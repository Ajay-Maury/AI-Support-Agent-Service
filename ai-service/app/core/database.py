"""
Async MongoDB client using Motor.
Exposes get_db() for dependency injection.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

_client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    # Verify connection
    await _client.admin.command("ping")
    print("✅  Connected to MongoDB Atlas")


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        print("🔌  MongoDB connection closed")


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("Database not initialised — call connect_db() first")
    return _client[settings.mongodb_db_name]
