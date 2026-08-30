from fastapi import APIRouter
from models.schemas import AnalyticsResponse, CategoryCount, TrendPoint, SentimentData
from database.operations import (
    get_total_count, get_category_counts,
    get_sentiment_counts, get_top_sources, get_daily_counts,
)
from rag.vector_store import get_collection_count

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("", response_model=AnalyticsResponse)
async def get_analytics():
    total = await get_total_count()
    categories_raw = await get_category_counts()
    sentiment_raw = await get_sentiment_counts()
    sources = await get_top_sources(limit=10)
    daily = await get_daily_counts(days=14)

    categories = [
        CategoryCount(category=c["category"], count=c["count"])
        for c in categories_raw
    ]

    trend = [
        TrendPoint(date=d["date"], count=d["count"])
        for d in daily
    ]

    sentiment = SentimentData(
        positive=sentiment_raw.get("positive", 0),
        negative=sentiment_raw.get("negative", 0),
        neutral=sentiment_raw.get("neutral", 0),
    )

    return AnalyticsResponse(
        total_articles=total,
        categories=categories,
        recent_trend=trend,
        sentiment=sentiment,
        top_sources=sources,
    )


@router.get("/vector-count")
async def vector_count():
    count = get_collection_count()
    return {"vector_count": count}
