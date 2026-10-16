/* Know Your Candidate - profile cards and race sections.
 *
 * Shared by the grid (index.html) and every state page. The card and the
 * race header used to live inside the directory module; the state pages
 * need the same markup, and a second copy is how the map came to render a
 * placeholder sentence months after the grid had stopped (rule 12). One
 * implementation, loaded after the data and before the page module.
 */
(function (global) {
  "use strict";

  var KYC = global.KYC;

  /* Primary results settle who is still running. Someone the results say
   * lost, withdrew, or was never on the primary ballot is not "in the race",
   * and showing them as though they were is the opposite mistake from the
   * one the FEC field fixed. They stay in the data - nothing is deleted -
   * behind a toggle. The statuses and their words are KYC.raceStatus's. */
  function offBallot(item) {
    return KYC.offBallot(item.raceStatus);
  }

  function raceBadge(item) {
    // "Renominated" is about the seat a member holds; a member on another
    // seat's ballot is simply on it.
    var spec = KYC.raceStatusOf(item, "card");
    if (!spec) return "";
    // A nominee on another line than their party's says so, or a primary
    // loser on a minor-party line reads as a second Democratic nominee.
    var line = KYC.ballotLine(item);
    // Not "won the primary": Jose Vega (NY-15) lost it and is on the ballot.
    // Before the count a nominee's own hover ("won the primary") is wrong for
    // a line like that; after it, "awaiting result" still needs its date.
    var campaign = KYC.contestStatus(item) === "nominee" &&
      KYC.electionStatus().phase !== "post-election";
    var title = line ? "On the general election ballot on the " + line +
      " line, per the published results." + (campaign ? "" : " " + spec.title) : spec.title;
    return '<span class="badge ' + spec.cls + '" title="' + KYC.escapeAttr(title) +
      '">' + KYC.escapeHtml(spec.label) + KYC.ballotLineSuffix(item) + "</span>";
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
      ) + '">Running for ' + KYC.escapeHtml(item.contestLabel.replace(/ • /, " ")) +
        "</span>" + (raceBadge(item) ? " " + raceBadge(item) : "");
    }
    /* A sitting member the primary eliminated is leaving too, and a reader
     * should see that before "seat up". */
    if (!item.isCandidate && KYC.offBallot(item.raceStatus)) {
      return raceBadge(item);
    }
    if (/retiring|not running|defeated|ineligible|resigned/.test(status)) {
      return '<span class="badge badge-danger">Leaving in ’26</span>';
    }
    if (item.isCandidate) {
      return raceBadge(item) ||
        '<span class="badge badge-money" title="Filed with the FEC; the primary has not been held yet.">2026 challenger</span>';
    }
    /* Won (or is in the runoff for) the primary for the seat they hold:
     * "Renominated" says more than "seat up", and "Re-elected" or "Lost
     * re-election" more again. Before any result, the seat badge below
     * still shows. */
    if (!item.isCandidate && (KYC.onNovemberBallot(item.raceStatus) ||
        item.raceStatus === "advanced")) {
      var renominated = raceBadge(item);
      if (renominated) return renominated;
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
   * item.party and the office label straight into innerHTML and carried an
   * onclick with the id interpolated into it; one delegated listener reads
   * data-id instead. */
  function card(item) {
    return [
      '<button type="button" class="card" data-id="', KYC.escapeAttr(item.id), '">',
      '<span class="card-photo">',
      // Cards measured 146-171px wide from a phone to a 2,000px screen.
      '<img ', KYC.portraitAttrs(item, "165px"),
      ' alt="" loading="lazy" decoding="async" data-photo-idx="0" data-profile="',
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

  /** Who is in *race* with *status*, by name: the people with a profile
   *  whose contest it is, and the names the results page gives with no
   *  profile here (res.otherElected, res.otherRunoff). */
  function namesWith(race, status, unprofiled) {
    var seen = {};
    var names = race.incumbentIds.concat(race.candidateIds).map(KYC.byId)
      .filter(function (p) {
        if (!p || seen[p.id]) return false;
        seen[p.id] = true;
        var contest = p.isCandidate ? p.raceId : (p.contestRaceId || p.raceId);
        return contest === race.id && KYC.contestStatus(p) === status;
      })
      .map(function (p) { return p.name; });
    (unprofiled || []).forEach(function (name) {
      if (names.indexOf(name) === -1) names.push(name);
    });
    return names;
  }

  /** After Election Day: who won the race, who is in its runoff, or that
   *  the results this site last read had not said - never a guess. */
  function outcomeBadge(race) {
    if (KYC.electionStatus().phase !== "post-election" || !race.settled) return "";
    var res = race.results || {};
    var won = namesWith(race, "elected", res.otherElected);
    if (won.length === 1) {
      return '<span class="badge badge-money" title="' + KYC.escapeAttr(
        "Marked as the winner on the state's Wikipedia election results page.") +
        '">Won by ' + KYC.escapeHtml(won[0]) + "</span>";
    }
    var runoff = namesWith(race, "runoff", res.otherRunoff);
    if (runoff.length) {
      return '<span class="badge badge-warn" title="' + KYC.escapeAttr(
        "No candidate won a majority in November. In the runoff, per the published " +
        "results: " + runoff.join(", ") + ".") + '">Going to a runoff</span>';
    }
    var asOf = (KYC.meta().election || {}).resultsAsOf;
    return '<span class="badge badge-neutral" title="' + KYC.escapeAttr(
      "The results this site last read" + (asOf ? ", on " + asOf + "," : "") +
      " had not marked a winner.") + '">Awaiting result</span>';
  }

  /** The badges that summarise a race: its November result, open seat,
   *  primary date, how many are on the ballot, how many filed. */
  function raceBadges(race) {
    var badges = [];
    var outcome = outcomeBadge(race);
    if (outcome) badges.push(outcome);
    if (race.openSeat) {
      var holder = race.incumbentIds.map(KYC.byId).filter(Boolean)[0];
      var why = !holder ? "A newly drawn seat with no sitting member." :
        holder.contestLabel ? holder.name + " is running for " + holder.contestLabel + "." :
        holder.alsoRunningSeat ? holder.name + " is running for " + holder.alsoRunningSeat + "." :
        KYC.offBallot(holder.raceStatus) ? holder.name + " is not on the November ballot." :
        holder.name + " is not seeking re-election.";
      badges.push('<span class="badge badge-warn" title="' + KYC.escapeAttr(why) +
        '">Open seat</span>');
    }
    if (race.primaryDate) {
      // A ballot read from a qualified list is not a held primary.
      var listed = !!(race.results && race.results.fromQualifiedList);
      var held = race.settled && !listed;
      badges.push(
        '<span class="badge badge-neutral" title="' +
        KYC.escapeAttr(held
          ? "Primary held " + race.primaryDate +
            (race.runoffDate ? "; runoff " + race.runoffDate : "") +
            ". Results from the state's Wikipedia election page."
          : "Primary scheduled for " + race.primaryDate + "." + (listed
            ? " Who is on its ballot: the Secretary of State's list of qualified candidates."
            : "")) + '">' +
        (held ? "Primary held " : "Primary ") + KYC.escapeHtml(race.primaryDate) +
        "</span>"
      );
    }

    /* "No declared challenger" was a claim about our roster dressed up as
     * a fact about the race, and it was wrong for 372 of them. filedCount
     * is how many people have actually filed with the FEC for the seat. */
    var res = race.results || null;
    // Nominees the results page names with no profile here: a filing under
    // $5,000, or none. They are on the ballot, so they count (rule 22).
    var unprofiled = res && res.otherNominees ? res.otherNominees.length : 0;
    if (race.contested) {
      var running = race.candidateCount + unprofiled;
      badges.push(
        '<span class="badge badge-money">' + running +
        " challenger" + (running === 1 ? "" : "s") +
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
    if (unprofiled) {
      badges.push(
        '<span class="badge badge-warn" title="' + KYC.escapeAttr(
          "On the November ballot per the published results, with no FEC filing " +
          "over $5,000 - the point at which federal law treats someone as a " +
          "candidate - so no profile here: " + res.otherNominees.join(", ")
        ) + '">' + unprofiled + " with no profile here</span>"
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
    return badges.join("");
  }

  /** One race: its header, the people still in it, and the people the
   *  primary removed folded underneath. *people* is the already-filtered
   *  list of profiles to show; *opts.title* overrides the heading. */
  function raceSection(race, people, opts) {
    opts = opts || {};
    var running = people.filter(function (p) { return !offBallot(p); });
    var out = people.filter(offBallot);
    var body = '<div class="card-grid">' + running.map(card).join("") + "</div>";
    if (out.length) {
      body +=
        '<details class="race-out"><summary>' + out.length +
        " no longer in this race &mdash; lost the primary, withdrew, or were " +
        "not on the primary ballot</summary>" +
        '<div class="card-grid">' + out.map(card).join("") + "</div></details>";
    }
    var title = opts.title || race.label;
    var link = opts.stateLink === false ? "" :
      ' <a class="race-state-link" href="' + KYC.escapeAttr(KYC.stateUrl(race.state)) +
      '" title="' + KYC.escapeAttr("Everything about " + KYC.stateName(race.state)) + '">' +
      KYC.escapeHtml(KYC.stateName(race.state)) + " &rsaquo;</a>";
    // The people first, then the markets: a reader came for who is running,
    // and 61% of House market blocks only show a 95-99% favourite.
    var odds = KYC.odds ? KYC.odds.render(race, { compact: !opts.fullOdds }) : "";
    return [
      '<section class="race" id="', KYC.escapeAttr("race-" + race.id), '">',
      '<div class="race-head"><h3 class="race-title">',
      KYC.escapeHtml(title), link, "</h3>", raceBadges(race), "</div>",
      body,
      odds,
      "</section>",
    ].join("");
  }

  KYC.cards = {
    offBallot: offBallot,
    raceBadge: raceBadge,
    statusBadge: statusBadge,
    card: card,
    raceBadges: raceBadges,
    raceSection: raceSection,
  };
})(window);
