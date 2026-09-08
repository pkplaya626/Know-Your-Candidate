"""Command-line entry point for the Know Your Candidate pipeline."""

import argparse
import json
import os
import sys

from . import (
    __version__,
    emit,
    fec,
    geo as geo_mod,
    legislators,
    overrides,
    portraits,
    profiles as profiles_mod,
    races as races_mod,
    sources,
    summary as summary_mod,
    validate,
    voteview,
)
from .profiles import build_profiles


def _load(args):
    """Read the rosters, or report why we cannot."""
    try:
        raw = sources.load_all(args.root)
    except sources.MissingRosterError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return None
    return raw


def _build(args):
    raw = _load(args)
    if raw is None:
        return 2

    for name, count in raw["found"]:
        print(f"  read {name} ({count} rows)")
    for name in raw["missing"]:
        print(f"  [warn] {name} not found - skipped")

    snapshot = legislators.load_snapshot(args.root)
    if snapshot:
        age = legislators.snapshot_age_days(snapshot)
        print(f"  read {legislators.SNAPSHOT_FILE} ({snapshot['count']} legislators"
              + (f", {age} days old)" if age is not None else ")"))
    else:
        print(f"  [warn] no {legislators.SNAPSHOT_FILE}; falling back to the "
              "curated 2026 Senate table. Run 'congress' to fetch one.")

    profiles, stats = build_profiles(raw, snapshot=snapshot)

    finance = fec.load_cache(args.root)
    stats["fec"] = fec.apply_cache(profiles, finance) if finance else 0
    if finance:
        print(f"  finance: {stats['fec']}/{len(profiles)} with FEC totals")

    cache = portraits.load_cache(args.root)
    if cache:
        stats["portraits"] = portraits.apply_cache(profiles, cache)
        print(f"  portraits: {stats['portraits']}/{len(profiles)} verified "
              f"({100 * stats['portraits'] / max(len(profiles), 1):.0f}%)")
    else:
        stats["portraits"] = 0
        print("  [warn] no portrait cache; run 'portraits' to resolve them")

    race_list = races_mod.build(profiles)
    stats.update(races_mod.stats(race_list))

    # The map geometry is a separate artefact with a separate source, so a
    # missing atlas degrades the map rather than failing the whole build.
    geo = None
    try:
        geo = geo_mod.build(args.root)
        stats.update(geo_mod.stats(geo))
    except geo_mod.AtlasError as exc:
        print(f"  [warn] map geometry unavailable: {exc}")

    print(
        f"\n[+] {stats['total']} profiles "
        f"({stats['members']} sitting members, {stats['candidates']} candidates)"
    )
    print(
        f"    {stats['senate_seats_up']} Senate seats up in 2026 | "
        f"{stats['voting_house']} voting House seats | "
        f"{stats['not_seeking']} incumbents not seeking re-election | "
        f"{stats['cross_linked']} members cross-linked to their own candidacy"
    )
    print(
        f"    {stats['races']} seats on the 2026 ballot | "
        f"{stats['contested']} with a declared challenger | "
        f"{stats['open_seats']} open (incumbent not running)"
    )
    if geo:
        print(f"    {stats['geo_states']} state shapes | "
              f"{stats['geo_territories']} territories")

    issues = validate.run(profiles, raw, races=race_list, geo=geo,
                          snapshot=snapshot, finance=finance)
    errors = [i for i in issues if i.level == "error"]

    if args.json:
        print(json.dumps(validate.as_dict(issues, stats), indent=2))
    elif issues:
        print()
        print(validate.format_report(issues, verbose=args.verbose))

    if errors and args.strict:
        print("\n[error] --strict set and errors found; not writing output.",
              file=sys.stderr)
        return 1

    if args.check:
        if not args.json:
            print("\n[check] validation only, nothing written.")
        return 1 if errors else 0

    summary = summary_mod.build(profiles, races=race_list)
    path, size = emit.write_profiles(
        profiles, stats, args.root, races=race_list, summary=summary
    )
    print(f"\n[ok] wrote {path} ({size / 1024:.0f} KB)")

    if geo:
        geo_path, geo_size = emit.write_geo(geo, args.root)
        print(f"[ok] wrote {geo_path} ({geo_size / 1024:.0f} KB)")

    for page, ok, note in emit.check_pages(args.root):
        print(f"     {'ok  ' if ok else 'WARN'} {page}: {note}")

    return 0


