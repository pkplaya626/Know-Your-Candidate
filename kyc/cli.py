"""Command-line entry point for the Know Your Candidate pipeline."""

import argparse
import json
import os
import re
import sys

from . import (
    __version__,
    campaigns,
    districts as districts_mod,
    emit,
    fec,
    geo as geo_mod,
    candidates,
    disclosures,
    enrich,
    legislators,
    odds as odds_mod,
    overrides,
    portraits,
    profiles as profiles_mod,
    races as races_mod,
    results as results_mod,
    sources,
    summary as summary_mod,
    validate,
    voteview,
)
from .profiles import build_profiles, screen_field


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

    field = candidates.load_cache(args.root)
    if field:
        print(f"  read {candidates.CACHE_PATH} ({field['count']} FEC filers)")
    else:
        print(f"  [warn] no FEC candidate field; run 'field'. Races will report "
              "only the roster's challengers.")

    finance = fec.load_cache(args.root)
    committees = legislators.load_committees(args.root)
    if committees:
        print(f"  read {legislators.COMMITTEES_FILE} "
              f"({len(committees['members'])} members with assignments)")
    profiles, stats = build_profiles(raw, snapshot=snapshot, field=field,
                                     finance=finance, committees=committees)
    # The same screen build_profiles applied: filedCount and validation must
    # count the field the profiles were built from.
    field = screen_field(field, profiles)
    if field:
        print(f"  field: {field['count']} filings for races on the 2026 ballot "
              f"({stats['field_stale']} stale registrations and "
              f"{stats['field_phantom']} filings for seats not up set aside)")
    stats["fec"] = fec.apply_cache(profiles, finance) if finance else 0
    # Filed candidates arrive with their totals from the field register, so
    # the finance cache covers only the roster. Count what the page shows.
    stats["with_finance"] = sum(1 for p in profiles if p.get("financeSource") == "FEC")
    if finance:
        print(f"  finance: {stats['with_finance']}/{len(profiles)} with FEC totals "
              f"({stats['fec']} roster profiles from the finance cache, the rest "
              f"from the candidate field)")

    filings = disclosures.load_cache(args.root)
    stats["disclosures"] = disclosures.apply_cache(profiles, filings) if filings else 0
    if filings:
        print(f"  disclosures: {stats['disclosures']} members linked to a filing")

    sites = campaigns.load_cache(args.root)
    stats["campaign_sites"] = campaigns.apply_cache(profiles, sites) if sites else 0
    if sites:
        withheld = len(campaigns.blocked_sites(sites))
        print(f"  campaigns: {stats['campaign_sites']} profiles with a campaign website"
              f" ({withheld} withheld as lapsed or hijacked)")

    cache = portraits.load_cache(args.root)
    if cache:
        stats["portraits"] = portraits.apply_cache(profiles, cache)
        print(f"  portraits: {stats['portraits']}/{len(profiles)} verified "
              f"({100 * stats['portraits'] / max(len(profiles), 1):.0f}%)")
    else:
        stats["portraits"] = 0
        print("  [warn] no portrait cache; run 'portraits' to resolve them")

    outcomes = results_mod.load_cache(args.root)
    stats["results"] = results_mod.apply_cache(profiles, outcomes) if outcomes else 0
    if outcomes:
        print(f"  results: {stats['results']} candidates with a primary outcome "
              f"(as of {outcomes.get('asOf')})")
    else:
        print("  [warn] no primary results; run 'results'. Eliminated candidates "
              "will still show as running.")

    # After the results: who is still running, and the article and campaign
    # site their state's election page links, both arrive with them.
    enrichment = enrich.load_cache(args.root)
    if enrichment:
        filled = enrich.apply_cache(profiles, enrichment, as_of=_age_date(stats))
        stats["enriched"] = dict(sorted(filled.items()))
        print("  enrich: " + ", ".join(f"{n} {k}" for k, n in sorted(filled.items()))
              + f" (read {enrichment.get('checked')})")
    else:
        print("  [warn] no enrichment cache; run 'enrich' to read candidates' "
              "articles and campaign sites")

    race_list = races_mod.build(profiles, candidates.filing_counts(field),
                                results=outcomes, dates=results_mod.load_dates(args.root))
    stats.update(races_mod.stats(race_list))
    markets = odds_mod.load_cache(args.root)
    if markets:
        reach = odds_mod.coverage(markets, race_list)
        print(f"  odds: markets for {reach['senate'][0]}/{reach['senate'][1]} Senate and "
              f"{reach['house'][0]}/{reach['house'][1]} House races, polling averages for "
              f"{reach['polls']} (fetched {markets.get('fetched')}); "
              f"{reach['unprofiled']} outcome labels name a nominee with no profile here "
              "and show as their party")
    else:
        print("  [warn] no odds cache; run 'odds' for market prices and polling averages")
    # The results settle who is on the ballot, so count after applying them.
    stats["not_seeking"] = sum(
        1 for p in profiles
        if p["seatUp2026"] and not p["isCandidate"] and not p["seekingReelection2026"]
    )

    # The map geometry is a separate artefact with a separate source, so a
    # missing atlas degrades the map rather than failing the whole build.
    geo = None
    try:
        geo = geo_mod.build(args.root)
        stats.update(geo_mod.stats(geo))
    except geo_mod.AtlasError as exc:
        print(f"  [warn] map geometry unavailable: {exc}")

    # The before-and-after district maps are vendored and checked in, so a
    # failure here is a data error, not a missing download: validation
    # reports it as one, and --strict refuses to write.
    district_maps, district_error = None, None
    try:
        district_maps = districts_mod.build(args.root)
        stats.update(districts_mod.stats(district_maps))
    except districts_mod.DistrictsError as exc:
        district_error = str(exc)

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
    if district_maps:
        redrawn = sorted(c for c, s in district_maps.items() if len(s["plans"]) == 2)
        print(f"    {len(district_maps)} district maps; redrawn for 2026: "
              f"{', '.join(redrawn)}")

    issues = validate.run(profiles, raw, races=race_list, geo=geo,
                          snapshot=snapshot, finance=finance, campaigns=sites,
                          results=outcomes, field=field, enrichment=enrichment,
                          odds=markets, district_maps=district_maps,
                          district_error=district_error)
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

    summary = summary_mod.build(profiles, races=race_list,
                                committees=legislators.load_committees(args.root))
    path, size = emit.write_profiles(
        profiles, stats, args.root, races=race_list, summary=summary
    )
    print(f"\n[ok] wrote {path} ({size / 1024:.0f} KB)")

    if geo:
        geo_path, geo_size = emit.write_geo(geo, args.root)
        print(f"[ok] wrote {geo_path} ({geo_size / 1024:.0f} KB)")
    if district_maps:
        files = emit.write_districts(district_maps, args.root)
        print(f"[ok] wrote {len(files)} district maps under {emit.DISTRICTS_DIR} "
              f"({sum(size for _, size in files) / 1024:.0f} KB)")

    # Rewritten only when the prices changed, so a roster rebuild leaves the
    # odds refresh's file alone.
    page_odds = odds_mod.payload(markets)
    odds_file = os.path.join(args.root, emit.ODDS_FILE)
    if emit.read_signature(path=odds_file) != emit.odds_signature(page_odds):
        odds_path, odds_size = emit.write_odds(page_odds, args.root)
        print(f"[ok] wrote {odds_path} ({odds_size / 1024:.0f} KB)")

    # Each state's legislature: districts and members, rewritten per state
    # only when its content changed.
    from . import legislature as legislature_mod
    try:
        legislatures = legislature_mod.build(args.root)
    except legislature_mod.LegislatureError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    written_legs = emit.write_legislature(legislatures, args.root)
    leg_stats = legislature_mod.stats(legislatures)
    print(f"[ok] state legislatures: {leg_stats['states']} states, {leg_stats['districts']:,} "
          f"districts, {leg_stats['placed']:,} members placed, {leg_stats['unplaced']} listed off "
          f"the map; {len(written_legs)} file(s) rewritten")

    # The guide's maps: rewritten only when what they say changed.
    from . import government_maps
    guide_maps = government_maps.payload()
    guide_file = os.path.join(args.root, emit.GOVERNMENT_FILE)
    if emit.read_signature(path=guide_file) != emit.government_signature(guide_maps):
        guide_path, guide_size = emit.write_government(guide_maps, args.root)
        print(f"[ok] wrote {guide_path} ({guide_size / 1024:.0f} KB)")

    written = emit.write_state_pages(profiles, args.root, summary=summary)
    maps = [w for w in written
            if os.path.normpath(emit.DISTRICT_PAGES_DIR) in os.path.normpath(w)]
    states = [w for w in written if os.path.normpath(emit.STATES_DIR) in os.path.normpath(w)]
    print(f"[ok] wrote {len(states)} state pages under {emit.STATES_DIR} and "
          f"{len(maps)} district pages under {emit.DISTRICT_PAGES_DIR}")
    sitemap_path = emit.write_sitemap(profiles, args.root)
    if sitemap_path:
        print(f"[ok] wrote {sitemap_path}")

    for page, ok, note in emit.check_pages(args.root):
        if ok and page.startswith(("states/", "districts/")):
            continue                    # 113 identical "ok" lines say nothing
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
    # The whole field, with results applied: a filed candidate is only
    # resolvable through the article their state's ballot page links to,
    # and that title arrives with the primary results.
    finance = fec.load_cache(args.root)
    profiles, _ = build_profiles(raw, snapshot=legislators.load_snapshot(args.root),
                                 field=candidates.load_cache(args.root), finance=finance)
    fec.apply_cache(profiles, finance)
    results_mod.apply_cache(profiles, results_mod.load_cache(args.root))
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


