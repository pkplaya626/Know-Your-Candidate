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
    filter: "M3 5h18l-7 8v6l-4 2v-8z",
    sort: "M7 4v16M3 16l4 4 4-4M17 20V4M13 8l4-4 4 4",
    landmark: "M3 9l9-5 9 5zM6 11v6M10 11v6M14 11v6M18 11v6M4 17h16M3 20h18",
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

  var profileIndex = null;

  /** Profiles keyed by id. Built once; the grid, the map and every deep link
   *  all resolve through it instead of scanning 594 records per lookup. */
  function byId(id) {
    if (profileIndex === null) {
      profileIndex = new Map();
      var data = global.legislatorsData || [];
      data.forEach(function (item) {
        profileIndex.set(item.id, item);
      });
      // A person registered with the FEC under several ids has one profile;
      // the others are kept as otherFecIds (derived in the pipeline). A link
      // shared under one of them still opens that person, never a stranger:
      // a real profile id always wins over an alias.
      data.forEach(function (item) {
        (item.otherFecIds || []).forEach(function (other) {
          var alias = "FEC_" + other;
          if (!profileIndex.has(alias)) profileIndex.set(alias, item);
        });
      });
    }
    return profileIndex.get(id);
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
    if (!item || contestStatus(item) !== "nominee") return "";
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
   *  silhouette when there is nothing to try. */
  function portraitSrc(item) {
    var first = item && item.photos && item.photos[0];
    return !first || first === "placeholder" ? SILHOUETTE : first;
  }

  /* Sizes of the first portrait for a srcset, when the build found several
   * of the same photograph: the browser then fetches one sharp at this
   * screen's density, rather than a 960px original for a 38px circle. */
  function portraitSrcset(item) {
    var set = item && item.photoSet;
    if (!set || !set.length || portraitSrc(item) === SILHOUETTE) return "";
    return set.map(function (entry) { return entry[1] + " " + entry[0] + "w"; }).join(", ");
  }

  /** The src - and srcset and sizes, when there are sizes - of a portrait
   *  <img>, escaped. *sizes* is the width it is drawn at, e.g. "38px". */
  function portraitAttrs(item, sizes) {
    var set = portraitSrcset(item);
    return 'src="' + escapeAttr(portraitSrc(item)) + '"' + (set
      ? ' srcset="' + escapeAttr(set) + '" sizes="' + escapeAttr(sizes) + '"'
      : "");
  }

  /** Point an existing <img> at a profile's portrait - the dialog reuses one
   *  element, so a srcset left by the last profile must go. */
  function setPortrait(img, item, sizes) {
    var set = portraitSrcset(item);
    img.setAttribute("data-photo-idx", "0");
    img.removeAttribute("srcset");
    img.removeAttribute("sizes");
    if (set) {
      img.setAttribute("sizes", sizes);
      img.setAttribute("srcset", set);
    }
    img.src = portraitSrc(item);
  }

  /* Delegated: one listener for every portrait on the page, rather than an
   * inline onerror attribute per image with an id interpolated into it. */
  function initPortraitFallback() {
    doc.addEventListener(
      "error",
      function (event) {
        var img = event.target;
        if (!img || img.tagName !== "IMG") return;
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
  };
  var ABSENT_TITLE = {
    not_disclosed: "No public disclosure exists for this field.",
    unknown: "No source has been recorded for this field yet.",
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
    if (status === "generic") {
      return (
        '<span class="kyc-generic" title="Generic placeholder, not researched detail.">' +
        escapeHtml(value) + "</span>"
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

  /** Plain text saying what period a profile's money covers, or "".
   *
   *  Every figure is an FEC total, but over which months matters as much as
   *  the amount: a senator's election period is the whole six-year term, so
   *  the same "Raised" tile can hold six years beside a challenger's two.
   *  The pipeline records the period (financePeriod, financeElection,
   *  financeSince, financeAsOf); this only words it, and never fills a
   *  missing start date in. Plain text - callers escape it. */
  function financePeriod(item) {
    if (!item || !item.financeSource) return "";
    var since = monthYear(item.financeSince);
    var through = monthYear(item.financeAsOf);
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
          : "");
    }
    if (!item.financeElection) return through ? "FEC figures through " + through : "";

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
    return text;
  }

  /** True when a field carries something worth showing at all. */
  function hasValue(item, field) {
    return !ABSENT[(item.quality || {})[field]];
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
        return !n.hasAttribute("hidden") && !n.closest("[hidden]");
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
  function createMenu(button, panel) {
    function isOpen() { return !panel.hidden; }

    function close(fromHistory) {
      if (!isOpen()) return;
      panel.hidden = true;
      button.setAttribute("aria-expanded", "false");
      doc.removeEventListener("keydown", onKey, true);
      doc.removeEventListener("click", onOutside, true);
      if (fromHistory !== true && history.state && history.state.kycMenu) history.back();
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
      if (!(history.state && history.state.kycMenu)) close(true);
    });

    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        button.focus();
      }
    }

    function onOutside(event) {
      if (!panel.contains(event.target) && event.target !== button) close();
    }

    button.setAttribute("aria-expanded", "false");
    button.addEventListener("click", function (event) {
      event.stopPropagation();
      if (isOpen()) close(); else open();
    });
    panel.addEventListener("click", function (event) {
      if (event.target.closest(".menu-item")) close();
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
      if (!hash) return { view: "list", params: {} };

      var profile = hash.match(/^profile\/(.+)$/);
      if (profile) {
        return { view: "profile", id: decodeURIComponent(profile[1]), params: {} };
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
      var hash = "#/profile/" + encodeURIComponent(id);
      if (global.location.hash === hash) return;
      var state = history.state;
      var depth = 1;
      if (state && state.kycProfile) {
        depth = (state.depth || 1) + 1;
      } else if (/#\/profile\//.test(global.location.hash)) {
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
      if (!/#\/profile\//.test(global.location.hash)) return;
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
   *  had their own and they disagreed about Democratic-Farmer Labor. */
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

  function searchIndex(item) {
    if (item.__search) return item.__search;
    var parts = [];
    SEARCH_FIELDS.forEach(function (field) {
      if (item[field] && hasValue(item, field)) parts.push(String(item[field]));
    });
    // Other names the member's own record gives ("Jim Clyburn" for James
    // Clyburn); derived in the pipeline from the bioguide-keyed record.
    (item.aliases || []).forEach(function (alias) { parts.push(String(alias)); });
    item.__search = foldText(parts.join(" "));
    return item.__search;
  }

  function matchesQuery(item, query) {
    if (!query) return true;
    var haystack = searchIndex(item);
    return foldText(query).split(/\s+/).every(function (term) {
      return !term || haystack.indexOf(term) !== -1;
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
  function renderSummary() {
    var info = meta();
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
      challengers.textContent = String(
        running !== undefined ? running : (election.challengers || 0)
      );
      if (running !== undefined && election.challengers) {
        challengers.title = election.challengers + " filed with the FEC; " +
          (election.challengers - running) + " lost a primary, withdrew, or were " +
          "not on the primary ballot";
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
    select.addEventListener("change", function () {
      var code = select.value;
      if (!code) return;
      global.location.href = onMaps && maps[code] ? siteRoot() + maps[code].page : stateUrl(code);
    });
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
        var people = global.legislatorsData || [];
        if (!people.length || doc.getElementById("kycNames")) return;
        var list = doc.createElement("datalist");
        list.id = "kycNames";
        // Each option's value is the display name; a member's aliases ride in
        // its label, which browsers show beside it and match typing against,
        // so "Jim Clyburn" offers "James Clyburn".
        var names = {};
        people.forEach(function (p) {
          if (p.raceStatus && p.raceStatus !== "nominee" && p.raceStatus !== "advanced" &&
              p.isCandidate) return;      // off-ballot filers would swamp the list
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

    // Footer freshness stamp, from the build metadata.
    var stamp = doc.getElementById("buildStamp");
    if (stamp && meta().built) {
      var built = new Date(meta().built);
      if (!isNaN(built)) {
        stamp.textContent = built.toISOString().slice(0, 10);
        stamp.setAttribute("datetime", built.toISOString());
      }
    }

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
    sourceBadge: sourceBadge,
    financePeriod: financePeriod,
    monthYear: monthYear,
    hasValue: hasValue,
    partyKey: partyKey,
    partyClass: partyClass,
    // data
    byId: byId,
    runsElsewhere: runsElsewhere,
    contestStatus: contestStatus,
    ballotLine: ballotLine,
    ballotLineSuffix: ballotLineSuffix,
    meta: meta,
    portraitSrc: portraitSrc,
    portraitSrcset: portraitSrcset,
    portraitAttrs: portraitAttrs,
    setPortrait: setPortrait,
    handleImageFallback: handleImageFallback,
    SILHOUETTE: SILHOUETTE,
    // behaviour
    createModal: createModal,
    createMenu: createMenu,
    router: router,
    electionStatus: electionStatus,
    generalElectionDay: generalElectionDay,
    matchesQuery: matchesQuery,
    foldText: foldText,
    searchIndex: searchIndex,
    districtOrder: districtOrder,
    debounce: debounce,
    ready: ready,
    // states
    stateName: stateName,
    stateUrl: stateUrl,
    siteRoot: siteRoot,
    rememberState: rememberState,
    renderRememberedState: renderRememberedState,
  };
})(window);
