import logging
import uuid
from typing import Optional, List
from models.schemas import ChatResponse, SourceCitation
from rag.retriever import retrieve_context, format_context_for_prompt
from rag.generator import generate_response

logger = logging.getLogger(__name__)


async def run_rag_pipeline(
    query: str,
    conversation_id: Optional[str] = None,
    category: Optional[str] = None,
    top_k: int = 5,
) -> ChatResponse:
    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    logger.info(f"RAG pipeline started for query: {query[:100]}...")

    # Step 1: Retrieve relevant context
    results = await retrieve_context(query, top_k=top_k, category=category)
    logger.info(f"Retrieved {len(results)} relevant chunks")

    # Step 2: Format context
    context = format_context_for_prompt(results)

    # Step 3: Generate response
    answer = await generate_response(query, context)

    # Step 4: Build source citations
    sources = []
    for result in results:
        meta = result["metadata"]
        sources.append(
            SourceCitation(
                title=meta.get("title", "Unknown"),
                source=meta.get("source", "Unknown"),
                url=meta.get("url", ""),
                snippet=result["document"][:200] + "..." if len(result["document"]) > 200 else result["document"],
                relevance=result["relevance"],
            )
        )

    return ChatResponse(
        answer=answer,
        sources=sources,
        conversation_id=conversation_id,
    )