def _fetch(args):
    print(f"Downloading DW-NOMINATE data from {voteview.VOTEVIEW_URL} ...")
    try:
        rows = voteview.fetch_members()
    except voteview.VoteviewError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    alignment = voteview.build_alignment_map(rows)
    print(f"  parsed {len(rows)} rows -> {len(alignment)} scored members")

    total_updated = 0
    for roster in sources.MEMBER_ROSTERS:
        path = f"{args.root}/{roster}"
        updated, count = voteview.apply_to_roster(path, alignment)
        total_updated += updated
        if count:
            print(f"  {roster}: updated {updated} of {count} rows")
        else:
            print(f"  [warn] {roster} not found - skipped")

    if total_updated == 0:
        print("\n[warn] No rows changed. Bioguide IDs may not match the Voteview data.")
    else:
        print(f"\n[ok] Updated {total_updated} rows. Run 'build' to regenerate the site data.")
    return 0


def _portraits(args):
    raw = _load(args)
    if raw is None:
        return 2
    profiles, _ = build_profiles(raw)
    cache, _summary = portraits.resolve_all(
        profiles, root=args.root, refresh=args.refresh
    )
    unresolved = sorted(
        record.get("name", key) for key, record in cache.items()
        if not record.get("url")
    )
    if unresolved:
        print(f"\n  {len(unresolved)} without a portrait:")
        shown = unresolved if args.verbose else unresolved[:10]
        for name in shown:
            print(f"    - {name}")
        if len(shown) < len(unresolved):
            print(f"    ... {len(unresolved) - len(shown)} more (--verbose)")
    print(f"\n[ok] portrait cache: {portraits.CACHE_PATH}")
    return 0


def _finance(args):
    raw = _load(args)
    if raw is None:
        return 2
    snapshot = legislators.load_snapshot(args.root)
    profiles, _ = build_profiles(raw, snapshot=snapshot)
    fec.resolve_all(profiles, root=args.root, limit=args.limit,
                    refresh=args.refresh, snapshot=snapshot)
    print(f"\n[ok] finance cache: {fec.CACHE_PATH}")
    return 0


