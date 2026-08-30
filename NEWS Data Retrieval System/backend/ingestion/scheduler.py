import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from ingestion.news_fetcher import fetch_multiple_categories
from database.operations import insert_articles_batch
from rag.vector_store import index_articles
from config import settings

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def _run_ingestion_sync():
    """Wrapper to run async ingestion from a sync scheduler context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_run_ingestion_pipeline())
        else:
            loop.run_until_complete(_run_ingestion_pipeline())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run_ingestion_pipeline())


async def _run_ingestion_pipeline():
    logger.info("Starting news ingestion pipeline...")
    try:
        articles = await fetch_multiple_categories(
            categories=["top", "technology", "science", "business", "health"],
            country="us",
        )
        logger.info(f"Fetched {len(articles)} articles total")

        if articles:
            inserted = await insert_articles_batch(articles)
            logger.info(f"Inserted {inserted} new articles into database")

            if inserted > 0:
                await index_articles(articles)
                logger.info("Indexed articles in vector store")

    except Exception as e:
        logger.error(f"Ingestion pipeline error: {e}", exc_info=True)


def start_scheduler():
    scheduler.add_job(
        _run_ingestion_sync,
        "interval",
        minutes=settings.FETCH_INTERVAL_MINUTES,
        id="news_fetch",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started - fetching every {settings.FETCH_INTERVAL_MINUTES} minutes")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
