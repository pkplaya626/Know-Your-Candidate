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
    statewide as statewide_mod,
    summary as summary_mod,
    validate,
    voteview,
    voting as voting_mod,
    voting_dates as voting_dates_mod,
)
from .profiles import build_profiles, screen_field
from . import federal as federal_mod
from . import judiciary as judiciary_mod
from . import vacancies as vacancies_mod
from . import ballot_measures as measures_mod
from . import search_index as search_index_mod


def _load(args):
    """Read the rosters, or report why we cannot."""
    try:
        raw = sources.load_all(args.root)
    except sources.MissingRosterError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return None
    return raw


def _legislature_links(root):
    """Print what the legislature pages leave off or label otherwise
    (``legislature.link_report``): portraits that are a search engine's
    thumbnail - not yet reported to Open States - or that 'statelegs'
    confirmed missing, members with no page, a page on a party caucus's
    site only, and pages withheld because two members were given one."""
    from . import legislature as legislature_mod
    report = legislature_mod.link_report(root)
    for kind, why, warn in (
            ("thumbnail", "legislator portraits left off, image-search thumbnails", True),
            ("broken", "legislator portraits left off, confirmed missing", True),
            ("sharedPage", "legislator pages withheld, the same page given to two members", True),
            ("noPage", "legislators with no page to link, on the legislature's site or a caucus's "
                       "(legislature.LEGISLATURE_HOSTS, CAUCUS_SITES)", False),
            ("caucus", "legislators linked only to a party caucus's page "
                       "(legislature.CAUCUS_SITES)", False)):
        found = report.get(kind) or {}
        if found:
            print(f"  {'[warn] ' if warn else ''}{why}: {sum(found.values())} ("
                  + ", ".join(f"{code} {n}" for code, n in sorted(found.items())) + ")")


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
    field = screen_field(field, profiles, raw.get("record"))
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

    outcomes = results_mod.load_cache(args.root)
    stats["results"] = (results_mod.apply_cache(profiles, outcomes, field=field)
                        if outcomes else 0)
    if outcomes:
        print(f"  results: {stats['results']} candidates with a primary outcome "
              f"(as of {outcomes.get('asOf')})")
    else:
        print("  [warn] no primary results; run 'results'. Eliminated candidates "
              "will still show as running.")

    # After the results: a challenger's portrait comes only through the
    # article their ballot page links, and that link - and the name on the
    # ballot the portrait cache is keyed on - arrives with them (rule 24).
    # A link that leads somewhere else is withheld first, so it delivers no
    # portrait either (rule 33).
    enrichment = enrich.load_cache(args.root)
    withheld = enrich.withhold_links(profiles, enrichment)
    cache = portraits.load_cache(args.root)
    if cache:
        # A legislature's photograph stands while its roster seats them.
        stats["portraits"] = portraits.apply_cache(profiles, cache,
                                                   legislators=_legislators(args.root))
        print(f"  portraits: {stats['portraits']}/{len(profiles)} verified "
              f"({100 * stats['portraits'] / max(len(profiles), 1):.0f}%)")
    else:
        stats["portraits"] = 0
        print("  [warn] no portrait cache; run 'portraits' to resolve them")

    # After the results: who is still running, and the article and campaign
    # site their state's election page links, both arrive with them.
    if enrichment:
        filled = enrich.apply_cache(profiles, enrichment, as_of=_age_date(stats))
        if withheld:
            filled["wikipedia_withheld"] += withheld
        stats["enriched"] = dict(sorted(filled.items()))
        print("  enrich: " + ", ".join(f"{n} {k}" for k, n in sorted(filled.items()))
              + f" (read {enrichment.get('checked')})")
    else:
        print("  [warn] no enrichment cache; run 'enrich' to read candidates' "
              "articles and campaign sites")
    # The owner's decision of 2026-10-19: a photograph is shown only where
    # its source offers it within the caps; one offered only oversized is
    # left out, and said here.
    from . import nominee_photos, photos as photos_mod
    oversized = ((stats.get("enriched") or {}).get("portrait_oversized", 0)
                 + nominee_photos.left_out(profiles, cache or {}))
    stats["portraits_left_out"] = oversized
    print(f"  portraits left out, offered by their source only over "
          f"{photos_mod.MAX_PORTRAIT_BYTES // 1000} KB or {photos_mod.MAX_PORTRAIT_PX}px: "
          f"{oversized}")
    # Whose photograph each portrait is, once every source has had its say.
    from .photos import assign_credits
    stats["photo_credits"] = assign_credits(profiles)
    # The offices each person has held, by id; a challenger's only while
    # their profile links the article they were read from (rule 20).
    from . import history as history_mod
    lineage = history_mod.load_cache(args.root)
    if lineage:
        stats["history"] = history_mod.apply_cache(profiles, lineage, snapshot=snapshot)
        print(f"  history: public offices for {stats['history']} people (read {lineage['read']})")
    else:
        print("  [warn] no political history cache; run 'history'")
    # Members' education, careers and platform, each from a source tied to
    # them by id and badged; the roster's typed columns are never read (rule 86).
    from . import members as members_mod
    member_sources = members_mod.load_cache(args.root)
    filled = members_mod.apply_cache(profiles, member_sources)
    stats["member_sources"] = dict(sorted(filled.items()))
    if member_sources:
        print("  members: " + ", ".join(f"{n} {k}" for k, n in sorted(filled.items()))
              + f" (read {member_sources.get('read')})")

    race_list = races_mod.build(profiles, candidates.filing_counts(field),
                                results=outcomes, dates=results_mod.load_dates(args.root),
                                filed=candidates.filed_rows(field), record=raw.get("record"),
                                snapshot=snapshot)
    stats.update(races_mod.stats(race_list))
    counts, money_problems = _outside_and_seats(args.root, profiles, race_list,
                                                record=raw.get("record"), snapshot=snapshot)
    stats.update(counts)
    print(f"  outside spending: {counts['outside_spending']} profiles; last elections: "
          f"{counts['last_elections']} races")
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
                          district_error=district_error,
                          voting=voting_mod.load_cache(args.root) or {},
                          federal=federal_mod.load_cache(args.root),
                          judiciary=judiciary_mod.load_cache(args.root),
                          vacancies=vacancies_mod.load_cache(args.root),
                          history=lineage,
                          voting_dates=voting_dates_mod.load(args.root),
                          statewide=statewide_mod.load(args.root),
                          # {} when the cache is missing, so validate's
                          # error says so under --check too (PR #120 review).
                          measures=measures_mod.load(args.root) or {},
                          portraits=portraits.load_cache(args.root))
    from . import oge as oge_mod
    for level, code, message, detail in oge_mod.problems(oge_mod.load_cache(args.root),
                                                         federal_mod.load_cache(args.root)):
        issues.append(validate.Issue(level, code, message, detail))
    for level, code, message, detail in members_mod.problems(profiles, member_sources):
        issues.append(validate.Issue(level, code, message, detail))
    departed_rows, departed_problems = _departed(args.root, snapshot, profiles)
    for level, code, message, detail in departed_problems + money_problems:
        issues.append(validate.Issue(level, code, message, detail))
    # What the judges' Wikipedia and portrait join withheld (kyc/judge_links.py):
    # said by every build, not only by the refresh that found it.
    from . import judge_links as judge_links_mod
    for level, code, message, detail in judge_links_mod.problems(judge_links_mod.load_cache(args.root)):
        issues.append(validate.Issue(level, code, message, detail))
    # The roll calls (kyc/rollcalls.py): votes given to nobody, and why.
    from . import rollcalls
    roll_calls = rollcalls.load_cache(args.root)
    for level, code, message, detail in rollcalls.problems(roll_calls, snapshot):
        issues.append(validate.Issue(level, code, message, detail))
    # "Find who represents me" answers from lookup_maps/: a ZIP code there
    # naming a district the maps do not draw is an error (kyc/lookup.py).
    from . import lookup as lookup_mod
    try:
        lookup_mod.build(args.root, district_maps=district_maps)
    except lookup_mod.LookupMapError as exc:
        issues.append(validate.Issue("error", "lookup-map", str(exc), ""))
    # The people are written one state to a file (rule 94): someone whose
    # race or seat is filed under another state would be missing from it.
    for problem in emit.split_problems(profiles, race_list):
        issues.append(validate.Issue("error", "people-split", problem, ""))
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
            # What the legislature pages leave off, here too, where a
            # reviewer looks (PR #96 review).
            _legislature_links(args.root)
            print("\n[check] validation only, nothing written.")
        return 1 if errors else 0

    summary = summary_mod.build(profiles, races=race_list,
                                committees=legislators.load_committees(args.root),
                                results=outcomes, snapshot=snapshot, root=args.root)
    summary["voting"] = voting_mod.for_page(voting_mod.load_cache(args.root),
                                          voting_dates_mod.load(args.root))
    summary["departed"] = departed_rows
    from . import seat_history as seat_history_mod
    summary["lastElectionSources"] = seat_history_mod.page_sources()
    people_files = emit.write_people(profiles, stats, args.root, races=race_list, summary=summary)
    print(f"\n[ok] wrote {people_files[0][0]} and {len(people_files) - 1} people file(s) under "
          f"{emit.PEOPLE_DIR} ({sum(size for _, size in people_files) / 1024:.0f} KB)")

    # Each chamber's roll calls, before any page that names them is stamped.
    vote_files = emit.write_votes(rollcalls.payloads(roll_calls), args.root)
    for vote_path, vote_size in vote_files:
        print(f"[ok] wrote {vote_path} ({vote_size / 1024:.0f} KB)")

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
    dropped = {}
    try:
        legislatures = legislature_mod.build(args.root, dropped=dropped)
    except legislature_mod.LegislatureError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    written_legs = emit.write_legislature(legislatures, args.root)
    leg_stats = legislature_mod.stats(legislatures)
    print(f"[ok] state legislatures: {leg_stats['states']} states, {leg_stats['districts']:,} "
          f"districts, {leg_stats['placed']:,} members placed, {leg_stats['unplaced']} listed off "
          f"the map; {len(written_legs)} file(s) rewritten")
    _legislature_links(args.root)

    # Each state's counties and their local governments.
    from . import counties as counties_mod
    city_problems = []
    try:
        local_maps = counties_mod.build(args.root, problems=city_problems)
    except counties_mod.CountiesError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    for problem in city_problems:
        print(f"  [warn] {problem}")
    from . import localsites
    for problem in localsites.problems(localsites.load_cache(args.root),
                                       set(localsites.targets(args.root))):
        print(f"  [warn] {problem}")
    written_local = emit.write_local(local_maps, args.root)

    # Where a ZIP code or a location falls, for "Find who represents me":
    # one file per state, checked against the maps, the county pages and the
    # legislature pages it answers with; then the index that versions them.
    try:
        lookups = lookup_mod.build(args.root, local=local_maps, legislatures=legislatures,
                                   district_maps=district_maps)
    except lookup_mod.LookupMapError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    written_lookup = emit.write_lookup(lookups, args.root)
    # With the dates: a place whose record says it holds no election is
    # marked in the index (lookup.place_info, rule 92).
    emit.write_lookup_index(lookup_mod.index(lookups, emit.lookup_stamps(lookups, args.root),
                                             voting_mod.for_page(voting_mod.load_cache(args.root),
                                                                 voting_dates_mod.load(args.root))),
                            args.root)
    lookup_stats = lookup_mod.stats(lookups)
    print(f"[ok] lookup: {lookup_stats['lookup_zips']:,} ZIP areas in "
          f"{lookup_stats['lookup_states']} states and territories; "
          f"{len(written_lookup)} file(s) rewritten")
    local_stats = counties_mod.stats(local_maps)
    print(f"[ok] counties: {local_stats['counties']:,} counties, {local_stats['governments']:,} "
          f"governments and school systems placed, {local_stats['unmatched']} under county areas "
          f"not on the map; {local_stats['cities']:,} cities and towns, "
          f"{local_stats['cities_joined']:,} joined to their government; "
          f"{local_stats['towns']:,} town and township governments placed; "
          f"{len(written_local)} file(s) rewritten")

    # Who runs each state: governors and party control, checked against NCSL.
    from . import stategov
    try:
        state_gov, gov_problems = stategov.build(args.root)
    except stategov.StateGovError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    for problem in gov_problems:
        print(f"  [warn] {problem}")
    gov_file = os.path.join(args.root, emit.STATEGOV_FILE)
    if emit.read_signature(path=gov_file) != emit.stategov_signature(state_gov):
        gov_path, gov_size = emit.write_stategov(state_gov, args.root)
        print(f"[ok] wrote {gov_path} ({gov_size / 1024:.0f} KB)")
    gov_stats = stategov.stats(state_gov)
    print(f"[ok] state government: {gov_stats['governors']} governors; " + ", ".join(
        f"{n} {k}" for k, n in sorted(gov_stats["trifectas"].items())))
    listed = statewide_mod.stats(statewide_mod.load(args.root))
    print(f"[ok] statewide candidates: {listed['candidates']} on the ballot and "
          f"{listed['writeIns']} write-ins for {listed['offices']} offices; "
          f"{listed['certified']} list(s) whose own words certify them, "
          f"{listed['notState']} not the state's own")

    # The statewide questions (rule 95): a cache that breaks its rules is
    # validate's error above, and is never written to the page.
    measures_cache = measures_mod.load(args.root)
    if measures_cache and not measures_mod.problems(measures_cache):
        measures = measures_mod.for_page(measures_cache)
        measures_file = os.path.join(args.root, emit.MEASURES_FILE)
        if emit.read_signature(path=measures_file) != emit.measures_signature(measures):
            m_path, m_size = emit.write_measures(measures, args.root)
            print(f"[ok] wrote {m_path} ({m_size / 1024:.0f} KB)")
        m_stats = measures_mod.stats(measures_cache)
        print(f"[ok] ballot measures: {m_stats['measures']} in {m_stats['with']} jurisdictions "
              f"(and {m_stats['local']} on every ballot, decided locally); "
              f"{m_stats['none']} with none; {m_stats['unknown']} with no official list found")
    else:
        print(f"[error] {measures_mod.CACHE_PATH} is missing or breaks its rules; "
              f"{emit.MEASURES_FILE} not written", file=sys.stderr)
        return 2

    # The federal executive and courts (kyc/federal_build.py): one file for
    # the hub, one per court, each rewritten only when what it says changed.
    # What is wrong with either cache is validate's to report.
    from . import federal_build
    try:
        fed_payload, fed_courts, fed_search, fed_problems = federal_build.build(args.root)
    except federal_build.FederalBuildError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    # What the pages leave out and why (an office in the line of succession
    # nobody can be named for): said here as well as by validate.
    for problem in fed_problems:
        print(f"  [warn] federal pages: {problem}")
    fed_written = emit.write_federal(fed_payload, fed_courts, fed_search, args.root)
    from . import court_districts
    county_courts = court_districts.county_courts(args.root)
    if emit.read_signature(path=os.path.join(args.root, emit.COURT_COUNTIES_FILE)) != \
            emit.federal_signature(county_courts):
        fed_written.append(emit.write_court_counties(county_courts, args.root))
    print(f"[ok] federal government: {len(fed_payload['offices'])} Cabinet offices, "
          f"{fed_payload['judges']:,} judges on {len(fed_courts)} courts; "
          f"{len(fed_written)} file(s) rewritten")

    # The guide's maps: rewritten only when what they say changed.
    from . import government_maps
    guide_maps = government_maps.payload()
    guide_file = os.path.join(args.root, emit.GOVERNMENT_FILE)
    if emit.read_signature(path=guide_file) != emit.government_signature(guide_maps):
        guide_path, guide_size = emit.write_government(guide_maps, args.root)
        print(f"[ok] wrote {guide_path} ({guide_size / 1024:.0f} KB)")

    # The home search's places and bodies (rule 97): rewritten only when
    # what it says changed. One that would answer wrongly is not written.
    search_payload = _search_index(args.root, local_maps, profiles, summary)
    search_wrong = search_index_mod.problems(search_payload)
    if search_wrong:
        print(f"[error] search index: {'; '.join(search_wrong[:5])}; "
              f"{emit.SEARCH_FILE} not written", file=sys.stderr)
        return 2
    search_file = os.path.join(args.root, emit.SEARCH_FILE)
    if emit.read_signature(path=search_file) != emit.search_signature(search_payload):
        s_path, s_size = emit.write_search(search_payload, args.root)
        print(f"[ok] wrote {s_path} ({s_size / 1024:.0f} KB)")

    # The sitemap and the share pages (rule 96) are written with the rest.
    written = emit.write_state_pages(profiles, args.root, summary=summary, races=race_list)
    maps = [w for w in written
            if os.path.normpath(emit.DISTRICT_PAGES_DIR) in os.path.normpath(w)]
    states = [w for w in written if os.path.normpath(emit.STATES_DIR) in os.path.normpath(w)]
    share_dirs = {os.path.normpath(os.path.join(args.root, d)) for d in emit.SHARE_DIRS}
    shared = [w for w in written if os.path.normpath(os.path.dirname(w)) in share_dirs]
    print(f"[ok] wrote {len(states)} state pages under {emit.STATES_DIR}, "
          f"{len(maps)} district pages under {emit.DISTRICT_PAGES_DIR} and "
          f"{len(shared)} changed share page(s) of {len(profiles) + len(race_list)}")
    from . import assets
    restamped = assets.stamp_templates(args.root)
    if restamped:
        print(f"[ok] restamped the asset versions in {', '.join(restamped)}")

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


