/* Know Your Candidate - who runs each state: its governor, and which party
 * holds each chamber of its legislature.
 *
 * Everything comes from window.kycStateGov, built by kyc/stategov.py: the
 * governor from the National Governors Association's roster, the lieutenant
 * governor and secretary of state from their associations' own rosters
 * (NLGA, NASS), the seats from the legislators Open States lists, checked
 * against NCSL's own count. One module draws it for the map's state views
 * and for every state page, so the two can never disagree (rule 12).
 *
 * A party "holds" a chamber when it has more than half of all its seats. A
 * seat with nobody listed counts for no one and is never called vacant.
 */
(function (global) {
  "use strict";

  var KYC = global.KYC;
  var data = global.kycStateGov || { states: {}, sources: {} };
  var PARTY = { D: "Democratic", R: "Republican" };

  function state(code) {
    return data.states[code] || null;
  }

  var FILL = {
    R: "var(--party-r)",
    D: "var(--party-d)",
    I: "var(--party-i-fill)",
    split: "var(--split)",
    /* A grey of its own (kyc.css): the faint mix it was sat 1.9 apart from
     * the vacant grey to every reader in the light theme. */
    nonpartisan: "var(--nonpartisan-fill)",
    /* An office that does not exist is the faintest grey; a vacancy is the
     * House view's vacant grey; sources that disagree are drawn in the text
     * colour itself, the strongest contrast any theme has, so the three
     * cannot be confused (the muted and faint greys were 1.27:1 in the
     * light theme). */
    disputed: "var(--text)",
    vacant: "var(--vacant-fill)",
    none: "var(--none-fill)",
  };
  /* An office the state does not have is drawn like a nonpartisan body: in
   * neither party's colour, and apart from "not covered". */
  FILL.absent = FILL.nonpartisan;

  /* The statewide offices other than governor, as the data keys them. */
  var OFFICES = {
    lt: { title: "Lieutenant governor", word: "lieutenant governor" },
    ag: { title: "Attorney general", word: "attorney general" },
    sos: { title: "Secretary of state", word: "secretary of state" },
  };

  var LEGENDS = {
    governor: [
      [FILL.R, "Republican governor"],
      [FILL.D, "Democratic governor"],
      [FILL.I, "Another party"],
    ],
    lt: [
      [FILL.R, "Republican"],
      [FILL.D, "Democratic"],
      [FILL.absent, "No lieutenant governor"],
    ],
    sos: [
      [FILL.R, "Republican"],
      [FILL.D, "Democratic"],
      [FILL.absent, "No secretary of state"],
    ],
    ag: [
      [FILL.R, "Republican"],
      [FILL.D, "Democratic"],
    ],
    legislature: [
      [FILL.R, "Republican majority in both chambers"],
      [FILL.D, "Democratic majority in both chambers"],
      [FILL.split, "Split, tied or run by a coalition"],
      [FILL.nonpartisan, "Nonpartisan"],
    ],
    trifecta: [
      [FILL.R, "Republican trifecta"],
      [FILL.D, "Democratic trifecta"],
      [FILL.split, "Divided government"],
      [FILL.nonpartisan, "Nonpartisan legislature"],
    ],
    governor2026: [
      // The year is part of the date: these pages are read long after it.
      // The colour is the sitting governor's party, who may not be running:
      // the legend says whose party it is, not who is on the ballot.
      [FILL.R, "Governor's election Nov 3, 2026 (current governor: Republican)"],
      [FILL.D, "Governor's election Nov 3, 2026 (current governor: Democratic)"],
      [FILL.none, "No governor's election in 2026"],
      // D.C. elects a mayor, not a governor: never the grey above, which
      // would say it holds no election at all.
      [FILL.nonpartisan, "D.C.: a mayor, not a governor"],
    ],
  };

  var TITLES = {
    governor: "Governor",
    lt: "Lieutenant governor",
    ag: "Attorney general",
    sos: "Secretary of state",
    legislature: "State legislature",
    trifecta: "Governor and legislature",
    governor2026: "2026 governor's races",
  };

  /* ------------------------------------------------------ the 2026 ballot */

  /* Which of a state's offices and legislative seats are elected on
   * November 3, from kyc/ballot2026.py, where each value cites the state's
   * own constitution, statute or election pages; and, for each office on
   * that ballot, the candidates its election office lists
   * (kyc/statewide.py, rule 91). */
  var BALLOT_WORD = { governor: "governor", lt: "lieutenant governor",
    ag: "attorney general", sos: "secretary of state" };

  function ballot(code) {
    var s = state(code);
    return s && s.ballot2026 && s.ballot2026.offices ? s.ballot2026 : null;
  }

  function seatsUp(c) {
    var name = c.name === "Legislature" ? "Legislature" : c.name;
    return c.up === c.seats ? "all " + c.seats + " " + name + " seats"
      : c.up + " of the " + c.seats + " " + name + " seats";
    // Regular elections: a special election for an unexpired term is not
    // counted, and the sentence that uses this says so.
  }

  function andList(list) {
    return list.length < 2 ? list.join("")
      : list.slice(0, -1).join(", ") + " and " + list[list.length - 1];
  }

  /** What the state's November 3 ballot elects among its governor,
   *  statewide officers and legislature, in words: "the governor,
   *  lieutenant governor and attorney general; all 56 Senate seats and all
   *  180 House of Representatives seats". "" when it elects none of them,
   *  null when the state is not covered. */
  function ballotList(code) {
    var b = ballot(code);
    if (!b) return null;
    var chambers = ["upper", "lower"].map(function (w) { return b.chambers[w]; })
      .filter(function (c) { return c && c.up; }).map(seatsUp);
    return [ballotOffices(code), andList(chambers)].filter(Boolean).join("; ");
  }

  /** The statewide offices alone, in the same words: "the governor,
   *  lieutenant governor and attorney general"; "" when none is elected,
   *  null when the state is not covered. A state page's "Statewide on the
   *  Nov 3, 2026 ballot" line names them (kyc-state.js). */
  function ballotOffices(code) {
    var b = ballot(code);
    if (!b) return null;
    var offices = ["governor", "lt", "ag", "sos"].filter(function (k) {
      return b.offices[k] && b.offices[k].up;
    }).map(function (k) { return BALLOT_WORD[k]; });
    return offices.length ? "the " + andList(offices) : "";
  }

  /** A mark beside an office or chamber: on the November 3 ballot or not,
   *  linked to the state's own record that says so. */
  function ballotMark(item, text, more) {
    if (!item) return "";
    return '<a class="gov-ballot-mark' + (item.up ? " up" : "") + '" href="' +
      KYC.escapeAttr(item.source) + '" target="_blank" rel="noopener noreferrer" title="' +
      KYC.escapeAttr((item.note || item.basis || "") + (more || "")) + '">' +
      KYC.escapeHtml(text) + "</a>";
  }

  function ballotItem(code, key) {
    var b = ballot(code);
    return (b && b.offices[key]) || null;
  }

  /* The mark is the office's, never the holder's: "On the Nov 3, 2026
   * ballot" printed under Brian Kemp, Gavin Newsom and Tim Walz read as a
   * fact about each of them, and none of them is on it (audit 2026-10-17,
   * STATEGOV-01). So it says "This office", and it sits on the office's own
   * label line, above whoever holds it (rule 79). */
  function after() {
    return KYC.electionStatus(2026).phase === "post-election";
  }

  /** When an office or chamber not on this ballot is next elected, linked
   *  to the record that gives the year (ballot2026.NEXT): never worked out
   *  here from a term length. "" when the table has no year for it. */
  function nextMark(item) {
    if (!item || !item.next) return "";
    // A month other than November is Louisiana's October first round, which
    // a runoff may follow: "Next election", not "Next elected".
    return ' <a class="gov-next" href="' + KYC.escapeAttr(item.next.source) +
      '" target="_blank" rel="noopener noreferrer">' +
      (item.next.month ? "Next election: " + KYC.escapeHtml(item.next.month) : "Next elected: November") +
      " " + KYC.escapeHtml(String(item.next.year)) + "</a>";
  }

  function officeMark(code, key) {
    var b = ballot(code);
    var item = b && b.offices[key];
    if (!item) return "";
    if (item.up) {
      return ballotMark(item, "This office " + (after() ? "was" : "is") + " on the Nov 3, 2026 ballot");
    }
    var elected = item.selection === "elected" || item.selection === "elected-jointly-with-governor";
    return ballotMark(item, elected ? "Not elected in 2026"
      : item.selection === "appointed" ? "Appointed, not elected"
      : item.selection === "chosen-by-legislature" ? "Chosen by the legislature, not elected"
      : "No such office") + (elected ? nextMark(item) : "");
  }

  /** Whether the holder of an office on the ballot is on it
   *  (stategov.holder_line): "Open seat" where a cited source - the
   *  election office's list of candidates, or the constitution's term
   *  limit with the list beside it - says they are not, the list's word
   *  where it names them ("on the certified list", never "running for
   *  re-election"), and, for any other office on the ballot, that this was
   *  not checked. One office silent beside another that said "Open seat"
   *  read as "the holder is running" (PR #94 review, rule 19). Said only
   *  until the election: after it, the office has a winner.
   *
   *  *opts.role*: the line stands where no holder block is above it (the
   *  Your ballot page), so it says who the holder is - "the holder, Katie
   *  Hobbs, is among the candidates" - or one candidate stood above the
   *  list, singled out for no stated reason (PR #115 review). */
  function openSeat(code, key, opts) {
    var b = ballot(code);
    var item = b && b.offices[key];
    var status = item && item.up && item.holderStatus;
    if (!status || after()) return "";
    var text = status.text;
    var at = status.holder ? text.indexOf(status.holder) : -1;
    var opens = status.why === "listed" || status.why === "unchecked";
    if (opts && opts.role && at !== -1) {
      // A sentence's first word in capitals; after "Open seat:", not.
      var the = at === 0 && opens ? "The holder, " : "the holder, ";
      text = text.slice(0, at) + the + status.holder + "," + text.slice(at + status.holder.length);
    }
    if (status.why === "unchecked") {
      return '<p class="gov-holder-status gov-holder-unchecked">' + KYC.escapeHtml(text) +
        ".</p>";
    }
    return '<p class="gov-holder-status' + (status.why === "listed" ? "" : " gov-open-seat") + '">' +
      (status.why === "listed" ? "" : "Open seat: ") + KYC.escapeHtml(text) + " (" +
      link(status.source, status.cite) + ")" +
      (status.then ? " and " + KYC.escapeHtml(status.then.text) + " (" +
        link(status.then.source, status.then.cite) + ")" : "") + ".</p>";
  }

  /* ------------------------------------------- the candidates on the ballot */

  /* One candidate as the pipeline writes them (statewide.for_page): the
   * name first name first and in ordinary capitals, with the list's own
   * form on hover (`printed`); the party in words, never the list's code;
   * a write-in's "party" that says only that it is a write-in dropped. A
   * candidate with a record of their own (Pennsylvania's lieutenant
   * governors) is linked to it. A photograph, where one reached the
   * candidate by a route tied to them (kyc/statewide_photos.py), sits
   * beside the name with whose it is under it (rule 87); in a list where
   * any candidate has one, the rest keep its column, an empty circle. */
  function candidateRow(person, key, pictured) {
    // A joint ticket: the governor's list names the running mate for
    // lieutenant governor, and the lieutenant governor's the governor.
    var mate = !person.runningMate ? ""
      : key === "lt" ? ", running with " + KYC.escapeHtml(person.runningMate) + " for governor"
      : ", with " + KYC.escapeHtml(person.runningMate) + " for lieutenant governor";
    var name = person.record ? link(person.record, person.name) : KYC.escapeHtml(person.name);
    // The smaller copy this site made of a heavy one, credited as the
    // original with the copy said (rule 101: KYC.photoAttrs, KYC.copyCredit).
    var credit = person.photo
      ? KYC.photoCreditHtml(KYC.copyCredit(person.photoCredit, person.photo, person.photoCopy)) : "";
    var photo = !pictured ? ""
      : person.photo && credit
        ? '<img class="gov-photo gov-candidate-photo" ' +
          KYC.photoAttrs(person.photo, person.photoCopy) +
          ' alt="" width="32" height="32" loading="lazy" decoding="async">'
        : NO_SMALL_PHOTO;
    return '<li class="gov-candidate' + (pictured ? " gov-pictured" : "") + '">' + photo +
      '<span class="gov-candidate-text"><span class="gov-candidate-name"' +
      (person.printed ? ' title="' + KYC.escapeAttr("The list prints: " + person.printed) + '"' : "") +
      ">" + name + "</span>" +
      (person.surnameOnly ? ' <span class="faint">(the list gives a surname only)</span>' : "") +
      (person.party ? ' <span class="gov-candidate-party">(' + KYC.escapeHtml(person.party) + ")</span>" : "") +
      mate +
      (person.ballotName ? '<span class="faint">; printed on the ballot as “' +
        KYC.escapeHtml(person.ballotName) + "”</span>" : "") +
      (photo && credit ? '<span class="gov-photo-credit">' + credit + "</span>" : "") +
      "</span></li>";
  }

  /** Where the state's own returns are, after the election: this site does
   *  not read state results, so it names no winner (voting.RESULTS). */
  function resultsLine(code) {
    var voting = (KYC.meta && KYC.meta().voting) || {};
    var url = (voting[code] || {}).results;
    return " This site does not read the state's results and names no winner" +
      (url ? ": " + link(url, "the official results") : "") + ".";
  }

  /** The candidates the election office lists for an office on the
   *  November 3 ballot, under the office (rule 91): each name and party as
   *  the list prints them, the running mate on a joint ticket, write-in
   *  candidates apart, credited to the list and the day it was read. No
   *  money or platform, and no link to a profile: nothing on the list says
   *  a candidate is the person of the same name elsewhere on this site
   *  (rule 25). A photograph only by the routes rule 91 names, with whose
   *  it is beside it. After the election it is in the past tense and
   *  points to the state's results. */
  function candidatesBlock(code, key) {
    var item = ballotItem(code, key);
    if (!item || !item.up) return "";
    var past = after();
    var list = item.candidates;
    if (!list) {
      // An office on the ballot whose list has not been read is said so,
      // not left blank beside offices that list their candidates.
      return '<div class="gov-candidates"><p class="gov-candidates-none">' +
        (past ? "Who was on the Nov 3, 2026 ballot for this office is not listed here"
          : "The candidates for this office are not listed here") +
        ": no election office's list of them has been read." + (past ? resultsLine(code) : "") +
        "</p></div>";
    }
    var printed = list.candidates.filter(function (p) { return !p.writeIn; });
    var writeIns = list.candidates.filter(function (p) { return p.writeIn; });
    var pictured = list.candidates.some(function (p) { return p.photo && p.photoCredit; });
    var row = function (p) { return candidateRow(p, key, pictured && !p.writeIn); };
    // The document is named as what it is - "the Florida Division of
    // Elections’ candidate listing", "Clark County Registrar of Voters’
    // notice of general election" - and called certified only where its
    // own words say so (statewide.source_words; PR #109 review).
    var credit = "Source: " + link(list.url, list.source) +
      " (read " + KYC.escapeHtml(KYC.dateWords(list.read)) + ")" +
      (list.writeIns && list.writeIns.url !== list.url
        ? "; write-in candidates: " + link(list.writeIns.url, list.writeIns.source) +
          " (read " + KYC.escapeHtml(KYC.dateWords(list.writeIns.read)) + ")"
        : "") + ".";
    var recased = list.candidates.some(function (p) { return p.printed; });
    return '<div class="gov-candidates">' +
      '<p class="gov-candidates-head">' + (past ? "Candidates who were on the Nov 3, 2026 ballot"
        : "Candidates on the Nov 3, 2026 ballot") + "</p>" +
      (list.notStateList ? '<p class="gov-candidates-uncertified">Not the state’s own list. ' +
        KYC.escapeHtml(list.notStateList) + ".</p>" : "") +
      '<ul class="gov-candidate-list">' + printed.map(row).join("") + "</ul>" +
      (writeIns.length
        ? '<p class="gov-candidates-head gov-writein-head">Write-in candidates (' +
          (past ? "their names were" : "names") + " not printed on the ballot)</p>" +
          '<ul class="gov-candidate-list gov-writein-list">' + writeIns.map(row).join("") + "</ul>"
        : "") +
      '<p class="faint gov-candidates-source">In surname order, not ballot order. ' +
        (recased ? "Names are written first name first, in ordinary capitals and without a " +
          "title the ballot prints; the list writes them its own way. " : "") + credit +
        (past ? resultsLine(code) : "") + "</p></div>";
  }

  /** The office's label with its ballot mark beside it. */
  function officeLine(cls, label, mark) {
    return '<p class="gov-office"><span class="' + cls + '">' + KYC.escapeHtml(label) + "</span>" +
      (mark ? " " + mark : "") + "</p>";
  }

  function chamberMark(code, which) {
    var b = ballot(code);
    var c = b && b.chambers[which];
    if (!c) return "";
    return ballotMark(c, !c.up ? "No regular elections in 2026"
      : (c.up === c.seats ? "All " + c.seats : c.up + " of " + c.seats) + " seats on the Nov 3, 2026 ballot",
      " Regular elections only: a special election to fill an unexpired term is not counted.") +
      (!c.up ? nextMark(c) : "");
  }

  function any(test) {
    return Object.keys(data.states).some(function (c) { return test(data.states[c]); });
  }

  /** The legend for one of the map's state views: [[fill, label]]. "Vacant"
   * and "Sources disagree" appear only when some state is. */
  function legend(mode) {
    var rows = (LEGENDS[mode] || []).slice();
    if (OFFICES[mode]) {
      if (any(function (s) {
        var key = s[mode] && s[mode].partyKey;
        return key && key !== "D" && key !== "R";
      })) {
        rows.push([FILL.I, "Another party"]);
      }
      if (any(function (s) { return !s[mode]; })) rows.push([FILL.none, "Not listed"]);
      if (any(function (s) { return s[mode] && s[mode].vacant; })) rows.push([FILL.vacant, "Vacant"]);
      if (any(function (s) { return s[mode] && s[mode].disputed; })) {
        rows.push([FILL.disputed, "Sources disagree"]);
      }
      // NASS's listing of a non-member is drawn in the same grey (look()).
      if (any(function (s) {
        return s[mode] && (s[mode].unconfirmed || s[mode].unlisted || s[mode].notMember);
      })) {
        rows.push([FILL.vacant, "Not confirmed by the office"]);
      }
    } else if (mode !== "governor" && any(function (s) { return s.legislature === "disputed"; })) {
      rows.push([FILL.disputed, "Sources disagree"]);
    }
    return rows;
  }

  function partyName(letter) {
    return PARTY[letter] || letter;
  }

  function seatWord(n) { return n + " seat" + (n === 1 ? "" : "s"); }

  function control(key) {
    return key === "nonpartisan" ? "elected without party labels"
      : key === "coalition" ? "run by a coalition across parties"
      : key === "disputed" ? "the sources disagree"
      : key === "split" ? "split: no party holds both chambers"
      : PARTY[key] ? PARTY[key] + " majority in both chambers" : "";
  }

  function trifectaText(key) {
    return key === "R" || key === "D"
      ? PARTY[key] + " trifecta: one party holds the governorship and a majority of the seats in both chambers"
      : key === "nonpartisan" ? "No trifecta is possible: the Legislature is elected without party labels"
      : key === "disputed" ? "The sources disagree about which party holds a chamber"
      : "Divided government: no one party holds the governorship and both chambers";
  }

  /** Fill and hover text for one state in one of the map's state views. */
  function look(code, mode) {
    var s = state(code);
    var name = KYC.stateName(code);
    if (mode === "governor2026" && !ballot(code)) {
      return { fill: FILL.nonpartisan, text: code === "DC"
        ? "D.C. elects a mayor, not a governor" : name + ": not covered here" };
    }
    if (!s) {
      return { fill: FILL.none, text: code === "DC"
        ? "D.C. has an elected mayor and council, not a governor"
        : name + ": no governor listed" };
    }
    var gov = s.governor;
    if (mode === "governor") {
      return { fill: FILL[gov.partyKey] || FILL.I,
               text: name + ": Gov. " + gov.name + " (" + gov.party + ")" };
    }
    if (mode === "governor2026") {
      // An open seat, where the election office's list leaves the governor
      // off (rule 91): said in words; the colour stays the sitting
      // governor's party, as the legend says.
      var hs = ballot(code).offices.governor.holderStatus;
      var said = hs && (hs.why === "not-listed" ? hs : hs.why === "term-limit" ? hs.then : null);
      // The list is named, as every other such claim on the site names it.
      var open = !after() && hs && hs.holder === gov.name && said
        ? "; open seat: " + gov.name + " is not among the candidates on " + said.cite : "";
      return ballot(code).offices.governor.up
        ? { fill: FILL[gov.partyKey] || FILL.I,
            text: name + ": the governor " +
              (KYC.electionStatus(2026).phase === "post-election" ? "was" : "is") +
              " elected on Nov 3, 2026 (current governor: " + gov.name + ", " + gov.party + ")" + open }
        : { fill: FILL.none, text: name + ": no governor's election in 2026" };
    }
    if (OFFICES[mode]) {
      var off = s[mode];
      var word = OFFICES[mode].word;
      if (!off) return { fill: FILL.none, text: name + ": no " + word + " listed" };
      if (off.disputed) return { fill: FILL.disputed, text: name + ": the sources disagree about the " + word };
      if (off.unconfirmed || off.unlisted) {
        return { fill: FILL.vacant, text: name + ": the " + word + " could not be confirmed with the office" };
      }
      if (off.vacant) return { fill: FILL.vacant, text: name + ": the office of " + word + " is vacant" };
      if (off.notMember) {
        return { fill: FILL.vacant, text: name + ": the " + word + " is not confirmed (NASS's listing only)" };
      }
      if (off.none) return { fill: FILL.absent, text: name + " has no " + word };
      return { fill: FILL[off.partyKey] || FILL.I,
               text: name + ": " + off.title + " " + off.name + " (" + partyName(off.party) + ")" };
    }
    if (!s.legislature) {
      return { fill: FILL.none, text: name + ": its legislature is not covered here" };
    }
    if (mode === "legislature") {
      var key = s.legislature === "coalition" ? "split" : s.legislature;
      return { fill: FILL[key] || FILL.split, text: name + " legislature: " + control(s.legislature) };
    }
    var t = s.trifecta === "divided" ? "split" : s.trifecta;
    return { fill: FILL[t] || FILL.split, text: name + ": " + trifectaText(s.trifecta).split(":")[0] };
  }

  /** The panel's badge: the party pills that say it at a glance. A
   * territory's governor is never shown as its legislature's party. */
  function badge(code, mode) {
    var s = state(code);
    if (!s) return '<span class="faint">No governor</span>';
    if (mode === "governor") {
      return '<span class="party-' + KYC.escapeAttr(s.governor.partyKey.toLowerCase()) + '">' +
        KYC.escapeHtml(s.governor.party) + "</span>";
    }
    if (mode === "governor2026") {
      var b = ballot(code);
      return !b ? '<span class="faint">' + (code === "DC" ? "A mayor, not a governor" : "Not covered") + "</span>"
        : b.offices.governor.up ? "Governor's election Nov 3"
        : "No governor's election in 2026" + (b.offices.governor.next
          ? "; next " + KYC.escapeHtml(String(b.offices.governor.next.year)) : "");
    }
    if (OFFICES[mode]) {
      var off = s[mode];
      if (!off) return '<span class="faint">Not listed</span>';
      if (off.disputed) return "Sources disagree";
      if (off.unconfirmed || off.unlisted) return "Not confirmed";
      if (off.vacant) return "Vacant";
      if (off.notMember) return "Not confirmed";
      if (off.none) return "No " + KYC.escapeHtml(OFFICES[mode].word);
      return '<span class="party-' + KYC.escapeAttr(off.partyKey.toLowerCase()) + '">' +
        KYC.escapeHtml(partyName(off.party)) + "</span>";
    }
    if (!s.legislature) return '<span class="faint">Legislature not covered</span>';
    if (mode === "trifecta") {
      return KYC.escapeHtml(s.trifecta === "R" || s.trifecta === "D" ? PARTY[s.trifecta] + " trifecta"
        : s.trifecta === "nonpartisan" ? "Nonpartisan legislature"
        : s.trifecta === "disputed" ? "Sources disagree" : "Divided government");
    }
    return KYC.escapeHtml(control(s.legislature).split(":")[0].replace(/^./, function (c) {
      return c.toUpperCase();
    }));
  }

  /* --------------------------------------------------------------- panel */

  function pills(c) {
    return [["R", "r"], ["D", "d"], ["I", "i"], ["N", "i"]].filter(function (p) {
      return c[p[0]];
    }).map(function (p) {
      return '<span class="party-' + p[1] + '">' + c[p[0]] + " " +
        (p[0] === "N" ? "nonpartisan" : p[0]) + "</span>";
    }).join('<span class="sep">/</span>');
  }

  function chamberRow(c, code, mark) {
    var unlisted = c.seats - c.listed;
    var holds = code === "NE" ? "Elected without party labels"
      : c.majority ? PARTY[c.majority] + " majority of the seats"
      : "No party holds a majority of the seats";
    return '<li class="gov-chamber">' +
      '<span class="gov-chamber-name">' + KYC.escapeHtml(c.title) + "</span>" +
      '<span class="gov-chamber-seats">' + pills(c) + ' <span class="faint">of ' + seatWord(c.seats) +
      (unlisted > 0 ? "; " + unlisted + " with nobody listed" : "") + "</span></span>" +
      // One square per seat, as on the legislature page (KYC.seatStrip).
      (KYC.seatStrip ? KYC.seatStrip(c) : "") +
      '<span class="gov-chamber-holds">' + KYC.escapeHtml(holds) +
      (c.ncsl ? ' <span class="badge badge-warn">NCSL: ' +
        KYC.escapeHtml(c.ncsl === "none" ? "no majority" : PARTY[c.ncsl] + " majority") + "</span>" : "") +
      "</span>" + (mark ? '<span class="gov-chamber-ballot">' + mark + "</span>" : "") + "</li>";
  }

  function source(key) {
    var s = data.sources[key];
    if (!s) return "";
    return '<a href="' + KYC.escapeAttr(s[1]) + '" target="_blank" rel="noopener noreferrer">' +
      KYC.escapeHtml(s[0]) + "</a>" + (s[2] ? " (" + KYC.escapeHtml(KYC.dateWords(s[2])) + ")" : "");
  }

  function link(href, text) {
    return '<a href="' + KYC.escapeAttr(href) + '" target="_blank" rel="noopener noreferrer">' +
      KYC.escapeHtml(text) + "</a>";
  }

  function who(person) {
    return KYC.escapeHtml(person.name) + ' <span class="party-' +
      KYC.escapeAttr(person.partyKey.toLowerCase()) + '">(' + KYC.escapeHtml(partyName(person.party)) +
      ")</span>";
  }

  /** The sentence that says this site has not confirmed a listing on the
   *  office's own site, and why, with that site linked in its words:
   *  *why* is "unreadable" (this site's automated read of it concluded
   *  nothing: a refusal, a timeout, a page drawn by script, or the
   *  attorney general's own page behind it not answering; the cache does
   *  not record which, so the sentence names none and never says the site
   *  refuses scripts, rule 19), "not-named" (it was read and does not name them as *word*),
   *  or unknown. */
  function notConfirmed(url, why, word) {
    if (!url) return "This site has not confirmed it with the office.";
    var site = link(url, "the office's own site");
    return why === "unreadable"
      ? "This site has not confirmed it: this site's automated check could not read " + site + "."
      : why === "not-named"
        ? "This site has not confirmed it: " + site + " does not name them as " +
          KYC.escapeHtml(word) + "."
        : "This site has not confirmed it on " + site + ".";
  }

  /** One statewide officer's row: the holder, or why there is none. */
  function officerRow(kind, off, mark, item, place, open, running) {
    var label = OFFICES[kind].title;
    place = place || "The state";
    // No roster lists a holder: the office on the ballot still lists who
    // is running for it.
    if (!off) {
      return running ? '<li class="gov-officer gov-officer-text">' +
        officeLine("gov-officer-role", label, mark) + running + "</li>" : "";
    }
    // An office the roster lists as missing that is elected on Nov 3 is a
    // new one (Arizona's lieutenant governor, Proposition 131 of 2022).
    var fresh = off.none && item && item.up ? item : null;
    var body;
    if (off.disputed && kind === "ag") {
      body = '<p class="gov-officer-note">The sources disagree: ' +
        off.disputed.map(KYC.escapeHtml).join("; ") + ". Neither is shown as the holder.</p>";
    } else if (off.disputed) {
      body = '<p class="gov-officer-note">The sources disagree: NASS lists ' +
        KYC.escapeHtml(off.disputed[0]) + "; NLGA lists " + KYC.escapeHtml(off.disputed[1]) +
        ". Neither is shown as the holder.</p>";
    } else if (off.unlisted) {
      // Whole sentences, the office's site linked in its words (never a
      // dangling "The office's site.").
      body = '<p class="gov-officer-note">Neither party\'s association of attorneys general lists ' +
        "one for this state, so this site names no holder." +
        (off.office ? " You can look on " + link(off.office, "the office's own site") + "." : "") + "</p>";
    } else if (off.unconfirmed) {
      // Why it is not confirmed is the pipeline's to say: a site this site's
      // read could not read, or a page that was read and does not name them.
      body = '<p class="gov-officer-note">The ' + KYC.escapeHtml(off.listedBy) + " lists " + who(off) +
        " as its member here. " + notConfirmed(off.office, off.unreadable ? "unreadable" : "not-named",
          "attorney general") + "</p>";
    } else if (off.vacant) {
      body = '<p class="gov-officer-note">Vacant, as the National Lieutenant Governors Association lists it.</p>';
    } else if (off.none && kind === "lt" && fresh) {
      body = '<p class="gov-officer-note">No one holds this office yet: ' +
        KYC.escapeHtml(fresh.note) + "." +
        (off.successor ? " First in line to succeed the governor until then: " +
          KYC.escapeHtml(off.successor.title) + " " + who(off.successor) + "." : "") + "</p>";
    } else if (off.none && kind === "lt") {
      body = '<p class="gov-officer-note">' + place + " has no lieutenant governor." +
        (off.successor ? " First in line to succeed the governor: " +
          KYC.escapeHtml(off.successor.title) + " " + who(off.successor) + "." : "") + "</p>";
    } else if (off.none) {
      body = '<p class="gov-officer-note">' + place + " has no secretary of state" +
        (off.electionChief ? "; the lieutenant governor's office runs its elections." : ".") + "</p>";
    } else if (off.notMember) {
      // NASS does not speak for an office that is not its member (rule 55);
      // why the office's own site did not confirm them is the pipeline's.
      body = '<p class="gov-officer-note">The National Association of Secretaries of State lists ' +
        who(off) + " as " + KYC.escapeHtml(off.title.toLowerCase()) + ", but the office is not " +
        "currently a member, so that listing does not speak for it. " +
        notConfirmed(off.website, off.officeRead, off.title.toLowerCase()) + "</p>";
    } else {
      var facts = [off.selection, off.electionChief ? "Chief election official" : "",
        off.listedBy ? "Party: a member of the " + off.listedBy : "",
        // A holder confirmed by hand where the association does not speak
        // for the office: the party is still only the association's listing.
        off.partyFrom ? "Party as the " + off.partyFrom + " lists it" : ""].filter(Boolean);
      var links = [off.website ? link(off.website, "Office") : "", off.office ? link(off.office, "Office") : "",
        off.bio ? link(off.bio, "Biography") : ""].filter(Boolean);
      var contact = [off.phone, off.email, off.address].filter(Boolean).map(KYC.escapeHtml);
      // A holder without a photograph keeps the photograph's column, an
      // empty circle, so the names line up down the card (STATEGOV-13).
      // The smaller copy this site made of a heavy one, or the photograph
      // itself (rule 101: KYC.photoAttrs).
      body = (off.photo ? '<img class="gov-officer-photo" ' + KYC.photoAttrs(off.photo, off.photoCopy) +
          ' alt="" width="40" height="40" loading="lazy" decoding="async">' : NO_PHOTO) +
        '<p class="gov-officer-name">' + who(off) + "</p>" +
        (off.title.toLowerCase() !== label.toLowerCase()
          ? '<p class="faint">' + KYC.escapeHtml(off.title) + "</p>" : "") +
        (facts.length ? '<p class="faint">' + KYC.escapeHtml(facts.join(" · ")) + "</p>" : "") +
        (links.length ? '<p class="gov-links">' + links.join(" · ") + "</p>" : "") +
        // Confirmed from the office's own page, read by hand in a person's
        // browser because this site's automated read concluded nothing (each
        // entry says what its reader saw: overrides.OFFICERS_READ_BY_HAND),
        // or because the association does not speak for it (rule 57's words).
        (off.readByHand ? '<p class="faint gov-by-hand">' + link(off.readByHand.url, "The office's own page") +
          " names them, read by hand on " + KYC.escapeHtml(KYC.dayMonthYear(off.readByHand.read)) +
          ".</p>" : "") +
        (contact.length ? '<p class="faint gov-contact">' + contact.join(" · ") + "</p>" : "");
    }
    var pictured = body.indexOf("gov-officer-photo") !== -1;
    // The office's label carries the ballot mark, above the holder (rule 79).
    return '<li class="gov-officer' + (pictured ? "" : " gov-officer-text") + '">' +
      officeLine("gov-officer-role", label, mark) + (open || "") + body + (running || "") + "</li>";
  }

  /** The federal courts for a state: its district courts and the court of
   *  appeals, each linked to its page; with several districts, where to find
   *  which covers a county (the county pages, 28 U.S.C. 81-131). */
  function federalCourtsBlock(list, code) {
    if (!list || !list.length) return "";
    var districts = list.filter(function (c) { return !/Court of Appeals/.test(c[1]); });
    var appeals = list.filter(function (c) { return /Court of Appeals/.test(c[1]); });
    var a = function (c) {
      return '<a href="' + KYC.escapeAttr(KYC.siteRoot() + "courts/" + c[0] + ".html") + '">' +
        KYC.escapeHtml(c[1].replace(/^U\.S\. (District Court for the |Court of Appeals for the )/, "")) + "</a>";
    };
    return '<p class="panel-subhead">Federal courts</p>' +
      '<p class="gov-federal-courts">' + (districts.length > 1 ? "District courts: " : "District court: ") +
      districts.map(a).join(", ") + (appeals.length ? "; appeals go to the " + appeals.map(a).join(", ") : "") +
      ".</p>" + (districts.length > 1
        ? '<p class="faint">Which district covers a county is on <a href="' +
          KYC.escapeAttr(KYC.siteRoot() + "counties/" + code.toLowerCase() + ".html") +
          '">the county pages</a>, from 28 U.S.C. 81-131.</p>' : "");
  }

  /** A state's court of last resort: who sits on it, as the court lists
   * them, or why its roster could not be read. No party: a justice is not
   * a party's officeholder. */
  function courtBlock(court, code) {
    if (!court) return "";
    var chiefTitle = court.word === "judges"
      ? (/Criminal/.test(court.name) ? "Presiding Judge" : "Chief Judge") : "Chief Justice";
    var about = court.chosen
      ? '<p class="faint">' + KYC.escapeHtml(court.word.charAt(0).toUpperCase() + court.word.slice(1)) +
        " are " + KYC.escapeHtml(court.chosen) + ". Term: " + KYC.escapeHtml(court.term) + ".</p>" : "";
    var body;
    if (court.unreadable) {
      body = '<p class="gov-officer-note">' + KYC.escapeHtml(court.unreadable) +
        ", so its members are not listed here." +
        (court.url ? " You can try " + link(court.url, "the court's own page") + " yourself." : "") + "</p>";
    } else {
      var members = court.members.slice().sort(function (a, b) {
        return (b === court.chief) - (a === court.chief);
      });
      var short = court.seats - members.length;
      // A justice's photograph from the court's own pages (court_photos),
      // credited to the court and linked to the page it was read on.
      var photos = court.photos || {};
      var pictured = members.some(function (name) { return photos[name]; });
      // The court by its whole name: "Supreme Court" alone reads as the
      // nation's.
      var whose = court.name + (code ? " of " + KYC.stateName(code) : "");
      body = '<ul class="gov-court' + (pictured ? " gov-court-pictured" : "") + '">' +
        members.map(function (name) {
          var shot = photos[name];
          return '<li class="gov-court-member' + (pictured ? " gov-pictured" : "") + '">' +
            (!pictured ? ""
              : shot ? '<img class="gov-photo gov-court-photo" ' +
                KYC.photoAttrs(shot.photo, shot.photoCopy) +
                ' alt="" width="32" height="32" loading="lazy" decoding="async">'
              : NO_SMALL_PHOTO) +
            '<span class="gov-court-text"><span class="gov-court-name">' + KYC.escapeHtml(name) +
            (name === court.chief ? ' <span class="faint">' + chiefTitle + "</span>" : "") + "</span>" +
            (shot ? '<span class="gov-photo-credit">' +
              KYC.photoCreditHtml(KYC.copyCredit({ by: whose, page: shot.page }, shot.photo,
                shot.photoCopy)) + "</span>" : "") +
            "</span></li>";
        }).join("") + "</ul>" +
        '<p class="faint">' + members.length + " of " + court.seats + " seats" +
        (short > 0 ? "; " + short + " with nobody listed by the court" : "") +
        (court.chief ? "" : "; the court lists no " + chiefTitle.toLowerCase()) + ". " +
        // A roster file says so before a tap starts a download.
        "From " + link(court.url, /\.pdf(?:[?#]|$)/i.test(court.url) ? "the court's roster (PDF)" : "the court's roster") +
        // Where the list came from, when it is not this week's read of the
        // page: a roster file's own date, or a page read by hand because
        // the site refuses automated reading (rule 57).
        (court.revised ? ", dated " + KYC.escapeHtml(KYC.dayMonthYear(court.revised)) : "") +
        (court.readOn ? ", read by hand on " + KYC.escapeHtml(KYC.dayMonthYear(court.readOn)) +
          ": the court's site refuses automated reading" : "") + ".</p>";
    }
    return '<p class="panel-subhead">' + KYC.escapeHtml(court.name) + "</p>" + about + body +
      (court.note ? '<p class="faint">' + KYC.escapeHtml(court.note) + "</p>" : "");
  }

  /** Everything known about who runs one state, as HTML. *opts.links* adds
   * the links to its legislature and county pages. */
  function render(code, opts) {
    var s = state(code);
    if (!s) {
      return '<p class="faint">' + (code === "DC"
        ? "The District of Columbia has an elected mayor and a council of 13, not a governor and legislature."
        : "No governor is listed for " + KYC.escapeHtml(KYC.stateName(code)) + ".") + "</p>";
    }
    var gov = s.governor;
    var key = KYC.escapeAttr(gov.partyKey.toLowerCase());
    var contact = [gov.phone, gov.address].filter(Boolean).map(KYC.escapeHtml).join(" · ");
    var html = '<div class="gov-card">' +
      (gov.headshot
        ? '<img class="gov-portrait" ' + KYC.photoAttrs(gov.headshot, gov.photoCopy) +
          ' alt="" width="72" height="72" loading="lazy" decoding="async">'
        : "") +
      '<div class="gov-who">' +
      officeLine("gov-role", "Governor", officeMark(code, "governor")) + openSeat(code, "governor") +
      '<p class="gov-name">' + KYC.escapeHtml(gov.name) + "</p>" +
      '<p class="gov-party party-' + key + '">' + KYC.escapeHtml(gov.party) + "</p>" +
      (gov.since ? '<p class="faint">In office since ' + KYC.escapeHtml(gov.since) + "</p>" : "") +
      '<p class="gov-links">' + (gov.website ? link(gov.website, "Governor's office") + " · " : "") +
      link(gov.profile, "NGA biography") + "</p>" +
      (contact ? '<p class="faint gov-contact">' + contact + "</p>" : "") +
      "</div></div>" + candidatesBlock(code, "governor");
    var place = s.territory ? "The territory" : "The state";
    if (s.lt || s.ag || s.sos) {
      html += '<p class="panel-subhead">' + (s.territory ? "Territorial" : "Statewide") +
        ' officers</p><ul class="gov-officers">' +
        ["lt", "ag", "sos"].map(function (k) {
          return officerRow(k, s[k], officeMark(code, k), ballotItem(code, k), place, openSeat(code, k),
            candidatesBlock(code, k));
        }).join("") + "</ul>";
    }
    if (s.territory) {
      // Said, not left out without a word: a territory's legislature, its
      // attorney general and its courts are in none of the sources read here.
      html += '<p class="gov-note">' + KYC.escapeHtml(KYC.possessive(KYC.stateName(code))) + " legislature, " +
        "attorney general and courts are not covered here: this site lists the governor and the " +
        "officers the national associations of lieutenant governors and secretaries of state list.</p>";
    }
    if (s.upper) {
      html += '<p class="panel-subhead">Legislature</p><ul class="gov-chambers">' +
        chamberRow(s.upper, code, chamberMark(code, "upper")) +
        (s.lower ? chamberRow(s.lower, code, chamberMark(code, "lower")) : "") + "</ul>" +
        (KYC.seatKey ? KYC.seatKey([s.upper, s.lower]) : "");
      if (s.note) {
        html += '<p class="gov-note">' + KYC.escapeHtml(s.note) + " " +
          link(s.noteSource, "Legislature's roster") + "</p>";
      }
      html += '<p class="gov-trifecta">' + KYC.escapeHtml(trifectaText(s.trifecta)) + ".</p>";
    }
    html += courtBlock(s.court, code) + courtBlock(s.criminalCourt, code) + federalCourtsBlock(s.federalCourts, code);
    if (opts && opts.links && s.upper) {
      var lower = code.toLowerCase();
      html += '<p class="gov-pages">' +
        '<a class="sidebar-link" href="' + KYC.escapeAttr(KYC.siteRoot() + "legislature/" + lower + ".html") +
        '">Every district and member ›</a> ' +
        '<a class="sidebar-link" href="' + KYC.escapeAttr(KYC.siteRoot() + "counties/" + lower + ".html") +
        '">Counties and local governments ›</a></p>';
    }
    var ncsl = data.sources.ncsl && data.sources.ncsl[2];
    html += '<p class="gov-sources faint">Governor: ' + source("nga") + ". " +
      (s.lt ? "Lieutenant governor: " + source("nlga") + ". " : "") +
      (s.ag ? "Attorney general: the office's own site, with party from " + source("raga") +
        " or " + source("daga") + ". " : "") +
      (s.sos ? "Secretary of state: " + source("nass") + ". " : "") +
      (ballot(code) ? "What is on the Nov 3 ballot: each state's constitution, statutes and " +
        "election office, linked from each mark (checked " +
        KYC.escapeHtml(KYC.dateWords((data.sources.ballot2026 || [])[2] || "")) + "). " +
        (["governor", "lt", "ag", "sos"].some(function (k) { return (ballotItem(code, k) || {}).candidates; })
          ? "The candidates for each office on it: an election office's list, named under the " +
            "office as the document it is. " : "") : "") +
      // Only which party holds each chamber is compared with NCSL; the seat
      // counts are Open States' own (stategov.filled_where_vacant reports
      // where the two counts part).
      (s.upper ? "Seats: " + source("openstates") + "." + (ncsl ? " Which party holds each chamber " +
        "is checked against " + source("ncsl") + "." : "") : "") +
      courtSource(s.court) + courtSource(s.criminalCourt) + photoSources(s) + "</p>";
    return html;
  }

  /** Whose each photograph on the card is (rule 87): the roster's
   *  association, or the office whose page it was taken from. */
  function photoSources(s) {
    var gov = s.governor || {};
    var rows = [["governor", gov.headshot && gov.headshotBy, gov.headshotPage,
      gov.headshot && KYC.copyOf(gov.headshot, gov.photoCopy)]];
    [["lieutenant governor", s.lt], ["attorney general", s.ag], ["secretary of state", s.sos]]
      .forEach(function (pair) {
        var off = pair[1] || {};
        // Only a row that draws its holder's photograph (officerRow's last
        // branch) credits one.
        var drawn = off.photo && !(off.disputed || off.unlisted || off.unconfirmed ||
          off.vacant || off.none || off.notMember);
        rows.push([pair[0], drawn && off.photoBy, off.photoPage,
          drawn && KYC.copyOf(off.photo, off.photoCopy)]);
      });
    // A smaller copy this site made of a heavy one says so, and links the
    // original (rule 101), as the credit line under a portrait does; the
    // note goes if the copy fails and the original is drawn
    // (KYC.retryOriginal removes every note naming that original).
    var said = rows.filter(function (row) { return row[1]; }).map(function (row) {
      var copy = row[3];
      return KYC.escapeHtml(row[0].toLowerCase()) + ", " +
        (row[2] ? link(row[2], row[1]) : KYC.escapeHtml(row[1])) +
        (copy ? '<span class="photo-copy-note" data-copy-of="' + KYC.escapeAttr(copy.of) +
          '"> (a smaller copy made by this site of ' +
          link(copy.of, "the original file" +
            (copy.ofBytes ? " (" + KYC.weightWords(copy.ofBytes) + ")" : "")) + ")</span>"
          : "");
    });
    return said.length ? " Photographs: " + said.join("; ") + "." : "";
  }

  /** A court's line in the list of sources: whose roster, and the day it
   * was read - by the refresh, or by hand. */
  function courtSource(court) {
    var day = court && (court.readOn || court.read);
    if (!day || !court.members) return "";
    return " " + KYC.escapeHtml(court.name) + ": the court's own roster (" +
      (court.readOn ? "read by hand, " : "") + KYC.escapeHtml(KYC.dateWords(day)) + ").";
  }

  /* The empty circle a named officer's row shows without a photograph. */
  var NO_PHOTO = '<span class="gov-officer-photo gov-officer-nophoto" aria-hidden="true"></span>';
  /* The same, for a candidate or a justice in a list where others have one. */
  var NO_SMALL_PHOTO = '<span class="gov-photo gov-photo-none" aria-hidden="true"></span>';

  /* An NGA headshot that fails to load leaves the card without one, not a
   * broken image. Error events do not bubble, so this listens on capture. */
  global.document.addEventListener("error", function (event) {
    var img = event.target;
    // A copy that fails falls back to its original first (rule 101).
    if (img && img.tagName === "IMG" && KYC.retryOriginal(img, event)) return;
    if (img && img.classList && img.classList.contains("gov-officer-photo")) {
      // The row keeps its column, as a holder never pictured does.
      var holder = global.document.createElement("span");
      holder.className = "gov-officer-photo gov-officer-nophoto";
      holder.setAttribute("aria-hidden", "true");
      img.replaceWith(holder);
    } else if (img && img.classList && img.classList.contains("gov-photo")) {
      // A candidate's or a justice's: the circle stays, and so does no credit
      // for a photograph not shown.
      var none = global.document.createElement("span");
      none.className = "gov-photo gov-photo-none";
      none.setAttribute("aria-hidden", "true");
      var credit = img.parentNode && img.parentNode.querySelector(".gov-photo-credit");
      if (credit) credit.remove();
      img.replaceWith(none);
    } else if (img && img.classList && img.classList.contains("gov-portrait")) {
      img.remove();
    }
  }, true);

  /* The directory of legislatures (legislature/index.html): each listed
   * state's chambers, in the words of its state page. The list is plain
   * links without this. */
  function directory() {
    var drawn = [];
    Array.prototype.forEach.call(global.document.querySelectorAll("[data-facts]"), function (cell) {
      var s = state(cell.getAttribute("data-facts"));
      if (!s) return;
      var code = cell.getAttribute("data-facts");
      var chambers = [s.upper, s.lower].filter(Boolean);
      drawn = drawn.concat(chambers);
      cell.innerHTML = '<ul class="gov-chambers">' + chambers.map(function (c) {
        return chamberRow(c, code, "");
      }).join("") + "</ul>" +
        (s.legislature && code !== "NE"
          ? '<p class="faint">' + KYC.escapeHtml(control(s.legislature).replace(/^./, function (c) {
              return c.toUpperCase();
            })) + ".</p>" : "");
    });
    // One key for every strip in the list, above it.
    var list = global.document.querySelector("#legislatureDirectory .directory-list");
    if (list && drawn.length && KYC.seatKey) list.insertAdjacentHTML("beforebegin", KYC.seatKey(drawn));
  }

  KYC.ready(function () {
    if (global.document.getElementById("legislatureDirectory")) directory();
  });

  /** The offices on the state's ballot whose candidates its page lists, in
   *  words ("the attorney general and secretary of state"), or "". The
   *  sentence that says so named "the governor" in states that elect none
   *  (PR #109 review). */
  function listsCandidates(code) {
    var offices = ["governor", "lt", "ag", "sos"].filter(function (k) {
      var item = ballotItem(code, k);
      return !!(item && item.up && item.candidates);
    }).map(function (k) { return BALLOT_WORD[k]; });
    return offices.length ? "the " + andList(offices) : "";
  }

  /* ----------------------------------------------------------- at a glance */

  /** One chamber's seats as one bar: Republicans from the left, Democrats
   *  from the right, others between and a seat with nobody listed outlined
   *  (never "vacant", rule 51), a tick at half where parties hold seats. */
  function chamberBar(c) {
    var unlisted = Math.max(0, c.seats - (c.listed || 0));
    var parts = [["r", c.R], ["i", c.I], ["n", c.N], ["vacant", unlisted], ["d", c.D]]
      .filter(function (p) { return p[1] > 0; });
    var said = [["R", "Republican"], ["D", "Democratic"], ["I", "independent or third-party"],
      ["N", "nonpartisan"]].filter(function (p) { return c[p[0]]; })
      .map(function (p) { return c[p[0]] + " " + p[1]; });
    if (unlisted) said.push(unlisted + " with nobody listed");
    var partisan = !!(c.R || c.D || c.I);
    var label = c.title + ": " + c.seats + " seats, " + said.join(", ") + ".";
    return '<div class="bb-track glance-bar" role="img" aria-label="' + KYC.escapeAttr(label) +
      '" title="' + KYC.escapeAttr(label) + '">' + parts.map(function (p) {
        return '<span class="bb-seg bb-' + p[0] + '" style="width:' + (100 * p[1] / c.seats).toFixed(3) +
          '%"></span>';
      }).join("") + (partisan ? '<span class="bb-half" aria-hidden="true"></span>' : "") + "</div>";
  }

  function glanceChamber(c, code, which) {
    var b = ballot(code);
    var up = b && b.chambers[which];
    return '<li class="glance-chamber"><span class="glance-label">' + KYC.escapeHtml(c.title) + "</span>" +
      chamberBar(c) + '<span class="glance-facts">' + pills(c) +
      (c.seats - c.listed > 0 ? ' <span class="faint">· ' + (c.seats - c.listed) + " nobody listed</span>" : "") +
      (up && up.up ? ' <span class="faint">· ' + (up.up === up.seats ? "all" : up.up + " of " + up.seats) +
        " regular-election seats on the Nov 3, 2026 ballot</span>" : "") + "</span></li>";
  }

  function glanceCourt(court) {
    if (!court) return "";
    var word = court.word || "justices";
    return '<li><span class="glance-label">' + KYC.escapeHtml(court.name) + "</span>" +
      '<span class="glance-facts">' + (court.seats ? court.seats + " " + KYC.escapeHtml(word) : "") +
      (court.chosen ? (court.seats ? ", " : "") + KYC.escapeHtml(court.chosen) : "") +
      (court.term ? "; term: " + KYC.escapeHtml(court.term) : "") + "</span></li>";
  }

  /** The state's government at a glance (VISUALS-28): who holds the
   *  governorship, how each chamber's seats divide and whether one party
   *  holds all three, and the high court's size and how it is chosen,
   *  without a party (a justice is not a party's officeholder). The ballot
   *  mark is the office's, as everywhere (rule 79). Every detail is in the
   *  section under it, with its sources. "" for D.C. and anywhere not
   *  covered. */
  function glance(code) {
    var s = state(code);
    if (!s || !s.governor) return "";
    var gov = s.governor;
    var govUp = ballotItem(code, "governor");
    var exec = '<div class="glance-box"><p class="glance-kind">Executive</p>' +
      '<p class="glance-label">Governor' + (govUp && govUp.up
        ? ' <span class="glance-mark">This office ' + (after() ? "was" : "is") +
          " on the Nov 3, 2026 ballot</span>" : "") + "</p>" +
      // Whether the holder is running, in the section's own words (rule
      // 79): the mark above a governor's name with nothing beside it read
      // as "Brian Kemp is running" (PR #111 review).
      openSeat(code, "governor") +
      '<p class="glance-who">' + KYC.escapeHtml(gov.name) + ' <span class="party-' +
      KYC.escapeAttr(String(gov.partyKey || "i").toLowerCase()) + '">(' + KYC.escapeHtml(gov.party) +
      ")</span></p>" +
      (s.lt || s.ag || s.sos ? '<p class="faint">' + (s.territory ? "Territorial" : "Statewide") +
        " officers below.</p>" : "") + "</div>";
    var leg = '<div class="glance-box"><p class="glance-kind">Legislature</p>' + (s.upper
      ? '<ul class="glance-list">' + glanceChamber(s.upper, code, "upper") +
        (s.lower ? glanceChamber(s.lower, code, "lower") : "") + "</ul>" +
        '<p class="glance-control">' + KYC.escapeHtml(trifectaText(s.trifecta).split(":")[0]) + "</p>" +
        (s.legislature === "coalition" && s.note ? '<p class="faint">' + KYC.escapeHtml(s.note) + "</p>" : "")
      : '<p class="faint">' + (s.territory ? "The territory’s legislature is not covered here."
        : "Not covered here.") + "</p>") + "</div>";
    var courts = s.court || s.criminalCourt
      ? '<ul class="glance-list">' + glanceCourt(s.court) + glanceCourt(s.criminalCourt) + "</ul>"
      : '<p class="faint">Not covered here.</p>';
    var bench = '<div class="glance-box"><p class="glance-kind">' +
      (s.criminalCourt ? "Highest courts" : "Highest court") + "</p>" + courts + "</div>";
    return '<div class="state-glance" role="group" aria-label="' +
      KYC.escapeAttr(KYC.stateName(code) + "’s government at a glance") + '">' + exec + leg + bench + "</div>";
  }

  KYC.stategov = {
    modes: ["governor", "lt", "ag", "sos", "legislature", "trifecta", "governor2026"],
    ballotList: ballotList,
    ballotOffices: ballotOffices,
    listsCandidates: listsCandidates,
    // The office's ballot mark, holder line and candidates, as the state
    // page shows them, for the Your ballot page too (kyc-ballot.js, rule 12).
    ballotOf: ballot,
    officeMark: officeMark,
    openSeat: openSeat,
    candidatesBlock: candidatesBlock,
    titles: TITLES,
    state: state,
    look: look,
    legend: legend,
    badge: badge,
    render: render,
    glance: glance,
  };
})(window);
