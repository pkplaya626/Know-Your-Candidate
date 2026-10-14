"""Each state's official voting pages, from NASS's "Can I Vote".

Nothing on the site told a reader how, when or where to vote (audit
2026-10-13, CG-5). The links are the states' own; NASS is the directory, and
a page that does not list every state and D.C. once is refused.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kyc import validate, voting  # noqa: E402
from kyc.normalize import US_STATES  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
NAMES = {code: name.title() for name, code in US_STATES.items() if code in voting.JURISDICTIONS}


def page(rows):
    return "<select>" + "".join(
        f'<option value="{url}">{name}</option>' for name, url in rows) + "</select>"


def every_state(**change):
    rows = {code: (NAMES[code], f"https://vote.{code.lower()}.gov/check") for code in NAMES}
    rows.update(change)
    return [row for row in rows.values() if row]


class TestParse(unittest.TestCase):
    def test_every_state_and_dc_once(self):
        found = voting.parse(page(every_state()))
        self.assertEqual(set(found), voting.JURISDICTIONS)
        self.assertEqual(len(found), 51)
        self.assertEqual(found["DC"], "https://vote.dc.gov/check")

    def test_a_missing_state_refuses_the_page(self):
        with self.assertRaisesRegex(voting.VotingError, "no link for WY"):
            voting.parse(page(every_state(WY=None)))

    def test_a_state_twice_is_refused(self):
        rows = every_state() + [("Texas", "https://elsewhere.example.org/")]
        with self.assertRaisesRegex(voting.VotingError, "TX is listed twice"):
            voting.parse(page(rows))

    def test_an_option_that_is_not_a_web_address_is_refused(self):
        with self.assertRaisesRegex(voting.VotingError, "not a web address"):
            voting.parse(page(every_state(OH=("Ohio", "javascript:alert(1)"))))

    def test_an_option_that_is_not_a_state_is_refused(self):
        rows = every_state() + [("Select a state", "https://www.nass.org/")]
        with self.assertRaisesRegex(voting.VotingError, "not a state"):
            voting.parse(page(rows))

    def test_fetch_reads_all_four_pages(self):
        cache = voting.fetch(get=lambda url: page(every_state()))
        self.assertEqual(set(cache["states"]["PA"]), set(voting.PAGES))
        self.assertEqual(cache["source"], voting.SOURCE)


class TestValidate(unittest.TestCase):
    def test_a_gap_is_an_error(self):
        cache = voting.fetch(get=lambda url: page(every_state()))
        self.assertEqual(validate.check_voting_links(cache), [])
        del cache["states"]["NV"]["polling"]
        self.assertEqual([i.code for i in validate.check_voting_links(cache)],
                         ["voting-links-incomplete"])

    def test_the_committed_cache_is_complete(self):
        cache = voting.load_cache(ROOT)
        self.assertIsNotNone(cache)
        self.assertEqual(validate.check_voting_links(cache), [])


if __name__ == "__main__":
    unittest.main()
