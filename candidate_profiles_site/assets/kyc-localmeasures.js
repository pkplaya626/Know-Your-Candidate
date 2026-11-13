/* Know Your Candidate - the local questions on the November 3, 2026 ballot
 * in the most populous counties (rule 102).
 *
 * The statewide questions are KYC.ballot's (rule 95); local questions were
 * "not listed here" everywhere. By the owner's decision of 2026-11-01
 * ("largest places first") they are listed for the 50 most populous
 * counties: each county's own, those of districts that cover the whole
 * county, and those of its cities of 250,000 people or more, each from the
 * county election office's, the city clerk's or the state election
 * office's own document (kyc/local_measures.py). One implementation for the
 * county pages and Your ballot (rule 12).
 *
 * A question is said in its official words only - designation, title, text
 * or the office's printed summary (said to be one), kind - and this site
 * never says what a yes or a no vote does; nothing is coloured by side.
 * "None" is said only on a document's own words; a list that holds none but
 * does not say it is whole is said to list none, and the page does not say
 * there is none; where no official list could be read the page says so and
 * sends the reader to the election office (rule 19). From the day after
 * Election Day the words are in the past tense: this site reads no result
 * of a ballot question.
 *
 * Data: data/localmeasures/index.js (which counties are covered) and one
 * file per state, data/localmeasures/<st>.js, assigning kycLocalMeasuresXX,
 * loaded only where a county's questions are shown (rule 94).
 */
