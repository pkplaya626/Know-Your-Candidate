/* Know Your Candidate - the guide to how government works.
 *
 * The guide's words are written into each page by kyc/government.py, with
 * the sources each section was checked against. This module adds only what
 * comes from the site's data, so nothing about a person is ever typed into
 * the guide: on the Congress page, who chairs each committee today and who
 * leads its minority, from the same committee rosters as each member's
 * profile, with each name opening that profile.
 *
 * A block it fills is marked <div class="guide-live" data-live="...">, and
 * says what it is without JavaScript.
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;

  /* ----------------------------------------------------------- committees */

  // A majority's lead is titled Chair, Chairman, Chairwoman or Cochairman.
  var CHAIR = /^(co-?)?chair(man|woman)?$/i;
  var CHAMBERS = [
    ["house", "House committees"],
    ["senate", "Senate committees"],
    ["joint", "Joint committees"],
  ];

  /** The minority's lead: its ranking member - or, where a committee gives
   *  the minority the vice chair (Senate Ethics, Intelligence, Indian
   *  Affairs), its vice chair. Lower is better; ex officio seats never. */
  function minorityRank(title) {
    if (/ranking/i.test(title)) return 0;
    if (/^vice/i.test(title)) return 1;
    if (CHAIR.test(title)) return 2;
    return -1;
  }

  /** ``{code: {code, info, majority: [], minority: []}}`` for every full
   *  committee with a titled seat, built from the sitting members' lists. */
  function committeeLeads() {
    var table = KYC.meta().committees || {};
    var out = {};
    (global.legislatorsData || []).forEach(function (person) {
      if (person.isCandidate) return;
      (person.committeeList || []).forEach(function (seat) {
        var info = table[seat.code];
        if (!seat.title || !info || info.parent) return;
        var row = out[seat.code] ||
          (out[seat.code] = { code: seat.code, info: info, majority: [], minority: [] });
        var lead = { person: person, title: seat.title };
        if (seat.side === "minority") {
          lead.rank = minorityRank(seat.title);
          if (lead.rank >= 0) row.minority.push(lead);
        } else if (CHAIR.test(seat.title)) {
          row.majority.push(lead);
        }
      });
    });
    Object.keys(out).forEach(function (code) {
      var row = out[code];
      var best = Math.min.apply(null, row.minority.map(function (l) { return l.rank; }));
      row.minority = row.minority.filter(function (l) { return l.rank === best; });
    });
    return out;
  }

  /** "House Committee on the Budget" sorts under B. */
  function sortName(name) {
    return String(name)
      .replace(/^(United States )?(House|Senate) /, "")
      .replace(/^((Joint|Permanent|Select|Special) )*(Committee|Caucus|Subcommittee)( of Congress)? (on|to) (the )?/i, "");
  }

  function personButton(lead, standard) {
    var p = lead.person;
    var key = KYC.partyKey(p);
    var extra = lead.title && !standard.test(lead.title)
      ? ' <span class="guide-person-title">' + KYC.escapeHtml(lead.title) + "</span>" : "";
    // "R-PA" is kept on one line: a wrap after the hyphen left "PA" alone.
    return '<button type="button" class="guide-person" data-id="' + KYC.escapeAttr(p.id) + '">' +
      '<span class="name">' + KYC.escapeHtml(p.name) + "</span> " +
      '<span class="guide-person-seat"><span class="party-' + KYC.escapeAttr(key) + '">' +
      KYC.escapeHtml(key === "vacant" ? "" : key.toUpperCase()) + "</span>" +
      '<span class="faint">-' + KYC.escapeHtml(p.state) + "</span></span>" + extra + "</button>";
  }

  function leadCell(leads, standard, label) {
    if (!leads.length) {
      return '<td data-label="' + KYC.escapeAttr(label) + '"><span class="faint">' +
        "None recorded</span></td>";
    }
    return '<td data-label="' + KYC.escapeAttr(label) + '">' +
      leads.map(function (l) { return personButton(l, standard); }).join("<br>") + "</td>";
  }

  function renderCommittees(target) {
    var leads = committeeLeads();
    var codes = Object.keys(leads);
    if (!codes.length) {
      target.innerHTML = '<p class="results-bar" role="status">The committee rosters did ' +
        "not load, so this list is empty. Each member's profile lists their committees.</p>";
      return;
    }
    var html = "";
    CHAMBERS.forEach(function (chamber) {
      var rows = codes.map(function (c) { return leads[c]; }).filter(function (row) {
        return row.info.chamber === chamber[0];
      }).sort(function (a, b) {
        return sortName(a.info.name).localeCompare(sortName(b.info.name));
      });
      if (!rows.length) return;
      html += '<h3 class="guide-subheading">' + KYC.escapeHtml(chamber[1]) +
        ' <span class="faint">' + rows.length + "</span></h3>" +
        '<div class="guide-table-wrap"><table class="guide-table guide-committees">' +
        '<thead><tr><th scope="col">Committee</th><th scope="col">Chair</th>' +
        '<th scope="col">Minority lead</th></tr></thead><tbody>' +
        rows.map(function (row) {
          var name = KYC.escapeHtml(row.info.name);
          return "<tr><th scope=\"row\">" +
            (row.info.url
              ? '<a href="' + KYC.escapeAttr(row.info.url) +
                '" target="_blank" rel="noopener noreferrer">' + name + "</a>"
              : name) + "</th>" +
            leadCell(row.majority, /^chair(man|woman)?$/i, "Chair") +
            leadCell(row.minority, /^ranking member$/i, "Minority lead") + "</tr>";
        }).join("") +
        "</tbody></table></div>";
    });
    target.innerHTML = html;
  }

  /* ----------------------------------------------------------------- boot */

  var LIVE = { committees: renderCommittees };

  function applyRoute(route) {
    if (!KYC.profile) return;
    if (route.view === "profile" && KYC.profile.open(route.id, { fromRoute: true })) return;
    if (KYC.profile.isOpen()) KYC.profile.close();
  }

  KYC.ready(function () {
    var blocks = doc.querySelectorAll(".guide-live[data-live]");
    Array.prototype.forEach.call(blocks, function (block) {
      var fill = LIVE[block.getAttribute("data-live")];
      if (fill) fill(block);
    });

    // A page with people on it opens their profiles in the shared dialog,
    // from one delegated listener (rule 13), and answers #/profile/ links.
    if (KYC.profile && global.legislatorsData) {
      KYC.profile.ensure();
      doc.getElementById("guideContent").addEventListener("click", function (event) {
        var person = event.target.closest("[data-id]");
        if (person) KYC.profile.open(person.getAttribute("data-id"));
      });
      KYC.router.onChange(function () { applyRoute(KYC.router.read()); });
      applyRoute(KYC.router.read());
    }
  });
})(window);
