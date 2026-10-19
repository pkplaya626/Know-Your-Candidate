# CLAUDE.md

Guidance for working in this repository. See `README.md` for the user-facing
overview.

## What this project is

A non-partisan civic dashboard covering the 119th U.S. Congress and the 2026
midterms. It makes factual claims about real, named people, so **a silent data
error is the worst failure mode here** — worse than a crash, which at least
announces itself. Prefer loud failure and explicit validation over defensive
fallbacks that paper over bad input.

## Architecture

Static site. No backend, no bundler, **no third-party Python packages, and no
third-party CSS or JavaScript on the page either**. Keep it that way: `pandas`
was removed from the pipeline deliberately, and CI fails if a
`requirements.txt` appears, if `pyproject.toml` grows a runtime dependency, or
if a page loads a remote script, stylesheet or font.

```text
*.csv (repo root)           ──┐
us_atlas_states_topo.json   ──┤
district_maps/*.json        ──┤   (every state's districts; tools/fetch_district_maps.py)
legislative_maps/*.json     ──┤   (state senate and house districts, counties; tools/fetch_legislative_maps.py)
local_governments/*.json    ──┤   (every local government, from the Census listing; localgov)
local_maps/*.json           ──┤   (every incorporated place and county subdivision, a point each; tools/fetch_local_maps.py)
congress_snapshot.json      ──┤
data/fec_field.json         ──┤   (the FEC's 2026 candidate register)
data/disclosures.json       ──┤
data/primary_results.json   ──┤
data/committees.json        ──┤   (committee rosters, with rank and title)
data/campaigns.json         ──┤
data/enrichment.json        ──┤
data/odds.json              ──┤
data/census_governments.json ─┤
data/state_legislators.json ──┤
data/executives.json        ──┤   (every governor, from the NGA)
data/statewide_officers.json ─┤   (lieutenant governors, secretaries of state, attorneys general)
data/courts.json            ──┤   (each state's highest court, from the courts)
data/voting_links.json      ──┤   (each state's official voting pages: NASS Can I Vote)
data/voting_dates.json      ──┤   (each jurisdiction's key dates, from its own pages: hand-edited, kyc/voting_dates.py)
data/federal_executive.json ──┤   (President, VP, Cabinet: White House, office pages, Senate votes)
data/judiciary.json         ──┤   (every sitting federal judge: FJC directory; the Supreme Court's own list)
data/judicial_vacancies.json ─┤   (vacancies, announced vacancies and emergencies: uscourts.gov)
data/judge_links.json       ──┤   (judges' articles and portraits: FJC slug -> Wikidata P2736)
data/court_districts.json   ──┤   (which district court covers each county: 28 U.S.C. 81-131)
data/political_history.json ──┤   (public offices held: congress-legislators; Wikidata the article confirms)
data/oge_disclosures.json   ──┤   (the executive's financial reports: Office of Government Ethics, by office)
data/tribal_leaders.json    ──┤   (every tribal government and its leader: BIA Tribal Leaders Directory)
data/local_sites.json       ──┤   (each local government's listed website, opened: localgov --check-sites)
data/members.json           ──┤   (members' platforms, education, careers, offices: members)
data/record_2026.json       ──┤   (the frozen 2026 race set: record --freeze)
data/departed_members.json  ──┤   (who left this Congress: congress, from legislators-historical)
data/partisan_composition.json ┴─> kyc/ ──> candidate_profiles_site/
                                             data/profiles.js   (profiles, races, build meta)
                                             data/geo.js        (SVG path data for the map)
                                             data/odds.js       (market prices, polling averages)
                                             data/government.js (the guide's maps: kyc/government_maps.py)
                                             data/stategov.js   (governors, chamber control, trifectas)
                                             data/legislature/*.js (one state legislature per state)
                                             data/local/*.js    (one state's counties and governments)
                                             data/courtcounties.js (each county's federal district court)
                                             data/districts/*.js (one district map per state)
                                             states/*.html      (generated, one per state)
                                             districts/*.html   (generated, one per state)
                                             government/*.html  (generated: Know Your Government, kyc/government_text.py)
                                             legislature/index.html, counties/index.html (generated directories)
                                             legislature/*.html (generated, one per state)
                                             counties/*.html    (generated, one per state)
                                             federal/index.html (generated: the federal government)
                                             courts/*.html      (generated, one per federal court)
                                             data/federal.js    (the executive, the Supreme Court, the courts)
                                             data/judiciary/*.js (one federal court's judges, and the judges' search)
                                             about.html, 404.html (generated: the site's frame, kyc/pages.py)
                                             districts/index.html, courts/index.html (generated directories)
                                             site.webmanifest   (generated)
                                             sitemap.xml        (generated)
                                             ├──> index.html    (grid, races, profiles)
                                             └──> map.html      (partisan map)
                                             assets/kyc.css
                                             assets/kyc.js
                                             assets/kyc-odds.js
                                             assets/kyc-cards.js
                                             assets/kyc-profile.js
                                             assets/kyc-senate.js
                                             assets/kyc-directory.js
                                             assets/kyc-map.js
                                             assets/kyc-state.js
                                             assets/kyc-districts.js
                                             assets/kyc-usmap.js
                                             assets/kyc-regionmap.js
                                             assets/kyc-legislature.js
                                             assets/kyc-local.js
                                             assets/kyc-stategov.js
                                             assets/kyc-guide.js
                                             assets/kyc-official.js
                                             assets/kyc-federal.js
```

- The root CSVs are the editorial source of truth. The state atlas and
  `congress_snapshot.json` are vendored inputs: refreshed by a command, never
  hand-edited. So is `district_maps/`, written by `tools/fetch_district_maps.py`
  from Census boundaries and each redrawn state's own enacted-plan file.
- Everything in `data/` is **generated**. Never edit `profiles.js`, `geo.js`,
  `odds.js` or `districts/*.js` by hand. `portraits.json`, `finance.json`, `fec_field.json`,
  `disclosures.json`, `primary_results.json`, `committees.json`,
  `campaigns.json`, `enrichment.json`, `odds.json`,
  `census_governments.json`, `state_legislators.json`, `executives.json`,
  `partisan_composition.json`, `statewide_officers.json`, `courts.json`, `voting_links.json`, `voting_dates.json`,
  `federal_executive.json`, `judiciary.json`, `judicial_vacancies.json`,
  `judge_links.json`, `court_districts.json`,
  `political_history.json`, `oge_disclosures.json`, `tribal_leaders.json`, `local_sites.json`
  and `departed_members.json` are caches, but
  they *are* hand-editable. `stategov.js` is generated from the last five,
  with `kyc/ballot2026.py`: which state offices and legislative seats are on
  the 2026 ballot, a curated table citing each state's own record.
  `members.json` (`members`, rule 86) is a hand-editable cache too.
