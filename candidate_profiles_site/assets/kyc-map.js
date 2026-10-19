/* The partisan map on map.html.
 *
 * Renders straight from window.kycGeo - SVG path data decoded at build time
 * by kyc/geo.py. The page used to load d3 and topojson-client from two CDNs
 * and decode an 82 KB TopoJSON blob in the browser on every visit, which is
 * roughly 300 KB of third-party JavaScript to draw 57 shapes that are
 * identical between builds.
 *
 * Fills use color-mix() against the theme's own party custom properties, so
 * switching theme recolours the map through CSS with no repaint pass.
 *
 * The drawing itself - shapes, labels, callouts, the territory strip - is
 * the shared KYC.usmap (kyc-usmap.js); this module decides what colours a
 * state and what its panel shows. The three state-government views -
 * governors, legislatures, trifectas - are KYC.stategov's (kyc-stategov.js),
 * the same module every state page draws its own section with.
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;

  var data = global.legislatorsData || [];

  var mode = "senate";
  var selected = "";
  // The House view drawn as the map ("map") or one square per seat
  // ("tiles", VISUALS-27); in the address as layout=tiles.
  var layout = "map";

  /* --------------------------------------------------------- delegations */

  /** Members and candidates grouped by state, built once. */
  var byState = (function () {
    var index = {};
    data.forEach(function (item) {
      if (!item.state || item.state === "N/A") return;
      (index[item.state] || (index[item.state] = [])).push(item);
    });
    return index;
  })();

  function delegation(code) {
    return byState[code] || [];
  }

  /** Party counts for a state's sitting delegation. */
  function tally(code) {
    var counts = {
      senate: { d: 0, r: 0, i: 0, vacant: 0 },
      house: { d: 0, r: 0, i: 0, vacant: 0 },
    };
    delegation(code).forEach(function (item) {
      if (!KYC.seated(item)) return;
      var chamber = item.chamber.indexOf("Senate") !== -1 ? "senate"
        : item.chamber.indexOf("House") !== -1 ? "house" : null;
      if (chamber) counts[chamber][KYC.partyKey(item)] += 1;
    });
    // A vacant seat has no member to count. The build counts it from the
    // races (summary.by_state), the figure the state page shows too: Texas
    // read "24 R 13 D" here and "24 R / 13 D / 1 Vacant" there.
    var balance = (((global.kycBuildMeta || {}).states || {})[code] || {}).balance;
    if (balance) {
      counts.house.vacant = balance.house.vacant || 0;
      counts.senate.vacant = balance.senate.vacant || 0;
    }
    return counts;
  }

  /** Who held the state's 2026 Senate seat, from its race: a senator who
   *  has since left still defends it for their party, and the record names
   *  them even with no profile here. */
  function senateDefender(code) {
    var race = (global.kycRaces || []).filter(function (r) {
      return r.chamber === "Senate" && r.state === code;
    })[0];
    if (!race) return null;
    var holder = race.incumbentIds.map(KYC.byId).filter(Boolean)[0];
    if (holder) return holder;
    var inc = race.incumbent;
    return inc ? { id: inc.bioguide, name: inc.name, party: inc.party } : null;
  }

  /* ---------------------------------------------------------------- fills */

  var VACANT_FILL = "var(--text-faint)";
  var NONE_FILL = "var(--surface-2)";
  var UNKNOWN_FILL = "var(--surface-3)";

  function mix(demShare) {
    // 0 = wholly Republican, 1 = wholly Democratic; the midpoint reads as the
    // split colour rather than a muddy blend of the two party colours.
    var pct = Math.round(Math.max(0, Math.min(1, demShare)) * 100);
    if (pct >= 50) {
      return "color-mix(in srgb, var(--party-d) " + ((pct - 50) * 2) +
        "%, var(--split))";
    }
    return "color-mix(in srgb, var(--party-r) " + ((50 - pct) * 2) + "%, var(--split))";
  }

  function stateMode() {
    return KYC.stategov.modes.indexOf(mode) !== -1;
  }

  /** Fill and hover text for one state in the current mode. */
  function appearance(code) {
    if (stateMode()) return KYC.stategov.look(code, mode);
    var counts = tally(code);

    if (mode === "senate") {
      var s = counts.senate;
      var seats = s.d + s.r + s.i;
      var fill = UNKNOWN_FILL;
      if (!seats) fill = NONE_FILL;
      else if (s.r === seats) fill = "var(--party-r)";
      else if (s.d === seats) fill = "var(--party-d)";
      else if (s.i === seats) fill = "var(--party-i)";
      else fill = "var(--split)";
      return {
        fill: fill,
        // D.C. and the territories elect no senators: "0R, 0D" read as a
        // count of senators found.
        text: !seats ? code + ": no senators (not a state)" :
          code + " Senate: " + s.r + "R, " + s.d + "D" + (s.i ? ", " + s.i + "I" : ""),
      };
    }

    if (mode === "house") {
      var h = counts.house;
      var held = h.d + h.r + h.i;
      var fill2;
      if (!held && h.vacant) fill2 = VACANT_FILL;
      else if (!held) fill2 = NONE_FILL;
      else if (h.i === held) fill2 = "var(--party-i)";
      else if (!(h.d + h.r)) fill2 = "var(--party-i)";
      else fill2 = mix(h.d / (h.d + h.r));
      return {
        fill: fill2,
        text: code + " House: " + h.r + "R, " + h.d + "D" +
          (h.i ? ", " + h.i + "I" : "") + (h.vacant ? ", " + h.vacant + " vacant" : ""),
      };
    }

    var defender = senateDefender(code);
    if (!defender) {
      return { fill: NONE_FILL, text: code + ": no Senate race in 2026" };
    }
    var key = KYC.partyKey(defender);
    // A senator who ran and lost the primary is not a retiree: John Cornyn
    // and Bill Cassidy read "not running" here while the panel beside the
    // map said "Lost primary". The phrase comes from the same status.
    // After November, the result (KYC.raceStatus's statuses), never "running".
    var status = KYC.contestStatus(defender);
    var counted = KYC.electionStatus().phase === "post-election";
    var party = defender.party === "Democrat" ? "Democratic" : defender.party;
    // An appointee was never elected or nominated to the seat: never
    // "re-elected", "renominated" or "lost re-election" (KYC.raceStatusOf).
    var own = !defender.appointed && !defender.raceRole;
    return {
      fill: key === "vacant" ? VACANT_FILL : "var(--party-" + key + ")",
      text: code + ": 2026 Senate race — " + party + " seat (" +
        defender.name + (status === "eliminated" ? " lost the primary" :
          status === "advanced" ? " in a primary runoff" :
          status === "elected" ? (own ? " re-elected" : " elected") :
          status === "defeated" ? (own ? " lost re-election" : " lost the election") :
          status === "runoff" ? " in the general election runoff" :
          status === "nominee" && counted ? " awaiting result" :
          // Through a top-two or top-four primary, nobody is renominated.
          status === "nominee" && defender.allPartyPrimary ? " advanced to November" :
          status === "nominee" && defender.seekingReelection2026 ?
            (own ? " renominated" : " on the November ballot") :
          defender.seekingReelection2026 ? " running" :
          defender.contestLabel ? " running for " + defender.contestLabel :
          defender.alsoRunningSeat ? " running for " + defender.alsoRunningSeat :
          " not running") + ")",
    };
  }

  /* ------------------------------------------------------------------ map */

  var map = KYC.usmap.create({
    look: appearance,
    onSelect: function (code) { select(code); },
  });

  /* --------------------------------------------------------------- legend */

  /* Each key is a fill some state is drawn in. The Senate's "Independent"
   * swatch matched no state - Maine and Vermont each have one independent
   * and are drawn as split - and D.C.'s and the territories' fill had no
   * key at all; "No race in 2026" showed a lighter grey than its states. */
  var LEGENDS = {
    senate: [
      ["var(--party-r)", "Both Republican"],
      ["var(--party-d)", "Both Democratic"],
      ["var(--split)", "Split, or one independent"],
      ["var(--party-i)", "Both independent", "allIndependent"],
      [NONE_FILL, "No senators (D.C. and territories)"],
    ],
    senate2026: [
      ["var(--party-r)", "Republican seat up"],
      ["var(--party-d)", "Democratic seat up"],
      [NONE_FILL, "No race in 2026"],
    ],
  };

  /* Does any state's delegation in *chamber* consist only of independents? */
  function allIndependent(chamber) {
    var states = (KYC.meta() || {}).states || {};
    return Object.keys(states).some(function (code) {
      var b = ((states[code] || {}).balance || {})[chamber] || {};
      return b.I > 0 && !b.D && !b.R;
    });
  }

  function drawLegend() {
    var target = doc.getElementById("mapLegend");
    if (stateMode()) {
      target.innerHTML = KYC.stategov.legend(mode).map(function (entry) {
        return '<span class="key"><span class="swatch" style="background:' +
          entry[0] + '"></span>' + KYC.escapeHtml(entry[1]) + "</span>";
      }).join("");
      return;
    }
    if (mode === "house") {
      target.innerHTML = [
        '<span class="key"><span class="party-r">All R</span>',
        '<span class="ramp" style="background:linear-gradient(to right,',
        "var(--party-r),var(--split),var(--party-d))\"></span>",
        '<span class="party-d">All D</span></span>',
        allIndependent("house")
          ? '<span class="key"><span class="swatch" style="background:var(--party-i)"></span>' +
            "All independent</span>" : "",
        '<span class="key"><span class="swatch" style="background:var(--text-faint)">',
        "</span>Vacant</span>",
      ].join("");
      return;
    }
    target.innerHTML = LEGENDS[mode]
      .filter(function (entry) { return !entry[2] || allIndependent("senate"); })
      .map(function (entry) {
        return '<span class="key"><span class="swatch" style="background:' +
          entry[0] + '"></span>' + KYC.escapeHtml(entry[1]) + "</span>";
      })
      .join("");
  }

  /* ---------------------------------------------------------------- panel */

  var MODE_TITLE = {
    senate: "Senate delegation",
    house: "House delegation and 2026 candidates",
    senate2026: "2026 Senate race",
  };
  KYC.stategov.modes.forEach(function (m) { MODE_TITLE[m] = KYC.stategov.titles[m]; });

  function forMode(code) {
    var people = delegation(code);
    if (mode === "senate") {
      return people.filter(function (x) {
        return KYC.seated(x) && x.chamber.indexOf("Senate") !== -1;
      });
    }
    if (mode === "house") {
      return people.filter(function (x) { return x.chamber.indexOf("House") !== -1; });
    }
    return people.filter(function (x) {
      return x.chamber.indexOf("Senate") !== -1 &&
        (x.seatUp2026 || x.isCandidate || x.raceRole === "winner");
    });
  }

  /* The panel's rows are narrow, so the shared badges' labels are shortened
   * here; the statuses themselves are the shared module's. */

  /* A member contesting another seat: the seat, and the result of the race
   * they are in, not of the seat they hold. The panel is one state's, so the
   * seat says only what the row does not: "Running for CA-41", "Running for
   * Senate" - and the state too, should a contest ever be in another one. */
  function contestSeat(item) {
    var seat = item.contestLabel.split(" • ");
    var label = seat[0] === "House" && seat[1] ? seat[1]
      : seat[1] === item.state ? seat[0] : seat.join(" ");
    // The shared words (KYC.contestLine): "Ran for" after a loss, and a
    // renumbered seat is "(redrawn)", re-election rather than leaving.
    var line = KYC.contestLine(item);
    var words = line.renumbered ? (line.past ? "Ran in " : "Running in ") + label + " (redrawn)"
      : (line.past ? "Ran for " : "Running for ") + label;
    return '<span class="badge ' + line.cls + ' contest" title="' +
      KYC.escapeAttr(line.title) + '">' + KYC.escapeHtml(words) + "</span>";
  }

  function badge(spec, item) {
    return '<span class="badge ' + spec.cls + '" title="' + KYC.escapeAttr(spec.title) + '">' +
      KYC.escapeHtml(spec.label) + KYC.ballotLineSuffix(item) + "</span>";
  }

  function contestBadge(item) {
    // The status of the race they are in, worded as KYC.raceStatusOf words
    // it: "Advanced" from a top-two primary, never "Nominee: won the primary".
    var spec = KYC.raceStatusOf(item, "short");
    return spec ? badge(spec, item) : "";
  }

  function rowBadge(item) {
    var status = String(item.status || "").toLowerCase();
    // "Renominated", "Leaving seat": about the seat a member holds, not the
    // whole ballot (a member may be on another office's). "Nominee – Speak
    // The Truth line": not a second Democratic nominee.
    // Never "Re-elected" for a member who won a seat they did not hold, or
    // for an appointee (KYC.raceStatusOf says the same).
    // The one status for this person (KYC.standing), so a filer the results
    // do not name reads "Status not known" here as on their card, never
    // "Challenger" (RACES-04).
    var race = KYC.standing(item, "short");
    // A member leaving for another office's ballot: the row is narrow, so
    // where they are going is in its hover, as the card names it.
    var going = KYC.otherOffice(item);
    if (race && going) {
      race = { cls: race.cls, label: race.label, title: race.title + " " + going.text + "." };
    }
    if (race) return badge(race, item);
    if (item.isCandidate) return '<span class="badge badge-money">Challenger</span>';
    if (/retiring|not running|defeated|ineligible|resigned/.test(status)) {
      return '<span class="badge badge-danger">Departing</span>';
    }
    if (item.chamber.indexOf("Senate") !== -1 && item.seatUp2026) {
      return '<span class="badge badge-warn">Up in ’26</span>';
    }
    return "";
  }

  function personRow(item) {
    // A member contesting another seat carries two badges. Both at the row's
    // end squeezed the name to nothing and broke "House • CA-38" over four
    // lines, so the seat ("Running for CA-41") takes a line under the text
    // and the result ("Nominee") stays at the end, in line with every other
    // row's "Renominated". The grid in kyc.css places them.
    var elsewhere = !item.isCandidate && item.contestLabel;
    return [
      '<button type="button" class="person-row" data-id="',
      KYC.escapeAttr(item.id), '">',
      '<img ', KYC.portraitAttrs(item, "38px"),
      ' alt="" loading="lazy" decoding="async" data-photo-idx="0" data-profile="',
      KYC.escapeAttr(item.id), '">',
      '<span class="who">',
      '<span class="name">', KYC.escapeHtml(item.name), "</span>",
      '<span class="office">', KYC.escapeHtml(item.officeLabel), "</span>",
      '<span class="party ', KYC.partyClass(item), '">',
      KYC.escapeHtml(item.party), "</span>",
      "</span>",
      elsewhere ? contestSeat(item) + contestBadge(item) : rowBadge(item),
      KYC.icon("chevron"),
      "</button>",
    ].join("");
  }

  /** The 2026 Senate view of a state with no Senate race: said, with when
   *  each sitting senator's seat is next on the ballot (the pipeline's
   *  nextElection, from the term), not "Nothing to show" (RACES-06). */
  function noSenateRace(code) {
    var name = KYC.escapeHtml(KYC.stateName(code));
    var senators = (global.legislatorsData || []).filter(function (p) {
      return p.state === code && KYC.seated(p) && /Senate/.test(p.chamber) && p.nextElection;
    }).sort(function (a, b) { return a.nextElection - b.nextElection; });
    if (!senators.length) return "No U.S. Senate election in " + name + " in 2026.";
    return "No U.S. Senate election in " + name + " in 2026. Its senators' seats are next on the " +
      "ballot in " + senators.map(function (p) {
        return p.nextElection + " (" + KYC.escapeHtml(p.name) + ")";
      }).join(" and ") + ".";
  }

  function showPanel(code) {
    var list = doc.getElementById("delegation");
    var counts = tally(code);
    var people = forMode(code).slice();

    doc.getElementById("panelState").textContent = map.name(code);
    doc.getElementById("panelMode").textContent = MODE_TITLE[mode];
    var pageLink = doc.getElementById("panelStateLink");
    if (pageLink) {
      pageLink.hidden = false;
      pageLink.href = KYC.stateUrl(code);
      pageLink.textContent = "Open the " + KYC.stateName(code) + " page \u203a";
    }

    if (stateMode()) {
      doc.getElementById("panelCounts").innerHTML = KYC.stategov.badge(code, mode);
      list.innerHTML = '<div class="stategov">' + KYC.stategov.render(code, { links: true }) + "</div>";
      list.scrollTop = 0;
      return;
    }

    var group = mode === "house" ? counts.house : counts.senate;
    var pill = function (n, cls, label) {
      return n ? '<span class="' + cls + '">' + n + " " + label + "</span>" : "";
    };
    doc.getElementById("panelCounts").innerHTML = [
      pill(group.r, "party-r", "R"),
      pill(group.d, "party-d", "D"),
      pill(group.i, "party-i", "I"),
      pill(group.vacant, "party-vacant", "vacant"),
    ].filter(Boolean).join(" ") || '<span class="faint">No seats</span>';

    if (!people.length) {
      list.innerHTML =
        '<div class="empty-state">' + KYC.icon("info") + "<p>" + (mode === "senate2026"
          ? noSenateRace(code) : "Nothing to show for " + KYC.escapeHtml(code) + " in this view.") +
        "</p></div>";
      return;
    }

    // By seat, then in each race's own order (the pipeline's: the seat's
    // holder, then by surname - TRUST-15).
    var order = function (a, b) {
      return (
        KYC.districtOrder(a) - KYC.districtOrder(b) ||
        KYC.racePosition(a) - KYC.racePosition(b) ||
        a.name.localeCompare(b.name)
      );
    };
    // Whoever sits in the seat now holds it - a winner seated since Election
    // Day included; a 2026 incumbent who has left is never "currently
    // seated" (rule 27), and is listed apart.
    var seated = people.filter(function (x) { return KYC.seated(x); }).sort(order);
    var former = people.filter(function (x) { return x.formerMember; }).sort(order);
    // A filer the published results do not settle is not counted as a
    // challenger: Florida's House panel read "2026 challengers 52" over
    // race headers summing 42 (RACES-04). They are listed apart, under the
    // words their cards use.
    var unknown = function (x) {
      var spec = KYC.standing(x, "short");
      return !!(spec && spec.unknown);
    };
    var running = people.filter(function (x) {
      return x.isCandidate && !KYC.offBallot(x.raceStatus) && !unknown(x);
    }).sort(order);
    var unsure = people.filter(function (x) { return x.isCandidate && unknown(x); }).sort(order);
    var out = people.filter(function (x) { return x.isCandidate && KYC.offBallot(x.raceStatus); });

    /* Texas has 37 representatives and 191 filed challengers. Listing all 228
     * in one scroll buries the delegation the reader clicked the state to
     * see, so the challengers sit behind a count they can open. */
    var html = "";
    if (mode === "senate2026" && KYC.odds) {
      var seatRace = (global.kycRaces || []).filter(function (r) {
        return r.chamber === "Senate" && r.state === code;
      })[0];
      if (seatRace) html += KYC.odds.render(seatRace, { compact: true });
    }
    if (seated.length) {
      html += '<p class="panel-subhead">' +
        (mode === "senate2026" ? "Seat held by" : "Currently seated") +
        " <span>" + seated.length + "</span></p>" +
        seated.map(personRow).join("");
    }
    if (former.length) {
      html += '<p class="panel-subhead">' +
        (mode === "senate2026" ? "Held the seat until " + former[0].formerMember.left
          : "Left office") +
        " <span>" + former.length + "</span></p>" + former.map(personRow).join("");
    }
    // The House view: every district drawn, with who holds it.
    var districtMap = mode === "house" && (KYC.meta().districtMaps || {})[code];
    if (districtMap) {
      html += '<p class="gov-pages"><a class="sidebar-link" href="' +
        KYC.escapeAttr(KYC.siteRoot() + districtMap.page) + '">' +
        (districtMap.redrawn ? "Old and new district lines \u203a" : "District map \u203a") + "</a></p>";
    }
    if (running.length) {
      html +=
        '<button type="button" class="panel-subhead expander" id="showChallengers"' +
        ' aria-expanded="false" aria-controls="challengerRows">' +
        KYC.icon("chevron") + " 2026 challengers <span>" + running.length + "</span>" +
        (out.length
          ? ' <span class="faint" title="Lost the primary, withdrew, or were not on the primary ballot">' +
            out.length + " out</span>"
          : "") +
        "</button>" +
        '<div id="challengerRows" hidden>' + running.map(personRow).join("") + "</div>";
    } else if (out.length) {
      html += '<p class="panel-subhead">No challenger still on the ballot ' +
        '<span title="Lost the primary, withdrew, or were not on the primary ballot">' +
        out.length + " out</span></p>";
    }
    if (unsure.length) {
      html +=
        '<button type="button" class="panel-subhead expander" id="showUnsure"' +
        ' aria-expanded="false" aria-controls="unsureRows">' +
        KYC.icon("chevron") + " Filed; ballot status not known <span>" + unsure.length +
        "</span></button>" +
        '<div id="unsureRows" hidden>' + unsure.map(personRow).join("") + "</div>";
    }
    // The people the results put on the ballot with no profile here: by
    // name for the state's Senate seat, counted for its House seats, with
    // the state page that lists them race by race. Only the view's own
    // chamber: the Senate view counted Hawaii's House nominees under a
    // Senate heading (audit 2026-10-17, RACES-06).
    var stateRaces = (global.kycRaces || []).filter(function (r) {
      return r.state === code && (mode === "house" ? r.chamber === "House" : r.chamber === "Senate");
    });
    if (mode === "senate2026") {
      html += stateRaces.map(function (r) { return KYC.cards.unprofiledNote(r, "panel-note"); }).join("");
    } else {
      /* Whose word each name is, counted apart (rules 64 and 77): once the
       * count has begun, some of Louisiana's districts read from the results
       * pages while others are still the Secretary of State's list, and a
       * state's certified list sets some races and not others. One sentence
       * crediting one source would credit the others' names to it. */
      var bySource = {};
      var order = [];
      stateRaces.forEach(function (r) {
        var n = KYC.cards.unprofiledNames(r).none.length;
        if (!n) return;
        var source = KYC.ballotSource(r);
        if (!(source in bySource)) { bySource[source] = 0; order.push(source); }
        bySource[source] += n;
      });
      var people = function (n) { return n + (n === 1 ? " person" : " people"); };
      var parts = order.map(function (source) { return people(bySource[source]) + " " + source; });
      if (parts.length) {
        html += '<p class="panel-note">Also on the November ballot, with no profile here: ' +
          KYC.escapeHtml(parts.join(", and ")) +
          '. <a href="' + KYC.escapeAttr(KYC.stateUrl(code)) + '">Each race on the ' +
          KYC.escapeHtml(KYC.stateName(code)) + " page \u203a</a></p>";
      }
    }
    /* The pages the statuses above were read from, linked, as a race's
     * head links its own (TRUST-06): one link per page, since a state's
     * House races share one results page. */
    var seenSource = {};
    var sources = stateRaces.map(function (r) {
      var url = r.results && r.results.sourceUrl;
      if (!url || seenSource[url]) return "";
      seenSource[url] = true;
      return KYC.resultsSourceHtml(r);
    }).filter(Boolean);
    if (sources.length) html += '<p class="panel-note race-results">' + sources.join(" ") + "</p>";
    list.innerHTML = html;
    list.scrollTop = 0;

    [["showChallengers", "challengerRows"], ["showUnsure", "unsureRows"]].forEach(function (pair) {
      var toggle = doc.getElementById(pair[0]);
      if (!toggle) return;
      toggle.addEventListener("click", function () {
        var rows = doc.getElementById(pair[1]);
        var open = rows.hidden;
        rows.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        toggle.classList.toggle("open", open);
      });
    });
  }

  /** The address of what is on screen: the state, the view, and the
   *  House's layout when it is the squares. */
  function routeNow() {
    return { state: selected, mode: mode === "senate" ? "" : mode,
             layout: mode === "house" && layout === "tiles" ? "tiles" : "" };
  }

  /* ------------------------------------------- bars and squares (charts) */

  /* Above the map in the views of Congress, the chamber's seats as one bar
   * with the seats on the 2026 ballot hatched (VISUALS-21); in the House
   * view, a choice between the map and one square per seat (VISUALS-27),
   * since the map gives Wyoming's one seat California's weight. */
  function drawCharts() {
    var box = doc.getElementById("mapBalance");
    var tiles = doc.getElementById("mapTiles");
    var stage = doc.getElementById("mapStage");
    if (!box || !tiles || !KYC.balanceBar) return;
    var chamber = mode === "house" ? "house" : mode === "senate" || mode === "senate2026" ? "senate" : "";
    var squares = mode === "house" && layout === "tiles" && !!KYC.houseTiles &&
      !!(KYC.meta() || {}).houseTiles;
    box.hidden = !chamber;
    box.innerHTML = !chamber ? "" :
      (mode === "house" && (KYC.meta() || {}).houseTiles
        ? '<div class="map-layout"><span id="mapLayoutLabel">Draw the House as</span>' +
          '<div class="segmented" role="group" aria-labelledby="mapLayoutLabel">' +
          '<button type="button" data-layout="map" aria-pressed="' + String(!squares) + '">A map</button>' +
          '<button type="button" data-layout="tiles" aria-pressed="' + String(squares) +
          '">One square per seat</button></div></div>' : "") +
      // On a phone, the one-line form: the map stays near the first screen.
      KYC.balanceBar(chamber, { title: chamber === "senate" ? "The Senate now" : "The House now",
        compact: !!(global.matchMedia && global.matchMedia("(max-width: 1000px)").matches) });
    stage.hidden = squares;
    tiles.hidden = !squares;
    if (squares) {
      tiles.innerHTML = KYC.houseTiles({ selected: selected }) +
        '<p class="bb-note">Each square is a voting seat, coloured by who sits for it, placed ' +
        "roughly where its district lies within its state. Pick a state for its delegation.</p>";
      // The key says what the squares are, in place of the map's ramp.
      doc.getElementById("mapLegend").innerHTML = KYC.houseTilesKey();
    } else {
      tiles.innerHTML = "";
    }
  }

  function setLayout(next) {
    layout = next === "tiles" ? "tiles" : "map";
    drawLegend();
    drawCharts();
    KYC.router.writeFilters(routeNow());
  }

  function select(code, opts) {
    if (!code) return;
    selected = code;
    map.setSelected(code);
    showPanel(code);
    Array.prototype.forEach.call(doc.querySelectorAll("#mapTiles .ht-state"), function (b) {
      var on = b.getAttribute("data-state") === code;
      b.classList.toggle("is-selected", on);
      b.setAttribute("aria-pressed", String(on));
    });
    var picker = doc.getElementById("mapStateSelect");
    if (picker && picker.value !== code) picker.value = code;
    // Every view needs a URL: a selected state is shareable as #/?state=TX.
    if (!(opts && opts.fromRoute)) {
      KYC.router.writeFilters(routeNow());
    }
    KYC.rememberState(code);
    KYC.renderRememberedState();
  }

  function setMode(next, opts) {
    if (!MODE_TITLE[next]) return;
    mode = next;
    Array.prototype.forEach.call(
      doc.querySelectorAll("[data-mode]"),
      function (button) {
        button.setAttribute(
          "aria-pressed", String(button.getAttribute("data-mode") === mode)
        );
      }
    );
    // The footer names this view's sources: the national view of Congress
    // named none (TECH-11). The state panels date their own.
    Array.prototype.forEach.call(doc.querySelectorAll("[data-sources]"), function (line) {
      line.hidden = (" " + line.getAttribute("data-sources") + " ").indexOf(" " + mode + " ") === -1;
    });
    drawLegend();
    drawCharts();
    map.paint();
    if (selected) showPanel(selected);
    if (!(opts && opts.fromRoute)) {
      KYC.router.writeFilters(routeNow());
    }
  }

  /* ----------------------------------------------------------------- boot */

  function initStatePicker() {
    var picker = doc.getElementById("mapStateSelect");
    if (!picker) return;
    map.codes().sort().forEach(function (code) {
      var option = doc.createElement("option");
      option.value = code;
      option.textContent = code;
      picker.appendChild(option);
    });
    picker.addEventListener("change", function () {
      if (!picker.value) return;
      select(picker.value);
      map.reveal();
    });
  }

  KYC.ready(function () {
    if (!map.loaded()) {
      doc.getElementById("mapStage").innerHTML =
        '<div class="empty-state">' + KYC.icon("info") +
        "<h3>Map geometry did not load</h3>" +
        "<p>Run <code>python build_profile_site.py geo</code> to regenerate " +
        "<code>data/geo.js</code>.</p></div>";
      return;
    }

    KYC.profile.ensure();
    map.start();
    initStatePicker();
    /* Read the incoming route before anything writes one. Boot used to call
     * setMode("senate") as a user action, which wrote "#/" over the address
     * before it was read - so map.html#/?state=TX, every state page's map
     * link and every shared profile link all landed on a blank map. */
    var initial = KYC.router.read();
    layout = initial.params.layout === "tiles" ? "tiles" : "map";
    setMode(MODE_TITLE[initial.params.mode] ? initial.params.mode : "senate",
            { fromRoute: true });

    doc.querySelector(".map-views").addEventListener("click", function (event) {
      var button = event.target.closest("[data-mode]");
      if (button) setMode(button.getAttribute("data-mode"));
    });
    doc.getElementById("mapBalance").addEventListener("click", function (event) {
      var button = event.target.closest("[data-layout]");
      if (button) setLayout(button.getAttribute("data-layout"));
    });
    doc.getElementById("mapTiles").addEventListener("click", function (event) {
      var state = event.target.closest(".ht-state");
      if (state) select(state.getAttribute("data-state"));
    });

    doc.getElementById("delegation").addEventListener("click", function (event) {
      var row = event.target.closest("[data-id]");
      if (row) KYC.profile.open(row.getAttribute("data-id"));
    });

    KYC.router.onChange(function () {
      var route = KYC.router.read();
      if (route.view === "profile") {
        KYC.profile.open(route.id, { fromRoute: true });
        return;
      }
      if (KYC.profile.isOpen()) KYC.profile.close();
      var wanted = route.params.mode || "senate";
      var shape = route.params.layout === "tiles" ? "tiles" : "map";
      if (shape !== layout) {
        layout = shape;
        if (wanted === mode) { drawLegend(); drawCharts(); }
      }
      if (wanted !== mode) setMode(wanted, { fromRoute: true });
      if (route.params.state && route.params.state !== selected) {
        select(route.params.state, { fromRoute: true });
      } else if (!route.params.state && selected) {
        // Back on the list with a state still showing - after closing a
        // profile someone landed on directly - so the address says which.
        KYC.router.writeFilters(routeNow());
      }
    });
    if (initial.view === "profile") {
      // A shared profile opens over that person's state, not a blank map.
      var person = KYC.byId(initial.id);
      if (person && map.hasShape(person.state)) select(person.state, { fromRoute: true });
      KYC.profile.open(initial.id, { fromRoute: true });
    } else if (initial.params.state) {
      select(initial.params.state, { fromRoute: true });
    }
  });
})(window);
