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

function buildPage(page) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => errors.push("jsdomError: " + e.message));
  vc.on("error", (...a) => errors.push("console.error: " + a.join(" ")));

  // jsdom does not fetch <script src>, so inline every local script in
  // document order - exactly the order a browser would execute them in.
  let html = fs.readFileSync(path.join(SITE, page), "utf8");
  const sources = [...html.matchAll(/<script[^>]*\bsrc="([^"]+)"[^>]*><\/script>/g)];
  for (const [tag, src] of sources) {
    const file = path.join(SITE, ...src.split("/"));
    if (!fs.existsSync(file)) throw new Error(`${page} references a missing ${src}`);
    html = html.replace(tag, () => "<script>\n" + fs.readFileSync(file, "utf8") + "\n</script>");
  }

  const dom = new JSDOM(html, {
    runScripts: "dangerously",
    url: "https://kyc.local/" + page,
    pretendToBeVisual: true,
    virtualConsole: vc,
    beforeParse(window) {
      // jsdom has no matchMedia; the theme layer asks it whether the OS
      // prefers light.
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
    const remoteLinks = [...raw.matchAll(/<link[^>]*>/g)].map((m) => m[0])
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
      const js = ["kyc.js", "kyc-profile.js", "kyc-directory.js", "kyc-map.js"]
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

  suite(`${page} — election arithmetic`, () => {
    const es = KYC.electionStatus(2026, new Date("2026-08-20T12:00:00Z"));
    check("2026 election day is 3 November", es.iso === "2026-11-03", es.iso);
    check("countdown counts down", es.days === 75, `${es.days} days`);
    check("phase during campaign", es.phase === "campaign", es.phase);
    check("phase after the vote",
      KYC.electionStatus(2026, new Date("2026-12-01T12:00:00Z")).phase === "post-election");
    // 2028: first Monday is the 6th, so election day is the 7th.
    check("election day generalises to 2028",
      KYC.electionStatus(2028, new Date("2028-01-01Z")).iso === "2028-11-07");
  });

  return { window, D, KYC };
}

/* ============================================================== index.html */

async function testDirectory() {
  const { window, D, KYC } = await testShared("index.html");
  const grid = D.getElementById("results");
  const cards = () => grid.querySelectorAll(".card");

  suite("index.html — grid", () => {
    check("cards rendered", cards().length > 400, `${cards().length} cards`);
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
      return texts.every((t) => !/District \d|([A-Z]{2})-/.test(t));
    })());
    check("card names are escaped", (() => {
      const html = grid.innerHTML;
      return !/<img[^>]*onerror/.test(html);
    })());
  });

  suite("index.html — filtering", () => {
    const label = D.getElementById("resultsLabel");
    const total = cards().length;

    D.querySelector('[data-group="chamber"][data-value="Senate"]').click();
    const senate = cards().length;
    check("chamber filter narrows the grid", senate > 0 && senate < total,
      `${senate} of ${total}`);
    check("chamber filter is reflected in the URL",
      /chamber=Senate/.test(window.location.hash), window.location.hash);
    check("results count is announced", /Showing/.test(label.textContent), label.textContent);

    D.querySelector('[data-group="party"][data-value="Republican"]').click();
    check("filters compose", cards().length < senate, `${cards().length}`);
    D.querySelector('[data-group="party"][data-value="Republican"]').click();
    check("clicking an active optional chip clears it", cards().length === senate);

    D.querySelector('[data-group="chamber"][data-value="all"]').click();
    check("chamber resets", cards().length === total);

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
    const total = cards().length;

    D.querySelector('[data-group="role"][data-value="member"]').click();
    const members = [...cards()];
    check("sitting members filter narrows the grid", members.length < total,
      `${members.length} of ${total}`);
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
      cards().length === total - members.length, `${cards().length}`);
    check("every card is a challenger",
      [...cards()].every((c) => KYC.byId(c.getAttribute("data-id")).isCandidate));

    D.querySelector('[data-group="role"][data-value="candidate"]').click();
    check("clicking the active chip clears it", cards().length === total);
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

/* ================================================================== report */

(async function main() {
  const only = process.argv[2];
  if (!only || only === "index.html") await testDirectoryAsync();
  if (!only || only === "map.html") await testMap();

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
