"""What the job pays: a member of Congress's salary as the law sets it.

A reader's question on a member's profile (PROFILES-25), answered from a
small table read from the sources below, never from a search. The salary is
not the member's: it is the rate the law sets for the post, $174,000 for
every senator, representative, delegate and the resident commissioner since
2009, when appropriations acts began denying the annual adjustment each
year. Four kinds of post are paid more, and congress-legislators records who
holds them (``legislators.held_posts``): the Speaker, the President pro
tempore, and the majority and minority leaders of each chamber.

The rates are a year's. A new year can bring a new rate (the adjustment is
denied one act at a time, and the Congressional Research Service names the
act for each year), so the table carries its year and the Congress sitting
then: a profile shows the line only while the membership is of that Congress
- the next Congress's leaders are not yet recorded on January 3, and a
re-elected Speaker would read as paid a member's rate - and the page drops it
once the reader's year is past the table's (assets/kyc-profile.js). The
build warns once its own year is (``validate.check_pay``): read the report
again, then move the year and the figures.
"""

import datetime
import re

# The year the rates are for, and the Congress sitting in it.
YEAR = 2026
CONGRESS = 119

# The salary set by law for a member who holds none of POSTS.
MEMBER = 174000

# The posts paid more, by the title congress-legislators records
# (legislators.held_posts, after overrides.LEADERSHIP_TITLES).
POSTS = {
    "Speaker of the House": 223500,
    "President Pro Tempore of the Senate": 193400,
    "Senate Majority Leader": 193400,
    "Senate Minority Leader": 193400,
    "House Majority Leader": 193400,
    "House Minority Leader": 193400,
}

# Where each figure was read, and on which day. The report is the source of
# every figure; the Senate's page agrees on the members' and its leaders'.
SOURCES = (
    {"title": "Congressional Research Service, Congressional Salaries and Allowances: In "
              "Brief (RL30064), updated September 10, 2026, Table 1",
     "url": "https://www.congress.gov/crs-product/RL30064",
     "read": "2026-10-19",
     "quote": "Table 1. Members and House and Senate Staff Maximum Salaries in 2026: Speaker of "
              "the House $223,500 per annum; President pro tempore $193,400 per annum; Majority "
              "and Minority Leaders (House and Senate) $193,400 per annum; All other "
              "Representatives (including Delegates and Resident Commissioner from Puerto Rico) "
              "and Senators $174,000 per annum. Sources: For salaries of Members of Congress, "
              "P.L. 119-37 (November 12, 2025). ... These levels have remained unchanged since "
              "2009."},
    {"title": "U.S. Senate: Senate Salaries (1789 to Present)",
     "url": "https://www.senate.gov/senators/SenateSalariesSince1789.htm",
     "read": "2026-10-19",
     "quote": "2026 $174,000 per annum. Note: Since the early 1980s, Senate leaders - majority "
              "and minority leaders, and the president pro tempore - have received higher "
              "salaries than other members. Currently, leaders earn $193,400 per year."},
)

# A post whose title says it is one of POSTS' kinds. One that matches this
# and is not in POSTS by its exact title would be paid a member's rate on the
# page: a renamed title fails the build instead (validate.check_pay).
_PAID_KIND = re.compile(r"\b(speaker|pro tempore|majority leader|minority leader)\b", re.I)
_NOT_THE_POST = re.compile(r"^(assistant|deputy)\b|\bwhip\b", re.I)


def is_paid_kind(title):
    """True when *title* reads as one of the posts paid more."""
    return bool(_PAID_KIND.search(title or "")) and not _NOT_THE_POST.search(title or "")


def rate(posts):
    """``(amount, post)``: the salary for a member holding *posts*, and the
    post that sets it (None for a member's rate)."""
    best = (MEMBER, None)
    for post in posts or ():
        if POSTS.get(post, 0) > best[0]:
            best = (POSTS[post], post)
    return best


def applies(sitting):
    """True when the membership is of the Congress the table's year is."""
    return sitting == CONGRESS


def apply(profiles, sitting):
    """Give each sitting member's profile ``pay``: ``{"amount", "post"}``,
    the post only where it sets a higher rate. Nobody else's: a candidate is
    paid nothing by Congress, a former member no longer, and a membership of
    another Congress than the table's gets none (its leaders may not be
    recorded yet)."""
    from .members import is_member
    from .record import seated

    for profile in profiles:
        profile.pop("pay", None)
        if not applies(sitting) or not seated(profile) or not is_member(profile):
            continue
        amount, post = rate(profile.get("leadership"))
        profile["pay"] = {"amount": amount, **({"post": post} if post else {})}


def for_page(sitting):
    """``kycBuildMeta.pay``: the year, the member's rate and the sources, or
    None where :func:`apply` gave nobody a figure."""
    if not applies(sitting):
        return None
    return {"year": YEAR, "member": MEMBER,
            "sources": [{"title": s["title"], "url": s["url"], "read": s["read"]} for s in SOURCES]}


def problems(profiles, sitting, today=None):
    """``[(severity, code, message, items)]`` for validate.check_pay."""
    out = []
    unknown = sorted({post for p in profiles for post in p.get("leadership") or []
                      if is_paid_kind(post) and post not in POSTS})
    if unknown:
        out.append(("error", "pay-post-unknown",
                    f"{len(unknown)} leadership posts read as paid more than a member but are not "
                    "in kyc/pay.POSTS by that title: add them with the rate the source gives",
                    unknown))
    today = today or datetime.date.today()
    if today.year > YEAR:
        out.append(("warn", "pay-stale",
                    f"kyc/pay.py holds {YEAR}'s salaries and it is {today.year}: read the CRS "
                    "report (RL30064) again, then move YEAR, CONGRESS and the figures", []))
    elif applies(sitting) and not any(p.get("pay") for p in profiles):
        out.append(("error", "pay-missing", "no sitting member has a salary line", []))
    return out
