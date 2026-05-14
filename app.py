import streamlit as st
import sqlite3
from groq import Groq

st.set_page_config(page_title="JARVIS VORTEX", layout="wide")

# ================= CONFIG =================

DB = "jarvis_memoria.db"

GROQ_KEYS = [
    st.secrets["GROQ_KEY_1"],
    st.secrets["GROQ_KEY_2"],
    st.secrets["GROQ_KEY_3"]
]

# ================= USUARIOS LOCALES =================

USUARIOS = {
    "ricardo": {
        "password": "1234",
        "rol": "admin"
    },

    "tester": {
        "password": "1234",
        "rol": "user"
    }
}

# ================= DB =================

def conectar():
    return sqlite3.connect(DB)

def init_db():
    conn = conectar()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS chat_log (
        id INTEGER PRIMARY KEY,
        usuario TEXT,
        rol TEXT,
        mensaje TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS memoria_media (
        id INTEGER PRIMARY KEY,
        usuario TEXT,
        contenido TEXT
    )
    """)

    conn.commit()
    conn.close()

# ================= LOGIN LOCAL =================

def login_user(username, password):

    username = username.strip().lower()
    password = password.strip()

    if username in USUARIOS:

        user_data = USUARIOS[username]

        if user_data["password"] == password:

            return {
                "username": username,
                "rol": user_data["rol"]
            }

    return None

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

def guardar_memoria(usuario, texto):

    conn = conectar()
    c = conn.cursor()

    c.execute(
        "INSERT INTO memoria_media (usuario, contenido) VALUES (?, ?)",
        (usuario, texto)
    )

    conn.commit()
    conn.close()

def obtener_contexto(usuario):

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    SELECT contenido FROM memoria_media
    WHERE usuario=?
    ORDER BY id DESC LIMIT 5
    """, (usuario,))

    media = "\n".join([x[0] for x in c.fetchall()])

    c.execute("""
    SELECT rol, mensaje FROM chat_log
    WHERE usuario=?
    ORDER BY id DESC LIMIT 6
    """, (usuario,))

    filas = c.fetchall()

    conn.close()

    historial = []

    for rol, msg in reversed(filas):

        historial.append({
            "role": rol,
            "content": msg
        })

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

Recuerdas lo importante.
Ignoras ruido.
No reveles información sensible a usuarios no admin.
"""

    mensajes = [{
        "role": "system",
        "content": system
    }]

    mensajes.extend(historial)

    mensajes.append({
        "role": "user",
        "content": prompt
    })

    res = ia(mensajes)

    if not res:
        return "⚠️ Error con IA"

    return res.choices[0].message.content

# ================= CHAT =================

def guardar_chat(usuario, rol, texto):

    conn = conectar()
    c = conn.cursor()

    c.execute(
        "INSERT INTO chat_log (usuario, rol, mensaje) VALUES (?, ?, ?)",
        (usuario, rol, texto)
    )

    conn.commit()
    conn.close()

# ================= UI =================

init_db()

if "user" not in st.session_state:
    st.session_state.user = None

if "chat" not in st.session_state:
    st.session_state.chat = []

# ================= LOGIN UI =================

if not st.session_state.user:

    st.title("🔐 Login JARVIS")

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Entrar"):

        user = login_user(username, password)

        if user:

            st.session_state.user = user

            st.success("Acceso concedido")

            st.rerun()

        else:

            st.error("Credenciales incorrectas")

    st.stop()

# ================= PANEL =================

user = st.session_state.user["username"]
rol = st.session_state.user["rol"]

st.title("🔘 JARVIS VORTEX")
st.write(f"👤 {user} | 🛡 {rol}")

# ================= CHAT =================

for m in st.session_state.chat:

    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ================= INPUT =================

if prompt := st.chat_input("Habla con JARVIS..."):

    st.session_state.chat.append({
        "role": "user",
        "content": prompt
    })

    guardar_chat(user, "user", prompt)

    guardar_memoria(user, prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):

        respuesta = responder(prompt, user, rol)

        st.markdown(respuesta)

    st.session_state.chat.append({
        "role": "assistant",
        "content": respuesta
    })

    guardar_chat(user, "assistant", respuesta)

    guardar_memoria(user, respuesta)
