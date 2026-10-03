// Render index.html / map.html in jsdom and exercise the real page code.
//
//   npm install jsdom
//   node tests/render_test.js            # both pages
//   node tests/render_test.js index.html # one page
//
// This is the only test that runs the shipped JavaScript against the shipped
// markup and the real generated data, so it is where "the page still works"
// is actually established. Everything it asserts is something that has been
// broken at least once.

const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const SITE = path.resolve(__dirname, "..", "candidate_profiles_site");

/* ------------------------------------------------------------------ setup */

function buildPage(page, opts) {
  opts = opts || {};
  const errors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => errors.push("jsdomError: " + e.message));
  vc.on("error", (...a) => errors.push("console.error: " + a.join(" ")));

  // jsdom does not fetch <script src>, so inline every local script in
  // document order - exactly the order a browser would execute them in.
  let html = fs.readFileSync(path.join(SITE, page), "utf8");
  const sources = [...html.matchAll(/<script[^>]*\bsrc="([^"]+)"[^>]*><\/script>/g)];
  for (const [tag, src] of sources) {
    // Relative to the page: the state pages sit one directory down.
    const file = path.join(path.dirname(path.join(SITE, page)), ...src.split("/"));
    if (!fs.existsSync(file)) throw new Error(`${page} references a missing ${src}`);
    html = html.replace(tag, () => "<script>\n" + fs.readFileSync(file, "utf8") + "\n</script>");
  }

  const dom = new JSDOM(html, {
    runScripts: "dangerously",
    url: "https://kyc.local/" + page + (opts.hash || ""),
    pretendToBeVisual: true,
    virtualConsole: vc,
    beforeParse(window) {
      // jsdom has no matchMedia; the theme layer asks it whether the OS
      // prefers light.
      // Count every history.back(): from a page someone landed on directly,
      // one takes them off the site, and jsdom would silently do nothing.
      window.__backCalls = 0;
      const back = window.history.back.bind(window.history);
      window.history.back = () => { window.__backCalls += 1; back(); };
      window.matchMedia = (query) => ({
        media: query,
        matches: false,
        addEventListener() {},
        removeEventListener() {},
        addListener() {},
        removeListener() {},
      });
    },
  });

  const { window } = dom;
  const packed = { window, D: window.document, errors, sources: sources.map((m) => m[1]) };

  // Wait for jsdom's own DOMContentLoaded rather than dispatching one. An
  // earlier version fired the event by hand, jsdom then fired its own, and
  // every page module booted twice - two listeners per control, so a single
  // click toggled the race view on and straight back off.
  return new Promise((resolve) => {
    if (window.document.readyState !== "loading") return resolve(packed);
    window.document.addEventListener("DOMContentLoaded", () => resolve(packed));
  });
}

/* ------------------------------------------------------------------ harness */

const results = [];
function check(label, cond, detail) {
  results.push({ label, ok: !!cond, detail });
}

function suite(name, fn) {
  results.push({ heading: name });
  fn();
}

/* ================================================================ shared */

