"""Cliente de Groq con lógica de reactores: 2 principales + 1 de emergencia."""

from typing import Optional

from groq import AsyncGroq

from app.config import get_settings


class GroqClient:
    """
    Lógica de reactores:
    - Reactor 1 y 2 → principales (se usan en orden normal)
    - Reactor 3     → emergencia (solo se activa si fallan 1 y 2)
    """

    def __init__(self):
        self.settings = get_settings()
        self.keys = self.settings.groq_keys_list
        self.model = self.settings.groq_model
        self.last_reactor = "NINGUNO"

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Optional[str]:
        if not self.keys:
            self.last_reactor = "NINGUNO"
            return None

        # Separar principales (índices 0 y 1) y emergencia (índice 2+)
        primary_keys = self.keys[:2]
        emergency_keys = self.keys[2:]

        # 1. Intentar reactores principales
        for i, key in enumerate(primary_keys):
            result = await self._try_key(key, i + 1, messages, temperature, max_tokens)
            if result is not None:
                return result

        # 2. Si ambos principales fallaron → activar emergencia
        for i, key in enumerate(emergency_keys):
            result = await self._try_key(
                key, 3 + i, messages, temperature, max_tokens, emergency=True
            )
            if result is not None:
                return result

        self.last_reactor = "NINGUNO"
        print("[GroqClient] Todos los reactores fallaron.")
        return None

    async def _try_key(
        self,
        key: str,
        reactor_num: int,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        emergency: bool = False,
    ) -> Optional[str]:
        try:
            client = AsyncGroq(api_key=key)
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            label = f"REACTOR {reactor_num}"
            if emergency:
                label += " (EMERGENCIA)"
            self.last_reactor = label
            return response.choices[0].message.content
        except Exception as e:
            print(f"[GroqClient] Reactor {reactor_num} falló: {e}")
            return None
