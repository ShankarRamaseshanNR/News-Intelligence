import logging
from typing import List
from google import genai
from config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []

    client = _get_client()
    all_embeddings = []

    # Process in batches of 20
    batch_size = 20
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            result = client.models.embed_content(
                model=settings.EMBEDDING_MODEL,
                contents=batch,
            )
            for embedding in result.embeddings:
                all_embeddings.append(embedding.values)
        except Exception as e:
            logger.error(f"Embedding error for batch {i}: {e}")
            # Fallback: return zero vectors
            for _ in batch:
                all_embeddings.append([0.0] * 3072)

    return all_embeddings


async def generate_single_embedding(text: str) -> List[float]:
    results = await generate_embeddings([text])
    return results[0] if results else [0.0] * 3072
