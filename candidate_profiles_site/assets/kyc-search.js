/* The home search's answers about government (rule 97).
 *
 * The grid's search found people by name, a state or a seat, and answered
 * a ZIP code; an office typed into it ("governor", "Texas AG", "Secretary
 * of Labor"), a place ("Travis County"), a body ("Texas House", "Armed
 * Services"), a court ("Fifth Circuit", "S.D.N.Y.") or a ballot question
 * ("Missouri Amendment 3") found nobody, or a challenger whose text
 * mentioned the word. This module reads such a query and answers it with
 * links to the page about the thing named, grouped by kind, above the
 * cards: offices with who holds each and, where the Nov 3, 2026 ballot has
 * a race for it, the candidates, labelled as such; places and bodies;
 * courts; ballot questions. A word too broad to answer ("judge") suggests
 * narrower searches.
 *
 * Nothing here is a profile. A federal official opens in their own dialog,
 * a state officer on their state's page; only a member of Congress links
 * to a profile (rule 27). A query is read as words, case and punctuation
 * folded, with the abbreviations readers write (AG, SoS, Lt. Gov., SCOTUS,
 * Calif.); never a fuzzy match, which could put one person's office on
 * another (rule 3).
 *
 * The data is read from the files the pages about it read - stategov.js,
 * federal.js, measures.js - and from data/search.js (kyc/search_index.py)
 * for what no such file holds: legislatures, counties, committees and
 * tribal governments. Each is loaded the first time a query needs it
 * (KYC.loadData); `answer` says which it is waiting for.
 */