- `index.html` / `map.html` are **hand-maintained templates**. The build reads
  them to check they load the right scripts in the right order, and rewrites
  nothing in them but the version stamps on their asset URLs (rule 76); they
  must carry the frame `kyc/pages.py` writes (navigation, footer line,
  sidebar freshness line, the home page's structured data: `emit.check_nav`).
  `states/*.html`, `districts/*.html`, `government/*.html`, `about.html`,
  `404.html` and `sitemap.xml` are the opposite: generated from `kyc/pages.py` (the
  guide's words from `kyc/government_text.py`) on every build, never
  edited by hand, and `verify` fails when one on disk is not what the
  template would write.
- Shared page behaviour belongs in `assets/`, not in a page. Neither page
  contains an inline `<script>` block of code. The one inline block allowed
  is structured data (`<script type="application/ld+json">`, written by
  `pages.jsonld`), and `emit.inline_script_problems` fails any other, or one
  that does not parse as JSON.

## Commands

```bash
python build_profile_site.py                  # build (offline)
python build_profile_site.py build --check    # validate only
python build_profile_site.py verify           # committed data matches sources
python build_profile_site.py congress --check # roster vs Congress (offline)
python build_profile_site.py congress --apply # write the drift in: new members, new terms, departures
python build_profile_site.py congress --apply --snapshot FILE  # the same from a file (a rehearsal)
python build_profile_site.py geo              # regenerate map geometry only (both maps)
python build_profile_site.py congress         # refresh membership, and who has left this Congress (network)
python build_profile_site.py field --check    # who is running, from the FEC
python build_profile_site.py disclosures      # House and Senate disclosure links
python build_profile_site.py results          # who is still in, from Wikipedia (Louisiana's qualified list; the states' certified ballots)
python build_profile_site.py record           # the frozen 2026 race record (--freeze writes it; refuses to overwrite)
python build_profile_site.py campaigns        # campaign websites from FEC committees
python build_profile_site.py enrich           # fill gaps; check every campaign site
python build_profile_site.py odds             # market prices and polling averages (writes odds.js)
python build_profile_site.py census           # local governments by state (Census of Governments)
python build_profile_site.py statelegs        # every state legislator (Open States), matched to districts
python build_profile_site.py localgov         # every local government (Census listing), checked
python build_profile_site.py localgov --check-sites  # open every listed local website; resumes (rule 78)
python build_profile_site.py executives       # every governor (NGA), and NCSL's party counts
python build_profile_site.py officers         # lieutenant governors (NLGA), secretaries of state (NASS), attorneys general
python build_profile_site.py courts           # each state's highest court, from the court's own roster
python build_profile_site.py voting           # each state's official voting pages (NASS Can I Vote)
python build_profile_site.py federal          # the President, VP and Cabinet (White House, office pages, Senate roll calls)
python build_profile_site.py judiciary        # every sitting federal judge (FJC) and the Supreme Court as the Court lists it;
                                              # the territorial courts' judges from their own sites; judges' Wikidata links
python build_profile_site.py vacancies        # vacancies in the federal courts, as uscourts.gov lists them
python build_profile_site.py history          # public offices each person has held (congress-legislators, Wikidata, Wikipedia)
python build_profile_site.py oge              # the executive's financial reports (Office of Government Ethics), by office
python build_profile_site.py members          # members' education and careers (Congressional Directory), platform (official site), offices
python build_profile_site.py tribes           # every tribal government and its leader (BIA Tribal Leaders Directory)
python tools/fetch_legislative_maps.py        # state senate and house boundaries (Census, network)
python tools/fetch_local_maps.py              # every incorporated place and county subdivision, for the county pages (Census, network)
python tools/fetch_court_districts.py         # which federal district court covers each county (28 U.S.C. 81-131, govinfo, network)
python tools/rehearse_changeover.py --out DIR # December's specials and January 3, on a copy outside the repo (CI runs it)
python -m unittest discover tests             # 1705 tests, no dependencies
npm install && npm test                       # 2254 real-DOM checks (needs jsdom)
```

Only `fetch`, `portraits`, `finance`, `field`, `disclosures`, `results`,
`campaigns`, `enrich`, `odds`, `census`, `statelegs`, `localgov`, `executives`,
`officers`, `courts`, `voting`, `federal`, `judiciary`, `vacancies`, `history`, `oge`, `tribes`, `members` and `congress` touch the network, as do the three `tools/fetch_*_maps.py` scripts and `tools/fetch_court_districts.py`. Run the
unit tests and `build --check` after touching the pipeline; run `npm test`
after touching a page or anything in `assets/`. Run `verify` before committing
generated data.

## Rules that exist because of real bugs

Each of these was a shipped defect found by measurement. Do not undo them.

1. **Derive election flags in Python, not in the page.** `isCandidate`,
   `seatUp2026`, `seekingReelection2026`, `raceId` and the 2026 Senate seat
   table live in `kyc/`. They were previously duplicated byte-for-byte in both
   HTML files — two places to fix, two places to drift.

2. **All 435 House seats are up every cycle.** House terms are two years, so
   `seatUp2026` is true for every House member. It previously read true *only*
   for retiring members — exactly the people not on the ballot.

3. **Key people on (name, state), never on name alone.** Rep. Mike Rogers
   (AL-3) and 2026 Senate candidate Mike Rogers (MI) are different people. A
   name-keyed photo override put one man's face on the other's profile, and a
   name-keyed dedup silently deleted six candidate records.

4. **Normalise districts in the pipeline, not in template strings.** Member
   CSVs say `"District 3"`, candidate CSVs say `"TX-32"`. Rendering these raw
   produced `House • AL-District 3` and `House • TX-TX-32`. The page renders
   `item.officeLabel` and never rebuilds it; three separate copies of that
   rebuild have been deleted.

5. **Match longer state names first.** `"VIRGINIA" in "WEST VIRGINIA"` is true.
   Also: only read bare two-letter codes from the *original* casing, or
   uppercased prose turns "in", "or" and "me" into Indiana, Oregon and Maine.
   The grid's search matched words as substrings, so "Kansas" returned
   Arkansans first and "TX-3" all of TX-30 to TX-39 (audit 2026-10-17,
   GRID-03/04). A search word matches where a word starts, and a query that
   is a state's whole name or code, or a district however written, is that
   place (`KYC.queryScore`), never text.

6. **A filed `$0` is not missing data.** `fmt_curr(0)` returns `"$0.00"`.

7. **Write output atomically.** `emit.py` writes to a temp file and renames.
   The previous in-place HTML surgery could truncate a 900 KB page to one
   character if its end-marker search failed.

8. **Never discard on an inconclusive network check.** `portraits.check_image`
   is deliberately tristate. Treating HTTP 429 as "broken" silently threw away
   ~160 working portraits.

9. **Never add a topical hint to a Wikipedia search.** `Dan Osborn NE politician`
   pushes his own article out of the results; `Dan Osborn` returns it first.

10. **A placeholder sentence is not data.** `"N/A (No net worth disclosure
    provided in sources)"` was rendered to users verbatim as if it were a
    finding. Everything surfaced on a profile goes through
    `normalize.classify()` in the pipeline and `KYC.renderField` on the page,
    and absences are excluded from search. `map.html` kept its own copy of the
    profile dialog that used `textContent` directly, so it shipped this exact
    bug months after the grid stopped — hence rule 12.

11. **Validate the field, not just its presence.** `"2026 Primary"` sat in a
    Birthdate column and passed a "contains four digits" check. Use
    `looks_like_date()`.

12. **One implementation, not one per page.** The profile dialog builds its own
    DOM in `assets/kyc-profile.js` rather than being pasted into both pages,
    which is what makes a second copy impossible. When both pages need
    something, it goes in `assets/`.

13. **Escape everything, and use delegated listeners.** Card and row markup
    interpolated `item.name`, `item.party` and the office label straight into
    `innerHTML`, and every card carried an `onclick` with a profile id
    interpolated into it. Use `KYC.escapeHtml` / `KYC.escapeAttr` and a
    `data-id` attribute read by one delegated listener. CI greps for
    `onclick=`.

14. **Never load a page's own module before its data.** Each generated file
    assigns a global that the page modules read as they initialise, so the
    wrong `<script>` order renders an empty site with no error anywhere.
    `emit.check_pages` asserts the order.

15. **Do not block pinch-zoom.** `user-scalable=no, maximum-scale=1` was in
    both viewport tags. It fails WCAG 1.4.4.

16. **A roster cannot notice that Congress changed.** The CSVs are accurate -
    checked field by field against `congress-legislators` they disagree about
    nobody - but two representatives seated in September 2026 were absent from
    the site and nothing said so. `congress_snapshot.json` is the
    authoritative membership; `validate.check_snapshot` makes any drift a
    build error. Never "fix" a drift finding by deleting the check.

17. **Match people on ids, never on surnames.** `SENATE_SEATS_UP_2026` said
    `"SC": "Graham"` for Lindsey Graham; that seat is now Darline Graham
    Nordone's, and the entry kept matching only because she shares the
    surname. The 2026 Senate class is derived from real term dates and matched
    on bioguide id. The same rule sends FEC lookups through the authoritative
    candidate id rather than a name search - the FEC files people under their
    legal name, and a loose match puts someone else's money on a profile.

18. **Do not answer "is this in sync?" by diffing whole files.** CI used to
    rebuild and `git diff --exit-code`, which conflates sync with build time.
    A rebuild always restamps the timestamp, so keeping the diff quiet meant
    committing the fixed `SOURCE_DATE_EPOCH` date - which the page footer
    shows to readers as the freshness stamp. Generated files carry a content
    signature and `verify` compares that.

19. **Distinguish "we did not look" from "we looked and it is not there".**
    `normalize.NO_FILING` exists because "No data" is a claim about us. The
    FEC is queried for every profile, and 17 sitting members have no filing
    this cycle because they are running for a different seat - which is
    information, not an absence of it. Never fill that gap with the previous
    cycle's figures; 2024 receipts on a 2026 page read as current money.
    The same goes for a share: "Funding sources" is of total receipts,
    loans and transfers included, and a candidate's own loan is their own
    money. Read from four contribution types, Jefferson Shreve, whose
    $2,000,000 loan was 79% of what his campaign received, read "PACs 70%".
    Where an adjustment the FEC deducts leaves a category negative, the
    shares are of the positive parts, and the profile says that sum
    (`fundingBase`) beside the receipts: Shri Thanedar's add up to
    $3,968,600 against $3,194,222 raised. And a challenger's split is read
    from their own filing (`fec.resolve_field`, the endpoint the
    incumbent's comes from), or every challenger beside a member's
    breakdown read "No data"; the daily refresh re-reads the oldest of
    them, a batch a day, and a stopped finance run warns and lets the
    refresh go on to the results.

20. **Check attribution, do not trust it.** An FEC candidate id encodes its
    own office and state, so `validate.check_finance` compares every figure
    against the profile it is about to appear on. Money shown against the
    wrong person looks entirely normal on the page.

21. **The public hostname has one source of truth.** `CNAME` is what GitHub
    Pages serves from; the canonical links, `og:url`, `robots.txt` and
    `sitemap.xml` must agree, and `verify` fails when they do not. A
    half-finished rename looks completely normal locally. Never put a hostname
    in a new file without adding it to `emit._HOST_REFERENCES`. Every own
    address on the home page is checked, its structured data's too, and the
    share card's source (`tools/social-card.html`), whose PNG prints the
    host: after a rename, regenerate it. No image carries the Congress's
    number; the card read "The 119th Congress" until 2026-10 (rule 68).

22. **A roster of challengers is not the field.** 57 curated challengers made
    the site report 436 of 474 races as having no declared challenger when
    only four of them did. The field comes from the FEC. `filedCount` on each
    race counts *everyone* who has filed, at any funding level, so a seat is
    never called uncontested because the people running are under a threshold.

23. **The candidate threshold is statutory, not editorial.** The receipts
    distribution has no natural cliff, so `candidates.STATUTORY_THRESHOLD` is
    the $5,000 at which 52 U.S.C. 30101(2) makes someone a candidate. If it
    ever needs to move, move it to another legal definition, not to a number
    that makes the page look tidy.

24. **Do not guess anyone's portrait.** The bioguide -> Wikipedia mapping
    cannot pick the wrong person; a title guess or a name search can, and
    "Michael Smith" resolves to a stranger. A portrait reaches a profile by
    an id - the Clerk's, congress.gov's and the Biographical Directory's
    photographs by bioguide id, the article the bioguide mapping names -
    through the article the person's ballot page links (rule 33), from the
    campaign site their own committee filed (rule 38), or as an evidenced
    `CANDIDATE_PHOTOS` entry naming a served file, and by no other route,
    for members and curated rows as much as filed candidates. A ballot link
    withheld as leading elsewhere is withheld before any portrait is taken
    from it (`enrich.withhold_links`).
    `title_is_about` rejects a resolved title that does not contain the
    person's surname - which is how a photograph of an Iran war protest ended
    up on Brian McGinnis's profile via a redirect. The guess came back
    through every other door: on 2026-10-17 the New Jersey and Oregon
    Republican Senate nominees showed a rugby league player and an Olympic
    kayaker from `Special:FilePath/<Name>.jpg`, every member's fallback chain
    ended in the same guesses ("Al_Green.jpg" is the singer), Kansas's
    nominee carried a 1930s photograph found by guessing "Adam Hamilton
    (politician)", and 24 of the 25 "hand-chosen" `CANDIDATE_PHOTOS` URLs
    named files that did not exist. So `photos.py` builds no URL from a
    name, `portraits.route_ok` refuses a cached portrait that did not come
    by one of these routes (it is applied after the results, which carry
    the ballot link), and `validate` fails on any `Special:FilePath` or
    `Special:Redirect` URL in any profile's chain.

25. **Report look-alike people; never merge them.** Alaska's Senate race holds
    both Dan Sullivan and a different Daniel J Sullivan.
    `validate.check_duplicate_people` warns and stops there. Only exact
    signals deduplicate automatically: a shared FEC candidate id; an exact
    first-and-last-name match against the sitting member of that same seat;
    and one committee's money reported under two registrations of the same
    name (`candidates.same_committee`: identical receipts, disbursements and
    coverage end). A shared name alone merged two Michael Thompsons in
    Florida and erased the FL-22 one from his race. Anything weaker is a
    curated, evidenced entry in `overrides.SAME_PERSON_FILINGS`. The merged
    ids stay on the profile as `otherFecIds`, so old links still open it.

26. **Net worth is not derived from a disclosure.** The forms report assets in
    bands; one figure from them is an estimate dressed as a fact.
    `disclosures.py` links the filing instead and never writes `net_worth`.

27. **A challenger is not a member, and the page must let a reader say so.**
    The FEC field made 79% of profiles people who do not hold the seat. The
    grid has a `role` filter and the map's delegation panel leads with who is
    seated. Any new view that lists people needs the same distinction, or it
    answers "who is running" when the reader asked "who represents me".
    The grid's search finds officials who are not candidates (the Cabinet,
    judges, governors) and members who left this Congress
    (`data/departed_members.json`); they are listed apart as links, never as
    profiles, so no count of who sits or runs can include them.

28. **Only write fields the source actually knows.** `congress --apply` fills
    name, party, state, district, term and birthday. Education, net worth,
    committees and platform stay empty, because the provenance layer reporting
    "No data" is true and a plausible invention is not.

29. **The FEC says who filed; it does not say who lost.** By September of an
    election year the register listed 858 people as running who had already
    been eliminated. `results.py` reads the state results pages behind a
    calendar gate, takes winners only from the `winning candidate` template,
    treats a table with no marked winner as undecided, and strikes an unnamed
    filer out only once the page has decided *their* contest. Eliminated
    people are hidden behind a toggle; nothing is deleted.

30. **The seat a person is contesting comes from their filing, and whether
    they are on the ballot comes from the results page.** The roster seats a
    member where they sit. After the 2025 redistricting thirteen members run
    in a different district number, seven House members run for the Senate,
    and thirty-nine more retired without the roster noticing; every one read
    as "seeking re-election" to a seat they are not contesting, and TX-35
    reported two Democratic nominees. `contestRaceId` and the absence rule in
    `results.apply_cache` derive both; `validate` lists every inference so a
    matching failure is seen. Nobody whose name fitted two filings is ever
    inferred absent.

31. **Split template parameters on the pipes that separate them.** A
    line-based field regex read Michigan's one-line rows as a candidate named
    `"Haley Stevens|party=Democratic Party |votes=731,160"`, and every result
    in that state went unread while nothing failed. `template_fields` walks
    the text and splits only at depth zero, so piped links and nested
    templates inside a value survive.

32. **Build every outbound link from an id the source holds, never from a
    name.** Members link to GovTrack, OpenSecrets, Vote Smart and
    Ballotpedia through the ids in `congress-legislators`; everyone links to
    the FEC through their candidate id; a campaign site comes from the
    committee's own Form 1. A Ballotpedia URL guessed from "Mike Rogers" is
    the wrong Mike Rogers half the time and looks entirely normal.

33. **A ballot page's link is an authority; a search is not.** Rule 24 stands
    - the field's portraits are never guessed - but a filing the state's
    election page links to an article carries that title (`wikipediaVia:
    "election-page"`), resolved through the title alone and still checked
    against the surname after redirects. That is how 201 challengers got a
    portrait without a single guess, and how Brian McGinnis's protest photo
    was rejected a second time. The link itself is checked the same way:
    `enrich` follows every ballot link's redirects, and one that lands on a
    section of another article, a list, an election or a party article is
    withheld (`wikipediaWithheld`) - "Brian McGinnis" leads to the protest,
    "Elijah Manley" to a party's 2016 primaries, and one candidate's link
    was the Cascade Party of Washington's own article. A title without the
    surname is withheld too, even a living person's article (a spouse or a
    namesake is one), unless `overrides.ARTICLE_UNDER_ANOTHER_NAME` records
    it with evidence ("Luther Campbell" is "Uncle Luke"); the link, the
    portrait, the infobox and the offices held all ask
    `portraits.article_is_theirs`, so none of them disagrees.

34. **Fifty-seven near-identical pages are generated, not maintained.** The
    state pages come from one template and carry nothing but a state code;
    `assets/kyc-state.js` renders them from the same `profiles.js` as the
    grid. A hand-edited copy per state would drift the first time one was
    touched, and a state page that disagreed with the grid about who holds
    a district would look entirely normal.

35. **A registered campaign site is not a working one.** The FEC keeps the
    website a committee filed, sometimes cycles ago, and lapsed campaign
    domains get bought. On 2026-10-01 seven sites linked from this page,
    five of them sitting members', served gambling spam under the
    candidate's name, and 13 more did not exist in DNS. Such hosts go in
    `overrides.BLOCKED_CAMPAIGN_HOSTS` with the date and what was seen. A
    block is no wider than the evidence: a dead `www.` host does not block
    its bare domain. Never treat a single failed lookup as dead (rule 8);
    confirm it at a second resolver first.

36. **Page on a unique key, and count what came back.** OpenFEC pages with
    LIMIT/OFFSET. The field was sorted on "-receipts", where 1,386 filers
    share $0, so tied rows shuffled between page requests: each refresh
    returned about one filing in seven twice and silently skipped as many,
    a different set every time - 638 people, a sitting member's filing with
    them, and Rhode Island's Senate primary from the unsorted calendar.
    `fec.fetch_pages` takes a sort that ends in a unique key; the field
    must arrive with every (candidate_id, cycle) exactly once or it is
    refetched and then refused.

37. **Pace to the limit the key reports, not the one the docs promise.** The
    FEC key answers `X-RateLimit-Limit: 60` - a minute, not 1,000 an hour.
    Runs from home stayed under it by accident of latency; the first refresh
    on a GitHub runner sent 61 requests in under a minute, got 429, and
    failed. `fec._get` spaces every request from that header (never faster
    than one a second) and waits out `Retry-After` or the whole window on a
    429. A failed refresh opens a "Weekly refresh failed" issue and the next
    good one closes it. A refresh pull request still open after a day opens
    a "Refresh waiting for review" issue (`refresh-waiting.yml`). A good
    refresh nobody merges is as stale as a failed one.

38. **Fill a gap only from a source tied to the person, in its own words,
    and say which.** A filed candidate arrives with a name, a party and
    money. `enrich.py` reads only the article their ballot page links
    (rule 33) and the campaign site their committee filed (rule 32) or the
    race page lists - never a search. What reaches the page is quoted, not
    paraphrased: an infobox date, the campaign's own description of itself,
    the headings of its issues page. All of it goes through
    `normalize.fill_field`, which never overwrites a value and records the
    source in `fieldSources` for the page to badge. A site must name the
    candidate in its text before anything is taken from it, and an image
    must carry their surname in its file name or alt text *and* be taller
    than it is wide, unless its own name says headshot, portrait or
    profile. Look at what passes: the first full run's 79 "portraits"
    included a T-shirt, a clipboard icon, four logos and eight group or
    family photographs, every one carrying the right name. What passes
    every rule and is still not a likeness goes in
    `overrides.NOT_A_PORTRAIT`, because the weekly re-read undoes an edit
    to the cache. Issue headings come from one heading level of a page
    that is not a ballot-question page ("Tyler votes NO" under a measure is
    not his platform), and never a line naming anyone else in the race -
    "Rob Wittman has allowed healthcare prices to skyrocket" is an attack
    line, not a platform.

39. **Read every linked campaign site, and know a compromised site from a
    hijacked one.** Rule 35's blocklist was a one-off sweep; domains keep
    lapsing. `enrich` reads every committee site linked for anyone still
    in a race, members' too. Visible gambling spam or a parking page is
    withdrawn from the profile automatically and reported for a person to
    record in `BLOCKED_CAMPAIGN_HOSTS` - that is how `joshweil.us` (a 301
    chain to a slot site) and two parked domains were found on 2026-10-02,
    one of them only after redirects were followed with cookies and a
    page's `window.location = "/lander"` was read as the parking script it
    is. Spam *hidden* in the campaign's own page (`display:none`,
    off-screen) is a compromised site, not a lapsed one: Ron Johnson's
    stays linked and is reported. A bot wall, a JavaScript-only page or a
    timeout concludes nothing (rule 8).