async function testShared(page) {
  const { window, D, errors, sources } = await buildPage(page);
  const KYC = window.KYC;

  suite(`${page} — load`, () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("data loaded", (window.legislatorsData || []).length > 0,
      `${(window.legislatorsData || []).length} profiles`);
    check("shared module present", !!KYC);
    check("theme applied before paint", !!D.documentElement.getAttribute("data-theme"),
      D.documentElement.getAttribute("data-theme"));
    check("icon sprite injected", !!D.getElementById("kyc-sprite"));
    check("every <use> resolves to a sprite symbol", (() => {
      const ids = new Set([...D.querySelectorAll("#kyc-sprite symbol")].map((s) => s.id));
      const used = [...D.querySelectorAll("use")].map((u) => (u.getAttribute("href") || "").slice(1));
      return used.length > 0 && used.every((id) => ids.has(id));
    })());
  });

  suite(`${page} — no third-party runtime dependencies`, () => {
    // The whole point of the rewrite: a civic directory should not depend on
    // four CDNs staying up, and Tailwind's play CDN compiled CSS in the
    // browser on every visit.
    const external = sources.filter((s) => /^https?:/.test(s));
    check("no remote <script src>", external.length === 0, external.join(", "));
    const raw = fs.readFileSync(path.join(SITE, page), "utf8");
    // Specifically a *stylesheet*, not any remote <link>. The original test
    // matched every https href and so failed the moment rel="canonical" was
    // added, which loads nothing at all.
    const remoteLinks = [...raw.matchAll(/<link\b[^>]*>/g)].map((m) => m[0])
      .filter((tag) => /href="https?:/.test(tag))
      .filter((tag) => /rel="(stylesheet|preload|preconnect|dns-prefetch)"/.test(tag));
    check("no remote stylesheet or font", remoteLinks.length === 0, remoteLinks.join(" "));
    check("no tailwind", !/tailwind/i.test(raw));
    check("no d3 / topojson / lucide", !/\b(d3|topojson|lucide)\b/i.test(raw));
  });

  suite(`${page} — accessibility`, () => {
    const viewport = D.querySelector('meta[name="viewport"]').content;
    check("pinch-zoom not blocked", !/user-scalable=no|maximum-scale/.test(viewport), viewport);
    check("has a skip link", !!D.querySelector("a.skip-link"));
    check("page has a title", D.title.length > 10, D.title);
    check("page has a description", !!D.querySelector('meta[name="description"]'));
    check("html has a lang", D.documentElement.lang === "en");
    check("theme menu is a real button", (() => {
      const b = D.getElementById("themeButton");
      return b && b.tagName === "BUTTON" && b.getAttribute("aria-expanded") === "false";
    })());
    check("theme menu opens on click", (() => {
      D.getElementById("themeButton").click();
      return !D.getElementById("themePanel").hidden;
    })());
    check("theme menu closes on Escape", (() => {
      D.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return D.getElementById("themePanel").hidden;
    })());
    check("every image has an alt attribute",
      [...D.querySelectorAll("img")].every((i) => i.hasAttribute("alt")));
  });

  suite(`${page} — hiding actually hides`, () => {
    // jsdom has no cascade, so this asserts the rule rather than the effect.
    // Without it a class selector like `.money-grid { display: grid }` beats
    // the bare [hidden] attribute and the page shows an empty box - which is
    // exactly what the "Cash on hand" tile did.
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    check("[hidden] wins over component display rules",
      /\[hidden\]\s*\{[^}]*display:\s*none\s*!important/.test(css));
    check("the page hides with the property, not a class", (() => {
      const js = ["kyc.js", "kyc-odds.js", "kyc-cards.js", "kyc-profile.js", "kyc-senate.js", "kyc-directory.js", "kyc-map.js", "kyc-state.js"]
        .filter((f) => fs.existsSync(path.join(SITE, "assets", f)))
        .map((f) => fs.readFileSync(path.join(SITE, "assets", f), "utf8"))
        .join("\n");
      return !/classList\.(add|remove|toggle)\(["']hidden["']/.test(js);
    })());
  });

  suite(`${page} — sidebar figures come from the build`, () => {
    // These were literal text in both sidebars ("53 R | 47 D/I", "35", "435")
    // with nothing tying them to the rosters.
    const meta = window.kycBuildMeta;
    check("build metadata carries the chamber split", !!(meta && meta.senate && meta.house));
    check("senate balance rendered", /\d/.test(D.getElementById("senateBalance").textContent));
    check("house balance rendered", /\d/.test(D.getElementById("houseBalance").textContent));
    check("senate seats up matches the data",
      D.getElementById("senateSeatsUp").textContent === String(meta.election.senateSeatsUp),
      D.getElementById("senateSeatsUp").textContent);
    check("house seats up is the full chamber",
      D.getElementById("houseSeatsUp").textContent === "435");
    check("countdown rendered", /\d+ days|Election Day|has passed/.test(
      D.getElementById("electionCountdown").textContent));
  });

  suite(`${page} — provenance`, () => {
    const absent = KYC.renderField(
      { net_worth: "Not disclosed", quality: { net_worth: "not_disclosed" } }, "net_worth");
    check("absence renders as an absence", /kyc-absent/.test(absent) && /Not disclosed/.test(absent));

    const generic = KYC.renderField(
      { funding_sources: "Individual/PAC contributions", quality: { funding_sources: "generic" } },
      "funding_sources");
    check("generic value marked low-information", /kyc-generic/.test(generic));

    const sourced = KYC.renderField(
      { receipts: "$1,022,664.06", quality: {}, financeSource: "FEC", financeAsOf: "2026-06-30" },
      "receipts", { source: true });
    check("sourced figure carries a badge", /badge-money/.test(sourced) && /FEC/.test(sourced));

    check("renderField escapes markup", (() => {
      const html = KYC.renderField({ x: '<img src=x onerror=alert(1)>', quality: {} }, "x");
      return !/<img/.test(html) && /&lt;img/.test(html);
    })());
    check("renderField escapes the FEC badge title", (() => {
      const html = KYC.renderField(
        { receipts: "$1", quality: {}, financeSource: '"><script>x</script>' },
        "receipts", { source: true });
      return !/<script/.test(html);
    })());
    check("a $0 filing is not an absence",
      !/kyc-absent/.test(KYC.renderField({ receipts: "$0.00", quality: {} }, "receipts")));
  });

  suite(`${page} — finance period`, () => {
    // An incumbent's and a challenger's totals were once measured over
    // different periods with nothing on the page to say so.
    const senate = { financeSource: "FEC", chamber: "Senate", financePeriod: "election",
      financeElection: 2026, financeSince: "2021-01-01", financeAsOf: "2026-08-26" };
    const p = KYC.financePeriod(senate);
    check("the election and its months are named",
      p.indexOf("Raised for the 2026 election, Jan 2021 – Aug 2026") === 0, p);
    check("a six-year Senate period says so", /six-year term/.test(p) && /2021/.test(p), p);

    const house = KYC.financePeriod({ financeSource: "FEC", chamber: "House (Candidate)",
      financePeriod: "election", financeElection: 2026,
      financeSince: "2025-01-01", financeAsOf: "2026-06-30" });
    check("a two-year House period carries no Senate caveat",
      house === "Raised for the 2026 election, Jan 2025 – Jun 2026", house);

    const noStart = KYC.financePeriod({ financeSource: "FEC", chamber: "House (Candidate)",
      financePeriod: "election", financeElection: 2026, financeSince: null,
      financeAsOf: "2026-06-30" });
    check("no start date is reported as none, not invented",
      noStart === "Raised for the 2026 election, through Jun 2026", noStart);

    const cycle = KYC.financePeriod({ financeSource: "FEC", chamber: "Senate",
      financePeriod: "cycle", financeSince: null, financeAsOf: "2026-08-26" });
    check("an old two-year cycle total is called one, not an election total",
      /2025–26 two-year cycle/.test(cycle) && !/2026 election/.test(cycle) &&
        /not comparable/.test(cycle), cycle);

    check("no money, no period", KYC.financePeriod({ receipts: "No data" }) === "");
    check("a malformed date is dropped, not shown",
      KYC.financePeriod({ financeSource: "FEC", financePeriod: "election",
        financeElection: 2026, financeSince: "<b>x</b>", financeAsOf: "2026-06-30" }) ===
        "Raised for the 2026 election, through Jun 2026");

    const badge = KYC.renderField(Object.assign({ receipts: "$1", quality: {} }, senate),
      "receipts", { source: true });
    check("the FEC badge title carries the period", /Jan 2021/.test(badge) && /2026 election/.test(badge));
  });

  suite(`${page} — election arithmetic`, () => {
    const es = KYC.electionStatus(2026, new Date("2026-08-20T12:00:00Z"));
    check("2026 election day is 3 November", es.iso === "2026-11-03", es.iso);
    check("countdown counts down", es.days === 75, `${es.days} days`);
    check("phase during campaign", es.phase === "campaign", es.phase);
    check("phase after the vote",
      KYC.electionStatus(2026, new Date("2026-12-01T12:00:00Z")).phase === "post-election");
    // The reader's calendar, not UTC's. Dates are built from local
    // components so the check means the same thing in every time zone: the
    // old UTC arithmetic said "Election Day" from Sunday evening in the
    // East and "has passed" while the West was still voting.
    const at = (m, d, h, min) => KYC.electionStatus(2026, new Date(2026, m - 1, d, h, min || 0));
    check("Sunday 1 Nov, late evening: still two days out",
      at(11, 1, 23, 30).phase === "campaign" && at(11, 1, 23, 30).days === 2,
      at(11, 1, 23, 30).label);
    check("Monday 2 Nov, all day: one day out, not Election Day",
      [0, 12, 19, 23].every((h) => at(11, 2, h).phase === "campaign" && at(11, 2, h).days === 1) &&
        at(11, 2, 20).label === "1 day to the 2026 election",
      at(11, 2, 20).label);
    check("Tuesday 3 Nov, midnight to midnight: Election Day",
      [0, 7, 19, 20, 23].every((h) => at(11, 3, h).phase === "election-day") &&
        at(11, 3, 23, 59).label === "Election Day",
      at(11, 3, 21).label);
    check("Wednesday 4 Nov from midnight: the election has passed",
      at(11, 4, 0, 1).phase === "post-election" &&
        at(11, 4, 0, 1).label === "2026 general election has passed",
      at(11, 4, 0, 1).label);
    check("1 October reads 33 days", at(10, 1, 12).days === 33, at(10, 1, 12).label);
    // 2028: first Monday is the 6th, so election day is the 7th.
    check("election day generalises to 2028",
      KYC.electionStatus(2028, new Date("2028-01-01Z")).iso === "2028-11-07");
  });

  return { window, D, KYC };
}

/* ============================================================== index.html */

/* The grid renders a screenful and appends the rest on scroll, so the DOM
 * holds at most a page of cards; the announced count is the real total. */
function announced(D) {
  const m = D.getElementById("resultsLabel").textContent.match(/Showing ([\d,]+)/);
  return m ? parseInt(m[1].replace(/,/g, ""), 10) : 0;
}

async function testDirectory() {
  const { window, D, KYC } = await testShared("index.html");
  const grid = D.getElementById("results");
  const cards = () => grid.querySelectorAll(".card");

  suite("index.html — grid", () => {
    check("a screenful of cards rendered", cards().length > 100, `${cards().length} cards`);
    check("the full count is announced", announced(D) > 400, `${announced(D)}`);
    check("the rest is one click away", (() => {
      const more = D.getElementById("gridMore");
      if (!more) return false;
      const before = cards().length;
      more.click();
      return cards().length > before;
    })(), `${cards().length} after Show more`);
    check("portraits lazy-load",
      grid.querySelectorAll('img[loading="lazy"]').length === cards().length);
    check("cards are buttons, not clickable divs",
      [...cards()].every((c) => c.tagName === "BUTTON"));
    check("no inline onclick handlers anywhere",
      D.querySelectorAll("[onclick],[onerror]").length === 0);
    check("office label comes from the data, not rebuilt in the page", (() => {
      // "House • AL-District 3" and "House • TX-TX-32" both shipped once,
      // from the page rebuilding a label the pipeline had already normalised.
      // The check is that the card prints exactly what kyc/profiles.py
      // produced - not that the label matches some shape guessed here.
      const cards = [...grid.querySelectorAll(".card")];
      return cards.length > 0 && cards.every((c) => {
        const item = KYC.byId(c.getAttribute("data-id"));
        return c.querySelector(".card-office").textContent === item.officeLabel;
      });
    })());
    check("no label carries a raw roster district spelling", (() => {
      const texts = [...grid.querySelectorAll(".card-office")].map((n) => n.textContent);
      return texts.every((t) => !/District \d|([A-Z]{2})-\1/.test(t));
    })());
    check("card names are escaped", (() => {
      const html = grid.innerHTML;
      return !/<img[^>]*onerror/.test(html);
    })());
  });

  suite("index.html — filtering", () => {
    const label = D.getElementById("resultsLabel");
    const total = announced(D);

    D.querySelector('[data-group="chamber"][data-value="Senate"]').click();
    const senate = announced(D);
    check("chamber filter narrows the grid", senate > 0 && senate < total,
      `${senate} of ${total}`);
    check("chamber filter is reflected in the URL",
      /chamber=Senate/.test(window.location.hash), window.location.hash);
    check("results count is announced", /Showing/.test(label.textContent), label.textContent);

    D.querySelector('[data-group="party"][data-value="Republican"]').click();
    check("filters compose", announced(D) < senate, `${announced(D)}`);
    D.querySelector('[data-group="party"][data-value="Republican"]').click();
    check("clicking an active optional chip clears it", announced(D) === senate);

    D.querySelector('[data-group="chamber"][data-value="all"]').click();
    check("chamber resets", announced(D) === total);

    const search = D.getElementById("searchInput");
    search.value = "Armed Services";
    search.dispatchEvent(new window.Event("input"));
    // The search is debounced; the assertion below runs after the timer.
    return { window, D, KYC, total };
  });

  return { window, D, KYC };
}

async function testDirectoryAsync() {
  const { window, D, KYC } = await testDirectory();
  await new Promise((r) => setTimeout(r, 250));
  const cards = () => D.getElementById("results").querySelectorAll(".card");

  suite("index.html — search", () => {
    check("committee text is searchable", cards().length > 0,
      `${cards().length} hits for "Armed Services"`);
    check("search reaches beyond name and state",
      cards().length < window.legislatorsData.length);

    const search = D.getElementById("searchInput");
    search.value = "not disclosed";
    search.dispatchEvent(new window.Event("input"));
  });

  await new Promise((r) => setTimeout(r, 250));
  suite("index.html — absences are not searchable", () => {
    // "Not disclosed" is a label the page prints, not a fact about a person,
    // so searching it must not match everyone who lacks a filing.
    check('searching "not disclosed" matches nothing', cards().length === 0,
      `${cards().length} hits`);
    const search = D.getElementById("searchInput");
    search.value = "";
    search.dispatchEvent(new window.Event("input"));
  });

  await new Promise((r) => setTimeout(r, 250));

  suite("index.html — sitting members vs challengers", () => {
    // Since the field came from the FEC, 79% of profiles are people who do
    // not hold the seat. "Who represents me" has to be one click.
    const cards = () => D.getElementById("results").querySelectorAll(".card");
    const total = announced(D);

    D.querySelector('[data-group="role"][data-value="member"]').click();
    const members = [...cards()];
    const memberTotal = announced(D);
    check("sitting members filter narrows the grid", memberTotal < total,
      `${memberTotal} of ${total}`);
    check("every card is someone currently in Congress",
      members.every((c) => !KYC.byId(c.getAttribute("data-id")).isCandidate));
    check("the filter is in the URL", /role=member/.test(window.location.hash),
      window.location.hash);

    D.querySelector('[data-group="chamber"][data-value="Senate"]').click();
    check("it composes with chamber", cards().length === 100,
      `${cards().length} senators`);
    D.querySelector('[data-group="chamber"][data-value="all"]').click();

    D.querySelector('[data-group="role"][data-value="candidate"]').click();
    check("challengers filter is the complement",
      announced(D) === total - memberTotal, `${announced(D)}`);
    check("every card is a challenger",
      [...cards()].every((c) => KYC.byId(c.getAttribute("data-id")).isCandidate));

    D.querySelector('[data-group="role"][data-value="candidate"]').click();
    check("clicking the active chip clears it", announced(D) === total);
  });

  suite("index.html — links shared before the filter moved", () => {
    // The challenger filter used to live in the election group.
    window.location.hash = "#/?election=candidate";
    window.dispatchEvent(new window.Event("hashchange"));
    const shown = [...D.getElementById("results").querySelectorAll(".card")];
    check("a legacy challenger link still filters", shown.length > 0 &&
      shown.every((c) => KYC.byId(c.getAttribute("data-id")).isCandidate),
      `${shown.length} cards`);
    check("and is rewritten to the new parameter",
      /role=candidate/.test(window.location.hash), window.location.hash);
    window.location.hash = "#/";
    window.dispatchEvent(new window.Event("hashchange"));
  });

  suite("index.html — races", () => {
    const toggle = D.getElementById("raceViewToggle");
    toggle.click();
    const sections = D.getElementById("results").querySelectorAll("section.race");
    check("race view groups profiles into seats", sections.length > 0,
      `${sections.length} races`);
    check("race view is announced as pressed", toggle.getAttribute("aria-pressed") === "true");
    check("every race has a heading",
      [...sections].every((s) => s.querySelector(".race-title").textContent.trim().length > 3));
    check("a contested race shows its challengers", (() => {
      const contested = [...sections].find((s) => /challenger/.test(s.textContent));
      return !!contested && contested.querySelectorAll(".card").length >= 2;
    })());
    toggle.click();
    check("race view toggles back off",
      D.getElementById("results").querySelectorAll("section.race").length === 0);
  });

  suite("index.html — profile dialog", () => {
    const first = D.getElementById("results").querySelector(".card");
    const id = first.getAttribute("data-id");
    first.click();

    const modal = D.getElementById("profileModal");
    check("dialog opens on card click", modal && !modal.hidden);
    check("dialog is labelled", modal.getAttribute("aria-labelledby") === "profileModalName");
    check("dialog names the person",
      D.getElementById("profileModalName").textContent === KYC.byId(id).name);
    check("deep link written to the URL",
      window.location.hash === "#/profile/" + encodeURIComponent(id), window.location.hash);
    check("region uses the pipeline's office label",
      D.getElementById("profileModalRegion").textContent === KYC.byId(id).officeLabel);

    check("Escape closes the dialog", (() => {
      D.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return modal.hidden;
    })());
  });

  suite("index.html — contact & links", () => {
    const member = window.legislatorsData.find(
      (p) => !p.isCandidate && p.website && p.social && p.social.twitter &&
        p.committeeList && p.committeeList.length && (p.refs || {}).govtrack);
    check("a member with a site, accounts, committees and ids exists", !!member);
    if (member) {
      KYC.profile.open(member.id);
      const panel = D.getElementById("profileModalContactPanel");
      check("contact panel shows for a member", panel && !panel.hidden);
      const links = [...D.getElementById("profileModalContact").querySelectorAll("a")];
      check("official website is linked",
        links.some((a) => a.href === member.website || a.href === member.website + "/"));
      check("X account is linked from the handle",
        links.some((a) => a.href === "https://x.com/" + encodeURIComponent(member.social.twitter)));
      check("GovTrack is linked from the id, not the name",
        links.some((a) => a.href.endsWith("/congress/members/" + member.refs.govtrack)));
      check("every outbound link opens safely",
        links.filter((a) => /^https?:/.test(a.href))
          .every((a) => a.target === "_blank" && /noopener/.test(a.rel)));
      const committees = D.getElementById("profileModalCommittees");
      const table = KYC.meta().committees || {};
      check("committees come from the structured rosters",
        committees.querySelectorAll(".committee").length ===
          member.committeeList.filter((c) => !(table[c.code] || {}).parent).length);
      KYC.profile.close();
    }
    const runner = window.legislatorsData.find((p) => p.isCandidate && p.campaignSite);
    check("a candidate with a campaign site exists", !!runner);
    if (runner) {
      KYC.profile.open(runner.id);
      const links = [...D.getElementById("profileModalContact").querySelectorAll("a")];
      check("campaign website is linked",
        links.some((a) => a.href.replace(/\/$/, "") === runner.campaignSite.replace(/\/$/, "")));
      check("FEC filings are linked from the candidate id",
        links.some((a) => a.href === "https://www.fec.gov/data/candidate/" +
          encodeURIComponent(runner.fecCandidateId) + "/"));
      KYC.profile.close();
    }
    const hostile = { id: "X_TEST", name: "Test", website: 'https://example.com/"><img src=x onerror=alert(1)>',
      isCandidate: true, social: { twitter: '"><b>x' } };
    // The renderer only ever sees data through the escaper; push one bad row
    // through it and make sure nothing executes.
    window.legislatorsData.push(hostile);
    KYC.profile.open("X_TEST");
    const html = D.getElementById("profileModalContact").innerHTML;
    check("hostile URLs are escaped, not interpreted", !/<img/.test(html) && !/<b>/.test(html));
    KYC.profile.close();
    window.legislatorsData.pop();
  });

  suite("index.html — finance period in the dialog", () => {
    // KYC.byId indexes the profiles once, so borrow a real profile, give it
    // the fields under test, and put it back exactly as it was.
    const host = window.legislatorsData.find((p) => p.isCandidate && p.financeSource);
    const show = (fields) => {
      const saved = {};
      Object.keys(fields).forEach((k) => { saved[k] = host[k]; host[k] = fields[k]; });
      KYC.profile.open(host.id);
      const el = D.getElementById("profileModalFinancePeriod");
      const out = { hidden: el.hidden, text: el.textContent,
        footer: D.getElementById("profileModalSource").textContent };
      KYC.profile.close();
      Object.keys(saved).forEach((k) => {
        if (saved[k] === undefined) delete host[k]; else host[k] = saved[k];
      });
      return out;
    };
    check("a candidate with FEC money exists", !!host);
    const base = { chamber: "Senate (Candidate)", financeSource: "FEC",
      financePeriod: "election", financeElection: 2026, financeAsOf: "2026-06-30" };
    const withStart = show(Object.assign({ financeSince: "2025-01-01" }, base));
    check("the period shows under the money",
      !withStart.hidden && withStart.text === "Raised for the 2026 election, Jan 2025 – Jun 2026.",
      withStart.text);
    check("the footer names the election period", /2026 election period/.test(withStart.footer),
      withStart.footer);
    const without = show(Object.assign({ financeSince: null }, base));
    check("without a start date the period says only what is known",
      !without.hidden && without.text === "Raised for the 2026 election, through Jun 2026.",
      without.text);
    const hostile = show(Object.assign({ financeSince: "<img src=x onerror=alert(1)>" }, base));
    check("a hostile start date never reaches the markup",
      !/<img/.test(D.getElementById("profileModalFinancePeriod").innerHTML) &&
        !/img/.test(hostile.text), hostile.text);
    const none = show({ financeSource: undefined });
    check("no money, no period line", none.hidden && none.text === "");

    const real = window.legislatorsData.find((p) => p.financeSource && p.financeElection);
    check("built profiles carry the election period", !!real);
  });

  suite("index.html — gaps filled from a named source", () => {
    // kyc/enrich.py fills a filed candidate's empty fields from their
    // Wikipedia infobox and their campaign's own site. Borrow a real filed
    // candidate, give them the fields under test, put everything back.
    const host = window.legislatorsData.find((p) => p.source === "fec-field" && p.isCandidate);
    check("a filed candidate exists to test", !!host);
    if (!host) return;
    const fields = {
      platforms: "Healthcare; Lower costs, higher wages; Public schools",
      birthdate: "1980-01-02", age: 46, previous_professions: "molecular biologist",
      quality: {}, campaignSite: "https://example.org/", campaignSiteVia: "election-page",
      campaignIssuesUrl: "https://example.org/issues",
      campaignQuote: "Zyxwvut fights for <img src=x onerror=alert(1)> working families.",
      fieldSources: { platforms: "campaign-site", birthdate: "wikipedia",
        previous_professions: "election-page" },
    };
    const saved = {};
    Object.keys(fields).forEach((k) => { saved[k] = host[k]; host[k] = fields[k]; });
    delete host.__search;
    KYC.profile.open(host.id);

    const platform = D.getElementById("profileModalPlatform");
    const bullets = [...platform.querySelectorAll(".bullets li")].map((li) => li.textContent);
    check("the campaign's issue headings are split on semicolons, not commas",
      bullets.length === 3 && bullets[1] === "Lower costs, higher wages", bullets.join(" | "));
    check("its own description is quoted, and markup in it is never interpreted",
      !platform.querySelector("img") && /onerror=alert/.test(platform.textContent) &&
        !!platform.querySelector("blockquote.campaign-quote"));
    check("the platform says it came from the campaign's site",
      /Campaign site/.test(platform.textContent));
    const out = [...platform.querySelectorAll("a")];
    check("and links the issues page it was read from, safely",
      out.some((a) => a.href === "https://example.org/issues") &&
        out.every((a) => a.target === "_blank" && /noopener/.test(a.rel)));
    check("a birthdate read from Wikipedia says so",
      /Wikipedia/.test(D.getElementById("profileModalAge").textContent));
    const careers = D.getElementById("profileModalCareers");
    check("the election page's description of them is credited to it",
      /molecular biologist/.test(careers.textContent) &&
        /election page/.test((careers.querySelector(".field-source") || {}).title || ""));
    const chip = [...D.getElementById("profileModalContact").querySelectorAll("a")]
      .find((a) => a.href === "https://example.org/");
    check("a site from the election page does not claim to be an FEC filing",
      !!chip && /Wikipedia/.test(chip.title) && !/FEC/.test(chip.title), chip && chip.title);
    check("the campaign's own words are searchable",
      KYC.matchesQuery(host, "zyxwvut"));
    KYC.profile.close();

    // A quote and no list: the platform shows the quote, not "No data".
    host.platforms = "No data";
    host.quality = { platforms: "unknown" };
    host.fieldSources = {};
    KYC.profile.open(host.id);
    check("a campaign's description stands in for an empty platform",
      /Zyxwvut/.test(platform.textContent) && !/No data/.test(platform.textContent),
      platform.textContent);
    KYC.profile.close();

    Object.keys(saved).forEach((k) => {
      if (saved[k] === undefined) delete host[k]; else host[k] = saved[k];
    });
    delete host.__search;

    // A roster platform with commas inside its items (Edward Markey's).
    const markey = KYC.byId("M000133");
    if (markey) {
      KYC.profile.open(markey.id);
      const items = [...D.querySelectorAll("#profileModalPlatform .bullets li")].map((li) => li.textContent);
      check("an item with commas inside it stays one bullet",
        items.includes("Telecommunications, technology, and digital privacy") &&
          !items.some((t) => /^(and|or) /.test(t)), items.join(" | "));
      KYC.profile.close();
    }

    const quoted = window.legislatorsData.find((p) => p.campaignQuote);
    check("built profiles carry campaign descriptions", !!quoted);
    const pictured = window.legislatorsData.filter((p) => p.photoSource === "campaign-site");
    check("a portrait from a campaign site is only ever a filed candidate's",
      pictured.every((p) => p.source === "fec-field" && p.isCandidate),
      pictured.filter((p) => p.source !== "fec-field").map((p) => p.id).join(","));
  });

  suite("index.html — in this race", () => {
    // A member with challengers still on the ballot: the dialog lists them.
    const race = window.kycRaces.find((r) => r.incumbentIds.length && r.candidateCount > 1 && r.settled);
    check("a contested, settled race exists to test", !!race);
    if (race) {
      KYC.profile.open(race.incumbentIds[0]);
      const panel = D.getElementById("profileModalRacePanel");
      check("the race panel is shown", panel && !panel.hidden);
      check("it is titled with the race", D.getElementById("profileModalRaceTitle").textContent === race.label);
      const rows = [...D.querySelectorAll("#profileModalRace .race-mate")];
      const everyone = race.incumbentIds.concat(race.candidateIds).filter((id) => id !== race.incumbentIds[0]);
      check("every other person in the race is listed", rows.length === everyone.length,
        `${rows.length} of ${everyone.length}`);
      const onBallot = [...D.querySelectorAll("#profileModalRace > .race-mate")];
      check("people still on the ballot come first, the rest are folded",
        onBallot.every((r) => !KYC.cards.offBallot(KYC.byId(r.getAttribute("data-goto")))));
      const first = rows[0];
      first.click();
      check("clicking a race-mate opens their profile",
        D.getElementById("profileModalName").textContent === KYC.byId(first.getAttribute("data-goto")).name);
      KYC.profile.close();
    }
  });

  suite("index.html — a nominee's November ballot line", () => {
    // NY-15: Jose Vega lost the Democratic primary and is on the "Speak The
    // Truth" line; without the line he read as a second Democratic nominee.
    // A real nominee in a race with a member stands in, given a hostile line.
    const race = window.kycRaces.find((r) => r.incumbentIds.length &&
      r.candidateIds.some((id) => (KYC.byId(id) || {}).raceStatus === "nominee"));
    check("a race with a challenger nominee exists to test", !!race);
    if (!race) return;
    const nominee = KYC.byId(race.candidateIds.find((id) => KYC.byId(id).raceStatus === "nominee"));
    const plain = KYC.cards.raceBadge(nominee);
    check("a nominee with no ballotLine shows no line", !/ line</.test(plain), plain);
    nominee.ballotLine = 'Speak <b>The</b> "Truth"';
    try {
      const badge = KYC.cards.raceBadge(nominee);
      check("the card badge names the line",
        badge.indexOf("On the November ballot – Speak &lt;b&gt;The&lt;/b&gt; &quot;Truth&quot; line") !== -1,
        badge);
      check("the card badge's title does not claim a primary win", !/Won the primary/.test(badge));
      KYC.profile.open(nominee.id);
      const status = D.getElementById("profileModalStatus");
      check("the profile status line names the line",
        status.textContent.indexOf('On the November ballot – Speak <b>The</b> "Truth" line') !== -1,
        status.textContent);
      check("the line is escaped, never markup", !status.querySelector("b"));
      KYC.profile.close();
      KYC.profile.open(race.incumbentIds[0]);
      const row = D.querySelector('#profileModalRace .race-mate[data-goto="' + nominee.id + '"]');
      check("'In this race' names the line",
        !!row && row.textContent.indexOf('On the ballot – Speak <b>The</b> "Truth" line') !== -1,
        row && row.textContent);
      check("and escapes it", !!row && !row.querySelector(".race-mate-meta b"));
      KYC.profile.close();
      nominee.raceStatus = "eliminated";
      check("only a nominee's line is shown", !/Truth/.test(KYC.cards.raceBadge(nominee)));
    } finally {
      nominee.raceStatus = "nominee";
      delete nominee.ballotLine;
    }
  });

  suite("index.html — search suggestions and remembered state", () => {
    const search = D.getElementById("searchInput");
    search.dispatchEvent(new window.Event("focus"));
    const list = D.getElementById("kycNames");
    check("focusing search builds the name list once", !!list && list.options.length > 500,
      list ? `${list.options.length} names` : "no list");
    check("the input points at it", search.getAttribute("list") === "kycNames");
    check("an off-ballot filer is not suggested", (() => {
      const out = window.legislatorsData.find((p) => p.isCandidate && p.raceStatus === "eliminated");
      return out && ![...list.options].some((o) => o.value === out.name);
    })());
    D.getElementById("stateSelect").value = "TX";
    D.getElementById("stateSelect").dispatchEvent(new window.Event("change"));
    const slot = D.getElementById("yourState");
    check("filtering by a state remembers it in the sidebar",
      slot && !slot.hidden && /Texas/.test(slot.textContent), slot && slot.textContent);
    check("and links to its page", /states\/tx\.html$/.test(slot.querySelector("a").getAttribute("href")));
    D.getElementById("stateSelect").value = "all";
    D.getElementById("stateSelect").dispatchEvent(new window.Event("change"));
  });

  suite("index.html — members are found by the names voters use", () => {
    // The roster holds legal names: 56 sitting members could not be found
    // as "Jim Clyburn" or "Hank Johnson", accented queries missed unaccented
    // names, and five displayed as "C. Franklin"-style initials.
    const byId = (id) => window.legislatorsData.find((p) => p.id === id);
    const finds = (id, q) => KYC.matchesQuery(byId(id), q.toLowerCase());
    check("'Jim Clyburn' finds James Clyburn", finds("C000537", "Jim Clyburn"));
    check("'Hank Johnson' finds Henry Johnson", finds("J000288", "Hank Johnson"));
    check("'Chuy Garcia' finds him without the accent", finds("G000586", "Chuy Garcia"));
    check("'Mario Díaz-Balart' finds the unaccented name", finds("D000600", "Mario Díaz-Balart"));
    check("'Diaz-Balart' still finds it", finds("D000600", "Diaz-Balart"));
    check("an alias does not match everyone",
      window.legislatorsData.filter((p) => KYC.matchesQuery(p, "jim clyburn")).length === 1);
    check("folding is exposed and total", KYC.foldText("JESÚS") === "jesus" && KYC.foldText(null) === "");

    const franklin = byId("F000472");
    check("an initial-first roster name displays as the name he goes by",
      franklin.name === "Scott Franklin", franklin.name);
    check("the roster spelling stays searchable", finds("F000472", "C. Franklin"));
    const list = D.getElementById("kycNames");
    const option = [...list.options].find((o) => o.value === "James Clyburn");
    check("suggestions keep the display name and carry the alias as a label",
      !!option && /Jim Clyburn/.test(option.getAttribute("label") || ""),
      option && option.getAttribute("label"));
    check("the initial-first roster spelling is not suggested; the display name is",
      ![...list.options].some((o) => o.value === "C. Franklin") &&
      [...list.options].some((o) => o.value === "Scott Franklin"));
  });

  suite("index.html — alias search through the directory", () => {
    window.location.hash = "#/?q=" + encodeURIComponent("Jim Clyburn");
    window.dispatchEvent(new window.Event("hashchange"));
    const ids = [...D.getElementById("results").querySelectorAll(".card")]
      .map((c) => c.getAttribute("data-id"));
    check("a 'Jim Clyburn' search shows his card, and only his", ids.length === 1 && ids[0] === "C000537",
      ids.slice(0, 5).join(","));
    const card = D.querySelector('#results .card[data-id="C000537"]');
    check("and the card shows the display name", !!card && /James Clyburn/.test(card.textContent));
    window.location.hash = "#/";
    window.dispatchEvent(new window.Event("hashchange"));
  });

  suite("index.html — the map's old bug, checked on both pages", () => {
    // map.html rendered `item.net_worth` with textContent, so a profile with
    // no filing showed the literal placeholder sentence as if it were data.
    const withPlaceholder = window.legislatorsData.find(
      (p) => (p.quality || {}).net_worth === "not_disclosed");
    check("a profile with no net-worth filing exists to test", !!withPlaceholder);
    if (withPlaceholder) {
      KYC.profile.open(withPlaceholder.id);
      const shown = D.getElementById("profileModalWorth").textContent;
      check("no placeholder prose reaches the reader",
        !/No net worth disclosure|N\/A \(/.test(shown), shown);
      check("it reads as an absence instead", /Not disclosed/.test(shown), shown);
      KYC.profile.close();
    }
  });

  suite("index.html — deep links", () => {
    const target = window.legislatorsData[42];
    window.location.hash = "#/profile/" + encodeURIComponent(target.id);
    window.dispatchEvent(new window.Event("hashchange"));
    check("a profile URL opens that profile",
      D.getElementById("profileModalName").textContent === target.name);

    window.location.hash = "#/?state=TX&chamber=Senate";
    window.dispatchEvent(new window.Event("hashchange"));
    const shown = [...D.getElementById("results").querySelectorAll(".card")];
    check("a filter URL restores the filters", shown.length > 0 && shown.length < 20,
      `${shown.length} cards`);
    check("restored filters are correct",
      shown.every((c) => {
        const item = KYC.byId(c.getAttribute("data-id"));
        return item.state === "TX" && item.chamber.includes("Senate");
      }));
    check("the state select follows the URL",
      D.getElementById("stateSelect").value === "TX");
  });
}

/* ================================================================ map.html */

async function testMap() {
  const { window, D, KYC } = await testShared("map.html");

  suite("map.html — geometry", () => {
    check("geometry loaded from the build", !!window.kycGeo &&
      Object.keys(window.kycGeo.states).length === 51,
      `${Object.keys(window.kycGeo || { states: {} }).length && Object.keys(window.kycGeo.states).length} states`);
    const shapes = D.querySelectorAll("#usMap .state");
    check("every state and territory is drawn", shapes.length === 57, `${shapes.length} shapes`);
    check("no path is empty",
      [...shapes].every((s) => (s.getAttribute("d") || "").length > 20));
    check("states are keyboard reachable",
      [...shapes].every((s) => s.getAttribute("tabindex") === "0"));
    check("states expose a role and a label",
      [...shapes].every((s) => s.getAttribute("role") === "button" && s.getAttribute("aria-label")));
    check("state labels drawn", D.querySelectorAll("#usMap .state-label").length >= 51);
  });

  suite("map.html — modes", () => {
    const senateFill = D.querySelector('[data-state="TX"]').style.fill;
    check("Senate mode fills states", !!senateFill, senateFill);

    D.querySelector('[data-mode="house"]').click();
    check("House mode blends by delegation share",
      /color-mix/.test(D.querySelector('[data-state="TX"]').style.fill),
      D.querySelector('[data-state="TX"]').style.fill);
    check("legend follows the mode", /All R/.test(D.getElementById("mapLegend").textContent));

    D.querySelector('[data-mode="senate2026"]').click();
    check("2026 mode marks a state with no race", (() => {
      // 65 senators' terms run past 2026, so plenty of states have no race.
      const none = [...D.querySelectorAll("#usMap .state")]
        .find((s) => /no Senate race/.test(s.getAttribute("aria-label") || ""));
      return !!none;
    })());
    check("mode buttons announce their state",
      D.querySelector('[data-mode="senate2026"]').getAttribute("aria-pressed") === "true");
    D.querySelector('[data-mode="senate"]').click();
  });

  suite("map.html — delegation panel", () => {
    D.querySelector('[data-state="TX"]').dispatchEvent(
      new window.MouseEvent("click", { bubbles: true }));
    check("selecting a state names it",
      D.getElementById("panelState").textContent === "Texas",
      D.getElementById("panelState").textContent);
    const rows = D.querySelectorAll("#delegation .person-row");
    check("Texas shows two senators", rows.length === 2, `${rows.length} rows`);
    check("selection is announced",
      D.querySelector('[data-state="TX"]').getAttribute("aria-pressed") === "true");
    check("rows are buttons", [...rows].every((r) => r.tagName === "BUTTON"));
    check("no inline handlers", D.querySelectorAll("[onclick],[onerror]").length === 0);

    D.querySelector('[data-mode="house"]').click();
    check("House mode lists the whole delegation",
      D.querySelectorAll("#delegation .person-row").length > 20,
      `${D.querySelectorAll("#delegation .person-row").length} rows`);
  });

  suite("map.html — the delegation panel leads with who holds the seat", () => {
    // Texas has 37 representatives and 191 filed challengers; listing all 228
    // buries the delegation the reader clicked the state to see.
    D.querySelector('[data-mode="house"]').click();
    D.querySelector('[data-state="TX"]').dispatchEvent(
      new window.MouseEvent("click", { bubbles: true }));

    const visible = () => [...D.querySelectorAll("#delegation .person-row")]
      .filter((row) => !row.closest("[hidden]")).length;
    const seated = visible();
    check("only seated members show at first", seated > 0 && seated < 60,
      `${seated} rows`);
    check("every visible row is a sitting member",
      [...D.querySelectorAll("#delegation .person-row")]
        .filter((r) => !r.closest("[hidden]"))
        .every((r) => !KYC.byId(r.getAttribute("data-id")).isCandidate));

    const toggle = D.getElementById("showChallengers");
    check("challengers are behind a labelled expander", !!toggle &&
      /challenger/i.test(toggle.textContent), toggle && toggle.textContent.trim());
    check("the expander reports its state",
      toggle.getAttribute("aria-expanded") === "false");
    toggle.click();
    check("expanding reveals them", visible() > seated, `${visible()} rows`);
    check("and updates aria-expanded",
      toggle.getAttribute("aria-expanded") === "true");

    D.querySelector('[data-mode="senate"]').click();
  });

  suite("map.html — keyboard and picker", () => {
    const picker = D.getElementById("mapStateSelect");
    check("a state picker exists for non-visual use", !!picker && picker.options.length > 50);
    picker.value = "WY";
    picker.dispatchEvent(new window.Event("change"));
    check("the picker selects a state",
      D.getElementById("panelState").textContent === "Wyoming",
      D.getElementById("panelState").textContent);

    const ca = D.querySelector('[data-state="CA"]');
    ca.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    check("Enter selects a state from the keyboard",
      D.getElementById("panelState").textContent === "California",
      D.getElementById("panelState").textContent);
  });

  suite("map.html — every view has a URL", () => {
    const picker = D.getElementById("mapStateSelect");
    picker.value = "TX";
    picker.dispatchEvent(new window.Event("change"));
    check("selecting a state writes it to the URL", /state=TX/.test(window.location.hash),
      window.location.hash);
    const houseButton = D.querySelector('[data-mode="house"]');
    if (houseButton) {
      houseButton.click();
      check("the mode is in the URL too", /mode=house/.test(window.location.hash),
        window.location.hash);
    }
    window.location.hash = "#/?state=AK&mode=senate2026";
    window.dispatchEvent(new window.Event("hashchange"));
    check("a pasted URL restores the state", D.getElementById("panelState").textContent === "Alaska",
      D.getElementById("panelState").textContent);
    check("and the mode", D.querySelector('[data-mode="senate2026"]').getAttribute("aria-pressed") === "true");
  });

  suite("map.html — the shared dialog", () => {
    // The map had its own copy of the dialog with no focus trap at all.
    D.querySelector('[data-state="TX"]').dispatchEvent(
      new window.MouseEvent("click", { bubbles: true }));
    const row = D.querySelector("#delegation .person-row");
    row.click();
    const modal = D.getElementById("profileModal");
    check("map opens the same dialog as the grid", modal && !modal.hidden);
    check("dialog uses renderField for net worth", (() => {
      const item = KYC.byId(row.getAttribute("data-id"));
      const shown = D.getElementById("profileModalWorth").innerHTML;
      return (item.quality || {}).net_worth
        ? /kyc-absent|kyc-generic/.test(shown)
        : shown.length > 0;
    })());
    check("Escape closes it", (() => {
      D.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return modal.hidden;
    })());
  });
}

/* ============================================================ state pages */

async function testStates() {
  const { window, D, KYC } = await testShared("states/tx.html");

  suite("states/tx.html — one state's page", () => {
    const content = D.getElementById("stateContent");
    check("the page is about Texas", /Texas/.test(D.querySelector(".state-title").textContent));
    check("the document title names the state", /^Texas/.test(D.title), D.title);
    const members = window.legislatorsData.filter((p) => !p.isCandidate && p.state === "TX");
    const senators = members.filter((p) => /Senate/.test(p.chamber));
    const heads = [...content.querySelectorAll(".state-heading")];
    check("senators come first", /senators/i.test(heads[0].textContent), heads[0].textContent);
    const grids = [...content.querySelectorAll(".state-section > .card-grid")];
    check("both senators are shown", grids[0].querySelectorAll(".card").length === senators.length);
    check("the whole delegation is shown",
      grids[1].querySelectorAll(".card").length === members.length - senators.length,
      `${grids[1].querySelectorAll(".card").length} of ${members.length - senators.length}`);
    check("the delegation is in district order", (() => {
      const nums = [...grids[1].querySelectorAll(".card")]
        .map((c) => KYC.districtOrder(KYC.byId(c.getAttribute("data-id"))));
      return nums.every((n, i) => i === 0 || n >= nums[i - 1]);
    })());
    const txRaces = window.kycRaces.filter((r) => r.state === "TX");
    const sections = [...content.querySelectorAll("section.race")];
    check("every Texas race has a section", sections.length === txRaces.length,
      `${sections.length} of ${txRaces.length}`);
    check("races are in ballot order: Senate, then districts", (() => {
      const titles = sections.map((s) => s.querySelector(".race-title").textContent.trim());
      const nums = titles.map((t) => (t.match(/District (\d+)/) || [0, 0])[1]).map(Number);
      return /Senate/.test(titles[0]) && nums.slice(1).every((n, i) => i === 0 || n >= nums[i]);
    })());
    check("race sections carry no self-link to the state",
      !content.querySelector(".race-state-link"));
    check("the map link uses the route the map understands", (() => {
      const a = [...content.querySelectorAll(".state-links a")].find((x) => /map\.html/.test(x.getAttribute("href")));
      return a && /map\.html#\/\?state=TX$/.test(a.getAttribute("href"));
    })());
    check("nothing under the page is unescaped markup from the data",
      !/<script/i.test(content.innerHTML));
    const first = content.querySelector(".card");
    first.click();
    check("a card opens the shared dialog",
      !D.getElementById("profileModal").hidden &&
      D.getElementById("profileModalName").textContent === KYC.byId(first.getAttribute("data-id")).name);
    check("the dialog links back to the state page", (() => {
      const a = D.getElementById("profileModalStateLink");
      return a && !a.hidden && /tx\.html$/.test(a.getAttribute("href"));
    })());
    KYC.profile.close();
    const jump = D.getElementById("stateJump");
    check("the jump list names every state", jump.options.length > 50, `${jump.options.length}`);
    check("the jump list has Texas selected", jump.value === "TX");
    check("search narrows the cards", (() => {
      const input = D.getElementById("stateSearch");
      input.value = "zzzz-no-such-person";
      input.dispatchEvent(new window.Event("input", { bubbles: true }));
      return true; // debounced; asserted below after a tick
    })());
  });

  await new Promise((r) => setTimeout(r, 200));
  suite("states/tx.html — search (after debounce)", () => {
    const cards = [...D.querySelectorAll("#stateContent .card")];
    check("no card matches nonsense", cards.every((c) => c.hidden), `${cards.filter((c) => !c.hidden).length} shown`);
  });

  const index = await testShared("states/index.html");
  suite("states/index.html — the directory of states", () => {
    const rows = [...index.D.querySelectorAll(".state-row")];
    const states = Object.keys(index.KYC.meta().states || {});
    check("one row per state and territory", rows.length === states.length,
      `${rows.length} of ${states.length}`);
    check("every row links to a page that exists", rows.every((r) => {
      const href = r.getAttribute("href");
      return fs.existsSync(path.join(SITE, "states", href));
    }));
    check("rows are alphabetical by name", (() => {
      const names = rows.map((r) => r.querySelector(".state-row-name").textContent.trim());
      return names.every((n, i) => i === 0 || n.localeCompare(names[i - 1]) >= 0);
    })());
    check("Texas is one of them", rows.some((r) => r.getAttribute("data-state") === "TX"));
  });

  suite("state pages — every generated page is wired", () => {
    const files = fs.readdirSync(path.join(SITE, "states")).filter((f) => f.endsWith(".html"));
    check("57 pages: 50 states, DC and 5 territories, plus the index",
      files.length === 57, `${files.length}`);
    const bad = files.filter((f) => {
      const raw = fs.readFileSync(path.join(SITE, "states", f), "utf8");
      return !/<link rel="canonical" href="https:\/\/[^"]+\/states\/[a-z]+\.html">/.test(raw) ||
        !/data-root="\.\.\/"/.test(raw);
    });
    check("each has a canonical URL and declares its depth", bad.length === 0, bad.join(", "));
    const sitemap = fs.readFileSync(path.join(SITE, "sitemap.xml"), "utf8");
    check("the sitemap lists every state page",
      files.filter((f) => f !== "index.html").every((f) => sitemap.includes("/states/" + f)));
  });
}

/* ============================================================ deep links */

const settle = (ms) => new Promise((r) => setTimeout(r, ms || 150));

/* A link someone was sent is the first page they see. Landing on
 * #/profile/<id> used to leave the grid behind the dialog at "Loading
 * profiles..." with no cards, and closing it called history.back() - which,
 * with nothing of ours behind it, left the site. The map overwrote its
 * incoming hash at boot, so state and profile links opened a blank map. */
async function testDeepLinks() {
  const probe = await buildPage("index.html");
  const people = probe.window.legislatorsData;
  const senator = people.find((p) => p.state === "TX" && /Senate/.test(p.chamber) && !p.isCandidate);
  probe.window.close();

  for (const page of ["index.html", "map.html", "states/tx.html"]) {
    const { window, D, errors } = await buildPage(page, { hash: "#/profile/" + senator.id });
    await settle();
    const modal = D.getElementById("profileModal");
    suite(`${page} — landing on a shared profile link`, () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      check("the profile opens", modal && !modal.hidden &&
        D.getElementById("profileModalName").textContent === senator.name,
        D.getElementById("profileModalName") && D.getElementById("profileModalName").textContent);
      check("the address still names the profile",
        window.location.hash === "#/profile/" + senator.id, window.location.hash);
      if (page === "index.html") {
        check("the grid is drawn underneath", announced(D) > 0 &&
          D.querySelectorAll("#results .card").length > 0,
          D.getElementById("resultsLabel").textContent.trim());
      }
      if (page === "map.html") {
        check("the map shows that person's state underneath",
          /Texas|TX/.test(D.getElementById("panelState").textContent),
          D.getElementById("panelState").textContent);
      }
    });

    D.querySelector("#profileModal .modal-footer [data-close]").click();
    await settle();
    suite(`${page} — closing a profile someone landed on`, () => {
      check("the dialog closes", modal.hidden);
      check("does not go back off the site", window.__backCalls === 0, `${window.__backCalls} back()`);
      check("the address becomes the list", !/profile/.test(window.location.hash),
        window.location.hash);
      if (page === "index.html") {
        check("the grid is still there", D.querySelectorAll("#results .card").length > 0);
      }
      if (page === "map.html") {
        check("the list address keeps the state", /state=TX/.test(window.location.hash),
          window.location.hash);
      }
    });

    // Opened in the page, closing still goes back: the entry is ours.
    const before = window.location.hash;
    window.KYC.profile.open(senator.id);
    await settle(50);
    const pushed = window.location.hash;
    D.querySelector("#profileModal .modal-footer [data-close]").click();
    await settle();
    suite(`${page} — closing a profile opened in the page`, () => {
      check("opening pushes the profile address", pushed === "#/profile/" + senator.id, pushed);
      check("closing goes back once", window.__backCalls === 1, `${window.__backCalls} back()`);
      check("back to where the reader was", window.location.hash === before,
        `${window.location.hash} vs ${before}`);
    });
    window.close();
  }

  const cases = [
    ["#/?state=TX", "TX", "senate"],
    ["#/?state=TX&mode=house", "TX", "house"],
    ["#/?state=OR&mode=house", "OR", "house"],
  ];
  for (const [hash, code, mode] of cases) {
    const { window, D, errors } = await buildPage("map.html", { hash });
    await settle(50);
    suite(`map.html${hash} — the incoming route survives boot`, () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      check("the address is not rewritten", window.location.hash === hash, window.location.hash);
      check(`${code} is selected`, D.getElementById("mapStateSelect").value === code,
        D.getElementById("mapStateSelect").value);
      check(`the ${mode} view is on`,
        D.querySelector(`[data-mode="${mode}"]`).getAttribute("aria-pressed") === "true");
    });
    window.close();
  }

  // The link every state page carries to the map lands on that state.
  {
    const { window, D } = await buildPage("states/tx.html");
    const link = [...D.querySelectorAll("a[href*='map.html']")].map((a) => a.getAttribute("href"))
      .find((h) => /#/.test(h));
    window.close();
    const hash = link ? link.slice(link.indexOf("#")) : "";
    const map = await buildPage("map.html", { hash });
    await settle(50);
    suite("states/tx.html — its map link", () => {
      check("the state page links to the map at its state", /state=TX/.test(hash), link);
      check("which opens on Texas", map.D.getElementById("mapStateSelect").value === "TX",
        map.D.getElementById("mapStateSelect").value);
    });
    map.window.close();
  }
}

/* ====================================================== running elsewhere */

/* A member contesting another seat has a primary result for the seat they
 * hold - usually "unlisted", because they are not running for it - and one
 * for the race they are in, on their filing's profile. The page showed the
 * first: Ashley Hinson, Iowa's Republican Senate nominee, read "Not on the
 * 2026 ballot - not seeking re-election". */
async function testRunningElsewhere() {
  const { window, D } = await buildPage("index.html");
  const KYC = window.KYC;
  const people = window.legislatorsData;
  const movers = people.filter((p) => KYC.runsElsewhere(p) && p.contestLabel &&
    p.raceStatusRace && p.raceStatusRace !== p.contestRaceId);
  const filingOf = (p) => KYC.byId(p.alsoRunningId);
  const decided = movers.filter((p) => filingOf(p) && filingOf(p).raceId === p.contestRaceId &&
    filingOf(p).raceStatus);
  const nominees = decided.filter((p) => filingOf(p).raceStatus === "nominee");
  const losers = decided.filter((p) => filingOf(p).raceStatus === "eliminated");

  const profileStatus = (p) => {
    KYC.profile.open(p.id, { fromRoute: true });
    const text = D.getElementById("profileModalStatus").textContent;
    KYC.profile.close();
    return text;
  };

  suite("members running for another seat — their race, not their seat", () => {
    check("the data has members whose held-seat result differs from their race",
      decided.length > 0 && nominees.length > 0, `${decided.length} decided, ${nominees.length} nominees`);
    check("every one shows the result of the race they are in",
      decided.every((p) => KYC.contestStatus(p) === filingOf(p).raceStatus),
      decided.filter((p) => KYC.contestStatus(p) !== filingOf(p).raceStatus).map((p) => p.name).join(", "));

    const badProfiles = decided.filter((p) => {
      const t = profileStatus(p);
      return /not seeking re-election|Not on the 2026 ballot|Renominated/i.test(t) ||
        !t.includes(p.contestLabel);
    });
    check("no profile calls them off the ballot or renominated", badProfiles.length === 0,
      badProfiles.map((p) => p.name + ": " + profileStatus(p)).join(" | "));
    check("a nominee's profile says which November ballot",
      nominees.every((p) => profileStatus(p).includes("On the November ballot for " + p.contestLabel)),
      nominees.length ? profileStatus(nominees[0]) : "");
    check("a loser's profile says which primary",
      losers.every((p) => profileStatus(p).includes("Lost the 2026 primary for " + p.contestLabel)),
      losers.length ? profileStatus(losers[0]) : "none in the data");

    // The card carries the filing's own badge. A filing that is itself
    // unlisted in its race says so; the held seat's absence never shows.
    const FILING_BADGE = { nominee: /On the November ballot/, eliminated: /Lost primary/,
      withdrawn: /Withdrew/, advanced: /In runoff/, unlisted: /Not on primary ballot/ };
    const badCards = decided.filter((p) => {
      const html = KYC.cards.statusBadge(p);
      return /Not on the ballot|Renominated/.test(html) ||
        !FILING_BADGE[filingOf(p).raceStatus].test(html) ||
        (filingOf(p).raceStatus !== "unlisted" && /Not on primary ballot/.test(html));
    });
    check("each card shows the result of their race, not their seat", badCards.length === 0,
      badCards.map((p) => p.name + ": " + KYC.cards.statusBadge(p)).join(" | "));

    // Someone with no filing in their race shows no result, never the seat's.
    const undecided = movers.filter((p) => !decided.includes(p));
    check("with no result for their race, nothing is borrowed from the seat",
      undecided.every((p) => KYC.contestStatus(p) === "" ||
        (filingOf(p) && filingOf(p).raceId === p.contestRaceId)));
  });

  /* "Nobody else has filed for this seat" was printed whenever no other
   * profile was in the race - for Hank Johnson with five filings and a named
   * November opponent. It may say so only when filedCount does. */
  suite("in this race — alone among the profiles", () => {
    const raceOf = (p) => window.kycRaces.find((r) => r.id === (p.contestRaceId || p.raceId));
    const alone = people.filter((p) => {
      const r = raceOf(p);
      return r && !r.incumbentIds.concat(r.candidateIds).some((id) => id !== p.id && KYC.byId(id));
    });
    const panelText = (p) => {
      KYC.profile.open(p.id, { fromRoute: true });
      const t = D.getElementById("profileModalRace").textContent;
      KYC.profile.close();
      return t;
    };
    check("the data has people alone among the profiles in their race", alone.length > 0,
      `${alone.length}`);
    const lies = alone.filter((p) => /Nobody else has filed/.test(panelText(p)) && raceOf(p).filedCount > 0);
    check("never 'nobody else has filed' when people have filed", lies.length === 0,
      lies.map((p) => `${p.name} (${raceOf(p).filedCount} filed)`).join(", "));
    const named = alone.filter((p) => ((raceOf(p).results || {}).otherNominees || []).length);
    check("a named November opponent without a profile is listed",
      named.length > 0 && named.every((p) => raceOf(p).results.otherNominees.every((n) => panelText(p).includes(n))),
      named.length ? panelText(named[0]) : "none in the data");
    const filedOnly = alone.find((p) => !raceOf(p).settled && raceOf(p).filedCount > 0);
    check("an unsettled race says how many filed",
      !filedOnly || panelText(filedOnly).includes(raceOf(filedOnly).filedCount + " ha"),
      filedOnly ? panelText(filedOnly) : "none in the data");
    const none = alone.find((p) => !raceOf(p).filedCount && !(raceOf(p).settled && raceOf(p).results));
    check("nobody filed is said only when nobody did",
      !none || /Nobody else has filed/.test(panelText(none)), none ? panelText(none) : "none in the data");
  });
  window.close();

  const map = await buildPage("map.html");
  await settle(50);
  const nominee = nominees[0];
  if (nominee) {
    map.D.querySelector('[data-mode="house"]').click();
    const picker = map.D.getElementById("mapStateSelect");
    picker.value = nominee.state;
    picker.dispatchEvent(new map.window.Event("change"));
    const row = map.D.querySelector(`#delegation [data-id="${nominee.id}"]`);
    suite("map.html — a member running for another seat", () => {
      check(`${nominee.name}'s row is in the ${nominee.state} delegation`, !!row);
      check("the row carries the result of their race",
        row && /Running for/.test(row.textContent) && /Nominee/.test(row.textContent) &&
          !/Not on ballot/.test(row.textContent),
        row && row.textContent.replace(/\s+/g, " ").trim());
    });
  }
  map.window.close();
}

/* ============================================================== contrast */

/* WCAG AA for text is 4.5:1. --text-faint labels fields, footers and every
 * absence, and was 3.4-4.3:1; the profile's party tag put near-black on the
 * light theme's dark party colours at 2.6-3.0:1. Checked from the tokens
 * themselves, so a new value cannot quietly regress. */
function testContrast() {
  const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
  const block = (sel) => {
    const i = css.indexOf(sel + " {");
    const out = {};
    for (const m of css.slice(i, css.indexOf("\n}", i)).matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
      out[m[1]] = m[2];
    }
    return out;
  };
  const base = block(":root");
  const themes = {
    dark: base,
    amoled: Object.assign({}, base, block('[data-theme="amoled"]')),
    light: Object.assign({}, base, block('[data-theme="light"]')),
  };
  const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const lum = (h) => {
    const c = rgb(h).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };

  suite("kyc.css — text contrast (WCAG AA, 4.5:1)", () => {
    for (const [name, t] of Object.entries(themes)) {
      const faint = ["surface-0", "surface-1", "surface-2"].map((s) => ratio(t["text-faint"], t[s]));
      check(`${name}: faint text on surfaces 0-2`, faint.every((r) => r >= 4.5),
        faint.map((r) => r.toFixed(2)).join(" / "));
      const tags = ["party-d", "party-r", "party-i", "text-muted"].map((p) => ratio(t["text-inverse"], t[p]));
      check(`${name}: party tag label on its party colour`, tags.every((r) => r >= 4.5),
        tags.map((r) => r.toFixed(2)).join(" / "));
    }
    const js = fs.readFileSync(path.join(SITE, "assets", "kyc-profile.js"), "utf8");
    check("the party tag's label colour comes from the theme, not a literal",
      !/style\.color\s*=\s*["']#/.test(js) && /\.party-tag\s*\{[^}]*color:\s*var\(--text-inverse\)/.test(css));
  });
}

/* ================================================================== report */

/* ============================================================ senate view */

/* The Senate by the year each seat is next decided. Every expected number
 * here is computed from the data the page loaded, never typed in. */
async function testSenate() {
  const { window, D, errors } = await buildPage("index.html", { hash: "#/?view=senate" });
  await settle(50);
  const KYC = window.KYC;
  const people = window.legislatorsData;
  const races = window.kycRaces;
  const results = D.getElementById("results");
  const toggle = D.getElementById("senateViewToggle");
  const senators = people.filter((p) => !p.isCandidate && /Senate/.test(p.chamber));
  const year = window.kycBuildMeta.election.year;
  const ids = (root) => [...root.querySelectorAll(".card")].map((c) => c.getAttribute("data-id"));
  const offBallot = (p) => !!KYC.cards.OFF_BALLOT[KYC.contestStatus(p)];
  const seatOf = (race) => {
    const head = race && D.getElementById("senate-seat-" + race.id);
    return head && head.closest("section");
  };

  suite("index.html — Senate view", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("#/?view=senate lands on the Senate view",
      results.querySelectorAll("section.senate-group").length > 0);
    check("the toggle is a button announced as pressed",
      toggle.tagName === "BUTTON" && toggle.getAttribute("aria-pressed") === "true");
    check("every sitting senator has a class and a next election",
      senators.every((p) => [1, 2, 3].includes(p.senateClass) && p.nextElection));

    const groups = [...results.querySelectorAll(":scope > section.senate-group")];
    const titles = groups.map((g) => g.querySelector(":scope > .senate-group-title").textContent);
    const years = [...new Set(senators.map((p) => p.nextElection))].sort();
    check("one top-level group per year, in order",
      groups.length === years.length &&
      years.every((y, i) => titles[i].indexOf("Up in " + y) === 0), titles.join(" | "));
    check("group headings are real headings", groups.every((g) =>
      g.querySelector(":scope > .senate-group-title").tagName === "H2"));

    const regular = (y) => senators.filter((p) => p.nextElection === y && !p.senateSpecial);
    check("each group's count is its senators in the data", groups.every((g, i) => {
      const n = regular(years[i]).length;
      return g.getAttribute("data-seats") === String(n) &&
        g.querySelector(".senate-count").textContent.indexOf(n + " seat") === 0;
    }), groups.map((g) => g.getAttribute("data-seats")).join(","));
    check("each group names its class", groups.every((g, i) => {
      const cls = regular(years[i])[0].senateClass;
      return titles[i].indexOf("Class " + ["", "I", "II", "III"][cls]) !== -1;
    }), titles.join(" | "));

    const specials = senators.filter((p) => p.senateSpecial);
    const sub = results.querySelector(".senate-group-special");
    const subTitle = sub ? sub.querySelector(".senate-group-title") : null;
    check("the specials are a labelled sub-group inside their year",
      !specials.length || (!!sub && sub.parentElement === groups[0] &&
        subTitle.tagName === "H3" && /special elections/.test(subTitle.textContent) &&
        sub.getAttribute("data-seats") === String(specials.length)),
      subTitle ? subTitle.textContent : "no sub-group");
    check("the specials come after the year's regular seats", !sub ||
      groups[0].lastElementChild === sub);

    const later = groups.slice(1);
    check("later years list their senators", later.every((g, i) => {
      const shown = ids(g);
      const expected = regular(years[i + 1]).map((p) => p.id);
      return shown.length === expected.length && expected.every((id) => shown.includes(id));
    }));

    // A 2026 seat: the holder, then the people running for it.
    const upRaces = races.filter((r) => r.chamber === "Senate" && r.year === year);
    const blocks = upRaces.map(seatOf);
    check("every 2026 Senate race has a seat block", blocks.every(Boolean),
      `${blocks.filter(Boolean).length} of ${upRaces.length}`);
    check("each seat block leads with its sitting senator",
      upRaces.every((r, i) => !blocks[i] || ids(blocks[i])[0] === r.incumbentIds[0]));
    const race = upRaces.find((r) => r.candidateIds.some((id) => !offBallot(KYC.byId(id))));
    const block = seatOf(race);
    const running = race ? race.candidateIds.map(KYC.byId).filter((p) => !offBallot(p)) : [];
    check("a 2026 seat lists its race's candidates after the incumbent", !!block &&
      running.length > 0 && running.every((p) => ids(block).indexOf(p.id) > 0 ||
        (p.incumbentId && ids(block).indexOf(p.incumbentId) > 0)),
      race ? race.id : "no race");
    check("and labels them as running for this seat",
      !!block && /Running for this seat/.test(block.textContent));
    const ranks = (b) => ids(b).slice(1).map((id) => {
      const st = KYC.contestStatus(KYC.byId(id));
      return st === "nominee" ? 0 : st === "advanced" ? 1 : 2;
    });
    check("nominees, then runoffs, then still running", blocks.filter(Boolean).every((b) => {
      const r = ranks(b);
      return r.every((v, i) => i === 0 || r[i - 1] <= v);
    }));
    const movers = people.filter((p) => !p.isCandidate && /House/.test(p.chamber) &&
      /^S-/.test(p.contestRaceId || "") && !offBallot(p));
    check("a member running for a Senate seat appears under it, once", movers.every((p) => {
      const b = seatOf(races.find((r) => r.id === p.contestRaceId));
      const shown = b ? ids(b) : [];
      return shown.includes(p.id) && !shown.includes(p.alsoRunningId);
    }), movers.map((p) => p.name).join(", "));

    const outIds = upRaces.flatMap((r) => r.candidateIds).filter((id) => offBallot(KYC.byId(id)));
    const anyOut = () => [...results.querySelectorAll(".card")]
      .some((c) => outIds.includes(c.getAttribute("data-id")));
    check("eliminated candidates are hidden by default", outIds.length > 0 && !anyOut(),
      `${outIds.length} off the ballot`);
    D.querySelector('[data-group="eliminated"]').click();
    check("and appear with the Include eliminated control", anyOut());
    check("after everyone still running", upRaces.every((r) => {
      const b = seatOf(r);
      if (!b) return true;
      const all = ids(b).slice(1);
      const firstOut = all.findIndex((id) => offBallot(KYC.byId(id)));
      return firstOut === -1 || all.slice(firstOut).every((id) => offBallot(KYC.byId(id)));
    }));
    check("the URL carries both", /view=senate/.test(window.location.hash) &&
      /eliminated=show/.test(window.location.hash), window.location.hash);
    D.querySelector('[data-group="eliminated"]').click();

    const shownCount = announced(D);
    check("the results bar counts what is shown",
      shownCount === results.querySelectorAll(".card").length, String(shownCount));

    // Filters narrow it; a seat with nothing matching disappears.
    const republican = D.querySelector('[data-group="party"][data-value="Republican"]');
    republican.click();
    const parties = [...results.querySelectorAll(".card")]
      .map((c) => KYC.byId(c.getAttribute("data-id")).party);
    check("the party filter narrows the Senate view",
      parties.length > 0 && parties.every((p) => p === "Republican"), `${parties.length} cards`);
    check("seat blocks with nothing matching are hidden",
      [...results.querySelectorAll("section.senate-seat")].every((s) => s.querySelector(".card")));
    republican.click();

    const first = results.querySelector(".card");
    first.click();
    const modal = D.getElementById("profileModal");
    check("a card opens the profile",
      modal && !modal.hidden && D.getElementById("profileModalName").textContent ===
        KYC.byId(first.getAttribute("data-id")).name);
    D.querySelector("#profileModal .modal-footer [data-close]").click();
  });

  suite("index.html — Senate view URL and escaping", () => {
    toggle.click();
    check("toggling off returns to the grid", toggle.getAttribute("aria-pressed") === "false" &&
      !results.querySelector("section.senate-group") && !/view=senate/.test(window.location.hash),
      window.location.hash);
    toggle.click();
    check("toggling on writes #/?view=senate", /view=senate/.test(window.location.hash) &&
      !!results.querySelector("section.senate-group"), window.location.hash);
    D.getElementById("raceViewToggle").click();
    check("the race view releases the Senate toggle",
      toggle.getAttribute("aria-pressed") === "false" &&
      D.getElementById("raceViewToggle").getAttribute("aria-pressed") === "true");
    window.location.hash = "#/?view=senate";
    window.dispatchEvent(new window.Event("hashchange"));
    check("the URL round-trips back to the Senate view",
      toggle.getAttribute("aria-pressed") === "true" && !!results.querySelector("section.senate-group"));

    const victim = senators[0];
    const real = victim.name;
    victim.name = '<img id="kyc-pwn" src=x>';
    toggle.click();
    toggle.click();
    check("names are escaped in the Senate view", !D.getElementById("kyc-pwn") &&
      results.textContent.includes('<img id="kyc-pwn" src=x>'));
    victim.name = real;
  });
  window.close();
}

/* A person registered with the FEC under several ids has one profile; a link
 * shared under a folded id opens them and the address moves to the current
 * id. A real profile id must never be shadowed by an alias. */
async function testFoldedIds() {
  const probe = await buildPage("index.html");
  const people = probe.window.legislatorsData;
  const person = people.find((p) => (p.otherFecIds || []).length);
  const ids = new Set(people.map((p) => p.id));
  probe.window.close();
  suite("folded FEC registrations — old links keep working", () => {
    check("the data has a person with folded registrations", !!person);
  });
  if (!person) return;
  const alias = "FEC_" + person.otherFecIds[0];
  const { window, D, errors, KYC } = await buildPage("index.html", { hash: "#/profile/" + alias });
  await settle();
  const modal = D.getElementById("profileModal");
  suite("folded FEC registrations — landing on an old id", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("the alias is not a profile of its own", !ids.has(alias), alias);
    check("the person's profile opens", modal && !modal.hidden &&
      D.getElementById("profileModalName").textContent === person.name,
      D.getElementById("profileModalName") && D.getElementById("profileModalName").textContent);
    check("the address moves to the current id",
      window.location.hash === "#/profile/" + encodeURIComponent(person.id), window.location.hash);
    check("lookups by the alias resolve to the same record",
      (window.KYC || KYC).byId(alias) === (window.KYC || KYC).byId(person.id));
    check("no profile id is shadowed by an alias",
      window.legislatorsData.every((p) => (window.KYC || KYC).byId(p.id) === p));
  });
  window.close();
}

/* Each 2026 Senate seat is one row - the senator, then the people running -
 * and a sitting member renominated for their own seat says so on the card
 * instead of the bare "seat up" a real-browser look caught. */
async function testSeatRows() {
  const { window, D, errors } = await buildPage("index.html", { hash: "#/?view=senate" });
  await settle();
  const people = window.legislatorsData;
  const renominated = people.find((p) => !p.isCandidate && p.chamber === "Senate" &&
    p.raceStatus === "nominee" && !p.contestLabel);
  const races = window.kycRaces;
  suite("Senate view — one row per seat", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    const rows = D.querySelectorAll(".senate-seat .senate-seat-row");
    check("2026 seats are drawn as rows", rows.length > 0, String(rows.length));
    const both = [...rows].filter((r) => r.querySelector(".senate-holder") && r.querySelector(".senate-running"));
    check("a row holds the senator and the people running side by side", both.length > 0);
    check("the senator comes first in the row", both.every((r) =>
      r.firstElementChild.classList.contains("senate-holder")));
    if (renominated) {
      // The id is on the seat's heading; the section is labelled by it.
      const heading = D.getElementById("senate-seat-" + renominated.raceId);
      const block = heading && heading.closest("section");
      const holderCard = block && block.querySelector('.senate-holder .card[data-id="' + renominated.id + '"]');
      check("a renominated senator is in their seat's row", !!holderCard, renominated.id);
      check("their card says Renominated, not just seat up",
        holderCard && /Renominated/.test(holderCard.textContent), holderCard && holderCard.textContent);
    }
  });
  window.close();
}

