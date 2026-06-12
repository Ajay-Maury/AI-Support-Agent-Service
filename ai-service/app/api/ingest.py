"""
POST /ingest         — upload a .md or .txt file, kick off background ingestion
GET  /ingest/:doc_id — poll ingestion status
"""

import os
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from nanoid import generate

from app.core.database import get_db
from app.models.schemas import IngestResponse, IngestStatusResponse
from app.services.ingestion import run_ingestion

router = APIRouter()
UPLOAD_DIR = "/tmp/rag_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
):
    if not file.filename or not file.filename.endswith((".md", ".txt")):
        raise HTTPException(400, "Only .md and .txt files are supported")

    doc_id = generate()
    safe_name = file.filename.replace(" ", "_")
    file_path = f"{UPLOAD_DIR}/{doc_id}_{safe_name}"

    # Save file to disk
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    db = get_db()

    # Create pending metadata record
    await db["doc_metadata"].insert_one({
        "_id": doc_id,
        "filename": file.filename,
        "file_path": file_path,
        "status": "pending",
        "uploaded_at": datetime.now(timezone.utc),
    })

    # Run pipeline in background so HTTP returns immediately
    background_tasks.add_task(run_ingestion, file_path, doc_id, db)

    return IngestResponse(
        doc_id=doc_id,
        status="pending",
        message=f"Ingestion started for '{file.filename}'",
    )


@router.get("/{doc_id}", response_model=IngestStatusResponse)
async def get_ingest_status(doc_id: str):
    db = get_db()
    doc = await db["doc_metadata"].find_one({"_id": doc_id})
    if not doc:
        raise HTTPException(404, f"Document '{doc_id}' not found")

    return IngestStatusResponse(
        doc_id=doc_id,
        filename=doc.get("filename", ""),
        status=doc.get("status", "unknown"),
        chunk_count=doc.get("chunk_count"),
        uploaded_at=doc.get("uploaded_at"),
        ingested_at=doc.get("ingested_at"),
        error=doc.get("error"),
    )


@router.get("", response_model=list[IngestStatusResponse])
async def list_documents():
    db = get_db()
    cursor = db["doc_metadata"].find({}, {"embedding": 0}).sort("uploaded_at", -1)
    docs = await cursor.to_list(length=50)
    return [
        IngestStatusResponse(
            doc_id=str(d["_id"]),
            filename=d.get("filename", ""),
            status=d.get("status", "unknown"),
            chunk_count=d.get("chunk_count"),
            uploaded_at=d.get("uploaded_at"),
            ingested_at=d.get("ingested_at"),
        )
        for d in docs
    ]