40. **A market belongs to the state its own question and rules name, and
    its price is quoted, never blended.** Kalshi's series ticker
    `SENATELA` holds *Kentucky's* race - "Will Republicans win the Senate
    race in Kentucky?", resolving on "a Senator of Kentucky" - while
    Louisiana's sits under `KXSENATELA`, and Alabama's series is titled
    just "Alabama". `odds.py` uses tickers and titles only to find
    candidates; a market is attributed to a state when its question and its
    resolution rules both name it, and a Polymarket event when its title and
    description agree. An outcome label that names nobody in the race is
    shown as the party the market resolves on and reported (rule 20). Each
    source's price, and each aggregator's polling average as the race's
    Wikipedia page lists it, is shown as published, dated, linked and
    labelled as not a poll and not this site's forecast; a poll table is
    used only when every candidate column names someone in the race, which
    is how the primary's "Cornyn / Hunt / Paxton" table stayed off the
    November race. House markets are placed the same way, by the district
    code both the question ("the House race for CA-3") and the rules
    ("sworn in for CA-03") carry. A label naming someone other than this
    site's candidate of that party is a conflict and a warning; one naming a
    nominee too small to have a profile here is counted, not warned about.

41. **A file that publishes on its own may change only itself.**
    `.github/workflows/odds.yml` commits to `main` every twelve hours
    without a review, so `data/odds.js` is a pure function of
    `data/odds.json` - labels are checked when prices are read and stored
    in the cache, never against the race list at build time - the build
    rewrites it only when its signature changes, and the workflow refuses
    to commit if any other file would change. Anything that would make the
    roster build touch the odds files, or the odds job touch anything else,
    breaks the property that keeps an unreviewed commit safe. The job stops
    refreshing at the first poll closing (23:00 UTC on Election Day), and
    from that day the page labels the prices final and not results. Prices
    that move on early returns would read as results.

42. **A srcset lists sizes of one photograph.** congress.gov's member
    portraits are 175px wide, soft on a 2x screen. The first-choice Wikimedia
    images were 960px thumbnails, or originals up to 2,364px wide, drawn in
    38px circles. The larger official copies are other photographs: for
    seven of ten members sampled on 2026-10-03, the House Clerk's was newer
    and the unitedstates project's a Congress or two older. A srcset mixing
    them would let screen density choose which photograph a reader sees. So
    a House member's portrait is the Clerk's, a single URL. A senator's is
    the article's, through the bioguide mapping. `photoSet` holds only
    Wikimedia's standard sizes of that one file, since any other width is
    refused with HTTP 400. The sizes are built from the measured original.
    `portraits` fetches only the smallest, slowly: the first run fetched
    every size, and a burst gets 429 for everything from that address. The
    page falls back to the plain URL when a size fails, and
    `validate.check_photo_sets` fails a set that names another file. The
    project's old image host,
    theunitedstates.io, lapsed into a parking network; nothing links it now
    (rule 35).

