"""
Ingestion pipeline:
  1. Load file content
  2. Split into overlapping chunks
  3. Embed each chunk (local sentence-transformers)
  4. Upsert into MongoDB doc_chunks collection
  5. Update doc_metadata status
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

from app.core.config import settings
from app.services.embedding import embed_texts


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_file(file_path: str) -> tuple[str, str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if path.suffix not in {".md", ".txt"}:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    return path.read_text(encoding="utf-8"), path.name


def _chunk_text(text: str, filename: str) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
    )
    pieces = splitter.split_text(text)
    return [
        {
            "text": piece,
            "filename": filename,
            "chunk_index": i,
        }
        for i, piece in enumerate(pieces)
    ]


def _embed_chunks(chunks: list[dict]) -> list[dict]:
    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)
    for chunk, vec in zip(chunks, vectors):
        chunk["embedding"] = vec
    return chunks


async def _upsert_to_atlas(
    chunks: list[dict],
    doc_id: str,
    db: AsyncIOMotorDatabase,
) -> int:
    collection = db["doc_chunks"]
    ops = [
        UpdateOne(
            filter={"doc_id": doc_id, "chunk_index": c["chunk_index"]},
            update={
                "$set": {
                    "doc_id": doc_id,
                    "filename": c["filename"],
                    "chunk_index": c["chunk_index"],
                    "text": c["text"],
                    "embedding": c["embedding"],
                }
            },
            upsert=True,
        )
        for c in chunks
    ]
    result = await collection.bulk_write(ops)
    return result.upserted_count + result.modified_count


async def _set_status(doc_id: str, status: str, db: AsyncIOMotorDatabase, **extra):
    await db["doc_metadata"].update_one(
        {"_id": doc_id},
        {"$set": {"status": status, **extra}},
    )


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run_ingestion(file_path: str, doc_id: str, db: AsyncIOMotorDatabase) -> dict:
    try:
        # 1. Load
        await _set_status(doc_id, "chunking", db)
        text, filename = _load_file(file_path)

        # 2. Chunk
        chunks = _chunk_text(text, filename)

        # 3. Embed  (CPU-bound — run in thread pool to not block event loop)
        await _set_status(doc_id, "embedding", db)
        loop = asyncio.get_event_loop()
        chunks = await loop.run_in_executor(None, _embed_chunks, chunks)

        # 4. Upsert
        upserted = await _upsert_to_atlas(chunks, doc_id, db)

        # 5. Mark complete
        await _set_status(
            doc_id,
            "completed",
            db,
            chunk_count=len(chunks),
            ingested_at=datetime.now(timezone.utc),
            embedding_model=settings.embedding_model,
        )

        return {"doc_id": doc_id, "chunk_count": len(chunks), "upserted": upserted}

    except Exception as exc:
        await _set_status(doc_id, "failed", db, error=str(exc))
        raise
