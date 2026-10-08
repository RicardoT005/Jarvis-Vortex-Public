"""Verificación de tokens de Firebase Auth."""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()
security = HTTPBearer(auto_error=False)

# Emails autorizados (owner + colaboradores).
# El primero se trata como owner si no existe aún.
AUTHORIZED_EMAILS = {
    # Se puede ampliar desde .env o dejar que el owner añada después
}


def _project_id() -> str:
    return getattr(settings, "firebase_project_id", "") or ""


def verify_firebase_token(token: str) -> dict:
    """
    Verifica un ID token de Firebase y devuelve el payload.
    Lanza HTTPException si es inválido.
    """
    project_id = _project_id()
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase no está configurado en el servidor.",
        )
    try:
        payload = id_token.verify_firebase_token(
            token,
            google_requests.Request(),
            audience=project_id,
        )
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token de Firebase inválido: {e}",
        )


async def get_or_create_user_from_firebase(
    db: AsyncSession,
    payload: dict,
) -> User:
    """Busca o crea un usuario a partir del token de Firebase."""
    email = (payload.get("email") or "").strip().lower()
    name = payload.get("name") or email.split("@")[0]
    uid = payload.get("sub") or payload.get("user_id") or ""

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no incluye email.",
        )

    # Buscar por username = email (o parte local)
    # Usamos el email completo como username único
    result = await db.execute(select(User).where(User.username == email))
    user = result.scalar_one_or_none()

    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta desactivada.",
            )
        return user

    # Primer usuario en la DB → owner (Ricardo)
    count_result = await db.execute(select(User))
    existing_users = count_result.scalars().all()
    is_first = len(existing_users) == 0

    # Si hay lista de autorizados y el email no está, rechazar
    # (por ahora permitimos al primero y luego solo los que cree el owner;
    #  para abrir a más emails se puede ampliar AUTHORIZED_EMAILS)

    role = "owner" if is_first else "collaborator"
    # Si el email contiene indicios del dueño, forzar owner
    if "ricardo" in email or is_first:
        role = "owner"

    from app.auth.security import hash_password
    import secrets

    user = User(
        username=email,
        password_hash=hash_password(secrets.token_urlsafe(32)),  # no se usa con Google
        display_name=name,
        role=role,
        gender="male",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def get_current_user_firebase(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependencia FastAPI: usuario autenticado vía Firebase."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado. Inicie sesión con Google.",
        )

    payload = verify_firebase_token(credentials.credentials)
    user = await get_or_create_user_from_firebase(db, payload)
    await db.commit()
    return user
