/* Know Your Candidate - one state's legislature on a map.
 *
 * The lines and the people both come from window.kycLegislature, built by
 * kyc/legislature.py: Census district boundaries, and the sitting legislators
 * Open States lists for them, matched by district name in the pipeline. The
 * map is drawn by the shared region map (kyc-regionmap.js).
 *
 * A district Open States lists nobody for is "nobody listed", never
 * "vacant": the record may be behind a special election (rule 19). People
 * the pipeline could not place on a district - New Hampshire's floterial
 * seats, Maine's tribal representatives - are listed, never dropped.
 *
 * The address carries the chamber and the picked district:
 * #/?chamber=lower&d=101.
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;
  var code = doc.body.getAttribute("data-state") || "";
  var state = (global.kycLegislature || {})[code] || null;

  var chamber = "";
  var picked = "";
  var map = null;

  function el(id) { return doc.getElementById(id); }

  function current() { return state.chambers[chamber]; }

  function partyClass(people) {
    if (!people || !people.length) return "party-none";
    var keys = {};
    people.forEach(function (p) { keys[p.partyKey] = true; });
    var list = Object.keys(keys);
    if (list.length > 1) return "party-split";
    return { D: "party-d", R: "party-r", I: "party-i", N: "party-none" }[list[0]] || "party-none";
  }

  function districtName(id) {
    var d = current().districts[id];
    return d ? d.name : id;
  }

  function look(id) {
    var people = current().members[id] || [];
    var who = people.length ? people.map(function (p) {
      return p.name + " (" + p.party + ")";
    }).join(", ") : "nobody listed";
    return { cls: "district-shape " + partyClass(people),
             title: current().title + " district " + districtName(id) + ": " + who };
  }

  /* ---------------------------------------------------------------- people */

  function personCard(p) {
    var links = (p.links || []).map(function (url) {
      return '<a href="' + KYC.escapeAttr(url) + '" target="_blank" rel="noopener noreferrer">' +
        KYC.escapeHtml(url.replace(/^https?:\/\//, "").replace(/\/$/, "")) + "</a>";
    });
    var contact = [];
    if (p.phone) contact.push('<a href="tel:' + KYC.escapeAttr(p.phone.replace(/[^\d+]/g, "")) + '">' +
      KYC.escapeHtml(p.phone) + "</a>");
    if (p.email) contact.push('<a href="mailto:' + KYC.escapeAttr(p.email) + '">' +
      KYC.escapeHtml(p.email) + "</a>");
    return '<article class="leg-person">' +
      (p.image ? '<img class="leg-photo" src="' + KYC.escapeAttr(p.image) +
        '" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">' : "") +
      '<div class="leg-who"><p class="leg-name">' + KYC.escapeHtml(p.name) + "</p>" +
      '<p class="leg-party ' + KYC.escapeAttr("party-" + ({ D: "d", R: "r", I: "i" }[p.partyKey] || "vacant")) +
      '">' + KYC.escapeHtml(p.party) + "</p>" +
      (p.tribalSeat ? '<p class="faint">Non-voting representative of the ' +
        KYC.escapeHtml(p.district) + "</p>" : "") +
      (contact.length ? '<p class="leg-contact">' + contact.join(" · ") + "</p>" : "") +
      (links.length ? '<p class="leg-links">' + links.join(" · ") + "</p>" : "") +
      "</div></article>";
  }

  function showDistrict(id) {
    var people = current().members[id] || [];
    el("legPanelTitle").textContent = current().title + " district " + districtName(id);
    el("legPanelBody").innerHTML = people.length
      ? people.map(personCard).join("")
      : '<p class="faint">Open States lists nobody for this seat. It may be vacant, or the record ' +
        "may be behind a special election.</p>";
  }

  function partyCounts(list) {
    var counts = {};
    list.forEach(function (p) { counts[p.party] = (counts[p.party] || 0) + 1; });
    return Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; })
      .map(function (k) { return counts[k] + " " + k; }).join(", ");
  }

  function showSummary() {
    var c = current();
    var everyone = [];
    Object.keys(c.members).forEach(function (id) { everyone = everyone.concat(c.members[id]); });
    var missing = c.seats - c.listed;
    var unplaced = state.unplaced.filter(function (p) { return p.chamber === chamber; });
    el("legPanelTitle").textContent = state.name + " " + c.title;
    el("legPanelBody").innerHTML =
      "<p>" + KYC.escapeHtml(c.seats + " seats" + (everyone.length ? ": " + partyCounts(everyone) : "")) + ".</p>" +
      (missing > 0 ? '<p class="faint">Open States lists nobody for ' + missing +
        (missing === 1 ? " seat" : " seats") + ". They may be vacant, or the record may be behind a special election.</p>" : "") +
      (unplaced.length ? '<p class="leg-subhead">Not on the map</p>' +
        '<p class="faint">These members hold seats the district map cannot draw: a district that ' +
        "overlays others, or a seat elected by a tribal nation rather than a district.</p>" +
        unplaced.map(personCard).join("") : "") +
      '<p class="faint">Pick a district on the map, or one below.</p>';
  }

  function roster() {
    var c = current();
    var ids = Object.keys(c.districts).sort(function (a, b) {
      return c.districts[a].name.localeCompare(c.districts[b].name, "en", { numeric: true });
    });
    el("legRoster").innerHTML = ids.map(function (id) {
      var people = c.members[id] || [];
      return '<button type="button" class="leg-row" data-region="' + KYC.escapeAttr(id) + '">' +
        '<span class="leg-row-district">' + KYC.escapeHtml(c.districts[id].name) + "</span>" +
        '<span class="leg-row-people">' + (people.length ? people.map(function (p) {
          return '<span class="' + ({ D: "party-d", R: "party-r", I: "party-i" }[p.partyKey] || "") + '">' +
            KYC.escapeHtml(p.name) + "</span>";
        }).join(", ") : '<span class="faint">Nobody listed</span>') + "</span></button>";
    }).join("");
  }

  /* ------------------------------------------------------------------- map */

  function draw() {
    var c = current();
    map = KYC.regionmap.create(el("legMap"), {
      title: state.name + " " + c.title + " districts",
      viewBox: state.viewBox,
      regions: c.districts,
      insets: c.insets,
      outline: state.counties.outline,
      mesh: state.counties.mesh,
      look: look,
      onSelect: function (id) { pick(id); },
    });
    map.setSelected(picked);
  }

  function pick(id, opts) {
    picked = current().districts[id] ? id : "";
    if (map) map.setSelected(picked);
    if (picked) showDistrict(picked); else showSummary();
    // On a phone the panel follows the map and its close-ups down the page:
    // after a tap, bring the answer into view.
    if (picked && !(opts && opts.fromRoute) && global.matchMedia &&
        global.matchMedia("(max-width: 1000px)").matches) {
      el("legPanelTitle").scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (!(opts && opts.fromRoute)) {
      KYC.router.writeFilters({ chamber: chamber === "upper" ? "" : chamber, d: picked });
    }
  }

  function setChamber(next, opts) {
    if (!state.chambers[next]) return;
    chamber = next;
    Array.prototype.forEach.call(doc.querySelectorAll(".segmented [data-chamber]"), function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-chamber") === chamber));
    });
    picked = "";
    draw();
    roster();
    showSummary();
    if (!(opts && opts.fromRoute)) KYC.router.writeFilters({ chamber: chamber === "upper" ? "" : chamber });
  }

  KYC.ready(function () {
    if (!state) {
      el("legMap").innerHTML = '<p class="results-bar">This state\'s legislature map did not load.</p>';
      return;
    }
    var route = KYC.router.read().params;
    setChamber(state.chambers[route.chamber] ? route.chamber : "upper", { fromRoute: true });
    if (route.d) pick(route.d, { fromRoute: true });

    var segmented = doc.querySelector(".segmented");
    if (segmented) {
      segmented.addEventListener("click", function (event) {
        var b = event.target.closest("[data-chamber]");
        if (b) setChamber(b.getAttribute("data-chamber"));
      });
    }
    // A portrait that does not load steps aside rather than showing a
    // broken image: one listener for every portrait (rule 13).
    doc.addEventListener("error", function (event) {
      var img = event.target;
      if (img && img.classList && img.classList.contains("leg-photo")) img.remove();
    }, true);
    el("legRoster").addEventListener("click", function (event) {
      var row = event.target.closest("[data-region]");
      if (row) {
        pick(row.getAttribute("data-region"));
        el("legMap").scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
    KYC.router.onChange(function () {
      var params = KYC.router.read().params;
      var wanted = state.chambers[params.chamber] ? params.chamber : "upper";
      if (wanted !== chamber) setChamber(wanted, { fromRoute: true });
      if ((params.d || "") !== picked) pick(params.d || "", { fromRoute: true });
    });
  });
})(window);
