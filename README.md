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
| `python build_profile_site.py` | Build `data/profiles.js`, `data/geo.js` and `data/districts/*.js` |
| `… build --check` | Validate only; write nothing |
| `… build --strict` | Refuse to write if validation finds an error |
| `… build --json` | Emit the validation report as JSON |
| `… verify` | Check the committed data still matches the sources |
| `… congress` | Refresh the membership snapshot (with contact details, accounts and committee rosters) and report roster drift |
| `… congress --check` | Report drift from the committed snapshot; no network |
| `… congress --apply` | Add newly seated members to the roster CSVs |
| `… field` | Refresh the FEC register of everyone running in 2026 |
| `… field --check` | Report the field from the committed cache; no network |
| `… census` | Count each state's local governments from the Census of Governments (`--check` reads the cache) |
| `… statelegs` | Every state legislator from Open States, matched to the district maps (`--check` re-matches the cache) |
| `… localgov` | Every local government from the Census listing, checked against the published counts |
| `… executives` | Every governor from the NGA, and NCSL's count of each legislature's parties (`--check` reports the caches) |
| `… officers` | Every lieutenant governor (NLGA) and secretary of state (NASS), cross-checked where the rosters overlap |
| `… courts` | Each state's highest court and its members, read from the court's own roster |
| `… disclosures` | Link members to their filed financial disclosures (House Clerk, Senate eFD) |
| `… results` | Read each state's primary results from Wikipedia: who is still in |
| `… results --check` | Report the results from the committed cache; no network |
| `… campaigns` | Look up campaign websites from each candidate's FEC committee (needs `FEC_API_KEY`) |
| `… campaigns --check` | Report campaign-site coverage from the committed cache; no network |
| `… enrich` | Fill gaps for everyone still running from their Wikipedia infobox and campaign site, and check every linked campaign site |
| `… enrich --check` | Report what the committed cache fills; no network |
| `… enrich --refresh` | Read everyone again, not only those read more than six days ago |
| `… odds` | Kalshi and Polymarket prices for each 2026 race and for control of both chambers, and the polling averages each Senate race's Wikipedia page lists; writes `data/odds.json` and `data/odds.js` |
| `… odds --check` | Report market and polling coverage from the committed cache; no network |
| `… geo` | Regenerate only the map geometry: the national map and the before-and-after district maps |
| `… fetch` | Refresh DW-NOMINATE scores from Voteview into the roster CSVs |
| `… portraits` | Resolve and check a portrait URL for every profile |
| `… portraits --refresh` | Re-resolve every portrait, not just the missing ones |
| `… finance --limit N` | Look up FEC campaign finance totals (needs `FEC_API_KEY`) |
| `… refresh` | `fetch`, then `build` |
| `python tools/fetch_district_maps.py` | Rebuild `district_maps/`: every state's district boundaries, the new 2026 maps, and the towns to label (network) |
| `python tools/fetch_local_maps.py` | Rebuild `local_maps/`: every incorporated place, one point each, for the county pages (network) |
| `python -m unittest discover tests` | The pipeline tests |
| `npm install && npm test` | Render every page in jsdom and drive the UI (1059 checks) |

`--root` and `--verbose` work on either side of the subcommand, so both
`--verbose portraits` and `portraits --verbose` do the same thing.

Only `fetch`, `portraits`, `finance`, `field`, `disclosures`, `results`,
`campaigns`, `enrich`, `odds` and `congress` touch the network. `build` and
`verify` are fully offline and read the committed caches and snapshot.

## How the data flows

