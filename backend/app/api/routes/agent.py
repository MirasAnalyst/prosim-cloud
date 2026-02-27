import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.agent import ChatRequest, ChatResponse
from app.services.openai_agent import AgentService

logger = logging.getLogger(__name__)
router = APIRouter()

agent_service = AgentService()


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    if not body.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")

    try:
        message, usage = await agent_service.chat(
            messages=body.messages,
            flowsheet_context=body.flowsheet_context,
        )
        return ChatResponse(message=message, usage=usage)
    except Exception as exc:
        logger.exception("Agent chat failed")
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    if not body.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")

    async def event_generator():
        try:
            async for chunk in agent_service.chat_stream(
                messages=body.messages,
                flowsheet_context=body.flowsheet_context,
            ):
                yield chunk
        except Exception as exc:
            logger.exception("Agent stream failed")
            yield f"data: {{\"error\": \"{exc}\"}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