def _congress(args):
    """Reconcile the roster CSVs against the authoritative membership."""
    raw = _load(args)
    if raw is None:
        return 2

    if args.check:
        snapshot = legislators.load_snapshot(args.root)
        if snapshot is None:
            print(f"[error] no {legislators.SNAPSHOT_FILE}; run 'congress' first.",
                  file=sys.stderr)
            return 2
        age = legislators.snapshot_age_days(snapshot)
        print(f"  snapshot: {snapshot['count']} legislators, fetched "
              f"{snapshot.get('fetched', '?')}"
              + (f" ({age} days ago)" if age is not None else ""))
    else:
        print(f"Downloading the current roster from {legislators.SOURCE_URL} ...")
        try:
            snapshot = legislators.build_snapshot(legislators.fetch())
        except legislators.LegislatorsError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
        path = legislators.save_snapshot(snapshot, args.root)
        print(f"  wrote {path} ({snapshot['count']} legislators)")

    drift = legislators.reconcile(raw["members"], snapshot)
    print(f"\n  reconciliation: {drift.summary()}")

    for person in drift.missing:
        seat = (
            f"{person['state']}-{person['district']}"
            if person["chamber"] == "House" else person["state"]
        )
        print(f"    + serving but not in the roster: {person['name']} "
              f"({person['chamber']} {seat}, {person['party']}, "
              f"since {person['termStart']})")

    for person in drift.departed:
        print(f"    - in the roster but no longer serving: {person['name']} "
              f"({person['bioguide']})")

    shown = drift.changed if args.verbose else drift.changed[:10]
    for change in shown:
        print(f"    ~ {change['name']}: {change['field']} "
              f"roster={change['roster']!r} authoritative={change['authoritative']!r}")
    if len(shown) < len(drift.changed):
        print(f"    ... {len(drift.changed) - len(shown)} more (--verbose)")

    # Cross-check the curated 2026 Senate table against the real term dates.
    derived = legislators.seats_up(snapshot, profiles_mod.ELECTION_YEAR)
    curated = overrides.SENATE_SEATS_UP_2026
    only_derived = sorted(set(derived) - set(curated))
    only_curated = sorted(set(curated) - set(derived))
    if only_derived or only_curated:
        print(f"\n  [warn] 2026 Senate seats disagree with {len(curated)} curated entries:")
        if only_derived:
            print(f"    on the ballot but not curated: {', '.join(only_derived)}")
        if only_curated:
            print(f"    curated but not on the ballot: {', '.join(only_curated)}")
    else:
        print(f"\n  ok  all {len(derived)} 2026 Senate seats agree with the curated table")

    if args.apply:
        if not drift.missing:
            print("\n[ok] nothing to add.")
        else:
            added = legislators.apply_missing(drift, args.root)
            for roster, names in sorted(added.items()):
                print(f"\n[ok] added {len(names)} row(s) to {roster}:")
                for name in names:
                    print(f"       {name}")
            print("\nOnly the fields the dataset actually knows were filled. "
                  "Run `python build_profile_site.py` to regenerate the site.")
        if drift.departed:
            print("\n[note] departed members are not removed automatically. Add them "
                  "to overrides.EXCLUDED_MEMBERS if the seat is genuinely gone.")
        return 0

    if not drift.clean:
        print("\n[warn] the roster has drifted. Run `congress --apply` to add the "
              "missing members, or `--verbose` to see every difference.")
    return 0


def _verify(args):
    """Assert the committed data files still match the sources.

    CI used to answer this by rebuilding and running `git diff --exit-code`.
    That conflates two questions: whether the data is in sync, and when it was
    built. Because a rebuild stamps a fresh timestamp, keeping the diff quiet
    would have meant committing the fixed SOURCE_DATE_EPOCH date and showing
    2001 to readers as the site's freshness stamp.

    Comparing content signatures answers only the first question, works
    without git, and tells a contributor what to run.
    """
    raw = _load(args)
    if raw is None:
        return 2

    profiles, stats = build_profiles(raw, snapshot=legislators.load_snapshot(args.root))
    finance = fec.load_cache(args.root)
    stats["fec"] = fec.apply_cache(profiles, finance) if finance else 0
    cache = portraits.load_cache(args.root)
    stats["portraits"] = portraits.apply_cache(profiles, cache) if cache else 0

    race_list = races_mod.build(profiles)
    stats.update(races_mod.stats(race_list))
    summary = summary_mod.build(profiles, races=race_list)

    problems = []

    expected = emit.data_signature(profiles, race_list, summary)
    committed = emit.read_signature(args.root)
    if committed is None:
        problems.append(f"{emit.DATA_FILE} is missing or carries no signature")
    elif committed != expected:
        problems.append(
            f"{emit.DATA_FILE} is stale\n"
            f"       committed {committed[:16]}...\n"
            f"       rebuilt   {expected[:16]}..."
        )
    else:
        print(f"  ok  {emit.DATA_FILE} matches the rosters ({expected[:16]}...)")

    try:
        geo = geo_mod.build(args.root)
    except geo_mod.AtlasError as exc:
        problems.append(f"map geometry unavailable: {exc}")
    else:
        geo_expected = emit.geo_signature(geo)
        geo_committed = emit.read_signature(
            path=os.path.join(args.root, emit.GEO_FILE)
        )
        if geo_committed is None:
            problems.append(f"{emit.GEO_FILE} is missing or carries no signature")
        elif geo_committed != geo_expected:
            problems.append(f"{emit.GEO_FILE} is stale")
        else:
            print(f"  ok  {emit.GEO_FILE} matches the atlas ({geo_expected[:16]}...)")

    for page, ok, note in emit.check_pages(args.root):
        if ok:
            print(f"  ok  {page} loads its data in the right order")
        else:
            problems.append(f"{page}: {note}")

    if problems:
        print("\n[error] the committed site data is out of date:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("\nRun `python build_profile_site.py` and commit the result.",
              file=sys.stderr)
        return 1

    print("\n[ok] committed data is in sync with the sources.")
    return 0


