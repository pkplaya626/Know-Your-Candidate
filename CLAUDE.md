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
us_atlas_states_topo.json   ──┴─> kyc/ ──> candidate_profiles_site/
                                             data/profiles.js   (profiles, races, build meta)
                                             data/geo.js        (SVG path data for the map)
                                             ├──> index.html    (grid, races, profiles)
                                             └──> map.html      (partisan map)
                                             assets/kyc.css
                                             assets/kyc.js
                                             assets/kyc-profile.js
                                             assets/kyc-directory.js
                                             assets/kyc-map.js
```

- The root CSVs and the state atlas are the source of truth.
- Everything in `data/` is **generated**. Never edit `profiles.js` or `geo.js`
  by hand. `portraits.json` and `finance.json` are caches, but they *are*
  hand-editable.
- `index.html` / `map.html` are **hand-maintained templates**. The build reads
  them only to check they load the right scripts in the right order; it never
  rewrites them.
- Shared page behaviour belongs in `assets/`, not in a page. Neither page
  contains an inline `<script>` block.

## Commands

```bash
python build_profile_site.py               # build (offline)
python build_profile_site.py build --check # validate only
python build_profile_site.py geo           # regenerate map geometry only
python -m unittest discover tests          # 126 tests, no dependencies
npm install && npm test                    # 129 real-DOM checks (needs jsdom)
```

Only `fetch`, `portraits` and `finance` touch the network. Run the unit tests
and `build --check` after touching the pipeline; run `npm test` after touching
a page or anything in `assets/`.

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
  `tests/test_geo.py` for map geometry, `tests/test_site.py` for summary
  figures, emitted files and page wiring, `tests/render_test.js` for anything
  visible on a page.
- When changing profile fields, update the field tables in `README.md`.
- Builds must stay reproducible under `SOURCE_DATE_EPOCH`, for `geo.js` as
  well as `profiles.js`.