def _campaigns(args):
    """Look up campaign websites from each candidate's principal committee."""
    raw = _load(args)
    if raw is None:
        return 2
    field = candidates.load_cache(args.root)
    finance = fec.load_cache(args.root)
    profiles, _ = build_profiles(raw, snapshot=legislators.load_snapshot(args.root),
                                 field=field, finance=finance)
    fec.apply_cache(profiles, finance)
    # Statuses decide who is worth a request: nobody the primary removed.
    results_mod.apply_cache(profiles, results_mod.load_cache(args.root))
    if args.check:
        cache = campaigns.load_cache(args.root)
        if not cache:
            print(f"[error] no {campaigns.CACHE_PATH}; run 'campaigns' first.",
                  file=sys.stderr)
            return 2
        on_ballot = campaigns.wanted(profiles)
        known = sum(1 for p in on_ballot if p["fecCandidateId"] in cache)
        sites = sum(1 for p in on_ballot if (cache.get(p["fecCandidateId"]) or {}).get("url"))
        print(f"  campaigns: {known} of {len(on_ballot)} people on a ballot looked up, "
              f"{sites} with a website")
        return 0
    _, stats = campaigns.resolve_all(profiles, root=args.root, limit=args.limit,
                                     refresh=args.refresh)
    print(f"\n[ok] campaigns cache: {campaigns.CACHE_PATH}")
    return 1 if stats.get("stopped") else 0


