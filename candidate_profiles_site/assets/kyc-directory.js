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
  // How well each shown profile matched the query (KYC.queryScore).
  var scores = new Map();
  // How many the filters match that the "out of the race" toggle hides.
  var hiddenOut = 0;
  // The best score any profile the filters match had for the query.
  var bestProfile = Infinity;

  /* ------------------------------------------------------------ filtering */

  var PARTY_TEST = {
    Democrat: function (item) { return String(item.party).indexOf("Democrat") !== -1; },
    Republican: function (item) { return item.party === "Republican"; },
    Independent: function (item) { return KYC.partyKey(item) === "i"; },
  };

  /* Who is actually in Congress. Since the field came from the FEC, 79% of
   * profiles are people who do not hold the seat, so "show me my
   * representatives" needs to be one click rather than a search. A former
   * member - a 2026 incumbent who has left - is neither. */
  var ROLE_TEST = {
    member: function (item) { return KYC.seated(item); },
    candidate: function (item) { return !!item.isCandidate; },
  };

  var offBallot = KYC.cards.offBallot;

  var ELECTION_TEST = {
    // The 2026 Senate races: who held each seat on the ballot, by the seat
    // they held (heldRaceId, from the pipeline), and everyone running for
    // them. The chip showed only the holders - Tuberville, Ernst, Durbin
    // and the rest leaving - and none of the people on the ballot (GRID-10).
    // A member running for the Senate is there once, as their filing's
    // profile, which is the one the race lists, or as themselves when they
    // have none. The key stays, so links shared under it still work.
    senateUp26: function (item) {
      var senate = function (id) { return String(id || "").indexOf("S-") === 0; };
      if (item.heldRaceId && senate(item.heldRaceId)) return true;
      if (!item.heldRaceId && item.seatUp2026 && !item.isCandidate &&
          item.chamber.indexOf("Senate") !== -1) return true;
      if (!item.isCandidate) return senate(item.contestRaceId) && !KYC.otherCampaign(item);
      return senate(item.raceId);
    },
    // Incumbents whose seat is up but who are not running again.
    // Not a member running again under a new district number (renumbered):
    // they are seeking re-election, for a seat with another number.
    notSeeking: function (item) {
      return item.seatUp2026 && !item.isCandidate && !item.seekingReelection2026 &&
        !item.renumbered;
    },
    // Kept for links shared before the chip changed: 469 of 475 races had
    // someone besides the holder in them, so it barely narrowed the grid
    // and read as "competitive" (GRID-13).
    contested: function (item) {
      return !!item.raceId && contestedRaces.has(item.raceId);
    },
    // The races whose head reads "No challenger on the ballot": the
    // primary is settled and nobody but the holder is on its November
    // ballot, profile or not - the same test as the head (kyc-cards.js
    // raceBadges), so the chip and the races never disagree (rule 73).
    unchallenged: function (item) {
      var rid = item.isCandidate ? item.raceId : (item.heldRaceId || item.raceId);
      return !!rid && unchallengedRaces.has(rid);
    },
  };

  var contestedRaces = new Set(
    races.filter(function (r) { return r.contested; }).map(function (r) { return r.id; })
  );
  var unchallengedRaces = new Set(
    races.filter(function (r) { return r.settled && !r.contested && r.results; })
      .map(function (r) { return r.id; })
  );

  function matchesFilters(item) {
    if (state.q && score(item) < 0) return false;

    if (state.chamber !== "all" && item.chamber.indexOf(state.chamber) === -1) {
      return false;
    }
    if (state.party !== "all" && !PARTY_TEST[state.party](item)) return false;
    if (state.role !== "all" && !ROLE_TEST[state.role](item)) return false;
    if (state.state !== "all" && item.state !== state.state) return false;
    if (state.election !== "all" && !ELECTION_TEST[state.election](item)) return false;
    return true;
  }

  function score(item) {
    if (!state.q) return 3;
    if (!scores.has(item)) scores.set(item, KYC.queryScore(item, state.q));
    return scores.get(item);
  }

  /* Only challengers, and members who have since left, are hidden. A
   * sitting member who lost their primary is still in Congress until
   * January and must stay under "Sitting members" - hiding John Cornyn
   * left the Senate one short. */
  function hideable(item) {
    return !KYC.seated(item) && offBallot(item);
  }

  function matches(item) {
    var ok = matchesFilters(item);
    // The best a profile matched the query by, hidden or not: a full name
    // that names a profile leaves the other officials' namesakes out.
    if (ok && state.q) bestProfile = Math.min(bestProfile, score(item));
    if (state.eliminated === "hide" && hideable(item)) {
      if (ok) hiddenOut += 1;
      return false;
    }
    return ok;
  }

  /* -------------------------------------------------------------- sorting */

  /* States by name: by postal code, Alaska came before Alabama and American
   * Samoa between Arkansas and Arizona (GRID-20). */
  function byState(a, b) {
    return KYC.stateName(a.state).localeCompare(KYC.stateName(b.state));
  }

  /* By the surname each person is listed under in their race (the
   * pipeline's `surname`, from Congress's record or the FEC filing), then
   * the whole name: "Name, A to Z" read Aaron Bean, Aaron Flint, Aaron Gies. */
  function bySurname(a, b) {
    return String(a.surname || a.name).localeCompare(String(b.surname || b.name)) ||
      a.name.localeCompare(b.name);
  }

  var SORTS = {
    name: bySurname,
    "age-desc": function (a, b) { return ageOrder(a, b, -1); },
    "age-asc": function (a, b) { return ageOrder(a, b, 1); },
    senate26: function (a, b) {
      var rank = function (x) {
        return x.chamber.indexOf("Senate") !== -1 && (x.seatUp2026 || x.isCandidate)
          ? 0 : 1;
      };
      return (
        rank(a) - rank(b) ||
        byState(a, b) ||
        (a.isCandidate ? 1 : 0) - (b.isCandidate ? 1 : 0) ||
        bySurname(a, b)
      );
    },
    // Within a seat by surname, as the race sections list them: by first
    // name, Amish Shah came before David Schweikert under "Listed by
    // surname." in the races.
    region: function (a, b) {
      var chamber = function (x) { return x.chamber.indexOf("Senate") !== -1 ? 0 : 1; };
      return (
        chamber(a) - chamber(b) ||
        byState(a, b) ||
        KYC.districtOrder(a) - KYC.districtOrder(b) ||
        bySurname(a, b)
      );
    },
  };

  /* A person with no birthdate on record goes after everyone with one,
   * under a divider that says how many (GRID-20): 79% of challengers have
   * none, and the age sorts put them last without a word. */
  function ageOrder(a, b, dir) {
    var x = KYC.ageOf(a);
    var y = KYC.ageOf(b);
    if (x === null || y === null) return (x === null ? 1 : 0) - (y === null ? 1 : 0) || bySurname(a, b);
    return dir * (x - y) || bySurname(a, b);
  }

  function ageSort() {
    return state.sort === "age-desc" || state.sort === "age-asc";
  }

  /* ------------------------------------------------------------ rendering */

  /** One card, with what this view says about it: the age under an age
   *  sort, and where a query matched when it was not the name, the office
   *  or the place (GRID-05). */
  function card(item) {
    var notes = [];
    if (ageSort() && KYC.ageOf(item) !== null) notes.push("Age " + KYC.ageOf(item));
    if (state.q && score(item) === 3) {
      var hit = KYC.searchSnippet(item, state.q);
      if (hit) notes.push(hit.label + ": " + hit.text);
    }
    return KYC.cards.card(item, notes.length ? { note: notes.join(" · ") } : null);
  }

  /* The races view: every race the shown people are in, by state name,
   * Senate before House, then by district (GRID-23, VISUALS-36). The races
   * come from the pipeline most contested first, and the view opened on
   * LA-5, LA-6, Montana's Senate seat and LA-4, with no state headings,
   * under a note saying it listed races seat by seat. */
  function raceOrder(a, b) {
    return KYC.stateName(a.state).localeCompare(KYC.stateName(b.state)) ||
      (a.chamber === "Senate" ? 0 : 1) - (b.chamber === "Senate" ? 0 : 1) ||
      (Number(a.district) || 0) - (Number(b.district) || 0) ||
      String(a.id).localeCompare(String(b.id));
  }

  function racesShown(items) {
    var shown = new Set(items.map(function (x) { return x.id; }));
    // In race context the people the primary removed are part of the story,
    // so they are folded under the race whatever the grid toggle says.
    data.forEach(function (item) {
      if (hideable(item) && matchesFilters(item)) shown.add(item.id);
    });
    return races.slice().sort(raceOrder).map(function (race) {
      var people = race.incumbentIds
        .concat(race.candidateIds)
        .filter(function (id) { return shown.has(id); })
        .map(KYC.byId)
        .filter(Boolean);
      return { race: race, people: people };
    }).filter(function (r) { return r.people.length; });
  }

  function stateAnchor(code) {
    return "race-state-" + code;
  }

  /* A flat grid of 594 cards answers "who is in Congress". It does not answer
   * the question a voter actually has, which is "who is running for my seat". */
  function raceSections(list) {
    var out = [];
    var last = null;
    var states = [];
    list.forEach(function (entry) {
      var code = entry.race.state;
      if (code !== last) {
        last = code;
        states.push(code);
        out.push('<h2 class="race-state-heading" id="' + KYC.escapeAttr(stateAnchor(code)) +
          '" tabindex="-1">' + KYC.escapeHtml(KYC.stateName(code)) + "</h2>");
      }
      // The people the primary removed are drawn when their list is opened:
      // 2,515 cards at once was 3.3 MB of markup (GRID-14).
      out.push(KYC.cards.raceSection(entry.race, entry.people, { lazyOut: true }));
    });
    var jump = states.length > 1
      ? '<div class="race-jump"><label for="raceJump">Jump to a state</label> ' +
        '<select id="raceJump" class="select">' +
        '<option value="">Choose a state…</option>' + states.map(function (code) {
          return '<option value="' + KYC.escapeAttr(code) + '">' +
            KYC.escapeHtml(KYC.stateName(code)) + "</option>";
        }).join("") + "</select></div>"
      : "";
    return jump + out.join("");
  }

  /* The Senate by the year each seat is next decided (assets/kyc-senate.js).
   * The view is the Senate by definition, so the chamber filter does not
   * apply - a House member running for a Senate seat belongs under it.
   * Every other filter narrows what is shown. */
  function senateMatches(item) {
    var chamber = state.chamber;
    state.chamber = "all";
    try {
      return matchesFilters(item);
    } finally {
      state.chamber = chamber;
    }
  }

  /* No profile carries a ZIP code: "85004" in the search found nobody and
   * said to try a state code (GRID-06). A ZIP code is answered by "Find who
   * represents you" in the hero instead, once per ZIP code typed, whatever
   * the grid finds: a profile's text can hold the number too. */
  var askedZip = "";
  function searchedZip() {
    var m = /^(\d{5})$/.exec(String(state.q || "").trim());
    return m && KYC.findRep ? m[1] : "";
  }

  function askZip() {
    var zip = searchedZip();
    zipNote(zip);
    if (!zip) {
      // Typed again after a clear, the same ZIP code is asked again.
      askedZip = "";
      return;
    }
    if (zip === askedZip) return;
    askedZip = zip;
    KYC.findRep.ask(zip);
  }

  /* The empty grid says where the ZIP code was answered, with a way there:
   * on a wide screen the hero scrolls away with the results (PR #104
   * review). A button, not a "#findrep" link, which the router would read
   * as a view and clear the search. */
  function zipNote(zip) {
    var empty = doc.getElementById("noResults");
    if (!empty) return;
    var note = empty.querySelector(".empty-zip");
    if (!zip) {
      if (note) note.hidden = true;
      return;
    }
    if (!note) {
      note = doc.createElement("p");
      note.className = "empty-zip";
      empty.insertBefore(note, empty.querySelector("p"));
      empty.addEventListener("click", function (event) {
        if (event.target.closest && event.target.closest("[data-findrep-reveal]")) KYC.findRep.reveal();
      });
    }
    note.hidden = false;
    note.innerHTML = "No profile carries a ZIP code: " + KYC.escapeHtml(zip) + " is answered " +
      "above, under Find who represents you. " +
      '<button type="button" class="btn" data-findrep-reveal>See the answer</button>';
  }

  /* The results line's words for a ZIP code, said wherever the line is. */
  function zipWords() {
    return searchedZip() ? " The ZIP code is answered above, under Find who represents you." : "";
  }

  /* What was searched for, as the reader typed it. */
  function typed() {
    return ((doc.getElementById("searchInput") || {}).value || state.q).trim();
  }

  /* " matching “warren”", " for TX-35", " in Texas": what narrowed the
   * list, in words, so a reader who typed a name can tell a miss from a
   * filter they forgot was on - on a phone the filters are folded away
   * (GRID-22). */
  function narrowed() {
    var text = "";
    if (state.q) {
      var place = KYC.queryLabel(state.q);
      text += place ? " for “" + typed() + "” (" + place + ")"
        : " matching “" + typed() + "”";
    }
    if (state.state !== "all") text += " in " + KYC.stateName(state.state);
    return text;
  }

  /* What the line says when no card is shown, as markup: why a seat named
   * does not exist; that the people found are out of the race, with the
   * switch that shows them - "No profiles matching “Gulrez Khan”" hid the
   * one person it had found; and that the officials found below are not
   * profiles. */
  function emptyLabel(officials) {
    var note = state.q ? KYC.queryNote(state.q) : "";
    var html = KYC.escapeHtml("No profiles" + (narrowed() || " match these filters") +
      (narrowed() && activeFilters() ? " with these filters" : "") + (note ? ". " + note : "."));
    if (hiddenOut && state.eliminated === "hide" && state.view !== "senate") {
      html += " " + KYC.escapeHtml(plural(hiddenOut, "person", "people") + " out of the race " +
        "(lost a primary, withdrew, or not on the ballot) " + (hiddenOut === 1 ? "matches" : "match") +
        " and " + (hiddenOut === 1 ? "is" : "are") + " hidden.") + outToggle();
    }
    if (officials) {
      html += " " + KYC.escapeHtml("The people found below are listed elsewhere on the site, " +
        "each linked to the page about them.");
    }
    return html + KYC.escapeHtml(zipWords());
  }

  function plural(n, one, many) {
    return n.toLocaleString() + " " + (n === 1 ? one : many);
  }

  /* The results line says what is hidden, with the switch beside it:
   * "Showing 1,114 of 2,568" never said that 1,454 people out of the race
   * were left out (GRID-14). */
  function outToggle() {
    var show = state.eliminated === "show";
    return ' <button type="button" class="link-button" data-out-toggle aria-pressed="' +
      String(show) + '">' + (show ? "Hide them" : "Show them") + "</button>";
  }

  function renderLabel(label, html) {
    label.innerHTML = html;
  }

  function gridLabel() {
    var n = visible.length;
    var html = "Showing " + KYC.escapeHtml(plural(n, "profile", "profiles") + narrowed());
    var out = visible.filter(hideable).length;
    if (state.eliminated === "show") {
      html += out ? KYC.escapeHtml(", " + out.toLocaleString() + " of them out of the race " +
        "(lost a primary, withdrew, or not on the ballot).") + outToggle() : ".";
    } else {
      html += KYC.escapeHtml(": " + (state.role === "candidate" ? "candidates still running"
        : "people in office or still running") + ".");
      if (hiddenOut) {
        html += " " + KYC.escapeHtml(plural(hiddenOut, "person", "people") +
          " out of the race (lost a primary, withdrew, or not on the ballot) " +
          (hiddenOut === 1 ? "is" : "are") + " hidden.") + outToggle();
      }
    }
    return html + challengerNote() + KYC.escapeHtml(zipWords());
  }

  /* The Challengers chip and the sidebar's "Challengers on the ballot"
   * count different people (GRID-12): the chip is the profiles, open-seat
   * candidates and those whose ballot status is not known among them; the
   * sidebar counts everyone on the ballot, profile or not. Said where the
   * chip's count is. */
  function challengerNote() {
    if (state.role !== "candidate") return "";
    var unknown = visible.filter(function (p) {
      var spec = KYC.standing(p, "card");
      return spec && spec.unknown;
    }).length;
    var election = (KYC.meta().election || {});
    var parts = [];
    if (unknown) {
      parts.push(plural(unknown, "of them has", "of them have") + " a ballot status this site " +
        "does not know, so the sidebar does not count them");
    }
    if (state.state === "all" && !state.q && election.renumbered) {
      // The sidebar's "with a profile here" counts them; this chip, which
      // is the filings, does not: they are under Sitting members.
      parts.push("the sidebar also counts " + plural(election.renumbered, "member", "members") +
        " running under a new district number, who are under Sitting members here");
    }
    if (state.state === "all" && !state.q && election.challengersUnprofiled) {
      parts.push("the sidebar also counts " + election.challengersUnprofiled.toLocaleString() +
        " people on the ballot with no FEC filing over $5,000, and so no profile here");
    }
    return parts.length ? '<span class="results-note"> ' +
      KYC.escapeHtml(parts.join("; ").replace(/^./, function (c) { return c.toUpperCase(); }) +
        ".") + "</span>" : "";
  }

  function renderSenate(grid, empty, label, officials) {
    var view = KYC.senate.render(data, races, {
      matches: senateMatches,
      showOut: state.eliminated === "show",
    });
    if (view.people) {
      label.textContent = "Showing " + view.people.toLocaleString() + " profiles across " +
        view.seats.toLocaleString() + " Senate seat" + (view.seats === 1 ? "" : "s") + narrowed() +
        (zipWords() ? "." + zipWords() : "");
    } else {
      renderLabel(label, emptyLabel(officials));
    }
    grid.className = "senate-view";
    grid.innerHTML = view.html;
    empty.hidden = view.people > 0 || officials;
    showLegend(view.people > 0);
  }

  /* The key to the labels, only over cards it explains. */
  function showLegend(on) {
    var slot = doc.getElementById("statusLegend");
    if (slot) slot.hidden = !on;
  }

  function syncViewToggles() {
    syncFiltersCount();
    var race = doc.getElementById("raceViewToggle");
    var senate = doc.getElementById("senateViewToggle");
    if (race) race.setAttribute("aria-pressed", String(state.view === "race"));
    if (senate) senate.setAttribute("aria-pressed", String(state.view === "senate"));
  }

  function render() {
    var grid = doc.getElementById("results");
    var empty = doc.getElementById("noResults");
    var label = doc.getElementById("resultsLabel");
    renderActiveFilters();
    var officials = renderOfficials();
    askZip();

    if (state.view === "senate" && KYC.senate) {
      if (observer) { observer.disconnect(); observer = null; }
      renderSenate(grid, empty, label, officials);
      return;
    }

    if (!visible.length) {
      renderLabel(label, emptyLabel(officials));
      grid.innerHTML = "";
      // "Nothing matches" under the official who did (GRID-07), or over a
      // match the out-of-the-race switch hides: the line says which.
      empty.hidden = officials || (hiddenOut > 0 && state.eliminated === "hide");
      showLegend(false);
      return;
    }
    empty.hidden = true;
    showLegend(true);

    if (state.view === "race") {
      if (observer) { observer.disconnect(); observer = null; }
      var list = racesShown(visible);
      var people = 0;
      var out = 0;
      list.forEach(function (entry) {
        entry.people.forEach(function (p) { if (offBallot(p)) out += 1; else people += 1; });
      });
      renderLabel(label, KYC.escapeHtml("Showing " + plural(list.length, "race", "races") +
        narrowed() + ": " + plural(people, "person", "people") + " on the ballot or holding " +
        "the seat" + (out ? ", and " + out.toLocaleString() + " out of the race folded under " +
        "each" : "") + ". Races by state, Senate before House, then by district." + zipWords()));
      grid.className = "";
      // The races, then which party the markets expect to hold each chamber.
      grid.innerHTML = raceSections(list) +
        (KYC.odds ? KYC.odds.control("senate") + KYC.odds.control("house") : "");
      return;
    }
    renderLabel(label, gridLabel());
    grid.className = "card-grid";
    renderWindow(grid, visible, 0);
  }

  /* The grid can hold 2,500 cards with every filter off. Building them all
   * at once made the first paint wait on 2,500 image elements; the page now
   * renders a screenful and appends the rest as the reader scrolls, the way
   * a feed does, with a button for anyone whose browser lacks the observer. */
  var PAGE = 120;
  var observer = null;

  /* Where the people with no birthdate start, under an age sort. */
  function firstUnknownAge(items) {
    if (!ageSort()) return -1;
    for (var i = 0; i < items.length; i++) if (KYC.ageOf(items[i]) === null) return i;
    return -1;
  }

  function renderWindow(grid, items, from) {
    var slice = items.slice(from, from + PAGE);
    var unknown = firstUnknownAge(items);
    var html = slice.map(function (item, i) {
      var divider = from + i === unknown
        ? '<p class="grid-divider" role="separator">No birthdate on record (' +
          (items.length - unknown).toLocaleString() + ")</p>"
        : "";
      return divider + card(item);
    }).join("");
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

  /* -------------------------------------------------- other officials */

  /* The header's search looks site-wide, and a reader types the names in
   * the news: "Hegseth", "Sotomayor", "Kristi Noem", a governor, a judge.
   * They are not candidates, so never profiles (rule 27): they are listed
   * apart, each linking to the page that is about them - the federal
   * page's dialog, a court's page, a state's page (GRID-07, FEDERAL-03).
   * So are members who left this Congress, with when and who holds the
   * seat now (GRID-08). Their data is fetched the first time a query is
   * typed (KYC.loadData). */
  var OFFICIAL_LIMIT = 8;
  var officialIndex = null;
  // The files asked for and not yet answered. One that fails to load is
  // asked for again with the next query (KYC.loadData allows it).
  var officialsPending = {};

  var OFFICIAL_FILES = [["federal.js", "kycFederal"], ["judiciary/index.js", "kycJudgesIndex"],
    ["stategov.js", "kycStateGov"]];

  function wantOfficials() {
    OFFICIAL_FILES.forEach(function (pair) {
      var file = pair[0];
      if (global[pair[1]] !== undefined || officialsPending[file]) return;
      officialsPending[file] = true;
      KYC.loadData(file, pair[1], function (ok) {
        officialsPending[file] = false;
        if (ok) officialsArrived();
      });
    });
  }

  /* A file that arrives after the list was drawn: the officials are
   * matched again, and an empty list's line and empty state with them. */
  function officialsArrived() {
    officialIndex = null;
    if (!listDrawn) return;
    if (!visible.length || state.view === "senate") render();
    else renderOfficials();
  }

  var KIND_ORDER = { executive: 0, justice: 1, governor: 2, officer: 3, judge: 4 };
  var STATE_OFFICES = [["governor", "Governor"], ["lt", "Lieutenant Governor"],
    ["ag", "Attorney General"], ["sos", "Secretary of State"]];

  /* An officer row is shown only where the state's page names them as the
   * holder: not a listing the office has not confirmed, nor two sources
   * that disagree, nor a vacancy (kyc-stategov.js officerRow). */
  function namedHolder(off) {
    return off && off.name && !off.disputed && !off.unlisted && !off.unconfirmed &&
      !off.vacant && !off.none && !off.notMember;
  }

  function buildOfficialIndex() {
    var rows = [];
    var seen = {};
    var add = function (row) {
      var key = row.id || row.kind + ":" + row.state + ":" + KYC.searchFold(row.name);
      if (seen[key]) return;
      seen[key] = true;
      rows.push(row);
    };
    var federal = global.kycFederal;
    if (federal) {
      [federal.president, federal.vicePresident].forEach(function (p) {
        if (p && p.id && p.name) {
          add({ id: p.id, name: p.name, kind: "executive", role: p.office,
                href: "federal/index.html#/official/" + encodeURIComponent(p.id) });
        }
      });
      (federal.offices || []).forEach(function (office) {
        var h = office.holder;
        if (!h || !h.id || !h.name) return;
        var role = KYC.holderRole(office);
        add({ id: h.id, name: h.name, kind: "executive",
              role: (role.acting ? "Acting " : "") + (role.title || office.office),
              href: "federal/index.html#/official/" + encodeURIComponent(h.id) });
      });
      ((federal.supremeCourt || {}).members || []).forEach(function (j) {
        add({ id: j.id, name: j.name, kind: "justice",
              role: ((j.justice && j.justice.role) || "Justice") + ", Supreme Court",
              href: "federal/index.html#/official/" + encodeURIComponent(j.id) });
      });
    }
    var courts = {};
    ((federal || {}).courts || []).forEach(function (c) { courts[c.id] = c; });
    (global.kycJudgesIndex || []).forEach(function (row) {
      if (!row[2] || !row[2].length) return;
      // The states their courts sit for, so a state filter keeps them.
      var served = {};
      row[2].forEach(function (c) {
        ((courts[c] || {}).states || []).forEach(function (code) { served[code] = true; });
      });
      add({ id: row[0], name: row[1], alt: row[4], kind: "judge", states: served,
            role: "Judge, " + row[2].map(function (c) { return (courts[c] || {}).name || c; })
              .join("; ") + (row[3] === "senior" ? " (senior status)" : ""),
            href: "courts/" + row[2][0] + ".html#/official/" + encodeURIComponent(row[0]) });
    });
    var states = (global.kycStateGov || {}).states || {};
    Object.keys(states).forEach(function (code) {
      STATE_OFFICES.forEach(function (pair) {
        var off = states[code][pair[0]];
        if (!namedHolder(off)) return;
        add({ name: off.name, state: code, kind: pair[0] === "governor" ? "governor" : "officer",
              role: (off.title || pair[1]) + ", " + KYC.stateName(code),
              href: KYC.stateUrl(code) + "#state-government" });
      });
    });
    return rows;
  }

  /* Which of the officials' files the index was built from: one that
   * arrives later rebuilds it. */
  function officialsLoaded() {
    return OFFICIAL_FILES.map(function (pair) { return global[pair[1]] ? 1 : 0; }).join("");
  }
  var officialsBuiltFrom = "";

  /* `[{row, score}]` for the officials *state.q* names (KYC.nameScore; a
   * state's name lists its governor and officers, at 1). A state filter
   * keeps a state's own officers and the judges whose courts sit for it;
   * the federal executive and the justices serve every state. */
  function officialMatches() {
    if (!state.q) return [];
    if (!officialIndex || officialsBuiltFrom !== officialsLoaded()) {
      officialsBuiltFrom = officialsLoaded();
      officialIndex = buildOfficialIndex();
    }
    var place = KYC.queryPlace(state.q);
    var hits = [];
    officialIndex.forEach(function (row) {
      if (state.state !== "all") {
        if (row.state && row.state !== state.state) return;
        if (row.states && !row.states[state.state]) return;
      }
      var s;
      if (place) {
        s = !place.chamber && place.district === undefined && row.state === place.state ? 1 : -1;
      } else {
        s = KYC.nameScore(state.q, [row.name, row.alt]);
      }
      if (s >= 0) hits.push({ row: row, score: s });
    });
    return hits.sort(function (a, b) {
      return a.score - b.score || KIND_ORDER[a.row.kind] - KIND_ORDER[b.row.kind] ||
        a.row.name.localeCompare(b.row.name);
    });
  }

  function departedMatches() {
    var rows = KYC.meta().departed || [];
    if (!state.q) return [];
    var place = KYC.queryPlace(state.q);
    var hits = [];
    rows.forEach(function (row) {
      if (state.state !== "all" && row.state !== state.state) return;
      var s = 1;
      if (place) {
        if (row.state !== place.state && !place.any) return;
        if (place.chamber && row.chamber !== place.chamber) return;
        if (place.district !== undefined && row.district !== place.district &&
            !(place.district === 1 && row.district === 0)) return;
      } else {
        s = KYC.nameScore(state.q, [row.name].concat(row.aliases || []));
      }
      if (s >= 0) hits.push({ row: row, score: s });
    });
    return hits.sort(function (a, b) { return a.score - b.score; });
  }

  /* Only the best kind of match among the officials and the members who
   * left, and no surname-only namesake once a full name has named
   * someone: "Lindsey Graham" listed two judges named Graham above her,
   * and "Mark Kelly" a governor, a lieutenant governor and six judges
   * beside his card. A word found only in part ("Roberts" in "Robertson")
   * goes once one is found whole. */
  function bestHits(found, gone) {
    var best = Infinity;
    found.concat(gone).forEach(function (h) { best = Math.min(best, h.score); });
    var keep = function (h) {
      if (h.score === 2) return best === 2 && bestProfile > 1;
      if (h.score === 1.5) return best === 1.5;
      return true;
    };
    return { found: found.filter(keep), gone: gone.filter(keep) };
  }

  /* The seat in the words the place gives it (rule 75): Puerto Rico's
   * Resident Commissioner, a delegate, never a territory's "Representative". */
  var WITH_THE = { DC: true, MP: true, VI: true };

  function seatWords(row) {
    var name = KYC.stateName(row.state);
    if (row.chamber === "Senate") return "U.S. Senator from " + name;
    var title = ((KYC.meta().states || {})[row.state] || {}).delegateTitle;
    if (title) return title + " from " + (WITH_THE[row.state] ? "the " : "") + name;
    return "U.S. Representative, " + row.state + "-" + (row.district ? row.district : "AL");
  }

  /* The day is congress-legislators' end of the term, said as theirs: it
   * can be a day from the chamber's own record (Doug LaMalfa's term ends
   * there on January 5, 2026; the House Clerk records his death on January
   * 6), and "Left Congress on" stated it as the fact. */
  function departedRow(row) {
    var holder = row.holder ? String(row.holder.name) : "";
    var now = row.holder
      ? "The seat is now held by " + '<a href="#/profile/' +
        KYC.escapeAttr(encodeURIComponent(row.holder.id)) + '">' + KYC.escapeHtml(holder) + "</a>" +
        (/\.$/.test(holder) ? "" : ".")
      : "Congress’s membership list seats nobody there now.";
    return '<li class="official-row"><span class="official-name">' + KYC.escapeHtml(row.name) +
      '</span> <span class="official-role">Former ' + KYC.escapeHtml(seatWords(row)) +
      ". Left during this Congress; congress-legislators ends the term on " +
      KYC.escapeHtml(KYC.dateWords(row.left)) + ". " + now + "</span></li>";
  }

  function officialList(found) {
    return '<h2 class="official-results-title">Other officials</h2>' +
      '<p class="official-results-note">Listed for the office they hold now, each linked to ' +
      "the page about it. Anyone also running for Congress has a profile card as well.</p>" +
      '<ul class="official-list">' + found.slice(0, OFFICIAL_LIMIT).map(function (h) {
        var row = h.row;
        return '<li class="official-row"><a class="official-name" href="' +
          KYC.escapeAttr(row.href) + '">' + KYC.escapeHtml(row.name) + "</a> " +
          '<span class="official-role">' + KYC.escapeHtml(row.role) + "</span></li>";
      }).join("") + "</ul>" +
      (found.length > OFFICIAL_LIMIT
        ? '<p class="official-results-note">' + (found.length - OFFICIAL_LIMIT).toLocaleString() +
          ' more. The <a href="federal/index.html#courts">federal page</a> searches every judge, ' +
          'and <a href="states/index.html">each state’s page</a> lists its officers.</p>'
        : "");
  }

  function departedList(gone) {
    return '<h2 class="official-results-title">Former members of this Congress</h2>' +
      '<ul class="official-list">' + gone.map(function (h) { return departedRow(h.row); }).join("") +
      "</ul>" +
      '<p class="official-results-note">From the congress-legislators project’s record of past ' +
      "members. It gives the day it ends each term, which can differ by a day from the House " +
      "Clerk’s or the Senate’s record, and not why the member left.</p>";
  }

  /** Draws the officials and former members the query names; true when
   *  there are any. */
  function renderOfficials() {
    var box = doc.getElementById("officialResults");
    if (!box) return false;
    if (!state.q) { box.hidden = true; box.innerHTML = ""; return false; }
    wantOfficials();
    var hits = bestHits(officialMatches(), departedMatches());
    var found = hits.found;
    var gone = hits.gone;
    if (!found.length && !gone.length) { box.hidden = true; box.innerHTML = ""; return false; }
    // The block with the better match first: a former member named in
    // full above a judge found by a word.
    var goneFirst = gone.length && (!found.length || gone[0].score < found[0].score);
    var parts = [found.length ? officialList(found) : "", gone.length ? departedList(gone) : ""];
    // Namesakes are listed as namesakes (bestHits keeps them only when
    // nobody answers to the whole name).
    var first = (goneFirst ? gone : found)[0];
    var namesakes = first.score === 2
      ? '<p class="official-results-note">Nobody below answers to “' + KYC.escapeHtml(typed()) +
        "”: each shares the surname alone.</p>"
      : "";
    box.innerHTML = namesakes + (goneFirst ? parts[1] + parts[0] : parts[0] + parts[1]);
    box.hidden = false;
    return true;
  }

  /* ----------------------------------------------------------- the list */

  /* The sidebar names the view: Congress for the sitting members,
   * Candidates otherwise (pages.nav_groups). Every redraw passes here, a
   * chip's as much as a link's. */
  function syncNav() {
    var here = state.role === "member" ? "congress" : "candidates";
    Array.prototype.forEach.call(doc.querySelectorAll('.site-nav [data-nav="candidates"], ' +
        '.site-nav [data-nav="congress"]'), function (link) {
      if (link.getAttribute("data-nav") === here) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  /* `quiet` renders without writing the filters into the URL, for the grid
   * drawn underneath a profile someone landed on directly - writing it then
   * would replace the profile link they arrived on. */
  function apply(opts) {
    syncStateLink();
    syncViewToggles();
    syncSort();
    syncNav();
    syncChips();
    scores = new Map();
    hiddenOut = 0;
    bestProfile = Infinity;
    visible = data.filter(matches);
    var order = SORTS[state.sort] || SORTS.region;
    // Best match first, then the chosen order (GRID-05): "Mike Johnson" put
    // a challenger whose text mentions him ahead of the Speaker.
    visible.sort(state.q ? function (a, b) { return score(a) - score(b) || order(a, b); } : order);
    listDrawn = true;
    if (opts && opts.quiet) {
      drawnFor = "{}";
      render();
      return;
    }
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
    drawnFor = JSON.stringify(KYC.router.read().params || {});
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
    syncFiltersCount();
  }

  /* On a phone the chips fold behind one button, which says how many are on
   * so a filtered grid never looks like the whole field - the state among
   * them: #/?state=TX showed 86 people with nothing on screen saying Texas
   * (GRID-22). */
  function activeFilters() {
    return ["chamber", "role", "party", "election"].filter(function (group) {
      return state[group] && state[group] !== "all";
    }).length + (state.eliminated === "show" ? 1 : 0) + (state.view !== "grid" ? 1 : 0) +
      (state.state !== "all" ? 1 : 0);
  }

  function syncFiltersCount() {
    var count = doc.getElementById("filtersCount");
    if (!count) return;
    var n = activeFilters();
    count.textContent = n ? "(" + n + " on)" : "";
  }

  /* What is on, as chips that each take one thing off, and "Clear all"
   * (GRID-11, GRID-22): the toolbar's "All" reset the chamber only, beside
   * other filters still pressed, and on a phone the chips are folded away. */
  /* Values with no chip any more, kept so links shared under them work:
   * the bar read "On: contested ×". */
  var LEGACY_CHIPS = { "election:contested": "Races with someone besides the holder running" };

  function chipText(group, value) {
    var chip = doc.querySelector('[data-group="' + group + '"][data-value="' + value + '"]');
    return chip ? chip.textContent.replace(/\s+/g, " ").trim()
      : LEGACY_CHIPS[group + ":" + value] || value;
  }

  function onFilters() {
    var on = [];
    if (state.q) on.push(["q", "“" + typed() + "”"]);
    if (state.state !== "all") on.push(["state", KYC.stateName(state.state)]);
    ["chamber", "role", "party", "election"].forEach(function (group) {
      if (state[group] !== "all") on.push([group, chipText(group, state[group])]);
    });
    if (state.eliminated === "show") on.push(["eliminated", chipText("eliminated", "show")]);
    if (state.view === "race") on.push(["view", "Grouped by race"]);
    if (state.view === "senate") on.push(["view", "Senate seats by year"]);
    return on;
  }

  function renderActiveFilters() {
    var bar = doc.getElementById("activeFilters");
    if (!bar) return;
    var on = onFilters();
    if (!on.length) { bar.hidden = true; bar.innerHTML = ""; return; }
    bar.hidden = false;
    bar.innerHTML = '<span class="active-filters-label">On:</span> ' + on.map(function (pair) {
      return '<button type="button" class="chip chip-remove" data-clear="' + pair[0] +
        '" aria-label="' + KYC.escapeAttr("Remove " + pair[1]) + '">' + KYC.escapeHtml(pair[1]) +
        ' <span aria-hidden="true">×</span></button>';
    }).join(" ") + ' <button type="button" class="chip chip-clear" data-clear="all">Clear all</button>';
  }

  var RESET = { q: "", chamber: "all", role: "all", party: "all", election: "all",
                eliminated: "hide", state: "all", view: "grid" };

  function clearFilter(key) {
    var keys = key === "all" ? Object.keys(RESET) : [key];
    keys.forEach(function (k) { state[k] = RESET[k]; });
    if (keys.indexOf("q") !== -1) doc.getElementById("searchInput").value = "";
    if (keys.indexOf("state") !== -1) doc.getElementById("stateSelect").value = "all";
    apply();
  }

  function initActiveFilters() {
    var bar = doc.getElementById("activeFilters");
    if (!bar) return;
    bar.addEventListener("click", function (event) {
      var chip = event.target.closest("[data-clear]");
      if (!chip) return;
      clearFilter(chip.getAttribute("data-clear"));
      var next = bar.querySelector("[data-clear]");
      (next || doc.getElementById("searchInput")).focus();
    });
  }

  function initFiltersToggle() {
    var toggle = doc.getElementById("filtersToggle");
    if (!toggle) return;
    var bar = toggle.closest(".toolbar");
    toggle.addEventListener("click", function () {
      var open = bar.getAttribute("data-filters") !== "open";
      bar.setAttribute("data-filters", open ? "open" : "closed");
      toggle.setAttribute("aria-expanded", String(open));
    });
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

    var senate = doc.getElementById("senateViewToggle");
    if (senate) {
      senate.addEventListener("click", function () {
        state.view = state.view === "senate" ? "grid" : "senate";
        apply();
      });
    }
  }

  /* The results line's own switch for the people out of the race. */
  function initLabel() {
    var label = doc.getElementById("resultsLabel");
    label.addEventListener("click", function (event) {
      if (!event.target.closest("[data-out-toggle]")) return;
      state.eliminated = state.eliminated === "show" ? "hide" : "show";
      apply();
      var again = label.querySelector("[data-out-toggle]");
      if (again) again.focus();
    });
  }

  function initStateFilter() {
    var select = doc.getElementById("stateSelect");
    var intro = doc.getElementById("introState");
    var seen = {};
    data.forEach(function (item) {
      if (item.state && item.state !== "N/A") seen[item.state] = true;
    });
    Object.keys(seen).sort(function (a, b) {
      return KYC.stateName(a).localeCompare(KYC.stateName(b));
    }).forEach(function (code) {
      [select, intro].forEach(function (list) {
        if (!list) return;
        var option = doc.createElement("option");
        option.value = code;
        option.textContent = KYC.stateName(code) + " (" + code + ")";
        list.appendChild(option);
      });
    });
    select.addEventListener("change", function () {
      state.state = select.value;
      apply();
    });
    // The intro's picker opens the state's own page - everything about one
    // state is there - but only when asked: navigating on "change" left the
    // page on the first arrow key or typed letter. A page restored from the
    // back cache starts blank again, or choosing the same state did nothing.
    var form = doc.getElementById("introForm");
    if (form && intro) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        if (!intro.value) { intro.focus(); return; }
        KYC.rememberState(intro.value);
        global.location.href = KYC.stateUrl(intro.value);
      });
      global.addEventListener("pageshow", function () { intro.value = ""; });
    }
  }

  /* A filtered state is one click from its own page. */
  function syncStateLink() {
    var link = doc.getElementById("stateSelectLink");
    if (!link) return;
    if (state.state && state.state !== "all") {
      link.hidden = false;
      link.href = KYC.stateUrl(state.state);
      link.textContent = "Open the " + KYC.stateName(state.state) + " page ›";
      KYC.rememberState(state.state);
      KYC.renderRememberedState();
    } else {
      link.hidden = true;
    }
  }

  function initSearch() {
    var input = doc.getElementById("searchInput");
    var run = function () {
      var q = input.value.toLowerCase().trim();
      if (q === state.q) return;
      state.q = q;
      apply();
      // Searching from 800px down the list left the reader among the
      // matches with the count off-screen - under the keyboard, on
      // Samsung Internet, where it shrinks the page.
      var label = doc.getElementById("resultsLabel");
      if (label && label.getBoundingClientRect().top < 0) {
        label.scrollIntoView({ block: "start" });
      }
    };
    input.addEventListener("input", KYC.debounce(run, 140));
    // Escape and the field's own clear button empty the box without an
    // "input" event in some browsers, and the grid stayed filtered by the
    // old query with nothing on screen saying so (GRID-09).
    input.addEventListener("search", run);
    input.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && input.value) {
        input.value = "";
        run();
      }
    });
  }

  /* The sort is a menu (KYC.createMenu), so it is drawn in the theme's own
   * colours and opens the same way on a phone, where it is an icon. It
   * orders the cards only: the races and Senate views list seats in their
   * own order, and the menu says so there. */
  function initSort() {
    KYC.createMenu(doc.getElementById("sortButton"), doc.getElementById("sortPanel"), {
      onSelect: function (item) {
        var key = item.getAttribute("data-sort");
        if (!SORTS[key]) return;
        state.sort = key;
        apply();
      },
    });
  }

  // What the sort does not order, in the view the reader is in.
  var SORT_NOTES = {
    race: "Sorting applies to the cards. The races view lists races by state, Senate before " +
      "House, then by district.",
    senate: "Sorting applies to the cards. The Senate view lists seats by the year each is " +
      "next on the ballot.",
  };

  function syncSort() {
    var current = "";
    Array.prototype.forEach.call(doc.querySelectorAll("#sortPanel [data-sort]"), function (item) {
      var on = item.getAttribute("data-sort") === state.sort;
      item.setAttribute("aria-checked", String(on));
      if (on) current = item.textContent.trim();
    });
    var label = doc.getElementById("sortLabel");
    var button = doc.getElementById("sortButton");
    var note = doc.getElementById("sortNote");
    if (!label || !button || !note) return;       // never stop the list being drawn
    label.textContent = current;
    button.setAttribute("aria-label", "Sort the cards: " + current);
    note.hidden = !SORT_NOTES[state.view];
    if (SORT_NOTES[state.view]) note.textContent = SORT_NOTES[state.view];
  }

  /* One delegated listener for the whole grid, rather than an inline onclick
   * with a profile id interpolated into every one of 594 cards. */
  function initCards() {
    var results = doc.getElementById("results");
    results.addEventListener("click", function (event) {
      var more = event.target.closest("#gridMore");
      if (more) {
        renderWindow(results, visible, parseInt(more.getAttribute("data-from"), 10) || 0);
        return;
      }
      var card = event.target.closest("[data-id]");
      if (card) KYC.profile.open(card.getAttribute("data-id"));
    });
    // A race's people out of the race are drawn when their list opens.
    results.addEventListener("toggle", function (event) {
      if (event.target.matches && event.target.matches("details[data-out-race]")) {
        KYC.cards.fillOut(event.target);
      }
    }, true);
    results.addEventListener("change", function (event) {
      if (event.target.id !== "raceJump" || !event.target.value) return;
      var heading = doc.getElementById(stateAnchor(event.target.value));
      if (heading) {
        heading.scrollIntoView({ block: "start" });
        heading.focus({ preventScroll: true });
      }
    });
  }

  /* The key to the status words on the cards, from the one table that
   * words them (KYC.raceStatusLegend, KYC.cards.legend): about seventeen
   * badges were explained only by hover titles (GRID-19). */
  function initLegend() {
    var slot = doc.getElementById("statusLegend");
    if (!slot || !KYC.cards.legend) return;
    slot.innerHTML = KYC.cards.legend();
  }

  /* -------------------------------------------------------------- routing */

  /* Landing on a shared #/profile/ link opened the dialog and returned before
   * the grid was ever drawn, so the page behind it read "Loading profiles..."
   * with no cards, and closing the dialog showed an empty site. The first
   * route draws the default list underneath whatever it opens. */
  var listDrawn = false;
  /* The filters the list on screen was drawn for. Closing a profile - by
   * its button or Android's back gesture - returns to the same list, and
   * redrawing it cut the grid back to its first 120 cards: a reader 300
   * cards down lost their place and the card they had opened. */
  var drawnFor = null;

  function applyRoute(route) {
    if (route.view === "profile" && KYC.profile.open(route.id, { fromRoute: true })) {
      if (!listDrawn) applyParams({}, { quiet: true });
      return;
    }
    if (KYC.profile.isOpen()) KYC.profile.close();
    if (listDrawn && JSON.stringify(route.params || {}) === drawnFor) return;
    applyParams(route.params || {});
  }

  function applyParams(params, opts) {
    var input = doc.getElementById("searchInput");
    state.q = params.q || "";
    /* A query typed while the profiles were still loading - 3.5 seconds on
     * a throttled phone - was wiped when they arrived (TECH-03). The first
     * draw keeps it when the address names none. */
    var adopted = !listDrawn && !state.q && !!input.value.trim();
    if (adopted) state.q = input.value.toLowerCase().trim();
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
    if (params.view === "senate" && KYC.senate) state.view = "senate";

    if (!adopted) input.value = state.q;
    doc.getElementById("stateSelect").value = state.state;
    doc.getElementById("raceViewToggle")
      .setAttribute("aria-pressed", String(state.view === "race"));
    syncChips();
    apply(opts);
  }

  /* ----------------------------------------------------------------- boot */

  KYC.ready(function () {
    if (!data.length) {
      doc.getElementById("resultsLabel").textContent =
        "Profile data did not load. Run: python build_profile_site.py";
      return;
    }
    KYC.profile.ensure();
    /* Each part of the grid starts on its own. One that throws - a page and
     * a script of two versions, as a reload minutes after a deploy gave -
     * once stopped every part after it, and the grid sat on "Loading
     * profiles..." until a chip was clicked. The list is drawn regardless,
     * the page says something failed, and the error still reaches the
     * console. */
    var failed = [];
    [initChips, initFiltersToggle, initActiveFilters, initLabel, initStateFilter, initSearch,
     initSort, initCards, initLegend]
      .forEach(function (step) {
        try { step(); } catch (err) { failed.push(err); }
      });
    KYC.router.onChange(function () { applyRoute(KYC.router.read()); });
    try {
      applyRoute(KYC.router.read());
    } catch (err) {
      // The draw itself failed: never "Loading profiles..." over nothing.
      failed.push(err);
      doc.getElementById("resultsLabel").textContent =
        "The profiles could not be drawn. Reloading the page usually fixes it.";
    }
    if (failed.length) {
      var note = doc.createElement("p");
      note.className = "state-note results-failed";
      note.setAttribute("role", "status");
      note.textContent = "Part of this page did not start, so some controls may not respond. " +
        "Reloading the page usually fixes it.";
      var results = doc.getElementById("results");
      results.parentNode.insertBefore(note, results);
      failed.forEach(function (err) { global.setTimeout(function () { throw err; }); });
    }
  });
})(window);
