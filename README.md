# Pentecost University Institutional Knowledge Assistant (RAG Demo)

A working Retrieval-Augmented Generation (RAG) system built from your final
year project report: it answers questions about Pentecost University using
real content scraped from **pentvars.edu.gh**, retrieves the most relevant
passages with a local vector search index, and generates a grounded, cited
answer.

This is a full-stack demo: a Python backend (FastAPI) + a simple web chat
page (HTML/JS). It intentionally does **not** include the Flutter mobile app
described in the report — that would be a separate, larger build. This demo
is meant to prove the RAG pipeline itself works end-to-end and give you
something you can actually run, screenshot, and demo to your supervisor.

## How it's different from a typical tutorial RAG demo

Two design decisions were made specifically so this runs with **zero cost
and zero signup**, and so it keeps working even without an academic/company
network that allows outbound API calls:

1. **Embeddings** (`backend/embeddings.py`): tries the real neural model
   (`sentence-transformers/all-MiniLM-L6-v2`) first. If it can't be
   downloaded (no internet, or a locked-down network), it automatically
   falls back to a local TF-IDF vector search — no download needed, fits
   directly on your own documents. Whichever one is used is recorded, so
   the same method is used again when answering questions.
2. **Answer generation** (`backend/llm.py`): if you set a `GROQ_API_KEY`
   (free, see below), it calls Groq's API to generate a natural,
   conversational cited answer. If no key is set, it falls back to
   **extractive mode**: it shows you the raw top-matching excerpt from the
   knowledge base, clearly labelled as such. This means the retrieval half
   of the system — the actual "R" in RAG, and the harder engineering
   problem — is fully demoable with nothing to sign up for.

Both fallbacks are permanent, real features of the system, not stubs to
delete later. They make the system robust on a machine with no internet
access at all (e.g. presenting live in a room with no wifi), and they mean
you and your supervisor can run this today with literally zero
configuration.

## Project structure

```
pentvars-rag/
├── README.md
├── requirements.txt
├── data/
│   ├── raw/                    # knowledge base source documents (Markdown)
│   ├── chroma_db/              # vector index (created by ingest.py)
│   └── sessions.log.jsonl      # one line per guided-flow sign-in (created at runtime)
├── backend/
│   ├── embeddings.py           # pluggable embedding backend
│   ├── ingest.py                # builds the vector index from data/raw/
│   ├── llm.py                   # pluggable answer-generation backend
│   ├── rag_pipeline.py          # retrieval + generation orchestration
│   ├── flow.py                  # declarative script for the guided assistant flow
│   ├── flow_engine.py           # runs the flow; one small in-memory session per student
│   └── main.py                  # FastAPI app (serves the API + the frontend)
└── frontend/
    └── index.html                # single-page chat UI (guided flow + free text; no build step)
```

## Setup

Requires Python 3.9+.

```bash
cd pentvars-rag
pip install -r requirements.txt
```

## 1. Build the knowledge base index

Run this once (and again any time you edit files in `data/raw/`):

```bash
python3 backend/ingest.py
```

You'll see it report which embedding backend it used. On most machines with
normal internet access, it will download and use the real
`all-MiniLM-L6-v2` model automatically — no code changes needed.

## 2. (Optional but recommended) Get a free Groq API key for real AI answers

Without this, the system still works in "extractive" mode (shows the raw
matched excerpt). With it, answers become natural, conversational, and
still strictly grounded in the retrieved excerpts — this is the "generation"
half of RAG your report describes.

1. Go to <https://console.groq.com/keys> and sign up (no credit card
   required for the free tier).
2. Create an API key.
3. Set it as an environment variable before starting the backend:

   ```bash
   export GROQ_API_KEY="your-key-here"        # macOS/Linux
   set GROQ_API_KEY=your-key-here              # Windows (cmd)
   $env:GROQ_API_KEY="your-key-here"           # Windows (PowerShell)
   ```

