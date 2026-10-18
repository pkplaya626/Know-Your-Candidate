/* Know Your Candidate - Know Your Government, the guide.
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
    ["other", "Caucuses and commissions"],
  ];

  /* A caucus or a commission on the rosters is not a committee of either
   * chamber: the Senate's narcotics caucus was counted among its
   * committees. Listed apart, by the name the rosters give it. */
  function groupOf(info) {
    return /\b(Caucus|Commission)\b/.test(info.name || "") ? "other" : info.chamber;
  }

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
      if (!KYC.seated(person)) return;
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

  /** A lead the rosters do not name reads as that, a claim about the
   *  rosters: "None recorded" read as though the minority had no leader or
   *  the data were broken (most joint committees title only majority
   *  members, one from each chamber). */
  var UNNAMED = { "Chair": "No chair named in the rosters",
    "Minority lead": "No minority lead named in the rosters" };

  function leadCell(leads, standard, label) {
    if (!leads.length) {
      return '<td data-label="' + KYC.escapeAttr(label) + '"><span class="faint lead-unnamed">' +
        KYC.escapeHtml(UNNAMED[label] || "Not named in the rosters") + "</span></td>";
    }
    return '<td data-label="' + KYC.escapeAttr(label) + '">' +
      leads.map(function (l) { return personButton(l, standard); }).join("<br>") + "</td>";
  }

  /** A seated member of *chamber* whose committees are not yet published:
   *  a new Congress's rosters come some weeks after it sits, a chamber at a
   *  time, and its members' profiles say so too (committeesPending). */
  function pendingIn(chamber) {
    return (global.legislatorsData || []).filter(function (p) {
      return KYC.seated(p) && p.committeesPending &&
        (chamber === "senate") === /Senate/.test(p.chamber || "");
    })[0];
  }

  function pendingText(member, what) {
    return KYC.escapeHtml(what + " assignments for the " +
      KYC.ordinal(member.committeesPending) + " Congress have not been published yet");
  }

  function renderCommittees(target) {
    var leads = committeeLeads();
    var codes = Object.keys(leads);
    if (!codes.length) {
      var pending = pendingIn("house") || pendingIn("senate");
      target.innerHTML = pending
        ? '<p class="results-bar" role="status">' + pendingText(pending, "Committee") +
          "; each committee's leaders will be listed here once they are.</p>"
        : '<p class="results-bar" role="status">The committee rosters did ' +
          "not load, so this list is empty. Each member's profile lists their committees.</p>";
      return;
    }
    var html = "";
    CHAMBERS.forEach(function (chamber) {
      var rows = codes.map(function (c) { return leads[c]; }).filter(function (row) {
        return groupOf(row.info) === chamber[0];
      }).sort(function (a, b) {
        return sortName(a.info.name).localeCompare(sortName(b.info.name));
      });
      if (!rows.length) {
        // One chamber's rosters can be out before the other's.
        var waiting = (chamber[0] === "house" || chamber[0] === "senate") && pendingIn(chamber[0]);
        if (waiting) {
          html += '<h3 class="guide-subheading">' + KYC.escapeHtml(chamber[1]) + "</h3>" +
            '<p class="results-bar" role="status">' +
            pendingText(waiting, chamber[0] === "house" ? "House committee" : "Senate committee") +
            ".</p>";
        }
        return;
      }
      // Counted from the rosters, so the note cannot outlive them.
      var unnamed = rows.filter(function (row) { return !row.minority.length; }).length;
      html += '<h3 class="guide-subheading">' + KYC.escapeHtml(chamber[1]) +
        ' <span class="faint">' + rows.length + "</span></h3>" +
        (unnamed ? '<p class="faint committees-unnamed" data-chamber="' + KYC.escapeAttr(chamber[0]) +
          '">' + (unnamed === rows.length
            ? (unnamed === 1 ? "This committee’s roster gives" : "Each of these committees’ rosters gives")
            : unnamed === 1 ? "One of these committees’ rosters gives"
            : unnamed + " of these committees’ rosters give") +
          " no member of the minority a leading title, so no minority lead is shown for " +
          (unnamed === 1 ? "it" : "them") + ".</p>" : "") +
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

    /* A state's fact cites the view's general sources and its own: a source
     * scoped to other states (kyc/government_maps.py "scoped") is not about
     * this one. */
    function sourceLinks(m, code) {
      var scoped = m.scoped || {};
      return m.sources.filter(function (key) {
        return !scoped[key] || scoped[key].indexOf(code) !== -1;
      }).map(function (key) {
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
          KYC.escapeHtml(map.name(code) + " " + ((data.legislatureNames || {})[code] || "Legislature")) +
          ": every district and member ›</a></p>"
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
      // On the circuits map, the state's own federal courts - its court of
      // appeals, then its district courts - each a link to its judges, as
      // the federal page lists them (data/federal.js): the guide's map and
      // the federal page's are one set of courts.
      var here = page === "courts" && global.kycFederal
        ? (global.kycFederal.courts || []).filter(function (c) {
            return /^(appeals|district|territorial)$/.test(c.kind) && (c.states || []).indexOf(code) !== -1;
          }).sort(function (a, b) {
            return (a.kind === "appeals" ? 0 : 1) - (b.kind === "appeals" ? 0 : 1) ||
              (a.name < b.name ? -1 : a.name > b.name ? 1 : 0);
          })
        : [];
      var courts = here.length
        ? '<ul class="guide-fact-courts">' + here.map(function (c) {
            return '<li><a href="' + KYC.escapeAttr(KYC.siteRoot() + "courts/" + encodeURIComponent(c.id) +
              ".html") + '">' + KYC.icon("scale") + " " + KYC.escapeHtml(c.name) + " ›</a></li>";
          }).join("") + "</ul>"
        : "";
      target.innerHTML = legislature + stateGov + local + courts + order.map(function (id) {
        var m = data.modes[id];
        var value = m.values[code];
        var fact = value === undefined ? m.outside : m.facts[code];
        if (!fact) return "";
        var e = value === undefined ? null : entry(m, value);
        var link = m.links && m.links[code];
        var cited = sourceLinks(m, code);
        // A view that names who is there (the tribal governments, each with
        // its leader) lists them under its fact, in its own view only.
        var rows = id === mode && m.lists && m.lists[code];
        var listed = rows ? '<ul class="guide-fact-list">' + rows.map(function (row) {
          var who = function (r) {
            return r[1] ? ' <span class="faint">' + KYC.escapeHtml(r[1]) +
              (r[2] ? ", " + KYC.escapeHtml(r[2]) : "") + "</span>"
              : ' <span class="faint">no leader listed</span>';
          };
          return "<li>" + KYC.escapeHtml(row[0]) + who(row) +
            (row[3] && row[3].length ? "<ul>" + row[3].map(function (sub) {
              return "<li>" + KYC.escapeHtml(sub[0]) + who(sub) + "</li>";
            }).join("") + "</ul>" : "") + "</li>";
        }).join("") + "</ul>" : "";
        return '<div class="guide-fact' + (id === mode ? " is-current" : "") + '">' +
          '<p class="guide-fact-title">' +
          (e ? '<span class="swatch" style="background:' + fill(e.token) + '"></span>' : "") +
          KYC.escapeHtml(m.label) + (e ? ' <span class="faint">' + KYC.escapeHtml(e.label) + "</span>" : "") +
          "</p><p>" + KYC.escapeHtml(fact) + "</p>" + listed +
          (link ?'<p><a href="' + KYC.escapeAttr(link[1]) +
            '" target="_blank" rel="noopener noreferrer">' + KYC.escapeHtml(link[0]) + " ›</a></p>" : "") +
          (cited ? '<p class="guide-sources"><span>Sources:</span> ' + cited + "</p>" : "") + "</div>";
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

  /* --------------------------------------------- who holds the office now */

  /* The executive and the Supreme Court as data/federal.js lists them, each
   * name opening the person's record on the federal government's page. The
   * guide's words name no one (rule 48); these lists are the data's. */
  function officialItem(person, role) {
    return '<li><a href="' + KYC.escapeAttr("../federal/index.html#/official/" +
      encodeURIComponent(person.id)) + '">' + KYC.escapeHtml(person.name) + "</a>" +
      (role ? ' <span class="faint">' + KYC.escapeHtml(role) + "</span>" : "") + "</li>";
  }

  function asOfNote(date) {
    return date ? '<p class="faint">As of ' + KYC.escapeHtml(date) + ".</p>" : "";
  }

  function renderExecutive(target) {
    var d = global.kycFederal;
    if (!d || !d.president) return;
    target.innerHTML = '<ul class="guide-holders">' +
      officialItem(d.president, "President") + officialItem(d.vicePresident, "Vice President") +
      "</ul>" + asOfNote((d.asOf || {}).executive);
  }

  function renderCabinet(target) {
    var d = global.kycFederal;
    if (!d || !d.offices) return;
    var departments = d.offices.filter(function (o) { return o.kind === "department"; })
      .sort(function (a, b) { return a.order - b.order; });
    target.innerHTML = '<ul class="guide-holders">' + departments.map(function (office) {
      // The office, the holder's own title and an acting mark, as the
      // federal page's card says them (KYC.holderRole).
      var role = KYC.holderRole(office);
      return office.holder ? officialItem(office.holder, (role.acting ? "Acting " : "") +
          office.office + (role.title ? " (" + role.title + ")" : ""))
        : '<li><span class="faint">' + KYC.escapeHtml(office.office) +
          ": nobody listed by the White House</span></li>";
    }).join("") + "</ul>" + asOfNote((d.asOf || {}).executive);
  }

  function renderJustices(target) {
    var d = global.kycFederal;
    var members = ((d || {}).supremeCourt || {}).members;
    if (!members || !members.length) return;
    target.innerHTML = '<ul class="guide-holders">' + members.map(function (j) {
      return officialItem(j, (j.justice || {}).role || "");
    }).join("") + "</ul>" + asOfNote((d.asOf || {}).judiciary);
  }

  /* ------------------------------------------------------ chamber leaders */

  /* Who holds each leadership post the page explains, from the posts
   * congress-legislators records for each sitting member's bioguide id
   * (profile.leadership): the Speaker and the floor leaders were defined
   * and never named. The principal posts first, in the order the page
   * explains them; a party's other posts (conference chairs, policy
   * committees) after. */
  var LEAD_ORDER = [/^Speaker/, /^President Pro Tempore/, /Majority Leader$/, /Minority Leader$/,
    /Majority Whip$/, /Minority Whip$/];

  function leadRank(title) {
    for (var i = 0; i < LEAD_ORDER.length; i++) if (LEAD_ORDER[i].test(title)) return i;
    return LEAD_ORDER.length;
  }

  function renderLeaders(target, chamber) {
    var rows = [];
    (global.legislatorsData || []).forEach(function (person) {
      if (!KYC.seated(person)) return;
      if ((chamber === "senate") !== /Senate/.test(person.chamber || "")) return;
      (person.leadership || []).forEach(function (title) {
        rows.push({ person: person, title: title, rank: leadRank(title) });
      });
    });
    if (!rows.length) return;      // the fallback stays: a link to each chamber's own list
    rows.sort(function (a, b) {
      return a.rank - b.rank || a.title.localeCompare(b.title);
    });
    target.innerHTML = '<ul class="guide-holders guide-leaders">' + rows.map(function (row) {
      return "<li>" + personButton({ person: row.person, title: row.title }, /^$/) + "</li>";
    }).join("") + "</ul>" +
      '<p class="faint">From the congress-legislators project&#8217;s record of each member&#8217;s ' +
      "leadership posts.</p>";
  }

  /* ------------------------------------------------- the reader's voting */

  /* "Your state's official voting pages" sent every reader to the states'
   * index, two clicks from the links they came for. With a state this
   * browser remembers (KYC.rememberedState), the link opens that state's
   * voting section; the picker opens any state's. */
  function votingUrl(code) {
    return KYC.stateUrl(code) + "#voting";
  }

  function initVoting() {
    var code = KYC.rememberedState ? KYC.rememberedState() : "";
    var known = code && doc.querySelector('#stateJump option[value="' + code + '"]');
    Array.prototype.forEach.call(doc.querySelectorAll("a[data-voting-link]"), function (a) {
      if (known) {
        a.href = votingUrl(code);
        a.title = known.textContent.replace(/\s*\([A-Z]{2}\)$/, "") + "'s official voting pages";
      }
    });
    var form = doc.querySelector("form[data-voting-picker]");
    if (!form) return;
    var select = form.querySelector("select");
    if (known && select.querySelector('option[value="' + code + '"]')) select.value = code;
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (select.value) global.location.href = votingUrl(select.value);
    });
  }

  /* ------------------------------------------------------------ timeline */

  /* The steps from Election Day to January 3: those past are marked done,
   * the next one as next, by the reader's own date. A step's status words
   * are the site's one table's (KYC.raceStatus, rule 63), never a copy. */
  var AFTER_ELECTION = new Date(Date.UTC(2026, 10, 5, 12));
  var BEFORE_ELECTION = new Date(Date.UTC(2026, 10, 1, 12));

  /* Each step names the status as it reads at that step, whatever today
   * is: a nominee "On the November ballot" before Election Day and
   * "Awaiting result" after it, until a winner is marked. */
  function statusSpec(key) {
    return key === "awaiting" ? KYC.raceStatus("nominee", "card", { now: AFTER_ELECTION })
      : KYC.raceStatus(key, "card", { now: BEFORE_ELECTION });
  }

  function initTimeline(now) {
    now = now || new Date();
    var today = now.getFullYear() + "-" + ("0" + (now.getMonth() + 1)).slice(-2) + "-" +
      ("0" + now.getDate()).slice(-2);
    Array.prototype.forEach.call(doc.querySelectorAll(".guide-timeline-steps"), function (list) {
      var next = false;
      Array.prototype.forEach.call(list.children, function (li) {
        var day = li.getAttribute("data-date") || "";
        li.classList.toggle("is-past", day < today);
        li.classList.toggle("is-next", !next && day >= today);
        if (day >= today) next = true;
      });
    });
    Array.prototype.forEach.call(doc.querySelectorAll(".guide-status[data-status]"), function (chip) {
      var spec = KYC.raceStatus && statusSpec(chip.getAttribute("data-status"));
      if (!spec) return;
      chip.textContent = spec.label;
      if (spec.cls) chip.classList.add(spec.cls);
      chip.title = spec.title || "";
    });
  }

  var LIVE = { committees: renderCommittees, executive: renderExecutive, cabinet: renderCabinet,
               justices: renderJustices,
               "leaders-senate": function (t) { renderLeaders(t, "senate"); },
               "leaders-house": function (t) { renderLeaders(t, "house"); } };
  KYC.guide = { live: LIVE, initTimeline: initTimeline };

  function applyRoute(route) {
    if (!KYC.profile) return;
    if (route.view === "profile" && KYC.profile.open(route.id, { fromRoute: true })) return;
    if (KYC.profile.isOpen()) KYC.profile.close();
  }

  /* One part of the page failing must not stop the rest (rule 76). */
  function safely(fn) {
    try { fn(); } catch (e) { if (global.console) global.console.error(e); }
  }

  KYC.ready(function () {
    safely(initMap);
    safely(initVoting);
    safely(function () { initTimeline(); });
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
