"""Listado e historial de conversaciones por usuario."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.firebase import get_current_user_firebase
from app.database import get_db
from app.models import Conversation, Message, User

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str | None = None


class ConversationOut(BaseModel):
    id: int
    title: str
    updated_at: str | None = None
    is_archived: bool = False


@router.get("/", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_firebase),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id, Conversation.is_archived == False)  # noqa: E712
        .order_by(Conversation.updated_at.desc())
        .limit(40)
    )
    rows = result.scalars().all()
    return [
        ConversationOut(
            id=c.id,
            title=c.title or "Conversación",
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
            is_archived=c.is_archived,
        )
        for c in rows
    ]


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_firebase),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.asc())
        .limit(200)
    )
    messages = msg_result.scalars().all()
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in messages
    ]