def _legislators(root):
    """The state legislators' roster (``statelegs``), or ``None``."""
    from . import statelegs
    return statelegs.load_cache(root) or None


def _portraits(args):
    raw = _load(args)
    if raw is None:
        return 2
    # The whole field, with results applied: a filed candidate is only
    # resolvable through the article their state's ballot page links to,
    # and that title arrives with the primary results.
    finance = fec.load_cache(args.root)
    field = candidates.load_cache(args.root)
    profiles, _ = build_profiles(raw, snapshot=legislators.load_snapshot(args.root),
                                 field=field, finance=finance)
    fec.apply_cache(profiles, finance)
    results_mod.apply_cache(profiles, results_mod.load_cache(args.root),
                            field=screen_field(field, profiles, raw.get("record")))
    # A ballot link that leads somewhere else is not resolved (rule 33).
    enrich.withhold_links(profiles, enrich.load_cache(args.root))
    cache, _summary = portraits.resolve_all(
        profiles, root=args.root, refresh=args.refresh
    )
    # Two more routes for the people on the ballot with none: Wikidata by
    # their own FEC id, and their state legislature's page for a sitting
    # member of it (kyc/nominee_photos.py). A source that cannot be read
    # keeps what it gave before and stops nothing (rule 8).
    from . import history as history_mod
    from . import nominee_photos
    try:
        nominee_photos.resolve_all(profiles, cache, history=history_mod.load_cache(args.root),
                                   legislators=_legislators(args.root))
        portraits.save_cache(cache, args.root)
    except Exception as exc:                     # never the refresh's end
        print(f"  [warn] nominee portraits stopped: {exc}; the cache is as it was")
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
    results_mod.apply_cache(profiles, results_mod.load_cache(args.root),
                            field=screen_field(field, profiles, raw.get("record")))
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


def _outside_and_seats(root, profiles, race_list, record=None, snapshot=None):
    """Outside spending on the profiles (kyc/outside.py) and each seat's
    last election on the races (kyc/seat_history.py), from their caches;
    the counts and what a build says about them. The record and the
    snapshot say who has held a seat since its last counted election."""
    from . import outside, seat_history
    spending = outside.load_cache(root)
    applied, refused = outside.apply(profiles, spending) if spending else (0, [])
    history = seat_history.load_cache(root)
    shown = seat_history.apply(race_list, history, record=record, snapshot=snapshot)
    problems = outside.problems(spending, refused) + seat_history.problems(history, race_list)
    return {"outside_spending": applied, "last_elections": shown}, problems


def _search_index(root, local_maps, profiles, summary):
    """The home search's places and bodies (kyc/search_index.py, rule 97):
    the county maps' names, the committee table the Congress guide shows,
    and the tribal governments the guide's map lists."""
    from . import tribes
    return search_index_mod.build(local_maps, profiles, (summary or {}).get("committees"),
                                  tribes.load_cache(root))


