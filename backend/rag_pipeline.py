#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag_pipeline.py — The core Retrieval-Augmented Generation pipeline.

answer_question(question) -> dict:
    1. Embeds the question with whichever embedding backend ingest.py used.
    2. Retrieves the most relevant chunks from the ChromaDB knowledge base.
    3. Sends the question + retrieved chunks to the LLM backend (llm.py) to
       generate a grounded, cited answer.
    4. Returns the answer text together with the list of sources used, so
       the API layer / frontend can display citations.
"""
import os
import re
import sys

import chromadb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embeddings import load_embedder_for_query
from llm import generate_answer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHROMA_DIR = os.path.join(ROOT, "data", "chroma_db")
COLLECTION_NAME = "pentvars_knowledge_base"

TOP_K = 6                      # how many chunks to retrieve
#
# 6 rather than a tighter 3-4: on this knowledge base the MiniLM embeddings
# cluster many generic "about the university" chunks close together, so the
# single on-point document for a question (e.g. the programme list for
# "what programmes are offered?") can sit at rank 5-6. 6 catches those
# while keeping the LLM prompt small enough for the Groq free tier's
# per-minute token budget. The distance threshold still filters genuinely
# off-topic chunks, and the LLM prompt says to use only what's relevant.

# Chunks weaker (further away) than this are treated as "not relevant", which
# is how off-topic questions ("what's the capital of France?") get rejected
# instead of answered from an irrelevant excerpt. The two embedding backends
# put distances on different scales, so the cutoff is per-backend:
#   - tfidf: a query sharing zero vocabulary with the knowledge base scores an
#     exact 1.0 distance, so 0.95 rejects off-topic questions while keeping
#     genuine matches (which scored 0.3-0.95 in testing).
#   - sentence-transformers: cosine distance. Measured on this knowledge base,
#     genuinely relevant chunks score ~0.2-0.6 and off-topic questions ~0.84+,
#     so 0.75 sits comfortably between the two.
DISTANCE_THRESHOLD_BY_BACKEND = {
    "tfidf": 0.95,
    "sentence-transformers": 0.75,
}
DEFAULT_DISTANCE_THRESHOLD = 0.95

_client = None
_collection = None
_embedder = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        if not os.path.isdir(CHROMA_DIR):
            raise RuntimeError(
                "No knowledge base index found. Run `python3 backend/ingest.py` first."
            )
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = _client.get_collection(COLLECTION_NAME)
    return _collection


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = load_embedder_for_query()
    return _embedder


def retrieve(question, top_k=TOP_K, source=None):
    """Retrieve the most relevant chunks. `source`, if given, restricts the
    search to one knowledge-base file (e.g. "scholarship_full.md") — the
    guided flow uses this so a scripted option always answers from its own
    document, even when several documents are worded almost identically."""
    collection = _get_collection()
    embedder = _get_embedder()
    query_vector = embedder.encode([question])[0]

    query_kwargs = {"query_embeddings": [query_vector], "n_results": top_k}
    if source:
        query_kwargs["where"] = {"source": source}
    results = collection.query(**query_kwargs)

    threshold = DISTANCE_THRESHOLD_BY_BACKEND.get(
        getattr(embedder, "kind", None), DEFAULT_DISTANCE_THRESHOLD
    )

    chunks = []
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]
    for doc, meta, dist in zip(docs, metas, dists):
        if dist <= threshold:
            chunks.append({"document": doc, "metadata": meta, "distance": dist})
    return chunks


def answer_question(question: str, source: str = None) -> dict:
    question = (question or "").strip()
    if not question:
        return {
            "answer": "Please enter a question.",
            "sources": [],
            "mode": "no_question",
        }

    chunks = retrieve(question, source=source)

    if not chunks:
        return {
            "answer": (
                "I couldn't find anything in the Pentecost University knowledge base "
                "relevant to that question. Try rephrasing it, or ask about admissions, "
                "programmes, tuition and scholarships, student life, or contact details."
            ),
            "sources": [],
            "mode": "no_match",
        }

    answer_text, mode = generate_answer(question, chunks)

    # Models sometimes cite with full-width / CJK brackets ("【2】"); fold
    # them back to "[2]" so both the reader and the citation parser below
    # see a consistent form.
    if mode == "groq":
        answer_text = re.sub(r"[［【]\s*(\d+)\s*[］】]", r"[\1]", answer_text)

    # We retrieve a wide net (TOP_K) for the model, but only show the
    # documents the answer actually rests on:
    #  - groq: the excerpts the model cited as [1], [2], ... (fall back to
    #    the 3 nearest if it cited nothing);
    #  - extractive fallback: the single excerpt that was shown.
    if mode == "groq":
        cited = sorted({
            int(n) - 1 for n in re.findall(r"\[(\d+)\]", answer_text)
        })
        cited = [i for i in cited if 0 <= i < len(chunks)]
        shown = [chunks[i] for i in cited] if cited else chunks[:3]
    else:
        shown = chunks[:1]

    # de-duplicated source list, in the order first referenced
    seen = set()
    sources = []
    for c in shown:
        title = c["metadata"]["title"]
        source_file = c["metadata"]["source"]
        if source_file not in seen:
            seen.add(source_file)
            sources.append({"title": title, "file": source_file})

    return {
        "answer": answer_text,
        "sources": sources,
        "mode": mode,
    }


if __name__ == "__main__":
    import sys as _sys
    q = " ".join(_sys.argv[1:]) or "What are the entry requirements for Pentecost University?"
    result = answer_question(q)
    print("Q:", q)
    print("\nA:", result["answer"])
    print("\nSources:", ", ".join(s["title"] for s in result["sources"]))
    print("Mode:", result["mode"])
