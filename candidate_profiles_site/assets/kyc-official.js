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
  var routed = false;

  function federal() {
    return global.kycFederal || {};
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
      '    <span id="officialModalSource"></span>',
      '    <span style="display:flex;gap:8px">',
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
    if (!s) {
      return absent("No Senate roll call confirming them to this office was found");
    }
    return "Confirmed " + KYC.escapeHtml(s.yeas + "–" + s.nays) + " on " +
      KYC.escapeHtml(s.date) + " (" + outLink(s.url, "roll call " + s.vote) + ")" +
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
      panel("link", "Links", links.length ? '<div class="links-row">' + links.join("") + "</div>"
        : absent("No links recorded")) + "</div>" +
      '<div class="modal-column">' +
      panel("info", "Where this comes from", '<p class="note-box">The term’s dates and ' +
        "party are from congress-legislators’ record of executive terms; the portrait is " +
        "the White House’s.</p>") + "</div>";
    el("officialModalSource").textContent = "As of " + ((federal().asOf || {}).executive || "");
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
    el("officialModalBody").innerHTML =
      '<div class="modal-column">' +
      panel("check", "The record", '<div class="field-grid">' + rows + "</div>") + "</div>" +
      '<div class="modal-column">' +
      panel("info", "Where this comes from", '<p class="note-box">Listed by the White House ' +
        "among the President’s Cabinet; checked on the office’s own page and " +
        "against the Senate’s roll-call votes. A Cabinet officer is shown without a " +
        "party.</p>") + "</div>";
    el("officialModalSource").textContent = "As of " + ((federal().asOf || {}).executive || "");
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
      if (seat.nominated) parts.push("nominated " + KYC.escapeHtml(seat.nominated));
      if (seat.confirmed) {
        parts.push("confirmed " + KYC.escapeHtml(seat.confirmed) +
          (seat.vote ? " (" + KYC.escapeHtml(vote(seat.vote)) + ")" : ""));
      }
      if (seat.commissioned) parts.push("commissioned " + KYC.escapeHtml(seat.commissioned));
      if (seat.chiefSince) parts.push("chief since " + KYC.escapeHtml(seat.chiefSince));
      if (seat.seniorSince) parts.push("senior status since " + KYC.escapeHtml(seat.seniorSince));
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
    var bio = field("Born", born ? KYC.escapeHtml(born) : absent("Not in the directory"));
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
      panel("scroll", "Career before the bench", career
        ? '<ul class="bullets scroll-y scroll-box">' + career + "</ul>" : absent("Not in the directory")) +
      (judge.otherNominations
        ? panel("info", "Other nominations", '<p class="note-box">' + KYC.escapeHtml(judge.otherNominations) + "</p>")
        : "") +
      panel("link", "Links", '<div class="links-row">' +
        (judge.fjc ? linkChip(judge.fjc, "Federal Judicial Center") : "") + "</div>") +
      "</div>";
    el("officialModalSource").textContent = "Federal Judicial Center, Biographical Directory of " +
      "Article III Federal Judges, as of " + ((federal().asOf || {}).judiciary || "");
  }

  /* --------------------------------------------------------- not listed */

  function renderMissing(id) {
    el("officialModalKind").textContent = "Not listed";
    el("officialModalMeta").textContent = "";
    el("officialModalBody").innerHTML = '<div class="modal-column">' +
      panel("info", "Nobody here by this link", '<p class="note-box">The link names ' +
        KYC.escapeHtml(id) + ", and nobody of that id is among the officials this page lists " +
        "now. They may have left office since the link was made.</p>") + "</div>";
    el("officialModalSource").textContent = "";
  }

  /* ---------------------------------------------------------------- open */

  function render(id, found) {
    var portrait = el("officialModalPortrait");
    var photo = el("officialModalPhoto");
    var person = found ? found.person : null;
    el("officialModalName").textContent = person ? person.name : "No longer listed";
    portrait.hidden = !(person && person.photo);
    if (person && person.photo) {
      photo.src = person.photo;
      photo.alt = person.name;
    } else {
      photo.removeAttribute("src");
      photo.alt = "";
    }
    if (!found) renderMissing(id);
    else if (found.kind === "leader") renderLeader(person);
    else if (found.kind === "officer") renderOfficer(person, found.office);
    else renderJudge(person);
  }

  function open(id, opts) {
    var found = officials()[id] || null;
    ensure();
    current = id;
    render(id, found);
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
    applyRoute: applyRoute, officials: officials,
  };
})(window);
