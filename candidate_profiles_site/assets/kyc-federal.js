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

  function leaderCard(p) {
    return '<li class="fed-leader">' +
      (p.photo ? '<img class="fed-photo" src="' + KYC.escapeAttr(p.photo) +
        '" alt="" width="72" height="90" loading="lazy" decoding="async">' : "") +
      '<div><p class="fed-office">' + esc(p.office) + "</p>" +
      '<p class="fed-name">' + person(p.id, p.name) + "</p>" +
      '<p class="faint">' + esc(p.party) + "; since " + esc(p.since) + ", term ends " +
      esc(p.until) + "</p></div></li>";
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

  function officeRow(office) {
    var h = office.holder;
    return "<tr><th scope=\"row\">" + esc(office.office) +
      '<br><span class="faint">' + esc(office.body) + "</span></th>" +
      cell("Who holds it", h ? person(h.id, h.name) + (h.title && h.title !== office.office
        ? '<br><span class="faint">' + esc(h.title) + "</span>" : "") +
        ((h.page || {}).acting ? ' <span class="badge badge-warn">Acting</span>' : "")
        : '<span class="faint">Nobody listed by the White House</span>') +
      cell("Senate vote", h ? senateCell(h) : "") +
      cell("The office’s page", h ? pageCell(h) : "") + "</tr>";
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
    var html = section("executive", "The President and Vice President",
      '<ul class="fed-leaders">' + leaderCard(d.president) + leaderCard(d.vicePresident) + "</ul>" +
      '<p class="faint">Terms from ' + source(d.sources.executive.executive,
        "congress-legislators’ record of executive terms") + ", as of " + esc(asOf.executive) + ".</p>");

    var departments = d.offices.filter(function (o) { return o.kind === "department"; })
      .sort(function (a, b) { return a.order - b.order; });
    var others = d.offices.filter(function (o) { return o.kind !== "department"; });
    var heads = ["Office", "Who holds it", "Senate vote", "The office’s page"];
    html += section("cabinet", "The Cabinet",
      '<p class="guide-lede">Who the White House lists in the ' +
      source(d.sources.executive.cabinet, "President’s Cabinet") + ", each checked on " +
      "the office’s own page and against the Senate’s roll-call votes, as of " +
      esc(asOf.executive) + ". A Cabinet officer is shown without a party.</p>" +
      table("The heads of the fifteen executive departments, in the order 3 U.S.C. 19(d)(1) " +
        "lists them", heads, departments.map(officeRow)) +
      (others.length ? table("Other officers the White House lists with the Cabinet", heads,
        others.map(officeRow)) : ""));

    var scotus = d.supremeCourt || {};
    html += section("supreme-court", "The Supreme Court",
      '<p class="guide-lede">Its members as ' + source(d.sources.judiciary.supremeCourt,
        "the Court lists them") + ", with each justice’s appointment from the Federal " +
      "Judicial Center’s directory, as of " + esc(asOf.judiciary) + ". " +
      '<a href="../courts/scotus.html">The Court’s page</a>.</p>' +
      table("", ["Justice", "Role", "Appointed by", "Since"], justiceRows(scotus.members || [])) +
      ((scotus.retired || []).length
        ? table("Retired justices, listed apart: they are not members of the Court",
          ["Justice", "Role", "Appointed by", "Since"], justiceRows(scotus.retired)) : ""));

    var courts = d.courts.filter(function (c) { return c.kind !== "supreme"; });
    var appeals = courts.filter(function (c) { return c.kind === "appeals"; });
    var body = '<div class="fed-search">' +
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
      if (typed) KYC.router.writeFilters({ q: input.value.trim() });
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
