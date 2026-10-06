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
    I: "var(--party-i)",
    split: "var(--split)",
    nonpartisan: "color-mix(in srgb, var(--text-faint) 45%, var(--surface-2))",
    /* An office that does not exist is the faintest grey; a vacancy is the
     * House view's vacant grey; sources that disagree are drawn in the text
     * colour itself, the strongest contrast any theme has, so the three
     * cannot be confused (the muted and faint greys were 1.27:1 in the
     * light theme). */
    disputed: "var(--text)",
    vacant: "var(--text-faint)",
    none: "var(--surface-2)",
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
  };

  var TITLES = {
    governor: "Governor",
    lt: "Lieutenant governor",
    ag: "Attorney general",
    sos: "Secretary of state",
    legislature: "State legislature",
    trifecta: "Governor and legislature",
  };

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
      if (any(function (s) { return s[mode] && (s[mode].unconfirmed || s[mode].unlisted); })) {
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

  function chamberRow(c, code) {
    var unlisted = c.seats - c.listed;
    var holds = code === "NE" ? "Elected without party labels"
      : c.majority ? PARTY[c.majority] + " majority of the seats"
      : "No party holds a majority of the seats";
    return '<li class="gov-chamber">' +
      '<span class="gov-chamber-name">' + KYC.escapeHtml(c.title) + "</span>" +
      '<span class="gov-chamber-seats">' + pills(c) + ' <span class="faint">of ' + seatWord(c.seats) +
      (unlisted > 0 ? "; " + unlisted + " with nobody listed" : "") + "</span></span>" +
      '<span class="gov-chamber-holds">' + KYC.escapeHtml(holds) +
      (c.ncsl ? ' <span class="badge badge-warn">NCSL: ' +
        KYC.escapeHtml(c.ncsl === "none" ? "no majority" : PARTY[c.ncsl] + " majority") + "</span>" : "") +
      "</span></li>";
  }

  function source(key) {
    var s = data.sources[key];
    if (!s) return "";
    return '<a href="' + KYC.escapeAttr(s[1]) + '" target="_blank" rel="noopener noreferrer">' +
      KYC.escapeHtml(s[0]) + "</a>" + (s[2] ? " (" + KYC.escapeHtml(s[2]) + ")" : "");
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
  function officerRow(kind, off) {
    var label = OFFICES[kind].title;
    if (!off) return "";
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
    } else if (off.none && kind === "lt") {
      body = '<p class="gov-officer-note">The state has no lieutenant governor.' +
        (off.successor ? " First in line to succeed the governor: " +
          KYC.escapeHtml(off.successor.title) + " " + who(off.successor) + "." : "") + "</p>";
    } else if (off.none) {
      body = '<p class="gov-officer-note">The state has no secretary of state' +
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
      body = (off.photo ? '<img class="gov-officer-photo" src="' + KYC.escapeAttr(off.photo) +
          '" alt="" width="40" height="40" loading="lazy" decoding="async">' : "") +
        '<p class="gov-officer-name">' + who(off) + "</p>" +
        (off.title.toLowerCase() !== label.toLowerCase()
          ? '<p class="faint">' + KYC.escapeHtml(off.title) + "</p>" : "") +
        (facts.length ? '<p class="faint">' + KYC.escapeHtml(facts.join(" · ")) + "</p>" : "") +
        (links.length ? '<p class="gov-links">' + links.join(" · ") + "</p>" : "") +
        (contact.length ? '<p class="faint gov-contact">' + contact.join(" · ") + "</p>" : "");
    }
    var pictured = body.indexOf("gov-officer-photo") !== -1;
    return '<li class="gov-officer' + (pictured ? "" : " gov-officer-text") + '">' +
      '<span class="gov-officer-role">' + KYC.escapeHtml(label) + "</span>" + body + "</li>";
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
        link(court.url, "The court's roster") + "</p>";
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
      '<p class="gov-role">Governor</p>' +
      '<p class="gov-name">' + KYC.escapeHtml(gov.name) + "</p>" +
      '<p class="gov-party party-' + key + '">' + KYC.escapeHtml(gov.party) + "</p>" +
      (gov.since ? '<p class="faint">In office since ' + KYC.escapeHtml(gov.since) + "</p>" : "") +
      '<p class="gov-links">' + (gov.website ? link(gov.website, "Governor's office") + " · " : "") +
      link(gov.profile, "NGA biography") + "</p>" +
      (contact ? '<p class="faint gov-contact">' + contact + "</p>" : "") +
      "</div></div>";
    if (s.lt || s.ag || s.sos) {
      html += '<p class="panel-subhead">Statewide officers</p><ul class="gov-officers">' +
        officerRow("lt", s.lt) + officerRow("ag", s.ag) + officerRow("sos", s.sos) + "</ul>";
    }
    if (s.upper) {
      html += '<p class="panel-subhead">Legislature</p><ul class="gov-chambers">' +
        chamberRow(s.upper, code) + (s.lower ? chamberRow(s.lower, code) : "") + "</ul>";
      if (s.note) {
        html += '<p class="gov-note">' + KYC.escapeHtml(s.note) + " " +
          link(s.noteSource, "Legislature's roster") + "</p>";
      }
      html += '<p class="gov-trifecta">' + KYC.escapeHtml(trifectaText(s.trifecta)) + ".</p>";
    }
    html += courtBlock(s.court) + courtBlock(s.criminalCourt);
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
      (s.sos ? "Secretary of state: " + source("nass") + ". " : "") + "Seats: " +
      (s.upper ? source("openstates") + (ncsl ? ", checked against " + source("ncsl") : "") :
        "not covered") + ".</p>";
    return html;
  }

  /* An NGA headshot that fails to load leaves the card without one, not a
   * broken image. Error events do not bubble, so this listens on capture. */
  global.document.addEventListener("error", function (event) {
    var img = event.target;
    if (img && img.classList &&
        (img.classList.contains("gov-portrait") || img.classList.contains("gov-officer-photo"))) {
      img.remove();
    }
  }, true);

  KYC.stategov = {
    modes: ["governor", "lt", "ag", "sos", "legislature", "trifecta"],
    titles: TITLES,
    state: state,
    look: look,
    legend: legend,
    badge: badge,
    render: render,
  };
})(window);