If Groq ever changes its free-tier terms, `backend/llm.py` is a single
self-contained file — swapping in any other OpenAI-compatible free API
(e.g. OpenRouter's free models) only requires changing `GROQ_API_URL` and
`GROQ_MODEL` and adjusting the auth header if needed.

## 3. Run the backend + frontend

```bash
uvicorn backend.main:app --reload --port 8000
```

Then open **http://localhost:8000/** in a browser. That's it — the FastAPI
app serves both the API and the chat page, so there's nothing else to start.

## Deploy it online

The repo ships a `Dockerfile` that installs `requirements-deploy.txt` (the
core deps without `sentence-transformers`), bakes the vector index into the
image with `ingest.py`, and serves on `$PORT`. It runs unchanged on any
container host and fits 512 MB free tiers (using the TF-IDF retriever).

**Render** (free, no card) — easiest:

1. Push this repo to GitHub/GitLab.
2. Render dashboard → **New → Blueprint** → pick the repo. It reads
   `render.yaml` and deploys the Docker service.
3. Optional: add a `GROQ_API_KEY` environment variable in the Render
   dashboard for AI-generated answers.
4. Your app is at `https://<name>.onrender.com/`. (Free instances sleep
   after 15 min idle; the first request then takes ~1 min to wake.)

**Any other Docker host** (Fly.io, Google Cloud Run, Railway, a VPS):

```bash
docker build -t pentvars-rag .
docker run -p 8000:8000 -e GROQ_API_KEY=your-key pentvars-rag   # key optional
```

**Hugging Face Spaces** (free, 16 GB RAM — enough for the neural embedder):
create a **Docker** Space from the repo, and either change the Dockerfile to
`COPY requirements.txt` / `pip install -r requirements.txt`, or leave it as
is for TF-IDF. Set `app_port` to `8000` in the Space settings.

Notes:

- CORS is wide open (`allow_origins=["*"]`) — fine for a demo; lock it down
  in `backend/main.py` before anything public-facing that matters.
- Sessions are in-memory, so a redeploy or a second instance loses them.
  That's acceptable for a single-instance demo; move `flow_engine._SESSIONS`
  to Redis if you ever scale out.

## 4. Try it

The chat page opens a **guided flow**:

1. It asks for your name and student index number (any well-formed index
   number is accepted — there is no student roster to check against). Each
   sign-in is appended to `data/sessions.log.jsonl`.
2. It offers a menu: **Scholarships & financial support**, **Report an
   issue**, **Ask a free-text question**, or end the session.
3. **Scholarships** drills down to a specific option (Full / Half / Bursary
   / Church Member Discount / application process / renewal) and answers it
   from the matching knowledge-base document, with citations.
4. **Report an issue** picks a category (Portal & IT, Fees & payments,
   Results & transcripts, Registration & ID, Accommodation & library) then
   a specific problem, and replies with step-by-step instructions, a
   grounded excerpt from the knowledge base, and the office to contact if
   it's still not resolved.
5. You can type a free-text question at any point — at a menu it's answered
   as a one-off without losing your place.

Free-text questions to try:
- "What are the entry requirements for Pentecost University?"
- "How much is tuition and are there scholarships?"
- "How do I request an official transcript?"
- "I can't log into the student e-portal."

Each answer shows which source document(s) it came from, and the little
status pill in the header shows which backends are active
(`GET /api/health` if you want it as raw JSON).

Off-topic questions (e.g. "what's the capital of France?") are correctly
rejected as not being covered by the knowledge base, rather than the system
making something up — this is the retrieval-grounding behaviour that
distinguishes RAG from a plain chatbot, and is worth pointing out in your
demo/defense.

### API endpoints

- `GET /api/health` — status + which embedding/LLM backends are active.
- `POST /api/ask` — `{"question": "..."}` → one grounded, cited answer.
- `POST /api/flow/start` — begin a guided session → the first turn to render.
- `POST /api/flow/next` — `{"session_id": "...", "input": "..."}` → the next
  turn. `input` is a chosen option id or free text. A `404` means the
  session expired; call `/api/flow/start` again.

### Editing the guided flow

The whole script is data in `backend/flow.py`:

- `NODES` — the scripted turns (welcome, sign-in, menus, follow-ups).
- `ISSUES` — the issue catalogue: five categories, each with a `doc` (the
  knowledge-base file its answers are pinned to) and a set of problems,
  each with `steps`, a `rag_query`, and a `contact`.
- `PHRASES` — small pools of wording (greeting, acknowledgements, issue
  openers, sign-off) that the engine rotates through so the assistant
  varies its phrasing and addresses the student by first name instead of
  reading like a form.

Add an issue by adding an entry to `ISSUES`; add a menu branch by adding a
node to `NODES`; reword the tone by editing `PHRASES`. `flow_engine.py`
(session state + validation + rendering) usually doesn't need to change.

## Updating the knowledge base

The content lives in `data/raw/` as plain Markdown files, one per topic
area — about/vision, entry requirements, academic programmes, tuition and
fees, student life, contact info, the four scholarship types plus the
application process, and five student-services areas (portal & IT, fee
problems, results & transcripts, registration & ID, accommodation &
library). Each file ends with a `Source:` line citing the page it came from
on pentvars.edu.gh; the service-desk procedures are representative of
typical university processes and should be confirmed against current
official notices before real use. To add more knowledge (e.g. a specific
faculty's page, an FAQ, exam regulations):

1. Add a new `.md` file to `data/raw/` (start it with a `# Title` heading).
2. Re-run `python3 backend/ingest.py` to rebuild the index.

No other code changes are needed — chunking, embedding, and indexing are
all automatic.

## Known limitation: TF-IDF fallback retrieval quality

If your machine can't reach Hugging Face (so `ingest.py` used the TF-IDF
fallback), retrieval is a bit more "keyword-sensitive" than true semantic
search — e.g. a question using different wording than the source document
may retrieve a slightly less on-point chunk. This is expected and documented
behaviour, not a bug: it resolves automatically once you run `ingest.py` on
a machine with normal internet access, which lets it download and use the
real semantic embedding model instead. This is worth mentioning explicitly
if your supervisor asks about retrieval accuracy — it shows you understand
*why* the tradeoff exists, not just that it exists.

## Relationship to the written report

The report describes a Flutter mobile app talking to this kind of backend.
This demo proves out the backend/RAG core described in Chapters 3-4 of the
report (chunking, embedding, vector storage, retrieval, generation with
citations) with a lightweight web UI standing in for the mobile app, so you
have a real, runnable system to demonstrate alongside the written work. The
guided flow (sign-in → menu → scholarship / issue branches) shows how the
same retrieval core sits underneath a structured, task-oriented assistant
rather than only a free-text search box.