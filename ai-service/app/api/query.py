"""
POST /query          — non-streaming JSON response
GET  /query/stream   — Server-Sent Events streaming response
"""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.database import get_db
from app.models.schemas import QueryRequest, QueryResponse, ChunkSource
from app.services.rag import run_query

router = APIRouter()


@router.post("", response_model=QueryResponse)
async def query_non_streaming(body: QueryRequest):
    """Non-streaming endpoint — collects full answer then returns."""
    db = get_db()
    token_stream, chunks = await run_query(body.question, db)

    full_answer = ""
    async for token in token_stream:
        full_answer += token

    sources = [
        ChunkSource(
            filename=c["filename"],
            chunk_index=c["chunk_index"],
            score=round(c.get("score", 0), 4),
        )
        for c in chunks
    ]

    return QueryResponse(
        answer=full_answer,
        sources=sources,
        session_id=body.session_id,
    )


@router.post("/stream")
async def query_streaming(body: QueryRequest):
    """
    SSE streaming endpoint.
    Emits:
      data: <token>\\n\\n        — each LLM token
      data: [SOURCES]<json>\\n\\n — sources metadata after stream ends
      data: [DONE]\\n\\n          — stream complete signal
    """
    db = get_db()
    token_stream, chunks = await run_query(body.question, db)

    async def event_generator():
        async for token in token_stream:
            # Escape newlines so SSE frame stays intact
            escaped = token.replace("\n", "\\n")
            yield f"data: {escaped}\n\n"

        # Send sources as a single frame after the answer
        sources_payload = [
            {
                "filename": c["filename"],
                "chunk_index": c["chunk_index"],
                "score": round(c.get("score", 0), 4),
            }
            for c in chunks
        ]
        yield f"data: [SOURCES]{json.dumps(sources_payload)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )
