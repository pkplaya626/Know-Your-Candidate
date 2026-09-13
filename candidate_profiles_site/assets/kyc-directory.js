/* The profile grid on index.html: filtering, sorting, races, deep links. */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;

  var data = global.legislatorsData || [];
  var races = global.kycRaces || [];

  var state = {
    q: "",
    chamber: "all",
    party: "all",
    role: "all",
    election: "all",
    eliminated: "hide",
    state: "all",
    sort: "region",
    view: "grid",
  };

  var visible = [];

  /* ------------------------------------------------------------ filtering */

  var PARTY_TEST = {
    Democrat: function (item) { return String(item.party).indexOf("Democrat") !== -1; },
    Republican: function (item) { return item.party === "Republican"; },
    Independent: function (item) { return KYC.partyKey(item) === "i"; },
  };

  /* Who is actually in Congress. Since the field came from the FEC, 79% of
   * profiles are people who do not hold the seat, so "show me my
   * representatives" needs to be one click rather than a search. */
  var ROLE_TEST = {
    member: function (item) { return !item.isCandidate; },
    candidate: function (item) { return !!item.isCandidate; },
  };

  /* Primary results settle who is still running. Someone the results say
   * lost, withdrew, or was never on the primary ballot is not "in the race",
   * and showing them as though they were is the opposite mistake from the
   * one the FEC field fixed. They stay in the data - nothing is deleted -
   * behind a toggle. */
  var OFF_BALLOT = { eliminated: true, withdrawn: true, unlisted: true };

  function offBallot(item) {
    return !!OFF_BALLOT[item.raceStatus];
  }

  /* A sitting member of this seat who is contesting another one belongs in
   * the race's story as the departing incumbent, not as someone "out". */

  var ELECTION_TEST = {
    // The 35 Senate seats on the 2026 ballot.
    senateUp26: function (item) {
      return item.seatUp2026 && !item.isCandidate &&
        item.chamber.indexOf("Senate") !== -1;
    },
    // Incumbents whose seat is up but who are not running again.
    notSeeking: function (item) {
      return item.seatUp2026 && !item.isCandidate && !item.seekingReelection2026;
    },
    contested: function (item) {
      return !!item.raceId && contestedRaces.has(item.raceId);
    },
  };

  var contestedRaces = new Set(
    races.filter(function (r) { return r.contested; }).map(function (r) { return r.id; })
  );

  function matchesFilters(item) {
    if (!KYC.matchesQuery(item, state.q)) return false;

    if (state.chamber !== "all" && item.chamber.indexOf(state.chamber) === -1) {
      return false;
    }
    if (state.party !== "all" && !PARTY_TEST[state.party](item)) return false;
    if (state.role !== "all" && !ROLE_TEST[state.role](item)) return false;
    if (state.state !== "all" && item.state !== state.state) return false;
    if (state.election !== "all" && !ELECTION_TEST[state.election](item)) return false;
    return true;
  }

  function matches(item) {
    /* Only challengers are hidden. A sitting member who lost their primary
     * is still in Congress until January and must stay under "Sitting
     * members" - hiding John Cornyn left the Senate one short. */
    if (state.eliminated === "hide" && item.isCandidate && offBallot(item)) return false;
    return matchesFilters(item);
  }

  /* -------------------------------------------------------------- sorting */

  var SORTS = {
    name: function (a, b) { return a.name.localeCompare(b.name); },
    "age-desc": function (a, b) { return age(b) - age(a); },
    "age-asc": function (a, b) { return age(a, 999) - age(b, 999); },
    senate26: function (a, b) {
      var rank = function (x) {
        return x.chamber.indexOf("Senate") !== -1 && (x.seatUp2026 || x.isCandidate)
          ? 0 : 1;
      };
      return (
        rank(a) - rank(b) ||
        a.state.localeCompare(b.state) ||
        (a.isCandidate ? 1 : 0) - (b.isCandidate ? 1 : 0) ||
        a.name.localeCompare(b.name)
      );
    },
    region: function (a, b) {
      var chamber = function (x) { return x.chamber.indexOf("Senate") !== -1 ? 0 : 1; };
      return (
        chamber(a) - chamber(b) ||
        a.state.localeCompare(b.state) ||
        KYC.districtOrder(a) - KYC.districtOrder(b) ||
        a.name.localeCompare(b.name)
      );
    },
  };

  function age(item, fallback) {
    return typeof item.age === "number" ? item.age : (fallback || 0);
  }

  /* ------------------------------------------------------------ rendering */

  var RACE_BADGE = {
    nominee: ['badge-money', 'On the November ballot',
      'Won the primary; will appear on the general election ballot.'],
    eliminated: ['badge-danger', 'Lost primary',
      'Did not win the primary, per the published results.'],
    withdrawn: ['badge-neutral', 'Withdrew',
      'Withdrew from the race, per the published results.'],
    unlisted: ['badge-neutral', 'Not on primary ballot',
      'Filed with the FEC but was not listed in the primary results.'],
    advanced: ['badge-warn', 'In runoff',
      'Advanced to a primary runoff that has not yet been decided.'],
  };

  /* For a sitting member the same facts read differently: no primary line
   * is a retirement, and a primary win is a renomination. */
  var MEMBER_RACE_BADGE = {
    nominee: ['badge-money', 'Renominated',
      'Won the 2026 primary for this seat.'],
    unlisted: ['badge-danger', 'Not on the ballot',
      'Not named in the primary results or on the November ballot; not seeking re-election.'],
  };

  function raceBadge(item) {
    var spec = (!item.isCandidate && MEMBER_RACE_BADGE[item.raceStatus]) ||
      RACE_BADGE[item.raceStatus];
    if (!spec) return "";
    return '<span class="badge ' + spec[0] + '" title="' + KYC.escapeAttr(spec[2]) +
      '">' + KYC.escapeHtml(spec[1]) + "</span>";
  }

  function statusBadge(item) {
    var status = String(item.status || "").toLowerCase();

    /* A member contesting another seat - the other chamber, or a redrawn
     * district - is leaving this one, and the reader should see where they
     * went before anything else. */
    if (!item.isCandidate && item.contestLabel) {
      return '<span class="badge badge-warn" title="' + KYC.escapeAttr(
        "Filed for " + item.contestLabel + " in 2026; not seeking re-election to " +
        item.officeLabel + "."
      ) + '">Running for ' + KYC.escapeHtml(item.contestLabel.replace(/ \u2022 /, " ")) +
        "</span>" + (raceBadge(item) ? " " + raceBadge(item) : "");
    }
    /* A sitting member the primary eliminated is leaving too, and a reader
     * should see that before "seat up". */
    if (!item.isCandidate && OFF_BALLOT[item.raceStatus]) {
      return raceBadge(item);
    }
    if (/retiring|not running|defeated|ineligible|resigned/.test(status)) {
      return '<span class="badge badge-danger">Leaving in ’26</span>';
    }
    if (item.isCandidate) {
      return raceBadge(item) ||
        '<span class="badge badge-money" title="Filed with the FEC; the primary has not been held yet.">2026 challenger</span>';
    }
    if (KYC.partyKey(item) === "vacant") {
      return '<span class="badge badge-neutral">Vacant seat</span>';
    }
    if (item.chamber.indexOf("Senate") !== -1 && item.seatUp2026) {
      return '<span class="badge badge-warn">Seat up in ’26</span>';
    }
    if (item.chamber.indexOf("Senate") !== -1 && item.electionYear) {
      return '<span class="badge badge-neutral">Up in ’' +
        String(item.electionYear).slice(2) + "</span>";
    }
    return "";
  }

  /* Every interpolation is escaped. The previous version put item.name,
   * item.party and the office label straight into innerHTML. */
  function card(item) {
    return [
      '<button type="button" class="card" data-id="', KYC.escapeAttr(item.id), '">',
      '<span class="card-photo">',
      '<img src="', KYC.escapeAttr(KYC.portraitSrc(item)),
      '" alt="" loading="lazy" decoding="async" data-photo-idx="0" data-profile="',
      KYC.escapeAttr(item.id), '">',
      "</span>",
      '<span class="card-body">',
      '<span class="card-name clamp-2">', KYC.escapeHtml(item.name), "</span>",
      '<span class="card-office truncate">', KYC.escapeHtml(item.officeLabel), "</span>",
      '<span class="card-party ', KYC.partyClass(item), '">',
      KYC.escapeHtml(item.party), "</span>",
      statusBadge(item),
      "</span></button>",
    ].join("");
  }

  /* A flat grid of 594 cards answers "who is in Congress". It does not answer
   * the question a voter actually has, which is "who is running for my seat". */
  function raceSections(items) {
    var shown = new Set(items.map(function (x) { return x.id; }));
    // In race context the people the primary removed are part of the story,
    // so they are folded under the race whatever the grid toggle says.
    data.forEach(function (item) {
      if (item.isCandidate && offBallot(item) && matchesFilters(item)) shown.add(item.id);
    });

    var groups = races
      .map(function (race) {
        var people = race.incumbentIds
          .concat(race.candidateIds)
          .filter(function (id) { return shown.has(id); })
          .map(KYC.byId)
          .filter(Boolean);
        return { race: race, people: people };
      })
      .filter(function (group) { return group.people.length; });

    if (!groups.length) return "";

    return groups
      .map(function (group) {
        var race = group.race;
        var badges = [];
        if (race.openSeat) {
          var holder = race.incumbentIds.map(KYC.byId).filter(Boolean)[0];
          var why = !holder ? "A newly drawn seat with no sitting member." :
            holder.contestLabel ? holder.name + " is running for " + holder.contestLabel + "." :
            holder.alsoRunningSeat ? holder.name + " is running for " + holder.alsoRunningSeat + "." :
            OFF_BALLOT[holder.raceStatus] ? holder.name + " is not on the November ballot." :
            holder.name + " is not seeking re-election.";
          badges.push('<span class="badge badge-warn" title="' + KYC.escapeAttr(why) +
            '">Open seat</span>');
        }
        if (race.primaryDate) {
          var held = race.settled;
          badges.push(
            '<span class="badge badge-neutral" title="' +
            KYC.escapeAttr(held
              ? "Primary held " + race.primaryDate +
                (race.runoffDate ? "; runoff " + race.runoffDate : "") +
                ". Results from the state's Wikipedia election page."
              : "Primary scheduled for " + race.primaryDate + ".") + '">' +
            (held ? "Primary held " : "Primary ") + KYC.escapeHtml(race.primaryDate) +
            "</span>"
          );
        }

        /* "No declared challenger" was a claim about our roster dressed up as
         * a fact about the race, and it was wrong for 372 of them. filedCount
         * is how many people have actually filed with the FEC for the seat. */
        var res = race.results || null;
        if (race.contested) {
          badges.push(
            '<span class="badge badge-money">' + race.candidateCount +
            " challenger" + (race.candidateCount === 1 ? "" : "s") +
            (race.settled ? " on the ballot" : "") + "</span>"
          );
        } else if (race.settled && res) {
          var gone = res.eliminated + res.withdrawn + res.unlisted;
          badges.push(
            '<span class="badge badge-neutral" title="' + KYC.escapeAttr(
              "The primary has been held. Of those who filed with the FEC, " +
              res.eliminated + " lost, " + res.withdrawn + " withdrew and " +
              res.unlisted + " were not on the primary ballot."
            ) + '">No challenger on the ballot' +
            (gone ? " &middot; " + gone + " out" : "") + "</span>"
          );
        } else if (race.filedCount) {
          badges.push(
            '<span class="badge badge-neutral" title="' +
            KYC.escapeAttr(
              race.filedCount + " people have filed with the FEC for this seat, " +
              "but none has yet reported raising $5,000 - the point at which " +
              "federal law treats someone as a candidate."
            ) + '">' + race.filedCount + " filed, none past $5k</span>"
          );
        } else {
          badges.push('<span class="badge badge-neutral">Nobody has filed</span>');
        }

        /* People the results page puts on the ballot but the FEC has no
         * filing for. Leaving them off would make the header lie. */
        if (res && res.otherNominees && res.otherNominees.length) {
          badges.push(
            '<span class="badge badge-warn" title="' + KYC.escapeAttr(
              "Also on the November ballot per the published results, but with no " +
              "FEC filing over $5,000, so no profile: " + res.otherNominees.join(", ")
            ) + '">+ ' + res.otherNominees.length + " on ballot without a filing</span>"
          );
        }

        if (race.contested && race.filedCount) {
          badges.push(
            '<span class="badge badge-neutral" title="' +
            KYC.escapeAttr(
              "Total filings with the FEC for this seat, including the sitting " +
              "member and everyone below the $5,000 threshold."
            ) + '">' + race.filedCount + " filed in total</span>"
          );
        }
        var running = group.people.filter(function (p) { return !offBallot(p); });
        var out = group.people.filter(offBallot);
        var body = '<div class="card-grid">' + running.map(card).join("") + "</div>";
        if (out.length) {
          body +=
            '<details class="race-out"><summary>' + out.length +
            " no longer in this race &mdash; lost the primary, withdrew, or were " +
            "not on the primary ballot</summary>" +
            '<div class="card-grid">' + out.map(card).join("") + "</div></details>";
        }
        return [
          '<section class="race">',
          '<div class="race-head"><h3 class="race-title">',
          KYC.escapeHtml(race.label), "</h3>", badges.join(""), "</div>",
          body,
          "</section>",
        ].join("");
      })
      .join("");
  }

  function render() {
    var grid = doc.getElementById("results");
    var empty = doc.getElementById("noResults");
    var label = doc.getElementById("resultsLabel");

    label.textContent = visible.length
      ? "Showing " + visible.length.toLocaleString() + " of " +
        data.length.toLocaleString() + " profiles"
      : "No profiles match these filters";

    if (!visible.length) {
      grid.innerHTML = "";
      empty.hidden = false;
      return;
    }
    empty.hidden = true;

    if (state.view === "race") {
      grid.className = "";
      grid.innerHTML = raceSections(visible);
    } else {
      grid.className = "card-grid";
      grid.innerHTML = visible.map(card).join("");
    }
  }

  function apply() {
    visible = data.filter(matches);
    visible.sort(SORTS[state.sort] || SORTS.region);
    KYC.router.writeFilters({
      q: state.q,
      chamber: state.chamber,
      party: state.party,
      role: state.role,
      state: state.state,
      election: state.election,
      eliminated: state.eliminated === "show" ? "show" : "",
      sort: state.sort === "region" ? "" : state.sort,
      view: state.view === "grid" ? "" : state.view,
    });
    render();
  }

  /* --------------------------------------------------------------- chrome */

  /** Chips within a group are mutually exclusive; clicking the active one in
   *  an optional group clears it. */
  function syncChips() {
    Array.prototype.forEach.call(
      doc.querySelectorAll("[data-group]"),
      function (chip) {
        var group = chip.getAttribute("data-group");
        var active = state[group] === chip.getAttribute("data-value");
        chip.setAttribute("aria-pressed", String(active));
      }
    );
  }

  function initChips() {
    doc.querySelector(".toolbar").addEventListener("click", function (event) {
      var chip = event.target.closest("[data-group]");
      if (!chip) return;

      var group = chip.getAttribute("data-group");
      var value = chip.getAttribute("data-value");
      var optional = chip.hasAttribute("data-optional");

      var cleared = group === "eliminated" ? "hide" : "all";
      state[group] = optional && state[group] === value ? cleared : value;
      syncChips();
      apply();
    });

    var toggle = doc.getElementById("raceViewToggle");
    toggle.addEventListener("click", function () {
      state.view = state.view === "race" ? "grid" : "race";
      toggle.setAttribute("aria-pressed", String(state.view === "race"));
      apply();
    });
  }

  function initStateFilter() {
    var select = doc.getElementById("stateSelect");
    var seen = {};
    data.forEach(function (item) {
      if (item.state && item.state !== "N/A") seen[item.state] = true;
    });
    Object.keys(seen).sort().forEach(function (code) {
      var option = doc.createElement("option");
      option.value = code;
      option.textContent = code;
      select.appendChild(option);
    });
    select.addEventListener("change", function () {
      state.state = select.value;
      apply();
    });
  }

  function initSearch() {
    var input = doc.getElementById("searchInput");
    input.addEventListener(
      "input",
      KYC.debounce(function () {
        state.q = input.value.toLowerCase().trim();
        apply();
      }, 140)
    );
  }

  function initSort() {
    var select = doc.getElementById("sortBy");
    select.addEventListener("change", function () {
      state.sort = select.value;
      apply();
    });
  }

  /* One delegated listener for the whole grid, rather than an inline onclick
   * with a profile id interpolated into every one of 594 cards. */
  function initCards() {
    doc.getElementById("results").addEventListener("click", function (event) {
      var card = event.target.closest("[data-id]");
      if (card) KYC.profile.open(card.getAttribute("data-id"));
    });
  }

  /* -------------------------------------------------------------- routing */

  function applyRoute(route) {
    if (route.view === "profile" && KYC.profile.open(route.id, { fromRoute: true })) {
      return;
    }
    if (KYC.profile.isOpen()) KYC.profile.close();

    var params = route.params || {};
    state.q = params.q || "";
    state.chamber = params.chamber || "all";
    state.party = params.party || "all";
    state.role = ROLE_TEST[params.role] ? params.role : "all";
    state.election = params.election || "all";
    state.eliminated = params.eliminated === "show" ? "show" : "hide";

    /* The challenger filter used to live in the election group. Links shared
     * before it moved still work. */
    if (params.election === "candidate") {
      state.role = "candidate";
      state.election = "all";
    }
    state.state = params.state || "all";
    state.sort = SORTS[params.sort] ? params.sort : "region";
    state.view = params.view === "race" ? "race" : "grid";

    doc.getElementById("searchInput").value = state.q;
    doc.getElementById("stateSelect").value = state.state;
    doc.getElementById("sortBy").value = state.sort;
    doc.getElementById("raceViewToggle")
      .setAttribute("aria-pressed", String(state.view === "race"));
    syncChips();
    apply();
  }

  /* ----------------------------------------------------------------- boot */

  KYC.ready(function () {
    if (!data.length) {
      doc.getElementById("resultsLabel").textContent =
        "Profile data did not load. Run: python build_profile_site.py";
      return;
    }
    KYC.profile.ensure();
    initChips();
    initStateFilter();
    initSearch();
    initSort();
    initCards();
    KYC.router.onChange(function () { applyRoute(KYC.router.read()); });
    applyRoute(KYC.router.read());
  });
})(window);