def _age_date(stats):
    """The date the build computes every age at (``profiles.age_as_of``)."""
    import datetime

    return datetime.date.fromisoformat(stats["ageAsOf"])


def _enrich(args):
    """Read the articles and campaign sites of everyone still running."""
    raw = _load(args)
    if raw is None:
        return 2
    field = candidates.load_cache(args.root)
    finance = fec.load_cache(args.root)
    profiles, stats = build_profiles(raw, snapshot=legislators.load_snapshot(args.root),
                                     field=field, finance=finance)
    fec.apply_cache(profiles, finance)
    campaigns.apply_cache(profiles, campaigns.load_cache(args.root))
    portraits.apply_cache(profiles, portraits.load_cache(args.root))
    # Who is still running, and the article and site the election page links.
    results_mod.apply_cache(profiles, results_mod.load_cache(args.root))
    if args.check:
        cache = enrich.load_cache(args.root)
        if not cache:
            print(f"[error] no {enrich.CACHE_PATH}; run 'enrich' first.", file=sys.stderr)
            return 2
        filled = enrich.apply_cache(profiles, cache, as_of=_age_date(stats))
        print("  enrich: " + ", ".join(f"{n} {k}" for k, n in sorted(filled.items())))
    else:
        cache, _counts = enrich.resolve_all(profiles, root=args.root, refresh=args.refresh,
                                            limit=args.limit)
        print(f"\n[ok] enrichment cache: {enrich.CACHE_PATH}")
    found = enrich.problems(profiles, cache)
    for title, lines in (("withdrawn as hijacked or parked", found["withdrawn"]),
                         ("kept, but the page could not confirm them", found["unconfirmed"]),
                         ("kept, but compromised with hidden gambling links",
                          found["compromised"])):
        if lines:
            print(f"\n  {len(lines)} committee site(s) {title}:")
            for line in (lines if args.verbose else lines[:10]):
                print(f"    - {line}")
            if not args.verbose and len(lines) > 10:
                print(f"    ... {len(lines) - 10} more (--verbose)")
    return 0


