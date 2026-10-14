"""Chat con herramientas en segundo plano y respuesta natural en dos fases."""

from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.groq_client import GroqClient
from app.ai.prompts import build_system_prompt
from app.auth.firebase import get_current_user_firebase
from app.database import get_db
from app.memory.extraction import FactExtractor
from app.memory.retrieval import MemoryRetriever
from app.memory.store import MemoryStore
from app.models import Conversation, User
from app.tools.functions import expand_tags, format_network, _hora, _fecha
from app.tools.weather import get_weather_for_coords, get_weather_for_place

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_label: str | None = None
    file_content: str | None = None
    file_name: str | None = None
    network: Optional[dict[str, Any]] = None
    low_bandwidth: bool = False


class ChatResponse(BaseModel):
    reply: str
    conversation_id: int
    reactor: str
    extracted_facts: list[dict] = []
    tool_notes: list[str] = []
    status: str | None = None


WEATHER_PATTERNS = [
    r"\bclima\b", r"\btiempo\b", r"\btemperatura\b",
    r"\bllueve\b", r"\blluvia\b", r"\bpron[oó]stico\b", r"\bweather\b",
]

NETWORK_DIAG_PATTERNS = [
    r"diagn[oó]stico\s+(de\s+)?(mi\s+)?(red|conexi[oó]n|internet|wifi|wi-?fi)",
    r"(revisa|revisar|analiza|analizar|mide|medir|checa|checar|prueba|probar)\s+(mi\s+)?(red|conexi[oó]n|internet|velocidad|wifi|wi-?fi|latencia)",
    r"(c[oó]mo\s+est[aá]|estado\s+de)\s+(mi\s+)?(red|conexi[oó]n|internet|wifi)",
    r"test\s+de\s+(velocidad|red)",
    r"speed\s*test",
    r"haz\s+un\s+diagn[oó]stico",
]

TIME_PATTERNS = [r"\bhora\b", r"\bqu[eé]\s+hora\b", r"\bfecha\b", r"\bd[ií]a\s+es\s+hoy\b"]


def _match_any(text: str, patterns: list[str]) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in patterns)


