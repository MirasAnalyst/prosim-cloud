import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project
from app.models.chat import ChatMessage as ChatMessageModel
from app.schemas.agent import ChatHistoryMessage, ChatHistoryResponse, SaveChatMessagesRequest

router = APIRouter()


@router.get("/{project_id}/chat", response_model=ChatHistoryResponse)
async def get_chat_history(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # Verify project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.project_id == project_id)
        .order_by(ChatMessageModel.created_at)
    )
    messages = result.scalars().all()
    return ChatHistoryResponse(
        messages=[
            ChatHistoryMessage(
                id=str(m.id),
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat(),
            )
            for m in messages
        ]
    )


@router.post("/{project_id}/chat", status_code=201)
async def save_chat_messages(
    project_id: uuid.UUID,
    body: SaveChatMessagesRequest,
    db: AsyncSession = Depends(get_db),
):
    # Verify project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    for msg in body.messages:
        chat_msg = ChatMessageModel(
            project_id=project_id,
            role=msg.role,
            content=msg.content,
        )
        db.add(chat_msg)

    await db.flush()
    return {"status": "ok", "count": len(body.messages)}


@router.delete("/{project_id}/chat", status_code=204)
async def delete_chat_history(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # Verify project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    await db.execute(
        delete(ChatMessageModel).where(ChatMessageModel.project_id == project_id)
    )
