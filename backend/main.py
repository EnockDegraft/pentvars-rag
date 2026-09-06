#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py — FastAPI backend exposing the RAG pipeline over HTTP.

Endpoints:
    GET  /api/health   -> status + which embedding/LLM backends are active
    POST /api/ask       -> {"question": "..."} -> {"answer", "sources", "mode"}
    GET  /              -> serves the static chat frontend (frontend/index.html)

Run with (from the project root, so the relative data/ paths resolve):
    uvicorn backend.main:app --reload --port 8000
Then open http://localhost:8000/ in a browser.
"""
import os
import sys
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rag_pipeline import answer_question, CHROMA_DIR
from embeddings import BACKEND_MARKER_PATH
import flow_engine

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FRONTEND_DIR = os.path.join(ROOT, "frontend")

app = FastAPI(title="Pentecost University Institutional Knowledge Assistant")

# Open CORS: this is a local student-project demo, not a public multi-tenant
# service, so we favour "just works from the static frontend" over locking
# down origins. Tighten this (allow_origins=["https://your-domain"]) before
# deploying anywhere public.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


class FlowNextRequest(BaseModel):
    session_id: str
    input: str = ""


@app.get("/api/health")
def health():
    embedding_backend = "not indexed yet"
    if os.path.exists(BACKEND_MARKER_PATH):
        with open(BACKEND_MARKER_PATH) as f:
            embedding_backend = json.load(f).get("kind", "unknown")

    llm_backend = "groq (live)" if os.environ.get("GROQ_API_KEY", "").strip() else "extractive_fallback (no GROQ_API_KEY set)"

    return {
        "status": "ok",
        "index_built": os.path.isdir(CHROMA_DIR),
        "embedding_backend": embedding_backend,
        "llm_backend": llm_backend,
    }


@app.post("/api/ask")
def ask(payload: AskRequest):
    return answer_question(payload.question)


@app.post("/api/flow/start")
def flow_start():
    """Begin a new guided session. Returns the first turn to render."""
    _, render = flow_engine.start_session()
    return render


@app.post("/api/flow/next")
def flow_next(payload: FlowNextRequest):
    """Advance the guided session with the student's reply (a chosen option
    id, or free text). 404 means the session expired -> the client should
    call /api/flow/start again."""
    try:
        return flow_engine.advance(payload.session_id, payload.input)
    except KeyError:
        raise HTTPException(status_code=404, detail="session_expired")


# Serve the static chat UI at the site root, if it exists.
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
