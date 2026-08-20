"""Know Your Candidate - data pipeline for the congressional profile site.

The pipeline reads the curated CSV rosters at the repo root, normalises them
into a single list of profile records, and emits that list as a JavaScript
data file consumed by ``candidate_profiles_site/``.

Entry point: ``python build_profile_site.py`` (see :mod:`kyc.cli`).
"""

__version__ = "2.0.0"
