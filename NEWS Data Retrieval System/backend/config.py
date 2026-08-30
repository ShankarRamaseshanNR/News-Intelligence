import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

class Settings:
    NEWSDATA_API_KEY: str = os.getenv("NEWSDATA_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./news.db")
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    FETCH_INTERVAL_MINUTES: int = int(os.getenv("FETCH_INTERVAL_MINUTES", "15"))
    NEWSDATA_BASE_URL: str = "https://newsdata.io/api/1/latest"
    GEMINI_MODEL: str = "gemini-2.0-flash-lite"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K_RESULTS: int = 5

settings = Settings()
