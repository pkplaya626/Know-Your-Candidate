/* Market prices and polling averages for a 2026 race (kyc/odds.py, emitted
 * as data/odds.js), rendered one way on every page that shows the race: the
 * grid's race view, the Senate view, the state pages, the map and the
 * profile dialog.
 *
 * Each source is quoted as it publishes itself and labelled as what it is.
 * Nothing here blends sources or computes a figure of its own: a market
 * price is what a trader pays for a $1 contract, a polling average is the
 * aggregator's, and the page says so beside them. */
(function (global) {
  "use strict";

  var KYC = global.KYC;
  if (!KYC) return;

  var SOURCE = {
    kalshi: ["Kalshi", "Kalshi, a CFTC-regulated exchange"],
    polymarket: ["Polymarket", "Polymarket, a prediction market"],
  };
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  // Outcomes priced under a cent are counted, not drawn: on Alaska's market
  // they are candidates the August primary already removed.
  var FLOOR = 0.01;

  function percent(price) {
    var value = price * 100;
    if (value >= 99.5) return ">99%";
    if (value < 1) return "<1%";
    return Math.round(value) + "%";
  }

  /** "2026-10-03T04:56:07+00:00" -> "Oct 3". */
  function day(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    return m ? MONTHS[+m[2] - 1] + " " + (+m[3]) : "";
  }

  function party(key) {
    return key === "d" || key === "r" ? key : "i";
  }

  /** data/odds.js, keyed by race id; absent on a page that does not load it. */
  function data() {
    return global.kycOdds || { races: {}, control: {} };
  }

  function link(url, label, title) {
    if (!url) return KYC.escapeHtml(label);
    return '<a href="' + KYC.escapeAttr(url) + '" target="_blank" rel="noopener noreferrer"' +
      (title ? ' title="' + KYC.escapeAttr(title) + '"' : "") + ">" +
      KYC.escapeHtml(label) + "</a>";
  }

  /* Prices that add up to far more or less than a dollar (Kalshi's WY-AL
   * read Gray 98% and Kinney 30%): a bar would rescale them into a split
   * neither number says, so the
   * prices are quoted as they are and say why there is no bar. The band is
   * validate's odds-incoherent band. Read here, page-side, so data/odds.js
   * stays a pure function of the cache (rule 41). */
  var COHERENT = [0.85, 1.2];

  function coherent(market) {
    var sum = (market.outcomes || []).reduce(function (s, o) { return s + (o.price || 0); }, 0);
    return { ok: sum >= COHERENT[0] && sum <= COHERENT[1], sum: sum };
  }

  /* An outcome that names a party, not a person: what a party-only market
   * resolves on. */
  var PARTY_LABEL = /^(?:(?:Democratic|Republican) [Pp]arty|Democrats?|Republicans?|Democratic|Independent|Other)$/;

  function partyOnly(market) {
    var outcomes = market.outcomes || [];
    return outcomes.length > 0 && outcomes.every(function (o) {
      return PARTY_LABEL.test(o.label) || !!o.mismatch;
    });
  }

  var PLURAL = { Democrat: "Democrats", Republican: "Republicans" };

  /** The one party everyone on the race's November ballot belongs to, or
   *  "": California's top two can be two Democrats (CA-4, CA-11), and a
   *  market on which party wins cannot tell them apart. Only once the
   *  primary is settled, only from profiles, and never when the results
   *  name someone on the ballot this site has no profile (and so no party)
   *  for. */
  function oneParty(race) {
    if (!race || !race.settled || !KYC.byId) return "";
    var res = race.results || {};
    if ((res.otherNominees || []).length) return "";
    var seen = {};
    var parties = {};
    var count = 0;
    (race.incumbentIds || []).concat(race.candidateIds || []).forEach(function (id) {
      var p = KYC.byId(id);
      if (!p || seen[p.id]) return;
      seen[p.id] = true;
      if (!p.isCandidate && (p.contestRaceId || p.raceId) !== race.id) return;
      var status = p.isCandidate ? p.raceStatus : KYC.contestStatus(p);
      if (!KYC.onNovemberBallot(status)) return;
      parties[p.party || ""] = true;
      count += 1;
    });
    var keys = Object.keys(parties);
    return count >= 2 && keys.length === 1 && PLURAL[keys[0]] ? keys[0] : "";
  }

  /** One market: its outcomes as a bar and a legend, its source linked. */
  function marketRow(market, race) {
    var source = SOURCE[market.source] || [market.source, market.source];
    var shown = (market.outcomes || []).filter(function (o) { return o.price >= FLOOR; });
    var hidden = (market.outcomes || []).length - shown.length;
    if (!shown.length) return "";
    var check = coherent(market);
    var same = partyOnly(market) ? oneParty(race) : "";
    // Only what is measured: the sum. The site holds no trading volume, so
    // it never says "thinly traded"; Kalshi's figures are last trades,
    // which can be old, while Polymarket's are its displayed prices, and a
    // sum short of 100% there may be an outcome it closed (PR #94 review).
    var notes = (check.ok ? "" : '<p class="odds-flag">' +
        (market.source === "kalshi" ? "These last-traded prices" : "These prices") + " add up to " +
        Math.round(check.sum * 100) + "%, not 100%, so they are quoted without a bar" +
        (market.source === "kalshi" ? "; they may be stale." : ".") + "</p>") +
      (same ? '<p class="odds-flag">Everyone on this November ballot is a ' + KYC.escapeHtml(same) +
        "; this market resolves on the party only, so it cannot tell them apart.</p>" : "");
    var total = shown.reduce(function (sum, o) { return sum + o.price; }, 0) || 1;
    var spoken = shown.map(function (o) { return o.label + " " + percent(o.price); }).join(", ");
    var bar = !check.ok ? "" : shown.map(function (o) {
      return '<span class="odds-seg odds-seg-' + party(o.party) + '" style="width:' +
        (100 * o.price / total).toFixed(1) + '%"></span>';
    }).join("");
    var legend = shown.map(function (o) {
      // A label that named nobody in the race is shown as its party, and
      // says what the market itself called it.
      var title = o.mismatch
        ? "The market labels this outcome “" + o.marketLabel + "”, who is not in this race; " +
          "it resolves on the party, so it is shown as the party."
        : o.question || "";
      return '<span class="odds-item" title="' + KYC.escapeAttr(title) + '">' +
        '<span class="odds-dot odds-seg-' + party(o.party) + '"></span>' +
        KYC.escapeHtml(o.label) + " <strong>" + percent(o.price) + "</strong></span>";
    }).join("");
    return '<div class="odds-market">' +
      '<span class="odds-source">' + link(market.url, source[0],
        source[1] + ": “" + (market.title || "") + "”") + "</span>" +
      (bar ? '<div class="odds-bar" role="img" aria-label="' +
        KYC.escapeAttr(source[0] + ": " + spoken) + '">' + bar + "</div>" : "") +
      '<div class="odds-legend">' + legend +
        (hidden ? '<span class="odds-item odds-faint">' + hidden + " more priced under 1%</span>" : "") +
      "</div>" + notes + "</div>";
  }

  var MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
                     "August", "September", "October", "November", "December"];

  /** "October 4, 2026" -> "2026-10-04", or "" when it is not a date. */
  function isoOf(text) {
    var m = /^([A-Z][a-z]+) (\d{1,2}), (\d{4})$/.exec(String(text || "").trim());
    var month = m ? MONTH_NAMES.indexOf(m[1]) : -1;
    if (month < 0) return "";
    return m[3] + "-" + (month < 9 ? "0" : "") + (month + 1) + "-" + (m[2].length < 2 ? "0" : "") + m[2];
  }

  /** The most recently updated average, for the one-line summary: the
   *  aggregators are listed in a fixed order, and the first was often the
   *  oldest (270toWin's Oct 4 beside averages of Oct 11; RACES-08). A row
   *  with no readable date never wins over one with a date. */
  function latest(rows) {
    return rows.reduce(function (best, row) {
      return isoOf(row.updated) > isoOf(best.updated) ? row : best;
    }, rows[0]);
  }

  /* --------------------------------------------------------- the polls */

  /** The candidates in the order the market bars above list them
   *  (VISUALS-34): Texas's markets put Talarico first and its polls Paxton,
   *  so a reader comparing the two read them crossed. A result is matched
   *  to a market outcome by the same profile id, or by party where that
   *  party is one candidate on each side; anyone unmatched keeps the
   *  aggregator's order, after them. Returns a sort key for a result. */
  function marketOrder(odds) {
    var outcomes = [];
    (odds.markets || []).some(function (m) {
      var shown = (m.outcomes || []).filter(function (o) { return o.price >= FLOOR; });
      if (shown.length && coherent(m).ok) { outcomes = shown; return true; }
      return false;
    });
    var once = function (list, key) {
      return list.filter(function (x) { return party(x.party) === key; }).length === 1;
    };
    return function (result, results) {
      for (var i = 0; i < outcomes.length; i++) {
        var o = outcomes[i];
        if (o.id && result.id && o.id === result.id) return i;
      }
      for (var j = 0; j < outcomes.length; j++) {
        var p = party(outcomes[j].party);
        if (p !== "i" && p === party(result.party) && once(outcomes, p) && once(results, p)) return j;
      }
      return outcomes.length + results.indexOf(result);
    };
  }

  function ordered(results, key) {
    return results.slice().sort(function (a, b) { return key(a, results) - key(b, results); });
  }

  var MARKS = ["poll-dot-fill", "poll-dot-ring", "poll-dot-square", "poll-dot-diamond"];

  /* The narrowest axis the dots are drawn on, in points. */
  var SPAN = 30;

  /** Each aggregator's average as dots on one shared axis, one row each:
   *  a party's colour and, for whoever cannot tell the colours apart, a
   *  shape per candidate, named in the key. The axis spans the figures
   *  shown, rounded out to fives, and never less than thirty points: on a
   *  ten-point axis Maine's 49.7 against 47.4 looked like a wide gap (PR
   *  #111 review). Every number is page text in the table beside it. */
  function pollDots(rows, key) {
    if (!rows.length) return "";
    var all = [];
    rows.forEach(function (row) { row.results.forEach(function (r) { all.push(r.pct); }); });
    var lo = Math.max(0, Math.floor((Math.min.apply(null, all) - 2) / 5) * 5);
    var hi = Math.min(100, Math.ceil((Math.max.apply(null, all) + 2) / 5) * 5);
    if (hi - lo < SPAN) {
      lo = Math.max(0, Math.floor(((lo + hi) / 2 - SPAN / 2) / 5) * 5);
      hi = Math.min(100, lo + SPAN);
      lo = Math.min(lo, hi - SPAN);
    }
    var at = function (v) { return (100 * (v - lo) / (hi - lo)).toFixed(2) + "%"; };
    var names = ordered(rows[0].results, key);
    var mark = function (r) {
      var i = names.map(function (n) { return n.label; }).indexOf(r.label);
      return MARKS[(i < 0 ? names.length : i) % MARKS.length];
    };
    var ticks = [];
    for (var t = lo; t <= hi; t += (hi - lo > SPAN ? 10 : 5)) ticks.push(t);
    var body = rows.map(function (row) {
      var spoken = row.aggregator + ": " + ordered(row.results, key).map(function (r) {
        return r.label + " " + r.pct.toFixed(1) + "%";
      }).join(", ");
      return '<li class="poll-row"><span class="poll-name">' + KYC.escapeHtml(row.aggregator) + "</span>" +
        '<span class="poll-track" role="img" aria-label="' + KYC.escapeAttr(spoken) + '" title="' +
        KYC.escapeAttr(spoken) + '">' + ordered(row.results, key).map(function (r) {
          return '<span class="poll-dot ' + mark(r) + " odds-seg-" + party(r.party) + '" style="left:' +
            at(r.pct) + '"></span>';
        }).join("") + "</span></li>";
    }).join("");
    return '<div class="poll-dots">' +
      '<ul class="poll-key">' + names.map(function (r) {
        return '<li><span class="poll-dot ' + mark(r) + " odds-seg-" + party(r.party) +
          '" aria-hidden="true"></span>' + KYC.escapeHtml(r.label) + "</li>";
      }).join("") + "</ul>" +
      '<ul class="poll-rows">' + body + "</ul>" +
      '<div class="poll-axis" aria-hidden="true"><span class="poll-name"></span><span class="poll-ticks">' +
      ticks.map(function (v) { return '<span style="left:' + at(v) + '">' + v + "%</span>"; }).join("") +
      "</span></div></div>";
  }

  /** The polling averages, as each aggregator published them. */
  function pollTable(polls, key) {
    var rows = (polls && polls.rows) || [];
    if (!rows.length) return "";
    var columns = ordered(rows[0].results, key);
    var heads = columns.map(function (r) {
      return '<th scope="col" class="party-' + party(r.party) + '">' + KYC.escapeHtml(r.label) + "</th>";
    }).join("");
    var body = rows.map(function (row) {
      var best = Math.max.apply(null, row.results.map(function (r) { return r.pct; }));
      // Each row's figures under the columns' names, whatever order the
      // aggregator gave them in.
      var cells = columns.map(function (c, i) {
        return row.results.filter(function (r) { return r.label === c.label; })[0] ||
          row.results[rows[0].results.indexOf(c)] || row.results[i];
      });
      return "<tr><th scope=\"row\">" + link(row.url, row.aggregator) + "</th>" +
        cells.map(function (r) {
          var text = r.pct.toFixed(1);
          return "<td>" + (r.pct === best ? "<strong>" + text + "</strong>" : text) + "</td>";
        }).join("") +
        '<td class="odds-faint">' + KYC.escapeHtml(row.updated || "") + "</td></tr>";
    }).join("");
    return '<div class="odds-polls">' +
      '<p class="odds-subhead">Polling averages <span class="odds-faint">' +
        link(polls.url, "as listed on Wikipedia", polls.page) + "</span></p>" + pollDots(rows, key) +
      '<div class="odds-scroll"><table class="odds-poll-table"><thead><tr><th scope="col">Average</th>' +
        heads + '<th scope="col">Updated</th></tr></thead><tbody>' + body +
      "</tbody></table></div></div>";
  }

  /** The race's block. *opts.compact* drops the poll table for one line. */
  function render(race, opts) {
    var odds = race && (data().races || {})[race.id];
    if (!odds) return "";
    opts = opts || {};
    var markets = (odds.markets || []).map(function (m) { return marketRow(m, race); })
      .filter(Boolean);
    var polls = odds.polls && odds.polls.rows && odds.polls.rows.length ? odds.polls : null;
    if (!markets.length && !polls) return "";
    var pollHtml = "";
    var key = marketOrder(odds);
    if (polls && opts.compact) {
      var first = latest(polls.rows);
      var when = day(isoOf(first.updated));
      pollHtml = '<p class="odds-line"><span class="odds-source">Polls</span> ' +
        ordered(first.results, key).map(function (r) {
          return '<span class="party-' + party(r.party) + '">' + KYC.escapeHtml(r.label) + " " +
            r.pct.toFixed(1) + "</span>";
        }).join(" · ") +
        ' <span class="odds-faint">(' + link(first.url, first.aggregator) +
        (when ? ", updated " + KYC.escapeHtml(when) : "") +
        (polls.rows.length > 1 ? "; " + (polls.rows.length - 1) + " more average" +
          (polls.rows.length > 2 ? "s" : "") : "") + ")</span></p>";
    } else if (polls) {
      pollHtml = pollTable(polls, key);
    }
    return '<section class="odds' + (opts.compact ? " odds-compact" : "") + '" aria-label="' +
      KYC.escapeAttr("Prediction markets and polling averages for " + (race.label || "this race")) + '">' +
      '<p class="odds-subhead">' + (finalPrices() ? FINAL_HEAD : "Prediction markets") +
        ' <span class="odds-faint">as of ' + KYC.escapeHtml(day(data().asOf)) + "</span></p>" +
      markets.join("") + pollHtml +
      '<p class="odds-note">A market price is what traders pay for a contract worth $1 if that ' +
        "outcome happens. It is not a poll, and not this site’s forecast. Polling averages " +
        "are each aggregator’s own" + (polls ? ", drawn as published, and not this site’s forecast either" : "") +
        "." + (finalPrices() ? FINAL_NOTE : "") + "</p>" +
      "</section>";
  }

  /* From Election Day on, these are the last prices read before the first
   * polls closed (odds.yml stops there), and the page says so: prices that
   * move on early returns would read as results beside "On the November
   * ballot". */
  var FINAL_HEAD = "Final market prices, from before the polls closed";
  var FINAL_NOTE = " These are not results.";
  function finalPrices(now) {
    return KYC.electionStatus(undefined, now).phase !== "campaign";
  }

  var CHAMBER = { senate: "the Senate", house: "the House" };

  /** Which party the markets expect to control *chamber* ("senate", "house"). */
  function control(chamber) {
    var markets = (data().control || {})[chamber] || [];
    if (!markets.length) return "";
    var name = CHAMBER[chamber] || chamber;
    return '<section class="odds odds-control" aria-label="' +
        KYC.escapeAttr("Prediction markets on control of " + name) + '">' +
      '<p class="odds-subhead">Control of ' + KYC.escapeHtml(name) +
        " after November, by prediction market" + (finalPrices() ? ": final prices, from before the polls closed" : "") +
        ' <span class="odds-faint">as of ' + KYC.escapeHtml(day(data().asOf)) + "</span></p>" +
      markets.map(function (m) { return marketRow(m, null); }).join("") +
      '<p class="odds-note">What traders pay for a $1 contract on each party winning a majority. ' +
        "Not a poll, and not this site’s forecast." + (finalPrices() ? FINAL_NOTE : "") +
        "</p></section>";
  }

  KYC.odds = { render: render, control: control, percent: percent, finalPrices: finalPrices };
})(window);
