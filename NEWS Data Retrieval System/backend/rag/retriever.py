import logging
from typing import List, Dict, Optional
from rag.vector_store import search_similar

logger = logging.getLogger(__name__)


async def retrieve_context(
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
) -> List[Dict]:
    results = await search_similar(query, top_k=top_k, category=category)

    # Deduplicate by article_id (keep highest relevance chunk per article)
    seen_articles = {}
    for result in results:
        article_id = result["metadata"].get("article_id", "")
        if article_id not in seen_articles or result["relevance"] > seen_articles[article_id]["relevance"]:
            seen_articles[article_id] = result

    # Sort by relevance
    unique_results = sorted(
        seen_articles.values(),
        key=lambda x: x["relevance"],
        reverse=True,
    )

    return unique_results


def format_context_for_prompt(results: List[Dict]) -> str:
    if not results:
        return "No relevant news articles found in the database."

    context_parts = []
    for i, result in enumerate(results, 1):
        meta = result["metadata"]
        context_parts.append(
            f"[Source {i}] {meta.get('title', 'Unknown')}\n"
            f"Source: {meta.get('source', 'Unknown')}\n"
            f"Category: {meta.get('category', 'Unknown')}\n"
            f"Published: {meta.get('published_at', 'Unknown')}\n"
            f"Content: {result['document']}\n"
        )

    return "\n---\n".join(context_parts)
