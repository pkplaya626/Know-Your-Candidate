/* Know Your Candidate - who runs each state: its governor, and which party
 * holds each chamber of its legislature.
 *
 * Everything comes from window.kycStateGov, built by kyc/stategov.py: the
 * governor from the National Governors Association's roster, the seats from
 * the legislators Open States lists, checked against NCSL's own count. One
 * module draws it for the map's three state views and for every state page,
 * so the two can never disagree (rule 12).
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
    disputed: "var(--text-faint)",
    none: "var(--surface-2)",
  };

  var LEGENDS = {
    governor: [
      [FILL.R, "Republican governor"],
      [FILL.D, "Democratic governor"],
      [FILL.I, "Another party"],
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
    legislature: "State legislature",
    trifecta: "Governor and legislature",
  };

  function anyDisputed() {
    return Object.keys(data.states).some(function (c) {
      return data.states[c].legislature === "disputed";
    });
  }

  /** The legend for one of the map's state views: [[fill, label]]. */
  function legend(mode) {
    var rows = (LEGENDS[mode] || []).slice();
    if (mode !== "governor" && anyDisputed()) rows.push([FILL.disputed, "Sources disagree"]);
    return rows;
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
    if (s.upper) {
      html += '<p class="panel-subhead">Legislature</p><ul class="gov-chambers">' +
        chamberRow(s.upper, code) + (s.lower ? chamberRow(s.lower, code) : "") + "</ul>";
      if (s.note) {
        html += '<p class="gov-note">' + KYC.escapeHtml(s.note) + " " +
          link(s.noteSource, "Legislature's roster") + "</p>";
      }
      html += '<p class="gov-trifecta">' + KYC.escapeHtml(trifectaText(s.trifecta)) + ".</p>";
    }
    if (opts && opts.links && s.upper) {
      var lower = code.toLowerCase();
      html += '<p class="gov-pages">' +
        '<a class="sidebar-link" href="' + KYC.escapeAttr(KYC.siteRoot() + "legislature/" + lower + ".html") +
        '">Every district and member ›</a> ' +
        '<a class="sidebar-link" href="' + KYC.escapeAttr(KYC.siteRoot() + "counties/" + lower + ".html") +
        '">Counties and local governments ›</a></p>';
    }
    var ncsl = data.sources.ncsl && data.sources.ncsl[2];
    html += '<p class="gov-sources faint">Governor: ' + source("nga") + ". Seats: " +
      (s.upper ? source("openstates") + (ncsl ? ", checked against " + source("ncsl") : "") :
        "not covered") + ".</p>";
    return html;
  }

  /* An NGA headshot that fails to load leaves the card without one, not a
   * broken image. Error events do not bubble, so this listens on capture. */
  global.document.addEventListener("error", function (event) {
    var img = event.target;
    if (img && img.classList && img.classList.contains("gov-portrait")) img.remove();
  }, true);

  KYC.stategov = {
    modes: ["governor", "legislature", "trifecta"],
    titles: TITLES,
    state: state,
    look: look,
    legend: legend,
    badge: badge,
    render: render,
  };
})(window);
