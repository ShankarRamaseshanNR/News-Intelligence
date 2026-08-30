from fastapi import APIRouter
from models.schemas import ChatMessage, ChatResponse
from rag.pipeline import run_rag_pipeline

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(message: ChatMessage):
    response = await run_rag_pipeline(
        query=message.message,
        conversation_id=message.conversation_id,
    )
    return response
