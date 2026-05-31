"""Dependency-free ingestion pipeline and TF-IDF retrieval.

The pipeline transforms a document's raw text through ordered stages and
produces chunks with a cached term-frequency vector. Retrieval ranks chunks
against a query using TF-IDF cosine similarity. Tokenisation handles mixed
Chinese/English text: CJK characters are indexed individually plus as
bigrams, Latin runs as lowercased words.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

_LATIN = re.compile(r"[a-zA-Z0-9]+")
_CJK = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """Tokenise mixed CJK/Latin text into retrieval terms."""
    tokens: list[str] = [m.group(0).lower() for m in _LATIN.finditer(text)]
    cjk = _CJK.findall(text)
    tokens.extend(cjk)
    # CJK bigrams improve precision for multi-character words.
    for i in range(len(cjk) - 1):
        tokens.append(cjk[i] + cjk[i + 1])
    return tokens


# --------------------------------------------------------------------------- #
# Pipeline stages
# --------------------------------------------------------------------------- #
def _stage_clean(text: str, config: dict[str, Any]) -> str:
    if config.get("strip", True):
        text = text.strip()
    if config.get("collapse_whitespace", True):
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
    if config.get("lowercase"):
        text = text.lower()
    return text


def _split(text: str, config: dict[str, Any]) -> list[str]:
    size = int(config.get("chunk_size", 500))
    overlap = int(config.get("chunk_overlap", 50))
    separator = config.get("separator", "\n\n")
    size = max(size, 1)
    overlap = max(min(overlap, size - 1), 0)

    # First break on the separator, then pack pieces up to ``size`` chars,
    # sliding a window with ``overlap`` to preserve cross-boundary context.
    pieces = [p for p in text.split(separator) if p.strip()] if separator else [text]
    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        if len(buf) + len(piece) + 1 <= size:
            buf = f"{buf}\n{piece}" if buf else piece
            continue
        if buf:
            chunks.append(buf)
        if len(piece) <= size:
            buf = piece
            continue
        # Hard-wrap an oversized piece with overlap.
        start = 0
        while start < len(piece):
            chunks.append(piece[start : start + size])
            start += size - overlap
        buf = ""
    if buf:
        chunks.append(buf)
    return [c.strip() for c in chunks if c.strip()]


def run_pipeline(
    raw_text: str,
    pipeline: list[dict[str, Any]],
) -> list[str]:
    """Run the ingestion pipeline, returning the list of chunk texts."""
    text = raw_text
    chunks: list[str] = [text]
    for stage in pipeline:
        kind = stage.get("type")
        config = stage.get("config", {}) or {}
        if kind == "extract":
            # Plain-text source; nothing to extract. Hook point for future
            # PDF/HTML extractors.
            text = text
        elif kind == "clean":
            text = _stage_clean(text, config)
        elif kind == "split":
            chunks = _split(text, config)
        elif kind == "index":
            # Indexing is handled by the caller (term-freq vectors persisted
            # to the chunk rows); this stage is a no-op over the text.
            continue
    # If no split stage ran, treat the whole cleaned text as a single chunk.
    if not any(s.get("type") == "split" for s in pipeline):
        chunks = [c.strip() for c in [text] if c.strip()]
    return chunks


# --------------------------------------------------------------------------- #
# Retrieval (TF-IDF cosine)
# --------------------------------------------------------------------------- #
def term_freq(text: str) -> dict[str, int]:
    """Return the term-frequency vector for a chunk."""
    return dict(Counter(tokenize(text)))


def rank(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int = 4,
    score_threshold: float = 0.0,
) -> list[dict[str, Any]]:
    """Rank ``chunks`` against ``query`` by TF-IDF cosine similarity.

    Each chunk is ``{"id", "content", "term_freq", ...}``. Returns the top
    matches annotated with a ``score`` in ``[0, 1]``.
    """
    if not chunks:
        return []
    q_tf = term_freq(query)
    if not q_tf:
        return []

    n_docs = len(chunks)
    # Document frequency per term across the corpus.
    doc_freq: Counter[str] = Counter()
    for chunk in chunks:
        for term in (chunk.get("term_freq") or {}):
            doc_freq[term] += 1

    def idf(term: str) -> float:
        return math.log((1 + n_docs) / (1 + doc_freq.get(term, 0))) + 1.0

    def tfidf_vec(tf: dict[str, int]) -> dict[str, float]:
        return {t: c * idf(t) for t, c in tf.items()}

    q_vec = tfidf_vec(q_tf)
    q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

    scored: list[dict[str, Any]] = []
    for chunk in chunks:
        c_vec = tfidf_vec(chunk.get("term_freq") or {})
        if not c_vec:
            continue
        dot = sum(q_vec.get(t, 0.0) * v for t, v in c_vec.items())
        c_norm = math.sqrt(sum(v * v for v in c_vec.values())) or 1.0
        score = dot / (q_norm * c_norm)
        if score >= score_threshold and score > 0:
            scored.append({**chunk, "score": round(score, 4)})
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_k]