def _departed(root, snapshot, profiles):
    """The members who left the sitting Congress, for the grid's search,
    and what is wrong with the list (kyc/departed.py)."""
    from . import departed as departed_mod

    return departed_mod.for_page(departed_mod.load_cache(root), snapshot, profiles)


def _age_date(stats):
    """The date the build computes every age at (``profiles.age_as_of``)."""
    import datetime

    return datetime.date.fromisoformat(stats["ageAsOf"])


def _history(args):
    """The public offices each person has held (kyc/history.py): Congress
    from congress-legislators, other offices from Wikidata where the
    person's own Wikipedia article agrees. A read that fails keeps the
    committed cache (rule 8)."""
    from . import federal, history

    if args.check:
        cache = history.load_cache(args.root)
        if not cache:
            print(f"[error] no {history.CACHE_PATH}; run 'history'", file=sys.stderr)
            return 2
    else:
        raw = _load(args)
        if raw is None:
            return 2
        field = candidates.load_cache(args.root)
        profiles, _stats = build_profiles(raw, snapshot=legislators.load_snapshot(args.root),
                                          field=field, finance=fec.load_cache(args.root))
        # The article each challenger's election page links (rule 33).
        results_mod.apply_cache(profiles, results_mod.load_cache(args.root),
                                field=screen_field(field, profiles, raw.get("record")))
        try:
            cache = history.fetch(profiles, executive=federal.load_cache(args.root))
        except history.HistoryError as exc:
            print(f"[error] {exc}; the committed cache is unchanged", file=sys.stderr)
            return 2
        lacking = history.short(cache, history.load_cache(args.root))
        if lacking:
            print(f"[error] the read came back short ({lacking}); the committed cache is "
                  "unchanged", file=sys.stderr)
            return 2
    people = cache["people"]
    offices = sum(len(p["offices"]) for p in people.values())
    congress = sum(1 for p in people.values() if p["congress"])
    print(f"  {len(people)} people: {congress} with service in Congress, {offices} other offices "
          f"shown, {sum(len(p['withheld']) for p in people.values())} withheld (as read "
          f"{cache['read']})")
    for level, code, message, detail in history.problems(cache):
        print(f"  [{level}] {code}: {message}")
        for line in detail[:10]:
            print(f"           - {line}")
    if not args.check:
        print(f"[ok] wrote {history.save_cache(cache, args.root)}")
    return 0


def _members(args):
    """Members' platforms, education, careers, contact pages and district
    offices, each from a source tied to the member by id (kyc/members.py).
    A read that fails keeps the last one (rule 8)."""
    from . import federal, members

    raw = _load(args)
    if raw is None:
        return 2
    from .cycle import snapshot_congress

    snapshot = legislators.load_snapshot(args.root)
    profiles, _stats = build_profiles(raw, snapshot=snapshot,
                                      committees=legislators.load_committees(args.root))
    if args.check:
        cache = members.load_cache(args.root)
        if not cache:
            print(f"[error] no {members.CACHE_PATH}; run 'members'", file=sys.stderr)
            return 2
    else:
        ids = set(args.id) if args.id else None
        if args.all:
            # Every site again, however recent its last read: after a change
            # to the reader, so no member is read by the old rules.
            ids = {p["id"] for p in profiles if members.is_member(p)}
        cache = members.refresh(profiles, root=args.root, executive=federal.load_cache(args.root),
                                limit=args.limit, sites=not args.no_sites, ids=ids,
                                congress=snapshot_congress(snapshot) if snapshot else None,
                                key=fec.api_key(args.root))
        print(f"[ok] wrote {members.CACHE_PATH}")
    counts = members.apply_cache(profiles, cache)
    print("  members: " + ", ".join(f"{n} {k}" for k, n in sorted(counts.items())))
    for level, code, message, detail in members.problems(profiles, cache):
        print(f"  [{level}] {code}: {message}")
        for line in (detail if args.verbose else detail[:10]):
            print(f"           - {line}")
    return 0


def _seats(args):
    """Each seat's last election (kyc/seat_history.py): the Clerk of the
    House's official statistics, checked against a second compilation. A
    read that fails keeps the committed cache (rule 8)."""
    from . import seat_history

    if args.check:
        cache = seat_history.load_cache(args.root)
        if not cache:
            print(f"[error] no {seat_history.CACHE_PATH}; run 'seats'", file=sys.stderr)
            return 2
    else:
        raw = _load(args)
        if raw is None:
            return 2
        record = raw.get("record") or {}
        try:
            races = record.get("races") or {}
            cache = seat_history.build(list(races.values()) if isinstance(races, dict) else races)
        except (seat_history.ClerkFormatError, OSError, portraits.PortraitError) as exc:
            print(f"[error] {exc}; the committed cache is unchanged", file=sys.stderr)
            return 2
    print(f"  {len(cache['house'])} House results and {len(cache['senate'])} Senate results "
          f"shown, {len(cache['withheld'])} withheld (read {cache['read']})")
    for item in cache["withheld"]:
        print(f"    withheld {item['seat']} {item['year']}: {item['why']}"
              + (f" ({item['page']})" if item.get("page") else ""))
    if not args.check:
        print(f"[ok] wrote {seat_history.save_cache(cache, args.root)}")
    return 0


def _outside(args):
    """Independent expenditures for and against each candidate
    (kyc/outside.py), by FEC candidate id at the key's pace (rule 37). A
    read that fails keeps the committed cache (rule 8)."""
    from . import outside

    raw = _load(args)
    if raw is None:
        return 2
    field = candidates.load_cache(args.root)
    finance = fec.load_cache(args.root)
    profiles, _stats = build_profiles(raw, snapshot=legislators.load_snapshot(args.root),
                                      field=field, finance=finance)
    fec.apply_cache(profiles, finance)
    if args.check:
        cache = outside.load_cache(args.root)
        if not cache:
            print(f"[error] no {outside.CACHE_PATH}; run 'outside'", file=sys.stderr)
            return 2
    else:
        ids = [i for p in profiles for i in outside.profile_ids(p)]
        try:
            cache = outside.fetch(ids)
        except (outside.OutsideError, fec.FecError) as exc:
            print(f"[error] {exc}; the committed cache is unchanged", file=sys.stderr)
            return 2
    applied, refused = outside.apply(profiles, cache)
    print(f"  {len(cache['candidates'])} of {cache['asked']} candidate ids with independent "
          f"expenditures; {applied} profiles show them (read {cache['read']})")
    for level, code, message, detail in outside.problems(cache, refused):
        print(f"  [{level}] {code}: {message}" + (f" ({detail[:5]})" if detail else ""))
    if not args.check:
        print(f"[ok] wrote {outside.save_cache(cache, args.root)}")
    return 0


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
    # Who is still running, and the article and site the election page links.
    results_mod.apply_cache(profiles, results_mod.load_cache(args.root),
                            field=screen_field(field, profiles, raw.get("record")))
    if args.check:
        cache = enrich.load_cache(args.root)
        if not cache:
            print(f"[error] no {enrich.CACHE_PATH}; run 'enrich' first.", file=sys.stderr)
            return 2
        # As in build: a withheld link delivers no portrait (rule 33), and a
        # campaign-site portrait is taken only where none came by id or link.
        withheld = enrich.withhold_links(profiles, cache)
        portraits.apply_cache(profiles, portraits.load_cache(args.root),
                              legislators=_legislators(args.root))
        filled = enrich.apply_cache(profiles, cache, as_of=_age_date(stats))
        if withheld:
            filled["wikipedia_withheld"] += withheld
        print("  enrich: " + ", ".join(f"{n} {k}" for k, n in sorted(filled.items())))
    else:
        cache, _counts = enrich.resolve_all(profiles, root=args.root, refresh=args.refresh,
                                            limit=args.limit,
                                            only_unreachable=args.unreachable)
        # The sites whose portrait only a browser draws, for the people with
        # none by any other route (enrich.render_portraits). No Chrome, or a
        # page it cannot read, keeps the last drawn read and stops nothing.
        if args.render:
            enrich.withhold_links(profiles, cache)
            portraits.apply_cache(profiles, portraits.load_cache(args.root),
                                  legislators=_legislators(args.root))
            try:
                if enrich.render_portraits(profiles, cache, root=args.root, limit=args.render):
                    enrich.save_cache(cache, args.root)
            except Exception as exc:                 # never the refresh's end
                print(f"  [warn] drawn campaign pages stopped: {exc}")
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
    results_mod.apply_cache(profiles, outcomes, field=screen_field(field, profiles, raw.get("record")))
    screened = screen_field(field, profiles, raw.get("record"))
    race_list = races_mod.build(profiles, candidates.filing_counts(screened),
                                results=outcomes, dates=results_mod.load_dates(args.root),
                                filed=candidates.filed_rows(screened), record=raw.get("record"),
                                snapshot=legislators.load_snapshot(args.root))
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
    if not args.field_only:
        _cache, stats = fec.resolve_all(profiles, root=args.root, limit=args.limit,
                                        refresh=args.refresh, snapshot=snapshot,
                                        active_ids=active, record=raw.get("record"))
        if stats.get("stopped"):
            # A stop keeps every figure already cached, dated as it was read,
            # and the next run resumes. It is not fatal: the daily refresh
            # runs the field and the results after this step, and a 429 here
            # must not keep a day's results off the site.
            print("  [warn] finance stopped early; cached figures kept, "
                  "the next run resumes")
            return 0
    # Then every challenger still on a ballot, by their own filing's id: who
    # that is comes from the results, as on the page.
    finance = fec.load_cache(args.root)
    profiles, _ = build_profiles(raw, snapshot=snapshot, field=field, finance=finance)
    fec.apply_cache(profiles, finance)
    results_mod.apply_cache(profiles, results_mod.load_cache(args.root),
                            field=screen_field(field, profiles, raw.get("record")))
    _cache, stats = fec.resolve_field([p for p in profiles if enrich.running(p)],
                                      root=args.root, refresh=args.refresh, limit=args.limit)
    if stats.get("stopped"):
        print("  [warn] challengers' totals stopped early; cached figures kept, "
              "the next run resumes")
    print(f"\n[ok] finance cache: {fec.CACHE_PATH}")
    return 0


