# Know Your Candidate

A non-partisan, data-driven directory of the 119th U.S. Congress and the 2026
midterm races. A Python pipeline turns curated CSV rosters into JavaScript data
files that two static HTML pages read.

The site ships **no third-party CSS or JavaScript**. No framework, no bundler,
no CDN, no web fonts — open `index.html` off disk and it works.

## Quick start

```bash
python build_profile_site.py                    # rebuild the site data
open candidate_profiles_site/index.html         # or just double-click it
```

Python 3.9+ and the standard library. Nothing to install.

## Commands

| Command | What it does |
|---|---|
| `python build_profile_site.py` | Build `data/people/*.js`, `data/geo.js` and `data/districts/*.js` |
| `… build --check` | Validate only; write nothing |
| `… build --strict` | Refuse to write if validation finds an error |
| `… build --json` | Emit the validation report as JSON |
| `… verify` | Check the committed data still matches the sources |
| `… congress` | Refresh the membership snapshot (with contact details, accounts and committee rosters) and report roster drift; also writes `data/departed_members.json`, everyone `legislators-historical` says left the sitting Congress, for the grid's search |
| `… congress --check` | Report drift from the committed snapshot; no network |
| `… congress --apply` | Write the drift into the roster CSVs: add the newly seated, renew terms, archive whoever the records say left |
| `… congress --apply --snapshot FILE` | The same from a given snapshot, with no download (a rehearsal; `--historical FILE` for legislators-historical) |
| `… field` | Refresh the FEC register of everyone running in 2026 |
| `… field --check` | Report the field from the committed cache; no network |
| `… census` | Count each state's local governments from the Census of Governments (`--check` reads the cache) |
| `… statelegs` | Every state legislator from Open States, matched to the district maps, each portrait checked (`--check` re-matches the cache; `--images-only` checks the portraits again without refetching; `--no-images` skips them) |
| `… legphotos` | The portraits of the legislators Open States has none for, from each legislature's own pages and records, writing `data/legislator_photos.json` (`--check` reports the cache; `--state ST` reads one state; `--force` reads entries younger than 14 days again) |
| `… localgov` | Every local government from the Census listing, checked against the published counts |
| `… localgov --check-sites` | Open every website the listing gives a local government - many hosts at once, one request at a time per host - and record what each is now in `data/local_sites.json` (hand-editable; a stopped run resumes; `--recheck VERDICT` looks again at one kind, `--states`, `--limit`, and `--max-minutes`, a time budget after which it opens nothing new, saves and stops) |
| `… executives` | Every governor from the NGA, and NCSL's count of each legislature's parties (`--check` reports the caches) |
| `… officers` | Every lieutenant governor (NLGA) and secretary of state (NASS), cross-checked where the rosters overlap |
| `… federal` | The President, the Vice President and the Cabinet: who holds each office, from the White House's pages, each office's own page and the Senate's roll-call votes (`--check` reports the cache) |
| `… judiciary` | Every sitting federal judge, from the Federal Judicial Center's directory, and the Supreme Court's members as the Court lists them; the territorial courts' judges from each court's own site; each judge's Wikipedia article and portrait through the FJC id on Wikidata. A short read keeps the last cache (`--check` reports it) |
| `… oge` | The financial reports the President, the Vice President and the Cabinet filed with the Office of Government Ethics, attributed by office and checked against the filer each report names (`--check` reports the cache). See [Financial disclosures](#financial-disclosures) |
| `… members` | Each sitting member's education and earlier careers (the Congressional Directory, by their official web address; their Wikipedia infobox by their id where the Directory has none), the issues their official website lists, a checked contact page and their offices at home (`congress-legislators`); a read that concludes nothing keeps the last one (`--check` reports the cache, `--id` re-reads one site, `--all` every site however recent its read, `--no-sites` skips the sites). See [A member's biography and platform](#a-members-biography-and-platform) |
| `… votes` | Every roll call of the 119th Congress, from the House Clerk's and the Senate's own XML records, attributed to members by id: one request a second, saved as it goes and resumed by the next run (`--chamber`, `--limit`; `--check` reports the cache). See [How members voted](#how-members-voted) |
| `… history` | The public offices each person has held: Congress from congress-legislators, every other office from Wikidata where the person's own Wikipedia article gives the same office the same years; a short read keeps the last cache (`--check` reports it). See [Public offices held](#public-offices-held) |
| `… voting` | Each state's and D.C.'s official pages for checking registration, finding a polling place, voting absentee or early, and registering, as NASS's "Can I Vote" lists them; refused unless all 51 are there. Then opens every link shown, NASS's and the curated results, sample-ballot, vote.gov and territory pages alike |
| `… courts` | Each state's highest court and its members, read from the court's own roster |
| `… seats` | Each seat's last election, from the Clerk of the House's official statistics, checked against MIT's Senate returns or each state's Wikipedia page; a failed read keeps the cache (`--check` reports it). See [The seat's last election](#the-seats-last-election) |
| `… outside` | Independent expenditures for and against each candidate, from the FEC's Schedule E totals by candidate id (`--check` reports the cache). See [Outside spending](#outside-spending) |
| `… tribes` | Every tribal government and its leader, from the BIA's Tribal Leaders Directory, by the state of its office; refused unless every row the service counts comes back once (`--check` reports the cache) |
| `… disclosures` | Link members to their filed financial disclosures (House Clerk, Senate eFD) |
| `… results` | Read each state's primary results from Wikipedia: who is still in |
| `… results --check` | Report the results from the committed cache; no network |
| `… campaigns` | Look up campaign websites from each candidate's FEC committee (needs `FEC_API_KEY`) |
| `… campaigns --check` | Report campaign-site coverage from the committed cache; no network |
| `… enrich` | Fill gaps for everyone still running from their Wikipedia infobox and campaign site, and check every linked campaign site |
| `… enrich --check` | Report what the committed cache fills; no network |
| `… enrich --refresh` | Read everyone again, not only those read more than six days ago |
| `… enrich --unreachable` | Read again only the committee sites the last read could not reach (trying "www." added or taken away), and check where every ballot-page Wikipedia link leads |
| `… odds` | Kalshi and Polymarket prices for each 2026 race and for control of both chambers, and the polling averages each Senate race's Wikipedia page lists; writes `data/odds.json` and `data/odds.js` |
| `… odds --check` | Report market and polling coverage from the committed cache; no network |
| `… geo` | Regenerate only the map geometry: the national map and the before-and-after district maps |
| `… fetch` | Refresh DW-NOMINATE scores from Voteview into the roster CSVs |
| `… portraits` | Resolve and check a portrait URL for every profile |
| `… portraits --refresh` | Re-resolve every portrait, not just the missing ones |
| `… finance --limit N` | Look up FEC campaign finance totals (needs `FEC_API_KEY`): members, then every challenger still on a ballot by their own filing (`--field-only` for the second part alone) |
| `… refresh` | `fetch`, then `build` |
| `python tools/fetch_district_maps.py` | Rebuild `district_maps/`: every state's district boundaries, the new 2026 maps, and the towns to label (network) |
| `python tools/fetch_local_maps.py` | Rebuild `local_maps/`: every incorporated place, one point each, for the county pages (network) |
| `python tools/fetch_lookup_maps.py` | Rebuild `lookup_maps/`: every ZIP code area's share of each district and county, and the finer boundaries a location is placed on, for "Find who represents you" (network) |
| `python tools/fetch_court_districts.py` | Rebuild `data/court_districts.json`: which federal district court and division covers each county, from 28 U.S.C. 81-131 (network; `--check` reads without writing) |
| `python tools/rehearse_changeover.py --out DIR` | Rehearse the turn of the Congress on a copy in `DIR`, which must be outside the repository: December's specials either way, and the 120th Congress on January 4, each through `congress --apply`, the build, the strict check and `verify`. The memberships are fiction about real people and never leave `DIR`. CI runs it on every push, with the unit tests and the page checks on each copy; a scenario the data is already past is skipped |
| `python -m unittest discover tests` | The pipeline tests |
| `npm install && npm test` | Render every page in jsdom and drive the UI (3316 checks) |

`--root` and `--verbose` work on either side of the subcommand, so both
`--verbose portraits` and `portraits --verbose` do the same thing.

Only `fetch`, `portraits`, `finance`, `field`, `disclosures`, `results`,
`campaigns`, `enrich`, `odds`, `votes` and `congress` touch the network, with
the other refresh commands listed above. `build` and
`verify` are fully offline and read the committed caches and snapshot.

## How the data flows

```text
Cleaned_House.csv                        ─┐
Cleaned_Senate.csv                       ─┤
Congressional_Candidates_2026.csv        ─┼─> kyc/ ─> data/people/*.js ─┬─> index.html
Completed_Primary_Candidates_2026.csv    ─┤          data/geo.js       ─┤   (grid + races)
Late_Primary_Candidates_2026.csv         ─┘          portraits.json     └─> map.html
us_atlas_states_topo.json                ──> kyc/geo.py                     (partisan map)
district_maps/*.json                     ──> kyc/districts.py ─> data/districts/<st>.js
                                             ─> districts/<st>.html  (every state's map)
congress_snapshot.json                   ──> kyc/legislators.py
      ^ authoritative membership, used to reconcile the rosters above
```

The CSVs and the state atlas at the repo root are the source of truth.
Everything under `candidate_profiles_site/data/` is **generated** — never edit
`people/*.js` or `geo.js` by hand. They are committed so the site serves
straight from GitHub Pages with no build step.

The profiles are written in the files each page needs (CLAUDE.md rule 94):

| File | Holds | Loaded by |
|------|-------|-----------|
| `data/people/meta.js` | `kycBuildMeta`: the build's figures, its signature, each chamber's left-right scores (`chamberScores`) | every page with people, `ballot.html`, and the guide's Congress page |
| `data/people/index.js` | every profile without the fields in `emit.INDEX_LEAVES_OUT` (but a member's district offices where their card's "Contact office" calls one, `emit.INDEX_KEEPS_FOR_THE_CARD`), and every race | `index.html`, `map.html`, `states/index.html`; elsewhere on demand |
| `data/people/<st>.js` | one state's profiles whole, and its races | `states/<st>.html`, `districts/<st>.html`; on `ballot.html`, the states an answer is in, before it is drawn; elsewhere on demand (`KYC.loadPeople`) |

Each people file assigns `window.kycPeopleFile`, which `assets/kyc.js` takes
into `window.legislatorsData` and `window.kycRaces` (`KYC.people()`,
`KYC.races()`) as it arrives, filling the index's records in place. Every
file names its build (`build`), and a file from another build than the
page's `kycBuildMeta.signature` is refused and said on the page.

Both pages load their data with `<script src>` rather than `fetch()`, so
opening the HTML directly off disk still works (`file://` blocks `fetch`, not
`<script src>`).

Builds honour `SOURCE_DATE_EPOCH`, so output is byte-for-byte reproducible and
CI asserts that a rebuild changes nothing.

## The `kyc` package

| Module | Responsibility |
|---|---|
| `sources.py` | Find and read the roster CSVs |
| `normalize.py` | Clean values; parse states, districts, ages, currency; classify provenance |
| `overrides.py` | Hand-curated corrections (statuses, 2026 Senate seats) |
| `photos.py` | Runtime portrait fallback chain (safety net) |
| `portraits.py` | Build-time portrait resolution and checking |
| `fec.py` | Campaign finance from the OpenFEC API |
| `voteview.py` | DW-NOMINATE ideology scores: the first dimension, worded on its own left-right scale (never a party's name) with the Congress the score is from |
| `profiles.py` | Assemble profiles; derive 2026 election flags and field provenance |
| `races.py` | Group profiles into the seats they contest |
| `legislators.py` | The authoritative membership, and reconciliation against it |
| `candidates.py` | The FEC's register of who is running in 2026 |
| `disclosures.py` | Links to members' filed financial disclosures (House Clerk, Senate eFD) |
| `geo.py` | Decode the state atlas into SVG path data |
| `summary.py` | Chamber balance, election headline figures, per-state figures |
| `pages.py` | The shared page template, the state pages, the states directory and the sitemap |
| `share.py` | A share page for every profile (`p/<id>.html`) and race (`r/<raceId>.html`), and the plain lists the state pages are written with, in the profile dialog's status words (rule 96) |
| `government.py` | Know Your Government, the guide: renders its pages and refuses a broken link or an uncited section |
| `government_text.py` | The guide's words and the sources each section was checked against |
| `government_maps.py` | What the guide's maps say about each state, every value with its source |
| `census.py` | The Census of Governments' counts of local governments by state (the `census` command) |
| `statelegs.py` | Every state legislator, from Open States, matched to a Census district (the `statelegs` command) |
| `legphotos.py` | The legislators' portraits Open States lacks, from each legislature's own records, with the words that name the member beside each (the `legphotos` command) |
| `legislature.py` | Each state's legislature page data: projected districts, close-ups and the members in each |
| `localgov.py` | Every local government, county by county, from the Census listing (the `localgov` command), and the listing's abbreviations written out |
| `localsites.py` | Whether each local government's listed website still is one (the `localgov --check-sites` command), and what the build withdraws |
| `counties.py` | Each state's counties page data: projected counties, the governments in each, and every incorporated place joined to its government |
| `executives.py` | Every governor, from the National Governors Association's roster (the `executives` command) |
| `officers.py` | Lieutenant governors and secretaries of state, from their associations' rosters (the `officers` command) |
| `courts.py` | Each state's court of last resort and its members, from each court's own page (the `courts` command) |
| `stategov.py` | Who runs each state: governor, chamber control, trifecta, checked against NCSL |
| `ballot_measures.py` | The statewide questions on each jurisdiction's November 3 ballot, from the hand-edited cache `data/ballot_measures.json` read from each election office's own list; checks it and writes `data/measures.js` (rule 95) |
| `campaigns.py` | Campaign websites from each candidate's FEC committee |
| `enrich.py` | Fill filed candidates' gaps from their Wikipedia infobox and campaign site; check every linked campaign site |
| `oge.py` | The executive's financial reports from the Office of Government Ethics, by office (the `oge` command) |
| `history.py` | The public offices each person has held, from congress-legislators and Wikidata, corroborated by the person's own article (the `history` command) |
| `rollcalls.py` | Every roll call of the Congress from the House Clerk's and the Senate's records, each vote attributed to a member by id inside a term they served (the `votes` command); writes `data/votes/house.js` and `data/votes/senate.js` |
| `odds.py` | Prediction-market prices (Kalshi, Polymarket) and published polling averages for the 2026 Senate races |
| `validate.py` | Data-quality checks |
| `emit.py` | Write the data files atomically; verify the pages are wired up |
| `cli.py` | Argument parsing and command wiring |

## The front end

`index.html` and `map.html` are hand-maintained templates. The build writes
into `data/` and rewrites nothing in them but the version stamps on their
script and stylesheet URLs. It does check that each page loads the scripts it
needs, **in the right order** — every generated file assigns a global that
the page modules read as they initialise, so the wrong order renders an
empty site with no error anywhere.

Every local script and stylesheet URL, on every page, carries `?v=` and a
hash of the file's contents (`kyc/assets.py`). A browser that reloads a page
keeps scripts still in its cache, and GitHub Pages caches each file for ten
minutes: without the stamp, a reload just after a deploy ran the new page
with an old script, and the grid never drew. A changed file now has a new
URL; `verify` fails when a stamp is stale. Data files carry their content
signature the same way, except `data/odds.js`, which the twice-daily odds job
commits on its own.

| File | Responsibility |
|---|---|
| `assets/kyc.css` | The entire stylesheet: tokens, three themes, every component |
| `assets/kyc.js` | Theme, icon sprite, escaping, provenance, router, dialog helper, shell |
| `assets/kyc-profile.js` | The profile dialog, shared by both pages |
| `assets/kyc-cards.js` | Profile cards and race sections, shared by the grid and the state pages |
| `assets/kyc-senate.js` | The grid's Senate view: every seat by the year it is next decided, with the candidates for each 2026 seat |
| `assets/kyc-search.js` | The search's answers about government: offices and who holds them, places, bodies, courts, ballot questions (rule 97) |
| `assets/kyc-directory.js` | The grid: filtering, sorting, races |
| `assets/kyc-map.js` | The map: rendering, modes, delegation panel |
| `assets/kyc-state.js` | A state's page (folded to one row per race on a phone), and the directory of states |
| `assets/kyc-usmap.js` | The map of the states, drawn once for the partisan map and the guide's maps |
| `assets/kyc-guide.js` | The guide's pages: their maps, and what they show from the data (who leads each committee) |
| `assets/kyc-regionmap.js` | A map of any regions inside a state (legislative districts, counties), with labels, close-ups and an optional layer of dots |
| `assets/kyc-legislature.js` | A state's legislature page: chambers, districts, members |
| `assets/kyc-local.js` | A state's counties page: every county and every local government in it, and every city and town |
| `assets/kyc-stategov.js` | Governors, legislatures and trifectas: the map's three state views and every state page's section |

### What the search answers

The header's search finds people by name, a state or a district, answers a
ZIP code with the lookup, and lists officials who are not candidates apart
from the cards. It also answers what a reader types about government
(`assets/kyc-search.js`, rule 97), above the cards, grouped by kind, each
answer a link to the page about it:

| Kind | Examples | Leads to |
|---|---|---|
| Offices | "governor" (every state's), "Ohio governor", "Texas AG", "Lt. Gov.", "Ohio SoS", "candidates for governor" | The state page's government section, with the holder and, where the office is on the Nov 3, 2026 ballot, the election office's candidate list, labelled as its |
| | "President", "VP", "Cabinet", "Secretary of Labor", "HHS" | The official's dialog on the federal page (never a profile) |
| | "Speaker", "majority leader", "whip", "president pro tem" | The holder's profile, from congress-legislators' posts in this Congress |
| | "senators", "congressman", "delegate", "state senator 43215" | The Senate view, the sitting members, the lookup by ZIP code |
| | "Senator Warren", "Rep. Crockett", "Ohio delegation", "Ohio congressman" | The grid: that chamber's sitting members by name first; a state's sitting members alone |
| | "mayor", "sheriff", "school board", "Texas county judge" | A note that this site names no local officials, and the county pages that list each local government, with its website where the Census listing gives one and the site's check did not withdraw it |
| Places and bodies | "Travis County", "Cook County, IL", "Orleans Parish" | The county page, at that county (`#/?county=<Census code>`) |
| | "Texas House", "Ohio Senate", "General Assembly", "General Court" | The legislature page, at that chamber |
| | "Texas House speaker", "Ohio Senate majority leader" | The legislature page, at that chamber, and a note that this site names no state legislature's leaders |
| | "Armed Services", "Judiciary Committee", "ways and means" | The committee's row in the Congress guide, with its chair and minority lead |
| | "Cherokee Nation", "Oklahoma tribes"; "Cherokee" or "Dallas" alone where no profile answers | The tribal governments page, at that state's list; the counties of that name |
| Courts | "Supreme Court", "chief justice", "Fifth Circuit", "S.D.N.Y.", "Eastern District of Texas", "Texas federal courts", "Ohio Supreme Court" | The court's page, a justice's dialog, or the state page's highest court |
| Ballot questions | "Proposition 1", "Missouri Amendment 3", "SQ 845", "ballot measures" | The question on its state's page (`#measure-<ST>-<n>`) |

A word too broad to answer ("judge", with 1,461 sitting federal judges)
suggests narrower searches instead. Abbreviations readers write are read
(AG, SoS, Lt. Gov., Rep., Sen., SCOTUS, S.D.N.Y., Calif., Tex.); in the
answers, a two-letter code that is also a word ("oh", "in", "va") beside
another word is a state only typed in capitals, as "DOE" is the Department
of Energy and "Doe" a surname. Nothing is matched fuzzily: "Govenor of
Ohio" names nobody. An answer says only what the site read: a state court
whose roster could not be read says so, and names no members or chief; a
ballot with no official list found answers no question about it; an acting
officer is shown with the title the state page gives them.
What no file a page already loads holds - each legislature by its own name,
each state's counties by Census code, the guide's committees and who leads
them, the tribal governments - is `data/search.js` (`kyc/search_index.py`),
generated, signed and checked by `verify`. It, `stategov.js`, `federal.js`
and the judges' index load the first time a query is typed, and
`measures.js` only when a query names a ballot question.

Every view has a URL: `#/profile/<id>` for a person,
`#/?state=TX&chamber=Senate` for a filtered list, so any view can be linked and
shared.

### The site's frame

What a reader needs to trust a page about real people is the same on every
page, so it is written by one set of helpers in `kyc/pages.py`, and
`emit.check_nav` holds the two hand-maintained pages to them:

- **About & sources** (`about.html`, in every sidebar's Learn group): an
  independent, non-partisan project, its code and data public; no affiliation
  with, or money from, any campaign, party, candidate or government office,
  and no advertising; not an official election source or legal advice. A
  table of every dataset - its source, what it covers, when it is read again
  and when it was last read (`pages.DATASETS`, dated from each cache, or
  saying where a reader finds the date, `_NO_READ_DATE`), the member rosters'
  hand-kept biographies and the editorial decisions among them - and the
  refresh schedule (`pages.REFRESH_DAILY`, `ODDS_TIMES`; a test holds them to
  `refresh.yml`'s gate and `odds.yml`'s cron). Privacy as the code behaves:
  no cookies, analytics or accounts; two settings in `localStorage` (the theme
  and the last state viewed); images from the hosts that publish them, asked
  for with no referrer (`<meta name="referrer" content="no-referrer">`);
  "Find my district" and "Find who represents you" never send the location
  or the ZIP code. Accessibility: WCAG 2.2 AA as
  the aim, what is tested, the known limits. The licence: MIT for the code,
  CC BY 4.0 for the data.
- **Report a problem**: every footer, the profile dialog and an official's
  dialog link GitHub's issue form (`.github/ISSUE_TEMPLATE/correction.yml`),
  its `page` and `profile` fields filled from the query string. The link is
  aimed as it is followed (`KYC.reportUrl`), so it names the profile open at
  the time. About says the form needs a free GitHub account.
- **Where a status was read**: a race's card, the profile dialog's race and
  the map's state panel link the results page (`KYC.resultsSourceHtml`), with
  "not the state's certified count" as page text; names the results give with
  no profile are credited to their own source, the results pages or a
  Secretary of State's list, counted apart.
- **Each page's own sources, dated** (`pages.footer_html`): a legislature page
  dates Open States, a county page the Census listing, a court page the
  Federal Judicial Center and uscourts.gov, each from the cache's own record of
  when it was read (`pages.data_dates`; never `odds.json`, rule 41). A
  footer whose sources each carry their date (`footer_dated`: the federal hub
  and the courts) does not repeat it in its last line. The sidebar repeats it
  in one line with the link to About, because the grid's endless scroll keeps
  its footer out of reach. "Data built" is the reader's own calendar day of
  the build (`KYC.localDay`), never a UTC date in their future.
- **The header's tag names the section** (`pages.brand_sub`, from the
  navigation's own names, rule 75); only a page that loads the build's figures
  (`data/people/meta.js`) says which Congress.
- `404.html`, which GitHub Pages serves for any missing address at any depth
  (so its URLs start at the root), with the search and every section;
  `districts/index.html` ("District maps", linked from each district page)
  and `courts/index.html` ("Federal courts", where the navigation's entry of
  that name leads), so those folders answer. map.html's footer follows the
  state panel in the page, so a phone reads the panel first; on a wide screen
  a grid (`.map-body`) puts it under the map.
- Structured data: a `WebSite` with the grid's search (`index.html?q=`, which
  the router reads) on the home page, a `BreadcrumbList` on every generated
  page. Never `Person` markup. These blocks are the only inline `<script>`
  a page may carry (`emit.inline_script_problems`).
- `site.webmanifest`, `assets/apple-touch-icon.png` and `assets/icon-512.png`
  (from `tools/app-icon.html`), and the share card
  `assets/social-card.png` (from `tools/social-card.html`, whose hostname
  `verify` checks against CNAME). Neither image carries a number, a year,
  the Congress's number or a list of sources: they cannot be regenerated by
  the build.
- Share pages (rule 96): `p/<id>.html` for every profile and `r/<raceId>.html`
  for every race, each with its own title, description, canonical address
  and image (the person's photograph only where it came by a sourced route,
  otherwise the share card), the facts in plain text, and a link to the view
  that `assets/kyc-share.js` follows for a reader with scripts. Each status
  names the source the profile dialog credits; the description writes the
  seat in words ("member of the U.S. House for AL-4"); a race page marks the
  seat's holder. A page shared under an id its profile no longer has (a
  folded filing, a filer since seated) is kept as that profile's, never
  deleted. "Copy link" in the profile dialog and on every race section gives
  this address, by a phone's share sheet, the clipboard, or a selected field
  to copy from. The words are checked against the page code for every case
  of the status table (`tests/fixtures/share_status_words.json`, written by
  `share.write_status_table()` after a change to the words on both sides).
- Every page has a `<noscript>` line saying what needs JavaScript, and the
  state pages, the federal pages and the court pages carry their names in
  plain HTML that the scripts draw over; a state page's plain lists include
  its statewide questions (designation and title, each linked to its
  source) from the same record as `data/measures.js`. The legislature and county pages
  say they list nothing without it; a district map page points to its
  state's page.

### No third-party runtime dependencies

The pages previously loaded four: Tailwind's play CDN, an unpinned
`lucide@latest`, d3 and topojson-client — roughly 700 KB of JavaScript, one
unpinned, on a site whose Python side deliberately has none. The play CDN in
particular compiled CSS *in the browser* on every visit, which meant an
unstyled first paint and a page that could not be read offline. Tailwind's own
documentation says not to use it in production.

They are gone:

| Was | Now |
|---|---|
| `cdn.tailwindcss.com` | `assets/kyc.css`, hand-written |
| `unpkg.com/lucide@latest` | An inline SVG sprite in `kyc.js` (~20 icons) |
| `d3` + `topojson-client` + 82 KB inline TopoJSON | `data/geo.js`, decoded at build time by `kyc/geo.py` |
| Google Fonts (Roboto) | The system font stack |

CI fails if any of them come back.

### Accessibility

- No `user-scalable=no`. Blocking pinch-zoom fails WCAG 1.4.4.
- Cards, delegation rows and map states are real buttons with visible focus,
  keyboard activation and `aria-pressed` state. They used to be `<div onclick>`.
- The theme picker is a click-opened menu with Escape handling. It used to be a
  CSS `:hover` popup — unreachable by keyboard, erratic under touch.
- The map has a state picker in the sidebar, so its content is reachable
  without using the map.
- Skip link, labelled controls, live region on the result count, focus-trapped
  dialog with focus restore, `prefers-reduced-motion` honoured.
- The sidebar becomes an off-canvas drawer under 1000px. It takes focus when
  it opens, closes when a state is picked in it, and is hidden, not just moved
  off-screen, when closed.

### On a phone

Measured in Chrome's device emulation at 360, 390 and 430px and in landscape:

- Below 1000px the page itself scrolls, under a sticky header, so Safari's
  toolbars collapse and a tap on the status bar goes back to the top. It used
  to be a box inside a body that never scrolled.
- Every text field and menu is 16px, so iOS does not zoom into the page when
  one is tapped.
- The grid's filters fold behind a **Filters** button that counts the ones that
  are on, and its sort is an icon over its own menu. The search box had been
  squeezed to 0-13px wide.
- The profile dialog is the whole screen and scrolls as one page, with the
  close button kept in reach.
- Map text is 11px on screen at the width the map is drawn. On the partisan
  map, states too small for their code are named in boxes of their own colour
  in the Atlantic, and the boxes can be tapped.
- Buttons, chips and links meant for a finger are at least 44px.
- The browser's toolbar colour follows the chosen theme.

Android's Chrome, Brave and Samsung Internet share Chromium's engine, so the
layout is the same. What they do differently is handled too:

- No grey flash over a tapped control or map state (a tapped control shows
  `:active` instead), and no hover look left stuck on what was tapped: hover
  styles apply only where there is a pointer that hovers.
- A quick double tap picks twice rather than zooming the page; pinch-zoom
  still works.
- The back gesture closes an open drawer or the theme menu, as it does the
  profile dialog, before it leaves the page. Closing a profile returns to the
  grid exactly as it was, scrolled to the same card.
- District maps are numbered down to a Galaxy Z Fold's 344px cover screen.
- The compact header runs up to 760px, which covers a Fold's inner screen and
  phones in landscape. Under 130% page zoom or more, the search box gets a
  row of its own.
- Every word on the maps is page text on a small backing laid over the map,
  not text drawn inside the SVG. Samsung Internet's dark mode repaints every
  page whatever it declares. Inside an SVG it lightened a label's dark halo
  along with the label, and the text bloomed into a smear. Page text
  survives a repaint: the backing goes dark, the text light. The page also
  declares `only dark` or `only light` for the theme it shows. Brave's night
  mode, Chrome's auto-dark and Samsung's "Use website dark theme" respect
  that.
- Timed on an emulated mid-range phone (4x CPU throttle), every page is
  loaded in under 0.6 s; Texas's district page took 11 s before its clip was
  made a single path. Brave's and Samsung's ad-block lists (EasyList,
  EasyPrivacy, uBlock Origin, AdGuard, Fanboy and Brave's own) neither hide
  an element of the site nor block one of its files.

### Getting around

The sidebar is the same on every page, grouped by level of government. It is
one table, `pages.nav_groups`: the generated pages render it, and the build
fails when the hand-maintained `index.html` or `map.html` carries anything
else (`emit.check_nav`).

| Group | Entries |
|---|---|
| Elections 2026 (the cycle's year, `cycle.CYCLE`) | Candidates (the grid), Races & partisan map |
| Federal | Congress (the grid's sitting members), President & Cabinet, Federal courts |
| State | States & territories, State legislatures (`legislature/index.html`) |
| Local | Counties & local governments (`counties/index.html`) |
| Learn | Know Your Government (the guide) |

A page that *is* an entry's link is marked `aria-current="page"`; one that
belongs to an entry (a state's legislature, a court) `aria-current="true"`.
The grid marks Congress while it shows the sitting members.

The guide and the data link each other. Each data page says where Know Your
Government explains it - the federal hub's sections, each court's page by
its kind, the district maps, the legislature and county pages, and the
Congress and election boxes in the sidebar - and each guide section ends
with where its subject can be seen on this site now (`government_text.SEE`).
The executive and Supreme Court sections list who holds those offices now,
from `data/federal.js` (`government_text.HOLDERS`, rule 48). On the guide's circuits
map a state's facts list its own federal courts - its court of appeals, then
its district courts - each linked to its judges, from the same `federal.js`. Every link is
checked: a guide section, by `government.href`; a section of the federal
hub, against the sections its script draws (`government.SITE_ANCHORS`).

The two directories:

- `legislature/index.html` lists every state legislature, each chamber's
  seats by party and who holds a majority, in the words of the state pages
  (`KYC.stategov`, from `data/stategov.js`).
- `counties/index.html` counts every state's local governments by kind, as
  the Census of Governments does; a state with none of a kind reads "none",
  never 0 (rule 49). Where a state's county governments are fewer than its
  counties, a numbered note under the table says why (rule 71).

- `/` focuses the search box from anywhere on any page; Escape hands focus
  back, and on the grid clears the query too.
- The grid's search reads a state's name or postal code as that state
  ("Kansas" is never Arkansas: words match where a word starts), a district
  however it is written as its race ("Ohio 9", "TX-35", "texas district 35",
  "ny14", "WY at large"; "TX-3" is never TX-30; a seat that does not exist,
  "AZ at large" or "Ohio 99", is said not to), and ranks the rest: the
  name or an alias exactly, then a name, then the office, a leadership post
  or the place, then the profile's text, a card matched only there saying
  where. Other officials - the President, the Cabinet, the justices and
  judges, governors and statewide officers - are listed apart for the
  office they hold, linking to their own pages and never shown as profiles
  (one also running for Congress has a card as well); their data is
  fetched the first time a query is typed (`KYC.loadData`, from the stamped
  URLs in the page's `<template id="onDemandData">`). Members who left this
  Congress (`data/departed_members.json`, written by `congress` from
  `legislators-historical`) are listed with the day that record ends the
  term, said as its own (it can be a day from the House Clerk's), and who
  holds the seat now. A full name that names someone lists no one who
  merely shares the surname; when nobody answers to it, the namesakes are
  listed as namesakes.
- What is on shows as removable chips with **Clear all**; the results line
  says how many out of the race are hidden, with the switch beside it; a
  collapsed key explains every status word on the cards, from the table
  that words them (`KYC.raceStatusLegend`). The races view lists races by
  state, Senate before House, with a jump list, and draws the people out of
  a race only when their list is opened.
- The grid renders a screenful of cards and appends the rest as you scroll
  (a **Show more** button does the same without the observer), so the first
  paint no longer waits on 2,500 image elements. The result count is always
  the full figure.
- The state filter lists states by name, and a filtered state is one click
  from its own page. Race headers, the profile dialog and the map panel link
  to the state page too; a state page has a jump row for its districts.
- On a phone (below 1000px), a state with more than four races opens with
  **Find your race** under its summary: a select of every race and section,
  the district squares, the ZIP lookup and the statewide offices and
  questions on the ballot. Each race folds to one row - who holds the seat,
  everyone on the November ballot in their cards' status words, the filers
  the results do not settle, and the head's count - over its section, which
  stays in the page hidden until found. A link, a square or a pick opens the
  race; **Open all** opens them all. 1000px and wider, the page is unchanged.
- Cards, rows and map states open the same profile dialog everywhere; a
  `#/profile/<id>` link opens it on whichever page it is pasted into.
- The dialog ends with **In this race**: everyone else contesting the same
  seat, people still on the ballot first and the rest folded, each one click
  away - the way a video page lists what to watch next.
- The search box suggests names on focus (people on a ballot; off-ballot
  filers would swamp the list), and the sidebar remembers the last state you
  looked at, in this browser only.

### Escaping

Everything user-visible from the data goes through `KYC.renderField` (which
escapes and renders provenance) or `KYC.escapeHtml`. There are no inline event
handlers anywhere; both pages use delegated listeners keyed on `data-` attributes.
CI greps for `onclick=` and friends and fails if one returns.

## The map

`kyc/geo.py` decodes `us_atlas_states_topo.json` — an already-projected Albers
USA atlas — into SVG path strings, once, at build time. Nothing about
cartography happens at runtime, and no mapping library is loaded.

Coordinates are rounded to 0.1 px (sub-pixel in a 975-wide viewBox) and emitted
as relative moves, which halves the file. Every delta is the difference between
two already-rounded absolute points, so replaying them reproduces those points
exactly; `tests/test_geo.py` replays every state's path and asserts it.

Fills use `color-mix()` against the theme's own party custom properties, so
switching theme recolours the map through CSS with no repaint pass.

Puerto Rico and the U.S. Virgin Islands are not in the atlas, and Guam,
American Samoa and the Northern Marianas are thousands of miles outside the
frame. All six territories plus D.C. render as a labelled strip beneath the
map, captioned "not to scale", so every delegation is reachable.

## Keeping up with Congress

The roster CSVs are hand-curated, and measurement says they are *accurate*.
Checked field by field against
[congress-legislators](https://github.com/unitedstates/congress-legislators),
they disagree about nobody's party, state, district, chamber or birthdate.

What a hand-maintained CSV cannot be is **current**. Members resign, die and
win special elections between builds, and nothing in the file notices. Two
representatives seated in September 2026 were simply absent from the site,
and no page, log line or test said so — which is precisely the failure mode
this project treats as worse than a crash.

`congress_snapshot.json` is a trimmed, committed copy of the authoritative
membership: bioguide id, name, chamber, state, district, party, term dates,
Senate class, birthday and FEC candidate id. 184 KB, sorted by bioguide, so a
change in the membership of Congress arrives as a reviewable diff rather than
as a silent shift in the output.

```bash
python build_profile_site.py congress          # refresh, then report drift
python build_profile_site.py congress --check  # report from the snapshot, offline
python build_profile_site.py congress --apply  # write the drift in
```

The rosters hold whoever the snapshot says is serving, of whichever Congress,
so their names no longer claim one (`Cleaned_House.csv`,
`Cleaned_Senate.csv`). `--apply` does three things, each file written
atomically:

- **Newly seated members** get a row with only the columns the dataset
  actually knows. Education, net worth, committees and platform stay empty:
  the roster's columns for them are never shown (rule 86), and `members`
  fills a member's education, careers and platform from sources tied to them
  by id - see [A member's biography and platform](#a-members-biography-and-platform).
- **A new term** — everyone re-elected, on January 3 — rewrites the row's
  chamber, state, district, term dates and status. A representative elected to
  the Senate moves to the Senate file, and their committee assignments are
  emptied, since they described the House seat. The name is the person's,
  and stays. A new term never changes a party,
  so a party difference is still an error for somebody to look at.
- **Anyone who has left** moves, row and all, to `Former_Members.csv`, with
  the day they left, the record that says so and their last Congress. A 2026
  winner who leaves keeps the race they won. The committed snapshot they last
  sat in still holds them, so their row also records `Race Role` "winner",
  the `Race ID`, and every FEC id Congress's record listed for them
  (`FEC IDs`, from `legislators.winners_leaving`). The race keeps its winner
  and the filing stays theirs. Who
  has left is decided by bioguide id, never by name: `legislators-historical`
  lists them with a term ended by the day the snapshot was read, and the day
  it gives is the one written (for an appointee, the day their successor was
  seated, not the special election's). That a term has ended is not evidence
  on its own — on January 3 it is true of every House member, so a current
  file that dropped someone by mistake would archive them. Anyone absent with
  no such record stays in the roster, and the build's `departed-member` error
  says so: an upstream fault until somebody shows otherwise. A failed
  download of the historical file archives nobody.

Running it twice changes nothing. Puerto Rico's Resident Commissioner is
the exception to the term dates: congress-legislators records the four-year
term one Congress at a time, so the statute (48 U.S.C. 891) decides it.

Three days after a new Congress's terms begin, a snapshot of the old one is a
build error (`snapshot-behind`). Every other check compares committed files
with each other, so a refresh failing every day from January 3 would leave CI
and the deploy green on the old Congress's data.

`build` reads the snapshot when it is present and falls back to the CSVs alone
when it is not, so the pipeline still works offline from a fresh clone.

### The 2026 Senate class is derived, not typed

`overrides.SENATE_SEATS_UP_2026` is 35 hand-typed `state: surname` pairs, and
the seat-matching test was `surname.lower() in member_name.lower()`. That is
only ever approximately right. The table says `"SC": "Graham"`, meaning
Lindsey Graham — but South Carolina's class-2 seat is now held by **Darline
Graham Nordone**, and the entry kept matching purely because she happens to
share the surname. A replacement without that coincidence would have dropped a
real 2026 Senate race off the site.

The class is now derived from the term each senator is actually serving and
matched on bioguide id. The regular class ends on 3 January of the following
year; seats filled by appointment after a resignation end on election day
itself, which is why the window opens in January of the election year rather
than testing a single date. Both routes agree on all 35 seats today, and
`build --check` reports it as a warning if they ever stop agreeing.

## Who is running

The roster carried 57 hand-curated challengers. Measured against the FEC that
was not merely thin — it made the site say something false. **436 of 474 races
rendered as "No declared challenger", and only four of them actually were.**
372 had a challenger who had already raised $25,000 or more. A voter reading
their own district was told nobody was running against the incumbent when
somebody plainly was.

The field now comes from the FEC, the authoritative register of who is running
for federal office, and the roster keeps its role as editorial detail on top.

| | Before | After |
|---|---|---|
| Profiles | 596 | **2,575** |
| Races with a declared challenger | 38 | **451 of 479** |
| Races falsely reading "no challenger" | 372 | **0** |

### The curated rows

The 45 hand-curated candidates in `Congressional_Candidates_2026.csv` and its
two siblings are each two ids and a seat. `ID` is the profile id, written in
the row so that deleting a row never renumbers the people below it: `odds.json`
and the enrichment cache hold these ids. `FEC Candidate ID` is the person's own
filing, and the finance lookup uses it as an authoritative id (`rosterFecId`).
`validate` fails a curated row with no id or with another seat's filing.

Nothing else about a person is read from these rows: not money, biography,
platform or committees. No member's money is read from the member rosters
either. A site audit on 2026-10-13 found three governors
who never filed for the Senate (Brian Kemp, Andy Beshear and Chris Sununu)
listed as candidates with round-number totals. One read "Raised
$22,000,000.00". It also found three nominees on a second profile with no money
of its own. For the curated nominees, 17 of 20 birthdates disagreed with the
person's own article. Money now comes from the FEC alone: `validate` fails any
figure whose `financeSource` is not `FEC`. Biography comes only from the
article the election page links (`enrich`, rule 38), with its source badge.
Where neither knows, the page says "No data".

### Where the line is drawn

The receipts distribution is smooth — there is no natural cliff, and picking a
number would be inventing an editorial judgement and presenting it as a fact.

So the line is the statutory one. Under **52 U.S.C. §30101(2)** a person
*becomes* a candidate for federal office once they raise or spend more than
**$5,000**. That is the legal definition of the word this site uses. Above it:
2,054 filings holding 100% of all money raised in the field.

Everyone below it is still counted. Each race carries `filedCount` — how many
people have filed at any funding level — so a seat is never described as
uncontested when somebody has filed for it. Of the 28 races with no profiled
challenger, 26 show a filing count and only **2** are genuinely empty.

A nominee under the threshold is on the ballot all the same. The 2026-10-13
audit found 54 decided races reading "No challenger on the ballot" over a
second nominee: TX-12's Democratic nominee raised nothing, and California's
top-two seats were the worst hit. The results page had already matched each
one to an FEC id. `races.build` names them from that filing
(`results.belowThreshold`, `{id, name, status, party}`) and adds them to `otherNominees`.
Each such name is printed with its party (`results.otherParties`, `{name: party}`):
the ballot's line as the results page or the state's certified list gives it,
else the filing's party where the FEC names one ("Alan Aversa (Republican)").
A bare name beside a market line for "Republican party" left the reader to
guess which of two names it was.
`contested` is true once anyone besides the incumbent is on the ballot, and
the card counts them: "1 challenger on the ballot · 1 with no profile here".
The FEC's incumbent flag keeps an incumbent's own second registration out.

Not every registration that lists 2026 is a 2026 filing, so the field is
screened first (`candidates.screen`) and the build reports each one it sets
aside:

- **Stale registrations** — no report covering anything since 1 January 2025.
  Jim Inhofe's committee last reported through 2022-12-31 and appeared as a
  2026 Oklahoma Senate candidate carrying 2022 receipts. They are neither
  profiles nor counted in `filedCount`. A registrant with no report at all is
  kept: a statement of candidacy with no money yet is still a filing.
- **Filings for races that do not exist** — a Senate filing from a state with
  no seat up, or a House district the state does not have (GA-23, NM-66).
  `races.contestable` derives the real races from the sitting members.

### Telling them apart

Adding the field made 79% of profiles people who do **not** hold the seat, so
the grid carries a **Sitting members / Challengers** filter and the URL keeps
it (`#/?role=member`). It composes with everything else, so
`#/?role=member&state=TX` is the 39 people who actually represent Texas.

The map's delegation panel leads with who holds the seat and puts the
challengers behind a count: Texas has 37 representatives and 191 filed
challengers, and listing all 228 buried the delegation the reader clicked the
state to see.

### What these profiles do and do not contain

Name, party, seat, receipts, disbursements and cash on hand, all from the FEC
with a coverage date. Committees are editorial research that no dataset
supplies, so they stay empty and the provenance layer reports them as
*No data*. For anyone still in a race, background, education, age, what the
campaign says it stands for and a portrait are filled where the person's own
sources say so - see [Filling the gaps](#filling-the-gaps) - each credited to
its source. A sitting member's education, earlier careers and the issues they
work on come from the Congressional Directory, the article their id maps to and
their official website, each badged - never the rosters' typed columns; see
[A member's biography and platform](#a-members-biography-and-platform).

They also carry **no portrait**. Portrait resolution for a member goes through
the authoritative bioguide→Wikipedia mapping and cannot pick the wrong person.
For a filed candidate it is a bare title guess and a search, and the field
holds 1,979 largely unknown people with ordinary names — "Michael Smith"
resolves to an article about somebody else. A silhouette says "we have no
portrait", which is true; a stranger's face on a candidate's profile is the
exact failure rule 3 exists for, and nothing on the page would look wrong.
Guessing also cost about 4,000 requests that 404, which took the page's load
event to 59 seconds.

### Duplicates are reported, never merged

The FEC's register is keyed by candidate id, and one person can hold two
committee registrations. Deciding automatically which pairs are one person is
not safe: Alaska's Senate race really does contain both Senator **Dan
Sullivan** and a different **Daniel J Sullivan**. `build --check` reports the
six current look-alike pairs as a warning for a person to judge.

Two cases *are* resolved automatically, because both are exact:

- A filing whose FEC candidate id already belongs to a roster profile. This
  runs through the finance cache, which is why `build_profiles` takes it —
  without that, "TUREK, JOSHUA" and "Josh Turek" appeared twice in the same
  race, once with a portrait and once without.
- A filing matching a sitting member of that same seat on **both** first and
  last name. The FEC's incumbent flag is not always current: South Carolina's
  class-2 seat changed hands in July 2026 and the FEC still marks Lindsey
  Graham as the incumbent, so Darline Graham's own committee arrived looking
  like a challenger to herself.

## Who is still in the race

The FEC's register says who *filed*. It does not say who lost. By September
of an election year most primaries have been held, and a page that listed
every filer as a live challenger was wrong about most of them: 858 of the
people it showed as running had already been eliminated.

`python build_profile_site.py results` reads each state's Wikipedia election
page and writes `data/primary_results.json`. Three things keep it honest:

- **A calendar gate.** The FEC's election calendar says when each state's
  primary (and runoff) is. Nothing is read for a race whose primary has not
  happened, however complete the page looks.
- **Winners come from the markup, never from the count.** A row is a winner
  only when it uses the `Election box winning candidate` template. A table
  with nobody marked decides nothing — it is a candidate list, not a result.
- **The general-election table is the authority** when the page has one; a
  party's runoff table decides for the people in it; otherwise a primary's
  marked winner is the nominee. In a runoff state a primary with two marked
  winners means both only *advanced*. The page's infobox, which editors keep
  current before the tables, can add a nominee but never overrule a table.

Names are matched to filings inside one race only: exact surname, a given
name that fits — exactly, as a common nickname (`NICKNAMES`: "Nick" for
"Nicholas", "Hank" for "Henry"), or as a prefix of two letters or more — with
honorifics and suffixes ignored. Two different people that both fit are left
alone and reported; a sitting member's roster name and Wikipedia title are
fed in as aliases so the match does not depend on how the FEC spells them.

### What the results change

- A candidate the page says lost, withdrew, or was never on the ballot keeps
  their profile and gains a status. The grid hides them by default behind
  **Include eliminated**; nothing is deleted.
- A candidate the page does not name is `unlisted` only once the page has
  decided *their* contest — their own party's primary, a nonpartisan primary,
  or the November ballot. A Democrat is not struck out because the Republican
  table is complete.
- **The seat a person is contesting comes from their FEC filing.** Texas,
  Florida, California and Utah redrew their maps for 2026, and thirteen
  sitting members now hold one district number and run in another. A member
  filed elsewhere carries `contestRaceId`, is listed in that race, and is not
  "seeking re-election" to the seat they hold, which is open. A curated
  challenger whose roster row disagrees with their filing is re-seated and
  reported.
- **A member absent from their own party's decided primary is not on the
  ballot.** Thirty-nine representatives retiring or running for state office
  were still "Active Member" in the roster, which cannot notice a retirement.
  They are shown as not seeking re-election, the seat as open, and
  `build --check` lists every one under `member-not-on-ballot` so a matching
  failure would be seen. Nobody whose name fitted two filings is ever inferred
  absent.
- **The ballot's party wins.** Seth Bodnar, Brian Bengs and Todd Achilles are
  on their states' Senate ballots as independents; the roster had all three as
  Democrats. A filed candidate takes the ballot party (the FEC record stays as
  `fecParty`); a roster row is reported for a person to correct.

Race headers show the primary date, who is on the November ballot, how many
filers are out, and anyone the results put on the ballot with no FEC filing
over $5,000 — leaving them off would make the header lie.

### The frozen 2026 race record

Which seats are on the 2026 ballot used to be worked out on every build from
whoever was sitting: a Senate seat was up because its senator's term ends at
the election. That stops being true twice. When the Florida and Ohio special
elections' winners are seated in December, their terms run to 2029, so the
two seats would stop looking "up" and both races, with their results, would
drop off the site. And on January 3 every term changes.

So the race set is frozen once, from the 119th Congress, before the
election: `python build_profile_site.py record --freeze` writes
`data/record_2026.json` (475 races, 35 of them Senate). It holds, for each
race, its chamber, state and district or Senate class and whether it is a
special election; and for each, who held the seat, by bioguide id, with
every FEC id the official membership lists for them (both chambers), the
ids the site links through, and whether they were appointed (an appointee
is never "re-elected"). Its signature is pinned in `kyc/cycle.py`, so
`verify` fails if the set of races changes without a reviewed code change.

`kyc/cycle.py` holds the cycle (`CYCLE = 2026`), the only value set by hand,
and the date arithmetic: which Congress sits on a date, which one an
election elects, and the Congress the committed snapshot is of. Until the
Congress the cycle elects is sitting, `build --check` compares today's seats
with the record (`record-drift`), reading today's Senate seats straight from
the snapshot's term dates so the record is never compared with itself; the
only difference allowed is a seat whose appointee's term has ended. A record
incumbent re-seated for a new term reads that term's end, and each Senate
race carries `special` from the record, so the Senate view keeps Ohio's and
Florida's seats with the 2026 specials after their winners are seated. A
senator who resigns early and is succeeded by an appointee in the same seat
is the roster's business, not a lost race. The surname table of 2026 Senate
seats is gone.

### Louisiana's open primary

Louisiana's House seats have no primary before November: the November 3
vote is an open primary, with a December 12 runoff between the top two. So
until the count no results page can say who is running, and the site showed
the FEC's register in its place - "3 filed, none past $5k" for LA-2, whose
ballot holds five. `results` now also reads the Secretary of State's
Candidate Inquiry (`kyc/qualified.py`), which lists everyone who qualified
for each seat and exports it as CSV. Qualifying closed on August 7.

- A filer the list names is `qualified` ("On the Nov 3 ballot"). That is not
  "nominee": nobody has won anything yet.
- A qualified candidate with no FEC filing over $5,000 is named on the race,
  as any other unprofiled nominee is.
- A filer the list does not name is not on the ballot (`unlisted`).
- The race header says "Primary 2026-11-03", not "Primary held", and names
  the Secretary of State's list as the source.
- Only the ballot's own words are kept: the name, the party, the day each
  candidate qualified, and a withdrawal. The export also carries home
  addresses, phone numbers and emails; none of it is stored.
- The export's Outcome column has never held a result (checked on the 2024
  export after its count), so any value other than "Withdrew" is refused.
- A failed read of the list keeps the last one read, with its date
  (`results.carry_qualified`), and `build --check` warns
  (`qualified-list-stale`); with no list ever read, the seats stay pending.
- Every status read from the list says so: "not on the Secretary of State's
  list of candidates qualified for the November 3 open primary", and names
  with no profile are "per the Secretary of State's list", never "per the
  published results".
- After the count, the results page decides, exactly as for every other race.
  Until it marks a result - or while it cannot be fetched or has no section
  for a seat - the list stays, its candidates read "Awaiting result", the
  header reads "Primary held" with no result read yet, and three days on
  `general-uncalled` lists the seat.

### The states' certified ballots

A results page says who won a primary; it does not say who is on the
November ballot. Audited on 2026-10-17 against the states' own lists, the
site showed Alaska's at-large seat with two people on the ballot over a
certified four, and said the two it left out had withdrawn, when it was four
other top-four finishers who withdrew and promoted them. It also left out a certified Alaska
Senate candidate, thirteen qualified Florida candidates, Colorado's minor-party
and unaffiliated candidates in every district, and called American Samoa's
seat uncontested over six certified names. Once a state has certified its
general-election candidates, its list is the ballot (rule 77):

- `kyc/certified.py` reads the published lists: Alaska's Division of
  Elections, Florida's Division of Elections (federal offices), Colorado's
  Secretary of State, American Samoa's Election Office and Texas's Secretary
  of State (its qualified-candidate search, read from the JSON service the
  page draws from: an accepted declaration in the general election is
  printed, a rejected one never was). A list published only as a PDF is
  transcribed in `overrides.CERTIFIED_BALLOTS` with its document and the day
  it was read (Iowa, Nebraska). Only an election office's list is a ballot: a
  party's list of its convention nominees is not, since the state may still
  refuse them.
- The name a profile shows comes from its source's authority: a name settled
  word for word or by an evidenced `overrides.RESULT_NAMES` alias ("Neil J.
  Gillespie", whom the FEC files as GILESPIE); a certified list's printed name
  unless it differs only in case and full stops, drops a hyphen, or is printed
  in capitals (Texas's is; "Daniel J. Sullivan Jr." is Alaska's); a results
  page's only where it adds a hyphen or its first name is the short form of
  the filed one ("Bob Harvie"). A page's formal form of a campaign's name
  ("Matthew Dunlap" for Matt Dunlap) is an alias, never the name shown.
- Party words beside a name with no profile are the site's ("Democratic",
  "Libertarian") whatever the list prints, a party of another name as printed,
  and none where the list prints none (American Samoa's).
- A filing is matched to a listed name as a results page's name is (rule 62):
  the matcher, an evidenced `overrides.RESULT_NAMES` alias, or the filing's
  own words in any order, a bracketed nickname aside, unique in the race.
- Someone the list prints is on the November ballot, whatever the page said:
  "withdrawn" included, and reads "On the November ballot" - never
  "Renominated", since a list is not a primary. A certified write-in, and a
  Florida candidate unopposed in November (Florida prints no uncontested
  race), is not read as printed, nor as left off the list; an unmatched one
  may still be a page nominee's other spelling and holds them.
- Where the list is the whole ballot, a filer it does not name is "Not on the
  November ballot" - unless a name on it that matched no filing may be theirs
  (`maybeNamed`) - and a page name it does not print is not counted on it.
- A listed name with no FEC filing over $5,000 is named on the race with the
  list's party. Every status the list set credits it: "per the Alaska Division
  of Elections, ..." on the race, and the list's name in the badge's title.
- Only the name as printed, the party, the office and district, and what the
  list says of the person (printed, withdrew, lost the primary, write-in) are
  kept; the lists' addresses, phone numbers and emails are not. A list that
  cannot be read, or reads as something it should not, is refused and the last
  one read is kept (rule 8).

### After Election Day

The same pages, read the same way, say who won. Nothing is read from the
November table until the day *after* Election Day (`results.general_held`):
on the day itself polls are open somewhere, and an early mark is not a
result.

- **One marked winner decides the race.** The general table's single
  `Election box winning candidate` row is `elected`; everyone else on that
  ballot is `defeated`. No marked winner, or two, changes nothing: the count
  is continuing, or the page is mid-edit. `validate` fails a race with more
  than one person elected (`multiple-elected`).
- **Georgia's December runoff.** `overrides.GENERAL_RUNOFFS` lists the states
  whose general election goes to a runoff without a majority, with the
  statute and the date (Georgia: December 1, O.C.G.A. 21-2-501). There, a
  runoff table that names no party is the general runoff only if everyone in
  it was on the November ballot — a party runoff's loser never was. Its two
  are `runoff`, the rest of the ballot `defeated`, and after the runoff date
  its marked winner is `elected`.
- **Louisiana's House seats** are an open primary whose first round is the
  November election itself: its majority winner is `elected`, its top two
  are in the December 12 `runoff`, and the rest `defeated`.
- **Who lost in November stays in view.** `defeated` is not off the ballot;
  they were on it. Only people the primary settled out sit behind
  **Include eliminated**.
- **A nominee with no result yet reads "Awaiting result"**, and the race
  header says the results this site last read (`election.resultsAsOf` in the
  build meta) had not marked a winner. That is a claim about when we looked,
  not about the count. A called race's header reads "Won by …"; a race going
  to a runoff says so.

Every view takes its words for a status from one table, `KYC.raceStatus` in
`assets/kyc.js`: the card, the profile, a race's list of people and a map row
each have a form, and a sitting member's own seat reads "Renominated",
"Re-elected" or "Lost re-election".

### Once the new Congress sits

The build metadata says which phase the data is in (`election.phase`, from
`kyc/cycle.phase`). It is `"campaign"` until the snapshot is of the Congress
the cycle elects and was read after noon on January 3. After that it is
`"record"`, and `KYC.recordPhase()` reads it. In the record phase:

- **The Senate view groups every senator by the year their seat is next
  decided.** That is 2028 for Class III, Florida's and Ohio's seats among
  them, then 2030 and 2032. No seat is "up in 2026". The 2026 results stay
  on the race view and the state pages. Between Election Day and January 3,
  the cycle's group reads "2026 elections", not "Up in 2026".
- **A redrawn state's district page draws the new Congress on the new
  map.** The old map is drawn in the party of whoever last held each seat:
  each race's incumbent, from the frozen record. "Running in a different
  district" is gone, and a district's 2026 race is shown as a record, "In
  the 2026 race".
- **A state page's headline figures say they are 2026's.**

The render suite builds pages on a clock before January 3 in the
campaign's phase, so its campaign checks hold on later data. The
record-phase views have their own checks (`testRecordPhase`).

## Filling the gaps

A filed candidate arrives with a name, a party and a dollar figure. For
everyone still in a race, `python build_profile_site.py enrich` reads what
their own sources say and writes `data/enrichment.json`:

| What | From | Shown as |
|---|---|---|
| Birth date (so age), education, occupation | The infobox of the Wikipedia article the state's ballot page links (rule 33), its title checked against the surname after redirects | The field, badged **Wikipedia** |
| A few words of background | The race page's own description of each listed candidate ("former president of the Navajo Nation"), read by `results` | *Previous careers*, badged **Wikipedia** |
| What the campaign says it is about | The campaign home page's own description of itself, quoted whole | A quotation under *Platform*, linked to the site |
| The issues it runs on | The section headings of the page the site links as its issues, platform or priorities | Bullets badged **Campaign site**, linked to that page |
| A portrait | An image on the campaign site named for the candidate and shaped like a headshot | The card and dialog portrait |
| A campaign website | The race page's "Campaign websites" list, for a challenger whose committee filed none or one that failed the check | The link, credited to the race page |

Nothing is summarised or rewritten. Every value goes through
`normalize.fill_field`, which never overwrites what a roster or filing gave and
records the source in `fieldSources`; the page shows that source as a badge.
Ages are computed at the same date as every other age on the site.

**Before anything is taken from a campaign site,** the site must come from the
committee's Form 1 or the race page (never a search), its text must name the
candidate (the surname, the middle name of a three-part filing name, or a first
name its own address carries - "Kristi for Congress" at votekristiburke.com),
and it must not read as hijacked or parked. A description is quoted only in
whole sentences - a search plugin's cut-off "…the people in U.S." is not one -
and without its calls to action, signposts ("The official campaign website
of…") and posts the home page happens to be showing. Issue headings come from
one heading level of a page that is not a privacy policy, a shop, a news page
or a ballot-question page ("Tyler votes NO" beneath a measure is not his
platform); furniture ("Become a Volunteer", "Checks can be mailed to", "This
website uses cookies") is dropped, a page that is mostly furniture gives no
list, and a heading that names anyone else in the race is an attack line, not
an issue. An image must carry the surname in its file name or alt text, must
not be named as a logo, a share card, merchandise, a collage or someone else
("Mikes Mom.png"), and must be taller than it is wide unless its own name or
alt text calls it a headshot, portrait or profile: the first full run took a
T-shirt, a clipboard icon, four logos, two collages and eight group or family
photographs, each carrying the right name. `overrides.NOT_A_PORTRAIT` holds the few that pass
every rule and are still not a likeness; the weekly re-read would undo a
correction made in the cache.

**Every linked campaign site is read, members' included.** A site serving
visible gambling spam or a parking page comes off the profile at once and is
reported (`campaign-site-withdrawn`) for a person to record in
`BLOCKED_CAMPAIGN_HOSTS`: the first run found `joshweil.us` redirecting to a
slot site and two parked domains, and confirmed four more dead or unrelated
hosts. A site with spam *hidden* in the campaign's own page is compromised,
not lapsed, and stays linked (`campaign-site-compromised` - Ron Johnson's,
2026-10-02). One that answers without naming the candidate, or is a "coming
soon" page, stays and is reported (`campaign-site-unconfirmed`). A bot wall, a
JavaScript-only page or a timeout concludes nothing (rule 8). The refresh
workflow re-reads everyone each Monday.

For the 509 challengers on the November ballot, on 2026-10-02:

| | Before | After |
|---|---|---|
| Background / previous careers | 40 (8%) | 433 (85%) |
| What they are running on (issues, or the campaign's own words) | 40 (8%) | 289 (57%) |
| Education | 40 (8%) | 152 (30%) |
| Age | 40 (8%) | 134 (26%) |
| Portrait | 140 (28%) | 171 (34%) |
| Campaign website | 391 (77%) | 413 (81%) |

## Prediction markets and polling averages

Every 2026 race shows what two prediction markets say about it, and every
Senate race the published polling averages too - in the grid's race view, the
state pages, the profile dialog's "in this race" panel, the Senate view and
the map's 2026 Senate panel. The race view opens with the markets on which
party will control each chamber, and the Senate view with the Senate's.
`python build_profile_site.py odds` writes `data/odds.json` and the page file
`data/odds.js`:

| Source | What is shown | How it is tied to the race |
|---|---|---|
| **Kalshi** (a CFTC-regulated exchange), public market data | Each outcome's last traded price, with the market's own label and question | The market's question and its resolution rules must both name the seat: the state for the Senate ("a Senator of Kentucky"), the district for the House ("sworn in for CA-03") |
| **Polymarket**, public Gamma API | Each live outcome's displayed price; placeholder outcomes ("Person A") are skipped | The event's title and its description must name the same seat |
| **Polling averages** (Senate only): 270toWin, Decision Desk HQ, FiftyPlusOne, RealClearPolitics, Race to the WH, Silver Bulletin and others, as the race's Wikipedia page lists them | Each aggregator's figures and the date it last updated them, linked to the aggregator | The general-election section's "Aggregate polls" table, used only when every candidate column names someone in the race |

House races have no polling averages. Wikipedia lists none for a district, and
its district tables are single polls - mostly primaries, many of them a
campaign's own ("Poll sponsored by Chaplik's campaign") - which would need a
partisan label beside every figure to be shown fairly.

Nothing is blended or recomputed. A market price is what a trader pays for a
contract worth $1 if that outcome happens; the page says beside every block
that it is not a poll and not this site's forecast, and dates it. Outcomes
under 1% are counted rather than drawn.

**Attribution is checked, not trusted (rule 40).** Kalshi's ticker `SENATELA`
holds Kentucky's race, labelled with Kentucky's nominees; a ticker-based
match would have put Andy Barr's odds on Louisiana's page. A market label
that names nobody in its race is shown as the party it resolves on. When this
site knows a candidate of that party in the race, that is a conflict and
`build --check` lists it (`odds-label-mismatch`); when it does not - a
nominee who filed too little to have a profile here, about 150 of them in
safe House seats - the build counts it instead. It also reports any Senate
race no market covers (`odds-uncovered`), prices that do not add up to about
a dollar (`odds-incoherent`), race ids no longer on the ballot
(`odds-unknown-race`) and a cache more than eight days old (`odds-stale`).

On 2026-10-03 both markets covered all 35 Senate races and control of both
chambers; Kalshi covered 425 House races and Polymarket 434, together 434 of
the 440 (435 voting seats and five delegates); 22 Senate races had polling
averages on their Wikipedia page.

**Refreshed every twelve hours, on its own.** `.github/workflows/odds.yml`
runs at 00:47 and 12:47 UTC: it reads the markets, runs the same
validation, `verify` and tests a deploy does, commits the two odds files to
`main` and starts the deploy. It may commit nothing else, and stops if any
other file would change. That is possible because `data/odds.js` is a pure
function of `data/odds.json` - labels are checked when the prices are read,
and the result is stored in the cache - so the roster build leaves it alone
and the weekly refresh's pull request never collides with it.

## Portraits

Portraits are resolved **at build time** and cached in
`candidate_profiles_site/data/portraits.json`, which is committed and
hand-editable. Coverage is **571/594 (96%)**; of the 23 without one, 9 are
placeholder rows for unresolved primaries, so 14 real people lack a portrait
because no public source has one.

Resolution order:

- **House members:** the House Clerk's official portrait (335px wide and the
  current one), then congress.gov's (175px, often a Congress or two older).
- **Senators:** the Wikipedia article's portrait through the
  `congress-legislators` Bioguide↔title mapping, then congress.gov's. The
  Senate publishes no portrait by Bioguide id, and for most senators sampled
  congress.gov's was the older photograph.
- **Everyone else:** the same mapping, a bare Wikipedia title guess, then a
  Wikipedia search - never a guess or a search for a filed candidate (see
  [Who is running](#who-is-running)).

A member and their own 2026 candidacy share a portrait.

### Sizes

A Wikimedia portrait carries `photoSet`: Wikimedia's standard thumbnail widths
of that file (120, 250, 330 and 500px) narrower than the original. The page
puts them in a `srcset`, so a 38px circle fetches the 120px file and a card on
a 2x screen the 330px one. Both used to fetch a 960px thumbnail or an original
of up to 2,364px. Wikimedia refuses any width but its standard ones, so the
sizes are built from the original's measured width. `portraits` fetches only
the smallest, slowly, to confirm the file can be resized at all: a burst of
thumbnail requests gets HTTP 429 for everything from that address. If a size
fails on the page, the page loads the photograph's plain URL instead.

A srcset holds sizes of one photograph only. The House Clerk, congress.gov
and the unitedstates project hold different photographs of most members
(seven of ten sampled), so a Clerk or congress.gov portrait ships as a single
URL, and `validate` fails a `photoSet` that names another file.

| Field | What it holds |
|---|---|
| `photos` | The fallback chain the page walks on a load error, ending in `"placeholder"` (the silhouette) |
| `photoSource` | Where the first entry came from: `clerk.house.gov`, `congress.gov`, `wikipedia` (the article the bioguide mapping names, or the one the ballot page links), `cross-link` (the same person's other profile), `campaign-site` (the campaign's own site, its About page or the page as a browser draws it), `wikidata-fec` (the Wikidata item carrying the person's own FEC candidate id) or `state-legislature` (the legislature's own page for a nominee who sits in it) |
| `photoSet` | `[[width, url], ...]`, smallest first: sizes of the first entry's photograph for the page's `srcset`. Wikimedia portraits only |
| `photoCredit` | Whose photograph the first entry is: `{by, licence, licenceUrl, page, via, authorUnrecorded?}`. A Commons file's author and licence as its own description page records them (`via: "Wikimedia Commons"`, `page` the file's page; `by` null where the page names no author, and `authorUnrecorded` where its licence asks for one); a government portrait's host (`by: "U.S. House of Representatives"`); a campaign's website (`by`, `page` the page the image was on); a state legislature's (`by: "New Mexico Legislature"`, `page` the member's page). Absent for the silhouette |

### Credits and weights

Every photograph the page shows says whose it is (rule 87). The profile and
official dialogs print one line under the name: "Photo: Gage Skidmore, CC
BY-SA 3.0, via Wikimedia Commons", the licence linked to its deed and
"Wikimedia Commons" to the file's page. In October 2026, 153 of the 394
Wikimedia portraits were CC BY or CC BY-SA, whose terms require exactly that,
and none was credited. `portraits` reads each Commons file's `Artist`,
`LicenseShortName` and `LicenseUrl` from its `extmetadata` (fifty files a
request, one request a second), strips the markup from the author - with
what Commons hides (a duplicate "Unknown author" span), an uploader's note
about themselves, a leading file name, and any "unknown" or sentence that
names no one (`portraits.author_of`) - names a licence code ("PDM-owner" is
the Public Domain Mark), and keeps them in the cache as `credit`, with the
`form` of the reading so an older one is read again; a file Wikipedia holds
as non-free is not shown, and one whose credit Commons has not yet answered
for waits for the next run. A fallback photograph that loads in the first one's place is credited
by its host, from `kycBuildMeta.photoCredits`. `validate` fails a photograph
with no credit (`photo-uncredited`) and a Commons portrait with no recorded
licence (`photo-licence-missing`).

A portrait not on Wikimedia is one file at one size, so its weight is
recorded when it is found: `bytes`, `width` and `height` in the portrait
cache for the House Clerk's (50-100 KB, 335px), `portraitWeight` in the
enrichment cache for a campaign's, `headshotWeight` in the executives cache
for a governor's NGA headshot. A governor's headshot over 300 KB or 1,200px
(`photos.MAX_PORTRAIT_BYTES`, `MAX_PORTRAIT_PX`) is shown smaller from the
same file (`photos.lighter_form`): its host's own resizer (Squarespace,
imgix) or WordPress.com's Photon (`i0.wp.com/<host>/<path>?w=500`), at 500px
or 330px, once that copy is weighed, within the caps and the same shape as
the original; 33 of the 55 governors' headshots are shown through Photon
(`headshotSmall`). A candidate's photograph over the caps is shown in a size
its source itself offers within them where there is one - a rendition its
page's `srcset` lists (`portraitForms`), or one of the fixed widths
Squarespace's image host makes of every upload (`photos.own_lighter_form`) -
never a width asked of imgix or Photon. Where none is offered it is shown at
full size all the same (`portraitHeavy` with `kept: true`; `heavy` in the
portrait cache), since a weight cap is no reason for the silhouette (the
owner's decision of 2026-10-25), and the build prints how many: "candidates'
portraits shown at full size, offered by their source only over 300 KB or
1200px". Only a challenger takes a campaign's photograph: a sitting member's
comes by their bioguide id.

The people on the November ballot have three routes besides the article
their ballot page links (`kyc/nominee_photos.py`, `enrich`). The campaign's
own site is read on its home page, then on its About or Meet page, then as
a headless Chrome draws it (`enrich --render N`, forty sites a run, for a
site that draws its images with JavaScript or answers a script with a bot
wall). A Wikidata item carrying the person's own FEC candidate id (P1839)
gives its image (P18) at Wikimedia's 330px width, credited from the file's
description page, where the item's label carries their surname and a given
name that fits theirs and the item ties itself to them a second way (a year
of birth that agrees, a 2026 candidacy in their state, or their campaign's
site as its official website); the srcset offers the 500px size only once it
is weighed within the caps. A nominee who sits in their state's legislature -
the chamber their own article's corroborated record of offices gives, the
same first and last name in it and nobody else - gets the photograph the
site's legislature page shows on that member's card, on the legislature's
own host, withheld once the roster seats someone else or the card shows
another file. Either route refuses a frame wider than tall not named a
headshot, and a file in `NOT_A_PORTRAIT` or `PORTRAIT_LICENCE_DOUBTS`. Each record keeps the page, the words naming the person
beside the image (`evidence`, `portraitEvidence`), the day read and the
bytes and pixel size; `validate` fails a shown one without them
(`photo-unevidenced`). Washington's voters' guide and Alaska's and Oregon's
pamphlets print candidates' photographs, but only base64 inside JSON or
inside PDFs, so there is no file to link; a hosted copy waits for the site's
store of copies. The page offers a srcset no size wider than a 2x screen
needs for the width it draws, so a 165px card stops at the 330px file and a
judge's 116px portrait at the 250px one.

Set `"pinned": true` on a cache entry to stop the resolver overwriting a
hand-corrected URL.

Two rules are load-bearing here, both learned the hard way:

- **Never discard on an inconclusive check.** Wikipedia returns HTTP 429 freely
  during a full run. Treating "could not tell" as "broken" silently threw away
  about 160 working portraits.
- **Never search with a topical hint.** Searching `Dan Osborn NE politician`
  pushes his own article out of the top results; `Dan Osborn` returns it first.
- **Never guess at all (rule 24).** Nothing in a chain is built from a name.
  The chains used to end in `Special:FilePath/<Name>.jpg`, and the files
  those names reach are whoever uploaded under them: two Senate nominees
  showed a rugby league player and an Olympic kayaker. Titles guessed from a
  name and name searches are gone too; a cached portrait is applied only
  when it came by an id or the ballot page's own link (`portraits.route_ok`),
  and `validate` fails on any `Special:FilePath` or `Special:Redirect` URL.

The fallback chain used to link the unitedstates project's images at
`theunitedstates.io`. That domain lapsed: on 2026-10-03 it resolved to a
domain-parking network, so every member's chain pointed twice at a host anyone
could buy. The chain now uses the project's GitHub Pages copy, because it is
often an older photograph, and then the Biographical Directory's own
photograph (`bioguide.congress.gov/photo/<ID>.jpg`); its old host,
`bioguideretro.congress.gov`, answered 404 for every member on 2026-10-17.

## Campaign finance

`finance` fills receipts, disbursements, cash on hand and a real funding
breakdown from the FEC, replacing the roster's generic
`"Individual/PAC contributions"` text. Figures carry the FEC coverage date.

**Every figure is an election-period total.** The FEC reports money per
two-year cycle and per *election period* - from the end of a candidate's last
election for the office to the next one. For the House the two are normally
the same; for the Senate the election period is the whole six-year term. The
field (`/candidates/totals/?election_year=2026`) and the FEC's own candidate
pages report the election period, and sitting members are looked up the same
way (`/candidate/{id}/totals/?election_full=true`, taking the period for the
next election at or after 2026). Before that, members were read per cycle:
Chris Coons showed $4,168,081 (2025-26) beside challengers measured from
2021, against $6,897,138 for his own 2026 election period.

| Field | Meaning |
|---|---|
| `financeAsOf` | The FEC's coverage end date for the figures |
| `financeSince` | The FEC's coverage start date; `null` when the cache predates it - never filled in |
| `financePeriod` | `election` for an election-period total, `cycle` for a member record cached before the election-period lookup (the 2025-26 cycle), until the next `finance` refresh replaces it |
| `financeElection` | The election an election-period total is for: 2026 for anyone on this year's ballot, 2028 or 2030 for a senator not up this year |
| `fundingBreakdown`, `funding_sources` | What the receipts were, by kind: Individual, PACs, Party, Self-funded (the candidate's own contributions; "Self-funded (incl. loans)" when a loan from the candidate is in it), Bank and other loans, Transfers from other committees (the campaign's other committees) and Other (offsets and other receipts). Each share is of total receipts, or of `fundingBase` where a negative adjustment brought the receipts below the parts. A record cached before loans and transfers were read has no breakdown until `finance` reads it again |
| `fundingBase` | The sum the funding shares are of, where it is not the receipts figure: the positive parts, when an adjustment the FEC deducts (a negative category) brought the net receipts below them. The page says so beside the split |
| `outsideSpending` | Independent expenditures for and against this candidate in the 2025-26 cycle, from `outside`: `{support, oppose, supportCommittees, opposeCommittees, supportTop, opposeTop, asOf, cycle, url}`. Each side is its own total, never a net; `*Top` are the three committees that spent most on that side, as the FEC names them; `asOf` the day the FEC's processed filings were read; `url` the FEC's table for the candidate id; `candidacy` (`House` or `Senate`) the office the ids are for. One committee under two of the person's ids is one group. `runningElsewhere`, on a member running for the other chamber, is the profile of the campaign they are running: these rows are their own candidacy's, not that campaign's. Only rows whose candidate id is the profile's and whose office and state are the profile's (rule 20) |
| `outsideSpendingOther` | On the campaign of a member running for the other chamber: a copy of the member's `outsideSpending` (with `profileId`, the member's profile), shown on a line of its own and never added to this campaign's figures |

### Outside spending

`python build_profile_site.py outside` reads the FEC's independent
expenditures by candidate (`/schedules/schedule_e/by_candidate/`, the
2025-26 cycle) for every candidate id a profile carries, forty ids a
request at the key's pace (rule 37). A batch over a page is split, and one
candidate's rows over a page are read a side at a time, sorted on the
committee, and counted (rule 36). The cache, `data/outside_spending.json`,
holds each id's committees by side. The build attaches them only where the
id's own office and state are the profile's; a row filed for another seat is
an `outside-attribution` error, and nothing is ever matched by name. The
FEC processes filings days to weeks after they are made, so the latest
spending - reported in 24- and 48-hour reports - is often not in these
totals, and the page says so beside them.

A coverage end the filer gave that is still to come ("through 2026-12-31" in
October) is shown "as filed", and `validate` lists it
(`finance-future-coverage`). A negative figure reads `-$582.63`.

**Shares are of everything received.** They were once of four contribution
types only, so a candidate's own loan counted for nothing: Jefferson Shreve
(IN-6), whose $2,000,000 loan was 79% of what his campaign received, read
"PACs 70%, Individual 30%".

**A challenger's split is their own filing's.** The field register
(`/candidates/totals/`) reports only itemized individual gifts, so no split is
built from it. `finance` reads every challenger still on a ballot from
`/candidate/{id}/totals/`, the endpoint members' figures come from, keyed on
their candidate id (`fec:<id>`) - about 550 requests, paced at the key's 60 a
minute (rule 37), resumable from the cache.

The profile dialog words these under the money ("Raised for the 2026
election, Jan 2021 - Aug 2026") and says when a Senate period spans the
six-year term.

Get a free key at <https://api.data.gov/signup/>, then supply it either way:

```bash
export FEC_API_KEY=...                 # environment wins
echo 'FEC_API_KEY=...' > .env          # or a local file; .gitignore covers *.env
```

For the weekly `refresh` workflow, add it at **Settings → Secrets → Actions →
`FEC_API_KEY`**; the finance step is skipped when the secret is absent rather
than wasting the run on `DEMO_KEY`.

Without a key the module falls back to `DEMO_KEY`, which the FEC throttles after a handful
of requests — enough to try it, not enough to fill 596 profiles. Results cache
per profile, so a throttled run stops cleanly and the next one resumes.

**Incumbents are looked up by id, not by name.** `congress-legislators` records
an FEC candidate id for 537 of the 539 sitting members, already scoped to the
seat they hold, and `congress_snapshot.json` carries it. This matters because
the FEC files people under their legal name — Ashley Hinson appears as
`ARENHOLZ, ASHLEY HINSON` — so a name search has to match loosely, and a loose
match that lands on the wrong person puts someone else's money on a profile
with nothing looking out of place. Using the id also halves the request count,
because finding the candidate no longer costs a round trip.

One full run fills the site's largest gap. Before it, `funding_sources` was
real data for **2%** of sitting members — the other 98% was the generic
`"Individual/PAC contributions"` filler — and receipts were real for 33%:

| Field | Before | After |
|---|---|---|
| `funding_sources` | 12/539 (2%) | **524/539 (97%)** |
| `receipts` | 176/539 (33%) | **523/539 (97%)** |
| `disbursements` | 175/539 (33%) | **522/539 (97%)** |
| Real data across all surfaced fields | 69% | **89%** |

533 of those were matched by authoritative id and 40 by name search. Every
attribution is checked: an FEC candidate id encodes its own office and state
(`S2NM00088` is a New Mexico Senate campaign), so `validate.check_finance`
compares it against the profile it is about to appear on. Money shown against
the wrong person would look entirely normal on the page, which is exactly why
it is checked rather than trusted.

## Net worth and financial disclosures

The site shows no net worth for anyone, deliberately. The roster once carried
an "Estimated Net Worth" for 144 of 539 sitting members, none of them sourced,
and the dialog showed it beside the disclosure link as though one came from the
other. The 2026-10-13 audit removed the column and the field.

No free service publishes a computed net worth for members of Congress, and
deriving one from a disclosure is not a small step: the forms report assets in
broad value *bands*, so any single figure from them is an estimate dressed as a
fact (rule 26), the exact thing the provenance layer exists to prevent.

What is available is the filing itself. The Clerk of the House publishes an
annual ZIP containing an XML index of every disclosure, and **401 of 439 House
members** carry a link to their own annual report (PDF) in the dialog's
"Financial disclosure" field. A member the matcher has not linked reads "Not
linked here", a statement about this site rather than about the member: the
matcher misses compound surnames such as Wasserman Schultz. Challengers'
disclosures are not looked up, so the field is not shown for them.

**98 of 100 senators** carry a link to their latest annual report in the
Secretary of the Senate's eFD system. eFD asks every visitor to agree that the
reports will not be used for a commercial purpose, a credit decision or to
solicit money; a non-commercial civic page linking each senator to their own
filing is the use the system exists for, so `disclosures` agrees once per run,
searches each senator's annual reports, and links the latest. A report is
matched only when the filer is listed as a senator, the surname matches, and
the first name fits - the legal name, the name in the filer label ("Cruz, Ted
(Senator)"), a prefix, or a common nickname - and anything that fits two
filers is left alone. Paper filings count too: Richard Durbin and Richard
Blumenthal file on paper, which eFD lists as plain "Annual Report" under the
label "Senator", so the year is taken as the one before the filing date and a
paper report belongs to the one labelled filer with the same legal name. Tammy
Duckworth's reports carry no state, so a search that finds nothing for the
state is repeated on the surname alone. The link says that the Senate shows its
terms first. The two without one, Alan Armstrong and Darline Graham Nordone,
were appointed in 2026 and have not filed an annual report yet.

## Data provenance

The rosters carry three different things in one column, and the site used to
render all three identically:

| Value | Means | Now shows as |
|---|---|---|
| `$3,161,009` | a sourced figure | the figure, with a source badge where known |
| `Not disclosed` | no filing exists | *Not disclosed* (muted) |
| `""` | nobody has researched it | *No data* (muted) |
| `General legislative priorities`, `Public service` | true of everyone; no information | *No data* (muted), titled as a generic placeholder (rule 10) |
| — | the FEC was queried and holds no filing for this cycle | *No filing this cycle* (muted) |

That last row is the only absence that reports work actually done. "No data"
is a claim about us: it says nobody looked. Once the pipeline queries the FEC
for all 596 profiles, using the same label for "we never checked" and "we
checked and there is no filing" discards the more informative of the two — and
17 of them are sitting members running for a *different* seat, whose money is
in another committee entirely. Showing their last cycle's figures instead
would be worse than either: a member's 2024 receipts on a page about the 2026
midterms reads as current money.

Each profile carries a `quality` map listing only the fields that
are *not* real data. About **11% of surfaced fields** fall into one of those
categories — that is the honest picture, and the page shows it as such. Absent
values are excluded from search, so "not disclosed" does not match everyone.

A field the pipeline filled from a named source rather than a roster records
that source in `fieldSources` - `wikipedia` (an article's infobox),
`election-page` (the race page's description), `campaign-site` (the
campaign's own issues page), or for a member `congressional-directory`,
`member-wikipedia` (the article their id maps to) or `official-site` (the
issues their official website lists) - and the page shows it as a badge
beside the value, with a tooltip saying exactly where it came from. A
member's `platforms` whose site was read and lists no issues has the quality
`not_listed`, shown as "Not listed on their official site"; one whose site
has an issues page this site could not read a list from in the page's own
words (prose under tabs, a page drawn by script, a page recorded in
`overrides.OFFICIAL_ISSUES_NOT_A_LIST`) has the quality `see_site`, shown as
"On their official site's issues page" with that page linked; one whose
only issue pages are linked from its home page or menu, too few to list,
has the quality `see_home`, shown as "On their official website" with the
site linked (a home page is never called an issues page). See
[Filling the gaps](#filling-the-gaps).

## A member's biography and platform

The rosters' Education, Previous Professions and "Policy Focus & Platforms"
columns were typed by hand, with no source, in wording that was not
even-handed: one member's platform read "Anti-abortion legislation" while four
others' read "Pro-life advocacy", and forty Democrats had "Reproductive rights"
where eighty-nine Republicans had "border security" (TRUST-05). They reached
537 member profiles unbadged, reading as fact. None of it is shown now (rule
86); `validate` fails a profile whose education, careers or platform has no
source the page can name (`bio-unsourced`). `python build_profile_site.py
members` writes `data/members.json`, and each field is filled from a source
tied to the member by id, never by a search on their name:

| What | From | Shown as |
|---|---|---|
| Education, earlier careers | The [Official Congressional Directory](https://www.govinfo.gov/app/collection/cdir) (GovInfo, the latest edition for the sitting Congress): each member's "education:" and "professional history:" (with any "military service:"), in its words. An entry is joined to a member by the office web address printed under it, which must be the address `congress-legislators` lists for their bioguide id or lead to it when opened (the Directory prints dingell.house.gov, which leads to debbiedingell.house.gov), and its printed name must carry their surname. Members it does not hold, and entries that join no one, are a build warning (`members-directory-unjoined`) | The field, badged **Congressional Directory** |
| Education or an occupation, where the Directory has none | The infobox of the Wikipedia article `congress-legislators` maps the bioguide id to, its title checked against the surname after redirects ("Politician" alone is not an earlier career, and is left out) | The field, badged **Wikipedia** |
| The issues they work on | Their official website (the `.house.gov` / `.senate.gov` address `congress-legislators` lists): the page its home page links as "Issues" (or "Priorities"), read one level down - its links to its own issue pages, in their words - or the site's own "Issues" menu (a list or a panel of `<div>`s), or that page's list or headings, a heading every page carries (the offices' cities) excepted. A link is labelled by its first block of words (a card's title, not its blurb). Nothing that names the member or anyone else, a recent President or Vice President included ("Trump's One Big Beautiful Betrayal", "Repeal Obamacare"), and none of the site's furniture filed under Issues (Community Project Funding, Legislative Process, Bill Search, an office, office hours, appropriations requests, a help page). A line cut short ("Sponsored &") is not taken, and one issue spelled twice is listed once. Where the home page links no issues page, `/issues` is tried before the home page's own issue links, which are shown as what the home page features. A list of nothing but the House template's stock categories (Congress, Economy, Education, Energy, Health, Veterans) is not a platform the member chose, and "Congress" is never an issue; a page listing them among the member's own is quoted whole, since nothing on it tells a default kept from one chosen | Bullets badged **Official site**, dated and linked to that page; "On their official site's issues page", linked, where the site has an issues page but no list could be read from it, or lists only the stock categories; "On their official website", linked, where only its home page or menu links issue pages, too few to list; "Not listed on their official site" where the site has none |
| A contact form | The page the home page links as Contact (or Email me), fetched and seen to hold a form to write to the office - a message box, or a ZIP or street-address step, never a site search or a newsletter sign-up (a name and an email alone, or a form the page's settings name as its newsletter) - or to lead to one; only where `congress-legislators` holds none | The *Contact form* chip, its title saying when it was checked |
| Offices at home | `congress-legislators`' `legislators-district-offices`, by bioguide id: address, phone and hours | *District offices* (a senator's *State offices*), under a line saying a federal agency problem is casework for them |

The Biographical Directory (bioguide.congress.gov) answers HTTP 403 to a
script and a Cloudflare challenge to headless Chrome (2026-10-18), so it is
linked from every member's profile but not read. A site that turns the
request away, or draws itself with script, concludes nothing (rule 8) until
headless Chrome has read it too, and a read that concludes nothing keeps the
last good one. Official sites are read one request at a time, 1.5 seconds
apart, and again after 27 days.

## How members voted

A member's profile shows how they voted in the roll calls of the 119th
Congress: the most recent first, ten at a time, each with its date, the
question, the bill or nomination and its title as the record gives it, the
member's vote in the record's own word ("Yea", "Aye", "Not Voting", a name in
an election of the Speaker), the result, and a link to the official record.
A search box finds any of their votes by a bill's title or its number, typed
as a reader types it ("H.R. 1", "hr1", "S 5", "PN1129"; a number is matched
whole, so H.R. 1 is not H.R. 10). Beside them: how many roll calls the record
lists them as not voting in, of how many it lists them in. No votes are
chosen for the reader; there is no "key votes" list.

`python build_profile_site.py votes` reads the two official records into
`data/roll_calls.json` (`kyc/rollcalls.py`):

- **The House**: the Clerk's XML, one file a roll call
  (`clerk.house.gov/evs/<year>/roll<NNN>.xml`), each vote keyed by bioguide
  id. A number the Clerk has not posted is answered with HTTP 200 and an
  "Error sanitizing file" note, which is not a file and concludes nothing:
  the run stops there and the next one asks again.
- **The Senate**: each session's vote menu, then each vote's LIS XML, keyed
  by the senator's LIS member id, which congress-legislators maps to their
  bioguide id.

One request a second, saved every 25 roll calls; a run that stops keeps what
it read, and a refused or failed request ends the run rather than skipping a
vote. The weekly refresh reads what is new.

A vote reaches a profile only by an id the record holds, and only inside a
term congress-legislators gives the member in that chamber, so a vote cast
before someone was seated, or under another member's id, never appears on
their profile. The record's own words for each id - its state, its surname -
are checked against the member the id names, and an id that disagrees gives
nobody its votes (the build says so: `votes-unattributed`). The Clerk writes
a delegate's state as "XX", accepted only for a member who sits for D.C. or
a territory. A member who left keeps the votes they cast. An id the record
lists for no member of the Congress (Matt Gaetz, who did not take his seat,
is in the first roll call) is an evidenced entry in
`overrides.ROLL_CALL_NON_MEMBERS`.

Roll calls held while a member served that do not list them at all are never
counted as missed, and the profile says how many: the Clerk lists a Speaker
who does not vote nowhere, and a delegate only in the Committee of the
Whole's roll calls. Each is said with the House's own rule, quoted (Rule I,
clause 7; Rule III, clause 3(a)).

The build writes `data/votes/house.js` and `data/votes/senate.js`, each
rewritten only when its content signature changes. They are not in
the people files: every page that opens a profile names them, with their version
stamps, in an inert `<template id="onDemandData">`, and the dialog loads a
chamber's file the first time one of its members is opened (`KYC.loadData`).
While it loads the panel says so, and if it fails, that it failed.

The left-right score from Voteview stays beside the votes, headed "Voting
record, left to right (Voteview)". A senator whose seat is not on the 2026
ballot reads "Seat up in 2028" (or 2030) in the dialog, as on the card; a
seat on the 2026 ballot says so through its race.

## Public offices held

Every profile, and every officer on the federal page, has a "Public offices
held" panel, and a card names the latest office beyond the seat it is about
("Fmr. Governor of Florida"). `python build_profile_site.py history` reads it;
`kyc/history.py` builds it from two sources, each joined to the person by an
id (rule 32):

- **Congress** from congress-legislators, the same project as the membership
  snapshot: every term of every member, by bioguide id. Consecutive terms in
  one seat are one span ("U.S. Representative, Vermont, at large, 1991-2007,
  8 terms").
- **Every other public office** from Wikidata's "position held" on the
  person's own item: the id congress-legislators records for a member, the
  item of the article a challenger's election page links (rule 33), the
  Cabinet history's id for an officer. A statement counts when it is not
  deprecated or qualified into something else ("instance of: assistant"),
  has a start, is not a seat in Congress, and is a public office or a
  judgeship in a U.S. state or place. A federal post counts only when it is
  on a reviewed list (the presidency, the Cabinet, a few more) or is an
  ambassadorship or a federal judgeship by its class.

An office is shown only where the person's own Wikipedia infobox gives the
same office the same start and end years, and is otherwise withheld and
reported - Wikidata's statements are the only free record of state and local
office, and they are wrong often enough to matter (rule 69). Three
agreements are shown, each said as such on the page:

| Agreement | Shown as |
|---|---|
| The same years | the years |
| Within a year at both ends | Wikidata's years, marked "±1 yr" |
| The same start, where Wikidata records no end and the article does | the article's end, marked "end: Wikipedia" |

"Acting" comes from the article's own entry. Years only: Wikidata often
records the election and the article the swearing-in. A profile the site
could not tie to an item reads "No linked record of public offices", with
why; a record whose offices could not be confirmed says so. A list opens by
saying it holds only offices the sources agree on and that others may be
missing: Keith Sonderling's listed only his Cabinet office while his OGE
report beside it was filed as Deputy Secretary. A read that fails or comes
back short keeps the committed cache.

What an agreement on office and years cannot check is checked on its own:

- **The place.** An office's place is its Wikidata item's jurisdiction, and
  a place below a state is shown only when it lies in a state the person is
  tied to - their profile's, their seats in Congress, their statewide
  offices. Wikidata's Jefferson County Judge/Executive is in Jefferson
  County, Oklahoma; Mitch McConnell's office is shown without it
  (`history-place`).
- **The district.** A span that crosses a redistricting names no district.
- **The name.** A position whose article is a list ("List of governors of
  Colorado") is named by its label.
- **What is current.** A seat in Congress is current while the membership
  snapshot lists the person, by the bioguide id their seats were read
  under, and the term runs past the snapshot's date - decided at build
  time, so a read from October does not keep a senator who left on January
  3 "since 1985". A seated member whose record holds no current seat is
  reported (`history-behind`).

## Election flags and races

Derived in `kyc/profiles.py` and `kyc/races.py`, shipped in the data.

| Field | Meaning |
|---|---|
| `isCandidate` | A 2026 challenger, not a sitting member |
| `seatUp2026` | This seat is on the 2026 ballot |
| `seekingReelection2026` | Seat is up **and** the incumbent is on the ballot for it |
| `raceId` | For a member, the seat they hold; for a challenger, the seat they filed for |
| `contestRaceId` / `contestLabel` | A member contesting a *different* seat: a redrawn district, the other chamber. Never set for a winner seated since in the seat they won (`raceRole`); their held seat is `heldRaceId` |
| `alsoRunningId` / `incumbentId` | Cross-link between a member and a separate profile for their own candidacy, matched first by any FEC id Congress's record lists for the member, then by name and state. The member's profile links that campaign's totals, labelled with its office and FEC id; they are never folded into the member's own (rule 68) |
| `otherOffice` | Sitting members only: `{text, source, checked}` when they are another office's November nominee ("Republican nominee for Governor of Florida"), from `overrides.OTHER_OFFICE_NOMINEES`, each the winner the election's results page marks, read on `checked`. From the day after Election Day the page says it in the past tense ("Was the ..."), since this site does not read that race's result. Dropped once the member starts a new term |
| `raceStatus` / `raceStatusRace` | `nominee`, `advanced`, `eliminated`, `withdrawn` or `unlisted`; `qualified` for Louisiana's open-primary House ballot before its count; a state's certified list of November candidates, where one was read, decides `nominee` and `unlisted` over the results page (`raceStatusSource: "certified"`, rule 77); after Election Day also `elected`, `defeated` or `runoff` (a general-election runoff); and the race it refers to |
| `ballotParty` / `fecParty` | The party the ballot lists, when it differs from the roster or FEC record |
| `ballotLine` | For a nominee only: the November ballot line as the results page spells it ("Speak The Truth", "Party for Socialism and Liberation"), when it is not the line of the party shown. Never set for "none", a write-in or a line named after the candidate themselves (an independent petition reads as "Independent"); `party` is never overwritten by it |
| `senateClass` | Sitting senators only: the constitutional class of the seat (1, 2 or 3), from the term record in `congress_snapshot.json`, keyed on bioguide id. `null` only when the build has no snapshot, which validation reports |
| `nextElection` | Sitting senators only: the year the seat is next on the November ballot, from the real term end date - a term ending 3 January is decided the November before; an appointee's term ending on election day is decided that year. Class II -> 2026, Class III -> 2028, Class I -> 2030, except a special |
| `senateSpecial` | Sitting senators only: `true` when `nextElection` comes before the class's regular cycle - a special election for the rest of the term (Ohio and Florida's Class III seats in 2026) |
| `rosterSeat` | For a curated challenger, the seat the roster gave them when the FEC filing says otherwise |
| `formerMember` | `{left, via, congress}`: a record incumbent - who held a 2026 seat - or a 2026 winner who has since left Congress. A winner keeps `raceRole` "winner" and `fecIds`, the FEC ids their archived row kept. Built from their `Former_Members.csv` row with the same bioguide id, so their race, money, portrait and links still find them. Never counted as sitting: every "who represents me" view asks `record.seated` / `KYC.seated`. The term ends the day they left; the archived status line and committee seats are not shown | Record incumbents who have left |
| `raceRole` | `"winner"`: a member seated since Election Day for the term a 2026 race decided, in a seat they did not hold (`record.seat_changes`); `raceId` is that race, and they are its winner, never its incumbent, never "re-elected". `"successor"`: seated in such a seat since Election Day for another term - a special election for the rest of the old one, an appointment - and in the race only if they ran in it. A record incumbent who won another seat (Andy Barr, KY-6 to the Senate) keeps `contestRaceId` for it | Members seated in a 2026 seat they did not hold |
| `committeesPending` | The Congress whose committee rosters are not published yet. It is set from January 3, a chamber at a time, until that chamber's rosters are whole: every full committee has members and nine in ten of its members hold a seat (`legislators.committee_chambers`). It replaces the previous Congress's seats, and the profile and the guide say so. A member of a chamber whose rosters are whole but who holds no seat has none, and is not pending | Sitting members, early in a Congress |
| `heldRaceId` | The 2026 race whose seat this record incumbent held, sitting or former, whatever they sit in now; what counts them among a chamber's seats up | Record incumbents |
| `appointed` | The record says this incumbent was appointed to the seat on the ballot. Never "re-elected" or "renominated": they were not elected to it | Florida, Ohio, Oklahoma and South Carolina's appointed senators |
| `politicalHistory` | `{wikidata, wikipedia, rows, withheld}`: the public offices the person has held, newest first. A row is `{office, where, district, from, to, current}`; a seat in Congress adds `congress` and `terms` (`district` 0 is at large); another office adds `agree` - `year-off` where the sources differ by a year, `start` where the end year is the article's alone. `withheld` counts offices Wikidata lists that the article does not confirm. See [Public offices held](#public-offices-held) | Members, and challengers whose election page links their article |
| `otherIds` | A curated candidate's profile id (`CAND_n`) folded into the member they became, by the FEC id Congress's record lists for them; a link or market label saved under it opens the member | Curated candidates since seated |

Each race (`kycRaces`) carries, beside `incumbentIds` and `candidateIds`:

| Field | Meaning |
|---|---|
| `incumbent` | From the frozen record: `{bioguide, name, party, profileId, seated, appointed}` - who held the seat on the ballot, named even when they have no profile here; `seated` while they still sit in it |
| `winnerId` | The profile of the member seated since Election Day in this seat, when it is not the record incumbent |
| `senateClass` / `special` | The Senate seat's class, and whether it is a special election, from the record |
| `results.sourceUrl` | Where the race's statuses were read: the Wikipedia results page the cache names (by its title), or the Secretary of State's Candidate Inquiry for a ballot read from a qualified list. The race head links it ("Results: Wikipedia, read Oct. 17, 2026"), and every status says whose word it is ("per Wikipedia's results page"), never "the published results", which read as a certified count |

| `lastElection` | The seat's last election, from `seats` (`kyc/seat_history.py`): `{year, date, kind, candidates: [{name, party, votes, share}], others, othersShare, total, margin, checkedBy}` - the winner and runner-up as the Clerk of the House's statistics count them, shares of the votes cast for a candidate (blank and void ballots excluded), the margin of the votes. `kind` is `general`, `runoff` (Georgia's 2021 runoff), `rcv-final` (Maine's final ranked-choice round) or `unopposed` (with the Clerk's `note`); `rankedChoice: "first-choices"` where the counts are first choices (Alaska). `checkedBy` is `"mit"` or the Wikipedia article checked against. `{redrawn: true, year}` for a district redrawn for 2026, which carries no 2024 figure (rule 90); `{withheld, year}` where no second source agrees. `seatedSince: {name, since, how}` where someone took the seat after the counted election without having won it, by `special-election` or `appointment` (from the frozen record and the snapshot): the result is then the last regular election's. The sources' titles and addresses are `kycBuildMeta.lastElectionSources`, by year |

`incumbentIds` comes from the record too: the person who held the seat, sitting or former, never whoever sits in it now. Every race of the record exists, whoever points at it.

### The seat's last election

`python build_profile_site.py seats` reads the Clerk of the House's
"Statistics of the Presidential and Congressional Election" for 2020, 2022
and 2024 from its PDF: every House seat's 2024 result, and each Senate
seat's latest election to the term on the ballot (Oklahoma's class II seat
was last elected in 2022's special, Nebraska's in 2024's). The FEC's own
compilation for 2024 was not published when this was built. Each result is
shown only where a second compilation names the same winner and runner-up
in that order with counts within 1%: MIT Election Data and Science Lab's
Senate returns, and for the House each state's 2024 Wikipedia page (MIT's
House file sits behind a download form asking for a name and an email).
What no second source confirms is withheld and says so. A district redrawn
for 2026 shows no 2024 result: it says the old lines' election was other
voters' and links where its area came from.

Each race block, on the state pages, in the grid's races view and in the
profile dialog, shows under its people the campaigns' money as bars on one
scale (raised including loans, spent, cash on hand, each row with its own
through-date), the last election folded, and "Compare the ballot": party,
offices held, money, the campaign's own platform headings with where they
came from, and its site. The grid's sort menu orders races closest first by
one market's prices - Kalshi's or Polymarket's, the gap between its two
highest, never a blend of the two.

## State pages

Every state and territory has its own page - `states/tx.html`, and
`states/index.html` listing all fifty-seven - written by the build from one
template in `kyc/pages.py`. A page opens with the state's headline figures,
then who holds its seats (senators first, then the House by district), then
every 2026 race in ballot order with the sitting member, everyone on the
November ballot, and the people the primary removed folded under each race.
The same profile dialog opens from every card.

The pages carry nothing but the state code; `assets/kyc-state.js` renders
them from its own state's people file, of the same build the grid and map load, so a state page can
never disagree with the grid about who represents a district. Each is also
written with its `<h1>`, its delegation and every race's people as plain
lists, from the same build, for a reader without scripts and for a crawler;
the script draws the full view over them. They are generated, so `verify`
regenerates them in memory and fails when a page on disk is not what the
template would write.

They are linked from everywhere a state is named: the race headers in the
grid, the profile dialog's "Represents" line, the state filter in the sidebar,
the map's delegation panel, the footer, and `sitemap.xml`.

## Know Your Government

`government/` is the guide to the offices around the people this site covers:
Congress, the executive and the federal courts, state governments, local
governments and tribal nations, and how elections work. Its eight pages are
generated, like the state pages, from the shared template in `kyc/pages.py`,
with their words in `kyc/government_text.py`.

The elections page (`government/elections.html`) answers what readers ask in
November and December: when federal elections are held and who runs them,
primaries and other ways of nominating, runoffs (Texas, Georgia's December 1
general runoff, Louisiana's December 12 round), ranked-choice counts in Maine
and Alaska, counting, canvass and certification (with *Watson v. RNC*, June
2026, on mailed ballots that arrive after Election Day), recounts, when the
winners take office, and how vacancies are filled. It names states only as
examples from their own laws and never counts states it did not check. Its
40 claims were drafted from primary sources and then attacked one by one by
a second reader; 11 were corrected (among them that Alaska's voters decide
on November 3 whether to repeal its top-four primary and ranked-choice
general elections). It was checked on 2026-10-16, a later date than the rest
of the guide, and its footer says so (`"reviewed"` on the page).

The words are static, so they are held to the standard of everything else
here in a different way:

- **Every section cites its sources.** The outline came from a report the
  site's owner supplied. Every checkable claim in it was checked against
  primary sources (the Constitution, the U.S. Code, court opinions, the
  Census Bureau, the Bureau of Indian Affairs, NCSL, state codes) by one
  researcher and then by a skeptic trying to refute the result. Where the
  report was wrong, out of date or took a side, the guide says what the
  sources say: 575 federally recognized tribes, not 574, since Congress
  recognized the Lumbee in December 2025; the FTC's removal protection struck
  down in *Trump v. Slaughter* (2026); the 94 district courts counted with the
  three territorial ones; "unitary executive", a contested legal theory,
  replaced by what Article II says. The footer gives the date the text was
  last checked (`REVIEWED`).
- **Nothing about a person is typed into it.** Who chairs each committee and
  who leads its minority comes from the same committee rosters as each
  profile, rendered by `assets/kyc-guide.js`; each name opens the profile.
  `test_guide.py` fails if a current officeholder's name appears in the text.
- **A link that leads nowhere is a build error.** Links are written
  `[label](target)` with a target the build resolves: `guide:congress#senate`,
  `site:map.html`, `state:TX` or an `https://` URL. `validate.check_guide`
  fails on a missing page, section or state, an unknown source, or a source
  no section cites.
- **One name per page.** A guide page's title, heading, navigation entry,
  card, pager link and every other page's link to it are one string
  (`government.name`), and a test fails on a link that calls a page anything
  else.
- **Counts come from the tables they describe.** "In {{ltgov-presides}}
  states the lieutenant governor presides" is filled from the map's own
  table (`government_maps.figures`), so the text and the map cannot
  disagree; the 2026 ballot counts come from `kyc/ballot2026.py`.
- **Figures are page text.** How a bill becomes law, who checks whom, the two
  court ladders and the Election Day to January 3 timeline are HTML boxes,
  never SVG text (rule 46). The timeline's status words are the site's own
  (`KYC.raceStatus`), and the step a reader is at is marked by their date.
- **Leaders come from the data.** The Speaker, the floor leaders, the whips
  and the other party posts are listed from congress-legislators'
  `leadership_roles`, kept per bioguide id in the snapshot (`leadership`,
  with each post's start) and shown on each member's profile while they
  sit. A post counts only when its record began in the Congress the
  snapshot is of (`legislators.held_posts`): the record leaves the sitting
  Congress's posts open-ended until after the next begins, so in January
  the lists say the new Congress's leaders are not recorded yet rather
  than name the last one's. A title the record words as something else is
  shown in the chamber's words (`overrides.LEADERSHIP_TITLES`: the Senate's
  "Republican Senatorial Committee Chair"). Tribal leaders come from the
  BIA's directory, with a disputed leadership said in words and the
  directory's asterisks dropped; a caucus's own style for its minority lead
  (`overrides.COMMITTEE_TITLES`, "Co-Chair") with the evidence.
- **No guide page loads profiles.** The Congress page's committee leads and
  chamber leaders are written in by the build (`pages.committees_html`,
  `leaders_html`), each a link to the profile on the grid; it loads only the
  build's figures for its sidebar. The others load only `kyc.js` and
  `kyc-guide.js`, and carry their "Jump to" list in the HTML.

Every page links to the guide from its sidebar, and the guide links back into
the grid, the Senate view, the map and the state pages.

### The guide's maps

Four of the guide's pages are maps, laid out like `map.html` and drawn by the
same code (`assets/kyc-usmap.js`): views over the map, a legend, and a panel
that lists everything the page says about a picked state, each fact with its
sources. `#/?state=TX&mode=veto` opens any view as sent.

| Page | Views | Source |
|---|---|---|
| State governments | Legislature (chambers and seats), who presides over the senate, line-item veto, how high-court justices are chosen, what each state elects on November 3, 2026 | NCSL; Book of the States 2022, tables 4.14, 5.1 and 5.6, checked for changes through October 2026; `kyc/ballot2026.py`, each state's own record |
| Federal courts | The circuit each state's appeals go to, numbered on the map | 28 U.S.C. 41; 48 U.S.C. 1824 |
| Local governments | Counts of every kind of local government, and of counties, municipalities, townships, school districts and special districts | Census of Governments 2022, table CG2200ORG02 (`census` command) |
| Tribal nations | Public Law 280: the six states the law names and the ten that took jurisdiction later; tribal governments by the state of their office, each with its leader | 18 U.S.C. 1162; BIA; the BIA's Tribal Leaders Directory (`tribes` command) |

The data is `kyc/government_maps.py`, emitted as `data/government.js`
(rewritten only when it changes; `verify` checks its signature). A view must
give every one of the fifty states a value, or `validate.check_guide` fails:
a fact known for a few states and not the rest stays in the text, which is
why there is no map of "councils that check the governor" - Iowa, Florida
and others have boards of elected officials that a two-colour map would deny.
Colours are categories (`--cat-1` to `--cat-5`, `--scale-1` to `--scale-5`),
never party colours. Circuits that share a border never share a colour; the
build colours them from the atlas's own borders (`geo.neighbours`).

Compiled tables were checked, not trusted. The Book of the States 2022 says
New Jersey's Supreme Court has five justices; the court's own site says a
chief justice and six associates. Utah enlarged its court to seven in 2026,
and Maryland renamed its own in 2022. Michigan's justices, whom the table
lists as partisan, run on a ballot that shows no party, so the map, which
groups states by what the ballot shows, puts Michigan with the nonpartisan
states.

The Census table marks a kind of government a state does not have with "X".
That is kept as "none" - Texas has no township governments - and never
written as a count of zero (rule 19). `census` refuses a table whose states do
not add up to its own national row.

## State legislatures

Every state has a page for its legislature, `legislature/<st>.html`: its Senate
and House districts on a map in their members' party colours, a panel for the
picked district with each member's party, contact details, portrait and
links, and every district listed below. `#/?chamber=lower&d=134` opens any
district as sent. Every state page links to it.

| What | Source | How |
|---|---|---|
| Members, party, district, contact, portraits, links | Open States, per-state current legislators (public domain) | `python build_profile_site.py statelegs` writes `data/state_legislators.json` |
| District boundaries | Census Bureau cartographic boundary files, 2025 (1:500,000), districts as set for the 2024 elections | `python tools/fetch_legislative_maps.py` writes `legislative_maps/<st>.json` |

Each member keeps Open States' own id, and is placed on the map by matching
their district's name to the Census boundary's, after both are reduced the
same way: "10th Bristol District" and "10th Bristol", "Hampshire-Franklin-
Worcester" and "Hampshire, Franklin and Worcester", "Merrimack 08" and
"Merrimack 8"; Idaho's seats 10A and 10B are district 10. Anyone who still
does not match is reported by `statelegs` and listed on the page under "Not
on the map", never guessed: New Hampshire's floterial representatives, who
sit for districts that overlay others, and Maine's non-voting tribal
representatives, elected by their nations rather than a district.

A seat Open States lists nobody for is "nobody listed", not "vacant": the
record may be behind a special election. Two states' lines changed after the
Census captured them, and their pages say so: Michigan's Senate (new lines
from November 2026) and Mississippi (2025 special elections under redrawn
lines, then vacated by the Supreme Court in May 2026). The Census server
refuses New Mexico's 2025 senate file, so that map comes from the 2024 file,
which holds the same districts.

The map is `assets/kyc-regionmap.js`, a renderer for any regions keyed by
any id - counties and towns are next - built on the district pages'
techniques: one definition per shape, labels as page text at 11px for the
drawn width, close-ups planned by `kyc/districts.insets`.

What a member's card and a chamber's summary show (`kyc/legislature.py`,
audit 2026-10-17):

| On the page | From | Rule |
|---|---|---|
| Party, and "Also on the ... line" | Open States' party label, split at "/": New York's and Connecticut's fusion lines are not parties, so "Democratic/Working Families" counts as Democratic | `party_name`, `fusion_lines` |
| District office phone, capitol phone and address | Open States' `district_voice`, `capitol_voice`, `capitol_address`, labelled as which office; the bulk export carries no capitol phone today | `_person` |
| One page, labelled as what it is | The member's page on a host of `LEGISLATURE_HOSTS` ("Official page"); never a file, a party caucus's page on the legislature's host, a past numbered General Assembly or Legislature (Illinois's `GA=`, Arizona's `legislature=`, Delaware's `/AssemblyMember/150/`), a page whose address names another member and not them (Rhode Island's roster links some twenty members to one colleague's page), a page for the other chamber, or one keyed to another district (`districts_in`: Kentucky's `DistrictNumber=`, Louisiana's `H_Reps/members?ID=`, Texas's `?district=`, California's `sdNN`, Florida's `/Senators/sNN`), which shows whoever holds that seat now - Open States keeps a senator's old House pages. A page chosen for two members is neither's. Where only the legislature's list of their bills is linked (Connecticut), "Bills on the legislature's site"; where only a past session's page is (33 in Indiana, 9 in Hawaii), it is shown with its session, a fallback, never as current; where the legislature's site has nothing, their page on a party caucus's site (`CAUCUS_SITES`: every Michigan legislator's), "Party caucus page: <caucus>", or the chamber's member list (Alabama's ALISON). Alabama's old ALIS pages are not used: they time out. A member with none says so on the card, and `build` and `build --check` count each kind | `member_page`, `pages_for` |
| Portrait | Open States' image, unless it is a search engine's thumbnail (gstatic, googleusercontent) or `statelegs` confirmed it missing - a GET answered 404 or 410 (never HEAD, which Massachusetts answers 404 for portraits it serves). A 200 that is not an image, a refusal, a throttle or a timeout concludes nothing (rule 8); each answer stands 14 days. `statelegs --images-only` checks again without refetching the roster | `check_portrait`, `check_images` |
| Portrait where Open States has none (`image`, `imageCredit`) | The legislature's own: Montana's roster API, New Jersey's bio records, Oklahoma's House pages, Louisiana's and Connecticut's seat pages, Indiana's IGA records, Ohio's directories, Colorado's list, and any other state's member page (for their own chamber) where the image's alt, file name or the member's own key in the page's address names them - never an album's or a gallery's photograph, nor one file offered on two members' pages. Only a rendition the legislature offers within 300 KB and 1,200 px; a member offered only heavier files is left without one and counted. A seat-keyed file (by district, or by surname and district, Kentucky's `senate1NN` among them) is shown only when dated on or after the member's arrival and only for the seat it was read for; a host that stamps its files by a deploy (California's Assembly), or a batch of seat files copied together long after the member arrived (Louisiana's of May 2024), does not date it. A page that calls the member former (New Mexico's `Former_Legislator`) or a directory listing their seat as vacant gives no photograph, and `build` names them for the roster to be checked. Michigan (party caucuses' photographs only) is not read; Kansas's pages name files that answer 404 and are read again each run; pages drawn by script are listed as unread. Credited `Photo: <legislature>`, linked to the page it was read from; Open States' own portrait is credited the same way, linked to the member's page, when the legislature serves it | rule 100, `legphotos` |
| Seats by party, majority, coalition note | The state page's own count (`stategov.chamber`) and note (`stategov.COALITIONS`); a different answer is a build error | `_count` |
| One square per seat | The same count: Republicans from the left and Democrats from the right, as the counts beside them read, nobody listed as an outline, a tick above and below at half the seats (none for Nebraska's nonpartisan chamber). Also on every state page and the directory, with one key each (`KYC.seatStrip`, `KYC.seatKey`) | rules 51, 73 |
| Seats on the Nov 3 ballot, and which districts | `ballot2026`'s record, read into districts only where its list or rule names exactly as many seats as it says are up; the term only where that record states one. A district the record names for a special election for the rest of a term (Kansas Senate 24 and 25, Nebraska 41, New Mexico Senate 33, Colorado Senate 17, 21, 29 and 31, ...) is marked `special` and its panel says first that it is on the ballot; a special naming no district on the map fails the build. The record is quoted only where it says more than "all" or "none" | `seats_up`, `specials`, `term_years` |
| Floterial district | New Hampshire's floterial members are named with their district under "Not on the map", where RSA 662:5 makes the district floterial (`NH_FLOTERIAL`, 39 districts, each the union of base districts); any other unplaced district is "unmatched" | `unplaced_why` |

## Governors and party control

The partisan map has state views beside its three for Congress - the
statewide offices (**Governors**, **Lt. governors**, **Attorneys general**,
**Secretaries of state**)
and party control (**Legislatures**, **Trifectas**) - and every state page has
a "State government" section drawn by the same module
(`assets/kyc-stategov.js`): the governor, with party, time in office, office
website, NGA biography and the office's address and phone; the lieutenant
governor and secretary of state, with how each holds the office and whether
they run the state's elections; and each chamber's seats by party.
`map.html#/?state=TX&mode=sos` opens a view as sent.

| What | Source | How |
|---|---|---|
| Governors: name, party, terms, office contact, headshot | National Governors Association, current governors (50 states and 5 territories) | `python build_profile_site.py executives` writes `data/executives.json` |
| Seats by party | The Open States legislators behind the legislature pages | `statelegs` (above) |
| A second count of seats, control and governors' parties | NCSL, State Partisan Composition | `executives` writes `data/partisan_composition.json` |
| Lieutenant governors, and who is first in line where there is none | National Lieutenant Governors Association, members | `officers` writes `data/statewide_officers.json` |
| Secretaries of state: party, elected or appointed, chief election official, contact | National Association of Secretaries of State, membership roster | `officers` |
| Attorneys general: who holds the office | The office's own website, linked from USA.gov's page for the state | `officers` |
| How to vote: registration status, polling place, absentee and early voting, registering | Each state's own pages, as NASS's "Can I Vote" (nass.org/can-I-vote) lists them. Shown as "Voting in <State>" on the state page | `voting` writes `data/voting_links.json` |
| Key dates: registration deadlines (online, by mail, in person), same-day registration, early voting, mail-ballot application and return deadlines, a late-arriving ballot's last day, runoffs | Each jurisdiction's election office: its pages, calendars and statutes, read 2026-10-17 and every value re-opened by a second researcher. Every value shown carries the page's address and its words, on the jurisdiction's own domains; a compiled table (NCSL, Ballotpedia, Wikipedia, vote.gov, Vote.org, fvap.gov, usa.gov) is refused as a source. Where same-day registration exists, a deadline before Election Day is called the regular deadline, and where it happens is quoted in the office's words. Shown in words and as a calendar strip in "Voting in <State>", each line linked, and marked passed on the reader's own calendar day; "Register to vote" says when registration closed. From the day after the election only a ballot still arriving and a runoff stay | hand-edited `data/voting_dates.json`, checked by `kyc/voting_dates.py` |
| Official results, sample ballots, registration deadlines, territories | `voting.RESULTS` (every state and D.C.) and `voting.SAMPLE_BALLOTS` (where the election office links a statewide one), each the office's own page; vote.gov's page for deadlines only where the jurisdiction's own record (above) does not say when registration closes; the territories' election offices (`voting.TERRITORY_LINKS`) | curated in `kyc/voting.py`; opened by `voting` with NASS's links |
| Attorneys general: party | Republican and Democratic Attorneys General Associations, members | `officers` |

A party holds a chamber when it has more than half of **all** its seats; a
seat Open States lists nobody for counts for no one. A trifecta is one party
holding the governorship and both chambers. Open States and NCSL are counted
separately and must agree about which party holds each chamber: where they do
not, the map shows "Sources disagree" and the panel shows both, rather than
either. On 2026-10-05 they agreed in all 50 states, as did the NGA and NCSL
on every governor's party.

Two cases the counts alone would get wrong are written down with their
evidence (`stategov.COALITIONS`). Alaska's Republicans hold a majority of the
seats in both chambers, but the Legislature's own roster lists a Republican
as minority leader in each: coalitions of both parties run them, so Alaska is
not drawn as a trifecta (NCSL, counting seats, calls it one). The note is
about the 34th Legislature, read from the session number in each member's
akleg.gov link; once the members listed belong to the 35th, or the seats stop
fitting it, the note is not shown and `build` says why. Nebraska's
Legislature is elected without party labels and is drawn as nonpartisan.

The roster is cross-checked against Wikidata's record of each state's
incumbent; Wikidata is a lead, never a source, and any disagreement is
reported, not applied. A governor's first day in office is shown only where
Wikidata records the same date: the NGA's own pages give Kay Ivey April 19,
2017 and Kim Reynolds May 27, 2017, and they took office on April 10 and May
24, so neither date is shown for them. A territory's page heads the section
"Territorial government"; its legislature is not covered yet. The NGA posts its headshots only at full size,
0.3-7.6 MB, and a guessed smaller URL is a 404, so a headshot over 1 MB is
left off the card. D.C. has a mayor and council, and its page says so.

Each association is the authority on its own members, and where two name
the holder of one office they must agree. NASS's member in Alaska, Hawaii and
Utah is the lieutenant governor (those states have no secretary of state);
NLGA's in Arizona, Oregon and Wyoming, which have no lieutenant governor, is
the secretary of state, first in line; where both name one office's holder
and disagree, the page names both and shows neither. "Acting" is the same
office on either roster. NASS marks some entries "Currently Not a NASS
Member": such an entry is not NASS speaking for its own member, so it never
overrides NLGA's - its Hawaii entry named Sylvia Luke, whom Keith Regan
(acting) had replaced - and a secretary of state NASS lists for a non-member
state is shown as fact only when that office's own site names them (Florida,
Virginia and Wisconsin's do; Nevada's draws itself with JavaScript, so it
stays NASS's listing). A state with no lieutenant governor says who is first
in line, unless that office is itself vacant or disputed; New Jersey's
lieutenant governorship is vacant, as NLGA lists it. A photograph from
either roster must carry the person's surname in its file name: NASS's alt
text calls every one a state seal, and NLGA's card for a vacancy carries the
association's logo.

No association lists every attorney general in a form a script can read
(NAAG's site is behind a Cloudflare challenge), and neither party's
association is trusted for the name: on 2026-10-05 RAGA listed for North
Carolina the Republican Jeff Jackson beat in 2024, and printed "Maryland" and
"Vermont" as members' names. So the associations - which between them have
covered all fifty - give each candidate and their party, and a name is shown
only when the attorney general's own office, linked from USA.gov's page for
the state, names that person beside the title: 48 of 50 on 2026-10-05.
Where the office's site refuses a script (Massachusetts, New Hampshire) the
page says which association lists whom, and that the office could not
confirm it. A few offices need another official page
(`officers.OFFICE_PAGES`: Wyoming's staff page, Kansas's state portal) and a
few a different front door (`OFFICE_LINK`: USA.gov's West Virginia link is a
404). A page that draws itself with JavaScript concludes nothing.

An attorney general's photograph is the office's own
(`officers.add_ag_photos`), read from the pages that confirmed the name and
the attorney general's page they link ("Meet the Attorney General", "About
Nick Brown"): never NAAG's, which refuses every script, never a party
association's, and only for a holder the office confirmed. An image is taken
when its file name or alt text carries the surname and says it is a likeness
("headshot", "portrait", "photo of") or is nothing but the name and the
title; when nothing in its words or class says logo, banner, seal, header,
slider or a scene ("talking to a townhall crowd", "sworn in"); when it is
head-and-shoulders shaped; and when it, or a size of the same file its
srcset or its host's resizer serves, is no heavier than 300 KB or 1,200px.
The cache keeps `photo`, `photoPage` and `photoWeight`; a read that
concludes nothing keeps the same person's last photograph. On 2026-10-18 the
offices of 19 of the 48 confirmed attorneys general showed one that passed;
the others' are too heavy (California's is 6 MB), landscape, unlabelled or
drawn by script, and each build lists them. A photograph the rosters cannot
tie to a person - NASS files some under the state's code, "AZ.jpg" - or one
from a governor's own office where the NGA's is over 1 MB is shown through
`overrides.OFFICER_PHOTOS`, an entry naming the holder it was checked for,
the page, its weight and the evidence, and it is withheld, with a warning,
once the roster names someone else. Each card's sources line says whose
every photograph on it is.

### What else is on the November 3 ballot

The site lists the candidates for Congress, but a reader's ballot holds
more: 36 governorships, most lieutenant governors, attorneys general and
secretaries of state, and 88 of the 99 legislative chambers (6,139 seats)
are elected the same day. `kyc/ballot2026.py` says which, state by state:
for each of the governor, lieutenant governor, attorney general and
secretary of state, how the office is filled and whether it is on the 2026
ballot; for each chamber, how many of its seats are up for regular election
(a special election to fill an unexpired term is not counted, and the page
says "regular" wherever a count could be read as the whole ballot). Every
value cites the
state's own constitution, statute or 2026 election pages - never NCSL,
Ballotpedia or Wikipedia, which were leads only (rule 50) - and was
researched state by state and then checked again by a second, independent
reader (300 checks, one correction: West Virginia's Senate President holds
the title of lieutenant governor as Tennessee's Speaker does).

`ballot2026.check()`, run by `build --check` (`validate.check_ballot2026`),
fails the build if a state is missing, an appointed
office is marked as elected, a joint ticket's lieutenant governor is not
elected with the governor, a source is a compiled table, or a chamber's size
disagrees with `government_maps.SEATS` (rule 53); a county's page is not a
state's record. The counts on the page are derived, never typed.
`ballot2026.TERRITORIES` covers the territories' governors and lieutenant
governors: Guam's and the Virgin Islands' from the Organic Acts (48 U.S.C.
1422, 1591), the Northern Mariana Islands' from its Commission's certified
list; American Samoa and Puerto Rico elected theirs in 2024. D.C. elects a
mayor, and the map says so. Arizona's lieutenant governor, a new office
first filled on November 3, reads "No one holds this office yet", not "no
such office".

Two more tables, each checked by `ballot2026.check()`:

- `NEXT`: when an office or chamber that is not on the 2026 ballot is next
  elected, only where a statute or the state's own record gives the year
  (Virginia's governor in 2029 by Va. Code 24.2-210, its legislature in
  2027), with the month where it is not November (Louisiana's October
  round reads "Next election: October 2027"). Never computed from a term
  length; an office without an entry shows no year.
- `OPEN_SEATS`: an office on the ballot whose holder cannot run for it
  again, from the constitution's term limit (read with the NGA's count of
  the governor's terms). `stategov` withholds an entry, and says so in the
  build, when the office's holder is someone else or the NGA counts fewer
  terms. Whether a holder is on the ballot is the list of candidates' to
  say (below); a term limit stays beside it as the reason, and the two must
  agree.

On the page:

- each state page's list of races for Congress says which of the offices
  this site covers the same ballot also elects, that it may hold other
  contests and measures this site does not list, and that the site lists the
  candidates for Congress there and those for the offices whose lists it
  holds, by name ("those for the attorney general under State government"),
  not those for the legislature; a territory's says its Territorial
  government section lists the governor's candidates;
- the State government section and the map's state panel mark each office on
  its own label line - "This office is on the Nov 3, 2026 ballot", never
  under the person who holds it, who may not be running - or say why not
  (not elected in 2026, with "Next elected: November <year>" where `NEXT`
  has it; appointed; chosen by the legislature; no such office), each mark
  linked to its source. Under each office, its holder line, read from the
  office's list of candidates for whoever holds it today: "Open seat:
  <holder> is not among the candidates for this office (<the list>)" (with
  "is term-limited ... and" first where `OPEN_SEATS` has the limit), or
  "<holder> is among the candidates for this office (<the list>)" - never
  "running for re-election", and the list named as the document it is -
  until Election Day. An office whose list does not settle its holder (a
  namesake on the list) says "Whether <holder> is running for this office
  is not checked here" (`holderStatus` "unchecked") and the build says why,
  so no office is silent beside another's "Open seat";
- the map has a "2026 governor's races" view: a state electing its governor
  is drawn in the party of its current governor, every other state in the
  empty grey, and the legend says the colour is the current governor's; an
  open seat says so in the state's label, naming the list.

### Statewide candidates

Under each office on the ballot, the candidates its election office lists
(rule 91): `data/statewide_candidates.json`, a hand-edited cache researched
jurisdiction by jurisdiction on 2026-10-18 from each Secretary of State's,
board of elections' or election commission's own list - a county election
office's or another state body's only where the state's own could not be
read or does not exist (Arkansas, Arizona, Nevada) - with every list
re-opened by a second reader. Ballotpedia, Wikipedia, news and party sites
were leads, never sources (rule 50). 129 offices in 42 jurisdictions; the
build log counts the candidates, the lists whose own words certify them and
those that are not the state's own.

| Shown | Source | Field (`ballot2026.offices.<office>.candidates` in `stategov.js`) |
|-------|--------|-------|
| Each candidate's name, first name first, in ordinary capitals and without a ballot title; the list's own form on hover | the list (`statewide.display_name`) | `candidates[].name`, `.printed` (where the two differ) |
| "(the list gives a surname only)" where the ballot prints a ticket by surnames | the list | `.surnameOnly` |
| The party, in words where the list abbreviates it (`statewide.PARTY_CODES`, from the list's key or the statute); a write-in's "WRI" or "Write-In (...)" label is dropped | the list | `.party` |
| The running mate on a joint ticket; the ticket as the ballot prints it, where it prints surnames | the list | `.runningMate`, `.ballotName` |
| A link to the candidate's own record, where the list is one record per candidate (Pennsylvania's lieutenant governors) | the election office | `.record` |
| Write-in candidates, apart, "names not printed on the ballot" | the list, or the office's write-in list | `.writeIn`; `writeIns` (its address, office, kind and day read) |
| "Source: <the office’s kind of document> (read <day>)", linked | the list | `url`, `by`, `source`, `read`, `certified` |
| "Not the state’s own list." and why, for a county's or commission's | the list | `notStateList` |
| The office's holder on the list | `statewide.holder_status` | `.holder` (the search leaves them to their holder row) |

Candidates are listed by surname, printed names first, and the page says
so: the lists' own orders differ (Minnesota rotates its ballot by
precinct). No portrait, money or platform for these people; none is a
profile, and none is linked to a profile of the same name (rule 25): the
lists carry no id. A sitting member of Congress a list names in their own
state is a build warning (`statewide-member-unnoted`) until an evidenced
`overrides.OTHER_OFFICE_NOMINEES` entry says so on their profile. The home
search finds the candidates under their own heading, "Statewide candidates
on the Nov 3, 2026 ballot", as "Candidate for <office>, <state> (Nov 3, 2026
ballot)" - also by the list's own form of the name - linked to the state
page; from the day after Election Day, "Was a candidate for <office>,
<state>, on the Nov 3, 2026 ballot". From that day the state page's block
is in the past tense too, and links the state's official results page
(`voting.RESULTS`): this site does not read state results and names no
winner.

`statewide.problems`, run by `build --check` (`validate.check_statewide_candidates`)
and by every build (`stategov.build` stops), fails a list that is not the
jurisdiction's election office's (its own domains, or an evidenced entry in
`overrides.STATEWIDE_LISTS_ELSEWHERE`, which says whether it is the state
office's own document on another host), has no quote, kind or day read, an
office the list covers that `kyc/ballot2026.py` does not put on the ballot
or the reverse, a list marked certified without the document's own words
saying so (`certifiedQuote`) or published by anyone but the state's own
office, a county's or commission's list that does not say why
(`notStateList`), a party code `PARTY_CODES` cannot spell out, a candidate
field the list does not print, two holders on one list, an elsewhere entry
no list uses, and a holder said to be off the list whose surname is on it -
a namesake is recorded with why in the office's `namesakes` ("Eddie Lee
Murphy" is not Governor Bill Lee). A holder the list writes with another
given name ("Lombardo, Joseph") is settled only by
`overrides.STATEWIDE_NAME_FORMS`, with evidence.

### Statewide questions

The statewide ballot measures on each jurisdiction's November 3, 2026 ballot
(rule 95): `data/ballot_measures.json`, a hand-edited cache researched
jurisdiction by jurisdiction on 2026-10-19 from each election office's own
list - its qualified or certified measures, its voter guide, the official
sample ballots - and re-opened by a second reader (`verified`). Ballotpedia,
NCSL, news and advocacy sites were leads, never sources (rule 50). 147
statewide measures in 41 jurisdictions, and New Hampshire's HB 1300
question, on every ballot but decided town by town; 11 whose official record shows none; 4
(American Samoa, Maine, Pennsylvania, Puerto Rico) where no official source
says either way. Measures decided at an earlier 2026 election (Alaska's
Ballot Measure 1, Missouri's August amendments, Alabama's May amendments)
and those a court removed are not listed; the research notes name them.
`kyc/ballot_measures.py` writes `data/measures.js`, which the state pages
and Your ballot load; one implementation draws both (`KYC.ballot`).

| Shown | Source | Field (`kycMeasures.<code>` in `measures.js`; the cache's in brackets) |
|-------|--------|-------|
| "<n> statewide questions are on the Nov 3, 2026 ballot, as <office> lists them: <list>, read <day>" | the office's list | `has`, `by`, `list`, `read` (`hasMeasures`, `by`, `listSource`, `read`) |
| "Official voter information: <guide>" | the office's guide | `guide` (`voterGuide`) |
| Each measure's designation, and its title where the state prints one (Alabama, Missouri and Tennessee print none) | the measure's source | `measures[].designation`, `.title` |
| Its official text, quoted, folded after about four lines ("Read the whole text") and printed whole; "Cut where marked" where the source cuts it | the measure's source | `.text`, `.cut` (`question`) |
| Its kind (constitutional amendment, statute, bond, referendum on a law, advisory question, constitutional convention question) and who put it on the ballot (the legislature by its own name, a citizens' petition, the constitution), or "not recorded here" | the source | `.kind`, `.origin` (`kind`, `origin`, `kindWords`, `originWords`) |
| What the quoted text is, where it is not the ballot's own wording (California's guide summaries) | the source | `textNote`, `.note` |
| "Its page in the voter guide", "Source (read <day>)" | the office | `.guide`, `.source` (`voterGuide`, `source.url`) |
| "No statewide question is on the Nov 3, 2026 ballot", and what shows it: the office's sentence, quoted; its list of its ballots' questions; or "This site read <the ballot> on <day>, and it prints no statewide question", naming the ballot read | the office | `none.from`, `none.words` (`noneFrom`, `noneWords`) |
| "One more question is on every ballot, but is not one statewide decision: each town or city votes on it for itself", listed apart and not counted, with how each ballot fills in its text | the measure's source | `.local` (`local`, with its `textNote`) |
| "This site has not found an official list of statewide questions ... and does not say there are none", with the election office's own site | the office | `office` |

The page never says what a yes or a no vote does in its own words - where
the official text says so (Arizona's, Ohio's), it is quoted - and nothing is
coloured by side. Local questions are "not listed here", with the state's
sample ballot where its office links one. "Statewide" is a state's word: the
District's are "District-wide", a territory's "Territory-wide", and Puerto
Rico, which holds no election that day, lists none; neither the District
nor a territory is told of a county's questions. A list's or guide's title is
the document's own name. From the day after Election Day the heading and the
lead are in the past tense, beside the state's own results page ("that were
on the ballot" only over a list, never over "none" or "not found"): this site
reads no result of a ballot question.

`ballot_measures.problems`, run by `build --check`
(`validate.check_ballot_measures`), by `verify` and by every build (which
writes no `measures.js` from a cache that breaks a rule), fails a measure or
list that is not the jurisdiction's own official page (its domains, or an
evidenced `overrides.MEASURE_SOURCES_ELSEWHERE` entry: a county's official
ballots, an office's file store) or is unquoted, a "none" without the words
or ballots it rests on, a "not found" that lists anything or names no
office, a kind or origin the page cannot word without the record's own, any
field the record does not define (a "yes means" of the site's own has none),
a measure listed twice, a shown title that carries an address or a
researcher's note, a `local` question without its `textNote` or a list of
only local ones, and a date outside the cycle.

## State high courts

Every state page's "State government" section, and the map's state panel,
list the state's court of last resort: its members as the court lists them,
the chief first, how justices are chosen and for how long (from the guide's
table), and a link to the court's own roster. Texas and Oklahoma also list
their Court of Criminal Appeals. No party is shown: a justice is not a
party's officeholder.

No national source lists sitting state justices - the Conference of Chief
Justices publishes only its board, and the National Center for State Courts
has no directory - so each roster is read from the court's own page with a
recipe in `courts.COURTS`: the page, the slice of it that holds the court,
and a pattern for one member (or, where the page draws itself with
JavaScript, the JSON it loads: Florida, Michigan, Minnesota, Oregon). A
roster with more names than seats, or two chiefs, is refused. Fewer names
than seats reads "nobody listed by the court" for the rest (California's,
Hawaii's and South Carolina's on 2026-10-06), never "vacant"; Utah's page
names no chief justice since Chief Justice Durrant retired, and the page
says the court lists none. An Associate, Vice or Deputy Chief Justice is not
the chief.

Until 2026-10-18 ten courts were listed with no members. Now:

- Connecticut's, Louisiana's, Massachusetts' and Tennessee's pages answer a
  browser but not a plain request, or draw their justices with JavaScript.
  Their recipes carry `browser: True`, and `courts` reads them in a headless
  Chrome through `tools/read_court_pages.mjs` (Node 22 or later, no
  dependencies; Chrome from `$CHROME` or the usual install paths). The
  reader keeps a page that answered with an error status, such as a bot
  wall's 403, out of the read, and a page that ended on another host than
  the court's (a redirect answers 200 too). A run with no Node or no Chrome reads none of
  them, says so, and each keeps its last good read (rule 8). The weekly
  refresh installs Node 24 for it.
- Rhode Island publishes its roster only as a PDF. `courts.pdf_lines`
  reads the file's own text with `zlib` alone. The recipe reads the Supreme
  Court's block, skips "Justice (Vacant)", and takes the date the file says
  it was revised, which the page shows ("dated June 5, 2026"). The link says
  "(PDF)". A name is letters, spaces and punctuation alone: a justice's line
  that holds anything else (a phone number set on the same baseline) is
  refused, not read into the name. A response that is not a PDF is refused
  (rule 52).
- Missouri's, New Hampshire's, Nevada's and New York's sites refuse every
  automated reader, a headless Chrome included (Cloudflare, Akamai, and
  Missouri's notice forbidding scrapers). Their rosters were read by hand
  from the court's own page in an ordinary windowed Chrome, and are kept in
  `overrides.COURT_ROSTERS` with the day they were read and the page's
  words. The build fails on one that does not fit its seats and chief, as
  a read roster would be refused. The page says "read by hand on" that day.
- Alabama's site resets every connection, from a browser too. Alabama is
  the one court left in `courts.UNREADABLE`: its page names the court and
  says why its members are not listed.

Every read carries its day (`read`), and a court kept at its last good read
keeps that day, never the cache's `fetched`, which every run rewrites. The
build warns about a court kept at its last good read, or a roster read by
hand, more than `courts.STALE_DAYS` (45) days ago, and `courts` reports any
court whose members changed since its last read. The list of sources under
each state's government names its court and the day its roster was read.
Nothing is taken from Wikipedia or Ballotpedia.

## The federal executive

`python build_profile_site.py federal` records who holds the federal
executive's offices, in `data/federal_executive.json`. The federal
government's page shows them (below).

| Fact | Source | Notes |
|---|---|---|
| The President and Vice President: name, party, term, ids | congress-legislators' `executive.json`, the project behind the membership snapshot | A term that does not cover today is a build error, so a stale file never shows a past President |
| That they are the White House's | whitehouse.gov/administration/ | The page's own links ("President Donald J. Trump"); a different name is reported |
| Their portraits | Their own White House pages | The first image in the page's content |
| Who the Cabinet is, and who holds each office | whitehouse.gov/administration/cabinet/ | The authority on which officials the President counts as Cabinet, and on nothing else (rule 55). A title the office table does not know stops the read |
| That the office names them | The office's own page (`federal_offices`), the name beside the title (rule 56) | Seven departments answer every script with 403: that concludes nothing (rule 8), and the office is shown as the White House lists it. OMB's pages name no Director |
| The Senate's confirmation | senate.gov's roll-call votes, no key | Found by the Senate's own wording of the office and the holder's surname - two signals, never a name alone. A voice vote has no roll call, and the record says none was found, not that there was no confirmation |

The fifteen departments are the ones 5 U.S.C. 101 lists, in the order 3
U.S.C. 19(d)(1) gives their heads in the line of succession - from the
statute, never from a page, which lists people by surname. "Secretary of
War" is the Secretary of Defense's secondary title under Executive Order
14347; the statute and this table say Defense. No Cabinet officer is given a
party: no source used states one, and the President's is not theirs.

## The federal judiciary

`python build_profile_site.py judiciary` records every sitting Article III
judge in `data/judiciary.json`. The federal government's page and one page
per court show them (below).

| Fact | Source | Notes |
|---|---|---|
| Every judge's service on every court: appointed by, nominated, confirmed (and the vote), commissioned, senior status, chief judge | The Federal Judicial Center's Biographical Directory of Article III Federal Judges, exported nightly | The FJC is the judiciary's own research agency (28 U.S.C. 620); its `nid` is each judge's id and builds the link to their FJC page |
| Birth, education, career | The same directory | The career is the FJC's own words, quoted, never paraphrased |
| Who sits on the Supreme Court | supremecourt.gov's list of the justices (rule 57) | The directory's open Supreme Court rows include two retired justices, who are not members: read naively it seats eleven |
| The courts, and the circuits | `kyc/federal_courts.py`, from 28 U.S.C. 41 and the directory's court names | 13 courts of appeals, 91 Article III district courts, the Court of International Trade; Guam's, the Northern Mariana Islands' and the Virgin Islands' courts are Article IV courts the directory does not cover |
| The territorial courts' judges | Each court's own website (`kyc/territorial_courts.py`): Guam's "Judicial Officers" page, the Northern Mariana Islands' banner, each Virgin Islands judge's own page | A recipe per court, as for the state high courts (rule 57): district judges only, never more than the statute's seats (48 U.S.C. 1424b, 1614, 1821), at most one chief; a page not read keeps the last roster, and one never read says so - never "none". Shown by name and title, with nothing to open |
| A judge's Wikipedia article, Wikidata item and portrait | The FJC's own page for the judge's `nid`, whose canonical address is the judge's slug; the Wikidata item carrying that slug as P2736 (`kyc/judge_links.py`) | Two ids, never a name. Two items for one slug, a label or article title without the surname, an item whose year of birth is not the directory's (or that gives none), two images or two articles: nothing. A portrait is a JPEG, PNG or WebP no more than a fifth wider than tall, not in `overrides.NOT_A_PORTRAIT`, drawn from Wikimedia's sizes of that one file (rule 42) and credited under the judge's name with its author and licence as the file's Commons page records them (`by`, `licence`, `licenceUrl`, read with the file's size); a file with no recorded licence, or a non-free one, is not shown, and the build fails a Commons portrait without a licence (`judge-portrait-licence-missing`). Read by `judiciary`; a failure keeps the last links |
| Each court's website | uscourts.gov's list of court websites (`kyc/court_info.py`) | Joined to the court ids by the circuit, state and district the list names, never by host name (`ca-n` is `cand.uscourts.gov`); every host the judiciary's own; each address fetched once |
| Which district court, and which division, covers each county | 28 U.S.C. 81-131 as govinfo publishes it (`tools/fetch_court_districts.py`, `kyc/court_districts.py`) into `data/court_districts.json`, with the amendments since the edition | The statute's names joined to the Census counties by name within the state; every county of a state of several districts placed exactly once or the build fails; a Code spelling or typo is an evidenced alias; Virginia's independent cities placed by their neighbours only where all agree |

A judge is sitting on a court when their service there has a commission and
no termination; senior from the day senior status began, never before; the
court's chief while their service as chief judge has begun and not ended. A
confirmed nominee with no commission is not sitting, and the build says so.
A judge sitting on several courts (a roving judgeship) is one person.

Two things the directory's rows need read together:

- **A chief judge on senior status.** A chief judge must be in regular
  active service (28 U.S.C. 136(a)), so a record holding both cannot say
  who is chief. Nobody is shown as that court's chief, the page says the
  record is contradictory, and the build warns (`judge-record-conflict`).
- **A statutory reassignment.** The Fifth Circuit's judges were reassigned
  to the new Eleventh in 1981. The open row names no President and dates
  the reassignment, so the appointment and the commission are taken from
  the row the reassignment ended, and the seat says when it was reassigned.

**Judges have no party.** The directory's "Party of Appointing President"
columns describe the president, not the judge: they are dropped when the
file is read, with its gender and race columns, so nothing later can show
them, and a check fails if a judge's record ever carries a party. A judge is
appointed by a president, by name.

## The federal government's pages

`federal/index.html` shows who holds the federal government's offices:

- the President and the Vice President, with their shared term said once;
- the Cabinet as cards with portraits, the fifteen departments first in the
  order of succession, each with the Senate's confirming vote, whether the
  office's own page names the holder, since when they have held it and whom
  they followed;
- every change in the Cabinet since the term began (below);
- the Supreme Court as cards with the justices' official portraits, with
  retired justices listed apart;
- a map of the states by federal judicial circuit, and every federal court,
  the courts of appeals and then each circuit's district courts, with a
  search of every sitting judge.

### Portraits

The Cabinet's portraits are the White House's. Its originals run to 6.5 MB,
so each card draws from the sizes the White House serves of that one file,
read from the srcset on its Cabinet page (`photoSet`, rule 42). Those URLs
contain commas (`?resize=428,600`), so the srcset is read by its "url width"
pairs, never split on commas. A justice's portrait is the Court's official
portrait as Wikimedia Commons holds it, credited to its photographer and
licence as the file's page gives them (the owner's decision of 2026-10-20:
the Court's photographs page asks for approval before its images are
published, and the portraits are its staff photographers' work).
`overrides.JUSTICE_PORTRAITS` names each justice's file and the author it
was checked against; the judges' read takes that file for them, by every
check a judge's portrait passes (`route: "official"`), and the federal
pages show it only while it is that file credited to that author
(`judge_links.official_portrait`). A justice the table does not name keeps
the Court's own portrait, from its biographies page, credited to the
Collection of the Supreme Court of the United States, and the page says
whose portraits are the Court's own; so does a justice whose named file
the read did not take as recorded (`justice-portrait-unread`), and the page
says the read did not confirm it (`portraitUnconfirmed`), not that Commons
holds none. Today the table names all nine:
Sonia Sotomayor's Wikidata image is a 2009 White House photograph and
Elena Kagan's a CC BY-SA upload, so theirs name the public-domain copy of
each one's official portrait. Commons holds the Court's official portraits,
some of them earlier ones than the Court now shows: Roberts's is of 2005,
Alito's 2006, Thomas's 2007, Sotomayor's 2009 (the Court's biographies page
shows one of 2025), Kagan's 2010, Gorsuch's 2017, Kavanaugh's 2018,
Barrett's 2021 and Jackson's 2022 (each file's date, read 2026-10-25). The Court's own pictures are joined
only to the nine justices already joined to the directory, since the page
also pictures retired justices, and only when its caption's title agrees
with the justice's role. Any failure shows none (`justice-portraits`); a
table entry the read does not hold is a warning (`justice-portrait-unread`). Every other judge's portrait is the image
of the Wikidata item that carries their FJC id (above), never one found by
name; the shape and surname checks withhold what is not a likeness, and the
`judiciary` run lists each one withheld. Where the item has no single
portrait, one is taken only by these routes, each tied to the judge by id:

- two images: the one the item's own article shows in its infobox;
- a wide hearing still: a Commons crop that says it was extracted from that
  very file and depicts the item alone;
- no image: the article's infobox image, if the article also leads with it
  (an article with no lead image gives nothing).

A judge whose FJC id no item carries is found through the one article whose
`{{FJC Bio}}` names their nid; the entry carries `linkVia: "fjc-bio"`, and
the dialog's note on the links says they came that way. A search that fails
keeps the judge's last entry; one that answers no article or several is
reported. A Commons file whose licence is in doubt by one test - its page or
name points to an author who is neither its uploader nor a government office,
or names no author - is withheld in
`overrides.PORTRAIT_LICENCE_DOUBTS`, kept portraits included, and the build
fails a portrait the overrides withhold (`judge-portrait-overridden`). A photograph is used only at Wikimedia's own
sizes, up to the 250px a page draws. Its largest size is weighed and must be
within 300 KB and 1,200px; a file offered only over that is left out and
counted. Each portrait in `judge_links.json` records its `route`, the
`evidence` naming the judge beside it, the day `read`, and the `bytes`,
`width` and `height` of its largest size. The build fails a portrait without
them (`judge-portrait-unevidenced`). `judiciary --links-only` reads just
these for the committed directory.

### Changes in the Cabinet

The executive refresh also records who has held each office since the
President's term began (`kyc/cabinet.py`), into `changes` in
`federal_executive.json`:

- **Confirmed:** the Senate's own roll calls for that office, with their
  date and tally. The Senate's name rides with the vote ("Walter Clayton"
  is Jay Clayton).
- **Who held it:** Wikidata's "position held" statements on the office's
  own item (each office's id is in `kyc/federal_offices.py`). Only people
  with a dated start count, joined to a confirmation by the office and the
  surname within the term. A holder is named by their Wikipedia article's
  title, never by a Wikidata label; the current holder by the White
  House's name.
- **When:** in office from and to only to the precision on which Wikidata
  and the person's own Wikipedia infobox agree: the day, the month or the
  year. Wikidata gave Pete Hegseth's start as 2025-09-05; his article and
  the Senate say January. Where they agree on nothing, the page says the
  sources differ and shows no date. An infobox entry is the office's exact
  name, past an ordinal and "Acting" - "Deputy Director of the Office of
  Management and Budget" is not its Director - and a person who held the
  office before takes the entry of this term. An acting officer whose end
  both sources put after the next holder's start (Ingrid Kolb's acting
  service as Secretary of Energy to 2025-02-04, Chris Wright's from
  2025-02-03) shows no end and says why; no date is moved to fit, and the
  build warns `acting-overlaps-successor`.

The hub lists every change newest first: confirmed, left, acting. Each
card says since when and whom its officer followed - for an officer who
served as acting before being confirmed, "Acting from" the date their
article gives and "then confirmed" on the vote's date, never "Since" the
acting start - and the dialog lists
the office's holders this term. An acting officer Wikidata does not record
is not listed, and the page says so. A failed read keeps the last history
(rule 8).

Each court has its own page, `courts/<id>.html` (`courts/ca5.html`,
`courts/tx-s.html`): its chief judge, active judges and judges on senior
status. A district court's page links to the circuit its appeals go to, and
a circuit's page links to its district courts. The guide's executive and
courts pages link to the federal page.

A name opens the person's record in one dialog (`assets/kyc-official.js`):

- a Cabinet officer's confirmation and office page;
- a judge's every seat, with who appointed them, the dates and the vote;
- a judge's earlier federal service, birth, education and career, in the
  directory's words, and links to their FJC page, their court's website and,
  through the FJC id, their Wikipedia article and Wikidata item;
- a Cabinet officer who has left since the term began, as a record of their
  time in office with a "Left office" banner, at the same id; the changes
  table links their name;
- the other federal posts a Cabinet officer's own OGE report lists for the
  last twelve months, quoted in its words and attributed, only from a
  report checked to name its filer (rule 70), and apart from the offices
  two sources agree on (rule 69).

The hub also lists the line of succession (3 U.S.C. 19): the Vice
President, the Speaker and the President pro tempore from congress-
legislators' leadership roles, checked against the current membership, then
the department heads in the statute's order, with the statute's caveat for
an acting head. Each Cabinet card links the department's website as USA.gov's
index of agencies gives it, whether or not the office's own page could be
checked.

A court's page also shows its active judges by the President who appointed
them, a row per President with a square per judge and the count in words
(`appointers`, counted over the same judges as its "active" figure), in a
category colour and never a party's; the hub shows the courts of appeals
the same way. A "This court" block links the court's website, PACER's case
locator and CourtListener, and, for a district court, each division, where
court is held and its counties. Each county's panel names its district
court and division, from `data/courtcounties.js` - one small file for every
county, which the county pages load beside their own state's data - and each
state page lists its federal courts.

The court pages and the hub carry their names in their HTML, written from
the same payload as their data files, for a reader without script and for a
crawler; the page's module draws over them.

`#/official/<id>` opens it as sent; on the hub, a judge's name opens their
record on their court's page, which loads it.

A tied Senate vote confirms only on the Vice President's vote (Article I,
Section 3), and the page says so beside the tally. When the Senate's votes
could not be read, an officer with no earlier finding reads "could not be
read when last checked", never "no roll call found" (rule 19). The pages
cover Article III judges and say so: the Court of Federal Claims, the Tax
Court, the Court of Appeals for Veterans Claims and the Court of Appeals for
the Armed Forces (each linked to its own list of judges), and bankruptcy and
magistrate judges are not in the directory, and a search that finds nobody
says it searched the directory.

| File | What it holds |
|---|---|
| `data/federal.js` (`kycFederal`) | The President, the Vice President, every Cabinet office, the Supreme Court's members, and an index of the courts with their counts and chief judges |
| `data/judiciary/<court>.js` (`kycCourt[<court>]`) | One court's judges, loaded only by that court's page: 1,463 judges in one file would load on every page |
| `data/judiciary/index.js` (`kycJudgesIndex`) | Every sitting judge's id, name, court and status, for the search, and the directory's full name where it brackets a given name the judge does not use |

Every file carries a content signature and is rewritten only when what it
says changes; `verify` names a stale one. An official is never a profile:
ids are `x-<name>` for an executive officer and `fjc-<nid>` for a judge, and
nobody on these pages is counted among the members of Congress. The FJC's
directory lists judges, not judgeships, so no vacancy is ever counted from
it. Guam's, the Northern Mariana Islands' and the Virgin Islands' courts say
why the directory does not list their judges, and name them as each court's
own site does.

Who sits is two sources' word (rule 82). A judge the courts' vacancy list
has on senior status by a date on or before its own as-of date, whom the
directory still lists as active, is counted senior, and the row, the dialog
and the hub say which source says what. Announced vacancies are in the
future tense ("Will take senior status", "Nominated to the Fifth Circuit"),
and a confirmed judge with no commission is listed apart, under "Confirmed,
not yet commissioned", and counted nowhere. The hub's "Vacancies and
nominees" table lists every vacancy, now and announced, with its court and
nominee.

The directory brackets a given name a judge does not use ("A[llen] Joe
Fish"). The pages show the name they go by, "A. Joe Fish"; the dialog gives
the full name and the search finds either (`judiciary.display_name`).

### Vacancies

`python build_profile_site.py vacancies` reads the courts' own lists, which
the Administrative Office of the U.S. Courts publishes on uscourts.gov, into
`data/judicial_vacancies.json`. There are three lists:

- **Current vacancies.** Each row gives the court, the judge whose seat is
  vacant, why, since when, and any nominee with the nomination date. The
  page's own summary gives the totals, and a read whose rows do not add up
  to them is refused.
- **Announced vacancies.** Judges who have said they will leave, with the
  date where one is set.
- **Judicial emergencies.** Each one is matched to its current vacancy by
  court, judge and date.

A row is placed on a court by the list's court code: "05 - TX-S" is the
Southern District of Texas, and "05 - CCA" is the Fifth Circuit. The code
must agree with `kyc/federal_courts.py`. A code the table does not know is
kept and reported (`vacancy-court-unknown`), never guessed at. Names are
shown as the list writes them, in reading order, and never matched to
anyone's record.

The hub gives the totals and each court's count. A court page lists its
vacancies, its announced ones and any emergency. The build compares the two
sources and warns (`vacancy-judge-not-senior`) when the list says a judge
took senior status but the directory does not yet show it; the two are
updated at different times, and the court page says so. When the list
implies the judge still serves (a seat left for senior status, or one only
announced) and the directory lists nobody of that surname on the court at
all, it warns `vacancy-judge-not-listed` and the row says "Not listed by the
FJC directory as serving on this court now", and nothing about why. The
surname is compared without accents or a generational suffix ("Osteen Jr."
is the directory's "Osteen"), and only to report, never to join.

### Financial disclosures

The dialog of the President, the Vice President and each Cabinet officer
links the reports they filed with the Office of Government Ethics:

- the latest annual report;
- the report on nomination;
- the ethics agreement and its latest certification of compliance;
- the periodic transaction reports, counted, with the latest linked.

`python build_profile_site.py oge` reads OGE's index (`kyc/oge.py`), a row
per document, and keeps a row only when it is the office's and the holder's:

- **The office.** OGE's agency and position for it, a curated table
  (`oge.OFFICES`) checked against every office the federal table knows.
- **The holder.** Their surname, as a cross-check: OGE files legal names
  ("Turner, Eric Scott"), so first names are never compared, and two OGE
  names of one surname on one office are refused.

The holder's annual report filed under another post in the same agency
shows that post ("as Deputy Attorney General").

Only a file OGE serves is linked; a document OGE releases on request is
counted, and its request form is never linked as though it were the
report. Each report OGE generates names its filer, and each is opened once
(a check is kept with the report's address, which never changes): one that
names someone else - another surname, or another first name of the same
one - is not linked, and a scan whose name cannot be read is linked and
marked "not checked". Only this administration's reports are shown (from
120 days before its first day, when nominees file), so a sitting officer
is never shown a report on leaving the office from an earlier tenure. The
dates are the day OGE's index posted each report, and the page says
"posted", not "filed": a report signed in July can be posted the next
April. A holder with no row reads "OGE's index lists no report for this
officer under this office", never "not filed"; one the index was not read
for reads "This site has not read OGE's index for this officer yet".

## Counties and local governments

Every state has a page for its counties, `counties/<st>.html`: a map of its
counties shaded by how many local governments each has, and a panel listing
every government in the picked county - its county government, cities and
towns, townships, school districts, special districts (with what each does)
and the school systems a state, county or city runs - each with its own
website, city, and population or enrollment where the Census records them.
`#/?county=48201` opens Harris County as sent. Each state's page, House
district map, legislature page and counties page link to one another, so a
reader can go from the national map down to one town's government and back.

The source is the Census Bureau's 2022 Government Units listing
(`python build_profile_site.py localgov` writes `local_governments/<st>.json`):
one row per government, 92,114 in all with the dependent school systems.
Before anything is written the listing is checked against the Bureau's
published table of counts (`census`), for every state and type; one that
disagrees is refused. Governments join their county on the Census code,
never a name. The listing prints names in capitals; the page shows them in
title case (acronyms such as ISD kept, McX and O'X handled) and keeps the
published form in the data. Many addresses are in capitals too: the scheme
and host are lowered, the path kept as published.

Not every county area has a county government. Rhode Island's five
counties are geographic areas the state uses for its courts; Connecticut
abolished county government in 1960, and its map shows the nine planning
regions the Census has used in its place since 2022; seven Massachusetts
counties have no government; and a city and county can be one government
(San Francisco, Denver, Philadelphia, New York City's five boroughs) or a
city can lie outside any county (Virginia's 38 independent cities,
Baltimore, St. Louis, Carson City). `kyc/county_areas.py` holds all 112, by
Census code, from Appendix A of the Census Bureau's 2022 Individual State
Descriptions. Each one's panel says what it is and what governs it, the
list under the map marks it, the state's summary says it once, and the
build fails on one the table does not explain. A state's page calls its
areas what the state does: parishes, boroughs and census areas, planning
regions.

What the listing does not hold is who serves: it names the title of a
contact official, not the person. No free, authoritative national source
lists local officials, so the page says what each government is and links
its own site rather than guessing who runs it - and every panel that lists
governments says so in a line of its own, with where to look.

The listing abbreviates ("Fairfax Co Schs", "Covina Val Unif Sch Dist").
The page writes the abbreviations out from a closed table of whole words
(`localgov.ABBREVIATIONS`; a word that means two things, such as "Co" or
"Val", only where its neighbours say which) and keeps the Census's form in
the name's title. It never guesses an official name: "Fairfax County
Schools", not "Fairfax County Public Schools". The place beside a
government is its mailing address, and is labelled so; the Census's
function categories read in plain words ("Single-purpose district"). An
independent city is named as its state names it ("City of Alexandria",
"Baltimore City"), and Virginia's count reads "95 counties and 38
independent cities"; the list under the map sorts the City of Richmond
under R, and the map calls the county beside a city of the same name by its
whole name ("Richmond County", "Baltimore County"). The map names counties
where an 11px label fits at the width it is drawn (`labelRoom`, page text
over the map, rule 46), and only where a quarter of them fit - a lone
"Pecos" on Texas read as the pick; the picked county is always named.
Every county is in the list under the map, which has a filter.

The websites are the ones the Census listed in 2022, and in October 2026
about one in a hundred led to gambling, parked or for-sale domains under a
public body's name. `localgov --check-sites` opens every one (rule 78) and
writes what it found to `data/local_sites.json`, address by address, with
the day and the evidence. The build withdraws an address that is now
gambling, parked, for sale or expired, that redirects to a business's page
(a chamber of commerce, an estate agent, a funeral home) or to a site whose
title and address carry no word of the government's name, that is gone
(404 or 410, twice), or whose host does not exist (NXDOMAIN, or no address,
here and at dns.google and Cloudflare); the government's line says why and
when. A redirect to a page that names part of it ("City of Greenfield" for
the listing's Town of Greenfield) is the government's own site as often as
not, and stays linked, marked "not confirmed". Everything else is linked and
labelled "Website as listed by the Census in 2022, checked Oct 17, 2026"
(its own day); a 403, a 429, a timeout or a bot wall concludes nothing, and
a row whose link could not be confirmed says so in words. A person's own
finding goes in `overrides.BLOCKED_LOCAL_HOSTS`. Gambling seen plainly - in
a page's title, on a site a lapsed address now redirects to, or all over
its text - is never cleared by a later check; seen once in a page's text it
is withdrawn and reported for a person, since "Schedule your slot online"
is English. A look that concludes nothing never undoes a withdrawal. The
weekly refresh looks again at 6,000 addresses a run, oldest first, and the
build warns about any not looked at in 60 days.

### Cities and towns

The same page switches to **Cities & towns**: every incorporated place - city,
town, village, borough - as a dot coloured by the legal form the Census names,
19,517 in all, and, in the twenty states that have them, every town or
township government as a ring at its county subdivision. Picking one shows its government, with its own site and
population, and a link to its county; a county's list has a button that shows
each of its cities on the map, and every place is also in a filterable list
under the map, since a dot is small to tap on a phone.
`#/?view=cities&city=4835000` opens Houston as sent.

The places come from the Census Bureau's 2025 place boundaries
(`python tools/fetch_local_maps.py` writes `local_maps/<st>.json`), with
census-designated places left out: a CDP is a statistical area, not a
government. Each is drawn at the pole of inaccessibility of its largest piece
of land. Hawaii has none - every place there is a CDP - and its page offers no
cities view.

The listing's place codes are not the boundary file's (Texarkana, Texas:
68810 against 72368), so a place is joined to its government by name, within
the state, and only where the join is one to one: in three passes over what
the last left - name and legal form, name, then name without the forms after
it ("Phenix City" is the listing's "CITY OF PHENIX") - and, where a name is
shared, only by the county the place's point lies in. 19,451 places join by
name. Two kinds no name can join are curated, each with its evidence and
checked on every build: a city whose government is the consolidated one
`county_areas.AREAS` names (Kansas City, Kansas, and the Unified Government
of Wyandotte County and Kansas City; Baton Rouge and its city-parish:
`county_areas.CONSOLIDATED_PLACES`), whose panel says that government also
does the county's work; and a place the listing files under another name
("Cajah's Mountain", Encampment's Town of Grand Encampment) or on a
subdivision code the Census has since replaced (Mount Lebanon,
Pennsylvania), joined on the listing's own government id
(`overrides.PLACE_GOVERNMENTS`). The rest are mostly places incorporated
since the 2022 listing (Mableton, Georgia; Mountain House, California). They
are drawn, say that no government could be tied to them - the listing may
name it otherwise, or the place may be newer - and are reported by the
build; nothing is matched to its nearest name, and a place is never joined
to a town or township it replaced (Rib Mountain, Wisconsin).

Towns and townships are joined the other way: the listing gives each the
Census code of its county subdivision, and the subdivision boundaries
(`cb_2025_<st>_cousub_500k`, vendored by the same tool for the twenty states
whose Census table counts town or township governments) carry the same
code. 16,167 of the 16,214 are placed on their own code, the name checked
against the boundary file's. The other 47 changed after 2022 - Wisconsin's
Town of Madison was dissolved, Rib Mountain became a village, two
Massachusetts towns took city charters - and stay listed under their county
unless curated onto their place's point as above; none is placed by its
name. The cities view counts the ones left off the map, from the data, under
its lede. In Connecticut, Massachusetts and the rest of New
England, where the town is the local government, the town rings are most of
the map.

## District maps

Every state and territory has a district page, `districts/tx.html`. It draws
the state's House districts, numbered, with who holds each seat and who is on
the November ballot. Where the map for 2026 is not the one members were
elected under in 2024, the page draws both maps side by side.

Nine states are in that position. Each was checked against the enacting body's
own record on 2026-10-03:

| State | The 2026 map |
|---|---|
| CA | Proposition 50 (AB 604) |
| TX | Plan C2333 (HB 4, 2025) |
| FL | HB 1-D (Chapter 2026-229) |
| UT | The court-ordered map |
| NC | S.L. 2025-95 (districts 1 and 3) |
| OH | The Ohio Redistricting Commission's 2025 map |
| TN | Public Chapter 3 (HB 7003) |
| LA | Act 2 (SB 121) |
| AL | The Legislature's 2023 plan, put back in effect by the U.S. Supreme Court on June 2, 2026 |

Missouri is not on the list. Its 2025 map was suspended by a referendum
petition, and the courts kept the 2022 map in place; its page says so.

- **Every district numbered, at any width.** Numbers are 11px on screen at
  whatever width the map is drawn; the page measures it, and redraws when it
  changes. A number is written where its district has room for it: the build
  records each district's clear room around its label point. Districts too
  small to number on a phone's map are numbered in insets, which
  `kyc/districts.py` places around each cluster and names after its biggest
  towns. An inset drawn too narrow for every number in it, such as New York
  City on a phone, is followed by a closer one ("New York, closer").
  `tests/test_districts.py` checks that every district is numbered at every
  width from 300px up.
- **Who moved, from the data.** Members running in a different district are
  read from `contestRaceId` (rule 30) and grouped where their moves share a
  district. Bera and Kiley are one view, and Al Green's move from TX-9
  to TX-18 another. A redrawn state opens on its first group. Any district can be
  picked from a list or by clicking it. Shift-click, or the **Compare** switch
  on a touch screen, compares up to three.
  The choice is in the address (`#/?d=3,6`).
- **A close-up of the picked districts.** It shows county lines, towns, and
  captions naming who holds the seat or is running in it, from the state's people file.
  On a redrawn state the other map's lines are dashed.
- **Party colours.** Each district is drawn in the party of the member who
  holds it, or as vacant. A redrawn state's new map is left plain: nobody
  holds those seats until November, and colouring them would be a forecast.
  Picked districts keep their fill and are outlined in their highlight colour.
- **The people, as cards.** Each opens the profile dialog. On a redrawn state,
  each card also gives the share of the district's land that came from, or
  went to, each district on the other map.

Every state page links to its map, and so does the profile dialog of anyone
in a House race. For a member running in a different district, the link picks
out both districts. The address of the first California page,
`redistricting/ca.html`, redirects to `districts/ca.html`.

`kyc/districts.py` projects each state at build time with an equal-area conic
fitted to it. California uses EPSG:3310's parameters, and Alaska's Aleutians
are unwrapped across the antimeridian. So the page loads no mapping library,
and a share of the drawing is a share of the ground. `data/districts/<st>.js`
holds only geometry, one file per state; everything said about a person comes
from the state's people file.

The build fails loudly when:

- a map does not number its seats exactly once, or as the state's races do;
- a district's number would be drawn outside its shape, or on water the page
  clips away;
- the new map does not cover every old district.

### Sources

`tools/fetch_district_maps.py` writes `district_maps/<st>.json` and
`district_maps/places.json`. It is standard-library only and runs over the
network; nothing it writes is edited by hand.

| Layer | Source |
|---|---|
| The districts members were elected in, and county lines | Census Bureau 2024 cartographic boundaries at 1:5,000,000 (`cb_2024_us_cd119_5m`, `cb_2024_us_county_5m`), used as published. They stop at the shore. |
| A new map for 2026 | The state's own enacted-plan shapefile: the California Senate, the Texas Legislative Council, Florida EDR, the Utah Geospatial Resource Center, the North Carolina General Assembly, the Tennessee Comptroller, the Louisiana Legislature and the Alabama Secretary of State. Ohio's commission publishes no shapefile, so Ohio's comes from Wikimedia Commons map data (CC0). It was checked against the commission's block assignment file: every district covers exactly the counties the commission assigns it. Projected files (Web Mercator, Lambert conformal conic) are unprojected, and refused if any point lands outside the state. |
| Towns | Every incorporated place's Census Gazetteer internal point, ranked by Census Vintage 2024 population estimates. |

The new maps are simplified along shared arcs, so neighbouring districts still
touch. Their water is clipped on the page to the Census map's land; area
shares and the label sizes that depend on them are measured over land only.

An internal point is inside its place but not always inside the part anyone
means: San Francisco's is on the Farallon Islands, 52 km out to sea. A point
outside its place's largest piece of land, per the Census 2024 place
boundaries, is moved to that piece's interior, and the file records each move.
A second source was tried first and rejected: USGS GNIS disagrees with the
Census by kilometres for dozens of ordinary towns, and for Alvin, Texas, it is
the USGS point that is out of town.

### Find who represents you

The home page's hero, every state page, and every legislature and county page
open with **Find who represents you**, and the map page's sidebar holds it
too: a ZIP code box and a **Use my location** button, with **How to vote in
your state** beside them (`assets/kyc-findrep.js`). The voting button goes to
the state page's voting block (on the states list it waits until a state is
known). A ZIP code typed into the grid's search is answered by the panel,
and the empty grid says so with a button back to the answer. One answer
names, each linked:

- the U.S. representative, on the map members sit under, and the 2026 House
  race, on the map for 2026 where the state was redrawn (in Athens, Ohio:
  OH-12 now, OH-2 on the ballot), with the race's people and their status
  words, nominees with no profile here included;
- both senators, and any Senate race on the ballot;
- the state senator and representative, from the legislature page's own
  file, with their party in words and their district as the legislature
  names it ("District I", "Chittenden-16"), linked to the district there; a
  district with nobody listed says "nobody listed", and members the map
  cannot place are pointed to;
- the county, by the county page's own name for it (a parish, a borough, a
  planning region, an independent city), linked to its governments; in a
  territory, its municipio, municipality, island or district, as the Census
  Bureau calls them (`lookup.TERRITORY_AREAS`); none for D.C. and Guam, each
  its own county-equivalent.

The legislature and county pages load no people files, so the state's name,
its district map and its own lookup come from the lookup index
(`lookup.place_info`), and members of Congress are linked on the state page.

Everything happens on the device. The page downloads this site's file for the
reader's state, `data/lookup/<st>.js`, and looks the ZIP code or the point up
in it; nothing the reader typed or shared is sent anywhere, and the panel says
so beside the control. The Census Bureau's geocoder would take an address,
but it sends no CORS header, so a page could call it only by loading a remote
script, which the site never does, and it would send the address away.

A ZIP code is not a place (rule 85). The Census Bureau maps ZIP codes as ZIP
Code Tabulation Areas, built from the addresses in each block; a ZIP code used
only for post office boxes, or created since 2020, has none, and the answer
says so. A ZIP code across a state line says so before either state's answer,
and links each state's own lookup. A ZIP area's share of a district is a share of its land, from the
Bureau's relationship files: to the 119th Congress's districts, to the 2024
state legislative districts (the session year of every legislature map on
the site), and to the counties, except Connecticut's, whose planning regions
replaced its counties in 2022 and are measured instead. No relationship file
exists for a 2026 map, so `tools/fetch_lookup_maps.py` measures those shares
by overlaying the ZIP areas on the enacted plan; the same measurement of the
119th map is compared with the Bureau's file for every redrawn state and
written into the file (it differs by 0.05 to 0.3 percentage points on
average). A ZIP area with 99% or more of its land in one district names it;
anything else lists every district with its share, says a ZIP code can cross
lines, and offers the reader's location and the state's own lookup.

A location is placed on the Census Bureau's 1:500,000 boundaries (each
redrawn state's own plan for the 2026 map), simplified to 30 m or a
thirty-thousandth of the state's size, and on the legislature file's own
lines through the projection it carries (`projection`). Within 400 m of a
line, plus the browser's own stated accuracy, the answer names both sides and
says why, naming the kind of line: a congressional or state legislative
district line, a county line, or the state line and the shore. The
legislature's lines are coarser (simplified at 120-300 m and rounded for
drawing), so their margin is wider by what each file records (`lineErrorKm`),
and the answer says so. A state whose file did not load is never answered
with a neighbour's whose edge is near. Only the states whose box holds the point are loaded, and only
the reader's state's files are fetched for a ZIP code
(`data/lookup/index.js`: each ZIP prefix's states, and every file's
versioned address, rule 76).

### Your ballot

`ballot.html` (`assets/kyc-ballot.js`, rule 92) answers a different question
from the one above: not who represents a reader, but who is on their
November ballot. It is in the navigation under the election, and reached from
the lookup's answer (**See everything on your ballot**, carrying the ZIP code),
each state's voting block and the home page's hero. A ZIP code or a location
is looked up on the device exactly as above, and the page lists, one card per
contest:

| Contest | From | Shown |
| --- | --- | --- |
| U.S. Senate, regular then special | the 2026 race record | the race's badges and people as the state page's race section draws them: the same split, order, status words and counts (`KYC.cards.racePeople`, rule 73), nominees with no profile named, each person opening their profile. Under the race, only whom the lookup's answer lists (`KYC.stillRunning`); a filer whose ballot status is not known after the primary is named apart, and a holder off the ballot is named with their own status |
| U.S. House (or the Delegate, the Resident Commissioner) | the ZIP area's districts on the 2026 map | the same, one card per district with its share of the ZIP area's land where there are several, and the location offered for an exact answer |
| Governor, lieutenant governor, attorney general, secretary of state | `ballot2026` and the election office's list (rule 91) | the office's mark, its holder line (naming the holder as the holder) and its listed candidates, write-ins apart, as the state page shows them; the offices not on this ballot with their record's words |
| State senate and house | the lookup's legislative districts, `legislature.seats_up`, `legislature.district_seats` | whether each district's seat is on the ballot, in the legislature page's words and in the words its count of seats gives ("this seat", "this district's seats", "one of this district's seats"); where this site's record names no district, that is said on the row; its candidates are not listed here; a chamber with no seat in reach up is drawn as off the ballot |
| Statewide questions | `data/measures.js` (rule 95) | the same list as the state page's "Statewide questions" section, last, as a printed ballot puts them; a "none" or "not found" card drawn as off the ballot |

Then what the site does not list (local ballot questions, local and judicial
contests, the legislature's candidates), with the state's own sample ballot
where its election office links one, and, at the top, the state's key dates
as its voting block gives them, a date said passed on the reader's own day.
D.C. and the territories are in their own words; Puerto Rico's record says no
election is held there on November 3, and the page says so.

The address keeps a ZIP code (`ballot.html#/?zip=30303`), so a copied link
shows the same list, and never a location. From the day after Election Day
the page says the election has been held, shows the results the site has for
Congress and links the state's official results for everything else; it names
no state winner. **Print or save this list** prints the list without the
site's controls, in the light theme's colours whatever theme is on screen.

### Find my district

A district page with more than one seat has a **Find my district** button.
The browser shares the reader's location, if they allow it, and the page
places it **on the device**: nothing is sent anywhere. Each
state's district file carries the projection the build drew it with
(`projection`: the Albers parallels and meridian, and the fit), so the page
projects the location exactly as the towns on the map were projected; a test
replays every town's longitude and latitude through the page's own code and
checks it lands on the town's point.

The location is placed on the same finer lines as Find who represents you,
from the state's lookup file. The page's own drawing is the Census Bureau's
1:5,000,000 boundaries, simplified again for display; within 3 km of its
lines it could not tell a reader which side they were on, which in a big city
was nearly everyone (RACES-01). They are used only when the lookup file does
not load, with the 3 km margin. The answer names who represents the reader
and the 2026 race (PERSONA-18), draws a pin at their point on every view of
both maps, and in a redrawn state picks out each map's own district: the
address carries both (`#/?d=2&was=12`, PERSONA-01). It answers in one of
these ways:

- "You are in PA-16": inside one district, no line within reach;
- "near the line between PA-2 and PA-3": both are named, neither chosen;
- "in TX-13, close to the state line or the shore": the only line in reach
  is the state's own edge;
- "at the edge of Missouri or just outside it; the nearest district is
  MO-5": inside no district, but close to one;
- "That location is not in Pennsylvania", with a link to find the state.

A fix rougher than 10 km is "too rough to place in a district"; a fix that
reaches more than three districts is "where several districts meet", never
an approximate location, and a distance under a kilometre is said in metres
(RACES-02). A state redrawn for 2026 is answered on
both maps. A refused or failed location says what to do instead. Every
answer links the state's own voter lookup (from NASS's Can I Vote) to
confirm it, and the answer stays above the map rather than scrolling away.

## Contact and links

| Field | Source | Who has it |
|---|---|---|
| `website`, `phone`, `office`, `contactForm` | The member's current term record in `congress-legislators`; where it holds no `contactForm`, the contact page the member's official site links, fetched and seen to hold a form (`contactFormVia: "official-site"`, `contactFormChecked`: the day) | Sitting members |
| `districtOffices`, `districtOfficesRead` | `[{building, address, suite, city, state, zip, phone, hours}]` from `congress-legislators`' `legislators-district-offices`, by bioguide id, and the day it was read (`members`) | Sitting members it lists |
| `officialIssuesUrl`, `platformRead` | The official-site page the member's `platforms` was read from, and the day; `platformRead` alone where the site lists no issues | Sitting members whose site was read |
| `platformFeatured` | `true` where the site has no issues page and `platforms` is the issue pages its home page links: what the home page features, which may not be every issue | Sitting members whose list came from the home page |
| `directoryEdition` | The Congressional Directory edition (`CDIR-2026-02-20`) a member's education or careers came from | Members in the Directory |
| `social` (`twitter`, `twitter_id`, `facebook`, `instagram`, `youtube`, `youtube_id`, `bluesky`) | `legislators-social-media`, the project's verified account list. An X account is linked by `twitter_id` (`x.com/i/user/<id>`, which follows a renamed handle) where the file holds one; a handle X answers "not found" for with no id is dropped (`overrides.DEAD_X_HANDLES`). A YouTube value is given its shape in the pipeline: a channel id (`UC...`) becomes `youtube_id` (`/channel/`), an `@handle` stays one (`/@handle`), and a legacy username is linked as `overrides.YOUTUBE_LEGACY_NAMES` found it on a dated check, or dropped | Sitting members |
| `refs` (`govtrack`, `opensecrets`, `votesmart`, `ballotpedia`) | Reference ids from `congress-legislators` | Sitting members |
| `wikipedia` | The bioguide mapping for members; the state ballot page's own link for filed candidates (`wikipediaVia`), kept only while it leads, through its redirects, to a whole article about them (`enrich`) | Members, and candidates the ballot page links |
| `wikipediaWithheld` | `{title, landsOn}`: a ballot-page link withheld because it leads to a section of another article, a list, an election or a party ("Brian McGinnis" redirects to a protest), or to a title without their surname that `overrides.ARTICLE_UNDER_ANOTHER_NAME` does not record. Not shown; `validate` lists it | Candidates whose ballot link is not their article |
| `aliases` | Other names a voter may search by, all from the member's own `congress-legislators` record (matched on bioguide id): `official_full` without its quoted nickname, nickname + surname (+ suffix), and the Wikipedia title without its disambiguator ("Jim Clyburn", "Hank Johnson"), plus any evidenced, bioguide-keyed entry in `overrides.SEARCH_ALIASES` ("AOC"). Names that fold to the display name are dropped. Searched, never displayed as the name. For a filed candidate renamed to the ballot's spelling (`nameVia`), the FEC's filed form ("Mahesh Ganorkar", "Carlquist Lisa") | Sitting members whose record adds a name; filed candidates renamed from the ballot |
| `surname` | The surname the person is listed under in their race (`races.surname`): Congress's record for a member, the FEC filing's ("WASSERMAN SCHULTZ, DEBBIE") where it ends the name shown, else the shown name's last word less a suffix. "Name, A to Z" sorts by it | Everyone |
| `nameVia` | `"election-page"` when the name shown is the results page's spelling for this filing, settled word for word, by an evidenced `overrides.RESULT_NAMES` entry ("Max Ganorkar", whose filing says Mahesh), or by the rule-62 matcher where the page adds a hyphen or uses the short form of the filed given name ("Bob Harvie" for "HARVIE, ROBERT J"; never the formal form of a filed nickname); `"certified-list"` when it is the certified list's printed name (never one printed in capitals) | Filed candidates the results page names differently |
| `fecName` | The name the FEC files them under, set beside `nameVia`; the profile shows "Files with the FEC as ..." under the ballot's name | Filed candidates the results page names differently |
| `raceStatusSourceName` | Set with `raceStatusSource: "certified"`: the certified list that set the status, or that does not name the person ("Alaska Division of Elections, 2026 General Election candidate list"), credited in the badge's title | Filers in states whose certified list was read |
| `raceStatusUnconfirmed` | Set beside `raceStatus: "unlisted"` when the results page does not name the person but names someone similar who lost or withdrew. Off the November ballot either way, and shown as "Not on the November ballot", never "not on the primary ballot" | Filers in decided races |
| `maybeNamed` | Results-page names that may be this person under another spelling, one of them on the ballot. No status is inferred, and the race counts the person once, as that name | Filers the page may name differently |
| `unprinted` | `{kind, source}`: a complete certified list names the person but does not print them - `"write-in"` (a declared or certified write-in candidate) or `"unopposed"` (Florida does not print an uncontested race). Shown as "Write-in candidate" or "Unopposed, not printed", credited to the list; counted neither on the ballot nor off it (`ballotUnknown` is set beside it) | Filers a certified list names as a write-in |
| `rosterName` | The roster CSV's spelling, set when `name` was replaced by the name the member's own `congress-legislators` record (by bioguide id) says they go by: a recorded nickname + surname ("Jack Reed", "Bernie Sanders"); for a bare initial ("C. Franklin") a real middle name + surname; the roster's own parenthetical ("Chuck Edwards"); or a shorter form of the first name in `official_full` ("Greg Casar"). Keys the finance cache and stays searchable | About fifty sitting members |
| `campaignSite`, `campaignCommittee` | The principal campaign committee's Form 1 at the FEC (`data/campaigns.json`); for a challenger whose committee filed none, or filed one that failed the check, the race page's "Campaign websites" list (`campaignSiteVia: "election-page"`) once `enrich` has confirmed the site names them. Where the filed address cannot be reached at all and the same site answers with "www." added or taken away, naming the candidate, that form (`enrich --unreachable` re-reads only those) | Everyone on a ballot with an FEC id |
| `electionPageSite` | The site the race page lists, held back until `enrich` has read it; never shown directly | Filed candidates the race page lists one for |
| `campaignQuote` | The campaign home page's own description of itself, quoted (`enrich`) | Challengers still running whose site describes itself |
| `campaignIssuesUrl` | The page the campaign site links as its issues, platform or priorities | Challengers still running |
| `disclosureUrl`, `disclosureSource` | The member's latest annual financial disclosure: `house-clerk` (a PDF from the Clerk's annual index) or `senate-efd` (a report in the Senate's eFD system) | Members with a filing on record |
| `committeeList`, `committeesSource` | `committee-membership-current`, with rank and title (`data/committees.json`); a titled seat also carries `side` (`majority` or `minority`), because a title alone cannot say which - "Vice Chairman" leads the minority on Senate Ethics and Intelligence | Sitting members |
| `leadership` | The party and chamber posts congress-legislators' `leadership_roles` lists for the member's bioguide id in the Congress the snapshot is of (Speaker, floor leaders, whips, conference officers; never the previous Congress's open-ended posts), in the chamber's words where `overrides.LEADERSHIP_TITLES` says so; shown on the profile and the guide's Congress page while they sit | Sitting members who hold one |
| `pay` | `{amount, post?}`: the annual salary the law sets for the member's post, from `kyc/pay.py`'s table read from the Congressional Research Service's RL30064 (Table 1) and the Senate's salaries page, dated; `post` only where a leadership post (Speaker, President pro tempore, a floor leader) sets a higher rate. The year, the sources and the one sentence the page says of the rates' history (`stood`, the report's "unchanged since 2009") are `kycBuildMeta.pay`; a sitting member's filing for another seat shows the member's line, credited to their record; the profile shows the line only in that year, and nobody has one while the membership is of another Congress than the table's | Sitting members, in the table's Congress |
| `fecCandidateId` | Links the FEC's own candidate page | Everyone the FEC knows |
| `rosterFecId` | The curated roster's `FEC Candidate ID` column; the finance lookup takes it as the person's authoritative id, and `validate` checks its office and state against the profile | Curated candidates |
| `otherFecIds` | The same person's other FEC registrations (one committee's money reported under several ids, or a curated pair in `overrides.SAME_PERSON_FILINGS`); a link shared under any of them opens this profile | People registered more than once |

Every link on the page is built from one of those ids. Nothing is guessed
from a name: a Ballotpedia page derived from "Mike Rogers" is the wrong Mike
Rogers half the time, and nothing on the page would look wrong.

The **Contact & links** panel in the profile dialog shows the official and
campaign websites, phone and office, the verified accounts, and the
reference links. Committees render as a hierarchy from the rosters - each
full committee with the member's subcommittees under it and any chair or
ranking-member title called out - and fall back to the roster's typed column
only for the handful of members the rosters do not list.

Filed candidates the state's ballot page links to an article also get a
portrait from it. That link is an editor's assertion about this person on
this ballot, the same kind of authority as the bioguide mapping for
members, so it is the one exception to the rule that portraits are never
guessed for the field - and the resolved title is still checked against the
surname after redirects. Portrait coverage went from 572 to 773 profiles.

All 435 House seats are two-year terms, so every voting House member has
`seatUp2026 = true`. Puerto Rico's Resident Commissioner is the exception: a
four-year term (48 U.S.C. 891), elected in 2024 and next in 2028, so that seat
has `seatUp2026 = false` and no 2026 race. Use `seekingReelection2026` to find who is actually
running. `isUpIn2026` remains as an alias of `seatUp2026`.

The grid's **Senate** view (`#/?view=senate`) groups all 100 seats by when
each is next decided: the 2026 seats (Class II, then the Class III specials),
each with its sitting senator followed by the people running for that seat
from `kycRaces`; then Class III (2028) and Class I (2030). Validation makes
a senator with no class, or two senators from one state in the same class,
a build error, and warns when `nextElection` and `seatUp2026` disagree.

`window.kycRaces` holds every seat on the 2026 ballot: 35 Senate, 5
territory delegates (not Puerto Rico) and the voting House seats. Every one of the 435 House
seats is on the ballot, but a seat nobody currently holds has no roster row and
therefore produces no race, so the shortfall is exactly the vacancies. The 65
senators whose terms run past 2026 belong to no race.

The **Group by race** toggle on the grid groups an incumbent with everyone
challenging them.

## Headline figures

`kyc/summary.py` counts the chamber balance, the seats on the ballot and the
defending split, and ships them in `window.kycBuildMeta`. The sidebars read
them at runtime.

On a state's own pages, its state page and its district map, the sidebar also
shows that state's delegation by party, in the same colours: Senate, then
House. A seat with no sitting member is counted as vacant. The roster has no
row for it, so the vacancy is counted from the races, which cover every seat.
The national House line counts the same vacancies, so it adds up to 435
rather than reading 433 as a full chamber.

They used to be literal text in both pages — `53 R | 47 D/I`, `35`, `435` —
with a copy-pasted counting function per page and nothing tying either to the
rosters they described.

## Charts

Every chart draws a figure the build already counts, as boxes and page text
(never SVG text, rule 46), coloured from the theme's tokens: a party's colour
only for a person's or a seat's party (a holder, a candidate in the markets and
polls), `--cat-*` for kinds that are not parties, and one
neutral ink for judges, races and navigation (audit 2026-10-17).

| Chart | Where | From |
|---|---|---|
| Balance of power: each chamber as one bar, Republicans from the left and Democrats from the right, the Senate seats on the 2026 ballot dotted in their holder's colour (not hatched: the map under it hatches "no race", "none" and a split), a tick at half | every sidebar; above the map in its views of Congress, in its one-line form, which prints the counts below the laptop layout | `kycBuildMeta.senate` / `.house`; `senate.up` (seated senators in a 2026 race's seat, by state and class; sent only while the cycle is a campaign) |
| The House, one square per voting seat, each state a button | the map's House view, "One square per seat" (`#/?mode=house&layout=tiles`) | `kycBuildMeta.houseTiles`, laid out by `kyc/tiles.py` from the district maps' label points: north to south, then west to east, within each state's block; `cells2026` for a redrawn state, used once the Congress the 2026 election chose sits |
| A state's House races as squares laid out as the districts lie | a state page's 2026 races, with four or more districts | `houseTiles` (the 2026 plan) and `kycRaces` |
| The states as a map-like grid of links, a dot where a Senate seat is on the 2026 ballot | States & territories | `kycBuildMeta.stateGrid` (`tiles.STATE_GRID`) |
| A state's government at a glance: governor, whether the governor is running in the section's own words (rule 79), each chamber's seats, the high court's size and selection (no party) | a state page's State government | `data/stategov.js` |
| Funding sources as one bar | the profile's campaign finance | `fundingBreakdown`, of `fundingBase` or the receipts |
| Polling averages as dots on one axis of at least thirty points, a row per aggregator, in the market bars' candidate order (the compact panel prints the line only) | every race's markets block | `data/odds.js` |
| The federal courts as a ladder, a judge senior by the courts' list but not yet the directory said on every count holding one (rule 82) | Federal government, the federal courts | `data/federal.js` |
| A court's active bench by year commissioned, a row per appointing President, the axis ending at the latest commission | each federal court's page | `data/judiciary/<court>.js` |
| Local governments by kind, a Census "X" said as "None" under the bar (rule 49) | Counties & local governments | `census_governments.json` (`pages.local_bar`) |

## Validation

`build --check` reports data-quality findings. Errors are structural: wrong
chamber size, duplicate districts, a duplicate profile id, a race naming a
profile that does not exist, a state with members but no shape on the map, a
2026 Senate seat matching no incumbent, **somebody serving in Congress who is
absent from the roster**, and **a roster field that contradicts the
authoritative membership**.

`verify` is the separate question of whether the *committed* output still
matches the sources. Both generated files carry a sha256 of their content with
the build timestamp excluded, and `verify` compares it against a rebuild:

```
[error] the committed site data is out of date:
  - candidate_profiles_site/data/people/meta.js is stale
       committed fb5d549512d1f75b...
       rebuilt   3c49b99d632c308b...

Run `python build_profile_site.py` and commit the result.
```

CI used to answer this by rebuilding and running `git diff --exit-code`, which
conflated the two questions. A rebuild always stamps a fresh timestamp, so the
only way to keep that diff quiet was to commit the fixed `SOURCE_DATE_EPOCH`
date — and the page footer prints exactly that value to readers as the site's
freshness stamp. Passing CI would have meant telling every visitor the data
was built in 2001.

Warnings are advisory, including **stale curation** — overrides that no longer
match any profile. That check is what caught a retirement note keyed to
`"Dick Durbin"` while the roster says `"Richard Durbin"`, which meant his
retirement never showed on the site.

Current warnings, all expected:

- 433 of 435 voting House seats — real mid-term vacancies.
- 9 placeholder rows standing in for unresolved primaries.
- 3 stale exclusions — members already removed from the cleaned rosters.
- 5 dual-role members: sitting House members running for Senate.

## Automation

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | push, PR | Tests, validation, `verify`, reproducibility, no-CDN and no-inline-handler checks |
| `refresh.yml` | Mondays and Thursdays 07:20 UTC (Thursdays only until election day), manual | Reconciles against congress-legislators, refreshes the field, results, money, disclosures and filled gaps, checks every campaign site, and **opens a PR** if anything changed |
| `refresh-waiting.yml` | Daily 14:40 UTC, manual | Opens a "Refresh waiting for review" issue once a refresh PR is a day old, comments each day it still waits, closes it when none is |
| `odds.yml` | Every twelve hours (00:47 and 12:47 UTC), manual; stops at the first poll closing on Election Day | Refreshes market prices and polling averages, validates, **commits only the two odds files to main** and starts the deploy. From 23:00 UTC on Nov 3 it changes nothing, and the page labels the last prices final |
| `deploy.yml` | manual only | Publishes to GitHub Pages |

`refresh.yml` never pushes to main directly. It resolves portraits for
anyone new, rebuilds, runs validation and the tests, and opens a pull request.
Once the pull request's CI passes, it merges it and starts the deploy (since
2026-10-14: after the election the results reach the page only this way, and a
pull request that waited for a person kept the site eight days behind). A
pull request whose checks fail stays open and opens the failure issue. It then starts CI on that pull request itself, because a pull request
opened with the workflow's own token is held at "action_required", and it
closes older refresh pull requests as superseded. In October 2026 two sat
unreviewed for days while the site served data eight days old, so
`refresh-waiting.yml` now tells a person when one is waiting.

## Publishing

The site is served by GitHub Pages at **<https://candidates.radicalrelay.us>**.

`.github/workflows/deploy.yml` publishes `candidate_profiles_site/` on every
push to `main` that touches the site, and on demand. It refuses to publish if
`build --check --strict` reports an error or if `verify` finds the committed
data out of step with the CSVs, so a broken build cannot reach readers.

### The hostname lives in one place

`candidate_profiles_site/CNAME` is what GitHub Pages actually serves from.
Five other spots repeat it — the canonical link and `og:url` on both pages,
the `Sitemap:` line in `robots.txt`, and `<loc>` in `sitemap.xml` — and
`verify` fails if any of them disagree:

```
[error] the committed site is not self-consistent:
  - candidate_profiles_site/robots.txt: names kyc.radicalrelay.us;
    CNAME says candidates.radicalrelay.us
```

Nothing about a half-finished rename looks wrong locally; the site would just
quietly tell search engines and social networks it lives somewhere it does not.

### DNS

One record, on Cloudflare, where `radicalrelay.us` is hosted:

| Type | Name | Content | Proxy |
|---|---|---|---|
| `CNAME` | `candidates` | `pkplaya626.github.io` | **DNS only** (grey cloud) |

It must be **DNS only**. Proxying it puts Cloudflare's certificate in front of
GitHub's and blocks Pages from provisioning its own, which breaks HTTPS.

This does not touch `subscribe.radicalrelay.us`, which is a separate Cloudflare
Worker custom domain serving the Morning Digest newsletter, nor the apex, which
has no record at all.

### Social preview

`assets/social-card.png` is the `og:image`, generated from
`tools/social-card.html` with headless Chrome (the command is in that file).
It deliberately carries no figures: the card cannot be regenerated on every
data refresh, so any number on it would eventually be wrong — the same reason
the sidebar counts moved into the build metadata.

## Known gaps

- **Campaign finance is only as complete as your FEC key allows.** With
  `DEMO_KEY` you get a handful of profiles.
- **Primary results depend on Wikipedia's state pages.** They are the only
  free, structured, current source; the resolver reads only the results
  tables and infobox and treats an unmarked table as undecided. Pages for the
  District of Columbia and the Virgin Islands delegate races do not exist, so
  those two races are never settled. The FEC field also lacks a handful of
  incumbents who have not amended their statement of candidacy for 2026;
  those members are matched through their roster name instead.
- **Caucus membership is not in the data.** Both independent senators caucus
  with the Democrats, which is why "53 R / 47 D/I" is the usual way to report
  the chamber. The rosters do not record it, so the site reports `53 R / 45 D /
  2 I` and leaves the arithmetic to the reader rather than asserting something
  it cannot source.
- **Campaign websites are what the treasurer filed, checked weekly.** The
  FEC's committee register holds a site for 856 of the 1,035 people on a
  ballot; the rest filed none, and nothing is guessed for them beyond the race
  page's own list. Off-ballot filers are not looked up. `enrich` reads every
  linked site each week, but a domain can lapse between two Mondays.
- **Most challengers still have no portrait, education or age.** About two in
  three on the November ballot have no headshot that their own campaign or a
  linked article names as theirs, and a guess is worse than a silhouette
  (rule 24). Issue lists and descriptions are the campaigns' own words and as
  current as their sites.
- **Two senators have no financial-disclosure link.** Both were appointed in
  2026 and have not filed an annual report yet.
- **Market prices are up to twelve hours old.** Every block says the date
  it was read. Polling averages appear only for the Senate races whose
  Wikipedia page lists them, and for no House race.
  Kalshi's site turns away automated requests, so its links - to each
  market's series page - were not checked by a script.

## Licence

The code is under the MIT licence (`LICENSE`). The data this project
compiles - the roster CSVs, the caches and generated files under
`candidate_profiles_site/data/`, and the guide's prose - is under CC BY 4.0
(`LICENSE-DATA.md`), credited as "Know Your Candidate
(https://github.com/pkplaya626/Know-Your-Candidate), CC BY 4.0".
Photographs and other sources' material keep their own terms;
`LICENSE-DATA.md` lists them.