```text
Cleaned_House_119th.csv                  ─┐
Cleaned_Senate_119th.csv                 ─┤
Congressional_Candidates_2026.csv        ─┼─> kyc/ ─> data/profiles.js ─┬─> index.html
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
`profiles.js` or `geo.js` by hand. They are committed so the site serves
straight from GitHub Pages with no build step.

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
| `voteview.py` | DW-NOMINATE ideology scores |
| `profiles.py` | Assemble profiles; derive 2026 election flags and field provenance |
| `races.py` | Group profiles into the seats they contest |
| `legislators.py` | The authoritative membership, and reconciliation against it |
| `candidates.py` | The FEC's register of who is running in 2026 |
| `disclosures.py` | Links to members' filed financial disclosures (House Clerk, Senate eFD) |
| `geo.py` | Decode the state atlas into SVG path data |
| `summary.py` | Chamber balance, election headline figures, per-state figures |
| `pages.py` | The shared page template, the state pages, the states directory and the sitemap |
| `government.py` | The guide to how government works: renders its pages and refuses a broken link or an uncited section |
| `government_text.py` | The guide's words and the sources each section was checked against |
| `government_maps.py` | What the guide's maps say about each state, every value with its source |
| `census.py` | The Census of Governments' counts of local governments by state (the `census` command) |
| `statelegs.py` | Every state legislator, from Open States, matched to a Census district (the `statelegs` command) |
| `legislature.py` | Each state's legislature page data: projected districts, close-ups and the members in each |
| `localgov.py` | Every local government, county by county, from the Census listing (the `localgov` command) |
| `counties.py` | Each state's counties page data: projected counties, the governments in each, and every incorporated place joined to its government |
| `executives.py` | Every governor, from the National Governors Association's roster (the `executives` command) |
| `officers.py` | Lieutenant governors and secretaries of state, from their associations' rosters (the `officers` command) |
| `courts.py` | Each state's court of last resort and its members, from each court's own page (the `courts` command) |
| `stategov.py` | Who runs each state: governor, chamber control, trifecta, checked against NCSL |
| `campaigns.py` | Campaign websites from each candidate's FEC committee |
| `enrich.py` | Fill filed candidates' gaps from their Wikipedia infobox and campaign site; check every linked campaign site |
| `odds.py` | Prediction-market prices (Kalshi, Polymarket) and published polling averages for the 2026 Senate races |
| `validate.py` | Data-quality checks |
| `emit.py` | Write the data files atomically; verify the pages are wired up |
| `cli.py` | Argument parsing and command wiring |

## The front end

`index.html` and `map.html` are hand-maintained templates. The build only
writes into `data/`; it never rewrites the HTML. It does check that each page
loads the scripts it needs, **in the right order** — every generated file
assigns a global that the page modules read as they initialise, so the wrong
order renders an empty site with no error anywhere.

| File | Responsibility |
|---|---|
| `assets/kyc.css` | The entire stylesheet: tokens, three themes, every component |
| `assets/kyc.js` | Theme, icon sprite, escaping, provenance, router, dialog helper, shell |
| `assets/kyc-profile.js` | The profile dialog, shared by both pages |
| `assets/kyc-cards.js` | Profile cards and race sections, shared by the grid and the state pages |
| `assets/kyc-senate.js` | The grid's Senate view: every seat by the year it is next decided, with the candidates for each 2026 seat |
| `assets/kyc-directory.js` | The grid: filtering, sorting, races |
| `assets/kyc-map.js` | The map: rendering, modes, delegation panel |
| `assets/kyc-state.js` | A state's page, and the directory of states |
| `assets/kyc-usmap.js` | The map of the states, drawn once for the partisan map and the guide's maps |
| `assets/kyc-guide.js` | The guide's pages: their maps, and what they show from the data (who leads each committee) |
| `assets/kyc-regionmap.js` | A map of any regions inside a state (legislative districts, counties), with labels, close-ups and an optional layer of dots |
| `assets/kyc-legislature.js` | A state's legislature page: chambers, districts, members |
| `assets/kyc-local.js` | A state's counties page: every county and every local government in it, and every city and town |
| `assets/kyc-stategov.js` | Governors, legislatures and trifectas: the map's three state views and every state page's section |

Every view has a URL: `#/profile/<id>` for a person,
`#/?state=TX&chamber=Senate` for a filtered list, so any view can be linked and
shared.

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

- `/` focuses the search box from anywhere on any page; Escape hands focus
  back.
- The grid renders a screenful of cards and appends the rest as you scroll
  (a **Show more** button does the same without the observer), so the first
  paint no longer waits on 2,500 image elements. The result count is always
  the full figure.
