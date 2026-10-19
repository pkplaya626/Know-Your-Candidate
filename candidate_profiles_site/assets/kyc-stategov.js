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
   * own constitution, statute or election pages. Who is running for them is
   * not here: no source keyed by an id lists state candidates. */
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
    var offices = ["governor", "lt", "ag", "sos"].filter(function (k) {
      return b.offices[k] && b.offices[k].up;
    }).map(function (k) { return BALLOT_WORD[k]; });
    var chambers = ["upper", "lower"].map(function (w) { return b.chambers[w]; })
      .filter(function (c) { return c && c.up; }).map(seatsUp);
    return [offices.length ? "the " + andList(offices) : "", andList(chambers)]
      .filter(Boolean).join("; ");
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

  /** Whether the holder of an office on the ballot is running for it
   *  (ballot2026.open_seat): "Open seat" where a cited source - the
   *  constitution's term limit or the election office's list of candidates
   *  - says they are not, the list's word where it names them, and, for
   *  every other office on the ballot, that this was not checked. One office
   *  silent beside another that said "Open seat" read as "the holder is
   *  running" (PR #94 review, rule 19). Said only until the election: after
   *  it, the office has a winner. */
  function openSeat(code, key) {
    var b = ballot(code);
    var item = b && b.offices[key];
    var status = item && item.up && item.holderStatus;
    if (!status || after()) return "";
    if (status.why === "unchecked") {
      return '<p class="gov-holder-status gov-holder-unchecked">' + KYC.escapeHtml(status.text) +
        ".</p>";
    }
    return '<p class="gov-holder-status' + (status.why === "listed" ? "" : " gov-open-seat") + '">' +
      (status.why === "listed" ? "" : "Open seat: ") + KYC.escapeHtml(status.text) + " (" +
      link(status.source, status.cite) + ").</p>";
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
      return ballot(code).offices.governor.up
        ? { fill: FILL[gov.partyKey] || FILL.I,
            text: name + ": the governor " +
              (KYC.electionStatus(2026).phase === "post-election" ? "was" : "is") +
              " elected on Nov 3, 2026 (current governor: " + gov.name + ", " + gov.party + ")" }
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

  /** One statewide officer's row: the holder, or why there is none. */
  function officerRow(kind, off, mark, item, place, open) {
    var label = OFFICES[kind].title;
    place = place || "The state";
    if (!off) return "";
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
      body = '<p class="gov-officer-note">Neither party\'s association of attorneys general lists ' +
        "one for this state." + (off.office ? " " + link(off.office, "The office's site") + "." : "") + "</p>";
    } else if (off.unconfirmed) {
      // Why it is not confirmed is the pipeline's to say: a site that refused
      // the request, or a page that was read and does not name them.
      body = '<p class="gov-officer-note">The ' + KYC.escapeHtml(off.listedBy) + " lists " + who(off) +
        " as its member here. " + (off.unreadable
          ? "The office's own site refuses automated requests, so this is not confirmed."
          : "The office's own page does not name them as attorney general, so this is the " +
            "association's listing, not confirmed.") +
        (off.office ? " " + link(off.office, "The office's site") + "." : "") + "</p>";
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
      body = '<p class="gov-officer-note">The National Association of Secretaries of State lists ' +
        who(off) + " as " + KYC.escapeHtml(off.title.toLowerCase()) + ", though the office is not " +
        "currently a NASS member, so this is the association's listing, not confirmed." +
        (off.website ? " " + link(off.website, "The office's site") + "." : "") + "</p>";
    } else {
      var facts = [off.selection, off.electionChief ? "Chief election official" : "",
        off.listedBy ? "Party: a member of the " + off.listedBy : ""].filter(Boolean);
      var links = [off.website ? link(off.website, "Office") : "", off.office ? link(off.office, "Office") : "",
        off.bio ? link(off.bio, "Biography") : ""].filter(Boolean);
      var contact = [off.phone, off.email, off.address].filter(Boolean).map(KYC.escapeHtml);
      // A holder without a photograph keeps the photograph's column, an
      // empty circle, so the names line up down the card (STATEGOV-13).
      body = (off.photo ? '<img class="gov-officer-photo" src="' + KYC.escapeAttr(off.photo) +
          '" alt="" width="40" height="40" loading="lazy" decoding="async">' : NO_PHOTO) +
        '<p class="gov-officer-name">' + who(off) + "</p>" +
        (off.title.toLowerCase() !== label.toLowerCase()
          ? '<p class="faint">' + KYC.escapeHtml(off.title) + "</p>" : "") +
        (facts.length ? '<p class="faint">' + KYC.escapeHtml(facts.join(" · ")) + "</p>" : "") +
        (links.length ? '<p class="gov-links">' + links.join(" · ") + "</p>" : "") +
        (contact.length ? '<p class="faint gov-contact">' + contact.join(" · ") + "</p>" : "");
    }
    var pictured = body.indexOf("gov-officer-photo") !== -1;
    // The office's label carries the ballot mark, above the holder (rule 79).
    return '<li class="gov-officer' + (pictured ? "" : " gov-officer-text") + '">' +
      officeLine("gov-officer-role", label, mark) + (open || "") + body + "</li>";
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
  function courtBlock(court) {
    if (!court) return "";
    var chiefTitle = court.word === "judges"
      ? (/Criminal/.test(court.name) ? "Presiding Judge" : "Chief Judge") : "Chief Justice";
    var about = court.chosen
      ? '<p class="faint">' + KYC.escapeHtml(court.word.charAt(0).toUpperCase() + court.word.slice(1)) +
        " are " + KYC.escapeHtml(court.chosen) + ". Term: " + KYC.escapeHtml(court.term) + ".</p>" : "";
    var body;
    if (court.unreadable) {
      body = '<p class="gov-officer-note">' + KYC.escapeHtml(court.unreadable) +
        ", so its members are not listed here." + (court.url ? " " + link(court.url, "The court's site") + "." : "") +
        "</p>";
    } else {
      var members = court.members.slice().sort(function (a, b) {
        return (b === court.chief) - (a === court.chief);
      });
      var short = court.seats - members.length;
      body = '<ul class="gov-court">' + members.map(function (name) {
        return '<li class="gov-court-member">' + KYC.escapeHtml(name) +
          (name === court.chief ? ' <span class="faint">' + chiefTitle + "</span>" : "") + "</li>";
      }).join("") + "</ul>" +
        '<p class="faint">' + members.length + " of " + court.seats + " seats" +
        (short > 0 ? "; " + short + " with nobody listed by the court" : "") +
        (court.chief ? "" : "; the court lists no " + chiefTitle.toLowerCase()) + ". " +
        // A roster file says so before a tap starts a download.
        link(court.url, /\.pdf(?:[?#]|$)/i.test(court.url) ? "The court's roster (PDF)" : "The court's roster") +
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
        ? '<img class="gov-portrait" src="' + KYC.escapeAttr(gov.headshot) +
          '" alt="" width="72" height="72" loading="lazy" decoding="async">'
        : "") +
      '<div class="gov-who">' +
      officeLine("gov-role", "Governor", officeMark(code, "governor")) + openSeat(code, "governor") +
      '<p class="gov-name">' + KYC.escapeHtml(gov.name) + "</p>" +
      '<p class="gov-party party-' + key + '">' + KYC.escapeHtml(gov.party) + "</p>" +
      (gov.since ? '<p class="faint">In office since ' + KYC.escapeHtml(gov.since) + "</p>" : "") +
      '<p class="gov-links">' + (gov.website ? link(gov.website, "Governor's office") + " · " : "") +
      link(gov.profile, "NGA biography") + "</p>" +
      (contact ? '<p class="faint gov-contact">' + contact + "</p>" : "") +
      "</div></div>";
    var place = s.territory ? "The territory" : "The state";
    if (s.lt || s.ag || s.sos) {
      html += '<p class="panel-subhead">' + (s.territory ? "Territorial" : "Statewide") +
        ' officers</p><ul class="gov-officers">' +
        officerRow("lt", s.lt, officeMark(code, "lt"), ballotItem(code, "lt"), place, openSeat(code, "lt")) +
        officerRow("ag", s.ag, officeMark(code, "ag"), ballotItem(code, "ag"), place, openSeat(code, "ag")) +
        officerRow("sos", s.sos, officeMark(code, "sos"), ballotItem(code, "sos"), place,
          openSeat(code, "sos")) + "</ul>";
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
    html += courtBlock(s.court) + courtBlock(s.criminalCourt) + federalCourtsBlock(s.federalCourts, code);
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
        KYC.escapeHtml(KYC.dateWords((data.sources.ballot2026 || [])[2] || "")) + "). " : "") +
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
    var rows = [["governor", gov.headshot && gov.headshotBy, gov.headshotPage]];
    [["lieutenant governor", s.lt], ["attorney general", s.ag], ["secretary of state", s.sos]]
      .forEach(function (pair) {
        var off = pair[1] || {};
        // Only a row that draws its holder's photograph (officerRow's last
        // branch) credits one.
        var drawn = off.photo && !(off.disputed || off.unlisted || off.unconfirmed ||
          off.vacant || off.none || off.notMember);
        rows.push([pair[0], drawn && off.photoBy, off.photoPage]);
      });
    var said = rows.filter(function (row) { return row[1]; }).map(function (row) {
      return KYC.escapeHtml(row[0].toLowerCase()) + ", " +
        (row[2] ? link(row[2], row[1]) : KYC.escapeHtml(row[1]));
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

  /* An NGA headshot that fails to load leaves the card without one, not a
   * broken image. Error events do not bubble, so this listens on capture. */
  global.document.addEventListener("error", function (event) {
    var img = event.target;
    if (img && img.classList && img.classList.contains("gov-officer-photo")) {
      // The row keeps its column, as a holder never pictured does.
      var holder = global.document.createElement("span");
      holder.className = "gov-officer-photo gov-officer-nophoto";
      holder.setAttribute("aria-hidden", "true");
      img.replaceWith(holder);
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

  KYC.stategov = {
    modes: ["governor", "lt", "ag", "sos", "legislature", "trifecta", "governor2026"],
    ballotList: ballotList,
    titles: TITLES,
    state: state,
    look: look,
    legend: legend,
    badge: badge,
    render: render,
  };
})(window);
