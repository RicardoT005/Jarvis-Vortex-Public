"""Modelos de base de datos de Jarvis."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), default="user")  # owner | collaborator | user
    gender: Mapped[str] = mapped_column(String(16), default="male")  # male | female (para tratamiento)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")
    memories: Mapped[list["LongTermMemory"]] = relationship(back_populates="user")
    profile_entries: Mapped[list["UserProfile"]] = relationship(back_populates="user")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="Nueva conversación")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    summaries: Mapped[list["Summary"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class LongTermMemory(Base):
    """
    Memoria de largo plazo.
    category = core_history | identity | preference | fact | event | relationship
    importance = 0.0 a 1.0 (1.0 = casi inmutable, como la historia de origen)
    """

    __tablename__ = "long_term_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    source: Mapped[str] = mapped_column(String(128), default="conversation")  # conversation | system | manual
    is_immutable: Mapped[bool] = mapped_column(Boolean, default=False)  # True = no se puede borrar/editar fácilmente
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="memories")


class UserProfile(Base):
    """Hechos estructurados clave-valor sobre el usuario o sobre Jarvis."""

    __tablename__ = "user_profile"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profile_entries")


class Summary(Base):
    """Resúmenes de conversaciones o de periodos de tiempo."""

    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("conversations.id"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    summary_type: Mapped[str] = mapped_column(String(32), default="conversation")  # conversation | daily | weekly
    content: Mapped[str] = mapped_column(Text)
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped[Optional["Conversation"]] = relationship(back_populates="summaries")
