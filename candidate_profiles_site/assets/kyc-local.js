/* Know Your Candidate - a state's counties, and every local government in
 * each: county governments, cities and towns, townships, school districts,
 * special districts, and the school systems a state, county or city runs.
 *
 * Everything comes from window.kycLocal, built by kyc/counties.py from the
<<<<<<< HEAD
 * Census Bureau's county boundaries, its 2022 Government Units listing and
 * its 2025 place boundaries, joined on the county's Census code. The map is
 * the shared region map (kyc-regionmap.js).
 *
 * Two views. Counties: shaded by how many local governments each has; pick
 * one to see every government in it. Cities and towns: every incorporated
 * place a dot in its county; pick one to see its own government.
 *
 * The address carries the view and the pick: #/?county=48201, or
 * #/?view=cities&city=4835000.
=======
 * Census Bureau's county and place boundaries and its 2022 Government Units
 * listing. Governments are joined to counties on the county's Census code,
 * and a city or town to its government only where the build found the join
 * one to one. The map is the shared region map (kyc-regionmap.js), in two
 * views:
 *   - Counties: each county shaded by how many local governments it has;
 *   - Cities and towns: every incorporated place a dot, coloured by the
 *     legal form the Census names (city, town, village, borough).
 *
 * The address carries the view and the pick:
 * #/?county=48201, #/?view=cities&city=4835000.
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
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
<<<<<<< HEAD
  var view = "counties";
=======
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
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

  // [x, y, kind, name, county, ref]; ref is [county code, row] or null.
  var cities = (state && state.cities) || {};
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

  /* The legal form as a reader should see it. The Census calls the part of
   * a consolidated government outside its other places its "balance". */
  function kindText(kind) {
    if (kind === "balance") return "consolidated government (the part outside its other places)";
    return kind;
  }

  function governmentRow(ref) {
    if (!ref) return null;
    var rows = state.governments[ref[0]];
    if (!rows) {
      var area = state.unmatched.filter(function (u) { return u.fips === ref[0]; })[0];
      rows = area ? area.governments : null;
    }
    return rows ? rows[ref[1]] || null : null;
  }

  function cityDots() {
    if (view !== "cities") return [];
    return cityIds.map(function (id) {
      var c = cities[id];
      return { id: id, at: [c[0], c[1]], cls: "dot-" + form(c[2]),
               title: c[3] + (c[2] ? " (" + kindText(c[2]) + ")" : "") };
    });
  }

  function look(fips) {
    if (view === "cities") {
      return { cls: "district-shape region-muted", title: state.counties[fips].name };
    }
    var rows = state.governments[fips] || [];
    var n = counted(rows);
    var title = state.counties[fips].name + ": " + plural(n, "local government");
    if (view === "cities") return { cls: "district-shape region-plain", title: title };
    return { cls: "district-shape region-" + shade(n), title: title };
  }

  /* ------------------------------------------------------------ cities */

  var CITY_KIND = { city: "City", town: "Town", village: "Village", borough: "Borough",
                    municipality: "Municipality", place: "Place" };

  function cities() { return state.cities || {}; }

  /* The government a city point is, from "fips:row", or null. */
  function governmentOf(ref) {
    if (!ref) return null;
    var parts = ref.split(":");
    return ((state.governments[parts[0]] || [])[+parts[1]]) || null;
  }

  function dots() {
    var all = cities();
    return Object.keys(all).map(function (id) {
      var c = all[id];
      return { id: id, at: [c[0], c[1]],
               cls: "dot-" + c[2] + (c[5] ? "" : " dot-unlisted"),
               title: c[3] + " (" + (CITY_KIND[c[2]] || c[2]).toLowerCase() + ")" };
    });
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
    var body = '<p class="local-total"><span class="swatch dot-swatch dot-' + form(c[2]) + '"></span>' +
      KYC.escapeHtml(c[2] ? "Incorporated " + kindText(c[2]) : "Incorporated place") +
      (c[4] && state.counties[c[4]] ? ", in " + KYC.escapeHtml(state.counties[c[4]].name) : "") + "</p>";
    if (row) {
      body += '<h3 class="local-group">Its government</h3><ul class="local-list">' + item(row, "") + "</ul>" +
        '<p class="faint">As the Census Bureau listed it in 2022, with its own website where the ' +
        "Bureau has one.</p>";
    } else {
      // Not joined is not "no government" (rule 19): the build found no
      // government in the listing it could tie to this place one to one.
      body += '<p class="gov-officer-note">The Census Bureau\'s 2022 listing of governments has no ' +
        "entry this site could tie to this place by its name alone, so none is shown here. A place " +
        "incorporated since 2022 is not in that listing yet.</p>";
    }
    body += countyButton(c[4]);
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
    var lede = view === "cities"
      ? '<p class="local-total">' + plural(cityIds.length, "incorporated place") + " (2025).</p>" +
        '<p class="faint">Every city, town, village and borough, at a point inside it. Pick one on the ' +
        "map, or from the list below, to see its government.</p>"
      : '<p class="local-total">' + total.toLocaleString("en-US") + " local governments in " +
        Object.keys(state.counties).length + " counties (2022).</p>" +
        '<p class="faint">Pick a county on the map, or from the list below, to see every ' +
        "government in it.</p>";
    el("localPanelBody").innerHTML = lede + extra;
  }

