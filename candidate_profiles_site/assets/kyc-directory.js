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

  var OFF_BALLOT = KYC.cards.OFF_BALLOT;
  var offBallot = KYC.cards.offBallot;

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

  var card = KYC.cards.card;

  /* A flat grid of 594 cards answers "who is in Congress". It does not answer
   * the question a voter actually has, which is "who is running for my seat". */
  function raceSections(items) {
    var shown = new Set(items.map(function (x) { return x.id; }));
    // In race context the people the primary removed are part of the story,
    // so they are folded under the race whatever the grid toggle says.
    data.forEach(function (item) {
      if (item.isCandidate && offBallot(item) && matchesFilters(item)) shown.add(item.id);
    });

    return races
      .map(function (race) {
        var people = race.incumbentIds
          .concat(race.candidateIds)
          .filter(function (id) { return shown.has(id); })
          .map(KYC.byId)
          .filter(Boolean);
        return people.length ? KYC.cards.raceSection(race, people) : "";
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
      return;
    }
    grid.className = "card-grid";
    renderWindow(grid, visible, 0);
  }

  /* The grid can hold 2,500 cards with every filter off. Building them all
   * at once made the first paint wait on 2,500 image elements; the page now
   * renders a screenful and appends the rest as the reader scrolls, the way
   * a feed does, with a button for anyone whose browser lacks the observer. */
  var PAGE = 120;
  var observer = null;

  function renderWindow(grid, items, from) {
    var slice = items.slice(from, from + PAGE);
    var html = slice.map(card).join("");
    var more = from + PAGE < items.length;
    if (from === 0) {
      grid.innerHTML = html;
    } else {
      var old = doc.getElementById("gridMore");
      if (old) old.remove();
      grid.insertAdjacentHTML("beforeend", html);
    }
    if (observer) { observer.disconnect(); observer = null; }
    if (!more) return;
    var remaining = items.length - from - PAGE;
    grid.insertAdjacentHTML("beforeend",
      '<button type="button" class="btn grid-more" id="gridMore" data-from="' +
      (from + PAGE) + '">Show ' + Math.min(PAGE, remaining) + " more of " +
      remaining.toLocaleString() + "</button>");
    var sentinel = doc.getElementById("gridMore");
    if (global.IntersectionObserver) {
      observer = new global.IntersectionObserver(function (entries) {
        if (entries.some(function (e) { return e.isIntersecting; })) {
          renderWindow(grid, items, from + PAGE);
        }
      }, { rootMargin: "600px 0px" });
      observer.observe(sentinel);
    }
  }

  function apply() {
    syncStateLink();
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
    Object.keys(seen).sort(function (a, b) {
      return KYC.stateName(a).localeCompare(KYC.stateName(b));
    }).forEach(function (code) {
      var option = doc.createElement("option");
      option.value = code;
      option.textContent = KYC.stateName(code) + " (" + code + ")";
      select.appendChild(option);
    });
    select.addEventListener("change", function () {
      state.state = select.value;
      apply();
    });
  }

  /* A filtered state is one click from its own page. */
  function syncStateLink() {
    var link = doc.getElementById("stateSelectLink");
    if (!link) return;
    if (state.state && state.state !== "all") {
      link.hidden = false;
      link.href = KYC.stateUrl(state.state);
      link.textContent = "Open the " + KYC.stateName(state.state) + " page \u203a";
    } else {
      link.hidden = true;
    }
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
      var more = event.target.closest("#gridMore");
      if (more) {
        renderWindow(doc.getElementById("results"), visible,
                     parseInt(more.getAttribute("data-from"), 10) || 0);
        return;
      }
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
