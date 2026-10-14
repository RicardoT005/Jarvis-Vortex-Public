"""Endpoint principal de chat con memoria, clima, etiquetas y modo ahorro."""

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
from app.tools.functions import expand_tags, format_network
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
    # Diagnóstico de red del cliente
    network: Optional[dict[str, Any]] = None
    low_bandwidth: bool = False


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

NETWORK_PATTERNS = [
    r"\bred\b",
    r"\bwi-?fi\b",
    r"\binternet\b",
    r"\bconexi[oó]n\b",
    r"\bvelocidad\b",
    r"\bancho de banda\b",
    r"\bdiagn[oó]stico\b",
    r"\blatencia\b",
    r"\bping\b",
    r"\bdatos m[oó]viles\b",
]


def _wants_weather(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in WEATHER_PATTERNS)


def _wants_network(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in NETWORK_PATTERNS)


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


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_firebase),
):
    tool_notes: list[str] = []
    user_message = request.message.strip()
    low_bw = bool(request.low_bandwidth)

    # Archivo: en red lenta, menos caracteres
    if request.file_content and request.file_name:
        limit = 8000 if low_bw else 30000
        snippet = request.file_content[:limit]
        user_message = (
            f"{user_message}\n\n"
            f"[Archivo adjunto: {request.file_name}]\n"
            f"--- INICIO DEL ARCHIVO ---\n{snippet}\n--- FIN DEL ARCHIVO ---"
        )
        tool_notes.append(f"Leí el archivo {request.file_name}.")

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

    # Clima solo si lo piden (evita llamadas extra)
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
                weather_block = await get_weather_for_place("Veracruz, Mexico")
                tool_notes.append("Consulté el clima de Veracruz, México.")
        except Exception as e:
            weather_block = f"No pude obtener el clima ({e})."
            tool_notes.append("Falló el clima.")

    context = await retriever.build_context(user.id, conversation.id)

    # Historial más corto en red lenta
    recent = context["recent_messages"]
    if low_bw:
        recent = recent[-8:]
    else:
        recent = recent[-14:]

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
        network_info=request.network,
        low_bandwidth=low_bw,
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(recent)
    if not messages or messages[-1].get("content") != user_message:
        messages.append({"role": "user", "content": user_message})

    max_tokens = 600 if low_bw else 1200
    # Si piden diagnóstico de red, no dejamos que el modelo diga "no puedo"
    if _wants_network(request.message):
        net_txt = format_network(request.network)
        if request.network:
            reply = (
                "Voy a revisar el estado de su conexión con los datos del dispositivo, señor.\n\n"
                f"Diagnóstico de red: {net_txt}.\n\n"
                "Esto es una estimación del navegador (tipo de red, latencia y velocidad aproximada), "
                "no un speedtest completo del proveedor. "
                "Si la calidad aparece como baja, conviene usar menos pestañas o cambiar a una red más estable."
            )
            tool_notes.append("Diagnóstico de red forzado con datos del cliente.")
        else:
            reply = (
                "Intenté leer el estado de su red, pero el navegador no envió datos de conexión. "
                "Pruebe recargar la página o usar un navegador que reporte el tipo de red (Chrome suele hacerlo)."
            )
            tool_notes.append("Diagnóstico de red sin datos del cliente.")
    else:
        reply = await ai.chat(messages, max_tokens=max_tokens)
        if not reply:
            reply = "Lo siento. Los reactores no responden en este momento."

        # Si el modelo habló de hora sin etiqueta, forzamos dato real al final no hace falta;
        # expandimos etiquetas siempre.
        # Si preguntó la hora y no usó [hora], reescribimos respuesta corta.
        if re.search(r"\bhora\b|\bqu[eé]\s+hora\b", request.message, re.IGNORECASE):
            if "[hora]" not in reply.lower() and not re.search(r"\d{1,2}:\d{2}", reply):
                reply = "Son las [hora], señor."

    # Expandir etiquetas [hora], [fecha], [clima:..], [red], etc.
    reply = await expand_tags(
        reply,
        user_display_name=user.display_name or "",
        network=request.network,
        latitude=request.latitude,
        longitude=request.longitude,
        location_label=request.location_label,
    )
    tool_notes.append("Etiquetas de función aplicadas.")

    await store.add_message(conversation.id, "assistant", reply)

    extracted = []
    # En red lenta no gastamos otra llamada al modelo extrayendo hechos
    if not low_bw:
        try:
            recent_txt = recent[-4:]
            conv_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent_txt)
            conv_text += f"\nuser: {user_message}\nassistant: {reply}"
            extractor = FactExtractor(db, ai)
            extracted = await extractor.extract_and_store(user.id, conv_text)
        except Exception as e:
            print(f"[chat] Error en extracción: {e}")

    await db.commit()

    return ChatResponse(
        reply=reply,
        conversation_id=conversation.id,
        reactor=ai.last_reactor,
        extracted_facts=extracted,
        tool_notes=tool_notes,
    )
