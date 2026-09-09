#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm.py — Pluggable answer-generation backend.

Primary path: Groq's free API (https://console.groq.com). Groq gives every
account a generous free tier (no credit card required) and serves fast,
capable open-weight models (gpt-oss, Qwen, Llama) — a good fit for a student
project. Set the GROQ_API_KEY environment variable to enable it. Groq
rotates its model line-up, so if GROQ_MODEL 404s, check the current list at
https://console.groq.com/docs/models (or GET /openai/v1/models).

Fallback path: if no GROQ_API_KEY is set (e.g. while first testing the
system, or on a machine with no internet access at all), the system does
NOT pretend to generate an AI answer. Instead it returns the most relevant
retrieved excerpt directly, clearly labelled as such, so the retrieval half
of the RAG pipeline is still fully demoable with zero setup and zero cost.
"""
import os
import re
import json
import urllib.request
import urllib.error

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
# Groq rotates its hosted model line-up; check https://console.groq.com/docs/models
# for the current list. gpt-oss-20b is a small, fast, free-tier instruction model.
GROQ_MODEL = "openai/gpt-oss-20b"

# Groq's free tier caps tokens-per-minute (~8k for this model), so keep each
# request lean: trim each retrieved chunk before putting it in the prompt,
# and cap the answer length.
MAX_CHUNK_CHARS = 700
MAX_ANSWER_TOKENS = 500

SYSTEM_PROMPT = (
    "You are the Pentecost University Institutional Knowledge Assistant. "
    "Answer the user's question using ONLY the information in the numbered "
    "context excerpts below, which come from official Pentecost University "
    "documents. If the answer is not contained in the excerpts, say clearly "
    "that you don't have that information in the knowledge base rather than "
    "guessing. When you use information from an excerpt, cite it inline "
    "like [1], [2] matching the excerpt numbers. Be concise and direct."
)


def _build_user_prompt(question, context_chunks):
    context_block = "\n\n".join(
        f"[{i + 1}] (Source: {c['metadata']['title']})\n{c['document'][:MAX_CHUNK_CHARS]}"
        for i, c in enumerate(context_chunks)
    )
    return f"Context excerpts:\n\n{context_block}\n\nQuestion: {question}"


def _call_groq(question, context_chunks, api_key):
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(question, context_chunks)},
        ],
        "temperature": 0.2,
        "max_tokens": MAX_ANSWER_TOKENS,
    }
    req = urllib.request.Request(
        GROQ_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Groq's API is behind Cloudflare, which 403s the default
            # "Python-urllib/x" User-Agent (Cloudflare error 1010). Send a
            # plain descriptive UA so the request gets through.
            "User-Agent": "pentvars-rag/1.0 (+https://github.com/EnockDegraft/pentvars-rag)",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


def _tidy_excerpt(text):
    """Indexed chunks carry ~150 chars of the previous chunk as retrieval
    overlap, so a raw chunk often begins mid-word or mid-sentence ("rsonal).
    Attach evidence..."). That overlap is useful as LLM context but looks
    broken when shown verbatim, so for the extractive display we drop a
    leading fragment up to the first clean sentence/line start."""
    t = text.strip()
    first = next((c for c in t if c.isalnum()), "")
    if not first or first.isupper() or first.isdigit() or t[:1] in "#-*>":
        return t
    m = re.search(r"[.!?]\s+|\n", t[:180])
    if m:
        rest = t[m.end():].lstrip()
        if len(rest) >= 80:
            return rest
    return t


def _extractive_fallback(question, context_chunks):
    if not context_chunks:
        return (
            "I couldn't find anything relevant to that question in the knowledge base.\n\n"
            "(No GROQ_API_KEY is configured, so this is the extractive fallback mode -- "
            "see the README for how to enable full AI-generated answers for free.)"
        )
    top = context_chunks[0]
    excerpt = _tidy_excerpt(top["document"])
    return (
        f"Here is the most relevant excerpt I found (from \"{top['metadata']['title']}\"):\n\n"
        f"\"{excerpt}\"\n\n"
        "(No GROQ_API_KEY is configured, so I'm showing the raw retrieved excerpt instead of "
        "an AI-generated answer. Add a free Groq API key -- see the README -- to get natural, "
        "conversational answers generated from this same retrieved context.)"
    )


def generate_answer(question, context_chunks):
    """Returns (answer_text: str, mode: 'groq' | 'extractive_fallback')."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if api_key:
        try:
            return _call_groq(question, context_chunks, api_key), "groq"
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            if e.code == 429:
                note = (
                    "The Groq free tier is rate-limited at the moment (too many "
                    "requests in a short time). Showing the retrieved excerpt "
                    "instead — try again in a minute for an AI-written answer."
                )
            else:
                note = (
                    f"The Groq API returned an error ({e.code}): {error_body}\n\n"
                    "Falling back to the retrieved excerpt below."
                )
            return (note + "\n\n" + _extractive_fallback(question, context_chunks)), "groq_error"
        except Exception as e:
            return (
                f"Could not reach the Groq API ({e.__class__.__name__}: {e}).\n\n"
                "Falling back to the retrieved excerpt below.\n\n"
                + _extractive_fallback(question, context_chunks)
            ), "groq_error"
    return _extractive_fallback(question, context_chunks), "extractive_fallback"
