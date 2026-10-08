"""Extracción automática de hechos importantes usando el LLM."""

import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.groq_client import GroqClient
from app.ai.prompts import FACT_EXTRACTION_PROMPT
from app.memory.store import MemoryStore


class FactExtractor:
    def __init__(self, db: AsyncSession, ai: GroqClient):
        self.store = MemoryStore(db)
        self.ai = ai

    async def extract_and_store(
        self,
        user_id: int,
        conversation_text: str,
    ) -> list[dict]:
        """
        Analiza el texto de la conversación, extrae hechos y los guarda.
        Devuelve la lista de hechos guardados.
        """
        if not conversation_text.strip():
            return []

        prompt = FACT_EXTRACTION_PROMPT.format(conversation=conversation_text[-6000:])

        messages = [
            {
                "role": "system",
                "content": "Eres un extractor de hechos preciso. Solo respondes en el formato pedido.",
            },
            {"role": "user", "content": prompt},
        ]

        response = await self.ai.chat(messages, temperature=0.1, max_tokens=800)
        if not response:
            return []

        facts = self._parse_facts(response)
        saved = []

        for fact in facts:
            mem = await self.store.add_memory(
                user_id=user_id,
                category=fact["category"],
                content=fact["content"],
                importance=fact["importance"],
                source="auto_extraction",
                is_immutable=fact["category"] == "core_history",
            )
            saved.append(
                {
                    "id": mem.id,
                    "category": mem.category,
                    "content": mem.content,
                    "importance": mem.importance,
                }
            )

        return saved

    def _parse_facts(self, text: str) -> list[dict]:
        if "NINGUNO" in text.upper() and len(text.strip()) < 30:
            return []

        facts = []
        for line in text.splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue

            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                continue

            category = parts[0].lower().replace(" ", "_")
            try:
                importance = float(parts[1])
            except ValueError:
                importance = 0.5

            content = " | ".join(parts[2:]).strip()
            if len(content) < 5:
                continue

            # Normalizar categorías conocidas
            valid_cats = {
                "identity",
                "preference",
                "fact",
                "event",
                "relationship",
                "core_history",
            }
            if category not in valid_cats:
                category = "fact"

            facts.append(
                {
                    "category": category,
                    "importance": min(max(importance, 0.0), 1.0),
                    "content": content,
                }
            )

        return facts
