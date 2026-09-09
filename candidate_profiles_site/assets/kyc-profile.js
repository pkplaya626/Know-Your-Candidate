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
      '          Represents <strong id="profileModalRegion"></strong></span>',
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

  function renderCrossLink(item) {
    var link = el("profileModalCrossLink");
    var id = item.alsoRunningId || item.incumbentId;
    var seat = item.alsoRunningSeat || item.incumbentSeat;

    if (!id || !seat) {
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

  function renderStatus(item) {
    var target = el("profileModalStatus");
    var text = String(item.status || "").trim();
    if (!text || text === "Active Member" || text === "N/A") {
      target.hidden = true;
      target.innerHTML = "";
      return;
    }
    var leaving = /retiring|not running|defeated|ineligible|resigned/i.test(text);
    target.hidden = false;
    target.innerHTML =
      '<span class="badge ' + (leaving ? "badge-danger" : "badge-warn") + '">' +
      KYC.escapeHtml(text) + "</span>";
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
