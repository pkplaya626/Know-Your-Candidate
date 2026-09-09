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
| `python build_profile_site.py` | Build `data/profiles.js` and `data/geo.js` |
| `… build --check` | Validate only; write nothing |
| `… build --strict` | Refuse to write if validation finds an error |
| `… build --json` | Emit the validation report as JSON |
| `… verify` | Check the committed data still matches the sources |
| `… congress` | Refresh the membership snapshot and report roster drift |
| `… congress --check` | Report drift from the committed snapshot; no network |
| `… congress --apply` | Add newly seated members to the roster CSVs |
| `… field` | Refresh the FEC register of everyone running in 2026 |
| `… field --check` | Report the field from the committed cache; no network |
| `… disclosures` | Link House members to their filed financial disclosures |
| `… geo` | Regenerate only the map geometry |
| `… fetch` | Refresh DW-NOMINATE scores from Voteview into the roster CSVs |
| `… portraits` | Resolve and check a portrait URL for every profile |
| `… portraits --refresh` | Re-resolve every portrait, not just the missing ones |
| `… finance --limit N` | Look up FEC campaign finance totals (needs `FEC_API_KEY`) |
| `… refresh` | `fetch`, then `build` |
| `python -m unittest discover tests` | 195 pipeline tests |
| `npm install && npm test` | Render both pages in jsdom and drive the UI (133 checks) |

`--root` and `--verbose` work on either side of the subcommand, so both
`--verbose portraits` and `portraits --verbose` do the same thing.

Only `fetch`, `portraits`, `finance` and `congress` touch the network. `build`
and `verify` are fully offline and read the committed caches and snapshot.

## How the data flows

```text
Cleaned_House_119th.csv                  ─┐
Cleaned_Senate_119th.csv                 ─┤
Congressional_Candidates_2026.csv        ─┼─> kyc/ ─> data/profiles.js ─┬─> index.html
Completed_Primary_Candidates_2026.csv    ─┤          data/geo.js       ─┤   (grid + races)
Late_Primary_Candidates_2026.csv         ─┘          portraits.json     └─> map.html
us_atlas_states_topo.json                ──> kyc/geo.py                     (partisan map)
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
| `disclosures.py` | Links to House members' filed financial disclosures |
| `geo.py` | Decode the state atlas into SVG path data |
| `summary.py` | Chamber balance and election headline figures |
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
| `assets/kyc-directory.js` | The grid: filtering, sorting, races |
| `assets/kyc-map.js` | The map: rendering, modes, delegation panel |

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
- The sidebar becomes an off-canvas drawer under 1000px.

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

### What these profiles do and do not contain

Name, party, seat, receipts, disbursements and cash on hand, all from the FEC
with a coverage date. Education, platform, committees and net worth are
editorial research that no dataset supplies, so they stay empty and the
provenance layer reports them as *No data*.

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

## Portraits

Portraits are resolved **at build time** and cached in
`candidate_profiles_site/data/portraits.json`, which is committed and
hand-editable. Coverage is **571/594 (96%)**; of the 23 without one, 9 are
placeholder rows for unresolved primaries, so 14 real people lack a portrait
because no public source has one.

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
annual ZIP containing an XML index of every disclosure, and **396 of 439 House
members** now carry a link to their own annual report (PDF) beside the
net-worth field.

Senators have none. The Senate's equivalent sits behind a session-based search
that must be agreed to before it returns anything; scraping it would be fragile
and against the spirit of that gate.

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

## Election flags and races

Derived in `kyc/profiles.py` and `kyc/races.py`, shipped in the data.

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

`window.kycRaces` holds **474 seats** on the 2026 ballot: 35 Senate, 6
territory delegates and 433 voting House seats. Every one of the 435 House
seats is on the ballot, but a seat nobody currently holds has no roster row and
therefore produces no race, so the shortfall is exactly the vacancies. The 65
senators whose terms run past 2026 belong to no race.

The **Group by race** toggle on the grid groups an incumbent with everyone
challenging them.

## Headline figures

`kyc/summary.py` counts the chamber balance, the seats on the ballot and the
defending split, and ships them in `window.kycBuildMeta`. The sidebars read
them at runtime.

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
| `refresh.yml` | Mondays 07:20 UTC, manual | Reconciles against congress-legislators and **opens a PR** if Congress has changed |
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
- **No state primary dates.** The countdown covers the general election, which
  is computed (first Tuesday after the first Monday in November). Per-state
  primary dates are not in the data and are deliberately not invented.
- **Caucus membership is not in the data.** Both independent senators caucus
  with the Democrats, which is why "53 R / 47 D/I" is the usual way to report
  the chamber. The rosters do not record it, so the site reports `53 R / 45 D /
  2 I` and leaves the arithmetic to the reader rather than asserting something
  it cannot source.
- **No social preview image.** `og:image` needs a raster asset and an absolute
  URL, so it waits on a canonical domain.
