/* Know Your Candidate - shared behaviour for index.html and map.html.
 *
 * Loaded in <head>, immediately after the Tailwind CDN script. Everything that
 * touches the DOM waits for DOMContentLoaded.
 *
 * This file exists because the theme switcher, the portrait fallback chain and
 * the profile modal were duplicated in both pages and had already drifted.
 */
(function (global) {
  "use strict";

  /* ------------------------------------------------------ tailwind config */

  if (global.tailwind) {
    global.tailwind.config = {
      darkMode: ["class", '[data-theme="amoled"]'],
      theme: {
        extend: {
          fontFamily: {
            sans: ["Roboto", "sans-serif"],
            slab: ["Roboto Slab", "serif"],
          },
          colors: {
            yt: {
              bg: "var(--bg-main)",
              elevated: "var(--bg-elevated)",
              input: "var(--bg-input)",
              hover: "var(--bg-hover)",
              border: "var(--border-main)",
              borderHover: "var(--border-hover)",
              text: "var(--text-main)",
              textMuted: "var(--text-muted)",
              textFaint: "var(--text-faint)",
              inverse: "var(--text-inverse)",
            },
          },
        },
      },
    };
  }

  /* ---------------------------------------------------------------- theme */

  var THEMES = ["dark", "amoled", "light"];

  function setTheme(name) {
    if (THEMES.indexOf(name) === -1) name = "dark";
    // Guard: this file is loaded in <head>, but never assume the root element
    // exists - a null here would abort the whole module.
    if (document.documentElement) {
      document.documentElement.setAttribute("data-theme", name);
    }
    try {
      localStorage.setItem("ytTheme", name);
    } catch (e) {
      /* private mode / opaque origin - the attribute above still applies */
    }
  }

  function initTheme() {
    var saved = "dark";
    try {
      saved = localStorage.getItem("ytTheme") || "dark";
    } catch (e) {}
    setTheme(saved);
  }

  /* ------------------------------------------------------------ portraits */

  var SILHOUETTE =
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' " +
    "fill='%23aaaaaa'%3E%3Ccircle cx='50' cy='35' r='20'/%3E" +
    "%3Cpath d='M20,80 C20,55 80,55 80,80 Z'/%3E%3C/svg%3E";

  /* Portraits are resolved and checked at build time, so the runtime chain is
   * now a safety net rather than the primary mechanism. */
  function handleImageFallback(img, profileId) {
    var item = (global.legislatorsData || []).find(function (x) {
      return x.id === profileId;
    });
    var chain = (item && item.photos) || [];
    var idx = parseInt(img.dataset.photoIdx || "0", 10) + 1;

    while (idx < chain.length && chain[idx] === "placeholder") idx++;

    if (idx < chain.length) {
      img.dataset.photoIdx = String(idx);
      img.src = chain[idx];
    } else {
      img.onerror = null;
      img.src = SILHOUETTE;
    }
  }

  /* ----------------------------------------------------------- provenance */

  var ABSENT = { not_disclosed: "Not disclosed", unknown: "No data" };

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return {
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
      }[ch];
    });
  }

  /* Render a field so an absence never looks like a finding. */
  function renderField(item, field, opts) {
    opts = opts || {};
    var status = (item.quality || {})[field];
    var value = item[field];

    if (status === "not_disclosed" || status === "unknown") {
      return (
        '<span class="kyc-absent" title="' +
        (status === "not_disclosed"
          ? "No public disclosure exists for this field."
          : "No source has been recorded for this field yet.") +
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
        ' <span class="kyc-badge kyc-badge--source" title="Filed with the FEC' +
        (item.financeAsOf ? ", coverage through " + escapeHtml(item.financeAsOf) : "") +
        '">' + escapeHtml(item.financeSource) + "</span>";
    }
    return html;
  }

  /* ------------------------------------------------------------- election */

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
    var ms = day.getTime() - now.getTime();
    var days = Math.ceil(ms / 86400000);

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

  /* -------------------------------------------------------------- a11y */

  var FOCUSABLE =
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]),' +
    ' textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function createModal(el, opts) {
    opts = opts || {};
    var lastFocus = null;

    function focusables() {
      return Array.prototype.filter.call(
        el.querySelectorAll(FOCUSABLE),
        function (n) { return n.offsetParent !== null; }
      );
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

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    var api = {
      isOpen: function () {
        return !el.classList.contains("hidden");
      },
      open: function () {
        lastFocus = document.activeElement;
        el.classList.remove("hidden");
        document.body.style.overflow = "hidden";
        document.addEventListener("keydown", onKeydown, true);
        var nodes = focusables();
        (nodes[0] || el).focus();
      },
      close: function () {
        if (!api.isOpen()) return;
        el.classList.add("hidden");
        document.body.style.overflow = "";
        document.removeEventListener("keydown", onKeydown, true);
        if (lastFocus && lastFocus.focus) lastFocus.focus();
        if (opts.onClose) opts.onClose();
      },
    };
    return api;
  }

  /* -------------------------------------------------------------- router */

  /* Deep links: "#/profile/<id>" for one person, "#/?k=v" for a filtered view.
   * Without this the site cannot be shared - the single biggest functional gap
   * for a tool whose whole purpose is being passed around before an election. */
  var router = {
    read: function () {
      var hash = global.location.hash.replace(/^#\/?/, "");
      if (!hash) return { view: "list", params: {} };

      var profile = hash.match(/^profile\/(.+)$/);
      if (profile) return { view: "profile", id: decodeURIComponent(profile[1]), params: {} };

      var params = {};
      var query = hash.indexOf("?") === 0 ? hash.slice(1) : hash;
      query.split("&").forEach(function (pair) {
        if (!pair) return;
        var bits = pair.split("=");
        params[decodeURIComponent(bits[0])] = decodeURIComponent(bits.slice(1).join("=") || "");
      });
      return { view: "list", params: params };
    },

    writeFilters: function (params) {
      var query = Object.keys(params)
        .filter(function (k) {
          return params[k] && params[k] !== "all";
        })
        .map(function (k) {
          return encodeURIComponent(k) + "=" + encodeURIComponent(params[k]);
        })
        .join("&");
      var hash = query ? "#/?" + query : "#/";
      // replaceState: filter tweaks should not fill the back button.
      history.replaceState(null, "", global.location.pathname + hash);
    },

    writeProfile: function (id) {
      history.pushState(null, "", global.location.pathname + "#/profile/" + encodeURIComponent(id));
    },

    clearProfile: function () {
      if (/#\/profile\//.test(global.location.hash)) history.back();
    },

    onChange: function (handler) {
      global.addEventListener("hashchange", handler);
      global.addEventListener("popstate", handler);
    },
  };

  /* ------------------------------------------------------------- helpers */

  function partyClass(party, status) {
    if (party === "Vacant" || status === "Vacant") return "text-yt-text";
    if (String(party).indexOf("Democrat") !== -1) return "text-[var(--party-d)]";
    if (party === "Republican") return "text-[var(--party-r)]";
    return "text-[var(--party-i)]";
  }

  /* Search across everything a voter might reasonably type, not just the four
   * fields the original implementation covered. */
  var SEARCH_FIELDS = [
    "name", "state", "party", "district", "officeLabel", "status",
    "education", "previous_professions", "committees", "platforms",
    "funding_sources", "voting_alignment",
  ];

  function searchIndex(item) {
    if (item.__search) return item.__search;
    var parts = [];
    SEARCH_FIELDS.forEach(function (f) {
      var status = (item.quality || {})[f];
      if (status === "not_disclosed" || status === "unknown") return;
      if (item[f]) parts.push(String(item[f]));
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
      var args = arguments, self = this;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(self, args); }, wait || 150);
    };
  }

  /* --------------------------------------------------------------- boot */

  function initShell() {
    // Off-canvas sidebar for narrow screens.
    var toggle = document.getElementById("sidebarToggle");
    var scrim = document.getElementById("sidebarScrim");
    function closeSidebar() { document.body.classList.remove("sidebar-open"); }
    if (toggle) {
      toggle.addEventListener("click", function () {
        document.body.classList.toggle("sidebar-open");
        toggle.setAttribute("aria-expanded", document.body.classList.contains("sidebar-open"));
      });
    }
    if (scrim) scrim.addEventListener("click", closeSidebar);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeSidebar();
    });

    // Footer freshness stamp, from the build metadata.
    var stamp = document.getElementById("buildStamp");
    if (stamp && global.kycBuildMeta) {
      var built = new Date(global.kycBuildMeta.built);
      stamp.textContent = isNaN(built) ? "unknown" : built.toISOString().slice(0, 10);
    }

    var countdown = document.getElementById("electionCountdown");
    if (countdown) {
      var status = electionStatus(2026);
      countdown.textContent = status.label;
      countdown.setAttribute("datetime", status.iso);
    }
  }

  initTheme();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initShell);
  } else {
    initShell();
  }

  global.KYC = {
    setTheme: setTheme,
    SILHOUETTE: SILHOUETTE,
    handleImageFallback: handleImageFallback,
    renderField: renderField,
    escapeHtml: escapeHtml,
    electionStatus: electionStatus,
    generalElectionDay: generalElectionDay,
    createModal: createModal,
    router: router,
    partyClass: partyClass,
    matchesQuery: matchesQuery,
    searchIndex: searchIndex,
    debounce: debounce,
  };

  // The pages still call these as bare globals.
  global.setTheme = setTheme;
  global.handleImageFallback = handleImageFallback;
  global.defaultSilhouette = SILHOUETTE;
})(window);
