import httpx
import hashlib
import logging
from typing import List, Optional
from models.schemas import NewsArticle
from config import settings

logger = logging.getLogger(__name__)


def _generate_id(title: str, source: str) -> str:
    raw = f"{title}_{source}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def _simple_sentiment(text: str) -> str:
    if not text:
        return "neutral"
    text_lower = text.lower()
    positive_words = [
        "good", "great", "positive", "success", "win", "growth", "improve",
        "benefit", "breakthrough", "achievement", "hope", "optimistic", "gain",
        "rise", "boost", "progress", "celebrate", "innovation", "recovery",
    ]
    negative_words = [
        "bad", "crisis", "fail", "loss", "threat", "danger", "decline",
        "conflict", "war", "death", "disaster", "attack", "crash", "fear",
        "scandal", "corruption", "collapse", "violence", "recession", "fraud",
    ]
    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)
    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"


async def fetch_news(
    category: Optional[str] = None,
    country: str = "us",
    language: str = "en",
    query: Optional[str] = None,
) -> List[NewsArticle]:
    if not settings.NEWSDATA_API_KEY or settings.NEWSDATA_API_KEY == "your_newsdata_api_key_here":
        logger.error("NEWSDATA_API_KEY is not set! Please set it in .env file.")
        raise ValueError(
            "NewsData API key is not configured. "
            "Please add your API key to the .env file. "
            "Get a free key at https://newsdata.io/register"
        )

    params = {
        "apikey": settings.NEWSDATA_API_KEY,
        "language": language,
    }
    if country:
        params["country"] = country
    if category:
        params["category"] = category
    if query:
        params["q"] = query

    articles = []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(settings.NEWSDATA_BASE_URL, params=params)

            if response.status_code == 401:
                logger.error("NewsData API returned 401 - Invalid API key")
                raise ValueError(
                    "Invalid NewsData API key. Please check your key at https://newsdata.io"
                )
            if response.status_code == 429:
                logger.error("NewsData API rate limit exceeded")
                raise ValueError(
                    "NewsData API rate limit exceeded. Free tier allows 30 requests/day."
                )

            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                error_msg = data.get("results", {}).get("message", str(data))
                logger.error(f"NewsData API error: {error_msg}")
                raise ValueError(f"NewsData API error: {error_msg}")

            for item in data.get("results", []):
                title = item.get("title", "")
                if not title:
                    continue

                source = item.get("source_name", item.get("source_id", "unknown"))
                content = item.get("content") or item.get("description") or ""
                description = item.get("description") or ""

                category_list = item.get("category", [])
                cat = category_list[0] if category_list else category

                article = NewsArticle(
                    article_id=_generate_id(title, source),
                    title=title,
                    description=description,
                    content=content,
                    source_name=source,
                    source_url=item.get("source_url"),
                    category=cat,
                    country=country,
                    language=language,
                    published_at=item.get("pubDate"),
                    url=item.get("link"),
                    image_url=item.get("image_url"),
                    sentiment=_simple_sentiment(f"{title} {description}"),
                    keywords=item.get("keywords") or [],
                )
                articles.append(article)

        logger.info(f"Fetched {len(articles)} articles from NewsData.io")
    except ValueError:
        raise  # Re-raise our custom errors
    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching news: {e}")
        raise ValueError(f"Network error fetching news: {str(e)}")
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        raise ValueError(f"Error fetching news: {str(e)}")

    return articles


async def fetch_multiple_categories(
    categories: List[str] = None,
    country: str = "us",
) -> List[NewsArticle]:
    if categories is None:
        categories = ["top", "technology", "science", "business", "health", "politics", "sports"]

    all_articles = []
    for cat in categories:
        try:
            articles = await fetch_news(category=cat, country=country)
            all_articles.extend(articles)
        except Exception as e:
            logger.error(f"Error fetching category {cat}: {e}")
            continue

    # Deduplicate by article_id
    seen = set()
    unique = []
    for a in all_articles:
        if a.article_id not in seen:
            seen.add(a.article_id)
            unique.append(a)

    return unique