def _odds(args):
    """Market prices and polling averages for every 2026 Senate race."""
    raw = _load(args)
    if raw is None:
        return 2
    field = candidates.load_cache(args.root)
    finance = fec.load_cache(args.root)
    profiles, _ = build_profiles(raw, snapshot=legislators.load_snapshot(args.root),
                                 field=field, finance=finance)
    fec.apply_cache(profiles, finance)
    outcomes = results_mod.load_cache(args.root)
    results_mod.apply_cache(profiles, outcomes)
    race_list = races_mod.build(profiles, candidates.filing_counts(screen_field(field, profiles)),
                                results=outcomes, dates=results_mod.load_dates(args.root))
    by_id = {p["id"]: p for p in profiles}

    def people_of(race):
        # Who a market label or a poll column may name: anyone still in it,
        # and the nominees the results page lists with no FEC filing over
        # $5,000 - in the race, though they have no profile here.
        ids = race.get("incumbentIds", []) + race.get("candidateIds", [])
        people = [by_id[i] for i in ids
                  if i in by_id and by_id[i].get("raceStatus") not in results_mod.OFF_BALLOT]
        unfiled = ((race.get("results") or {}).get("otherNominees") or [])
        return people + [{"name": name} for name in unfiled]

    if args.check:
        cache = odds_mod.load_cache(args.root)
        if not cache:
            print(f"[error] no {odds_mod.CACHE_PATH}; run 'odds' first.", file=sys.stderr)
            return 2
    else:
        cache = odds_mod.build(race_list, people_of)
        odds_mod.save_cache(cache, args.root)
        odds_path, _ = emit.write_odds(odds_mod.payload(cache), args.root)
        print(f"\n[ok] odds cache: {odds_mod.CACHE_PATH}; page data: {odds_path}")
    reach = odds_mod.coverage(cache, race_list)
    print(f"  markets for {reach['senate'][0]} of {reach['senate'][1]} Senate and "
          f"{reach['house'][0]} of {reach['house'][1]} House races; polling averages for "
          f"{reach['polls']}; control of "
          f"{' and '.join(sorted(cache.get('control') or {})) or 'neither chamber'} "
          f"(fetched {cache.get('fetched')})")
    notes = cache.get("notes") or []
    if notes:
        print(f"\n  {len(notes)} note(s):")
        for note in (notes if args.verbose else notes[:12]):
            print(f"    - {note}")
    return 0


def _finance(args):
    raw = _load(args)
    if raw is None:
        return 2
    snapshot = legislators.load_snapshot(args.root)
    profiles, _ = build_profiles(raw, snapshot=snapshot)
    field = candidates.load_cache(args.root)
    active = {r["candidate_id"] for r in (field or {}).get("candidates", [])}
    fec.resolve_all(profiles, root=args.root, limit=args.limit,
                    refresh=args.refresh, snapshot=snapshot, active_ids=active)
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
            rows = legislators.fetch()
        except legislators.LegislatorsError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
        # The companion files are supplementary: a failure is reported and
        # the membership snapshot is still written, because a missing
        # Twitter handle is an absence and a missing member is an error.
        social = None
        try:
            social = legislators.fetch_json(legislators.SOCIAL_URL)
            print(f"  social media: {len(social)} accounts")
        except legislators.LegislatorsError as exc:
            print(f"  [warn] {exc}")
        snapshot = legislators.build_snapshot(rows, social=social)
        path = legislators.save_snapshot(snapshot, args.root)
        print(f"  wrote {path} ({snapshot['count']} legislators)")
        try:
            membership = legislators.fetch_json(legislators.MEMBERSHIP_URL)
            committees = legislators.fetch_json(legislators.COMMITTEES_URL)
        except legislators.LegislatorsError as exc:
            print(f"  [warn] {exc}")
        else:
            data = legislators.build_committees(membership, committees)
            path = legislators.save_committees(data, args.root)
            print(f"  wrote {path} ({len(data['committees'])} committees, "
                  f"{len(data['members'])} members with assignments)")

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


