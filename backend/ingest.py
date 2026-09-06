#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest.py — Loads the institutional knowledge-base documents (Markdown files
under data/raw/), splits them into overlapping chunks, embeds each chunk with
a free, local sentence-transformers model (no API key, no cost), and stores
the embeddings + text in a persistent local ChromaDB collection.

Run this once whenever the documents in data/raw/ change:
    python3 backend/ingest.py
"""
import os
import re
import glob
import sys

import chromadb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embeddings import build_embedder_for_ingest

# --- Configuration -----------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW_DOCS_DIR = os.path.join(ROOT, "data", "raw")
CHROMA_DIR = os.path.join(ROOT, "data", "chroma_db")
COLLECTION_NAME = "pentvars_knowledge_base"

CHUNK_SIZE = 800       # characters per chunk
CHUNK_OVERLAP = 150    # characters of overlap between consecutive chunks


def load_documents(source_dir: str):
    """Read every .md/.txt file in source_dir, returning a list of
    {source, title, text} dicts. The first '# Heading' line (if present)
    is used as the document title."""
    documents = []
    paths = sorted(glob.glob(os.path.join(source_dir, "*.md"))) + \
        sorted(glob.glob(os.path.join(source_dir, "*.txt")))
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        title_match = re.match(r"^#\s+(.+)$", text.strip(), re.MULTILINE)
        title = title_match.group(1).strip() if title_match else os.path.basename(path)
        documents.append({
            "source": os.path.basename(path),
            "title": title,
            "text": text,
        })
    return documents


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Split text into overlapping chunks, preferring to break on paragraph
    or sentence boundaries so chunks stay coherent."""
    # Normalise whitespace within paragraphs but keep paragraph breaks.
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            if len(para) <= chunk_size:
                current = para
            else:
                # paragraph itself is too long -> hard-split with overlap
                start = 0
                while start < len(para):
                    end = start + chunk_size
                    chunks.append(para[start:end])
                    start = end - overlap
                current = ""
    if current:
        chunks.append(current)

    # add overlap between consecutive chunks for better retrieval continuity
    overlapped = []
    for i, c in enumerate(chunks):
        if i == 0:
            overlapped.append(c)
        else:
            prev_tail = chunks[i - 1][-overlap:]
            overlapped.append(prev_tail + "\n\n" + c)
    return overlapped


def build_index():
    print(f"Loading documents from {RAW_DOCS_DIR} ...")
    documents = load_documents(RAW_DOCS_DIR)
    print(f"Found {len(documents)} source documents.")

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    # Start fresh each time ingest.py is run, so stale chunks never linger.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    all_ids, all_texts, all_metadatas = [], [], []
    for doc in documents:
        chunks = chunk_text(doc["text"])
        for i, chunk in enumerate(chunks):
            all_ids.append(f"{doc['source']}::chunk{i}")
            all_texts.append(chunk)
            all_metadatas.append({
                "source": doc["source"],
                "title": doc["title"],
                "chunk_index": i,
            })
        print(f"  {doc['source']}: {len(chunks)} chunk(s)")

    embedder = build_embedder_for_ingest(all_texts)
    print(f"Embedding {len(all_texts)} chunks...")
    embeddings = embedder.encode(all_texts)

    collection.add(
        ids=all_ids,
        embeddings=embeddings,
        documents=all_texts,
        metadatas=all_metadatas,
    )

    print(f"Done. Indexed {collection.count()} chunks into '{COLLECTION_NAME}' at {CHROMA_DIR}")


if __name__ == "__main__":
    build_index()
