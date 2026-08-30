from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, text
from database.connection import ArticleDB, async_session
from models.schemas import NewsArticle
from typing import List, Optional
from datetime import datetime, timezone
import hashlib


def generate_article_id(title: str, source: str) -> str:
    raw = f"{title}_{source}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()


async def insert_article(article: NewsArticle) -> Optional[ArticleDB]:
    async with async_session() as session:
        existing = await session.execute(
            select(ArticleDB).where(ArticleDB.article_id == article.article_id)
        )
        if existing.scalar_one_or_none():
            return None

        db_article = ArticleDB(
            article_id=article.article_id,
            title=article.title,
            description=article.description,
            content=article.content,
            source_name=article.source_name,
            source_url=article.source_url,
            category=article.category,
            country=article.country,
            language=article.language,
            published_at=article.published_at,
            url=article.url,
            image_url=article.image_url,
            sentiment=article.sentiment,
            keywords=article.keywords or [],
            created_at=datetime.now(timezone.utc),
        )
        session.add(db_article)
        await session.commit()
        await session.refresh(db_article)
        return db_article


async def insert_articles_batch(articles: List[NewsArticle]) -> int:
    count = 0
    for article in articles:
        result = await insert_article(article)
        if result:
            count += 1
    return count


async def get_articles(
    limit: int = 20,
    offset: int = 0,
    category: Optional[str] = None,
) -> List[ArticleDB]:
    async with async_session() as session:
        query = select(ArticleDB).order_by(desc(ArticleDB.created_at))
        if category:
            query = query.where(ArticleDB.category == category)
        query = query.limit(limit).offset(offset)
        result = await session.execute(query)
        return result.scalars().all()


async def get_article_by_id(article_id: str) -> Optional[ArticleDB]:
    async with async_session() as session:
        result = await session.execute(
            select(ArticleDB).where(ArticleDB.article_id == article_id)
        )
        return result.scalar_one_or_none()


async def get_total_count() -> int:
    async with async_session() as session:
        result = await session.execute(select(func.count(ArticleDB.id)))
        return result.scalar() or 0


async def get_category_counts() -> List[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(ArticleDB.category, func.count(ArticleDB.id).label("count"))
            .where(ArticleDB.category.isnot(None))
            .group_by(ArticleDB.category)
            .order_by(desc("count"))
        )
        return [{"category": row[0], "count": row[1]} for row in result.all()]


async def get_sentiment_counts() -> dict:
    async with async_session() as session:
        result = await session.execute(
            select(ArticleDB.sentiment, func.count(ArticleDB.id).label("count"))
            .where(ArticleDB.sentiment.isnot(None))
            .group_by(ArticleDB.sentiment)
        )
        counts = {"positive": 0, "negative": 0, "neutral": 0}
        for row in result.all():
            if row[0] in counts:
                counts[row[0]] = row[1]
        return counts


async def get_top_sources(limit: int = 10) -> List[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(ArticleDB.source_name, func.count(ArticleDB.id).label("count"))
            .where(ArticleDB.source_name.isnot(None))
            .group_by(ArticleDB.source_name)
            .order_by(desc("count"))
            .limit(limit)
        )
        return [{"source": row[0], "count": row[1]} for row in result.all()]


async def get_daily_counts(days: int = 7) -> List[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(
                func.date(ArticleDB.created_at).label("date"),
                func.count(ArticleDB.id).label("count"),
            )
            .group_by(func.date(ArticleDB.created_at))
            .order_by(desc("date"))
            .limit(days)
        )
        return [{"date": str(row[0]), "count": row[1]} for row in result.all()]


def db_article_to_schema(db_article: ArticleDB) -> NewsArticle:
    return NewsArticle(
        id=db_article.id,
        article_id=db_article.article_id,
        title=db_article.title,
        description=db_article.description,
        content=db_article.content,
        source_name=db_article.source_name,
        source_url=db_article.source_url,
        category=db_article.category,
        country=db_article.country,
        language=db_article.language,
        published_at=db_article.published_at,
        url=db_article.url,
        image_url=db_article.image_url,
        sentiment=db_article.sentiment,
        keywords=db_article.keywords or [],
        created_at=str(db_article.created_at) if db_article.created_at else None,
    )
