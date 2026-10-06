/* Know Your Candidate - a state's counties, and every local government in
 * each: county governments, cities and towns, townships, school districts,
 * special districts, and the school systems a state, county or city runs.
 *
 * Everything comes from window.kycLocal, built by kyc/counties.py from the
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
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;
  var code = doc.body.getAttribute("data-state") || "";
  var state = (global.kycLocal || {})[code] || null;
  var picked = "";
  var pickedCity = "";
  var view = "counties";
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

  function el(id) { return doc.getElementById(id); }

  function counted(rows) {
    return rows.filter(function (r) { return r[0] !== "dependent"; }).length;
  }

  function shade(n) {
    var step = 1;
    EDGES.forEach(function (edge) { if (n >= edge) step += 1; });
    return "scale-" + step;
  }

  function look(fips) {
    if (view === "cities") {
      return { cls: "district-shape region-muted", title: state.counties[fips].name };
    }
    var rows = state.governments[fips] || [];
    var n = counted(rows);
    return { cls: "district-shape region-" + shade(n),
             title: state.counties[fips].name + ": " + n + " local government" + (n === 1 ? "" : "s") };
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

  function item(row) {
    var name = row[3]
      ? '<a href="' + KYC.escapeAttr(row[3]) + '" target="_blank" rel="noopener noreferrer">' +
        KYC.escapeHtml(row[1]) + "</a>"
      : KYC.escapeHtml(row[1]);
    var bits = [row[5], row[2], size(row), row[6] === "inactive" ? "listed as inactive" : ""]
      .filter(Boolean).map(KYC.escapeHtml);
    return '<li class="local-item"><span class="local-name">' + name + "</span>" +
      (bits.length ? '<span class="local-meta">' + bits.join(" · ") + "</span>" : "") + "</li>";
  }

  function groups(rows, filter) {
    var q = KYC.foldText ? KYC.foldText(filter || "") : (filter || "").toLowerCase();
    var html = "";
    ORDER.forEach(function (kind) {
      var mine = rows.filter(function (r) {
        if (r[0] !== kind) return false;
        if (!q) return true;
        var text = r[1] + " " + r[5] + " " + r[2];
        return (KYC.foldText ? KYC.foldText(text) : text.toLowerCase()).indexOf(q) !== -1;
      });
      if (!mine.length) return;
      html += '<h3 class="local-group">' + KYC.escapeHtml(KINDS[kind]) +
        ' <span class="faint">' + mine.length + "</span></h3>" +
        '<ul class="local-list">' + mine.map(item).join("") + "</ul>";
    });
    return html || '<p class="faint">Nothing matches.</p>';
  }

  function showCounty(fips) {
    var rows = state.governments[fips] || [];
    var county = state.counties[fips];
    var n = counted(rows);
    el("localPanelTitle").textContent = county.name;
    el("localPanelBody").innerHTML =
      '<p class="local-total">' + n + " local government" + (n === 1 ? "" : "s") +
      " in 2022</p>" +
      '<label class="sr-only" for="localFilter">Filter this county\'s governments</label>' +
      '<input type="search" id="localFilter" class="local-filter" placeholder="Filter by name, kind or city" autocomplete="off">' +
      '<div id="localGroups">' + groups(rows, "") + "</div>";
    el("localFilter").addEventListener("input", function () {
      el("localGroups").innerHTML = groups(rows, el("localFilter").value);
    });
  }

  function showState() {
    var total = 0;
    Object.keys(state.governments).forEach(function (f) { total += counted(state.governments[f]); });
    var extra = state.unmatched.map(function (u) {
      return '<p class="leg-subhead">' + KYC.escapeHtml(u.name) + "</p>" +
        '<p class="faint">The Census listing files these under a county area that is not on the ' +
        "current county map.</p>" + groups(u.governments, "");
    }).join("") + (state.statewide.length
      ? '<p class="leg-subhead">Statewide</p><p class="faint">Run by the state, with no county.</p>' +
        groups(state.statewide, "") : "");
    el("localPanelTitle").textContent = state.name;
    el("localPanelBody").innerHTML =
      '<p class="local-total">' + total.toLocaleString("en-US") + " local governments in " +
      Object.keys(state.counties).length + " counties (2022).</p>" +
      '<p class="faint">Pick a county on the map, or from the list below, to see every ' +
      "government in it.</p>" + extra;
  }

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

  function countyRoster() {
    var ids = Object.keys(state.counties).sort(function (a, b) {
      return state.counties[a].name.localeCompare(state.counties[b].name);
    });
    el("localRosterTitle").textContent = "Every county";
    el("localRosterFilterWrap").hidden = true;
    el("localRoster").innerHTML = ids.map(function (fips) {
      var n = counted(state.governments[fips] || []);
      return '<button type="button" class="leg-row" data-region="' + KYC.escapeAttr(fips) + '">' +
        '<span class="leg-row-district">' + KYC.escapeHtml(state.counties[fips].name) + "</span>" +
        '<span class="leg-row-people">' + n + " local government" + (n === 1 ? "" : "s") + "</span></button>";
    }).join("");
  }

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
    return global.matchMedia && global.matchMedia("(max-width: 1000px)").matches;
  }

  function write() {
    KYC.router.writeFilters(view === "cities"
      ? { view: "cities", city: pickedCity, county: "" }
      : { view: "", city: "", county: picked });
  }

  function pick(fips, opts) {
    picked = state.counties[fips] ? fips : "";
    if (map) map.setSelected(picked);
    if (picked) showCounty(picked); else showState();
    if (picked && !(opts && opts.fromRoute) && onPhone()) {
      el("localPanelTitle").scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (!(opts && opts.fromRoute)) write();
  }

  function pickCity(id, opts) {
    pickedCity = cities()[id] ? id : "";
    if (map) map.setSelectedDot(pickedCity);
    if (pickedCity) showCity(pickedCity); else showCities();
    if (pickedCity && !(opts && opts.fromRoute) && onPhone()) {
      el("localPanelTitle").scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (!(opts && opts.fromRoute)) write();
  }

  function setView(next, opts) {
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
  }

  KYC.ready(function () {
    if (!state) {
      el("localMap").innerHTML = '<p class="results-bar">This state\'s county map did not load.</p>';
      return;
    }
    map = KYC.regionmap.create(el("localMap"), {
      title: state.name + " counties",
      viewBox: state.viewBox,
      regions: state.counties,
      insets: state.insets,
      outline: state.outline,
      look: look,
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
  });
})(window);