def _congress(args):
    """Reconcile the roster CSVs against the authoritative membership."""
    raw = _load(args)
    if raw is None:
        return 2
    # The membership as committed, before this run writes a new one: who
    # leaves is still in it, with the term a 2026 winner was seated for.
    previous = legislators.load_snapshot(args.root)

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
    elif args.snapshot:
        try:
            with open(args.snapshot, "r", encoding="utf-8") as handle:
                snapshot = json.load(handle)
        except (OSError, ValueError) as exc:
            print(f"[error] could not read {args.snapshot}: {exc}", file=sys.stderr)
            return 2
        if not snapshot.get("legislators"):
            print(f"[error] {args.snapshot} lists no legislators", file=sys.stderr)
            return 2
        path = legislators.save_snapshot(snapshot, args.root)
        print(f"  wrote {path} from {args.snapshot} ({len(snapshot['legislators'])} "
              f"legislators, read {snapshot.get('fetched', '?')})")
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

    # Whoever has left: by id, from legislators-historical, downloaded only
    # when somebody has. A failed download decides nothing (rule 8): nobody is
    # archived, those people stay "departed", and the build says so.
    absent = legislators.roster_ids(raw["members"]) - set(legislators.by_bioguide(snapshot))
    historical = None
    if absent and args.historical:
        try:
            with open(args.historical, "r", encoding="utf-8") as handle:
                historical = json.load(handle)
        except (OSError, ValueError) as exc:
            print(f"  [warn] could not read {args.historical}: {exc}")
    elif absent and not args.check and not args.snapshot:
        try:
            historical = legislators.fetch(legislators.HISTORICAL_URL)
            print(f"  legislators-historical: {len(historical)} people")
        except legislators.LegislatorsError as exc:
            print(f"  [warn] {exc}; nobody is archived this run")
    ended = legislators.departures(absent, snapshot, historical=historical)

    # Everyone who has left the sitting Congress, for the grid's search
    # (kyc/departed.py, GRID-08): from the same historical file, read when
    # the membership was. A failed download keeps the last list (rule 8).
    if not args.check and not args.snapshot:
        from . import departed as departed_mod
        if historical is None and not args.historical:
            try:
                historical = legislators.fetch(legislators.HISTORICAL_URL)
            except legislators.LegislatorsError as exc:
                print(f"  [warn] {exc}; the list of departed members is kept as it was")
        if historical is not None:
            data = departed_mod.build(historical, snapshot)
            path = departed_mod.save_cache(data, args.root)
            from .cycle import ordinal
            print(f"  wrote {path} ({len(data['members'])} who left the "
                  f"{ordinal(data['congress'])} Congress)")

    drift = legislators.reconcile(raw["members"], snapshot, ended=ended)
    print(f"\n  reconciliation: {drift.summary()}")
    for person in legislators.winners_leaving(drift, previous, raw.get("record")):
        print(f"    - {person['name']} won {person['raceId']} and has left: the archive keeps "
              f"the race and their FEC ids ({', '.join(person['fec']) or 'none listed'})")

    for person in drift.missing:
        seat = (
            f"{person['state']}-{person['district']}"
            if person["chamber"] == "House" else person["state"]
        )
        print(f"    + serving but not in the roster: {person['name']} "
              f"({person['chamber']} {seat}, {person['party']}, "
              f"since {person['termStart']})")

    for person in drift.expected:
        print(f"    - left office {person['left']} ({person['via']}): {person['name']} "
              f"({person['bioguide']})")

    for person in drift.departed:
        print(f"    - in the roster, no longer serving, and no record of leaving: "
              f"{person['name']} ({person['bioguide']})")

    # Every re-elected member begins a new term on January 3: one line for
    # those whose seat is unchanged, one each for a new seat.
    renewed = [s for s in drift.reseated if not s["moved"]]
    if renewed:
        print(f"    ~ {len(renewed)} member{'s' if len(renewed) != 1 else ''} began a new "
              f"term in the same seat")
    for seat in drift.reseated:
        if seat["moved"]:
            moved = ", ".join(f"{c['field']} {c['roster']!r} -> {c['authoritative']!r}"
                              for c in seat["moved"])
            print(f"    ~ a new term in a new seat: {seat['name']} ({moved})")

    for name in drift.twice:
        print(f"    ! on more than one roster row: {name}")

    shown = drift.changed if args.verbose else drift.changed[:10]
    for change in shown:
        print(f"    ~ {change['name']}: {change['field']} "
              f"roster={change['roster']!r} authoritative={change['authoritative']!r}")
    if len(shown) < len(drift.changed):
        print(f"    ... {len(drift.changed) - len(shown)} more (--verbose)")

    # The frozen race record against today's seats (kyc/record.py).
    from . import record as record_mod
    record = raw.get("record")
    if record:
        # Today's seats, from the sitting members and the snapshot's terms.
        sitting, _ = build_profiles(dict(raw, record=None), snapshot=snapshot)
        live = record_mod.live_races(sitting, snapshot)
        apart = record_mod.drift(record, live, snapshot)
        if apart:
            print(f"\n  [warn] {len(apart)} races differ between the 2026 record and "
                  f"today's seats:")
            for line in apart:
                print(f"    {line}")
        else:
            print(f"\n  ok  the 2026 record's {len(record['races'])} races agree with "
                  f"today's seats")

    if args.apply:
        report = legislators.apply(drift, args.root)
        for roster, names in sorted(report["added"].items()):
            print(f"\n[ok] added {len(names)} row(s) to {roster}:")
            for name in names:
                print(f"       {name}")
        for roster, names in sorted(report["reseated"].items()):
            print(f"\n[ok] renewed the term of {len(names)} row(s) in {roster}")
        if report["archived"]:
            print(f"\n[ok] moved {len(report['archived'])} row(s) to "
                  f"{legislators.FORMER_ROSTER}:")
            for name in report["archived"]:
                print(f"       {name}")
        if not any(report.values()):
            print("\n[ok] nothing to write.")
        else:
            print("\nOnly the fields the dataset actually knows were written. "
                  "Run `python build_profile_site.py` to regenerate the site.")
        if drift.departed:
            print(f"\n[error] {len(drift.departed)} roster member(s) are absent from "
                  "the membership, and legislators-historical (if it could be read) does "
                  "not say they left. They stay in the roster, and the build fails, "
                  "until somebody looks.")
        return 0

    if not drift.clean:
        print("\n[warn] the roster has drifted. Run `congress --apply` to write it in, "
              "or `--verbose` to see every difference.")
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
    cache = screen_field(cache, profiles, raw.get("record"))
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

    from .record import seated as sits

    members = [p for p in profiles if sits(p)]
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
        field = screen_field(field, profiles, raw.get("record"))
        print(f"  field: {field['count']} filings for races on the 2026 ballot "
              f"({len(field['screened']['stale'])} stale and "
              f"{len(field['screened']['phantom'])} for absent races set aside)")
        fec.apply_cache(profiles, fec.load_cache(args.root))
        filed = {row["candidate_id"]: row for row in field["candidates"]}
        known = {person["bioguide"]: person
                 for person in (snapshot or {}).get("legislators", [])}
        # A record incumbent who has left is no longer in the snapshot; the
        # record holds their official name and article title.
        for inc in ((raw.get("record") or {}).get("incumbents") or {}).values():
            if inc and inc["bioguide"] not in known:
                known[inc["bioguide"]] = inc
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
        # Louisiana's House ballot before its November open primary. A failed
        # read leaves those races pending, as they were; it is never read as
        # nobody having qualified (rule 8).
        from . import qualified as qualified_mod
        try:
            listed = qualified_mod.fetch()
            print(f"  qualified: {sum(len(v) for v in listed[0].values())} candidates for "
                  f"{len(listed[0])} Louisiana House seats ({qualified_mod.SOURCE})")
        except Exception as exc:          # inconclusive: say so, conclude nothing
            print(f"  [warn] Louisiana's qualified list could not be read: {exc}")
            listed = None
        previous = results_mod.load_cache(args.root)
        # Each state's certified November ballot, where one is published
        # (rule 77). A state whose list cannot be read keeps the last one
        # read; it is never read as nobody being certified (rule 8).
        from . import certified as certified_mod
        print("Reading the states' certified November ballots ...")
        ballots, unread = certified_mod.fetch(log=print)
        for state in certified_mod.carry(ballots, unread, previous):
            print(f"  [warn] kept {state}'s certified list read on "
                  f"{ballots[state].get('fetched')}")
        print("Reading primary results from Wikipedia ...")
        cache = results_mod.build(field, dates, today=datetime.date.today(), log=print,
                                  aliases=aliases, qualified=listed, certified=ballots)
        kept = results_mod.carry_qualified(cache, previous)
        if kept:
            print(f"  [warn] kept the qualified list read on "
                  f"{cache['qualified'].get('fetched')} for {len(kept)} seats")
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


