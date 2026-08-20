"""Command-line entry point for the Know Your Candidate pipeline."""

import argparse
import sys

from . import emit, sources, validate, voteview
from .profiles import build_profiles


def _build(args):
    try:
        raw = sources.load_all(args.root)
    except sources.MissingRosterError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    for name, count in raw["found"]:
        print(f"  read {name} ({count} rows)")
    for name in raw["missing"]:
        print(f"  [warn] {name} not found - skipped")

    profiles, stats = build_profiles(raw)
    print(
        f"\n[+] {stats['total']} profiles "
        f"({stats['members']} sitting members, {stats['candidates']} candidates)"
    )
    print(
        f"    {stats['senate_seats_up']} Senate seats up in 2026 | "
        f"{stats['voting_house']} voting House seats | "
        f"{stats['not_seeking']} incumbents not seeking re-election | "
        f"{stats['cross_linked']} members cross-linked to their own candidacy"
    )

    issues = validate.run(profiles, raw)
    errors = [i for i in issues if i.level == "error"]
    if issues:
        print()
        print(validate.format_report(issues, verbose=args.verbose))

    if errors and args.strict:
        print("\n[error] --strict set and errors found; not writing output.", file=sys.stderr)
        return 1

    if args.check:
        print("\n[check] validation only, nothing written.")
        return 1 if errors else 0

    path, size = emit.write_profiles(profiles, stats, args.root)
    print(f"\n[ok] wrote {path} ({size / 1024:.0f} KB)")

    for page, ok, note in emit.check_pages(args.root):
        print(f"     {'ok  ' if ok else 'WARN'} {page}: {note}")

    return 0


def _fetch(args):
    print(f"Downloading DW-NOMINATE data from {voteview.VOTEVIEW_URL} ...")
    try:
        rows = voteview.fetch_members()
    except voteview.VoteviewError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2

    alignment = voteview.build_alignment_map(rows)
    print(f"  parsed {len(rows)} rows -> {len(alignment)} scored members")

    total_updated = 0
    for roster in sources.MEMBER_ROSTERS:
        path = f"{args.root}/{roster}"
        updated, count = voteview.apply_to_roster(path, alignment)
        total_updated += updated
        if count:
            print(f"  {roster}: updated {updated} of {count} rows")
        else:
            print(f"  [warn] {roster} not found - skipped")

    if total_updated == 0:
        print("\n[warn] No rows changed. Bioguide IDs may not match the Voteview data.")
    else:
        print(f"\n[ok] Updated {total_updated} rows. Run 'build' to regenerate the site data.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="build_profile_site.py",
        description="Build the Know Your Candidate site data from the roster CSVs.",
    )
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--verbose", action="store_true",
                        help="list every item in a validation finding")

    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser("build", help="generate candidate_profiles_site/data/profiles.js")
    build.add_argument("--check", action="store_true",
                       help="validate only; do not write output")
    build.add_argument("--strict", action="store_true",
                       help="refuse to write when validation reports an error")

    sub.add_parser("fetch", help="refresh DW-NOMINATE scores from Voteview")

    refresh = sub.add_parser("refresh", help="fetch, then build")
    refresh.add_argument("--check", action="store_true")
    refresh.add_argument("--strict", action="store_true")

    # Bare invocation keeps the historical behaviour: just build.
    args = parser.parse_args(argv)
    if args.command is None:
        args.command = "build"
        args.check = getattr(args, "check", False)
        args.strict = getattr(args, "strict", False)

    if args.command == "fetch":
        return _fetch(args)
    if args.command == "refresh":
        code = _fetch(args)
        if code:
            return code
        print()
    return _build(args)


if __name__ == "__main__":
    raise SystemExit(main())
