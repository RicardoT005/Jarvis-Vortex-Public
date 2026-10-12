"""Endpoint principal de chat con memoria, clima y archivos."""

from __future__ import annotations

import re

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
from app.tools.weather import get_weather_for_coords, get_weather_for_place

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    conversation_id: int | None = None
    # Ubicación del dispositivo (opcional)
    latitude: float | None = None
    longitude: float | None = None
    location_label: str | None = None
    # Contenido de archivo .txt ya leído en el cliente
    file_content: str | None = None
    file_name: str | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: int
    reactor: str
    extracted_facts: list[dict] = []
    tool_notes: list[str] = []


WEATHER_PATTERNS = [
    r"\bclima\b",
    r"\btiempo\b",
    r"\btemperatura\b",
    r"\bllueve\b",
    r"\blluvia\b",
    r"\bpron[oó]stico\b",
    r"\bweather\b",
]


def _wants_weather(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in WEATHER_PATTERNS)


def _extract_place(text: str) -> str | None:
    """Intenta extraer un lugar después de palabras clave."""
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


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_firebase),
):
    tool_notes: list[str] = []
    user_message = request.message.strip()

    # Archivo adjunto
    if request.file_content and request.file_name:
        snippet = request.file_content[:45000]
        user_message = (
            f"{user_message}\n\n"
            f"[Archivo adjunto: {request.file_name}]\n"
            f"--- INICIO DEL ARCHIVO ---\n{snippet}\n--- FIN DEL ARCHIVO ---"
        )
        tool_notes.append(f"Leí el archivo {request.file_name}.")

    # Conversación
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
        title_src = request.message.strip()[:60] or "Nueva conversación"
        conversation = Conversation(user_id=user.id, title=title_src)
        db.add(conversation)
        await db.flush()

    store = MemoryStore(db)
    retriever = MemoryRetriever(db)
    ai = GroqClient()

    await store.add_message(conversation.id, "user", user_message)

    # Herramienta de clima si aplica
    weather_block = ""
    if _wants_weather(request.message):
        try:
            place = _extract_place(request.message)
            if place:
                weather_block = await get_weather_for_place(place)
                tool_notes.append(f"Consulté el clima de {place}.")
            elif request.latitude is not None and request.longitude is not None:
                label = request.location_label or "su ubicación actual"
                weather_block = await get_weather_for_coords(
                    request.latitude, request.longitude, label
                )
                tool_notes.append("Consulté el clima de su ubicación.")
            else:
                # Por defecto Veracruz, México si piden clima sin lugar
                weather_block = await get_weather_for_place("Veracruz, Mexico")
                tool_notes.append("Consulté el clima de Veracruz, México (por defecto).")
        except Exception as e:
            weather_block = f"No pude obtener el clima en este momento ({e})."
            tool_notes.append("Falló la consulta de clima.")

    context = await retriever.build_context(user.id, conversation.id)

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
        weather_data=weather_block or None,
        location_hint=location_hint,
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(context["recent_messages"])
    if not messages or messages[-1].get("content") != user_message:
        messages.append({"role": "user", "content": user_message})

    reply = await ai.chat(messages)
    if not reply:
        reply = (
            "Lo siento. En este momento no puedo procesar su solicitud. "
            "Los reactores no responden."
        )

    await store.add_message(conversation.id, "assistant", reply)

    extracted = []
    try:
        recent = context["recent_messages"][-6:]
        conv_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
        conv_text += f"\nuser: {user_message}\nassistant: {reply}"
        extractor = FactExtractor(db, ai)
        extracted = await extractor.extract_and_store(user.id, conv_text)
    except Exception as e:
        print(f"[chat] Error en extracción de hechos: {e}")

    await db.commit()

    return ChatResponse(
        reply=reply,
        conversation_id=conversation.id,
        reactor=ai.last_reactor,
        extracted_facts=extracted,
        tool_notes=tool_notes,
    )
