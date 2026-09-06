# Portable image for the Pentecost University RAG assistant.
# Builds and runs unchanged on Render, Fly.io, Google Cloud Run,
# Hugging Face Spaces (Docker SDK), or plain `docker run`.

FROM python:3.12-slim

WORKDIR /app

# Python deps first, so this layer is cached across code changes.
# Uses requirements-deploy.txt (no sentence-transformers) — small image,
# fits free tiers, TF-IDF retrieval. Swap for requirements.txt on a host
# with >= 2 GB RAM to get neural embeddings.
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY backend/ backend/
COPY frontend/ frontend/
COPY data/raw/ data/raw/

# Bake the vector index into the image so the container boots instantly
# instead of indexing on every cold start.
RUN python backend/ingest.py

# Most platforms inject $PORT; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