def _record(args):
    """Freeze the cycle's race record, or report the one on disk."""
    from . import cycle as cycle_mod, record as record_mod

    raw = _load(args)
    if raw is None:
        return 2
    snapshot = legislators.load_snapshot(args.root)
    if not args.freeze:
        record = raw.get("record")
        if not record:
            print("  no record; run: python build_profile_site.py record --freeze")
            return 1
        print(f"  the {record['cycle']} record: {len(record['races'])} races, frozen from the "
              f"{cycle_mod.ordinal(record['sittingCongress'])} Congress "
              f"(snapshot {record['frozenFrom'].get('snapshotFetched')}); signature "
              f"{cycle_mod.record_signature(record)}")
        return 0
    raw = dict(raw, record=None)          # frozen from the live seats, never itself
    profiles, _ = build_profiles(raw, snapshot=snapshot)
    try:
        record = record_mod.freeze(profiles, snapshot)
        path = record_mod.save(record, args.root, force=args.force)
    except record_mod.RecordError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    senate = sum(1 for r in record["races"].values() if r["chamber"] == "Senate")
    print(f"  wrote {path}: {len(record['races'])} races ({senate} Senate)")
    print(f"  signature, to pin in cycle.RECORD_SIGNATURES[{record['cycle']}]:")
    print(f"    {cycle_mod.record_signature(record)}")
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
    filings = disclosures.load_cache(args.root)
    stats["disclosures"] = disclosures.apply_cache(profiles, filings) if filings else 0
    stats["campaign_sites"] = campaigns.apply_cache(profiles, campaigns.load_cache(args.root))

    field = screen_field(candidates.load_cache(args.root), profiles, raw.get("record"))
    outcomes = results_mod.load_cache(args.root)
    stats["results"] = (results_mod.apply_cache(profiles, outcomes, field=field)
                        if outcomes else 0)
    enrichment = enrich.load_cache(args.root)
    enrich.withhold_links(profiles, enrichment)
    cache = portraits.load_cache(args.root)
    stats["portraits"] = (portraits.apply_cache(profiles, cache,
                                                legislators=_legislators(args.root))
                          if cache else 0)
    enrich.apply_cache(profiles, enrichment, as_of=_age_date(stats))
    from .photos import assign_credits
    stats["photo_credits"] = assign_credits(profiles)
    from . import history as history_mod
    history_mod.apply_cache(profiles, history_mod.load_cache(args.root),
                            snapshot=legislators.load_snapshot(args.root))
    from . import members as members_mod
    members_mod.apply_cache(profiles, members_mod.load_cache(args.root))
    race_list = races_mod.build(
        profiles, candidates.filing_counts(field),
        results=outcomes, dates=results_mod.load_dates(args.root),
        filed=candidates.filed_rows(field), record=raw.get("record"),
        snapshot=legislators.load_snapshot(args.root),
    )
    stats.update(races_mod.stats(race_list))
    stats.update(_outside_and_seats(args.root, profiles, race_list, record=raw.get("record"),
                                    snapshot=legislators.load_snapshot(args.root))[0])
    summary = summary_mod.build(profiles, races=race_list,
                                committees=legislators.load_committees(args.root),
                                results=outcomes,
                                snapshot=legislators.load_snapshot(args.root),
                                root=args.root)
    summary["voting"] = voting_mod.for_page(voting_mod.load_cache(args.root),
                                          voting_dates_mod.load(args.root))
    summary["departed"] = _departed(args.root, legislators.load_snapshot(args.root), profiles)[0]
    from . import seat_history as seat_history_mod
    summary["lastElectionSources"] = seat_history_mod.page_sources()

    problems = []
    from . import cycle as cycle_mod
    record = raw.get("record")
    if record is None:
        problems.append(f"no {cycle_mod.record_path(args.root)}; run: "
                        f"python build_profile_site.py record --freeze")
    else:
        pinned = cycle_mod.RECORD_SIGNATURES.get(record.get("cycle"))
        found = cycle_mod.record_signature(record)
        if found != pinned:
            problems.append(f"the {record.get('cycle')} race record's races are {found[:16]}..., "
                            f"cycle.RECORD_SIGNATURES pins {str(pinned)[:16]}...: the set "
                            f"of races changed without a reviewed code change")
        else:
            print(f"  ok  the {record['cycle']} race record matches its pinned signature "
                  f"({found[:16]}...)")

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
    # Each state's people and the index of everyone, from the same build
    # (rule 94): a stale one would put another build beside this one.
    stale_people = emit.check_people(profiles, race_list, summary, args.root)
    if stale_people:
        problems.append(f"{len(stale_people)} people file(s) are not this build's: "
                        + "; ".join(f"{os.path.basename(p)} {why}" for p, why in stale_people[:6]))
    else:
        print(f"  ok  {emit.PEOPLE_DIR}: the index and every state's file are this build's")

    from . import rollcalls
    stale_votes = emit.check_votes(rollcalls.payloads(rollcalls.load_cache(args.root)), args.root)
    if stale_votes:
        problems.append(f"{len(stale_votes)} vote file(s) are {stale_votes[0][1]}: "
                        + ", ".join(os.path.basename(p) for p, _ in stale_votes))
    else:
        print(f"  ok  {emit.VOTES_DIR}: both chambers match {rollcalls.CACHE_PATH}")

    stale_pages = emit.check_state_pages(profiles, args.root, summary=summary, races=race_list)
    if stale_pages:
        problems.append(f"{len(stale_pages)} state page(s) are {stale_pages[0][1]}: "
                        + ", ".join(rel for rel, _ in stale_pages[:5])
                        + (" ..." if len(stale_pages) > 5 else ""))
    else:
        print(f"  ok  {emit.STATES_DIR} pages, the share pages and the sitemap match the template")

    odds_expected = emit.odds_signature(odds_mod.payload(odds_mod.load_cache(args.root)))
    odds_committed = emit.read_signature(path=os.path.join(args.root, emit.ODDS_FILE))
    if odds_committed is None:
        problems.append(f"{emit.ODDS_FILE} is missing or carries no signature")
    elif odds_committed != odds_expected:
        problems.append(f"{emit.ODDS_FILE} is stale")
    else:
        print(f"  ok  {emit.ODDS_FILE} matches odds.json ({odds_expected[:16]}...)")

    from . import legislature as legislature_mod
    legislatures = None
    try:
        legislatures = legislature_mod.build(args.root)
        stale_legs = emit.check_legislature(legislatures, args.root)
    except legislature_mod.LegislatureError as exc:
        problems.append(f"state legislatures unavailable: {exc}")
    else:
        if stale_legs:
            problems.append(f"{len(stale_legs)} legislature file(s) are {stale_legs[0][1]}: "
                            + ", ".join(os.path.basename(p) for p, _ in stale_legs[:5]))
        else:
            print(f"  ok  {emit.LEGISLATURE_DIR}: every state matches its maps and roster")

    from . import counties as counties_mod
    local_maps = None
    try:
        local_maps = counties_mod.build(args.root)
        stale_local = emit.check_local(local_maps, args.root)
    except counties_mod.CountiesError as exc:
        problems.append(f"county pages unavailable: {exc}")
    else:
        if stale_local:
            problems.append(f"{len(stale_local)} county file(s) are {stale_local[0][1]}: "
                            + ", ".join(os.path.basename(p) for p, _ in stale_local[:5]))
        else:
            print(f"  ok  {emit.LOCAL_DIR}: every state matches its counties and listing")

    # The home search's places and bodies (rule 97): the committed file is
    # what the maps, the rosters and the directory say now.
    if local_maps is not None:
        search_payload = _search_index(args.root, local_maps, profiles, summary)
        search_committed = emit.read_signature(path=os.path.join(args.root, emit.SEARCH_FILE))
        search_wrong = search_index_mod.problems(search_payload)
        if search_wrong:
            problems.append(f"search index: {search_wrong[0]}")
        elif search_committed is None:
            problems.append(f"{emit.SEARCH_FILE} is missing or carries no signature")
        elif search_committed != emit.search_signature(search_payload):
            problems.append(f"{emit.SEARCH_FILE} is stale")
        else:
            print(f"  ok  {emit.SEARCH_FILE} matches the county maps, the committee rosters and "
                  f"the tribal directory ({search_committed[:16]}...)")

    from . import stategov
    try:
        gov_expected = emit.stategov_signature(stategov.build(args.root)[0])
    except stategov.StateGovError as exc:
        gov_expected = None
        problems.append(str(exc))
    gov_committed = emit.read_signature(path=os.path.join(args.root, emit.STATEGOV_FILE))
    if gov_expected is None:
        pass
    elif gov_committed is None:
        problems.append(f"{emit.STATEGOV_FILE} is missing or carries no signature")
    elif gov_committed != gov_expected:
        problems.append(f"{emit.STATEGOV_FILE} is stale")
    else:
        print(f"  ok  {emit.STATEGOV_FILE} matches the governor, legislator and NCSL caches "
              f"({gov_expected[:16]}...)")

    # The statewide questions (rule 95): the page's file is the cache's.
    measures_cache = measures_mod.load(args.root)
    unfit = measures_mod.problems(measures_cache) if measures_cache else ["missing"]
    measures_committed = emit.read_signature(path=os.path.join(args.root, emit.MEASURES_FILE))
    if unfit:
        problems.append(f"{measures_mod.CACHE_PATH}: {len(unfit)} problem(s): {unfit[0]}")
    elif measures_committed is None:
        problems.append(f"{emit.MEASURES_FILE} is missing or carries no signature")
    elif measures_committed != emit.measures_signature(measures_mod.for_page(measures_cache)):
        problems.append(f"{emit.MEASURES_FILE} is stale")
    else:
        print(f"  ok  {emit.MEASURES_FILE} matches {measures_mod.CACHE_PATH} "
              f"({measures_committed[:16]}...)")

    from . import federal_build
    try:
        fed = federal_build.build(args.root)
    except federal_build.FederalBuildError as exc:
        fed = None
        problems.append(str(exc))
    if fed is not None:
        stale_fed = emit.check_federal(*fed[:3], root=args.root)
        if stale_fed:
            problems.append(f"{len(stale_fed)} federal file(s) are missing or stale: "
                            + ", ".join(os.path.basename(p) for p, _ in stale_fed[:5]))
        else:
            print(f"  ok  {emit.FEDERAL_FILE} and {len(fed[1])} court files match the "
                  f"executive and judiciary caches")
    from . import court_districts
    county_courts = emit.read_signature(path=os.path.join(args.root, emit.COURT_COUNTIES_FILE))
    if county_courts is None:
        problems.append(f"{emit.COURT_COUNTIES_FILE} is missing or carries no signature")
    elif county_courts != emit.federal_signature(court_districts.county_courts(args.root)):
        problems.append(f"{emit.COURT_COUNTIES_FILE} is stale")
    else:
        print(f"  ok  {emit.COURT_COUNTIES_FILE} matches 28 U.S.C. 81-131 as read")

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

        from . import lookup as lookup_mod
        try:
            lookups = lookup_mod.build(args.root, local=local_maps, legislatures=legislatures,
                                       district_maps=district_maps)
        except lookup_mod.LookupMapError as exc:
            problems.append(f"lookup files unavailable: {exc}")
        else:
            stale_lookup = emit.check_lookup(lookups, args.root)
            if stale_lookup:
                problems.append(f"{len(stale_lookup)} lookup file(s) are {stale_lookup[0][1]}: "
                                + ", ".join(os.path.basename(p) for p, _ in stale_lookup[:5]))
            else:
                print(f"  ok  {emit.LOOKUP_DIR}: {len(lookups)} states and the index match "
                      f"{lookup_mod.LOOKUP_DIR}")

    for page, ok, note in emit.check_pages(args.root):
        if ok:
            print(f"  ok  {page} loads its data in the right order")
        else:
            problems.append(f"{page}: {note}")
    from . import assets
    stale_stamps = assets.stamp_templates(args.root, write=False)
    if stale_stamps:
        problems.append(f"{', '.join(stale_stamps)}: a script or stylesheet changed and its "
                        f"version stamp did not; run the build (kyc/assets.py)")
    else:
        print(f"  ok  {', '.join(assets.TEMPLATES)} load their code at its current version")

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