43. **Size map text for the width the map is drawn at.** The district
    maps' numbers were sized for a 620px map and scaled down with it, so a
    phone drew them 4px tall; the partisan map's codes were 3.8px, at weight
    800 on a halo - a glow, not a letter. Both pages measure the width they
    draw at and write text 11px on screen, where the build's measured room
    (`room`, `labelRoom`) says it fits; the rest is numbered in an inset or a
    callout, never dropped. `test_every_district_is_numbered_at_every_width`
    checks every district at every width from `PHONE_PX` up. A label point
    is the pole of what the page draws: a new map's district is labelled on
    its land (`geo.polylabel(..., within=)`). The grid search it replaced
    ignored its own bounding box and numbered FL-19 and OH-14 on their own
    borders.

44. **On a phone, the page scrolls.** A fixed body with a scrolling box
    inside kept Safari's toolbars on screen, broke tap-to-top, and pinned the
    grid's filters over half the screen while results scrolled under them.
    Below 1000px the document scrolls under a sticky header, and what must
    stay in reach (the dialog's close button) is sticky inside what scrolls.
    Every field and menu is 16px there, or iOS zooms the page when one is
    tapped and leaves it zoomed.

45. **Time it on a throttled phone, not on this machine.** A mid-range
    Android phone runs a page about 4x slower than a desktop. Texas's
    district page froze such a phone for 11-12 seconds: the new map was
    clipped to a `<clipPath>` of 38 `<use>` elements, and Blink took 2
    seconds just to resolve it even on a desktop. One path of the same
    rings draws the same pixels in 0.5 seconds. Measured the same way:
    - The label search compared every sample with every other.
    - Each district page drew three times on load.
    - Closing a profile redrew the grid from its first card, losing the
      reader's place.
    Before shipping anything that draws, time it under CDP
    `Emulation.setCPUThrottlingRate` 4 and 6, as well as looking at it.
    Keep a clip, mask or filter to one child.

46. **Words on a map are page text, not SVG text.** Samsung Internet's
    dark mode is on whenever the phone is dark. By default it repaints
    every page and ignores `color-scheme`, `only light` and
    `prefers-color-scheme` alike. Inside an SVG it lightens anything dark
    and keeps anything light. A district number's dark text and its light
    halo both came out light, and every label on both maps bloomed into a
    smear: the "too bold", then "blurry", text reported from a Galaxy.
    No halo colour survives that. Page text on a page background does:
    every forced dark mode darkens the backing and lightens the text. So
    labels are spans on a small backing, placed by percentage over the map
    (`kyc-districts.js` `text()`, `kyc-map.js` `drawMap`), and the tests
    fail if either map draws an SVG `<text>`. The page still declares the
    scheme it shows with `only` (`syncColorScheme`), which Chromium honours.

47. **Check every page, not only the pages at the root.** CI's link check
    globbed `candidate_profiles_site/*.html`, so every one of the 56
    district pages linked "States & territories" to a `districts/index.html`
    that never existed, and nothing failed. CI and
    `test_guide.TestEveryLocalLinkResolves` walk every folder now.

48. **The guide is checked text, and names no one.** `government/` explains
    institutions in static prose, so each section cites the primary
    sources it was checked against, and `validate.check_guide` fails on a
    link to a page, section or state that does not exist, or a section
    with no source. The owner's source report said 574 tribes (575 since
    the Lumbee were recognized in December 2025), treated FTC removal
    protection as settled (*Trump v. Slaughter*, June 2026, struck it
    down), and called the federal executive "unitary", a contested
    theory's label. Every claim was researched and then attacked by a
    second agent before it was written. When the text is revised, re-check
    what can change (counts, decisions, agency names) and move `REVIEWED`;
    a page checked on another day carries its own `"reviewed"` date.
    Who holds an office is never typed in: the Congress page renders
    committee leads from the rosters, and a committee's minority lead is
    found by the seat's `side`, not its title. The 2026-10-17 audit found
    the same rosters titling the narcotics caucus's minority lead
    "Chairman", two chairmen of one panel: a minority seat with a chair's
    title is a build warning until the body's own style is recorded, with
    evidence, in `overrides.COMMITTEE_TITLES`. The Speaker and the party
    leaders come from congress-legislators' `leadership_roles`, tribal
    leaders from the BIA's directory. A count the text states that a table
    determines is written `{{key}}` and filled from that table: the text
    said "about 26" lieutenant governors preside over the map's 24. A page
    has one name (`government.name`) wherever it is named (rule 75), a
    state's fact on a map cites the general sources and its own (`scoped`),
    never another state's, and a figure is page text, never SVG (rule 46).

49. **A map of every state is a claim about every state.** The guide's maps
    (`kyc/government_maps.py`) must give each of the fifty a sourced value,
    and `check()` fails otherwise. A fact known for three states is a list
    in the text, not a map: "councils that check the governor" was dropped as
    a map because Iowa's Executive Council and other boards of elected
    officials would have been coloured as having none. Draw categories in
    `--cat-*` and `--scale-*`, never party colours, and keep a state that has
    none of a thing ("X" in the Census table) apart from a count of zero.

50. **A compiled table is a lead, not a source.** The Book of the States
    2022 gives New Jersey's Supreme Court five justices; it has seven. Its
    tables also predate Utah's 2026 enlargement and Maryland's 2022 rename.
    Read a compiled table from its raw HTML or file, not through a
    summarizer, and check it against each state's own record and for
    changes since it was published before a map shows it.

51. **A member who cannot be placed is listed, never guessed.** Open States
    names districts as each legislature does ("10th Bristol", "Belknap 1",
    "10A"); the Census names them its own way. `statelegs.norm` reduces both
    alike and anything left over is reported and shown under "Not on the
    map" - New Hampshire's floterial seats, Maine's tribal representatives,
    each card naming the district it holds. A nearest-name match would put
    someone on the wrong district, and a map makes that look entirely
    normal. A seat with nobody listed is "nobody listed", never "vacant"
    (rule 19): its own legend entry and an outlined square in the seat
    strip, never folded in with Nebraska's nonpartisan seats. The cards
    printed every page Open States read - up to eighteen raw URLs, past
    sessions' pages, PDFs - and among them Rhode Island's roster links some
    twenty representatives to one colleague's page. A card links one
    `legislature.member_page`: a member's page on the legislature's own
    host, never a past numbered assembly's, or one whose address names
    another member and not them (rule 3), or another chamber or district.
    The first fix chose by host alone and linked 79 senators to their old
    House pages or another district's: Kentucky, Louisiana, Texas and
    Florida key a page by seat, so it shows whoever holds that seat now.
    Label the link as what it is - a bill list, a past session's page, a
    caucus's page, the chamber's list - and a district the 2026 record
    names for a special election is on the ballot, never "not up". A
    floterial seat is one RSA 662:5 makes floterial (`NH_FLOTERIAL`); any
    other unplaced name is unmatched. A portrait that is a search
    engine's thumbnail is not shown; one is dropped as missing only when a
    GET answers 404 or 410 (`statelegs.check_portrait`). Texas's host
    refused one machine every connection (rule 8), and HEAD lies:
    Massachusetts answers it 404 for portraits GET serves, and the first
    run called 211 working portraits missing.

52. **A rejection page is not a file.** The Census server answers a burst -
    and New Mexico's 2025 senate file, always - with "Request Rejected" and
    status 200. The downloader cached that page as the file, so every later
    run read HTML as a shapefile. `fetch_district_maps.get` refuses a zip URL
    whose body is not a zip and never caches it, and the legislative tool
    probes a file's first bytes before falling back to the 2024 release.

53. **Two sources of one count must agree, or neither is shown.** The
    county pages list 92,114 governments from the Census listing; the guide's
    local map counts them from the Census table. `localgov` refuses a listing
    whose count disagrees with the table for any state and type. Join a
    government to its county on the Census code, never the county's name,
    and show what the listing does not hold - who serves - as absent, not
    guessed.