<<<<<<< HEAD
  function showCity(id) {
    var c = cities()[id];
    var gov = governmentOf(c[5]);
    var county = state.counties[c[4]];
    el("localPanelTitle").textContent = c[3];
    el("localPanelBody").innerHTML =
      '<p class="local-total">' + KYC.escapeHtml(CITY_KIND[c[2]] || c[2]) +
      (county ? " in " + KYC.escapeHtml(county.name) : "") + "</p>" +
      (gov
        ? '<ul class="local-list">' + item(gov) + "</ul>" +
          '<p class="faint">Its government, as the Census Bureau listed it in 2022.</p>'
        : '<p class="faint">No government in the Census listing matches this place by name, so ' +
          "none is shown here; the county's own list has every government in it.</p>") +
      (county ? '<p><button type="button" class="sidebar-link local-link" data-county="' +
        KYC.escapeAttr(c[4]) + '">Every government in ' + KYC.escapeHtml(county.name) + " \u203a</button></p>" : "");
  }

  function showCities() {
    var all = cities();
    var ids = Object.keys(all);
    var listed = ids.filter(function (id) { return all[id][5]; }).length;
    var unplaced = (state.unplacedCities || []).map(governmentOf).filter(Boolean);
    el("localPanelTitle").textContent = state.name + ": cities and towns";
    el("localPanelBody").innerHTML =
      '<p class="local-total">' + ids.length.toLocaleString("en-US") + " incorporated places; " +
      listed.toLocaleString("en-US") + " matched to their government.</p>" +
      '<p class="faint">Pick a dot on the map, or a name from the list below. A hollow dot is a ' +
      "place no government in the Census listing matches by name.</p>" +
      (unplaced.length
        ? '<p class="leg-subhead">Not on the map</p><p class="faint">Municipal governments in the ' +
          "Census listing that no place on the map matches by name:</p>" +
          '<ul class="local-list">' + unplaced.map(item).join("") + "</ul>"
        : "");
  }

  /* -------------------------------------------------------------- roster */