def _field(args):
    """Refresh the FEC's register of who has filed for the cycle."""
    if args.check:
        cache = candidates.load_cache(args.root)
        if cache is None:
            print(f"[error] no {candidates.CACHE_PATH}; run 'field' first.",
                  file=sys.stderr)
            return 2
    else:
        print("Downloading the 2026 candidate field from the FEC ...")
        try:
            cache = candidates.build_cache(candidates.fetch(log=print))
        except (candidates.FieldError, fec.FecError) as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
        path = candidates.save_cache(cache, args.root)
        print(f"  wrote {path}")

    # Screen exactly as the build does, so these numbers are the site's.
    raw_count = cache["count"]
    raw = _load(args)
    if raw is None:
        return 2
    profiles, _ = build_profiles(raw, snapshot=legislators.load_snapshot(args.root))
    cache = screen_field(cache, profiles)
    screened = cache["screened"]
    print(f"\n  {raw_count} registrations list {cache['cycle']}; set aside "
          f"{len(screened['stale'])} with no report since {screened['cycleStart']} "
          f"and {len(screened['phantom'])} for seats not on the ballot")
    if getattr(args, "verbose", False):
        for kind in ("stale", "phantom"):
            for row in screened[kind]:
                print(f"    {kind:7} {row['candidate_id']} {row.get('name')} "
                      f"{candidates.race_id(row)} (through {row.get('coverage_end_date')})")

    counts = candidates.filing_counts(cache)
    keep = candidates.eligible(cache)
    print(f"\n  {cache['count']} people have filed for {cache['cycle']}")
    print(f"  {len(counts)} seats have at least one filing")
    print(f"  {len(keep)} are past the ${candidates.STATUTORY_THRESHOLD:,} "
          f"statutory threshold and are not the sitting member")

    busiest = sorted(counts.items(), key=lambda kv: -kv[1])[:8]
    print("\n  most contested seats by filings:")
    for rid, n in busiest:
        print(f"    {rid:18} {n:>3} filed")
    return 0


def _disclosures(args):
    """Link members to their filed financial disclosures."""
    import datetime

    raw = _load(args)
    if raw is None:
        return 2
    profiles, _ = build_profiles(
        raw, snapshot=legislators.load_snapshot(args.root)
    )

    if args.check:
        found = disclosures.load_cache(args.root)
        if not found:
            print(f"[error] no {disclosures.CACHE_PATH}; run 'disclosures' first.",
                  file=sys.stderr)
            return 2
    else:
        year = datetime.date.today().year
        filings = []
        for which in (year, year - 1):
            print(f"Downloading the {which} House disclosure index ...")
            try:
                got = disclosures.fetch_year(which)
            except disclosures.DisclosureError as exc:
                print(f"  [warn] {exc}")
                continue
            print(f"  {len(got)} filings")
            filings.extend(got)
        if not filings:
            print("[error] no disclosure index could be read.", file=sys.stderr)
            return 2
        found = disclosures.match(profiles, filings)
        print("Searching the Senate's eFD for senators' annual reports ...")
        try:
            found.update(disclosures.match_senate(profiles))
        except disclosures.DisclosureError as exc:
            # The House links stand on their own; a Senate outage keeps last
            # run's Senate links rather than writing them out (rule 8).
            print(f"  [warn] {exc}; keeping the cached Senate links")
            previous = disclosures.load_cache(args.root)
            found.update({k: v for k, v in previous.items()
                          if v.get("source") == disclosures.SENATE_SOURCE})
        print(f"  wrote {disclosures.save_cache(found, args.root)}")

    members = [p for p in profiles if not p["isCandidate"]]
    for chamber in ("House", "Senate"):
        seated = [p for p in members if p["chamber"] == chamber]
        have = sum(1 for p in seated if p["id"] in found)
        print(f"  {have} of {len(seated)} {chamber} members have an annual report on file")
    return 0


