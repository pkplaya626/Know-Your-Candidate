/* Know Your Candidate - one federal official's record, in a dialog.
 *
 * An executive officer (the President, the Vice President, a Cabinet
 * officer) from data/federal.js, or a federal judge from the court files the
 * page loaded (data/judiciary/<court>.js) and the Supreme Court's members in
 * data/federal.js. One dialog for the hub and every court page (rule 12),
 * built on KYC.createModal for its focus trap.
 *
 * An official is never a profile: ids are "x-<name>" and "fjc-<nid>", the
 * address is #/official/<id>, and nobody here is counted among the members
 * of Congress (rule 27). A judge carries no party: the Federal Judicial
 * Center's party column is dropped when the directory is read
 * (kyc/judiciary.py), and a judge is described by who appointed them. A
 * Cabinet officer carries none either; the President and the Vice President
 * were elected on a party's ticket and show it.
 */
(function (global) {
  "use strict";

  var KYC = global.KYC;
  var doc = global.document;
  var dialog = null;
  var root = null;
  var current = null;
  // The page's own title, put back when the dialog closes.
  var baseTitle = null;
  var routed = false;

  function federal() {
    return global.kycFederal || {};
  }

  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December"];

  /** An agreed date at its precision: "Feb. 5, 2025", "March 2026", "2026".
   *  A day is in words, as every view writes one (KYC.dateWords): the dialog
   *  read "In office since 2025-01-20" beside the page's "Oct. 17, 2026". */
  function whenText(w) {
    if (!w || !w.date) return "";
    if (w.precision === "month") return MONTHS[Number(w.date.slice(5, 7)) - 1] + " " + w.date.slice(0, 4);
    return KYC.dateWords(w.date);
  }

  /** One holder of an office this term, in words: confirmed, acting, in
   *  office from and to - each date only where the sources agree. */
  function tenureText(row) {
    var parts = [];
    // In the order it happened: acting service, then the confirmation.
    if (row.actingNote) parts.push(row.actingNote.replace(/^Acting:/, "acting"));
    else if (row.acting) parts.push("acting");
    if (row.confirmed) {
      parts.push("confirmed " + KYC.dateWords(row.confirmed.date) + " (" + row.confirmed.yeas + "\u2013" +
        row.confirmed.nays + (row.confirmed.yeas === row.confirmed.nays
          ? ", the Vice President breaking the tie" : "") + ")");
    } else {
      parts.push("no Senate roll call confirming them to this office found");
    }
    var start = row.start && row.start.shown ? whenText(row.start.shown) : "";
    var end = row.end ? (row.end.shown ? whenText(row.end.shown) : "") : "";
    if (row.end && row.end.overlap) {
      // Both sources end it after the next holder began (kyc/cabinet.py).
      parts.push((start ? "in office from " + start + "; " : "") + "the end is not shown: both " +
        "sources put it after the successor took office");
    } else if (row.end) {
      parts.push(start || end ? "in office " + (start || "?") + " to " + (end || "?")
        : "in office, then left; " + (row.end.differs ? "the sources differ on the dates"
          : "the dates are not in both sources"));
    } else if (start) {
      parts.push("in office since " + start);
    } else if (row.start && row.start.differs) {
      parts.push("the sources differ on when they took office");
    }
    return parts.join("; ");
  }

  /** An official's picture: the White House's photo with the sizes it
   *  serves of that one file (rule 42), or a justice's official portrait.
   *  ``{src, srcset, credit, source}``, or null. */
  function picture(person) {
    if (!person) return null;
    if (person.photo) {
      var sizes = person.photoSet || [];
      return {
        src: sizes.length ? sizes[0][0] : person.photo,
        srcset: sizes.map(function (s) { return s[0] + " " + s[1] + "w"; }).join(", "),
        credit: "Photo: The White House", source: null,
      };
    }
    if (person.portrait && person.portrait.url) {
      return { src: person.portrait.url, srcset: "", credit: "Portrait: " + person.portrait.credit,
               source: person.portrait.source };
    }
    return null;
  }

  /** The markup for a picture *px* wide, lazy, decorative (the name is
   *  beside it). */
  function pictureTag(person, px, className) {
    var p = picture(person);
    if (!p) return "";
    return '<img class="' + KYC.escapeAttr(className) + '" src="' + KYC.escapeAttr(p.src) + '"' +
      (p.srcset ? ' srcset="' + KYC.escapeAttr(p.srcset) + '" sizes="' + px + 'px"' : "") +
      ' alt="" width="' + px + '" height="' + Math.round(px * 1.25) +
      '" loading="lazy" decoding="async">';
  }

  /** Every official the page holds, by id: ``{kind, person, office}``. */
  function officials() {
    var out = {};
    var data = federal();
    ["president", "vicePresident"].forEach(function (key) {
      if (data[key]) out[data[key].id] = { kind: "leader", person: data[key] };
    });
    (data.offices || []).forEach(function (office) {
      if (office.holder) out[office.holder.id] = { kind: "officer", person: office.holder, office: office };
    });
    var scotus = data.supremeCourt || {};
    (scotus.members || []).concat(scotus.retired || []).forEach(function (j) {
      out[j.id] = { kind: "judge", person: j };
    });
    var loaded = global.kycCourt || {};
    Object.keys(loaded).forEach(function (cid) {
      (loaded[cid].judges || []).concat(loaded[cid].retired || []).forEach(function (j) {
        out[j.id] = { kind: "judge", person: j };
      });
    });
    return out;
  }

  /** A court's name and page, from the hub's index of courts. */
  function court(id) {
    return (federal().courts || []).filter(function (c) { return c.id === id; })[0] || null;
  }

  /** A court's page, from this page: a court page sits beside the others. */
  function courtUrl(id) {
    var prefix = doc.body.getAttribute("data-page") === "court" ? "" : "../courts/";
    return prefix + encodeURIComponent(id) + ".html";
  }

  /* ---------------------------------------------------------------- markup */

  function template() {
    var wrap = doc.createElement("div");
    wrap.className = "modal";
    wrap.id = "officialModal";
    wrap.hidden = true;
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", "officialModalName");
    wrap.innerHTML = [
      '<button class="modal-scrim" data-close tabindex="-1" aria-hidden="true"></button>',
      '<div class="modal-dialog">',
      '  <button class="btn-icon modal-close" data-close aria-label="Close">',
      KYC.icon("x"),
      "  </button>",
      '  <header class="modal-header">',
      '    <div class="modal-portrait" id="officialModalPortrait" hidden>',
      '      <img id="officialModalPhoto" src="" alt="">',
      "    </div>",
      '    <div class="modal-identity">',
      '      <span class="badge badge-neutral" id="officialModalKind"></span>',
      '      <h2 class="modal-name" id="officialModalName"></h2>',
      '      <p class="modal-meta" id="officialModalMeta"></p>',
      "    </div>",
      "  </header>",
      '  <div class="modal-body scroll-y" id="officialModalBody"></div>',
      '  <footer class="modal-footer">',
      '    <span class="modal-footer-notes"><span id="officialModalSource"></span>',
      // The same way to report an error as a profile's (TRUST-03).
      '    <a class="report-link" id="officialModalReport" data-report target="_blank"' +
      ' rel="noopener noreferrer" href="' + KYC.escapeAttr(KYC.reportUrl()) + '">' +
      KYC.icon("flag") + " Report a problem with this record</a></span>",
      '    <span class="modal-footer-actions">',
      '      <button type="button" class="btn" id="officialModalCopy">' +
      KYC.icon("share") + " Copy link</button>",
      '      <button type="button" class="btn" data-close>Close</button>',
      "    </span>",
      "  </footer>",
      "</div>",
    ].join("");
    return wrap;
  }

  function el(id) {
    return doc.getElementById(id);
  }

  function linkChip(url, label) {
    return '<a class="link-chip" href="' + KYC.escapeAttr(url) +
      '" target="_blank" rel="noopener noreferrer">' + KYC.escapeHtml(label) +
      KYC.icon("share", "link-chip-icon") + "</a>";
  }

  function outLink(url, text) {
    return '<a href="' + KYC.escapeAttr(url) + '" target="_blank" rel="noopener noreferrer">' +
      KYC.escapeHtml(text) + "</a>";
  }

  function panel(icon, title, body) {
    return '<section class="panel"><h3 class="panel-head">' + KYC.icon(icon) + " " +
      KYC.escapeHtml(title) + "</h3>" + body + "</section>";
  }

  function field(label, value, wide) {
    return '<div class="field' + (wide ? " span-2" : "") + '"><span class="field-label">' +
      KYC.escapeHtml(label) + '</span><span class="field-value">' + value + "</span></div>";
  }

  function absent(text) {
    return '<span class="kyc-absent">' + KYC.escapeHtml(text) + "</span>";
  }

  /** "78/22" -> "78-22"; the directory also writes "voice vote". */
  function vote(text) {
    var m = /^(\d+)\/(\d+)$/.exec(String(text || ""));
    return m ? m[1] + "–" + m[2] : String(text || "");
  }

  var REFERENCE = [
    ["whitehouse", "White House", function (v) { return v; }],
    ["wikipedia", "Wikipedia", function (v) {
      return "https://en.wikipedia.org/wiki/" + encodeURIComponent(String(v).replace(/ /g, "_"));
    }],
    ["ballotpedia", "Ballotpedia", function (v) {
      return "https://ballotpedia.org/" + encodeURIComponent(String(v).replace(/ /g, "_"));
    }],
    ["bioguide", "Congress biography", function (v) {
      return "https://bioguide.congress.gov/search/bio/" + encodeURIComponent(v);
    }],
  ];

  /* -------------------------------------------------------- an executive */

  function senateText(holder) {
    var s = holder.senate;
    if (holder.senateUnread) {
      return absent("The Senate’s votes could not be read when last checked; this says nothing either way");
    }
    if (!s) {
      return absent("No Senate roll call confirming them to this office was found");
    }
    // A tied roll call confirms only on the Vice President's vote
    // (Article I, Section 3).
    return "Confirmed " + KYC.escapeHtml(s.yeas + "–" + s.nays) +
      (s.yeas === s.nays ? ", the Vice President breaking the tie," : "") + " on " +
      KYC.escapeHtml(KYC.dateWords(s.date)) + " (" + outLink(s.url, "roll call " + s.vote) + ")" +
      (s.nominee && s.nominee !== holder.name
        ? '<br><span class="faint">The Senate’s record names them ' +
          KYC.escapeHtml(s.nominee) + "</span>" : "");
  }

  function pageText(holder) {
    var page = holder.page || {};
    if (page.status === "confirmed") {
      return "Named beside the title on " + outLink(page.url, "the office’s own page") +
        (page.acting ? " as acting" : "");
    }
    if (page.status === "unconfirmed") {
      return absent("The office’s own page did not name them beside the title when last read") +
        (page.url ? " " + outLink(page.url, "(the page)") : "");
    }
    if (page.status === "unreadable") {
      return absent("The office’s own page could not be read when last checked; this says nothing either way");
    }
    return absent("The office has no page naming its head");
  }

  // An officer's record is found by the Wikidata item the Cabinet's history
  // names them by (kyc/cabinet.py).
  var NO_RECORD = "This site has no Wikidata item for this officer from the Cabinet\u2019s " +
    "history, so their earlier offices are not listed.";

  /* What the officer filed with the Office of Government Ethics, by office
   * (kyc/oge.py): the latest of each kind, linked to the file OGE serves,
   * and what OGE releases only on request counted. Never "not filed": the
   * index is not every report (rule 19). */
  var OGE_INDEX = "https://extapps2.oge.gov/201/Presiden.nsf/";

  function disclosuresPanel(person) {
    var d = person.disclosures;
    var index = outLink(OGE_INDEX, "OGE\u2019s index");
    var about = '<p class="faint">The Office of Government Ethics publishes the reports of the ' +
      "President, the Vice President and the officers the Senate confirms: " + index + ".</p>";
    if (!d || d.notRead) {
      // A claim about this site, not the officer (rule 19).
      return panel("scroll", "Financial disclosures", '<p class="kyc-absent">This site has not ' +
        "read OGE\u2019s index for this officer yet.</p>" + about);
    }
    if (d.none) {
      return panel("scroll", "Financial disclosures", '<p class="kyc-absent">' + (d.refused
        ? "OGE\u2019s index files reports under this office for two people of this officer\u2019s " +
          "surname, so neither\u2019s is shown."
        : "OGE\u2019s index lists no report for this officer under this office.") + "</p>" + about);
    }
    var rows = (d.documents || []).map(function (doc) {
      var when = whenText({ date: doc.date, precision: "day" });
      var label = doc.count && doc.kind === "transaction"
        ? doc.words + "s (" + doc.count + "), the latest posted " + when
        : doc.words;
      return "<li>" + outLink(doc.url, label) +
        (doc.count && doc.kind === "transaction" ? "" : ' <span class="faint">posted ' +
          '<span class="nowrap">' + KYC.escapeHtml(when) + "</span></span>") +
        (doc.as ? ' <span class="faint">as ' + KYC.escapeHtml(doc.as) + "</span>" : "") +
        (doc.amended ? ' <span class="faint">(amended)</span>' : "") +
        (doc.unchecked ? ' <span class="faint held-note" title="' + KYC.escapeAttr(
          "This report is a scan, or was not read: its filer\u2019s name was not checked in it. " +
          "OGE\u2019s index files it under this officer and office.") + '">not checked</span>' : "") +
        "</li>";
    }).join("");
    return panel("scroll", "Financial disclosures",
      (rows ? '<ul class="bullets oge-docs">' + rows + "</ul>"
        : '<p class="kyc-absent">OGE\u2019s index lists no report it publishes as a file.</p>') +
      (d.onRequest ? '<p class="faint">' + d.onRequest + (d.onRequest === 1 ? " more is" : " more are") +
        " listed in " + index + " and released on request.</p>" : "") +
      '<p class="held-source">Filed with the Office of Government Ethics as \u201c' +
      KYC.escapeHtml(d.filed) + "\u201d, " + KYC.escapeHtml(d.position) + ", " +
      KYC.escapeHtml(d.agency) + ". Dates are the day OGE posted each report. Each report OGE " +
      "generates was opened to check it names its filer" + ((d.documents || []).some(function (doc) { return doc.unchecked; })
        ? "; one marked “not checked” is a scan, or could not be read" : "") + ".</p>");
  }

  function renderLeader(person) {
    el("officialModalKind").textContent = person.office;
    el("officialModalMeta").innerHTML =
      "<span>" + KYC.icon("flag") + " " + KYC.escapeHtml(person.party || "") + "</span>" +
      "<span>" + KYC.icon("calendar") + " In office since <strong>" +
      KYC.escapeHtml(person.since || "") + "</strong>; term ends <strong>" +
      KYC.escapeHtml(person.until || "") + "</strong></span>";
    var links = REFERENCE.filter(function (r) { return (person.links || {})[r[0]]; })
      .map(function (r) { return linkChip(r[2](person.links[r[0]]), r[1]); });
    el("officialModalBody").innerHTML =
      '<div class="modal-column">' +
      panel("landmark", "Public offices held", KYC.officesHeld(person.politicalHistory, NO_RECORD)) +
      disclosuresPanel(person) +
      panel("link", "Links", links.length ? '<div class="links-row">' + links.join("") + "</div>"
        : absent("No links recorded")) + "</div>" +
      '<div class="modal-column">' +
      panel("info", "Where this comes from", '<p class="note-box">The term’s dates and ' +
        "party are from congress-legislators’ record of executive terms; the portrait is " +
        "the White House’s.</p>") + "</div>";
    el("officialModalSource").textContent = "As of " + KYC.dateWords((federal().asOf || {}).executive || "");
  }

  function renderOfficer(holder, office) {
    el("officialModalKind").textContent = office.body;
    var titled = holder.title && holder.title !== office.office;
    el("officialModalMeta").innerHTML =
      "<span>" + KYC.icon("landmark") + " <strong>" + KYC.escapeHtml(holder.title || office.office) +
      "</strong></span>" +
      (titled ? '<span class="faint">The office in law: ' + KYC.escapeHtml(office.office) + "</span>" : "") +
      ((holder.page || {}).acting ? '<span class="badge badge-warn">Acting</span>' : "");
    var rows = field("Senate confirmation", senateText(holder), true) +
      field("The office’s own page", pageText(holder), true);
    var history = (office.history || []);
    var since = (federal().changes || {}).since;
    var held = history.length ? '<ol class="bullets fed-history">' + history.map(function (row) {
      return "<li><strong>" + KYC.escapeHtml(row.name) + "</strong>" +
        (row.current ? ' <span class="badge badge-neutral">Now</span>' : "") + "<br>" +
        KYC.escapeHtml(tenureText(row)) + "</li>";
    }).join("") + "</ol>" + '<p class="faint">Confirmations from the Senate’s roll calls; who ' +
      "held the office from Wikidata; dates where Wikidata and the person’s Wikipedia article " +
      "agree. An acting officer Wikidata does not record is not listed.</p>" : "";
    el("officialModalBody").innerHTML =
      '<div class="modal-column">' +
      panel("check", "The record", '<div class="field-grid">' + rows + "</div>") +
      (held ? panel("calendar", "This office since " + (since || "the term began"), held) : "") +
      panel("landmark", "Public offices held", KYC.officesHeld(holder.politicalHistory, NO_RECORD)) +
      "</div>" +
      '<div class="modal-column">' + disclosuresPanel(holder) +
      panel("info", "Where this comes from", '<p class="note-box">Listed by the White House ' +
        "among the President’s Cabinet; checked on the office’s own page and " +
        "against the Senate’s roll-call votes. A Cabinet officer is shown without a " +
        "party.</p>") + "</div>";
    el("officialModalSource").textContent = "As of " + KYC.dateWords((federal().asOf || {}).executive || "");
  }

  /* ------------------------------------------------------------- a judge */

  function seatRows(judge) {
    return (judge.seats || []).map(function (seat) {
      var c = court(seat.court);
      var name = c ? c.name : seat.court;
      var page = doc.getElementById("federalContent");
      var here = !!page && page.getAttribute("data-court") === seat.court;
      var parts = [];
      if (seat.appointedBy) parts.push("Appointed by " + KYC.escapeHtml(seat.appointedBy));
      if (seat.nominated) parts.push("nominated " + KYC.escapeHtml(KYC.dateWords(seat.nominated)));
      if (seat.confirmed) {
        parts.push("confirmed " + KYC.escapeHtml(KYC.dateWords(seat.confirmed)) +
          (seat.vote ? " (" + KYC.escapeHtml(vote(seat.vote)) + ")" : ""));
      }
      if (seat.commissioned) parts.push("commissioned " + KYC.escapeHtml(KYC.dateWords(seat.commissioned)));
      if (seat.reassigned) parts.push("reassigned to this court by statute " + KYC.escapeHtml(KYC.dateWords(seat.reassigned)));
      if (seat.chiefSince) parts.push("chief since " + KYC.escapeHtml(KYC.dateWords(seat.chiefSince)));
      // A retired justice is "retired", as the status line above says, not
      // on "senior status": one word for one status in one dialog.
      if (seat.seniorSince) {
        parts.push((judge.retiredJustice ? "retired since " : "senior status since ") +
          KYC.escapeHtml(KYC.dateWords(seat.seniorSince)));
      }
      return "<li><strong>" + KYC.escapeHtml(seat.title || "Judge") + "</strong>, " +
        (here || !c ? KYC.escapeHtml(name)
          : '<a href="' + KYC.escapeAttr(courtUrl(seat.court)) + '">' + KYC.escapeHtml(name) + "</a>") +
        "<br>" + parts.join("; ") + "</li>";
    }).join("");
  }

  function renderJudge(judge) {
    var seats = judge.seats || [];
    var first = seats[0] || {};
    var c = court(first.court);
    el("officialModalKind").textContent = judge.justice ? "Supreme Court" :
      (c ? c.name : "Federal judge");
    var status = judge.retiredJustice ? "Retired justice, not a member of the Court" :
      judge.status === "senior" ? "Senior status" : "Active service";
    el("officialModalMeta").innerHTML =
      "<span>" + KYC.icon("landmark") + " <strong>" +
      KYC.escapeHtml(judge.justice ? judge.justice.role : (first.title || "Judge")) + "</strong></span>" +
      "<span>" + KYC.escapeHtml(status) + "</span>" +
      (first.appointedBy ? "<span>Appointed by <strong>" + KYC.escapeHtml(first.appointedBy) +
        "</strong></span>" : "");

    var born = judge.born ? [judge.born.city, judge.born.state].filter(Boolean).join(", ") +
      (judge.born.year ? (judge.born.city || judge.born.state ? ", " : "") + judge.born.year : "") : "";
    var bio = (judge.fullName ? field("Full name", KYC.escapeHtml(judge.fullName)) : "") +
      field("Born", born ? KYC.escapeHtml(born) : absent("Not in the directory"));
    if (judge.justice) {
      bio += field("Took the oath", KYC.escapeHtml(judge.justice.oath || "")) +
        field("Appointed from", KYC.escapeHtml(judge.justice.stateAppointedFrom || ""));
    }
    var education = (judge.education || []).map(function (e) {
      return "<li>" + KYC.escapeHtml([e.degree, e.school, e.year].filter(Boolean).join(", ")) + "</li>";
    }).join("");
    bio += field("Education", education ? '<ul class="bullets">' + education + "</ul>"
      : absent("Not in the directory"), true);
    var career = String(judge.career || "").split(/;\s+/).filter(Boolean).map(function (line) {
      return "<li>" + KYC.escapeHtml(line) + "</li>";
    }).join("");

    var prior = (judge.prior || []).map(function (p) {
      return "<li>" + KYC.escapeHtml((p.title || "Judge") + ", " + p.court) + "<br>" +
        KYC.escapeHtml([p.from, p.to].filter(Boolean).join(" to ")) + "</li>";
    }).join("");

    el("officialModalBody").innerHTML =
      '<div class="modal-column">' +
      panel("landmark", seats.length > 1 ? "Seats held now" : "Seat",
        '<ul class="bullets">' + seatRows(judge) + "</ul>") +
      (prior ? panel("calendar", "Earlier federal judicial service", '<ul class="bullets">' + prior + "</ul>") : "") +
      panel("user", "Biography", '<div class="field-grid">' + bio + "</div>") +
      "</div>" +
      '<div class="modal-column">' +
      // The directory's own label: its career field holds roles a judge
      // holds now ("Chair of the board, Federal Judicial Center,
      // 2005-present"), so it is not only a career before the bench.
      panel("scroll", "Professional career", career
        ? '<ul class="bullets scroll-y scroll-box">' + career + "</ul>" : absent("Not in the directory")) +
      (judge.otherNominations
        ? panel("info", "Other nominations", '<p class="note-box">' + KYC.escapeHtml(judge.otherNominations) + "</p>")
        : "") +
      panel("link", "Links", '<div class="links-row">' +
        (judge.fjc ? linkChip(judge.fjc, "Federal Judicial Center") : "") + "</div>") +
      "</div>";
    el("officialModalSource").textContent = "Federal Judicial Center, Biographical Directory of " +
      "Article III Federal Judges, as of " + KYC.dateWords((federal().asOf || {}).judiciary || "");
  }

  /* --------------------------------------------------------- not listed */

  function renderMissing(id) {
    // A court page holds only its own judges; the hub holds everyone.
    var court = doc.body.getAttribute("data-page") === "court";
    el("officialModalKind").textContent = "Not listed";
    el("officialModalMeta").textContent = "";
    el("officialModalBody").innerHTML = '<div class="modal-column">' +
      panel("info", "Nobody here by this link", '<p class="note-box">The link names ' +
        KYC.escapeHtml(id) + (court
          ? ", and nobody of that id sits on this court. " +
            '<a href="../federal/index.html#courts">Find a judge on the federal government’s page</a>.'
          : ", and nobody of that id is among the officials this page lists now. They may " +
            "have left office since the link was made.") + "</p>") + "</div>";
    el("officialModalSource").textContent = "";
  }

  /* ---------------------------------------------------------------- open */

  function render(id, found) {
    var portrait = el("officialModalPortrait");
    var photo = el("officialModalPhoto");
    var person = found ? found.person : null;
    // A court page holds only its own judges: someone not on it may sit
    // elsewhere, so only the hub, which holds everyone, says "no longer".
    el("officialModalName").textContent = person ? person.name :
      doc.body.getAttribute("data-page") === "court" ? "Not on this court" : "No longer listed";
    var pic = picture(person);
    portrait.hidden = !pic;
    if (pic) {
      photo.srcset = pic.srcset;
      photo.sizes = pic.srcset ? "116px" : "";
      photo.src = pic.src;
      photo.alt = person.name;
    } else {
      photo.removeAttribute("srcset");
      photo.removeAttribute("src");
      photo.alt = "";
    }
    if (!found) renderMissing(id);
    else if (found.kind === "leader") renderLeader(person);
    else if (found.kind === "officer") renderOfficer(person, found.office);
    else renderJudge(person);
    // Whose picture it is: credited beside the record's own source.
    if (pic) {
      var credit = doc.createElement("span");
      credit.className = "faint official-credit";
      credit.innerHTML = "; " + (pic.source ? '<a href="' + KYC.escapeAttr(pic.source) +
        '" target="_blank" rel="noopener noreferrer">' + KYC.escapeHtml(pic.credit) + "</a>"
        : KYC.escapeHtml(pic.credit)) + ".";
      el("officialModalSource").appendChild(credit);
    }
  }

  function open(id, opts) {
    var found = officials()[id] || null;
    var elsewhere = !found && (global.kycJudgesIndex || []).filter(function (row) {
      return row[0] === id;
    })[0];
    if (elsewhere) {
      // A judge of a court whose file this page has not loaded: their
      // court's page has their record.
      global.location.replace(courtUrl(elsewhere[2][0]) + "#/official/" + encodeURIComponent(id));
      return true;
    }
    ensure();
    current = id;
    render(id, found);
    el("officialModalReport").setAttribute("data-profile", id);
    // A tab or a bookmark names the person, as a profile's does (GRID-24).
    if (baseTitle === null) baseTitle = doc.title;
    var shown = el("officialModalName").textContent;
    // The pages' own separator: "North Carolina — Know Your Candidate".
    if (shown) doc.title = shown + " — Know Your Candidate";
    if (!(opts && opts.fromRoute)) KYC.router.writeOfficial(id);
    dialog.open();
    return !!found;
  }

  function close() {
    if (dialog) dialog.close();
  }

  function isOpen() {
    return !!dialog && dialog.isOpen();
  }

  /** Open or close as the address says: a shared link, or Back. */
  function applyRoute() {
    var route = KYC.router.read();
    if (route.view === "official") {
      open(route.id, { fromRoute: true });
    } else if (isOpen()) {
      routed = true;
      close();
    }
  }

  function ensure() {
    if (dialog) return dialog;
    root = template();
    doc.body.appendChild(root);
    dialog = KYC.createModal(root, {
      onClose: function () {
        current = null;
        if (baseTitle !== null) doc.title = baseTitle;
        if (routed) {
          routed = false;
          return;
        }
        KYC.router.clearProfile();
      },
    });
    // A portrait that will not load is dropped, never shown broken.
    el("officialModalPhoto").addEventListener("error", function () {
      el("officialModalPortrait").hidden = true;
    });
    var copy = el("officialModalCopy");
    copy.addEventListener("click", function () {
      if (!current) return;
      var url = global.location.origin === "null" ? global.location.href
        : global.location.origin + global.location.pathname + "#/official/" + encodeURIComponent(current);
      if (global.navigator.clipboard && global.navigator.clipboard.writeText) {
        global.navigator.clipboard.writeText(url).then(function () {
          copy.innerHTML = KYC.icon("check") + " Copied";
          setTimeout(function () { copy.innerHTML = KYC.icon("share") + " Copy link"; }, 1800);
        }, function () {});
      }
    });
    return dialog;
  }

  /* One delegated listener: any [data-official] control on the page opens
   * that official (rule 13). */
  doc.addEventListener("click", function (event) {
    var button = event.target.closest && event.target.closest("[data-official]");
    if (!button) return;
    event.preventDefault();
    open(button.getAttribute("data-official"));
  });

  KYC.official = {
    open: open, close: close, isOpen: isOpen, ensure: ensure,
    applyRoute: applyRoute, officials: officials, pictureTag: pictureTag,
    whenText: whenText, tenureText: tenureText,
  };
})(window);
