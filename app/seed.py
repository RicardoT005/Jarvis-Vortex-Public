"""Inicializa datos núcleo de Jarvis (identidad inmutable)."""

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import LongTermMemory, User, UserProfile

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


async def seed_core_data(db: AsyncSession) -> None:
    """Crea el usuario dueño y las memorias de identidad núcleo si no existen."""

    # 1. Usuario dueño
    result = await db.execute(
        select(User).where(User.username == settings.admin_username)
    )
    owner = result.scalar_one_or_none()

    if not owner:
        owner = User(
            username=settings.admin_username,
            password_hash=pwd_context.hash(settings.admin_password),
            display_name=settings.owner_full_name,
            role="owner",
            gender="male",
        )
        db.add(owner)
        await db.flush()
        print(f"[SEED] Usuario dueño creado: {owner.username}")
    else:
        print(f"[SEED] Usuario dueño ya existe: {owner.username}")

    # 2. Memorias de identidad núcleo (inmutables)
    core_facts = [
        {
            "category": "core_history",
            "content": f"Mi nombre es {settings.jarvis_name}. Soy un asistente personal avanzado.",
            "importance": 1.0,
        },
        {
            "category": "core_history",
            "content": f"Fui creado por {settings.owner_full_name}. Él es mi dueño y creador principal.",
            "importance": 1.0,
        },
        {
            "category": "core_history",
            "content": f"Mi marca madre original es {settings.brand_name}. Esta es mi historia de origen y debe preservarse siempre, aunque en el futuro cambien nombres de marca o proyectos.",
            "importance": 1.0,
        },
        {
            "category": "identity",
            "content": f"Debo dirigirme a {settings.owner_full_name} como 'señor'.",
            "importance": 0.95,
        },
        {
            "category": "identity",
            "content": "A las usuarias mujeres debo dirigirme como 'señora' o 'jefa' según el contexto.",
            "importance": 0.9,
        },
        {
            "category": "identity",
            "content": "Mi personalidad es leal, precisa, elegante y con un toque de ironía suave al estilo del Jarvis de Iron Man.",
            "importance": 0.9,
        },
    ]

    for fact in core_facts:
        existing = await db.execute(
            select(LongTermMemory).where(
                LongTermMemory.user_id == owner.id,
                LongTermMemory.content == fact["content"],
            )
        )
        if not existing.scalar_one_or_none():
            mem = LongTermMemory(
                user_id=owner.id,
                category=fact["category"],
                content=fact["content"],
                importance=fact["importance"],
                source="system",
                is_immutable=True,
            )
            db.add(mem)

    # 3. Perfil básico
    profile_data = {
        "full_name": settings.owner_full_name,
        "short_name": settings.owner_short_name,
        "brand": settings.brand_name,
        "preferred_address": "señor",
    }
    for key, value in profile_data.items():
        existing = await db.execute(
            select(UserProfile).where(
                UserProfile.user_id == owner.id, UserProfile.key == key
            )
        )
        if not existing.scalar_one_or_none():
            db.add(UserProfile(user_id=owner.id, key=key, value=value))

    await db.commit()
    print("[SEED] Datos núcleo de identidad cargados correctamente.")
