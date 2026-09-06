#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
embeddings.py — Pluggable embedding backend for the RAG pipeline.

Two backends are supported, both 100% free (no API key, no per-query cost):

1. "sentence-transformers" (preferred): a real local neural embedding model
   (all-MiniLM-L6-v2). Produces much better semantic search than the
   fallback below, but its weights must be downloaded from Hugging Face the
   first time it runs, so it needs normal internet access on the machine
   running ingest.py.

2. "tfidf" (automatic fallback): a classic statistical TF-IDF + cosine
   similarity backend built entirely with scikit-learn. Nothing to
   download — it fits directly on your own documents — so it always works,
   even on a network that blocks Hugging Face. Retrieval quality is a bit
   more "keyword-sensitive" than true semantic embeddings, but for a
   focused knowledge base like a university's own documents it works well.

`ingest.py` tries backend 1 first and automatically falls back to backend 2
if the model can't be downloaded, recording which one it used in
`data/embedding_backend.txt` so `rag_pipeline.py` encodes queries the same
way at question-answering time.
"""
import os
import json
import pickle

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(ROOT, "data")
BACKEND_MARKER_PATH = os.path.join(DATA_DIR, "embedding_backend.json")
TFIDF_VECTORIZER_PATH = os.path.join(DATA_DIR, "tfidf_vectorizer.pkl")

SENTENCE_TRANSFORMER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class SentenceTransformerEmbedder:
    kind = "sentence-transformers"

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)

    def fit(self, texts):
        # Nothing to fit -- the pretrained model already knows how to
        # embed arbitrary text.
        pass

    def encode(self, texts):
        return self.model.encode(list(texts), normalize_embeddings=True).tolist()


class TfidfEmbedder:
    kind = "tfidf"

    def __init__(self, vectorizer=None):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vectorizer = vectorizer or TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            max_features=20000,
        )

    def fit(self, texts):
        self.vectorizer.fit(texts)

    def encode(self, texts):
        import numpy as np
        from sklearn.preprocessing import normalize
        matrix = self.vectorizer.transform(list(texts))
        matrix = normalize(matrix)  # cosine similarity via dot product
        return matrix.toarray().tolist()

    def save(self, path=TFIDF_VECTORIZER_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.vectorizer, f)

    @classmethod
    def load(cls, path=TFIDF_VECTORIZER_PATH):
        with open(path, "rb") as f:
            vectorizer = pickle.load(f)
        return cls(vectorizer=vectorizer)


def build_embedder_for_ingest(corpus_texts):
    """Used by ingest.py. Tries the real semantic embedder first; falls
    back to TF-IDF (fit on the given corpus) if the model can't be
    downloaded. Persists which backend was chosen so query time matches."""
    try:
        embedder = SentenceTransformerEmbedder()
        print(f"Using embedding backend: {embedder.kind} ({SENTENCE_TRANSFORMER_MODEL})")
    except Exception as e:
        print(f"Could not load '{SENTENCE_TRANSFORMER_MODEL}' ({e.__class__.__name__}: {e}).")
        print("Falling back to the local TF-IDF embedding backend (no download needed).")
        embedder = TfidfEmbedder()
        embedder.fit(corpus_texts)
        embedder.save()

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BACKEND_MARKER_PATH, "w") as f:
        json.dump({"kind": embedder.kind}, f)

    return embedder


def load_embedder_for_query():
    """Used by rag_pipeline.py at question-answering time. Loads whichever
    backend ingest.py actually used, so queries are encoded the same way
    the documents were."""
    if not os.path.exists(BACKEND_MARKER_PATH):
        raise RuntimeError(
            "No embedding backend recorded yet. Run `python3 backend/ingest.py` first."
        )
    with open(BACKEND_MARKER_PATH) as f:
        marker = json.load(f)

    if marker["kind"] == "sentence-transformers":
        return SentenceTransformerEmbedder()
    elif marker["kind"] == "tfidf":
        return TfidfEmbedder.load()
    else:
        raise RuntimeError(f"Unknown embedding backend recorded: {marker['kind']!r}")
