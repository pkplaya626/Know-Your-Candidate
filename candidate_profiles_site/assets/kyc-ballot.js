/* Know Your Candidate - what is on a reader's ballot, and how to vote.
 *
 * Four things, each said once for every page that needs it (rule 12):
 *
 * - The voting block of every state page: the jurisdiction's own links and
 *   key dates, a date said passed on the reader's own calendar day (rule
 *   84). The Your ballot page shows the same dates.
 * - Whether a state legislative chamber's seats, and one district's seat,
 *   are on the November ballot, from the state's own record
 *   (kyc/legislature.seats_up): the legislature pages and the Your ballot
 *   page say it in the same words.
 * - The statewide questions on the ballot, in their official words (rule
 *   95): the state pages and the Your ballot page list them alike.
 * - The Your ballot page itself (ballot.html, rule 92): every contest on one
 *   reader's November ballot that this site can name, from a ZIP code or a
 *   location, looked up on the device by "Find who represents you"
 *   (kyc-findrep.js). "Who is on my ballot" is not "who represents me"
 *   (rule 27): the page names who is running, never who holds a seat but
 *   as a race's own words do.
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;

  /* ============================================================ voting */

  /* How to vote here: the state's own pages, as the secretaries of state's
   * association lists them (kyc/voting.py). Nothing on the site said how,
   * when or where to vote. No date is typed here: the dates are the
   * jurisdiction's own, from the pipeline (kyc/voting_dates.py, datesFor).
   * NASS covers the 50 states and D.C.; a territory's links are its own
   * office's (voting.TERRITORY_LINKS). */
  var VOTING = [
    ["status", "Check your registration"],
    ["polling", "Find your polling place"],
    ["sample", "See a sample ballot"],
    ["absentee", "Vote absentee or early"],
    // Before the form, so the deadline is reached first (PR #94 review).
    // Only where the jurisdiction's own record does not say when its
    // registration closes (voting.for_page): a compiled table beside the
    // state's own dates is a second source that may disagree (rule 53).
    ["deadlines", "Registration deadlines (vote.gov)"],
    ["register", "Register to vote"],
    ["info", "Election information"],
    ["results", "Official results"],
  ];
  // A place's own name where its short name is not one (rule 75).
  var PLACE = {
    DC: "the District of Columbia",
    MP: "the Northern Mariana Islands",
    VI: "the U.S. Virgin Islands",
  };

  // One possessive for every page, as kyc/pages.py writes it (rules 12 and
  // 75): "Virgin Islands'", "Texas's" - this file's own copy wrote "Texas'".
  var possessive = KYC.possessive;

  /** "“A”, “B” and “C”": the links of *kinds*, by the words on them. */
  function quoted(kinds, labels) {
    var words = VOTING.filter(function (v) { return kinds.indexOf(v[0]) !== -1; })
      .map(function (v) { return "“" + KYC.escapeHtml(labels[v[0]] || v[1]) + "”"; });
    return words.length < 2 ? words.join("")
      : words.slice(0, -1).join(", ") + " and " + words[words.length - 1];
  }

  /** Today's date as "YYYY-MM-DD", on the reader's clock. */
  function isoToday() {
    var now = new Date();
    return now.getFullYear() + "-" + ("0" + (now.getMonth() + 1)).slice(-2) + "-" +
      ("0" + now.getDate()).slice(-2);
  }
  var MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
                     "August", "September", "October", "November", "December"];

  function longDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
    return m ? MONTH_NAMES[+m[2] - 1] + " " + (+m[3]) + ", " + m[1] : "";
  }

  function outLink(href, text) {
    return '<a href="' + KYC.escapeAttr(href) + '" target="_blank" rel="noopener noreferrer">' +
      KYC.escapeHtml(text) + "</a>";
  }

  var SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                      "Nov", "Dec"];

  function shortDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
    return m ? SHORT_MONTHS[+m[2] - 1] + " " + (+m[3]) : "";
  }

  /* The jurisdiction's own dates (kyc/voting_dates.py), as its election
   * office gives them, each line linked to the page that says it. Seventeen
   * days out the page offered "Register to vote" in Georgia twelve days
   * after its deadline and gave no early-voting or mail-ballot date
   * (audit 2026-10-17, STATEGOV-11, PERSONA-03, FRESHNESS-11). Which dates
   * are words and which a reader's calendar day has passed is the only
   * thing decided here, on the reader's own clock, as KYC.electionStatus
   * counts days. From the day after the election, only what still matters
   * stays: a mailed ballot that may still arrive, a runoff. Once a date has
   * passed, a line says what the date was, never what will happen on it
   * (rule 63). */
  function datesFor(all, code) {
    var dates = all._dates || {};
    var mine = (dates.states || {})[code];
    if (!mine) return null;
    var today = isoToday();
    var election = dates.election || "2026-11-03";
    var after = today > election;
    var lines = (mine.lines || []).filter(function (l) {
      if (!after) return true;
      if (!l.keep) return false;
      // A ballot that can no longer arrive is no longer news; a runoff's
      // date is said in the past tense once it has gone.
      return l.k === "runoff" || !(l.d < today);
    });
    return { mine: mine, lines: lines, today: today, election: election, after: after };
  }

  /** Where a line's date stands on the reader's calendar. */
  function when(line, today) {
    if (!line.d) return null;
    if (line.e) {
      if (today > line.e) return { cls: "is-past", word: "Ended" };
      if (today >= line.d) return { cls: "is-now", word: "Under way" };
      return null;
    }
    if (today > line.d) return { cls: "is-past", word: "Passed" };
    if (today === line.d) return { cls: "is-now", word: "Today" };
    return null;
  }

  function lineSources(mine, line) {
    var links = (line.src || []).map(function (i) {
      return mine.urls[i] ? outLink(mine.urls[i], mine.labels[i] || mine.urls[i]) : "";
    }).filter(Boolean);
    // Semicolons between sources: an archived page's label carries its own
    // date in brackets, and commas ran one label into the next.
    return links.length ? ' <span class="vote-src">(' + links.join("; ") + ")</span>" : "";
  }

  /* The sentence a reader came for: can I still register for November 3?
   * Said only until Election Day, and only from the record's own dates.
   * Where a reader can register and vote at once, a deadline before
   * Election Day is the regular one, never "the last day" and never
   * "open until": Illinois's page told readers on October 18 that it was
   * the last day to register, with grace-period registration running to
   * November 3 (PR #102 review). Where the record does not say whether
   * there is same-day registration, the deadline is said and nothing
   * more. */
  function registrationLead(info, place) {
    var reg = info.mine.register;
    if (!reg || info.after || !reg.by) return "";
    var day = longDate(reg.by);
    var t = info.today;
    var how = " (" + reg.how + ")";
    var text;
    if (reg.sameDay) {
      var until = reg.through ? ", until " + longDate(reg.through) : "";
      var then = "you can still register and vote at the same time" + until +
        "; where and when " + place + " offers it is below.";
      if (reg.by >= info.election) {
        text = t < reg.by ? "You can still register for November 3, through Election Day" + how + "."
          : "Today, Election Day, you can still register" + how + ".";
      } else if (reg.through && t > reg.through) {
        text = "The regular deadline to register for November 3 was " + day +
          ", and same-day registration ended on " + longDate(reg.through) + ".";
      } else if (t < reg.by) {
        text = "The regular deadline to register for November 3 is " + day + how + "; after it " + then;
      } else if (t === reg.by) {
        text = "Today is the regular deadline to register for November 3" + how + "; after it " + then;
      } else {
        text = "The regular deadline to register for November 3 was " + day + "; " + then;
      }
    } else if (reg.sameDay === false) {
      text = t < reg.by ? "Registration for November 3 is open until " + day + how + "."
        : t === reg.by ? "Today is the last day to register for November 3" + how + "."
        : "Registration for November 3 closed on " + day + ".";
    } else {
      text = t < reg.by ? "The deadline to register for November 3 is " + day + how + "."
        : t === reg.by ? "Today is the deadline to register for November 3" + how + "."
        : "The deadline to register for November 3 was " + day + ".";
    }
    return '<p class="vote-lead">' + KYC.escapeHtml(text) + "</p>";
  }

  /* What the "Register to vote" button adds once registration for
   * November 3 has closed, or "" while it is open. Only where the record
   * says there is no same-day route, or that the route has ended: New
   * York's record says neither, and its lead only gives the deadline. */
  function registrationClosed(info) {
    var reg = info && info.mine.register;
    if (!reg || !reg.by || info.after) return "";
    if (reg.sameDay === false && info.today > reg.by) return "closed for Nov 3 on " + shortDate(reg.by);
    if (reg.sameDay && reg.through && info.today > reg.through) {
      return "same-day registration ended " + shortDate(reg.through);
    }
    return "";
  }

  /** A button's label with a note: "Registration package (PDF; closed ...)". */
  function withNote(label, note) {
    if (!note) return label;
    return /\)$/.test(label) ? label.slice(0, -1) + "; " + note + ")" : label + " (" + note + ")";
  }

  /* VISUALS-25: the dates as a strip, in order, Election Day among them and
   * a mark for today. Page text, never SVG text (rule 46); it wraps on a
   * phone rather than scrolling the page sideways. */
  function calendarStrip(info) {
    var items = info.lines.filter(function (l) { return l.d; }).map(function (l) {
      return { d: l.d, e: l.e, s: l.s, sp: l.sp, line: l };
    });
    if (!items.length) return "";
    items.push({ d: info.election, s: "Election Day", election: true });
    items.sort(function (a, b) { return a.d < b.d ? -1 : a.d > b.d ? 1 : 0; });
    var html = [];
    var marked = false;
    // Today has a mark of its own wherever it falls, first included (the
    // strip of a state whose first date was tomorrow had none), unless a
    // date of the strip is today itself.
    var onToday = items.some(function (item) { return item.d === info.today && !item.e; });
    function today() {
      marked = true;
      html.push('<li class="vote-cal-item is-today" aria-label="Today, ' +
        KYC.escapeAttr(longDate(info.today)) + '"><span class="vote-cal-date">' +
        KYC.escapeHtml(shortDate(info.today)) + '</span><span class="vote-cal-label">Today</span></li>');
    }
    items.forEach(function (item) {
      var end = item.e || item.d;
      if (!marked && !onToday && info.today < item.d) today();
      var past = end < info.today;
      var cls = past ? " is-past"
        : (item.d <= info.today && info.today <= end ? " is-now" : "");
      var date = shortDate(item.d) + (item.e ? "–" + shortDate(item.e).replace(
        shortDate(item.d).split(" ")[0] + " ", "") : "");
      // A date gone is named for what it was ("Runoff date"), never what
      // may still happen on it ("Runoff, if needed").
      var label = past && item.sp ? item.sp : item.s;
      html.push('<li class="vote-cal-item' + cls + (item.election ? " is-election" : "") + '">' +
        '<span class="vote-cal-date">' + KYC.escapeHtml(date) + "</span>" +
        '<span class="vote-cal-label">' + KYC.escapeHtml(label || "") + "</span></li>");
    });
    if (!marked && !onToday) today();
    return '<ol class="vote-cal" aria-label="Key dates, in order">' + html.join("") + "</ol>";
  }

  function keyDates(info) {
    if (!info || !info.lines.length) return "";
    var today = info.today;
    return '<ul class="vote-dates">' + info.lines.map(function (l) {
      var status = when(l, today);
      var past = l.d && (l.e || l.d) < today;
      var words = past && l.p ? l.p : l.t;
      var date = l.d ? (l.e ? longDate(l.d).replace(/, \d{4}$/, "") + " – " + longDate(l.e)
                            : longDate(l.d)) : "";
      return '<li data-kind="' + KYC.escapeAttr(l.k) + '">' +
        (date ? "<strong>" + KYC.escapeHtml(date) + ".</strong> " : "") +
        KYC.escapeHtml(words) + "." +
        (status && !(past && l.p) ? ' <span class="vote-when ' + status.cls + '">' +
          KYC.escapeHtml(status.word) + "</span>" : "") +
        lineSources(info.mine, l) + "</li>";
    }).join("") + "</ul>";
  }

  /** Where the block's links come from, said link by link from the
   *  pipeline's record of each (voting.effective): "the first four from
   *  NASS" credited NASS with eleven states' sample-ballot pages, Wyoming's
   *  results page and D.C.'s mail-ballot page (PR #94 review). And
   *  "each link opened" is said only when every link was found live. */
  function votingSources(all, code, links, labels, place) {
    var shown = VOTING.map(function (v) { return v[0]; }).filter(function (k) { return links[k]; });
    var nass = ((all._nass || {})[code] || []).filter(function (k) { return links[k]; });
    var own = shown.filter(function (k) { return nass.indexOf(k) === -1 && k !== "deadlines"; });
    var office = (all._territories || {})[code];
    var out = [];
    if (nass.length) {
      out.push(quoted(nass, labels) + (nass.length === 1 ? " is " : " are ") +
        KYC.escapeHtml(possessive(place)) + " own official page" + (nass.length === 1 ? "" : "s") +
        " as the National Association of Secretaries of State’s " +
        outLink(all._source || "https://www.nass.org/can-I-vote", "Can I Vote") +
        (all._listed ? " listed " + (nass.length === 1 ? "it" : "them") + " on " +
          KYC.escapeHtml(all._listed) : " lists " + (nass.length === 1 ? "it" : "them")) + ".");
    }
    if (own.length) {
      out.push(quoted(own, labels) + (own.length === 1 ? " is " : " are ") +
        (office ? "the " + outLink(office.url, office.name) + (/s$/.test(office.name) ? "'" : "'s") +
          " own page" + (own.length === 1 ? "" : "s") +
          "; the National Association of Secretaries of State lists no territory."
        : KYC.escapeHtml(possessive(place)) + " election office's own page" +
          (own.length === 1 ? "" : "s") + ", as its site links " + (own.length === 1 ? "it." : "them.")));
    }
    if (links.deadlines) {
      // The deadlines are vote.gov's to state, never typed here, and the
      // page never calls one passed (STATEGOV-11, PERSONA-03).
      out.push("“" + KYC.escapeHtml(labels.deadlines || "Registration deadlines (vote.gov)") +
        "” is the page for " + KYC.escapeHtml(place) + " on vote.gov, the federal government's " +
        "voting site, which gives the registration rules there, deadlines included.");
    }
    if (all._opened) {
      // A link refused or unanswered concludes nothing (rule 8): said as
      // unconfirmed, never as broken, and never counted as opened.
      var missed = ((all._unreached || {})[code] || []).filter(function (k) { return links[k]; });
      out.push(missed.length
        ? "Links checked " + KYC.escapeHtml(all._opened) + "; " + quoted(missed, labels) +
          " could not be confirmed by this site's automated check that day."
        : "Each link opened " + KYC.escapeHtml(all._opened) + ".");
    }
    return out.join(" ");
  }

  /** The election office's own line that no election is held on November
   *  3 there (voting_dates, "noElection"), or null. */
  function noElection(code) {
    var mine = (((KYC.meta().voting || {})._dates || {}).states || {})[code];
    return ((mine && mine.lines) || []).filter(function (l) { return l.k === "none"; })[0] || null;
  }

  /** What the way to this page says it holds, wherever it is offered. */
  var ENTRY_WORDS = "Every contest on your ballot that this site can name, from your ZIP code " +
    "or location: Congress, statewide offices and your state legislative seats.";

  /** The way from a state's voting block to the reader's whole ballot
   *  (ballot.html), which needs their ZIP code or location to name their
   *  districts. */
  function ballotEntry(code) {
    // A place whose own record says it holds no election on November 3
    // (Puerto Rico) has no ballot to see.
    if (noElection(code)) return "";
    var past = KYC.electionStatus((KYC.meta().election || {}).year || 2026).phase === "post-election";
    return '<p class="vote-ballot"><a class="btn" data-ballot-entry href="' +
      KYC.escapeAttr(KYC.siteRoot() + "ballot.html") + '">' + KYC.icon("ballot") +
      (past ? " See what was on your ballot" : " See everything on your ballot") + "</a> " +
      // The home page's hero says the same words (index.html .intro-ballot;
      // test_site checks the two agree): one link, one description.
      '<span class="field-note">' + ENTRY_WORDS + "</span></p>";
  }

  function votingBlock(code, name) {
    var all = KYC.meta().voting || {};
    var links = all[code];
    if (!links) return "";
    // A per-state label where NASS's kind does not fit the state: North
    // Dakota does not register voters (overrides.VOTING_LINKS); a
    // territory's office words its own pages (voting.TERRITORY_LINKS).
    var labels = (all._labels || {})[code] || {};
    var place = PLACE[code] || name;
    var info = datesFor(all, code);
    var closed = registrationClosed(info);
    return '<section class="state-section vote-box" id="voting" aria-labelledby="votingHead">' +
      '<h2 class="state-heading" id="votingHead">' + KYC.icon("vote") + " Voting in " +
        KYC.escapeHtml(place) + "</h2>" +
      (info ? registrationLead(info, place) + calendarStrip(info) : "") +
      ballotEntry(code) +
      '<p class="state-links">' + VOTING.filter(function (v) { return links[v[0]]; }).map(function (v) {
        var label = labels[v[0]] || v[1];
        // Never offered as open once it has closed (STATEGOV-11): the
        // form still registers a reader for later elections.
        if (v[0] === "register") label = withNote(label, closed);
        return '<a class="btn" target="_blank" rel="noopener noreferrer" href="' +
          KYC.escapeAttr(links[v[0]]) + '" data-kind="' + KYC.escapeAttr(v[0]) + '"' +
          (v[0] === "register" && closed ? ' data-closed="true"' : "") + ">" +
          KYC.icon("link") + " " + KYC.escapeHtml(label) + "</a>";
      }).join(" ") + "</p>" +
      keyDates(info) +
      '<p class="state-note">' + datesNote(all, info) + votingSources(all, code, links, labels, place) +
        " Hours and ID rules are on the election office's pages.</p>" +
      "</section>";
  }

  /** Where the dates come from, said once under them. */
  function datesNote(all, info) {
    if (!info || !info.lines.length) return "";
    var d = all._dates || {};
    // Not every date is printed as a date: where the office or its law
    // gives a rule ("15 days before the election", Guam's runoff "on the
    // fourteenth day" after it), the date is that rule counted on the 2026
    // calendar, and the page says so (PR #102 review).
    return "Each date is from the election office's own page or the law, linked beside it" +
      (d.read ? ", read on " + KYC.escapeHtml(d.read) : "") +
      (d.checked ? " and checked again on " + KYC.escapeHtml(d.checked) : "") +
      // A source read later than the record (Nevada's Secretary of State's
      // page, read by hand) says its own day (PR #140 review).
      ((info.mine || {}).reread || []).map(function (r) {
        return " (" + KYC.escapeHtml(r.labels.join(" and ")) + " read on " + KYC.escapeHtml(r.d) + ")";
      }).join("") +
      "; where the source gives a rule, such as “15 days before the election”, the date " +
      "is that rule counted on the 2026 calendar. Whether a date has passed is counted on your " +
      "device's calendar. ";
  }

  /* ============================================ the legislature's seats */

  function link(href, text) {
    return '<a href="' + KYC.escapeAttr(href) + '" target="_blank" rel="noopener noreferrer">' +
      KYC.escapeHtml(text) + "</a>";
  }

  function andList(list) {
    return list.length < 2 ? list.join("")
      : list.slice(0, -1).join(", ") + " and " + list[list.length - 1];
  }

  /* The legislature pages load no people files, so the year is the one the
   * record is of: these seats are the 2026 ballot's (kyc/ballot2026.py). */
  function after() {
    return KYC.electionStatus(2026).phase === "post-election";
  }

  function nextLine(b) {
    if (!b.next) return "";
    return " " + link(b.next.source, "Next regular election: " + (b.next.month || "November") +
      " " + b.next.year);
  }

  function plainName(name) { return String(name).replace(/^0+(?=\d)/, ""); }

  /** What the state's record says beyond "all" or "none", and beyond the
   *  term the next line states: "all" alone says nothing the count did not
   *  ("The state's record: all." read on Connecticut's page), and "all
   *  (2-year terms)" repeated the term line under it. */
  function basisText(c) {
    // "all 56 districts" says no more than the count beside it.
    // A list after the count ("11 districts: 2, 8, 9, ...", Nevada's
    // Senate) names the districts; its count dropped, it read "The state's
    // record: : 2, 8" (PR #140 review).
    var t = String(c.ballot.basis || "").replace(/^(none regular|none|all)\b:?\s*/i, "")
      .replace(/^\d+ districts:\s*/i, "Districts ")
      .replace(/^\d+ districts\b\s*/i, "").trim();
    if (c.termYears) {
      var n = String(c.termYears);
      t = t.replace(new RegExp("\\s*\\(" + n + "-year terms\\)"), "")
        .replace(new RegExp(",\\s*" + n + "-year terms\\b"), "")
        .replace(new RegExp("\\b" + n + "-year terms,?\\s*"), "");
    }
    // "25 of 50 (staggered 4-year terms)" less its term is "(staggered)",
    // never "(staggered )".
    t = t.replace(/^\((.*)\)$/, "$1").replace(/\(\s*\)/g, "").replace(/\s+\)/g, ")")
      .replace(/^[\s,;]+|[\s,;]+$/g, "");
    return t ? t.charAt(0).toUpperCase() + t.slice(1) + "." : "";
  }

  /** The chamber's districts with an election for the rest of a term
   *  (kyc/legislature.specials), from the same record. */
  function specialLine(c) {
    var list = (c.specials || []).map(plainName);
    if (!list.length) return "";
    return (list.length === 1 ? "District " : "Districts ") + andList(list) + (c.ballot.up ? " also " : " ") +
      (list.length === 1 ? (after() ? "had" : "has") : (after() ? "had" : "have")) +
      " a special election for the rest of a term on the Nov 3, 2026 ballot.";
  }

  /** The chamber's seats on the November 3 ballot, in the state's own
   *  record's words, linked to it: the regular elections, then any special
   *  election for the rest of a term. */
  function chamberBallot(c) {
    var b = c.ballot;
    if (!b) return "";
    var was = after() ? "were" : "are";
    var head = !b.up ? "No regular elections for the " + c.title + " in 2026."
      : b.up === b.seats ? "All " + b.seats + " seats " + was + " on the Nov 3, 2026 ballot."
      : b.up + " of the " + b.seats + " seats " + was + " on the Nov 3, 2026 ballot.";
    var more = basisText(c);
    var special = specialLine(c);
    return '<p class="leg-ballot">' + KYC.escapeHtml(head) +
      (special ? " " + KYC.escapeHtml(special) : "") +
      (more ? ' <span class="faint">' + KYC.escapeHtml("The state's record: " + more) + "</span>" : "") +
      " " + link(b.source, "Source") + (!b.up ? nextLine(b) : "") + "</p>" +
      (c.termYears ? '<p class="leg-term">Members serve ' + KYC.escapeHtml(String(c.termYears)) +
        "-year terms, as the state's record says.</p>" : "");
  }

  /** Whether district *id*'s seat in chamber *c* (a legislature file's) is
   *  on the ballot: true, false, or null where the state's record does not
   *  say which districts' seats are up (Montana's "25 of 50"). A district
   *  the record names for a special election is on it (rule 74). */
  function seatUp(c, id) {
    var d = c && c.ballot && c.districts[id];
    if (!d) return null;
    if (d.special) return true;
    return d.up === undefined ? null : !!d.up;
  }

  /** One district's seat on the ballot, where the record names it. A
   *  district the record names for a special election is on the ballot,
   *  and its panel says so first (rule 74; PR #96 review: Kansas Senate 24
   *  read "not up for regular election" over a seat on the ballot). */
  /** The words for one district's regular election, by how its seats
   *  stand (kyc/legislature.district_seats): Arizona's House elects two a
   *  district, West Virginia's Senate one of each district's two, and
   *  "This seat" fitted neither (PR #115 review). */
  function regularWords(c, up) {
    var past = after();
    var is = past ? "was" : "is", are = past ? "were" : "are";
    var kind = c.districtSeats;
    if (kind === "one") {
      return up ? "This seat " + is + " on the Nov 3, 2026 ballot."
        : "This seat " + is + " not up for regular election in 2026.";
    }
    if (kind === "several" || (kind === "one-of-several" && !up)) {
      return up ? "This district's seats " + are + " on the Nov 3, 2026 ballot."
        : "This district's seats " + are + " not up for regular election in 2026.";
    }
    if (kind === "one-of-several") return "One of this district's seats " + is + " on the Nov 3, 2026 ballot.";
    return up ? "This district's regular election " + is + " on the Nov 3, 2026 ballot."
      : "This district " + (past ? "had" : "has") + " no regular election in 2026.";
  }

  function seatBallot(c, id) {
    var d = c.districts[id];
    if (!c.ballot || !d || (d.up === undefined && !d.special)) return chamberBallot(c);
    var is = after() ? "was" : "is";
    var text = d.special
      ? "A special election for the rest of a term in this district " + is + " on the Nov 3, 2026 ballot." +
        (d.up === true ? " So " + is + " its regular election."
          : d.up === false ? " It " + (after() ? "had" : "has") + " no regular election in 2026." : "")
      : regularWords(c, !!d.up);
    var more = basisText(c);
    return '<p class="leg-ballot">' + KYC.escapeHtml(text) +
      (more ? ' <span class="faint">' + KYC.escapeHtml("The state's record: " + more) + "</span>" : "") +
      " " + link(c.ballot.source, "Source") + (!d.up && !d.special ? nextLine(c.ballot) : "") + "</p>";
  }

  /* What a state's ballot may hold beyond what this site lists, in the
   * state page's words and this page's alike. D.C. has no governor or
   * legislature; its own offices, as the D.C. Board of Elections lists them
   * for 2026 (candidate list, July 2026). */
  var UNLISTED = "special elections for vacant seats, other statewide, judicial and local " +
    "contests, and local ballot questions, which this site does not list";

  function dcContests(past) {
    return "Your ballot may also " + (past ? "have held" : "hold") +
      " the District's own contests, such as for mayor, attorney " +
      "general, the D.C. Council, the State Board of Education and Advisory Neighborhood " +
      "Commissions, which this site does not list (" +
      '<a href="https://www.dcboe.org/elections/2026-elections" target="_blank" ' +
      'rel="noopener noreferrer">D.C. Board of Elections</a>).';
  }

  var TERRITORY_UNLISTED = "Your ballot may also hold territorial and local contests, such as for " +
    "the legislature, which this site does not list.";

  /* ====================================================== the questions */

  /* The statewide questions on the November 3 ballot (rule 95), from each
   * election office's own list (kyc/ballot_measures.py, data/measures.js).
   * Every state page said the ballot also held "ballot measures, which this
   * site does not list" (audit 2026-10-17, RACES-16, STATEGOV-14,
   * PERSONA-08). One implementation for the state pages and Your ballot
   * (rule 12). A measure is said in its official words only - designation,
   * title, text, kind and who put it on the ballot - and this site never
   * says what a yes or a no vote does; nothing is coloured by side. "None"
   * is said only where the record quotes what shows it; where no official
   * list was found the page says so and sends the reader to the election
   * office, never "none" (rule 19). From the day after Election Day the
   * questions are in the past tense with the state's own results: this site
   * reads no result of a ballot question. */

  // Text longer than this is folded after its first lines.
  var FOLD_AT = 320;

  function measuresOf(code) {
    var all = global.kycMeasures;
    return all && all[code] ? all[code] : null;
  }

  /** "Statewide" is a state's word: the District's and a territory's are
   *  their own (rule 75). */
  function questionScope(code) {
    if (code === "DC") return "District-wide";
    return stateInfo(code).territory ? "Territory-wide" : "Statewide";
  }

  /** The section's name, for its heading and its jump chip alike (rule 75). */
  function measuresName(code) {
    return questionScope(code) + " questions";
  }

  /** The past tense says there were questions, so only a record that lists
   *  some takes it: under "that were on the ballot", "No statewide question
   *  was on it" and "not found" contradicted their own heading (PR #120
   *  review). */
  function measuresHeading(code) {
    var rec = measuresOf(code);
    return measuresName(code) + (held() && rec && rec.has === true
      ? " that were on the Nov 3, 2026 ballot" : " on the Nov 3, 2026 ballot");
  }

  /** The official text, paragraph by paragraph, folded after its first
   *  lines where it is long; printed whole. */
  function measureText(code, m, i) {
    var id = "measure-text-" + code + "-" + i;
    var long = m.text.length > FOLD_AT;
    var paras = m.text.split(/\n+/).map(function (p) {
      return "<p>" + esc(p) + "</p>";
    }).join("");
    return '<blockquote class="measure-text' + (long ? " is-folded" : "") + '" id="' +
      KYC.escapeAttr(id) + '" cite="' + KYC.escapeAttr(m.source) + '">' + paras + "</blockquote>" +
      (long ? '<button type="button" class="link-button measure-more" data-measure-more ' +
        'aria-expanded="false" aria-controls="' + KYC.escapeAttr(id) + '">Read the whole text</button>' : "");
  }

  // After the election the heading and the lead carry the tense; each item
  // does not repeat it (California's fourteen did).
  function measureItem(code, m, i, level, read) {
    var kind = [m.kind, m.origin ? "Put on the ballot by " + m.origin
      : "Who put it on the ballot is not recorded here"].filter(Boolean).join(". ");
    var notes = [];
    if (m.cut) notes.push("Cut where marked “…”; the whole text is at its source.");
    if (m.note) notes.push(m.note);
    var links = [];
    if (m.guide) links.push(link(m.guide, "Its page in the voter guide"));
    links.push(link(m.source, "Source") + " (read " + esc(KYC.dateWords(read)) + ")");
    // Addressed by its place in the record, so the home search links the
    // question itself (kyc-search.js, rule 97).
    return '<li class="measure" id="' + KYC.escapeAttr("measure-" + code + "-" + i) + '">' +
      "<h" + level + ' class="measure-name">' + esc(m.designation) +
        (m.title ? ' <span class="measure-title">' + esc(m.title) + "</span>" : "") +
      "</h" + level + ">" +
      '<p class="measure-kind">' + esc(kind) + ".</p>" +
      measureText(code, m, i) +
      (notes.length ? '<p class="measure-note">' + esc(notes.join(" ")) + "</p>" : "") +
      '<p class="measure-links">' + links.join(" &middot; ") + "</p>" +
      "</li>";
  }

  /** What a "none" rests on, in the record's words, with its source. A
   *  ballot is named as the one read - often one county's - never "the
   *  official sample ballots" as though every one had been (PR #120
   *  review); a statewide question is printed on every ballot, which is
   *  what makes one enough. */
  function noneLine(code, rec) {
    var scope = questionScope(code).toLowerCase();
    var read = esc(KYC.dateWords(rec.read));
    var src = rec.list ? link(rec.list.url, rec.list.title) + ", read " + read : "";
    var basis = (rec.none || {}).from;
    var words = (rec.none || {}).words;
    if (basis === "statement") {
      return "The " + esc(rec.by) + " says: “" + esc(words) + "” (" + src + ").";
    }
    if (basis === "list") {
      return "The " + esc(rec.by) + "'s list of the questions on its ballots holds none that " +
        "is " + scope + ": " + src + ". A " + scope + " question would be on every ballot.";
    }
    return "This site read " + (rec.list ? link(rec.list.url, rec.list.title) : "the official " +
      "sample ballot") + " on " + read + ", and it prints no " + scope + " question. A " + scope +
      " question would be printed on every ballot.";
  }

  /** Where the questions not listed here are: the sample ballot the
   *  election office links, or its pages. "A county's, a city's or a school
   *  district's" is a state's: the District and the territories hold
   *  neither counties nor such questions, and are told only where the
   *  whole ballot is (rule 75). */
  function localLine(code, others) {
    var sample = sampleLink(code);
    var whole = sample ? "The election office's sample ballot shows every question on it: " +
      sample + "." : "";
    if (questionScope(code) !== "Statewide") {
      return whole ? '<p class="measures-local">' + whole + "</p>" : "";
    }
    return '<p class="measures-local">' + (others ? "Other local" : "Local") + " questions - a " +
      "county's, a city's or a school district's - are not listed here." + (whole ? " " + whole
        : " The election office's own pages are under " + '<a href="' +
          KYC.escapeAttr(KYC.stateUrl(code) + "#voting") + '">how to vote in ' +
          esc(placeName(code)) + "</a>.") + "</p>";
  }

  /** The statewide questions of *code*, as HTML: the lead, the list, and
   *  what is not listed; "" where nothing is recorded or the place holds no
   *  election that day. *opts.level*: the heading level of each measure. */
  function measuresBody(code, opts) {
    var rec = measuresOf(code);
    if (!rec || noElection(code)) return "";
    var level = (opts && opts.level) || 4;
    var past = held();
    var scope = questionScope(code).toLowerCase();
    var results = resultsLink(code);
    var out = [];
    // A question on every ballot that each municipality decides for itself
    // (New Hampshire's HB 1300 question) is listed apart and is not counted
    // as a statewide one (PR #120 review).
    var local = [];
    var measures = [];
    if (rec.has === true) {
      rec.measures.forEach(function (m, i) {
        (m.local ? local : measures).push({ m: m, i: i });
      });
    }
    if (rec.has === true) {
      var n = measures.length;
      out.push('<p class="measures-lead">' + (n === 1 ? "One " + scope + " question " +
        (past ? "was" : "is") : n + " " + scope + " questions " + (past ? "were" : "are")) +
        " on the Nov 3, 2026 ballot, as the " + esc(rec.by) + " lists " + (n === 1 ? "it" : "them") +
        ": " + link(rec.list.url, rec.list.title) + ", read " + esc(KYC.dateWords(rec.read)) + ".</p>");
      if (rec.guide) {
        out.push('<p class="measures-guide">Official voter information: ' +
          link(rec.guide.url, rec.guide.title) + ".</p>");
      }
      out.push('<p class="measures-words">Each is quoted in its official words. This site does ' +
        "not say what a yes or a no vote does; where the official text says so, it is quoted." +
        (rec.textNote ? " " + esc(rec.textNote) : "") + "</p>");
      out.push('<ol class="measures">' + measures.map(function (x) {
        return measureItem(code, x.m, x.i, level, rec.read);
      }).join("") + "</ol>");
      if (local.length) {
        out.push('<p class="measures-lead measures-apart">' + (local.length === 1
          ? "One more question " + (past ? "was" : "is") + " on every ballot, but " +
            (past ? "was" : "is") + " not one " + scope + " decision"
          : local.length + " more questions " + (past ? "were" : "are") + " on every ballot, " +
            "but " + (past ? "were" : "are") + " not " + scope + " decisions") +
          ": each town or city " + (past ? "voted" : "votes") + " on it for itself, and its " +
          "own ballot names the place.</p>");
        out.push('<ol class="measures measures-local-list">' + local.map(function (x) {
          return measureItem(code, x.m, x.i, level, rec.read);
        }).join("") + "</ol>");
      }
    } else if (rec.has === false) {
      out.push('<p class="measures-lead">No ' + scope + " question " + (past ? "was" : "is") +
        " on the Nov 3, 2026 ballot.</p>");
      out.push('<p class="measures-source">' + noneLine(code, rec) + "</p>");
    } else {
      out.push('<p class="measures-lead">This site ' + (past ? "did" : "has") + " not " +
        (past ? "find" : "found") + " an official list of " + scope + " questions on the " +
        "Nov 3, 2026 ballot, and does not say there " + (past ? "were" : "are") + " none. " +
        "The election office's own site: " + link(rec.office.url, rec.office.name) + ".</p>");
    }
    if (past && rec.has === true) {
      out.push('<p class="measures-results">This site does not read the results of ballot ' +
        "questions" + (results ? ": " + results : "") + ".</p>");
    }
    out.push(localLine(code, local.length > 0));
    return out.join("");
  }

  /** Whether *code*'s ballot holds statewide questions this site lists. */
  function hasMeasures(code) {
    var rec = measuresOf(code);
    return !!rec && rec.has === true && !noElection(code);
  }

  /** Whether data/measures.js failed to load: no record for any place,
   *  which is not a place with no record. A failed load is said on the
   *  page, and the state page keeps the list it was written with (rules
   *  76, 96): drawn from nothing, the questions vanished without a word
   *  (PR #123 review). */
  function measuresMissing() {
    return !global.kycMeasures;
  }

  /** What a reader is told where the list did not load. *onStatePage*:
   *  above the plain list the page was written with, which stays. */
  function measuresFailedLine(code, onStatePage) {
    var section = measuresName(code).toLowerCase();
    if (onStatePage) {
      return '<p class="results-bar measures-failed">The ' + esc(section) + " in full, with " +
        "their official text, did not load. Below is what this page was written with; reload " +
        "the page to try again.</p>";
    }
    var sample = sampleLink(code);
    return '<p class="measures-lead measures-failed">The list of ' + esc(section) + " did not " +
      "load, so this page cannot say whether any is on this ballot. Reload the page, or see " +
      '<a href="' + KYC.escapeAttr(KYC.stateUrl(code) + "#measures") + '">' +
      esc(placeName(code)) + "'s page</a>" +
      (sample ? " or the election office's sample ballot: " + sample : "") + ".</p>";
  }

  /** The state page's section: its own heading and the same list. */
  function measuresSection(code) {
    var body = measuresBody(code, { level: 3 });
    if (!body) return "";
    return '<section class="state-section measures-section" id="measures">' +
      '<h2 class="state-heading">' + esc(measuresHeading(code)) + "</h2>" + body + "</section>";
  }

  /* One listener for every page that shows the questions: the fold opens
   * and closes in place. */
  doc.addEventListener("click", function (event) {
    var button = event.target && event.target.closest && event.target.closest("[data-measure-more]");
    if (!button) return;
    var text = doc.getElementById(button.getAttribute("aria-controls"));
    if (!text) return;
    var open = button.getAttribute("aria-expanded") !== "true";
    button.setAttribute("aria-expanded", open ? "true" : "false");
    text.classList.toggle("is-folded", !open);
    button.textContent = open ? "Show less" : "Read the whole text";
  });

  /* ======================================================= Your ballot */

  /* A reader asked "who is on my ballot" and the site answered only "who
   * represents me", on a state page that listed the candidates for Congress
   * and named no one running for governor (audit 2026-10-17, VISUALS-26,
   * RACES-16, PERSONA-08). This page puts every contest the site can name
   * on one list, in the order a ballot prints offices - federal, then
   * statewide, then the legislature, then the statewide questions - each
   * drawn by the module that draws it elsewhere: a race's people by the
   * race sections' split, order, status words and count (KYC.cards, rules
   * 12 and 73), a statewide office's candidates by the state page's block
   * (KYC.stategov, rule 91), a legislative seat by the legislature page's
   * words, the questions by the state page's list (rule 95). What the site
   * does not hold - legislative candidates, local questions and contests - is
   * said to be not listed here, with the state's own sample ballot where
   * one is linked, and never guessed (rule 19).
   *
   * The address carries a ZIP code the reader typed ("#/?zip=30303"), so a
   * copied link shows the same list, and nothing else: a location is never
   * put in an address, which a copied link would carry away (rule 92). */

  var OFFICES = ["governor", "lt", "ag", "sos"];

  var page = { zip: "", ticket: 0 };

  function esc(text) { return KYC.escapeHtml(text); }

  function cycleYear() { return (KYC.meta().election || {}).year || 2026; }

  /** From the day after Election Day the page speaks of an election held. */
  function held() { return KYC.electionStatus(cycleYear()).phase === "post-election"; }

  function stateInfo(code) { return (KYC.meta().states || {})[code] || {}; }

  function placeName(code) { return PLACE[code] || KYC.findRep.nameOf(code); }

  function votingOf(code) { return (KYC.meta().voting || {})[code] || {}; }

  /** The state's own sample-ballot page, where its election office links
   *  one (voting.SAMPLE_BALLOTS, NASS), labelled as the voting block
   *  labels it; "" where none is linked. */
  function sampleLink(code, cls) {
    var url = votingOf(code).sample;
    if (!url) return "";
    var labels = ((KYC.meta().voting || {})._labels || {})[code] || {};
    return '<a class="' + (cls || "") + '" href="' + KYC.escapeAttr(url) +
      '" target="_blank" rel="noopener noreferrer">' + (cls === "btn" ? KYC.icon("link") + " " : "") +
      esc(labels.sample || "See a sample ballot") + "</a>";
  }

  function resultsLink(code) {
    var url = votingOf(code).results;
    return url ? link(url, KYC.possessive(placeName(code)) + " official results") : "";
  }

  /* ------------------------------------------------- one contest's card */

  function contest(cls, title, seat, body, id) {
    return '<li class="ballot-contest' + (cls ? " " + cls : "") + '"' +
      (id ? ' id="' + KYC.escapeAttr(id) + '"' : "") + ">" +
      '<h4 class="ballot-office">' + esc(title) +
      (seat ? ' <span class="ballot-seat">' + esc(seat) + "</span>" : "") + "</h4>" +
      body + "</li>";
  }

  function personRow(p) {
    return '<li class="ballot-person"><button type="button" class="link-button" data-id="' +
      KYC.escapeAttr(p.id) + '">' + esc(p.name) + "</button> " +
      '<span class="party-chip ' + KYC.partyClass(p) + '">' + esc(p.party) + "</span> " +
      KYC.cards.statusBadge(p) + "</li>";
  }

  /** A race for Congress as the race views show it: its badges (the
   *  result, the primary, how many are on the ballot), the seat's holder
   *  running elsewhere, the people still in it with each one's status, the
   *  people the results name with no profile here, and the order they are
   *  listed in; who is no longer in it is counted and left to the state
   *  page, as a printed ballot leaves them off. */
  function raceCard(code, race, title, seat, lead) {
    var all = race.incumbentIds.concat(race.candidateIds).map(KYC.byId).filter(Boolean);
    var split = KYC.cards.racePeople(race, all);
    // Under "On your ballot", only the people the lookup's answer lists
    // (KYC.stillRunning): a filer the results do not settle after the
    // primary is not counted on the ballot (rule 74), and listed among
    // those on it they made IL-4's card name 7 under a count of 5 (PR #115
    // review). They are named apart, as not known.
    var running = split.running.filter(function (p) { return KYC.stillRunning(race, p); });
    var unsure = split.running.filter(function (p) { return running.indexOf(p) === -1; });
    var none = !running.length && !(((race.results || {}).otherNominees || []).length);
    var name = stateInfo(code).name || KYC.stateName(code);
    // The seat's holder off this ballot is named with their own status
    // ("Not running for re-election", rule 61), never counted among the
    // people who "lost the primary, withdrew, or were not on the primary
    // ballot".
    var holders = split.out.filter(function (p) {
      return !p.isCandidate && race.incumbentIds.indexOf(p.id) !== -1;
    });
    var gone = split.out.filter(function (p) { return holders.indexOf(p) === -1; });
    var body = (lead || "") +
      '<p class="ballot-badges">' + KYC.cards.raceBadges(race) + "</p>" +
      split.moved.map(KYC.cards.heldByLine).join("") +
      holders.map(function (p) {
        return '<p class="race-held ballot-holder">Held by <button type="button" class="link-button" ' +
          'data-id="' + KYC.escapeAttr(p.id) + '">' + esc(p.name) + "</button> " +
          KYC.cards.statusBadge(p) + "</p>";
      }).join("") +
      (running.length ? '<ul class="ballot-people">' + running.map(personRow).join("") + "</ul>" : "") +
      (none ? '<p class="ballot-note">Nobody with a profile here is ' +
        (unsure.length ? "known to be on this ballot" : "in this race") + ".</p>" : "") +
      KYC.cards.unprofiledNote(race, "ballot-note") +
      KYC.cards.orderNote(running.length ? running : split.people, race, split.people.length) +
      (unsure.length
        ? '<p class="ballot-note ballot-unsure-note">Filed for this seat; whether ' +
          (unsure.length === 1 ? "this person is" : "these people are") + " on the " +
          (held() ? "" : "November ") + "ballot is not known here:</p>" +
          '<ul class="ballot-people ballot-unsure">' + unsure.map(personRow).join("") + "</ul>"
        : "") +
      (gone.length
        ? '<p class="ballot-note">' + gone.length + (holders.length ? " other" : "") +
          (gone.length === 1 ? " person" : " people") +
          " no longer in this race - lost the primary, withdrew, or " +
          (gone.length === 1 ? "was" : "were") + " not on the primary ballot - " +
          (gone.length === 1 ? "is" : "are") + " listed on the " + esc(name) + " page.</p>"
        : "") +
      '<p class="ballot-more"><a href="' + KYC.escapeAttr(KYC.stateUrl(code) + "#race-" + race.id) +
        '">This race on the ' + esc(name) + " page &rsaquo;</a></p>";
    return contest("ballot-federal", title, seat, body, "contest-" + race.id);
  }

  function senateCards(code) {
    var info = stateInfo(code);
    if (!info.senators) return [];
    // The regular election first, then a special one for the rest of a term.
    var races = KYC.findRep.senateRaces(code).slice().sort(function (a, b) {
      return (a.special ? 1 : 0) - (b.special ? 1 : 0);
    });
    if (!races.length) {
      // The race set is the cycle's frozen record (rule 65): no race in it
      // is no seat of the state's on this ballot.
      return [contest("ballot-federal ballot-off", "U.S. Senate", "",
        '<p class="ballot-note">Neither of ' + esc(KYC.possessive(info.name || code)) +
        " U.S. Senate seats is up in " + cycleYear() + ".</p>")];
    }
    return races.map(function (race) {
      return raceCard(code, race, "U.S. Senate", race.special ? "Special election" : "");
    });
  }

  /** Each part's share of the ZIP area's land, in words that add up as
   *  the panel's do (KYC.findRep.pcts); none for a location's parts. */
  function shareWords(parts) {
    var shares = parts.map(function (p) { return Array.isArray(p) ? p[1] : null; });
    return shares.every(function (s) { return typeof s === "number"; })
      ? KYC.findRep.pcts(shares) : [];
  }

  /** The House: one card per district the ZIP area or the location
   *  reaches, on the map the 2026 race is fought on, each with its share of
   *  the ZIP area's land where there is more than one. */
  function houseCards(code, parts, ctx) {
    var info = stateInfo(code);
    var title = info.delegates && !info.house
      ? (info.delegateTitle || "Delegate") + " to the U.S. House" : "U.S. House";
    var several = parts.length > 1;
    var words = shareWords(parts);
    return parts.map(function (part, i) {
      var n = Array.isArray(part) ? part[0] : part;
      var share = Array.isArray(part) ? part[1] : null;
      var race = KYC.findRep.houseRace(code, n);
      var seat = String(n) === "0" ? (info.delegates && !info.house ? "" : "At large")
        : "District " + n + (ctx.redrawn ? ", on the 2026 map" : "");
      var lead = !several ? ""
        : share !== null
          ? '<p class="ballot-share"><span class="findrep-share">' + words[i] +
            "</span> of ZIP " + esc(ctx.zip) + "&rsquo;s land is in this district.</p>"
          : '<p class="ballot-share">One of the districts in reach of your location.</p>';
      if (race) return raceCard(code, race, title, seat, lead);
      var term = info.houseTerm;
      return contest("ballot-federal ballot-off", title, seat, lead + '<p class="ballot-note">' +
        (term ? "Not on the " + cycleYear() + " ballot: the seat has a " + term.years +
          "-year term, last on the ballot in " + term.last + " and next in " + term.next + "."
          : "No race for this seat is in this site's record of the " + cycleYear() + " ballot.") +
        "</p>");
    });
  }

  /** "Statewide" is a state's word; a territory's offices are its own
   *  (rule 75). */
  function wide(code) {
    return stateInfo(code).territory ? "Territorial" : "Statewide";
  }

  /** The statewide offices on the ballot, each with its mark (linked to
   *  the record that puts it there), whether its holder is on the list, and
   *  the candidates its election office lists (rule 91), write-ins apart;
   *  then the offices the site covers that are not on this ballot, each
   *  with its own record's words. */
  function statewideCards(code) {
    var sg = KYC.stategov;
    var b = sg && sg.ballotOf(code);
    if (!b) return [];
    var keys = OFFICES.filter(function (k) { return b.offices[k]; });
    var up = keys.filter(function (k) { return b.offices[k].up; });
    var place = stateInfo(code).name || KYC.stateName(code);
    var cards = up.map(function (k) {
      return contest("ballot-statewide", sg.titles[k], place,
        '<p class="gov-office">' + sg.officeMark(code, k) + "</p>" + sg.openSeat(code, k, { role: true }) +
        sg.candidatesBlock(code, k), "contest-" + code + "-" + k);
    });
    var notUp = keys.filter(function (k) {
      return !b.offices[k].up && b.offices[k].selection !== "no-such-office";
    });
    if (notUp.length) {
      cards.push(contest("ballot-statewide ballot-off", up.length
        ? wide(code) + " offices not on this ballot"
        : "No " + wide(code).toLowerCase() + " office this site covers is on this ballot", "",
        '<ul class="ballot-offlist">' + notUp.map(function (k) {
          return "<li>" + esc(sg.titles[k]) + ": " + sg.officeMark(code, k) + "</li>";
        }).join("") + "</ul>"));
    }
    return cards;
  }

  /** The state legislature: for each chamber, the district (or each one in
   *  reach) and whether its seat is on the ballot, in the legislature
   *  page's words from the state's own record; its candidates are not
   *  listed here, with the state's sample ballot where one is linked. Who
   *  holds the seat is the "Find who represents you" answer's to say. */
  function legislatureCards(code, ctx) {
    var leg = ctx.leg;
    if (!leg) {
      if (!ctx.legFailed) return [];
      var failed = [contest("ballot-legislature", "State legislature", "",
        '<p class="ballot-note">Its districts did not load. <a href="' +
        KYC.escapeAttr(KYC.siteRoot() + "legislature/" + code.toLowerCase() + ".html") +
        '">Find your district on the legislature page &rsaquo;</a></p>')];
      failed.anyUp = true;   // not known, so never said to be off it
      return failed;
    }
    var name = KYC.findRep.nameOf(code);
    var pageUrl = KYC.siteRoot() + leg.page;
    var sample = sampleLink(code);
    var past = held();
    var anyUp = false;
    var cards = ["upper", "lower"].filter(function (ch) { return leg.chambers[ch]; }).map(function (ch) {
      var c = leg.chambers[ch];
      var parts = ctx[ch] || [];
      var title = name + " " + c.title;
      if (!parts.length) {
        anyUp = true;
        return contest("ballot-legislature", title, "", '<p class="ballot-note">Your district was not ' +
          'found on its district map; <a href="' + KYC.escapeAttr(pageUrl) +
          '">pick it on the legislature page &rsaquo;</a></p>' + chamberBallot(c));
      }
      var several = parts.length > 1;
      var words = shareWords(parts);
      var maybe = false, unknown = false;
      var rows = parts.map(function (part, i) {
        var id = Array.isArray(part) ? part[0] : part;
        var share = Array.isArray(part) && several ? part[1] : null;
        var href = pageUrl + "#/?" + (ch === "lower" ? "chamber=lower&" : "") + "d=" +
          encodeURIComponent(id);
        var up = seatUp(c, id);
        if (up !== false) maybe = true;
        if (up === null) unknown = true;
        // A district the record cannot place says so on its own row, and
        // the chamber's count is said once, above the rows, never repeated
        // under each (PR #115 review: Montana's Senate).
        var says = up !== null ? seatBallot(c, id)
          : '<p class="leg-ballot">Whether this district ' + (past ? "had" : "has") +
            " a seat on the Nov 3, 2026 ballot is not known here.</p>";
        return '<div class="ballot-seat-row"><p class="ballot-seat-name">' +
          (share !== null ? '<span class="findrep-share">' + words[i] + "</span> " : "") +
          '<a class="ballot-district" href="' + KYC.escapeAttr(href) + '">' +
          esc(KYC.findRep.districtName(c, id)) + "</a></p>" + says + "</div>";
      });
      if (maybe) anyUp = true;
      var lead = several ? (ctx.zip
        ? '<p class="ballot-share">ZIP ' + esc(ctx.zip) + " touches " + parts.length +
          " of its districts; the shares are of its land.</p>"
        : '<p class="ballot-share">' + parts.length + " of its districts are in reach of your " +
          "location.</p>") : "";
      var notes = [];
      if (unknown) {
        // The gap is this site's, not the state's: its record of the 2026
        // ballot gives a count, or words that name no district on the map
        // (Montana's "25 of 50", Illinois's senate groups).
        notes.push("This site's record of the " + cycleYear() + " ballot gives how many of the " +
          "chamber's seats are up, not which districts' they are.");
      }
      if (maybe) {
        var what = several ? "these seats" : c.districtSeats === "one" ? "this seat" : "this district";
        notes.push((past ? "Who was on the ballot for " + what + " is not listed here"
          : "The candidates for " + what + " are not listed here") +
          (sample ? ": " + sample + "." : past && resultsLink(code) ? "; " + resultsLink(code) + "." : "."));
      }
      // A chamber with no seat of the reader's up is not a contest on this
      // ballot, and is drawn as the other offices not on it are.
      return contest("ballot-legislature" + (maybe ? "" : " ballot-off"), title, "", lead +
        (unknown ? chamberBallot(c) : "") + rows.join("") +
        (notes.length ? '<p class="ballot-note">' + notes.join(" ") + "</p>" : ""));
    });
    cards.anyUp = anyUp;
    return cards;
  }

  /* -------------------------------------------- one state's whole ballot */

  /** The state's key dates, as its voting block gives them (rule 84),
   *  and the way to the rest of how to vote. */
  function datesSection(code) {
    var all = KYC.meta().voting || {};
    var info = datesFor(all, code);
    var place = placeName(code);
    var list = keyDates(info);
    // A place whose own record holds no election on November 3 keeps that
    // line after the day too: from it, the dates drop every line not still
    // news, and Puerto Rico's section was a heading over nothing (PR #115
    // review).
    var none = noElection(code);
    if (none && !(info && info.lines.some(function (l) { return l.k === "none"; }))) {
      list = '<ul class="vote-dates"><li data-kind="none">' + esc(none.t) + "." +
        (info ? lineSources(info.mine, none) : "") + "</li></ul>";
    }
    var heading = none ? place.charAt(0).toUpperCase() + place.slice(1) + " in " + cycleYear()
      : "Key dates in " + place;
    return '<section class="ballot-section ballot-dates" aria-label="' +
      KYC.escapeAttr(heading) + '">' +
      '<h3 class="ballot-heading">' + esc(heading) + "</h3>" +
      (info ? registrationLead(info, place) + calendarStrip(info) : "") + list +
      (list && datesNote(all, info) ? '<p class="state-note">' + datesNote(all, info) + "</p>" : "") +
      '<p class="state-links ballot-actions">' + KYC.findRep.voteLink(code) +
        (sampleLink(code, "btn") ? " " + sampleLink(code, "btn") : "") + "</p>" +
      "</section>";
  }

  /** What the ballot may also hold that this site does not list. */
  function unlistedSection(code, anything) {
    var info = stateInfo(code);
    var place = esc(placeName(code));
    // A place with nothing this site covers on its ballot (Puerto Rico,
    // whose commission holds no general election in 2026) is not told its
    // ballot "may also hold" more: what else it holds is not recorded here
    // (rule 19).
    var none = noElection(code);
    // From the day after the election, in the past tense like the rest of
    // the page (PR #115 review).
    var past = held();
    var hold = past ? "may also have held" : "may also hold";
    var words = none
      ? esc(none.t) + ", as its election office's own record says (linked above)."
      : !anything
      ? "Nothing this site covers " + (past ? "was" : "is") + " on " +
        esc(KYC.possessive(placeName(code))) + " " + cycleYear() + " ballot. Whether any other " +
        "contest " + (past ? "was" : "is") + ", this site does not record."
      : code === "DC" ? dcContests(past)
      : info.territory ? esc(TERRITORY_UNLISTED.replace("may also hold", hold))
      : "Your ballot " + hold + " " + esc(UNLISTED) + ".";
    var sample = sampleLink(code);
    // A candidate list above that is itself a sample ballot (Guam's
    // territorial offices) is named, or "no sample ballot" contradicted
    // the source line of the card above it (PR #115 review).
    var cited = !sample && citedSampleBallot(code);
    return '<section class="ballot-section ballot-unlisted">' +
      '<h3 class="ballot-heading">' + (!anything ? "The rest of your ballot"
        : past ? "Also on the ballot, not listed here" : "Also on your ballot, not listed here") + "</h3>" +
      '<p class="ballot-note">' + words + " " + (sample
        ? "The election office links a sample ballot, every contest on it: " + sample + "."
        : "This site's voting links hold no sample ballot for " + place +
          (cited ? " (the candidate lists above cite " + link(cited.url, cited.source) + ")" : "") +
          "; its election office's pages are under " +
          '<a href="' + KYC.escapeAttr(KYC.stateUrl(code) + "#voting") +
          '">how to vote in ' + place + "</a>.") + "</p></section>";
  }

  /** The first statewide candidate list on this ballot whose own source is
   *  a sample ballot (rule 91's words for it), or null. */
  function citedSampleBallot(code) {
    var b = KYC.stategov && KYC.stategov.ballotOf(code);
    if (!b) return null;
    var found = null;
    OFFICES.forEach(function (k) {
      var list = b.offices[k] && b.offices[k].up && b.offices[k].candidates;
      if (!found && list && list.url && /sample ballot/i.test(list.source || "")) found = list;
    });
    return found;
  }

  /** The line under a state's heading: when the election is, or, from the
   *  day after it, that it has been held, with the results this site has
   *  for Congress and the state's own for the rest (it reads no state
   *  results and names no state winner). */
  function whenLine(code) {
    var none = noElection(code);
    if (none) return '<p class="ballot-when">' + esc(none.t) + ".</p>";
    if (!held()) {
      return '<p class="ballot-when">Election Day is ' +
        esc(KYC.dateWords(KYC.electionStatus(cycleYear()).iso)) + ".</p>";
    }
    var asOf = (KYC.meta().election || {}).resultsAsOf;
    var results = resultsLink(code);
    return '<p class="ballot-when ballot-after">The ' + esc(KYC.dateWords(
      KYC.electionStatus(cycleYear()).iso)) + " election has been held. The races for Congress " +
      "show the results this site last read" + (asOf ? ", on " + esc(KYC.dateWords(asOf)) : "") +
      ". This site does not read state or local results and names no winner for them" +
      (results ? ": " + results : "") + ".</p>";
  }

  /** One state's ballot. *ctx*: the districts the answer reaches - *race*
   *  (the House, on the 2026 race's map), *upper* and *lower* (the state
   *  legislature) - each ``[[id, share]]`` or ids; *leg*, the legislature
   *  file; *zip*; *head*, the heading's words; *notes*, what the answer
   *  cannot say. */
  function stateBallot(code, ctx) {
    var statewide = statewideCards(code);
    var legislature = legislatureCards(code, ctx);
    // The statewide questions last, as a printed ballot puts them (rule 95):
    // a card whether there are any or not, since "none" and "not found"
    // are each something to say (rule 19).
    // A list that did not load is said in the same card, never dropped.
    var questions = !noElection(code) && measuresMissing() ? measuresFailedLine(code)
      : measuresBody(code, { level: 5 });
    var asked = hasMeasures(code);
    var cards = senateCards(code).concat(houseCards(code, ctx.race, ctx))
      .concat(statewide).concat(legislature)
      .concat(questions ? [contest("ballot-measures" + (asked ? "" : " ballot-off"),
        measuresName(code), "", questions, "contest-" + code + "-measures")] : []);
    // The order said as what it is: this site's, which a printed ballot
    // may not follow.
    // Whether anything this site covers is on this ballot at all.
    var offices = KYC.stategov && KYC.stategov.ballotOf(code);
    var statewideUp = !!offices && OFFICES.some(function (k) {
      return offices.offices[k] && offices.offices[k].up;
    });
    // A legislature whose seats in reach are none of them up is not part of
    // this ballot's order (Virginia's, New Jersey's, PR #115 review).
    var anything = KYC.findRep.senateRaces(code).length > 0 || !!legislature.anyUp ||
      ctx.race.some(function (part) {
        return KYC.findRep.houseRace(code, Array.isArray(part) ? part[0] : part);
      }) || statewideUp || asked;
    var order = ["Congress"];
    if (statewideUp) order.push(wide(code).toLowerCase() + " offices");
    if (legislature.anyUp) order.push("the state legislature");
    // The note names every card the list shows: where there are no
    // questions, or no list was found, the last card still says so (PR #120
    // review).
    if (asked) order.push("the " + measuresName(code).toLowerCase());
    else if (questions) order.push("a note on " + measuresName(code).toLowerCase());
    var past = held();
    // A place that holds no election on November 3 has no ballot to speak
    // of, before the day or after it.
    var heading = noElection(code) ? "The offices this site covers"
      : past ? "What was on the ballot" : "On your ballot";
    return '<article class="ballot-state" data-state="' + KYC.escapeAttr(code) + '">' +
      '<h2 class="ballot-place">' + ctx.head + "</h2>" +
      whenLine(code) +
      (ctx.notes && ctx.notes.length ? '<p class="findrep-note">' + ctx.notes.join(" ") + "</p>" : "") +
      (ctx.actions ? '<p class="ballot-actions">' + ctx.actions + "</p>" : "") +
      datesSection(code) +
      '<section class="ballot-section">' +
        '<h3 class="ballot-heading">' + heading + "</h3>" +
        (order.length > 1 ? '<p class="ballot-note">' + esc(order[0] + " first, then " +
          order.slice(1).join(", then ")) +
          (past ? ". Your printed ballot may have listed them in another order.</p>"
            : ". Your printed ballot may list them in another order.</p>") : "") +
        '<ol class="ballot-list">' + cards.join("") + "</ol>" +
      "</section>" +
      unlistedSection(code, anything) +
      "</article>";
  }

  function printRow() {
    return '<p class="ballot-print-row"><button type="button" class="btn" data-ballot-print>' +
      KYC.icon("print") + " Print or save this list</button></p>";
  }

  function locateButton() {
    return KYC.findRep.canLocate()
      ? ' <button type="button" class="btn" data-ballot-locate>' + KYC.icon("pin") +
        " Use my location</button>" : "";
  }

  /** The ballot for a ZIP code, from KYC.findRep.zip's list. Where the ZIP
   *  area touches more than one district at any level, each is listed with
   *  its share of the land, and the state's ballot says so under its
   *  heading, with the way to an exact answer (rule 85). */
  function zipBallot(zip5, found) {
    if (!found.length) return KYC.findRep.noZipArea(zip5);
    var crosses = found.length > 1;
    var out = crosses ? [KYC.findRep.crossesNote(zip5, found, "ballot")] : [];
    found.forEach(function (f) {
      var parts = KYC.findRep.zipParts(f);
      var split = parts.race.length > 1 || parts.upper.length > 1 || parts.lower.length > 1;
      var check = KYC.findRep.officialLookup(f.code);
      var notes = split ? ['<span class="ballot-caveat">ZIP ' + esc(zip5) + " crosses district " +
        "lines: each district it touches is listed with the share of the ZIP area's land in it. " +
        "The shares are of land, not people, so they cannot say which side your home is on. " +
        "For an exact answer, use your location" + (check ? " or the official lookup" : "") +
        ".</span>"] : [];
      // The ways to an exact answer on a row of their own: inline, the
      // button broke the sentence on a phone (PR #115 review).
      var actions = split ? (locateButton() + (check ? " " + check : "")).trim() : "";
      out.push(stateBallot(f.code, {
        head: "Your ballot: ZIP " + esc(zip5) + ", " + esc(KYC.findRep.nameOf(f.code)) +
          (crosses ? " (" + KYC.findRep.pct(KYC.findRep.landIn(f.entry)) + " of its land)" : ""),
        zip: zip5, race: parts.race, upper: parts.upper, lower: parts.lower,
        leg: f.leg, legFailed: f.legFailed, redrawn: !!f.data.next && !KYC.recordPhase(),
        notes: notes, actions: actions,
      }));
    });
    return out.join("") + printRow();
  }

  /** The ballot for a location, from KYC.findRep.where's answer. */
  function pointBallot(hit, accuracy) {
    if (!hit.code) {
      return '<p class="findrep-note">That location is not in any state, D.C. or territory ' +
        'this site covers. <a href="' + KYC.escapeAttr(KYC.siteRoot() + "states/index.html") +
        '">Find your state &rsaquo;</a></p>';
    }
    var fr = KYC.findRep;
    var key = fr.plans(hit.data);
    var f = hit.found, lf = hit.legFound || {};
    var levels = [
      { f: f[key.race], line: "a congressional district line", many: "congressional districts" },
      { f: lf.upper, line: "a state legislative district line", many: "state legislative districts", leg: true },
      { f: lf.lower, line: "a state legislative district line", many: "state legislative districts", leg: true },
    ];
    var said = fr.pointNotes(hit, levels, accuracy);
    var notes = said.notes.slice();
    if (said.unsure && fr.officialLookup(hit.code)) notes.push(fr.officialLookup(hit.code));
    return stateBallot(hit.code, {
      head: "Your ballot: your location, " + esc(fr.nameOf(hit.code)),
      race: fr.reach(f[key.race]), upper: fr.reach(lf.upper), lower: fr.reach(lf.lower),
      leg: hit.leg, legFailed: hit.legFailed, redrawn: !!hit.data.next && !KYC.recordPhase(),
      notes: notes,
    }) + printRow();
  }

  /* ------------------------------------------------------- the controls */

  function result() { return doc.getElementById("ballotResult"); }

  /** Draws *html* as the answer; with *pending*, a word that the answer is
   *  on its way, which keeps the room kyc.js held for it. */
  function show(html, pending) {
    var out = result();
    out.hidden = false;
    out.innerHTML = html;
    if (!pending) doc.documentElement.classList.remove("has-zip");
  }

  function note(text) { return '<p class="findrep-note">' + text + "</p>"; }

  function askZip(zip5, write) {
    page.zip = zip5;
    var input = doc.getElementById("ballotZip");
    if (input) input.value = zip5;
    // The ZIP code in the address, so a copied link shows this list; a
    // fragment is never sent to a server.
    if (write) KYC.router.writeFilters({ zip: zip5 });
    show(note("Looking up " + esc(zip5) + "&hellip;"), true);
    var ticket = ++page.ticket;
    return KYC.findRep.zip(zip5).then(function (found) {
      if (ticket !== page.ticket) return;
      // The page holds no one's records until an answer needs them (rule
      // 94): the answer's states first, and a state whose file did not
      // load is said by name, never drawn as a ballot with nobody on it.
      return KYC.findRep.peopleFor(found.map(function (f) { return f.code; })).then(function (failed) {
        if (ticket !== page.ticket) return;
        if (failed.length) {
          show(KYC.findRep.peopleFailed(failed, "The races and candidates"));
          return;
        }
        show(zipBallot(zip5, found));
        if (found.length === 1) KYC.findRep.remember(found[0].code);
      });
    }, function () {
      if (ticket !== page.ticket) return;
      show(note("The ZIP code lookup did not load. Check your connection and try again."));
    });
  }

  function locate() {
    var button = doc.querySelector("#ballotAsk [data-ballot-locate]");
    page.zip = "";
    // A location is never written into the address (rule 92): whatever
    // ZIP code was there goes, and nothing takes its place.
    KYC.router.writeFilters({});
    var input = doc.getElementById("ballotZip");
    if (input) input.value = "";
    var ticket = ++page.ticket;
    if (button) button.disabled = true;
    show(note("Finding your location&hellip;"));
    global.navigator.geolocation.getCurrentPosition(function (pos) {
      if (button) button.disabled = false;
      if (ticket !== page.ticket) return;
      var acc = pos.coords.accuracy;
      if (isFinite(acc) && acc / 1000 > KYC.findRep.ROUGH_KM) {
        show(note("Your browser shared only an approximate location (to within " +
          KYC.findRep.distance(acc) + "), too rough to place in a district. Type your ZIP code instead."));
        return;
      }
      KYC.findRep.where(pos.coords.longitude, pos.coords.latitude, acc).then(function (hit) {
        if (ticket !== page.ticket) return;
        return KYC.findRep.peopleFor([hit.code]).then(function (failed) {
          if (ticket !== page.ticket) return;
          if (failed.length) {
            show(KYC.findRep.peopleFailed(failed, "The races and candidates"));
            return;
          }
          show(pointBallot(hit, acc));
          if (hit.code) KYC.findRep.remember(hit.code);
        });
      }, function () {
        if (ticket !== page.ticket) return;
        show(note("The lookup did not load. Check your connection and try again."));
      });
    }, function (err) {
      if (button) button.disabled = false;
      if (ticket !== page.ticket) return;
      show(note((err && err.code === 1 ? "Your browser did not share a location."
        : "Your location could not be found.") + " Type your ZIP code instead."));
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
  }

  function mountAsk(slot) {
    slot.innerHTML =
      '<h2 class="findrep-title" id="ballotAskTitle">' + KYC.icon("ballot") + " Find your ballot</h2>" +
      '<form class="findrep-form" novalidate>' +
        '<label class="findrep-label" for="ballotZip">ZIP code</label>' +
        '<input class="text-input findrep-zip" id="ballotZip" name="zip" type="text" ' +
          'inputmode="numeric" autocomplete="postal-code" maxlength="10" placeholder="e.g. 43215" ' +
          'aria-describedby="ballotNote">' +
        '<button type="submit" class="btn">Show my ballot</button>' + locateButton() +
      "</form>" +
      '<p class="field-note findrep-privacy" id="ballotNote">' + KYC.findRep.PRIVACY +
        " The page's address keeps a ZIP code you type, so a copied link shows the same list; " +
        "it never keeps your location.</p>";
    slot.setAttribute("aria-labelledby", "ballotAskTitle");
    var input = slot.querySelector("#ballotZip");
    slot.querySelector("form").addEventListener("submit", function (event) {
      event.preventDefault();
      var m = /^(\d{5})(?:-?\d{4})?$/.exec(String(input.value || "").trim());
      if (!m) {
        show(note("Type a five-digit ZIP code."));
        input.focus();
        return;
      }
      askZip(m[1], true);
    });
  }

  function route() {
    var r = KYC.router.read();
    if (!/^\d{5}$/.test((r.params || {}).zip || "")) doc.documentElement.classList.remove("has-zip");
    if (r.view === "profile") {
      if (KYC.profile.open(r.id, { fromRoute: true })) return;
    } else if (KYC.profile.isOpen()) {
      KYC.profile.close();
    }
    var zip5 = (r.params || {}).zip || "";
    if (/^\d{5}$/.test(zip5)) {
      if (zip5 !== page.zip) askZip(zip5, false);
    } else if (zip5) {
      show(note("The address holds no five-digit ZIP code. Type yours above."));
    }
  }

  /** The page: its controls, a delegated listener for what its answers
   *  hold, and its address read. */
  function start() {
    var root = doc.getElementById("ballotPage");
    if (!root) return;
    // The page loads the build's figures, and each answer's people when it
    // is asked for (rule 94): without the figures nothing can be drawn.
    if (!KYC.meta().signature || !KYC.findRep) {
      show(note("The site's data did not load. Reload the page to try again."));
      return;
    }
    KYC.profile.ensure();
    if (held()) {
      var lede = root.querySelector("[data-ballot-lede]");
      if (lede) {
        lede.textContent = "What was on your " + KYC.dateWords(KYC.electionStatus(cycleYear()).iso) +
          " ballot that this site can name, from your ZIP code or your location, with the " +
          "results it has for Congress.";
      }
    }
    mountAsk(root.querySelector("[data-ballot-ask]"));
    root.addEventListener("click", function (event) {
      var t = event.target;
      if (t.closest("[data-ballot-print]")) { global.print(); return; }
      if (t.closest("[data-ballot-locate]")) { locate(); return; }
      var person = t.closest("button[data-id]");
      if (person) KYC.profile.open(person.getAttribute("data-id"));
    });
    // Paper is white: printed in a dark theme, the list's light text came
    // out white on white. The light theme's colours for the print only,
    // the reader's own choice put back after it (and never saved).
    // The page's declared scheme goes with it: "only dark" left the paper's
    // canvas dark under light text.
    var html = doc.documentElement;
    var scheme = doc.querySelector('meta[name="color-scheme"]');
    var theme = null, declared = null;
    global.addEventListener("beforeprint", function () {
      theme = html.getAttribute("data-theme");
      html.setAttribute("data-theme", "light");
      if (scheme) {
        declared = scheme.getAttribute("content");
        scheme.setAttribute("content", "only light");
      }
    });
    global.addEventListener("afterprint", function () {
      if (theme === null) html.removeAttribute("data-theme");
      else html.setAttribute("data-theme", theme);
      if (scheme && declared !== null) scheme.setAttribute("content", declared);
      theme = declared = null;
    });
    KYC.router.onChange(route);
    route();
  }

  KYC.ballot = {
    // The state pages' voting block and its parts.
    votingBlock: votingBlock,
    datesFor: datesFor,
    keyDates: keyDates,
    calendarStrip: calendarStrip,
    registrationLead: registrationLead,
    // The legislature pages' words for a chamber's seats and one seat's.
    chamberBallot: chamberBallot,
    seatBallot: seatBallot,
    seatUp: seatUp,
    // What a ballot may hold that the site does not list.
    unlisted: UNLISTED,
    dcContests: dcContests,
    territoryUnlisted: TERRITORY_UNLISTED,
    // The statewide questions (rule 95): the state page's section, and its
    // name for the page's jump chip.
    measuresSection: measuresSection,
    measuresName: measuresName,
    hasMeasures: hasMeasures,
    measuresMissing: measuresMissing,
    measuresFailedLine: measuresFailedLine,
    // The Your ballot page.
    zipBallot: zipBallot,
    pointBallot: pointBallot,
    stateBallot: stateBallot,
  };

  KYC.ready(function () {
    if (doc.body.getAttribute("data-page") === "ballot") start();
  });
})(window);
