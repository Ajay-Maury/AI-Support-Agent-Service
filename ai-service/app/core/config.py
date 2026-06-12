"""
Central config — all env vars in one place.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Groq
    groq_api_key: str
    groq_model: str = "llama3-8b-8192"        # free-tier model
    groq_embedding_model: str = "llama3-8b-8192"

    # MongoDB Atlas
    mongodb_uri: str
    mongodb_db_name: str = "rag_support_agent"

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 64

    # Retrieval
    top_k: int = 3
    min_score: float = 0.70
    num_candidates: int = 100

    # HuggingFace (local embeddings — free, no API key needed)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
