"""Rebuild data/court_districts.json: which federal district court, and
which of its divisions, each county belongs to, as 28 U.S.C. 81-131 say.

Source: chapter 5 of title 28 as govinfo publishes the United States Code
(kyc.court_districts.SOURCE_URL). The statute's words are reduced to lists
- each district, its divisions, the counties, parishes and cities each
comprises, the places court is held, and any exception in its own words -
and nothing else is written. An amendment enacted after the edition govinfo
publishes is applied from kyc.court_districts.AMENDMENTS, each with its
Public Law; re-read every section's current text (Cornell LII lists each
section's amendments) before refreshing. The join to the Census Bureau's counties, and
the check that every county of a state with several districts is placed
exactly once, are the build's (kyc/court_districts.py): a read that leaves
any county unplaced is refused here too, and the committed file stands.

    python tools/fetch_court_districts.py            # read, check, write
    python tools/fetch_court_districts.py --check    # read and check only
"""

import argparse
import datetime
import os
import sys
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from kyc import court_districts  # noqa: E402

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 know-your-candidate/1.0")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="read and check; write nothing")
    args = parser.parse_args(argv)
    request = urllib.request.Request(court_districts.SOURCE_URL,
                                     headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        page = response.read().decode("utf-8", errors="replace")
    states = court_districts.parse(page)
    cache = {"source": court_districts.SOURCE_URL, "edition": "2024",
             "read": datetime.date.today().isoformat(), "states": states}
    placed, problems = court_districts.table(cache, ROOT)
    for problem in problems:
        print(f"  [error] {problem}")
    print(f"  {len(placed)} counties placed in {len(states)} states")
    if problems:
        print("[error] the read leaves counties unplaced; nothing written", file=sys.stderr)
        return 2
    if not args.check:
        print(f"[ok] wrote {court_districts.save_cache(cache, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
