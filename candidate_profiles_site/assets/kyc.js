/* Know Your Candidate - shared behaviour for index.html and map.html.
 *
 * Loaded in <head>; everything that touches the DOM waits for DOMContentLoaded.
 *
 * This file carries anything both pages need. The two pages had already
 * drifted apart once - the map still rendered raw "N/A (No net worth
 * disclosure provided in sources)" placeholder prose months after the grid
 * stopped - so shared behaviour lives here and nowhere else.
 */
(function (global) {
  "use strict";

  var doc = global.document;

  /* =============================================================== icons */

  /* An inline SVG sprite, replacing the `unpkg.com/lucide@latest` script.
   * That was an unpinned dependency (`@latest` - whatever shipped today) and
   * a whole icon library fetched to draw about twenty glyphs. Sprite symbols
   * are referenced with <use>, so each icon's geometry exists once in the
   * document no matter how many cards render it. */
  var ICONS = {
    menu: "M3 6h18M3 12h18M3 18h18",
    vote: "M9 12l2 2 4-4M3 7l9-4 9 4v10l-9 4-9-4z",
    // A ballot sheet, one row marked: "Your ballot" and the ways to it,
    // beside "How to vote", which the site's own mark (vote) draws.
    ballot: "M5 3h14v18H5zM8 8.5l1.3 1.3L12 7M14 8.5h2M8 14h3v3H8zM14 15.5h2",
    search: "M11 11m-7 0a7 7 0 1 0 14 0a7 7 0 1 0-14 0M20 20l-4.5-4.5",
    "search-x": "M11 11m-7 0a7 7 0 1 0 14 0a7 7 0 1 0-14 0M20 20l-4.5-4.5M9 9l4 4M13 9l-4 4",
    grid: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
    map: "M9 4L3 7v13l6-3 6 3 6-3V4l-6 3zM9 4v13M15 7v13",
    flag: "M4 21V4M4 4h12l-2 4 2 4H4",
    x: "M18 6L6 18M6 6l12 12",
    user: "M12 11m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0M5 21c0-3.9 3.1-7 7-7s7 3.1 7 7",
    scroll: "M6 4h11a2 2 0 0 1 2 2v11a3 3 0 0 0 3 3H7a3 3 0 0 1-3-3V6a2 2 0 0 1 2-2zM9 8h7M9 12h7",
    dollar: "M12 2v20M17 6.5c0-1.9-2.2-3-5-3s-5 1.1-5 3 2.2 3 5 3.5 5 1.6 5 3.5-2.2 3-5 3-5-1.1-5-3",
    chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
    layers: "M12 3l9 5-9 5-9-5zM3 13l9 5 9-5M3 17l9 5 9-5",
    pin: "M12 22s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11zM12 11m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0",
    calendar: "M5 5h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM8 3v4M16 3v4M4 10h16",
    branch: "M6 3v12M6 21m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0M18 6m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0M18 9v3a3 3 0 0 1-3 3H9",
    chevron: "M9 5l7 7-7 7",
    info: "M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 11v5M12 8h.01",
    palette: "M12 3a9 9 0 1 0 0 18h1.5a2 2 0 0 0 1.5-3.3 2 2 0 0 1 1.5-3.3H19a3 3 0 0 0 3-3A9 9 0 0 0 12 3zM7.5 11h.01M10.5 7.5h.01M15 7.5h.01",
    check: "M4 12.5l5 5L20 6.5",
    columns: "M4 4h16v16H4zM12 4v16",
    link: "M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1",
    share: "M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M12 15V3M8 7l4-4 4 4",
    mail: "M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM3 7l9 6 9-6",
    phone: "M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A17 17 0 0 1 3 5a2 2 0 0 1 2-2z",
    filter: "M3 5h18l-7 8v6l-4 2v-8z",
    print: "M6 9V3h12v6M6 17H4a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-2M6 14h12v7H6z",
    sort: "M7 4v16M3 16l4 4 4-4M17 20V4M13 8l4-4 4 4",
    landmark: "M3 9l9-5 9 5zM6 11v6M10 11v6M14 11v6M18 11v6M4 17h16M3 20h18",
    scale: "M12 3v18M7 21h10M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2M2 16l3-8 3 8c-.9.7-1.9 1-3 1s-2.1-.3-3-1zM16 16l3-8 3 8c-.9.7-1.9 1-3 1s-2.1-.3-3-1z",
  };

  function iconSprite() {
    var symbols = Object.keys(ICONS)
      .map(function (name) {
        return (
          '<symbol id="i-' + name + '" viewBox="0 0 24 24">' +
          '<path d="' + ICONS[name] + '"/></symbol>'
        );
      })
      .join("");
    return (
      '<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">' +
      symbols + "</svg>"
    );
  }

  /** Markup for one icon. Decorative by default - the label lives in the
   *  surrounding control, so a screen reader is not told "flag" twice. */
  function icon(name, className) {
    if (!ICONS[name]) return "";
    return (
      '<svg class="icon' + (className ? " " + className : "") +
      '" aria-hidden="true" focusable="false"><use href="#i-' + name + '"/></svg>'
    );
  }

  /* =============================================================== theme */

  var THEMES = ["system", "dark", "amoled", "light"];
  var THEME_KEY = "kycTheme";
  var themeListeners = [];

  function prefersLight() {
    return (
      global.matchMedia && global.matchMedia("(prefers-color-scheme: light)").matches
    );
  }

  function resolveTheme(name) {
    if (name !== "system") return name;
    return prefersLight() ? "light" : "dark";
  }

  function currentTheme() {
    try {
      var saved = localStorage.getItem(THEME_KEY);
      if (THEMES.indexOf(saved) !== -1) return saved;
    } catch (e) {
      /* private mode, or storage disabled */
    }
    return "system";
  }

  function setTheme(name) {
    if (THEMES.indexOf(name) === -1) name = "system";
    // Guard: this file loads in <head>; never assume the element exists.
    if (doc.documentElement) {
      doc.documentElement.setAttribute("data-theme", resolveTheme(name));
      doc.documentElement.setAttribute("data-theme-pref", name);
    }
    try {
      localStorage.setItem(THEME_KEY, name);
    } catch (e) {
      /* the attribute above still applies */
    }
    syncThemeColor();
    syncColorScheme(resolveTheme(name));
    themeListeners.forEach(function (fn) {
      try { fn(resolveTheme(name), name); } catch (e) { /* keep going */ }
    });
  }

  /* The page declares only the scheme it is showing, with "only": the
   * standard's way to say "do not repaint this". Chromium's auto dark mode
   * honours it, and so does Samsung Internet in its "Use website dark theme"
   * mode. Its default dark mode ignores every declaration, which is why the
   * maps' words are page text that survives a repaint (rule 46). */
  function syncColorScheme(theme) {
    var meta = doc.querySelector('meta[name="color-scheme"]');
    if (meta) meta.setAttribute("content", theme === "light" ? "only light" : "only dark");
  }

  /* A phone tints its toolbar from <meta name="theme-color">. The pages
   * carry a pair keyed to the OS's preference, so a reader who chose light on
   * a dark phone got a near-black bar over a white page, and AMOLED black got
   * a grey one. Once a theme applies, both say the page's own colour. */
  function syncThemeColor() {
    var metas = doc.querySelectorAll('meta[name="theme-color"]');
    if (!metas.length || !global.getComputedStyle || !doc.documentElement) return;
    var colour = global.getComputedStyle(doc.documentElement)
      .getPropertyValue("--surface-0").trim();
    if (!colour) return;
    Array.prototype.forEach.call(metas, function (meta) {
      meta.removeAttribute("media");
      meta.setAttribute("content", colour);
    });
  }

  function onThemeChange(fn) {
    themeListeners.push(fn);
  }

  function initTheme() {
    setTheme(currentTheme());
    // Follow the OS while the preference is "system".
    if (global.matchMedia) {
      var query = global.matchMedia("(prefers-color-scheme: light)");
      var react = function () {
        if (currentTheme() === "system") setTheme("system");
      };
      if (query.addEventListener) query.addEventListener("change", react);
      else if (query.addListener) query.addListener(react);
    }
  }

  /* =========================================================== escaping */

  var ESCAPES = {
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  };

  /** Escape a value for interpolation into HTML.
   *
   *  Everything the site renders comes from CSV rows describing real, named
   *  people. Nothing from the data reaches innerHTML without passing through
   *  here or through renderField. */
  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return ESCAPES[ch];
    });
  }

  /** Escape for a double-quoted HTML attribute. Same rules; named for the
   *  call site so the intent is legible. */
  var escapeAttr = escapeHtml;

  /* ============================================================ portraits */

  var SILHOUETTE =
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' " +
    "fill='%23888888'%3E%3Ccircle cx='50' cy='36' r='19'/%3E" +
    "%3Cpath d='M18,86 C18,60 82,60 82,86 Z'/%3E%3C/svg%3E";

  /* ============================================================== people */

  /* One build's profiles, races and figures come in several files (rule
   * 94): data/people/meta.js, the build's figures (kycBuildMeta), on every
   * page with people; data/people/index.js, everyone's card and search
   * fields and every race, on the grid and the map; data/people/<st>.js, a
   * state's full records and its races, on its own state's pages and
   * wherever one of its people is opened (KYC.loadPeople). One 6.7 MB
   * profiles.js held all of it, and every page loaded all of it.
   *
   * Each people file assigns window.kycPeopleFile; this takes each in as it
   * is assigned, into the two arrays every view reads - window.legislatorsData
   * and window.kycRaces, through KYC.people() and KYC.races() - so they keep
   * their shape whichever files a page holds. A record is filled in, never
   * replaced: the index's record of a person is the same object once their
   * state's file arrives, with the rest of its fields added. A file from
   * another build than the page's figures is refused, and the page says so
   * (rule 34: a page reads one build). Each file taken in fires "kyc:people"
   * on the document. */
  var fullStates = {};     // code -> true once the state's own file is in
  var indexIn = false;     // whether the index of everyone is in
  var partial = {};        // id -> true for a record the index holds in part
  var refusedPeople = [];  // the files refused, as the index or a state code
  var lastPeopleFile;

  function takePeople(file) {
    lastPeopleFile = file;
    if (!file || !file.people || !file.races) return;
    var what = file.index ? "index" : String(file.state || "");
    var build = (global.kycBuildMeta || {}).signature;
    if (build && file.build !== build) {
      if (refusedPeople.indexOf(what) === -1) refusedPeople.push(what);
      return;
    }
    if (file.index ? indexIn : fullStates[what]) return;
    var list = global.legislatorsData || (global.legislatorsData = []);
    var raceList = global.kycRaces || (global.kycRaces = []);
    var held = {};
    list.forEach(function (p) { held[p.id] = p; });
    file.people.forEach(function (p) {
      var known = held[p.id];
      if (!known) {
        list.push(p);
        held[p.id] = p;
        if (file.index) partial[p.id] = true;
        return;
      }
      if (!file.index) {
        Object.keys(p).forEach(function (key) { if (!(key in known)) known[key] = p[key]; });
        delete partial[p.id];
      }
    });
    var heldRace = {};
    raceList.forEach(function (r) { heldRace[r.id] = true; });
    file.races.forEach(function (r) { if (!heldRace[r.id]) raceList.push(r); });
    if (file.index) indexIn = true;
    else fullStates[what] = true;
    // What was built from the arrays is built again from them.
    profileIndex = null;
    racePositions = null;
    if (doc && typeof global.CustomEvent === "function") {
      doc.dispatchEvent(new global.CustomEvent("kyc:people", { detail: { file: what } }));
    }
  }

  try {
    Object.defineProperty(global, "kycPeopleFile", {
      configurable: true,
      get: function () { return lastPeopleFile; },
      set: takePeople,
    });
  } catch (e) { /* a page without the property cannot hold people files */ }

  /** Every profile the page holds: the array every view reads. */
  function people() {
    return global.legislatorsData || (global.legislatorsData = []);
  }

  /** Every race the page holds. */
  function races() {
    return global.kycRaces || (global.kycRaces = []);
  }

  /** Whether *item* is held whole, every field the dialog shows: false for
   *  a card the index holds until its state's file is in. */
  function isFull(item) {
    return !!item && !partial[item.id];
  }

  /** Whether every record of *code* the page holds is whole. */
  function peopleFull(code) {
    return !!fullStates[String(code || "").toUpperCase()] || !indexIn;
  }

  /** Whether the page holds *code*'s people at all: everyone's cards (the
   *  index) or the state's own file. */
  function peopleHeld(code) {
    return indexIn || !!fullStates[String(code || "").toUpperCase()];
  }

  /** Why the page holds fewer people than it should, in a sentence for the
   *  page, or "": a file from another build than the page's own. */
  function peopleProblem() {
    return refusedPeople.length
      ? "This site's data has been updated since this page was opened. Reload the page " +
        "to see the current version."
      : "";
  }

  var profileIndex = null;

  /** Profiles keyed by id. Built once; the grid, the map and every deep link
   *  all resolve through it instead of scanning 594 records per lookup. */
  function byId(id) {
    if (profileIndex === null) {
      profileIndex = new Map();
      var data = people();
      data.forEach(function (item) {
        profileIndex.set(item.id, item);
      });
      // A person registered with the FEC under several ids has one profile;
      // the others are kept as otherFecIds (derived in the pipeline). A link
      // shared under one of them still opens that person, never a stranger:
      // a real profile id always wins over an alias. A curated profile
      // answers to its own filing's id too: Mike Collins's filing was
      // FEC_S6GA00390 until his curated row named it, and links and market
      // labels saved under that id still open him.
      data.forEach(function (item) {
        var own = item.fecCandidateId && item.id !== "FEC_" + item.fecCandidateId
          ? [item.fecCandidateId] : [];
        (item.otherFecIds || []).concat(own).forEach(function (other) {
          var alias = "FEC_" + other;
          if (!profileIndex.has(alias)) profileIndex.set(alias, item);
        });
        // A curated candidate since seated answers to their curated id too.
        (item.otherIds || []).forEach(function (alias) {
          if (!profileIndex.has(alias)) profileIndex.set(alias, item);
        });
      });
    }
    return profileIndex.get(id);
  }

  /** Sitting in Congress now: a member's profile, and not a former member's.
   *  A record incumbent who has left keeps the member shape so their 2026
   *  race still finds them (`formerMember`, from the pipeline); every view
   *  that answers "who represents me" asks this, never `!isCandidate` alone
   *  (rule 27). The pipeline's own test is kyc/record.py `seated`. */
  function seated(item) {
    return !!item && !item.isCandidate && !item.formerMember;
  }

  /** "Left office 2026-12-08" for a former member, else "". */
  function formerText(item) {
    var former = item && item.formerMember;
    return former ? "Left office " + former.left : "";
  }

  /** True for a sitting member whose 2026 filing is for a different seat -
   *  the other chamber, or a redrawn district. */
  function runsElsewhere(item) {
    return !!item && !item.isCandidate && !!item.contestRaceId &&
      item.contestRaceId !== item.raceId;
  }

  /** The primary result that describes what this person is doing in 2026.
   *
   *  For a member running for another seat, the record's own raceStatus can
   *  be about the seat they hold: Ashley Hinson is "unlisted" in IA-2
   *  because she is the Senate nominee in Iowa, and the page called that
   *  "not seeking re-election". The result for the race they are actually
   *  in lives on their filing's profile (alsoRunningId), and is used only
   *  when that profile is in the same race. Anything else is "", never the
   *  held seat's absence. The pipeline derives both statuses; this only
   *  chooses which of them the reader is shown. */
  function contestStatus(item) {
    if (!item) return "";
    if (!runsElsewhere(item) || item.raceStatusRace === item.contestRaceId) {
      return item.raceStatus || "";
    }
    var filing = item.alsoRunningId && byId(item.alsoRunningId);
    if (filing && filing.raceId === item.contestRaceId) return filing.raceStatus || "";
    return "";
  }

  /** The November ballot line of a nominee whose line is not their party's
   *  ("Speak The Truth"), read from the same record contestStatus reads, or
   *  "". The pipeline decides when there is one; this never derives it. */
  function ballotLine(item) {
    if (!item || !NOVEMBER[contestStatus(item)]) return "";
    if (!runsElsewhere(item) || item.raceStatusRace === item.contestRaceId) {
      return String(item.ballotLine || "");
    }
    var filing = item.alsoRunningId && byId(item.alsoRunningId);
    return String((filing && filing.raceId === item.contestRaceId && filing.ballotLine) || "");
  }

  /** " – Speak The Truth line", already escaped, to follow a nominee's
   *  status; "" for everyone else. */
  function ballotLineSuffix(item) {
    var line = ballotLine(item);
    return line ? " – " + escapeHtml(line) + " line" : "";
  }

  /* ======================================================= race statuses */

  /* Where someone stands in their 2026 race, in one table for every view
   * that shows it (rule 12): four copies of it, one per view, had to learn
   * each new status separately. Each status has its badge class; its words
   * on a card, in the profile ("long"), in a race's list of people ("mate")
   * and in a map row ("short"); its hover text; and where a race lists it.
   * `member` holds what reads differently for a sitting member on the seat
   * they hold: no primary line is a retirement, a primary win a
   * renomination, a November win a re-election. `off` takes someone out of
   * the race, behind a toggle. Someone who lost in November was on the
   * ballot, and stays in view beside the person who beat them. */
  // Never "the state's": a territory's, or D.C.'s, is not (rule 75).
  var SOURCE = " Source: Wikipedia's election results page.";
  /* A sitting member leaving the seat they hold, in the same words whether
   * the results list them as withdrawn or do not list them: only the title,
   * which cites its source, differs. */
  function MEMBER_LEAVING(spec) {
    return { cls: "badge-danger", card: "Not running for re-election",
      long: "Not running for re-election in 2026", mate: "Not running for re-election",
      short: "Leaving seat", title: spec.title };
  }
  /* An appointee was never elected to the seat, so is not "re-elected" or
   * "not running for re-election": Alan Armstrong took Oklahoma's on an
   * oath not to seek it. */
  var APPOINTEE_LEAVING = { cls: "badge-danger", card: "Not running in 2026",
    long: "Not running in 2026", mate: "Not running in 2026", short: "Leaving seat",
    title: "Appointed to the seat; not named in the primary results or on the November " +
      "ballot for it, so not seeking election to it." };
  var RACE_STATUS = {
    nominee: { cls: "badge-money", rank: 0,
      card: "On the November ballot", long: "On the November ballot", mate: "On the ballot",
      short: "Nominee",
      title: "Won the primary; will appear on the general election ballot.",
      member: { card: "Renominated", long: "Renominated for 2026", short: "Renominated",
        title: "Won the 2026 primary for this seat." } },
    elected: { cls: "badge-money", rank: 0,
      card: "Elected", long: "Elected in November", mate: "Elected", short: "Elected",
      title: "Won the November general election, per Wikipedia's results page.",
      member: { card: "Re-elected", long: "Re-elected in November", mate: "Re-elected",
        short: "Re-elected",
        title: "Won re-election to this seat in November, per Wikipedia's results page." } },
    runoff: { cls: "badge-warn", rank: 1,
      card: "In the runoff", long: "In the general election runoff", mate: "In the runoff",
      short: "In runoff",
      title: "No candidate won a majority in November; in the runoff between the top two, " +
        "per Wikipedia's results page." },
    advanced: { cls: "badge-warn", rank: 1,
      card: "In runoff", long: "In a primary runoff", mate: "In runoff", short: "In runoff",
      title: "Advanced to a primary runoff that has not yet been decided." },
    // Louisiana's House seats: everyone qualified for the November 3 open
    // primary is on that ballot, and nobody has won anything yet.
    qualified: { cls: "badge-money", rank: 0,
      card: "On the Nov 3 ballot", long: "On the November 3 open-primary ballot",
      mate: "On the ballot", short: "On ballot",
      title: "Qualified for the November 3 open primary, per the Secretary of State's " +
        "list of qualified candidates.",
      source: " Source: the Secretary of State's Candidate Inquiry." },
    defeated: { cls: "badge-danger", rank: 3,
      card: "Lost in November", long: "Lost the November election", mate: "Lost in November",
      short: "Lost",
      title: "Lost the November general election, per Wikipedia's results page.",
      member: { card: "Lost re-election", long: "Lost re-election in November",
        mate: "Lost re-election", short: "Lost re-election",
        title: "Lost re-election to this seat in November, per Wikipedia's results page." } },
    eliminated: { cls: "badge-danger", rank: 4, off: true,
      card: "Lost primary", long: "Lost the 2026 primary", mate: "Lost primary",
      short: "Lost primary",
      title: "Did not win the primary, per Wikipedia's results page." },
    // A sitting member who withdrew from their own seat's race is not
    // running for re-election: "Withdrew" on Thom Tillis and Tommy
    // Tuberville read as quitting a campaign mid-way (TRUST-18).
    withdrawn: { cls: "badge-neutral", rank: 5, off: true,
      card: "Withdrew", long: "Withdrew from the 2026 race", mate: "Withdrew", short: "Withdrew",
      title: "Withdrew from the race, per Wikipedia's results page.",
      member: MEMBER_LEAVING({
        title: "Not seeking re-election to this seat: Wikipedia's results page lists them as " +
          "withdrawn from its race." }) },
    unlisted: { cls: "badge-neutral", rank: 6, off: true,
      card: "Not on primary ballot", long: "Not on the 2026 primary ballot", mate: "Not on ballot",
      short: "Not on ballot",
      title: "Filed with the FEC but was not listed in the primary results.",
      // About this seat only. "Not on the ballot" was false for a member on
      // another office's ballot: Byron Donalds, Florida's Republican nominee
      // for governor, read it on the Florida page. The same words as a
      // member who withdrew: which way the results page happened to list a
      // retirement split the Senate view's retiring senators between "Not
      // running for re-election" and "Not running for this seat", and the
      // race-mate lists between that and "Not on ballot" (RACES-10).
      member: MEMBER_LEAVING({
        title: "Not named in the primary results or on the November ballot for this seat; " +
          "not seeking re-election to it." }) },
  };

  /* Not named on the results page, which does name someone like them who
   * lost or withdrew: off the November ballot whichever reading is right,
   * and that is all the badge says. */
  var UNCONFIRMED = { cls: "badge-neutral", rank: 6, off: true,
    card: "Not on the November ballot", long: "Not on the November ballot",
    mate: "Not on ballot", short: "Not on ballot",
    title: "Wikipedia's results page puts nobody of this name on the November ballot; a similar " +
      "name they list lost or withdrew." };

  /* After Election Day, a nominee the results have not marked either way.
   * The results are read twice a week, so this is a claim about when this
   * site last looked, and says so (rule 19), not one about the count. */
  var AWAITING = { cls: "badge-neutral", rank: 0,
    card: "Awaiting result", long: "On the November ballot: awaiting result",
    mate: "Awaiting result", short: "Awaiting result" };

  var MINOR_NOMINEE = { cls: "badge-money", rank: 0,
    card: "On the November ballot", long: "On the November ballot", mate: "On the ballot",
    short: "On ballot",
    title: "On the general election ballot, per Wikipedia's results page. Independent and " +
      "minor-party candidates get there by petition or by their party's nomination, not " +
      "necessarily by a primary." };

  var NOVEMBER = { nominee: true, elected: true, defeated: true, runoff: true, qualified: true };

  /* A status read from a state's list of qualified candidates (Louisiana's
   * House seats before their count) is the Secretary of State's word, not a
   * results page's, and says so. */
  var LISTED_SOURCE = " Source: the Secretary of State's Candidate Inquiry.";
  var LISTED = {
    unlisted: { cls: "badge-neutral", rank: 6, off: true,
      card: "Not on the Nov 3 ballot", long: "Not on the November 3 open-primary ballot",
      mate: "Not on ballot", short: "Not on ballot",
      title: "Filed with the FEC but not on the Secretary of State's list of candidates " +
        "qualified for the November 3 open primary.",
      member: MEMBER_LEAVING({
        title: "Not on the Secretary of State's list of candidates qualified for this seat; " +
          "not seeking re-election to it." }) },
    withdrawn: { cls: "badge-neutral", rank: 5, off: true,
      card: "Withdrew", long: "Withdrew from the 2026 race", mate: "Withdrew", short: "Withdrew",
      title: "Withdrew, per the Secretary of State's list of qualified candidates.",
      member: MEMBER_LEAVING({
        title: "Not seeking re-election to this seat: the Secretary of State's list of " +
          "qualified candidates shows them as withdrawn." }) },
  };
  /* A status a state's certified list of November candidates set (rule 77):
   * the list's word, credited to the office that published it (the source
   * line names it - a territory's is never "the state's"). Only what the
   * list says differently from a results page is here. A member the list
   * puts on the ballot is on it, never "renominated": a list is not a
   * primary, and American Samoa holds none. */
  var CERTIFIED = {
    nominee: { title: "On the certified list of candidates for the November 3 ballot.",
      member: { card: "On the November ballot", long: "On the November ballot",
        short: "On ballot", mate: "On the ballot",
        title: "On the certified list of candidates for the November 3 ballot." } },
    unlisted: { cls: "badge-neutral", rank: 6, off: true,
      card: "Not on the November ballot", long: "Not on the November ballot",
      mate: "Not on ballot", short: "Not on ballot",
      title: "Filed with the FEC but not on the certified list of candidates for the " +
        "November 3 ballot.",
      // The one wording a leaving member has, whichever source says so
      // (RACES-10).
      member: MEMBER_LEAVING({
        title: "Not on the certified list of candidates for this seat; not seeking " +
          "re-election to it." }) },
    withdrawn: { title: "Withdrew, per the certified list of candidates." },
    eliminated: { title: "Lost the primary, per the certified list of candidates." },
  };
  var OFF_BALLOT = { eliminated: true, withdrawn: true, unlisted: true };

  /** How to show *status* in *form* ("card", "long", "mate" or "short"):
   *  `{cls, label, title, rank, off}`, or null for no status. Options:
   *  `own` - a sitting member, about the seat they hold; `unconfirmed` - the
   *  record's raceStatusUnconfirmed; `appointed` - an appointee, who is
   *  never "not running for re-election"; `now` - the clock, for tests. */
  /* Through to November from an all-party primary - California's and
   * Washington's top two, Alaska's top four: nobody won a party's
   * nomination, and two of one party can both go through. The pipeline
   * says which (results.ALL_PARTY_PRIMARIES, `allPartyPrimary`). */
  function allParty(kind) {
    var top = kind === "top-four" ? "top four" : "top two";
    var title = "Finished in the " + top + " of the all-party primary, which sends the leaders " +
      "to November whatever their party; on the November ballot.";
    // One outcome, one label: the member read "Advanced to November" and a
    // challenger through the same primary "On the November ballot", which
    // the key defined as winning a primary nobody there wins (GRID-19,
    // rule 74).
    var words = { card: "Advanced to November", long: "Advanced to the November ballot",
      short: "Advanced", mate: "Advanced", title: title };
    return { cls: "badge-money", rank: 0, card: words.card, long: words.long, mate: words.mate,
      short: words.short, title: title, member: words };
  }

  function raceStatus(status, form, opts) {
    var spec = RACE_STATUS[status];
    if (!spec) return null;
    opts = opts || {};
    if (status === "nominee" && opts.allParty) spec = allParty(opts.allParty);
    var listed = opts.source === "qualified";
    if (listed && LISTED[status]) spec = LISTED[status];
    var certified = opts.source === "certified" && CERTIFIED[status];
    if (certified) {
      // The list's own words where they differ; the rest as for any result.
      var merged = {};
      Object.keys(spec).forEach(function (k) { merged[k] = spec[k]; });
      Object.keys(certified).forEach(function (k) { merged[k] = certified[k]; });
      if (!certified.member && spec.member) {
        merged.member = { title: certified.title };
        Object.keys(spec.member).forEach(function (k) {
          if (k !== "title") merged.member[k] = spec.member[k];
        });
      }
      spec = merged;
    }
    if (status === "unlisted" && opts.unconfirmed && !certified) spec = UNCONFIRMED;
    var own = (opts.own && spec.member) || {};
    if (opts.own && opts.appointed && spec.member && spec.off) own = APPOINTEE_LEAVING;
    var title = own.title || spec.title;
    var source = spec.source || (listed ? LISTED_SOURCE : certified
      ? " Source: " + (opts.sourceName || "the certified list of candidates") + "."
      : SOURCE);
    // An independent or a minor party's nominee reaches the ballot by
    // petition or by their party's nomination, mostly without a primary:
    // "Won the primary" was false for Dan Osborn and 57 others (PROFILES-17).
    if (status === "nominee" && spec === RACE_STATUS.nominee && opts.minor && !opts.own) {
      spec = MINOR_NOMINEE;
      title = spec.title;
    }
    if ((status === "nominee" || status === "qualified") &&
        electionStatus(undefined, opts.now).phase === "post-election") {
      var asOf = (meta().election || {}).resultsAsOf;
      spec = AWAITING;
      own = {};
      title = "On the November ballot. The results this site last read" +
        (asOf ? ", on " + asOf + "," : "") + " had not marked a winner.";
    }
    return {
      cls: own.cls || spec.cls,
      label: own[form] || spec[form],
      title: form === "long" ? title + source : title,
      rank: spec.rank,
      off: !!spec.off,
    };
  }

  /** The same for a person: their contest's status, as a member when the
   *  race is for the seat they hold. A member seated since Election Day in
   *  a seat they did not hold (`raceRole`) was elected, not re-elected; an
   *  appointee who held the seat was never elected or nominated to it, so
   *  wins and losses read as anyone's - only "not running in 2026" is
   *  theirs. */
  function raceStatusOf(item, form, opts) {
    if (!item) return null;
    opts = opts || {};
    // The source of the record contestStatus read: a member's own seat, or
    // their filing's race when they run elsewhere.
    var record = !runsElsewhere(item) || item.raceStatusRace === item.contestRaceId ? item
      : byId(item.alsoRunningId) || {};
    var status = contestStatus(item);
    return raceStatus(status, form, {
      own: !item.isCandidate && !item.contestLabel && !item.raceRole &&
        !(item.appointed && status !== "unlisted"),
      unconfirmed: !!item.raceStatusUnconfirmed,
      appointed: !!item.appointed,
      source: record.raceStatusSource,
      sourceName: record.raceStatusSourceName,
      allParty: record.allPartyPrimary,
      minor: partyKey(item) === "i",
      now: opts.now,
    });
  }

  /* A filer the published results do not settle: they name someone who
   * may be this person under another spelling (maybeNamed), or they do not
   * name them at all, after the primary (ballotUnknown). Neither is "the
   * primary has not been held", and neither is on the ballot as far as
   * this site can say. The dialog showed no status for them at all while
   * their card said "Ballot status not known", and the map counted them as
   * challengers (PROFILES-06, RACES-04). */
  function unsettled(item) {
    if (!item || !item.isCandidate || item.raceStatus) return null;
    if (item.maybeNamed && item.maybeNamed.length) {
      return { cls: "badge-neutral", rank: 2, off: false, unknown: true,
        card: "Result not matched", long: "Result not matched", mate: "Result not matched",
        short: "Not matched",
        title: "Wikipedia's results page names " + item.maybeNamed.join(" and ") + ", who may be " +
          "this person under another spelling. Not confirmed here, so the race counts them " +
          "once, under that name." };
    }
    var unprinted = item.unprinted;
    if (unprinted && unprinted.kind) {
      // Named on a certified list but not printed (rule 77): Texas's
      // declared write-ins for the Senate read "the published results do
      // not name them", which the state's own list did.
      var source = unprinted.source ? " Source: " + unprinted.source + "." : "";
      if (unprinted.kind === "unopposed") {
        return { cls: "badge-neutral", rank: 2, off: false, unknown: true,
          card: "Unopposed, not printed", long: "Unopposed in November, not printed",
          mate: "Unopposed", short: "Unopposed",
          title: "Unopposed in November. Florida does not print an uncontested race on the " +
            "ballot." + source };
      }
      return { cls: "badge-neutral", rank: 2, off: false, unknown: true,
        card: "Write-in candidate", long: "Write-in candidate", mate: "Write-in",
        short: "Write-in",
        title: "On the certified list of candidates as a write-in: not printed on the " +
          "November ballot, though a voter can write their name in." + source };
    }
    var noPrimary = !item.ballotUnknown && noPrimaryRace(item.raceId);
    if (item.ballotUnknown || noPrimary) {
      return { cls: "badge-neutral", rank: 2, off: false, unknown: true,
        card: "Ballot status not known", long: "Ballot status not known",
        mate: "Ballot status not known", short: "Status not known",
        title: noPrimary
          ? "Filed with the FEC. The election calendar lists no primary for this seat, and " +
            "this site reads no list of who is on its November ballot, so whether they are " +
            "on it is not known here."
          : "Filed with the FEC. Wikipedia's results page for this race does not name them, so " +
            "whether they are on the November ballot is not known here." };
    }
    return null;
  }

  /* A race with no primary in the calendar and no results read for it: the
   * Northern Mariana Islands' delegate is elected in November with no
   * primary, and its filer's card said "the primary has not been held
   * yet" over a dialog with no status (PROFILES-06). */
  function noPrimaryRace(raceId) {
    var race = null;
    races().some(function (r) {
      if (r.id === raceId) { race = r; return true; }
      return false;
    });
    // null, not absent: a build without the calendar says nothing either way.
    return !!race && race.primaryDate === null && !race.results;
  }

  /** Where *item* stands in their 2026 race, in *form*, for every view
   *  (rule 63's one table): KYC.raceStatusOf, or a filer the results do not
   *  settle, or null. `unknown` marks the second, which no count of who is
   *  on the ballot includes. */
  function standing(item, form, opts) {
    var spec = raceStatusOf(item, form, opts);
    if (spec) return spec;
    var open = unsettled(item);
    if (!open) return null;
    return { cls: open.cls, label: open[form] || open.card, title: open.title,
             rank: open.rank, off: false, unknown: true };
  }

  /** Every status word a card can show for where someone stands in their
   *  race, once each, from the tables above - so the key on the grid says
   *  what the badges say, and a new status is in it the day it is added
   *  (GRID-19: about seventeen badges were explained only by hover titles,
   *  which a phone never shows). `[{cls, label, title}]`, in rank order.
   *  The title is the badge's own, but where a status is read from more
   *  than one kind of source the badge on a card names its source. */
  var NOMINEE_KEY = "Will appear on the November general election ballot: a party's nominee, " +
    "or an independent or minor-party candidate there by petition or their party's nomination.";

  function raceStatusLegend() {
    var seen = {};
    var out = [];
    var add = function (spec, title) {
      if (!spec || !spec.card || seen[spec.card]) return;
      seen[spec.card] = true;
      out.push({ cls: spec.cls, label: spec.card, title: title || spec.title || "",
                 rank: spec.rank === undefined ? 9 : spec.rank });
    };
    var member = function (spec) {
      var m = spec.member;
      if (m) add({ cls: m.cls || spec.cls, card: m.card, rank: spec.rank }, m.title);
    };
    Object.keys(RACE_STATUS).forEach(function (status) {
      var spec = RACE_STATUS[status];
      // A badge's own title says how its holder got there; the key's entry
      // covers everyone who carries the words. "Won the primary" was false
      // for an independent on the ballot by petition (rule 74).
      add(spec, status === "nominee" ? NOMINEE_KEY : undefined);
      member(spec);
    });
    add(allParty("top-two"), "Finished in the top two (California, Washington) or the top four " +
      "(Alaska) of an all-party primary, which sends the leaders to November whatever their " +
      "party; on the November ballot.");
    add(LISTED.unlisted);
    add(UNCONFIRMED);
    add(APPOINTEE_LEAVING);
    add(AWAITING, "After Election Day: on the November ballot, and the results this site last " +
      "read had not marked a winner.");
    [{ maybeNamed: ["a similar name"] }, { unprinted: { kind: "write-in" } },
     { unprinted: { kind: "unopposed" } }, { ballotUnknown: true }].forEach(function (fake) {
      fake.isCandidate = true;
      var spec = unsettled(fake);
      if (spec) add(spec);
    });
    return out.sort(function (a, b) { return a.rank - b.rank; });
  }

  /** The filing profile of a member's run for another seat, when it is the
   *  race they contest (alsoRunningId), else null. Its money is that
   *  campaign's: shown beside the member's, labelled, never as theirs
   *  (rule 68: a member carries only their own chamber's FEC ids). */
  function otherCampaign(item) {
    if (!runsElsewhere(item) || !item.alsoRunningId) return null;
    var filing = byId(item.alsoRunningId);
    return filing && filing.id !== item.id && filing.raceId === item.contestRaceId ? filing : null;
  }

  /** A sitting member's run for a seat other than the one they hold, as
   *  one badge's words for every view: `{cls, label, title, past}`, or
   *  null. Running again under a new district number is re-election, not
   *  leaving (rule 74): "Running in CA-40 (redrawn)". A run that ended in
   *  a loss or a withdrawal is in the past tense: "Ran for Senate IL"
   *  read "Running for" beside "Lost primary" into October (GRID-15). */
  function contestLine(item) {
    if (!item || item.isCandidate || !item.contestLabel) return null;
    var seat = item.contestLabel.replace(/ • /, " ");
    var status = contestStatus(item);
    var past = OFF_BALLOT[status] || status === "defeated";
    var end = String(item.term_start || "").split(" - ")[1] || "";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(end)) end = "";
    if (item.renumbered) {
      var number = seat.replace(/^House /, "");
      return past
        ? { cls: "badge-neutral", past: true, renumbered: true,
            label: "Ran in " + number + " (redrawn)",
            title: "Ran for re-election under the state's new district map, in " +
              item.contestLabel + ", and " +
              (status === "defeated" ? "lost in November" : "is not on its November ballot") +
              "; holds " + item.officeLabel + (end ? " until " + end : "") + "." }
        : { cls: "badge-neutral", past: false, renumbered: true,
            label: "Running in " + number + " (redrawn)",
            title: "Running for re-election under the state's new district map, in " +
              item.contestLabel + "; holds " + item.officeLabel + " until the new term begins." };
    }
    if (past) {
      return { cls: "badge-neutral", past: true, label: "Ran for " + seat,
        title: "Ran for " + item.contestLabel + " in 2026 and " +
          (status === "defeated" ? "lost in November" : "is not on its November ballot") +
          "; not seeking re-election to " + item.officeLabel +
          (end ? ", whose term ends " + end : "") + "." };
    }
    return { cls: "badge-warn", past: false, label: "Running for " + seat,
      title: "Running for " + item.contestLabel + " in 2026; not seeking re-election to " +
        item.officeLabel + "." };
  }

  /* Each race lists its people in one order, decided by the pipeline
   * (races.order_people): the seat's holder first, then by surname. A view
   * that lists people from several races - the map's state panel - keeps
   * that order within each race. */
  var racePositions = null;
  function racePosition(item) {
    if (racePositions === null) {
      racePositions = {};
      races().forEach(function (race) {
        race.incumbentIds.concat(race.candidateIds).forEach(function (id, i) {
          if (racePositions[race.id + " " + id] === undefined) racePositions[race.id + " " + id] = i;
        });
      });
    }
    var rid = item && (item.isCandidate ? item.raceId : (item.contestRaceId || item.raceId));
    var at = racePositions[rid + " " + (item && item.id)];
    return at === undefined ? 1e6 : at;
  }

  /** Where a member leaving their seat is going, from the curated, sourced
   *  `otherOffice` (overrides.OTHER_OFFICE_NOMINEES): `{text, title, past}`,
   *  or null. Byron Donalds read only "Not running for this seat"
   *  (FRESHNESS-09). From the day after Election Day it is in the past
   *  tense, by the reader's clock as every result is (rule 63): this site
   *  does not read that race's result, and "Republican nominee for
   *  Governor of Alabama" two months after the count would read as though
   *  nothing had happened. *now* is for tests. */
  function otherOffice(item, now) {
    var other = item && !item.isCandidate && item.otherOffice;
    if (!other || !other.text) return null;
    var past = electionStatus(undefined, now).phase === "post-election";
    var read = " Source: the election's Wikipedia page, which marks the primary's winner " +
      "(read " + other.checked + ").";
    return past
      ? { past: true, text: "Was the " + other.text,
          title: "Was on the November 3 ballot for an office this site does not cover; this " +
            "site does not show that race's result." + read }
      : { past: false, text: other.text,
          title: "On the November 3 ballot for an office this site does not cover." + read };
  }

  /** The same as a badge, after *sep*; else "". */
  function otherOfficeBadge(item, sep, now) {
    var other = otherOffice(item, now);
    if (!other) return "";
    return (sep || "") + '<span class="badge ' + (other.past ? "badge-neutral" : "badge-warn") +
      ' other-office" title="' + escapeAttr(other.title) + '">' + escapeHtml(other.text) +
      "</span>";
  }

  /** The sentence that says how a race's people are ordered. */
  var RACE_ORDER = "The seat's holder first, then everyone else by surname.";
  var RACE_ORDER_PLAIN = "Listed by surname.";

  /** That sentence for *list*, the people a view shows of *race* in the
   *  race's order: the holder clause only when the list opens with one of
   *  the race's incumbents. Under the Senate view's "Running for this seat",
   *  whose holder has a column of their own, and in a holder's own dialog,
   *  it said the first person listed held the seat: Barry Moore, under
   *  Alabama's. */
  function raceOrderNote(list, race) {
    var first = list && list[0];
    var held = !!first && !!race && (race.incumbentIds || []).indexOf(first.id) !== -1;
    return held ? RACE_ORDER : RACE_ORDER_PLAIN;
  }

  /** Who says who is on a race's ballot, for a sentence: "per the published
   *  results", or the Secretary of State's qualified list where that is the
   *  ballot (Louisiana's House seats before their count). */
  function ballotSource(race) {
    var res = (race && race.results) || {};
    if (res.fromQualifiedList) return "per the Secretary of State's list of qualified candidates";
    // A state's certified November ballot (rule 77), named by its office;
    // a party's list of its own nominees only adds to the results.
    if (res.certifiedBy) {
      return res.certifiedComplete ? "per the " + res.certifiedBy
        : "per Wikipedia's results page and the " + res.certifiedBy;
    }
    return "per Wikipedia's results page";
  }

  /** The link a race's head carries to the page its statuses were read from
   *  (the pipeline's `results.sourceUrl`), so a reader can check a "Lost
   *  the primary" against it: "Results: Wikipedia, read Oct. 17, 2026", or
   *  the Secretary of State's list. "" when the race names no page. */
  function resultsSourceHtml(race) {
    var r = race && race.results;
    if (!r || !/^https:\/\//.test(r.sourceUrl || "")) return "";
    var asOf = (meta().election || {}).resultsAsOf;
    var listed = !!r.fromQualifiedList;
    var label = listed ? "Ballot: the Secretary of State's list"
      : "Results: Wikipedia" + (asOf ? ", read " + dateWords(asOf) : "");
    var title = listed
      ? "The Secretary of State's list of candidates qualified for this seat"
      : "The state's election results page on Wikipedia, which this site reads for who " +
        "won, lost or withdrew.";
    // The caveat is page text: a title is a hover a phone never shows.
    var note = listed ? "" : '<span class="race-source-note"> (not the state\u2019s certified count)</span>';
    return '<span class="race-source"><a href="' + escapeAttr(r.sourceUrl) +
      '" target="_blank" rel="noopener noreferrer" title="' + escapeAttr(title) + '">' +
      escapeHtml(label) + "</a>" + note + "</span>";
  }

  /** True when the primary settled *status* out of the race. */
  function offBallot(status) {
    return !!OFF_BALLOT[status];
  }

  /** True when *status* means on the November ballot, counted or not. */
  function onNovemberBallot(status) {
    return !!NOVEMBER[status];
  }

  /** Whether *p* is among the people still in *race* as the lookup's answer
   *  and the Your ballot page list them: once the primary has settled the
   *  race, only those on the November ballot or through to it; before it,
   *  anyone the primary has not removed. A filer the results do not settle
   *  after the primary (ballotUnknown) is not counted on the ballot (rule
   *  74), so neither view lists them as on it (PR #115 review: IL-4's card
   *  counted 5 on the ballot over 7 names). */
  function stillRunning(race, p) {
    var status = p.isCandidate ? p.raceStatus : contestStatus(p);
    if (race && race.settled) return onNovemberBallot(status) || status === "advanced";
    return !offBallot(status);
  }

  /* Portraits are resolved and checked at build time, so this runtime chain
   * is a safety net rather than the primary mechanism. */
  function handleImageFallback(img, profileId) {
    var item = byId(profileId);
    var chain = (item && item.photos) || [];
    var at = parseInt(img.getAttribute("data-photo-idx") || "0", 10);

    // The srcset only chooses a size of the photograph at chain[at], so a
    // size that fails is retried as that photograph's plain URL before the
    // chain moves on to another source.
    if (img.hasAttribute("srcset")) {
      img.removeAttribute("srcset");
      img.removeAttribute("sizes");
      if (chain[at] && chain[at] !== "placeholder") {
        img.src = chain[at];
        return;
      }
    }

    var idx = at + 1;

    while (idx < chain.length && chain[idx] === "placeholder") idx++;

    if (idx < chain.length) {
      img.setAttribute("data-photo-idx", String(idx));
      img.src = chain[idx];
    } else {
      img.onerror = null;
      img.removeAttribute("onerror");
      img.src = SILHOUETTE;
    }
  }

  /** First URL worth trying for a profile, already resolved to the
   *  silhouette when there is nothing to try: the smaller copy this site
   *  made of a heavy first portrait (rule 101), else the portrait. */
  function portraitSrc(item) {
    var first = item && item.photos && item.photos[0];
    if (!first || first === "placeholder") return SILHOUETTE;
    return photoSrc(first, item.photoCopy);
  }

  /* ---------------------------------------------------------- photo copies */

  /** The copy of *url* the build made (``photoCopy``: ``{src, of}``), when
   *  it is the copy of that very address, or null. */
  function copyOf(url, copy) {
    return copy && copy.src && url && copy.of === url ? copy : null;
  }

  /** A photograph this site hosts itself, unmodified, because its source
   *  (an election office's guide) gives it no address of its own: named
   *  ``photos/<hash>`` from the site's root (rule 101, kyc/guide_photos.py). */
  var HOSTED = /^photos\/[0-9a-f]{20}\.(?:jpg|png)$/;

  /** *url* as an <img> or a link loads it from this page: a photograph
   *  hosted here from the site's root at any depth, any other as it is. */
  function photoHref(url) {
    return HOSTED.test(String(url || "")) ? siteRoot() + url : url || "";
  }

  /** The attributes naming the original a copy falls back to: its address
   *  as this page loads it and, where that differs from the original's
   *  own (a file hosted here), the original, which the credit's note names. */
  function originalAttrs(url) {
    var href = photoHref(url);
    return ' data-photo-original="' + escapeAttr(href) + '"' +
      (href !== url ? ' data-photo-of="' + escapeAttr(url) + '"' : "");
  }

  /** Where an <img> loads a portrait from: the smaller copy this site made
   *  of a heavy original (rule 101), from the site's root at any depth, or
   *  the original's own address. One helper for every portrait (rule 12). */
  function photoSrc(url, copy) {
    var own = copyOf(url, copy);
    return own ? siteRoot() + own.src : photoHref(url);
  }

  /** The attributes of a portrait <img>, escaped: its src (``photoSrc``) and,
   *  for a copy, the original it falls back to if the copy fails to load. */
  function photoAttrs(url, copy) {
    var own = copyOf(url, copy);
    return 'src="' + escapeAttr(photoSrc(url, copy)) + '"' + (own ? originalAttrs(url) : "");
  }

  /** *credit* for a portrait the page shows as its copy: the original's
   *  credit, saying it is a smaller copy made here, and how heavy the
   *  original it links is (``photoCreditHtml``). */
  function copyCredit(credit, url, copy) {
    var own = copyOf(url, copy);
    if (!credit || !own) return credit;
    var out = {};
    Object.keys(credit).forEach(function (k) { out[k] = credit[k]; });
    out.copyOf = url;
    if (own.ofBytes) out.copyOfBytes = own.ofBytes;
    return out;
  }

  /** "12.4 MB", "820 KB": a file's weight, for a link to it. */
  function weightWords(bytes) {
    var n = Number(bytes) || 0;
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + " MB";
    return Math.max(1, Math.round(n / 1e3)) + " KB";
  }

  /** A copy that fails to load is replaced by its original, once (or by
   *  *data-photo-original*: a lighter rendition its host serves of it),
   *  and every note on the page that the copy was shown goes with it; true
   *  when it was (or another listener already did so for this *event*). */
  function retryOriginal(img, event) {
    if (event && event.kycRetried) return true;
    var original = img && img.getAttribute("data-photo-original");
    if (!original) return false;
    var of = img.getAttribute("data-photo-of") || original;
    img.removeAttribute("data-photo-original");
    img.removeAttribute("data-photo-of");
    img.removeAttribute("srcset");
    if (event) event.kycRetried = true;
    img.src = original;
    Array.prototype.forEach.call(doc.querySelectorAll(".photo-copy-note"), function (note) {
      if (note.getAttribute("data-copy-of") === of) note.remove();
    });
    return true;
  }

  /** Has the build found a portrait for *item* (rule 24: none is guessed)? */
  function hasPortrait(item) {
    return portraitSrc(item) !== SILHOUETTE;
  }

  /** "Mary Gay Scanlon" -> "MS", "Ralph Abraham Jr." -> "RA": the letters
   *  a card shows in a disc where there is no portrait. A race of six grey
   *  silhouettes was the largest thing on its cards and said nothing
   *  (audit 2026-10-17, VISUALS-16). */
  function monogram(name) {
    var words = String(name || "").replace(/\([^)]*\)|"[^"]*"/g, " ")
      .split(/[\s,]+/).filter(function (w) {
        return w && !/^(jr|sr|ii|iii|iv|v|md|phd|dr|mr|mrs|ms)\.?$/i.test(w) && /\p{L}/u.test(w);
      });
    if (!words.length) return "";
    var letter = function (w) { return (w.match(/\p{L}/u) || [""])[0].toUpperCase(); };
    return words.length === 1 ? letter(words[0]) : letter(words[0]) + letter(words[words.length - 1]);
  }

  /* Sizes of the first portrait for a srcset, when the build found several
   * of the same photograph: the browser then fetches one sharp at this
   * screen's density, rather than a 960px original for a 38px circle. */
  function portraitSrcset(item, sizes) {
    var set = item && item.photoSet;
    if (!set || !set.length || portraitSrc(item) === SILHOUETTE) return "";
    // A copy is one size, made for the largest box it is drawn in.
    if (copyOf(item.photos[0], item.photoCopy)) return "";
    return cappedSrcset(set, sizes);
  }

  /** A srcset of ``[[width, url], ...]`` (one photograph's sizes) for an
   *  image drawn *sizes* wide ("116px"), offering no size wider than a 2x
   *  screen needs (TECH-13): a 165px card on a 3x phone fetched a 494px
   *  original where the 330px file is sharp enough, and a judge's 116px
   *  portrait fetched the Commons original. The smallest size at least
   *  that wide is the last one offered. */
  function cappedSrcset(set, sizes) {
    var sorted = (set || []).slice().sort(function (a, b) { return a[0] - b[0]; });
    var px = parseFloat(sizes);
    var cap = px > 0 ? 2 * px : Infinity;
    var kept = [];
    for (var i = 0; i < sorted.length; i++) {
      kept.push(sorted[i]);
      if (sorted[i][0] >= cap) break;
    }
    return kept.map(function (entry) { return entry[1] + " " + entry[0] + "w"; }).join(", ");
  }

  /** The src - and srcset and sizes, when there are sizes - of a portrait
   *  <img>, escaped. *sizes* is the width it is drawn at, e.g. "38px". */
  function portraitAttrs(item, sizes) {
    var set = portraitSrcset(item, sizes);
    var first = item && item.photos && item.photos[0];
    var copy = copyOf(first, item && item.photoCopy);
    return 'src="' + escapeAttr(portraitSrc(item)) + '"' + (set
      ? ' srcset="' + escapeAttr(set) + '" sizes="' + escapeAttr(sizes) + '"'
      : "") + (copy ? originalAttrs(first) : "");
  }

  /** A small round portrait for a row - the map's panel, a profile's race -
   *  or, where the build found none, the person's initials in a disc of the
   *  same size. The cards had the disc and the rows kept grey silhouettes
   *  (VISUALS-16); one helper draws it for every row (rule 12). *sizes* is
   *  the width it is drawn at, e.g. "38px". */
  function portraitThumb(item, sizes) {
    if (!hasPortrait(item)) {
      return '<span class="thumb-monogram" aria-hidden="true">' +
        escapeHtml(monogram(item && item.name)) + "</span>";
    }
    return "<img " + portraitAttrs(item, sizes) + ' alt="" loading="lazy" decoding="async"' +
      ' data-photo-idx="0" data-profile="' + escapeAttr(item.id) + '">';
  }

  /** Point an existing <img> at a profile's portrait - the dialog reuses one
   *  element, so a srcset left by the last profile must go. */
  function setPortrait(img, item, sizes) {
    var set = portraitSrcset(item, sizes);
    var first = item && item.photos && item.photos[0];
    img.setAttribute("data-photo-idx", "0");
    img.removeAttribute("srcset");
    img.removeAttribute("sizes");
    img.removeAttribute("data-photo-original");
    if (set) {
      img.setAttribute("sizes", sizes);
      img.setAttribute("srcset", set);
    }
    img.removeAttribute("data-photo-of");
    if (copyOf(first, item && item.photoCopy)) {
      img.setAttribute("data-photo-original", photoHref(first));
      if (photoHref(first) !== first) img.setAttribute("data-photo-of", first);
    }
    img.src = portraitSrc(item);
  }

  function hostOf(url) {
    try {
      return new URL(String(url)).hostname.toLowerCase();
    } catch (e) {
      return "";
    }
  }

  /** Whose photograph an <img> drawn by setPortrait is showing now: the
   *  profile's own credit for its first portrait (``photoCredit``), a
   *  fallback's by the host that serves it (``kycBuildMeta.photoCredits``),
   *  or null for the silhouette (rule 87). */
  function shownPhotoCredit(img, item) {
    if (!img || !item) return null;
    var src = img.getAttribute("src") || "";
    if (!src || src === SILHOUETTE) return null;
    var at = parseInt(img.getAttribute("data-photo-idx") || "0", 10);
    if (!at) {
      // The copy this site made, or its original once the copy failed.
      var first = (item.photos || [])[0];
      return (src === photoSrc(first, item.photoCopy) && copyOf(first, item.photoCopy)
        ? copyCredit(item.photoCredit, first, item.photoCopy) : item.photoCredit) || null;
    }
    var table = (global.kycBuildMeta && global.kycBuildMeta.photoCredits) || {};
    var by = table[hostOf((item.photos || [])[at])];
    return by ? { by: by } : null;
  }

  /** One line crediting a photograph: "Photo: <author>, <licence>, via
   *  Wikimedia Commons", each linked where the credit holds the address,
   *  or "" when there is no credit. Escaped. */
  function photoCreditHtml(credit) {
    if (!credit || !(credit.by || credit.licence || credit.host)) return "";
    function anchor(href, text) {
      return /^https?:\/\//.test(href || "")
        ? '<a href="' + escapeAttr(href) + '" target="_blank" rel="noopener noreferrer">' +
          escapeHtml(text) + "</a>"
        : escapeHtml(text);
    }
    var parts = [];
    if (credit.by) parts.push(credit.via ? escapeHtml(credit.by) : anchor(credit.page, credit.by));
    // The licence asks for the author and the file's page names none.
    else if (credit.authorUnrecorded) parts.push("author not recorded on Commons");
    // Where a list found it, not whose it is: "Photo: from <host>, as listed
    // by Open States" (a host may be a news site or an image CDN).
    else if (credit.host) parts.push("from " + escapeHtml(credit.host));
    if (credit.licence) parts.push(anchor(credit.licenceUrl, credit.licence));
    // When it was made, where the source dates it plainly: any Commons
    // file's own single year, "Photo (1981): ..." - one phrase, and true of
    // a painted portrait too, where "Photograph, 2012." was not (the PR
    // #139 review) - and a justice's "Official portrait, 2005." before it.
    // Never a guessed, an estimated or an upload year (portraits.year_of).
    var year = !credit.dated && /^\d{4}$/.test(String(credit.year || "")) ? " (" + credit.year + ")" : "";
    var line = parts.length ? "Photo" + year + ": " + parts.join(", ") : "Photo" + year;
    if (credit.via) line += (parts.length ? ", via " : " via ") + anchor(credit.page, credit.via);
    if (credit.listedBy) line += ", as listed by " + escapeHtml(credit.listedBy);
    if (credit.dated) line = escapeHtml(credit.dated) + ". " + line;
    // A file this site decoded from the guide's (Oregon's JPEG 2000, which
    // no browser draws) is not the guide's own file, and says so, as a
    // smaller copy does (rule 101; kyc/guide_photos.py).
    if (credit.converted) {
      line += '<span class="photo-converted-note">; ' + escapeHtml(credit.converted) + "</span>";
    }
    // A smaller copy this site made of a heavy original (rule 101): whose
    // photograph it is stays the original's, and the original is linked.
    if (credit.copyOf) {
      var original = "the original file" +
        (credit.copyOfBytes ? " (" + weightWords(credit.copyOfBytes) + ")" : "");
      // An original hosted here (an election office's guide's) is linked
      // where this page loads it from.
      line += '<span class="photo-copy-note" data-copy-of="' + escapeAttr(credit.copyOf) +
        '">; a smaller copy made by this site of ' +
        (HOSTED.test(credit.copyOf)
          ? '<a href="' + escapeAttr(photoHref(credit.copyOf)) +
            '" target="_blank" rel="noopener noreferrer">' + escapeHtml(original) + "</a>"
          : anchor(credit.copyOf, original)) + "</span>";
    }
    return line;
  }

  /* Delegated: one listener for every portrait on the page, rather than an
   * inline onerror attribute per image with an id interpolated into it. */
  function initPortraitFallback() {
    doc.addEventListener(
      "error",
      function (event) {
        var img = event.target;
        if (!img || img.tagName !== "IMG") return;
        // A copy that fails falls back to its original first (rule 101).
        if (retryOriginal(img, event)) return;
        var id = img.getAttribute("data-profile");
        if (id) handleImageFallback(img, id);
      },
      true // error does not bubble; capture instead
    );
  }

  /* =========================================================== provenance */

  var ABSENT = {
    not_disclosed: "Not disclosed",
    unknown: "No data",
    no_filing: "No filing this cycle",
    not_listed: "Not listed on their official site",
    see_site: "On their official site's issues page",
    see_home: "On their official website",
  };
  var ABSENT_TITLE = {
    not_disclosed: "No public disclosure exists for this field.",
    unknown: "No source has been recorded for this field yet.",
    // Work this site did (rule 19): it read the member's official website.
    not_listed: "This site read the member's official website and found no page or menu " +
      "listing the issues they work on.",
    see_site: "This site read the member's official website and found an issues page, but no " +
      "list of issues it could take in the page's own words. The page is linked.",
    see_home: "This site read the member's official website and found issue pages it links, " +
      "but no issues page and too few issues to list. The site is linked.",
    // The only absence that reports work we actually did.
    no_filing: "Checked with the FEC: this candidate has no filing for the "
      + "current cycle. Members running for a different seat file under a "
      + "separate committee.",
  };

  /** Render one profile field so an absence never reads as a finding.
   *
   *  Three different things arrive in the same roster column - a sourced
   *  figure, "no filing exists", and "nobody has researched this" - and
   *  showing all three identically is the core credibility problem on a
   *  transparency site. */
  /* Where a field filled by the pipeline came from: [badge, tooltip]. */
  var FIELD_SOURCES = {
    "election-page": ["Wikipedia",
      "How Wikipedia's 2026 election page describes this candidate"],
    "wikipedia": ["Wikipedia", "From the candidate's Wikipedia article"],
    "campaign-site": ["Campaign site",
      "From the campaign's own website, in its own words"],
    // A member's (kyc/members.py, rule 86): each tied to them by their id,
    // never by a search on their name.
    "official-site": ["Official site",
      "From their official website, in its own words"],
    "congressional-directory": ["Congressional Directory",
      "From the Official Congressional Directory, printed by the Government Publishing " +
      "Office from each member's own office, in its words"],
    "member-wikipedia": ["Wikipedia",
      "From the infobox of the Wikipedia article congress-legislators links to this member"],
  };

  /** The badge saying where a pipeline-filled field came from, or "". */
  function sourceBadge(item, field) {
    var from = FIELD_SOURCES[((item && item.fieldSources) || {})[field]];
    return from
      ? ' <span class="badge badge-neutral field-source" title="' + escapeAttr(from[1]) +
        '">' + escapeHtml(from[0]) + "</span>"
      : "";
  }

  function renderField(item, field, opts) {
    opts = opts || {};
    var status = (item.quality || {})[field];
    var value = item[field];

    if (ABSENT[status]) {
      return (
        '<span class="kyc-absent" title="' + escapeAttr(ABSENT_TITLE[status]) +
        '">' + escapeHtml(ABSENT[status]) + "</span>"
      );
    }
    // A placeholder is not data (rule 10). "General legislative priorities"
    // stood as 67 members' platforms and "Public service" as 70 members'
    // careers, muted but still read as an answer; they are an absence.
    if (status === "generic") {
      return (
        '<span class="kyc-absent" title="The source held only a generic placeholder here, ' +
        'not researched detail.">' + escapeHtml(ABSENT.unknown) + "</span>"
      );
    }

    // A field filled from a named source (normalize.fill_field) says which.
    var html = escapeHtml(value) + sourceBadge(item, field);
    if (opts.source && item.financeSource) {
      var period = financePeriod(item);
      html +=
        ' <span class="badge badge-money" title="Filed with the FEC' +
        escapeAttr(period ? ". " + period : "") +
        '">' + escapeHtml(item.financeSource) + "</span>";
    }
    return html;
  }

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /** "2024-10-01" -> "Oct 2024"; anything that is not an ISO date -> "". */
  function monthYear(iso) {
    var m = /^(\d{4})-(\d{2})/.exec(String(iso || ""));
    if (!m || +m[2] < 1 || +m[2] > 12) return "";
    return MONTHS[+m[2] - 1] + " " + m[1];
  }

  /* A day in words, one helper for every view: "2026-10-15" ->
   * "Oct. 15, 2026", as the generated pages write it (kyc/pages.date_words)
   * and as a candidate's term already read ("Jan. 3, 2027"). A member's
   * dialog showed "Term 2025-01-03 - 2027-01-03" and "born 1965-06-15"
   * beside it. Anything that is not an ISO date is returned as it was. */
  var MONTH_WORDS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.",
                     "Sept.", "Oct.", "Nov.", "Dec."];

  function dateWords(iso) {
    var text = String(iso == null ? "" : iso);
    var m = /^(\d{4})-(\d{2})-(\d{2})(?:$|T)/.exec(text);
    if (!m || +m[2] < 1 || +m[2] > 12 || +m[3] < 1 || +m[3] > 31) return text;
    return MONTH_WORDS[+m[2] - 1] + " " + +m[3] + ", " + m[1];
  }

  /* The reader's own calendar day of a moment, as "2026-10-17". The build
   * stamp is UTC: built at 01:53 UTC on the 18th, every page read "Data
   * built Oct. 18, 2026" to a reader whose evening was still the 17th, a
   * day in their future beside results "read on Oct. 17". */
  function localDay(date) {
    function two(n) { return (n < 10 ? "0" : "") + n; }
    return date.getFullYear() + "-" + two(date.getMonth() + 1) + "-" + two(date.getDate());
  }

  /* --------------------------------------------------------- report a problem */

  /* The public repository, where a reader reports an error: an issue form
   * (.github/ISSUE_TEMPLATE/correction.yml) whose fields GitHub fills from
   * the query parameters named for them. kyc/pages.py writes the same
   * address into the generated footers (pages.REPO), and a test holds the
   * two together. */
  var REPO_URL = "https://github.com/pkplaya626/Know-Your-Candidate";

  /** The issue form, filled in with the page and the profile it is about. */
  function reportUrl(page, profile) {
    var url = REPO_URL + "/issues/new?template=correction.yml";
    if (page) url += "&page=" + encodeURIComponent(page);
    if (profile) url += "&profile=" + encodeURIComponent(profile);
    return url;
  }

  /* Every "Report a problem" link names the address the reader is on, the
   * open profile's included, when it is followed: the footer's link was
   * written before a profile opened over it, and the 404 page's cannot
   * know the address it was served for. */
  function aimReport(link) {
    var href = global.location.href;
    if (/^https?:/.test(href)) {
      link.setAttribute("href", reportUrl(href, link.getAttribute("data-profile") || ""));
    }
  }

  function initReportLinks() {
    Array.prototype.forEach.call(doc.querySelectorAll("a[data-report]"), aimReport);
    var aim = function (event) {
      var link = event.target && event.target.closest && event.target.closest("a[data-report]");
      if (link) aimReport(link);
    };
    doc.addEventListener("click", aim, true);
    doc.addEventListener("focusin", aim);
    doc.addEventListener("contextmenu", aim, true);
  }

  // A date in a sentence, as the profile writes a term ("Jan. 3, 2027"):
  // the one month table dateWords uses.
  var LONG_MONTHS = MONTH_WORDS;

  /** "2026-04-21" -> "April 21, 2026"; anything that is not an ISO date -> "". */
  function dayMonthYear(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    if (!m || +m[2] < 1 || +m[2] > 12) return "";
    return LONG_MONTHS[+m[2] - 1] + " " + (+m[3]) + ", " + m[1];
  }

  /** Plain text for an empty House seat (summary.py, from
   *  overrides.SEAT_VACANCIES): who left it, when and how, and whether a
   *  special election has been called, as of the day that was checked.
   *  "Vacant" alone left FL-20's and TX-23's readers to assume one was
   *  coming. One sentence for the state page and the district map alike. */
  function vacancyNote(v) {
    if (!v) return "";
    return "Vacant since " + dayMonthYear(v.left) + " (" + v.name + " " + v.how + "); " +
      v.special + " as of " + dayMonthYear(v.checked) + ".";
  }

  /** A place's possessive, as kyc/pages.py writes it (rule 75): "Virgin
   *  Islands'", never "Virgin Islands's"; "Texas's". */
  function possessive(name) {
    name = String(name || "");
    return name + (/Islands$/.test(name) ? "'" : "'s");
  }

  /** The vacancy record for *code*'s House district *n*, or null. */
  function vacancyOf(code, n) {
    var list = ((meta().states || {})[code] || {}).vacancies || [];
    for (var i = 0; i < list.length; i++) if (list[i].district === n) return list[i];
    return null;
  }

  /** Plain text saying what period a profile's money covers, or "".
   *
   *  Every figure is an FEC total, but over which months matters as much as
   *  the amount: a senator's election period is the whole six-year term, so
   *  the same "Raised" tile can hold six years beside a challenger's two.
   *  The pipeline records the period (financePeriod, financeElection,
   *  financeSince, financeAsOf); this only words it, and never fills a
   *  missing start date in. Plain text - callers escape it. */
  /** True when the coverage end a report gives is after the build. */
  function filedAhead(item) {
    var built = String(meta().built || "").slice(0, 10);
    return !!(item && item.financeAsOf && built && item.financeAsOf > built);
  }

  function financePeriod(item) {
    if (!item || !item.financeSource) return "";
    var since = monthYear(item.financeSince);
    var through = monthYear(item.financeAsOf);
    // A report can give a coverage end still to come (filed "through
    // December 31" in October): it is the filer's date, and one sentence at
    // the end says so, rather than a bare "(as filed)" that did not say why.
    var ahead = through && filedAhead(item)
      ? ". The report gives an end date still to come, " + through : "";
    var range = since && through ? ", " + since + " – " + through
      : through ? ", through " + through
      : since ? ", from " + since : "";

    if (item.financePeriod === "cycle") {
      // Cached before every figure moved to the election period: the
      // two-year cycle, which for a senator is not their whole campaign.
      return "Raised in the 2025–26 two-year cycle" + range +
        // Sitting senators only: for them two years is a third of the
        // election period their challengers' totals are measured over.
        (item.chamber === "Senate"
          ? ". That is not a senator's whole six-year election period, so it is not comparable with a challenger's total"
          : "") + ahead;
    }
    if (!item.financeElection) return through ? "FEC figures through " + through + ahead : "";

    var text = "Raised for the " + item.financeElection + " election" + range;
    var startYear = +(String(item.financeSince || "").slice(0, 4));
    // A period opening more than two calendar years before its election
    // spans a Senate term, not a House cycle. Say so rather than let it read
    // as two years of money.
    if (startYear && item.financeElection - startYear >= 2) {
      text += /^Senate/.test(String(item.chamber || ""))
        ? ". A Senate election period runs the whole six-year term, so this total goes back to " + startYear
        : ". This election period goes back to " + startYear;
    }
    return text + ahead;
  }

  /** True when a field carries something worth showing at all. */
  // A generic placeholder is no more a value than an absence (rule 10).
  // Counted as present, "General legislative priorities" still printed as
  // 67 members' platforms and matched a search for it.
  function hasValue(item, field) {
    var status = (item.quality || {})[field];
    return !ABSENT[status] && status !== "generic";
  }

  /* A filed figure as a number: "$47,190,466.06" -> 47190466.06; null for
   * anything that is not a figure (an absence's words). A filed $0 is a
   * figure (rule 6). */
  function moneyAmount(item, field) {
    if (!item || !hasValue(item, field) || !item.financeSource) return null;
    var text = String(item[field] == null ? "" : item[field]).trim().replace(/[$,]/g, "");
    return /^-?\d+(?:\.\d+)?$/.test(text) ? parseFloat(text) : null;
  }

  /* A figure rounded for a bar's label, "$35.0M", "$412K", "$950"; the
   * exact figure is the profile's. */
  function moneyShort(value) {
    if (value === null || value === undefined || isNaN(value)) return "";
    var sign = value < 0 ? "-" : "";
    var v = Math.abs(value);
    if (v >= 1e9) return sign + "$" + (v / 1e9).toFixed(1) + "B";
    if (v >= 1e6) return sign + "$" + (v / 1e6).toFixed(1) + "M";
    if (v >= 1e3) return sign + "$" + Math.round(v / 1e3) + "K";
    return sign + "$" + Math.round(v);
  }

  /* A profile's platform as its items: the campaign site's issue headings
   * ("; "-joined by kyc/enrich.py), a member's official website's issue
   * list (also "; "-joined, by kyc/members.py, rule 86), a list literal, or
   * comma-separated text. One reading for the dialog and the race's
   * comparison table (rule 12). Null when there is nothing to list. */
  function platformItems(item) {
    if (!item || !hasValue(item, "platforms")) return null;
    var text = String(item.platforms || "").trim();
    if (!text) return null;
    var source = (item.fieldSources || {}).platforms;
    var fromSite = source === "campaign-site" || source === "official-site";
    var parts = null;
    if (fromSite) {
      parts = text.split(/;\s+/);
    } else if (text.charAt(0) === "[" && text.charAt(text.length - 1) === "]") {
      try {
        var parsed = JSON.parse(text.replace(/'/g, '"'));
        if (Array.isArray(parsed)) parts = parsed.map(String);
      } catch (e) {
        /* not a list literal after all; fall through to the comma split */
      }
    }
    if (!parts) {
      // The rosters separate items with commas and use them inside items
      // too: "Telecommunications, technology, and digital privacy" is one
      // item, not three bullets reading "technology" and "and digital
      // privacy". Items start with a capital; a fragment that does not
      // belongs to the one before it.
      parts = text.split(/,\s+/).reduce(function (items, piece) {
        if (items.length && /^[a-z]/.test(piece)) items[items.length - 1] += ", " + piece;
        else items.push(piece);
        return items;
      }, []);
    }
    return { items: parts, fromSite: fromSite, text: text };
  }

  /* ============================================================= election */

  /* Federal general elections fall on the first Tuesday after the first
   * Monday in November - computed rather than hardcoded so the page stays
   * correct in later cycles. */
  function generalElectionDay(year) {
    var d = new Date(Date.UTC(year, 10, 1));
    while (d.getUTCDay() !== 1) d.setUTCDate(d.getUTCDate() + 1); // first Monday
    d.setUTCDate(d.getUTCDate() + 1); // the Tuesday after it
    return d;
  }

  /* A person's age today, in the reader's calendar, from their birthdate.
   * The build's `age` is computed on the build date and goes stale a day at
   * a time: nine days after one build, 17 were a year out, Alexandria
   * Ocasio-Cortez's among them on her birthday. A year-only birthdate keeps
   * the build's figure, which is all it supports; null when neither exists. */
  function ageOf(item, now) {
    if (!item) return null;
    var born = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(item.birthdate || ""));
    if (!born) return typeof item.age === "number" ? item.age : null;
    now = now || new Date();
    var years = now.getFullYear() - Number(born[1]);
    var month = now.getMonth() + 1;
    if (month < Number(born[2]) ||
        (month === Number(born[2]) && now.getDate() < Number(born[3]))) years -= 1;
    return years;
  }

  /* Counted in the reader's own calendar, not in UTC. Election Day is a
   * local date - polls open and close on local clocks - and measuring to
   * UTC midnight called it "Election Day" from 7 pm Eastern on the Sunday
   * before, then "the election has passed" from 7 pm Eastern on the day
   * itself, while every polling place west of the Mississippi was open.
   * Both sides are reduced to a calendar date (the reader's local
   * year/month/day, the election's civil date) and compared as whole days. */
  function electionStatus(year, now) {
    year = year || 2026;
    now = now || new Date();
    var day = generalElectionDay(year);
    var today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
    var days = Math.round((day.getTime() - today) / 86400000);

    var phase;
    if (days > 0) phase = "campaign";
    else if (days === 0) phase = "election-day";
    else phase = "post-election";

    return {
      year: year,
      date: day,
      days: days,
      phase: phase,
      label:
        phase === "election-day"
          ? "Election Day"
          : phase === "post-election"
          ? year + " general election has passed"
          : days + " day" + (days === 1 ? "" : "s") + " to the " + year + " election",
      iso: day.toISOString().slice(0, 10),
    };
  }

  /* ================================================================= a11y */

  var FOCUSABLE =
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]),' +
    ' textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  /** An accessible dialog: focus trap, Escape to close, focus restored to
   *  whatever opened it. */
  function createModal(el, opts) {
    opts = opts || {};
    var lastFocus = null;

    /* Anything focusable that is not inside a collapsed section. Tested with
     * `hidden` rather than offsetParent: a position:fixed element reports a
     * null offsetParent in several browsers, which would have emptied the
     * trap for this dialog specifically. */
    function focusables() {
      return Array.prototype.filter.call(el.querySelectorAll(FOCUSABLE), function (n) {
        return !n.hasAttribute("hidden") && !n.closest("[hidden]") &&
          n.getAttribute("tabindex") !== "-1";
      });
    }

    function onKeydown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        api.close();
        return;
      }
      if (event.key !== "Tab") return;

      var nodes = focusables();
      if (!nodes.length) return;
      var first = nodes[0];
      var last = nodes[nodes.length - 1];

      if (event.shiftKey && doc.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && doc.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    var api = {
      el: el,
      isOpen: function () {
        return !el.hidden;
      },
      open: function () {
        if (api.isOpen()) return;
        lastFocus = doc.activeElement;
        el.hidden = false;
        doc.body.style.overflow = "hidden";
        doc.addEventListener("keydown", onKeydown, true);
        var nodes = focusables();
        (nodes[0] || el).focus();
      },
      close: function () {
        if (!api.isOpen()) return;
        el.hidden = true;
        doc.body.style.overflow = "";
        doc.removeEventListener("keydown", onKeydown, true);
        if (lastFocus && lastFocus.focus) lastFocus.focus();
        if (opts.onClose) opts.onClose();
      },
    };

    // Any element marked data-close inside the dialog dismisses it: the
    // scrim, the X, the footer button. One rule instead of three onclicks.
    el.addEventListener("click", function (event) {
      if (event.target.closest("[data-close]")) api.close();
    });

    return api;
  }

  /** Phones and tablets: the layout with a drawer, or a finger to point. */
  function touchLayout() {
    return !!(global.matchMedia &&
      global.matchMedia("(max-width: 1000px), (pointer: coarse)").matches);
  }

  /** A click-opened, keyboard-operable menu.
   *
   *  The theme picker used to be a CSS :hover popup, which meant it could not
   *  be opened by keyboard at all and behaved erratically on touch, where a
   *  tap fires hover and click together. */
  function createMenu(button, panel, opts) {
    opts = opts || {};
    /* An item picked while the menu's history step (below) is still to be
     * undone. On a phone, closing steps back from that entry, and the step
     * lands after anything run now: a sort written to the address at the
     * pick was undone a moment later, back to the old order. So the pick
     * runs once the step has landed (*opts.onSelect*). */
    var picked = null;

    function isOpen() { return !panel.hidden; }

    function run() {
      var item = picked;
      picked = null;
      if (item && opts.onSelect) opts.onSelect(item);
    }

    /* *handover*: another menu is opening and takes the history entry, so
     * there is no step back - with two menus on a page, the step taken for
     * the first closed the second as it opened. */
    function close(fromHistory, handover) {
      if (!isOpen()) return;
      panel.hidden = true;
      button.setAttribute("aria-expanded", "false");
      doc.removeEventListener("keydown", onKey, true);
      doc.removeEventListener("click", onOutside, true);
      if (handover) return;
      if (fromHistory !== true && history.state && history.state.kycMenu) {
        history.back();               // the pick runs on the popstate it fires
        return;
      }
      run();
    }

    function open() {
      panel.hidden = false;
      button.setAttribute("aria-expanded", "true");
      doc.addEventListener("keydown", onKey, true);
      doc.addEventListener("click", onOutside, true);
      // On a touch screen Android's back gesture should close the menu, not
      // leave the page: an entry at the same address to step back from.
      if (touchLayout() && !(history.state && history.state.kycMenu)) {
        history.pushState({ kycMenu: true }, "", global.location.href);
      }
      var first = panel.querySelector(FOCUSABLE);
      if (first) first.focus();
    }

    global.addEventListener("popstate", function () {
      if (!(history.state && history.state.kycMenu)) {
        close(true);
        run();
      }
    });

    /* A role="menu" is announced as one, and a screen reader then hands the
     * keys to the page: arrows, Home and End moved nothing (audit
     * 2026-10-17, TECH-15). They move among the items, wrapping, as the
     * APG menu-button pattern has them. */
    function items() {
      var marked = panel.querySelectorAll('[role^="menuitem"]');
      var list = marked.length ? marked : panel.querySelectorAll(FOCUSABLE);
      return Array.prototype.filter.call(list, function (node) {
        return !node.disabled && !node.hidden && !node.closest("[hidden]");
      });
    }

    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        button.focus();
        return;
      }
      var move = { ArrowDown: 1, ArrowUp: -1, Home: "first", End: "last" }[event.key];
      if (!move) return;
      var list = items();
      if (!list.length) return;
      event.preventDefault();
      var at = list.indexOf(doc.activeElement);
      var next = move === "first" ? 0 : move === "last" ? list.length - 1
        : at === -1 ? (move > 0 ? 0 : list.length - 1)
        : (at + move + list.length) % list.length;
      list[next].focus();
    }

    function onOutside(event) {
      if (panel.contains(event.target) || button.contains(event.target)) return;
      var other = event.target.closest && event.target.closest("[data-kyc-menu]");
      close(false, !!other);
    }

    button.setAttribute("aria-expanded", "false");
    button.setAttribute("data-kyc-menu", "");
    button.addEventListener("click", function (event) {
      event.stopPropagation();
      if (isOpen()) close(); else open();
    });
    panel.addEventListener("click", function (event) {
      var item = event.target.closest(".menu-item");
      if (!item) return;
      picked = item;
      close();
    });

    return { open: open, close: close, isOpen: isOpen };
  }

  /* =============================================================== router */

  /* Deep links: "#/profile/<id>" for one person, "#/?k=v" for a filtered
   * view. Without this the site cannot be shared, which is the single
   * biggest functional gap for a tool whose whole purpose is being passed
   * around before an election. */
  var routeHandlers = [];
  /* The address the page last showed. A history step that lands on the same
   * address - the entry the drawer pushes so Android's back gesture can
   * close it - is not a navigation, and redrawing for it would cut a grid
   * the reader had scrolled deep into back to its first page of cards. The
   * one dispatcher also stops each handler running twice per hash change,
   * once for hashchange and once for popstate. */
  var routedHref = global.location.href;

  function onNavigate() {
    if (global.location.href === routedHref) return;
    routedHref = global.location.href;
    routeHandlers.forEach(function (handler) { handler(); });
  }
  global.addEventListener("hashchange", onNavigate);
  global.addEventListener("popstate", onNavigate);

  var router = {
    read: function () {
      var hash = global.location.hash.replace(/^#\/?/, "");
      if (!hash) {
        // "index.html?q=..." - a search submitted with no script, or the
        // address search engines are given (the page's SearchAction).
        var asked = /[?&]q=([^&]*)/.exec(global.location.search || "");
        var words = "";
        try { words = asked ? decodeURIComponent(asked[1].replace(/\+/g, " ")) : ""; } catch (e) { /* malformed */ }
        return { view: "list", params: words ? { q: words } : {} };
      }

      // A person: a profile, or a federal official (kyc-official.js).
      var dialog = hash.match(/^(profile|official)\/(.+)$/);
      if (dialog) {
        try {
          return { view: dialog[1], id: decodeURIComponent(dialog[2]), params: {} };
        } catch (e) {
          return { view: dialog[1], id: dialog[2], params: {} };
        }
      }

      var params = {};
      var query = hash.indexOf("?") === 0 ? hash.slice(1) : hash;
      query.split("&").forEach(function (pair) {
        if (!pair) return;
        var bits = pair.split("=");
        try {
          params[decodeURIComponent(bits[0])] =
            decodeURIComponent(bits.slice(1).join("=") || "");
        } catch (e) {
          /* a malformed hash should not blank the page */
        }
      });
      return { view: "list", params: params };
    },

    writeFilters: function (params) {
      var query = Object.keys(params)
        .filter(function (k) { return params[k] && params[k] !== "all"; })
        .map(function (k) {
          // Commas are legal in a fragment: a shared link reads "d=3,6",
          // not "d=3%2C6". read() decodes either.
          return encodeURIComponent(k) + "=" +
            encodeURIComponent(params[k]).replace(/%2C/g, ",");
        })
        .join("&");
      var hash = query ? "#/?" + query : "#/";
      if (global.location.hash === hash) return;
      // replaceState: filter tweaks should not fill the back button.
      history.replaceState(null, "", global.location.pathname + hash);
      routedHref = global.location.href;
    },

    /* The pushed entry is marked, so closing knows whether there is a view
     * of ours behind it to go back to - and counts how many profiles deep
     * it is. A profile opened from another profile's race list is pushed
     * on top of it, so the browser's Back steps back through them; closing
     * used to step back one at a time too, and every profile visited had
     * to be closed in turn. */
    writeProfile: function (id) {
      router.writeDialog("profile", id);
    },

    /** A federal official's dialog: the same history as a profile's. */
    writeOfficial: function (id) {
      router.writeDialog("official", id);
    },

    writeDialog: function (kind, id) {
      var hash = "#/" + kind + "/" + encodeURIComponent(id);
      if (global.location.hash === hash) return;
      var state = history.state;
      var depth = 1;
      if (state && state.kycProfile) {
        depth = (state.depth || 1) + 1;
      } else if (/#\/(profile|official)\//.test(global.location.hash)) {
        // A profile the reader landed on from a shared link: put the list
        // beneath it, so closing what they open from it ends on the list,
        // not on the profile they arrived at.
        history.replaceState(null, "", global.location.pathname + "#/");
      }
      history.pushState({ kycProfile: true, depth: depth }, "",
        global.location.pathname + hash);
      routedHref = global.location.href;
    },

    /** Leave a profile view, however many profiles deep. Back only undoes
     *  profiles this page pushed. A visitor who arrived on a shared
     *  #/profile/ link has nothing of ours behind them, and history.back()
     *  sent them off the site - so that entry is replaced with the list in
     *  place and the page told to show it, since replaceState fires no
     *  event of its own. */
    clearProfile: function () {
      if (!/#\/(profile|official)\//.test(global.location.hash)) return;
      var state = history.state;
      if (state && state.kycProfile) {
        var depth = state.depth || 1;
        if (depth > 1) history.go(-depth);
        else history.back();
        return;
      }
      history.replaceState(null, "", global.location.pathname + "#/");
      routedHref = global.location.href;
      routeHandlers.forEach(function (handler) { handler(); });
    },

    onChange: function (handler) {
      routeHandlers.push(handler);
    },
  };

  /* ============================================================== helpers */

  /** The party bucket a profile displays as. One definition; the pages each
   *  had their own and they disagreed about Democratic-Farmer Labor. The
   *  pages the build writes use kyc/pages.py party_key, the same test in
   *  Python; test_guide runs this one beside it, so change both together. */
  function partyKey(item) {
    if (!item) return "i";
    if (item.party === "Vacant" || item.status === "Vacant") return "vacant";
    if (String(item.party).indexOf("Democrat") !== -1) return "d";
    if (item.party === "Republican") return "r";
    return "i";
  }

  function partyClass(item) {
    return "party-" + partyKey(item);
  }

  /** A person's party, in brackets after the name: D and R, I for an
   *  independent, and any other party by its own name. The colour bucket
   *  (partyKey) folds every third party into "i", and the lookup's answer
   *  called the Libertarian Ted Brown "(I)" beside a ballot page that
   *  names him Libertarian (PR #118 review). One for the lookup and a
   *  state page's race rows (rule 12). */
  function partyAbbr(p) {
    var key = partyKey(p);
    if (key === "d") return "D";
    if (key === "r") return "R";
    if (key !== "i") return "";
    var party = String((p && p.party) || "").trim();
    if (!party || party === "Other") return "";
    return party === "Independent" ? "I" : party;
  }

  /* ------------------------------------------------------------- hatches */

  /* "Split" and "none" are told apart from the colours around them by a
   * hatch as well as a colour, a cue that does not depend on seeing hue:
   * to a deuteranope the old split lilac was the Democratic blue, and every
   * divided state read as Democratic (audit 2026-10-17, VISUALS-03). A map
   * draws the patterns in its own SVG at its own scale (hatchDefs) and
   * names them on the SVG as custom properties (hatchVars); a shape's fill
   * then names the property with its plain colour as the fallback
   * (svgFill), so a map with no patterns still draws the colour. One fill
   * per shape, no clip or mask (rule 45). */
  var HATCHES = {
    "split": ["var(--split)", "var(--split-hatch)", 0.4],
    "split-soft": ["color-mix(in srgb, var(--split) 70%, var(--surface-1))",
      "color-mix(in srgb, var(--split-hatch) 70%, var(--surface-1))", 0.4],
    "none": ["var(--none-fill)", "var(--none-hatch)", 0.22],
  };
  var HATCHED = { "var(--split)": "split", "var(--none-fill)": "none" };

  /** The patterns, *unit* map units apart (about 6px on screen), with ids
   *  that begin with *prefix*. */
  function hatchDefs(prefix, unit) {
    var u = (+unit || 6).toFixed(2);
    var w = function (share) { return (unit * share).toFixed(2); };
    return "<defs>" + Object.keys(HATCHES).map(function (key) {
      var h = HATCHES[key];
      return '<pattern id="' + prefix + "hatch-" + key + '" patternUnits="userSpaceOnUse" width="' +
        u + '" height="' + u + '" patternTransform="rotate(45)">' +
        '<rect width="' + u + '" height="' + u + '" style="fill:' + h[0] + '"/>' +
        '<rect width="' + w(h[2]) + '" height="' + u + '" style="fill:' + h[1] + '"/></pattern>';
    }).join("") + "</defs>";
  }

  /** The style that names the patterns for the shapes inside an SVG. */
  function hatchVars(prefix) {
    return Object.keys(HATCHES).map(function (key) {
      return "--hatch-" + key + ":url(#" + prefix + "hatch-" + key + ")";
    }).join(";");
  }

  /** A shape's fill: a hatched colour names its pattern, the colour after. */
  function svgFill(fill) {
    var key = HATCHED[fill];
    return key ? "var(--hatch-" + key + ", " + fill + ")" : fill;
  }

  /* A scroll the page makes for the reader animates only for a reader who
   * has not asked for less motion: an explicit { behavior: "smooth" }
   * overrides the stylesheet's reduced-motion rule (audit 2026-10-17,
   * TECH-16). Every scrollIntoView the modules make passes this. */
  function scrollBehavior() {
    try {
      if (global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches) return "auto";
    } catch (e) { /* no media queries: the default */ }
    return "smooth";
  }

  /* The word's colour on a fill, where the callout's default (the inverse
   * text) does not read: the mid-tones and the greys name their own ink,
   * per theme, in kyc.css. */
  var FILL_INK = {
    "var(--split)": "var(--split-ink)",
    "var(--party-r-tint)": "var(--text)",
    "var(--party-d-tint)": "var(--text)",
    "var(--vacant-fill)": "var(--vacant-ink)",
    "var(--none-fill)": "var(--text)",
  };
  function fillInk(fill) {
    return FILL_INK[fill] || (/--surface-/.test(fill || "") ? "var(--text)" : "");
  }

  /** The same fill as an HTML background, for a legend swatch or a callout. */
  function swatchFill(fill) {
    var key = HATCHED[fill];
    if (!key) return fill;
    var h = HATCHES[key];
    var edge = (5 * h[2]).toFixed(1);
    return "repeating-linear-gradient(135deg, " + h[1] + " 0 " + edge + "px, " + h[0] + " " +
      edge + "px 5px)";
  }

  /* Search across everything a voter might reasonably type, not just name
   * and state. Absent fields are excluded so "not disclosed" does not match
   * every profile at once. */
  var SEARCH_FIELDS = [
    "name", "state", "party", "district", "officeLabel", "status",
    "education", "previous_professions", "committees", "platforms",
    "funding_sources", "voting_alignment",
    // The campaign's own words: "nurse", "veteran" find who says so.
    "campaignQuote",
  ];

  /* Lower case with accents removed (NFD, then drop the combining marks), on
   * the query and the profile alike: "Diaz-Balart" finds "Díaz-Balart" and
   * the other way round. */
  function foldText(text) {
    return String(text == null ? "" : text).normalize("NFD")
      .replace(/\p{Mn}/gu, "").toLowerCase();
  }

  /* What a search compares: folded (foldText), with periods made spaces so
   * "J.D." is "J D" (and, through joinInitials, "JD") and "C. Franklin" is
   * "C Franklin", curly apostrophes
   * made straight, and spaces collapsed. */
  function searchFold(text) {
    return foldText(text).replace(/\./g, " ").replace(/[‘’]/g, "'")
      .replace(/\s+/g, " ").trim();
  }

  /* "j d vance" and "jd vance" are one name: runs of single letters joined. */
  function joinInitials(folded) {
    return folded.replace(/\b([a-z]) (?=[a-z]\b)/g, "$1");
  }

  // The name fields, the place and office fields, and the rest: a query is
  // ranked by the first tier its every word is found in (GRID-05).
  var NAME_FIELDS = ["name"];
  var OFFICE_FIELDS = ["state", "party", "district", "officeLabel", "contestLabel"];

  /* A seat's title before a name, as a reader writes it: "Senator Warren",
   * "Rep. Crockett", "Congressman Davidson", "Delegate Norton" (rule 97).
   * Read off the query, never added to a profile's text: there "Con" and
   * "Sen", typed on the way to a name, matched every sitting member. The
   * title says the chamber and nothing else - the data hold no one's sex,
   * so "Congresswoman Smith" is every sitting House member named Smith. */
  var SEAT_TITLE = /^(?:(senators?|sens?)|(representatives?|reps?|congress ?(?:man|woman|member|person)|delegates?|resident commissioner)) (.+)$/;

  function searchTiers(item) {
    if (item.__tiers) return item.__tiers;
    var names = [item.name].concat(item.aliases || []).filter(Boolean).map(String);
    var office = [];
    OFFICE_FIELDS.forEach(function (field) { if (item[field]) office.push(String(item[field])); });
    if (item.state && item.state !== "N/A") office.push(stateName(item.state));
    // The party's name as the chip says it: "Democratic" found 26 people
    // and the Democratic chip 541, because the FEC's word is "Democrat".
    if (item.party === "Democrat") office.push("Democratic");
    // A leadership post held, as the profile shows it (by bioguide id, from
    // congress-legislators): "Speaker" found only a "motivational speaker"
    // in a challenger's text, never the Speaker (GRID-05).
    if (seated(item)) (item.leadership || []).forEach(function (t) { office.push(String(t)); });
    var body = [];
    SEARCH_FIELDS.forEach(function (field) {
      if (NAME_FIELDS.indexOf(field) !== -1 || OFFICE_FIELDS.indexOf(field) !== -1) return;
      if (item[field] && hasValue(item, field)) body.push(String(item[field]));
    });
    var name = searchFold(names.join(" · "));
    item.__tiers = {
      names: names.map(searchFold),
      name: " " + name,
      office: " " + name + " " + searchFold(office.join(" · ")),
      all: " " + name + " " + searchFold(office.join(" · ")) + " " +
        searchFold(body.join(" · ")),
    };
    return item.__tiers;
  }

  /** Everything a profile is searched by, folded: kept for callers that
   *  want the whole text. */
  function searchIndex(item) {
    return searchTiers(item).all;
  }

  /* A word matches where a word starts, never inside one (rule 5):
   * "kansas" is in "arkansas" as text, and the grid returned Arkansans for
   * it (GRID-03). A word may be typed in part: "pelo" finds Pelosi. */
  function escapeRegex(text) {
    return String(text).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function wordStart(term) {
    return new RegExp("(?:^|[^a-z0-9])" + escapeRegex(term));
  }

  /* Names a reader types for a first name (FEDERAL-02): "Jim Boasberg",
   * "Bill Pryor". Common English short forms only, so a short form finds
   * the formal name and never the reverse; a query is still matched on
   * the surname alone (nameScore). */
  var NICKNAMES = {
    al: ["albert", "alan", "allen", "alfred"], alex: ["alexander", "alexandra", "alejandro"],
    andy: ["andrew"], ben: ["benjamin"], bill: ["william"], billy: ["william"],
    bob: ["robert"], bobby: ["robert"], charlie: ["charles"], chris: ["christopher", "christine"],
    chuck: ["charles"], dan: ["daniel"], danny: ["daniel"], dave: ["david"], dick: ["richard"],
    don: ["donald"], doug: ["douglas"], drew: ["andrew"], ed: ["edward", "edwin", "edmund"],
    fred: ["frederick"], greg: ["gregory"], hank: ["henry"], jack: ["john"], jake: ["jacob"],
    jeff: ["jeffrey"], jerry: ["gerald", "jerome"], jim: ["james"], jimmy: ["james"],
    joe: ["joseph"], jon: ["jonathan"], kate: ["katherine", "kathryn", "catherine"],
    ken: ["kenneth"], larry: ["lawrence"], liz: ["elizabeth"], matt: ["matthew"],
    mike: ["michael"], nick: ["nicholas"], pat: ["patrick", "patricia"], pete: ["peter"],
    rick: ["richard", "frederick"], rob: ["robert"], ron: ["ronald"], sam: ["samuel"],
    steve: ["stephen", "steven"], sue: ["susan"], ted: ["edward", "theodore"],
    tim: ["timothy"], tom: ["thomas"], tony: ["anthony"], will: ["william"],
  };

  var SUFFIX_WORDS = { jr: true, sr: true, ii: true, iii: true, iv: true, v: true };

  /* The last word of a folded name that is not a suffix: "pryor" of
   * "william h pryor, jr". */
  function lastName(folded) {
    var words = folded.replace(/,/g, " ").split(" ").filter(Boolean);
    while (words.length > 1 && SUFFIX_WORDS[words[words.length - 1]]) words.pop();
    return words[words.length - 1] || "";
  }

  function wholeWord(term) {
    return new RegExp("(?:^|[^a-z0-9])" + escapeRegex(term) + "(?![a-z0-9])");
  }

  /** How well *query* names someone known as any of *names*: 0 for the
   *  name itself, 1 for every word found whole in one of the names (a
   *  first name's short form counts: "Jim" for James), 1.5 for every word
   *  found where a word starts, some only in part ("Roberts" in
   *  "Robertson", "pelo" while typing Pelosi), 2 for a query whose last
   *  word is the surname alone ("Skip Rankin"), else -1. For people a
   *  reader looks up by name: the judges, the officials. */
  function nameScore(query, names) {
    var q = searchFold(query);
    if (!q) return -1;
    var folded = (names || []).filter(Boolean).map(searchFold);
    var joined = joinInitials(q);
    if (folded.some(function (n) {
      return n.replace(/,/g, "") === q || joinInitials(n.replace(/,/g, "")) === joined;
    })) return 0;
    var terms = q.split(" ");
    var all = function (name, test) {
      return terms.every(function (term, i) {
        var forms = [term].concat(i === 0 && terms.length > 1 ? NICKNAMES[term] || [] : []);
        return forms.some(function (form) { return test(form).test(name); });
      });
    };
    var found = function (test) {
      return folded.some(function (n) { return all(n, test) || all(joinInitials(n), test); });
    };
    if (found(wholeWord)) return 1;
    if (found(wordStart)) return 1.5;
    var last = terms[terms.length - 1];
    if (terms.length > 1 && folded.some(function (n) { return lastName(n) === last; })) return 2;
    return -1;
  }

  /* ----------------------------------------------------- query parsing */

  /* A query that names a state or a seat is answered as one: "Ohio 9",
   * "TX-35", "texas district 35", "ny14", "AZ at large" are a race, and
   * "TX-3" is never TX-30 to TX-39; "Kansas" is Kansas's people, not
   * everyone whose text mentions it (GRID-03, GRID-04). */
  /* The short forms a reader writes a state's name in ("Calif.", "Tex.",
   * "Mass."), with whether one alone is the state. A word that is also an
   * English word or the start of a name ("Miss", "Wash", "Del", "Mont" of
   * Montgomery, "Tenn" of Tenney) names the state only beside an office or
   * a court ("Ill. governor", "D. Del.", kyc-search.js), never typed alone:
   * there it is a name being typed. */
  var STATE_ABBREVIATIONS = {
    ala: ["AL", false], ariz: ["AZ", true], ark: ["AR", false], cal: ["CA", false],
    calif: ["CA", true], colo: ["CO", false], conn: ["CT", false], del: ["DE", false],
    fla: ["FL", true], haw: ["HI", false], ill: ["IL", false], ind: ["IN", false],
    kan: ["KS", false], kans: ["KS", true], mass: ["MA", false], mich: ["MI", false],
    minn: ["MN", false], miss: ["MS", false], mont: ["MT", false], neb: ["NE", false],
    nebr: ["NE", true], nev: ["NV", false], okla: ["OK", true], ore: ["OR", false],
    oreg: ["OR", true], penn: ["PA", false], penna: ["PA", true], tenn: ["TN", false],
    tex: ["TX", false], wash: ["WA", false], wis: ["WI", false], wisc: ["WI", true],
    wyo: ["WY", true], "w va": ["WV", true], wva: ["WV", true], "n mex": ["NM", true],
    "n dak": ["ND", true], "s dak": ["SD", true], "n car": ["NC", true], "s car": ["SC", true],
  };

  /** The state a short form names ("calif" -> "CA"), or null; *alone*
   *  asks only for the forms that name it typed on their own. */
  function stateAbbreviation(word, alone) {
    var hit = STATE_ABBREVIATIONS[word];
    return hit && (!alone || hit[1]) ? hit[0] : null;
  }

  var stateByName = null;
  function stateNames() {
    if (stateByName === null) {
      stateByName = {};
      var states = meta().states || {};
      Object.keys(states).forEach(function (code) {
        stateByName[searchFold(states[code].name || "")] = code;
      });
      if (states.DC) {
        ["washington dc", "washington d c", "d c"].forEach(function (n) { stateByName[n] = "DC"; });
      }
      if (states.VI) {
        stateByName["us virgin islands"] = stateByName["u s virgin islands"] = "VI";
        stateByName["virgin islands"] = "VI";
      }
      if (states.MP) stateByName["northern marianas"] = stateByName["mariana islands"] = "MP";
      Object.keys(STATE_ABBREVIATIONS).forEach(function (word) {
        var code = stateAbbreviation(word, true);
        if (code && states[code]) stateByName[word] = code;
      });
    }
    return stateByName;
  }

  /** The state *text* names, whole: its name or its postal code. */
  function stateNamed(text) {
    var folded = searchFold(text).replace(/-/g, " ").replace(/\s+/g, " ");
    var byName = stateNames();
    if (byName[folded]) return byName[folded];
    var code = folded.toUpperCase();
    return /^[A-Z]{2}$/.test(code) && (meta().states || {})[code] ? code : null;
  }

  var SEAT_REST = [
    // "9", "9th", "district 9", "cd 9", "9th district", "congressional district 9"
    [/^(?:(?:congressional )?(?:district|dist|cd) )?(\d{1,2})(?:st|nd|rd|th)?(?: (?:congressional )?district| cd)?$/,
      function (m) { return { district: parseInt(m[1], 10) }; }],
    [/^(?:at large|atlarge|al)(?: (?:district|seat))?$/, function () { return { district: 0 }; }],
    [/^(?:us |u s )?(?:senate|senators?|senate race|senate seat)$/,
      function () { return { chamber: "Senate" }; }],
    [/^(?:us |u s )?(?:house|representatives?|reps?|house delegation|house members)$/,
      function () { return { chamber: "House" }; }],
    // "Ohio congressman", "Texas congresswomen" (rule 97): who sits for the
    // state in the House, as a reader says it - the members, never the
    // people running against them (rule 27).
    [/^(?:us |u s )?(?:congress ?(?:man|woman|men|women|person|people|member|members))$/,
      function () { return { chamber: "House", seated: true }; }],
    // "Ohio delegation", "Ohio members of Congress": both chambers' members.
    [/^(?:(?:us |u s )?congressional delegation|delegation|members of congress|congress)$/,
      function () { return { seated: true }; }],
  ];

  /** *query* read as a place: `{state, chamber, district, any}` (any: a
   *  district number with no state, "district 7"), or null for words. */
  function parsePlace(query) {
    var s = searchFold(query).replace(/[-–#,]/g, " ").replace(/'s\b/g, "")
      .replace(/\s+/g, " ").trim();
    if (!s) return null;
    var whole = stateNamed(s);
    if (whole) return { state: whole };
    var compact = /^([a-z]{2}) ?(\d{1,2}|al)$/.exec(s);
    var states = meta().states || {};
    if (compact && states[compact[1].toUpperCase()]) {
      return { state: compact[1].toUpperCase(), chamber: "House",
               district: compact[2] === "al" ? 0 : parseInt(compact[2], 10) };
    }
    var any = /^(?:congressional )?(?:district|cd) (\d{1,2})$/.exec(s);
    if (any) return { chamber: "House", district: parseInt(any[1], 10), any: true };
    // The longest state name the query opens with, then what follows it.
    var byName = stateNames();
    var best = null;
    Object.keys(byName).forEach(function (name) {
      if (s.indexOf(name + " ") === 0 && (!best || name.length > best.length)) best = name;
    });
    var code = best ? byName[best] : null;
    var rest = best ? s.slice(best.length + 1) : "";
    if (!code) {
      var two = /^([a-z]{2}) (.+)$/.exec(s);
      if (two && states[two[1].toUpperCase()]) { code = two[1].toUpperCase(); rest = two[2]; }
    }
    if (!code) return null;
    for (var i = 0; i < SEAT_REST.length; i++) {
      var m = SEAT_REST[i][0].exec(rest);
      if (m) {
        var out = SEAT_REST[i][1](m);
        out.state = code;
        if (out.district !== undefined) out.chamber = "House";
        return out;
      }
    }
    return null;
  }

  /** The races a place names: a district's (a state with one at-large seat
   *  answers its "1" too), or none. */
  function placeRaces(place) {
    if (!place || place.district === undefined) return [];
    var house = races().filter(function (r) {
      return r.chamber === "House" && (place.any || r.state === place.state);
    });
    var exact = house.filter(function (r) { return Number(r.district) === place.district; });
    if (!exact.length && !place.any && place.district === 1 &&
        house.length && house.every(function (r) { return Number(r.district) === 0; })) {
      exact = house;
    }
    return exact;
  }

  /** "OH-9", "Ohio's House seats", "Kansas": what a place query asked for,
   *  for the results line. */
  function houseSeats(code) {
    var info = (meta().states || {})[code] || {};
    return (info.house || 0) + (info.delegates || 0);
  }

  /** Why a seat a query names does not exist, in a sentence, or "": "AZ at
   *  large" and "Ohio 99" were answered as AZ-AL and OH-99, seats nobody
   *  holds or runs for. The count of seats is the build's (one at large
   *  answers "1" too); a state with none listed concludes nothing. */
  function seatNote(place) {
    if (!place || place.district === undefined || place.any) return "";
    var seats = houseSeats(place.state);
    if (!seats) return "";
    var name = stateName(place.state);
    if (seats === 1) {
      return place.district <= 1 ? "" : name + " has one House seat, elected at large (" +
        place.state + "-AL).";
    }
    if (place.district >= 1 && place.district <= seats) return "";
    return name + (place.district === 0 ? " has no at-large seat" : " has no district " +
      place.district) + "; its districts are numbered 1 to " + seats + ".";
  }

  function placeLabel(place) {
    if (!place) return "";
    if (place.district !== undefined) {
      if (seatNote(place)) return "";
      // A state with one seat: its "1" is the at-large seat, and is named so.
      var seat = place.district === 0 || (!place.any && houseSeats(place.state) === 1)
        ? "AL" : String(place.district);
      return place.any ? "district " + seat + " in every state" : place.state + "-" + seat;
    }
    var name = stateName(place.state);
    if (place.seated) {
      return name + "’s sitting " + (place.chamber === "House" ? "House members" : "members of Congress");
    }
    if (place.chamber === "Senate") return name + "’s Senate seats";
    if (place.chamber === "House") return name + "’s House seats";
    return name;
  }

  /* A compiled query, kept for the last query asked: the grid asks once per
   * profile. */
  var compiled = { query: null };

  function compileQuery(query) {
    if (compiled.query === query) return compiled;
    var place = parsePlace(query);
    var q = searchFold(query);
    var terms = q ? q.split(" ").map(wordStart) : [];
    var exact = q;
    // "Senator Warren": a sitting senator named Warren first (SEAT_TITLE).
    var titled = !place && SEAT_TITLE.exec(q);
    var title = titled ? { chamber: titled[1] ? "Senate" : "House",
      terms: titled[3].split(" ").map(wordStart), exact: titled[3] } : null;
    var seat = null;
    if (place && place.district !== undefined) {
      seat = new Set();
      placeRaces(place).forEach(function (race) {
        race.incumbentIds.concat(race.candidateIds).forEach(function (id) { seat.add(id); });
        seat.add("race:" + race.id);
      });
    }
    var two = place && /^[a-z]{2}$/.test(q);
    compiled = { query: query, place: place, seat: seat, terms: terms, exact: exact,
                 two: two, title: title, label: placeLabel(place), note: seatNote(place) };
    return compiled;
  }

  function placeScore(c, item) {
    var place = c.place;
    if (c.seat) {
      var rid = item.isCandidate ? item.raceId : (item.contestRaceId || item.raceId);
      if (c.seat.has(item.id) || c.seat.has("race:" + rid) ||
          c.seat.has("race:" + item.heldRaceId)) return 1;
      // Whoever holds the seat now, if the race does not list them.
      if (!item.isCandidate && !item.formerMember && item.state === place.state &&
          !place.any && String(item.chamber).indexOf("House") !== -1 &&
          item.districtNum === place.district) return 1;
      return -1;
    }
    if (item.state !== place.state) return -1;
    if (place.seated) {
      return seated(item) && (!place.chamber || String(item.chamber).indexOf(place.chamber) !== -1) ? 1 : -1;
    }
    if (!place.chamber) return 1;
    var running = item.isCandidate ? item.raceId : item.contestRaceId;
    var prefix = place.chamber === "Senate" ? "S-" : "H-";
    return String(item.chamber).indexOf(place.chamber) !== -1 ||
      String(running || "").indexOf(prefix) === 0 ? 1 : -1;
  }

  /** How well *item* matches *query*: 0 its name or an alias exactly, 1
   *  every word in its names, 2 in its names, place and office, 3 anywhere
   *  in its text; a state or seat query is 1 for that place's people (and
   *  2 for anyone else so named: "Virginia" is also Virginia Foxx); -1 for
   *  no match. Words match where a word starts. */
  function queryScore(item, query) {
    if (!query) return 3;
    var c = compileQuery(query);
    var tiers = searchTiers(item);
    var exact = tiers.names.some(function (n) {
      return n === c.exact || joinInitials(n) === joinInitials(c.exact);
    });
    if (c.place) {
      var at = placeScore(c, item);
      if (at >= 0) return at;
      if (c.seat) return -1;
      // A postal code is a state, not the start of a name ("in", "me").
      if (c.two) return exact ? 2 : -1;
      return c.terms.every(function (t) { return t.test(tiers.name); }) ? 2 : -1;
    }
    // A sitting member of the chamber the title names, by name; anyone
    // else only as the whole query finds them.
    if (c.title && seated(item) && String(item.chamber).indexOf(c.title.chamber) !== -1) {
      if (tiers.names.some(function (n) {
        return n === c.title.exact || joinInitials(n) === joinInitials(c.title.exact);
      })) return 0;
      if (c.title.terms.every(function (t) { return t.test(tiers.name); })) return 1;
    }
    if (exact) return 0;
    var every = function (text) { return c.terms.every(function (t) { return t.test(text); }); };
    if (every(tiers.name)) return 1;
    if (every(tiers.office)) return 2;
    return every(tiers.all) ? 3 : -1;
  }

  function matchesQuery(item, query) {
    return !query || queryScore(item, query) >= 0;
  }

  var SNIPPET_FIELDS = {
    education: "Education", previous_professions: "Career", committees: "Committees",
    platforms: "Platform", funding_sources: "Funding", voting_alignment: "Voting record",
    campaignQuote: "Campaign", status: "Status",
  };

  /** Where a body-text match was found, for a card matched only there:
   *  `{label, text}` with the words around the first hit, or null. Nothing
   *  on a card said why "Speaker" found a "motivational speaker" (GRID-05). */
  function searchSnippet(item, query) {
    var c = compileQuery(query);
    if (!c.terms.length) return null;
    var tiers = searchTiers(item);
    var term = c.terms.filter(function (t) { return !t.test(tiers.office); })[0] || c.terms[0];
    var fields = Object.keys(SNIPPET_FIELDS);
    for (var i = 0; i < fields.length; i++) {
      var field = fields[i];
      if (!item[field] || !hasValue(item, field)) continue;
      var raw = String(item[field]);
      // foldText keeps the length of composed text, so a position in it is
      // a position in the original.
      var folded = foldText(raw).replace(/[‘’]/g, "'");
      var hit = term.exec(folded);
      if (!hit) continue;
      var at = hit.index + (hit[0].length && /[^a-z0-9]/.test(hit[0][0]) ? 1 : 0);
      var from = Math.max(0, at - 30);
      var to = Math.min(raw.length, at + 60);
      return { label: SNIPPET_FIELDS[field],
               text: (from ? "…" : "") + raw.slice(from, to).trim() + (to < raw.length ? "…" : "") };
    }
    return null;
  }

  /* --------------------------------------------------- data on demand */

  /* A data file the page needs only sometimes - the officials the grid's
   * search also looks through, a chamber's roll calls for the profile
   * dialog - is named, with its version stamp, in an inert
   * <template id="onDemandData"> (so the build stamps it, rule 76) and
   * loaded the first time it is wanted. *file* is its path under data/; a
   * page a folder down names it "../data/...". *global* is the variable it
   * assigns: one already there (a page that loads it anyway, a test) is
   * used as it is. */
  var demanded = {};

  /** The stamped address the page names for data/<file>, or null. */
  function onDemandSrc(file) {
    var holder = doc.getElementById("onDemandData");
    if (!holder || !holder.content) return null;
    var tag = Array.prototype.filter.call(holder.content.querySelectorAll("script[src]"),
      function (s) {
        return s.getAttribute("src").split("?")[0].replace(/^(\.\.\/)+/, "") === "data/" + file;
      })[0];
    return tag ? tag.getAttribute("src") : null;
  }

  function loadData(file, name, done) {
    if (global[name] !== undefined) { done(true); return; }
    var waiting = demanded[file];
    if (waiting) { waiting.push(done); return; }
    var src = onDemandSrc(file);
    if (!src) { done(false); return; }
    demanded[file] = [done];
    var script = doc.createElement("script");
    var finish = function (ok) {
      var calls = demanded[file] || [];
      // A failed fetch can be asked for again.
      demanded[file] = ok && global[name] !== undefined ? [] : null;
      calls.forEach(function (fn) { fn(ok && global[name] !== undefined); });
    };
    script.onload = function () { finish(true); };
    script.onerror = function () { finish(false); };
    script.src = src;
    doc.head.appendChild(script);
  }

  /* The people files (rule 94), each loaded once, one promise per file: it
   * resolves true once the file's people are in, false when it failed to
   * load or was refused (peopleProblem), and a failed file can be asked
   * for again. */
  var peopleLoads = {};
  function loadPeopleFile(file, ready) {
    if (ready()) return Promise.resolve(true);
    if (peopleLoads[file]) return peopleLoads[file];
    var src = onDemandSrc(file);
    if (!src) return Promise.resolve(false);
    var promise = new Promise(function (resolve) {
      var script = doc.createElement("script");
      script.onload = function () { resolve(ready()); };
      script.onerror = function () {
        if (script.parentNode) script.parentNode.removeChild(script);
        resolve(false);
      };
      script.src = src;
      doc.head.appendChild(script);
    }).then(function (ok) {
      if (!ok) delete peopleLoads[file];
      return ok;
    });
    peopleLoads[file] = promise;
    return promise;
  }

  /** A promise of whether *code*'s full records are in: at once where the
   *  page holds them, else once data/people/<st>.js has loaded. A page that
   *  names no such file - its people were given it whole - holds what it
   *  holds. */
  function loadPeople(code) {
    code = String(code || "").toUpperCase();
    var file = "people/" + code.toLowerCase() + ".js";
    if (!fullStates[code] && !indexIn && !onDemandSrc(file)) {
      return Promise.resolve(people().some(function (p) { return p.state === code; }));
    }
    return loadPeopleFile(file, function () { return !!fullStates[code]; });
  }

  /** A promise of whether everyone's cards are in (data/people/index.js):
   *  where a page holds one state's people, it finds anyone else's state. */
  function loadIndex() {
    return loadPeopleFile("people/index.js", function () { return indexIn; });
  }

  /** A promise of the person *id* names (an FEC id they were merged from
   *  among them), held whole; null where no profile has that id. Rejects
   *  when a file it needed did not load. */
  function loadPerson(id) {
    var item = byId(id);
    if (item && isFull(item)) return Promise.resolve(item);
    var found = item ? Promise.resolve(true) : indexIn ? Promise.resolve(false) : loadIndex();
    return found.then(function (ok) {
      var person = byId(id);
      if (!person) {
        if (!item && !indexIn && !ok && onDemandSrc("people/index.js")) {
          throw new Error("the index of profiles did not load");
        }
        return null;
      }
      return loadPeople(person.state).then(function (whole) {
        var again = byId(id);
        if (!whole || !isFull(again)) {
          throw new Error(KYC.stateName(person.state) + "'s profiles did not load");
        }
        return again;
      });
    });
  }

  function debounce(fn, wait) {
    var timer;
    return function () {
      var args = arguments;
      var self = this;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(self, args); }, wait || 150);
    };
  }

  /** Parse a district label for sorting. Non-districts sort last. */
  function districtOrder(item) {
    if (item.districtNum !== null && item.districtNum !== undefined) {
      return item.districtNum;
    }
    var match = String(item.district || "").match(/\d+/);
    return match ? parseInt(match[0], 10) : 999;
  }

  /* ================================================================ shell */

  function meta() {
    return global.kycBuildMeta || {};
  }

  /** True once the Congress this cycle elects is sitting: the cycle's
   *  races are then a record of what happened, and no longer the next
   *  election for any seat (kyc/cycle.phase, from the data). */
  function recordPhase() {
    return (meta().election || {}).phase === "record";
  }

  /* ================================================================ states */

  /** "TX" -> "Texas", from the build metadata (one table, in kyc/pages.py). */
  function stateName(code) {
    var states = meta().states || {};
    return (states[code] && states[code].name) || code;
  }

  /** Where the page for a state lives, relative to the current page. The
   *  state pages sit one directory down, so they reach everything through
   *  "../"; the root pages declare no prefix. */
  function siteRoot() {
    return (doc.body && doc.body.getAttribute("data-root")) || "";
  }

  function stateUrl(code) {
    return siteRoot() + "states/" + String(code).toLowerCase() + ".html";
  }

  /* ---------------------------------------------------------------- share */

  /** The address of a profile's or a race's share page (rule 96), whole:
   *  "https://host/p/<id>.html". A crawler drops the "#/profile/<id>" a
   *  view lives behind, so a link to the view unfurled as the home page's
   *  card; the share page carries the person's own. *kind* "race" or
   *  "profile". */
  function shareUrl(kind, id) {
    var path = siteRoot() + (kind === "race" ? "r/" : "p/") + encodeURIComponent(id) + ".html";
    try {
      return new URL(path, global.location.href).href;
    } catch (e) {
      return path;
    }
  }

  /** Share or copy *url* from *button*: a phone's share sheet; else the
   *  clipboard; and where the clipboard is missing or refuses (an in-app
   *  browser, a page not served over HTTPS), a read-only field after the
   *  button, its text selected, that says to copy it. The handler did
   *  nothing at all there (TECH-09). The sheet only where the pointer is a
   *  finger: desktop Chrome, Edge and Safari have one too, and a button
   *  that says "Copy link" opened it and copied nothing (PR #121 review). */
  function shareLink(button, url, title) {
    var nav = global.navigator || {};
    // What the button says at rest, kept once: read again on a second click
    // within the "Copied" moment, it was "Copied", and stayed so for good.
    if (!button.hasAttribute("data-label")) button.setAttribute("data-label", button.innerHTML);
    var said = function () {
      button.innerHTML = icon("check") + " Copied";
      clearTimeout(button._kycCopied);
      button._kycCopied = setTimeout(function () {
        button.innerHTML = button.getAttribute("data-label");
      }, 1800);
    };
    var field = function () { showShareField(button, url); };
    var copy = function () {
      if (!nav.clipboard || typeof nav.clipboard.writeText !== "function") return field();
      var done;
      try {
        done = nav.clipboard.writeText(url);
      } catch (e) {
        return field();
      }
      Promise.resolve(done).then(said, field);
    };
    if (typeof nav.share === "function" && touchFirst()) {
      var shared;
      try {
        shared = nav.share({ title: title || doc.title, url: url });
      } catch (e) {
        return copy();
      }
      // Closing the sheet is the reader's answer, not a failure to share.
      Promise.resolve(shared).then(function () {}, function (err) {
        if (!err || err.name !== "AbortError") copy();
      });
      return;
    }
    copy();
  }

  /** True where the main pointer is a finger (a phone or a tablet). */
  function touchFirst() {
    try {
      return !!(global.matchMedia && global.matchMedia("(pointer: coarse)").matches);
    } catch (e) {
      return false;
    }
  }

  function showShareField(button, url) {
    var next = button.nextElementSibling;
    var box = next && next.classList.contains("share-field") ? next : null;
    if (!box) {
      box = doc.createElement("span");
      box.className = "share-field";
      box.setAttribute("role", "status");
      box.innerHTML = '<label>Copy this link: <input type="text" class="input share-field-input" ' +
        'readonly spellcheck="false"></label>';
      button.insertAdjacentElement("afterend", box);
    }
    var input = box.querySelector("input");
    input.value = url;
    input.focus();
    input.select();
  }

  /** Take away the field showShareField left after *button*: a dialog
   *  opened on someone else must not offer the last person's link. */
  function clearShareField(button) {
    var next = button && button.nextElementSibling;
    if (next && next.classList.contains("share-field")) next.parentNode.removeChild(next);
  }

  /* The last state a reader looked at, so the sidebar can offer it back -
   * a per-viewer convenience, kept in this browser only. */
  var STATE_KEY = "kycState";

  function rememberState(code) {
    try { localStorage.setItem(STATE_KEY, code); } catch (e) { /* private mode */ }
  }

  function rememberedState() {
    try { return localStorage.getItem(STATE_KEY) || ""; } catch (e) { return ""; }
  }

  function renderRememberedState() {
    var slot = doc.getElementById("yourState");
    if (!slot) return;
    var code = rememberedState();
    var states = meta().states || {};
    if (!code || !states[code]) { slot.hidden = true; return; }
    slot.hidden = false;
    slot.innerHTML = '<a class="nav-link" href="' + escapeAttr(stateUrl(code)) + '">' +
      icon("pin") + " " + escapeHtml(states[code].name) + "</a>";
  }

  /** Fill the chamber-balance readouts from the build metadata.
   *
   *  These were literal text in both sidebars ("53 R | 47 D/I", "35", "435")
   *  plus a copy-pasted counting function per page. They are counted in
   *  kyc/summary.py now, from the same rosters the grid renders. */
  /** 120 -> "120th". */
  function ordinal(n) {
    var tens = n % 100;
    var suffix = tens >= 10 && tens <= 20 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" })[n % 10] || "th";
    return n + suffix;
  }

  function renderSummary() {
    var info = meta();
    // Which Congress the membership is of, from the data (kyc/summary.py):
    // the pages carry "U.S. Congress" until it is known, never a number.
    if (info.congress) {
      Array.prototype.forEach.call(doc.querySelectorAll("[data-congress]"), function (el) {
        el.textContent = ordinal(info.congress) + " Congress";
      });
    }
    if (!info.senate) return;

    var pill = function (count, cls, label) {
      return count
        ? '<span class="' + cls + '">' + count + " " + label + "</span>"
        : "";
    };
    var join = function (parts) {
      return parts.filter(Boolean).join('<span class="sep">/</span>');
    };

    var set = function (id, html) {
      var el = doc.getElementById(id);
      if (el) el.innerHTML = html;
    };

    // Independents are counted separately here and on the map, rather than
    // folded into "D/I". Which party an independent caucuses with is a real
    // fact, but it is not in the rosters, so the site does not assert it.
    set("senateBalance", join([
      pill(info.senate.R, "party-r", "R"),
      pill(info.senate.D, "party-d", "D"),
      pill(info.senate.I, "party-i", "I"),
      pill(info.senate.vacant, "party-vacant", "Vacant"),
    ]));

    set("houseBalance", join([
      pill(info.house.R, "party-r", "R"),
      pill(info.house.D, "party-d", "D"),
      pill(info.house.I, "party-i", "I"),
      pill(info.house.vacant, "party-vacant", "Vacant"),
    ]));

    // On a state's own pages, that state's delegation, counted the same way
    // and drawn in the same colours. D.C. and the territories have no
    // senators, so no Senate line.
    var slot = doc.getElementById("stateBalance");
    var code = doc.body && doc.body.getAttribute("data-state");
    var mine = code && info.states && info.states[code];
    if (slot && mine && mine.balance) {
      var line = function (label, counts) {
        return '<div class="balance-label">' + label + "</div>" +
          '<div class="balance">' + join([
            pill(counts.R, "party-r", "R"),
            pill(counts.D, "party-d", "D"),
            pill(counts.I, "party-i", "I"),
            pill(counts.vacant, "party-vacant", "Vacant"),
          ]) + "</div>";
      };
      slot.innerHTML = '<h2 class="sidebar-heading">' + escapeHtml(mine.name) + "</h2>" +
        (mine.senators ? line("Senate", mine.balance.senate) : "") +
        line("House", mine.balance.house);
      slot.hidden = false;
    }

    var election = info.election || {};
    var defending = election.senateDefending || {};
    set("senateSeatsUp", String(election.senateSeatsUp || 0));
    set("houseSeatsUp", String(election.houseSeatsUp || 0));
    set("senateDefending", join([
      pill(defending.D, "party-d", "D"),
      pill(defending.I, "party-i", "I"),
      pill(defending.R, "party-r", "R"),
    ]));

    var challengers = doc.getElementById("challengerCount");
    if (challengers) {
      var running = election.challengersOnBallot;
      // Open-seat candidates are nobody's challengers: the sidebar called
      // them "Challengers on the ballot" after the state strips stopped
      // (RACES-14). The two rows sum to the race headers' count (rule 73).
      var open = election.openCandidates || 0;
      challengers.textContent = String(
        running !== undefined ? running - open : (election.challengers || 0)
      );
      var openRow = doc.getElementById("openCandidateCount");
      if (openRow) openRow.textContent = String(open);
      // The same count as every race header: everyone on the ballot but a
      // member running for the seat they hold, profile or not.
      if (running !== undefined) {
        challengers.title = "Everyone on the 2026 ballot for a seat whose holder is running for " +
          "it, except that member. With the " + open + " candidates for open seats, " + running +
          " people are on the ballot besides members running for the seat they hold: " +
          (election.challengersWithProfile !== undefined
            ? election.challengersWithProfile + " with a profile here" +
              (election.renumbered ? " (" + election.renumbered + " of them members running " +
                "under a new district number)" : "") + ", " +
              election.challengersUnprofiled + " named on Wikipedia's results pages with no FEC " +
              "filing over $5,000"
            : running + " in all") + ".";
        // The same split as page text: a title is a hover a phone and a
        // keyboard never show, and the Challengers chip counts profiles
        // only (GRID-12).
        var split = doc.getElementById("challengerSplit");
        if (split && election.challengersWithProfile !== undefined) {
          split.textContent = "Of the " + running.toLocaleString() + " in these two rows, " +
            election.challengersWithProfile.toLocaleString() + " have a profile here; " +
            election.challengersUnprofiled.toLocaleString() + " are named by the published " +
            "results with no FEC filing over $5,000, so have none.";
          split.hidden = false;
        }
      }
    }
  }

  /* The sidebar's "Jump to" list, on every page that carries one. It lived
   * in the state pages' module, so the district maps - the same sidebar, a
   * different module - showed an empty list. On a district map it goes to
   * that state's map; anywhere else, to the state's page. */
  function initJump() {
    var select = doc.getElementById("stateJump");
    if (!select || select.getAttribute("data-wired")) return;
    select.setAttribute("data-wired", "true");
    var states = meta().states || {};
    var maps = meta().districtMaps || {};
    var here = (doc.body && doc.body.getAttribute("data-state")) || "";
    var onMaps = doc.body && doc.body.getAttribute("data-page") === "districts";
    // The guide's pages load no build metadata, so the build writes their
    // list into the page; it still needs its listener.
    var written = select.options.length > 1;
    if (!written) Object.keys(states).sort(function (a, b) {
      return states[a].name.localeCompare(states[b].name);
    }).forEach(function (code) {
      var option = doc.createElement("option");
      option.value = code;
      option.textContent = states[code].name + " (" + code + ")";
      if (code === here) option.selected = true;
      select.appendChild(option);
    });
    // A guide map picks the state on its own map instead (kyc-guide.js).
    if (select.getAttribute("data-jump") === "map") return;
    // A page of a kind every state has (a legislature) jumps to that state's.
    var pattern = select.getAttribute("data-jump-to");
    select.addEventListener("change", function () {
      var code = select.value;
      if (!code) return;
      if (pattern) {
        global.location.href = siteRoot() + pattern.replace("{code}", code.toLowerCase());
        return;
      }
      global.location.href = onMaps && maps[code] ? siteRoot() + maps[code].page : stateUrl(code);
    });
  }

  /* The drawer's close, once initShell has wired it. */
  var drawerClose = null;

  /** Close the drawer on a narrow screen, if it is open, then run *then*.
   *  Closing steps back off the history entry the drawer pushed, and a
   *  browser restores that entry's scroll position as it does: anything
   *  that scrolls the page (a link caught to reveal a panel on this page)
   *  waits for that step, or the restore undoes it. */
  function closeDrawer(then) {
    var open = !!(doc.body && doc.body.classList.contains("sidebar-open"));
    var stepping = open && !!(history.state && history.state.kycDrawer);
    if (stepping && then) {
      var done = false;
      var run = function () {
        if (done) return;
        done = true;
        global.removeEventListener("popstate", run);
        global.setTimeout(then, 0);
      };
      global.addEventListener("popstate", run);
      // A browser that never reports the step still gets there.
      global.setTimeout(run, 400);
    }
    if (open && drawerClose) drawerClose();
    if (!stepping && then) then();
  }

  function initShell() {
    if (doc.body && !doc.getElementById("kyc-sprite")) {
      var holder = doc.createElement("div");
      holder.id = "kyc-sprite";
      holder.innerHTML = iconSprite();
      doc.body.insertBefore(holder, doc.body.firstChild);
    }

    // Off-canvas sidebar for narrow screens.
    var toggle = doc.querySelector(".sidebar-toggle");
    var scrim = doc.querySelector(".sidebar-scrim");
    var sidebar = doc.getElementById("sidebar");
    var closeSidebar = function (fromHistory) {
      if (!doc.body.classList.contains("sidebar-open")) return;
      doc.body.classList.remove("sidebar-open");
      // Closed by a tap rather than by Back: take its history entry off
      // again. A pick in the drawer has already replaced that entry with
      // the address it chose, which is then the step Back undoes.
      if (fromHistory !== true && history.state && history.state.kycDrawer) history.back();
      if (toggle) {
        toggle.setAttribute("aria-expanded", "false");
        // Back to the button that opened it, unless the reader has already
        // moved on to something outside the drawer.
        if (!doc.activeElement || doc.activeElement === doc.body ||
            (sidebar && sidebar.contains(doc.activeElement))) toggle.focus();
      }
    };
    drawerClose = closeSidebar;
    if (toggle) {
      toggle.addEventListener("click", function () {
        if (doc.body.classList.contains("sidebar-open")) return closeSidebar();
        doc.body.classList.add("sidebar-open");
        toggle.setAttribute("aria-expanded", "true");
        // On Android the back gesture is expected to close an open drawer,
        // not leave the page under it: give it an entry to step back from.
        // Same address, so the router does not treat it as a navigation.
        if (!(history.state && history.state.kycDrawer)) {
          history.pushState({ kycDrawer: true }, "", global.location.href);
        }
        var first = sidebar && sidebar.querySelector(FOCUSABLE);
        if (first) first.focus({ preventScroll: true });
      });
    }
    if (scrim) scrim.addEventListener("click", closeSidebar);
    global.addEventListener("popstate", function () {
      if (!(history.state && history.state.kycDrawer)) closeSidebar(true);
    });
    doc.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeSidebar();
    });
    // Picking a state in the drawer on a phone left the drawer open over
    // what was picked; the reader had to find the dimmed strip to see it.
    if (sidebar) {
      sidebar.addEventListener("change", function (event) {
        // "Jump to" leaves the page; stepping back now would cancel that.
        if (event.target.matches("select") && event.target.id !== "stateJump") closeSidebar();
      });
    }

    // Theme menu.
    var themeButton = doc.getElementById("themeButton");
    var themePanel = doc.getElementById("themePanel");
    if (themeButton && themePanel) {
      createMenu(themeButton, themePanel);
      var markChecked = function () {
        var active = currentTheme();
        Array.prototype.forEach.call(
          themePanel.querySelectorAll("[data-theme-option]"),
          function (item) {
            item.setAttribute(
              "aria-checked",
              String(item.getAttribute("data-theme-option") === active)
            );
          }
        );
      };
      themePanel.addEventListener("click", function (event) {
        var item = event.target.closest("[data-theme-option]");
        if (!item) return;
        setTheme(item.getAttribute("data-theme-option"));
        markChecked();
      });
      markChecked();
    }

    // A placeholder written for a desktop box read "Search na" on a phone.
    // It follows the width, so folding or unfolding a Fold updates it.
    if (global.matchMedia) {
      var compact = global.matchMedia("(max-width: 760px)");
      var placeholders = function () {
        Array.prototype.forEach.call(doc.querySelectorAll("[data-placeholder-short]"), function (input) {
          if (!input.hasAttribute("data-placeholder-long")) {
            input.setAttribute("data-placeholder-long", input.getAttribute("placeholder") || "");
          }
          input.setAttribute("placeholder", input.getAttribute(
            compact.matches ? "data-placeholder-short" : "data-placeholder-long"));
        });
      };
      placeholders();
      if (compact.addEventListener) compact.addEventListener("change", placeholders);
    }

    renderSummary();
    renderRememberedState();
    initJump();
    var here = doc.body && doc.body.getAttribute("data-state");
    if (here) rememberState(here);

    // "/" focuses the search box from anywhere, as it does on YouTube and
    // GitHub; Escape hands focus back and clears an empty-result search.
    var search = doc.querySelector('input[type="search"]');
    if (search) {
      // Name suggestions, built once on first focus so 2,500 options never
      // sit in the DOM of a page nobody searches.
      search.addEventListener("focus", function build() {
        search.removeEventListener("focus", build);
        var everyone = people();
        if (!everyone.length || doc.getElementById("kycNames")) return;
        var list = doc.createElement("datalist");
        list.id = "kycNames";
        // Each option's value is the display name; a member's aliases ride in
        // its label, which browsers show beside it and match typing against,
        // so "Jim Clyburn" offers "James Clyburn".
        var names = {};
        everyone.forEach(function (p) {
          if (p.raceStatus && p.isCandidate && !NOVEMBER[p.raceStatus] &&
              p.raceStatus !== "advanced") return;  // off-ballot filers would swamp the list
          var known = names[p.name] || (names[p.name] = []);
          (p.aliases || []).forEach(function (alias) {
            if (known.indexOf(alias) === -1) known.push(alias);
          });
        });
        list.innerHTML = Object.keys(names).sort().map(function (name) {
          var label = names[name].length ? ' label="' + escapeAttr(names[name].join(" · ")) + '"' : "";
          return '<option value="' + escapeAttr(name) + '"' + label + '></option>';
        }).join("");
        doc.body.appendChild(list);
        search.setAttribute("list", "kycNames");
      });
      doc.addEventListener("keydown", function (event) {
        if (event.key !== "/" || event.altKey || event.ctrlKey || event.metaKey) return;
        var target = event.target;
        var typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" ||
          target.isContentEditable);
        if (typing) return;
        event.preventDefault();
        search.focus();
        search.select();
      });
      search.addEventListener("keydown", function (event) {
        if (event.key === "Escape") search.blur();
      });
    }

    // The freshness stamps, from the build metadata: the footer's, and the
    // sidebar's (the grid's infinite scroll keeps pushing its footer away),
    // and when the results pages were last read.
    var built = meta().built ? new Date(meta().built) : null;
    if (built && !isNaN(built)) {
      var stamps = [doc.getElementById("buildStamp")].concat(
        Array.prototype.slice.call(doc.querySelectorAll("time[data-built]")));
      stamps.forEach(function (stamp) {
        if (!stamp) return;
        stamp.textContent = dateWords(localDay(built));
        stamp.setAttribute("datetime", built.toISOString());
      });
    }
    var resultsRead = (meta().election || {}).resultsAsOf;
    Array.prototype.forEach.call(doc.querySelectorAll("time[data-results-as-of]"), function (el) {
      if (!resultsRead) return;
      el.textContent = dateWords(resultsRead);
      el.setAttribute("datetime", resultsRead);
      var wrap = el.closest("[data-results-read]");
      if (wrap) wrap.hidden = false;
    });

    // The header's search on a page with no grid: the words go to the
    // grid's own search, on the home page.
    Array.prototype.forEach.call(doc.querySelectorAll("form[data-site-search]"), function (form) {
      form.addEventListener("submit", function (event) {
        var input = form.querySelector('input[name="q"]');
        var words = input ? input.value.trim() : "";
        event.preventDefault();
        global.location.href = siteRoot() + "index.html" +
          (words ? "#/?q=" + encodeURIComponent(words) : "");
      });
    });
    initReportLinks();

    var countdown = doc.getElementById("electionCountdown");
    if (countdown) {
      var status = electionStatus((meta().election || {}).year || 2026);
      countdown.textContent = status.label;
      countdown.setAttribute("datetime", status.iso);
    }

    initPortraitFallback();
  }

  function ready(fn) {
    if (doc.readyState === "loading") {
      doc.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  /* Applied before first paint so the page never flashes the wrong theme. */
  initTheme();
  ready(initShell);

  /* An address that carries a ZIP code (the Your ballot page's
   * "#/?zip=30303") will draw an answer once the data has loaded: marked
   * now, before first paint, so the page holds the answer's room and the
   * footer does not jump down under the reader when it comes (PR #115
   * review: a layout shift of 0.15-0.28 on a throttled phone). The page's
   * module takes the mark off when its answer is drawn. */
  try {
    if (/[?&]zip=\d{5}\b/.test(String(global.location.hash || "")) && doc.documentElement) {
      doc.documentElement.classList.add("has-zip");
    }
  } catch (e) { /* no location: nothing to hold */ }

  /* ---------------------------------------------------------- offices held */

  /* The public offices a person has held (kyc/history.py): service in
   * Congress from congress-legislators, every other office from Wikidata
   * where the person's own Wikipedia article gives the same office the same
   * years. One renderer for the profile dialog, the officials' dialog and
   * the grid's cards (rule 12). Years only: that is as far as the two
   * sources are compared. */

  function heldYears(row) {
    if (row.current || !row.to) return "since " + row.from;
    return row.to === row.from ? String(row.from) : row.from + "\u2013" + row.to;
  }

  /** Where an office was held: "Vermont, at large", "California's 12th
   *  district", or the place and district Wikidata gives, unless the
   *  office's name already says it ("Governor of Florida"). */
  function heldPlace(row) {
    if (row.congress) {
      var state = row.where;
      if (row.district === undefined) return state;
      return row.district === 0 ? state + ", at large"
        : state + "\u2019s " + ordinal(row.district) + " district";
    }
    var parts = [];
    if (row.where) {
      // "Mayor of Burlington" in "Burlington, Vermont" says the rest only.
      var pieces = row.where.split(/,\s*/);
      var office = row.office.toLowerCase();
      if (office.indexOf(row.where.toLowerCase()) !== -1) pieces = [];
      else if (office.indexOf(pieces[0].toLowerCase()) !== -1) pieces = pieces.slice(1);
      if (pieces.length) parts.push(pieces.join(", "));
    }
    if (row.district) parts.push(row.district);
    return parts.join(" \u00b7 ");
  }

  function heldText(row) {
    var place = heldPlace(row);
    return row.office + (place ? ", " + place : "") + ", " + heldYears(row);
  }

  // Said in words on the page: a phone shows no tooltip (FEDERAL-20).
  var HELD_NOTES = {
    "year-off": ["years differ by one between Wikidata and Wikipedia; Wikidata\u2019s shown",
      "Wikidata and the person\u2019s Wikipedia article differ by a year here; the years " +
      "shown are Wikidata\u2019s."],
    start: ["end year from Wikipedia; Wikidata records none", "Wikidata records no end to " +
      "this office; the end year is the person\u2019s Wikipedia article\u2019s."],
  };

  /** The panel body for a record of offices held; *why* says, when there is
   *  no record, why this site has none (a claim about us, rule 19). */
  function officesHeld(record, why) {
    if (!record) {
      return '<p class="kyc-absent" title="' + escapeAttr(why || "") +
        '">No linked record of public offices</p>';
    }
    var rows = record.rows || [];
    // The list is what two sources agree on, not a full record: it says so
    // before it starts, or its heading reads as complete (an officer's
    // earlier office can be in their OGE filings and not here).
    var list = rows.length
      ? '<p class="held-scope faint">Only offices the sources below agree on; ' +
        "others may be missing.</p>" +
        '<ul class="held-list">' + rows.map(function (row) {
          var note = HELD_NOTES[row.agree];
          var place = heldPlace(row);
          return '<li class="held-row">' +
            '<span class="held-office">' + escapeHtml(row.office) + "</span>" +
            '<span class="held-years">' + escapeHtml(heldYears(row)) +
            (row.terms ? " \u00b7 " + row.terms + (row.terms === 1 ? " term" : " terms") : "") +
            "</span>" +
            (place ? '<span class="held-where">' + escapeHtml(place) + "</span>" : "") +
            (note ? '<span class="held-note" title="' + escapeAttr(note[1]) + '">' +
              escapeHtml(note[0]) + "</span>" : "") +
            "</li>";
        }).join("") + "</ul>"
      : '<p class="kyc-absent">None that Wikidata and the person\u2019s Wikipedia article ' +
        "both record</p>";
    var article = record.wikipedia
      ? '<a href="' + escapeAttr("https://en.wikipedia.org/wiki/" +
          encodeURIComponent(record.wikipedia.replace(/ /g, "_"))) +
        '" target="_blank" rel="noopener noreferrer">their Wikipedia article</a>'
      : "their Wikipedia article";
    var item = record.wikidata
      ? '<a href="' + escapeAttr("https://www.wikidata.org/wiki/" + record.wikidata) +
        '" target="_blank" rel="noopener noreferrer">Wikidata</a>'
      : "Wikidata";
    var withheld = record.withheld
      ? " " + record.withheld + (record.withheld === 1 ? " more is" : " more are") +
        " in Wikidata and not shown: the article does not give the same office the same years."
      : "";
    return list + '<p class="held-source">' +
      (rows.some(function (r) { return r.congress; })
        ? "Congress: the congress-legislators project. " : "") +
      "Other offices: " + item + ", where " + article +
      " gives the same office the same years." + escapeHtml(withheld) + "</p>";
  }

  /** The same record in a narrow column (the ballot comparison, GRID-17):
   *  each office with its place and years and the note the panel gives it,
   *  the first *limit* of them. One renderer of a row's words with the panel
   *  (rule 12): the comparison's own copy dropped the place, so a mayoralty
   *  read with no city. */
  function officesHeldShort(record, limit) {
    if (!record) return '<span class="kyc-absent">No linked record</span>';
    var rows = record.rows || [];
    if (!rows.length) return '<span class="kyc-absent">None the sources agree on</span>';
    limit = limit || rows.length;
    return '<ul class="compare-list">' + rows.slice(0, limit).map(function (row) {
      var note = HELD_NOTES[row.agree];
      var place = heldPlace(row);
      return "<li>" + escapeHtml(row.office) + (place ? ", " + escapeHtml(place) : "") +
        ' <span class="faint">' + escapeHtml(heldYears(row)) + "</span>" +
        (note ? ' <span class="held-note" title="' + escapeAttr(note[1]) + '">' +
          escapeHtml(note[0]) + "</span>" : "") + "</li>";
    }).join("") + (rows.length > limit ? '<li class="faint">and ' + (rows.length - limit) +
      " more on the profile</li>" : "") + "</ul>";
  }

  /** What a Cabinet office's holder is called, as the federal page and
   *  the guide both say it: their own title where it is not the office's
   *  ("Secretary of War" for the Secretary of Defense), else none, and
   *  whether the office's page says they are acting. */
  function holderRole(office) {
    var h = (office && office.holder) || {};
    return { title: h.title && h.title !== office.office ? h.title : "",
             acting: !!(h.page || {}).acting };
  }

  /* --------------------------------------------------------- seat strip */

  /* A legislative chamber as one square per seat. An area map gives a
   * chamber of dense city districts to the party of its rural ones:
   * Minnesota's House is 67 DFL to 66 Republican and its map is nearly all
   * red (audit 2026-10-17, STATEGOV-23, VISUALS-22). *c* is a chamber's
   * count as kyc/stategov.py makes it - {D, R, I, N, seats, listed} - for
   * the state page, the legislatures directory and the legislature page
   * alike, so the squares are the figures beside them (rule 73).
   * Republicans fill from the left and Democrats from the right, in the
   * order the state page's counts read ("27 R / 8 D"), everyone else
   * between; a seat with nobody listed is an empty outline, never "vacant"
   * (rule 51). A tick marks half the seats, where there are parties to
   * hold a majority: Nebraska's 49 nonpartisan seats have none. */
  var SEAT_KINDS = [["R", "seat-r", "Republican"], ["I", "seat-i", "independent or third-party"],
    ["N", "seat-n", "nonpartisan"], ["", "seat-none", "with nobody listed"],
    ["D", "seat-d", "Democratic"]];

  function seatUnlisted(c) { return Math.max(0, c.seats - (c.listed || 0)); }

  function seatPartisan(c) { return !!(c.D || c.R || c.I); }

  function seatStrip(c) {
    if (!c || !c.seats) return "";
    var unlisted = seatUnlisted(c);
    var rows = Math.max(1, Math.ceil(c.seats / 50));
    var cols = Math.ceil(c.seats / rows);
    var cells = [];
    var said = [];
    SEAT_KINDS.forEach(function (kind) {
      var n = kind[0] ? (c[kind[0]] || 0) : unlisted;
      if (n) said.push(n + " " + kind[2]);
      for (var i = 0; i < n; i++) cells.push('<span class="seat ' + kind[1] + '"></span>');
    });
    var partisan = seatPartisan(c);
    var half = ((c.seats / 2) / rows / cols * 100).toFixed(2);
    var label = c.seats + " seats, one square each: " + said.join(", ") + "." +
      (partisan ? " " + (Math.floor(c.seats / 2) + 1) + " seats are more than half." : "");
    return '<div class="seat-strip" role="img" aria-label="' + escapeAttr(label) + '" title="' +
      escapeAttr(label) + '" style="--seat-cols:' + cols + ";--seat-rows:" + rows + '">' +
      cells.join("") + (partisan ? '<span class="seat-half" aria-hidden="true" style="left:' + half +
      '%"></span>' : "") + "</div>";
  }

  /** One line that says how to read the strips of *chambers*: only what
   *  they draw (an outline only where a seat has nobody listed, the tick
   *  only where parties hold seats). Shown once under a state's chambers,
   *  once over the legislatures directory, and under each legislature
   *  page's strip (PR #96 review: the key was only in a tooltip). */
  function seatKey(chambers) {
    var list = (chambers || []).filter(function (c) { return c && c.seats; });
    if (!list.length) return "";
    var partisan = list.some(seatPartisan);
    var unlisted = list.some(function (c) { return seatUnlisted(c) > 0; });
    var text = "Each square is a seat" + (partisan ? ": Republicans from the left, Democrats from " +
      "the right, others between" : "") + "." +
      (unlisted ? " An outlined square is a seat with nobody listed." : "") +
      (partisan ? " The tick marks half the seats." : "");
    return '<p class="seat-key">' + escapeHtml(text) + "</p>";
  }

  global.KYC = {
    // theme
    setTheme: setTheme,
    currentTheme: currentTheme,
    onThemeChange: onThemeChange,
    // rendering
    icon: icon,
    escapeHtml: escapeHtml,
    escapeAttr: escapeAttr,
    renderField: renderField,
    officesHeld: officesHeld,
    officesHeldShort: officesHeldShort,
    holderRole: holderRole,
    heldText: heldText,
    heldYears: heldYears,
    sourceBadge: sourceBadge,
    financePeriod: financePeriod,
    filedAhead: filedAhead,
    monthYear: monthYear,
    dayMonthYear: dayMonthYear,
    vacancyNote: vacancyNote,
    vacancyOf: vacancyOf,
    possessive: possessive,
    hasValue: hasValue,
    moneyAmount: moneyAmount,
    moneyShort: moneyShort,
    platformItems: platformItems,
    partyKey: partyKey,
    partyClass: partyClass,
    partyAbbr: partyAbbr,
    hatchDefs: hatchDefs,
    hatchVars: hatchVars,
    svgFill: svgFill,
    swatchFill: swatchFill,
    fillInk: fillInk,
    scrollBehavior: scrollBehavior,
    seatStrip: seatStrip,
    seatKey: seatKey,
    // data
    byId: byId,
    runsElsewhere: runsElsewhere,
    contestStatus: contestStatus,
    ballotLine: ballotLine,
    ballotLineSuffix: ballotLineSuffix,
    raceStatus: raceStatus,
    raceStatusOf: raceStatusOf,
    standing: standing,
    otherCampaign: otherCampaign,
    contestLine: contestLine,
    otherOffice: otherOffice,
    otherOfficeBadge: otherOfficeBadge,
    racePosition: racePosition,
    RACE_ORDER: RACE_ORDER,
    RACE_ORDER_PLAIN: RACE_ORDER_PLAIN,
    raceOrderNote: raceOrderNote,
    seated: seated,
    formerText: formerText,
    ordinal: ordinal,
    ballotSource: ballotSource,
    resultsSourceHtml: resultsSourceHtml,
    dateWords: dateWords,
    localDay: localDay,
    REPO_URL: REPO_URL,
    reportUrl: reportUrl,
    offBallot: offBallot,
    onNovemberBallot: onNovemberBallot,
    stillRunning: stillRunning,
    meta: meta,
    recordPhase: recordPhase,
    portraitSrc: portraitSrc,
    portraitSrcset: portraitSrcset,
    portraitAttrs: portraitAttrs,
    hasPortrait: hasPortrait,
    monogram: monogram,
    portraitThumb: portraitThumb,
    setPortrait: setPortrait,
    shownPhotoCredit: shownPhotoCredit,
    cappedSrcset: cappedSrcset,
    photoCreditHtml: photoCreditHtml,
    photoSrc: photoSrc,
    photoHref: photoHref,
    photoAttrs: photoAttrs,
    copyCredit: copyCredit,
    copyOf: copyOf,
    weightWords: weightWords,
    retryOriginal: retryOriginal,
    handleImageFallback: handleImageFallback,
    SILHOUETTE: SILHOUETTE,
    // behaviour
    createModal: createModal,
    createMenu: createMenu,
    closeDrawer: closeDrawer,
    router: router,
    electionStatus: electionStatus,
    ageOf: ageOf,
    generalElectionDay: generalElectionDay,
    matchesQuery: matchesQuery,
    queryScore: queryScore,
    queryPlace: function (query) { return compileQuery(query).place; },
    queryLabel: function (query) { return compileQuery(query).label; },
    queryNote: function (query) { return compileQuery(query).note; },
    searchSnippet: searchSnippet,
    searchFold: searchFold,
    nameScore: nameScore,
    stateNamed: stateNamed,
    stateAbbreviation: stateAbbreviation,
    loadData: loadData,
    people: people,
    races: races,
    isFull: isFull,
    peopleFull: peopleFull,
    peopleHeld: peopleHeld,
    peopleProblem: peopleProblem,
    loadPeople: loadPeople,
    loadIndex: loadIndex,
    loadPerson: loadPerson,
    indexHeld: function () { return indexIn; },
    canLoadPeople: function (file) { return !!onDemandSrc(file); },
    raceStatusLegend: raceStatusLegend,
    foldText: foldText,
    searchIndex: searchIndex,
    districtOrder: districtOrder,
    debounce: debounce,
    ready: ready,
    // states
    stateName: stateName,
    stateUrl: stateUrl,
    shareUrl: shareUrl,
    shareLink: shareLink,
    clearShareField: clearShareField,
    siteRoot: siteRoot,
    rememberState: rememberState,
    rememberedState: rememberedState,
    renderRememberedState: renderRememberedState,
  };
})(window);

