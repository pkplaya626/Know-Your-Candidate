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

  var data = KYC.people();

  var mode = "senate";
  var selected = "";
  // The House view drawn as the map ("map") or one square per seat
  // ("tiles", VISUALS-27); in the address as layout=tiles.
  var layout = "map";
  // The Senate and House views drawn as who sits now ("now") or as the
  // Congress the 2026 election has elected so far ("elected", rule 104),
  // from the day after Election Day until that Congress sits; in the
  // address as congress=elected.
  var basis = "now";

  /** The elected Congress's figures (KYC.incoming), where the view is the
   *  Senate's or the House's and the reader asked for them; else null. */
  function elected() {
    if (basis !== "elected" || (mode !== "senate" && mode !== "house")) return null;
    return KYC.incoming ? KYC.incoming() : null;
  }

  /** The chamber the view draws, and the state's part of the elected count. */
  function electedPart(code) {
    var m = elected();
    var st = m && (m.states || {})[code];
    return st ? st[mode === "house" ? "house" : "senate"] || null : null;
  }

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
  function senateRace(code) {
    return KYC.races().filter(function (r) {
      return r.chamber === "Senate" && r.state === code;
    })[0] || null;
  }

  function senateDefender(code) {
    var race = senateRace(code);
    if (!race) return null;
    var holder = race.incumbentIds.map(KYC.byId).filter(Boolean)[0];
    if (holder) return holder;
    var inc = race.incumbent;
    return inc ? { id: inc.bioguide, name: inc.name, party: inc.party } : null;
  }

  /* ---------------------------------------------------------------- fills */

  var VACANT_FILL = "var(--vacant-fill)";
  /* Nothing to show is the grey kept for that (--none-fill, hatched by
   * KYC.svgFill): the page's own surface made those states black holes in
   * the dark and AMOLED themes (VISUALS-19, RACES-17). */
  var NONE_FILL = "var(--none-fill)";
  var SPLIT_FILL = "var(--split)";
  var I_FILL = "var(--party-i-fill)";
  // A delegation the seats not yet called could still change (rule 104):
  // a grid of its own, hatched by KYC.svgFill like split and none.
  var PENDING_FILL = "var(--pending-fill)";

  /* "In the general election runoff" -> "in the general election runoff",
   * for a status's words inside a sentence. */
  function lowerFirst(text) {
    text = String(text || "");
    return text.charAt(0).toLowerCase() + text.slice(1);
  }

  /** A party's colour, lighter in weight: a majority short of the whole
   *  delegation, or an open seat (--party-r-tint, --party-d-tint in
   *  kyc.css). A step of lightness from the party's own colour, which a
   *  reader who cannot see hue still tells apart. */
  function tint(key) {
    return "var(--party-" + key + "-tint)";
  }

  /* The House view in five labelled steps. A continuous ramp from red
   * through purple to blue had no values on it, so a reader could learn a
   * delegation's split only by clicking each state, and to a deuteranope
   * its Democratic half was one colour (VISUALS-09, VISUALS-03). An even
   * delegation is the hatched split. */
  var HOUSE_STEPS = [
    ["allR", "var(--party-r)", "All R"],
    ["majR", tint("r"), "R majority"],
    ["even", SPLIT_FILL, "Even"],
    ["majD", tint("d"), "D majority"],
    ["allD", "var(--party-d)", "All D"],
  ];

  /* *seats* counts every seat, independents' and vacant ones too: "All R"
   * is said only of a delegation whose every seat is Republican, never of
   * two Republicans beside an independent or an empty seat. */
  function houseStep(d, r, seats) {
    if (r === seats) return HOUSE_STEPS[0];
    if (d === seats) return HOUSE_STEPS[4];
    return d > r ? HOUSE_STEPS[3] : d < r ? HOUSE_STEPS[1] : HOUSE_STEPS[2];
  }

  /** The word's colour on a fill a callout is drawn in (kyc.js fillInk). */
  function inkFor(fill) {
    return KYC.fillInk(fill);
  }

  function stateMode() {
    return KYC.stategov.modes.indexOf(mode) !== -1;
  }

  /* The elected view's fills, by the step kyc/incoming.py works out for
   * each delegation over every way its uncalled seats could go: a step
   * the uncalled seats cannot change is drawn as decided, and one they
   * could is "not settled in the results this site read" - a claim about
   * this site's read (rule 19), never that the election is undecided. */
  var STEP_FILL = {
    allR: "var(--party-r)", majR: tint("r"), even: SPLIT_FILL, majD: tint("d"), allD: "var(--party-d)",
    split: SPLIT_FILL, allI: I_FILL, vacant: VACANT_FILL, none: NONE_FILL, undecided: PENDING_FILL,
  };
  var STEP_WORDS = {
    senate: { allR: "both Republican", allD: "both Democratic", split: "split, or one independent",
      allI: "both independent", vacant: "one seat or both vacant", none: "no senators",
      undecided: "not settled in the results this site read" },
    house: { allR: "all Republican", majR: "a Republican majority", even: "even", majD: "a Democratic majority",
      allD: "all Democratic", allI: "all independent", none: "no seats",
      undecided: "not settled in the results this site read" },
  };

  /** The counts of one state's part of the elected Congress, in words. */
  function partWords(part) {
    var n = KYC.incomingWords.totals(part);
    return [["R", "R"], ["D", "D"], ["I", "I"]].filter(function (k) { return n[k[0]]; })
      .map(function (k) { return n[k[0]] + k[1]; })
      .concat(n.vacant ? [n.vacant + " vacant"] : [])
      .concat(n.pending ? [n.pending + " " + KYC.incomingWords.notCalled(elected())] : []).join(", ");
  }

  /** A part of the elected Congress with no seat on the 2026 ballot, in
   *  words: "Neither of Ohio’s seats in the U.S. Senate was on the 2026
   *  ballot: they are counted by who holds each now." */
  function notOnBallot(code) {
    var part = electedPart(code);
    var whose = KYC.possessive(KYC.placeStart(code), "’");
    var vacant = part && part.notUp && part.notUp.vacant;
    if (mode === "house") {
      return whose + " seat in the U.S. House was not on the 2026 ballot" +
        (vacant ? ", and it is vacant now." : ": it is counted by who holds it now.");
    }
    return "Neither of " + KYC.possessive(KYC.placeWords(code), "’") +
      " seats in the U.S. Senate was on the 2026 ballot: they are counted by who holds each now" +
      (vacant ? ", or as vacant." : ".");
  }

  /** The elected panel's lead (rule 104), true whoever the members-elect
   *  are: when they take office, never that they "are not who represents"
   *  the place now - most are re-elected members who do (Jon Ossoff,
   *  Georgia's one senator-elect; PR review) - and, where none of the
   *  place's seats on the ballot is called yet, that none is as of the
   *  read's day, with no members-elect sentence over nobody (Louisiana's
   *  House). The Now view's button follows it. */
  function electedLead(code, m, won, open, nowButton) {
    var esc = KYC.escapeHtml;
    var words = KYC.incomingWords;
    var day = words.readOn(m);
    var place = KYC.placeWords(code);
    var chamber = mode === "house" ? "the U.S. House" : "the U.S. Senate";
    var asOf = (day ? " as of " + day + "," : "") + " in the results this site last read";
    var tail = words.due(m)
      ? " This site has not yet read the new Congress’s membership: " + nowButton("the Now view") +
        " shows who sat as it last read it."
      : null;
    if (!won) {
      return esc((open === 1
        ? KYC.possessive(KYC.placeStart(code), "’") + " race for " + chamber + " on the 2026 ballot is not yet called"
        : "None of " + KYC.possessive(place, "’") + " " + open + " races for " + chamber +
          " on the 2026 ballot is called") + asOf + (open === 1 ? ": no member-elect yet." : ": no members-elect yet.")) +
        (tail || " " + nowButton("The Now view") + " shows who represents " + esc(place) + ".");
    }
    return esc("Elected so far, as the results this site last read" + (day ? ", on " + day + "," : "") +
      " mark the winners. The members-elect " + words.takeOffice(m)) +
      (tail ? "." + tail : "; until then " + nowButton("the Now view") + " shows who represents " + esc(place) + ".");
  }

  /** Fill and hover text for one state in the elected Congress's view. */
  function electedLook(code) {
    var part = electedPart(code);
    var chamber = mode === "house" ? "House" : "Senate";
    if (!part) return { fill: NONE_FILL, text: code + ": no senators (not a state)" };
    var offBallot = !(mode === "house" ? Object.keys(part.seats || {}).length : (part.seats || []).length);
    var fill = STEP_FILL[part.step] || PENDING_FILL;
    var words = STEP_WORDS[mode === "house" ? "house" : "senate"][part.step] || part.step;
    var ordinal = KYC.ordinal(elected().congress);
    return {
      fill: fill,
      ink: inkFor(fill),
      text: offBallot ? code + " " + chamber + ", " + ordinal + " Congress: not on the 2026 ballot, " +
        "counted by who holds " + (mode === "house" ? "it" : "each") + " now: " + partWords(part) :
        code + " " + chamber + ", " + ordinal + " Congress as called so far: " + partWords(part) +
        (part.step === "undecided" ? " (" + words + ": the seats " + KYC.incomingWords.notCalled(elected()) +
            " could change it)"
          : part.uncalled ? " (" + words + " whatever the seats not yet called decide)" : ""),
    };
  }

  /** Fill and hover text for one state in the current mode. */
  function appearance(code) {
    if (stateMode()) return KYC.stategov.look(code, mode);
    if (elected()) return electedLook(code);
    var counts = tally(code);

    if (mode === "senate") {
      var s = counts.senate;
      // The step the build works out for the state's two seats
      // (summary.by_state's senateStep, by incoming.senate_step - the
      // elected view's own, rule 12): a senator beside an empty seat is
      // "one seat or both vacant", never both of that senator's party.
      var info = ((KYC.meta() || {}).states || {})[code];
      var step = info ? info.senateStep : "none";
      var fill = STEP_FILL[step];
      if (!fill) throw new Error("kyc-map: no Senate step for " + code + " (" + step + ")");
      return {
        fill: fill,
        ink: inkFor(fill),
        // D.C. and the territories elect no senators: "0R, 0D" read as a
        // count of senators found.
        text: step === "none" ? code + ": no senators (not a state)" :
          code + " Senate: " + s.r + "R, " + s.d + "D" + (s.i ? ", " + s.i + "I" : "") +
            (s.vacant ? ", " + s.vacant + " vacant" : ""),
      };
    }

    if (mode === "house") {
      var h = counts.house;
      var held = h.d + h.r + h.i;
      var fill2;
      if (!held && h.vacant) fill2 = VACANT_FILL;
      else if (!held) fill2 = NONE_FILL;
      else if (h.i === held) fill2 = I_FILL;
      else if (!(h.d + h.r)) fill2 = I_FILL;
      else fill2 = houseStep(h.d, h.r, held + (h.vacant || 0))[1];
      return {
        fill: fill2,
        ink: inkFor(fill2),
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
    // An open seat is the party's colour lighter in weight; a special
    // election is outlined (RACES-21). Both were only in the hover text,
    // which a touch reader never sees.
    var race = senateRace(code) || {};
    var fill3 = key === "vacant" ? VACANT_FILL : race.openSeat && key !== "i" ? tint(key)
      : key === "i" ? I_FILL : "var(--party-" + key + ")";
    return {
      fill: fill3,
      ink: inkFor(fill3),
      special: !!race.special,
      text: code + ": 2026 Senate race — " + (race.special ? "special election, " : "") +
        (race.openSeat ? "open " : "") + party + " seat (" +
        defender.name + (status === "eliminated" ? " lost the primary" :
          status === "advanced" ? " in a primary runoff" :
          status === "elected" ? (own ? " re-elected" : " elected") :
          status === "defeated" ? (own ? " lost re-election" : " lost the election") :
          // The status table's words for the race's December round, never
          // a copy of them here (rule 12).
          status === "runoff" ? " " + lowerFirst(KYC.raceStatusOf(defender, "long").label) :
          // Once the new Congress sits, one its record seats for the term
          // in the status table's words ("seated for the 2027–2033 term").
          status === "nominee" && counted ? (/^Seated for the /.test(KYC.raceStatusOf(defender, "long").label)
            ? " " + lowerFirst(KYC.raceStatusOf(defender, "long").label) : " awaiting result") :
          // Through a top-two or top-four primary, nobody is renominated.
          status === "nominee" && defender.allPartyPrimary ? " advanced to November" :
          status === "nominee" && defender.seekingReelection2026 ?
            (own ? " renominated" : " on the November ballot") :
          // From the day after Election Day nobody is "running" (rule 63):
          // "Richard Durbin not running" stood over Illinois after the
          // election; the verbs are KYC.contestLine's.
          defender.seekingReelection2026 ? (counted ? " ran" : " running") :
          defender.contestLabel ? " " + lowerFirst(KYC.contestLine(defender).verb) + " " +
            KYC.seatInWords(defender.contestLabel) :
          defender.alsoRunningSeat ? (counted ? " ran for " : " running for ") +
            KYC.seatInWords(defender.alsoRunningSeat) :
          counted ? " did not run" : " not running") + ")",
    };
  }

  /* ------------------------------------------------------------------ map */

  var map = KYC.usmap.create({
    look: appearance,
    onSelect: function (code) { select(code); },
    // A special election's state is outlined (RACES-21).
    marked: function (code) { return mode === "senate2026" && !!appearance(code).special; },
    // A state with seats not yet called, in the elected view (rule 104).
    pending: function (code) { var part = electedPart(code); return !!(part && part.uncalled); },
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
      [SPLIT_FILL, "Split, or one independent"],
      [I_FILL, "Both independent", "allIndependent"],
      [VACANT_FILL, "One seat or both vacant", "senateVacant"],
      [NONE_FILL, "No senators (D.C. and territories)"],
    ],
    senate2026: [
      // "Open" is the race's own word: no member who holds the seat is on
      // its ballot. The other key claims nothing about who is running.
      ["var(--party-r)", "Republican seat up", "", "Republican seat that was up"],
      [tint("r"), "Open Republican seat", "open:r"],
      ["var(--party-d)", "Democratic seat up", "", "Democratic seat that was up"],
      [tint("d"), "Open Democratic seat", "open:d"],
      ["special", "Special election (dashed outline)", "special"],
      [NONE_FILL, "No race in 2026"],
    ],
  };

  /** Is a legend key's fill drawn on some state? Only keys the map uses. */
  function legendShown(entry) {
    var want = entry[2];
    if (!want) return true;
    if (want === "allIndependent") return allIndependent("senate");
    if (want === "senateVacant") {
      var states = (KYC.meta() || {}).states || {};
      return Object.keys(states).some(function (code) { return states[code].senateStep === "vacant"; });
    }
    var races = KYC.races().filter(function (r) { return r.chamber === "Senate"; });
    if (want === "special") return races.some(function (r) { return r.special; });
    return races.some(function (r) {
      var held = senateDefender(r.state);
      return r.openSeat && held && KYC.partyKey(held) === want.split(":")[1];
    });
  }

  /** A legend key's swatch, drawn as the map draws its fill (hatched where
   *  the map hatches), naming that fill in data-fill. */
  function swatch(fill) {
    if (fill === "pending-outline") {
      return '<svg class="swatch swatch-pending" data-fill="pending-outline" viewBox="0 0 26 12"' +
        ' aria-hidden="true" focusable="false"><rect x="1" y="1" width="24" height="10"/></svg>';
    }
    /* The key is the map's own dash, on a shape wide enough to show it: a
     * dashed border on a 10px square drew as a solid box, the look of the
     * picked state's outline. */
    if (fill === "special") {
      return '<svg class="swatch swatch-special" data-fill="special" viewBox="0 0 26 12"' +
        ' aria-hidden="true" focusable="false"><rect x="1" y="1" width="24" height="10"/></svg>';
    }
    return '<span class="swatch" data-fill="' + KYC.escapeAttr(KYC.svgFill(fill)) +
      '" style="background:' + KYC.swatchFill(fill) + '"></span>';
  }

  /* Does any state's delegation in *chamber* consist only of independents? */
  function allIndependent(chamber) {
    var states = (KYC.meta() || {}).states || {};
    return Object.keys(states).some(function (code) {
      var b = ((states[code] || {}).balance || {})[chamber] || {};
      return b.I > 0 && !b.D && !b.R;
    });
  }

  /* The elected view's keys, in each chamber's order: only the steps some
   * state is drawn in, and the dotted outline where a state has seats not
   * yet called. "Not yet called as of" a day is the site's own words for
   * its read (rule 19), never "not yet decided"; kept short, since on a
   * laptop every line of the key comes out of the map's height (the
   * elected view's three lines of key drew Texas 36px tall at 1280x800). */
  var ELECTED_KEYS = {
    senate: [["allR", "Both Republican"], ["allD", "Both Democratic"], ["split", "Split, or one independent"],
      ["allI", "Both independent"], ["vacant", "One seat or both vacant"],
      ["undecided", "A race {notCalled}"],
      ["none", "No senators (D.C. and territories)"]],
    house: [["allR", "All R"], ["majR", "R majority"], ["even", "Even"], ["majD", "D majority"],
      ["allD", "All D"], ["allI", "All independent"],
      ["undecided", "Seats {notCalled} could change it"]],
  };

  function electedLegend() {
    var codes = map.codes();
    var drawn = {};
    var pending = false;
    codes.forEach(function (code) {
      var part = electedPart(code);
      drawn[part ? part.step : "none"] = true;
      if (part && part.uncalled) pending = true;
    });
    var chamber = mode === "house" ? "house" : "senate";
    return ELECTED_KEYS[chamber].filter(function (k) { return drawn[k[0]]; })
      .map(function (k) {
        return '<span class="key" data-step="' + k[0] + '">' + swatch(STEP_FILL[k[0]]) +
          KYC.escapeHtml(k[1].replace("{notCalled}", function () { return KYC.incomingWords.notCalled(elected()); })) + "</span>";
      }).join("") + (pending ? '<span class="key" data-step="pending-outline">' + swatch("pending-outline") +
        "Dotted: some seats not yet called</span>" : "");
  }

  function drawLegend() {
    var target = doc.getElementById("mapLegend");
    if (elected()) {
      target.innerHTML = electedLegend();
      return;
    }
    if (stateMode()) {
      target.innerHTML = KYC.stategov.legend(mode).map(function (entry) {
        return '<span class="key">' + swatch(entry[0]) + KYC.escapeHtml(entry[1]) + "</span>";
      }).join("");
      return;
    }
    if (mode === "house") {
      // Each step says what it counts: "R majority" is more Republican
      // than Democratic members, short of all of them.
      target.innerHTML = HOUSE_STEPS.map(function (step) {
        return '<span class="key" data-step="' + step[0] + '">' + swatch(step[1]) +
          KYC.escapeHtml(step[2]) + "</span>";
      }).join("") +
        (allIndependent("house")
          ? '<span class="key">' + swatch(I_FILL) + "All independent</span>" : "") +
        '<span class="key">' + swatch(VACANT_FILL) + "Vacant</span>";
      return;
    }
    // A key's words from the day after Election Day where it has its own
    // (entry[3]): "Republican seat up" read as the next election.
    var after = KYC.electionStatus().phase === "post-election";
    target.innerHTML = LEGENDS[mode]
      .filter(legendShown)
      .map(function (entry) {
        return '<span class="key">' + swatch(entry[0]) +
          KYC.escapeHtml(after && entry[3] ? entry[3] : entry[1]) + "</span>";
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
    // The shared words (KYC.contestLine): "Elected to" after a win, "Ran
    // for" after a loss, and a renumbered seat is "(redrawn)", re-election
    // rather than leaving.
    var line = KYC.contestLine(item);
    var words = line.verb + " " + label + (line.renumbered ? " (redrawn)" : "");
    // A run for another seat is one badge, its result in it: the panel lists
    // members under the seat they hold, so a bare "Elected" at the row's end
    // read as Andy Barr's win in KY-6 (rule 74; KYC.cards.statusBadge says
    // it the same way). "Elected to Senate" says it alone.
    var spec = line.renumbered ? null : KYC.raceStatusOf(item, "short");
    return '<span class="badge ' + line.cls + ' contest" title="' +
      KYC.escapeAttr(line.title + (spec ? " " + spec.title : "")) + '">' + KYC.escapeHtml(words) +
      (spec && line.stage !== "won" ? " &middot; " + KYC.escapeHtml(spec.label) +
        KYC.ballotLineSuffix(item) : "") + "</span>";
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

  /* The run's own status at the row's end, for a member re-elected under a
   * new number (renumbered) beside "Re-elected in CA-40 (redrawn)", as their
   * card says it (KYC.cards.statusBadge); a run for another seat says its
   * result inside the seat's badge (contestSeat). */
  function contestResult(item) {
    return KYC.contestLine(item).renumbered ? contestBadge(item) : "";
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
    // A member re-elected under a new number carries two badges. Both at the
    // row's end squeezed the name to nothing and broke "House • CA-38" over
    // four lines, so the seat ("Running in CA-41 (redrawn)") takes a line
    // under the text and the result ("Nominee") stays at the end, in line
    // with every other row's "Renominated". The grid in kyc.css places them.
    // A run for another seat is the seat's badge, its result in it
    // (contestSeat).
    var elsewhere = !item.isCandidate && item.contestLabel;
    // The person's other roles on this site, each linked to its card (rule
    // 105), by the one helper and outside the row's button, as a card's is:
    // a link cannot sit inside one. The Senate panel's row for Amy
    // Klobuchar said nothing of Minnesota's list for governor, which the
    // governor's-race panel beside it did.
    var also = KYC.alsoHtml(item, { cls: "row-also" });
    var row = [
      '<button type="button" class="person-row" data-id="',
      KYC.escapeAttr(item.id), '">',
      KYC.portraitThumb(item, "38px"),
      '<span class="who">',
      '<span class="name">', KYC.escapeHtml(item.name), "</span>",
      '<span class="office">', KYC.escapeHtml(item.officeLabel), "</span>",
      '<span class="party ', KYC.partyClass(item), '">',
      KYC.escapeHtml(item.party), "</span>",
      "</span>",
      elsewhere ? contestSeat(item) + contestResult(item) : rowBadge(item),
      KYC.icon("chevron"),
      "</button>",
    ].join("");
    return also ? '<div class="person-cell">' + row + also + "</div>" : row;
  }

  /** The 2026 Senate view of a state with no Senate race: said, with when
   *  each sitting senator's seat is next on the ballot (the pipeline's
   *  nextElection, from the term), not "Nothing to show" (RACES-06). */
  /* A place in its own words (rule 75), never its code: "Nothing to show
   * for AS in this view" stood over American Samoa's empty Senate panel.
   * D.C. and the territories have no seat in the Senate, and say so. */
  function noSenators(code) {
    var info = (KYC.meta().states || {})[code] || {};
    return info.territory || code === "DC";
  }

  function nothingHere(code) {
    var place = KYC.placeWords(code);
    if (noSenators(code) && /^senate/.test(mode)) {
      return KYC.escapeHtml(place.charAt(0).toUpperCase() + place.slice(1)) +
        " has no seat in the U.S. Senate.";
    }
    return "Nothing to show for " + KYC.escapeHtml(place) + " in this view.";
  }

  function noSenateRace(code) {
    if (noSenators(code)) return nothingHere(code);
    var name = KYC.escapeHtml(KYC.placeWords(code));
    var senators = data.filter(function (p) {
      return p.state === code && KYC.seated(p) && /Senate/.test(p.chamber) && p.nextElection;
    }).sort(function (a, b) { return a.nextElection - b.nextElection; });
    if (!senators.length) return "No U.S. Senate election in " + name + " in 2026.";
    return "No U.S. Senate election in " + name + " in 2026. Its senators' seats are next on the " +
      "ballot in " + senators.map(function (p) {
        return p.nextElection + " (" + KYC.escapeHtml(p.name) + ")";
      }).join(" and ") + ".";
  }

  /* Each race's money (rule 90, VISUALS-20): the race block's own fold
   * (KYC.cards.moneyBlock, rule 12), closed, and drawn when opened from the
   * state's own file, which it says while it loads and if it fails (rule
   * 94): the map holds everyone's card only, where every figure would read
   * "No data". One race is "Money in the race", as on the state page; a
   * state's House races each name their district, behind one count, so
   * Texas's 38 do not bury its delegation. */
  function moneyFolds(stateRaces) {
    if (!KYC.cards || !KYC.cards.moneyBlock) return "";
    var many = stateRaces.length > 1;
    var name = function (r) {
      if (r.chamber === "Senate") return r.special ? "the special election" : "the regular election";
      return r.district ? r.state + "-" + r.district : "the at-large race";
    };
    var blocks = stateRaces.slice().sort(function (a, b) {
      return (a.special ? 1 : 0) - (b.special ? 1 : 0) ||
        (Number(a.district) || 0) - (Number(b.district) || 0);
    }).map(function (r) {
      var everyone = (r.incumbentIds || []).concat(r.candidateIds || []).map(KYC.byId).filter(Boolean);
      return KYC.cards.moneyBlock(r, everyone, { lazy: true, scope: "map",
        summary: many ? "Money in " + name(r) : "Money in the race" });
    }).filter(Boolean);
    if (!blocks.length) return "";
    // The panel is a polite live region; a fold that fills when opened would
    // have a screen reader read a whole race's figures aloud. The folds are
    // kept out of it (aria-live="off"): the reader who opened one reads it,
    // and its loading and failure lines (role="status") still speak.
    if (blocks.length < 2) return '<div class="panel-money" aria-live="off">' + blocks[0] + "</div>";
    return '<button type="button" class="panel-subhead expander" id="showMoney"' +
      ' aria-expanded="false" aria-controls="moneyRows">' +
      KYC.icon("chevron") + " Money in each race <span>" + blocks.length + "</span></button>" +
      '<div id="moneyRows" class="panel-money" aria-live="off" hidden>' + blocks.join("") + "</div>";
  }

  /** The 2026 races view's line to the state's race for governor, on its
   *  state page (KYC.stategov.racePointer): the panel shows the state's
   *  2026 races, and the governor's is one of them. A governor is never a
   *  profile and in none of this panel's counts (rule 27). */
  function governorPointer(code) {
    return KYC.stategov && KYC.stategov.racePointer && KYC.stategov.loaded()
      ? KYC.stategov.racePointer(code, false) : "";
  }

  function showPanel(code) {
    var list = doc.getElementById("delegation");
    var counts = tally(code);
    var people = forMode(code).slice();

    doc.getElementById("panelState").textContent = map.name(code);
    doc.getElementById("panelMode").textContent = elected()
      ? (mode === "house" ? "House" : "Senate") + ", the " + KYC.ordinal(elected().congress) +
        " Congress as called so far" : MODE_TITLE[mode];
    var pageLink = doc.getElementById("panelStateLink");
    if (pageLink) {
      pageLink.hidden = false;
      pageLink.href = KYC.stateUrl(code);
      pageLink.textContent = "Open the " + KYC.stateName(code) + " page \u203a";
    }

    if (stateMode()) {
      doc.getElementById("panelCounts").innerHTML = KYC.stategov.badge(code, mode);
      // The race for governor's cards in the governor's own views; in
      // another office's, a line to them on the state page, so the office
      // the reader chose is not pushed a screen down (PR #191 review).
      var governorViews = mode === "governor" || mode === "governor2026";
      // The 2026 governor's races view: the race's panel in the Senate
      // panel's shape (KYC.stategov.racePanel) - the candidates on the
      // election office's list counted and as cards, the markets, then the
      // sitting governor's card - never the whole state-government block.
      list.innerHTML = '<div class="stategov">' + (mode === "governor2026"
        ? KYC.stategov.racePanel(code)
        : KYC.stategov.render(code, { links: true, raceLink: !governorViews })) + "</div>";
      list.scrollTop = 0;
      return;
    }

    if (elected()) {
      electedPanel(code, list);
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
          ? noSenateRace(code) : nothingHere(code)) +
        "</p></div>" + (mode === "senate2026" ? governorPointer(code) : "");
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
    var outNote = out.length
      ? ' <span class="faint" title="Lost the primary, withdrew, or were not on the primary ballot">' +
        out.length + " out</span>"
      : "";
    var stateRaces = KYC.races().filter(function (r) {
      return r.state === code && (mode === "house" ? r.chamber === "House" : r.chamber === "Senate");
    });
    /* The pages the statuses in the panel were read from, linked, as a
     * race's head links its own (TRUST-06): one link per page, since a
     * state's House races share one results page. */
    var seenSource = {};
    var sources = stateRaces.map(function (r) {
      var url = r.results && r.results.sourceUrl;
      if (!url || seenSource[url]) return "";
      seenSource[url] = true;
      return KYC.resultsSourceHtml(r);
    }).filter(Boolean);
    var sourceLine = sources.length ? '<p class="panel-note race-results">' + sources.join(" ") + "</p>" : "";
    var unsureBlock = unsure.length
      ? '<button type="button" class="panel-subhead expander" id="showUnsure"' +
        ' aria-expanded="false" aria-controls="unsureRows">' +
        KYC.icon("chevron") + " Filed; ballot status not known <span>" + unsure.length +
        "</span></button>" +
        '<div id="unsureRows" hidden>' + unsure.map(personRow).join("") + "</div>"
      : "";

    /* Texas has 37 representatives and 191 filed challengers. Listing all 228
     * in one scroll buries the delegation the reader clicked the state to
     * see, so the challengers sit behind a count they can open. */
    var html = "";
    /* The 2026 race view leads with the race: everyone in it, listed in the
     * race's own order, the seat's holder too while the race has them, then
     * what the markets quote, then whoever holds the seat and is not in
     * the race. Texas led with John Cornyn, "Lost primary", and folded its
     * two nominees away under "2026 challengers" (VISUALS-10); the first
     * race-first list then took only filers, and left every renominated
     * senator out of "Still in the race" and its count. The delegation
     * views keep who is seated first (rule 27). */
    var raceFirst = mode === "senate2026";
    var listed = {};
    if (raceFirst) {
      var raceOf = {};
      stateRaces.forEach(function (r) { raceOf[r.id] = r; });
      var holdsThisRace = function (x) {
        return stateRaces.some(function (r) {
          return (r.incumbentIds || []).indexOf(x.id) !== -1 || r.winnerId === x.id;
        });
      };
      var inRace = function (x) {
        if (KYC.offBallot(x.raceStatus) || unknown(x)) return false;
        if (x.isCandidate) return true;
        // A holder running for another seat is in that race, not this one.
        if (!holdsThisRace(x) || (x.contestRaceId && !raceOf[x.contestRaceId])) return false;
        return !!(x.raceStatus || x.seekingReelection2026);
      };
      var racePeople = people.filter(inRace).sort(order);
      racePeople.forEach(function (x) { listed[x.id] = true; });
      // One formula with the race's own count (rule 73): the people the
      // results put on the ballot with no profile here are in it too.
      var unprofiled = 0;
      stateRaces.forEach(function (r) {
        var u = KYC.cards.unprofiledNames(r);
        unprofiled += u.none.length + u.maybe.length;
      });
      var inCount = racePeople.length + unprofiled;
      // After Election Day the list holds who won and who lost (rule 63):
      // never "still in the race".
      var heading = KYC.electionStatus().phase === "post-election"
        ? "On the November ballot" : "Still in the race";
      if (inCount) {
        html += '<p class="panel-subhead race-people">' + heading + " <span>" + inCount + "</span>" +
          outNote + "</p>" + racePeople.map(personRow).join("") +
          (stateRaces.length === 1 ? KYC.cards.orderNote(racePeople, stateRaces[0]) : "");
      } else if (out.length) {
        html += '<p class="panel-subhead race-people">' +
          (KYC.electionStatus().phase === "post-election"
            ? "Nobody listed on the November ballot" : "Nobody listed as still in the race") +
          outNote + "</p>";
      }
      html += stateRaces.map(function (r) { return KYC.cards.unprofiledNote(r, "panel-note"); }).join("");
      // Before the markets and the holder, beside the statuses they back.
      html += unsureBlock + sourceLine;
      // The campaigns' money, then the markets, as a race block has them.
      html += moneyFolds(stateRaces);
      if (KYC.odds) {
        html += stateRaces.map(function (r) {
          return KYC.odds.render(r, { compact: true, collapsed: true });
        }).join("");
      }
      html += governorPointer(code);
    }
    var seatedRest = seated.filter(function (x) { return !listed[x.id]; });
    if (seatedRest.length) {
      html += '<p class="panel-subhead">' +
        (mode === "senate2026" ? "Seat held by" : "Currently seated") +
        " <span>" + seatedRest.length + "</span></p>" +
        seatedRest.map(personRow).join("");
    }
    if (former.length) {
      html += '<p class="panel-subhead">' +
        (mode === "senate2026" ? "Held the seat until " + KYC.dateWords(former[0].formerMember.left)
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
    if (raceFirst) {
      // The race's people, its unsettled filers and its source are above.
    } else {
      if (running.length) {
        html +=
          '<button type="button" class="panel-subhead expander" id="showChallengers"' +
          ' aria-expanded="false" aria-controls="challengerRows">' +
          KYC.icon("chevron") + " 2026 challengers <span>" + running.length + "</span>" + outNote +
          "</button>" +
          '<div id="challengerRows" hidden>' + running.map(personRow).join("") + "</div>";
      } else if (out.length) {
        html += '<p class="panel-subhead">' + (KYC.electionStatus().phase === "post-election"
          ? "No challenger was on the ballot " : "No challenger still on the ballot ") +
          '<span title="Lost the primary, withdrew, or were not on the primary ballot">' +
          out.length + " out</span></p>";
      }
      html += unsureBlock;
      /* The people the results put on the ballot with no profile here,
       * counted for the state's House seats, with the state page that lists
       * them race by race (the 2026 Senate view names them, above). Only the
       * view's own chamber: the Senate view counted Hawaii's House nominees
       * under a Senate heading (audit 2026-10-17, RACES-06).
       *
       * Whose word each name is, counted apart (rules 64 and 77): once the
       * count has begun, some of Louisiana's districts read from the results
       * pages while others are still the Secretary of State's list, and a
       * state's certified list sets some races and not others. One sentence
       * crediting one source would credit the others' names to it. */
      var bySource = {};
      var sourceOrder = [];
      stateRaces.forEach(function (r) {
        var n = KYC.cards.unprofiledNames(r).none.length;
        if (!n) return;
        var source = KYC.ballotSource(r);
        if (!(source in bySource)) { bySource[source] = 0; sourceOrder.push(source); }
        bySource[source] += n;
      });
      var counted = function (n) { return n + (n === 1 ? " person" : " people"); };
      var parts = sourceOrder.map(function (source) { return counted(bySource[source]) + " " + source; });
      if (parts.length) {
        html += '<p class="panel-note">Also on the November ballot, with no profile here: ' +
          KYC.escapeHtml(parts.join(", and ")) +
          '. <a href="' + KYC.escapeAttr(KYC.stateUrl(code)) + '">Each race on the ' +
          KYC.escapeHtml(KYC.stateName(code)) + " page \u203a</a></p>";
      }
      html += sourceLine;
      // The 2026 races' money, below the statuses and their source: the
      // House view's races (the Senate delegation view has none).
      if (mode === "house") html += moneyFolds(stateRaces);
    }
    list.innerHTML = html;
    list.scrollTop = 0;

    [["showChallengers", "challengerRows"], ["showUnsure", "unsureRows"],
     ["showMoney", "moneyRows"]].forEach(function (pair) {
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

  /** A state's panel in the elected view (rule 104): its members-elect,
   *  its senators whose seats were not on the 2026 ballot, then its races
   *  not yet called with their people in their status words
   *  (KYC.standing, through personRow) - and, first, when the members-elect
   *  take office and that until then the Now view shows who represents the
   *  state (rule 27; electedLead). */
  function electedPanel(code, list) {
    var m = elected();
    var part = electedPart(code);
    var esc = KYC.escapeHtml;
    var words = KYC.incomingWords;
    var pill = function (n, cls, label) {
      return n ? '<span class="' + cls + '">' + n + " " + label + "</span>" : "";
    };
    if (!part) {
      doc.getElementById("panelCounts").innerHTML = '<span class="faint">No seats</span>';
      list.innerHTML = '<div class="empty-state">' + KYC.icon("info") + "<p>" + nothingHere(code) + "</p></div>";
      return;
    }
    var n = words.totals(part);
    doc.getElementById("panelCounts").innerHTML = [pill(n.R, "party-r", "R"), pill(n.D, "party-d", "D"),
      pill(n.I, "party-i", "I"), pill(n.vacant, "party-vacant", "vacant"),
      pill(n.pending, "faint", "not yet called")].filter(Boolean).join(" ");
    var seats = mode === "house"
      ? Object.keys(part.seats).sort(function (a, b) { return a - b; }).map(function (k) { return part.seats[k]; })
      : part.seats;
    var nowButton = function (words) {
      return '<button type="button" class="link-button" data-basis="now">' + words + "</button>";
    };
    // A part with no seat on the 2026 ballot has no members-elect: its
    // holders keep counting, and they do represent it now - Puerto Rico's
    // Resident Commissioner read "They are not who represents Puerto Rico
    // now" over his own row (PR review), as did every senator of a state
    // with no 2026 race.
    var won = seats.filter(function (seat) { return seat.party; });
    var open = seats.filter(function (seat) { return !seat.party; });
    var html = !seats.length
      ? '<p class="panel-note incoming-note">' + esc(notOnBallot(code)) + " " + nowButton("The Now view") +
        " shows the same people.</p>"
      : '<p class="panel-note incoming-note">' + electedLead(code, m, won.length, open.length, nowButton) + "</p>";
    if (won.length) {
      html += '<p class="panel-subhead">Elected in 2026 <span>' + won.length + "</span></p>" +
        won.map(function (seat) {
          var p = seat.id ? KYC.byId(seat.id) : null;
          return p ? personRow(p) : '<p class="panel-note">' + esc(seat.name) +
            (seat.partyName ? " (" + esc(seat.partyName) + ")" : "") +
            ", elected in 2026, as the results page names them; no profile here.</p>";
        }).join("");
    }
    var held = (part.held || []).map(function (h) { return KYC.byId(h.id); }).filter(Boolean);
    if (mode === "senate" && (held.length || n.vacant)) {
      html += '<p class="panel-subhead">Seats not on the 2026 ballot <span>' + (held.length + n.vacant) +
        '</span></p><p class="panel-note">Counted by who holds each now.</p>' + held.map(personRow).join("") +
        (n.vacant ? '<p class="panel-note">' + n.vacant + (n.vacant === 1 ? " seat" : " seats") +
          " vacant now.</p>" : "");
    } else if (held.length) {
      // Puerto Rico's Resident Commissioner, elected to a four-year term.
      html += '<p class="panel-subhead">Not on the 2026 ballot <span>' + held.length + "</span></p>" +
        held.map(personRow).join("");
    }
    if (open.length) {
      html += '<p class="panel-subhead">' + esc(words.notCalled(m).replace(/^./, function (c) {
        return c.toUpperCase(); })) + " <span>" + open.length + "</span></p>" +
        '<div class="incoming-open">' + open.map(function (seat) {
          var race = KYC.races().filter(function (r) { return r.id === seat.race; })[0];
          if (!race) return "";
          // The race's people split as every race view splits them (rules
          // 12 and 73: KYC.cards.racePeople, as Your ballot does): a holder
          // running for another seat is not in this race, however their
          // status reads - Mike Collins, who ran for the Senate, was listed
          // under GA-10's uncalled race (PR review) - and only those the
          // lookup's answer would list are (KYC.stillRunning).
          var all = race.incumbentIds.concat(race.candidateIds).filter(function (id, i, ids) {
            return ids.indexOf(id) === i;
          }).map(KYC.byId).filter(Boolean);
          var people = KYC.cards.racePeople(race, all).running.filter(function (p) {
            return KYC.stillRunning(race, p);
          }).sort(function (a, b) { return KYC.racePosition(a) - KYC.racePosition(b); });
          var round = seat.status === "runoff" ? KYC.runoffWords(race) : null;
          return '<p class="panel-seat">' + esc(race.label || race.id) +
            (round ? ' <span class="badge ' + round.cls + '">' + esc(round.race) + "</span>" : "") + "</p>" +
            people.map(personRow).join("") + KYC.cards.unprofiledNote(race, "panel-note");
        }).join("") + "</div>";
    }
    list.innerHTML = html;
    list.scrollTop = 0;
  }

  /** The address of what is on screen: the state, the view, the House's
   *  layout when it is the squares, and the elected Congress's basis. */
  function routeNow() {
    return { state: selected, mode: mode === "senate" ? "" : mode,
             layout: mode === "house" && layout === "tiles" ? "tiles" : "",
             congress: elected() ? "elected" : "" };
  }

  /* ------------------------------------------- bars and squares (charts) */

  /* Above the map in the views of Congress, the chamber's seats as one bar
   * with the seats on the 2026 ballot dotted (VISUALS-21); in the House
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
    var m = KYC.incoming ? KYC.incoming() : null;
    var shown = elected();
    // Now or the Congress elected so far, in the Senate's and the House's
    // views, from the day after Election Day until it sits (rule 104).
    var basisChoice = m && (mode === "senate" || mode === "house")
      ? '<div class="map-layout map-basis"><span id="mapBasisLabel">Show the ' +
        (mode === "house" ? "House" : "Senate") + "</span>" +
        '<div class="segmented" role="group" aria-labelledby="mapBasisLabel">' +
        '<button type="button" data-basis="now" aria-pressed="' + String(!shown) + '">Now</button>' +
        '<button type="button" data-basis="elected" aria-pressed="' + String(!!shown) + '">The ' +
        KYC.escapeHtml(KYC.ordinal(m.congress)) + " Congress, as called</button></div></div>" : "";
    box.hidden = !chamber;
    box.innerHTML = !chamber ? "" : basisChoice +
      (mode === "house" && (KYC.meta() || {}).houseTiles
        ? '<div class="map-layout"><span id="mapLayoutLabel">Draw the House as</span>' +
          '<div class="segmented" role="group" aria-labelledby="mapLayoutLabel">' +
          '<button type="button" data-layout="map" aria-pressed="' + String(!squares) + '">A map</button>' +
          '<button type="button" data-layout="tiles" aria-pressed="' + String(squares) +
          '">One square per seat</button></div></div>' : "") +
      // The one-line form at every width: the sidebar carries the full key,
      // and the full bar here took the map 110-150px on a laptop (PR #111
      // review), pushing Vermont and Connecticut into callouts. Its counts
      // are printed below the laptop layout, where the sidebar is not
      // beside the map and a phone has no hover for the track's title.
      // The switch beside it names the Congress; the title says what the
      // bar counts in few words, or on a laptop it took the row and left
      // the bar a stub.
      (shown
        ? KYC.balanceBar(chamber, { basis: "elected", compact: true, counts: true,
          title: (chamber === "senate" ? "Senate" : "House") + ", as called so far" })
        : KYC.balanceBar(chamber, { title: chamber === "senate" ? "The Senate now" : "The House now",
          compact: true, counts: true }));
    stage.hidden = squares;
    tiles.hidden = !squares;
    if (squares) {
      tiles.innerHTML = KYC.houseTiles({ selected: selected, basis: shown ? "elected" : "" }) +
        (shown
          ? '<p class="bb-note">Each square is a voting seat on the 2026 district map, coloured by the ' +
            "party of the winner the results this site last read mark, or a grid where the race is " +
            KYC.escapeHtml(KYC.incomingWords.notCalled(shown)) + ", in bands from its state’s north to its " +
            "south. The members-elect " + KYC.escapeHtml(KYC.incomingWords.takeOffice(shown)) +
            ". Pick a state for its members-elect.</p>"
          : '<p class="bb-note">Each square is a voting seat, coloured by who sits for it, in bands ' +
            "from its state’s north to its south. Pick a state for its delegation.</p>");
      // The key says what the squares are, in place of the map's ramp.
      doc.getElementById("mapLegend").innerHTML = KYC.houseTilesKey({ basis: shown ? "elected" : "" });
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

  /** Now, or the Congress elected so far (rule 104): its own address. */
  function setBasis(next, opts) {
    basis = next === "elected" ? "elected" : "now";
    syncSources();
    drawLegend();
    drawCharts();
    map.paint();
    if (selected) showPanel(selected);
    if (!(opts && opts.fromRoute)) KYC.router.writeFilters(routeNow());
  }

  /* The footer names this view's sources: the national view of Congress
   * named none (TECH-11), and the elected view counts from the results,
   * which it says. The state panels date their own. */
  function syncSources() {
    var key = elected() ? "elected" : mode;
    Array.prototype.forEach.call(doc.querySelectorAll("[data-sources]"), function (line) {
      line.hidden = (" " + line.getAttribute("data-sources") + " ").indexOf(" " + key + " ") === -1;
    });
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
    // A phone's one menu of views (TECH-14, VISUALS-12).
    var picker = doc.getElementById("mapModeSelect");
    if (picker) picker.value = mode;
    syncSources();
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
    // D.C. is both a shape and a tile in the territory strip; it was listed
    // twice, and every option was a bare code (VISUALS-V2). Named and in
    // name order, as every other picker on the site.
    var seen = {};
    map.codes().filter(function (code) {
      if (seen[code]) return false;
      seen[code] = true;
      return true;
    }).map(function (code) {
      return { code: code, name: KYC.stateName(code) || map.name(code) };
    }).sort(function (a, b) {
      return a.name.replace(/^the /i, "").localeCompare(b.name.replace(/^the /i, ""));
    }).forEach(function (place) {
      var option = doc.createElement("option");
      option.value = place.code;
      option.textContent = place.name + " (" + place.code + ")";
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
    basis = initial.params.congress === "elected" ? "elected" : "now";
    setMode(MODE_TITLE[initial.params.mode] ? initial.params.mode : "senate",
            { fromRoute: true });

    doc.querySelector(".map-views").addEventListener("click", function (event) {
      var button = event.target.closest("[data-mode]");
      if (button) setMode(button.getAttribute("data-mode"));
    });
    var modePicker = doc.getElementById("mapModeSelect");
    if (modePicker) {
      modePicker.addEventListener("change", function () { setMode(modePicker.value); });
    }
    doc.getElementById("mapBalance").addEventListener("click", function (event) {
      var button = event.target.closest("[data-layout]");
      if (button) setLayout(button.getAttribute("data-layout"));
      var choice = event.target.closest("[data-basis]");
      if (choice) setBasis(choice.getAttribute("data-basis"));
    });
    doc.getElementById("mapTiles").addEventListener("click", function (event) {
      var state = event.target.closest(".ht-state");
      if (state) select(state.getAttribute("data-state"));
    });

    doc.getElementById("delegation").addEventListener("click", function (event) {
      var choice = event.target.closest("[data-basis]");
      if (choice) {
        setBasis(choice.getAttribute("data-basis"));
        return;
      }
      var row = event.target.closest("[data-id]");
      if (row) KYC.profile.open(row.getAttribute("data-id"));
    });

    KYC.router.onChange(function () {
      var route = KYC.router.read();
      if (route.view === "profile") {
        KYC.profile.open(route.id, { fromRoute: true });
        return;
      }
      // A governor's overlay (kyc-governor.js) over the map as it stands:
      // read as a list route, it reset the mode and rewrote the address.
      // A profile opened from its "Also on this site" line closes on Back to
      // it, leaving the history as it is (rule 105).
      if (route.view === "official") {
        if (KYC.profile.isOpen()) KYC.profile.close({ routed: true });
        return;
      }
      if (KYC.profile.isOpen()) KYC.profile.close();
      var wanted = route.params.mode || "senate";
      var shape = route.params.layout === "tiles" ? "tiles" : "map";
      var asked = route.params.congress === "elected" ? "elected" : "now";
      if (shape !== layout) {
        layout = shape;
        if (wanted === mode && asked === basis) { drawLegend(); drawCharts(); }
      }
      if (asked !== basis) {
        basis = asked;
        if (wanted === mode) setBasis(asked, { fromRoute: true });
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
    // An address asking for the elected Congress where there is none to
    // show (before Election Day, or once it sits) says what is shown.
    if (initial.view !== "profile" && initial.params.congress && !elected()) {
      KYC.router.writeFilters(routeNow());
    }
  });
})(window);
