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
const { JSDOM, VirtualConsole, requestInterceptor } = require("jsdom");

const SITE = path.resolve(__dirname, "..", "candidate_profiles_site");

/* A script a page adds itself - "Find who represents me" loads one state's
 * lookup and legislature files only when a reader asks (kyc-findrep.js) -
 * is served from the site's own folder, as the browser would fetch it, and
 * runs and fires its load event as in a browser. Anything else is refused,
 * and nothing reaches the network: the pages load nothing from another host
 * (CLAUDE.md), and a stylesheet is nothing a test reads. *served* lists the
 * site's files a page asked for. */
function siteResources(served, refuse) {
  return {
    interceptors: [requestInterceptor((request) => {
      const u = new URL(request.url);
      if (u.hostname !== "kyc.local") return new Response("", { status: 403 });
      if (/\.css$/.test(u.pathname)) return new Response("", { headers: { "Content-Type": "text/css" } });
      const file = path.join(SITE, ...decodeURIComponent(u.pathname).split("/").filter(Boolean));
      served.push(u.pathname + u.search);
      if (refuse && refuse.test(u.pathname)) return new Response("", { status: 503 });
      if (!fs.existsSync(file) || !fs.statSync(file).isFile()) return new Response("", { status: 404 });
      return new Response(fs.readFileSync(file), {
        headers: { "Content-Type": "application/javascript; charset=utf-8" },
      });
    })],
  };
}

/* What a people file assigns (rule 94), read as the page would run it. */
function readPeopleFile(file) {
  const sandbox = { window: {} };
  require("vm").runInNewContext(fs.readFileSync(file, "utf8"), sandbox);
  return sandbox.window.kycPeopleFile || sandbox.window.kycBuildMeta;
}

/* Everyone's whole record, from every state's file, keyed by id: what a
 * check compares a page against where the page itself holds less. */
let everyoneCache = null;
function everyone() {
  if (!everyoneCache) {
    everyoneCache = new Map();
    peopleStates().forEach((code) => {
      readPeopleFile(path.join(SITE, "data", "people", code + ".js")).people
        .forEach((p) => everyoneCache.set(p.id, p));
    });
  }
  return everyoneCache;
}

/* The profile id a link to it names: "../index.html#/profile/S000148". */
function profileHref(a) {
  const m = /#\/profile\/([^&?]+)$/.exec(a.getAttribute("href") || "");
  return m ? decodeURIComponent(m[1]) : null;
}

/* Every race, from the index of everyone (rule 94). */
function allRaces() {
  return readPeopleFile(path.join(SITE, "data", "people", "index.js")).races;
}

/* Every state's people file (rule 94), by its lower-case code. */
function peopleStates() {
  return fs.readdirSync(path.join(SITE, "data", "people"))
    .filter((name) => /^[a-z]{2}\.js$/.test(name)).map((name) => name.slice(0, 2)).sort();
}

/* Until *test* holds, or *ms* pass: a lookup answers after its files load. */
async function until(test, ms) {
  const end = Date.now() + (ms || 5000);
  while (!test() && Date.now() < end) await new Promise((r) => setTimeout(r, 10));
  return test();
}

/* ============================================== the statewide questions */

/* The statewide questions on each ballot (kyc-ballot.js, rule 95): every
 * state page said the ballot also held "ballot measures, which this site
 * does not list" (audit 2026-10-17, RACES-16, STATEGOV-14, PERSONA-08). */
async function testMeasures() {
  const officialText = (li) => [...li.querySelectorAll(".measure-text p")].map((p) => p.textContent).join("\n");
  const ca = await buildPage("states/ca.html");
  await settle(50);
  suite("states/ca.html — the statewide questions, in their official words", () => {
    const { window, D, errors } = ca;
    const rec = window.kycMeasures.CA;
    const section = D.getElementById("measures");
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("its own section, named as its jump chip names it", !!section &&
      section.querySelector("h2").textContent === "Statewide questions on the Nov 3, 2026 ballot" &&
      !!D.querySelector('.state-parts a[href="#measures"]') &&
      D.querySelector('.state-parts a[href="#measures"]').textContent === window.KYC.ballot.measuresName("CA"));
    const items = section ? [...section.querySelectorAll("li.measure")] : [];
    check("every measure the record lists, in its order", rec.has === true && items.length === rec.measures.length &&
      items.every((li, i) => li.querySelector(".measure-name").firstChild.textContent.trim() === rec.measures[i].designation),
      items.length + " / " + rec.measures.length);
    check("each quoted exactly as the record holds it", items.every((li, i) =>
      officialText(li) === rec.measures[i].text.split(/\n+/).join("\n")));
    check("each says what kind it is and who put it on the ballot", items.every((li, i) =>
      li.querySelector(".measure-kind").textContent.indexOf(rec.measures[i].kind) === 0 &&
      /Put on the ballot by (the Legislature|a citizens' petition)/.test(li.querySelector(".measure-kind").textContent)));
    check("each links its source and its voter guide page, outside the site", items.every((li, i) => {
      const hrefs = [...li.querySelectorAll(".measure-links a")].map((a) => a.getAttribute("href"));
      return hrefs.includes(rec.measures[i].source) && (!rec.measures[i].guide || hrefs.includes(rec.measures[i].guide)) &&
        [...li.querySelectorAll(".measure-links a")].every((a) => a.target === "_blank" && /noopener/.test(a.rel));
    }));
    check("the list is credited to the office that publishes it, and dated",
      /as the California Secretary of State lists them/.test(section.textContent) &&
      !!section.querySelector('.measures-lead a[href="' + rec.list.url + '"]') && /read Oct\. 19, 2026/.test(section.textContent));
    check("a text that is not the ballot's own wording says what it is",
      /summary in the Official Voter Information Guide, not the label printed on the ballot/.test(section.textContent));
    check("no colour, badge or word of the site's own takes a side", !section.querySelector(".badge, [style], .party, [class*=yes], [class*=oppose], [class*=support]") &&
      /does not say what a yes or a no vote does/.test(section.textContent));
    check("local questions are not listed here, and said so", /Local questions .* are not listed here/.test(section.textContent));
    const note = D.querySelector("#races .state-note");
    check("the race list's note points to them, and no longer calls them unlisted",
      !!note && !!note.querySelector('a[href="#measures"]') && !/ballot measures, which/.test(note.textContent),
      note && note.textContent);
  });

  /* Folding: a long text shows its first lines and opens in place. */
  const az = await buildPage("states/az.html");
  await settle(50);
  suite("states/az.html — a long official text is folded after its first lines", () => {
    const { window, D } = az;
    const items = [...D.querySelectorAll("#measures li.measure")];
    const long = items.filter((li, i) => window.kycMeasures.AZ.measures[i].text.length > 320);
    const short = items.filter((li, i) => window.kycMeasures.AZ.measures[i].text.length <= 320);
    check("each long one is folded, with the button that opens it", long.length > 0 && long.every((li) =>
      li.querySelector(".measure-text.is-folded") && li.querySelector("button[data-measure-more]")
        .getAttribute("aria-expanded") === "false"), long.length + " long");
    check("a short one is whole, with no button", short.every((li) =>
      !li.querySelector(".is-folded") && !li.querySelector("[data-measure-more]")));
    const li = long[0];
    const button = li && li.querySelector("[data-measure-more]");
    const text = button && D.getElementById(button.getAttribute("aria-controls"));
    if (button) button.click();
    check("'Read the whole text' opens it in place", !!text && !text.classList.contains("is-folded") &&
      button.getAttribute("aria-expanded") === "true" && button.textContent === "Show less");
    if (button) button.click();
    check("and folds it again", !!text && text.classList.contains("is-folded") &&
      button.textContent === "Read the whole text");
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    check("a folded text is printed whole, without its button", /\.measure-text\.is-folded \{ max-height: none; overflow: visible;/.test(css) &&
      /\.measure-more \{ display: none !important; \}/.test(css));
    check("a long word or address wraps at a phone's width", /\.measure-text \{[^}]*overflow-wrap: anywhere/.test(css) &&
      /\.measure-name \{[^}]*overflow-wrap: anywhere/.test(css));
  });

  const tx = await buildPage("states/tx.html");
  const me = await buildPage("states/me.html");
  const dc = await buildPage("states/dc.html");
  const mp = await buildPage("states/mp.html");
  const gu = await buildPage("states/gu.html");
  const pr = await buildPage("states/pr.html");
  await settle(50);
  suite("state pages — none, not found, the District and the territories", () => {
    const sec = (p) => p.D.getElementById("measures");
    const t = (p) => (sec(p) || { textContent: "" }).textContent;
    // A "none" on a ballot names the ballot read, never "the official
    // sample ballots" as though every county's had been (PR #120 review).
    check("Texas: none, credited to the ballot that was read, by name",
      /No statewide question is on the Nov 3, 2026 ballot\./.test(t(tx)) &&
      tx.window.kycMeasures.TX.none.from === "ballots" &&
      t(tx).indexOf("This site read " + tx.window.kycMeasures.TX.list.title + " on Oct. 19, 2026, and it " +
        "prints no statewide question.") !== -1 &&
      !/sample ballots print none|orders it only/.test(t(tx)) &&
      !!sec(tx).querySelector('a[href="' + tx.window.kycMeasures.TX.list.url + '"]') &&
      !sec(tx).querySelector("li.measure"), t(tx).slice(0, 300));
    check("no list's or guide's link text is a note or an address",
      [tx, me, dc, mp, gu].every((p) => [...(sec(p) || p.D.createElement("i")).querySelectorAll("a")].every((a) =>
        !/https?:|\blinked\b|described as/.test(a.textContent))));
    // The District and the territories hold no county's or school
    // district's question; a state's words are not theirs (rule 75).
    check("the District and the territories are not told of counties' questions",
      [dc, mp, gu].every((p) => !/a county's, a city's or a school district's/.test(t(p))) &&
      /a county's, a city's or a school district's/.test(t(tx)));
    check("Maine: not found, never 'none', and the election office's own site",
      /has not found an official list of statewide questions/.test(t(me)) && /does not say there are none/.test(t(me)) &&
      !/No statewide question is/.test(t(me)) &&
      !!sec(me).querySelector('a[href^="https://www.maine.gov/"]'), t(me).slice(0, 300));
    check("the District's questions are its own, not a state's",
      /^District-wide questions on the Nov 3, 2026 ballot/.test(sec(dc) ? sec(dc).querySelector("h2").textContent : "") &&
      sec(dc).querySelectorAll("li.measure").length === dc.window.kycMeasures.DC.measures.length);
    check("a territory's are territory-wide; who put one on the ballot, where not recorded, is said so",
      /^Territory-wide questions/.test(sec(mp) ? sec(mp).querySelector("h2").textContent : "") &&
      /Who put it on the ballot is not recorded here/.test(t(mp)) && /No territory-wide question is on/.test(t(gu)),
      t(mp).slice(0, 200));
    check("a place with no election that day lists no questions", !sec(pr));
  });

  /* New Hampshire's HB 1300 question is on every ballot, but each town or
   * city decides it for itself: it is listed apart and not counted as a
   * statewide question (PR #120 review). */
  const nh = await buildPage("states/nh.html");
  await settle(50);
  suite("states/nh.html — a question each town decides for itself is not a statewide one", () => {
    const { window, D } = nh;
    const section = D.getElementById("measures");
    const text = section ? section.textContent : "";
    const rec = window.kycMeasures.NH;
    const local = rec.measures.filter((m) => m.local);
    const statewide = rec.measures.filter((m) => !m.local);
    check("the record marks one question as decided locally", local.length > 0 && statewide.length > 0);
    check("the lead counts only the statewide ones", statewide.length === 1
      ? /One statewide question is on the Nov 3, 2026 ballot/.test(text)
      : new RegExp(statewide.length + " statewide questions are on").test(text), text.slice(0, 200));
    check("the statewide list holds only those", !!section &&
      section.querySelectorAll("ol.measures:not(.measures-local-list) > li.measure").length === statewide.length);
    check("the local one is listed apart, and says each town or city votes on it for itself",
      !!section && section.querySelectorAll("ol.measures-local-list > li.measure").length === local.length &&
      /not one statewide decision: each town or city votes on it for itself/.test(text) &&
      /Other local questions/.test(text));
    check("its kind line does not repeat its designation", !!section &&
      [...section.querySelectorAll("li.measure")].every((li) =>
        li.querySelector(".measure-kind").textContent.indexOf(
          li.querySelector(".measure-name").firstChild.textContent.trim()) === -1));
  });

  /* A state page is written with its statewide questions in plain text
   * (pages.measures_static, rule 96), from the record measures.js is
   * written from; the script draws its section over them. The two must say
   * the same: the questions, in order, and the lead's words. */
  suite("state pages' plain lists hold the questions the drawn section shows (rules 95, 96)", () => {
    const wrong = [];
    [["CA", ca], ["AZ", az], ["TX", tx], ["ME", me], ["DC", dc], ["MP", mp], ["GU", gu], ["PR", pr], ["NH", nh]]
      .forEach(([code, page]) => {
        const file = fs.readFileSync(path.join(SITE, "states", code.toLowerCase() + ".html"), "utf8");
        const holder = page.D.createElement("div");
        const at = /<section class="state-section measures-section" id="measures">[\s\S]*?<\/section>/.exec(file);
        holder.innerHTML = at ? at[0] : "";
        const plain = holder.querySelector("section");
        const drawn = page.D.getElementById("measures");
        if (!drawn || !plain) {
          if (!!drawn !== !!plain) wrong.push(`${code}: drawn ${!!drawn}, plain ${!!plain}`);
          return;
        }
        const text = (el, sel) => [...el.querySelectorAll(sel)].map((n) => n.textContent.replace(/\s+/g, " ").trim());
        ["h2", ".measures-lead", ".measures-source"].forEach((sel) => {
          if (text(plain, sel).join("|") !== text(drawn, sel).join("|")) {
            wrong.push(`${code} ${sel}: "${text(plain, sel)[0]}" / "${text(drawn, sel)[0]}"`);
          }
        });
        const drawnItems = [...drawn.querySelectorAll("li.measure")].map((li) => {
          const title = li.querySelector(".measure-title");
          return li.querySelector(".measure-name").firstChild.textContent.trim() +
            (title ? ": " + title.textContent.trim() : "");
        });
        const plainItems = [...plain.querySelectorAll("li[data-measure]")].map((li) =>
          li.textContent.replace(/\s+/g, " ").replace(/ \(source\)$/, "").trim());
        if (drawnItems.join("|") !== plainItems.join("|")) {
          wrong.push(`${code}: items ${plainItems.length} / ${drawnItems.length}: ${plainItems[0]} / ${drawnItems[0]}`);
        }
      });
    check("each plain list says what the drawn section says, question by question", wrong.length === 0,
      wrong.slice(0, 4).join(" | "));
  });

  /* A failed data/measures.js: the state page drew over its plain list and
   * put nothing back, and Your ballot dropped the card, both without a word
   * (PR #123 review, rules 76 and 96). */
  const caNoData = await buildPage("states/ca.html", { block: ["data/measures.js"] });
  const caBallotNoData = await ballotFor("#/?zip=94103", { block: ["data/measures.js"] });
  await settle(50);
  suite("a statewide-questions file that did not load is said, and the plain list stays", () => {
    const { window, D, errors } = caNoData;
    const file = fs.readFileSync(path.join(SITE, "states", "ca.html"), "utf8");
    const plainCount = (file.match(/<li data-measure="/g) || []).length;
    const section = D.getElementById("measures");
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("the data really did not load", !window.kycMeasures);
    check("the page was drawn (not left as the plain page)", !!D.querySelector("#senators .card-grid"));
    check("the plain list the page was written with stays, every question",
      !!section && plainCount > 0 && section.querySelectorAll("li[data-measure]").length === plainCount,
      (section ? section.querySelectorAll("li[data-measure]").length : 0) + " / " + plainCount);
    check("a line under the heading says the full list did not load",
      !!section && !!section.querySelector("h2 + .measures-failed") &&
      /did not load/.test(section.querySelector(".measures-failed").textContent));
    check("its jump chip and the race list's pointer are still there",
      !!D.querySelector('.state-parts a[href="#measures"]') &&
      !!D.querySelector('#races .state-note a[href="#measures"]'));
    check("one section, not two", D.querySelectorAll("#measures").length === 1);
    const card = caBallotNoData.out.querySelector(".ballot-contest.ballot-measures");
    check("Your ballot: no page errors", caBallotNoData.errors.length === 0, caBallotNoData.errors.join(" | "));
    check("Your ballot: the last card says the list did not load, and where to look",
      !!card && /did not load/.test(card.textContent) &&
      !!card.querySelector('a[href$="states/ca.html#measures"]') &&
      !/No statewide question/.test(card.textContent),
      card ? card.textContent : "no card");
    check("Your ballot: the order note still names the card",
      /then a note on statewide questions\./.test(
        (caBallotNoData.out.querySelector(".ballot-note") || { textContent: "" }).textContent));
  });

  const caAfter = await buildPage("states/ca.html", { now: "2026-11-05T09:00:00" });
  const txAfter = await buildPage("states/tx.html", { now: "2026-11-05T09:00:00" });
  const meAfter = await buildPage("states/me.html", { now: "2026-11-05T09:00:00" });
  await settle(50);
  suite("state pages after Election Day — the questions in the past tense, no result of our own", () => {
    const section = caAfter.D.getElementById("measures");
    const text = section ? section.textContent : "";
    const results = ((caAfter.window.kycBuildMeta.voting || {}).CA || {}).results;
    check("the heading and the lead are in the past tense",
      /questions that were on the Nov 3, 2026 ballot/.test(section.querySelector("h2").textContent) &&
      /questions were on the Nov 3, 2026 ballot/.test(text));
    check("no measure repeats the tense the heading and the lead carry",
      [...section.querySelectorAll("li.measure")].every((li) => !/Was on the Nov 3, 2026 ballot/.test(li.textContent)));
    check("the state's own results, and no result said here", /does not read the results of ballot questions/.test(text) &&
      (!results || !!section.querySelector('.measures-results a[href="' + results + '"]')) &&
      !/\b(passed|failed|approved|rejected)\b/i.test(section.querySelector(".measures-results").textContent));
    check("a 'none' is in the past tense too", /No statewide question was on the Nov 3, 2026 ballot/.test(
      txAfter.D.getElementById("measures").textContent));
    // "...that were on the ballot" says there were some: never over a
    // "none" or a "not found" (PR #120 review, rule 19).
    check("over a 'none' or a 'not found', the heading does not say there were questions",
      [txAfter, meAfter].every((p) => p.D.querySelector("#measures h2").textContent ===
        "Statewide questions on the Nov 3, 2026 ballot"),
      [txAfter, meAfter].map((p) => p.D.querySelector("#measures h2").textContent).join(" | "));
    check("'not found' is in the past tense, and still never 'none'",
      /did not find an official list/.test(meAfter.D.getElementById("measures").textContent) &&
      !/No statewide question/.test(meAfter.D.getElementById("measures").textContent));
  });

  /* Your ballot: a card after the state offices, the same list. */
  const caBallot = await ballotFor("#/?zip=94103");
  suite("Your ballot: the statewide questions after the state offices", () => {
    const { window, out, errors } = caBallot;
    check("no page errors", errors.length === 0, errors.join(" | "));
    const cards = [...out.querySelectorAll(".ballot-list > .ballot-contest")];
    const card = out.querySelector(".ballot-contest.ballot-measures");
    check("one card, last in the list", !!card && cards[cards.length - 1] === card &&
      card.querySelector(".ballot-office").textContent.trim() === "Statewide questions");
    check("the order note names them", /then the statewide questions/.test(out.textContent));
    const items = card ? [...card.querySelectorAll("li.measure")] : [];
    check("the same list as the state page's", items.length === window.kycMeasures.CA.measures.length &&
      items.every((li, i) => officialText(li) === window.kycMeasures.CA.measures[i].text.split(/\n+/).join("\n")));
    check("each measure's heading sits under the card's", items.every((li) => li.querySelector("h5.measure-name")));
    check("only local questions are left unlisted", /local ballot questions/.test(out.textContent) &&
      !/, and ballot measures,/.test(out.textContent));
    window.dispatchEvent(new window.Event("beforeprint"));
    check("in print mode the list is all there, folded texts included (the stylesheet opens them)",
      out.querySelectorAll("li.measure .measure-text").length === items.length);
    window.dispatchEvent(new window.Event("afterprint"));
  });

  const txBallot = await ballotFor("#/?zip=75036");
  const meBallot = await ballotFor("#/?zip=04101");
  const caBallotAfter = await ballotFor("#/?zip=94103", { now: "2026-11-05T12:00:00" });
  suite("Your ballot: none, not found, and after the day", () => {
    const card = (b) => b.out.querySelector(".ballot-contest.ballot-measures");
    check("Texas: a card drawn as off this ballot, saying none", !!card(txBallot) &&
      /ballot-off/.test(card(txBallot).className) && /No statewide question is on/.test(card(txBallot).textContent) &&
      !/then the statewide questions/.test(txBallot.out.textContent));
    check("Maine: not found, never none", !!card(meBallot) &&
      /has not found an official list/.test(card(meBallot).textContent) &&
      !/No statewide question is/.test(card(meBallot).textContent));
    // The order note names every card the list shows (PR #120 review).
    check("the order note names the card even where it says none or not found",
      [txBallot, meBallot].every((b) => /then a note on statewide questions\./.test(
        (b.out.querySelector(".ballot-note") || { textContent: "" }).textContent)));
    check("after the day, in the past tense, said once", !!card(caBallotAfter) &&
      /questions were on the Nov 3, 2026 ballot/.test(card(caBallotAfter).textContent) &&
      [...card(caBallotAfter).querySelectorAll("li.measure")].every((li) => !/Was on the Nov 3, 2026 ballot/.test(li.textContent)));
  });
}

/* ------------------------------------------------------------------ setup */

/* The page reads the clock: after Election Day a nominee reads "Awaiting
 * result" and market prices read as final. A suite that used the real clock
 * would start failing on 4 November and hold every refresh behind it, so a
 * page is built at a campaign-season moment unless a suite says otherwise
 * (opts.now: an ISO local time, or null for the real clock). */
const CAMPAIGN_NOW = "2026-10-20T12:00:00";

function freezeClock(window, iso) {
  const Real = window.Date;
  const fixed = new Real(iso).getTime();
  class Frozen extends Real {
    constructor(...args) {
      if (args.length) super(...args);
      else super(fixed);
    }
    static now() { return fixed; }
  }
  window.Date = Frozen;
}

/* The data moves too: from 4 November the daily refresh writes November
 * results into it. A page built at CAMPAIGN_NOW sees the data as it stood
 * then - elected, defeated and runoff read back as the nominee each was
 * (results.NOVEMBER), and the race summaries with them - or every suite
 * that looks for a nominee would fail on the first called race and hold
 * the refresh behind it. A suite that sets its own clock gets the data as
 * it is, and opts.data may change it as it loads. */
const NOVEMBER_RESULTS = { elected: true, defeated: true, runoff: true };

function rewindToCampaign(window) {
  window.legislatorsData.forEach((p) => {
    if (NOVEMBER_RESULTS[p.raceStatus]) p.raceStatus = "nominee";
  });
  window.kycRaces.forEach((r) => {
    const res = r.results;
    if (!res) return;
    res.nominees = (res.nominees || 0) + (res.elected || 0) + (res.defeated || 0) + (res.runoff || 0);
    res.elected = res.defeated = res.runoff = 0;
    res.otherElected = [];
    res.otherRunoff = [];
  });
}

/* A page built on a clock before the new Congress is sworn in (noon,
 * Eastern, January 3) sees the phase the build wrote then: the campaign's
 * (kyc/cycle.phase). After January 3 the data says "record", and a check
 * written for the campaign's views would otherwise read the archive. */
const NEW_CONGRESS = new Date("2027-01-03T17:00:00Z");

function phaseAt(now) {
  return (window, meta) => {
    if (meta && meta.election && new Date(now) < NEW_CONGRESS) {
      meta.election = Object.assign({}, meta.election, { phase: "campaign" });
    }
  };
}

/* Whether the data is from before the Congress its cycle elects sits.
 * The suite rewinds the phase and the clock, not the membership: in the
 * January rehearsal (tools/rehearse_changeover.py) every member sits in the
 * seat they won, and the campaign's cases - a member running for another
 * seat, a member leaving theirs, a renumbered member - describe nobody
 * (rule 68). A check that asks the data for such cases asks only while
 * the old Congress sits. The Congress elected in year Y is (Y - 1786) / 2. */
function oldCongressSits(window) {
  const meta = window.kycBuildMeta;
  return meta.congress < (meta.election.year - 1786) / 2;
}

/* Run *hooks* once the profile data has loaded, before any page module
 * reads it: kyc.js takes each people file in as it is assigned and fires
 * "kyc:people" (rule 94). Once the page's first *files* are in - its own
 * state's, or the index and every state's file inlined after it - every
 * hook runs; each file loaded after them (a state's, when one of its
 * people is opened) runs the idempotent ones again (*again*: the rewind,
 * the phase), so what it adds is seen as it stood then too. */
function onData(window, hooks, again, files) {
  if (!hooks.length) return;
  let seen = 0;
  window.document.addEventListener("kyc:people", () => {
    seen += 1;
    if (seen < files) return;
    const meta = window.kycBuildMeta;
    (seen === files ? hooks : hooks.filter((hook) => again.indexOf(hook) !== -1))
      .forEach((hook) => hook(window, meta));
  });
}

function buildPage(page, opts) {
  opts = opts || {};
  const errors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => errors.push("jsdomError: " + e.message));
  vc.on("error", (...a) => errors.push("console.error: " + a.join(" ")));

  // jsdom does not fetch <script src>, so inline every local script in
  // document order - exactly the order a browser would execute them in.
  let html = fs.readFileSync(path.join(SITE, page), "utf8");
  // A <template>'s scripts are inert, named for loading on demand
  // (KYC.loadData): kept as they are.
  const inert = [];
  html = html.replace(/<template[\s\S]*?<\/template>/g, (block) => {
    inert.push(block);
    return `<!--inert-${inert.length - 1}-->`;
  });
  const sources = [...html.matchAll(/<script[^>]*\bsrc="([^"]+)"[^>]*><\/script>/g)];
  let inlined = false;
  for (const [tag, src] of sources) {
    // Relative to the page: the state pages sit one directory down.
    // Without the version stamp a local asset's URL carries (kyc/assets.py).
    const file = path.join(path.dirname(path.join(SITE, page)), ...src.split("?")[0].split("/"));
    if (!fs.existsSync(file)) throw new Error(`${page} references a missing ${src}`);
    // opts.block: scripts that "failed to load", to see what a reader is told.
    if ((opts.block || []).some((b) => src.split("?")[0].endsWith(b))) {
      html = html.replace(tag, () => "");
      continue;
    }
    let body = "<script>\n" + fs.readFileSync(file, "utf8") + "\n</script>";
    // A page that loads the index of everyone (rule 94) holds each state's
    // full records only once one of its people is opened. Most suites ask
    // the data for a person's every field and open their profile at once,
    // as they did when one file held everyone: for them every state's file
    // follows the index, as loaded, before any page module reads it.
    // opts.people "index" builds the page as it ships, the index alone,
    // and the suites that prove the index enough say so (testPeopleSplit).
    // A state's page ships with its own state's file; opts.people "all"
    // puts everyone after it, to show the page draws the same without.
    const plain = src.split("?")[0];
    const index = /(^|\/)data\/people\/index\.js$/.test(plain);
    const own = /(^|\/)data\/people\/([a-z]{2})\.js$/.exec(plain);
    if ((index && opts.people !== "index") || (own && opts.people === "all")) {
      const folder = path.dirname(file);
      inlined = true;
      const more = own ? ["index"].concat(peopleStates().filter((c) => c !== own[2])) : peopleStates();
      more.forEach((code) => {
        body += "\n<script>\n" + fs.readFileSync(path.join(folder, code + ".js"), "utf8") + "\n</script>";
      });
    }
    html = html.replace(tag, () => body);
  }
  html = html.replace(/<!--inert-(\d+)-->/g, (m, i) => inert[Number(i)]);

  const served = [];
  const dom = new JSDOM(html, {
    runScripts: "dangerously",
    resources: siteResources(served, opts.refuse),
    url: "https://kyc.local/" + page + (opts.search || "") + (opts.hash || ""),
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
      if (opts.now !== null) freezeClock(window, opts.now || CAMPAIGN_NOW);
      // opts.written: the data as a later refresh would write it, before the rewind.
      const rewind = opts.now === undefined ? rewindToCampaign : null;
      const phase = opts.now === null ? null : phaseAt(opts.now || CAMPAIGN_NOW);
      onData(window, [opts.written, rewind, phase, opts.data].filter(Boolean), [rewind, phase],
        inlined ? 1 + peopleStates().length : 1);
      if (opts.setup) opts.setup(window);
    },
  });

  const { window } = dom;
  const packed = { window, D: window.document, errors, served,
    sources: sources.map((m) => m[1].split("?v=")[0]) };

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
    check("every <use> resolves: icons to a sprite symbol, district maps to a shape", (() => {
      const ids = new Set([...D.querySelectorAll("#kyc-sprite symbol")].map((s) => s.id));
      const used = [...D.querySelectorAll("use")].map((u) => (u.getAttribute("href") || "").slice(1));
      return used.length > 0 && used.every((id) => ids.has(id) ||
        (/^kycd-/.test(id) && !!D.querySelector(".district-defs #" + id)));
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
    // A role="menu" answers the keys a screen reader hands it (TECH-15).
    const menuItems = [...D.querySelectorAll('#themePanel [role^="menuitem"]')];
    const key = (k) => D.activeElement.dispatchEvent(new window.KeyboardEvent("keydown", { key: k, bubbles: true }));
    check("the menu's arrows, Home and End move among its items, wrapping", (() => {
      if (menuItems.length < 2) return false;
      menuItems[0].focus();
      key("ArrowDown");
      const second = D.activeElement === menuItems[1];
      key("End");
      const last = D.activeElement === menuItems[menuItems.length - 1];
      key("ArrowDown");
      const wrapped = D.activeElement === menuItems[0];
      key("ArrowUp");
      const back = D.activeElement === menuItems[menuItems.length - 1];
      key("Home");
      return second && last && wrapped && back && D.activeElement === menuItems[0];
    })(), `${menuItems.length} items`);
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
    // All but a folded race's section, hidden until found (kyc-state.js):
    // display: none would hide it from the browser's find-in-page.
    check("[hidden] wins over component display rules",
      /\[hidden\](:not\(\[hidden="until-found" i\]\))?\s*\{[^}]*display:\s*none\s*!important/.test(css));
    check("the page hides with the property, not a class", (() => {
      const js = ["kyc.js", "kyc-odds.js", "kyc-cards.js", "kyc-profile.js", "kyc-senate.js", "kyc-directory.js", "kyc-map.js", "kyc-state.js", "kyc-districts.js"]
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
    check("a generic placeholder renders as an absence, not as an answer (rule 10)",
      /kyc-absent/.test(generic) && !/Individual/.test(generic), generic);
    const filler = { name: "Pat Example", platforms: "General legislative priorities",
      quality: { platforms: "generic" } };
    check("a generic placeholder is not a value, so not shown or searched",
      !KYC.hasValue(filler, "platforms") && !KYC.matchesQuery(filler, "legislative priorities"));

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

    // FEC_H4IA01127's report ran "through 2026-12-31" in October 2026.
    const ahead = { financeSource: "FEC", chamber: "House (Candidate)",
      financePeriod: "election", financeElection: 2026,
      financeSince: "2025-01-01", financeAsOf: "2099-12-31" };
    check("a coverage end still to come is said in one sentence",
      KYC.financePeriod(ahead) === "Raised for the 2026 election, Jan 2025 – Dec 2099. " +
        "The report gives an end date still to come, Dec 2099",
      KYC.financePeriod(ahead));
    check("a coverage end already passed is not marked",
      !KYC.filedAhead({ financeAsOf: "2000-06-30" }));

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

  suite(`${page} — ages are today's, not the build's`, () => {
    // The build stamps `age` on its own date; 17 were a year out nine days
    // later. The page counts from the birthdate in the reader's calendar.
    const aoc = { birthdate: "1989-10-13", age: 36 };
    check("the day before a birthday", KYC.ageOf(aoc, new Date(2026, 9, 12)) === 36);
    check("on the birthday", KYC.ageOf(aoc, new Date(2026, 9, 13)) === 37);
    check("a year-only birthdate keeps the build's figure",
      KYC.ageOf({ birthdate: "1950", age: 76 }, new Date(2026, 9, 13)) === 76);
    check("no birthdate and no age is no age", KYC.ageOf({ birthdate: "", age: "Unknown" }) === null);
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
    // A card with no portrait has no image to load, only its initials.
    check("portraits lazy-load",
      grid.querySelectorAll('img[loading="lazy"]').length ===
        [...cards()].filter((c) => !c.classList.contains("card-no-photo")).length);
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

  suite("index.html — the filter bar shows every chip", () => {
    // It scrolled sideways with its scrollbar hidden: short of about 2,100px
    // "Senate by class" was cut off, and nothing said it was there.
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    const bar = (css.match(/\n\.toolbar\s*\{[^}]*\}/) || [""])[0];
    check("the bar wraps rather than scrolling",
      /flex-wrap:\s*wrap/.test(bar) && !/overflow/.test(bar) &&
        !/scrollbar-width:\s*none/.test(css),
      bar.replace(/\s+/g, " ").trim());
    const chips = [...D.querySelectorAll(".toolbar .chip:not(.filters-toggle)")];
    check("every chip is in a labelled group, which wraps as a whole",
      chips.length > 0 && chips.every((c) => c.closest('.chip-group[role="group"][aria-label]')),
      `${chips.length} chips`);
    // jsdom has no layout, so this asserts the rules rather than the effect.
    check("dividers come from the stylesheet, and none starts a line",
      !D.querySelector(".toolbar-divider") &&
        /\.chip-group \+ \.chip-group::before/.test(css) &&
        /\.chip-groups\s*\{[^}]*clip-path:\s*inset\(/.test(css));
  });

  suite("index.html — on a phone the filters fold behind one button", () => {
    // Fourteen chips wrapped onto seven rows, 328px of a 780px screen, and
    // stayed pinned there while the cards scrolled underneath.
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    const toggle = D.getElementById("filtersToggle");
    const bar = toggle && toggle.closest(".toolbar");
    check("the button is in the filter bar, and says what it controls",
      !!bar && toggle.getAttribute("aria-controls") === "chipGroups" &&
        !!D.getElementById("chipGroups"));
    check("it shows only on a phone, where the chips fold while it is closed",
      /\.filters-toggle\s*\{\s*display:\s*none/.test(css) &&
        /\.toolbar\[data-filters="closed"\] > \.chip-groups\s*\{\s*display:\s*none/.test(css));
    check("it starts closed", bar.getAttribute("data-filters") === "closed" &&
      toggle.getAttribute("aria-expanded") === "false");
    toggle.click();
    check("a tap opens it", bar.getAttribute("data-filters") === "open" &&
      toggle.getAttribute("aria-expanded") === "true");
    toggle.click();
    check("and another closes it", bar.getAttribute("data-filters") === "closed");
    const count = D.getElementById("filtersCount");
    check("with no filter on, it counts none", count.textContent === "", count.textContent);
    D.querySelector('.chip[data-group="party"][data-value="Democrat"]').click();
    D.querySelector('.chip[data-group="chamber"][data-value="House"]').click();
    check("it counts the filters that are on, so a folded bar never hides one",
      count.textContent === "(2 on)", count.textContent);
    D.querySelector('.chip[data-group="party"][data-value="Democrat"]').click();
    D.querySelector('.chip[data-group="chamber"][data-value="all"]').click();
    check("and stops counting them when they are off", count.textContent === "",
      count.textContent);
  });

  suite("index.html — the header leaves the search box room", () => {
    // The sort, a select as wide as "Sort: 2026 Senate races", took 184px of
    // a 390px header and left the search field 0-13px wide.
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    const button = D.getElementById("sortButton");
    const control = button && button.closest(".sort-control");
    check("on a phone the sort is an icon that opens its menu",
      !!control && !!control.querySelector('use[href="#i-sort"]') &&
        !!D.getElementById("i-sort") &&
        /\.btn-sort \.sort-current,\s*\.btn-sort::after\s*\{\s*display:\s*none/.test(css));
    check("and keeps a name when its words are hidden",
      /^Sort the cards: /.test(button.getAttribute("aria-label") || ""));
    check("no field or menu is under 16px on a phone, so iOS never zooms in",
      /\.search input,\s*\.search-page input,\s*\.select,\s*\.text-input\s*\{\s*font-size:\s*16px/.test(css));
    // A rule more specific than the phone's bare "input" that sets the
    // field's font wins over it: the 404 page's search was 14px on a phone
    // (".search-page input { font: inherit }"). Every such selector is in the
    // phone rule, or has its own 16px rule.
    const bare = css.replace(/\/\*[\s\S]*?\*\//g, "");
    const phoneRule = bare.match(/@media \(max-width: 1000px\), \(pointer: coarse\) \{\s*([^{}]+)\{\s*font-size:\s*16px;?\s*\}/);
    const covered = new Set((phoneRule ? phoneRule[1] : "").split(",").map((s) => s.trim()));
    const fieldSel = /(?:^|[\s>+~])(?:input|select|textarea)(?![\w-])(?![^\s>+~]*\[type="?(?:checkbox|radio|range)"?\])[^\s>+~]*$/;
    const rules = [...bare.matchAll(/([^{}]+)\{([^{}]*)\}/g)];
    const ownSixteen = new Set();
    rules.forEach((m) => { if (/font-size\s*:\s*16px/.test(m[2])) m[1].split(",").forEach((s) => ownSixteen.add(s.trim())); });
    const shrunk = [];
    rules.forEach((m) => {
      if (!/(^|;|\s)font(-size)?\s*:/.test(m[2])) return;
      m[1].split(",").map((s) => s.trim()).forEach((sel) => {
        if (fieldSel.test(sel) && !covered.has(sel) && !ownSixteen.has(sel)) shrunk.push(sel);
      });
    });
    check("and no field's own rule sets its font below that rule's reach",
      !!phoneRule && shrunk.length === 0, shrunk.join(" | "));
    // A native list drawn white under the theme's white text showed only the
    // highlighted option.
    check("a native menu's options take the theme's colours",
      /select option,\s*select optgroup\s*\{[^}]*background-color:\s*var\(--surface-1\);[^}]*color:\s*var\(--text\)/.test(css));
  });

  suite("index.html — the sort is the site's own menu", () => {
    const button = D.getElementById("sortButton");
    const panel = D.getElementById("sortPanel");
    check("closed until asked", panel.hidden && button.getAttribute("aria-expanded") === "false");
    button.click();
    check("a click opens it, the current order checked",
      !panel.hidden && button.getAttribute("aria-expanded") === "true" &&
      panel.querySelector('[aria-checked="true"]').getAttribute("data-sort") === "region");
    panel.querySelector('[data-sort="name"]').click();
    // By surname, as each race lists its people: "Name, A to Z" read Aaron
    // Bean, Aaron Flint, Aaron Gies (GRID-20).
    const names = [...D.querySelectorAll("#results .card")].slice(0, 6)
      .map((c) => KYC.byId(c.getAttribute("data-id")).surname);
    check("picking an order closes the menu, sorts the cards by surname and names the order",
      panel.hidden && D.getElementById("sortLabel").textContent === "Name, A to Z" &&
      names.length === 6 && names.every((n) => !!n) &&
      names.every((n, i) => i === 0 || names[i - 1].localeCompare(n) <= 0) &&
      /Name, A to Z/.test(button.getAttribute("aria-label")), names.join(", "));
    check("and puts it in the address", /[?&]sort=name\b/.test(window.location.hash), window.location.hash);
    check("only one order is checked",
      panel.querySelectorAll('[aria-checked="true"]').length === 1 &&
      panel.querySelector('[aria-checked="true"]').getAttribute("data-sort") === "name");
    // Every order the menu offers is one the grid sorts by: an unknown one
    // would be ignored and the menu would claim an order the cards lack.
    const offered = [...panel.querySelectorAll("[data-sort]")].map((b) => b.getAttribute("data-sort"));
    const took = offered.filter((key) => {
      button.click();
      panel.querySelector(`[data-sort="${key}"]`).click();
      return panel.querySelector('[aria-checked="true"]').getAttribute("data-sort") === key;
    });
    check("every order offered is one the grid knows", took.length === offered.length && offered.length === 7,
      offered.join(" "));
    check("the cards view says nothing about races", D.getElementById("sortNote").hidden);
    D.getElementById("raceViewToggle").click();
    check("the races view, which lists seats in their own order, says the sort is for the cards",
      !D.getElementById("sortNote").hidden);
    D.getElementById("raceViewToggle").click();
    D.getElementById("senateViewToggle").click();
    check("and in the Senate view it names that view, not the races view",
      !D.getElementById("sortNote").hidden && /Senate view/.test(D.getElementById("sortNote").textContent) &&
        !/races view/.test(D.getElementById("sortNote").textContent), D.getElementById("sortNote").textContent);
    D.getElementById("senateViewToggle").click();
    button.click();
    panel.querySelector('[data-sort="region"]').click();
  });

  suite("index.html — portraits come in sizes of one photograph", () => {
    // A 960px original in a 38px circle cost up to 760 KB, and congress.gov's
    // 175px portrait was soft on a 2x screen. Wikimedia's standard sizes of
    // the same file go in a srcset, and the browser picks one for the screen.
    const set = [[120, "https://u.test/120px-x.jpg"], [250, "https://u.test/250px-x.jpg"]];
    const attrs = KYC.portraitAttrs({ photos: ["https://u.test/x.jpg"], photoSet: set }, "165px");
    check("a portrait with sizes gets a srcset and the width it is drawn at",
      attrs.includes('srcset="https://u.test/120px-x.jpg 120w, https://u.test/250px-x.jpg 250w"') &&
        attrs.includes('sizes="165px"'), attrs);
    check("one without sizes gets only its src",
      !/srcset/.test(KYC.portraitAttrs({ photos: ["https://u.test/x.jpg"] }, "165px")));
    check("a silhouette never gets a srcset",
      !/srcset/.test(KYC.portraitAttrs({ photos: ["placeholder"], photoSet: set }, "38px")));
    check("a srcset is escaped like everything else",
      !/"onerror/.test(KYC.portraitAttrs(
        { photos: ["https://u.test/x.jpg"], photoSet: [[120, 'https://u.test/"onerror="1']] }, "38px")));

    // A race of six grey silhouettes said nothing (VISUALS-16): no
    // portrait is a disc of initials, and no portrait is guessed (rule 24).
    const bare = window.legislatorsData.find((p) => !KYC.hasPortrait(p));
    const pictured = window.legislatorsData.find((p) => KYC.hasPortrait(p));
    const holder = D.createElement("div");
    holder.innerHTML = KYC.cards.card(bare) + KYC.cards.card(pictured);
    const [bareCard, picturedCard] = holder.querySelectorAll(".card");
    check("a card with no portrait shows the person's initials in a disc, and no silhouette",
      !!bare && !bareCard.querySelector("img") &&
        bareCard.querySelector(".card-monogram").textContent === KYC.monogram(bare.name) &&
        KYC.monogram(bare.name).length >= 1, bare && bare.name);
    check("a card with a portrait keeps it", !!picturedCard.querySelector(".card-photo img"));
    check("initials skip suffixes, nicknames and punctuation",
      KYC.monogram("Ralph Abraham Jr.") === "RA" && KYC.monogram('James "Jim" O\'Brien') === "JO" &&
        KYC.monogram("Mary Gay Scanlon") === "MS" && KYC.monogram("Ana Ortiz (write-in)") === "AO",
      [KYC.monogram("Ralph Abraham Jr."), KYC.monogram('James "Jim" O\'Brien')].join(" "));

    const real = window.legislatorsData.find((p) => p.photoSet && p.photos.length > 1);
    check("the build lists sizes for Wikimedia portraits", !!real);
    if (real) {
      const img = D.createElement("img");
      img.setAttribute("data-profile", real.id);
      KYC.setPortrait(img, real, "116px");
      check("the dialog's portrait gets the sizes too",
        img.getAttribute("srcset") === KYC.portraitSrcset(real, "116px") &&
          img.getAttribute("sizes") === "116px");
      KYC.handleImageFallback(img, real.id);
      check("a size that fails is retried as the same photograph's plain URL",
        !img.hasAttribute("srcset") && !img.hasAttribute("sizes") &&
          img.getAttribute("src") === real.photos[0], img.getAttribute("src"));
      KYC.handleImageFallback(img, real.id);
      const next = real.photos.slice(1).find((u) => u !== "placeholder") || KYC.SILHOUETTE;
      check("and only then does the chain move on", img.getAttribute("src") === next,
        img.getAttribute("src"));
      KYC.setPortrait(img, { photos: ["https://u.test/y.jpg"] }, "116px");
      check("the next profile's portrait does not keep the last one's sizes",
        !img.hasAttribute("srcset") && !img.hasAttribute("sizes"));
    }

    // TECH-13: a 165px card on a 3x phone fetched a 494px original. No size
    // wider than a 2x screen needs is offered; the smallest at least that
    // wide is the last.
    const four = { photos: ["https://u.test/x.jpg"], photoSet: [120, 250, 330, 494].map((w) =>
      [w, "https://u.test/" + w + "px-x.jpg"]) };
    const widths = (sizes) => KYC.portraitSrcset(four, sizes).split(", ").map((e) => e.split(" ")[1]);
    check("a 165px card is offered sizes up to 330px, never the 494px original",
      widths("165px").join() === "120w,250w,330w", widths("165px").join());
    check("a 116px dialog portrait up to 250px", widths("116px").join() === "120w,250w",
      widths("116px").join());
    check("a 36px circle the smallest alone", widths("36px").join() === "120w", widths("36px").join());
  });

  suite("index.html — every portrait says whose photograph it is (rule 87)", () => {
    // 148 of 381 Wikimedia portraits were CC BY or CC BY-SA, and none was
    // credited; the footer credited every portrait to Congress.gov (TRUST-08).
    const shown = window.legislatorsData.filter((p) => (p.photos || [])[0] &&
      p.photos[0] !== "placeholder");
    const bare = shown.filter((p) => !p.photoCredit || !(p.photoCredit.by || p.photoCredit.licence));
    check("every profile that shows a photograph carries its credit", !bare.length,
      bare.slice(0, 5).map((p) => p.id).join(","));
    const unlicensed = shown.filter((p) => /wikimedia\.org/.test(p.photos[0]) &&
      !(p.photoCredit || {}).licence);
    check("and every Wikimedia one its licence", !unlicensed.length,
      unlicensed.slice(0, 5).map((p) => p.id).join(","));

    const line = () => D.getElementById("profileModalPhotoCredit");
    const commons = shown.find((p) => (p.photoCredit || {}).via === "Wikimedia Commons" &&
      p.photoCredit.by && p.photoCredit.licenceUrl && p.photoCredit.page);
    check("a Commons portrait with an author and a licence link exists", !!commons);
    if (commons) {
      KYC.profile.open(commons.id);
      const text = line().textContent;
      check("the dialog credits its author, its licence and Commons",
        !line().hidden && text.indexOf("Photo" + (commons.photoCredit.year ? " (" +
          commons.photoCredit.year + ")" : "") + ": " + commons.photoCredit.by + ", " +
          commons.photoCredit.licence + ", via Wikimedia Commons") === 0, text);
      check("linking the licence and the file's own page",
        !!line().querySelector('a[href="' + commons.photoCredit.licenceUrl + '"]') &&
          !!line().querySelector('a[href="' + commons.photoCredit.page + '"]'));
      KYC.profile.close();
    }

    const house = shown.find((p) => p.photoSource === "clerk.house.gov" && p.photos.length > 2);
    if (house) {
      KYC.profile.open(house.id);
      check("a House portrait is the House's",
        line().textContent === "Photo: U.S. House of Representatives", line().textContent);
      // A fallback that loads in the first one's place is another
      // photograph, credited by the host that serves it.
      const photo = D.getElementById("profileModalPhoto");
      KYC.handleImageFallback(photo, house.id);
      photo.dispatchEvent(new window.Event("load"));
      const host = new URL(house.photos[1]).hostname;
      check("a fallback photograph is credited to its own source",
        line().textContent === "Photo: " + window.kycBuildMeta.photoCredits[host],
        line().textContent);
      KYC.profile.close();
    }

    const campaign = shown.find((p) => p.photoSource === "campaign-site");
    if (campaign) {
      KYC.profile.open(campaign.id);
      check("a campaign's photograph is credited to its website, linked",
        /^Photo: the campaign's website/.test(line().textContent) &&
          !!line().querySelector("a[href^='https://']"), line().textContent);
      KYC.profile.close();
    }

    // A nominee who sits in their state's legislature: its own photograph,
    // credited to the legislature by its name and linked to their page.
    const legislature = shown.find((p) => p.photoSource === "state-legislature");
    if (legislature) {
      KYC.profile.open(legislature.id);
      check("a legislature's photograph is credited to it by name, linked to the member's page",
        line().textContent === "Photo: " + legislature.photoCredit.by &&
          !!line().querySelector('a[href="' + legislature.photoCredit.page + '"]'),
        line().textContent);
      KYC.profile.close();
    }

    const silhouette = window.legislatorsData.find((p) => (p.photos || [])[0] === "placeholder");
    if (silhouette) {
      KYC.profile.open(silhouette.id);
      check("the silhouette is credited to no one", line().hidden && !line().textContent);
      KYC.profile.close();
    }

    const hostile = KYC.photoCreditHtml({ by: '<img src=x onerror="1">', licence: "CC BY 4.0",
      licenceUrl: "javascript:alert(1)", page: "https://commons.wikimedia.org/wiki/File:X.jpg",
      via: "Wikimedia Commons" });
    check("a credit is escaped, and links only http(s)",
      !/<img/.test(hostile) && !/javascript:/.test(hostile) && /CC BY 4\.0/.test(hostile), hostile);
    // A licence asking for an author the file's page does not name says so,
    // and still links the file's page; it never prints a placeholder name.
    const unrecorded = KYC.photoCreditHtml({ by: null, licence: "CC BY-SA 4.0",
      page: "https://commons.wikimedia.org/wiki/File:Judge_Moore.jpg", via: "Wikimedia Commons",
      authorUnrecorded: true });
    check("a credit with no recorded author says so, and links the file",
      /^Photo: author not recorded on Commons, /.test(unrecorded.replace(/<[^>]+>/g, "")) &&
        /File:Judge_Moore\.jpg/.test(unrecorded), unrecorded);
    const shownCredits = window.legislatorsData
      .map((p) => KYC.photoCreditHtml(p.photoCredit).replace(/<[^>]+>/g, ""))
      .filter(Boolean);
    check("no credit prints a doubled phrase, a file name or an uploader's sentence",
      shownCredits.length > 0 && shownCredits.every((t) =>
        !/Unknown author Unknown author|\.jpe?g\s*:|I do not know|uploader|PDM-owner/i.test(t)),
      shownCredits.filter((t) => /Unknown author Unknown|\.jpe?g\s*:|I do not know/i.test(t))[0]);
    const profileJs = fs.readFileSync(path.join(SITE, "assets", "kyc-profile.js"), "utf8");
    check("the dialog sets its portrait through setPortrait",
      /KYC\.setPortrait\(photo, item, "116px"\)/.test(profileJs) && !/photo\.src\s*=/.test(profileJs));
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
    // While the sitting Congress's rosters are published (from January 3
    // there are none for some weeks, and no profile lists a committee).
    const rosters = window.legislatorsData.some((p) => (p.committeeList || []).length);
    check("committee text is searchable", !rosters || cards().length > 0,
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
    check("the Congress named is the data's, not a typed number",
      [...D.querySelectorAll("[data-congress]")].every((el) =>
        el.textContent === window.kycBuildMeta.congress + "th Congress"),
      [...D.querySelectorAll("[data-congress]")].map((el) => el.textContent).join(" | "));
    check("every card is someone currently in Congress",
      members.every((c) => KYC.seated(KYC.byId(c.getAttribute("data-id")))));
    check("the filter is in the URL", /role=member/.test(window.location.hash),
      window.location.hash);

    D.querySelector('[data-group="chamber"][data-value="Senate"]').click();
    check("it composes with chamber", cards().length === 100,
      `${cards().length} senators`);
    D.querySelector('[data-group="chamber"][data-value="all"]').click();

    D.querySelector('[data-group="role"][data-value="candidate"]').click();
    // A 2026 incumbent who has left Congress is in neither, and shows under
    // "all" only while on a ballot (the grid hides who is off it).
    const formers = window.legislatorsData.filter((p) => p.formerMember &&
      !KYC.cards.offBallot(p)).length;
    check("challengers filter is the complement",
      announced(D) === total - memberTotal - formers, `${announced(D)}`);
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

  suite("index.html — says what it is and where to start", () => {
    // It opened on filter chips, with no heading, and on a phone no name.
    const h1 = [...D.querySelectorAll("h1")];
    check("one h1, naming what the site answers", h1.length === 1 && /represents you/.test(h1[0].textContent),
      h1.map((h) => h.textContent).join(" | "));
    const intro = D.getElementById("introState");
    const filter = D.getElementById("stateSelect");
    check("the intro offers every state the filter does",
      !!intro && intro.options.length === filter.options.length &&
        [...intro.options].slice(1).every((o, i) => o.value === filter.options[i + 1].value),
      intro && intro.options.length + " vs " + filter.options.length);
    // Outside the scroller it stayed pinned, 200px above the results, on a
    // desktop; inside it, it scrolls away with them.
    check("the intro scrolls with the results",
      !!intro && !!intro.closest(".content.scroll-y") &&
        (intro.compareDocumentPosition(D.getElementById("results")) & 4) !== 0);
    // Navigating on "change" left the page on the first arrow key.
    const form = D.getElementById("introForm");
    check("the picker opens a state's page only when asked",
      !!form && !!form.querySelector('button[type="submit"]') && form.contains(intro));
  });

  suite("index.html — a state's name finds its people", () => {
    // "Pennsylvania" found 14 of 61, the ones that mentioned it in their text.
    const pa = window.legislatorsData.filter((p) => p.state === "PA");
    check("every Pennsylvania profile matches 'Pennsylvania'",
      pa.length > 0 && pa.every((p) => KYC.matchesQuery(p, "pennsylvania")));
    // The whole name only (rule 5): indexed as text, "virginia" found all of
    // West Virginia and "kansas" found Arkansas.
    const blank = (state) => ({ state: state, name: "Pat Example", quality: {} });
    check("a state's name finds that state, not a longer one containing it",
      KYC.matchesQuery(blank("VA"), "virginia") && !KYC.matchesQuery(blank("WV"), "virginia") &&
        KYC.matchesQuery(blank("WV"), "west virginia") &&
        KYC.matchesQuery(blank("KS"), "kansas") && !KYC.matchesQuery(blank("AR"), "kansas"));
  });

  suite("index.html — profile dialog", () => {
    const first = D.getElementById("results").querySelector(".card");
    const id = first.getAttribute("data-id");
    first.click();

    const modal = D.getElementById("profileModal");
    check("dialog opens on card click", modal && !modal.hidden);
    check("dialog is labelled", modal.getAttribute("aria-labelledby") === "profileModalName");
    // The full-screen backdrop took first focus: "Close profile, button".
    const scrim = modal.querySelector(".modal-scrim");
    check("focus lands inside the dialog, not on the invisible backdrop",
      D.activeElement !== scrim && scrim.getAttribute("tabindex") === "-1" &&
        scrim.getAttribute("aria-hidden") === "true",
      D.activeElement && D.activeElement.className);
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

  suite("index.html — public offices held", () => {
    const rows = (p) => (p.politicalHistory || {}).rows || [];
    const member = window.legislatorsData.find((p) => KYC.seated(p) &&
      rows(p).some((r) => r.congress) && rows(p).some((r) => !r.congress));
    check("a member with Congress and another office exists", !!member);
    if (member) {
      KYC.profile.open(member.id);
      const panel = D.getElementById("profileModalHeld");
      const shown = [...panel.querySelectorAll(".held-row")];
      check("one row per office, newest first", shown.length === rows(member).length &&
        shown.every((li, i) => li.querySelector(".held-office").textContent === rows(member)[i].office));
      check("the years are the record's",
        shown.every((li, i) => li.querySelector(".held-years").textContent
          .indexOf(KYC.heldYears(rows(member)[i])) === 0));
      check("a seat in Congress names its state, never a code",
        shown.filter((li, i) => rows(member)[i].congress).every((li) =>
          !/^[A-Z]{2}\b/.test((li.querySelector(".held-where") || {}).textContent || "")));
      const source = panel.querySelector(".held-source");
      check("the sources are named and the person's item linked",
        /congress-legislators/.test(source.textContent) &&
        !!source.querySelector('a[href="https://www.wikidata.org/wiki/' +
          member.politicalHistory.wikidata + '"]'));
      check("its links open safely", [...source.querySelectorAll("a")]
        .every((a) => a.target === "_blank" && /noopener/.test(a.rel)));
      // Two sources' agreement is not a complete record, and the list says
      // so before it starts (an officer's earlier office was missing).
      const scope = panel.querySelector(".held-scope");
      check("the list says other offices may be missing, before it starts", !!scope &&
        /others may be missing/.test(scope.textContent) &&
        !!(scope.compareDocumentPosition(panel.querySelector(".held-list")) & 4));
      KYC.profile.close();
    }
    const atLarge = window.legislatorsData.find((p) => rows(p).some((r) => r.congress && r.district === 0));
    check("an at-large seat exists in the records", !!atLarge);
    if (atLarge) {
      KYC.profile.open(atLarge.id);
      check("an at-large seat says so (district 0 is not an absence)",
        /, at large/.test(D.getElementById("profileModalHeld").textContent));
      KYC.profile.close();
    }
    const differs = window.legislatorsData.find((p) => rows(p).some((r) => r.agree));
    check("a row whose sources differ exists", !!differs);
    if (differs) {
      KYC.profile.open(differs.id);
      const note = D.getElementById("profileModalHeld").querySelector(".held-note");
      check("where the sources differ, the row says how",
        !!note && /Wikidata/.test(note.getAttribute("title")));
      // A phone shows no tooltip: the note's words are on the page (FEDERAL-20).
      check("and says it in visible words, not only a tooltip",
        !!note && /Wikidata/.test(note.textContent) && /Wikipedia/.test(note.textContent), note && note.textContent);
      KYC.profile.close();
    }
    const unlinked = window.legislatorsData.find((p) => p.isCandidate && !p.politicalHistory);
    if (unlinked) {
      KYC.profile.open(unlinked.id);
      const absent = D.getElementById("profileModalHeld").querySelector(".kyc-absent");
      check("no record is a claim about this site, and says why (rule 19)",
        !!absent && /No linked record/.test(absent.textContent) &&
        /election page/.test(absent.getAttribute("title")));
      KYC.profile.close();
    }
    const host = window.legislatorsData.find((p) => p.politicalHistory);
    const kept = host.politicalHistory;
    host.politicalHistory = { rows: [{ office: '<img src=x onerror=alert(1)>', where: "<b>x</b>",
      from: "2001", to: "2003" }], wikidata: '"><b>' };
    KYC.profile.open(host.id);
    // Elements, not markup: a serialised attribute keeps "<" as it is.
    const held = D.getElementById("profileModalHeld");
    check("an office's name is escaped, not interpreted", !held.querySelector("img, b") &&
      held.querySelector(".held-office").textContent === "<img src=x onerror=alert(1)>");
    KYC.profile.close();
    host.politicalHistory = kept;
    const cards = [...D.getElementById("results").querySelectorAll(".card")];
    const lined = cards.filter((c) => c.querySelector(".card-held"));
    check("cards name an earlier office", lined.length > 0);
    check("each from the person's own record", lined.every((c) => rows(KYC.byId(c.getAttribute("data-id")))
      .some((r) => KYC.heldText(r) === c.querySelector(".card-held").getAttribute("title"))));
    // 91 sitting representatives once read "Fmr. U.S. Representative" under
    // their own seat, because redistricting renumbered it.
    check("never a seat in the card's own chamber", lined.every((c) => {
      const item = KYC.byId(c.getAttribute("data-id"));
      const senate = /senate/i.test(item.chamber);
      return !(senate ? /^U\.S\. Senator\b/ : /^(U\.S\. Representative|Delegate|Resident Commissioner)\b/)
        .test(c.querySelector(".card-held").getAttribute("title"));
    }));
    const climbing = window.legislatorsData.find((p) => /senate/i.test(p.chamber) && p.isCandidate &&
      rows(p).some((r) => r.congress && r.current && r.office === "U.S. Representative"));
    if (climbing) {
      const tmp = D.createElement("div");
      tmp.innerHTML = KYC.cards.card(climbing);
      check("a representative running for the Senate is shown as one, not as a former one",
        (tmp.querySelector(".card-held") || {}).textContent === "U.S. Representative",
        (tmp.querySelector(".card-held") || {}).textContent);
    }
    const burlington = { office: "Mayor of Burlington", where: "Burlington, Vermont", from: "1981", to: "1989" };
    check("a place the office already names is not said twice",
      KYC.heldText(burlington) === "Mayor of Burlington, Vermont, 1981–1989", KYC.heldText(burlington));
  });

  suite("index.html — contact & links", () => {
    // Rule 24: CAND_40 and CAND_43 showed a rugby player and a kayaker from
    // Special:FilePath/<Name>.jpg, and G000553's chain ended in the singer.
    const guessed = window.legislatorsData.filter((p) =>
      (p.photos || []).some((u) => /Special:(FilePath|Redirect)/.test(u)));
    check("no portrait chain holds a file reached by a name",
      guessed.length === 0, guessed.map((p) => p.id).slice(0, 5).join(" "));
    const rosters = window.legislatorsData.some((p) => (p.committeeList || []).length);
    const member = window.legislatorsData.find(
      (p) => KYC.seated(p) && p.website && p.social && p.social.twitter &&
        (!rosters || (p.committeeList && p.committeeList.length)) && (p.refs || {}).govtrack);
    check("a member with a site, accounts, committees and ids exists", !!member);
    if (member) {
      KYC.profile.open(member.id);
      const panel = D.getElementById("profileModalContactPanel");
      check("contact panel shows for a member", panel && !panel.hidden);
      const links = [...D.getElementById("profileModalContact").querySelectorAll("a")];
      check("official website is linked",
        links.some((a) => a.href === member.website || a.href === member.website + "/"));
      // By the id where the source holds one: it follows a renamed handle
      // (RepMikeJohnson, "not found", is SpeakerJohnson).
      check("X account is linked from its id, else the handle",
        links.some((a) => a.href === (member.social.twitter_id
          ? "https://x.com/i/user/" + encodeURIComponent(member.social.twitter_id)
          : "https://x.com/" + encodeURIComponent(member.social.twitter))));
      check("only one X chip", links.filter((a) => /^https:\/\/x\.com\//.test(a.href)).length === 1);
      // An id-linked chip names no handle: the source's may be the old one.
      const byId = links.filter((a) => /^https:\/\/x\.com\/i\/user\//.test(a.href));
      check("an X chip linked by id names no handle in its tooltip",
        byId.every((a) => !/@/.test(a.title || "")), byId.map((a) => a.title).join(" | "));
      check("GovTrack is linked from the id, not the name",
        links.some((a) => a.href.endsWith("/congress/members/" + member.refs.govtrack)));
      check("every outbound link opens safely",
        links.filter((a) => /^https?:/.test(a.href))
          .every((a) => a.target === "_blank" && /noopener/.test(a.rel)));
      const committees = D.getElementById("profileModalCommittees");
      const table = KYC.meta().committees || {};
      check("committees come from the structured rosters",
        !rosters ? /have not been published yet/.test(committees.textContent) :
          committees.querySelectorAll(".committee").length ===
            member.committeeList.filter((c) => !(table[c.code] || {}).parent).length);
      KYC.profile.close();
    }
    // A leadership post congress-legislators records for a sitting member
    // is on their profile (GUIDE-12); a member who holds none shows none.
    const leader = window.legislatorsData.find((p) => KYC.seated(p) && (p.leadership || []).length);
    if (leader) {
      KYC.profile.open(leader.id);
      const posts = D.querySelector("#profileModalCommittees .leadership-posts");
      check("a member's leadership posts are on their profile",
        !!posts && leader.leadership.every((t) => posts.textContent.includes(t)),
        leader.name + ": " + (posts ? posts.textContent : "none"));
      KYC.profile.close();
      const plain = window.legislatorsData.find((p) => KYC.seated(p) && !p.isCandidate &&
        !(p.leadership || []).length);
      KYC.profile.open(plain.id);
      check("a member with no post shows none",
        !D.querySelector("#profileModalCommittees .leadership-posts"));
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
    // A YouTube value is linked by its shape: 88 of 90 members' links were
    // youtube.com/user/<value>, 404 for handles and channel ids alike.
    [[{ youtube: "@RepAlford" }, "https://www.youtube.com/@RepAlford"],
      [{ youtube_id: "UCjy0W7sksMz37IYY27tAZNQ", youtube: "RepX" },
        "https://www.youtube.com/channel/UCjy0W7sksMz37IYY27tAZNQ"],
      [{ youtube: "adamschiff" }, "https://www.youtube.com/user/adamschiff"]].forEach(([social, want]) => {
      if (!member) return;
      const kept = member.social;
      member.social = social;
      KYC.profile.open(member.id);
      const yt = [...D.getElementById("profileModalContact").querySelectorAll("a")]
        .filter((a) => /youtube\.com/.test(a.href)).map((a) => a.href);
      check("a YouTube " + Object.keys(social)[0] + " is linked as " + want,
        yt.length === 1 && yt[0] === want, yt.join(" "));
      KYC.profile.close();
      member.social = kept;
    });
    // The funding split: each label on one line with its share, and what the
    // shares are of when adjustments put the receipts below the parts.
    const split = window.legislatorsData.find((p) => p.fundingBreakdown &&
      Object.keys(p.fundingBreakdown).length > 1);
    check("a profile with a funding split exists", !!split);
    if (split) {
      KYC.profile.open(split.id);
      const box = D.getElementById("profileModalFunding");
      const parts = [...box.querySelectorAll(".funding-part")].map((s) => s.textContent);
      check("every funding pair is one unbreakable part",
        parts.length === Object.keys(split.fundingBreakdown).length &&
          parts.join(", ") === split.funding_sources, parts.join(" | "));
      check("no base note where the shares are of the receipts shown",
        !!split.fundingBase === !!box.querySelector(".funding-base"));
      KYC.profile.close();
      const kept = [split.fundingBase, split.receipts];
      split.fundingBase = "$3,968,600.00";
      split.receipts = "$3,194,222.05";
      KYC.profile.open(split.id);
      const note = D.querySelector("#profileModalFunding .funding-base");
      check("a base above the receipts says what the shares are of",
        note && /\$3,968,600\.00/.test(note.textContent) && /\$3,194,222\.05/.test(note.textContent),
        note ? note.textContent : "no note");
      KYC.profile.close();
      [split.fundingBase, split.receipts] = kept;
      if (kept[0] === undefined) delete split.fundingBase;
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

  /* TRUST-05: members' education, careers and platform were the rosters'
   * typed text, unsourced and unevenly worded ("Anti-abortion legislation"
   * for one member, "Pro-life advocacy" for four others). Now each comes
   * from a source tied to the member by id, and says which (rule 86);
   * PERSONA-14 and PROFILES-16 add their offices at home and a checked
   * contact page. */
  suite("index.html — a member's biography, platform and offices, sourced", () => {
    const SOURCED = { "congressional-directory": 1, "member-wikipedia": 1, "official-site": 1 };
    const members = window.legislatorsData.filter((p) => !p.isCandidate);
    const bare = [];
    members.forEach((p) => ["education", "previous_professions", "platforms"].forEach((f) => {
      if (KYC.hasValue(p, f) && p[f] && !SOURCED[(p.fieldSources || {})[f]]) bare.push(p.id + " " + f);
    }));
    check("no member's education, careers or platform is shown without its source",
      bare.length === 0, bare.slice(0, 5).join(", "));

    const host = members.find((p) => KYC.seated(p) && p.chamber === "House" && p.website);
    check("a House member exists to test", !!host);
    if (!host) return;
    const fields = {
      platforms: "Agriculture; Health Care, Medicare and Medicaid; Veterans",
      education: "B.A., Pacific Lutheran University, Tacoma, WA, 1987",
      // The Directory's own run, with a semicolon inside brackets that
      // separates nothing.
      previous_professions: "staffer, Chapel Hill Police department, 1987-2008; attorney " +
        "(admitted to the California Bar, 1977; admitted to the Idaho Bar, 1979); member, " +
        "Orange County Board of Commissioners, 2004-12 (chair, 2008-10)",
      phone: "202-225-1784",
      office: "2452 Rayburn House Office Building",
      officeAddress: "2452 Rayburn House Office Building, Washington, DC 20515-3304",
      quality: {}, officialIssuesUrl: host.website + "/issues", platformRead: "2026-10-18",
      fieldSources: { platforms: "official-site", education: "congressional-directory",
        previous_professions: "congressional-directory" },
      contactForm: host.website + "/contact/email-me", contactFormVia: "official-site",
      contactFormChecked: "2026-10-18",
      districtOffices: [
        { address: "2930 Wetmore Avenue", suite: "Suite 9F", city: "Everett", state: "WA",
          zip: "98201", phone: "425-252-3188", hours: "<b>M-F</b> 9-5" },
        { address: "119 North Commercial Street", city: "Bellingham", state: "WA",
          zip: "98225", phone: "360-733-4500" }],
      districtOfficesRead: "2026-10-18",
      platformFeatured: false,
    };
    const saved = {};
    Object.keys(fields).forEach((k) => { saved[k] = host[k]; host[k] = fields[k]; });
    delete host.__search;
    KYC.profile.open(host.id);
    const platform = D.getElementById("profileModalPlatform");
    const bullets = [...platform.querySelectorAll(".bullets li")].map((li) => li.textContent);
    check("the issues their site lists are one bullet each, split on semicolons",
      bullets.length === 3 && bullets[1] === "Health Care, Medicare and Medicaid", bullets.join(" | "));
    check("the platform says it is from their official website, with the date and the page",
      /Official site/.test(platform.textContent) && /official website lists/.test(platform.textContent) &&
        /Oct\. 18, 2026/.test(platform.textContent) &&
        [...platform.querySelectorAll("a")].some((a) => a.href === host.website + "/issues"));
    const education = D.getElementById("profileModalEducation");
    check("education is credited to the Congressional Directory",
      /Congressional Directory/.test(education.textContent) &&
        /Government Publishing Office/.test((education.querySelector(".field-source") || {}).title || ""));
    // The careers, entry by entry (the owner's request of 2026-10-26).
    const careers = D.getElementById("profileModalCareers");
    const jobs = [...careers.querySelectorAll(".field-list li")].map((li) => li.textContent);
    check("careers are a list, one entry a line, split only where the source separates them",
      jobs.length === 3 && jobs[0] === "Staffer, Chapel Hill Police department, 1987-2008" &&
        jobs[1] === "Attorney (admitted to the California Bar, 1977; admitted to the Idaho Bar, 1979)" &&
        jobs[2] === "Member, Orange County Board of Commissioners, 2004-12 (chair, 2008-10)",
      jobs.join(" | "));
    check("the careers' source is said once, after the list",
      careers.querySelectorAll(".field-source").length === 1 &&
        careers.lastElementChild.classList.contains("field-source") &&
        /Congressional Directory/.test(careers.lastElementChild.textContent));
    check("a field of one entry stays a plain line",
      !education.querySelector("ul") && /^B\.A\., Pacific Lutheran/.test(education.textContent));

    const contact = D.getElementById("profileModalContact");
    check("a House member's offices at home are listed, with the casework line",
      /District offices/.test(contact.textContent) &&
        /For help with a federal agency/.test(contact.textContent) &&
        /Social Security, the VA, the IRS/.test(contact.textContent) &&
        contact.querySelectorAll(".home-office").length === 2);
    const capitol = contact.querySelector(".washington-office");
    check("the Washington office gives the record's whole address, Washington, DC and the ZIP code",
      !!capitol && /Washington office/.test(capitol.querySelector(".office-name").textContent) &&
        capitol.querySelector(".office-address").textContent.replace(/^Address: /, "") ===
          "2452 Rayburn House Office Building Washington, DC 20515-3304" &&
        capitol.querySelector(".office-address .office-city").textContent ===
          "Washington, DC 20515-3304",
      capitol && capitol.textContent);
    check("its phone is a number to dial beside a phone icon, never the address's pin",
      !!capitol && capitol.querySelector(".office-phone a").getAttribute("href") === "tel:2022251784" &&
        !!capitol.querySelector('.office-phone use[href="#i-phone"]') &&
        !!capitol.querySelector('.office-address use[href="#i-pin"]') &&
        !capitol.querySelector('.office-phone use[href="#i-pin"]'));
    const cards = [...contact.querySelectorAll(".offices > .office")];
    check("every office, Washington's and those at home, has one layout: name, address, phone",
      cards.length === 3 && cards.every((c) => c.firstElementChild.classList.contains("office-name") &&
        !!c.querySelector(".office-address use[href='#i-pin']") &&
        !!c.querySelector(".office-phone a[href^='tel:']")) &&
        cards[1].querySelector(".office-name").textContent === "Everett" &&
        cards[1].querySelector(".office-city").textContent === "Everett, WA 98201",
      cards.map((c) => c.textContent).join(" | "));
    check("the casework note comes before the offices at home",
      !!contact.querySelector(".casework-note + .offices .home-office"));
    check("each office's phone can be dialled",
      [...contact.querySelectorAll(".home-office a")].map((a) => a.getAttribute("href")).join(" ") ===
        "tel:4252523188 tel:3607334500");
    check("an office's hours are text, never markup, beside a clock",
      !contact.querySelector(".home-office b") && /<b>M-F<\/b>/.test(contact.textContent) &&
        !!contact.querySelector(".office-hours use[href='#i-clock']"));
    const credits = contact.querySelectorAll(".field-credit");
    check("the offices say where they come from and when, once, after every office",
      credits.length === 1 && /congress-legislators: the Washington office from its record of this term, the district offices as read on Oct\. 18, 2026/
        .test(credits[0].textContent) &&
        [...contact.querySelectorAll(".office")].every((o) =>
          o.compareDocumentPosition(credits[0]) & window.Node.DOCUMENT_POSITION_FOLLOWING),
      credits.length && credits[0].textContent);
    const form = [...contact.querySelectorAll("a")].find((a) => /Write to their office/.test(a.textContent));
    check("a contact page from their own site is the way to write to the office, and says it was checked",
      !!form && form.href === host.website + "/contact/email-me" && /checked on Oct\. 18, 2026/.test(form.title) &&
        !!form.closest(".links-row") && form.closest(".links-row") === contact.firstElementChild);
    KYC.profile.close();

    // Read, and their site lists no issues: said as that, with the site.
    host.platforms = "No data";
    host.quality = { platforms: "not_listed" };
    host.fieldSources = {};
    KYC.profile.open(host.id);
    check("a site with no issues list reads 'Not listed on their official site', linked",
      /Not listed on their official site/.test(platform.textContent) && !/No data/.test(platform.textContent) &&
        [...platform.querySelectorAll("a")].some((a) => a.href.replace(/\/$/, "") === host.website.replace(/\/$/, "")),
      platform.textContent);
    check("and it is not searchable as a platform", !KYC.matchesQuery(host, "not listed on their official"));
    KYC.profile.close();

    // An issues page with no list this site could read: linked, never
    // called empty.
    host.quality = { platforms: "see_site" };
    host.officialIssuesUrl = host.website + "/issues/";
    delete host.__search;
    KYC.profile.open(host.id);
    check("an issues page with no list read is linked, not called empty",
      /issues page/.test(platform.textContent) && !/Not listed/.test(platform.textContent) &&
        !/No data/.test(platform.textContent) &&
        [...platform.querySelectorAll("a")].some((a) => a.href === host.website + "/issues/"),
      platform.textContent);
    KYC.profile.close();

    // Issue pages only from the home page, too few to list: the website,
    // never an "issues page" (Stansbury's, before the review of PR #106).
    host.quality = { platforms: "see_home" };
    host.officialIssuesUrl = host.website;
    delete host.__search;
    KYC.profile.open(host.id);
    check("issue pages too few to list link the website, never 'their issues page'",
      /On their official website/.test(platform.textContent) && !/issues page/.test(platform.textContent) &&
        !/No data/.test(platform.textContent) &&
        [...platform.querySelectorAll("a")].some((a) => a.textContent === "their official website"),
      platform.textContent);
    check("and that is not searchable as a platform", !KYC.matchesQuery(host, "on their official website"));
    KYC.profile.close();
    host.quality = { platforms: "see_site" };

    // The page linked is the home page: called the website, never "their
    // issues page" (Stansbury's, before the review of PR #106).
    host.officialIssuesUrl = host.website.replace(/\/$/, "");
    KYC.profile.open(host.id);
    const homeLink = [...platform.querySelectorAll("a")].find((a) =>
      a.href.replace(/\/$/, "") === host.website.replace(/\/$/, ""));
    check("a home page linked for the issues is called their official website",
      !!homeLink && homeLink.textContent === "their official website" &&
        !/their issues page/.test(platform.textContent), platform.textContent);
    KYC.profile.close();

    // A list read from the home page's own issue links is what it features,
    // not the site's whole list (Hoyer's home page showed five of nine).
    host.platforms = fields.platforms;
    host.quality = {};
    host.fieldSources = { platforms: "official-site" };
    host.platformFeatured = true;
    delete host.__search;
    KYC.profile.open(host.id);
    check("a home page's featured issues say so, and link the website",
      /home page features/.test(platform.textContent) && !/official website lists/.test(platform.textContent) &&
        /their official website/.test(platform.textContent) && !/read them there/.test(platform.textContent),
      platform.textContent);
    KYC.profile.close();
    Object.keys(saved).forEach((k) => {
      if (saved[k] === undefined) delete host[k]; else host[k] = saved[k];
    });
    delete host.__search;

    const senator = members.find((p) => KYC.seated(p) && p.chamber === "Senate");
    if (senator) {
      const kept = senator.districtOffices;
      senator.districtOffices = [{ address: "915 Second Avenue", city: "Seattle", state: "WA",
        phone: "206-553-5545" }];
      KYC.profile.open(senator.id);
      const text = D.getElementById("profileModalContact").textContent;
      check("a senator's are state offices", /State offices/.test(text) && /call a state office/.test(text) &&
        !/District offices/.test(text), text.slice(0, 200));
      KYC.profile.close();
      if (kept === undefined) delete senator.districtOffices; else senator.districtOffices = kept;
    }
    const withOffices = members.filter((p) => KYC.seated(p) && (p.districtOffices || []).length);
    check("the built profiles carry members' offices at home",
      withOffices.length > members.filter((p) => KYC.seated(p)).length / 2, withOffices.length);
  });

  /* PROFILES-18: a challenger's dialog opened on a wall of absences, with
   * "not a sitting member" twice and their opponents two phone screens
   * down. The race comes first, then the money, then the platform, then the
   * biography; panels only a member has are not shown. */
  suite("index.html — a challenger's profile leads with the race", () => {
    const challenger = window.legislatorsData.find((p) => p.isCandidate && !p.incumbentId &&
      (p.contestRaceId || p.raceId) && !p.politicalHistory);
    check("a challenger exists to test", !!challenger);
    if (!challenger) return;
    const saved = { education: challenger.education, quality: challenger.quality,
      previous_professions: challenger.previous_professions, birthdate: challenger.birthdate,
      age: challenger.age };
    challenger.education = "No data";
    challenger.previous_professions = "No data";
    challenger.birthdate = "Unknown";
    challenger.age = "Unknown";
    challenger.quality = Object.assign({}, challenger.quality,
      { education: "unknown", previous_professions: "unknown", birthdate: "unknown" });
    KYC.profile.open(challenger.id);
    const order = ["profileModalRacePanel", "profileModalFinancePanel", "profileModalPlatformPanel",
      "profileModalBioPanel"].map((id) => D.getElementById(id));
    const before = (a, b) => !!(a.compareDocumentPosition(b) & 4);
    check("race, then money, then platform, then biography",
      before(order[0], order[1]) && before(order[1], order[2]) && before(order[2], order[3]));
    check("no voting-record or committee panel for someone who holds no seat",
      D.getElementById("profileModalVotingPanel").hidden &&
        D.getElementById("profileModalCommitteesPanel").hidden);
    const bio = D.getElementById("profileModalBioPanel");
    const absent = D.getElementById("profileModalBioAbsent");
    check("the absent fields are said once, in one line",
      !absent.hidden && /No data/.test(absent.textContent) &&
        /age, education, previous careers or public offices held/.test(absent.textContent) &&
        [...bio.querySelectorAll(".kyc-absent")].filter((s) => !s.closest("[hidden]")).length === 1,
      absent.textContent);
    check("and the empty rows are not shown",
      D.getElementById("profileModalEducationField").hidden &&
        D.getElementById("profileModalCareersField").hidden &&
        D.getElementById("profileModalHeldPanel").hidden);
    KYC.profile.close();
    Object.assign(challenger, saved);

    // A member's dialog keeps its panels and its order.
    const member = window.legislatorsData.find((p) => KYC.seated(p) && !p.isCandidate);
    KYC.profile.open(member.id);
    check("a member's dialog shows the voting record and committees, biography first",
      !D.getElementById("profileModalVotingPanel").hidden &&
        !D.getElementById("profileModalCommitteesPanel").hidden &&
        before(D.getElementById("profileModalBioPanel"), D.getElementById("profileModalFinancePanel")) &&
        D.getElementById("profileModalBioAbsent").hidden);
    KYC.profile.close();
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
    delete host.__tiers;
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

    // A platform with commas inside its items (an official site's
    // "Telecommunications, technology, and digital privacy").
    const listed = window.legislatorsData.find((p) => !p.isCandidate && KYC.seated(p));
    if (listed) {
      const keep = { platforms: listed.platforms, quality: listed.quality, fieldSources: listed.fieldSources };
      listed.platforms = "Telecommunications, technology, and digital privacy; Veterans";
      listed.quality = {};
      listed.fieldSources = Object.assign({}, listed.fieldSources, { platforms: "official-site" });
      delete listed.__search;
      KYC.profile.open(listed.id);
      const items = [...D.querySelectorAll("#profileModalPlatform .bullets li")].map((li) => li.textContent);
      check("an item with commas inside it stays one bullet",
        items.includes("Telecommunications, technology, and digital privacy") &&
          !items.some((t) => /^(and|or) /.test(t)), items.join(" | "));
      KYC.profile.close();
      Object.assign(listed, keep);
      delete listed.__search;
    }

    const quoted = window.legislatorsData.find((p) => p.campaignQuote);
    check("built profiles carry campaign descriptions", !!quoted);
    const pictured = window.legislatorsData.filter((p) => p.photoSource === "campaign-site");
    // A challenger's, filed or curated (Brian Bengs's sat unused in the
    // cache); never a sitting member's, whose portrait comes by their id.
    check("a portrait from a campaign site is only ever a challenger's",
      pictured.every((p) => p.isCandidate && !p.bioguide),
      pictured.filter((p) => !p.isCandidate || p.bioguide).map((p) => p.id).join(","));
  });

  suite("index.html — in this race", () => {
    // A member with challengers still on the ballot: the dialog lists them.
    // The member must be contesting this seat: a member running elsewhere
    // (LA-5's, for the Senate), or seated since in a seat they won, is shown
    // that race instead.
    const race = window.kycRaces.find((r) => {
      const holder = KYC.byId(r.incumbentIds[0]) || {};
      return r.incumbentIds.length && r.candidateCount > 1 && r.settled &&
        !holder.contestLabel && (holder.contestRaceId || holder.raceId) === r.id;
    });
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
      // The race list kept grey silhouettes after the cards had initials
      // (VISUALS-16 review): one helper draws every row's (KYC.portraitThumb).
      const bare = rows.filter((r) => !KYC.hasPortrait(KYC.byId(r.getAttribute("data-goto"))));
      check("a race-mate with no portrait shows initials, never a silhouette",
        bare.every((r) => !r.querySelector("img") && r.querySelector(".thumb-monogram") &&
          r.querySelector(".thumb-monogram").textContent === KYC.monogram(KYC.byId(r.getAttribute("data-goto")).name)) &&
          rows.filter((r) => !bare.includes(r)).every((r) => !!r.querySelector("img")),
        `${bare.length} of ${rows.length} without a portrait`);
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

    // A curated candidate's roster status ("Primary Candidate / US
    // Representative") was written before the primary and contradicted the
    // result beside it; and no figure on the page is "as filed in the source
    // rosters" any more.
    const curated = window.legislatorsData.find((p) =>
      /^CAND_/.test(p.id) && p.raceStatus && p.status && p.status !== "Candidate");
    check("there is a curated candidate with a result to test", !!curated);
    if (curated) {
      KYC.profile.open(curated.id);
      const line = D.getElementById("profileModalStatus").textContent;
      check("a candidate's result replaces the roster's status text",
        line.indexOf(curated.status) === -1, line);
      check("no money is credited to the rosters",
        !/source rosters/.test(D.getElementById("profileModalSource").textContent));
      KYC.profile.close();
    }

    // Named, if at all, under a spelling that lost: off the ballot either way,
    // and said as that, not as "not on the primary ballot".
    const hedged = window.legislatorsData.filter((p) => p.raceStatusUnconfirmed);
    check("an unconfirmed absence reads 'Not on the November ballot'",
      hedged.length > 0 && hedged.every((p) => {
        const html = KYC.cards.statusBadge(p);
        return /Not on the November ballot/.test(html) && !/primary ballot/.test(html);
      }), hedged.length + " people");
    check("nobody whose page name lost is counted as running",
      !(window.kycRaces || []).some((r) => r.candidateIds.some((id) => {
        const p = KYC.byId(id);
        return p && p.raceStatusUnconfirmed && !KYC.cards.offBallot(p);
      })));

    // Rule 22: a nominee whose filing is under $5,000 has no profile but is
    // on the ballot. 54 decided races said "No challenger on the ballot".
    const unprofiled = (window.kycRaces || []).filter((r) => r.settled && r.candidateCount === 0 &&
      ((r.results || {}).belowThreshold || []).length);
    check("there are races whose only challengers are under the threshold", unprofiled.length > 0);
    const badly = unprofiled.filter((r) => {
      const html = KYC.cards.raceBadges(r);
      const n = r.results.otherNominees.length;
      return /No challenger on the ballot/.test(html) ||
        (html.indexOf(n + " challenger") === -1 && html.indexOf(n + " candidate") === -1) ||
        html.indexOf(n + " with no profile here") === -1;
    });
    check("each counts them as challengers and says they have no profile here",
      badly.length === 0, badly.slice(0, 3).map((r) => r.id + ": " + KYC.cards.raceBadges(r)).join(" | "));
    const noOne = (window.kycRaces || []).filter((r) => r.settled && !r.contested &&
      (r.results.nominees + r.results.otherNominees.length) > Math.max(1, r.incumbentIds.length));
    check("no decided race with a second nominee says it has no challenger", noOne.length === 0,
      noOne.slice(0, 5).map((r) => r.id).join(", "));

    // A curated profile that took over its FEC filing answers to the old id,
    // which shared links and odds.json labels still carry.
    // Not one a seated member also carries: the same person before their
    // record lists the id, which validate reports (seated-unlinked).
    const seatedIds = new Set(window.legislatorsData.filter((p) => KYC.seated(p))
      .map((p) => p.fecCandidateId).filter(Boolean));
    const merged = window.legislatorsData.filter((p) => /^CAND_/.test(p.id) && p.fecCandidateId &&
      !seatedIds.has(p.fecCandidateId));
    check("a curated profile answers to its own filing's id",
      merged.length > 0 && merged.every((p) => KYC.byId("FEC_" + p.fecCandidateId) === p),
      merged.filter((p) => KYC.byId("FEC_" + p.fecCandidateId) !== p).map((p) => p.name).join(", "));

    // A DW-NOMINATE score is a place on a left-right scale, never a party's
    // name: an independent read "Moderate Republican".
    const independent = window.legislatorsData.find((p) => KYC.seated(p) && p.party === "Independent" &&
      /DW-NOMINATE/.test(p.voting_alignment || ""));
    KYC.profile.open(independent.id);
    const voting = D.getElementById("profileModalVoting").textContent;
    const ticks = D.querySelectorAll("#profileModalVoting .ideology-peer").length;
    KYC.profile.close();
    // The track was a blue-to-red gradient under a caption saying the score
    // is not a party label (TRUST-12, VISUALS-05): neutral ink, with every
    // sitting member of the chamber as a tick to read the score against.
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    const track = (css.match(/\n\.ideology-track\s*\{[^}]*\}/) || [""])[0];
    check("the score's track is drawn in no party's colour",
      !!track && !/--party-|--split|gradient/.test(track), track.replace(/\s+/g, " "));
    check("and the chamber's members are ticks on it, counted in words",
      ticks > 50 && /Each tick is a sitting member of the (House|Senate)/.test(voting) &&
        /\d+ of \d+ score further left, \d+ further right/.test(voting), `${ticks} ticks`);
    check("an independent's score is in the scale's words, with its source and Congress",
      /of centre|near the centre/.test(voting) && !/Republican|Democrat/.test(voting) &&
        /Voteview/.test(voting) && /\d+(st|nd|rd|th) Congress/.test(voting), voting.replace(/\s+/g, " "));

    // Rule 27: a challenger is running for the seat, not representing it.
    const challenger = window.legislatorsData.find((p) => p.isCandidate);
    const seated = window.legislatorsData.find((p) => KYC.seated(p));
    KYC.profile.open(challenger.id);
    const meta = D.querySelector("#profileModal .modal-meta").textContent;
    check("a candidate's dialog says Running for, never Represents",
      /Running for/.test(meta) && !/Represents/.test(meta), meta.replace(/\s+/g, " "));
    KYC.profile.close();
    KYC.profile.open(seated.id);
    check("a member's dialog says Represents",
      /Represents/.test(D.querySelector("#profileModal .modal-meta").textContent));
    KYC.profile.close();
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
    // Shown by the name he goes by (his record's nickname); the roster's
    // legal name is an alias.
    const option = [...list.options].find((o) => o.value === "Jim Clyburn");
    check("suggestions keep the display name and carry the alias as a label",
      !!option && /James/.test(option.getAttribute("label") || ""),
      option && option.getAttribute("label"));
    check("the initial-first roster spelling is not suggested; the display name is",
      ![...list.options].some((o) => o.value === "C. Franklin") &&
      [...list.options].some((o) => o.value === "Scott Franklin"));
  });

  suite("index.html — alias search through the directory", () => {
    window.location.hash = "#/?q=" + encodeURIComponent("James Clyburn");
    window.dispatchEvent(new window.Event("hashchange"));
    const ids = [...D.getElementById("results").querySelectorAll(".card")]
      .map((c) => c.getAttribute("data-id"));
    check("a 'James Clyburn' search shows his card, and only his", ids.length === 1 && ids[0] === "C000537",
      ids.slice(0, 5).join(","));
    const card = D.querySelector('#results .card[data-id="C000537"]');
    check("and the card shows the display name", !!card && /Jim Clyburn/.test(card.textContent));
    window.location.hash = "#/";
    window.dispatchEvent(new window.Event("hashchange"));
  });

  suite("index.html — the map's old bug, checked on both pages", () => {
    // map.html rendered `item.net_worth` with textContent, so a profile with
    // no filing showed the literal placeholder sentence as if it were data.
    // The field itself is gone (rule 26): no profile carries a net worth, and
    // no dialog prints the roster's placeholder sentences anywhere.
    check("no profile carries a net-worth value",
      !window.legislatorsData.some((p) => "net_worth" in p));
    const member = window.legislatorsData.find((p) => !p.isCandidate);
    KYC.profile.open(member.id);
    const shown = D.getElementById("profileModal").textContent;
    check("no placeholder prose reaches the reader",
      !/No net worth disclosure|N\/A \(|Est\. net worth|Party Loyalty/.test(shown));
    KYC.profile.close();
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
    // In place where the code fits; in a callout or the territory strip
    // where it does not - but every one somewhere.
    const named = new Set([...D.querySelectorAll("#mapLabels .map-label")]
      .map((t) => t.textContent));
    const every = Object.keys(window.kycGeo.states).concat(window.kycGeo.territories.map((t) => t.code));
    check("every state and territory is named on the map",
      every.every((c) => named.has(c)), every.filter((c) => !named.has(c)).join(" "));
  });

  suite("map.html — modes", () => {
    const senateFill = D.querySelector('[data-state="TX"]').style.fill;
    check("Senate mode fills states", !!senateFill, senateFill);
    // Every key is a fill some state is drawn in, and every fill has a key:
    // "Independent" matched no state, and D.C.'s grey had no key.
    // A key names the fill it stands for (data-fill), hatched or not.
    const keys = [...D.querySelectorAll("#mapLegend .swatch")].map((s) => s.getAttribute("data-fill"));
    const fills = new Set([...D.querySelectorAll("#usMap .state")].map((s) => s.style.fill));
    check("each Senate key is a fill a state is drawn in, and each fill has a key",
      keys.every((k) => fills.has(k)) && [...fills].every((f) => keys.indexOf(f) !== -1),
      `keys ${keys.join(", ")} | fills ${[...fills].join(", ")}`);
    // Alaska's senator went through a top-four primary: "advanced", never
    // "renominated" (the card and profile already said so).
    D.querySelector('[data-mode="senate2026"]').click();
    const ak = D.querySelector('[data-state="AK"]');
    const akText = (ak && ak.getAttribute("aria-label")) || "";
    check("a senator through Alaska's top four reads 'advanced', not 'renominated'",
      !/renominated/.test(akText) && (!/nominee/i.test(akText) || /advanced/.test(akText)), akText);
    D.querySelector('[data-mode="senate"]').click();
    const dc = D.querySelector('[data-state="DC"]');
    check("D.C. says it has no senators, not '0R, 0D'",
      !!dc && /no senators/.test(dc.getAttribute("aria-label") || "") &&
        !/0R, 0D/.test(dc.getAttribute("aria-label") || ""), dc && dc.getAttribute("aria-label"));

    D.querySelector('[data-mode="house"]').click();
    // Five labelled steps, not a ramp with no values (VISUALS-09): a
    // delegation with members of both parties is a majority's tint, or the
    // hatched split when even, and its key says so.
    const houseKeys = [...D.querySelectorAll("#mapLegend .swatch")].map((s) => s.getAttribute("data-fill"));
    const mixed = [...D.querySelectorAll("#usMap .state")].filter((s) =>
      /House: [1-9]\d*R, [1-9]\d*D/.test(s.getAttribute("aria-label") || ""));
    check("House mode draws each delegation in a labelled step, by its majority",
      mixed.length > 5 && mixed.every((s) => {
        const m = /House: (\d+)R, (\d+)D/.exec(s.getAttribute("aria-label"));
        const want = +m[1] > +m[2] ? "var(--party-r-tint)" : +m[1] < +m[2] ? "var(--party-d-tint)"
          : KYC.svgFill("var(--split)");
        return s.style.fill === want && houseKeys.indexOf(want) !== -1;
      }),
      mixed.slice(0, 3).map((s) => s.getAttribute("aria-label") + " " + s.style.fill).join(" | "));
    check("legend follows the mode", /All R/.test(D.getElementById("mapLegend").textContent) &&
      /R majority/.test(D.getElementById("mapLegend").textContent));

    D.querySelector('[data-mode="senate2026"]').click();
    check("2026 mode marks a state with no race", (() => {
      // 65 senators' terms run past 2026, so plenty of states have no race.
      const none = [...D.querySelectorAll("#usMap .state")]
        .find((s) => /no Senate race/.test(s.getAttribute("aria-label") || ""));
      return !!none;
    })());
    check("mode buttons announce their state",
      D.querySelector('[data-mode="senate2026"]').getAttribute("aria-pressed") === "true");
    // Open seats and special elections were only in the hover text, which
    // a touch reader never sees (RACES-21): an open seat is its party's
    // tint, a special is outlined, and the legend has a key for each.
    const senateRaces = window.kycRaces.filter((r) => r.chamber === "Senate");
    const shapeOf = (code) => D.querySelector('#usMap .state[data-state="' + code + '"]');
    const legend26 = D.getElementById("mapLegend").textContent;
    const opens = senateRaces.filter((r) => r.openSeat);
    check("an open seat is drawn in its party's tint, and the legend names it",
      opens.every((r) => /-tint\)$/.test(shapeOf(r.state).style.fill) ||
        /party-i-fill|vacant-fill/.test(shapeOf(r.state).style.fill)) &&
        (!opens.length || /Open (Republican|Democratic) seat/.test(legend26)),
      senateRaces.filter((r) => r.openSeat).map((r) => r.state + " " + shapeOf(r.state).style.fill).join(" | "));
    check("a special election is outlined, and only a special",
      [...D.querySelectorAll("#usMap .state")].every((s) => s.classList.contains("is-marked") ===
        senateRaces.some((r) => r.special && r.state === s.getAttribute("data-state"))) &&
        (!senateRaces.some((r) => r.special) || /Special election/.test(legend26)),
      senateRaces.filter((r) => r.special).map((r) => r.state).join(", "));
    // The key was a 2px dashed border on a 10px square, which draws solid -
    // the look of a picked state's outline, so a reader who tapped Texas saw
    // it drawn like the key for a special election.
    const specialKey = D.querySelector('#mapLegend [data-fill="special"]');
    const mapCss = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    const ruleFor = (sel) => (mapCss.match(new RegExp("\\n" + sel.replace(/[.[\]"=]/g, "\\$&") + "\\s*\\{([^}]*)\\}")) || ["", ""])[1];
    check("the special-election key draws the map's dash, wide enough to show it",
      !senateRaces.some((r) => r.special) || (!!specialKey && specialKey.tagName.toLowerCase() === "svg" &&
        !!specialKey.querySelector("rect") && /stroke-dasharray:\s*5 3/.test(ruleFor(".map-legend .swatch-special rect")) &&
        /stroke-dasharray:\s*5 3/.test(ruleFor(".state.is-marked")) && /dashed outline/.test(legend26)),
      specialKey ? specialKey.outerHTML.slice(0, 80) : "no key");
    check("a picked state's outline is solid and thicker than a special's dash",
      /stroke-dasharray:\s*none/.test(ruleFor('.state[aria-pressed="true"]')) &&
        parseFloat((ruleFor('.state[aria-pressed="true"]').match(/stroke-width:\s*([\d.]+)/) || [])[1]) >
        parseFloat((ruleFor(".state.is-marked").match(/stroke-width:\s*([\d.]+)/) || [])[1]),
      ruleFor('.state[aria-pressed="true"]').replace(/\s+/g, " "));
    // John Cornyn and Bill Cassidy ran and lost; the label called them "not
    // running", like a retiree, while the panel beside it said "Lost primary".
    const label = (code) => (D.querySelector('#usMap [data-state="' + code + '"]') || {
      getAttribute: () => "" }).getAttribute("aria-label") || "";
    const lost = window.legislatorsData.filter((p) => !p.isCandidate &&
      /Senate/.test(p.chamber) && p.seatUp2026 && KYC.contestStatus(p) === "eliminated");
    check("a senator who lost the primary is labelled so, not 'not running'",
      lost.every((p) => /lost the primary/.test(label(p.state)) &&
        !/not running/.test(label(p.state))),
      lost.map((p) => label(p.state)).join(" | "));
    // Appointed to the seat, never elected or nominated to it.
    const appointees = window.legislatorsData.filter((p) => p.appointed &&
      /Senate/.test(p.chamber) && p.seatUp2026);
    check("an appointee is never called renominated or re-elected",
      appointees.length > 0 && appointees.every((p) =>
        !/renominated|re-elected|re-election/.test(label(p.state))),
      appointees.map((p) => label(p.state)).join(" | "));
    // White on the empty grey was 1.15:1 (light) and dark on dark 1.02:1.
    // "None" is hatched now, and the hatch is the callout's edge.
    const greys = [...D.querySelectorAll(".map-callout")].filter((c) => /none-fill|surface/.test(c.style.background || ""));
    check("a callout on the empty grey takes the page's text colour and an edge",
      greys.length > 0 && greys.every((c) => c.style.color === "var(--text)" &&
        (c.classList.contains("is-hatched") || /text-faint/.test(c.style.borderColor || ""))),
      greys.length + " grey callouts");
    check("party is an adjective in the label, as in the legend",
      ![...D.querySelectorAll("#usMap .state")].some((s) =>
        /Democrat seat/.test(s.getAttribute("aria-label") || "")));
    D.querySelector('[data-mode="senate"]').click();
    // On a phone the ten views are one menu (TECH-14): three rows of
    // buttons took the first 330-385px of the screen above the map.
    const menu = D.getElementById("mapModeSelect");
    const buttons = [...D.querySelectorAll(".map-views button[data-mode]")].map((b) => b.getAttribute("data-mode"));
    check("the phone's view menu offers every view the buttons do, in their groups",
      !!menu && [...menu.options].map((o) => o.value).join() === buttons.join() &&
        menu.querySelectorAll("optgroup").length === D.querySelectorAll(".map-view-group").length,
      menu && [...menu.options].map((o) => o.value).join());
    menu.value = "trifecta";
    menu.dispatchEvent(new window.Event("change", { bubbles: true }));
    check("picking a view from the menu switches the map and the address",
      D.querySelector('[data-mode="trifecta"]').getAttribute("aria-pressed") === "true" &&
        /mode=trifecta/.test(window.location.hash), window.location.hash);
    D.querySelector('[data-mode="house"]').click();
    check("and a button press shows in the menu", menu.value === "house", menu.value);
    check("each group of buttons says what it is, on the page",
      [...D.querySelectorAll(".map-view-group")].every((g) => {
        const kicker = g.querySelector(".map-view-kicker");
        return kicker && kicker.textContent.trim() &&
          g.querySelector(".segmented").getAttribute("aria-labelledby") === kicker.id;
      }));
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

    // The 2026 race view leads with the race: Texas's led with John
    // Cornyn, "Lost primary", and folded its nominees away under "2026
    // challengers" (VISUALS-10). The delegation views keep who is seated
    // first (rule 27).
    D.querySelector('[data-mode="senate2026"]').click();
    const panel = D.getElementById("delegation");
    const race26 = window.kycRaces.find((r) => r.chamber === "Senate" && r.state === "TX");
    const stillIn = [...panel.querySelectorAll(".panel-subhead")].find((h) => /Still in the race/.test(h.textContent));
    const heldBy = [...panel.querySelectorAll(".panel-subhead")].find((h) => /held by|Seat held/i.test(h.textContent));
    check("the 2026 race view lists the people still in the race first, open",
      !!race26 && !!stillIn && !panel.querySelector("#showChallengers") &&
        (!heldBy || (stillIn.compareDocumentPosition(heldBy) & 4)) &&
        [...panel.querySelectorAll(".person-row")].filter((r) => !r.closest("[hidden]")).length >= 2,
      [...panel.querySelectorAll(".panel-subhead")].map((h) => h.textContent.trim()).join(" | "));

    /* The rows under the race's heading: up to the next heading or block. */
    const raceRows = () => {
      const head = panel.querySelector(".panel-subhead.race-people");
      const rows = [];
      for (let el = head && head.nextElementSibling; el; el = el.nextElementSibling) {
        if (!el.classList.contains("person-row")) break;
        rows.push(el);
      }
      return { head, rows };
    };
    const pick = (code) => D.querySelector('#usMap [data-state="' + code + '"]')
      .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    // The first race-first list took only filers: every renominated senator
    // - 25 of the 35 seats - was left out of "Still in the race" and its
    // count, and named only under "Seat held by", below the markets.
    const renominated = window.kycRaces.filter((r) => r.chamber === "Senate" && !r.special)
      .map((r) => ({ race: r, holder: KYC.byId(r.incumbentIds[0]) }))
      .filter((x) => x.holder && KYC.seated(x.holder) && x.holder.raceStatus === "nominee" &&
        !x.holder.contestRaceId);
    if (oldCongressSits(window) && renominated.length) {
      const failed = [];
      renominated.forEach(({ race, holder }) => {
        pick(race.state);
        const { head, rows } = raceRows();
        const ids = rows.map((r) => r.getAttribute("data-id"));
        const unprofiled = KYC.cards.unprofiledNames(race);
        const count = head && parseInt(head.querySelector("span").textContent, 10);
        const heldBy = [...panel.querySelectorAll(".panel-subhead")].find((h) => /Seat held by/.test(h.textContent));
        const twice = heldBy && [...panel.querySelectorAll('.person-row[data-id="' + holder.id + '"]')].length > 1;
        if (!head || ids[0] !== holder.id || count !== ids.length + unprofiled.none.length + unprofiled.maybe.length ||
            twice) {
          failed.push(race.state + ": " + (head ? head.textContent.trim() : "no heading") + " [" + ids.join(",") + "]");
        }
      });
      check("a renominated senator is in the race's list, first, and in its count", failed.length === 0,
        failed.slice(0, 4).join(" | ") || renominated.length + " seats");
      // The heading says what the list holds once the votes are cast (rule 63).
      pick(renominated[0].race.state);
      check("the race's heading is 'Still in the race' before Election Day",
        /^Still in the race/.test(raceRows().head.textContent.trim()), raceRows().head.textContent);
    }
    pick("TX");
    // The unsettled filers and the page their statuses come from sit with
    // the race, before the markets and the seat's holder.
    const kids = [...panel.children];
    const at = (sel) => kids.findIndex((el) => el.matches(sel));
    const markets = at(".odds");
    check("the race's source and its unsettled filers come before its markets",
      markets === -1 || ((at(".race-results") === -1 || at(".race-results") < markets) &&
        (at("#showUnsure") === -1 || at("#showUnsure") < markets)),
      kids.map((el) => el.className || el.tagName).join(" | "));
    // Beside the people the markets are closed until opened (TRUST-14).
    check("the panel's markets are closed until opened",
      [...panel.querySelectorAll(".odds")].every((o) => o.tagName === "DETAILS" && !o.open),
      [...panel.querySelectorAll(".odds")].map((o) => o.tagName).join(","));
    // A row with no portrait shows the person's initials, as a card does,
    // never a grey silhouette (VISUALS-16).
    D.querySelector('[data-mode="house"]').click();
    const opener = D.getElementById("showChallengers");
    if (opener) opener.click();
    const panelRows = [...panel.querySelectorAll(".person-row")];
    const silhouettes = panelRows.filter((r) => {
      const img = r.querySelector("img");
      return img && !KYC.hasPortrait(KYC.byId(r.getAttribute("data-id")));
    });
    const discs = panelRows.filter((r) => r.querySelector(".thumb-monogram"));
    check("a panel row with no portrait shows initials, never a silhouette",
      silhouettes.length === 0 && discs.every((r) => r.querySelector(".thumb-monogram").textContent ===
        KYC.monogram(KYC.byId(r.getAttribute("data-id")).name)),
      `${silhouettes.length} silhouettes, ${discs.length} discs of ${panelRows.length} rows`);
    D.querySelector('[data-mode="senate"]').click();
  });

  suite("map.html — the state picker and the empty panel", () => {
    // D.C. was listed twice, and every option a bare code (VISUALS-V2).
    const options = [...D.querySelectorAll("#mapStateSelect option")].filter((o) => o.value);
    const values = options.map((o) => o.value);
    check("each place once, by name and code",
      new Set(values).size === values.length && values.length === 56 &&
        options.every((o) => o.textContent === KYC.stateName(o.value) + " (" + o.value + ")"),
      `${values.length} options; ${options.slice(0, 3).map((o) => o.textContent).join(", ")}`);
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    // A blank grey pill sat in the panel before a state was picked (VISUALS-11).
    check("the panel's counts take no room while empty", /#panelCounts:empty\s*\{\s*display:\s*none/.test(css));
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
    // Rule 26: no figure for net worth, only the filing itself or "None linked".
    check("the dialog shows no net-worth figure, only the disclosure", (() => {
      const item = KYC.byId(row.getAttribute("data-id"));
      const shown = D.getElementById("profileModalDisclosure").innerHTML;
      return !D.getElementById("profileModalWorth") &&
        (item.disclosureUrl ? /disclosure-link/.test(shown) : /kyc-absent/.test(shown));
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

  // Nothing on the site said how, when or where to vote (audit CG-5).
  suite("states/tx.html — the rest of the November 3 ballot", () => {
    const note = D.querySelector("#races .state-note");
    const gov = D.getElementById("state-government");
    const marks = gov ? [...gov.querySelectorAll(".gov-ballot-mark")] : [];
    check("the race list says what else the ballot elects",
      !!note && /Of the state offices this site covers, the same ballot also elects the governor/
        .test(note.textContent) && /local ballot questions, which this site does not list/.test(note.textContent) &&
        note.textContent.indexOf("This site lists the candidates for Congress here, and those for " +
          window.KYC.stategov.listsCandidates("TX") + " under State government; not those for the " +
          "legislature") !== -1 && /^the governor/.test(window.KYC.stategov.listsCandidates("TX")),
      note && note.textContent);
    check("the governor, each officer and each chamber is marked, linked to its source",
      marks.length >= 6 && marks.every((a) => /^https:\/\//.test(a.getAttribute("href")) &&
        a.target === "_blank" && /noopener/.test(a.rel)), marks.length + " marks");
    check("a chamber says how many of its seats are up",
      marks.some((a) => /seats on the Nov 3, 2026 ballot/.test(a.textContent)));
    const jump = note && note.querySelector('a[href="#state-government"]');
    if (jump) jump.click();
    check("its link to State government leaves the address alone",
      !!jump && !/state-government/.test(window.location.hash), window.location.hash);
  });
  const va = await buildPage("states/va.html");
  suite("states/va.html — the guide's page is called what it calls itself", () => {
    // The state page drew its button with a typed name; it takes the one
    // the generated page carries, the guide page's own (rule 75).
    const name = va.D.getElementById("stateContent").getAttribute("data-guide-name");
    const button = [...va.D.querySelectorAll('#stateContent a.btn[href$="government/states.html"]')];
    check("one button to the state-government guide, named as the guide names itself",
      !!name && button.length === 1 && button[0].textContent.trim() === name, name);
  });
  suite("states/va.html — a state that elects none of it in 2026", () => {
    const note = va.D.querySelector("#races .state-note");
    check("says none of the offices covered here is elected this year",
      !!note && /None of Virginia's governor, lieutenant governor, attorney general, secretary of state or regular legislative seats/.test(note.textContent),
      note && note.textContent);
  });

  // Delaware elects only its attorney general of these offices in 2026: the
  // sentence named "the governor" anyway (PR #109 review).
  const de = await buildPage("states/de.html");
  suite("states/de.html — the race list names only the offices whose candidates it lists", () => {
    const note = de.D.querySelector("#races .state-note");
    const listed = de.window.KYC.stategov.listsCandidates("DE");
    check("names the attorney general, not the governor",
      !!note && listed === "the attorney general" &&
        note.textContent.indexOf("and those for the attorney general under State government") !== -1 &&
        !/those for the governor/.test(note.textContent), note && note.textContent);
  });

  const gu = await buildPage("states/gu.html");
  suite("states/gu.html — a territory's ballot is not only local", () => {
    const note = gu.D.querySelector("#races .state-note");
    check("names territorial contests, not only local ones",
      !!note && /territorial and local contests/.test(note.textContent) &&
        !/state offices/.test(note.textContent), note && note.textContent);
    check("and says where the governor's candidates are listed",
      /Territorial government, which lists the candidates for the governor/.test(note.textContent),
      note && note.textContent);
  });
  const az = await buildPage("map.html", { hash: "#/?state=AZ&mode=lt" });
  suite("map.html — Arizona's first lieutenant governor", () => {
    const text = az.D.getElementById("delegation").textContent;
    check("a new office elected on Nov 3 is not called one the state lacks",
      /No one holds this office yet/.test(text) && !/The state has no lieutenant governor/.test(text) &&
        /This office is on the Nov 3, 2026 ballot/.test(text), text.slice(0, 300));
  });

  /* "On the Nov 3, 2026 ballot" sat under Brian Kemp, Gavin Newsom and Tim
   * Walz, none of them on it (audit 2026-10-17, STATEGOV-01). The mark is the
   * office's: it says "This office", sits on the office's label line, and
   * never in the holder's block. */
  const ga = await buildPage("states/ga.html");
  suite("states/ga.html — the ballot mark belongs to the office, not the holder", () => {
    const gov = ga.D.getElementById("state-government");
    const marks = gov ? [...gov.querySelectorAll(".gov-ballot-mark.up")]
      .filter((a) => !a.closest(".gov-chamber")) : [];
    check("every office on the ballot is marked 'This office is on the Nov 3, 2026 ballot'",
      marks.length >= 4 && marks.every((a) => a.textContent === "This office is on the Nov 3, 2026 ballot"),
      marks.map((a) => a.textContent).join(" | "));
    check("each mark sits on its office's label line",
      marks.every((a) => a.parentElement.classList.contains("gov-office") &&
        !!a.parentElement.querySelector(".gov-role, .gov-officer-role")));
    check("no mark follows a holder's name",
      !gov.querySelector(".gov-name ~ p .gov-ballot-mark, .gov-officer-name ~ p .gov-ballot-mark"));
    check("nothing on the page says a person is on the ballot",
      !/\bOn the Nov 3, 2026 ballot/.test(gov.textContent), gov.textContent.slice(0, 200));
    // Kemp, Jones, Carr and Raffensperger are on none of the November 3
    // ballot's lists (PERSONA-02): each office says so, citing the list.
    const sg = ga.window.kycStateGov.states.GA;
    const open = [...gov.querySelectorAll(".gov-open-seat")].map((p) => p.textContent);
    check("each of the four offices says its holder is not on the list, naming the list",
      ["governor", "lt", "ag", "sos"].every((k) => open.some((t) =>
        t.indexOf("Open seat: " + sg[k].name + " is not among the candidates for this office (" +
          sg.ballot2026.offices[k].holderStatus.cite + ")") === 0)) &&
        [...gov.querySelectorAll(".gov-open-seat a")].every((a) => /sos\.ga\.gov/.test(a.getAttribute("href"))),
      open.join(" | "));
    // Georgia's list is the Secretary of State's spreadsheet, which does not
    // call itself a certification: nothing calls it one (PR #109 review).
    check("a list that does not say it is certified is never called certified",
      !/certified list|Certified by/.test(open.join(" ")), open.join(" | "));
  });

  /* Silence beside one office read as "the holder is running" once another
   * office said "Open seat" (PR #94 review, rule 19): every office on the
   * ballot says something about its holder. Minnesota's lists are read now
   * (rule 91), so none says "not checked". */
  const mnGov = await buildPage("states/mn.html");
  suite("states/mn.html — every office on the ballot says something of its holder", () => {
    const gov = mnGov.D.getElementById("state-government");
    const sg = mnGov.window.kycStateGov.states.MN;
    const up = Object.keys(sg.ballot2026.offices).filter((k) => sg.ballot2026.offices[k].up);
    // The glance at the top repeats the governor's line (rule 79); the
    // section's own lines are one per office.
    const own = [...gov.querySelectorAll(".gov-holder-status")].filter((p) => !p.closest(".state-glance"));
    check("every office on the ballot carries a holder line",
      up.length >= 4 && own.length === up.length, up.join(",") + " / " + own.length);
    // Minnesota's certified list (PR #109) settles every office, the
    // governor's too, so nothing on the page - the glance included - says
    // "not checked" (PR #111's "Tim Walz ... not checked" predates the list).
    check("with a list in hand, nothing says 'not checked'",
      !gov.querySelector(".gov-holder-unchecked"),
      [...gov.querySelectorAll(".gov-holder-unchecked")].map((p) => p.textContent).join(" | "));
  });
  const caGov = await buildPage("states/ca.html");
  suite("states/ca.html — the certified list read both ways", () => {
    const sg = caGov.window.kycStateGov.states.CA;
    const lines = [...caGov.D.querySelectorAll("#state-government .gov-holder-status")].map((p) => p.textContent);
    const offices = sg.ballot2026.offices;
    const listed = ["governor", "lt", "ag", "sos"].filter((k) =>
      offices[k] && offices[k].holderStatus && offices[k].holderStatus.why === "listed");
    const off = ["governor", "lt", "ag", "sos"].filter((k) =>
      offices[k] && offices[k].holderStatus && offices[k].holderStatus.why === "not-listed");
    check("a holder the list leaves off is an open seat; one it names is not",
      listed.length && off.length &&
        off.every((k) => lines.some((t) => t.indexOf("Open seat: " + offices[k].holderStatus.holder +
          " is not among the candidates for this office (the California Secretary of State’s " +
          "certified list of candidates)") === 0)) &&
        listed.every((k) => lines.some((t) => t.indexOf(offices[k].holderStatus.holder +
          " is among the candidates for this office (the California Secretary of State’s " +
          "certified list of candidates)") === 0)),
      lines.join(" | "));
    check("never 'running for re-election': the list says only that they are on it",
      !/re-?election/i.test(caGov.D.getElementById("state-government").textContent));
  });

  const fl = await buildPage("states/fl.html");
  suite("states/fl.html — an open seat, from the constitution's term limit", () => {
    const open = fl.D.querySelector("#state-government .gov-open-seat");
    const name = fl.window.kycStateGov.states.FL.governor.name;
    check("says the governor is term-limited, with the source linked",
      !!open && open.textContent.indexOf("Open seat: " + name + " is term-limited") === 0 &&
        /^http/.test(open.querySelector("a").getAttribute("href")),
      open && open.textContent);
  });
  const flAfter = await buildPage("states/fl.html", { now: "2026-11-05T09:00:00" });
  suite("states/fl.html after Election Day — the office was on the ballot", () => {
    const gov = flAfter.D.getElementById("state-government");
    check("the mark is in the past tense",
      /This office was on the Nov 3, 2026 ballot/.test(gov.textContent));
    check("the open-seat line is gone: the office has a winner now",
      !gov.querySelector(".gov-open-seat"));
  });

  /* The candidates for each statewide office on the ballot, from the
   * election office's own list (audit 2026-10-17, FRESHNESS-05,
   * STATEGOV-14, PERSONA-08, RACES-16; rule 91). */
  suite("states/ga.html — an open governor's seat lists who is on the ballot", () => {
    const gov = ga.D.getElementById("state-government");
    const item = ga.window.kycStateGov.states.GA.ballot2026.offices.governor;
    const block = gov.querySelector(".gov-candidates");
    const names = block ? [...block.querySelectorAll(".gov-candidate-name")].map((n) => n.textContent) : [];
    const printed = item.candidates.candidates.filter((c) => !c.writeIn);
    const writeIns = item.candidates.candidates.filter((c) => c.writeIn);
    check("every candidate the list gives, as it prints them, in the pipeline's order",
      names.join("|") === printed.concat(writeIns).map((c) => c.name).join("|") && printed.length >= 2,
      names.join(" | "));
    check("party in words, never the list's code",
      printed.every((c) => !c.party || block.textContent.indexOf(c.name + " (" + c.party + ")") !== -1) &&
        printed.every((c) => !/^[A-Z]{1,4}$/.test(c.party || "")),
      printed.map((c) => c.party).join(" | "));
    check("write-ins apart, under their own heading",
      writeIns.length > 0 && !!block.querySelector(".gov-writein-head") &&
        /Write-in candidates \(names not printed on the ballot\)/.test(block.textContent) &&
        block.querySelectorAll(".gov-writein-list .gov-candidate").length === writeIns.length);
    const source = block.querySelector(".gov-candidates-source");
    check("credited to the list, linked, with the day it was read, and the order said",
      /^In surname order, not ballot order\. (Names are written [^.]*\. )?Source: the Georgia Secretary of State’s list of November candidates \(read /.test(source.textContent) &&
        [...source.querySelectorAll("a")].every((a) => /^https:\/\/sos\.ga\.gov\//.test(a.getAttribute("href"))),
      source.textContent);
    // A photograph only by rule 91's routes, each with whose it is beside it.
    check("no profile link and no money; a photograph only with its credit (rules 24, 25, 27, 91)",
      !block.querySelector("a[href*='#/profile/']") && !/\$/.test(block.textContent) &&
        [...block.querySelectorAll("img")].every((img) => img.classList.contains("gov-candidate-photo") &&
          /^Photo( \(\d{4}\))?: ./.test((img.parentNode.querySelector(".gov-photo-credit") || {}).textContent || "")));
    check("the governor's holder line still says the seat is open",
      /^Open seat: /.test((gov.querySelector(".gov-holder-status") || {}).textContent || ""));
    check("every office on the ballot lists its candidates",
      gov.querySelectorAll(".gov-candidates").length === 4);
  });

  const maGov = await buildPage("states/ma.html");
  suite("states/ma.html — a joint ticket, and a holder on the list", () => {
    const gov = maGov.D.getElementById("state-government");
    const sg = maGov.window.kycStateGov.states.MA;
    const ticket = sg.ballot2026.offices.governor.candidates.candidates.find((c) => c.runningMate);
    const rows = [...gov.querySelectorAll(".gov-candidate")].map((li) => li.textContent);
    check("the governor's list names each running mate for lieutenant governor",
      !!ticket && rows.some((t) => t.indexOf(ticket.name) === 0 &&
        t.indexOf(", with " + ticket.runningMate + " for lieutenant governor") !== -1), rows.join(" | "));
    const mate = sg.ballot2026.offices.lt.candidates.candidates.find((c) => c.runningMate);
    check("the lieutenant governor's list names the governor each runs with",
      !!mate && rows.some((t) => t.indexOf(", running with " + mate.runningMate + " for governor") !== -1));
    check("a ticket the ballot prints by surnames says how it is printed",
      !ticket.ballotName || rows.some((t) => t.indexOf("printed on the ballot as “" + ticket.ballotName + "”") !== -1));
    const status = sg.ballot2026.offices.governor.holderStatus;
    const line = gov.querySelector(".gov-holder-status");
    check("a holder the list names: among its candidates, never an open seat",
      status.why === "listed" && line.textContent.indexOf(status.holder +
        " is among the candidates for this office (the Secretary of the Commonwealth of " +
        "Massachusetts’ sample ballot)") === 0 &&
        !line.classList.contains("gov-open-seat"), line.textContent);
    const lone = sg.ballot2026.offices.governor.candidates.candidates.find((c) => c.surnameOnly);
    check("a name the ballot prints as a surname only says so, and no first name is invented",
      !lone || rows.some((t) => t.indexOf(lone.name + " (the list gives a surname only)") === 0),
      rows.join(" | "));
  });

  /* A list from a county or a commission is named as what it is and is
   * never "Certified by" it; the page says why the state's own was not used
   * (PR #109 review: "Certified by the Clark County Registrar of Voters").
   * Arkansas's Secretary of State publishes no list of the November
   * candidates, so Pulaski County's notice of election stands. */
  const arGov = await buildPage("states/ar.html");
  suite("states/ar.html — a county's notice, named as one; parties in words", () => {
    const gov = arGov.D.getElementById("state-government");
    const block = [...gov.querySelectorAll(".gov-candidates")].find((b) =>
      /Pulaski County/.test((b.querySelector(".gov-candidates-source") || {}).textContent || ""));
    check("credited as the county's notice, never 'Certified by'",
      !!block && /Source: the Pulaski County Board of Election Commissioners’ notice of election \(read /
        .test(block.querySelector(".gov-candidates-source").textContent) &&
        !/Certified by/.test(gov.textContent) &&
        ![...gov.querySelectorAll(".gov-candidates-source, .gov-holder-status")]
          .some((p) => /certified/i.test(p.textContent)), block && block.textContent);
    check("says why the state's own list was not used",
      !!block && /^Not the state’s own list\. The Secretary of State publishes no statewide list/
        .test((block.querySelector(".gov-candidates-uncertified") || {}).textContent || ""));
    check("a party the list abbreviates is spelled out",
      !!block && !/\((REP|DEM|LIB)\)/.test(gov.textContent) &&
        /\((Republican|Democratic)\)/.test(block.textContent), block && block.textContent);
  });

  /* Nevada's lists were Clark County's notice while nvsos.gov refused every
   * script; the Secretary of State's own certified list, read by hand from
   * the office's page on 2026-10-25 (rule 91), is the source now, and the
   * county's stands for nothing. */
  const nvGov = await buildPage("states/nv.html");
  suite("states/nv.html — the Secretary of State's certified list; names and parties as it prints them", () => {
    const gov = nvGov.D.getElementById("state-government");
    const offices = nvGov.window.kycStateGov.states.NV.ballot2026.offices;
    const blocks = [...gov.querySelectorAll(".gov-candidates")];
    const sources = blocks.map((b) => (b.querySelector(".gov-candidates-source") || {}).textContent || "");
    check("every office's list is the Secretary of State's certified list",
      blocks.length === 4 && sources.every((t) =>
        /Source: the Nevada Secretary of State’s certified list of candidates \(read /.test(t)) &&
        [...gov.querySelectorAll(".gov-candidates-source a")].every((a) =>
          /^https:\/\/www\.nvsos\.gov\//.test(a.getAttribute("href"))), sources.join(" | "));
    check("no county stands in for it, and nothing says it is not the state's",
      !gov.querySelector(".gov-candidates-uncertified") && !/Clark County/.test(gov.textContent),
      gov.textContent.slice(0, 400));
    const block = blocks[0];
    const names = block ? [...block.querySelectorAll(".gov-candidate-name")] : [];
    check("names first name first, the list's own form on hover (rule 77)",
      names.length >= 2 && names.every((n) => !/,/.test(n.textContent)) &&
        names.some((n) => /^The list prints: [^,]+, /.test(n.getAttribute("title") || "")),
      names.map((n) => n.textContent + " / " + n.getAttribute("title")).join(" | "));
    check("the page says how names are written",
      !!block && /Names are written first name first, in ordinary capitals/.test(block.textContent));
    check("each party in the list's own words, never a code",
      offices.governor.candidates.candidates.some((c) => c.party === "No Political Party") &&
        offices.lt.candidates.candidates.some((c) => c.party === "Independent American Party") &&
        offices.sos.candidates.candidates.some((c) => c.party === "Libertarian Party of Nevada") &&
        !/\((IAP|LPN|NPP|DEM|REP)\)/.test(gov.textContent), gov.textContent.slice(0, 400));
    // PR #140 review: "Nicole Jeanette Cannizzaro (Democratic Party)" stood
    // under "Aaron Ford (Democratic)"; the major parties read as one word.
    check("the major parties in the one word the holder lines use",
      offices.ag.candidates.candidates.some((c) => c.party === "Democratic") &&
        !/\((Democratic|Republican) Party\)/.test(gov.textContent), gov.textContent.slice(0, 400));
    const lines = [...gov.querySelectorAll(".gov-holder-status")].map((p) => p.textContent);
    check("the holder lines cite the certified list",
      lines.some((t) => /^Joe Lombardo is among the candidates for this office \(the Nevada Secretary of State’s certified list of candidates\)/.test(t)) &&
        lines.some((t) => /^Open seat: Aaron Ford is not among the candidates for this office \(the Nevada Secretary of State’s certified list of candidates\)/.test(t)),
      lines.join(" | "));
  });

  const flList = await buildPage("states/fl.html");
  suite("states/fl.html — the Division of Elections' own listing, not a county's ballot", () => {
    const gov = flList.D.getElementById("state-government");
    const sources = [...gov.querySelectorAll(".gov-candidates-source a")].map((a) => a.getAttribute("href"));
    check("every list is the Division's", sources.length >= 3 &&
      sources.every((h) => /^https:\/\/dos\.elections\.myflorida\.com\//.test(h)), sources.join(" | "));
    check("no county is credited", !/Miami-Dade/.test(gov.textContent));
  });

  /* Pennsylvania's lieutenant governor candidates come from the Department
   * of State's record of each: each name links its own record, and the
   * holder line links the holder's, never another candidate's (PR #109
   * review). */
  const paGov = await buildPage("states/pa.html");
  suite("states/pa.html — each candidate's own record", () => {
    const sg = paGov.window.kycStateGov.states.PA.ballot2026.offices.lt;
    const people = sg.candidates.candidates;
    const gov = paGov.D.getElementById("state-government");
    const links = [...gov.querySelectorAll(".gov-candidate-name a")].map((a) => a.getAttribute("href"));
    check("each lieutenant governor candidate is linked to their own record",
      people.length >= 2 && people.every((p) => p.record && links.indexOf(p.record) !== -1) &&
        new Set(people.map((p) => p.record)).size === people.length, links.join(" | "));
    const holder = people.find((p) => p.holder);
    check("the holder line links the holder's own record",
      !holder || (sg.holderStatus.why === "listed" && sg.holderStatus.source === holder.record),
      JSON.stringify(sg.holderStatus));
    check("no name in capitals (rule 77)",
      [...gov.querySelectorAll(".gov-candidate-name")].every((n) => n.textContent !== n.textContent.toUpperCase()));
    check("the order is said once, never 'Listed by' twice",
      !/Listed by surname[^.]*\. Listed by/.test(gov.textContent) &&
        /In surname order, not ballot order\./.test(gov.textContent));
  });

  const inGov = await buildPage("states/in.html");
  suite("states/in.html — a write-in's party, without the word write-in again", () => {
    const rows = [...inGov.D.querySelectorAll("#state-government .gov-writein-list .gov-candidate")]
      .map((li) => li.textContent);
    check("no 'Write-In (' inside the write-in list", rows.length > 0 &&
      rows.every((t) => !/Write-In \(/i.test(t)), rows.join(" | "));
  });

  // A jurisdiction whose list has not been read says so, office by office,
  // and claims nothing about its holder (rule 19). Every office on the 2026
  // ballot has a list now, so the case is made by withholding one.
  const unread = await buildPage("states/ga.html", { setup(window) {
    let value;
    Object.defineProperty(window, "kycStateGov", { configurable: true, get() { return value; },
      set(v) {
        const ag = v.states.GA.ballot2026.offices.ag;
        delete ag.candidates;
        ag.holderStatus = { holder: v.states.GA.ag.name, why: "unchecked",
          text: "Whether " + v.states.GA.ag.name + " is running for this office is not checked here" };
        value = v;
      } });
  } });
  suite("states/ga.html — an office whose list was not read", () => {
    const gov = unread.D.getElementById("state-government");
    const none = gov.querySelectorAll(".gov-candidates-none");
    check("says the candidates are not listed, and why",
      none.length === 1 && /The candidates for this office are not listed here: no election office's list of them has been read\./
        .test(none[0].textContent), none.length && none[0].textContent);
    check("and that the holder was not checked, by name",
      !!gov.querySelector(".gov-holder-unchecked"));
    check("the other offices still list theirs", gov.querySelectorAll(".gov-candidate-list").length >= 3);
  });

  const vaGov = await buildPage("states/va.html");
  suite("states/va.html — no statewide office on the 2026 ballot", () => {
    const gov = vaGov.D.getElementById("state-government");
    check("no candidates are listed and no list is credited",
      !gov.querySelector(".gov-candidates") && !/election office's own list/.test(gov.textContent));
  });

  const gaVoted = await buildPage("states/ga.html", { now: "2026-11-05T09:00:00" });
  suite("states/ga.html after Election Day — the candidates were on the ballot", () => {
    const gov = gaVoted.D.getElementById("state-government");
    const heads = [...gov.querySelectorAll(".gov-candidates-head:not(.gov-writein-head)")].map((p) => p.textContent);
    check("in the past tense", heads.length === 4 &&
      heads.every((t) => t === "Candidates who were on the Nov 3, 2026 ballot"), heads.join(" | "));
    const results = ((gaVoted.window.kycBuildMeta.voting || {}).GA || {}).results;
    const source = gov.querySelector(".gov-candidates-source");
    check("the state's own results are linked; this site names no winner",
      /This site does not read the state's results and names no winner/.test(source.textContent) &&
        (!results || [...source.querySelectorAll("a")].some((a) => a.getAttribute("href") === results)) &&
        !/\b(won|winner:|elected governor)\b/i.test(gov.textContent.replace(/names no winner/g, "")),
      source.textContent);
    check("no open-seat line: the office has a winner now", !gov.querySelector(".gov-open-seat"));
  });

  suite("states/va.html — when an office not up in 2026 is next elected (PERSONA-19)", () => {
    const next = [...va.D.querySelectorAll("#state-government .gov-next")];
    const words = next.map((a) => a.textContent);
    check("the governor is next elected in 2029, from the statute",
      words.filter((w) => w === "Next elected: November 2029").length === 3 &&
        next.every((a) => /law\.lis\.virginia\.gov|njleg|\.gov/.test(a.getAttribute("href"))),
      words.join(" | "));
    check("both chambers in 2027", words.filter((w) => w === "Next elected: November 2027").length === 2,
      words.join(" | "));
  });

  suite("states/gu.html — a territory's governor is on the Nov 3 ballot (RACES-07)", () => {
    const gov = gu.D.getElementById("state-government");
    const note = gu.D.querySelector("#races .state-note");
    check("the governor's office is marked on the ballot",
      !!gov && /This office is on the Nov 3, 2026 ballot/.test(gov.textContent));
    check("the race list names the territorial offices it elects",
      !!note && /Of the territorial offices this site covers, the same ballot also elects the governor/
        .test(note.textContent), note && note.textContent);
  });
  /* Hawaii has no Senate race in 2026, yet the Senate view counted its
   * House nominees under the Senate heading (audit 2026-10-17, RACES-06). */
  const hiCode = "HI";
  const hiSenate = await buildPage("map.html", { hash: "#/?state=" + hiCode + "&mode=senate" });
  const hi2026 = await buildPage("map.html", { hash: "#/?state=" + hiCode + "&mode=senate2026" });
  suite("map.html — a state with no Senate race in its Senate views", () => {
    const hasRace = hiSenate.window.kycRaces.some((r) => r.state === hiCode && r.chamber === "Senate");
    check("Hawaii has no 2026 Senate race in the data", !hasRace);
    const senateText = hiSenate.D.getElementById("delegation").textContent;
    check("the Senate view counts no House nominees", !/Also on the November ballot/.test(senateText),
      senateText.slice(0, 300));
    const text = hi2026.D.getElementById("delegation").textContent;
    const next = hi2026.window.legislatorsData.filter((p) => p.state === hiCode &&
      hi2026.window.KYC.seated(p) && /Senate/.test(p.chamber));
    check("the 2026 Senate view says there is no race, and when each senator's seat is next up",
      /No U\.S\. Senate election in Hawaii in 2026/.test(text) && next.length === 2 &&
        next.every((p) => text.indexOf(p.nextElection + " (" + p.name + ")") !== -1) &&
        !/Nothing to show/.test(text), text.slice(0, 300));
  });
  const ks = await buildPage("map.html", { hash: "#/?state=KS&mode=legislature" });
  suite("map.html — a chamber with no regular election", () => {
    const marks = [...ks.D.querySelectorAll("#delegation .gov-ballot-mark")].map((a) => a.textContent);
    check("says no regular elections, never that no seat is on the ballot",
      marks.some((m) => /No regular elections in 2026/.test(m)) &&
        !marks.some((m) => /No seats elected/.test(m)), marks.join(" | "));
  });

  suite("states/tx.html — how to vote here, from the state's own pages", () => {
    const box = D.getElementById("voting");
    const want = window.kycBuildMeta.voting.TX;
    const links = box ? [...box.querySelectorAll(".state-links a")] : [];
    check("a 'Voting in Texas' block", !!box && /Voting in Texas/.test(box.textContent));
    check("its four NASS links are the ones NASS lists for Texas",
      ["status", "polling", "absentee", "register"].every((k) =>
        links.some((a) => a.getAttribute("href") === want[k])),
      links.map((a) => a.getAttribute("href")).join(" "));
    // Where to read the count on election night (audit 2026-10-17, RACES-20).
    check("an 'Official results' link to the state's own results page",
      links.some((a) => a.textContent.trim() === "Official results" && a.getAttribute("href") === want.results),
      want.results);
    check("each opens in a new tab, without an opener",
      links.every((a) => a.target === "_blank" && /noopener/.test(a.rel)));
    check("it names NASS's Can I Vote and the dates it was listed and opened",
      !!box.querySelector('a[href^="https://www.nass.org/"]') && /listed (?:it|them) on \d{4}-\d{2}-\d{2}/.test(box.textContent) &&
        /Each link opened \d{4}-\d{2}-\d{2}/.test(box.textContent), box.textContent);
    // The deadlines are Texas's own, dated and linked; vote.gov's compiled
    // page is not shown beside them (rules 50 and 53; STATEGOV-11).
    check("no vote.gov deadlines link where the state's own dates are shown",
      !box.querySelector('a[href^="https://vote.gov/"]'), box.textContent);
  });

  /* The jurisdiction's own dates, on the reader's calendar (audit
   * 2026-10-17, STATEGOV-11, PERSONA-03, FRESHNESS-11, VISUALS-25). Built
   * at CAMPAIGN_NOW, October 20. */
  suite("states/tx.html — Texas's dates, each linked to its own office (STATEGOV-11)", () => {
    const want = window.kycBuildMeta.voting._dates.states.TX;
    const items = [...D.querySelectorAll("#voting .vote-dates li")];
    check("every line with a date links an official page of Texas's",
      items.length > 0 && items.every((li) => [...li.querySelectorAll(".vote-src a")].every((a) =>
        /^https:\/\/[^/]*(?:texas\.gov|state\.tx\.us)\//.test(a.getAttribute("href")))) &&
        items.every((li) => li.querySelector(".vote-src a")), items.map((li) => li.textContent).join(" | "));
    const reg = items.find((li) => li.getAttribute("data-kind") === "register");
    check("the registration deadline is said in words, and called passed on October 20",
      !!reg && /October 5, 2026/.test(reg.textContent) && /Passed/.test(reg.textContent), reg && reg.textContent);
    const early = items.find((li) => li.getAttribute("data-kind") === "early");
    check("early voting October 19-30 is under way",
      !!early && /October 19 – October 30, 2026/.test(early.textContent) && /Under way/.test(early.textContent),
      early && early.textContent);
    check("the lead says registration closed", /Registration for November 3 closed on October 5, 2026/.test(
      (D.querySelector("#voting .vote-lead") || {}).textContent || ""));
    const button = D.querySelector('#voting .state-links a[data-kind="register"]');
    check("'Register to vote' says it closed for November 3, never offering itself as open",
      !!button && button.getAttribute("data-closed") === "true" && /closed for Nov 3 on Oct 5/.test(button.textContent),
      button && button.textContent);
    check("the page shows every line the pipeline wrote", items.length === want.lines.length,
      items.length + " of " + want.lines.length);
  });
  suite("states/tx.html — the calendar strip is page text (VISUALS-25, rule 46)", () => {
    const strip = D.querySelector("#voting ol.vote-cal");
    const cells = strip ? [...strip.querySelectorAll("li")] : [];
    check("a strip of the dates in order, Election Day among them",
      cells.length > 2 && cells.some((li) => li.classList.contains("is-election") && /Nov 3/.test(li.textContent)),
      strip && strip.textContent);
    check("a mark for today, between the past and the future",
      cells.some((li) => li.classList.contains("is-today") && /Oct 20/.test(li.textContent)), strip && strip.textContent);
    check("passed dates are marked passed", cells.some((li) => li.classList.contains("is-past") && /Oct 5/.test(li.textContent)));
    check("no SVG text in the voting block", !D.querySelector("#voting svg text"));
  });

  /* "The first four from NASS" credited NASS with a curated sample-ballot
   * page and left out NASS's own registration link; on Wyoming's page, its
   * results page (PR #94 review). Each link's source is named by its words. */
  const mnVote = await buildPage("states/mn.html");
  suite("states/mn.html — each link credited to its own source", () => {
    const note = mnVote.D.querySelector("#voting .state-note").textContent;
    const nassPart = note.slice(0, note.indexOf("Can I Vote"));
    check("NASS is credited with registration, polling, absentee and registering, and not the sample ballot",
      /“Check your registration”/.test(nassPart) && /“Register to vote”/.test(nassPart) &&
        !/sample ballot/.test(nassPart) && !/first four/.test(note), note);
    check("the sample ballot and results are the election office's own",
      /“See a sample ballot” and “Official results” are Minnesota's election office's own pages/.test(note), note);
    const missed = mnVote.window.kycBuildMeta.voting._unreached.MN || [];
    check("a link not found live is never called opened",
      missed.length ? /could not be confirmed/.test(note) && !/Each link opened/.test(note)
        : /Each link opened/.test(note), missed.join(",") + " / " + note);
  });
  const wyVote = await buildPage("states/wy.html");
  suite("states/wy.html — no results page credited to NASS", () => {
    const note = wyVote.D.querySelector("#voting .state-note").textContent;
    const nassPart = note.slice(0, note.indexOf("Can I Vote"));
    check("NASS's three links, and only them", !/Official results/.test(nassPart) &&
      /“Official results” is Wyoming's election office's own page/.test(note), note);
  });
  const mpVote = await buildPage("states/mp.html");
  const viVote = await buildPage("states/vi.html");
  const guVote = await buildPage("states/gu.html");
  suite("territories — their own names, and their offices by name (rule 75)", () => {
    const mp = mpVote.D.getElementById("voting").textContent;
    const vi = viVote.D.getElementById("voting").textContent;
    check("'the Northern Mariana Islands', never 'Northern Mariana Islands's'",
      /Voting in the Northern Mariana Islands/.test(mp) && !/Islands's/.test(mp) &&
        /the Commonwealth Election Commission's own page/.test(mp), mp);
    check("'the U.S. Virgin Islands', and the Election System by name",
      /Voting in the U\.S\. Virgin Islands/.test(vi) && /Election System of the Virgin Islands/.test(vi) &&
        !/Islands's/.test(vi), vi);
    check("NASS spelled as its name", /National Association of Secretaries of State lists no territory/.test(mp) &&
      !/national association/.test(mp), mp);
    const gu = guVote.D.getElementById("voting").textContent;
    const missed = guVote.window.kycBuildMeta.voting._unreached.GU || [];
    check("Guam's link that could not be reached is not called opened",
      missed.indexOf("info") !== -1 && /could not be confirmed/.test(gu) && !/Each link opened/.test(gu), gu);
  });

  const nd = await buildPage("states/nd.html");
  suite("states/nd.html — a state that does not register voters", () => {
    const text = (nd.D.getElementById("voting") || {}).textContent || "";
    check("North Dakota is never told to register or to check a registration",
      /Voting in North Dakota/.test(text) && !/Register to vote|Check your registration/.test(text), text);
  });
  const dc = await buildPage("states/dc.html");
  suite("states/dc.html — the District of Columbia", () => {
    const text = (dc.D.getElementById("voting") || {}).textContent || "";
    check("the heading says 'the District of Columbia'", /Voting in the District of Columbia/.test(text), text.slice(0, 60));
    // NASS linked "Voting by Special Ballot"; D.C. mails every voter a
    // ballot (STATEGOV-10).
    const absentee = [...dc.D.querySelectorAll("#voting .state-links a")]
      .find((a) => /absentee/.test(a.textContent));
    check("its absentee link is the Board's mail-ballot page, not special ballots",
      !!absentee && /mail-ballot/.test(absentee.getAttribute("href")), absentee && absentee.getAttribute("href"));
  });
  const wy = await buildPage("states/wy.html");
  suite("states/wy.html — no lookup, no 'Check your registration'", () => {
    const links = [...wy.D.querySelectorAll("#voting .state-links a")];
    check("Wyoming's registering page is not offered twice as a registration check",
      !links.some((a) => /Check your registration/.test(a.textContent)) &&
        links.some((a) => /Register to vote/.test(a.textContent)), links.map((a) => a.textContent).join(" | "));
  });
  suite("states/wy.html — open seats have candidates, not challengers (RACES-14)", () => {
    const strip = wy.D.querySelector(".state-hero") || wy.D.body;
    const info = wy.window.kycBuildMeta.states.WY;
    check("the summary calls open-seat candidates candidates",
      info.openCandidates > 0 && new RegExp(info.openCandidates + " candidates? for open seats").test(strip.textContent) &&
        !/\d+ challengers? on the ballot/.test(strip.textContent), strip.textContent.slice(0, 400));
  });
  const guam = await buildPage("states/gu.html");
  suite("states/gu.html — a territory's own election office (RACES-07)", () => {
    const box = guam.D.getElementById("voting");
    const links = box ? [...box.querySelectorAll(".state-links a")] : [];
    check("a 'Voting in Guam' block from Guam's own election office, with its own dates",
      !!box && /Voting in Guam/.test(box.textContent) && links.length > 0 &&
        links.every((a) => /\.gov\//.test(a.getAttribute("href"))) &&
        !box.querySelector('a[href^="https://vote.gov/"]') &&
        /October 19, 2026/.test(box.textContent) &&
        !/Can I Vote/.test(box.textContent), box && box.textContent);
    // The Commission refused connections on 2026-10-17: its pages are
    // linked as the Internet Archive captured them, and say so.
    const archived = [...box.querySelectorAll(".vote-src a")].filter((a) => /web\.archive\.org/.test(a.href));
    check("an archived page of the Commission's is labelled as archived",
      archived.length > 0 && archived.every((a) => /gec\.guam\.gov \(archived \d{4}-\d{2}-\d{2}\)/.test(a.textContent)),
      archived.map((a) => a.textContent).join(" | "));
    // Sources are separated by semicolons, so a label's own date never
    // reads as another source (PR #102 review).
    const lists = [...box.querySelectorAll(".vote-src")].map((el) => el.textContent);
    check("a line's sources are separated by semicolons", lists.every((t) => !/\), gec/.test(t)), lists.join(" | "));
    const runoff = box.querySelector('.vote-dates li[data-kind="runoff"]');
    check("Guam's November 17 runoff names the offices it decides",
      !!runoff && /November 17, 2026/.test(runoff.textContent) && /Delegate/.test(runoff.textContent),
      runoff && runoff.textContent);
  });
  const georgia = await buildPage("states/ga.html");
  suite("states/ga.html — the December 1 runoff (PERSONA-06)", () => {
    const dates = georgia.D.querySelector('#voting .vote-dates li[data-kind="runoff"]');
    check("the voting block names December 1, 2026, with the state's page that gives it",
      !!dates && /December 1, 2026/.test(dates.textContent) && /runoff/.test(dates.textContent) &&
        /^https:\/\/sos\.ga\.gov\//.test(dates.querySelector(".vote-src a").getAttribute("href")),
      dates && dates.textContent);
    const heads = [...georgia.D.querySelectorAll("#races .race-head")];
    check("each Georgia race head says a runoff follows on Dec 1 if no one has a majority, linked to the guide",
      heads.length > 0 && heads.every((h) => [...h.querySelectorAll("a.badge")].some((a) =>
        /Runoff Dec 1 if no majority/.test(a.textContent) && /elections\.html#runoffs$/.test(a.getAttribute("href")))));
  });
  const la = await buildPage("states/la.html");
  suite("states/la.html — the December 12 House round (PERSONA-06)", () => {
    const dates = la.D.querySelector("#voting .vote-dates");
    check("the voting block names December 12, 2026",
      !!dates && /December 12, 2026/.test(dates.textContent) && /open primary/.test(dates.textContent),
      dates && dates.textContent);
    const house = [...la.D.querySelectorAll('#races section.race[id^="race-H-"] .race-head')];
    check("each House race head says it is an open primary with a general on Dec 12",
      house.length > 0 && house.every((h) => /Open primary Nov 3/.test(h.textContent) &&
        /General Dec 12 if no majority/.test(h.textContent)));
    // The same date was said twice, in two formats (PR #94 review).
    check("the open primary's date is said once, on its own badge",
      house.every((h) => !/Primary 2026-11-03/.test(h.textContent)), house.map((h) => h.textContent).join(" | "));
    const senate = la.D.querySelector('#races section.race[id^="race-S-"] .race-head');
    check("the Senate race, with closed party primaries, carries neither",
      !senate || !/Open primary|Dec 12/.test(senate.textContent));
  });
  /* Registration, as the reader's calendar day finds it (STATEGOV-11,
   * PERSONA-03): open, closing today, closed with a same-day route. */
  const maVote = await buildPage("states/ma.html");
  const nvVote = await buildPage("states/nv.html");
  const ncVote = await buildPage("states/nc.html");
  const nhVote = await buildPage("states/nh.html");
  suite("state pages — whether registration is still open, on the reader's day", () => {
    const lead = (p) => (p.D.querySelector("#voting .vote-lead") || {}).textContent || "";
    const button = (p) => p.D.querySelector('#voting .state-links a[data-kind="register"]');
    check("Massachusetts on October 20: open until October 24",
      /Registration for November 3 is open until October 24, 2026/.test(lead(maVote)) &&
        button(maVote) && !button(maVote).hasAttribute("data-closed"), lead(maVote));
    // NRS 293.560(1)(a)(3): online registration runs through Election
    // Day; October 20 is the last day to be mailed a ballot (PR #102 review).
    check("Nevada on October 20: registration runs through Election Day, never 'the last day'",
      /You can still register for November 3, through Election Day \(online\)/.test(lead(nvVote)) &&
        !/last day|open until|closed/i.test(lead(nvVote)), lead(nvVote));
    const nvMail = nvVote.D.querySelector('#voting .vote-dates li[data-kind="mailreg"]');
    check("Nevada's October 20 is the last day to register and still be mailed a ballot",
      !!nvMail && /October 20, 2026/.test(nvMail.textContent) && /mailed a ballot/.test(nvMail.textContent) &&
        /Today/.test(nvMail.textContent), nvMail && nvMail.textContent);
    // PR #140 review: nvsos.gov's early-voting words were read by hand on
    // 2026-10-25, not on the record's read and check days.
    const nvNote = (nvVote.D.querySelector("#voting") || {}).textContent || "";
    check("Nevada's note gives the day nvsos.gov was read",
      /read on 2026-10-17 and checked again on 2026-10-18 \(nvsos\.gov read on 2026-10-25\);/.test(nvNote),
      nvNote.slice(nvNote.indexOf("Each date"), nvNote.indexOf("Each date") + 200));
    const maNote = (maVote.D.querySelector("#voting") || {}).textContent || "";
    check("a state with no later reading says nothing more",
      /checked again on 2026-10-18; where/.test(maNote) && !/ read on 2026-10-2/.test(maNote));
    check("North Carolina after its deadline: the regular deadline, same-day registration until October 31",
      /The regular deadline to register for November 3 was October 9, 2026; you can still register and vote at the same time, until October 31, 2026/.test(lead(ncVote)) &&
        !!ncVote.D.querySelector('#voting .vote-dates li[data-kind="sameday"]') &&
        button(ncVote) && !button(ncVote).hasAttribute("data-closed"), lead(ncVote));
  });

  /* A state where a reader can register and vote at once never reads
   * "the last day" or "open until" over a regular deadline: Illinois's
   * page said "Today is the last day to register" on October 18, with
   * grace-period registration running to November 3 (PR #102 review). */
  const ilDay = await buildPage("states/il.html", { now: "2026-10-18T09:00:00" });
  const caDay = await buildPage("states/ca.html", { now: "2026-10-19T09:00:00" });
  const wiVote = await buildPage("states/wi.html");
  const dcVote = await buildPage("states/dc.html");
  suite("same-day states — a regular deadline is never the last chance (PR #102 review)", () => {
    const lead = (p) => (p.D.querySelector("#voting .vote-lead") || {}).textContent || "";
    const never = /last day|open until|closes|closed/i;
    check("Illinois on October 18, its online deadline: today is the regular deadline, and registering goes on",
      /^Today is the regular deadline to register for November 3 \(online\); after it you can still register and vote at the same time/.test(lead(ilDay)) &&
        !never.test(lead(ilDay)), lead(ilDay));
    check("California on October 19: the same, by every method",
      /^Today is the regular deadline to register for November 3 \(online, by mail or in person\); after it you can still register/.test(lead(caDay)) &&
        !never.test(lead(caDay)), lead(caDay));
    check("Wisconsin before its in-person deadline: the regular deadline, not 'open until'",
      /^The regular deadline to register for November 3 is October 30, 2026 \(in person\)/.test(lead(wiVote)) &&
        !never.test(lead(wiVote)), lead(wiVote));
    for (const [name, p] of [["Illinois", ilDay], ["California", caDay], ["Wisconsin", wiVote], ["D.C.", dcVote]]) {
      const regs = [...p.D.querySelectorAll('#voting .vote-dates li[data-kind="register"]')].map((li) => li.textContent);
      check(name + ": no deadline line or strip label reads as the last chance to register",
        regs.length > 0 && regs.every((t) => /Regular deadline to register/.test(t) && !/Last day/.test(t)) &&
          ![...p.D.querySelectorAll("#voting ol.vote-cal li")].some((li) => /Registration closes/.test(li.textContent)),
        regs.join(" | "));
      const sameDay = p.D.querySelector('#voting .vote-dates li[data-kind="sameday"]');
      check(name + ": the same-day line quotes the office's words, with the page they are from",
        !!sameDay && /in the office's words, “/.test(sameDay.textContent) &&
          !!sameDay.querySelector(".vote-src a"), sameDay && sameDay.textContent);
      const button = p.D.querySelector('#voting .state-links a[data-kind="register"]');
      check(name + ": 'Register to vote' is not marked closed", !!button && !button.hasAttribute("data-closed"));
    }
    check("D.C. shows no in-person date counted to a Sunday its office is closed",
      !/October 25/.test(dcVote.D.getElementById("voting").textContent));
  });
  const ncLate = await buildPage("states/nc.html", { now: "2026-11-02T09:00:00" });
  suite("states/nc.html once same-day registration has ended (PR #102 review)", () => {
    const lead = (ncLate.D.querySelector("#voting .vote-lead") || {}).textContent || "";
    check("the lead says same-day registration ended on October 31",
      /same-day registration ended on October 31, 2026/.test(lead) && !/is below/.test(lead), lead);
    const button = ncLate.D.querySelector('#voting .state-links a[data-kind="register"]');
    check("'Register to vote' says same-day registration ended",
      !!button && button.getAttribute("data-closed") === "true" &&
        /same-day registration ended Oct 31/.test(button.textContent), button && button.textContent);
  });
  suite("states/nh.html — vote.gov's deadlines only where the record gives none (PR #94 review)", () => {
    const kinds = [...nhVote.D.querySelectorAll("#voting .state-links a")].map((a) => a.getAttribute("data-kind"));
    const deadlines = nhVote.D.querySelector('#voting .state-links a[data-kind="deadlines"]');
    check("'Registration deadlines (vote.gov)' is a button, just before 'Register to vote'",
      !!deadlines && deadlines.textContent.trim() === "Registration deadlines (vote.gov)" &&
        kinds.indexOf("deadlines") === kinds.indexOf("register") - 1, kinds.join(" "));
    const note = nhVote.D.querySelector("#voting .state-note").textContent;
    check("vote.gov is the federal government's voting site, not the EAC's",
      /vote\.gov, the federal government's voting site/.test(note) && !/Election Assistance/.test(note), note);
    check("no lead sentence claims a deadline the record does not hold",
      !nhVote.D.querySelector("#voting .vote-lead"));
  });
  const coVote = await buildPage("states/co.html", { now: "2026-10-18T09:00:00" });
  const nyLate = await buildPage("states/ny.html", { now: "2026-10-28T09:00:00" });
  suite("state pages — the strip's Today mark, and the button's note (PR #102 review)", () => {
    const strip = [...coVote.D.querySelectorAll("#voting ol.vote-cal li")];
    check("Colorado on October 18, before its first date: Today comes first",
      strip.length > 1 && strip[0].classList.contains("is-today"), strip.map((li) => li.textContent).join(" | "));
    const mp = mpVote.D.querySelector('#voting .state-links a[data-kind="register"]');
    check("the Northern Marianas' button reads as one label with one pair of brackets",
      !!mp && /\(PDF; closed for Nov 3 on Sep 4\)$/.test(mp.textContent.trim()), mp && mp.textContent);
    // New York's record does not say whether it registers voters at once:
    // the lead gives the deadline, and the button claims no more.
    const ny = nyLate.D.querySelector('#voting .state-links a[data-kind="register"]');
    const nyLead = (nyLate.D.querySelector("#voting .vote-lead") || {}).textContent || "";
    check("New York after its deadline: the deadline was, and the button is not marked closed",
      /^The deadline to register for November 3 was/.test(nyLead) && !!ny && !ny.hasAttribute("data-closed"),
      nyLead + " / " + (ny && ny.textContent));
  });
  const msVote = await buildPage("states/ms.html");
  suite("states/ms.html — the strip says whose runoff December 1 is", () => {
    const strip = [...msVote.D.querySelectorAll("#voting ol.vote-cal li")].map((li) => li.textContent);
    check("not a bare 'Runoff' on a page about federal races",
      strip.some((t) => /Dec 1Judicial, school board runoff/.test(t)), strip.join(" | "));
  });
  const arVote = await buildPage("states/ar.html");
  const prVote = await buildPage("states/pr.html");
  const ndVote = await buildPage("states/nd.html");
  suite("state pages — a December date says what it decides", () => {
    const runoff = arVote.D.querySelector('#voting .vote-dates li[data-kind="runoff"]');
    check("Arkansas's December 1 is not a runoff for federal offices",
      !!runoff && /county and municipal/.test(runoff.textContent) && /not for federal offices/.test(runoff.textContent),
      runoff && runoff.textContent);
    const pr = prVote.D.getElementById("voting").textContent;
    check("Puerto Rico holds no election on November 3", /No election is held in Puerto Rico on November 3, 2026/.test(pr), pr);
    const nd = ndVote.D.getElementById("voting").textContent;
    check("North Dakota: no voter registration, said from its own page, and no vote.gov link",
      /North Dakota has no voter registration/.test(nd) &&
        !ndVote.D.querySelector('#voting a[href^="https://vote.gov/"]'), nd);
  });

  /* After Election Day the block keeps what still matters: a mailed
   * ballot that may still arrive, a runoff (FRESHNESS-11). */
  const caAfter = await buildPage("states/ca.html", { now: "2026-11-05T09:00:00" });
  const gaAfter = await buildPage("states/ga.html", { now: "2026-11-05T09:00:00" });
  suite("state pages after Election Day — only what still matters", () => {
    const kinds = (p) => [...p.D.querySelectorAll("#voting .vote-dates li")].map((li) => li.getAttribute("data-kind"));
    check("California keeps the mailed ballots arriving by November 10, and nothing about registering",
      kinds(caAfter).join(",") === "arrive" && !caAfter.D.querySelector("#voting .vote-lead"), kinds(caAfter).join(","));
    check("Georgia keeps its December 1 runoff alone", kinds(gaAfter).join(",") === "runoff", kinds(gaAfter).join(","));
    const button = gaAfter.D.querySelector('#voting .state-links a[data-kind="register"]');
    check("'Register to vote' is not marked closed once the election is past",
      !!button && !button.hasAttribute("data-closed") && button.textContent.trim() === "Register to vote",
      button && button.textContent);
    const strip = [...caAfter.D.querySelectorAll("#voting ol.vote-cal li")].map((li) => li.textContent);
    check("the strip shows Election Day as past and the date still to come",
      strip.some((t) => /Nov 3/.test(t)) && strip.some((t) => /Nov 10/.test(t)), strip.join(" | "));
  });
  const viAfter = await buildPage("states/vi.html", { now: "2026-11-05T09:00:00" });
  const gaLater = await buildPage("states/ga.html", { now: "2026-12-14T09:00:00" });
  suite("after Election Day — a ballot still arriving, a runoff gone (PR #102 review)", () => {
    const kinds = [...viAfter.D.querySelectorAll("#voting .vote-dates li")].map((li) => li.getAttribute("data-kind"));
    check("the Virgin Islands keep the mail ballots due by November 13", kinds.includes("return"), kinds.join(","));
    const strip = [...gaLater.D.querySelectorAll("#voting ol.vote-cal li")].map((li) => li.textContent);
    check("Georgia's strip names December 1 for what it was, after it",
      strip.some((t) => /Dec 1Runoff date/.test(t)) && !strip.some((t) => /if needed/.test(t)), strip.join(" | "));
  });
  const caLate = await buildPage("states/ca.html", { now: "2026-11-12T09:00:00" });
  suite("states/ca.html once the last ballot could arrive — no dates left to show", () => {
    check("no dated lines and no strip", !caLate.D.querySelector("#voting .vote-dates") &&
      !caLate.D.querySelector("#voting ol.vote-cal"));
  });

  const ca = await buildPage("states/ca.html");
  suite("states/ca.html — the top-two primary, visible (RACES-11)", () => {
    const heads = [...ca.D.querySelectorAll("#races .race-head")];
    check("every race head says 'Top-two primary', linked to the guide's primaries section",
      heads.length > 0 && heads.every((h) => [...h.querySelectorAll("a.badge")].some((a) =>
        a.textContent === "Top-two primary" && /elections\.html#primaries$/.test(a.getAttribute("href")))));
    const tx = [...D.querySelectorAll("#races .race-head")];
    check("a state with party primaries carries no such badge",
      tx.length > 0 && !tx.some((h) => /Top-two|Top-four|Open primary/.test(h.textContent)));
  });

  suite("states/tx.html — one state's page", () => {
    const content = D.getElementById("stateContent");
    check("the page is about Texas", /Texas/.test(D.querySelector(".state-title").textContent));
    check("the document title names the state", /^Texas/.test(D.title), D.title);
    // Who represents Texas now (rule 27): never a member who has left.
    const members = window.legislatorsData.filter((p) => window.KYC.seated(p) && p.state === "TX");
    const senators = members.filter((p) => /Senate/.test(p.chamber));
    // Of the people on the page, the senators come first (rule 27); the
    // short block of voting links above them is about no one.
    // Nor is a phone's "Find your race", which lists no one (VISUALS-15).
    const heads = [...content.querySelectorAll(".state-heading")]
      .filter((h) => !h.closest("#voting") && !h.closest("#find-race"));
    check("senators come first", /senators/i.test(heads[0].textContent), heads[0].textContent);
    // On a phone the races began eleven screens down; the page now says
    // where each part starts, and every link lands on a section.
    const parts = [...D.querySelectorAll(".state-parts a")];
    check("an 'On this page' row links every part of the page",
      // The four parts, and the statewide questions where the record has
      // any word on them (rule 95: Texas's is "none").
      parts.length === 4 + (window.kycMeasures && window.kycMeasures.TX ? 1 : 0) &&
      parts.every((a) => !!D.getElementById(a.getAttribute("href").slice(1))),
      parts.map((a) => a.getAttribute("href")).join(" "));
    // Left in the address, a fragment sent the reader back to the section
    // when a profile closed. A jump scrolls and leaves the address alone.
    const before = window.location.hash;
    parts[3].dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true }));
    check("a jump leaves the address as it was", window.location.hash === before, window.location.hash);
    check("the race list says it covers Congress, and where the statewide candidates are",
      /2026 races for Congress in Texas/.test(D.getElementById("races").textContent) &&
        /not those for the legislature/.test(D.getElementById("races").textContent));
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
    // The state's own delegation in the sidebar, counted from the data: a
    // House race with no member is a vacancy.
    const block = D.getElementById("stateBalance");
    const seated = members.filter((p) => /House/.test(p.chamber));
    const count = (list, key) => list.filter((p) => KYC.partyKey(p) === key).length;
    const houseSeats = window.kycRaces.filter((r) => r.state === "TX" && r.chamber === "House").length;
    const expectHouse = [["r", "R"], ["d", "D"], ["i", "I"]]
      .filter(([k]) => count(seated, k)).map(([k, l]) => count(seated, k) + " " + l)
      .concat(houseSeats > seated.length ? [(houseSeats - seated.length) + " Vacant"] : []);
    const lines = [...block.querySelectorAll(".balance")].map((b) => b.textContent.replace(/\s+/g, " ").trim());
    check("the sidebar shows Texas's own delegation", !block.hidden &&
      /Texas/.test(block.querySelector(".sidebar-heading").textContent));
    check("its senators by party", lines[0] === [["r", "R"], ["d", "D"], ["i", "I"]]
      .filter(([k]) => count(senators, k)).map(([k, l]) => count(senators, k) + " " + l).join("/"),
      lines[0]);
    check("its House members by party, vacancies included", lines[1] === expectHouse.join("/"),
      `${lines[1]} vs ${expectHouse.join("/")}`);
    check("in the party colours", !!block.querySelector(".party-r") &&
      block.querySelectorAll(".balance").length === 2);
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
    const shown = (n) => !n.closest("[hidden]");
    check("no card matches nonsense", cards.every((c) => !shown(c)), `${cards.filter(shown).length} shown`);
    // A sitting member's card sits in a cell with its contact link (GRID-16):
    // hiding the card alone left rows of "Contact office" with no name.
    // (A race's "Held by" line names its holder beside the link, and the
    // search never hid it.)
    const contacts = [...D.querySelectorAll("#stateContent .card-cell > .card-contact")];
    check("nor is a member's contact link left without its card",
      contacts.every((a) => !shown(a)),
      `${contacts.filter(shown).length} shown`);
  });
  const input = D.getElementById("stateSearch");
  const one = [...D.querySelectorAll("#stateContent .card-cell > .card[data-id]")][0];
  const target = one && window.KYC.byId(one.getAttribute("data-id"));
  input.value = target ? target.name : "";
  input.dispatchEvent(new window.Event("input", { bubbles: true }));
  await new Promise((r) => setTimeout(r, 200));
  suite("states/tx.html — search finds a member with their contact link", () => {
    const cell = one && one.parentNode;
    // Texas's delegation has offices on record; a membership read before
    // any is recorded has no cell to look at.
    check("the member's card and its contact link show together",
      !one || (!cell.closest("[hidden]") && !!cell.querySelector(".card-contact")));
  });
  input.value = "";
  input.dispatchEvent(new window.Event("input", { bubbles: true }));
  await new Promise((r) => setTimeout(r, 200));

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
/* The sidebar, by level of government (pages.nav_groups), the directories
 * of legislatures and of local governments, and Know Your Government's
 * links to what it explains. */
async function testNavigation() {
  const GROUPS = ["Start here", "Elections 2026", "Federal", "State", "Local", "Learn"];
  const grid = await buildPage("index.html");
  await settle(50);
  suite("the sidebar, by level of government", () => {
    const { D, window } = grid;
    const heads = [...D.querySelectorAll(".site-nav .nav-group")].map((h) => h.textContent.trim());
    check("six groups, from finding who represents you to learning",
      JSON.stringify(heads) === JSON.stringify(GROUPS), heads.join(" | "));
    const keys = [...D.querySelectorAll(".site-nav [data-nav]")].map((a) => a.getAttribute("data-nav"));
    check("twelve places to go, the lookup first and About & sources last", keys.join(",") ===
      "findrep,candidates,ballot,races,congress,executive,courts,states,legislatures,local,guide,about",
      keys.join(","));
    check("the grid is Candidates",
      D.querySelector('.site-nav [aria-current="page"]').getAttribute("data-nav") === "candidates");
    window.location.hash = "#/?role=member";
    window.dispatchEvent(new window.HashChangeEvent("hashchange"));
    check("and Congress when it shows the sitting members",
      D.querySelector('.site-nav [aria-current="page"]').getAttribute("data-nav") === "congress" &&
        D.querySelectorAll('.site-nav [aria-current]').length === 1);
    // A chip writes the address without a hashchange: the mark follows it too.
    D.querySelector('[data-group="role"][data-value="member"]').click();
    const off = D.querySelector('.site-nav [aria-current="page"]').getAttribute("data-nav");
    D.querySelector('[data-group="role"][data-value="member"]').click();
    const on = D.querySelector('.site-nav [aria-current="page"]').getAttribute("data-nav");
    check("and follows the role chip, both ways", off === "candidates" && on === "congress",
      off + " / " + on);
    check("the guide is named Know Your Government",
      D.querySelector('.site-nav [data-nav="guide"]').textContent.trim() === "Know Your Government");
    check("the Congress and election boxes say where they are explained",
      !!D.querySelector('a.learn-link[href="government/congress.html"]') &&
        !!D.querySelector('a.learn-link[href="government/elections.html"]'));
  });

  const legs = await buildPage("legislature/index.html");
  await settle(50);
  suite("legislature/index.html — every state legislature", () => {
    const { D, errors } = legs;
    check("no page errors", errors.length === 0, errors.join(" | "));
    const rows = D.querySelectorAll(".directory-row");
    check("one row per state, each linked to its legislature", rows.length === 50 &&
      [...rows].every((r) => r.querySelector('a.directory-name[href$=".html"]')));
    const outside = D.querySelector(".directory-outside");
    const said = outside ? outside.textContent.replace(/\s+/g, " ") : "";
    check("it says D.C. and the territories are not listed, and why D.C. is not",
      /District of Columbia has a mayor and a council/.test(said) &&
      /territories’ legislatures are not covered here/.test(said) &&
      !!outside.querySelector('a[href="../states/dc.html"]'), said);
    check("its jump list, of the fifty states, is labelled so",
      D.querySelector('label[for="stateJump"]').textContent === "Jump to a state");
    const mn = D.querySelector('[data-facts="MN"]');
    check("each chamber's seats by party, in the state pages' words",
      mn.querySelectorAll(".gov-chamber").length === 2 && /seats/.test(mn.textContent), mn.textContent);
    const ne = D.querySelector('[data-facts="NE"]');
    check("Nebraska's one chamber", ne.querySelectorAll(".gov-chamber").length === 1, ne.textContent);
    check("the sidebar marks State legislatures",
      D.querySelector('.site-nav [aria-current="page"]').getAttribute("data-nav") === "legislatures");
    check("its state picker lists every state", D.getElementById("stateJump").options.length > 50);
    check("and links how legislatures work",
      !!D.querySelector('a[href="../government/states.html#legislatures"]'));
  });

  const counties = await buildPage("counties/index.html");
  await settle(50);
  suite("counties/index.html — every state's local governments", () => {
    const { D, errors } = counties;
    check("no page errors", errors.length === 0, errors.join(" | "));
    const rows = [...D.querySelectorAll(".directory-table tbody tr")];
    check("one row per state, linked to its counties page", rows.length === 50 &&
      rows.every((r) => r.querySelector('a[href$=".html"]')));
    const heads = [...D.querySelectorAll(".directory-table thead th")].map((th) => th.textContent);
    // STATEGOV-19, VISUALS-13: the total was the seventh column, off a
    // 1280px screen; it is the first number now, and the headers wrap.
    check("the total is the first number after the state",
      heads[1] === "All local governments", heads.join(" | "));
    check("the long headers may wrap, so the table fits a desktop",
      D.querySelector(".directory-table").classList.contains("directory-wrap"));
    const cc = heads.indexOf("County governments");
    const ct = rows.find((r) => /Connecticut/.test(r.textContent));
    // Rule 49: a state with none of a kind is not a count of zero.
    check("a state with no county governments says none, not 0",
      ct && /^none\d+$/.test(ct.children[cc].textContent), ct && ct.children[cc].textContent);
    // Rhode Island read "none" here while its own page drew five counties.
    const riRow = rows.find((r) => /Rhode Island/.test(r.textContent));
    const riRef = riRow && riRow.children[cc].querySelector("a.note-ref");
    const riNote = riRef && D.querySelector(riRef.getAttribute("href"));
    check("its none links a note that says why",
      !!riNote && /geographic areas the state uses to organize its courts/.test(riNote.textContent),
      riNote ? riNote.textContent : String(riRef));
    const maRow = rows.find((r) => /Massachusetts/.test(r.textContent));
    check("a state with fewer county governments than counties is noted too",
      maRow && /^5\d+$/.test(maRow.children[cc].textContent) &&
      /Suffolk and Nantucket/.test(D.querySelector(maRow.children[cc].querySelector("a.note-ref")
        .getAttribute("href")).textContent), maRow && maRow.children[cc].textContent);
    check("a state whose every county area has a county government has no note",
      !rows.find((r) => /^Texas/.test(r.textContent)).children[cc].querySelector("a.note-ref"));
    const marked = D.querySelector('.site-nav [aria-current="page"]');
    check("the sidebar marks Counties & local governments, the page's own name",
      marked.getAttribute("data-nav") === "local" &&
      marked.textContent.trim() === "Counties & local governments" && /^Counties & local governments/.test(D.title),
      marked.textContent.trim() + " / " + D.title);
    check("its state picker lists every state", D.getElementById("stateJump").options.length > 50);
    check("and, listing only the states, is labelled so",
      D.querySelector('label[for="stateJump"]').textContent === "Jump to a state");
    const outside = D.querySelector(".directory-outside");
    const dcCounts = JSON.parse(fs.readFileSync(path.join(SITE, "data/census_governments.json"), "utf8")).states.DC;
    check("it says why D.C. and the territories are not in the table, with D.C.'s count from the data",
      !!outside && /District of Columbia has no counties/.test(outside.textContent) &&
      outside.textContent.indexOf("counted " + dcCounts.total + " local governments") !== -1 &&
      /five territories are outside the Census of Governments/.test(outside.textContent),
      outside && outside.textContent);
    const md = rows.find((r) => /Maryland/.test(r.textContent));
    const col = [...D.querySelectorAll(".directory-table thead th")]
      .findIndex((th) => th.textContent === "Independent school districts");
    check("a state with no independent school districts says what that means",
      col > 0 && /dependent/.test(md.children[col].getAttribute("title") || ""),
      md && md.children[col] && md.children[col].outerHTML);
  });

  const exec = await buildPage("government/executive.html");
  await settle(50);
  suite("government/executive.html — who holds the offices it explains", () => {
    const { D, errors, window } = exec;
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("the guide is Know Your Government", /Know Your Government/.test(
      D.querySelector(".state-kicker").textContent));
    const d = window.kycFederal;
    const president = D.querySelector('.guide-live[data-live="executive"] a');
    check("the President, from the data, linked to their record",
      !!president && president.textContent === d.president.name &&
        president.getAttribute("href") === "../federal/index.html#/official/" +
          encodeURIComponent(d.president.id));
    const heads = D.querySelectorAll('.guide-live[data-live="cabinet"] li');
    check("every department's head", heads.length ===
      d.offices.filter((o) => o.kind === "department").length);
    const list = D.querySelector('.guide-live[data-live="cabinet"]');
    check("under a heading of its own, not the section's last subheading",
      /Who heads each department now/.test((list.previousElementSibling || {}).textContent || ""));
    // The federal page's words for a holder: their own title, and Acting.
    const office = d.offices.find((o) => o.kind === "department" && o.holder);
    const kept = office.holder.page;
    office.holder.page = Object.assign({}, kept, { acting: true });
    window.KYC.guide.live.cabinet(list);
    const said = [...list.querySelectorAll("li")].find((li) => li.textContent.indexOf(office.holder.name) === 0);
    office.holder.page = kept;
    window.KYC.guide.live.cabinet(list);
    check("an acting head is called acting, as the federal page calls them",
      !!said && /Acting /.test(said.textContent), said && said.textContent);
    const titled = d.offices.find((o) => o.holder && o.holder.title && o.holder.title !== o.office);
    if (titled) {
      check("and by their own title where it is not the office's",
        [...list.querySelectorAll("li")].some((li) => li.textContent.indexOf(titled.holder.title) !== -1));
    }
    check("each section says where it can be seen on this site",
      !!D.querySelector('#departments .guide-see a[href="../federal/index.html#cabinet"]'));
    check("the sidebar marks Know Your Government as this page's level",
      D.querySelector('.site-nav [aria-current]').getAttribute("data-nav") === "guide");
  });

  const hub = await buildPage("federal/index.html", { hash: "#supreme-court" });
  await settle(50);
  suite("federal/index.html — the hub holds two of the sidebar's entries", () => {
    const { D } = hub;
    check("Federal courts is marked on the courts' sections",
      D.querySelector('.site-nav [aria-current="page"]').getAttribute("data-nav") === "courts" &&
        D.querySelectorAll('.site-nav [aria-current]').length === 1);
    check("the changes section is always drawn, for the guide's link", !!D.getElementById("changes"));
  });

  const courts = await buildPage("government/courts.html");
  await settle(50);
  suite("government/courts.html — the justices sitting now", () => {
    const { D, errors, window } = courts;
    check("no page errors", errors.length === 0, errors.join(" | "));
    const items = D.querySelectorAll('.guide-live[data-live="justices"] li');
    check("every justice, from the data", items.length === window.kycFederal.supremeCourt.members.length);
    check("the Chief Justice is named as one", /Chief Justice/.test(items[0].textContent),
      items[0].textContent);
  });
}

/* Every level links to the levels around it: the state page, its House
 * districts, its legislature, its counties, and back. */
async function testInterlinks() {
  const has = (D, href) => !!D.querySelector(`a[href="${href}"]`);
  const districts = await buildPage("districts/tx.html");
  const dc = await buildPage("districts/dc.html");
  const leg = await buildPage("legislature/tx.html");
  const local = await buildPage("counties/tx.html");
  suite("pages link to the levels around them", () => {
    check("a district page links to its state's legislature and counties",
      has(districts.D, "../legislature/tx.html") && has(districts.D, "../counties/tx.html"));
    // The page's own links: the sidebar links every directory.
    check("D.C.'s district page links to no legislature or counties page it does not have",
      !dc.D.querySelector('main a[href^="../legislature/"]') &&
        !dc.D.querySelector('main a[href^="../counties/"]'));
    check("a legislature page links to its state's counties and House districts",
      has(leg.D, "../counties/tx.html") && has(leg.D, "../districts/tx.html"));
    check("a counties page links to its state's legislature and House districts",
      has(local.D, "../legislature/tx.html") && has(local.D, "../districts/tx.html"));
    check("a district page links to how the House works",
      has(districts.D, "../government/congress.html#house"));
    check("a page belongs to its level in the sidebar",
      (leg.D.querySelector(".site-nav [aria-current]") || {}).getAttribute &&
        leg.D.querySelector(".site-nav [aria-current]").getAttribute("data-nav") === "legislatures" &&
        local.D.querySelector(".site-nav [aria-current]").getAttribute("data-nav") === "local" &&
        districts.D.querySelector(".site-nav [aria-current]").getAttribute("data-nav") === "states");
  });

  const map = await buildPage("map.html", { hash: "#/?state=TX&mode=house" });
  suite("map.html — the House view links to the district map", () => {
    const panel = map.D.getElementById("delegation");
    check("Texas's House panel links its district page",
      !!panel.querySelector('a[href="districts/tx.html"]'), panel.innerHTML.slice(0, 200));
    // The panel counted members only; the state page's balance counts the
    // vacant seat too. Both read the build's figure now.
    const vacant = map.window.kycBuildMeta.states.TX.balance.house.vacant;
    const counts = map.D.getElementById("panelCounts").textContent;
    check("the House counts show the state's vacancies, as the state page does",
      !vacant || counts.indexOf(vacant + " vacant") !== -1, counts);
  });

  const guide = await buildPage("government/states.html");
  suite("government/states.html — a state links to who holds its offices", () => {
    guide.D.querySelector('#usMap .state[data-state="TX"]')
      .dispatchEvent(new guide.window.MouseEvent("click", { bubbles: true }));
    check("picking a state links its page's state-government section",
      !!guide.D.querySelector('#guideFacts a[href="../states/tx.html#state-government"]'));
  });

  const state = await buildPage("states/tx.html", { hash: "#state-government" });
  suite("states/tx.html — a link to a section reaches it", () => {
    check("the section a link names exists once the page is drawn",
      !!state.D.getElementById("state-government"));
    check("a plain section link is no route: no profile opens",
      !state.D.querySelector("dialog[open]"));
    check("the fragment is dropped once used, so closing a profile does not jump back to it",
      state.window.location.hash === "", state.window.location.hash);
  });
}

async function testDeepLinks() {
  const probe = await buildPage("index.html");
  const people = probe.window.legislatorsData;
  // Texas's senator in its 2026 race - its incumbent, sitting or since left,
  // or the winner seated in it - so the dialog has race-mates to follow.
  const senator = people.find((p) => p.state === "TX" && /Senate/.test(p.chamber) &&
    !p.isCandidate && p.raceId);
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

    // Profiles opened from one another's race lists: Back steps through
    // them, and one close ends on the page. Each close used to step back a
    // single profile, so a reader closed every profile they had visited.
    const start = window.location.hash;
    window.KYC.profile.open(senator.id);
    await settle(50);
    const hops = [];
    for (let i = 0; i < 2; i++) {
      const next = [...D.querySelectorAll("#profileModal [data-goto]")]
        .find((b) => hops.indexOf(b.getAttribute("data-goto")) === -1 &&
          b.getAttribute("data-goto") !== senator.id);
      if (!next) break;
      hops.push(next.getAttribute("data-goto"));
      next.click();
      await settle(50);
    }
    window.history.back();
    await settle();
    const afterBack = D.getElementById("profileModalName").textContent;
    D.querySelector("#profileModal .modal-footer [data-close]").click();
    await settle();
    const closedHash = window.location.hash;
    const closed = modal.hidden;
    await settle(200);
    suite(`${page} — profiles opened from one another`, () => {
      check("two race-mates were followed", hops.length === 2, hops.join(", "));
      check("Back steps to the previous profile",
        afterBack === window.KYC.byId(hops[0]).name, afterBack);
      check("one close ends on the page the reader started from",
        closed && closedHash === start, `${closedHash} vs ${start}`);
      check("and the dialog stays closed", modal.hidden);
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

/* ======================================================= people's wording */

/* What the pages say about a person's race, found wrong by the 2026-10-17
 * audit: a member listed as their own opponent, a member's Senate filing
 * calling them "not a sitting member", "No filing this cycle" on a member
 * whose Senate campaign had raised millions, "Running for" after a loss,
 * "Withdrew" on senators who retired, an independent who "won the
 * primary", and a filer whose card, dialog and map row disagreed. */
async function testPeopleWording() {
  const { window, D, errors } = await buildPage("index.html");
  await settle(50);
  const KYC = window.KYC;
  const people = window.legislatorsData;
  const races = window.kycRaces;
  const text = (id) => (D.getElementById(id).textContent || "").replace(/\s+/g, " ").trim();
  const opened = (p, fn) => {
    KYC.profile.open(p.id, { fromRoute: true });
    try { return fn(); } finally { KYC.profile.close(); }
  };
  const twins = people.filter((p) => p.isCandidate && p.incumbentId &&
    KYC.seated(KYC.byId(p.incumbentId)));
  const members = people.filter((p) => KYC.seated(p) && p.alsoRunningId);
  // The campaign's cases exist only while the old Congress sits.
  const campaign = oldCongressSits(window);

  suite("index.html — one person is never their own opponent (PROFILES-02)", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("the data has members with a filing for another seat",
      !campaign || (members.length > 0 && twins.length > 0));
    const selfListed = members.concat(twins).filter((p) => opened(p, () => {
      const other = p.alsoRunningId || p.incumbentId;
      return !!D.querySelector(`#profileModalRace [data-goto="${other}"]`);
    }));
    check("neither the member nor their filing lists the other in its race",
      selfListed.length === 0, selfListed.map((p) => p.name + " " + p.id).join(", "));
  });

  suite("index.html — a member's filing is a sitting member's (PROFILES-03)", () => {
    const wrong = twins.filter((p) => opened(p, () =>
      /not a sitting member/.test(text("profileModalVoting") + text("profileModalCommittees")) ||
      !D.querySelector(`#profileModalVoting [data-goto="${p.incumbentId}"]`)));
    check("their voting record and committees are the member's, and say whose",
      (twins.length > 0 || !campaign) && wrong.length === 0, wrong.map((p) => p.name).join(", "));
    // In the name the filing is shown under: "From Garland Barr's record" on
    // Andy Barr's Senate filing read as another man's. Every filing is
    // checked, not only those whose member card carries another name: the
    // member is now shown as Andy Barr too (legislators.display_name).
    const misnamed = twins.filter((p) => !opened(p, () =>
      text("profileModalVoting").includes("From " + p.name + "’s record")));
    check("in the filing's own name", (twins.length > 0 || !campaign) && misnamed.length === 0,
      misnamed.map((p) => p.name).join(", "));
  });

  suite("index.html — a member running elsewhere has that campaign's money (PERSONA-07)", () => {
    const running = people.filter((p) => KYC.otherCampaign(p));
    const missing = running.filter((p) => (p.quality || {}).receipts === "no_filing");
    check("the data has members with no filing for their seat and one for another",
      missing.length > 0, `${missing.length} of ${running.length}`);
    const wrong = running.filter((p) => opened(p, () => {
      const filing = KYC.otherCampaign(p);
      const note = D.getElementById("profileModalOtherCampaign");
      const tiles = text("profileModalReceipts") + text("profileModalSpent");
      return /No filing this cycle/.test(tiles) || note.hidden ||
        !note.textContent.includes(filing.fecCandidateId) ||
        !note.textContent.includes(filing.officeLabel) ||
        !note.querySelector(`[data-goto="${filing.id}"]`) ||
        (KYC.hasValue(filing, "receipts") && !note.textContent.includes(filing.receipts));
    }));
    check("never 'No filing this cycle'; the other campaign's totals, its office and FEC id",
      wrong.length === 0, wrong.map((p) => p.name).join(", "));
    // "through 2026-10-14" sat above the outside spending (2026-10-26).
    check("the other campaign's totals are dated in words", running.every((p) => opened(p, () =>
      !/\d{4}-\d\d-\d\d/.test(D.getElementById("profileModalOtherCampaign").textContent))));
    check("a missing filing is named for the seat held", missing.every((p) => opened(p, () =>
      /^No (House|Senate) filing$/.test(text("profileModalReceipts")))),
      missing.length ? opened(missing[0], () => text("profileModalReceipts")) : "");
    // "No data" under it claimed this site had not looked (rule 19).
    check("and the funding box never says 'No data' beside it", missing.every((p) => opened(p, () =>
      !/No data/.test(text("profileModalFunding")))),
      missing.length ? opened(missing[0], () => text("profileModalFunding")) : "");
    check("a member running nowhere else has no such line", opened(people.find((p) =>
      KYC.seated(p) && !p.contestRaceId), () => D.getElementById("profileModalOtherCampaign").hidden));
  });

  suite("index.html — a run that ended is in the past tense (PROFILES-07, PROFILES-04)", () => {
    const off = people.filter((p) => p.isCandidate && KYC.offBallot(p.raceStatus));
    const sample = ["eliminated", "withdrawn", "unlisted"].map((s) =>
      off.find((p) => p.raceStatus === s)).filter(Boolean);
    check("the data has someone who lost, withdrew and was never listed", sample.length === 3);
    const wrong = sample.filter((p) => opened(p, () => {
      const label = text("profileModalRegionLabel");
      return label !== (p.raceStatus === "unlisted" ? "Filed for" : "Ran for") ||
        !D.getElementById("profileModalTermWrap").hidden;
    }));
    check("'Ran for' (or 'Filed for'), with no term 'if elected'", wrong.length === 0,
      wrong.map((p) => p.name + ": " + opened(p, () => text("profileModalRegionLabel"))).join(", "));
    const live = people.find((p) => p.isCandidate && p.raceStatus === "nominee");
    check("a nominee is still 'Running for', with the term", opened(live, () =>
      text("profileModalRegionLabel") === "Running for" &&
      !D.getElementById("profileModalTermWrap").hidden));
    // An appointee serves until the special election's winner is sworn in
    // (PROFILES-21), and that sentence may wrap: held on one line it ran
    // off a phone's screen.
    const appointees = people.filter((p) => KYC.seated(p) && /sworn in/.test(p.term_start || ""));
    // Only while a special election's seat is still held by its appointee
    // on the term they were appointed to: in December the winner is sworn
    // in (a winnerId, or the appointee's own new term), rule 67.
    const election = KYC.electionStatus(window.kycBuildMeta.election.year).date.toISOString().slice(0, 10);
    const awaiting = races.some((r) => r.special && !r.winnerId && r.incumbentIds.some((id) => {
      const p = KYC.byId(id);
      return p && KYC.seated(p) && p.appointed && String(p.term_start || "").slice(0, 10) < election;
    }));
    check("an appointee's term runs to the winner's swearing-in, and wraps",
      (appointees.length > 0 || !awaiting) && appointees.every((p) => opened(p, () => {
        const parts = [...D.querySelectorAll("#profileModalTerm > span")];
        return !/\(special election\)/.test(text("profileModalTerm")) &&
          parts.some((s) => /sworn in/.test(s.textContent) && !s.classList.contains("nowrap"));
      })), appointees.map((p) => p.term_start).join(" | "));
    const lostElsewhere = people.filter((p) => KYC.seated(p) && p.alsoRunningId &&
      KYC.offBallot((KYC.byId(p.alsoRunningId) || {}).raceStatus));
    check("a member whose other run ended reads 'Also ran for', never 'Also running'",
      (lostElsewhere.length > 0 || !campaign) && lostElsewhere.every((p) => opened(p, () =>
        /Also ran for/.test(text("profileModalCrossLink")) &&
        !/Also running/.test(text("profileModalCrossLink")))),
      lostElsewhere.map((p) => opened(p, () => text("profileModalCrossLink"))).slice(0, 2).join(" | "));
  });

  suite("index.html — a member who withdrew is not running for re-election (TRUST-18)", () => {
    const withdrew = people.filter((p) => KYC.seated(p) && !p.contestLabel &&
      p.raceStatus === "withdrawn" && !p.appointed);
    check("the data has sitting members the results list as withdrawn", withdrew.length > 0);
    const wrong = withdrew.filter((p) => !/Not running for re-election/.test(KYC.cards.statusBadge(p)) ||
      />Withdrew</.test(KYC.cards.statusBadge(p)));
    check("their card says 'Not running for re-election', not 'Withdrew'", wrong.length === 0,
      wrong.map((p) => p.name).join(", "));
    check("and so does their profile", withdrew.every((p) => opened(p, () =>
      /Not running for re-election in 2026/.test(text("profileModalStatus")) &&
      !/Withdrew/.test(text("profileModalStatus")))));
    check("a challenger who withdrew still 'Withdrew'", /Withdrew/.test(KYC.cards.statusBadge(
      people.find((p) => p.isCandidate && p.raceStatus === "withdrawn"))));
    // However the results happened to list a retirement - withdrawn, or not
    // at all - it reads the same in every form (RACES-10): the Senate view
    // set "Not running for re-election" beside "Not running for this seat",
    // and race-mate lists "Not on ballot" beside both.
    const leaving = people.filter((p) => KYC.seated(p) && !p.contestLabel && !p.appointed &&
      (p.raceStatus === "withdrawn" || p.raceStatus === "unlisted") && !p.raceStatusUnconfirmed);
    const kinds = new Set(leaving.map((p) => p.raceStatus));
    check("the data has members leaving both ways", kinds.size === 2, [...kinds].join(", "));
    const forms = ["card", "long", "mate", "short"];
    const words = (p) => forms.map((f) => KYC.raceStatusOf(p, f).label).join(" | ");
    const split = leaving.filter((p) => words(p) !== words(leaving[0]));
    check("every retiring member reads the same words in every form", split.length === 0,
      split.slice(0, 3).map((p) => p.name + ": " + words(p)).join(" / ") + " vs " + words(leaving[0]));
    check("which are 'Not running for re-election'",
      words(leaving[0]) === "Not running for re-election | Not running for re-election in 2026 | " +
        "Not running for re-election | Leaving seat", words(leaving[0]));
    const hover = (s) => KYC.raceStatusOf(leaving.find((p) => p.raceStatus === s &&
      !p.raceStatusSource), "card").title;
    check("the hover still says which way the results listed them",
      /withdrawn/.test(hover("withdrawn")) && /Not named in the primary results/.test(hover("unlisted")));
    const qualified = ["withdrawn", "unlisted"].map((s) =>
      KYC.raceStatus(s, "mate", { own: true, source: "qualified" }).label);
    check("and so does a member on a qualified list", qualified.every((l) =>
      l === "Not running for re-election"), qualified.join(", "));
    // An appointee was never elected to the seat (Alan Armstrong).
    const appointee = people.find((p) => KYC.seated(p) && p.appointed && p.raceStatus === "unlisted");
    check("an appointee who is leaving is 'Not running in 2026', not 're-election'",
      !appointee || (KYC.raceStatusOf(appointee, "card").label === "Not running in 2026" &&
        !/re-election/.test(KYC.raceStatusOf(appointee, "card").title)),
      appointee ? KYC.raceStatusOf(appointee, "card").label : "no appointee leaving");
    // Said once: the roster's note repeats the badge (Eleanor Norton), but
    // a note that says more stays (Cleo Fields, for the state senate).
    const restating = people.filter((p) => KYC.seated(p) && !p.otherOffice &&
      /^(incumbent )?not running for re-election( in \d{4})?( \([^)]*\))?\.?$/i.test(p.status || "") &&
      /^Not running/.test((KYC.standing(p, "long") || {}).label || ""));
    check("the data has a roster note that only restates the badge", restating.length > 0 || !campaign);
    check("it is not shown beside the badge", restating.every((p) => opened(p, () =>
      (text("profileModalStatus").match(/not running for re-election/gi) || []).length === 1)),
      restating.map((p) => opened(p, () => text("profileModalStatus"))).slice(0, 2).join(" | "));
    const saysMore = people.find((p) => KYC.seated(p) && /; running for/.test(p.status || "") &&
      KYC.standing(p, "long"));
    check("a note that says more is kept", !saysMore || opened(saysMore, () =>
      text("profileModalStatus").includes(saysMore.status)), saysMore ? saysMore.name : "none");
  });

  suite("index.html — where a member who is leaving is going (FRESHNESS-09)", () => {
    const going = people.filter((p) => KYC.seated(p) && p.otherOffice);
    check("the data has members on another office's ballot", going.length >= 4 || !campaign,
      going.map((p) => p.name).join(", "));
    // The card of a member leaving their seat; one whose seat is not up
    // (Marsha Blackburn) says it in the profile.
    const leavingSeat = going.filter((p) => KYC.offBallot(p.raceStatus));
    check("each card of a member leaving their seat names it", (leavingSeat.length > 0 || !campaign) &&
      leavingSeat.every((p) => KYC.cards.statusBadge(p).includes(KYC.escapeHtml(p.otherOffice.text))));
    check("each profile names it, with its source", going.every((p) => opened(p, () =>
      text("profileModalStatus").includes(p.otherOffice.text) &&
      !!D.querySelector(`#profileModalStatus a[href="${p.otherOffice.source}"]`))));
    // After Election Day this site does not know who won that race, and
    // "Republican nominee for Governor of Alabama" would read as a race
    // still to come for two months (rule 63).
    const after = new window.Date("2026-11-10T12:00:00");
    check("after Election Day it is in the past tense, and says the result is not shown",
      going.every((p) => {
        const html = KYC.otherOfficeBadge(p, "", after);
        return html.includes(KYC.escapeHtml("Was the " + p.otherOffice.text)) &&
          /does not show that race(&#39;|')s result/.test(html) && !/On the November 3 ballot/.test(html);
      }), going.length ? KYC.otherOfficeBadge(going[0], "", after) : "");
    check("and on Election Day itself it is not yet", going.every((p) =>
      !/Was the/.test(KYC.otherOfficeBadge(p, "", new window.Date("2026-11-03T20:00:00")))));
  });

  suite("index.html — an independent did not win a primary (PROFILES-17)", () => {
    // Not a top-two or top-four state's, where everyone did run in the
    // all-party primary and the badge says so.
    const minor = people.filter((p) => p.isCandidate && p.raceStatus === "nominee" &&
      KYC.partyKey(p) === "i" && !p.allPartyPrimary);
    const major = people.find((p) => p.isCandidate && p.raceStatus === "nominee" &&
      p.party === "Republican");
    check("the data has independent and minor-party nominees", minor.length > 0);
    check("none is told they won the primary", minor.every((p) =>
      !/primary/i.test(KYC.raceStatusOf(p, "card").title.replace(/not necessarily by a primary/, ""))));
    check("a party's nominee still won its primary", /Won the primary/.test(
      KYC.raceStatusOf(major, "card").title));
  });

  suite("index.html — one status for an unsettled filer, everywhere (PROFILES-06)", () => {
    const unsettled = people.filter((p) => p.isCandidate && !p.raceStatus &&
      (p.ballotUnknown || (p.maybeNamed || []).length));
    check("the data has filers the results do not settle", unsettled.length > 0);
    const wrong = unsettled.filter((p) => {
      const spec = KYC.standing(p, "card");
      return !spec || !spec.unknown || !KYC.cards.statusBadge(p).includes(spec.label) ||
        !opened(p, () => text("profileModalStatus").includes(KYC.standing(p, "long").label));
    });
    check("the dialog shows the card's status", wrong.length === 0, wrong.map((p) => p.name).join(", "));
    // The Northern Mariana Islands hold no primary for their delegate: a
    // filer there is neither "the primary has not been held yet" nor
    // without a status in the dialog.
    const noPrimary = people.filter((p) => p.isCandidate && !p.raceStatus && !p.ballotUnknown &&
      races.some((r) => r.id === p.raceId && r.primaryDate === null && !r.results));
    check("a filer in a race with no primary has the same status everywhere",
      noPrimary.every((p) => {
        const spec = KYC.standing(p, "card");
        return spec && spec.unknown && /no primary/.test(spec.title) &&
          !/has not been held/.test(KYC.cards.statusBadge(p)) &&
          opened(p, () => text("profileModalStatus").includes(spec.label));
      }), noPrimary.map((p) => p.name).join(", "));
    // A build without the calendar says nothing either way.
    const sample = people.find((p) => p.isCandidate && !p.raceStatus && !p.ballotUnknown &&
      !(p.maybeNamed || []).length);
    check("only when the calendar says so", !sample || (() => {
      const race = races.find((r) => r.id === sample.raceId);
      const was = race.primaryDate;
      delete race.primaryDate;
      try { return !KYC.standing(sample, "card"); } finally { race.primaryDate = was; }
    })());
  });

  suite("index.html — the people in a race, in one order (TRUST-15)", () => {
    const race = races.find((r) => r.id === "S-NC-2026") || races.find((r) => r.candidateIds.length > 2);
    const surnameOrder = race.candidateIds.map(KYC.byId).map((p) => p.name);
    const member = KYC.byId(race.incumbentIds[0]);
    const shown = opened(member, () => [...D.querySelectorAll("#profileModalRace > .race-mate")]
      .map((b) => b.getAttribute("data-goto")));
    const expected = race.candidateIds.filter((id) => shown.includes(id));
    check("the profile lists a race's people in the race's order",
      shown.length > 1 && JSON.stringify(shown) === JSON.stringify(expected), surnameOrder.join(", "));
    check("and says what the order is", opened(member, () =>
      text("profileModalRace").includes(KYC.RACE_ORDER_PLAIN)));
    // The holder's own dialog leaves the holder out, so nobody listed holds
    // the seat: "The seat's holder first" put Barry Moore in Tuberville's.
    // While the old Congress sits: from January 3 a 2026 incumbent who
    // moved (Kevin Kiley, CA-3 to CA-6) sits in the seat they won, and its
    // race's record holder, listed first, is someone else (rule 67).
    const holders = campaign ? races.map((r) => KYC.byId(r.incumbentIds[0]))
      .filter((p) => p && KYC.seated(p) && !p.contestRaceId) : [];
    const wrongHolder = holders.filter((p) => opened(p, () =>
      text("profileModalRace").includes(KYC.RACE_ORDER)));
    check("a holder's own dialog never says its first name holds the seat",
      (holders.length > 0 || !campaign) && wrongHolder.length === 0,
      wrongHolder.slice(0, 3).map((p) => p.name).join(", "));
    // A challenger's dialog lists the holder first, and says so.
    const seatHeld = races.find((r) => r.incumbentIds.length && KYC.byId(r.incumbentIds[0]) &&
      KYC.seated(KYC.byId(r.incumbentIds[0])) && !KYC.byId(r.incumbentIds[0]).contestRaceId &&
      !KYC.offBallot(KYC.byId(r.incumbentIds[0]).raceStatus) &&
      r.candidateIds.filter((id) => KYC.byId(id) && !KYC.offBallot(KYC.byId(id).raceStatus)).length > 1);
    const challenger = seatHeld && KYC.byId(seatHeld.candidateIds.find((id) =>
      KYC.byId(id) && !KYC.offBallot(KYC.byId(id).raceStatus)));
    check("a challenger's dialog opens with the holder and says so", !!challenger && opened(challenger, () =>
      D.querySelector("#profileModalRace > .race-mate").getAttribute("data-goto") === seatHeld.incumbentIds[0] &&
      text("profileModalRace").includes(KYC.RACE_ORDER)), seatHeld ? seatHeld.id : "none");
    check("the note's sentence follows the list's head",
      KYC.raceOrderNote([KYC.byId(race.incumbentIds[0])], race) === KYC.RACE_ORDER &&
      KYC.raceOrderNote([KYC.byId(race.candidateIds[0])], race) === KYC.RACE_ORDER_PLAIN);
  });

  suite("index.html — the 2026 Senate races chip (GRID-10, GRID-21)", () => {
    const chip = D.querySelector('[data-group="election"][data-value="senateUp26"]');
    check("it is named for the races", /2026 Senate races/.test(chip.textContent), chip.textContent);
    chip.click();
    const cards = [...D.querySelectorAll("#results .card")].map((c) => KYC.byId(c.getAttribute("data-id")));
    const nominees = people.filter((p) => p.isCandidate && /^S-/.test(p.raceId || "") &&
      p.raceStatus === "nominee");
    check("it shows the people running for those seats, not only who holds them",
      nominees.every((p) => cards.includes(p)), `${cards.length} cards`);
    check("each person once: a member running for the Senate as their filing",
      !cards.some((p) => p && p.alsoRunningId && cards.includes(KYC.byId(p.alsoRunningId)) &&
        /^S-/.test(p.contestRaceId || "")));
    chip.click();
    const party = D.querySelector('[data-group="party"][data-value="Independent"]');
    check("the third chip says it holds every other party", /Independent &\s*third party/.test(
      party.textContent), party.textContent);
    check("no one's party reads 'None'", !people.some((p) => p.party === "None"));
    const democrats = people.filter((p) => p.party === "Democrat");
    check("searching the chip's word finds the party's people",
      democrats.length > 0 && democrats.every((p) => KYC.matchesQuery(p, "Democratic")));
  });
  window.close();

  // The map's state panel: a filer whose place on the ballot is not known
  // is not a challenger there either (RACES-04).
  // Asked of a state that still has such filers: Florida's certified list
  // (rule 77) settled every one there.
  const probe = await buildPage("map.html");
  const unsettled = probe.window.legislatorsData.find((p) => p.isCandidate &&
    /^House/.test(p.chamber) && (probe.window.KYC.standing(p, "short") || {}).unknown);
  const code = unsettled ? unsettled.state : "FL";
  probe.window.close();
  const map = await buildPage("map.html", { hash: "#/?state=" + code + "&mode=house" });
  await settle(50);
  suite("map.html — an unsettled filer is not counted as a challenger (RACES-04)", () => {
    const M = map.window.KYC;
    const fl = map.window.legislatorsData.filter((p) => p.state === code && p.isCandidate &&
      /^House/.test(p.chamber));
    const unknown = fl.filter((p) => (M.standing(p, "short") || {}).unknown);
    const running = fl.filter((p) => !M.offBallot(p.raceStatus) && !unknown.includes(p));
    const head = map.D.getElementById("showChallengers");
    const count = head ? Number(head.querySelector("span").textContent) : 0;
    check("a state has filers the results do not settle (" + code + ")", unknown.length > 0);
    check("the challenger count leaves them out", count === running.length, `${count} vs ${running.length}`);
    const unsure = map.D.getElementById("unsureRows");
    check("and they are listed apart, under their status",
      !!unsure && unsure.querySelectorAll(".person-row").length === unknown.length &&
      !/Challenger/.test(unsure.textContent));
  });
  map.window.close();
}

/* After Election Day: a member's other run that lost in November is over,
 * and another office's nomination is in the past tense - by the page's own
 * clock, with no edit to the data (rule 63). */
async function testPeopleWordingAfterElection() {
  let lost = null;
  const { window, D, errors } = await buildPage("index.html", { now: "2026-11-10T12:00:00",
    data: (w) => {
      const member = w.legislatorsData.find((p) => p.alsoRunningId && !p.isCandidate &&
        (w.legislatorsData.find((f) => f.id === p.alsoRunningId) || {}).raceStatus === "nominee");
      if (!member) return;
      w.legislatorsData.find((f) => f.id === member.alsoRunningId).raceStatus = "defeated";
      lost = member.id;
    } });
  await settle(50);
  const KYC = window.KYC;
  const text = (id) => (D.getElementById(id).textContent || "").replace(/\s+/g, " ").trim();
  const opened = (id, fn) => {
    KYC.profile.open(id, { fromRoute: true });
    try { return fn(); } finally { KYC.profile.close(); }
  };
  suite("index.html after Election Day — what has happened is in the past tense", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    const going = window.legislatorsData.filter((p) => KYC.seated(p) && p.otherOffice);
    check("another office's nominee reads 'Was the ...' on the card and in the profile",
      going.length > 0 && going.every((p) => {
        const card = KYC.cards.statusBadge(p);
        const dialog = opened(p.id, () => text("profileModalStatus"));
        return (!/other-office/.test(card) || card.includes(KYC.escapeHtml("Was the " + p.otherOffice.text))) &&
          dialog.includes("Was the " + p.otherOffice.text) && !/On the November 3 ballot/.test(card);
      }), going.length ? opened(going[0].id, () => text("profileModalStatus")) : "");
    check("a member whose other run lost in November 'also ran'", !!lost && opened(lost, () =>
      /Also ran for/.test(text("profileModalCrossLink")) && !/Also running/.test(text("profileModalCrossLink"))),
      lost ? opened(lost, () => text("profileModalCrossLink")) : "no member with a nominee filing");
    check("and the card agrees", !!lost && KYC.contestLine(KYC.byId(lost)).past);
  });
  window.close();
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

  suite("a race's panel says where its holder went, not that race's result", () => {
    // Kevin Kiley read "On the ballot" in CA-3, which he holds and is not
    // running for; Al Green "Lost primary" in TX-9, though he lost TX-18's.
    const races = window.kycRaces;
    const cases = people.filter((m) => KYC.seated(m) && !m.isCandidate && m.contestRaceId &&
      m.raceId && m.contestRaceId !== m.raceId).map((m) => {
      const held = races.find((r) => r.id === m.raceId && r.incumbentIds.indexOf(m.id) !== -1);
      const opener = held && held.candidateIds.map(KYC.byId).find((c) => c && c.id !== m.id &&
        (c.contestRaceId || c.raceId) === held.id);
      return opener ? { m, opener } : null;
    }).filter(Boolean);
    // Once the new Congress sits, every member is in the seat they won, and
    // nobody holds one seat while running for another (rule 68).
    const movers = people.filter((m) => KYC.seated(m) && !m.isCandidate && m.contestRaceId &&
      m.raceId && m.contestRaceId !== m.raceId);
    check("the data has a holder running elsewhere, in a race someone else is running in",
      cases.length > 0 || !movers.length, `${cases.length} of ${movers.length} movers`);
    const wrong = cases.filter(({ m, opener }) => {
      KYC.profile.open(opener.id, { fromRoute: true });
      const row = D.querySelector(`#profileModalRace [data-goto="${m.id}"]`);
      // "Running for Senate GA", "Running in CA-40 (redrawn)", or, once that
      // run is over, "Ran for House TX-18" (KYC.contestLine).
      const line = KYC.contestLine(m);
      const words = line.past ? /Ran for/ : line.renumbered ? /Running in .*\(redrawn\)/ : /Running for/;
      const bad = !row || !words.test(row.textContent) || !!row.closest(".race-out");
      KYC.profile.close();
      return bad;
    });
    check("each reads where they went - running, redrawn, or ran - and is not folded under " +
      "'no longer in this race'", wrong.length === 0, wrong.map(({ m }) => m.name).join(", "));
    // Both only while the old Congress sits: from January 3 the movers sit
    // in the seats they won, and a renumbered member who lost has left.
    check("a member whose run ended reads it in the past tense", (cases.some(({ m }) =>
      KYC.contestLine(m).past) || !oldCongressSits(window)) && cases.every(({ m }) =>
      KYC.contestLine(m).past === (KYC.offBallot(KYC.contestStatus(m)) ||
        KYC.contestStatus(m) === "defeated")));
    check("a renumbered member is running for re-election, not leaving", !oldCongressSits(window) || people.filter((m) =>
      m.renumbered).every((m) => /\(redrawn\)/.test(KYC.cards.statusBadge(m)) &&
      !/not seeking re-election/.test(KYC.cards.statusBadge(m))),
      people.filter((m) => m.renumbered).map((m) => KYC.cards.statusBadge(m)).slice(0, 1).join(""));
  });

  suite("members running for another seat — their race, not their seat", () => {
    check("the data has members whose held-seat result differs from their race",
      decided.length > 0 && nominees.length > 0, `${decided.length} decided, ${nominees.length} nominees`);
    check("every one shows the result of the race they are in",
      decided.every((p) => KYC.contestStatus(p) === filingOf(p).raceStatus),
      decided.filter((p) => KYC.contestStatus(p) !== filingOf(p).raceStatus).map((p) => p.name).join(", "));

    const badProfiles = decided.filter((p) => {
      const t = profileStatus(p);
      return /not seeking re-election|Not running for (this seat|re-election)|Renominated/i.test(t) ||
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
      return /Not running for (this seat|re-election)|Renominated/.test(html) ||
        !FILING_BADGE[filingOf(p).raceStatus].test(html) ||
        (filingOf(p).raceStatus !== "unlisted" && /Not on primary ballot/.test(html));
    });
    check("each card shows the result of their race, not their seat", badCards.length === 0,
      badCards.map((p) => p.name + ": " + KYC.cards.statusBadge(p)).join(" | "));

    // A member with no line for their own seat may be on another office's
    // ballot (Byron Donalds, Florida's nominee for governor), so the badge
    // speaks only of the seat.
    const leaving = people.filter((p) => !p.isCandidate && !p.contestLabel &&
      KYC.contestStatus(p) === "unlisted");
    check("a member not running for their seat is never called off the ballot",
      leaving.length > 0 && leaving.every((p) => {
        const html = KYC.cards.statusBadge(p);
        return /Not running (for re-election|in 2026)/.test(html) && !/Not on the ballot/.test(html);
      }), leaving.length + " members");

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
          !/Leaving seat|Not on ballot/.test(row.textContent),
        row && row.textContent.replace(/\s+/g, " ").trim());
      // Both badges beside the name took the whole row: the name vanished and
      // "House • CA-38" broke a word a line. The seat gets a line of its own
      // under the text; the result stays at the end, in line with every
      // "Renominated".
      const contestOf = (r) => [...r.children].find((c) => c.classList.contains("contest"));
      const atEnd = (r) => [...r.children]
        .filter((c) => c.classList.contains("badge") && !c.classList.contains("contest"));
      check("the row says which seat they are running for",
        !!row && /^Running for /.test((contestOf(row) || {}).textContent || ""),
        row && row.innerHTML.replace(/<img[^>]*>/, "").slice(0, 240));
      // One state's panel: the district or "Senate" is all the row lacks, and
      // "Running for House CA-41" wrapped to two lines beside "Nominee".
      const seat = nominee.contestLabel.split(" • ");
      const said = row && (contestOf(row) || {}).textContent;
      check("the seat is said in the panel's terms: the district, or Senate",
        said === "Running for " + (seat[0] === "House" ? seat[1] : "Senate"),
        `${said} for ${nominee.contestLabel}`);
      check("and the result of their race at the row's end, like everyone else's",
        !!row && atEnd(row).length === 1 && /Nominee/.test(atEnd(row)[0].textContent),
        row && atEnd(row).map((b) => b.textContent).join(" | "));
      const own = [...map.D.querySelectorAll("#delegation .person-row")].find((r) => {
        const p = map.window.KYC.byId(r.getAttribute("data-id"));
        return p && !p.isCandidate && !p.contestLabel && p.raceStatus === "nominee";
      });
      check("a member seeking re-election keeps one badge at the row's end",
        !!own && !contestOf(own) && atEnd(own).length === 1,
        own && own.textContent.replace(/\s+/g, " ").trim());
      // jsdom has no layout, so these assert the rule rather than the effect.
      const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
      check("the seat line is cut short, never broken a word a line",
        /\.person-row \.who \.office[^{]*\{[^}]*white-space:\s*nowrap/.test(css));
      check("a long name or party wraps rather than being cut short",
        !!row && !row.querySelector(".who .name").classList.contains("truncate") &&
          !/\.person-row \.who \.(name|party)[^{]*\{[^}]*white-space:\s*nowrap/.test(css));
      // "Nominee – Party for Socialism and Liberation line" took 48% and cut
      // the seat beside it to "House • NY-…".
      check("the text column never narrows below the seat line",
        /\.person-row\s*\{[^}]*grid-template-columns:\s*auto minmax\(min-content, 1fr\)/.test(css));
      check("the seat's line spans the text and status columns, under both",
        /grid-template-areas:\s*"photo who status go"\s*"\.\s+contest contest \."/.test(css) &&
          /\.person-row > \.badge\.contest\s*\{[^}]*grid-area:\s*contest/.test(css));
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
    // A status badge is 11px bold text over a 14% tint of its own colour.
    // The light theme's plain colours reached only 4.17-4.42 (audit, VUX-8).
    const mix = (a, b, w) => "#" + rgb(a).map((v, i) => Math.round(w * v + (1 - w) * rgb(b)[i])
      .toString(16).padStart(2, "0")).join("");
    for (const [name, t] of Object.entries(themes)) {
      const badges = ["money-in", "warn", "danger"].flatMap((c) => ["surface-1", "surface-2"].map((s) =>
        ratio(t[c + "-text"] || t[c], mix(t[c], t[s], 0.14))));
      check(`${name}: status badges on their tint`, badges.every((r) => r >= 4.5),
        badges.map((r) => r.toFixed(2)).join(" / "));
    }
    // A state with no value is drawn in the empty grey; its code is white on
    // a dark backing (rgb(0 0 0 / a) over the grey). 0.26 gave 2.15:1.
    const alpha = parseFloat((css.match(/\[data-theme="light"\] \{[^}]*--map-label-backing:\s*rgb\(0 0 0 \/ ([\d.]+)\)/) || [])[1]);
    const backed = mix("#000000", themes.light["surface-2"], alpha);
    check("light: a map code on the empty grey", ratio(themes.light["map-label"] || "#ffffff", backed) >= 4.5,
      ratio(themes.light["map-label"] || "#ffffff", backed).toFixed(2));
    const js = fs.readFileSync(path.join(SITE, "assets", "kyc-profile.js"), "utf8");
    check("the party tag's label colour comes from the theme, not a literal",
      !/style\.color\s*=\s*["']#/.test(js) && /\.party-tag\s*\{[^}]*color:\s*var\(--text-inverse\)/.test(css));
  });
  testColourVision(css);
  testMotion();
  testPhoneRules(css);
}

/* A phone's first screen and its width. jsdom has no layout, so these
 * assert the rules; a CDP sweep of every page at 320px measured them. */
function testPhoneRules(css) {
  const media = (max) => [...css.matchAll(new RegExp("@media \\(max-width: " + max + "px\\) \\{([\\s\\S]*?)\\n\\}", "g"))]
    .map((m) => m[1]).join("\n");
  const phone = media(600);
  suite("kyc.css — a phone's first screen, and nothing wider than it", () => {
    // California's first senator started at 1,147px under seven badges, six
    // full-width buttons and four jump chips (TECH-14, VISUALS-02).
    check("a page's links and its jump chips each take one row that scrolls sideways",
      /\.state-links,\s*\.jump-row\.state-parts\s*\{[^}]*flex-wrap:\s*nowrap;[^}]*overflow-x:\s*auto/.test(phone));
    check("a state's figures read as one line of text", /\.state-summary \.badge\s*\{[^}]*display:\s*inline/.test(phone));
    // California's page was about 60 screens of portrait tiles (VISUALS-15).
    check("a state page's people are rows on a phone, not portrait tiles",
      /#stateContent \.card\s*\{[^}]*flex-direction:\s*row/.test(phone) &&
        /#stateContent \.card-photo\s*\{[^}]*width:\s*52px/.test(phone));
    const stateJs = fs.readFileSync(path.join(SITE, "assets", "kyc-state.js"), "utf8");
    // Closed at every width since (TRUST-14 review): the same prices were
    // open on a desktop state page and closed on a phone.
    check("and its races' markets are closed there, at every width", !/collapsedOdds/.test(stateJs) &&
      /collapsed:\s*opts\.collapsedOdds !== false/.test(fs.readFileSync(path.join(SITE, "assets", "kyc-cards.js"), "utf8")));
    check("the map's ten views are one menu on a phone",
      /\.map-view-group\s*\{\s*display:\s*none;?\s*\}/.test(media(760)) &&
        /\.map-mode-pick\s*\{[^}]*display:\s*flex/.test(media(760)));
    // A 260px phone laid out at 287px, cutting off the profile's close
    // button (PERSONA-21); Indiana's record, one unbreakable word, at 434px.
    check("the home page's state menu is capped by the screen, not the column",
      /\.intro-pick \.select\s*\{[^}]*max-width:\s*min\(20rem, calc\(100vw - 3rem\)\)/.test(css));
    check("a legislature's quoted record wraps anywhere", /\.leg-ballot\s*\{\s*overflow-wrap:\s*anywhere/.test(css));
  });
}

/* Six scrollIntoView calls passed { behavior: "smooth" }, which overrides
 * the stylesheet's reduced-motion rule, so picking a district or a county
 * animated a long scroll for a reader who had asked for less motion
 * (TECH-16). Every one asks KYC.scrollBehavior(). */
function testMotion() {
  const dir = path.join(SITE, "assets");
  const literal = fs.readdirSync(dir).filter((f) => f.endsWith(".js") && f !== "kyc.js")
    .filter((f) => /behavior:\s*["']smooth["']/.test(fs.readFileSync(path.join(dir, f), "utf8")));
  const kyc = fs.readFileSync(path.join(dir, "kyc.js"), "utf8");
  const fn = (kyc.match(/function scrollBehavior\(\) \{[\s\S]*?\n  \}/) || [""])[0];
  // eslint-disable-next-line no-new-func
  const run = (reduce) => new Function("global", fn + "; return scrollBehavior();")(
    { matchMedia: (q) => ({ matches: reduce && /prefers-reduced-motion: reduce/.test(q) }) });
  suite("assets — a scroll the page makes honours reduced motion", () => {
    check("no module asks for a smooth scroll outright", literal.length === 0, literal.join(", "));
    check("KYC.scrollBehavior() is 'auto' for a reader who asked for less motion, 'smooth' otherwise",
      !!fn && run(true) === "auto" && run(false) === "smooth");
  });
}

/* ========================================================= colour vision */

/* To a deuteranope the split lilac was the Democratic blue (0.8 apart in
 * the dark theme), the light theme's Republican red and independent amber
 * one olive (2.3), and the guide's teal and magenta 3.7 apart (audit
 * 2026-10-17, VISUALS-03, -04, -07). Every map legend's fills are run
 * through the Machado (2009) severity-1 matrices for protanopia,
 * deuteranopia and tritanopia, in linear sRGB, and compared in OKLab (x100)
 * in all three themes, from the tokens themselves. A pair two readers must
 * tell apart by colour alone is 10 apart under protanopia and deuteranopia
 * and 7 under tritanopia; a pair one side of which is hatched (split,
 * none: KYC.svgFill) carries a second cue and needs 5. */
function testColourVision(css) {
  const block = (sel) => {
    const i = css.indexOf(sel + " {");
    const out = {};
    for (const m of css.slice(i, css.indexOf("\n}", i)).matchAll(/--([\w-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim();
    return out;
  };
  const base = block(":root");
  const themes = {
    dark: base,
    amoled: Object.assign({}, base, block('[data-theme="amoled"]')),
    light: Object.assign({}, base, block('[data-theme="light"]')),
  };
  const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const hex = (c) => "#" + c.map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
  // A token's colour in a theme, through var() and color-mix(in srgb).
  const resolve = (t, v, depth = 0) => {
    v = v.trim();
    if (depth > 20) throw new Error("token loop at " + v);
    if (/^#[0-9a-f]{6}$/i.test(v)) return v.toLowerCase();
    let m = v.match(/^var\(--([\w-]+)(?:,\s*(.+))?\)$/);
    if (m) return resolve(t, t[m[1]] !== undefined ? t[m[1]] : m[2], depth + 1);
    m = v.match(/^color-mix\(in srgb,\s*(.+?)\s+(\d+)%,\s*(.+)\)$/);
    if (m) {
      const a = rgb(resolve(t, m[1], depth + 1)), b = rgb(resolve(t, m[3], depth + 1)), w = +m[2] / 100;
      return hex(a.map((x, i) => w * x + (1 - w) * b[i]));
    }
    throw new Error("cannot resolve " + v);
  };
  const MATRIX = {
    protanopia: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    deuteranopia: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    tritanopia: [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
  };
  const lin = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const oklab = ([r, g, b]) => {
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    return [0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
      1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
      0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s];
  };
  const seen = (h, k) => {
    const c = rgb(h).map(lin);
    return oklab(MATRIX[k].map((row) => Math.min(1, Math.max(0, row[0] * c[0] + row[1] * c[1] + row[2] * c[2]))));
  };
  const apart = (a, b, k) => { const x = seen(a, k), y = seen(b, k); return 100 * Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]); };
  const lum = (h) => {
    const c = rgb(h).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const HATCHED = new Set(["var(--split)", "var(--none-fill)", "color-mix(in srgb, var(--split) 70%, var(--surface-1))"]);
  const mix70 = (k) => `color-mix(in srgb, var(--${k}) 70%, var(--surface-1))`;
  // The fills each legend draws side by side, as the map modules name them.
  const LEGENDS = {
    "the partisan and state-government maps": ["var(--party-r)", "var(--party-d)", "var(--party-i-fill)",
      "var(--party-r-tint)", "var(--party-d-tint)", "var(--split)", "var(--vacant-fill)",
      "var(--none-fill)", "var(--nonpartisan-fill)", "var(--text)"],
    "the district and legislature maps": [mix70("party-d"), mix70("party-r"), mix70("party-i-fill"),
      mix70("split"), "color-mix(in srgb, var(--party-vacant) 35%, var(--surface-1))"],
    "the guide's categories": ["var(--cat-1)", "var(--cat-2)", "var(--cat-3)", "var(--cat-4)",
      "var(--cat-5)", "var(--none-fill)"],
  };
  // The charts' fills, read from their own rules (wave 2d review: the
  // balance bar and the House squares filled independents with the light
  // theme's text amber, the olive rule 88 removed from every map).
  const ruleFill = (sel) => {
    const m = css.match(new RegExp("^" + sel.replace(/\./g, "\\.") + " \\{ background(?:-color)?: ([^;]+);", "m"));
    if (!m) throw new Error("no fill rule for " + sel);
    return m[1].trim();
  };
  LEGENDS["the balance bar"] = ["r", "d", "i"].map((p) => ruleFill(".bb-" + p));
  LEGENDS["the House squares"] = ["r", "d", "i"].map((p) => ruleFill(".ht-" + p));
  suite("kyc.css — no fill is a text colour (rule 88)", () => {
    const fills = [...css.matchAll(/(?:^|[;{\s])(?:background(?:-color)?|fill)\s*:\s*[^;}]*var\(--party-i\)[^;}]*/g)]
      .map((m) => m[0].trim());
    check("no background or fill draws with --party-i, the independents' text colour", fills.length === 0,
      fills.slice(0, 4).join(" | "));
    const up = css.match(/^\.bb-up \{([^}]*)\}/m);
    check("the bar marks a seat on the ballot with dots, not the map's hatch",
      !!up && /radial-gradient/.test(up[1]) && !/linear-gradient/.test(up[1]), up ? up[1] : "no .bb-up rule");
  });
  suite("kyc.css — legend colours under colour-vision deficiency (Machado 2009)", () => {
    for (const [name, t] of Object.entries(themes)) {
      for (const [legend, fills] of Object.entries(LEGENDS)) {
        const bad = [];
        for (let i = 0; i < fills.length; i++) {
          for (let j = i + 1; j < fills.length; j++) {
            const a = resolve(t, fills[i]), b = resolve(t, fills[j]);
            const hatched = HATCHED.has(fills[i]) || HATCHED.has(fills[j]);
            for (const k of Object.keys(MATRIX)) {
              const need = hatched ? (k === "tritanopia" ? 2 : 5) : (k === "tritanopia" ? 7 : 10);
              const d = apart(a, b, k);
              if (d < need) bad.push(`${fills[i]} ~ ${fills[j]} ${k} ${d.toFixed(1)}`);
            }
          }
        }
        check(`${name}: ${legend}`, bad.length === 0, bad.slice(0, 4).join(" | "));
      }
      // The count scale: each step a step of lightness from the next, the
      // first well apart from "none" and from the page (GUIDE-16: 1.4:1).
      const scale = [1, 2, 3, 4, 5].map((n) => resolve(t, `var(--scale-${n})`));
      const steps = scale.slice(1).map((c, i) => Math.min(...Object.keys(MATRIX).map((k) => apart(c, scale[i], k))));
      const floor = Math.min(...["none-fill", "surface-0"].flatMap((s) =>
        Object.keys(MATRIX).map((k) => apart(scale[0], resolve(t, `var(--${s})`), k))));
      check(`${name}: the count scale's steps, and its first against none and the page`,
        steps.every((d) => d >= 5) && floor >= 10,
        `steps ${steps.map((d) => d.toFixed(1)).join(" / ")}, first ${floor.toFixed(1)}`);
      // A callout writes on these fills in the ink kyc.js names for them.
      const inks = [["split", "split-ink"], ["party-r-tint", "text"], ["party-d-tint", "text"],
        ["vacant-fill", "vacant-ink"], ["none-fill", "text"], ["nonpartisan-fill", "text-inverse"],
        ["cat-1", "cat-1-ink"], ["cat-2", "cat-2-ink"], ["cat-3", "cat-3-ink"], ["cat-4", "cat-4-ink"]]
        .map(([f, ink]) => [f, ratio(resolve(t, `var(--${f})`), resolve(t, `var(--${ink})`))]);
      // Grey means "none": the Eleventh Circuit drawn in it read as missing
      // data (VISUALS-08). Every category has a hue (OKLab chroma).
      const greyish = [1, 2, 3, 4].filter((n) => {
        const [, a, b] = oklab(rgb(resolve(t, `var(--cat-${n})`)).map(lin));
        return Math.hypot(a, b) < 0.05;
      });
      check(`${name}: no guide category is grey`, greyish.length === 0, greyish.map((n) => "cat-" + n).join(", "));
      check(`${name}: a callout's word on its fill, 4.5:1`, inks.every((p) => p[1] >= 4.5),
        inks.map((p) => `${p[0]} ${p[1].toFixed(2)}`).join(" / "));
      // No status or money colour is a party's (VISUALS-06): "Lost primary"
      // was the Republican red, "Open seat" the independents' amber, and a
      // Democrat's "Spent" was in Republican red.
      const parties = ["party-d", "party-r", "party-i", "party-i-fill", "split"].map((p) => resolve(t, `var(--${p})`));
      // Compared as seen without a deficiency: these sit in badges and
      // money tiles, never beside a party's fill in a legend.
      const plain = (a, b) => { const x = oklab(rgb(a).map(lin)), y = oklab(rgb(b).map(lin));
        return 100 * Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]); };
      const shared = ["warn", "danger", "warn-text", "danger-text", "money-out", "money-in"]
        .filter((s) => parties.some((p) => plain(resolve(t, `var(--${s})`), p) < 10));
      check(`${name}: no status or money colour is a party's`, shared.length === 0, shared.join(", "));
    }
    const js = fs.readFileSync(path.join(SITE, "assets", "kyc.js"), "utf8");
    check("the fills the tests call hatched are the ones kyc.js hatches",
      /"var\(--split\)": "split", "var\(--none-fill\)": "none"/.test(js));
  });
}

/* ================================================================== report */

/* ============================================================ senate view */

/* The Senate by the year each seat is next decided. Every expected number
 * here is computed from the data the page loaded, never typed in. */
/* Everyone on the ballot, counted one way: the sidebar, a state's strip and
 * its race headers read 587, 16 and 58 for the same people. The people the
 * results name with no profile here are named in every view of a race, and
 * nobody is said to await a primary that has been held. */
async function testBallotCounts() {
  const { window, D, errors } = await buildPage("states/mi.html");
  await settle(50);
  const KYC = window.KYC;
  const races = window.kycRaces;
  suite("states/mi.html — the state's count is its race headers' sum", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    // The strip splits challengers (held seats) from open-seat candidates
    // (RACES-14); the two still add up to the race headers' sum.
    const strip = [...D.querySelectorAll(".state-hero .badge")].map((b) => b.textContent)
      .filter((t) => / (challengers?|candidates? for open seats) on the ballot$/.test(t));
    const stripSum = strip.reduce((n, t) => n + Number(t.split(" ")[0]), 0);
    const heads = [...D.querySelectorAll(".race-head .badge-money")]
      .map((b) => (/^(\d+) (challenger|candidate)s? on the ballot$/.exec(b.textContent) || [])[1])
      .filter(Boolean).reduce((n, x) => n + Number(x), 0);
    check("the strip equals the race headers added up",
      strip.length > 0 && stripSum === heads, `${strip.join(" + ")} vs ${heads}`);
    const national = window.kycBuildMeta.election.challengersOnBallot;
    // A race with no primary whose ballot has not been read counts its
    // filers as filed, not on the ballot (summary.ballot_known). Every
    // state's races, from the index of everyone: this page holds its own
    // state's (rule 94).
    const known = (r) => !("primaryDate" in r && !r.primaryDate && r.settled === false);
    const all = allRaces().filter(known).reduce((n, r) => n + (r.candidateCount || 0) +
      ((r.results || {}).otherNominees || []).length, 0);
    check("and the national figure is every race's, added up", national === all, `${national} vs ${all}`);
  });

  const index = await buildPage("index.html", { hash: "#/?view=senate" });
  await settle(50);
  const W = index.window;
  const I = index.D;
  /* The sidebar called open-seat candidates "Challengers on the ballot"
   * after the state strips stopped (RACES-14, PR #94 review); on both
   * pages that carry it, the two rows now add up to the national figure. */
  const mapSidebar = await buildPage("map.html");
  suite("index.html and map.html — the sidebar splits challengers from open-seat candidates", () => {
    const e = W.kycBuildMeta.election;
    [["index.html", I], ["map.html", mapSidebar.D]].forEach(([page, doc]) => {
      const ch = doc.getElementById("challengerCount");
      const open = doc.getElementById("openCandidateCount");
      check(page + ": both rows, adding up to everyone on the ballot besides members running for their seat",
        !!ch && !!open && e.openCandidates > 0 &&
          Number(ch.textContent) + Number(open.textContent) === e.challengersOnBallot &&
          Number(open.textContent) === e.openCandidates,
        (ch && ch.textContent) + " + " + (open && open.textContent) + " vs " + e.challengersOnBallot);
    });
  });
  suite("index.html — the people the results name with no profile here", () => {
    const seat = W.kycRaces.find((r) => r.chamber === "Senate" &&
      KYC.cards && W.KYC.cards.unprofiledNames(r).none.length >= 2);
    check("a Senate seat has people the results name with no profile here", !!seat);
    const block = seat && I.getElementById("senate-seat-" + seat.id);
    const section = block && block.closest("section");
    const names = seat ? W.KYC.cards.unprofiledNames(seat).none : [];
    check("the Senate view names them in words, not only in a badge's hover",
      !!section && names.every((n) => [...section.querySelectorAll(".race-note")]
        .some((p) => p.textContent.indexOf(n) !== -1)), seat && seat.id);
    const unknown = W.legislatorsData.find((p) => p.ballotUnknown && !p.raceStatus && !p.unprinted);
    const badge = unknown && W.KYC.cards.card(unknown);
    // A filer a certified list names as a write-in is said to be one, on
    // the list's word: Texas's two declared Senate write-ins read "the
    // published results do not name them" (rule 77). Built here, so the
    // check runs whatever the data holds.
    const filed = W.legislatorsData.find((p) => p.isCandidate);
    const writeIn = Object.assign({}, filed, { raceStatus: null, maybeNamed: null,
      ballotUnknown: true, unprinted: { kind: "write-in", source: "Texas Secretary of State" } });
    const wiCard = W.KYC.standing(writeIn, "card");
    const wiLong = W.KYC.standing(writeIn, "long");
    check("a certified write-in reads as one, credited to the list, and is not counted on the ballot",
      !!wiCard && wiCard.label === "Write-in candidate" && wiLong.label === "Write-in candidate" &&
        wiCard.unknown && /not printed/.test(wiCard.title) &&
        /Texas Secretary of State/.test(wiCard.title) && !/do not name them/.test(wiCard.title),
      wiCard && wiCard.label + " | " + wiCard.title);
    const wiBadge = W.KYC.cards.card(writeIn);
    check("a certified write-in's card says so", /Write-in candidate/.test(wiBadge) &&
      !/Ballot status not known/.test(wiBadge));
    // A race whose only challenger's place on the ballot is not known says
    // that, never "No challenger on the ballot" or "0 challengers".
    const lone = Object.assign({}, W.kycRaces.find((r) => r.settled && r.results), {
      candidateCount: 0, contested: true, ballotUnknown: 1, openSeat: false });
    lone.results = Object.assign({}, lone.results, { otherNominees: [], maybeProfiled: {} });
    const loneBadges = W.KYC.cards.raceBadges(lone);
    check("a race whose only challenger's ballot status is unknown never says nobody is running",
      /ballot status not known/.test(loneBadges) && !/No challenger/.test(loneBadges) &&
        !/>0 (challengers|candidates)/.test(loneBadges), loneBadges.replace(/<[^>]+>/g, " | "));
    check("a filer the results do not name, after the primary, is not said to await it",
      !unknown || (/Ballot status not known/.test(badge) && !/has not been held yet/.test(badge)),
      unknown && unknown.name);
    const maybe = W.legislatorsData.find((p) => p.maybeNamed && p.maybeNamed.length && !p.raceStatus);
    const race = maybe && W.kycRaces.find((r) => r.id === maybe.raceId);
    // Top-two and top-four primaries send the leaders through whatever
    // their party: two Democrats "won" CA-11's primary and members read
    // "Renominated".
    // A member through it for the seat they hold; not a winner seated since
    // in a seat they did not hold, who was never renominated (rule 67).
    const through = W.legislatorsData.filter((p) => p.allPartyPrimary === "top-two" &&
      W.KYC.seated(p) && !p.contestLabel && !p.raceRole && p.raceStatus === "nominee");
    const badges = through.map((p) => W.KYC.cards.card(p));
    check("a member through a top-two primary reads 'Advanced to November', never 'Renominated'",
      through.length > 0 && badges.every((b) => /Advanced to November/.test(b) &&
        !/Renominated/.test(b) && /top two of the all-party primary/.test(b)),
      `${through.length} members; ` + (badges.find((b) => !/Advanced to November/.test(b) ||
        /Renominated/.test(b)) || "").replace(/\s+/g, " ").slice(0, 400));
    // One outcome, one label (GRID-19): a challenger through the same
    // primary read "On the November ballot", which the key defined as
    // winning a primary nobody there wins.
    const mates = W.legislatorsData.filter((p) => p.allPartyPrimary && p.isCandidate &&
      p.raceStatus === "nominee");
    const mateBadges = mates.map((p) => W.KYC.cards.card(p));
    check("a challenger through it reads the same 'Advanced to November' as the member",
      mates.length > 0 && mateBadges.every((b) => /Advanced to November/.test(b) &&
        !/On the November ballot/.test(b)),
      `${mates.length} challengers; ` + (mateBadges.find((b) => !/Advanced to November/.test(b)) || "")
        .replace(/\s+/g, " ").slice(0, 300));
    const key = W.KYC.raceStatusLegend();
    const onBallot = key.find((row) => row.label === "On the November ballot");
    check("the key does not say everyone 'On the November ballot' won a primary (rule 74)",
      !!onBallot && !/Won the primary/.test(onBallot.title), onBallot && onBallot.title);
    const elsewhere = W.legislatorsData.find((p) => !p.allPartyPrimary && p.raceStatus === "nominee" &&
      W.KYC.seated(p) && !p.contestLabel && !p.raceRole);
    check("and a member renominated in a party primary still reads 'Renominated'",
      !!elsewhere && /Renominated/.test(W.KYC.cards.card(elsewhere)));
    check("a name the results may give a profile here is said to be that, not 'no profile'",
      !maybe || (/Result not matched/.test(W.KYC.cards.card(maybe)) &&
        W.KYC.cards.unprofiledNames(race).maybe.some((m) => m.id === maybe.id) &&
        /who may be/.test(W.KYC.cards.unprofiledNote(race))),
      maybe && maybe.name);
  });
}

/* A member running for the House again under the state's new district
 * number is not leaving: Utah read "4 open seats" with all four members
 * running, and "Not seeking re-election" listed eleven nominees. A member
 * who ran under a new number and lost is leaving, and is listed. */
async function testRenumbered() {
  const { window, D, errors } = await buildPage("index.html", { hash: "#/?election=notSeeking" });
  await settle(50);
  const KYC = window.KYC;
  suite("index.html — members running under a new district number", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    const moved = window.kycRaces.filter((r) => r.holderMoved);
    check("the data has seats whose holder runs under a new number", moved.length > 0);
    // Open means no sitting member on the seat's ballot: a holder's move
    // is in the open seat's explanation, or its own badge when a member is
    // running there under the new number.
    const wrong = moved.filter((r) => {
      const badge = KYC.cards.raceBadges(r);
      const mover = r.candidateIds.map(KYC.byId).some((p) => p && p.renumbered && p.contestRaceId === r.id);
      return r.openSeat === mover || (r.openSeat ? !/new district map/.test(badge)
        : !/Holder running in/.test(badge) || />Open seat</.test(badge));
    });
    check("a renumbered seat is open only when no member runs there, and says where its holder went",
      moved.length > 0 && wrong.length === 0, wrong.map((r) => r.id).join(", "));
    const shown = new Set([...D.querySelectorAll("#results .card")].map((c) => c.getAttribute("data-id")));
    const renumbered = window.legislatorsData.filter((p) => p.renumbered);
    check("'Not seeking re-election' leaves out members running again under a new number",
      shown.size > 0 && renumbered.length > 0 && renumbered.every((p) => !shown.has(p.id)),
      renumbered.filter((p) => shown.has(p.id)).map((p) => p.name).join(", "));
    const lost = window.legislatorsData.filter((p) => KYC.seated(p) && p.contestRaceId &&
      p.contestRaceId.startsWith("H-" + p.state + "-") && KYC.offBallot(KYC.contestStatus(p)));
    check("and keeps one who ran under a new number and lost",
      lost.every((p) => shown.has(p.id) && !p.renumbered), lost.map((p) => p.name).join(", "));
  });
  const ut = await buildPage("states/ut.html");
  await settle(50);
  suite("states/ut.html — open seats are seats nobody holding them runs for", () => {
    const strip = [...ut.D.querySelectorAll(".badge")].map((b) => b.textContent);
    const info = ut.window.kycBuildMeta.states.UT;
    check("the strip counts members under a new number apart from open seats",
      info.renumbered > 0 && strip.some((t) => /running under a new district number/.test(t)) &&
        !strip.some((t) => t === "4 open seats"), strip.join(" | "));
  });
}

/* On a phone a menu pushes a history entry so the back gesture closes it,
 * and closing steps back from it. A sort picked there was written to the
 * address, then undone a moment later when the step landed; and with the
 * theme menu open, opening the sort menu closed it again. */
async function testPhoneMenus() {
  const { window, D } = await buildPage("index.html");
  await settle(50);
  window.matchMedia = (q) => ({ media: q, matches: /max-width: 1000px|pointer: coarse/.test(q),
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} });
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const sortPanel = D.getElementById("sortPanel");
  const themePanel = D.getElementById("themePanel");
  D.getElementById("sortButton").click();
  const pushed = !!(window.history.state && window.history.state.kycMenu);
  D.querySelector('#sortPanel [data-sort="name"]').click();
  await wait(300);
  const label = D.getElementById("sortLabel").textContent;
  const hash = window.location.hash;
  const names = [...D.querySelectorAll("#results .card")].slice(0, 6)
    .map((c) => window.KYC.byId(c.getAttribute("data-id")).surname);
  D.getElementById("themeButton").click();
  await wait(50);
  D.getElementById("sortButton").click();
  await wait(300);
  const sortStays = !sortPanel.hidden && themePanel.hidden;
  D.getElementById("themeButton").click();
  await wait(300);
  const themeStays = !themePanel.hidden && sortPanel.hidden;
  suite("index.html — menus on a phone", () => {
    check("opening a menu on a phone gives the back gesture an entry to close it", pushed);
    check("a sort picked on a phone holds after the menu's history step lands",
      label === "Name, A to Z" && /[?&]sort=name\b/.test(hash) &&
        names.every((n, i) => i === 0 || names[i - 1].localeCompare(n) <= 0), `${label} ${hash}`);
    check("opening the sort menu while the theme menu is open keeps it open", sortStays);
    check("and the other way round", themeStays);
  });
}

/* One part of the grid failing to start - as a stale script did, minutes
 * after a deploy - must not leave it on "Loading profiles...". */
async function testBootSurvivesAFailure() {
  const { window, D } = await buildPage("index.html", {
    // The sort's start throws, as the stale script's did.
    data: (w) => { w.KYC.createMenu = () => { throw new Error("rehearsed failure"); }; },
  });
  await settle(50);
  suite("index.html — the grid starts though one of its parts does not", () => {
    check("the cards are drawn", D.querySelectorAll("#results .card").length > 0,
      D.getElementById("resultsLabel").textContent);
    const note = D.querySelector(".results-failed");
    check("and the page says part of it did not start", !!note && /did not start/.test(note.textContent));
    D.querySelector('.chip[data-group="chamber"][data-value="Senate"]').click();
    check("the filters still work", [...D.querySelectorAll("#results .card")].every((c) =>
      /Senate/.test(window.KYC.byId(c.getAttribute("data-id")).chamber)));
  });
  // The first draw itself failing: never "Loading profiles..." over nothing.
  const broken = await buildPage("index.html", {
    data: (w) => { w.KYC.districtOrder = () => { throw new Error("rehearsed draw failure"); }; },
  });
  await settle(50);
  suite("index.html — a draw that fails says so", () => {
    const label = broken.D.getElementById("resultsLabel").textContent;
    check("the label says the profiles could not be drawn, not that they are loading",
      /could not be drawn/.test(label) && !/Loading/.test(label), label);
    check("and the page says part of it did not start", !!broken.D.querySelector(".results-failed"));
  });
}

async function testSenate() {
  const { window, D, errors } = await buildPage("index.html", { hash: "#/?view=senate" });
  await settle(50);
  const KYC = window.KYC;
  const people = window.legislatorsData;
  const races = window.kycRaces;
  const results = D.getElementById("results");
  const toggle = D.getElementById("senateViewToggle");
  const senators = people.filter((p) => KYC.seated(p) && /Senate/.test(p.chamber));
  const year = window.kycBuildMeta.election.year;
  // Every 2026 Senate race is a seat, whoever holds it now; later years are
  // the sitting senators who neither held nor won one.
  const senateRaces = races.filter((r) => r.chamber === "Senate");
  const placed = new Set(senateRaces.flatMap((r) =>
    r.incumbentIds.slice(0, 1).concat(r.winnerId ? [r.winnerId] : [])));
  const unplaced = senators.filter((p) => !placed.has(p.id));
  const ids = (root) => [...root.querySelectorAll(".card")].map((c) => c.getAttribute("data-id"));
  const offBallot = (p) => KYC.offBallot(KYC.contestStatus(p));
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
    const years = [...new Set(senateRaces.map((r) => r.year)
      .concat(unplaced.map((p) => p.nextElection)))].sort();
    check("one top-level group per year, in order",
      groups.length === years.length &&
      years.every((y, i) => titles[i].indexOf("Up in " + y) === 0), titles.join(" | "));
    check("group headings are real headings", groups.every((g) =>
      g.querySelector(":scope > .senate-group-title").tagName === "H2"));

    const regular = (y) => y === year
      ? senateRaces.filter((r) => r.year === y && !r.special)
      : unplaced.filter((p) => p.nextElection === y && !p.senateSpecial);
    check("each group's count is its senators in the data", groups.every((g, i) => {
      const n = regular(years[i]).length;
      return g.getAttribute("data-seats") === String(n) &&
        g.querySelector(".senate-count").textContent.indexOf(n + " seat") === 0;
    }), groups.map((g) => g.getAttribute("data-seats")).join(","));
    check("each group names its class", groups.every((g, i) => {
      const cls = regular(years[i])[0].senateClass;
      return titles[i].indexOf("Class " + ["", "I", "II", "III"][cls]) !== -1;
    }), titles.join(" | "));

    const specials = senateRaces.filter((r) => r.year === year && r.special);
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
    check("the groups hold the whole Senate", groups.reduce((n, g) =>
      n + Number(g.getAttribute("data-seats")), 0) + specials.length === senators.length,
      groups.map((g) => g.getAttribute("data-seats")).join(","));
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
    // Whoever sits in the seat now: its winner once seated, else who held it.
    const lead = (r) => r.winnerId && KYC.seated(KYC.byId(r.winnerId)) ? r.winnerId
      : r.incumbentIds[0];
    check("each seat block leads with its sitting senator",
      upRaces.every((r, i) => !blocks[i] || ids(blocks[i])[0] === lead(r)));
    const race = upRaces.find((r) => r.candidateIds.some((id) => !offBallot(KYC.byId(id))));
    const block = seatOf(race);
    // A winner seated in the seat holds it now, and leads the block instead.
    const running = race ? race.candidateIds.map(KYC.byId)
      .filter((p) => !offBallot(p) && p.id !== race.winnerId) : [];
    check("a 2026 seat lists its race's candidates after the incumbent", !!block &&
      running.length > 0 && running.every((p) => ids(block).indexOf(p.id) > 0 ||
        (p.incumbentId && ids(block).indexOf(p.incumbentId) > 0)),
      race ? race.id : "no race");
    check("and labels them as running for this seat",
      !!block && /Running for this seat/.test(block.textContent));
    // The people running, after whoever holds or held the seat.
    const runningIds = (b) => [...b.querySelectorAll(".senate-running .card, .senate-out .card")]
      .map((c) => c.getAttribute("data-id"));
    // One order for a race's people in every view (TRUST-15): the race's
    // own, which the pipeline sorts by surname.
    check("the people running are in the race's own order", upRaces.every((r, i) => {
      const b = blocks[i];
      if (!b) return true;
      const at = runningIds(b).filter((id) => !offBallot(KYC.byId(id)))
        .map((id) => KYC.racePosition(KYC.byId(id)));
      return at.every((v, j) => j === 0 || at[j - 1] <= v);
    }));
    check("and the order is said under them", blocks.filter(Boolean).some((b) =>
      b.querySelector(".senate-running .race-order")));
    // The holder has a column of their own, so the running column opens
    // with someone else: "The seat's holder first" made Barry Moore
    // Alabama's senator.
    const notes = blocks.filter(Boolean).map((b) => b.querySelector(".senate-running .race-order"))
      .filter(Boolean);
    check("which never says the first name listed holds the seat",
      notes.length > 0 && notes.every((n) => n.textContent === KYC.RACE_ORDER_PLAIN),
      notes.map((n) => n.textContent).find((t) => t !== KYC.RACE_ORDER_PLAIN) || "");
    // The Senate filing's profile, as the state page and the map show it -
    // never the House member's, whose money is the House seat's (RACES-03).
    const movers = people.filter((p) => !p.isCandidate && /House/.test(p.chamber) &&
      /^S-/.test(p.contestRaceId || "") && !offBallot(p));
    check("a member running for a Senate seat appears under it, once, as that filing",
      movers.length > 0 && movers.every((p) => {
        const race = races.find((r) => r.id === p.contestRaceId);
        const b = seatOf(race);
        const shown = b ? ids(b) : [];
        const filing = race.candidateIds.includes(p.alsoRunningId) ? p.alsoRunningId : p.id;
        return shown.includes(filing) && shown.filter((id) => id === p.id ||
          id === p.alsoRunningId).length === 1;
      }), movers.map((p) => p.name).join(", "));
    const stateOf = (race) => [...race.incumbentIds, ...race.candidateIds];
    check("the same profile the race lists, as the state page and the map list it",
      movers.every((p) => {
        const race = races.find((r) => r.id === p.contestRaceId);
        const shown = ids(seatOf(race));
        return shown.filter((id) => stateOf(race).includes(id) ||
          id === race.winnerId).length === shown.length;
      }));

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
      const all = runningIds(b);
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
  const KYC = window.KYC;
  // An appointee is never "renominated": they were not nominated to the seat.
  const renominated = people.find((p) => KYC.seated(p) && p.chamber === "Senate" &&
    p.raceStatus === "nominee" && !p.contestLabel && !p.appointed && !p.raceRole);
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

  suite("index.html — prices are labelled final once the polls close", () => {
    // odds.yml stops refreshing at the first poll closing; from Election Day
    // on, the page says these are the final prices and not results.
    check("before Election Day they are live prices",
      !KYC.odds.finalPrices(new Date(2026, 9, 14, 12)));
    check("on Election Day and after they are final",
      KYC.odds.finalPrices(new Date(2026, 10, 3, 20)) && KYC.odds.finalPrices(new Date(2026, 10, 20)));
  });

  suite("index.html — prediction markets and polling averages", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    const control = results.querySelector(".odds-control");
    // The people first, the markets after them (audit 2026-10-13, CG-14).
    check("the Senate view ends with the markets on control of the chamber",
      !!control && control.querySelectorAll(".odds-market").length >= 1 &&
        results.lastElementChild === control);
    const seat = results.querySelector(".senate-seat .odds");
    check("a seat's markets come after its people",
      !!seat && !!seat.parentNode.querySelector(".senate-seat-row") &&
        (seat.parentNode.querySelector(".senate-seat-row").compareDocumentPosition(seat) & 4));
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

    check("the prices come from data/odds.js, keyed by race id",
      !!window.kycOdds && !!window.kycOdds.races["S-TX-2026"] &&
        Object.keys(window.kycOdds.races).some((id) => /^H-/.test(id)));

    // Markup in a market label never reaches the page as markup.
    window.kycOdds.races.X_HOSTILE = { markets: [
      { source: "kalshi", url: "https://kalshi.com/markets/x", title: "<b>x</b>", outcomes: [
        { label: "<img src=x onerror=alert(1)>", party: "r", price: 0.6 },
        { label: "Other", party: "d", price: 0.4 }] }] };
    const holder = D.createElement("div");
    holder.innerHTML = KYC.odds.render({ id: "X_HOSTILE", label: "Test" });
    delete window.kycOdds.races.X_HOSTILE;
    check("market labels are escaped", !holder.querySelector("img") && !holder.querySelector("b") &&
      /onerror/.test(holder.textContent));
    check("a race with no odds renders nothing", KYC.odds.render({ id: "nope", label: "x" }) === "");
    check("prices are written as the market writes them",
      KYC.odds.percent(0.995) === ">99%" && KYC.odds.percent(0.004) === "<1%" &&
        KYC.odds.percent(0.384) === "38%");
  });

  /* What a market's prices cannot say (audit 2026-10-17): the one-line poll
   * summary showed the alphabetically first average, undated (RACES-08);
   * Kalshi's WY-AL prices added up to 128% and the bar rescaled them into a
   * split neither number said (RACES-23); a party-only market priced a
   * Republican win over a ballot of two Democrats (RACES-22). Each is read
   * page-side, so data/odds.js stays a pure function of its cache (rule 41).
   * The markets are injected: the real ones move twice a day. */
  suite("index.html — what a market's prices cannot say", () => {
    const render = (id, odds, race) => {
      window.kycOdds.races[id] = odds;
      const holder = D.createElement("div");
      holder.innerHTML = KYC.odds.render(Object.assign({ id: id, label: "Test" }, race || {}),
        { compact: true });
      delete window.kycOdds.races[id];
      return holder;
    };
    const polls = render("X_POLLS", { polls: { rows: [
      { aggregator: "270toWin", updated: "October 4, 2026", url: "https://www.270towin.com/x",
        results: [{ label: "A (D)", party: "d", pct: 51.0 }, { label: "B (R)", party: "r", pct: 43.4 }] },
      { aggregator: "Decision Desk HQ", updated: "October 11, 2026", url: "https://decisiondeskhq.com/x",
        results: [{ label: "A (D)", party: "d", pct: 52.2 }, { label: "B (R)", party: "r", pct: 43.8 }] },
      { aggregator: "RealClearPolling", updated: "", url: "https://www.realclearpolling.com/x",
        results: [{ label: "A (D)", party: "d", pct: 50.0 }, { label: "B (R)", party: "r", pct: 44.0 }] },
    ] } });
    const line = polls.querySelector(".odds-line");
    check("the one-line summary is the most recent average, with its date",
      !!line && /52\.2/.test(line.textContent) && /Decision Desk HQ, updated Oct 11/.test(line.textContent) &&
        /2 more averages/.test(line.textContent), line && line.textContent);

    const thin = render("X_THIN", { markets: [{ source: "kalshi", url: "https://kalshi.com/markets/x",
      title: "x", outcomes: [{ label: "Gray", party: "r", price: 0.98 },
        { label: "Kinney", party: "d", price: 0.30 }] }] });
    check("prices that add up to 128% are quoted without a bar, and say why",
      !thin.querySelector(".odds-bar") && /98%/.test(thin.textContent) && /30%/.test(thin.textContent) &&
        /These last-traded prices add up to 128%, not 100%/.test(thin.textContent) &&
        /may be stale/.test(thin.textContent), thin.textContent);
    // The site holds no volume: it says what it measured, never why
    // (PR #94 review). Polymarket's are displayed prices, not last trades.
    check("no claim about trading volume", !/thin/i.test(thin.textContent), thin.textContent);
    const poly = render("X_POLY", { markets: [{ source: "polymarket", url: "https://polymarket.com/event/x",
      title: "x", outcomes: [{ label: "Democratic Party", party: "d", price: 0.70 },
        { label: "Republican Party", party: "r", price: 0.12 }] }] });
    check("a Polymarket sum short of 100% is not called last trades or stale",
      /These prices add up to 82%, not 100%/.test(poly.textContent) &&
        !/last-traded|stale/.test(poly.textContent), poly.textContent);
    const fine = render("X_FINE", { markets: [{ source: "kalshi", url: "https://kalshi.com/markets/x",
      title: "x", outcomes: [{ label: "Gray", party: "r", price: 0.95 },
        { label: "Kinney", party: "d", price: 0.04 }] }] });
    check("prices that add up to about a dollar keep their bar, with no note",
      !!fine.querySelector(".odds-bar") && !fine.querySelector(".odds-flag"));

    // A settled race whose November ballot is two or more Democrats, found
    // in the data rather than named.
    const onBallot = (race) => race.incumbentIds.concat(race.candidateIds).map(KYC.byId)
      .filter((p) => p && (p.isCandidate || (p.contestRaceId || p.raceId) === race.id) &&
        KYC.onNovemberBallot(p.isCandidate ? p.raceStatus : KYC.contestStatus(p)));
    const same = window.kycRaces.find((r) => r.settled && !(r.results && r.results.otherNominees || []).length &&
      onBallot(r).length >= 2 && onBallot(r).every((p) => p.party === "Democrat"));
    check("the data holds a race whose November ballot is one party", !!same);
    const partyMarket = { markets: [{ source: "polymarket", url: "https://polymarket.com/event/x",
      title: "x", outcomes: [{ label: "Democratic Party", party: "d", price: 0.95 },
        { label: "Republican Party", party: "r", price: 0.04 }] }] };
    if (same) {
      const shown = render(same.id, partyMarket, same);
      check("a party-only market over a one-party ballot says it cannot tell them apart",
        /Everyone on this November ballot is a Democrat; this market resolves on the party only/
          .test(shown.textContent), same.id + ": " + shown.textContent);
    }
    const mixed = window.kycRaces.find((r) => r.settled && onBallot(r).some((p) => p.party === "Democrat") &&
      onBallot(r).some((p) => p.party === "Republican"));
    const plain = render(mixed.id, partyMarket, mixed);
    check("a party-only market over a two-party ballot carries no such note",
      !/Everyone on this November ballot/.test(plain.textContent), mixed.id);
  });

  suite("index.html — a race's markets in the grid's race view", () => {
    window.location.hash = "#/";
    window.dispatchEvent(new window.Event("hashchange"));
    D.getElementById("raceViewToggle").click();
    const tails = [...results.children].slice(-2);
    const firstRace = [...results.children].findIndex((c) => c.classList.contains("race"));
    check("the race view ends with control of both chambers, after the races",
      tails.every((t) => t.classList.contains("odds-control")) &&
        /Senate/.test(tails[0].textContent) && /House/.test(tails[1].textContent) &&
        firstRace > 0 && firstRace < results.children.length - 2 &&
        [...results.children].slice(0, firstRace).every((c) => !c.classList.contains("odds-control")));
    const sections = [...results.querySelectorAll("section.race")];
    const senate = sections.filter((s) => /^race-S-/.test(s.id));
    const house = sections.filter((s) => /^race-H-/.test(s.id));
    check("Senate races show their markets, compactly",
      senate.length > 0 && senate.some((s) => s.querySelector(".odds-compact")), String(senate.length));
    check("House races show theirs too",
      house.filter((s) => s.querySelector(".odds-compact")).length > house.length / 2,
      house.filter((s) => s.querySelector(".odds-compact")).length + " of " + house.length);
    D.getElementById("raceViewToggle").click();
  });

  suite("index.html — a race's markets in the profile dialog", () => {
    const member = window.legislatorsData.find((p) => !p.isCandidate && p.chamber === "House" &&
      p.raceId && window.kycOdds.races[p.raceId]);
    check("a House member whose race has a market exists", !!member);
    if (member) {
      KYC.profile.open(member.id);
      const slot = D.getElementById("profileModalRaceOdds");
      check("the dialog shows their race's markets after the people in it",
        !!slot.querySelector(".odds-compact .odds-market") &&
          D.getElementById("profileModalRace").compareDocumentPosition(slot) & 4,
        member.name);
      // On a person's own profile, closed until opened, and saying the
      // site takes nothing from the markets (TRUST-14).
      const block = slot.querySelector("details.odds-collapsed");
      check("closed until the reader opens them, under a heading that says what they are",
        !!block && !block.open && /prediction markets/i.test(block.querySelector("summary").textContent));
      check("and the note says the site has no relationship with the markets",
        /no relationship with these markets and earns no money from them/.test(slot.textContent));
      KYC.profile.close();
      // A state page on a phone closes each race's markets too (VISUALS-15).
      const race = window.kycRaces.find((r) => r.id === member.raceId);
      const html = KYC.cards.raceSection(race, [member], { fullOdds: true, collapsedOdds: true });
      check("a race section can show its markets closed", /<details class="odds odds-compact odds-collapsed"/.test(html));
    }
  });
}

/* ========================================================= redistricting */

/* California's House map before and after Proposition 50. Everything the
 * page says about a person is read from profiles.js, so every expectation
 * here is derived from the same records rather than typed in: a name in a
 * test is a name that goes stale the next time someone moves. */
async function testRedistricting() {
  const page = "districts/ca.html";
  const { window, D, KYC } = await testShared(page);
  const maps = window.kycDistricts && window.kycDistricts.CA;
  const people = window.legislatorsData;
  const races = window.kycRaces;
  // Who sits now (rule 27): a former member holds no district.
  const caHouse = (p) => KYC.seated(p) && p.state === "CA" && /House/.test(p.chamber);
  const holders = (n) => people.filter((p) => caHouse(p) && p.districtNum === n);
  const raceFor = (n) => races.find((r) => r.chamber === "House" && r.state === "CA" && r.district === n);
  const contestOf = (p) => (races.find((r) => r.id === p.contestRaceId) || {}).district;
  const OUT = { eliminated: true, withdrawn: true, unlisted: true };
  const movers = people.filter((p) => caHouse(p) && KYC.runsElsewhere(p) &&
    /^H-CA-/.test(p.contestRaceId) && !OUT[KYC.contestStatus(p)]);
  const cards = () => [...D.querySelectorAll(".plan-card")];
  const focusOf = (card) => [...card.querySelectorAll(".district-statewide use.is-focus")]
    .map((u) => +u.getAttribute("data-district")).sort((a, b) => a - b);
  const click = (el, opts) => el.dispatchEvent(new window.MouseEvent("click",
    Object.assign({ bubbles: true }, opts || {})));

  suite(`${page} — the two maps`, () => {
    check("the maps loaded", !!maps && maps.plans.length === 2);
    check("every district is drawn once, into shared defs",
      D.querySelectorAll(".district-defs > defs > path").length === maps.seats * 2 + 2,
      `${D.querySelectorAll(".district-defs > defs > path").length}`);
    check("a card per map, before then after", cards().length === 2 &&
      /Before/.test(cards()[0].textContent) && /After/.test(cards()[1].textContent));
    cards().forEach((card, i) => {
      const plan = maps.plans[i];
      const shapes = [...card.querySelectorAll(".district-statewide use.district-shape")];
      check(`${plan.title}: the statewide map draws every district`,
        shapes.length === maps.seats, `${shapes.length}`);
      check(`${plan.title}: every shape is this map's own`, shapes.every((u) =>
        u.getAttribute("href") === "#kycd-" + plan.key + "-" + u.getAttribute("data-district")));
      const numbered = new Set([...card.querySelectorAll(".map-frame .district-num")]
        .map((t) => +t.textContent));
      const missing = [];
      for (let n = 1; n <= maps.seats; n++) if (!numbered.has(n)) missing.push(n);
      check(`${plan.title}: every district is numbered, statewide or in an inset`,
        missing.length === 0, missing.join(", "));
    });
  });

  suite(`${page} — who moved comes from the data`, () => {
    const rows = [...D.querySelectorAll(".mover")];
    check("a row per member running in a different California district",
      rows.length === movers.length, `${rows.length} of ${movers.length}`);
    check("each member's group holds both of their districts", movers.every((p) => {
      const group = [...D.querySelectorAll(".mover-group")]
        .find((g) => g.textContent.indexOf(p.name) !== -1);
      const ds = group ? group.getAttribute("data-focus").split(",").map(Number) : [];
      return ds.indexOf(p.districtNum) !== -1 && ds.indexOf(contestOf(p)) !== -1;
    }));
    const first = D.querySelector(".mover-group");
    if (!first) return;          // every mover re-seated: nobody is moving
    check("the first group is the view a visitor lands on",
      first.getAttribute("aria-pressed") === "true");
    const wanted = first.getAttribute("data-focus").split(",").map(Number).sort((a, b) => a - b);
    check("its districts are picked out on both maps",
      cards().every((c) => focusOf(c).join() === wanted.join()), cards().map(focusOf).join(" / "));
  });

  // From January 3 every mover sits in the district they won: nobody is
  // moving, and the checks below are about who was.
  if (!movers.length) return;

  suite(`${page} — the close-ups and cards name who the data names`, () => {
    const [before, after] = cards();
    const beforeText = before.querySelector(".district-closeup").textContent;
    const afterText = after.querySelector(".district-closeup").textContent;
    const fact = (card, n) => [...card.querySelectorAll(".district-fact")].find((f) =>
      f.querySelector(".district-fact-title").textContent.indexOf("CA-" + n + " ") !== -1);
    const ids = (f) => (f ? [...f.querySelectorAll(".card[data-id]")] : [])
      .map((c) => c.getAttribute("data-id")).sort().join();
    focusOf(before).forEach((n) => {
      const held = holders(n);
      check(`CA-${n}: the old map's close-up names who holds the seat`,
        held.length > 0 && held.every((p) => beforeText.indexOf(p.name) !== -1),
        held.map((p) => p.name).join());
      const here = movers.filter((p) => contestOf(p) === n);
      check(`CA-${n}: the new map's close-up names the members running there`,
        here.every((p) => afterText.indexOf(p.name) !== -1), here.map((p) => p.name).join());
      check(`CA-${n}: the old map's card is the seat's holder`,
        ids(fact(before, n)) === held.map((p) => p.id).sort().join());
      const race = raceFor(n);
      const onBallot = [...new Set(race.incumbentIds.concat(race.candidateIds))].map(KYC.byId)
        .filter((p) => p && (p.isCandidate || (p.contestRaceId || p.raceId) === race.id) &&
          /^(nominee|advanced)$/.test(p.isCandidate ? p.raceStatus : KYC.contestStatus(p)));
      check(`CA-${n}: the new map's cards are the race's nominees`,
        onBallot.length > 0 && ids(fact(after, n)) === onBallot.map((p) => p.id).sort().join(),
        ids(fact(after, n)) + " vs " + onBallot.map((p) => p.id).join());
      check(`CA-${n}: the new map's card links to the race on the state page`,
        !!fact(after, n).querySelector('a[href="../states/ca.html#race-' + race.id + '"]'));
    });
  });

  suite(`${page} — every view has a URL`, () => {
    const groups = [...D.querySelectorAll(".mover-group")];
    if (groups[1]) {
      groups[1].click();
      check("picking a group writes it to the address, commas and all",
        window.location.hash === "#/?d=" + groups[1].getAttribute("data-focus"), window.location.hash);
      check("and presses it, and only it", groups[1].getAttribute("aria-pressed") === "true" &&
        groups[0].getAttribute("aria-pressed") === "false");
    }
    click(D.querySelector('.district-statewide use[data-district="12"]'));
    check("clicking a district picks it out",
      window.location.hash === "#/?d=12" && focusOf(cards()[1]).join() === "12", window.location.hash);
    click(D.querySelector('.district-statewide use[data-district="11"]'), { shiftKey: true });
    check("Shift-click adds one", window.location.hash === "#/?d=12,11", window.location.hash);
    // A phone has no Shift key: with Compare on, a plain tap adds one too.
    const compare = D.getElementById("compareToggle");
    compare.click();
    click(D.querySelector('.district-statewide use[data-district="13"]'));
    check("with Compare on, a tap adds a district", window.location.hash === "#/?d=12,11,13",
      window.location.hash);
    click(D.querySelector('.district-statewide use[data-district="11"]'));
    check("and a tap on a picked one takes it off", window.location.hash === "#/?d=12,13",
      window.location.hash);
    compare.click();
    const pick = D.getElementById("districtPick");
    pick.value = "5";
    pick.dispatchEvent(new window.Event("change", { bubbles: true }));
    check("the district list picks one too", window.location.hash === "#/?d=5", window.location.hash);
    check("the close-up follows", /CA-5\b/.test(
      cards()[0].querySelector(".district-closeup").getAttribute("aria-label")));
    const toggle = D.getElementById("ghostToggle");
    toggle.click();
    check("the other map's dashed lines can be hidden",
      D.getElementById("districtsApp").classList.contains("hide-ghosts"));
    toggle.click();
    const card = D.querySelector(".plan-card .card[data-id]");
    card.click();
    check("a card opens the shared profile dialog", !D.getElementById("profileModal").hidden &&
      D.getElementById("profileModalName").textContent === KYC.byId(card.getAttribute("data-id")).name);
    KYC.profile.close();
    check("nothing on the page is unescaped markup from the data",
      !/<script/i.test(D.getElementById("districtsApp").innerHTML));
  });

  const linked = await buildPage(page, { hash: "#/?d=41" });
  suite(`${page} — a shared link opens its own view`, () => {
    check("#/?d=41 lands on CA-41", focusOf(linked.D.querySelector(".plan-card")).join() === "41");
    check("and leaves no group pressed",
      ![...linked.D.querySelectorAll(".mover-group")].some((g) => g.getAttribute("aria-pressed") === "true"));
  });
  const broken = await buildPage(page, { hash: "#/?d=99,abc" });
  suite(`${page} — a broken link falls back to the first group`, () => {
    check("nothing out of range is picked",
      broken.D.querySelector(".mover-group").getAttribute("aria-pressed") === "true");
  });

  const mover = movers[0];
  const expectLink = "districts/ca.html#/?d=" +
    [mover.districtNum, contestOf(mover)].sort((a, b) => a - b).join(",");
  const direct = await buildPage(page, { hash: "#/profile/" + encodeURIComponent(mover.id) });
  suite(`${page} — a profile link opens over the maps`, () => {
    check("the dialog shows the person", !direct.D.getElementById("profileModal").hidden &&
      direct.D.getElementById("profileModalName").textContent === mover.name, mover.name);
    const note = direct.D.querySelector("#profileModalRace .race-redrawn a");
    check("the dialog links to both of their districts",
      !!note && note.getAttribute("href") === "../" + expectLink, note && note.getAttribute("href"));
  });

  const grid = await buildPage("index.html");
  suite("index.html — the profile dialog links to the redrawn lines", () => {
    grid.window.KYC.profile.open(mover.id);
    const note = grid.D.querySelector("#profileModalRace .race-redrawn a");
    check("a member running in a redrawn district gets a link to both districts",
      !!note && note.getAttribute("href") === expectLink, note && note.getAttribute("href"));
    grid.window.KYC.profile.close();
    // From the grid, which holds everyone: the California page holds its
    // own state's people only (rule 94).
    const iowan = grid.window.legislatorsData.find((p) => !p.isCandidate && p.state === "IA" &&
      /House/.test(p.chamber) && !p.contestRaceId && grid.window.kycRaces.some((r) => r.id === p.raceId));
    grid.window.KYC.profile.open(iowan.id);
    const plain = grid.D.querySelector("#profileModalRace .race-redrawn a");
    check("a race in a state whose map did not change links to its one map",
      !!plain && plain.getAttribute("href") === "districts/ia.html#/?d=" + iowan.districtNum &&
        /on the district map/.test(plain.textContent) && !/redrew/.test(plain.textContent),
      plain && plain.textContent);
    grid.window.KYC.profile.close();
  });

  const ca = await buildPage("states/ca.html");
  const ia = await buildPage("states/ia.html");
  suite("state pages — the link to the maps", () => {
    const link = (d) => [...d.querySelectorAll(".state-links a")]
      .find((a) => /districts\//.test(a.getAttribute("href")));
    check("California's page links to its old and new lines",
      link(ca.D) && link(ca.D).getAttribute("href") === "../districts/ca.html" &&
        /Old and new/.test(link(ca.D).textContent));
    check("Iowa's page links to its district map",
      link(ia.D) && link(ia.D).getAttribute("href") === "../districts/ia.html" &&
        /District map/.test(link(ia.D).textContent));
    const sitemap = fs.readFileSync(path.join(SITE, "sitemap.xml"), "utf8");
    check("the sitemap lists every district page",
      fs.readdirSync(path.join(SITE, "districts")).every((f) => sitemap.includes("/districts/" + f)));
  });
}

/* Every other shape of district page: one map, a single seat, a seat with no
 * race this year, a redrawn map clipped to the land, and the old address. */
/* Find my district: the reader's location, placed on the device. */
function at(lat, lon, fail, accuracy) {
  return (window) => {
    Object.defineProperty(window.navigator, "geolocation", { configurable: true, value: {
      getCurrentPosition(ok, err) {
        if (fail) err({ code: fail });
        else ok({ coords: { latitude: lat, longitude: lon,
          accuracy: accuracy === undefined ? 30 : accuracy } });
      },
    } });
  };
}

async function located(page, lat, lon, accuracy) {
  const built = await buildPage(page, { setup: at(lat, lon, 0, accuracy) });
  built.D.getElementById("locateMe").click();
  const out = built.D.getElementById("locateResult");
  // The finer lines load first (kyc-findrep.js), so the answer comes after.
  await until(() => !/Finding your location/.test(out.textContent));
  return { text: out.textContent, html: out.innerHTML, D: built.D, window: built.window,
    served: built.served, errors: built.errors };
}

/* "Find who represents me": a ZIP code typed into the panel on *page*. */
async function askZip(page, zip, opts) {
  const built = await buildPage(page, opts);
  const slot = built.D.querySelector("[data-findrep]");
  if (!slot) return Object.assign(built, { slot: null, out: null, text: "" });
  slot.querySelector(".findrep-zip").value = zip;
  slot.querySelector("form").dispatchEvent(new built.window.Event("submit",
    { bubbles: true, cancelable: true }));
  const out = slot.querySelector(".findrep-result");
  await until(() => !out.hidden && !/Looking up/.test(out.textContent));
  return Object.assign(built, { slot, out, text: out.textContent });
}

/* The same, from a location the browser shares. */
async function askHere(page, lat, lon, accuracy) {
  const built = await buildPage(page, { setup: at(lat, lon, 0, accuracy) });
  const slot = built.D.querySelector("[data-findrep]");
  slot.querySelector("[data-findrep-locate]").click();
  const out = slot.querySelector(".findrep-result");
  await until(() => !out.hidden && !/Finding your location/.test(out.textContent));
  return Object.assign(built, { slot, out, text: out.textContent });
}

/** A row of the answer by its heading. */
function answerRow(out, heading) {
  const row = [...out.querySelectorAll(".findrep-row")]
    .find((r) => r.querySelector("dt").textContent.trim() === heading);
  return row ? row.querySelector("dd") : null;
}

/** Who sits for a House district now, from the data (rule 27), so no test
 *  names a member (rule 68). */
function holdersOf(window, code, n) {
  return window.legislatorsData.filter((p) => window.KYC.seated(p) && p.state === code &&
    /House/.test(p.chamber) && String(p.districtNum) === String(n));
}

async function testFindRep() {
  // Athens, Ohio: OH-12 on the map members were elected on, OH-2 on 2026's.
  const athens = await askZip("index.html", "45701");
  const { window, out } = athens;
  const KYC = window.KYC;
  const oh = (window.kycLookup || {}).OH;
  const entry = oh && oh.zips["45701"];
  suite("index.html — find who represents you, by ZIP code (GRID-06, PERSONA-04)", () => {
    check("no page errors", athens.errors.length === 0, athens.errors.join(" | "));
    const slot = athens.slot;
    check("the home page's hero holds the panel, above the state picker",
      !!slot && !!slot.closest(".intro") &&
        !!(slot.compareDocumentPosition(athens.D.getElementById("introForm")) &
          window.Node.DOCUMENT_POSITION_FOLLOWING));
    const note = slot.querySelector(".findrep-privacy");
    check("beside the control, in view: the ZIP code and location stay on the device",
      !!note && /stay on this device/.test(note.textContent) && /sends them nowhere/.test(note.textContent) &&
        slot.querySelector(".findrep-zip").getAttribute("aria-describedby") === note.id);
    check("only Ohio's lookup and legislature files were loaded, each at its version (rule 76)",
      athens.served.length === 2 && athens.served.every((s) => /\?v=[0-9a-f]{10}$/.test(s)) &&
        athens.served.some((s) => /^\/data\/lookup\/oh\.js/.test(s)) &&
        athens.served.some((s) => /^\/data\/legislature\/oh\.js/.test(s)), athens.served.join(", "));
    check("the lookup's threshold is the build's (rule 85)", window.kycLookupIndex.whole === 0.99);
    check("the answer is Ohio's", /ZIP 45701, Ohio/.test(athens.text), athens.text.slice(0, 200));
    if (!entry) return check("Ohio's lookup holds 45701", false);
    const record = KYC.recordPhase();
    const now = record ? entry.next[0][0] : entry.cd[0][0];
    const rep = answerRow(out, "U.S. representative");
    const held = holdersOf(window, "OH", now);
    check("it names the representative for the district members sit in, linked to the profile",
      !!rep && (held.length ? held.every((p) => rep.innerHTML.indexOf("#/profile/" + p.id) !== -1 &&
        rep.textContent.indexOf(p.name) !== -1) : /no sitting member|Vacant/.test(rep.textContent)) &&
        rep.textContent.indexOf("OH-" + now) !== -1, rep && rep.textContent);
    const race = answerRow(out, "Your 2026 House race") || answerRow(out, "The 2026 House race");
    const raceId = "H-OH-" + String(entry.next[0][0]).padStart(2, "0") + "-2026";
    check("and the 2026 race on the new map, linked to it on the state page",
      !!race && !!race.querySelector('a[href="states/oh.html#race-' + raceId + '"]') &&
        race.textContent.indexOf("OH-" + entry.next[0][0]) !== -1, race && race.innerHTML.slice(0, 200));
    const raceData = window.kycRaces.find((r) => r.id === raceId);
    const unfiled = ((raceData && raceData.results) || {}).otherNominees || [];
    check("naming the nominees with no profile here too, as every view of a race does",
      !!race && unfiled.every((n) => race.textContent.indexOf(n) !== -1), unfiled.join(", "));
    check("in Ohio, redrawn, the representative and the race are on different maps, and it says so",
      record || (now !== entry.next[0][0] && /redrawn for 2026/.test(athens.text)));
    const sen = answerRow(out, "U.S. senators");
    const senators = window.legislatorsData.filter((p) => KYC.seated(p) && p.state === "OH" &&
      /Senate/.test(p.chamber));
    check("both senators, by name", !!sen && senators.length > 0 &&
      senators.every((p) => sen.textContent.indexOf(p.name) !== -1), sen && sen.textContent);
    const leg = window.kycLegislature && window.kycLegislature.OH;
    const upper = answerRow(out, "Ohio " + leg.chambers.upper.title);
    const su = entry.su[0][0];
    const senMembers = (leg.chambers.upper.members[su] || []).map((m) => m.name);
    check("the state senator, on the legislature page's district",
      !!upper && !!upper.querySelector('a[href="legislature/oh.html#/?d=' + su + '"]') &&
        senMembers.every((n) => upper.textContent.indexOf(n) !== -1), upper && upper.innerHTML);
    const lower = answerRow(out, "Ohio " + leg.chambers.lower.title);
    const pct = (s) => Math.round(s * 100) + "%";
    check("a ZIP code across two house districts lists both, each with its share of the land",
      !!lower && entry.sl.length === 2 && entry.sl.every((p) =>
        lower.querySelector('a[href="legislature/oh.html#/?chamber=lower&d=' + p[0] + '"]') &&
        lower.textContent.indexOf(pct(p[1])) !== -1), lower && lower.textContent);
    const county = answerRow(out, "County");
    check("the county, linked to its governments",
      !!county && !!county.querySelector('a[href="counties/oh.html#/?county=' + entry.co[0][0] + '"]'),
      county && county.innerHTML);
    check("and how to vote in Ohio (GRID-16)",
      !!out.querySelector('a[href="states/oh.html#voting"]'));
    check("the hero's own voting link now goes to Ohio's",
      /states\/oh\.html#voting$/.test(athens.slot.querySelector("[data-findrep-vote]").getAttribute("href")));
  });

  const split = await askZip("index.html", "43215");
  const splitEntry = split.window.kycLookup.OH.zips["43215"];
  // A ZIP 99% or more in one district names it alone; found in the data.
  const near = Object.keys(oh.zips).find((z) => oh.zips[z].cd.length > 1 &&
    oh.zips[z].cd[0][1] >= 0.99 && oh.zips[z].cd[0][1] < 1);
  const almost = near ? await askZip("index.html", near) : null;
  const none = await askZip("index.html", "00000");
  const bad = await askZip("index.html", "12");
  suite("index.html — what a ZIP code cannot say (rule 85)", () => {
    const rep = answerRow(split.out, "U.S. representative");
    const now = split.window.KYC.recordPhase() ? splitEntry.next : splitEntry.cd;
    check("a ZIP across a district line lists every district, with its share, and chooses none",
      now.length > 1 && !!rep && rep.querySelectorAll(".findrep-share").length === now.length &&
        now.every((p) => rep.textContent.indexOf("OH-" + p[0]) !== -1), rep && rep.textContent);
    check("and says a ZIP code can cross lines, offering the reader's location",
      /can cross district lines/.test(split.text) && /use your location/.test(split.text) &&
        !!split.out.querySelector('a[target="_blank"][rel~="noopener"]'), split.text.slice(-400));
    check("a ZIP 99% in one district names that one alone", !!almost &&
      (() => {
        const r = answerRow(almost.out, "U.S. representative");
        const e = oh.zips[near].cd;
        return almost.window.KYC.recordPhase() || (!!r && !r.querySelector(".findrep-share") &&
          r.textContent.indexOf("OH-" + e[0][0]) !== -1 && r.textContent.indexOf("OH-" + e[1][0] + ")") === -1);
      })(), near);
    check("a ZIP with no Census ZIP area says why: PO-box-only ZIP codes have none",
      /not one of the Census Bureau's ZIP Code Tabulation Areas/.test(none.text) &&
        /post office boxes/.test(none.text) && none.served.length === 0, none.text);
    check("anything but a ZIP code is asked for again", /five-digit ZIP code/.test(bad.text), bad.text);
  });

  // A ZIP code typed into the grid's search: no profile carries one.
  const searched = await buildPage("index.html", { hash: "#/?q=45701" });
  const searchOut = searched.D.querySelector("[data-findrep] .findrep-result");
  await until(() => /ZIP 45701, Ohio/.test(searchOut.textContent));
  suite("index.html — a ZIP code in the search (GRID-06)", () => {
    check("is answered by the hero's panel, not 'try a state code' alone",
      /ZIP 45701, Ohio/.test(searchOut.textContent) &&
        searched.D.querySelector("[data-findrep] .findrep-zip").value === "45701",
      searchOut.textContent.slice(0, 120));
  });

  // The reader's location, on the home page.
  const here = await askHere("index.html", 39.33, -82.10, 25);
  const paris = await askHere("index.html", 48.8566, 2.3522, 25);
  suite("index.html — find who represents you, from a location", () => {
    check("no page errors", here.errors.length === 0, here.errors.join(" | "));
    const KYC2 = here.window.KYC;
    const rep = answerRow(here.out, "U.S. representative");
    const want = KYC2.recordPhase() ? 2 : 12;
    check("Athens, Ohio: the representative of the district on the map members sit under",
      /Your location, Ohio/.test(here.text) && !!rep && rep.textContent.indexOf("OH-" + want) !== -1 &&
        holdersOf(here.window, "OH", want).every((p) => rep.textContent.indexOf(p.name) !== -1),
      rep && rep.textContent);
    const race = answerRow(here.out, "Your 2026 House race") || answerRow(here.out, "The 2026 House race");
    check("and the 2026 race on the new map", !!race && /OH-2\b/.test(race.textContent), race && race.textContent);
    check("the state senator and representative, and the county", !!answerRow(here.out, "County") &&
      here.out.querySelectorAll('a[href^="legislature/oh.html#/?"]').length >= 2);
    check("never 'within about 0 km'", !/about 0 k?m/.test(here.text));
    check("an inland point says nothing of a border or shore", !/border or shore/.test(here.text),
      here.text.slice(-300));
    check("outside every state, it says so and names nothing",
      /not in any state/.test(paris.text) && !paris.out.querySelector(".findrep-row"), paris.text);
  });

  // A state page, a legislature page, a county page: the same panel.
  const ohState = await askZip("states/oh.html", "85004");
  const legPage = await askZip("legislature/oh.html", "45701");
  const coPage = await askZip("counties/oh.html", "45701");
  suite("the panel on the state, legislature and county pages (PERSONA-05, STATEGOV-04)", () => {
    const slot = ohState.slot;
    check("the state page opens with it, for its state, before the voting block",
      !!slot && slot.getAttribute("data-findrep-state") === "OH" &&
        !!(slot.compareDocumentPosition(ohState.D.getElementById("voting")) &
          ohState.window.Node.DOCUMENT_POSITION_FOLLOWING));
    check("with 'How to vote in Ohio' beside it, to the voting block",
      !!slot.querySelector('.findrep-form a[href="#voting"]') &&
        /How to vote in Ohio/.test(slot.querySelector(".findrep-form").textContent));
    check("a ZIP code from another state is answered for that state",
      /ZIP 85004, Arizona/.test(ohState.text), ohState.text.slice(0, 120));
    check("no page errors on the state page", ohState.errors.length === 0, ohState.errors.join(" | "));
    check("the legislature page has it, and answers from its own file",
      !!legPage.slot && legPage.served.every((s) => !/legislature\//.test(s)) &&
        !!legPage.out.querySelector('a[href="../legislature/oh.html#/?d=' +
          legPage.window.kycLookup.OH.zips["45701"].su[0][0] + '"]'), legPage.served.join(", "));
    check("and sends the reader to the state page for Congress, which it does not load, " +
      "carrying the ZIP code in the fragment",
      !!legPage.out.querySelector('a[href="../states/oh.html#findrep?zip=45701"]'));
    check("the county page has it, naming the county on that page",
      !!coPage.slot && !!coPage.out.querySelector('a[href^="../counties/oh.html#/?county="]'));
    check("no page errors on the legislature and county pages",
      legPage.errors.length + coPage.errors.length === 0, legPage.errors.concat(coPage.errors).join(" | "));
  });

  await testFindRepReview(legPage, coPage);
  await testFindRepSecondReview();
}

/* The PR #104 second review: a page with no profiles spoke of congressional
 * lines it lists none of, and lost the ZIP code on the way to the state
 * page; the grid's search did not take ZIP+4. */
async function testFindRepSecondReview() {
  // Downtown Dallas: near a congressional line and a state legislative one.
  const legHere = await askHere("legislature/tx.html", 32.7767, -96.797);
  const stateHere = await askHere("states/tx.html", 32.7767, -96.797);
  // The legislature page's link, followed: the state page asks the ZIP code.
  const followed = await buildPage("states/oh.html", { hash: "#findrep?zip=45701" });
  const followedOut = followed.D.querySelector("[data-findrep] .findrep-result");
  await until(() => /ZIP 45701, Ohio/.test(followedOut.textContent));
  // ZIP+4, the panel's own form, typed into the grid's search.
  const plus4 = await buildPage("index.html", { hash: "#/?q=43215-1234" });
  const plus4Out = plus4.D.querySelector("[data-findrep] .findrep-result");
  await until(() => /ZIP 43215, Ohio/.test(plus4Out.textContent));
  suite("the panel where no profiles load, and ZIP+4 in the grid (PR #104 second review)", () => {
    check("the state page, at the same spot, does speak of a congressional line (the check below is not vacuous)",
      /congressional district line|several congressional districts/.test(stateHere.text), stateHere.text.slice(-400));
    check("the legislature page's notes speak of no congressional line it does not list",
      !/congressional district line|congressional districts meet|several congressional/.test(legHere.text) &&
        /state legislative district line/.test(legHere.text), legHere.text.slice(-400));
    const congress = answerRow(legHere.out, "Congress");
    check("and its Congress link, for a location, says to use it again on the state page",
      !!congress && /use your location again/.test(congress.textContent) &&
        !!congress.querySelector('a[href="../states/tx.html#findrep"]'), congress && congress.innerHTML);
    const mapLink = legHere.out.querySelector("a[href*='districts/']");
    check("its district map link says it is the congressional map",
      !mapLink || /congressional district/.test(mapLink.textContent), mapLink && mapLink.textContent);
    check("the state page asks a ZIP code the link carried, and drops it from the address",
      /ZIP 45701, Ohio/.test(followedOut.textContent) && !/zip=/.test(followed.window.location.href) &&
        followed.D.querySelector("[data-findrep] .findrep-zip").value === "45701",
      followed.window.location.href);
    check("the grid hands ZIP+4 to the panel by its first five digits",
      /ZIP 43215, Ohio/.test(plus4Out.textContent) &&
        /ZIP code is answered above/.test(plus4.D.getElementById("resultsLabel").textContent),
      plus4Out.textContent.slice(0, 120));
    check("no page errors", legHere.errors.length + stateHere.errors.length + followed.errors.length +
      plus4.errors.length === 0,
      legHere.errors.concat(stateHere.errors, followed.errors, plus4.errors).join(" | "));
  });
}

/* The PR #104 review: the legislature and county pages load no profiles.js,
 * and the panel there named "OH Senate", sent "How to vote" to a #voting the
 * page does not have, and dropped the district map and the state's lookup. */
async function testFindRepReview(legPage, coPage) {
  suite("the panel on pages without profiles.js names the state and links what it has", () => {
    for (const [label, built] of [["legislature", legPage], ["county", coPage]]) {
      const top = built.slot.querySelector(".findrep-form .findrep-vote a");
      check(label + " page: 'How to vote in Ohio' goes to the state page's voting block, " +
        "not a #voting the page does not have",
        !!top && top.getAttribute("href") === "../states/oh.html#voting" &&
          /How to vote in Ohio/.test(top.textContent) && !built.D.getElementById("voting"),
        top && top.outerHTML);
      check(label + " page: the answer calls the state Ohio, never OH",
        /ZIP 45701, Ohio/.test(built.text) && !/\bOH (Senate|House)\b/.test(built.text) &&
          !/How to vote in OH\b/.test(built.text), built.text.slice(0, 160));
      check(label + " page: it links the district map and Ohio's own lookup",
        !!built.out.querySelector('a[href^="../districts/oh.html#/?"]') &&
          /Check with Ohio's own lookup/.test(built.text), built.text.slice(-300));
      check(label + " page: no note about House rows the answer does not show",
        !/redrawn for 2026/.test(built.text));
    }
    const leg = legPage.window.kycLegislature.OH;
    check("the legislature page's answer names the chambers in full",
      !!answerRow(legPage.out, "Ohio " + leg.chambers.upper.title) &&
        !!answerRow(legPage.out, "Ohio " + leg.chambers.lower.title));
  });

  // A district picked in the answer is selected on the page, and the map,
  // below the panel, is brought into view.
  const scrolled = [];
  const picked = await askZip("legislature/oh.html", "45701", { setup: (w) => {
    w.Element.prototype.scrollIntoView = function () { scrolled.push(this.id); };
  } });
  const link = picked.out.querySelector('a[href^="../legislature/oh.html#/?d="]');
  if (link) link.click();
  await until(() => scrolled.indexOf("legMap") !== -1, 1000);
  suite("legislature/oh.html — a district picked in the panel's answer", () => {
    check("is selected, and the map is brought into view",
      !!link && /d=/.test(picked.window.location.hash) && scrolled.indexOf("legMap") !== -1,
      picked.window.location.hash + " " + scrolled.join(","));
  });

  // The territories' and D.C.'s areas, in their own words (rule 75).
  const sanJuan = await askZip("index.html", "00901");
  const dc = await askZip("index.html", "20001");
  suite("index.html — D.C. and the territories: no 'County' (rule 75)", () => {
    check("Puerto Rico's area is a municipio", !answerRow(sanJuan.out, "County") &&
      !!answerRow(sanJuan.out, "Municipio"), sanJuan.text.slice(0, 300));
    check("D.C. is its own county-equivalent: no row for it", /ZIP 20001/.test(dc.text) &&
      !answerRow(dc.out, "County"), dc.text.slice(0, 300));
    check("and is 'the District of Columbia' in a sentence, as its state page says",
      /How to vote in the District of Columbia/.test(dc.text) &&
        !/in District of Columbia\b/.test(dc.text), dc.text.slice(-300));
  });

  // Never "the state" of a territory: no state line on an island, and no
  // "your state's own lookup" where none is linked (rule 75).
  const sanJuanHere = await askHere("index.html", 18.4655, -66.1057, 25);
  const samoa = await askZip("index.html", "96799");
  suite("index.html — a territory's edge is its shore", () => {
    const hit = sanJuanHere;
    check("San Juan, by the shore, is answered for Puerto Rico", /Your location, Puerto Rico/.test(hit.text),
      hit.text.slice(0, 120));
    check("with no word of a state line or another side to live on",
      !/state line|other side of that line|border or shore/.test(hit.text), hit.text.slice(-400));
    check("American Samoa's answer sends no one to 'your state's own lookup'",
      /ZIP 96799, American Samoa/.test(samoa.text) && !/your state/.test(samoa.text), samoa.text.slice(-300));
  });

  // The legislature's members in the legislature page's words.
  const omaha = await askZip("index.html", "68102");
  const anchorage = await askZip("index.html", "99501");
  suite("index.html — a state legislator's party and district, in words", () => {
    check("Nebraska's members are Nonpartisan, never '(N)'",
      /Nonpartisan/.test(omaha.text) && !/\(N\)/.test(omaha.text), omaha.text.slice(0, 400));
    const ak = anchorage.window.kycLegislature && anchorage.window.kycLegislature.AK;
    const entry = anchorage.window.kycLookup.AK.zips["99501"];
    const upper = ak && answerRow(anchorage.out, "Alaska " + ak.chambers.upper.title);
    const names = (entry.su || []).map((p) => ak.chambers.upper.districts[p[0]].name);
    check("Alaska's lettered Senate district reads 'District I', not 'I'",
      !!upper && names.length > 0 && names.every((n) => upper.textContent.indexOf("District " + n) !== -1),
      upper && upper.textContent);
  });

  // A ZIP code across a state line says so, first, and links each state's lookup.
  const crossing = await askZip("index.html", "42223");
  suite("index.html — a ZIP code across a state line", () => {
    const note = crossing.out.querySelector(".findrep-crosses");
    const states = crossing.out.querySelectorAll(".findrep-place");
    check("says it crosses a state line, naming each state with its share",
      !!note && states.length === 2 && /crosses a state line/.test(note.textContent) &&
        /Kentucky/.test(note.textContent) && /Tennessee/.test(note.textContent),
      note && note.textContent);
    check("and links each state's own lookup",
      /Check with Kentucky's own lookup/.test(crossing.text) &&
        /Check with Tennessee's own lookup/.test(crossing.text), crossing.text.slice(-400));
  });

  // Just inside Missouri, a block from the Kansas line.
  const kc = await askHere("index.html", 39.09, -94.6050, 25);
  const kcFailed = await buildPage("index.html", { refuse: /^\/data\/lookup\/mo\.js$/,
    setup: at(39.09, -94.6050, 0, 25) });
  const failedSlot = kcFailed.D.querySelector("[data-findrep]");
  failedSlot.querySelector("[data-findrep-locate]").click();
  const failedOut = failedSlot.querySelector(".findrep-result");
  await until(() => !failedOut.hidden && !/Finding your location/.test(failedOut.textContent));
  const hit = await kc.window.KYC.findRep.where(-94.6050, 39.09, 25);
  const kansas = await kc.window.KYC.findRep.where(-94.6050, 39.09, 25, "KS");
  suite("index.html — a location near a state line", () => {
    const inMissouri = /Your location, Missouri/.test(kc.text);
    check("the point is within Kansas's margin too, so the refusal below is a real test",
      kansas.code === "KS" && kansas.found.cd.kind !== "none" && !kansas.found.cd.inside.length, kansas.code + " " +
        (kansas.found && kansas.found.cd.kind));
    check("Kansas City, Missouri, a block from Kansas, is answered for Missouri", inMissouri,
      kc.text.slice(0, 120));
    check("and says it is near the state's border, which a district line note would not",
      /Missouri's border or shore/.test(kc.text) && /If you live on the other side of that line/.test(kc.text),
      kc.text.slice(-500));
    check("with Missouri's file refused, the neighbour's edge is not answered: it did not load",
      !inMissouri || (/did not load/.test(failedOut.textContent) &&
        !/Your location, Kansas/.test(failedOut.textContent)), failedOut.textContent);
    check("the legislature's coarser lines are read with a wider margin, by the file's own figure",
      !!hit.leg && hit.leg.lineErrorKm > 0 &&
        Math.abs(hit.legMarginKm - (hit.marginKm + hit.leg.lineErrorKm)) < 1e-9,
      hit.leg && [hit.marginKm, hit.legMarginKm, hit.leg.lineErrorKm].join(" "));
  });

  // The grid: a ZIP code in the search says where it was answered.
  const searched = await buildPage("index.html", { hash: "#/?q=45701" });
  const senate = await buildPage("index.html", { hash: "#/?view=senate&q=45701" });
  const senateOut = senate.D.querySelector("[data-findrep] .findrep-result");
  await until(() => /ZIP 45701, Ohio/.test(senateOut.textContent));
  suite("index.html — the grid's empty state for a ZIP code", () => {
    const note = searched.D.querySelector("#noResults .empty-zip");
    check("says the ZIP code was answered above, with a way there that keeps the search",
      !!note && !note.hidden && /answered\s+above/.test(note.textContent) &&
        !!note.querySelector("button[data-findrep-reveal]") && !note.querySelector('a[href="#findrep"]'),
      note && note.outerHTML);
    check("and the results label says so",
      /ZIP code is answered above/.test(searched.D.getElementById("resultsLabel").textContent));
    check("the Senate view hands a ZIP code to the panel too", /ZIP 45701, Ohio/.test(senateOut.textContent),
      senateOut.textContent.slice(0, 120));
  });

  // A ZIP code typed into the grid's search, which also reads states,
  // districts and officials (#103): the hero's panel answers it, the grid
  // says so in both its line and its empty state, Escape takes it back, and
  // typed again after a clear it is asked again.
  const typed = await buildPage("index.html");
  const tw = typed.window, TD = typed.D;
  const heroOut = TD.querySelector("[data-findrep] .findrep-result");
  const heroZip = TD.querySelector("[data-findrep] .findrep-zip");
  const typedLabel = () => TD.getElementById("resultsLabel").textContent.replace(/\s+/g, " ");
  typeInto(tw, TD, "43215");
  await until(() => /ZIP 43215, Ohio/.test(heroOut.textContent), 4000);
  await settle(250);
  const firstLabel = typedLabel();
  const zipNoteShown = TD.querySelector("#noResults .empty-zip");
  const emptyShown = !TD.getElementById("noResults").hidden;
  const cardsShown = TD.querySelectorAll("#results .card").length;
  const officialsShown = !TD.getElementById("officialResults").hidden;
  TD.getElementById("searchInput").dispatchEvent(new tw.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  await settle(250);
  const clearedLabel = typedLabel();
  const clearedHash = tw.location.hash;
  const noteAfterClear = TD.querySelector("#noResults .empty-zip");
  const noteGone = !noteAfterClear || noteAfterClear.hidden;
  heroZip.value = "";
  typeInto(tw, TD, "43215");
  await until(() => heroZip.value === "43215", 4000);
  suite("index.html — a ZIP code typed into the grid's search", () => {
    check("the hero's panel answers it, with the ZIP code in its box",
      /ZIP 43215, Ohio/.test(heroOut.textContent) && !!answerRow(heroOut, "U.S. senators"),
      heroOut.textContent.slice(0, 160));
    check("the results line says it was answered above", /ZIP code is answered above/.test(firstLabel),
      firstLabel);
    check("with no profile shown, the empty state says so and offers the answer",
      cardsShown > 0 || (emptyShown && !!zipNoteShown && !zipNoteShown.hidden &&
        !!zipNoteShown.querySelector("button[data-findrep-reveal]")),
      cardsShown + " " + (zipNoteShown && zipNoteShown.outerHTML));
    check("and no official is offered for a ZIP code", !officialsShown);
    check("Escape takes the query and the ZIP words back",
      !/ZIP code/.test(clearedLabel) && !/[?&]q=/.test(clearedHash) &&
        noteGone,
      clearedLabel + " | " + clearedHash);
    check("typed again after a clear, it is asked again", heroZip.value === "43215");
    check("no page errors", typed.errors.length === 0, typed.errors.join(" | "));
  });

  // The states index: no "How to vote" link to the page the reader is on.
  const list = await buildPage("states/index.html");
  const listVote = list.D.querySelector("[data-findrep] [data-findrep-vote]");
  suite("states/index.html — the voting button waits for a state", () => {
    check("hidden until a state is known, never a link to this page",
      !!listVote && (listVote.hidden || !/states\/index\.html$/.test(listVote.getAttribute("href"))),
      listVote && listVote.outerHTML);
  });

  // The map page's sidebar (RACES-12).
  const onMap = await askZip("map.html", "45701");
  suite("map.html — find who represents you in the sidebar (RACES-12)", () => {
    check("the sidebar holds the panel", !!onMap.slot && !!onMap.slot.closest(".sidebar"));
    check("and answers a ZIP code", /ZIP 45701, Ohio/.test(onMap.text) &&
      !!answerRow(onMap.out, "U.S. senators"), onMap.text.slice(0, 200));
    check("no page errors", onMap.errors.length === 0, onMap.errors.join(" | "));
  });
}

// Never "between" one district, or none.
const lonelyBetween = (html) => /between (<strong>[^<]*<\/strong>)?[.,;]/.test(html) ||
  /between\s*$/.test(html);

async function testFindMyDistrict() {
  const places = JSON.parse(fs.readFileSync(path.join(SITE, "..", "district_maps", "places.json"),
    "utf8")).places;
  const town = (code, name) => places[code].find((p) => p[0] === name);
  // Erie, well inside PA-16 (Pittsburgh's point is within 3 km of PA-17).
  const [, plon, plat] = town("PA", "Erie");

  const page = await buildPage("districts/pa.html", { setup: at(plat, plon) });
  const { window, D, errors } = page;
  const KYC = window.KYC;
  const state = window.kycDistricts.PA;
  D.getElementById("locateMe").click();
  const said = D.getElementById("locateResult");
  await until(() => !/Finding your location/.test(said.textContent));
  // A town near a line, found with the lines the page places a reader on:
  // the lookup file's (kyc-findrep.js), loaded by the click above.
  let near = null, nearFound = null;
  for (const p of places.PA) {
    const hit = await KYC.findRep.where(p[1], p[2], 30, "PA");
    const f = hit.code && hit.found.cd;
    if (f && f.kind === "line" && f.inside.length + f.near.length === 2) {
      near = p;
      nearFound = f;
      break;
    }
  }
  suite("districts/pa.html — find my district", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    const button = D.getElementById("locateMe");
    // In visible words beside it: a phone never shows a title (TRUST-10).
    const note = D.getElementById("locateNote");
    check("a Find my district button, saying in view that the location stays on the device",
      !!button && !!note && button.getAttribute("aria-describedby") === "locateNote" &&
        /never sent anywhere/.test(note.textContent) && !note.hidden);
    // Several towns share a name (three Franklins): any one of them will do.
    const off = places.PA.filter((p) => state.places.some((d) => d[0] === p[0])).filter((p) => {
      const xy = KYC.districtMap.project(p[1], p[2]);
      return !state.places.some((d) => d[0] === p[0] &&
        Math.abs(xy[0] - d[1]) <= 0.06 && Math.abs(xy[1] - d[2]) <= 0.06);
    });
    check("every Pennsylvania town lands on its own point", off.length === 0,
      off.slice(0, 3).map((p) => p[0]).join(", "));
    check("Erie is in PA-16, as on record", !said.hidden &&
      /^You are in PA-16\./.test(said.textContent), said.textContent);
    check("and PA-16 is the district shown", D.getElementById("districtPick").value === "16",
      D.getElementById("districtPick").value);
    check("with the state's own lookup to confirm it",
      !!said.querySelector('a[target="_blank"][rel~="noopener"]'));
    check("a Pennsylvania town lies near a line, to test with", !!near);
    check("the finer lines came from Pennsylvania's lookup file, at its version",
      page.served.some((s) => /^\/data\/lookup\/pa\.js\?v=[0-9a-f]{10}$/.test(s)), page.served.join(", "));
    const rep = answerRow(said, "U.S. representative");
    check("the answer names who represents the reader, not only a number (PERSONA-18)",
      !!rep && holdersOf(window, "PA", 16).every((p) => rep.textContent.indexOf(p.name) !== -1) &&
        !!answerRow(said, "U.S. senators"), said.textContent.slice(0, 300));
    check("the reader's point is marked on the map", D.querySelectorAll(".reader-pin").length >= 1 &&
      /your location marked/.test(D.querySelector(".district-statewide").getAttribute("aria-label")));
  });

  const rough = await located("districts/pa.html", plat, plon, 20000);
  const line = near ? await located("districts/pa.html", near[2], near[1], 30) : null;
  suite("districts/pa.html — what the map cannot say", () => {
    check("a fix 20 km rough names no district",
      /too rough to place in a district/.test(rough.text) && !/You are in/.test(rough.text) &&
        /about 20 km/.test(rough.text), rough.text);
    if (line) {
      const both = nearFound.inside.concat(nearFound.near).map((n) => "PA-" + n);
      check("near a line, both districts are named, neither chosen, and it says why",
        /near the line between/.test(line.text) && both.every((s) => line.text.indexOf(s) !== -1) &&
          !/You are in/.test(line.text) &&
          (line.text.match(/cannot say which side you are on/g) || []).length === 1,
        line.text);
      check("and how near: within about 400 m of the line, not 3 km (RACES-01)",
        /Within about 400 m of a line/.test(line.text), line.text);
      check("and the map shows both", line.D.getElementById("districtPick").value === "");
    }
  });

  // Athens, Ohio: OH-12 on the map members were elected on, OH-2 on the
  // 2026 map. Each map's card shows its own district (PERSONA-01).
  const athens = await located("districts/oh.html", 39.33, -82.10, 25);
  // Brooklyn, with a fix good to 1.5 km: more districts in reach than the
  // page can show, which is not an approximate location (RACES-02).
  const brooklyn = await located("districts/ny.html", 40.6710, -73.9814, 1500);
  suite("districts — each map's own district, and where several meet", () => {
    check("no page errors", athens.errors.length === 0, athens.errors.join(" | "));
    check("Athens is in OH-12 on the old map and OH-2 on the new",
      /On the map members were elected on, you are in OH-12\./.test(athens.text) &&
        /On the map for 2026, you are in OH-2\./.test(athens.text), athens.text.slice(0, 200));
    check("the address carries both maps' districts",
      /[#&?]d=2(&|$)/.test(athens.window.location.hash) && /was=12/.test(athens.window.location.hash),
      athens.window.location.hash);
    const cards = athens.D.querySelectorAll(".plan-card");
    const facts = (card) => [...card.querySelectorAll(".district-fact-title")].map((h) => h.textContent);
    check("the old map's card shows OH-12, the new map's OH-2",
      cards.length === 2 && facts(cards[0]).length === 1 && /^OH-12 on the/.test(facts(cards[0])[0]) &&
        facts(cards[1]).length === 1 && /^OH-2 on the/.test(facts(cards[1])[0]),
      facts(cards[0]).concat(facts(cards[1])).join(" | "));
    check("each close-up is of its own map's district, and the reader's point is on both",
      /Close-up: OH-12/.test(cards[0].textContent) && /Close-up: OH-2/.test(cards[1].textContent) &&
        cards[0].querySelectorAll(".reader-pin").length >= 2 && cards[1].querySelectorAll(".reader-pin").length >= 2);
    const rep = answerRow(athens.D.getElementById("locateResult"), "U.S. representative");
    const now = athens.window.KYC.recordPhase() ? 2 : 12;
    check("the answer names the representative of the reader's district on the map members sit under",
      !!rep && rep.textContent.indexOf("OH-" + now) !== -1 &&
        holdersOf(athens.window, "OH", now).every((p) => rep.textContent.indexOf(p.name) !== -1),
      rep && rep.textContent);
    const reopened = athens.window.location.hash;
    check("a shared link opens on the same two districts", /d=2/.test(reopened) && /was=12/.test(reopened));
    check("a fix where several districts meet says so, never 'approximate' or 'about 0 km'",
      /where several districts meet/.test(brooklyn.text) && !/approximate/.test(brooklyn.text) &&
        !/about 0 k?m/.test(brooklyn.text) && /NY-\d+/.test(brooklyn.text), brooklyn.text.slice(0, 200));
    check("a distance under a kilometre is said in metres",
      athens.window.KYC.findRep.distance(30) === "about 30 m" &&
        athens.window.KYC.findRep.distance(2500) === "about 2.5 km");
  });

  // South Houston with a fix good to 2.5 km: four districts in reach on the
  // map members were elected on, one on the 2026 map. The crowded sentence
  // lists the crowded map's districts and names that map, and the other map
  // still says where the reader is (PR #104 review: it listed the 2026
  // map's districts as though they were the crowded ones).
  const houston = await located("districts/tx.html", 29.60, -95.28, 2500);
  const houstonHit = await houston.window.KYC.findRep.where(-95.28, 29.60, 2500, "TX");
  suite("districts/tx.html — crowded on one map only", () => {
    const reachOf = (f) => f.inside.concat(f.near);
    const old = houstonHit.code ? reachOf(houstonHit.found.cd) : [];
    const now = houstonHit.code ? reachOf(houstonHit.found.next) : [];
    check("the point is crowded on the old map and not the new (a real test)",
      old.length > 3 && now.length > 0 && now.length <= 3, old.join(",") + " / " + now.join(","));
    const said = /several districts meet \(([^)]*)\)/.exec(houston.text);
    check("the crowded districts are the old map's, and the sentence names that map",
      !!said && /^on the map members were elected on, /.test(said[1]) &&
        old.every((n) => new RegExp("\\bTX-" + n + "\\b").test(said[1])), houston.text.slice(0, 240));
    check("and the 2026 map's own district is said beside it",
      now.every((n) => new RegExp("On the map for 2026, you [^.]*\\bTX-" + n + "\\b").test(houston.text)),
      houston.text.slice(0, 400));
  });
  const shared = await buildPage("districts/oh.html", { hash: "#/?d=2&was=12" });
  suite("districts/oh.html — a shared link with both maps' districts", () => {
    const cards = shared.D.querySelectorAll(".plan-card");
    check("opens OH-12 on the old map and OH-2 on the new",
      cards.length === 2 && /^OH-12 on the/.test((cards[0].querySelector(".district-fact-title") || {}).textContent) &&
        /^OH-2 on the/.test((cards[1].querySelector(".district-fact-title") || {}).textContent));
  });

  // The lookup file does not load: the page's own lines answer, with their
  // wider margin - never "not in Pennsylvania" for a reader in it.
  const offline = await buildPage("districts/pa.html", { setup: at(plat, plon), refuse: /\/lookup\// });
  offline.D.getElementById("locateMe").click();
  const offOut = offline.D.getElementById("locateResult");
  await until(() => !/Finding your location/.test(offOut.textContent));
  suite("districts/pa.html — when the finer lines do not load", () => {
    check("Erie is still placed in PA-16, on the page's own lines",
      /You are in PA-16\./.test(offOut.textContent) && !/not in Pennsylvania/.test(offOut.textContent),
      offOut.textContent.slice(0, 160));
  });

  const paris = await located("districts/pa.html", 48.8566, 2.3522);
  const denied = await buildPage("districts/pa.html", { setup: at(0, 0, 1) });
  denied.D.getElementById("locateMe").click();
  const kck = await located("districts/mo.html", 39.1067, -94.625);
  const bay = await located("districts/tx.html", 29.55, -94.85);
  const tx = town("TX", "Austin");
  const austin = await located("districts/tx.html", tx[2], tx[1]);
  // Texhoma straddles the line at 36.5 degrees north: 30 m either side of it.
  const texhomaTX = await located("districts/tx.html", 36.4997, -101.7849);
  const texhomaOK = await located("districts/ok.html", 36.5003, -101.7832);
  suite("districts — find my district at the edges", () => {
    check("a location far outside the state says so",
      /not in Pennsylvania/.test(paris.text), paris.text);
    const deniedOut = denied.D.getElementById("locateResult");
    check("a refused location says what to do, and links the state's lookup",
      /did not share a location/.test(deniedOut.textContent) &&
        !!deniedOut.querySelector('a[target="_blank"]'), deniedOut.textContent);
    check("Kansas City, Kansas is not placed in Missouri, nor 'between' one district",
      (/not in Missouri/.test(kck.text) || /at the edge of Missouri or just outside it/.test(kck.text)) &&
        !/You are in MO-/.test(kck.text) && !lonelyBetween(kck.html), kck.text);
    check("over Galveston Bay no sentence names nothing",
      !lonelyBetween(bay.html) && !/between \./.test(bay.text) &&
        !/On the map members were elected on, the map/.test(bay.text), bay.text);
    check("Austin is answered for both maps, naming districts, simplified said once",
      /TX-\d+/.test(austin.text) && (/On both maps/.test(austin.text) ||
        (/On the map for 2026/.test(austin.text) && /On the map members were elected on/.test(austin.text))) &&
        (austin.text.match(/simplified/g) || []).length <= 1 && !lonelyBetween(austin.html), austin.text);
    check("on the state line, neither neighbour claims it outright",
      [texhomaTX.text, texhomaOK.text].every((s) => !/^You are in [A-Z]{2}-\d+\.( |$)/.test(s) ||
        /state line/.test(s)), texhomaTX.text + " || " + texhomaOK.text);
  });
  const ak = await buildPage("districts/ak.html", { setup: at(61.2, -149.9) });
  suite("districts/ak.html — one seat, nothing to find", () => {
    check("no button for a state elected at large", !ak.D.getElementById("locateMe"));
  });
}

async function testDistrictPages() {
  // Texas listed Al Green (TX-9 -> TX-18) and Julie Johnson (TX-32 -> TX-33)
  // under "Running in a different district" after both lost those primaries.
  const txMoves = await buildPage("districts/tx.html");
  suite("districts/tx.html — a member who lost is not 'running'", () => {
    const listed = [...txMoves.D.querySelectorAll(".mover-name")].map((e) => e.textContent);
    const out = txMoves.window.legislatorsData.filter((p) => p.state === "TX" &&
      /House/.test(p.chamber) && txMoves.window.KYC.runsElsewhere(p) &&
      ["eliminated", "withdrawn", "unlisted"].indexOf(txMoves.window.KYC.contestStatus(p)) !== -1);
    check("no one off the ballot in their new district is listed as running",
      out.every((p) => listed.indexOf(p.name) === -1),
      `${out.length} off the ballot; listed: ${listed.join(", ")}`);
    const sentence = (txMoves.D.querySelector(".state-note") || {}).textContent || "";
    check("the count in the sentence is the count listed",
      !listed.length || sentence.indexOf(String(listed.length) + " member") === 0, sentence);
  });

  // A tap changed only an outline, with the district's facts two screens
  // below it on a phone (audit MAP-4). After a pick they come into view.
  const nc = await buildPage("districts/nc.html");
  suite("districts/nc.html — a pick on a phone shows what was picked", () => {
    const win = nc.window;
    win.matchMedia = (q) => ({ media: q, matches: /max-width: 1000px/.test(q),
      addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} });
    Object.defineProperty(win, "innerHeight", { value: 844, configurable: true });
    const scrolled = [];
    win.Element.prototype.scrollIntoView = function () { scrolled.push(this); };
    win.Element.prototype.getBoundingClientRect = function () {
      return { top: this.classList.contains("district-fact") ? 1346 : 0, left: 0,
        width: 300, height: 100, right: 300, bottom: 100 };
    };
    const shape = nc.D.querySelector('.district-statewide [data-district="4"]') ||
      nc.D.querySelector('[data-district="4"]');
    check("NC-4 is drawn to tap", !!shape);
    if (shape) shape.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
    check("the picked district's facts are scrolled into view",
      scrolled.length === 1 && scrolled[0].classList.contains("is-focus") &&
        /4/.test(scrolled[0].querySelector(".district-fact-title").textContent),
      scrolled.map((s) => s.className).join(" | "));
    // Each map has its own facts; a tap on the 2025 map went to the 2024
    // map's, already above the screen, and nothing moved.
    scrolled.length = 0;
    const cardsNow = [...nc.D.querySelectorAll(".plan-card")];
    const second = cardsNow[1] && cardsNow[1].querySelector('[data-district="4"]');
    if (second) second.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
    const after = [...nc.D.querySelectorAll(".plan-card")];
    check("a tap on the second map shows the second map's facts",
      !!second && scrolled.length === 1 && after[1].contains(scrolled[0]),
      scrolled.map((s) => s.className).join(" | "));
  });

  // The folder's own directory (districts/index.html) is not a state's map.
  const files = fs.readdirSync(path.join(SITE, "districts"))
    .filter((f) => f.endsWith(".html") && f !== "index.html");
  suite("districts/ — one page per state and territory", () => {
    check("56 pages", files.length === 56, `${files.length}`);
    const unwired = files.filter((f) => {
      const raw = fs.readFileSync(path.join(SITE, "districts", f), "utf8");
      // With or without the version stamp its URL carries (kyc/assets.py).
      return !new RegExp('src="\\.\\./data/districts/' + f.replace(".html", ".js") + '(\\?v=[0-9a-f]+)?"').test(raw);
    });
    check("each loads its own state's map and no other", unwired.length === 0, unwired.join(", "));
  });

  const ia = await buildPage("districts/ia.html");
  suite("districts/ia.html — a map that did not change", () => {
    const D = ia.D;
    check("no page errors", ia.errors.length === 0, ia.errors.join(" | "));
    check("one map", D.querySelectorAll(".plan-card").length === 1);
    check("no moves to pick from", !D.querySelector(".mover-group"));
    check("no dashed other-map lines to toggle", !D.getElementById("ghostToggle"));
    check("nothing is picked until the reader picks", !D.querySelector(".district-closeup"));
    const pick = D.getElementById("districtPick");
    pick.value = "2";
    pick.dispatchEvent(new ia.window.Event("change", { bubbles: true }));
    check("picking a district shows its close-up", !!D.querySelector(".district-closeup") &&
      ia.window.location.hash === "#/?d=2", ia.window.location.hash);
    const holder = ia.window.legislatorsData.find((p) => !p.isCandidate && p.state === "IA" &&
      p.districtNum === 2);
    check("and its people, from the data",
      !!D.querySelector('.district-fact .card[data-id="' + holder.id + '"]'), holder.name);
    const people = ia.window.legislatorsData;
    const wrong = [...D.querySelectorAll(".district-statewide use.district-shape")].filter((u) => {
      const n = +u.getAttribute("data-district");
      const seated = people.find((p) => !p.isCandidate && p.state === "IA" &&
        /House/.test(p.chamber) && p.districtNum === n);
      return !u.classList.contains("party-" + (seated ? ia.window.KYC.partyKey(seated) : "vacant"));
    });
    check("each district is drawn in its member's party", wrong.length === 0,
      wrong.map((u) => u.getAttribute("data-district")).join(", "));
    check("the legend names only the parties drawn",
      [...D.querySelectorAll(".party-legend .key")].length ===
        new Set(people.filter((p) => !p.isCandidate && p.state === "IA" && /House/.test(p.chamber))
          .map((p) => ia.window.KYC.partyKey(p))).size);
  });

  const fl = await buildPage("districts/fl.html");
  suite("districts/fl.html — the party legend", () => {
    // "Democrat" as an adjective here, "Democratic" on every other legend
    // (VISUALS-18): the party is an adjective on a map key.
    const legend = fl.D.querySelector(".party-legend").textContent;
    check("a key names the party as an adjective, as every other legend does",
      /Democratic/.test(legend) && !/Democrat(?!ic)/.test(legend), legend);
    // A 72-character address ran off a 320px screen (TECH-07): a source's
    // address is a link named by its host.
    const sources = fl.D.querySelector(".districts-sources");
    const link = sources && sources.querySelector('a[href^="https://edr.state.fl.us/"]');
    check("a source's address is a link named by its host, not printed whole",
      !!link && link.textContent === "edr.state.fl.us" && !/https?:\/\//.test(sources.textContent),
      sources && sources.textContent.slice(0, 200));
  });
  suite("districts/fl.html — a seat with no member", () => {
    const vacant = fl.window.kycRaces.filter((r) => r.state === "FL" && r.chamber === "House")
      .map((r) => r.district)
      .filter((n) => !fl.window.legislatorsData.some((p) => fl.window.KYC.seated(p) &&
        p.state === "FL" && /House/.test(p.chamber) && p.districtNum === n));
    // Only while a seat is empty: from January 3 every one is filled.
    if (!vacant.length) return;
    check("the data has a seat with no member", vacant.length > 0, vacant.join(", "));
    const shape = fl.D.querySelector('.plan-card .district-statewide use[data-district="' +
      vacant[0] + '"]');
    check("it is drawn as vacant, not as a party", !!shape && shape.classList.contains("party-vacant"));
    check("and the legend says what that colour means",
      /Vacant seat/.test(fl.D.querySelector(".party-legend").textContent));
  });

  const ak = await buildPage("districts/ak.html");
  suite("districts/ak.html — a seat elected at large", () => {
    const D = ak.D;
    check("no page errors", ak.errors.length === 0, ak.errors.join(" | "));
    check("the one seat is shown without a pick", !!D.querySelector(".district-fact"));
    check("its number reads AL", [...D.querySelectorAll(".district-num")]
      .some((t) => t.textContent === "AL"));
    check("no close-up of the whole state", !D.querySelector(".district-closeup"));
  });

  const pr = await buildPage("districts/pr.html");
  suite("districts/pr.html — a seat with no race in 2026", () => {
    check("no page errors", pr.errors.length === 0, pr.errors.join(" | "));
    check("it says there is no race, not that nobody is running",
      /No race for this seat in 2026/.test(pr.D.getElementById("districtsApp").textContent));
  });

  const tx = await buildPage("districts/tx.html");
  suite("districts/tx.html — a redrawn map, clipped to the land", () => {
    const D = tx.D;
    check("no page errors", tx.errors.length === 0, tx.errors.join(" | "));
    // Words are page text over every view - statewide, insets, close-up.
    // Inside the SVG, Samsung Internet's dark mode lightened a number's dark
    // halo along with the number, and every label bloomed.
    check("no district map draws SVG text", !D.querySelector(".district-map text"),
      D.querySelectorAll(".district-map text").length + " text elements");
    check("its labels are page text on the map's frame",
      D.querySelectorAll(".map-frame > .map-labels .map-label").length > 20);
    const scheme = D.querySelector('meta[name="color-scheme"]').getAttribute("content");
    check("the page declares only the scheme it shows", /^only (dark|light)$/.test(scheme), scheme);
    const clip = D.querySelector(".district-defs clipPath#kycd-land");
    // One path of every old district's rings. One <use> per district froze
    // Texas's page for 11-12 seconds on a mid-range Android phone while
    // Blink resolved the clip.
    const oldPlan = tx.window.kycDistricts.TX.plans[0];
    const ring = (d) => d.split("M").filter(Boolean).length;
    const rings = Object.values(oldPlan.districts).reduce((n, d) => n + ring(d.d), 0);
    check("the land is one path of the old map's districts",
      !!clip && clip.children.length === 1 && clip.children[0].tagName === "path" &&
        ring(clip.children[0].getAttribute("d")) === rings,
      clip && clip.children.length + " children");
    const cards = D.querySelectorAll(".plan-card");
    check("the new map's shapes are drawn inside the clip",
      !!cards[1].querySelector('.district-statewide g[clip-path="url(#kycd-land)"] use.district-shape'));
    check("the old map's are not",
      !cards[0].querySelector('.district-statewide g[clip-path] use.district-shape'));
    check("each map's sources are listed",
      /Census Bureau/.test(D.querySelector(".districts-sources").textContent));
    check("the old map is drawn in its members' parties, the new one in none",
      ![...cards[0].querySelectorAll(".district-statewide use.district-shape")]
        .some((u) => u.classList.contains("party-none")) &&
      [...cards[1].querySelectorAll(".district-statewide use.district-shape")]
        .every((u) => u.classList.contains("party-none")));
    // A district is picked on landing while members are moving (the first
    // group); from January 3 none is, and nothing is picked.
    const picked = !!D.querySelector(".mover-group");
    check("a picked district is outlined over its fill, not refilled", !picked ||
      !!cards[0].querySelector(".district-statewide .district-focus.focus-1") &&
      !cards[0].querySelector(".district-statewide use.district-shape.is-focus.party-none"));
    // The sidebar's list was filled by the state pages' module only, so it
    // was empty here.
    const jump = D.getElementById("stateJump");
    check("the Jump to list names every state and territory",
      jump.options.length === 57, `${jump.options.length} options`);
    check("with this page's state selected", jump.value === "TX", jump.value);
  });

  suite("redistricting/ca.html — the first page's address still answers", () => {
    const raw = fs.readFileSync(path.join(SITE, "redistricting", "ca.html"), "utf8");
    check("it sends readers to the new page", /url=\.\.\/districts\/ca\.html/.test(raw));
    check("and tells search engines not to index it", /noindex/.test(raw));
  });
}

async function testDrawerBack() {
  // Android's back gesture is expected to close an open drawer, not leave
  // the page under it.
  const { window, D } = await buildPage("index.html");
  await new Promise((r) => setTimeout(r, 300));
  const wait = () => new Promise((r) => setTimeout(r, 120));
  const toggle = D.querySelector(".sidebar-toggle");
  toggle.click();
  const pushed = !!(window.history.state && window.history.state.kycDrawer);
  // A sentinel in the grid: a redraw replaces the grid's contents.
  const sentinel = D.createElement("i");
  sentinel.id = "drawerSentinel";
  D.getElementById("results").appendChild(sentinel);
  window.history.back();
  await wait();
  const closedByBack = !D.body.classList.contains("sidebar-open");
  const keptGrid = !!D.getElementById("drawerSentinel");
  toggle.click();
  D.querySelector(".sidebar-scrim").click();
  await wait();
  const popped = !(window.history.state && window.history.state.kycDrawer);
  const shut = !D.body.classList.contains("sidebar-open");
  const chip = D.querySelector('.chip[data-group="party"][data-value="Republican"]');
  chip.click();
  const filtered = /party=Republican/.test(window.location.hash);
  chip.click();
  suite("index.html — Back closes the drawer, and nothing else", () => {
    check("opening the drawer gives it a history entry, at the same address", pushed);
    check("Back closes the drawer", closedByBack);
    check("and does not redraw the grid under it, so a long scroll survives", keptGrid,
      "the grid was redrawn");
    check("closing it with a tap takes its entry off again", popped && shut);
    check("filters still write the address", filtered, window.location.hash);
  });
}

/* The drawer's "Find who represents you" (PERSONA-04): every page's, to
 * the home page's panel. On the home page itself the link is caught: the
 * grid's router would read "#findrep" as a view and clear the filters. */
async function testFindRepNav() {
  const arrived = await buildPage("index.html", { hash: "#findrep" });
  await settle(300);
  const home = await buildPage("index.html", { hash: "#/?party=Republican" });
  await settle(300);
  const { window, D } = home;
  const sentinel = D.createElement("i");
  sentinel.id = "findrepSentinel";
  D.getElementById("results").appendChild(sentinel);
  D.querySelector(".sidebar-toggle").click();
  const opened = D.body.classList.contains("sidebar-open");
  const link = D.querySelector('.site-nav a[data-nav="findrep"]');
  const click = new window.MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
  link.dispatchEvent(click);
  await settle(500);
  const about = await buildPage("about.html");
  const state = await buildPage("states/oh.html");
  suite("the drawer's Find who represents you (PERSONA-04)", () => {
    check("no page errors", arrived.errors.length === 0 && home.errors.length === 0,
      arrived.errors.concat(home.errors).join(" | "));
    check("it opens the list, first, on every page: the home page's panel",
      about.D.querySelector(".site-nav a[data-nav]").getAttribute("href") === "index.html#findrep" &&
        state.D.querySelector(".site-nav a[data-nav]").getAttribute("href") === "../index.html#findrep" &&
        /Find who represents you/.test(link.textContent));
    check("named as the panel is (rule 75)", link.textContent.trim() ===
      arrived.D.querySelector("[data-findrep] .findrep-title").textContent.trim());
    check("arriving from another page puts the reader in the ZIP code field",
      !!arrived.D.activeElement && arrived.D.activeElement.classList.contains("findrep-zip"),
      arrived.D.activeElement && arrived.D.activeElement.outerHTML.slice(0, 80));
    check("and drops the fragment, so the grid does not read it as a view",
      /^(#\/)?$/.test(arrived.window.location.hash), arrived.window.location.hash);
    check("on the home page the link is caught, not followed", opened && click.defaultPrevented);
    check("the drawer closes", !D.body.classList.contains("sidebar-open"));
    check("the reader's filters and grid stay as they were",
      /party=Republican/.test(window.location.hash) && !!D.getElementById("findrepSentinel"),
      window.location.hash);
    check("and the ZIP code field has the focus",
      !!D.activeElement && D.activeElement.classList.contains("findrep-zip"),
      D.activeElement && D.activeElement.outerHTML.slice(0, 80));
  });

  // A page whose own panel answers as the home page's does - it holds
  // profiles - keeps the reader there (PR #118 review): a state page's
  // panel, and the map's, which sits in the drawer itself.
  const follow = async (page) => {
    await until(() => !!page.D.querySelector("[data-findrep][data-findrep-ready]"), 6000);
    const toggle = page.D.querySelector(".sidebar-toggle");
    if (toggle) toggle.click();
    const a = page.D.querySelector('.site-nav a[data-nav="findrep"]');
    const ev = new page.window.MouseEvent("click", { bubbles: true, cancelable: true, button: 0 });
    // Whether the page caught it, read after its own listener (on the
    // document); then nothing is followed, which jsdom cannot do.
    let caught = null;
    page.window.addEventListener("click", (e) => { caught = e.defaultPrevented; e.preventDefault(); },
      { once: true });
    a.dispatchEvent(ev);
    await settle(500);
    const active = page.D.activeElement;
    return { caught, open: page.D.body.classList.contains("sidebar-open"),
      inPanel: !!active && active.classList.contains("findrep-zip") && !!active.closest("[data-findrep]") };
  };
  const onState = await follow(state);
  const map = await buildPage("map.html");
  const onMap = await follow(map);
  const leg = await buildPage("legislature/oh.html");
  const onLeg = await follow(leg);
  suite("the drawer's Find who represents you, on a page with its own panel (PR #118 review)", () => {
    check("no page errors", state.errors.length === 0 && map.errors.length === 0 && leg.errors.length === 0,
      state.errors.concat(map.errors, leg.errors).join(" | "));
    check("a state page's link brings its own panel into view, the ZIP code field focused",
      onState.caught && !onState.open && onState.inPanel, JSON.stringify(onState));
    check("the map's brings the panel in its drawer into view, and leaves the drawer open",
      onMap.caught && onMap.open && onMap.inPanel, JSON.stringify(onMap));
    check("a legislature page's panel names no member of Congress: the link goes home",
      onLeg.caught === false, JSON.stringify(onLeg));
  });

  // One ZIP code's shares add up as its land does, on the panel and the
  // ballot page alike; a third party is named, never "I" (PR #118 review).
  const F = home.window.KYC.findRep;
  suite("the answer's shares and party words (PR #118 review)", () => {
    check("shares of one ZIP code's land add up to 100%, largest remainder first",
      F.pcts([0.335, 0.335, 0.33]).join() === "34%,33%,33%" && F.pcts([0.9151, 0.0849]).join() === "92%,8%" &&
        F.pcts([0.4, 0.3, 0.3]).join() === "40%,30%,30%", F.pcts([0.335, 0.335, 0.33]).join());
    check("a sliver is under 1%, and a share short of the whole is never 100%",
      F.pcts([0.996, 0.004]).join() === "99%,under 1%", F.pcts([0.996, 0.004]).join());
    check("D, R and I as before, and a third party by its own name",
      F.partyLetter({ party: "Democrat" }) === "D" && F.partyLetter({ party: "Republican" }) === "R" &&
        F.partyLetter({ party: "Independent" }) === "I" &&
        F.partyLetter({ party: "Libertarian" }) === "Libertarian" &&
        F.partyLetter({ party: "Green" }) === "Green" && F.partyLetter({ party: "" }) === "");
  });
}

/* GRID-16: a sitting member's card, and a race their seat is in, say how
 * to reach their office; nobody else's does (rule 27). */
async function testContactActions() {
  const page = await buildPage("index.html", { hash: "#/?view=race&state=OH" });
  await settle(300);
  const { window, D, errors } = page;
  const KYC = window.KYC;
  const people = window.legislatorsData;
  const seated = people.filter((p) => KYC.seated(p));
  const others = people.filter((p) => !KYC.seated(p));
  const html = (p) => {
    const box = D.createElement("div");
    box.innerHTML = KYC.cards.card(p);
    return box;
  };
  const wrong = [];
  seated.forEach((p) => {
    const a = html(p).querySelector(".card-cell > a.card-contact");
    const want = p.contactForm || (p.phone ? "tel:" + String(p.phone).replace(/[^\d+]/g, "") : null);
    if (!want ? !!a : !a || a.getAttribute("href") !== want) wrong.push(p.id);
  });
  const leaked = others.filter((p) => html(p).querySelector(".card-contact")).map((p) => p.id);
  const sample = seated.find((p) => p.contactForm) || seated[0];
  const link = sample && html(sample).querySelector("a.card-contact");
  const phoneOnly = Object.assign({}, sample, { contactForm: null, phone: "202-555-0100" });
  const call = html(phoneOnly).querySelector("a.card-contact");
  const campaign = Object.assign({}, sample, { contactForm: null, phone: null, districtOffices: null,
    campaignSite: "https://example.org/" });
  suite("index.html — a way to reach a member's office, on the card (GRID-16)", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("every sitting member's card carries their office's contact form, else its phone",
      seated.length > 0 && wrong.length === 0, wrong.slice(0, 5).join(", "));
    check("beside the card's button, never inside it (a link in a button is not operable)",
      !!link && !link.closest("button") && !!link.parentNode.querySelector("button.card[data-id]"));
    check("a form opens safely in a new tab and is named for whose office it is",
      !!link && link.getAttribute("target") === "_blank" && /noopener/.test(link.getAttribute("rel")) &&
        link.getAttribute("aria-label") === "Contact " + sample.name + "’s office" &&
        /official website|congress-legislators/.test(link.getAttribute("title")));
    check("a phone is a call to the Washington office, with the number in its title",
      !!call && call.getAttribute("href") === "tel:2025550100" && /Washington: 202-555-0100/.test(
        call.getAttribute("title")) && call.textContent.trim() === "Call office");
    check("a campaign site is never offered as the office's contact",
      !html(campaign).querySelector(".card-contact"));
    check("no challenger's or former member's card carries one (rule 27)", leaked.length === 0,
      leaked.slice(0, 5).join(", "));
    const raced = [...D.querySelectorAll("section.race .card-cell > a.card-contact")];
    check("the race view's cards carry it too", raced.length > 0);
  });
  if (!oldCongressSits(window)) return;
  // A holder running for another seat is a line above the race, not a card.
  const moved = seated.find((p) => p.contestRaceId && p.heldRaceId &&
    p.contestRaceId !== p.heldRaceId && p.contestLabel);
  const race = moved && window.kycRaces.find((r) => r.id === moved.heldRaceId);
  if (!race) return;
  const box = D.createElement("div");
  box.innerHTML = KYC.cards.raceSection(race, people.filter((p) =>
    (race.incumbentIds || []).indexOf(p.id) !== -1 || p.contestRaceId === race.id));
  const held = box.querySelector(".race-held");
  suite("index.html — a race whose holder runs elsewhere still says how to reach them (GRID-16)", () => {
    check("the Held by line carries the holder's office contact",
      !!held && !!held.querySelector("a.card-contact"), held ? held.innerHTML.slice(0, 200) : moved.id);
  });
}

/* PROFILES-25: what the job pays, on a sitting member's profile, as the
 * law sets it for their post (kyc/pay.py), with its source. */
async function testPayLine() {
  const page = await buildPage("index.html");
  await settle(300);
  const { window, D, errors } = page;
  const KYC = window.KYC;
  const meta = window.kycBuildMeta.pay;
  const people = window.legislatorsData;
  const open = (p) => {
    window.location.hash = "#/profile/" + encodeURIComponent(p.id);
    window.dispatchEvent(new window.HashChangeEvent("hashchange"));
    const field = D.getElementById("profileModalPayField");
    return { hidden: !field || field.hidden, text: field ? field.textContent : "",
             html: field ? field.innerHTML : "" };
  };
  const plain = people.find((p) => KYC.seated(p) && p.pay && !p.pay.post);
  const leader = people.find((p) => KYC.seated(p) && p.pay && p.pay.post);
  const memberOf = (p) => {
    const m = p.isCandidate && p.incumbentId ? KYC.byId(p.incumbentId) : null;
    return m && m.id !== p.id && KYC.seated(m) ? m : null;
  };
  const challenger = people.find((p) => p.isCandidate && !memberOf(p));
  // A sitting member's filing for another seat is the same person (PROFILES-03).
  const running = people.find((p) => memberOf(p) && memberOf(p).pay);
  const former = people.find((p) => p.formerMember);
  suite("index.html — what the job pays (PROFILES-25)", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    if (!meta) {
      // Another Congress than the table's: nobody has a figure (kyc/pay.py).
      check("no member carries a figure without the table's year",
        people.every((p) => !p.pay), "");
      return;
    }
    check("every sitting member has a figure, and nobody else",
      people.every((p) => !!p.pay === (KYC.seated(p) && !p.isCandidate)));
    const a = plain && open(plain);
    check("a member's profile says the salary the law sets, for the year, with its source",
      !!a && !a.hidden && a.text.indexOf("$" + meta.member.toLocaleString("en-US") + " a year in " +
        meta.year) !== -1 && /the law sets for a member of Congress/.test(a.text) &&
        a.html.indexOf(meta.sources[0].url) !== -1 && /read on/.test(a.text), a && a.text);
    check("what it says of the rates' history is the table's sentence, from the report",
      !!a && !!meta.stood && a.text.indexOf(meta.stood) !== -1 && !/denied/.test(a.text), a && a.text);
    const b = leader && open(leader);
    // "Other members are paid $174,000" was wrong on a leader's profile:
    // the other leaders are paid more too.
    check("a post paid more says the post's rate, by the post's name, and whose rate is a member's",
      !b || (!b.hidden && b.text.indexOf("$" + leader.pay.amount.toLocaleString("en-US")) !== -1 &&
        b.text.indexOf(leader.pay.post) !== -1 && !/Other members/.test(b.text) &&
        b.text.indexOf("A member who is not the Speaker, the President pro tempore or a majority " +
          "or minority leader is paid $" + meta.member.toLocaleString("en-US")) !== -1), b && b.text);
    const c = running && open(running);
    check("a sitting member's filing for another seat shows the member's pay, credited to their record",
      !running || (!c.hidden && c.text.indexOf("$" + memberOf(running).pay.amount
        .toLocaleString("en-US")) !== -1 && /record as the member for/.test(c.text)),
      running ? running.id + ": " + c.text : "");
    check("a challenger's profile names no salary (rule 27)", !challenger || open(challenger).hidden);
    check("nor a former member's", !former || open(former).hidden);
  });
  // Read in a later year than the table's: no figure, rather than a stale one.
  const later = await buildPage("index.html", { now: "2027-02-01T12:00:00Z" });
  await settle(300);
  const sitting = later.window.legislatorsData.find((p) => later.window.KYC.seated(p) && p.pay);
  suite("index.html — what the job pays, read in a later year", () => {
    later.window.location.hash = "#/profile/" + (sitting ? sitting.id : "");
    later.window.dispatchEvent(new later.window.HashChangeEvent("hashchange"));
    const field = later.D.getElementById("profileModalPayField");
    check("the line is not shown once the reader's year is past the table's",
      !sitting || !field || field.hidden);
  });
}

/* VISUALS-31: how a bill becomes law, as two chambers' tracks meeting. The
 * words are page text; the lines are one SVG path with no text (rule 46),
 * drawn from where the boxes fall. jsdom lays nothing out, so the boxes are
 * given a wide figure's places and the stylesheet's "lines shown". */
async function testBillFlow() {
  const page = await buildPage("government/congress.html");
  await settle(100);
  const { window, D, errors } = page;
  const figure = D.querySelector("[data-billflow]");
  const svg = figure && figure.querySelector("svg.billflow-lines");
  // A wide layout: the tracks side by side, each box 60px tall with 30px gaps.
  const place = {};
  const at = (x, y, w) => ({ left: x, right: x + w, top: y, bottom: y + 60, width: w, height: 60 });
  [0, 1].forEach((t) => [0, 1, 2].forEach((s) => { place[`t${t}-${s}`] = at(t * 500, s * 90, 450); }));
  place.joined = at(250, 300, 450);
  place.president = at(250, 390, 450);
  [0, 1, 2, 3].forEach((e) => { place[`end-${e}`] = at(e * 240, 500, 220); });
  place["end-3-then"] = at(720, 590, 220);
  [...figure.querySelectorAll("[data-node]")].forEach((n) => {
    n.getBoundingClientRect = () => place[n.getAttribute("data-node")];
  });
  figure.getBoundingClientRect = () => at(0, 0, 950);
  const real = window.getComputedStyle;
  window.getComputedStyle = (el, ...rest) => (el === svg ? { display: "block" } : real(el, ...rest));
  window.KYC.guide.initBillFlow();
  window.getComputedStyle = real;
  const d = (svg.querySelector("path") || { getAttribute: () => "" }).getAttribute("d");
  suite("government/congress.html — how a bill becomes law, drawn (VISUALS-31)", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("the House's and the Senate's steps, as page text",
      [...figure.querySelectorAll(".billflow-track .billflow-head")].map((h) => h.textContent)
        .join("|") === "In the House|In the Senate" &&
        figure.querySelectorAll('.billflow-track [data-node]').length === 6);
    check("meeting at one text, then the president and four answers, the veto's override under it",
      !!figure.querySelector('[data-node="joined"]') && !!figure.querySelector('[data-node="president"]') &&
        figure.querySelectorAll(".billflow-end").length === 4 &&
        !!figure.querySelector('.billflow-end:last-child [data-node="end-3-then"]'));
    check("each answer says what it makes of the bill, in words",
      [...figure.querySelectorAll(".billflow-result")].map((r) => r.textContent).join("|") ===
        "It is law|It is law, as if signed|It is not law|It is law");
    check("the lines are SVG with no text in it (rule 46), hidden from assistive technology",
      !!svg && svg.getAttribute("aria-hidden") === "true" && !svg.querySelector("text") &&
        svg.querySelectorAll("*").length === 1);
    // 4 steps within the tracks, 2 into the joined box, 1 to the president,
    // 4 to the answers, 1 to the override: 12 lines, each with an arrowhead.
    check("one path: a line and an arrowhead for each of the 12 links", (d.match(/M/g) || []).length === 24, d);
    check("a track meets the joined box inside its edge",
      d.indexOf("M225 240V270H262V299") !== -1 && d.indexOf("M725 240V270H688V299") !== -1, d);
    check("the president fans out to each answer's top",
      [110, 350, 590, 830].every((x) => d.indexOf("H" + x + "V499") !== -1), d);
  });
}

async function testAndroidBack() {
  // A phone's layout: the queries a phone matches.
  const phone = (window) => {
    window.matchMedia = (query) => ({
      media: query,
      matches: /max-width: (1000|760)px|pointer: coarse/.test(query),
      addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
    });
  };
  const { window, D } = await buildPage("index.html", { setup: phone });
  const KYC = window.KYC;
  await new Promise((r) => setTimeout(r, 300));
  const wait = () => new Promise((r) => setTimeout(r, 120));

  // Closing a profile returns to the list as it was drawn. A sitting
  // member's card, whose term the dialog prints.
  const card = [...D.querySelectorAll("#results .card")]
    .find((c) => KYC.seated(KYC.byId(c.getAttribute("data-id"))));
  card.click();
  const opened = /#\/profile\//.test(window.location.hash);
  const sentinel = D.createElement("i");
  sentinel.id = "profileSentinel";
  D.getElementById("results").appendChild(sentinel);
  window.history.back();
  await wait();
  const closed = D.getElementById("profileModal").hidden;
  const kept = !!D.getElementById("profileSentinel");

  // The theme menu, on a touch layout: Back closes it and stays.
  const theme = D.getElementById("themeButton");
  theme.click();
  const menuPushed = !!(window.history.state && window.history.state.kycMenu);
  window.history.back();
  await wait();
  const menuClosed = D.getElementById("themePanel").hidden;
  theme.click();
  D.querySelector('[data-theme-option="dark"]').click();
  await wait();
  const menuPopped = !(window.history.state && window.history.state.kycMenu) &&
    D.getElementById("themePanel").hidden;

  // The term reads as two unbreakable dates.
  card.click();
  const spans = [...D.querySelectorAll("#profileModalTerm .nowrap")].map((x) => x.textContent);
  KYC.profile.close();
  await wait();

  suite("index.html — Back on Android", () => {
    check("a profile opens at its own address", opened, window.location.hash);
    check("Back closes it", closed);
    check("and the grid underneath is not redrawn, so the reader keeps their place", kept,
      "the grid was redrawn from its first card");
    check("the theme menu gets a history entry on a touch layout", menuPushed);
    check("Back closes the menu and stays on the page", menuClosed);
    check("picking a theme closes the menu and takes its entry off", menuPopped);
    check("a short placeholder on a phone", D.getElementById("searchInput").placeholder === "Search…",
      D.getElementById("searchInput").placeholder);
    // In words, as a candidate's term reads (PROFILES-19): "Jan. 3, 2025".
    check("a term's dates never break inside a date, and read in words", spans.length === 2 &&
      spans.every((x) => /^[A-Z][a-z]+\.? \d{1,2}, \d{4}$/.test(x)), spans.join(" | "));
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    check("a chosen Light theme opts out of forced dark (Samsung Internet, Brave)",
      /\[data-theme="light"\] \{[^}]*color-scheme: only light/.test(css));
    // Every :hover rule sits inside @media (hover: hover); strip those
    // blocks and no :hover selector may be left.
    const ungated = css.replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/@media \(hover: hover\) \{[\s\S]*?\n\}/g, "");
    check("hover looks apply only where a pointer hovers",
      !/:hover[^{}]*\{/.test(ungated), (ungated.match(/[^{}]*:hover[^{}]*\{/) || [""])[0].trim());
    check("no grey tap flash", /-webkit-tap-highlight-color: transparent/.test(css));
  });
}

/* jsdom has no layout, so a page that measures itself sees 0 - which the
 * district page reads as "no layout" and draws for 620px. This makes the
 * statewide maps measure *width* instead, as a phone's would. */
function drawnAt(width) {
  return (window) => {
    const real = window.Element.prototype.getBoundingClientRect;
    window.Element.prototype.getBoundingClientRect = function () {
      if (!this.classList || !this.classList.contains("district-statewide")) {
        return real.call(this);
      }
      return { width, height: width, top: 0, left: 0, right: width, bottom: width, x: 0, y: 0 };
    };
  };
}

/* The same, for the partisan map's SVG. */
function mapDrawnAt(width) {
  return (window) => {
    const real = window.Element.prototype.getBoundingClientRect;
    window.Element.prototype.getBoundingClientRect = function () {
      if (this.id !== "usMap") return real.call(this);
      return { width, height: 0, top: 0, left: 0, right: width, bottom: 0, x: 0, y: 0 };
    };
  };
}

async function testMapOnAPhone() {
  // Codes were 10 map units: a phone drew them 3.8px tall, at weight 800 on
  // a 2.5-unit halo. Now they are 11px at the width the map is drawn.
  for (const width of [320, 360, 374, 390, 900]) {
    const page = await buildPage("map.html", { setup: mapDrawnAt(width) });
    suite(`map.html — the map drawn ${width}px wide`, () => {
      const D = page.D;
      check("no page errors", page.errors.length === 0, page.errors.join(" | "));
      // No word sits on another (TECH-08): at 320-390px Mississippi's code
      // sat on Alabama's and West Virginia's on the Vermont callout ("WV T").
      // Boxes from where each word is placed, at 11px bold capitals' size.
      const vb = D.getElementById("usMap").getAttribute("viewBox").split(" ").map(Number);
      const height = width * vb[3] / vb[2];
      const boxes = [...D.querySelectorAll("#mapLabels .map-label")]
        .filter((s) => !s.classList.contains("territory-caption"))
        .map((s) => {
          const callout = s.classList.contains("map-callout");
          const w = Math.max(callout ? 2.3 * 11 : 0, s.textContent.length * 6.8 + 4);
          return { t: s.textContent, x: parseFloat(s.style.left) / 100 * width,
            y: parseFloat(s.style.top) / 100 * height, w, h: callout ? 15 : 13 };
        });
      const overlaps = [];
      boxes.forEach((a, i) => boxes.slice(i + 1).forEach((b) => {
        if (Math.abs(a.x - b.x) * 2 < a.w + b.w - 1 && Math.abs(a.y - b.y) * 2 < a.h + b.h - 1) {
          overlaps.push(a.t + "/" + b.t);
        }
      }));
      check("no state's word covers another's", overlaps.length === 0, overlaps.join(", "));
      // The first collision pass cleared every overlap by sending inland
      // states to the Atlantic column: Kentucky's line ran 136px across the
      // map at 390px, Indiana's 166px at 320px. A code moved within its
      // state stays in the box the build measured clear of its edges, and
      // only the small coastal states (labelRoom under 7) join the column.
      const geo = page.window.kycGeo.states;
      const unit = width / vb[2];
      const screen = (p) => [(p[0] - vb[0]) * unit, (p[1] - vb[1]) * unit];
      const placedOff = [], farAway = [];
      D.querySelectorAll("#mapLabels .map-label").forEach((s) => {
        const code = s.getAttribute("data-state") || s.textContent;
        const shape = geo[code];
        if (!shape || !shape.label || s.classList.contains("territory-label")) return;
        const x = parseFloat(s.style.left) / 100 * width, y = parseFloat(s.style.top) / 100 * height;
        const [lx, ly] = screen(shape.label);
        const room = (shape.labelRoom || 0) * unit;
        if (s.classList.contains("state-code")) {
          if (Math.abs(x - lx) > 1.75 * room + 0.5 || Math.abs(y - ly) > room + 0.5) placedOff.push(code);
        } else if ((shape.labelRoom || 0) >= 7 && Math.hypot(x - lx, y - ly) > 75) {
          farAway.push(code + " " + Math.round(Math.hypot(x - lx, y - ly)) + "px");
        }
      });
      check("a code moved to clear another stays on its own state's land", placedOff.length === 0,
        placedOff.join(", "));
      check("a large state's callout stays beside it, never across the map", farAway.length === 0,
        farAway.join(", "));
      check("and none runs off the screen", boxes.every((b) => b.x - b.w / 2 >= -1 && b.x + b.w / 2 <= width + 1),
        boxes.filter((b) => b.x - b.w / 2 < -1 || b.x + b.w / 2 > width + 1).map((b) => b.t).join(", "));
      // Every word is page text over the map: inside the SVG, Samsung
      // Internet's dark mode lightened a code's dark halo with the code, and
      // every label bloomed.
      check("no text is drawn inside the map's SVG", !D.querySelector("#usMap text"));
      const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
      const rule = (css.match(/\n\.us-map-labels \.map-label\s*\{[^}]*\}/) || [""])[0];
      check("a state's code is 11px on screen, on a backing from the theme",
        /font-size:\s*11px/.test(rule) && /background:\s*var\(--map-label-backing\)/.test(rule) &&
          !/#[0-9a-f]{3,6}/i.test(rule), rule.replace(/\s+/g, " "));
      const codes = (cls) => [...D.querySelectorAll("#mapLabels ." + cls)].map((s) => s.textContent);
      const callouts = codes("map-callout");
      if (width < 500) {
        check("states too small for their code are named in callouts",
          ["RI", "DE", "MD", "NJ", "MA", "CT", "HI"].every((c) => callouts.includes(c)),
          callouts.join(" "));
        check("and are not also labelled in place",
          ["RI", "DE"].every((c) => !codes("state-code").includes(c)));
      } else {
        check("a wide map labels more states in place", callouts.length < 7, callouts.join(" "));
      }
      check("D.C. is named in the strip, not a callout", !callouts.includes("DC") &&
        codes("territory-label").includes("DC"));
      const left = (s) => parseFloat(s.style.left);
      check("labels are placed inside the map's frame", [...D.querySelectorAll("#mapLabels .map-label")]
        .every((s) => left(s) >= 0 && left(s) <= 100 && parseFloat(s.style.top) >= 0 &&
          parseFloat(s.style.top) <= 100));
      const ri = D.querySelector('#mapLabels .map-callout[data-state="RI"]');
      if (ri) {
        ri.dispatchEvent(new page.window.MouseEvent("click", { bubbles: true }));
        check("a callout can be tapped to pick its state",
          /state=RI/.test(page.window.location.hash) &&
            D.querySelector('#usMap .state[data-state="RI"]').getAttribute("aria-pressed") === "true",
          page.window.location.hash);
        check("and its box takes the state's colour and shows it is picked",
          ri.classList.contains("is-selected") && !!ri.style.background);
        check("a callout is not a second tab stop for the state",
          ri.closest('[aria-hidden="true"]') && !ri.hasAttribute("tabindex"));
      }
    });
  }
}

async function testDistrictsOnAPhone() {
  // Two picked districts' numbers printed on top of each other on Texas's
  // statewide map at 390px: "37" 6px from "35" and covering it (RACES-24).
  for (const width of [302, 360, 620]) {
    const page = await buildPage("districts/tx.html", { hash: "#/?d=35,37", setup: drawnAt(width) });
    await settle(50);
    suite(`districts/tx.html#/?d=35,37 — the picked numbers drawn ${width}px wide`, () => {
      const layer = page.D.querySelector(".district-statewide + .map-labels");
      const vb = page.D.querySelector(".district-statewide").getAttribute("viewBox").split(" ").map(Number);
      const height = width * vb[3] / vb[2];
      const boxes = [...(layer ? layer.querySelectorAll(".is-focus") : [])].map((s) => {
        const size = parseFloat(s.style.fontSize);
        const w = (s.textContent.length * 0.6 + 0.44) * size;
        return { t: s.textContent, x: parseFloat(s.style.left) / 100 * width,
          y: parseFloat(s.style.top) / 100 * height, w, h: size * 1.24 };
      });
      const hit = (a, b) => Math.abs(a.x - b.x) * 2 < a.w + b.w && Math.abs(a.y - b.y) * 2 < a.h + b.h;
      check("both picked districts are numbered, neither on the other",
        boxes.length === 2 && !hit(boxes[0], boxes[1]),
        boxes.map((b) => `${b.t}@${b.x.toFixed(0)},${b.y.toFixed(0)}`).join(" "));
      // The first fix stepped "37" a line up, onto district 11's land, with
      // nothing joining it to its own (rule 43). A picked number is on its
      // district, or a callout with a line from its district's own point.
      const plan = page.window.kycDistricts.TX.plans[0];
      const ringsOf = (d) => String(d).split("M").map((part) => {
        const nums = (part.match(/-?\d+(?:\.\d+)?/g) || []).map(Number);
        const ring = [];
        let x = nums[0], y = nums[1];
        if (nums.length >= 2) ring.push([x, y]);
        for (let i = 2; i + 1 < nums.length; i += 2) { x += nums[i]; y += nums[i + 1]; ring.push([x, y]); }
        return ring;
      }).filter((r) => r.length > 2);
      const inside = (rings, x, y) => {
        let hit = false;
        rings.forEach((ring) => {
          for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
            const [xi, yi] = ring[i], [xj, yj] = ring[j];
            if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) hit = !hit;
          }
        });
        return hit;
      };
      const svgMap = page.D.querySelector(".district-statewide");
      const wrong = [...(layer ? layer.querySelectorAll(".is-focus") : [])].filter((s) => {
        const n = s.textContent;
        const x = vb[0] + parseFloat(s.style.left) / 100 * vb[2];
        const y = vb[1] + parseFloat(s.style.top) / 100 * vb[3];
        if (inside(ringsOf(plan.districts[n].d), x, y)) return false;
        const line = svgMap.querySelector('.pick-leader[data-district="' + n + '"]');
        const at = plan.districts[n].at;
        return !(s.classList.contains("is-callout") && line &&
          Math.abs(+line.getAttribute("x1") - at[0]) < 0.01 && Math.abs(+line.getAttribute("y1") - at[1]) < 0.01);
      }).map((s) => s.textContent);
      check("each picked number is on its own district, or joined to it by a line", wrong.length === 0,
        wrong.join(", "));
    });
  }
  // Numbers were sized for a 620px map and scaled with it: on a phone every
  // one was 4px tall. They are 11px at the width the map is drawn, written
  // where they fit, and every district is numbered somewhere.
  for (const [code, width] of [["NY", 286], ["TX", 302], ["CA", 286], ["TX", 620], ["TX", 860]]) {
    const page = await buildPage("districts/" + code.toLowerCase() + ".html",
                                 { setup: drawnAt(width) });
    suite(`districts/${code.toLowerCase()}.html — the map drawn ${width}px wide`, () => {
      const D = page.D;
      const state = page.window.kycDistricts[code];
      check("no page errors", page.errors.length === 0, page.errors.join(" | "));
      [...D.querySelectorAll(".plan-card")].forEach((card, i) => {
        const plan = state.plans[i];
        const written = new Set([...card.querySelectorAll(".district-num")]
          .map((t) => t.textContent));
        const missing = Object.keys(plan.districts).filter((n) => !written.has(n));
        check(`every district on the ${plan.title} is numbered somewhere`,
          missing.length === 0, missing.join(", "));
        const map = card.querySelector(".district-statewide");
        const num = map.closest(".map-frame").querySelector(".map-labels .district-num");
        const size = num && parseFloat(num.style.fontSize);
        check("a statewide number is 11px on screen", Math.abs(size - 11) < 0.05, size);
        // Page text on a backing, not SVG text on a halo: a forced dark mode
        // made the halo as light as the number.
        check("drawn as page text over the map, not inside the SVG",
          !map.querySelector("text") && num.classList.contains("map-label"));
      });
      const titles = [...D.querySelectorAll(".plan-card")[0]
        .querySelectorAll("figure.inset figcaption")].map((f) => f.textContent);
      if (code === "NY") {
        check("Manhattan gets a closer inset", titles.includes("New York, closer"),
          titles.join(" | "));
      }
      if (code === "TX") {
        // A closer inset appears exactly when its inset is drawn narrower
        // than every number in it needs.
        state.insets.filter((i) => i.detail).forEach((inset) => {
          const drawn = Math.min(width, inset.width);
          const closer = inset.detail.every((d) => titles.includes(d.title));
          check(drawn < inset.fits ? `${inset.title} gets its closer insets when drawn too narrow`
                                   : `${inset.title}, drawn whole, gets none`,
            closer === drawn < inset.fits,
            `${drawn}px for ${inset.fits}px: ` + titles.join(" | "));
        });
        const widest = Math.max(...[...D.querySelectorAll("figure.inset")]
          .map((f) => parseFloat(f.style.width)));
        check("no inset is drawn wider than the map", widest <= width, widest);
      }
    });
  }
}

/* ================================================================ guide */

/* Know Your Government, the guide: static, sourced text generated by
 * kyc/government.py, plus what kyc-guide.js fills in from the data. Most of
 * its pages load no profiles, so testShared's "data loaded" does not apply. */
async function testGuide() {
  const slugs = fs.readdirSync(path.join(SITE, "government"))
    .filter((f) => f.endsWith(".html")).map((f) => f.replace(/\.html$/, ""));

  for (const slug of slugs) {
    const page = `government/${slug}.html`;
    const { window, D, errors, sources } = await buildPage(page);
    const KYC = window.KYC;
    const people = sources.includes("../data/people/meta.js");
    suite(`${page} — load and wiring`, () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      check("shared module present", !!KYC);
      check("icon sprite injected, every <use> resolves", (() => {
        const ids = new Set([...D.querySelectorAll("#kyc-sprite symbol")].map((s) => s.id));
        const used = [...D.querySelectorAll("use")].map((u) => (u.getAttribute("href") || "").slice(1));
        return used.length > 0 && used.every((id) => ids.has(id));
      })());
      check("no remote script", !sources.some((s) => /^https?:/.test(s)));
      check("no inline <script> in the page", !/<script>(?!\n)/.test(
        fs.readFileSync(path.join(SITE, page), "utf8")));
      check("one h1, the page's title", D.querySelectorAll("h1").length === 1 &&
        D.title.indexOf(D.querySelector("h1").textContent.trim()) === 0, D.title);
      // "Federal courts" was both the site's link to who sits on them and
      // the guide's link to how they work, in one sidebar.
      const byText = {};
      [...D.querySelectorAll(".sidebar a.nav-link")].forEach((a) => {
        const t = a.textContent.trim();
        // Resolved: the site's "Know Your Government" (../government/index.html)
        // and the guide's own first page (index.html) are one page, one name.
        (byText[t] = byText[t] || new Set()).add(
          new window.URL(a.getAttribute("href"), window.location.href).pathname);
      });
      const twice = Object.keys(byText).filter((t) => byText[t].size > 1);
      check("no two sidebar links share a name and go to different pages", twice.length === 0, twice.join(", "));
      check("every section has a heading and its sources",
        [...D.querySelectorAll(".guide-section")].every((s) =>
          s.querySelector("h2.guide-heading") && s.querySelector(".guide-sources a[href^='https://']")));
      check("every link out opens safely", [...D.querySelectorAll('a[target="_blank"]')]
        .every((a) => /noopener/.test(a.getAttribute("rel") || "")));
      check("the sidebar marks this page in the guide",
        D.querySelector('.nav-sub[aria-current="page"]').getAttribute("href") === `${slug}.html`);
      check("the Views list leads to the guide",
        !!D.querySelector('.nav-link[href="../government/index.html"]'));
      check("only a page that names members loads the build's figures, and only it shows Congress's balance",
        people === !!D.getElementById("senateBalance"));
      // Its members are written into it by the build (rule 94): the page
      // loads no profile data, neither the index of everyone nor a state's.
      check("no guide page loads profile data",
        !sources.some((src) => /data\/(profiles|people\/(?!meta)[a-z]+)\.js/.test(src)),
        sources.filter((src) => /data\/people|profiles/.test(src)).join(", "));
      if (!people) {
        const jump = D.getElementById("stateJump");
        check("the jump list is written into the page, and wired",
          jump.options.length > 50 && jump.getAttribute("data-wired") === "true",
          `${jump.options.length}`);
      }
      check("a table becomes cards on a phone: every cell says its column",
        [...D.querySelectorAll(".guide-table td")].every((td) => td.getAttribute("data-label")));
    });

    if (slug !== "congress") continue;

    // Written into the page by the build (kyc/pages.py leaders_html,
    // committees_html): checked against every state's people file, since the
    // page itself holds no profiles (rule 94).
    const all = everyone();
    const linked = (a) => all.get(profileHref(a));
    suite(`${page} — who leads each chamber, from the data`, () => {
      const leaders = D.querySelector('.guide-built[data-built-from="leaders-house"]');
      const speaker = [...all.values()].find((p) => KYC.seated(p) &&
        (p.leadership || []).includes("Speaker of the House"));
      const firstHouse = leaders && leaders.querySelector(".guide-person");
      check("the House's leaders are named from the data, the Speaker first",
        !!leaders && (!speaker || (firstHouse && profileHref(firstHouse) === speaker.id &&
          /Speaker of the House/.test(firstHouse.textContent))),
        leaders ? leaders.textContent.slice(0, 120) : "no block");
      const houseTitles = leaders ? [...leaders.querySelectorAll(".guide-person")].map((b) => b.textContent) : [];
      const lead = houseTitles.findIndex((t) => /(^|\s)House Minority Leader$/.test(t.trim()) && !/Assistant/.test(t));
      const assistant = houseTitles.findIndex((t) => /Assistant House Minority Leader/.test(t));
      check("the Minority Leader comes before the Assistant Minority Leader",
        lead === -1 || assistant === -1 || lead < assistant, `${lead} ${assistant}`);
      const senateLeads = [...D.querySelectorAll('.guide-built[data-built-from="leaders-senate"] .guide-person')];
      check("every name in the Senate's list is a sitting senator holding that post",
        senateLeads.every((b) => {
          const p = linked(b);
          return p && KYC.seated(p) && /Senate/.test(p.chamber || "") &&
            (p.leadership || []).some((t) => b.textContent.includes(t));
        }), `${senateLeads.length} senators`);
      // A new Congress's posts reach the record days after it sits; until
      // then nobody is shown holding one, and the list says so rather than
      // naming the last Congress's leaders (legislators.held_posts).
      for (const ch of ["house", "senate"]) {
        const box = D.querySelector(`.guide-built[data-built-from="leaders-${ch}"]`);
        const any = [...all.values()].some((p) => KYC.seated(p) &&
          (ch === "senate") === /Senate/.test(p.chamber || "") && (p.leadership || []).length);
        check(`the ${ch === "senate" ? "Senate" : "House"} list names its leaders, or says this Congress's are not recorded yet`,
          !!box && (any ? box.querySelectorAll(".guide-person").length > 0
            : /lists nobody in a \w+ leadership post for the \d+(st|nd|rd|th) Congress yet/.test(box.textContent)),
          box ? box.textContent.slice(0, 160) : "no block");
      }
      check("no block is left to fill on the page", !D.querySelector(
        '.guide-live[data-live="committees"], .guide-live[data-live^="leaders-"]'));
    });

    suite(`${page} — who leads each committee, from the data`, () => {
      const live = D.querySelector('.guide-built[data-built-from="committees"]');
      const table = KYC.meta().committees || {};
      // What the page should list, worked out here from the profiles.
      const expected = new Set();
      all.forEach((p) => {
        if (p.isCandidate) return;
        (p.committeeList || []).forEach((seat) => {
          if (seat.title && table[seat.code] && !table[seat.code].parent) expected.add(seat.code);
        });
      });
      const rows = live ? [...live.querySelectorAll("tbody tr")] : [];
      if (!expected.size && [...all.values()].some((p) => p.committeesPending)) {
        // A new Congress before its rosters are published.
        check("says the new Congress's committees are not published yet",
          !!live && /have not been published yet/.test(live.textContent), live && live.textContent);
        return;
      }
      check("a row for every full committee with a titled seat", rows.length === expected.size,
        `${rows.length} rows, ${expected.size} committees`);
      check("House, Senate and joint committees each have a table",
        !!live && live.querySelectorAll("table").length >= 3);
      if (!live) return;
      // The Senate's narcotics caucus is not a Senate committee, and its
      // minority lead is its Co-Chair, not a second Chairman.
      const caucus = rows.find((r) => /Caucus on International Narcotics Control/.test(r.textContent));
      if (caucus) {
        let head = caucus.closest(".guide-table-wrap").previousElementSibling;
        while (head && head.tagName !== "H3") head = head.previousElementSibling;
        check("a caucus is listed apart from the committees",
          /Caucuses and commissions/.test(head ? head.textContent : ""), head && head.textContent);
        const lead = caucus.querySelector('td[data-label="Minority lead"]').textContent;
        check("the caucus's minority lead is its Co-Chair, as the caucus styles it",
          /Co-Chair/.test(lead) && !/Chairman/.test(lead), lead);
      }
      const people = [...live.querySelectorAll(".guide-person")];
      check("every name is a sitting member who holds a titled seat on that committee",
        people.length > 80 && people.every((b) => {
          const p = linked(b);
          const name = b.closest("tr").querySelector("th").textContent.trim();
          const code = Object.keys(table).find((c) => table[c].name === name);
          return p && !p.isCandidate &&
            (p.committeeList || []).some((s) => s.code === code && s.title);
        }), `${people.length} names`);
      check("a chair is on the majority's side and a minority lead on the minority's",
        people.every((b) => {
          const p = linked(b);
          const name = b.closest("tr").querySelector("th").textContent.trim();
          const code = Object.keys(table).find((c) => table[c].name === name);
          const seat = p.committeeList.find((s) => s.code === code);
          const minority = b.closest("td").getAttribute("data-label") === "Minority lead";
          return (seat.side === "minority") === minority;
        }));
      check("Senate Intelligence's minority lead is its vice chairman", (() => {
        const row = rows.find((r) => /Senate Select Committee on Intelligence/.test(r.textContent));
        if (!row) return true;     // not in this Congress's rosters
        const lead = row.querySelector('td[data-label="Minority lead"]');
        return /Vice Chairman/.test(lead.textContent) && !/Ex Officio/.test(row.textContent);
      })());
      check("names are escaped text, not markup", !/<script/i.test(live.innerHTML));
      // A joint committee's roster may title only majority members: the
      // cell says what the rosters name, never "None recorded".
      const unnamedCells = [...live.querySelectorAll('td[data-label="Minority lead"] .lead-unnamed')];
      check("a lead the rosters do not name is said to be not named, not 'none recorded'",
        !/None recorded/.test(live.textContent) && unnamedCells.every((s) =>
          s.textContent === "No minority lead named in the rosters"), live.textContent.slice(0, 200));
      check("each table counts its committees with no minority lead named",
        [...live.querySelectorAll("table")].every((t) => {
          const n = t.querySelectorAll('td[data-label="Minority lead"] .lead-unnamed').length;
          const note = t.closest(".guide-table-wrap").previousElementSibling;
          const has = !!note && note.classList.contains("committees-unnamed");
          return n ? has && /no member of the minority a leading title/.test(note.textContent) : !has;
        }));
      check("each name is a link to that member's profile on the grid",
        people.every((b) => b.tagName === "A" &&
          /^\.\.\/index\.html#\/profile\//.test(b.getAttribute("href")) && !!linked(b)));
    });
  }

  await testGuideMaps();

  suite("guide — reachable from every kind of page", () => {
    for (const page of ["index.html", "map.html", "states/tx.html", "districts/ca.html"]) {
      const raw = fs.readFileSync(path.join(SITE, page), "utf8");
      const prefix = page.includes("/") ? "../" : "";
      check(`${page} links to the guide`, raw.includes(`href="${prefix}government/index.html"`));
    }
    // Every district page's "States & territories" pointed at a
    // districts/index.html that never existed. It exists now, as the
    // district maps' directory, and each district page links it by name.
    const district = fs.readFileSync(path.join(SITE, "districts/ca.html"), "utf8");
    check("a district page's states link reaches the states index",
      district.includes('href="../states/index.html"') &&
        (!/href="index\.html"/.test(district) || fs.existsSync(path.join(SITE, "districts/index.html"))));
  });
}

/* The guide's maps: the views in kyc/government_maps.py, drawn by the shared
 * map (kyc-usmap.js) the partisan map uses. */
async function testGuideMaps() {
  const pages = (() => {
    const text = fs.readFileSync(path.join(SITE, "data", "government.js"), "utf8");
    const json = text.slice(text.indexOf("window.kycGovernment = ") + 23, text.indexOf(";\nwindow.kycGovernmentMeta"));
    return JSON.parse(json).pages;
  })();

  for (const slug of Object.keys(pages)) {
    const page = `government/${slug}.html`;
    const { window, D, errors } = await buildPage(page);
    const KYC = window.KYC;
    const data = window.kycGovernment;
    const ids = pages[slug];
    suite(`${page} — the map`, () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const shapes = [...D.querySelectorAll("#usMap .state")];
      check("every state, D.C. and territory is a shape", shapes.length >= 56, `${shapes.length}`);
      check("no text is drawn inside the map's SVG (rule 46)", !D.querySelector("#usMap text"));
      check("every fill is a theme colour, never a literal",
        shapes.every((s) => /^var\(--/.test(s.style.fill)), shapes.map((s) => s.style.fill).find((f) => !/^var/.test(f)));
      check("every state names its value to a screen reader",
        shapes.every((s) => (s.getAttribute("aria-label") || "").includes(":")));
      check("the legend shows the first view",
        D.querySelectorAll("#mapLegend .key").length >= 2);
      check("one explanation shows, for the first view",
        [...D.querySelectorAll(".guide-about")].filter((s) => !s.hidden).map((s) => s.getAttribute("data-mode"))
          .join() === ids[0]);
      if (ids.length > 1) {
        check("a button for every view", D.querySelectorAll(".segmented [data-mode]").length === ids.length);
      }

      // Pick a state with a click, as a reader would.
      const tx = D.querySelector('#usMap .state[data-state="TX"]');
      tx.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
      check("picking a state names it in the panel", D.getElementById("panelState").textContent === "Texas");
      check("the panel lists every view's fact about it, with sources",
        D.querySelectorAll("#guideFacts .guide-fact").length === ids.length &&
        [...D.querySelectorAll("#guideFacts .guide-fact")].every((f) => f.querySelector(".guide-sources a[href^='https://']")));
      check("the current view's fact comes first",
        D.querySelector("#guideFacts .guide-fact").classList.contains("is-current"));
      check("the pick is in the address, so the view can be shared",
        /state=TX/.test(window.location.hash), window.location.hash);
      check("the panel links to the state's page",
        /states\/tx\.html$/.test(D.getElementById("panelStateLink").getAttribute("href")));
      check("the facts are text, not markup from the data", !/<script/i.test(D.getElementById("guideFacts").innerHTML));

      // The jump list picks on the map instead of leaving the page.
      const jump = D.getElementById("stateJump");
      jump.value = "CA";
      jump.dispatchEvent(new window.Event("change"));
      check("the jump list picks the state on this map",
        D.getElementById("panelState").textContent === "California" &&
        D.querySelector('#usMap .state[data-state="CA"]').getAttribute("aria-pressed") === "true");

      if (ids.length > 1) {
        const last = ids[ids.length - 1];
        D.querySelector(`.segmented [data-mode="${last}"]`).click();
        check("switching view shows its explanation and legend",
          !D.querySelector(`.guide-about[data-mode="${last}"]`).hidden &&
          D.querySelector(`.guide-about[data-mode="${ids[0]}"]`).hidden);
        check("switching view is in the address", window.location.hash.includes(`mode=${last}`),
          window.location.hash);
        check("the picked state's current fact follows the view",
          D.querySelector("#guideFacts .guide-fact.is-current .guide-fact-title").textContent
            .indexOf(data.modes[last].label) === 0);
      }
      // A faint fill writes its callout in the theme's text colour.
      const faint = [...D.querySelectorAll("#mapLabels .map-callout")]
        .filter((c) => /scale-[123]|none-fill|surface-2/.test(c.style.background));
      check("callouts on faint fills use the light ink", faint.every((c) => c.style.color === "var(--text)"),
        `${faint.length} faint callouts`);
      // A category's callout writes in the ink kyc.css names for it, the
      // colour that reads on it in each theme.
      const cats = [...D.querySelectorAll("#mapLabels .map-callout")]
        .filter((c) => /var\(--cat-[1-4]\)/.test(c.style.background));
      check("a category's callout uses its own ink", cats.every((c) =>
        c.style.color === "var(--" + c.style.background.match(/cat-[1-4]/)[0] + "-ink)"),
        cats.filter((c) => !/-ink/.test(c.style.color)).map((c) => c.textContent).join(", "));
    });
  }

  // Deep links land on the view and state they name.
  {
    const { window, D } = await buildPage("government/states.html", { hash: "#/?mode=veto&state=IN" });
    suite("government/states.html — a shared view opens as sent", () => {
      check("the veto view is pressed",
        D.querySelector('.segmented [data-mode="veto"]').getAttribute("aria-pressed") === "true");
      check("Indiana is picked, and its fact says it has no line-item veto",
        D.getElementById("panelState").textContent === "Indiana" &&
        /cannot veto single items/.test(D.querySelector("#guideFacts .guide-fact.is-current").textContent));
    });
  }
  {
    const { D } = await buildPage("government/states.html", { hash: "#/?mode=legislature&state=VA" });
    suite("government/states.html — a legislature's link reads as its page does", () => {
      const link = D.querySelector('#guideFacts a[href$="legislature/va.html"]');
      check("Virginia's link says General Assembly, the name on the page it opens",
        !!link && /Virginia General Assembly/.test(link.textContent) && !/Virginia Legislature/.test(link.textContent),
        link && link.textContent);
    });
  }
  {
    const { D } = await buildPage("government/courts.html", { hash: "#/?state=TX" });
    suite("government/courts.html — circuits are numbered", () => {
      const labels = Object.fromEntries([...D.querySelectorAll("#mapLabels .state-code")]
        .map((s) => [s.textContent, true]));
      check("states carry their circuit's number, not their code", labels["5"] && labels["9"] && !labels.TX);
      check("the legend keys each circuit by its number",
        [...D.querySelectorAll("#mapLegend .swatch-label")].map((s) => s.textContent).includes("11"));
      check("Texas is in the Fifth Circuit, with a link to that court",
        /Fifth Circuit/.test(D.getElementById("guideFacts").textContent) &&
        !!D.querySelector('#guideFacts a[href="https://www.ca5.uscourts.gov/"]'));
      // The guide's map and the federal page are one set of courts.
      const here = [...D.querySelectorAll("#guideFacts .guide-fact-courts a")].map((a) => a.getAttribute("href"));
      // Exactly these: a court from another state, or a nationwide one, would pass a superset check.
      check("Texas's own federal courts link to their judges: its court of appeals first",
        here[0] === "../courts/ca5.html" && here.length === 5 &&
        here.slice(1).sort().join(" ") === ["tx-e", "tx-n", "tx-s", "tx-w"]
          .map((id) => "../courts/" + id + ".html").join(" "), here.join(" "));
    });
  }
  {
    // A state's fact cites only the general sources and its own: Oklahoma's
    // "Choosing judges" cited New Jersey's courts and a Utah bill.
    const { D } = await buildPage("government/states.html", { hash: "#/?mode=judges&state=OK" });
    suite("government/states.html — a fact cites its own state's sources", () => {
      const facts = D.getElementById("guideFacts").textContent;
      check("Oklahoma's facts cite neither New Jersey's court nor Utah's bill nor Arizona's amendment",
        !/New Jersey Courts|Utah S\.B\. 134|Arizona Legislature|Nebraska Legislature/.test(facts),
        facts.slice(0, 300));
      check("and still cite the general sources", /Book of the States/.test(facts));
      const first = D.querySelector("details.guide-more-section");
      check("the page's first section is open, its title a heading",
        first.open && !!first.querySelector("summary > h3"));
    });
  }
  {
    const { D } = await buildPage("government/states.html", { hash: "#/?mode=ballot&state=TX" });
    suite("government/states.html — the 2026 ballot, state by state", () => {
      const fact = D.querySelector("#guideFacts .guide-fact.is-current");
      check("Texas's 2026 ballot names its offices and seats",
        /governor/.test(fact.textContent) && /16 of the 31 seats in the Senate/.test(fact.textContent),
        fact.textContent.slice(0, 200));
      check("citing Texas's own record, not another state's",
        /Texas's own record/.test(fact.textContent) && !/Alabama's own record/.test(fact.textContent));
    });
  }
  {
    const { D } = await buildPage("government/tribal.html", { hash: "#/?state=OK" });
    suite("government/tribal.html — state jurisdiction since 2022", () => {
      const fact = D.querySelector("#guideFacts .guide-fact.is-current").textContent;
      check("Oklahoma's fact names Castro-Huerta and McGirt, and cites both",
        /Castro-Huerta/.test(fact) && /McGirt v\. Oklahoma/.test(fact) &&
        /591 U\.S\. 894/.test(fact) && /597 U\.S\. 629/.test(fact), fact.slice(0, 300));
    });
  }
  {
    // Which nations have their office in a state, and who leads each, as
    // the BIA's directory lists them (GUIDE-18).
    const { window, D } = await buildPage("government/tribal.html", { hash: "#/?mode=tribes&state=ME" });
    suite("government/tribal.html — tribal governments and their leaders", () => {
      const mode = window.kycGovernment.modes.tribes;
      const rows = mode.lists.ME;
      const fact = D.querySelector("#guideFacts .guide-fact.is-current");
      const items = [...fact.querySelectorAll(".guide-fact-list > li")];
      check("every government the directory places in Maine is listed under the fact",
        rows.length > 0 && items.length === rows.length, `${items.length} of ${rows.length}`);
      check("each with the leader and title the directory gives, or says it gives none",
        items.every((li, i) => rows[i][1] ? li.textContent.includes(rows[i][1])
          : /no leader listed/.test(li.textContent)));
      const nested = rows.filter((r) => r[3].length);
      check("a band the directory lists under its tribe is named with it",
        nested.every((r) => items.some((li) => li.firstChild.textContent.trim() === r[0] &&
          li.querySelectorAll("ul > li").length === r[3].length)), nested.length);
      check("the fact cites the directory", /Tribal Leaders Directory/.test(fact.textContent));
      const other = D.querySelector('#guideFacts .guide-fact:not(.is-current) .guide-fact-list');
      check("another view's fact carries no list", !other);
    });
  }
  {
    const { window, D } = await buildPage("government/tribal.html", { hash: "#/?mode=tribes&state=AK" });
    suite("government/tribal.html — a long list opens on request", () => {
      // Alaska's 229 governments were 10,000px on a phone before anything
      // else on the panel.
      const rows = window.kycGovernment.modes.tribes.lists.AK;
      const fact = D.querySelector("#guideFacts .guide-fact.is-current");
      const shown = fact.querySelectorAll(":scope > .guide-fact-list > li");
      const more = fact.querySelector("details.guide-fact-more");
      check("the first rows are shown and the rest fold under one control",
        rows.length > 30 && shown.length === 20 && !!more && !more.open &&
          more.querySelectorAll(":scope > .guide-fact-list > li").length === rows.length - 20 &&
          new RegExp(`Show the other ${rows.length - 20} of ${rows.length}`).test(more.querySelector("summary").textContent),
        `${shown.length} shown of ${rows.length}`);
    });
  }
  {
    const { window, D } = await buildPage("government/tribal.html", { hash: "#/?mode=tribes&state=OK" });
    suite("government/tribal.html — the directory's marks are not shown as names", () => {
      const fact = D.querySelector("#guideFacts .guide-fact.is-current");
      const disputed = window.kycGovernment.modes.tribes.lists.OK.filter((r) => r[4]);
      check("no asterisk or dispute note inside a leader's name or title",
        !/\*/.test(fact.textContent) && !/Subject to Tribal Leadership Dispute/.test(fact.textContent),
        fact.textContent.slice(0, 200));
      check("a disputed leadership says so in words",
        disputed.length > 0 && fact.querySelectorAll(".badge").length >= disputed.length &&
          /leadership disputed/.test(fact.textContent), disputed.length);
    });
  }
  {
    const { D } = await buildPage("government/states.html", { hash: "#/?mode=ballot" });
    suite("government/states.html — the ballot view's sources are each state's own", () => {
      const about = D.querySelector('.guide-about[data-mode="ballot"] .guide-sources');
      check("with no state picked, the panel does not cite every state's records",
        !!about && !about.querySelector("a") && /cited on that state/.test(about.textContent),
        about && about.textContent.slice(0, 160));
    });
  }
  {
    const { window, D } = await buildPage("government/elections.html", {
      setup: (w) => w.localStorage.setItem("kycState", "TX") });
    const K = window.KYC;
    suite("government/elections.html — the reader's voting pages, and the count's timeline", () => {
      const link = D.querySelector("a[data-voting-link]");
      check("the voting link opens the remembered state's voting section",
        /states\/tx\.html#voting$/.test(link.getAttribute("href")), link.getAttribute("href"));
      check("the picker starts on the remembered state", D.getElementById("votingState").value === "TX");
      check("the jump list opens a state's voting section",
        D.getElementById("stateJump").getAttribute("data-jump-to") === "states/{code}.html#voting");
      const chip = (key) => D.querySelector(`.guide-status[data-status="${key}"]`).textContent;
      check("each step's status words are the site's own (KYC.raceStatus)",
        chip("elected") === K.raceStatus("elected", "card").label &&
        chip("defeated") === K.raceStatus("defeated", "card").label &&
        chip("runoff") === K.raceStatus("runoff", "card").label &&
        chip("awaiting") === K.raceStatus("nominee", "card",
          { now: new window.Date(Date.UTC(2026, 10, 5, 12)) }).label &&
        chip("awaiting") !== chip("nominee"), chip("awaiting"));
      check("on the campaign clock Election Day is next and nothing is past",
        D.querySelector(".guide-timeline-steps li.is-next").getAttribute("data-date") === "2026-11-03" &&
        !D.querySelector(".guide-timeline-steps li.is-past"));
      K.guide.initTimeline(new window.Date(Date.UTC(2026, 11, 5, 12)));
      check("in December the steps passed are marked done and the next is Texas's canvass",
        D.querySelector(".guide-timeline-steps li.is-next").getAttribute("data-date") === "2026-12-07" &&
        D.querySelectorAll(".guide-timeline-steps li.is-past").length === 5);
      // The highlighted step read as "today": each mark is a word, and the
      // caption says what the words mean.
      const tags = [...D.querySelectorAll(".guide-timeline-steps .guide-timeline-tag")];
      const next = D.querySelector(".guide-timeline-steps li.is-next .guide-timeline-tag");
      check("the next step says Next and each past step says Done, in words",
        !!next && next.textContent === "Next" &&
          tags.filter((t) => t.textContent === "Next").length === 1 &&
          [...D.querySelectorAll(".guide-timeline-steps li.is-past")].every((li) =>
            (li.querySelector(".guide-timeline-tag") || {}).textContent === "Done"),
        tags.map((t) => t.textContent).join(","));
      check("the caption says what Done and Next mean",
        /marked Done/.test(D.querySelector(".guide-timeline figcaption").textContent) &&
          /marked Next/.test(D.querySelector(".guide-timeline figcaption").textContent));
      K.guide.initTimeline(new window.Date(Date.UTC(2026, 11, 6, 12)));
      check("a second marking replaces the words, never adds to them",
        [...D.querySelectorAll(".guide-timeline-steps li")].every((li) =>
          li.querySelectorAll(".guide-timeline-tag").length <= 1));
    });
  }
  {
    const { D } = await buildPage("government/local.html", { hash: "#/?mode=local-county&state=CT" });
    suite("government/local.html — none is not zero", () => {
      check("Connecticut has no county governments, said in words",
        /has no county governments: it abolished them in 1960/.test(
          D.querySelector("#guideFacts .guide-fact.is-current").textContent));
    });
  }
}

/* ======================================================= legislatures */

/* A state's legislature: Census districts, Open States members, drawn by
 * the shared region map (kyc-regionmap.js). */
async function testLegislatures() {
  const pick = (D, window, id) => {
    const shape = D.querySelector(`#legMap .district-statewide [data-region="${id}"]`);
    shape.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  };
  /* STATEGOV-13, the photo research of 2026-10-19: 132 of Montana's 150
   * legislators had no portrait from Open States; the Legislature's own
   * roster has one for each. A photograph from a legislature's own record
   * is credited to it, linked to the page it was read from (rule 87). */
  {
    const { window, D, errors } = await buildPage("legislature/mt.html");
    const state = window.kycLegislature.MT;
    suite("legislature/mt.html — the legislature's own photographs, credited", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const everyone = [].concat(...Object.values(state.chambers.upper.members), state.unplaced);
      const credited = everyone.filter((p) => p.imageCredit && p.imageCredit.by);
      check("every credited photograph is the legislature's, from its own host",
        credited.every((p) => /^https:\/\/(www\.)?legmt\.gov\//.test(p.image) &&
          p.imageCredit.by === "Montana Legislature" && /legmt\.gov/.test(p.imageCredit.page)),
        credited.filter((p) => !/legmt\.gov/.test(p.image)).map((p) => p.name).join(", "));
      const p = credited[0];
      if (p) {
        const id = Object.keys(state.chambers.upper.members).find((k) =>
          state.chambers.upper.members[k].includes(p));
        pick(D, window, id);
        const card = [...D.querySelectorAll("#legPanelBody .leg-person")].find((el) =>
          el.textContent.includes(p.name));
        const credit = card && card.querySelector(".leg-credit");
        check("the card says whose photograph it is, linked to its page",
          !!credit && credit.textContent === "Photo: Montana Legislature" &&
          credit.querySelector("a").getAttribute("href") === p.imageCredit.page,
          credit ? credit.innerHTML : "no credit line");
        check("the photograph is the one the credit names", card.querySelector(".leg-photo").getAttribute("src") === p.image);
        // A photograph that does not load takes its credit with it (the
        // reviewers of PR #125): a card never credits what it does not show.
        card.querySelector(".leg-photo").dispatchEvent(new window.Event("error"));
        check("a portrait that fails to load takes its credit with it",
          !card.querySelector(".leg-photo") && !card.querySelector(".leg-credit"));
      }
      /* An Open States portrait the legislature's own host serves is
       * credited to it as well: Vermont's two-member districts showed one
       * credited and one not, from the same folder. */
      const hosted = everyone.filter((p) => p.image && /^https:\/\/([a-z0-9-]+\.)*legmt\.gov\//.test(p.image));
      check("every portrait served by the legislature is credited to it",
        hosted.every((p) => p.imageCredit && p.imageCredit.by === "Montana Legislature"),
        hosted.filter((p) => !p.imageCredit).map((p) => p.name).join(", "));
      /* Any other Open States portrait says where Open States found it,
       * never "Photo: <host>" as though the host were whose it is (the
       * reviewers of PR #137: a news site, an image CDN). */
      const listed = everyone.filter((p) => p.image && !(p.imageCredit && p.imageCredit.by));
      check("every other portrait is said to be where Open States found it",
        listed.every((p) => p.imageCredit && p.imageCredit.listedBy === "Open States" &&
          p.imageCredit.host === new URL(p.image).hostname),
        listed.filter((p) => !p.imageCredit).map((p) => p.name).join(", "));
      const plain = listed.find((p) => Object.keys(state.chambers.upper.members).some((k) =>
        state.chambers.upper.members[k].includes(p)));
      if (plain) {
        const id = Object.keys(state.chambers.upper.members).find((k) =>
          state.chambers.upper.members[k].includes(plain));
        pick(D, window, id);
        const card = [...D.querySelectorAll("#legPanelBody .leg-person")].find((el) =>
          el.textContent.includes(plain.name));
        const line = card && card.querySelector(".leg-credit");
        check("such a card says where the file is and who listed it, and credits no one",
          !!line && line.textContent === "Photo: from " + plain.imageCredit.host +
            ", as listed by Open States" && !line.querySelector("a"), line && line.textContent);
      }
    });
  }
  /* A party caucus's photograph of its own member is credited to the
   * caucus by the name its own site gives itself (the owner, 2026-10-25:
   * "we can credit caucus"); another party's caucus is never named. */
  {
    const { window, D, errors } = await buildPage("legislature/mi.html");
    const state = window.kycLegislature.MI;
    suite("legislature/mi.html — a caucus's photograph of its own member, credited to it", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const everyone = [].concat(...Object.values(state.chambers.upper.members),
        ...Object.values(state.chambers.lower.members), state.unplaced || []);
      const caucus = everyone.filter((p) => p.imageCredit && p.imageCredit.caucus);
      check("Michigan's caucus photographs are credited to their caucuses", caucus.length > 0);
      check("each caucus credited is the member's own party's",
        caucus.every((p) => (p.partyKey === "D" ? /Democrat/ : /Republican/).test(p.imageCredit.by)),
        caucus.filter((p) => !/Democrat|Republican/.test(p.imageCredit.by)).map((p) => p.name).join(", "));
      const mccann = everyone.find((p) => p.name === "Sean McCann");
      check("Sean McCann's card shows the Michigan Senate Democrats' photograph of him",
        !!mccann && /^https:\/\/senatedems\.com\/mccann\//.test(mccann.image) &&
        mccann.imageCredit.by === "Michigan Senate Democrats", mccann && mccann.image);
      if (mccann) {
        const id = Object.keys(state.chambers.upper.members).find((k) =>
          state.chambers.upper.members[k].includes(mccann));
        pick(D, window, id);
        const card = [...D.querySelectorAll("#legPanelBody .leg-person")].find((el) =>
          el.textContent.includes(mccann.name));
        const line = card && card.querySelector(".leg-credit");
        check("the card names the caucus, linked to his page on its site",
          !!line && /^Photo: Michigan Senate Democrats/.test(line.textContent) &&
          !/as listed by Open States/.test(line.textContent) &&
          line.querySelector("a").getAttribute("href") === mccann.imageCredit.page,
          line && line.innerHTML);
      }
    });
  }
  {
    const { window, D, errors, sources } = await buildPage("legislature/tx.html");
    const state = window.kycLegislature.TX;
    suite("legislature/tx.html — the Senate and House on a map", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      check("its data loads before the map and the page", sources.indexOf("../data/legislature/tx.js") <
        sources.indexOf("../assets/kyc-regionmap.js") &&
        sources.indexOf("../assets/kyc-regionmap.js") < sources.indexOf("../assets/kyc-legislature.js"));
      const shapes = D.querySelectorAll("#legMap .district-statewide .region-shape");
      check("the Senate is drawn first, a shape per district",
        shapes.length === Object.keys(state.chambers.upper.districts).length, `${shapes.length}`);
      check("no text is drawn inside the map's SVG (rule 46)", !D.querySelector("#legMap svg text"));
      check("every district is in a party's colour or none",
        [...shapes].every((s) => /party-(d|r|i|split|none)/.test(s.getAttribute("class"))));
      check("the panel opens on the chamber", /Texas Senate/.test(D.getElementById("legPanelTitle").textContent));
      D.querySelector('.segmented [data-chamber="lower"]').click();
      check("the House has its own map", D.querySelectorAll("#legMap .district-statewide .region-shape").length ===
        Object.keys(state.chambers.lower.districts).length);
      check("the chamber is in the address", /chamber=lower/.test(window.location.hash), window.location.hash);
      const id = Object.keys(state.chambers.lower.members)[0];
      pick(D, window, id);
      const people = state.chambers.lower.members[id];
      check("picking a district names its members, from the data",
        people.every((p) => D.getElementById("legPanelBody").textContent.includes(p.name)));
      check("the pick is in the address", window.location.hash.includes("d=" + id), window.location.hash);
      check("every district is listed below, as buttons",
        D.querySelectorAll("#legRoster .leg-row").length === Object.keys(state.chambers.lower.districts).length);
      check("member text is escaped, never markup", !/<script/i.test(D.getElementById("legPanelBody").innerHTML));
      const img = D.querySelector("#legPanelBody .leg-photo");
      if (img) {
        img.dispatchEvent(new window.Event("error"));
        check("a portrait that fails to load steps aside", !D.querySelector("#legPanelBody .leg-photo"));
      }
      check("the page links to the state page and its congressional map",
        !!D.querySelector('a[href="../states/tx.html"]') && !!D.querySelector('a[href="../districts/tx.html"]'));
      check("the jump list goes to another state's legislature",
        D.getElementById("stateJump").getAttribute("data-jump-to") === "legislature/{code}.html");
    });
    /* Audit 2026-10-17: the cards dumped every page Open States read (up
     * to eighteen raw URLs), dropped the district office's phone, and the
     * map alone made a chamber look like its rural party's. */
    suite("legislature/tx.html — a card, the seats and the ballot", () => {
      const everyone = [].concat(...Object.values(state.chambers.lower.members), state.unplaced);
      const withPage = everyone.find((p) => p.page);
      const withPhone = everyone.find((p) => p.districtPhone);
      const card = (p) => {
        const id = Object.keys(state.chambers.lower.members).find((k) =>
          state.chambers.lower.members[k].includes(p));
        pick(D, window, id);
        return D.getElementById("legPanelBody");
      };
      check("no member carries the source's raw link list", everyone.every((p) => !p.links && !p.social));
      if (withPage) {
        const body = card(withPage);
        const links = [...body.querySelectorAll(".leg-person .leg-page a[href^='http']")];
        check("a card links one official page, labelled, never a raw address",
          links.length === body.querySelectorAll(".leg-person").length &&
          links.every((a) => a.textContent === "Official page"), links.map((a) => a.textContent).join(" | "));
      }
      if (withPhone) {
        const body = card(withPhone);
        check("the district office's phone is shown, labelled",
          body.textContent.includes("District office: " + withPhone.districtPhone) &&
          !!body.querySelector('a[href^="tel:"]'));
      }
      D.querySelector('.segmented [data-chamber="upper"]').click();
      const c = state.chambers.upper;
      const strip = D.querySelector("#legSeats .seat-strip");
      check("a strip of one square per seat sits above the map",
        !!strip && strip.querySelectorAll(".seat").length === c.seats &&
        D.getElementById("legSeats").compareDocumentPosition(D.getElementById("legMap")) &
          window.Node.DOCUMENT_POSITION_FOLLOWING);
      check("its squares are the chamber's own count, nobody listed outlined (rule 51)",
        strip.querySelectorAll(".seat-r").length === c.count.R &&
        strip.querySelectorAll(".seat-d").length === c.count.D &&
        strip.querySelectorAll(".seat-none").length === c.seats - c.listed);
      check("and it says what it shows to a screen reader",
        strip.getAttribute("role") === "img" && /seats, one square each/.test(strip.getAttribute("aria-label")));
      const holds = D.querySelector("#legPanelBody .leg-holds");
      check("the summary says who holds a majority, as the state page does",
        !!holds && holds.textContent.startsWith(c.count.majority === "R" ? "Republican majority"
          : c.count.majority === "D" ? "Democratic majority" : "No party holds"), holds && holds.textContent);
      const ballot = D.querySelector("#legPanelBody .leg-ballot");
      check("and which seats are on the Nov 3 ballot, from the state's record",
        !!ballot && ballot.textContent.includes(`${c.ballot.up} of the ${c.ballot.seats} seats`) &&
        !!ballot.querySelector(`a[href="${c.ballot.source}"]`), ballot && ballot.textContent);
      // PR #96 review: "The state's record: all." and a special-election
      // sentence on every chamber said nothing the count did not.
      check("the record is quoted only where it says more than the count",
        !/The state's record: (all|none)\b/i.test(ballot.textContent) &&
        !/A special election to fill an unexpired term is not counted/.test(ballot.textContent),
        ballot.textContent);
      const up = Object.keys(c.districts).find((id) => c.districts[id].up === true);
      const off = Object.keys(c.districts).find((id) => c.districts[id].up === false);
      if (up && off) {
        pick(D, window, up);
        const yes = D.querySelector("#legPanelBody .leg-ballot").textContent;
        pick(D, window, off);
        const no = D.querySelector("#legPanelBody .leg-ballot").textContent;
        check("a district says whether its own seat is up",
          /This seat (is|was) on the Nov 3, 2026 ballot/.test(yes) && /not up for regular election/.test(no),
          yes + " / " + no);
      }
    });
  }
  {
    const { window, D, errors } = await buildPage("legislature/ne.html");
    suite("legislature/ne.html — one chamber", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      check("no chamber switch for a one-chamber legislature", !D.querySelector("[data-chamber]"));
      check("all 49 districts drawn", D.querySelectorAll("#legMap .district-statewide .region-shape").length === 49);
      // Audit 2026-10-17, STATEGOV-06: one dark fill under a party legend
      // that did not apply, with "nobody listed" folded into "nonpartisan".
      const shown = [...D.querySelectorAll(".party-legend [data-key]")].filter((k) => !k.hidden)
        .map((k) => k.getAttribute("data-key"));
      const members = window.kycLegislature.NE.chambers.upper.members;
      const empty = Object.keys(window.kycLegislature.NE.chambers.upper.districts).some((id) => !members[id]);
      check("the legend names only what the map draws: nonpartisan, and nobody listed where there is one",
        shown[0] === "n" && shown.length === (empty ? 2 : 1) && !shown.includes("r"), shown.join(","));
      check("a nonpartisan district is not drawn as a seat with nobody listed",
        [...D.querySelectorAll("#legMap .district-statewide .region-shape")].every((s, i) =>
          /party-(n|none)\b/.test(s.getAttribute("class"))) &&
        !!D.querySelector("#legMap .region-shape.party-n"));
      check("the summary says the Legislature is elected without party labels",
        /Elected without party labels/.test(D.getElementById("legPanelBody").textContent));
      const summary = D.getElementById("legPanelBody").textContent;
      check("its seats are counted as nonpartisan, not under a party's name",
        /\d+ seats: \d+ nonpartisan/.test(summary), summary.slice(0, 80));
      // STATEGOV-18: the term, only where the state's own record states it.
      const c = window.kycLegislature.NE.chambers.upper;
      check("the term is said where the state's record states it",
        !c.termYears || summary.includes("Members serve " + c.termYears + "-year terms"), summary);
    });
  }
  {
    // PR #140 review: Nevada's Senate record, "11 districts: 2, 8, 9, ...",
    // read "The state's record: : 2, 8, 9" once its count was dropped.
    const { D, errors } = await buildPage("legislature/nv.html");
    suite("legislature/nv.html — the state's record names its districts", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      D.querySelector('.segmented [data-chamber="upper"]').click();
      const ballot = (D.querySelector("#legPanelBody .leg-ballot") || {}).textContent || "";
      check("the list reads as districts, with one colon",
        /The state's record: Districts 2, 8, 9, 10\b/.test(ballot) && !/: :/.test(ballot), ballot);
    });
  }
  {
    // A fusion ballot's lines are not parties (STATEGOV-21); a coalition
    // runs Alaska's chambers (STATEGOV-05, rule 54).
    const sg = {};
    new Function("window", fs.readFileSync(path.join(SITE, "data/stategov.js"), "utf8"))(sg);
    const ny = await buildPage("legislature/ny.html");
    suite("legislature/ny.html — parties, not ballot lines", () => {
      const line = ny.D.querySelector("#legPanelBody p").textContent;
      const want = sg.kycStateGov.states.NY.upper;
      check("the Senate's party line names no fusion line", !line.includes("/"), line);
      const got = {};
      [...line.matchAll(/(\d+) (Republican|Democratic)/g)].forEach((m) => { got[m[2][0]] = +m[1]; });
      check("and counts each party as the state page does", got.D === want.D && got.R === want.R,
        line + " vs " + JSON.stringify(want));
      const fused = [].concat(...Object.values(ny.window.kycLegislature.NY.chambers.upper.members))
        .find((p) => p.lines && p.lines.length);
      check("a member's card names their party and, apart, their other lines",
        !fused || (!fused.party.includes("/") && fused.lines.every((l) => !l.includes("/"))));
    });
    const ak = await buildPage("legislature/ak.html");
    suite("legislature/ak.html — who runs the chambers", () => {
      const s = sg.kycStateGov.states.AK;
      const text = ak.D.getElementById("legPanelBody").textContent;
      check("the coalition note is on the legislature page, as on the state page",
        !s.note || (text.includes(s.note) && !!ak.D.querySelector(`#legPanelBody a[href="${s.noteSource}"]`)), text);
    });
  }
  {
    /* PR #96 review: districts with a special election for the rest of a
     * term opened with "This seat is not up for regular election in 2026"
     * over a seat on the Nov 3 ballot (Kansas Senate 24, Nebraska 41). */
    for (const [file, st, name] of [["legislature/ks.html", "KS", "24"], ["legislature/ne.html", "NE", "41"]]) {
      const { window, D, errors } = await buildPage(file);
      suite(`${file} — a special election puts district ${name} on the ballot`, () => {
        check("no page errors", errors.length === 0, errors.join(" | "));
        const c = window.kycLegislature[st].chambers.upper;
        const id = Object.keys(c.districts).find((k) => c.districts[k].name.replace(/^0+/, "") === name);
        check("the district is marked from the state's record", !!id && c.districts[id].special === true,
          JSON.stringify(id && c.districts[id]));
        const summary = D.querySelector("#legPanelBody .leg-ballot").textContent;
        check("the chamber's ballot line names it", summary.includes("special election for the rest of a term") &&
          new RegExp("\\b" + name + "\\b").test(summary), summary);
        pick(D, window, id);
        const text = D.querySelector("#legPanelBody .leg-ballot").textContent;
        check("its panel says its seat is on the ballot, first, and never 'not up'",
          /^A special election for the rest of a term in this district (is|was) on the Nov 3, 2026 ballot/.test(text) &&
          !/not up for regular election/.test(text), text);
      });
      if (st === "NE") {
        suite("legislature/ne.html — a strip with no parties draws no majority tick", () => {
          const strip = D.querySelector("#legSeats .seat-strip");
          const key = D.querySelector("#legSeats .seat-key").textContent;
          const c = window.kycLegislature.NE.chambers.upper;
          check("no tick and no 'half' where nobody holds a party's seats",
            !strip.querySelector(".seat-half") && !/half/.test(key) && !/half/.test(strip.getAttribute("aria-label")), key);
          check("an outline is explained only where a seat is outlined",
            /outlined/.test(key) === (c.seats > c.listed), key);
        });
      }
    }
  }
  {
    /* PR #96 review: every link read "Official page", Connecticut's list of
     * a member's bills and nothing at all for Michigan's legislators, whose
     * only pages are on their caucuses' sites. */
    for (const [file, st] of [["legislature/mi.html", "MI"], ["legislature/ct.html", "CT"],
                              ["legislature/al.html", "AL"], ["legislature/in.html", "IN"]]) {
      const { window, D, errors } = await buildPage(file);
      suite(`${file} — a member's link says what it is`, () => {
        check("no page errors", errors.length === 0, errors.join(" | "));
        const s = window.kycLegislature[st];
        const want = { member: /^(Official page|Page on the legislature's site, \d{4}(-\d{4})? session)$/,
                       bills: /^Bills on the legislature's site$/, caucus: /^Party caucus page: \S/,
                       list: /^On the .+ member list$/ };
        const seen = {};
        for (const which of Object.keys(s.chambers)) {
          const btn = D.querySelector(`.segmented [data-chamber="${which}"]`);
          if (btn) btn.click();
          const members = s.chambers[which].members;
          for (const id of Object.keys(members)) {
            const p = members[id].find((m) => !seen[m.pageKind || "none"]);
            if (!p) continue;
            seen[p.pageKind || "none"] = true;
            pick(D, window, id);
            const card = [...D.querySelectorAll("#legPanelBody .leg-person")].find((el) =>
              el.querySelector(".leg-name").textContent === p.name);
            const a = card && card.querySelector(".leg-page a");
            if (p.page) {
              check(`a ${p.pageKind} link is labelled as one`, !!a && want[p.pageKind].test(a.textContent) &&
                a.getAttribute("href") === p.page, a && a.textContent);
            } else {
              check("a member with no page says so", !a && /links no page for this member/.test(card.textContent));
            }
          }
        }
        const kinds = { MI: "caucus", CT: "bills", AL: "list", IN: "member" };
        check(`the state's own kind of page is among them (${kinds[st]})`, !!seen[kinds[st]], Object.keys(seen).join(","));
      });
    }
  }
  {
    // The key that reads the strips, once on a state page and the directory.
    const st = await buildPage("states/mn.html");
    suite("states/mn.html — the seat strips have a key", () => {
      const keys = st.D.querySelectorAll(".seat-key");
      check("one key under the chambers", keys.length === 1 && /Republicans from the left/.test(keys[0].textContent),
        `${keys.length}`);
      const strip = st.D.querySelector(".gov-chamber .seat-strip");
      const cells = [...strip.querySelectorAll(".seat")];
      check("Republicans fill from the left, as the counts beside them read",
        cells[0].classList.contains("seat-r") && cells[cells.length - 1].classList.contains("seat-d"));
    });
    const dir = await buildPage("legislature/index.html");
    suite("legislature/index.html — one key for every strip", () => {
      const keys = dir.D.querySelectorAll(".seat-key");
      check("one key, above the list", keys.length === 1 &&
        !!(keys[0].compareDocumentPosition(dir.D.querySelector(".directory-list")) &
          dir.window.Node.DOCUMENT_POSITION_FOLLOWING), `${keys.length}`);
    });
  }
  {
    const { window, D, errors } = await buildPage("legislature/nh.html", { hash: "#/?chamber=lower" });
    suite("legislature/nh.html — members the map cannot draw are listed", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const off = window.kycLegislature.NH.unplaced.filter((p) => p.chamber === "lower");
      check("floterial members are listed under 'Not on the map'",
        off.length > 0 && off.every((p) => D.getElementById("legPanelBody").textContent.includes(p.name)),
        `${off.length}`);
      // The state page and the legislatures directory count from
      // data/stategov.js; this page must say the same numbers.
      const sg = {};
      new Function("window", fs.readFileSync(path.join(SITE, "data/stategov.js"), "utf8"))(sg);
      const want = sg.kycStateGov.states.NH.lower;
      const line = D.querySelector("#legPanelBody p").textContent;
      const got = {};
      [...line.matchAll(/(\d+) (Republican|Democratic|Independent)/g)].forEach((m) => { got[m[2][0]] = +m[1]; });
      check("the party line counts them too, as the state page does",
        ["R", "D", "I"].every((k) => (got[k] || 0) === (want[k] || 0)), line + " vs " + JSON.stringify(want));
      // Audit 2026-10-17, STATEGOV-17: listed with no district at all.
      const cards = [...D.querySelectorAll("#legPanelBody .leg-person")];
      check("each floterial member's card names their district",
        off.filter((p) => p.why === "floterial").every((p) => cards.some((card) =>
          card.textContent.includes(p.name) && card.textContent.includes("Floterial district " + p.district))));
    });
  }
  {
    const { window, D } = await buildPage("legislature/me.html", { hash: "#/?chamber=lower" });
    suite("legislature/me.html — a non-voting tribal seat is no seat in the count", () => {
      const c = window.kycLegislature.ME.chambers.lower;
      const line = D.querySelector("#legPanelBody p").textContent;
      const total = [...line.matchAll(/(\d+) [A-Z]/g)].reduce((n, m) => n + +m[1], 0);
      check("the party line adds up to the members listed for its seats", total === c.listed, line);
    });
  }
  {
    const raw = fs.readFileSync(path.join(SITE, "legislature/ms.html"), "utf8");
    suite("legislature/ms.html — a state whose lines changed says so", () => {
      check("the page names the redrawn districts", /Senate districts 1, 2, 11, 19/.test(raw));
    });
  }
  {
    const tx = await buildPage("states/tx.html");
    const dc = await buildPage("states/dc.html");
    suite("state pages — link to their legislature", () => {
      check("Texas's page links to its legislature",
        !!tx.D.querySelector('#stateContent a[href="../legislature/tx.html"]'));
      check("D.C., which has no state legislature, has no such link",
        !!dc.D.querySelector("#stateContent .state-links") &&
        !dc.D.querySelector('#stateContent a[href*="legislature/"]'));
    });
  }
}

/* =========================================================== counties */

/* A state's counties and every local government in each: the Census
 * listing, joined to the county map on the Census code. */
async function testCounties() {
  const { window, D, errors, sources } = await buildPage("counties/tx.html", { hash: "#/?county=48201" });
  const state = window.kycLocal.TX;
  suite("counties/tx.html — every county and its governments", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("its data loads before the map and the page",
      sources.indexOf("../data/local/tx.js") < sources.indexOf("../assets/kyc-regionmap.js") &&
      sources.indexOf("../assets/kyc-regionmap.js") < sources.indexOf("../assets/kyc-local.js"));
    const shapes = D.querySelectorAll("#localMap .district-statewide .region-shape");
    check("a shape per county", shapes.length === Object.keys(state.counties).length, `${shapes.length}`);
    check("counties are shaded by count, never a party colour",
      [...shapes].every((s) => /region-scale-[1-5]/.test(s.getAttribute("class")) &&
        !/party-/.test(s.getAttribute("class"))));
    check("no text inside the map's SVG (rule 46)", !D.querySelector("#localMap svg text"));
    check("a shared county link opens that county", D.getElementById("localPanelTitle").textContent === "Harris County");
    // FEDERAL-08: which federal court covers the county, from 28 U.S.C. 124,
    // through the one small file the county pages load.
    const court = D.querySelector("#localPanelBody .local-court");
    check("the county names its federal district court and division, linked to the court's page",
      !!court && /Southern District of Texas/.test(court.textContent) &&
      /Houston Division/.test(court.textContent) &&
      !!court.querySelector('a[href="../courts/tx-s.html"]'), court ? court.textContent : "none");
    check("the court table loads before the page's module",
      sources.indexOf("../data/courtcounties.js") > -1 &&
      sources.indexOf("../data/courtcounties.js") < sources.indexOf("../assets/kyc-local.js"));
    const rows = state.governments["48201"];
    const listed = D.querySelectorAll("#localPanelBody .local-item").length;
    check("every government and school system in the county is listed", listed === rows.length,
      `${listed} of ${rows.length}`);
    check("a government's own site is linked, opening safely",
      [...D.querySelectorAll('#localPanelBody .local-name a')].every((a) =>
        /^https?:\/\//.test(a.getAttribute("href")) && /noopener/.test(a.getAttribute("rel"))));
    const filter = D.getElementById("localFilter");
    filter.value = "school";
    filter.dispatchEvent(new window.Event("input"));
    const shown = D.querySelectorAll("#localPanelBody .local-item").length;
    check("the filter narrows the list", shown > 0 && shown < rows.length, `${shown}`);
    const travis = D.querySelector('#localMap .district-statewide [data-region="48453"]');
    travis.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    check("picking another county shows it, and puts it in the address",
      D.getElementById("localPanelTitle").textContent === "Travis County" &&
      /county=48453/.test(window.location.hash), window.location.hash);
    check("every county is in the list below",
      D.querySelectorAll("#localRoster .leg-row").length === Object.keys(state.counties).length);
    check("names are text, never markup", !/<script/i.test(D.getElementById("localPanelBody").innerHTML));
  });
  const cityPage = await buildPage("counties/tx.html", { hash: "#/?county=48201" });
  suite("counties/tx.html — cities and towns", () => {
    const W = cityPage.window, CD = cityPage.D;
    const cities = W.kycLocal.TX.cities;
    const ids = Object.keys(cities);
    check("no page errors", cityPage.errors.length === 0, cityPage.errors.join(" | "));
    check("the counties view draws no dots", !CD.querySelector("#localMap .map-dot"));
    const pin = CD.querySelector('#localPanelBody .local-pin[data-city="4835000"]');
    check("a county's city that is on the map has a button to show it there", !!pin);
    CD.querySelector('.segmented [data-view="cities"]').dispatchEvent(new W.MouseEvent("click", { bubbles: true }));
    const dots = CD.querySelectorAll("#localMap .district-statewide .map-dot");
    check("the cities view draws a dot per incorporated place", dots.length === ids.length,
      `${dots.length} of ${ids.length}`);
    check("the switch says which view is on, and the address carries it",
      CD.querySelector('[data-view="cities"]').getAttribute("aria-pressed") === "true" &&
      /view=cities/.test(W.location.hash), W.location.hash);
    check("dots are coloured by legal form, never a party colour",
      [...dots].every((d) => /dot-(city|town|village|borough|other)/.test(d.getAttribute("class")) &&
        !/party-/.test(d.getAttribute("class"))));
    check("counties become a plain ground under the dots",
      [...CD.querySelectorAll("#localMap .district-statewide .region-shape")].every((s) =>
        /region-plain/.test(s.getAttribute("class"))));
    check("the legend switches to the legal forms", CD.getElementById("countyLegend").hidden &&
      !CD.getElementById("cityLegend").hidden && /City/.test(CD.getElementById("cityLegend").textContent));
    check("no text inside the map's SVG (rule 46)", !CD.querySelector("#localMap svg text"));
    const listed = CD.querySelectorAll('#localRoster [data-city]').length;
    check("the list shows the first places and a button for the rest",
      listed < ids.length && listed <= 200 && !!CD.querySelector("#localRoster [data-more]"), `${listed}`);
    CD.querySelector("#localRoster [data-more]").dispatchEvent(new W.MouseEvent("click", { bubbles: true }));
    check("showing all lists every place",
      CD.querySelectorAll('#localRoster [data-city]').length === ids.length && !CD.querySelector("#localRoster [data-more]"));
    const filter = CD.getElementById("cityFilter");
    filter.value = "houston";
    filter.dispatchEvent(new W.Event("input"));
    const shown = CD.querySelectorAll('#localRoster [data-city]').length;
    check("the list's filter narrows it", shown > 0 && shown < 20, `${shown}`);
    CD.querySelector('#localMap .district-statewide [data-dot="4835000"]')
      .dispatchEvent(new W.MouseEvent("click", { bubbles: true }));
    const body = CD.getElementById("localPanelBody");
    check("picking a dot shows the place and its government, linked to its own site",
      CD.getElementById("localPanelTitle").textContent === "Houston" && /City of Houston/.test(body.textContent) &&
      !!body.querySelector('.local-name a[rel~="noopener"]'), body.textContent.slice(0, 120));
    check("the place is in the address", /city=4835000/.test(W.location.hash), W.location.hash);
    check("the picked dot is drawn larger, and once",
      CD.querySelectorAll('#localMap .district-statewide [data-dot="4835000"].is-focus').length === 1);
    body.querySelector("[data-county]").dispatchEvent(new W.MouseEvent("click", { bubbles: true }));
    check("its county is a click away", CD.getElementById("localPanelTitle").textContent === "Harris County" &&
      /county=48201/.test(W.location.hash), W.location.hash);
    const unjoined = ids.filter((id) => !cities[id][5] && !cities[id][6])[0];
    if (unjoined) {
      CD.querySelector('.segmented [data-view="cities"]').dispatchEvent(new W.MouseEvent("click", { bubbles: true }));
      CD.querySelector(`#localMap .district-statewide [data-dot="${unjoined}"]`)
        .dispatchEvent(new W.MouseEvent("click", { bubbles: true }));
      check("a place with no government joined says so, and claims no government",
        /could not tie this place to one entry/.test(body.textContent) && !body.querySelector(".local-item"),
        body.textContent.slice(0, 160));
    }
  });
  const shared = await buildPage("counties/tx.html", { hash: "#/?view=cities&city=4835000" });
  suite("counties/tx.html — a shared place link", () => {
    check("opens the cities view on that place",
      shared.D.getElementById("localPanelTitle").textContent === "Houston" &&
      shared.D.querySelectorAll("#localMap .map-dot").length > 0);
  });
  const ct = await buildPage("counties/ct.html", { hash: "#/?view=cities" });
  suite("counties/ct.html — towns, where towns are the local government", () => {
    const W = ct.window, CD = ct.D;
    const towns = W.kycLocal.CT.towns;
    const townIds = Object.keys(towns);
    check("no page errors", ct.errors.length === 0, ct.errors.join(" | "));
    check("Connecticut's towns are on the map, each joined to its government",
      townIds.length > 100 && townIds.every((id) => towns[id][5]), `${townIds.length}`);
    const rings = CD.querySelectorAll("#localMap .district-statewide .map-dot.dot-township");
    check("a town is drawn as a ring, apart from the incorporated places", rings.length === townIds.length,
      `${rings.length} of ${townIds.length}`);
    check("the legend names the ring", /Town or township government/.test(CD.getElementById("cityLegend").textContent));
    const id = townIds[0];
    CD.querySelector(`#localMap .district-statewide [data-dot="${id}"]`)
      .dispatchEvent(new W.MouseEvent("click", { bubbles: true }));
    const body = CD.getElementById("localPanelBody");
    const ref = towns[id][5];
    const gov = W.kycLocal.CT.governments[ref[0]][ref[1]];
    check("picking a town shows it as a county subdivision government, with its government",
      CD.getElementById("localPanelTitle").textContent === towns[id][3] &&
      /county subdivision/.test(body.textContent) && body.textContent.indexOf(gov[1]) !== -1,
      body.textContent.slice(0, 160));
    check("the town is in the address", W.location.hash.indexOf("city=" + id) !== -1, W.location.hash);
    check("every town is in the list under the map",
      townIds.every((t) => CD.querySelector(`#localRoster [data-city="${t}"]`)));
    body.querySelector("[data-county]").dispatchEvent(new W.MouseEvent("click", { bubbles: true }));
    check("the town's government has a button that shows it on the map",
      !!CD.querySelector(`#localPanelBody .local-pin[data-city="${id}"]`));
  });
  const ky = await buildPage("counties/ky.html", { hash: "#/?view=cities&city=2148000" });
  suite("counties/ky.html — a place the Census records as not governing", () => {
    const body = ky.D.getElementById("localPanelBody").textContent;
    check("Louisville says what the Census records, in its words, and claims no government",
      /records Louisville as a nonfunctioning legal entity/.test(body) &&
      !ky.D.querySelector("#localPanelBody .local-item") && !/incorporated since/.test(body), body.slice(0, 200));
  });
  const co = await buildPage("counties/co.html", { hash: "#/?view=cities&city=0806255" });
  suite("counties/co.html — a city listed under another county than its point", () => {
    const body = co.D.getElementById("localPanelBody");
    check("Berthoud links the county whose list holds its government, and says so",
      body.querySelector("[data-county]").getAttribute("data-county") === "08069" &&
      /under Larimer County/.test(body.textContent), body.textContent.slice(0, 200));
  });
  // Rule 71: the directory said Rhode Island had no county governments while
  // its page drew five counties and said nothing about it.
  const ri = await buildPage("counties/ri.html");
  suite("counties/ri.html — counties with no county government say so", () => {
    const body = ri.D.getElementById("localPanelBody").textContent;
    check("no page errors", ri.errors.length === 0, ri.errors.join(" | "));
    check("the state says it has no county governments, and what its counties are",
      /Rhode Island has no county governments/.test(body) && /organize its courts/.test(body), body.slice(0, 300));
    check("every county in the list under the map says it has no county government",
      [...ri.D.querySelectorAll("#localRoster .leg-row")].every((r) => /no county government/.test(r.textContent)));
    ri.D.querySelector('#localRoster [data-region="44001"]')
      .dispatchEvent(new ri.window.MouseEvent("click", { bubbles: true }));
    const panel = ri.D.getElementById("localPanelBody").textContent;
    check("a county's panel says why it has no county government, above its governments",
      /Bristol County has no county government/.test(panel) && /Town of Barrington/.test(panel), panel.slice(0, 300));
  });
  const ny = await buildPage("counties/ny.html", { hash: "#/?county=36005" });
  suite("counties/ny.html — a borough's governments are listed under Manhattan", () => {
    const body = ny.D.getElementById("localPanelBody");
    check("the Bronx says it has none of its own, and why, not 0",
      /No local governments of its own/.test(body.textContent) && /the Bronx, one of New York City/.test(body.textContent) &&
      !/^0 /.test(body.textContent), body.textContent.slice(0, 300));
    check("with a link to the county that lists the City of New York",
      body.querySelector("[data-county]") && body.querySelector("[data-county]").getAttribute("data-county") === "36061");
    check("and no empty filter", !body.querySelector("#localFilter"));
  });
  const parishes = await buildPage("counties/la.html");
  suite("counties/la.html — parishes are called parishes", () => {
    check("the map's button, the list and the state's count say parish",
      parishes.D.querySelector('[data-view="counties"]').textContent === "Parishes" &&
      parishes.D.getElementById("localRosterTitle").textContent === "Every parish" &&
      / in 64 parishes \(2022\)/.test(parishes.D.getElementById("localPanelBody").textContent),
      parishes.D.getElementById("localPanelBody").textContent.slice(0, 120));
  });
  // STATEGOV-20: an independent city in Virginia's words, and counted apart.
  const va = await buildPage("counties/va.html", { hash: "#/?county=51510" });
  suite("counties/va.html — independent cities in the state's own words", () => {
    check("no page errors", va.errors.length === 0, va.errors.join(" | "));
    check("Alexandria is headed City of Alexandria, not the Census's 'Alexandria city'",
      va.D.getElementById("localPanelTitle").textContent === "City of Alexandria");
    const label = va.D.querySelector('label[for="localFilter"]');
    check("its filter is not called a county's", !!label && !/county/i.test(label.textContent) &&
      /in the City of Alexandria$/.test(label.textContent), label && label.textContent);
    // An independent city sorts under its own name, not among the C's.
    const order = [...va.D.querySelectorAll("#countyRows [data-region]")].map((r) => r.getAttribute("data-region"));
    const at = (fips) => order.indexOf(fips);
    check("the list sorts the City of Richmond under R, between Rappahannock and Richmond County",
      at("51157") < at("51760") && at("51760") < at("51159") && at("51033") < at("51059") &&
      at("51510") < at("51013"), [at("51157"), at("51760"), at("51159")].join(" "));
    va.D.querySelector('#localRoster [data-region="51059"]')
      .dispatchEvent(new va.window.MouseEvent("click", { bubbles: true }));
    const body = va.D.getElementById("localPanelBody");
    // STATEGOV-09, PERSONA-17: "Fairfax Co Schs", written out, the listing's form kept.
    const schools = [...body.querySelectorAll(".local-item")].find((li) => /Fairfax County Schools/.test(li.textContent));
    check("a Census abbreviation is written out, the listing's form in its title",
      !!schools && /Fairfax Co Schs/.test(schools.querySelector('[title^="Listed by"]').getAttribute("title")) &&
      !/Co Schs/.test(body.textContent), schools && schools.innerHTML);
    // A browser shows only the innermost title: one per name, on the link.
    check("a linked name carries one title, the listing's name and the link's check together",
      [...body.querySelectorAll(".local-name a")].every((a) => !a.querySelector("[title]")) &&
      [...body.querySelectorAll(".local-name a[title^='Listed by']")].every((a) =>
        /Website as listed by the Census in 2022/.test(a.getAttribute("title"))));
    // A link the check could not confirm says so on the row, for a phone.
    const unsure = Object.values(va.window.kycLocal.VA.governments).flat()
      .filter((r) => r[3] && /^unread /.test(r[7] || ""));
    check("the data has links the check could not confirm", unsure.length > 0);
    check("the place line is the mailing address, said so",
      /mailing address in Fairfax/.test(body.textContent), body.textContent.slice(0, 300));
    // STATEGOV-08, PERSONA-16: who serves is an absence here, said once, with where to look.
    check("the panel says who holds office is not listed here, and where to look",
      /Who holds office in these governments is not listed here/.test(body.textContent) &&
      /own website/.test(body.textContent));
    // Many listed bodies have appointed boards, and many sites list neither.
    check("it does not claim every site names elected officials and their elections",
      !/names its elected officials|when they are elected/.test(body.textContent) &&
      /usually where its officials, and how they are chosen, are listed/.test(body.textContent));
    const rowsVa = [...body.querySelectorAll(".local-item")];
    const unconfirmed = rowsVa.filter((li) => /website not confirmed when checked/.test(li.textContent));
    check("a row whose link the check could not confirm says so in words",
      unconfirmed.every((li) => !!li.querySelector("a")) &&
      rowsVa.filter((li) => li.querySelector("a") && /not confirmed/.test(li.querySelector("a").getAttribute("title")))
        .length === unconfirmed.length, `${unconfirmed.length}`);
    va.window.location.hash = "#/";
  });
  await new Promise((resolve) => setTimeout(resolve, 30));
  suite("counties/va.html — the state's count", () => {
    const text = va.D.getElementById("localPanelBody").textContent;
    check("counts its counties and independent cities apart",
      / in 95 counties and 38 independent cities \(2022\)/.test(text), text.slice(0, 160));
    check("and says who serves is not listed", /not listed here/.test(text));
  });
  // LINKS-07, TRUST-07, rule 78: a listed website that now leads to
  // gambling, parking or nowhere is withdrawn, and the list says so.
  const ctSites = await buildPage("counties/ct.html");
  suite("counties/ct.html — a local website the check refused is withdrawn", () => {
    const W = ctSites.window, CD = ctSites.D;
    const govs = W.kycLocal.CT.governments;
    const where = Object.keys(govs).find((f) => govs[f].some((r) => r[1] === "Town of Clinton"));
    CD.querySelector(`#localRoster [data-region="${where}"]`)
      .dispatchEvent(new W.MouseEvent("click", { bubbles: true }));
    const item = [...CD.querySelectorAll("#localPanelBody .local-item")]
      .find((li) => li.querySelector(".local-name").textContent.trim() === "Town of Clinton");
    check("the Town of Clinton's old address, now a slot site, is not linked",
      !!item && !item.querySelector("a"), item && item.innerHTML);
    check("and its line says why, and when",
      !!item && /website withdrawn: .*gambling spam \(checked [A-Z][a-z]{2} \d{1,2}, \d{4}\)/.test(item.textContent),
      item && item.textContent);
    const links = [...CD.querySelectorAll("#localPanelBody .local-name a")];
    check("every link left says what it is: the Census's 2022 address, and whether it was checked",
      links.length > 0 && links.every((a) => /Website as listed by the Census in 2022/.test(a.getAttribute("title"))));
    const note = CD.querySelector("#localPanelBody .local-sites");
    check("the panel says what its websites are and when they were checked",
      !!note && /listed in 2022/.test(note.textContent) && /withdrawn, and each says why/.test(note.textContent),
      note && note.textContent);
    const all = Object.values(govs).flat();
    check("no withdrawn row keeps an address",
      all.every((r) => !/^(dead|gone|parked|for-sale|expired|gambling|elsewhere|business) /.test(r[7] || "") || r[3] === ""));
  });
  // VISUALS-14: county names on the map where they fit, as page text.
  const wi = await buildPage("counties/wi.html");
  suite("counties/wi.html — county names on the map", () => {
    const W = wi.window, WD = wi.D;
    const counties = W.kycLocal.WI.counties;
    const labels = [...WD.querySelectorAll("#localMap .map-labels .county-label")];
    check("names counties where the build measured room, as page text, never SVG text (rule 46)",
      labels.length > 10 && !WD.querySelector("#localMap svg text"), `${labels.length}`);
    check("each label is a county's own name", labels.every((l) =>
      Object.values(counties).some((c) => c.label === l.textContent)));
    check("only where it fits at the width drawn",
      labels.length < Object.keys(counties).length);
    const filter = WD.getElementById("countyFilter");
    check("the list under the map has a filter, above its grid, not in it",
      !!filter && !filter.closest(".leg-roster") && !!WD.querySelector("#countyRows.leg-roster"));
    filter.value = "milw";
    filter.dispatchEvent(new W.Event("input"));
    const rows = [...WD.querySelectorAll("#countyRows [data-region]")];
    check("and finds a county by name", rows.length === 1 && /Milwaukee/.test(rows[0].textContent),
      rows.map((r) => r.textContent).join(" | "));
    WD.querySelector('[data-view="cities"]').dispatchEvent(new W.MouseEvent("click", { bubbles: true }));
    check("the cities view, which draws its dots over the counties, has no county names",
      !WD.querySelector("#localMap .county-label"));
    const cityFilter = WD.getElementById("cityFilter");
    // STATEGOV-07: inside the 3-column grid the filter was one cell, 15,000px tall.
    check("the cities filter sits above the list's grid, not in it",
      !!cityFilter && !cityFilter.closest(".leg-roster") && !!WD.querySelector("#cityRows.leg-roster") &&
      !WD.getElementById("localRoster").classList.contains("leg-roster"));
  });
  // VISUALS-14 review: Texas had room for one name, "Pecos", which read as
  // the pick; picking Harris left "Pecos" the only word on the map.
  const txNames = await buildPage("counties/tx.html", { hash: "#/?county=48201" });
  suite("counties/tx.html — names only where a fair share fit; the pick always", () => {
    const labels = [...txNames.D.querySelectorAll("#localMap .county-label")];
    const all = Object.keys(txNames.window.kycLocal.TX.counties).length;
    const focus = labels.filter((l) => l.classList.contains("is-focus"));
    check("the picked county is named, room or not (rule 43)",
      focus.length === 1 && focus[0].textContent === "Harris", labels.map((l) => l.textContent).join(" | "));
    check("and no lone name of another county stands for the rest",
      labels.length === 1 || labels.length - 1 >= 0.25 * all, `${labels.length} of ${all}`);
  });
  const once = await buildPage("counties/tx.html", { hash: "#/?county=48201" });
  let draws = 0;
  new once.window.MutationObserver((records) => {
    draws += records.filter((r) => r.target.id === "localMap").length;
  }).observe(once.D.getElementById("localMap"), { childList: true });
  once.window.location.hash = "#/?view=cities&city=4819000";
  await new Promise((resolve) => setTimeout(resolve, 60));
  suite("counties/tx.html — one address change, one draw (rule 45)", () => {
    check("switching the view and picking a city from one link draws the map once", draws === 1, `${draws}`);
    check("and shows the city", once.D.getElementById("localPanelTitle").textContent === "Dallas");
  });
  const il = await buildPage("counties/il.html", { hash: "#/?view=cities&city=1754885" });
  suite("counties/il.html — a township and a village at one point", () => {
    const body = il.D.getElementById("localPanelBody");
    const ring = il.D.querySelector('#localMap .district-statewide [data-dot="1703154898"]');
    const dot = il.D.querySelector('#localMap .district-statewide [data-dot="1754885"]');
    check("the Village of Oak Park's panel names the township at the same point",
      !!body.querySelector('[data-city="1703154898"]'), body.textContent.slice(0, 200));
    check("the ring is drawn under the dot and round it, so both show and the dot takes its own taps",
      !!ring && !!dot && (ring.compareDocumentPosition(dot) & il.window.Node.DOCUMENT_POSITION_FOLLOWING) !== 0 &&
      +ring.getAttribute("data-r") > +dot.getAttribute("data-r"), ring && ring.getAttribute("data-r"));
    const dots = [...il.D.querySelectorAll("#localMap .district-statewide .map-dot")];
    const firstPlace = dots.findIndex((d) => !d.classList.contains("dot-township"));
    check("every ring is drawn before every city dot",
      dots.slice(firstPlace).every((d) => !d.classList.contains("dot-township")));
  });
  const ksTown = await buildPage("counties/ks.html", { hash: "#/?view=cities&city=2011924200" });
  suite("counties/ks.html — a township the Census records as inactive", () => {
    check("says so, in the Census's words",
      /records Fowler as an inactive governmental unit/.test(ksTown.D.getElementById("localPanelBody").textContent));
  });
  const la = await buildPage("counties/la.html", { hash: "#/?view=cities&city=2205000" });
  suite("counties/la.html — a city its consolidated government governs", () => {
    const text = la.D.getElementById("localPanelBody").textContent;
    check("Baton Rouge gives its status, its government, and why that government is the parish's too",
      /partially consolidated/.test(text) && /City-Parish of Baton Rouge-East Baton Rouge/.test(text) &&
      /East Baton Rouge Parish has no separate parish government/.test(text) &&
      !/incorporated since/.test(text), text.slice(0, 400));
  });
  const stGeorge = await buildPage("counties/la.html", { hash: "#/?view=cities&city=2267303" });
  suite("counties/la.html — a place tied to no government names no single cause", () => {
    const text = stGeorge.D.getElementById("localPanelBody").textContent;
    check("St. George (2024) is told both causes, neither as the one",
      /could not tie this place to one entry/.test(text) && /may file its government under another name/.test(text) &&
      /may have been incorporated since 2022/.test(text), text.slice(0, 400));
  });
  const kc = await buildPage("counties/ks.html", { hash: "#/?view=cities&city=2036000" });
  suite("counties/ks.html — Kansas City and the Unified Government", () => {
    const text = kc.D.getElementById("localPanelBody").textContent;
    check("Kansas City's government is the Unified Government, said as Wyandotte County's too",
      /Unified Government of Wyandotte County and Kansas City/.test(text) &&
      /Wyandotte County has no separate county government/.test(text), text.slice(0, 400));
    kc.window.location.hash = "#/?view=cities";
    kc.window.dispatchEvent(new kc.window.Event("hashchange"));
  });
  await new Promise((resolve) => setTimeout(resolve, 60));
  suite("counties/ks.html — the township governments the map cannot place are counted", () => {
    const body = kc.D.getElementById("localPanelBody").textContent;
    const state = kc.window.kycLocal.KS;
    const placed = new Set(Object.values(state.towns).concat(Object.values(state.cities))
      .filter((c) => c[5]).map((c) => c[5].join(":")));
    let left = 0;
    Object.keys(state.governments).forEach((f) => state.governments[f].forEach((r, i) => {
      if (r[0] === "township" && !placed.has(f + ":" + i)) left += 1;
    }));
    check("the lede no longer says every township is drawn, and counts those that are not",
      !/every town or township that governs/.test(body) && left > 0 &&
      body.indexOf(left + " more town or township governments in the 2022 listing could not be placed") !== -1,
      left + " | " + body.slice(0, 500));
  });
  const mn = await buildPage("counties/mn.html", { hash: "#/?view=cities&city=2711100100" });
  suite("counties/mn.html — Show all, and a link without its view", () => {
    const more = mn.D.querySelector("#localRoster [data-more]");
    more.dispatchEvent(new mn.window.MouseEvent("click", { bubbles: true }));
    const rows = mn.D.querySelectorAll("#localRoster [data-city]");
    check("Show all leaves keyboard focus on the first row it showed", mn.D.activeElement === rows[200],
      mn.D.activeElement && mn.D.activeElement.textContent.slice(0, 40));
    const filter = mn.D.getElementById("cityFilter");
    filter.value = "a";
    filter.dispatchEvent(new mn.window.Event("input"));
    check("a new filter starts from the first 200 again",
      mn.D.querySelectorAll("#localRoster [data-city]").length <= 200 && !!mn.D.querySelector("#localRoster [data-more]"));
  });
  let mnDraws = 0;
  new mn.window.MutationObserver((records) => {
    mnDraws += records.filter((r) => r.target.id === "localMap").length;
  }).observe(mn.D.getElementById("localMap"), { childList: true });
  mn.window.location.hash = "#/?city=2711100100";
  await new Promise((resolve) => setTimeout(resolve, 60));
  suite("counties/mn.html — a place in the address is a place on the cities map", () => {
    check("dropping view=cities from a place's link does not redraw the map", mnDraws === 0, `${mnDraws}`);
    check("and the place stays picked",
      mn.D.querySelector('[data-view="cities"]').getAttribute("aria-pressed") === "true" &&
      mn.D.getElementById("localPanelTitle").textContent === mn.window.kycLocal.MN.towns["2711100100"][3]);
  });
  const hawaii = await buildPage("counties/hi.html");
  suite("counties/hi.html — a state with no incorporated place", () => {
    check("offers no cities view", hawaii.D.querySelector(".segmented").hidden &&
      !hawaii.D.querySelector("#localMap .map-dot"));
  });
  const nj = await buildPage("counties/nj.html");
  suite("counties/nj.html — the statewide list says what the listing says", () => {
    const body = nj.D.getElementById("localPanelBody").textContent;
    check("filed under the state, never 'run by the state' (Jersey City's schools are not)",
      /listing files these under the state rather than under a county/.test(body) &&
      !/Run by the state/.test(body), body.slice(-400));
  });
  const nc = await buildPage("counties/nc.html", { hash: "#/?county=37001" });
  suite("counties/nc.html — a county's count and the school systems under it", () => {
    const rows = nc.window.kycLocal.NC.governments["37001"];
    const dependent = rows.filter((r) => r[0] === "dependent").length;
    const body = nc.D.getElementById("localPanelBody").textContent;
    check("the headline counts the governments, not the dependent school systems",
      body.indexOf((rows.length - dependent) + " local governments in 2022") === 0 && dependent > 0,
      body.slice(0, 80));
    check("and the school systems under it say why they are not counted",
      /School systems run by another government/.test(body) &&
      /Not counted as local governments: the Census Bureau counts a school system/.test(body));
  });
  const tx = await buildPage("states/tx.html");
  suite("states/tx.html — links to its counties", () => {
    check("the state page links to its counties page",
      !!tx.D.querySelector('#stateContent a[href="../counties/tx.html"]'));
  });
}

/* ======================================================= state government */

async function testStateGov() {
  const { window, D, errors, sources } = await buildPage("map.html", { hash: "#/?state=AK&mode=legislature" });
  const data = window.kycStateGov;
  const KYC = window.KYC;
  const shape = (code) => D.querySelector('#usMap [data-state="' + code + '"]');
  const stateCodes = Object.keys(window.kycGeo.states).filter((c) => c !== "DC");

  suite("map.html — governors, legislatures and trifectas", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("the data loads before the module, and the module before the map",
      sources.indexOf("data/stategov.js") < sources.indexOf("assets/kyc-stategov.js") &&
      sources.indexOf("assets/kyc-stategov.js") < sources.indexOf("assets/kyc-map.js"));
    check("a pasted URL opens the view and the state",
      D.querySelector('[data-mode="legislature"]').getAttribute("aria-pressed") === "true" &&
      D.getElementById("panelState").textContent === "Alaska");
    const panel = D.getElementById("delegation");
    check("Alaska's coalitions are said, with the Legislature's own roster",
      /coalitions/.test(panel.textContent) &&
      !!panel.querySelector('a[href^="https://www.akleg.gov/"]'));
    check("so Alaska is not a trifecta", data.states.AK.trifecta === "divided");
    check("the panel links the state's legislature and counties pages",
      !!panel.querySelector('a[href$="legislature/ak.html"]') &&
      !!panel.querySelector('a[href$="counties/ak.html"]'));
    check("every outbound link opens safely",
      [...panel.querySelectorAll('a[target="_blank"]')].every((a) => /noopener/.test(a.getAttribute("rel"))));
    check("a seat is never called vacant", !/vacan/i.test(panel.textContent));
    check("Nebraska is drawn as nonpartisan, not as a party",
      /without party labels/.test(shape("NE").getAttribute("aria-label")) &&
      !/party-/.test(shape("NE").style.fill));

    D.querySelector('[data-mode="governor"]').click();
    check("each state is filled by its governor's party", stateCodes.every((c) =>
      shape(c).style.fill === "var(--party-" + data.states[c].governor.partyKey.toLowerCase() + ")"),
      stateCodes.filter((c) => !data.states[c]).join(" "));
    check("D.C. says it has a mayor, not a governor",
      /mayor/.test(shape("DC").getAttribute("aria-label")));
    check("the governor is named, with the NGA's page",
      D.getElementById("delegation").textContent.indexOf(data.states.AK.governor.name) !== -1 &&
      !!D.querySelector('#delegation a[href^="https://www.nga.org/governors/"]'));
    check("the view is in the address", /mode=governor/.test(window.location.hash), window.location.hash);
    check("the legend follows the view", /Republican governor/.test(D.getElementById("mapLegend").textContent));

    // Which governorships are elected on Nov 3: the current governor's party
    // where one is, and the empty grey where none is.
    D.querySelector('[data-mode="governor2026"]').click();
    const up = stateCodes.filter((c) => data.states[c].ballot2026 &&
      data.states[c].ballot2026.offices.governor.up);
    check("every state has a 2026 ballot record", stateCodes.every((c) => !!data.states[c].ballot2026));
    check("a governor's election is drawn in the governor's party, and no other state is",
      up.length > 0 && stateCodes.every((c) => up.indexOf(c) !== -1
        ? shape(c).style.fill === "var(--party-" + data.states[c].governor.partyKey.toLowerCase() + ")"
        : shape(c).style.fill === window.KYC.svgFill("var(--none-fill)")),
      up.length + " up");
    check("its label says whether the governor is elected on Nov 3",
      /elected on Nov 3/.test(shape(up[0]).getAttribute("aria-label")) &&
      /no governor's election in 2026/.test(shape("VA").getAttribute("aria-label")));
    // An open seat is said in words, naming the list that says so, as every
    // other such claim on the site does (PR #109 review).
    const openSeat = up.find((c) => {
      const hs = data.states[c].ballot2026.offices.governor.holderStatus;
      return hs && hs.why === "not-listed" && hs.holder === data.states[c].governor.name;
    });
    check("an open seat's label names the list that leaves the governor off",
      !openSeat || shape(openSeat).getAttribute("aria-label").indexOf("open seat: " +
        data.states[openSeat].governor.name + " is not among the candidates on " +
        data.states[openSeat].ballot2026.offices.governor.holderStatus.cite) !== -1,
      openSeat && shape(openSeat).getAttribute("aria-label"));
    // The colour is the sitting governor's party, who may not be running
    // (audit 2026-10-17, RACES-09): the legend says whose party it is.
    const legendText = D.getElementById("mapLegend").textContent;
    check("the legend says what the colours mean, and that the colour is the current governor's",
      /No governor's election in 2026/.test(legendText) &&
      /current governor: Republican/.test(legendText) && !/the governor now is/.test(legendText) &&
      !/territories/.test(legendText), legendText);
    // Guam, the Virgin Islands and the Northern Mariana Islands elect their
    // governors on Nov 3 (RACES-07): drawn like any state, never "not covered".
    ["GU", "VI", "MP"].forEach((t) => {
      const shapeT = D.querySelector('#usMap [data-state="' + t + '"]');
      check(t + " is drawn as electing its governor on Nov 3",
        !!shapeT && shapeT.style.fill === "var(--party-" +
          data.states[t].governor.partyKey.toLowerCase() + ")" &&
          /elected on Nov 3/.test(shapeT.getAttribute("aria-label")),
        shapeT && shapeT.getAttribute("aria-label"));
    });
    const pr = D.querySelector('#usMap [data-state="PR"]');
    check("Puerto Rico, which elected its governor in 2024, is drawn as no election",
      !!pr && pr.style.fill === window.KYC.svgFill("var(--none-fill)") &&
        /no governor's election in 2026/.test(pr.getAttribute("aria-label")),
      pr && pr.getAttribute("aria-label"));

    D.querySelector('[data-mode="trifecta"]').click();
    const painted = stateCodes.filter((c) => shape(c).style.fill === "var(--party-r)").length;
    const counted = stateCodes.filter((c) => data.states[c].trifecta === "R").length;
    check("every Republican trifecta in the data is painted, and nothing else",
      painted === counted && counted > 0, `${painted} painted, ${counted} in the data`);
    check("a state without a trifecta is divided", (() => {
      const divided = stateCodes.filter((c) => data.states[c].trifecta === "divided");
      // Hatched as well as coloured: to a deuteranope the split colour
      // alone was the Democratic blue (VISUALS-03).
      return divided.length > 0 && divided.every((c) =>
        shape(c).style.fill === window.KYC.svgFill("var(--split)") && /hatch-split/.test(shape(c).style.fill));
    })());

    window.location.hash = "#/?state=GU&mode=legislature";
    window.dispatchEvent(new window.Event("hashchange"));
    check("a territory's governor is never shown as its legislature's party",
      !/Democratic|Republican/.test(D.getElementById("panelCounts").textContent) &&
      /not covered/.test(D.getElementById("panelCounts").textContent),
      D.getElementById("panelCounts").textContent);

    window.location.hash = "#/?state=MN&mode=legislature";
    window.dispatchEvent(new window.Event("hashchange"));
    check("a chamber where no party has a majority says so",
      /No party holds a majority/.test(D.getElementById("delegation").textContent));

    const img = D.querySelector("#delegation .gov-portrait");
    if (img) {
      img.dispatchEvent(new window.Event("error"));
      check("a headshot that fails to load is removed, not left broken",
        !D.querySelector("#delegation .gov-portrait"));
    }
    check("no text inside the map's SVG (rule 46)", !D.querySelector("#usMap text"));
  });

  suite("map.html — lieutenant governors and secretaries of state", () => {
    const pick = (hash) => {
      window.location.hash = hash;
      window.dispatchEvent(new window.Event("hashchange"));
      return D.getElementById("delegation").textContent;
    };
    // Oregon has none; Arizona's is a new office first filled on Nov 3.
    let text = pick("#/?state=OR&mode=lt");
    check("the Lt. governors view is selected, and only it, across every group",
      D.querySelectorAll('[data-mode][aria-pressed="true"]').length === 1 &&
      D.querySelector('[data-mode="lt"]').getAttribute("aria-pressed") === "true");
    check("a state with no lieutenant governor names who is first in line",
      /no lieutenant governor/.test(text) && /First in line/.test(text) &&
      /Secretary of State/.test(text), text.slice(0, 200));
    check("and is drawn as having no such office, not in a party colour",
      !/party-/.test(shape("OR").style.fill) && !/party-/.test(shape("AZ").style.fill));
    // Whichever state is vacant this week: the test must not fail the refresh
    // that fills New Jersey's office.
    const vacancy = stateCodes.find((c) => data.states[c].lt && data.states[c].lt.vacant);
    if (vacancy) {
      text = pick("#/?state=" + vacancy + "&mode=lt");
      check("a vacancy is said, and attributed", /Vacant, as the National Lieutenant Governors Association lists it/.test(text));
    }
    const listed = stateCodes.find((c) => data.states[c].sos && data.states[c].sos.notMember);
    if (listed) {
      text = pick("#/?state=" + listed + "&mode=sos");
      check("a secretary NASS lists for a non-member is its listing, not a fact",
        /not currently a NASS member/.test(text) && (() => {
          const row = [...D.querySelectorAll("#delegation .gov-officer")]
            .find((li) => /Secretary of state/i.test(li.querySelector(".gov-officer-role").textContent));
          return row && !row.querySelector(".gov-officer-name");
        })());
      check("and is drawn unconfirmed, not in a party colour", !/party-/.test(shape(listed).style.fill));
      check("and the legend has a key for that grey",
        /Not confirmed by the office/.test(D.getElementById("mapLegend").textContent),
        D.getElementById("mapLegend").textContent);
    }
    const hi = data.states.HI.lt;
    if (hi && hi.disputed) {
      text = pick("#/?state=HI&mode=lt");
      check("where the rosters disagree, both are named and neither is the holder",
        hi.disputed.every((n) => text.indexOf(n) !== -1) && /Neither is shown as the holder/.test(text) &&
        !D.querySelector("#delegation .gov-officer-name"));
      check("the legend explains the disagreement",
        /Sources disagree/.test(D.getElementById("mapLegend").textContent));
    }
    pick("#/?state=TX&mode=sos");
    check("each state is filled by its secretary of state's party", stateCodes.every((c) => {
      const o = data.states[c].sos;
      if (!o || o.none || o.disputed || o.vacant || o.notMember) return true;
      return shape(c).style.fill === "var(--party-" + o.partyKey.toLowerCase() + ")";
    }));
    text = pick("#/?state=UT&mode=sos");
    check("a state with no secretary of state says who runs its elections",
      /no secretary of state; the lieutenant governor's office runs its elections/.test(text));
    text = pick("#/?state=TX&mode=sos");
    check("an appointed secretary of state is marked so", /Appointed/.test(text) && /Chief election official/.test(text));
    check("every outbound link opens safely",
      [...D.querySelectorAll('#delegation a[target="_blank"]')].every((a) => /noopener/.test(a.getAttribute("rel"))));
    const photo = D.querySelector("#delegation .gov-officer-photo");
    if (photo) {
      photo.dispatchEvent(new window.Event("error"));
      check("an officer's photo that fails to load is removed", !photo.isConnected);
    }
  });

  suite("map.html — attorneys general", () => {
    const pick = (hash) => {
      window.location.hash = hash;
      window.dispatchEvent(new window.Event("hashchange"));
      return D.getElementById("delegation").textContent;
    };
    const confirmed = stateCodes.find((c) => data.states[c].ag && data.states[c].ag.name &&
      !data.states[c].ag.unconfirmed);
    let text = pick("#/?state=" + confirmed + "&mode=ag");
    check("a confirmed attorney general is named, with the association their party comes from",
      text.indexOf(data.states[confirmed].ag.name) !== -1 && /Party: a member of the/.test(text));
    check("each confirmed attorney general's state is in their party's colour", stateCodes.every((c) => {
      const o = data.states[c].ag;
      if (!o || o.unconfirmed || o.disputed || o.unlisted) return true;
      return shape(c).style.fill === "var(--party-" + o.partyKey.toLowerCase() + ")";
    }));
    const unconfirmed = stateCodes.find((c) => data.states[c].ag && data.states[c].ag.unconfirmed);
    if (unconfirmed) {
      text = pick("#/?state=" + unconfirmed + "&mode=ag");
      check("an unconfirmed listing is attributed to its association, not stated as fact",
        /lists .* as its member here/.test(text) && /not confirmed/.test(text));
      check("and is drawn unconfirmed, with a legend for it",
        !/party-/.test(shape(unconfirmed).style.fill) &&
        /Not confirmed by the office/.test(D.getElementById("mapLegend").textContent));
    }
    // STATEGOV-13: no attorney general had a photograph, so their rows read
    // differently from every row above them.
    const pictured = stateCodes.find((c) => data.states[c].ag && data.states[c].ag.photo &&
      !data.states[c].ag.unconfirmed);
    check("attorneys general are pictured", !!pictured);
    if (pictured) {
      const ag = data.states[pictured].ag;
      pick("#/?state=" + pictured + "&mode=ag");
      check("a confirmed attorney general's row carries their photograph",
        [...D.querySelectorAll("#delegation .gov-officer-photo")].some((i) =>
          i.getAttribute("src") === ag.photo));
      const sources = (D.querySelector("#delegation .gov-sources") || {}).textContent || "";
      check("and the sources say whose photograph it is (rule 87)",
        sources.indexOf("attorney general, " + ag.photoBy) !== -1, sources);
    }
    // A named holder without a photograph keeps the photograph's column, so
    // the row lines up with the pictured rows above it.
    const bare = stateCodes.find((c) => data.states[c].ag && data.states[c].ag.name &&
      !data.states[c].ag.photo && !data.states[c].ag.unconfirmed && !data.states[c].ag.disputed);
    if (bare) {
      pick("#/?state=" + bare + "&mode=ag");
      const row = [...D.querySelectorAll("#delegation .gov-officer")].find((li) =>
        li.textContent.indexOf(data.states[bare].ag.name) !== -1);
      check("an unpictured attorney general's row keeps the photograph's column",
        !!row && !row.classList.contains("gov-officer-text") &&
        !!row.querySelector(".gov-officer-nophoto[aria-hidden='true']"));
    }
  });

  suite("state government — the data", () => {
    check("every state has a governor", stateCodes.every((c) => data.states[c] && data.states[c].governor.name));
    const uncredited = stateCodes.filter((c) => {
      const s = data.states[c];
      return (s.governor.headshot && !s.governor.headshotBy) ||
        ["lt", "ag", "sos"].some((k) => s[k] && s[k].photo && !s[k].photoBy);
    });
    check("every photograph on a state's card says whose it is (rule 87)", !uncredited.length,
      uncredited.join(","));
    check("a majority is more than half of all seats", stateCodes.every((c) => {
      const s = data.states[c];
      return ["upper", "lower"].every((k) => {
        const ch = s[k];
        if (!ch) return true;
        const m = ch.majority;
        return m ? ch[m] * 2 > ch.seats : ch.D * 2 <= ch.seats && ch.R * 2 <= ch.seats;
      });
    }));
  });

  const ak = await buildPage("states/ak.html");
  const mapped = await buildPage("map.html", { hash: "#/?state=AK&mode=legislature" });
  suite("states/ak.html — its state government", () => {
    const section = ak.D.getElementById("state-government");
    check("the state page has a state government section", !!section);
    const sources = section.querySelector(".gov-sources").textContent;
    check("its sources say NCSL checks which party holds a chamber, not the seat counts",
      /Seats: Open States.*?\)\. Which party holds each chamber is checked against National Conference/.test(sources),
      sources);
    const heads = [...ak.D.querySelectorAll("#stateContent .state-heading")].map((h) => h.textContent);
    check("it follows the congressional delegation (rule 27)",
      heads.findIndex((h) => /State government/.test(h)) > heads.findIndex((h) => /House/.test(h)), heads.join(" | "));
    check("it says exactly what the map's panel says (rule 12)",
      section.querySelector(".gov-chambers").innerHTML ===
        mapped.D.querySelector("#delegation .gov-chambers").innerHTML &&
      section.querySelector(".gov-note").textContent ===
        mapped.D.querySelector("#delegation .gov-note").textContent);
  });

  const pr = await buildPage("states/pr.html");
  suite("states/pr.html — a territory's government", () => {
    const section = pr.D.getElementById("state-government");
    check("headed as the territory's government, not local government",
      !!section && /Territorial government/.test(section.querySelector(".state-heading").textContent));
    const chips = [...pr.D.querySelectorAll(".state-parts a")].map((a) => a.textContent);
    check("its jump chip says what its heading says", chips.indexOf("Territorial government") !== -1 &&
      chips.indexOf("State government") === -1, chips.join(" | "));
    const text = section.textContent;
    check("a territory is never called 'the state'",
      /The territory has no lieutenant governor/.test(text) && !/The state has/.test(text), text.slice(0, 300));
    check("it says its legislature, attorney general and courts are not covered, not just 'not covered'",
      /Puerto Rico's legislature, attorney general and courts are not covered here/.test(text) &&
      !/Seats: not covered/.test(text));
  });
  suite("states/pr.html — the Resident Commissioner, and why no seat is on the 2026 ballot", () => {
    const hero = pr.D.querySelector(".state-summary").textContent;
    check("the hero names the office and its next election, not zeros",
      /1 Resident Commissioner/.test(hero) && /Resident Commissioner: a 4-year term, next on the ballot in 2028/.test(hero) &&
      !/delegate/.test(hero) && !/0 seats in Congress/.test(hero) && !/0 challengers/.test(hero), hero);
    const delegation = pr.D.getElementById("delegation");
    check("the section is headed Resident Commissioner, and says why it has no race",
      /Resident Commissioner to the U\.S\. House/.test(delegation.querySelector(".state-heading").textContent) &&
      /last on the ballot in 2024 and is next in 2028/.test(delegation.textContent) &&
      !!delegation.querySelector('a[href="https://www.law.cornell.edu/uscode/text/48/891"]'),
      delegation.textContent.slice(0, 300));
    const chips = [...pr.D.querySelectorAll(".state-parts a")].map((a) => a.textContent);
    check("its jump chip says Resident Commissioner", chips.indexOf("Resident Commissioner") !== -1, chips.join(" | "));
  });
  const statesIndex = await buildPage("states/index.html");
  suite("states/index.html — Puerto Rico's row says the same as its page", () => {
    const row = statesIndex.D.querySelector('.state-row[data-state="PR"]');
    check("Resident Commissioner, next on the ballot in 2028",
      !!row && /1 Resident Commissioner/.test(row.textContent) && /next on the ballot in 2028/.test(row.textContent) &&
      !/challenger/.test(row.textContent), row && row.textContent);
  });
  const guTerr = await buildPage("states/gu.html");
  suite("states/gu.html — a territory with no secretary of state", () => {
    const text = guTerr.D.getElementById("state-government").textContent;
    check("says the territory has none", /The territory has no secretary of state/.test(text), text.slice(0, 300));
  });

  /* A photograph beside a statewide candidate and a justice, each with
   * whose it is (rules 87 and 91; STATEGOV-13). Drawn from a copy of
   * Georgia's own record with one photograph given, so the check holds
   * whoever the caches picture today. */
  const gaPhotos = await buildPage("states/ga.html");
  suite("state pages — candidates' and justices' photographs, each credited", () => {
    const { window } = gaPhotos;
    const sg = window.kycStateGov.states.GA;
    const item = sg.ballot2026.offices.governor;
    const list = item && item.candidates && item.candidates.candidates;
    const court = sg.court;
    if (!list || !court || !court.members || !court.members.length) {
      check("Georgia lists its governor's candidates and its justices", false);
      return;
    }
    const saved = JSON.stringify({ list, photos: court.photos || null });
    const printed = list.filter((p) => !p.writeIn);
    printed.forEach((p) => { delete p.photo; delete p.photoCredit; });
    printed[0].photo = "https://commons.example/thumb/250px-A.jpg";
    printed[0].photoCredit = { by: "Jane Photographer", licence: "CC BY-SA 4.0",
      licenceUrl: "https://creativecommons.org/licenses/by-sa/4.0", page: "https://commons.example/A",
      via: "Wikimedia Commons" };
    if (printed[1]) {
      printed[1].photo = "https://www.azcleanelections.gov/Custom/Picture/2427";
      printed[1].photoCredit = { by: "Arizona Citizens Clean Elections Commission",
        page: "https://www.azcleanelections.gov/Custom/CandidateList?location=" };
    }
    court.photos = {};
    court.photos[court.members[0]] = { photo: "https://court.example/j.jpg", page: "https://court.example/bio" };
    const box = window.document.createElement("div");
    box.innerHTML = window.KYC.stategov.render("GA", { links: false });
    // The governor's list: the card's first (the other offices' lists picture no one here).
    const block = box.querySelector(".gov-candidates");
    const rows = [...block.querySelectorAll(".gov-candidate-list:not(.gov-writein-list) .gov-candidate")];
    const first = rows.find((li) => li.querySelector(".gov-candidate-name").textContent === printed[0].name);
    check("a candidate's photograph is drawn beside their name",
      !!first && !!first.querySelector('img.gov-candidate-photo[src="' + printed[0].photo + '"]'));
    check("with whose it is: author, licence and Commons",
      !!first && /^Photo: Jane Photographer, CC BY-SA 4\.0, via Wikimedia Commons$/.test(
        first.querySelector(".gov-photo-credit").textContent), first && first.textContent);
    if (printed[1]) {
      const second = rows.find((li) => li.querySelector(".gov-candidate-name").textContent === printed[1].name);
      check("an official guide's photograph names the guide, linked to its page",
        !!second && !!second.querySelector('.gov-photo-credit a[href^="https://www.azcleanelections.gov/"]'));
    }
    const bare = rows.filter((li) => !li.querySelector("img"));
    check("a candidate without one keeps the column, an empty circle, and no credit",
      bare.every((li) => li.querySelector(".gov-photo-none") && !li.querySelector(".gov-photo-credit")),
      bare.length);
    check("no photograph is ever drawn without its credit",
      [...box.querySelectorAll("img.gov-photo")].every((img) =>
        img.parentNode.querySelector(".gov-photo-credit")));
    const member = box.querySelector(".gov-court-member");
    check("a justice's photograph is credited to the court, linked to the page it was read on",
      !!member && !!member.querySelector('img.gov-court-photo') &&
        member.querySelector(".gov-photo-credit").textContent ===
          "Photo: " + court.name + " of " + window.KYC.stateName("GA") &&
        member.querySelector(".gov-photo-credit a").getAttribute("href") === "https://court.example/bio");
    // One credit implementation for every photograph (rule 12, PR #135
    // review): the justices' line is KYC.photoCreditHtml's, as a
    // candidate's is.
    check("a justice's credit is KYC.photoCreditHtml's own line",
      !!member && member.querySelector(".gov-photo-credit").innerHTML ===
        window.KYC.photoCreditHtml({ by: court.name + " of " + window.KYC.stateName("GA"),
          page: "https://court.example/bio" }));
    check("the justice's name and title still read first",
      !!member && member.querySelector(".gov-court-name").textContent.indexOf(court.members[0]) === 0);
    // A photograph that fails to load takes its credit with it.
    window.document.body.appendChild(box);
    const img = box.querySelector("img.gov-candidate-photo");
    img.dispatchEvent(new window.Event("error"));
    check("a photograph that fails to load leaves the circle and no credit",
      !!first && !first.querySelector("img") && !!first.querySelector(".gov-photo-none") &&
        !first.querySelector(".gov-photo-credit"));
    box.remove();
    // Put the record back as it was for the suites after this one.
    const back = JSON.parse(saved);
    list.splice(0, list.length, ...back.list);
    if (back.photos) court.photos = back.photos; else delete court.photos;
  });

  const tx = await buildPage("states/tx.html");
  const al = await buildPage("states/al.html");
  const ut = await buildPage("states/ut.html");
  suite("state pages — each state's highest court", () => {
    const court = tx.window.kycStateGov.states.TX.court;
    const section = tx.D.getElementById("state-government");
    const names = [...section.querySelectorAll(".gov-court-name")].map((li) => li.textContent);
    check("the court's members are listed, as the court lists them",
      court.members.every((m) => names.some((n) => n.indexOf(m) === 0)), names.join("; "));
    check("the chief comes first, marked as chief", /Chief Justice$/.test(names[0]) &&
      names[0].indexOf(court.chief) === 0, names[0]);
    check("Texas's Court of Criminal Appeals is listed too, its head the presiding judge",
      /Court of Criminal Appeals/.test(section.textContent) && /Presiding Judge/.test(section.textContent));
    check("the roster links to the court's own page",
      !!section.querySelector('a[href^="https://www.txcourts.gov/"][rel~="noopener"]'));
    const alText = al.D.getElementById("state-government").textContent;
    check("a court whose roster cannot be read says why, and names no one",
      /members are not listed here/.test(alText) && !al.D.querySelector("#state-government .gov-court-member"));
    const utText = ut.D.getElementById("state-government").textContent;
    check("a court with no chief listed says so", /lists no chief justice/.test(utText), utText.slice(0, 120));
    check("no party is shown for a justice", ![...section.querySelectorAll(".gov-court-member")]
      .some((li) => li.querySelector('[class^="party-"]')));
    check("a court read this week does not claim to be read by hand or dated",
      !/read by hand|, dated /.test(section.textContent));
  });

  // STATEGOV-12: ten courts showed no one. Four sites refuse every automated
  // reader, so their rosters were read by hand (overrides.COURT_ROSTERS) and
  // the page must say so and when; Rhode Island's roster is a PDF with its
  // own date. Asked of the data, not of named people.
  const ny = await buildPage("states/ny.html");
  const ri = await buildPage("states/ri.html");
  suite("state pages — a court read by hand, or from a dated roster file", () => {
    const court = ny.window.kycStateGov.states.NY.court;
    const nyText = ny.D.getElementById("state-government").textContent;
    const nyNames = [...ny.D.querySelectorAll("#state-government .gov-court-name")].map((li) => li.textContent);
    check("New York's judges are listed, with the chief judge first",
      !!court && court.members.length > 0 && nyNames.length === court.members.length &&
      nyNames[0].indexOf(court.chief) === 0 && /Chief Judge$/.test(nyNames[0]), nyNames.join("; "));
    check("and the page says they were read by hand, on which day, and why",
      !!court.readOn && nyText.indexOf("read by hand on " + ny.window.KYC.dayMonthYear(court.readOn)) !== -1 &&
      /refuses automated reading/.test(nyText), nyText.slice(0, 400));
    const riCourt = ri.window.kycStateGov.states.RI.court;
    const riText = ri.D.getElementById("state-government").textContent;
    check("Rhode Island's roster carries the date the court's file gives it",
      !!riCourt.revised && riText.indexOf("dated " + ri.window.KYC.dayMonthYear(riCourt.revised)) !== -1 &&
      !/read by hand/.test(riText), riText.slice(0, 400));
    // Review of #98: a link that opens a PDF says so before a tap starts a
    // download; a page's link does not.
    const pdfLinks = [...ri.D.querySelectorAll("#state-government a")].filter((a) =>
      /\.pdf$/i.test(a.href) && /court's roster/.test(a.textContent));
    check("a roster that is a PDF is labelled (PDF)",
      pdfLinks.length > 0 && pdfLinks.every((a) => /\(PDF\)$/.test(a.textContent)),
      pdfLinks.map((a) => a.textContent).join(" | "));
    const txLinks = [...tx.D.querySelectorAll("#state-government a")].filter((a) => /court's roster/.test(a.textContent));
    check("a roster that is a page is not", txLinks.length > 0 && txLinks.every((a) => !/PDF/.test(a.textContent)),
      txLinks.map((a) => a.textContent).join(" | "));
    // The seat line is a sentence however the roster was read.
    const seatLines = [tx, ny, ri].map((p) => [...p.D.querySelectorAll("#state-government .gov-court + p.faint")]
      .map((el) => el.textContent.trim())).flat();
    check("each court's seat line ends as a sentence", seatLines.length >= 3 &&
      seatLines.every((t) => /\.$/.test(t)), seatLines.join(" | "));
    // The list of sources names each court with the day its roster was
    // read, and a hand read as one; a court with no read day is not dated.
    const txCourt = tx.window.kycStateGov.states.TX.court;
    const txSources = tx.D.querySelector("#state-government .gov-sources").textContent;
    const nySources = ny.D.querySelector("#state-government .gov-sources").textContent;
    check("the sources name the court and the day its roster was read",
      !!txCourt.read && txSources.indexOf(txCourt.name + ": the court's own roster (" +
        tx.window.KYC.dateWords(txCourt.read) + ")") !== -1 && !/read by hand/.test(txSources), txSources);
    check("and say a roster read by hand was",
      nySources.indexOf(court.name + ": the court's own roster (read by hand, " +
        ny.window.KYC.dateWords(court.readOn) + ")") !== -1, nySources);
  });

  const dc = await buildPage("states/dc.html");
  suite("states/dc.html — D.C. has no governor", () => {
    const section = dc.D.getElementById("state-government");
    check("the page says so rather than showing nothing", !!section && /mayor/.test(section.textContent));
    const note = dc.D.querySelector("#races .state-note");
    check("its ballot is never said to hold a governor or legislature",
      !!note && !/governor|legislature/.test(note.textContent) &&
      /mayor, attorney general, the D\.C\. Council/.test(note.textContent) &&
      !!note.querySelector('a[href="https://www.dcboe.org/elections/2026-elections"][rel~="noopener"]'),
      note && note.textContent);
    const chips = [...dc.D.querySelectorAll(".state-parts a")].map((a) => a.textContent);
    check("its jump chip says Local government, as its heading does",
      chips.indexOf("Local government") !== -1 && chips.indexOf("State government") === -1, chips.join(" | "));
  });
}

/* ========================================================= election night */

/* The day after: one Georgia race called, one going to a runoff, one the
 * results have not marked. The data is first put back as it stood before
 * the count, whatever the refresh has written since, and the statuses are
 * then set the way the pipeline sets them (results.resolve_race). */
function electionNight(window, meta) {
  rewindToCampaign(window);
  meta.election = Object.assign({}, meta.election, { resultsAsOf: "2026-11-05" });
  const byId = Object.fromEntries(window.legislatorsData.map((p) => [p.id, p]));
  const own = (p, r) => p && !p.contestLabel &&
    (p.isCandidate ? p.raceId : (p.contestRaceId || p.raceId)) === r.id;
  const nominees = (r) => [...new Set(r.incumbentIds.concat(r.candidateIds))]
    .map((id) => byId[id]).filter((p) => own(p, r) && p.raceStatus === "nominee");
  const races = window.kycRaces.filter((r) => r.state === "GA" && r.settled &&
    nominees(r).length >= 2);
  if (races.length < 3) {
    window.__night = {};
    return;
  }
  const [called, runoff, open] = races;
  const winner = nominees(called)[0];
  nominees(called).forEach((p) => { p.raceStatus = p === winner ? "elected" : "defeated"; });
  nominees(runoff).forEach((p, i) => { p.raceStatus = i < 2 ? "runoff" : "defeated"; });
  window.__night = { called, runoff, open, winner };
}

/* Louisiana's House seats before their November 3 open primary: the
 * Secretary of State's qualified list is the ballot. The fixture marks one
 * race that way whatever the data holds, since after the count the results
 * page decides instead. */
/* Rule 77: once a state certifies its November candidates, its list is the
 * ballot. Read from the data as built: Alaska's at-large seat showed two of
 * its four certified names and called the other two withdrawn; American
 * Samoa, with no primary, read "0 challengers on the ballot" over six. */
async function testCertifiedBallots() {
  const ak = await buildPage("states/ak.html");
  suite("states/ak.html — the Division of Elections' list is the November ballot", () => {
    check("no page errors", ak.errors.length === 0, ak.errors.join(" | "));
    const race = ak.window.kycRaces.find((r) => r.id === "H-AK-00-2026");
    const res = (race && race.results) || {};
    check("the at-large race is certified by the Division of Elections",
      /Alaska Division of Elections/.test(res.certifiedBy || "") && res.certifiedComplete,
      res.certifiedBy);
    const section = ak.D.getElementById("race-H-AK-00-2026");
    const shown = section ? [...section.querySelectorAll(".card")].filter((c) => !c.closest("details"))
      .map((c) => c.textContent).join(" ") + " " +
      [...section.querySelectorAll(".race-note")].map((n) => n.textContent).join(" ") : "";
    check("Hafner and McDermott, promoted when four finishers withdrew, are on it",
      /Hafner/.test(shown) && /McDermott/.test(shown), shown.slice(0, 400));
    const folded = section ? [...section.querySelectorAll("details .card")].map((c) => c.textContent).join(" ") : "";
    check("and neither is folded away as no longer running",
      !/Hafner|McDermott/.test(folded), folded.slice(0, 300));
    const note = section && [...section.querySelectorAll(".race-note")].find((n) =>
      /Also on the November ballot/.test(n.textContent));
    check("a name with no profile is credited to the list, with its party",
      !note || (/per the Alaska Division of Elections/.test(note.textContent) &&
        /\((Democrat|Democratic|Libertarian|Nonpartisan)\)/.test(note.textContent)),
      note && note.textContent);
  });

  const as = await buildPage("states/as.html");
  suite("states/as.html — a territory with no primary, after its list is read", () => {
    check("no page errors", as.errors.length === 0, as.errors.join(" | "));
    const strip = as.D.querySelector(".state-summary").textContent;
    const race = as.window.kycRaces.find((r) => r.id === "H-AS-00-2026");
    const res = (race && race.results) || {};
    check("the race is the Election Office's certified list",
      /American Samoa Election Office/.test(res.certifiedBy || ""), res.certifiedBy);
    check("its challengers are counted on the ballot, never 0 over six certified",
      !/\b0 challengers on the ballot/.test(strip) && /[1-9]\d* challengers? on the ballot/.test(strip),
      strip);
    // American Samoa holds no primary: its delegate, put on the ballot by
    // the certified list, read "Renominated", credited to "the state's"
    // list (rules 74 and 75).
    const delegate = as.window.legislatorsData.find((p) => as.window.KYC.seated(p) &&
      p.state === "AS" && p.raceStatusSource === "certified");
    const card = delegate ? as.window.KYC.cards.card(delegate) : "";
    const long = delegate ? as.window.KYC.raceStatusOf(delegate, "long") : null;
    check("the delegate reads 'On the November ballot', never 'Renominated'",
      !!delegate && /On the November ballot/.test(card) && !/Renominated/.test(card) &&
        long && long.label === "On the November ballot",
      card.replace(/\s+/g, " ").slice(0, 300));
    check("and the list is never 'the state's'",
      !!long && !/state's/.test(long.title) && /American Samoa Election Office/.test(long.title),
      long && long.title);
    // A name the list prints with no party is shown with none.
    const note = as.window.KYC.cards.unprofiledNote(race) || "";
    check("no party is added beside a name the list prints without one",
      !/\((Democratic|Republican|Independent)\)/.test(note), note.slice(0, 300));
  });

  // A territory with no primary whose ballot has not been read counts its
  // filers as filed, not as on the ballot (RACES-13).
  const mp = await buildPage("states/mp.html");
  suite("states/mp.html — no primary and no list read yet", () => {
    const info = mp.window.kycBuildMeta.states.MP || {};
    const strip = mp.D.querySelector(".state-summary").textContent;
    check("filers are counted as filed, and never as on the ballot",
      !info.challengersFiled || (new RegExp(info.challengersFiled + " challengers? filed; ballot list not checked")
        .test(strip) && !/challengers? on the ballot/.test(strip)), strip);
    check("the page writes Northern Mariana Islands' (rule 75)",
      !/Islands's/.test(mp.D.body.textContent) && /Northern Mariana Islands' /.test(mp.D.body.textContent));
  });
  const vi = await buildPage("states/vi.html");
  suite("states/vi.html — a plural name's possessive", () => {
    check("never Virgin Islands's", !/Islands's/.test(vi.D.body.textContent));
  });

  // PERSONA-09: a nominee with no profile carries their party.
  const withParty = (window) => window.kycRaces.find((r) => r.results &&
    Object.keys(r.results.otherParties || {}).length && r.state !== "LA");
  const probe = await buildPage("index.html");
  const partyRace = withParty(probe.window);
  probe.window.close();
  if (partyRace) {
    const page = await buildPage("states/" + partyRace.state.toLowerCase() + ".html");
    suite(`states/${partyRace.state.toLowerCase()}.html — names with no profile carry their party`, () => {
      const section = page.D.getElementById("race-" + partyRace.id);
      const text = section ? section.textContent : "";
      const parties = partyRace.results.otherParties;
      check("each is printed with the party the ballot gives it",
        Object.keys(parties).every((n) => text.indexOf(n + " (" + parties[n] + ")") !== -1),
        JSON.stringify(parties));
    });
  } else {
    suite("names with no profile carry their party", () => {
      check("a race with a nominee who has no profile and a known party", false);
    });
  }

  // PERSONA-20: the ballot's name, with the FEC's beneath it.
  const named = await buildPage("index.html");
  const renamed = named.window.legislatorsData.find((p) => p.fecName && p.fecName !== p.name);
  named.window.close();
  if (renamed) {
    const page = await buildPage("index.html", { hash: "#/profile/" + renamed.id });
    await settle();
    suite("index.html — a candidate the ballot names differently from the FEC", () => {
      const head = page.D.getElementById("profileModalName").textContent;
      const fec = page.D.getElementById("profileModalFecName");
      check("the dialog leads with the ballot's name", head === renamed.name, head);
      check("and says what the FEC files them under", !!fec && !fec.hidden &&
        fec.textContent === "Files with the FEC as " + renamed.fecName, fec && fec.textContent);
    });
  }

  // RACES-05, FRESHNESS-12: an empty seat says who left, when, and that no
  // special election has been called. Only while the old Congress sits: on
  // January 3 the seats are filled (rule 68; the January rehearsal failed
  // asking recordPhase(), which waits for a snapshot read after noon).
  const tx = await buildPage("states/tx.html");
  const vacancies = (tx.window.kycBuildMeta.states.TX || {}).vacancies || [];
  if (oldCongressSits(tx.window)) {
    suite("states/tx.html — an empty House seat says why", () => {
      check("the build records TX-23's vacancy", vacancies.some((v) => v.district === 23),
        JSON.stringify(vacancies));
      const notes = [...tx.D.querySelectorAll("#delegation .state-note")].map((n) => n.textContent).join(" ");
      check("the delegation says who left, when, and that no special election was called",
        vacancies.every((v) => notes.indexOf("District " + v.district + ": Vacant since ") !== -1 &&
          notes.indexOf("(" + v.name + " " + v.how + ")") !== -1) &&
          /no special election called as of [A-Z][a-z]{2,4}\.? \d{1,2}, \d{4}/.test(notes), notes);
    });
    const fl = await buildPage("districts/fl.html", { hash: "#/?d=20" });
    suite("districts/fl.html — the old map's empty FL-20", () => {
      check("no page errors", fl.errors.length === 0, fl.errors.join(" | "));
      const facts = [...fl.D.querySelectorAll(".district-fact")].filter((f) =>
        /Vacant since April 21, 2026 \(Sheila Cherfilus-McCormick resigned\); no special election called as of Oct\. 17, 2026/.test(f.textContent));
      const cards = [...fl.D.querySelectorAll(".plan-card")];
      check("the old map's FL-20 says who left and when, and only it does",
        facts.length === 1 && cards.length === 2 && cards[0].contains(facts[0]),
        facts.length + " notes on " + cards.length + " maps");
    });
  }
}

function qualifiedRace(window) {
  const byId = Object.fromEntries(window.legislatorsData.map((p) => [p.id, p]));
  const race = window.kycRaces.find((r) => r.state === "LA" && r.chamber === "House" &&
    r.candidateIds.length >= 2);
  if (!race) return;
  const people = race.candidateIds.map((id) => byId[id]).filter(Boolean);
  people.forEach((p, i) => {
    p.raceStatus = i === people.length - 1 ? "unlisted" : "qualified";
    p.raceStatusSource = "qualified";
  });
  race.settled = true;
  race.results = Object.assign({}, race.results, { fromQualifiedList: true,
    otherNominees: ["Kate Cotten"] });
  window.__qualified = { race, on: people.slice(0, -1), off: people[people.length - 1] };
}

async function testQualifiedBallot() {
  const { window, D, errors } = await buildPage("states/la.html", { data: qualifiedRace });
  const { race, on, off } = window.__qualified || {};
  suite("states/la.html — the November 3 open primary's qualified list", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("a Louisiana House race to read", !!race);
    if (!race) return;
    const section = D.getElementById("race-" + race.id);
    const head = section && section.querySelector(".race-head");
    // One badge says the open primary and its date (PR #94 review).
    const date = head && [...head.querySelectorAll(".badge")].find((b) => /Open primary/.test(b.textContent));
    check("its primary is not called held", !!date && !/held/.test(date.textContent) &&
      /Nov 3/.test(date.textContent), date && date.textContent);
    check("and says whose list the ballot is", /qualified candidates/.test(date.getAttribute("title")),
      date && date.getAttribute("title"));
    const card = (p) => section.querySelector('.card[data-id="' + p.id + '"]');
    check("a qualified candidate is on the Nov 3 ballot, not a nominee",
      on.every((p) => card(p) && /On the Nov 3 ballot/.test(card(p).textContent) &&
        !/Won the primary/.test(card(p).innerHTML)));
    check("a filer the list does not name is folded away",
      !!card(off) && !!card(off).closest("details"));
    const KYC = window.KYC;
    const spec = KYC.raceStatus("qualified", "long");
    check("the profile cites the Secretary of State, not a Wikipedia page",
      /Secretary of State/.test(spec.title) && !/Wikipedia/.test(spec.title), spec.title);
    const offBadge = card(off) && card(off).querySelector(".badge[title]");
    check("a filer not on the list is credited to the Secretary of State, not the results",
      !!offBadge && /Secretary of State's list/.test(offBadge.getAttribute("title")) &&
        !/primary results/.test(offBadge.getAttribute("title")),
      offBadge && offBadge.getAttribute("title"));
    const unprofiled = head && [...head.querySelectorAll(".badge")].find((b) => /no profile here/.test(b.textContent));
    check("names with no profile are credited to the list too",
      !!unprofiled && /Secretary of State's list/.test(unprofiled.getAttribute("title")) &&
        !/published results/.test(unprofiled.getAttribute("title")),
      unprofiled && unprofiled.getAttribute("title"));
  });
  const after = await buildPage("states/la.html", { now: "2026-11-05T09:00:00", data: qualifiedRace });
  suite("states/la.html — after the count, with no result read yet", () => {
    const { race: r2, on: still } = after.window.__qualified || {};
    const h2 = r2 && after.D.getElementById("race-" + r2.id).querySelector(".race-head");
    const held = h2 && [...h2.querySelectorAll(".badge")].find((b) => /Open primary/.test(b.textContent));
    check("the primary is held, and no result has been read yet",
      !!held && /Open primary held Nov 3/.test(held.textContent) && /no result has been read yet/.test(
        held.getAttribute("title")) && !/scheduled/.test(held.getAttribute("title")),
      held && held.getAttribute("title"));
    const c = still && still[0] && after.D.querySelector('.card[data-id="' + still[0].id + '"]');
    check("a qualified candidate reads Awaiting result", !!c && /Awaiting result/.test(c.textContent),
      c && c.textContent);
  });
}

async function testElectionNight() {
  const { window, D, errors } = await buildPage("states/ga.html",
    { now: "2026-11-05T09:00:00", data: electionNight });
  const KYC = window.KYC;
  const { called, runoff, open, winner } = window.__night || {};
  const section = (r) => r && D.getElementById("race-" + r.id);
  const head = (r) => ((section(r) || {}).querySelector || (() => null)).call(
    section(r), ".race-head");
  const cardOf = (r, p) => section(r) && section(r).querySelector(
    '.card[data-id="' + p.id + '"]');

  suite("states/ga.html — the day after the election", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("three Georgia races to read", !!(called && runoff && open),
      [called, runoff, open].map((r) => r && r.id).join(" "));
    if (!(called && runoff && open)) return;
    const h = head(called);
    check("a called race's header names its winner",
      !!h && h.textContent.indexOf("Won by " + winner.name) !== -1, h && h.textContent);
    const won = cardOf(called, winner);
    // Re-elected only for who held the seat by election; a winner seated in
    // a seat they did not hold, or an appointee, was elected.
    const reElected = !winner.isCandidate && !winner.raceRole && !winner.appointed;
    check("the winner's card says Elected (Re-elected for the member)",
      !!won && (reElected ? /Re-elected/ : /Elected/).test(won.textContent),
      won && won.textContent);
    const loser = called.incumbentIds.concat(called.candidateIds).map(KYC.byId)
      .find((p) => p && p.raceStatus === "defeated");
    const lost = loser && cardOf(called, loser);
    check("who lost is still in view, and says they lost in November",
      !!lost && !lost.closest("details") &&
        /Lost in November|Lost re-election/.test(lost.textContent),
      lost ? lost.textContent : "no loser");

    const r = head(runoff);
    check("a race in a runoff says so", !!r && /Going to a runoff/.test(r.textContent),
      r && r.textContent);
    const inIt = runoff.incumbentIds.concat(runoff.candidateIds).map(KYC.byId)
      .filter((p) => p && p.raceStatus === "runoff");
    check("both in the runoff read In the runoff", inIt.length === 2 &&
      inIt.every((p) => /In the runoff/.test((cardOf(runoff, p) || {}).textContent || "")));

    const o = head(open);
    const badge = o && [...o.querySelectorAll(".badge")].find((b) => /Awaiting result/.test(b.textContent));
    check("a race nobody has marked is awaiting a result, as of the last read",
      !!badge && /2026-11-05/.test(badge.getAttribute("title")), o && o.textContent);
    const waiting = open.incumbentIds.concat(open.candidateIds).map(KYC.byId)
      .filter((p) => p && p.raceStatus === "nominee");
    check("its nominees no longer read On the November ballot, as if nothing had happened",
      waiting.length >= 2 && waiting.every((p) => {
        const c = cardOf(open, p);
        return c && /Awaiting result/.test(c.textContent) &&
          !/On the November ballot|Renominated/.test(c.textContent);
      }));
    const lineHolder = waiting[0];
    lineHolder.ballotLine = "Speak The Truth";
    const hover = (KYC.cards.raceBadge(lineHolder).match(/title="([^"]*)"/) || [])[1] || "";
    delete lineHolder.ballotLine;
    check("a nominee on another line still says when the results were last read",
      /Speak The Truth line/.test(hover) && /2026-11-05/.test(hover) && /had not marked/.test(hover),
      hover);
    check("Won by appears once per called race, and nowhere else",
      D.querySelectorAll(".race-head").length > 0 &&
        [...D.querySelectorAll(".race-head")].filter((x) => /Won by/.test(x.textContent)).length === 1);
    // The December badge follows the race (rule 63; PR #94 review): gone
    // from a race decided on November 3, without its "if" on a race the
    // results send to a runoff, and conditional only where nothing is marked.
    check("a race decided on Nov 3 carries no December runoff badge",
      !!h && !/Runoff Dec/.test(h.textContent), h && h.textContent);
    check("a race in a runoff says the runoff's date without 'if no majority'",
      !!r && /Runoff Dec 1/.test(r.textContent) && !/if no majority/.test(r.textContent), r && r.textContent);
    check("an unmarked race keeps the conditional badge", !!o && /Runoff Dec 1 if no majority/.test(o.textContent),
      o && o.textContent);

    won.click();
    const status = D.getElementById("profileModalStatus");
    check("the winner's profile says so",
      !!status && /(Re-)?[Ee]lected in November/.test(status.textContent),
      status && status.textContent);
    D.querySelector("#profileModal .modal-footer [data-close]").click();
  });

  const december = await buildPage("states/ga.html", { now: "2026-12-05T09:00:00", data: electionNight });
  suite("states/ga.html after December 1 — the runoff is in the past tense", () => {
    const dates = december.D.querySelector("#voting .vote-dates");
    check("the key date says what the date was, not what will happen on it",
      !!dates && /December 1, 2026/.test(dates.textContent) && /The date set for a runoff/.test(dates.textContent) &&
        !/meet in a runoff on this date/.test(dates.textContent), dates && dates.textContent);
    const heads = [...december.D.querySelectorAll(".race-head")].map((x) => x.textContent).join(" ");
    check("no race head still says 'Runoff Dec 1 if no majority'",
      heads.length > 0 && !/if no majority/.test(heads) && /Runoff (held Dec 1|Dec 1, if one was needed)/.test(heads),
      heads.slice(0, 300));
  });

  const before = await buildPage("states/ga.html", { now: CAMPAIGN_NOW, data: electionNight });
  suite("states/ga.html — the same results before Election Day are not shown as results", () => {
    const text = [...before.D.querySelectorAll(".race-head")].map((x) => x.textContent).join(" ");
    check("no race header reads Won by, runoff or awaiting during the campaign",
      text.length > 0 && !/Won by|Going to a runoff|Awaiting result/.test(text));
  });

  /* The data as the refresh will write it once races are called: every
   * suite built at the campaign clock still finds its nominees. */
  const refreshed = await buildPage("index.html", { written: (win) => {
    win.legislatorsData.forEach((p) => {
      if (p.raceStatus === "nominee") p.raceStatus = p.isCandidate ? "defeated" : "elected";
    });
  } });
  suite("index.html — November results in the data, campaign clock on the page", () => {
    const people = refreshed.window.legislatorsData;
    check("no page errors", refreshed.errors.length === 0, refreshed.errors.join(" | "));
    check("the page sees them as nominees, as they stood before the count",
      people.some((p) => p.raceStatus === "nominee") &&
        !people.some((p) => NOVEMBER_RESULTS[p.raceStatus]));
  });

  // The partisan map's Senate-2026 label read a senator who lost in
  // November as "running" while the panel said "Lost re-election".
  const map = await buildPage("map.html", { now: "2026-11-05T09:00:00", data: (w) => {
    rewindToCampaign(w);
    const up = w.legislatorsData.filter((p) => !p.isCandidate && /Senate/.test(p.chamber) &&
      p.seatUp2026 && p.raceStatus === "nominee" && !p.contestLabel);
    w.__senators = { lost: up[0], won: up[1], waiting: up[2] };
    if (up[0]) up[0].raceStatus = "defeated";
    if (up[1]) up[1].raceStatus = "elected";
  } });
  suite("map.html — the 2026 Senate map after the election", () => {
    const { lost, won, waiting } = map.window.__senators || {};
    map.D.querySelector('[data-mode="senate2026"]').click();
    const label = (p) => (map.D.querySelector('#usMap [data-state="' + p.state + '"]') ||
      { getAttribute: () => "" }).getAttribute("aria-label") || "";
    check("three senators to read", !!(lost && won && waiting));
    if (!(lost && won && waiting)) return;
    check("a senator who lost in November is not 'running'",
      /lost re-election/.test(label(lost)) && !/running/.test(label(lost)), label(lost));
    check("a senator who won reads re-elected", /re-elected/.test(label(won)), label(won));
    check("an uncalled race reads awaiting result, not renominated",
      /awaiting result/.test(label(waiting)) && !/renominated/.test(label(waiting)), label(waiting));
  });
}

/* The grid's search and its controls, as the audit of 2026-10-17 found
 * them (GRID-03 to GRID-23, TECH-03, FEDERAL-02/03, RACES-18). */
const typeInto = (window, D, words) => {
  const input = D.getElementById("searchInput");
  input.value = words;
  input.dispatchEvent(new window.Event("input"));
};

function loadOfficials(window) {
  ["federal.js", "judiciary/index.js", "stategov.js"].forEach((file) => {
    window.eval(fs.readFileSync(path.join(SITE, "data", ...file.split("/")), "utf8"));
  });
}

async function testSearchAndFilters() {
  const { window, D, errors } = await buildPage("index.html");
  await settle(50);
  const KYC = window.KYC;
  const data = window.legislatorsData;
  const races = window.kycRaces;
  const cards = () => [...D.querySelectorAll("#results .card")].map((c) => KYC.byId(c.getAttribute("data-id")));
  const label = () => D.getElementById("resultsLabel").textContent.replace(/\s+/g, " ");
  const matching = (q) => data.filter((p) => KYC.matchesQuery(p, q));
  const raceOf = (p) => (p.isCandidate ? p.raceId : p.contestRaceId || p.raceId);

  suite("search — a state's name is that state (GRID-03)", () => {
    const names = KYC.meta().states;
    // Every state whose name another state's contains: Kansas/Arkansas,
    // Virginia/West Virginia.
    const pairs = Object.keys(names).filter((a) => Object.keys(names).some((b) => b !== a &&
      new RegExp("\\w" + names[a].name.toLowerCase()).test(names[b].name.toLowerCase())));
    check("the case exists to test", pairs.length > 0, pairs.join(" "));
    pairs.forEach((code) => {
      const found = matching(names[code].name.toLowerCase());
      const elsewhere = found.filter((p) => p.state !== code &&
        KYC.queryScore(p, names[code].name.toLowerCase()) !== 2);
      check(`"${names[code].name}" finds ${code}'s people and no other state's`,
        found.some((p) => p.state === code) && !elsewhere.length,
        elsewhere.slice(0, 3).map((p) => p.name + " " + p.state).join(", "));
      check(`and every one of ${code}'s`, data.filter((p) => p.state === code)
        .every((p) => KYC.matchesQuery(p, names[code].name)));
    });
    const blank = { id: "x", name: "Pat Example", state: "AR", quality: {},
      platforms: "Arkansas Agriculture", officeLabel: "House • AR-1" };
    check("a word matches where a word starts, never inside one",
      !KYC.matchesQuery(blank, "kansas") && KYC.matchesQuery(blank, "agri") &&
        !KYC.matchesQuery(blank, "griculture"));
    check("a postal code alone is the state", matching("dc").every((p) => p.state === "DC") &&
      matching("dc").length > 0);
  });

  suite("search — a district is its race (GRID-04)", () => {
    // A state with a district 3 and districts 30-39: "TX-3" read as a prefix.
    const tens = races.find((r) => r.chamber === "House" && r.district === 3 &&
      races.some((o) => o.state === r.state && o.district >= 30));
    check("the case exists to test", !!tens);
    const code = tens.state;
    const name = KYC.stateName(code);
    const forms = [`${code}-3`, `${code.toLowerCase()}3`, `${code} 3`, `${name} 3`,
      `${name} district 3`, `${name.toLowerCase()} 3rd district`, `${name}'s 3rd`, `${code}-03`];
    forms.forEach((q) => {
      const found = matching(q.toLowerCase());
      const wrong = found.filter((p) => !(raceOf(p) === tens.id || p.heldRaceId === tens.id ||
        tens.incumbentIds.concat(tens.candidateIds).indexOf(p.id) !== -1 ||
        (KYC.seated(p) && p.state === code && p.districtNum === 3)));
      check(`"${q}" is ${code}-3's race and nothing else`, found.length > 0 && !wrong.length,
        wrong.slice(0, 4).map((p) => p.officeLabel).join(", "));
    });
    const people = new Set(tens.incumbentIds.concat(tens.candidateIds));
    check("everyone in the race is found", [...people].every((id) =>
      !KYC.byId(id) || KYC.matchesQuery(KYC.byId(id), `${code}-3`)));
    const atLarge = races.find((r) => r.chamber === "House" && r.district === 0 &&
      !races.some((o) => o.state === r.state && o.district > 0));
    check("'at large' and the seat's '1' find an at-large race",
      !!atLarge && ["at large", "AL", "1", "district 1"].every((rest) => {
        const found = matching(`${atLarge.state} ${rest}`.toLowerCase());
        return found.length > 0 && found.every((p) => p.state === atLarge.state);
      }));
    typeInto(window, D, `${name} district 3`);
  });
  await settle(250);
  suite("search — typed in the box, a district names itself in the results line", () => {
    check("the cards are the race's", cards().length > 0 && cards().every((p) => p.state ===
      races.find((r) => r.chamber === "House" && r.district === 3 &&
        races.some((o) => o.state === r.state && o.district >= 30)).state), label());
    check("and the line says which seat it read", /\(([A-Z]{2})-3\)/.test(label()), label());
  });

  // A sitting member another profile's text names: "Mike Johnson" put a
  // challenger whose text said "challenging Mike Johnson" first.
  const named = data.find((p) => KYC.seated(p) && p.name.split(" ").length === 2 &&
    data.some((o) => o !== p && KYC.queryScore(o, p.name.toLowerCase()) === 3));
  if (named) typeInto(window, D, named.name);
  await settle(250);
  suite("search — the person whose name was typed comes first (GRID-05)", () => {
    check("the case exists to test", !!named);
    const shown = cards();
    check(`'${named && named.name}' opens on them`, shown[0] === named,
      shown.slice(0, 3).map((p) => p.name).join(", "));
    const later = [...D.querySelectorAll("#results .card")].find((c) =>
      KYC.queryScore(KYC.byId(c.getAttribute("data-id")), named.name.toLowerCase()) === 3);
    check("a card found only in its text says where", !!later &&
      !!later.querySelector(".card-note") && later.querySelector(".card-note").textContent.length > 4,
      later && later.textContent);
    const pat = { id: "a", name: "Pat Example", quality: {}, state: "OH", officeLabel: "House • OH-1" };
    const sam = { id: "b", name: "Sam Other", quality: {}, state: "OH", officeLabel: "House • OH-2",
      platforms: "Running against Pat Example" };
    check("an exact name ranks above a mention", KYC.queryScore(pat, "pat example") <
      KYC.queryScore(sam, "pat example"));
    check("a name token ranks above an office", KYC.queryScore(pat, "example") <
      KYC.queryScore(sam, "house"));
    if (oldCongressSits(window) && KYC.byId("O000172")) {
      check("an evidenced alias finds its member ('AOC')", KYC.queryScore(KYC.byId("O000172"), "aoc") === 0);
    }
  });

  // GRID-09: Escape and the field's own clear reset the query.
  const input = D.getElementById("searchInput");
  input.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  await settle(50);
  suite("search — Escape clears the query, not only the box (GRID-09)", () => {
    check("the box is empty", input.value === "");
    check("the address has no query", !/[?&]q=/.test(window.location.hash), window.location.hash);
    check("and the line names none", !/“/.test(label()), label());
  });
  typeInto(window, D, "warren");
  await settle(250);
  input.value = "";
  input.dispatchEvent(new window.Event("search"));
  await settle(50);
  suite("search — the field's clear button does too", () => {
    check("the address has no query", !/[?&]q=/.test(window.location.hash), window.location.hash);
  });

  // GRID-14: the line says what is hidden, and shows it.
  suite("the results line says who is hidden (GRID-14)", () => {
    check("it says how many out of the race are hidden", /out of the race .*hidden/.test(label()), label());
    const toggle = D.querySelector("#resultsLabel [data-out-toggle]");
    check("with the switch beside it", !!toggle && /Show them/.test(toggle.textContent));
    const before = cards().length;
    toggle.click();
    check("which shows them", /eliminated=show/.test(window.location.hash) && cards().length >= before,
      window.location.hash);
    D.querySelector("#resultsLabel [data-out-toggle]").click();
    check("and hides them again", !/eliminated=show/.test(window.location.hash));
  });

  // GRID-11, GRID-22: what is on, removable; "Both chambers"; Clear all.
  D.getElementById("stateSelect").value = "TX";
  D.getElementById("stateSelect").dispatchEvent(new window.Event("change"));
  D.querySelector('[data-group="chamber"][data-value="Senate"]').click();
  suite("filters that are on are shown, and each comes off (GRID-11, GRID-22)", () => {
    check("the chamber chip is 'Both chambers'",
      D.querySelector('[data-group="chamber"][data-value="all"]').textContent.trim() === "Both chambers");
    check("the Filters button counts the state", /\(2 on\)/.test(D.getElementById("filtersCount").textContent),
      D.getElementById("filtersCount").textContent);
    const bar = D.getElementById("activeFilters");
    check("the state and the chamber are chips", !bar.hidden && /Texas/.test(bar.textContent) &&
      /Senate/.test(bar.textContent), bar.textContent);
    check("the results line names the state", /in Texas/.test(label()), label());
    bar.querySelector('[data-clear="state"]').click();
    check("one comes off", D.getElementById("stateSelect").value === "all" &&
      /chamber=Senate/.test(window.location.hash) && !/state=/.test(window.location.hash));
    D.querySelector('[data-group="party"][data-value="Democrat"]').click();
    D.getElementById("activeFilters").querySelector('[data-clear="all"]').click();
    check("Clear all clears everything", window.location.hash === "#/" &&
      D.getElementById("activeFilters").hidden, window.location.hash);
  });

  // GRID-12: the sidebar's split is page text, and the chip says its count.
  suite("the challenger counts say what they count (GRID-12)", () => {
    const split = D.getElementById("challengerSplit");
    check("the sidebar's split is visible text", !!split && !split.hidden &&
      /have a profile here/.test(split.textContent), split && split.textContent);
    D.querySelector('[data-group="role"][data-value="candidate"]').click();
    check("the Challengers chip's line says what the sidebar adds",
      /sidebar/.test(label()), label());
    D.querySelector('[data-group="role"][data-value="candidate"]').click();
  });

  // GRID-13: "No challenger on the ballot" is the race heads' own test.
  suite("'No challenger on the ballot' is what the race heads say (GRID-13)", () => {
    D.querySelector('[data-group="election"][data-value="unchallenged"]').click();
    const shown = cards();
    const heads = new Set(races.filter((r) => r.settled && !r.contested && r.results).map((r) => r.id));
    check("every card is in such a race", shown.every((p) =>
      heads.has(p.isCandidate ? p.raceId : p.heldRaceId || p.raceId)), shown.length);
    D.getElementById("raceViewToggle").click();
    const sections = [...D.querySelectorAll("#results section.race")];
    check("and each race's head says so", sections.every((s) => /No challenger on the ballot/.test(
      s.querySelector(".race-head").textContent)), sections.length);
    D.getElementById("raceViewToggle").click();
    D.querySelector('[data-group="election"][data-value="unchallenged"]').click();
  });

  // GRID-20: by surname, by state name, ages printed.
  suite("the sorts (GRID-20)", () => {
    const shown = cards();
    const states = shown.filter((p) => String(p.chamber).indexOf("Senate") !== -1)
      .map((p) => KYC.stateName(p.state));
    check("the default order is by state name", states.every((s, i) => i === 0 ||
      states[i - 1].localeCompare(s) <= 0), states.slice(0, 4).join(", "));
    // Within a seat by surname, as the races say they list people.
    const seat = (p) => [p.chamber, p.state, KYC.districtOrder(p)].join("|");
    const unsorted = shown.filter((p, i) => i > 0 && seat(shown[i - 1]) === seat(p) &&
      String(shown[i - 1].surname || shown[i - 1].name).localeCompare(String(p.surname || p.name)) > 0);
    check("and within a seat by surname", shown.length > 10 && !unsorted.length,
      unsorted.slice(0, 3).map((p) => p.name).join(", "));
    D.getElementById("sortButton").click();
    D.querySelector('#sortPanel [data-sort="age-desc"]').click();
    const first = D.querySelector("#results .card");
    check("an age sort prints the age", /Age \d+/.test(first.textContent), first.textContent);
    // The cards come a window at a time: draw them all. Bounded: a click
    // that draws nothing (a card that throws) leaves the button in place,
    // and an unbounded loop would spin until the job is killed.
    for (let i = 0; D.getElementById("gridMore") && i < 1000; i++) D.getElementById("gridMore").click();
    check("every window of cards draws", !D.getElementById("gridMore"));
    const divider = D.querySelector("#results .grid-divider");
    const unknown = cards().some((p) => KYC.ageOf(p) === null);
    check("and says where the unknown ages start", !unknown ||
      (!!divider && /No birthdate on record \([\d,]+\)/.test(divider.textContent)));
    const after = [...D.querySelectorAll("#results .grid-divider ~ .card")]
      .map((c) => KYC.byId(c.getAttribute("data-id")));
    check("everyone after it has no age, and everyone before it one", !divider ||
      (after.length > 0 && after.every((p) => KYC.ageOf(p) === null) &&
        cards().length - after.length === cards().filter((p) => KYC.ageOf(p) !== null).length));
    D.getElementById("sortButton").click();
    D.querySelector('#sortPanel [data-sort="region"]').click();
  });

  // GRID-23, RACES-18, GRID-14: the races view.
  D.getElementById("raceViewToggle").click();
  suite("the races view (GRID-23, VISUALS-36, RACES-18)", () => {
    const heads = [...D.querySelectorAll("#results .race-state-heading")].map((h) => h.textContent);
    check("races are under their state's name, in order", heads.length > 40 &&
      heads.every((h, i) => i === 0 || heads[i - 1].localeCompare(h) <= 0), heads.slice(0, 4).join(", "));
    check("with a jump list", D.querySelectorAll("#raceJump option").length === heads.length + 1);
    const ids = [...D.querySelectorAll("#results section.race")].map((s) => s.id.replace(/^race-/, ""));
    const order = ids.map((id) => races.find((r) => r.id === id));
    check("Senate before House within a state, then by district", order.every((r, i) => {
      const p = order[i - 1];
      if (!p || p.state !== r.state) return true;
      return (p.chamber === "Senate" ? 0 : 1) < (r.chamber === "Senate" ? 0 : 1) ||
        (p.chamber === r.chamber && (p.district || 0) <= (r.district || 0));
    }));
    check("the line counts races, not cards", /Showing [\d,]+ races?/.test(label()), label());
    const folded = D.querySelector("#results details[data-out-race]");
    check("the people out of a race are drawn when their list opens", !!folded &&
      folded.querySelectorAll(".card").length === 0);
    folded.open = true;
    folded.dispatchEvent(new window.Event("toggle"));
    check("and are there once it is", folded.querySelectorAll(".card").length > 0);
    if (oldCongressSits(window)) {
      const moved = races.filter((r) => r.holderMoved);
      check("a moved holder exists to test", moved.length > 0);
      moved.forEach((race) => {
        const section = D.getElementById("race-" + race.id);
        if (!section) return;
        const line = section.querySelector(".race-held");
        const holder = race.incumbentIds.map(KYC.byId).find((p) => p && p.contestRaceId &&
          p.contestRaceId !== race.id);
        check(`${race.id}: its holder is a line, not a card among those running`, !holder ||
          (!!line && line.textContent.indexOf(holder.name) !== -1 &&
            !section.querySelector(`.card-grid .card[data-id="${holder.id}"]`)),
          line && line.textContent);
      });
    }
  });
  D.getElementById("raceViewToggle").click();

  // GRID-19: the key says every word a card shows.
  suite("the key to the labels (GRID-19)", () => {
    const legend = D.querySelector("#statusLegend details.status-legend");
    check("it is there, collapsed", !!legend && !legend.open);
    const said = new Set([...legend.querySelectorAll("dt .badge")].map((b) => b.textContent));
    const seen = new Set();
    D.getElementById("raceViewToggle").click();
    [...D.querySelectorAll("#results details")].forEach((d) => {
      d.open = true;
      d.dispatchEvent(new window.Event("toggle"));
    });
    [...D.querySelectorAll("#results .card .badge")].forEach((b) => {
      if (!b.classList.contains("other-office")) seen.add(b.textContent.replace(/ – .* line$/, ""));
    });
    D.getElementById("raceViewToggle").click();
    const missing = [...seen].filter((t) => !said.has(t) &&
      !/^(Running for|Ran for|Running in|Seat up in) /.test(t));
    check("every status word on a card is in the key", seen.size > 3 && !missing.length,
      missing.join(" | "));
  });

  // GRID-07, FEDERAL-03, GRID-08: other officials, never profiles.
  loadOfficials(window);
  const federal = window.kycFederal;
  const office = federal.offices.find((o) => o.holder && o.holder.name);
  const surname = office.holder.name.replace(/,? (Jr|Sr|II|III)\.?$/, "").split(" ").pop();
  typeInto(window, D, surname);
  await settle(250);
  suite("search — officials who are not candidates (GRID-07, FEDERAL-03)", () => {
    const box = D.getElementById("officialResults");
    const link = box && [...box.querySelectorAll("a")].find((a) =>
      a.getAttribute("href") === "federal/index.html#/official/" + encodeURIComponent(office.holder.id));
    check(`'${surname}' lists the ${office.office} apart, linking their dialog`, !box.hidden && !!link,
      box.textContent);
    check("never as a profile card (rule 27)", !box.querySelector(".card") &&
      !cards().some((p) => p.id === office.holder.id));
  });
  const justice = federal.supremeCourt.members[0];
  typeInto(window, D, justice.name.split(",")[0].split(" ").pop());
  await settle(250);
  suite("search — a justice, and a governor by their state", () => {
    const box = D.getElementById("officialResults");
    check("a justice's surname lists them", [...box.querySelectorAll("a")].some((a) =>
      /#\/official\//.test(a.getAttribute("href")) && a.textContent === justice.name), box.textContent);
  });
  const govState = Object.keys(window.kycStateGov.states).find((c) =>
    (window.kycStateGov.states[c].governor || {}).name);
  typeInto(window, D, KYC.stateName(govState));
  await settle(250);
  suite("search — a state's name lists its governor", () => {
    const box = D.getElementById("officialResults");
    check("linked to the state's page", [...box.querySelectorAll("a")].some((a) =>
      a.textContent === window.kycStateGov.states[govState].governor.name &&
      /states\/[a-z]{2}\.html#state-government$/.test(a.getAttribute("href"))), box.textContent);
  });
  // The statewide candidates (rule 91): found by name, listed for the
  // office they are a candidate for, linked to the state page; never a
  // profile card, and never matched to one by name (rule 25).
  const gaGov = window.kycStateGov.states.GA.ballot2026.offices.governor.candidates.candidates
    .find((c) => !c.writeIn && !c.holder);
  typeInto(window, D, gaGov.name);
  await settle(250);
  suite("search — a candidate for governor", () => {
    const box = D.getElementById("officialResults");
    const row = [...box.querySelectorAll(".official-row")].find((li) =>
      li.querySelector(".official-name").textContent === gaGov.name);
    check("is listed as a candidate for the office, linked to the state's page",
      !!row && row.querySelector(".official-role").textContent ===
        "Candidate for Governor, Georgia (Nov 3, 2026 ballot)" &&
        row.querySelector("a").getAttribute("href") === "states/ga.html#state-government",
      box.textContent);
    check("never as a profile card", !box.querySelector(".card, a[href*='#/profile/']"));
    // A candidate who holds no office is not an "official" (PR #109 review).
    const list = row && row.closest(".official-list");
    const head = list && list.previousElementSibling && list.previousElementSibling.previousElementSibling;
    check("under its own heading, not 'Other officials'",
      !!head && head.textContent === "Statewide candidates on the Nov 3, 2026 ballot", head && head.textContent);
  });
  // The list's own form of a name finds the candidate, who is shown by the
  // name the page writes ("Lombardo, Joseph" is Joseph Lombardo).
  const nvRow = window.kycStateGov.states.NV.ballot2026.offices.governor.candidates.candidates
    .find((c) => c.printed && !c.holder);
  if (nvRow) typeInto(window, D, nvRow.printed);
  await settle(250);
  // After Election Day the search says it in the past tense, as the state
  // page does; it names no winner (PR #109 review).
  const voted = await buildPage("index.html", { now: "2026-11-05T09:00:00" });
  await settle(50);
  loadOfficials(voted.window);
  typeInto(voted.window, voted.D, gaGov.name);
  await settle(250);
  suite("search after Election Day — a candidate who was on the ballot", () => {
    const box = voted.D.getElementById("officialResults");
    const row = [...box.querySelectorAll(".official-row")].find((li) =>
      li.querySelector(".official-name").textContent === gaGov.name);
    check("in the past tense",
      !!row && row.querySelector(".official-role").textContent ===
        "Was a candidate for Governor, Georgia, on the Nov 3, 2026 ballot", box.textContent);
    check("under a heading in the past tense",
      /Statewide candidates who were on the Nov 3, 2026 ballot/.test(box.textContent));
  });
  suite("search — a candidate by the list's own form of the name", () => {
    if (!nvRow) { check("no list writes a name another way", true); return; }
    const box = D.getElementById("officialResults");
    check("is found, and shown first name first",
      [...box.querySelectorAll(".official-name")].some((a) => a.textContent === nvRow.name) &&
        box.textContent.indexOf(nvRow.printed + " —") === -1, box.textContent);
  });
  const departed = (KYC.meta().departed || [])[0];
  if (departed) typeInto(window, D, departed.name);
  await settle(250);
  suite("search — a member who left this Congress (GRID-08)", () => {
    if (!departed) { check("no departed members to test (a new Congress)", true); return; }
    const box = D.getElementById("officialResults");
    // The day is the record's end of the term, said as the record's: it can
    // be a day from the House Clerk's (a death recorded the day before).
    check("is found, with the day the record ends the term, said as the record's",
      /Former members of this Congress/.test(box.textContent) &&
      box.textContent.indexOf(departed.name) !== -1 &&
      /congress-legislators ends the term on/.test(box.textContent) &&
      !/Left Congress on/.test(box.textContent), box.textContent);
    check("never a double period after a name that ends in one", !/\.\./.test(box.textContent),
      box.textContent);
    check("nothing on the page says nothing matches", D.getElementById("noResults").hidden ||
      cards().length > 0);
    check("and is never a profile, so never counted", !data.some((p) => p.id === departed.id));
    const holder = departed.holder && box.querySelector(`a[href="#/profile/${encodeURIComponent(departed.holder.id)}"]`);
    check("who holds the seat now is linked, when someone does", !departed.holder ||
      (!!holder && !!KYC.byId(departed.holder.id)));
  });

  // A full name that names someone lists no namesakes beside them: "Mark
  // Kelly" listed a governor, a lieutenant governor and six judges named
  // Kelly under the senator's card, "Lindsey Graham" two judges above her.
  const lastWord = (n) => KYC.searchFold(n).replace(/,/g, " ").split(" ")
    .filter((w) => w && !/^(jr|sr|ii|iii|iv)$/.test(w)).pop();
  const judges = window.kycJudgesIndex;
  const judgeSurnames = new Set(judges.map((r) => lastWord(r[1])));
  const namesake = data.find((p) => KYC.seated(p) && p.name.split(" ").length === 2 &&
    judgeSurnames.has(lastWord(p.name)) &&
    !judges.some((r) => { const s = KYC.nameScore(p.name, [r[1], r[4]]); return s >= 0 && s < 2; }));
  const officialRows = () => [...D.querySelectorAll("#officialResults .official-name")]
    .map((a) => a.textContent);
  if (namesake) typeInto(window, D, namesake.name);
  await settle(250);
  suite("search — a full name lists no namesakes", () => {
    check("the case exists to test", !!namesake);
    check(`'${namesake && namesake.name}' lists no official who only shares the surname`,
      cards().some((p) => p === namesake) &&
        !officialRows().some((n) => KYC.nameScore(namesake.name, [n]) === 2),
      officialRows().join(", "));
  });
  const goneNamesake = (KYC.meta().departed || []).find((row) =>
    judgeSurnames.has(lastWord(row.name)) && !data.some((p) => {
      const s = KYC.queryScore(p, row.name.toLowerCase());
      return s >= 0 && s <= 1;
    }));
  if (goneNamesake) typeInto(window, D, goneNamesake.name);
  await settle(250);
  suite("search — a former member named in full comes before any namesake", () => {
    if (!goneNamesake) { check("no former member shares a judge's surname (nothing to test)", true); return; }
    check(`'${goneNamesake.name}' is listed first, and alone`, officialRows()[0] === goneNamesake.name &&
      !officialRows().some((n) => KYC.nameScore(goneNamesake.name, [n]) === 2), officialRows().join(", "));
  });
  const judgeSurname = lastWord(judges[0][1]);
  typeInto(window, D, "Zyxwq " + judgeSurname);
  await settle(250);
  suite("search — namesakes alone are said to be namesakes", () => {
    const box = D.getElementById("officialResults");
    check("the surname's judges are listed", !box.hidden && officialRows().length > 0, officialRows().join(", "));
    check("and the box says nobody answers to the whole name", /Nobody below answers to/.test(box.textContent),
      box.textContent.slice(0, 200));
  });
  // Officials only: the empty state's "Nothing matches" sat under them.
  const loneOfficial = federal.offices.map((o) => o.holder).find((h) => h && h.name &&
    !data.some((p) => KYC.queryScore(p, h.name.toLowerCase()) >= 0));
  if (loneOfficial) typeInto(window, D, loneOfficial.name);
  await settle(250);
  suite("search — officials found, and no profile", () => {
    check("the case exists to test", !!loneOfficial);
    check("no 'Nothing matches' under them", D.getElementById("noResults").hidden &&
      !D.getElementById("officialResults").hidden, label());
    check("the line says where they are", /listed elsewhere on the site/.test(label()), label());
    check("and no key to labels on cards there are none of", D.getElementById("statusLegend").hidden);
  });
  // Everyone found is out of the race: "No profiles matching" hid them.
  const outOnly = data.find((p) => !KYC.seated(p) && KYC.cards.offBallot(p) &&
    p.name.split(" ").length >= 2 &&
    data.every((o) => KYC.queryScore(o, p.name.toLowerCase()) < 0 || (!KYC.seated(o) && KYC.cards.offBallot(o))));
  if (outOnly) typeInto(window, D, outOnly.name);
  await settle(250);
  suite("search — a match out of the race is said to be hidden, with the switch", () => {
    check("the case exists to test", !!outOnly);
    const toggle = D.querySelector("#resultsLabel [data-out-toggle]");
    check("the line counts them and offers to show them", /hidden/.test(label()) && !!toggle, label());
    check("and does not also say nothing matches", D.getElementById("noResults").hidden);
    if (toggle) toggle.click();
    check("the switch shows them", cards().some((p) => p === outOnly), label());
    const back = D.querySelector("#resultsLabel [data-out-toggle]");
    if (back) back.click();
  });
  // A seat that does not exist is said not to, and a lone seat is at large.
  const states = KYC.meta().states;
  const many = Object.keys(states).find((c) => (states[c].house || 0) > 2 && !states[c].territory);
  const lone = Object.keys(states).find((c) => states[c].house === 1 && !states[c].territory);
  typeInto(window, D, `${many} ${states[many].house + 1}`);
  await settle(250);
  suite("search — a seat that does not exist", () => {
    check(`'${many} ${states[many].house + 1}' says ${many} has no such district`,
      /has no district/.test(label()) && label().indexOf(`(${many}-`) === -1, label());
  });
  typeInto(window, D, `${many} at large`);
  await settle(250);
  suite("search — no at-large seat in a state of districts", () => {
    check("says so", /has no at-large seat/.test(label()) && label().indexOf(`(${many}-AL)`) === -1, label());
  });
  typeInto(window, D, `${lone} 1`);
  await settle(250);
  suite("search — a lone seat's '1' is named as the at-large seat", () => {
    check(`'${lone} 1' reads (${lone}-AL)`, label().indexOf(`(${lone}-AL)`) !== -1 &&
      label().indexOf(`(${lone}-1)`) === -1, label());
  });
  // A leadership post finds who holds it (GRID-05's "Speaker").
  const leader = data.find((p) => KYC.seated(p) && (p.leadership || []).length);
  if (leader) typeInto(window, D, leader.leadership[0]);
  await settle(250);
  suite("search — a leadership post finds who holds it", () => {
    if (!leader) { check("no leadership posts recorded yet (a new Congress)", true); return; }
    check(`'${leader.leadership[0]}' finds them`, cards().some((p) => p === leader), label());
  });
  // A territory's former member is titled as the place titles them.
  const meta = KYC.meta();
  const realDeparted = meta.departed;
  meta.departed = (realDeparted || []).concat([{ id: "test-pr", name: "Zyxw Commissioner",
    chamber: "House", state: "PR", district: 0, left: "2026-01-05", holder: null }]);
  typeInto(window, D, "Zyxw Commissioner");
  await settle(250);
  suite("search — a territory's former member, in its own words (rule 75)", () => {
    const text = D.getElementById("officialResults").textContent;
    check("Puerto Rico's is a Resident Commissioner, never a Representative",
      /Former Resident Commissioner from Puerto Rico/.test(text) && !/Representative, PR/.test(text), text);
    check("and a seat nobody holds is never 'vacant' (rule 19)", !/vacant/i.test(text) &&
      /seats nobody there now/.test(text), text);
  });
  meta.departed = realDeparted;
  // An old link's value with no chip is labelled in words.
  window.location.hash = "#/?election=contested";
  await settle(250);
  suite("search — an old election=contested link reads in words", () => {
    const bar = D.getElementById("activeFilters").textContent;
    check("never the raw value", !/\bcontested\b/.test(bar) && /besides the holder/.test(bar), bar);
  });
  window.location.hash = "#/";
  await settle(250);
  typeInto(window, D, "");
  await settle(250);
  check("no errors", errors.length === 0, errors.join("\n"));

  // The officials' data is fetched only when a query is typed, from the
  // stamped URL the page names (rule 76).
  const lazy = await buildPage("index.html");
  await settle(50);
  const template = lazy.D.getElementById("onDemandData");
  const before = lazy.D.querySelectorAll("head script[src]").length;
  typeInto(lazy.window, lazy.D, "zzz");
  await settle(250);
  suite("search — the officials' data comes on demand", () => {
    // The officials' files and the search's places and bodies (rule 97);
    // the votes' are the profile dialog's (testVotes).
    const srcs = [...template.content.querySelectorAll("script")].map((s) => s.getAttribute("src"))
      .filter((s) => !/^data\/(votes|people)\//.test(s));
    check("the page names each file with its version", srcs.length === 5 &&
      srcs.every((s) => /^data\/[a-z/]+\.js\?v=[0-9a-f]{10}$/.test(s)), srcs.join(" "));
    const added = [...lazy.D.querySelectorAll("head script[src]")].slice(before).map((s) => s.getAttribute("src"));
    const typed = srcs.filter((s) => !/^data\/measures\.js/.test(s));
    check("and fetches them when a query is typed", typed.length === 4 &&
      typed.every((s) => added.indexOf(s) !== -1), added.join(" "));
    // The ballot questions are fetched only when a query names one.
    check("but not the ballot questions, which no query named",
      !added.some((s) => /^data\/measures\.js/.test(s)), added.join(" "));
  });
  typeInto(lazy.window, lazy.D, "Proposition 1");
  await settle(250);
  suite("search — the ballot questions come when a query names one (rule 97)", () => {
    const added = [...lazy.D.querySelectorAll("head script[src]")].slice(before).map((s) => s.getAttribute("src"));
    check("data/measures.js is fetched, from its stamped address",
      added.some((s) => /^data\/measures\.js\?v=[0-9a-f]{10}$/.test(s)), added.join(" "));
  });

  // TECH-03: a query typed before the profiles arrived is kept.
  const early = await buildPage("index.html", {
    data: (w) => { w.document.getElementById("searchInput").value = "Warren"; },
  });
  await settle(50);
  suite("search — a query typed while the page loads is kept (TECH-03)", () => {
    check("the box still holds it", early.D.getElementById("searchInput").value === "Warren");
    check("and the grid is searched for it", /q=warren/.test(early.window.location.hash) &&
      /“Warren”/.test(early.D.getElementById("resultsLabel").textContent),
      early.window.location.hash);
  });
}

/* The search answers what a reader types about government (rule 97):
 * an office and who holds it, a place, a body, a court, a ballot question,
 * each a link to the page about it, grouped by kind, above the cards. The
 * owner asked for it on 2026-10-19; "governor" found only challengers whose
 * text mentioned the word (GRID-07). */
function loadAnswers(window) {
  loadOfficials(window);
  ["search.js", "measures.js"].forEach((file) => {
    window.eval(fs.readFileSync(path.join(SITE, "data", file), "utf8"));
  });
}

async function testSearchAnswers() {
  const { window, D, errors } = await buildPage("index.html");
  await settle(50);
  const KYC = window.KYC;
  loadAnswers(window);
  const gov = window.kycStateGov.states;
  const fed = window.kycFederal;
  const index = window.kycSearch;
  const box = () => D.getElementById("searchAnswers");
  const text = () => box().textContent.replace(/\s+/g, " ");
  const hrefs = () => [...box().querySelectorAll("a")].map((a) => a.getAttribute("href"));
  const label = () => D.getElementById("resultsLabel").textContent.replace(/\s+/g, " ");
  const cards = () => [...D.querySelectorAll("#results .card")].map((c) => KYC.byId(c.getAttribute("data-id")));
  const ask = async (q) => { typeInto(window, D, q); await settle(200); };
  // Nobody outside Congress is a profile (rule 27): a profile link in the
  // answers names a sitting member, and no card is drawn in them.
  const onlyMembers = () => !box().querySelector(".card") && hrefs().filter((h) => /^#\/profile\//.test(h))
    .every((h) => KYC.seated(KYC.byId(decodeURIComponent(h.split("/").pop()))));
  const named = (off) => KYC.answers.namedHolder(off);

  await ask("governor");
  suite("search answers — 'governor' alone lists every state's, compactly", () => {
    const want = Object.keys(gov).filter((c) => named(gov[c].governor));
    const links = hrefs().filter((h) => /^states\/[a-z]{2}\.html#state-government$/.test(h));
    check("shown, under Offices", !box().hidden && /^Offices/.test(box().querySelector(".answer-group-title").textContent));
    check("a row for each state whose governor its page names, each linked to it",
      want.length > 40 && links.length === want.length && want.every((c) =>
        text().indexOf(gov[c].governor.name) !== -1), `${links.length} of ${want.length}`);
    check("as a compact list", !!box().querySelector(".answer-compact"));
    check("never as profiles", onlyMembers());
  });

  const ohio = gov.OH;
  await ask("Ohio governor");
  suite("search answers — 'Ohio governor' is Ohio's, with its 2026 race", () => {
    check("names the holder, linked to Ohio's page", named(ohio.governor) &&
      text().indexOf(ohio.governor.name) !== -1 && hrefs().indexOf("states/oh.html#state-government") !== -1,
      text().slice(0, 200));
    check("and no other state's governor", !Object.keys(gov).some((c) => c !== "OH" &&
      named(gov[c].governor) && text().indexOf(gov[c].governor.name) !== -1));
    const item = ohio.ballot2026.offices.governor;
    const printed = ((item.candidates || {}).candidates || []).filter((c) => !c.writeIn);
    check("the race is labelled as the election office's list",
      !item.up || (/on the Nov 3, 2026 ballot/.test(text()) && /lists them/.test(text()) &&
        printed.every((c) => text().indexOf(c.name) !== -1)), text().slice(0, 400));
  });
  const ohioText = text();
  await ask("governor of Ohio");
  suite("search answers — 'governor of Ohio' reads the same", () => {
    check("the same answer", text() === ohioText);
  });

  await ask("Texas AG");
  suite("search answers — 'Texas AG' is Texas's attorney general", () => {
    check("named, linked to Texas's page", !named(gov.TX.ag) ||
      (text().indexOf(gov.TX.ag.name) !== -1 && hrefs().indexOf("states/tx.html#state-government") !== -1),
      text().slice(0, 200));
    check("never the U.S. Attorney General when a state is named",
      !hrefs().some((h) => /federal\/index\.html#\/official\//.test(h)));
  });

  await ask("attorney general");
  suite("search answers — 'attorney general' alone", () => {
    const office = fed.offices.find((o) => o.key === "justice");
    check("the U.S. Attorney General first, in their own dialog, never a profile",
      !office.holder || hrefs()[0] === "federal/index.html#/official/" + encodeURIComponent(office.holder.id),
      hrefs()[0]);
    check("then every state's, compactly", !!box().querySelector(".answer-compact"));
  });

  await ask("Calif. governor");
  suite("search answers — an abbreviation a reader writes ('Calif.')", () => {
    check("is California", !named(gov.CA.governor) || text().indexOf(gov.CA.governor.name) !== -1,
      text().slice(0, 120));
  });

  // A misspelling is not fuzzily matched to anyone (rule 3).
  await ask("Govenor of Ohio");
  suite("search answers — a misspelling names nobody", () => {
    check("no answer", box().hidden, text().slice(0, 120));
    check("and no official named for it", D.getElementById("officialResults").hidden ||
      D.getElementById("officialResults").textContent.indexOf(ohio.governor.name) === -1);
  });
  await ask("Texsa AG");
  suite("search answers — a misspelled state is no state", () => {
    check("nobody's attorney general", !Object.keys(gov).some((c) => named(gov[c].ag) &&
      text().indexOf(gov[c].ag.name) !== -1), text().slice(0, 160));
  });

  const speaker = KYC.people().find((p) => KYC.seated(p) && (p.leadership || []).indexOf("Speaker of the House") !== -1);
  await ask("Speaker");
  suite("search answers — 'Speaker' is the Speaker of the House", () => {
    if (!speaker) { check("no Speaker recorded in this Congress yet (rule 68)", box().hidden || true); return; }
    check("linked to their profile", hrefs().indexOf("#/profile/" + encodeURIComponent(speaker.id)) !== -1 &&
      /Speaker of the House:/.test(text()), text());
    check("only members of Congress are profiles", onlyMembers());
  });

  const labor = fed.offices.find((o) => o.key === "labor");
  for (const q of ["Secretary of Labor", "labor secretary"]) {
    await ask(q);
    suite(`search answers — '${q}'`, () => {
      check("the office's holder, in the federal page's dialog", !labor.holder ||
        hrefs().indexOf("federal/index.html#/official/" + encodeURIComponent(labor.holder.id)) !== -1,
        hrefs().join(" "));
      check("never a profile (rule 27)", !hrefs().some((h) => /^#\/profile\//.test(h)));
    });
  }
  await ask("labor");
  suite("search answers — a department's word alone is not its secretary", () => {
    check("no office answered", box().hidden || !/Secretary of Labor/.test(text()), text().slice(0, 120));
  });

  await ask("Cabinet");
  suite("search answers — 'Cabinet' lists every office and its holder", () => {
    const held = fed.offices.filter((o) => o.holder && o.holder.id);
    check("each holder linked to their dialog", held.length > 10 && held.every((o) =>
      hrefs().indexOf("federal/index.html#/official/" + encodeURIComponent(o.holder.id)) !== -1));
  });

  await ask("senators");
  suite("search answers — 'senators' alone explains, and points to the Senate view and the lookup", () => {
    check("the Senate view", hrefs().indexOf("#/?view=senate") !== -1, hrefs().join(" "));
    check("Find who represents you", !!box().querySelector("[data-findrep-reveal]"));
  });
  await ask("Ohio congressman");
  suite("search — 'Ohio congressman' is who sits for Ohio in the House (rule 27)", () => {
    check("the grid says so", /Ohio’s sitting House members/.test(label()), label());
    check("and shows Ohio's sitting House members only, no challenger", cards().length > 0 &&
      cards().every((p) => p.state === "OH" && KYC.seated(p) && /House/.test(p.chamber)),
      cards().filter((p) => !KYC.seated(p)).map((p) => p.name).join(", "));
  });
  for (const q of ["Ohio delegation", "Ohio members of Congress"]) {
    await ask(q);
    suite(`search — '${q}' asks who represents Ohio, not who is running (rule 27)`, () => {
      check("the grid says so", /Ohio’s sitting members of Congress/.test(label()), label());
      check("both chambers' sitting members, and nobody else", cards().length > 0 &&
        cards().every((p) => p.state === "OH" && KYC.seated(p)) &&
        cards().some((p) => p.chamber === "Senate") && cards().some((p) => /House/.test(p.chamber)),
        cards().filter((p) => !KYC.seated(p)).map((p) => p.name).join(", "));
    });
  }
  // A seat's title is read off the query, never added to a profile's text:
  // "Con", typed on the way to a name, ranked every sitting member by the
  // word "Congressman" (PR #124 review).
  await ask("Con");
  suite("search — a title typed in part does not rank every member", () => {
    check("the first cards are named Con...", cards().length > 0 &&
      cards().slice(0, 3).every((p) => /(^|[^a-z])con/i.test(KYC.searchFold(p.name))),
      cards().slice(0, 3).map((p) => p.name).join(", "));
    // Ranked by office (2) only where the office's own words start so:
    // Connecticut's members do.
    const byTitle = KYC.people().filter((p) => KYC.seated(p) && p.state !== "CT" &&
      !/(^|[^a-z])con/.test(KYC.searchFold([p.name, p.officeLabel, p.contestLabel, p.party, p.district]
        .concat(p.aliases || [], p.leadership || []).join(" "))) &&
      KYC.queryScore(p, "Con") === 2);
    check("and no sitting member is ranked by a title's letters", byTitle.length === 0,
      byTitle.slice(0, 3).map((p) => p.name).join(", "));
  });
  const houseSmiths = KYC.people().filter((p) => KYC.seated(p) && /House/.test(p.chamber) &&
    / smith$/.test(KYC.searchFold(p.name)));
  await ask("Congresswoman Smith");
  suite("search — 'Congresswoman Smith' is the sitting House members named Smith first", () => {
    if (!houseSmiths.length) { check("no sitting House member named Smith (nothing to test)", true); return; }
    check("each of them, before anyone else", cards().slice(0, houseSmiths.length).every((p) =>
      houseSmiths.indexOf(p) !== -1), cards().slice(0, houseSmiths.length + 1).map((p) => p.name).join(", "));
  });
  const senator = KYC.people().find((p) => KYC.seated(p) && p.chamber === "Senate" &&
    KYC.people().filter((o) => o.name.split(" ").pop() === p.name.split(" ").pop()).length === 1);
  await ask("Senator " + senator.name.split(" ").pop());
  suite("search — 'Senator <surname>' finds the senator by the seat's title", () => {
    check(`'Senator ${senator.name.split(" ").pop()}' finds ${senator.name}`, cards()[0] === senator,
      cards().slice(0, 3).map((p) => p && p.name).join(", "));
  });

  await ask("state senator 43215");
  suite("search answers — a state legislator and a ZIP code ask the lookup", () => {
    check("a button asks the ZIP code", !!box().querySelector('[data-findrep-zip="43215"]'), text());
  });
  await ask("Texas House");
  suite("search answers — 'Texas House' is the legislature's chamber", () => {
    check("linked to its lower chamber's map", hrefs().indexOf("legislature/tx.html#/?chamber=lower") !== -1,
      hrefs().join(" "));
    check("named as the legislature names it", text().indexOf("Texas House of Representatives") !== -1);
    check("and the cards stay Texas's seats in the U.S. House", cards().length > 0 &&
      cards().every((p) => p.state === "TX") && /U\.S\. House are the cards below/.test(text()));
  });
  await ask("General Court");
  suite("search answers — a legislature by the name its constitution gives it (rule 75)", () => {
    check("Massachusetts's and New Hampshire's", hrefs().indexOf("legislature/ma.html") !== -1 &&
      hrefs().indexOf("legislature/nh.html") !== -1 && /Massachusetts General Court/.test(text()));
  });

  await ask("Fifth Circuit");
  suite("search answers — 'Fifth Circuit' is its court's page", () => {
    check("courts/ca5.html", hrefs().indexOf("courts/ca5.html") !== -1, hrefs().join(" "));
    check("under Courts", /Courts/.test(box().querySelector(".answer-group-title").textContent));
  });
  for (const [q, id] of [["S.D.N.Y.", "ny-s"], ["Eastern District of Texas", "tx-e"], ["5th Cir.", "ca5"],
      ["D.C. Circuit", "cadc"], ["D. Mass.", "ma"]]) {
    await ask(q);
    suite(`search answers — '${q}'`, () => {
      check(`is courts/${id}.html, alone`, hrefs().filter((h) => /^courts\//.test(h)).join(" ") === `courts/${id}.html`,
        hrefs().join(" "));
    });
  }
  await ask("DNC");
  suite("search answers — 'DNC' is not North Carolina's district courts", () => {
    check("no court", !hrefs().some((h) => /^courts\//.test(h)), hrefs().join(" "));
  });
  await ask("Supreme Court");
  suite("search answers — 'Supreme Court' is the nine, in their dialogs", () => {
    const members = fed.supremeCourt.members;
    check("the court's page and each justice", hrefs().indexOf("courts/scotus.html") !== -1 &&
      members.every((j) => hrefs().indexOf("federal/index.html#/official/" + encodeURIComponent(j.id)) !== -1));
  });
  await ask("Ohio Supreme Court");
  suite("search answers — a state's highest court is on its state page", () => {
    check("Ohio's", !ohio.court || (hrefs().indexOf("states/oh.html#state-government") !== -1 &&
      text().indexOf(ohio.court.name) !== -1), text());
  });
  await ask("judge");
  suite("search answers — 'judge' alone is too broad to list", () => {
    check("narrower searches are suggested", /Narrower searches/.test(text()) &&
      hrefs().indexOf("#/?q=Fifth%20Circuit") !== -1, text().slice(0, 200));
    check("and no judge is listed", !hrefs().some((h) => /#\/official\/|^courts\//.test(h)), hrefs().join(" "));
    check("the federal page's judge search is linked", hrefs().indexOf("federal/index.html#courts") !== -1);
  });

  const travis = (index.counties.TX || []).find((c) => c[1] === "Travis County");
  await ask("Travis County");
  suite("search answers — 'Travis County' is its county page", () => {
    check("the case exists to test", !!travis);
    check("linked by its Census code", hrefs().indexOf("counties/tx.html#/?county=" + travis[0]) !== -1,
      hrefs().join(" "));
  });
  await ask("Cook County, IL");
  suite("search answers — a county and its state", () => {
    const cook = index.counties.IL.find((c) => c[1] === "Cook County");
    check("Illinois's only", hrefs().join(" ") === "counties/il.html#/?county=" + cook[0], hrefs().join(" "));
  });
  await ask("Texas counties");
  suite("search answers — a state's counties are its county page, not Texas County", () => {
    check("counties/tx.html", hrefs().indexOf("counties/tx.html") !== -1 &&
      !hrefs().some((h) => /county=/.test(h)), hrefs().join(" "));
  });
  await ask("mayor");
  suite("search answers — a local office says this site names none, and where to look", () => {
    check("said, and the county pages linked", /names no local officials/.test(text()) &&
      hrefs().indexOf("counties/index.html") !== -1, text().slice(0, 200));
  });
  await ask("DC mayor");
  suite("search answers — a local office where there is no county page", () => {
    check("the District's own page, never the county pages", hrefs().join(" ") === "states/dc.html" &&
      /no county page for the District of Columbia/.test(text()), hrefs().join(" ") + " | " + text());
  });

  const committee = (index.committees || []).find((c) => / Armed Services$/.test(c[1]));
  await ask("Armed Services");
  suite("search answers — 'Armed Services' is the committees' rows in the Congress guide", () => {
    if (!committee) { check("no rosters yet (a new Congress, rule 68)", true); return; }
    const guide = fs.readFileSync(path.join(SITE, "government", "congress.html"), "utf8");
    const links = hrefs().filter((h) => /^government\/congress\.html#committee-/.test(h));
    check("each chamber's", links.length === 2, links.join(" "));
    check("each row is on the guide's page", links.every((h) => guide.indexOf(`id="${h.split("#")[1]}"`) !== -1));
    check("its leaders are members' profiles", onlyMembers());
  });
  await ask("education");
  suite("search answers — one word of a committee's longer name is not the committee", () => {
    check("no committee", !hrefs().some((h) => /committee-/.test(h)), hrefs().join(" "));
  });

  const tribe = Object.keys(index.tribes || {}).map((c) => [c, (index.tribes[c] || [])
    .find((t) => t[0] === "Cherokee Nation")]).find((x) => x[1]);
  await ask("Cherokee Nation");
  suite("search answers — a tribal government, on its state's list", () => {
    check("the case exists to test", !!tribe);
    check("linked to the tribal page's list for its state",
      hrefs().indexOf(`government/tribal.html#/?state=${tribe[0]}&mode=tribes`) !== -1, hrefs().join(" "));
  });

  await ask("Proposition 50");
  suite("search answers — 'Proposition 50' names no 2026 question", () => {
    check("said so, under Ballot questions", /Ballot questions/.test(text()) &&
      /No statewide question on a Nov 3, 2026 ballot/.test(text()), text());
    check("and never Proposition 5", !hrefs().some((h) => /#measure-/.test(h)), hrefs().join(" "));
  });
  const measures = window.kycMeasures;
  const moAt = ((measures.MO || {}).measures || []).findIndex((m) => m.designation === "Amendment 3");
  await ask("Missouri Amendment 3");
  suite("search answers — 'Missouri Amendment 3' is the question on Missouri's page", () => {
    if (moAt < 0) { check("Missouri lists no Amendment 3 (nothing to test)", true); return; }
    check("linked to the question itself", hrefs().join(" ") === `states/mo.html#measure-MO-${moAt}`,
      hrefs().join(" "));
  });
  await ask("Amendment 3");
  suite("search answers — a question's number is matched whole", () => {
    // North Carolina's "...MAXIMUM INCOME TAX RATE OF 3.5%" is not Amendment 3.
    const wrong = Object.keys(measures).some((c) => (measures[c].measures || []).some((m, i) =>
      /3\.5/.test(m.designation) && hrefs().indexOf(`states/${c.toLowerCase()}.html#measure-${c}-${i}`) !== -1));
    check("no question numbered otherwise", !wrong && hrefs().length > 0, hrefs().join(" "));
  });

  // The empty grid says where the answers are.
  await ask("Federal Circuit");
  suite("search answers — the answers only: no 'Nothing matches' under them", () => {
    if (cards().length) { check("profiles also match (nothing to test)", true); return; }
    check("the line says the answers are below", /offices, places and bodies found below/.test(label()), label());
    check("and the empty state is hidden", D.getElementById("noResults").hidden);
  });
  await ask("");
  suite("search answers — an empty box answers nothing", () => {
    check("hidden", box().hidden);
  });

  /* PR #124 review: what the answers say must be what the site read. */
  // A court whose roster could not be read is said so, and nothing about
  // its members or its chief (rules 19 and 57).
  for (const code of Object.keys(gov).filter((c) => gov[c].court && gov[c].court.unreadable)) {
    const name = KYC.stateName(code);
    for (const q of [`${name} Supreme Court`, `${name} chief justice`]) {
      await ask(q);
      suite(`search answers — '${q}': a court whose roster was not read`, () => {
        check("says why, as its state page does", text().indexOf(gov[code].court.unreadable) !== -1 &&
          /members are not listed here/.test(text()), text().slice(0, 300));
        check("and claims no count of members and no chief",
          !/members? listed by the court|names no chief|lists no chief/.test(text()), text().slice(0, 300));
      });
    }
  }
  // A place whose list of ballot questions was never found answers no
  // question, by name or as a list (rule 19).
  const noListRead = Object.keys(measures).filter((c) => measures[c] && measures[c].has !== true &&
    measures[c].has !== false);
  for (const code of noListRead) {
    for (const q of [`${KYC.stateName(code)} Question 1`, `${KYC.stateName(code)} ballot questions`]) {
      await ask(q);
      suite(`search answers — '${q}': no official list was found`, () => {
        check("says so", /has not found an official list/.test(text()) && /does not say there are none/.test(text()),
          text().slice(0, 300));
        check("and never that no question is called that", !/No statewide question/.test(text()), text().slice(0, 300));
      });
    }
  }
  await ask("Proposition 50");
  suite("search answers — a question named nowhere: the places with no list read are named", () => {
    check("each of them", !noListRead.length || noListRead.every((c) => text().indexOf(KYC.stateName(c)) !== -1) &&
      /has not found an official list for/.test(text()), text());
    const inList = (/Questions called a proposition are on the ballot in ([^.]*)\./.exec(text()) || [])[1] || "";
    check("and the states with such questions are a list with 'and'", !/,/.test(inList) || / and [A-Z]/.test(inList),
      inList);
  });

  // Every state's officer: an acting officer, or an office called
  // otherwise, carries the title its page gives them, and a new office
  // first elected on Nov 3 is listed and counted (rule 73).
  for (const [key, q] of [["governor", "governor"], ["lt", "lieutenant governor"], ["ag", "attorney general"],
      ["sos", "secretary of state"]]) {
    await ask(q);
    const rowsText = [...box().querySelectorAll(".answer-compact .answer-row")].map((li) => li.textContent);
    const listed = text();
    suite(`search answers — '${q}': each state's officer as its page titles them`, () => {
      const acting = Object.keys(gov).filter((c) => named(gov[c][key]) && /Acting|Interim/.test(gov[c][key].title || ""));
      check("an acting officer is never shown as the holder", acting.every((c) =>
        rowsText.some((t) => t.indexOf(gov[c][key].name + " (" + gov[c][key].title + ")") !== -1)),
        acting.map((c) => c + " " + gov[c][key].name).join(", "));
      const fresh = Object.keys(gov).filter((c) => gov[c][key] && gov[c][key].none &&
        ((gov[c].ballot2026 || {}).offices || {})[key] && gov[c].ballot2026.offices[key].up);
      check("a new office no one holds yet is listed", fresh.every((c) =>
        rowsText.some((t) => t.indexOf(KYC.stateName(c) + ":") === 0 && /no one holds this office yet/.test(t))));
      const up = Object.keys(gov).filter((c) => ((gov[c].ballot2026 || {}).offices || {})[key] &&
        gov[c].ballot2026.offices[key].up).length;
      check("the count on the ballot is the races' count", listed.indexOf(up + " of these offices") !== -1 ||
        (up === 1 && listed.indexOf("1 of these offices") !== -1), `${up}: ${listed.slice(0, 260)}`);
    });
    await ask(q + " races");
    suite(`search answers — '${q} races' counts as '${q}' does`, () => {
      const races = [...box().querySelectorAll(".answer-compact .answer-row")].length;
      check("one count", listed.indexOf(races + " of these offices") !== -1, `${races}: ${listed.slice(0, 260)}`);
    });
  }
  for (const code of Object.keys(gov).filter((c) => gov[c].lt && gov[c].lt.none &&
      ((gov[c].ballot2026 || {}).offices || {}).lt && gov[c].ballot2026.offices.lt.up)) {
    const q = KYC.stateName(code) + " lieutenant governor race";
    await ask(q);
    suite(`search answers — '${q}': a new office on the ballot for the first time`, () => {
      const item = gov[code].ballot2026.offices.lt;
      const printed = ((item.candidates || {}).candidates || []).filter((c) => !c.writeIn);
      check("no one holds it yet, and it is on the ballot", /No one holds this office yet/.test(text()) &&
        /on the Nov 3, 2026 ballot/.test(text()) && !/has no such office/.test(text()), text().slice(0, 300));
      check("with the candidates its list names", printed.every((c) => text().indexOf(c.name) !== -1));
      check("and a list that is not the state's own says so", !item.candidates || !item.candidates.notStateList ||
        /Not the state’s own list/.test(text()));
    });
  }
  // An office a place does not have, or this site does not list, is not
  // titled as though the page held it (rule 75).
  await ask("DC governor");
  suite("search answers — 'DC governor': the District has no governor", () => {
    check("said in the District's own words", /The District of Columbia has an elected mayor/.test(text()), text());
    check("and no row is titled as its governor", !/Governor, District of Columbia/.test(text()));
  });
  const missing = Object.keys(gov).filter((c) => !gov[c].ag)[0];
  if (missing) {
    await ask(KYC.stateName(missing) + " attorney general");
    suite(`search answers — '${KYC.stateName(missing)} attorney general': an office this site does not list`, () => {
      check("is said not to be listed", /lists no attorney general for/.test(text()), text());
      check("and is not titled as an office its page holds",
        !/^Attorney General,/.test(box().querySelector(".answer-row").textContent), text());
    });
  }
  // A state legislature's leaders: the chamber's page, and why no name.
  await ask("Texas House speaker");
  suite("search answers — 'Texas House speaker': the chamber, and that no leader is named here", () => {
    check("the Texas House's page", hrefs().indexOf("legislature/tx.html#/?chamber=lower") !== -1, hrefs().join(" "));
    check("says this site names no state legislative leaders", /does not name the leaders of state legislatures/.test(text()));
    check("said after the chamber is named",
      text().indexOf("Texas House of Representatives") < text().indexOf("does not name"), text().slice(0, 200));
  });
  // A court's row is named before the note about it.
  await ask("Fifth Circuit");
  suite("search answers — the circuit's note follows its row", () => {
    check("row, then note", text().indexOf("Fifth Circuit") < text().indexOf("It hears appeals"), text().slice(0, 200));
  });
  // A court the answers name is not also answered by a judge's surname.
  await ask("Ohio Supreme Court");
  suite("search answers — 'Ohio Supreme Court' answers once, not also with a judge named Court", () => {
    const officials = D.getElementById("officialResults");
    check("no surname-only namesake beside the court", officials.hidden ||
      !/shares the surname alone/.test(officials.textContent), officials.textContent.slice(0, 200));
    check("and one sentence about what is found below", (label().match(/found below/g) || []).length <= 1, label());
  });
  // Local governments' websites: only where the Census gives one, checked
  // (rule 78).
  await ask("mayor");
  suite("search answers — a local office never says every government has a website", () => {
    check("worded as the county pages hold them", !/each with its own website|where its officials are named/.test(text()) &&
      /where the Census listing gives one/.test(text()), text());
  });
  // A state's local office is the state's, never a county named for it.
  for (const [q, code] of [["Texas county judge", "tx"], ["Ohio county commissioner", "oh"]]) {
    await ask(q);
    suite(`search answers — '${q}' is the state's local offices`, () => {
      check("its county page", hrefs().indexOf(`counties/${code}.html`) !== -1, hrefs().join(" "));
      check("and no county named for the state", !hrefs().some((h) => /county=/.test(h)), hrefs().join(" "));
    });
  }
  // Short names that are words: only in capitals, or with a cue.
  await ask("Doe");
  suite("search answers — 'Doe' is a surname, not the Department of Energy", () => {
    check("no office", box().hidden || !/Secretary of Energy/.test(text()), text().slice(0, 120));
  });
  await ask("DOE");
  suite("search answers — 'DOE' in capitals is the department", () => {
    const energy = fed.offices.find((o) => o.key === "energy");
    check("its secretary", !energy || !energy.holder || /Secretary of Energy/.test(text()), text().slice(0, 120));
  });
  // Only the capitals changed: the answers are drawn again (rule 97).
  await ask("in governor");
  await ask("IN governor");
  suite("search answers — 'in governor' then 'IN governor' is Indiana's", () => {
    check("Indiana's governor alone", !named(gov.IN.governor) || (text().indexOf(gov.IN.governor.name) !== -1 &&
      !box().querySelector(".answer-compact")), text().slice(0, 200));
    check("and the line quotes it as typed", /“IN governor”/.test(label()), label());
  });
  // A bare name no profile answers may be a tribe's or a county's.
  await ask("Cherokee");
  suite("search answers — 'Cherokee', where no profile answers it", () => {
    if (cards().length) { check("a profile answers it (nothing to test)", true); return; }
    check("the tribal governments of that name", tribe && hrefs().indexOf(`government/tribal.html#/?state=${tribe[0]}&mode=tribes`) !== -1,
      hrefs().join(" "));
  });
  check("no errors", errors.length === 0, errors.join("\n"));

  // From the day after the election, the race is in the past tense.
  const voted = await buildPage("index.html", { now: "2026-11-05T09:00:00" });
  await settle(50);
  loadAnswers(voted.window);
  typeInto(voted.window, voted.D, "Ohio governor");
  await settle(200);
  suite("search answers after Election Day — the race in the past tense", () => {
    const t = voted.D.getElementById("searchAnswers").textContent;
    check("was on the ballot", !ohio.ballot2026.offices.governor.up ||
      /was on the Nov 3, 2026 ballot/.test(t) && /Candidates who were on it/.test(t), t.slice(0, 300));
  });
  // Every note that counts the ballot is in the past tense too (rules 63, 84).
  for (const [q, past, now] of [["governor", /offices were on the Nov 3, 2026 ballot/, /offices are on/],
      ["governor races", /elected this office on Nov 3, 2026/, /elect this office/],
      ["Proposition 50", /was called/, /is called/]]) {
    typeInto(voted.window, voted.D, q);
    await settle(200);
    suite(`search answers after Election Day — '${q}' in the past tense`, () => {
      const t = voted.D.getElementById("searchAnswers").textContent;
      check("past", past.test(t) && !now.test(t), t.slice(0, 300));
    });
  }
  const someQuestion = Object.keys(measures).find((c) => measures[c].has === true && (measures[c].measures || []).length);
  if (someQuestion) {
    const m = measures[someQuestion].measures[0];
    typeInto(voted.window, voted.D, KYC.stateName(someQuestion) + " " + m.designation);
    await settle(200);
    suite("search answers after Election Day — a ballot question in the past tense", () => {
      const t = voted.D.getElementById("searchAnswers").textContent;
      check("as each election office listed them", /listed them/.test(t), t.slice(0, 300));
    });
  }

  // The state page addresses each question, as the answers link it.
  if (moAt >= 0) {
    const mo = await buildPage("states/mo.html");
    await settle(50);
    suite("a state page addresses each ballot question (rule 97)", () => {
      check(`#measure-MO-${moAt} is Amendment 3`, !!mo.D.getElementById(`measure-MO-${moAt}`) &&
        /Amendment 3/.test(mo.D.getElementById(`measure-MO-${moAt}`).querySelector(".measure-name").textContent));
    });
  }
}

/* The federal page's judge search, as readers name judges (FEDERAL-02). */
async function testJudgeSearch() {
  const { window, D } = await buildPage("federal/index.html");
  await settle(80);
  const input = D.getElementById("judgeSearch");
  const index = window.kycJudgesIndex;
  const find = (q) => {
    input.value = q;
    input.dispatchEvent(new window.Event("input"));
    return [...D.querySelectorAll("#judgeResults a")].map((a) => a.textContent);
  };
  suite("federal page — finding a judge by the name they go by (FEDERAL-02)", () => {
    const william = index.find((r) => /^William [A-Z]/.test(r[1]));
    const surname = william && william[1].replace(/,? Jr\.?$/, "").split(" ").pop();
    check("a short first name finds the formal one ('Bill')", !!william &&
      find("Bill " + surname).indexOf(william[1]) !== -1, william && william[1]);
    const middle = index.find((r) => /^[A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+$/.test(r[1]));
    const parts = middle[1].split(" ");
    check("an initial with a period finds the name ('J. Michelle Childs')",
      find(parts[0][0] + ". " + parts[1] + " " + parts[2]).indexOf(middle[1]) !== -1, middle[1]);
    check("a first name the table does not know still finds the surname ('Skip Rankin')",
      find("Zebulon " + parts[2]).indexOf(middle[1]) !== -1);
    const exec = window.kycFederal.offices.find((o) => o.holder && o.holder.name);
    const shown = find(exec.holder.name);
    check("the executive is found here too", shown[0] === exec.holder.name, shown.slice(0, 3).join(", "));
  });
}

/* Ohio's special election after its winner is seated for the term to 2029:
 * the senator's next election moves to 2028, and the seat block must stay
 * with the 2026 specials, where its race is. */
async function testReseatedSpecial() {
  const { window, D, errors } = await buildPage("index.html", {
    hash: "#/?view=senate",
    data: (w) => {
      const race = w.kycRaces.find((r) => r.id === "S-OH-2026");
      const holder = race && w.legislatorsData.find((p) => p.id === race.incumbentIds[0]);
      if (holder) holder.nextElection = 2028;
      w.__ohio = race;
    },
  });
  suite("index.html — a special-election seat after its winner is seated", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    const race = window.__ohio;
    check("Ohio's 2026 race is in the data, marked special", !!race && race.special === true);
    const block = race && D.getElementById("senate-seat-" + race.id);
    const group = block && block.closest(".senate-group-special");
    check("its seat block stays with the 2026 special elections", !!group &&
      /2026 special elections/.test(group.querySelector(".senate-group-title").textContent),
      group ? group.querySelector(".senate-group-title").textContent : "not in a special group");
  });
}

/* December or January: a 2026 incumbent who has left Congress
 * (`formerMember`, built from Former_Members.csv) and the winner seated in
 * that seat (`raceRole` "winner"). Made from Florida's Senate seat as the
 * data stands; a fictional winner, Z900001, never a real person. */
function departFlorida(w) {
  const race = w.kycRaces.find((r) => r.id === "S-FL-2026");
  const holder = race && w.legislatorsData.find((p) => p.id === race.incumbentIds[0]);
  w.__florida = { race, holder };
  if (!holder || holder.formerMember || race.winnerId) return;
  holder.formerMember = { left: "2026-12-08", via: "legislators-historical", congress: 119 };
  holder.status = "Former member: left office 2026-12-08";
  holder.raceStatus = "defeated";
  race.incumbent.seated = false;
  const winner = Object.assign({}, holder, {
    id: "Z900001", name: "Zora Example", party: "Independent", raceRole: "winner",
    raceId: race.id, seatUp2026: false, isUpIn2026: false, seekingReelection2026: false,
    raceStatus: "elected", status: "Active Member", senateClass: 3, nextElection: 2028,
    senateSpecial: false, term_start: "2026-12-08 - 2029-01-03",
  });
  delete winner.formerMember;
  delete winner.appointed;
  delete winner.fecCandidateId;
  w.legislatorsData.push(winner);
  race.candidateIds.push(winner.id);
  race.winnerId = winner.id;
}

/* January 3: a representative who won their state's Senate seat sits in it
 * (`raceRole` "winner", kyc/record.py). The House seat they held is open
 * because they won elsewhere - never because they are "running for" the
 * seat they now hold. Hypothetical, made from a member running today. */
function senateWinnerState() {
  const mover = [...everyone().values()].find((p) => !p.isCandidate && !p.formerMember && p.chamber === "House" &&
    /^S-/.test(p.contestRaceId || ""));
  return mover && mover.state;
}

function seatSenateWinner(state) {
  return (w) => {
    const mover = w.legislatorsData.find((p) => !p.isCandidate && p.state === state &&
      p.chamber === "House" && /^S-/.test(p.contestRaceId || ""));
    const house = mover && w.kycRaces.find((r) => r.incumbentIds.indexOf(mover.id) !== -1);
    w.__winner = { mover, house };
    if (!mover || !house) return;
    Object.assign(mover, { raceRole: "winner", heldRaceId: house.id, raceId: mover.contestRaceId,
      chamber: "Senate", district: "N/A", districtNum: null,
      officeLabel: "Senate • " + mover.state, raceStatus: "elected" });
    ["contestRaceId", "contestLabel", "alsoRunningId", "alsoRunningSeat"]
      .forEach((k) => { delete mover[k]; });
  };
}

async function testSenateWinner() {
  // Only while some House member is running for the Senate: after January 3
  // the data holds the real case, and testFormerIncumbent's checks cover it.
  const state = senateWinnerState();
  if (!state) return;
  const built = await buildPage("states/" + state.toLowerCase() + ".html",
    { data: seatSenateWinner(state) });
  await settle(50);
  suite("states page — a representative seated in the Senate seat they won", () => {
    const { window, D, errors } = built;
    const { mover, house } = window.__winner;
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("their House race is on the page", !!house && !!D.getElementById("race-" + house.id));
    if (!house) return;
    const badge = [...D.getElementById("race-" + house.id).querySelectorAll(".race-head .badge")]
      .find((b) => /Open seat/.test(b.textContent));
    const why = badge ? badge.getAttribute("title") : "";
    check("the House seat is open because they won the Senate race",
      why === mover.name + " won the race for Senate " + mover.state + ".", why);
    const cards = [...D.querySelectorAll('.card[data-id="' + mover.id + '"]')];
    check("no card of theirs says they are running for a seat",
      cards.length > 0 && cards.every((c) => !/Running for/.test(c.textContent)),
      cards.map((c) => c.textContent.replace(/ +/g, " ").slice(0, 120)).join(" | "));
  });
}

/* January: the House's committee rosters are out and the Senate's are not
 * (kyc/legislators.committee_chambers). The guide lists the House's leads
 * and says the Senate's are not published; a senator's profile says so too,
 * naming the Congress from the data. */
function senatePending(w) {
  w.legislatorsData.forEach((p) => {
    if (p.isCandidate || p.formerMember || p.chamber !== "Senate") return;
    delete p.committeeList;
    p.committees = "";
    p.committeesPending = 120;
  });
}

async function testCommitteesPending() {
  // The guide's half - the House's leads listed, the Senate's said to be
  // pending - is written by the build, and tested there
  // (tests/test_guide.py, committees_html).
  const grid = await buildPage("index.html", { data: senatePending });
  await settle(50);
  suite("index.html — a senator whose committees are not yet published", () => {
    const { window, D, errors } = grid;
    check("no page errors", errors.length === 0, errors.join(" | "));
    const senator = window.legislatorsData.find((p) => p.committeesPending);
    window.KYC.profile.open(senator.id);
    const text = D.getElementById("profileModalCommittees").textContent;
    check("their profile says so, with the Congress's ordinal",
      /Committee assignments for the 120th Congress have not been published yet/.test(text), text);
    window.KYC.profile.close();
  });
}

/* January 3, in the page: once the Congress the cycle elects is sitting
 * (meta.election.phase "record", kyc/cycle.phase), the 2026 races are a
 * record. Made from today's data: the phase is set, and each senator whose
 * seat was on the 2026 ballot is given the next election a re-elected term
 * would have. A redrawn state's new map is then held, and its old map is
 * drawn in who last held each seat. */
function recordPhase(w, meta) {
  meta.election = Object.assign({}, meta.election, { phase: "record" });
  w.legislatorsData.forEach((p) => {
    if (w.KYC.seated(p) && /Senate/.test(p.chamber) && p.nextElection === 2026) {
      p.nextElection = p.senateClass === 3 ? 2028 : 2032;
      p.senateSpecial = false;
    }
  });
}

async function testRecordPhase() {
  const senate = await buildPage("index.html", { hash: "#/?view=senate", data: recordPhase });
  await settle(50);
  suite("index.html — the Senate view once the new Congress sits", () => {
    const { window, D, errors } = senate;
    check("no page errors", errors.length === 0, errors.join(" | "));
    const titles = [...D.querySelectorAll(".senate-group-title")].map((h) => h.textContent);
    check("no seat is said to be up in 2026", titles.length > 0 &&
      titles.every((t) => !/2026/.test(t)), titles.join(" | "));
    const ids = [...D.querySelectorAll(".senate-group .card")].map((c) => c.getAttribute("data-id"));
    const sitting = window.legislatorsData.filter((p) => window.KYC.seated(p) && /Senate/.test(p.chamber));
    check("every sitting senator once, and nobody else", ids.length === sitting.length &&
      new Set(ids).size === ids.length && sitting.every((p) => ids.includes(p.id)),
      `${ids.length} cards, ${sitting.length} senators`);
  });

  const after = await buildPage("index.html", { hash: "#/?view=senate", now: new Date("2026-11-20T12:00:00Z") });
  await settle(50);
  suite("index.html — the Senate view after Election Day, before January 3", () => {
    const titles = [...after.D.querySelectorAll(".senate-group-title")].map((h) => h.textContent);
    check("the 2026 seats are no longer \"up\"", titles.some((t) => /^2026 elections/.test(t)) &&
      !titles.some((t) => /Up in 2026/.test(t)), titles.join(" | "));
  });

  const state = await buildPage("states/ky.html", { data: recordPhase });
  await settle(50);
  suite("states/ky.html — the headline once the new Congress sits", () => {
    const strip = [...state.D.querySelectorAll(".state-summary .badge")].map((b) => b.textContent);
    check("its 2026 figures say they are 2026's", strip.length > 3 &&
      strip.filter((b) => /seat|challenger|primaries/.test(b)).every((b) => /2026/.test(b)),
      strip.join(" | "));
  });

  const tx = await buildPage("districts/tx.html", { data: recordPhase });
  await settle(50);
  suite("districts/tx.html — a redrawn state once the new Congress sits", () => {
    const { window, D, errors } = tx;
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("no member is \"running in a different district\"", !D.querySelector(".mover-group") &&
      !/Running in a different district/.test(D.getElementById("districtsApp").textContent));
    const legend = D.querySelector(".party-legend").textContent;
    check("the legend says the old map shows who last held each seat",
      /by who last held it/.test(legend) && !/seats filled in November/.test(legend), legend);
    const pick = D.getElementById("districtPick");
    pick.value = pick.options[1].value;
    pick.dispatchEvent(new window.Event("change", { bubbles: true }));
    const labels = [...D.querySelectorAll(".district-fact-label")].map((f) => f.textContent);
    check("the old map's district says who last held it",
      labels.some((t) => /^(Last held by|No holder on the record)/.test(t)), labels.join(" | "));
    check("the new map's district says who holds it, and the 2026 race as a record",
      labels.some((t) => /^(Seat held by|No sitting member)/.test(t)) &&
      labels.some((t) => /^In the 2026 race/.test(t)) &&
      !labels.some((t) => /^(On the November ballot|Running)/.test(t)), labels.join(" | "));
  });
}

async function testFormerIncumbent() {
  const now = new Date("2026-12-10T12:00:00Z");
  const grid = await buildPage("index.html", { hash: "#/?role=member&chamber=Senate", now,
                                                 data: departFlorida });
  await settle(50);
  suite("index.html — a 2026 incumbent who has left, and the seat's winner", () => {
    const { window, D, errors } = grid;
    const KYC = window.KYC;
    const { race, holder } = window.__florida;
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("Florida's appointee is a former member", !!holder && !!holder.formerMember);
    const ids = [...D.querySelectorAll("#results .card")].map((c) => c.getAttribute("data-id"));
    check("sitting senators exclude her and include the winner",
      !ids.includes(holder.id) && ids.includes(race.winnerId), `${ids.length} cards`);
    check("the Senate is still 100", ids.length === 100, `${ids.length}`);
    KYC.profile.open(holder.id);
    const meta = D.querySelector("#profileModal .modal-meta").textContent;
    check("her dialog says she represented the state until she left",
      /Represented \(until 2026-12-08\)/.test(meta) && !/Represents/.test(meta),
      meta.replace(/\s+/g, " "));
    check("and says she left office",
      /Left office 2026-12-08/.test(D.getElementById("profileModalStatus").textContent));
    KYC.profile.close();
    KYC.profile.open(race.winnerId);
    const status = D.getElementById("profileModalStatus").textContent;
    const won = KYC.byId(race.winnerId).raceStatus === "elected";
    check("the winner was elected, never re-elected", !/Re-elected/.test(status) &&
      (!won || /Elected/.test(status)), status);
    KYC.profile.close();
  });

  const view = await buildPage("index.html", { hash: "#/?view=senate", now, data: departFlorida });
  await settle(50);
  suite("index.html — Senate view after a 2026 seat changes hands", () => {
    const { window, D, errors } = view;
    const { race, holder } = window.__florida;
    check("no page errors", errors.length === 0, errors.join(" | "));
    const head = D.getElementById("senate-seat-" + race.id);
    const block = head && head.closest("section");
    const ids = block ? [...block.querySelectorAll(".card")].map((c) => c.getAttribute("data-id")) : [];
    check("the seat block leads with its winner, who holds it now, then who held it",
      ids[0] === race.winnerId && ids[1] === holder.id, ids.join(","));
    check("saying so", !!block && /Holds the seat \(won it in 2026\)/.test(block.textContent) &&
      /Held the seat until Dec\. 8, 2026/.test(block.textContent));
    const running = block && block.querySelector(".senate-running");
    check("the winner is never listed as running for it",
      !running || !running.querySelector('.card[data-id="' + race.winnerId + '"]'));
    const elsewhere = [...view.D.querySelectorAll(".card")]
      .filter((c) => c.getAttribute("data-id") === race.winnerId).length;
    check("and nowhere else", elsewhere === 1, `${elsewhere}`);
    const badge = block && block.querySelector('.card[data-id="' + holder.id + '"]');
    check("her card is badged a former member", !!badge && /Former member/.test(badge.textContent));
  });

  const ca = await buildPage("districts/ca.html", { now, data: (w) => {
    const mover = w.legislatorsData.find((p) => !p.isCandidate && p.state === "CA" &&
      /House/.test(p.chamber) && w.KYC.runsElsewhere(p));
    if (mover) mover.formerMember = { left: "2027-01-03", via: "legislators-historical",
                                      congress: 119 };
    w.__mover = mover;
  } });
  await settle(50);
  suite("districts/ca.html — a member who moved and has left", () => {
    const { window, D, errors } = ca;
    const mover = window.__mover;
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("a California member ran in another district", !!mover);
    const named = [...D.querySelectorAll(".mover")].some((m) => mover &&
      m.textContent.indexOf(mover.name) !== -1);
    check("they are not listed as holding one district and running in another", !named);
  });

  const state = await buildPage("states/fl.html", { now, data: departFlorida });
  await settle(50);
  suite("states/fl.html — after a 2026 seat changes hands", () => {
    const { window, D, errors } = state;
    const { race, holder } = window.__florida;
    check("no page errors", errors.length === 0, errors.join(" | "));
    const section = D.getElementById("senators");
    const ids = section ? [...section.querySelectorAll(".card")].map((c) => c.getAttribute("data-id")) : [];
    check("the state's senators are who sits now", ids.length === 2 &&
      !ids.includes(holder.id) && ids.includes(race.winnerId), ids.join(","));
  });
}

/* The federal government's pages (kyc-federal.js) and the official dialog
 * (kyc-official.js), from data/federal.js and one court file each. An
 * official is never a profile; a judge is shown with who appointed them,
 * never with a party; a page lists who sits and never counts vacancies. */
const PARTY_WORDS = /\b(Republican|Democrat(ic)?|Independent)\b/;

async function testFederal() {
  const hub = await buildPage("federal/index.html");
  await settle(50);
  const { window, D, errors } = hub;
  const d = window.kycFederal;
  suite("federal/index.html — who holds the federal government's offices", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("the data loaded", !!d && d.offices.length > 0 && d.courts.length > 100);
    if (!d) return;
    const leaders = [...D.querySelectorAll(".fed-leader")];
    const term = D.getElementById("executiveTerm");
    const same = d.president.since === d.vicePresident.since && d.president.until === d.vicePresident.until;
    check("a term they share is said once, above them", !same || (!!term &&
      term.textContent.indexOf(window.KYC.dateWords(d.president.since)) !== -1 &&
      [...D.querySelectorAll(".fed-leader")].every((c) =>
        c.textContent.indexOf(window.KYC.dateWords(d.president.until)) === -1)),
      term && term.textContent);
    check("the President, then the Vice President",
      leaders.length === 2 && leaders[0].textContent.indexOf(d.president.name) !== -1 &&
      leaders[1].textContent.indexOf(d.vicePresident.name) !== -1);
    const rows = [...D.querySelectorAll("#cabinet .fed-officer")];
    check("a card for every office the White House lists", rows.length === d.offices.length,
      `${rows.length} cards, ${d.offices.length} offices`);
    check("every officer the White House pictures is pictured", d.offices.every((o) =>
      !o.holder || !o.holder.photo || rows.some((r) => r.textContent.indexOf(o.holder.name) !== -1 &&
        r.querySelector("img.fed-photo"))));
    const departments = d.offices.filter((o) => o.kind === "department")
      .sort((a, b) => a.order - b.order);
    check("the departments first, in the order of succession", departments.every((o, i) =>
      rows[i].querySelector(".fed-office").textContent === o.office));
    check("no Cabinet officer is shown with a party",
      !PARTY_WORDS.test(D.getElementById("cabinet").textContent));
    const justices = [...D.querySelectorAll("#supreme-court .fed-justice")];
    check("the Court's members as the Court lists them",
      justices.length === d.supremeCourt.members.length, `${justices.length}`);
    const retired = new Set((d.supremeCourt.retired || []).map((j) => j.id));
    check("a retired justice is never among them", justices.every((c) =>
      !retired.has(c.querySelector("[data-official]").getAttribute("data-official"))));
    check("each justice the Court pictures is pictured", d.supremeCourt.members.every((j, i) =>
      !j.portrait || (justices[i].querySelector("img.fed-photo") || {}).getAttribute &&
        justices[i].querySelector("img.fed-photo").getAttribute("src") === j.portrait.url));
    // The owner's decision of 2026-10-20: the Court's official portraits as
    // Wikimedia Commons holds them; the Court's own named apart, never all
    // credited to its Collection over files that are Commons'.
    const scotusLede = D.querySelector("#supreme-court .guide-lede").textContent;
    const fromCourt = d.supremeCourt.members.filter((j) => j.portrait && !j.portrait.licence);
    check("the portraits are said to be the official ones Commons holds, the Court's own named apart",
      (!d.supremeCourt.members.some((j) => j.portrait && j.portrait.licence) ||
        /official portraits as Wikimedia Commons holds them/.test(scotusLede)) &&
      fromCourt.every((j) => scotusLede.indexOf(j.name + "’s from the Court’s own site") !== -1) &&
      // Commons holds a file the table names; when the read did not
      // confirm it, the line never says Commons does not hold it (the PR
      // #133 review).
      (!fromCourt.some((j) => j.portraitUnconfirmed) || /did not confirm/.test(scotusLede)) &&
      (fromCourt.some((j) => !j.portraitUnconfirmed) || !/Commons does not hold/.test(scotusLede)),
      scotusLede);
    const sized = [...D.querySelectorAll("#cabinet img.fed-photo, #executive img.fed-photo")];
    // A srcset is read by its "url widthw" pairs: the URLs hold commas.
    const urlsOf = (img) => [...(img.getAttribute("srcset") || "").matchAll(/(\S+)\s+\d+w/g)]
      .map((m) => m[1].replace(/^,/, ""));
    check("an executive photo is drawn from the sizes of that one file", sized.length > 0 &&
      sized.every((img) => urlsOf(img).every((u) =>
        u.split("?")[0] === img.getAttribute("src").split("?")[0])) &&
      sized.some((img) => urlsOf(img).length > 0));
    // TECH-13: a 72px photo is offered no size wider than a 2x screen needs.
    const widthsOf = (img) => [...(img.getAttribute("srcset") || "").matchAll(/\s(\d+)w/g)]
      .map((m) => parseInt(m[1], 10));
    check("and offered no size wider than a 2x screen needs", sized.every((img) =>
      widthsOf(img).filter((w) => w >= 144).length <= 1));
    // The court tables; the list of vacancies links courts again, by row.
    const links = [...D.querySelectorAll('#courts table a[href^="../courts/"]')]
      .filter((a) => !a.closest("#vacancy-list")).map((a) => a.getAttribute("href"))
      .filter((href) => href.indexOf("#") === -1);
    check("every court but the Supreme Court is linked, once",
      links.length === d.courts.length - 1 && new Set(links).size === links.length,
      `${links.length} links, ${d.courts.length} courts`);
    check("no court lists a party", !PARTY_WORDS.test(D.getElementById("courts").textContent));
    check("every link out opens safely", [...D.querySelectorAll('a[target="_blank"]')]
      .every((a) => /noopener/.test(a.getAttribute("rel") || "")));
    check("a table becomes cards on a phone: every cell says its column",
      [...D.querySelectorAll(".guide-table td")].every((td) => td.getAttribute("data-label")));
    check("the nav marks this page", (D.querySelector('.nav-link[aria-current="page"]') || {})
      .getAttribute && D.querySelector('.nav-link[aria-current="page"]').getAttribute("data-nav") ===
      "executive");
    const learn = [...D.querySelectorAll(".fed-section .learn-link")].map((a) => a.getAttribute("href"));
    check("each section links where Know Your Government explains it",
      ["executive", "cabinet", "supreme-court", "courts"].every((id) =>
        !!D.querySelector("#" + id + " .learn-link[href^='../government/']")), learn.join(" "));
    check("no state is remembered from this page", D.body.getAttribute("data-state") === "");
    check("the sidebar's state list is written into the page",
      D.getElementById("stateJump").options.length > 50, `${D.getElementById("stateJump").options.length}`);
    // The hub loads no court's file: a name it cannot open must not be a
    // button, or a sitting judge reads as "no longer listed".
    const buttons = [...D.querySelectorAll("[data-official]")];
    check("every name the hub offers to open, it can open", buttons.every((b) =>
      window.KYC.official.officials()[b.getAttribute("data-official")]),
      buttons.filter((b) => !window.KYC.official.officials()[b.getAttribute("data-official")])
        .map((b) => b.textContent).slice(0, 5).join(", "));
    const chiefs = d.courts.filter((c) => c.kind !== "supreme" && c.chief);
    check("a chief judge links to their record on their court's page", chiefs.every((c) =>
      !!D.querySelector('#courts a[href="../courts/' + c.id + ".html#/official/" +
        encodeURIComponent(c.chief.id) + '"]')));
    const tie = d.offices.find((o) => o.holder && o.holder.senate &&
      o.holder.senate.yeas === o.holder.senate.nays);
    check("a tie the Vice President broke is said", !tie || [...D.querySelectorAll("#cabinet .fed-officer")]
      .some((tr) => tr.textContent.indexOf(tie.holder.name) !== -1 &&
        /the Vice President breaking the tie/.test(tr.textContent)));
    const summary = D.getElementById("vacancySummary");
    check("the vacancies are the courts' own count, dated", !!summary &&
      summary.textContent.indexOf(d.vacancies.totals.vacancies + " vacancies") !== -1 &&
      summary.textContent.indexOf(window.KYC.dateWords(d.vacancies.asOf)) !== -1, summary && summary.textContent);
    check("each court's row gives its vacancies",
      [...D.querySelectorAll("#courts thead")].filter((h) => !h.closest("#vacancy-list"))
        .every((h) => /Vacancies/.test(h.textContent)));
    const changes = D.getElementById("changes");
    const withHistory = d.offices.filter((o) => (o.history || []).length);
    check("the Cabinet's changes since the term began are listed", !withHistory.length ||
      (!!changes && changes.querySelectorAll("tbody tr").length > 0));
    if (changes && withHistory.length) {
      const when = [...changes.querySelectorAll("tbody tr th")].map((th) => th.textContent)
        .filter((w) => /^\d{4}/.test(w));
      check("newest first", when.every((w, i) => i === 0 || w.slice(0, 4) <= when[i - 1].slice(0, 4)),
        when.slice(0, 6).join(" | "));
      const left = withHistory.reduce((n, o) => n + o.history.filter((r) => r.end).length, 0);
      check("a departure for every holder who left", [...changes.querySelectorAll(".badge")]
        .filter((b) => b.textContent === "Left").length === left, `${left}`);
      const replaced = withHistory.find((o) => o.history.findIndex((r) => r.current) > 0);
      const card = replaced && [...D.querySelectorAll("#cabinet .fed-officer")]
        .find((c) => c.querySelector(".fed-office").textContent === replaced.office);
      const prev = replaced && replaced.history[replaced.history.findIndex((r) => r.current) - 1];
      check("a card names whom its officer followed this term", !replaced ||
        (!!card && (card.textContent.indexOf("after " + prev.name) !== -1 ||
          card.textContent.indexOf("previously this term: " + prev.name) !== -1)), card && card.textContent);
      const actingNotes = withHistory.flatMap((o) => o.history.filter((r) => r.actingNote && r.actingStart));
      check("acting service before a confirmation is in the timeline", actingNotes.every((r) =>
        [...changes.querySelectorAll("tbody tr")].some((tr) =>
          tr.textContent.indexOf(r.name + " became acting") !== -1)), actingNotes.map((r) => r.name).join(", "));
      // Labor: "Since 2026-04-20", an acting start, beside a September vote.
      const actingNow = withHistory.filter((o) => o.history.some((r) => r.current && r.actingNote && r.actingStart));
      check("a card whose officer was acting before confirmation says both, never 'Since' the acting start",
        actingNow.every((o) => {
          const row = o.history.find((r) => r.current);
          const card = [...D.querySelectorAll("#cabinet .fed-officer")]
            .find((c) => c.querySelector(".fed-office").textContent === o.office);
          const text = card ? card.textContent : "";
          return /Acting from /.test(text) && /their Wikipedia article/.test(text) &&
            !/In office Since/.test(text) && (!row.confirmed ||
              text.indexOf("then confirmed " + window.KYC.dateWords(row.confirmed.date)) !== -1);
        }), actingNow.map((o) => o.office).join(", "));
      const cards = [...D.querySelectorAll("#cabinet .fed-officer")];
      check("'after' only where the hand-over is shown", withHistory.every((o) => {
        const i = o.history.findIndex((r) => r.current);
        if (i < 1) return true;
        const prev = o.history[i - 1], now = o.history[i];
        const same = prev.end && prev.end.shown && now.start && now.start.shown &&
          prev.end.shown.precision === "day" && now.start.shown.precision === "day" &&
          prev.end.shown.date === now.start.shown.date;
        const card = cards.find((c) => c.querySelector(".fed-office").textContent === o.office);
        return !card || card.textContent.indexOf((same ? "after " : "previously this term: ") + prev.name) !== -1;
      }));
      // An acting end both sources put after the successor's start is not
      // shown as a date (Energy: Kolb to Feb 4, Wright from Feb 3).
      const overlapped = withHistory.flatMap((o) => o.history.filter((r) => r.end && r.end.overlap));
      check("an acting end after the successor took office is not shown as a date",
        overlapped.every((r) => [...changes.querySelectorAll("tbody tr")].some((tr) =>
          tr.textContent.indexOf(r.name + "’s service as acting ended") !== -1 &&
          /Date not shown: both sources put it after the successor took office/.test(tr.textContent))),
        overlapped.map((r) => r.name).join(", "));
      check("no Wikidata label is shown for a person: names are the White House's, the Senate's " +
        "or an article's", withHistory.every((o) => o.history.every((r) =>
          r.current ? r.name === o.holder.name : !!(r.wikipedia || (r.confirmed && r.name === r.confirmed.nominee)))));
    }
    check("the courts are said to be the Article III courts",
      /Article III/.test(D.getElementById("courts").textContent) &&
      !/Every federal court/.test(D.getElementById("federalBody").textContent));
    // The section holds the Article IV territorial courts too: its title
    // and lede may not promise only Article III courts, or their judges.
    const courtsHead = D.querySelector("#courts .guide-subheading");
    check("the section is the federal courts, not 'the Article III courts'",
      !!courtsHead && courtsHead.textContent === "The federal courts", courtsHead && courtsHead.textContent);
    const lede = D.getElementById("courtsLede");
    check("the lede says the territorial courts' judges are not in the directory, why, and from where",
      !!lede && /territorial district courts/.test(lede.textContent) &&
      /not in the directory/.test(lede.textContent) && /court’s own website/.test(lede.textContent) &&
      /Article IV/.test(lede.textContent), lede && lede.textContent);
    const territorial = d.courts.filter((c) => !c.listed && c.kind === "territorial");
    check("each territorial court's row says its judges serve under Article IV",
      territorial.length === 3 && territorial.every((c) => {
        const a = D.querySelector('#courts a[href="../courts/' + c.id + '.html"]');
        const row = a && a.closest("tr");
        // FEDERAL-06: with the court's own list read, its count and chief,
        // attributed; otherwise that the directory does not hold them.
        return !!row && (c.courtListed
          ? /Article IV judgeships? filled, by the court’s list/.test(row.textContent) &&
            (!c.courtListed.chief || (row.textContent.includes(c.courtListed.chief) &&
              /the court’s list/.test(row.textContent)))
          : /Article IV judges: not in the directory/.test(row.textContent));
      }), territorial.map((c) => c.id).join(", "));
  });

  suite("federal/index.html — the circuit map", () => {
    const svg = D.getElementById("circuitMap");
    check("the map is drawn", !!svg && svg.querySelectorAll("[data-state]").length >= 56,
      svg && `${svg.querySelectorAll("[data-state]").length}`);
    check("no word is SVG text (rule 46)", !!svg && !svg.querySelector("text"));
    // The territory strip's own caption is the map's, not a state's.
    const labels = [...D.querySelectorAll("#circuitLabels .map-label")]
      .filter((s) => !/Territories/.test(s.textContent));
    const circuits = new Set(d.courts.filter((c) => c.token).map((c) => c.circuit).concat(["–"]));
    // On its shape a state carries the number alone; a word drawn away from
    // its shape (a callout, a territory's tile) names the place as well:
    // the Northeast's callouts read "2, 1, 1, 1, 2" and the territories
    // "1, 3, 9, 9" with nothing saying which was which (VISUALS-17).
    const away = (s) => s.classList.contains("map-callout") || s.classList.contains("territory-label");
    const inside = labels.filter((s) => !away(s)).map((s) => s.textContent);
    const outside = labels.filter(away).map((s) => s.textContent);
    check("each state carries its circuit's number, never its code", inside.length >= 30 &&
      inside.every((w) => circuits.has(w)) && inside.includes("5") && inside.includes("9"),
      inside.filter((w) => !circuits.has(w)).slice(0, 5).join(", "));
    check("a callout or a territory's tile names its place beside the number",
      // D.C.'s circuit is named "DC" itself, so its word is the code once.
      outside.length >= 6 && outside.every((w) => w === "DC" ||
        (/^[A-Z]{2} \S+$/.test(w) && circuits.has(w.slice(3)))) &&
        ["PR", "GU", "VI", "MP"].every((t) => outside.some((w) => w.indexOf(t + " ") === 0)),
      outside.join(", "));
    const texas = svg && svg.querySelector('[data-state="TX"]');
    if (texas) texas.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    const panel = D.getElementById("circuitPanel");
    const tx = d.courts.filter((c) => (c.states || []).includes("TX") && c.kind === "district")
      .map((c) => c.id);
    check("picking a state lists its court of appeals and every district court",
      !!panel.querySelector('a[href="../courts/ca5.html"]') &&
      tx.length === 4 && tx.every((id) => !!panel.querySelector('a[href="../courts/' + id + '.html"]')),
      panel.textContent);
    check("and the pick is in the address", /circuitState=TX/.test(window.location.hash), window.location.hash);
    const samoa = svg && svg.querySelector('[data-state="AS"]');
    check("American Samoa is in no circuit", !!samoa && /surface-2/.test(samoa.style.fill || samoa.getAttribute("style") || ""));
  });

  suite("federal/index.html — finding a judge", () => {
    const input = D.getElementById("judgeSearch");
    const chief = d.supremeCourt.members[0];
    input.value = chief.sortName.split(",")[0];
    input.dispatchEvent(new window.Event("input"));
    const results = [...D.querySelectorAll("#judgeResults a")];
    const link = results.find((a) => a.textContent === chief.name);
    check("a surname finds the Chief Justice", !!link, results.map((a) => a.textContent).join(", "));
    check("linking to them on their court's page", !!link &&
      link.getAttribute("href") === "../courts/scotus.html#/official/" + encodeURIComponent(chief.id),
      link && link.getAttribute("href"));
    check("the search is in the address", /q=/.test(window.location.hash), window.location.hash);
    input.value = "zzqxv nobody";
    input.dispatchEvent(new window.Event("input"));
    // Not "no such judge in the directory": the directory holds legal
    // names, and a judge's usual name may not be one (FEDERAL-02).
    check("a name nobody has says so, and suggests the surname",
      /No judge matches that name; try the surname alone/.test(
        D.getElementById("judgeSearchCount").textContent));
    // Namesakes are counted as namesakes: "Jim Smith" read "4 judges".
    const first = window.kycJudgesIndex[0];
    const last = first[1].replace(/,? (Jr|Sr|II|III)\.?$/, "").split(" ").pop();
    input.value = "Zyxwq " + last;
    input.dispatchEvent(new window.Event("input"));
    const said = D.getElementById("judgeSearchCount").textContent;
    check("judges found by the surname alone are said to be", new RegExp(
      "No judge by that full name; \\d+ judges? with the surname " + last).test(said), said);
    const exec = d.offices.map((o) => o.holder).find((h) => h && h.name &&
      !window.kycJudgesIndex.some((row) => window.KYC.nameScore(h.name, [row[1], row[4]]) >= 0));
    if (exec) {
      input.value = exec.name;
      input.dispatchEvent(new window.Event("input"));
      const line = D.getElementById("judgeSearchCount").textContent;
      check("an executive official found is not told to try the surname",
        /^1 in the executive branch; no judge by that name$/.test(line), line);
    }
    const index = window.kycJudgesIndex;
    const roving = index.find((row) => row[2].length > 1);
    if (roving) {
      input.value = roving[1];
      input.dispatchEvent(new window.Event("input"));
      const shown = [...D.querySelectorAll("#judgeResults a")].filter((a) => a.textContent === roving[1]);
      check("a judge on several courts is listed once", shown.length === 1, `${shown.length}`);
    }
    check("the count is of people", D.getElementById("judgeSearchCount") &&
      new Set(index.map((row) => row[0])).size === index.length);
    // The directory's "A[llen] Joe Fish": shown as he goes by, found by both.
    check("no judge's name carries the directory's brackets", index.every((row) => row[1].indexOf("[") === -1),
      index.filter((row) => row[1].indexOf("[") !== -1).map((row) => row[1]).slice(0, 3).join(", "));
    const bracketed = index.find((row) => row[4]);
    if (bracketed) {
      input.value = bracketed[4];
      input.dispatchEvent(new window.Event("input"));
      check("a judge is found by the full name the directory gives",
        [...D.querySelectorAll("#judgeResults a")].some((a) => a.textContent === bracketed[1]),
        bracketed[4] + " -> " + bracketed[1]);
    }
    input.value = "";
    input.dispatchEvent(new window.Event("input"));
  });

  suite("federal/index.html — an official's dialog", () => {
    const KYC = window.KYC;
    const office = d.offices.find((o) => o.holder && o.holder.senate);
    D.querySelector('#cabinet [data-official="' + office.holder.id + '"]').click();
    const modal = D.getElementById("officialModal");
    check("a Cabinet officer opens in the dialog", !!modal && !modal.hidden &&
      D.getElementById("officialModalName").textContent === office.holder.name);
    check("at their own address", window.location.hash === "#/official/" +
      encodeURIComponent(office.holder.id), window.location.hash);
    check("with the Senate's vote, linked to the Senate",
      !!modal.querySelector('a[href^="https://www.senate.gov/"]'));
    check("and no party", !PARTY_WORDS.test(D.getElementById("officialModalMeta").textContent) &&
      !modal.querySelector(".party-tag"));
    const credit = D.getElementById("officialModalPhotoCredit");
    check("their photograph is credited under their name, as a profile's is (rule 87)",
      office.holder.photo ? !credit.hidden && credit.textContent === "Photo: The White House" +
        (office.holder.photoCopy ? "; a smaller copy made by this site of the original file" +
          (office.holder.photoCopy.ofBytes
            ? " (" + window.KYC.weightWords(office.holder.photoCopy.ofBytes) + ")" : "") : "")
        : credit.hidden, credit.textContent);
    KYC.official.close();
    const record = d.offices.find((o) => o.holder && (o.holder.politicalHistory || {}).rows &&
      o.holder.politicalHistory.rows.some((r) => r.congress));
    check("an officer who served in Congress exists", !!record);
    if (record) {
      KYC.official.open(record.holder.id);
      const head = [...modal.querySelectorAll(".panel-head")]
        .find((h) => /Public offices held/.test(h.textContent));
      check("their offices held are listed, from the same renderer as a profile's",
        !!head && head.closest("section").querySelectorAll(".held-row").length ===
          record.holder.politicalHistory.rows.length);
      check("a seat in Congress names its state here too, with no state table loaded",
        [...head.closest("section").querySelectorAll(".held-where")]
          .every((el) => !/^[A-Z]{2}\b/.test(el.textContent)));
      KYC.official.close();
    }
    const filer = d.offices.find((o) => o.holder && o.holder.disclosures &&
      (o.holder.disclosures.documents || []).length);
    check("an officer with OGE reports exists", !!filer);
    if (filer) {
      KYC.official.open(filer.holder.id);
      const head = [...modal.querySelectorAll(".panel-head")]
        .find((h) => /Financial disclosures/.test(h.textContent));
      const links = head ? [...head.closest("section").querySelectorAll("a")] : [];
      const reports = links.filter((a) => /\/PAS\+Index\/[0-9A-F]{32}\/\$FILE\//.test(a.href));
      check("their reports link to the files OGE serves",
        reports.length === filer.holder.disclosures.documents.length);
      check("never to OGE's request form, as though it were a report",
        !links.some((a) => /201%20Request|201 Request/.test(a.href)));
      check("and say whose filing they are, as OGE files it",
        head.closest("section").textContent.indexOf(filer.holder.disclosures.filed) !== -1);
      check("its links open safely", links.every((a) => a.target === "_blank" && /noopener/.test(a.rel)));
      KYC.official.close();
    }
    // The absences, driven from fixtures so they always run.
    const host = d.offices.find((o) => o.holder);
    const kept = host.holder.disclosures;
    const panelText = () => {
      const head = [...modal.querySelectorAll(".panel-head")]
        .find((h) => /Financial disclosures/.test(h.textContent));
      return head ? head.closest("section").textContent : "";
    };
    host.holder.disclosures = { none: true, agency: "Department of Labor", position: "Secretary" };
    KYC.official.open(host.holder.id);
    check("read and nothing found says so, and never 'filed as' no one (rule 19)",
      /lists no report/.test(panelText()) && !/Filed with the Office/.test(panelText()) &&
        !/not filed|has not filed/i.test(panelText()), panelText());
    KYC.official.close();
    host.holder.disclosures = { notRead: true };
    KYC.official.open(host.holder.id);
    check("not read for this officer is a claim about this site, not the officer",
      /has not read OGE/.test(panelText()) && !/lists no report/.test(panelText()), panelText());
    KYC.official.close();
    host.holder.disclosures = { filed: "Doe, Jane", agency: "Department of Labor", position: "Secretary",
      documents: [{ kind: "annual", words: "Annual report, 2026", date: "2026-07-01",
        url: "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/" + "A".repeat(32) + "/$FILE/x.pdf",
        unchecked: true }] };
    KYC.official.open(host.holder.id);
    check("a report whose filer was not read is marked so",
      !!modal.querySelector(".held-note") && /not checked/.test(panelText()) &&
        /posted/.test(panelText()), panelText());
    KYC.official.close();
    host.holder.disclosures = kept;
  });
  await settle(50);
  suite("federal/index.html — a justice's dialog", () => {
    check("closing the last one left its address", !/official/.test(window.location.hash),
      window.location.hash);
    const modal = D.getElementById("officialModal");
    const justice = d.supremeCourt.members[1];
    D.querySelector('#supreme-court [data-official="' + justice.id + '"]').click();
    const meta = D.getElementById("officialModalMeta").textContent;
    check("a justice is shown with who appointed them, never a party",
      /Appointed by/.test(meta) && !PARTY_WORDS.test(meta), meta);
    if (justice.portrait && justice.portrait.licence) {
      const credit = D.getElementById("officialModalPhotoCredit").textContent;
      check("a justice's Commons portrait is credited to its photographer and licence (rule 87)",
        credit.indexOf(justice.portrait.by) !== -1 && credit.indexOf(justice.portrait.licence) !== -1,
        credit);
    }
    check("and links to the Federal Judicial Center's page",
      !!modal.querySelector('a[href^="https://www.fjc.gov/node/"]'));
    // The directory's career field holds roles held now ("-present"): the
    // panel keeps the directory's label, never "before the bench".
    const heads = [...modal.querySelectorAll(".panel-head")].map((h) => h.textContent);
    check("the career panel carries the directory's own label",
      heads.some((h) => /Professional career/.test(h)) && !heads.some((h) => /before the bench/.test(h)),
      heads.join(" | "));
    check("Escape closes it", (() => {
      D.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      return modal.hidden;
    })());
    // A retired justice: retired since a date, never "Since" their
    // commission under a heading about retirement, nor "senior status".
    const retired = (d.supremeCourt.retired || [])[0];
    if (retired) {
      const table = [...D.querySelectorAll("#supreme-court table")].find((t) =>
        /Retired justices/.test(t.textContent));
      const heads = table ? [...table.querySelectorAll("thead th")].map((th) => th.textContent) : [];
      check("the retired justices' table says when each took the oath and when they retired",
        heads.includes("Took the oath") && heads.includes("Retired") && !heads.includes("Since"),
        heads.join(" | "));
      const row = table && [...table.querySelectorAll("tbody tr")].find((tr) =>
        tr.textContent.indexOf(retired.name) !== -1);
      // FEDERAL-11: one "took the oath" date for a justice on every page -
      // the Court's own, never the commission (Kennedy: 1988-02-18, not -11).
      check("their retirement is the directory's senior-status date, their start the Court's oath", !!row &&
        row.querySelector('[data-label="Retired"]').textContent ===
          window.KYC.dateWords(retired.seats[0].seniorSince) &&
        !!retired.courtService &&
        row.querySelector('[data-label="Took the oath"]').textContent ===
          window.KYC.dateWords(retired.courtService.oath),
        row && row.textContent);
      D.querySelector('#supreme-court [data-official="' + retired.id + '"]').click();
      const body = D.getElementById("officialModalBody").textContent;
      check("their dialog says retired, not senior status",
        /retired since/.test(body) && !/senior status since/.test(body), body.slice(0, 300));
      window.KYC.official.close();
    }
  });

  const president = d && d.president;
  const deep = await buildPage("federal/index.html",
    { hash: "#/official/" + encodeURIComponent(president ? president.id : "") });
  await settle(50);
  suite("federal/index.html — a shared link to the President", () => {
    const { D: doc, errors: errs } = deep;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const modal = doc.getElementById("officialModal");
    check("opens the dialog", !!modal && !modal.hidden &&
      doc.getElementById("officialModalName").textContent === president.name);
    check("the President's party is shown: elected on a ticket",
      doc.getElementById("officialModalMeta").textContent.indexOf(president.party) !== -1);
  });

  const gone = await buildPage("federal/index.html", { hash: "#/official/x-nobody-of-that-name" });
  await settle(50);
  suite("federal/index.html — a link to someone no longer listed", () => {
    const { D: doc, errors: errs } = gone;
    check("no page errors", errs.length === 0, errs.join(" | "));
    check("says so, rather than showing someone else",
      doc.getElementById("officialModalName").textContent === "No longer listed" &&
      /may have left office/.test(doc.getElementById("officialModalBody").textContent));
  });

  const ca1 = await buildPage("courts/ca1.html");
  await settle(50);
  suite("courts/ca1.html — one court's judges", () => {
    const { window: w, D: doc, errors: errs } = ca1;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const mine = (w.kycCourt || {}).ca1;
    const court = w.kycFederal.courts.find((c) => c.id === "ca1");
    const people = [...doc.querySelectorAll("#federalBody tbody [data-official]")]
      .map((b) => b.getAttribute("data-official"));
    check("every judge the directory lists, once", !!mine && people.length === mine.judges.length &&
      new Set(people).size === people.length, `${people.length}`);
    check("the chief judge first", !!court.chief && people[0] === court.chief.id);
    check("active judges, then senior", !!doc.getElementById("active") &&
      (court.senior === 0 || !!doc.getElementById("senior")));
    const below = w.kycFederal.courts.filter((c) => c.circuit === "1" && c.kind !== "appeals");
    check("its district courts are linked", below.every((c) =>
      !!doc.querySelector('.fed-related a[href="' + c.id + '.html"]')));
    check("no judge is shown with a party", !PARTY_WORDS.test(doc.getElementById("federalBody").textContent));
    check("no state is remembered from a court page", doc.body.getAttribute("data-state") === "");
  });

  const judge = ((ca1.window.kycCourt || {}).ca1 || { judges: [] }).judges.slice(-1)[0];
  const deepJudge = await buildPage("courts/ca1.html",
    { hash: "#/official/" + encodeURIComponent(judge ? judge.id : "") });
  await settle(50);
  suite("courts/ca1.html — a shared link to a judge", () => {
    const { D: doc, errors: errs } = deepJudge;
    check("no page errors", errs.length === 0, errs.join(" | "));
    check("opens their record", !!judge &&
      doc.getElementById("officialModalName").textContent === judge.name);
    check("their own court is not a link away from itself",
      !doc.querySelector('#officialModalBody a[href="ca1.html"]'));
  });

  const conflicted = ((ca1.window.kycFederal || {}).courts || []).find((c) => c.chiefUnsettled);
  if (conflicted) {
    const page = await buildPage("courts/" + conflicted.id + ".html");
    await settle(50);
    suite("courts/" + conflicted.id + ".html — a chief the directory also lists as senior", () => {
      check("no page errors", page.errors.length === 0, page.errors.join(" | "));
      const note = page.D.getElementById("chiefUnsettled");
      check("nobody is shown as chief, and the page says why", !!note &&
        /28 U\.S\.C\. 136/.test(note.textContent) && !page.D.querySelector("#federalBody .badge"),
        note && note.textContent);
    });
  }

  const withVacancies = ((ca1.window.kycFederal || {}).courts || []).find((c) => c.vacancies > 1);
  const vacantPage = withVacancies && await buildPage("courts/" + withVacancies.id + ".html");
  if (vacantPage) await settle(50);
  suite("a court page's vacancies, as the courts list them", () => {
    check("a court with vacancies exists to test", !!vacantPage);
    if (!vacantPage) return;
    const { window: w, D: doc, errors: errs } = vacantPage;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const mine = w.kycCourt[withVacancies.id];
    const rows = [...doc.querySelectorAll("#vacancies table:first-of-type tbody tr")];
    check("a row for every vacancy the list gives this court", rows.length === mine.vacancies.length,
      `${rows.length} rows, ${mine.vacancies.length} vacancies`);
    check("an emergency says so", doc.querySelectorAll("#vacancies .badge").length ===
      mine.vacancies.filter((r) => r.emergency).length);
    check("it names its source and date", !!doc.querySelector('#vacancies a[href^="https://www.uscourts.gov/"]') &&
      doc.getElementById("vacancies").textContent.indexOf(w.KYC.dateWords(w.kycFederal.vacancies.asOf)) !== -1);
    check("a judge the directory lists on the court carries no 'not listed' note",
      doc.querySelectorAll("#vacancies .vacancy-unlisted").length ===
        mine.vacancies.concat(mine.future || []).filter((r) => r.notInDirectory).length);
  });

  // A vacancy for senior status whose judge the directory no longer lists
  // on the court (New Mexico's, in the committed data): a reader looking
  // for them among the senior judges is told they are not there.
  const unlistedCourt = ((ca1.window.kycFederal || {}).courts || []).find((c) => c.id === "nm");
  const unlistedPage = unlistedCourt && await buildPage("courts/nm.html");
  if (unlistedPage) await settle(50);
  suite("a vacancy whose judge the directory does not list", () => {
    if (!unlistedPage) return;
    const { window: w, D: doc, errors: errs } = unlistedPage;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const flagged = (w.kycCourt.nm.vacancies || []).concat(w.kycCourt.nm.future || [])
      .filter((r) => r.notInDirectory);
    const notes = [...doc.querySelectorAll("#vacancies .vacancy-unlisted")];
    check("each such row says the directory does not list the judge, and no more",
      notes.length === flagged.length && notes.every((n) =>
        /Not listed by the FJC directory as serving on this court now/.test(n.textContent) &&
        !/retired|resigned|died/i.test(n.textContent)), `${notes.length} notes, ${flagged.length} rows`);
    check("and the judge is indeed not among the court's judges", flagged.every((r) =>
      !w.kycCourt.nm.judges.some((j) => j.name === r.vacatedBy.name)));
  });

  const guam = await buildPage("courts/gu.html");
  await settle(50);
  suite("courts/gu.html — a territorial court", () => {
    const { D: doc, errors: errs } = guam;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const text = doc.getElementById("federalBody").textContent;
    const own = guam.window.kycCourt.gu.courtList;
    check("says why its judges are not in the directory", /Article IV/.test(text) && /ten-year terms/.test(text));
    // FEDERAL-06: the judges the court's own site lists, attributed and
    // dated, never more than its seats, and nothing to open (no FJC record).
    if (own && !own.unread) {
      const names = [...doc.querySelectorAll("#courtList tbody th")].map((th) => th.textContent);
      check("its judges, as the court lists them", names.length === own.judges.length &&
        own.judges.every((j) => names.some((n) => n.startsWith(j.name))), names.join(" | "));
      check("no more than the statute's seats, at most one chief", own.judges.length <= own.seats &&
        own.judges.filter((j) => j.chief).length <= 1);
      check("attributed to the court's own website, with the day it was read",
        !!doc.querySelector('#courtList a[href="' + own.source + '"]') &&
        text.includes(guam.window.KYC.dateWords(own.read)));
      check("with no record to open", !doc.querySelector("#courtList [data-official]"));
    } else {
      check("a list never read says so, and that it is not a vacancy", /not a vacancy/.test(text));
    }
    check("and where its appeals go", !!doc.querySelector('.fed-related a[href="ca9.html"]'));
  });

  const scotus = await buildPage("courts/scotus.html");
  await settle(50);
  suite("courts/scotus.html — the Supreme Court's page", () => {
    const { window: w, D: doc, errors: errs } = scotus;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const members = w.kycFederal.supremeCourt.members.map((j) => j.id);
    const listed = [...doc.querySelectorAll("#active [data-official]")].map((b) => b.getAttribute("data-official"));
    check("the justices, the Chief Justice first", listed.join() === members.join(), listed.join());
    const retired = (w.kycFederal.supremeCourt.retired || []).length;
    check("retired justices apart", !retired || doc.querySelectorAll("#retired [data-official]").length === retired);
    check("with the date each retired", !retired || [...doc.querySelectorAll("#retired thead th")]
      .some((th) => th.textContent === "Retired"));
    // FEDERAL-11: the justices' column is "Justice", their date the oath
    // the Court lists - the same date the hub's cards give.
    const heads = [...doc.querySelectorAll("#active thead th")].map((th) => th.textContent);
    check("the justices are headed 'Justice', dated by the oath", heads[0] === "Justice" &&
      heads.includes("Took the oath") && !heads.includes("Commissioned"), heads.join(" | "));
    const first = w.kycFederal.supremeCourt.members[0];
    const cellText = (doc.querySelector('#active tbody tr [data-label="Took the oath"]') || {}).textContent;
    check("with the Court's own oath date, as on the hub",
      cellText === w.KYC.dateWords(first.justice.oath), cellText);
  });

  await testFederalAudit();
}

/* The reader-side audit of 2026-10-17 (FEDERAL-*): who sits, announced
 * vacancies, the hub's vacancies and nominees, the executive's departed
 * officers, the line of succession, the agencies' own websites. */
async function testFederalAudit() {
  const hub = await buildPage("federal/index.html");
  await settle(50);
  const { window, D, errors } = hub;
  const d = window.kycFederal;
  suite("federal/index.html — vacancies and nominees, in one place", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    const list = D.getElementById("vacancy-list");
    const rows = list ? list.querySelectorAll("tbody tr").length : 0;
    check("every vacancy, now and announced, has a row", rows === d.vacancies.rows.length,
      `${rows} rows, ${d.vacancies.rows.length} vacancies`);
    // In the courts' tables' order: by circuit, then by the name shown -
    // never by the hidden code (the District of Alaska before Alabama's).
    const circuits = d.courts.filter((c) => c.kind === "appeals").map((c) => c.circuit);
    const byId = Object.fromEntries(d.courts.map((c) => [c.id, c]));
    const shown = (tr) => tr.querySelector("th a").getAttribute("href").replace(/^.*\//, "").replace(/\.html$/, "");
    [...list.querySelectorAll("table")].forEach((t) => {
      const keys = [...t.querySelectorAll("tbody tr")].map((tr) => {
        const c = byId[shown(tr)];
        return [circuits.indexOf(c.circuit), c.kind === "appeals" ? 0 : 1, tr.querySelector("th a").textContent];
      });
      check("the " + t.querySelector("caption").textContent + " table is in the courts' order",
        keys.every((k, i) => i === 0 || (keys[i - 1][0] < k[0] || (keys[i - 1][0] === k[0] &&
          (keys[i - 1][1] < k[1] || (keys[i - 1][1] === k[1] && keys[i - 1][2] <= k[2]))))),
        keys.map((k) => k[2]).slice(0, 8).join(" | "));
    });
    check("no empty Nominated cell", ![...list.querySelectorAll('[data-label="Nominated"]')]
      .some((c) => !c.textContent.trim()));
    const summary = D.getElementById("vacancySummary").textContent;
    check("the summary counts the nominees for announced vacancies too",
      !d.vacancies.futureNominees || summary.indexOf((d.vacancies.totals.nominees + d.vacancies.futureNominees) +
        " nominees are pending in all") !== -1, summary);
    check("a judicial emergency is defined in words a phone shows, not a tooltip",
      /A judicial emergency is a vacancy the courts have designated as one/.test(summary) &&
      !D.querySelector('#courts .badge[title]'));
    // A court with announced vacancies only: not "None listed" (ca5).
    const announced = d.courts.find((c) => !c.vacancies && c.future);
    // The court's row in its table: the ladder above links the court first.
    const row = announced && D.querySelector('#courts tr a[href="../courts/' + announced.id + '.html"]').closest("tr");
    check("a court with only announced vacancies says so in its row", !announced ||
      (/announced/.test(row.querySelector('[data-label="Vacancies"]').textContent) &&
       !/None listed/.test(row.textContent)), row && row.textContent);
    // FEDERAL-V1: a judge nominated to another court is a nominee, not appointed.
    const texts = [...list.querySelectorAll('[data-label="Why"]')].map((c) => c.textContent);
    const future = d.vacancies.rows.filter((r) => r.future);
    check("no announced vacancy is told in the past tense",
      future.length > 0 && !texts.slice(texts.length - future.length).some((t) =>
        /^(Took senior status|Retired|Resigned|Appointed to another court)$/.test(t)),
      texts.slice(texts.length - future.length).join(" | "));
    const elevated = future.find((r) => r.nominatedTo);
    check("an elevation names the court the judge is nominated to", !elevated || texts.some((t) =>
      t === "Nominated to the " + elevated.nominatedTo.name.replace(/^U\.S\. /, "")), texts.join(" | "));
    // FEDERAL-17: the contradictory chief is a reader's sentence.
    const unsettled = d.courts.find((c) => c.chiefUnsettled);
    const cell = unsettled && D.querySelector('#courts a[href="../courts/' + unsettled.id + '.html"]')
      .closest("tr").querySelector('[data-label="Chief judge"]');
    check("a chief the directory contradicts reads 'Not settled', linked to why", !unsettled ||
      (/^Not settled \(see the court’s page\)$/.test(cell.textContent) &&
       !!cell.querySelector('a[href$="#chiefUnsettled"]')), cell && cell.textContent);
    // FEDERAL-24: the Article I courts are named and linked.
    const lede = D.getElementById("courtsLede");
    check("the national courts outside the directory are named and linked",
      (d.otherCourts || []).length === 4 && d.otherCourts.every((c) =>
        lede.textContent.indexOf(c.name) !== -1 && !!lede.querySelector('a[href="' + c.judges + '"]')),
      lede.textContent);
  });

  suite("federal/index.html — Varlan: senior by the courts' list, active by the directory", () => {
    const moving = d.courts.filter((c) => c.listedSenior);
    check("such a court exists in the committed data", moving.length > 0);
    moving.forEach((c) => {
      const row = D.querySelector('#courts a[href="../courts/' + c.id + '.html"]').closest("tr");
      const judges = row.querySelector('[data-label="Judges"]').textContent;
      check(c.id + ": counted senior, and the row says by which source",
        /senior by the courts’ list of vacancies, not yet by the FJC directory/.test(judges), judges);
    });
  });

  suite("federal/index.html — the executive: websites, succession, former officers", () => {
    const cards = [...D.querySelectorAll("#cabinet .fed-officer")];
    const sited = d.offices.filter((o) => o.holder && o.site);
    check("every office the directory lists a website for links it, checked or not (FEDERAL-07)",
      sited.length >= 20 && sited.every((o) => cards.some((c) =>
        c.querySelector(".fed-office").textContent === o.office &&
        !!c.querySelector('a[href="' + o.site.url + '"]'))), `${sited.length}`);
    check("no link reads 'Named there'", !/Named there/.test(D.getElementById("cabinet").textContent));
    const line = [...D.querySelectorAll("#succession .fed-succession li")];
    check("the line of succession names the Vice President, the Speaker, the President pro tempore, " +
      "then the departments", line.length === d.succession.length && line.length === 18 &&
      /Vice President/.test(line[0].textContent) && /Speaker of the House/.test(line[1].textContent) &&
      /President pro tempore/.test(line[2].textContent) && /Secretary of State/.test(line[3].textContent),
      line.map((li) => li.textContent).slice(0, 4).join(" | "));
    check("the congressional officers link to their profiles",
      d.succession.filter((p) => p.kind === "member").every((p) =>
        !!D.querySelector('#succession a[href="../index.html#/profile/' + p.id + '"]')));
    check("the acting-officer caveat is said", /3 U\.S\.C\. 19\(e\)/.test(D.getElementById("succession").textContent));
    const lede = D.querySelector("#succession .guide-lede").textContent;
    check("the Vice President succeeds by the Constitution, the rest by the statute",
      /First the Vice President \(the 25th Amendment\)/.test(lede) &&
      !/if the office and the Vice Presidency were both empty \(3 U\.S\.C\. 19\)/.test(lede), lede);
    check("an office nobody is named for says why",
      d.succession.filter((p) => p.kind === "missing").every((p) => !p.reason ||
        line.some((li) => li.textContent.indexOf(p.reason) !== -1)));
    check("no date on a Cabinet card is left as 2025-01-24",
      !/\b\d{4}-\d{2}-\d{2}\b/.test(D.getElementById("cabinet").textContent));
    // FEDERAL-13: no bare "Since 2025" beside an exact confirmation date.
    const rough = d.offices.filter((o) => (o.history || []).some((r) => r.current && r.start &&
      r.start.shown && r.start.shown.precision !== "day" && !r.actingNote));
    check("a start known only to the year says why, beside the vote's day", rough.every((o) => {
      const card = cards.find((c) => c.querySelector(".fed-office").textContent === o.office);
      const fact = card ? card.textContent : "";
      return !/In office Since \d{4}(?!-)/.test(fact) && /agree only on the (year|month)/.test(fact);
    }), rough.map((o) => o.office).join(", "));
    // FEDERAL-18: the federal posts a filer-checked OGE report lists,
    // quoted and attributed, apart from the offices two sources agree on.
    const poster = d.offices.find((o) => o.holder && ((o.holder.disclosures || {}).otherPositions || {}).rows &&
      o.holder.disclosures.otherPositions.rows.length);
    check("an officer whose OGE report lists other federal posts exists", !!poster);
    if (poster) {
      window.KYC.official.open(poster.holder.id);
      const head = [...D.querySelectorAll("#officialModal .panel-head")]
        .find((h) => /Other federal posts, as their OGE report lists them/.test(h.textContent));
      const section = head && head.closest("section");
      check("they are listed in the report's words, linked to the report",
        !!section && poster.holder.disclosures.otherPositions.rows.every((r) => section.textContent.indexOf(r) !== -1) &&
        !!section.querySelector('a[href="' + poster.holder.disclosures.otherPositions.url + '"]'),
        section && section.textContent.slice(0, 200));
      const held = [...D.querySelectorAll("#officialModal .panel-head")]
        .find((h) => /Public offices held/.test(h.textContent));
      const items = section ? [...section.querySelectorAll(".oge-positions li")] : [];
      check("'Present' is dated as the report's, never as today's",
        items.every((li) => !/Present\)/.test(li.textContent) ||
          /“Present” as of the report, posted [A-Z]/.test(li.textContent)),
        items.map((li) => li.textContent).join(" | "));
      check("and never merged into the offices two sources agree on", !!held &&
        !poster.holder.disclosures.otherPositions.rows.some((r) =>
          held.closest("section").textContent.indexOf(r) !== -1));
      window.KYC.official.close();
    }
    const former = d.former || [];
    check("the departed officers are records (FEDERAL-19)", former.length > 0 &&
      former.every((p) => window.KYC.official.officials()[p.id]));
    const bondi = former[0];
    const button = bondi && D.querySelector('#changes [data-official="' + bondi.id + '"]');
    check("their names in the changes table open them", !!button);
    if (button) {
      button.click();
      const body = D.getElementById("officialModalBody").textContent;
      check("their record opens with a banner saying they left",
        D.getElementById("officialModalName").textContent === bondi.name &&
        /^They no longer hold this office/.test(D.getElementById("officialLeft").textContent) &&
        /(Left office|Acting service ended)/.test(D.getElementById("officialModalMeta").textContent) &&
        // Said once: the subheading has the day, the banner does not repeat it.
        !/Left office/.test(D.getElementById("officialLeft").textContent) &&
        !/Nobody here by this link/.test(body), body.slice(0, 200));
      window.KYC.official.close();
    }
  });

  const tne = await buildPage("courts/tn-e.html");
  await settle(50);
  suite("courts/tn-e.html — a judge the two sources disagree about (FEDERAL-01)", () => {
    const { window: w, D: doc, errors: errs } = tne;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const moved = w.kycCourt["tn-e"].judges.filter((j) => j.listedSenior);
    check("the committed data has one", moved.length === 1);
    moved.forEach((j) => {
      check("not among the active judges", !doc.querySelector('#active [data-official="' + j.id + '"]'));
      const row = doc.querySelector('#senior [data-official="' + j.id + '"]');
      const tr = row && row.closest("tr");
      check("among the senior, with which source says what", !!tr &&
        /uscourts\.gov lists senior status from/.test(tr.textContent) &&
        /FJC directory has not recorded it yet/.test(tr.textContent), tr && tr.textContent);
      row.click();
      const meta = doc.getElementById("officialModalMeta").textContent;
      check("their dialog says both", /by the courts’ list of vacancies/.test(meta) &&
        /FJC directory still lists active service/.test(meta), meta);
      w.KYC.official.close();
    });
  });

  const lae = await buildPage("courts/la-e.html");
  await settle(50);
  suite("courts/la-e.html — a sitting judge nominated to another court (FEDERAL-V1)", () => {
    const { window: w, D: doc, errors: errs } = lae;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const later = w.kycCourt["la-e"].future || [];
    const rows = [...doc.querySelectorAll("#vacancies table")].pop();
    const why = rows ? [...rows.querySelectorAll('[data-label="Why"]')].map((c) => c.textContent) : [];
    check("an announced elevation is a nomination, never 'Appointed to another court'",
      later.length > 0 && why.length === later.length &&
      !why.some((t) => /Appointed to another court/.test(t)) && why.some((t) => /^Nominated to/.test(t)),
      why.join(" | "));
  });

  const txs = await buildPage("courts/tx-s.html");
  await settle(50);
  suite("courts/tx-s.html — confirmed, not yet commissioned (FEDERAL-25)", () => {
    const { window: w, D: doc, errors: errs } = txs;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const pending = w.kycCourt["tx-s"].pending || [];
    const section = doc.getElementById("pending");
    check("listed apart, and not counted", pending.length === 0 || (!!section &&
      pending.every((p) => section.textContent.indexOf(p.name) !== -1) &&
      !pending.some((p) => (doc.getElementById("active") || {}).textContent.indexOf(p.name) !== -1)),
      section && section.textContent.slice(0, 200));
  });

  suite("courts/tx-s.html — how to reach the court (LINKS-13, FEDERAL-21)", () => {
    const { window: w, D: doc } = txs;
    const court = w.kycFederal.courts.find((c) => c.id === "tx-s");
    const block = doc.getElementById("this-court");
    check("the court's own website is linked", !!block && !!court.site &&
      !!block.querySelector('a[href="' + court.site + '"][rel~="noopener"]'));
    check("with where to find a case", !!block.querySelector('a[href="https://pcl.uscourts.gov/"]'));
    const units = w.kycCourt["tx-s"].divisions || [];
    const items = block ? [...block.querySelectorAll(".fed-divisions > li")] : [];
    check("each division, where it sits and its counties, from 28 U.S.C. 81-131",
      units.length > 1 && items.length === units.length &&
      /Houston Division/.test(block.textContent) && /College Station/.test(block.textContent) &&
      /Harris County/.test(block.textContent), block && block.textContent.slice(0, 300));
  });

  const ISO = /\b\d{4}-\d{2}-\d{2}\b/;
  const lae2 = lae;
  suite("courts/la-e.html — the areas in Louisiana's words", () => {
    const block = lae2.D.getElementById("this-court");
    const covers = block && [...block.querySelectorAll(".fed-fact")].find((f) => /Covers/.test(f.textContent));
    const summaries = block ? [...block.querySelectorAll(".fed-counties summary")].map((x) => x.textContent) : [];
    check("parishes, never counties", !!covers && /\d+ parishes/.test(covers.textContent) &&
      !/count(y|ies)/.test(covers.textContent) && summaries.length > 0 &&
      summaries.every((x) => /^(\d+ parish(es)?|List them by name)$/.test(x)), (covers && covers.textContent) + " | " + summaries.join(" | "));
    check("a site of a district court mentions jury service", /jury service/.test(block.textContent));
  });
  const ca9 = await buildPage("courts/ca9.html");
  await settle(50);
  suite("courts/ca9.html — an appellate court's website", () => {
    const block = ca9.D.getElementById("this-court");
    check("no jury service at a court that holds no jury trials", !!block &&
      !/jury service/.test(block.textContent) && /opinions, the docket/.test(block.textContent),
      block && block.textContent.slice(0, 200));
  });
  const cod = await buildPage("courts/co.html");
  await settle(50);
  suite("courts/co.html — one division, and a judge nominated to another court", () => {
    const { window: w, D: doc, errors: errs } = cod;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const items = [...doc.querySelectorAll("#this-court .fed-divisions > li")];
    check("an undivided court's list begins with a capital", items.length === 1 &&
      /^Court is held at /.test(items[0].textContent), items.map((i) => i.textContent.slice(0, 40)).join(" | "));
    const nominated = w.kycCourt.co.judges.filter((j) => j.nominatedTo);
    check("the committed data has a judge nominated to the Tenth Circuit", nominated.length === 1 &&
      nominated[0].nominatedTo.id === "ca10");
    nominated.forEach((j) => {
      w.KYC.official.open(j.id);
      const note = doc.getElementById("officialNominated");
      check("their own record says so, dated in words", !!note &&
        /Nominated to the Court of Appeals for the Tenth Circuit/.test(note.textContent) &&
        /pending in the Senate/.test(note.textContent) && !ISO.test(note.textContent) &&
        !!note.querySelector('a[href$="ca10.html"]'), note && note.textContent);
      w.KYC.official.close();
    });
    const empty = [...doc.querySelectorAll('#vacancies [data-label="Nominated"]')]
      .filter((c) => !c.textContent.trim());
    check("no empty Nominated cell", empty.length === 0);
  });
  suite("courts/tn-e.html — dates in words in the dialog", () => {
    const { window: w, D: doc } = tne;
    const moved = w.kycCourt["tn-e"].judges.filter((j) => j.listedSenior);
    moved.forEach((j) => {
      w.KYC.official.open(j.id);
      const meta = doc.getElementById("officialModalMeta").textContent;
      check("the listed senior status is dated in words", !ISO.test(meta) && /Senior status from [A-Z]/.test(meta), meta);
      w.KYC.official.close();
    });
  });

  const county = await buildPage("counties/tx.html", { hash: "#/?county=48201" });
  await settle(50);
  suite("counties/tx.html — which federal court covers a county (FEDERAL-08)", () => {
    const { D: doc, errors: errs } = county;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const line = doc.querySelector("#localPanelBody .local-court");
    check("Harris County's panel names its district and division, linked",
      !!line && /Southern District of Texas, Houston Division/.test(line.textContent) &&
      !!line.querySelector('a[href="../courts/tx-s.html"]'), line && line.textContent);
  });
  const durham = await buildPage("counties/nc.html", { hash: "#/?county=37063" });
  await settle(50);
  suite("counties/nc.html — a county the statute splits", () => {
    const line = durham.D.querySelector("#localPanelBody .local-court");
    check("says part of it is in another district, in the statute's words",
      !!line && /Middle District of North Carolina/.test(line.textContent) && /Butner/.test(line.textContent),
      line && line.textContent);
    check("and names that district, linked",
      !!line && /Part of it \(the Federal Correctional Institution, Butner/.test(line.textContent) &&
      /is in the Eastern District of North Carolina/.test(line.textContent) &&
      !!line.querySelector('a[href="../courts/nc-e.html"]'), line && line.textContent);
  });
  const richmond = await buildPage("counties/va.html", { hash: "#/?county=51760" });
  await settle(50);
  suite("counties/va.html — an independent city the statute does not name", () => {
    const line = richmond.D.querySelector("#localPanelBody .local-court");
    const placed = (richmond.window.kycCourtCounties.VA.counties || {})["51760"] || [];
    check("says it is placed by the land around it, when it is", !!line && (placed[4] === "neighbours"
      ? /The statute does not name this city/.test(line.textContent)
      : !/The statute does not name this city/.test(line.textContent)), line && line.textContent);
  });

  const state = await buildPage("states/tx.html");
  await settle(50);
  suite("states/tx.html — the state's federal courts", () => {
    const { D: doc, errors: errs } = state;
    check("no page errors", errs.length === 0, errs.join(" | "));
    const line = doc.querySelector(".gov-federal-courts");
    check("lists its four district courts and its court of appeals, each linked",
      !!line && ["tx-n", "tx-s", "tx-e", "tx-w", "ca5"].every((id) =>
        !!line.querySelector('a[href$="courts/' + id + '.html"]')), line && line.textContent);
    check("and says where to find which covers a county",
      !!doc.querySelector('.gov-federal-courts + .faint a[href$="counties/tx.html"]'));
  });

  suite("federal/index.html — the circuit map points to the county map", () => {
    const svg = D.getElementById("circuitMap");
    const texas = svg && svg.querySelector('[data-state="TX"]');
    if (texas) texas.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
    check("a state of several districts links its county map",
      !!D.querySelector('#circuitPanel a[href="../counties/tx.html"]'), D.getElementById("circuitPanel").textContent);
  });

  const blank = await buildPage("courts/ca1.html", { block: ["judiciary/ca1.js"] });
  await settle(50);
  suite("a court page whose data did not load (FEDERAL-15)", () => {
    const text = blank.D.getElementById("federalBody").textContent;
    check("speaks to a reader, never shows a build command",
      !/python|build_profile_site/.test(text) && /could not be loaded|Loading/.test(text), text.slice(0, 200));
    // FEDERAL-12: the names written into the page stay when its data fails.
    const judges = blank.window.kycFederal.courts.find((c) => c.id === "ca1");
    check("and keeps the judges' names the page carries in its HTML",
      !!blank.D.querySelector("#federalBody .fed-prerendered") &&
      (!judges || !judges.chief || text.indexOf(judges.chief.name) !== -1), text.slice(0, 200));
  });

  const ca1Page = await buildPage("courts/ca1.html");
  await settle(50);
  suite("courts/ca1.html — who appointed the active judges (FEDERAL-22)", () => {
    const { window: w, D: doc } = ca1Page;
    const court = w.kycFederal.courts.find((c) => c.id === "ca1");
    const fig = doc.querySelector('.fed-appointers[data-court="ca1"]');
    const rows = fig ? [...fig.querySelectorAll(".fed-appointer")] : [];
    check("a row per appointing President, named in words", rows.length === court.appointers.length &&
      rows.every((r, i) => r.querySelector(".fed-appointer-name").textContent === court.appointers[i][0]),
      rows.map((r) => r.textContent).join(" | "));
    check("a square per active judge, and the count in words",
      rows.reduce((n, r) => n + r.querySelectorAll(".fed-appointer-units i").length, 0) === court.active &&
      rows.every((r, i) => r.querySelector(".fed-appointer-n").textContent.endsWith(String(court.appointers[i][1]))));
    check("no party named or coloured", !!fig && !PARTY_WORDS.test(fig.textContent) &&
      !fig.querySelector('[class*="party"]'));
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    check("its squares are a category colour, never a party's",
      /\.fed-appointer-units i \{[^}]*background: var\(--cat-1\)/.test(css));
  });

  const hubPage = await buildPage("federal/index.html");
  await settle(50);
  suite("federal/index.html — the courts of appeals by appointing President (FEDERAL-22)", () => {
    const { window: w, D: doc } = hubPage;
    const strips = doc.querySelectorAll("#appointersByCircuit .fed-appointers");
    const appeals = w.kycFederal.courts.filter((c) => c.kind === "appeals" && c.listed);
    check("one per court of appeals", strips.length === appeals.length, `${strips.length}`);
  });

  // FEDERAL-12: the names are in the HTML a crawler, or a reader without
  // script, receives - the page's own module draws over them.
  suite("the federal pages carry their names in their HTML (FEDERAL-12)", () => {
    const fed = hubPage.window.kycFederal;
    const raw = fs.readFileSync(path.join(SITE, "courts", "ca1.html"), "utf8");
    const court = fed.courts.find((c) => c.id === "ca1");
    check("a court page names its judges", !!court.chief && raw.includes(court.chief.name) &&
      /<table class="guide-table fed-table">/.test(raw));
    check("and its counts in its description", new RegExp('<meta name="description"[^>]*' +
      court.active + " active").test(raw));
    const hubRaw = fs.readFileSync(path.join(SITE, "federal", "index.html"), "utf8");
    const holder = fed.offices.find((o) => o.holder);
    check("the hub names the President, a Cabinet officer and the Chief Justice",
      hubRaw.includes(fed.president.name) && hubRaw.includes(holder.holder.name) &&
      hubRaw.includes(fed.supremeCourt.members[0].name));
    check("and the drawn page replaces them", !hubPage.D.querySelector("#federalBody .fed-prerendered"));
  });

  // FEDERAL-04, -05: a judge's article and portrait through the FJC id on
  // Wikidata, never a search; only Wikimedia's sizes of one file.
  const withLinks = (() => {
    for (const c of hubPage.window.kycFederal.courts) {
      if (!c.listed || c.kind === "supreme") continue;
      const file = path.join(SITE, "data", "judiciary", c.id + ".js");
      if (!fs.existsSync(file)) continue;
      const m = /^window\.kycCourt\[[^\]]+\] = (.*);$/m.exec(fs.readFileSync(file, "utf8"));
      if (!m) continue;
      let data;
      try { data = JSON.parse(m[1]); } catch (e) { continue; }
      const j = data.judges.find((x) => x.wikipedia && x.portrait && x.portrait.set);
      if (j) return { court: c.id, judge: j };
    }
    return null;
  })();
  if (withLinks) {
    const linked = await buildPage("courts/" + withLinks.court + ".html",
      { hash: "#/official/" + encodeURIComponent(withLinks.judge.id) });
    await settle(50);
    suite("a judge's record links their article and shows their portrait (FEDERAL-04, -05)", () => {
      const { D: doc, errors: errs } = linked;
      check("no page errors", errs.length === 0, errs.join(" | "));
      const body = doc.getElementById("officialModalBody");
      const wiki = [...body.querySelectorAll("a")].find((a) => /en\.wikipedia\.org\/wiki\//.test(a.href));
      check("the article the Wikidata item names", !!wiki &&
        decodeURIComponent(wiki.href).replace(/_/g, " ").endsWith(withLinks.judge.wikipedia), wiki && wiki.href);
      check("never a search", ![...body.querySelectorAll("a")].some((a) => /search|Special:Search/i.test(a.href)));
      check("the court's own website", [...body.querySelectorAll("a")].some((a) => /uscourts\.gov/.test(a.href)));
      const photo = doc.getElementById("officialModalPhoto");
      const urls = (photo.getAttribute("srcset") || "").split(",").map((x) => x.trim().split(" ")[0]).filter(Boolean)
        .concat([photo.getAttribute("src")]);
      const file = (/\/commons\/(?:thumb\/)?([0-9a-f]\/[0-9a-f]{2}\/[^/]+)/.exec(withLinks.judge.portrait.set[0][1]) || [])[1];
      check("a portrait, in sizes of one Wikimedia file only (rule 42)", !!file && urls.length > 1 &&
        urls.every((u) => u.startsWith("https://upload.wikimedia.org/") && u.includes(file)), urls.join(" "));
      // Rule 87: its author and licence, as the file's own page gives them,
      // on the line under the name, linked to the file.
      const credit = doc.getElementById("officialModalPhotoCredit");
      const p = withLinks.judge.portrait;
      check("a judge's Commons portrait carries its licence", !!p.licence, JSON.stringify(p));
      check("credited under the name with its author, licence and Commons, linked to the file",
        !credit.hidden && credit.textContent.indexOf((p.year && p.route === "official" ?
          "Official portrait, " + p.year + ". Photo: " : p.year ? "Photo (" + p.year + "): " : "Photo: ") +
          (p.by ? p.by + ", " :
          p.authorUnrecorded ? "author not recorded on Commons, " : "") + p.licence +
          ", via Wikimedia Commons") === 0 && !!credit.querySelector('a[href="' + p.source + '"]'),
        credit.textContent);
      // TECH-13: the 116px portrait is offered no size wider than a 2x
      // screen needs; a 3x phone fetched the Commons original.
      const widths = (photo.getAttribute("srcset") || "").split(",").map((x) =>
        parseInt(x.trim().split(" ")[1], 10)).filter((w) => w > 0);
      check("the dialog's srcset stops at the first size a 2x screen needs",
        widths.length > 0 && widths.filter((w) => w >= 232).length <= 1, widths.join(" "));
      // PR #127's review: the note says the route the links came by.
      const note = [...body.querySelectorAll("p.faint")].map((x) => x.textContent).join(" ");
      check("the links' note names the item carrying the FJC id, for a judge found that way",
        withLinks.judge.linkVia ||
        /through the Wikidata item that carries this judge’s Federal Judicial Center id/.test(note), note);
    });
  }

  // A judge no Wikidata item carries, found through the one article whose
  // {{FJC Bio}} names their nid: the note must not claim an item carries
  // the id (the review of PR #127 found it did for sixteen judges).
  const viaBio = (() => {
    for (const c of hubPage.window.kycFederal.courts) {
      if (!c.listed || c.kind === "supreme") continue;
      const file = path.join(SITE, "data", "judiciary", c.id + ".js");
      if (!fs.existsSync(file)) continue;
      const m = /^window\.kycCourt\[[^\]]+\] = (.*);$/m.exec(fs.readFileSync(file, "utf8"));
      if (!m) continue;
      let data;
      try { data = JSON.parse(m[1]); } catch (e) { continue; }
      const j = data.judges.find((x) => x.linkVia === "fjc-bio" && (x.wikipedia || x.wikidata));
      if (j) return { court: c.id, judge: j };
    }
    return null;
  })();
  if (viaBio) {
    const page = await buildPage("courts/" + viaBio.court + ".html",
      { hash: "#/official/" + encodeURIComponent(viaBio.judge.id) });
    await settle(50);
    suite("a judge found through {{FJC Bio}} says so beside their links (PR #127)", () => {
      const { D: doc, errors: errs } = page;
      check("no page errors", errs.length === 0, errs.join(" | "));
      const body = doc.getElementById("officialModalBody");
      const note = [...body.querySelectorAll("p.faint")].map((x) => x.textContent).join(" ");
      check("the note names the article citing their FJC record", /\{\{FJC Bio\}\} template/.test(note) &&
        /no Wikidata item carries the id/.test(note), note);
      check("and never claims an item carries the id",
        !/item that carries this judge’s Federal Judicial Center id/.test(note), note);
    });
  }
}

/* ============================================================ the frame */

/* What lets a reader trust the site (the 2026-10-17 audit): who runs it and
 * where every fact comes from (about.html), a way to report an error from
 * every page and dialog, a 404 page with the way back, the section each page
 * is in, and each page's own sources with the date they were read. */
const WORD_DATE = /(Jan|Feb|March|April|May|June|July|Aug|Sept|Oct|Nov|Dec)\.? \d{1,2}, \d{4}/;
const ISSUE_FORM = "https://github.com/pkplaya626/Know-Your-Candidate/issues/new?template=correction.yml";

/* ============================================================ share pages */

/* The text kyc/share.py escaped (html.escape), read back. */
function unescapeHtml(s) {
  return String(s).replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">").replace(/&#8217;/g, "\u2019").replace(/&middot;/g, "\u00b7")
    .replace(/&amp;/g, "&");
}

/* The <li data-id> of a plain list, with the standing each one is given. */
function plainItems(block) {
  return [...String(block || "").matchAll(
    /<li data-id="([^"]+)">.*?(?:<span class="share-standing">(.*?)<\/span>)?<\/li>/g)]
    .map((m) => ({ id: unescapeHtml(m[1]), standing: m[2] === undefined ? null : unescapeHtml(m[2]) }));
}

function plainList(html, attr, id) {
  const m = new RegExp('<ul class="share-list[^"]*" ' + attr + '="' + id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") +
    '">([\\s\\S]*?)</ul>').exec(html);
  return m ? plainItems(m[1]) : [];
}

/* Rule 96: a profile's and a race's share page, and a state page's plain
 * lists, are written by the pipeline (kyc/share.py) in the words the page
 * code gives the same people. Every one is compared with KYC.standing as
 * the profile dialog shows it, on the day the results were read: the day
 * the pipeline writes them for (share.post_election). Two copies of the
 * status words once drifted apart unseen (rule 63); these cannot. */
async function testSharePages() {
  const meta = readPeopleFile(path.join(SITE, "data", "people", "meta.js"));
  const asOf = String((meta.election || {}).resultsAsOf || CAMPAIGN_NOW).slice(0, 10);
  const { window, D, errors } = await buildPage("index.html", { now: asOf + "T12:00:00" });
  const KYC = window.KYC;
  const people = window.legislatorsData;
  const races = window.kycRaces;
  const read = (rel) => {
    const file = path.join(SITE, ...rel.split("/"));
    return fs.existsSync(file) ? fs.readFileSync(file, "utf8") : null;
  };
  const words = (p) => {
    const spec = KYC.standing(p, "long");
    if (!spec) return null;
    const line = KYC.ballotLine(p);
    return spec.label + (!p.isCandidate && p.contestLabel ? " for " + p.contestLabel : "") +
      (line ? " \u2013 " + line + " line" : "");
  };
  // The source a status's long title credits: its words after "Source:".
  const creditOf = (spec) => {
    const title = (spec && spec.title) || "";
    const at = title.lastIndexOf(" Source: ");
    return at === -1 ? null : title.slice(at + 9).replace(/\.$/, "");
  };
  const pageNow = new window.Date();
  const byId = new Map(people.map((p) => [p.id, p]));
  const split = (race) => {
    const ids = race.incumbentIds.concat(race.candidateIds);
    const list = ids.filter((id, i) => ids.indexOf(id) === i).map((id) => byId.get(id)).filter(Boolean);
    const moved = list.filter((p) => !p.isCandidate && race.incumbentIds.indexOf(p.id) !== -1 &&
      !!p.contestRaceId && p.contestRaceId !== race.id && !!p.contestLabel);
    const rest = list.filter((p) => moved.indexOf(p) === -1);
    return { ids, moved, running: rest.filter((p) => !KYC.offBallot(p.raceStatus)),
             out: rest.filter((p) => KYC.offBallot(p.raceStatus)) };
  };

  suite("share pages — one per profile and race, in the page code's words (rule 96)", () => {
    check("the index page loads", errors.length === 0, errors.join(" | "));
    const pFiles = new Set(fs.readdirSync(path.join(SITE, "p")));
    const rFiles = new Set(fs.readdirSync(path.join(SITE, "r")));
    // Besides each profile's own page, only a page kept at an id a profile
    // answers to (a merged filing, a filer since seated), pointing at it.
    const strays = [...pFiles].filter((f) => {
      const id = f.replace(/\.html$/, "");
      if (people.some((p) => p.id === id)) return false;
      const owner = KYC.byId(id);
      const html = read("p/" + f) || "";
      return !(owner && owner.id !== id &&
        html.indexOf('/p/' + owner.id + '.html">') !== -1 &&
        html.indexOf('id="shareView" href="../index.html#/profile/' + owner.id + '"') !== -1);
    });
    check("a share page for every profile, and none for anyone else",
      people.every((p) => pFiles.has(p.id + ".html")) && strays.length === 0,
      `${pFiles.size} pages, ${people.length} profiles; ${strays.slice(0, 4)}`);
    check("a share page for every race, and none for any other",
      rFiles.size === races.length && races.every((r) => rFiles.has(r.id + ".html")),
      `${rFiles.size} pages, ${races.length} races`);
    const wrong = [];
    const images = [];
    let photos = 0;
    people.forEach((p) => {
      const html = read("p/" + p.id + ".html") || "";
      const m = /<p class="share-status"><strong>(.*?)<\/strong><\/p>/.exec(html);
      const shown = m ? unescapeHtml(m[1]) : null;
      const want = words(p);
      if (shown !== want) wrong.push(`${p.id}: "${shown}" for "${want}"`);
      const desc = /<meta name="description" content="([^"]*)">/.exec(html);
      const spec = KYC.standing(p, "long");
      if (spec && !(desc && unescapeHtml(desc[1]).indexOf(spec.label) !== -1)) wrong.push(`${p.id}: description`);
      // Who says so: the source the dialog's badge credits (rule 19).
      const credit = /<p class="share-source faint">Source: (.*?)\.<\/p>/.exec(html);
      const said = credit ? unescapeHtml(credit[1]) : null;
      if (said !== creditOf(spec)) wrong.push(`${p.id}: source "${said}" for "${creditOf(spec)}"`);
      if (said && !(desc && unescapeHtml(desc[1]).indexOf(", per " + said) !== -1)) wrong.push(`${p.id}: description's source`);
      // Where a member leaving is going, and when a seat not up is next up.
      const other = KYC.otherOffice(p, pageNow);
      const otherShown = /<p class="share-other">(.*?)\. <span/.exec(html);
      if ((other ? other.text : null) !== (otherShown ? unescapeHtml(otherShown[1]) : null)) {
        wrong.push(`${p.id}: other office "${otherShown && otherShown[1]}"`);
      }
      const next = KYC.seated(p) && !p.seatUp2026 && p.electionYear ? "Seat up in " + p.electionYear : null;
      const nextShown = /<p class="share-next">(.*?)<\/p>/.exec(html);
      if (next !== (nextShown ? nextShown[1] : null)) wrong.push(`${p.id}: "${nextShown && nextShown[1]}" for "${next}"`);
      // A portrait only by a sourced route (rule 24): never a fallback's.
      const img = (/<meta property="og:image" content="([^"]*)">/.exec(html) || [])[1];
      const url = img ? unescapeHtml(img) : "";
      const sizes = (p.photoSet || []).map((s) => s[1]);
      // A campaign's heavy portrait unfurls as the smaller copy made here
      // (rule 101), on the site's own host, and only the copy of that file.
      const copy = p.photoCopy && p.photoCopy.of === p.photo_url ? p.photoCopy : null;
      // An office's photograph a person chose, hosted here unmodified
      // because its page draws it with no address of its own (Brent
      // Taylor's, the PR #141 review), unfurls from the site's own host.
      const host = "https://" + fs.readFileSync(path.join(SITE, "CNAME"), "utf8").trim() + "/";
      const hosted = p.photoSource === "curated" && !!p.photoCredit &&
        /^photos\/[0-9a-f]{20}\.(?:jpg|png)$/.test(p.photo_url || "");
      const ok = /\/assets\/social-card\.png$/.test(url) ||
        (hosted ? url === host + (copy ? copy.src : p.photo_url) :
        sizes.length ? sizes.indexOf(url) !== -1
          : copy && p.photoSource === "campaign-site" && !!p.photoCredit
            ? url === "https://" + fs.readFileSync(path.join(SITE, "CNAME"), "utf8").trim() + "/" + copy.src
            : url === p.photo_url && ((/^https:\/\/clerk\.house\.gov\//.test(url) &&
              (p.photoSource === "clerk.house.gov" || p.photoSource === "cross-link")) ||
            ((p.photoSource === "campaign-site" || p.photoSource === "state-legislature" ||
              p.photoSource === "curated") && !!p.photoCredit)));
      if (!ok || /Special:/.test(url)) images.push(`${p.id}: ${url}`);
      if (!/social-card/.test(url)) photos += 1;
    });
    check("every profile's share page says where they stand as the dialog does",
      wrong.length === 0, wrong.slice(0, 6).join(" | "));
    check("a share image is the person's sourced photograph or the site's card", images.length === 0 &&
      photos > 100, images.slice(0, 4).join(" | ") || `${photos} photographs`);
    const raceWrong = [];
    races.forEach((race) => {
      const html = read("r/" + race.id + ".html") || "";
      const s = split(race);
      if (s.ids.length !== new Set(s.ids).size) raceWrong.push(`${race.id}: someone twice`);
      const running = plainList(html, "data-race", race.id);
      const out = plainList(html, "data-race-out", race.id);
      const same = (got, want) => got.map((x) => x.id).join() === want.map((p) => p.id).join() &&
        got.every((x, i) => x.standing === words(want[i]));
      if (!same(running, s.running)) raceWrong.push(`${race.id}: running ${running.map((x) => x.id)}`);
      // The seat's holder is marked while they sit in it (rule 67).
      const marked = [...html.matchAll(/<li data-id="([^"]+)">[^\n]*?<span class="share-holder">/g)]
        .map((m) => unescapeHtml(m[1]));
      const holders = s.running.filter((p) => race.incumbentIds.indexOf(p.id) !== -1 && KYC.seated(p)).map((p) => p.id);
      if (marked.join() !== holders.join()) raceWrong.push(`${race.id}: holder ${marked} for ${holders}`);
      const credits = [];
      s.moved.concat(s.running, s.out).forEach((p) => {
        const c = creditOf(KYC.standing(p, "long"));
        if (c && credits.indexOf(c) === -1) credits.push(c);
      });
      const sources = /<p class="share-source faint">Where each stands: per (.*?)\.<\/p>/.exec(html);
      const andList = (w) => w.length < 2 ? w.join("") : w.slice(0, -1).join(", ") + " and " + w[w.length - 1];
      if ((sources ? unescapeHtml(sources[1]) : "") !== andList(credits)) raceWrong.push(`${race.id}: sources`);
      if (!same(out, s.out)) raceWrong.push(`${race.id}: out ${out.map((x) => x.id)}`);
      s.moved.forEach((p) => {
        if (html.indexOf('<p class="race-held">Held by <a href="../p/' + p.id + '.html">') === -1) {
          raceWrong.push(`${race.id}: held by ${p.id}`);
        }
      });
      const named = KYC.ballotSource(race);
      const others = ((race.results || {}).otherNominees || []).filter((n) => !((race.results.maybeProfiled || {})[n]));
      if (others.length && unescapeHtml(html).indexOf("Also on the November ballot, " + named) === -1) {
        raceWrong.push(`${race.id}: the names with no profile`);
      }
    });
    check("every race's share page lists its people as its section on the state page does",
      raceWrong.length === 0, raceWrong.slice(0, 6).join(" | "));
    const sample = read("p/" + people[0].id + ".html") || "";
    check("no inline script; the view is linked and opened by kyc-share.js",
      !/<script>/.test(sample) && /<script src="\.\.\/assets\/kyc-share\.js\?v=[0-9a-f]+"><\/script>/.test(sample) &&
      sample.indexOf('id="shareView" href="../index.html#/profile/' + people[0].id + '"') !== -1);
    check("its own address, title and description", /<link rel="canonical" href="https:\/\/[^/]+\/p\//.test(sample) &&
      /<meta property="og:url" content="https:\/\/[^/]+\/p\//.test(sample) &&
      sample.indexOf("<title>" + KYC.escapeHtml(people[0].name)) !== -1);
    const sizes = [...pFiles].concat([...rFiles].map((f) => "r:" + f)).map((f) =>
      fs.statSync(path.join(SITE, f.startsWith("r:") ? "r" : "p", f.replace(/^r:/, ""))).size);
    check("each share page is small", Math.max(...sizes) < 8000, `largest ${Math.max(...sizes)} bytes`);
  });

  // Every case of the status table, on both sides (PR #121 review). The
  // people in today's data hold only some statuses: "elected", "defeated",
  // "runoff" and every post-election word would first meet the page code on
  // the night a November result was read, and a word changed in kyc.js
  // alone would have held that refresh. The pipeline's answers are in
  // tests/fixtures/share_status_words.json (share.status_table; test_share
  // checks the file is current); each is asked of the page code here.
  const table = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "share_status_words.json"), "utf8"));
  const CAMPAIGN_DAY = new window.Date(2026, 9, 1, 12);
  const AFTER_DAY = new window.Date(2026, 10, 5, 12);
  suite("share pages' status words — every case, asked of the page code (rule 96)", () => {
    const off = [];
    table.statuses.forEach((row) => {
      const [status, allParty, source, own, appointed, unconfirmed, minor, post, label, gone] = row;
      const spec = KYC.raceStatus(status, "long", { own: !!own, appointed: !!appointed,
        unconfirmed: !!unconfirmed, minor: !!minor, allParty: allParty || undefined,
        source: source || undefined, now: post ? AFTER_DAY : CAMPAIGN_DAY });
      if (!spec || spec.label !== label || !!spec.off !== !!gone) {
        off.push(`${row.slice(0, 8).join("/")}: "${spec && spec.label}" for "${label}"`);
      }
    });
    check("every status, member or not, appointed, unconfirmed, minor-party, all-party, " +
      "certified or qualified, before and after Election Day", table.statuses.length > 1000 &&
      off.length === 0, off.slice(0, 4).join(" | ") || `${table.statuses.length} cases`);
    const credited = table.credits.filter(([status, source, name, credit]) =>
      creditOf(KYC.raceStatus(status, "long", { source: source || undefined,
        sourceName: name || undefined, now: CAMPAIGN_DAY })) !== credit);
    check("and the source each credits", credited.length === 0,
      credited.slice(0, 4).map((r) => r.join("/")).join(" | "));
    const filers = table.filers.filter(([fake, label, credit]) => {
      const spec = KYC.standing(Object.assign({ isCandidate: true, id: "FAKE" }, fake), "long");
      return !spec || spec.label !== label || creditOf(spec) !== credit;
    });
    check("and each filer the results do not settle", table.filers.length >= 4 && filers.length === 0,
      filers.map((r) => JSON.stringify(r)).join(" | "));
  });

  suite("state pages — written with their names before the script draws (TECH-10)", () => {
    const wrong = [];
    peopleStates().forEach((code) => {
      const html = read("states/" + code + ".html");
      if (html === null) return;
      const st = code.toUpperCase();
      const name = (meta.states[st] || {}).name;
      if (name && html.indexOf('<h1 class="state-title">' + KYC.escapeHtml(name) + "</h1>") === -1) wrong.push(`${code}: h1`);
      const block = (re) => (re.exec(html) || [])[1] || "";
      const seated = people.filter((p) => KYC.seated(p) && p.state === st);
      const senators = seated.filter((p) => p.chamber.indexOf("Senate") !== -1).map((p) => p.id);
      const house = seated.filter((p) => p.chamber.indexOf("House") !== -1)
        .sort((a, b) => KYC.districtOrder(a) - KYC.districtOrder(b)).map((p) => p.id);
      const gotSen = plainItems(block(/id="senators">([\s\S]*?)<\/section>/)).map((x) => x.id);
      const gotHouse = plainItems(block(/id="delegation">([\s\S]*?)<\/section>/)).map((x) => x.id);
      if (gotSen.join() !== senators.join()) wrong.push(`${code}: senators ${gotSen}`);
      if (gotHouse.join() !== house.join()) wrong.push(`${code}: House ${gotHouse}`);
      const mine = races.filter((r) => r.state === st);
      const order = mine.filter((r) => r.chamber === "Senate").concat(mine.filter((r) => r.chamber === "House")
        .sort((a, b) => (a.district || 0) - (b.district || 0))).map((r) => r.id);
      const got = [...html.matchAll(/<h3 class="race-title" id="race-([^"]+)">/g)].map((m) => unescapeHtml(m[1]));
      if (got.join() !== order.join()) wrong.push(`${code}: races ${got.length} for ${order.length}`);
      mine.forEach((race) => {
        const listed = plainList(html, "data-race", race.id);
        if (listed.map((x) => x.id).join() !== split(race).running.map((p) => p.id).join()) {
          wrong.push(`${code}: ${race.id}`);
        }
      });
    });
    check("every state page's h1, delegation and races are the data's", wrong.length === 0,
      wrong.slice(0, 6).join(" | "));
  });

  // Copy link: the share page's address, by the device's share sheet, the
  // clipboard, or a field to copy from by hand (TECH-09).
  const settle = () => new Promise((r) => setTimeout(r, 0));
  const someone = people.find((p) => p.isCandidate) || people[0];
  KYC.profile.open(someone.id);
  const copy = D.getElementById("profileModalCopy");
  const want = new window.URL("p/" + someone.id + ".html", window.location.href).href;
  let copied = null;
  Object.defineProperty(window.navigator, "clipboard", { configurable: true,
    value: { writeText: (t) => { copied = t; return Promise.resolve(); } } });
  copy.click();
  await settle();
  const viaClipboard = copied;
  const said = copy.textContent;
  // A second click while it says "Copied" still comes back to "Copy link".
  copy.click();
  await settle();
  await new Promise((r) => setTimeout(r, 1900));
  const back = copy.textContent;
  Object.defineProperty(window.navigator, "clipboard", { configurable: true,
    value: { writeText: () => Promise.reject(new Error("NotAllowedError")) } });
  copy.click();
  await settle(); await settle();
  const field = copy.nextElementSibling;
  const input = field && field.querySelector("input");
  const picked = !!input && D.activeElement === input &&
    input.selectionEnd - input.selectionStart === input.value.length;
  let shared = null;
  Object.defineProperty(window.navigator, "share", { configurable: true,
    value: (d) => { shared = d; return Promise.resolve(); } });
  Object.defineProperty(window.navigator, "clipboard", { configurable: true,
    value: { writeText: (t) => { copied = t; return Promise.resolve(); } } });
  // A desktop browser with a share sheet (Chrome, Edge, Safari): the button
  // says "Copy link", so it copies.
  copied = null;
  copy.click();
  await settle();
  const desktopCopied = copied;
  const desktopShared = shared;
  // A phone: its share sheet.
  const mouse = window.matchMedia;
  window.matchMedia = (q) => Object.assign(mouse(q), { matches: /pointer: coarse/.test(q) });
  copied = null;
  copy.click();
  await settle();
  window.matchMedia = mouse;
  delete window.navigator.share;
  KYC.profile.close();
  KYC.profile.open(people[1].id);
  const cleared = !(copy.nextElementSibling && copy.nextElementSibling.classList.contains("share-field"));
  suite("Copy link — the share page, shared, copied, or offered to copy (TECH-09)", () => {
    check("the clipboard gets the share page's address", viaClipboard === want, `${viaClipboard} for ${want}`);
    check("a phone opens its share sheet on the address, and copies nothing",
      copied === null && !!shared && shared.url === want && shared.title === someone.name,
      `${shared && shared.url}`);
    check("a desktop browser with a share sheet copies, as the button says",
      desktopCopied === want && desktopShared === null, `${desktopCopied} / ${desktopShared}`);
    check("the button says it was copied, then says what it does again, clicked twice or not",
      /Copied/.test(said) && /Copy link/.test(back) && !/Copied/.test(back), said + " / " + back);
    check("a refused clipboard leaves the link in a selected read-only field", !!input && input.readOnly &&
      input.value === want && picked && /Copy this link/.test(field.textContent));
    check("a dialog opened on someone else does not offer the last link", cleared);
  });
  window.close();

  // A race's own "Copy link", on a state page.
  const state = await buildPage("states/vt.html");
  let raceCopied = null;
  Object.defineProperty(state.window.navigator, "clipboard", { configurable: true,
    value: { writeText: (t) => { raceCopied = t; return Promise.resolve(); } } });
  const raceButton = state.D.querySelector("[data-share-race]");
  if (raceButton) raceButton.click();
  await settle();
  suite("a race section's Copy link", () => {
    const id = raceButton && raceButton.getAttribute("data-share-race");
    check("every race section has one", state.D.querySelectorAll(".race").length > 0 &&
      state.D.querySelectorAll(".race").length === state.D.querySelectorAll(".race [data-share-race]").length);
    check("it copies the race's share page", !!id && raceCopied ===
      new state.window.URL("../r/" + id + ".html", state.window.location.href).href, raceCopied);
    check("the script's view replaced the plain lists", !state.D.querySelector(".share-static") &&
      state.D.querySelectorAll("#stateContent .card").length > 0);
  });
  state.window.close();

  // A shared race's link (r/<raceId>.html sends a reader to the race on its
  // state page) lands on the race, and is held there while what is drawn
  // above it goes on growing, until the reader moves: on a phone it was
  // left 3,000px above CA-22 (PR #121 review). jsdom lays nothing out, so
  // the jumps themselves are counted.
  const target = races.filter((r) => r.state === "CA").slice(-1)[0] || races[races.length - 1];
  const sizes = [];
  const jumps = [];
  const landed = await buildPage("states/" + target.state.toLowerCase() + ".html", {
    hash: "#race-" + target.id,
    setup: (w) => {
      w.ResizeObserver = function (cb) {
        const me = { cb, on: false };
        sizes.push(me);
        this.observe = () => { me.on = true; };
        this.disconnect = () => { me.on = false; };
      };
      w.HTMLElement.prototype.scrollIntoView = function () { jumps.push(this.id); };
    },
  });
  await settle();
  const first = jumps.slice();
  const grow = () => sizes.forEach((o) => { if (o.on) o.cb([]); });
  grow();
  const held = jumps.length;
  landed.window.dispatchEvent(new landed.window.WheelEvent("wheel", { deltaY: -100 }));
  grow();
  suite("a shared race's link lands on its race (PR #121 review)", () => {
    check("it jumps to the race once the page is drawn", first.length === 1 &&
      first[0] === "race-" + target.id, first.join());
    check("and again when what is above it grows", held === 2 && jumps[1] === "race-" + target.id,
      jumps.join());
    check("until the reader scrolls, and then never again", jumps.length === 2 &&
      sizes.every((o) => !o.on), jumps.join());
    check("the fragment is dropped from the address", landed.window.location.hash === "",
      landed.window.location.hash);
  });
  landed.window.close();

  // A state page whose people did not load keeps its plain lists.
  const broken = await buildPage("states/vt.html", { block: ["data/people/vt.js"] });
  suite("a state page whose data did not load", () => {
    check("says so above the plain lists, which stay",
      !!broken.D.querySelector("#stateContent > .results-bar") &&
      broken.D.querySelectorAll("#stateContent .share-list li").length > 0);
  });
  broken.window.close();
}

async function testFrame() {
  const PAGES = ["index.html", "map.html", "about.html", "404.html", "states/ca.html",
    "districts/ca.html", "districts/index.html", "legislature/index.html", "legislature/nc.html",
    "counties/index.html", "counties/nc.html", "federal/index.html", "courts/index.html",
    "courts/ca9.html", "courts/gu.html", "government/index.html", "government/congress.html"];
  // The tag beside the site's name (VISUALS-01): the section, as the
  // navigation names it; "U.S. Congress" only where profiles.js says which.
  const TAGS = [["legislature/", "State legislatures"], ["counties/", "Counties & local governments"],
    ["federal/", "Federal government"], ["courts/", "Federal courts"],
    ["government/", "Know Your Government"], ["about.html", "About & sources"]];
  for (const page of PAGES) {
    const { window, D, errors } = await buildPage(page);
    await settle(30);
    const raw = fs.readFileSync(path.join(SITE, page), "utf8");
    suite(`${page} — the site's frame`, () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      check("exactly one h1", D.querySelectorAll("h1").length === 1,
        `${D.querySelectorAll("h1").length}`);
      const report = D.querySelector(".site-footer a[data-report]");
      // Aimed as it is followed, at the address the reader is on then.
      if (report) report.dispatchEvent(new window.FocusEvent("focusin", { bubbles: true }));
      check("the footer's Report a problem opens the issue form, naming this page",
        !!report && report.href.indexOf(ISSUE_FORM) === 0 &&
          report.href.indexOf("&page=" + encodeURIComponent(window.location.href)) !== -1,
        report && report.href);
      const about = [...D.querySelectorAll(".site-footer a")].find((a) => /about\.html$/.test(a.href));
      check("the footer links About & sources", !!about && about.textContent.trim() === "About & sources");
      const side = D.querySelector(".sidebar-built");
      check("the sidebar says how fresh the page is and links About & sources, out of the " +
        "grid's endless scroll", !!side && !!side.querySelector('a[href$="about.html"]'),
        side && side.textContent.replace(/\s+/g, " "));
      const congress = /<script src="(\.\.\/)?data\/people\/meta\.js/.test(raw);
      const tag = D.querySelector(".brand-sub");
      const want = TAGS.find(([prefix]) => page.indexOf(prefix) === 0);
      if (want) {
        check(`the header names the section: ${want[1]}`, !!tag && tag.textContent.trim() === want[1] &&
          !tag.hasAttribute("data-congress"), tag && tag.textContent);
      }
      check("data-congress only where the build's figures load", !tag || !tag.hasAttribute("data-congress") ||
        congress, tag && tag.outerHTML);
      if (congress && !/^government\//.test(page)) {
        check("the sidebar's build date, in words", !!side && WORD_DATE.test(side.textContent),
          side && side.textContent.replace(/\s+/g, " "));
      }
      // Structured data: a breadcrumb trail on every generated page.
      const blocks = [...D.querySelectorAll('script[type="application/ld+json"]')]
        .map((s) => { try { return JSON.parse(s.textContent); } catch (e) { return { bad: s.textContent }; } });
      check("structured data parses", blocks.every((b) => !b.bad), JSON.stringify(blocks).slice(0, 200));
      if (!/^(index|map|404)\.html$/.test(page)) {
        const crumbs = blocks.find((b) => b["@type"] === "BreadcrumbList");
        const items = (crumbs && crumbs.itemListElement) || [];
        const canonical = D.querySelector('link[rel="canonical"]').getAttribute("href");
        check("a breadcrumb trail from the site to this page", items.length >= 2 &&
          items[0].name === "Know Your Candidate" &&
          items[items.length - 1].item === canonical, JSON.stringify(items).slice(0, 300));
      }
    });
  }

  // A page's own sources, with the date each was read (TECH-12, FEDERAL-14).
  const footerOf = async (page) => {
    const { D } = await buildPage(page);
    return D.querySelector(".site-footer").textContent.replace(/\s+/g, " ");
  };
  const leg = await footerOf("legislature/nc.html");
  const county = await footerOf("counties/nc.html");
  const court = await footerOf("courts/ca9.html");
  const fed = await footerOf("federal/index.html");
  suite("each page names its own sources, dated", () => {
    check("a legislature: Open States, as read on a date", new RegExp("Open States.*as read on " +
      WORD_DATE.source).test(leg), leg);
    check("and portraits are each legislature's, not Open States' public domain",
      !/public domain/.test(leg) && /portraits as each legislature publishes them/.test(leg), leg);
    check("a county page: the 2022 Census of Governments and when its listing was read",
      new RegExp("2022 Census of Governments.*listing, read on " + WORD_DATE.source).test(county), county);
    check("a court: the FJC and uscourts.gov, dated, and not the President's or the Cabinet's",
      /Federal Judicial Center/.test(court) && /uscourts\.gov, as read on/.test(court) &&
        !/Cabinet|Vice President from/.test(court), court);
    check("the federal hub dates the executive, the judges and the vacancies",
      (fed.match(/as read on/g) || []).length >= 3, fed);
  });

  // about.html: who runs the site, and what it does with a reader's data.
  const about = await buildPage("about.html");
  suite("about.html — who runs the site, and on what", () => {
    const text = about.D.body.textContent.replace(/\s+/g, " ");
    const hrefs = [...about.D.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    check("independent and non-partisan, with no campaign, party or government tie, money or ads",
      /independent, non-partisan project/.test(text) &&
        /not affiliated with any campaign, party, candidate or government office/.test(text) &&
        /takes no money from any of them/.test(text) && /no advertising/.test(text));
    check("not an official election source, nor legal advice; ask the state's election office",
      /not an official election source/.test(text) && /legal advice/.test(text) &&
        /election office/.test(text));
    check("the repository, the MIT licence and CC BY 4.0, linked",
      hrefs.indexOf("https://github.com/pkplaya626/Know-Your-Candidate") !== -1 &&
        hrefs.some((h) => /\/blob\/main\/LICENSE$/.test(h)) &&
        hrefs.some((h) => /\/blob\/main\/LICENSE-DATA\.md$/.test(h)) &&
        /MIT/.test(text) && /CC BY 4\.0/.test(text));
    check("privacy as the code behaves: no cookies or analytics, two settings kept on the device, " +
      "the location never sent", /No cookies, no analytics/.test(text) &&
        /theme you picked and the last state you looked at/.test(text) &&
        /Neither is ever sent anywhere/.test(text) && /ZIP code/.test(text));
    check("accessibility: the standard aimed at, its limits, and how to report",
      /WCAG\)? 2\.2 at level AA/.test(text) && /Known limits/.test(text));
    check("the refresh schedule, in words", /every day from Oct\. 15 to Nov\. 2, 2026/.test(text) &&
      /every 12 hours/.test(text), (text.match(/The scheduled refresh[^.]*\./) || [""])[0]);
    const rows = [...about.D.querySelectorAll(".about-table tbody tr")];
    check("a table of every dataset: its source, what it covers, when it is read",
      rows.length >= 15 && rows.every((r) => r.querySelectorAll("td").length === 4),
      `${rows.length} rows`);
    check("each read date in words, or where the reader finds the date instead",
      rows.every((r) => { const last = r.lastElementChild.textContent.trim();
        return last === "–" || WORD_DATE.test(last) || /^(Each|In the repository)/.test(last); }),
      rows.map((r) => r.lastElementChild.textContent.trim()).join(" | "));
    const fecRow = rows.find((r) => /Who is running/.test(r.textContent));
    check("the FEC's figures say where their date is, not a dash",
      !!fecRow && /run through/.test(fecRow.lastElementChild.textContent), fecRow && fecRow.textContent);
    check("the hand-kept rosters are a source of their own, and the page does not say every fact is a script's",
      /kept by hand/.test(text) && !/Every fact is read from a source by a script/.test(text) &&
        /Most facts are read/.test(text));
    // Rule 86: the rosters' typed biographies are no longer a source.
    check("a member's biography is not said to be kept by hand",
      !rows.some((r) => /rosters in this site's repository/.test(r.textContent)) &&
        rows.some((r) => /Congressional Directory/.test(r.textContent)) &&
        !/rosters' biographies/.test(text));
    check("a report needs a GitHub account, and the page says so", /needs a free GitHub account/.test(text));
    check("the maps' limit as it is: no list of every state", /no view lists every state/.test(text) &&
      !/list beside or below/.test(text));
    check("the schedule's words: not 'the eve of the election'", !/eve of the election/.test(text));
    check("names no person and no email address", !/mailto:|@[a-z]/i.test(about.D.body.innerHTML.replace(
      /"@(context|type)"/g, "")));
  });

  // 404.html: GitHub serves it at any depth, so every address is the root's.
  const missing = await buildPage("404.html");
  suite("404.html — the way back from any address", () => {
    const local = [...missing.D.querySelectorAll("a[href], link[href], script[src]")]
      .map((e) => e.getAttribute("href") || e.getAttribute("src"))
      .filter((u) => !/^(https?:|#|mailto:)/.test(u));
    check("every local address starts at the root", local.length > 5 && local.every((u) => u[0] === "/"),
      local.filter((u) => u[0] !== "/").join(" "));
    check("a search box, and every section", !!missing.D.querySelector('form[data-site-search] input[name="q"]') &&
      missing.D.querySelectorAll(".directory-list a").length >= 9);
    check("not indexed, and not in the sitemap", !!missing.D.querySelector('meta[name="robots"][content="noindex"]') &&
      // The page's own address: share pages' ids can hold "404" (FEC_H6IL07404).
      !/\/404\.html</.test(fs.readFileSync(path.join(SITE, "sitemap.xml"), "utf8")));
  });

  // The home page answers ?q=, the address its SearchAction gives.
  const searched = await buildPage("index.html", { search: "?q=Warren" });
  await settle(80);
  suite("index.html — a search from another page, or a search engine", () => {
    const site = [...searched.D.querySelectorAll('script[type="application/ld+json"]')]
      .map((s) => JSON.parse(s.textContent)).find((b) => b["@type"] === "WebSite");
    check("the WebSite's SearchAction is the grid's ?q=", !!site &&
      /\/index\.html\?q=\{search_term_string\}$/.test(site.potentialAction.target.urlTemplate));
    check("index.html?q= fills the search", searched.D.getElementById("searchInput").value === "Warren",
      searched.D.getElementById("searchInput").value);
  });

  // The profile dialog: its report link, its title, the Senate's terms.
  const grid = await buildPage("index.html");
  await settle(50);
  suite("the profile dialog — report, title, plain words", () => {
    const { window, D } = grid;
    const KYC = window.KYC;
    const base = D.title;
    const senator = window.legislatorsData.find((p) => p.disclosureSource === "senate-efd" && p.disclosureUrl);
    check("a senator with a Senate disclosure link", !!senator);
    if (!senator) return;
    KYC.profile.open(senator.id);
    const link = D.getElementById("profileModalReport");
    link.dispatchEvent(new window.FocusEvent("focusin", { bubbles: true }));
    check("Report a problem with this profile names the profile and its address",
      !!link && link.href.indexOf(ISSUE_FORM) === 0 &&
        link.href.indexOf("&profile=" + encodeURIComponent(senator.id)) !== -1 &&
        link.href.indexOf(encodeURIComponent("#/profile/")) !== -1, link && link.href);
    check("the tab names the person while the profile is open (GRID-24)",
      D.title.indexOf(senator.name) === 0 && /Know Your Candidate$/.test(D.title), D.title);
    const disclosure = D.getElementById("profileModalDisclosure").textContent;
    check("the Senate's terms-of-use step is visible text, not a hover title (TRUST-16)",
      /Senate financial disclosure/.test(disclosure) && /accept them, then open this link again/.test(disclosure) &&
        !/eFD/.test(disclosure), disclosure);
    const age = D.getElementById("profileModalAge").textContent;
    check("a birth date in words", !/\d{4}-\d{2}-\d{2}/.test(age), age);
    const voting = D.getElementById("profileModalVoting").textContent.replace(/\s+/g, " ");
    check("the voting record in plain words, its method named after what it is",
      !/first dimension/.test(voting) && (/left-right score/.test(voting) || /No congressional voting/.test(voting)), voting);
    KYC.profile.close();
    check("closing gives the page its title back", D.title === base, D.title);
  });

  // TRUST-06: a race's statuses are Wikipedia's reading, and the race links it.
  suite("a race head links the page its statuses come from", () => {
    const { window } = grid;
    const KYC = window.KYC;
    const race = (window.kycRaces || []).find((r) => r.results && r.results.sourceUrl &&
      !r.results.fromQualifiedList);
    if (!race) { check("no race names a results page in this data; nothing to check", true); return; }
    const html = KYC.cards.raceBadges(race);
    const holder = window.document.createElement("div");
    holder.innerHTML = html;
    const a = holder.querySelector(".race-source a");
    check("Results: Wikipedia, with the day it was read, linked to the page",
      !!a && /^https:\/\/en\.wikipedia\.org\/wiki\//.test(a.getAttribute("href")) &&
        /^Results: Wikipedia/.test(a.textContent) && a.getAttribute("rel").indexOf("noopener") !== -1,
      a && a.outerHTML);
    check("and 'not the state's certified count' is page text, not only a hover",
      /not the state\u2019s certified count/.test(holder.textContent), holder.textContent);
    // The profile dialog, where a named person reads "Lost the 2026 primary",
    // links the same page (TRUST-06).
    const person = window.legislatorsData.find((p) => (p.contestRaceId || p.raceId) === race.id);
    if (person) {
      KYC.profile.open(person.id);
      const block = window.document.getElementById("profileModalRace");
      const link = block && block.querySelector(".race-source a");
      check("the profile dialog's race links the results page it was read from",
        !!link && link.getAttribute("href") === race.results.sourceUrl,
        block && block.textContent.replace(/\s+/g, " ").slice(-200));
      KYC.profile.close();
    }
    check("and the words say whose results they are", race.results.certifiedComplete
      ? KYC.ballotSource(race) === "per the " + race.results.certifiedBy
      : /^per Wikipedia's results page/.test(KYC.ballotSource(race)), KYC.ballotSource(race));
  });

  // map.html: the national views name their sources (TECH-11).
  const map = await buildPage("map.html");
  await settle(50);
  suite("map.html — each view's sources", () => {
    const { D } = map;
    const shown = () => [...D.querySelectorAll("[data-sources]")].filter((p) => !p.hidden)
      .map((p) => p.getAttribute("data-sources"));
    check("the Senate view names congress-legislators and the FEC",
      shown().length === 1 && /\bsenate\b/.test(shown()[0]), shown().join(" | "));
    D.querySelector('[data-mode="governor"]').click();
    check("a governors' view names the governors' sources instead",
      shown().length === 1 && /\bgovernor\b/.test(shown()[0]), shown().join(" | "));
    const footer = D.querySelector(".map-footer");
    const panel = D.querySelector(".detail-panel");
    check("the footer follows the state's panel in the page, so a phone reads the panel first",
      !!footer && !!panel && !!(panel.compareDocumentPosition(footer) & map.window.Node.DOCUMENT_POSITION_FOLLOWING) &&
        !footer.closest("main"));
    check("the header has the site's search, as every page does (TECH-12)",
      !!D.querySelector('.app-header form[data-site-search] input[name="q"]'));
    check("the sources line does not credit the FEC with the race set (rule 65)",
      !/the 2026 races,\s+the candidate field/.test(D.querySelector('[data-sources~="senate"]').textContent));
    check("the state-government line says what picking a state shows",
      /Pick a\s+state to see each source and the date it was read/.test(
        D.querySelector('[data-sources~="governor"]').textContent));
  });

  // The new directories: words a reader can read, under one name each.
  const districtsDir = await buildPage("districts/index.html");
  const courtsDir = await buildPage("courts/index.html");
  suite("the district and court directories", () => {
    const rows = [...districtsDir.D.querySelectorAll(".directory-row")];
    check("a state's row does not repeat its name under it",
      rows.length > 50 && rows.every((r) => {
        const name = r.querySelector(".directory-name").textContent;
        const facts = r.querySelector(".directory-facts");
        return !!facts && facts.tagName === "DIV" && facts.textContent.indexOf(name) === -1;
      }), rows.slice(0, 3).map((r) => r.textContent).join(" | "));
    check("its title, heading and breadcrumb are one name",
      districtsDir.D.querySelector("h1").textContent.trim() === "District maps" &&
        /^District maps —/.test(districtsDir.D.title));
    const headings = [...courtsDir.D.querySelectorAll("h2.state-heading")].map((h) => h.textContent.trim());
    check("each kind of court in its own plural", headings.indexOf("Courts of appeals") !== -1 &&
      headings.indexOf("District courts") !== -1 && !headings.some((h) => /ss$/.test(h)), headings.join(" | "));
    check("the courts' page is named as the navigation names it, and the navigation leads to it",
      courtsDir.D.querySelector("h1").textContent.trim() === "Federal courts" &&
        !!courtsDir.D.querySelector('.site-nav a[data-nav="courts"][href$="courts/index.html"]'));
  });

  // A senator's card speaks of the seat, never of the person's future:
  // the data knows when a term ends, not who will run (rule 61).
  suite("a senator's seat badge", () => {
    const { window } = grid;
    const KYC = window.KYC;
    const senators = window.legislatorsData.filter((p) => !p.isCandidate && /Senate/.test(p.chamber) &&
      p.electionYear && !p.seatUp2026);
    const badges = senators.map((p) => KYC.cards.statusBadge(p)).join(" ");
    check("'Seat up in <year>', never 'On the ballot in <year>'",
      senators.length > 0 && !/On the ballot in 20/.test(badges) && /Seat up in 20\d\d/.test(badges),
      badges.slice(0, 200));
    check("the build stamp is the reader's own day", KYC.localDay(new window.Date(2026, 9, 17, 23, 30)) === "2026-10-17");
  });

  // TECH-04: the footer does not paint in view and jump away.
  suite("room is kept for what the scripts draw", () => {
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    check("a district page's boxes are no wider than the panel: a one-line 'Former ...' pushed " +
      "Vermont's page past a phone's width",
      /\.district-facts \{[^}]*grid-template-columns: minmax\(0, 1fr\)/.test(css) &&
        /\.district-fact \.card-grid \{ grid-template-columns: minmax\(0, 1fr\)/.test(css));
    check("the grid, a state page and a district page hold a screen while loading",
      /#results:empty\):has\(#noResults\[hidden\]\) #results/.test(css) &&
        /#stateContent:has\(> \.results-bar:only-child\)/.test(css) &&
        /#districtsApp:has\(> \.results-bar:only-child\)/.test(css));
  });
}

/* How members voted (PERSONA-15, PROFILES-25): a member's roll calls from the
 * House Clerk's and the Senate's records, loaded on demand, the most recent
 * first, searchable by a bill's title or number, with the count of roll calls
 * the record lists them as not voting in. jsdom fetches no script, so the
 * suite loads the files as the page would have. */
function loadVotes(window) {
  ["house", "senate"].forEach((chamber) => {
    window.eval(fs.readFileSync(path.join(SITE, "data", "votes", chamber + ".js"), "utf8"));
  });
}

async function testVotes() {
  const { window, D, errors } = await buildPage("index.html", { setup: loadVotes });
  await settle(50);
  const KYC = window.KYC;
  const house = window.kycVotesHouse;
  const senate = window.kycVotesSenate;
  const text = (id) => (D.getElementById(id) || { textContent: "" }).textContent.replace(/\s+/g, " ");
  const compact = (s) => KYC.searchFold(s).replace(/[^a-z0-9]/g, "");
  const has = (file, p) => file.members[p.id] && file.members[p.id].listed >= 20;
  const member = window.legislatorsData.find((p) => !p.isCandidate && KYC.seated(p) &&
    /House/.test(p.chamber) && has(house, p) && !house.members[p.id].delegate);

  suite("profile — how a member voted (PERSONA-15)", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("each chamber's file holds its roll calls and its members' votes",
      house.rolls.length > 100 && Object.keys(house.members).length > 400 &&
        senate.rolls.length > 100 && Object.keys(senate.members).length >= 100,
      `${house.rolls.length} House, ${senate.rolls.length} Senate roll calls`);
    check("the people files do not carry them", !window.legislatorsData.some((p) => p.votes));
    KYC.profile.open(member.id);
    const entry = house.members[member.id];
    const rows = [...D.querySelectorAll("#profileModalVoteList .vote-row")];
    check("a member's dialog shows how they voted", !D.getElementById("profileModalVotesPanel").hidden &&
      /How they voted/.test(D.getElementById("profileModalVotesPanel").textContent));
    check("the ten most recent first", rows.length === 10 && (() => {
      const shown = [...entry.votes].map((c, i) => [c, i]).filter(([c]) => c !== ".")
        .map(([, i]) => i).reverse().slice(0, 10);
      return rows.every((row, k) => row.querySelector("a").href === house.rolls[shown[k]][7]);
    })(), rows.length);
    check("each with the record's word for the vote, and a link to the official record",
      rows.every((row) => Object.values(house.codes).indexOf(row.querySelector(".vote-cast").textContent) !== -1 &&
        /^https:\/\/clerk\.house\.gov\/Votes\/\d{5,8}$/.test(row.querySelector("a").href)));
    const summary = text("profileModalVotes");
    check("the roll calls the record lists them as not voting in, counted by the pipeline",
      summary.indexOf("Not voting in " + entry.notVoting.toLocaleString() + " of " +
        entry.listed.toLocaleString() + " roll calls") !== -1, summary.slice(0, 160));
    check("the record and the Congress are named", /House Clerk’s roll-call record of the \d+(st|nd|rd|th) Congress/.test(summary));
    check("the left-right score keeps its place, named as Voteview's",
      /Voting record, left to right \(Voteview\)/.test(D.getElementById("profileModal").textContent));

    // A bill's number as a reader types it.
    const index = [...entry.votes].findIndex((c, i) => c !== "." && /^H\.R\. \d+$/.test(house.rolls[i][3]));
    const measure = house.rolls[index][3];
    const input = D.getElementById("profileModalVoteSearch");
    // As a reader types it: "hr 9497" is H.R. 9497.
    input.value = measure.replace("H.R. ", "hr ");
    input.dispatchEvent(new window.Event("input", { bubbles: true }));
  });
  await settle(250);
  suite("profile — searching a member's votes", () => {
    const entry = house.members[member.id];
    const measure = D.getElementById("profileModalVoteSearch").value;
    const found = [...D.querySelectorAll("#profileModalVoteList .vote-row")];
    const want = compact(measure);
    check("a bill's number finds its votes", found.length > 0 &&
      found.every((row) => {
        const roll = house.rolls.find((r) => r[7] === row.querySelector("a").href);
        return compact(roll[3]) === want || compact(roll[4] + " " + roll[5]).indexOf(want) !== -1;
      }), measure + ": " + found.length);
    check("and never a longer number that starts the same ('H.R. 1' is not H.R. 10)",
      found.every((row) => !new RegExp("^" + want + "\\d").test(compact(row.querySelector("strong") ? row.querySelector("strong").textContent : ""))));
    check("the count says what matched", /match(es)? “/.test(text("profileModalVoteHead")));
    check("only the count is announced as the reader types, not every row",
      D.getElementById("profileModalVoteHead").getAttribute("aria-live") === "polite" &&
        !D.getElementById("profileModalVoteList").hasAttribute("aria-live"));
    const input = D.getElementById("profileModalVoteSearch");
    input.value = "zzzz no such bill";
    input.dispatchEvent(new window.Event("input", { bubbles: true }));
    void entry;
  });
  await settle(250);
  suite("profile — a search that finds nothing says so", () => {
    check("none of their votes match", /None of their votes match/.test(text("profileModalVoteHead")) &&
      !D.querySelector("#profileModalVoteList .vote-row"));
    const input = D.getElementById("profileModalVoteSearch");
    input.value = "ice";
    input.dispatchEvent(new window.Event("input", { bubbles: true }));
  });
  await settle(250);
  suite("profile — a word is searched from its start", () => {
    // 37 House titles hold "ice" inside "justice", "service", "police".
    const rows = [...D.querySelectorAll("#profileModalVoteList .vote-row")];
    check("'ICE' never finds 'justice'", rows.every((row) => {
      const roll = house.rolls.find((r) => r[7] === row.querySelector("a").href);
      return /(^|[^a-z0-9])ice/.test(KYC.searchFold([roll[3], roll[4], roll[2], roll[5]].join(" ")));
    }), rows.map((row) => row.textContent.slice(0, 60)).join(" | "));
    const input = D.getElementById("profileModalVoteSearch");
    input.value = "";
    input.dispatchEvent(new window.Event("input", { bubbles: true }));
  });
  await settle(250);
  suite("profile — more votes on request", () => {
    D.querySelector("[data-votes-more]").focus();
    D.querySelector("[data-votes-more]").click();
    const more = D.querySelectorAll("#profileModalVoteList .vote-row");
    check("ten more", more.length === 20);
    check("and the reader goes on from the first of them, not the top of the page",
      D.activeElement === more[10], D.activeElement && D.activeElement.tagName);
    check("a House number is written as the bills write it, never the Clerk's 'H R'",
      house.rolls.every((r) => !/^(H|S)( [A-Z]+)* \d+$/.test(r[3]) && !/^(QUORUM|ADJOURN)$/.test(r[3])) &&
        [...more].some((row) => /^H\.(R|Res|J\.Res|Con\.Res)\. \d+/.test(row.querySelector(".vote-what").textContent)));
    check("a placeholder is never a title (rule 10)",
      !/short title on file/i.test(text("profileModalVotes")) &&
        ![...house.rolls, ...senate.rolls].some((r) => /short title on file/i.test(r[4])));
    check("the House's two words for each vote are explained",
      /“Aye” and “No” are the House’s words on a recorded vote/.test(text("profileModalVotes")));
    KYC.profile.close();

    // Rule 17: a vote cast before a member was seated never reaches them.
    // Only while the Congress the votes are of sits (rule 68): after January
    // 3 a re-elected member's term begins after every vote of the last one.
    if (oldCongressSits(window)) {
      const late = window.legislatorsData.filter((p) => KYC.seated(p) && house.members[p.id] &&
        /House/.test(p.chamber) && String(p.term_start || "").slice(0, 10) > house.first);
      check("a member seated mid-Congress has no vote from before their seat",
        late.length > 0 && late.every((p) => [...house.members[p.id].votes].every((c, i) =>
          c === "." || house.rolls[i][1] >= String(p.term_start).slice(0, 10))),
        late.map((p) => p.name).join(", "));
    }

    const senator = window.legislatorsData.find((p) => KYC.seated(p) && /Senate/.test(p.chamber) &&
      has(senate, p));
    KYC.profile.open(senator.id);
    const link = D.querySelector("#profileModalVoteList .vote-row a");
    check("a senator's votes link the Senate's record", !!link &&
      /^https:\/\/www\.senate\.gov\/legislative\/LIS\/roll_call_votes\/vote\d{4}\/vote_\d+_\d_\d{5}\.htm$/.test(link.href),
      link && link.href);
    check("and name the Senate's record", /the Senate’s roll-call record/.test(text("profileModalVotes")));
    KYC.profile.close();

    const challenger = window.legislatorsData.find((p) => p.isCandidate && !p.incumbentId);
    KYC.profile.open(challenger.id);
    check("a challenger has no votes panel (rule 27)", D.getElementById("profileModalVotesPanel").hidden);
    KYC.profile.close();

    // A member's filing for another seat shows the member's votes, and says
    // whose record and which seat they were cast in, as the panels beside
    // it do (Andy Barr's Senate filing).
    const filing = window.legislatorsData.find((p) => p.isCandidate && p.incumbentId &&
      p.incumbentId !== p.id && KYC.byId(p.incumbentId) && KYC.seated(KYC.byId(p.incumbentId)) &&
      (house.members[p.incumbentId] || senate.members[p.incumbentId]));
    if (filing) {
      KYC.profile.open(filing.id);
      const seat = KYC.byId(filing.incumbentId).officeLabel;
      check("a member's filing for another seat says which seat its votes were cast in",
        text("profileModalVotes").indexOf("record as the member for " + seat) !== -1 &&
          D.querySelectorAll("#profileModalVoteList .vote-row").length > 0, text("profileModalVotes").slice(-160));
      KYC.profile.close();
    }

    // A member who has changed chambers since the Congress the record is of
    // (a representative seated as a senator on January 3): their votes come
    // from the chamber they sat in, which the panel names.
    const mover = window.legislatorsData.find((p) => !p.isCandidate && /House/.test(p.chamber) &&
      has(house, p) && !senate.members[p.id]);
    const was = mover && mover.chamber;
    if (mover) mover.chamber = "Senate";
    if (mover) KYC.profile.open(mover.id);
    if (mover) check("a member who changed chambers is shown the votes of the chamber they sat in, named",
      /Their votes as a member of the House in the \d+(st|nd|rd|th) Congress/.test(text("profileModalVotes")) &&
        D.querySelectorAll("#profileModalVoteList .vote-row").length === 10, text("profileModalVotes").slice(0, 200));
    KYC.profile.close();
    if (mover) mover.chamber = was;

    // When are they next up (PROFILES-25), in the card's words.
    if (oldCongressSits(window)) {
      const later = window.legislatorsData.find((p) => KYC.seated(p) && /Senate/.test(p.chamber) &&
        !p.seatUp2026 && p.electionYear);
      KYC.profile.open(later.id);
      check("a seat not on the 2026 ballot says when it next is, of the seat",
        text("profileModalStatus").indexOf("Seat up in " + later.electionYear) !== -1 &&
          !/On the ballot in/.test(text("profileModalStatus")), text("profileModalStatus"));
      KYC.profile.close();
    }
    const speaker = window.legislatorsData.find((p) => house.members[p.id] && house.members[p.id].asSpeaker);
    if (speaker) {
      KYC.profile.open(speaker.id);
      check("the Speaker's roll calls quote the House's rule beside the count",
        /House Rule I, clause 7/.test(text("profileModalVotes")) &&
          /not required to vote/.test(text("profileModalVotes")), text("profileModalVotes").slice(0, 400));
      const notes = [...D.querySelectorAll("#profileModalVotes .vote-note")].map((n) => n.textContent);
      check("the roll calls that do not list the Speaker are given their reason in the same sentence",
        !house.members[speaker.id].unlisted ||
          notes.some((n) => /does not list them at all in [\d,]+ other roll calls? held while they served: the Speaker need not vote/.test(n) &&
            /House Rule I, clause 7/.test(n)), notes.join(" | "));
      check("and no note opens on an 'It' with nothing before it", !notes.some((n) => /^It /.test(n)));
      KYC.profile.close();
    }
    const delegate = window.legislatorsData.find((p) => house.members[p.id] && house.members[p.id].delegate);
    if (delegate) {
      KYC.profile.open(delegate.id);
      check("a delegate's count says where the record lists them, with the rule",
        /Committee of the Whole/.test(text("profileModalVotes")) &&
          /House Rule III, clause 3\(a\)/.test(text("profileModalVotes")), text("profileModalVotes").slice(0, 400));
      KYC.profile.close();
    }
    check("no errors", errors.length === 0, errors.join(" | "));
  });

  // Loaded on demand from the stamped URL the page names (rule 76), and
  // "Loading" until it comes.
  const lazy = await buildPage("index.html");
  await settle(50);
  const before = lazy.D.querySelectorAll("head script[src]").length;
  const someone = lazy.window.legislatorsData.find((p) => !p.isCandidate && lazy.window.KYC.seated(p) &&
    /House/.test(p.chamber));
  lazy.window.KYC.profile.open(someone.id);
  suite("profile — a chamber's votes come on demand", () => {
    const srcs = [...lazy.D.getElementById("onDemandData").content.querySelectorAll("script")]
      .map((s) => s.getAttribute("src")).filter((s) => /votes/.test(s));
    check("the page names both chambers' files with their versions", srcs.length === 2 &&
      srcs.every((s) => /^data\/votes\/(house|senate)\.js\?v=[0-9a-f]{10}$/.test(s)), srcs.join(" "));
    const added = [...lazy.D.querySelectorAll("head script[src]")].slice(before).map((s) => s.getAttribute("src"));
    check("and fetches the House's when a representative is opened",
      added.length === 1 && added[0] === srcs.find((s) => /house/.test(s)), added.join(" "));
    check("saying so while it loads", /Loading their votes/.test(lazy.D.getElementById("profileModalVotes").textContent));
  });

  // A state page a folder down names them too, "../data/votes/...".
  const state = await buildPage("states/oh.html", { setup: loadVotes });
  await settle(80);
  suite("profile — votes on a state page", () => {
    const named = [...state.D.getElementById("onDemandData").content.querySelectorAll("script")]
      .map((s) => s.getAttribute("src"));
    const srcs = named.filter((s) => /\/votes\//.test(s));
    check("named from one folder down", srcs.length === 2 && srcs.every((s) => /^\.\.\/data\/votes\//.test(s)),
      srcs.join(" "));
    // So are the people files it does not load (rule 94): the index of
    // everyone and every other state's, never its own.
    const people = named.filter((s) => /\/people\//.test(s));
    check("and the people files it may want, from one folder down, never its own",
      people.length === peopleStates().length && people.every((s) => /^\.\.\/data\/people\/[a-z]+\.js\?v=/.test(s)) &&
        !people.some((s) => /\/oh\.js/.test(s)) && people.some((s) => /\/index\.js/.test(s)),
      people.length + " named");
    const ohio = state.window.legislatorsData.find((p) => p.state === "OH" && !p.isCandidate &&
      state.window.KYC.seated(p) && has(state.window.kycVotesHouse, p));
    state.window.KYC.profile.open(ohio.id);
    check("and the dialog shows the member's votes there",
      state.D.querySelectorAll("#profileModalVoteList .vote-row").length === 10);
  });
}

/* Money in the race, the seat's last election, the ballot side by side,
 * outside spending and the closest races (VISUALS-20, PERSONA-11/12,
 * RACES-15, VISUALS-33, GRID-17; rule 90). */
function openFold(window, details) {
  details.open = true;
  details.dispatchEvent(new window.Event("toggle"));
}

async function testRaceMoney() {
  const nc = await buildPage("states/nc.html");
  const { window, D, errors } = nc;
  const KYC = window.KYC;
  const races = [...D.querySelectorAll("section.race")];

  suite("states/nc.html — money in the race", () => {
    check("no page errors", errors.length === 0, errors.join(" | "));
    const blocks = races.map((r) => r.querySelector(".race-money")).filter(Boolean);
    check("each race with people on the ballot shows their money, open on a state page",
      blocks.length >= races.length - 1 && blocks.every((b) => b.open), blocks.length + "/" + races.length);
    const rows = blocks.flatMap((b) => [...b.querySelectorAll(".money-row")]);
    const barred = rows.filter((r) => r.querySelector(".money-bar"));
    check("a row with FEC totals draws raised, spent and cash, each labelled with its rounded figure",
      barred.length > 0 && barred.every((r) => r.querySelectorAll(".money-bar").length >= 2 &&
        [...r.querySelectorAll(".money-value")].every((v) => /^-?\$[\d.]+[KMB]?$/.test(v.textContent))),
      barred.length + " rows");
    check("every row with figures says through when (campaigns file on different days)",
      barred.every((r) => /^FEC, through [A-Z][a-z]+\.? \d{1,2}, 20\d\d$/.test(
        r.querySelector(".money-asof").textContent)));
    // The totals' source is linked to the filing, not left to the outside
    // line's link (PR #110 review).
    check("the FEC beside each campaign's totals links that candidate's filings",
      barred.every((r) => {
        const a = r.querySelector(".money-asof a");
        return !!a && /^https:\/\/www\.fec\.gov\/data\/candidate\/[HSP]\w+\/$/.test(a.href);
      }));
    check("the bars are neutral ink: no party colour on a bar, the party only in its chip",
      rows.every((r) => !r.querySelector(".money-bars [class*='party']")) &&
        rows.every((r) => !!r.querySelector(".money-who .party-chip")));
    const scaled = blocks.every((b) => {
      const widths = [...b.querySelectorAll(".money-fill")].map((f) => parseFloat(f.style.width));
      return !widths.length || (Math.max(...widths) === 100 && widths.every((w) => w >= 0 && w <= 100));
    });
    check("one scale per race: its largest figure is the full bar", scaled);
    check("raised is labelled as including loans", blocks.every((b) =>
      /Raised includes loans and transfers/.test(b.textContent)));
    const outside = D.querySelectorAll(".money-outside");
    check("outside groups' spending is each side as filed, dated and linked to the FEC, never netted",
      [...outside].every((o) => /^(?:Filed (?:under their|separately under their) (?:House|Senate) candidacy[^:]*: o|O)utside groups spent \$[\d.]+[KMB]? (supporting|opposing)/.test(o.textContent) &&
        /processed when read on/.test(o.textContent) && /fec\.gov/.test(o.querySelector("a").href) &&
        !/\bnet\b/i.test(o.textContent)), outside.length + " lines");
  });

  suite("states/nc.html — the seat's last election", () => {
    const senate = D.querySelector('section.race[id^="race-S-NC"] .race-last');
    check("the Senate seat's last election is under its race, folded",
      !!senate && !senate.open && /^Last time \(20\d\d\): .+ won by \d+\.\d points$/.test(
        senate.querySelector("summary").textContent), senate && senate.textContent.slice(0, 80));
    if (senate) {
      openFold(window, senate);
      const text = senate.textContent;
      check("it gives each share of the votes cast for a candidate, cites the Clerk and its check",
        /\d+\.\d%/.test(text) && /votes cast for a candidate/.test(text) &&
          /Statistics of the Presidential and Congressional Election/.test(text) &&
          /checked against/.test(text), text.slice(0, 300));
    }
    // North Carolina redrew its House map for 2026: no 2024 figure is
    // carried onto a new district (rule 90).
    const house = [...D.querySelectorAll('section.race[id^="race-H-NC"] .race-last')];
    check("a redrawn district says so and shows no 2024 result",
      house.length > 0 && house.every((d) => {
        openFold(window, d);
        return /not shown \(district redrawn for 2026\)/.test(d.querySelector("summary").textContent) &&
          /counted on the old lines/.test(d.textContent) && !/other voters/.test(d.textContent) &&
          !/\d+\.\d%/.test(d.textContent);
      }));
  });

  /* "The last election to this district" over a 2024 result was false
   * where a special election has filled the seat since (VA-11, AZ-7,
   * NJ-11, GA-13, GA-14), and every "Last time" becomes 2026's own from the
   * day after Election Day (PR #110 review; rule 63). */
  suite("the seat's last election: specials since, and the day after", () => {
    // Every state's races: the North Carolina page holds its own (rule 94).
    const all = allRaces();
    const specials = all.filter((r) => r.lastElection && r.lastElection.seatedSince &&
      r.lastElection.seatedSince.how === "special-election");
    const campaign = new window.Date(2026, 9, 20);
    const after = new window.Date(2026, 10, 4);
    const holder = (html) => {
      const box = D.createElement("div");
      box.innerHTML = html;
      return box;
    };
    check("the record's House specials since 2024 are marked (five while their holders sit)",
      !oldCongressSits(window) || specials.length >= 5, specials.map((r) => r.id).join(","));
    check("a seat filled by a special says its figure is the last regular election's, and who " +
      "took the seat after it",
      specials.every((r) => {
        const box = holder(KYC.cards.lastTimeBlock(r, { lazy: false, now: campaign }));
        const text = box.textContent;
        return /^Last regular election \(20\d\d\)/.test(box.querySelector("summary").textContent) &&
          text.includes(r.lastElection.seatedSince.name + " took the seat on") &&
          /after a special election whose result this site does not show/.test(text) &&
          !/The last election to this/.test(text);
      }));
    const appointed = all.filter((r) => r.lastElection && r.lastElection.seatedSince &&
      r.lastElection.seatedSince.how === "appointment");
    check("an appointee is said as one, and the counted election is still the last",
      appointed.every((r) => {
        const text = holder(KYC.cards.lastTimeBlock(r, { lazy: false, now: campaign })).textContent;
        return /by appointment\./.test(text) && /The last election to this seat before the 2026 election/.test(text);
      }), appointed.length);
    const shown = all.filter((r) => r.lastElection && r.lastElection.candidates);
    check("no fold calls a result the last election without saying before 2026's",
      shown.every((r) => !/last (regular )?election to this (district|seat)\.(?! )/.test(
        holder(KYC.cards.lastTimeBlock(r, { lazy: false, now: campaign })).textContent)));
    check("from the day after Election Day it is 'Before 2026', never 'Last time'",
      shown.every((r) => /^Before 2026/.test(holder(KYC.cards.lastTimeBlock(r,
        { lazy: false, now: after })).querySelector("summary").textContent)));
    const rcv = shown.filter((r) => r.lastElection.rankedChoice === "first-choices" &&
      r.lastElection.candidates[1]);
    check("a ranked-choice count's first choices are a lead, not a win, in the summary",
      rcv.every((r) => / led first choices by \d+\.\d points$/.test(holder(KYC.cards.lastTimeBlock(r,
        { lazy: false, now: campaign })).querySelector("summary").textContent)), rcv.length);
    const unchecked = all.filter((r) => r.lastElection && r.lastElection.withheld === "unchecked");
    check("a result the second compilation does not confirm says so, not that it was unread",
      unchecked.every((r) => /does not confirm it/.test(holder(KYC.cards.lastTimeBlock(r,
        { lazy: false })).textContent)), unchecked.length);
  });

  suite("compare the ballot: offices with their place, one renderer", () => {
    const html = KYC.officesHeldShort({ rows: [
      { office: "Mayor", where: "Burlington, Vermont", from: 1981, to: 1989, agree: "year-off" },
      { office: "Member of the Vermont House", from: 1990, to: 1991 }] }, 4);
    check("a local office keeps its place and its note", /Mayor, Burlington, Vermont/.test(html) &&
      /years differ by one/.test(html), html);
    check("an absent record is said as one", /No linked record/.test(KYC.officesHeldShort(null)));
  });

  suite("states/nc.html — compare the ballot", () => {
    const fold = D.querySelector('section.race[id^="race-S-NC"] .race-compare');
    check("a race with two or more on the ballot has a comparison, drawn only when opened",
      !!fold && !fold.querySelector("table"));
    if (fold) {
      openFold(window, fold);
      const table = fold.querySelector("table.compare-table");
      const heads = table ? [...table.querySelectorAll("thead th")].slice(1) : [];
      const rows = table ? [...table.querySelectorAll("tbody th")].map((th) => th.textContent) : [];
      check("one column per person on the ballot, each opening their profile",
        heads.length >= 2 && heads.every((th) => th.querySelector("[data-id]")), heads.length);
      check("party, offices, money, platform and site, and never net worth",
        rows.join("|") === "Party|Public offices held|Campaign money|Platform|Campaign site" &&
          !/net worth:/i.test(table.textContent.replace(/No net worth/, "")), rows.join("|"));
      check("its money carries the FEC's date", /FEC, through/.test(table.textContent));
      // Curated roster text was headed "in the campaign's words" (PR #110
      // review): each platform says where it came from.
      const platforms = table ? [...table.querySelectorAll("tbody tr")][3] : null;
      const cells = platforms ? [...platforms.querySelectorAll("td")] : [];
      check("each platform cell says its source, the roster's never as the campaign's words",
        cells.every((td, i) => {
          const list = td.querySelector(".compare-list");
          if (!list) return true;
          const from = td.querySelector(".compare-source");
          return !!from && /^(Headings from the campaign’s own site|The issues their official website lists|The issues their official website’s home page features|From the candidate’s Wikipedia article|From Wikipedia’s 2026 election page|This site’s roster summary, not the campaign’s words)$/.test(from.textContent);
        }), cells.length);
      // An absent platform says what was looked at (wave 2d review: an
      // official site's "not listed" beside a challenger's "No data").
      check("a cell with no platform says what was looked at",
        cells.every((td) => td.querySelector(".compare-list") ||
          /^(This site read their official website, not a campaign site|Nothing recorded from a campaign site or article)$/
            .test((td.querySelector(".compare-source") || {}).textContent || "")),
        cells.map((td) => td.textContent.slice(0, 60)).join(" | "));
      check("the note says a member's platform and a challenger's are not the same kind of page",
        /official website/.test(fold.querySelector(".race-note").textContent));
      // A phone gets a card per person with the same rows (wave 2d review).
      const cards = [...fold.querySelectorAll(".compare-cards > .compare-card")];
      check("a card per person, in the table's order, each with the table's rows",
        cards.length === heads.length && cards.every((c, i) =>
          c.querySelector("[data-id]") && heads[i].querySelector("[data-id]") &&
          c.querySelector("[data-id]").getAttribute("data-id") === heads[i].querySelector("[data-id]").getAttribute("data-id") &&
          [...c.querySelectorAll("dt")].map((dt) => dt.textContent).join("|") === rows.join("|")),
        `${cards.length} cards for ${heads.length} columns`);
    }
    // A member's platform is their official website's issue list (#106,
    // rule 86), "; "-joined like a campaign's headings: the comparison read
    // it as comma-split roster text and called it "this site's roster
    // summary" (found merging #110 after #106).
    // Every person the page could compare, by id: the fold is drawn only
    // when opened, so a fixture set first is what it draws.
    const byId = new Map(window.legislatorsData.map((p) => [String(p.id), p]));
    const other = D.querySelector('section.race:not([id^="race-S-NC"]) .race-compare');
    let sample = null, keep = null;
    if (other) {
      // Draw it once to see whose columns it has, then redraw with the fixture.
      openFold(window, other);
      const first = other.querySelector("table.compare-table thead th [data-id]");
      sample = first ? byId.get(first.getAttribute("data-id")) : null;
    }
    check("a race beside the Senate's has a comparison to test", !!other && !!sample);
    if (other && sample) {
      keep = { platforms: sample.platforms, fieldSources: sample.fieldSources,
        quality: sample.quality, platformFeatured: sample.platformFeatured, party: sample.party };
      // The FEC files a write-in's party as "Write-in" (six profiles do).
      sample.party = "Write-in";
      sample.platforms = "Agriculture; Health Care, Medicare and Medicaid; Veterans";
      sample.fieldSources = Object.assign({}, sample.fieldSources, { platforms: "official-site" });
      sample.quality = {};
      sample.platformFeatured = false;
      delete sample.__search;
      const section = other.closest("section.race");
      const race = window.kycRaces.find((r) => "race-" + r.id === section.id);
      const people = [...other.querySelectorAll("thead th [data-id]")]
        .map((b) => byId.get(b.getAttribute("data-id"))).filter(Boolean);
      // In the document, where the one toggle listener draws a fold.
      const holder = D.createElement("div");
      D.body.appendChild(holder);
      holder.innerHTML = race ? KYC.cards.compareBlock(race, people, { scope: "official-test" }) : "";
      const fold = holder.querySelector(".race-compare");
      if (fold) openFold(window, fold);
      const table = fold ? fold.querySelector("table.compare-table") : null;
      const ids = table ? [...table.querySelectorAll("thead th")].slice(1).map((th) => {
        const b = th.querySelector("[data-id]");
        return b ? b.getAttribute("data-id") : null;
      }) : [];
      const col = ids.indexOf(String(sample.id));
      const row = table ? [...table.querySelectorAll("tbody tr")][3] : null;
      const cell = row && col >= 0 ? row.querySelectorAll("td")[col] : null;
      const items = cell ? [...cell.querySelectorAll(".compare-list li")].map((li) => li.textContent) : [];
      check("a member's official-site platform is split on semicolons and credited to that site",
        items.length === 3 && items[1] === "Health Care, Medicare and Medicaid" &&
          cell.querySelector(".compare-source").textContent === "The issues their official website lists",
        items.join(" | ") + " / " + (cell ? cell.textContent.slice(-60) : "no cell"));
      const partyRow = table ? [...table.querySelectorAll("tbody tr")][0] : null;
      const partyCell = partyRow && col >= 0 ? partyRow.querySelectorAll("td")[col] : null;
      check("a write-in's FEC 'party' is said as a status, never as a party",
        !!partyCell && partyCell.textContent === "Write-in candidate; no party on file" &&
          !partyCell.querySelector(".party-chip"), partyCell ? partyCell.textContent : "no cell");
      holder.remove();
      Object.assign(sample, keep);
      delete sample.__search;
    }
  });

  // The CSS that keeps an open comparison scrolling inside its race: a grid
  // track sized to its content widened the section on a phone and clipped
  // the money figures beside it (PR #110 review, PA-1 at 390px). jsdom has
  // no layout, so the rule itself is checked.
  suite("kyc.css — a race's folds stay the section's width", () => {
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    check("the folds' grid has one track no wider than the section",
      /\.race-extra\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/.test(css));
    check("each fold may shrink below its content", /\.race-extra > \*\s*\{\s*min-width:\s*0;?\s*\}/.test(css));
    check("the comparison scrolls inside its box", /\.compare-scroll\s*\{[^}]*overflow-x:\s*auto/.test(css));
  });

  // Every person's: on the grid, which holds them all (rule 94).
  const whole = await buildPage("index.html");
  suite("outside spending under a member's other candidacy", () => {
    const window = whole.window;
    const D = whole.D;
    const KYC = window.KYC;
    const people = window.legislatorsData;
    const others = people.filter((p) => p.outsideSpendingOther);
    check("the campaign of a member running for the other chamber carries it (while they run)",
      !oldCongressSits(window) || others.length > 0, others.length);
    others.forEach((p) => {
      const member = people.find((m) => m.id === p.outsideSpendingOther.profileId);
      const row = holderOf(KYC.cards.moneyBlock(
        window.kycRaces.find((r) => r.id === (p.contestRaceId || p.raceId)) || { id: "x" }, [p],
        { open: true }));
      // A campaign off the ballot (a lost primary) has no money row.
      check(p.name + "'s race row shows the other candidacy's spending apart, never added in",
        !row.querySelector(".money-row") || /Filed separately under their (House|Senate) candidacy, and not added in here: outside groups spent/
          .test(row.textContent), row.textContent.slice(0, 200));
      check(p.name + "'s member line says whose candidacy it is",
        !!member && /^Filed under their (House|Senate) candidacy, not the (House|Senate) campaign they are running: /
          .test(holderOf(KYC.cards.outsideLine(member)).textContent));
    });
    function holderOf(html) {
      const box = D.createElement("div");
      box.innerHTML = html;
      return box;
    }
  });

  const grid = await buildPage("index.html", { hash: "#/?view=race" });
  await settle(100);
  suite("index.html — the races view draws a race's folds when opened", () => {
    const results = grid.D.getElementById("results");
    const money = results.querySelector(".race-money[data-fold]");
    check("money and last results are folded and empty until opened (GRID-14's budget)",
      !!money && !money.open && !money.querySelector(".money-row") &&
        !results.querySelector(".race-last[data-fold] .last-table"));
    if (money) {
      openFold(grid.window, money);
      check("opening one draws it", !!money.querySelector(".money-row"));
    }
    check("the sort menu offers closest races by each market, never both blended",
      !!grid.D.querySelector('[data-sort="close-kalshi"]') &&
        !!grid.D.querySelector('[data-sort="close-polymarket"]') &&
        /Kalshi prices/.test(grid.D.querySelector('[data-sort="close-kalshi"]').textContent));
  });

  const close = await buildPage("index.html", { hash: "#/?view=race&sort=close-kalshi" });
  await settle(100);
  suite("index.html — closest races first, by one market's prices", () => {
    const K = close.window.KYC;
    const ids = [...close.D.querySelectorAll("#results section.race")].map((s) => s.id.replace(/^race-/, ""));
    const byId = Object.fromEntries(close.window.kycRaces.map((r) => [r.id, r]));
    const gaps = ids.map((id) => K.odds.gap(byId[id], "kalshi"));
    const priced = gaps.filter(Boolean).map((g) => g.gap);
    const firstNull = gaps.findIndex((g) => !g);
    check("the races Kalshi prices come first, smallest gap first",
      priced.length > 20 && priced.every((g, i) => i === 0 || g >= priced[i - 1]) &&
        (firstNull === -1 || gaps.slice(firstNull).every((g) => !g)), priced.slice(0, 5).join(","));
    const lead = close.D.querySelector("#results .race-lead");
    check("each says it is a market price, not a poll or a forecast",
      !!lead && /Kalshi’s two highest prices: .*\d+% and .*\d+%/.test(lead.textContent) &&
        /not a poll/.test(lead.textContent), lead && lead.textContent);
    check("the races Kalshi does not price follow under a heading that says so",
      firstNull === -1 || /No usable Kalshi market/.test(close.D.getElementById("results").textContent));
    check("the view's line says what the order is", /closest first by Kalshi/.test(
      close.D.getElementById("resultsLabel").textContent));
    // A party-only market over a ballot of one party's people cannot tell
    // them apart: it is listed unranked, never "98 points apart" (rule 79).
    const blind = close.window.kycRaces.filter((r) =>
      /cannot tell them apart/.test(K.odds.render(r, { compact: false })));
    check("a party-only market over one party's ballot is not ranked",
      blind.every((r) => ["kalshi", "polymarket"].every((s) => {
        const g = K.odds.gap(r, s);
        return !g || !/^(?:(?:Democratic|Republican) [Pp]arty|Democrats?|Republicans?)$/.test(g.topLabel);
      })), blind.map((r) => r.id).join(","));
  });

  const cards = await buildPage("index.html", { hash: "#/?sort=close-polymarket" });
  await settle(100);
  suite("index.html — the cards say what a closest-first order is", () => {
    check("the cards' line names the market and says it is not a poll",
      /Cards ordered by their race, closest first by Polymarket’s prices/.test(
        cards.D.getElementById("resultsLabel").textContent) &&
        /not polls/.test(cards.D.getElementById("resultsLabel").textContent),
      cards.D.getElementById("resultsLabel").textContent);
  });

  suite("index.html — a profile's outside spending", () => {
    const person = close.window.legislatorsData.find((p) => p.outsideSpending &&
      p.outsideSpending.support && p.outsideSpending.oppose);
    check("some profile has outside spending on both sides", !!person);
    if (!person) return;
    K_open(close.window, person.id);
    const panel = close.D.getElementById("profileModalOutside");
    check("the dialog lists each side's committees as filed, with the FEC's caveat",
      !!panel && !panel.hidden && /Supporting \$/.test(panel.textContent) &&
        /Opposing \$/.test(panel.textContent) && /24- and 48-hour reports/.test(panel.textContent) &&
        !/\bnet\b(?! )/.test(panel.querySelector(".outside-sides").textContent),
      panel && panel.textContent.slice(0, 200));
    if (!panel) return;
    const summary = panel.querySelector(".outside-summary");
    check("a short line of the totals, each side's groups and the cycle, and nothing else",
      !!summary && /^Outside groups spent \$[\d.]+[KMB]? supporting \(\d+ groups?\) and \$[\d.]+[KMB]? opposing \(\d+ groups?\) in \d{4}–\d\d\.$/
        .test(summary.textContent) && !summary.querySelector("a"), summary && summary.textContent);
    const o = person.outsideSpending;
    const rows = [...panel.querySelectorAll(".outside-side")].map((side) =>
      [...side.querySelectorAll(".outside-row")].map((r) =>
        [r.querySelector(".outside-name").textContent, r.querySelector(".outside-amount").textContent]));
    check("each side's committees with their amounts in a column, their names as the FEC files them",
      rows.length === 2 && rows[0][0][0] === "Supporting" && rows[1][0][0] === "Opposing" &&
        rows[0].slice(1).map((r) => r[0]).join("|") === o.supportTop.map((c) => c.committee).join("|") &&
        rows[0].slice(1).every((r, i) => r[1] === close.window.KYC.moneyShort(o.supportTop[i].total)),
      JSON.stringify(rows).slice(0, 200));
    const note = panel.lastElementChild;
    check("the FEC's caveat, the day read and its page close the section, in the faint note style",
      note.classList.contains("outside-note") && /24- and 48-hour reports/.test(note.textContent) &&
        new RegExp("Read on " + close.window.KYC.dateWords(o.asOf).replace(/\./g, "\\.") + ": FEC\\.$")
          .test(note.textContent) && /fec\.gov/.test(note.querySelector("a").href),
      note.textContent.slice(-80));
    const css = fs.readFileSync(path.join(SITE, "assets/kyc.css"), "utf8");
    check("the section is spaced from the funding box, and its amounts are a right-aligned column",
      /\.outside-panel\s*\{\s*margin-top:\s*var\(--s-4\)/.test(css) &&
        /\.outside-row\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto/.test(css) &&
        /\.outside-amount\s*\{[^}]*text-align:\s*right/.test(css));
    close.window.KYC.profile.close();
    // A member's campaign for the other chamber: its own spending apart.
    const barr = close.window.legislatorsData.find((p) => p.outsideSpendingOther && p.outsideSpending);
    if (barr) {
      K_open(close.window, barr.id);
      const box = close.D.getElementById("profileModalOutside");
      const other = box.querySelector(".outside-summary.outside-other");
      check("the other candidacy's spending is a line of its own, never added in, and its page is linked",
        !!other && /^Filed separately under their (House|Senate) candidacy, and not added in here: outside groups spent/
          .test(other.textContent) && box.lastElementChild.querySelectorAll("a").length === 2 &&
          /FEC, (House|Senate) candidacy/.test(box.lastElementChild.textContent),
        box.textContent.slice(-200));
      close.window.KYC.profile.close();
    }
  });
}

function K_open(window, id) {
  window.KYC.profile.open(id);
}

/* ================================================================ charts
 * Audit 2026-10-17, VISUALS-21 to -35: pictures of the build's own figures,
 * drawn as boxes and page text (rule 46), never in a party's colour where
 * the thing is not a party's. */
const width = (el) => parseFloat(el.style.width);
const noSvgText = (el) => !el.querySelector("svg text");

async function testCharts() {
  {
    const { window, D, errors } = await buildPage("map.html");
    await settle(100);
    const meta = window.kycBuildMeta;
    const KYC = window.KYC;
    suite("charts — the balance of power (VISUALS-21)", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const bars = D.querySelectorAll(".balance-bar-slot .balance-bar");
      check("the sidebar draws a bar under each chamber's counts", bars.length === 2, String(bars.length));
      ["senate", "house"].forEach((chamber) => {
        const bar = D.querySelector(`.balance-bar-slot [data-chamber="${chamber}"]`);
        const seats = chamber === "senate" ? 100 : meta.house.seats;
        const sum = [...bar.querySelectorAll(".bb-seg")].reduce((n, s) => n + width(s), 0);
        check(`the ${chamber} bar's parts are the whole chamber`, Math.abs(sum - 100) < 0.01, String(sum));
        const r = [...bar.querySelectorAll(".bb-r")].reduce((n, s) => n + width(s), 0);
        check(`the ${chamber}'s Republican part is its seats' share`,
          Math.abs(r - 100 * meta[chamber].R / seats) < 0.01, `${r} for ${meta[chamber].R}`);
        check(`independents are a part of their own in the ${chamber}, never folded into a party`,
          !meta[chamber].I || !!bar.querySelector(".bb-i"));
        check(`a tick marks half the ${chamber}'s seats`, !!bar.querySelector(".bb-half"));
        check(`the ${chamber} bar says what it draws in words`,
          /Republicans?/.test(bar.querySelector(".bb-track").getAttribute("aria-label") || ""));
      });
      const senate = D.querySelector('.balance-bar-slot [data-chamber="senate"]');
      const up = meta.senate.up;
      if (up) {
        const dotted = (cls) => [...senate.querySelectorAll(".bb-up." + cls)].reduce((n, s) => n + width(s), 0);
        check("each party's Senate seats on the 2026 ballot are dotted, in its own colour",
          Math.abs(dotted("bb-r") - up.R) < 0.01 && Math.abs(dotted("bb-d") - up.D) < 0.01 &&
            Math.abs(dotted("bb-i") - up.I) < 0.01, JSON.stringify(up));
        check("the dotted seats are the races' seats", up.total === meta.election.senateSeatsUp ||
          up.total <= meta.election.senateSeatsUp, `${up.total} of ${meta.election.senateSeatsUp}`);
        check("the bar's words call its mark what it is: dotted, never hatched",
          /Dotted: the /.test(senate.textContent) && !/Hatched/.test(senate.textContent), senate.textContent);
      } else {
        check("nothing is dotted once the Congress the cycle elects sits", !senate.querySelector(".bb-up"));
      }
      check("the House bar dots nothing: every seat is on the ballot, and says so",
        !D.querySelector('.balance-bar-slot [data-chamber="house"] .bb-up'));
      check("the map's Senate view carries the Senate's bar",
        !D.getElementById("mapBalance").hidden && !!D.querySelector('#mapBalance [data-chamber="senate"]'));
      // The map has no hover on a phone: its bar prints every part's count,
      // the independents' too (wave 2d review: an unlabelled amber sliver).
      const mapCounts = D.querySelector('#mapBalance [data-chamber="senate"] .bb-counts');
      const want = [["R", "r"], ["I", "i"], ["D", "d"]].filter(([k]) => meta.senate[k])
        .map(([k, c]) => [`${meta.senate[k]} ${k}`, c]);
      check("the map's bar prints each party's count, in its party's colour",
        !!mapCounts && want.every(([t, c]) => [...mapCounts.querySelectorAll(".party-" + c)]
          .some((n) => n.textContent === t)), mapCounts ? mapCounts.textContent : "no counts");
      check("the sidebar's bar does not repeat the counts printed above it",
        !D.querySelector(".balance-bar-slot .bb-counts"));
    });

    suite("charts — the House as one square per seat (VISUALS-27)", () => {
      D.querySelector('[data-mode="house"]').click();
      check("the House view offers a choice of layout", !!D.querySelector('#mapBalance [data-layout="tiles"]'));
      D.querySelector('#mapBalance [data-layout="tiles"]').click();
      const tiles = D.getElementById("mapTiles");
      check("the squares replace the map", D.getElementById("mapStage").hidden && !tiles.hidden);
      check("the address says so", /layout=tiles/.test(window.location.hash), window.location.hash);
      const squares = tiles.querySelectorAll(".ht-seat");
      check("one square per voting seat", squares.length === meta.house.seats, String(squares.length));
      const buttons = tiles.querySelectorAll(".ht-state");
      check("every state with a vote has a block, each a button named in words",
        buttons.length === Object.keys(meta.houseTiles.states).length &&
          [...buttons].every((b) => /seats?, /.test(b.getAttribute("aria-label"))));
      check("every code above a block is page text, not SVG text", noSvgText(tiles) &&
        [...tiles.querySelectorAll(".ht-code")].every((c) => /^[A-Z]{2}$/.test(c.textContent)));
      if (oldCongressSits(window)) {
        // Who sits, counted from the profiles: the squares draw the same.
        const seated = window.legislatorsData.filter((p) => KYC.seated(p) && /House/.test(p.chamber) &&
          meta.houseTiles.states[p.state]);
        const count = (cls) => tiles.querySelectorAll(".ht-seat.ht-" + cls).length;
        check("each square is the party of whoever sits for it",
          count("r") === seated.filter((p) => KYC.partyKey(p) === "r").length &&
            count("d") === seated.filter((p) => KYC.partyKey(p) === "d").length,
          `${count("r")} R, ${count("d")} D`);
        check("an empty seat is an outlined square, as many as the chamber's vacancies",
          count("vacant") === (meta.house.vacant || 0), `${count("vacant")} vs ${meta.house.vacant}`);
      }
      tiles.querySelector('.ht-state[data-state="TX"]').click();
      check("a tap on a state's block picks it, as on the map",
        /state=TX/.test(window.location.hash) &&
          tiles.querySelector('.ht-state[data-state="TX"]').getAttribute("aria-pressed") === "true");
      D.querySelector('[data-mode="senate"]').click();
      check("the Senate view is the map again", !D.getElementById("mapStage").hidden && tiles.hidden &&
        !/layout=/.test(window.location.hash));
    });
  }

  {
    const { window, D } = await buildPage("states/index.html");
    await settle(50);
    const meta = window.kycBuildMeta;
    suite("charts — the states as a grid of links (VISUALS-35)", () => {
      const tiles = [...D.querySelectorAll(".tile-picker .tp-tile")];
      check("every state and territory page has a tile",
        tiles.length === Object.keys(meta.states).filter((c) => meta.stateGrid[c]).length &&
          tiles.length === Object.keys(meta.states).length, String(tiles.length));
      check("each tile links to its state's page and names the state for a screen reader",
        tiles.every((a) => a.getAttribute("href").endsWith(a.dataset.state.toLowerCase() + ".html") &&
          a.querySelector(".sr-only").textContent.indexOf(meta.states[a.dataset.state].name) === 0));
      const senate = new Set(window.kycRaces.filter((r) => r.chamber === "Senate").map((r) => r.state));
      check("a dot marks exactly the states with a Senate race in 2026",
        tiles.every((a) => !!a.querySelector(".tp-dot") === senate.has(a.dataset.state)));
      check("no tile is drawn in a party's colour", tiles.every((a) => !/party-/.test(a.className)));
    });
  }

  {
    const { window, D } = await buildPage("states/tx.html");
    await settle(50);
    suite("charts — a state's districts as a navigator (VISUALS-27)", () => {
      const races = window.kycRaces.filter((r) => r.state === "TX" && r.chamber === "House");
      const links = [...D.querySelectorAll(".district-tiles a")];
      check("a square per House race", links.length === races.length, `${links.length} of ${races.length}`);
      check("each square jumps to its race on the page",
        links.every((a) => !!D.getElementById(a.getAttribute("href").slice(1))));
      check("the squares are neutral: a race is not a party's",
        links.every((a) => !/party-|ht-[rd]/.test(a.className)));
    });
    suite("charts — the state government at a glance (VISUALS-28)", () => {
      const glance = D.querySelector("#state-government .state-glance");
      check("three boxes: executive, legislature, highest courts",
        !!glance && glance.querySelectorAll(".glance-box").length === 3);
      const gov = window.kycStateGov.states.TX;
      check("the governor named as the roster names them", glance.textContent.indexOf(gov.governor.name) !== -1);
      const bars = glance.querySelectorAll(".glance-bar");
      check("a bar per chamber, each the whole chamber",
        bars.length === 2 && [...bars].every((b) =>
          Math.abs([...b.querySelectorAll(".bb-seg")].reduce((n, s) => n + width(s), 0) - 100) < 0.01));
      check("the courts' box carries no party", !glance.querySelectorAll(".glance-box")[2]
        .querySelector('[class*="party-"], .bb-seg'));
      check("the ballot mark is the office's, never the holder's (rule 79)",
        !/Abbott[^.]*on the Nov 3/.test(glance.textContent) && /This office (is|was) on the Nov 3/.test(glance.textContent));
      // Rule 79 in the glance as in the section below it: the mark above a
      // governor's name with no word of whether they run read as "Brian Kemp
      // is running" (PR #111 review). Every state, from the data.
      const sg = window.KYC.stategov;
      const html = (s) => { const d = D.createElement("div"); d.innerHTML = s; return d; };
      const status = (el) => [...el.querySelectorAll(".gov-holder-status")].map((p) => p.textContent);
      const codes = Object.keys(window.kycStateGov.states);
      const differ = codes.filter((c) => {
        const g = sg.glance(c);
        if (!g) return false;
        const card = html(sg.render(c)).querySelector(".gov-card");
        return String(status(html(g))) !== String(card ? status(card) : []);
      });
      check("every state's glance says whether its governor runs, in the section's words", differ.length === 0,
        differ.join(" "));
      const after = window.KYC.electionStatus(2026).phase === "post-election";
      const said = (why) => codes.filter((c) => {
        const b = window.kycStateGov.states[c].ballot2026;
        const st = b && b.offices && b.offices.governor && b.offices.governor.up && b.offices.governor.holderStatus;
        return st && st.why === why;
      });
      const open = said("term-limit").concat(said("not-listed"));
      check("a governor's open seat is said in the glance", after || open.length === 0 ||
        open.every((c) => /Open seat: /.test(html(sg.glance(c)).textContent)), open.join(" "));
      const unchecked = said("unchecked");
      check("an unchecked holder says so in the glance", after || unchecked.length === 0 ||
        unchecked.every((c) => /not checked/.test(html(sg.glance(c)).textContent)), unchecked.join(" "));
      const territories = codes.filter((c) => window.kycStateGov.states[c].territory && sg.glance(c));
      check("a territory's glance never calls its officers statewide (rule 75)", territories.every((c) =>
        !/Statewide/.test(html(sg.glance(c)).textContent)), territories.join(" "));
      check("the glance counts regular-election seats, as the section's mark does",
        !/ \d+ seats on the Nov 3|all seats on the Nov 3/.test(glance.textContent));
    });
  }

  {
    const { window, D } = await buildPage("federal/index.html");
    await settle(50);
    suite("charts — the federal courts as a ladder (VISUALS-29)", () => {
      const courts = window.kycFederal.courts;
      const nodes = [...D.querySelectorAll(".court-ladder .cl-node")];
      const appeals = courts.filter((c) => c.kind === "appeals");
      check("the Supreme Court over every court of appeals", nodes.length === appeals.length + 1,
        String(nodes.length));
      check("every rung opens its court's page", nodes.every((a) =>
        fs.existsSync(path.join(SITE, "courts", a.getAttribute("href").replace("../courts/", "")))));
      const subs = [...D.querySelectorAll(".court-ladder a.cl-sub")];
      check("each circuit's district courts jump to their table on the page",
        subs.length > 0 && subs.every((a) => !!D.getElementById(a.getAttribute("href").slice(1))));
      const trial = courts.filter((c) => c.kind === "district" || c.kind === "territorial");
      check("the count of district courts is the courts' own",
        D.querySelector(".cl-total").textContent.indexOf(trial.length + " district courts") === 0);
      // Rule 82: a judge the courts' list has on senior status while the
      // directory counts them active is said, never folded in silently
      // (PR #111 review: the Sixth Circuit's line credited 61 to the
      // directory, which counts 62). Every circuit, from the data.
      const silent = courts.filter((c) => c.kind === "appeals").filter((c) => {
        const mine = trial.filter((t) => t.circuit === c.circuit && t.listed);
        const n = mine.reduce((k, t) => k + (t.listedSenior || 0), 0);
        const node = D.querySelector(`.court-ladder a.cl-node[href$="/${c.id}.html"]`);
        const sub = D.querySelector(`.court-ladder a.cl-sub[href="#districts-${c.id}"]`);
        const said = (el) => !!el && /senior by the courts’ list of vacancies/.test(el.textContent);
        return (n > 0 && !said(sub)) || (c.listedSenior > 0 && !said(node));
      });
      check("every circuit line holding a judge senior by the courts' list says so", silent.length === 0,
        silent.map((c) => c.id).join(" "));
      const total = trial.filter((t) => t.listed).reduce((k, t) => k + (t.listedSenior || 0), 0);
      check("the total line says so too", !total ||
        /senior by the courts’ list of vacancies/.test(D.querySelector(".cl-total").textContent));
      check("the caption does not credit the adjusted counts to the directory alone",
        !/as the directory counts them/.test(D.querySelector(".court-ladder figcaption").textContent));
      const fed = D.querySelector(".court-ladder .cl-note");
      check("the Federal Circuit's line names the district courts' patent appeals and cites the statute",
        !fed || (/patent cases from every district court/.test(fed.textContent) &&
          /uscode\/text\/28\/1295$/.test(fed.querySelector("a").getAttribute("href"))));
    });
  }

  {
    const { window, D } = await buildPage("courts/ca9.html");
    await settle(50);
    suite("charts — a court's bench by year (VISUALS-30)", () => {
      const fig = D.querySelector(".bench-timeline");
      const judges = (window.kycCourt.ca9.judges || []).filter((j) => j.status !== "senior" && !j.listedSenior);
      const dated = judges.filter((j) => (j.seats || []).some((s) => s.court === "ca9" && s.commissioned));
      check("a dot per active judge with a commission", !!fig && fig.querySelectorAll(".bt-dot").length === dated.length,
        `${fig && fig.querySelectorAll(".bt-dot").length} of ${dated.length}`);
      check("a row per appointing President, named in page text", !!fig &&
        [...fig.querySelectorAll(".bt-name")].filter((n) => n.textContent).length ===
          new Set(dated.map((j) => j.seats.filter((s) => s.court === "ca9")[0].appointedBy)).size);
      check("one neutral ink: no party anywhere in it", !!fig && !fig.querySelector('[class*="party-"]'));
      const years = [...fig.querySelectorAll(".bt-ticks span")].map((s) => +s.textContent);
      const latest = Math.max(...dated.map((j) => +j.seats.filter((s) => s.court === "ca9")[0].commissioned.slice(0, 4)));
      check("the axis ends where the bench does, never years ahead", years.length > 1 &&
        Math.max(...years) <= latest + 1, `${years.join(",")} for ${latest}`);
      // Inset by the dot's radius, so the latest judge's dot stays on the
      // rule (wave 2d review: past its end at 390px).
      const lefts = [...fig.querySelectorAll(".bt-dot, .bt-ticks span")].map((s) => s.getAttribute("style") || "");
      const inside = lefts.every((l) => {
        const m = /left:\s*calc\(5px \+ \(100% - 10px\) \* ([\d.]+)\)/.exec(l);
        return m && +m[1] >= 0 && +m[1] <= 1;
      });
      check("every dot and tick is placed inside the track by a dot's radius", inside,
        lefts.filter((l) => !/calc\(5px/.test(l)).slice(0, 3).join(" | "));
    });
  }

  {
    const { D } = await buildPage("counties/index.html");
    suite("charts — local governments by kind (VISUALS-32)", () => {
      const rows = [...D.querySelectorAll("tbody tr")];
      check("a bar under every state's name", rows.length > 0 && rows.every((tr) => tr.querySelector(".lg-bar")));
      const hawaii = rows.find((tr) => /Hawaii/.test(tr.querySelector("th").textContent));
      check("a kind the state has none of is a word under the bar, never a zero-length part (rule 49)",
        !!hawaii && !hawaii.querySelector(".lg-township") && /None: .*town/.test(hawaii.textContent));
    });
  }

  {
    const { window, D } = await buildPage("index.html");
    await settle(50);
    const KYC = window.KYC;
    suite("charts — funding sources as one bar (VISUALS-24)", () => {
      const who = window.legislatorsData.find((p) => p.fundingBreakdown && !p.fundingBase &&
        Object.keys(p.fundingBreakdown).length >= 3);
      KYC.profile.open(who.id);
      const bar = D.querySelector("#profileModalFunding .funding-bar");
      const parts = Object.values(who.fundingBreakdown).filter((v) => v > 0);
      check("a part per kind of receipt", !!bar && bar.querySelectorAll(".fs-seg").length === parts.length);
      const sum = bar ? [...bar.querySelectorAll(".fs-seg")].reduce((n, s) => n + width(s), 0) : 0;
      check("the parts are shares of what the shares are of, never more", sum <= 100.01 && sum > 95, String(sum));
      check("each share named beside a swatch of its tone",
        D.querySelectorAll("#profileModalFunding .funding-part .fs-swatch").length === parts.length);
      check("never a party's colour", !bar.querySelector('[class*="party-"], [class*="odds-seg"]'));
      KYC.profile.close();
    });

    suite("charts — polling averages as dots (VISUALS-34)", () => {
      const odds = window.kycOdds || { races: {} };
      const raceIds = Object.keys(odds.races).filter((id) => (odds.races[id].polls || {}).rows &&
        odds.races[id].polls.rows.length && (odds.races[id].markets || []).length);
      let checked = 0;
      let inOrder = 0;
      raceIds.forEach((id) => {
        const race = (window.kycRaces || []).find((r) => r.id === id);
        if (!race) return;
        const box = D.createElement("div");
        box.innerHTML = KYC.odds.render(race, {});
        const rows = box.querySelectorAll(".poll-row");
        if (rows.length !== odds.races[id].polls.rows.length) return;
        checked += 1;
        // The key's order against the first coherent market's, by party.
        const market = (box.querySelector(".odds-market .odds-legend") || { querySelectorAll: () => [] });
        const marketParties = [...market.querySelectorAll(".odds-dot")].map((d) => d.className.match(/odds-seg-(\w)/)[1])
          .filter((p) => p !== "i");
        const keyParties = [...box.querySelectorAll(".poll-key .poll-dot")].map((d) => d.className.match(/odds-seg-(\w)/)[1])
          .filter((p) => p !== "i");
        const firstOf = (list) => list.filter((p, i) => list.indexOf(p) === i);
        const m = firstOf(marketParties);
        const k = firstOf(keyParties);
        if (m.length < 2 || k.length < 2 || marketParties.length !== m.length || keyParties.length !== k.length) {
          inOrder += 1;
          return;
        }
        if (m.filter((p) => k.indexOf(p) !== -1).join() === k.filter((p) => m.indexOf(p) !== -1).join()) inOrder += 1;
      });
      check("every race with polling averages draws a dot row per aggregator", checked === raceIds.length &&
        checked > 0, `${checked} of ${raceIds.length}`);
      check("the candidates come in the market bars' order", inOrder === checked, `${inOrder} of ${checked}`);
      // A ten-point axis made 49.7 against 47.4 look like a wide gap (PR
      // #111 review); the compact line already prints its two figures.
      const narrow = raceIds.filter((id) => {
        const race = (window.kycRaces || []).find((r) => r.id === id);
        if (!race) return false;
        const box = D.createElement("div");
        box.innerHTML = KYC.odds.render(race, {});
        const ticks = [...box.querySelectorAll(".poll-ticks span")].map((s) => parseFloat(s.textContent));
        return ticks.length < 2 || Math.max(...ticks) - Math.min(...ticks) < 30;
      });
      check("every poll axis spans at least thirty points", narrow.length === 0, narrow.join(" "));
      const compact = raceIds.map((id) => (window.kycRaces || []).find((r) => r.id === id)).filter(Boolean)
        .filter((race) => { const b = D.createElement("div"); b.innerHTML = KYC.odds.render(race, { compact: true });
          return !!b.querySelector(".poll-dots"); });
      check("the compact panel prints the line, not a one-row chart of it", compact.length === 0,
        compact.map((r) => r.id).join(" "));
    });
  }
}

/* ============================================================ Your ballot */

/* ballot.html (kyc-ballot.js, rule 92): every contest on one reader's
 * ballot, from a ZIP code in the address or a location. */
async function ballotFor(hash, opts) {
  const built = await buildPage("ballot.html", Object.assign({ hash }, opts || {}));
  const out = built.D.getElementById("ballotResult");
  await until(() => out && !out.hidden && !/Looking up|Finding your location/.test(out.textContent), 8000);
  return Object.assign(built, { out, text: out ? out.textContent : "" });
}

/** A contest's card by its heading's first words. */
function contestsOf(out) {
  return [...out.querySelectorAll(".ballot-contest")].map((li) => ({
    li,
    office: li.querySelector(".ballot-office").firstChild.textContent.trim(),
    seat: (li.querySelector(".ballot-seat") || { textContent: "" }).textContent.trim(),
  }));
}

const badgeWords = (el) => [...el.querySelectorAll(".badge")].map((b) => b.textContent.trim());

async function testBallot() {
  // A redrawn state's ZIP code that touches two districts on the 2026 map:
  // Frisco, Texas (75036), in TX-26 and TX-4.
  // A browser that can share a location, so the page offers it.
  const tx = await ballotFor("#/?zip=75036", { setup: at(0, 0, 1) });
  const txState = await buildPage("states/tx.html");
  await settle(50);
  suite("Your ballot: a ZIP code across two House districts in a redrawn state", () => {
    const { window, out, errors } = tx;
    check("no page errors", errors.length === 0, errors.join(" | "));
    check("the page asked the lookup itself, from the ZIP code in its address",
      /Your ballot: ZIP 75036, Texas/.test(tx.text), tx.text.slice(0, 200));
    check("its address carries the ZIP code, and nothing else", window.location.hash === "#/?zip=75036",
      window.location.hash);
    const entry = window.kycLookup.TX.zips["75036"];
    const shares = (entry.next || []).filter((p) => p[1] < window.kycLookupIndex.whole);
    const cards = contestsOf(out);
    const house = cards.filter((c) => c.office === "U.S. House");
    check("one House card per district the ZIP area reaches on the 2026 map",
      house.length === entry.next.length && entry.next.length > 1,
      house.map((c) => c.seat).join(" | "));
    check("each with its share of the ZIP area's land", house.every((c) =>
      /of ZIP 75036.s land is in this district/.test(c.li.textContent)) && shares.length > 1);
    check("each named on the 2026 map", house.every((c) => /on the 2026 map/.test(c.seat)) ||
      window.KYC.recordPhase());
    check("the caveat, and the way to an exact answer: the reader's location",
      /crosses district lines/.test(tx.text) &&
      !!out.querySelector(".ballot-state [data-ballot-locate]"));
    const order = cards.map((c) => c.li.className.match(/ballot-(federal|statewide|legislature|measures)/)[1]);
    const rank = { federal: 0, statewide: 1, legislature: 2, measures: 3 };
    check("in ballot order: Congress, statewide offices, the legislature, the questions",
      order.every((k, i) => !i || rank[order[i - 1]] <= rank[k]) && order[0] === "federal" &&
      order.indexOf("statewide") !== -1 && order.indexOf("legislature") !== -1, order.join(","));
    check("the Senate first among them", cards[0].office === "U.S. Senate");
    // The same people, order, words and count as the state page's race
    // sections (rules 12 and 73): each race card against its section.
    const D2 = txState.D;
    const differ = [];
    cards.filter((c) => c.li.id && /^contest-[SH]-/.test(c.li.id)).forEach((c) => {
      const id = c.li.id.replace(/^contest-/, "");
      const section = D2.getElementById("race-" + id);
      if (!section) return differ.push(id + ": no section");
      // The ballot lists those on it first and those whose ballot status
      // is not known apart (PR #115 review), each in the section's order.
      // A race that can fold keeps its section in a body under its row.
      const theirCards = [...section.querySelectorAll(":scope > .card-grid .card, " +
        ":scope > .race-body > .card-grid .card")];
      const theirs = theirCards.map((n) => n.querySelector(".card-name").textContent);
      const listed = [...c.li.querySelectorAll(".ballot-people:not(.ballot-unsure) .ballot-person .link-button")]
        .map((n) => n.textContent);
      const unsure = [...c.li.querySelectorAll(".ballot-unsure .ballot-person .link-button")].map((n) => n.textContent);
      const ours = listed.concat(unsure);
      const expect = theirs.filter((n) => listed.includes(n)).concat(theirs.filter((n) => unsure.includes(n)));
      if (JSON.stringify(expect) !== JSON.stringify(ours) || ours.length !== theirs.length) {
        differ.push(id + ": " + ours + " / " + theirs);
      }
      const head = section.querySelector(".race-head");
      if (JSON.stringify(badgeWords(head)) !== JSON.stringify(badgeWords(c.li.querySelector(".ballot-badges")))) {
        differ.push(id + " badges: " + badgeWords(c.li.querySelector(".ballot-badges")) + " / " + badgeWords(head));
      }
      const statusOf = {};
      theirCards.forEach((n) => { statusOf[n.querySelector(".card-name").textContent] = badgeWords(n).join("+"); });
      const theirStatus = ours.map((n) => statusOf[n]);
      const ourStatus = [...c.li.querySelectorAll(".ballot-people:not(.ballot-unsure) .ballot-person, .ballot-unsure .ballot-person")]
        .map((n) => badgeWords(n).join("+"));
      if (JSON.stringify(theirStatus) !== JSON.stringify(ourStatus)) differ.push(id + " status: " + ourStatus + " / " + theirStatus);
    });
    check("each race lists the race section's people, in its order, with its status words and counts",
      differ.length === 0, differ.join(" || "));
    check("each person opens their profile here", (() => {
      const b = out.querySelector(".ballot-person .link-button");
      if (!b) return false;
      b.click();
      return window.location.hash === "#/profile/" + encodeURIComponent(b.getAttribute("data-id"));
    })());
    const leg = cards.filter((c) => /ballot-legislature/.test(c.li.className));
    check("the state legislature: each chamber's district, and whether its seat is up, from the record",
      leg.length === 2 && leg.every((c) => c.li.querySelector(".leg-ballot")), leg.map((c) => c.office).join(" | "));
    const senate = leg[0].li;
    const sid = senate.querySelector(".ballot-district").getAttribute("href").match(/d=([^&]+)$/)[1];
    const leg2 = Object.values(window.kycLegislature || {})[0];
    check("a seat the record says is not up is said so, never guessed",
      !leg2 || leg2.chambers.upper.districts[decodeURIComponent(sid)].up !== false ||
      /not up for regular election in 2026/.test(senate.textContent), senate.textContent.slice(0, 200));
    check("legislative candidates are not listed here, and said so",
      /candidates for (this seat|these seats) are not listed here/.test(tx.text));
    check("local ballot questions and local contests: not listed here",
      /Also on your ballot, not listed here/.test(tx.text) && /local ballot questions/.test(tx.text));
    check("the key dates, passed ones said passed on the reader's day",
      !!out.querySelector(".ballot-dates .vote-dates") && /Passed/.test(out.querySelector(".ballot-dates").textContent));
    check("and the way to how to vote in Texas", !!out.querySelector('.ballot-dates a[href$="states/tx.html#voting"]'));
  });

  // Georgia: a Senate race and an open governor's seat with its listed
  // candidates; a ZIP code typed into the page.
  const ga = await buildPage("ballot.html");
  const slot = ga.D.getElementById("ballotAsk");
  slot.querySelector("#ballotZip").value = "30009";
  slot.querySelector("form").dispatchEvent(new ga.window.Event("submit", { bubbles: true, cancelable: true }));
  const gaOut = ga.D.getElementById("ballotResult");
  await until(() => !/Looking up/.test(gaOut.textContent) && gaOut.querySelector(".ballot-state"), 8000);
  suite("Your ballot: Georgia, a Senate race and an open governor's seat", () => {
    const { window } = ga;
    const cards = contestsOf(gaOut);
    check("a typed ZIP code is written into the address, for a copied link", window.location.hash === "#/?zip=30009",
      window.location.hash);
    check("the U.S. Senate race", cards.some((c) => c.office === "U.S. Senate" && c.li.querySelector(".ballot-person")));
    const gov = cards.find((c) => c.office === "Governor");
    const listed = window.kycStateGov.states.GA.ballot2026.offices.governor.candidates.candidates;
    check("the governor's office, marked on the ballot from the state's record",
      !!gov && /This office is on the Nov 3, 2026 ballot/.test(gov.li.textContent));
    check("with every candidate the election office lists, printed names first and write-ins apart",
      !!gov && gov.li.querySelectorAll(".gov-candidate-list:not(.gov-writein-list) li").length ===
        listed.filter((p) => !p.writeIn).length &&
        gov.li.querySelectorAll(".gov-writein-list li").length === listed.filter((p) => p.writeIn).length);
    check("credited to the list as the document it is, and dated (rule 91), never 'Certified by'",
      !!gov && /Source: .*\(read /.test(gov.li.textContent) && !/Certified by/.test(gov.li.textContent));
    check("no statewide candidate is linked to a profile (rule 25)",
      !!gov && !gov.li.querySelector(".gov-candidates [data-id]"));
    check("Georgia's every statewide office on the ballot has its card",
      ["Governor", "Lieutenant governor", "Attorney general", "Secretary of state"].every((o) =>
        cards.some((c) => c.office === o)));
    check("the reader's state is remembered", window.KYC.rememberedState() === "GA");
    check("print: one button, and it prints", (() => {
      let printed = 0;
      window.print = () => { printed += 1; };
      const b = gaOut.querySelector("[data-ballot-print]");
      if (!b) return false;
      b.click();
      return printed === 1 && /Print or save this list/.test(b.textContent);
    })());
    check("printed in the light theme's colours, the reader's own put back after", (() => {
      const root = window.document.documentElement;
      const meta = window.document.querySelector('meta[name="color-scheme"]');
      root.setAttribute("data-theme", "dark");
      meta.setAttribute("content", "only dark");
      window.dispatchEvent(new window.Event("beforeprint"));
      const during = [root.getAttribute("data-theme"), meta.getAttribute("content")].join();
      window.dispatchEvent(new window.Event("afterprint"));
      return during === "light,only light" && root.getAttribute("data-theme") === "dark" &&
        meta.getAttribute("content") === "only dark";
    })());
  });

  suite("Your ballot: the print stylesheet keeps the list and drops the controls", () => {
    const css = fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8");
    const blocks = [...css.matchAll(/@media print\s*\{([\s\S]*?)\n\}/g)].map((m) => m[1]);
    const ballot = blocks.find((b) => /\.ballot-ask/.test(b)) || "";
    check("the ZIP form, the print button and the page's controls are hidden in print",
      /\.ballot-ask,[\s\S]*\.ballot-print-row,[\s\S]*display: none/.test(ballot));
    check("a contest is never split across pages", /\.ballot-contest \{ break-inside: avoid/.test(ballot));
    check("the scrolling column becomes the page", /overflow: visible/.test(ballot));
    check("the list itself is not hidden", !/\.ballot-list|\.ballot-contest,|\.ballot-state,/.test(
      (ballot.match(/([^{}]*)\{ display: none/) || [""])[0]));
  });

  // Kentucky elects no statewide officer in 2026.
  const ky = await ballotFor("#/?zip=40202");
  suite("Your ballot: a state with no statewide office on the ballot", () => {
    const cards = contestsOf(ky.out);
    const none = cards.find((c) => /^No statewide office this site covers is on this ballot/.test(c.office));
    check("said in one card, each office with its record's mark", !!none &&
      none.li.querySelectorAll(".ballot-offlist li .gov-ballot-mark").length >= 4,
      cards.map((c) => c.office).join(" | "));
    check("and no candidates for an office not on it", !ky.out.querySelector(".gov-candidates"));
    check("the order line names no statewide offices", !/then statewide offices/.test(ky.text));
  });

  const dc = await ballotFor("#/?zip=20001");
  suite("Your ballot: the District of Columbia in its own words", () => {
    check("no page errors", dc.errors.length === 0, dc.errors.join(" | "));
    const cards = contestsOf(dc.out);
    check("its Delegate's race", cards.some((c) => /Delegate to the U.S. House/.test(c.office)),
      cards.map((c) => c.office).join(" | "));
    check("no statewide office, no state legislature", !/statewide|state legislature/i.test(
      [...dc.out.querySelectorAll(".ballot-office, .ballot-heading")].map((h) => h.textContent).join(" ")));
    check("the District's own contests, not listed here", /the District's own contests/.test(dc.text));
    check("'the District of Columbia' in a sentence (rule 75)", /Key dates in the District of Columbia/.test(dc.text));
  });

  const gu = await ballotFor("#/?zip=96910");
  const pr = await ballotFor("#/?zip=00601");
  suite("Your ballot: a territory in its own words", () => {
    const cards = contestsOf(gu.out);
    check("Guam's Delegate race and its own offices", cards.some((c) => /Delegate/.test(c.office)) &&
      cards.some((c) => c.office === "Governor"), cards.map((c) => c.office).join(" | "));
    check("never 'statewide' of a territory", !/statewide/i.test(gu.text), (gu.text.match(/.{40}statewide.{40}/i) || [""])[0]);
    check("territorial offices, in the order line", /then territorial offices/.test(gu.text));
    check("Puerto Rico: no election on November 3, in its election office's words",
      /No election is held in Puerto Rico on November 3, 2026/.test(pr.text) && !/Election Day is/.test(pr.text));
    check("and its Resident Commissioner's seat not on this ballot, with its term",
      /Resident Commissioner to the U\.S\. House/.test(pr.text) && /next in \d{4}/.test(pr.text));
    check("never 'may also hold' where no election is held", !/may also hold/.test(pr.text));
  });

  const pobox = await ballotFor("#/?zip=30003");
  suite("Your ballot: a ZIP code with no ZIP area", () => {
    check("said so, with the way on", /not one of the Census Bureau's ZIP Code Tabulation Areas/.test(pobox.text));
    check("and no ballot is guessed", !pobox.out.querySelector(".ballot-state"));
  });

  // A location: answered, and never written into the address (rule 92).
  const here = await buildPage("ballot.html", { hash: "#/?zip=30009", setup: at(33.749, -84.388, 0, 30) });
  const hereOut = here.D.getElementById("ballotResult");
  await until(() => hereOut.querySelector(".ballot-state"), 8000);
  here.D.querySelector("#ballotAsk [data-ballot-locate]").click();
  await until(() => /your location/.test(hereOut.textContent) && !/Finding/.test(hereOut.textContent), 8000);
  suite("Your ballot: from a location", () => {
    check("the location's ballot", /Your ballot: your location, Georgia/.test(hereOut.textContent),
      hereOut.textContent.slice(0, 160));
    check("the address keeps no ZIP code and no coordinate", here.window.location.hash === "#/" &&
      !/33\.7|84\.3/.test(here.window.location.href), here.window.location.href);
  });

  // The day after the election: an election held, the federal results the
  // site has, the state's own results for the rest, no state winner named.
  const after = await ballotFor("#/?zip=30009", { now: "2026-11-05T12:00:00" });
  suite("Your ballot: after Election Day", () => {
    check("it says the election has been held", /election has been held/.test(after.text));
    check("and links the state's own results for state offices",
      /does not read state or local results and names no winner/.test(after.text) &&
      !!after.out.querySelector('.ballot-after a[target="_blank"]'));
    const gov = contestsOf(after.out).find((c) => c.office === "Governor");
    check("a statewide office's candidates in the past tense, no winner named",
      !!gov && /Candidates who were on the Nov 3, 2026 ballot/.test(gov.li.textContent) &&
      !/Won by|Elected/.test(gov.li.textContent));
    check("the page's own words in the past tense", /What was on the ballot/.test(after.text));
    check("every federal race says its result or that none has been read",
      contestsOf(after.out).filter((c) => /ballot-federal/.test(c.li.className) && !/ballot-off/.test(c.li.className))
        .every((c) => /Won by|Going to a runoff|Awaiting result/.test(c.li.querySelector(".ballot-badges").textContent)));
  });

  // PR #115 review: every race's card, in every state, lists under "On your
  // ballot" only the people the lookup's answer lists (KYC.stillRunning);
  // a filer whose ballot status is not known after the primary is named
  // apart, and a holder off the ballot by their own status, never among
  // those who "lost the primary, withdrew, or were not on the primary
  // ballot".
  suite("Your ballot: every race lists only who is on it, the rest apart", () => {
    const { window } = tx;
    const KYC = window.KYC;
    const D = window.document;
    const bad = [], holders = [], unsureSeen = [], lookup = [];
    const codes = [...new Set(window.kycRaces.map((r) => r.state))];
    codes.forEach((code) => {
      const districts = window.kycRaces.filter((r) => r.state === code && r.chamber === "House")
        .map((r) => r.district);
      const box = D.createElement("div");
      box.innerHTML = KYC.ballot.stateBallot(code, { head: code, race: districts, upper: [], lower: [], notes: [] });
      box.querySelectorAll(".ballot-contest[id^='contest-']").forEach((li) => {
        const race = window.kycRaces.find((r) => "contest-" + r.id === li.id);
        if (!race) return;
        li.querySelectorAll(".ballot-people:not(.ballot-unsure) .ballot-person [data-id]").forEach((b) => {
          const p = KYC.byId(b.getAttribute("data-id"));
          if (!p || !KYC.stillRunning(race, p)) bad.push(race.id + ": " + b.textContent);
        });
        li.querySelectorAll(".ballot-unsure .ballot-person [data-id]").forEach((b) => {
          unsureSeen.push(race.id);
          const p = KYC.byId(b.getAttribute("data-id"));
          if (!p || KYC.stillRunning(race, p) || KYC.offBallot(p.raceStatus)) bad.push(race.id + " (apart): " + b.textContent);
        });
        // A holder off this ballot, not running elsewhere, is named with
        // their status.
        race.incumbentIds.map(KYC.byId).filter(Boolean).forEach((p) => {
          if (p.isCandidate || !KYC.offBallot(p.raceStatus)) return;
          if (p.contestRaceId && p.contestRaceId !== race.id && p.contestLabel) return;
          const line = li.querySelector('.ballot-holder [data-id="' + p.id + '"]');
          if (!line || !line.parentNode.querySelector(".badge")) holders.push(race.id + ": " + p.name);
        });
        // The count of people out never counts a holder named above it.
        const outLine = (li.textContent.match(/\d+( other)? (?:person|people) no longer in this race/) || [""])[0];
        if (outLine && li.querySelector(".ballot-holder") && !/ other /.test(outLine)) {
          bad.push(race.id + ": holder counted among those out");
        }
        // The same people as the lookup's answer for this race.
        const ids = [...li.querySelectorAll(".ballot-people:not(.ballot-unsure) .ballot-person [data-id]")]
          .map((b) => b.getAttribute("data-id")).sort();
        const theirs = KYC.findRep.running(race).map((p) => p.id).sort();
        if (JSON.stringify(ids) !== JSON.stringify(theirs)) lookup.push(race.id + ": " + ids + " / " + theirs);
      });
    });
    check("each person under 'On your ballot' is on it, by the lookup's own test", bad.length === 0,
      bad.slice(0, 8).join(" | "));
    check("each seat's holder off the ballot is named with their own status", holders.length === 0,
      holders.slice(0, 8).join(" | "));
    // Asked while the campaign's Congress sits (rule 68): from January 3 a
    // re-seated member's seat is their new term's, which the lookup reads
    // and the race record does not.
    check("each race lists the same people as the lookup's answer for it",
      lookup.length === 0 || !oldCongressSits(window), lookup.slice(0, 6).join(" | "));
    check("(a filer whose status is not known exists to test with, or none does)",
      unsureSeen.length > 0 || !oldCongressSits(window));
  });

  // PR #115 review: West Virginia's Senate and North Dakota's House name
  // the districts up; Virginia's legislature is not up at all.
  const nd = await ballotFor("#/?zip=58501");
  const wv = await ballotFor("#/?zip=25301");
  const va = await ballotFor("#/?zip=23219");
  const az = await ballotFor("#/?zip=85004");
  const mt = await ballotFor("#/?zip=59601");
  suite("Your ballot: each legislative seat, in the record's words", () => {
    const legOf = (b) => contestsOf(b.out).filter((c) => /ballot-legislature/.test(c.li.className));
    const ndHouse = legOf(nd).find((c) => /House/.test(c.office));
    check("North Dakota's House: whether the seat is up, never 'not known'",
      !!ndHouse && !/not known here/.test(ndHouse.li.textContent) &&
      /(on the Nov 3, 2026 ballot|no regular election in 2026|not up for regular election)/.test(ndHouse.li.textContent),
      ndHouse && ndHouse.li.textContent.slice(0, 300));
    const wvSenate = legOf(wv).find((c) => /Senate/.test(c.office));
    check("West Virginia's Senate: one of each district's seats is up",
      !!wvSenate && /One of this district's seats is on the Nov 3, 2026 ballot|special election/.test(wvSenate.li.textContent) &&
      !/not known here/.test(wvSenate.li.textContent), wvSenate && wvSenate.li.textContent.slice(0, 300));
    const azHouse = legOf(az).find((c) => /House/.test(c.office));
    check("Arizona's House, two members a district: 'this district's seats', never 'this seat'",
      !!azHouse && /This district's seats are on the Nov 3, 2026 ballot/.test(azHouse.li.textContent) &&
      !/This seat is/.test(azHouse.li.textContent), azHouse && azHouse.li.textContent.slice(0, 300));
    const mtSenate = legOf(mt).find((c) => /Senate/.test(c.office));
    check("Montana's Senate: not known on each row, the chamber's count said once, the gap this site's",
      !!mtSenate && [...mtSenate.li.querySelectorAll(".ballot-seat-row")].every((r) =>
        /is not known here/.test(r.textContent) && !/seats are on the Nov 3/.test(r.textContent)) &&
        (mtSenate.li.textContent.match(/of the 50 seats are on the Nov 3, 2026 ballot/g) || []).length === 1 &&
        /This site's record of the 2026 ballot gives how many/.test(mtSenate.li.textContent) &&
        !/The state's record gives how many/.test(mtSenate.li.textContent) && !/\( |\s\)/.test(mtSenate.li.textContent),
      mtSenate && mtSenate.li.textContent.slice(0, 400));
    const vaLeg = legOf(va);
    check("Virginia's legislature, not up: drawn as off this ballot, and out of the order line",
      vaLeg.length > 0 && vaLeg.every((c) => /ballot-off/.test(c.li.className)) &&
      !/then the state legislature/.test(va.text), va.text.match(/Congress first[^.]*\./));
    check("a chamber with a seat up is a contest, not drawn as off it",
      legOf(az).every((c) => !/ballot-off/.test(c.li.className)) && /then the state legislature/.test(az.text));
  });

  suite("Your ballot: a statewide office's holder is named as the holder", () => {
    const { window } = az;
    const sg = window.KYC.stategov;
    const states = window.kycStateGov.states;
    const missed = [];
    let seen = 0;
    Object.keys(states).forEach((code) => {
      ["governor", "lt", "ag", "sos"].forEach((k) => {
        const item = sg.ballotOf(code) && sg.ballotOf(code).offices[k];
        const status = item && item.up && item.holderStatus;
        if (!status || !status.holder || status.text.indexOf(status.holder) === -1) return;
        seen += 1;
        const line = sg.openSeat(code, k, { role: true });
        if (!/[Tt]he holder, /.test(line) || /Open seat: The/.test(line)) missed.push(code + " " + k + ": " + line);
      });
    });
    check("on the ballot page, every holder line says who the holder is", seen > 0 && missed.length === 0,
      missed.slice(0, 4).join(" | "));
    const gov = contestsOf(az.out).find((c) => c.office === "Governor");
    const st = states.AZ.ballot2026.offices.governor.holderStatus;
    check("Arizona's governor card", !gov || !st || !st.holder ||
      gov.li.textContent.indexOf("he holder, " + st.holder + ",") !== -1, gov && gov.li.textContent.slice(0, 300));
  });

  suite("Your ballot: the answer's room is held, and let go when it is drawn", () => {
    check("kyc.js marks an address with a ZIP code before first paint",
      /classList\.add\("has-zip"\)/.test(fs.readFileSync(path.join(SITE, "assets", "kyc.js"), "utf8")));
    check("the stylesheet holds the room", /html\.has-zip \.ballot-result \{ min-height/.test(
      fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8")));
    check("and the drawn answer lets it go", !az.window.document.documentElement.classList.contains("has-zip"));
    check("the ways to an exact answer on a row of their own, out of the sentence",
      !!tx.out.querySelector(".ballot-state > .ballot-actions [data-ballot-locate]") &&
      !tx.out.querySelector(".findrep-note [data-ballot-locate]"));
  });

  const guam = gu;
  suite("Your ballot: Guam's sample ballot, said once", () => {
    check("never 'links no sample ballot' over a list that is one",
      !/This site links no sample ballot/.test(guam.text) &&
      (!/sample ballot/.test((contestsOf(guam.out).find((c) => c.office === "Governor") || { li: { textContent: "" } }).li.textContent) ||
        /the candidate lists above cite/.test(guam.text)), (guam.text.match(/.{60}no sample ballot.{80}/) || [""])[0]);
  });

  const azAfter = await ballotFor("#/?zip=85004", { now: "2026-11-05T12:00:00" });
  const prAfter = await ballotFor("#/?zip=00601", { now: "2026-11-05T12:00:00" });
  suite("Your ballot: after Election Day, every line in the past tense", () => {
    check("'Who was on the ballot for this seat is', never '... are'",
      /Who was on the ballot for (this seat|these seats|this district) is not listed here/.test(azAfter.text) &&
      !/Who was on the ballot for [a-z' ]+ are not listed/.test(azAfter.text), (azAfter.text.match(/Who was on.{60}/) || [""])[0]);
    check("the unlisted contests in the past tense",
      /Also on the ballot, not listed here/.test(azAfter.text) && /may also have held/.test(azAfter.text) &&
      !/may also hold/.test(azAfter.text) && !/Also on your ballot/.test(azAfter.text));
    check("the order line in the past tense", /may have listed them in another order/.test(azAfter.text));
    check("Puerto Rico keeps its no-election line under a neutral heading",
      /Puerto Rico in 2026/.test(prAfter.text) && !/Key dates in Puerto Rico/.test(prAfter.text) &&
      (prAfter.out.querySelector(".ballot-dates").textContent.match(/No election is held in Puerto Rico/) || []).length === 1 &&
      !/What was on the ballot/.test(prAfter.text) && /The offices this site covers/.test(prAfter.text),
      prAfter.text.slice(0, 300));
  });

  // The ways in: the lookup's answer, each state's voting block, the home page.
  const home = await askZip("index.html", "30009");
  const gaPage = await buildPage("states/ga.html");
  const prPage = await buildPage("states/pr.html");
  const prAnswer = await askZip("index.html", "00601");
  await settle(50);
  suite("Your ballot: the ways to it", () => {
    const link = home.out.querySelector("a[data-findrep-ballot]");
    check("the lookup's answer: 'See everything on your ballot', carrying the ZIP code only",
      !!link && /ballot\.html#\/\?zip=30009$/.test(link.getAttribute("href")) &&
      /See everything on your ballot/.test(link.textContent), link && link.getAttribute("href"));
    check("the home page's hero", !!home.D.querySelector('.intro a[data-ballot-entry][href="ballot.html"]'));
    check("each state's voting block", !!gaPage.D.querySelector('#voting a[data-ballot-entry][href$="ballot.html"]'));
    check("but not where no election is held", !prPage.D.querySelector("#voting a[data-ballot-entry]") &&
      !!prAnswer.out.querySelector(".findrep-answer") && !prAnswer.out.querySelector("a[data-findrep-ballot]"));
    check("the navigation", !!home.D.querySelector('.site-nav a[data-nav="ballot"][href="ballot.html"]'));
  });
}

/* ========================================================== people split */

/* The profiles are split by what each page needs (rule 94): the grid and
 * the map load data/people/index.js, everyone's card and search fields; a
 * state's and a district's page load data/people/<st>.js, that state's
 * whole records; any page loads another state's file, or the index, only
 * when it wants one of its people. Every other suite builds the grid and
 * the map with every state's file after the index, as one file held them
 * all before; these build the pages as they ship and prove the index is
 * enough: each view draws the same from it as from everyone's whole
 * records, and whatever needs more loads it, says so while it loads, and
 * says so when it fails. */

/* The markup a reader sees in *ids*, one string, for comparing two pages. */
function shown(D, ids) {
  return ids.map((id) => {
    const el = D.getElementById(id);
    return id + ":" + (el ? (el.hidden ? "[hidden]" : "") + el.innerHTML.replace(/\s+/g, " ") : "-");
  }).join("\n");
}

/* Where two strings first differ, with some of each, for a failing check. */
function firstDifference(a, b) {
  if (a === b) return a.length + " characters";
  let i = 0;
  while (i < a.length && a[i] === b[i]) i += 1;
  return `at ${i}: "${a.slice(Math.max(0, i - 80), i + 120)}" vs "${b.slice(Math.max(0, i - 80), i + 120)}"`;
}

/* Visit each of *routes* on both pages and compare what *ids* show. */
async function sameOnBoth(full, slim, routes, ids, wait) {
  const out = [];
  for (const route of routes) {
    full.window.location.hash = route;
    slim.window.location.hash = route;
    await settle(wait || 150);
    if (/q=\d{5}/.test(route)) {
      const done = (b) => !/Looking up/.test((b.D.getElementById("findrep") || {}).textContent || "");
      await until(() => done(full) && done(slim), 8000);
    }
    const a = shown(full.D, ids);
    const b = shown(slim.D, ids);
    out.push({ route, same: a === b, why: a === b ? "" : firstDifference(a, b), size: a.length });
  }
  return out;
}

function servedPeople(built) {
  return built.served.filter((s) => /\/data\/people\//.test(s)).map((s) => s.split("?")[0]);
}

async function testPeopleSplit() {
  const all = everyone();
  const meta = readPeopleFile(path.join(SITE, "data", "people", "meta.js"));
  const index = readPeopleFile(path.join(SITE, "data", "people", "index.js"));

  suite("people files — one build, split by state (rule 94)", () => {
    const files = peopleStates().map((c) => readPeopleFile(path.join(SITE, "data", "people", c + ".js")));
    check("every file names the build the figures are of", index.build === meta.signature &&
      files.every((f) => f.build === meta.signature), meta.signature.slice(0, 12));
    check("the index holds everyone, once, and every race",
      index.people.length === all.size && new Set(index.people.map((p) => p.id)).size === all.size &&
        index.races.length === files.reduce((n, f) => n + f.races.length, 0),
      `${index.people.length} people, ${index.races.length} races`);
    check("each state's file holds its own people and races and no one else's",
      files.every((f) => f.people.every((p) => p.state === f.state) && f.races.every((r) => r.state === f.state)));
    check("an index record is the whole record's fields, with the same values",
      index.people.every((p) => Object.keys(p).every((k) =>
        JSON.stringify(p[k]) === JSON.stringify(all.get(p.id)[k]))));
    check("the index leaves out what only the dialog and a race's folds show",
      index.people.every((p) => !("districtOffices" in p) && !("committeeList" in p) &&
        !("receipts" in p) && !("fundingBreakdown" in p)) &&
        [...all.values()].some((p) => "receipts" in p || "committeeList" in p || "districtOffices" in p));
  });

  // Every view of the grid, from the index and from everyone's records.
  {
    const full = await buildPage("index.html");
    const slim = await buildPage("index.html", { people: "index" });
    await settle(100);
    suite("index.html as it ships — the index of everyone, no state's file", () => {
      check("no page errors", slim.errors.length === 0, slim.errors.join(" | "));
      check("it loads the build's figures and the index, and no state's file",
        slim.sources.some((s) => /data\/people\/meta\.js$/.test(s)) &&
          slim.sources.some((s) => /data\/people\/index\.js$/.test(s)) &&
          servedPeople(slim).length === 0, servedPeople(slim).join(" "));
      check("every person is a card's record, not a whole one",
        slim.window.legislatorsData.length === all.size &&
          slim.window.legislatorsData.every((p) => !slim.window.KYC.isFull(p)));
      check("the globals keep their shape: legislatorsData, kycRaces, kycBuildMeta",
        Array.isArray(slim.window.legislatorsData) && Array.isArray(slim.window.kycRaces) &&
          slim.window.kycRaces.length === index.races.length && !!slim.window.kycBuildMeta.signature);
    });
    const routes = ["#/", "#/?sort=name", "#/?sort=age-desc", "#/?sort=age-asc", "#/?sort=senate26",
      "#/?sort=close-kalshi", "#/?sort=close-polymarket", "#/?view=race", "#/?view=senate",
      "#/?eliminated=show", "#/?chamber=Senate", "#/?party=Democrat", "#/?party=Independent",
      "#/?role=candidate", "#/?role=member&state=TX", "#/?election=senateUp26", "#/?election=notSeeking",
      "#/?election=unchallenged", "#/?state=CA&view=race", "#/?q=nurse", "#/?q=veteran",
      "#/?q=speaker", "#/?q=pelo", "#/?q=texas", "#/?q=j.d.", "#/?q=warren", "#/?q=vance",
      "#/?q=80202", "#/?q=02139", "#/?q=nurse&sort=name&eliminated=show"];
    const ids = ["results", "resultsLabel", "officialResults", "activeFilters", "findrep", "noResults"];
    const compared = await sameOnBoth(full, slim, routes, ids, 200);
    suite("index.html — every view the same from the index as from everyone's whole records", () => {
      compared.forEach((c) => check(`${c.route} draws the same`, c.same && c.size > 200, c.why || c.size));
      check("still no state's file loaded", servedPeople(slim).length === 0, servedPeople(slim).join(" "));
    });

    // A race's money and its ballot side by side are the state's file's:
    // loaded when the fold opens, said while it loads, then the same.
    slim.window.location.hash = "#/?state=GA&view=race";
    full.window.location.hash = "#/?state=GA&view=race";
    await settle(200);
    const fold = (b) => b.D.querySelector('#results .race-money[data-fold]');
    const compare = (b) => b.D.querySelector('#results .race-compare[data-fold]');
    const before = servedPeople(slim).length;
    openFold(slim.window, fold(slim));
    const loading = fold(slim).querySelector(".fold-body").textContent;
    openFold(full.window, fold(full));
    await until(() => !!fold(slim).querySelector(".money-row"), 5000);
    openFold(slim.window, compare(slim));
    openFold(full.window, compare(full));
    await until(() => !!compare(slim).querySelector(".compare-table"), 5000);
    suite("index.html — a race's money and comparison load the state's records when opened", () => {
      check("it says it is loading, and draws nothing from the cards meanwhile",
        /Loading Georgia/.test(loading) && !/No data/.test(loading), loading);
      check("it loads that state's file, and only it",
        servedPeople(slim).slice(before).join() === "/data/people/ga.js", servedPeople(slim).join(" "));
      check("then the money is what the whole records show",
        fold(slim).innerHTML === fold(full).innerHTML, firstDifference(fold(full).innerHTML, fold(slim).innerHTML));
      check("and the ballot side by side too",
        compare(slim).innerHTML === compare(full).innerHTML,
        firstDifference(compare(full).innerHTML, compare(slim).innerHTML));
      check("Georgia's people are whole now, no one else's",
        slim.window.legislatorsData.every((p) => slim.window.KYC.isFull(p) === (p.state === "GA")));
    });

    // A card opens the dialog over a loading line, never over the card's
    // fields: "No data" about a real person would be false.
    slim.window.location.hash = "#/?state=CA";
    await settle(150);
    const card = slim.D.querySelector('#results .card[data-id]');
    const person = card && all.get(card.getAttribute("data-id"));
    card.click();
    const waiting = slim.D.getElementById("profileModalWaiting");
    const waitText = waiting ? waiting.textContent : "";
    const headerHidden = slim.D.querySelector("#profileModal .modal-header").hidden;
    await until(() => slim.D.getElementById("profileModalWaiting").hidden, 5000);
    suite("index.html — a card's profile loads its state's records first", () => {
      check("a loading line names the person, the dialog's parts hidden",
        !!person && new RegExp("Loading " + person.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(waitText) &&
          headerHidden, waitText);
      check("then the whole profile, with what only the state's file holds",
        slim.D.getElementById("profileModalName").textContent === person.name &&
          !slim.D.querySelector("#profileModal .modal-header").hidden &&
          slim.D.getElementById("profileModalReceipts").textContent.trim() !== "",
        slim.D.getElementById("profileModalReceipts").textContent);
      check("from California's file", servedPeople(slim).indexOf("/data/people/ca.js") !== -1,
        servedPeople(slim).join(" "));
      check("no page errors", slim.errors.length === 0, slim.errors.join(" | "));
    });
    slim.window.KYC.profile.close();
    full.window.close();
    slim.window.close();
  }

  // The directory of states counts every state's races from the index.
  {
    const full = await buildPage("states/index.html");
    const slim = await buildPage("states/index.html", { people: "index" });
    await settle(100);
    suite("states/index.html — the same from the index as from everyone's records", () => {
      const a = shown(full.D, ["stateContent"]);
      const b = shown(slim.D, ["stateContent"]);
      check("every state's row and the picker", a === b && a.length > 2000, firstDifference(a, b));
      check("no page errors", slim.errors.length === 0, slim.errors.join(" | "));
    });
    full.window.close();
    slim.window.close();
  }

  // Every mode of the map, and a state's panel in each.
  {
    const full = await buildPage("map.html");
    const slim = await buildPage("map.html", { people: "index" });
    await settle(100);
    const routes = ["#/?mode=senate", "#/?mode=house", "#/?mode=house&layout=tiles", "#/?mode=senate2026",
      "#/?mode=governor", "#/?mode=governor2026", "#/?mode=trifecta", "#/?mode=legislature",
      "#/?mode=lt", "#/?mode=sos", "#/?mode=ag", "#/?state=TX&mode=house", "#/?state=CA&mode=senate2026",
      "#/?state=AK&mode=senate", "#/?state=GA&mode=senate2026", "#/?state=PR&mode=house",
      "#/?state=NY&mode=house&layout=tiles", "#/?state=OH&mode=senate2026", "#/?state=MN&mode=governor2026"];
    const ids = ["usMap", "mapTiles", "mapLegend", "mapBalance", "panelState", "panelCounts", "panelMode",
      "panelStateLink", "delegation"];
    const compared = await sameOnBoth(full, slim, routes, ids, 150);
    suite("map.html — every mode the same from the index as from everyone's whole records", () => {
      check("no page errors", slim.errors.length === 0, slim.errors.join(" | "));
      compared.forEach((c) => check(`${c.route} draws the same`, c.same && c.size > 500, c.why || c.size));
      check("and no state's file loaded for it", servedPeople(slim).length === 0, servedPeople(slim).join(" "));
    });
    full.window.close();
    slim.window.close();
  }

  // A state's and a district's page draw the same with everyone as with
  // their own state's file: nothing on them is another state's.
  for (const page of ["states/ca.html", "states/wy.html", "states/dc.html", "states/as.html",
    "districts/tx.html", "districts/dc.html", "districts/nc.html"]) {
    const own = await buildPage(page);
    const everyoneHere = await buildPage(page, { people: "all" });
    await settle(150);
    const ids = ["stateContent", "districtsApp", "senateBalance", "houseBalance", "senateSeatsUp",
      "challengerCount", "yourState"];
    const a = shown(everyoneHere.D, ids);
    const b = shown(own.D, ids);
    suite(`${page} — its own state's file is all it needs`, () => {
      check("no page errors", own.errors.length === 0, own.errors.join(" | "));
      check("it loads the build's figures and its own state's file, not the index",
        own.sources.some((s) => /data\/people\/meta\.js$/.test(s)) &&
          own.sources.filter((s) => /data\/people\//.test(s)).length === 2 &&
          !own.sources.some((s) => /data\/people\/index\.js$/.test(s)), own.sources.join(" "));
      check("and draws the same as with everyone's records", a === b && a.length > 1000, firstDifference(a, b));
    });
    own.window.close();
    everyoneHere.window.close();
  }

  // Deep links: on the grid, on the map and on a state page of another
  // state; to a merged FEC id (rule 25) and to a departed member (rule 67).
  const californian = [...all.values()].find((p) => p.state === "CA" && !p.isCandidate &&
    !p.formerMember && /House/.test(p.chamber) && p.committeeList && p.committeeList.length) ||
    [...all.values()].find((p) => p.state === "CA" && !p.isCandidate && !p.formerMember);
  const merged = [...all.values()].find((p) => (p.otherFecIds || []).length);
  for (const page of ["index.html", "map.html", "states/wy.html"]) {
    const built = await buildPage(page, { people: "index", hash: "#/profile/" + californian.id });
    const loading = built.D.getElementById("profileModalWaiting");
    await until(() => built.D.getElementById("profileModalWaiting") &&
      built.D.getElementById("profileModalWaiting").hidden &&
      built.D.getElementById("profileModalName").textContent === californian.name, 6000);
    suite(`${page}#/profile/ — a Californian's profile from a link`, () => {
      check("no page errors", built.errors.length === 0, built.errors.join(" | "));
      check("the dialog opens on the person", !built.D.getElementById("profileModal").hidden &&
        built.D.getElementById("profileModalName").textContent === californian.name,
        built.D.getElementById("profileModalName").textContent);
      check("held whole, with what only their state's file holds",
        built.window.KYC.isFull(built.window.KYC.byId(californian.id)) &&
          (!(californian.committeeList || []).length || californian.committeeList.some((seat) =>
            built.D.getElementById("profileModalCommittees").innerHTML.indexOf(seat.code) !== -1 ||
            built.D.getElementById("profileModalCommittees").textContent.length > 20)),
        built.D.getElementById("profileModalCommittees").textContent.slice(0, 80));
      const wanted = page === "states/wy.html" ? ["/data/people/index.js", "/data/people/ca.js"]
        : ["/data/people/ca.js"];
      check("loading only what it needs: " + wanted.join(", "),
        servedPeople(built).join() === wanted.join(), servedPeople(built).join(" "));
      check("the address keeps the profile", built.window.location.hash === "#/profile/" + californian.id);
    });
    built.window.close();
  }
  if (merged) {
    const alias = "FEC_" + merged.otherFecIds[0];
    for (const page of ["index.html", "map.html", "states/as.html"]) {
      const built = await buildPage(page, { people: "index", hash: "#/profile/" + alias });
      await until(() => built.D.getElementById("profileModalName") &&
        built.D.getElementById("profileModalName").textContent === merged.name &&
        built.D.getElementById("profileModalWaiting").hidden, 6000);
      suite(`${page}#/profile/${alias} — a link under a folded FEC id (rule 25)`, () => {
        check("no page errors", built.errors.length === 0, built.errors.join(" | "));
        check("opens the person it was folded into", built.D.getElementById("profileModalName").textContent === merged.name,
          built.D.getElementById("profileModalName").textContent);
        check("and the address moves to their current id",
          built.window.location.hash === "#/profile/" + encodeURIComponent(merged.id), built.window.location.hash);
      });
      built.window.close();
    }
  }
  {
    // A record incumbent who has left keeps the member shape and a
    // profile (rule 67): the index and their state's file both carry it.
    const leaving = [...all.values()].find((p) => p.formerMember) ||
      [...all.values()].find((p) => !p.isCandidate && p.state === "OH" && /House/.test(p.chamber));
    const departed = (w) => {
      w.legislatorsData.forEach((p) => {
        if (p.id === leaving.id && !p.formerMember) {
          p.formerMember = { left: "2026-12-08", via: "legislators-historical", congress: 119 };
        }
      });
    };
    const built = await buildPage("index.html", { people: "index", hash: "#/profile/" + leaving.id,
      data: departed });
    await until(() => built.D.getElementById("profileModalWaiting") &&
      built.D.getElementById("profileModalWaiting").hidden &&
      built.D.getElementById("profileModalName").textContent === leaving.name, 6000);
    suite("index.html#/profile/ — a member who has left (rule 67)", () => {
      check("no page errors", built.errors.length === 0, built.errors.join(" | "));
      check("opens their profile, said as a former member's",
        built.D.getElementById("profileModalName").textContent === leaving.name &&
          /Represented \(until /.test(built.D.getElementById("profileModalRegionLabel").textContent),
        built.D.getElementById("profileModalRegionLabel").textContent);
      check("not counted among those who sit", !built.window.KYC.seated(built.window.KYC.byId(leaving.id)));
    });
    built.window.close();
  }
  // Nobody by that id (a stale or mistyped shared link): every page says
  // the same sentence. The grid used to drop it silently, the map to open
  // nothing under the address, and a state page to say this.
  for (const page of ["index.html", "map.html"]) {
    const built = await buildPage(page, { people: "index", hash: "#/profile/X_NOBODY" });
    await until(() => /No profile on this site has the id/.test(
      (built.D.getElementById("profileModalWaiting") || {}).textContent || ""), 6000);
    const modal = built.D.getElementById("profileModal");
    const line = built.D.getElementById("profileModalWaiting");
    suite(page + "#/profile/ — an id nobody has", () => {
      check("says no profile has it", !!modal && !modal.hidden && !!line && !line.hidden &&
        /No profile on this site has the id X_NOBODY\./.test(line.textContent),
        line ? line.textContent : "no dialog");
      check("names no one in the dialog's heading", !!modal &&
        built.D.getElementById("profileModalName").textContent === "Profile");
      check("no state's file loaded for it", servedPeople(built).length === 0, servedPeople(built).join(" "));
      if (page === "index.html") {
        check("the grid drawn under it", built.D.querySelectorAll("#grid .card, .card").length > 0);
      }
    });
    // Closing it leaves the address for the page itself.
    built.window.KYC.profile.close();
    await settle(30);
    suite(page + "#/profile/ — closing the not-found line", () => {
      check("the address no longer names the id", !/X_NOBODY/.test(built.window.location.hash),
        built.window.location.hash);
    });
    built.window.close();
  }
  {
    // A member who left during this Congress has no profile; a link to
    // their id says whose it is and who holds the seat now (PR #118 review).
    const probe = await buildPage("index.html", { people: "index" });
    const gone = ((probe.window.KYC.meta() || {}).departed || []).find((r) => r.holder);
    probe.window.close();
    if (gone) {
      const built = await buildPage("index.html", { people: "index", hash: "#/profile/" + gone.id });
      await until(() => /No profile on this site has the id/.test(
        (built.D.getElementById("profileModalWaiting") || {}).textContent || ""), 6000);
      const line = built.D.getElementById("profileModalWaiting");
      const to = line.querySelector("button[data-goto]");
      suite("index.html#/profile/ — a member who left during this Congress", () => {
        check("names them and when the term ended",
          line.textContent.indexOf("It is the id of " + gone.name + ", who left the") !== -1 &&
            /congress-legislators ends the term on/.test(line.textContent), line.textContent);
        check("and opens the seat's holder now",
          !!to && to.getAttribute("data-goto") === gone.holder.id && to.textContent === gone.holder.name);
      });
      built.window.close();
    }
  }
  {
    // On a state page an unknown id is looked for in the index first.
    const built = await buildPage("states/wy.html", { people: "index", hash: "#/profile/X_NOBODY" });
    await until(() => /No profile on this site has the id/.test(
      (built.D.getElementById("profileModalWaiting") || {}).textContent || ""), 6000);
    suite("states/wy.html#/profile/ — an id nobody has", () => {
      check("says no profile has it, after looking in the index",
        /No profile on this site has the id X_NOBODY/.test(built.D.getElementById("profileModalWaiting").textContent) &&
          servedPeople(built).join() === "/data/people/index.js", servedPeople(built).join(" "));
    });
    built.window.close();
  }

  // A file that fails to load is said, and nothing is drawn from a card.
  {
    const built = await buildPage("index.html", { people: "index", refuse: /\/data\/people\/ca\.js$/,
      hash: "#/profile/" + californian.id });
    await until(() => /did not load/.test((built.D.getElementById("profileModalWaiting") || {}).textContent || ""), 6000);
    const text = built.D.getElementById("profileModalWaiting").textContent;
    suite("index.html — a state's file that fails to load", () => {
      check("the dialog says the profile did not load, by name", new RegExp(californian.name.replace(
        /[.*+?^${}()|[\]\\]/g, "\\$&") + ".s profile did not load").test(text), text);
      check("and shows none of the card's fields as the person's",
        built.D.querySelector("#profileModal .modal-body").hidden &&
          built.D.querySelector("#profileModal .modal-header").hidden);
    });
    built.window.location.hash = "#/?state=CA&view=race";
    await settle(200);
    const money = built.D.querySelector("#results .race-money[data-fold]");
    openFold(built.window, money);
    await until(() => /did not load/.test(money.textContent), 5000);
    suite("index.html — a race's money when its state's file fails", () => {
      check("says the figures did not load, and how to retry",
        /did not load\. Close this and open it again to retry/.test(money.textContent), money.textContent);
      check("no money rows drawn from the cards", !money.querySelector(".money-row"));
    });
    built.window.close();
  }

  // A file from another build than the page's figures is refused (rule 34).
  {
    const built = await buildPage("index.html", { people: "index" });
    await settle(80);
    const KYC = built.window.KYC;
    const before = built.window.legislatorsData.length;
    built.window.kycPeopleFile = { build: "0".repeat(64), state: "CA",
      people: [{ id: "X_STALE", name: "Stale Person", state: "CA" }], races: [] };
    suite("a people file from another build", () => {
      check("is refused: nothing it holds reaches the page",
        built.window.legislatorsData.length === before && !KYC.byId("X_STALE"));
      check("and the page says why, for a page opened before the update",
        /updated since this page was opened\. Reload the page/.test(KYC.peopleProblem()),
        KYC.peopleProblem());
    });
    built.window.close();
  }

  // "Find who represents me" on a state page, for a ZIP code in another
  // state: that state's people are loaded first.
  {
    const wy = await askZip("states/wy.html", "80202");
    suite("states/wy.html — a ZIP code in Colorado", () => {
      check("no page errors", wy.errors.length === 0, wy.errors.join(" | "));
      const reps = [...all.values()].filter((p) => p.state === "CO" && wy.window.KYC.seated(p) &&
        /Senate/.test(p.chamber));
      check("names Colorado's senators, from Colorado's file",
        reps.length === 2 && reps.every((p) => wy.text.indexOf(p.name) !== -1) &&
          servedPeople(wy).indexOf("/data/people/co.js") !== -1, wy.text.slice(0, 200));
    });
    const failed = await askZip("states/wy.html", "80202", { refuse: /\/data\/people\/co\.js$/ });
    suite("states/wy.html — a ZIP code in Colorado when its file fails", () => {
      check("says Colorado's members did not load, names nobody",
        /members of Congress for Colorado did not load/.test(failed.text) &&
          !failed.out.querySelector(".findrep-row"), failed.text);
    });
    wy.window.close();
    failed.window.close();
  }

  // Your ballot (rule 92) holds no one's records until an answer needs
  // them: the build's figures, then the files of the states the answer is
  // in, before it is drawn. testBallot compares each of its contests with
  // the state page's section, drawn from the same file.
  {
    const ga = await ballotFor("#/?zip=30009");
    suite("ballot.html — a ZIP code loads its own state's people, and no one else's", () => {
      check("no page errors", ga.errors.length === 0, ga.errors.join(" | "));
      check("loads Georgia's file, and neither the index nor another state's",
        servedPeople(ga).join(" ") === "/data/people/ga.js", servedPeople(ga).join(" "));
      check("draws Georgia's contests and the people in them",
        ga.out.querySelectorAll(".ballot-contest").length > 2 && !!ga.out.querySelector(".ballot-person"),
        ga.text.slice(0, 200));
    });
    // Frisco, Texas: a ZIP code across two districts of one state loads
    // that state alone.
    const crossing = await ballotFor("#/?zip=75036");
    suite("ballot.html — a ZIP code in Texas", () => {
      check("loads Texas's file only", servedPeople(crossing).join(" ") === "/data/people/tx.js",
        servedPeople(crossing).join(" "));
    });
    const failed = await ballotFor("#/?zip=30009", { refuse: /\/data\/people\/ga\.js$/ });
    suite("ballot.html — a ZIP code whose state's file fails", () => {
      check("says Georgia's races did not load, and draws no contest",
        /races and candidates for Georgia did not load/.test(failed.text) &&
          !failed.out.querySelector(".ballot-contest"), failed.text);
    });
    // A profile linked from the page opens whole, from its state's file.
    const linked = await buildPage("ballot.html", { hash: "#/profile/" + [...all.values()]
      .find((p) => p.state === "WY" && p.chamber.indexOf("Senate") !== -1).id });
    await until(() => linked.D.getElementById("profileModalWaiting") &&
      linked.D.getElementById("profileModalWaiting").hidden &&
      /\S/.test(linked.D.getElementById("profileModalName").textContent), 6000);
    suite("ballot.html — a profile's address", () => {
      const id = linked.window.KYC.router.read().id;
      check("opens the person whole, from the index and their state's file",
        linked.window.KYC.isFull(linked.window.KYC.byId(id)) &&
          servedPeople(linked).indexOf("/data/people/wy.js") !== -1, servedPeople(linked).join(" "));
    });
    [ga, crossing, failed, linked].forEach((b) => b.window.close());
  }

  // The federal pages link members to the grid: every one opens there.
  {
    // The guide's Congress page writes its links in; the federal page draws
    // the line of succession's from data/federal.js (kyc-federal.js).
    const raw = fs.readFileSync(path.join(SITE, "government", "congress.html"), "utf8");
    const sandbox = { window: {} };
    require("vm").runInNewContext(fs.readFileSync(path.join(SITE, "data", "federal.js"), "utf8"), sandbox);
    const succession = ((sandbox.window.kycFederal || {}).succession || [])
      .filter((p) => p.kind === "member").map((p) => p.id);
    const ids = [...new Set(succession.concat(
      [...raw.matchAll(/index\.html#\/profile\/([A-Za-z0-9_]+)/g)].map((m) => m[1])))];
    suite("links from the federal and guide pages to members", () => {
      // While the old Congress sits its leaders and committee leads are
      // named; a new Congress's come days or weeks after it sits (rule 68).
      const sits = meta.congress < (meta.election.year - 1786) / 2;
      check("each names a profile the index holds", (!sits || ids.length > 20) && ids.every((id) => all.has(id) ||
        index.people.some((p) => (p.otherFecIds || []).some((o) => "FEC_" + o === id))),
        ids.filter((id) => !all.has(id)).join(" ") || ids.length);
    });
    if (ids.length) {
      const target = all.get(succession[0] || ids[0]);
      const built = await buildPage("index.html", { people: "index", hash: "#/profile/" + target.id });
      await until(() => built.D.getElementById("profileModalName") &&
        built.D.getElementById("profileModalName").textContent === target.name &&
        built.D.getElementById("profileModalWaiting").hidden, 6000);
      suite("a federal page's member link opens on the grid", () => {
        check("the profile opens, whole", built.D.getElementById("profileModalName").textContent === target.name &&
          built.window.KYC.isFull(built.window.KYC.byId(target.id)), target.name);
      });
      built.window.close();
    }
  }
}

/* ======================================== a big state's page on a phone */

/* Below 1000px a state with more than four races opens with "Find your
 * race" and folds each race to one row over its section (VISUALS-15,
 * TECH-14): California's page was about 92 screens once drawn, its district
 * squares 13,900px down. *phone* is the width the page is drawn at; a
 * change listener lets a suite turn the tablet. */
function phoneWidth(window, phone) {
  const media = { phone, listeners: [] };
  window.__media = media;
  window.matchMedia = (query) => ({
    media: query,
    get matches() { return /max-width: 999/.test(query) ? media.phone : false; },
    addEventListener(type, fn) { media.listeners.push(fn); },
    removeEventListener() {},
    addListener(fn) { media.listeners.push(fn); },
    removeListener() {},
  });
}

function turn(window, phone) {
  window.__media.phone = phone;
  window.__media.listeners.forEach((fn) => fn({ matches: phone }));
}

/* What a folded race's row says, read back: its holder line, the names it
 * groups under each label, the unsettled filers, and its badges. */
function readRow(section) {
  const row = section.querySelector(".race-row");
  const groups = (cls) => [...row.querySelectorAll("." + cls)].map((g) => ({
    label: g.querySelector(".race-row-label").textContent.replace(/:$/, ""),
    names: [...g.querySelectorAll(".race-row-name")].map((n) => n.textContent),
  }));
  return {
    row,
    held: (row.querySelector(".race-row-held") || { textContent: "" }).textContent,
    ballot: groups("race-row-ballot"),
    unsettled: groups("race-row-unsettled"),
    badges: [...row.querySelectorAll(".race-row-badges .badge")].map((b) => b.textContent),
    text: row.textContent.replace(/\s+/g, " "),
  };
}

/* The Find your race select's House options against who sits for each
 * district now, read from the people (district, chamber, seated), never
 * from the race record: "District 3 · held by Kevin Kiley" once Ami Bera
 * sits there. Returns the problems found. */
function houseOptionProblems(window, D) {
  const KYC = window.KYC;
  const out = [];
  [...D.querySelectorAll('#raceJumpSelect optgroup[label="U.S. House"] option')].forEach((o) => {
    const race = KYC.races().filter((r) => "race-" + r.id === o.value)[0];
    if (!race) return out.push(o.value + ": no race");
    const sitting = KYC.people().filter((p) => KYC.seated(p) && /House/.test(p.chamber || "") &&
      p.state === race.state && (parseInt(p.district, 10) || 0) === Number(race.district || 0)).map((p) => p.name);
    const m = / · held by (.+)$/.exec(o.textContent);
    const said = m ? m[1].split(" and ") : [];
    if (said.join("|") !== sitting.join("|")) {
      out.push(o.value + ": says " + JSON.stringify(said) + ", sitting " + JSON.stringify(sitting));
    }
    if (!sitting.length && / · held by /.test(o.textContent)) out.push(o.value + ": a holder for an empty seat");
  });
  return out;
}

/* Each race's row against its own section, on one built page: the same
 * people under the same words, the same count, and the holder clause the
 * section's own "Held by" line gives. Returns the problems found. */
function rowProblems(window, D) {
  const KYC = window.KYC;
  const out = [];
  [...D.querySelectorAll("section.race-foldable")].forEach((section) => {
    const id = section.getAttribute("data-race");
    const race = KYC.races().filter((r) => r.id === id)[0];
    const row = readRow(section);
    const say = (what) => out.push(id + ": " + what);
    // Everyone on the November ballot whose card is in the race, under
    // their card's own words; the unsettled apart (rule 62).
    const grid = section.querySelector(".race-body > .card-grid");
    const people = [...grid.querySelectorAll(".card")].map((c) => KYC.byId(c.getAttribute("data-id")));
    const want = [];
    const apart = [];
    people.forEach((p) => {
      const spec = KYC.standing(p, "card");
      if (spec && spec.unknown) apart.push([spec.label, p.name]);
      else if (spec) want.push([spec.label, p.name]);
      else if (p.isCandidate) want.push(["2026 challenger", p.name]);
      // Seated since as the race's winner, before a result is read for them
      // (the December rehearsals; rule 67): the Senate view's words.
      else if (p.raceRole === "winner" && KYC.seated(p)) want.push(["Holds the seat (won it in " + race.year + ")", p.name]);
    });
    const flat = (groups) => [].concat(...groups.map((g) => g.names.map((n) => [g.label, n])));
    // A label naming one person is plural over more than one ("Write-in
    // candidates", "2026 challengers"; the PR #133 review); the status
    // words are not.
    const one = (label) => label.replace(/(candidate|challenger)s$/, "$1");
    const got = flat(row.ballot).filter((x) => !/^Also /.test(x[0])).map((x) => [one(x[0]), x[1]]);
    const gotApart = flat(row.unsettled).map((x) => [one(x[0]), x[1]]);
    row.ballot.concat(row.unsettled).forEach((g) => {
      if (/(candidate|challenger)s?$/.test(g.label) && /s$/.test(g.label) !== (g.names.length > 1)) {
        say("a label in the wrong number: " + g.label + " over " + g.names.length);
      }
      // A write-in group does not say "Write-in" again of each name.
      if (/write-in/i.test(g.label) && g.names.some((n) => /\(Write-?in\)/i.test(n))) {
        say("write-in said twice: " + g.names.join(", "));
      }
    });
    const same = (a, b) => a.length === b.length && a.every((x, i) => b.some((y) =>
      y[0] === x[0] && (y[1] === x[1] || y[1].indexOf(x[1] + " (") === 0 || y[1].indexOf(x[1] + " –") === 0)));
    if (!same(want, got)) say("ballot " + JSON.stringify(got) + " against cards " + JSON.stringify(want));
    if (!same(apart, gotApart)) say("unsettled " + JSON.stringify(gotApart) + " against " + JSON.stringify(apart));
    // Dates in words, as the row's other dates are ("until 2026-12-08").
    if (/\b\d{4}-\d{2}-\d{2}\b/.test(row.text)) say("a date not in words: " + row.held);
    // A name with no profile is credited as the section credits it (rules 64, 77).
    row.ballot.filter((g) => /^Also /.test(g.label)).forEach((g) => {
      if (g.label.indexOf(KYC.ballotSource(race)) === -1) say("uncredited: " + g.label);
    });
    // Nobody held the seat, so nobody challenges (FL-20).
    if (!(race.incumbentIds || []).length && row.badges.some((b) => /challenger/.test(b))) {
      say("challengers to nobody: " + row.badges.join("|"));
    }
    // The results' names with no profile here, every one of them.
    const others = ((race.results || {}).otherNominees || []);
    const named = [].concat(...row.ballot.filter((g) => /^Also /.test(g.label)).map((g) => g.names));
    if (others.length !== named.length || !others.every((n) => named.some((m) => m === n || m.indexOf(n + " (") === 0))) {
      say("no-profile names " + JSON.stringify(named) + " against " + JSON.stringify(others));
    }
    // The count is the head's own badge (rule 73), and the names fit it.
    const headCount = [...section.querySelectorAll(".race-head .badge")].map((b) => b.textContent)
      .filter((t) => /(challenger|candidate)s? on the ballot$|^\d+ (challenger|candidate)s?$|^No challenger|filed|Nobody/.test(t));
    if (!row.badges.some((b) => headCount.indexOf(b) !== -1)) say("count " + row.badges.join("|") + " against " + headCount.join("|"));
    const m = /^(\d+) (challenger|candidate)s? on the ballot$/.exec(headCount[0] || "");
    if (m) {
      const holders = got.filter((x) => people.some((p) => race.incumbentIds.indexOf(p.id) !== -1 &&
        (x[1] === p.name || x[1].indexOf(p.name + " (") === 0 || x[1].indexOf(p.name + " –") === 0)));
      if (got.length + named.length - holders.length !== Number(m[1])) {
        say("names " + (got.length + named.length) + " less " + holders.length + " holder(s) against " + m[0]);
      }
    }
    // The holder clause: the section's own "Held by" line, word for word.
    section.querySelectorAll(".race-body > .race-held").forEach((line) => {
      const contact = line.querySelector(".card-contact");
      const words = line.textContent.replace(contact ? contact.textContent : "", "").trim();
      if (row.held.indexOf(words) === -1) say("held " + JSON.stringify(row.held) + " against " + JSON.stringify(words));
    });
    // An open seat says so first, in the badge's words, unless the seat is
    // empty and its vacancy says more; an appointee is never "re-election".
    const open = !!section.querySelector(".race-head .badge-warn[title]") &&
      [...section.querySelectorAll(".race-head .badge")].some((b) => b.textContent === "Open seat");
    const vacancy = race.chamber === "House" && KYC.vacancyOf(race.state, race.district || 0);
    if (open && !vacancy && row.held.indexOf("Open seat.") !== 0) say("open seat not said: " + row.held);
    if (vacancy && !race.incumbentIds.length && row.held.indexOf(KYC.vacancyNote(vacancy)) === -1) {
      say("vacancy not said: " + row.held);
    }
    if (race.incumbent && race.incumbent.appointed && /re-election/.test(row.held)) say("appointee: " + row.held);
    // An all-party primary has no nominee (rule 74).
    if (/top-(two|four)/.test(race.primaryKind || "") && /Nominee|Renominated|Won the primary/.test(row.text)) {
      say("all-party primary: " + row.text);
    }
  });
  return out;
}

async function testStatePhone() {
  const PAGES = ["ca", "tx", "fl", "ny", "la", "ok", "wa", "il", "ga", "al"];
  const built = {};
  for (const st of PAGES) {
    built[st] = await buildPage("states/" + st + ".html", { setup: (w) => phoneWidth(w, true) });
  }
  const { window, D, errors } = built.ca;
  const KYC = window.KYC;
  const block = D.getElementById("find-race");
  const races = D.getElementById("races");
  const sections = [...D.querySelectorAll("section.race-foldable")];

  suite("states/ca.html on a phone — Find your race, under the summary (VISUALS-15, TECH-14)", () => {
    check("no page errors on any folded page", PAGES.every((st) => !built[st].errors.length),
      PAGES.map((st) => built[st].errors.join(" | ")).join(" "));
    check("the block is shown, directly after the title and summary",
      !!block && !block.hidden && block.previousElementSibling.classList.contains("state-hero"));
    const select = D.getElementById("raceJumpSelect");
    check("a labelled native select jumps to a race or section",
      !!select && D.querySelector('label[for="raceJumpSelect"]').textContent === "Jump to a race or section");
    check("its groups are Statewide, U.S. House and This page",
      [...select.querySelectorAll("optgroup")].map((g) => g.label).join("|") === "Statewide|U.S. House|This page");
    const house = [...select.querySelectorAll('optgroup[label="U.S. House"] option')];
    const houseRaces = KYC.races().filter((r) => r.state === "CA" && r.chamber === "House");
    check("every House race is in it once, by district",
      house.length === houseRaces.length && house.every((o) => {
        const race = houseRaces.filter((r) => "race-" + r.id === o.value)[0];
        return race && o.textContent.indexOf("District " + race.district) === 0;
      }), house.slice(0, 3).map((o) => o.textContent).join(" | "));
    // Who sits for the district now, as the delegation lists them (rule
    // 27): never the frozen record's incumbent, who from January 3 may sit
    // in the Senate or for another district (rule 67). On the january
    // rehearsal the record's names put Barry Moore on AL-1 and Kevin Kiley
    // on CA-3 (PR #126 review).
    const holderProblems = [].concat(...PAGES.map((st) => houseOptionProblems(built[st].window, built[st].D)));
    check("every House option names whoever sits for that district now, and only them (rules 27, 67)",
      holderProblems.length === 0, holderProblems.slice(0, 4).join(" || "));
    check("every option names a place on the page",
      [...select.querySelectorAll("option")].every((o) => !o.value || !!D.getElementById(o.value)));
    const values = [...select.querySelectorAll("option")].map((o) => o.value).filter(Boolean);
    check("and each place once: a section the Statewide group offers is not offered again under This page",
      PAGES.every((st) => {
        const vs = [...built[st].D.querySelectorAll("#raceJumpSelect option")].map((o) => o.value).filter(Boolean);
        return new Set(vs).size === vs.length;
      }) && values.indexOf("state-government") !== -1, values.filter((v) => !/^race-/.test(v)).join(","));
    check("the voting block is offered by its own heading's words",
      !!select.querySelector('option[value="voting"]') &&
        select.querySelector('option[value="voting"]').textContent === D.getElementById("votingHead").textContent.trim());
    check("the district squares are moved into the block",
      !!block.querySelector(".find-race-tiles .district-tiles") && !races.querySelector(".district-tiles"));
    check("Find who represents you is moved into it, keeping its id, once",
      D.querySelectorAll("#findrep").length === 1 && !!block.querySelector(".find-race-lookup #findrep"));
    const line = block.querySelector(".find-race-statewide");
    const offices = KYC.stategov.ballotOffices("CA");
    check("the statewide line names the state offices in the State government table's words",
      !!line && !!offices && [...line.querySelectorAll("a")].some((a) =>
        a.textContent === offices && a.getAttribute("href") === "#state-government"), line && line.textContent);
    check("and the statewide questions by their section's name",
      [...line.querySelectorAll("a")].some((a) => a.textContent === KYC.ballot.measuresName("CA") &&
        a.getAttribute("href") === "#measures"));
    // Texas's line read as the whole statewide ballot, without its
    // comptroller or railroad commissioner (PR #126 review).
    check("the line says it is what this site covers, and that the ballot may hold more",
      PAGES.every((st) => {
        const l = built[st].D.querySelector(".find-race-statewide");
        return !l || (/^Of what this site covers, the Nov 3, 2026 ballot holds statewide: /.test(l.textContent) &&
          l.textContent.endsWith("It may also hold " + KYC.ballot.unlisted + "."));
      }), line.textContent);
    check("the header's links follow the block; the section chips give way to the select",
      block.nextElementSibling.classList.contains("state-links") && D.querySelector(".state-parts").hidden);
  });

  suite("states/ca.html on a phone — every race one row over its section", () => {
    check("every race folds", sections.length === KYC.races().filter((r) => r.state === "CA").length &&
      races.classList.contains("races-folded"));
    check("each row is a heading's button that names the section it controls", sections.every((s) => {
      const b = s.querySelector("h3.race-row-title > button.race-row");
      const body = s.querySelector(".race-body");
      return !!b && !s.querySelector(".race-row-title").hidden && b.getAttribute("aria-controls") === body.id;
    }));
    check("folded, each section stays in the page, hidden until found", sections.every((s) =>
      s.querySelector(".race-body").getAttribute("hidden") === "until-found" &&
      s.querySelector(".race-row").getAttribute("aria-expanded") === "false" &&
      s.querySelectorAll(".race-body .card").length > 0));
    const shared = D.querySelector(".race-shared");
    const sharedWords = [...shared.querySelectorAll(".badge")].map((b) => b.textContent);
    check("the badges every race shares are said once above the rows",
      !!shared && sharedWords.length > 0 && sharedWords.every((w) => sections.every((s) =>
        [...s.querySelectorAll(".race-head .badge-shared")].some((b) => b.textContent === w))), sharedWords.join(" | "));
    check("and no row repeats them",
      sections.every((s) => !readRow(s).badges.some((b) => sharedWords.indexOf(b) !== -1)));
    check("a row's badges are its head's (rule 73)", sections.every((s) => {
      const head = [...s.querySelectorAll(".race-head .badge")].map((b) => b.textContent);
      return readRow(s).badges.every((b) => head.indexOf(b) !== -1);
    }));
    // CA-2 opened read "1 challenger on the ballot" twice, one under the
    // other (PR #126 review): the head leaves those to the row, folded.
    check("and the opened head leaves those to the row above it", sections.every((s) => {
      const said = readRow(s).badges;
      return [...s.querySelectorAll(".race-head .badge")].every((b) =>
        b.classList.contains("badge-in-row") === (said.indexOf(b.textContent) !== -1 &&
          !b.classList.contains("badge-shared")));
    }) && /\.races-folded \.badge-in-row \{ display: none; \}/.test(
      fs.readFileSync(path.join(SITE, "assets", "kyc.css"), "utf8")));
  });

  suite("a folded row and its race's section never disagree (rules 12, 62, 63, 73, 74)", () => {
    PAGES.forEach((st) => {
      const problems = rowProblems(built[st].window, built[st].D);
      check(`states/${st}.html: each row names its section's people, in their cards' words, and its count`,
        problems.length === 0 && built[st].D.querySelectorAll("section.race-foldable").length > 4,
        problems.slice(0, 4).join(" || "));
    });
    // The cases the rows were written for, wherever the data holds them:
    // the old Congress's members running elsewhere exist only while it sits
    // (rule 68).
    const all = PAGES.map((st) => built[st]);
    // Texas's Senate row read "Write-in candidate: Bradford Winston Hall
    // (Write-in), Jade Simmons (I)" (the PR #133 review).
    const writeIns = [].concat(...all.map((b) => [...b.D.querySelectorAll("section.race-foldable")]
      .map(readRow))).filter((row) => row.ballot.concat(row.unsettled)
      .some((g) => /write-in/i.test(g.label) && g.names.length > 1));
    check("a group of write-ins is labelled in the plural, and says write-in once (where the data holds one)",
      writeIns.every((row) => row.ballot.concat(row.unsettled).every((g) => !/write-in/i.test(g.label) ||
        (/s$/.test(g.label) === (g.names.length > 1) && !g.names.some((n) => /\(Write-?in\)/i.test(n))))),
      writeIns.map((r) => r.text).slice(0, 2).join(" || "));
    const rowsWhere = (test) => [].concat(...all.map((b) => [...b.D.querySelectorAll("section.race-foldable")]
      .filter((s) => test(b.window.KYC.races().filter((r) => r.id === s.getAttribute("data-race"))[0], s, b.window))));
    if (oldCongressSits(window)) {
      const moved = rowsWhere((r, s) => !!s.querySelector(".race-body > .race-held"));
      check("a holder running elsewhere is named as the section names them, never on this ballot",
        moved.length > 0 && moved.every((s) => {
          const row = readRow(s);
          const holder = /^(?:Open seat\. )?Held by (.+?), who /.exec(row.held);
          return holder && !row.ballot.some((g) => g.names.some((n) => n.indexOf(holder[1] + " (") === 0));
        }), moved.length + " rows");
      const renumbered = rowsWhere((r) => !!r.holderMoved);
      check("a renumbered member's old seat says where they run under the new map",
        renumbered.length > 0 && renumbered.every((s) => /under the state’s new district map/.test(readRow(s).held)));
      const appointed = rowsWhere((r) => !!(r.incumbent && r.incumbent.appointed));
      check("an appointee's seat is never \"re-election\" (rule 61)",
        appointed.length > 0 && appointed.every((s) => !/re-election/.test(readRow(s).held)),
        appointed.map((s) => readRow(s).held).join(" | "));
      const vacant = rowsWhere((r, s, w) => r.chamber === "House" && !r.incumbentIds.length &&
        !!w.KYC.vacancyOf(r.state, r.district || 0));
      check("an empty seat says when and why it is vacant",
        vacant.length > 0 && vacant.every((s) => /^Vacant since /.test(readRow(s).held)),
        vacant.map((s) => readRow(s).held).join(" | "));
    }
    // Byron Donalds is on Florida's ballot, for governor; a retiring
    // member's card says "Not running for re-election" (rule 61). The row
    // made the Open seat hover's "is not on the November ballot" visible.
    const outRows = rowsWhere((r, s, w) => {
      const h = r.openSeat && !r.holderMoved && r.incumbentIds.map(w.KYC.byId).filter(Boolean)[0];
      return !!h && !h.contestLabel && !h.alsoRunningSeat && !(h.raceRole === "winner" && h.raceId !== r.id) &&
        w.KYC.offBallot(h.raceStatus);
    });
    const outWords = (s) => {
      const b = all.filter((x) => x.D.contains(s))[0];
      const r = b.window.KYC.races().filter((x) => x.id === s.getAttribute("data-race"))[0];
      const h = b.window.KYC.byId(r.incumbentIds[0]);
      const other = b.window.KYC.otherOffice(h);
      return h.name + ": " + b.window.KYC.standing(h, "card").label + (other ? " · " + other.text : "") + ".";
    };
    check("a holder out of their seat's race reads in their card's words, row and Open seat hover alike (rule 61)",
      (!oldCongressSits(window) || outRows.length > 0) && outRows.every((s) => {
        const open = [...s.querySelectorAll(".race-head .badge")].filter((b) => b.textContent === "Open seat")[0];
        return readRow(s).held.indexOf(outWords(s)) !== -1 && !!open && open.getAttribute("title") === outWords(s);
      }), outRows.length + " rows: " + outRows.slice(0, 2).map((s) => readRow(s).held).join(" | "));
    const otherOffice = outRows.filter((s) => / · .*(nominee|Nominee)/.test(outWords(s)));
    check("an other office's nominee among them names that office, as their card does",
      !oldCongressSits(window) || otherOffice.length > 0, otherOffice.map((s) => readRow(s).held).join(" | "));
    const notOn = rowsWhere(() => true).filter((s) => / is not on the November ballot/.test(readRow(s).held));
    check("no row says a holder \"is not on the November ballot\"", notOn.length === 0,
      notOn.slice(0, 3).map((s) => readRow(s).held).join(" | "));
    const listed = rowsWhere((r) => !!(r.results && r.results.fromQualifiedList));
    // Once the new Congress sits, a member it seated reads as their own
    // card does (rule 68): the list's own words are asked only before.
    check("Louisiana's qualified list reads as the list's words, never a nominee (rule 64)",
      listed.every((s) => !/Nominee|Renominated|Advanced/.test(readRow(s).text) &&
        (!oldCongressSits(window) || readRow(s).ballot.every((g) =>
          /^On the Nov 3 ballot$|^Also /.test(g.label) || g.label === "2026 challenger"))),
      listed.map((s) => readRow(s).ballot.map((g) => g.label).join("/")).join(" | "));
    const allParty = rowsWhere((r) => r.primaryKind === "top-two");
    check("a top-two primary's people advanced, never \"nominee\" (rule 74)",
      allParty.length > 0 && allParty.every((s) => readRow(s).ballot.every((g) =>
        /^Advanced to November$|^Also /.test(g.label))),
      allParty.map((s) => readRow(s).ballot.map((g) => g.label).join("/")).filter((t) => !/^(Advanced|Also)/.test(t)).slice(0, 3).join(" | "));
    const unsettled = rowsWhere((r) => !!r.ballotUnknown);
    check("a filer the results do not settle is listed apart, never on the ballot (rule 62)",
      unsettled.every((s) => readRow(s).unsettled.length > 0 &&
        readRow(s).unsettled.every((g) => g.label !== "On the November ballot")), unsettled.length + " rows");
  });

  // Reading the rows after Election Day: the same table words them.
  const after = await buildPage("states/ca.html", { now: "2026-11-05T09:00:00",
    setup: (w) => phoneWidth(w, true) });
  suite("states/ca.html on a phone after Election Day — rows in the result's words (rule 63)", () => {
    const problems = rowProblems(after.window, after.D);
    check("each row still names its section's people in their cards' words", problems.length === 0,
      problems.slice(0, 3).join(" || "));
    const rows = [...after.D.querySelectorAll("section.race-foldable")].map(readRow);
    check("no row reads a pre-count \"Advanced to November\" for anyone still awaiting a result",
      rows.every((r) => !r.ballot.some((g) => g.label === "Advanced to November")),
      rows.map((r) => r.ballot.map((g) => g.label).join("/")).slice(0, 3).join(" | "));
    check("no row says its outcome twice, as its people's label and again as a badge",
      rows.every((r) => !r.badges.some((b) => r.ballot.some((g) => g.label === b))),
      rows.filter((r) => r.badges.some((b) => r.ballot.some((g) => g.label === b))).slice(0, 2).map((r) => r.text).join(" | "));
    const pastLine = after.D.querySelector(".find-race-statewide").textContent;
    check("the statewide line is in the past tense from the day after (rule 84)",
      /^Of what this site covers, the Nov 3, 2026 ballot held statewide: /.test(pastLine) &&
        pastLine.endsWith("It may also have held " + after.window.KYC.ballot.unlisted + "."), pastLine);
  });
  after.window.close();

  /* What a reader does with it. */
  const pick = (id) => D.getElementById("race-" + id);
  const isOpen = (s) => s.querySelector(".race-row").getAttribute("aria-expanded") === "true" &&
    !s.querySelector(".race-body").hasAttribute("hidden");
  const first = sections[0];
  const mid = sections[Math.floor(sections.length / 2)];
  first.querySelector(".race-row").click();
  const opened = isOpen(first) && first.classList.contains("is-open");
  first.querySelector(".race-row").click();
  const folded = !isOpen(first) && first.querySelector(".race-body").getAttribute("hidden") === "until-found";
  first.querySelector(".race-row").click();
  first.querySelector("[data-race-close]").click();
  const closedFocus = !isOpen(first) && D.activeElement === first.querySelector(".race-row");
  const select = D.getElementById("raceJumpSelect");
  // How each jump scrolls: at once, never animated (PR #126 review: a
  // smooth scroll past the delegation's growing cards stopped CA-40's jump
  // 850px short, below the screen).
  const scrolls = [];
  const realScroll = window.Element.prototype.scrollIntoView;
  window.Element.prototype.scrollIntoView = function (opts) {
    scrolls.push(opts && typeof opts === "object" ? opts.behavior || "auto" : "auto");
    if (realScroll) realScroll.call(this, opts);
  };
  select.value = mid.id;
  select.dispatchEvent(new window.Event("change", { bubbles: true }));
  const bySelect = isOpen(mid) && D.activeElement === mid.querySelector(".race-row") && select.value === "" &&
    sections.filter(isOpen).length === 1;
  // Arrow keys on a closed select change it as they go: no jump until Enter.
  const other = sections[1];
  select.dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
  select.value = other.id;
  select.dispatchEvent(new window.Event("change", { bubbles: true }));
  const arrowsWait = !isOpen(other);
  select.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
  const enterJumps = isOpen(other);
  mid.querySelector("[data-race-close]").click();
  other.querySelector("[data-race-close]").click();
  // Alt+Down opens the list itself, where a pick is a pick.
  const third = sections[2];
  select.dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowDown", altKey: true, bubbles: true }));
  select.value = third.id;
  select.dispatchEvent(new window.Event("change", { bubbles: true }));
  const listPicks = isOpen(third);
  third.querySelector("[data-race-close]").click();
  const tile = D.querySelector(".find-race-tiles .dt-seat");
  const tiled = D.getElementById(tile.getAttribute("href").slice(1));
  tile.click();
  const byTile = isOpen(tiled) && window.location.hash === "";
  tiled.querySelector("[data-race-close]").click();
  // The lookup's answer links a race by the page's own address.
  const answer = D.createElement("a");
  answer.href = KYC.stateUrl("CA") + "#" + mid.id;
  D.getElementById("findrep").appendChild(answer);
  answer.click();
  const byAnswer = isOpen(mid) && window.location.hash === "";
  answer.remove();
  const statewideLink = D.querySelector(".find-race-statewide a.state-jump");
  statewideLink.click();
  window.Element.prototype.scrollIntoView = realScroll;
  const instant = scrolls.length >= 4 && scrolls.every((b) => b === "auto");
  mid.querySelector("[data-race-close]").click();
  // Opening a profile and closing it leaves the page as it was (rule 45).
  mid.querySelector(".race-row").click();
  const card = mid.querySelector(".race-body .card");
  card.click();
  await settle(60);
  const profileOpen = KYC.profile.isOpen();
  KYC.profile.close();
  await settle(60);
  const kept = isOpen(mid) && pick(mid.getAttribute("data-race")) === mid && mid.querySelector(".race-body .card") === card;
  mid.querySelector("[data-race-close]").click();
  // Open all, and fold all again.
  const all = D.querySelector("[data-race-open-all]");
  all.click();
  const allOpen = sections.every(isOpen) && /^Fold all/.test(all.textContent);
  all.click();
  const allFolded = !sections.some(isOpen) && /^Open all/.test(all.textContent);
  // The browser's find opens what it found (beforematch), print opens all.
  const found = sections[3].querySelector(".race-body");
  found.removeAttribute("hidden");
  found.dispatchEvent(new window.Event("beforematch", { bubbles: true }));
  const byFind = sections[3].querySelector(".race-row").getAttribute("aria-expanded") === "true";
  sections[3].querySelector("[data-race-close]").click();
  window.dispatchEvent(new window.Event("beforeprint"));
  const printed = sections.every(isOpen);
  window.dispatchEvent(new window.Event("afterprint"));
  const unprinted = !sections.some(isOpen);
  suite("states/ca.html on a phone — every way to a race opens it", () => {
    check("a row's button opens its race in place, and folds it again", opened && folded);
    check("Close folds the race and puts the reader back on its row", closedFocus);
    check("a pick in the select opens that race alone and lands on its row", bySelect);
    check("arrow keys through a closed select do not jump; Enter does", arrowsWait && enterJumps);
    check("a pick from the list opened with Alt+Down jumps at once", listPicks);
    check("a district square opens its race, leaving the address alone", byTile);
    check("the lookup's link to a race on this page opens it, leaving the address alone", byAnswer);
    check("every jump - select, square, lookup, statewide line, Close - scrolls at once, never animated",
      instant, scrolls.join(","));
    check("opening and closing a profile keeps the open race and its nodes (rule 45)", profileOpen && kept);
    check("Open all opens every race and Fold all folds them", allOpen && allFolded);
    check("the browser's find-in-page opening a race marks its row open", byFind);
    check("printing opens every race and folds back what it opened", printed && unprinted);
  });

  // The page search opens the races holding a match and hides the rest.
  const input = D.getElementById("stateSearch");
  const person = KYC.byId(mid.querySelector(".race-body .card").getAttribute("data-id"));
  input.value = person.name;
  input.dispatchEvent(new window.Event("input"));
  await settle(200);
  const searched = isOpen(mid) && sections.some((s) => s.hidden) &&
    sections.filter((s) => !s.hidden).every((s) => isOpen(s));
  input.value = "";
  input.dispatchEvent(new window.Event("input"));
  await settle(200);
  const cleared = !sections.some((s) => s.hidden) && !sections.some(isOpen);
  // A name only the row gives - the results' with no profile here - keeps
  // that row; a turned tablet keeps the search (PR #126 review).
  const rowOnly = sections.filter((s) => readRow(s).ballot.some((g) => /^Also on/.test(g.label)))[0];
  const rowName = rowOnly && readRow(rowOnly).ballot.filter((g) => /^Also on/.test(g.label))[0].names[0]
    .replace(/ \(.*$/, "");
  input.value = rowName || "";
  input.dispatchEvent(new window.Event("input"));
  await settle(200);
  const keptRow = !!rowOnly && !rowOnly.hidden && sections.some((s) => s.hidden);
  const hiddenBefore = sections.map((s) => s.hidden).join();
  turn(window, false);
  const wideShown = !sections.some((s) => s.hidden);
  turn(window, true);
  const heldOnTurn = sections.map((s) => s.hidden).join() === hiddenBefore;
  input.value = "";
  input.dispatchEvent(new window.Event("input"));
  await settle(200);
  suite("states/ca.html on a phone — the page's search", () => {
    check("a search opens the races holding a match and hides those holding none", searched);
    check("clearing it shows every row and folds back what it opened", cleared);
    check("a name only a row gives keeps that row in view", keptRow, rowName);
    check("a turned tablet keeps the search: every race shown wide, the same rows back narrow",
      wideShown && heldOnTurn);
  });

  // A tablet turned past 1000px is the desktop page, and back.
  mid.querySelector(".race-row").click();
  turn(window, false);
  const wide = block.hidden && !races.classList.contains("races-folded") &&
    sections.every((s) => s.querySelector(".race-row-title").hidden && !s.querySelector(".race-body").hasAttribute("hidden")) &&
    D.getElementById("findrep").nextElementSibling === D.getElementById("voting") &&
    !!races.querySelector(".district-tiles") && !D.querySelector(".state-parts").hidden &&
    !!D.querySelector(".state-hero .state-links");
  turn(window, true);
  const narrow = !block.hidden && !!block.querySelector("#findrep") && isOpen(mid) &&
    sections.filter(isOpen).length === 1;
  suite("states/ca.html — a turned tablet moves the parts, never redraws them", () => {
    check("past 1000px every race is open and every part back where the desktop has it", wide);
    check("back under it the page folds again, keeping the race the reader had open", narrow);
  });
  PAGES.forEach((st) => built[st].window.close());

  // A race reached by a link from another page opens on arrival.
  const linked = await buildPage("states/tx.html", { hash: "#race-H-TX-07-2026",
    setup: (w) => phoneWidth(w, true) });
  const target = linked.D.getElementById("race-H-TX-07-2026");
  suite("states/tx.html#race-… on a phone — a shared race's link opens it", () => {
    check("the linked race is open and the rest folded", !!target && isOpen(target) &&
      [...linked.D.querySelectorAll("section.race-foldable")].filter(isOpen).length === 1);
    check("and the fragment is dropped from the address", linked.window.location.hash === "");
  });
  linked.window.close();

  // Desktop is unchanged; a state with four races or fewer never folds.
  const wideCa = await buildPage("states/ca.html", { setup: (w) => phoneWidth(w, false) });
  const small = await buildPage("states/ut.html", { setup: (w) => phoneWidth(w, true) });
  suite("states/ca.html at 1000px and wider, and a small state on a phone — as before", () => {
    const W = wideCa.D;
    check("no fold: the block hidden, every row hidden, every race open",
      W.getElementById("find-race").hidden && !W.getElementById("races").classList.contains("races-folded") &&
      [...W.querySelectorAll("section.race-foldable")].every((s) => s.querySelector(".race-row-title").hidden &&
        !s.querySelector(".race-body").hasAttribute("hidden") && s.querySelector(".race-close-row").hidden));
    check("every head keeps all its badges, the shared ones too",
      [...W.querySelectorAll(".race-head")].every((h) => h.querySelectorAll(".badge-shared").length > 0) &&
        W.querySelector(".race-fold-bar").hidden);
    check("the parts stay where they were: lookup before voting, squares with the races, chips shown",
      W.getElementById("findrep").nextElementSibling === W.getElementById("voting") &&
      !!W.querySelector("#races .district-tiles") && !W.querySelector(".state-parts").hidden);
    const races = small.window.KYC.races().filter((r) => r.state === "UT").length;
    check("a state with four races or fewer never folds", races <= 4 && !small.D.getElementById("find-race") &&
      !small.D.querySelector("section.race-foldable"), races + " races");
  });
  wideCa.window.close();
  small.window.close();
}

/* ===================================================== photo copies */

/* Rule 101, the owner's decision of 2026-10-25: a heavy portrait the site
 * already shows is shown as a smaller copy made here, from the site's root
 * at any depth, credited as the original's and linking the original file;
 * a copy that fails to load gives way to its original. And a justice's
 * official portrait says the year Commons dates it to. */
async function testPhotoCopies() {
  const COPY = "photos/0123456789abcdef0123.jpg?v=0123456789";
  {
    const { window, D, errors } = await buildPage("legislature/ok.html");
    const KYC = window.KYC;
    const state = window.kycLegislature.OK;
    suite("legislature/ok.html — a heavy portrait, as the copy made here", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const everyone = [].concat(...Object.values(state.chambers.upper.members),
        ...Object.values(state.chambers.lower.members), state.unplaced);
      const copied = everyone.filter((p) => p.photoCopy);
      check("every copy in the file is the copy of that member's own portrait, credited",
        copied.every((p) => p.photoCopy.of === p.image && p.imageCredit &&
          /^photos\/[0-9a-f]{20}\.jpg\?v=[0-9a-f]{10}$/.test(p.photoCopy.src)),
        copied.filter((p) => p.photoCopy.of !== p.image).map((p) => p.name).join(", "));
      // A member of the Senate, given a copy here so the check never depends
      // on what the last run copied.
      const id = Object.keys(state.chambers.upper.members)[0];
      const p = state.chambers.upper.members[id][0];
      const original = p.image;
      p.photoCopy = { src: COPY, of: original };
      p.imageCredit = p.imageCredit || { by: "oksenate.gov", via: "Open States" };
      const shape = D.querySelector(`#legMap .district-statewide [data-region="${id}"]`);
      shape.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
      const card = [...D.querySelectorAll("#legPanelBody .leg-person")].find((el) =>
        el.textContent.includes(p.name));
      const img = card && card.querySelector(".leg-photo");
      check("the card loads the copy from the site's root, one folder up",
        !!img && img.getAttribute("src") === "../" + COPY, img && img.getAttribute("src"));
      check("and knows the original it falls back to",
        !!img && img.getAttribute("data-photo-original") === original);
      const credit = card.querySelector(".leg-credit");
      check("the credit stays the original's and says the copy is the site's, linking the original",
        !!credit && credit.textContent.indexOf("Photo: " + p.imageCredit.by) === 0 &&
        /a smaller copy made by this site of the original file$/.test(credit.textContent) &&
        !!credit.querySelector('.photo-copy-note a[href="' + original + '"]'), credit && credit.innerHTML);
      img.dispatchEvent(new window.Event("error"));
      check("a copy that fails gives way to its original, once",
        card.querySelector(".leg-photo") === img && img.getAttribute("src") === original &&
        !img.hasAttribute("data-photo-original"), img.getAttribute("src"));
      check("and the credit stops calling it a copy",
        !!card.querySelector(".leg-credit") && !card.querySelector(".photo-copy-note"));
      img.dispatchEvent(new window.Event("error"));
      check("the original failing too takes the photograph and its credit away",
        !card.querySelector(".leg-photo") && !card.querySelector(".leg-credit"));
      check("escaped: a credit's words are text",
        KYC.photoCreditHtml({ by: "<b>x</b>", copyOf: 'https://e.x/a"b.jpg' }).indexOf("<b>") === -1);
      check("a copy that is not of this address is never used",
        KYC.photoSrc("https://e.x/a.jpg", { src: COPY, of: "https://e.x/b.jpg" }) === "https://e.x/a.jpg");
      // The link to the original says how heavy it is (PR #137 review): one
      // tap on a phone fetched 9 to 12 MB.
      const weighed = KYC.photoCreditHtml(KYC.copyCredit({ by: "Oklahoma Legislature" }, "https://e.x/a.jpg",
        { src: COPY, of: "https://e.x/a.jpg", ofBytes: 12_400_000 })).replace(/<[^>]+>/g, "");
      check("the original's weight is in its link",
        /a smaller copy made by this site of the original file \(12\.4 MB\)$/.test(weighed), weighed);
      check("a weight under a megabyte in KB, a whole one without a decimal",
        KYC.weightWords(820_400) === "820 KB" && KYC.weightWords(2_000_000) === "2 MB");
      check("an Open States listing names where the file is, never whose it is",
        KYC.photoCreditHtml({ host: "www.chicagotribune.com", listedBy: "Open States" }) ===
          "Photo: from www.chicagotribune.com, as listed by Open States");
      // A Commons photograph says the year its file's page gives (the
      // owner's brief of 2026-10-25: Tad Jude's 1981 portrait read as
      // current); a justice's official words stand; no year, no words.
      const plainText = (c) => KYC.photoCreditHtml(c).replace(/<[^>]+>/g, "");
      // One phrase, true of a painted portrait too: "Photograph, 2012." was
      // printed under a judge's oil portrait (the PR #139 review).
      check("a Commons credit says its year in the one phrase",
        plainText({ by: "The Minnesota Legislature", licence: "Public domain", year: 1981,
          page: "https://commons.wikimedia.org/wiki/File:X.jpg", via: "Wikimedia Commons" }) ===
          "Photo (1981): The Minnesota Legislature, Public domain, via Wikimedia Commons");
      check("a justice's official portrait keeps its own words",
        /^Official portrait, 2005\. Photo: /.test(plainText({ by: "Steve Petteway", licence: "Public domain",
          year: 2005, dated: "Official portrait, 2005", via: "Wikimedia Commons" })) &&
        !/\(2005\)/.test(plainText({ by: "Steve Petteway", licence: "Public domain",
          year: 2005, dated: "Official portrait, 2005", via: "Wikimedia Commons" })));
      check("no year, or one that is not a single four-digit year, says none",
        /^Photo: X/.test(plainText({ by: "X", licence: "CC0", via: "Wikimedia Commons" })) &&
        /^Photo: X/.test(plainText({ by: "X", licence: "CC0", year: "1990s" })) &&
        !/Photograph/.test(plainText({ by: "X", licence: "CC0", year: 1990 })));
    });
    window.close();
  }
  {
    const { window, D, errors } = await buildPage("federal/index.html");
    const KYC = window.KYC;
    const d = window.kycFederal;
    suite("federal/index.html — a White House photograph, as the copy made here", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const people = [d.president, d.vicePresident].concat(d.offices.map((o) => o.holder).filter(Boolean));
      check("every copy is the copy of that official's own photograph",
        people.every((p) => !p.photoCopy || p.photoCopy.of === p.photo));
      const office = d.offices.find((o) => o.holder && o.holder.photo);
      const holder = office.holder;
      const kept = holder.photoCopy;
      holder.photoCopy = { src: COPY, of: holder.photo };
      KYC.official.open(holder.id);
      const photo = D.getElementById("officialModalPhoto");
      const credit = D.getElementById("officialModalPhotoCredit");
      check("the dialog shows the copy, one size, from the site's root",
        photo.getAttribute("src") === "../" + COPY && !photo.getAttribute("srcset"),
        photo.getAttribute("src"));
      check("credited to the White House, a copy made here of the original file",
        credit.textContent === "Photo: The White House; a smaller copy made by this site of the original file" &&
        !!credit.querySelector('a[href="' + holder.photo + '"]'), credit.textContent);
      photo.dispatchEvent(new window.Event("error"));
      // Never the heavy original itself: the White House's own smallest
      // rendition of the file, as before the copies (PR #137 review).
      const lighter = holder.photoSet && holder.photoSet.length ? holder.photoSet[0][0] : holder.photo;
      check("a copy that fails gives way to the White House's own rendition, and the credit says only whose it is",
        photo.getAttribute("src") === lighter && credit.textContent === "Photo: The White House" &&
        !D.getElementById("officialModalPortrait").hidden, photo.getAttribute("src"));
      check("that rendition is a smaller size of the same file",
        !holder.photoSet || !holder.photoSet.length ||
          lighter.split("?")[0] === holder.photo.split("?")[0], lighter);
      KYC.official.close();
      const card = KYC.official.pictureTag(holder, 72, "fed-photo");
      check("the hub's card loads the copy too", card.indexOf('src="../' + COPY + '"') !== -1 &&
        card.indexOf('data-photo-original="' + KYC.escapeAttr(lighter) + '"') !== -1, card);
      // A copy of another address is not this photograph's: the White
      // House's own sizes are drawn, as on a page with no copies.
      holder.photoCopy = { src: COPY, of: "https://www.whitehouse.gov/other.jpg" };
      const own = KYC.official.pictureTag(holder, 72, "fed-photo");
      check("a copy of another photograph falls through to the White House's own sizes",
        own.indexOf(COPY) === -1 && own.indexOf("data-photo-original") === -1 &&
        (!holder.photoSet || !holder.photoSet.length || own.indexOf("srcset=") !== -1), own);
      holder.photoCopy = kept;
    });
    suite("federal/index.html — a justice's official portrait says its year", () => {
      const dated = d.supremeCourt.members.filter((j) => j.portrait && j.portrait.year);
      check("the Commons portraits carry the year Commons dates them to", dated.length > 0);
      const roberts = d.supremeCourt.members.find((j) => /Roberts/.test(j.name));
      if (roberts && roberts.portrait && roberts.portrait.year) {
        KYC.official.open(roberts.id);
        const text = D.getElementById("officialModalPhotoCredit").textContent;
        check("“Official portrait, 2005”, before whose photograph it is",
          text.indexOf("Official portrait, " + roberts.portrait.year + ". Photo: ") === 0 &&
          roberts.portrait.year === 2005, text);
        KYC.official.close();
      }
      const undated = d.supremeCourt.members.find((j) => j.portrait && !j.portrait.year);
      if (undated) {
        KYC.official.open(undated.id);
        check("a portrait Commons does not date says no year",
          !/Official portrait, \d/.test(D.getElementById("officialModalPhotoCredit").textContent));
        KYC.official.close();
      }
    });
    window.close();
  }
  {
    /* Every Commons photograph's credit says the year its file's page
     * gives (the owner's brief of 2026-10-25): Tad Jude's 1981 Minnesota
     * Legislature portrait, a statewide candidate's, read as current. */
    const { window, D, errors } = await buildPage("states/mn.html");
    suite("states/mn.html — a Commons photograph's credit says its year", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const jude = [...D.querySelectorAll("*")].filter((el) => el.children.length === 0 &&
        /Photo \(1981\): The Minnesota Legislature/.test(el.parentNode.textContent));
      check("Tad Jude's portrait is dated 1981 in its credit", jude.length > 0);
    });
    window.close();
  }
  {
    const { window, D, errors } = await buildPage("states/ok.html");
    const KYC = window.KYC;
    suite("states/ok.html — an officer's and a governor's photograph, as the copy made here", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const s = window.kycStateGov.states.OK;
      const off = ["lt", "ag", "sos"].map((k) => s[k]).find((o) => o && o.photo && !o.disputed &&
        !o.unlisted && !o.unconfirmed && !o.vacant && !o.none && !o.notMember);
      const gov = s.governor;
      const keep = [off && off.photoCopy, gov.photoCopy];
      if (off) off.photoCopy = { src: COPY, of: off.photo };
      if (gov.headshot) gov.photoCopy = { src: COPY, of: gov.headshot };
      const host = D.createElement("div");
      host.innerHTML = KYC.stategov.render("OK");
      if (off) {
        const img = host.querySelector(".gov-officer-photo");
        check("an officer's row loads the copy", !!img && img.getAttribute("src") === "../" + COPY &&
          img.getAttribute("data-photo-original") === off.photo);
      }
      if (gov.headshot) {
        const img = host.querySelector(".gov-portrait");
        check("the governor's card loads the copy", !!img && img.getAttribute("src") === "../" + COPY);
        const said = () => [...host.querySelectorAll(".photo-copy-note")].some((n) =>
          n.getAttribute("data-copy-of") === gov.headshot);
        check("the list of sources says the governor's photograph is a copy made here", said(),
          host.textContent.slice(-400));
        D.body.appendChild(host);
        img.dispatchEvent(new window.Event("error"));
        check("a governor's copy that fails gives way to the original, not to nothing",
          host.contains(img) && img.getAttribute("src") === gov.headshot);
        // ...and the sources stop calling it a copy (PR #137 review).
        check("and the list of sources stops calling it a copy", !said());
        host.remove();
      }
      if (off) off.photoCopy = keep[0];
      gov.photoCopy = keep[1];
    });
    window.close();
  }
  {
    // #135's photographs go through the same copies (rule 101): a justice's
    // from the court's own pages and a statewide candidate's.
    const { window, D, errors } = await buildPage("states/az.html");
    const KYC = window.KYC;
    suite("states/az.html — a justice's and a statewide candidate's photograph, as the copy made here", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const s = window.kycStateGov.states.AZ;
      const court = s.court || {};
      const name = Object.keys(court.photos || {})[0];
      const shot = name && court.photos[name];
      const rows = Object.values((s.ballot2026 || {}).offices || {})
        .flatMap((item) => ((item.candidates || {}).candidates || []));
      const row = rows.find((p) => p.photo && p.photoCredit && !p.writeIn);
      check("Arizona shows a justice's and a candidate's photograph to copy", !!shot && !!row);
      if (!shot || !row) return;
      const keep = [shot.photoCopy, row.photoCopy];
      shot.photoCopy = { src: COPY, of: shot.photo, ofBytes: 2400000 };
      row.photoCopy = { src: COPY, of: row.photo };
      const host = D.createElement("div");
      host.innerHTML = KYC.stategov.render("AZ");
      const justice = [...host.querySelectorAll(".gov-court-photo")].find((img) =>
        img.getAttribute("data-photo-original") === shot.photo);
      const candidate = [...host.querySelectorAll(".gov-candidate-photo")].find((img) =>
        img.getAttribute("data-photo-original") === row.photo);
      check("the justice's row loads the copy, and knows its original",
        !!justice && justice.getAttribute("src") === "../" + COPY);
      check("the candidate's row loads the copy, and knows its original",
        !!candidate && candidate.getAttribute("src") === "../" + COPY);
      const note = (img) => img && img.closest("li").querySelector(".photo-copy-note");
      check("the justice's credit stays the court's and says it is a copy made here, with the weight",
        !!note(justice) && /^Photo: Supreme Court of Arizona; a smaller copy made by this site of the original file \(2\.4 MB\)$/
          .test(justice.closest("li").querySelector(".gov-photo-credit").textContent),
        justice && justice.closest("li").querySelector(".gov-photo-credit").textContent);
      check("the candidate's credit says it is a copy made here", !!note(candidate));
      D.body.appendChild(host);
      justice.dispatchEvent(new window.Event("error"));
      check("a justice's copy that fails gives way to the original, and stops calling it a copy",
        host.contains(justice) && justice.getAttribute("src") === shot.photo && !note(justice) &&
        /^Photo: Supreme Court of Arizona$/.test(
          justice.closest("li").querySelector(".gov-photo-credit").textContent));
      host.remove();
      shot.photoCopy = { src: COPY, of: "https://www.azcourts.gov/another.jpg" };
      row.photoCopy = { src: COPY, of: "https://www.azcleanelections.gov/another.jpg" };
      host.innerHTML = KYC.stategov.render("AZ");
      check("a copy of another address is never drawn for a justice or a candidate",
        host.innerHTML.indexOf(COPY) === -1 && host.querySelectorAll(".photo-copy-note").length === 0);
      shot.photoCopy = keep[0];
      row.photoCopy = keep[1];
      if (!shot.photoCopy) delete shot.photoCopy;
      if (!row.photoCopy) delete row.photoCopy;
    });
    window.close();
  }
  {
    const { window, errors } = await buildPage("index.html");
    const KYC = window.KYC;
    suite("index.html — a profile's heavy portrait, as the copy made here", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const url = "https://campaign.example/heavy.png";
      const item = { id: "t", photos: [url, "placeholder"], photoSet: [[330, url]],
                     photoCredit: { by: "campaign.example", page: "https://campaign.example/" },
                     photoCopy: { src: COPY, of: url } };
      const attrs = KYC.portraitAttrs(item, "165px");
      check("the card loads the copy, with no srcset, and knows its original",
        attrs.indexOf('src="' + COPY + '"') === 0 && attrs.indexOf("srcset") === -1 &&
        attrs.indexOf('data-photo-original="' + url + '"') !== -1, attrs);
      const img = window.document.createElement("img");
      KYC.setPortrait(img, item, "116px");
      check("the dialog credits the copy as the campaign's photograph, made smaller here",
        /a smaller copy made by this site of the original file$/.test(
          KYC.photoCreditHtml(KYC.shownPhotoCredit(img, item)).replace(/<[^>]+>/g, "")));
      img.setAttribute("src", url);
      check("and the original as the campaign's alone once the copy gave way",
        KYC.photoCreditHtml(KYC.shownPhotoCredit(img, item)).indexOf("smaller copy") === -1);
      check("a copy of another address is never this profile's",
        KYC.portraitSrc({ photos: [url], photoCopy: { src: COPY, of: "https://x.example/y.png" } }) === url);
    });
    window.close();
  }
}

/* ============================================ election offices' guides */

/* The owner's decision of 2026-10-25 (kyc/guide_photos.py): an election
 * office's guide that prints a candidate's photograph beside their name but
 * gives it no address - Washington's voters' guide, Alaska's pamphlet - is
 * shown from an unmodified copy hosted under photos/, from the site's root
 * at any depth, credited to the guide and linked to the candidate's page in
 * it; a heavy one as the smaller copy made of it, which gives way to the
 * hosted file, never to a broken relative address. */
async function testGuidePhotos() {
  const HOSTED = "photos/0123456789abcdef0123.jpg";
  const COPY = "photos/fedcba98765432100123.jpg?v=fedcba9876";
  {
    const { window, D, errors } = await buildPage("states/wa.html");
    const KYC = window.KYC;
    suite("states/wa.html — a nominee's photograph from the voters' guide, hosted here", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const guided = KYC.people().filter((p) => p.photoSource === "election-guide");
      check("every guide photograph in the data is a file hosted here, credited to the guide and its page",
        guided.every((p) => /^photos\/[0-9a-f]{20}\.(jpg|png)$/.test(p.photos[0]) &&
          p.photo_url === p.photos[0] && /voters' guide$/.test((p.photoCredit || {}).by || "") &&
          /^https:\/\/voter\.votewa\.gov\//.test((p.photoCredit || {}).page || "")),
        guided.map((p) => p.name).join(", "));
      const item = { id: "t", name: "A Nominee", photos: [HOSTED, "placeholder"],
                     photoCredit: { by: "from the Washington Secretary of State's voters' guide",
                                    page: "https://voter.votewa.gov/genericvoterguide.aspx?e=899&c=99#/candidates/1/2" } };
      const attrs = KYC.portraitAttrs(item, "165px");
      check("the card loads the hosted file from the site's root, one folder up",
        attrs.indexOf('src="../' + HOSTED + '"') === 0 && attrs.indexOf("data-photo-original") === -1, attrs);
      check("one helper for every portrait resolves it", KYC.photoSrc(HOSTED) === "../" + HOSTED &&
        KYC.photoHref("https://e.x/a.jpg") === "https://e.x/a.jpg");
      const img = D.createElement("img");
      KYC.setPortrait(img, item, "116px");
      const line = KYC.photoCreditHtml(KYC.shownPhotoCredit(img, item));
      const text = (html) => { const el = D.createElement("p"); el.innerHTML = html; return el.textContent; };
      check("the dialog credits where it was found, the guide, linked to the candidate's page in it",
        text(line) === "Photo: from the Washington Secretary of State's voters' guide" &&
        line.indexOf('href="' + item.photoCredit.page.replace(/&/g, "&amp;") + '"') !== -1, line);
      // A heavy one (Duresky's 4.2 MB): the smaller copy made of the hosted file.
      item.photoCopy = { src: COPY, of: HOSTED, ofBytes: 4228148 };
      KYC.setPortrait(img, item, "116px");
      check("a heavy one loads the copy, and falls back to the hosted file at its real address",
        img.getAttribute("src") === "../" + COPY && img.getAttribute("data-photo-original") === "../" + HOSTED &&
        img.getAttribute("data-photo-of") === HOSTED, img.outerHTML);
      const said = KYC.photoCreditHtml(KYC.shownPhotoCredit(img, item));
      check("its credit stays the guide's, and links the hosted original with its weight",
        /^Photo: from the Washington Secretary of State's voters' guide; a smaller copy made by this site of the original file \(4\.2 MB\)$/
          .test(text(said)) && said.indexOf('href="../' + HOSTED + '"') !== -1, said);
      const host = D.createElement("div");
      host.innerHTML = '<img ' + KYC.portraitAttrs(item, "165px") + '><p>' + said + "</p>";
      D.body.appendChild(host);
      const card = host.querySelector("img");
      card.dispatchEvent(new window.Event("error"));
      check("a copy that fails gives way to the hosted file, and the note that it was a copy goes",
        card.getAttribute("src") === "../" + HOSTED && !host.querySelector(".photo-copy-note"),
        card.getAttribute("src"));
      host.remove();
    });
    window.close();
  }
  {
    const { window, D, errors } = await buildPage("states/ak.html");
    const KYC = window.KYC;
    suite("states/ak.html — a statewide candidate's photograph from the pamphlet, hosted here", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const s = window.kycStateGov.states.AK;
      const rows = Object.values((s.ballot2026 || {}).offices || {})
        .flatMap((item) => ((item.candidates || {}).candidates || []));
      const hosted = rows.filter((p) => /^photos\//.test(p.photo || ""));
      check("every hosted row is a file under photos/, credited to the pamphlet's statement",
        hosted.every((p) => /^photos\/[0-9a-f]{20}\.(jpg|png)$/.test(p.photo) && !p.writeIn &&
          p.photoCredit.by === "from the Alaska Division of Elections' Official Election Pamphlet" && !p.photoCredit.converted &&
          /^https:\/\/elections\.alaska\.gov\/doc\/oep\/2026\/.+\.pdf$/.test(p.photoCredit.page)),
        hosted.map((p) => p.name).join(", "));
      const row = rows.find((p) => !p.writeIn);
      check("Alaska lists a candidate to draw", !!row);
      if (!row) return;
      const keep = [row.photo, row.photoCredit, row.photoCopy];
      row.photo = HOSTED;
      row.photoCredit = { by: "from the Alaska Division of Elections' Official Election Pamphlet",
                          page: "https://elections.alaska.gov/doc/oep/2026/A.pdf" };
      delete row.photoCopy;
      const host = D.createElement("div");
      host.innerHTML = KYC.stategov.render("AK");
      const img = [...host.querySelectorAll(".gov-candidate-photo")].find((el) =>
        el.getAttribute("src") === "../" + HOSTED);
      check("the row loads the hosted file from the site's root", !!img);
      const credit = img && img.closest("li").textContent;
      check("and credits the pamphlet", !!credit &&
        credit.indexOf("Photo: from the Alaska Division of Elections' Official Election Pamphlet") !== -1 &&
        credit.indexOf("converted") === -1, credit);
      row.photoCopy = { src: COPY, of: HOSTED, ofBytes: 321884 };
      host.innerHTML = KYC.stategov.render("AK");
      const copied = [...host.querySelectorAll(".gov-candidate-photo")].find((el) =>
        el.getAttribute("src") === "../" + COPY);
      check("a heavy one is the copy, falling back to the hosted file at its real address",
        !!copied && copied.getAttribute("data-photo-original") === "../" + HOSTED);
      [row.photo, row.photoCredit, row.photoCopy] = keep;
      if (!row.photo) delete row.photo;
      if (!row.photoCredit) delete row.photoCredit;
      if (!row.photoCopy) delete row.photoCopy;
    });
    window.close();
  }
  {
    // Oregon's pamphlet holds JPEG 2000, which no browser draws: the file
    // hosted is this site's lossless PNG of it, and the credit says so, as a
    // smaller copy's does (the review of PR #138); a guide's own bytes never.
    const { window, D, errors } = await buildPage("states/or.html");
    const KYC = window.KYC;
    suite("states/or.html — a pamphlet photograph this site decoded says so", () => {
      check("no page errors", errors.length === 0, errors.join(" | "));
      const text = (html) => { const el = D.createElement("p"); el.innerHTML = html; return el.textContent; };
      const NOTE = "; converted by this site to PNG from the pamphlet's JPEG 2000 image, pixel for pixel";
      const guided = KYC.people().filter((p) => p.photoSource === "election-guide");
      check("Oregon's guide photographs are PNGs hosted here, each credited as converted",
        guided.length > 0 && guided.every((p) => /^photos\/[0-9a-f]{20}\.png$/.test(p.photos[0]) &&
          (p.photoCredit || {}).by === "from the Oregon Secretary of State's State Voters' Pamphlet" &&
          /^https:\/\/sos\.oregon\.gov\/.+#page=\d+$/.test(p.photoCredit.page) &&
          text(KYC.photoCreditHtml(p.photoCredit)) ===
            "Photo: from the Oregon Secretary of State's State Voters' Pamphlet" + NOTE),
        guided.map((p) => p.name + ": " + text(KYC.photoCreditHtml(p.photoCredit || {}))).join(" | "));
      const s = window.kycStateGov.states.OR;
      const rows = Object.values((s.ballot2026 || {}).offices || {})
        .flatMap((item) => ((item.candidates || {}).candidates || []))
        .filter((p) => /^photos\//.test(p.photo || ""));
      check("a statewide candidate's decoded photograph says so on the state page too",
        rows.length > 0 && rows.every((p) => p.photoCredit.converted) &&
          rows.every((p) => KYC.stategov.render("OR").indexOf(KYC.escapeHtml(p.photoCredit.converted)) !== -1),
        rows.map((p) => p.name).join(", "));
      const unmodified = { by: "from the Washington Secretary of State's voters' guide", page: "https://voter.votewa.gov/g#/candidates/1/2" };
      check("a guide's own bytes carry no such note", text(KYC.photoCreditHtml(unmodified)).indexOf("converted") === -1);
    });
    window.close();
  }
}

(async function main() {
  const only = process.argv[2];
  if (!only || only === "split") await testPeopleSplit();
  if (!only || only === "index.html" || only === "votes") await testVotes();
  if (!only || only === "money") await testRaceMoney();
  if (!only || only === "charts") await testCharts();
  if (!only || only === "guide") await testGuide();
  if (!only || only === "guide") await testBillFlow();
  if (!only || only === "federal") await testFederal();
  if (!only || only === "legislature") await testLegislatures();
  if (!only || only === "photos" || only === "legislature") await testPhotoCopies();
  if (!only || only === "photos") await testGuidePhotos();
  if (!only || only === "counties") await testCounties();
  if (!only || only === "stategov") await testStateGov();
  if (!only || only === "index.html") await testDirectoryAsync();
  if (!only || only === "index.html") await testSenate();
  if (!only || only === "index.html") await testBallotCounts();
  if (!only || only === "index.html") await testRenumbered();
  if (!only || only === "index.html") await testPhoneMenus();
  if (!only || only === "index.html") await testBootSurvivesAFailure();
  if (!only || only === "index.html" || only === "search") await testSearchAndFilters();
  if (!only || only === "index.html" || only === "search") await testSearchAnswers();
  if (!only || only === "federal" || only === "search") await testJudgeSearch();
  if (!only || only === "index.html") await testReseatedSpecial();
  if (!only || only === "index.html") await testFormerIncumbent();
  if (!only || only === "index.html") await testRecordPhase();
  if (!only || only === "states") await testSenateWinner();
  if (!only || only === "guide") await testCommitteesPending();
  if (!only || only === "index.html") await testOdds();
  if (!only || only === "index.html") await testSeatRows();
  if (!only || only === "map.html") await testMap();
  if (!only || only === "map.html") await testMapOnAPhone();
  if (!only || only === "index.html") await testDrawerBack();
  if (!only || only === "index.html") await testAndroidBack();
  if (!only || only === "states") await testStates();
  if (!only || only === "states" || only === "statephone") await testStatePhone();
  if (!only || only === "states") await testElectionNight();
  if (!only || only === "states") await testQualifiedBallot();
if (!only || only === "states") await testCertifiedBallots();
  if (!only || only === "redistricting") await testRedistricting();
  if (!only || only === "redistricting") await testDistrictPages();
  if (!only || only === "redistricting") await testFindMyDistrict();
  if (!only || only === "findrep") await testFindRep();
  if (!only || only === "ballot" || only === "findrep") await testBallot();
  if (!only || only === "ballot" || only === "states") await testMeasures();
  if (!only || only === "findrep") await testFindRepNav();
  if (!only || only === "index.html") await testContactActions();
  if (!only || only === "index.html") await testPayLine();
  if (!only || only === "redistricting") await testDistrictsOnAPhone();
  if (!only || only === "links") await testInterlinks();
  if (!only || only === "links") await testNavigation();
  if (!only || only === "links") await testDeepLinks();
  if (!only || only === "links") await testFoldedIds();
  if (!only || only === "links") await testRunningElsewhere();
  if (!only || only === "index.html") await testPeopleWording();
  if (!only || only === "index.html") await testPeopleWordingAfterElection();
  if (!only || only === "frame") await testFrame();
  if (!only || only === "share") await testSharePages();
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
