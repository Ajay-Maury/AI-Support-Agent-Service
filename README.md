# RAG Support System

An internal AI-powered customer support tool. Agents ask natural language questions about company documentation — the system retrieves the most relevant chunks from MongoDB Atlas Vector Search and generates a grounded, citation-backed answer via **Groq** (free tier).

---

## Architecture

```
React Frontend  ──POST /api/chat/stream──►  Express Gateway (Node.js)
                                                    │
                                          session save to MongoDB
                                                    │
                                         ──POST /query/stream──►  FastAPI AI Service (Python)
                                                                         │
                                                               embed query (local model)
                                                                         │
                                                               Atlas Vector Search
                                                                         │
                                                               Groq LLM (llama-3.1-8b-instant)
                                                                         │
                                                               ◄── SSE tokens ──
```

### Services

| Service | Stack | Port | Responsibility |
|---|---|---|---|
| **AI Service** | Python, FastAPI, LangChain, sentence-transformers | `8000` | Ingestion pipeline, vector search, Groq LLM streaming |
| **Gateway** | Node.js, Express, TypeScript, Mongoose | `3000` | API surface, session management, SSE proxy |
| **Data Layer** | MongoDB Atlas | Cloud | Vector store (`doc_chunks`), chat history (`chat_sessions`), doc metadata (`doc_metadata`) |

### Design decisions

- **Groq instead of OpenAI** — free-tier API with fast inference. `llama-3.1-8b-instant` provides good quality with generous rate limits.
- **Local embeddings (sentence-transformers/all-MiniLM-L6-v2)** — 384-dimensional vectors, runs on CPU, zero cost, no API key required. The model is baked into the Docker image.
- **Express as gateway, not just proxy** — Express owns session state, input validation (Zod), and SSE piping. FastAPI focuses purely on AI logic.
- **Streaming via SSE** — tokens stream from Groq → FastAPI → Express → React. First token appears in < 1 second.
- **Upsert-safe ingestion** — re-uploading the same file updates existing chunks rather than duplicating them.

---

## Project Structure

```
rag-support-system/
├── ai-service/                  # Python FastAPI
│   ├── app/
│   │   ├── api/
│   │   │   ├── health.py
│   │   │   ├── ingest.py        # POST /ingest, GET /ingest/:id
│   │   │   └── query.py         # POST /query, POST /query/stream
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings from .env
│   │   │   ├── database.py      # Motor async MongoDB client
│   │   │   └── prompts.py       # system prompt + fallback string
│   │   ├── models/
│   │   │   └── schemas.py       # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── embedding.py     # sentence-transformers wrapper
│   │   │   ├── ingestion.py     # load → chunk → embed → upsert pipeline
│   │   │   └── rag.py           # vector search + Groq streaming
│   │   └── main.py
│   ├── scripts/
│   │   └── ingest_doc.py        # CLI one-shot ingestion
│   ├── requirements.txt
│   └── Dockerfile
│
├── gateway/                     # Node.js Express
│   ├── src/
│   │   ├── config/index.ts      # env vars
│   │   ├── middleware/
│   │   │   └── errorHandler.ts
│   │   ├── models/
│   │   │   └── ChatSession.ts   # Mongoose schema
│   │   ├── routes/
│   │   │   ├── chat.ts          # /api/chat, /api/chat/stream
│   │   │   └── docs.ts          # /api/docs/upload, /api/docs
│   │   ├── services/
│   │   │   └── fastapi.ts       # HTTP client for AI service
│   │   ├── app.ts
│   │   └── server.ts
│   ├── package.json
│   ├── tsconfig.json
│   └── Dockerfile
│
├── docs/
│   └── sample-knowledge-base.md  # Sample document to ingest
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Local Setup

### Prerequisites

- Docker & Docker Compose v2
- A free [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register) account
- A free [Groq](https://console.groq.com) API key

### Environment variables (.env)

Add the following keys to your `.env` file. Keys in ALL CAPS are the environment variable names used by Docker and examples below show recommended defaults.

- `GROQ_API_KEY`: (required) your Groq API key
- `MONGODB_URI`: (required) MongoDB Atlas connection string
- `MONGODB_DB_NAME`: database name (default: `rag_support_agent`)
- `GROQ_MODEL`: Groq model to use (default: `llama-3.1-8b-instant`)
- `EMBEDDING_MODEL`: local HF embedding model (default: `sentence-transformers/all-MiniLM-L6-v2`)
- `CHUNK_SIZE`: document chunk size (default: `512`)
- `CHUNK_OVERLAP`: chunk overlap (default: `64`)
- `TOP_K`: top-k retrieval (default: `3`)
- `MIN_SCORE`: retrieval min score (default: `0.70`)
- `NUM_CANDIDATES`: retrieval candidate pool (default: `100`)

Example `.env` (minimum):

```
MONGODB_URI=mongodb+srv://<user>:<pw>@cluster0.mongodb.net
GROQ_API_KEY=gsk_XXXXXXXXXXXXXXXX
GROQ_MODEL=llama-3.1-8b-instant
MIN_SCORE=0.70
```

Note: the Python service reads settings via `pydantic-settings` and accepts the same variable names in lower/upper case. The defaults listed above match the values in `ai-service/app/core/config.py`.

### Step 1 — Clone and configure

```bash
git clone https://github.com/Ajay-Maury/AI-Support-Agent-Service.git
cd AI-Support-Agent-Service
cp .env.example .env
```

Edit `.env` and fill in:
```
MONGODB_URI=mongodb+srv://...
GROQ_API_KEY=gsk_...
```

### Step 2 — Create the Atlas Vector Search index

This is a one-time manual step in the Atlas UI.

1. Go to **Atlas UI → your cluster → Search → Create Search Index**
2. Choose **Vector Search** (not Atlas Search)
3. Select the `rag_support_agent` database and `doc_chunks` collection
4. Use this JSON definition:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 384,
      "similarity": "cosine"
    }
  ]
}
```

