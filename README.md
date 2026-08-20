# Know Your Candidate

A non-partisan, data-driven directory of the 119th U.S. Congress and the 2026
midterm races. Static site, no backend, no build toolchain — a Python pipeline
turns curated CSV rosters into one JavaScript data file that two HTML pages read.

## Quick start

```bash
python build_profile_site.py            # rebuild the site data from the CSVs
open candidate_profiles_site/index.html # or just double-click it
```

There are no third-party dependencies. Python 3.8+ and the standard library.

## Commands

| Command | What it does |
|---|---|
| `python build_profile_site.py` | Build `candidate_profiles_site/data/profiles.js` |
| `python build_profile_site.py build --check` | Validate only; write nothing |
| `python build_profile_site.py build --strict` | Refuse to write if validation finds an error |
| `python build_profile_site.py fetch` | Refresh DW-NOMINATE scores from Voteview into the roster CSVs |
| `python build_profile_site.py refresh` | `fetch`, then `build` |
| `python -m unittest discover tests` | Run the test suite |

Add `--verbose` to see every item behind a validation finding rather than the
first five. `fetch_voting_data.py` still works and is an alias for `fetch`.

## How the data flows

```
Cleaned_House_119th.csv      ─┐
Cleaned_Senate_119th.csv     ─┤
Congressional_Candidates_2026.csv        ├─> kyc/ ─> candidate_profiles_site/data/profiles.js
Completed_Primary_Candidates_2026.csv    ─┤                    │
Late_Primary_Candidates_2026.csv         ─┘                    ├─> index.html  (profile grid)
                                                               └─> map.html    (partisan map)
```

The CSVs at the repo root are the source of truth. `data/profiles.js` is
generated — never edit it by hand. It is committed so the site can be served
straight from GitHub Pages with no build step.

Both pages load the data with `<script src="data/profiles.js">` rather than
`fetch()`, so opening the HTML directly off disk still works (`file://` blocks
`fetch`, but not `<script src>`).

### Candidate roster precedence

`Congressional_Candidates_2026.csv` → `Completed_Primary_Candidates_2026.csv` →
`Late_Primary_Candidates_2026.csv`. Later files win, so a resolved primary
overrides the broad roster. Records are keyed on **(name, state, chamber)** —
keying on name alone merges different people who happen to share one.

## The `kyc` package

| Module | Responsibility |
|---|---|
| `sources.py` | Find and read the roster CSVs |
| `normalize.py` | Clean values; parse states, districts, ages, currency |
| `overrides.py` | Hand-curated corrections (photos, statuses, 2026 Senate seats) |
| `photos.py` | Build the portrait fallback chain |
| `profiles.py` | Assemble unified profiles; derive all 2026 election flags |
| `validate.py` | Data-quality checks |
| `emit.py` | Write `profiles.js` atomically; verify the pages are wired up |
| `voteview.py` | Download and apply DW-NOMINATE scores |
| `cli.py` | Argument parsing and command wiring |

## Election flags

Derived in `kyc/profiles.py` and shipped in the data. They used to be computed
in the browser, duplicated verbatim in both HTML files.

| Field | Meaning |
|---|---|
| `isCandidate` | A 2026 challenger, not a sitting member |
| `seatUp2026` | This seat is on the 2026 ballot |
| `seekingReelection2026` | Seat is up **and** the incumbent is running |
| `termEndYear` / `electionYear` | Derived term boundaries |
| `alsoRunningId` / `incumbentId` | Cross-link between a member and their own 2026 candidacy |

`isUpIn2026` is retained as an alias of `seatUp2026` for the existing page code.

All 435 House seats are two-year terms, so every House member has
`seatUp2026 = true`. Use `seekingReelection2026` to find who is actually
running — retiring members have the seat up but are not on the ballot.

### Portraits

Tried in order, falling back on load error to an inline silhouette:
Congress.gov → theunitedstates.io (450×550, then 225×275) → Bioguide Retro →
Wikipedia. Candidates have no Bioguide ID, so they start at Wikipedia.

Curated overrides in `overrides.CANDIDATE_PHOTOS` are keyed on
**(name, state)** and apply only to candidates. Rep. Mike Rogers (AL-3) and
2026 Senate candidate Mike Rogers (MI) are different people; a name-only key
put one man's portrait on the other's profile.

## Validation

`build --check` reports data-quality findings. Errors are structural
(wrong chamber size, duplicate districts, a 2026 Senate seat matching no
incumbent). Warnings are advisory — including **stale curation**: overrides
in `overrides.py` that no longer match any profile. That check is what caught
a retirement note keyed to `"Dick Durbin"` while the roster says
`"Richard Durbin"`, which meant his retirement never showed on the site.

Current known warnings, all expected:

- 431 of 435 voting House seats — real mid-term vacancies.
- 9 placeholder rows (`"Democratic Nominee"`, `"Republican Nominee"`) standing
  in for states whose primary has not resolved.
- 3 stale exclusions — members already removed from the cleaned rosters.
- 5 dual-role members, sitting House members running for Senate.

## Editing the site

`index.html` and `map.html` are hand-maintained templates. The build only
writes `data/profiles.js`; it never rewrites the HTML. Keep the
`<script src="data/profiles.js"></script>` tag — the build warns if a page
stops loading it.

To sanity-check a page change without a browser, `node --check` each inline
`<script>` block. A fuller render test using `jsdom` (exercising the filter
chips, sidebar counts, and modal cross-links) is straightforward to run if
you install `jsdom` locally; it is not a project dependency.
