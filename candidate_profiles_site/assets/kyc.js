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
    themeListeners.forEach(function (fn) {
      try { fn(resolveTheme(name), name); } catch (e) { /* keep going */ }
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
      (global.legislatorsData || []).forEach(function (item) {
        profileIndex.set(item.id, item);
      });
    }
    return profileIndex.get(id);
  }

  /* Portraits are resolved and checked at build time, so this runtime chain
   * is a safety net rather than the primary mechanism. */
  function handleImageFallback(img, profileId) {
    var item = byId(profileId);
    var chain = (item && item.photos) || [];
    var idx = parseInt(img.getAttribute("data-photo-idx") || "0", 10) + 1;

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

    var html = escapeHtml(value);
    if (opts.source && item.financeSource) {
      html +=
        ' <span class="badge badge-money" title="Filed with the FEC' +
        escapeAttr(item.financeAsOf ? ", coverage through " + item.financeAsOf : "") +
        '">' + escapeHtml(item.financeSource) + "</span>";
    }
    return html;
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

  function electionStatus(year, now) {
    year = year || 2026;
    now = now || new Date();
    var day = generalElectionDay(year);
    var days = Math.ceil((day.getTime() - now.getTime()) / 86400000);

    var phase;
    if (days > 1) phase = "campaign";
    else if (days >= 0) phase = "election-day";
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

  /** A click-opened, keyboard-operable menu.
   *
   *  The theme picker used to be a CSS :hover popup, which meant it could not
   *  be opened by keyboard at all and behaved erratically on touch, where a
   *  tap fires hover and click together. */
  function createMenu(button, panel) {
    function isOpen() { return !panel.hidden; }

    function close() {
      if (!isOpen()) return;
      panel.hidden = true;
      button.setAttribute("aria-expanded", "false");
      doc.removeEventListener("keydown", onKey, true);
      doc.removeEventListener("click", onOutside, true);
    }

    function open() {
      panel.hidden = false;
      button.setAttribute("aria-expanded", "true");
      doc.addEventListener("keydown", onKey, true);
      doc.addEventListener("click", onOutside, true);
      var first = panel.querySelector(FOCUSABLE);
      if (first) first.focus();
    }

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
          return encodeURIComponent(k) + "=" + encodeURIComponent(params[k]);
        })
        .join("&");
      var hash = query ? "#/?" + query : "#/";
      if (global.location.hash === hash) return;
      // replaceState: filter tweaks should not fill the back button.
      history.replaceState(null, "", global.location.pathname + hash);
    },

    writeProfile: function (id) {
      history.pushState(
        null, "", global.location.pathname + "#/profile/" + encodeURIComponent(id)
      );
    },

    clearProfile: function () {
      if (/#\/profile\//.test(global.location.hash)) history.back();
    },

    onChange: function (handler) {
      global.addEventListener("hashchange", handler);
      global.addEventListener("popstate", handler);
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
  ];

  function searchIndex(item) {
    if (item.__search) return item.__search;
    var parts = [];
    SEARCH_FIELDS.forEach(function (field) {
      if (item[field] && hasValue(item, field)) parts.push(String(item[field]));
    });
    item.__search = parts.join(" ").toLowerCase();
    return item.__search;
  }

  function matchesQuery(item, query) {
    if (!query) return true;
    var haystack = searchIndex(item);
    return query.split(/\s+/).every(function (term) {
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
    if (challengers) challengers.textContent = String(election.challengers || 0);
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
    var closeSidebar = function () {
      doc.body.classList.remove("sidebar-open");
      if (toggle) toggle.setAttribute("aria-expanded", "false");
    };
    if (toggle) {
      toggle.addEventListener("click", function () {
        var open = doc.body.classList.toggle("sidebar-open");
        toggle.setAttribute("aria-expanded", String(open));
      });
    }
    if (scrim) scrim.addEventListener("click", closeSidebar);
    doc.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeSidebar();
    });

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

    renderSummary();

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
    hasValue: hasValue,
    partyKey: partyKey,
    partyClass: partyClass,
    // data
    byId: byId,
    meta: meta,
    portraitSrc: portraitSrc,
    handleImageFallback: handleImageFallback,
    SILHOUETTE: SILHOUETTE,
    // behaviour
    createModal: createModal,
    createMenu: createMenu,
    router: router,
    electionStatus: electionStatus,
    generalElectionDay: generalElectionDay,
    matchesQuery: matchesQuery,
    searchIndex: searchIndex,
    districtOrder: districtOrder,
    debounce: debounce,
    ready: ready,
  };
})(window);
