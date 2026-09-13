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
   * behind a toggle. */
  var OFF_BALLOT = { eliminated: true, withdrawn: true, unlisted: true };

  function offBallot(item) {
    return !!OFF_BALLOT[item.raceStatus];
  }

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
    // "Renominated" is about the seat a member holds; a member on another
    // seat's ballot is simply on it.
    var own = !item.isCandidate && !item.contestLabel;
    var spec = (own && MEMBER_RACE_BADGE[item.raceStatus]) || RACE_BADGE[item.raceStatus];
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
      ) + '">Running for ' + KYC.escapeHtml(item.contestLabel.replace(/ • /, " ")) +
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
   * item.party and the office label straight into innerHTML and carried an
   * onclick with the id interpolated into it; one delegated listener reads
   * data-id instead. */
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

  /** The badges that summarise a race: open seat, primary date, how many
   *  are on the ballot, how many filed. */
  function raceBadges(race) {
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
    return [
      '<section class="race" id="', KYC.escapeAttr("race-" + race.id), '">',
      '<div class="race-head"><h3 class="race-title">',
      KYC.escapeHtml(title), link, "</h3>", raceBadges(race), "</div>",
      body,
      "</section>",
    ].join("");
  }

  KYC.cards = {
    OFF_BALLOT: OFF_BALLOT,
    offBallot: offBallot,
    raceBadge: raceBadge,
    statusBadge: statusBadge,
    card: card,
    raceBadges: raceBadges,
    raceSection: raceSection,
  };
})(window);
