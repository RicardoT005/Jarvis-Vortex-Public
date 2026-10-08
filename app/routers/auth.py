"""Endpoints de autenticación."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token, get_current_user
from app.auth.security import verify_password, hash_password
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    display_name: str
    role: str


class UserInfo(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    gender: str


class RegisterRequest(BaseModel):
    """Solo el owner puede crear usuarios (por ahora se usa desde seed/admin)."""
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=128)
    role: str = Field(default="collaborator")  # owner | collaborator | user
    gender: str = Field(default="male")  # male | female


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    username = request.username.strip().lower()

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada.",
        )

    # Actualizar último login
    user.last_login = datetime.utcnow()
    await db.commit()

    token = create_access_token(user.id, user.username, user.role)

    return LoginResponse(
        access_token=token,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


@router.get("/me", response_model=UserInfo)
async def me(user: User = Depends(get_current_user)):
    return UserInfo(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        gender=user.gender,
    )


@router.post("/register", response_model=UserInfo)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Solo el owner puede crear nuevos usuarios."""
    if current.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el propietario puede crear usuarios.",
        )

    username = request.username.strip().lower()
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ese usuario ya existe.",
        )

    if request.role not in ("owner", "collaborator", "user"):
        raise HTTPException(status_code=400, detail="Rol inválido.")

    user = User(
        username=username,
        password_hash=hash_password(request.password),
        display_name=request.display_name.strip(),
        role=request.role,
        gender=request.gender if request.gender in ("male", "female") else "male",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserInfo(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        gender=user.gender,
    )
