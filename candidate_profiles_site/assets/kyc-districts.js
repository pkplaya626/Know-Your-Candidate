/* Know Your Candidate - a state's House map before and after a redistricting.
 *
 * The lines come from window.kycDistricts: SVG paths projected at build time
 * by kyc/districts.py, which also measured how much of each new district's
 * area came from each old one. Everything said about a person - who holds a
 * seat, who is running where, who is on the November ballot - comes from
 * profiles.js, the same records the grid and the state pages render, so this
 * page cannot disagree with them about anyone.
 *
 * Each district is drawn once, into one hidden <defs>, and every view - the
 * statewide map, the metro insets, the close-up - is a set of <use>
 * references to it. Fills are set on the <use>, which the shared path
 * inherits, so a district can be highlighted in one view and not another.
 *
 * Which districts are picked out lives in the address (#/?d=3,6), so every
 * view can be shared.
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;
  var code = doc.body.getAttribute("data-state") || "";
  var state = (global.kycDistricts || {})[code] || null;
  var data = global.legislatorsData || [];
  var races = global.kycRaces || [];

  /* Text is sized for a map drawn this many pixels wide; SVG scales it with
   * the map, so it stays in proportion on a phone. */
  var DESIGN = 620;
  /* One colour per picked district; they are deliberately not the party
   * colours, which mean something everywhere else on the site. */
  var MAX_FOCUS = 3;
  /* Overlaps smaller than this are not listed: two maps simplified
   * separately leave slivers along every shared line. */
  var MIN_SHARE = 0.01;
  var TOWN_LABELS = 14;

  var focus = [];
  var OFF_BALLOT = { eliminated: true, withdrawn: true, unlisted: true };

  function el(id) {
    return doc.getElementById(id);
  }

  function seat(n) {
    return code + "-" + n;
  }

  function numbers(plan) {
    return Object.keys(plan.districts).map(Number).sort(function (a, b) { return a - b; });
  }

  function newPlan() {
    return state.plans[state.plans.length - 1];
  }

  function otherPlan(plan) {
    return state.plans[0] === plan ? state.plans[1] : state.plans[0];
  }

  function pct(share) {
    var whole = Math.round(share * 100);
    // A share is measured on simplified lines; it is never quite all.
    return (whole >= 100 && share < 1 ? 99 : whole) + "%";
  }

  /* --------------------------------------------------------- the people */

  /** Sitting House members by the district they hold - the old map's. */
  var holdersOf = {};
  /** The 2026 House race for each new district. */
  var raceOf = {};

  function indexPeople() {
    data.forEach(function (p) {
      if (p.isCandidate || p.state !== code || p.chamber.indexOf("House") === -1) return;
      (holdersOf[p.districtNum] || (holdersOf[p.districtNum] = [])).push(p);
    });
    races.forEach(function (r) {
      if (r.chamber === "House" && r.state === code) raceOf[r.district] = r;
    });
  }

  /** Who is running in a new district: the race's people, less a member
   *  who holds the old seat of that number but is running elsewhere. Once
   *  the primary is decided, only those on the November ballot. */
  function running(n) {
    var race = raceOf[n];
    if (!race) return [];
    var seen = {};
    return race.incumbentIds.concat(race.candidateIds).map(KYC.byId).filter(function (p) {
      if (!p || seen[p.id]) return false;
      seen[p.id] = true;
      if (!p.isCandidate && (p.contestRaceId || p.raceId) !== race.id) return false;
      var status = p.isCandidate ? p.raceStatus : KYC.contestStatus(p);
      if (race.settled) return status === "nominee" || status === "advanced";
      return !OFF_BALLOT[status];
    }).sort(function (a, b) {
      return (a.isCandidate ? 1 : 0) - (b.isCandidate ? 1 : 0) || a.name.localeCompare(b.name);
    });
  }

  /** Members holding one of this state's districts and running in another,
   *  from the pipeline's contestRaceId (rule 30). */
  function moves() {
    var byId = {};
    races.forEach(function (r) { byId[r.id] = r; });
    return data.filter(function (p) {
      return !p.isCandidate && p.state === code && p.chamber.indexOf("House") !== -1 &&
        KYC.runsElsewhere(p);
    }).map(function (p) {
      var race = byId[p.contestRaceId];
      return race && race.chamber === "House" && race.state === code
        ? { person: p, from: p.districtNum, to: race.district } : null;
    }).filter(Boolean);
  }

  /** Moves that share a district belong together: Bera's 6 -> 3 and
   *  Kiley's 3 -> 6 are one story, and one view. */
  function groups(list) {
    var parent = {};
    function find(n) {
      if (parent[n] === undefined) parent[n] = n;
      while (parent[n] !== n) {
        parent[n] = parent[parent[n]];
        n = parent[n];
      }
      return n;
    }
    list.forEach(function (m) { parent[find(m.from)] = find(m.to); });
    var byRoot = {};
    list.forEach(function (m) {
      var g = byRoot[find(m.from)] || (byRoot[find(m.from)] = { districts: [], moves: [] });
      g.moves.push(m);
      [m.from, m.to].forEach(function (n) {
        if (g.districts.indexOf(n) === -1) g.districts.push(n);
      });
    });
    return Object.keys(byRoot).map(function (key) {
      var g = byRoot[key];
      g.districts.sort(function (a, b) { return a - b; });
      g.moves.sort(function (a, b) { return a.from - b.from; });
      return g;
    }).sort(function (a, b) { return a.districts[0] - b.districts[0]; });
  }

  /* ----------------------------------------------------------- geometry */

  var ringCache = {};

  /** A district's rings, replayed from its relative path data. */
  function ringsOf(plan, n) {
    var key = plan.key + "-" + n;
    if (ringCache[key]) return ringCache[key];
    var rings = [];
    String(plan.districts[n].d).split("M").forEach(function (part) {
      var nums = part.match(/-?\d+(?:\.\d+)?/g);
      if (!nums || nums.length < 2) return;
      var x = +nums[0], y = +nums[1];
      var ring = [[x, y]];
      for (var i = 2; i + 1 < nums.length; i += 2) {
        x += +nums[i];
        y += +nums[i + 1];
        ring.push([x, y]);
      }
      rings.push(ring);
    });
    ringCache[key] = rings;
    return rings;
  }

  /** Even-odd point in polygon, so a hole counts as outside. */
  function contains(rings, x, y) {
    var hit = false;
    rings.forEach(function (ring) {
      for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
        if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) hit = !hit;
      }
    });
    return hit;
  }

  function within(point, frame, margin) {
    return point[0] >= frame[0] + margin && point[0] <= frame[0] + frame[2] - margin &&
      point[1] >= frame[1] + margin && point[1] <= frame[1] + frame[3] - margin;
  }

  function meets(box, frame) {
    return box[0] < frame[0] + frame[2] && box[2] > frame[0] &&
      box[1] < frame[1] + frame[3] && box[3] > frame[1];
  }

  /** Where to write a district's number inside *frame*: its own label
   *  point when that is in view, otherwise the roomiest visible point -
   *  the close-up crops old CA-3, which ran south to Death Valley. Returns
   *  [x, y, room] with room in map units, or null. */
  function labelAt(plan, n, frame, margin) {
    var district = plan.districts[n];
    if (within(district.at, frame, margin)) return [district.at[0], district.at[1], Infinity];
    var x0 = Math.max(district.box[0], frame[0] + margin);
    var y0 = Math.max(district.box[1], frame[1] + margin);
    var x1 = Math.min(district.box[2], frame[0] + frame[2] - margin);
    var y1 = Math.min(district.box[3], frame[1] + frame[3] - margin);
    if (x1 <= x0 || y1 <= y0) return null;
    var rings = ringsOf(plan, n);
    var steps = 16, cells = [];
    for (var i = 0; i <= steps; i++) {
      for (var j = 0; j <= steps; j++) {
        var x = x0 + (x1 - x0) * i / steps, y = y0 + (y1 - y0) * j / steps;
        cells.push([x, y, contains(rings, x, y)]);
      }
    }
    var best = null;
    cells.forEach(function (c) {
      if (!c[2]) return;
      // Room: the distance to the nearest outside sample or the frame edge.
      var room = Math.min(c[0] - frame[0], frame[0] + frame[2] - c[0],
                          c[1] - frame[1], frame[1] + frame[3] - c[1]);
      cells.forEach(function (o) {
        if (!o[2]) room = Math.min(room, Math.hypot(o[0] - c[0], o[1] - c[1]));
      });
      if (!best || room > best[2]) best = [c[0], c[1], room];
    });
    return best;
  }

  /* -------------------------------------------------------------- labels */

  function textBox(x, y, text, size, anchor) {
    var w = String(text).length * size * 0.6;
    var left = anchor === "middle" ? x - w / 2 : anchor === "end" ? x - w : x;
    return [left, y - size * 0.6, left + w, y + size * 0.6];
  }

  function collides(box, placed) {
    return placed.some(function (b) {
      return box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1];
    });
  }

  function fits(box, frame) {
    return box[0] >= frame[0] && box[2] <= frame[0] + frame[2] &&
      box[1] >= frame[1] && box[3] <= frame[1] + frame[3];
  }

  /* The anchor is always an attribute: a stylesheet rule would override a
   * presentation attribute, and a caption set beside a number would be
   * centred over it instead. */
  function text(cls, x, y, size, content, anchor) {
    return '<text class="' + cls + '" x="' + x.toFixed(1) + '" y="' + y.toFixed(1) +
      '" font-size="' + size.toFixed(2) + '" stroke-width="' + (size * 0.24).toFixed(2) +
      '" text-anchor="' + (anchor || "middle") + '">' + KYC.escapeHtml(content) + "</text>";
  }

  /* --------------------------------------------------------------- views */

  function pathId(plan, n) {
    return "kycd-" + plan.key + "-" + n;
  }

  function focusClass(n) {
    var at = focus.indexOf(n);
    return at === -1 ? "" : " is-focus focus-" + (at + 1);
  }

  function tip(plan, n) {
    var where = seat(n) + " on the " + plan.title;
    if (plan === newPlan()) {
      var names = running(n).map(function (p) { return p.name; });
      return names.length ? where + ": " + names.join(", ") + " on the ballot" : where;
    }
    var held = (holdersOf[n] || []).map(function (p) { return p.name; });
    return held.length ? where + ": held by " + held.join(", ") : where;
  }

  /** Every district meeting *frame*, as <use> elements. */
  function shapes(plan, frame) {
    return numbers(plan).filter(function (n) {
      return meets(plan.districts[n].box, frame);
    }).map(function (n) {
      return '<use href="#' + pathId(plan, n) + '" class="district-shape' + focusClass(n) +
        '" data-district="' + n + '"><title>' + KYC.escapeHtml(tip(plan, n)) + "</title></use>";
    }).join("");
  }

  function svg(frame, cls, label, body) {
    return '<svg class="district-map ' + cls + '" viewBox="' + frame.map(function (v) {
      return v.toFixed(1);
    }).join(" ") + '" role="img" aria-label="' + KYC.escapeAttr(label) + '">' + body + "</svg>";
  }

  function insetBoxes() {
    return state.insets.map(function (inset) { return inset.box; });
  }

  /** The whole state. Districts too small to number here are numbered in
   *  the metro insets instead, as on a printed atlas. */
  function statewide(plan) {
    var frame = state.viewBox.slice();
    var px = DESIGN / frame[2];
    var insets = insetBoxes();
    var labels = numbers(plan).map(function (n) {
      var district = plan.districts[n];
      var picked = focus.indexOf(n) !== -1;
      if (!picked) {
        if (insets.some(function (b) { return within(district.at, b, 0); })) return "";
        if (district.area * px * px < 380) return "";
      }
      return text("district-num" + focusClass(n), district.at[0], district.at[1],
                  (picked ? 15 : 11) / px, String(n));
    }).join("");
    var lines = insets.map(function (b) {
      return '<rect class="inset-outline" x="' + b[0] + '" y="' + b[1] + '" width="' + b[2] +
        '" height="' + b[3] + '"/>';
    }).join("");
    return svg(frame, "district-statewide",
      "All " + state.seats + " districts on the " + plan.title,
      '<g class="district-shapes">' + shapes(plan, frame) + "</g>" +
      '<use href="#kycd-outline" class="state-line"/>' + lines +
      '<g class="district-labels" aria-hidden="true">' + labels + "</g>");
  }

  function insets(plan) {
    var total = state.insets.reduce(function (sum, i) { return sum + i.box[2] / i.box[3]; }, 0);
    return '<div class="inset-row">' + state.insets.map(function (inset) {
      var frame = inset.box;
      var aspect = frame[2] / frame[3];
      var px = (DESIGN - 24) * (aspect / total) / frame[2];
      var placed = [];
      var labels = numbers(plan).filter(function (n) {
        return meets(plan.districts[n].box, frame);
      }).map(function (n) {
        var district = plan.districts[n];
        if (district.area * px * px < 30) return "";
        var at = labelAt(plan, n, frame, 9 / px);
        if (!at || at[2] * px < 7) return "";
        var size = (focus.indexOf(n) !== -1 ? 12 : 10) / px;
        var box = textBox(at[0], at[1], String(n), size, "middle");
        if (collides(box, placed)) return "";
        placed.push(box);
        return text("district-num" + focusClass(n), at[0], at[1], size, String(n));
      }).join("");
      return '<figure class="inset" style="flex-grow:' + aspect.toFixed(3) + '">' +
        svg(frame, "district-inset", inset.title + " on the " + plan.title,
          '<g class="district-shapes">' + shapes(plan, frame) + "</g>" +
          '<use href="#kycd-outline" class="state-line"/>' +
          '<g class="district-labels" aria-hidden="true">' + labels + "</g>") +
        "<figcaption>" + KYC.escapeHtml(inset.title) + "</figcaption></figure>";
    }).join("") + "</div>";
  }

  /** The frame for the close-up: where the picked districts run under the
   *  new map, padded, and never so small that simplified lines look blocky
   *  or so narrow that the two close-ups stop being comparable. */
  function closeupFrame() {
    var plan = newPlan();
    var box = null;
    focus.forEach(function (n) {
      var b = plan.districts[n].box;
      box = box ? [Math.min(box[0], b[0]), Math.min(box[1], b[1]),
                   Math.max(box[2], b[2]), Math.max(box[3], b[3])] : b.slice();
    });
    var w = box[2] - box[0], h = box[3] - box[1];
    var cx = (box[0] + box[2]) / 2, cy = (box[1] + box[3]) / 2;
    w = Math.max(w * 1.16, 70);
    h = Math.max(h * 1.16, 70);
    if (w / h > 1.45) h = w / 1.45;
    if (h / w > 1.25) w = h / 1.25;
    return [cx - w / 2, cy - h / 2, w, h];
  }

  /** Names for the picked districts on the close-up: who held the seat,
   *  or which members are running in it now. */
  function caption(plan, n) {
    var people = plan === newPlan()
      ? running(n).filter(function (p) { return !p.isCandidate; })
      : holdersOf[n] || [];
    return people.map(function (p) { return p.name; }).join(" · ");
  }

  function closeup(plan) {
    var frame = closeupFrame();
    var px = DESIGN / frame[2];
    var other = otherPlan(plan);
    var placed = [];
    var marks = [];
    var dots = [];
    var spots = {};
    var towns = 0;
    var tried = {};
    var year = (KYC.meta().election || {}).year || "";

    function free(box) {
      return fits(box, frame) && !collides(box, placed);
    }

    function number(n) {
      var picked = focus.indexOf(n) !== -1;
      var at = labelAt(plan, n, frame, 20 / px);
      if (!at || (!picked && at[2] * px < 16)) return;
      var size = (picked ? 30 : 17) / px;
      var box = textBox(at[0], at[1], String(n), size, "middle");
      if (!picked && collides(box, placed)) return;
      placed.push(box);
      marks.push(text("district-num" + focusClass(n), at[0], at[1], size, String(n)));
      spots[n] = [at[0], at[1], size];
    }

    /* Who held the seat, or who is running in it now: under its number,
     * else above it, else beside it - wherever the towns have left room. */
    function captionFor(n) {
      var spot = spots[n];
      var words = spot && caption(plan, n);
      if (!words) return;
      var name = 12.5 / px, role = 10.5 / px;
      var what = plan === newPlan() ? "running here in " + year : "holds this seat";
      var half = spot[2] * 0.95, aside = spot[2] * 0.45 + 6 / px;
      // [x, y of the name line, y of the role line, anchor]
      var options = [
        [spot[0], spot[1] + half, spot[1] + half + name * 1.2, "middle"],
        [spot[0], spot[1] - half - name * 1.2, spot[1] - half, "middle"],
        [spot[0] - aside, spot[1] - name * 0.6, spot[1] + name * 0.6, "end"],
        [spot[0] + aside, spot[1] - name * 0.6, spot[1] + name * 0.6, "start"],
      ];
      options.some(function (o) {
        var first = textBox(o[0], o[1], words, name, o[3]);
        if (!free(first)) return false;
        placed.push(first);
        marks.push(text("district-caption", o[0], o[1], name, words, o[3]));
        var second = textBox(o[0], o[2], what, role, o[3]);
        if (free(second)) {
          placed.push(second);
          marks.push(text("district-caption district-caption-role", o[0], o[2], role, what, o[3]));
        }
        return true;
      });
    }

    function dotBox(place) {
      return [place[1] - 3 / px, place[2] - 3 / px, place[1] + 3 / px, place[2] + 3 / px];
    }

    /* A town: its dot, and its name on whichever side has room. A town
     * whose dot was reserved passes that box, so it does not collide with
     * itself. */
    function town(place, reserved) {
      var x = place[1], y = place[2];
      tried[place[0]] = true;
      var dot = reserved || dotBox(place);
      if (!reserved && collides(dot, placed)) return false;
      var size = 11 / px, gap = 5 / px, lift = size * 0.85;
      var spot = [[gap, 0, "start"], [-gap, 0, "end"], [gap, -lift, "start"],
                  [gap, lift, "start"], [-gap, -lift, "end"], [-gap, lift, "end"]]
        .map(function (s) {
          return [x + s[0], y + s[1], s[2], textBox(x + s[0], y + s[1], place[0], size, s[2])];
        })
        .filter(function (s) { return free(s[3]); })[0];
      if (!spot) return false;
      if (!reserved) placed.push(dot);
      placed.push(spot[3]);
      dots.push('<circle class="town-dot" cx="' + x + '" cy="' + y + '" r="' +
        (2.6 / px).toFixed(2) + '" stroke-width="' + (1.2 / px).toFixed(2) + '"/>');
      marks.push(text("town-name", spot[0], spot[1], size, place[0], spot[2]));
      towns += 1;
      return true;
    }

    // The picked districts' numbers; then the biggest towns, so a reader
    // can find where they live; then who is running where; then the rest.
    focus.forEach(number);
    var inView = (state.places || []).filter(function (place) {
      return within([place[1], place[2]], frame, 12 / px);
    });
    // The biggest towns' dots go down before any of their names, so one
    // town's name never covers the next one's dot.
    var reserved = inView.slice(0, 8).filter(function (place) {
      return !collides(dotBox(place), placed);
    }).map(function (place) {
      var box = dotBox(place);
      placed.push(box);
      return [place, box];
    });
    reserved.forEach(function (pair) {
      if (!town(pair[0], pair[1])) placed.splice(placed.indexOf(pair[1]), 1);
    });
    focus.forEach(captionFor);
    numbers(plan).filter(function (n) {
      return focus.indexOf(n) === -1 && meets(plan.districts[n].box, frame);
    }).sort(function (a, b) {
      return plan.districts[b].area - plan.districts[a].area;
    }).forEach(number);
    inView.some(function (place) {
      if (!tried[place[0]]) town(place);
      return towns >= TOWN_LABELS;
    });

    state.counties.names.forEach(function (county) {
      if (county[3] * px * px < 9000 || !within([county[1], county[2]], frame, 0)) return;
      var words = county[0].toUpperCase() + " CO.";
      var size = 9.5 / px;
      var box = textBox(county[1], county[2], words, size, "middle");
      if (!fits(box, frame) || collides(box, placed)) return;
      placed.push(box);
      marks.unshift(text("county-name", county[1], county[2], size, words));
    });

    var ghosts = focus.map(function (n) {
      return '<use href="#' + pathId(other, n) + '" class="district-ghost-halo"/>' +
        '<use href="#' + pathId(other, n) + '" class="district-ghost focus-' +
        (focus.indexOf(n) + 1) + '"/>';
    }).join("");

    return svg(frame, "district-closeup",
      "Close-up of " + focus.map(seat).join(", ") + " on the " + plan.title,
      '<g class="district-shapes">' + shapes(plan, frame) + "</g>" +
      '<use href="#kycd-counties" class="county-line"/>' +
      '<use href="#kycd-outline" class="state-line"/>' +
      '<g class="district-ghosts">' + ghosts + "</g>" +
      '<g aria-hidden="true">' + dots.join("") + "</g>" +
      '<g class="district-labels" aria-hidden="true">' + marks.join("") + "</g>");
  }

  /* --------------------------------------------------------------- facts */

  function focusLink(n, prefix) {
    return '<button type="button" class="link-button" data-focus="' + n + '">' +
      KYC.escapeHtml((prefix ? prefix + " " : "") + seat(n)) + "</button>";
  }

  function flowLine(label, list, prefix) {
    if (!list.length) return "";
    return '<p class="district-flow"><span class="district-fact-label">' +
      KYC.escapeHtml(label) + "</span> " + list.map(function (f) {
        return focusLink(f[0], prefix) + " " + pct(f[1]);
      }).join(", ") + "</p>";
  }

  /** The old map's district: who holds it, and where its land went. */
  function factOld(plan, n) {
    var held = holdersOf[n] || [];
    var went = state.flows.filter(function (f) { return f[0] === n && f[3] >= MIN_SHARE; })
      .map(function (f) { return [f[1], f[3]]; })
      .sort(function (a, b) { return b[1] - a[1]; });
    return '<section class="district-fact' + focusClass(n) + '">' +
      '<h4 class="district-fact-title"><span class="focus-swatch"></span>' +
      KYC.escapeHtml(seat(n)) + " on the " + KYC.escapeHtml(plan.title) + "</h4>" +
      (held.length
        ? '<p class="district-fact-label">Seat held by</p><div class="card-grid">' +
          held.map(KYC.cards.card).join("") + "</div>"
        : '<p class="district-fact-label">No sitting member</p>') +
      flowLine("Where its area went:", went, "new") +
      "</section>";
  }

  /** The new map's district: the 2026 race, and where its land came from. */
  function factNew(plan, n) {
    var race = raceOf[n];
    var people = running(n);
    var came = state.flows.filter(function (f) { return f[1] === n && f[2] >= MIN_SHARE; })
      .map(function (f) { return [f[0], f[2]]; })
      .sort(function (a, b) { return b[1] - a[1]; });
    var res = race && race.results;
    var unfiled = res && res.otherNominees && res.otherNominees.length ? res.otherNominees : [];
    var who = race && race.settled ? "On the November ballot" : "Running";
    return '<section class="district-fact' + focusClass(n) + '">' +
      '<h4 class="district-fact-title"><span class="focus-swatch"></span>' +
      KYC.escapeHtml(seat(n)) + " on the " + KYC.escapeHtml(plan.title) + "</h4>" +
      (people.length
        ? '<p class="district-fact-label">' + who + '</p><div class="card-grid">' +
          people.map(KYC.cards.card).join("") + "</div>"
        : '<p class="district-fact-label">' + who + ": nobody with a profile here</p>") +
      (unfiled.length
        ? '<p class="state-note">Also on the ballot, per the published results, with no FEC ' +
          "filing over $5,000: " + KYC.escapeHtml(unfiled.join(", ")) + ".</p>"
        : "") +
      flowLine("Where its area came from:", came, "old") +
      (race
        ? '<p class="district-flow"><a class="race-state-link" href="' +
          KYC.escapeAttr(KYC.stateUrl(code) + "#race-" + race.id) + '">The ' +
          KYC.escapeHtml(seat(n)) + " race on the " + KYC.escapeHtml(KYC.stateName(code)) +
          " page &rsaquo;</a></p>"
        : "") +
      "</section>";
  }

  /* -------------------------------------------------------------- render */

  function planCard(plan, index) {
    var old = index === 0;
    var head = [
      '<header class="plan-head">',
      '<p class="state-kicker">', KYC.escapeHtml(plan.label), "</p>",
      '<h2 class="plan-title">', KYC.escapeHtml(plan.title), "</h2>",
      '<p class="plan-used">Drawn by ', KYC.escapeHtml(plan.drawnBy), "; used for ",
      KYC.escapeHtml(plan.used), ".</p>",
      "</header>",
    ].join("");
    var body = '<h3 class="plan-panel-title">Statewide</h3>' + statewide(plan) +
      '<h3 class="plan-panel-title">Dense metro areas</h3>' + insets(plan);
    if (focus.length) {
      body += '<h3 class="plan-panel-title">Close-up: ' +
        KYC.escapeHtml(focus.map(seat).join(", ")) + "</h3>" + closeup(plan) +
        '<div class="district-facts">' + focus.map(function (n) {
          return old ? factOld(plan, n) : factNew(plan, n);
        }).join("") + "</div>";
    }
    return '<section class="plan-card" aria-label="' + KYC.escapeAttr(plan.label + ": " +
      plan.title) + '">' + head + body + "</section>";
  }

  function render() {
    el("planGrid").innerHTML = state.plans.map(planCard).join("");
    Array.prototype.forEach.call(doc.querySelectorAll(".mover-group"), function (button) {
      button.setAttribute("aria-pressed",
        String(button.getAttribute("data-focus") === focus.join(",")));
    });
    el("districtPick").value = focus.length === 1 ? String(focus[0]) : "";
  }

  function setFocus(list, opts) {
    focus = list.slice(0, MAX_FOCUS);
    render();
    if (!(opts && opts.fromRoute)) {
      KYC.router.writeFilters({ d: focus.join(",") });
    }
  }

  function parseFocus(value) {
    var seen = {};
    return String(value || "").split(",").map(function (s) {
      return parseInt(s, 10);
    }).filter(function (n) {
      if (!(n >= 1 && n <= state.seats) || seen[n]) return false;
      seen[n] = true;
      return true;
    }).slice(0, MAX_FOCUS);
  }

  /* The controls: the moves, then any district. Written once; render()
   * only updates which is pressed. */
  function controls(list) {
    var grouped = groups(list);
    var html = ['<section class="state-section">'];
    if (grouped.length) {
      html.push(
        '<h2 class="state-heading">Running in a different district</h2>',
        '<p class="state-note">', String(list.length), " member", list.length === 1 ? "" : "s",
        " of the House from ", KYC.escapeHtml(state.name), " hold one district and ",
        list.length === 1 ? "is" : "are", " running in another. Pick a group to see the ",
        "districts on both maps, or choose any district below.</p>",
        '<div class="mover-groups">'
      );
      grouped.forEach(function (g) {
        html.push('<button type="button" class="mover-group" data-focus="',
          g.districts.slice(0, MAX_FOCUS).join(","), '" aria-pressed="false">');
        g.moves.forEach(function (m) {
          html.push('<span class="mover"><span class="mover-name">',
            KYC.escapeHtml(m.person.name), '</span> <span class="',
            KYC.partyClass(m.person), '">', KYC.escapeHtml(m.person.party), "</span>",
            '<span class="mover-seats">', KYC.escapeHtml(seat(m.from)), " &rarr; ",
            KYC.escapeHtml(seat(m.to)), "</span></span>");
        });
        html.push("</button>");
      });
      html.push("</div>");
    }
    html.push(
      '<div class="districts-tools">',
      '<label class="districts-pick"><span>Any district</span>',
      '<select id="districtPick" class="select"><option value="">Choose&hellip;</option>'
    );
    for (var n = 1; n <= state.seats; n++) {
      html.push('<option value="', String(n), '">', KYC.escapeHtml(seat(n)), "</option>");
    }
    html.push(
      "</select></label>",
      '<label class="districts-toggle"><input type="checkbox" id="ghostToggle" checked> ',
      "Dashed: the same districts' lines on the other map</label>",
      "</div>",
      '<p class="state-note">Or click a district on either map; Shift-click to compare up to ',
      String(MAX_FOCUS), ". Shares of area describe land, not people.</p>",
      "</section>",
      '<div class="plan-grid" id="planGrid"></div>'
    );
    return html.join("");
  }

  function drawDefs() {
    var parts = ['<svg class="district-defs" aria-hidden="true" focusable="false"><defs>'];
    state.plans.forEach(function (plan) {
      numbers(plan).forEach(function (n) {
        parts.push('<path id="', pathId(plan, n), '" d="', KYC.escapeAttr(plan.districts[n].d),
          '" vector-effect="non-scaling-stroke"/>');
      });
    });
    parts.push('<path id="kycd-counties" d="', KYC.escapeAttr(state.counties.mesh),
      '" vector-effect="non-scaling-stroke"/>');
    parts.push('<path id="kycd-outline" d="', KYC.escapeAttr(state.counties.outline),
      '" vector-effect="non-scaling-stroke"/>');
    parts.push("</defs></svg>");
    var holder = doc.createElement("div");
    holder.innerHTML = parts.join("");
    doc.body.appendChild(holder.firstChild);
  }

  function bind(app, defaults) {
    app.addEventListener("click", function (event) {
      var card = event.target.closest("[data-id]");
      if (card) {
        KYC.profile.open(card.getAttribute("data-id"));
        return;
      }
      var button = event.target.closest("[data-focus]");
      if (button) {
        setFocus(parseFocus(button.getAttribute("data-focus")));
        return;
      }
      var shape = event.target.closest("[data-district]");
      if (!shape) return;
      var n = parseInt(shape.getAttribute("data-district"), 10);
      if (event.shiftKey || event.ctrlKey || event.metaKey) {
        var next = focus.indexOf(n) === -1 ? focus.concat([n])
          : focus.filter(function (m) { return m !== n; });
        setFocus(next.length > MAX_FOCUS ? next.slice(1) : next);
      } else {
        setFocus([n]);
      }
    });
    el("districtPick").addEventListener("change", function (event) {
      var n = parseInt(event.target.value, 10);
      setFocus(n ? [n] : defaults);
    });
    el("ghostToggle").addEventListener("change", function (event) {
      app.classList.toggle("hide-ghosts", !event.target.checked);
    });
  }

  function applyRoute(route, defaults) {
    if (route.view === "profile") {
      KYC.profile.open(route.id, { fromRoute: true });
      return;
    }
    if (KYC.profile.isOpen()) KYC.profile.close();
    var wanted = parseFocus(route.params.d);
    if (!wanted.length) wanted = defaults;
    if (wanted.join(",") !== focus.join(",")) setFocus(wanted, { fromRoute: true });
  }

  KYC.ready(function () {
    var app = el("districtsApp");
    if (!app) return;
    if (!state) {
      app.innerHTML = '<div class="empty-state">' + KYC.icon("info") +
        "<h3>The district maps did not load</h3>" +
        "<p>Run <code>python build_profile_site.py geo</code> to regenerate " +
        "<code>data/districts.js</code>.</p></div>";
      return;
    }
    if (!data.length) {
      app.innerHTML = '<p class="results-bar">Profile data did not load. Run: ' +
        "python build_profile_site.py</p>";
      return;
    }
    KYC.profile.ensure();
    indexPeople();
    var list = moves();
    var first = groups(list)[0];
    var defaults = first ? first.districts.slice(0, MAX_FOCUS) : [];

    drawDefs();
    app.innerHTML = controls(list);
    bind(app, defaults);

    var initial = KYC.router.read();
    var wanted = initial.view === "list" ? parseFocus(initial.params.d) : [];
    setFocus(wanted.length ? wanted : defaults, { fromRoute: true });
    if (initial.view === "profile") KYC.profile.open(initial.id, { fromRoute: true });
    KYC.router.onChange(function () { applyRoute(KYC.router.read(), defaults); });
  });
})(window);
