"""
JARVIS VORTEX v2
Asistente personal avanzado - Backend FastAPI
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.config import get_settings
from app.database import init_db, AsyncSessionLocal
from app.seed import seed_core_data
from app.routers import chat
from app.routers import auth

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("⚡ Iniciando Jarvis Vortex...")
    await init_db()
    async with AsyncSessionLocal() as db:
        await seed_core_data(db)
    print(f"✅ Jarvis v{settings.version} listo. Dueño: {settings.owner_full_name}")
    yield
    # Shutdown
    print("👋 Jarvis detenido.")


app = FastAPI(
    title="Jarvis Vortex",
    description="Asistente personal avanzado creado por Ricardo Torres · MultSoftCreations",
    version=settings.version,
    lifespan=lifespan,
)

# CORS (necesario cuando el frontend esté en GitHub Pages)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción restringir al dominio de GitHub Pages
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(chat.router)

# Frontend estático (cuando exista)
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    index = os.path.join(static_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {
        "name": "Jarvis Vortex",
        "version": settings.version,
        "owner": settings.owner_full_name,
        "brand": settings.brand_name,
        "status": "online",
        "message": "Señor, el sistema está operativo. Use /docs para la documentación de la API.",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.version}
