/**
 * Orca in-page panel (content script).
 *
 * Injects a floating, draggable side panel that can be toggled via:
 *   - the keyboard command (routed through background.js)
 *   - a message from the popup ("Open in-page panel")
 *
 * Supports grounding answers in the user's current text selection by sending
 * it as `page_context` when the "Use page selection" checkbox is on.
 *
 * Renders answers using the shared OrcaRender + OrcaMarkdown helpers.
 */
(function () {
  "use strict";

  // Guard against double-injection (content script + programmatic injection).
  if (window.__oracleInjected) {
    // Already present — just toggle if asked via the listener below.
  } else {
    window.__oracleInjected = true;
  }

  const DEFAULT_BASE_URL = "http://127.0.0.1:8000";
  const PANEL_ID = "oracle-panel-root";

  function getBaseUrl() {
    return new Promise((resolve) => {
      try {
        chrome.storage.sync.get(["baseUrl"], (res) => {
          resolve((res && res.baseUrl) || DEFAULT_BASE_URL);
        });
      } catch (e) {
        resolve(DEFAULT_BASE_URL);
      }
    });
  }

  function buildPanel() {
    const root = document.createElement("div");
    root.id = PANEL_ID;
    root.className = "oracle-panel";
    root.innerHTML = [
      '<div class="oracle-header" id="oracle-drag">',
      '  <div class="oracle-brand"><span class="oracle-logo">◎</span> Orca</div>',
      '  <div class="oracle-status" id="oracle-status">checking…</div>',
      '  <button class="oracle-x" id="oracle-close" title="Close">×</button>',
      "</div>",
      '<div class="oracle-body">',
      '  <textarea class="oracle-q" id="oracle-q" rows="2" placeholder="Ask Orca about your teamwork graph…"></textarea>',
      '  <div class="oracle-controls">',
      '    <label class="oracle-check"><input type="checkbox" id="oracle-usesel" /> Use page selection</label>',
      '    <button class="oracle-ask" id="oracle-ask">Ask</button>',
      "  </div>",
      '  <div class="oracle-selnote" id="oracle-selnote"></div>',
      '  <div class="oracle-result" id="oracle-result" hidden></div>',
      "</div>",
    ].join("");
    return root;
  }

  let panel = null;

  function $(id) {
    return panel ? panel.querySelector("#" + id) : null;
  }

  async function checkHealth() {
    const statusEl = $("oracle-status");
    if (!statusEl) return;
    const baseUrl = (await getBaseUrl()).replace(/\/+$/, "");
    try {
      const res = await fetch(baseUrl + "/health");
      if (!res.ok) throw new Error();
      const data = await res.json();
      statusEl.textContent = "● " + (data.mode || "connected");
      statusEl.className = "oracle-status ok";
    } catch (e) {
      statusEl.textContent = "● offline";
      statusEl.className = "oracle-status down";
    }
  }

  function currentSelection() {
    const sel = window.getSelection ? String(window.getSelection()) : "";
    return sel ? sel.trim() : "";
  }

  function showLoading() {
    const r = $("oracle-result");
    r.hidden = false;
    r.className = "oracle-result";
    r.textContent = "";
    const wrap = document.createElement("div");
    wrap.className = "oracle-loading";
    const spin = document.createElement("div");
    spin.className = "oracle-spinner";
    wrap.appendChild(spin);
    wrap.appendChild(document.createTextNode("Consulting the Teamwork Graph…"));
    r.appendChild(wrap);
  }

  function showError(msg) {
    const r = $("oracle-result");
    r.hidden = false;
    r.className = "oracle-result";
    r.textContent = "";
    const e = document.createElement("div");
    e.className = "oracle-error";
    e.textContent = "Error: " + msg;
    r.appendChild(e);
  }

  function showAnswer(data) {
    const r = $("oracle-result");
    r.hidden = false;
    r.className = "oracle-result" + (data && data.refused ? " refused" : "");
    r.textContent = "";
    r.appendChild(window.OrcaRender.renderAnswer(data));
  }

  async function ask() {
    const qEl = $("oracle-q");
    const question = (qEl.value || "").trim();
    if (!question) return;

    const usesel = $("oracle-usesel").checked;
    let pageContext = "";
    if (usesel) {
      pageContext = currentSelection();
      if (!pageContext && panel.__lastSelection) {
        pageContext = panel.__lastSelection;
      }
    }

    const askBtn = $("oracle-ask");
    askBtn.disabled = true;
    showLoading();

    const baseUrl = (await getBaseUrl()).replace(/\/+$/, "");
    try {
      const body = { question: question };
      if (pageContext) body.page_context = pageContext;
      const res = await fetch(baseUrl + "/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      showAnswer(data);
    } catch (err) {
      showError(
        (err && err.message ? err.message : String(err)) +
          " — is the backend running at " +
          baseUrl +
          "?"
      );
    } finally {
      askBtn.disabled = false;
    }
  }

  function updateSelNote() {
    const note = $("oracle-selnote");
    if (!note) return;
    const usesel = $("oracle-usesel").checked;
    if (!usesel) {
      note.textContent = "";
      return;
    }
    const sel = currentSelection() || panel.__lastSelection || "";
    if (sel) {
      const preview = sel.length > 80 ? sel.slice(0, 80) + "…" : sel;
      note.textContent = "Grounding on selection: “" + preview + "”";
      note.className = "oracle-selnote active";
    } else {
      note.textContent = "No text selected on the page yet.";
      note.className = "oracle-selnote";
    }
  }

  function makeDraggable(handle, target) {
    let startX, startY, origLeft, origTop, dragging = false;
    handle.addEventListener("mousedown", (e) => {
      if (e.target.closest(".oracle-x")) return;
      dragging = true;
      const rect = target.getBoundingClientRect();
      origLeft = rect.left;
      origTop = rect.top;
      startX = e.clientX;
      startY = e.clientY;
      target.style.right = "auto";
      target.style.left = origLeft + "px";
      target.style.top = origTop + "px";
      e.preventDefault();
    });
    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      target.style.left = Math.max(0, origLeft + dx) + "px";
      target.style.top = Math.max(0, origTop + dy) + "px";
    });
    window.addEventListener("mouseup", () => {
      dragging = false;
    });
  }

  function ensurePanel() {
    if (panel && document.body.contains(panel)) return panel;
    panel = buildPanel();
    document.body.appendChild(panel);

    $("oracle-close").addEventListener("click", hidePanel);
    $("oracle-ask").addEventListener("click", ask);
    $("oracle-q").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        ask();
      }
    });
    $("oracle-usesel").addEventListener("change", updateSelNote);

    makeDraggable($("oracle-drag"), panel);
    checkHealth();
    return panel;
  }

  // Remember the last non-empty selection so it survives focusing the textarea
  // (which clears the page selection).
  document.addEventListener("selectionchange", () => {
    const sel = currentSelection();
    if (panel && sel) {
      panel.__lastSelection = sel;
      if ($("oracle-usesel") && $("oracle-usesel").checked) updateSelNote();
    }
  });

  function showPanel() {
    ensurePanel();
    panel.classList.add("open");
    // Pre-fill selection if user already has text highlighted.
    const sel = currentSelection();
    if (sel) {
      panel.__lastSelection = sel;
      $("oracle-usesel").checked = true;
      updateSelNote();
    }
    setTimeout(() => $("oracle-q") && $("oracle-q").focus(), 50);
  }

  function hidePanel() {
    if (panel) panel.classList.remove("open");
  }

  function togglePanel() {
    if (panel && panel.classList.contains("open")) {
      hidePanel();
    } else {
      showPanel();
    }
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg && msg.type === "ORACLE_TOGGLE_PANEL") {
      togglePanel();
      sendResponse && sendResponse({ ok: true });
    }
    return false;
  });
})();
