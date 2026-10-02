/* Know Your Candidate - the Senate by the year each seat is next decided.
 *
 * The grid answers "who is in Congress" and the race view "who is running
 * for each seat"; neither answers the question the Senate's staggered terms
 * raise, which is "which seats are actually on this ballot, and who wants
 * them". This groups all 100 seats by the year they are next decided -
 * 2026 (Class II, then the Class III specials), 2028 (Class III), 2030
 * (Class I) - and puts everyone running for a 2026 seat beneath the
 * senator who holds it.
 *
 * Nothing is derived here (rule 1). senateClass, nextElection and
 * senateSpecial come from the pipeline, keyed on bioguide id; a seat's race
 * is the one whose incumbentIds names the senator; candidates are the
 * race's candidateIds plus any member whose contestRaceId is that race;
 * statuses come from KYC.contestStatus. Cards are KYC.cards.card, so they
 * look and open exactly like the grid's (one implementation, rule 12).
 */
(function (global) {
  "use strict";

  var KYC = global.KYC;

  var ROMAN = { 1: "I", 2: "II", 3: "III" };

  /* Nominees first, then a primary runoff still to be decided, then people
   * whose primary has not been held; the people the primary removed come
   * last and only on request. */
  var RANK = { nominee: 0, advanced: 1 };
  var RUNNING = 2;
  var OUT = 3;

  function rank(item) {
    var status = KYC.contestStatus(item);
    if (KYC.cards.OFF_BALLOT[status]) return OUT;
    return status in RANK ? RANK[status] : RUNNING;
  }

  function isSenator(item) {
    return !item.isCandidate && String(item.chamber).indexOf("Senate") !== -1;
  }

  function byState(a, b) {
    return KYC.stateName(a.state).localeCompare(KYC.stateName(b.state)) ||
      a.name.localeCompare(b.name);
  }

  /** The race a sitting senator's seat is in, matched on the id in
   *  incumbentIds - never on the state alone, which holds two seats. */
  function raceIndex(races) {
    var index = {};
    races.forEach(function (race) {
      if (race.chamber !== "Senate") return;
      race.incumbentIds.forEach(function (id) { index[id] = race; });
    });
    return index;
  }

  /** Everyone running for *race* other than its sitting senator, in ballot
   *  order. A member contesting the seat from elsewhere (contestRaceId) is
   *  shown once, as their member profile; their separate filing profile
   *  (alsoRunningId / incumbentId) is the same person and is dropped. */
  function contenders(race, people, holder) {
    var seen = {};
    var shown = [];
    var twins = {};
    function add(item) {
      if (!item || seen[item.id] || item.id === holder.id) return;
      seen[item.id] = true;
      shown.push(item);
    }
    [holder].concat(people.filter(function (p) {
      return !p.isCandidate && p.contestRaceId === race.id && p.id !== holder.id;
    })).forEach(function (member) {
      twins[member.id] = true;
      if (member.alsoRunningId) twins[member.alsoRunningId] = true;
      if (member !== holder) add(member);
    });
    race.candidateIds.forEach(function (id) {
      var item = KYC.byId(id);
      if (!item || twins[id] || (item.incumbentId && twins[item.incumbentId])) return;
      add(item);
    });
    return shown.sort(function (a, b) {
      return rank(a) - rank(b) ||
        String(a.party).localeCompare(String(b.party)) ||
        a.name.localeCompare(b.name);
    });
  }

  /** The groups in reading order: each year's regular class, then that
   *  year's specials, then any senator the data could not place (which
   *  validation reports as an error - shown rather than silently dropped).
   *
   *  Returns ``[{key, year, classes, special, title, seats: [{holder, race,
   *  running}]}]``. */
  function groups(people, races) {
    var raceOf = raceIndex(races);
    var buckets = {};
    people.filter(isSenator).forEach(function (holder) {
      var known = holder.senateClass && holder.nextElection;
      var key = known ? holder.nextElection + (holder.senateSpecial ? "s" : "r") : "unknown";
      (buckets[key] = buckets[key] || []).push(holder);
    });
    return Object.keys(buckets).sort().map(function (key) {
      var seats = buckets[key].sort(byState);
      var classes = [];
      seats.forEach(function (s) {
        if (s.senateClass && classes.indexOf(s.senateClass) === -1) classes.push(s.senateClass);
      });
      classes.sort();
      var year = key === "unknown" ? null : parseInt(key, 10);
      var special = key.slice(-1) === "s";
      var classText = classes.map(function (c) { return "Class " + ROMAN[c]; }).join(", ");
      var title = year === null ? "Class or next election not known" :
        special ? year + " special elections – " + classText + " seats" :
        "Up in " + year + " – " + classText;
      return {
        key: key,
        year: year,
        classes: classes,
        special: special,
        title: title,
        seats: seats.map(function (holder) {
          var race = raceOf[holder.id] || null;
          return { holder: holder, race: race,
                   running: race ? contenders(race, people, holder) : [] };
        }),
      };
    });
  }

  function cards(items) {
    return '<div class="card-grid">' + items.map(KYC.cards.card).join("") + "</div>";
  }

  function count(n, word) {
    return n.toLocaleString() + " " + word + (n === 1 ? "" : "s");
  }

  /** One 2026 seat: its sitting senator, then everyone running for it. */
  function seatBlock(seat, level, opts) {
    var match = opts.matches;
    var holder = match(seat.holder) ? [seat.holder] : [];
    var running = seat.running.filter(function (p) { return rank(p) !== OUT && match(p); });
    var out = opts.showOut
      ? seat.running.filter(function (p) { return rank(p) === OUT && match(p); })
      : [];
    if (!holder.length && !running.length && !out.length) return null;

    var race = seat.race;
    var id = "senate-seat-" + (race ? race.id : seat.holder.id);
    var stateName = KYC.stateName(seat.holder.state);
    var html = [
      '<section class="race senate-seat" aria-labelledby="', KYC.escapeAttr(id), '">',
      '<div class="race-head"><h', level, ' class="race-title" id="', KYC.escapeAttr(id), '">',
      KYC.escapeHtml(stateName), " – Class ", ROMAN[seat.holder.senateClass] || "?",
      ' seat <a class="race-state-link" href="', KYC.escapeAttr(KYC.stateUrl(seat.holder.state)),
      '" title="', KYC.escapeAttr("Everything about " + stateName), '">',
      KYC.escapeHtml(stateName), " &rsaquo;</a></h", level, ">",
      race ? KYC.cards.raceBadges(race) : "",
      "</div>",
    ];
    // One row per seat: the senator, then the people running for the seat,
    // side by side - stacked, each seat took a screen of mostly empty width.
    var row = [];
    if (holder.length) {
      row.push('<div class="senate-side senate-holder"><p class="senate-role">Holds the seat</p>' +
               cards(holder) + "</div>");
    }
    if (running.length) {
      row.push('<div class="senate-side senate-running"><p class="senate-role">' +
               "Running for this seat (" + running.length + ")</p>" + cards(running) + "</div>");
    }
    if (row.length) html.push('<div class="senate-seat-row">', row.join(""), "</div>");
    if (out.length) {
      html.push('<div class="race-out senate-out"><p class="senate-role">No longer running ' +
                "for this seat (" + out.length + ") &mdash; lost the primary, withdrew, or " +
                "were not on the primary ballot</p>", cards(out), "</div>");
    }
    html.push("</section>");
    return { html: html.join(""), people: holder.length + running.length + out.length };
  }

  /** A whole group. 2026 seats get a block each; later years are just the
   *  senators, by state - nobody is on those ballots yet. */
  function groupSection(group, opts, nested, inner) {
    var heading = nested ? 3 : 2;
    var id = "senate-" + group.key;
    var blocks = [];
    var people = 0;
    var withRaces = group.year === opts.electionYear;

    if (withRaces) {
      group.seats.forEach(function (seat) {
        var block = seatBlock(seat, heading + 1, opts);
        if (block) { blocks.push(block.html); people += block.people; }
      });
    } else {
      var shown = group.seats.map(function (s) { return s.holder; }).filter(opts.matches);
      if (shown.length) blocks.push(cards(shown));
      people = shown.length;
    }
    inner = inner || { html: "", people: 0, seats: 0 };
    if (!people && !inner.people) return null;

    var seatsShown = withRaces ? blocks.length : people;
    var filtered = seatsShown !== group.seats.length;
    return {
      people: people + inner.people,
      seats: seatsShown + inner.seats,
      html: [
        '<section class="senate-group', nested ? " senate-group-special" : "",
        '" aria-labelledby="', KYC.escapeAttr(id), '" data-group-key="',
        KYC.escapeAttr(group.key), '" data-seats="', group.seats.length, '">',
        "<h", heading, ' class="senate-group-title" id="', KYC.escapeAttr(id), '">',
        KYC.escapeHtml(group.title),
        ' <span class="senate-count">', count(group.seats.length, "seat"),
        filtered ? " &middot; " + seatsShown + " shown" : "", "</span>",
        "</h", heading, ">",
        blocks.join(""),
        inner.html,
        "</section>",
      ].join(""),
    };
  }

  /** The whole view. *opts.matches* is the page's filter predicate;
   *  *opts.showOut* is the "Include eliminated" control. Returns
   *  ``{html, people, seats}``. */
  function render(people, races, opts) {
    var meta = global.kycBuildMeta || {};
    opts = {
      matches: opts.matches || function () { return true; },
      showOut: !!opts.showOut,
      electionYear: (meta.election && meta.election.year) || null,
    };
    var all = groups(people, races);
    if (opts.electionYear === null) {
      // The build always says which year it is about; without that, the
      // earliest year in the data is the ballot in front of the reader.
      all.forEach(function (g) {
        if (g.year !== null && (opts.electionYear === null || g.year < opts.electionYear)) {
          opts.electionYear = g.year;
        }
      });
    }
    var html = [];
    var total = 0;
    var seats = 0;
    function emit(section) {
      if (!section) return;
      html.push(section.html);
      total += section.people;
      seats += section.seats;
    }
    /* A year's specials are a labelled sub-group inside that year's
     * section, after its regular seats; they stand alone only in a year
     * with no regular class on the ballot. */
    all.forEach(function (group) {
      var specials = all.filter(function (g) { return g.special && g.year === group.year; });
      if (group.special) {
        var parent = all.some(function (g) { return !g.special && g.year === group.year; });
        if (!parent) emit(groupSection(group, opts, false));
        return;
      }
      var inner = { html: "", people: 0, seats: 0 };
      specials.forEach(function (g) {
        var section = groupSection(g, opts, true);
        if (!section) return;
        inner.html += section.html;
        inner.people += section.people;
        inner.seats += section.seats;
      });
      emit(groupSection(group, opts, false, inner));
    });
    return { html: html.join(""), people: total, seats: seats };
  }

  KYC.senate = {
    groups: groups,
    contenders: contenders,
    render: render,
  };
})(window);