/* =========================================================== odds */

async function testOdds() {
  const { window, D, errors } = await buildPage("index.html", { hash: "#/?view=senate" });
  await settle(50);
  const KYC = window.KYC;
  const results = D.getElementById("results");

  suite("index.html — prediction markets and polling averages", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    const control = results.querySelector(".odds-control");
    check("the Senate view opens with the markets on control of the chamber",
      !!control && control.querySelectorAll(".odds-market").length >= 1 &&
        results.firstElementChild === control);
    const blocks = [...results.querySelectorAll(".senate-seat .odds")];
    check("2026 seats carry their race's markets", blocks.length > 20, String(blocks.length));
    check("every bar says in words what it draws",
      [...results.querySelectorAll(".odds-bar")].every((b) => /\d+%/.test(b.getAttribute("aria-label") || "")));
    const links = [...results.querySelectorAll(".odds a")];
    check("every source is linked, and opens safely",
      links.length > 0 && links.every((a) => /^https:/.test(a.href) && a.target === "_blank" &&
        /noopener/.test(a.rel)));
    check("each block says a price is not a poll or a forecast",
      blocks.every((b) => /not a poll/.test(b.textContent)));
    check("a polling table names the aggregator and when it was updated",
      !!results.querySelector(".odds-poll-table tbody th") &&
        /Updated/.test((results.querySelector(".odds-poll-table thead") || {}).textContent || ""));

    // Markup in a market label never reaches the page as markup.
    const hostile = { label: "Test", odds: { asOf: "2026-10-03T00:00:00Z", markets: [
      { source: "kalshi", url: "https://kalshi.com/markets/x", title: "<b>x</b>", outcomes: [
        { label: "<img src=x onerror=alert(1)>", party: "r", price: 0.6 },
        { label: "Other", party: "d", price: 0.4 }] }] } };
    const holder = D.createElement("div");
    holder.innerHTML = KYC.odds.render(hostile);
    check("market labels are escaped", !holder.querySelector("img") && !holder.querySelector("b") &&
      /onerror/.test(holder.textContent));
    check("a race with no odds renders nothing", KYC.odds.render({ label: "x" }) === "");
    check("prices are written as the market writes them",
      KYC.odds.percent(0.995) === ">99%" && KYC.odds.percent(0.004) === "<1%" &&
        KYC.odds.percent(0.384) === "38%");
  });

  suite("index.html — a race's markets in the grid's race view", () => {
    window.location.hash = "#/";
    window.dispatchEvent(new window.Event("hashchange"));
    D.getElementById("raceViewToggle").click();
    const senate = [...results.querySelectorAll("section.race")].filter((s) => /^race-S-/.test(s.id));
    check("Senate races show their markets, compactly",
      senate.length > 0 && senate.some((s) => s.querySelector(".odds-compact")), String(senate.length));
    check("House races show none", ![...results.querySelectorAll("section.race")]
      .filter((s) => /^race-H-/.test(s.id)).some((s) => s.querySelector(".odds")));
  });
}

(async function main() {
  const only = process.argv[2];
  if (!only || only === "index.html") await testDirectoryAsync();
  if (!only || only === "index.html") await testSenate();
  if (!only || only === "index.html") await testOdds();
  if (!only || only === "index.html") await testSeatRows();
  if (!only || only === "map.html") await testMap();
  if (!only || only === "states") await testStates();
  if (!only || only === "links") await testDeepLinks();
  if (!only || only === "links") await testFoldedIds();
  if (!only || only === "links") await testRunningElsewhere();
  if (!only || only === "contrast") testContrast();

  let failed = 0;
  for (const r of results) {
    if (r.heading) {
      console.log(`\n${r.heading}`);
      continue;
    }
    if (!r.ok) failed += 1;
    console.log(
      `  ${r.ok ? "PASS" : "FAIL"}  ${r.label}${r.detail ? "  -> " + r.detail : ""}`
    );
  }
  const total = results.filter((r) => !r.heading).length;
  console.log(`\n${total - failed}/${total} checks passed`);
  process.exit(failed ? 1 : 0);
})();