def _local_sites(args):
    """Open every website the Census listing gives a local government and
    record what it is now (kyc/localsites.py)."""
    from . import localsites
    codes = [c.strip().upper() for c in (args.states or "").split(",") if c.strip()] or None
    recheck = tuple(v.strip() for v in (args.recheck or "").split(",") if v.strip())
    unknown = [v for v in recheck if v not in localsites.VERDICTS]
    if unknown:
        print(f"[error] --recheck: not a verdict: {', '.join(unknown)}", file=sys.stderr)
        return 2
    budget = args.max_minutes * 60 if args.max_minutes else None
    cache = localsites.check_all(args.root, codes=codes, workers=args.workers, limit=args.limit,
                                 refresh=args.refresh, recheck=recheck, max_seconds=budget)
    counts = localsites.summary(cache)
    total = sum(counts.values())
    print(f"[ok] {total:,} addresses in {localsites.CACHE_PATH}: " + ", ".join(
        f"{counts[v]:,} {v}" for v in localsites.VERDICTS if counts.get(v)))
    withdrawn = sum(counts.get(v, 0) for v in localsites.WITHDRAWN)
    print(f"     {withdrawn:,} withdrawn by the build; {counts.get(localsites.UNREAD, 0):,} could "
          f"not be read and stay linked, marked unchecked")
    return 0


def _localgov(args):
    """Every local government, county by county, checked against the
    published table before anything is written (kyc/localgov.py)."""
    from . import census, localgov
    if getattr(args, "check_sites", False):
        return _local_sites(args)
    table = census.load_cache(args.root)
    if not table:
        print(f"[error] no {census.CACHE_PATH}; run 'census' first", file=sys.stderr)
        return 2
    try:
        by_state = localgov.fetch()
    except localgov.LocalGovError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    problems = localgov.check_against_table(by_state, table)
    if problems:
        print("[error] the listing disagrees with the published table:", file=sys.stderr)
        for problem in problems[:20]:
            print(f"    {problem}", file=sys.stderr)
        return 1
    paths = localgov.save(by_state, args.root)
    total = sum(len(e["governments"]) for s in by_state.values() for e in s["counties"].values())
    print(f"[ok] wrote {len(paths)} files under {localgov.OUT_DIR}: {total:,} governments and "
          f"school systems in {sum(len(s['counties']) for s in by_state.values()):,} counties; "
          f"every count agrees with the published table")
    return 0


def _courts(args):
    """Every state's court of last resort and who sits on it, read from each
    court's own roster (kyc/courts.py)."""
    from . import courts
    from .government_maps import STATES
    if args.check:
        cache = courts.load_cache(args.root)
        if not cache:
            print(f"[error] no {courts.CACHE_PATH}; run 'courts'", file=sys.stderr)
            return 2
        read, problems = cache["courts"], []
    else:
        read, problems = courts.fetch(root=args.root)
        # A court that could not be read this time keeps its last good read
        # (rule 8): a timeout is not a court with no members.
        old = courts.load_cache(args.root) or {}
        before = old.get("courts", {})
        for code in sorted(set(courts.COURTS) - set(read)):
            if code in before:
                # With the day it was read, which this run's save does not
                # change: dated by the cache's "fetched", rewritten every
                # run, a court that never read again would never grow old.
                read[code] = dict(before[code], read=before[code].get("read")
                                  or str(old.get("fetched") or "")[:10])
                problems.append(f"{code}: kept the last good read, of {read[code]['read']}")
        problems.extend(courts.shrunk(before, read))
        problems.extend(courts.changed(before, read))
    for code, court in sorted(read.items()):
        short = court["seats"] - court["listed"]
        print(f"  {code}: {court['listed']} of {court['seats']}" + (f" ({short} with nobody listed)"
              if short else "") + (f"; chief {court['chief']}" if court["chief"] else "; no chief listed"))
    curated = courts.curated()
    unfit = courts.curated_errors()
    for problem in unfit:
        print(f"  [error] {problem}", file=sys.stderr)
    problems.extend(courts.curated_stale())
    problems.extend(courts.stale({"courts": read}))
    missing = [c for c in STATES if c not in read and c not in courts.UNREADABLE and c not in curated]
    for problem in problems:
        print(f"  [warn] {problem}")
    print(f"  {len(read)} courts read; {len(curated)} read by hand from the court's own page "
          f"({', '.join(sorted(curated))}); {len(courts.UNREADABLE)} cannot be read at all"
          + (f"; no recipe or no result for {', '.join(missing)}" if missing else ""))
    if not args.check:
        print(f"[ok] wrote {courts.save_cache(read, args.root)}")
    return 2 if unfit else 0


def _voting(args):
    """Each state's official voting pages, as NASS's "Can I Vote" lists them
    (kyc/voting.py): registration status, polling place, absentee and early
    voting, registering."""
    from . import voting
    if args.check:
        cache = voting.load_cache(args.root)
        if not cache:
            print(f"[error] no {voting.CACHE_PATH}; run 'voting'", file=sys.stderr)
            return 2
    else:
        try:
            cache = voting.fetch()
        except voting.VotingError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
        print(f"[ok] wrote {voting.save_cache(cache, args.root)}")
    states = cache.get("states") or {}
    print(f"  {len(states)} jurisdictions, {len(voting.PAGES)} official pages each "
          f"(source: {cache.get('source')})")
    links = cache.get("links") or {}
    if links:
        counts = {s: sum(1 for v in links.values() if v == s)
                  for s in (voting.LIVE, voting.UNKNOWN, voting.DEAD)}
        print(f"  opened {len(links)} links: {counts[voting.LIVE]} answered, "
              f"{counts[voting.UNKNOWN]} inconclusive (bot walls, timeouts), "
              f"{counts[voting.DEAD]} dead")
    for line in voting.dead_links(cache):
        print(f"  [dead] {line} - not shown; add an overrides.VOTING_LINKS entry")
    for line in voting.stale_overrides(cache):
        print(f"  [stale override] {line}")
    return 0


def _tribes(args):
    """Every tribal government and its leader, as the BIA's Tribal Leaders
    Directory lists them (kyc/tribes.py), for the guide's tribal map."""
    from . import tribes
    if args.check:
        cache = tribes.load_cache(args.root)
        if not cache:
            print(f"[error] no {tribes.CACHE_PATH}; run 'tribes'", file=sys.stderr)
            return 2
    else:
        try:
            cache = tribes.fetch()
        except tribes.TribesError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
        print(f"[ok] wrote {tribes.save_cache(cache, args.root)}")
    placed, _ = tribes.placed(cache)
    print(f"  {cache.get('count')} rows, edited {cache.get('edited')}: "
          f"{sum(len(v) for v in placed.values())} listed in {len(placed)} states "
          f"(source: {cache.get('source')})")
    for line in tribes.problems(cache):
        print(f"  [warn] {line}")
    return 0


def _officers(args):
    """Every lieutenant governor and secretary of state, from the NLGA's and
    NASS's own rosters, cross-checked where they overlap (kyc/officers.py)."""
    from . import officers
    from .government_maps import STATES
    if args.check:
        cache = officers.load_cache(args.root)
        if not cache:
            print(f"[error] no {officers.CACHE_PATH}; run 'officers'", file=sys.stderr)
            return 2
    else:
        try:
            cache = officers.fetch(previous=officers.load_cache(args.root))
        except officers.OfficersError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
    incomplete = False
    for office, rows in (("secretaries of state (NASS)", cache["sos"]),
                         ("lieutenant governors (NLGA)", cache["lt"])):
        missing = [c for c in STATES if c not in rows]
        print(f"  {len(rows)} {office}" + (f"; none listed for {', '.join(missing)}" if missing else ""))
        incomplete = incomplete or bool(missing)
    if incomplete and not args.check:
        print("[error] a roster is missing states; the cache is not written", file=sys.stderr)
        return 1
    for code, office, nass, nlga in officers.overlaps(cache["sos"], cache["lt"]):
        print(f"  [warn] {code}: NASS lists {nass} as {office}, NLGA {nlga}; neither is shown")
    ag = cache.get("ag", {})
    confirmed = sum(1 for row in ag.values() if row.get("name") and not row.get("unconfirmed"))
    print(f"  {confirmed} of {len(STATES)} attorneys general confirmed on their office's own page; "
          f"{sum(1 for row in ag.values() if row.get('photo'))} with their office's photograph")
    for problem in cache.pop("agProblems", officers.ag_problems(ag)):
        print(f"  [warn] {problem}")
    if not args.check:
        print(f"[ok] wrote {officers.save_cache(cache, args.root)}")
    return 0


def _oge(args):
    """Financial disclosures of the President, the Vice President and the
    Cabinet, from the Office of Government Ethics' index, attributed by
    office (kyc/oge.py). A read that fails keeps the committed cache
    (rule 8)."""
    from . import federal, oge

    executive = federal.load_cache(args.root)
    if executive is None:
        print(f"[error] no {federal.CACHE_PATH}; run 'federal'", file=sys.stderr)
        return 2
    previous = oge.load_cache(args.root)
    if args.check:
        cache = previous
        if not cache:
            print(f"[error] no {oge.CACHE_PATH}; run 'oge'", file=sys.stderr)
            return 2
    else:
        try:
            cache = oge.build(executive, previous=previous)
        except oge.OGEError as exc:
            print(f"[error] {exc}; the committed cache is unchanged", file=sys.stderr)
            return 2
    people = cache["people"]
    print(f"  {sum(1 for p in people.values() if p['filed'])} of {len(people)} officers in OGE's "
          f"index, {sum(1 for p in people.values() for d in p['documents'] if d['url'])} reports "
          f"linked (read {cache['read']})")
    failed = 0
    for level, code, message, detail in oge.problems(cache, executive):
        print(f"  [{level}] {code}: {message}")
        for line in detail[:10]:
            print(f"           - {line}")
        failed += level == "error"
    if not args.check:
        print(f"[ok] wrote {oge.save_cache(cache, args.root)}")
    return 1 if failed else 0


