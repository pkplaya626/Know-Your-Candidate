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
 * Once the Congress the cycle elects is sitting (KYC.recordPhase), the
 * cycle's races are a record, not the next election for any seat: every
 * senator is grouped by the year their seat is next decided, and the 2026
 * results stay on the race view and the state pages. Before then, after
 * Election Day, the cycle's group is "2026 elections", not "Up in 2026".
 *
 * Nothing is derived here (rule 1). senateClass, nextElection and
 * senateSpecial come from the pipeline, keyed on bioguide id. A 2026 seat
 * is its race - every Senate race of the cycle, whoever holds the seat now:
 * the race's incumbentIds names who held it (a senator who has since left
 * is a former member, "Held the seat until"), and its winner, once seated,
 * is listed in that seat and nowhere else, so the Senate stays 100 seats.
 * Candidates are the race's candidateIds plus any member whose
 * contestRaceId is that race; statuses come from KYC.contestStatus. Cards
 * are KYC.cards.card, so they look and open exactly like the grid's (one
 * implementation, rule 12).
 */
(function (global) {
  "use strict";

  var KYC = global.KYC;

  var ROMAN = { 1: "I", 2: "II", 3: "III" };

  /* Nominees (and, after November, the winner) first, then a runoff still
   * to be decided, then people whose primary has not been held, then who
   * lost in November; the people the primary removed come last and only on
   * request. The order is KYC.raceStatus's. */
  var RUNNING = 2;

  function rank(item) {
    var spec = KYC.raceStatusOf(item, "short");
    return spec ? spec.rank : RUNNING;
  }

  function isOut(item) {
    return KYC.offBallot(KYC.contestStatus(item));
  }

  /** A senator sitting now: never a former member (rule 27). */
  function isSenator(item) {
    return KYC.seated(item) && String(item.chamber).indexOf("Senate") !== -1;
  }

  function byState(a, b) {
    return KYC.stateName(a.state).localeCompare(KYC.stateName(b.state)) ||
      (a.holder ? a.holder.name : "").localeCompare(b.holder ? b.holder.name : "");
  }

  /** Everyone running for *race* other than its sitting senator, in ballot
   *  order. A member contesting the seat from elsewhere (contestRaceId) is
   *  shown once, as their member profile; their separate filing profile
   *  (alsoRunningId / incumbentId) is the same person and is dropped. */
  function contenders(race, people, holder) {
    var seen = {};
    var shown = [];
    var twins = {};
    var holderId = holder ? holder.id : null;
    function add(item) {
      if (!item || seen[item.id] || item.id === holderId) return;
      seen[item.id] = true;
      shown.push(item);
    }
    (holder ? [holder] : []).concat(people.filter(function (p) {
      return !p.isCandidate && p.contestRaceId === race.id && p.id !== holderId;
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
   *  running, state, senateClass}]}]``; a 2026 seat's holder is null when
   *  the record's incumbent has no profile (its race still names them). */
  function groups(people, races) {
    var buckets = {};
    var placed = {};
    function put(key, seat) {
      (buckets[key] = buckets[key] || []).push(seat);
    }
    // Every Senate race is a seat, grouped by the race: Ohio's special
    // election stays a 2026 special after its winner is seated for the term
    // to 2029, and Florida's still has a seat after its appointee has left.
    // Once the new Congress sits, no race is any seat's next election.
    races.forEach(function (race) {
      if (race.chamber !== "Senate" || KYC.recordPhase()) return;
      var holder = race.incumbentIds.map(KYC.byId).filter(Boolean)[0] || null;
      // Seated since Election Day for the term this race decided: the seat
      // is theirs now, shown as held, never as a challenger.
      var winner = KYC.byId(race.winnerId);
      winner = winner && KYC.seated(winner) ? winner : null;
      if (holder) placed[holder.id] = true;
      if (race.winnerId) placed[race.winnerId] = true;
      put(race.year + (race.special ? "s" : "r"), {
        holder: holder, winner: winner, race: race, state: race.state,
        senateClass: race.senateClass || (holder && holder.senateClass) || null,
        running: contenders(race, people, holder).filter(function (p) { return p !== winner; }),
      });
    });
    // Every other sitting senator, by the year their seat is next decided.
    people.filter(function (p) { return isSenator(p) && !placed[p.id]; }).forEach(function (holder) {
      var known = holder.senateClass && holder.nextElection;
      var key = known ? holder.nextElection + (holder.senateSpecial ? "s" : "r") : "unknown";
      put(key, { holder: holder, race: null, state: holder.state,
                 senateClass: holder.senateClass, running: [] });
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
      // After Election Day the cycle's seats are no longer "up".
      var past = year !== null && KYC.electionStatus(year).phase === "post-election";
      var title = year === null ? "Class or next election not known" :
        special ? year + " special elections – " + classText + " seats" :
        (past ? year + " elections – " : "Up in " + year + " – ") + classText;
      return {
        key: key,
        year: year,
        classes: classes,
        special: special,
        title: title,
        seats: seats,
      };
    });
  }

  function cards(items) {
    return '<div class="card-grid">' + items.map(KYC.cards.card).join("") + "</div>";
  }

  function count(n, word) {
    return n.toLocaleString() + " " + word + (n === 1 ? "" : "s");
  }

  /** One 2026 seat: who holds it (or held it, until they left), then
   *  everyone running for it. */
  function seatBlock(seat, level, opts) {
    var match = opts.matches;
    var holder = seat.holder && match(seat.holder) ? [seat.holder] : [];
    var winner = seat.winner && match(seat.winner) ? [seat.winner] : [];
    var running = seat.running.filter(function (p) { return !isOut(p) && match(p); });
    var out = opts.showOut
      ? seat.running.filter(function (p) { return isOut(p) && match(p); })
      : [];
    if (!holder.length && !winner.length && !running.length && !out.length) return null;

    var race = seat.race;
    var id = "senate-seat-" + (race ? race.id : seat.holder.id);
    var stateName = KYC.stateName(seat.state);
    var html = [
      '<section class="race senate-seat" aria-labelledby="', KYC.escapeAttr(id), '">',
      '<div class="race-head"><h', level, ' class="race-title" id="', KYC.escapeAttr(id), '">',
      KYC.escapeHtml(stateName), " – Class ", ROMAN[seat.senateClass] || "?",
      ' seat <a class="race-state-link" href="', KYC.escapeAttr(KYC.stateUrl(seat.state)),
      '" title="', KYC.escapeAttr("Everything about " + stateName), '">',
      KYC.escapeHtml(stateName), " &rsaquo;</a></h", level, ">",
      race ? KYC.cards.raceBadges(race) : "",
      "</div>",
    ];
    // One row per seat: the senator, then the people running for the seat,
    // side by side - stacked, each seat took a screen of mostly empty width.
    var row = [];
    if (winner.length) {
      row.push('<div class="senate-side senate-holder"><p class="senate-role">' +
               "Holds the seat (won it in " + seat.race.year + ")</p>" + cards(winner) + "</div>");
    }
    if (holder.length) {
      var role = KYC.seated(seat.holder) ? "Holds the seat"
        : seat.holder.formerMember ? "Held the seat until " + seat.holder.formerMember.left
        : "Held the seat";
      row.push('<div class="senate-side senate-holder"><p class="senate-role">' +
               KYC.escapeHtml(role) + "</p>" + cards(holder) + "</div>");
    } else if (!seat.holder && race && race.incumbent) {
      // The record names who held the seat even with no profile here
      // (validate reports that as an error).
      row.push('<div class="senate-side senate-holder"><p class="senate-role">Held the seat</p>' +
               "<p>" + KYC.escapeHtml(race.incumbent.name + " (" + race.incumbent.party + ")") +
               "</p></div>");
    }
    // The people the results name with no profile here, in words: in a
    // badge's hover only, Tennessee's seat listed two running over nine.
    var unlisted = race ? KYC.cards.unprofiledNote(race) : "";
    if (running.length || unlisted) {
      row.push('<div class="senate-side senate-running"><p class="senate-role">' +
               "Running for this seat (" + (running.length +
                 (race ? KYC.cards.unprofiledNames(race).none.length +
                   KYC.cards.unprofiledNames(race).maybe.length : 0)) + ")</p>" +
               cards(running) + unlisted + "</div>");
    }
    if (row.length) html.push('<div class="senate-seat-row">', row.join(""), "</div>");
    // The markets after the people still running, before those who left
    // the race: shown, a dozen faded cards had pushed them 1,400px down.
    if (race && KYC.odds) html.push(KYC.odds.render(race));
    if (out.length) {
      html.push('<div class="race-out senate-out"><p class="senate-role">No longer running ' +
                "for this seat (" + out.length + ") &mdash; lost the primary, withdrew, or " +
                "were not on the primary ballot</p>", cards(out), "</div>");
    }
    html.push("</section>");
    return { html: html.join(""),
             people: winner.length + holder.length + running.length + out.length };
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
      var shown = group.seats.map(function (s) { return s.holder; }).filter(function (p) {
        return p && opts.matches(p);
      });
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
    // Which party the markets expect to hold the chamber, after the seats.
    if (html.length && KYC.odds) html.push(KYC.odds.control("senate"));
    return { html: html.join(""), people: total, seats: seats };
  }

  KYC.senate = {
    groups: groups,
    contenders: contenders,
    render: render,
  };
})(window);
