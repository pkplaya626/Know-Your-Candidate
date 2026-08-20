#!/usr/bin/env python3
"""Refresh DW-NOMINATE voting alignment from Voteview.

Downloads the public roll-call dataset and writes an alignment string into the
member roster CSVs. Equivalent to ``python build_profile_site.py fetch``.

The implementation lives in :mod:`kyc.voteview`; this script no longer requires
pandas.
"""

import sys

from kyc.cli import main

if __name__ == "__main__":
    sys.exit(main(["fetch"]))
