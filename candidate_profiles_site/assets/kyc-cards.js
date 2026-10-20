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
      " line, per Wikipedia's results page." + (campaign ? "" : " " + spec.title) : spec.title;
    return '<span class="badge ' + spec.cls + '" title="' + KYC.escapeAttr(title) +
      '">' + KYC.escapeHtml(spec.label) + KYC.ballotLineSuffix(item) + "</span>";
  }

  /* The badges a card shows about a seat rather than a race, in one table
   * with the words the key on the grid gives them (legend, GRID-19). */
  var SEAT_BADGES = {
    former: { cls: "badge-neutral", label: "Former member",
      title: "Held this seat in the 2026 race and has since left Congress." },
    leaving: { cls: "badge-danger", label: "Leaving in ’26",
      title: "The member’s status line says they are retiring or not running for this seat " +
        "again." },
    challenger: { cls: "badge-money", label: "2026 challenger",
      title: "Filed with the FEC; the primary has not been held yet." },
    vacant: { cls: "badge-neutral", label: "Vacant seat", title: "Nobody holds this seat now." },
    up: { cls: "badge-warn", label: "Seat up in 2026",
      title: "This Senate seat’s term ends in January 2027, so the seat is on the 2026 ballot." },
    later: { cls: "badge-neutral", label: "Seat up in 2028 or 2030",
      title: "The year this Senate seat is next on the ballot. It says when the term ends, not " +
        "whether the senator will run." },
    running: { cls: "badge-warn", label: "Running for …",
      title: "A sitting member running for another seat in 2026; the badge names it." },
    redrawn: { cls: "badge-neutral", label: "Running in … (redrawn)",
      title: "A sitting member running for re-election under the state’s new district map, " +
        "for the district the badge names." },
    ran: { cls: "badge-neutral", label: "Ran for …",
      title: "A sitting member who ran for another seat in 2026 and is not on its November ballot." },
  };

  function seatBadge(key, label, title) {
    var spec = SEAT_BADGES[key];
    return '<span class="badge ' + spec.cls + '" title="' + KYC.escapeAttr(title || spec.title) +
      '">' + KYC.escapeHtml(label || spec.label) + "</span>";
  }

  function statusBadge(item) {
    var status = String(item.status || "").toLowerCase();

    /* A 2026 incumbent who has left Congress: that first, then how their
     * race went. Never "seat up", never a sitting member's badge. */
    if (item.formerMember) {
      var how = raceBadge(item);
      return seatBadge("former", null, KYC.formerText(item) + "; held this seat in the 2026 race.") +
        (how ? " " + how : "");
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
      return seatBadge("leaving") + KYC.otherOfficeBadge(item, " ");
    }
    if (item.isCandidate) {
      /* The primary has been held and the published results do not name
       * them (an independent, a minor party's filer): not "the primary has
       * not been held yet", and not counted as on the ballot. raceBadge
       * says so, as KYC.standing words it for every view. */
      return raceBadge(item) || seatBadge("challenger");
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
      return seatBadge("vacant");
    }
    /* The badge speaks of the seat, never the person: the data knows when
     * the term ends (electionYear is its last year, less one), not whether
     * the senator will run. "On the ballot in 2028" claimed the second. The
     * year in full: "Up in ’28" was shorthand a reader had to decode
     * (TRUST-17). */
    if (item.chamber.indexOf("Senate") !== -1 && item.seatUp2026) {
      return seatBadge("up");
    }
    if (item.chamber.indexOf("Senate") !== -1 && item.electionYear) {
      return seatBadge("later", "Seat up in " + item.electionYear,
                       "The year this Senate seat is next on the ballot.");
    }
    return "";
  }

  /** The key to every status word a card shows: where someone stands in
   *  their race (KYC.raceStatusLegend, from the table that words the
   *  badges), then what the seat badges mean. Collapsed until asked for. */
  function legend() {
    var row = function (spec) {
      return '<div class="legend-row"><dt><span class="badge ' + KYC.escapeAttr(spec.cls) + '">' +
        KYC.escapeHtml(spec.label) + "</span></dt><dd>" + KYC.escapeHtml(spec.title) + "</dd></div>";
    };
    var seats = Object.keys(SEAT_BADGES).map(function (k) { return SEAT_BADGES[k]; });
    return '<details class="status-legend"><summary>What the labels on the cards mean</summary>' +
      '<h3 class="legend-heading">Where someone stands in their 2026 race</h3>' +
      '<dl class="legend-list">' + KYC.raceStatusLegend().map(row).join("") + "</dl>" +
      '<h3 class="legend-heading">About the seat</h3>' +
      '<dl class="legend-list">' + seats.map(row).join("") + "</dl>" +
      '<p class="legend-note">A card’s own badge names the source its status was read ' +
      "from: Wikipedia’s results page for the state, or the state’s list of " +
      "candidates.</p></details>";
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
      KYC.escapeHtml((row.current ? "" : "Former ") + row.office) + "</span>";
  }

  /** How to reach a sitting member's office, or null (GRID-16): the
   *  contact form their record or their official website gives (the
   *  dialog's "Contact form", checked as kyc/members.py reads it), else the
   *  Washington office's phone, else a district or state office's. Only a
   *  member who sits now (KYC.seated): a challenger's campaign form is not
   *  "contact your representative" (rule 27), and a former member's office
   *  is closed. Never a campaign site. */
  function contactOf(item) {
    if (!item || !KYC.seated(item)) return null;
    var who = item.name + "’s office";
    if (item.contactForm && /^https?:\/\//i.test(item.contactForm)) {
      return { href: item.contactForm, external: true, label: "Contact office",
        title: "Write to " + who + ": " + (item.contactFormVia === "official-site"
          ? "the contact page their official website links" +
            (item.contactFormChecked ? ", checked on " + KYC.dateWords(item.contactFormChecked) : "")
          : "the contact form congress-legislators records for them") };
    }
    var tel = function (phone, where) {
      return { href: "tel:" + String(phone).replace(/[^\d+]/g, ""), label: "Call office",
        title: "Call " + who + " in " + where + ": " + phone };
    };
    if (item.phone) return tel(item.phone, "Washington");
    var home = (item.districtOffices || []).filter(function (o) { return o && o.phone; })[0];
    return home ? tel(home.phone, home.city || "the " +
      (/Senate/.test(item.chamber) ? "state" : "district")) : null;
  }

  /** The contact link itself, beside a card or in a line of a race. */
  function contactLink(item, cls) {
    var c = contactOf(item);
    if (!c) return "";
    return '<a class="' + (cls || "card-contact") + '" href="' + KYC.escapeAttr(c.href) + '"' +
      (c.external ? ' target="_blank" rel="noopener noreferrer"' : "") +
      ' title="' + KYC.escapeAttr(c.title) + '" aria-label="' +
      KYC.escapeAttr(c.label.replace(/ office$/, "") + " " + item.name + "’s office") + '">' +
      // One look for both forms of the action, and not the dialog's
      // "Copy link" arrow: an envelope for a form, a handset for a call.
      KYC.icon(c.external ? "mail" : "phone", "icon-sm") + KYC.escapeHtml(c.label) + "</a>";
  }

  /* Every interpolation is escaped. The previous version put item.name,
   * item.party and the office label straight into innerHTML and carried an
   * onclick with the id interpolated into it; one delegated listener reads
   * data-id instead. */
  /* *opts.note* is a line the view adds under the card's facts: an age
   * under an age sort, where a search matched (kyc-directory.js). A sitting
   * member's card carries a way to reach their office beside it, outside
   * the button: a link cannot sit inside one. */
  function card(item, opts) {
    var note = opts && typeof opts === "object" ? opts.note : "";
    var contact = contactLink(item);
    var html = cardButton(item, note);
    return contact ? '<div class="card-cell">' + html + contact + "</div>" : html;
  }

  function cardButton(item, note) {
    // No portrait (rule 24 guesses none): a disc with the person's
    // initials, not a 150x190 grey silhouette (VISUALS-16).
    var photo = KYC.hasPortrait(item)
      ? ['<span class="card-photo">',
        // Cards measured 146-171px wide from a phone to a 2,000px screen.
        '<img ', KYC.portraitAttrs(item, "165px"),
        ' alt="" loading="lazy" decoding="async" data-photo-idx="0" data-profile="',
        KYC.escapeAttr(item.id), '">', "</span>"].join("")
      : '<span class="card-photo card-monogram" aria-hidden="true">' +
        KYC.escapeHtml(KYC.monogram(item.name)) + "</span>";
    return [
      '<button type="button" class="card', KYC.hasPortrait(item) ? "" : " card-no-photo",
      '" data-id="', KYC.escapeAttr(item.id), '">',
      photo,
      '<span class="card-body">',
      '<span class="card-name clamp-2">', KYC.escapeHtml(item.name), "</span>",
      '<span class="card-office truncate">', KYC.escapeHtml(item.officeLabel), "</span>",
      heldLine(item),
      '<span class="card-party ', KYC.partyClass(item), '">',
      KYC.escapeHtml(item.party), "</span>",
      statusBadge(item),
      note ? '<span class="card-note clamp-2">' + KYC.escapeHtml(note) + "</span>" : "",
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
        "Marked as the winner on Wikipedia's election results page.") +
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

  /* One badge of a race's head, as data: *key* names the fact it states,
   * so the state page can say once the ones every race shares and a folded
   * race's row can repeat the ones that tell races apart (headBadgeHtml
   * draws it; *html*, where given, is drawn as it is). */
  function headBadge(key, cls, text, title, href) {
    return { key: key, cls: cls, text: text, title: title || "", href: href || "" };
  }

  /* The badge as the race's head draws it; *shared* marks one that every
   * race on the page shares, which a phone says once above the races. */
  function headBadgeHtml(b, shared) {
    if (b.html) return b.html;
    var cls = "badge " + b.cls + (shared ? " badge-shared" : "");
    var title = b.title ? ' title="' + KYC.escapeAttr(b.title) + '"' : "";
    return b.href
      ? '<a class="' + cls + '" href="' + KYC.escapeAttr(b.href) + '"' + title + ">" +
        KYC.escapeHtml(b.text) + "</a>"
      : '<span class="' + cls + '"' + title + ">" + KYC.escapeHtml(b.text) + "</span>";
  }

  function guideLink(section, cls, title, text) {
    return headBadge(section === "runoffs" ? "runoff" : "kind", cls, text, title,
      KYC.siteRoot() + "government/elections.html#" + section);
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
        ? "Primary held " + KYC.dateWords(race.primaryDate) +
          (race.runoffDate ? "; runoff " + KYC.dateWords(race.runoffDate) : "") +
          ". Its ballot was the Secretary of State's list of qualified candidates; no result " +
          "has been read yet."
        : held
        ? "Primary held " + KYC.dateWords(race.primaryDate) +
          (race.runoffDate ? "; runoff " + KYC.dateWords(race.runoffDate) : "") +
          ". Results from the state's Wikipedia election page."
        : "Primary scheduled for " + KYC.dateWords(race.primaryDate) + "." + (listed
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
  function ballotKindItems(race) {
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

  /* Why a race is an open seat, in the words its badge's hover gives and a
   * folded race's row shows (raceRow): one sentence, from the record. */
  var NO_MEMBER = "No sitting member: the seat is vacant.";

  function openSeatWhy(race) {
    var holder = race.incumbentIds.map(KYC.byId).filter(Boolean)[0];
    // The record names who held the seat even when they have no profile.
    var named = race.incumbent && race.incumbent.name;
    if (race.holderMoved) {
      return race.holderMoved.name + ", who holds this seat, is running for " +
        race.holderMoved.to.replace(/ • /, " ") + " under the state's new district map; no " +
        "sitting member is on this seat's ballot.";
    }
    // A mid-decade map keeps every district number, so a seat nobody
    // holds is vacant, not new: FL-20 and TX-23 read "newly drawn".
    return !holder ? (named ? named + " no longer holds the seat." : NO_MEMBER) :
      // Seated since in the seat they won elsewhere (kyc/record.py).
      holder.raceRole === "winner" && holder.raceId !== race.id
        ? holder.name + " won the race for " + holder.officeLabel.replace(/ • /, " ") + "." :
      holder.contestLabel && KYC.offBallot(KYC.contestStatus(holder))
        ? holder.name + " ran for " + holder.contestLabel.replace(/ • /, " ") +
          " and is not on the November ballot." :
      holder.contestLabel ? holder.name + " is running for " + holder.contestLabel + "." :
      holder.alsoRunningSeat ? holder.name + " is running for " + holder.alsoRunningSeat + "." :
      KYC.offBallot(holder.raceStatus) ? holder.name + " is not on the November ballot." :
      // An appointee was never elected to the seat, so is not "not seeking
      // re-election" (rule 61): the words their own card gives.
      holder.appointed ? holder.name + " was appointed to the seat and is not running in 2026." :
      holder.name + " is not seeking re-election.";
  }

  /** The badges that summarise a race, as data (headBadge), in the order
   *  its head shows them. */
  function raceBadgeItems(race) {
    var badges = [];
    var outcome = outcomeBadge(race);
    if (outcome) badges.push({ key: "outcome", html: outcome, text: outcome.replace(/<[^>]*>/g, "") });
    if (race.openSeat) {
      badges.push(headBadge("open", "badge-warn", "Open seat", openSeatWhy(race)));
    } else if (race.holderMoved) {
      // Not open - a member is running here under the new number - but its
      // holder is on another seat's ballot, and the reader should see where.
      badges.push(headBadge("moved", "badge-neutral",
        "Holder running in " + race.holderMoved.to.replace(/^House • /, ""),
        race.holderMoved.name + ", who holds this seat, is running for " +
        race.holderMoved.to.replace(/ • /, " ") + " under the state's new district map."));
    }
    // An open primary's date is on its own badge (ballotKindItems).
    if (race.primaryDate && race.primaryKind !== "open") {
      var primary = primaryState(race);
      badges.push(headBadge("primary", "badge-neutral",
        (primary.held ? "Primary held " : "Primary ") + KYC.dateWords(race.primaryDate), primary.title));
    }
    badges = badges.concat(ballotKindItems(race));

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
      badges.push(headBadge("count", "badge-neutral", race.ballotUnknown +
        " filed, ballot status not known",
        "Filed with the FEC; Wikipedia's results page does not name them, so whether they are on " +
        "the November ballot is not known here."));
    } else if (race.contested) {
      var running = race.candidateCount + unprofiled;
      // With nobody holding the seat on the ballot, nobody is challenging.
      var word = race.openSeat ? "candidate" : "challenger";
      badges.push(headBadge("count", "badge-money", running + " " + word + (running === 1 ? "" : "s") +
        (race.settled ? " on the ballot" : "")));
    } else if (race.settled && res) {
      var gone = res.eliminated + res.withdrawn + res.unlisted;
      badges.push(headBadge("count", "badge-neutral",
        "No challenger on the ballot" + (gone ? " · " + gone + " out" : ""),
        "The primary has been held. Of those who filed with the FEC, " +
        res.eliminated + " lost, " + res.withdrawn + " withdrew and " +
        res.unlisted + " were not on the primary ballot."));
    } else if (race.filedCount) {
      badges.push(headBadge("count", "badge-neutral", race.filedCount + " filed, none past $5k",
        race.filedCount + " people have filed with the FEC for this seat, " +
        "but none has yet reported raising $5,000 - the point at which " +
        "federal law treats someone as a candidate."));
    } else {
      badges.push(headBadge("count", "badge-neutral", "Nobody has filed"));
    }

    /* People the results page puts on the ballot but the FEC has no
     * filing for. Leaving them off would make the header lie. */
    if (noProfile.length) {
      badges.push(headBadge("noprofile", "badge-warn", noProfile.length + " with no profile here",
        "On the November ballot " + KYC.ballotSource(race) + ", with no FEC filing " +
        "over $5,000 - the point at which federal law treats someone as a " +
        "candidate - so no profile here: " + noProfile.join(", ")));
    }

    if (race.contested && race.filedCount) {
      badges.push(headBadge("registered", "badge-neutral", race.filedCount + " registered with the FEC",
        "Everyone registered with the FEC for this seat, including the sitting " +
        "member and everyone below the $5,000 threshold."));
    }
    // Where the statuses above were read, linked (TRUST-06).
    var source = KYC.resultsSourceHtml(race);
    if (source) badges.push({ key: "source", html: source, text: "" });
    return badges;
  }

  /** The race's head badges; *opts.shared* (sharedBadges) marks the ones
   *  every race on the page shares. */
  function raceBadges(race, opts) {
    var shared = (opts && opts.shared) || {};
    return raceBadgeItems(race).map(function (b) {
      return headBadgeHtml(b, sameBadge(shared[b.key], b));
    }).join("");
  }

  function sameBadge(a, b) {
    return !!a && !!b && !a.html && !b.html && a.text === b.text && a.title === b.title && a.href === b.href;
  }

  /* The facts a page of races may share: when its primary was, what kind
   * of primary, when a runoff would be. */
  var SHAREABLE = ["primary", "kind", "runoff"];

  /** The head badges every one of *races* carries in the same words, by
   *  key: California's 52 heads each said "Primary held June 2, 2026" and
   *  "Top-two primary" (VISUALS-15). {} for fewer than two races. */
  function sharedBadges(races) {
    var shared = {};
    if (!races || races.length < 2) return shared;
    var lists = races.map(raceBadgeItems);
    SHAREABLE.forEach(function (key) {
      var first = null;
      var same = lists.every(function (items) {
        var b = items.filter(function (x) { return x.key === key; })[0];
        if (!b) return false;
        if (!first) first = b;
        return sameBadge(first, b);
      });
      if (same && first) shared[key] = first;
    });
    return shared;
  }

  /** One race: its header, the people still in it, and the people the
   *  primary removed folded underneath. *people* is the already-filtered
   *  list of profiles to show; *opts.title* overrides the heading. */
  /* A seat's holder who is running for another seat is not one of the
   * people running for this one: CA-3's grid opened with "Kevin Kiley -
   * Running for House CA-6; On the November ballot", and a reader skimming
   * it saw three people on CA-3's ballot (RACES-18). They are one line
   * above it, which says where they are running. */
  function elsewhere(race, p) {
    return !p.isCandidate && (race.incumbentIds || []).indexOf(p.id) !== -1 &&
      !!p.contestRaceId && p.contestRaceId !== race.id && !!p.contestLabel;
  }

  /* What a seat's holder running elsewhere is doing, after "who": the one
   * clause the race's "Held by" line and its folded row both say. */
  function heldByWhat(p) {
    var line = KYC.contestLine(p);
    var seat = String(p.contestLabel).replace(/ • /, " ").replace(/^House /, "");
    return !line ? "is running for " + seat
      : line.renumbered ? (line.past ? "ran in " + seat + " under the state’s new district map, " +
          "and is not on its November ballot" : "is running in " + seat + " under the state’s " +
          "new district map")
      : line.past ? "ran for " + seat + " and is not on its November ballot"
      : "is running for " + seat;
  }

  function heldByLine(p) {
    // They still hold the seat, so the race says how to reach their office
    // as their card would (GRID-16).
    var contact = contactLink(p, "card-contact race-held-contact");
    return '<p class="race-held">Held by <button type="button" class="link-button" data-id="' +
      KYC.escapeAttr(p.id) + '">' + KYC.escapeHtml(p.name) + "</button>, who " +
      KYC.escapeHtml(heldByWhat(p)) + "." + (contact ? " " + contact : "") + "</p>";
  }

  /** Who holds the seat, in sentences, for a folded race's row: the holder
   *  running elsewhere in the words of the race's own "Held by" line; an
   *  open seat in its badge's words (openSeatWhy); an empty seat by its
   *  vacancy record; else the holder on this race's ballot. A member who
   *  has left since (rule 67) is never "held by". *split* is racePeople's. */
  function holderWords(race, split) {
    var out = [];
    var holders = split.people.filter(function (p) {
      return (race.incumbentIds || []).indexOf(p.id) !== -1;
    });
    var vacancy = !holders.length && !split.moved.length && race.chamber === "House" && KYC.vacancyOf
      ? KYC.vacancyOf(race.state, race.district || 0) : null;
    if (race.openSeat && !vacancy) out.push("Open seat.");
    if (split.moved.length) {
      split.moved.forEach(function (p) { out.push("Held by " + p.name + ", who " + heldByWhat(p) + "."); });
    } else if (vacancy) {
      out.push(KYC.vacancyNote(vacancy));
    } else if (race.openSeat) {
      out.push(openSeatWhy(race));
    } else if (!holders.length) {
      out.push(NO_MEMBER);
    } else {
      holders.forEach(function (p) {
        // A holder out of the race (a lost primary) says so in their card's
        // words: the ballot below does not name them.
        var spec = offBallot(p) ? KYC.standing(p, "card") : null;
        // One who has left since says until when, as the Senate view's
        // "Held the seat until" does (rule 67).
        out.push(KYC.seated(p) ? "Held by " + p.name + (spec ? " (" + spec.label + ")" : "") + "."
          : p.formerMember ? "Held by " + p.name + " until " + p.formerMember.left + "."
          : p.name + " held this seat in the 2026 race.");
      });
    }
    return out.join(" ");
  }

  /* A person in a row: their name, party and any ballot line not their
   * party's, as their card gives them. */
  function rowName(p) {
    var abbr = KYC.partyAbbr(p);
    var line = KYC.ballotLine(p);
    return p.name + (abbr ? " (" + abbr + ")" : "") + (line ? " – " + line + " line" : "");
  }

  /** Who a folded race's row names, from the helpers its section uses:
   *  `ballot`, everyone on the November ballot grouped by the status words
   *  their cards carry (KYC.standing), with the results' names that have no
   *  profile here; `unsettled`, the filers the results do not settle,
   *  never counted as on it (rule 62), grouped the same way. Each group is
   *  [label, [names]]. A holder with no status yet is named by the line
   *  above, and a filer before any primary carries the card's own word. */
  function rowPeople(race, split) {
    var ballot = [];
    var unsettled = [];
    var add = function (list, label, name) {
      var group = list.filter(function (g) { return g[0] === label; })[0];
      if (!group) list.push(group = [label, []]);
      group[1].push(name);
    };
    split.running.forEach(function (p) {
      var spec = KYC.standing(p, "card");
      if (spec && spec.unknown) return add(unsettled, spec.label, rowName(p));
      // A member seated since in the seat this race decided (rule 67), with
      // no result read for them yet, in the Senate view's words for them.
      var label = spec ? spec.label : p.isCandidate ? SEAT_BADGES.challenger.label
        : p.raceRole === "winner" && KYC.seated(p) && race.year ? "Holds the seat (won it in " + race.year + ")"
        : "";
      if (label) add(ballot, label, rowName(p));
    });
    var u = unprofiledNames(race);
    var parties = ((race.results || {}).otherParties) || {};
    u.none.forEach(function (n) {
      var abbr = parties[n] ? KYC.partyAbbr({ party: parties[n] }) : "";
      add(ballot, "Also on the November ballot, no profile here", n + (abbr ? " (" + abbr + ")" : ""));
    });
    u.maybe.forEach(function (m) {
      add(ballot, "Also named, may be a profile here under another spelling", m.name);
    });
    return { ballot: ballot, unsettled: unsettled };
  }

  /* The head badges a row repeats: the outcome, the count of who is on the
   * ballot (the head's own figure, rule 73), and the ballot's dates and
   * kind where they differ from the page's other races. */
  var ROW_BADGES = { outcome: true, count: true, primary: true, kind: true, runoff: true };

  function groupsHtml(cls, groups) {
    return groups.map(function (g) {
      return '<span class="' + cls + '"><span class="race-row-label">' + KYC.escapeHtml(g[0]) +
        ":</span> " + g[1].map(function (name) {
          return '<span class="race-row-name">' + KYC.escapeHtml(name) + "</span>";
        }).join(", ") + ".</span> ";
    }).join("");
  }

  /** A race folded to one row (VISUALS-15): a heading whose button opens
   *  the race's section below it. *fold*: {short, label, shared}: the
   *  district's number or "Senate", the race's name, and the badges the
   *  page says once (sharedBadges). Drawn hidden; the page shows it where
   *  it folds. */
  function raceRow(race, split, fold) {
    var who = rowPeople(race, split);
    var badges = raceBadgeItems(race).filter(function (b) {
      return ROW_BADGES[b.key] && !sameBadge((fold.shared || {})[b.key], b);
    }).map(function (b) {
      // Inside a button: the words, never a link.
      return b.html || '<span class="badge ' + KYC.escapeAttr(b.cls.replace(/ ?badge-link/, "")) + '">' +
        KYC.escapeHtml(b.text) + "</span>";
    }).join(" ");
    var held = holderWords(race, split);
    return '<h3 class="race-row-title" hidden><button type="button" class="race-row" aria-expanded="true" ' +
      'aria-controls="' + KYC.escapeAttr("race-body-" + race.id) + '" data-race-toggle="' +
      KYC.escapeAttr(race.id) + '">' +
      '<span class="race-row-num' + (/^\d+$/.test(fold.short) ? "" : " is-word") + '" aria-hidden="true">' +
      KYC.escapeHtml(fold.short) + "</span>" +
      '<span class="race-row-main"><span class="sr-only">' + KYC.escapeHtml(fold.label) + ". </span>" +
      (held ? '<span class="race-row-held">' + KYC.escapeHtml(held) + "</span> " : "") +
      groupsHtml("race-row-ballot", who.ballot) + groupsHtml("race-row-unsettled", who.unsettled) +
      (badges ? '<span class="race-row-badges">' + badges + "</span>" : "") + "</span>" +
      KYC.icon("chevron", "race-row-chevron") + "</button></h3>";
  }

  /* The people the primary removed, folded under the race. With
   * *opts.lazyOut* their cards are drawn only when the list is opened
   * (fillOut): the grid's race view built 2,515 cards, 3.3 MB of markup,
   * most of them folded away (GRID-14). */
  var lazyPeople = {};

  function fillOut(details) {
    var key = details.getAttribute("data-out-race");
    var people = lazyPeople[key];
    var grid = details.querySelector(".card-grid");
    if (!people || !grid || grid.childElementCount) return;
    grid.innerHTML = people.map(function (p) { return card(p); }).join("");
  }

  /** A race's people as every view that lists the race splits them: the
   *  seat's holder running elsewhere (*moved*, one line above the race),
   *  the people still in it (*running*) and those no longer in it (*out*),
   *  each in the pipeline's order; *people* is everyone but the moved. The
   *  race sections and the Your ballot page split them here, so the two
   *  list the same people (rules 12 and 73). */
  function racePeople(race, people) {
    var moved = people.filter(function (p) { return elsewhere(race, p); });
    people = people.filter(function (p) { return moved.indexOf(p) === -1; });
    return { moved: moved, people: people,
             running: people.filter(function (p) { return !offBallot(p); }),
             out: people.filter(offBallot) };
  }

  function raceSection(race, people, opts) {
    opts = opts || {};
    var split = racePeople(race, people);
    var moved = split.moved, running = split.running, out = split.out;
    people = split.people;
    var body = moved.map(heldByLine).join("") +
      '<div class="card-grid">' + running.map(function (p) { return card(p); }).join("") + "</div>" +
      unprofiledNote(race) + orderNote(running.length ? running : people, race, people.length);
    if (out.length) {
      if (opts.lazyOut) lazyPeople[race.id] = out;
      body +=
        '<details class="race-out"' + (opts.lazyOut ? ' data-out-race="' +
          KYC.escapeAttr(race.id) + '"' : "") + "><summary>" + out.length +
        " no longer in this race &mdash; lost the primary, withdrew, or were " +
        "not on the primary ballot</summary>" +
        '<div class="card-grid">' + (opts.lazyOut ? "" : out.map(function (p) { return card(p); })
          .join("")) + "</div></details>";
    }
    var title = opts.title || race.label;
    var link = opts.stateLink === false ? "" :
      ' <a class="race-state-link" href="' + KYC.escapeAttr(KYC.stateUrl(race.state)) +
      '" title="' + KYC.escapeAttr("Everything about " + KYC.stateName(race.state)) + '">' +
      KYC.escapeHtml(KYC.stateName(race.state)) + " &rsaquo;</a>";
    // The people first, then the markets: a reader came for who is running,
    // and 61% of House market blocks only show a 95-99% favourite. Beside
    // the people the markets are closed until opened, at every width and in
    // every view (TRUST-14): open on a desktop state page and in the map's
    // panel, closed on a phone and on a profile, the same prices read as a
    // verdict in some places and not others.
    var odds = KYC.odds ? KYC.odds.render(race, { compact: !opts.fullOdds,
                                                  collapsed: opts.collapsedOdds !== false }) : "";
    // Then what the race is fought with and over: each campaign's money,
    // the seat's last result, and the ballot side by side.
    var extra = moneyBlock(race, people, { open: opts.moneyOpen, lazy: !!opts.lazyOut,
                                          scope: opts.scope }) +
      lastTimeBlock(race, { lazy: !!opts.lazyOut, scope: opts.scope }) +
      compareBlock(race, people, { scope: opts.scope });
    var inner = [
      '<div class="race-head"><h3 class="race-title">',
      KYC.escapeHtml(title), link, "</h3>", raceBadges(race, { shared: (opts.fold || {}).shared }),
      '<button type="button" class="btn race-share" data-share-race="' + KYC.escapeAttr(race.id) +
        '" aria-label="' + KYC.escapeAttr("Copy link to " + race.label) + '">' +
        KYC.icon("share") + " Copy link</button>",
      "</div>",
      opts.lead ? '<p class="race-order race-lead">' + opts.lead + "</p>" : "",
      body,
      extra ? '<div class="race-extra">' + extra + "</div>" : "",
      odds,
    ].join("");
    if (!opts.fold) {
      return '<section class="race" id="' + KYC.escapeAttr("race-" + race.id) + '">' + inner + "</section>";
    }
    /* *opts.fold*: the race can fold to one row (raceRow) over today's
     * section, which stays in the page below it - hidden until found, so
     * the browser's find and the page's search still reach it. Drawn
     * open, the row hidden: the page folds it where it should. */
    var fold = opts.fold;
    return '<section class="race race-foldable" id="' + KYC.escapeAttr("race-" + race.id) +
      '" data-race="' + KYC.escapeAttr(race.id) + '">' + raceRow(race, split, fold) +
      '<div class="race-body" id="' + KYC.escapeAttr("race-body-" + race.id) + '">' + inner +
      '<p class="race-close-row" hidden><button type="button" class="btn race-close" data-race-close="' +
      KYC.escapeAttr(race.id) + '">' + KYC.icon("chevron", "race-close-icon") + " Close " +
      KYC.escapeHtml(fold.label) + "</button></p></div></section>";
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
    var parties = ((race && race.results) || {}).otherParties || {};
    var parts = [];
    if (u.none.length) {
      // Each with their party, as the ballot or the results give it: a
      // bare name beside a market line for "Republican party" left the
      // reader to guess which of two names it was.
      parts.push("Also on the November ballot, " + KYC.escapeHtml(KYC.ballotSource(race)) +
        ", with no FEC filing over $5,000 and so no profile here: " +
        u.none.map(function (n) {
          return KYC.escapeHtml(n) + (parties[n] ? " (" + KYC.escapeHtml(parties[n]) + ")" : "");
        }).join(", ") + ".");
    }
    u.maybe.forEach(function (m) {
      var who = KYC.byId(m.id);
      // Credited to whoever named them: Florida's certified list, not "the
      // results", named FL-13's Tony D'Arrigo.
      parts.push("Also named, " + KYC.escapeHtml(KYC.ballotSource(race)) + ": " +
        KYC.escapeHtml(m.name) + ", who may be " +
        KYC.escapeHtml(who ? who.name : "a candidate with a profile here") +
        " under another spelling; this site has not confirmed it.");
    });
    return parts.length ? '<p class="' + (cls || "race-note") + '">' + parts.join(" ") + "</p>" : "";
  }

  /* ------------------------------------------------- money in the race */

  /* Raised, spent and cash on hand for each person on the ballot, as bars
   * on one scale (VISUALS-20, PERSONA-11). The bars are neutral ink: the
   * party is in the name chip only, so the length reads as money and not as
   * a side. Each row carries its own through-date, because campaigns file
   * on different days (NC's Senate nominees: Jun 30 and Sep 30), and the
   * labels are rounded; the exact figure is the profile's. */
  var MONEY = [
    ["receipts", "Raised", "Raised, including loans and transfers (FEC)"],
    ["disbursements", "Spent", "Spent (FEC)"],
    ["cashOnHand", "Cash", "Cash on hand at the end of the period (FEC)"],
  ];

  /* A person in a race block, opening their profile; in their own dialog
   * (*self*: their ids, a member's filing for this seat among them) their
   * name alone, so no one is listed as a link to themselves (PROFILES-02). */
  function personButton(p, attr, self) {
    if (self && self[p.id]) return '<span class="money-self">' + KYC.escapeHtml(p.name) + "</span>";
    return '<button type="button" class="link-button" ' + (attr || "data-id") + '="' +
      KYC.escapeAttr(p.id) + '">' + KYC.escapeHtml(p.name) + "</button>";
  }

  function partyChip(p) {
    return '<span class="party-chip ' + KYC.partyClass(p) + '">' +
      KYC.escapeHtml(p.party) + "</span>";
  }

  /* What outside groups reported spending for and against a person, as
   * filed: each side's own total, never a net (kyc/outside.py). */
  var OUTSIDE_NOTE = "Independent expenditures: money spent by groups that are not the " +
    "campaign (super PACs, party committees, other PACs) to support or oppose this candidate, " +
    "as the FEC totals them by candidate. The FEC processes filings days to weeks after they " +
    "are made, sometimes longer, so the latest spending, reported in 24- and 48-hour reports, " +
    "is often not yet in these totals, and in a race spent on heavily near the election the " +
    "totals can be well below what has been spent. Each side is shown as filed; nothing is netted.";
  function outsideSpan(o, lead, opts) {
    var side = function (total, n, word) {
      return total ? KYC.moneyShort(total) + " " + word +
        (n ? " (" + n + (n === 1 ? " group" : " groups") + ")" : "") : "";
    };
    var parts = [side(o.support, o.supportCommittees, "supporting"),
                 side(o.oppose, o.opposeCommittees, "opposing")].filter(Boolean);
    return '<span class="money-outside' + (opts && opts.block ? " block" : "") + '" title="' +
      KYC.escapeAttr(OUTSIDE_NOTE) + '">' + KYC.escapeHtml(lead || "") +
      (lead ? "outside" : "Outside") + " groups spent " + KYC.escapeHtml(parts.join(" and ")) +
      " in 2025–26, in the filings the FEC had processed when read on " +
      KYC.escapeHtml(KYC.dateWords(o.asOf)) +
      // Said on the line, where a phone reader sees it (wave 2d review: a
      // title alone let the totals read as the race's whole scale).
      "; the latest spending may not be in them yet" +
      ' &middot; <a href="' + KYC.escapeAttr(o.url) +
      '" target="_blank" rel="noopener noreferrer">FEC</a></span>';
  }

  function chamberWord(p) {
    return /Senate/.test((p && p.chamber) || "") ? "Senate" : "House";
  }

  /* A member running for the other chamber has two candidacies, and the
   * FEC totals outside spending under each id apart (kyc/outside.py
   * elsewhere): on the member's own line it says whose candidacy it is, and
   * the campaign they are running carries it on a line of its own, never
   * added to its own figures. Andy Barr's $7.2 million under his House id
   * read as his Senate race's under a House candidacy he is not running. */
  function outsideLine(p, opts) {
    var o = p && p.outsideSpending;
    if (!o) return "";
    var lead = "";
    if (o.runningElsewhere) {
      var running = KYC.byId(o.runningElsewhere);
      lead = "Filed under their " + (o.candidacy || chamberWord(p)) + " candidacy, not the " +
        (running ? chamberWord(running) : "other") + " campaign they are running: ";
    }
    return outsideSpan(o, lead, opts);
  }

  function outsideOtherLine(p, opts) {
    var o = p && p.outsideSpendingOther;
    if (!o) return "";
    return outsideSpan(o, "Filed separately under their " + (o.candidacy || "other") +
      " candidacy, and not added in here: ", opts);
  }

  function moneyRow(p, max, attr, self) {
    var bars = "";
    var any = false;
    MONEY.forEach(function (spec) {
      var value = KYC.moneyAmount(p, spec[0]);
      if (value === null) return;
      any = true;
      var width = max > 0 ? Math.max(0, Math.min(100, 100 * value / max)) : 0;
      bars += '<span class="money-bar" title="' + KYC.escapeAttr(spec[2] + ": " + p[spec[0]]) + '">' +
        '<span class="money-label">' + KYC.escapeHtml(spec[1]) + "</span>" +
        '<span class="money-track" aria-hidden="true"><span class="money-fill" style="width:' +
        width.toFixed(1) + '%"></span></span>' +
        '<span class="money-value">' + KYC.escapeHtml(KYC.moneyShort(value)) + "</span></span>";
    });
    var through = p.financeAsOf ? "through " + KYC.dateWords(p.financeAsOf) : "";
    // The totals' own source, linked to the filing they are from: the only
    // "FEC" link in the row was the outside-spending one's.
    var fec = p.fecCandidateId
      ? '<a href="' + KYC.escapeAttr("https://www.fec.gov/data/candidate/" +
          encodeURIComponent(p.fecCandidateId) + "/") + '" target="_blank" ' +
        'rel="noopener noreferrer" title="' + KYC.escapeAttr("Candidate " + p.fecCandidateId +
          "'s filings at the Federal Election Commission") + '">FEC</a>'
      : "FEC";
    var body = any
      ? '<span class="money-bars">' + bars + "</span>" +
        '<span class="money-asof">' + fec + KYC.escapeHtml(through ? ", " + through : "") +
        "</span>"
      // No figure: the absence in its own words (rule 19), never a $0 bar.
      : '<span class="money-none">' + KYC.renderField(p, "receipts") + "</span>";
    return '<li class="money-row"><span class="money-who">' + personButton(p, attr, self) + " " +
      partyChip(p) + "</span>" + body + outsideLine(p) + outsideOtherLine(p) + "</li>";
  }

  /* The people a race's money block and comparison list: those on its
   * ballot, in the race's own order. */
  function ballotPeople(race, people) {
    return people.filter(function (p) { return !offBallot(p) && !elsewhere(race, p); });
  }

  function moneyBlock(race, people, opts) {
    opts = opts || {};
    var shown = ballotPeople(race, people);
    if (!shown.length) return "";
    return fold("race-money", "Money in the race", opts, (opts.scope || "race") + ":money:" + race.id,
      race.state, function () {
        var max = 0;
        shown.forEach(function (p) {
          MONEY.forEach(function (spec) {
            var v = KYC.moneyAmount(p, spec[0]);
            if (v !== null && v > max) max = v;
          });
        });
        var below = (((race.results || {}).belowThreshold) || []).map(function (b) {
          return KYC.escapeHtml(b.name);
        });
        return '<p class="race-note">Each campaign’s own totals as filed with the FEC, on one ' +
          "scale. Raised includes loans and transfers. Campaigns report through different " +
          "days; each row says which. Exact figures are on each profile.</p>" +
          '<ul class="money-rows">' + shown.map(function (p) {
            return moneyRow(p, max, opts.attr, opts.self);
          }).join("") + "</ul>" +
          (below.length ? '<p class="race-note">On the ballot with no FEC filing over $5,000: ' +
            below.join(", ") + ".</p>" : "");
      });
  }

  /* A race's fold: drawn now when it opens on arrival, else when the reader
   * opens it (fillFold). The grid's races view holds 475 races, and drawn
   * at once their money and last results nearly doubled its markup, which
   * GRID-14 had cut to 2.5 MB.
   *
   * A fold about the race's people (*state*, the race's) needs their whole
   * records: the grid and the map hold everyone's card only, and the money
   * and the ballot side by side are in the state's own file (rule 94),
   * loaded when the fold opens. Never drawn from the cards, where every
   * figure would read "No data". */
  var lazyFolds = {};

  function fold(cls, summary, opts, key, state, body) {
    var ready = !state || KYC.peopleFull(state);
    var eager = ready && (opts.open || !opts.lazy);
    if (!eager) lazyFolds[key] = { body: body, state: ready ? null : state };
    return '<details class="' + cls + '"' + (eager && opts.open ? " open" : "") +
      (eager ? "" : ' data-fold="' + KYC.escapeAttr(key) + '"') + "><summary>" +
      KYC.escapeHtml(summary) + '</summary><div class="fold-body">' + (eager ? body() : "") +
      "</div></details>";
  }

  function fillFold(details) {
    var entry = lazyFolds[details.getAttribute("data-fold")];
    var target = details.querySelector(".fold-body");
    if (!entry || !target || target.childElementCount) return;
    if (!entry.state || KYC.peopleFull(entry.state)) {
      target.innerHTML = entry.body();
      return;
    }
    target.innerHTML = '<p class="race-note" role="status">Loading ' +
      KYC.escapeHtml(KYC.stateName(entry.state)) + "&rsquo;s campaigns&hellip;</p>";
    KYC.loadPeople(entry.state).then(function (ok) {
      if (ok) {
        target.innerHTML = entry.body();
        return;
      }
      // Said, and asked again the next time the fold opens.
      target.innerHTML = '<p class="race-note kyc-absent" role="status">' +
        KYC.escapeHtml(KYC.peopleProblem() || "The campaigns\u2019 figures did not load. " +
          "Close this and open it again to retry.") + "</p>";
      var again = function () {
        if (details.open) return;
        details.removeEventListener("toggle", again);
        target.innerHTML = "";
      };
      details.addEventListener("toggle", again);
    });
  }

  /* ------------------------------------------------ compare the ballot */

  /* The people on a race's ballot side by side (GRID-17): party and
   * ballot line, offices held, money with its date, the campaign's own
   * platform headings with where they came from, and its site. No net
   * worth (rule 26); money only as filed (rule 61). */

  /* What was looked at, under a platform the comparison cannot show: a
   * member's official website is not a campaign's site (wave 2d review:
   * Ossoff's "Not listed on their official site" beside Collins's "No
   * data" read as Ossoff having no platform). */
  var MEMBER_SITE_ABSENCES = { not_listed: 1, see_site: 1, see_home: 1 };
  function platformLooked(p) {
    var q = (p.quality || {}).platforms;
    return MEMBER_SITE_ABSENCES[q]
      ? "This site read their official website, not a campaign site"
      : "Nothing recorded from a campaign site or article";
  }

  function compareCell(p, what) {
    if (what === "party") {
      // The FEC files a write-in's party as "Write-in": a way of running,
      // not a party, said as a status (wave 2d review).
      if (/^write-?in$/i.test(String(p.party || "").trim())) {
        return '<span class="faint">Write-in candidate; no party on file</span>';
      }
      // ballotLineSuffix is markup already escaped: " – Working Families line".
      var line = KYC.ballotLineSuffix(p);
      return partyChip(p) + (line
        ? ' <span class="faint">' + line.replace(/^ – /, "") + "</span>" : "");
    }
    if (what === "held") return KYC.officesHeldShort(p.politicalHistory, 4);
    if (what === "money") {
      var lines = MONEY.map(function (spec) {
        var v = KYC.moneyAmount(p, spec[0]);
        return v === null ? "" : "<li>" + KYC.escapeHtml(spec[1]) + " " +
          KYC.escapeHtml(KYC.moneyShort(v)) + "</li>";
      }).filter(Boolean);
      if (!lines.length) return KYC.renderField(p, "receipts");
      return '<ul class="compare-list">' + lines.join("") + "</ul>" +
        '<span class="faint">' + KYC.escapeHtml("FEC" + (p.financeAsOf ? ", through " +
          KYC.dateWords(p.financeAsOf) : "")) + "</span>" + outsideLine(p, { block: true }) +
        outsideOtherLine(p, { block: true });
    }
    if (what === "platform") {
      var plat = KYC.platformItems(p);
      if (!plat) {
        return KYC.renderField(p, "platforms") + '<span class="faint compare-source">' +
          KYC.escapeHtml(platformLooked(p)) + "</span>";
      }
      return '<ul class="compare-list">' + plat.items.slice(0, 8).map(function (x) {
        return "<li>" + KYC.escapeHtml(x) + "</li>";
      }).join("") + (plat.items.length > 8 ? '<li class="faint">and ' + (plat.items.length - 8) +
        " more</li>" : "") + "</ul>" + '<span class="faint compare-source">' +
        KYC.escapeHtml(platformFrom(p)) +
        "</span>";
    }
    if (what === "site") {
      return p.campaignSite
        ? '<a href="' + KYC.escapeAttr(p.campaignSite) + '" target="_blank" ' +
          'rel="noopener noreferrer">' + KYC.escapeHtml(String(p.campaignSite)
            .replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "")) + "</a>"
        : '<span class="kyc-absent">None linked</span>';
    }
    return "";
  }

  /* Where each cell's platform came from, in words under it. The row was
   * headed "in the campaign's words" over sitting members' platforms that
   * are this site's own roster summaries (rules 38, 61); a badge reading
   * "Campaign site" also sat right above the row of that name. */
  var PLATFORM_FROM = {
    "campaign-site": "Headings from the campaign’s own site",
    // A member's, from their official website (kyc/members.py, rule 86):
    // the office's site, not the campaign's, and said as the dialog says
    // it - a home page's featured issues may not be every issue.
    "official-site": "The issues their official website lists",
    "official-featured": "The issues their official website’s home page features",
    "wikipedia": "From the candidate’s Wikipedia article",
    "election-page": "From Wikipedia’s 2026 election page",
    roster: "This site’s roster summary, not the campaign’s words",
  };

  function platformFrom(p) {
    var source = (p.fieldSources || {}).platforms;
    if (source === "official-site" && p.platformFeatured) return PLATFORM_FROM["official-featured"];
    return PLATFORM_FROM[source] || PLATFORM_FROM.roster;
  }

  var COMPARE_ROWS = [
    ["party", "Party"],
    ["held", "Public offices held"],
    ["money", "Campaign money"],
    ["platform", "Platform"],
    ["site", "Campaign site"],
  ];

  /* A table side by side where there is room; on a phone a card per
   * person, the same cells in the same order (wave 2d review: a five-way
   * race showed 1.3 columns per screen, rows tall with blank cells, the
   * two nominees behind two write-ins). CSS shows one of the two. */
  function compareTable(race, people, attr, self) {
    var shown = ballotPeople(race, people);
    var cells = shown.map(function (p) {
      return COMPARE_ROWS.map(function (row) { return compareCell(p, row[0]); });
    });
    return '<div class="compare-scroll"><table class="compare-table"><thead><tr>' +
      '<th scope="col"><span class="sr-only">Compared</span></th>' +
      shown.map(function (p) {
        return '<th scope="col">' + personButton(p, attr, self) + "</th>";
      }).join("") + "</tr></thead><tbody>" +
      COMPARE_ROWS.map(function (row, j) {
        return '<tr><th scope="row">' + KYC.escapeHtml(row[1]) + "</th>" +
          shown.map(function (p, i) { return "<td>" + cells[i][j] + "</td>"; }).join("") +
          "</tr>";
      }).join("") + "</tbody></table></div>" +
      '<ul class="compare-cards">' + shown.map(function (p, i) {
        return '<li class="compare-card"><p class="compare-card-name">' + personButton(p, attr, self) +
          '</p><dl class="compare-card-rows">' + COMPARE_ROWS.map(function (row, j) {
            return "<dt>" + KYC.escapeHtml(row[1]) + "</dt><dd>" + cells[i][j] + "</dd>";
          }).join("") + "</dl></li>";
      }).join("") + "</ul>" +
      '<p class="race-note">Offices: only those two sources agree on. Platform: each says ' +
      "where it came from. A sitting member’s is the list of issues their official website " +
      "gives, a challenger’s the headings of their campaign’s site: not the same kind of page, " +
      "and a member’s campaign site is not read for it. No net worth: a disclosure reports " +
      "assets in bands, not a figure.</p>";
  }

  function compareBlock(race, people, opts) {
    opts = opts || {};
    if (ballotPeople(race, people).length < 2) return "";
    // Always drawn when opened: a table per race is markup no one asked for.
    return fold("race-compare", "Compare the ballot", { lazy: true },
      (opts.scope || "race") + ":compare:" + race.id, race.state,
      function () { return compareTable(race, people, opts.attr, opts.self); });
  }

  // One listener for every page that draws a race: a details element's
  // toggle does not bubble, so it is caught on the way down.
  if (global.document && global.document.addEventListener) {
    global.document.addEventListener("toggle", function (event) {
      var t = event.target;
      if (t && t.matches && t.matches("details[data-fold]") && t.open) fillFold(t);
    }, true);
    // A race's "Copy link": its share page (rule 96), delegated (rule 13).
    global.document.addEventListener("click", function (event) {
      var button = event.target && event.target.closest && event.target.closest("[data-share-race]");
      if (!button) return;
      var id = button.getAttribute("data-share-race");
      var race = KYC.races().filter(function (r) { return r.id === id; })[0];
      KYC.shareLink(button, KYC.shareUrl("race", id), race ? race.label : "");
    });
  }

  /* ---------------------------------------------------------- last time */

  /* The seat's last election before 2026's (kyc/seat_history.py): who
   * won, with what share and margin, from the Clerk of the House's official
   * statistics, checked against a second compilation. A district redrawn
   * for 2026 says so and shows no 2024 figure (rule 90). A seat filled
   * since by a special election says its figure is the last *regular*
   * election's and who took the seat after it: "the last election to this
   * district" over Gerald Connolly's 2024 result sat beside the member who
   * won VA-11's 2025 special. From the day after Election Day the fold is
   * "Before 2026", not "Last time", which would then be 2026's own (rule
   * 63). *now* is for tests. */
  function pct(v) {
    return (Math.round(v * 10) / 10).toFixed(1) + "%";
  }

  function lastTimeLabel(last, now) {
    var past = KYC.electionStatus(undefined, now).phase === "post-election";
    var special = last.seatedSince && last.seatedSince.how !== "appointment";
    if (special) return past ? "Before 2026, the last regular election" : "Last regular election";
    return past ? "Before 2026" : "Last time";
  }

  function lastTimeSummary(race, last, now) {
    var label = lastTimeLabel(last, now);
    if (last.redrawn) return label + ": not shown (district redrawn for 2026)";
    if (last.withheld) return label + ": not shown";
    var won = last.candidates[0];
    label += " (" + last.year + "): ";
    if (last.kind === "unopposed") return label + won.name + ", unopposed";
    if (!last.candidates[1]) return label + won.name + " won";
    // A ranked-choice count's first choices are not its result: Nick
    // Begich "won by 2.0 points" was his lead in first choices.
    return label + won.name + (last.rankedChoice === "first-choices"
      ? " led first choices by " : " won by ") + last.margin.toFixed(1) + " points";
  }

  /* Who took the seat after the counted election, in words that stay true
   * on any day: "took the seat on", never "holds". */
  function seatedSinceWords(last) {
    var s = last.seatedSince;
    if (!s) return "";
    return " " + s.name + " took the seat on " + KYC.dateWords(s.since) +
      (s.how === "appointment" ? ", by appointment."
        : ", after a special election whose result this site does not show.");
  }

  function lastTimeBody(race, last) {
    var where = race.chamber === "Senate" ? "this seat" : "this district";
    if (last.redrawn) {
      var plan = (KYC.meta().districtMaps || {})[race.state];
      var link = plan ? ' <a href="' + KYC.escapeAttr(KYC.siteRoot() + plan.page + "#/?d=" +
        (race.district || 0)) + '">See where its area came from &rsaquo;</a>' : "";
      // Said of every redrawn district alike: many of Florida's and North
      // Carolina's new districts are nearly the old ones, so "fought by
      // other voters" was not true of them.
      return '<p class="race-note">' + KYC.escapeHtml(KYC.stateName(race.state)) +
        " redrew its House districts for 2026. The " + last.year + " result was counted on " +
        "the old lines, which this site does not carry over to the new ones." + link + "</p>";
    }
    if (last.withheld) {
      return '<p class="race-note">The ' + last.year + " result is not shown: " +
        (last.withheld === "disagree"
          ? "the Clerk of the House’s statistics and the compilation this site checks them " +
            "against disagree about it."
          : "the compilation this site checks the Clerk of the House’s statistics against " +
            "does not confirm it.") + "</p>";
    }
    var day = KYC.dateWords(last.date);
    var lead;
    if (last.kind === "runoff") {
      lead = "Decided in the runoff on " + day + ", between the two the November vote left.";
    } else if (last.kind === "rcv-final") {
      lead = "The final round of the ranked-choice count, " + day + ".";
    } else if (last.kind === "unopposed") {
      lead = "Election of " + day + ".";
    } else {
      lead = "Election of " + day + (race.chamber === "Senate" && last.term === "unexpired"
        ? ", a special election for the rest of the term" : "") + ".";
    }
    var rows;
    if (last.kind === "unopposed") {
      rows = '<p class="race-note">' + KYC.escapeHtml(last.candidates[0].name + " (" +
        last.candidates[0].party + ") was unopposed. " + (last.note || "")) + "</p>";
    } else {
      rows = '<table class="last-table"><tbody>' + last.candidates.map(function (c, i) {
        return "<tr><th scope=\"row\">" + KYC.escapeHtml(c.name) + ' <span class="faint">' +
          KYC.escapeHtml(c.party) + "</span>" + (i === 0 ? ' <span class="badge badge-neutral">Won</span>' : "") +
          "</th><td>" + pct(c.share) + "</td><td class=\"faint\">" +
          c.votes.toLocaleString("en-US") + " votes</td></tr>";
      }).join("") + (last.others ? '<tr><th scope="row">Everyone else</th><td>' +
        pct(last.othersShare) + '</td><td class="faint">' + last.others.toLocaleString("en-US") +
        " votes</td></tr>" : "") + "</tbody></table>" +
        '<p class="race-note">' + (last.candidates[1]
          ? "Margin: " + last.margin.toFixed(1) + " points. "
          : "No other candidate was named on the ballot. ") +
        "Shares are of the " + last.total.toLocaleString("en-US") +
        " votes cast for a candidate; blank and spoiled ballots are not counted." +
        (last.rankedChoice === "first-choices" ? " " + KYC.stateName(race.state) +
          " counts ranked choices: these are first choices, as the Clerk lists them." : "") +
        "</p>";
    }
    // The sources, once for the page (kycBuildMeta.lastElectionSources).
    var sources = KYC.meta().lastElectionSources || {};
    var source = sources[String(last.year)] || {};
    var by = last.checkedBy === "mit" ? sources.mit
      : last.checkedBy ? { title: "Wikipedia’s “" + last.checkedBy + "”",
                           url: "https://en.wikipedia.org/wiki/" +
                             encodeURIComponent(last.checkedBy.replace(/ /g, "_")) }
      : null;
    var checked = by && by.url
      ? " The winner and runner-up checked against " + '<a href="' +
        KYC.escapeAttr(by.url) + '" target="_blank" rel="noopener noreferrer">' +
        KYC.escapeHtml(by.title) + "</a>."
      : "";
    var special = last.seatedSince && last.seatedSince.how !== "appointment";
    return '<p class="race-note">' + KYC.escapeHtml(lead) + " " +
      KYC.escapeHtml("The last " + (special ? "regular " : "") + "election to " + where +
        " before the 2026 election." + seatedSinceWords(last)) + "</p>" + rows +
      '<p class="race-note race-results">Counts: <a href="' + KYC.escapeAttr(source.url || "") +
      '" target="_blank" rel="noopener noreferrer">' + KYC.escapeHtml(source.title || "") +
      "</a>, compiled from each state’s certified results." + checked + "</p>";
  }

  function lastTimeBlock(race, opts) {
    opts = opts || {};
    var last = race && race.lastElection;
    if (!last) return "";
    return fold("race-last", lastTimeSummary(race, last, opts.now), opts,
      (opts.scope || "race") + ":last:" + race.id, null,
      function () { return lastTimeBody(race, last); });
  }

  KYC.cards = {
    moneyBlock: moneyBlock,
    compareBlock: compareBlock,
    fillFold: fillFold,
    lastTimeBlock: lastTimeBlock,
    outsideLine: outsideLine,
    outsideOtherLine: outsideOtherLine,
    outsideNote: OUTSIDE_NOTE,
    unprofiledNames: unprofiledNames,
    unprofiledNote: unprofiledNote,
    orderNote: orderNote,
    offBallot: offBallot,
    raceBadge: raceBadge,
    statusBadge: statusBadge,
    card: card,
    contactOf: contactOf,
    raceBadges: raceBadges,
    raceBadgeItems: raceBadgeItems,
    headBadgeHtml: headBadgeHtml,
    sharedBadges: sharedBadges,
    holderWords: holderWords,
    rowPeople: rowPeople,
    raceRow: raceRow,
    raceSection: raceSection,
    racePeople: racePeople,
    heldByLine: heldByLine,
    fillOut: fillOut,
    legend: legend,
  };
})(window);
