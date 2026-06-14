# Orca — Teamwork Graph (Chrome Extension)

A Manifest V3 Chrome extension that brings **Orca — the Teamwork Graph for AI agents** into any web page. Ask Orca from a toolbar popup or from a floating in-page panel, and ground answers in the text you're currently reading.

## Prerequisites

The Orca FastAPI backend must be running locally at **http://127.0.0.1:8000** (default). It exposes:

- `POST /ask` — `{ "question": "...", "page_context": "<optional selected text>" }`
- `GET /health` — connection/mode status

If your backend runs elsewhere, change the base URL in the popup's **Settings** (it is stored in `chrome.storage.sync`). `http://localhost:8000` is also pre-authorized.

## Load the extension (unpacked)

1. Open `chrome://extensions` in Chrome.
2. Toggle **Developer mode** (top-right) on.
3. Click **Load unpacked**.
4. Select this folder: `oracle/extension`.

The Orca icon appears in the toolbar.

## How to use

### Popup
Click the toolbar icon. Type a question (or click an example chip) and hit **Ask** (or Cmd/Ctrl+Enter). You'll get:
- the markdown answer,
- a **confidence meter**,
- the **reasoning trace** as a numbered list,
- **citations** with source, score, and excerpt.
- a **status pill** showing the backend mode + graph size (from `/health`).
- Refused answers are styled distinctly with a "Refused" badge.

### In-page panel
Press the keyboard shortcut to toggle a floating, **draggable** side panel on the current page:

- **macOS:** `Cmd + Shift + O`
- **Windows/Linux:** `Ctrl + Shift + O`

You can also open it from the popup via **"Open in-page panel"**. (If the shortcut conflicts with another extension, remap it at `chrome://extensions/shortcuts`.)

### Page-selection grounding
Select any text on the page, then open the panel. The **"Use page selection"** checkbox turns on automatically and your highlighted text is sent as `page_context`, so the answer is grounded in what you're reading. The panel remembers your last selection even after you click into the question box.

## Files

| File | Purpose |
|------|---------|
| `manifest.json` | MV3 manifest (action popup, content script on `<all_urls>`, service worker, keyboard command, host permissions) |
| `background.js` | Service worker — routes the keyboard command + popup request to toggle the in-page panel; seeds default base URL |
| `popup.html` / `popup.css` / `popup.js` | Toolbar popup UI |
| `content.js` / `content.css` | In-page draggable panel + page-selection grounding |
| `lib/markdown.js` | Tiny, dependency-free, HTML-escaping markdown renderer |
| `lib/render.js` | Shared answer renderer (markdown, confidence, trace, citations) used by popup + panel |
| `icons/` | Toolbar icons (16/48/128) |

## Security / CSP notes

- No remote scripts or CDNs — MV3 CSP forbids them, so everything is bundled locally.
- The markdown renderer **escapes all HTML first**, then re-applies a small whitelist (bold, italics, inline/block code, headings, lists, http(s) links). Only the backend's answer text is ever rendered as markdown; arbitrary page content is never injected as HTML.

## Caveats

- **Icons are simple placeholders** (a dark tile with an accent ring) generated programmatically. Replace `icons/icon{16,48,128}.png` with branded art for production.
- The panel cannot be injected on restricted pages (`chrome://*`, the Chrome Web Store, etc.) — Chrome blocks content scripts there.
- The extension targets a **local** backend on port 8000 by default; for a remote backend, update the base URL in Settings and add the host to `host_permissions` in `manifest.json`.
