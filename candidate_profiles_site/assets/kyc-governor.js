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
      // A slot the credit helper hides once it is empty (rule 87).
      '      <p class="modal-credit" id="governorModalPhotoCredit" data-credit-slot hidden></p>',
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

  /** The term's length, from the ballot table's note where the office is on
   *  the ballot and the note opens with one ("4-year term; term begins
   *  01/2027" -> "4 years"), else "". The rest of a note is why the
   *  office is on the ballot - "last elected 2022", Guam's statute, "open
   *  seat (Mills term-limited)" - and is no term (PR #195 review). Written
   *  as a length: under the label "Term", "4-year term" read "Term 4-year
   *  term (if elected)". */
  function termLength(code) {
    var b = sg().ballotOf(code);
    var item = b && b.offices.governor;
    var years = item && item.up ? sg().termYears(item) : "";
    return years ? years + (years === "1" ? " year" : " years") : "";
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
    return sg().candidateBadge(person);
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
    "as the race’s Wikipedia article links it; it has none for this candidate.";
  var NOT_READ_CANDIDATE = "This site has not yet read the offices held through this candidate’s " +
    "article, which the race’s Wikipedia article links.";

  /* Why a date the NGA gives is not shown, in rule 19's words, as the
   * pipeline records it (kyc/stategov.py since_why, attach_history's
   * bornWhy): a disagreement only where both dates exist and differ. */
  var NOT_CHECKED = "Not shown: this site has no Wikidata item for this governor to check the NGA’s date against";
  var SINCE_WHY = {
    disagree: "Not shown: the NGA’s date and Wikidata’s do not agree",
    "no-item": NOT_CHECKED,
    "no-date": "Not shown: the Wikidata item records no first day in this office to check the NGA’s date against",
    "no-nga": "Not shown: the NGA’s roster gives no first day in office",
  };
  var BORN_WHY = {
    disagree: "Not shown: the NGA’s date and Wikidata’s do not agree",
    "no-item": NOT_CHECKED,
    "not-read": "Not shown: this site has not yet read the Wikidata item’s date of birth to check the NGA’s against",
    "no-date": "Not shown: the Wikidata item records no date of birth to the day to check the NGA’s against",
    "no-nga": "Not shown: the NGA’s page gives no date of birth",
  };
  var ONLY_AGREED = "Not shown: this site shows a date only where the NGA and Wikidata record the same day";

  /** Where the biography's facts come from, for the governor. */
  function governorBiography(code, gov) {
    var sources = global.kycStateGov.sources || {};
    var nga = sources.nga || [];
    var born = gov.born
      ? KYC.escapeHtml(KYC.dateWords(gov.born.date)) +
        ' <span class="faint">(the NGA’s page and Wikidata agree)</span>'
      : absent(BORN_WHY[gov.bornWhy] || ONLY_AGREED);
    var since = gov.since
      ? KYC.escapeHtml(gov.since) + ' <span class="faint">(the NGA’s roster, confirmed by Wikidata)</span>'
      : absent(SINCE_WHY[gov.sinceWhy] || ONLY_AGREED);
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

  /** What the race's own Wikipedia article was found to link for the
   *  candidate, as the pipeline records it (kyc/statewide_photos.py
   *  read_articles): their article; none, where the article was read and
   *  links none; a link not confirmed as theirs; or "not recorded here"
   *  where nothing was read (rule 19). */
  function articleLine(person) {
    var read = person.articleRead ? ", read " + KYC.dateWords(person.articleRead) + "," : "";
    if (person.wikipedia) {
      return linkChip(wikipediaUrl(person.wikipedia), "Wikipedia") +
        '<p class="faint">The article the race’s own Wikipedia article links for this ' +
        "candidate" + KYC.escapeHtml(read || ",") + " checked to be theirs; never a search by name.</p>";
    }
    if (person.articleNone === "not-linked") {
      // A claim about this site's reader, never about the article: a link
      // the reader could not match to the list's name is not an absence
      // (rules 19 and 62; PR #195's second review found Bronson's, Taylor's
      // and Bextel's articles linked where the reader did not look).
      return absent("No article: this site’s reader found no link in the race’s Wikipedia " +
        "article" + (person.articleRead ? " (read " + KYC.dateWords(person.articleRead) + ")" : "") +
        " that it could match to the list’s name, and it never searches by name");
    }
    if (person.articleNone) {
      return absent("No article: the link the race’s own Wikipedia article" + read +
        " gives this candidate could not be confirmed as theirs");
    }
    return absent("Not recorded here: this site has not read the race’s Wikipedia article for " +
      "this candidate");
  }

  /** A candidate who is someone this site has a record of: the sitting
   *  governor (the holder line settles them as the holder) or a member of
   *  Congress an evidenced entry ties to the list's name (the photograph's
   *  member route). Never joined by a name alone (rule 25). */
  function recordLine(code, person, words) {
    if (person.holder) {
      return '<a href="#/official/' + KYC.escapeAttr("gov-" + code) + '">' + KYC.escapeHtml(words.record) + "</a>";
    }
    if (person.member) {
      return '<a href="#/profile/' + KYC.escapeAttr(person.member) + '">' + KYC.escapeHtml(words.record) + "</a>";
    }
    return "";
  }

  /** The document that names *person*: a write-in's is the list of
   *  write-ins where the office keeps one apart (Georgia's certified
   *  write-ins, Maine's declared ones), never the printed list that does
   *  not hold their name (rules 19, 91); everyone else's is the list. The
   *  race panel cites both; the head, the footer, the biography's line and
   *  the share page (kyc/governor_share.py list_for) cite this one. */
  function listFor(list, person) {
    return person && person.writeIn && list && list.writeIns && list.writeIns.source
      ? list.writeIns : (list || {});
  }

  function candidateBiography(code, person, parts, words) {
    var list = listFor(parts.list, person);
    var record = recordLine(code, person, words);
    var mate = words.runningMate.replace(/ for lieutenant governor$/, "");
    var body = '<div class="field-grid">' +
      (record ? field("Record", record, true) : "") +
      field("Party", person.party ? KYC.escapeHtml(person.party) : absent("The list gives none")) +
      field("Running mate", words.runningMate
        ? KYC.escapeHtml(mate) + ' <span class="faint">for lieutenant governor</span>'
        : absent("The list names none")) +
      field("Born", record
        ? absent("Not shown here: see their record")
        : absent("Not looked at: this site reads no biography for a candidate for governor " +
          "beyond the election office’s list and the race’s article")) +
      field("Campaign finance", absent("Not looked at: this site reads federal campaign filings only, " +
        "not the state’s")) +
      field("Platform", absent("Not looked at: this site reads no platform for a candidate for governor"), true) +
      field("Links", articleLine(person), true) +
      "</div>" +
      '<p class="held-source">The name, party and running mate are from ' + outLink(list.url, list.source) +
      ", read " + KYC.escapeHtml(KYC.dateWords(list.read)) + ".</p>";
    return body;
  }

  /* ------------------------------------------------------------ the words */

  function textOf(html) {
    var d = doc.createElement("div");
    d.innerHTML = html;
    return d.textContent.replace(/\s+/g, " ").trim();
  }

  var PAST = "This site does not read the state’s results and names no winner";
  var RECORD = { holder: "The sitting governor: see their record ›",
                 member: "A member of Congress: see their profile ›",
                 // stategov's memberFormer: the membership snapshot no longer seats them.
                 former: "A former member of Congress: see their profile ›" };

  /** Every word the overlay's head and footer give *found* ({kind, code,
   *  person}), each "" where it says none: one table (rule 12) that the
   *  overlay draws from and the share page (o/<id>.html,
   *  kyc/governor_share.py share_words) writes without scripts. The render
   *  suite compares the two for every governor and candidate, and asks
   *  every case of tests/fixtures/governor_share_words.json of this code on
   *  both clocks (rule 96). The ballot mark and the holder line are the
   *  cards' own (officeMark, openSeat, rule 79), read here as text; after
   *  Election Day the past tense and the state's results, naming no winner
   *  (rule 91). */
  function shareWords(found) {
    var code = found.code;
    var p = found.person;
    var past = after();
    var b = sg().ballotOf(code);
    var item = b && b.offices.governor;
    var out = { kind: "", office: "", seeking: "", party: "", since: "", mark: "", holder: "",
                status: "", printed: "", ballotName: "", surnameOnly: "", runningMate: "", term: "",
                record: "", past: "", results: "", source: "" };
    if (past && item && item.up) {
      var voting = (KYC.meta && KYC.meta().voting) || {};
      out.past = PAST;
      out.results = (voting[code] || {}).results || "";
    }
    out.party = p.party || "";
    if (found.kind === "governor") {
      var nga = ((global.kycStateGov || {}).sources || {}).nga || [];
      out.kind = "Governor";
      out.office = sg().governorOf(code);
      out.since = p.since ? "In office since " + p.since : "";
      out.mark = textOf(sg().officeMark(code, "governor"));
      out.holder = textOf(sg().openSeat(code, "governor"));
      out.source = "Governor: " + (nga[0] || "National Governors Association") +
        (nga[2] ? ", read " + KYC.dateWords(nga[2]) : "") + ".";
      return out;
    }
    var list = (item && item.candidates) || {};
    var term = termLength(code);
    out.kind = "Governor (Candidate)";
    out.seeking = past ? "Ran for" : "Running for";
    out.office = "Governor • " + code;
    out.status = textOf(statusBadge(p));
    out.printed = p.printed ? "The list prints: " + p.printed : "";
    out.ballotName = p.ballotName ? "Printed on the ballot as “" + p.ballotName + "”" : "";
    out.surnameOnly = p.surnameOnly ? "The list gives a surname only." : "";
    out.runningMate = p.runningMate ? p.runningMate + " for lieutenant governor" : "";
    out.term = term ? "Term " + term + (past ? "" : " (if elected)") : "";
    out.record = p.holder ? RECORD.holder : p.member ? (p.memberFormer ? RECORD.former : RECORD.member) : "";
    var named = listFor(list, p);
    out.source = "Source: " + named.source + " (read " + KYC.dateWords(named.read) + ").";
    return out;
  }

  /** After Election Day, under an office that was on the ballot: this site
   *  names no winner, and the state's own results are linked (rule 91). */
  function pastLine(words) {
    if (!words.past) return "";
    return ' <span class="faint gov-past">' + KYC.escapeHtml(words.past) +
      (words.results ? ": " + outLink(words.results, "the official results") : "") + ".</span>";
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
    // The card's credit line, as a span naming the photograph it credits
    // (data-credits), so a photograph that fails for good takes it with it
    // through the cards' one helper (KYC.stategov.dropPhotoCredit, rule 87).
    attrs.innerHTML = photo.credit;
    var said = attrs.firstChild;
    var credit = doc.createElement("span");
    credit.setAttribute("data-credits", said.getAttribute("data-credits") || "");
    while (said.firstChild) credit.appendChild(said.firstChild);
    line.innerHTML = "";
    line.appendChild(credit);
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
    // The head's words from the one table the share page writes (rule 96).
    var words = shareWords({ kind: "governor", code: code, person: gov });
    el("governorModalKind").textContent = words.kind;
    el("governorModalPrinted").hidden = true;
    el("governorModalMeta").innerHTML =
      "<span>" + KYC.icon("pin") + " <strong>" + KYC.escapeHtml(words.office) + "</strong> " +
      stateLink(code, "governor") + "</span>" +
      (words.since ? "<span>" + KYC.icon("calendar") + " In office since <strong>" +
        KYC.escapeHtml(gov.since) + "</strong></span>" : "");
    var status = el("governorModalStatus");
    // The ballot mark is the office's and sits on the office's line, the
    // holder line under it (rule 79), in the card's own words; after the
    // election, the state's results, naming no winner (rule 91).
    status.innerHTML = '<span class="gov-office">' + sg().officeMark(code, "governor") + "</span>" +
      sg().openSeat(code, "governor").replace(/^<p class="/, '<span class="').replace(/<\/p>$/, "</span>") +
      pastLine(words);
    status.hidden = !status.textContent.trim();
    el("governorModalBody").innerHTML =
      '<div class="modal-column">' + racePanel(code, gov.id) + "</div>" +
      '<div class="modal-column">' +
      panel("user", "Biography", governorBiography(code, gov)) +
      panel("landmark", "Public offices held", KYC.officesHeld(gov.politicalHistory, NO_RECORD_GOVERNOR)) +
      panel("link", "Links", governorLinks(gov)) + "</div>";
    el("governorModalSource").textContent = words.source;
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
    // The head's words from the one table the share page writes (rule 96).
    var words = shareWords({ kind: "candidate", code: code, person: person });
    el("governorModalKind").textContent = words.kind;
    var printed = el("governorModalPrinted");
    printed.textContent = words.printed;
    printed.hidden = !words.printed;
    var term = /^Term (.+?)( \(if elected\))?$/.exec(words.term);
    el("governorModalMeta").innerHTML =
      "<span>" + KYC.icon("pin") + " " + KYC.escapeHtml(words.seeking) +
      " <strong>" + KYC.escapeHtml(words.office) + "</strong> " + stateLink(code, "governor-race") + "</span>" +
      (term ? '<span class="gov-term">' + KYC.icon("calendar") + " Term <strong>" + KYC.escapeHtml(term[1]) +
        "</strong>" + (term[2] || "") + "</span>" : "");
    var status = el("governorModalStatus");
    status.innerHTML = statusBadge(person) +
      (words.ballotName ? ' <span class="faint">' + KYC.escapeHtml(words.ballotName) + "</span>" : "") +
      (words.surnameOnly ? ' <span class="faint">' + KYC.escapeHtml(words.surnameOnly) + "</span>" : "") +
      pastLine(words);
    status.hidden = false;
    el("governorModalBody").innerHTML =
      '<div class="modal-column">' + racePanel(code, person.id) + "</div>" +
      '<div class="modal-column">' +
      panel("user", "Biography", candidateBiography(code, person, parts, words)) +
      panel("landmark", "Public offices held", KYC.officesHeld(person.politicalHistory,
        person.wikipedia ? NOT_READ_CANDIDATE : NO_RECORD_CANDIDATE)) +
      "</div>";
    var list = listFor(parts.list, person);
    el("governorModalSource").innerHTML = KYC.escapeHtml(words.source)
      .replace(KYC.escapeHtml(list.source), outLink(list.url, list.source));
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

  /* A state's page holds its own state's government alone
   * (data/stategov/<st>.js): a link to another state's governor or race
   * there is not "not in this build's data" (rule 19), but on that state's
   * page, at the same address. Null, or ``{code, here}``: the state the id
   * names and the page's own. Only a place the file names as having a
   * governor (``governed``, kyc/emit.py): the District of Columbia has
   * none, and its page would say nobody was there (rule 19). */
  function elsewhere(id) {
    var m = ID.exec(String(id || ""));
    var code = m ? m[1] : "";
    var page = doc.querySelector('[data-page="state"][data-state]');
    var here = page ? page.getAttribute("data-state") : "";
    var governed = (global.kycStateGov || {}).governed;
    var has = governed ? governed.indexOf(code) !== -1 : KYC.stateName(code) !== code;
    return code && here && code !== here && !states()[code] && has
      ? { code: code, here: here } : null;
  }

  /* A place in its own words (rule 75): "the District of Columbia", "the
   * U.S. Virgin Islands", never "District of Columbia" in a sentence, and
   * no territory or the District called a state. */
  var WITH_THE = { DC: true, MP: true, VI: true };
  function placeWords(code) {
    return (WITH_THE[code] ? "the " : "") + KYC.stateName(code);
  }
  function placeOwn(code) {
    var w = placeWords(code);
    return w + (/Islands$/.test(w) ? "’" : "’s");
  }

  function renderElsewhere(id, other) {
    var there = placeWords(other.code);
    el("governorModalKind").textContent = "On another page";
    el("governorModalParty").hidden = true;
    el("governorModalPrinted").hidden = true;
    el("governorModalMeta").textContent = "";
    el("governorModalStatus").hidden = true;
    el("governorModalBody").innerHTML = '<div class="modal-column">' +
      panel("info", "On " + placeOwn(other.code) + " page", '<p class="note-box">This page holds the records of ' +
        KYC.escapeHtml(placeWords(other.here)) + " alone. The link names " +
        KYC.escapeHtml(id) + ", a record of " + KYC.escapeHtml(there) + ": " + '<a href="' +
        KYC.escapeAttr(KYC.stateUrl(other.code) + "#/official/" + encodeURIComponent(id)) + '">open it on ' +
        KYC.escapeHtml(placeOwn(other.code)) + " page</a>.</p>") + "</div>";
    el("governorModalSource").textContent = "";
    setPortrait("", null, null, "");
  }

  function render(id, found) {
    var other = found ? null : elsewhere(id);
    el("governorModalName").textContent = found ? found.person.name
      : other ? "On " + placeOwn(other.code) + " page" : "No longer listed";
    if (other) renderElsewhere(id, other);
    else if (!found) renderMissing(id);
    else if (found.kind === "governor") renderGovernor(found.code, found.person);
    else renderCandidate(found.code, found.person, found.parts);
  }

  /* ------------------------------------------------------------------ open */

  var pending = false;

  /** The overlay while the governors' data is loading, or where it did
   *  not load (rule 94): said, never a blank or "not listed". */
  function renderWaiting(failed) {
    el("governorModalName").textContent = failed ? "Did not load" : "Loading…";
    el("governorModalKind").textContent = "Governor";
    el("governorModalParty").hidden = true;
    el("governorModalPrinted").hidden = true;
    el("governorModalMeta").textContent = "";
    el("governorModalStatus").hidden = true;
    el("governorModalBody").innerHTML = '<div class="modal-column">' + (failed
      ? panel("info", "The governors’ data did not load", '<p class="note-box">This record cannot be ' +
        "shown, because the file of the states’ governors and their races did not load. Reloading the " +
        "page usually fixes it.</p>")
      : '<p class="race-note" role="status">Loading the governors and their races…</p>') + "</div>";
    el("governorModalSource").textContent = "";
    setPortrait("", null, null, "");
  }

  function open(id, opts) {
    if (!sg()) return false;
    if (!sg().loaded()) {
      // The grid loads the governors' data on demand (rule 94): a shared
      // link to an overlay asks for it once, says so while it loads, and
      // draws the record when it comes - or says it did not load.
      // One wait for the file, whichever record is asked for meanwhile: it
      // draws what is open when the file comes, not the first id asked for.
      // A wait per call left the overlay "Loading…" for ever once the
      // address changed before the file arrived (PR #172 review).
      show(id, null, opts, false);
      if (pending) return true;
      pending = true;
      KYC.loadData("stategov.js", "kycStateGov", function (ok) {
        pending = false;
        if (!isOpen() || !current) return;
        if (ok && sg().loaded()) open(current, { fromRoute: true });
        else renderWaiting(true);
      });
      return true;
    }
    return show(id, find(id), opts, true);
  }

  /** The overlay for *id*: its record (*found*), once the data is in
   *  (*ready*), or the line saying it is loading. */
  function show(id, found, opts, ready) {
    ensure();
    current = id;
    KYC.clearShareField(el("governorModalCopy"));
    if (ready) render(id, found);
    else renderWaiting(false);
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
    // original first (rule 101), which keeps the credit, no longer calling
    // it a copy (KYC.retryOriginal removes that note wherever it is). One
    // helper with the cards (KYC.stategov.dropPhotoCredit, rule 12): only
    // the original failing takes the credit, here and wherever else the
    // page prints it once nothing on the page shows that photograph.
    el("governorModalPhoto").addEventListener("error", function (event) {
      if (KYC.retryOriginal(event.target, event)) return;
      var address = event.target.getAttribute("src");
      if (!address) return;
      event.target.removeAttribute("src");
      el("governorModalPortrait").classList.add("gov-portrait-empty");
      var line = el("governorModalPhotoCredit");
      sg().dropPhotoCredit(address, line.querySelector("[data-credits]"));
      line.hidden = true;
    });
    // "Copy link" shares the person's share page (o/<id>.html, rule 96),
    // which unfurls with their name and the overlay's words; an id nobody
    // here answers to has none, and shares the overlay's own address. A
    // record of another state, which a state's page does not hold
    // (data/stategov/<st>.js, PR #172), shares the address on that state's
    // page, where it is drawn - never this page's note that it is elsewhere.
    var copy = el("governorModalCopy");
    copy.addEventListener("click", function () {
      if (!current) return;
      var found = find(current);
      var other = found ? null : elsewhere(current);
      var url = found ? KYC.shareUrl("official", current)
        : other ? new global.URL(KYC.stateUrl(other.code) + "#/official/" + encodeURIComponent(current),
          global.location.href).href
        : global.location.origin === "null" ? global.location.href
        : global.location.origin + global.location.pathname + "#/official/" + encodeURIComponent(current);
      KYC.shareLink(copy, url, found ? found.person.name : "");
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
                   find: find, applyRoute: applyRoute, shareWords: shareWords,
                   listFor: listFor };
})(window);
