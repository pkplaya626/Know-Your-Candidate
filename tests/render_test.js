// Render index.html / map.html in jsdom and exercise the real page code.
// Requires jsdom:  npm install jsdom
//   node tests/render_test.js index.html
//   node tests/render_test.js map.html
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const SITE = path.resolve(__dirname, "..", "candidate_profiles_site");

const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errors.push("jsdomError: " + e.message));
vc.on("error", (...a) => errors.push("console.error: " + a.join(" ")));

const page = process.argv[2] || "index.html";
// Inline the two local <script src> tags so jsdom parses them in document
// order, exactly as a browser would. jsdom will not fetch them itself.
const inline = (file) =>
  "<script>\n" + fs.readFileSync(path.join(SITE, file), "utf8") + "\n</script>";

const html = fs
  .readFileSync(path.join(SITE, page), "utf8")
  .replace('<script src="assets/kyc.js"></script>', () => inline("assets/kyc.js"))
  .replace('<script src="data/profiles.js"></script>', () => inline("data/profiles.js"));

const dom = new JSDOM(html, {
  runScripts: "dangerously",
  url: "https://kyc.local/" + page,
  virtualConsole: vc,
  beforeParse(window) {
    window.lucide = { createIcons: () => {} };
    window.tailwind = { config: {} };
    window.d3 = new Proxy(function () {}, { get: () => window.d3, apply: () => window.d3 });
    window.topojson = { feature: () => ({ features: [] }), mesh: () => ({}) };
    window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
  },
});

const { window } = dom;
window.document.dispatchEvent(new window.Event("DOMContentLoaded", { bubbles: true }));

const D = window.document;
const pass = [];
const fail = [];
const check = (label, cond, detail) =>
  (cond ? pass : fail).push(`${cond ? "PASS" : "FAIL"}  ${label}${detail ? " -> " + detail : ""}`);

check("data loaded", (window.legislatorsData || []).length > 0, `${window.legislatorsData.length} profiles`);
check("KYC shared module present", !!window.KYC);
check("theme applied", !!D.documentElement.getAttribute("data-theme"),
  D.documentElement.getAttribute("data-theme"));

// ---- shared module behaviour (both pages) --------------------------------
const es = window.KYC.electionStatus(2026, new Date("2026-08-20T12:00:00Z"));
check("2026 election day computed", es.iso === "2026-11-03", es.iso);
check("countdown counts down", es.days === 75, `${es.days} days`);
check("election phase", es.phase === "campaign", es.phase);

const past = window.KYC.electionStatus(2026, new Date("2026-12-01T12:00:00Z"));
check("post-election phase", past.phase === "post-election", past.label);

// Provenance rendering must not present an absence as a finding.
const absent = window.KYC.renderField({ net_worth: "Not disclosed", quality: { net_worth: "not_disclosed" } }, "net_worth");
check("absent field renders muted", /kyc-absent/.test(absent) && /Not disclosed/.test(absent));
const generic = window.KYC.renderField({ funding_sources: "Individual/PAC contributions", quality: { funding_sources: "generic" } }, "funding_sources");
check("generic field marked", /kyc-generic/.test(generic));
const real = window.KYC.renderField({ receipts: "$1,022,664.06", quality: {}, financeSource: "FEC", financeAsOf: "2026-06-30" }, "receipts", { source: true });
check("sourced field shows FEC badge", /kyc-badge--source/.test(real) && /FEC/.test(real));
check("renderField escapes html",
  !/<img/.test(window.KYC.renderField({ x: '<img src=x onerror=alert(1)>', quality: {} }, "x")));

