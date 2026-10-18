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
    // seat's ballot is simply on it. A filer the results do not settle
    // reads as the dialog and the map read them (KYC.standing).
    var spec = KYC.standing(item, "card");
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

    /* A 2026 incumbent who has left Congress: that first, then how their
     * race went. Never "seat up", never a sitting member's badge. */
    if (item.formerMember) {
      var how = raceBadge(item);
      return '<span class="badge badge-neutral" title="' +
        KYC.escapeAttr(KYC.formerText(item) + "; held this seat in the 2026 race.") +
        '">Former member</span>' + (how ? " " + how : "");
    }

    /* A member contesting another seat - the other chamber, or a redrawn
     * district - is leaving this one, and the reader should see where they
     * went before anything else. */
    if (!item.isCandidate && item.contestLabel) {
      var line = KYC.contestLine(item);
      return '<span class="badge ' + line.cls + '" title="' + KYC.escapeAttr(line.title) + '">' +
        KYC.escapeHtml(line.label) + "</span>" + (raceBadge(item) ? " " + raceBadge(item) : "");
    }
    /* A sitting member the primary eliminated is leaving too, and a reader
     * should see that before "seat up" - and where they are going, when a
     * results page has made them another office's nominee. */
    if (!item.isCandidate && KYC.offBallot(item.raceStatus)) {
      return raceBadge(item) + KYC.otherOfficeBadge(item, " ");
    }
    if (/retiring|not running|defeated|ineligible|resigned/.test(status)) {
      return '<span class="badge badge-danger">Leaving in ’26</span>' +
        KYC.otherOfficeBadge(item, " ");
    }
    if (item.isCandidate) {
      /* The primary has been held and the published results do not name
       * them (an independent, a minor party's filer): not "the primary has
       * not been held yet", and not counted as on the ballot. raceBadge
       * says so, as KYC.standing words it for every view. */
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

  /* The latest public office beyond the seat the card is about: "Fmr.
   * Governor of Florida" on Rick Scott's, a state senator's own seat on a
   * challenger's, "U.S. Representative" on a representative's card for a
   * Senate race. A seat in the card's own chamber is the card's subject,
   * whichever district it was: a member whose district was renumbered is
   * not a former representative. The years are in the title and the
   * dialog. */
  function heldLine(item) {
    var senate = String(item.chamber || "").toLowerCase().indexOf("senate") !== -1;
    var row = ((item.politicalHistory || {}).rows || []).filter(function (r) {
      return !(r.congress && (r.office === "U.S. Senator") === senate);
    })[0];
    if (!row) return "";
    return '<span class="card-held truncate" title="' + KYC.escapeAttr(KYC.heldText(row)) + '">' +
      KYC.escapeHtml((row.current ? "" : "Fmr. ") + row.office) + "</span>";
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
      heldLine(item),
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
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /** "2026-12-01" -> "Dec 1". */
  function shortDate(iso) {
    var m = /^\d{4}-(\d{2})-(\d{2})$/.exec(String(iso || ""));
    return m ? MONTHS[+m[1] - 1] + " " + (+m[2]) : "";
  }

  /* How the race's ballot is decided, visibly and linked to the guide that
   * explains it: a top-two ballot of two Democrats read like a misprint
   * with the rule only in a hover title (audit 2026-10-17, RACES-11), and
   * Georgia's and Louisiana's December rounds were on no state page
   * (PERSONA-06). The pipeline says which (races.ballot_kind, from tables
   * citing each statute); nothing here knows a state. */
  var KIND = {
    "top-two": ["Top-two primary", "primaries",
      "Every candidate ran on one primary ballot, and the two with the most votes go to November " +
      "whatever their party."],
    "top-four": ["Top-four primary", "primaries",
      "Every candidate ran on one primary ballot, and the four with the most votes go to November " +
      "whatever their party; November is decided by ranked-choice voting."],
    "open": ["Open primary Nov 3", "primaries",
      "Every candidate runs on one ballot on November 3; a candidate with a majority of the votes " +
      "is elected."],
  };

  function guideLink(section, cls, title, text) {
    return '<a class="badge ' + cls + '" href="' +
      KYC.escapeAttr(KYC.siteRoot() + "government/elections.html#" + section) + '" title="' +
      KYC.escapeAttr(title) + '">' + KYC.escapeHtml(text) + "</a>";
  }

  function todayIso() {
    var now = new Date();
    return now.getFullYear() + "-" + ("0" + (now.getMonth() + 1)).slice(-2) + "-" +
      ("0" + now.getDate()).slice(-2);
  }

  /** Whether the race's primary has been held, and the words that say so.
   *  A ballot read from a qualified list is not a held primary until its
   *  date has passed. */
  function primaryState(race) {
    var listed = !!(race.results && race.results.fromQualifiedList);
    var held = race.settled && (!listed || race.primaryDate < todayIso());
    return {
      held: held,
      title: held && listed
        ? "Primary held " + race.primaryDate + (race.runoffDate ? "; runoff " + race.runoffDate : "") +
          ". Its ballot was the Secretary of State's list of qualified candidates; no result " +
          "has been read yet."
        : held
        ? "Primary held " + race.primaryDate +
          (race.runoffDate ? "; runoff " + race.runoffDate : "") +
          ". Results from the state's Wikipedia election page."
        : "Primary scheduled for " + race.primaryDate + "." + (listed
          ? " Who is on its ballot: the Secretary of State's list of qualified candidates."
          : ""),
    };
  }

  /* The badges follow the race through the election (rule 63): "Runoff
   * Dec 1 if no majority" stayed on a race decided on November 3, and read
   * in the future tense after December 1 (PR #94 review). A race with one
   * marked winner has no December round; one the results send to a runoff
   * says so without the "if"; a date that has passed is "held". And an
   * open primary's date is said once, on its own badge: Louisiana's House
   * heads read "Primary 2026-11-03" beside "Open primary Nov 3". */
  function ballotKindBadges(race) {
    var out = [];
    var today = todayIso();
    var kind = KIND[race.primaryKind];
    if (kind) {
      var title = kind[2];
      var text = kind[0];
      if (race.primaryKind === "open" && race.primaryDate) {
        // The primary's own badge, folded in: one date, once.
        var primary = primaryState(race);
        text = (primary.held ? "Open primary held " : "Open primary ") + shortDate(race.primaryDate);
        title = primary.title + " " + title;
      }
      out.push(guideLink(kind[1], "badge-neutral badge-link", title, text));
    }
    if (race.generalRunoff) {
      var after = KYC.electionStatus().phase === "post-election" && race.settled;
      var res = race.results || {};
      if (after && namesWith(race, "elected", res.otherElected).length === 1) return out;
      var going = after && namesWith(race, "runoff", res.otherRunoff).length > 0;
      var when = shortDate(race.generalRunoff);
      var held = race.generalRunoff < today;
      var round = race.primaryKind === "open" ? "General " : "Runoff ";
      out.push(guideLink("runoffs", "badge-neutral badge-link",
        held
          ? "The date set for a " + (race.primaryKind === "open" ? "general election" : "runoff") +
            " if no candidate won a majority on November 3: " + when + "."
          : going
          ? "No candidate won a majority on November 3; the top two meet on " + when + "."
          : race.primaryKind === "open"
          ? "If no candidate wins a majority on November 3, the top two, of any party, meet on " +
            when + "."
          : "If no candidate wins a majority on November 3, the top two meet in a runoff on " +
            when + ".",
        round + (held ? (going ? "held " + when : when + ", if one was needed")
          : going ? when : when + " if no majority")));
    }
    return out;
  }

  function raceBadges(race) {
    var badges = [];
    var outcome = outcomeBadge(race);
    if (outcome) badges.push(outcome);
    if (race.openSeat) {
      var holder = race.incumbentIds.map(KYC.byId).filter(Boolean)[0];
      // The record names who held the seat even when they have no profile.
      var named = race.incumbent && race.incumbent.name;
      // A mid-decade map keeps every district number, so a seat nobody
      // holds is vacant, not new: FL-20 and TX-23 read "newly drawn".
      var why = !holder ? (named ? named + " no longer holds the seat." :
          "No sitting member: the seat is vacant.") :
        // Seated since in the seat they won elsewhere (kyc/record.py).
        holder.raceRole === "winner" && holder.raceId !== race.id
          ? holder.name + " won the race for " + holder.officeLabel.replace(/ • /, " ") + "." :
        holder.contestLabel && KYC.offBallot(KYC.contestStatus(holder))
          ? holder.name + " ran for " + holder.contestLabel.replace(/ • /, " ") +
            " and is not on the November ballot." :
        holder.contestLabel ? holder.name + " is running for " + holder.contestLabel + "." :
        holder.alsoRunningSeat ? holder.name + " is running for " + holder.alsoRunningSeat + "." :
        KYC.offBallot(holder.raceStatus) ? holder.name + " is not on the November ballot." :
        holder.name + " is not seeking re-election.";
      if (race.holderMoved) {
        why = race.holderMoved.name + ", who holds this seat, is running for " +
          race.holderMoved.to.replace(/ • /, " ") + " under the state's new district map; no " +
          "sitting member is on this seat's ballot.";
      }
      badges.push('<span class="badge badge-warn" title="' + KYC.escapeAttr(why) + '">Open seat</span>');
    } else if (race.holderMoved) {
      // Not open - a member is running here under the new number - but its
      // holder is on another seat's ballot, and the reader should see where.
      badges.push('<span class="badge badge-neutral" title="' + KYC.escapeAttr(
        race.holderMoved.name + ", who holds this seat, is running for " +
        race.holderMoved.to.replace(/ • /, " ") + " under the state's new district map.") +
        '">Holder running in ' + KYC.escapeHtml(race.holderMoved.to.replace(/^House • /, "")) +
        "</span>");
    }
    // An open primary's date is on its own badge (ballotKindBadges).
    if (race.primaryDate && race.primaryKind !== "open") {
      var primary = primaryState(race);
      badges.push(
        '<span class="badge badge-neutral" title="' + KYC.escapeAttr(primary.title) + '">' +
        (primary.held ? "Primary held " : "Primary ") + KYC.escapeHtml(race.primaryDate) +
        "</span>"
      );
    }
    badges = badges.concat(ballotKindBadges(race));

    /* "No declared challenger" was a claim about our roster dressed up as
     * a fact about the race, and it was wrong for 372 of them. filedCount
     * is how many people have actually filed with the FEC for the seat. */
    var res = race.results || null;
    // Nominees the results page names with no profile here: a filing under
    // $5,000, or none. They are on the ballot, so they count (rule 22).
    var unprofiled = res && res.otherNominees ? res.otherNominees.length : 0;
    var noProfile = unprofiledNames(race).none;
    if (race.contested && !(race.candidateCount + unprofiled) && race.ballotUnknown) {
      // Nobody known to be on the ballot, and someone who may be: never
      // "No challenger on the ballot", never "0 challengers".
      badges.push('<span class="badge badge-neutral" title="' + KYC.escapeAttr(
        "Filed with the FEC; the published results do not name them, so whether they are on " +
        "the November ballot is not known here.") + '">' + race.ballotUnknown +
        " filed, ballot status not known</span>");
    } else if (race.contested) {
      var running = race.candidateCount + unprofiled;
      // With nobody holding the seat on the ballot, nobody is challenging.
      var word = race.openSeat ? "candidate" : "challenger";
      badges.push(
        '<span class="badge badge-money">' + running +
        " " + word + (running === 1 ? "" : "s") +
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
    if (noProfile.length) {
      badges.push(
        '<span class="badge badge-warn" title="' + KYC.escapeAttr(
          "On the November ballot " + KYC.ballotSource(race) + ", with no FEC filing " +
          "over $5,000 - the point at which federal law treats someone as a " +
          "candidate - so no profile here: " + noProfile.join(", ")
        ) + '">' + noProfile.length + " with no profile here</span>"
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
    var body = '<div class="card-grid">' + running.map(card).join("") + "</div>" +
      unprofiledNote(race) + orderNote(running.length ? running : people, race, people.length);
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

  /* How the people of a race are listed, under them, where there are two
   * or more to order (TRUST-15). The order is the pipeline's
   * (races.order_people); the sentence names the holder only when *people*
   * opens with one (KYC.raceOrderNote). *count*, when given, is how many
   * the whole list holds. */
  function orderNote(people, race, count) {
    var n = count === undefined ? people.length : count;
    return n > 1
      ? '<p class="race-order">' + KYC.escapeHtml(KYC.raceOrderNote(people, race)) + "</p>"
      : "";
  }

  /* The people the published results put on the November ballot whom no
   * profile here matches, split into those with no profile at all and
   * those whose name may be a profile's under another spelling. */
  function unprofiledNames(race) {
    var res = (race && race.results) || {};
    var maybe = res.maybeProfiled || {};
    var names = res.otherNominees || [];
    return {
      none: names.filter(function (n) { return !maybe[n]; }),
      maybe: names.filter(function (n) { return maybe[n]; })
        .map(function (n) { return { name: n, id: maybe[n] }; }),
    };
  }

  /* One visible line for them, in every view that lists a race: the race
   * sections, the profile's race panel, the district pages, the Senate view
   * and the map's state panel. Left out, a member with a named November
   * opponent read as unopposed, and Tennessee's Senate seat listed two
   * people running over a ballot of nine. */
  function unprofiledNote(race, cls) {
    var u = unprofiledNames(race);
    var parts = [];
    if (u.none.length) {
      parts.push("Also on the November ballot, " + KYC.escapeHtml(KYC.ballotSource(race)) +
        ", with no FEC filing over $5,000 and so no profile here: " +
        KYC.escapeHtml(u.none.join(", ")) + ".");
    }
    u.maybe.forEach(function (m) {
      var who = KYC.byId(m.id);
      parts.push("The results also name " + KYC.escapeHtml(m.name) + ", who may be " +
        KYC.escapeHtml(who ? who.name : "a candidate with a profile here") +
        " under another spelling; this site has not confirmed it.");
    });
    return parts.length ? '<p class="' + (cls || "race-note") + '">' + parts.join(" ") + "</p>" : "";
  }

  KYC.cards = {
    unprofiledNames: unprofiledNames,
    unprofiledNote: unprofiledNote,
    orderNote: orderNote,
    offBallot: offBallot,
    raceBadge: raceBadge,
    statusBadge: statusBadge,
    card: card,
    raceBadges: raceBadges,
    raceSection: raceSection,
  };
})(window);
