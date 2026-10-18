"""How to reach each federal court: its own website, and the national
courts the judges' directory does not cover.

``SITES`` is each court's website as the courts list them on uscourts.gov's
"Court Website Links" page (the courts of appeals, and the district courts'
column of its district and bankruptcy table), joined to this site's court
ids by the circuit and the state and district the page names - never by
the host name, which does not follow the ids (``ca-n`` is
``cand.uscourts.gov``). The Supreme Court's is supremecourt.gov, and the
District of Columbia's district court, which the page lists under "District
of Columbia", is ``dcd``. Read on 2026-10-17; every address was fetched
that day, a second apart, and answered with the court's own home page
(Colorado's still serves plain http, and is listed as it serves itself).

Every host is the judiciary's own (``uscourts.gov``, ``supremecourt.gov``),
not a domain that can lapse and be bought (rule 35); ``check`` fails on any
other host, a court with no address, or two courts sharing one.

``OTHER_COURTS`` are the national courts created under Article I, whose
judges serve terms and are not in the Federal Judicial Center's directory
of Article III judges: each is named on the federal page, linked to its own
list of judges, so a reader can tell they were left out on purpose. Each
address was fetched on 2026-10-17 and answered with that court's judges.
"""

from urllib.parse import urlparse

REVIEWED = "2026-10-17"
SOURCE = "https://www.uscourts.gov/about-federal-courts/court-role-and-structure/court-website-links"

SITES = {
    "scotus": "https://www.supremecourt.gov",
    "ca1": "https://www.ca1.uscourts.gov",
    "ca2": "https://www.ca2.uscourts.gov",
    "ca3": "https://www.ca3.uscourts.gov",
    "ca4": "https://www.ca4.uscourts.gov",
    "ca5": "https://www.ca5.uscourts.gov",
    "ca6": "https://www.ca6.uscourts.gov",
    "ca7": "https://www.ca7.uscourts.gov",
    "ca8": "https://www.ca8.uscourts.gov",
    "ca9": "https://www.ca9.uscourts.gov",
    "ca10": "https://www.ca10.uscourts.gov",
    "ca11": "https://www.ca11.uscourts.gov",
    "cadc": "https://www.cadc.uscourts.gov",
    "cafc": "https://www.cafc.uscourts.gov",
    "cit": "https://www.cit.uscourts.gov",
    "ak": "https://www.akd.uscourts.gov",
    "al-m": "https://www.almd.uscourts.gov",
    "al-n": "https://www.alnd.uscourts.gov",
    "al-s": "https://www.alsd.uscourts.gov",
    "ar-e": "https://www.are.uscourts.gov",
    "ar-w": "https://www.arwd.uscourts.gov",
    "az": "https://www.azd.uscourts.gov",
    "ca-c": "https://www.cacd.uscourts.gov",
    "ca-e": "https://www.caed.uscourts.gov",
    "ca-n": "https://www.cand.uscourts.gov",
    "ca-s": "https://www.casd.uscourts.gov",
    "co": "http://www.cod.uscourts.gov/Home.aspx",
    "ct": "https://www.ctd.uscourts.gov",
    "dc": "https://www.dcd.uscourts.gov",
    "de": "https://www.ded.uscourts.gov",
    "fl-m": "https://www.flmd.uscourts.gov",
    "fl-n": "https://www.flnd.uscourts.gov",
    "fl-s": "https://www.flsd.uscourts.gov",
    "ga-m": "https://www.gamd.uscourts.gov",
    "ga-n": "https://www.gand.uscourts.gov",
    "ga-s": "https://www.gasd.uscourts.gov",
    "gu": "https://www.gud.uscourts.gov",
    "hi": "https://www.hid.uscourts.gov",
    "ia-n": "https://www.iand.uscourts.gov",
    "ia-s": "https://www.iasd.uscourts.gov",
    "id": "https://www.id.uscourts.gov",
    "il-c": "https://www.ilcd.uscourts.gov",
    "il-n": "https://www.ilnd.uscourts.gov",
    "il-s": "https://www.ilsd.uscourts.gov",
    "in-n": "https://www.innd.uscourts.gov",
    "in-s": "https://www.insd.uscourts.gov",
    "ks": "https://www.ksd.uscourts.gov",
    "ky-e": "https://www.kyed.uscourts.gov",
    "ky-w": "https://www.kywd.uscourts.gov",
    "la-e": "https://www.laed.uscourts.gov",
    "la-m": "https://www.lamd.uscourts.gov",
    "la-w": "https://www.lawd.uscourts.gov",
    "ma": "https://www.mad.uscourts.gov",
    "md": "https://www.mdd.uscourts.gov",
    "me": "https://www.med.uscourts.gov",
    "mi-e": "https://www.mied.uscourts.gov",
    "mi-w": "https://www.miwd.uscourts.gov",
    "mn": "https://www.mnd.uscourts.gov",
    "mo-e": "https://www.moed.uscourts.gov",
    "mo-w": "https://www.mow.uscourts.gov",
    "mp": "https://www.nmid.uscourts.gov",
    "ms-n": "https://www.msnd.uscourts.gov",
    "ms-s": "https://www.mssd.uscourts.gov",
    "mt": "https://www.mtd.uscourts.gov",
    "nc-e": "https://www.nced.uscourts.gov",
    "nc-m": "https://www.ncmd.uscourts.gov",
    "nc-w": "https://www.ncwd.uscourts.gov",
    "nd": "https://www.ndd.uscourts.gov",
    "ne": "https://www.ned.uscourts.gov",
    "nh": "https://www.nhd.uscourts.gov",
    "nj": "https://www.njd.uscourts.gov",
    "nm": "https://www.nmd.uscourts.gov",
    "nv": "https://www.nvd.uscourts.gov",
    "ny-e": "https://www.nyed.uscourts.gov",
    "ny-n": "https://www.nynd.uscourts.gov",
    "ny-s": "https://www.nysd.uscourts.gov",
    "ny-w": "https://www.nywd.uscourts.gov",
    "oh-n": "https://www.ohnd.uscourts.gov",
    "oh-s": "https://www.ohsd.uscourts.gov",
    "ok-e": "https://www.oked.uscourts.gov",
    "ok-n": "https://www.oknd.uscourts.gov",
    "ok-w": "https://www.okwd.uscourts.gov",
    "or": "https://www.ord.uscourts.gov",
    "pa-e": "https://www.paed.uscourts.gov",
    "pa-m": "https://www.pamd.uscourts.gov",
    "pa-w": "https://www.pawd.uscourts.gov",
    "pr": "https://www.prd.uscourts.gov",
    "ri": "https://www.rid.uscourts.gov",
    "sc": "https://www.scd.uscourts.gov",
    "sd": "https://www.sdd.uscourts.gov",
    "tn-e": "https://www.tned.uscourts.gov",
    "tn-m": "https://www.tnmd.uscourts.gov",
    "tn-w": "https://www.tnwd.uscourts.gov",
    "tx-e": "https://www.txed.uscourts.gov",
    "tx-n": "https://www.txnd.uscourts.gov",
    "tx-s": "https://www.txs.uscourts.gov",
    "tx-w": "https://www.txwd.uscourts.gov",
    "ut": "https://www.utd.uscourts.gov",
    "va-e": "https://www.vaed.uscourts.gov",
    "va-w": "https://www.vawd.uscourts.gov",
    "vi": "https://www.vid.uscourts.gov",
    "vt": "https://www.vtd.uscourts.gov",
    "wa-e": "https://www.waed.uscourts.gov",
    "wa-w": "https://www.wawd.uscourts.gov",
    "wi-e": "https://www.wied.uscourts.gov",
    "wi-w": "https://www.wiwd.uscourts.gov",
    "wv-n": "https://www.wvnd.uscourts.gov",
    "wv-s": "https://www.wvsd.uscourts.gov",
    "wy": "https://www.wyd.uscourts.gov",
}

