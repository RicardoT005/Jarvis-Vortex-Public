"""Clima en tiempo real vía Open-Meteo (sin API key)."""

from __future__ import annotations

from typing import Any, Optional

import httpx

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO = {
    0: "despejado",
    1: "mayormente despejado",
    2: "parcialmente nublado",
    3: "nublado",
    45: "niebla",
    48: "niebla con escarcha",
    51: "llovizna ligera",
    53: "llovizna",
    55: "llovizna intensa",
    61: "lluvia ligera",
    63: "lluvia",
    65: "lluvia intensa",
    71: "nieve ligera",
    73: "nieve",
    75: "nieve intensa",
    80: "chubascos ligeros",
    81: "chubascos",
    82: "chubascos fuertes",
    95: "tormenta",
    96: "tormenta con granizo",
    99: "tormenta fuerte con granizo",
}


async def geocode(place: str) -> Optional[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            GEOCODE_URL,
            params={"name": place, "count": 1, "language": "es", "format": "json"},
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        if not results:
            return None
        item = results[0]
        return {
            "name": item.get("name"),
            "country": item.get("country"),
            "admin1": item.get("admin1"),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "timezone": item.get("timezone"),
        }


async def forecast_by_coords(
    lat: float,
    lon: float,
    timezone: str = "auto",
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "timezone": timezone,
                "forecast_days": 3,
            },
        )
        r.raise_for_status()
        return r.json()


def format_weather(place_label: str, data: dict[str, Any]) -> str:
    current = data.get("current") or {}
    daily = data.get("daily") or {}
    code = current.get("weather_code", 0)
    desc = WMO.get(code, f"código {code}")
    temp = current.get("temperature_2m")
    feels = current.get("apparent_temperature")
    humidity = current.get("relative_humidity_2m")
    wind = current.get("wind_speed_10m")

    lines = [
        f"Clima actual en {place_label}:",
        f"- Condición: {desc}",
        f"- Temperatura: {temp} °C (sensación {feels} °C)",
        f"- Humedad: {humidity}%",
        f"- Viento: {wind} km/h",
    ]

    times = daily.get("time") or []
    tmax = daily.get("temperature_2m_max") or []
    tmin = daily.get("temperature_2m_min") or []
    precip = daily.get("precipitation_probability_max") or []
    if times:
        lines.append("Pronóstico próximos días:")
        for i, day in enumerate(times[:3]):
            lines.append(
                f"- {day}: máx {tmax[i] if i < len(tmax) else '?'} °C / "
                f"mín {tmin[i] if i < len(tmin) else '?'} °C, "
                f"prob. lluvia {precip[i] if i < len(precip) else '?'}%"
            )
    return "\n".join(lines)


async def get_weather_for_place(place: str) -> str:
    geo = await geocode(place)
    if not geo:
        return f"No pude encontrar la ubicación «{place}»."
    data = await forecast_by_coords(
        geo["latitude"],
        geo["longitude"],
        timezone=geo.get("timezone") or "auto",
    )
    label = ", ".join(
        p for p in [geo.get("name"), geo.get("admin1"), geo.get("country")] if p
    )
    return format_weather(label, data)


async def get_weather_for_coords(lat: float, lon: float, label: str = "su ubicación") -> str:
    data = await forecast_by_coords(lat, lon, timezone="auto")
    return format_weather(label, data)
