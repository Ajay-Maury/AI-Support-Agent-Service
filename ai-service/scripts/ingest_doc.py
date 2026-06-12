"""
CLI script to ingest a document directly (bypasses HTTP).
Usage:
  python scripts/ingest_doc.py docs/sample-knowledge-base.md
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import connect_db, get_db
from app.core.config import settings
from app.services.ingestion import run_ingestion
from nanoid import generate
from datetime import datetime, timezone


async def main(file_path: str):
    print(f"🚀  Ingesting: {file_path}")
    await connect_db()
    db = get_db()

    doc_id = generate()
    filename = Path(file_path).name

    await db["doc_metadata"].insert_one({
        "_id": doc_id,
        "filename": filename,
        "file_path": file_path,
        "status": "pending",
        "uploaded_at": datetime.now(timezone.utc),
    })

    result = await run_ingestion(file_path, doc_id, db)
    print(f"✅  Done! doc_id={doc_id}  chunks={result['chunk_count']}")
    print(f"📌  Now create Atlas vector index on 'doc_chunks.embedding' (dims=384, similarity=cosine)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_doc.py <path/to/file.md>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