def _results(args):
    """Resolve primary results: who is still in each race."""
    import datetime

    field = candidates.load_cache(args.root)
    if field is None:
        print(f"[error] no {candidates.CACHE_PATH}; run 'field' first.", file=sys.stderr)
        return 2

    if args.check:
        cache = results_mod.load_cache(args.root)
        if cache is None:
            print(f"[error] no {results_mod.CACHE_PATH}; run 'results' first.",
                  file=sys.stderr)
            return 2
        print(f"  results as of {cache.get('asOf')}")
    else:
        print("Fetching the 2026 election calendar from the FEC ...")
        try:
            dates = results_mod.fetch_dates()
        except (results_mod.ResultsError, fec.FecError) as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
        print(f"  {len(dates)} state/office calendars")
        # Curated roster candidates carry a display name the FEC does not use
        # ("Ken Paxton" for "PAXTON, WARREN KENNETH JR."), and the finance
        # lookup has already tied that name to a candidate id.
        aliases = {}
        # Matched against the same screened field the build uses: only
        # races on the 2026 ballot. The raw register listed Senate "races"
        # for states with no seat up (S-AZ, S-CA, S-NY ...) as pending
        # primaries, and stale registrations as people to match.
        raw = _load(args)
        if raw is None:
            return 2
        snapshot = legislators.load_snapshot(args.root)
        profiles, _ = build_profiles(raw, snapshot=snapshot)
        field = screen_field(field, profiles)
        print(f"  field: {field['count']} filings for races on the 2026 ballot "
              f"({len(field['screened']['stale'])} stale and "
              f"{len(field['screened']['phantom'])} for absent races set aside)")
        fec.apply_cache(profiles, fec.load_cache(args.root))
        filed = {row["candidate_id"]: row for row in field["candidates"]}
        known = {person["bioguide"]: person
                 for person in (snapshot or {}).get("legislators", [])}
        for profile in profiles:
            cid = profile.get("fecCandidateId")
            # A member with no filing this cycle is keyed on their
            # bioguide id instead, so the page can still say whether they
            # are on the ballot: the FEC field lacked Nick LaLota while
            # New York's page had him on the November ballot.
            key = cid if cid in filed else (
                profile["id"] if not profile["isCandidate"] else cid)
            if not key:
                continue
            # The alias belongs to the race the filing is for, which is
            # not always the seat the roster gives: after redistricting
            # Ami Bera holds CA-6 and is filed for CA-3, and the CA-3
            # results name him.
            rid = candidates.race_id(filed[cid]) if cid in filed else candidates.race_id({
                "state": profile["state"],
                "office": "S" if "Senate" in profile["chamber"] else "H",
                "district_number": profile.get("districtNum"),
            })
            if not rid:
                continue
            names = {profile["name"]}
            person = known.get(profile["id"])
            if person:
                # The article title is the spelling the election page
                # links to: "Andy Barr", not the roster's "Garland Barr".
                names.update(
                    re.sub(r"\s*\([^)]*\)\s*$", "", n)      # "Dan Sullivan (U.S. senator)"
                    for n in (person.get("name"), person.get("wikipedia")) if n
                )
            for name in sorted(names):
                aliases.setdefault(rid, []).append((name, key))
        print("Reading primary results from Wikipedia ...")
        cache = results_mod.build(field, dates, today=datetime.date.today(), log=print,
                                  aliases=aliases)
        print(f"  wrote {results_mod.save_cache(cache, args.root)}")

    import collections
    tally = collections.Counter(
        status for race in cache["races"].values() for status in race["status"].values()
    )
    print(f"\n  races with results: {len(cache['races'])}   "
          f"primaries still to come: {len(cache.get('pending', []))}")
    for status, n in sorted(tally.items()):
        print(f"    {status:12} {n:>5}")
    unmatched = sum(len(r.get("unmatched") or ()) for r in cache["races"].values())
    ambiguous = sum(len(r.get("ambiguous", [])) for r in cache["races"].values())
    print(f"    names on Wikipedia with no matching filing: {unmatched}")
    print(f"    names left alone as ambiguous:              {ambiguous}")
    if cache.get("missingPages"):
        print(f"    state pages not found: {', '.join(cache['missingPages'])}")
    if args.verbose:
        for rid, race in sorted(cache["races"].items()):
            if race.get("ambiguous"):
                print(f"    ~ {rid}: ambiguous {race['ambiguous']}")
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

    finance = fec.load_cache(args.root)
    profiles, stats = build_profiles(
        raw,
        snapshot=legislators.load_snapshot(args.root),
        field=candidates.load_cache(args.root),
        finance=finance,
        committees=legislators.load_committees(args.root),
    )
    stats["fec"] = fec.apply_cache(profiles, finance) if finance else 0
    cache = portraits.load_cache(args.root)
    stats["portraits"] = portraits.apply_cache(profiles, cache) if cache else 0
    filings = disclosures.load_cache(args.root)
    stats["disclosures"] = disclosures.apply_cache(profiles, filings) if filings else 0
    stats["campaign_sites"] = campaigns.apply_cache(profiles, campaigns.load_cache(args.root))

    outcomes = results_mod.load_cache(args.root)
    stats["results"] = results_mod.apply_cache(profiles, outcomes) if outcomes else 0
    enrich.apply_cache(profiles, enrich.load_cache(args.root), as_of=_age_date(stats))
    race_list = races_mod.build(
        profiles, candidates.filing_counts(
            screen_field(candidates.load_cache(args.root), profiles)),
        results=outcomes, dates=results_mod.load_dates(args.root),
    )
    stats.update(races_mod.stats(race_list))
    summary = summary_mod.build(profiles, races=race_list,
                                committees=legislators.load_committees(args.root))

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

    stale_pages = emit.check_state_pages(profiles, args.root, summary=summary)
    if stale_pages:
        problems.append(f"{len(stale_pages)} state page(s) are {stale_pages[0][1]}: "
                        + ", ".join(rel for rel, _ in stale_pages[:5])
                        + (" ..." if len(stale_pages) > 5 else ""))
    else:
        print(f"  ok  {emit.STATES_DIR} pages match the template")

    odds_expected = emit.odds_signature(odds_mod.payload(odds_mod.load_cache(args.root)))
    odds_committed = emit.read_signature(path=os.path.join(args.root, emit.ODDS_FILE))
    if odds_committed is None:
        problems.append(f"{emit.ODDS_FILE} is missing or carries no signature")
    elif odds_committed != odds_expected:
        problems.append(f"{emit.ODDS_FILE} is stale")
    else:
        print(f"  ok  {emit.ODDS_FILE} matches odds.json ({odds_expected[:16]}...)")

    from . import legislature as legislature_mod
    try:
        stale_legs = emit.check_legislature(legislature_mod.build(args.root), args.root)
    except legislature_mod.LegislatureError as exc:
        problems.append(f"state legislatures unavailable: {exc}")
    else:
        if stale_legs:
            problems.append(f"{len(stale_legs)} legislature file(s) are {stale_legs[0][1]}: "
                            + ", ".join(os.path.basename(p) for p, _ in stale_legs[:5]))
        else:
            print(f"  ok  {emit.LEGISLATURE_DIR}: every state matches its maps and roster")

    from . import government_maps
    guide_expected = emit.government_signature(government_maps.payload())
    guide_committed = emit.read_signature(path=os.path.join(args.root, emit.GOVERNMENT_FILE))
    if guide_committed is None:
        problems.append(f"{emit.GOVERNMENT_FILE} is missing or carries no signature")
    elif guide_committed != guide_expected:
        problems.append(f"{emit.GOVERNMENT_FILE} is stale")
    else:
        print(f"  ok  {emit.GOVERNMENT_FILE} matches kyc/government_maps.py "
              f"({guide_expected[:16]}...)")

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

    try:
        district_maps = districts_mod.build(args.root)
    except districts_mod.DistrictsError as exc:
        problems.append(f"district maps unavailable: {exc}")
    else:
        stale_maps = emit.check_districts(district_maps, args.root)
        if stale_maps:
            problems.append(f"{len(stale_maps)} district map file(s) are "
                            f"{stale_maps[0][1]}: " + ", ".join(
                                os.path.basename(p) for p, _ in stale_maps[:5]))
        else:
            print(f"  ok  {emit.DISTRICTS_DIR}: {len(district_maps)} maps match "
                  f"{districts_mod.MAPS_DIR}")

    for page, ok, note in emit.check_pages(args.root):
        if ok:
            print(f"  ok  {page} loads its data in the right order")
        else:
            problems.append(f"{page}: {note}")

    for name, ok, note in emit.check_hostname(args.root):
        if ok:
            print(f"  ok  {name}: {note}")
        else:
            problems.append(f"{name}: {note}")

    if problems:
        print("\n[error] the committed site is not self-consistent:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        # Only the generated files are fixed by rebuilding. The pages, CNAME,
        # robots.txt and sitemap.xml are hand-maintained, and telling someone
        # to run a build that cannot touch them wastes their time.
        if any("is stale" in p or "signature" in p for p in problems):
            print("\nFor stale data: run `python build_profile_site.py` and commit "
                  "the result.", file=sys.stderr)
        if any("CNAME says" in p or "names no host" in p for p in problems):
            print("\nFor the hostname: candidate_profiles_site/CNAME is the source "
                  "of truth. Update the pages, robots.txt and sitemap.xml to match "
                  "it.", file=sys.stderr)
        return 1

    print("\n[ok] committed data is in sync with the sources.")
    return 0


def _statelegs(args):
    """Every state legislator from Open States, matched to the district maps."""
    from . import statelegs
    from .government_maps import STATES
    if args.check:
        cache = statelegs.load_cache(args.root)
        if not cache:
            print(f"[error] no {statelegs.CACHE_PATH}; run 'statelegs'", file=sys.stderr)
            return 2
        by_state = cache["states"]
    else:
        try:
            by_state = statelegs.fetch(STATES)
        except statelegs.StateLegislatorsError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
    unplaced_total = 0
    for code in STATES:
        topo = statelegs.load_map(code, args.root)
        if not topo:
            print(f"  [warn] {code}: no legislative_maps/{code.lower()}.json; run "
                  f"tools/fetch_legislative_maps.py")
            continue
        unplaced = statelegs.match(code, by_state[code], topo)
        unplaced_total += len(unplaced)
        if unplaced:
            reasons = sorted({why for _, why in unplaced})
            print(f"  {code}: {len(unplaced)} not placed on the map ({'; '.join(reasons)}): "
                  + ", ".join(sorted({r['district'] for r, _ in unplaced})[:6]))
    report = statelegs.seats_report(by_state)
    short = [f"{c} {ch} {n}/{s}" for c, v in report.items() for ch, (n, s) in v.items() if n < s]
    over = [f"{c} {ch} {n}/{s}" for c, v in report.items() for ch, (n, s) in v.items() if n > s]
    total = sum(len(v) for v in by_state.values())
    print(f"  {total:,} legislators in {len(by_state)} states; {unplaced_total} not placed")
    if short:
        print(f"  seats with nobody listed: {', '.join(short)}")
    if over:
        print(f"[error] more legislators than seats: {', '.join(over)}", file=sys.stderr)
        return 1
    if not args.check:
        path = statelegs.save_cache(by_state, args.root)
        print(f"[ok] wrote {path}")
    return 0


def _census(args):
    """The Census of Governments' counts of local governments, by state, for
    the guide's local map (kyc/census.py)."""
    from . import census
    if args.check:
        cache = census.load_cache(args.root)
        if not cache:
            print(f"[error] no {census.CACHE_PATH}; run 'census' to fetch it", file=sys.stderr)
            return 2
        print(f"  {census.CACHE_PATH}: {len(cache['states']) - 1} states and D.C., "
              f"{cache['national']['total']:,} local governments ({cache['year']})")
        return 0
    try:
        national, states = census.fetch()
    except census.CensusError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    path = census.save_cache(national, states, args.root)
    print(f"[ok] wrote {path}: {len(states) - 1} states and D.C., "
          f"{national['total']:,} local governments; every column adds up to the table's total")
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
    try:
        district_maps = districts_mod.build(args.root)
    except districts_mod.DistrictsError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    files = emit.write_districts(district_maps, args.root)
    print(f"[ok] wrote {len(files)} district maps under {emit.DISTRICTS_DIR} "
          f"({sum(size for _, size in files) / 1024:.0f} KB)")
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
    add("geo", help="regenerate the map geometry: the state atlas and every "
                    "state's district maps")
    add("verify", help="check the committed data still matches the sources")

    disc = add("disclosures", help="link members to their filed financial disclosures")
    disc.add_argument("--check", action="store_true",
                      help="use the committed cache; make no network call")

    res = add("results", help="resolve primary results: who is still in each race")
    res.add_argument("--check", action="store_true",
                     help="use the committed cache; make no network call")

    camp = add("campaigns", help="look up campaign websites from FEC committee filings")
    camp.add_argument("--check", action="store_true",
                      help="report coverage from the committed cache; no network")
    camp.add_argument("--limit", type=int, default=None,
                      help="look up at most N committees this run")
    camp.add_argument("--refresh", action="store_true",
                      help="look everyone up again, not just the uncached")

    odds = add("odds", help="market prices and polling averages for the 2026 races")
    odds.add_argument("--check", action="store_true",
                      help="report coverage from the committed cache; no network")

    rich = add("enrich", help="read candidates' Wikipedia infoboxes and campaign sites")
    rich.add_argument("--check", action="store_true",
                      help="report what the committed cache fills; no network")
    rich.add_argument("--limit", type=int, default=None,
                      help="read at most N people this run")
    rich.add_argument("--refresh", action="store_true",
                      help="read everyone again, not just those read over six days ago")

    field = add("field", help="refresh the FEC register of 2026 candidates")
    field.add_argument("--check", action="store_true",
                       help="use the committed cache; make no network call")

    congress = add("congress",
                   help="reconcile the rosters against the authoritative membership")
    congress.add_argument("--check", action="store_true",
                          help="use the committed snapshot; make no network call")
    congress.add_argument("--apply", action="store_true",
                          help="add newly seated members to the roster CSVs")

    legs = add("statelegs", help="every state legislator, from Open States")
    legs.add_argument("--check", action="store_true",
                      help="match the committed cache to the district maps; no network")

    census = add("census", help="count each state's local governments (Census of Governments)")
    census.add_argument("--check", action="store_true",
                        help="report the committed cache; make no network call")

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
    if args.command == "census":
        return _census(args)
    if args.command == "statelegs":
        return _statelegs(args)
    if args.command == "verify":
        return _verify(args)
    if args.command == "congress":
        return _congress(args)
    if args.command == "field":
        return _field(args)
    if args.command == "disclosures":
        return _disclosures(args)
    if args.command == "results":
        return _results(args)
    if args.command == "campaigns":
        return _campaigns(args)
    if args.command == "enrich":
        return _enrich(args)
    if args.command == "odds":
        return _odds(args)
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
