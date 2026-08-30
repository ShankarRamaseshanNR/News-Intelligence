from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
from models.schemas import NewsArticle, FetchRequest
from database.operations import (
    get_articles, get_article_by_id, db_article_to_schema,
    insert_articles_batch,
)
from ingestion.news_fetcher import fetch_news
from rag.vector_store import index_articles

router = APIRouter(prefix="/api/news", tags=["News"])


@router.get("", response_model=List[NewsArticle])
async def list_articles(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
):
    db_articles = await get_articles(limit=limit, offset=offset, category=category)
    return [db_article_to_schema(a) for a in db_articles]


@router.get("/{article_id}")
async def get_single_article(article_id: str):
    article = await get_article_by_id(article_id)
    if not article:
        return {"error": "Article not found"}
    return db_article_to_schema(article)


@router.post("/fetch")
async def trigger_fetch(request: FetchRequest):
    try:
        articles = await fetch_news(
            category=request.category,
            country=request.country,
            language=request.language,
            query=request.query,
        )

        if articles:
            inserted = await insert_articles_batch(articles)
            if inserted > 0:
                await index_articles(articles)
            return {
                "status": "success",
                "fetched": len(articles),
                "new_inserted": inserted,
            }

        return {"status": "success", "fetched": 0, "new_inserted": 0}

    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": str(e)},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Unexpected error: {str(e)}"},
        )
