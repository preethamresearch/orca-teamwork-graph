/**
 * Orca shared answer renderer.
 *
 * Builds the answer DOM (markdown answer, meta tags, confidence meter,
 * reasoning trace, citations) from a /ask response object. Used by both the
 * popup and the in-page panel so they look identical.
 *
 * Returns a DocumentFragment. All text goes through OrcaMarkdown (which
 * escapes) or document.createTextNode — never raw innerHTML from the backend.
 *
 * Exposes window.OrcaRender.renderAnswer(data) -> DocumentFragment
 */
(function () {
  "use strict";

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function renderAnswer(data) {
    var frag = document.createDocumentFragment();

    if (data && data.refused) {
      frag.appendChild(el("span", "refused-badge", "Refused"));
    }

    // Answer markdown
    var md = el("div", "answer-md");
    var renderer =
      typeof window !== "undefined" && window.OrcaMarkdown
        ? window.OrcaMarkdown
        : null;
    if (renderer) {
      md.innerHTML = renderer.render(data && data.answer ? data.answer : "");
    } else {
      md.textContent = data && data.answer ? data.answer : "";
    }
    frag.appendChild(md);

    // Meta tags: intent / mode / refused
    var meta = el("div", "meta-grid");
    if (data && data.intent) meta.appendChild(el("span", "tag", "intent: " + data.intent));
    if (data && data.mode) meta.appendChild(el("span", "tag", "mode: " + data.mode));
    if (data && data.work_iq && data.work_iq.user && data.work_iq.user.displayName) {
      meta.appendChild(el("span", "tag", "as: " + data.work_iq.user.displayName));
    }
    if (meta.childNodes.length) frag.appendChild(meta);

    // Confidence meter
    if (data && typeof data.confidence === "number") {
      var conf = el("div", "section confidence");
      conf.appendChild(el("div", "section-title", "Confidence"));
      var bar = el("div", "confidence-bar");
      var fill = el("div", "confidence-fill");
      var pct = Math.max(0, Math.min(100, Math.round(data.confidence * 100)));
      fill.style.width = pct + "%";
      bar.appendChild(fill);
      conf.appendChild(bar);
      conf.appendChild(el("div", "confidence-label", pct + "% confident"));
      frag.appendChild(conf);
    }

    // Reasoning trace
    if (data && Array.isArray(data.reasoning_trace) && data.reasoning_trace.length) {
      var traceSec = el("div", "section");
      traceSec.appendChild(el("div", "section-title", "Reasoning trace"));
      var ol = el("ol", "trace");
      data.reasoning_trace.forEach(function (step) {
        var li = el("li");
        // trace strings may contain **bold** markdown; render inline-safely
        if (renderer) {
          li.innerHTML = renderer.render(String(step)).replace(/^<p>|<\/p>$/g, "");
        } else {
          li.textContent = String(step);
        }
        ol.appendChild(li);
      });
      traceSec.appendChild(ol);
      frag.appendChild(traceSec);
    }

    // Citations
    if (data && Array.isArray(data.citations) && data.citations.length) {
      var citeSec = el("div", "section");
      citeSec.appendChild(
        el("div", "section-title", "Citations (" + data.citations.length + ")")
      );
      data.citations.forEach(function (c) {
        var box = el("div", "citation");
        var head = el("div", "citation-head");
        var label = el("div", "citation-label");
        var n = el("span", "citation-n", "[" + (c.n != null ? c.n : "?") + "]");
        label.appendChild(n);
        label.appendChild(document.createTextNode(c.label || "Source"));
        head.appendChild(label);
        var metaParts = [];
        if (c.source) metaParts.push(c.source);
        if (typeof c.score === "number") metaParts.push("score " + c.score.toFixed(2));
        head.appendChild(el("span", "citation-meta", metaParts.join(" · ")));
        box.appendChild(head);
        if (c.excerpt) {
          box.appendChild(el("div", "citation-excerpt", c.excerpt));
        }
        citeSec.appendChild(box);
      });
      frag.appendChild(citeSec);
    }

    return frag;
  }

  var api = { renderAnswer: renderAnswer };
  if (typeof window !== "undefined") {
    window.OrcaRender = api;
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})();