(function (global) {
  "use strict";

  var KYC = global.KYC;

  var esc = function (text) { return KYC.escapeHtml(text); };

  /* ------------------------------------------------------------ words */

  /** *text* as words: folded as the search folds it, punctuation made
   *  spaces, a possessive's "'s" dropped and runs of single letters joined:
   *  "S.D.N.Y." is "sdny", "U.S." "us", "Lt. Gov." "lt gov". */
  function words(text) {
    var s = KYC.searchFold(text).replace(/'s\b/g, "").replace(/'/g, "")
      .replace(/&/g, " and ").replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim()
      .replace(/\b([a-z]) (?=[a-z]\b)/g, "$1");
    return s ? s.split(" ") : [];
  }

  function phrase(ws) { return ws.join(" "); }

  /* Two-letter codes that are also words a query is made of ("governor of
   * ohio" has "of" in it, "in" and "me" are words, "va" is Veterans
   * Affairs): read as a state only typed in capitals (rule 5). */
  var AMBIGUOUS = { in: 1, or: 1, me: 1, oh: 1, hi: 1, ok: 1, de: 1, al: 1, la: 1, ma: 1,
    mo: 1, id: 1, as: 1, pa: 1, co: 1, ne: 1, va: 1, ms: 1, mt: 1, ct: 1 };

  function capitalised(raw, code) {
    return new RegExp("(^|[^A-Za-z])" + code + "([^A-Za-z]|$)").test(String(raw || ""));
  }

  /** The first state *ws* names - its name, an alias, a short form or its
   *  postal code - as `{code, at, len}`, or null. The longest name at a
   *  place wins: "west virginia" is never Virginia, "washington dc" never
   *  Washington. */
  function findState(ws, raw) {
    var states = KYC.meta().states || {};
    for (var i = 0; i < ws.length; i++) {
      for (var len = Math.min(4, ws.length - i); len >= 1; len--) {
        var p = phrase(ws.slice(i, i + len));
        var code = null;
        if (len === 1 && /^[a-z]{2}$/.test(p)) {
          var upper = p.toUpperCase();
          if (states[upper] && (!AMBIGUOUS[p] || capitalised(raw, upper))) code = upper;
        } else {
          code = KYC.stateNamed(p) || KYC.stateAbbreviation(p, false);
        }
        if (code && states[code]) return { code: code, at: i, len: len };
      }
    }
    return null;
  }

  function without(ws, at, len) {
    return ws.slice(0, at).concat(ws.slice(at + len));
  }

  var FILLER = { the: 1, who: 1, whos: 1, is: 1, are: 1, current: 1, currently: 1, my: 1,
    our: 1, of: 1, for: 1, in: 1, from: 1, what: 1, list: 1, all: 1, every: 1, find: 1 };

  /** *ws* without the filler words at either end ("who is the governor
   *  of" is "governor"). */
  function trim(ws) {
    var out = ws.slice();
    while (out.length && FILLER[out[0]]) out.shift();
    while (out.length && FILLER[out[out.length - 1]]) out.pop();
    return out;
  }

  /* -------------------------------------------------------------- data */

  var FILES = {
    stategov: ["stategov.js", "kycStateGov"],
    federal: ["federal.js", "kycFederal"],
    search: ["search.js", "kycSearch"],
    measures: ["measures.js", "kycMeasures"],
  };

  function have(key) { return global[FILES[key][1]] !== undefined; }
  function gov() { return (global.kycStateGov || {}).states || {}; }
  function fed() { return global.kycFederal || {}; }
  function index() { return global.kycSearch || {}; }

  function root() { return KYC.siteRoot(); }
  function statePage(code, anchor) {
    return KYC.stateUrl(code) + (anchor ? "#" + anchor : "");
  }
  function officialHref(id) {
    return root() + "federal/index.html#/official/" + encodeURIComponent(id);
  }

  /* An officer is named only where the state's page names them as the
   * holder: not a listing the office has not confirmed, nor two sources
   * that disagree, nor a vacancy (kyc-stategov.js officerRow). The grid's
   * "Other officials" block asks the same (kyc-directory.js). */
  function namedHolder(off) {
    return !!(off && off.name && !off.disputed && !off.unlisted && !off.unconfirmed &&
      !off.vacant && !off.none && !off.notMember);
  }

  function past() {
    return KYC.electionStatus(2026).phase === "post-election";
  }

  /* --------------------------------------------------------- rendering */

  function link(href, text) {
    return '<a href="' + KYC.escapeAttr(href) + '">' + esc(text) + "</a>";
  }

  /** One answer: *main* is markup (a link, usually), *detail* markup too,
   *  after a dash unless *main* ends in a colon. */
  function row(main, detail) {
    var sep = /:(<\/a>)?$/.test(main) ? " " : " — ";
    return '<li class="answer-row">' + main +
      (detail ? '<span class="answer-detail">' + sep + detail + "</span>" : "") + "</li>";
  }

  /* A place in a sentence, in its own words (rule 75): "the District of
   * Columbia", "the Northern Mariana Islands". */
  var WITH_THE = { DC: true, MP: true, VI: true };
  function placeWords(code) {
    return (WITH_THE[code] ? "the " : "") + KYC.stateName(code);
  }

  /** "Louisiana, Mississippi and Texas". */
  function andList(items) {
    if (items.length < 2) return items.join("");
    return items.slice(0, -1).join(", ") + " and " + items[items.length - 1];
  }

  /** A member's profile link, with the seat in brackets. */
  function memberLink(id, name) {
    var p = KYC.byId(id);
    return '<a href="#/profile/' + KYC.escapeAttr(encodeURIComponent(id)) + '">' + esc(name) + "</a>" +
      (p && p.officeLabel ? ' <span class="faint">(' + esc(p.officeLabel) + ")</span>" : "");
  }

  /** A block of answers of one *kind*: `{kind, title, note, rows, compact,
   *  more}`. */
  function block(kind, title, rows, opts) {
    opts = opts || {};
    return { kind: kind, title: title, rows: rows, note: opts.note || "",
             compact: !!opts.compact, more: opts.more || "" };
  }

  var KINDS = [["offices", "Offices"], ["places", "Places and bodies"], ["courts", "Courts"],
    ["measures", "Ballot questions"], ["narrow", "Narrower searches"]];

  function render(blocks) {
    if (!blocks.length) return "";
    return KINDS.map(function (kind) {
      var mine = blocks.filter(function (b) { return b.kind === kind[0]; });
      if (!mine.length) return "";
      return '<div class="answer-group" data-kind="' + kind[0] + '">' +
        '<h2 class="answer-group-title">' + esc(kind[1]) + "</h2>" +
        mine.map(function (b) {
          return (b.title ? '<h3 class="answer-title">' + esc(b.title) + "</h3>" : "") +
            (b.note ? '<p class="answer-note">' + b.note + "</p>" : "") +
            (b.rows.length ? '<ul class="answer-list' + (b.compact ? " answer-compact" : "") + '">' +
              b.rows.join("") + "</ul>" : "") +
            (b.more ? '<p class="answer-note">' + b.more + "</p>" : "");
        }).join("") + "</div>";
    }).join("");
  }

  /** A link that runs another search: "#/?q=..." is the grid's own address
   *  for one (KYC.router). */
  function searchLink(q) {
    return '<a href="#/?q=' + KYC.escapeAttr(encodeURIComponent(q)) + '">' + esc(q) + "</a>";
  }

  function plural(n, one, many) {
    return n.toLocaleString() + " " + (n === 1 ? one : many);
  }

  var LIMIT = 12;

  /* ------------------------------------------------- state offices */

  var STATE_OFFICES = { governor: "Governor", lt: "Lieutenant Governor",
    ag: "Attorney General", sos: "Secretary of State" };
  var STATE_ORDER = ["governor", "lt", "ag", "sos"];

  var OFFICE_WORDS = [
    ["lt", /^(?:lieutenant|lieut|lt) ?(?:governors?|govs?)$|^ltgovs?$/],
    ["governor", /^(?:governors?|govs?|gubernatorial)$/],
    ["ag", /^(?:attorneys? generals?|attorney gen|ags?)$/],
    ["sos", /^(?:secretar(?:y|ies) of state|secs? of state|secy of state|sos)$/],
  ];

  var RACE_BEFORE = /^(?:candidates? (?:for|running for)|(?:who is |whos )?running for|race for|races for|election for|elections for|nominees? for) /;
  var RACE_AFTER = / (?:candidates?|race|races|election|elections|nominees?|ballot)$/;

  /** `{office, race, scope}` for the office words *rest* names: *scope*
   *  is "us" for "U.S. Attorney General", "state" for "state AG". */
  function officeOf(rest) {
    var p = phrase(rest);
    var race = false;
    if (RACE_BEFORE.test(p)) { p = p.replace(RACE_BEFORE, ""); race = true; }
    if (RACE_AFTER.test(p)) { p = p.replace(RACE_AFTER, ""); race = true; }
    var scope = "";
    var m = /^(us|federal|united states|state) (.+)$/.exec(p);
    if (m) { scope = m[1] === "state" ? "state" : "us"; p = m[2]; }
    for (var i = 0; i < OFFICE_WORDS.length; i++) {
      if (OFFICE_WORDS[i][1].test(p)) return { office: OFFICE_WORDS[i][0], race: race, scope: scope };
    }
    return null;
  }

  function officeTitle(code, key) {
    var off = (gov()[code] || {})[key];
    return (off && off.title) || STATE_OFFICES[key];
  }

  /** The state's record of *key* on the 2026 ballot, or null. */
  function ballotItem(code, key) {
    return (((gov()[code] || {}).ballot2026 || {}).offices || {})[key] || null;
  }

  /** Whether *key* is on *code*'s Nov 3, 2026 ballot: one test for every
   *  count of it (rule 73). Arizona's lieutenant governor, an office no one
   *  holds yet, is on it for the first time. */
  function onBallot(code, key) {
    var item = ballotItem(code, key);
    return !!(item && item.up);
  }

  /** "Arizona", "The District of Columbia": a place opening a sentence. */
  function PlaceWords(code) {
    var w = placeWords(code);
    return w.charAt(0).toUpperCase() + w.slice(1);
  }

  /** The office's 2026 line: on the ballot or not, as the state's record
   *  says, and the candidates its election office lists, labelled as the
   *  list's (rule 79: who is not running is a source's word, never ours). */
  function ballotLine(code, key, full) {
    var item = ballotItem(code, key);
    if (!item) return "";
    if (!item.up) {
      if (item.next && item.next.year) return "Next on the ballot in " + esc(item.next.year) + ".";
      return /^appointed|chosen/.test(item.selection || "") ? "Not an office voters elect." :
        "Not on the Nov 3, 2026 ballot.";
    }
    var out = past() ? "This office was on the Nov 3, 2026 ballot." : "This office is on the Nov 3, 2026 ballot.";
    var hs = item.holderStatus;
    if (hs && hs.why && hs.text) {
      out += " " + esc(hs.text) + (hs.cite ? " (" + esc(hs.cite) + ")" : "") + ".";
    }
    var list = item.candidates;
    // As the state page says it (kyc-stategov.js): a list not read is said
    // so, and a list that is not the state's own says that too.
    if (!list || !list.candidates) {
      return out + (full ? " Its candidates are not listed here: no election office’s list of them " +
        "has been read." : "");
    }
    var printed = list.candidates.filter(function (c) { return !c.writeIn; });
    var writeIns = list.candidates.length - printed.length;
    var writeInsCertified = !!(list.certified || (list.writeIns && list.writeIns.certified));
    var notState = list.notStateList ? " Not the state’s own list. " + esc(list.notStateList) + "." : "";
    if (!full) {
      return esc(plural(printed.length, "candidate", "candidates")) + " on " +
        esc(list.source || "the election office’s list") + "." + notState;
    }
    return out + notState + " " + (past() ? "Candidates who were on it" : "Candidates on it") + ", as " +
      (list.url ? '<a href="' + KYC.escapeAttr(list.url) + '" target="_blank" rel="noopener noreferrer">' +
        esc(list.source || list.by || "the election office’s list") + "</a>"
        : esc(list.source || list.by || "the election office’s list")) + " lists them: " +
      printed.map(function (c) {
        return esc(c.name) + (c.party ? " (" + esc(c.party) + ")" : "");
      // "Certified" only where the list's own words say so (rule 91):
      // Arizona's listing marks its write-ins and certifies no one;
      // Georgia's write-ins come from its "Final List of Certified Write-In
      // Candidates", though its main list is not marked certified.
      }).join(", ") + (writeIns ? "; and " + esc(plural(writeIns,
        (writeInsCertified ? "certified " : "") + "write-in candidate",
        (writeInsCertified ? "certified " : "") + "write-in candidates")) : "") + ".";
  }

  /** The holder's row for one state's office. A row is titled as an office
   *  only where the place has it (rule 75): the District has a mayor, not
   *  a governor, and an office this site does not list is not named as
   *  though its page held it. */
  function officeRow(code, key, full) {
    var info = gov()[code];
    var href = statePage(code, "state-government");
    var word = STATE_OFFICES[key].toLowerCase();
    if (!info) {
      return row(link(statePage(code), PlaceWords(code) + "’s page"), esc(code === "DC"
        ? (key === "governor" || key === "lt"
          ? "The District of Columbia has an elected mayor and a council of 13, not a governor and legislature."
          : "This site does not list the District of Columbia’s officers.")
        : "This site does not list " + placeWords(code) + "’s officers."));
    }
    var off = info[key];
    if (!off) {
      return row(link(href, PlaceWords(code) + "’s page"), esc("This site lists no " + word + " for " +
        placeWords(code) + "; its page lists the officers it does."));
    }
    var title = officeTitle(code, key) + ", " + KYC.stateName(code);
    if (off.none) {
      var successor = off.successor && off.successor.name
        ? " First in line to succeed the governor" + (onBallot(code, key) ? " until then" : "") + ": " +
          off.successor.title + " " + off.successor.name + "." : "";
      // A new office, first elected on Nov 3 (Arizona's lieutenant
      // governor): no one holds it yet, and its race is shown.
      if (onBallot(code, key)) {
        var item = ballotItem(code, key);
        return row(link(href, title) + ":", esc("No one holds this office yet" +
          (item.note ? ": " + item.note : "") + "." + successor) +
          (full === false ? "" : " " + ballotLine(code, key, full)));
      }
      return row(link(href, PlaceWords(code) + "’s page"), esc(PlaceWords(code) + " has no " + word +
        (key === "sos" && off.electionChief ? "; the lieutenant governor’s office runs its elections." : ".") +
        successor));
    }
    var holder = namedHolder(off)
      ? '<span class="answer-holder">' + esc(off.name) + "</span>"
      : "who holds it is not named here; its page says what each source lists";
    return row(link(href, title) + ":", holder + (full === false ? "" : ". " + ballotLine(code, key, full)));
  }

  /** Every state's holder of *key*, compactly: an acting officer, or an
   *  office called otherwise ("Secretary of the Commonwealth"), with the
   *  title the page gives them, so no acting officer reads as the holder;
   *  and a new office no one holds yet, which is on the ballot. */
  function everyState(key) {
    var states = gov();
    var codes = Object.keys(states).sort(function (a, b) {
      return KYC.stateName(a).localeCompare(KYC.stateName(b));
    });
    var up = 0;
    var rows = [];
    codes.forEach(function (code) {
      var off = states[code][key];
      var ballot = onBallot(code, key);
      if (!off || (off.none && !ballot)) return;
      if (ballot) up += 1;
      var detail;
      if (off.none) {
        detail = esc("no one holds this office yet; first elected on Nov 3, 2026");
      } else if (namedHolder(off)) {
        detail = esc(off.name) + (off.title && off.title !== STATE_OFFICES[key]
          ? " (" + esc(off.title) + ")" : "");
      } else {
        detail = "not named here";
      }
      rows.push(row(link(statePage(code, "state-government"), KYC.stateName(code)) + ":", detail));
    });
    return { rows: rows, up: up };
  }

  function stateOffice(ctx) {
    var found = officeOf(trim(ctx.state ? ctx.rest : ctx.ws));
    if (!found) return [];
    var out = [];
    var key = found.office;
    var name = STATE_OFFICES[key];
    // The federal office of the same name, unless a state was named.
    if (!ctx.state && found.scope !== "state" && (key === "ag" || key === "sos")) {
      if (!have("federal")) ctx.wants.push("federal");
      var fedKey = key === "ag" ? "justice" : "state";
      var office = (fed().offices || []).filter(function (o) { return o.key === fedKey; })[0];
      if (office) out.push(block("offices", "", [federalRow(office)]));
      if (found.scope === "us") return out;
    }
    if (found.scope === "us") return out;
    if (!have("stategov")) { ctx.wants.push("stategov"); return out; }
    if (ctx.state) {
      out.push(block("offices", "", [officeRow(ctx.state, key, true)]));
      return out;
    }
    var all = everyState(key);
    var was = past();
    if (found.race) {
      var codes = Object.keys(gov()).filter(function (code) { return onBallot(code, key); })
        .sort(function (a, b) { return KYC.stateName(a).localeCompare(KYC.stateName(b)); });
      out.push(block("offices", name + " races on the Nov 3, 2026 ballot",
        codes.map(function (code) {
          return row(link(statePage(code, "state-government"), KYC.stateName(code)) + ":",
            ballotLine(code, key, false));
        }), { compact: true, note: esc(plural(codes.length,
          was ? "state or territory elected" : "state or territory elects",
          was ? "states and territories elected" : "states and territories elect") +
          " this office on Nov 3, 2026, as each state’s own record says. Type a state with the office (") +
          searchLink("Ohio " + name.toLowerCase()) + esc(") to see its candidates.") }));
      return out;
    }
    out.push(block("offices", (key === "ag" || key === "sos" ? "Each state’s " + name.toLowerCase() : name + "s"),
      all.rows, { compact: true,
        note: esc("Each state’s and territory’s " + name.toLowerCase() + ", as its page lists them, " +
          "with the title it gives an acting officer. " + plural(all.up, "of these offices", "of these offices") +
          (all.up === 1 ? (was ? " was" : " is") : (was ? " were" : " are")) + " on the Nov 3, 2026 ballot. " +
          "Type a state with the office (") +
          searchLink(KYC.stateName("TX") + " " + name.toLowerCase()) + esc(") to see who holds it there and its 2026 race, if it has one.") }));
    return out;
  }

  /* --------------------------------------------- the federal executive */

  /* The departments' and offices' short names, by federal.js's key. */
  var ACRONYMS = { justice: ["doj"], defense: ["dod", "pentagon"], agriculture: ["usda"],
    labor: ["dol"], hhs: ["hhs"], hud: ["hud"], transportation: ["dot"], energy: ["doe"],
    homeland: ["dhs"], epa: ["epa"], omb: ["omb"], ustr: ["ustr"], dni: ["dni", "odni"],
    cia: ["cia"], sba: ["sba"], treasury: [], state: [] };
  /* Short names that are also a word or a name ("Doe", "dot", "hud"): the
   * department only typed in capitals ("DOE") or with "secretary" or
   * "department", or a search for a surname answers with a Cabinet post. */
  var WORDLIKE = { doe: 1, dot: 1, hud: 1, dol: 1 };

  var FED_FILLER = { secretary: 1, secretaries: 1, sec: 1, secy: 1, department: 1, dept: 1,
    of: 1, the: 1, us: 1, united: 1, states: 1, federal: 1, administrator: 1, director: 1,
    head: 1, agency: 1, office: 1, who: 1, is: 1, current: 1, and: 1, for: 1 };
  var FED_CUE = { secretary: 1, secretaries: 1, sec: 1, secy: 1, department: 1, dept: 1,
    administrator: 1, director: 1, head: 1, agency: 1 };

  var PRESIDENT = /^(?:president|potus|us president|president of the united states)$/;
  var VICE = /^(?:vice president|vp|vpotus|veep|vice president of the united states|president of the senate)$/;
  var CABINET = /^(?:cabinet|cabinet members?|cabinet secretar(?:y|ies)|presidents? cabinet|executive branch|white house)$/;

  function federalRow(office) {
    var h = office.holder || {};
    var role = KYC.holderRole(office);
    var title = "U.S. " + office.office;
    if (!h.id || !h.name) return row(esc(title) + ":", "nobody is named on the federal page");
    return row(esc(title) + ":", link(officialHref(h.id), (role.acting ? "Acting: " : "") + h.name) +
      (role.title ? " (" + esc(role.title) + ")" : ""));
  }

  function personRow(title, p) {
    if (!p || !p.id || !p.name) return "";
    return row(esc(title) + ":", link(officialHref(p.id), p.name));
  }

  function federalOffices(ctx) {
    if (ctx.state) return [];
    var p = phrase(trim(ctx.ws));
    var wantsFed = PRESIDENT.test(p) || VICE.test(p) || CABINET.test(p);
    var words2 = ctx.ws.filter(function (w) { return !FED_FILLER[w]; });
    var cue = ctx.ws.some(function (w) { return FED_CUE[w]; });
    if (!wantsFed && !words2.length) return [];
    if (!have("federal")) { ctx.wants.push("federal"); return []; }
    var d = fed();
    if (PRESIDENT.test(p)) {
      return [block("offices", "", [personRow("President of the United States", d.president)])];
    }
    if (VICE.test(p)) {
      return [block("offices", "", [personRow("Vice President of the United States", d.vicePresident)],
        { note: p === "president of the senate" ? esc("The Vice President is the Senate’s president.") : "" })];
    }
    if (CABINET.test(p)) {
      var rows = [personRow("President", d.president), personRow("Vice President", d.vicePresident)]
        .concat((d.offices || []).map(federalRow)).filter(Boolean);
      return [block("offices", "The President’s Cabinet", rows,
        { compact: true, more: link(root() + "federal/index.html#cabinet", "The federal government page") +
          " says who each is and how they came to the post." })];
    }
    // "Secretary of State" and "Attorney General" are the state offices'
    // too, answered with them (stateOffice).
    if (!words2.length || officeOf(trim(ctx.ws))) return [];
    var matched = (d.offices || []).filter(function (office) {
      var h = office.holder || {};
      var text = " " + words([office.office, office.body, h.title].join(" ")).join(" ") + " ";
      var acronym = (ACRONYMS[office.key] || []).some(function (a) {
        return words2.length === 1 && words2[0] === a &&
          (!WORDLIKE[a] || cue || capitalised(ctx.raw, a.toUpperCase()));
      });
      if (acronym) return true;
      var all = words2.every(function (w) { return text.indexOf(" " + w + " ") !== -1; });
      if (!all) return false;
      // A department's own word alone ("labor") is not its secretary: it
      // takes "secretary" or "department", or two words of its name.
      return cue || words2.length >= 2;
    });
    if (!matched.length) return [];
    return [block("offices", "", matched.map(federalRow))];
  }

  /* ------------------------------------------------ Congress's leaders */

  var LEADER_CUE = { speaker: 1, leader: 1, leaders: 1, whip: 1, whips: 1, tempore: 1,
    leadership: 1, tem: 1 };
  var LEADER_FORMS = { leaders: "leader", whips: "whip", tem: "tempore", dem: "democratic",
    dems: "democratic", democrat: "democratic", democrats: "democratic", gop: "republican",
    republicans: "republican" };
  var PRINCIPAL = /^(Speaker|President Pro Tempore|(House |Senate )?(Majority|Minority) (Leader|Whip))\b/;

  /* "Texas House speaker", "speaker of the Ohio House", "Nebraska majority
   * leader": this site names no state legislature's leaders (it has no
   * source for them), so the answer is the chamber's page, and says so. */
  function stateLeaders(ctx) {
    var rest = trim(ctx.rest).filter(function (w) { return !FILLER[w]; });
    if (!rest.some(function (w) { return LEADER_CUE[w] && w !== "leadership"; })) return [];
    var known = { house: 1, senate: 1, assembly: 1, delegates: 1, representatives: 1, legislature: 1,
      state: 1, majority: 1, minority: 1, floor: 1, president: 1, pro: 1, assistant: 1, deputy: 1,
      democratic: 1, democrat: 1, democrats: 1, dem: 1, dems: 1, republican: 1, republicans: 1,
      gop: 1, caucus: 1, party: 1, general: 1, lower: 1, upper: 1, chamber: 1 };
    if (!rest.every(function (w) { return LEADER_CUE[w] || known[w]; })) return [];
    if (!have("search")) { ctx.wants.push("search"); return []; }
    var chamber = rest.indexOf("senate") !== -1 || rest.indexOf("upper") !== -1 ? "upper"
      : rest.some(function (w) { return w === "house" || w === "assembly" || w === "delegates" ||
        w === "representatives" || w === "lower"; }) ? "lower" : null;
    var out = legislatureRows(ctx, chamber);
    // Said under the chamber's row, which names it first.
    out[0].more = esc("This site does not name the leaders of state legislatures: it has no source " +
      "for them. The " + (chamber ? "chamber’s" : "legislature’s") + " page lists who sits for each district.");
    return out;
  }

  function leaders(ctx) {
    if (ctx.state) return stateLeaders(ctx);
    if (!ctx.ws.some(function (w) { return LEADER_CUE[w]; })) return [];
    var ws = ctx.ws.filter(function (w) { return !FILLER[w] && w !== "congressional" && w !== "congress" &&
      w !== "party" && w !== "us"; })
      .map(function (w) { return LEADER_FORMS[w] || w; });
    var general = ws.every(function (w) { return w === "leadership" || w === "leader"; });
    var held = [];
    KYC.people().forEach(function (p) {
      if (!KYC.seated(p)) return;
      (p.leadership || []).forEach(function (title) {
        var text = " " + words(title).join(" ") + " ";
        var ok = general ? PRINCIPAL.test(title)
          : ws.every(function (w) { return text.indexOf(" " + w + " ") !== -1; });
        if (ok) held.push({ title: title, p: p });
      });
    });
    if (!held.length) return [];
    held.sort(function (a, b) {
      var rank = function (t) { return PRINCIPAL.test(t) ? 0 : 1; };
      return rank(a.title) - rank(b.title) || a.title.localeCompare(b.title);
    });
    return [block("offices", "Leaders in Congress", held.slice(0, LIMIT * 2).map(function (h) {
      return row(esc(h.title) + ":", memberLink(h.p.id, h.p.name));
    }), { note: esc("As congress-legislators records the posts held in this Congress.") })];
  }

  /* ------------------------------------------------ seats in Congress */

  function zipOf(raw) {
    var m = /\b(\d{5})(?:-\d{4})?\b/.exec(String(raw || ""));
    return m ? m[1] : "";
  }

  function zipButton(zip) {
    return '<button type="button" class="btn" data-findrep-zip="' + KYC.escapeAttr(zip) + '">' +
      "Who represents " + esc(zip) + "</button>";
  }

  function congressSeats(ctx) {
    var p = phrase(trim(ctx.rest));
    var senate = /^(?:us |federal )?(?:senators?|sens?)$/.test(p);
    var house = /^(?:us |federal )?(?:representatives?|reps?|congress ?(?:man|woman|men|women|person|people|member|members)|members? of congress|house members?)$/.test(p);
    var delegate = /^(?:non ?voting )?delegates?(?: to congress)?$/.test(p);
    var commissioner = /^resident commissioners?$/.test(p);
    if (!senate && !house && !delegate && !commissioner) return [];
    if (ctx.zip) {
      return [block("offices", "", [row(zipButton(ctx.zip), esc("Your members of Congress and your " +
        "state legislators, by the ZIP code’s districts."))])];
    }
    if (ctx.state) {
      // "Maryland delegate": a member of its House of Delegates.
      if (delegate && !have("search")) { ctx.wants.push("search"); return []; }
      var lower = (index().legislatures || {})[ctx.state];
      if (delegate && lower && /Delegates/.test(lower[2] || "")) return legislatureRows(ctx, "lower");
      return [];                        // the grid answers a state's seats
    }
    var meta = KYC.meta().states || {};
    if (delegate || commissioner) {
      var rows = KYC.people().filter(function (x) {
        return KYC.seated(x) && meta[x.state] && meta[x.state].delegateTitle &&
          (!commissioner || meta[x.state].delegateTitle === "Resident Commissioner");
      }).sort(function (a, b) { return KYC.stateName(a.state).localeCompare(KYC.stateName(b.state)); })
        .map(function (x) {
          return row(esc(meta[x.state].delegateTitle + ", " + KYC.stateName(x.state)) + ":",
            memberLink(x.id, x.name));
        });
      var also = [];
      ["MD", "VA", "WV"].forEach(function (code) {
        if ((index().legislatures || {})[code]) {
          also.push(link(root() + "legislature/" + code.toLowerCase() + ".html#/?chamber=lower",
            KYC.stateName(code)));
        }
      });
      return [block("offices", commissioner ? "The Resident Commissioner" : "Delegates in the House", rows,
        { note: esc("The District of Columbia and the territories each send one member to the House, " +
          "who votes in committee but not on the floor.") +
          (delegate && also.length ? " " + esc("A delegate in ") + andList(also) +
            esc(" is a member of the state’s House of Delegates.") : "") })];
    }
    var note = senate
      ? esc("Each state elects two U.S. senators. ") +
        link("#/?role=member&chamber=Senate", "Every sitting senator") + " · " +
        link("#/?view=senate", "the Senate by the year each seat is next decided") +
        esc(". Type a state with it (") + searchLink("Ohio senators") + esc(") for its two.")
      : esc("Each state’s House members are elected by district. ") +
        link("#/?role=member&chamber=House", "Every sitting House member") +
        esc(". Your own is found by ZIP code, under Find who represents you, or type a state (") +
        searchLink("Ohio representatives") + esc(") or a district (") + searchLink("OH-3") + esc(").");
    var rows = [];
    if (senate || house) {
      rows.push(row('<button type="button" class="btn" data-findrep-reveal>Find who represents you</button>',
        esc("by ZIP code or location.")));
    }
    return [block("offices", senate ? "U.S. senators" : "U.S. representatives", rows, { note: note })];
  }

  /* ------------------------------------------------ state legislatures */

  var LEGISLATOR = /^(?:state (?:senators?|sens?|representatives?|reps?|legislators?|lawmakers?|delegates?|assembly ?(?:members?|man|woman|men|women)?)|assembly ?(?:man|woman|men|women|members?|person|people)|assemblymembers?|legislators?|lawmakers?)$/;
  var UPPER = /^(?:state )?senate$|^upper (?:house|chamber)$/;
  var LOWER = /^(?:state )?house$|^lower (?:house|chamber)$/;
  var BODY = /^(?:state )?(?:legislature|legislatures|legislative assembly|general assembly|general court|statehouse|state house|state capitol|unicameral)$/;

  function legislatureRows(ctx, chamber) {
    var leg = (index().legislatures || {})[ctx.state];
    var name = KYC.stateName(ctx.state);
    if (!leg) {
      return [block("places", "", [row(link(statePage(ctx.state), name),
        esc("This site has no page for " + name + "’s legislature."))])];
    }
    var href = root() + "legislature/" + ctx.state.toLowerCase() + ".html";
    var what = leg[0];
    if (chamber && leg[1]) {
      href += chamber === "lower" ? "#/?chamber=lower" : "";
      what = name + " " + (chamber === "lower" ? leg[2] : leg[1]);
    }
    var rows = [row(link(href, what), esc(chamber && !leg[1]
      ? "Nebraska’s Legislature has one chamber; its members are called senators."
      : (chamber ? "A chamber of the " + leg[0] + ": its districts on a map, and who sits for each."
        : !leg[1] ? "One chamber: its districts on a map, and who sits for each."
        : "Its Senate and " + (leg[2] || "House") + " districts on a map, and who sits for each.")))];
    if (ctx.zip) rows.push(row(zipButton(ctx.zip), esc("Your state legislators by the ZIP code’s districts.")));
    return [block("places", "", rows)];
  }

  function legislatures(ctx) {
    var rest = trim(ctx.rest);
    var p = phrase(rest);
    var legislator = LEGISLATOR.test(p);
    if (!legislator && !UPPER.test(p) && !LOWER.test(p) && !BODY.test(p) &&
        !/^(?:house of representatives|house of delegates|assembly|general assembly|state assembly)$/.test(p)) {
      return [];
    }
    if (!have("search")) { ctx.wants.push("search"); return []; }
    var legs = index().legislatures || {};
    if (ctx.state) {
      var leg = legs[ctx.state] || [];
      var lowerName = phrase(words(leg[2] || ""));
      var chamber = null;
      if (UPPER.test(p) || /senators?|sens?$/.test(p)) chamber = "upper";
      else if (LOWER.test(p) || p === lowerName || /representatives?|reps?$|assembly ?(?:man|woman|men|women|members?)|delegates?$/.test(p) ||
               (p === "house of representatives") || (p === "assembly" && /Assembly/.test(leg[2] || "")) ||
               (p === "house of delegates" && /Delegates/.test(leg[2] || ""))) chamber = "lower";
      if (BODY.test(p) && !(p === "general assembly" && /General Assembly/.test(leg[2] || ""))) chamber = null;
      if (legislator && /legislators?|lawmakers?/.test(p)) chamber = null;
      var out = legislatureRows(ctx, chamber);
      // "Texas House" is also Texas's seats in the U.S. House: the cards.
      if (chamber && !legislator && /^(?:house|senate|house of representatives)$/.test(p)) {
        out[0].note = esc("The state legislature’s chamber. " + KYC.stateName(ctx.state) +
          "’s seats in the U.S. " + (chamber === "upper" ? "Senate" : "House") + " are the cards below.");
      }
      return out;
    }
    if (ctx.zip && legislator) {
      return [block("places", "", [row(zipButton(ctx.zip),
        esc("Your state legislators by the ZIP code’s districts."))])];
    }
    var pick = function (test) {
      return Object.keys(legs).filter(function (code) { return test(legs[code]); }).sort()
        .map(function (code) {
          return row(link(root() + "legislature/" + code.toLowerCase() + ".html" +
            (test.lower ? "#/?chamber=lower" : ""), legs[code][0]),
          test.lower ? esc("its " + legs[code][2]) : "");
        });
    };
    var named = function (title, test, note) {
      return [block("places", title, pick(test), { compact: true, note: note || "" })];
    };
    if (p === "general assembly") {
      var lowerGA = function (leg) { return leg[2] === "General Assembly"; };
      lowerGA.lower = true;
      return named("Legislatures called the General Assembly",
        function (leg) { return /General Assembly$/.test(leg[0]); })
        .concat(named("A lower chamber called the General Assembly", lowerGA));
    }
    if (p === "general court") return named("Legislatures called the General Court", function (leg) { return /General Court$/.test(leg[0]); });
    if (p === "legislative assembly") return named("Legislatures called the Legislative Assembly", function (leg) { return /Legislative Assembly$/.test(leg[0]); });
    if (p === "unicameral") return named("The one-chamber legislature", function (leg) { return !leg[1]; });
    if (p === "house of delegates" || p === "assembly" || p === "state assembly") {
      var word = p === "house of delegates" ? "House of Delegates" : "Assembly";
      var test = function (leg) { return leg[2] === word; };
      test.lower = true;
      return named("Lower chambers called the " + word, test);
    }
    return [block("places", "State legislatures", [row(link(root() + "legislature/index.html",
      "Every state legislature"), esc("each with its districts on a map and who sits for each."))],
      { note: esc("Type a state with it (") + searchLink("Texas House") + esc(", ") +
        searchLink("Ohio state senators") + esc(") or a ZIP code (") + searchLink("state senator 43215") +
        esc(") for your own.") })];
  }

  /* ------------------------------------------------------------- local */

  var LOCAL = new RegExp("\\b(?:" + [
    "mayors?", "city councils?", "council ?(?:members?|man|woman|men|women)", "councilors?",
    "aldermen", "alderman", "alderwoman", "alderpersons?", "county commissioners?",
    "commissioners court", "county commission", "county executives?", "county judges?",
    "county clerks?", "county treasurers?", "county assessors?", "sheriffs?", "school boards?",
    "boards? of education", "school board members?", "school districts?",
    "school superintendents?", "city managers?", "town councils?", "select ?boards?",
    "selectmen", "township trustees?", "district attorneys?", "county attorneys?", "coroners?",
    "constables?", "justices? of the peace", "city officials?", "local officials?",
    "local governments?", "local elections?", "city government", "county government",
    "town government",
  ].join("|") + ")\\b");

  function local(ctx, counties) {
    var p = phrase(ctx.ws);
    if (!LOCAL.test(p)) return [];
    var where;
    if (ctx.state && have("search") && !(index().counties || {})[ctx.state]) {
      // The District and the territories have no county page here.
      return [block("offices", "Local offices", [], { note: esc("This site names no local officials, " +
        "and has no county page for " + placeWords(ctx.state) + ". ") +
        link(statePage(ctx.state), PlaceWords(ctx.state) + "’s page") + esc(" lists what it does cover.") })];
    }
    if (counties.length === 1) {
      where = link(counties[0].href, counties[0].name.replace(/,.*$/, "") + "’s page");
    } else if (ctx.state && (index().counties || {})[ctx.state]) {
      where = link(root() + "counties/" + ctx.state.toLowerCase() + ".html", KYC.stateName(ctx.state) +
        "’s county page");
    } else {
      where = link(root() + "counties/index.html", "Each state’s county page");
    }
    // Most local governments have no website in the Census listing, and a
    // listed one is linked only once checked (rule 78).
    return [block("offices", "Local offices", [], { note: esc("This site names no local officials: no " +
      "mayors, councils, county officers, sheriffs or school boards. ") + where +
      esc(" lists every local government the Census Bureau records there (cities, towns, school " +
        "districts and others), with its website where the Census listing gives one, checked before " +
        "it is linked.") })];
  }

  /* ---------------------------------------------------------- counties */

  // The words that make a query a county's, and the word a name of that
  // kind ends in.
  var COUNTY_CUE = { county: "county", counties: "county", parish: "parish", parishes: "parish",
    borough: "borough", boroughs: "borough", municipality: "municipality",
    municipio: "municipio", municipios: "municipio" };
  var COUNTY_SUFFIX = / (?:county|parish|borough|census area|city and borough|municipality|planning region)$/;

  /** A county's name as a search compares it: "St. Louis County" and
   *  "Saint Louis" are "stlouis", "DeKalb" and "De Kalb" "dekalb". */
  function countyKey(name) {
    var p = phrase(words(name)).replace(COUNTY_SUFFIX, "").replace(/^(?:city|municipality|town) of /, "")
      .replace(/\bsaint\b/g, "st").replace(/\bsainte\b/g, "ste");
    return p.replace(/ /g, "");
  }

  var countyKeys = null;
  function countyIndex() {
    if (countyKeys) return countyKeys;
    countyKeys = {};
    var all = index().counties || {};
    Object.keys(all).forEach(function (code) {
      all[code].forEach(function (c) {
        var key = countyKey(c[1]);
        (countyKeys[key] = countyKeys[key] || []).push({ code: code, fips: c[0], name: c[1] });
      });
    });
    return countyKeys;
  }

  /** The counties *ctx* names, `[{code, fips, name, href}]`, and the
   *  answer's blocks. */
  /* "Texas county judge", "Ohio county commissioner": the state's local
   * offices, never Texas County, Missouri or Ohio County, Kentucky. */
  var COUNTY_OFFICE = /^(?:county|parish|borough) (?:commissioners?|commission|executives?|judges?|clerks?|treasurers?|assessors?|attorneys?|sheriffs?|officials?|officers?|offices?|governments?|boards?|councils?)\b/;

  /** The counties named *ws* exactly, `[{code, fips, name, href}]`. */
  function countiesNamed(ws, code) {
    return (countyIndex()[countyKey(phrase(ws))] || []).filter(function (c) {
      return !code || c.code === code;
    });
  }

  function countyBlocks(found) {
    found = found.map(function (c) {
      return { code: c.code, fips: c.fips, name: c.name + ", " + KYC.stateName(c.code),
               href: root() + "counties/" + c.code.toLowerCase() + ".html#/?county=" + encodeURIComponent(c.fips) };
    }).sort(function (a, b) { return a.name.localeCompare(b.name); });
    if (!found.length) return { found: [], blocks: [] };
    return { found: found, blocks: [block("places", found.length > 1 ? plural(found.length, "county", "counties") +
      " of that name" : "", found.slice(0, LIMIT * 3).map(function (c) {
        return row(link(c.href, c.name), esc("its local governments on a map, with the website the " +
          "Census listing gives, where it gives one, checked before it is linked."));
      }), { compact: found.length > 4 })] };
  }

  function counties(ctx) {
    var at = -1;
    for (var i = 0; i < ctx.ws.length; i++) if (COUNTY_CUE[ctx.ws[i]]) { at = i; break; }
    if (at < 0) {
      // A county's name alone ("Dallas"), only where no profile answers it:
      // a surname is the usual one-word search, and many are counties'.
      var bare = trim(ctx.ws);
      if (!ctx.alone || !bare.length || bare.length > 3) return { found: [], blocks: [] };
      if (!have("search")) { ctx.wants.push("search"); return { found: [], blocks: [] }; }
      return countyBlocks(ctx.state ? countiesNamed(trim(ctx.rest), ctx.state) : countiesNamed(bare, null));
    }
    if (!have("search")) { ctx.wants.push("search"); return { found: [], blocks: [] }; }
    var before = trim(ctx.ws.slice(0, at));
    var after = ctx.ws.slice(at + 1);
    var keys = countyIndex();
    var listOf = function (code) {
      if (code && (index().counties || {})[code]) {
        return { found: [], blocks: [block("places", "", [row(link(root() + "counties/" + code.toLowerCase() + ".html",
          KYC.stateName(code) + "’s counties and local governments"), esc("every county on a map, and every " +
          "local government in each."))])] };
      }
      return { found: [], blocks: [block("places", "", [row(link(root() + "counties/index.html",
        "Counties and local governments"), esc("each state’s counties, and every local government in each."))])] };
    };
    // "Texas counties" is Texas's list; "Texas County" is a county (in
    // Missouri, and in Oklahoma).
    var wholeState = before.length ? findState(before, ctx.raw) : null;
    if (/s$/.test(ctx.ws[at]) && wholeState && wholeState.at === 0 && wholeState.len === before.length) {
      return listOf(wholeState.code);
    }
    // "County judge", "county commissioners": the local offices' answer.
    if (!before.length && LOCAL.test(phrase(ctx.ws))) return { found: [], blocks: [] };
    if (wholeState && wholeState.at === 0 && wholeState.len === before.length &&
        COUNTY_OFFICE.test(phrase(ctx.ws.slice(at)))) return { found: [], blocks: [] };
    var tries = [];
    // "Cook County, IL", "Travis County Texas commissioner": the state after.
    var stateAfter = findState(after, ctx.raw);
    // "Texas Travis County": a state before, where what follows it names one.
    var stateBefore = before.length > 1 ? findState(before, ctx.raw) : null;
    if (stateBefore && stateBefore.at === 0) {
      tries.push({ name: before.slice(stateBefore.len), code: stateBefore.code });
    }
    tries.push({ name: before, code: stateAfter ? stateAfter.code : null });
    var found = [];
    for (var t = 0; t < tries.length && !found.length; t++) {
      if (!tries[t].name.length) continue;
      var key = countyKey(phrase(tries[t].name));
      found = (keys[key] || []).filter(function (c) { return !tries[t].code || c.code === tries[t].code; });
    }
    // "Orleans Parish" is Louisiana's, not Orleans County, New York; "St.
    // Louis County" the counties, before the City of St. Louis.
    var kindOf = new RegExp(" " + COUNTY_CUE[ctx.ws[at]] + "$", "i");
    var sameKind = found.filter(function (c) { return kindOf.test(c.name); });
    if (sameKind.length) found = sameKind;
    if (found.length) return countyBlocks(found);
    // "Counties", "Texas county": the state's page, or every state's.
    var code = (stateAfter || wholeState || {}).code || ctx.state;
    if (!before.length || (wholeState && wholeState.at === 0 && wholeState.len === before.length)) {
      return listOf(code);
    }
    return { found: [], blocks: [block("places", "", [], { note: esc("No county called " +
      phrase(before) + (stateAfter ? " in " + KYC.stateName(stateAfter.code) : "") + " is on this site’s " +
      "county pages, which cover the 50 states. ") + link(root() + "counties/index.html",
      "Every state’s counties") + "." })] };
  }

  /* ------------------------------------------------------- committees */

  var COMMITTEE_FILLER = { committee: 1, committees: 1, cmte: 1, comm: 1, on: 1, the: 1, of: 1,
    us: 1, congressional: 1, congress: 1, permanent: 1, select: 1, special: 1, and: 1, to: 1 };
  var CHAMBER_WORD = { house: "house", senate: "senate", joint: "joint" };

  /** "Senate Committee on Armed Services" -> "armed services". */
  function committeeCore(name) {
    return phrase(words(name)).replace(/^(?:united states )?(?:house |senate )?/, "")
      .replace(/^(?:(?:permanent|select|special|joint) )*(?:committee|caucus|commission|subcommittee)(?: of congress)? (?:on|to|of) (?:the )?/, "")
      .replace(/ committee$/, "").replace(/^joint /, "");
  }

  function committees(ctx) {
    if (ctx.state) return [];
    var cue = ctx.ws.some(function (w) { return w === "committee" || w === "committees" || w === "cmte"; });
    var chamber = null;
    var ws = [];
    ctx.ws.forEach(function (w) {
      if (CHAMBER_WORD[w]) chamber = CHAMBER_WORD[w];
      else if (!COMMITTEE_FILLER[w] && !FILLER[w]) ws.push(w);
    });
    if (!ws.length) {
      if (!cue) return [];
      return [block("places", "", [row(link(root() + "government/congress.html#committees",
        "Congress’s committees"), esc("each with its chair and minority lead."))])];
    }
    if (!have("search")) { ctx.wants.push("search"); return []; }
    var rows = (index().committees || []).filter(function (c) {
      if (chamber && c[2] !== chamber) return false;
      var core = committeeCore(c[1]);
      var coreWords = core.split(" ").filter(function (w) { return w !== "and"; });
      var text = " " + coreWords.join(" ") + " ";
      if (!ws.every(function (w) { return text.indexOf(" " + w + " ") !== -1; })) return false;
      // Without "committee", only its name: "armed services", "budget",
      // "small business" - never one word of a longer name ("education").
      return cue || ws.length === coreWords.length || (ws.length >= 2 && coreWords.join(" ").indexOf(ws.join(" ")) === 0);
    });
    if (!rows.length) return [];
    var who = function (list, word) {
      if (!list.length) return "";
      return word + " " + list.map(function (m) { return memberLink(m[0], m[1]); }).join(", ");
    };
    return [block("places", rows.length > 1 ? "Committees of Congress" : "", rows.slice(0, LIMIT).map(function (c) {
      var lead = [who(c[3], "Chair:"), who(c[4], "Minority lead:")].filter(Boolean).join("; ");
      return row(link(root() + "government/congress.html#committee-" + c[0], c[1]), lead);
    }), { note: rows.length > 1 || !cue ? "" : "" })];
  }

  /* ------------------------------------------------- tribal governments */

  var TRIBE_CUE = { tribe: 1, tribes: 1, tribal: 1, nation: 1, nations: 1, band: 1, bands: 1,
    pueblo: 1, pueblos: 1, rancheria: 1, indian: 1, indians: 1, reservation: 1, community: 1,
    village: 1, chapter: 1, native: 1 };
  var TRIBE_GENERAL = { tribe: 1, tribes: 1, tribal: 1, nation: 1, nations: 1, native: 1,
    american: 1, americans: 1, indian: 1, indians: 1, government: 1, governments: 1,
    leader: 1, leaders: 1, sovereign: 1 };

  function tribalHref(code) {
    return root() + "government/tribal.html#/?state=" + encodeURIComponent(code) + "&mode=tribes";
  }

  function tribal(ctx) {
    var cue = ctx.ws.some(function (w) { return TRIBE_CUE[w]; });
    var ws = ctx.ws.filter(function (w) { return !FILLER[w]; });
    if (!ws.length) return [];
    // One word with no cue ("Cherokee") only where no profile answers it.
    if (!cue && ws.length < 2 && !ctx.alone) return [];
    var rest = trim(ctx.rest).filter(function (w) { return !FILLER[w]; });
    if (cue && rest.every(function (w) { return TRIBE_GENERAL[w]; })) {
      if (!ctx.state) {
        return [block("places", "", [row(link(root() + "government/tribal.html", "Tribal governments"),
          esc("how tribal nations govern themselves, and each government’s leader, by state."))])];
      }
      return [block("places", "", [row(link(tribalHref(ctx.state), "Tribal governments listed in " +
        KYC.stateName(ctx.state)), esc("each with its leader, as the BIA’s directory lists them."))])];
    }
    if (!have("search")) { ctx.wants.push("search"); return []; }
    var all = index().tribes || {};
    var hits = [];
    var q = phrase(ws);
    Object.keys(all).forEach(function (code) {
      all[code].forEach(function (t) {
        var name = words(t[0]);
        var text = " " + name.join(" ") + " ";
        if (phrase(name) === q || ((cue || ws.length >= 2 || ctx.alone) &&
            ws.every(function (w) { return text.indexOf(" " + w + " ") !== -1; }))) {
          hits.push({ code: code, t: t });
        }
      });
    });
    if (!hits.length) return [];
    hits.sort(function (a, b) { return a.t[0].localeCompare(b.t[0]); });
    return [block("places", hits.length > 1 ? "Tribal governments" : "", hits.slice(0, LIMIT).map(function (h) {
      var t = h.t;
      var leader = t[1] ? esc(t[1] + (t[2] ? ", " + t[2] : "")) + (t[3] ? " (leadership disputed)" : "")
        : "no leader listed";
      return row(link(tribalHref(h.code), t[0]), esc("listed in " + KYC.stateName(h.code) +
        (t[4] ? ", under " + t[4] : "") + "; ") + leader);
    }), { note: esc("As the Bureau of Indian Affairs’ Tribal Leaders Directory lists them, with the " +
      "leader it names."), more: hits.length > LIMIT ? esc((hits.length - LIMIT) + " more on the " +
      "tribal governments page.") : "" })];
  }

  /* ------------------------------------------------------------- courts */

  var ORDINALS = { first: "1", "1st": "1", second: "2", "2nd": "2", third: "3", "3rd": "3",
    fourth: "4", "4th": "4", fifth: "5", "5th": "5", sixth: "6", "6th": "6", seventh: "7",
    "7th": "7", eighth: "8", "8th": "8", ninth: "9", "9th": "9", tenth: "10", "10th": "10",
    eleventh: "11", "11th": "11", dc: "dc", federal: "fc", fed: "fc" };
  for (var n = 1; n <= 11; n++) ORDINALS[String(n)] = String(n);
  var DIRECTIONS = { northern: "n", north: "n", n: "n", southern: "s", south: "s", s: "s",
    eastern: "e", east: "e", e: "e", western: "w", west: "w", w: "w", middle: "m", mid: "m",
    m: "m", central: "c", c: "c" };
  var COURT_FILLER = { us: 1, united: 1, states: 1, federal: 1, court: 1, courts: 1, of: 1,
    for: 1, the: 1, judge: 1, judges: 1, judicial: 1, in: 1 };

  function courtsById() {
    var out = {};
    (fed().courts || []).forEach(function (c) { out[c.id] = c; });
    return out;
  }

  function courtRow(c) {
    var detail = c.kind === "supreme" ? "the nine justices"
      : (c.active !== undefined ? plural(c.active, "active judge", "active judges") +
        (c.senior ? ", " + plural(c.senior, "on senior status", "on senior status") : "") : "");
    return row(link(root() + "courts/" + c.id + ".html", c.name), esc(detail));
  }

  /** The district courts *code* has, by their ids: "tx-e", or "nj". */
  function districtsOf(code) {
    var lower = code.toLowerCase();
    return (fed().courts || []).filter(function (c) {
      return c.kind !== "appeals" && c.kind !== "supreme" && c.kind !== "trade" &&
        (c.id === lower || c.id.indexOf(lower + "-") === 0);
    });
  }

  /** `{court, list}` for a district court *ws* names, compact or in full. */
  function districtCourt(ws, raw) {
    var p = phrase(ws);
    // "sdny", "ed tex", "ndcal", "d mass", "D.D.C.", "D.N.J."
    var compact = /^([nsewmc])?d ?([a-z]{2}|[a-z]{2,5}(?: [a-z]{2,4})?)$/.exec(p);
    var dir = null;
    var st = null;
    if (compact) {
      var tail = compact[2];
      var code = /^[a-z]{2}$/.test(tail) && (KYC.meta().states || {})[tail.toUpperCase()]
        ? tail.toUpperCase() : KYC.stateAbbreviation(tail, false) || KYC.stateNamed(tail);
      // With no direction, a state of one district only, written as a
      // court is ("D.N.J.", "DNJ", "D. Mass."): "dnc" is the party's
      // committee, never North Carolina's three courts.
      var single = code && districtsOf(code).length === 1 &&
        (/\./.test(raw) || /(^|[^A-Za-z])D/.test(String(raw)) || tail.length > 2);
      if (code && (compact[1] || single || !have("federal"))) { dir = compact[1] || ""; st = code; }
    }
    if (!st) {
      var found = findState(ws, raw);
      if (!found) return null;
      var rest = without(ws, found.at, found.len);
      if (rest.indexOf("district") === -1 && rest.indexOf("districts") === -1 && rest.indexOf("dist") === -1) {
        return null;
      }
      dir = "";
      var courtWord = false;
      var other = rest.filter(function (w) {
        if (w === "district" || w === "districts" || w === "dist") return false;
        if (COURT_FILLER[w]) { courtWord = courtWord || w !== "the" && w !== "in"; return false; }
        if (DIRECTIONS[w] && w.length > 1 && !dir) { dir = DIRECTIONS[w]; return false; }
        return true;
      });
      if (other.length) return null;
      // "Ohio district" is as likely a seat in Congress: a court is named
      // by its direction, "court", or "District of".
      if (!dir && !courtWord && !/district of/.test(p)) return null;
      st = found.code;
    }
    var courts = districtsOf(st);
    if (!courts.length) return { list: [], code: st };
    if (dir) {
      var one = courts.filter(function (c) { return c.id === st.toLowerCase() + "-" + dir; });
      return { list: one.length ? one : courts, code: st, missed: !one.length };
    }
    return { list: courts, code: st };
  }

  function courts(ctx) {
    var ws = ctx.ws;
    var p = phrase(trim(ws));
    var out = [];
    var needFed = function () { if (!have("federal")) { ctx.wants.push("federal"); return true; } return false; };

    // The Supreme Court, its justices and its chief.
    var scotus = /^(?:scotus|(?:us |united states )?supreme court(?: of the united states)?|the supreme court|us high court)$/.test(p);
    var justices = /^(?:(?:us |supreme court |scotus )?justices?|(?:us )?supreme court justices?)$/.test(p);
    var chief = /^(?:(?:us )?chief justice(?: of the united states)?)$/.test(p);
    if (!ctx.state && (scotus || justices || chief)) {
      if (needFed()) return out;
      var d = fed();
      var members = ((d.supremeCourt || {}).members || []);
      var court = courtsById().scotus;
      if (chief) {
        var c = members.filter(function (j) { return j.justice && j.justice.role === "Chief Justice"; })[0];
        if (c) out.push(block("courts", "", [row(esc("Chief Justice of the United States:"), link(officialHref(c.id), c.name))]));
      } else {
        out.push(block("courts", "", (court ? [courtRow(court)] : []).concat(members.map(function (j) {
          return row(link(officialHref(j.id), j.name), esc(((j.justice && j.justice.role) || "Justice")));
        })), { compact: true }));
      }
      out.push(block("courts", "", [], { note: esc("Each state’s highest court is on its state’s page: type " +
        "the state with it (") + searchLink("Ohio Supreme Court") + esc(").") }));
      return out;
    }

    // A state's highest court.
    if (ctx.state) {
      var r = phrase(trim(ctx.rest));
      var sc = /^(?:state )?(?:supreme court|high court|highest court|court of last resort|supreme judicial court|court of appeals|supreme court justices?|justices?|chief justice)$/.test(r);
      if (sc) {
        if (!have("stategov")) { ctx.wants.push("stategov"); return out; }
        var info = gov()[ctx.state];
        var hc = info && info.court;
        if (!hc || !hc.name) {
          out.push(block("courts", "", [row(link(statePage(ctx.state, "state-government"), KYC.stateName(ctx.state)),
            esc("this site names no members of its highest court."))]));
          return out;
        }
        // What the state page says (kyc-stategov.js courtBlock): a court
        // whose roster could not be read is said so, and nothing about who
        // sits on it or who is chief (rules 19 and 57).
        var chiefTitle = hc.word === "judges"
          ? (/Criminal/.test(hc.name) ? "Presiding Judge" : "Chief Judge") : "Chief Justice";
        var members = hc.members || [];
        var detail;
        if (hc.unreadable || !members.length) {
          detail = (hc.unreadable || "This site has not read the court’s roster") +
            ", so its members are not listed here.";
        } else if (/chief|presiding/.test(r)) {
          detail = hc.chief ? chiefTitle + ": " + hc.chief + ", as the court’s roster names its chief."
            : "The court’s roster, as read, lists no " + chiefTitle.toLowerCase() + ".";
        } else {
          var short = (hc.seats || 0) - members.length;
          detail = plural(members.length, "member", "members") + " listed by the court" +
            (hc.seats ? ", of " + hc.seats + " seats" + (short > 0 ? "; " + short + " with nobody listed" : "") : "") + ".";
        }
        var typedName = r.replace(/^state /, "");
        var otherName = /^(?:supreme court|court of appeals|supreme judicial court)$/.test(typedName) &&
          phrase(words(hc.name)) !== typedName;
        out.push(block("courts", "", [row(link(statePage(ctx.state, "state-government"),
          KYC.stateName(ctx.state) + "’s highest court, the " + hc.name), esc(detail))],
          { note: otherName ? esc(KYC.stateName(ctx.state) + "’s highest court is its " + hc.name + ". A court " +
            "called what you typed, if " + placeWords(ctx.state) + " has one, is a lower court this site " +
            "does not cover.") : "" }));
        return out;
      }
    }

    // Courts of appeals: "Fifth Circuit", "5th Cir.", "D.C. Circuit",
    // "Federal Circuit", "Ninth Circuit Court of Appeals".
    var circuit = ws.indexOf("circuit") !== -1 || ws.indexOf("cir") !== -1 || ws.indexOf("circuits") !== -1;
    if (circuit) {
      var ord = null;
      for (var i = 0; i < ws.length; i++) {
        var w = ws[i];
        if (w === "federal" || w === "fed") {
          if (ws[i + 1] === "circuit" || ws[i + 1] === "cir") ord = "fc";
        } else if (!ord && ORDINALS[w]) {
          ord = ORDINALS[w];
        }
      }
      // "D.C. Circuit" names the District as a state.
      if (!ord && ctx.state === "DC") ord = "dc";
      var others = trim(ctx.rest).filter(function (w2) {
        return !ORDINALS[w2] && !COURT_FILLER[w2] && w2 !== "circuit" && w2 !== "circuits" &&
          w2 !== "cir" && w2 !== "appeals" && w2 !== "fed";
      });
      if (!others.length || ord) {
        if (needFed()) return out;
        var byId = courtsById();
        var id = ord === "dc" ? "cadc" : ord === "fc" ? "cafc" : ord ? "ca" + ord : null;
        if (id && byId[id]) {
          // Said under the court's row, which names it first.
          out.push(block("courts", "", [courtRow(byId[id])], { more: byId[id].states && byId[id].states.length
            ? esc("It hears appeals from the federal courts in " + andList(byId[id].states.map(placeWords)) + ".")
            : "" }));
          return out;
        }
        if (ctx.state && ctx.state !== "DC") {
          // "Texas circuit": the federal court of appeals over its courts.
          // A state's own circuit courts are trial courts, not covered here.
          var mine = (fed().courts || []).filter(function (c) {
            return c.kind === "appeals" && (c.states || []).indexOf(ctx.state) !== -1;
          });
          if (mine.length) {
            out.push(block("courts", "", mine.map(courtRow), { note: esc("The federal court of appeals for " +
              KYC.stateName(ctx.state) + ". A state’s own circuit courts, where it has them, are trial " +
              "courts this site does not cover.") }));
          }
          return out;
        }
        var all = (fed().courts || []).filter(function (c) { return c.kind === "appeals"; });
        out.push(block("courts", "The courts of appeals", all.map(courtRow), { compact: true }));
        return out;
      }
    }
    if (!ctx.state && /^(?:us |federal )?(?:courts? of appeals|appeals courts?|appellate courts?|circuit courts?)$/.test(p)) {
      if (needFed()) return out;
      out.push(block("courts", "The courts of appeals", (fed().courts || []).filter(function (c) {
        return c.kind === "appeals";
      }).map(courtRow), { compact: true }));
      return out;
    }
    if (/^(?:us |)?court of international trade$|^international trade court$|^cit$/.test(p)) {
      if (needFed()) return out;
      var cit = courtsById().cit;
      if (cit) out.push(block("courts", "", [courtRow(cit)]));
      return out;
    }

    // District courts: "Eastern District of Texas", "S.D.N.Y.", "D. Mass."
    var district = districtCourt(trim(ws), ctx.raw);
    if (district) {
      if (needFed()) return out;
      district = districtCourt(trim(ws), ctx.raw);
      if (!district) return out;
      if (!district.list.length) {
        out.push(block("courts", "", [], { note: esc(KYC.stateName(district.code) + " has no federal district " +
          "court of its own on this site’s list.") }));
        return out;
      }
      out.push(block("courts", district.list.length > 1 ? "Federal district courts in " + KYC.stateName(district.code) : "",
        district.list.map(courtRow), { note: district.missed ? esc(KYC.stateName(district.code) +
          " has no district of that name; its federal district " + (district.list.length > 1 ? "courts are" : "court is") + ":") : "" }));
      return out;
    }

    // "Texas federal courts", "federal judges in Ohio".
    if (ctx.state && /^(?:federal |us )?(?:courts?|judges?|judiciary|federal court system)$|^(?:federal|us) (?:courts?|judges?)$/.test(phrase(trim(ctx.rest))) &&
        /federal|us|judges?/.test(phrase(ctx.rest))) {
      if (needFed()) return out;
      var here = (fed().courts || []).filter(function (c) {
        return (c.kind === "appeals" && (c.states || []).indexOf(ctx.state) !== -1) ||
          districtsOf(ctx.state).indexOf(c) !== -1;
      });
      if (here.length) {
        out.push(block("courts", "Federal courts for " + KYC.stateName(ctx.state), here.map(courtRow), {
          note: esc("Each court’s page lists its judges. " + KYC.stateName(ctx.state) + "’s own highest court is on ") +
            link(statePage(ctx.state, "state-government"), "its state page") + "." }));
      }
      return out;
    }
    return out;
  }

  /* --------------------------------------------- too broad to answer */

  function narrow(ctx) {
    if (ctx.state) return [];
    var p = phrase(trim(ctx.ws));
    var judge = /^(?:judges?|federal judges?|us judges?|district judges?|circuit judges?|federal courts?|courts?|judiciary|federal judiciary|judicial branch)$/.test(p);
    var secretary = /^(?:secretar(?:y|ies)|cabinet secretar(?:y|ies)|department|departments)$/.test(p);
    var official = /^(?:officials?|elected officials?|government|office ?holders?|politicians?|offices?)$/.test(p);
    if (!judge && !secretary && !official) return [];
    if (judge) {
      if (!have("federal")) ctx.wants.push("federal");
      return [block("narrow", "", [
        row(link(root() + "federal/index.html#courts", "Find a federal judge by name"),
          esc("every sitting federal judge, on the federal page.")),
      ], { note: esc("The federal page lists " + (fed().judges ? fed().judges.toLocaleString() + " " : "") +
        "sitting federal judges, too many to list here. Try a judge’s name, a court (") +
        searchLink("Fifth Circuit") + ", " + searchLink("Eastern District of Texas") + ", " +
        searchLink("Supreme Court") + esc("), or a state’s courts (") + searchLink("Texas federal courts") +
        ", " + searchLink("Ohio Supreme Court") + esc(").") })];
    }
    if (secretary) {
      return [block("narrow", "", [], { note: esc("Try the department (") + searchLink("Secretary of Labor") +
        ", " + searchLink("Treasury Secretary") + esc("), the whole ") + searchLink("Cabinet") +
        esc(", or a state’s officer (") + searchLink("Ohio secretary of state") + esc(").") })];
    }
    return [block("narrow", "", [], { note: esc("Try an office (") + searchLink("governor") + ", " +
      searchLink("Texas AG") + ", " + searchLink("Speaker") + ", " + searchLink("Cabinet") +
      esc("), a place (") + searchLink("Travis County") + ", " + searchLink("Texas House") +
      esc("), a court (") + searchLink("Fifth Circuit") + esc(") or a ZIP code.") })];
  }

  /* --------------------------------------------------- ballot questions */

  var MEASURE_FORMS = { prop: "proposition", props: "proposition", propositions: "proposition",
    amendments: "amendment", amend: "amendment", issues: "issue", questions: "question",
    measures: "measure", initiatives: "initiative", referendums: "referendum",
    referenda: "referendum", proposals: "proposal", one: "1", two: "2", three: "3", four: "4",
    five: "5", six: "6", seven: "7", eight: "8", nine: "9", ten: "10", eleven: "11",
    twelve: "12" };
  var MEASURE_KIND = { proposition: 1, amendment: 1, issue: 1, question: 1, measure: 1,
    initiative: 1, referendum: 1, proposal: 1 };
  var MEASURE_DROP = { no: 1, number: 1, num: 1, nbr: 1, the: 1, ballot: 1, statewide: 1, on: 1 };

  function measureWords(text) {
    var out = [];
    // "3.5%" is one figure, never the number 3 (a rate in North Carolina's
    // question is not its "Amendment 3").
    words(String(text || "").replace(/(\d)[.,](\d)/g, "$1p$2")).forEach(function (w) {
      if (w === "sq") { out.push("state", "question"); return; }
      w = MEASURE_FORMS[w] || w;
      if (!MEASURE_DROP[w]) out.push(w);
    });
    return out;
  }

  function measureAnchor(code, i) {
    return statePage(code, "measure-" + code + "-" + i);
  }

  function ballotQuestions(ctx) {
    var raw = ctx.state ? ctx.rest : ctx.ws;
    var qs = measureWords(phrase(raw));
    var kinds = qs.filter(function (w) { return MEASURE_KIND[w]; });
    var ids = qs.filter(function (w, i) {
      return /\d/.test(w) || (i > 0 && MEASURE_KIND[qs[i - 1]] && /^[a-z]{1,2}$/.test(w));
    });
    // "IP26-645", "CI-132", "I-194": a designation of letters and a number,
    // matched only whole. Never "OH 9", which is a seat.
    var coded = !kinds.length && !ctx.state && qs.length === 2 && /^[a-z]{1,4}\d*$/.test(qs[0]) &&
      /^\d+$/.test(qs[1]);
    var mixed = coded || qs.some(function (w) { return /[a-z]/.test(w) && /\d/.test(w); });
    var ballotWord = ctx.ws.indexOf("ballot") !== -1 || ctx.ws.indexOf("statewide") !== -1;
    if (!kinds.length && !mixed) return [];
    if (!kinds.length && !ids.length) return [];
    if (!have("measures")) { ctx.wants.push("measures"); return []; }
    var all = global.kycMeasures || {};
    var was = past();
    // Only a list the site read answers for a question (rule 19): where it
    // found no official list (`has` null), it says nothing of what is or
    // is not on the ballot, as the state's page does (kyc-ballot.js).
    var codes = (ctx.state ? [ctx.state] : Object.keys(all)).filter(function (c) { return all[c]; });
    var listed = codes.filter(function (c) { return all[c].has === true; }).sort(function (a, b) {
      return KYC.stateName(a).localeCompare(KYC.stateName(b));
    });
    var unread = Object.keys(all).filter(function (c) { return all[c] && all[c].has !== true && all[c].has !== false; })
      .sort(function (a, b) { return KYC.stateName(a).localeCompare(KYC.stateName(b)); });
    var stateRec = ctx.state ? all[ctx.state] : null;
    var noList = function (code) {
      return esc("This site " + (was ? "did not find" : "has not found") + " an official list of " + placeWords(code) + "’s statewide " +
        "questions on the Nov 3, 2026 ballot, and does not say there " + (was ? "were" : "are") + " none. ") +
        link(statePage(code, "measures"), PlaceWords(code) + "’s page") + esc(" links its election office.");
    };
    if (ctx.state && (!stateRec || (stateRec.has !== true && stateRec.has !== false))) {
      return [block("measures", "", [], { note: noList(ctx.state) })];
    }
    if (!ids.length) {
      // "ballot measures", "Ohio issues", "propositions": a state's list.
      var strong = qs.some(function (w) { return w === "proposition" || w === "initiative" || w === "referendum"; });
      if (!ctx.state && !ballotWord && !strong) return [];
      if (qs.some(function (w) { return !MEASURE_KIND[w] && w !== "state" && w !== "constitutional"; })) return [];
      if (ctx.state) {
        return [block("measures", "", [row(link(statePage(ctx.state, "measures"), KYC.stateName(ctx.state) +
          "’s ballot questions"), esc(stateRec.has === true
            ? plural((stateRec.measures || []).length, "statewide question", "statewide questions") +
              " on the Nov 3, 2026 ballot."
            : "No statewide question " + (was ? "was" : "is") + " on the Nov 3, 2026 ballot; its page " +
              "cites the election office for it."))])];
      }
      return [block("measures", "Statewide questions on the Nov 3, 2026 ballot", listed.map(function (c) {
        return row(link(statePage(c, "measures"), KYC.stateName(c)), esc(plural((all[c].measures || []).length, "question", "questions")));
      }), { compact: true, note: esc("As each election office lists them. Type a state with it (") +
        searchLink("Missouri Amendment 3") + esc(") for one question."),
        more: unread.length ? esc("This site " + (was ? "did not find" : "has not found") + " an official list for " +
          andList(unread.map(placeWords)) + ".") : "" })];
    }
    var hits = [];
    listed.forEach(function (code) {
      (all[code].measures || []).forEach(function (m, i) {
        var dw = measureWords(m.designation);
        var set = {};
        dw.forEach(function (w) { set[w] = true; });
        var equal = phrase(dw) === phrase(qs);
        if (!equal && !qs.every(function (w) { return set[w]; })) return;
        if (!equal && !kinds.length && (coded || !mixed)) return;
        hits.push({ code: code, m: m, i: i });
      });
    });
    if (!hits.length) {
      // A code that names no question ("cd 7", "pa 7") is not a question.
      if (!kinds.length) return [];
      var kindWord = kinds[0];
      var withKind = listed.filter(function (c) {
        return (all[c].measures || []).some(function (m) { return measureWords(m.designation).indexOf(kindWord) !== -1; });
      });
      var verb = was ? "was" : "is";
      return [block("measures", "", [], { note: esc("No statewide question on a Nov 3, 2026 ballot " +
        (ctx.state ? "in " + KYC.stateName(ctx.state) + " " : "") + verb + " called “" +
        phrase(trim(ctx.state ? ctx.rest : ctx.ws)) + "”, as the election offices " + (was ? "listed" : "list") + " them.") + (ctx.state
          ? " " + link(statePage(ctx.state, "measures"), KYC.stateName(ctx.state) + "’s questions") + "."
          : (withKind.length ? " " + esc("Questions called a " + kindWord + " " + (was ? "were" : "are") +
              " on the ballot in ") +
            andList(withKind.map(function (c) { return link(statePage(c, "measures"), KYC.stateName(c)); })) + "." : "") +
            (unread.length ? " " + esc("This site " + (was ? "did not find" : "has not found") + " an official list for " +
              andList(unread.map(placeWords)) + ".") : "")) })];
    }
    hits.sort(function (a, b) { return KYC.stateName(a.code).localeCompare(KYC.stateName(b.code)) || a.i - b.i; });
    return [block("measures", "", hits.slice(0, LIMIT).map(function (h) {
      var about = h.m.title || h.m.text || "";
      if (about.length > 160) about = about.slice(0, 157).replace(/\s+\S*$/, "") + "…";
      return row(link(measureAnchor(h.code, h.i), h.m.designation + ", " + KYC.stateName(h.code)), esc(about));
    }), { note: esc((was ? "On the Nov 3, 2026 ballot, as each election office listed them" :
      "On the Nov 3, 2026 ballot, as each election office lists them") +
      "; each links to its state’s page, with its text and source."),
      more: hits.length > LIMIT ? esc((hits.length - LIMIT) + " more: add a state to the search.") : "" })];
  }

  /* --------------------------------------------------------------- answer */

  var memo = { q: null };

  /** The answers to *query* (as typed: its capitals tell "OH" from "oh"):
   *  `{html, wants: [[file, global]], count}`. *opts.alone*: no profile
   *  answers the query, so a bare name may be a county's or a tribe's. */
  function answer(query, opts) {
    var raw = String(query || "");
    var alone = !!(opts && opts.alone);
    var zip = zipOf(raw);
    // A ZIP code in the query is the lookup's ("state senator 43215"), not
    // a word to match.
    var ws = words(raw.replace(/\b\d{5}(?:-\d{4})?\b/g, " "));
    var key = raw + "|" + (alone ? 1 : 0) + "|" +
      Object.keys(FILES).map(function (k) { return have(k) ? 1 : 0; }).join("");
    if (memo.q === key) return memo.result;
    var result = { html: "", wants: [], count: 0 };
    if (!ws.length || /^\d{5}(?:-?\d{4})?$/.test(raw.trim())) {
      memo = { q: key, result: result };
      return result;
    }
    var found = findState(ws, raw);
    var ctx = {
      raw: raw, ws: ws, zip: zip, wants: [], alone: alone,
      state: found ? found.code : null, stateFound: found,
      rest: found ? without(ws, found.at, found.len) : ws,
    };
    // A state alone ("Ohio") is the grid's answer, and the officials'.
    if (found && !trim(ctx.rest).length) {
      memo = { q: key, result: result };
      return result;
    }
    var blocks = [];
    var county = counties(ctx);
    var parts = [stateOffice, federalOffices, leaders, congressSeats, legislatures, committees,
      tribal, courts, ballotQuestions, narrow];
    blocks = blocks.concat(local(ctx, county.found));
    parts.forEach(function (fn) { blocks = blocks.concat(fn(ctx)); });
    blocks = blocks.concat(county.blocks);
    var seen = {};
    result.wants = ctx.wants.filter(function (k) {
      if (seen[k]) return false;
      seen[k] = true;
      return true;
    }).map(function (k) { return FILES[k]; });
    blocks = blocks.filter(function (b) { return b.rows.length || b.note; });
    result.count = blocks.length;
    result.html = render(blocks);
    memo = { q: key, result: result };
    return result;
  }

  KYC.answers = {
    answer: answer,
    words: words,
    findState: findState,
    namedHolder: namedHolder,
    countyKey: countyKey,
  };
})(window);