def _votes(args):
    """Every roll call of the Congress the 2026 record is about, from the
    House Clerk's and the Senate's own records, attributed to members by id
    (kyc/rollcalls.py). Resumable: what each run reads is saved as it goes,
    and a source that refuses or fails keeps what was read (rule 8)."""
    from . import rollcalls

    previous = rollcalls.load_cache(args.root)
    if args.check:
        cache = previous
        if not cache:
            print(f"[error] no {rollcalls.CACHE_PATH}; run 'votes'", file=sys.stderr)
            return 2
    else:
        chambers = (args.chamber,) if args.chamber else rollcalls.CHAMBERS
        failed = None
        try:
            cache = rollcalls.fetch(previous, chambers=chambers, limit=args.limit,
                                    pause=args.pause,
                                    save=lambda c: rollcalls.save_cache(c, args.root))
        except rollcalls.RollCallError as exc:
            failed = exc
            cache = rollcalls.load_cache(args.root)
            if not cache:
                print(f"[error] {exc}", file=sys.stderr)
                return 2
        if failed:
            print(f"  [warn] {failed}; what was read is saved, and the next run goes on "
                  "from there")
    for chamber in rollcalls.CHAMBERS:
        part = cache.get(chamber) or {}
        rolls = part.get("rolls") or []
        print(f"  {chamber}: {len(rolls)} roll calls"
              + (f", {rolls[0]['date']} to {rolls[-1]['date']}" if rolls else "")
              + f" (read {part.get('read') or 'never'})")
    for level, code, message, detail in rollcalls.problems(
            cache, legislators.load_snapshot(args.root)):
        print(f"  [{level}] {code}: {message}")
        for line in detail[:10]:
            print(f"           - {line}")
    if not args.check:
        print(f"[ok] wrote {rollcalls.CACHE_PATH}")
    return 0


def _vacancies(args):
    """Vacancies in the federal courts, as the courts list them on
    uscourts.gov: current, announced and emergencies (kyc/vacancies.py). A
    list that cannot be read, or whose rows do not add up to its own totals,
    keeps the committed cache (rule 8)."""
    from . import judiciary, vacancies

    if args.check:
        cache = vacancies.load_cache(args.root)
        if not cache:
            print(f"[error] no {vacancies.CACHE_PATH}; run 'vacancies'", file=sys.stderr)
            return 2
    else:
        try:
            cache = vacancies.fetch()
        except vacancies.VacanciesError as exc:
            print(f"[error] {exc}; the committed cache is unchanged", file=sys.stderr)
            return 2
    print(f"  {cache['totals']['vacancies']} vacancies, {cache['totals']['nominees']} with a "
          f"nominee pending, as of {cache['asOf']}; {len(cache['future'])} announced; "
          f"{sum(1 for r in cache['current'] if r.get('emergency'))} judicial emergencies")
    failed = 0
    for level, code, message, detail in vacancies.problems(
            cache, judiciary=judiciary.load_cache(args.root)):
        print(f"  [{level}] {code}: {message}")
        for line in detail[:10]:
            print(f"           - {line}")
        failed += level == "error"
    if not args.check:
        print(f"[ok] wrote {vacancies.save_cache(cache, args.root)}")
    return 1 if failed else 0


def _judiciary(args):
    """Every sitting Article III judge, from the Federal Judicial Center's
    directory, and the Supreme Court's members as the Court lists them
    (kyc/judiciary.py). A source that cannot be read, or reads short, keeps
    the committed cache (rule 8)."""
    from . import federal_courts, judiciary

    previous = judiciary.load_cache(args.root)
    links_only = getattr(args, "links_only", False)
    if args.check or links_only:
        cache = previous
        if not cache:
            print(f"[error] no {judiciary.CACHE_PATH}; run 'judiciary'", file=sys.stderr)
            return 2
    else:
        try:
            cache = judiciary.fetch(previous=previous)
        except judiciary.JudiciaryError as exc:
            print(f"[error] {exc}; the committed cache is unchanged", file=sys.stderr)
            return 2
        # The territorial courts' judges, from each court's own site
        # (kyc/territorial_courts.py); a page not read keeps the last roster.
        from . import territorial_courts
        cache["territorial"], trouble = territorial_courts.fetch((previous or {}).get("territorial"))
        for line in trouble:
            print(f"  [warn] territorial court: {line}; its last roster stands")
    # A retired justice is listed apart and never counted as sitting.
    judges = {k: j for k, j in cache["judges"].items() if not j.get("retiredJustice")}
    active = sum(1 for j in judges.values() if j["status"] == "active")
    print(f"  {len(judges)} sitting judges: {active} active, {len(judges) - active} senior "
          f"(directory as of {cache['asOf']})")
    scotus = cache["courts"]["scotus"]
    print("  Supreme Court: " + "; ".join(judges[i]["name"] for i in scotus["judges"]))
    if scotus.get("retired"):
        print("  retired justices, not members: "
              + "; ".join(cache["judges"][i]["name"] for i in scotus["retired"]))
    for kind in ("appeals", "trade", "district", "territorial"):
        ids = [c for c, court in federal_courts.COURTS.items() if court["kind"] == kind]
        listed = [c for c in ids if cache["courts"][c]["listed"]]
        print(f"  {federal_courts.KINDS[kind]}: {len(ids)} courts, "
              f"{sum(cache['courts'][c]['active'] for c in ids)} active and "
              f"{sum(cache['courts'][c]['senior'] for c in ids)} senior judges"
              + ("" if len(listed) == len(ids) else
                 f"; {len(ids) - len(listed)} not in the FJC's directory of Article III judges"))
    failed = 0
    for level, code, message, detail in judiciary.problems(cache):
        print(f"  [{level}] {code}: {message}")
        for line in detail[:10]:
            print(f"           - {line}")
        failed += level == "error"
    if not args.check:
        if not links_only:
            print(f"[ok] wrote {judiciary.save_cache(cache, args.root)}")
        # Each judge's Wikipedia article and portrait, joined through the
        # FJC id on Wikidata (kyc/judge_links.py). A failure keeps the last
        # links and does not fail the refresh (rule 8).
        from . import judge_links
        try:
            links = judge_links.refresh(cache, args.root)
        except judge_links.JudgeLinksError as exc:
            print(f"  [warn] judge links: {exc}; the committed links are unchanged")
        else:
            print(f"  judge links: {len(links['judges'])} judges on Wikidata, "
                  f"{sum(1 for j in links['judges'].values() if j.get('portrait'))} portraits, "
                  f"{len(links['problems'])} withheld, {len(links.get('oversized') or [])} "
                  f"offered only over the size caps; {links['unread']} FJC pages to read again")
            for line in links["problems"][:10]:
                print(f"           - {line}")
            print(f"[ok] wrote {judge_links.CACHE_PATH}")
    return 1 if failed else 0


def _federal(args):
    """The federal executive (kyc/federal.py): who holds each office, from the
    White House's pages, each office's own page and the Senate's roll calls.
    A source that cannot be read keeps the last good cache (rule 8)."""
    from . import federal

    previous = federal.load_cache(args.root)
    if args.check:
        cache = previous
        if not cache:
            print(f"[error] no {federal.CACHE_PATH}; run 'federal'", file=sys.stderr)
            return 2
    else:
        try:
            cache = federal.fetch(previous=previous)
        except federal.FederalError as exc:
            print(f"[error] {exc}; the committed cache is unchanged", file=sys.stderr)
            return 2
    for person, title in ((cache["president"], "President"),
                          (cache["vicePresident"], "Vice President")):
        print(f"  {title}: {person['name']} ({person.get('party')}), "
              f"{person['termStart']} to {person['termEnd']}")
    for office in cache["offices"]:
        holder = office.get("holder")
        if not holder:
            print(f"  {office['office']}: not listed by the White House")
            continue
        senate = holder.get("senate")
        print(f"  {office['office']}: {holder['name']} - own page {holder['page']['status']}"
              + (", acting" if holder["page"].get("acting") else "")
              + (f"; confirmed {senate['date']}, {senate['yeas']}-{senate['nays']} "
                 f"(vote {senate['vote']})" if senate else "; no Senate roll call found"))
    failed = 0
    for level, code, message, detail in federal.problems(cache):
        print(f"  [{level}] {code}: {message}")
        for line in detail[:10]:
            print(f"           - {line}")
        failed += level == "error"
    if not args.check:
        print(f"[ok] wrote {federal.save_cache(cache, args.root)}")
    return 1 if failed else 0


