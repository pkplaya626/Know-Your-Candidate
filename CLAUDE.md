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
data/statewide_officers.json ─┤   (lieutenant governors, secretaries of state: NLGA, NASS)
data/partisan_composition.json ┴─> kyc/ ──> candidate_profiles_site/
                                             data/profiles.js   (profiles, races, build meta)
                                             data/geo.js        (SVG path data for the map)
                                             data/odds.js       (market prices, polling averages)
                                             data/government.js (the guide's maps: kyc/government_maps.py)
                                             data/stategov.js   (governors, chamber control, trifectas)
                                             data/legislature/*.js (one state legislature per state)
                                             data/local/*.js    (one state's counties and governments)
                                             data/districts/*.js (one district map per state)
                                             states/*.html      (generated, one per state)
                                             districts/*.html   (generated, one per state)
                                             government/*.html  (generated: the guide, kyc/government_text.py)
                                             legislature/*.html (generated, one per state)
                                             counties/*.html    (generated, one per state)
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
  `partisan_composition.json` and `statewide_officers.json` are caches, but
  they *are* hand-editable. `stategov.js` is generated from the last four.
- `index.html` / `map.html` are **hand-maintained templates**. The build reads
  them only to check they load the right scripts in the right order; it never
  rewrites them. `states/*.html`, `districts/*.html`, `government/*.html`
  and `sitemap.xml` are the opposite: generated from `kyc/pages.py` (the
  guide's words from `kyc/government_text.py`) on every build, never
  edited by hand, and `verify` fails when one on disk is not what the
  template would write.
- Shared page behaviour belongs in `assets/`, not in a page. Neither page
  contains an inline `<script>` block.

## Commands

```bash
python build_profile_site.py                  # build (offline)
python build_profile_site.py build --check    # validate only
python build_profile_site.py verify           # committed data matches sources
python build_profile_site.py congress --check # roster vs Congress (offline)
python build_profile_site.py congress --apply # write newly seated members in
python build_profile_site.py geo              # regenerate map geometry only (both maps)
python build_profile_site.py congress         # refresh membership (network)
python build_profile_site.py field --check    # who is running, from the FEC
python build_profile_site.py disclosures      # House and Senate disclosure links
python build_profile_site.py results          # who is still in, from Wikipedia
python build_profile_site.py campaigns        # campaign websites from FEC committees
python build_profile_site.py enrich           # fill gaps; check every campaign site
python build_profile_site.py odds             # market prices and polling averages (writes odds.js)
python build_profile_site.py census           # local governments by state (Census of Governments)
python build_profile_site.py statelegs        # every state legislator (Open States), matched to districts
python build_profile_site.py localgov         # every local government (Census listing), checked
python build_profile_site.py executives       # every governor (NGA), and NCSL's party counts
python build_profile_site.py officers         # lieutenant governors (NLGA), secretaries of state (NASS)
python tools/fetch_legislative_maps.py        # state senate and house boundaries (Census, network)
python -m unittest discover tests             # 765 tests, no dependencies
npm install && npm test                       # 999 real-DOM checks (needs jsdom)
```

Only `fetch`, `portraits`, `finance`, `field`, `disclosures`, `results`,
`campaigns`, `enrich`, `odds`, `census`, `statelegs`, `localgov`, `executives`,
`officers` and `congress` touch the network, as do the two `tools/fetch_*_maps.py` scripts. Run the
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

20. **Check attribution, do not trust it.** An FEC candidate id encodes its
    own office and state, so `validate.check_finance` compares every figure
    against the profile it is about to appear on. Money shown against the
    wrong person looks entirely normal on the page.

21. **The public hostname has one source of truth.** `CNAME` is what GitHub
    Pages serves from; the canonical links, `og:url`, `robots.txt` and
    `sitemap.xml` must agree, and `verify` fails when they do not. A
    half-finished rename looks completely normal locally. Never put a hostname
    in a new file without adding it to `emit._HOST_REFERENCES`.

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

24. **Do not guess portraits for filed candidates.** The bioguide -> Wikipedia
    mapping cannot pick the wrong person; a title guess for one of 1,979
    largely unknown people can, and "Michael Smith" resolves to a stranger.
    `portraits.resolve_all` skips `source == "fec-field"` and
    `title_is_about` rejects a resolved title that does not contain the
    person's surname - which is how a photograph of an Iran war protest ended
    up on Brian McGinnis's profile via a redirect.

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
    was rejected a second time.

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
    good one closes it.

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
    breaks the property that keeps an unreviewed commit safe.

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
    what can change (counts, decisions, agency names) and move `REVIEWED`.
    Who holds an office is never typed in: the Congress page renders
    committee leads from the rosters, and a committee's minority lead is
    found by the seat's `side`, not its title.

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
    map" - New Hampshire's floterial seats, Maine's tribal representatives.
    A nearest-name match would put someone on the wrong district, and a map
    makes that look entirely normal. A seat with nobody listed is "nobody
    listed", never "vacant" (rule 19).

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

55. **An association's roster is the authority on its members, and only
    on them.** NASS's member for Alaska, Hawaii and Utah is the lieutenant
    governor; NLGA's for Arizona, Oregon and Wyoming is the secretary of
    state. Where two rosters name one office's holder they must name the
    same person of the same party, or the page names both and shows neither
    (`officers.overlaps`): Hawaii's lieutenant governor, on 2026-10-05. Compare
    names without honorifics ("Hon.", "High Chief"), strip invisible
    characters (one RAGA card carried a zero-width space, and two cards for
    one state then disagreed), and drop a card whose "name" is a state:
    RAGA prints "Maryland" and "Vermont" where it has no member. RAGA also
    lists a North Carolina attorney general who lost the 2024 election, so
    an attorney general's name needs the office's own confirmation.

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
  inline `<script>`.
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

## Conventions

- Standard library only in `kyc/`.
- Normalisation helpers are total: they accept `None`, `"nan"`, `""` and always
  return something display-ready.
- Add a regression test for any data bug fixed — `tests/test_pipeline.py` for
  core parsing, `tests/test_enrichment.py` for provenance/portraits/FEC/races,
  `tests/test_geo.py` for map geometry, `tests/test_districts.py` for the
  before-and-after district maps, `tests/test_site.py` for summary
  figures, emitted files and page wiring, `tests/render_test.js` for anything
  visible on a page.
- When changing profile fields, update the field tables in `README.md`.
- Builds must stay reproducible under `SOURCE_DATE_EPOCH`, for `geo.js` as
  well as `profiles.js`.
- Do not hard-code a total that the data determines. A test asserting `472`
  races carried a comment reading "435 + 6 + 35", which is 476; nobody had
  reconciled the two, and the number moved the moment a vacant seat was
  filled. Assert the structure and account for the difference.