if (page === "index.html") {
  check("cards rendered", D.getElementById("cardsGrid").querySelectorAll("img").length > 400,
    `${D.getElementById("cardsGrid").querySelectorAll("img").length} portraits`);
  check("portraits lazy-load", D.getElementById("cardsGrid").querySelectorAll('img[loading="lazy"]').length > 400);
  check("sidebar has id for drawer CSS", !!D.getElementById("sidebar"));
  check("hamburger present", !!D.getElementById("sidebarToggle"));
  check("skip link present", !!D.querySelector("a.skip-link"));
  check("search has a label", !!D.querySelector('label[for="searchInput"]'));
  check("results is a live region", D.getElementById("resultsLabel").getAttribute("aria-live") === "polite");
  check("countdown rendered", /day|Election/.test(D.getElementById("electionCountdown").textContent),
    D.getElementById("electionCountdown").textContent);
  check("build stamp rendered", /^\d{4}-\d{2}-\d{2}$/.test(D.getElementById("buildStamp").textContent),
    D.getElementById("buildStamp").textContent);
  check("sources footer present", /Voteview/.test(D.body.textContent) && /FEC/.test(D.body.textContent));

  // ---- expanded search -------------------------------------------------
  const si = D.getElementById("searchInput");
  const runSearch = (q) => { si.value = q; window.filterData(); return window.filteredData.length; };

  const committee = runSearch("appropriations");
  check("search matches committees", committee > 5, `"appropriations" -> ${committee}`);
  const edu = runSearch("harvard");
  check("search matches education", edu > 5, `"harvard" -> ${edu}`);
  const multi = runSearch("harvard texas");
  check("multi-term search narrows", multi >= 0 && multi < edu, `"harvard texas" -> ${multi}`);
  const nameSearch = runSearch("hinson");
  check("search still matches names", nameSearch > 0, `"hinson" -> ${nameSearch}`);
  runSearch("");

  // Absent values must not be searchable, or "No data" matches everyone.
  const noData = runSearch("not disclosed");
  check("absent placeholders are not searchable", noData === 0, `"not disclosed" -> ${noData}`);
  runSearch("");

  // ---- deep linking ----------------------------------------------------
  const target = window.legislatorsData.find((x) => x.name === "Ashley Hinson" && !x.isCandidate);
  window.openProfile(target.id);
  check("opening a profile writes the URL", window.location.hash === `#/profile/${target.id}`,
    window.location.hash);
  check("modal is open", !D.getElementById("profileModal").classList.contains("hidden"));

  // ---- accessibility ---------------------------------------------------
  const esc = new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true });
  D.dispatchEvent(esc);
  check("Escape closes the modal", D.getElementById("profileModal").classList.contains("hidden"));

  window.location.hash = `#/profile/${target.id}`;
  window.dispatchEvent(new window.Event("hashchange"));
  check("deep link opens the profile", !D.getElementById("profileModal").classList.contains("hidden"),
    "restored from URL");
  window.closeModal();

  // ---- race view -------------------------------------------------------
  check("races emitted", (window.kycRaces || []).length > 400, `${(window.kycRaces||[]).length} races`);
  const contested = (window.kycRaces || []).filter((r) => r.contested).length;
  check("contested races flagged", contested > 0, `${contested} contested`);

  window.toggleRaceView();
  const sections = D.getElementById("cardsGrid").querySelectorAll("section");
  check("race view groups into sections", sections.length > 100, `${sections.length} sections`);
  check("race sections are labelled", sections.length > 0 && !!sections[0].getAttribute("aria-label"),
    sections.length ? sections[0].getAttribute("aria-label") : "no sections");
  const openBadges = D.getElementById("cardsGrid").querySelectorAll(".kyc-badge--estimate").length;
  check("open seats badged", openBadges > 0, `${openBadges} open-seat badges`);
  const inRace = D.getElementById("cardsGrid").querySelectorAll("img").length;
  check("every profile still shown in race view", inRace > 400, `${inRace} portraits`);
  window.toggleRaceView();
  check("toggling back restores the grid",
    D.getElementById("cardsGrid").querySelectorAll("section").length === 0);

  // Filters round-trip through the URL.
  const senateChip = D.querySelector('button[data-filter="Senate"]');
  window.setFilter(senateChip, "chamber");
  check("filters write to the URL", /chamber=Senate/.test(window.location.hash), window.location.hash);
  const route = window.KYC.router.read();
  check("router reads filters back", route.params.chamber === "Senate", JSON.stringify(route.params));
}

if (page === "map.html") {
  check("map still exposes setTheme", typeof window.setTheme === "function");
  check("no duplicated silhouette in page", !/const defaultSilhouette/.test(html));
  check("shared silhouette available", typeof window.defaultSilhouette === "string");
}

console.log(`--- ${page} ---`);
pass.forEach((l) => console.log("  " + l));
fail.forEach((l) => console.log("  " + l));
if (errors.length) {
  console.log("  page errors:");
  errors.slice(0, 8).forEach((e) => console.log("    " + e));
}
console.log(`  ${pass.length} passed, ${fail.length} failed, ${errors.length} page error(s)`);
process.exitCode = fail.length || errors.length ? 1 : 0;
