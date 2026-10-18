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

  /** A day in words, escaped: "Oct. 17, 2026", as the footer under it
   *  writes the same day (KYC.dateWords; anything else as it is). */
  function day(text) {
    return esc(KYC.dateWords(text == null ? "" : text));
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

  /* Where Know Your Government explains each of the hub's sections
   * (kyc/government.py checks these sections exist: tests/test_guide.py). */
  var LEARN = {
    executive: ["executive.html#president", "How the presidency works"],
    cabinet: ["executive.html#departments", "How the executive departments work"],
    succession: ["executive.html#president", "How the presidency works"],
    "supreme-court": ["courts.html#supreme-court", "How the Supreme Court works"],
    courts: ["courts.html#appeals", "How the federal courts are organized"],
  };

  function section(id, title, body) {
    var learn = LEARN[id];
    return '<section class="fed-section" id="' + KYC.escapeAttr(id) + '">' +
      '<div class="section-head"><h2 class="guide-subheading">' + esc(title) + "</h2>" +
      (learn ? '<a class="learn-link" href="' + KYC.escapeAttr("../government/" + learn[0]) + '">' +
        KYC.icon("scroll") + " " + esc(learn[1]) + "</a>" : "") + "</div>" + body + "</section>";
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

  /** A court's active judges by the President who appointed them
   *  (FEDERAL-22): a row per President, earliest appointment first, one
   *  square per judge and the count in words. *caption* is HTML. The
   *  squares are one category colour: the row's name says who, and a
   *  President is never coloured as a party (a judge has none here). */
  function appointerStrip(court, caption) {
    var rows = court.appointers || [];
    if (!court.listed || !rows.length) return "";
    var total = rows.reduce(function (n, r) { return n + r[1]; }, 0);
    return '<figure class="fed-appointers" data-court="' + KYC.escapeAttr(court.id) + '">' +
      "<figcaption>" + caption + "</figcaption><ul>" + rows.map(function (r) {
        var units = "";
        for (var i = 0; i < r[1]; i++) units += "<i></i>";
        var words = r[1] + " of " + total + (court.kind === "supreme" ? " justices" : " active judges") +
          " appointed by " + r[0];
        return '<li class="fed-appointer" title="' + KYC.escapeAttr(words) + '">' +
          '<span class="fed-appointer-name">' + esc(r[0]) + "</span>" +
          '<span class="fed-appointer-bar"><span aria-hidden="true" class="fed-appointer-units">' +
          units + '</span><span class="fed-appointer-n"><span class="sr-only">' +
          esc(words.replace(/ appointed by .*$/, "")) + ": </span>" + r[1] + "</span></span></li>";
      }).join("") + "</ul></figure>";
  }

  function appointersNote(kind) {
    return '<p class="faint">' + (kind === "supreme" ? "The sitting justices" : "Active judges only") +
      ", from the Federal Judicial Center’s directory; earliest appointment first. A count of " +
      "Presidents, not of parties: a " + (kind === "supreme" ? "justice" : "judge") +
      " is shown without one.</p>";
  }

  /** "5 active, 4 senior". A judge the courts' list has on senior status,
   *  whom the directory still lists as active, is counted senior and said
   *  so: neither source is picked silently (kyc/vacancies.py). */
  function counts(court) {
    if (!court.listed) return "";
    return court.active + " active, " + court.senior + " senior" + (court.listedSenior
      ? " (" + court.listedSenior + " of them senior by the courts’ list of vacancies, " +
        "not yet by the FJC directory)" : "");
  }

  /** A judge named on the hub opens on their court's page, which loads
   *  their record; the hub loads only the courts' index. */
  function judgeLink(court, judge, prefix) {
    return '<a href="' + KYC.escapeAttr(prefix + court.id + ".html#/official/" +
      encodeURIComponent(judge.id)) + '">' + esc(judge.name) + "</a>";
  }

  function chiefCell(c, prefix) {
    if (c.chief) return judgeLink(c, c.chief, prefix);
    // The directory lists its chief on senior status too: the court's page
    // says why nobody is named (28 U.S.C. 136(a)).
    if (c.listed && c.chiefUnsettled) {
      return '<span class="faint">Not settled (see <a href="' + KYC.escapeAttr(prefix + c.id +
        ".html#chiefUnsettled") + '">the court’s page</a>)</span>';
    }
    // A territorial court's chief, as the court's own site names them.
    var own = c.courtListed;
    if (!c.listed && own && own.chief) {
      return '<a href="' + KYC.escapeAttr(prefix + c.id + ".html#courtList") + '">' + esc(own.chief) +
        '</a> <span class="faint">(the court’s list)</span>';
    }
    return '<span class="faint">' + (!c.listed ? "Not in the directory" : "None named") + "</span>";
  }

  function courtRows(courts, prefix) {
    return courts.map(function (c) {
      return "<tr><th scope=\"row\">" + courtLink(c, prefix) + "</th>" +
        cell("Chief judge", chiefCell(c, prefix)) +
        // A territorial court's judges serve under Article IV, and the
        // directory lists Article III judges only: the row says so itself.
        cell("Judges", c.listed ? esc(counts(c)) : '<span class="faint" data-article-iv>' +
          (c.courtListed ? esc(c.courtListed.judges + " of " + c.courtListed.seats) +
            " Article IV " + (c.courtListed.seats === 1 ? "judgeship" : "judgeships") +
            " filled, by the court’s list" : "Article IV judges: not in the directory") + "</span>") +
        cell("Vacancies", vacancyCount(c)) + "</tr>";
    });
  }

  /** "2, 1 with a nominee; 1 announced", from the courts' own lists: the
   *  vacancies now, and the ones judges have announced, with their
   *  nominees. */
  function vacancyCount(c) {
    if (!c.vacancies && !c.future) return '<span class="faint">None listed</span>';
    var now = c.vacancies ? c.vacancies + (c.nominees ? ", " + c.nominees + " with a nominee" : "")
      : "None now";
    var later = c.future ? c.future + " announced" + (c.futureNominees
      ? ", " + c.futureNominees + " with a nominee" : "") : "";
    return esc(now + (later ? "; " + later : ""));
  }

  var COURT_HEADS = ["Court", "Chief judge", "Judges", "Vacancies"];

  /* -------------------------------------------------------- vacancies */

  var REASONS = {
    Senior: "Took senior status", Deceased: "Died", Retired: "Retired",
    Resigned: "Resigned", Elevated: "Appointed to another court",
  };
  // An announced vacancy has not happened: the future list's reasons in
  // the future tense, and a judge "elevated" there is only a nominee.
  var FUTURE_REASONS = {
    Senior: "Will take senior status", Retired: "Will retire", Resigned: "Will resign",
    Elevated: "Nominated to another court",
  };

  /** Why a seat is (or will be) vacant, in the tense of the list the row
   *  is from; a nominee's other court is named and linked where the lists
   *  name it. */
  function reasonText(r, prefix) {
    if (!r.future) return esc(REASONS[r.reason] || r.reason || "");
    if (r.reason === "Elevated" && r.nominatedTo) {
      return "Nominated to the " + '<a href="' + KYC.escapeAttr(prefix + r.nominatedTo.id + ".html") +
        '">' + esc(r.nominatedTo.name.replace(/^U\.S\. /, "")) + "</a>";
    }
    return esc(FUTURE_REASONS[r.reason] || r.reason || "");
  }

  /** What a judicial emergency is, in words a phone shows: the courts'
   *  own criteria are caseload and how long the seat has been empty. */
  function emergencyNote(v) {
    return " A judicial emergency is a vacancy the courts have designated as one, for the " +
      "court’s caseload and how long the seat has been empty (" +
      source((v.sources || {}).emergencies || "https://www.uscourts.gov/data-news/judicial-vacancies/judicial-emergencies",
        "the courts’ criteria and list") + ").";
  }

  function personText(p) {
    return p ? esc(p.name) : '<span class="faint">None yet</span>';
  }

  /** The judge a vacancy names, and - where the list implies they still
   *  serve but the directory lists nobody of that name on this court - a
   *  note saying only that (kyc/vacancies.py), never why. */
  function vacatedText(r) {
    return personText(r.vacatedBy) + (r.notInDirectory
      ? ' <span class="faint vacancy-unlisted">Not listed by the FJC directory as serving ' +
        "on this court now</span>" : "");
  }

  /** A court's vacancies, now and announced, as the courts list them. */
  function vacancySection(d, mine) {
    var v = d.vacancies || {};
    var now = mine.vacancies || [];
    var later = mine.future || [];
    var src = source((v.sources || {}).current, "the courts’ list of vacancies");
    var body = '<p class="guide-lede">From ' + src + ", as of " + day(v.asOf) + ".";
    if (later.length) {
      body += " An announced vacancy has not happened yet: the judge has said they will leave.";
    }
    if (!now.length && !later.length) {
      return section("vacancies", "Vacancies", body + " It lists no vacancy on this court, " +
        "and none announced.</p>");
    }
    body += ((mine.judges || []).some(function (j) { return j.listedSenior; })
      ? " A judge the list has on senior status whom the FJC directory still lists as active " +
        "is counted senior here, and their row above says which source says what." : "") +
      (now.some(function (r) { return r.emergency; }) ? emergencyNote(v) : "") + "</p>";
    if (now.length) {
      body += table("", ["Seat vacated by", "Why", "Vacant since", "Nominee", "Nominated"],
        now.map(function (r) {
          return "<tr><th scope=\"row\">" + vacatedText(r) +
            (r.emergency ? ' <span class="badge badge-warn">Judicial emergency</span>' : "") + "</th>" +
            cell("Why", reasonText(r, "")) +
            cell("Vacant since", day(r.since || "")) +
            cell("Nominee", personText(r.nominee)) +
            cell("Nominated", day(r.nominated || "")) + "</tr>";
        }));
    }
    if (later.length) {
      body += '<h3 class="panel-subhead">Announced</h3>' +
        table("", ["Judge leaving", "Why", "Announced", "Leaves", "Nominee", "Nominated"],
          later.map(function (r) {
            return "<tr><th scope=\"row\">" + vacatedText(r) + "</th>" +
              cell("Why", reasonText(r, "")) +
              cell("Announced", day(r.announced || "")) +
              cell("Leaves", r.vacancyDate ? day(r.vacancyDate) : '<span class="faint">Not yet set</span>') +
              cell("Nominee", personText(r.nominee)) +
              cell("Nominated", day(r.nominated || "")) + "</tr>";
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
      (shared ? "" : "; since " + day(p.since) + ", term ends " + day(p.until)) +
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
      esc(s.yeas + "–" + s.nays) + "</a>, " + day(s.date) +
      (s.yeas === s.nays ? ", the Vice President breaking the tie" : "");
  }

  /* Never "confirmed": the cell sits beside the Senate vote, where that
   * word means confirmation, and an acting officer would have read as
   * "Confirmed on its page (acting)" next to "No confirming roll call". */
  function pageCell(holder) {
    var page = (holder && holder.page) || {};
    if (page.status === "confirmed") {
      return '<a href="' + KYC.escapeAttr(page.url) + '" target="_blank" rel="noopener noreferrer">' +
        "Named on the office's site</a>" + (page.acting ? ", as acting" : "");
    }
    if (page.status === "unconfirmed") return '<span class="faint">Not named there when last read</span>';
    if (page.status === "unreadable") return '<span class="faint">Could not be read</span>';
    // "None" is what this site checks, not a claim about the office (rule
    // 19): OMB's page exists and names nobody this site reads (FEDERAL-07).
    return '<span class="faint">Not checked: no page of the office’s is read here</span>';
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
    // Acting before being confirmed: "Since" an acting start, beside a
    // later confirmation vote, read as confirmed service months before
    // the vote. Both are said, the acting start credited to the article
    // that alone gives it (as the changes list does).
    var acting = now && now.actingNote && now.actingStart
      ? "Acting from " + esc(KYC.official.whenText(now.actingStart)) +
        " (their Wikipedia article)" +
        (now.confirmed ? ", then confirmed " + day(now.confirmed.date) : "") : "";
    var prev = before[before.length - 1];
    if (!start && !prev && !acting) return "";
    // A start the sources agree on only to the year or month, beside an
    // exact confirmation date, read as a gap: the vote's day is said, and
    // why the start is not (FEDERAL-13).
    var rough = now && now.start && now.start.shown && now.start.shown.precision !== "day";
    if (start && rough && !acting) {
      start = (now.confirmed ? "Confirmed " + now.confirmed.date + "; took office in " : "") + start +
        " (" + KYC.official.precisionNote(now.start.shown) + ")";
    } else if (start) {
      start = "Since " + start;
    }
    // "After" only when the dates show one handing over to the other on the
    // same day: an acting officer the record lacks may have served between.
    var handover = prev && prev.end && prev.end.shown && now.start && now.start.shown &&
      prev.end.shown.precision === "day" && now.start.shown.precision === "day" &&
      prev.end.shown.date === now.start.shown.date;
    return '<p class="fed-fact"><span class="fed-fact-label">In office</span> ' +
      (acting || day(start)) +
      (prev ? (acting || start ? "; " : "") + (handover ? "after " : "previously this term: ") +
        esc(prev.name) + (prev.acting ? " (acting)" : "") : "") +
      "</p>";
  }

  /** The line of presidential succession as it stands: the Vice
   *  President; the Speaker and the President pro tempore, from
   *  congress-legislators' leadership roles and the membership snapshot;
   *  then the department heads in the statute's order (kyc/federal_build.py
   *  succession). Nobody is typed in. */
  function successionSection(d) {
    var line = d.succession || [];
    if (!line.length) return "";
    var items = line.map(function (p, i) {
      var who;
      if (p.kind === "member") {
        who = '<a href="../index.html#/profile/' + encodeURIComponent(p.id) + '">' + esc(p.name) +
          "</a> <span class=\"faint\">(" + esc(p.state) + ")</span>";
      } else if (p.kind === "official" && p.id) {
        who = person(p.id, p.name) + (p.acting ? ' <span class="badge badge-warn">Acting</span>' : "");
      } else {
        who = '<span class="faint">Nobody listed</span>';
      }
      return '<li value="' + (i + 1) + '"><span class="fed-succession-role">' + esc(p.role) +
        "</span> " + who + "</li>";
    });
    return section("succession", "The line of succession",
      '<p class="guide-lede">Who would act as President, in order, if the office and the ' +
      "Vice Presidency were both empty (" + source("https://www.law.cornell.edu/uscode/text/3/19",
        "3 U.S.C. 19") + "). The Speaker and the President pro tempore are from " +
      source((d.sources.executive || {}).leadership ||
        "https://unitedstates.github.io/congress-legislators/legislators-current.json",
        "congress-legislators’ record of leadership roles") + ", each checked against the " +
      "current membership; the department heads are the Cabinet above.</p>" +
      '<ol class="fed-succession">' + items.join("") + "</ol>" +
      '<p class="faint">The statute counts a department head only if they were appointed with ' +
      "the Senate’s consent (3 U.S.C. 19(e)) and are eligible to be President under the " +
      "Constitution (a natural-born citizen, at least 35, fourteen years a resident). An acting " +
      "head never confirmed to any office is passed over, and whether one confirmed to another " +
      "office counts is unsettled. This page does not check anyone’s eligibility.</p>");
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
            : row.end.overlap ? "Date not shown: both sources put it after the successor took office"
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

  /** A change's words, its person's name opening their record - the
   *  holder now, or a former officer this term (FEDERAL-19) - and the rest
   *  linked to the roll call where there is one. */
  function changeText(e) {
    var name = e.row && e.row.name;
    var known = name && e.row.id && KYC.official.officials()[e.row.id];
    var head = known && e.text.indexOf(name) === 0 ? person(e.row.id, name) : "";
    var rest = head ? e.text.slice(name.length) : e.text;
    var link = e.url ? '<a href="' + KYC.escapeAttr(e.url) + '" target="_blank" rel="noopener noreferrer">' +
      esc(rest.replace(/^\s+/, "")) + "</a>" : esc(rest.replace(/^\s+/, ""));
    return head ? head + (/^’/.test(rest) ? "" : " ") + link : link;
  }

  function changeRow(e) {
    var badge = CHANGE_BADGES[e.kind];
    return "<tr><th scope=\"row\">" + day(e.when) + "</th>" +
      cell("Office", esc(e.office.office)) +
      cell("What happened", '<span class="badge ' + badge[0] + '">' + badge[1] + "</span> " +
        changeText(e)) + "</tr>";
  }

  function changesSection(d) {
    var events = changeEvents(d);
    var meta = d.changes || {};
    // Always drawn: the guide links #changes (government_text.SEE).
    if (!events.length) {
      return section("changes", "Changes since the term began",
        '<p class="faint">No change in the Cabinet is recorded since ' + (meta.since ? day(meta.since) : "the term began") +
        (meta.read ? ", as read " + day(meta.read) : "") + ".</p>");
    }
    var recent = events.slice(0, 12);
    var earlier = events.slice(12);
    var heads = ["When", "Office", "What happened"];
    return section("changes", "Changes since the term began",
      '<p class="guide-lede">Who was confirmed, who left and who served as acting in each ' +
      "office since " + day(meta.since || "") + ", newest first. Confirmations are the " +
      "Senate’s roll calls; who held each office comes from Wikidata, and a date is shown only " +
      "to the day, month or year on which Wikidata and the person’s Wikipedia article agree" +
      (meta.read ? ", as read " + day(meta.read) : "") + ". An acting officer Wikidata does not " +
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
    var role = KYC.holderRole(office);
    return '<li class="fed-card fed-officer">' + portrait(h) +
      '<div><p class="fed-office">' + esc(office.office) + "</p>" +
      '<p class="fed-name">' + person(h.id, h.name) +
      (role.acting ? ' <span class="badge badge-warn">Acting</span>' : "") + "</p>" +
      (role.title ? '<p class="faint">' + esc(role.title) + "</p>" : "") +
      tenureLine(office) +
      '<p class="fed-fact"><span class="fed-fact-label">Senate vote</span> ' + senateCell(h) + "</p>" +
      '<p class="fed-fact"><span class="fed-fact-label">The office’s page</span> ' + pageCell(h) +
      "</p>" + siteLine(office) + "</div></li>";
  }

  /** The agency's own website, as USA.gov's directory lists it: always
   *  linked, whatever the check of the head's name concluded (rule 8). */
  function siteLine(office) {
    var site = office.site;
    if (!site || !site.url) return "";
    return '<p class="fed-fact"><span class="fed-fact-label">Website</span> ' +
      source(site.url, office.body + " website") + "</p>";
  }

  /** The day a justice took the oath, as the Court lists it: one date for
   *  a justice on every page (the members' cards, the Court's page, the
   *  retired table). The commission is the dialog's, beside it. */
  function oathOf(j) {
    return (j.justice && j.justice.oath) || (j.courtService && j.courtService.oath) || "";
  }

  /** A justice as a card: the Court's own portrait, role, appointment. */
  function justiceCard(j) {
    var seat = (j.seats || [])[0] || {};
    return '<li class="fed-card fed-justice">' + portrait(j) +
      '<div><p class="fed-office">' + esc(j.justice ? j.justice.role : seat.title) + "</p>" +
      '<p class="fed-name">' + person(j.id, j.name) + "</p>" +
      '<p class="fed-fact"><span class="fed-fact-label">Appointed by</span> ' +
        esc(seat.appointedBy) + "</p>" +
      '<p class="fed-fact"><span class="fed-fact-label">' + (oathOf(j) ? "Took the oath" : "Commissioned") +
        "</span> " + day(oathOf(j) || seat.commissioned) + "</p></div></li>";
  }

  /** Retired justices: when each took the oath and when they retired,
   *  never a bare "Since" under a heading about retirement. The oath is the
   *  Court's own date, as the members' cards give it; a retired justice's
   *  retirement is the directory's senior-status date. */
  function retiredRows(justices) {
    return justices.map(function (j) {
      var seat = (j.seats || [])[0] || {};
      return "<tr><th scope=\"row\">" + person(j.id, j.name) + "</th>" +
        cell("Role", esc(seat.title)) +
        cell("Appointed by", esc(seat.appointedBy)) +
        cell("Took the oath", oathOf(j) ? day(oathOf(j))
          : '<span class="faint">Not on the Court’s list</span>') +
        cell("Retired", seat.seniorSince ? day(seat.seniorSince)
          : '<span class="faint">Not in the directory</span>') + "</tr>";
    });
  }

  function renderHub(d) {
    var asOf = d.asOf || {};
    var shared = sameTerm(d.president, d.vicePresident);
    var html = section("executive", "The President and Vice President",
      (shared ? '<p class="fed-term" id="executiveTerm">The term: <strong>' +
        day(d.president.since) + "</strong> to <strong>" + day(d.president.until) +
        "</strong></p>" : "") +
      '<ul class="fed-cards fed-leaders">' + leaderCard(d.president, shared) +
        leaderCard(d.vicePresident, shared) + "</ul>" +
      '<p class="faint">Terms from ' + source(d.sources.executive.executive,
        "congress-legislators’ record of executive terms") + ", as of " + day(asOf.executive) + ".</p>");

    var departments = d.offices.filter(function (o) { return o.kind === "department"; })
      .sort(function (a, b) { return a.order - b.order; });
    var others = d.offices.filter(function (o) { return o.kind !== "department"; });
    html += section("cabinet", "The Cabinet",
      '<p class="guide-lede">Who the White House lists in the ' +
      source(d.sources.executive.cabinet, "President’s Cabinet") + ", each checked on " +
      "the office’s own page and against the Senate’s roll-call votes, as of " +
      day(asOf.executive) + ". A Cabinet officer is shown without a party.</p>" +
      '<h3 class="fed-subhead">The heads of the fifteen executive departments, in the order ' +
        '<span class="cite">3 U.S.C. 19(d)(1)</span> lists them</h3>' +
      '<ul class="fed-cards">' + departments.map(officeCard).join("") + "</ul>" +
      (others.length ? '<h3 class="fed-subhead">Other officers the White House lists with ' +
        'the Cabinet</h3><ul class="fed-cards">' + others.map(officeCard).join("") + "</ul>" : "") +
      '<p class="faint">Each department’s website as ' + source(((d.sources.executive || {}).agencies) ||
        "https://www.usa.gov/agency-index", "USA.gov’s index of agencies") + " lists it.</p>");

    html += successionSection(d);
    html += changesSection(d);

    var scotus = d.supremeCourt || {};
    html += section("supreme-court", "The Supreme Court",
      '<p class="guide-lede">Its members as ' + source(d.sources.judiciary.supremeCourt,
        "the Court lists them") + ", with each justice’s appointment from the Federal " +
      "Judicial Center’s directory, as of " + day(asOf.judiciary) + ". " +
      '<a href="../courts/scotus.html">The Court’s page</a>.' +
      ((scotus.members || []).some(function (j) { return j.portrait; })
        ? " Portraits: " + source((scotus.members.filter(function (j) { return j.portrait; })[0]
            .portrait || {}).source, "Collection of the Supreme Court of the United States") + "."
        : "") + "</p>" +
      '<ul class="fed-cards">' + (scotus.members || []).map(justiceCard).join("") + "</ul>" +
      ((scotus.retired || []).length
        ? table("Retired justices, listed apart: they are not members of the Court",
          ["Justice", "Role", "Appointed by", "Took the oath", "Retired"],
          retiredRows(scotus.retired)) : ""));

    var courts = d.courts.filter(function (c) { return c.kind !== "supreme"; });
    var appeals = courts.filter(function (c) { return c.kind === "appeals"; });
    var body = circuitMapMarkup() + '<div class="fed-search">' +
      '<label class="field-label" for="judgeSearch">Find a federal judge</label>' +
      '<input id="judgeSearch" class="search-input" type="search" autocomplete="off" ' +
      'placeholder="A judge’s name" aria-describedby="judgeSearchCount">' +
      '<p class="faint" id="judgeSearchCount" role="status"></p>' +
      '<ul class="fed-results" id="judgeResults"></ul></div>' +
      '<p class="guide-lede" id="courtsLede">Every sitting judge of each court whose judges are ' +
      "appointed under Article III, from the " +
      source(d.sources.judiciary.directory, "Federal Judicial Center’s Biographical Directory") +
      " as of " + day(asOf.judiciary) + ". The three territorial district courts (Guam, the " +
      "Northern Mariana Islands and the Virgin Islands) are not in the directory: their judges " +
      "serve ten-year terms under Article IV, and the directory lists Article III judges only, " +
      "so they are named as each court’s own website lists them. " +
      "Bankruptcy and magistrate judges are not in it" + otherCourts(d) + "</p>" +
      vacancySummary(d) +
      "<h3 class=\"panel-subhead\">Courts of appeals</h3>" +
      table("", COURT_HEADS, courtRows(appeals, "../courts/")) +
      '<details class="fed-earlier" id="appointersByCircuit"><summary>Who appointed each court of ' +
      "appeals’ active judges</summary>" + '<div class="fed-appointers-courts">' +
      appeals.map(function (c) {
        return appointerStrip(c, courtLink(c, "../courts/"));
      }).join("") + "</div>" + appointersNote("appeals") + "</details>";
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
    body += vacancyList(d);
    html += section("courts", "The federal courts", body);
    el("federalBody").innerHTML = html;
    initSearch();
    initCircuitMap(d);
  }

  /** The national courts outside the directory (Article I courts), each
   *  named and linked to its own list of judges (kyc/federal_courts.py),
   *  so a reader can tell they were left out on purpose. */
  function otherCourts(d) {
    var list = (d.otherCourts || []).map(function (c) {
      return source(c.judges, c.name);
    });
    if (!list.length) return ".";
    return ", nor are the national courts created under Article I, whose judges serve terms: " +
      (list.length > 1 ? list.slice(0, -1).join(", ") + " and " + list[list.length - 1] : list[0]) +
      ", each linked to its own list of judges.";
  }

  function vacancySummary(d) {
    var v = d.vacancies;
    if (!v) return "";
    var all = (v.totals.nominees || 0) + (v.futureNominees || 0);
    return '<p class="guide-lede" id="vacancySummary">' + source(v.sources.current,
      "The courts list") + " " + esc(v.totals.vacancies) + " vacancies, " +
      esc(v.totals.nominees) + " with a nominee pending, as of " + day(v.asOf) + "; " +
      esc(v.emergencies) + " of them designated judicial emergencies; and " +
      source(v.sources.future, v.future + " more announced") +
      (v.futureNominees ? ", " + esc(v.futureNominees) + " with a nominee" : "") + ". " +
      (v.futureNominees ? esc(all) + " nominees are pending in all (" + esc(v.totals.nominees) +
        " for vacancies now, " + esc(v.futureNominees) + " for announced ones). " : "") +
      '<a href="#vacancy-list">Every vacancy and nominee</a>.' + emergencyNote(v) + "</p>";
  }

  /** One table of every vacancy, now and announced, with its court and
   *  any nominee: who is nominated, without opening 40 court pages. */
  function vacancyList(d) {
    var v = d.vacancies || {};
    var courts = courtsById();
    var rows = v.rows || [];
    if (!rows.length) return "";
    function row(r) {
      var c = courts[r.court];
      return "<tr><th scope=\"row\">" + (c ? courtLink(c, "../courts/") : esc(r.court)) + "</th>" +
        cell(r.future ? "Judge leaving" : "Seat vacated by", vacatedText(r) +
          (r.emergency ? ' <span class="badge badge-warn">Judicial emergency</span>' : "")) +
        cell("Why", reasonText(r, "../courts/")) +
        cell(r.future ? "Leaves" : "Vacant since", r.future
          ? (r.vacancyDate ? day(r.vacancyDate) : '<span class="faint">Not yet set</span>')
          : day(r.since || "")) +
        cell("Nominee", personText(r.nominee)) +
        cell("Nominated", day(r.nominated || "")) + "</tr>";
    }
    var now = rows.filter(function (r) { return !r.future; });
    var later = rows.filter(function (r) { return r.future; });
    return '<div class="fed-vacancy-list" id="vacancy-list">' +
      '<h3 class="panel-subhead">Vacancies and nominees</h3>' +
      '<p class="faint">As ' + source(v.sources.current, "the courts list them") + ", as of " +
      day(v.asOf) + ". A nominee is pending until the Senate confirms them.</p>" +
      (now.length ? table("Vacant now", ["Court", "Seat vacated by", "Why", "Vacant since", "Nominee",
        "Nominated"], now.map(row)) : "") +
      (later.length ? table("Announced", ["Court", "Judge leaving", "Why", "Leaves", "Nominee",
        "Nominated"], later.map(row)) : "") + "</div>";
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
          mine.map(function (m) { return courtLink(m, "../courts/"); }).join(", ") + "</p>" +
          // Which district covers a county: each county's panel says, from
          // 28 U.S.C. 81-131 (FEDERAL-08).
          (mine.length > 1 ? '<p class="faint">Which of them covers a county: pick the county on ' +
            '<a href="../counties/' + KYC.escapeAttr(code.toLowerCase()) + '.html">' +
            esc(map.name(code)) + "’s county map</a>.</p>" : "")
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
    // A fifth entry is the directory's full name, where the name shown is
    // the one the judge goes by ("A. Joe Fish", "Allen Joe Fish").
    var folded = index.map(function (row) { return KYC.foldText(row[1] + (row[4] ? " " + row[4] : "")); });

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
          '<span class="faint">' + esc(names.join("; ")) + (row[3] === "senior" ? ", senior status"
            : row[3] === "listed-senior" ? ", senior status by the courts’ list (not yet the FJC’s)" : "") +
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

  /** *since* names a last column of the seat's senior-status date: "Senior
   *  status since" for a judge, "Retired" for a retired justice. */
  function judgeRows(judges, since) {
    var scotus = courtId() === "scotus";
    return judges.map(function (j) {
      var seat = (j.seats || []).filter(function (s) {
        return s.court === courtId();
      })[0] || (j.seats || [])[0] || {};
      // Senior by the courts' list, active by the directory: both said.
      var listed = j.listedSenior;
      return "<tr><th scope=\"row\">" + person(j.id, j.name) +
        (seat.chiefSince ? ' <span class="badge badge-neutral">Chief</span>' : "") +
        (listed ? '<br><span class="faint fed-status-note">' + esc(listedSeniorText(listed)) + "</span>" : "") +
        "</th>" +
        cell("Title", esc((j.justice && j.justice.role) || seat.title)) +
        cell("Appointed by", esc(seat.appointedBy)) +
        // A justice's date is the oath the Court lists, as on the hub.
        (scotus ? cell("Took the oath", day(oathOf(j))) : cell("Commissioned", day(seat.commissioned))) +
        (since ? cell(since, listed ? day(listed.since) + ' <span class="faint">(the courts’ list)</span>'
          : day(seat.seniorSince)) : "") + "</tr>";
    });
  }

  function listedSeniorText(listed) {
    return "uscourts.gov lists senior status from " + KYC.dateWords(listed.since) +
      "; the FJC directory has not recorded it yet and still lists active service.";
  }

  /** Confirmed by the Senate and not yet commissioned: listed apart, never
   *  among the court's judges or in its counts (kyc/judiciary.py). */
  function pendingSection(mine) {
    var rows = mine.pending || [];
    if (!rows.length) return "";
    return section("pending", "Confirmed, not yet commissioned",
      '<p class="guide-lede">The Senate has confirmed ' + (rows.length === 1 ? "this judge" : "these judges") +
      ", and the directory records no commission yet. A judge takes office once commissioned, so " +
      "they are not counted among the court’s judges above.</p>" +
      table("", ["Judge", "Appointed by", "Nominated", "Confirmed"], rows.map(function (p) {
        return "<tr><th scope=\"row\">" + (p.fjc ? source(p.fjc, p.name) : esc(p.name)) + "</th>" +
          cell("Appointed by", esc(p.appointedBy || "")) +
          cell("Nominated", day(p.nominated || "")) +
          cell("Confirmed", day(p.confirmed || "") + (p.vote ? " (" + esc(String(p.vote).replace("/", "–")) + ")" : "")) +
          "</tr>";
      })));
  }

  function renderCourt(d) {
    var id = courtId();
    var courts = courtsById();
    var court = courts[id];
    var mine = (global.kycCourt || {})[id];
    var target = el("federalBody");
    if (!court || !mine) {
      // The names written into the page stay: only the full view is missing.
      var kept = target.querySelector(".fed-prerendered");
      target.innerHTML = '<p class="results-bar" role="status">This court’s ' +
        (kept ? "full page" : "judges") + " could not be loaded. Reload the page, or see " +
        source((d.sources.judiciary || {}).directory || "https://www.fjc.gov/history/judges",
          "the Federal Judicial Center’s directory") + ".</p>";
      if (kept) target.appendChild(kept);
      return;
    }
    var asOf = (d.asOf || {}).judiciary;
    if (!mine.listed) {
      target.innerHTML = territorialJudges(mine) + thisCourt(d, court, mine) + vacancySection(d, mine) +
        related(court, courts);
      return;
    }
    var active = mine.judges.filter(function (j) { return j.status !== "senior" && !j.listedSenior; });
    var senior = mine.judges.filter(function (j) { return j.status === "senior" || j.listedSenior; });
    var html = '<p class="guide-lede">' + esc(id === "scotus" ? active.length + " justices"
      : court.active + " active " + (court.active === 1 ? "judge" : "judges") + " and " +
        court.senior + " on senior status" + (court.listedSenior ? " (" + court.listedSenior +
        " of them on senior status by the courts’ list of vacancies, not yet by the FJC " +
        "directory)" : "")) + ", from the " +
      source(d.sources.judiciary.directory, "Federal Judicial Center’s Biographical Directory") +
      " as of " + day(asOf) + (id === "scotus" ? "; its members as " +
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
    html += appointerStrip(court, id === "scotus" ? "The justices, by the President who appointed them"
      : "Active judges, by the President who appointed them");
    if (court.appointers && court.appointers.length) html += appointersNote(court.kind);
    var heads = id === "scotus" ? ["Justice", "Title", "Appointed by", "Took the oath"]
      : ["Judge", "Title", "Appointed by", "Commissioned"];
    html += section("active", id === "scotus" ? "The justices" : "Active judges",
      active.length ? table("", heads, judgeRows(active, false))
        : '<p class="faint">Nobody listed by the directory</p>');
    if (senior.length) {
      html += section("senior", "Judges on senior status",
        '<p class="guide-lede">A judge on senior status keeps the office and may hear a ' +
        "reduced caseload; taking it opens a seat the President may fill (28 U.S.C. 371).</p>" +
        table("", heads.concat(["Senior status since"]), judgeRows(senior, "Senior status since")));
    }
    if ((mine.retired || []).length) {
      html += section("retired", "Retired justices",
        '<p class="guide-lede">Listed apart: they are not members of the Court.</p>' +
        table("", heads.concat(["Retired"]), judgeRows(mine.retired, "Retired")));
    }
    target.innerHTML = html + pendingSection(mine) + vacancySection(d, mine) +
      thisCourt(d, court, mine) + related(court, courts);
  }

  /** A territorial court's judges (FEDERAL-06): they serve ten-year terms
   *  under Article IV, so the FJC's directory of Article III judges does not
   *  list them, and they are listed as the court's own website names them
   *  (kyc/territorial_courts.py) - by name and title only, with no record
   *  to open. A court whose site was never read says so. */
  function territorialJudges(mine) {
    var own = mine.courtList;
    var intro = '<p class="guide-lede">This court’s judges are appointed by the President with ' +
      "the Senate’s consent to ten-year terms under Article IV of the Constitution" +
      (own && own.statute ? " (" + esc(own.statute) + ")" : "") + ", not for life under " +
      "Article III, so the Federal Judicial Center’s directory, which the other court pages " +
      "are built from, does not list them.</p>";
    if (!own || own.unread || !own.judges) {
      return intro + '<p class="results-bar" role="status">The court’s own list of its judges ' +
        "could not be read, so nobody is listed here: that is not a vacancy.</p>";
    }
    var rows = own.judges.map(function (j) {
      return '<tr><th scope="row">' + (j.page ? source(j.page, j.name) : esc(j.name)) +
        (j.chief ? ' <span class="badge badge-neutral">Chief</span>' : "") + "</th>" +
        cell("Title", esc(j.title)) + "</tr>";
    });
    var open = own.seats - own.judges.length;
    return intro + section("courtList", "Judges, as the court lists them",
      (rows.length ? table("", ["Judge", "Title"], rows) : "") +
      '<p class="faint">From ' + source(own.source, "the court’s own website") + ", read " +
      day(own.read) + ". The statute gives the court " + own.seats +
      (own.seats === 1 ? " judgeship" : " judgeships") +
      (open > 0 ? "; the court lists " + (own.judges.length || "nobody") +
        " for it, which is what its page names, not a finding of a vacancy" : "") +
      ". Magistrate and bankruptcy judges the court also lists are not shown, as for every " +
      "court here.</p>");
  }

  /** How to reach the court: its own website (uscourts.gov's list of court
   *  websites, kyc/court_info.py), where to look up a case, and - for a
   *  district court - the counties it covers and where it sits, division
   *  by division, as 28 U.S.C. 81-131 draw them (kyc/court_districts.py). */
  function thisCourt(d, court, mine) {
    var host = court.site ? court.site.replace(/^https?:\/\//, "").replace(/\/.*$/, "") : "";
    var html = '<div class="fed-court-facts">' +
      (court.site ? '<p class="fed-fact"><span class="fed-fact-label">Website</span> ' +
        source(court.site, host) + ' <span class="faint">(dockets, jury service, local rules, ' +
        "the clerk’s office)</span></p>" : "") +
      '<p class="fed-fact"><span class="fed-fact-label">Find a case</span> ' +
      (court.kind === "supreme"
        ? source("https://www.supremecourt.gov/docket/docket.aspx", "the Court’s docket search")
        : source("https://pcl.uscourts.gov/", "PACER Case Locator") + " (the courts’ own records; " +
          "PACER charges for documents) or " + source("https://www.courtlistener.com/", "CourtListener") +
          " (free copies of some, from the Free Law Project)") + "</p>";
    var units = mine.divisions || [];
    if (units.length) {
      var count = units.reduce(function (n, u) { return n + u.counties.length; }, 0);
      var named = units.some(function (u) { return u.division; });
      html += '<p class="fed-fact"><span class="fed-fact-label">Covers</span> ' + count +
        (count === 1 ? " county" : " counties and county equivalents") +
        (named ? " in " + units.length + " divisions" : "") + "</p>" +
        '<ul class="fed-divisions">' + units.map(function (u) {
          return "<li>" + (u.division ? "<strong>" + esc(u.division) + " Division</strong>: " : "") +
            (u.held ? "court is held at " + esc(u.held) + ". " : "") +
            '<details class="fed-counties"><summary>' + u.counties.length +
            (u.counties.length === 1 ? " county" : " counties") + "</summary>" +
            esc(u.counties.join(", ")) + "</details></li>";
        }).join("") + "</ul>" +
        '<p class="faint">From ' + source(d.statute || "https://www.govinfo.gov/app/collection/uscode",
          "28 U.S.C. 81-131") + " (the 2024 edition, with the amendments enacted since), joined to " +
        "the Census Bureau’s counties by name.</p>";
    }
    return section("this-court", "This court", html + "</div>");
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
      el("federalBody").innerHTML = '<p class="results-bar" role="status">This page’s data ' +
        "could not be loaded. Reload the page to try again.</p>";
      return;
    }
    if (root.getAttribute("data-federal") === "court") renderCourt(d); else renderHub(d);
    // The hub holds two of the sidebar's entries: the courts' sections are
    // Federal courts, the rest President & Cabinet.
    if (root.getAttribute("data-federal") === "hub") {
      var syncNav = function () {
        var courts = /^#(supreme-court|courts)\b/.test(global.location.hash);
        Array.prototype.forEach.call(global.document.querySelectorAll(
            '.site-nav [data-nav="executive"], .site-nav [data-nav="courts"]'), function (link) {
          if ((link.getAttribute("data-nav") === "courts") === courts) link.setAttribute("aria-current", "page");
          else link.removeAttribute("aria-current");
        });
      };
      syncNav();
      global.addEventListener("hashchange", syncNav);
    }
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