54. **A majority of seats is not a majority that governs.** Counted by
    seats, as NCSL counts them, Alaska is a Republican trifecta; the
    Legislature's own roster lists a Republican as minority leader in both
    chambers, because coalitions of both parties run them. Control is
    counted from Open States and from NCSL separately and shown only where
    they agree; a seat with nobody listed counts for no one, so 67 of 134
    is not a majority. What the counts cannot show goes in
    `stategov.COALITIONS` with its evidence, and `build` warns once the
    seats stop fitting it - or once the members listed belong to a later
    legislature, read from the session in their own links. The NGA's roster
    page carries the NGA's own links and logo before its list: read only the
    list items, or Alabama's governor gets the leadership page and the logo.
    And the NGA's pages are themselves wrong about two governors' first day
    in office, so a date is shown only where Wikidata records the same one.
    The legislature pages showed Alaska's seat counts and a red map with no
    word of its coalitions, and split New York's Senate into six "parties"
    by fusion line. They now carry the state page's count, majority and note
    (`legislature._count` fails the build if the two disagree), count
    "Democratic/Working Families" as Democratic with its line named apart,
    and draw one square per seat, since an area map gives a chamber of
    dense city districts to its rural party (Minnesota's tied House).

55. **An association's roster is the authority on its members, and only
    on them.** NASS's member for Alaska, Hawaii and Utah is the lieutenant
    governor; NLGA's for Arizona, Oregon and Wyoming is the secretary of
    state. Where two rosters name one office's holder they must name the
    same person of the same party, or the page names both and shows neither
    (`officers.overlaps`), and "Acting" is the same office on either roster.
    An entry NASS marks "Currently Not a NASS Member" is not NASS speaking
    for its member: its Hawaii entry named a lieutenant governor NLGA's
    member had replaced. Compare
    names without honorifics ("Hon.", "High Chief"), strip invisible
    characters (one RAGA card carried a zero-width space, and two cards for
    one state then disagreed), and drop a card whose "name" is a state:
    RAGA prints "Maryland" and "Vermont" where it has no member. RAGA also
    lists a North Carolina attorney general who lost the 2024 election, so
    an attorney general's name needs the office's own confirmation.

56. **A name is confirmed where the office names it beside its title.**
    `officers.names_holder` takes the full name within 80 characters of the
    title, up to two middle words between first and last, or the title
    directly before the surname ("Attorney General Sunday"). It never takes a
    different first name: DAGA's "Tish James" is the office's "Letitia
    James" only through `NAME_FORMS`, an evidenced entry, because "Attorney
    General <anyone> Brown" on Utah's site could be Washington's Nick Brown.
    A site that refuses the request, or draws itself with JavaScript (fewer
    than 300 visible characters), concludes nothing (rule 8) and is tried
    again before the listing is shown as an association's, attributed.
    Text inside an HTML comment is not on the page: North Carolina's keeps a
    commented-out "Attorney General Josh Stein". And a name counts only
    directly beside its title - an 80-character window confirmed "former
    attorney general Treg Taylor" on Alaska's page, and a governor standing
    beside the attorney general.

57. **A court's members come from the court.** No national source lists
    sitting state justices, so `courts.COURTS` holds a recipe per court and
    `read_court` refuses a roster with more names than seats or two chiefs.
    Fewer names than seats is "nobody listed by the court", never
    "vacant" (rule 19). "Chief" is the chief: Arizona's Vice Chief Justice,
    Utah's and Washington's Associate Chief Justice and Kentucky's Deputy
    Chief Justice are not, and Utah's page, which names no chief since its
    chief justice retired, is shown as naming none. Recipes run
    case-insensitively, so a pattern that must see capitals scopes it
    (`(?-i:...)`): Montana's matched "is" and "was" as names.

    A page a plain request cannot read is not yet unreadable. Ten courts
    once showed nobody, among them New York's Court of Appeals. They are
    read now in four ways:
    - A page that draws itself with JavaScript, or answers only a
      browser, is read in a headless Chrome (`browser: True`,
      `tools/read_court_pages.mjs`). That Chrome uses its own headless user
      agent, and a page that answered with an error status is not read.
    - A PDF roster is read from its own text (`pdf_lines`), and the date it
      gives itself is shown. A move along a line joins text and adds no
      space: the first reader spelled "Keou gh" and "Taft -Carter".
    - A site that refuses every automated reader is read by hand from the
      court's page, in `overrides.COURT_ROSTERS`, with the day and the
      page's words quoted. It is checked like a read roster, and the page
      says "read by hand on" that day.
    - Only a court nobody can read stays in `UNREADABLE`, listed without
      members and never filled from Wikipedia or Ballotpedia.

    A run with no Chrome keeps each court's last good read (rule 8), and the
    build warns once a read, kept or by hand, is `courts.STALE_DAYS` old.
    Each read carries its own `read` day, kept with it: dated by the cache's
    `fetched`, which every run rewrites, a court that never read again
    would never have aged. A hand-read roster that does not fit its court
    stops the build (`curated_errors`), as a read one never reaches the
    page. A browser page is read only on the court's own host, a PDF line
    only as a name and nothing beside it, and any change in a court's
    members is reported (`changed`). Count what a new recipe reads against
    the page: Louisiana's first read five of seven, and Tennessee's missed
    a justice whose card linked his old court.

58. **A shapefile says its own encoding.** `read_dbf` decoded every layer
    as Latin-1, dBase's default, and the Census writes UTF-8 and says so in
    the layer's `.cpg`: "DoÃ±a Ana County" and sixteen Puerto Rico
    municipios were on the district, legislature and county pages for weeks
    with nothing failing. `read_layer` honours the `.cpg`, and
    `test_no_vendored_or_generated_file_carries_mojibake` fails on "Ã" or
    "Â" followed by a character from U+0080-U+00BF in any map or data file.

59. **A city is joined to its government only one to one.** The Census
    listing's place codes are not its boundary file's (Texarkana, Texas:
    68810 against 72368), so `counties.match_cities` joins on the name -
    within the state, never across one - and only where one place and one
    government share it, or, for a name shared, where one government of it
    is filed in the county the place's point lies in. Passes go from
    strictest to loosest over what the last left: name and legal form (the
    city and the village of Pewaukee, Wisconsin share a name and a county);
    name; name without the forms after it ("Phenix City" is the listing's
    "CITY OF PHENIX"). A place left unjoined is drawn and says so, the
    government stays under its county, and the build reports both. Never
    fall back to a town or township of the same name: the Village of Rib
    Mountain was incorporated in 2023 from a Town of Rib Mountain the 2022
    listing still holds, and joining them would show a dissolved
    government as the village's.

60. **A town or township is placed by its Census code, never its name.**
    For the 16,214 town and township governments the listing's FIPS_PLACE
    is the county subdivision's own code (`localgov` keeps it as
    `cousub`), and 16,167 of them are on a subdivision of that code.
    `counties.build_towns` joins on the code; the name is a cross-check
    (`same_town`), and a code whose names disagree, or one two governments
    claim, is reported and not drawn. The other 47 changed after 2022 and
    stay under their county: Wisconsin's Town of Madison was dissolved,
    and looking it up by name would have put it on the City of Madison;
    the Town of Rib Mountain's name now belongs to the village that
    replaced it. A city's FIPS_PLACE is not its boundary-file code
    (Texarkana: 68810 against 72368), which is why cities are joined by
    name (rule 59) and towns are not. Draw what a reader must find among
    thousands at a size that leaves room: Minnesota's 1,774 township rings
    at the cities' dot size covered its cities on a phone. A code is not
    enough on its own: the subdivision must be one the Census says
    governs (status A, B, C, G or I in its Gazetteer) - Mitchell, South
    Dakota's township is unorganized territory in every Gazetteer since
    2015 - and a town listed under another county than its subdivision
    (the Town of Pomfret, Connecticut) is reported as such, not as missing.

