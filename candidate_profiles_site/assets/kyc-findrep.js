/* Know Your Candidate - "Find who represents me".
 *
 * A reader types a ZIP code or shares a location, and one answer names who
 * represents them at every level the site holds: the U.S. representative
 * and the 2026 House race (on the new map, where a state was redrawn), both
 * senators, the state senator and representative, and the county. Each is
 * linked to the page that says more.
 *
 * Everything happens on the device. The page downloads this site's file for
 * the reader's state (data/lookup/<st>.js, kyc/lookup.py) and looks the ZIP
 * code or the point up in it; nothing the reader typed or shared is sent
 * anywhere, and the panel says so beside the control. The Census Bureau's
 * geocoder would take an address, but it cannot be called from a page (it
 * sends no CORS header) without loading a remote script, and it would send
 * the address away.
 *
 * A ZIP code is not a place (rule 85). The Census maps ZIP codes as ZIP Code
 * Tabulation Areas, from the addresses in each block; a ZIP used only for
 * post office boxes has none, and a ZIP can cross any line. So a ZIP names a
 * district outright only when WHOLE of its land is in it; otherwise every
 * district it touches is listed with its share, and the reader is offered
 * their location for an exact answer. A location near a line says so, as
 * the district pages do: the boundaries are the Census Bureau's at
 * 1:500,000, so within NEAR_KM of a line no one can say which side a home is
 * on from them, and the state's own lookup is linked.
 *
 * Who holds a seat is the profiles' (KYC.seated, rule 27) and the
 * legislature files'; a seat with no one listed is "nobody listed", never
 * "vacant" (rule 19). The geometry helpers here (KYC.place) are the district
 * pages' too: one implementation (rule 12).
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;

  /* kyc/lookup.py WHOLE: the share of a ZIP area's land in one district
   * that names it outright. The index carries the build's figure. */
  var WHOLE = 0.99;
  /* Within this of a line on the lookup boundaries a point is "near the
   * line": the 1:500,000 files are generalised by up to a few hundred metres. */
  var NEAR_KM = 0.4;
  /* A browser's fix vaguer than this names no district at all. */
  var ROUGH_KM = 10;
  /* More districts than this within reach: "where several districts meet". */
  var MAX_NEAR = 3;

  /* ============================================================ geometry */

  /** Where a longitude and latitude fall on a map drawn by the build with
   *  *p*, its projection (kyc/districts.projection_payload), or null. */
  function project(p, lon, lat) {
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

  /** A path's rings, replayed from the build's relative path data. */
  function pathRings(d) {
    var rings = [];
    String(d).split("M").forEach(function (part) {
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
    return rings;
  }

  /** Even-odd point in polygon, so a hole counts as outside. */
  function contains(rings, x, y) {
    var hit = false;
    for (var r = 0; r < rings.length; r++) {
      var ring = rings[r];
      for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
        if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) hit = !hit;
      }
    }
    return hit;
  }

  /** Shortest distance from a point to a shape's boundary, in the units of
   *  its coordinates, each axis scaled by *sx*, *sy* (1 when omitted). */
  function edgeDistance(rings, x, y, sx, sy) {
    sx = sx || 1;
    sy = sy || 1;
    var best = Infinity;
    for (var r = 0; r < rings.length; r++) {
      var ring = rings[r];
      for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        var ax = (ring[j][0] - x) * sx, ay = (ring[j][1] - y) * sy;
        var bx = (ring[i][0] - x) * sx, by = (ring[i][1] - y) * sy;
        var dx = bx - ax, dy = by - ay;
        var len = dx * dx + dy * dy;
        var t = len ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len)) : 0;
        var ex = ax + t * dx, ey = ay + t * dy;
        var dist = Math.sqrt(ex * ex + ey * ey);
        if (dist < best) best = dist;
      }
    }
    return best;
  }

  function boxOf(rings) {
    var b = [Infinity, Infinity, -Infinity, -Infinity];
    rings.forEach(function (ring) {
      ring.forEach(function (p) {
        if (p[0] < b[0]) b[0] = p[0];
        if (p[1] < b[1]) b[1] = p[1];
        if (p[0] > b[2]) b[2] = p[0];
        if (p[1] > b[3]) b[3] = p[1];
      });
    });
    return b;
  }

  /** Where a point falls among *shapes* (``{id: {rings, box}}``):
   *  ``{kind, inside, near}``, the district pages' words for it -
   *  - "in": inside one shape, no line within *margin*;
   *  - "line": within *margin* of a line between two or more shapes;
   *  - "edge": inside one shape, near a line no other shape shares - the
   *    state line or the shore;
   *  - "out": inside none, but near one;
   *  - "none": nowhere near.
   *  *sx*, *sy* scale the axes into the margin's units; *pad* is the margin
   *  in the coordinates' own units, for skipping shapes by their box. */
  function classify(shapes, x, y, margin, sx, sy, padX, padY) {
    var inside = [], near = [], ownEdge = false;
    Object.keys(shapes).forEach(function (id) {
      var s = shapes[id];
      var b = s.box;
      if (x < b[0] - padX || x > b[2] + padX || y < b[1] - padY || y > b[3] + padY) return;
      var dist = edgeDistance(s.rings, x, y, sx, sy);
      if (contains(s.rings, x, y)) {
        inside.push(id);
        if (dist <= margin) ownEdge = true;
      } else if (dist <= margin) {
        near.push(id);
      }
    });
    var kind = inside.length + near.length >= 2 ? "line"
      : inside.length === 1 ? (ownEdge ? "edge" : "in")
      : near.length ? "out" : "none";
    return { kind: kind, inside: inside, near: near };
  }

  /* ============================================================= loading */

  var loading = {};

  /** A file of this site's, loaded once, as a script: a page opened from
   *  disk cannot fetch(), and these files are scripts like every other. */
  function loadScript(path) {
    if (loading[path]) return loading[path];
    loading[path] = new Promise(function (resolve, reject) {
      var script = doc.createElement("script");
      script.src = KYC.siteRoot() + path;
      script.async = true;
      script.onload = function () { resolve(); };
      script.onerror = function () {
        delete loading[path];
        script.parentNode.removeChild(script);
        reject(new Error("could not load " + path));
      };
      doc.head.appendChild(script);
    });
    return loading[path];
  }

  function index() {
    return global.kycLookupIndex || null;
  }

  function files(code) {
    var i = index();
    return (i && i.files && i.files[code]) || null;
  }

  function whole() {
    var i = index();
    return (i && i.whole) || WHOLE;
  }

  /** One state's lookup file, decoded: its shapes as rings of degrees. */
  function lookupOf(code) {
    var have = (global.kycLookup || {})[code];
    if (have) return Promise.resolve(decoded(have));
    var f = files(code);
    if (!f) return Promise.reject(new Error("no lookup file for " + code));
    return loadScript(f.lookup).then(function () {
      var got = (global.kycLookup || {})[code];
      if (!got) throw new Error("the lookup file for " + code + " did not load");
      return decoded(got);
    });
  }

  function decoded(data) {
    if (data._shapes) return data;
    var q = data.q;
    var arcs = data.arcs.map(function (flat) {
      var pts = [], x = 0, y = 0;
      for (var i = 0; i + 1 < flat.length; i += 2) {
        x = i === 0 ? flat[0] : x + flat[i];
        y = i === 0 ? flat[1] : y + flat[i + 1];
        pts.push([x * q, y * q]);
      }
      return pts;
    });
    function ring(ids) {
      var out = [];
      ids.forEach(function (a) {
        var pts = a >= 0 ? arcs[a] : arcs[~a].slice().reverse();
        out = out.concat(out.length ? pts.slice(1) : pts);
      });
      return out;
    }
    function shapes(polys) {
      var out = {};
      Object.keys(polys || {}).forEach(function (id) {
        var rings = polys[id].map(ring);
        out[id] = { rings: rings, box: boxOf(rings) };
      });
      return out;
    }
    data._shapes = { cd: shapes(data.cd), next: shapes(data.next), co: shapes(data.co) };
    return data;
  }

  var legislatures = {};

  /** A state's legislature file: on its own page, the page's; elsewhere
   *  loaded, and the page's own global put back, since every legislature
   *  file sets the same one. Null where the state has none. */
  function legislatureOf(code) {
    if (legislatures[code] !== undefined) return Promise.resolve(legislatures[code]);
    var own = (global.kycLegislature || {})[code];
    if (own) {
      legislatures[code] = own;
      return Promise.resolve(own);
    }
    var f = files(code);
    if (!f || !f.legislature) return Promise.resolve(null);
    var before = global.kycLegislature;
    return loadScript(f.legislature).then(function () {
      var got = (global.kycLegislature || {})[code] || null;
      legislatures[code] = got;
      if (before) global.kycLegislature = before;
      return got;
    });
  }

  /* =========================================================== answering */

  function shareSort(a, b) { return b[1] - a[1] || String(a[0]).localeCompare(String(b[0])); }

  /** A point's answer in one state's lookup: each level's ``{kind,
   *  inside, near}``, ids as strings. */
  function pointIn(data, lon, lat, marginKm) {
    var kx = 111.32 * Math.cos(lat * Math.PI / 180), ky = 110.574;
    var padX = marginKm / kx, padY = marginKm / ky;
    var out = { co: classify(data._shapes.co, lon, lat, marginKm, kx, ky, padX, padY) };
    if (data.atLarge) {
      // One district: the counties say whether the point is in the state.
      var c = out.co;
      out.cd = { kind: c.inside.length ? "in" : c.kind === "none" ? "none" : "out",
                 inside: c.inside.length ? ["0"] : [], near: c.inside.length ? [] : c.near.length ? ["0"] : [] };
    } else {
      out.cd = classify(data._shapes.cd, lon, lat, marginKm, kx, ky, padX, padY);
    }
    if (data.next) out.next = classify(data._shapes.next, lon, lat, marginKm, kx, ky, padX, padY);
    return out;
  }

  /** The state legislature's districts at a point, from the legislature
   *  file's own lines and projection. */
  function legislatureAt(leg, lon, lat, marginKm) {
    var at = leg && project(leg.projection, lon, lat);
    if (!at) return null;
    var out = {};
    var margin = marginKm / leg.unitKm;
    ["upper", "lower"].forEach(function (chamber) {
      var c = leg.chambers[chamber];
      if (!c) return;
      if (!c._shapes) {
        c._shapes = {};
        Object.keys(c.districts).forEach(function (id) {
          var rings = pathRings(c.districts[id].d);
          c._shapes[id] = { rings: rings, box: c.districts[id].box || boxOf(rings) };
        });
      }
      out[chamber] = classify(c._shapes, at[0], at[1], margin, 1, 1, margin, margin);
    });
    return out;
  }

  function inState(found) {
    return found.cd.inside.length > 0;
  }

  /** Which state a point is in, and everything there: a Promise of
   *  ``{code, data, found, leg}`` or ``{code: null}``. Only the states whose
   *  box holds the point are loaded. */
  function where(lon, lat, accuracy, only) {
    var i = index();
    if (!i) return Promise.reject(new Error("the lookup index did not load"));
    var marginKm = NEAR_KM + (isFinite(accuracy) && accuracy > 0 ? accuracy / 1000 : 0);
    var codes = Object.keys(i.boxes).filter(function (code) {
      if (only && code !== only) return false;
      var b = i.boxes[code];
      return lon >= b[0] - 0.1 && lon <= b[2] + 0.1 && lat >= b[1] - 0.1 && lat <= b[3] + 0.1;
    });
    return Promise.all(codes.map(function (code) {
      return lookupOf(code).then(function (data) {
        return { code: code, data: data, found: pointIn(data, lon, lat, marginKm) };
      }, function () { return null; });
    })).then(function (all) {
      all = all.filter(Boolean);
      var hit = all.filter(function (a) { return inState(a.found); })[0] ||
        all.filter(function (a) { return a.found.cd.kind !== "none"; })[0];
      if (!hit) return { code: null, tried: codes.length, loaded: all.length };
      return legislatureOf(hit.code).then(function (leg) {
        hit.leg = leg;
        hit.legFound = legislatureAt(leg, lon, lat, marginKm);
        hit.marginKm = marginKm;
        return hit;
      }, function () { return hit; });
    });
  }

  /** A ZIP code's answer: a Promise of ``[{code, data, entry, leg}]``, one
   *  per state its area reaches (a few cross a state line), empty when the
   *  Census has no ZIP area by that number. */
  function zip(code5) {
    var i = index();
    if (!i) return Promise.reject(new Error("the lookup index did not load"));
    var states = (i.zip3 || {})[code5.slice(0, 3)] || [];
    return Promise.all(states.map(function (code) {
      return lookupOf(code).then(function (data) {
        var entry = data.zips[code5];
        if (!entry) return null;
        return legislatureOf(code).then(function (leg) {
          return { code: code, data: data, entry: entry, leg: leg };
        }, function () { return { code: code, data: data, entry: entry, leg: null }; });
      });
    })).then(function (all) {
      return all.filter(Boolean).sort(function (a, b) {
        return landIn(b.entry) - landIn(a.entry);
      });
    });
  }

  function landIn(entry) {
    return (entry.cd || []).reduce(function (sum, p) { return sum + p[1]; }, 0);
  }

  /* ========================================================== the people */

  function people() {
    return global.legislatorsData || [];
  }

  function stateInfo(code) {
    return (KYC.meta().states || {})[code] || {};
  }

  function seatLabel(code, n) {
    return code + "-" + (String(n) === "0" ? "AL" : n);
  }

  /** Who sits for House district *n* of *code* now (rule 27). */
  function houseHolders(code, n) {
    return people().filter(function (p) {
      return KYC.seated(p) && p.state === code && p.chamber.indexOf("House") !== -1 &&
        String(p.districtNum) === String(n);
    });
  }

  function senators(code) {
    return people().filter(function (p) {
      return KYC.seated(p) && p.state === code && p.chamber.indexOf("Senate") !== -1;
    });
  }

  function races() {
    return global.kycRaces || [];
  }

  function houseRace(code, n) {
    return races().filter(function (r) {
      return r.chamber === "House" && r.state === code && String(r.district) === String(n);
    })[0] || null;
  }

  function senateRaces(code) {
    return races().filter(function (r) { return r.chamber === "Senate" && r.state === code; });
  }

  /** Who is running in *race*: its people, less a member who holds a seat
   *  of that number but is running elsewhere (rule 30). Once the primary is
   *  decided, only those on the November ballot. The district pages list
   *  a race's people with this too (rule 12). */
  function running(race) {
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

  function partyLetter(p) {
    var key = KYC.partyKey(p);
    return key === "d" ? "D" : key === "r" ? "R" : key === "i" ? "I" : "";
  }

  /** A person's name, linked to their profile on this page. */
  function personLink(p, extra) {
    var party = partyLetter(p);
    var bits = [party, extra].filter(Boolean).join(", ");
    return '<a href="#/profile/' + KYC.escapeAttr(encodeURIComponent(p.id)) + '">' +
      KYC.escapeHtml(p.name) + "</a>" + (bits ? " (" + KYC.escapeHtml(bits) + ")" : "");
  }

  function list(items) {
    return items.length < 2 ? items.join("")
      : items.length === 2 ? items[0] + " and " + items[1]
      : items.slice(0, -1).join(", ") + " and " + items[items.length - 1];
  }

  function pct(share) {
    var whole = Math.round(share * 100);
    if (whole >= 100 && share < 1) whole = 99;
    return whole < 1 ? "under 1%" : whole + "%";
  }

  function districtsPage(code, now, next) {
    var info = (KYC.meta().districtMaps || {})[code];
    if (!info) return "";
    var params = [];
    if (next && next.length) params.push("d=" + next.slice(0, MAX_NEAR).join(","));
    if (now && now.length && info.redrawn && now.join(",") !== (next || []).join(",")) {
      params.push("was=" + now.slice(0, MAX_NEAR).join(","));
    }
    return KYC.siteRoot() + info.page + (params.length ? "#/?" + params.join("&") : "");
  }

  /* ============================================================ rendering */

  function row(term, body) {
    return '<div class="findrep-row"><dt>' + term + "</dt><dd>" + body + "</dd></div>";
  }

  /** Each of *parts* (``[[id, share]]``, or ids alone for a point), as
   *  *one(id)*'s words, with the share where there is more than one. */
  function each(parts, one) {
    var shares = parts.length > 1 && Array.isArray(parts[0]) && typeof parts[0][1] === "number";
    return parts.map(function (p) {
      var id = Array.isArray(p) ? p[0] : p;
      return '<div class="findrep-item">' +
        (shares ? '<span class="findrep-share">' + pct(p[1]) + "</span> " : "") + one(id) + "</div>";
    }).join("");
  }

  /** The House member for *n*, or what the build records about the seat. */
  function holderWords(code, n) {
    var held = houseHolders(code, n);
    if (held.length) {
      return held.map(function (p) { return personLink(p, seatLabel(code, n)); }).join(", ");
    }
    var v = KYC.vacancyOf(code, Number(n));
    return KYC.escapeHtml(seatLabel(code, n)) + ": " +
      (v ? KYC.escapeHtml(KYC.vacancyNote(v)) : "no sitting member");
  }

  function raceWords(code, n) {
    var race = houseRace(code, n);
    if (!race) return KYC.escapeHtml(seatLabel(code, n)) + ": no race this year";
    return raceLine(code, race, seatLabel(code, n));
  }

  /** A race: its name, linked to it on the state page, and its people
   *  with the status words every view uses (KYC.raceStatusOf, rule 63). */
  function raceLine(code, race, label) {
    var who = running(race).map(function (p) {
      var status = KYC.raceStatusOf(p, "short");
      return personLink(p) + (status && status.label
        ? ' <span class="findrep-status">' + KYC.escapeHtml(status.label) + "</span>" : "");
    });
    // Nominees with no profile here are named too, as in every view that
    // lists a race (kyc-cards.js): left out, a member read as unopposed.
    var others = KYC.cards ? KYC.cards.unprofiledNote(race, "findrep-note") : "";
    return '<a href="' + KYC.escapeAttr(KYC.stateUrl(code) + "#race-" + race.id) + '">' +
      KYC.escapeHtml(label) + "</a>" + (who.length ? ": " + list(who)
        : others ? "" : ": nobody with a profile here") + others;
  }

  /** The federal rows: House member, House race, senators, Senate races.
   *  *now* and *next* are ``[[district, share]]`` or district lists, on the
   *  map members sit under and the map for the 2026 race. */
  function federalRows(code, now, next) {
    var rows = [];
    if (!people().length) {
      rows.push(row("Congress", '<a href="' + KYC.escapeAttr(KYC.stateUrl(code) + "#findrep") +
        '">Your members of Congress, on the ' + KYC.escapeHtml(KYC.stateName(code)) +
        " page &rsaquo;</a>"));
      return rows;
    }
    var info = stateInfo(code);
    var title = info.delegates && !info.house ? (info.delegateTitle || "Delegate") + " to the U.S. House"
      : "U.S. representative";
    rows.push(row(KYC.escapeHtml(title), each(now, function (n) { return holderWords(code, n); })));
    var record = KYC.recordPhase();
    var raceTitle = record ? "The " + ((KYC.meta().election || {}).year || "") + " House race"
      : "Your " + ((KYC.meta().election || {}).year || "") + " House race";
    rows.push(row(KYC.escapeHtml(raceTitle), each(next, function (n) { return raceWords(code, n); })));
    if (info.senators) {
      var sen = senators(code);
      rows.push(row("U.S. senators", sen.length
        ? sen.map(function (p) { return personLink(p); }).join(", ")
        : "no sitting senators on this site's roster"));
      var sr = senateRaces(code);
      if (sr.length) {
        rows.push(row(record ? "The Senate race" : "Senate race", sr.map(function (r) {
          return '<div class="findrep-item">' + raceLine(code, r, (r.special ? "Special election"
            : "U.S. Senate") + " in " + KYC.stateName(code)) + "</div>";
        }).join("")));
      }
    }
    return rows;
  }

  function districtName(c, id) {
    var d = c.districts[id];
    var name = d ? d.name : id;
    return /^\d+[A-Z]?$/.test(name) ? "District " + name : name;
  }

  /** The state legislature rows, one per chamber, from the legislature
   *  file. The people listed for a district are the file's, linked to the
   *  district on the legislature page; nobody listed is said so. */
  function legislatureRows(code, leg, picks) {
    if (!leg) return [];
    var rows = [];
    var page = KYC.siteRoot() + leg.page;
    ["upper", "lower"].forEach(function (chamber) {
      var c = leg.chambers[chamber];
      var parts = picks[chamber];
      if (!c) return;
      var title = KYC.escapeHtml(stateWord(code) + " " + c.title);
      if (!parts || !parts.length) {
        // Said, not dropped: a level missing from the answer reads as none.
        rows.push(row(title, "not found on its district map; " + '<a href="' +
          KYC.escapeAttr(page) + '">pick your district on the legislature page &rsaquo;</a>'));
        return;
      }
      var body = each(parts, function (id) {
        var members = (c.members || {})[id] || [];
        var href = page + "#/?" + (chamber === "lower" ? "chamber=lower&" : "") + "d=" +
          encodeURIComponent(id);
        return '<a href="' + KYC.escapeAttr(href) + '">' + KYC.escapeHtml(districtName(c, id)) +
          "</a>: " + (members.length ? members.map(function (m) {
            return KYC.escapeHtml(m.name) + (m.partyKey ? " (" + KYC.escapeHtml(m.partyKey) + ")" : "");
          }).join(", ") : "nobody listed");
      });
      var unplaced = (leg.unplaced || []).filter(function (m) { return m.chamber === chamber; });
      if (unplaced.length) {
        body += '<div class="findrep-note">' + unplaced.length + " member" +
          (unplaced.length === 1 ? " of this chamber is" : "s of this chamber are") +
          " not placed on a district map; " + '<a href="' + KYC.escapeAttr(page) +
          '">the legislature page lists them</a>.</div>';
      }
      rows.push(row(title, body));
    });
    return rows;
  }

  function stateWord(code) {
    return KYC.stateName(code);
  }

  function countyRows(code, data, parts) {
    if (!parts || !parts.length) return [];
    var word = data.area || "county";
    var label = word.charAt(0).toUpperCase() + word.slice(1);
    return [row(KYC.escapeHtml(label), each(parts, function (geoid) {
      var name = (data.names || {})[geoid] || geoid;
      var also = (data.noCounty || {})[geoid];
      var words = KYC.escapeHtml(name) + (also ? " (" + KYC.escapeHtml(also) + ")" : "");
      return data.countyPages
        ? '<a href="' + KYC.escapeAttr(KYC.siteRoot() + "counties/" + code.toLowerCase() +
          ".html#/?county=" + encodeURIComponent(geoid)) + '">' + words + "</a>"
        : words;
    }))];
  }

  /** "Check with Ohio's own lookup", from the state's voting pages. */
  function officialLookup(code) {
    var links = (KYC.meta().voting || {})[code] || {};
    var url = links.status || links.polling;
    return url ? '<a href="' + KYC.escapeAttr(url) + '" target="_blank" rel="noopener noreferrer">' +
      "Check with " + KYC.escapeHtml(KYC.possessive(KYC.stateName(code))) + " own lookup &rsaquo;</a>" : "";
  }

  function voteLink(code) {
    return '<a class="btn" href="' + KYC.escapeAttr(KYC.stateUrl(code) + "#voting") + '">' +
      KYC.icon("vote") + " How to vote in " + KYC.escapeHtml(KYC.stateName(code)) + "</a>";
  }

  /** The plan a seat is held under, and the plan of the 2026 race: a
   *  redrawn state's members sit on the old map until the new Congress does. */
  function plans(data) {
    var redrawn = !!data.next;
    return { now: redrawn && KYC.recordPhase() ? "next" : "cd", race: redrawn ? "next" : "cd" };
  }

  function answer(head, code, rows, notes) {
    return '<div class="findrep-answer">' +
      '<p class="findrep-place">' + head + "</p>" +
      '<dl class="findrep-list">' + rows.join("") + "</dl>" +
      (notes.length ? '<p class="findrep-note">' + notes.join(" ") + "</p>" : "") +
      '<p class="findrep-actions">' + voteLink(code) + "</p>" +
      "</div>";
  }

  function sourcesNote(data) {
    return '<details class="findrep-sources"><summary>Sources</summary>' +
      (data.sources || []).map(function (s) { return "<p>" + KYC.escapeHtml(s) + "</p>"; }).join("") +
      "</details>";
  }

  /** The answer for a ZIP code, from ``zip()``'s list. */
  function zipAnswer(code5, found) {
    if (!found.length) {
      return '<p class="findrep-note">' + KYC.escapeHtml(code5) + " is not one of the Census " +
        "Bureau's ZIP Code Tabulation Areas. A ZIP code used only for post office boxes, or by " +
        "a single building or business, has no area of its own, and nor does one created " +
        "since 2020. Try the ZIP code of your home, or use your location.</p>";
    }
    var out = [];
    var split = false;
    found.forEach(function (f) {
      var e = f.entry, data = f.data, code = f.code, w = whole();
      var key = plans(data);
      function pick(parts) {
        parts = (parts || []).slice().sort(shareSort);
        if (parts.length && parts[0][1] >= w) return [parts[0][0]];
        if (parts.length > 1) split = true;
        return parts;
      }
      var now = pick(e[key.now]), next = pick(e[key.race]);
      var rows = federalRows(code, now, next)
        .concat(legislatureRows(code, f.leg, { upper: pick(e.su), lower: pick(e.sl) }))
        .concat(countyRows(code, data, pick(e.co)));
      var head = "ZIP " + KYC.escapeHtml(code5) + ", " + KYC.escapeHtml(KYC.stateName(code)) +
        (found.length > 1 ? " (" + pct(landIn(e)) + " of its land)" : "");
      var notes = [];
      if (data.next && !KYC.recordPhase()) {
        notes.push(KYC.escapeHtml(KYC.stateName(code)) + "'s House map was redrawn for 2026: the " +
          "representative is the one elected on the old map, the race is on the new one.");
      }
      var map = districtsPage(code, ids(now), ids(next));
      if (map) notes.push('<a href="' + KYC.escapeAttr(map) + '">See it on the district map &rsaquo;</a>');
      out.push(answer(head, code, rows, notes) + sourcesNote(data));
    });
    var caveat = split
      ? "A ZIP code can cross district lines, and this one does. The shares are of the ZIP " +
        "area's land, not its people, so they cannot say which side your home is on: use your " +
        "location for an exact answer, or your state's own lookup."
      : "The Census Bureau's ZIP Code Tabulation Areas follow ZIP codes closely but not " +
        "exactly; a few addresses fall outside their ZIP code's area.";
    return out.join("") + '<p class="findrep-note">' + caveat + " " +
      officialLookup(found[0].code) + "</p>";
  }

  function ids(parts) {
    return (parts || []).map(function (p) { return Array.isArray(p) ? p[0] : p; });
  }

  function reach(f) {
    return f ? f.inside.concat(f.near) : [];
  }

  /** "about 30 m", "about 2.5 km": never "about 0 km" (RACES-02). */
  function distance(metres) {
    if (!isFinite(metres)) return "";
    if (metres < 1000) return "about " + Math.max(10, Math.round(metres / 10) * 10) + " m";
    return "about " + (Math.round(metres / 100) / 10) + " km";
  }

  /** The answer for a location, from ``where()``. */
  function pointAnswer(hit, accuracy) {
    if (!hit.code) {
      return '<p class="findrep-note">That location is not in any state, D.C. or territory ' +
        'this site covers. <a href="' + KYC.escapeAttr(KYC.siteRoot() + "states/index.html") +
        '">Find your state &rsaquo;</a></p>';
    }
    var code = hit.code, data = hit.data, f = hit.found, key = plans(data);
    var crowded = [];
    function pick(found) {
      var r = reach(found);
      if (r.length > MAX_NEAR) crowded.push(r);
      return r;
    }
    var now = pick(f[key.now]), next = pick(f[key.race]);
    var legPicks = {};
    if (hit.legFound) {
      Object.keys(hit.legFound).forEach(function (chamber) {
        legPicks[chamber] = pick(hit.legFound[chamber]);
      });
    }
    var rows = federalRows(code, now, next)
      .concat(legislatureRows(code, hit.leg, legPicks))
      .concat(countyRows(code, data, pick(f.co)));
    var notes = [];
    var unsure = [f[key.now], f[key.race], f.co].concat(hit.legFound
      ? [hit.legFound.upper, hit.legFound.lower] : []).some(function (x) {
      return x && x.kind !== "in" && x.kind !== "none";
    });
    if (crowded.length) {
      notes.push("You are where several districts meet; the boundaries here cannot tell " +
        "which you are in, so each one in reach is listed.");
    } else if (unsure) {
      notes.push("Where two districts are listed, you are near the line between them: the " +
        "boundaries here are the Census Bureau's at 1:500,000, and within about " +
        (NEAR_KM * 1000) + " m of a line they cannot say which side you are on" +
        (accuracy >= 100 ? ", and your browser placed you to within " + distance(accuracy) : "") + ".");
    }
    if (data.next && !KYC.recordPhase()) {
      notes.push(KYC.escapeHtml(KYC.stateName(code)) + "'s House map was redrawn for 2026: the " +
        "representative is the one elected on the old map, the race is on the new one.");
    }
    var map = districtsPage(code, now, next);
    if (map) notes.push('<a href="' + KYC.escapeAttr(map) + '">See it on the district map &rsaquo;</a>');
    if (unsure || crowded.length) notes.push(officialLookup(code));
    return answer("Your location, " + KYC.escapeHtml(KYC.stateName(code)), code, rows, notes) +
      sourcesNote(data);
  }

  /* ============================================================ the panel */

  var PRIVACY = "Your ZIP code and location stay on this device: the page looks them up " +
    "itself, in this site's file for your state, and sends them nowhere.";

  function canLocate() {
    return !!(global.navigator && global.navigator.geolocation);
  }

  /** The panel's controls, written into *slot* (``[data-findrep]``). */
  function mount(slot) {
    if (!slot || slot.getAttribute("data-findrep-ready")) return;
    slot.setAttribute("data-findrep-ready", "1");
    var code = slot.getAttribute("data-findrep-state") || "";
    var uid = "findrep" + (++mounted);
    var vote = code
      ? '<a class="btn" href="#voting">' + KYC.icon("vote") + " How to vote in " +
        KYC.escapeHtml(KYC.stateName(code)) + "</a>"
      : voteHome();
    slot.innerHTML =
      '<h2 class="findrep-title" id="' + uid + 'Title">' + KYC.icon("pin") +
        " Find who represents you</h2>" +
      '<form class="findrep-form" novalidate>' +
        '<label class="findrep-label" for="' + uid + 'Zip">ZIP code</label>' +
        '<input class="text-input findrep-zip" id="' + uid + 'Zip" name="zip" type="text" ' +
          'inputmode="numeric" autocomplete="postal-code" maxlength="10" placeholder="e.g. 43215" ' +
          'aria-describedby="' + uid + 'Note">' +
        '<button type="submit" class="btn">Find</button>' +
        (canLocate() ? '<button type="button" class="btn" data-findrep-locate>' + KYC.icon("pin") +
          " Use my location</button>" : "") +
        '<span class="findrep-vote">' + vote + "</span>" +
      "</form>" +
      '<p class="field-note findrep-privacy" id="' + uid + 'Note">' + PRIVACY + "</p>" +
      '<div class="findrep-result" role="status" aria-live="polite" hidden></div>';
    slot.setAttribute("aria-labelledby", uid + "Title");
    var form = slot.querySelector("form");
    var input = slot.querySelector(".findrep-zip");
    var out = slot.querySelector(".findrep-result");
    var locate = slot.querySelector("[data-findrep-locate]");
    function show(html) {
      out.hidden = false;
      out.innerHTML = html;
    }
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var value = String(input.value || "").trim();
      var m = /^(\d{5})(?:-?\d{4})?$/.exec(value);
      if (!m) {
        show('<p class="findrep-note">Type a five-digit ZIP code.</p>');
        input.focus();
        return;
      }
      show('<p class="findrep-note">Looking up ' + KYC.escapeHtml(m[1]) + "&hellip;</p>");
      zip(m[1]).then(function (found) {
        show(zipAnswer(m[1], found));
        remember(found.length === 1 ? found[0].code : "");
      }, function () {
        show('<p class="findrep-note">The ZIP code lookup did not load. Check your connection ' +
          "and try again.</p>");
      });
    });
    if (locate) {
      locate.addEventListener("click", function () {
        locate.disabled = true;
        show('<p class="findrep-note">Finding your location&hellip;</p>');
        global.navigator.geolocation.getCurrentPosition(function (pos) {
          locate.disabled = false;
          var acc = pos.coords.accuracy;
          if (isFinite(acc) && acc / 1000 > ROUGH_KM) {
            show('<p class="findrep-note">Your browser shared only an approximate location (to ' +
              "within " + distance(acc) + "), too rough to place in a district. Type your " +
              "ZIP code instead.</p>");
            return;
          }
          where(pos.coords.longitude, pos.coords.latitude, acc).then(function (hit) {
            show(pointAnswer(hit, acc));
            remember(hit.code || "");
          }, function () {
            show('<p class="findrep-note">The lookup did not load. Check your connection and ' +
              "try again.</p>");
          });
        }, function (err) {
          locate.disabled = false;
          show('<p class="findrep-note">' + (err && err.code === 1
            ? "Your browser did not share a location." : "Your location could not be found.") +
            " Type your ZIP code instead.</p>");
        }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
      });
    }
  }

  var mounted = 0;

  /** The home page's "How to vote in your state": the remembered state's
   *  voting block, or the list of states. */
  function voteHome() {
    var code = KYC.rememberedState();
    var known = code && (KYC.meta().states || {})[code];
    return '<a class="btn" data-findrep-vote href="' + KYC.escapeAttr(known
      ? KYC.stateUrl(code) + "#voting" : KYC.siteRoot() + "states/index.html") + '">' +
      KYC.icon("vote") + " How to vote in " + KYC.escapeHtml(known ? KYC.stateName(code) : "your state") +
      "</a>";
  }

  /** A reader's state, remembered in this browser for the sidebar and the
   *  home page's voting link - a per-viewer convenience (kyc.js). */
  function remember(code) {
    if (!code || !(KYC.meta().states || {})[code]) return;
    KYC.rememberState(code);
    Array.prototype.forEach.call(doc.querySelectorAll("[data-findrep-vote]"), function (a) {
      a.setAttribute("href", KYC.stateUrl(code) + "#voting");
      a.innerHTML = KYC.icon("vote") + " How to vote in " + KYC.escapeHtml(KYC.stateName(code));
    });
  }

  function mountAll(root) {
    Array.prototype.forEach.call((root || doc).querySelectorAll("[data-findrep]"), mount);
  }

  KYC.place = {
    project: project,
    pathRings: pathRings,
    contains: contains,
    edgeDistance: edgeDistance,
    classify: classify,
  };

  KYC.findRep = {
    NEAR_KM: NEAR_KM,
    MAX_NEAR: MAX_NEAR,
    ROUGH_KM: ROUGH_KM,
    mount: mount,
    mountAll: mountAll,
    where: where,
    zip: zip,
    running: running,
    federalRows: federalRows,
    distance: distance,
    officialLookup: officialLookup,
    zipAnswer: zipAnswer,
    pointAnswer: pointAnswer,
  };

  KYC.ready(function () { mountAll(doc); });
})(window);
