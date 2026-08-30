from fastapi import APIRouter
from models.schemas import SearchQuery, SearchResponse, SearchResult, NewsArticle
from rag.vector_store import search_similar
from database.operations import get_article_by_id, db_article_to_schema

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.post("", response_model=SearchResponse)
async def semantic_search(query: SearchQuery):
    results = await search_similar(
        query=query.query,
        top_k=query.top_k,
        category=query.category,
    )

    search_results = []
    seen_articles = set()

    for result in results:
        article_id = result["metadata"].get("article_id", "")
        if article_id in seen_articles:
            continue
        seen_articles.add(article_id)

        db_article = await get_article_by_id(article_id)
        if db_article:
            article = db_article_to_schema(db_article)
        else:
            meta = result["metadata"]
            article = NewsArticle(
                article_id=article_id,
                title=meta.get("title", "Unknown"),
                source_name=meta.get("source", "Unknown"),
                category=meta.get("category", ""),
                published_at=meta.get("published_at", ""),
                url=meta.get("url", ""),
            )

        search_results.append(
            SearchResult(
                article=article,
                relevance_score=result["relevance"],
                matched_snippet=result["document"][:300],
            )
        )

    return SearchResponse(
        query=query.query,
        results=search_results,
        total=len(search_results),
    )
