import streamlit as st
import sqlite3
from groq import Groq
import os
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

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
        except Exception as e:
            continue
    return None

# ================= MEMORIA =================

def clasificar(texto):
    res = ia([
        {"role": "system", "content": "Clasifica: IGNORAR / MEDIA / LARGA"},
        {"role": "user", "content": texto}
    ])
    return res.choices[0].message.content.strip() if res else "IGNORAR"

def estructurar(texto):
    res = ia([
        {"role": "system", "content": "Extrae clave:valor (ej: nombre: Ricardo)"},
        {"role": "user", "content": texto}
    ])
    return res.choices[0].message.content if res else ""

def guardar_memoria(texto):
    tipo = clasificar(texto)

    conn = conectar()
    c = conn.cursor()

    if "MEDIA" in tipo:
        c.execute("INSERT INTO memoria_media (contenido) VALUES (?)", (texto,))

    elif "LARGA" in tipo:
        try:
            kv = estructurar(texto)
            clave, valor = kv.split(":")
            c.execute("INSERT OR REPLACE INTO memoria_larga VALUES (?, ?)", (clave.strip(), valor.strip()))
        except:
            pass

    conn.commit()
    conn.close()

# ================= CONTEXTO =================

def obtener_contexto(usuario):
    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT clave, valor FROM memoria_larga")
    larga = "\n".join([f"{k}: {v}" for k,v in c.fetchall()])

    c.execute("SELECT contenido FROM memoria_media ORDER BY id DESC LIMIT 5")
    media = "\n".join([x[0] for x in c.fetchall()])

    c.execute("SELECT rol, mensaje FROM chat_log WHERE usuario=? ORDER BY id DESC LIMIT 6", (usuario,))
    filas = c.fetchall()

    conn.close()

    historial = []
    for rol, msg in reversed(filas):
        historial.append({"role": rol, "content": msg})

    return larga, media, historial

# ================= RESPUESTA =================

def responder(prompt, usuario, rol):
    larga, media, historial = obtener_contexto(usuario)

    system = f"""
IDENTIDAD:
{larga}

USUARIO ACTUAL:
Nombre: {usuario}
Rol: {rol}

CONTEXTO:
{media}

REGLAS:
- Protege información sensible
- No reveles datos de otros usuarios
- Ajusta respuestas según rol

Eres JARVIS.
"""

    mensajes = [{"role": "system", "content": system}]
    mensajes.extend(historial)
    mensajes.append({"role": "user", "content": prompt})

    res = ia(mensajes)

    if not res:
        return "⚠️ Error: No hay conexión con IA"

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
