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
 * Every figure here is the pipeline's: the chamber's count is the state
 * page's (stategov.chamber), its parties are counted by party, never by
 * fusion line, who runs it is the state page's word (stategov.COALITIONS),
 * and which seats are on the November ballot is the state's own record
 * (kyc/ballot2026.py), read into districts in kyc/legislature.seats_up.
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

  var PARTY = { D: "Democratic", R: "Republican" };
  var PARTY_CLASS = { D: "party-d", R: "party-r", I: "party-i", N: "party-n" };

  function el(id) { return doc.getElementById(id); }

  function current() { return state.chambers[chamber]; }

  function link(href, text) {
    return '<a href="' + KYC.escapeAttr(href) + '" target="_blank" rel="noopener noreferrer">' +
      KYC.escapeHtml(text) + "</a>";
  }

  function andList(list) {
    return list.length < 2 ? list.join("")
      : list.slice(0, -1).join(", ") + " and " + list[list.length - 1];
  }

  function partyClass(people) {
    if (!people || !people.length) return "party-none";
    var keys = {};
    people.forEach(function (p) { keys[p.partyKey] = true; });
    var list = Object.keys(keys);
    if (list.length > 1) return "party-split";
    return PARTY_CLASS[list[0]] || "party-none";
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

  /* The legend names only what this chamber's map draws: Nebraska's is one
   * nonpartisan neutral, and a seat with nobody listed is its own entry,
   * never folded in with "nonpartisan" (audit 2026-10-17, STATEGOV-06). */
  function legend() {
    var c = current();
    var drawn = {};
    Object.keys(c.districts).forEach(function (id) {
      drawn[partyClass(c.members[id]).replace("party-", "")] = true;
    });
    Array.prototype.forEach.call(doc.querySelectorAll(".party-legend [data-key]"), function (key) {
      key.hidden = !drawn[key.getAttribute("data-key")];
    });
  }

  /* ---------------------------------------------------------------- people */

  function tel(number, label) {
    return KYC.escapeHtml(label) + ': <a href="tel:' + KYC.escapeAttr(number.replace(/[^\d+]/g, "")) +
      '">' + KYC.escapeHtml(number) + "</a>";
  }

  function host(url) {
    return url.replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0];
  }

  /** Where an unplaced member sits, in words: the district the map cannot
   *  draw, by its name (audit 2026-10-17, STATEGOV-17). */
  function seatLine(p) {
    if (p.tribalSeat) {
      return '<p class="faint">Non-voting representative of the ' + KYC.escapeHtml(p.district) + "</p>";
    }
    if (p.why === "floterial") {
      return '<p class="faint">Floterial district ' + KYC.escapeHtml(p.district) +
        ": it overlays several of the districts on the map</p>";
    }
    if (p.why) {
      return '<p class="faint">District ' + KYC.escapeHtml(p.district) + ", which the map does not draw</p>";
    }
    return "";
  }

  function personCard(p) {
    var contact = [];
    if (p.phone) contact.push(tel(p.phone, "Capitol office"));
    if (p.districtPhone) contact.push(tel(p.districtPhone, "District office"));
    if (p.email) contact.push('<a href="mailto:' + KYC.escapeAttr(p.email) + '">' +
      KYC.escapeHtml(p.email) + "</a>");
    return '<article class="leg-person">' +
      // The smaller copy this site made of a heavy portrait, or the
      // portrait itself (rule 101: KYC.photoAttrs).
      (p.image ? '<img class="leg-photo" ' + KYC.photoAttrs(p.image, p.photoCopy) +
        ' alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">' : "") +
      '<div class="leg-who"><p class="leg-name">' + KYC.escapeHtml(p.name) + "</p>" +
      '<p class="leg-party ' + KYC.escapeAttr("party-" + ({ D: "d", R: "r", I: "i" }[p.partyKey] || "vacant")) +
      '">' + KYC.escapeHtml(p.party) + "</p>" +
      // A fusion ballot's other lines, apart from the party (STATEGOV-21).
      (p.lines && p.lines.length ? '<p class="leg-lines">Also on the ' +
        KYC.escapeHtml(andList(p.lines)) + (p.lines.length === 1 ? " line" : " lines") + "</p>" : "") +
      seatLine(p) +
      (contact.length ? '<p class="leg-contact">' + contact.join(" · ") + "</p>" : "") +
      (p.address ? '<p class="leg-contact">Capitol office: ' + KYC.escapeHtml(p.address) + "</p>" : "") +
      // One page, never the dump of every page Open States read (LINKS-04,
      // STATEGOV-16), labelled as what it is (pageLink).
      pageLink(p) +
      // Whose photograph it is, where the legislature's own record gave it
      // (rule 87: kyc/legphotos.py).
      (p.image && p.imageCredit ? '<p class="leg-credit">' +
        KYC.photoCreditHtml(KYC.copyCredit(p.imageCredit, p.image, p.photoCopy)) + "</p>" : "") +
      "</div></article>";
  }

  /** The member's one page, called what it is (kyc/legislature.py
   *  member_page): their page on the legislature's site, the legislature's
   *  list of their bills (Connecticut links no other), their page on a
   *  party caucus's site (every Michigan legislator's only page), the
   *  chamber's member list, or a past session's page - never all of them
   *  "Official page". A member with none says so. */
  function pageLink(p) {
    if (!p.page) {
      return '<p class="leg-page faint">Open States links no page for this member on the ' +
        "legislature's site.</p>";
    }
    var text = p.pageKind === "bills" ? "Bills on the legislature's site"
      : p.pageKind === "caucus" ? "Party caucus page" + (p.pageCaucus ? ": " + p.pageCaucus : "")
      : p.pageKind === "list" ? "On the " + current().title + " member list"
      : p.pageSession ? "Page on the legislature's site, " + p.pageSession + " session"
      : "Official page";
    return '<p class="leg-page">' + link(p.page, text) +
      ' <span class="faint">' + KYC.escapeHtml(host(p.page)) + "</span></p>";
  }

  /* -------------------------------------------------------- 2026 ballot */

  /* Whether a chamber's seats, and one district's, are on the November 3
   * ballot: the words are KYC.ballot's, which the Your ballot page says
   * too (kyc-ballot.js, rule 12). */
  function chamberBallot(c) { return KYC.ballot.chamberBallot(c); }

  function districtBallot(id) { return KYC.ballot.seatBallot(current(), id); }

  function showDistrict(id) {
    var people = current().members[id] || [];
    el("legPanelTitle").textContent = current().title + " district " + districtName(id);
    el("legPanelBody").innerHTML = (people.length
      ? people.map(personCard).join("")
      : '<p class="faint">Open States lists nobody for this seat. It may be vacant, or the record ' +
        "may be behind a special election.</p>") + districtBallot(id);
  }

  /* -------------------------------------------------------------- summary */

  function partyCounts(c) {
    // Nebraska's senators carry no party: "49 nonpartisan", not a party name.
    return c.parties.map(function (p) {
      return p[2] + " " + (p[1] === "N" ? "nonpartisan" : p[0]);
    }).join(", ");
  }

  /** Who runs the chamber, in the state page's words. */
  function holds(c) {
    var n = c.count;
    var text = code === "NE" ? "Elected without party labels"
      : n.majority ? PARTY[n.majority] + " majority of the seats"
      : "No party holds a majority of the seats";
    return '<p class="leg-holds">' + KYC.escapeHtml(text) +
      (n.ncsl ? ' <span class="badge badge-warn">NCSL: ' +
        KYC.escapeHtml(n.ncsl === "none" ? "no majority" : PARTY[n.ncsl] + " majority") + "</span>" : "") +
      "</p>";
  }

  function showSummary() {
    var c = current();
    var missing = c.seats - c.listed;
    var unplaced = state.unplaced.filter(function (p) { return p.chamber === chamber; });
    el("legPanelTitle").textContent = state.name + " " + c.title;
    // A member the map cannot draw (New Hampshire's floterial seats) still
    // holds a seat and counts in the chamber's parties, as the state page
    // counts them; a non-voting tribal representative holds none of its
    // seats and counts in neither (kyc/statelegs.py).
    el("legPanelBody").innerHTML =
      "<p>" + KYC.escapeHtml(c.seats + " seats" + (c.parties.length ? ": " + partyCounts(c) : "")) +
        (missing > 0 ? KYC.escapeHtml("; " + missing + " with nobody listed") : "") + ".</p>" +
      holds(c) +
      // The coalition note, where the majority of seats does not run the
      // chamber (rule 54, STATEGOV-05).
      (state.note ? '<p class="gov-note">' + KYC.escapeHtml(state.note) + " " +
        link(state.noteSource, "Legislature's roster") + "</p>" : "") +
      (missing > 0 ? '<p class="faint">Open States lists nobody for ' + missing +
        (missing === 1 ? " seat" : " seats") + ". They may be vacant, or the record may be behind a special election.</p>" : "") +
      chamberBallot(c) +
      (state.sources.peopleDate ? '<p class="faint">Members as Open States listed them on ' +
        KYC.escapeHtml(state.sources.peopleDate) + ".</p>" : "") +
      (unplaced.length ? '<p class="leg-subhead">Not on the map</p>' +
        '<p class="faint">These members hold seats the district map cannot draw: a district that ' +
        "overlays others, or a seat elected by a tribal nation rather than a district.</p>" +
        unplaced.map(personCard).join("") : "") +
      '<p class="faint">Pick a district on the map, or one below.</p>';
  }

  /** The chamber as one square per seat, above its map (STATEGOV-23). */
  function seats() {
    var c = current();
    el("legSeats").innerHTML = KYC.seatStrip(c.count) + KYC.seatKey([c.count]);
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
      el("legPanelTitle").scrollIntoView({ behavior: KYC.scrollBehavior(), block: "start" });
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
    // Each part on its own: one that fails leaves the rest drawn (rule 76).
    [seats, legend, draw, roster, showSummary].forEach(function (step) {
      try { step(); } catch (err) {
        if (global.console) global.console.error(err);
      }
    });
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
      if (!img || !img.classList || !img.classList.contains("leg-photo")) return;
      var card = img.closest(".leg-person");
      // A copy this site made that fails gives way to its original, and the
      // credit stops calling it a copy (rule 101).
      if (KYC.retryOriginal(img, event)) {
        var note = card && card.querySelector(".photo-copy-note");
        if (note) note.remove();
        return;
      }
      // Its credit goes with it: a card never credits a photograph it
      // does not show (rule 87).
      var credit = card && card.querySelector(".leg-credit");
      if (credit) credit.remove();
      img.remove();
    }, true);
    el("legRoster").addEventListener("click", function (event) {
      var row = event.target.closest("[data-region]");
      if (row) {
        pick(row.getAttribute("data-region"));
        el("legMap").scrollIntoView({ behavior: KYC.scrollBehavior(), block: "start" });
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
