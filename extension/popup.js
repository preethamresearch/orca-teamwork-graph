/**
 * Orca popup logic.
 *
 * - Loads/saves the backend base URL from chrome.storage.sync.
 * - Polls /health to show a connection status pill.
 * - POSTs /ask and renders the answer via OrcaRender.
 */
(function () {
  "use strict";

  const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

  const $ = (id) => document.getElementById(id);
  const questionEl = $("question");
  const askBtn = $("askBtn");
  const resultEl = $("result");
  const statusDot = $("statusDot");
  const statusText = $("statusText");
  const baseUrlEl = $("baseUrl");
  const saveUrlBtn = $("saveUrlBtn");
  const settingsHint = $("settingsHint");
  const openPanelBtn = $("openPanelBtn");

  let baseUrl = DEFAULT_BASE_URL;

  function getBaseUrl() {
    return new Promise((resolve) => {
      chrome.storage.sync.get(["baseUrl"], (res) => {
        resolve((res && res.baseUrl) || DEFAULT_BASE_URL);
      });
    });
  }

  function setBaseUrl(url) {
    return new Promise((resolve) => {
      chrome.storage.sync.set({ baseUrl: url }, resolve);
    });
  }

  async function checkHealth() {
    statusDot.className = "dot";
    statusText.textContent = "checking…";
    try {
      const res = await fetch(baseUrl.replace(/\/+$/, "") + "/health", {
        method: "GET",
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      statusDot.className = "dot ok";
      const nodes = data.graph && data.graph.nodes != null ? data.graph.nodes : "?";
      const edges = data.graph && data.graph.edges != null ? data.graph.edges : "?";
      statusText.textContent =
        (data.mode || "connected") + " · " + nodes + "n/" + edges + "e";
    } catch (err) {
      statusDot.className = "dot down";
      statusText.textContent = "offline";
    }
  }

  function showLoading() {
    resultEl.hidden = false;
    resultEl.className = "result";
    resultEl.textContent = "";
    const wrap = document.createElement("div");
    wrap.className = "loading";
    const spin = document.createElement("div");
    spin.className = "spinner";
    wrap.appendChild(spin);
    wrap.appendChild(document.createTextNode("Consulting the Teamwork Graph…"));
    resultEl.appendChild(wrap);
  }

  function showError(msg) {
    resultEl.hidden = false;
    resultEl.className = "result";
    resultEl.textContent = "";
    const e = document.createElement("div");
    e.className = "error";
    e.textContent = "Error: " + msg;
    resultEl.appendChild(e);
  }

  function showAnswer(data) {
    resultEl.hidden = false;
    resultEl.className = "result" + (data && data.refused ? " refused" : "");
    resultEl.textContent = "";
    resultEl.appendChild(window.OrcaRender.renderAnswer(data));
  }

  async function ask(question) {
    if (!question || !question.trim()) return;
    askBtn.disabled = true;
    showLoading();
    try {
      const res = await fetch(baseUrl.replace(/\/+$/, "") + "/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: question.trim() }),
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

  // ---- wiring ----
  askBtn.addEventListener("click", () => ask(questionEl.value));

  questionEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      ask(questionEl.value);
    }
  });

  document.getElementById("examples").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    const q = chip.getAttribute("data-q");
    questionEl.value = q;
    ask(q);
  });

  saveUrlBtn.addEventListener("click", async () => {
    const url = (baseUrlEl.value || "").trim() || DEFAULT_BASE_URL;
    await setBaseUrl(url);
    baseUrl = url;
    settingsHint.textContent = "Saved.";
    setTimeout(() => (settingsHint.textContent = ""), 1500);
    checkHealth();
  });

  openPanelBtn.addEventListener("click", () => {
    chrome.runtime.sendMessage({ type: "ORACLE_OPEN_PANEL_FROM_POPUP" }, () => {
      // close popup so the in-page panel is visible
      window.close();
    });
  });

  // ---- init ----
  (async function init() {
    baseUrl = await getBaseUrl();
    baseUrlEl.value = baseUrl;
    checkHealth();
    questionEl.focus();
  })();
})();
