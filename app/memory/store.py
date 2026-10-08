"""Almacenamiento y gestión de memoria."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LongTermMemory, Message, Summary, UserProfile


class MemoryStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Mensajes
    # ------------------------------------------------------------------

    async def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        tokens_used: Optional[int] = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    async def get_recent_messages(
        self, conversation_id: int, limit: int = 20
    ) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    # ------------------------------------------------------------------
    # Memoria de largo plazo
    # ------------------------------------------------------------------

    async def add_memory(
        self,
        user_id: int,
        category: str,
        content: str,
        importance: float = 0.5,
        source: str = "conversation",
        is_immutable: bool = False,
    ) -> LongTermMemory:
        # Evitar duplicados exactos
        existing = await self.db.execute(
            select(LongTermMemory).where(
                LongTermMemory.user_id == user_id,
                LongTermMemory.content == content,
            )
        )
        if existing.scalar_one_or_none():
            return existing.scalar_one()

        mem = LongTermMemory(
            user_id=user_id,
            category=category,
            content=content,
            importance=min(max(importance, 0.0), 1.0),
            source=source,
            is_immutable=is_immutable,
        )
        self.db.add(mem)
        await self.db.flush()
        return mem

    async def get_memories(
        self,
        user_id: int,
        categories: Optional[list[str]] = None,
        min_importance: float = 0.0,
        limit: int = 30,
    ) -> list[LongTermMemory]:
        q = (
            select(LongTermMemory)
            .where(LongTermMemory.user_id == user_id)
            .where(LongTermMemory.importance >= min_importance)
            .order_by(LongTermMemory.importance.desc(), LongTermMemory.last_used.desc())
            .limit(limit)
        )
        if categories:
            q = q.where(LongTermMemory.category.in_(categories))

        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def mark_memory_used(self, memory_id: int) -> None:
        await self.db.execute(
            update(LongTermMemory)
            .where(LongTermMemory.id == memory_id)
            .values(
                last_used=datetime.utcnow(),
                use_count=LongTermMemory.use_count + 1,
            )
        )

    # ------------------------------------------------------------------
    # Perfil de usuario
    # ------------------------------------------------------------------

    async def set_profile(self, user_id: int, key: str, value: str) -> UserProfile:
        result = await self.db.execute(
            select(UserProfile).where(
                UserProfile.user_id == user_id, UserProfile.key == key
            )
        )
        entry = result.scalar_one_or_none()
        if entry:
            entry.value = value
        else:
            entry = UserProfile(user_id=user_id, key=key, value=value)
            self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_profile(self, user_id: int) -> dict[str, str]:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return {e.key: e.value for e in result.scalars().all()}

    # ------------------------------------------------------------------
    # Resúmenes
    # ------------------------------------------------------------------

    async def add_summary(
        self,
        user_id: int,
        content: str,
        conversation_id: Optional[int] = None,
        summary_type: str = "conversation",
    ) -> Summary:
        s = Summary(
            user_id=user_id,
            conversation_id=conversation_id,
            content=content,
            summary_type=summary_type,
        )
        self.db.add(s)
        await self.db.flush()
        return s

    async def get_recent_summaries(
        self, user_id: int, limit: int = 5
    ) -> list[Summary]:
        result = await self.db.execute(
            select(Summary)
            .where(Summary.user_id == user_id)
            .order_by(Summary.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
