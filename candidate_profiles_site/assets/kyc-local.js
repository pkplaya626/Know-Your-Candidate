/* Know Your Candidate - a state's counties, and every local government in
 * each: county governments, cities and towns, townships, school districts,
 * special districts, and the school systems a state, county or city runs.
 *
 * Everything comes from window.kycLocal, built by kyc/counties.py from the
 * Census Bureau's county boundaries and its 2022 Government Units listing,
 * joined on the county's Census code. The map is the shared region map
 * (kyc-regionmap.js); counties are shaded by how many local governments
 * each has.
 *
 * The address carries the picked county: #/?county=48201.
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;
  var code = doc.body.getAttribute("data-state") || "";
  var state = (global.kycLocal || {})[code] || null;
  var picked = "";
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
    var rows = state.governments[fips] || [];
    var n = counted(rows);
    return { cls: "district-shape region-" + shade(n),
             title: state.counties[fips].name + ": " + n + " local government" + (n === 1 ? "" : "s") };
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

  function roster() {
    var ids = Object.keys(state.counties).sort(function (a, b) {
      return state.counties[a].name.localeCompare(state.counties[b].name);
    });
    el("localRoster").innerHTML = ids.map(function (fips) {
      var n = counted(state.governments[fips] || []);
      return '<button type="button" class="leg-row" data-region="' + KYC.escapeAttr(fips) + '">' +
        '<span class="leg-row-district">' + KYC.escapeHtml(state.counties[fips].name) + "</span>" +
        '<span class="leg-row-people">' + n + " local government" + (n === 1 ? "" : "s") + "</span></button>";
    }).join("");
  }

  function pick(fips, opts) {
    picked = state.counties[fips] ? fips : "";
    if (map) map.setSelected(picked);
    if (picked) showCounty(picked); else showState();
    if (picked && !(opts && opts.fromRoute) && global.matchMedia &&
        global.matchMedia("(max-width: 1000px)").matches) {
      el("localPanelTitle").scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (!(opts && opts.fromRoute)) KYC.router.writeFilters({ county: picked });
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
      onSelect: function (fips) { pick(fips); },
    });
    var route = KYC.router.read().params;
    map.render();
    roster();
    pick(route.county || "", { fromRoute: true });
    el("localRoster").addEventListener("click", function (event) {
      var row = event.target.closest("[data-region]");
      if (row) {
        pick(row.getAttribute("data-region"));
        el("localMap").scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
    KYC.router.onChange(function () {
      var wanted = KYC.router.read().params.county || "";
      if (wanted !== picked) pick(wanted, { fromRoute: true });
    });
  });
})(window);
