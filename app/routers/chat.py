"""Endpoint principal de chat."""

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

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: int
    reactor: str
    extracted_facts: list[dict] = []


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_firebase),
):
    # 1. Usuario autenticado vía Firebase (Google)

    # 2. Conversación
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
        conversation = Conversation(user_id=user.id, title=request.message[:60])
        db.add(conversation)
        await db.flush()

    store = MemoryStore(db)
    retriever = MemoryRetriever(db)
    ai = GroqClient()

    # 3. Guardar mensaje del usuario
    await store.add_message(conversation.id, "user", request.message)

    # 4. Construir contexto de memoria
    context = await retriever.build_context(user.id, conversation.id)

    system_prompt = build_system_prompt(
        user_display_name=user.display_name,
        user_role=user.role,
        user_gender=user.gender,
        long_term_memories=context["long_term_memories"],
        recent_summaries=context["recent_summaries"],
        profile_facts=context["profile_facts"],
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(context["recent_messages"])
    # El último mensaje del usuario ya está en recent_messages porque lo acabamos de guardar.
    # Si por alguna razón no, lo añadimos:
    if not messages or messages[-1].get("content") != request.message:
        messages.append({"role": "user", "content": request.message})

    # 5. Llamar al modelo
    reply = await ai.chat(messages)
    if not reply:
        reply = "Lo siento, señor. En este momento no puedo procesar su solicitud. Los reactores no responden."

    # 6. Guardar respuesta
    await store.add_message(conversation.id, "assistant", reply)

    # 7. Extracción de hechos (en segundo plano ligero)
    extracted = []
    try:
        # Solo extraemos de los últimos mensajes para no gastar tokens de más
        recent = context["recent_messages"][-6:]
        conv_text = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
        conv_text += f"\nuser: {request.message}\nassistant: {reply}"

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
    )
