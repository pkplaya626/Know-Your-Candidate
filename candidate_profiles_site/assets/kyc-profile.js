/* The profile dialog, shared by the grid and the map.
 *
 * There used to be two of these - roughly 200 lines of near-identical markup
 * and rendering code copy-pasted into both pages - and they had drifted. The
 * grid's copy routed every field through KYC.renderField; the map's copy
 * still did `element.textContent = item.net_worth`, so a reader who opened a
 * senator from the map was shown the literal sentence
 *
 *     N/A (No net worth disclosure provided in sources)
 *
 * as though it were a research finding. The map's copy also never called the
 * dialog helper, so it had no focus trap and its Escape handler leaked a
 * document listener on every open.
 *
 * The dialog builds its own DOM here rather than being pasted into both
 * pages, which is what makes a second copy impossible.
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;

  var PARTY_LABEL_BG = {
    d: "var(--party-d)", r: "var(--party-r)",
    i: "var(--party-i)", vacant: "var(--text-muted)",
  };

  var dialog = null;
  var root = null;
  var current = null;
  // The page's own title, put back when the profile closes.
  var baseTitle = null;

  /* ---------------------------------------------------------------- markup */

  function template() {
    var wrap = doc.createElement("div");
    wrap.className = "modal";
    wrap.id = "profileModal";
    wrap.hidden = true;
    wrap.setAttribute("role", "dialog");
    wrap.setAttribute("aria-modal", "true");
    wrap.setAttribute("aria-labelledby", "profileModalName");

    wrap.innerHTML = [
      // Clicking the backdrop closes; it is not a stop for the keyboard or
      // a screen reader, which landed on it first ("Close profile, button").
      '<button class="modal-scrim" data-close tabindex="-1" aria-hidden="true"></button>',
      '<div class="modal-dialog">',
      '  <button class="btn-icon modal-close" data-close aria-label="Close profile">',
      KYC.icon("x"),
      "  </button>",
      '  <header class="modal-header">',
      '    <div class="modal-portrait">',
      '      <img id="profileModalPhoto" data-photo-idx="0" src="" alt="">',
      '      <span class="party-tag" id="profileModalParty"></span>',
      "    </div>",
      '    <div class="modal-identity">',
      '      <span class="badge badge-neutral" id="profileModalChamber"></span>',
      '      <h2 class="modal-name" id="profileModalName"></h2>',
      '      <p class="modal-aka" id="profileModalFecName" hidden></p>',
      '      <p class="modal-meta">',
      '        <span>' + KYC.icon("pin") +
      '          <span id="profileModalRegionLabel">Represents</span> <strong id="profileModalRegion"></strong>' +
      '          <a id="profileModalStateLink" class="state-link" href="#"></a></span>',
      '        <span id="profileModalTermWrap">' + KYC.icon("calendar") +
      '          Term <strong id="profileModalTerm"></strong></span>',
      '        <span id="profileModalCrossLink" hidden></span>',
      "      </p>",
      '      <p class="modal-meta" id="profileModalStatus" hidden></p>',
      // Whose photograph the portrait is, and on what licence (rule 87).
      '      <p class="modal-credit" id="profileModalPhotoCredit" hidden></p>',
      "    </div>",
      "  </header>",
      '  <div class="modal-body scroll-y">',
      '    <div class="modal-column">',
      '      <section class="panel">',
      '        <h3 class="panel-head">' + KYC.icon("user") + " Biography</h3>",
      '        <div class="field-grid">',
      '          <div class="field"><span class="field-label">Age / born</span>',
      '            <span class="field-value" id="profileModalAge"></span></div>',
      '          <div class="field" id="profileModalDisclosureField"><span class="field-label">Financial disclosure</span>',
      '            <span class="field-value" id="profileModalDisclosure"></span></div>',
      '          <div class="field span-2"><span class="field-label">Education</span>',
      '            <span class="field-value subtle" id="profileModalEducation"></span></div>',
      '          <div class="field span-2"><span class="field-label">Previous careers</span>',
      '            <span class="field-value subtle" id="profileModalCareers"></span></div>',
      "        </div>",
      "      </section>",
      '      <section class="panel">',
      '        <h3 class="panel-head">' + KYC.icon("landmark") + " Public offices held</h3>",
      '        <div id="profileModalHeld"></div>',
      "      </section>",
      '      <section class="panel" id="profileModalContactPanel" hidden>',
      '        <h3 class="panel-head">' + KYC.icon("link") + " Contact &amp; links</h3>",
      '        <div id="profileModalContact"></div>',
      "      </section>",
      '      <section class="panel panel-accent">',
      '        <h3 class="panel-head">' + KYC.icon("scroll") + " Platform &amp; priorities</h3>",
      '        <div class="scroll-y scroll-box" id="profileModalPlatform"></div>',
      "      </section>",
      "    </div>",
      '    <div class="modal-column">',
      '      <section class="panel">',
      '        <h3 class="panel-head">' + KYC.icon("dollar") + " Campaign finance</h3>",
      '        <div class="money-grid">',
      '          <div class="money-tile in"><span class="label">Raised</span>',
      '            <span class="amount" id="profileModalReceipts"></span></div>',
      '          <div class="money-tile out"><span class="label">Spent</span>',
      '            <span class="amount" id="profileModalSpent"></span></div>',
      "        </div>",
      '        <div class="money-grid" id="profileModalCashWrap" hidden>',
      '          <div class="money-tile"><span class="label">Cash on hand</span>',
      '            <span class="amount" id="profileModalCash"></span></div>',
      "        </div>",
      '        <p class="finance-period" id="profileModalFinancePeriod" hidden></p>',
      '        <p class="finance-period" id="profileModalOtherCampaign" hidden></p>',
      '        <span class="field-label">Funding sources</span>',
      '        <p class="note-box" id="profileModalFunding" style="margin-top:6px"></p>',
      // Groups that are not the campaign, for and against (kyc/outside.py).
      '        <div class="outside-panel" id="profileModalOutside" hidden></div>',
      "      </section>",
      '      <section class="panel">',
      '        <h3 class="panel-head">' + KYC.icon("chart") + " Voting record</h3>",
      '        <div class="note-box" id="profileModalVoting"></div>',
      "      </section>",
      '      <section class="panel">',
      '        <h3 class="panel-head">' + KYC.icon("layers") + " Committees</h3>",
      '        <div class="scroll-y scroll-box list-rows" id="profileModalCommittees"></div>',
      "      </section>",
      '      <section class="panel" id="profileModalRacePanel" hidden>',
      '        <h3 class="panel-head">' + KYC.icon("flag") + ' <span id="profileModalRaceTitle">In this race</span></h3>',
      '        <div class="list-rows race-mates" id="profileModalRace"></div>',
      '        <div id="profileModalRaceOdds"></div>',
      "      </section>",
      "    </div>",
      "  </div>",
      '  <footer class="modal-footer">',
      '    <span class="modal-footer-notes"><span id="profileModalSource"></span>',
      // A named person who is mislabelled, or a reader who sees it, needs a
      // way to say so (TRUST-03): GitHub's issue form, filled in with this
      // profile and the address (KYC.reportUrl, aimed as it is followed).
      '    <a class="report-link" id="profileModalReport" data-report target="_blank"' +
      ' rel="noopener noreferrer" href="' + KYC.escapeAttr(KYC.reportUrl()) + '">' +
      KYC.icon("flag") + " Report a problem with this profile</a></span>",
      '    <span class="modal-footer-actions">',
      '      <button type="button" class="btn" id="profileModalCopy">' +
      KYC.icon("share") + " Copy link</button>",
      '      <button type="button" class="btn" data-close>Close</button>',
      "    </span>",
      "  </footer>",
      "</div>",
    ].join("");
    // The credit follows the photograph shown: a fallback that loads in
    // place of the first is another photograph, credited by its host.
    var photo = wrap.querySelector("#profileModalPhoto");
    photo.addEventListener("load", showPhotoCredit);
    photo.addEventListener("error", showPhotoCredit);
    return wrap;
  }

  /** Credit the photograph the dialog's portrait shows now, or hide the
   *  line for the silhouette. */
  function showPhotoCredit() {
    var photo = el("profileModalPhoto");
    var line = el("profileModalPhotoCredit");
    if (!photo || !line) return;
    var html = KYC.photoCreditHtml(
      KYC.shownPhotoCredit(photo, KYC.byId(photo.getAttribute("data-profile"))));
    line.innerHTML = html;
    line.hidden = !html;
  }

  function el(id) {
    return doc.getElementById(id);
  }

  /* -------------------------------------------------------------- sections */

  function outLink(url, label) {
    return '<a href="' + KYC.escapeAttr(url) + '" target="_blank" rel="noopener noreferrer">' +
      KYC.escapeHtml(label) + "</a>";
  }

  /** Platform text arrives as prose, a comma list, or a Python-style list
   *  literal - or, for a filed candidate, as the headings of their campaign's
   *  issues page, joined with "; " by kyc/enrich.py. Whatever the shape,
   *  every fragment is escaped, and what came from a campaign says so. */
  function renderPlatform(item) {
    var target = el("profileModalPlatform");
    var fromSite = (item.fieldSources || {}).platforms === "campaign-site";
    var html = "";

    // The campaign's own one-line description of itself, quoted, never
    // paraphrased.
    if (item.campaignQuote) {
      html += '<blockquote class="campaign-quote"><p>“' +
        KYC.escapeHtml(item.campaignQuote) + "”</p><footer>The campaign’s own " +
        "description, from " +
        (item.campaignSite ? outLink(item.campaignSite, "its website") : "its website") +
        "</footer></blockquote>";
    }

    // One reading of the field for the dialog and the race's comparison
    // table (KYC.platformItems).
    var platform = KYC.platformItems(item);
    if (platform) {
      var text = platform.text;
      var parts = platform.items;

      if (parts.length > 1) {
        html +=
          '<ul class="bullets">' +
          parts.map(function (p) { return "<li>" + KYC.escapeHtml(p) + "</li>"; }).join("") +
          "</ul>";
      } else {
        html += '<p class="note-box">' + KYC.escapeHtml(text) + "</p>";
      }
      if (fromSite) {
        html += '<p class="field-credit">' + KYC.sourceBadge(item, "platforms").trim() +
          " The headings of the campaign’s issues page" +
          (item.campaignIssuesUrl ? ": " + outLink(item.campaignIssuesUrl, "read it in full") : "") +
          "</p>";
      }
    } else if (!item.campaignQuote) {
      html += KYC.renderField(item, "platforms");
    }

    if (!fromSite && item.campaignIssuesUrl) {
      html += '<p class="field-credit">' +
        outLink(item.campaignIssuesUrl, "The campaign’s issues page") + "</p>";
    }
    target.innerHTML = html;
  }

  /** DW-NOMINATE renders as a position on a scale. The string also carries a
   *  descriptive label and a party-loyalty estimate, both of which are
   *  parsed out rather than shown as raw text. */
  function renderVoting(item) {
    var target = el("profileModalVoting");
    if (!KYC.hasValue(item, "voting_alignment")) {
      target.innerHTML =
        '<span class="kyc-absent">No congressional voting record ' +
        (item.isCandidate ? "(not a sitting member)" : "on file") + "</span>";
      return;
    }

    var text = String(item.voting_alignment);
    var score = text.match(/DW-NOMINATE:\s*([+-]?\d+(?:\.\d+)?)/i);
    if (!score) {
      target.innerHTML = KYC.renderField(item, "voting_alignment");
      return;
    }

    var value = parseFloat(score[1]);
    var pct = Math.max(0, Math.min(100, ((value + 1) / 2) * 100));
    // "(right of centre; 119th Congress)": where on the scale, in its own
    // words - never a party's name, or an independent read as one - and the
    // Congress whose votes it scores. Not drawn in a party's colour either.
    var inner = ((text.match(/\(([^)]+)\)/) || [])[1] || "").split(";");
    var label = inner[0].trim();
    var congress = (inner[1] || "").trim();

    target.innerHTML = [
      '<div class="ideology">',
      '  <div class="ideology-head">',
      '    <span class="ideology-score">',
      (value > 0 ? "+" : "") + value.toFixed(2),
      label ? '<span class="label">' + KYC.escapeHtml(label) + "</span>" : "",
      "    </span>",
      "  </div>",
      '  <div class="ideology-track" role="img" aria-label="Left-right score ' +
      KYC.escapeAttr(value.toFixed(2)) + ' on a scale from -1 (left) to +1 (right)">',
      '    <span class="ideology-marker" style="left:' + pct.toFixed(2) + '%"></span>',
      "  </div>",
      '  <div class="ideology-axis"><span>-1.0 left</span>' +
      "<span>centre</span><span>right +1.0</span></div>",
      // In plain words (TRUST-17): the method's name stays, after what it is.
      '  <p class="held-source">A left-right score of this member\u2019s roll-call votes' +
      (congress ? " in the " + KYC.escapeHtml(congress) : "") +
      ', from <a href="https://voteview.com/" target="_blank" rel="noopener noreferrer">' +
      "Voteview</a> (its DW-NOMINATE method). It places votes on a scale; it is not a " +
      "party label.</p>",
      "</div>",
    ].join("");
  }

  /* The party and chamber posts congress-legislators records for a sitting
   * member's bioguide id (profile.leadership): the guide defined the
   * Speaker and the floor leaders and the site never named them. Only
   * while they sit (rule 68). */
  function renderLeadership(item) {
    var posts = KYC.seated(item) ? (item.leadership || []) : [];
    if (!posts.length) return;
    el("profileModalCommittees").insertAdjacentHTML("afterbegin",
      '<div class="leadership-posts"><span class="dot"></span><span>Leadership: ' +
      posts.map(function (title) {
        return '<span class="badge badge-accent">' + KYC.escapeHtml(title) + "</span>";
      }).join(" ") + "</span></div>");
  }

  function renderCommittees(item) {
    var target = el("profileModalCommittees");
    var text = String(item.committees || "").trim();

    /* The committee rosters carry rank and title; the roster column was
     * typed by hand. When the structured list exists it is rendered as a
     * hierarchy: each full committee with the member's subcommittees under
     * it, and any chair or ranking-member title called out. */
    var table = KYC.meta().committees || {};
    var seats = (item.committeeList || []).map(function (seat) {
      var info = table[seat.code] || {};
      return { code: seat.code, title: seat.title, name: info.name || seat.code,
               url: info.url, parent: info.parent };
    });
    if (seats.length) {
      var full = seats.filter(function (x) { return !x.parent; });
      var subs = seats.filter(function (x) { return x.parent; });
      target.innerHTML = full.map(function (seat) {
        var under = subs.filter(function (x) { return x.parent === seat.code; });
        return '<div class="committee">' +
          '<span class="dot"></span><span>' +
          (seat.url
            ? '<a href="' + KYC.escapeAttr(seat.url) + '" target="_blank" rel="noopener noreferrer">' +
              KYC.escapeHtml(seat.name) + "</a>"
            : KYC.escapeHtml(seat.name)) +
          (seat.title ? ' <span class="badge badge-accent">' + KYC.escapeHtml(seat.title) + "</span>" : "") +
          (under.length
            ? '<span class="committee-subs">' + under.map(function (x) {
                return KYC.escapeHtml(x.name) +
                  (x.title ? " (" + KYC.escapeHtml(x.title) + ")" : "");
              }).join(" &middot; ") + "</span>"
            : "") +
          "</span></div>";
      }).join("");
      return;
    }

    if (item.committeesPending) {
      // A new Congress's rosters are published some weeks after it sits.
      target.innerHTML = '<span class="kyc-absent">Committee assignments for the ' +
        KYC.escapeHtml(KYC.ordinal(item.committeesPending)) +
        " Congress have not been published yet</span>";
      return;
    }
    if (!KYC.hasValue(item, "committees") || !text || text === "None" ||
        text === "None (Candidate)") {
      target.innerHTML =
        '<span class="kyc-absent">No committee assignments' +
        (!KYC.seated(item) ? " (not a sitting member)" : "") + "</span>";
      return;
    }
    target.innerHTML = text
      .split(/;\s*/)
      .filter(Boolean)
      .map(function (name) {
        return '<div><span class="dot"></span><span>' +
          KYC.escapeHtml(name) + "</span></div>";
      })
      .join("");
  }

  /* Who else is in this person's 2026 race - the way a video page lists what
   * to watch next. A reader who opened a member sees their challengers one
   * click away; a reader who opened a challenger sees the incumbent. */

  function renderRace(item) {
    var panel = el("profileModalRacePanel");
    var target = el("profileModalRace");
    var raceId = item.contestRaceId || item.raceId;
    var race = null;
    (global.kycRaces || []).some(function (r) {
      if (r.id === raceId) { race = r; return true; }
      return false;
    });
    if (!race) {
      panel.hidden = true;
      target.innerHTML = "";
      el("profileModalRaceOdds").innerHTML = "";
      return;
    }
    /* Never the person themselves under another profile: a member's own
     * filing for this seat (alsoRunningId), or, on that filing, the member
     * it belongs to (incumbentId). Kevin Hern's Senate race listed "Kevin
     * Hern, On the ballot" as his own opponent (PROFILES-02). In the race's
     * own order - the seat's holder, then by surname (TRUST-15). */
    var self = {};
    self[item.id] = true;
    if (item.alsoRunningId) self[item.alsoRunningId] = true;
    if (item.incumbentId) self[item.incumbentId] = true;
    var others = race.incumbentIds.concat(race.candidateIds)
      .filter(function (id) { return !self[id]; })
      .map(KYC.byId).filter(function (p) { return p && !self[p.id]; });
    /* A member who holds this seat and is contesting another - a redrawn
     * district's new number, the other chamber - has a status about that
     * other race. Read as this race's, Kevin Kiley was "On the ballot" in
     * CA-3, which he holds and is not running for, and Al Green was
     * "Lost primary" in TX-9, though he lost TX-18's. Said as where they
     * went, and never folded under "no longer in this race". */
    var elsewhere = function (p) {
      return !p.isCandidate && !!p.contestRaceId && p.contestRaceId !== race.id;
    };
    var out = others.filter(function (p) {
      return !elsewhere(p) && KYC.cards && KYC.cards.offBallot(p);
    });
    var shown = others.filter(function (p) {
      return elsewhere(p) || !(KYC.cards && KYC.cards.offBallot(p));
    });
    el("profileModalRaceTitle").textContent = race.label;
    // The markets on this race, compactly, after the people in it.
    el("profileModalRaceOdds").innerHTML = KYC.odds ? KYC.odds.render(race, { compact: true }) : "";
    var row = function (p) {
      var role = KYC.seated(p) ? '<span class="badge badge-neutral">Member</span> '
        : p.formerMember ? '<span class="badge badge-neutral" title="' +
          KYC.escapeAttr(KYC.formerText(p)) + '">Former member</span> ' : "";
      // The words every view uses for this person (KYC.standing): a sitting
      // member's "Not running for re-election", a filer the results do not
      // settle, as their card and the map say it.
      var spec = KYC.standing(p, "mate");
      var status = spec
        ? '<span class="badge ' + spec.cls + '" title="' + KYC.escapeAttr(spec.title) + '">' +
          KYC.escapeHtml(spec.label) + KYC.ballotLineSuffix(p) + "</span>"
        : "";
      if (elsewhere(p)) {
        var there = KYC.raceStatusOf(p, "mate");
        var line = KYC.contestLine(p);
        status = '<span class="badge ' + line.cls + '" title="' + KYC.escapeAttr(
          "Holds this seat. " + line.title + (there ? " " + there.title : "")) + '">' +
          KYC.escapeHtml(line.label) +
          (there ? " &middot; " + KYC.escapeHtml(there.label) : "") + "</span>";
      }
      return '<button type="button" class="race-mate" data-goto="' + KYC.escapeAttr(p.id) + '">' +
        '<img ' + KYC.portraitAttrs(p, "36px") + ' alt="" loading="lazy" ' +
        'data-photo-idx="0" data-profile="' + KYC.escapeAttr(p.id) + '">' +
        '<span class="race-mate-body"><span class="race-mate-name">' + KYC.escapeHtml(p.name) +
        '</span><span class="race-mate-meta"><span class="' + KYC.partyClass(p) + '">' +
        KYC.escapeHtml(p.party) + "</span> " + role + status + "</span></span></button>";
    };
    var html = shown.map(row).join("");
    if (shown.length > 1) {
      html += '<p class="race-note race-order">' + KYC.escapeHtml(KYC.raceOrderNote(shown, race)) +
        "</p>";
    }
    if (out.length) {
      html += '<details class="race-out"><summary>' + out.length +
        " no longer in this race</summary>" + out.map(row).join("") + "</details>";
    }
    /* People the results page puts on the November ballot with no FEC filing
     * over $5,000 have no profile, so no row - but leaving them out made a
     * member with a named November opponent read as unopposed. */
    var res = race.results || null;
    var unfiled = res && res.otherNominees && res.otherNominees.length ? res.otherNominees : [];
    if (unfiled.length) html += KYC.cards.unprofiledNote(race);
    if (!others.length && !unfiled.length) html = aloneNote(race);
    /* Where the statuses in this dialog were read: "Lost the 2026 primary"
     * about a named person, with the page that says so (TRUST-06), as the
     * race's card on a state page links it. */
    var source = KYC.resultsSourceHtml(race);
    if (source) html += '<p class="race-note race-results">' + source + "</p>";
    // What the race is fought with and over, as the race's own section
    // shows it (KYC.cards), with this person among the rest.
    var everyone = race.incumbentIds.concat(race.candidateIds).map(KYC.byId).filter(Boolean);
    html += KYC.cards.moneyBlock(race, everyone, { open: true, attr: "data-goto", self: self }) +
      KYC.cards.lastTimeBlock(race) +
      KYC.cards.compareBlock(race, everyone, { attr: "data-goto", scope: "dialog", self: self });
    panel.hidden = false;
    target.innerHTML = redrawnNote(item, race) + html;
  }

  /* A House race: a link to the district on its state's map - and where the
   * map was redrawn for 2026, on both maps, with the district a member holds
   * when they are running in another one. */
  function redrawnNote(item, race) {
    var plan = (KYC.meta().districtMaps || {})[race.state];
    if (!plan || race.chamber !== "House") return "";
    var label = function (n) { return race.state + "-" + (n ? n : "AL"); };
    var seats = [race.district || 0];
    if (plan.redrawn && KYC.runsElsewhere(item) && item.state === race.state &&
        item.districtNum && item.districtNum !== race.district) {
      seats.unshift(item.districtNum);
    }
    var link = KYC.siteRoot() + plan.page + "#/?d=" +
      seats.slice().sort(function (a, b) { return a - b; }).join(",");
    var words = plan.redrawn
      ? plan.name + " redrew its House districts for 2026: " +
        seats.map(label).join(" and ") + " before and after"
      : label(seats[0]) + " on the district map";
    return '<p class="race-note race-redrawn">' + KYC.icon("layers") + ' <a href="' +
      KYC.escapeAttr(link) + '">' + KYC.escapeHtml(words) + " &rsaquo;</a></p>";
  }

  /* Nobody else in this race has a profile. That used to read "Nobody else
   * has filed for this seat" for every such race, including ones where five
   * people had filed - a claim about our profiles dressed up as a fact about
   * the race. It is worded from the race's own counts, as the race header
   * on the cards is, and says nobody filed only when filedCount does. */
  function aloneNote(race) {
    var filed = race.filedCount || 0;
    var res = race.results || null;
    var text;
    if (race.settled && res) {
      text = "No one else is on the November ballot for this seat, " + KYC.ballotSource(race) +
        (filed ? " (" + filed + " filed with the FEC in all)." : ".");
    } else if (filed) {
      text = filed + (filed === 1 ? " has" : " have") + " filed with the FEC for this seat, " +
        "but no one else has reported raising $5,000 - the point at which federal law " +
        "treats someone as a candidate.";
    } else {
      return '<span class="kyc-absent">Nobody else has filed with the FEC for this seat</span>';
    }
    return '<p class="race-note">' + KYC.escapeHtml(text) + "</p>";
  }

  /* Every link is built from an id the source dataset holds - never from a
   * name. A Ballotpedia page guessed from "Mike Rogers" is the wrong Mike
   * Rogers half the time, and nothing on the page would look wrong. */
  var REFERENCE = [
    ["wikipedia", "Wikipedia", function (v) {
      return "https://en.wikipedia.org/wiki/" + encodeURIComponent(String(v).replace(/ /g, "_"));
    }],
    ["ballotpedia", "Ballotpedia", function (v) {
      return "https://ballotpedia.org/" + encodeURIComponent(String(v).replace(/ /g, "_"));
    }],
    ["govtrack", "GovTrack", function (v) {
      return "https://www.govtrack.us/congress/members/" + encodeURIComponent(v);
    }],
    ["opensecrets", "OpenSecrets", function (v) {
      return "https://www.opensecrets.org/members-of-congress/summary?cid=" + encodeURIComponent(v);
    }],
    ["votesmart", "Vote Smart", function (v) {
      return "https://justfacts.votesmart.org/candidate/" + encodeURIComponent(v);
    }],
  ];

  // An account is linked by the id the source holds where it holds one: an
  // X id follows a renamed handle (RepMikeJohnson, now SpeakerJohnson, is
  // "not found"). The pipeline gives a YouTube value its shape - a channel
  // id is youtube_id, a handle starts with "@", anything else is a legacy
  // username that still answers at /user/.
  var SOCIAL = [
    ["twitter_id", "X", function (v) { return "https://x.com/i/user/" + encodeURIComponent(v); }],
    ["twitter", "X", function (v) { return "https://x.com/" + encodeURIComponent(v); }],
    ["facebook", "Facebook", function (v) { return "https://www.facebook.com/" + encodeURIComponent(v); }],
    ["instagram", "Instagram", function (v) { return "https://www.instagram.com/" + encodeURIComponent(v); }],
    ["youtube_id", "YouTube", function (v) { return "https://www.youtube.com/channel/" + encodeURIComponent(v); }],
    ["youtube", "YouTube", function (v) {
      v = String(v);
      return v.charAt(0) === "@"
        ? "https://www.youtube.com/@" + encodeURIComponent(v.slice(1))
        : "https://www.youtube.com/user/" + encodeURIComponent(v);
    }],
    ["bluesky", "Bluesky", function (v) { return "https://bsky.app/profile/" + encodeURIComponent(v); }],
  ];

  /**
   * A chip's tooltip. An account linked by its id names no handle: the id
   * follows a rename, and the source's handle beside it may be the old one
   * (Speaker Johnson's id leads to SpeakerJohnson; the source still says
   * RepMikeJohnson, which X answers "not found" for and anyone could take).
   */
  function handleTitle(social, key, value) {
    if (key === "twitter_id") return "X account, linked by its id";
    if (key === "youtube_id") return "YouTube channel, linked by its id";
    value = String(value);
    return value.charAt(0) === "@" ? value : "@" + value;
  }

  /**
   * The funding split, each label kept on one line with its share ("Transfers
   * from other committees <1%" broke between label and value at 390px), and,
   * where adjustments brought the receipts below the parts, what the shares
   * are of: Shri Thanedar's add up to $3,968,600 beside "Raised $3,194,222".
   */
  function fundingHtml(item) {
    if (!item.fundingBreakdown || !KYC.hasValue(item, "funding_sources")) {
      return KYC.renderField(item, "funding_sources");
    }
    var html = String(item.funding_sources).split(", ").map(function (pair) {
      return '<span class="funding-part">' + KYC.escapeHtml(pair) + "</span>";
    }).join(", ");
    if (item.fundingBase) {
      html += '<span class="funding-base">Shares of ' + KYC.escapeHtml(item.fundingBase) +
        " received, before adjustments the FEC deducts to reach the " +
        KYC.escapeHtml(item.receipts || "") + " raised.</span>";
    }
    return html;
  }

  function linkChip(url, label, title) {
    return '<a class="link-chip" href="' + KYC.escapeAttr(url) +
      '" target="_blank" rel="noopener noreferrer"' +
      (title ? ' title="' + KYC.escapeAttr(title) + '"' : "") + ">" +
      KYC.escapeHtml(label) + KYC.icon("share", "link-chip-icon") + "</a>";
  }

  function renderContact(item) {
    var panel = el("profileModalContactPanel");
    var target = el("profileModalContact");
    var rows = [];

    var sites = [];
    if (item.website) sites.push(linkChip(item.website, "Official website", item.website));
    if (item.campaignSite) {
      sites.push(linkChip(item.campaignSite, "Campaign website",
        item.campaignSiteVia === "election-page"
          // Not from a filing: the race's Wikipedia page lists it, and the
          // pipeline checked that the site names the candidate.
          ? "As listed on Wikipedia’s page for this race"
          : (item.campaignCommittee ? item.campaignCommittee + " - " : "") +
            "as filed with the FEC"));
    }
    if (item.contactForm) sites.push(linkChip(item.contactForm, "Contact form"));
    if (sites.length) rows.push('<div class="links-row">' + sites.join("") + "</div>");

    var office = [];
    if (item.phone) {
      office.push('<span>' + KYC.icon("pin") + ' <a href="tel:' +
        KYC.escapeAttr(String(item.phone).replace(/[^\d+]/g, "")) + '">' +
        KYC.escapeHtml(item.phone) + "</a></span>");
    }
    if (item.office) office.push("<span>" + KYC.escapeHtml(item.office) + "</span>");
    if (office.length) rows.push('<p class="modal-meta contact-office">' + office.join("") + "</p>");

    var social = [];
    var seen = {};
    SOCIAL.forEach(function (spec) {
      var value = item.social && item.social[spec[0]];
      if (!value || seen[spec[1]]) return;
      seen[spec[1]] = true;
      social.push(linkChip(spec[2](value), spec[1], handleTitle(item.social, spec[0], value)));
    });
    if (social.length) {
      rows.push('<span class="field-label">Official accounts</span>' +
        '<div class="links-row">' + social.join("") + "</div>");
    }

    var refs = [];
    REFERENCE.forEach(function (spec) {
      var value = spec[0] === "wikipedia" ? item.wikipedia : (item.refs || {})[spec[0]];
      if (value) refs.push(linkChip(spec[2](value), spec[1]));
    });
    if (item.fecCandidateId) {
      refs.push(linkChip("https://www.fec.gov/data/candidate/" +
        encodeURIComponent(item.fecCandidateId) + "/", "FEC filings",
        "Candidate " + item.fecCandidateId + " at the Federal Election Commission"));
    }
    if (!item.isCandidate && /^[A-Z]\d{6}$/.test(item.id)) {
      refs.push(linkChip("https://bioguide.congress.gov/search/bio/" +
        encodeURIComponent(item.id), "Biographical Directory"));
    }
    if (refs.length) {
      rows.push('<span class="field-label">Elsewhere</span>' +
        '<div class="links-row">' + refs.join("") + "</div>");
    }

    panel.hidden = !rows.length;
    target.innerHTML = rows.join("");
  }

  /* A member running for another seat files for it under another FEC id,
   * on its own profile (rule 68: a member carries only their own chamber's
   * ids, so nothing is folded). "Raised: No filing this cycle" on Chris
   * Pappas, whose Senate campaign had raised $15.4 million, was false read
   * plainly (PERSONA-07, RACES-03). So the tiles say which filing is
   * missing, and that campaign's own totals follow, labelled with its
   * office, its FEC id and its date, and linked to its profile. */
  var FINANCE_FIELDS = ["receipts", "disbursements", "funding_sources"];

  function renderOtherCampaign(item) {
    var target = el("profileModalOtherCampaign");
    var filing = KYC.otherCampaign(item);
    if (!filing) {
      target.hidden = true;
      target.innerHTML = "";
      return;
    }
    var chamber = item.chamber.indexOf("Senate") !== -1 ? "Senate" : "House";
    var quality = item.quality || {};
    var missing = quality.receipts === "no_filing";
    var tiles = { receipts: "profileModalReceipts", disbursements: "profileModalSpent",
                  funding_sources: "profileModalFunding" };
    /* The funding box under them said "No data" - a claim that this site
     * did not look (rule 19) - while the tiles beside it said the FEC had
     * been checked: its quality is "unknown" when the money is not there. */
    FINANCE_FIELDS.forEach(function (field) {
      if (quality[field] !== "no_filing" &&
          !(field === "funding_sources" && missing && quality[field] !== "ok")) return;
      el(tiles[field]).innerHTML = '<span class="kyc-absent" title="' + KYC.escapeAttr(
        "Checked with the FEC: no filing for the " + chamber + " seat this member holds in this " +
        "cycle. Their campaign for " + filing.officeLabel + " files separately; its totals are " +
        "below.") + '">No ' + chamber + " filing</span>";
    });
    var line = KYC.contestLine(item);
    var seat = filing.officeLabel;
    var words = (missing ? "No " + chamber + " filing this cycle; " : "") +
      (line && line.past ? "ran for " : missing ? "running for " : "Also running for ") +
      seat + ". That campaign";
    words = words.charAt(0).toUpperCase() + words.slice(1);
    var id = filing.fecCandidateId ? " (FEC " + filing.fecCandidateId + ")" : "";
    var money = KYC.hasValue(filing, "receipts") && filing.financeSource
      ? " raised " + filing.receipts +
        (KYC.hasValue(filing, "disbursements") ? " and spent " + filing.disbursements : "") +
        (filing.financeAsOf ? ", through " + filing.financeAsOf : "") + "."
      : " reports no totals yet.";
    target.hidden = false;
    target.innerHTML = KYC.escapeHtml(words + id + money) +
      ' <button type="button" class="link-button" data-goto="' + KYC.escapeAttr(filing.id) +
      '">Its profile &rsaquo;</button>';
  }

  /* Outside spending: each side's total and the committees that spent it,
   * as the FEC totals them by candidate (PERSONA-12). Two sides, never a
   * net; the committees as filed. */
  function renderOutside(item) {
    var target = el("profileModalOutside");
    var o = item.outsideSpending;
    var other = item.outsideSpendingOther ?
      '<p class="finance-period">' + KYC.cards.outsideOtherLine(item) + "</p>" : "";
    if (!o && !other) {
      target.hidden = true;
      target.innerHTML = "";
      return;
    }
    if (!o) {
      target.hidden = false;
      target.innerHTML = '<span class="field-label">Outside spending</span>' + other +
        '<p class="faint outside-note">' + KYC.escapeHtml(KYC.cards.outsideNote) + "</p>";
      return;
    }
    var side = function (word, total, n, top) {
      if (!total) return "";
      return '<div class="outside-side"><span class="field-label">' + KYC.escapeHtml(word) +
        " " + KYC.escapeHtml(KYC.moneyShort(total)) + "</span>" +
        '<ul class="outside-list">' + (top || []).map(function (c) {
          return "<li>" + KYC.escapeHtml(c.committee) + ' <span class="faint">' +
            KYC.escapeHtml(KYC.moneyShort(c.total)) + "</span></li>";
        }).join("") + (n > (top || []).length ? '<li class="faint">and ' +
          (n - top.length) + " more</li>" : "") + "</ul></div>";
    };
    target.hidden = false;
    target.innerHTML = '<span class="field-label">Outside spending</span>' +
      '<p class="finance-period">' + KYC.cards.outsideLine(item) + "</p>" +
      '<div class="outside-sides">' +
      side("Supporting", o.support, o.supportCommittees, o.supportTop) +
      side("Opposing", o.oppose, o.opposeCommittees, o.opposeTop) + "</div>" + other +
      '<p class="faint outside-note">' + KYC.escapeHtml(KYC.cards.outsideNote) + "</p>";
  }

  function renderCrossLink(item) {
    var link = el("profileModalCrossLink");
    var id = item.alsoRunningId || item.incumbentId;
    var seat = item.alsoRunningSeat || item.incumbentSeat;

    if (!id || !seat) {
      /* A member contesting a different seat under the same name - a
       * redrawn district - has no second profile to jump to; the seat they
       * are running for is on this one. */
      /* Al Green read "Running in 2026 for House • TX-18" beside "Lost the
       * 2026 primary for House • TX-18" (PROFILES-04): a run that ended is
       * in the past tense, and a renumbered seat is re-election. */
      if (item.contestLabel && !item.isCandidate) {
        var line = KYC.contestLine(item);
        link.hidden = false;
        link.innerHTML = KYC.icon("branch") + ' <span class="cross-link-text">' + (line.renumbered
          ? (line.past ? "Ran" : "Running") + " for re-election in <strong>" +
            KYC.escapeHtml(item.contestLabel) +
            "</strong> under the new district map"
          : (line.past ? "Ran in 2026 for <strong>" : "Running in 2026 for <strong>") +
            KYC.escapeHtml(item.contestLabel) + "</strong> instead of " +
            KYC.escapeHtml(item.officeLabel)) + "</span>";
        return;
      }
      link.hidden = true;
      link.innerHTML = "";
      return;
    }
    link.hidden = false;
    // The member this filing belongs to may have left since: never
    // "currently holds" a seat they no longer sit in.
    var member = item.incumbentId ? KYC.byId(item.incumbentId) : null;
    var left = member && member.formerMember ? member.formerMember.left : null;
    // "Also running Senate • SC" beside Russell Fry's renomination, after
    // he lost the Senate primary: a run that ended is "Also ran for", a
    // November loss included, as KYC.contestLine says it on the card.
    var other = item.alsoRunningId ? KYC.byId(item.alsoRunningId) : null;
    var ended = !!other && (KYC.offBallot(other.raceStatus) || other.raceStatus === "defeated");
    var how = ended ? KYC.raceStatus(other.raceStatus, "mate") : null;
    link.innerHTML =
      KYC.icon("branch") + ' <span class="cross-link-text">' +
      (item.alsoRunningId ? (ended ? "Also ran for" : "Also running for")
        : left ? "Held until " + left : "Currently holds") +
      ' <button type="button" data-goto="' + KYC.escapeAttr(id) + '">' +
      KYC.escapeHtml(seat) + "</button>" +
      (how ? " (" + KYC.escapeHtml(how.label.toLowerCase()) + ")" : "") + "</span>";
  }

  function renderStatus(item) {
    var target = el("profileModalStatus");
    var pieces = [];

    /* A member running for another seat reads as anyone else in that race,
     * named: "On the November ballot for Senate • IA". The member wording -
     * "renominated", "not seeking re-election" - is about the seat they
     * hold, and their result there is not their 2026 story. */
    var elsewhere = !item.isCandidate && !!item.contestLabel;
    // The status every view shows for this person, a filer the results do
    // not settle included: Cinde Wirth's card read "Result not matched"
    // over a dialog with no status at all (PROFILES-05, PROFILES-06).
    var race = KYC.standing(item, "long");
    if (race) {
      var label = elsewhere ? race.label + " for " + item.contestLabel : race.label;
      // "On the November ballot – Speak The Truth line": a primary loser on
      // a minor-party line must not read as their party's second nominee.
      var line = KYC.ballotLine(item);
      var campaign = KYC.contestStatus(item) === "nominee" &&
        KYC.electionStatus().phase !== "post-election";
      var title = line ? "On the general election ballot on the " + line + " line. " +
        (campaign ? "Source: the state's Wikipedia election results page." : race.title)
        : race.title;
      pieces.push('<span class="badge ' + race.cls + '" title="' +
        KYC.escapeAttr(title) + '">' + KYC.escapeHtml(label) +
        KYC.ballotLineSuffix(item) + "</span>");
    }

    /* A curated candidate's roster status ("Primary Candidate / US
     * Representative") was written before the primary; once the results say
     * where they stand, it only contradicts them. A member's status line is
     * kept: it is where a retirement or an appointment is explained. */
    var text = String(item.status || "").trim();
    if (item.isCandidate && race) text = "";
    if (item.formerMember) {
      // Left Congress: said plainly, not as a warning about the seat.
      pieces.push('<span class="badge badge-neutral">' +
        KYC.escapeHtml(KYC.formerText(item)) + "</span>");
      text = "";
    }
    // Where a member who is leaving is going, when a results page has made
    // them another office's nominee: that says more than "Retiring to run
    // for governor", which it replaces.
    if (KYC.otherOffice(item)) {
      pieces.push(KYC.otherOfficeBadge(item) + ' <a class="field-credit" href="' +
        KYC.escapeAttr(item.otherOffice.source) + '" target="_blank" rel="noopener noreferrer">' +
        "Source</a>");
      text = "";
    }
    // "Not running for re-election" said twice, once by the results and
    // once by the roster's note, is said once - and only when the note says
    // nothing more: Eleanor Norton's "Not running for re-election in 2026
    // (announced January 2026)." repeated her badge, while Cleo Fields's
    // goes on to say where he is running.
    var restated = /^(incumbent )?not running for re-election( in \d{4})?( \(announced [^)]*\))?\.?$/i;
    if (race && /^not running/i.test(race.label) && restated.test(text)) {
      text = "";
    }
    if (text && text !== "Active Member" && text !== "N/A" &&
        text !== "Filed with the FEC") {
      var leaving = /retiring|not running|defeated|ineligible|resigned/i.test(text);
      pieces.push('<span class="badge ' + (leaving ? "badge-danger" : "badge-warn") +
        '">' + KYC.escapeHtml(text) + "</span>");
    }

    target.hidden = !pieces.length;
    target.innerHTML = pieces.join(" ");
  }

  function renderAge(item) {
    var years = KYC.ageOf(item);
    var hasAge = years !== null;
    var hasBirth = KYC.hasValue(item, "birthdate") && item.birthdate !== "Unknown";
    // A birthdate the pipeline read from a Wikipedia infobox says so.
    var badge = hasBirth ? KYC.sourceBadge(item, "birthdate") : "";

    if (hasAge && hasBirth) {
      return KYC.escapeHtml(years + " (born " + KYC.dateWords(item.birthdate) + ")") + badge;
    }
    if (hasAge) return KYC.escapeHtml(years + " years old");
    if (hasBirth) return KYC.escapeHtml(KYC.dateWords(item.birthdate)) + badge;
    return '<span class="kyc-absent">No data</span>';
  }

  /* ------------------------------------------------------------------ open */

  function render(item) {
    el("profileModalName").textContent = item.name;
    // The name on the ballot, where the results page or the state's list
    // settled it, with the registration it was matched to beneath: a
    // reader who searches the FEC for "Bob Harvie" finds Robert J Harvie.
    var fecName = el("profileModalFecName");
    fecName.hidden = !(item.fecName && item.fecName !== item.name);
    fecName.textContent = fecName.hidden ? "" : "Files with the FEC as " + item.fecName;
    // officeLabel is normalised in kyc/profiles.py. The pages used to rebuild
    // it from chamber + state + district in three separate places, which is
    // how "House • AL-District 3" and "House • TX-TX-32" once shipped.
    el("profileModalRegion").textContent = item.officeLabel;
    // A challenger does not represent the seat they are running for (rule
    // 27), and until 2026-10 every candidate's dialog said they did.
    // Nor is someone who lost, withdrew or never made the ballot still
    // running, with a term "if elected" (PROFILES-07).
    var settled = item.isCandidate ? KYC.contestStatus(item) : "";
    var ended = KYC.offBallot(settled) || settled === "defeated";
    el("profileModalRegionLabel").textContent = item.formerMember
      ? "Represented (until " + item.formerMember.left + ")"
      : !item.isCandidate ? "Represents"
      : settled === "unlisted" ? "Filed for"
      : ended ? "Ran for" : "Running for";
    el("profileModalTermWrap").hidden = ended;
    var stateLink = el("profileModalStateLink");
    if (item.state && item.state !== "N/A") {
      stateLink.hidden = false;
      stateLink.href = KYC.stateUrl(item.state);
      stateLink.textContent = KYC.stateName(item.state) + " \u203a";
      stateLink.title = "Everything about " + KYC.stateName(item.state) + ": its delegation and 2026 races";
    } else {
      stateLink.hidden = true;
    }
    // "2021-01-03 - 2027-01-03" broke as "2027-01-" / "03" in large text.
    // Only a date is kept whole: an appointee's "until the winner of the
    // 2026-11-03 special election is sworn in" is a sentence, and held on
    // one line it ran off a phone's screen.
    var term = el("profileModalTerm");
    term.textContent = "";
    String(item.term_start || "N/A").split(" - ").forEach(function (part, i) {
      if (i) term.appendChild(doc.createTextNode(" - "));
      var span = doc.createElement("span");
      if (part.length <= 24) span.className = "nowrap";
      span.textContent = KYC.dateWords(part);
      term.appendChild(span);
    });

    var chamber = el("profileModalChamber");
    chamber.textContent = item.chamber;
    chamber.className =
      "badge " + (item.chamber.indexOf("Senate") !== -1 ? "badge-accent" : "badge-neutral");

    var party = el("profileModalParty");
    party.textContent = item.party;
    party.style.background = PARTY_LABEL_BG[KYC.partyKey(item)];

    var photo = el("profileModalPhoto");
    photo.setAttribute("data-profile", item.id);
    photo.alt = "Portrait of " + item.name;
    KYC.setPortrait(photo, item, "116px");
    showPhotoCredit();

    el("profileModalAge").innerHTML = renderAge(item);

    /* No free source publishes a computed net worth, and a disclosure reports
     * assets in broad value bands, so deriving one figure from it would be an
     * estimate dressed as a fact (rule 26). The dialog showed an unsourced
     * "Est. net worth" from the roster for 144 members, beside this link, as
     * though one came from the other. It links the filing alone now. A
     * challenger's disclosures are not looked up, so the field is not shown
     * for them rather than reading as an absence. */
    var disclosure = el("profileModalDisclosure");
    el("profileModalDisclosureField").hidden = !!item.isCandidate && !item.disclosureUrl;
    if (item.disclosureUrl) {
      // The Senate's disclosure site shows its terms of use before the
      // first report a visitor opens. That was said only in a hover title,
      // which a phone never shows, so the link looked broken (TRUST-16):
      // it is a visible line under the link now.
      var senate = item.disclosureSource === "senate-efd";
      var filed = item.disclosureFiled ? " on " + KYC.dateWords(item.disclosureFiled) : "";
      disclosure.innerHTML =
        '<a class="disclosure-link" target="_blank" rel="noopener noreferrer" href="' +
        KYC.escapeAttr(item.disclosureUrl) + '" title="' +
        KYC.escapeAttr(senate
          ? "Annual financial disclosure filed with the Secretary of the Senate" + filed
          : "Annual financial disclosure filed with the Clerk of the House" + filed + " (PDF)"
        ) + '">' + KYC.icon("link") + " " +
        KYC.escapeHtml((item.disclosureYear ? item.disclosureYear + " " : "") +
          (senate ? "Senate financial disclosure" : "House financial disclosure (PDF)")) + "</a>" +
        (senate ? '<span class="field-note">The Senate shows its terms of use first: ' +
          "accept them, then open this link again.</span>" : "");
    } else {
      // A claim about this site, not about the member (rule 19): the
      // matcher misses compound surnames and other first names (Debbie
      // Wasserman Schultz, H. Morgan Griffith), so "none exists" was false.
      disclosure.innerHTML = '<span class="kyc-absent" title="' +
        KYC.escapeAttr("This site has not matched this member to a filing in the House " +
          "Clerk's index or the Senate's eFD. The filing may exist.") +
        '">Not linked here</span>';
    }
    el("profileModalEducation").innerHTML = KYC.renderField(item, "education");
    el("profileModalCareers").innerHTML = KYC.renderField(item, "previous_professions");
    // A member's record is found by their congress-legislators id; a
    // challenger's only through the article their election page links.
    el("profileModalHeld").innerHTML = KYC.officesHeld(item.politicalHistory, item.isCandidate
      ? "This site finds a challenger\u2019s record only through the article their state\u2019s " +
        "election page links. None is linked for this person, or it is not theirs."
      : "This site has not read this member\u2019s record of offices.");
    el("profileModalReceipts").innerHTML = KYC.renderField(item, "receipts", { source: true });
    el("profileModalSpent").innerHTML = KYC.renderField(item, "disbursements");
    el("profileModalFunding").innerHTML = fundingHtml(item);

    var cashWrap = el("profileModalCashWrap");
    cashWrap.hidden = !item.cashOnHand;
    if (item.cashOnHand) el("profileModalCash").textContent = item.cashOnHand;

    // Which months the money covers, next to the money: a Senate election
    // period is six years and a House one two, and the tiles alone cannot
    // say which a figure is.
    var period = KYC.financePeriod(item);
    var periodEl = el("profileModalFinancePeriod");
    periodEl.hidden = !period;
    periodEl.textContent = period ? period + "." : "";

    renderStatus(item);
    renderCrossLink(item);
    renderPlatform(item);
    /* A sitting member's filing for another seat is the same person: their
     * voting record and committees are the member's, not "(not a sitting
     * member)" under "Currently holds House • AL-1" (PROFILES-03). */
    var sitting = item.isCandidate && item.incumbentId ? KYC.byId(item.incumbentId) : null;
    sitting = sitting && KYC.seated(sitting) && sitting.id !== item.id ? sitting : null;
    renderVoting(sitting || item);
    renderCommittees(sitting || item);
    renderLeadership(sitting || item);
    if (sitting) {
      // In the filing's own name: "From Garland Barr's record" on Andy
      // Barr's Senate filing read as someone else's (the roster's name).
      var from = '<p class="field-credit">From ' + KYC.escapeHtml(item.name) +
        "’s record as the member for " + '<button type="button" class="link-button" data-goto="' +
        KYC.escapeAttr(sitting.id) + '">' + KYC.escapeHtml(sitting.officeLabel) + "</button></p>";
      el("profileModalVoting").insertAdjacentHTML("beforeend", from);
      el("profileModalCommittees").insertAdjacentHTML("beforeend", from);
    }
    renderOtherCampaign(item);
    renderOutside(item);
    renderContact(item);
    renderRace(item);

    // Every figure of money on the site is the FEC's (validate: finance-not-fec).
    el("profileModalSource").textContent = item.financeSource
      ? "Finance figures from the FEC" +
        (item.financeAsOf ? ", through " + KYC.dateWords(item.financeAsOf) +
          (KYC.filedAhead(item) ? ", a date still to come" : "") : "") +
        (item.financeElection ? " (" + item.financeElection + " election period)" : "")
      : "";
  }

  function open(id, opts) {
    var item = KYC.byId(id);
    if (!item) return false;

    ensure();
    current = item;
    render(item);
    // A tab, a bookmark or a history entry names the person (GRID-24).
    if (baseTitle === null) baseTitle = doc.title;
    // The pages' own separator: "North Carolina \u2014 Know Your Candidate".
    doc.title = item.name + " (" + item.officeLabel + ") \u2014 Know Your Candidate";
    el("profileModalReport").setAttribute("data-profile", item.id);
    if (!(opts && opts.fromRoute)) {
      KYC.router.writeProfile(item.id);
    } else if (item.id !== id) {
      // Arrived under one of the person's other FEC ids: show the canonical
      // one, so the link a reader copies onward is the current id.
      global.history.replaceState(global.history.state, "",
        global.location.pathname + "#/profile/" + encodeURIComponent(item.id));
    }
    dialog.open();
    return true;
  }

  function close() {
    if (dialog) dialog.close();
  }

  function isOpen() {
    return !!dialog && dialog.isOpen();
  }

  function ensure() {
    if (dialog) return dialog;

    root = template();
    doc.body.appendChild(root);
    dialog = KYC.createModal(root, {
      onClose: function () {
        current = null;
        if (baseTitle !== null) doc.title = baseTitle;
        KYC.router.clearProfile();
      },
    });

    // Cross-links replace the dialog's contents rather than stacking a
    // second dialog on top of the first.
    root.addEventListener("click", function (event) {
      var goto = event.target.closest("[data-goto]");
      if (goto) open(goto.getAttribute("data-goto"));
    });

    var copy = el("profileModalCopy");
    copy.addEventListener("click", function () {
      if (!current) return;
      var url =
        global.location.origin === "null"
          ? global.location.href
          : global.location.origin + global.location.pathname +
            "#/profile/" + encodeURIComponent(current.id);
      var done = function () {
        copy.innerHTML = KYC.icon("check") + " Copied";
        setTimeout(function () {
          copy.innerHTML = KYC.icon("share") + " Copy link";
        }, 1800);
      };
      if (global.navigator.clipboard && global.navigator.clipboard.writeText) {
        global.navigator.clipboard.writeText(url).then(done, function () {});
      }
    });

    return dialog;
  }

  KYC.profile = { open: open, close: close, isOpen: isOpen, ensure: ensure };
})(window);