(function (global) {
  "use strict";

  var doc = global.document;
  var KYC = global.KYC;

  // Text longer than this is folded after its first lines.
  var FOLD_AT = 320;
  var TOTAL = 50;

  function esc(text) { return KYC.escapeHtml(text); }

  function index() { return global.kycLocalMeasuresIndex || null; }

  /** The county's [state, name] where this site lists its questions. */
  function covered(fips) {
    var idx = index();
    return idx && idx.counties ? idx.counties[fips] || null : null;
  }

  /** The state's sample-ballot page in KYC.sampleBallotLine's words, from
   *  the index (a county page loads no build figures); "" where none. */
  function sampleLine(code) {
    var idx = index();
    return KYC.sampleBallotLine(((idx && idx.samples) || {})[String(code).toUpperCase()]);
  }

  function stateFileName(code) { return "kycLocalMeasures" + String(code).toUpperCase(); }

  function stateData(code) { return global[stateFileName(code)] || null; }

  /** The county's record, or null where its state's file has not loaded. */
  function record(fips) {
    var c = covered(fips);
    var file = c && stateData(c[0]);
    return file ? file[fips] || null : null;
  }

  /** Loads the state files the counties *fipsList* need; resolves with the
   *  states whose file did not load. */
  function prepare(fipsList) {
    var states = [];
    (fipsList || []).forEach(function (fips) {
      var c = covered(fips);
      if (c && states.indexOf(c[0]) === -1 && !stateData(c[0])) states.push(c[0]);
    });
    return Promise.all(states.map(function (code) {
      return new Promise(function (resolve) {
        KYC.loadData("localmeasures/" + code.toLowerCase() + ".js", stateFileName(code),
          function (ok) { resolve(ok ? null : code); });
      });
    })).then(function (failed) { return failed.filter(Boolean); });
  }

  function cycleYear() {
    var meta = KYC.meta ? KYC.meta() : {};
    return ((meta || {}).election || {}).year || 2026;
  }

  /** From the day after Election Day the page speaks of an election held. */
  function held() { return KYC.electionStatus(cycleYear()).phase === "post-election"; }

  function link(url, words) {
    return '<a href="' + KYC.escapeAttr(url) + '" target="_blank" rel="noopener noreferrer">' +
      esc(words) + "</a>";
  }

  function day(iso) { return esc(KYC.dateWords(iso)); }

  /** What the coverage is, in one sentence, for every place it is said. */
  function coverageWords() {
    return "This site lists local questions only for the " + TOTAL + " most populous counties, " +
      "by the Census Bureau's 2024 estimates: each county's own questions, those of districts " +
      "that cover the whole county, and those of its cities of 250,000 people or more. Questions " +
      "of other cities and towns, and of school and special districts that do not cover the " +
      "whole county, are not listed here.";
  }

  /* ------------------------------------------------------- one question */

  var serial = 0;

  function textBlock(m) {
    if (!m.text) return '<p class="measure-note">' + esc(m.missing) + "</p>";
    var id = "local-measure-text-" + (++serial);
    var long = m.text.length > FOLD_AT;
    var paras = m.text.split(/\n+/).map(function (p) { return "<p>" + esc(p) + "</p>"; }).join("");
    return (m.summary ? '<p class="measure-summary">The office’s printed summary, not the ' +
        "ballot’s own words:</p>" : "") +
      '<blockquote class="measure-text' + (long ? " is-folded" : "") + '" id="' +
      KYC.escapeAttr(id) + '" cite="' + KYC.escapeAttr(m.source) + '">' + paras + "</blockquote>" +
      (long ? '<button type="button" class="link-button measure-more" data-local-more ' +
        'aria-expanded="false" aria-controls="' + KYC.escapeAttr(id) + '">Read the whole text</button>' : "");
  }

  function measureItem(m, level) {
    var name = m.designation || m.title;
    var title = m.designation ? m.title : null;
    var facts = [m.kind || "Kind not recorded here", m.j].filter(Boolean).join(". ") + ".";
    var notes = [];
    if (m.voters) notes.push(m.voters);
    if (m.cut) notes.push("Cut where marked “…”; the whole text is at its source.");
    if (m.note) notes.push(m.note);
    return '<li class="measure local-measure">' +
      "<h" + level + ' class="measure-name">' + esc(name) +
        (title ? ' <span class="measure-title">' + esc(title) + "</span>" : "") +
      "</h" + level + ">" +
      '<p class="measure-kind">' + esc(facts) + "</p>" +
      textBlock(m) +
      (notes.length ? '<p class="measure-note">' + esc(notes.join(" ")) + "</p>" : "") +
      '<p class="measure-links">' + link(m.source, m.sourceTitle) + " (read " + day(m.read) +
      ")</p></li>";
  }

  function list(measures, level) {
    return '<ol class="measures local-measures-list">' + measures.map(function (m) {
      return measureItem(m, level);
    }).join("") + "</ol>";
  }

  /* ---------------------------------------------- what a list rests on */

  /** The document a "none" or a list holding none rests on, and what it
   *  shows, in one sentence. */
  function basisLine(b) {
    return '<p class="measures-source">' + link(b.url, b.title) + ", read " + day(b.read) + ", " +
      esc(b.found) + "." + (b.words ? " In its own words: “" + esc(b.words) + "”." : "") + "</p>";
  }

  function isAre(n, past) {
    return n === 1 ? (past ? "was" : "is") : (past ? "were" : "are");
  }

  /** The words for one part of a county: the county's own questions
   *  (*who* "of Harris County or of a district covering the whole county")
   *  or a city's ("of the City of Houston"). */
  function partBody(part, who, read, office, level, past) {
    var out = [];
    var on = " on the Nov 3, 2026 ballot";
    var b = part.basis ? Object.assign({ read: read }, part.basis) : null;
    if (part.status === "listed") {
      var n = part.measures.length;
      out.push('<p class="measures-lead">' + (n === 1 ? "One question " : n + " questions ") +
        esc(who) + " " + isAre(n, past) + on + ":</p>");
      out.push(list(part.measures, level));
      if (part.partial) out.push('<p class="measure-note local-partial">' + esc(part.partial) + "</p>");
    } else if (part.status === "none" && b && b.from === "noGovernment") {
      // A county with no government puts no question; that says nothing of
      // the districts that cover it, which were not looked for (rule 19).
      out.push('<p class="measures-lead">' + esc(part.county || "This county") + " has no " +
        "county government to put a question" + on + ". This site " + (past ? "did" : "has") +
        " not look" + (past ? "" : "ed") + " for questions of districts covering the whole " +
        "county, and does not say there " + (past ? "were" : "are") + " none.</p>");
      out.push(basisLine(b));
    } else if (part.status === "none") {
      out.push('<p class="measures-lead">No question ' + esc(who) + " " + (past ? "was" : "is") +
        on + ".</p>");
      out.push(basisLine(b));
    } else if (part.status === "unlisted") {
      out.push('<p class="measures-lead">This site ' + (past ? "did" : "has") + " not " +
        (past ? "find" : "found") + " a question " + esc(who) + on + ", and does not say there " +
        (past ? "was" : "is") + " none: the document it read does not say in its own words that " +
        "it " + (past ? "held" : "holds") + " every contest.</p>");
      out.push(basisLine(b));
    } else if (part.status === "notFound") {
      out.push('<p class="measures-lead">This site ' + (past ? "did" : "has") + " not " +
        (past ? "find" : "found") + " an official list of the questions " + esc(who) + on +
        ", and does not say there " + (past ? "were" : "are") + " none. " + esc(part.why) +
        " The election office's own site: " + link(office.url, office.name) + ".</p>");
    }
    return out.join("");
  }

  /* ------------------------------------------------------- one county */

  /** One covered county's questions, as HTML. *opts.level*: the heading
   *  level of the city headings (questions take the next); *opts.head*: the
   *  county's own heading, or none. */
  function countyBody(fips, opts) {
    opts = opts || {};
    var rec = record(fips);
    var level = opts.level || 3;
    var past = held();
    if (!rec) {
      return '<p class="measures-lead measures-failed">The list of local questions for ' +
        esc((covered(fips) || [])[1] || "this county") + " did not load. Reload the page to try " +
        "again.</p>";
    }
    var out = [];
    var who = "of " + rec.name + " or of a district covering the whole county";
    if (rec.own.status === "same") {
      var same = rec.cities.filter(function (c) { return c.place === rec.own.city; })[0];
      out.push('<p class="measures-lead">' + esc(rec.name) + " and the " + esc(same ? same.name : "city") +
        " are one government; " + (past ? "its questions were" : "its questions are") +
        " listed under the city.</p>");
    } else {
      out.push(partBody(Object.assign({ county: rec.name }, rec.own), who, rec.read, rec.office,
        Math.min(level + 1, 6), past));
    }
    var skip = opts.skipPlaces || {};
    rec.cities.forEach(function (c) {
      // A city a ZIP code's other county already drew is drawn once.
      if (skip[c.place]) {
        out.push('<p class="faint local-drawn" data-place="' + KYC.escapeAttr(c.place) + '">' +
          "The " + esc(c.name) + "'s questions are under " + esc(skip[c.place]) + ", above.</p>");
        return;
      }
      skip[c.place] = rec.name;
      // Where its questions are recorded, never why: "most of the city is
      // in Kings County" was false of New York City.
      var lead = c.from ? '<p class="faint local-from">This site records the ' + esc(c.name) +
        "'s questions under " + esc(c.from.name) + ".</p>" : "";
      out.push('<section class="local-city" data-place="' + KYC.escapeAttr(c.place) + '">' +
        "<h" + level + ' class="local-city-name">If you live in the ' + esc(c.name) + "</h" + level + ">" +
        lead + partBody(c, "of the " + c.name, c.read || rec.read, rec.office, Math.min(level + 1, 6), past) +
        "</section>");
    });
    out.push('<p class="measures-words">Each question is quoted in its official words, as the ' +
      "office printed it. This site does not say what a yes or a no vote does; where the official " +
      "text says so, it is quoted." + (past ? " This site does not read the results of ballot " +
        "questions." : "") + "</p>");
    out.push('<p class="faint local-coverage">' + esc(coverageWords()) + "</p>");
    return out.join("");
  }

  /** What a county this site does not cover is told, beside its state's
   *  own sample ballot or election pages (*where*, HTML). */
  function uncoveredLine(name, where, code) {
    // A county area that is the place itself opens the sentence as the
    // place does (rule 75): "The District of Columbia is not among ...".
    var opening = code && KYC.placeWords(code, "") === "the " + name ? "The " + name : name;
    return '<p class="measures-local local-uncovered">' + esc(opening) + " is not among the " + TOTAL +
      " most populous counties this site lists local questions for, so its questions - the " +
      "county's, its cities' and its school and special districts' - are not listed here." +
      (where ? " " + where : "") + "</p>";
  }

  /** The index did not load: nothing can be said either way. */
  function missingLine() {
    return '<p class="measures-lead measures-failed">The list of local questions did not load, ' +
      "so this page cannot say whether this site lists any for this county. Reload the page to " +
      "try again.</p>";
  }

  /* One listener for every page that shows the questions: the fold opens
   * and closes in place. */
  doc.addEventListener("click", function (event) {
    var button = event.target && event.target.closest && event.target.closest("[data-local-more]");
    if (!button) return;
    var text = doc.getElementById(button.getAttribute("aria-controls"));
    if (!text) return;
    var open = button.getAttribute("aria-expanded") !== "true";
    button.setAttribute("aria-expanded", open ? "true" : "false");
    text.classList.toggle("is-folded", !open);
    button.textContent = open ? "Show less" : "Read the whole text";
  });

  KYC.localMeasures = {
    TOTAL: TOTAL,
    index: index,
    covered: covered,
    sampleLine: sampleLine,
    record: record,
    prepare: prepare,
    countyBody: countyBody,
    uncoveredLine: uncoveredLine,
    missingLine: missingLine,
    coverageWords: coverageWords,
    held: held,
  };
})(window);
