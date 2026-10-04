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
  var STRIP_LEFT = 366;

  /* State codes are drawn 11px tall on screen at whatever width the map is
   * drawn. They were 10 map units, which a phone draws 3.8px tall - at weight
   * 800, on a 2.5-unit halo, a glow rather than a letter. A code goes inside
   * its state where it fits (geo.py's labelRoom is the half-height of the
   * biggest code-shaped box at the label point; FIT_PX is half an 11px
   * code's capitals). The small states that do not fit are named in boxes of
   * their own colour, out in the Atlantic, or beside Hawaii - and the boxes
   * can be tapped, because a finger cannot find Rhode Island on a phone. */
  var LABEL_PX = 11;
  var FIT_PX = 3.6;
  /* East of this x, a state that does not fit goes to the Atlantic column,
   * which starts south of Long Island and Cape Cod. */
  var EAST = 780;
  var COLUMN_TOP = 212;
  /* The width the map is drawn at; 760 until layout says otherwise (and in
   * a test, which has no layout). */
  var drawnAt = 760;

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
        defender.name + (defender.seekingReelection2026 ? " running" :
          defender.contestLabel ? " running for " + defender.contestLabel :
          defender.alsoRunningSeat ? " running for " + defender.alsoRunningSeat :
          " not running") + ")",
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
    var px = drawnAt / box[2];
    var size = LABEL_PX / px;
    var strip = geo.territories || [];
    var inStrip = strip.map(function (t) { return t.code; });

    // Every word on the map is page text in a layer over it, not SVG text:
    // Samsung Internet's dark mode lightens whatever is dark inside an SVG,
    // so a code's dark halo came out as light as the code and bloomed. Page
    // text on a page background is darkened and lightened predictably.
    // Positions are in map units here and become percentages of the frame.
    var labels = [];
    function label(x, y, html, cls, extra) {
      labels.push({ x: x, y: y, html: html, cls: cls, extra: extra || "" });
    }

    // A callout: the state's code in a box of its colour, joined to it.
    var w = size * 2.3;
    var h = size * 1.4;
    var lines = [];
    function callout(code, cx, cy) {
      var at = geo.states[code].label;
      lines.push('<line class="callout-line" x1="' + at[0] + '" y1="' + at[1] + '" x2="' +
        (cx - w / 2).toFixed(1) + '" y2="' + cy.toFixed(1) + '"/>');
      label(cx, cy, KYC.escapeHtml(code), "map-callout",
        ' data-state="' + KYC.escapeAttr(code) + '"');
    }

    var parts = [];
    var column = [];
    var beside = [];
    Object.keys(geo.states).sort().forEach(function (code) {
      var shape = geo.states[code];
      parts.push(shapeMarkup(code, shape.name, shape.d));
      // The build places each label at the point farthest from the state's
      // edges, not at its centroid (kyc/geo.py polylabel).
      if (!shape.label) return;
      if ((shape.labelRoom || 0) * px >= FIT_PX) {
        label(shape.label[0], shape.label[1], KYC.escapeHtml(code), "state-code");
      } else if (inStrip.indexOf(code) === -1) {
        // D.C. is named in the strip below, so it needs no callout.
        (shape.label[0] >= EAST ? column : beside).push(code);
      }
    });

    var gap = h + 3 / px;
    var cx = box[2] - 6 / px - w / 2;
    var y = -Infinity;
    column.sort(function (a, b) { return geo.states[a].label[1] - geo.states[b].label[1]; })
      .forEach(function (code) {
        y = Math.max(geo.states[code].label[1], y + gap, COLUMN_TOP + h / 2);
        callout(code, cx, y);
      });
    beside.forEach(function (code) {
      var shape = geo.states[code];
      callout(code, shape.bounds[2] + 6 / px + w / 2, shape.label[1]);
    });

    // Territories are not in the atlas - three of them sit thousands of miles
    // outside the frame - so they get a strip of schematic shapes, at least
    // 28px across so each can be tapped, below the column of callouts.
    var tile = Math.max(40, 28 / px);
    var step = tile + Math.max(6, 10 / px);
    var top = Math.max(STRIP_Y, y + h / 2 + 8 / px);
    var tileHeight = tile * 35 / 40;
    label(STRIP_LEFT - 10 / px, top + tileHeight / 2,
      "Territories &amp; D.C.<br>(not to scale)", "territory-caption anchor-end");
    var territories = [];
    strip.forEach(function (territory, i) {
      var x = STRIP_LEFT + i * step;
      territories.push(
        '<g transform="translate(' + x.toFixed(1) + "," + top.toFixed(1) + ") scale(" +
        (tile / 40).toFixed(3) + ')">' +
        shapeMarkup(territory.code, territory.name, territory.d, null, "state--detached") + "</g>");
      label(x + tile / 2, top + tileHeight + size * 0.8, KYC.escapeHtml(territory.code),
        "territory-label");
    });

    // The strip sits below the projected atlas, so the viewBox is taller
    // than the atlas itself.
    var height = top + tileHeight + size * 1.6;
    svg.setAttribute("viewBox", box[0] + " " + box[1] + " " + box[2] + " " + height.toFixed(1));
    svg.innerHTML =
      '<g id="mapStates">' + parts.join("") + "</g>" +
      '<g aria-hidden="true">' + lines.join("") + "</g>" +
      '<g id="mapTerritories">' + territories.join("") + "</g>";
    labelLayer().innerHTML = labels.map(function (l) {
      return '<span class="map-label ' + l.cls + '"' + l.extra + ' style="left:' +
        ((l.x - box[0]) / box[2] * 100).toFixed(3) + "%;top:" +
        ((l.y - box[1]) / height * 100).toFixed(3) + '%">' + l.html + "</span>";
    }).join("");
    placeLabels();
  }

  /** The layer the map's words are written in, made once. */
  function labelLayer() {
    var layer = doc.getElementById("mapLabels");
    if (!layer) {
      layer = doc.createElement("div");
      layer.id = "mapLabels";
      layer.className = "map-labels us-map-labels";
      layer.setAttribute("aria-hidden", "true");
      doc.getElementById("mapStage").appendChild(layer);
    }
    return layer;
  }

  /** Lay the word layer exactly over the drawn map: the SVG letterboxes the
   *  map when its height is capped, so the layer is the map's own box inside
   *  the SVG's, not the SVG's. */
  function placeLabels() {
    var svg = doc.getElementById("usMap");
    var layer = labelLayer();
    var stage = doc.getElementById("mapStage");
    var rect = svg.getBoundingClientRect();
    var view = (svg.getAttribute("viewBox") || "").split(" ").map(Number);
    if (!rect.width || view.length !== 4 || !view[3]) {
      layer.style.cssText = "";
      return;
    }
    var width = Math.min(rect.width, rect.height * view[2] / view[3] || rect.width);
    var height = width * view[3] / view[2];
    var outer = stage.getBoundingClientRect();
    layer.style.left = (rect.left - outer.left + (rect.width - width) / 2).toFixed(1) + "px";
    layer.style.top = (rect.top - outer.top + (rect.height - height) / 2).toFixed(1) + "px";
    layer.style.width = width.toFixed(1) + "px";
    layer.style.height = height.toFixed(1) + "px";
    layer.style.right = "auto";
    layer.style.bottom = "auto";
  }

  /** How wide the map is drawn, in CSS pixels; 0 without layout. The SVG
   *  letterboxes the map when its height is capped (a phone in landscape),
   *  so this is the narrower of its width and what its height allows. */
  function mapWidth() {
    var svg = doc.getElementById("usMap");
    if (!svg) return 0;
    var rect = svg.getBoundingClientRect();
    var view = (svg.getAttribute("viewBox") || "").split(" ").map(Number);
    var width = view.length === 4 && view[3] > 0 && rect.height > 0
      ? Math.min(rect.width, rect.height * view[2] / view[3]) : rect.width;
    return width > 40 ? Math.round(width) : 0;
  }

  /** Redraw when the map's width changes - a rotated phone, a resized
   *  window - so the codes stay 11px. */
  function watchWidth() {
    if (!global.ResizeObserver) return;
    var redraw = KYC.debounce(function () {
      var width = mapWidth();
      if (!width || Math.abs(width - drawnAt) <= 4) return placeLabels();
      drawnAt = width;
      drawMap();
      paint();
    }, 120);
    new global.ResizeObserver(redraw).observe(doc.getElementById("mapStage"));
  }

  /** On a phone the delegation follows the map down the page. After a tap,
   *  bring it into view if none of it shows. */
  function revealPanel() {
    var panel = doc.querySelector(".detail-panel");
    if (!panel || !global.matchMedia || !global.matchMedia("(max-width: 1000px)").matches) return;
    if (panel.getBoundingClientRect().top > global.innerHeight - 80) {
      panel.scrollIntoView({ behavior: "smooth", block: "start" });
    }
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
    Array.prototype.forEach.call(
      doc.querySelectorAll("#mapLabels .map-callout"),
      function (node) {
        var code = node.getAttribute("data-state");
        node.style.background = appearance(code).fill;
        node.classList.toggle("is-selected", code === selected);
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

    doc.getElementById("panelState").textContent =
      (geo.states[code] && geo.states[code].name) ||
      ((geo.territories || []).filter(function (t) { return t.code === code; })[0] || {}).name ||
      code;
    doc.getElementById("panelMode").textContent = MODE_TITLE[mode];
    var pageLink = doc.getElementById("panelStateLink");
    if (pageLink) {
      pageLink.hidden = false;
      pageLink.href = KYC.stateUrl(code);
      pageLink.textContent = "Open the " + KYC.stateName(code) + " page \u203a";
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
    paint();
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
    paint();
    if (selected) showPanel(selected);
    if (!(opts && opts.fromRoute)) {
      KYC.router.writeFilters({ state: selected, mode: mode === "senate" ? "" : mode });
    }
  }

  /* ----------------------------------------------------------------- boot */

  function hasShape(code) {
    return !!code && (!!geo.states[code] ||
      (geo.territories || []).some(function (t) { return t.code === code; }));
  }

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
      if (!picker.value) return;
      select(picker.value);
      revealPanel();
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
    drawnAt = mapWidth() || drawnAt;
    drawMap();
    watchWidth();
    initStatePicker();
    /* Read the incoming route before anything writes one. Boot used to call
     * setMode("senate") as a user action, which wrote "#/" over the address
     * before it was read - so map.html#/?state=TX, every state page's map
     * link and every shared profile link all landed on a blank map. */
    var initial = KYC.router.read();
    setMode(MODE_TITLE[initial.params.mode] ? initial.params.mode : "senate",
            { fromRoute: true });

    var svg = doc.getElementById("usMap");
    // On the stage, not the SVG: a small state's callout is page text
    // over the map, and picks its state too.
    doc.getElementById("mapStage").addEventListener("click", function (event) {
      var shape = event.target.closest("[data-state]");
      if (!shape) return;
      select(shape.getAttribute("data-state"));
      revealPanel();
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
      if (person && hasShape(person.state)) select(person.state, { fromRoute: true });
      KYC.profile.open(initial.id, { fromRoute: true });
    } else if (initial.params.state) {
      select(initial.params.state, { fromRoute: true });
    }
  });
})(window);
