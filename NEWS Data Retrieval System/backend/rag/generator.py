import logging
from google import genai
from google.genai import types
from config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


SYSTEM_PROMPT = """You are an intelligent news analyst AI assistant. Your role is to answer questions about current news events using the provided source articles.

INSTRUCTIONS:
1. Base your answers ONLY on the provided source articles. Do not make up information.
2. If the sources don't contain enough information to fully answer the question, clearly state what you know and what you don't.
3. Always cite your sources by referencing [Source N] when using information from a specific article.
4. Provide balanced, objective analysis when asked about controversial topics.
5. If asked to verify a claim, compare it against the available sources and provide your assessment.
6. Use clear, well-structured responses with paragraphs or bullet points as appropriate.
7. When multiple sources provide conflicting information, acknowledge the discrepancy.
"""


async def generate_response(query: str, context: str) -> str:
    import asyncio
    client = _get_client()

    prompt = f"""Based on the following news articles, please answer the user's question.

NEWS ARTICLES:
{context}

USER QUESTION: {query}

Please provide a comprehensive, well-cited answer."""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.3,
                    max_output_tokens=2048,
                ),
            )
            return response.text
        except Exception as e:
            error_str = str(e)
            logger.error(f"Gemini generation error (attempt {attempt + 1}): {e}")
            # Retry on rate limit errors
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                    logger.info(f"Rate limited, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
            return f"I encountered an error generating a response. Please try again. Error: {error_str}"
    return "Failed after multiple retries due to rate limiting. Please try again in a minute."
