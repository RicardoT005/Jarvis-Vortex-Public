"""Recuperación inteligente de memoria para el contexto del prompt."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.store import MemoryStore


class MemoryRetriever:
    def __init__(self, db: AsyncSession):
        self.store = MemoryStore(db)

    async def build_context(self, user_id: int, conversation_id: int) -> dict:
        """
        Devuelve todo lo necesario para construir el system prompt + historial.
        """
        # 1. Memorias de alta importancia + core_history siempre
        core_and_important = await self.store.get_memories(
            user_id=user_id,
            min_importance=0.6,
            limit=25,
        )

        # 2. Perfil estructurado
        profile = await self.store.get_profile(user_id)

        # 3. Resúmenes recientes
        summaries = await self.store.get_recent_summaries(user_id, limit=4)

        # 4. Historial reciente de la conversación actual
        recent_messages = await self.store.get_recent_messages(
            conversation_id, limit=16
        )

        return {
            "long_term_memories": [m.content for m in core_and_important],
            "profile_facts": profile,
            "recent_summaries": [s.content for s in summaries],
            "recent_messages": [
                {"role": m.role, "content": m.content} for m in recent_messages
            ],
            "memory_objects": core_and_important,  # para marcar como usados después
        }