def _geo(args):
    try:
        geo = geo_mod.build(args.root)
    except geo_mod.AtlasError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    path, size = emit.write_geo(geo, args.root)
    print(f"[ok] wrote {path} ({size / 1024:.0f} KB) "
          f"- {len(geo['states'])} states, {len(geo['territories'])} territories")
    return 0


def _add_build_flags(parser):
    parser.add_argument("--check", action="store_true",
                        help="validate only; do not write output")
    parser.add_argument("--strict", action="store_true",
                        help="refuse to write when validation reports an error")
    parser.add_argument("--json", action="store_true",
                        help="print the validation report as JSON")


def _subcommand_flags():
    """``--root`` / ``--verbose`` again, for use *after* the subcommand.

    ``build --check --strict --verbose`` is the obvious thing to type, and it
    used to fail with "unrecognized arguments: --verbose" because the flag
    existed only on the top-level parser.

    Two details here are load-bearing:

    * The defaults are ``SUPPRESS`` so that ``--verbose build`` is not undone
      by the subparser writing its own default back over the namespace.
    * These are a *separate* parser from the top-level flags rather than one
      shared parent, because ``parents=`` shares the action objects and
      ``set_defaults`` mutates ``action.default`` in place - so seeding a
      default on the top-level parser silently replaced the SUPPRESS in every
      subparser and reintroduced exactly the bug it was meant to prevent.
    """
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--root", default=argparse.SUPPRESS,
                        help="repository root (default: .)")
    shared.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS,
                        help="list every item in a validation finding")
    return shared


def build_parser():
    parser = argparse.ArgumentParser(
        prog="build_profile_site.py",
        description="Build the Know Your Candidate site data from the roster CSVs.",
    )
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--verbose", action="store_true",
                        help="list every item in a validation finding")
    parser.add_argument("--version", action="version",
                        version=f"know-your-candidate {__version__}")

    shared = _subcommand_flags()
    sub = parser.add_subparsers(dest="command")

    def add(name, **kwargs):
        return sub.add_parser(name, parents=[shared], **kwargs)

    _add_build_flags(add("build", help="generate candidate_profiles_site/data/*.js"))

    add("fetch", help="refresh DW-NOMINATE scores from Voteview")
    add("geo", help="regenerate the map geometry from the state atlas")
    add("verify", help="check the committed data still matches the sources")

    congress = add("congress",
                   help="reconcile the rosters against the authoritative membership")
    congress.add_argument("--check", action="store_true",
                          help="use the committed snapshot; make no network call")
    congress.add_argument("--apply", action="store_true",
                          help="add newly seated members to the roster CSVs")

    pics = add("portraits", help="resolve and verify portrait URLs")
    pics.add_argument("--refresh", action="store_true",
                      help="re-verify every portrait, not just missing ones")

    money = add("finance", help="look up FEC campaign finance totals")
    money.add_argument("--limit", type=int, default=None,
                       help="stop after N lookups (useful on a rate-limited key)")
    money.add_argument("--refresh", action="store_true",
                       help="re-query profiles already cached")

    _add_build_flags(add("refresh", help="fetch, then build"))
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    # A bare invocation keeps the historical behaviour: just build.
    if args.command is None:
        args.command = "build"
        for flag in ("check", "strict", "json"):
            setattr(args, flag, False)

    if args.command == "fetch":
        return _fetch(args)
    if args.command == "geo":
        return _geo(args)
    if args.command == "verify":
        return _verify(args)
    if args.command == "congress":
        return _congress(args)
    if args.command == "portraits":
        return _portraits(args)
    if args.command == "finance":
        return _finance(args)
    if args.command == "refresh":
        code = _fetch(args)
        if code:
            return code
        print()
    return _build(args)


if __name__ == "__main__":
    raise SystemExit(main())
