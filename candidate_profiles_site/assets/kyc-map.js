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
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;

  var geo = global.kycGeo || { states: {}, territories: [], viewBox: [0, 0, 975, 610] };
  var data = global.legislatorsData || [];

  var STRIP_Y = 618;
  var STRIP_STEP = 46;
  var STRIP_LEFT = 366;

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

  /** Fill and hover text for one state in the current mode. */
  function appearance(code) {
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
        defender.name + (defender.seekingReelection2026 ? " running" : " not running") + ")",
    };
  }

  /* ------------------------------------------------------------- geometry */

  /* States are <path> elements with a role and a tabindex, so the map can be
   * driven from the keyboard. The previous version bound click handlers to
   * bare <g> elements: mouse only, and invisible to assistive technology. */
  function shapeMarkup(code, label, d, transform, extraClass) {
    return [
      '<path class="state', extraClass ? " " + extraClass : "", '" d="', d, '"',
      transform ? ' transform="' + transform + '"' : "",
      ' data-state="', KYC.escapeAttr(code), '"',
      ' role="button" tabindex="0" aria-pressed="false"',
      ' aria-label="', KYC.escapeAttr(label), '">',
      "<title></title></path>",
    ].join("");
  }

  function drawMap() {
    var svg = doc.getElementById("usMap");
    var box = geo.viewBox || [0, 0, 975, 610];
    // The territory strip sits below the projected atlas, so the viewBox is
    // taller than the atlas itself.
    svg.setAttribute("viewBox", box.join(" ") + "");
    svg.setAttribute(
      "viewBox",
      box[0] + " " + box[1] + " " + box[2] + " " + (STRIP_Y + 34)
    );

    var parts = [];
    var labels = [];

    Object.keys(geo.states).sort().forEach(function (code) {
      var shape = geo.states[code];
      parts.push(shapeMarkup(code, shape.name, shape.d));
      if (shape.centroid) {
        labels.push(
          '<text class="state-label" x="' + shape.centroid[0] +
          '" y="' + (shape.centroid[1] + 3.5) + '" text-anchor="middle">' +
          KYC.escapeHtml(code) + "</text>"
        );
      }
    });

    // Territories are not in the atlas - three of them sit thousands of miles
    // outside the frame - so they get a labelled strip. The shapes are
    // schematic and the caption says so.
    var strip = [
      '<text class="territory-caption" x="' + (STRIP_LEFT + 100) + '" y="' +
      (STRIP_Y - 10) + '" text-anchor="middle">' +
      "Territories &amp; D.C. (not to scale)</text>",
    ];
    (geo.territories || []).forEach(function (territory, i) {
      var x = STRIP_LEFT + i * STRIP_STEP;
      strip.push(
        '<g transform="translate(' + x + "," + STRIP_Y + ')">' +
        shapeMarkup(territory.code, territory.name, territory.d, null, "state--detached") +
        '<text class="state-label" x="20" y="44" text-anchor="middle">' +
        KYC.escapeHtml(territory.code) + "</text></g>"
      );
    });

    svg.innerHTML =
      '<g id="mapStates">' + parts.join("") + "</g>" +
      '<g aria-hidden="true">' + labels.join("") + "</g>" +
      '<g id="mapTerritories">' + strip.join("") + "</g>";
  }

  function paint() {
    Array.prototype.forEach.call(
      doc.querySelectorAll("#usMap .state"),
      function (node) {
        var code = node.getAttribute("data-state");
        var look = appearance(code);
        node.style.fill = look.fill;
        node.setAttribute("aria-pressed", String(code === selected));
        var title = node.querySelector("title");
        if (title) title.textContent = look.text;
        node.setAttribute("aria-label", look.text);
      }
    );
  }

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

  function rowBadge(item) {
    var status = String(item.status || "").toLowerCase();
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
    return [
      '<button type="button" class="person-row" data-id="',
      KYC.escapeAttr(item.id), '">',
      '<img src="', KYC.escapeAttr(KYC.portraitSrc(item)),
      '" alt="" loading="lazy" decoding="async" data-photo-idx="0" data-profile="',
      KYC.escapeAttr(item.id), '">',
      '<span class="who">',
      '<span class="name truncate">', KYC.escapeHtml(item.name), "</span>",
      '<span class="office">', KYC.escapeHtml(item.officeLabel), "</span>",
      '<span class="party ', KYC.partyClass(item), '">',
      KYC.escapeHtml(item.party), "</span>",
      "</span>",
      rowBadge(item),
      KYC.icon("chevron"),
      "</button>",
    ].join("");
  }

  function showPanel(code) {
    var list = doc.getElementById("delegation");
    var counts = tally(code);
    var people = forMode(code).slice();

    doc.getElementById("panelState").textContent =
      (geo.states[code] && geo.states[code].name) ||
      ((geo.territories || []).filter(function (t) { return t.code === code; })[0] || {}).name ||
      code;
    doc.getElementById("panelMode").textContent = MODE_TITLE[mode];

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
    var seated = people.filter(function (x) { return !x.isCandidate; }).sort(order);
    var running = people.filter(function (x) { return x.isCandidate; }).sort(order);

    /* Texas has 37 representatives and 191 filed challengers. Listing all 228
     * in one scroll buries the delegation the reader clicked the state to
     * see, so the challengers sit behind a count they can open. */
    var html = "";
    if (seated.length) {
      html += '<p class="panel-subhead">' +
        (mode === "senate2026" ? "Seat held by" : "Currently seated") +
        " <span>" + seated.length + "</span></p>" +
        seated.map(personRow).join("");
    }
    if (running.length) {
      html +=
        '<button type="button" class="panel-subhead expander" id="showChallengers"' +
        ' aria-expanded="false" aria-controls="challengerRows">' +
        KYC.icon("chevron") + " 2026 challengers <span>" + running.length + "</span>" +
        "</button>" +
        '<div id="challengerRows" hidden>' + running.map(personRow).join("") + "</div>";
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

  function select(code) {
    if (!code) return;
    selected = code;
    paint();
    showPanel(code);
    var picker = doc.getElementById("mapStateSelect");
    if (picker && picker.value !== code) picker.value = code;
  }

  function setMode(next) {
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
    paint();
    if (selected) showPanel(selected);
  }

  /* ----------------------------------------------------------------- boot */

  function initStatePicker() {
    var picker = doc.getElementById("mapStateSelect");
    if (!picker) return;
    var codes = Object.keys(geo.states).concat(
      (geo.territories || []).map(function (t) { return t.code; })
    );
    codes.sort().forEach(function (code) {
      var option = doc.createElement("option");
      option.value = code;
      option.textContent = code;
      picker.appendChild(option);
    });
    picker.addEventListener("change", function () {
      if (picker.value) select(picker.value);
    });
  }

  KYC.ready(function () {
    if (!Object.keys(geo.states).length) {
      doc.getElementById("mapStage").innerHTML =
        '<div class="empty-state">' + KYC.icon("info") +
        "<h3>Map geometry did not load</h3>" +
        "<p>Run <code>python build_profile_site.py geo</code> to regenerate " +
        "<code>data/geo.js</code>.</p></div>";
      return;
    }

    KYC.profile.ensure();
    drawMap();
    initStatePicker();
    setMode("senate");

    var svg = doc.getElementById("usMap");
    svg.addEventListener("click", function (event) {
      var shape = event.target.closest("[data-state]");
      if (shape) select(shape.getAttribute("data-state"));
    });
    // SVG elements are not buttons, so Enter and Space have to be wired up.
    svg.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" && event.key !== " ") return;
      var shape = event.target.closest("[data-state]");
      if (!shape) return;
      event.preventDefault();
      select(shape.getAttribute("data-state"));
    });

    doc.querySelector(".segmented").addEventListener("click", function (event) {
      var button = event.target.closest("[data-mode]");
      if (button) setMode(button.getAttribute("data-mode"));
    });

    doc.getElementById("delegation").addEventListener("click", function (event) {
      var row = event.target.closest("[data-id]");
      if (row) KYC.profile.open(row.getAttribute("data-id"));
    });

    KYC.router.onChange(function () {
      var route = KYC.router.read();
      if (route.view === "profile") KYC.profile.open(route.id, { fromRoute: true });
      else if (KYC.profile.isOpen()) KYC.profile.close();
    });
    var initial = KYC.router.read();
    if (initial.view === "profile") {
      KYC.profile.open(initial.id, { fromRoute: true });
    } else if (initial.params.state) {
      select(initial.params.state);
    }
  });
})(window);