def _executives(args):
    """Every governor, from the NGA's roster, cross-checked against Wikidata,
    and NCSL's count of each legislature's parties (kyc/executives.py,
    kyc/stategov.py)."""
    from . import executives, stategov
    from .government_maps import STATES
    if args.check:
        cache = executives.load_cache(args.root)
        if not cache:
            print(f"[error] no {executives.CACHE_PATH}; run 'executives'", file=sys.stderr)
            return 2
        governors = cache["governors"]
    else:
        try:
            governors = executives.fetch(previous=executives.load_cache(args.root))
        except executives.ExecutivesError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
        for code, gov in sorted(governors.items()):
            if gov.get("unread"):
                print(f"  [warn] {code}: the NGA page has contact fields the parser does not "
                      f"read: {', '.join(gov['unread'])}")
            if gov.get("headshot") and gov.get("headshotBytes") is None:
                print(f"  [warn] {code}: the headshot's size could not be measured; it is left "
                      f"off the card until it can be")
    missing = [code for code in STATES if code not in governors]
    if missing:
        print(f"[error] no governor for {', '.join(missing)}", file=sys.stderr)
        return 1
    if not args.check:
        wikidata = executives.wikidata_governors()
        if not wikidata:
            # Unreachable is not "no record" (rule 8): keep the last run's
            # confirmation for anyone still in office.
            kept = executives.carry_over(governors, executives.load_cache(args.root))
            print(f"  [warn] Wikidata could not be reached; kept the last check for {kept}")
        agree, disagree = executives.cross_check(governors, wikidata)
        print(f"  Wikidata confirms {len(agree)} of {len(governors)}")
        for code, ours, theirs in disagree:
            print(f"  [warn] {code}: NGA says {ours!r}, Wikidata {theirs!r}")
        try:
            table = stategov.fetch_ncsl()
        except stategov.StateGovError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 2
        print(f"[ok] wrote {executives.save_cache(governors, args.root)}")
        print(f"[ok] wrote {stategov.save_ncsl(table, args.root)} (NCSL, updated {table['updated']})")
    try:
        _, problems = stategov.build(args.root)
    except stategov.StateGovError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    for problem in problems:
        print(f"  [warn] {problem}")
    parties = {}
    for gov in governors.values():
        parties[gov["partyKey"]] = parties.get(gov["partyKey"], 0) + 1
    print(f"  {len(governors)} governors: " +
          ", ".join(f"{n} {k}" for k, n in sorted(parties.items())))
    return 0


def _statelegs(args):
    """Every state legislator from Open States, matched to the district maps."""
    from . import statelegs
    from .government_maps import STATES
    fetched = None
    if args.check or args.images_only:
        cache = statelegs.load_cache(args.root)
        if not cache:
            print(f"[error] no {statelegs.CACHE_PATH}; run 'statelegs'", file=sys.stderr)
            return 2
        by_state = cache["states"]
        fetched = cache.get("fetched")
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
    if not args.check and not args.no_images:
        # Each portrait, checked the tristate way: only a definite answer
        # drops one from the page (rule 8).
        images = statelegs.check_images(by_state, previous=statelegs.load_cache(args.root))
    else:
        images = {code: {"ok": 0, "broken": 0, "unknown": 0} for code in by_state}
        for code, records in by_state.items():
            for r in records:
                if r.get("image"):
                    images[code][r.get("imageStatus") or "unknown"] += 1
    broken = {code: c["broken"] for code, c in images.items() if c["broken"]}
    print(f"  portraits: {sum(c['ok'] for c in images.values()):,} load, "
          f"{sum(broken.values())} confirmed missing and left off the page"
          + (f" ({', '.join(f'{c} {n}' for c, n in sorted(broken.items()))})" if broken else "")
          + f", {sum(c['unknown'] for c in images.values()):,} not checked or inconclusive")
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
        path = statelegs.save_cache(by_state, args.root, fetched=fetched)
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

    rec = add("record", help="the frozen record of the cycle's races (kyc/record.py)")
    rec.add_argument("--freeze", action="store_true",
                     help="write it from the sitting Congress; refuses to overwrite")
    rec.add_argument("--force", action="store_true", help="replace an existing record")

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
    rich.add_argument("--render", type=int, default=enrich.RENDER_LIMIT, metavar="N",
                      help="draw at most N campaign sites with no portrait in a headless "
                           "browser and read them again (0: none)")
    rich.add_argument("--unreachable", action="store_true",
                      help="read again only the committee sites the last read could not reach")

    field = add("field", help="refresh the FEC register of 2026 candidates")
    field.add_argument("--check", action="store_true",
                       help="use the committed cache; make no network call")

    congress = add("congress",
                   help="reconcile the rosters against the authoritative membership")
    congress.add_argument("--check", action="store_true",
                          help="use the committed snapshot; make no network call")
    congress.add_argument("--apply", action="store_true",
                          help="write the drift into the roster CSVs: add the newly "
                               "seated, renew terms, archive whoever the records say left")
    congress.add_argument("--snapshot", metavar="FILE",
                          help="take the membership from FILE, a congress_snapshot.json, "
                               "instead of downloading it (a rehearsal)")
    congress.add_argument("--historical", metavar="FILE",
                          help="read legislators-historical.json from FILE instead of "
                               "downloading it")

    local = add("localgov", help="every local government, county by county (Census listing)")
    local.add_argument("--check-sites", action="store_true",
                       help="open every listed website and record what it is now "
                            "(data/local_sites.json); one request at a time per host")
    local.add_argument("--workers", type=int, default=24,
                       help="hosts checked at once (default 24)")
    local.add_argument("--limit", type=int, default=None,
                       help="check at most this many addresses this run (it resumes)")
    local.add_argument("--max-minutes", type=float, default=None,
                       help="open no new address after this many minutes, then save and stop "
                            "(it resumes); keep it well inside a CI step's time limit")
    local.add_argument("--refresh", action="store_true",
                       help="check every address again, not only those due")
    local.add_argument("--recheck", default="",
                       help="also check again every address with these verdicts, comma-separated "
                            "(after a change to how one is reached; gambling stays for a person)")
    local.add_argument("--states", default="",
                       help="only these states, comma-separated codes")

    courts_cmd = add("courts", help="every state's highest court and its members, from the courts")
    courts_cmd.add_argument("--check", action="store_true",
                            help="report the committed cache; make no network call")

    tribes_cmd = add("tribes", help="every tribal government and its leader (BIA Tribal Leaders "
                                    "Directory)")
    tribes_cmd.add_argument("--check", action="store_true",
                            help="report the committed cache; make no network call")

    voting_cmd = add("voting", help="each state's official voting pages (NASS Can I Vote)")
    voting_cmd.add_argument("--check", action="store_true",
                            help="report the committed cache; make no network call")

    officers_cmd = add("officers", help="every lieutenant governor and secretary of state (NLGA, NASS)")
    officers_cmd.add_argument("--check", action="store_true",
                              help="report the committed cache; make no network call")

    jud = add("judiciary", help="every sitting federal judge (Federal Judicial Center) and the "
                                 "Supreme Court as the Court lists it")
    jud.add_argument("--check", action="store_true",
                     help="report the committed cache; make no network call")
    jud.add_argument("--links-only", action="store_true",
                     help="read only the judges' Wikipedia articles and portraits "
                          "(kyc/judge_links.py), for the committed directory")

    og = add("oge", help="financial disclosures of the President, the Vice President and the "
                         "Cabinet, from the Office of Government Ethics")
    og.add_argument("--check", action="store_true",
                    help="report the committed cache; make no network call")

    mem = add("members", help="members' platforms (official sites), education and careers "
                              "(their Wikipedia infobox), contact pages and district offices")
    mem.add_argument("--check", action="store_true",
                     help="report what the committed cache fills; no network")
    mem.add_argument("--limit", type=int, default=None,
                     help="read at most N official sites this run")
    mem.add_argument("--id", action="append", default=None,
                     help="read this member's official site again (a bioguide id; repeatable)")
    mem.add_argument("--all", action="store_true",
                     help="read every member's official site again, however recent the last read")
    mem.add_argument("--no-sites", action="store_true",
                     help="read the district offices and articles only")

    vt = add("votes", help="every roll call of the Congress, from the House Clerk's and the "
                           "Senate's records, attributed to members by id")
    vt.add_argument("--check", action="store_true",
                    help="report the committed cache; make no network call")
    vt.add_argument("--chamber", choices=("house", "senate"),
                    help="read one chamber only")
    vt.add_argument("--limit", type=int, default=None,
                    help="read at most this many roll calls a chamber this run")
    vt.add_argument("--pause", type=float, default=1.0,
                    help="seconds between requests (never less than 1)")

    hist = add("history", help="the public offices each person has held: Congress from "
                               "congress-legislators, other offices from Wikidata")
    hist.add_argument("--check", action="store_true",
                      help="report the committed cache; make no network call")

    seats = add("seats", help="each seat's last election: the Clerk of the House's official "
                              "statistics, checked against a second compilation")
    seats.add_argument("--check", action="store_true",
                       help="report the committed cache; make no network call")

    out = add("outside", help="independent expenditures for and against each candidate, "
                              "from the FEC")
    out.add_argument("--check", action="store_true",
                     help="report the committed cache; make no network call")

    vac = add("vacancies", help="vacancies in the federal courts, as uscourts.gov lists them")
    vac.add_argument("--check", action="store_true",
                     help="report the committed cache; make no network call")

    fed = add("federal", help="the President, the Vice President and the Cabinet, from the "
                              "White House, each office's page and the Senate's votes")
    fed.add_argument("--check", action="store_true",
                     help="report the committed cache; make no network call")

    execs = add("executives", help="every governor, from the National Governors Association")
    execs.add_argument("--check", action="store_true",
                       help="report the committed cache; make no network call")

    legs = add("statelegs", help="every state legislator, from Open States")
    legs.add_argument("--check", action="store_true",
                      help="match the committed cache to the district maps; no network")
    legs.add_argument("--no-images", action="store_true",
                      help="do not check whether each portrait loads")
    legs.add_argument("--images-only", action="store_true",
                      help="check the committed roster's portraits again; do not refetch it")

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
    money.add_argument("--field-only", action="store_true",
                       help="only the challengers still on a ballot, by their own filing")

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
    if args.command == "localgov":
        return _localgov(args)
    if args.command == "executives":
        return _executives(args)
    if args.command == "federal":
        return _federal(args)
    if args.command == "judiciary":
        return _judiciary(args)
    if args.command == "vacancies":
        return _vacancies(args)
    if args.command == "history":
        return _history(args)
    if args.command == "members":
        return _members(args)
    if args.command == "seats":
        return _seats(args)
    if args.command == "outside":
        return _outside(args)
    if args.command == "oge":
        return _oge(args)
    if args.command == "votes":
        args.pause = max(1.0, args.pause)
        return _votes(args)
    if args.command == "courts":
        return _courts(args)
    if args.command == "officers":
        return _officers(args)
    if args.command == "voting":
        return _voting(args)
    if args.command == "tribes":
        return _tribes(args)
    if args.command == "verify":
        return _verify(args)
    if args.command == "congress":
        return _congress(args)
    if args.command == "field":
        return _field(args)
    if args.command == "disclosures":
        return _disclosures(args)
    if args.command == "record":
        return _record(args)
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
