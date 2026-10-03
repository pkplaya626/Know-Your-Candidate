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

  /** One market: its outcomes as a bar and a legend, its source linked. */
  function marketRow(market) {
    var source = SOURCE[market.source] || [market.source, market.source];
    var shown = (market.outcomes || []).filter(function (o) { return o.price >= FLOOR; });
    var hidden = (market.outcomes || []).length - shown.length;
    if (!shown.length) return "";
    var total = shown.reduce(function (sum, o) { return sum + o.price; }, 0) || 1;
    var spoken = shown.map(function (o) { return o.label + " " + percent(o.price); }).join(", ");
    var bar = shown.map(function (o) {
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
      '<div class="odds-bar" role="img" aria-label="' +
        KYC.escapeAttr(source[0] + ": " + spoken) + '">' + bar + "</div>" +
      '<div class="odds-legend">' + legend +
        (hidden ? '<span class="odds-item odds-faint">' + hidden + " more under 1%</span>" : "") +
      "</div></div>";
  }

  /** The polling averages, as each aggregator published them. */
  function pollTable(polls) {
    var rows = (polls && polls.rows) || [];
    if (!rows.length) return "";
    var heads = rows[0].results.map(function (r) {
      return '<th scope="col" class="party-' + party(r.party) + '">' + KYC.escapeHtml(r.label) + "</th>";
    }).join("");
    var body = rows.map(function (row) {
      var best = Math.max.apply(null, row.results.map(function (r) { return r.pct; }));
      return "<tr><th scope=\"row\">" + link(row.url, row.aggregator) + "</th>" +
        row.results.map(function (r) {
          var text = r.pct.toFixed(1);
          return "<td>" + (r.pct === best ? "<strong>" + text + "</strong>" : text) + "</td>";
        }).join("") +
        '<td class="odds-faint">' + KYC.escapeHtml(row.updated || "") + "</td></tr>";
    }).join("");
    return '<div class="odds-polls">' +
      '<p class="odds-subhead">Polling averages <span class="odds-faint">' +
        link(polls.url, "as listed on Wikipedia", polls.page) + "</span></p>" +
      '<div class="odds-scroll"><table class="odds-poll-table"><thead><tr><th scope="col">Average</th>' +
        heads + '<th scope="col">Updated</th></tr></thead><tbody>' + body +
      "</tbody></table></div></div>";
  }

  /** The race's block. *opts.compact* drops the poll table for one line. */
  function render(race, opts) {
    var odds = race && (data().races || {})[race.id];
    if (!odds) return "";
    opts = opts || {};
    var markets = (odds.markets || []).map(marketRow).filter(Boolean);
    var polls = odds.polls && odds.polls.rows && odds.polls.rows.length ? odds.polls : null;
    if (!markets.length && !polls) return "";
    var pollHtml = "";
    if (polls && opts.compact) {
      var first = polls.rows[0];
      pollHtml = '<p class="odds-line"><span class="odds-source">Polls</span> ' +
        first.results.map(function (r) {
          return '<span class="party-' + party(r.party) + '">' + KYC.escapeHtml(r.label) + " " +
            r.pct.toFixed(1) + "</span>";
        }).join(" · ") +
        ' <span class="odds-faint">(' + link(first.url, first.aggregator) +
        (polls.rows.length > 1 ? " + " + (polls.rows.length - 1) + " more" : "") + ")</span></p>";
    } else if (polls) {
      pollHtml = pollTable(polls);
    }
    return '<section class="odds' + (opts.compact ? " odds-compact" : "") + '" aria-label="' +
      KYC.escapeAttr("Prediction markets and polling averages for " + (race.label || "this race")) + '">' +
      '<p class="odds-subhead">Prediction markets <span class="odds-faint">as of ' +
        KYC.escapeHtml(day(data().asOf)) + "</span></p>" +
      markets.join("") + pollHtml +
      '<p class="odds-note">A market price is what traders pay for a contract worth $1 if that ' +
        "outcome happens. It is not a poll, and not this site’s forecast. Polling averages " +
        "are each aggregator’s own.</p>" +
      "</section>";
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
        ' after November, by prediction market <span class="odds-faint">as of ' +
        KYC.escapeHtml(day(data().asOf)) + "</span></p>" +
      markets.map(marketRow).join("") +
      '<p class="odds-note">What traders pay for a $1 contract on each party winning a majority. ' +
        "Not a poll, and not this site’s forecast.</p></section>";
  }

  KYC.odds = { render: render, control: control, percent: percent };
})(window);
