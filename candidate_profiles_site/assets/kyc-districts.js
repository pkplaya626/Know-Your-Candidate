/* Know Your Candidate - a state's House districts, and where the map was
 * redrawn for 2026, the map it replaced.
 *
 * The lines come from window.kycDistricts: SVG paths projected at build time
 * by kyc/districts.py, which also measured how much of each new district's
 * land came from each old one. Everything said about a person - who holds a
 * seat, who is running where, who is on the November ballot - comes from
 * profiles.js, the same records the grid and the state pages render, so this
 * page cannot disagree with them about anyone.
 *
 * Each district is drawn once, into one hidden <defs>, and every view - the
 * statewide map, the insets, the close-up - is a set of <use> references to
 * it. Fills are set on the <use>, which the shared path inherits, so a
 * district can be highlighted in one view and not another. A new map's
 * districts run out over water; they are clipped to the old map's land,
 * which stops at the shore.
 *
 * Which districts are picked out lives in the address (#/?d=3,6), so every
 * view can be shared.
 *
 * Once the Congress the cycle elects is sitting (KYC.recordPhase), its
 * members sit for a redrawn state's new map: the new map is drawn in their
 * parties, and the old map in the parties of who last held its seats - each
 * race's incumbent, from the frozen record. The 2026 race is shown as a
 * record, and members "running in a different district" are history.
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;
  var code = doc.body.getAttribute("data-state") || "";
  var state = (global.kycDistricts || {})[code] || null;
  var data = global.legislatorsData || [];
  var races = global.kycRaces || [];

  /* Text is sized for the width a map is actually drawn at, measured after
   * the first render. It used to be sized for 620px and left to scale with
   * the map: on a phone the map is half that, and every number came out
   * 4px tall - a smudge of bold glyph and halo. 620 is only the first guess
   * (and what a test without layout sees). */
  var DESIGN = 620;
  var drawnAt = DESIGN;
  /* One colour per picked district; they are deliberately not the party
   * colours, which mean something everywhere else on the site. */
  var MAX_FOCUS = 3;
  /* Overlaps smaller than this are not listed: two maps simplified
   * separately leave slivers along every shared line. */
  var MIN_SHARE = 0.01;
  var TOWN_LABELS = 14;
  /* A district's number is written wherever the district has this much
   * clear room around its label point, in screen pixels: half an 11px number
   * and its halo. kyc/districts.py plans the insets by the same rule
   * (LABEL_ROOM_PX), so every district is numbered somewhere. */
  var LABEL_ROOM = 6.5;
  var NUMBER_PX = 11;

  var focus = [];

  function el(id) {
    return doc.getElementById(id);
  }

  /* "TX-9", and "AK-AL" for a seat elected at large - the site's own label. */
  function seat(n) {
    return code + "-" + (n === 0 ? "AL" : n);
  }

  function numLabel(n) {
    return n === 0 ? "AL" : String(n);
  }

  function numbers(plan) {
    return Object.keys(plan.districts).map(Number).sort(function (a, b) { return a - b; });
  }

  function redrawn() {
    return state.plans.length === 2;
  }

  /** The map for 2026: the new one where there is one. */
  function newPlan() {
    return state.plans[state.plans.length - 1];
  }

  function otherPlan(plan) {
    if (!redrawn()) return null;
    return state.plans[0] === plan ? state.plans[1] : state.plans[0];
  }

  /** The new map is drawn clipped to the old map's land. */
  function clipped(plan, markup) {
    return redrawn() && plan === newPlan()
      ? '<g clip-path="url(#kycd-land)">' + markup + "</g>" : markup;
  }

  function pct(share) {
    var whole = Math.round(share * 100);
    // A share is measured on simplified lines; it is never quite all.
    return (whole >= 100 && share < 1 ? 99 : whole) + "%";
  }

  /* --------------------------------------------------------- the people */

  /** Sitting House members by the district they hold - on the map they sit
   *  under: the old map's until the new Congress sits, then the new map's.
   *  A former member holds nothing (rule 27). */
  var holdersOf = {};
  /** The 2026 House race for each new district. */
  var raceOf = {};

  function indexPeople() {
    data.forEach(function (p) {
      if (!KYC.seated(p) || p.state !== code || p.chamber.indexOf("House") === -1) return;
      (holdersOf[p.districtNum] || (holdersOf[p.districtNum] = [])).push(p);
    });
    races.forEach(function (r) {
      if (r.chamber === "House" && r.state === code) raceOf[r.district] = r;
    });
  }

  /** A redrawn state once the new Congress sits: its old map is a record. */
  function archive() {
    return KYC.recordPhase() && redrawn();
  }

  /** Who holds district *n* of *plan*: the sitting members, on the map they
   *  sit under. A redrawn state's new map has nobody until the new Congress
   *  sits; then its old map's seats are who last held them - the record's
   *  incumbent of the race of that number, as a profile where they have one,
   *  else by the record's name and party. */
  function holders(plan, n) {
    if (archive() && plan === state.plans[0]) {
      var inc = (raceOf[n] || {}).incumbent;
      if (!inc) return [];
      return [KYC.byId(inc.profileId) || { name: inc.name, party: inc.party }];
    }
    if (redrawn() && plan === newPlan() && !KYC.recordPhase()) return [];
    return holdersOf[n] || [];
  }

  /** Cards for people with a profile; a name and party for the rest. */
  function peopleCards(list) {
    var cards = list.filter(function (p) { return p.id; });
    var names = list.filter(function (p) { return !p.id; });
    return (cards.length ? '<div class="card-grid">' + cards.map(KYC.cards.card).join("") + "</div>" : "") +
      names.map(function (p) {
        return '<p class="state-note">' + KYC.escapeHtml(p.name) + " (" + KYC.escapeHtml(p.party) +
          ")</p>";
      }).join("");
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
      if (race.settled) return KYC.onNovemberBallot(status) || status === "advanced";
      return !KYC.offBallot(status);
    }).sort(function (a, b) {
      // Members first, then the race's own order (by surname, TRUST-15).
      return (a.isCandidate ? 1 : 0) - (b.isCandidate ? 1 : 0) ||
        KYC.racePosition(a) - KYC.racePosition(b);
    });
  }

  /** Filers in a new district's race whom the published results do not
   *  settle (KYC.standing's `unknown`): not on the ballot as far as this
   *  page can say, and not dropped either - the map and the state page
   *  list them, and the district page left them out (RACES-04). */
  function unsure(n) {
    var race = raceOf[n];
    if (!race || !race.settled) return [];
    return race.candidateIds.map(KYC.byId).filter(function (p) {
      var spec = p && KYC.standing(p, "card");
      return !!(spec && spec.unknown);
    });
  }

  function unsureCards(n) {
    var people = unsure(n);
    return people.length
      ? '<p class="district-fact-label">Filed; ballot status not known</p><div class="card-grid">' +
        people.map(KYC.cards.card).join("") + "</div>"
      : "";
  }

  /** Members holding one of this state's districts and running in another,
   *  from the pipeline's contestRaceId (rule 30). A member who lost that
   *  primary, or left it, is not running anywhere: Texas listed Al Green
   *  (TX-9 -> TX-18) and Julie Johnson (TX-32 -> TX-33) as running after
   *  both lost. Their status in the race they entered decides. */
  function moves() {
    // Once the new Congress sits, every move has happened or not: the
    // record of it is each race's.
    if (KYC.recordPhase()) return [];
    var byId = {};
    races.forEach(function (r) { byId[r.id] = r; });
    return data.filter(function (p) {
      // Members who sit now (rule 27): a former member holds no district.
      return KYC.seated(p) && p.state === code && p.chamber.indexOf("House") !== -1 &&
        KYC.runsElsewhere(p) && !KYC.offBallot(KYC.contestStatus(p));
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

  /* --------------------------------------------------- find my district */

  /* A reader's location is placed on the map here, on the device: it is
   * never sent anywhere. The maps are Census cartographic boundaries
   * (1:5,000,000), simplified again for display, so within this distance of
   * a line the map cannot say which side a home is on, and says so. */
  var NEAR_KM = 3;

  /** Where a longitude and latitude fall on this state's map, by the
   *  projection the build drew it with (kyc/districts.py), or null. */
  function project(lon, lat) {
    var p = state && state.projection;
    if (!p) return null;
    var rad = Math.PI / 180;
    var phi0 = p.parallels[0] * rad, phi1 = p.parallels[1] * rad;
    var n = (Math.sin(phi0) + Math.sin(phi1)) / 2;
    var c = 1 + Math.sin(phi0) * (2 * n - Math.sin(phi0));
    var r0 = Math.sqrt(c) / n;
    var d = ((lon - p.meridian + 180) % 360 + 360) % 360 - 180;
    var lam = d * rad * n;
    var r = Math.sqrt(c - 2 * n * Math.sin(lat * rad)) / n;
    var x = r * Math.sin(lam), y = r0 - r * Math.cos(lam);
    return [p.pad + p.k * (x - p.minX), p.pad + p.k * (p.maxY - y)];
  }

  /** Shortest distance from a point to a district's boundary. */
  function edgeDistance(rings, x, y) {
    var best = Infinity;
    rings.forEach(function (ring) {
      for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        var ax = ring[j][0], ay = ring[j][1], bx = ring[i][0], by = ring[i][1];
        var dx = bx - ax, dy = by - ay;
        var len = dx * dx + dy * dy;
        var t = len ? Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / len)) : 0;
        var ex = ax + t * dx - x, ey = ay + t * dy - y;
        best = Math.min(best, Math.sqrt(ex * ex + ey * ey));
      }
    });
    return best;
  }

  /** On each map, where a location falls: ``[{plan, kind, inside, near}]``,
   *  or null when the map has no projection. *accuracy* is the browser's own
   *  estimate in metres; the margin grows by it, since a fix 2 km off is a
   *  home 2 km away.
   *
   *  kind is
   *  - "in": inside one district, no line within the margin;
   *  - "line": within the margin of a line between two or more districts;
   *  - "edge": inside one district, near a line no other district shares -
   *    the state line or the shore, so possibly outside the state;
   *  - "out": inside no district but near one: at the edge or outside;
   *  - "none": nowhere near this map. */
  function locate(lon, lat, accuracy) {
    var at = project(lon, lat);
    if (!at) return null;
    var extra = isFinite(accuracy) && accuracy > 0 ? accuracy / 1000 : 0;
    var margin = (NEAR_KM + extra) / state.unitKm;
    return state.plans.map(function (plan) {
      var inside = [], near = [], ownEdge = false;
      numbers(plan).forEach(function (n) {
        var rings = ringsOf(plan, n);
        var dist = edgeDistance(rings, at[0], at[1]);
        if (contains(rings, at[0], at[1])) {
          inside.push(n);
          if (dist <= margin) ownEdge = true;
        } else if (dist <= margin) {
          near.push(n);
        }
      });
      var kind = inside.length + near.length >= 2 ? "line"
        : inside.length === 1 ? (ownEdge ? "edge" : "in")
        : near.length ? "out" : "none";
      return { plan: plan, kind: kind, inside: inside, near: near };
    });
  }

  /* Beyond this the browser's fix is too rough to name a district at all. */
  var ROUGH_KM = 10;

  function lookupLink() {
    var lookup = (KYC.meta().voting || {})[code] || {};
    var official = lookup.status || lookup.polling;
    return official ? ' <a href="' + KYC.escapeAttr(official) + '" target="_blank" ' +
      'rel="noopener noreferrer">Check with ' + KYC.escapeHtml(state.name) +
      "'s own lookup &rsaquo;</a>" : "";
  }

  function seats(list) {
    var names = list.map(function (n) { return "<strong>" + KYC.escapeHtml(seat(n)) + "</strong>"; });
    return names.length < 2 ? names.join("")
      : names.slice(0, -1).join(", ") + " and " + names[names.length - 1];
  }

  function phrase(f) {
    if (f.kind === "in") return "you are in " + seats(f.inside);
    if (f.kind === "line") return "you are near the line between " + seats(f.inside.concat(f.near));
    if (f.kind === "edge") return "you are in " + seats(f.inside) +
      ", close to the state line or the shore";
    if (f.kind === "out") return "you are at the edge of " + KYC.escapeHtml(state.name) +
      " or just outside it; the nearest district is " + seats(f.near);
    return "this map does not reach your location";
  }

  /** What a location means on this page, in words, and the districts to
   *  show. Never a district the map cannot vouch for. */
  function located(found, accuracy) {
    var check = lookupLink();
    var main = found[found.length - 1];          // the map for 2026
    var km = isFinite(accuracy) ? Math.round(accuracy / 100) / 10 : null;
    var reach = main.inside.concat(main.near);
    if ((km !== null && km > ROUGH_KM) || reach.length > MAX_FOCUS) {
      return { html: "Your browser shared only an approximate location" +
        (km !== null ? " (to within about " + km + " km)" : "") +
        ", too rough to place in a district. Pick your district below." + check, focus: null };
    }
    if (main.kind === "none") {
      return { html: "That location is not in " + KYC.escapeHtml(state.name) + ". " +
        '<a href="' + KYC.escapeAttr(KYC.siteRoot() + "states/index.html") +
        '">Find your state &rsaquo;</a>', focus: null };
    }
    var phrases = found.map(phrase);
    var names = ["the map members were elected on", "the map for 2026"];
    var first;
    if (found.length === 1 || phrases[0] === phrases[1]) {
      first = (found.length > 1 ? "On both maps, " : "") + phrases[0] + ".";
    } else {
      first = found.map(function (f, i) {
        return f.kind === "none" ? names[i] + " does not reach this point."
          : "on " + names[i] + ", " + phrases[i] + ".";
      }).map(function (s) { return s.charAt(0).toUpperCase() + s.slice(1); }).join(" ");
    }
    first = first.charAt(0).toUpperCase() + first.slice(1);
    var unsure = found.some(function (f) { return f.kind !== "in" && f.kind !== "none"; });
    var lines = [first];
    if (unsure) {
      lines.push("The map is simplified, so it cannot say exactly where a line runs" +
        (km !== null && km >= 1 ? ", and your browser's location is accurate to about " + km + " km" : "") +
        ".");
    }
    return { html: lines.join(" ") + check, focus: reach.slice(0, MAX_FOCUS) };
  }

  function findMe() {
    var out = el("locateResult");
    var button = el("locateMe");
    out.hidden = false;
    out.textContent = "Finding your location…";
    button.disabled = true;
    global.navigator.geolocation.getCurrentPosition(function (pos) {
      button.disabled = false;
      var accuracy = pos.coords.accuracy;
      var found = locate(pos.coords.longitude, pos.coords.latitude, accuracy);
      if (!found) {
        out.innerHTML = "This map cannot place a location. Pick your district below." + lookupLink();
        return;
      }
      var said = located(found, accuracy);
      out.innerHTML = said.html;
      // The answer stays where it is, above the map, with its caveat and
      // the lookup link: revealing the district card scrolled them away on
      // a phone.
      if (said.focus && said.focus.length) setFocus(said.focus);
    }, function (err) {
      button.disabled = false;
      out.innerHTML = (err && err.code === 1
        ? "Your browser did not share a location."
        : "Your location could not be found.") + " Pick your district below." + lookupLink();
    }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
  }

  function within(point, frame, margin) {
    return point[0] >= frame[0] + margin && point[0] <= frame[0] + frame[2] - margin &&
      point[1] >= frame[1] + margin && point[1] <= frame[1] + frame[3] - margin;
  }

  function meets(box, frame) {
    return box[0] < frame[0] + frame[2] && box[2] > frame[0] &&
      box[1] < frame[1] + frame[3] && box[3] > frame[1];
  }

  var labelCache = {};

  /** Where to write a district's number inside *frame*: its own label
   *  point when that is in view, otherwise the roomiest visible point -
   *  the close-up crops old CA-3, which ran south to Death Valley. Returns
   *  [x, y, room] with room in map units, or null.
   *
   *  Room is the distance from a sample to the nearest sample outside the
   *  district, or to the frame's edge. It used to compare every sample with
   *  every other - 289 x 289 distances a label, never kept - and an inset
   *  full of districts reaching in from outside cost a mid-range Android
   *  phone a quarter of a second each time it was drawn. Two passes over
   *  the grid carry each sample's nearest outside sample instead, and the
   *  answer, being in map units, is kept for the next draw. */
  function labelAt(plan, n, frame, margin) {
    var district = plan.districts[n];
    if (within(district.at, frame, margin)) return [district.at[0], district.at[1], Infinity];
    var key = plan.key + "-" + n + "-" + frame.join(",") + "-" + margin.toFixed(2);
    if (Object.prototype.hasOwnProperty.call(labelCache, key)) return labelCache[key];
    var x0 = Math.max(district.box[0], frame[0] + margin);
    var y0 = Math.max(district.box[1], frame[1] + margin);
    var x1 = Math.min(district.box[2], frame[0] + frame[2] - margin);
    var y1 = Math.min(district.box[3], frame[1] + frame[3] - margin);
    if (x1 <= x0 || y1 <= y0) return (labelCache[key] = null);
    var rings = ringsOf(plan, n);
    var steps = 16, size = steps + 1;
    var xs = [], ys = [], inside = [], nearX = [], nearY = [];
    for (var k = 0; k < size; k++) {
      xs.push(x0 + (x1 - x0) * k / steps);
      ys.push(y0 + (y1 - y0) * k / steps);
    }
    for (var i = 0; i < size; i++) {
      for (var j = 0; j < size; j++) {
        var at = i * size + j;
        inside[at] = contains(rings, xs[i], ys[j]);
        nearX[at] = inside[at] ? NaN : xs[i];
        nearY[at] = inside[at] ? NaN : ys[j];
      }
    }
    // A sample takes its neighbour's nearest outside sample when that is
    // closer than its own: forwards, then backwards.
    function relax(i, j, ni, nj) {
      if (ni < 0 || nj < 0 || ni >= size || nj >= size) return;
      var at = i * size + j, from = ni * size + nj;
      if (isNaN(nearX[from])) return;
      var d = Math.hypot(xs[i] - nearX[from], ys[j] - nearY[from]);
      if (isNaN(nearX[at]) || d < Math.hypot(xs[i] - nearX[at], ys[j] - nearY[at])) {
        nearX[at] = nearX[from];
        nearY[at] = nearY[from];
      }
    }
    for (i = 0; i < size; i++) {
      for (j = 0; j < size; j++) {
        relax(i, j, i - 1, j); relax(i, j, i, j - 1);
        relax(i, j, i - 1, j - 1); relax(i, j, i - 1, j + 1);
      }
    }
    for (i = steps; i >= 0; i--) {
      for (j = steps; j >= 0; j--) {
        relax(i, j, i + 1, j); relax(i, j, i, j + 1);
        relax(i, j, i + 1, j + 1); relax(i, j, i + 1, j - 1);
      }
    }
    var best = null;
    for (i = 0; i < size; i++) {
      for (j = 0; j < size; j++) {
        var cell = i * size + j;
        if (!inside[cell]) continue;
        var x = xs[i], y = ys[j];
        var room = Math.min(x - frame[0], frame[0] + frame[2] - x, y - frame[1], frame[1] + frame[3] - y);
        if (!isNaN(nearX[cell])) room = Math.min(room, Math.hypot(x - nearX[cell], y - nearY[cell]));
        if (!best || room > best[2]) best = [x, y, room];
      }
    }
    return (labelCache[key] = best);
  }

  /* -------------------------------------------------------------- labels */

  function textBox(x, y, text, size, anchor) {
    var w = (String(text).length * 0.6 + 0.44) * size;
    var left = anchor === "middle" ? x - w / 2 : anchor === "end" ? x - w : x;
    return [left, y - size * 0.62, left + w, y + size * 0.62];
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

  /* A label is page text over the map, not SVG text. Samsung Internet's
   * dark mode - on whenever the phone is dark, and deaf to every opt-out a
   * page can declare - repaints a page by lightening anything dark: inside
   * an SVG that took a number's dark text and left its light halo light,
   * so every label bloomed into a smear. Page text on a page background is
   * what every forced dark mode treats predictably, darkening the backing
   * and lightening the text. So a label is a span on a small backing of
   * the page colour, placed by percentage of its map's frame; *x*, *y* and
   * *size* are in map units, and the anchor says which edge sits at x. */
  function text(cls, x, y, size, content, anchor) {
    return { cls: cls, x: x, y: y, size: size, content: content, anchor: anchor || "middle" };
  }

  function labelLayer(frame, px, labels) {
    return '<div class="map-labels" aria-hidden="true">' + labels.filter(Boolean).map(function (l) {
      return '<span class="map-label ' + l.cls + " anchor-" + l.anchor + '" style="left:' +
        ((l.x - frame[0]) / frame[2] * 100).toFixed(3) + "%;top:" +
        ((l.y - frame[1]) / frame[3] * 100).toFixed(3) + "%;font-size:" +
        (l.size * px).toFixed(2) + 'px">' + KYC.escapeHtml(l.content) + "</span>";
    }).join("") + "</div>";
  }

  /* --------------------------------------------------------------- views */

  function pathId(plan, n) {
    return "kycd-" + plan.key + "-" + n;
  }

  function focusClass(n) {
    var at = focus.indexOf(n);
    return at === -1 ? "" : " is-focus focus-" + (at + 1);
  }

  /** The party a district is drawn in: its sitting member's, on the map
   *  the members were elected under. A seat with no member on the roster is
   *  vacant. A redrawn state's new map has no members until the new Congress
   *  sits - November fills its seats - so it is drawn in none, never in a
   *  guess; then the old map is drawn in who last held each seat. */
  function partyOf(plan, n) {
    if (redrawn() && plan === newPlan() && !KYC.recordPhase()) return "none";
    var held = holders(plan, n);
    return held.length ? KYC.partyKey(held[0]) : "vacant";
  }

  function tip(plan, n) {
    var where = seat(n) + " on the " + plan.title;
    var parts = [];
    var last = archive() && plan === state.plans[0];
    if (plan === state.plans[0] || KYC.recordPhase()) {
      var held = holders(plan, n);
      parts.push(held.length ? (last ? "last held by " : "held by ") + held.map(function (p) {
        return p.name + " (" + p.party + ")";
      }).join(", ") : last ? "no holder on the record" : "vacant: no sitting member");
    }
    if (plan === newPlan() && !KYC.recordPhase()) {
      var names = running(n).map(function (p) { return p.name; });
      if (names.length) parts.push(names.join(", ") + " on the ballot");
    }
    return parts.length ? where + ": " + parts.join("; ") : where;
  }

  /** Every district meeting *frame*, as <use> elements, in its party. */
  function shapes(plan, frame) {
    return numbers(plan).filter(function (n) {
      return meets(plan.districts[n].box, frame);
    }).map(function (n) {
      return '<use href="#' + pathId(plan, n) + '" class="district-shape party-' +
        partyOf(plan, n) + focusClass(n) + '" data-district="' + n + '"><title>' +
        KYC.escapeHtml(tip(plan, n)) + "</title></use>";
    }).join("");
  }

  /** The picked districts' outlines, drawn over every fill so a district
   *  keeps its party colour and is still found at a glance. */
  function focusLines(plan) {
    return clipped(plan, focus.map(function (n) {
      return '<use href="#' + pathId(plan, n) + '" class="district-focus-halo"/>' +
        '<use href="#' + pathId(plan, n) + '" class="district-focus focus-' +
        (focus.indexOf(n) + 1) + '"/>';
    }).join(""));
  }

  /** A map: the SVG, and its labels over it. *px* is screen pixels per
   *  map unit at the width the map is drawn. */
  function svg(frame, cls, label, body, labels, px) {
    return '<div class="map-frame"><svg class="district-map ' + cls +
      (focus.length ? " has-focus" : "") + '" viewBox="' + frame.map(function (v) {
        return v.toFixed(1);
      }).join(" ") + '" role="img" aria-label="' + KYC.escapeAttr(label) + '">' + body + "</svg>" +
      labelLayer(frame, px, labels || []) + "</div>";
  }

  /** Whether a district's number fits at *px* screen pixels per map unit.
   *  A state elected at large has one district, labelled however small. */
  function fitsAt(district, px) {
    return state.atLarge || district.room * px >= LABEL_ROOM;
  }

  /** The whole state. A district too small to number here is numbered in
   *  a metro inset, as on a printed atlas. */
  function statewide(plan) {
    var frame = state.viewBox.slice();
    var px = drawnAt / frame[2];
    var labels = numbers(plan).map(function (n) {
      var district = plan.districts[n];
      var picked = focus.indexOf(n) !== -1;
      if (!picked && !fitsAt(district, px)) return null;
      return text("district-num" + focusClass(n), district.at[0], district.at[1],
                  (picked ? 15 : NUMBER_PX) / px, numLabel(n));
    });
    var lines = state.insets.map(function (inset) {
      var b = inset.box;
      return '<rect class="inset-outline" x="' + b[0] + '" y="' + b[1] + '" width="' + b[2] +
        '" height="' + b[3] + '"/>';
    }).join("");
    return svg(frame, "district-statewide",
      "All " + state.seats + " districts on the " + plan.title,
      '<g class="district-shapes">' + clipped(plan, shapes(plan, frame)) + "</g>" +
      '<use href="#kycd-outline" class="state-line"/>' + focusLines(plan) + lines,
      labels, px);
  }

  /* Each inset is drawn as wide as it needs for every number in it, or as
   * wide as the card where that is narrower, and they wrap: squeezed into
   * one row, the Los Angeles inset was too small to number every district.
   * Drawn narrower than it needs - New York City on a phone - an inset is
   * followed by the closer insets the build planned for that case, and the
   * districts too small for it are numbered there. */
  function insets(plan) {
    return '<div class="inset-row">' + insetFigures(plan, state.insets) + "</div>";
  }

  function insetFigures(plan, list) {
    return list.map(function (inset) {
      var width = Math.min(drawnAt, inset.width);
      return insetFigure(plan, inset, width) +
        (width < inset.fits ? insetFigures(plan, inset.detail || []) : "");
    }).join("");
  }

  function insetFigure(plan, inset, width) {
    var frame = inset.box;
    var px = width / frame[2];
    var placed = [];
    var mine = [];
    var others = [];
    numbers(plan).forEach(function (n) {
      var district = plan.districts[n];
      if (within(district.at, frame, 9 / px)) mine.push(n);
      else if (meets(district.box, frame)) others.push(n);
    });
    // The districts whose label points are in the frame are what the inset
    // is for, and are numbered first; a district reaching in from outside
    // is numbered only where that collides with nothing.
    var labels = mine.map(function (n) {
      var district = plan.districts[n];
      var picked = focus.indexOf(n) !== -1;
      if (!picked && !fitsAt(district, px)) return null;
      var size = (picked ? 13 : NUMBER_PX) / px;
      placed.push(textBox(district.at[0], district.at[1], numLabel(n), size, "middle"));
      return text("district-num" + focusClass(n), district.at[0], district.at[1], size,
                  numLabel(n));
    }).concat(others.map(function (n) {
      var at = labelAt(plan, n, frame, 9 / px);
      if (!at || at[2] * px < LABEL_ROOM + 0.5) return null;
      var size = (focus.indexOf(n) !== -1 ? 13 : NUMBER_PX) / px;
      var box = textBox(at[0], at[1], numLabel(n), size, "middle");
      if (collides(box, placed)) return null;
      placed.push(box);
      return text("district-num" + focusClass(n), at[0], at[1], size, numLabel(n));
    }));
    return '<figure class="inset" style="width:' + Math.round(width) + 'px">' +
      svg(frame, "district-inset", inset.title + " on the " + plan.title,
        '<g class="district-shapes">' + clipped(plan, shapes(plan, frame)) + "</g>" +
        '<use href="#kycd-outline" class="state-line"/>' + focusLines(plan),
        labels, px) +
      "<figcaption>" + KYC.escapeHtml(inset.title) + "</figcaption></figure>";
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
    var people = redrawn() && plan === newPlan() && !KYC.recordPhase()
      ? running(n).filter(function (p) { return KYC.seated(p); })
      : holders(plan, n);
    return people.map(function (p) { return p.name; }).join(" · ");
  }

  function closeup(plan) {
    var frame = closeupFrame();
    var px = drawnAt / frame[2];
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
      var box = textBox(at[0], at[1], numLabel(n), size, "middle");
      if (!picked && collides(box, placed)) return;
      placed.push(box);
      marks.push(text("district-num" + focusClass(n), at[0], at[1], size, numLabel(n)));
      spots[n] = [at[0], at[1], size];
    }

    /* Who held the seat, or who is running in it now: under its number,
     * else above it, else beside it - wherever the towns have left room. */
    function captionFor(n) {
      var spot = spots[n];
      var words = spot && caption(plan, n);
      if (!words) return;
      var name = 12.5 / px, role = 10.5 / px;
      var what = redrawn() && plan === newPlan() && !KYC.recordPhase() ? "running here in " + year
        : archive() && plan === state.plans[0] ? "held this seat" : "holds this seat";
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
      // The Census name says what kind of county it is: "Orleans Parish",
      // "Juneau City and Borough", "Richmond city".
      var words = county[0].replace(/ County$/, " Co.").toUpperCase();
      var size = 9.5 / px;
      var box = textBox(county[1], county[2], words, size, "middle");
      if (!fits(box, frame) || collides(box, placed)) return;
      placed.push(box);
      marks.unshift(text("county-name", county[1], county[2], size, words));
    });

    var ghosts = other ? clipped(other, focus.map(function (n) {
      return '<use href="#' + pathId(other, n) + '" class="district-ghost-halo"/>' +
        '<use href="#' + pathId(other, n) + '" class="district-ghost focus-' +
        (focus.indexOf(n) + 1) + '"/>';
    }).join("")) : "";

    return svg(frame, "district-closeup",
      "Close-up of " + focus.map(seat).join(", ") + " on the " + plan.title,
      '<g class="district-shapes">' + clipped(plan, shapes(plan, frame)) + "</g>" +
      '<use href="#kycd-counties" class="county-line"/>' +
      '<use href="#kycd-outline" class="state-line"/>' + focusLines(plan) +
      '<g class="district-ghosts">' + ghosts + "</g>" +
      '<g aria-hidden="true">' + dots.join("") + "</g>",
      marks, px);
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

  /** Why a seat on the map the members sit under is empty, where the
   *  build records it: who left, when, and whether a special election has
   *  been called. Only the old map's seat - the new map's district of the
   *  same number is another place (FL-20 kept 3% of its land). */
  function vacancyLine(n) {
    var v = archive() ? null : KYC.vacancyOf(code, n);
    return v ? '<p class="state-note">' + KYC.escapeHtml(KYC.vacancyNote(v)) + "</p>" : "";
  }

  /** The old map's district: who holds it, and where its land went. */
  function factOld(plan, n) {
    var held = holders(plan, n);
    var last = archive();
    var went = state.flows.filter(function (f) { return f[0] === n && f[3] >= MIN_SHARE; })
      .map(function (f) { return [f[1], f[3]]; })
      .sort(function (a, b) { return b[1] - a[1]; });
    return '<section class="district-fact' + focusClass(n) + '">' +
      '<h4 class="district-fact-title"><span class="focus-swatch"></span>' +
      KYC.escapeHtml(seat(n)) + " on the " + KYC.escapeHtml(plan.title) + "</h4>" +
      (held.length
        ? '<p class="district-fact-label">' + (last ? "Last held by" : "Seat held by") + "</p>" +
          peopleCards(held)
        : '<p class="district-fact-label">' + (last ? "No holder on the record" : "No sitting member") +
          "</p>" + vacancyLine(n)) +
      flowLine("Where its area went:", went, "new") +
      "</section>";
  }

  /** The new map's district: the 2026 race, and where its land came from. */
  function factNew(plan, n) {
    var race = raceOf[n];
    var rec = KYC.recordPhase();
    var held = rec ? holders(plan, n) : [];
    var people = running(n).filter(function (p) { return held.indexOf(p) === -1; });
    var came = state.flows.filter(function (f) { return f[1] === n && f[2] >= MIN_SHARE; })
      .map(function (f) { return [f[0], f[2]]; })
      .sort(function (a, b) { return b[1] - a[1]; });
    var res = race && race.results;
    var unfiled = res && res.otherNominees && res.otherNominees.length ? res.otherNominees : [];
    var who = rec ? "In the " + raceYear(race) + " race" :
      race && race.settled ? "On the November ballot" : "Running";
    return '<section class="district-fact' + focusClass(n) + '">' +
      '<h4 class="district-fact-title"><span class="focus-swatch"></span>' +
      KYC.escapeHtml(seat(n)) + " on the " + KYC.escapeHtml(plan.title) + "</h4>" +
      (rec
        ? '<p class="district-fact-label">' + (held.length ? "Seat held by" : "No sitting member") +
          "</p>" + peopleCards(held)
        : "") +
      (people.length
        ? '<p class="district-fact-label">' + who + '</p><div class="card-grid">' +
          people.map(KYC.cards.card).join("") + "</div>"
        : '<p class="district-fact-label">' + who + ": nobody with a profile here</p>") +
      (unfiled.length ? KYC.cards.unprofiledNote(race, "state-note") : "") + unsureCards(n) +
      flowLine("Where its area came from:", came, "old") +
      (race
        ? '<p class="district-flow"><a class="race-state-link" href="' +
          KYC.escapeAttr(KYC.stateUrl(code) + "#race-" + race.id) + '">The ' +
          KYC.escapeHtml(seat(n)) + " race on the " + KYC.escapeHtml(KYC.stateName(code)) +
          " page &rsaquo;</a></p>"
        : "") +
      "</section>";
  }

  /** One map, one district: who holds it and who is on the ballot - the
   *  holder once, when they are running for it again. */
  function factOnly(plan, n) {
    var race = raceOf[n];
    var people = running(n);
    var held = (holdersOf[n] || []).filter(function (p) { return people.indexOf(p) === -1; });
    var res = race && race.results;
    var unfiled = res && res.otherNominees && res.otherNominees.length ? res.otherNominees : [];
    var who = KYC.recordPhase() ? "In the " + raceYear(race) + " race" :
      race && race.settled ? "On the November ballot" : "Running in 2026";
    return '<section class="district-fact' + focusClass(n) + '">' +
      '<h4 class="district-fact-title"><span class="focus-swatch"></span>' +
      KYC.escapeHtml(seat(n)) + "</h4>" +
      (held.length
        ? '<p class="district-fact-label">Seat held by</p><div class="card-grid">' +
          held.map(KYC.cards.card).join("") + "</div>"
        : vacancyLine(n)) +
      (!race
        ? '<p class="state-note">No race for this seat in 2026.</p>'
        : people.length
          ? '<p class="district-fact-label">' + who + '</p><div class="card-grid">' +
            people.map(KYC.cards.card).join("") + "</div>"
          : '<p class="district-fact-label">' + who + ": nobody with a profile here</p>") +
      (unfiled.length ? KYC.cards.unprofiledNote(race, "state-note") : "") + unsureCards(n) +
      (race
        ? '<p class="district-flow"><a class="race-state-link" href="' +
          KYC.escapeAttr(KYC.stateUrl(code) + "#race-" + race.id) + '">The ' +
          KYC.escapeHtml(seat(n)) + " race on the " + KYC.escapeHtml(KYC.stateName(code)) +
          " page &rsaquo;</a></p>"
        : "") +
      "</section>";
  }

  function raceYear(race) {
    return (race && race.year) || (KYC.meta().election || {}).year || "";
  }

  /* -------------------------------------------------------------- render */

  function planCard(plan, index) {
    var head = [
      '<header class="plan-head">',
      '<p class="state-kicker">', KYC.escapeHtml(plan.label), "</p>",
      '<h2 class="plan-title">', KYC.escapeHtml(plan.title), "</h2>",
      '<p class="plan-used">',
      plan.drawnBy ? "Drawn by " + KYC.escapeHtml(plan.drawnBy) + "; used for "
        : "Used for ",
      KYC.escapeHtml(plan.used), ".</p>",
      "</header>",
    ].join("");
    // An at-large seat is the whole state: the statewide map is its close-up.
    var whole = state.atLarge;
    var body = '<h3 class="plan-panel-title">' + (whole ? "The district" : "Statewide") +
      "</h3>" + statewide(plan) +
      (state.insets.length
        ? '<h3 class="plan-panel-title">Where districts are small</h3>' + insets(plan) : "");
    if (focus.length) {
      if (!whole) {
        body += '<h3 class="plan-panel-title">Close-up: ' +
          KYC.escapeHtml(focus.map(seat).join(", ")) + "</h3>" + closeup(plan);
      }
      body += '<div class="district-facts">' + focus.map(function (n) {
        if (!redrawn()) return factOnly(plan, n);
        return index === 0 ? factOld(plan, n) : factNew(plan, n);
      }).join("") + "</div>";
    }
    return '<section class="plan-card" aria-label="' + KYC.escapeAttr(plan.label + ": " +
      plan.title) + '">' + head + body + "</section>";
  }

  function render() {
    var expected = expectedWidth();
    if (expected) drawnAt = expected;
    el("planGrid").innerHTML = state.plans.map(planCard).join("");
    Array.prototype.forEach.call(doc.querySelectorAll(".mover-group"), function (button) {
      button.setAttribute("aria-pressed",
        String(button.getAttribute("data-focus") === focus.join(",")));
    });
    el("districtPick").value = focus.length === 1 ? String(focus[0]) : "";
    // Text sizes depend on the drawn width, which only layout knows. One
    // redraw at most, so a width that flickers cannot loop.
    var measured = mapWidth();
    if (measured && Math.abs(measured - drawnAt) > 4 && !remeasuring) {
      drawnAt = measured;
      remeasuring = true;
      try { render(); } finally { remeasuring = false; }
    }
  }

  var remeasuring = false;

  /** How wide the statewide map is actually drawn, in CSS pixels; 0 when
   *  there is no layout to measure (a test, a hidden page). */
  function mapWidth() {
    var map = doc.querySelector(".plan-card .district-statewide");
    var width = map ? map.getBoundingClientRect().width : 0;
    return width > 40 ? Math.round(width) : 0;
  }

  /** The width the statewide map will be drawn at, from the grid's width,
   *  its columns and a card's padding - so a page draws once per width
   *  instead of drawing at a guess, measuring and drawing again. 0 without
   *  layout; render() still measures what it drew and corrects a miss. */
  function expectedWidth() {
    var grid = el("planGrid");
    var width = grid ? grid.getBoundingClientRect().width : 0;
    if (width < 40 || !global.getComputedStyle) return 0;
    var gap = parseFloat(global.getComputedStyle(grid).columnGap) || 0;
    var single = grid.classList.contains("single");
    // The grid's own rule: columns of at least 420px, as many as there are
    // maps; a single map is at most 860px.
    var columns = single ? 1
      : Math.max(1, Math.min(state.plans.length, Math.floor((width + gap) / (420 + gap))));
    var card = (width - gap * (columns - 1)) / columns;
    if (single) card = Math.min(card, 860);
    var probe = doc.createElement("div");
    probe.className = "plan-card";
    grid.appendChild(probe);
    var style = global.getComputedStyle(probe);
    var inner = card - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) -
      parseFloat(style.borderLeftWidth) - parseFloat(style.borderRightWidth);
    grid.removeChild(probe);
    return inner > 40 ? Math.round(inner) : 0;
  }

  function watchWidth() {
    if (!global.ResizeObserver) return;
    // The observer reports the width it starts at; that is not a change.
    var last = Math.round(el("planGrid").getBoundingClientRect().width);
    var redraw = KYC.debounce(function () { render(); }, 120);
    new global.ResizeObserver(function (entries) {
      var width = Math.round(entries[0].contentRect.width);
      if (Math.abs(width - last) > 4) {
        last = width;
        redraw();
      }
    }).observe(el("planGrid"));
  }

  /* On a phone the facts follow the maps down the page. A tap changed only
   * an outline, with the district's facts two screens below it (NC-4 at
   * y=1346 on an 844px screen), so the page looked as if nothing happened.
   * After a pick, bring the first picked district's facts into view if none
   * of it shows - as the US map does with its panel. */
  function reveal(card) {
    if (!global.matchMedia || !global.matchMedia("(max-width: 1000px)").matches) return;
    // The facts of the map that was tapped: each plan has its own, and the
    // first on the page is the 2024 map's even when the 2025 map was tapped.
    // Without a card (the list), the newest plan's - the 2026 lines.
    var cards = doc.querySelectorAll(".plan-card");
    var scope = cards[card === undefined ? cards.length - 1 : card] || doc;
    var fact = scope.querySelector(".district-fact.is-focus");
    if (fact && fact.getBoundingClientRect().top > global.innerHeight - 80) {
      fact.scrollIntoView({ behavior: "smooth", block: "start" });
    }
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
    var valid = {};
    numbers(newPlan()).forEach(function (n) { valid[n] = true; });
    return String(value || "").split(",").map(function (s) {
      return /^\s*\d+\s*$/.test(s) ? parseInt(s, 10) : NaN;
    }).filter(function (n) {
      if (!valid[n] || seen[n]) return false;
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
        " of the House from ", KYC.escapeHtml(state.name), " hold", list.length === 1 ? "s" : "",
        " one district and ", list.length === 1 ? "is" : "are",
        " running in another. Pick a group to see the districts on both maps, or choose any ",
        "district below.</p>",
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
    var many = numbers(newPlan()).length > 1;
    // Only where the browser can share a location and the map can place it.
    var canLocate = many && !!state.projection && !!(global.navigator && global.navigator.geolocation);
    if (canLocate) {
      html.push(
        // Said beside the button, not only in its title: a phone, where the
        // button is used, never shows a title (TRUST-10).
        '<div class="districts-locate"><button type="button" class="btn" id="locateMe" ',
        'aria-describedby="locateNote">', KYC.icon("pin"), " Find my district</button>",
        '<span class="field-note" id="locateNote">Your location is placed on this map on your ',
        "device and is never sent anywhere.</span>",
        '<p class="state-note" id="locateResult" role="status" aria-live="polite" hidden></p></div>'
      );
    }
    html.push(
      '<div class="districts-tools"', many ? "" : " hidden", ">",
      '<label class="districts-pick"><span>', redrawn() ? "Any district" : "Pick a district",
      "</span>",
      '<select id="districtPick" class="select"><option value="">Choose&hellip;</option>'
    );
    numbers(newPlan()).forEach(function (n) {
      html.push('<option value="', String(n), '">', KYC.escapeHtml(seat(n)), "</option>");
    });
    html.push("</select></label>");
    // Shift-click has no touch equivalent: on a phone the only way to
    // compare districts was a preset group.
    html.push(
      '<label class="districts-toggle"><input type="checkbox" id="compareToggle"> ',
      "Compare: each click adds a district</label>"
    );
    if (redrawn()) {
      html.push(
        '<label class="districts-toggle"><input type="checkbox" id="ghostToggle" checked> ',
        "Dashed: the same districts' lines on the other map</label>"
      );
    }
    html.push("</div>");
    if (many) {
      html.push('<p class="state-note">', redrawn() ? "Or click" : "Or click",
        " a district on ", redrawn() ? "either map" : "the map",
        "; turn on Compare, or Shift-click, to compare up to ", String(MAX_FOCUS), ".",
        redrawn() ? " Shares of area describe land, not people." : "", "</p>");
    }
    html.push(
      legend(),
      "</section>",
      '<div class="plan-grid', redrawn() ? "" : " single", '" id="planGrid"></div>',
      '<div class="districts-sources">', (state.sources || []).map(function (line) {
        return "<p>" + KYC.escapeHtml(line) + "</p>";
      }).join(""), "</div>"
    );
    return html.join("");
  }

  /** Which colour is which: only the parties the map actually shows. */
  function legend() {
    var shown = {};
    (archive() ? state.plans : [state.plans[0]]).forEach(function (plan) {
      numbers(plan).forEach(function (n) { shown[partyOf(plan, n)] = true; });
    });
    var keys = [["d", "Democratic"], ["r", "Republican"], ["i", "Independent"],
      ["vacant", "Vacant seat"]].filter(function (p) { return shown[p[0]]; });
    var items = keys.map(function (p) {
      return '<span class="key"><span class="swatch party-fill-' + p[0] + '"></span>' +
        KYC.escapeHtml(p[1]) + "</span>";
    });
    if (redrawn() && !archive()) {
      items.push('<span class="key"><span class="swatch party-fill-none"></span>' +
        "The " + KYC.escapeHtml(newPlan().title) + ": seats filled in November</span>");
    }
    var title = archive()
      ? "Colored by the party of the member who holds each seat; the " +
        KYC.escapeHtml(state.plans[0].title) + " by who last held it"
      : (redrawn() ? "The " + KYC.escapeHtml(state.plans[0].title) + " is colored"
        : "Colored") + " by the party of the member who holds each seat";
    return '<p class="party-legend"><span class="party-legend-title">' + title + "</span>" +
      items.join("") + "</p>";
  }

  function drawDefs() {
    var parts = ['<svg class="district-defs" aria-hidden="true" focusable="false"><defs>'];
    state.plans.forEach(function (plan) {
      numbers(plan).forEach(function (n) {
        parts.push('<path id="', pathId(plan, n), '" d="', KYC.escapeAttr(plan.districts[n].d),
          '" vector-effect="non-scaling-stroke"/>');
      });
    });
    if (redrawn()) {
      // The old map's land, which the new map is clipped to: one path of
      // every old district's rings. It was one <use> per district, and Blink
      // spent 2 seconds resolving that clip on a desktop - 11 to 20 on an
      // Android phone - with Texas's page frozen and blank the whole time.
      // Same rings, same nonzero rule, the same pixels.
      var land = numbers(state.plans[0]).map(function (n) {
        return state.plans[0].districts[n].d;
      }).join(" ");
      parts.push('<clipPath id="kycd-land"><path d="', KYC.escapeAttr(land), '"/></clipPath>');
    }
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
      var compare = el("compareToggle");
      if (event.shiftKey || event.ctrlKey || event.metaKey || (compare && compare.checked)) {
        var next = focus.indexOf(n) === -1 ? focus.concat([n])
          : focus.filter(function (m) { return m !== n; });
        setFocus(next.length > MAX_FOCUS ? next.slice(1) : next);
      } else {
        var card = Array.prototype.indexOf.call(doc.querySelectorAll(".plan-card"),
          shape.closest(".plan-card"));
        setFocus([n]);
        reveal(card === -1 ? undefined : card);
      }
    });
    var locateMe = el("locateMe");
    if (locateMe) locateMe.addEventListener("click", findMe);
    el("districtPick").addEventListener("change", function (event) {
      var n = parseInt(event.target.value, 10);
      setFocus(n ? [n] : defaults);
      if (n) reveal();
    });
    var toggle = el("ghostToggle");
    if (toggle) {
      toggle.addEventListener("change", function (event) {
        app.classList.toggle("hide-ghosts", !event.target.checked);
      });
    }
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

  KYC.districtMap = { project: project, locate: locate };

  KYC.ready(function () {
    var app = el("districtsApp");
    if (!app) return;
    if (!state) {
      app.innerHTML = '<div class="empty-state">' + KYC.icon("info") +
        "<h3>The district map did not load</h3>" +
        "<p>Run <code>python build_profile_site.py geo</code> to regenerate " +
        "<code>data/districts/</code>.</p></div>";
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
    // A redrawn state opens on its first group of moves; a single seat is
    // always the one shown; anywhere else the reader picks.
    var only = numbers(newPlan());
    var defaults = first ? first.districts.slice(0, MAX_FOCUS)
      : only.length === 1 ? only : [];

    drawDefs();
    app.innerHTML = controls(list);
    bind(app, defaults);
    watchWidth();

    var initial = KYC.router.read();
    var wanted = initial.view === "list" ? parseFocus(initial.params.d) : [];
    setFocus(wanted.length ? wanted : defaults, { fromRoute: true });
    if (initial.view === "profile") KYC.profile.open(initial.id, { fromRoute: true });
    KYC.router.onChange(function () { applyRoute(KYC.router.read(), defaults); });
  });
})(window);
