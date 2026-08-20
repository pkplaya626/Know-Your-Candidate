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

Static site, no backend, no bundler, **no third-party Python dependencies**.
Keep it that way; `pandas` was removed from the pipeline deliberately.

```
*.csv (repo root)  ──>  kyc/  ──>  candidate_profiles_site/data/profiles.js
                                          ├──> index.html
                                          └──> map.html
```

- The root CSVs are the source of truth.
- `candidate_profiles_site/data/profiles.js` is **generated**. Never edit it.
- `index.html` / `map.html` are **hand-maintained templates**. The build reads
  them only to check they still load the data file; it never rewrites them.

## Commands

```bash
python build_profile_site.py               # build
python build_profile_site.py build --check # validate only
python build_profile_site.py refresh       # fetch DW-NOMINATE, then build
python -m unittest discover tests          # 38 tests, no dependencies
```

Always run `build --check` and the test suite after touching the pipeline.

## Rules that exist because of real bugs

Each of these was a shipped defect. Do not undo them.

1. **Derive election flags in Python, not in the page.** `isCandidate`,
   `seatUp2026`, `seekingReelection2026`, `termEndYear`, `electionYear` and the
   2026 Senate seat table all live in `kyc/profiles.py` and `kyc/overrides.py`.
   They were previously duplicated byte-for-byte in both HTML files, which is
   two places to fix and two places to drift.

2. **All 435 House seats are up every cycle.** House terms are two years, so
   `seatUp2026` is true for every House member. It previously read true *only*
   for retiring members — exactly the people not on the ballot. Use
   `seekingReelection2026` to mean "the incumbent is actually running".

3. **Key people on (name, state), never on name alone.** Rep. Mike Rogers
   (AL-3) and 2026 Senate candidate Mike Rogers (MI) are different people. A
   name-keyed photo override put one man's face on the other's profile, and a
   name-keyed dedup silently deleted six candidate records.

4. **Normalise districts in the pipeline, not in template strings.** The
   member CSVs say `"District 3"` and the candidate CSVs say `"TX-32"`. Pages
   rendering these raw produced `House • AL-District 3` and `House • TX-TX-32`.
   `parse_district()` returns `(number, label)`; use those.

5. **Match longer state names first.** `"VIRGINIA" in "WEST VIRGINIA"` is true,
   so naive substring matching resolved West Virginia to `VA`. Also: only read
   bare two-letter codes from the *original* casing, or uppercased prose turns
   "in", "or" and "me" into Indiana, Oregon and Maine.

6. **A filed `$0` is not missing data.** `fmt_curr(0)` returns `"$0.00"`.
   Collapsing it to `"N/A"` conflates "raised nothing" with "no filing" — two
   different claims on a transparency site.

7. **Write output atomically.** `emit.py` writes to a temp file and renames.
   The previous in-place HTML surgery could truncate a 900 KB page to a single
   character if its end-marker search failed.

## Curated data

`kyc/overrides.py` holds every editorial judgement: photo overrides, status
corrections, excluded members, and the 35 Senate seats up in 2026. Keep the
CSVs authoritative wherever they are correct and keep this file small.

`validate.py` reports overrides that no longer match anything. Take those
warnings seriously — a stale override is invisible in the UI but quietly
wrong. That check found a retirement note keyed `"Dick Durbin"` when the
roster says `"Richard Durbin"`, so his retirement never displayed.

## Conventions

- Standard library only in `kyc/`.
- Normalisation helpers are total: they accept `None`, `"nan"`, `""` and
  always return something display-ready.
- Add a regression test in `tests/test_pipeline.py` for any data bug fixed.
- When changing profile fields, update the field table in `README.md`.
