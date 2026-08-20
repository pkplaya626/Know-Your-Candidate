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
Keep it that way; `pandas` was removed from the pipeline deliberately, and CI
fails if a `requirements.txt` appears.

```
*.csv (repo root)  ──>  kyc/  ──>  candidate_profiles_site/data/*.js|json
                                        ├──> index.html   (grid, races, profiles)
                                        └──> map.html     (partisan map)
                                   candidate_profiles_site/assets/kyc.{css,js}
```

- The root CSVs are the source of truth.
- Everything in `data/` is **generated**. Never edit `profiles.js` by hand.
  `portraits.json` and `finance.json` are caches, but they *are* hand-editable.
- `index.html` / `map.html` are **hand-maintained templates**. The build reads
  them only to check they still load the data; it never rewrites them.
- Shared page behaviour belongs in `assets/kyc.js`, not in a page.

## Commands

```bash
python build_profile_site.py               # build (offline)
python build_profile_site.py build --check # validate only
python -m unittest discover tests          # 65 tests, no dependencies
node tests/render_test.js index.html       # real DOM test (needs jsdom)
```

Only `fetch`, `portraits` and `finance` touch the network. Run the unit tests
and `build --check` after touching the pipeline; run the render test after
touching a page or `assets/kyc.js`.

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
   produced `House • AL-District 3` and `House • TX-TX-32`.

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
    `normalize.classify()`, and absences are excluded from search.

11. **Validate the field, not just its presence.** `"2026 Primary"` sat in a
    Birthdate column and passed a "contains four digits" check. Use
    `looks_like_date()`.

## Curated data

`kyc/overrides.py` holds every editorial judgement. Keep the CSVs authoritative
wherever they are correct and keep this file small.

`validate.py` reports overrides that no longer match anything. Take those
warnings seriously — a stale override is invisible in the UI but quietly wrong.
That check found a retirement note keyed `"Dick Durbin"` when the roster says
`"Richard Durbin"`, so his retirement never displayed.

## Front-end conventions

- Shared CSS/JS in `assets/`; nothing duplicated between the two pages.
- Colours come from CSS custom properties (`--party-d`, `--money-in`, …), not
  hex literals, so all three themes stay consistent.
- Anything user-visible from the data goes through `KYC.renderField` (which
  escapes HTML and renders provenance) or `KYC.escapeHtml`.
- Every view needs a URL. Use `KYC.router`.
- New dialogs use `KYC.createModal` so they get the focus trap for free.

## Conventions

- Standard library only in `kyc/`.
- Normalisation helpers are total: they accept `None`, `"nan"`, `""` and always
  return something display-ready.
- Add a regression test for any data bug fixed — `tests/test_pipeline.py` for
  core parsing, `tests/test_enrichment.py` for provenance/portraits/FEC/races.
- When changing profile fields, update the field tables in `README.md`.
- Builds must stay reproducible under `SOURCE_DATE_EPOCH`.
