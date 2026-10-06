/* The partisan map on map.html.
 *
 * Renders straight from window.kycGeo - SVG path data decoded at build time
 * by kyc/geo.py. The page used to load d3 and topojson-client from two CDNs
 * and decode an 82 KB TopoJSON blob in the browser on every visit, which is
 * roughly 300 KB of third-party JavaScript to draw 57 shapes that are
 * identical between builds.
 *
 * Fills use color-mix() against the theme's own party custom properties, so
 * switching theme recolours the map through CSS with no repaint pass.
 *
 * The drawing itself - shapes, labels, callouts, the territory strip - is
 * the shared KYC.usmap (kyc-usmap.js); this module decides what colours a
 * state and what its panel shows. The three state-government views -
 * governors, legislatures, trifectas - are KYC.stategov's (kyc-stategov.js),
 * the same module every state page draws its own section with.
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;

  var data = global.legislatorsData || [];

  var mode = "senate";
  var selected = "";

  /* --------------------------------------------------------- delegations */

  /** Members and candidates grouped by state, built once. */
  var byState = (function () {
    var index = {};
    data.forEach(function (item) {
      if (!item.state || item.state === "N/A") return;
      (index[item.state] || (index[item.state] = [])).push(item);
    });
    return index;
  })();

  function delegation(code) {
    return byState[code] || [];
  }

  /** Party counts for a state's sitting delegation. */
  function tally(code) {
    var counts = {
      senate: { d: 0, r: 0, i: 0, vacant: 0 },
      house: { d: 0, r: 0, i: 0, vacant: 0 },
    };
    delegation(code).forEach(function (item) {
      if (item.isCandidate) return;
      var chamber = item.chamber.indexOf("Senate") !== -1 ? "senate"
        : item.chamber.indexOf("House") !== -1 ? "house" : null;
      if (chamber) counts[chamber][KYC.partyKey(item)] += 1;
    });
    return counts;
  }

  function senateDefender(code) {
    return delegation(code).filter(function (item) {
      return !item.isCandidate && item.chamber.indexOf("Senate") !== -1 &&
        item.seatUp2026;
    })[0] || null;
  }

  /* ---------------------------------------------------------------- fills */

  var VACANT_FILL = "var(--text-faint)";
  var NONE_FILL = "var(--surface-2)";
  var UNKNOWN_FILL = "var(--surface-3)";

  function mix(demShare) {
    // 0 = wholly Republican, 1 = wholly Democratic; the midpoint reads as the
    // split colour rather than a muddy blend of the two party colours.
    var pct = Math.round(Math.max(0, Math.min(1, demShare)) * 100);
    if (pct >= 50) {
      return "color-mix(in srgb, var(--party-d) " + ((pct - 50) * 2) +
        "%, var(--split))";
    }
    return "color-mix(in srgb, var(--party-r) " + ((50 - pct) * 2) + "%, var(--split))";
  }

  function stateMode() {
    return KYC.stategov.modes.indexOf(mode) !== -1;
  }

  /** Fill and hover text for one state in the current mode. */
  function appearance(code) {
    if (stateMode()) return KYC.stategov.look(code, mode);
    var counts = tally(code);

    if (mode === "senate") {
      var s = counts.senate;
      var seats = s.d + s.r + s.i;
      var fill = UNKNOWN_FILL;
      if (!seats) fill = NONE_FILL;
      else if (s.r === seats) fill = "var(--party-r)";
      else if (s.d === seats) fill = "var(--party-d)";
      else if (s.i === seats) fill = "var(--party-i)";
      else fill = "var(--split)";
      return {
        fill: fill,
        text: code + " Senate: " + s.r + "R, " + s.d + "D" + (s.i ? ", " + s.i + "I" : ""),
      };
    }

    if (mode === "house") {
      var h = counts.house;
      var held = h.d + h.r + h.i;
      var fill2;
      if (!held && h.vacant) fill2 = VACANT_FILL;
      else if (!held) fill2 = NONE_FILL;
      else if (h.i === held) fill2 = "var(--party-i)";
      else if (!(h.d + h.r)) fill2 = "var(--party-i)";
      else fill2 = mix(h.d / (h.d + h.r));
      return {
        fill: fill2,
        text: code + " House: " + h.r + "R, " + h.d + "D" +
          (h.i ? ", " + h.i + "I" : "") + (h.vacant ? ", " + h.vacant + " vacant" : ""),
      };
    }

    var defender = senateDefender(code);
    if (!defender) {
      return { fill: NONE_FILL, text: code + ": no Senate race in 2026" };
    }
    var key = KYC.partyKey(defender);
    return {
      fill: key === "vacant" ? VACANT_FILL : "var(--party-" + key + ")",
      text: code + ": 2026 Senate race — " + defender.party + " seat (" +
        defender.name + (defender.seekingReelection2026 ? " running" :
          defender.contestLabel ? " running for " + defender.contestLabel :
          defender.alsoRunningSeat ? " running for " + defender.alsoRunningSeat :
          " not running") + ")",
    };
  }

  /* ------------------------------------------------------------------ map */

  var map = KYC.usmap.create({
    look: appearance,
    onSelect: function (code) { select(code); },
  });

  /* --------------------------------------------------------------- legend */

  var LEGENDS = {
    senate: [
      ["var(--party-r)", "Both Republican"],
      ["var(--party-d)", "Both Democratic"],
      ["var(--split)", "Split delegation"],
      ["var(--party-i)", "Independent"],
    ],
    senate2026: [
      ["var(--party-r)", "Republican seat up"],
      ["var(--party-d)", "Democratic seat up"],
      ["var(--surface-1)", "No race in 2026"],
    ],
  };

  function drawLegend() {
    var target = doc.getElementById("mapLegend");
    if (stateMode()) {
      target.innerHTML = KYC.stategov.legend(mode).map(function (entry) {
        return '<span class="key"><span class="swatch" style="background:' +
          entry[0] + '"></span>' + KYC.escapeHtml(entry[1]) + "</span>";
      }).join("");
      return;
    }
    if (mode === "house") {
      target.innerHTML = [
        '<span class="key"><span class="party-r">All R</span>',
        '<span class="ramp" style="background:linear-gradient(to right,',
        "var(--party-r),var(--split),var(--party-d))\"></span>",
        '<span class="party-d">All D</span></span>',
        '<span class="key"><span class="swatch" style="background:var(--party-i)">',
        "</span>Independent</span>",
        '<span class="key"><span class="swatch" style="background:var(--text-faint)">',
        "</span>Vacant</span>",
      ].join("");
      return;
    }
    target.innerHTML = LEGENDS[mode]
      .map(function (entry) {
        return '<span class="key"><span class="swatch" style="background:' +
          entry[0] + '"></span>' + KYC.escapeHtml(entry[1]) + "</span>";
      })
      .join("");
  }

  /* ---------------------------------------------------------------- panel */

  var MODE_TITLE = {
    senate: "Senate delegation",
    house: "House delegation and 2026 candidates",
    senate2026: "2026 Senate race",
  };
  KYC.stategov.modes.forEach(function (m) { MODE_TITLE[m] = KYC.stategov.titles[m]; });

  function forMode(code) {
    var people = delegation(code);
    if (mode === "senate") {
      return people.filter(function (x) {
        return !x.isCandidate && x.chamber.indexOf("Senate") !== -1;
      });
    }
    if (mode === "house") {
      return people.filter(function (x) { return x.chamber.indexOf("House") !== -1; });
    }
    return people.filter(function (x) {
      return x.chamber.indexOf("Senate") !== -1 && (x.seatUp2026 || x.isCandidate);
    });
  }

  /* The panel's rows are narrow, so the shared badges' labels are shortened
   * here; the statuses themselves are the shared module's. */
  var RACE_BADGE = {
    nominee: "badge-money|Nominee", eliminated: "badge-danger|Lost primary",
    withdrawn: "badge-neutral|Withdrew", unlisted: "badge-neutral|Not on ballot",
    advanced: "badge-warn|In runoff",
  };

  /* A member contesting another seat: the seat, and the result of the race
   * they are in, not of the seat they hold. The panel is one state's, so the
   * seat says only what the row does not: "Running for CA-41", "Running for
   * Senate" - and the state too, should a contest ever be in another one. */
  function contestSeat(item) {
    var seat = item.contestLabel.split(" • ");
    var label = seat[0] === "House" && seat[1] ? seat[1]
      : seat[1] === item.state ? seat[0] : seat.join(" ");
    return '<span class="badge badge-warn contest" title="' +
      KYC.escapeAttr("Running for " + item.contestLabel) + '">Running for ' +
      KYC.escapeHtml(label) + "</span>";
  }

  function contestBadge(item) {
    var contest = RACE_BADGE[KYC.contestStatus(item)];
    return contest ? '<span class="badge ' + contest.split("|")[0] + '">' +
      contest.split("|")[1] + KYC.ballotLineSuffix(item) + "</span>" : "";
  }

  function rowBadge(item) {
    var status = String(item.status || "").toLowerCase();
    var race = RACE_BADGE[item.raceStatus];
    if (race) {
      var bits = race.split("|");
      if (!item.isCandidate && !item.contestLabel && item.raceStatus === "nominee") bits[1] = "Renominated";
      if (!item.isCandidate && item.raceStatus === "unlisted") bits = ["badge-danger", "Not on ballot"];
      // "Nominee – Speak The Truth line": not a second Democratic nominee.
      return '<span class="badge ' + bits[0] + '">' + bits[1] +
        (item.raceStatus === "nominee" ? KYC.ballotLineSuffix(item) : "") + "</span>";
    }
    if (item.isCandidate) return '<span class="badge badge-money">Challenger</span>';
    if (/retiring|not running|defeated|ineligible|resigned/.test(status)) {
      return '<span class="badge badge-danger">Departing</span>';
    }
    if (item.chamber.indexOf("Senate") !== -1 && item.seatUp2026) {
      return '<span class="badge badge-warn">Up in ’26</span>';
    }
    return "";
  }

  function personRow(item) {
    // A member contesting another seat carries two badges. Both at the row's
    // end squeezed the name to nothing and broke "House • CA-38" over four
    // lines, so the seat ("Running for CA-41") takes a line under the text
    // and the result ("Nominee") stays at the end, in line with every other
    // row's "Renominated". The grid in kyc.css places them.
    var elsewhere = !item.isCandidate && item.contestLabel;
    return [
      '<button type="button" class="person-row" data-id="',
      KYC.escapeAttr(item.id), '">',
      '<img ', KYC.portraitAttrs(item, "38px"),
      ' alt="" loading="lazy" decoding="async" data-photo-idx="0" data-profile="',
      KYC.escapeAttr(item.id), '">',
      '<span class="who">',
      '<span class="name">', KYC.escapeHtml(item.name), "</span>",
      '<span class="office">', KYC.escapeHtml(item.officeLabel), "</span>",
      '<span class="party ', KYC.partyClass(item), '">',
      KYC.escapeHtml(item.party), "</span>",
      "</span>",
      elsewhere ? contestSeat(item) + contestBadge(item) : rowBadge(item),
      KYC.icon("chevron"),
      "</button>",
    ].join("");
  }

  function showPanel(code) {
    var list = doc.getElementById("delegation");
    var counts = tally(code);
    var people = forMode(code).slice();

    doc.getElementById("panelState").textContent = map.name(code);
    doc.getElementById("panelMode").textContent = MODE_TITLE[mode];
    var pageLink = doc.getElementById("panelStateLink");
    if (pageLink) {
      pageLink.hidden = false;
      pageLink.href = KYC.stateUrl(code);
      pageLink.textContent = "Open the " + KYC.stateName(code) + " page \u203a";
    }

    if (stateMode()) {
      doc.getElementById("panelCounts").innerHTML = KYC.stategov.badge(code, mode);
      list.innerHTML = '<div class="stategov">' + KYC.stategov.render(code, { links: true }) + "</div>";
      list.scrollTop = 0;
      return;
    }

    var group = mode === "house" ? counts.house : counts.senate;
    var pill = function (n, cls, label) {
      return n ? '<span class="' + cls + '">' + n + " " + label + "</span>" : "";
    };
    doc.getElementById("panelCounts").innerHTML = [
      pill(group.r, "party-r", "R"),
      pill(group.d, "party-d", "D"),
      pill(group.i, "party-i", "I"),
      pill(group.vacant, "party-vacant", "vacant"),
    ].filter(Boolean).join(" ") || '<span class="faint">No seats</span>';

    if (!people.length) {
      list.innerHTML =
        '<div class="empty-state">' + KYC.icon("info") +
        "<p>Nothing to show for " + KYC.escapeHtml(code) + " in this view.</p></div>";
      return;
    }

    var order = function (a, b) {
      return (
        KYC.districtOrder(a) - KYC.districtOrder(b) ||
        a.name.localeCompare(b.name)
      );
    };
    var OFF = KYC.cards.OFF_BALLOT;
    var seated = people.filter(function (x) { return !x.isCandidate; }).sort(order);
    var running = people.filter(function (x) {
      return x.isCandidate && !OFF[x.raceStatus];
    }).sort(order);
    var out = people.filter(function (x) { return x.isCandidate && OFF[x.raceStatus]; });

    /* Texas has 37 representatives and 191 filed challengers. Listing all 228
     * in one scroll buries the delegation the reader clicked the state to
     * see, so the challengers sit behind a count they can open. */
    var html = "";
    if (mode === "senate2026" && KYC.odds) {
      var seatRace = (global.kycRaces || []).filter(function (r) {
        return r.chamber === "Senate" && r.state === code;
      })[0];
      if (seatRace) html += KYC.odds.render(seatRace, { compact: true });
    }
    if (seated.length) {
      html += '<p class="panel-subhead">' +
        (mode === "senate2026" ? "Seat held by" : "Currently seated") +
        " <span>" + seated.length + "</span></p>" +
        seated.map(personRow).join("");
    }
    // The House view: every district drawn, with who holds it.
    var districtMap = mode === "house" && (KYC.meta().districtMaps || {})[code];
    if (districtMap) {
      html += '<p class="gov-pages"><a class="sidebar-link" href="' +
        KYC.escapeAttr(KYC.siteRoot() + districtMap.page) + '">' +
        (districtMap.redrawn ? "Old and new district lines \u203a" : "District map \u203a") + "</a></p>";
    }
    if (running.length) {
      html +=
        '<button type="button" class="panel-subhead expander" id="showChallengers"' +
        ' aria-expanded="false" aria-controls="challengerRows">' +
        KYC.icon("chevron") + " 2026 challengers <span>" + running.length + "</span>" +
        (out.length
          ? ' <span class="faint" title="Lost the primary, withdrew, or were not on the primary ballot">' +
            out.length + " out</span>"
          : "") +
        "</button>" +
        '<div id="challengerRows" hidden>' + running.map(personRow).join("") + "</div>";
    } else if (out.length) {
      html += '<p class="panel-subhead">No challenger still on the ballot ' +
        '<span title="Lost the primary, withdrew, or were not on the primary ballot">' +
        out.length + " out</span></p>";
    }
    list.innerHTML = html;
    list.scrollTop = 0;

    var toggle = doc.getElementById("showChallengers");
    if (toggle) {
      toggle.addEventListener("click", function () {
        var rows = doc.getElementById("challengerRows");
        var open = rows.hidden;
        rows.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        toggle.classList.toggle("open", open);
      });
    }
  }

  function select(code, opts) {
    if (!code) return;
    selected = code;
    map.setSelected(code);
    showPanel(code);
    var picker = doc.getElementById("mapStateSelect");
    if (picker && picker.value !== code) picker.value = code;
    // Every view needs a URL: a selected state is shareable as #/?state=TX.
    if (!(opts && opts.fromRoute)) {
      KYC.router.writeFilters({ state: code, mode: mode === "senate" ? "" : mode });
    }
    KYC.rememberState(code);
    KYC.renderRememberedState();
  }

  function setMode(next, opts) {
    if (!MODE_TITLE[next]) return;
    mode = next;
    Array.prototype.forEach.call(
      doc.querySelectorAll("[data-mode]"),
      function (button) {
        button.setAttribute(
          "aria-pressed", String(button.getAttribute("data-mode") === mode)
        );
      }
    );
    drawLegend();
    map.paint();
    if (selected) showPanel(selected);
    if (!(opts && opts.fromRoute)) {
      KYC.router.writeFilters({ state: selected, mode: mode === "senate" ? "" : mode });
    }
  }

  /* ----------------------------------------------------------------- boot */

  function initStatePicker() {
    var picker = doc.getElementById("mapStateSelect");
    if (!picker) return;
    map.codes().sort().forEach(function (code) {
      var option = doc.createElement("option");
      option.value = code;
      option.textContent = code;
      picker.appendChild(option);
    });
    picker.addEventListener("change", function () {
      if (!picker.value) return;
      select(picker.value);
      map.reveal();
    });
  }

  KYC.ready(function () {
    if (!map.loaded()) {
      doc.getElementById("mapStage").innerHTML =
        '<div class="empty-state">' + KYC.icon("info") +
        "<h3>Map geometry did not load</h3>" +
        "<p>Run <code>python build_profile_site.py geo</code> to regenerate " +
        "<code>data/geo.js</code>.</p></div>";
      return;
    }

    KYC.profile.ensure();
    map.start();
    initStatePicker();
    /* Read the incoming route before anything writes one. Boot used to call
     * setMode("senate") as a user action, which wrote "#/" over the address
     * before it was read - so map.html#/?state=TX, every state page's map
     * link and every shared profile link all landed on a blank map. */
    var initial = KYC.router.read();
    setMode(MODE_TITLE[initial.params.mode] ? initial.params.mode : "senate",
            { fromRoute: true });

    doc.querySelector(".map-views").addEventListener("click", function (event) {
      var button = event.target.closest("[data-mode]");
      if (button) setMode(button.getAttribute("data-mode"));
    });

    doc.getElementById("delegation").addEventListener("click", function (event) {
      var row = event.target.closest("[data-id]");
      if (row) KYC.profile.open(row.getAttribute("data-id"));
    });

    KYC.router.onChange(function () {
      var route = KYC.router.read();
      if (route.view === "profile") {
        KYC.profile.open(route.id, { fromRoute: true });
        return;
      }
      if (KYC.profile.isOpen()) KYC.profile.close();
      var wanted = route.params.mode || "senate";
      if (wanted !== mode) setMode(wanted, { fromRoute: true });
      if (route.params.state && route.params.state !== selected) {
        select(route.params.state, { fromRoute: true });
      } else if (!route.params.state && selected) {
        // Back on the list with a state still showing - after closing a
        // profile someone landed on directly - so the address says which.
        KYC.router.writeFilters({ state: selected, mode: mode === "senate" ? "" : mode });
      }
    });
    if (initial.view === "profile") {
      // A shared profile opens over that person's state, not a blank map.
      var person = KYC.byId(initial.id);
      if (person && map.hasShape(person.state)) select(person.state, { fromRoute: true });
      KYC.profile.open(initial.id, { fromRoute: true });
    } else if (initial.params.state) {
      select(initial.params.state, { fromRoute: true });
    }
  });
})(window);
