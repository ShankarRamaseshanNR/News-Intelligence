import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database.connection import init_db
from ingestion.scheduler import start_scheduler, stop_scheduler
from api.news import router as news_router
from api.search import router as search_router
from api.chat import router as chat_router
from api.analytics import router as analytics_router
from api.spark_api import router as spark_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting News RAG System...")
    await init_db()
    logger.info("Database initialized")
    start_scheduler()
    logger.info("Scheduler started")
    yield
    stop_scheduler()
    logger.info("Shutdown complete")


app = FastAPI(
    title="News Intelligence RAG API",
    description="Intelligent News Retrieval and Analysis System Using RAG",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(news_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(analytics_router)
app.include_router(spark_router)


@app.get("/")
async def root():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "name": "News Intelligence RAG API",
        "version": "1.0.0",
        "endpoints": {
            "news": "/api/news",
            "search": "/api/search",
            "chat": "/api/chat",
            "analytics": "/api/analytics",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# Mount static files AFTER API routes to avoid conflicts
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
