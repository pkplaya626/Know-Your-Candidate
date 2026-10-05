/* The map of the United States, drawn the same way wherever it appears.
 *
 * The partisan map (kyc-map.js) and the guide's maps (kyc-guide.js) both draw
 * the states from window.kycGeo - SVG path data decoded at build time by
 * kyc/geo.py - and differ only in what colours a state and what happens when
 * one is picked. That much is theirs; the drawing is here, once (rule 12),
 * so a fix to the labels or the territory strip reaches every map.
 *
 *   var map = KYC.usmap.create({
 *     look: function (code) { return { fill: "var(--party-r)", text: "TX: ...",
 *                                      ink: "var(--text)" }; },  // ink: a callout's text, optional
 *     label: function (code) { return code; },   // optional: the word drawn on a state
 *     onSelect: function (code) { ... },          // a click, Enter or Space
 *   });
 *   map.draw(); map.paint();
 *
 * Every word on the map is page text in a layer over the SVG, never SVG text
 * (rule 46), and is written 11px tall at whatever width the map is drawn
 * (rule 43).
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;

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

  function create(opts) {
    var ids = {
      svg: opts.svg || "usMap",
      stage: opts.stage || "mapStage",
      layer: opts.layer || "mapLabels",
    };
    var geo = global.kycGeo || { states: {}, territories: [], viewBox: [0, 0, 975, 610] };
    var look = opts.look;
    var labelText = opts.label || function (code) { return code; };
    /* The width the map is drawn at; 760 until layout says otherwise (and in
     * a test, which has no layout). */
    var drawnAt = 760;
    var selected = "";

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

    function draw() {
      var svg = doc.getElementById(ids.svg);
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

      // A callout: the state's word in a box of its colour, joined to it.
      var w = size * 2.3;
      var h = size * 1.4;
      var lines = [];
      function callout(code, cx, cy) {
        var at = geo.states[code].label;
        lines.push('<line class="callout-line" x1="' + at[0] + '" y1="' + at[1] + '" x2="' +
          (cx - w / 2).toFixed(1) + '" y2="' + cy.toFixed(1) + '"/>');
        label(cx, cy, KYC.escapeHtml(labelText(code)), "map-callout",
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
          label(shape.label[0], shape.label[1], KYC.escapeHtml(labelText(code)), "state-code");
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
        label(x + tile / 2, top + tileHeight + size * 0.8, KYC.escapeHtml(labelText(territory.code)),
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
      var layer = doc.getElementById(ids.layer);
      if (!layer) {
        layer = doc.createElement("div");
        layer.id = ids.layer;
        layer.className = "map-labels us-map-labels";
        layer.setAttribute("aria-hidden", "true");
        doc.getElementById(ids.stage).appendChild(layer);
      }
      return layer;
    }

    /** Lay the word layer exactly over the drawn map: the SVG letterboxes the
     *  map when its height is capped, so the layer is the map's own box inside
     *  the SVG's, not the SVG's. */
    function placeLabels() {
      var svg = doc.getElementById(ids.svg);
      var layer = labelLayer();
      var stage = doc.getElementById(ids.stage);
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
      var svg = doc.getElementById(ids.svg);
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
        draw();
        paint();
      }, 120);
      new global.ResizeObserver(redraw).observe(doc.getElementById(ids.stage));
    }

    function paint() {
      Array.prototype.forEach.call(
        doc.querySelectorAll("#" + ids.svg + " .state"),
        function (node) {
          var code = node.getAttribute("data-state");
          var shown = look(code);
          node.style.fill = shown.fill;
          node.setAttribute("aria-pressed", String(code === selected));
          var title = node.querySelector("title");
          if (title) title.textContent = shown.text;
          node.setAttribute("aria-label", shown.text);
        }
      );
      Array.prototype.forEach.call(
        doc.querySelectorAll("#" + ids.layer + " .map-callout"),
        function (node) {
          var code = node.getAttribute("data-state");
          var shown = look(code);
          node.style.background = shown.fill;
          // A callout's word is dark on the bright fills of the partisan
          // map; a faint fill names its own ink so the word stays legible.
          node.style.color = shown.ink || "";
          node.classList.toggle("is-selected", code === selected);
        }
      );
    }

    /** On a phone the panel follows the map down the page. After a tap,
     *  bring it into view if none of it shows. */
    function reveal() {
      var panel = doc.querySelector(".detail-panel");
      if (!panel || !global.matchMedia || !global.matchMedia("(max-width: 1000px)").matches) return;
      if (panel.getBoundingClientRect().top > global.innerHeight - 80) {
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }

    function hasShape(code) {
      return !!code && (!!geo.states[code] ||
        (geo.territories || []).some(function (t) { return t.code === code; }));
    }

    /** "TX" -> "Texas", from the geometry. */
    function name(code) {
      return (geo.states[code] && geo.states[code].name) ||
        ((geo.territories || []).filter(function (t) { return t.code === code; })[0] || {}).name ||
        code;
    }

    function codes() {
      return Object.keys(geo.states).concat((geo.territories || []).map(function (t) { return t.code; }));
    }

    /** Draw at the laid-out width, follow it, and wire the pointer and the
     *  keyboard. Picking a state calls opts.onSelect; the caller decides
     *  what that means and calls setSelected(). */
    function start() {
      drawnAt = mapWidth() || drawnAt;
      draw();
      watchWidth();
      // On the stage, not the SVG: a small state's callout is page text
      // over the map, and picks its state too.
      doc.getElementById(ids.stage).addEventListener("click", function (event) {
        var shape = event.target.closest("[data-state]");
        if (!shape || !opts.onSelect) return;
        opts.onSelect(shape.getAttribute("data-state"));
        reveal();
      });
      // SVG elements are not buttons, so Enter and Space have to be wired up.
      doc.getElementById(ids.svg).addEventListener("keydown", function (event) {
        if (event.key !== "Enter" && event.key !== " ") return;
        var shape = event.target.closest("[data-state]");
        if (!shape || !opts.onSelect) return;
        event.preventDefault();
        opts.onSelect(shape.getAttribute("data-state"));
      });
    }

    return {
      start: start,
      draw: draw,
      paint: paint,
      reveal: reveal,
      hasShape: hasShape,
      name: name,
      codes: codes,
      setSelected: function (code) { selected = code || ""; paint(); },
      selected: function () { return selected; },
      loaded: function () { return Object.keys(geo.states).length > 0; },
    };
  }

  KYC.usmap = { create: create };
})(window);
