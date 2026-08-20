#!/usr/bin/env python3
"""Build the Know Your Candidate site data.

Reads the roster CSVs at the repo root and writes
``candidate_profiles_site/data/profiles.js``, which both index.html and
map.html load.

    python build_profile_site.py                 # build
    python build_profile_site.py build --check   # validate only
    python build_profile_site.py fetch           # refresh DW-NOMINATE scores
    python build_profile_site.py refresh         # fetch, then build

The implementation lives in the :mod:`kyc` package.
"""

import sys

from kyc.cli import main

if __name__ == "__main__":
    sys.exit(main())
