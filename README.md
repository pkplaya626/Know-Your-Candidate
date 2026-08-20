# Know Your Candidate

A non-partisan, data-driven directory of the 119th U.S. Congress and the 2026
midterm races. Static site, no backend, no build toolchain — a Python pipeline
turns curated CSV rosters into JavaScript data files that two HTML pages read.

## Quick start

```bash
python build_profile_site.py            # rebuild the site data from the CSVs
open candidate_profiles_site/index.html # or just double-click it
```

No third-party dependencies. Python 3.9+ and the standard library.

## Commands

| Command | What it does |
|---|---|
| `python build_profile_site.py` | Build `candidate_profiles_site/data/profiles.js` |
| `… build --check` | Validate only; write nothing |
| `… build --strict` | Refuse to write if validation finds an error |
| `… fetch` | Refresh DW-NOMINATE scores from Voteview into the roster CSVs |
| `… portraits` | Resolve and check a portrait URL for every profile |
| `… portraits --refresh` | Re-resolve every portrait, not just the missing ones |
| `… finance --limit N` | Look up FEC campaign finance totals (needs `FEC_API_KEY`) |
| `… refresh` | `fetch`, then `build` |
| `python -m unittest discover tests` | 65 pipeline tests |
| `node tests/render_test.js index.html` | Render the page and exercise the UI (needs `npm install jsdom`) |

`--root` and `--verbose` go before the subcommand: `python build_profile_site.py --verbose portraits`.

The three enrichment commands (`fetch`, `portraits`, `finance`) are the only
ones that touch the network. `build` is fully offline and reads their caches.

## How the data flows

```
Cleaned_House_119th.csv                  ─┐
Cleaned_Senate_119th.csv                 ─┤
Congressional_Candidates_2026.csv        ─┼─> kyc/ ─> data/profiles.js  ─┬─> index.html
Completed_Primary_Candidates_2026.csv    ─┤           data/portraits.json │   (grid + races)
Late_Primary_Candidates_2026.csv         ─┘           data/finance.json   └─> map.html
```

The CSVs at the repo root are the source of truth. Everything under
`candidate_profiles_site/data/` is generated — never edit `profiles.js` by hand.
It is committed so the site serves straight from GitHub Pages with no build step.

Both pages load the data with `<script src>` rather than `fetch()`, so opening
the HTML directly off disk still works (`file://` blocks `fetch`, not `<script src>`).

Builds honour `SOURCE_DATE_EPOCH`, so output is byte-for-byte reproducible and
CI can assert that a rebuild changes nothing.

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
| `validate.py` | Data-quality checks |
| `emit.py` | Write the data files atomically; verify the pages are wired up |
| `cli.py` | Argument parsing and command wiring |

## Portraits

Portraits are resolved **at build time** and cached in
`candidate_profiles_site/data/portraits.json`, which is committed and
hand-editable. Coverage is currently **571/594 (96%)**; of the 23 without one,
9 are placeholder rows for unresolved primaries, so 14 real people lack a
portrait because no public source has one.

Resolution order: Congress.gov official portrait → Wikipedia via the
`congress-legislators` Bioguide↔title mapping → a bare Wikipedia title guess →
a Wikipedia search. A member and their own 2026 candidacy share a portrait.

Set `"pinned": true` on a cache entry to stop the resolver overwriting a
hand-corrected URL.

Two rules are load-bearing here, both learned the hard way:

- **Never discard on an inconclusive check.** Wikipedia returns HTTP 429 freely
  during a full run. Treating "could not tell" as "broken" silently threw away
  about 160 working portraits.
- **Never search with a topical hint.** Searching `Dan Osborn NE politician`
  pushes his own article out of the top results; `Dan Osborn` returns it first.

## Campaign finance

`finance` fills receipts, disbursements, cash on hand and a real funding
breakdown from the FEC, replacing the roster's generic
`"Individual/PAC contributions"` text. Figures carry the FEC coverage date.

