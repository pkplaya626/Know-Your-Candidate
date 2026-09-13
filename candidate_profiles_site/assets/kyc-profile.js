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
      '<button class="modal-scrim" data-close aria-label="Close profile"></button>',
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
      '      <p class="modal-meta">',
      '        <span>' + KYC.icon("pin") +
      '          Represents <strong id="profileModalRegion"></strong>' +
      '          <a id="profileModalStateLink" class="state-link" href="#"></a></span>',
      '        <span>' + KYC.icon("calendar") +
      '          Term <strong id="profileModalTerm"></strong></span>',
      '        <span id="profileModalCrossLink" hidden></span>',
      "      </p>",
      '      <p class="modal-meta" id="profileModalStatus" hidden></p>',
      "    </div>",
      "  </header>",
      '  <div class="modal-body scroll-y">',
      '    <div class="modal-column">',
      '      <section class="panel">',
      '        <h3 class="panel-head">' + KYC.icon("user") + " Biography</h3>",
      '        <div class="field-grid">',
      '          <div class="field"><span class="field-label">Age / born</span>',
      '            <span class="field-value" id="profileModalAge"></span></div>',
      '          <div class="field"><span class="field-label">Est. net worth</span>',
      '            <span class="field-value" id="profileModalWorth"></span>',
      '            <span id="profileModalDisclosure"></span></div>',
      '          <div class="field span-2"><span class="field-label">Education</span>',
      '            <span class="field-value subtle" id="profileModalEducation"></span></div>',
      '          <div class="field span-2"><span class="field-label">Previous careers</span>',
      '            <span class="field-value subtle" id="profileModalCareers"></span></div>',
      "        </div>",
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
      '        <span class="field-label">Funding sources</span>',
      '        <p class="note-box" id="profileModalFunding" style="margin-top:6px"></p>',
      "      </section>",
      '      <section class="panel">',
      '        <h3 class="panel-head">' + KYC.icon("chart") + " Voting alignment</h3>",
      '        <div class="note-box" id="profileModalVoting"></div>',
      "      </section>",
      '      <section class="panel">',
      '        <h3 class="panel-head">' + KYC.icon("layers") + " Committees</h3>",
      '        <div class="scroll-y scroll-box list-rows" id="profileModalCommittees"></div>',
      "      </section>",
      "    </div>",
      "  </div>",
      '  <footer class="modal-footer">',
      '    <span id="profileModalSource"></span>',
      '    <span style="display:flex;gap:8px">',
      '      <button type="button" class="btn" id="profileModalCopy">' +
      KYC.icon("share") + " Copy link</button>",
      '      <button type="button" class="btn" data-close>Close</button>',
      "    </span>",
      "  </footer>",
      "</div>",
    ].join("");
    return wrap;
  }

  function el(id) {
    return doc.getElementById(id);
  }

  /* -------------------------------------------------------------- sections */

  /** Platform text arrives as prose, a comma list, or a Python-style list
   *  literal. Whatever the shape, every fragment is escaped. */
  function renderPlatform(item) {
    var target = el("profileModalPlatform");
    if (!KYC.hasValue(item, "platforms")) {
      target.innerHTML = KYC.renderField(item, "platforms");
      return;
    }

    var text = String(item.platforms || "").trim();
    var parts = null;

    if (text.charAt(0) === "[" && text.charAt(text.length - 1) === "]") {
      try {
        var parsed = JSON.parse(text.replace(/'/g, '"'));
        if (Array.isArray(parsed)) parts = parsed.map(String);
      } catch (e) {
        /* not a list literal after all; fall through to the comma split */
      }
    }
    if (!parts) parts = text.split(/,\s+/);

    if (parts.length > 1) {
      target.innerHTML =
        '<ul class="bullets">' +
        parts.map(function (p) { return "<li>" + KYC.escapeHtml(p) + "</li>"; }).join("") +
        "</ul>";
    } else {
      target.innerHTML = '<p class="note-box">' + KYC.escapeHtml(text) + "</p>";
    }
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
    var label = (text.match(/\(([^)]+)\)/) || [])[1] || "";
    var loyalty = (text.match(/•\s*(.*)$/) || [])[1] || "";
    var tone = value <= -0.1 ? "party-d" : value >= 0.1 ? "party-r" : "";

    target.innerHTML = [
      '<div class="ideology">',
      '  <div class="ideology-head">',
      '    <span class="ideology-score ' + tone + '">',
      (value > 0 ? "+" : "") + value.toFixed(2),
      label ? '<span class="label">' + KYC.escapeHtml(label) + "</span>" : "",
      "    </span>",
      loyalty ? '<span class="badge badge-neutral">' +
        KYC.escapeHtml(loyalty) + "</span>" : "",
      "  </div>",
      '  <div class="ideology-track" role="img" aria-label="DW-NOMINATE first dimension ' +
      KYC.escapeAttr(value.toFixed(2)) + ' on a scale from -1 (left) to +1 (right)">',
      '    <span class="ideology-marker" style="left:' + pct.toFixed(2) + '%"></span>',
      "  </div>",
      '  <div class="ideology-axis"><span>-1.0 left</span>' +
      "<span>centre</span><span>right +1.0</span></div>",
      "</div>",
    ].join("");
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

    if (!KYC.hasValue(item, "committees") || !text || text === "None" ||
        text === "None (Candidate)") {
      target.innerHTML =
        '<span class="kyc-absent">No committee assignments' +
        (item.isCandidate ? " (not a sitting member)" : "") + "</span>";
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

  var SOCIAL = [
    ["twitter", "X", function (v) { return "https://x.com/" + encodeURIComponent(v); }],
    ["facebook", "Facebook", function (v) { return "https://www.facebook.com/" + encodeURIComponent(v); }],
    ["instagram", "Instagram", function (v) { return "https://www.instagram.com/" + encodeURIComponent(v); }],
    ["youtube_id", "YouTube", function (v) { return "https://www.youtube.com/channel/" + encodeURIComponent(v); }],
    ["youtube", "YouTube", function (v) { return "https://www.youtube.com/user/" + encodeURIComponent(v); }],
    ["bluesky", "Bluesky", function (v) { return "https://bsky.app/profile/" + encodeURIComponent(v); }],
  ];

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
        (item.campaignCommittee ? item.campaignCommittee + " - " : "") +
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
    var seenYouTube = false;
    SOCIAL.forEach(function (spec) {
      var value = item.social && item.social[spec[0]];
      if (!value) return;
      if (spec[1] === "YouTube") {
        if (seenYouTube) return;
        seenYouTube = true;
      }
      social.push(linkChip(spec[2](value), spec[1], "@" + value));
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

  function renderCrossLink(item) {
    var link = el("profileModalCrossLink");
    var id = item.alsoRunningId || item.incumbentId;
    var seat = item.alsoRunningSeat || item.incumbentSeat;

    if (!id || !seat) {
      /* A member contesting a different seat under the same name - a
       * redrawn district - has no second profile to jump to; the seat they
       * are running for is on this one. */
      if (item.contestLabel && !item.isCandidate) {
        link.hidden = false;
        link.innerHTML = KYC.icon("branch") + " Running in 2026 for <strong>" +
          KYC.escapeHtml(item.contestLabel) + "</strong>, not for " +
          KYC.escapeHtml(item.officeLabel);
        return;
      }
      link.hidden = true;
      link.innerHTML = "";
      return;
    }
    link.hidden = false;
    link.innerHTML =
      KYC.icon("branch") + " " +
      (item.alsoRunningId ? "Also running" : "Currently holds") +
      ' <button type="button" data-goto="' + KYC.escapeAttr(id) + '">' +
      KYC.escapeHtml(seat) + "</button>";
  }

  var RACE_STATUS = {
    nominee: ["badge-money", "On the November ballot",
      "Won the 2026 primary. Source: the state's Wikipedia election results page."],
    eliminated: ["badge-danger", "Lost the 2026 primary",
      "Did not win the primary. Source: the state's Wikipedia election results page."],
    withdrawn: ["badge-neutral", "Withdrew from the 2026 race",
      "Listed as withdrawn in the published primary results."],
    unlisted: ["badge-neutral", "Not on the 2026 primary ballot",
      "Filed with the FEC, but not listed in the primary results for this seat."],
    advanced: ["badge-warn", "In a primary runoff",
      "Advanced to a runoff that has not yet been decided."],
  };

  /* The same facts read differently for a sitting member: "not on the
   * primary ballot" is a retirement, and a primary win is a renomination. */
  var MEMBER_RACE_STATUS = {
    nominee: ["badge-money", "Renominated for 2026",
      "Won the 2026 primary for this seat. Source: the state's Wikipedia election results page."],
    unlisted: ["badge-danger", "Not on the 2026 ballot",
      "Not named in the primary results or on the November ballot for this seat; " +
      "not seeking re-election."],
  };

  function renderStatus(item) {
    var target = el("profileModalStatus");
    var pieces = [];

    var table = item.isCandidate ? RACE_STATUS :
      Object.assign({}, RACE_STATUS, MEMBER_RACE_STATUS);
    var race = table[item.raceStatus];
    if (race) {
      var label = race[1];
      // A member's result belongs to the seat they are contesting.
      if (!item.isCandidate && item.contestLabel) {
        label = label.replace("for 2026", "for " + item.contestLabel)
          .replace("the November ballot", "the November ballot for " + item.contestLabel);
      }
      pieces.push('<span class="badge ' + race[0] + '" title="' +
        KYC.escapeAttr(race[2]) + '">' + KYC.escapeHtml(label) + "</span>");
    }

    var text = String(item.status || "").trim();
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
    var hasAge = item.age && item.age !== "Unknown";
    var hasBirth = KYC.hasValue(item, "birthdate") && item.birthdate !== "Unknown";

    if (hasAge && hasBirth) {
      return KYC.escapeHtml(item.age + " (born " + item.birthdate + ")");
    }
    if (hasAge) return KYC.escapeHtml(item.age + " years old");
    if (hasBirth) return KYC.escapeHtml(item.birthdate);
    return '<span class="kyc-absent">No data</span>';
  }

  /* ------------------------------------------------------------------ open */

  function render(item) {
    el("profileModalName").textContent = item.name;
    // officeLabel is normalised in kyc/profiles.py. The pages used to rebuild
    // it from chamber + state + district in three separate places, which is
    // how "House • AL-District 3" and "House • TX-TX-32" once shipped.
    el("profileModalRegion").textContent = item.officeLabel;
    var stateLink = el("profileModalStateLink");
    if (item.state && item.state !== "N/A") {
      stateLink.hidden = false;
      stateLink.href = KYC.stateUrl(item.state);
      stateLink.textContent = KYC.stateName(item.state) + " \u203a";
      stateLink.title = "Everything about " + KYC.stateName(item.state) + ": its delegation and 2026 races";
    } else {
      stateLink.hidden = true;
    }
    el("profileModalTerm").textContent = item.term_start || "N/A";

    var chamber = el("profileModalChamber");
    chamber.textContent = item.chamber;
    chamber.className =
      "badge " + (item.chamber.indexOf("Senate") !== -1 ? "badge-accent" : "badge-neutral");

    var party = el("profileModalParty");
    party.textContent = item.party;
    party.style.background = PARTY_LABEL_BG[KYC.partyKey(item)];
    party.style.color = "#0b0d10";

    var photo = el("profileModalPhoto");
    photo.setAttribute("data-photo-idx", "0");
    photo.setAttribute("data-profile", item.id);
    photo.alt = "Portrait of " + item.name;
    photo.src = KYC.portraitSrc(item);

    el("profileModalAge").innerHTML = renderAge(item);
    el("profileModalWorth").innerHTML = KYC.renderField(item, "net_worth");

    /* No free source publishes a computed net worth, and a disclosure reports
     * assets in broad value bands, so deriving one figure from it would be an
     * estimate dressed as a fact. Link the filing instead and let the reader
     * see what was actually submitted. */
    var disclosure = el("profileModalDisclosure");
    if (item.disclosureUrl) {
      disclosure.innerHTML =
        '<a class="disclosure-link" target="_blank" rel="noopener noreferrer" href="' +
        KYC.escapeAttr(item.disclosureUrl) + '" title="' +
        KYC.escapeAttr(
          "Annual financial disclosure filed with the Clerk of the House" +
          (item.disclosureFiled ? " on " + item.disclosureFiled : "") + " (PDF)"
        ) + '">' + KYC.icon("link") + " " +
        KYC.escapeHtml(item.disclosureYear || "") + " disclosure (PDF)</a>";
    } else {
      disclosure.innerHTML = "";
    }
    el("profileModalEducation").innerHTML = KYC.renderField(item, "education");
    el("profileModalCareers").innerHTML = KYC.renderField(item, "previous_professions");
    el("profileModalReceipts").innerHTML = KYC.renderField(item, "receipts", { source: true });
    el("profileModalSpent").innerHTML = KYC.renderField(item, "disbursements");
    el("profileModalFunding").innerHTML = KYC.renderField(item, "funding_sources");

    var cashWrap = el("profileModalCashWrap");
    cashWrap.hidden = !item.cashOnHand;
    if (item.cashOnHand) el("profileModalCash").textContent = item.cashOnHand;

    renderStatus(item);
    renderCrossLink(item);
    renderPlatform(item);
    renderVoting(item);
    renderCommittees(item);
    renderContact(item);

    el("profileModalSource").textContent = item.financeSource
      ? "Finance figures from the FEC" +
        (item.financeAsOf ? ", through " + item.financeAsOf : "")
      : "Figures as filed in the source rosters";
  }

  function open(id, opts) {
    var item = KYC.byId(id);
    if (!item) return false;

    ensure();
    current = item;
    render(item);
    if (!(opts && opts.fromRoute)) KYC.router.writeProfile(id);
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
