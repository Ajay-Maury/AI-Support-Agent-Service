"""
Pydantic schemas for request / response validation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Ingest ────────────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    doc_id: str
    status: str
    message: str


class IngestStatusResponse(BaseModel):
    doc_id: str
    filename: str
    status: str                    # pending | chunking | embedding | completed | failed
    chunk_count: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    ingested_at: Optional[datetime] = None
    error: Optional[str] = None


# ── Query ─────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None


class ChunkSource(BaseModel):
    filename: str
    chunk_index: int
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[ChunkSource]
    session_id: Optional[str] = None
