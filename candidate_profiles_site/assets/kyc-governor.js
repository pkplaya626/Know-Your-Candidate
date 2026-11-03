/* Know Your Candidate - a governor's, or a candidate for governor's, record
 * in a dialog: the overlay the governor cards open (kyc-stategov.js
 * governorCard, candidateCard; rule 91).
 *
 * Built like the federal officials' dialog (kyc-official.js) on
 * KYC.createModal, in the profile dialog's shape: a header with the
 * portrait and its credit, the party, an office tag, the name and the
 * office line; the race's people on the left with what the prediction
 * markets and polling averages say about it (KYC.odds, rule 40); the
 * biography and the public offices held on the right. One implementation
 * for the state pages, the grid's Governors view and the map (rule 12).
 *
 * A governor is never a profile (rule 27): the address is
 * #/official/gov-<ST> for the sitting governor and #/official/gov-<ST>-<name>
 * for a candidate, as the pipeline writes the ids (kyc/statewide.py
 * candidate_id, governor_id); nothing here reads a profile, carries a
 * data-id, or moves a count of Congress. Everything shown is a source's
 * words: the NGA's roster and the election office's list (data/stategov.js),
 * the offices Wikidata and the person's own article agree on (rule 69), a
 * date of birth only where the NGA's page and Wikidata agree (rule 54's
 * pattern). What this site has not read is said so (rule 19): no money (it
 * reads federal campaign filings only), no platform.
 */
