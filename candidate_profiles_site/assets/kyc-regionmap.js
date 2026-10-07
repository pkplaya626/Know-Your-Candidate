/* A map of regions inside one state: legislative districts now, counties
 * and towns next - any set of shapes keyed by any id.
 *
 * It draws the way the congressional district pages do (kyc-districts.js),
 * which is where these rules were learned:
 *   - each shape is defined once in a hidden <defs>, and every view - the
 *     statewide map and its close-ups - is <use> references to it;
 *   - every word is page text over the map, never SVG text (rule 46), 11px
 *     at whatever width the map is drawn (rule 43);
 *   - a shape too small to label statewide is labelled in a close-up inset
 *     the build planned for a phone-width map (kyc/districts.insets);
 *   - one draw per width (rule 45); a resize redraws, a pick only repaints.
 *
 *   var map = KYC.regionmap.create(target, {
 *     viewBox, regions: {id: {d, at, box, room, label}}, insets, outline, mesh,
 *     look: function (id) { return { cls: "party-r", title: "..." }; },
 *     onSelect: function (id) {},
<<<<<<< HEAD
 *     // Optional points over the regions - a state's cities - each a dot a
 *     // few pixels across at any width, its name page text in a <title>.
=======
 *     // Optional points over the regions - a state's cities and towns -
 *     // each a dot a few pixels across at any width. A dot's name is its
 *     // <title>, never SVG text (rule 46).
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
 *     dots: function () { return [{ id, at: [x, y], cls, title }]; },
 *     onDot: function (id) {},
 *   });
 *   map.render();
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;

  var LABEL_PX = 11;
  /* Clear room a label needs around its point, in screen pixels: half an
   * 11px label and its backing (kyc/districts.LABEL_ROOM_PX). */
  var LABEL_ROOM = 6.5;
  var DESIGN = 620;
  var counter = 0;

  function create(target, opts) {
    var prefix = "kycr" + (++counter) + "-";
    var regions = opts.regions || {};
    var ids = Object.keys(regions).sort(function (a, b) {
      return a.localeCompare(b, "en", { numeric: true });
    });
    var drawnAt = Math.max(280, target.clientWidth || DESIGN);
    var selected = "";
    var selectedDot = "";
    /* A dot's radius on screen, in pixels; the picked one larger. */
<<<<<<< HEAD
    var DOT_PX = 3.2;
=======
    var DOT_PX = 3.5;
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd

    function meets(box, frame) {
      return box[0] < frame[0] + frame[2] && box[2] > frame[0] &&
        box[1] < frame[1] + frame[3] && box[3] > frame[1];
    }

    function within(at, frame) {
      return at[0] >= frame[0] && at[0] <= frame[0] + frame[2] &&
        at[1] >= frame[1] && at[1] <= frame[1] + frame[3];
    }

    function defs() {
      return '<svg class="district-defs" aria-hidden="true"><defs>' + ids.map(function (id) {
        return '<path id="' + prefix + KYC.escapeAttr(id) + '" d="' + regions[id].d + '"/>';
      }).join("") + (opts.outline ? '<path id="' + prefix + 'outline" d="' + opts.outline + '"/>' : "") +
        "</defs></svg>";
    }

    function shapes(frame) {
      return ids.filter(function (id) { return meets(regions[id].box, frame); }).map(function (id) {
        var shown = opts.look(id);
        return '<use href="#' + prefix + KYC.escapeAttr(id) + '" class="region-shape ' +
          (shown.cls || "") + (id === selected ? " is-focus" : "") + '" data-region="' +
          KYC.escapeAttr(id) + '"><title>' + KYC.escapeHtml(shown.title || id) + "</title></use>";
      }).join("");
    }

    function labels(frame, px, mine) {
      return '<div class="map-labels" aria-hidden="true">' + mine.map(function (id) {
        var r = regions[id];
        var picked = id === selected;
        if (!r.label || (!picked && r.room * px < LABEL_ROOM)) return "";
        return '<span class="map-label district-num' + (picked ? " is-focus" : "") +
          ' anchor-middle" style="left:' + ((r.at[0] - frame[0]) / frame[2] * 100).toFixed(3) +
          "%;top:" + ((r.at[1] - frame[1]) / frame[3] * 100).toFixed(3) + "%;font-size:" +
          (picked ? 13 : LABEL_PX) + 'px">' + KYC.escapeHtml(r.label) + "</span>";
      }).join("") + "</div>";
    }

    function dots(frame, px) {
      if (!opts.dots) return "";
<<<<<<< HEAD
      return '<g class="map-dots">' + opts.dots().filter(function (d) {
        return within(d.at, frame);
      }).map(function (d) {
        var picked = d.id === selectedDot;
        return '<circle class="map-dot ' + (d.cls || "") + (picked ? " is-focus" : "") + '" cx="' +
          d.at[0] + '" cy="' + d.at[1] + '" r="' + ((picked ? DOT_PX * 1.7 : DOT_PX) / px).toFixed(2) +
=======
      var list = opts.dots();
      if (!list.length) return "";
      // The picked dot last, so it is drawn over its neighbours.
      return '<g class="map-dots">' + list.filter(function (d) {
        return d.id !== selectedDot && within(d.at, frame);
      }).concat(list.filter(function (d) {
        return d.id === selectedDot && within(d.at, frame);
      })).map(function (d) {
        var picked = d.id === selectedDot;
        return '<circle class="map-dot ' + (d.cls || "") + (picked ? " is-focus" : "") + '" cx="' +
          d.at[0] + '" cy="' + d.at[1] + '" r="' + ((picked ? DOT_PX * 1.6 : DOT_PX) / px).toFixed(2) +
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
          '" data-dot="' + KYC.escapeAttr(d.id) + '"><title>' + KYC.escapeHtml(d.title || d.id) +
          "</title></circle>";
      }).join("") + "</g>";
    }

    function view(frame, cls, label, px) {
      var mine = ids.filter(function (id) { return within(regions[id].at, frame); });
      var outline = opts.outline ? '<use href="#' + prefix + 'outline" class="state-line"/>' : "";
      var mesh = opts.mesh ? '<path class="county-line" d="' + opts.mesh + '"/>' : "";
      var lines = cls === "district-statewide" ? (opts.insets || []).map(function (inset) {
        var b = inset.box;
        return '<rect class="inset-outline" x="' + b[0] + '" y="' + b[1] + '" width="' + b[2] +
          '" height="' + b[3] + '"/>';
      }).join("") : "";
      return '<div class="map-frame"><svg class="district-map ' + cls + '" viewBox="' +
        frame.map(function (v) { return (+v).toFixed(1); }).join(" ") + '" role="img" aria-label="' +
        KYC.escapeAttr(label) + '"><g class="district-shapes">' + shapes(frame) + "</g>" + mesh +
        outline + lines + dots(frame, px) + "</svg>" + labels(frame, px, mine) + "</div>";
    }

    /* Each inset as wide as it needs for every label in it, or the width
     * available; drawn narrower than it needs, it is followed by the closer
     * insets the build planned for that case. */
    function insetFigures(list) {
      return list.map(function (inset) {
        var width = Math.min(drawnAt, inset.width);
        return '<figure class="inset" style="width:' + Math.round(width) + 'px">' +
          view(inset.box, "district-inset", inset.title, width / inset.box[2]) +
          "<figcaption>" + KYC.escapeHtml(inset.title) + "</figcaption></figure>" +
          (width < inset.fits ? insetFigures(inset.detail || []) : "");
      }).join("");
    }

    function render() {
      var frame = opts.viewBox;
      target.innerHTML = defs() +
        view(frame, "district-statewide", opts.title || "Map", drawnAt / frame[2]) +
        ((opts.insets || []).length ? '<div class="inset-row">' + insetFigures(opts.insets) + "</div>" : "");
    }

    /* A pick repaints the fills and labels it changes, not the whole map. */
    function setSelected(id) {
      selected = id || "";
      render();
    }

<<<<<<< HEAD
    /* A pick of a dot repaints the map with it larger. */
=======
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
    function setSelectedDot(id) {
      selectedDot = id || "";
      render();
    }

<<<<<<< HEAD
=======
    /* A region and a dot picked together, in one draw (rule 45). */
    function select(region, dot) {
      selected = region || "";
      selectedDot = dot || "";
      render();
    }

>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
    target.addEventListener("click", function (event) {
      var dot = event.target.closest("[data-dot]");
      if (dot && opts.onDot) {
        opts.onDot(dot.getAttribute("data-dot"));
        return;
      }
      var shape = event.target.closest("[data-region]");
      if (shape && opts.onSelect) opts.onSelect(shape.getAttribute("data-region"));
    });

    if (global.ResizeObserver) {
      var redraw = KYC.debounce(function () {
        var width = target.clientWidth;
        if (!width || Math.abs(width - drawnAt) <= 4) return;
        drawnAt = Math.max(280, width);
        render();
      }, 120);
      new global.ResizeObserver(redraw).observe(target);
    }

    return {
      render: render,
      setSelected: setSelected,
      setSelectedDot: setSelectedDot,
<<<<<<< HEAD
=======
      select: select,
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
      ids: function () { return ids.slice(); },
    };
  }

  KYC.regionmap = { create: create };
})(window);