61. **A figure needs a source the page can name, and a curated row is two
    ids and a seat.** The 2026-10-13 audit found:
    - Three governors who never filed (Kemp, Beshear, Chris Sununu)
      listed as Senate candidates with round-number totals ("Raised
      $22,000,000.00").
    - Curated birthdates that disagreed with the person's own article in
      17 of 20 checked.
    - "~92% Party Loyalty" on 536 profiles, independents' included. It
      was 80 + 30 x |DW-NOMINATE|: one number derived from another and
      shown as a measurement.
    - Unsourced net-worth figures beside a disclosure link, as though
      taken from it.

    A curated row now carries its profile id (`ID`, so deleting a row
    renumbers no one; odds.json and the enrichment cache key on these
    ids) and the person's own filing (`FEC Candidate ID`). `validate`
    fails a row without either, a filing for another seat, and any money
    whose `financeSource` is not the FEC. The rows hold nothing else: not
    biography, platform or committees. Biography comes from the
    ballot-linked article (rule 38), net worth from nowhere (rule 26), and
    a label speaks only of what its status knows. A member with no
    primary line for their seat is "Not running for re-election", never
    "Not on the ballot": Byron Donalds is on Florida's, for governor. It is
    the same words whether the results list a retiring member as withdrawn
    or not at all - the two read differently side by side in the Senate
    view - and only the hover, which cites its source, differs; an
    appointee, never elected to the seat, is "Not running in 2026". A
    future year speaks of the seat: a senator's card says "Seat up in
    2028", never "On the ballot in 2028", because the data knows when the
    term ends, not who will run.

62. **A refused name match is not an absence, and an unsettled person is
    never counted on the ballot.** The results page writes people as they
    campaign ("Max Ganorkar", "Buddy Carter", "Lisa Carlquist") and the FEC
    as they filed ("GANORKAR, MAHESH", "LISA, CARLQUIST"). 36 such filers,
    six of them November nominees, were told "Not on the 2026 primary
    ballot". `results.apply_cache` settles a page name only when it is the
    filing's words in any order (unique among every filer in the race) or
    an alias in `overrides.RESULT_NAMES` evidenced by the campaign's own
    FEC committee. Anyone else whose surname, or a near spelling of it, is
    among the page's unmatched names is never called unlisted:
    - if every such name lost or withdrew, they are off the ballot either
      way and read "Not on the November ballot" (`raceStatusUnconfirmed`);
    - otherwise they are undecided (`maybeNamed`) and counted once, as the
      page's name.

    The first fix left 29 of them with no status, so the races counted
    people who had withdrawn (J.D. Scholten) as challengers.
    A nominee whose filing is under $5,000 is on the ballot all the same.
    `races.build` names them from the filing (`belowThreshold`), never
    twice for one person.

63. **A November result is read like a primary result, and not before the
    day after.** `results.general_held` opens the November table on the day
    after Election Day; a single marked winner is `elected` and the rest of
    that ballot `defeated`, and no mark or two marks change nothing.
    Georgia's general runoff (`overrides.GENERAL_RUNOFFS`) is a runoff table
    naming no party whose people were all on the November ballot - a June
    party runoff titled "Runoff results" holds a loser who never was. Who
    lost in November is not off the ballot and stays in view. A nominee
    with no result after Election Day reads "Awaiting result" as of the day
    the results were last read, never "On the November ballot" as though
    nothing had happened. The status words live in one table,
    `KYC.raceStatus`; five views each kept their own and every new status
    had to be taught to each. The 2026-10-17 audit found the same split
    again: a filer the results do not settle was "Ballot status not known"
    on a card, nothing in the dialog and "Challenger" on the map, and a
    member's run elsewhere read "Running for" after a loss. Every view now
    reads a person through `KYC.standing` (the table, plus an unsettled
    filer) and a member's other run through `KYC.contestLine`; a race's
    people come in one order, the pipeline's (`races.order_people`: the
    holder, then by surname), said under the race - the holder clause only
    when the list shown opens with one (`KYC.raceOrderNote`): under the
    Senate view's "Running for this seat" it named Barry Moore as
    Alabama's holder. A curated "another office's nominee"
    (`overrides.OTHER_OFFICE_NOMINEES`) is in the past tense from the day
    after Election Day (`KYC.otherOffice`), since this site does not read
    that race's result. The render suite builds pages on a frozen
    campaign-season clock (`CAMPAIGN_NOW`) and reads the data back as it
    stood then (`rewindToCampaign`), or every check that looks for a
    nominee would fail on the first called race and hold each refresh. And
    a row is read whole: the row pattern once ended at a nested template
    followed by a newline (`{{nowrap|N/A}}`), so the 2022 Georgia Senate
    page lost both runoff candidates' November rows and Warnock read as
    "withdrawn" - and five New Jersey nominees were missing in 2026. Within
    one race's page a misspelling a letter apart that never shares a table
    with its correct form is the same person (NM-1's "Okapareke" made the
    primary winner "withdrawn"), and a person is matched by any spelling
    the page gives them (ID-1's "Sarah Zabel Peterson" and "Sarah Zabel").

64. **An open primary's ballot is the state's list, and a list is not a
    result.** Louisiana's House seats vote first on November 3, so until the
    count the site showed every FEC filer: LA-2 read "3 filed, none past
    $5k" over a ballot of five. `results` reads the Secretary of State's
    qualified list (`kyc/qualified.py`) for such a seat. Its people are
    `qualified`, never "nominee", and a filer it does not name is not on the
    ballot. The export carries addresses, phones and emails; only the name,
    party, date and a withdrawal are kept. Its Outcome column has never held
    a result, so any other value is refused, not guessed at. A failed read
    keeps the last list read (rule 8), and a page that fails after the count
    never takes the list away. A status read from it credits the Secretary
    of State, never "the published results". After the count the results
    page decides, as everywhere else.

65. **A cycle's races are frozen, not re-derived from whoever sits.** A
    Senate seat was "up" because its senator's term ends at the election,
    so the Florida and Ohio special elections' winners, seated in December
    with terms to 2029, would have taken both races - and their results -
    off the site, and January 3 would have taken all of them. The race set
    is frozen once from the 119th Congress (`record --freeze`,
    `data/record_2026.json`, signature pinned in `cycle.RECORD_SIGNATURES`
    so a change is a reviewed code change); its incumbents are bioguide ids
    with every FEC id the source lists (`fecAll`, both chambers) and whether
    they were appointed. The surname table `SENATE_SEATS_UP_2026` is gone.
    The cycle is set by hand in `kyc/cycle.py` and nowhere else; the sitting
    Congress is the snapshot's, and the record phase begins only once it is
    the Congress the cycle elects and was read after noon on January 3.

66. **A departure is decided by id, from a record of it.** January 3 takes
    about a hundred members out of the snapshot at once, and the
    `departed-member` error would have failed every refresh from then on.
    The way out was `overrides.EXCLUDED_MEMBERS`, a list of names (rules 3
    and 17) whose three entries had already left the roster. Now
    `congress --apply` archives a member to `Former_Members.csv` only when
    `legislators-historical` lists their bioguide with a term ended by the
    day the snapshot was read (`legislators.departures`), on the day it
    gives. A term that has ended is not evidence on its own: on January 3
    every House term has, so a current file that dropped someone would
    archive them. Anyone else absent stays in the roster and fails the
    build (rule 16), and a failed download archives nobody. A new term
    rewrites the row's seat and dates (`reseated`) but never its party, and
    the term on a profile is the snapshot's, except Puerto Rico's:
    congress-legislators lists its four-year term one Congress at a time.
    Members are
    deduplicated on bioguide, not seat: a stale district and a newcomer
    seated at that number shared a key, and one vanished. Three days into a
    new Congress, a snapshot of the old one fails every build
    (`snapshot-behind`); the refresh runs daily from January 3 to 14 so
    that takes two missed runs, not one missed Monday.

67. **Who held a seat is the record's word; who sits now is `seated`.**
    Archived by rule 66, Florida's appointee would have vanished from the
    race she held: her member profile gone, her own filing excluded as an
    incumbent's, "35 Senate seats up" reading 34 - and the refresh failing
    every December day. A record incumbent who has left is a profile with
    the same bioguide id and `formerMember` (from `Former_Members.csv`), so
    every cache keyed on them still finds them; the term ends the day they
    left, and the archived status and committee seats are not shown. Every
    "who represents me" view counts with `record.seated` / `KYC.seated`,
    never `not isCandidate`, or a former member reads as someone's
    senator (rule 27). A race's `incumbentIds` and `incumbent` come from the
    record, and every record race exists whoever points at it. A member
    seated since Election Day for the term a race decided, in a seat they
    did not hold, is its winner (`raceRole`), never an incumbent, never
    "re-elected" - nor is an appointee; anyone else seated there since (a
    special for the rest of the old term, an appointment) is a successor,
    never the 2026 winner: TX-18's special and regular races had different
    winners in 2024. A record incumbent who won another seat keeps the one
    they held (`heldRaceId`), which is what the seats-up counts read.

68. **A new Congress is the data's word, about everything that changes
    with it.** Rehearsed on a fictional January 4 membership, the site
    would have gone on calling itself the "119th Congress" (typed into the
    templates), listed every re-elected member on their old committees
    (the roster's hand-typed column, and congress-legislators' rosters for
    the two weeks before it publishes the new ones), kept 2026 status notes
    on members past that race, and shown a new senator's House money as
    Senate money (`legislators._fec_ids` fell back to the other chamber's
    ids; Ashley Hinson's Senate filing is missing upstream). So: the
    Congress number is `cycle.snapshot_congress`, printed by the pages from
    `kycBuildMeta.congress` into `[data-congress]`; committee rosters are
    shown only while their members sit (`committees_current`) and the
    curated column only while the 119th does, otherwise
    `committeesPending` says the new rosters are not published yet;
    leadership posts count only when their record began in the sitting
    Congress (`legislators.held_posts`, checked at build time), because
    congress-legislators leaves the old Congress's Speaker and leaders
    open-ended and a re-elected Speaker passes every "seated" test; a
    status note stops at a new term; a member has only their own chamber's
    FEC ids, with any upstream lacks in `overrides.MEMBER_FEC_IDS`, and
    `member-candidacy-id-missing` lists the next one. Tests that describe
    the campaign say so and skip after it; the rehearsal is the scratch
    generator plus `congress --apply --snapshot`, never committed. Their filing is folded in only by the FEC id Congress's
    record lists for them, a curated row's id kept as `otherIds`; without
    that id both profiles stay and `seated-unlinked` says so (rule 25).
    The federal page's line of succession meets the leadership posts' test:
    congress-legislators records a Speaker's and a President pro tempore's role with no end
    date, so on January 3 the 119th Congress's would have stayed second and
    third in line until the file caught up. A role that began before the
    snapshot's Congress did names nobody, and the build says so
    (`federal_build.congressional_officers`, `succession-unnamed`).
    Linking is not folding: a sitting member's filing for the other chamber
    is found by any id Congress's record lists for them (the roster's
    "Garland Barr" never met Andy Barr's Senate filing), and the member's
    profile then says "No House filing" and shows that campaign's totals
    under its own office and FEC id, linked to its profile - never "No
    filing this cycle" for someone who raised millions for another seat.

69. **An office held is shown where two sources agree on it.** Wikidata's
    "position held" is the only free record of state and local offices,
    and on a first read it put Ben McAdams in the mayoralty of Salt Lake
    City (he was the county's mayor), Steven Horsford in the Nevada
    Assembly (the Senate) and Darin LaHood in the office of U.S. Attorney
    (he was an assistant). `kyc/history.py` shows an office only where the
    person's own article - the item's sitelink, never a search - gives the
    *same office* the same years; the first version compared years alone,
    and a U.S. Senate term "confirmed" Jeanne Shaheen's state senate seat.
    The article's infobox is read block by block: a long career keeps its
    earlier offices in embedded `{{Infobox officeholder|embed=yes}}`
    sections that number their fields afresh, so merged into one they
    paired one block's office with another's years. What disagrees is
    withheld and reported (`history-withheld`), never chosen between.
    Congress comes from congress-legislators alone. A challenger's item is
    the one their election page's article belongs to (rule 33), and the
    offices attach only while the profile still links that article
    (`history-stale`). A record that cannot be read is "No linked record",
    never "none" (rule 19). The review of the first build found more an
    agreement on office and years does not catch, each now refused:
    Wikidata puts the Jefferson County Judge/Executive in Oklahoma, so
    Mitch McConnell's Kentucky office read as Oklahoma's (a place below a
    state is shown only in a state the person is tied to,
    `history-place`); a span across a redistricting kept its first
    district (it names none now); a position's article can be a list
    ("List of governors of Colorado"); "Nebraska Legislature" stood for
    any chamber, so a House abolished in 1937 was "corroborated"; and
    "since 2013" was frozen at the read, so a senator who left on January
    3 would have stayed current. Whether a seat in Congress is current is
    the membership snapshot's to say, by the person's bioguide id, at
    build time (`history-behind`).

70. **A disclosure belongs to an office, and the report must name its
    filer.** The Office of Government Ethics files people under their
    legal names ("Turner, Eric Scott" is Scott Turner), so `kyc/oge.py`
    attributes a row by the office - OGE's agency and position for it,
    in `oge.OFFICES`, compared without case and past OGE's record number
    ("Director 2") - with the holder's surname as a cross-check; two OGE
    names of that surname on one office are refused (rule 25). The
    holder's other rows in the same agency under the very same OGE name
    are theirs (Todd Blanche's annual report is filed as Deputy Attorney
    General). Only a file OGE serves is linked, never the request form.
    Each report OGE generates names its filer under "Filer's
    Information", and is opened: on the first read Robert F. Kennedy
    Jr.'s transaction report wrote "Kennedy Jr, Robert F" against the
    index's "Kennedy, Robert F", and the check refused his own report
    until a suffix stopped counting as a surname. A report that names
    someone else is not linked; a scan (the President's and the Vice
    President's reports are) concludes nothing (rule 8) and is linked and
    marked "not checked". A holder with no row reads "OGE's index lists
    no report", never "not filed" (rule 19). A report's "Present" is the
    day it was filed, not today's (rule 69's "since 2013"): the page dates
    it, and a post that is the office the person now holds ("Acting
    Attorney General" for the Attorney General) is not "another post".

71. **A map that draws a county the counts say has no government says
    why.** The counties directory and the guide's map read "none" for
    Rhode Island's county governments while its own page drew five
    counties and listed governments in each, with no word on why; New
    York's page read "0 local governments" for the Bronx, Brooklyn,
    Queens and Staten Island, whose governments the Census files under
    Manhattan. 112 county areas have no county government of their own.
    `kyc/county_areas.AREAS` holds each by its Census code, from Appendix
    A of the Census Bureau's 2022 Individual State Descriptions, with the
    government that does its work as the listing names it. The build fails
    on an area with no county government that the table does not explain,
    and on an entry whose area has one, is renamed or gone, or whose
    government the listing does not hold (rule 53). The county page, the
    directory's numbered notes and the guide's map all take their words
    from that one table, and a state's page calls its areas what the
    state does: parishes, boroughs and census areas, planning regions.

72. **One campaign is one person, whatever names it filed under.** Six
    candidates registered twice for one committee under two name forms
    ("Dan" and "Daniel Miressi"); the name-keyed fold never met them, so
    each appeared twice in their race and was counted twice as on the
    ballot. `candidates.registrations` also joins filings whose Form 1
    names the same committee (`committeeOf`, from the campaigns cache)
    when the money is the same to the cent; equal money alone never
    joins anyone. One committee and the very same filed name, letter for
    letter, join whatever the money: Arthur Grahame Purves registered three
    times for PURVES FOR CONGRESS as "PURVES, ARTHUR GRAHAME MR.", one
    registration's totals also counted a second committee, and VA-11 listed
    him as two Republican nominees. Filers off every ballot have no
    committee in the campaigns cache, so a pair like Broden's in FL-1 is an
    evidenced `SAME_PERSON_FILINGS` entry, and `validate` warns on two
    profiles under one name in one race (`same-name-in-race`). A race's
    "filed in total" counts the person once too (`filing_counts` folds the
    same registrations), or VA-11 read 22 filed with Purves three times. A
    results-page name that was ambiguous only between one person's
    registrations is theirs (`results._claim_unmatched`).

73. **A count is one formula, wherever it is shown.** The sidebar read
    587 challengers on the ballot, a state's strip 16 over race headers
    summing 58: the headers counted the people the results name with no
    profile, the rest did not. Every "on the ballot" figure is now the
    races' own sum (`summary.by_state`), and a figure that reads as what
    it is not carries its note from one table (`government_maps.COUNT_NOTES`).
    Say what a second source checks: "checked against NCSL" was read as
    covering the seat counts, when only control was compared.

74. **A status word must describe the race it badges, and what that race
    decided.** California's and Washington's top two and Alaska's top
    four advance whatever the party (`results.ALL_PARTY_PRIMARIES`), so
    no one there "won the primary" or was "renominated". A member running
    under a new district number is not leaving (`renumbered`, and the
    seat they hold says `holderMoved`); one who ran there and lost is.
    A race-mate's status is about the race it came from: Kevin Kiley was
    "On the ballot" in CA-3, which he holds and is not running for. A filer
    the results do not name after the primary is `ballotUnknown`, never
    "the primary has not been held yet", and is not counted as on it.

75. **Write a place's own words.** A territory or D.C. is never "the
    state"; a legislature carries the name its constitution gives it
    (General Assembly, General Court); a judge's name is shown without the
    directory's brackets. A section's name comes from one helper shared by
    its heading and its jump chip, and a page has one name in the
    navigation, its title and the links to it. The tag beside the site's
    name is the section's (`pages.brand_sub`, from the navigation's labels):
    "U.S. Congress" stood over 219 pages about counties, courts and the
    guide, and only a page that loads profiles.js names the Congress. Where a city's name join
    cannot work, a place is joined to a government only through the
    listing's own id (`overrides.PLACE_GOVERNMENTS`, with its evidence) or
    the government `county_areas` names, never to a town it replaced.

76. **A page and the code it runs are one version.** GitHub Pages serves
    every file for ten minutes, and a reload refetches the page but keeps
    scripts still in cache: minutes after a deploy, the new index.html ran
    the previous kyc-directory.js, which threw looking for the sort's old
    `<select>`, so the new sort menu did nothing and the grid sat on
    "Loading profiles..." until a chip was clicked. Every local script and
    stylesheet URL carries `?v=` and its file's content hash
    (`kyc/assets.py`, line endings folded): generated pages are stamped as
    they render, the build restamps the templates, and `verify` fails on a
    stale stamp. The data files the code reads are stamped too, by their
    content signature (so a rebuild of the same data restamps nothing,
    rule 18) - all but `data/odds.js`, which the odds job may change alone
    (rule 41). And no one part of a page's start may stop the rest: the
    grid's start-up runs each step and its first draw on their own, draws
    what it can, and says on the page that something failed.

77. **Once a state certifies its November candidates, its list is the
    ballot.** A results page says who won a primary, not who is printed in
    November. Audited on 2026-10-17, Alaska's at-large seat showed two
    people on the ballot over a certified four, and called the two it left
    out "withdrawn": four other top-four finishers had withdrawn and
    promoted them. Alaska's certified Daniel J. Sullivan Jr. read "Not on
    the 2026 primary ballot", thirteen qualified Florida candidates and
    every Colorado minor-party and unaffiliated candidate were missing, and
    American Samoa, which holds no primary, read "0 challengers on the
    ballot" over six certified names. `kyc/certified.py` reads each list a
    script can (Alaska, Florida, Colorado, American Samoa, Texas); a PDF
    list is transcribed in `overrides.CERTIFIED_BALLOTS` with its document
    and the day it was read. A party's list of its own nominees is not a
    ballot: the state may refuse them. `results.certify_race` lays a list
    over the page: whom it prints is on the ballot whatever the page said
    ("On the November ballot", never "Renominated": a list is not a
    primary); where it is the whole ballot, a filer it does not name is not
    on it, unless a name it prints, or names unprinted (a write-in,
    Florida's unopposed), that matched no filing may be theirs. Names are
    matched as a results page's are (rule 62), with an apostrophe inside a
    surname kept ("D'Arrigo") and a surname written with a space or a
    hyphen one spelling ("Kim Varet", "Kim-Varet"), or one person's two
    spellings on a page fit one filing twice and it reads "ambiguous" -
    as New Jersey's "Natalie Rivera" and "Natalie Lynn Rivera" did, under
    two headings' Withdrawn lists that the parser had gathered into one
    "table" (it splits them back now). The name shown is chosen by its
    source: an exact or evidenced match, a list's name for anyone it holds,
    printed or not (Florida's "Yen Bailey" lost the primary; never a name
    in capitals), and a page's only for a hyphen or a short form of the
    filed first name. A person's article is the one a piped link names
    over a bare link's redirect (NM-3's "Martin R. Zamora"). And a county
    convention awards a ballot line, not a nomination: losing one never
    outranks a Withdrawn list - six New Jersey filers who withdrew before
    the primary read "Lost the primary". When the matcher began
    settling names that used to be claimed, the Florida Senate nominee lost
    "Gillespie" to the FEC's misspelling, and a page's "Matthew" replaced a
    campaign's "Matt". A list's name keeps what it prints: Florida's
    "Arias, V. Michael" has a first initial, not a suffix ("Michael Arias
    V." was shown), and a suffix is no surname to the look-alike check of
    rule 25, which lost Alaska's two Sullivans when one became "Daniel J.
    Sullivan Jr.". A certified write-in is not printed, and is not read
    as on the ballot or as left off it. Rule 64's limits hold: only the
    name, party, office and what the list says of the person are kept, and
    a failed read keeps the
    last list. Short of a list, a minor-party or unaffiliated filer missing
    from a page's November table is "ballot status not known", never off
    the ballot: those tables are copied from the major parties' primaries.
    And a primary winner missing from the November table beside a name a
    letter from theirs ("Gegen", "Gegan") is undecided, never "withdrawn";
    a seat whose primary was not its state's (Alabama's four August
    districts) carries its own date in `overrides.SEAT_PRIMARY_DATES`.

78. **A public body's website is checked before it is linked, and a
    move is kept only where the new page names the body.** The county
    pages linked the 39,452 websites in the Census's 2022 listing
    unchecked: Clinton, Connecticut's opened a slot-machine demo,
    Vermilion Parish's SBOBET88, Bismarck's a parked page, Switzerland
    County's a GoDaddy for-sale page - under each government's name.
    `localgov --check-sites` (`kyc/localsites.py`) opens every address,
    one request at a time per host and redirects followed by hand with
    cookies (a `window.location = "/lander"` page is parking, rule 39),
    and writes `data/local_sites.json` with the day and the evidence. The
    build withdraws gambling, parked, for-sale and expired pages, a page
    gone twice (404, 410), a host NXDOMAIN or without an address here and
    at both dns.google and Cloudflare (rule 35), and a cross-host redirect
    to a page whose title and address carry no word of the body's name, or
    to a business's page (a chamber of commerce, an estate agent, a funeral
    home); the line says why and when,
    and every other link says it is the Census's 2022 address and when it
    was checked. A 403, 429, 5xx, timeout, sign-in or bot wall, a server's
    placeholder page and a SERVFAIL (a lame delegation) conclude nothing
    (rule 8). "Names the body" is its distinctive words *and* a word for
    its kind in the title ("Pettisville Schools"), its whole name as a
    phrase, or a `.gov` host: the first full run withdrew 115 moves as
    "elsewhere", most of them school districts and authorities on new
    domains, because it asked a title for the listing's full name - and
    for the listing's abbreviations ("Ind", "Sch") as if they were words of
    it. A place's name alone is not enough: Alma's address opens its
    chamber of commerce, Haverhill's an estate agent's listings. The
    second run went too far the other way: the page said "now leads to a
    site that does not name it" of Las Virgenes Municipal Water District's
    own lvmwd.gov, because the listing misspells it "Muncipal", and of the
    Bartlett Fire District, the DesPlaines Valley mosquito district and
    the Hoosic Valley schools. A word one slip from the listing's spelling,
    or two words run together, now count; a page that names any part of
    the body is not confirmed (`unread`), never claimed not to be it. And
    48
    checks at once dropped about 4,700 lookups at this machine's resolver
    that dns.google answered: a local failure is looked up again before
    it is believed. Gambling seen plainly (a title, a redirect target,
    a page full of it) is never cleared by a later run; one match in a
    page's text is withdrawn and waits for a person, because "Schedule your
    slot online" on the Keansburg schools' blood-drive notice and "Secure
    your 15-minute slot online" on the Landfill of North Iowa's were
    shipped as gambling sites, for good. A person's finding goes in
    `overrides.BLOCKED_LOCAL_HOSTS`. A look that concludes nothing never
    undoes a withdrawal (`merge`). Domains keep lapsing (rule 39): the
    weekly refresh looks at 6,000 addresses a run, oldest first, and the
    build warns about any not looked at in 60 days. As of 2026-10-18, 7,366
    of 39,447 governments' links are withdrawn: 5,090 dead, 1,179 gone,
    351 for sale, 255 gambling, 254 parked, 208 elsewhere, 20 expired and
    9 a business's; 5,269 could not be confirmed and stay linked, marked
    so.

79. **A mark about an office sits on the office, and "not running" is a
    source's word.** "On the Nov 3, 2026 ballot" sat under Brian Kemp,
    Gavin Newsom, Tim Walz and every officer whose office is elected, in the
    style the race badges use for people; it read as a fact about each, and
    none of them is on that ballot. The mark says "This office is on the
    Nov 3, 2026 ballot" and sits on the office's label line, never in the
    holder's block. Who is not running is said only where a cited source
    says so (`ballot2026.OPEN_SEATS`): the constitution's term limit, read
    with the NGA's count of the governor's terms, or the election office's
    certified list for that office - never news, and never a term limit for
    anyone else, since a term-limited officer may be on the ballot for
    another office. `stategov` withholds an entry whose holder has changed.
    Every other office on the ballot says by name that this was not checked
    (`holderStatus` "unchecked"): silence beside Georgia's governor, with
    "Open seat" beside Alaska's, read as "Brian Kemp is running" (rule 19).
    A voting link is credited to its own source, link by link - "the first
    four from NASS" credited NASS with eleven curated sample-ballot pages -
    and "each link opened" is said only of links found live.
    A next election year is a statute's or the state's record's
    (`ballot2026.NEXT`), never a term length's: Virginia's governor was
    elected in 2025 and is next elected in 2029, its legislature in 2027.
    The same goes for a market: a party-only market over a ballot of two
    Democrats, or last prices that add up to 128%, is quoted with a note
    saying what it cannot tell, read page-side so `data/odds.js` stays the
    cache's (rule 41).

82. **Who sits on a court is two sources' word, said side by side, and what
    has not happened is in the future tense.** The 2026-10-17 audit found
    the Eastern District of Tennessee counting Judge Varlan active - the
    FJC's directory had not recorded the senior status uscourts.gov's
    vacancy list dated 2026-10-05 - so five active judges and a vacancy
    filled a five-seat court. A judge the courts' list has on senior status
    by a date on or before its own as-of date is counted senior, and the row,
    the dialog and the hub say which source says what
    (`vacancies.listed_senior`); neither is picked silently. The announced
    list is the future: "Will take senior status", "Nominated to the Fifth
    Circuit" - never "Took senior status" or "Appointed to another court"
    for three district judges who were only nominees. A confirmed judge
    with no commission is listed apart and counted nowhere. A judge's
    portrait and article come only through the FJC's own canonical slug
    for their `nid` and the Wikidata item carrying it (P2736), the item's
    label and the article's title checked for the surname and its year of
    birth for the directory's (`kyc/judge_links.py`); never a name search.
    An id is not proof on its own: Wikidata carried Judge Robert H.
    Whaley's FJC id on the basketball player Robert Whaley, born 1982, and
    the surname check passed his photograph and article; fourteen more
    items' years disagreed with the directory's on the first full read.
    What disagrees, or cannot be checked, gives nothing; a size Commons
    did not answer for keeps the last portrait read of the same file
    (rule 8). A vacancy's judge is found on its court by surname *and*
    first given name (`vacancies.judge_of`): two of the list's departing
    judges are not in the directory, and a surname alone would have moved
    a colleague of that name to senior status. The
    territorial courts'
    judges, whom the directory does not hold, come from each court's own
    site through a recipe that refuses more names than seats or two chiefs
    (`kyc/territorial_courts.py`, rule 57). And a count of judges by
    appointing President is a count of Presidents, in `--cat-*` colours,
    never a party's.

84. **A date a reader acts on is the office's own, and is said passed on
    the reader's day.** Seventeen days before the election every state page
    offered "Register to vote" - Georgia's twelve days after its deadline -
    and gave no early-voting or mail-ballot date, because typing dates in
    was refused as drift. Each jurisdiction's dates are now a hand-edited
    cache, `data/voting_dates.json`, read from the election office's own
    pages, calendars and statutes and re-opened by a second reader. Every
    value the page shows carries its page's address and words
    (`voting_dates.SHOWN`; a time of day may stand on its date's source,
    but "postmarked" or "received" only on a quote that says it), on the
    jurisdiction's own domains (`JURISDICTION_DOMAINS`) or an evidenced
    entry in `OFFICIAL_ELSEWHERE`: being on .gov is not enough, since
    another state's office, a county and a federal guide all are. A
    compiled table is refused wherever it appears (rule 50), vote.gov,
    fvap.gov and usa.gov included, and vote.gov's deadlines page is not
    shown beside the state's own dates (rule 53). Where a reader can
    register and vote at once, a deadline before Election Day is the
    regular one, never "the last day" or "open until": the first page told
    Illinois readers on October 18 that it was the last day to register,
    with grace-period registration open to November 3. Where the record
    does not say whether there is same-day registration, the page gives
    the deadline and claims nothing more. Where same-day registration
    happens is the office's words, quoted and checked against a cited
    quote; the researchers' summary had been shown. A date the office
    gives as a rule ("15 days before the election", Guam's runoff on "the
    fourteenth day" after it) is that rule counted on the calendar, and the
    page says so; a counted date that lands where the office cannot act
    (D.C.'s in-person deadline, a Sunday) is not shown. A December date the
    results reader also holds must be the same date in both. The pipeline
    writes the words; the page only decides, on the reader's own calendar
    day, which have passed: "Register to vote" then says when it closed,
    and from the day after the election only a ballot still arriving and a
    runoff stay, the runoff in the past tense once gone (rule 63). A null
    is a gap and says nothing; a researcher's note is never shown. A
    runoff says what it decides (`RUNOFF_WORDS`): Arkansas's December 1 is
    not a runoff for Congress. The cycle's dates are reread each cycle, and
    `check` refuses a date outside it.

86. **A member's biography is a source's words, and says which.** The
    rosters' Education, Previous Professions and "Policy Focus & Platforms"
    columns were typed with no source and reached 537 member profiles
    unbadged, in uneven words: "Anti-abortion legislation" for one member,
    "Pro-life advocacy" for four others (TRUST-05). `profiles` never reads
    them, and `validate` fails any education, careers or platform without a
    source the page badges (`bio-unsourced`). `kyc/members.py` fills them by
    id: education and careers from the Congressional Directory, joined on
    the office web address congress-legislators lists for the bioguide id
    and cross-checked against the printed surname (the Biographical
    Directory answers a script 403 and headless Chrome a Cloudflare
    challenge); education or an occupation from the infobox of the article
    the id maps to where the Directory has none; the platform from the
    official site's own issues list, one level, in its words, never a line
    naming the member or anyone else ("Trump's One Big Beautiful Betrayal"
    is a banner under Van Hollen's issues path). An "On The Issues" link
    can lead to a page whose children are a voting record (Matsui's
    /legislative-work), so pages filed under an issues path win. A link
    is labelled by its first block of words: Cruz's issues are cards, and
    read whole "Tax Reform Promote jobs, growth, and opportunity" passed as
    an issue while the cards with longer blurbs were dropped, a partial list
    that looked whole. The House template's furniture filed under Issues
    (Community Project Funding, Legislative Process, Bill Search) is not an
    issue. A site read that lists none is "Not listed on their official
    site", never "No data" and never the typed text; a refusal concludes
    nothing until headless Chrome has tried (rule 8). A contact page is
    linked only once a fetch shows a form to write with, or the House's
    shared form framed on the member's page: a soft 200 is not one. A
    challenger's dialog leads with the race, then the money, the platform
    and the biography, and its absences are said once (PROFILES-18).
    The review of the first build found more, each now refused or said:
    the House template's stock categories ("Congress; Economy; Education;
    Energy; Health; Veterans", each "news and information related to")
    were eighteen members' platforms while Figures's identical page read
    "Not listed", so a list of nothing but those links the page, for
    everyone (`stock_list`), and "Congress" is never an issue - a page
    listing them among the member's own is quoted whole, since Schrier's
    gives both the same card and blurb and nothing tells a default kept
    from one chosen; a home page is never called "their issues page"
    (Stansbury's was), and too few issue pages linked from it read "On
    their official website" (`see_home`); a heading
    broken by `</br>` was cut to "Sponsored &", and a line ending in "&" or
    a comma is not taken; one issue spelled twice is listed once; a home
    page's own issue links were shown as the list when Hoyer's unlinked
    /issues held nine to its five, so `/issues` is tried first and a home
    page's links are said to be what it "features" (`platformFeatured`); a
    newsletter form (Aguilar's, Mfume's) is not a way to write, and a
    name and an email alone never make one; the Directory printed no ";"
    before Graves's and McConnell's "election history", which ran into
    their careers; an address it prints that leads to the member's listed
    site (dingell.house.gov) joins, and members it does not hold are
    reported (`members-directory-unjoined`), never left silently blank.

## District maps

`kyc/districts.REDRAWN` lists the states whose 2026 House map differs from
2024's. It is an editorial judgement checked against primary sources, not
something the data can show: Missouri passed a map and is not on it, because
a referendum petition suspended the map and the courts kept the old one.
Before adding a state, confirm the enacting record and that the plan is in
effect, and point `shapefile` at the state's own file. `tools/fetch_district_maps.py`
refuses a projection it cannot undo, and a file with any point outside the
state.

## Curated data

`kyc/overrides.py` holds every editorial judgement. Keep the CSVs authoritative
wherever they are correct and keep this file small.

`validate.py` reports overrides that no longer match anything. Take those
warnings seriously — a stale override is invisible in the UI but quietly wrong.
That check found a retirement note keyed `"Dick Durbin"` when the roster says
`"Richard Durbin"`, so his retirement never displayed.

## Front-end conventions

- One stylesheet (`assets/kyc.css`) and one behaviour module per concern in
  `assets/`. Nothing duplicated between the two pages; neither page has an
  inline `<script>` but structured data (`application/ld+json`).
- Colours come from CSS custom properties (`--party-d`, `--money-in`, …), never
  hex literals, so all three themes stay consistent. The map's continuous
  House scale uses `color-mix()` against those same properties, which is why
  changing theme recolours it with no repaint.
- Class names describe the thing (`.card`, `.chip`, `.field`), not its
  appearance. Sizes come from the `--s-*` and `--t-*` scales.
- Anything user-visible from the data goes through `KYC.renderField` or
  `KYC.escapeHtml`.
- Icons come from the sprite in `kyc.js` via `KYC.icon(name)` or
  `<use href="#i-name">`.
- Every view needs a URL. Use `KYC.router`.
- New dialogs use `KYC.createModal` so they get the focus trap for free; new
  menus use `KYC.createMenu` so they are keyboard-operable.
- Headline figures come from `window.kycBuildMeta`, never typed into a page.
- A federal official is never a profile. They open in `KYC.official`
  (`kyc-official.js`) at `#/official/<id>`, with ids `x-<name>` and
  `fjc-<nid>`, and nobody there counts as a member of Congress. A judge or a
  Cabinet officer is shown without a party; a judge with the President who
  appointed them.
- A page's own code goes in `data-state` only when it is a state:
  `kyc.js` remembers it as the reader's state. A court page carries its id
  on its container (`data-court`).

## Conventions

- Standard library only in `kyc/`.
- Normalisation helpers are total: they accept `None`, `"nan"`, `""` and always
  return something display-ready.
- Add a regression test for any data bug fixed — `tests/test_pipeline.py` for
  core parsing, `tests/test_enrichment.py` for provenance/portraits/FEC/races,
  `tests/test_geo.py` for map geometry, `tests/test_districts.py` for the
  before-and-after district maps, `tests/test_frame.py` for the site's frame (about, 404, footers, header tags), `tests/test_site.py` for summary
  figures, emitted files and page wiring, `tests/render_test.js` for anything
  visible on a page.
- When changing profile fields, update the field tables in `README.md`.
- Builds must stay reproducible under `SOURCE_DATE_EPOCH`, for `geo.js` as
  well as `profiles.js`.
- Do not hard-code a total that the data determines. A test asserting `472`
  races carried a comment reading "435 + 6 + 35", which is 476; nobody had
  reconciled the two, and the number moved the moment a vacant seat was
  filled. Assert the structure and account for the difference.