Get a free key at <https://api.data.gov/signup/> and set `FEC_API_KEY`. Without
one the module falls back to `DEMO_KEY`, which the FEC throttles after a handful
of requests — enough to try it, not enough to fill 594 profiles. Results cache
per profile, so a throttled run stops cleanly and the next one resumes.

## Data provenance

The rosters carry three different things in one column, and the site used to
render all three identically:

| Value | Means | Now shows as |
|---|---|---|
| `$3,161,009` | a sourced figure | the figure, with a source badge where known |
| `N/A (No net worth disclosure provided…)` | no filing exists | *Not disclosed* (muted) |
| `""` | nobody has researched it | *No data* (muted) |
| `Individual/PAC contributions` | true of everyone; no information | dotted underline, marked generic |

`profiles.js` carries a `quality` map per profile listing only the fields that
are *not* real data. About **31% of surfaced fields** fall into one of those
categories — that is the honest picture, and the page now shows it as such.
Absent values are excluded from search, so "not disclosed" does not match
everyone.

## Election flags and races

Derived in `kyc/profiles.py` and `kyc/races.py`, shipped in the data. They used
to be computed in the browser, duplicated verbatim in both HTML files.

| Field | Meaning |
|---|---|
| `isCandidate` | A 2026 challenger, not a sitting member |
| `seatUp2026` | This seat is on the 2026 ballot |
| `seekingReelection2026` | Seat is up **and** the incumbent is running |
| `raceId` | The 2026 contest this profile is competing in |
| `alsoRunningId` / `incumbentId` | Cross-link between a member and their own candidacy |

All 435 House seats are two-year terms, so every House member has
`seatUp2026 = true`. Use `seekingReelection2026` to find who is actually
running. `isUpIn2026` remains as an alias of `seatUp2026`.

`window.kycRaces` holds **472 seats** on the 2026 ballot (435 voting House + 6
territory delegates + 35 Senate), of which 38 have a declared challenger in the
rosters and 13 are open seats. The 65 senators whose terms run past 2026 belong
to no race. The **By Race** toggle on the grid groups an incumbent with
everyone challenging them.

## The pages

`index.html` and `map.html` are hand-maintained templates. The build only
writes into `data/`; it never rewrites the HTML. Shared styling and behaviour
live in `assets/kyc.css` and `assets/kyc.js` — themes, the portrait fallback,
the accessible modal, the hash router, provenance rendering and the election
countdown. Keep the `<script src="assets/kyc.js">` and
`<script src="data/profiles.js">` tags; the build warns if a page drops them.

Every view has a URL: `#/profile/<id>` for a person, `#/?state=TX&chamber=Senate`
for a filtered list, so any view can be linked and shared.

Accessibility: skip link, labelled search, live region on the result count,
focus-visible outlines, and a modal with a focus trap, Escape handling and
focus restore. The sidebar becomes an off-canvas drawer under 900px.

## Validation

`build --check` reports data-quality findings. Errors are structural (wrong
chamber size, duplicate districts, a 2026 Senate seat matching no incumbent).
Warnings are advisory, including **stale curation** — overrides that no longer
match any profile. That check is what caught a retirement note keyed to
`"Dick Durbin"` while the roster says `"Richard Durbin"`, which meant his
retirement never showed on the site.

Current warnings, all expected:

- 431 of 435 voting House seats — real mid-term vacancies.
- 9 placeholder rows standing in for unresolved primaries.
- 3 stale exclusions — members already removed from the cleaned rosters.
- 5 dual-role members: sitting House members running for Senate.

## Known gaps

- **Campaign finance is only as complete as your FEC key allows.** With
  `DEMO_KEY` you get a handful of profiles.
- **No state primary dates.** The countdown covers the general election, which
  is computed (first Tuesday after the first Monday in November). Per-state
  primary dates are not in the data and are deliberately not invented.
- **Candidate coverage is thin** — 57 challengers across 472 seats. Most races
  show an incumbent with no declared opponent, which reflects the rosters
  rather than the field.
