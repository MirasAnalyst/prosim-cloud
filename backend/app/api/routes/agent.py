import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.schemas.agent import ChatRequest, ChatResponse
from app.services.openai_agent import AgentService

logger = logging.getLogger(__name__)
router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)

agent_service = AgentService()


@router.post("/chat", response_model=ChatResponse)
@_limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest):
    if not body.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")

    try:
        message, usage, flowsheet_action, completion_log = await agent_service.chat(
            messages=body.messages,
            flowsheet_context=body.flowsheet_context,
        )
        return ChatResponse(
            message=message,
            usage=usage,
            flowsheet_action=flowsheet_action,
            completion_log=completion_log,
        )
    except Exception as exc:
        logger.exception("Agent chat failed")
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")


@router.post("/chat/stream")
@_limiter.limit("20/minute")
async def chat_stream(request: Request, body: ChatRequest):
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
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
