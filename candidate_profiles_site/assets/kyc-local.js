/* Know Your Candidate - a state's counties, and every local government in
 * each: county governments, cities and towns, townships, school districts,
 * special districts, and the school systems a state, county or city runs.
 *
 * Everything comes from window.kycLocal, built by kyc/counties.py from the
 * Census Bureau's county and place boundaries and its 2022 Government Units
 * listing. Governments are joined to counties on the county's Census code,
 * and a city or town to its government only where the build found the join
 * one to one. The map is the shared region map (kyc-regionmap.js), in two
 * views:
 *   - Counties: each county shaded by how many local governments it has;
 *   - Cities and towns: every incorporated place a dot, coloured by the
 *     legal form the Census names (city, town, village, borough), and in
 *     the twenty states that have them, every town or township government
 *     a ring at its county subdivision, joined on the Census code.
 *
 * The address carries the view and the pick:
 * #/?county=48201, #/?view=cities&city=4835000.
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;
  var code = doc.body.getAttribute("data-state") || "";
  var state = (global.kycLocal || {})[code] || null;
  var view = "counties";
  var picked = "";
  var pickedCity = "";
  var map = null;

  var KINDS = {
    county: "County government",
    municipal: "Cities, towns and villages",
    township: "Towns and townships",
    school: "School districts",
    special: "Special districts",
    dependent: "School systems run by another government",
  };
  var ORDER = ["county", "municipal", "township", "school", "special", "dependent"];
  /* Shades for the count of governments in a county: five steps of one hue
   * (the --scale-* colours), never a party colour. */
  var EDGES = [10, 25, 50, 100];
  /* A place's dot by its legal form, in the --cat-* colours; every other
   * form (a consolidated government, a municipality) is "other". */
  var FORMS = [
    ["city", "City"],
    ["town", "Town"],
    ["village", "Village"],
    ["borough", "Borough"],
    ["other", "Other legal form"],
    ["township", "Town or township government"],
  ];

  function el(id) { return doc.getElementById(id); }
  function plural(n, word) { return n.toLocaleString("en-US") + " " + word + (n === 1 ? "" : "s"); }

  function counted(rows) {
    return rows.filter(function (r) { return r[0] !== "dependent"; }).length;
  }

  function shade(n) {
    var step = 1;
    EDGES.forEach(function (edge) { if (n >= edge) step += 1; });
    return "scale-" + step;
  }

  /* --------------------------------------------------------------- cities */

  // [x, y, kind, name, county, ref, status]; ref is [county code, row] or
  // null, status the Census's functional status where it is not "A".
  // Towns and townships (county subdivisions, ten-digit codes) share the
  // view with the incorporated places (seven digits); each is joined.
  var towns = (state && state.towns) || {};
  var cities = {};
  [(state && state.cities) || {}, towns].forEach(function (set) {
    Object.keys(set).forEach(function (id) { cities[id] = set[id]; });
  });
  function isTown(id) { return Object.prototype.hasOwnProperty.call(towns, id); }
  var TOWN_PX = 2.3;
  var SHARED_PX = 5.8;
  var cityIds = Object.keys(cities).sort(function (a, b) {
    return cities[a][3].localeCompare(cities[b][3], "en") || a.localeCompare(b);
  });
  // "48201:12" -> the place joined to that government row.
  var cityOfRow = {};
  cityIds.forEach(function (id) {
    var ref = cities[id][5];
    if (ref) cityOfRow[ref[0] + ":" + ref[1]] = id;
  });

  function form(kind) {
    return ["city", "town", "village", "borough"].indexOf(kind) !== -1 ? kind : "other";
  }

  /* A place's mark: its legal form's colour, or the town or township ring. */
  function formOf(id) {
    return isTown(id) ? "township" : form(cities[id][2]);
  }

  /* What a place is, in a line: "Incorporated village", "Charter township
   * government (a county subdivision)". */
  function whatItIs(id) {
    var kind = cities[id][2];
    if (isTown(id)) {
      return (kind ? kind.charAt(0).toUpperCase() + kind.slice(1) : "Town or township") +
        " government (a county subdivision)";
    }
    return kind ? "Incorporated " + kindText(kind) : "Incorporated place";
  }

  /* The legal form as a reader should see it. The Census calls the part of
   * a consolidated government outside its other places its "balance". */
  function kindText(kind) {
    if (kind === "balance") return "consolidated government (the part outside its other places)";
    return kind;
  }

  /* The Census's own words for a place's functional status (2025
   * Gazetteer; census.gov functional status codes). "A", an active
   * government, needs no note; "F" is a balance, said by its kind. */
  var STATUS = {
    I: "an inactive governmental unit",
    N: "a nonfunctioning legal entity",
    B: "an active government partially consolidated with another government, with separate officials",
    C: "an active government consolidated with another government, with a single set of officials",
    G: "an active government subordinate to another unit of government",
  };
  // Statuses that explain on their own why no government is shown.
  var NOT_GOVERNING = { I: true, N: true };

  function governmentRow(ref) {
    if (!ref) return null;
    var rows = state.governments[ref[0]];
    if (!rows) {
      var area = state.unmatched.filter(function (u) { return u.fips === ref[0]; })[0];
      rows = area ? area.governments : null;
    }
    return rows ? rows[ref[1]] || null : null;
  }

  /* A township and a city with one boundary (Oak Park's village and
   * township) get one point: each panel names the other, since the ring
   * drawn over the dot is small to tap. */
  var samePoint = {};
  cityIds.forEach(function (id) {
    var key = cities[id][0] + "," + cities[id][1];
    (samePoint[key] = samePoint[key] || []).push(id);
  });

  function sharesPoint(id) {
    return (samePoint[cities[id][0] + "," + cities[id][1]] || []).length > 1;
  }

  function cityDots() {
    if (view !== "cities") return [];
    // Rings first, so a city's dot is never covered: drawn over the dots,
    // neighbouring rings took the taps meant for Allentown and 159 other
    // Minnesota and Pennsylvania cities on a phone.
    return cityIds.filter(isTown).concat(cityIds.filter(function (id) { return !isTown(id); }))
      .map(function (id) {
      var c = cities[id];
      // Townships tile a state about 6 px apart on a phone (Minnesota has
      // 1,774), so their rings are smaller than the cities' dots - except
      // a ring at a city's own point, drawn round the dot so both show.
      var px = !isTown(id) ? 0 : sharesPoint(id) ? SHARED_PX : TOWN_PX;
      var named = c[2] && c[3].toLowerCase().indexOf(c[2].toLowerCase()) !== 0;
      return { id: id, at: [c[0], c[1]], cls: "dot-" + formOf(id), px: px,
               title: c[3] + (named ? " (" + kindText(c[2]) + ")" : "") };
    });
  }

  function look(fips) {
    var rows = state.governments[fips] || [];
    var n = counted(rows);
    var title = state.counties[fips].name + ": " + plural(n, "local government");
    if (view === "cities") return { cls: "district-shape region-plain", title: title };
    return { cls: "district-shape region-" + shade(n), title: title };
  }

  /* ----------------------------------------------------------------- lists */

  function size(row) {
    if (row[4] === "") return "";
    return (row[0] === "school" || row[0] === "dependent" ? "enrollment " : "population ") +
      Number(row[4]).toLocaleString("en-US");
  }

  /* One government. *key* ("48201:12") finds the place joined to it, which
   * gets a button that shows it on the cities map. */
  function item(row, key) {
    var name = row[3]
      ? '<a href="' + KYC.escapeAttr(row[3]) + '" target="_blank" rel="noopener noreferrer">' +
        KYC.escapeHtml(row[1]) + "</a>"
      : KYC.escapeHtml(row[1]);
    var bits = [row[5], row[2], size(row), row[6] === "inactive" ? "listed as inactive" : ""]
      .filter(Boolean).map(KYC.escapeHtml);
    var place = key && cityOfRow[key];
    var pin = place
      ? ' <button type="button" class="local-pin" data-city="' + KYC.escapeAttr(place) +
        '" aria-label="Show ' + KYC.escapeAttr(cities[place][3]) + ' on the map">' +
        KYC.icon("pin") + "</button>"
      : "";
    return '<li class="local-item"><span class="local-name">' + name + pin + "</span>" +
      (bits.length ? '<span class="local-meta">' + bits.join(" · ") + "</span>" : "") + "</li>";
  }

  function groups(rows, filter, fips) {
    var q = KYC.foldText ? KYC.foldText(filter || "") : (filter || "").toLowerCase();
    var html = "";
    ORDER.forEach(function (kind) {
      var mine = [];
      rows.forEach(function (r, i) {
        if (r[0] !== kind) return;
        if (q) {
          var text = r[1] + " " + r[5] + " " + r[2];
          if ((KYC.foldText ? KYC.foldText(text) : text.toLowerCase()).indexOf(q) === -1) return;
        }
        mine.push(item(r, fips ? fips + ":" + i : ""));
      });
      if (!mine.length) return;
      html += '<h3 class="local-group">' + KYC.escapeHtml(KINDS[kind]) +
        ' <span class="faint">' + mine.length + "</span></h3>" +
        '<ul class="local-list">' + mine.join("") + "</ul>";
    });
    return html || '<p class="faint">Nothing matches.</p>';
  }

  function showCounty(fips) {
    var rows = state.governments[fips] || [];
    var county = state.counties[fips];
    var n = counted(rows);
    el("localPanelTitle").textContent = county.name;
    el("localPanelBody").innerHTML =
      '<p class="local-total">' + plural(n, "local government") + " in 2022</p>" +
      '<label class="sr-only" for="localFilter">Filter this county\'s governments</label>' +
      '<input type="search" id="localFilter" class="local-filter" placeholder="Filter by name, kind or city" autocomplete="off">' +
      '<div id="localGroups">' + groups(rows, "", fips) + "</div>";
    el("localFilter").addEventListener("input", function () {
      el("localGroups").innerHTML = groups(rows, el("localFilter").value, fips);
    });
  }

  function countyButton(fips) {
    if (!fips || !state.counties[fips]) return "";
    return '<button type="button" class="sidebar-link local-county-link" data-county="' +
      KYC.escapeAttr(fips) + '">' + KYC.escapeHtml(state.counties[fips].name) +
      ": every local government ›</button>";
  }

  function showCity(id) {
    var c = cities[id];
    var row = governmentRow(c[5]);
    el("localPanelTitle").textContent = c[3];
    // Where the place is, and where its government is listed: a city on a
    // county line can be in one county and listed under the other (Berthoud,
    // Colorado: its point in Weld, its government under Larimer). The link
    // goes to the county whose list holds the government.
    var here = c[4] && state.counties[c[4]] ? c[4] : "";
    var filed = c[5] && state.counties[c[5][0]] ? c[5][0] : here;
    var body = '<p class="local-total"><span class="swatch dot-swatch dot-' + formOf(id) + '"></span>' +
      KYC.escapeHtml(whatItIs(id)) +
      (here ? ", in " + KYC.escapeHtml(state.counties[here].name) : "") + "</p>";
    var status = STATUS[c[6]];
    if (status) {
      body += '<p class="gov-officer-note">The Census Bureau records ' + KYC.escapeHtml(c[3]) + " as " +
        KYC.escapeHtml(status) + " (2025).</p>";
    }
    if (row) {
      body += '<h3 class="local-group">Its government</h3><ul class="local-list">' + item(row, "") + "</ul>" +
        '<p class="faint">As the Census Bureau listed it in 2022' +
        (filed !== here ? ", under " + KYC.escapeHtml(state.counties[filed].name) : "") +
        ", with its own website where the Bureau has one.</p>";
    } else if (!NOT_GOVERNING[c[6]]) {
      // Not joined is not "no government" (rule 19): the build found no
      // government in the listing it could tie to this place one to one.
      // Why is not guessed; the listing's date is a fact. A status that
      // explains the absence (inactive, nonfunctioning) says it instead.
      body += '<p class="gov-officer-note">The Census Bureau\'s 2022 listing of governments has no ' +
        "entry this site could tie to this place by its name alone, so none is shown here. The " +
        "listing is from 2022; a place incorporated since then is not in it.</p>";
    }
    var shared = (samePoint[c[0] + "," + c[1]] || []).filter(function (other) { return other !== id; });
    if (shared.length) {
      body += '<p class="faint">At the same point: ' + shared.map(function (other) {
        return '<button type="button" class="sidebar-link local-county-link" data-city="' +
          KYC.escapeAttr(other) + '">' + KYC.escapeHtml(cities[other][3] + " (" + whatItIs(other).toLowerCase() + ")") +
          " \u203a</button>";
      }).join(" ") + "</p>";
    }
    body += countyButton(filed);
    el("localPanelBody").innerHTML = body;
  }

  function showState() {
    var total = 0;
    Object.keys(state.governments).forEach(function (f) { total += counted(state.governments[f]); });
    var extra = state.unmatched.map(function (u) {
      return '<p class="leg-subhead">' + KYC.escapeHtml(u.name) + "</p>" +
        '<p class="faint">The Census listing files these under a county area that is not on the ' +
        "current county map.</p>" + groups(u.governments, "", u.fips);
    }).join("") + (state.statewide.length
      ? '<p class="leg-subhead">Statewide</p><p class="faint">Run by the state, with no county.</p>' +
        groups(state.statewide, "") : "");
    el("localPanelTitle").textContent = state.name;
    var townCount = Object.keys(towns).length;
    var lede = view === "cities"
      ? '<p class="local-total">' + plural(cityIds.length - townCount, "incorporated place") + " (2025)" +
        (townCount ? " and " + plural(townCount, "town or township government") : "") + ".</p>" +
        '<p class="faint">Every city, town, village and borough, at a point inside it' +
        (townCount ? ", and every town or township that governs, as a ring" : "") +
        ". Pick one on the map, or from the list below, to see its government.</p>"
      : '<p class="local-total">' + total.toLocaleString("en-US") + " local governments in " +
        Object.keys(state.counties).length + " counties (2022).</p>" +
        '<p class="faint">Pick a county on the map, or from the list below, to see every ' +
        "government in it.</p>";
    el("localPanelBody").innerHTML = lede + extra;
  }

  /* ---------------------------------------------------------------- roster */

  function countyRoster() {
    var ids = Object.keys(state.counties).sort(function (a, b) {
      return state.counties[a].name.localeCompare(state.counties[b].name);
    });
    return ids.map(function (fips) {
      var n = counted(state.governments[fips] || []);
      return '<button type="button" class="leg-row" data-region="' + KYC.escapeAttr(fips) + '">' +
        '<span class="leg-row-district">' + KYC.escapeHtml(state.counties[fips].name) + "</span>" +
        '<span class="leg-row-people">' + plural(n, "local government") + "</span></button>";
    }).join("");
  }

  /* Minnesota has 2,630 cities, towns and townships. Drawing every row at
   * once cost 370 ms on a phone slowed 4x (rule 45), so the list shows the
   * first LIST_LIMIT that match, a button for the rest, and the filter
   * always searches them all. */
  var LIST_LIMIT = 200;
  var listAll = false;

  function cityRows(filter) {
    var q = KYC.foldText ? KYC.foldText(filter || "") : (filter || "").toLowerCase();
    var shown = cityIds.filter(function (id) {
      if (!q) return true;
      var text = cities[id][3] + " " + ((state.counties[cities[id][4]] || {}).name || "");
      return (KYC.foldText ? KYC.foldText(text) : text.toLowerCase()).indexOf(q) !== -1;
    });
    if (!shown.length) return '<p class="faint">Nothing matches.</p>';
    var cut = !listAll && shown.length > LIST_LIMIT ? shown.slice(0, LIST_LIMIT) : shown;
    return cut.map(function (id) {
      var c = cities[id];
      var county = (state.counties[c[4]] || {}).name || "";
      return '<button type="button" class="leg-row" data-city="' + KYC.escapeAttr(id) + '">' +
        '<span class="leg-row-district"><span class="swatch dot-swatch dot-' + formOf(id) + '"></span>' +
        KYC.escapeHtml(c[3]) + "</span>" +
        '<span class="leg-row-people">' + KYC.escapeHtml([c[2] ? kindText(c[2]) : "", county]
          .filter(Boolean).join(" · ")) + "</span></button>";
    }).join("") + (cut.length < shown.length
      ? '<button type="button" class="leg-row local-more" data-more="1">' +
        '<span class="leg-row-district">Show all ' + shown.length.toLocaleString("en-US") + "</span>" +
        '<span class="leg-row-people">The first ' + cut.length + " are listed; the filter above " +
        "searches them all.</span></button>"
      : "");
  }

  function roster() {
    listAll = false;
    if (view === "cities") {
      el("localRosterTitle").textContent = "Every city and town";
      el("localRoster").innerHTML =
        '<label class="sr-only" for="cityFilter">Filter the cities and towns</label>' +
        '<input type="search" id="cityFilter" class="local-filter" placeholder="Filter by name or county" autocomplete="off">' +
        '<div id="cityRows" class="leg-roster">' + cityRows("") + "</div>";
      el("cityFilter").addEventListener("input", function () {
        listAll = false;                 // a new filter starts from the first 200 again
        el("cityRows").innerHTML = cityRows(el("cityFilter").value);
      });
    } else {
      el("localRosterTitle").textContent = "Every county";
      el("localRoster").innerHTML = countyRoster();
    }
  }

  function legend() {
    var countyKey = el("countyLegend");
    var cityKey = el("cityLegend");
    if (countyKey) countyKey.hidden = view === "cities";
    if (!cityKey) return;
    cityKey.hidden = view !== "cities";
    var present = {};
    cityIds.forEach(function (id) { present[formOf(id)] = true; });
    cityKey.innerHTML = '<span class="party-legend-title">Cities and towns, by legal form</span>' +
      FORMS.filter(function (f) { return present[f[0]]; }).map(function (f) {
        return '<span class="key"><span class="swatch dot-swatch dot-' + f[0] + '"></span>' +
          KYC.escapeHtml(f[1]) + "</span>";
      }).join("");
  }

  /* ----------------------------------------------------------------- picks */

  /* Marks the picks on the map: in place within a view, a full draw when
   * the view has changed since the map was last drawn. */
  var drawnView = "";
  function draw(region, dot) {
    if (!map) return;
    map.select(region, dot, drawnView !== view);
    drawnView = view;
  }

  function narrow() {
    return global.matchMedia && global.matchMedia("(max-width: 1000px)").matches;
  }

  function write() {
    KYC.router.writeFilters({ view: view === "cities" ? "cities" : "", county: picked, city: pickedCity });
  }

  function pick(fips, opts) {
    picked = state.counties[fips] ? fips : "";
    pickedCity = "";
    draw(picked, "");
    if (picked) showCounty(picked); else showState();
    if (picked && !(opts && opts.fromRoute) && narrow()) {
      reveal(el("localPanelTitle"));
    }
    if (!(opts && opts.fromRoute)) write();
  }

  function pickCity(id, opts) {
    if (!cities[id]) return;
    if (view !== "cities") setView("cities", { quiet: true });
    pickedCity = id;
    picked = "";
    draw("", id);
    showCity(id);
    if (!(opts && opts.fromRoute) && narrow()) {
      reveal(el("localPanelTitle"));
    }
    if (!(opts && opts.fromRoute)) write();
  }

  function setView(next, opts) {
    view = next === "cities" && cityIds.length ? "cities" : "counties";
    Array.prototype.forEach.call(doc.querySelectorAll(".segmented [data-view]"), function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-view") === view));
    });
    legend();
    roster();
    // Quiet: the caller picks next, and that draws the map.
    if (opts && opts.quiet) return;
    if (view === "counties") pickedCity = "";
    draw(picked, pickedCity);
    if (pickedCity) showCity(pickedCity); else if (picked) showCounty(picked); else showState();
    if (!(opts && opts.fromRoute)) write();
  }

  /* One address change, one draw (rule 45): when a pick follows a change
   * of view, the view is switched quietly and the pick draws. */
  function follow(params) {
    var city = params.city && cities[params.city] ? params.city : "";
    // A place in the address is a place on the cities map, view or not.
    var wantedView = city || params.view === "cities" ? "cities" : "counties";
    var picks = city ? city !== pickedCity : (params.county || "") !== picked || !!pickedCity;
    if (wantedView !== view) setView(wantedView, { fromRoute: true, quiet: picks });
    if (city) {
      if (city !== pickedCity) pickCity(city, { fromRoute: true });
    } else if (picks) {
      pick(params.county || "", { fromRoute: true });
    }
  }

  /* The panel is brought into view on a phone after the frame that draws
   * the map: scrolled inside the click, it forced the new map's layout
   * there (194 ms of a 450 ms pin on Minnesota at 6x). */
  function reveal(node) {
    (global.requestAnimationFrame || global.setTimeout)(function () {
      node.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  KYC.ready(function () {
    if (!state) {
      el("localMap").innerHTML = '<p class="results-bar">This state\'s county map did not load.</p>';
      return;
    }
    var segmented = doc.querySelector(".segmented");
    if (segmented) {
      // Hawaii has no incorporated places: its counties are its only
      // general-purpose local governments.
      segmented.hidden = !cityIds.length;
      segmented.addEventListener("click", function (event) {
        var b = event.target.closest("[data-view]");
        if (b) setView(b.getAttribute("data-view"));
      });
    }
    map = KYC.regionmap.create(el("localMap"), {
      title: state.name + " counties",
      viewBox: state.viewBox,
      regions: state.counties,
      insets: state.insets,
      outline: state.outline,
      look: look,
      dots: cityDots,
      onSelect: function (fips) { pick(fips); },
      onDot: function (id) { pickCity(id); },
    });
    var params = KYC.router.read().params;
    view = params.view === "cities" && cityIds.length ? "cities" : "counties";
    Array.prototype.forEach.call(doc.querySelectorAll(".segmented [data-view]"), function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-view") === view));
    });
    legend();
    roster();
    // The pick draws the map: once on load (rule 45).
    if (params.city && cities[params.city]) pickCity(params.city, { fromRoute: true });
    else pick(params.county || "", { fromRoute: true });

    el("localRoster").addEventListener("click", function (event) {
      if (event.target.closest("[data-more]")) {
        listAll = true;
        el("cityRows").innerHTML = cityRows(el("cityFilter").value);
        // Keyboard focus to the first row it showed, not back to the top.
        var shown = el("cityRows").querySelectorAll("[data-city]");
        if (shown[LIST_LIMIT]) shown[LIST_LIMIT].focus();
        return;
      }
      var row = event.target.closest("[data-region],[data-city]");
      if (!row) return;
      if (row.hasAttribute("data-city")) pickCity(row.getAttribute("data-city"));
      else pick(row.getAttribute("data-region"));
      el("localMap").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    el("localPanelBody").addEventListener("click", function (event) {
      var city = event.target.closest("[data-city]");
      if (city) {
        pickCity(city.getAttribute("data-city"));
        if (narrow()) el("localMap").scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      var county = event.target.closest("[data-county]");
      if (county) {
        setView("counties", { quiet: true });
        pick(county.getAttribute("data-county"));
      }
    });
    KYC.router.onChange(function () { follow(KYC.router.read().params); });
  });
})(window);
