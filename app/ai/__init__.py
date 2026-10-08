"""Módulo de inteligencia artificial."""

from app.ai.groq_client import GroqClient
from app.ai.prompts import build_system_prompt, CORE_IDENTITY

__all__ = ["GroqClient", "build_system_prompt", "CORE_IDENTITY"]