/* ================================================================ charts
 *
 * Pictures of figures the build already counts (audit 2026-10-17): the
 * balance of power with the seats on the 2026 ballot (VISUALS-21), the
 * House as one square per seat (VISUALS-27), a state's districts as a
 * navigator, and the states as a grid of links (VISUALS-35). Every one is
 * page text and plain boxes - no SVG text (rule 46) and no script from
 * anywhere else - coloured from the theme's tokens, and placed from
 * figures the pipeline computed (kyc/summary.py, kyc/tiles.py), never
 * worked out again here. */
(function (global) {
  "use strict";

  var KYC = global.KYC;
  var doc = global.document;
  if (!KYC) return;
  var esc = KYC.escapeHtml;
  var attr = KYC.escapeAttr;

  var WORDS = {
    R: ["Republican", "Republicans"], D: ["Democratic", "Democrats"],
    I: ["independent", "Independents"],
  };

  function share(n, total) {
    return (100 * n / total).toFixed(3) + "%";
  }

  function past() {
    return KYC.electionStatus(2026).phase === "post-election";
  }

  /* ------------------------------------------------- the balance of power */

  /** One chamber's seats as one bar (VISUALS-21): Republicans from the
   *  left, Democrats from the right, independents and empty seats between,
   *  as the legislatures' seat strips run (KYC.seatStrip). A Senate seat on
   *  the November 3 ballot is dotted in its holder's colour - dotted, not
   *  hatched, because the map drawn under the bar hatches "no race",
   *  "none" and a split delegation (rule 88); every House seat is on it,
   *  which dots over the whole bar would not tell anyone, so the caption
   *  says so instead. A tick marks half the seats. An independent is never
   *  folded into either party (rule: the rosters do not say whom they
   *  caucus with). Nothing is dotted once the Congress the cycle elects
   *  sits (summary.py sends no "up" then). The compact form prints the
   *  counts when asked (opts.counts): the map has no sidebar above it, and
   *  a phone has no hover to read the track's title. */
  function balanceBar(chamber, opts) {
    opts = opts || {};
    var info = KYC.meta();
    var c = info[chamber];
    if (!c) return "";
    var seats = chamber === "senate" ? 100 : (c.seats || 435);
    var held = (c.R || 0) + (c.D || 0) + (c.I || 0);
    var vacant = Math.max(0, seats - held);
    var up = chamber === "senate" ? c.up : null;
    var parts = [];
    var add = function (key, n, hatched) {
      if (n > 0) parts.push({ key: key, n: n, up: hatched });
    };
    var upOf = function (key) { return up ? up[key] || 0 : 0; };
    add("r", (c.R || 0) - upOf("R"), false);
    add("r", upOf("R"), true);
    add("i", (c.I || 0) - upOf("I"), false);
    add("i", upOf("I"), true);
    add("vacant", vacant, false);
    add("d", upOf("D"), true);
    add("d", (c.D || 0) - upOf("D"), false);
    var name = chamber === "senate" ? "Senate" : "House";
    var verb = past() ? "were" : "are";
    var counted = [["R", c.R], ["I", c.I], ["D", c.D]].filter(function (p) { return p[1]; })
      .map(function (p) {
        return p[1] + " " + WORDS[p[0]][p[1] === 1 ? 0 : 1] +
          (upOf(p[0]) ? " (" + upOf(p[0]) + " of their seats " + verb + " on the Nov 3, 2026 ballot)" : "");
      });
    if (vacant) counted.push(vacant + " vacant");
    var half = chamber === "senate"
      ? "51 seats is a majority; at 50 each, the Vice President breaks a tie"
      : (Math.floor(seats / 2) + 1) + " of " + seats + " seats is a majority";
    var spoken = "The " + name + ": " + counted.join(", ") + ". The tick marks half the seats: " + half + ".";
    var bar = parts.map(function (p) {
      return '<span class="bb-seg bb-' + p.key + (p.up ? " bb-up" : "") + '" style="width:' +
        share(p.n, seats) + '"></span>';
    }).join("");
    var key = [["R", "r"], ["I", "i"], ["D", "d"]].filter(function (p) { return c[p[0]]; })
      .map(function (p) {
        var n = c[p[0]];
        return '<li><span class="bb-swatch bb-' + p[1] + '" aria-hidden="true"></span>' +
          esc(WORDS[p[0]][n === 1 ? 0 : 1].replace(/^./, function (ch) { return ch.toUpperCase(); })) +
          " <strong>" + n + "</strong>" +
          (up && upOf(p[0]) ? ' <span class="bb-faint">' + upOf(p[0]) + " up</span>" : "") + "</li>";
      });
    if (vacant) {
      key.push('<li><span class="bb-swatch bb-vacant" aria-hidden="true"></span>Vacant <strong>' +
        vacant + "</strong></li>");
    }
    var ballot = up
      ? '<li class="bb-ballot"><span class="bb-swatch bb-up bb-neutral" aria-hidden="true"></span>' +
        "Dotted: a seat on the Nov 3, 2026 ballot</li>"
      : chamber === "house" && (info.election || {}).phase === "campaign"
        ? '<li class="bb-ballot">Every House seat ' + (past() ? "was" : "is") +
          " on the Nov 3, 2026 ballot</li>" : "";
    var track = '<div class="bb-track" role="img" aria-label="' + attr(spoken) + '" title="' + attr(spoken) +
      '">' + bar + '<span class="bb-half" aria-hidden="true"></span></div>';
    if (opts.compact) {
      // Under the sidebar's counts, which already name each party in its
      // colour: only what the bar adds, in one line.
      var dotted = up ? [["R", "R"], ["I", "I"], ["D", "D"]].filter(function (p) { return upOf(p[0]); })
        .map(function (p) { return upOf(p[0]) + " " + p[1]; }) : [];
      // Where nothing above the bar names the parts (the map), the counts
      // come first, each in its party's text colour, in the bar's order.
      var counts = !opts.counts ? "" : [["R", "r"], ["I", "i"], ["D", "d"]].filter(function (p) { return c[p[0]]; })
        .map(function (p) {
          return '<strong class="party-' + p[1] + '">' + c[p[0]] + " " + p[0] + "</strong>";
        }).concat(vacant ? ["<strong>" + vacant + " vacant</strong>"] : []).join(" · ");
      return '<figure class="balance-bar balance-bar-compact" data-chamber="' + attr(chamber) + '">' +
        (opts.title ? '<figcaption class="bb-title">' + esc(opts.title) + "</figcaption>" : "") + track +
        '<p class="bb-note">' + (counts ? '<span class="bb-counts">' + counts + ". </span>" : "") + (dotted.length
          ? '<span class="bb-swatch bb-up bb-neutral" aria-hidden="true"></span> Dotted: the ' +
            esc(dotted.join(", ")) + " seats " + (past() ? "that were " : "") + "on the Nov 3, 2026 ballot. "
          : chamber === "house" && (info.election || {}).phase === "campaign"
            ? "Every seat " + (past() ? "was" : "is") + " on the Nov 3, 2026 ballot. " : "") +
        "The tick marks half: " + (chamber === "senate" ? 51 : Math.floor(seats / 2) + 1) +
        " is a majority.</p></figure>";
    }
    return '<figure class="balance-bar" data-chamber="' + attr(chamber) + '">' +
      (opts.title ? '<figcaption class="bb-title">' + esc(opts.title) + "</figcaption>" : "") + track +
      '<ul class="bb-key">' + key.join("") + ballot + "</ul>" +
      '<p class="bb-note">The tick marks half the seats: ' + esc(half) + "." +
      (chamber === "house" && info.delegates
        ? " Voting seats only: the " + info.delegates + " delegates have no floor vote." : "") + "</p>" +
      "</figure>";
  }

  /* ------------------------------------------- the House, a square a seat */

  function houseLayout() {
    return KYC.meta().houseTiles || null;
  }

  /** The plan whose districts members sit for: the 2024 map until the
   *  Congress the 2026 election chose is seated, then the 2026 map. */
  function seatedCells(block) {
    return KYC.recordPhase() && block.cells2026 ? block.cells2026 : block.cells;
  }

  function seatedBySeat() {
    var out = {};
    KYC.people().forEach(function (p) {
      if (!KYC.seated(p) || String(p.chamber).indexOf("House") === -1) return;
      if (p.districtNum === null || p.districtNum === undefined) return;
      out[p.state + "-" + p.districtNum] = p;
    });
    return out;
  }

  function partyLetter(p) {
    var key = KYC.partyKey(p);
    return key === "d" || key === "r" ? key : "i";
  }

  /** The House as one square per voting seat, each state a button (a tap
   *  picks it, as on the map), its code above its block as page text. The
   *  layout is kyc/tiles.py's; the colour is whoever sits for the seat. */
  function houseTiles(opts) {
    opts = opts || {};
    var layout = houseLayout();
    if (!layout) return "";
    var who = seatedBySeat();
    var W = layout.width;
    var H = layout.height;
    var states = Object.keys(layout.states).sort();
    var html = states.map(function (code) {
      var b = layout.states[code];
      var gap = layout.gap || 0;
      var slot = Math.max(b.cols, layout.slot || 2);
      var reach = slot + gap;
      var left = b.x - (slot - b.cols) / 2 - gap / 2;
      var top = b.y - layout.band;
      var cells = seatedCells(b);
      var tally = { r: 0, d: 0, i: 0, vacant: 0 };
      var squares = Object.keys(cells).map(function (n) {
        var p = who[code + "-" + n];
        var kind = p ? partyLetter(p) : "vacant";
        tally[kind] += 1;
        var seat = code + (n === "0" ? " at large" : "-" + n);
        return '<span class="ht-seat ht-' + kind + '" style="grid-column:' + (cells[n][0] + 1) +
          ";grid-row:" + (cells[n][1] + 1) + '" title="' + attr(seat + ": " +
          (p ? p.name + " (" + p.party + ")" : "vacant")) + '"></span>';
      }).join("");
      var said = [["r", "Republican"], ["d", "Democratic"], ["i", "independent"], ["vacant", "vacant"]]
        .filter(function (k) { return tally[k[0]]; })
        .map(function (k) { return tally[k[0]] + " " + k[1]; });
      var total = Object.keys(cells).length;
      var label = KYC.stateName(code) + ": " + total + (total === 1 ? " seat, " : " seats, ") + said.join(", ");
      return '<button type="button" class="ht-state' + (opts.selected === code ? " is-selected" : "") +
        '" data-state="' + attr(code) + '" aria-pressed="' + String(opts.selected === code) +
        '" aria-label="' + attr(label) + '" style="left:' + share(left, W) + ";top:" + share(top, H) +
        ";width:" + share(reach, W) + ";height:" + share(layout.band + b.rows, H) + '">' +
        '<span class="ht-code" style="height:' + share(layout.band, layout.band + b.rows) + '">' +
        esc(code) + "</span>" +
        '<span class="ht-block" style="width:' + share(b.cols, reach) + ";height:" +
        share(b.rows, layout.band + b.rows) + ";grid-template-columns:repeat(" + b.cols +
        ",1fr);grid-template-rows:repeat(" + b.rows + ',1fr)">' + squares + "</span></button>";
    }).join("");
    return '<div class="house-tiles" style="aspect-ratio:' + W + " / " + H + ";--ht-ratio:" +
      (W / H).toFixed(4) + '">' + html + "</div>";
  }

  /** The key under the tiles: only the kinds some square is drawn in. */
  function houseTilesKey() {
    var layout = houseLayout();
    if (!layout) return "";
    var who = seatedBySeat();
    var seen = {};
    Object.keys(layout.states).forEach(function (code) {
      var cells = seatedCells(layout.states[code]);
      Object.keys(cells).forEach(function (n) {
        var p = who[code + "-" + n];
        seen[p ? partyLetter(p) : "vacant"] = true;
      });
    });
    return [["r", "Republican"], ["d", "Democratic"], ["i", "Independent"], ["vacant", "Vacant"]]
      .filter(function (k) { return seen[k[0]]; })
      .map(function (k) {
        return '<span class="key"><span class="swatch ht-swatch ht-' + k[0] + '"></span>' + esc(k[1]) + "</span>";
      }).join("");
  }

  /** A state's House districts as a navigator (VISUALS-27): one square
   *  per 2026 race, placed as kyc/tiles.py places them on the 2026 map,
   *  each a link to that race on the page. Neutral: the race is open to
   *  everyone on its ballot, and a square names its district, not a party.
   *  "" where there is nothing to navigate (one district, or no layout). */
  function districtTiles(code, races) {
    var layout = houseLayout();
    var b = layout && layout.states[code];
    if (!b || !races || races.length < 2) return "";
    var cells = b.cells2026 || b.cells;
    var byNum = {};
    races.forEach(function (r) { byNum[String(r.district || 0)] = r; });
    var nums = Object.keys(cells);
    if (nums.some(function (n) { return !byNum[n]; })) return "";
    var links = nums.map(function (n) {
      var r = byNum[n];
      return '<a class="dt-seat" href="#' + attr("race-" + r.id) + '" style="grid-column:' +
        (cells[n][0] + 1) + ";grid-row:" + (cells[n][1] + 1) + '" title="' + attr(r.label || "District " + n) +
        '"><span class="sr-only">District </span>' + esc(n) + "</a>";
    }).join("");
    return '<p class="dt-caption">House races: a square per district, in bands from the state’s ' +
      "north to its south, west to east within each band.</p>" +
      '<nav class="district-tiles jump-row" aria-label="Jump to a House race, districts laid out as on the map"' +
      ' style="--dt-cols:' + b.cols + ";--dt-rows:" + b.rows + '">' + links + "</nav>";
  }

  /* ------------------------------------------------ the states as a grid */

  /** Every state, D.C. and territory as a tile at its place on a map-like
   *  grid (VISUALS-35), each a link to its page; a dot marks a state with a
   *  Senate seat on the 2026 ballot. Neutral fill: a link, not a party. */
  function statePicker() {
    var grid = KYC.meta().stateGrid;
    var states = KYC.meta().states || {};
    if (!grid) return "";
    var senate = {};
    KYC.races().forEach(function (r) {
      if (r.chamber === "Senate") senate[r.state] = true;
    });
    var verb = past() ? "was" : "is";
    var tiles = Object.keys(grid).filter(function (code) { return states[code]; }).sort()
      .map(function (code) {
        var at = grid[code];
        var name = states[code].name;
        // The territories' row (kyc/tiles.py's last) sits one empty row
        // below the states'.
        var apart = at[0] >= 8;
        return '<a class="tp-tile' + (apart ? " tp-territory" : "") + '" href="' +
          attr(KYC.stateUrl(code)) + '" data-state="' + attr(code) + '" style="grid-row:' +
          (at[0] + (apart ? 2 : 1)) +
          ";grid-column:" + (at[1] + 1) + '" title="' + attr(name + (senate[code]
            ? ": a Senate seat " + verb + " on the Nov 3, 2026 ballot" : "")) + '">' +
          '<span aria-hidden="true">' + esc(code) + "</span>" +
          '<span class="sr-only">' + esc(name) + (senate[code] ? ", Senate race in 2026" : "") + "</span>" +
          (senate[code] ? '<span class="tp-dot" aria-hidden="true"></span>' : "") + "</a>";
      }).join("");
    return '<nav class="tile-picker" aria-label="States and territories, laid out as on a map">' +
      '<div class="tp-grid">' + tiles + "</div>" +
      '<p class="tp-key"><span class="tp-dot tp-dot-key" aria-hidden="true"></span>A Senate seat ' + verb +
      " on the Nov 3, 2026 ballot. The bottom row is the territories.</p></nav>";
  }

  /* The sidebar's chamber counts, with the bar under each. */
  KYC.ready(function () {
    [["senateBalance", "senate"], ["houseBalance", "house"]].forEach(function (pair) {
      var slot = doc.getElementById(pair[0]);
      if (!slot || !KYC.meta()[pair[1]]) return;
      var wrap = doc.createElement("div");
      wrap.className = "balance-bar-slot";
      wrap.innerHTML = balanceBar(pair[1], { compact: true });
      slot.parentNode.insertBefore(wrap, slot.nextSibling);
    });
  });

  KYC.balanceBar = balanceBar;
  KYC.houseTiles = houseTiles;
  KYC.houseTilesKey = houseTilesKey;
  KYC.districtTiles = districtTiles;
  KYC.statePicker = statePicker;
})(window);