5. Name the index `vector_index` and click **Create**

> **Why 384?** We use `sentence-transformers/all-MiniLM-L6-v2` which produces 384-dimensional vectors — free, local, no API key required.

### Step 3 — Start the services

```bash
docker compose up --build
```

On first run, Docker will:
- Install Python dependencies and download the embedding model (~80 MB) into the image
- Build the TypeScript gateway

Both services start automatically. The AI service exposes a health check — the gateway waits for it before starting.

### Step 4 — Ingest a document

**Option A — via curl:**
```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@docs/sample-knowledge-base.md"
```

**Option B — via the CLI script (inside the container):**
```bash
docker exec rag_ai_service python scripts/ingest_doc.py /app/docs/sample-knowledge-base.md
```

Poll ingestion status:
```bash
curl http://localhost:8000/ingest/<doc_id>
```

Wait for `"status": "completed"` before querying.

### Step 5 — Query the system

**Non-streaming (quick test):**
```bash
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the return policy?"}'
```

**Streaming via SSE:**
```bash
curl -N http://localhost:3000/api/chat/stream \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "What payment methods do you accept?"}'
```

---

## API Reference

### Gateway (port 3000)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Gateway health check |
| `POST` | `/api/chat` | Ask a question (JSON response) |
| `POST` | `/api/chat/stream` | Ask a question (SSE streaming) |
| `GET` | `/api/chat/:id` | Load session history by session_id |
| `GET` | `/api/chat` | List recent sessions |
| `POST` | `/api/docs/upload` | Upload a .md or .txt document |
| `GET` | `/api/docs/:id/status` | Poll document ingestion status |
| `GET` | `/api/docs` | List all ingested documents |

### AI Service (port 8000)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | AI service + DB health check |
| `POST` | `/ingest` | Ingest a document (multipart) |
| `GET` | `/ingest/:doc_id` | Get ingestion status |
| `GET` | `/ingest` | List all documents |
| `POST` | `/query` | Non-streaming query |
| `POST` | `/query/stream` | SSE streaming query |

### SSE event types (streaming)

| Frame | Meaning |
|---|---|
| `data: [SESSION]<id>` | Session ID assigned (first frame) |
| `data: <token>` | LLM token to append to chat bubble |
| `data: [SOURCES]<json>` | Array of `{filename, chunk_index, score}` |
| `data: [DONE]` | Stream complete |

---

## Changing the Groq Model

Edit `GROQ_MODEL` in `.env`:

| Model | Context | Best for |
|---|---|---|
| `llama-3.1-8b-instant` | 8b | Default — fast, good quality |
| `llama3-70b-8192` | 8K | Better reasoning, slower |
| `mixtral-8x7b-32768` | 32K | Long documents |
| `gemma2-9b-it` | 8K | Alternative, Google model |

No code changes required — restart with `docker compose up`.

---

## Troubleshooting

**Atlas Vector Search returns no results**
- Verify the index name is exactly `vector_index`
- Verify `numDimensions` is `384` (not 1536 — that's for OpenAI)
- Check the index status is `Active` in Atlas UI before querying

**"I cannot find the answer in the provided documentation."**
- The question has no relevant match in ingested docs (score < 0.70)
- Try lowering `MIN_SCORE=0.60` in `.env` for more permissive retrieval
- Make sure the document was fully ingested (`status: completed`)

**Gateway can't reach AI service**
- Confirm `ai-service` is healthy: `docker compose ps`
- The gateway waits for the AI service healthcheck — on first run with model download, allow 2–3 minutes

**Groq rate limit errors**
- Free tier: ~30 requests/min. For testing, add a small delay between calls.
- Switch to `llama-3.1-8b-instant` (fastest) if hitting limits on larger models.
