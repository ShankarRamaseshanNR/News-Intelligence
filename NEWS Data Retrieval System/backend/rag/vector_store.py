import logging
from typing import List, Optional, Dict
import chromadb
from models.schemas import NewsArticle
from rag.embeddings import generate_embeddings, generate_single_embedding
from config import settings

logger = logging.getLogger(__name__)

_chroma_client = None
_collection = None


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
        )
        _collection = _chroma_client.get_or_create_collection(
            name="news_articles",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    if not text or len(text) < 100:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind(".")
            last_newline = chunk.rfind("\n")
            break_point = max(last_period, last_newline)
            if break_point > chunk_size * 0.3:
                chunk = chunk[: break_point + 1]
                end = start + break_point + 1

        chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if c]


async def index_articles(articles: List[NewsArticle]) -> int:
    collection = _get_collection()
    indexed = 0

    for article in articles:
        try:
            # Combine title + description + content for richer embedding
            full_text = f"{article.title}. {article.description or ''}. {article.content or ''}"
            chunks = _chunk_text(full_text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)

            if not chunks:
                continue

            embeddings = await generate_embeddings(chunks)

            ids = []
            documents = []
            metadatas = []
            valid_embeddings = []

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                doc_id = f"{article.article_id}_chunk_{i}"

                # Check if already exists
                try:
                    existing = collection.get(ids=[doc_id])
                    if existing and existing["ids"]:
                        continue
                except Exception:
                    pass

                ids.append(doc_id)
                documents.append(chunk)
                metadatas.append({
                    "article_id": article.article_id,
                    "title": article.title,
                    "source": article.source_name or "unknown",
                    "category": article.category or "general",
                    "published_at": article.published_at or "",
                    "url": article.url or "",
                    "chunk_index": i,
                })
                valid_embeddings.append(embedding)

            if ids:
                collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=valid_embeddings,
                )
                indexed += 1

        except Exception as e:
            logger.error(f"Error indexing article {article.article_id}: {e}")

    logger.info(f"Indexed {indexed} articles into ChromaDB")
    return indexed


async def search_similar(
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
) -> List[Dict]:
    collection = _get_collection()

    query_embedding = await generate_single_embedding(query)

    where_filter = None
    if category:
        where_filter = {"category": category}

    try:
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, collection.count()) if collection.count() > 0 else top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            kwargs["where"] = where_filter

        results = collection.query(**kwargs)
    except Exception as e:
        logger.error(f"ChromaDB search error: {e}")
        return []

    search_results = []
    if results and results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i] if results["distances"] else 0
            relevance = max(0, 1 - distance)  # cosine distance to similarity

            search_results.append({
                "id": doc_id,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "relevance": round(relevance, 4),
            })

    return search_results


def get_collection_count() -> int:
    try:
        collection = _get_collection()
        return collection.count()
    except Exception:
        return 0