=======
  /* ---------------------------------------------------------------- roster */
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd

  function countyRoster() {
    var ids = Object.keys(state.counties).sort(function (a, b) {
      return state.counties[a].name.localeCompare(state.counties[b].name);
    });
<<<<<<< HEAD
    el("localRosterTitle").textContent = "Every county";
    el("localRosterFilterWrap").hidden = true;
    el("localRoster").innerHTML = ids.map(function (fips) {
=======
    return ids.map(function (fips) {
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
      var n = counted(state.governments[fips] || []);
      return '<button type="button" class="leg-row" data-region="' + KYC.escapeAttr(fips) + '">' +
        '<span class="leg-row-district">' + KYC.escapeHtml(state.counties[fips].name) + "</span>" +
        '<span class="leg-row-people">' + plural(n, "local government") + "</span></button>";
    }).join("");
  }

<<<<<<< HEAD
  function cityRoster(filter) {
    var all = cities();
    var q = KYC.foldText ? KYC.foldText(filter || "") : (filter || "").toLowerCase();
    var ids = Object.keys(all).filter(function (id) {
      var text = all[id][3];
      return !q || (KYC.foldText ? KYC.foldText(text) : text.toLowerCase()).indexOf(q) !== -1;
    }).sort(function (a, b) { return all[a][3].localeCompare(all[b][3]); });
    el("localRosterTitle").textContent = "Every city and town";
    el("localRosterFilterWrap").hidden = false;
    el("localRoster").innerHTML = ids.map(function (id) {
      var c = all[id];
      var county = state.counties[c[4]];
      return '<button type="button" class="leg-row" data-city="' + KYC.escapeAttr(id) + '">' +
        '<span class="leg-row-district">' + KYC.escapeHtml(c[3]) + "</span>" +
        '<span class="leg-row-people">' + KYC.escapeHtml(CITY_KIND[c[2]] || c[2]) +
        (county ? ", " + KYC.escapeHtml(county.name) : "") + "</span></button>";
    }).join("") || '<p class="faint">Nothing matches.</p>';
  }

  /* --------------------------------------------------------------- picks */

  function onPhone() {
=======
  function cityRows(filter) {
    var q = KYC.foldText ? KYC.foldText(filter || "") : (filter || "").toLowerCase();
    var shown = cityIds.filter(function (id) {
      if (!q) return true;
      var text = cities[id][3] + " " + ((state.counties[cities[id][4]] || {}).name || "");
      return (KYC.foldText ? KYC.foldText(text) : text.toLowerCase()).indexOf(q) !== -1;
    });
    if (!shown.length) return '<p class="faint">Nothing matches.</p>';
    return shown.map(function (id) {
      var c = cities[id];
      var county = (state.counties[c[4]] || {}).name || "";
      return '<button type="button" class="leg-row" data-city="' + KYC.escapeAttr(id) + '">' +
        '<span class="leg-row-district"><span class="swatch dot-swatch dot-' + form(c[2]) + '"></span>' +
        KYC.escapeHtml(c[3]) + "</span>" +
        '<span class="leg-row-people">' + KYC.escapeHtml([c[2] ? kindText(c[2]) : "", county]
          .filter(Boolean).join(" · ")) + "</span></button>";
    }).join("");
  }

  function roster() {
    if (view === "cities") {
      el("localRosterTitle").textContent = "Every city and town";
      el("localRoster").innerHTML =
        '<label class="sr-only" for="cityFilter">Filter the cities and towns</label>' +
        '<input type="search" id="cityFilter" class="local-filter" placeholder="Filter by name or county" autocomplete="off">' +
        '<div id="cityRows" class="leg-roster">' + cityRows("") + "</div>";
      el("cityFilter").addEventListener("input", function () {
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
    cityIds.forEach(function (id) { present[form(cities[id][2])] = true; });
    cityKey.innerHTML = '<span class="party-legend-title">Incorporated places, by legal form</span>' +
      FORMS.filter(function (f) { return present[f[0]]; }).map(function (f) {
        return '<span class="key"><span class="swatch dot-swatch dot-' + f[0] + '"></span>' +
          KYC.escapeHtml(f[1]) + "</span>";
      }).join("");
  }

  /* ----------------------------------------------------------------- picks */

  function narrow() {
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
    return global.matchMedia && global.matchMedia("(max-width: 1000px)").matches;
  }

  function write() {
<<<<<<< HEAD
    KYC.router.writeFilters(view === "cities"
      ? { view: "cities", city: pickedCity, county: "" }
      : { view: "", city: "", county: picked });
=======
    KYC.router.writeFilters({ view: view === "cities" ? "cities" : "", county: picked, city: pickedCity });
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
  }

  function pick(fips, opts) {
    picked = state.counties[fips] ? fips : "";
    pickedCity = "";
    if (map) map.select(picked, "");
    if (picked) showCounty(picked); else showState();
<<<<<<< HEAD
    if (picked && !(opts && opts.fromRoute) && onPhone()) {
=======
    if (picked && !(opts && opts.fromRoute) && narrow()) {
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
      el("localPanelTitle").scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (!(opts && opts.fromRoute)) write();
  }

  function pickCity(id, opts) {
<<<<<<< HEAD
    pickedCity = cities()[id] ? id : "";
    if (map) map.setSelectedDot(pickedCity);
    if (pickedCity) showCity(pickedCity); else showCities();
    if (pickedCity && !(opts && opts.fromRoute) && onPhone()) {
=======
    if (!cities[id]) return;
    if (view !== "cities") setView("cities", { quiet: true });
    pickedCity = id;
    picked = "";
    map.select("", id);
    showCity(id);
    if (!(opts && opts.fromRoute) && narrow()) {
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
      el("localPanelTitle").scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (!(opts && opts.fromRoute)) write();
  }

  function setView(next, opts) {
<<<<<<< HEAD
    view = next === "cities" ? "cities" : "counties";
    Array.prototype.forEach.call(doc.querySelectorAll("[data-view]"), function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-view") === view));
    });
    el("localLegendCounties").hidden = view !== "counties";
    el("localLegendCities").hidden = view !== "cities";
    map.setSelected(view === "counties" ? picked : "");
    map.setSelectedDot(view === "cities" ? pickedCity : "");
    if (view === "cities") {
      cityRoster(el("localRosterFilter").value);
      if (pickedCity) showCity(pickedCity); else showCities();
    } else {
      countyRoster();
      if (picked) showCounty(picked); else showState();
    }
    if (!(opts && opts.fromRoute)) write();
=======
    view = next === "cities" && cityIds.length ? "cities" : "counties";
    Array.prototype.forEach.call(doc.querySelectorAll(".segmented [data-view]"), function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-view") === view));
    });
    legend();
    roster();
    // Quiet: the caller picks next, and that draws the map.
    if (opts && opts.quiet) return;
    if (view === "counties") pickedCity = "";
    if (map) map.select(picked, pickedCity);
    if (pickedCity) showCity(pickedCity); else if (picked) showCounty(picked); else showState();
    if (!(opts && opts.fromRoute)) write();
  }

  function follow(params) {
    var wantedView = params.view === "cities" ? "cities" : "counties";
    if (wantedView !== view) setView(wantedView, { fromRoute: true });
    if (params.city && cities[params.city]) {
      if (params.city !== pickedCity) pickCity(params.city, { fromRoute: true });
    } else if ((params.county || "") !== picked || pickedCity) {
      pick(params.county || "", { fromRoute: true });
    }
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
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
<<<<<<< HEAD
      onSelect: function (fips) { if (view === "counties") pick(fips); },
      dots: function () { return view === "cities" ? dots() : []; },
      onDot: function (id) { pickCity(id); },
    });
    var route = KYC.router.read().params;
    picked = state.counties[route.county] ? route.county : "";
    pickedCity = cities()[route.city] ? route.city : "";
    map.render();
    setView(route.view, { fromRoute: true });

    el("localRoster").addEventListener("click", function (event) {
      var row = event.target.closest("[data-region]");
      var city = event.target.closest("[data-city]");
      if (row) pick(row.getAttribute("data-region"));
      if (city) pickCity(city.getAttribute("data-city"));
      if (row || city) el("localMap").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    el("localPanelBody").addEventListener("click", function (event) {
      var link = event.target.closest("[data-county]");
      if (!link) return;
      picked = link.getAttribute("data-county");
      setView("counties");
    });
    el("localRosterFilter").addEventListener("input", function () {
      if (view === "cities") cityRoster(el("localRosterFilter").value);
    });
    doc.querySelector(".local-views").addEventListener("click", function (event) {
      var button = event.target.closest("[data-view]");
      if (button) setView(button.getAttribute("data-view"));
    });
    KYC.router.onChange(function () {
      var params = KYC.router.read().params;
      var wantView = params.view === "cities" ? "cities" : "counties";
      if (wantView !== view) setView(wantView, { fromRoute: true });
      if (view === "cities" && (params.city || "") !== pickedCity) pickCity(params.city || "", { fromRoute: true });
      if (view === "counties" && (params.county || "") !== picked) pick(params.county || "", { fromRoute: true });
    });
=======
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
>>>>>>> e0dbc40abcac113b20d9ab1d67bd78b2a52667bd
  });
})(window);
