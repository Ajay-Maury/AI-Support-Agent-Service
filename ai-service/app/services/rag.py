"""
RAG query pipeline:
  1. Embed the user question (local model)
  2. Atlas Vector Search — top-K chunks by cosine similarity
  3. Score gate — drop weak matches
  4. Assemble context block
  5. Stream answer from Groq (llama3-8b-8192 or qwen)
"""

import asyncio
from typing import AsyncIterator

from groq import AsyncGroq
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.prompts import SYSTEM_PROMPT, NOT_FOUND_RESPONSE
from app.services.embedding import embed_single

_groq_client: AsyncGroq | None = None


def get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=settings.groq_api_key)
    return _groq_client


# ── Vector search ─────────────────────────────────────────────────────────────

async def _vector_search(query_vector: list[float], db: AsyncIOMotorDatabase) -> list[dict]:
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": settings.num_candidates,
                "limit": settings.top_k,
            }
        },
        {
            "$project": {
                "text": 1,
                "filename": 1,
                "chunk_index": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    cursor = db["doc_chunks"].aggregate(pipeline)
    return await cursor.to_list(length=settings.top_k)


# ── Context assembly ──────────────────────────────────────────────────────────

def _build_context(chunks: list[dict]) -> str:
    parts = [
        f"[Source: {c['filename']}  chunk {c['chunk_index']}  score {c['score']:.2f}]\n{c['text']}"
        for c in chunks
    ]
    return "\n\n---\n\n".join(parts)


# ── Main query pipeline ───────────────────────────────────────────────────────

async def run_query(
    question: str,
    db: AsyncIOMotorDatabase,
) -> tuple[AsyncIterator[str], list[dict]]:
    """
    Returns (token_stream, source_chunks).
    Caller iterates token_stream for SSE delivery.
    """

    # 1. Embed question (CPU-bound → thread pool)
    loop = asyncio.get_event_loop()
    query_vector = await loop.run_in_executor(None, embed_single, question)

    # 2. Vector search
    raw_chunks = await _vector_search(query_vector, db)

    # 3. Score gate
    chunks = [c for c in raw_chunks if c.get("score", 0) >= settings.min_score]

    if not chunks:
        async def _fallback():
            yield NOT_FOUND_RESPONSE
        return _fallback(), []

    # 4. Assemble context
    context = _build_context(chunks)

    # 5. Stream from Groq
    client = get_groq_client()

    async def _stream_tokens() -> AsyncIterator[str]:
        stream = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {question}",
                },
            ],
            temperature=0,
            max_tokens=512,
            stream=True,
        )
        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token

    return _stream_tokens(), chunks
