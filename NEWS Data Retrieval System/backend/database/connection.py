from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from datetime import datetime, timezone
from config import settings


class Base(DeclarativeBase):
    pass


class ArticleDB(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    source_name = Column(String(255), nullable=True)
    source_url = Column(String(500), nullable=True)
    category = Column(String(100), nullable=True, index=True)
    country = Column(String(10), nullable=True)
    language = Column(String(10), nullable=True, default="en")
    published_at = Column(String(50), nullable=True)
    url = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)
    sentiment = Column(String(20), nullable=True)
    keywords = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
