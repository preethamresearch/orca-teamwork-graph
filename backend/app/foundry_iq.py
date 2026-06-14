"""Foundry IQ — grounded retrieval layer.

In **live mode** this queries an Azure AI Search index that backs a Foundry IQ
knowledge base (hybrid semantic + vector retrieval with reranking).

In **local-demo mode** it provides an equivalent, dependency-free grounded
retriever over the bundled enterprise knowledge base: documents are split into
section chunks and scored with a TF-IDF-style ranker so the demo reproduces the
"retrieve → rank → ground → cite" behaviour without any cloud calls.

Either way, the rest of the agent consumes the same `Chunk` objects, so swapping
to live Foundry IQ is a config change, not a code change.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from .config import MOCK_DATA_DIR, settings

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "to", "of", "and", "or", "is", "are", "in", "on", "for",
    "with", "how", "do", "i", "my", "we", "you", "can", "what", "when", "be",
    "this", "that", "it", "as", "at", "by", "from", "if", "your", "our",
}


def _tok(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]


@dataclass
class Chunk:
    doc_id: str
    title: str
    section: str
    text: str
    score: float = 0.0

    @property
    def citation_label(self) -> str:
        return f"{self.title} — {self.section}"


def _split_sections(doc_id: str, title: str, body: str) -> list[Chunk]:
    """Split a markdown doc into one chunk per `##` section."""
    chunks: list[Chunk] = []
    current_section = "Overview"
    buf: list[str] = []

    def flush():
        if buf:
            text = "\n".join(buf).strip()
            if text:
                chunks.append(Chunk(doc_id, title, current_section, text))

    for line in body.splitlines():
        if line.startswith("## "):
            flush()
            current_section = line[3:].strip()
            buf = []
        elif line.startswith("# "):
            continue  # doc title, already captured
        else:
            buf.append(line)
    flush()
    return chunks


@lru_cache(maxsize=1)
def _load_corpus() -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(MOCK_DATA_DIR.glob("kb_*.md")):
        body = path.read_text(encoding="utf-8")
        first = body.splitlines()[0] if body.splitlines() else path.stem
        title = first[2:].strip() if first.startswith("# ") else path.stem
        chunks.extend(_split_sections(path.stem, title, body))
    return chunks


def _chunks_from_documents(documents: list[dict]) -> list[Chunk]:
    """Build retrieval chunks from workspace documents (each split into sections)."""
    chunks: list[Chunk] = []
    for d in documents:
        title = d.get("title") or d.get("id") or "Document"
        body = d.get("content", "") or ""
        if "## " in body or body.startswith("# "):
            chunks.extend(_split_sections(d.get("id", title), title, body))
        else:
            chunks.append(Chunk(d.get("id", title), title, "", body))
    return chunks


def _idf_for(corpus: list[Chunk]) -> dict[str, float]:
    n = len(corpus) or 1
    df: Counter[str] = Counter()
    for c in corpus:
        for w in set(_tok(c.text)):
            df[w] += 1
    return {w: math.log((n + 1) / (d + 0.5)) for w, d in df.items()}


@lru_cache(maxsize=1)
def _idf() -> dict[str, float]:
    return _idf_for(_load_corpus())


def _score(query_tokens: list[str], chunk: Chunk, idf: dict[str, float] | None = None) -> float:
    idf = idf if idf is not None else _idf()
    tf = Counter(_tok(chunk.text))
    length = sum(tf.values()) or 1
    score = 0.0
    for q in query_tokens:
        if q in tf:
            score += (tf[q] / length) * idf.get(q, 0.0)
    # small boost when the query term appears in the section heading
    heading = set(_tok(chunk.section))
    score += 0.05 * len(set(query_tokens) & heading)
    return score


def retrieve(query: str, top_k: int = 4, documents: list[dict] | None = None) -> list[Chunk]:
    """Return the top-k grounded chunks for a query (normalized 0..1 scores).

    If `documents` (the workspace's own ingested docs) are given, ground over
    those; otherwise fall back to the bundled enterprise corpus.
    """
    if settings.live_search:
        try:
            live = _retrieve_live(query, top_k)
            if live:
                return live
        except Exception:
            pass  # fall back to local grounding on any error

    if documents is not None:
        corpus = _chunks_from_documents(documents)
        idf = _idf_for(corpus)
    else:
        corpus = _load_corpus()
        idf = _idf()

    qt = _tok(query)
    scored = []
    for c in corpus:
        s = _score(qt, c, idf)
        if s > 0:
            scored.append(Chunk(c.doc_id, c.title, c.section, c.text, s))
    scored.sort(key=lambda c: c.score, reverse=True)
    top = scored[:top_k]
    if top:
        hi = top[0].score or 1.0
        for c in top:
            c.score = round(c.score / hi, 3)
    return top


def _search_url(path: str) -> str:
    ep = settings.foundry_iq_search_endpoint.rstrip("/")
    return f"{ep}/indexes/{settings.foundry_iq_search_index}/docs/{path}?api-version=2023-11-01"


def _retrieve_live(query: str, top_k: int) -> list[Chunk]:
    """Live Foundry IQ retrieval via Azure AI Search (full-text; free-tier compatible)."""
    import json
    import urllib.request

    body = json.dumps({"search": query, "top": top_k, "queryType": "simple", "searchMode": "any"}).encode()
    req = urllib.request.Request(
        _search_url("search"), data=body, method="POST",
        headers={"api-key": settings.foundry_iq_search_key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    results = data.get("value", [])
    hi = max((r.get("@search.score", 0.0) for r in results), default=1.0) or 1.0
    return [
        Chunk(
            doc_id=r.get("doc_id") or r.get("id", ""),
            title=r.get("title", ""),
            section=r.get("section", ""),
            text=r.get("content", ""),
            score=round(float(r.get("@search.score", 0.0)) / hi, 3),
        )
        for r in results
    ]


def index_documents(documents: list[dict]) -> int:
    """Push documents to the Azure AI Search index so they ground live (Foundry IQ).
    No-op unless live search is configured. Returns number of chunks indexed."""
    if not settings.live_search:
        return 0
    import json
    import re
    import urllib.request

    chunks = _chunks_from_documents(documents)
    payload = [{
        "@search.action": "mergeOrUpload",
        "id": re.sub(r"[^A-Za-z0-9_\-=]", "_", f"{c.doc_id}-{i}"),
        "doc_id": c.doc_id, "title": c.title, "section": c.section, "content": c.text,
    } for i, c in enumerate(chunks)]
    if not payload:
        return 0
    body = json.dumps({"value": payload}).encode()
    req = urllib.request.Request(
        _search_url("index"), data=body, method="POST",
        headers={"api-key": settings.foundry_iq_search_key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            json.load(resp)
        return len(payload)
    except Exception:
        return 0
