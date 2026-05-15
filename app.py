import streamlit as st
import sqlite3
import os
from groq import Groq

st.set_page_config(page_title="JARVIS VORTEX", layout="wide")

# ================= CONFIG =================

DB = "jarvis_memoria.db"

GROQ_KEYS = [
    st.secrets["GROQ_KEY_1"],
    st.secrets["GROQ_KEY_2"],
    st.secrets["GROQ_KEY_3"]
]

# ================= LOGIN LOCAL =================

USUARIOS = {
    "ricardo": {
        "password": "1234",
        "rol": "admin"
    },
    "colaborador": {
        "password": "1234",
        "rol": "colaborador"
    },
    "usuario": {
        "password": "1234",
        "rol": "usuario"
    }
}

# ================= DB =================

def conectar():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():

    conn = conectar()
    c = conn.cursor()

    # ================= CHAT LOG =================

    c.execute("""
    CREATE TABLE IF NOT EXISTS chat_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT DEFAULT 'ricardo',
        rol TEXT,
        mensaje TEXT
    )
    """)

    c.execute("PRAGMA table_info(chat_log)")
    columnas = [col[1] for col in c.fetchall()]

    if "usuario" not in columnas:
        c.execute("""
        ALTER TABLE chat_log
        ADD COLUMN usuario TEXT DEFAULT 'ricardo'
        """)

    # ================= MEMORIA MEDIA =================

    c.execute("""
    CREATE TABLE IF NOT EXISTS memoria_media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT DEFAULT 'ricardo',
        contenido TEXT
    )
    """)

    c.execute("PRAGMA table_info(memoria_media)")
    columnas_mem = [col[1] for col in c.fetchall()]

    if "usuario" not in columnas_mem:
        c.execute("""
        ALTER TABLE memoria_media
        ADD COLUMN usuario TEXT DEFAULT 'ricardo'
        """)

    conn.commit()
    conn.close()

# ================= IA =================

def ia(prompt):

    for key in GROQ_KEYS:

        try:

            client = Groq(api_key=key)

            respuesta = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=prompt
            )

            return respuesta

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

    # memoria media
    c.execute("""
    SELECT contenido FROM memoria_media
    WHERE usuario=?
    ORDER BY id DESC LIMIT 5
    """, (usuario,))

    media = "\n".join([x[0] for x in c.fetchall()])

    # historial
    c.execute("""
    SELECT rol, mensaje FROM chat_log
    WHERE usuario=?
    ORDER BY id DESC LIMIT 6
    """, (usuario,))

    filas = c.fetchall()

    conn.close()

    historial = []

    for rol, msg in reversed(filas):

        r = "assistant" if rol == "assistant" else "user"

        historial.append({
            "role": r,
            "content": msg
        })

    return media, historial

# ================= LEER ARCHIVOS =================

def leer_archivo(archivo):

    try:

        nombre = archivo.name.lower()

        extensiones_validas = [
            ".txt",
            ".md",
            ".py",
            ".json",
            ".html",
            ".css",
            ".js"
        ]

        valido = False

        for ext in extensiones_validas:

            if nombre.endswith(ext):
                valido = True
                break

        if not valido:
            return None

        contenido = archivo.read().decode("utf-8")

        return contenido

    except Exception as e:
        return f"Error leyendo archivo: {e}"

# ================= RESPUESTA =================

def responder(prompt, usuario, rol):

    media, historial = obtener_contexto(usuario)

    system = f"""
Eres JARVIS VORTEX.

USUARIO ACTUAL:
{usuario}

ROL:
{rol}

CONTEXTO RECIENTE:
{media}

REGLAS:

- Recuerdas datos importantes.
- Ignoras ruido innecesario.
- Mantienes contexto.
- Si el usuario NO es admin:
  NO reveles información sensible.
- Puedes analizar archivos de texto.
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

# ================= INICIAR DB =================

init_db()

# ================= SESSION =================

if "user" not in st.session_state:
    st.session_state.user = None

if "chat" not in st.session_state:
    st.session_state.chat = []

# ================= LOGIN =================

if not st.session_state.user:

    st.title("🔐 LOGIN JARVIS")

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Entrar"):

        username = username.strip().lower()

        if username in USUARIOS:

            if password == USUARIOS[username]["password"]:

                st.session_state.user = {
                    "username": username,
                    "rol": USUARIOS[username]["rol"]
                }

                st.success("Acceso concedido")
                st.rerun()

        st.error("Credenciales incorrectas")

    st.stop()

# ================= DATOS USER =================

user = st.session_state.user["username"]
rol = st.session_state.user["rol"]

# ================= UI =================

st.title("🔘 JARVIS VORTEX")
st.write(f"👤 {user} | 🛡 {rol}")

# ================= SUBIR ARCHIVOS =================

archivo = st.file_uploader(
    "📂 Subir archivo de texto",
    type=["txt", "md", "py", "json", "html", "css", "js"]
)

contenido_archivo = ""

if archivo:

    contenido_archivo = leer_archivo(archivo)

    if contenido_archivo:

        st.success("Archivo cargado correctamente")

        with st.expander("Ver contenido"):

            st.text(contenido_archivo[:5000])

# ================= MOSTRAR CHAT =================

for m in st.session_state.chat:

    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ================= INPUT =================

if prompt := st.chat_input("Habla con JARVIS..."):

    prompt_final = prompt

    if contenido_archivo:

        prompt_final += f"""

ARCHIVO CARGADO:
{contenido_archivo}
"""

    # guardar mensaje usuario
    st.session_state.chat.append({
        "role": "user",
        "content": prompt
    })

    guardar_chat(user, "user", prompt)
    guardar_memoria(user, prompt)

    # respuesta IA
    with st.chat_message("assistant"):

        respuesta = responder(prompt_final, user, rol)

        st.markdown(respuesta)

    # guardar respuesta
    st.session_state.chat.append({
        "role": "assistant",
        "content": respuesta
    })

    guardar_chat(user, "assistant", respuesta)
    guardar_memoria(user, respuesta)