(function (global) {
  "use strict";

  var KYC = global.KYC;
  if (!KYC) return;
  var doc = global.document;
  var dialog = null;
  var current = null;
  var baseTitle = null;
  var routed = false;
  var ID = /^gov-([A-Z]{2})(?:-(.+))?$/;

  function sg() { return KYC.stategov; }

  function states() {
    return (global.kycStateGov && global.kycStateGov.states) || {};
  }

  /** Whom an id names: ``{kind, code, person, list}``, or null. */
  function find(id) {
    var m = ID.exec(String(id || ""));
    if (!m) return null;
    var code = m[1];
    var s = states()[code];
    if (!s || !s.governor) return null;
    if (!m[2]) return s.governor.id === id ? { kind: "governor", code: code, person: s.governor } : null;
    var parts = sg().listParts(code, "governor");
    if (!parts || parts.none) return null;
    var person = parts.list.candidates.filter(function (p) { return p.id === id; })[0];
    return person ? { kind: "candidate", code: code, person: person, parts: parts } : null;
  }

  function after() {
    return KYC.electionStatus(2026).phase === "post-election";
  }

  function el(id) {
    return doc.getElementById(id);
  }

  function outLink(url, text) {
    return '<a href="' + KYC.escapeAttr(url) + '" target="_blank" rel="noopener noreferrer">' +
      KYC.escapeHtml(text) + "</a>";
  }

  function linkChip(url, label) {
    return '<a class="link-chip" href="' + KYC.escapeAttr(url) +
      '" target="_blank" rel="noopener noreferrer">' + KYC.escapeHtml(label) +
      KYC.icon("share", "link-chip-icon") + "</a>";
  }

  function panel(icon, title, body, id) {
    return '<section class="panel"' + (id ? ' id="' + id + '"' : "") + '><h3 class="panel-head">' +
      KYC.icon(icon) + " " + KYC.escapeHtml(title) + "</h3>" + body + "</section>";
  }

  function field(label, value, wide) {
    return '<div class="field' + (wide ? " span-2" : "") + '"><span class="field-label">' +
      KYC.escapeHtml(label) + '</span><span class="field-value">' + value + "</span></div>";
  }

  function absent(text) {
    return '<span class="kyc-absent">' + KYC.escapeHtml(text) + "</span>";
  }

  function wikipediaUrl(title) {
    return "https://en.wikipedia.org/wiki/" + encodeURIComponent(String(title).replace(/ /g, "_"));
  }

  /* ---------------------------------------------------------------- markup */

  function template() {
    var wrap = doc.createElement("div");
    wrap.className = "modal";
    wrap.id = "governorModal";
    wrap.hidden = true;
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", "governorModalName");
    wrap.innerHTML = [
      '<button class="modal-scrim" data-close tabindex="-1" aria-hidden="true"></button>',
      '<div class="modal-dialog">',
      '  <button class="btn-icon modal-close" data-close aria-label="Close">',
      KYC.icon("x"),
      "  </button>",
      '  <header class="modal-header">',
      '    <div class="modal-portrait" id="governorModalPortrait">',
      '      <img id="governorModalPhoto" src="" alt="">',
      '      <span class="party-tag" id="governorModalParty"></span>',
      "    </div>",
      '    <div class="modal-identity">',
      '      <span class="badge badge-neutral" id="governorModalKind"></span>',
      '      <h2 class="modal-name" id="governorModalName"></h2>',
      // The list's own form of the name, as a profile's "Files with the
      // FEC as" line sits under the name.
      '      <p class="modal-aka" id="governorModalPrinted" hidden></p>',
      '      <p class="modal-meta" id="governorModalMeta"></p>',
      // The office's ballot mark and the holder line (rule 79), and a
      // candidate's status badge.
      '      <p class="modal-meta" id="governorModalStatus" hidden></p>',
      '      <p class="modal-credit" id="governorModalPhotoCredit" hidden></p>',
      "    </div>",
      "  </header>",
      '  <div class="modal-body scroll-y" id="governorModalBody"></div>',
      '  <footer class="modal-footer">',
      '    <span class="modal-footer-notes"><span id="governorModalSource"></span>',
      '    <a class="report-link" id="governorModalReport" data-report target="_blank"' +
      ' rel="noopener noreferrer" href="' + KYC.escapeAttr(KYC.reportUrl()) + '">' +
      KYC.icon("flag") + " Report a problem with this record</a></span>",
      '    <span class="modal-footer-actions">',
      '      <button type="button" class="btn" id="governorModalCopy">' +
      KYC.icon("share") + " Copy link</button>",
      '      <button type="button" class="btn" data-close>Close</button>',
      "    </span>",
      "  </footer>",
      "</div>",
    ].join("");
    return wrap;
  }

  /* ------------------------------------------------------------ the parts */

  /** The party's colour bucket for the tag under the portrait: a sitting
   *  governor's from the roster's key; a candidate's from the list's words
   *  only where they are one major party's own name (a fusion line is
   *  several parties, drawn in ink: rule 88). */
  function partyKey(person, kind) {
    if (kind === "governor") return String(person.partyKey || "i").toLowerCase();
    var words = String(person.party || "");
    if (/^Democratic(?:-Farmer-Labor|-NPL)?$/.test(words)) return "d";
    if (words === "Republican") return "r";
    return "";
  }

  /** The state's name in a sentence, in its own words (rule 75). */
  function placeName(code) {
    return sg().governorOf(code).replace(/^Governor of /, "");
  }

  /** The link to the state page's section, as the profile's state link. */
  function stateLink(code, part) {
    return '<a class="state-link" href="' + KYC.escapeAttr(KYC.stateUrl(code) + "#" + part) + '">' +
      KYC.escapeHtml(KYC.stateName(code)) + " ›</a>";
  }

  /** The race's term note from the ballot table ("4-year term; term begins
   *  01/2027"), where the office is on the ballot. */
  function termNote(code) {
    var b = sg().ballotOf(code);
    var item = b && b.offices.governor;
    return item && item.up && item.note ? item.note : "";
  }

  /** One candidate as a row in the race panel, in the profile dialog's
   *  race-mate form: portrait, name, party and the badge the cards use.
   *  A button that opens their overlay (one delegated listener, rule 13). */
  function mateRow(person, code) {
    var photo = sg().cardPhoto(person.writeIn ? "" : person.photo, person.photoCopy, person.photoCredit);
    var thumb = photo.img
      ? photo.img.replace('class="gov-portrait"', 'class="gov-portrait race-mate-thumb"')
        .replace('width="72" height="72"', 'width="36" height="36"')
      : '<span class="thumb-monogram" aria-hidden="true"></span>';
    var status = statusBadge(person);
    return '<button type="button" class="race-mate" data-governor="' + KYC.escapeAttr(person.id || "") + '"' +
      (person.id ? "" : " disabled") + ">" + thumb +
      '<span class="race-mate-body"><span class="race-mate-name">' + KYC.escapeHtml(person.name) +
      '</span><span class="race-mate-meta">' +
      (person.party ? '<span class="gcard-party-words">' + KYC.escapeHtml(person.party) + "</span> " : "") +
      status +
      (person.runningMate ? '<span class="faint">with ' + KYC.escapeHtml(person.runningMate) +
        " for lieutenant governor</span>" : "") +
      "</span></span></button>";
  }

  /** The badge in the cards' words: on the list for the November 3 ballot,
   *  or a write-in; after Election Day in the past tense, and never a
   *  winner (rule 91). */
  function statusBadge(person) {
    var past = after();
    var text = person.writeIn
      ? (past ? "Was a write-in candidate" : "Write-in candidate")
      : (past ? "Was on the Nov 3, 2026 ballot" : "On the Nov 3, 2026 ballot");
    var title = person.writeIn
      ? "The election office's list of write-in candidates names them; the name is not printed on the ballot."
      : "The election office's list of candidates for governor names them.";
    return '<span class="badge badge-neutral" title="' + KYC.escapeAttr(title) + '">' +
      KYC.escapeHtml(text) + "</span>";
  }

  /** The race panel: the other candidates as rows, write-ins apart, the
   *  list cited and dated (sg().listParts, the cards' own words), the
   *  markets and averages block, and the line on money (rule 19). */
  function racePanel(code, selfId) {
    var parts = sg().listParts(code, "governor");
    var title = code + " — Governor";
    if (!parts) {
      var b = sg().ballotOf(code);
      var item = b && b.offices.governor;
      return panel("flag", title, '<p class="race-note">' + KYC.escapeHtml(KYC.stateName(code)) +
        " does not elect its governor in 2026." + (item ? " " + sg().officeMark(code, "governor") : "") +
        "</p>");
    }
    if (parts.none) {
      return panel("flag", title, parts.none);
    }
    var others = function (list) { return list.filter(function (p) { return p.id !== selfId; }); };
    var printed = others(parts.printed);
    var writeIns = others(parts.writeIns);
    var html = '<div class="list-rows race-mates">' +
      printed.map(function (p) { return mateRow(p, code); }).join("") + "</div>";
    if (!printed.length && !writeIns.length) {
      html += '<p class="race-note">The list names nobody else for this office.</p>';
    }
    if (writeIns.length) {
      html += '<details class="race-out"><summary>' + writeIns.length + " write-in candidate" +
        (writeIns.length === 1 ? "" : "s") + " (" + (parts.past ? "their names were" : "names") +
        " not printed on the ballot)</summary>" +
        '<div class="list-rows race-mates">' + writeIns.map(function (p) { return mateRow(p, code); }).join("") +
        "</div></details>";
    }
    html += parts.uncertified + parts.source.replace('class="faint gov-candidates-source"',
      'class="race-note race-results gov-candidates-source"');
    // The markets and averages, closed until opened, as a profile's are
    // (TRUST-14); each price quoted and dated, labelled not a poll and not
    // this site's forecast (rule 40).
    html += sg().raceOdds(code, { compact: true, collapsed: true });
    html += '<p class="race-note gov-money-note">Money in this race is not looked at here: this site ' +
      "reads federal campaign filings only, not the state’s.</p>";
    return panel("flag", title, html, "governorModalRacePanel");
  }

  var NO_RECORD_GOVERNOR = "This site reads the offices held through the Wikidata item the NGA roster’s " +
    "cross-check holds for the governor; it has none for this one yet.";
  var NO_RECORD_CANDIDATE = "This site reads a candidate’s offices held through their own article, " +
    "as the race’s Wikipedia article links it (rule 33); it has none for this candidate.";

  /** Where the biography's facts come from, for the governor. */
  function governorBiography(code, gov) {
    var sources = global.kycStateGov.sources || {};
    var nga = sources.nga || [];
    var born = gov.born
      ? KYC.escapeHtml(KYC.dateWords(gov.born.date)) +
        ' <span class="faint">(the NGA’s page and Wikidata agree)</span>'
      : absent("Not shown: this site shows a date of birth only where the NGA’s page and " +
        "Wikidata give the same day");
    var since = gov.since
      ? KYC.escapeHtml(gov.since) + ' <span class="faint">(the NGA’s roster, confirmed by Wikidata)</span>'
      : absent("Not shown: the NGA’s date and Wikidata’s do not agree");
    var contact = [gov.phone, gov.address].filter(Boolean).map(KYC.escapeHtml).join("<br>");
    var links = [outLink(gov.profile, "NGA biography")];
    if (gov.website) links.unshift(outLink(gov.website, "The governor’s office"));
    var body = '<div class="field-grid">' +
      field("Born", born) + field("In office since", since) +
      field("Office", links.join(" · ") + (contact ? "<br>" + contact : ""), true) +
      "</div>" +
      '<p class="held-source">The National Governors Association’s roster' +
      (nga[2] ? ", read " + KYC.escapeHtml(KYC.dateWords(nga[2])) : "") +
      ". No education, career or platform is shown: this site reads none for a governor.</p>";
    return body;
  }

  function governorLinks(gov) {
    var chips = [];
    if (gov.wikipedia) chips.push(linkChip(wikipediaUrl(gov.wikipedia), "Wikipedia"));
    if (gov.wikidata) chips.push(linkChip("https://www.wikidata.org/wiki/" + encodeURIComponent(gov.wikidata), "Wikidata"));
    if (gov.website) chips.push(linkChip(gov.website, "Governor’s office"));
    chips.push(linkChip(gov.profile, "NGA biography"));
    return '<div class="links-row">' + chips.join("") + "</div>" +
      (gov.wikipedia ? '<p class="faint">Wikipedia and Wikidata through the item the NGA roster’s ' +
        "cross-check holds for this governor; never a search by name.</p>" : "");
  }

  function candidateBiography(code, person, parts) {
    var list = parts.list;
    var article = person.wikipedia
      ? linkChip(wikipediaUrl(person.wikipedia), "Wikipedia") +
        '<p class="faint">The article the race’s own Wikipedia article links for this ' +
        "candidate, checked to be theirs (rule 33); never a search by name.</p>"
      : absent("No article linked: this site takes a candidate’s article only from the race’s " +
        "own Wikipedia article, checked to be theirs, and it links none for this candidate");
    var body = '<div class="field-grid">' +
      field("Party", person.party ? KYC.escapeHtml(person.party) : absent("The list gives none")) +
      field("Running mate", person.runningMate
        ? KYC.escapeHtml(person.runningMate) + ' <span class="faint">for lieutenant governor</span>'
        : absent("The list names none")) +
      field("Born", absent("Not looked at: this site reads no biography for a candidate for governor " +
        "beyond the election office’s list and the race’s article")) +
      field("Campaign finance", absent("Not looked at: this site reads federal campaign filings only, " +
        "not the state’s")) +
      field("Platform", absent("Not looked at: this site reads no platform for a candidate for governor"), true) +
      field("Links", article, true) +
      "</div>" +
      '<p class="held-source">The name, party and running mate are ' + outLink(list.url, list.source) +
      "’s, read " + KYC.escapeHtml(KYC.dateWords(list.read)) + ".</p>";
    return body;
  }

  /* ---------------------------------------------------------------- render */

  function setPortrait(url, copy, credit, name) {
    var wrap = el("governorModalPortrait");
    var img = el("governorModalPhoto");
    var line = el("governorModalPhotoCredit");
    var photo = sg().cardPhoto(url, copy, credit);
    img.removeAttribute("data-photo-original");
    img.removeAttribute("data-photo-of");
    if (!photo.credit) {
      img.removeAttribute("src");
      img.alt = "";
      wrap.classList.add("gov-portrait-empty");
      line.innerHTML = "";
      line.hidden = true;
      return;
    }
    wrap.classList.remove("gov-portrait-empty");
    var attrs = doc.createElement("div");
    attrs.innerHTML = photo.img;
    var drawn = attrs.firstChild;
    if (drawn.getAttribute("data-photo-original")) {
      img.setAttribute("data-photo-original", drawn.getAttribute("data-photo-original"));
    }
    if (drawn.getAttribute("data-photo-of")) img.setAttribute("data-photo-of", drawn.getAttribute("data-photo-of"));
    img.src = drawn.getAttribute("src");
    img.alt = name;
    line.innerHTML = photo.credit.replace(/^<p[^>]*>|<\/p>$/g, "");
    line.hidden = false;
  }

  function renderGovernor(code, gov) {
    var key = partyKey(gov, "governor");
    var tag = el("governorModalParty");
    tag.textContent = gov.party || "";
    tag.className = "party-tag party-" + (key || "i");
    // The fill the profile dialog's tag takes (kyc-profile.js PARTY_LABEL_BG).
    tag.style.background = "var(--party-" + (key || "i") + ")";
    tag.hidden = !gov.party;
    el("governorModalKind").textContent = "Governor";
    el("governorModalPrinted").hidden = true;
    el("governorModalMeta").innerHTML =
      "<span>" + KYC.icon("pin") + " <strong>" + KYC.escapeHtml(sg().governorOf(code)) + "</strong> " +
      stateLink(code, "governor") + "</span>" +
      (gov.since ? "<span>" + KYC.icon("calendar") + " In office since <strong>" +
        KYC.escapeHtml(gov.since) + "</strong></span>" : "");
    var status = el("governorModalStatus");
    // The ballot mark is the office's and sits on the office's line, the
    // holder line under it (rule 79), in the card's own words.
    status.innerHTML = '<span class="gov-office">' + sg().officeMark(code, "governor") + "</span>" +
      sg().openSeat(code, "governor").replace(/^<p class="/, '<span class="').replace(/<\/p>$/, "</span>");
    status.hidden = !status.textContent.trim();
    el("governorModalBody").innerHTML =
      '<div class="modal-column">' + racePanel(code, gov.id) + "</div>" +
      '<div class="modal-column">' +
      panel("user", "Biography", governorBiography(code, gov)) +
      panel("landmark", "Public offices held", KYC.officesHeld(gov.politicalHistory, NO_RECORD_GOVERNOR)) +
      panel("link", "Links", governorLinks(gov)) + "</div>";
    var nga = (global.kycStateGov.sources || {}).nga || [];
    el("governorModalSource").textContent = "Governor: " + (nga[0] || "National Governors Association") +
      (nga[2] ? ", read " + KYC.dateWords(nga[2]) : "") + ".";
    setPortrait(gov.headshot, gov.photoCopy, gov.headshotBy
      ? { by: gov.headshotBy, page: gov.headshotPage } : null, gov.name);
  }

  function renderCandidate(code, person, parts) {
    var key = partyKey(person, "candidate");
    var tag = el("governorModalParty");
    tag.textContent = person.party || "";
    tag.className = "party-tag " + (key ? "party-" + key : "party-tag-ink");
    tag.style.background = key ? "var(--party-" + key + ")" : "";
    tag.hidden = !person.party;
    el("governorModalKind").textContent = "Governor (Candidate)";
    var printed = el("governorModalPrinted");
    printed.textContent = person.printed ? "The list prints: " + person.printed : "";
    printed.hidden = !person.printed;
    var note = termNote(code);
    el("governorModalMeta").innerHTML =
      "<span>" + KYC.icon("pin") + " " + (parts.past ? "Ran for" : "Running for") +
      " <strong>Governor • " + KYC.escapeHtml(code) + "</strong> " + stateLink(code, "governor-race") + "</span>" +
      (note ? "<span>" + KYC.icon("calendar") + " Term <strong>" + KYC.escapeHtml(note) + "</strong>" +
        (parts.past ? "" : " (if elected)") + "</span>" : "");
    var status = el("governorModalStatus");
    status.innerHTML = statusBadge(person) +
      (person.ballotName ? ' <span class="faint">Printed on the ballot as “' +
        KYC.escapeHtml(person.ballotName) + "”</span>" : "") +
      (person.surnameOnly ? ' <span class="faint">The list gives a surname only.</span>' : "") +
      (parts.past ? ' <span class="faint">This site does not read the state’s results and names no winner.</span>' : "");
    status.hidden = false;
    el("governorModalBody").innerHTML =
      '<div class="modal-column">' + racePanel(code, person.id) + "</div>" +
      '<div class="modal-column">' +
      panel("user", "Biography", candidateBiography(code, person, parts)) +
      panel("landmark", "Public offices held", KYC.officesHeld(person.politicalHistory, NO_RECORD_CANDIDATE)) +
      "</div>";
    var list = parts.list;
    el("governorModalSource").innerHTML = "Source: " + outLink(list.url, list.source) + " (read " +
      KYC.escapeHtml(KYC.dateWords(list.read)) + ").";
    setPortrait(person.writeIn ? "" : person.photo, person.photoCopy, person.photoCredit, person.name);
  }

  function renderMissing(id) {
    el("governorModalKind").textContent = "Not listed";
    el("governorModalParty").hidden = true;
    el("governorModalPrinted").hidden = true;
    el("governorModalMeta").textContent = "";
    el("governorModalStatus").hidden = true;
    el("governorModalBody").innerHTML = '<div class="modal-column">' +
      panel("info", "Nobody here by this link", '<p class="note-box">The link names ' +
        KYC.escapeHtml(id) + ", and no governor or candidate for governor of that id is in this " +
        "build’s data. The election office’s list may have changed since the link was made.</p>") +
      "</div>";
    el("governorModalSource").textContent = "";
    setPortrait("", null, null, "");
  }

  function render(id, found) {
    el("governorModalName").textContent = found ? found.person.name : "No longer listed";
    if (!found) renderMissing(id);
    else if (found.kind === "governor") renderGovernor(found.code, found.person);
    else renderCandidate(found.code, found.person, found.parts);
  }

  /* ------------------------------------------------------------------ open */

  var pending = null;

  function open(id, opts) {
    if (!sg()) return false;
    if (!sg().loaded()) {
      // The grid loads the governors' data on demand (rule 94): a shared
      // link to an overlay asks for it once, and opens when it comes.
      if (pending === id) return true;
      pending = id;
      KYC.loadData("stategov.js", "kycStateGov", function (ok) {
        var wanted = pending;
        pending = null;
        if (ok && wanted === id) open(id, opts);
      });
      return true;
    }
    var found = find(id);
    ensure();
    current = id;
    KYC.clearShareField(el("governorModalCopy"));
    render(id, found);
    el("governorModalReport").setAttribute("data-profile", id);
    if (baseTitle === null) baseTitle = doc.title;
    var shown = el("governorModalName").textContent;
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

  /** Whether an id is one of these: the sitting governor's or a
   *  candidate's, never a federal official's (x-, fjc-). */
  function owns(id) {
    return ID.test(String(id || ""));
  }

  /** Open or close as the address says: a shared link, or Back. */
  function applyRoute() {
    var route = KYC.router.read();
    if (route.view === "official" && owns(route.id)) {
      open(route.id, { fromRoute: true });
    } else if (isOpen()) {
      routed = true;
      close();
    }
  }

  function ensure() {
    if (dialog) return dialog;
    var root = template();
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
    // A portrait that will not load leaves the circle, and takes its
    // credit with it (rule 87); a copy this site made gives way to its
    // original first (rule 101).
    el("governorModalPhoto").addEventListener("error", function (event) {
      if (KYC.retryOriginal(event.target, event)) {
        var note = el("governorModalPhotoCredit").querySelector(".photo-copy-note");
        if (note) note.remove();
        return;
      }
      event.target.removeAttribute("src");
      el("governorModalPortrait").classList.add("gov-portrait-empty");
      el("governorModalPhotoCredit").hidden = true;
    });
    var copy = el("governorModalCopy");
    copy.addEventListener("click", function () {
      if (!current) return;
      var url = global.location.origin === "null" ? global.location.href
        : global.location.origin + global.location.pathname + "#/official/" + encodeURIComponent(current);
      KYC.shareLink(copy, url);
    });
    return dialog;
  }

  /* One delegated listener (rule 13): the chevron, a race row, or the card
   * itself opens the person it names; a link or a button inside a card goes
   * where it says. Enter on a focused card opens it too. */
  function target(event) {
    var hit = event.target.closest && event.target.closest("[data-governor]");
    if (!hit) return null;
    if (hit.tagName !== "BUTTON" && event.target.closest("a, button, details, summary")) return null;
    return hit;
  }

  doc.addEventListener("click", function (event) {
    var hit = target(event);
    if (!hit || hit.hasAttribute("disabled")) return;
    event.preventDefault();
    open(hit.getAttribute("data-governor"));
  });

  doc.addEventListener("keydown", function (event) {
    if (event.key !== "Enter") return;
    var hit = target(event);
    if (!hit || hit.tagName === "BUTTON" || hit !== event.target) return;
    event.preventDefault();
    open(hit.getAttribute("data-governor"));
  });

  KYC.ready(function () {
    KYC.router.onChange(applyRoute);
    applyRoute();
  });

  KYC.governor = { open: open, close: close, isOpen: isOpen, ensure: ensure, owns: owns,
                   find: find, applyRoute: applyRoute };
})(window);
