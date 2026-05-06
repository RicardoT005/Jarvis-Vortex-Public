import streamlit as st
import sqlite3
import time
from groq import Groq
from supabase import create_client

st.set_page_config(page_title="JARVIS VORTEX", layout="wide")

# ================= CONFIG =================

DB = "jarvis_memoria.db"

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

GROQ_KEYS = [
    st.secrets["GROQ_KEY_1"],
    st.secrets["GROQ_KEY_2"],
    st.secrets["GROQ_KEY_3"]
]

# ================= DIAGNÓSTICO =================

st.title("🔧 Inicializando sistema...")

status_ok = True

# --- SUPABASE TEST ---
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    test = supabase.table("usuarios").select("*").limit(1).execute()
    st.success("🟢 Supabase conectado")
except Exception as e:
    st.error(f"🔴 Supabase ERROR: {e}")
    status_ok = False

# --- GROQ TEST ---
groq_ok = False

for key in GROQ_KEYS:
    try:
        client = Groq(api_key=key)
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "ping"}]
        )
        st.success("🟢 Groq conectado")
        groq_ok = True
        break
    except:
        continue

if not groq_ok:
    st.error("🔴 Groq ERROR: ninguna API funciona")
    status_ok = False

# --- RESULTADO FINAL ---
if not status_ok:
    st.error("❌ Sistema no inicializado. Corrige errores arriba.")
    st.stop()

st.success("✅ Todo correcto. Iniciando JARVIS...")
time.sleep(2)

# ================= DB =================

def conectar():
    return sqlite3.connect(DB)

def init_db():
    conn = conectar()
    c = conn.cursor()

    c.execute("CREATE TABLE IF NOT EXISTS chat_log (id INTEGER PRIMARY KEY, usuario TEXT, rol TEXT, mensaje TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS memoria_media (id INTEGER PRIMARY KEY, contenido TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS memoria_larga (clave TEXT PRIMARY KEY, valor TEXT)")

    conn.commit()
    conn.close()

# ================= LOGIN =================

def login_user(username, password):
    res = supabase.table("usuarios") \
        .select("*") \
        .eq("username", username) \
        .eq("password", password) \
        .execute()

    return res.data[0] if res.data else None

# ================= IA =================

def ia(prompt):
    for key in GROQ_KEYS:
        try:
            client = Groq(api_key=key)
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=prompt
            )
            return res
        except:
            continue
    return None

# ================= MEMORIA =================

def guardar_memoria(texto):
    conn = conectar()
    c = conn.cursor()
    c.execute("INSERT INTO memoria_media (contenido) VALUES (?)", (texto,))
    conn.commit()
    conn.close()

def obtener_contexto(usuario):
    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT contenido FROM memoria_media ORDER BY id DESC LIMIT 5")
    media = "\n".join([x[0] for x in c.fetchall()])

    c.execute("SELECT rol, mensaje FROM chat_log WHERE usuario=? ORDER BY id DESC LIMIT 6", (usuario,))
    filas = c.fetchall()

    conn.close()

    historial = []
    for rol, msg in reversed(filas):
        historial.append({"role": rol, "content": msg})

    return media, historial

# ================= RESPUESTA =================

def responder(prompt, usuario, rol):
    media, historial = obtener_contexto(usuario)

    system = f"""
USUARIO: {usuario}
ROL: {rol}

CONTEXTO:
{media}

Eres JARVIS.
"""

    mensajes = [{"role": "system", "content": system}]
    mensajes.extend(historial)
    mensajes.append({"role": "user", "content": prompt})

    res = ia(mensajes)

    if not res:
        return "⚠️ Error IA"

    return res.choices[0].message.content

# ================= CHAT =================

def guardar_chat(usuario, rol, texto):
    conn = conectar()
    c = conn.cursor()
    c.execute("INSERT INTO chat_log (usuario, rol, mensaje) VALUES (?, ?, ?)", (usuario, rol, texto))
    conn.commit()
    conn.close()

# ================= UI =================

init_db()

if "user" not in st.session_state:
    st.session_state.user = None

# LOGIN
if not st.session_state.user:

    st.title("🔐 Login JARVIS")

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Entrar"):
        user = login_user(username, password)

        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

    st.stop()

# PANEL

user = st.session_state.user["username"]
rol = st.session_state.user["rol"]

st.title("🔘 JARVIS VORTEX")
st.write(f"👤 {user} | 🛡 {rol}")

if "chat" not in st.session_state:
    st.session_state.chat = []

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Habla con JARVIS..."):

    st.session_state.chat.append({"role": "user", "content": prompt})
    guardar_chat(user, "user", prompt)
    guardar_memoria(prompt)

    with st.chat_message("assistant"):
        respuesta = responder(prompt, user, rol)
        st.markdown(respuesta)

    st.session_state.chat.append({"role": "assistant", "content": respuesta})
    guardar_chat(user, "assistant", respuesta)
    guardar_memoria(respuesta)
