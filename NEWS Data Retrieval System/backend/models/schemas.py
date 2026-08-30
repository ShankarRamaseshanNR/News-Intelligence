from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class NewsArticle(BaseModel):
    id: Optional[int] = None
    article_id: str
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = "en"
    published_at: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    sentiment: Optional[str] = None
    keywords: Optional[List[str]] = []
    created_at: Optional[str] = None


class SearchQuery(BaseModel):
    query: str
    category: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    top_k: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    article: NewsArticle
    relevance_score: float
    matched_snippet: str


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int


class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class SourceCitation(BaseModel):
    title: str
    source: Optional[str] = None
    url: Optional[str] = None
    snippet: str
    relevance: float


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
    conversation_id: str


class CategoryCount(BaseModel):
    category: str
    count: int


class TrendPoint(BaseModel):
    date: str
    count: int
    category: Optional[str] = None


class SentimentData(BaseModel):
    positive: int
    negative: int
    neutral: int


class AnalyticsResponse(BaseModel):
    total_articles: int
    categories: List[CategoryCount]
    recent_trend: List[TrendPoint]
    sentiment: SentimentData
    top_sources: List[dict]


class FetchRequest(BaseModel):
    category: Optional[str] = None
    country: Optional[str] = "us"
    language: Optional[str] = "en"
    query: Optional[str] = None
