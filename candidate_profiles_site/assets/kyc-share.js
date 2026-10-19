/* Know Your Candidate - a share page (p/<id>.html, r/<raceId>.html; rule 96).
 *
 * A share page exists for the crawlers that unfurl a link, which drop the
 * "#/profile/<id>" a view lives behind: it carries the person's or the
 * race's own title, description and image, and the facts in plain text.
 * A reader with scripts is sent straight on to the view the page links
 * (#shareView), replacing the share page in the history so Back leaves
 * the site's view, not a page that sends them forward again. A reader
 * without scripts, and a crawler, stay and read the facts: a meta refresh
 * would have sent them to a view that needs this very JavaScript.
 */
(function (global) {
  "use strict";
  var link = global.document.getElementById("shareView");
  if (link && link.href) global.location.replace(link.href);
})(window);
