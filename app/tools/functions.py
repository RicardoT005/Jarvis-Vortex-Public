"""
Sistema de funciones por etiquetas.

Jarvis escribe etiquetas en su respuesta (ej. [hora]) y el sistema
las reemplaza por datos reales antes de mostrar al usuario.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.tools.weather import get_weather_for_coords, get_weather_for_place

ZONA = ZoneInfo("America/Mexico_City")

# Etiquetas activas (solo lo que funciona al 100%)
CAPABILITIES = """
FUNCIONES DISPONIBLES (úsalas escribiendo la etiqueta exacta en tu respuesta):

1) [hora]     → se reemplaza por la hora real de México (HH:MM:SS)
2) [fecha]    → se reemplaza por la fecha real de México
3) [usuario]  → se reemplaza por el nombre de quien habla ahora
4) [red]      → se reemplaza por el diagnóstico de red del dispositivo del usuario
5) [clima:LUGAR] → consulta clima real. Ejemplo: [clima:Veracruz, México]
6) [clima]    → clima de la ubicación del dispositivo (si la compartió) o Veracruz por defecto

CÓMO USARLAS:
- NO inventes la hora ni el clima. Escribe la etiqueta y el sistema pondrá el dato real.
- Habla natural. Ejemplo: "Son las [hora], señor." → el usuario verá "Son las 23:15:02, señor."
- Si te piden diagnóstico de internet/velocidad/red: usa [red] y comenta el resultado.
- Puedes usar varias etiquetas en la misma respuesta.

CAPACIDADES ACTIVAS (funcionan al 100%):
- Recordar quién eres y quién te creó (Ricardo Torres / MultSoftCreations)
- Saber qué usuario te habla (cuenta Google)
- Memoria de la conversación actual y hechos importantes del usuario
- Reabrir conversaciones anteriores del mismo usuario
- Hora y fecha reales de México con [hora] y [fecha]
- Clima en tiempo real con [clima:lugar]
- Leer archivos .txt que el usuario adjunte
- Usar ubicación del dispositivo si el usuario la comparte
- Diagnóstico básico de red del cliente con [red]
"""


def _hora() -> str:
    return datetime.now(ZONA).strftime("%H:%M:%S")


def _fecha() -> str:
    ahora = datetime.now(ZONA)
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return f"{dias[ahora.weekday()]} {ahora.day} de {meses[ahora.month - 1]} de {ahora.year}"


def format_network(net: Optional[dict[str, Any]]) -> str:
    if not net:
        return "sin datos de red del dispositivo"
    parts = []
    if net.get("type"):
        parts.append(f"tipo {net['type']}")
    if net.get("downlink") is not None:
        parts.append(f"~{net['downlink']} Mb/s estimados")
    if net.get("rtt") is not None:
        parts.append(f"latencia ~{net['rtt']} ms")
    if net.get("save_data"):
        parts.append("modo ahorro de datos activo")
    if net.get("measured_kbps") is not None:
        parts.append(f"prueba local ~{net['measured_kbps']:.0f} kb/s")
    if net.get("quality"):
        parts.append(f"calidad {net['quality']}")
    return ", ".join(parts) if parts else "red detectada sin detalles"


async def expand_tags(
    text: str,
    *,
    user_display_name: str = "",
    network: Optional[dict[str, Any]] = None,
    latitude: float | None = None,
    longitude: float | None = None,
    location_label: str | None = None,
) -> str:
    """Reemplaza etiquetas [hora], [fecha], [usuario], [red], [clima:...] por datos reales."""
    if not text:
        return text

    out = text

    # Simples (síncronos)
    out = re.sub(r"\[hora\]", _hora(), out, flags=re.IGNORECASE)
    out = re.sub(r"\{hora\}", _hora(), out, flags=re.IGNORECASE)
    out = re.sub(r"\[fecha\]", _fecha(), out, flags=re.IGNORECASE)
    out = re.sub(r"\{fecha\}", _fecha(), out, flags=re.IGNORECASE)
    out = re.sub(r"\[usuario\]", user_display_name or "usuario", out, flags=re.IGNORECASE)
    out = re.sub(r"\{usuario\}", user_display_name or "usuario", out, flags=re.IGNORECASE)

    red_txt = format_network(network)
    out = re.sub(r"\[red\]", red_txt, out, flags=re.IGNORECASE)
    out = re.sub(r"\{red\}", red_txt, out, flags=re.IGNORECASE)
    out = re.sub(r"\[velocidad\]", red_txt, out, flags=re.IGNORECASE)

    # Clima con lugar: [clima:Veracruz]
    async def repl_clima_lugar(match: re.Match) -> str:
        place = (match.group(1) or "").strip()
        if not place:
            return "clima no disponible"
        try:
            return await get_weather_for_place(place)
        except Exception as e:
            return f"no pude obtener el clima de {place} ({e})"

    for match in list(re.finditer(r"\[clima:([^\]]+)\]", out, flags=re.IGNORECASE)):
        replacement = await repl_clima_lugar(match)
        out = out.replace(match.group(0), replacement, 1)

    # [clima] sin lugar
    if re.search(r"\[clima\]", out, flags=re.IGNORECASE):
        try:
            if latitude is not None and longitude is not None:
                w = await get_weather_for_coords(
                    latitude, longitude, location_label or "su ubicación"
                )
            else:
                w = await get_weather_for_place("Veracruz, Mexico")
        except Exception as e:
            w = f"no pude obtener el clima ({e})"
        out = re.sub(r"\[clima\]", w, out, flags=re.IGNORECASE)

    return out