- The state filter lists states by name, and a filtered state is one click
  from its own page. Race headers, the profile dialog and the map panel link
  to the state page too; a state page has a jump row for its districts.
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
python build_profile_site.py congress --apply  # write newly seated members in
```

`--apply` fills only the columns the dataset actually knows. Education, net
worth, committees and platform are editorial research that no dataset
supplies, so they stay empty and the provenance layer reports them as *No
data* — which is true, and better than a plausible invention. Departed members
are never removed automatically: a roster row may carry curated work, and
taking someone out of Congress is a judgement that belongs in
`overrides.EXCLUDED_MEMBERS` where it is visible.

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
with a coverage date. Committees and net worth are editorial research that no
dataset supplies, so they stay empty and the provenance layer reports them as
*No data*. For anyone still in a race, background, education, age, what the
campaign says it stands for and a portrait are filled where the person's own
sources say so - see [Filling the gaps](#filling-the-gaps) - each credited to
its source.

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
| `photoSource` | Where the first entry came from: `clerk.house.gov`, `congress.gov`, `wikipedia`, `wikipedia-search`, `cross-link` or `campaign-site` |
| `photoSet` | `[[width, url], ...]`, smallest first: sizes of the first entry's photograph for the page's `srcset`. Wikimedia portraits only |

Set `"pinned": true` on a cache entry to stop the resolver overwriting a
hand-corrected URL.

Two rules are load-bearing here, both learned the hard way:

- **Never discard on an inconclusive check.** Wikipedia returns HTTP 429 freely
  during a full run. Treating "could not tell" as "broken" silently threw away
  about 160 working portraits.
- **Never search with a topical hint.** Searching `Dan Osborn NE politician`
  pushes his own article out of the top results; `Dan Osborn` returns it first.

The fallback chain used to link the unitedstates project's images at
`theunitedstates.io`. That domain lapsed: on 2026-10-03 it resolved to a
domain-parking network, so every member's chain pointed twice at a host anyone
could buy. The chain now uses the project's GitHub Pages copy, as a last
resort, because it is often an older photograph.

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

The site shows an "Estimated Net Worth" for 144 of 539 sitting members and
nothing for the rest, and the figures it does show carry no source.

**This is not filled in, deliberately.** No free service publishes a computed
net worth for members of Congress, and deriving one from a disclosure is not a
small step: the forms report assets in broad value *bands*, so any single
figure from them is an estimate dressed as a fact — the exact thing the
provenance layer exists to prevent.

What is available is the filing itself. The Clerk of the House publishes an
annual ZIP containing an XML index of every disclosure, and **401 of 439 House
members** carry a link to their own annual report (PDF) beside the net-worth
field.

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
| `N/A (No net worth disclosure provided…)` | no filing exists | *Not disclosed* (muted) |
| `""` | nobody has researched it | *No data* (muted) |
| `Individual/PAC contributions` | true of everyone; no information | dotted underline, marked generic |
| — | the FEC was queried and holds no filing for this cycle | *No filing this cycle* (muted) |

That last row is the only absence that reports work actually done. "No data"
is a claim about us: it says nobody looked. Once the pipeline queries the FEC
for all 596 profiles, using the same label for "we never checked" and "we
checked and there is no filing" discards the more informative of the two — and
17 of them are sitting members running for a *different* seat, whose money is
in another committee entirely. Showing their last cycle's figures instead
would be worse than either: a member's 2024 receipts on a page about the 2026
midterms reads as current money.

`profiles.js` carries a `quality` map per profile listing only the fields that
are *not* real data. About **11% of surfaced fields** fall into one of those
categories — that is the honest picture, and the page shows it as such. Absent
values are excluded from search, so "not disclosed" does not match everyone.

A field the pipeline filled from a named source rather than a roster records
that source in `fieldSources` - `wikipedia` (an article's infobox),
`election-page` (the race page's description) or `campaign-site` (the
campaign's own issues page) - and the page shows it as a badge beside the
value, with a tooltip saying exactly where it came from. See
[Filling the gaps](#filling-the-gaps).

## Election flags and races

Derived in `kyc/profiles.py` and `kyc/races.py`, shipped in the data.

| Field | Meaning |
|---|---|
| `isCandidate` | A 2026 challenger, not a sitting member |
| `seatUp2026` | This seat is on the 2026 ballot |
| `seekingReelection2026` | Seat is up **and** the incumbent is on the ballot for it |
| `raceId` | For a member, the seat they hold; for a challenger, the seat they filed for |
| `contestRaceId` / `contestLabel` | A member contesting a *different* seat: a redrawn district, the other chamber |
| `alsoRunningId` / `incumbentId` | Cross-link between a member and a separate profile for their own candidacy |
| `raceStatus` / `raceStatusRace` | `nominee`, `advanced`, `eliminated`, `withdrawn` or `unlisted`, and the race it refers to |
| `ballotParty` / `fecParty` | The party the ballot lists, when it differs from the roster or FEC record |
| `ballotLine` | For a nominee only: the November ballot line as the results page spells it ("Speak The Truth", "Party for Socialism and Liberation"), when it is not the line of the party shown. Never set for "none", a write-in or a line named after the candidate themselves (an independent petition reads as "Independent"); `party` is never overwritten by it |
| `senateClass` | Sitting senators only: the constitutional class of the seat (1, 2 or 3), from the term record in `congress_snapshot.json`, keyed on bioguide id. `null` only when the build has no snapshot, which validation reports |
| `nextElection` | Sitting senators only: the year the seat is next on the November ballot, from the real term end date - a term ending 3 January is decided the November before; an appointee's term ending on election day is decided that year. Class II -> 2026, Class III -> 2028, Class I -> 2030, except a special |
| `senateSpecial` | Sitting senators only: `true` when `nextElection` comes before the class's regular cycle - a special election for the rest of the term (Ohio and Florida's Class III seats in 2026) |
| `rosterSeat` | For a curated challenger, the seat the roster gave them when the FEC filing says otherwise |

## State pages

Every state and territory has its own page - `states/tx.html`, and
`states/index.html` listing all fifty-seven - written by the build from one
template in `kyc/pages.py`. A page opens with the state's headline figures,
then who holds its seats (senators first, then the House by district), then
every 2026 race in ballot order with the sitting member, everyone on the
November ballot, and the people the primary removed folded under each race.
The same profile dialog opens from every card.

The pages carry nothing but the state code; `assets/kyc-state.js` renders
them from the same `profiles.js` the grid and map load, so a state page can
never disagree with the grid about who represents a district. They are
generated, so `verify` regenerates them in memory and fails when a page on
disk is not what the template would write.

They are linked from everywhere a state is named: the race headers in the
grid, the profile dialog's "Represents" line, the state filter in the sidebar,
the map's delegation panel, the footer, and `sitemap.xml`.

## How government works

`government/` is a guide to the offices around the people this site covers:
Congress, the executive and the federal courts, state governments, local
governments and tribal nations. Its seven pages are generated, like the state
pages, from the shared template in `kyc/pages.py`, with their words in
`kyc/government_text.py`.

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
- **Only the page that shows people loads them.** The Congress page loads
  `profiles.js` like a state page; the others load only `kyc.js` and
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
| State governments | Legislature (chambers and seats), who presides over the senate, line-item veto, how high-court justices are chosen | NCSL; Book of the States 2022, tables 4.14, 5.1 and 5.6, checked for changes through October 2026 |
| Federal courts | The circuit each state's appeals go to, numbered on the map | 28 U.S.C. 41; 48 U.S.C. 1824 |
| Local governments | Counts of every kind of local government, and of counties, municipalities, townships, school districts and special districts | Census of Governments 2022, table CG2200ORG02 (`census` command) |
| Tribal nations | Public Law 280: the six states the law names and the ten that took jurisdiction later | 18 U.S.C. 1162; BIA |

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

Ten states' courts cannot be read by a script (`courts.UNREADABLE`):
Alabama's site resets every connection; Louisiana's draws its justices with
JavaScript; Massachusetts', Missouri's, New Hampshire's and Tennessee's
answer with a bot wall or challenge; Connecticut's, Nevada's and New York's
refuse this pipeline's requests; Rhode Island's publishes only a PDF. Their
pages name the court and say why its members are not listed, and nothing is
taken from Wikipedia or Ballotpedia instead.

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

What the listing does not hold is who serves: it names the title of a
contact official, not the person. No free, authoritative national source
lists local officials, so the page says what each government is and links
its own site rather than guessing who runs it.

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
shared, only by the county the place's point lies in. 19,451 places join. The
rest are places incorporated since the 2022 listing (Mableton, Georgia;
Mountain House, California), consolidated governments the two sources name
differently (Baton Rouge's city-parish), and a handful of spellings that
disagree ("Cajah's Mountain"). They are drawn, say that no government is
joined, and are reported by the build; nothing is matched to its nearest name.

Towns and townships are joined the other way: the listing gives each the
Census code of its county subdivision, and the subdivision boundaries
(`cb_2025_<st>_cousub_500k`, vendored by the same tool for the twenty states
whose Census table counts town or township governments) carry the same
code. 16,167 of the 16,214 are placed on their own code, the name checked
against the boundary file's. The other 47 changed after 2022 - Wisconsin's
Town of Madison was dissolved, Rib Mountain became a village, two
Massachusetts towns took city charters - and stay listed under their county;
none is placed by its name. In Connecticut, Massachusetts and the rest of New
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
  captions naming who holds the seat or is running in it, from `profiles.js`.
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
from `profiles.js`.

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

## Contact and links

| Field | Source | Who has it |
|---|---|---|
| `website`, `phone`, `office`, `contactForm` | The member's current term record in `congress-legislators` | Sitting members |
| `social` (`twitter`, `facebook`, `instagram`, `youtube_id`, `bluesky`) | `legislators-social-media`, the project's verified account list | Sitting members |
| `refs` (`govtrack`, `opensecrets`, `votesmart`, `ballotpedia`) | Reference ids from `congress-legislators` | Sitting members |
| `wikipedia` | The bioguide mapping for members; the state ballot page's own link for filed candidates (`wikipediaVia`) | Members, and candidates the ballot page links |
| `aliases` | Other names a voter may search by, all from the member's own `congress-legislators` record (matched on bioguide id): `official_full` without its quoted nickname, nickname + surname (+ suffix), and the Wikipedia title without its disambiguator ("Jim Clyburn", "Hank Johnson"). Names that fold to the display name are dropped. Searched, never displayed as the name | Sitting members whose record adds a name |
| `rosterName` | The roster CSV's spelling, set only when it opens with a bare initial ("C. Franklin") and `name` was replaced by the name the record says they go by (nickname + surname, else a real middle name + surname). Keys the finance cache and stays searchable | Five sitting members |
| `campaignSite`, `campaignCommittee` | The principal campaign committee's Form 1 at the FEC (`data/campaigns.json`); for a challenger whose committee filed none, or filed one that failed the check, the race page's "Campaign websites" list (`campaignSiteVia: "election-page"`) once `enrich` has confirmed the site names them | Everyone on a ballot with an FEC id |
| `electionPageSite` | The site the race page lists, held back until `enrich` has read it; never shown directly | Filed candidates the race page lists one for |
| `campaignQuote` | The campaign home page's own description of itself, quoted (`enrich`) | Challengers still running whose site describes itself |
| `campaignIssuesUrl` | The page the campaign site links as its issues, platform or priorities | Challengers still running |
| `disclosureUrl`, `disclosureSource` | The member's latest annual financial disclosure: `house-clerk` (a PDF from the Clerk's annual index) or `senate-efd` (a report in the Senate's eFD system) | Members with a filing on record |
| `committeeList`, `committeesSource` | `committee-membership-current`, with rank and title (`data/committees.json`); a titled seat also carries `side` (`majority` or `minority`), because a title alone cannot say which - "Vice Chairman" leads the minority on Senate Ethics and Intelligence | Sitting members |
| `fecCandidateId` | Links the FEC's own candidate page | Everyone the FEC knows |
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
  - candidate_profiles_site/data/profiles.js is stale
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
| `odds.yml` | Every twelve hours (00:47 and 12:47 UTC), manual | Refreshes market prices and polling averages, validates, **commits only the two odds files to main** and starts the deploy |
| `deploy.yml` | manual only | Publishes to GitHub Pages |

`refresh.yml` never pushes to main and never deploys. It resolves portraits for
anyone new, rebuilds, runs validation and the tests, and opens a pull request
so a change in the membership of Congress is something a person reads and
merges.

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
