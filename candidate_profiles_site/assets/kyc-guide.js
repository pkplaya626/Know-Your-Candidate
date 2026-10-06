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

  /* ----------------------------------------------------------------- maps */

  /* A guide page with a map: the views in kyc/government_maps.py, drawn by
   * the shared map (kyc-usmap.js). Picking a state lists everything this
   * page says about it, each fact with its sources; with no state picked,
   * the panel says what the current view shows. The address carries both,
   * #/?state=TX&mode=veto, so any view can be shared (KYC.router). */
  function initMap() {
    var data = global.kycGovernment;
    var page = (doc.body.getAttribute("data-page") || "").replace(/^guide-/, "");
    var ids = data && data.pages && data.pages[page];
    if (!ids || !ids.length || !KYC.usmap) return;

    var route = KYC.router.read().params;
    var mode = ids.indexOf(route.mode) !== -1 ? route.mode : ids[0];
    var selected = "";

    function current() { return data.modes[mode]; }

    function fill(token) {
      return token === "none" ? "var(--surface-2)" : "var(--" + token + ")";
    }

    /* The faint fills - the low counts, grey, none - take the theme's own
     * text colour in a callout; the bright ones keep the dark default. */
    var LIGHT_INK = { "scale-1": 1, "scale-2": 1, "scale-3": 1, "cat-4": 1, none: 1 };
    function ink(token) {
      return LIGHT_INK[token] ? "var(--text)" : "";
    }

    function entry(m, value) {
      return m.legend.filter(function (e) { return e.key === value; })[0];
    }

    function look(code) {
      var m = current();
      var value = m.values[code];
      var e = value === undefined ? null : entry(m, value);
      if (!e) {
        return { fill: "var(--surface-2)", ink: "var(--text)",
                 text: map.name(code) + ": " + (m.outside || "not shown") };
      }
      return { fill: fill(e.token), ink: ink(e.token), text: map.name(code) + ": " + e.label };
    }

    var map = KYC.usmap.create({
      look: look,
      label: function (code) {
        var labels = current().labels;
        return (labels && labels[code]) || code;
      },
      onSelect: function (code) { select(code); },
    });

    function drawLegend() {
      var m = current();
      var used = {};
      Object.keys(m.values).forEach(function (code) { used[m.values[code]] = true; });
      // A view that writes its own words on the states (the circuits) keys
      // its legend by those words; colour alone repeats there.
      doc.getElementById("mapLegend").innerHTML = m.legend.filter(function (e) {
        return used[e.key];
      }).map(function (e) {
        var chip = m.labels
          ? '<span class="swatch swatch-label" style="background:' + fill(e.token) +
            (ink(e.token) ? ";color:" + ink(e.token) : "") + '">' +
            KYC.escapeHtml(e.key === "none" ? "–" : e.key) + "</span>"
          : '<span class="swatch" style="background:' + fill(e.token) + '"></span>';
        return '<span class="key">' + chip + KYC.escapeHtml(e.label) + "</span>";
      }).join("");
    }

    function sourceLinks(keys) {
      return keys.map(function (key) {
        var s = data.sources[key];
        return s ? '<a href="' + KYC.escapeAttr(s[1]) + '" target="_blank" rel="noopener noreferrer">' +
          KYC.escapeHtml(s[0]) + "</a>" : "";
      }).filter(Boolean).join("; ");
    }

    /* Everything this page says about one state: the current view first. */
    function showFacts(code) {
      var target = doc.getElementById("guideFacts");
      if (!code) { target.innerHTML = ""; return; }
      var order = [mode].concat(ids.filter(function (id) { return id !== mode; }));
      // On the state-government map, a state's own legislature is a click
      // away: its districts and members (legislature/<st>.html).
      var legislature = page === "states" && data.modes.legislature &&
        data.modes.legislature.values[code] !== undefined
        ? '<p class="guide-fact-link"><a href="' + KYC.escapeAttr(KYC.siteRoot() + "legislature/" +
          code.toLowerCase() + ".html") + '">' + KYC.icon("landmark") + " " +
          KYC.escapeHtml(map.name(code)) + " Legislature: every district and member ›</a></p>"
        : "";
      // On the local map, the state's counties and every government in each.
      var local = page === "local" && data.modes["local-total"] &&
        data.modes["local-total"].values[code] !== undefined && code !== "DC"
        ? '<p class="guide-fact-link"><a href="' + KYC.escapeAttr(KYC.siteRoot() + "counties/" +
          code.toLowerCase() + ".html") + '">' + KYC.icon("layers") + " " +
          KYC.escapeHtml(map.name(code)) + ": every county and its local governments ›</a></p>"
        : "";
      // On the state-government map, the state's own page says who holds
      // each office the map describes: governor, legislature, highest court.
      var stateGov = legislature
        ? '<p class="guide-fact-link"><a href="' + KYC.escapeAttr(KYC.stateUrl(code) + "#state-government") +
          '">' + KYC.icon("pin") + " " + KYC.escapeHtml(map.name(code)) +
          "'s governor, legislature and highest court: who holds each \u203a</a></p>"
        : "";
      target.innerHTML = legislature + stateGov + local + order.map(function (id) {
        var m = data.modes[id];
        var value = m.values[code];
        var fact = value === undefined ? m.outside : m.facts[code];
        if (!fact) return "";
        var e = value === undefined ? null : entry(m, value);
        var link = m.links && m.links[code];
        return '<div class="guide-fact' + (id === mode ? " is-current" : "") + '">' +
          '<p class="guide-fact-title">' +
          (e ? '<span class="swatch" style="background:' + fill(e.token) + '"></span>' : "") +
          KYC.escapeHtml(m.label) + (e ? ' <span class="faint">' + KYC.escapeHtml(e.label) + "</span>" : "") +
          "</p><p>" + KYC.escapeHtml(fact) + "</p>" +
          (link ? '<p><a href="' + KYC.escapeAttr(link[1]) +
            '" target="_blank" rel="noopener noreferrer">' + KYC.escapeHtml(link[0]) + " ›</a></p>" : "") +
          '<p class="guide-sources"><span>Sources:</span> ' + sourceLinks(m.sources) + "</p></div>";
      }).join("");
    }

    function showHead() {
      doc.getElementById("panelState").textContent = selected ? map.name(selected) : "Select a state";
      doc.getElementById("panelMode").textContent = current().title;
      var link = doc.getElementById("panelStateLink");
      var hasPage = selected && map.hasShape(selected);
      link.hidden = !hasPage;
      if (hasPage) {
        link.href = KYC.stateUrl(selected);
        link.textContent = "Open the " + map.name(selected) + " page ›";
      }
      Array.prototype.forEach.call(doc.querySelectorAll(".guide-about[data-mode]"), function (s) {
        s.hidden = s.getAttribute("data-mode") !== mode;
      });
    }

    function writeRoute() {
      KYC.router.writeFilters({ state: selected, mode: mode === ids[0] ? "" : mode });
    }

    function select(code, opts) {
      if (!code || !map.hasShape(code)) return;
      selected = code;
      map.setSelected(code);
      showHead();
      showFacts(code);
      var picker = doc.getElementById("stateJump");
      if (picker && picker.value !== code) picker.value = code;
      if (!(opts && opts.fromRoute)) writeRoute();
    }

    function setMode(next, opts) {
      if (!data.modes[next] || ids.indexOf(next) === -1) return;
      var relabel = !!(data.modes[next].labels || current().labels) && next !== mode;
      mode = next;
      Array.prototype.forEach.call(doc.querySelectorAll(".segmented [data-mode]"), function (b) {
        b.setAttribute("aria-pressed", String(b.getAttribute("data-mode") === mode));
      });
      // Only a view that writes its own words on the states (the circuit
      // numbers) needs the labels redrawn; the rest only repaint.
      if (relabel) map.draw();
      map.paint();
      drawLegend();
      showHead();
      showFacts(selected);
      if (!(opts && opts.fromRoute)) writeRoute();
    }

    if (!map.loaded()) {
      doc.getElementById("mapStage").innerHTML = '<div class="empty-state">' + KYC.icon("info") +
        "<h3>Map geometry did not load</h3></div>";
      return;
    }
    // The first view is chosen before the first draw, so the map draws once.
    map.start();
    map.paint();
    drawLegend();
    showHead();

    var segmented = doc.querySelector(".segmented");
    if (segmented) {
      segmented.addEventListener("click", function (event) {
        var button = event.target.closest("[data-mode]");
        if (button) setMode(button.getAttribute("data-mode"));
      });
      Array.prototype.forEach.call(segmented.querySelectorAll("[data-mode]"), function (b) {
        b.setAttribute("aria-pressed", String(b.getAttribute("data-mode") === mode));
      });
    }
    var picker = doc.getElementById("stateJump");
    if (picker && picker.getAttribute("data-jump") === "map") {
      picker.addEventListener("change", function () {
        if (picker.value) { select(picker.value); map.reveal(); }
      });
    }
    KYC.router.onChange(function () {
      var params = KYC.router.read().params;
      var wanted = ids.indexOf(params.mode) !== -1 ? params.mode : ids[0];
      if (wanted !== mode) setMode(wanted, { fromRoute: true });
      if (params.state && params.state !== selected) select(params.state, { fromRoute: true });
    });
    if (route.state) select(route.state, { fromRoute: true });

    // A link to one of the page's sections (#legislatures) opens it.
    function openSection() {
      var id = (global.location.hash || "").slice(1);
      if (!id || id.charAt(0) === "/") return;
      var target = doc.getElementById(id);
      if (target && target.tagName === "DETAILS") {
        target.open = true;
        target.scrollIntoView({ block: "start" });
      }
    }
    openSection();
    global.addEventListener("hashchange", openSection);
  }

  /* ----------------------------------------------------------------- boot */

  var LIVE = { committees: renderCommittees };

  function applyRoute(route) {
    if (!KYC.profile) return;
    if (route.view === "profile" && KYC.profile.open(route.id, { fromRoute: true })) return;
    if (KYC.profile.isOpen()) KYC.profile.close();
  }

  KYC.ready(function () {
    initMap();
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
