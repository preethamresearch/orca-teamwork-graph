/**
 * Orca service worker (MV3).
 *
 * Responsibilities:
 *  - Handle the keyboard command -> tell the active tab's content script to
 *    toggle the in-page panel.
 *  - Provide a fallback that injects the content script if it isn't present yet
 *    (e.g. tabs opened before the extension was installed/reloaded).
 *  - Seed the default backend base URL on install.
 */

const DEFAULT_BASE_URL = "http://127.0.0.1:8000";

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(["baseUrl"], (res) => {
    if (!res || !res.baseUrl) {
      chrome.storage.sync.set({ baseUrl: DEFAULT_BASE_URL });
    }
  });
});

async function togglePanelInTab(tabId) {
  try {
    await chrome.tabs.sendMessage(tabId, { type: "ORACLE_TOGGLE_PANEL" });
  } catch (err) {
    // Content script not loaded on this tab yet — inject then retry.
    try {
      await chrome.scripting.insertCSS({
        target: { tabId },
        files: ["content.css"],
      });
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["lib/markdown.js", "lib/render.js", "content.js"],
      });
      await chrome.tabs.sendMessage(tabId, { type: "ORACLE_TOGGLE_PANEL" });
    } catch (e) {
      // Likely a restricted page (chrome://, web store, etc.) where we cannot inject.
      console.warn("Orca: cannot toggle panel on this tab.", e);
    }
  }
}

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "toggle-panel") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab && tab.id != null) {
    togglePanelInTab(tab.id);
  }
});

// Allow the popup to ask us to open the in-page panel in the active tab.
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "ORACLE_OPEN_PANEL_FROM_POPUP") {
    chrome.tabs
      .query({ active: true, currentWindow: true })
      .then(([tab]) => {
        if (tab && tab.id != null) {
          togglePanelInTab(tab.id);
        }
        sendResponse({ ok: true });
      })
      .catch(() => sendResponse({ ok: false }));
    return true; // async response
  }
});