def _extract_place(text: str) -> str | None:
    patterns = [
        r"(?:clima|tiempo|temperatura|pron[oó]stico)\s+(?:en|de|para)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ,.-]{2,60})",
        r"(?:en|de)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]{2,40})\s*,\s*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]{2,40})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            if m.lastindex and m.lastindex >= 2:
                return f"{m.group(1).strip()}, {m.group(2).strip()}"
            return m.group(1).strip().rstrip("?.!,")
    return None


async def _run_tools(request: ChatRequest) -> tuple[str, list[str], str | None]:
    notes: list[str] = []
    blocks: list[str] = []
    status_parts: list[str] = []
    msg = request.message

    if _match_any(msg, TIME_PATTERNS):
        blocks.append(f"HORA_REAL={_hora()} | FECHA_REAL={_fecha()}")
        notes.append("hora/fecha")
        status_parts.append("consultando la hora")

    if _match_any(msg, NETWORK_DIAG_PATTERNS):
        net_txt = format_network(request.network)
        blocks.append(f"DATOS_DE_RED_DEL_DISPOSITIVO: {net_txt}")
        notes.append("red")
        status_parts.append("midiendo la conexión")

    if _match_any(msg, WEATHER_PATTERNS):
        try:
            place = _extract_place(msg)
            if place:
                w = await get_weather_for_place(place)
                blocks.append(f"CLIMA_REAL ({place}):\n{w}")
                notes.append(f"clima:{place}")
                status_parts.append(f"consultando el clima en {place}")
            elif request.latitude is not None and request.longitude is not None:
                label = request.location_label or "su ubicación"
                w = await get_weather_for_coords(request.latitude, request.longitude, label)
                blocks.append(f"CLIMA_REAL ({label}):\n{w}")
                notes.append("clima:ubicacion")
                status_parts.append("consultando el clima de su ubicación")
            else:
                w = await get_weather_for_place("Veracruz, Mexico")
                blocks.append(f"CLIMA_REAL (Veracruz, México):\n{w}")
                notes.append("clima:veracruz")
                status_parts.append("consultando el clima")
        except Exception as e:
            blocks.append(f"CLIMA_ERROR: {e}")
            notes.append("clima_error")

    if request.network and "red" not in notes:
        blocks.append(f"CONTEXTO_RED_OPCIONAL: {format_network(request.network)}")

    status = None
    if status_parts:
        status = "Voy a " + ", ".join(status_parts) + ", señor."

    return ("\n\n".join(blocks), notes, status)


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_firebase),
):
    tool_notes: list[str] = []
    user_message = request.message.strip()
    low_bw = bool(request.low_bandwidth)

    if request.file_content and request.file_name:
        limit = 8000 if low_bw else 30000
        snippet = request.file_content[:limit]
        user_message = (
            f"{user_message}\n\n[Archivo: {request.file_name}]\n"
            f"---\n{snippet}\n---"
        )
        tool_notes.append(f"archivo:{request.file_name}")

    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
    else:
        conversation = Conversation(
            user_id=user.id,
            title=(request.message.strip()[:60] or "Nueva conversación"),
        )
        db.add(conversation)
        await db.flush()

    store = MemoryStore(db)
    retriever = MemoryRetriever(db)
    ai = GroqClient()

    await store.add_message(conversation.id, "user", user_message)

    tool_block, notes, status = await _run_tools(request)
    tool_notes.extend(notes)

    context = await retriever.build_context(user.id, conversation.id)
    recent = context["recent_messages"]
    recent = recent[-8:] if low_bw else recent[-14:]

    location_hint = None
    if request.latitude is not None and request.longitude is not None:
        location_hint = {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "label": request.location_label or "ubicación del dispositivo",
        }

    system_prompt = build_system_prompt(
        user_display_name=user.display_name,
        user_role=user.role,
        user_gender=user.gender,
        user_email=user.username,
        long_term_memories=context["long_term_memories"],
        recent_summaries=context["recent_summaries"],
        profile_facts=context["profile_facts"],
        weather_data=None,
        location_hint=location_hint,
        network_info=request.network,
        low_bandwidth=low_bw,
    )

    mask_instructions = """
MODO MÁSCARA (interno, el usuario no ve esto):
- Abajo hay DATOS YA MEDIDOS por el sistema. Son reales.
- Tú NO mides nada: ya está hecho. Tú solo INTERPRETAS y RESUMES.
- Responde en lenguaje natural como Jarvis. SIN etiquetas [hora] [red] [clima].
- No digas "no tengo acceso" si hay datos abajo.
- Sé concreto: lo importante primero. Sin guías largas de ping/Windows salvo que las pidan.
- Si hay red: di si está lenta o aceptable y por qué (tipo 3G/4G, Mb/s, latencia).
- Si hay clima: resume temperatura y condición.
- Si hay hora/fecha: dilas con naturalidad.
"""

    if tool_block:
        system_prompt = (
            system_prompt + "\n\n" + mask_instructions
            + "\n\nDATOS INTERNOS YA OBTENIDOS:\n" + tool_block
        )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(recent)
    if not messages or messages[-1].get("content") != user_message:
        messages.append({"role": "user", "content": user_message})

    max_tokens = 500 if low_bw else 900
    reply = await ai.chat(messages, max_tokens=max_tokens)
    if not reply:
        reply = "Lo siento, señor. No pude completar el análisis en este momento."

    reply = await expand_tags(
        reply,
        user_display_name=user.display_name or "",
        network=request.network,
        latitude=request.latitude,
        longitude=request.longitude,
        location_label=request.location_label,
    )

    await store.add_message(conversation.id, "assistant", reply)

    extracted = []
    if not low_bw:
        try:
            recent_txt = recent[-4:]
            conv_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent_txt)
            conv_text += f"\nuser: {user_message}\nassistant: {reply}"
            extractor = FactExtractor(db, ai)
            extracted = await extractor.extract_and_store(user.id, conv_text)
        except Exception as e:
            print(f"[chat] extracción: {e}")

    await db.commit()

    return ChatResponse(
        reply=reply,
        conversation_id=conversation.id,
        reactor=ai.last_reactor,
        extracted_facts=extracted,
        tool_notes=tool_notes,
        status=status,
    )
