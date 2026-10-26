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
lookup_maps/*.json          ──┤   (ZIP code areas' shares, finer lines for a location; tools/fetch_lookup_maps.py)
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
data/legislator_photos.json ──┤   (portraits Open States lacks, from each legislature: kyc/legphotos.py)
data/executives.json        ──┤   (every governor, from the NGA)
data/statewide_officers.json ─┤   (lieutenant governors, secretaries of state, attorneys general)
data/courts.json            ──┤   (each state's highest court, from the courts)
data/voting_links.json      ──┤   (each state's official voting pages: NASS Can I Vote)
data/voting_dates.json      ──┤   (each jurisdiction's key dates, from its own pages: hand-edited, kyc/voting_dates.py)
data/statewide_candidates.json ┤  (who is on the ballot for governor and the statewide offices: hand-edited, kyc/statewide.py)
data/statewide_photos.json  ──┤   (those candidates' photographs, by the routes rule 91 names: ballotphotos)
data/guide_photos.json      ──┤   (the election offices' guides' photographs, hosted under photos/: guidephotos)
data/ballot_measures.json   ──┤   (each jurisdiction's statewide questions, from its own list: hand-edited, kyc/ballot_measures.py)
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
data/roll_calls.json        ──┤   (every roll call of the Congress: House Clerk, Senate LIS; votes)
data/record_2026.json       ──┤   (the frozen 2026 race set: record --freeze)
data/seat_history.json      ──┤   (each seat's last election: the Clerk's statistics, checked; seats)
data/outside_spending.json  ──┤   (independent expenditures by candidate: FEC Schedule E; outside)
data/departed_members.json  ──┤   (who left this Congress: congress, from legislators-historical)
data/photo_copies.json      ──┤   (each heavy portrait's original and its copy, and each photograph hosted here: rule 101)
data/partisan_composition.json ┴─> kyc/ ──> candidate_profiles_site/
                                             data/people/meta.js (the build's figures and signature)
                                             data/people/index.js (everyone's cards and search fields, every race)
                                             data/people/*.js   (one state's whole records and races; rule 94)
                                             data/geo.js        (SVG path data for the map)
                                             data/odds.js       (market prices, polling averages)
                                             data/government.js (the guide's maps: kyc/government_maps.py)
                                             data/stategov.js   (governors, chamber control, trifectas)
                                             data/measures.js   (the statewide questions: kyc/ballot_measures.py)
                                             data/search.js     (the search's places and bodies: kyc/search_index.py)
                                             data/legislature/*.js (one state legislature per state)
                                             data/local/*.js    (one state's counties and governments)
                                             data/courtcounties.js (each county's federal district court)
                                             data/districts/*.js (one district map per state)
                                             data/lookup/*.js   ("Find who represents you", one per state, and the index: kyc/lookup.py)
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
                                             data/votes/*.js    (each chamber's roll calls, loaded by the profile dialog on demand)
                                             about.html, 404.html (generated: the site's frame, kyc/pages.py)
                                             ballot.html        (generated: Your ballot, drawn by kyc-ballot.js)
                                             districts/index.html, courts/index.html (generated directories)
                                             p/*.html, r/*.html (generated share pages: one per profile and race, kyc/share.py)
                                             photos/*.jpg       (smaller copies of heavy portraits, by hash: photocopies)
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
                                             assets/kyc-search.js
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
                                             assets/kyc-share.js
                                             assets/kyc-findrep.js
                                             assets/kyc-ballot.js
```

- The root CSVs are the editorial source of truth. The state atlas and
  `congress_snapshot.json` are vendored inputs: refreshed by a command, never
  hand-edited. So is `district_maps/`, written by `tools/fetch_district_maps.py`
  from Census boundaries and each redrawn state's own enacted-plan file.
- Everything in `data/` is **generated**. Never edit `people/*.js`, `geo.js`,
  `odds.js` or `districts/*.js` by hand. `portraits.json`, `finance.json`, `fec_field.json`,
  `disclosures.json`, `primary_results.json`, `committees.json`,
  `campaigns.json`, `enrichment.json`, `odds.json`,
  `census_governments.json`, `state_legislators.json`, `legislator_photos.json`, `executives.json`,
  `partisan_composition.json`, `statewide_officers.json`, `courts.json`, `voting_links.json`, `voting_dates.json`,
  `statewide_candidates.json`, `statewide_photos.json`, `guide_photos.json`, `ballot_measures.json`,
  `federal_executive.json`, `judiciary.json`, `judicial_vacancies.json`,
  `judge_links.json`, `court_districts.json`,
  `political_history.json`, `oge_disclosures.json`, `tribal_leaders.json`, `local_sites.json`,
  `seat_history.json`, `outside_spending.json`
  and `departed_members.json` are caches, but
  they *are* hand-editable. `stategov.js` is generated from the last five,
  with `kyc/ballot2026.py`: which state offices and legislative seats are on
  the 2026 ballot, a curated table citing each state's own record.
  `members.json` (`members`, rule 86) is a hand-editable cache too.
  `roll_calls.json`, written by `votes`, is a cache too; `data/votes/*.js`
  is generated from it alone.
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
python build_profile_site.py legphotos       # their portraits Open States lacks, from each legislature's own records
python build_profile_site.py localgov         # every local government (Census listing), checked
python build_profile_site.py localgov --check-sites  # open every listed local website; resumes (rule 78)
python build_profile_site.py executives       # every governor (NGA), and NCSL's party counts
python build_profile_site.py officers         # lieutenant governors (NLGA), secretaries of state (NASS), attorneys general
python build_profile_site.py courts           # each state's highest court, from the court's own roster, and its justices' photographs
python build_profile_site.py ballotphotos     # the statewide candidates' photographs (official guides, members, the race's Wikipedia article)
python build_profile_site.py guidephotos      # the election offices' guides' photographs (WA voters' guide, AK and OR pamphlets), hosted here
python build_profile_site.py voting           # each state's official voting pages (NASS Can I Vote)
python build_profile_site.py federal          # the President, VP and Cabinet (White House, office pages, Senate roll calls)
python build_profile_site.py judiciary        # every sitting federal judge (FJC) and the Supreme Court as the Court lists it;
                                              # the territorial courts' judges from their own sites; judges' Wikidata links
python build_profile_site.py judiciary --links-only  # only the judges' articles and portraits (rule 82), for the committed directory
python build_profile_site.py vacancies        # vacancies in the federal courts, as uscourts.gov lists them
python build_profile_site.py history          # public offices each person has held (congress-legislators, Wikidata, Wikipedia)
python build_profile_site.py oge              # the executive's financial reports (Office of Government Ethics), by office
python build_profile_site.py members          # members' education and careers (Congressional Directory), platform (official site), offices
python build_profile_site.py tribes           # every tribal government and its leader (BIA Tribal Leaders Directory)
python build_profile_site.py votes            # every roll call of the Congress (House Clerk, Senate LIS); resumes (rule 89)
python build_profile_site.py seats            # each seat's last election (the Clerk's statistics; checked against MIT or Wikipedia)
python build_profile_site.py outside          # outside spending for and against each candidate (FEC Schedule E, by candidate id)
python build_profile_site.py photocopies      # weigh every portrait shown outside Wikimedia; copy the heavy ones in headless Chrome (rule 101)
python tools/fetch_legislative_maps.py        # state senate and house boundaries (Census, network)
python tools/fetch_local_maps.py              # every incorporated place and county subdivision, for the county pages (Census, network)
python tools/fetch_lookup_maps.py             # ZIP code areas and finer lines, for "Find who represents you" (Census, network)
python tools/fetch_court_districts.py         # which federal district court covers each county (28 U.S.C. 81-131, govinfo, network)
python tools/rehearse_changeover.py --out DIR # December's specials and January 3, on a copy outside the repo (CI runs it)
python -m unittest discover tests             # 2383 tests, no dependencies
npm install && npm test                       # 3396 real-DOM checks (needs jsdom)
```

Only `fetch`, `portraits`, `finance`, `field`, `disclosures`, `results`,
`campaigns`, `enrich`, `odds`, `census`, `statelegs`, `legphotos`, `localgov`, `executives`,
`officers`, `courts`, `ballotphotos`, `guidephotos`, `voting`, `federal`, `judiciary`, `vacancies`, `history`, `oge`, `tribes`, `members`, `votes`, `seats`, `outside`, `photocopies` and `congress` touch the network, as do the four `tools/fetch_*_maps.py` scripts and `tools/fetch_court_districts.py`. Run the
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
   ~160 working portraits. Nor let one source stop the others: a refresh step
   whose source cannot be read keeps its committed cache and the run goes on
   (`continue-on-error`). On 2026-10-19 one association's roster that did not
   resolve in DNS failed the whole daily refresh, money and results with it,
   because four state-government commands ran as one step.

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
    `Special:Redirect` URL in any profile's chain. On 2026-10-19, 417 of
    the 585 people on the November ballot for Congress showed the
    silhouette, so two more routes reach them (`kyc/nominee_photos.py`),
    each taught to `route_ok` by name, so a cached portrait from any other
    route is still refused:
    - a Wikidata item carrying the person's own FEC candidate id (P1839)
      and an image (P18), asked by every id the profile holds: a human,
      the only item any of the person's ids is on, its label ending in
      their surname and carrying one of their given names as the profile
      or the filing writes it (`given_fits`: no nickname table, no prefix;
      "Drew Williams" is not "WILLIAMS, JOHN ANDREW" but through an
      evidenced `overrides.PORTRAIT_NAME_FORMS` entry), and a second tie of
      the item's own - a year of birth the profile's agrees with, else a
      2026 candidacy in their state (P3602), an office held for it (P39,
      or its electoral district, P768), each a label of a whole shape with
      the state in its slot, never the state's name found in it ("Mayor of
      Kansas City, Missouri" is not an office for Kansas, "Ambassador to
      Georgia" is the country's: rule 5), an official website (P856) that
      is their campaign's, or an English article that is the one their
      ballot page links. An id is not proof on its own (rule 82): the
      first version took the surname alone - "John Andrews" passed for
      John Andrew Williams, as "andrew" is in it - and none of the three
      nominees it pictured had a birth date to compare, so a namesake's
      item carrying a bot-added id would have passed. The file is resolved
      on Commons (never `Special:FilePath`) and credited from its own page
      (rule 87);
    - for a nominee who sits in their state's legislature, the photograph
      this site's legislature page shows on that member's card
      (`legislature.card_photo`, one implementation, rule 12): only on the
      legislature's own host and credited to it, or on their own party's
      caucus's host in that chamber (`legislature.CAUCUS_SITES`) and
      credited to the caucus - the owner's decision of 2026-10-25, "we can
      credit caucus": Sean McCann's is the Michigan Senate Democrats' file,
      tied to him by his page on its site - never a file Open States gives
      two members, and never an
      "oversized" legphotos entry, whose file was offered before the
      checks a seat-keyed file needs (it waits for those, which legphotos
      now makes before it takes a heavy file, rule 100, not for its
      weight). The first version read the member's
      page again by rules of its own, which skipped legphotos' safeguards.
      That member is found by the chamber their own article's corroborated
      record of offices gives (rule 69) and the same first and last name
      in it, nobody else's, and the photograph is withheld once the roster
      seats someone else or the card shows another file: "Sen22.jpg" shows
      whoever holds the seat.
    Either route refuses a frame wider than tall unless its file is named
    a headshot or portrait (rule 38), and any file in
    `overrides.NOT_A_PORTRAIT` or `PORTRAIT_LICENCE_DOUBTS`: the first
    version gave a person no way to withdraw one. So does every other
    route, at build time (`photos.refused`): a member's article portrait
    (`portraits.held_back`) as much as a nominee's, an officer's roster
    card, a curated association card, a legislator's card. A photograph over the
    caps is shown smaller from the same file where a resizer serves it,
    else as it is, and said (rule 87), and as rule 101's smaller copy once
    one is made. The election offices that print candidates' photographs
    (Washington's voters' guide, Alaska's and Oregon's pamphlets) serve
    them only base64 inside JSON or inside PDFs, with no file to link; by
    the owner's decision of 2026-10-25 they are a route of their own, kept
    here as copies (`kyc/guide_photos.py`, rule 101) and shown only where
    every other route leaves the silhouette. The guide's own page must name
    the person beside the photograph, for that office: the statement record
    (Washington), the statement's heading under the candidate list's link
    beside the name (Alaska), the column under the office's heading with the
    name beside the photograph (Oregon). The name joins in the words of the
    filing, the profile or the office's list, in any order - never a
    surname alone, a short form or an initial only through an evidenced
    `overrides.GUIDE_NAME_FORMS` entry (Oregon's "David Russ" is the filing
    "RUSS, DAVID HONORABLE" through the campaign site both name) - and only
    where it fits one person in the race and the person one of the guide's
    names: Alaska's Senate statements of Dan S. Sullivan and Daniel J.
    Sullivan Jr. are told apart by the initial and the suffix alone. A PDF
    page that draws two images or none, an image no browser draws as the
    guide prints it (Bill Hill's statement holds a CMYK JPEG with an Adobe
    marker, drawn inverted; Oregon's colour ones), and anything the
    likeness test refuses (a frame wider than tall, `photos.refused`) give
    none. A person's refusal is keyed on an address that names one
    candidate - the hosted file, Washington's candidate page, Alaska's
    statement PDF - never one the race shares (Washington's
    `candidate.ashx`, an Oregon page of two columns or its county book),
    which would withdraw the other column's photograph
    (`guide_photos.own_addresses`). A guide that answers in a shape it no
    longer reads - an index with none of the races, a list with no row or
    statement link for an office, a statement record with no photograph
    field, a statement PDF the reader cannot parse - concludes nothing
    (rules 8 and 36): the review of PR #138 found that one changed heading
    tag would have sent thirteen people back to the silhouette and deleted
    their files. Every record keeps the page,
    the words naming the person, the day read and its bytes and size, and
    `validate` fails a shown one without them (`photo-unevidenced`), read
    from the build's own caches. The words are the page's: two runs of
    type that abut are one word (`pdfread.page_text`, by the font's
    widths), or Kreiss-Tomkins's heading was cached as "Registered Demo
    crat".

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
    state pages come from one template, with the state's code and its names
    written in as plain lists from the same build (rule 96);
    `assets/kyc-state.js` draws over them from the same build's people files as the
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
    to the cache. Where the home page has none, the campaign's About or
    Meet page on its own host is read by the same rules, and must itself
    name the candidate (four of thirty nominees' sites without one had it
    there); a site that draws its images with JavaScript, or answers a
    script with a bot wall (Mary Silva's 403, Jena Nelson's 202), is drawn
    in the courts' headless Chrome (`render_portraits`, forty a run, a
    dozen to a browser run) and read by them again, never across a
    redirect to another host. The image is the one the campaign's own page
    draws, wherever it is hosted (a site builder's CDN serves the site's
    files), and the cache keeps that page, the words that named them
    (`portraitEvidence`: an alt text naming them, else the file name) and
    the day. A heavy one is taken in a rendition the page itself lists
    (its `srcset`), else its host's resizer's or Photon's, else at full
    size (rule 87). What a person looks at is judged by one test: a
    photograph of the candidate alone - nobody else in the frame, even in
    the background or in part (an arm, a shoulder, a child's face, a
    hearing's audience; the owner, 2026-10-25: "probably better to leave
    out background people") - whose face, brow to chin, is at
    least a tenth of the height of the 4:5 card that crops it from the top
    (6.5px of the state pages' 65px phone card, where eyes and a mouth can
    be made out) is a likeness and is shown; anything else goes in
    `NOT_A_PORTRAIT` with what was seen and measured. The first version
    let Jamie Davis by a tractor and Brian Bengs speaking in a park stand
    while refusing like scenes; measured, Bengs's face is a seventh and a
    half of the card and stays, Davis's an eleventh and Lauren Jewett's
    beside a seal a fifteenth, and both are refused, as are a family
    photograph, a page of biography text, a halftone street scene, and
    a festival stall and a rally with other people in the frame. On
    2026-10-25 the photographs shown by the routes the owner's brief named
    were looked at - 701: 53 campaign sites', 391 profiles' Commons files
    (the article's or Wikidata's), 122 statewide candidates' (Commons, the
    guides and commissions, the holder's office card), 46 attorneys
    general's (their offices' pages and NAAG's cards) and 89 judges' (the
    crop, article and agreeing-article routes) - and the 88 with anyone
    else visible refused, by route: 1 campaign's, 33 profiles' Commons
    files, 5 statewide candidates' (Arizona's Clean Elections photograph of
    Duwayne Collier is cropped from a family snapshot: a child's face and
    another person's arm), 1 attorney general's office's, and 48 judges'
    Senate hearing stills (9 crops, 39 articles' images); the 267
    legislator cards newly credited to a caucus were looked at too, and 2
    refused. Its review found five more (a hand at JoCasta Zamarripa's
    edge, two judges' hearing audiences, a face on the screen behind Donna
    Miller, a framed photograph of people behind Adam Hamawy, as John
    Giles's and Dave Sunday's were refused) and a refusal's worst case: it
    promoted James Talarico's campaign photograph of him helping a child in
    a classroom, which nobody had seen, and then his Wikidata item's uncut
    file of the refused crop. A photograph that comes forward when a
    person refuses the one before it, from a route that can take a picture
    not made in a studio, is now a build warning
    (`portrait-fallback-unseen`) until it is in
    `overrides.SEEN_AFTER_A_REFUSAL` or `NOT_A_PORTRAIT`, and the nominee
    routes keep what a record stands in for (`replaces`); a refused
    portrait is no portrait, so those routes are asked for its person
    (Talarico, Jeremy Moss, La Shawn Ford and Adrian Boafo now show their
    legislature's or caucus's photograph). Not looked at: the judges'
    `item` route (a Wikidata item's own image, 1,012 portraits), which the
    brief did not name. Most of its recent judges' are Senate Judiciary
    hearing stills with the audience behind them - in a sample of the
    first 330, some 130 clearly show someone else - so applying the
    owner's test there would withdraw several hundred judges' photographs;
    that waits for the owner. One test asks the list wherever a
    page is read (`photos.not_a_portrait`, rule 12: the campaign sites'
    reader, a court's, an attorney general's office's, a statewide
    candidate's guide or article, a judge's), and records what it refused
    in that route's cache (`notPortraits`) for `validate`'s staleness
    check. A curated row takes its campaign's
    portrait as a filer does: Brian Bengs's sat in the cache while his
    profile showed the silhouette. A sitting member never does: their
    portrait comes by their bioguide id. Issue headings come from one heading level of a page
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
    `validate.check_photo_sets` fails a set that names another file. A
    smaller copy this site made of a heavy original (rule 101) is one size
    and stands alone, never in a srcset beside the original's sizes. The
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
    borders. No word may sit on another: at 320-390px the partisan map put
    West Virginia's code on Vermont's callout ("WV T") and Mississippi's on
    Alabama's, and two picked district numbers on Texas's map covered each
    other. Clearing an overlap must not move a word off its own land: the
    first fix sent Kentucky's, Indiana's and West Virginia's codes to the
    Atlantic column on lines up to 170px long, and stepped Texas's "37"
    onto district 11. `kyc-usmap.js` moves a colliding code only within
    the box the build measured clear of its state's edges (`labelRoom`),
    then makes it a callout beside its own state; only the small coastal
    states (`SMALL_ROOM`) join the column. A picked district's number
    moves to another point inside its district, or becomes a callout with
    a line to its own label point (`pick-leader`), clear of the numbers
    already drawn. `testMapOnAPhone` and `testDistrictsOnAPhone` check
    both.

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
    covering the seat counts, when only control was compared. A race's
    people include its holder: the map's first race-first panel listed
    only filers under "Still in the race", so 25 renominated senators -
    Susan Collins, Jon Ossoff - were missing from the list and its count,
    and named only under "Seat held by", below the markets.

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
    guide, and only a page that loads the build's figures names the Congress. Where a city's name join
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
    weekly refresh looks at 6,000 addresses a run, oldest first, inside a
    time budget that ends the run cleanly well before its step's limit
    (`--max-minutes`): killed at the limit, its threads saved the cache
    after the next step had read it, and verify failed the refresh of
    2026-10-19. The build warns about any address not looked at in 60 days. As of 2026-10-18, 7,366
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
    says so: the election office's list of candidates for that office
    (rule 91), with the constitution's term limit (`ballot2026.OPEN_SEATS`,
    read with the NGA's count of the governor's terms) as the reason beside
    it - never news, and never a term limit for anyone else, since a
    term-limited officer may be on the ballot for another office. `stategov`
    withholds an entry whose holder has changed. Any other office on the
    ballot says by name that this was not checked (`holderStatus`
    "unchecked"): silence beside Georgia's governor, with "Open seat" beside
    Alaska's, read as "Brian Kemp is running" (rule 19).
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
    (rule 8). 482 of 1,463 judges had no portrait on 2026-10-19, and the
    research found why. The FJC writes an accented judge's slug
    percent-encoded (`p%C3%A9rez-myrna`), and the reader took only plain
    letters, so ten judges' pages were "unread" on every run. A judge no
    item carries is found by the one article whose `{{FJC Bio}}` names
    their nid, a search on the id; the dialog then says the links came
    that way (`linkVia`), not through an item carrying the id, and a
    search that fails keeps the judge's last entry (rule 8). An item with
    no year of birth is checked by its article's year, and the two must
    agree where both give one. Where the item has no single portrait,
    only these routes take one:
    - two images: the one the item's own article shows;
    - a wide hearing still: a Commons crop `{{Extracted from}}` that file
      and depicting the item alone (P180); Don Willett's depicts a
      microphone and shows a rally's banner;
    - no image: the article's infobox image, if its lead image is the
      same file; an article with no lead image gives nothing.
    A licence doubt is one test for every portrait: Commons' tag stands
    unless the file points to an author who is neither its uploader nor
    a government office (a studio's code, a university's credit, a
    private site's photograph guessed official) or names no author. The
    first list withheld two D.C. court photographs while 491 court
    photographs under the same tag were shown. What fails waits in
    `overrides.PORTRAIT_LICENCE_DOUBTS` for a person, and a portrait kept
    from an earlier read is asked of it again. A photograph
    is shown only at Wikimedia's own sizes up to the 250px a page draws,
    its largest weighed and within 300 KB and 1,200px. A file offered
    only over that is left out and counted (`judge-portraits-oversized`),
    never resized or copied here. Each portrait records its route, the
    evidence naming the judge, the day read and its weight, and the
    build fails one without them. A justice's portrait is the Court's
    official one as Commons holds it, credited to its photographer
    (`overrides.JUSTICE_PORTRAITS`, the owner's decision of 2026-10-20):
    the Court's photographs page asks for approval before publication, and
    the site loaded all nine from supremecourt.gov. The table names the
    file and the author it was checked against, since a Wikidata item's
    image need not be the Court's: Sotomayor's is a 2009 White House
    photograph and Kagan's a CC BY-SA upload, so the table names the
    public-domain copy of each one's official portrait (read 2026-10-25).
    Commons holds the Court's official portraits, not always the ones the
    Court shows now: Roberts's is of 2005, Alito's 2006, Thomas's 2007,
    Sotomayor's 2009 (the Court shows one of 2025) and Kagan's 2010. The
    Court's own stands for a justice the table does not name, and for one
    whose named file the read did not take as recorded - another author,
    an unread size, weight or credit, a licence doubt
    (`justice-portrait-unread`) - and the page then says this site's read
    did not confirm it (`portraitUnconfirmed`), never that Commons does
    not hold it. A credit drops a link whose words name no one ("source"),
    never a link to a user's page: Sotomayor's read "Steve Petteway
    source". A file Commons credits to anyone else is not the Court's. A
    vacancy's judge is found on its court by surname *and* first given name (`vacancies.judge_of`): two of the list's departing
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

85. **A ZIP code is not a place, and a location is placed on lines fine
    enough to place it.** "Who represents me" had no answer outside a
    district page's GPS button, and that button read the 1:5,000,000 maps
    the page draws with a 3 km margin: in Manhattan none of 25 points got
    one district, a 30 m fix in Brooklyn was told it was "approximate (to
    within about 0 km)", and in Athens, Ohio the old map's card showed OH-2
    and David Taylor, not OH-12 and the reader's own member, because one
    list of numbers picked both maps. Now `kyc-findrep.js` answers a ZIP code
    or a location at every level from `data/lookup/<st>.js` and the
    legislature file, on the device, and the district page places a point on
    the same lines: the Census Bureau's 1:500,000 boundaries and each
    redrawn state's own plan, near a line within 400 m plus the browser's
    stated accuracy, each map's own district in the address (`d=`, `was=`).
    The state legislature's districts are not on those lines but on the
    legislature page's, simplified at 120-300 m and rounded to 0.1 map unit,
    so a reader 500 m from a Texas house line was named one legislator with
    no caveat: each legislature file says how far its lines may stray
    (`lineErrorKm`, `legislature.line_error_km`, from the tool's own
    `statelegs.map_tolerance_m`), the margin there is wider by it, and the
    answer gives both margins. The panel is on pages without people files
    too, where it read "OH Senate" and sent "How to vote" to a `#voting`
    the page did not have, which its router read as clearing the reader's
    selection: a state's name, district map and own lookup come from the
    lookup index (`lookup.place_info`), and `#voting` is used only where
    the page holds that block. A note names the kind of line that is near
    (a district line, a county line, the state line or the shore); a ZIP
    code across a state line says so first; and a file that failed to load
    is never answered with a neighbour's edge. A place is in its own words
    there too (rule 75): "the District of Columbia" in a sentence
    (`place`), and no "if you live across the state line" by Puerto Rico's
    shore, or Hawaii's (`alone`: no state meets it across a land line).
    A ZIP area's share of a district is a share of its land, from the
    Census relationship files of the vintage the pages draw (the 2024
    legislative districts; counties by the 2020 file except where they
    changed, `fetch_lookup_maps.COUNTIES_CHANGED`); a 2026 plan's shares are
    measured, and the same measurement of the 119th map is compared with the
    Bureau's file and kept in the file. Only `lookup.WHOLE` (99%) of a ZIP
    area's land names one district; anything less lists every district with
    its share and offers the location, and a ZIP code with no ZIP area (post
    office boxes) says so. `lookup.build` refuses a ZIP code naming a
    district, county or legislative district the pages do not draw. Never
    send what a reader typed: the Census geocoder takes addresses, but only
    through a remote script, and it would send them away.

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

87. **A photograph says whose it is, read from its source, and weighs
    what a card needs.** 153 of 394 Wikimedia portraits were CC BY or
    CC BY-SA, whose terms require the author, the licence and a link, and
    none was credited; the footer gave every portrait to Congress.gov,
    though the House's are the Clerk's and two dozen came from campaign
    sites. `portraits` reads each Commons file's author and licence from
    its own description page (`extmetadata`), never typed in; a non-free
    file is not shown. Both dialogs print the credit under the name, a
    government photograph names its host, a campaign's its website, an
    election office's guide's where it was found ("Photo: from the
    Washington Secretary of State's voters' guide", linked to the
    candidate's page in it, though the file is hosted here:
    `kyc/guide_photos.py`; the candidates submit these photographs, and
    "Photo: Washington Secretary of State" read as the office's own), a
    file this site decoded says so ("converted by this site to PNG from the
    pamphlet's JPEG 2000 image, pixel for pixel", `credit.converted`), and a
    fallback that loads instead is credited by its own host.
    `validate` fails a shown photograph with no credit and a Commons one
    with no recorded licence, a judge's (`judge_links`, read with the
    file's size) included. A credit is the file page's words with what
    Commons hides or says of no one taken out (`portraits.author_of`): a
    hidden duplicate span printed "Unknown author Unknown author" under
    ten photographs, an uploader's sentence about not knowing the
    photographer ran to four lines on a phone, a file name stood as an
    author and "PDM-owner" as a licence. Where the licence asks for an
    author the page does not name, the line says "author not recorded on
    Commons" and links the file. A new Commons portrait whose credit
    could not be read waits off the page for the next run (rule 8) rather
    than fail the build. A portrait not on Wikimedia is weighed when
    found: one campaign's was a 5 MB PNG for a 165px card, and 27 of the
    NGA's governors' headshots weighed 320 KB to 7.6 MB for a 40px circle.
    Over 300 KB or 1,200px it is shown smaller from the same file - a
    rendition its page's srcset or a `<picture>`'s `<source>` lists,
    Wikimedia's standard widths, its host's own resizer, or WordPress.com's
    Photon, which fetches that very address and scales it (rule 42) - once
    the smaller copy is weighed and found the same shape
    (`photos.lighter_rendition`; `lighter_form` where no page offers
    renditions), by every route alike: a campaign's, a legislature's, a
    Wikidata item's, an attorney general's, a justice's and a statewide
    candidate's (`kyc/official_photos.py` `choose`, `officers.ag_photo`).
    Where none serves it, it is shown all the same and said
    (`portraitHeavy`, with the heavy file's address, which rule 101's copies
    key on; `kept`, or `heavy` in the portrait cache; the build prints how
    many), as the smaller copy this site made of it where its host is one
    rule 101 copies from, and a heavy record that does not say so fails the
    build. Weight is never a reason to leave a photograph out. A brief of 2026-10-19
    ("official small renditions only") ruled the resizers out: the first
    version of PR #134, built under it, left six nominees main showed out
    again (Michael J. Quirk's PNG was 6 KB over), with Nevada's headshot of
    Carrie Buck; withholding them left eleven November nominees with the
    silhouette beside an opponent's photograph; and under it 27 justices the
    court's own page tied to them - all nine of Texas's Court of Criminal
    Appeals - drew empty circles for their weight alone. The owner's
    decision of 2026-10-25 ("more content is better than strict rules")
    relaxed it for nominees, attorneys general, justices and statewide
    candidates alike: a weight cap and a resizer cost or save only page
    weight and guard no fact about a person. What it never relaxes is a
    route tied to the person (rule 24), the words naming them, the shape
    test, a person's look and the licence doubts (`NOT_A_PORTRAIT`,
    `PORTRAIT_LICENCE_DOUBTS`), and the credits. The House
    Clerk's are only weighed; every one is within the caps. A server that
    gzips an image is read through it (Missouri's attorney general's
    headshot read as "not an image"). No srcset offers a size wider than
    a 2x screen needs, the officials' dialog's included. A state officer's photograph
    comes only from their office or their association's roster, matched by
    state, never a search. No attorney general had one (STATEGOV-13): a
    party association's photograph is the party's. So
    `officers.add_ag_photos` reads the office's own pages - those that
    confirmed the name (rule 56), the attorney general's page they link,
    and where the front page links none the office's own page about its
    attorney general (`officers.BIO_PAGES`, an address typed in, the image
    on it tested like any other) - and takes only an image carrying the surname as a word, or in
    run-together words of the holder's name and title
    ("AgLizMurrillHeadshot"), with no other first name before it, whose
    words say it is a likeness ("headshot", "photo of") or are nothing but
    the name and title. A substring test would take "Carrie-Smith-Headshot"
    for Chris Carr and "Solicitor General Jessica Ford headshot" for Aaron
    Ford, and every photograph added, changed or dropped is reported for a
    person to look at. Arkansas's "AG-Griffin-Logo.png" is alt-texted "Tim Griffin
    Attorney General of Arkansas", Arizona's "AG Mayes talking to a
    townhall crowd": a logo, a banner or a scene is refused by its words,
    a landscape frame by its shape. A NASS card filed under the state's
    code ("AZ.jpg") cannot carry a surname; it is shown only through an
    evidenced `overrides.OFFICER_PHOTOS` entry, which names the holder it
    was checked for and is withheld, and said, once the roster names
    someone else. Every build lists the confirmed officers still shown
    without one.

    Nine attorneys general's offices offer theirs only above the caps
    (California's is a 6 MB original).
    Their association's card is the lighter of two photographs tied to the
    person and goes first there (`stategov.officer_photos`): NAAG's "Find
    my AG" roster names each attorney general and the state beside the
    photograph at WordPress's own 225x300. naag.org answers a script and
    a headless browser with a Cloudflare challenge, so a person reads it
    in a windowed Chrome (`tools/read_naag_cards.mjs`) and records each
    card in `OFFICER_PHOTOS` on its state and name, never its file's:
    West Virginia's is "ag-WA-McCusker". A holder whose name the office
    has not confirmed gets none. An office's biography page typed into
    `officers.BIO_PAGES` carries the day and the holder it was found for,
    and the build says when the holder has changed or the page gave them
    nothing. A state justice's photograph comes from the roster the
    court's recipe reads (rule 57) or the one page the roster links from
    that justice's own name or row - never an address built from a name -
    and only where every word the page gives the image (its alt text,
    title, caption and file name) is theirs and none says a scene
    (`court_photos.judge`). Two Connecticut justices' own pages carry a
    former justice's alt text, "Justice Christine E. Keller"; Oklahoma's
    Edmondson page shows him "pinned by his brother". A surname that is
    also a word the test passes over (Iowa's Justice May) counts only
    beside a given name, an initial or a title: "IMG_May_2024" is a date.
    An official portrait those words refuse is an evidenced
    `overrides.JUSTICE_PHOTOS` entry. The state page credits each to the
    court, linked to the page it was read on (`KYC.photoCreditHtml`, as
    every credit is). Every photograph on these routes is cached with that
    page, the words naming the person beside it, the day read, its bytes
    and pixel size; `official_photos.record_problems` fails one without
    them, read or curated, and the build stops on it rather than drop it
    from the page without a word. Every record, read now or kept from an
    earlier read (rule 8), is asked of the lists a person keeps -
    `NOT_A_PORTRAIT` and `PORTRAIT_LICENCE_DOUBTS`, one of each for every
    route, a nominee's, an official's, a judge's and a campaign's
    (`photos.refused`, one test that `nominee_photos`,
    `official_photos.held_back`, `judge_links.held_back`,
    `portraits.held_back`, `enrich.campaign_portrait`, the officers'
    roster cards and the legislator cards all ask) - and a file in either
    never reaches a page. A page read asks `NOT_A_PORTRAIT` through one
    helper beside it (`photos.not_a_portrait`), which records what it
    passed over for the staleness check (rule 12).

    A party caucus's photograph of its own member is that caucus's word
    about its member, and is shown credited to the caucus by the name its
    own site gives itself (the owner, 2026-10-25: "we can credit caucus"):
    only a host `legislature.CAUCUS_SITES` lists for that state and
    chamber, with its own page title and the day read as evidence, whose
    party is the member's (an independent on the House Republicans' host
    is not credited to them), for a file Open States gives that member
    alone and whose name does not call it a group's, a leader's or a
    banner (`legislature.caucus_photo`). One test says what host is a
    caucus's, for its files and its member pages alike
    (`legislature.on_caucus_host`: the entry or any subdomain of it): the
    first matched "www.misenategop.com" for a file and not for a page, so
    18 cards were credited to the Michigan Senate Republicans without a
    link to their page there. Any other host still reads
    "Photo: from <host>, as listed by Open States", and New Hampshire's
    nhhousedems.org is not a caucus: its title is "New Hampshire House
    Dems Victory Committee", a campaign committee's.

    A Commons photograph's credit says the year its file's own page gives
    it (`portraits.year_of`, read with the author and licence:
    `CREDIT_FORM` 4), every route alike - a profile's, a statewide
    candidate's, a judge's - through the one helper
    (`KYC.photoCreditHtml`: "Photo (1981): ..."; a justice's official
    portrait keeps "Official portrait, 2005"), and nothing where the page
    gives no single four-digit year, never a guessed or an upload year:
    Tad Jude's (MN) black-and-white legislature portrait is from 1981 and
    read as current (the owner's brief of 2026-10-25). Its review found
    the first reading took any single year: "13 October 2020 (upload
    date)" and "(original upload date)" printed as the year Amanda Edwards's
    and four judges' photographs were taken, "circa 1993", "c. 2000" and
    "circa 2025-26" as exact years, and a date that is the very day the
    file was uploaded (the upload form's default) as evidence. Now a date
    that says upload, is qualified (circa, before, "or", a "?", an
    `{{other date}}` carrying P1480), is a span, or is the upload day
    gives none. The year is said as "Photo (1981)", not "Photograph,
    1981.", which was false under a judge's oil portrait.

88. **A colour that carries meaning is checked as a colour-blind reader
    sees it, and is never the only cue.** The 2026-10-17 audit ran the
    Machado matrices over the legends: to a deuteranope the split lilac was
    the Democratic blue (0.8 apart in OKLab x100), so 21 divided
    governments read as Democratic trifectas; the light theme's Republican
    red and independent amber were one olive (2.3); the guide's teal and
    magenta 3.7 apart erased the judges map's main distinction. So:
    - `render_test.js` (`testColourVision`) runs protanopia, deuteranopia
      and tritanopia over every legend's fills, in all three themes, from
      the tokens. Two fills a reader must tell apart by colour alone are 10
      apart (7 under tritanopia).
    - Split, divided and "none" are hatched as well as coloured
      (`KYC.svgFill`, one pattern fill per shape, rule 45), and that pair
      needs 5. A pattern means one thing on a screen: the balance bar over
      the map marks the seats on the ballot with dots, never the map's
      hatch, which there means "no race".
    - Grey means "none" and nothing else: no category is grey
      (`--none-fill`, the Eleventh Circuit was).
    - A fill is never also a text colour that needs 4.5:1. Light
      `--party-i` is text; `--party-i-fill` fills, in every chart as on
      every map (the balance bar and the House squares came in with the
      text amber, and `testColourVision` now reads their rules). A callout
      writes on a fill in the ink `KYC.fillInk` names for it.
    - No status or money colour is a party's: "Lost primary" was the
      Republican red, "Open seat" the independents' amber, a Democrat's
      "Spent" red.
    - A scale that is not about party (the ideology score) is drawn in
      neutral ink.
    - A distinction drawn only in a hover title does not exist for a
      touch reader: an open Senate seat is its party's tint, a special
      election is outlined, each with a legend key. A key is drawn as
      the map draws it: a 2px dashed border on a 10px square drew solid,
      the look of a picked state's outline, so the special-election key
      is the map's own dash on an SVG wide enough to show it, and a
      picked state's line is solid and thicker.

89. **A vote is a member's by the record's id, inside a term they served,
    and an absence from the record is not a missed vote.** "How did my
    representative vote" had no answer but a DW-NOMINATE score
    (PERSONA-15). `kyc/rollcalls.py` reads every roll call from the House
    Clerk's XML (bioguide ids) and the Senate's LIS XML (LIS ids, mapped
    through congress-legislators), and gives a vote to a member only by
    that id and only on a day congress-legislators has them serving in that
    chamber: the first House roll call of 2025 lists Matt Gaetz, who never
    took his seat (`overrides.ROLL_CALL_NON_MEMBERS`), and a member seated
    in a special election is listed in nothing before it. The record's
    words for each id are checked against the member - its state, and its
    surname among their name's words, never a first name (the Senate
    writes "John Reed" for Jack Reed) - and an id that disagrees gives
    nobody anything (`votes-unattributed`). The Clerk writes a delegate's
    state "XX" in the Committee of the Whole's roll calls; that passes only
    for a member who sits for D.C. or a territory. Read on 2026-10-18, the
    Clerk listed the Speaker in 522 of the 676 roll calls held: one he does
    not vote in names him nowhere. Counted as missed, he would have read as
    absent from 154 of the House's votes, so only a record's "Not Voting"
    is missed, the rest is said apart with the House's own rule quoted
    (Rule I, clause 7; Rule III, clause 3(a)). A "Not Voting" dated after a
    member left (David Scott, listed the day after) is nobody's. A roll
    call on the day a member took their seat, before the first that lists
    them, or on the day they left, after the last, was not held while they
    served: congress-legislators dates a term by the day, and six members
    seated mid-Congress were told the record had left them out of one
    (Walkinshaw, House roll call 244 of 2025, on his first day). One LIS id
    under two members gives its votes to neither. A record's placeholder
    is not a title (rule 10): the Senate's "No short title on file" stood
    in a bill's place on 169 votes, and a roll call with no title takes the
    one its measure's other roll calls give. The Clerk's "H R 9497" is
    written "H.R. 9497", as the Senate's record and the bills write it, and
    its "QUORUM" and "ADJOURN" are not measures. A word is searched from
    its start: "ICE" found 37 votes on "justice", "service" and "police".
    The Clerk answers a roll call it
    has not posted with HTTP 200 and an "Error sanitizing file" note: not
    a file (rule 52), and it ends the run there without concluding
    anything (rule 8). Nothing is chosen: no "key votes", which would be an
    editorial list. The votes are in `data/votes/<chamber>.js`, loaded on
    demand from the stamped URLs every profile page names in its
    `onDemandData` template (rule 76), never in the people files.

90. **A past result belongs to the lines it was fought on, is read from
    the official count, and is checked before it is shown; money is
    attributed by id and shown as filed.** The 2026-10-17 audit found no
    past result, no outside spending and no money beside a race anywhere
    (RACES-15, PERSONA-11/12, VISUALS-20/33). `kyc/seat_history.py`
    reads the Clerk of the House's "Statistics of the Presidential and
    Congressional Election" (2024 for the House; 2020, 2022 and 2024 for
    the Senate, the latest election to a term ending when the seat's
    does: Oklahoma's class II seat was last elected in 2022's special,
    not 2020) from its PDF. Each file numbers its accented letters
    afresh (0x83 is "é" in 2020 and "í" in 2024), so the decoder reads
    the file's own /Differences and fails on any byte it does not name.
    A block whose names and counts do not pair is an error, never
    guessed: the page number follows a page's last count, a fusion line
    names a party and no one ("Conservative, Common Sense"), a runoff's
    counts are footnoted (Georgia's January 5, 2021 runoff) and shown as
    the runoff's, Maine's final ranked-choice round and Alaska's first
    choices say which they are, and an unopposed name has no count and a
    footnote saying why. A result is shown only where a second
    compilation names the same winner and runner-up, in that order, with
    counts within 1% (MIT's Senate returns; for the House, whose MIT file
    sits behind a form asking for a name and an email, each state's 2024
    Wikipedia page) - a lead, rule 50 - and the page says what was
    checked; the cache keeps every difference. A district in
    `districts.REDRAWN` shows no 2024 figure, and says only what is true of
    every redrawn district - the result was counted on the old lines - and
    links where its area came from: "fought by other voters" was false of
    FL-1, 99.8% of whose old area it keeps. A result is "the last election
    before the 2026 election", never "the last election": five House seats
    (VA-11, AZ-7, NJ-11, GA-13, GA-14) were filled by special elections
    after 2024, and the page named Gerald Connolly as VA-11's last winner
    beside the member who won it after his death. Who took a seat after its
    counted election comes from the frozen record and the snapshot
    (`seat_history.seated_since`, `seatedSince`): the fold then says the
    last *regular* election and who took the seat, by special election or
    appointment, on what day. From the day after Election Day the fold is
    "Before 2026", not "Last time" (rule 63), and a ranked-choice count's
    first choices are a lead, never a win.
    `kyc/outside.py` reads independent expenditures from the FEC's
    by-candidate totals for the 2025-26 cycle (an election-period read gave
    Jon Ossoff the January 2021 runoff's spending), by the profile's own
    candidate ids at the key's pace (rule 37), one side at a time where
    one candidate's rows run past a page (sorted on committee and side
    together, the API repeated 12 of 101 rows). A row counts only where its
    id's office and state are the profile's (`outside-attribution` is an
    error), never by name; each side is its own total, never a net, and
    says the FEC's processed filings trail the 24- and 48-hour reports.
    One committee under two of a person's ids is one group (`merged`). A
    member running for the other chamber keeps what was filed under their
    own id, labelled as that candidacy's, and the campaign they are running
    shows it on a line of its own (`outsideSpendingOther`), never summed:
    Andy Barr's $7.2 million under his House id read as spending on a House
    race he is not in. A comparison's platform says where each came from,
    in the words the dialog uses (`KYC.platformItems`, one reading): a
    sitting member's is their official website's issue list (rule 86),
    never the campaign's words, and is split on its semicolons as a
    campaign's headings are - read as comma-split roster text, it was
    called "this site's roster summary". A party-only market over one party's ballot is never ranked by
    closeness (rule 79).
    A race's money is its campaigns' own totals as bars in neutral ink on
    one scale, the party only in the name chip, each row with its own
    through-date. Closest races are ordered by one market's prices, the
    gap between its two highest, never a blend (rule 40). In the grid's
    races view every new fold is drawn when opened (GRID-14's budget).

91. **A ballot's candidates are the election office's list, read for
    whoever holds the office today.** The state pages marked 36
    governorships and some 90 other statewide offices "This office is on
    the Nov 3, 2026 ballot" and named no one running for any of them; a
    reader asked "who is on my ballot" and got the holder, who in half the
    states is not (audit 2026-10-17, FRESHNESS-05, STATEGOV-14,
    PERSONA-08, RACES-16). The candidates are a hand-edited cache,
    `data/statewide_candidates.json` (`kyc/statewide.py`), each list the
    jurisdiction's own election office's - a county's only where the state
    publishes none that can be read, by an evidenced
    `overrides.STATEWIDE_LISTS_ELSEWHERE` entry - quoted and dated, and
    exactly the offices `kyc/ballot2026.py` puts on the ballot. A list is
    named as the document it is ("the Clark County Registrar of Voters’
    notice of general election"), never "Certified by" a body: the first
    page credited a county's sample ballot and a commission's voter guide
    as certified by them. "Certified" is said only where the document's
    own words say so (`certifiedQuote`) and the state's own office
    published it; a county's or commission's list says why the state's
    was not used (`notStateList`). Names are the list's, written first
    name first, in ordinary capitals and without a ballot title (rule 77:
    "Lombardo, Joseph", "JOSH SHAPIRO", "Governor Sarah Huckabee
    Sanders"), the list's form kept beside them; a party the list
    abbreviates is spelled out from its key or statute
    (`statewide.PARTY_CODES`), and an unexplained code fails the build.
    Write-ins apart, listed by surname and said to be; no money or
    platform, never a profile (rule 27), never joined to one by a name
    (rule 25). A photograph since the owner's decision of 2026-10-19, by
    these routes in this order and no other (`kyc/statewide_photos.py`,
    `ballotphotos`), credited beside the name: the office photograph the
    card already shows, for the one candidate the holder line settles as
    its holder; a member of Congress's own, by bioguide id, through an
    evidenced `OTHER_OFFICE_NOMINEES` entry; an official guide's (Arizona's
    Clean Elections Commission's list, California's voter guide, each
    pairing the picture with the name - by block and alt text, never by
    nearness: California's image precedes its heading, and a reader that
    took the next image gave Rob Bonta Michael Gates's face); and
    the race's own Wikipedia article, its title built from the race, its
    link matched on given name and surname within that race (Danielle
    Ford is not Aaron Ford, whose article the same page links) and never
    on a one-word name, then checked as rule 33's are, the race's infobox
    image beside the nominee before the article's lead. The guides whose
    photographs have no address of their own - Alaska's statements (PDFs,
    none of them encrypted, whatever this rule once said) and Oregon's
    pamphlet (JPEG 2000 inside PDFs) - picture a candidate none of those
    routes reaches, kept here as copies by the owner's decision of
    2026-10-25 (`kyc/guide_photos.py`, rules 24 and 101), joined on the
    list's own words for that office. A heavy photograph is shown and said, as rule 87 says. A Commons
    file is held to rule 82's one licence test, at the read and again at
    every build (`statewide_photos.licence_doubt`): one whose page names no
    author, public domain on an uploader's word alone ("PD-author", or no
    PD category), or an uploader's own declaration (CC0, "Copyrighted free
    use", "Attribution") on a file calling itself official by an author
    who is no government office - Kris Kobach's "official portrait, 2024",
    CC0 by a user account - is withheld and said, and what a person doubts
    is in `PORTRAIT_LICENCE_DOUBTS`; the first review found CC0 taken on
    the same word that refused "PD-author". A scene or an event ("Aaron
    Ford addresses the United Nations Human Rights Committee") is refused
    by the file's name, and what a person looked at and found no likeness
    in is in `NOT_A_PORTRAIT`, keyed on the Commons upload. A running
    mate is matched only beside their own ticket's nominee
    (`running_mateN` beside `nomineeN`). A sitting member a list names is a
    build warning (`statewide-member-unnoted`) until an evidenced
    `OTHER_OFFICE_NOMINEES` entry says so on their profile - Amy
    Klobuchar was on Minnesota's governor ballot while hers said nothing.
    The holder line is read from the list for the roster's holder at build
    time, never copied from the research: "not among the candidates for
    this office" where no one on it carries their surname (a hyphen and a
    space one spelling), "among the candidates" (never "running for
    re-election") only where the list's marked holder carries their
    surname and given name, each naming the list. A namesake settles nothing: the first
    read called Governor Bill Lee absent from a list printing "Eddie Lee
    Murphy" only because a person had looked, so a namesake is recorded
    with why (`namesakes`), and a short form the list does not print
    ("Joe" for "Lombardo, Joseph") is an evidenced
    `overrides.STATEWIDE_NAME_FORMS` entry, or the line says "not
    checked". After Election Day the block is in the past tense and links
    the state's results; this site names no state winner.

92. **"Who is on my ballot" is its own question, answered from the views
    that already answer its parts, and an address keeps a ZIP code, never
    a location.** A reader asked who was on her ballot and the site had
    only "who represents me": a state page listing the races for Congress
    and saying the governor was elected without naming anyone running,
    and no link from the lookup's answer to any of it (audit 2026-10-17,
    VISUALS-26, RACES-16, PERSONA-08). `ballot.html` (`kyc-ballot.js`)
    lists every contest the site can name for one ZIP code or location:
    the Senate races, the House race on the 2026 map (a ZIP area across
    district lines gives one card per district with its share, and offers
    the location, rule 85), the statewide offices on the ballot with the
    election office's list (rule 91), and whether the reader's legislative
    seats are up. Nothing in it is drawn twice: a race's people are split,
    ordered, badged and counted by `KYC.cards` as on the state page
    (`racePeople`, rules 12 and 73), an office by `KYC.stategov`, a seat by
    the words the legislature page says it in, and the state page's voting
    block and its key dates live in the same module. It never names who
    holds a seat (rule 27) beyond a race's own words, and what it does not
    hold - legislative candidates, local questions and contests - is
    "not listed here", with the state's own sample ballot where one is
    linked; a seat whose district the record cannot name is said to be
    unknown, never "not up" (rule 19). A place with no election that day
    (Puerto Rico's record says so) is told that, not "may also hold". The
    address is `#/?zip=`, so a copied link shows the same list, and a
    location is never put in it: a shared link would carry the reader's
    whereabouts. From the day after the election it says the election was
    held and links the state's results, and names no state winner. It
    prints in the light theme's colours whatever the reader chose: printed
    from the dark theme, its light text came out white on white paper.
    Its review found the shared split was not enough. "On your ballot"
    lists only whom the lookup's answer lists (`KYC.stillRunning`): IL-4's
    card counted five on the ballot over seven names, two of them filers
    the results do not settle (rule 74), who are now named apart; a holder
    off the ballot is named with their own status (rule 61), never among
    those who "lost the primary, withdrew, or were not on the primary
    ballot". A statewide holder line says who the holder is, since no
    holder block stands above it. "Not known" is this site's gap, not the
    state's: North Dakota's House and West Virginia's Senate records name
    their districts (`legislature.seats_up`), and a district's seats take
    the words their count gives (`districtSeats`: Arizona's House elects
    two a district, never "this seat").

94. **A page loads the people it shows, and one build of them.** Every
    grid, map, state and district page loaded all of `profiles.js` - 6.7 MB,
    874 KB gzipped - to show one state: Wyoming's page carried 2,589
    profiles to draw 15, and a throttled phone waited 6.5 to 7 seconds for
    the first card (TECH-02, RACES-25). The build now writes
    `data/people/meta.js` (the build's figures, `kycBuildMeta`),
    `data/people/index.js` (everyone's card and search fields, every race)
    for the grid, the map and the directory of states, and
    `data/people/<st>.js` (a state's whole records and its races) for its own
    state and district pages. What the index leaves out is a list,
    `emit.INDEX_LEAVES_OUT`: fields only the dialog or a race's money and
    comparison folds show, and fields no page reads; a new field is in the
    index until it is named there. `testPeopleSplit` draws a sample of the
    grid's, the map's and the state pages' views from the index and from
    everyone's whole records and fails where they differ, and
    `TestTheIndexDrawsNothingItLeavesOut` reads every module those pages
    load and fails on a read of a left-out field, or of a kyc.js helper that
    reads one, outside the folds that wait for the state's file. A card's
    one-line office (`politicalHistory`) is a card field, and so is its way
    to a sitting member's office (`contactForm`, `phone`): landed beside the
    split, the "Contact office" action read four fields the index left out
    and would have vanished from every card on the grid and the map with
    nothing failing. A member's district offices stay the dialog's but on
    the record of one whose card calls a district office, which carries them
    whole (`emit.INDEX_KEEPS_FOR_THE_CARD`). A card's record is
    never shown as a person's whole record: the dialog, a race's money and
    its comparison load the state's file first (`KYC.loadPeople`, one
    promise per file, named stamped in `onDemandData`), say so while they
    load and say so when it fails, because a field missing from a card reads
    as "No data" about a real person. A ZIP code or a link to someone of
    another state loads that state's file, or the index to find them. Your
    ballot (`ballot.html`, rule 92) loads the build's figures and no one's
    records: each answer loads the files of the states it is in before it
    is drawn (`KYC.findRep.peopleFor`), and one that did not load is named,
    never drawn as a ballot with nobody on it. A
    file is taken in as it is assigned (`kycPeopleFile`, kyc.js), filling
    the index's record, never replacing it, and refused when it names
    another build than the page's figures, which the page then says (rule
    34): a tab opened before a deploy reads that the site was updated since
    it was opened, not that it was loading. A link to an id nobody here
    has says so in the dialog, on every page alike. A state's file must hold everyone its races and people point at,
    or the build stops (`emit.split_problems`). A figure about the whole
    chamber is the build's, not a page's sum: the dialog's left-right ticks
    are `chamberScores`, counted from every profile, since a state page
    holding one delegation drew a senator among their own state's members
    as though it were the Senate. The guide's Congress page names its
    members from the build (`pages.committees_html`, `leaders_html`) and
    loads no profile data.

95. **A ballot question is the election office's words, and "none" is a
    document's.** Every state page said the ballot also held "ballot
    measures, which this site does not list", and a reader asking what was
    on her ballot got no question at all (audit 2026-10-17, RACES-16,
    STATEGOV-14, PERSONA-08). The questions are a hand-edited cache,
    `data/ballot_measures.json` (`kyc/ballot_measures.py`), researched from
    each election office's own list and re-opened by a second reader, and
    written to `data/measures.js` for the state pages' "Statewide
    questions" section and Your ballot's last card, one implementation
    (`KYC.ballot`, rule 12). Each measure is its designation, its title
    where the state prints one, its official text quoted, its kind and who
    put it on the ballot, its source's address and words and the day read;
    a measure or list on any host but the jurisdiction's own official
    domains or an evidenced `overrides.MEASURE_SOURCES_ELSEWHERE` entry
    fails the build (rule 50). A quoted text is said to be what it is:
    California's are the voter guide's summaries, not the ballot label
    (`textNote`), and one the source cuts is marked cut. The page never
    says what a yes or a no vote does in its own words, and no colour
    suggests a side; a record field the cache does not define (a "yes
    means" of the site's own) is refused. "None" is said only with what
    shows it, quoted: the office's sentence (Illinois, Oregon), an office's
    list of its ballots' questions, or the official ballots, which print
    every statewide question (`noneFrom`), named as the ballot read - often
    one county's - never "the official sample ballots" as though every one
    had been. A proclamation calling the election for offices is no basis:
    Texas's first "none" rested on one, which would not name an amendment
    election that its own resolution sets. A shown title is the document's
    own name: the researchers' "linked from https://..." asides were link
    text on the page, and a title carrying an address or a note is refused.
    A question on every ballot that each town or city decides for itself
    (New Hampshire's HB 1300 question, with "[name of municipality]" in its
    text) is `local`, listed apart and never counted as statewide.
    Where no official source says either way (American Samoa, Maine,
    Pennsylvania, Puerto Rico), the page says this site has not found an
    official list and links the election office, never "none" (rule 19):
    Maine's first record said "none" on a town's sample ballot, and a
    second reader set it back. A measure decided at an earlier 2026
    election, or taken off by a court, is not listed. "Statewide" is a
    state's word (rule 75): the District's are District-wide, a
    territory's Territory-wide, and neither is told of a county's questions.
    From the day after Election Day the heading and lead are in the past
    tense beside the state's results page - "that were on the ballot" only
    over a list, never over "none" or "not found" - and this site reads no
    result of a ballot question.

96. **A person or a race shared is its own page, and a page says its facts
    without scripts.** A profile and a race live behind a fragment
    (`#/profile/<id>`) that every crawler drops, so each shared person
    unfurled as the home page's card - whose image said "who is running in
    2026" and named three sources, false of a court page and after the
    election - and "Copy link" did nothing where the clipboard refused
    (TECH-09). And with scripts off, or to a crawler's first pass, a state
    page read "Loading..." for ever (TECH-10). So the build writes a share
    page per profile (`p/<id>.html`) and per race (`r/<raceId>.html`,
    `kyc/share.py`): its own title, description, canonical address and
    image, the facts in plain text, and a link to the view, which
    `assets/kyc-share.js` follows at once for a reader with scripts. Not a
    meta refresh: that would send a reader without scripts, and some
    unfurlers, to a view that needs them. The image is a photograph only
    by a sourced route (rule 24): the article's own `photoSet`, the Clerk's
    portrait, or a credited campaign portrait; anything else is the card.
    A state page is written with its `<h1>`, delegation and races as plain
    lists from the build's profiles and races (`pages.state_static`), and
    its statewide questions (rule 95) from the record `data/measures.js`
    is written from (`pages.measures_static`, each designation and title
    linked to its source, in `KYC.ballot`'s words); its script draws over
    them, and a failed load keeps them: a failed `data/measures.js` keeps
    the plain questions under a line saying so, and Your ballot's last card
    says the list did not load (`KYC.ballot.measuresMissing`); drawn from
    nothing, they vanished without a word (PR #123 review). Where someone
    stands is said in the profile dialog's words: `share.status_words`
    reads `KYC.standing` the way kyc.js does, on the day the results were
    read (`share.post_election`), and `testSharePages` compares the two for
    every profile, every race's lists and every state page's. That covers
    only the statuses today's data holds: "elected", "defeated", "runoff"
    and every post-election word would first have met the page code on the
    night a November result was read, and a word changed in kyc.js alone
    would have held that refresh (PR #121 review). So every case of the
    table - each status, member or not, appointed, unconfirmed, minor-party,
    all-party, certified or qualified, before and after Election Day, and
    each filer the results do not settle - is written by `share.status_table`
    to `tests/fixtures/share_status_words.json`, which `test_share` checks is
    current and the render suite asks `KYC.raceStatus` about row by row: a
    word changed on one side fails the day it changes (rule 63). Each status
    carries the source the dialog's badge credits (`share.status_source`):
    the card the pages unfurl with said "every fact names its source" over
    pages that named none. The seat is in words in a description ("member
    of the U.S. House for AL-4"; a card's bullet read as a glitch in an
    unfurl), a race's description credits its source before its list and
    stops at `share.DESCRIPTION_MAX` characters with how many more (an
    unfurler's cut took 62 races' later candidates and every credit), the
    holder of a race's seat is marked while seated (rule 67),
    and a member leaving says where they are going (`otherOffice`) or when
    their seat is next up, as the dialog does. Nothing in them is dated or
    carries the build's time, and an unchanged share page is not rewritten:
    a refresh that moves nobody touches none of 3,000 files. They are in
    the sitemap, and `verify` regenerates them with the state pages,
    reporting one stale, missing, or left for a profile or race the data no
    longer holds (the build removes those) - except a page at an id the
    profile still answers to (`share.aliases`: a folded filing, a filer
    since seated), which is rewritten as that profile's, its canonical
    address the profile's own page, so a link once shared never becomes a
    404. A crawler that runs scripts may fold a share page into the view it
    is sent to, and so into the home page; the unfurlers this is for run
    none. Every generated page and both templates carry a `<noscript>` line
    saying what needs JavaScript, and a page that lists nothing without it
    (a legislature's, a county page) says so rather than promising plain
    text. "Copy link" is `KYC.shareLink`: a phone's share sheet (the main
    pointer coarse: desktop browsers have one too, and the button says
    "Copy"), else the clipboard, else a selected read-only field saying to
    copy it. A shared race opens its state page at the race and holds it
    there while the page above it draws (`kyc-state.js` `holdPlace`, until
    the reader moves): it once landed 3,000px short on a phone.

97. **The search answers what a reader types about government, from the
    data the page about it shows, and never guesses.** "governor", "Texas
    AG", "Secretary of Labor", "Travis County", "Texas House", "Fifth
    Circuit" and "Missouri Amendment 3" found nobody, or a challenger whose
    text held the word (GRID-07; the owner's request of 2026-10-19).
    `assets/kyc-search.js` reads such a query and answers above the cards,
    grouped by kind (offices, places and bodies, courts, ballot questions),
    each answer a link to the page about it: the state page's government
    section, an official's dialog, a court's page, a county by its Census
    code, a legislature's chamber, a committee's row in the Congress guide
    (`#committee-<code>`), a question on its state page
    (`#measure-<ST>-<n>`). Its data is what those pages read
    (`stategov.js`, `federal.js`, `measures.js`, the profiles' leadership
    posts, rule 68) and `data/search.js` (`kyc/search_index.py`) for what
    none of them holds: the legislatures by their own names
    (`government_maps.legislature_title`, the legislature page's title),
    the county maps' names, the guide's committees with their leads by
    `pages.committee_leads`, the tribal directory's governments. It is
    generated, signed, stamped and compared by `verify` (rules 18, 76), and
    loaded only when a query is typed; `measures.js` only when one names a
    question. An office says who holds it only where the state's page names
    them (`KYC.answers.namedHolder`, one test for the answers and the
    "Other officials" block), and its 2026 race only as the election
    office's list, labelled as such, with what a cited source says of the
    holder (rule 79). Nobody outside Congress becomes a profile (rule 27).
    A word is matched whole: "Proposition 50" is not Proposition 5, and
    "3.5%" in North Carolina's question title is not "Amendment 3". A short
    form readers write is read ("Calif.", "S.D.N.Y.", "Lt. Gov."), but in
    the answers a two-letter code that is a word ("oh", "in", "va") beside
    another word is a state only typed in capitals (rule 5), and changing
    only the capitals redraws them; the grid still reads a code typed alone
    as the state. "DNC" is not North Carolina's courts, "Doe" is not the
    Department of Energy (only "DOE" is), and "Mich" alone is a name being
    typed, not Michigan. No fuzzy match: "Govenor of Ohio" names nobody,
    since a near spelling can put one person's office on another (rule 3).
    A word too broad ("judge": 1,461 judges) suggests narrower searches; a
    local office ("mayor") says this site names no local officials and links
    the county pages, which hold a website only where the Census listing
    gives one and its check did not withdraw it (rule 78); "Texas county
    judge" is Texas's local offices, never Texas County, Missouri. A state
    legislature's leader ("Texas House speaker") is the chamber's page and
    the words that this site names no legislature's leaders. "Texas House"
    is the state's chamber and its U.S. House seats both: the answer says
    the cards are the latter. A seat's title before a name ("Senator
    Warren", "Rep. Crockett") is read off the query and ranks that
    chamber's sitting members by the name; it is never added to a profile's
    text, where "Con" typed on the way to a name matched every member. "Ohio
    delegation" and "Ohio congressman" ask who represents the state, so
    they list its sitting members alone (rule 27).

    The review of the first version found the answers saying what the site
    never read, each now refused and tested over every case in the data:
    Alabama's Supreme Court, whose site could not be read, was "0 members
    listed by the court" and its page "names no chief justice" (rules 19,
    57: it says why, as the state page does); Maine's and Pennsylvania's
    ballots, for which no official list was found, held "no statewide
    question called Question 1" (only a list read answers a question); the
    every-state list named Hawaii's acting lieutenant governor as its
    holder (the title the page gives is shown); Arizona's new lieutenant
    governor, on the ballot for the first time, was "no such office", and
    "33 on the ballot" sat beside "34 elect it" (one test, `onBallot`, for
    every count: rule 73); "DC governor" and "Puerto Rico attorney general"
    were titled as offices the page holds (rule 75); and a court the
    answers named was offered again as a judge sharing its name ("Court"),
    since a query the answers read drops surname-only namesakes. Notes that
    count the ballot are in the past tense from the day after the election.
    Measured on a 4x and 6x throttled phone, a keystroke costs what it did
    before (rule 45).

99. **On a phone a big state's races are rows, and a row says what its race
    says.** California's page was 92 screens once drawn, its district
    squares 13,900px down, every race's head repeating "Primary held June 2"
    and "Top-two primary" (VISUALS-15, measured at 390px, CPU 4x). Below
    1000px a state with more than four races opens with "Find your race"
    and folds each race to an `<h3><button aria-expanded>` row
    (`KYC.cards.raceRow`) over its section, which stays in the page as
    `hidden="until-found"` so find-in-page and the page's search reach it;
    the stylesheet's `[hidden]` rule exempts it, since `display: none` would
    hide it from find. A row's words come from the race's own helpers only:
    the holder clause its "Held by" line uses (`heldByWhat`), the open seat's
    badge (`openSeatWhy`), the vacancy record, each person's card words
    (`KYC.standing`), the results' unprofiled names, and the head's own count
    badge (rule 73); the unsettled are listed apart (rule 62).
    `rowProblems` in the render suite holds every row to its section on ten
    states, on the campaign clock and after Election Day. Every way to a race
    (a link, a square, the select, the lookup's answer) opens it; a turned
    tablet moves the borrowed parts, never redraws them. 1000px and wider,
    the page is as it was. The review found three things the rows made
    visible. The select named each district's holder from the frozen
    record, so on the January rehearsal it put Barry Moore on AL-1 after he
    went to the Senate; it now names whoever sits for that district, as the
    delegation does (rules 27, 67). The open seat's hover said "Byron
    Donalds is not on the November ballot", which rule 61 forbids; a
    holder out of the race now reads in their card's words, with the
    other office they are running for. And a smooth scroll past the
    delegation's cards (content-visibility) stopped every jump 500-950px
    short of its race, so every jump on the page now scrolls at once.
100. **A legislator's portrait is the legislature's, named beside them,
    and a seat's file is dated before it is believed.** 1,022 of 7,323
    state legislators had no portrait (audit 2026-10-17, STATEGOV-13;
    the photo research of 2026-10-19): Open States stored none, a search
    thumbnail, or an address the legislature had since moved. Most
    legislatures publish one all the same. `kyc/legphotos.py` reads it
    only from a page or record the legislature serves for that member,
    reached by its own key for them or by chamber and district with the
    surname agreeing, and only where the legislature names them beside the
    image - the record naming the file (Montana's roster, New Jersey's
    `PictureText`, Indiana's lpid), the alt text with their given name,
    the file name with their surname, or the member's own key from the
    page's address (the file's own name, never a folder's: Florida keeps
    member-uploaded event photographs under a folder named by the member's
    id). A templated alt naming only a surname is no evidence: the Florida
    House alt-texts one album photograph with each page's member, so
    nothing is taken from an album or a gallery, and one file offered on
    two members' pages is neither's. The page is the member's own, for
    their chamber: New Mexico's sponsor code opens with it ("HFIGU",
    "SFIGU"), and five senators were read from their House pages, headed
    "Former Representative", until `legislature.chamber_of` read it. The
    words are kept as `evidence`, and `build` fails a shown
    entry without them, whose evidence does not carry the member's
    surname, off the legislature's host, or over the caps. A file keyed by
    the seat (Louisiana's `rep<n>.jpg`, Connecticut's `legpics/<code>`,
    California's `assembly_member_02.jpg`, Nebraska's `dist01.jpg`, and
    Missouri's Senate `Mosley13.jpg`, surname and seat together, which a
    successor of the same surname would inherit) can still be the predecessor's:
    it is shown only when the server dates it on or after the member's
    arrival less `SEAT_MARGIN_DAYS` (members-elect are photographed), and
    never while the file is unchanged since it showed someone else
    (`seatFiles`). Connecticut's Melissa Osborne is withheld that way: the
    file is from 2023 and her record from 2025. Only a rendition the source
    itself offers is taken - no image service (owner, 2026-10-19) - the
    lightest within 300 KB and 1,200 px where there is one. Where the
    legislature offers only heavier files (17 of Indiana's 30, most of
    Vermont's), they were left out until 2026-10-25; the first `legphotos`
    stopped its checks (a landscape frame, a seat file's date) at the
    weight, so they had never been checked as theirs. Now the lightest
    offered is taken, marked `heavy`, after every check any file gets (a
    seat file told apart by its first bytes and length, since its whole
    hash is not read), and shown as a smaller copy made here: 36 more
    legislators with a portrait (rule 101: the owner relaxed "no
    resizing"). A portrait the card shows, its or Open States's, that is
    over the caps is shown as that copy; a landscape frame is
    not a portrait (rule 38). `legphotos` reads no party caucus's pages
    (Michigan's only portraits are theirs), but a caucus's file Open
    States lists for its own member is shown credited to the caucus (rule
    87, the owner's decision of 2026-10-25), and no archived copy of a
    file the legislature stopped serving:
    Kansas's pages name a file that answers 404, and are read again each
    run so a restored file is shown. A host that answers nothing three
    times running (Maine's) is not asked again that run, and pages drawn by
    script (Georgia, South Dakota, Utah) are listed by the command as
    unread, never as unpictured (rule 8). Each card credits
    `Photo: <legislature>`, linked to the page, and so does an Open
    States portrait the legislature's own host serves: in Vermont's
    two-seat districts one card was credited and its neighbour, from the
    same folder, was not. The review of the first build found more:
    - A date is only a file's when the server keeps one. California's
      Assembly answers every `assembly_member_NN.jpg` with one deploy's
      Last-Modified (`UNDATED_SEAT_HOSTS`), and Louisiana's House rewrote
      some fifty seat files within twenty seconds on 2024-05-15, for
      members seated since 2016. Seat files a host wrote together
      (`batches`) date a file only when the copy fell near the member's
      arrival, and a shown seat file must carry the full stamp.
    - Kentucky keys its files by seat too (`house12.jpg`, Senate
      `senate137.jpg` for seat 37), and `seat_key` missed them; a chamber's
      word before the number is a seat now. A seat file is shown only for
      the chamber and district it was read for.
    - The legislature saying a member has left is not a photo problem:
      New Mexico's page for Andi Reeb is headed "Former Representative",
      Ohio's directory lists D.J. Swearingen's seat as vacant, and Open
      States seats both. Such a page gives no photograph, and `build`
      warns `legislator-not-seated` so the roster is checked (rules 16,
      51).
    - One file shown for two members fails the build, across runs and
      recipes, and an initial counts only when written as one: "A photo of
      Representative Smith" names no Andy.
    - The same holds of Open States's own files, which the credit above
      made the legislature's word: it gave Arkansas's Ashley Hudson the
      file the Arkansas General Assembly serves for Andrew Collins, and her
      card showed his face over "Photo: Arkansas General Assembly". A file
      it gives two members of one legislature is shown for neither
      (`statelegs.mark_shared_images`, in memory, never written to the
      cache), `build` warns `legislator-openstates-photo-shared`, and
      `legphotos` reads each one's own (PR #133 review). The credit names
      the hosts the legislature's pages name for its files
      (`EXTRA_PHOTO_HOSTS`: New Jersey's pub.njleg.gov, Ohio's
      legislature.ohio.gov), or a district's two cards disagree again.

101. **A heavy portrait is shown as a smaller copy made here, of exactly
    the photograph the page already shows.** The legislature pages drew
    every portrait straight from its host in a 56x70 box: the Oklahoma
    Senate's run 9 to 12.5 MB each (one chamber's list was some 300 MB on
    a phone), Connecticut's House Democrats' 4 to 8 MB, the White House's
    up to 3.5 MB (measured 2026-10-25). The owner's decision that day,
    "more content is better than strict rules", relaxes only what cost
    weight or coverage - rule 87's "shown all the same" and rule 100's "no
    resizing" - and nothing that guards whose photograph it is. So
    `photocopies` (`kyc/photocopies.py`) copies only an address a record
    already shows by a route the rules allow (a legislator's `image`, the
    White House's `photo`, an NGA headshot, an officer's `photo`, a
    justice's from the court's pages, a statewide candidate's, a profile's
    first portrait), never a Wikimedia file (rule 42): no new route, no
    search, no address built from a name. Hosting a copy is another act
    than linking a file, and the decision was for official photographs: a
    legislator's is copied only from the legislature's own host or a
    government's (`.gov`, `.mil`, `state.XX.us`; `photocopies.may_copy`)
    or the member's own party caucus's in `legislature.CAUCUS_SITES`
    where the card credits the caucus (`photocopies.caucus_own`, rule
    87), a profile's portrait (kind "person") the same way - a
    government's host, the legislature's, the caucus's, or an office's
    own - and a justice's or a statewide candidate's only from a
    government's host or the court's own (its roster's host) - a
    candidate shown the holder's office photograph as the holder's card
    is - never a news organisation's, a party's or a campaign's file.
    The first version copied four campaigns' portraits (Mary Silva's,
    Michael J. Quirk's, Mark Nair's, Jonny Larsen's) though this rule
    said it would not; they are drawn from their own host again, in a
    rendition it offers or at full size and said (`portraitHeavy`), and
    their copies were removed (2026-10-25). One walk of what
    `stategov.js` shows (`photocopies.stategov_photos`) serves the build,
    the checks and the weighing. Open States also lists news sites',
    campaigns', party sites' and image CDNs' photographs - the Chicago
    Tribune's, Gannett's, NPR's, Squarespace's - and the first version
    hosted 148 copies of them; those stay drawn from their own host, as
    before, and the build counts them. It weighs each with a
    ranged GET (HEAD lies, rule 51), one request a second to each host,
    and copies those over 300 KB or 1,200 px: the downloaded file drawn
    once in headless Chrome (`tools/make_photo_copies.mjs`, served to it
    from 127.0.0.1) with the browser's decoder and EXIF orientation, white
    under transparency, smoothing "high", scaled down - never up - to just
    cover three times the largest CSS box a page draws that kind in
    (`BOXES`, read back from `kyc.css` by the tests; phones are DPR 3), a
    JPEG at 0.86. Nothing is cropped, retouched or sharpened. A copy
    lives under `photos/` named by its own hash and is listed in
    `data/photo_copies.json` (hand-editable) with its original's bytes,
    pixels, sha256, ETag, Last-Modified and day read, and how it was made.
    It is never made again while the original's sha256 is unchanged:
    Chrome versions encode differently and the build must stay
    reproducible from committed files (rule 18). An original that changes
    is read again, and its old copy is withdrawn at once, before the new
    one is made and even when the file cannot then be downloaded (the
    first version kept it until a download succeeded), so no copy of a
    predecessor's photograph outlives its file (rule 100's seat files);
    the copy comes back only on the very same hash, as when a server's
    machines give one file two ETags. A copy is tied to the people it was
    made for, not only to its address (`copy.for`, a person's key: a
    legislator's id, a governor or officer by name, never a seat): a seat's
    file that passes to a successor kept showing the predecessor's copy
    under the successor's name until the address happened to be read again,
    up to two weeks, and January seats new members. A record not in `for`
    is shown the original, and its address is read again at once, whatever
    its age, whole and never on its validators; the copy becomes theirs
    only on the very same hash. A legislature's own photograph (rule 100)
    is copied only where this cache read the file `legphotos` weighed, the
    same length and day of Last-Modified (`photocopies.expected`), and
    `legphotos` tells a heavy seat file apart by its first bytes and its
    length, so one unchanged since it showed someone else is withheld
    (tested). One answering 404 or 410 twice is gone
    and its copy with it; a refusal, a reset, a truncated file Chrome
    cannot decode (two of Georgia's stop at exactly 1 MB) concludes
    nothing (rule 8), and Maine's host, which refuses this machine's TLS,
    is listed as unweighed, never as light. A run is a batch, oldest
    first, inside a time budget (rule 78) that counts Chrome's time too:
    the weighing stops early enough to leave the copy maker its share, is
    saved before Chrome starts, and the maker starts no job past the
    deadline. The refresh runs one after every step that sets a portrait;
    the people it reads are the last build's, so a campaign portrait first
    set in the same refresh is weighed by the next one. The record keeps
    its original and gains `photoCopy: {src, of, ofBytes}`; every page
    draws it through one helper (`KYC.photoSrc` / `photoAttrs` /
    `portraitSrc` / `copyOf`, from `KYC.siteRoot()` at any depth, stamped
    `?v=` with the copy's hash, rule 76), and a copy that fails to load
    gives way to its original (`KYC.retryOriginal`, one listener's word for
    every module's) - a White House photograph to the White House's own
    smallest rendition of it, never the heavy file - and every note on
    the page calling it a copy goes with it. The credit stays the
    original's, adding "a smaller copy made by this site of the original
    file (12.4 MB)", linked to it with its weight (`KYC.copyCredit`). An
    Open States portrait off the legislature's host credits no one: "Photo:
    from" a host, "as listed by Open States", copied or not - the first
    version printed "Photo:" and the bare host on its copies, read as whose
    photograph a CDN's or a newspaper's file was. A share page unfurls
    with the copy at its absolute address on the one hostname (rule 21).
    `verify`, `build` and `build --check` fail a file under `photos/` the
    manifest does not list, a listed copy missing or not its hash, one
    that does not record whom it was made for, one not its original's
    shape or not the pixels the manifest gives, a copy larger than its box
    or than its original, of a light or a Wikimedia file or a legislator's
    off a government's host, shown for another address or person than its
    own or without a credit; they count the originals still over the caps
    with no copy, and those not yet weighed, by kind. The first runs made
    1,557 copies; after the review's scope, 1,409 copies (1,383
    legislators', 15 of the White House's, 11 of campaigns') stand for
    originals that weigh some 2.4 GB, in 14.0 MB. 36 of them are
    legislators `legphotos` used to leave out as offered only over the
    caps, now checked as theirs and shown (rule 100). Merged with the
    nominees' portraits (PR #134) and the justices', attorneys general's
    and statewide candidates' photographs (PR #135), 1,402 copies stand
    (1,383 legislators', 15 of the White House's, 4 of campaigns'): ten
    campaign copies went, their profiles now showing a rendition the
    campaign's page lists, and no justice's or statewide candidate's
    photograph on a host this site copies from was over the caps; 35
    justices' (Photon's, a CloudFront's, Illinois's Azure storage) are
    drawn from their own host. The same day's photo
    research found five of the justices' official portraits on Commons
    older than the Court's current ones; the credit says the year
    Commons' `DateTimeOriginal` gives ("Official portrait, 2005"), read
    with the author and licence, and nothing where Commons names no single
    year (`portraits.year_of`, `judge_links.dated`); every other Commons
    photograph's credit now says its year the same way (rule 87). With
    the campaigns' four copies removed, the two Connecticut photographs
    refused (rule 38) gone with them, and eleven more legislators' made
    where the card now credits their caucus, 1,407 copies stand (1,392
    legislators', 15 of the White House's), for originals of some 2.4 GB,
    in 13.4 MB.
    An election office's guide that prints a candidate's photograph with
    no address of its own - Washington's voters' guide (base64 inside its
    JSON), Alaska's statement PDFs, Oregon's pamphlet (JPEG 2000 inside
    county PDFs) - is shown from a file hosted here, by the owner's same
    decision (official guides' photographs with no address of their own,
    hosted as unmodified copies, credited and sourced). `guidephotos`
    (`kyc/guide_photos.py`) writes it under `photos/`, named by its own
    hash, and lists it in the manifest's `hosted` table with how it was
    taken (`method`: "unmodified", the very bytes the JSON or PDF holds; or
    "decoded", for Oregon's, whose JPEG 2000 no browser draws: the
    reversible 5/3 coding decoded losslessly by `kyc/jpx.py`, standard
    library only, and written as a PNG with the codestream's hash and the
    decoder named - its pixels matched Chrome's own PDF renderer, PDFium,
    one for one on every photograph shown, 2026-10-25, and a test decodes
    one pamphlet codestream, kept in `tests/fixtures`, to the very pixels
    hosted for him), the guide's page
    and the JSON or PDF address, sha256, bytes, pixel size, the day read
    and whom it shows (`for`). The checks run both ways: a file under
    `photos/` the manifest does not list, a listed file missing or not the
    bytes or pixels it gives, an entry that does not say how, from where,
    when or for whom, a record showing a hosted file the manifest does not
    hold for it, or showing it with no credit, fails `verify`, `build` and
    `build --check`. Every page addresses it from the site's root at any
    depth (`KYC.photoHref`). Three over the caps (John Duresky's 4.2 MB;
    Dave Bronson's and Candi English's, over 1,200px) are shown as smaller
    copies made from that file the way every copy is made, at once by
    `guidephotos` rather than at the next refresh, and a copy that fails
    gives way to the hosted file; with them, 1,410 copies stand (13.5 MB),
    beside the 18 files hosted here. A decoded file's credit says this site
    converted it, as a copy's says it is one (rule 87). Of the 20 nominees and
    statewide candidates in the three states who showed no photograph on
    2026-10-25, 18 have one: Bill Hill's statement holds a CMYK JPEG no
    browser draws as printed (rule 24), and the pamphlet pictures no Jason
    Faler.

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
- A chart is boxes and page text (rule 46), never a third-party script, and
  its colours are tokens: a party's colour only for a person's or a seat's
  party (a holder, a candidate in the markets and polls), `--cat-*` for kinds that are not parties, one neutral ink for judges, races
  and navigation. A layout the page cannot work out cheaply (the House tiles)
  is computed in the pipeline (`kyc/tiles.py`), and anything that draws is
  timed throttled (rule 45). README's "Charts" lists them.
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
  well as the people files.
- Do not hard-code a total that the data determines. A test asserting `472`
  races carried a comment reading "435 + 6 + 35", which is 476; nobody had
  reconciled the two, and the number moved the moment a vacant seat was
  filled. Assert the structure and account for the difference.
