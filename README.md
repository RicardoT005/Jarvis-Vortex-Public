# Jarvis Vortex v2

Asistente personal avanzado creado por **Ricardo Torres** · Marca madre: **MultSoftCreations**

## Arquitectura de despliegue (gratis)

| Pieza | Servicio | Para qué |
|-------|----------|----------|
| **Frontend** | GitHub Pages | Interfaz web (HTML/JS) |
| **Backend** | Hugging Face Spaces | FastAPI + Groq + memoria |
| **Base de datos** | Supabase (PostgreSQL) | Memoria persistente multi-usuario |
| **Login** | Firebase Auth (Google) | Entrar con cuenta de Google |

No usamos solo Firebase/Firestore para la memoria porque ya tenemos un sistema SQL robusto (conversaciones, hechos, identidad inmutable). **Supabase** es Postgres gratis y se conecta casi igual que SQLite.

---

## Estructura

```
jarvis/
├── app/                 # Backend FastAPI
├── static/              # Frontend
│   ├── index.html
│   └── config.js        # URL del backend (para GitHub Pages)
├── Dockerfile           # Para Hugging Face Spaces
├── requirements.txt
├── .env.example
└── README.md
```

---

## Guía de despliegue (paso a paso)

### A) Supabase (base de datos) — 10 min

1. Entra a https://supabase.com → Sign up (con Google).
2. **New project** → nombre `jarvis-vortex` → elige contraseña fuerte → región cercana.
3. Espera a que el proyecto esté listo.
4. Ve a **Project Settings → Database**.
5. Copia la **Connection string** (URI), modo **URI**.
6. Debe quedar algo así (cambia a asyncpg):

```
postgresql+asyncpg://postgres.XXXX:TU_PASSWORD@aws-0-xx.pooler.supabase.com:6543/postgres
```

O la directa:

```
postgresql+asyncpg://postgres:TU_PASSWORD@db.XXXX.supabase.co:5432/postgres
```

Guárdala: será tu `DATABASE_URL`.

---

### B) Hugging Face Spaces (backend) — 15 min

1. Entra a https://huggingface.co → crea cuenta.
2. Arriba a la derecha → **New → Space**.
3. Nombre: `jarvis-vortex`
4. SDK: **Docker**
5. Visibility: **Public** (o Private si prefieres)
6. Crea el Space.

7. Sube el código del backend:
   - Opción fácil: en el Space → **Files** → subir `Dockerfile`, `requirements.txt` y la carpeta `app/` y `static/`.
   - O con git (desde PC/Termux si tienes token):

```bash
git clone https://huggingface.co/spaces/TU_USUARIO/jarvis-vortex
cd jarvis-vortex
# copia aquí app/, static/, Dockerfile, requirements.txt
git add .
git commit -m "Jarvis backend"
git push
```

8. **Settings → Variables and secrets** → añade:

| Nombre | Valor |
|--------|--------|
| `GROQ_API_KEYS` | tus keys separadas por coma |
| `GROQ_MODEL` | `openai/gpt-oss-20b` |
| `DATABASE_URL` | la URL de Supabase (con `postgresql+asyncpg://`) |
| `SECRET_KEY` | cualquier cadena larga aleatoria |
| `FIREBASE_PROJECT_ID` | `jarvis-vortex-78100` |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |

9. El Space se reconstruye. La URL será:

```
https://TU_USUARIO-jarvis-vortex.hf.space
```

Prueba abriendo esa URL: debe cargar Jarvis o al menos responder.

---

### C) Firebase — dominios autorizados

1. https://console.firebase.google.com → proyecto `jarvis-vortex-78100`
2. **Authentication → Settings → Authorized domains**
3. Añade:
   - `localhost`
   - `TU_USUARIO.github.io`  (GitHub Pages)
   - `TU_USUARIO-jarvis-vortex.hf.space` (por si abres el backend directo)

---

### D) GitHub Pages (frontend) — 10 min

1. En https://github.com/RicardoT005/Jarvis-Vortex-Public (o repo nuevo):
   - Sube **solo** la carpeta `static/` como raíz del sitio, **o**
   - Sube todo el proyecto y en Pages apunta a `/static`.

Recomendado (repo solo frontend o carpeta docs):

```
# En el repo de GitHub Pages, en la raíz:
index.html          ← copia de static/index.html
config.js           ← copia de static/config.js
```

2. Edita `config.js`:

```js
window.JARVIS_API_URL = 'https://TU_USUARIO-jarvis-vortex.hf.space';
```

3. **Settings → Pages → Source: Deploy from branch → main / root**

4. URL final:

```
https://ricardot005.github.io/Jarvis-Vortex-Public/
```

---

### E) Probar con tu colaboradora

1. Abre la URL de GitHub Pages.
2. **Continuar con Google**.
3. El primer usuario queda como owner; los siguientes como collaborators.
4. La memoria se guarda en Supabase (no se pierde al reiniciar).

---

## Local (Termux / PC)

```bash
cd jarvis
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edita .env con tus keys
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abre http://localhost:8000

> Nota Termux: el paquete `cryptography` a veces falla con Python 3.14 en Android. El despliegue real es en Hugging Face (Linux), no depende de Termux.

---

## Memoria

| Capa | Contenido | Dónde |
|------|-----------|--------|
| Corto plazo | Mensajes recientes | Supabase / SQLite |
| Medio plazo | Resúmenes | Supabase / SQLite |
| Largo plazo | Hechos + identidad (MultSoftCreations, Ricardo Torres) | Inmutable en DB |

---

## Créditos

Creado por **Ricardo Torres** · **MultSoftCreations**