OTHER_COURTS = (
    {"name": "U.S. Court of Federal Claims", "site": "https://www.uscfc.uscourts.gov",
     "judges": "https://www.uscfc.uscourts.gov/judges"},
    {"name": "U.S. Tax Court", "site": "https://www.ustaxcourt.gov",
     "judges": "https://www.ustaxcourt.gov/judges/"},
    {"name": "U.S. Court of Appeals for Veterans Claims", "site": "https://www.uscourts.cavc.gov",
     "judges": "https://www.uscourts.cavc.gov/judges.php"},
    {"name": "U.S. Court of Appeals for the Armed Forces", "site": "https://www.armfor.uscourts.gov",
     "judges": "https://www.armfor.uscourts.gov/newcaaf/judges.htm"},
)

_HOSTS = ("uscourts.gov", "supremecourt.gov", "ustaxcourt.gov", "cavc.gov")


def _judiciary_host(url):
    host = urlparse(url).hostname or ""
    return any(host == h or host.endswith("." + h) for h in _HOSTS)


def check():
    """Problems with the tables. Empty when they are sound."""
    from .federal_courts import COURTS

    problems = []
    missing = sorted(set(COURTS) - set(SITES))
    extra = sorted(set(SITES) - set(COURTS))
    if missing or extra:
        problems.append(f"court sites: missing {missing}, unknown {extra}")
    hosts = {}
    for cid, url in SITES.items():
        if not _judiciary_host(url):
            problems.append(f"{cid}: {url} is not on a host of the judiciary's own")
        hosts.setdefault(urlparse(url).hostname, []).append(cid)
    shared = {h: c for h, c in hosts.items() if len(c) > 1}
    if shared:
        problems.append(f"courts sharing one website: {shared}")
    for court in OTHER_COURTS:
        if not (_judiciary_host(court["site"]) and _judiciary_host(court["judges"])):
            problems.append(f"{court['name']}: not on a host of the judiciary's own")
    return problems
