# Guía rápida de despliegue – Jarvis Vortex

## Orden recomendado

1. **Supabase** → base de datos  
2. **Hugging Face Space** → backend  
3. **Firebase** → autorizar dominios  
4. **GitHub Pages** → frontend  

---

## 1. Supabase

1. https://supabase.com → New project  
2. Settings → Database → Connection string (URI)  
3. Cambia el inicio a: `postgresql+asyncpg://...`  
4. Guarda esa URL como `DATABASE_URL`

---

## 2. Hugging Face Spaces

1. https://huggingface.co → New Space → SDK **Docker** → nombre `jarvis-vortex`  
2. Sube: `Dockerfile`, `requirements.txt`, carpetas `app/` y `static/`  
3. Settings → Secrets:

```
GROQ_API_KEYS=...
GROQ_MODEL=openai/gpt-oss-20b
DATABASE_URL=postgresql+asyncpg://...
SECRET_KEY=...
FIREBASE_PROJECT_ID=jarvis-vortex-78100
ENVIRONMENT=production
DEBUG=false
```

4. URL del backend: `https://TU_USUARIO-jarvis-vortex.hf.space`

---

## 3. Firebase

Authentication → Settings → Authorized domains:

- `localhost`
- `tuusuario.github.io`
- dominio del Space de HF (opcional)

---

## 4. GitHub Pages

1. Repo (ej. Jarvis-Vortex-Public)  
2. En la raíz (o en `/docs`): `index.html` + `config.js`  
3. En `config.js`:

```js
window.JARVIS_API_URL = 'https://TU_USUARIO-jarvis-vortex.hf.space';
```

4. Settings → Pages → branch main  

URL: `https://ricardot005.github.io/NOMBRE_REPO/`

---

## Por qué este stack

| Opción | Veredicto |
|--------|-----------|
| Solo Netlify | No sirve bien para FastAPI continuo |
| Solo Firebase/Firestore | Obligaría a reescribir toda la memoria SQL |
| Termux 24/7 | No fiable para compartir con colaboradora |
| **HF + Supabase + GH Pages + Firebase** | Gratis, estable, multi-usuario |

La memoria vive en **Supabase**: no se borra, crece y sirve para varios usuarios.
