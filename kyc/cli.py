"""Command-line entry point for the Know Your Candidate pipeline."""

import argparse
import sys

from . import emit, fec, portraits, races as races_mod, sources, validate, voteview
from .profiles import build_profiles


def _build(args):
    try:
        raw = sources.load_all(args.root)
    except sources.MissingRosterError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    for name, count in raw["found"]:
        print(f"  read {name} ({count} rows)")
    for name in raw["missing"]:
        print(f"  [warn] {name} not found - skipped")

    profiles, stats = build_profiles(raw)

    finance = fec.load_cache(args.root)
    if finance:
        applied = fec.apply_cache(profiles, finance)
        stats["fec"] = applied
        print(f"  finance: {applied}/{len(profiles)} with FEC totals")
    else:
        stats["fec"] = 0

    cache = portraits.load_cache(args.root)
    if cache:
        hits = portraits.apply_cache(profiles, cache)
        stats["portraits"] = hits
        print(f"  portraits: {hits}/{len(profiles)} verified "
              f"({100 * hits / max(len(profiles), 1):.0f}%)")
    else:
        stats["portraits"] = 0
        print("  [warn] no portrait cache; run 'portraits' to resolve them")

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

    race_list = races_mod.build(profiles)
    stats.update(races_mod.stats(race_list))
    print(
        f"    {stats['races']} seats on the 2026 ballot | "
        f"{stats['contested']} with a declared challenger | "
        f"{stats['open_seats']} open (incumbent not running)"
    )

    issues = validate.run(profiles, raw)
    errors = [i for i in issues if i.level == "error"]
    if issues:
        print()
        print(validate.format_report(issues, verbose=args.verbose))

    if errors and args.strict:
        print("\n[error] --strict set and errors found; not writing output.", file=sys.stderr)
        return 1

    if args.check:
        print("\n[check] validation only, nothing written.")
        return 1 if errors else 0

    path, size = emit.write_profiles(profiles, stats, args.root, races=race_list)
    print(f"\n[ok] wrote {path} ({size / 1024:.0f} KB)")

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
    try:
        raw = sources.load_all(args.root)
    except sources.MissingRosterError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    profiles, _ = build_profiles(raw)
    cache, summary = portraits.resolve_all(
        profiles, root=args.root, refresh=args.refresh
    )
    unresolved = sorted(
        r.get("name", key) for key, r in cache.items() if not r.get("url")
    )
    if unresolved:
        print(f"\n  {len(unresolved)} without a portrait:")
        for name in unresolved[: 40 if args.verbose else 10]:
            print(f"    - {name}")
        if not args.verbose and len(unresolved) > 10:
            print(f"    ... {len(unresolved) - 10} more (--verbose)")
    print(f"\n[ok] portrait cache: {portraits.CACHE_PATH}")
    return 0


def _finance(args):
    try:
        raw = sources.load_all(args.root)
    except sources.MissingRosterError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    profiles, _ = build_profiles(raw)
    _, summary = fec.resolve_all(
        profiles, root=args.root, limit=args.limit, refresh=args.refresh
    )
    print(f"\n[ok] finance cache: {fec.CACHE_PATH}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="build_profile_site.py",
        description="Build the Know Your Candidate site data from the roster CSVs.",
    )
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--verbose", action="store_true",
                        help="list every item in a validation finding")

    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser("build", help="generate candidate_profiles_site/data/profiles.js")
    build.add_argument("--check", action="store_true",
                       help="validate only; do not write output")
    build.add_argument("--strict", action="store_true",
                       help="refuse to write when validation reports an error")

    sub.add_parser("fetch", help="refresh DW-NOMINATE scores from Voteview")

    pics = sub.add_parser("portraits", help="resolve and verify portrait URLs")
    pics.add_argument("--refresh", action="store_true",
                      help="re-verify every portrait, not just missing ones")

    money = sub.add_parser("finance", help="look up FEC campaign finance totals")
    money.add_argument("--limit", type=int, default=None,
                       help="stop after N lookups (useful on a rate-limited key)")
    money.add_argument("--refresh", action="store_true",
                       help="re-query profiles already cached")

    refresh = sub.add_parser("refresh", help="fetch, then build")
    refresh.add_argument("--check", action="store_true")
    refresh.add_argument("--strict", action="store_true")

    # Bare invocation keeps the historical behaviour: just build.
    args = parser.parse_args(argv)
    if args.command is None:
        args.command = "build"
        args.check = getattr(args, "check", False)
        args.strict = getattr(args, "strict", False)

    if args.command == "fetch":
        return _fetch(args)
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
