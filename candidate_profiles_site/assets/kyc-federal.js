/* Know Your Candidate - the federal government's pages.
 *
 * federal/index.html (data-federal="hub"): the President and Vice President,
 * the Cabinet, the Supreme Court, and every federal court with a search of
 * every sitting judge. courts/<id>.html (data-federal="court"): one court's
 * judges. Both are drawn from data/federal.js, and a court page from its own
 * data/judiciary/<id>.js; the pages themselves carry no names (rule 34).
 * Each person opens in the shared dialog (kyc-official.js).
 *
 * What a page says is what a source states: a judge's appointing President,
 * never a party; who sits, never how many seats are empty, since the
 * directory lists judges, not judgeships.
 */
(function (global) {
  "use strict";

  var KYC = global.KYC;
  var doc = global.document;
  var SEARCH_LIMIT = 25;

  function data() {
    return global.kycFederal || null;
  }

  function el(id) {
    return doc.getElementById(id);
  }

  function esc(text) {
    return KYC.escapeHtml(text == null ? "" : String(text));
  }

  function person(id, name) {
    return '<button type="button" class="guide-person" data-official="' + KYC.escapeAttr(id) +
      '"><span class="name">' + esc(name) + "</span></button>";
  }

  function cell(label, html) {
    return '<td data-label="' + KYC.escapeAttr(label) + '">' + html + "</td>";
  }

  function table(caption, heads, rows) {
    return '<div class="guide-table-wrap"><table class="guide-table fed-table">' +
      (caption ? "<caption>" + caption + "</caption>" : "") +
      "<thead><tr>" + heads.map(function (h) { return '<th scope="col">' + esc(h) + "</th>"; }).join("") +
      "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>";
  }

  function section(id, title, body) {
    return '<section class="fed-section" id="' + KYC.escapeAttr(id) + '">' +
      '<h2 class="guide-subheading">' + esc(title) + "</h2>" + body + "</section>";
  }

  function source(url, text) {
    return '<a href="' + KYC.escapeAttr(url) + '" target="_blank" rel="noopener noreferrer">' +
      esc(text) + "</a>";
  }

  /* ------------------------------------------------------------- courts */

  function courtsById() {
    var out = {};
    ((data() || {}).courts || []).forEach(function (c) { out[c.id] = c; });
    return out;
  }

  function shortName(court) {
    return String(court.name)
      .replace(/^U\.S\. Court of Appeals for the /, "")
      .replace(/^U\.S\. District Court for the /, "");
  }

  function courtLink(court, prefix) {
    return '<a href="' + KYC.escapeAttr(prefix + court.id + ".html") + '">' +
      esc(shortName(court)) + "</a>";
  }

  function counts(court) {
    return court.listed ? court.active + " active, " + court.senior + " senior" : "";
  }

  /** A judge named on the hub opens on their court's page, which loads
   *  their record; the hub loads only the courts' index. */
  function judgeLink(court, judge, prefix) {
    return '<a href="' + KYC.escapeAttr(prefix + court.id + ".html#/official/" +
      encodeURIComponent(judge.id)) + '">' + esc(judge.name) + "</a>";
  }

  function chiefCell(c, prefix) {
    if (c.chief) return judgeLink(c, c.chief, prefix);
    return '<span class="faint">' + (!c.listed ? "Not in the directory"
      : c.chiefUnsettled ? "The directory’s record of its chief is contradictory"
      : "None named") + "</span>";
  }

  function courtRows(courts, prefix) {
    return courts.map(function (c) {
      return "<tr><th scope=\"row\">" + courtLink(c, prefix) + "</th>" +
        cell("Chief judge", chiefCell(c, prefix)) +
        cell("Judges", c.listed ? esc(counts(c)) :
          '<span class="faint">Not in the directory</span>') +
        cell("Vacancies", vacancyCount(c)) + "</tr>";
    });
  }

  /** "2, 1 with a nominee", from the courts' own list. */
  function vacancyCount(c) {
    if (!c.vacancies) return '<span class="faint">None listed</span>';
    return esc(c.vacancies + (c.nominees ? ", " + c.nominees + " with a nominee" : ""));
  }

  var COURT_HEADS = ["Court", "Chief judge", "Judges", "Vacancies"];

  /* -------------------------------------------------------- vacancies */

  var REASONS = {
    Senior: "Took senior status", Deceased: "Died", Retired: "Retired",
    Resigned: "Resigned", Elevated: "Appointed to another court",
  };

  function personText(p) {
    return p ? esc(p.name) : '<span class="faint">None yet</span>';
  }

  /** A court's vacancies, now and announced, as the courts list them. */
  function vacancySection(d, mine) {
    var v = d.vacancies || {};
    var now = mine.vacancies || [];
    var later = mine.future || [];
    var src = source((v.sources || {}).current, "the courts’ list of vacancies");
    var body = '<p class="guide-lede">From ' + src + ", as of " + esc(v.asOf) + ".";
    if (!now.length && !later.length) {
      return section("vacancies", "Vacancies", body + " It lists no vacancy on this court, " +
        "and none announced.</p>");
    }
    body += " The two sources are kept apart: a judge the list says has taken senior status " +
      "can still be among the active judges above until the directory records it.</p>";
    if (now.length) {
      body += table("", ["Seat vacated by", "Why", "Vacant since", "Nominee", "Nominated"],
        now.map(function (r) {
          return "<tr><th scope=\"row\">" + personText(r.vacatedBy) +
            (r.emergency ? ' <span class="badge badge-warn" title="Designated a judicial ' +
              'emergency by the courts">Judicial emergency</span>' : "") + "</th>" +
            cell("Why", esc(REASONS[r.reason] || r.reason || "")) +
            cell("Vacant since", esc(r.since || "")) +
            cell("Nominee", personText(r.nominee)) +
            cell("Nominated", esc(r.nominated || "")) + "</tr>";
        }));
    }
    if (later.length) {
      body += '<h3 class="panel-subhead">Announced</h3>' +
        table("", ["Judge leaving", "Why", "Announced", "Leaves", "Nominee", "Nominated"],
          later.map(function (r) {
            return "<tr><th scope=\"row\">" + personText(r.vacatedBy) + "</th>" +
              cell("Why", esc(REASONS[r.reason] || r.reason || "")) +
              cell("Announced", esc(r.announced || "")) +
              cell("Leaves", r.vacancyDate ? esc(r.vacancyDate) : '<span class="faint">Not yet set</span>') +
              cell("Nominee", personText(r.nominee)) +
              cell("Nominated", esc(r.nominated || "")) + "</tr>";
          }));
    }
    return section("vacancies", "Vacancies", body);
  }

  /* ---------------------------------------------------------------- hub */

  /** The President or Vice President. Their term is said once, above
   *  both, when they share it; a card says its own only when they differ (a
   *  Vice President who took office mid-term). */
  function leaderCard(p, shared) {
    return '<li class="fed-card fed-leader">' + portrait(p) +
      '<div><p class="fed-office">' + esc(p.office) + "</p>" +
      '<p class="fed-name">' + person(p.id, p.name) + "</p>" +
      '<p class="faint">' + esc(p.party) +
      (shared ? "" : "; since " + esc(p.since) + ", term ends " + esc(p.until)) +
      "</p></div></li>";
  }

  function sameTerm(a, b) {
    return !!a && !!b && a.since === b.since && a.until === b.until;
  }

  function senateCell(holder) {
    var s = holder && holder.senate;
    if (holder && holder.senateUnread) {
      return '<span class="faint">The Senate’s votes could not be read when last checked</span>';
    }
    if (!s) return '<span class="faint">No confirming roll call found</span>';
    return '<a href="' + KYC.escapeAttr(s.url) + '" target="_blank" rel="noopener noreferrer">' +
      esc(s.yeas + "–" + s.nays) + "</a>, " + esc(s.date) +
      (s.yeas === s.nays ? ", the Vice President breaking the tie" : "");
  }

  function pageCell(holder) {
    var page = (holder && holder.page) || {};
    if (page.status === "confirmed") {
      return '<a href="' + KYC.escapeAttr(page.url) + '" target="_blank" rel="noopener noreferrer">' +
        "Named there</a>" + (page.acting ? " (acting)" : "");
    }
    if (page.status === "unconfirmed") return '<span class="faint">Not named there when last read</span>';
    if (page.status === "unreadable") return '<span class="faint">Could not be read</span>';
    return '<span class="faint">No page names the head</span>';
  }

  function portrait(person) {
    return KYC.official.pictureTag(person, 72, "fed-photo");
  }

  /** Since when the holder has held the office, and whom they followed
   *  this term - each date only where the sources agree. */
  function tenureLine(office) {
    var rows = office.history || [];
    var now = rows.filter(function (r) { return r.current; })[0];
    var before = now ? rows.slice(0, rows.indexOf(now)) : [];
    var start = now && now.start && now.start.shown ? KYC.official.whenText(now.start.shown) : "";
    var prev = before[before.length - 1];
    if (!start && !prev) return "";
    // "After" only when the dates show one handing over to the other on the
    // same day: an acting officer the record lacks may have served between.
    var handover = prev && prev.end && prev.end.shown && now.start && now.start.shown &&
      prev.end.shown.precision === "day" && now.start.shown.precision === "day" &&
      prev.end.shown.date === now.start.shown.date;
    return '<p class="fed-fact"><span class="fed-fact-label">In office</span> ' +
      (start ? "Since " + esc(start) : "") +
      (prev ? (start ? "; " : "") + (handover ? "after " : "previously this term: ") +
        esc(prev.name) + (prev.acting ? " (acting)" : "") : "") +
      "</p>";
  }

  /** Every change since the term began, newest first: who was confirmed,
   *  who left, who served as acting - each date where the sources agree. */
  function changeEvents(d) {
    var events = [];
    d.offices.forEach(function (office) {
      (office.history || []).forEach(function (row) {
        if (row.confirmed) {
          events.push({ sort: row.confirmed.date, when: row.confirmed.date, office: office,
            kind: "confirmed", row: row,
            text: row.name + " confirmed by the Senate, " + row.confirmed.yeas + "\u2013" +
              row.confirmed.nays + (row.confirmed.yeas === row.confirmed.nays
                ? ", the Vice President breaking the tie" : ""), url: row.confirmed.url });
        }
        if (row.acting && row.start && row.start.shown) {
          events.push({ sort: row.start.shown.date, when: KYC.official.whenText(row.start.shown),
            office: office, kind: "acting", row: row, text: row.name + " became acting" });
        } else if (row.actingNote && row.actingStart) {
          // Acting before being confirmed, as the person's own article puts it.
          events.push({ sort: row.actingStart.date, when: KYC.official.whenText(row.actingStart),
            office: office, kind: "acting", row: row,
            text: row.name + " became acting (their Wikipedia article: \u201c" + row.actingNote + "\u201d)" });
        }
        if (row.end) {
          var shown = row.end.shown;
          events.push({ sort: shown ? shown.date : row.end.sort || "", when: shown
            ? KYC.official.whenText(shown)
            : row.end.differs ? "Date differs between sources" : "Date not in both sources",
            office: office, kind: "left", row: row,
            text: row.acting ? row.name + "’s service as acting ended"
              : row.name + " left the office" });
        }
      });
    });
    return events.sort(function (a, b) { return a.sort < b.sort ? 1 : a.sort > b.sort ? -1 : 0; });
  }

  var CHANGE_BADGES = { confirmed: ["badge-neutral", "Confirmed"], left: ["badge-warn", "Left"],
    acting: ["badge-neutral", "Acting"] };

  function changeRow(e) {
    var badge = CHANGE_BADGES[e.kind];
    return "<tr><th scope=\"row\">" + esc(e.when) + "</th>" +
      cell("Office", esc(e.office.office)) +
      cell("What happened", '<span class="badge ' + badge[0] + '">' + badge[1] + "</span> " +
        (e.url ? '<a href="' + KYC.escapeAttr(e.url) + '" target="_blank" rel="noopener noreferrer">' +
          esc(e.text) + "</a>" : esc(e.text))) + "</tr>";
  }

  function changesSection(d) {
    var events = changeEvents(d);
    if (!events.length) return "";
    var recent = events.slice(0, 12);
    var earlier = events.slice(12);
    var heads = ["When", "Office", "What happened"];
    var meta = d.changes || {};
    return section("changes", "Changes since the term began",
      '<p class="guide-lede">Who was confirmed, who left and who served as acting in each ' +
      "office since " + esc(meta.since || "") + ", newest first. Confirmations are the " +
      "Senate’s roll calls; who held each office comes from Wikidata, and a date is shown only " +
      "to the day, month or year on which Wikidata and the person’s Wikipedia article agree" +
      (meta.read ? ", as read " + esc(meta.read) : "") + ". An acting officer Wikidata does not " +
      "record is not listed.</p>" +
      table("", heads, recent.map(changeRow)) +
      (earlier.length ? '<details class="fed-earlier"><summary>' + earlier.length +
        " earlier changes</summary>" + table("", heads, earlier.map(changeRow)) + "</details>" : ""));
  }

  /** One Cabinet office as a card: its holder's portrait and name, the
   *  Senate's vote and the office's own page. An office the White House
   *  lists with nobody in it says so. */
  function officeCard(office) {
    var h = office.holder;
    if (!h) {
      return '<li class="fed-card fed-officer"><div><p class="fed-office">' + esc(office.office) +
        '</p><p class="faint">Nobody listed by the White House</p></div></li>';
    }
    return '<li class="fed-card fed-officer">' + portrait(h) +
      '<div><p class="fed-office">' + esc(office.office) + "</p>" +
      '<p class="fed-name">' + person(h.id, h.name) +
      ((h.page || {}).acting ? ' <span class="badge badge-warn">Acting</span>' : "") + "</p>" +
      (h.title && h.title !== office.office ? '<p class="faint">' + esc(h.title) + "</p>" : "") +
      tenureLine(office) +
      '<p class="fed-fact"><span class="fed-fact-label">Senate vote</span> ' + senateCell(h) + "</p>" +
      '<p class="fed-fact"><span class="fed-fact-label">The office’s page</span> ' + pageCell(h) +
      "</p></div></li>";
  }

  /** A justice as a card: the Court's own portrait, role, appointment. */
  function justiceCard(j) {
    var seat = (j.seats || [])[0] || {};
    return '<li class="fed-card fed-justice">' + portrait(j) +
      '<div><p class="fed-office">' + esc(j.justice ? j.justice.role : seat.title) + "</p>" +
      '<p class="fed-name">' + person(j.id, j.name) + "</p>" +
      '<p class="fed-fact"><span class="fed-fact-label">Appointed by</span> ' +
        esc(seat.appointedBy) + "</p>" +
      '<p class="fed-fact"><span class="fed-fact-label">' + (j.justice ? "Took the oath" : "Commissioned") +
        "</span> " + esc((j.justice && j.justice.oath) || seat.commissioned) + "</p></div></li>";
  }

  function justiceRows(justices) {
    return justices.map(function (j) {
      var seat = (j.seats || [])[0] || {};
      return "<tr><th scope=\"row\">" + person(j.id, j.name) + "</th>" +
        cell("Role", esc(j.justice ? j.justice.role : seat.title)) +
        cell("Appointed by", esc(seat.appointedBy)) +
        cell("Since", esc((j.justice && j.justice.oath) || seat.commissioned)) + "</tr>";
    });
  }

  function renderHub(d) {
    var asOf = d.asOf || {};
    var shared = sameTerm(d.president, d.vicePresident);
    var html = section("executive", "The President and Vice President",
      (shared ? '<p class="fed-term" id="executiveTerm">The term: <strong>' +
        esc(d.president.since) + "</strong> to <strong>" + esc(d.president.until) +
        "</strong></p>" : "") +
      '<ul class="fed-cards fed-leaders">' + leaderCard(d.president, shared) +
        leaderCard(d.vicePresident, shared) + "</ul>" +
      '<p class="faint">Terms from ' + source(d.sources.executive.executive,
        "congress-legislators’ record of executive terms") + ", as of " + esc(asOf.executive) + ".</p>");

    var departments = d.offices.filter(function (o) { return o.kind === "department"; })
      .sort(function (a, b) { return a.order - b.order; });
    var others = d.offices.filter(function (o) { return o.kind !== "department"; });
    html += section("cabinet", "The Cabinet",
      '<p class="guide-lede">Who the White House lists in the ' +
      source(d.sources.executive.cabinet, "President’s Cabinet") + ", each checked on " +
      "the office’s own page and against the Senate’s roll-call votes, as of " +
      esc(asOf.executive) + ". A Cabinet officer is shown without a party.</p>" +
      '<h3 class="fed-subhead">The heads of the fifteen executive departments, in the order ' +
        '<span class="cite">3 U.S.C. 19(d)(1)</span> lists them</h3>' +
      '<ul class="fed-cards">' + departments.map(officeCard).join("") + "</ul>" +
      (others.length ? '<h3 class="fed-subhead">Other officers the White House lists with ' +
        'the Cabinet</h3><ul class="fed-cards">' + others.map(officeCard).join("") + "</ul>" : ""));

    html += changesSection(d);

    var scotus = d.supremeCourt || {};
    html += section("supreme-court", "The Supreme Court",
      '<p class="guide-lede">Its members as ' + source(d.sources.judiciary.supremeCourt,
        "the Court lists them") + ", with each justice’s appointment from the Federal " +
      "Judicial Center’s directory, as of " + esc(asOf.judiciary) + ". " +
      '<a href="../courts/scotus.html">The Court’s page</a>.' +
      ((scotus.members || []).some(function (j) { return j.portrait; })
        ? " Portraits: " + source((scotus.members.filter(function (j) { return j.portrait; })[0]
            .portrait || {}).source, "Collection of the Supreme Court of the United States") + "."
        : "") + "</p>" +
      '<ul class="fed-cards">' + (scotus.members || []).map(justiceCard).join("") + "</ul>" +
      ((scotus.retired || []).length
        ? table("Retired justices, listed apart: they are not members of the Court",
          ["Justice", "Role", "Appointed by", "Since"], justiceRows(scotus.retired)) : ""));

    var courts = d.courts.filter(function (c) { return c.kind !== "supreme"; });
    var appeals = courts.filter(function (c) { return c.kind === "appeals"; });
    var body = circuitMapMarkup() + '<div class="fed-search">' +
      '<label class="field-label" for="judgeSearch">Find a federal judge</label>' +
      '<input id="judgeSearch" class="search-input" type="search" autocomplete="off" ' +
      'placeholder="A judge’s name" aria-describedby="judgeSearchCount">' +
      '<p class="faint" id="judgeSearchCount" role="status"></p>' +
      '<ul class="fed-results" id="judgeResults"></ul></div>' +
      '<p class="guide-lede">Every sitting judge of each court whose judges are appointed under ' +
      "Article III, from the " +
      source(d.sources.judiciary.directory, "Federal Judicial Center’s Biographical Directory") +
      " as of " + esc(asOf.judiciary) + ", and the three territorial district courts. The " +
      "Court of Federal Claims, the Tax Court, and bankruptcy and magistrate judges are not " +
      "in it.</p>" + vacancySummary(d) +
      "<h3 class=\"panel-subhead\">Courts of appeals</h3>" +
      table("", COURT_HEADS, courtRows(appeals, "../courts/"));
    appeals.forEach(function (circuit) {
      var districts = courts.filter(function (c) {
        return c.kind !== "appeals" && c.kind !== "trade" && c.circuit === circuit.circuit;
      });
      if (!districts.length) return;
      body += '<h3 class="panel-subhead">District courts of the ' + esc(shortName(circuit)) + "</h3>" +
        table("", COURT_HEADS, courtRows(districts, "../courts/"));
    });
    var trade = courts.filter(function (c) { return c.kind === "trade"; });
    if (trade.length) {
      body += '<h3 class="panel-subhead">Court of International Trade</h3>' +
        table("", COURT_HEADS, courtRows(trade, "../courts/"));
    }
    html += section("courts", "The Article III courts", body);
    el("federalBody").innerHTML = html;
    initSearch();
    initCircuitMap(d);
  }

  function vacancySummary(d) {
    var v = d.vacancies;
    if (!v) return "";
    return '<p class="guide-lede" id="vacancySummary">' + source(v.sources.current,
      "The courts list") + " " + esc(v.totals.vacancies) + " vacancies, " +
      esc(v.totals.nominees) + " with a nominee pending, as of " + esc(v.asOf) + "; " +
      esc(v.emergencies) + " of them designated judicial emergencies, and " +
      source(v.sources.future, v.future + " more announced") + ".</p>";
  }

  /* ------------------------------------------------------- circuit map */

  /* The states by the court of appeals that hears their federal appeals,
   * drawn by the shared map (kyc-usmap.js) in the guide's colours - one
   * table of circuits (kyc/federal_courts.circuits) and one colouring, so
   * the two maps cannot disagree. Picking a state lists its courts. */
  function circuitMapMarkup() {
    if (!KYC.usmap || !global.kycGeo) return "";
    return '<div class="fed-circuits">' +
      '<h3 class="panel-subhead">Which court of appeals hears each state’s appeals</h3>' +
      '<div class="map-legend" id="circuitLegend"></div>' +
      '<div class="map-stage fed-circuit-stage" id="circuitStage">' +
      '<svg id="circuitMap" viewBox="0 0 975 652" preserveAspectRatio="xMidYMid meet" ' +
      'role="group" aria-label="Map of the states and territories by federal judicial circuit. ' +
      'Each state is a button that lists its federal courts."></svg></div>' +
      '<div class="fed-circuit-panel" id="circuitPanel" aria-live="polite">' +
      '<p class="faint">Pick a state for its district courts and its court of appeals.</p></div>' +
      "</div>";
  }

  function tokenFill(token) {
    return token ? "var(--" + token + ")" : "var(--surface-2)";
  }

  function tokenInk(token) {
    return !token || token === "cat-4" ? "var(--text)" : "";
  }

  /** The address's parameters, with *key* set: the search and the map share
   *  the address and neither may wipe the other's. */
  function setParam(key, value) {
    var route = KYC.router.read();
    var params = route.view === "list" ? route.params : {};
    params[key] = value;
    KYC.router.writeFilters(params);
  }

  function initCircuitMap(d) {
    if (!KYC.usmap || !global.kycGeo || !el("circuitMap")) return;
    var circuitOf = {};
    var courtsOf = {};
    d.courts.forEach(function (c) {
      (c.states || []).forEach(function (code) {
        if (c.kind === "appeals") circuitOf[code] = c;
        else if (c.kind === "district" || c.kind === "territorial") {
          (courtsOf[code] = courtsOf[code] || []).push(c);
        }
      });
    });
    var map = KYC.usmap.create({
      svg: "circuitMap", stage: "circuitStage", layer: "circuitLabels",
      look: function (code) {
        var c = circuitOf[code];
        return c
          ? { fill: tokenFill(c.token), ink: tokenInk(c.token), text: map.name(code) + ": " + shortName(c) }
          : { fill: tokenFill(null), ink: "var(--text)",
              text: map.name(code) + ": no federal district court, in no circuit" };
      },
      label: function (code) {
        var c = circuitOf[code];
        return c ? c.circuit : "\u2013";
      },
      onSelect: function (code) { pick(code, true); },
    });

    function pick(code, typed) {
      if (!map.hasShape(code)) return;
      map.setSelected(code);
      if (typed) setParam("circuitState", code);
      var c = circuitOf[code];
      var mine = courtsOf[code] || [];
      el("circuitPanel").innerHTML = '<h4 class="fed-circuit-state">' + esc(map.name(code)) + "</h4>" +
        (c ? '<p class="fed-fact"><span class="fed-fact-label">Court of appeals</span> ' +
          courtLink(c, "../courts/") + "</p>" : "") +
        (mine.length ? '<p class="fed-fact"><span class="fed-fact-label">' +
          (mine.length > 1 ? "District courts" : "District court") + "</span> " +
          mine.map(function (m) { return courtLink(m, "../courts/"); }).join(", ") + "</p>"
          : '<p class="faint">No federal district court: its courts are territorial, and it is in ' +
            "no circuit.</p>");
    }

    var seen = {};
    var legend = d.courts.filter(function (c) { return c.kind === "appeals" && c.token; })
      .map(function (c) {
        if (seen[c.circuit]) return "";
        seen[c.circuit] = true;
        return '<span class="key"><span class="swatch swatch-label" style="background:' +
          tokenFill(c.token) + (tokenInk(c.token) ? ";color:" + tokenInk(c.token) : "") + '">' +
          esc(c.circuit) + "</span>" + esc(shortName(c)) + "</span>";
      }).join("");
    var federal = d.courts.filter(function (c) { return c.id === "cafc"; })[0];
    el("circuitLegend").innerHTML = legend + '<span class="key"><span class="swatch swatch-label" ' +
      'style="background:' + tokenFill(null) + ';color:var(--text)">\u2013</span>In no circuit</span>' +
      (federal ? '<span class="key">' + courtLink(federal, "../courts/") + " hears certain cases " +
        "from every state</span>" : "");
    map.start();
    map.paint();
    var wanted = KYC.router.read().params.circuitState;
    if (wanted) pick(String(wanted).toUpperCase(), false);
  }

  /* ------------------------------------------------------------- search */

  function initSearch() {
    var input = el("judgeSearch");
    var index = global.kycJudgesIndex || [];
    var courts = courtsById();
    if (!input) return;
    var folded = index.map(function (row) { return KYC.foldText(row[1]); });

    function run(typed) {
      var words = KYC.foldText(input.value).split(/\s+/).filter(Boolean);
      var list = el("judgeResults");
      var status = el("judgeSearchCount");
      // Only what the reader types goes in the address: on load it may be
      // a shared #/official/ link, which this must not overwrite.
      if (typed) setParam("q", input.value.trim());
      if (!words.length) {
        list.innerHTML = "";
        status.textContent = index.length.toLocaleString("en-US") + " sitting Article III judges";
        return;
      }
      var hits = [];
      for (var i = 0; i < index.length; i += 1) {
        if (words.every(function (w) { return folded[i].indexOf(w) !== -1; })) hits.push(index[i]);
      }
      status.textContent = hits.length === 0 ? "No Article III judge by that name in the directory" :
        hits.length + (hits.length === 1 ? " judge" : " judges") +
        (hits.length > SEARCH_LIMIT ? ", the first " + SEARCH_LIMIT + " shown" : "");
      list.innerHTML = hits.slice(0, SEARCH_LIMIT).map(function (row) {
        var names = row[2].map(function (cid) { return (courts[cid] || { name: cid }).name; });
        return '<li><a href="' + KYC.escapeAttr("../courts/" + row[2][0] + ".html#/official/" +
          encodeURIComponent(row[0])) + '">' + esc(row[1]) + "</a> " +
          '<span class="faint">' + esc(names.join("; ")) + (row[3] === "senior" ? ", senior status" : "") +
          "</span></li>";
      }).join("");
    }

    input.value = KYC.router.read().params.q || "";
    input.addEventListener("input", function () { run(true); });
    run(false);
  }

  /* -------------------------------------------------------------- court */

  function courtId() {
    return el("federalContent").getAttribute("data-court");
  }

  function judgeRows(judges, senior) {
    return judges.map(function (j) {
      var seat = (j.seats || []).filter(function (s) {
        return s.court === courtId();
      })[0] || (j.seats || [])[0] || {};
      return "<tr><th scope=\"row\">" + person(j.id, j.name) +
        (seat.chiefSince ? ' <span class="badge badge-neutral">Chief</span>' : "") + "</th>" +
        cell("Title", esc((j.justice && j.justice.role) || seat.title)) +
        cell("Appointed by", esc(seat.appointedBy)) +
        cell("Commissioned", esc(seat.commissioned)) +
        (senior ? cell("Senior status since", esc(seat.seniorSince)) : "") + "</tr>";
    });
  }

  function renderCourt(d) {
    var id = courtId();
    var courts = courtsById();
    var court = courts[id];
    var mine = (global.kycCourt || {})[id];
    var target = el("federalBody");
    if (!court || !mine) {
      target.innerHTML = '<p class="results-bar" role="status">This court’s data did not ' +
        "load. Run: python build_profile_site.py</p>";
      return;
    }
    var asOf = (d.asOf || {}).judiciary;
    if (!mine.listed) {
      target.innerHTML = '<p class="results-bar" role="status">This court’s judges serve ' +
        "under Article IV of the Constitution, and the Federal Judicial Center’s directory, " +
        "which these pages are built from, lists Article III judges only. They are not listed " +
        "here: that is not a vacancy.</p>" + vacancySection(d, mine) + related(court, courts);
      return;
    }
    var active = mine.judges.filter(function (j) { return j.status !== "senior"; });
    var senior = mine.judges.filter(function (j) { return j.status === "senior"; });
    var html = '<p class="guide-lede">' + esc(id === "scotus" ? active.length + " justices"
      : counts(court) + " judges") + ", from the " +
      source(d.sources.judiciary.directory, "Federal Judicial Center’s Biographical Directory") +
      " as of " + esc(asOf) + (id === "scotus" ? "; its members as " +
        source(d.sources.judiciary.supremeCourt, "the Court lists them") : "") +
      ".</p>";
    // A chief the directory also lists on senior status: nobody is shown as
    // chief, and the page says why (kyc/judiciary.py).
    var unsettled = court.chiefUnsettled && mine.judges.filter(function (j) {
      return (j.seats || []).some(function (s) { return s.court === id && s.chiefUnsettled; });
    })[0];
    if (unsettled) {
      html += '<p class="state-note" id="chiefUnsettled">The directory lists ' + esc(unsettled.name) +
        " as this court’s chief judge and also on senior status. A chief judge must be in " +
        "regular active service (28 U.S.C. 136(a)), so nobody is shown as chief until the " +
        "record is settled.</p>";
    }
    var heads = ["Judge", "Title", "Appointed by", "Commissioned"];
    html += section("active", id === "scotus" ? "The justices" : "Active judges",
      active.length ? table("", heads, judgeRows(active, false))
        : '<p class="faint">Nobody listed by the directory</p>');
    if (senior.length) {
      html += section("senior", "Judges on senior status",
        '<p class="guide-lede">A judge on senior status keeps the office and may hear a ' +
        "reduced caseload; taking it opens a seat the President may fill (28 U.S.C. 371).</p>" +
        table("", heads.concat(["Senior status since"]), judgeRows(senior, true)));
    }
    if ((mine.retired || []).length) {
      html += section("retired", "Retired justices",
        '<p class="guide-lede">Listed apart: they are not members of the Court.</p>' +
        table("", heads, judgeRows(mine.retired, false)));
    }
    target.innerHTML = html + vacancySection(d, mine) + related(court, courts);
  }

  /** The courts above and below this one. */
  function related(court, courts) {
    var list = [];
    if (court.kind === "district" || court.kind === "territorial") {
      var circuit = Object.keys(courts).map(function (k) { return courts[k]; }).filter(function (c) {
        return c.kind === "appeals" && c.circuit === court.circuit;
      })[0];
      if (circuit) list.push("Appeals go to the " + courtLink(circuit, ""));
    }
    if (court.kind === "appeals") {
      var below = Object.keys(courts).map(function (k) { return courts[k]; }).filter(function (c) {
        return (c.kind === "district" || c.kind === "territorial") && c.circuit === court.circuit;
      });
      if (below.length) {
        list.push("Its district courts: " + below.map(function (c) { return courtLink(c, ""); }).join(", "));
      }
    }
    return list.length ? '<p class="fed-related">' + list.join(". ") + ".</p>" : "";
  }

  /* --------------------------------------------------------------- start */

  KYC.ready(function () {
    var root = el("federalContent");
    if (!root) return;
    var d = data();
    if (!d) {
      el("federalBody").innerHTML = '<p class="results-bar" role="status">The federal data ' +
        "did not load. Run: python build_profile_site.py</p>";
      return;
    }
    if (root.getAttribute("data-federal") === "court") renderCourt(d); else renderHub(d);
    // A portrait that will not load is dropped, never shown broken.
    root.addEventListener("error", function (event) {
      if (event.target.classList && event.target.classList.contains("fed-photo")) {
        event.target.remove();
      }
    }, true);
    KYC.official.ensure();
    KYC.router.onChange(KYC.official.applyRoute);
    KYC.official.applyRoute();
  });
})(window);
