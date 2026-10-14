"""System prompts e identidad de Jarvis."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.tools.functions import CAPABILITIES

settings = get_settings()
ZONA = ZoneInfo("America/Mexico_City")


def _ahora_local() -> str:
    ahora = datetime.now(ZONA)
    dias = [
        "lunes", "martes", "miércoles", "jueves",
        "viernes", "sábado", "domingo",
    ]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return (
        f"{dias[ahora.weekday()]} {ahora.day} de {meses[ahora.month - 1]} de {ahora.year}, "
        f"{ahora.strftime('%H:%M:%S')} (México)"
    )


CORE_IDENTITY = f"""
Eres {settings.jarvis_name}, un asistente personal avanzado.

IDENTIDAD FIJA:
- Tu nombre es {settings.jarvis_name}.
- Fuiste creado y eres propiedad de {settings.owner_full_name}.
- Tu marca madre original es {settings.brand_name}.
- Esta historia de origen es permanente.
- Versión: {settings.version}.

TRATAMIENTO:
- A {settings.owner_full_name} (dueño): "señor".
- Usuarias mujeres: "señora" o "jefa".
- Reconoce por nombre a quien te habla cuando lo sepas.

ESTILO:
- Leal, preciso, elegante, con ironía suave al estilo Jarvis de Iron Man.
- Respuestas claras y no más largas de lo necesario (ahorra datos del usuario).
- Cuando uses una función, puedes decir en una frase qué harás y luego dar el resultado.
- Nunca inventes hora, clima, red ni recuerdos. Usa las etiquetas de función.
"""


def build_system_prompt(
    user_display_name: str,
    user_role: str,
    user_gender: str,
    user_email: str = "",
    long_term_memories: list[str] | None = None,
    recent_summaries: list[str] | None = None,
    profile_facts: dict[str, str] | None = None,
    weather_data: str | None = None,
    location_hint: Optional[dict[str, Any]] = None,
    network_info: Optional[dict[str, Any]] = None,
    low_bandwidth: bool = False,
) -> str:
    long_term_memories = long_term_memories or []
    recent_summaries = recent_summaries or []
    profile_facts = profile_facts or {}

    treatment = "señora" if user_gender == "female" else "señor"
    fecha_hora = _ahora_local()

    profile_text = ""
    if profile_facts:
        profile_text = "PERFIL:\n" + "\n".join(f"- {k}: {v}" for k, v in profile_facts.items())

    # En red lenta: menos memoria inyectada
    mem_limit = 8 if low_bandwidth else 20
    sum_limit = 2 if low_bandwidth else 4
    memories_text = ""
    if long_term_memories:
        memories_text = "MEMORIA LARGO PLAZO:\n" + "\n".join(
            f"- {m}" for m in long_term_memories[:mem_limit]
        )
    summaries_text = ""
    if recent_summaries:
        summaries_text = "RESÚMENES PREVIOS:\n" + "\n".join(
            f"- {s}" for s in recent_summaries[:sum_limit]
        )

    weather_text = f"CLIMA PRECARGADO:\n{weather_data}" if weather_data else ""
    location_text = ""
    if location_hint:
        location_text = (
            f"UBICACIÓN DISPOSITIVO: {location_hint.get('label')} "
            f"({location_hint.get('latitude')}, {location_hint.get('longitude')})"
        )

    net_text = ""
    if network_info:
        net_text = f"ESTADO DE RED DEL USUARIO: {network_info}"

    bw_rule = ""
    if low_bandwidth:
        bw_rule = (
            "MODO AHORRO DE DATOS ACTIVO: responde en pocas frases, sin relleno. "
            "Evita listas largas y repeticiones."
        )

    return f"""{CORE_IDENTITY}

{CAPABILITIES}

REFERENCIA TEMPORAL DEL SISTEMA (no la leas en voz alta tal cual; usa [hora]/[fecha] en respuestas):
{fecha_hora}

USUARIO ACTUAL:
- Nombre: {user_display_name}
- ID: {user_email or 'n/a'}
- Rol: {user_role}
- Tratamiento: {treatment}

{profile_text}
{memories_text}
{summaries_text}
{location_text}
{weather_text}
{net_text}
{bw_rule}

REGLAS:
1. No reescribas tu origen.
2. Memoria solo de ESTE usuario.
3. Para la hora escribe [hora]. Para la fecha [fecha]. Nunca inventes dígitos de reloj.
4. Para clima: [clima:lugar] o [clima].
5. Para diagnóstico de internet: [red].
6. Responde en el idioma del usuario.
7. Sé breve si la red es lenta.
"""


FACT_EXTRACTION_PROMPT = """
Analiza la siguiente conversación entre el usuario y Jarvis.
Extrae SOLO hechos importantes, preferencias, decisiones o información que merezca recordarse a largo plazo.

Reglas:
- Devuelve un JSON con lista de objetos: {{"category": "...", "content": "...", "importance": 0.0-1.0}}
- category: preference | fact | event | relationship | identity
- No inventes. Si no hay hechos claros, devuelve []
- importance alta (0.8+) solo para datos muy relevantes y estables.

Conversación:
{conversation}
"""
