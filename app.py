import streamlit as st
import sqlite3
from groq import Groq
import os

# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="JARVIS VORTEX",
    layout="wide"
)

DB = "jarvis_memoria.db"

GROQ_KEYS = [
    os.getenv("GROQ_KEY_1", st.secrets["GROQ_KEY_1"]),
    os.getenv("GROQ_KEY_2", st.secrets["GROQ_KEY_2"]),
    os.getenv("GROQ_KEY_3", st.secrets["GROQ_KEY_3"])
]

# =========================================================
# LOGIN LOCAL TEMPORAL
# =========================================================

USUARIOS = {
    "ricardo": {
        "password": "admin123",
        "rol": "admin"
    },

    "colab1": {
        "password": "colab123",
        "rol": "colaborador"
    },

    "user1": {
        "password": "user123",
        "rol": "usuario"
    }
}

# =========================================================
# DB
# =========================================================

def conectar():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():

    conn = conectar()
    c = conn.cursor()

    # =====================================================
    # CHAT
    # =====================================================

    c.execute("""
    CREATE TABLE IF NOT EXISTS chat_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        rol TEXT,
        mensaje TEXT
    )
    """)

    # =====================================================
    # MEMORIA
    # =====================================================

    c.execute("""
    CREATE TABLE IF NOT EXISTS memoria_media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        contenido TEXT
    )
    """)

    conn.commit()
    conn.close()

# =========================================================
# LOGIN
# =========================================================

def login_local(username, password):

    username = username.lower().strip()
    password = password.strip()

    if username not in USUARIOS:
        return None

    user = USUARIOS[username]

    if user["password"] == password:
        return {
            "username": username,
            "rol": user["rol"]
        }

    return None

# =========================================================
# VERIFICACIÓN REACTORES
# =========================================================

def verificar_reactor(key):

    try:

        client = Groq(api_key=key)

        client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": "ping"
                }
            ],
            max_tokens=5
        )

        return True

    except:
        return False

# =========================================================
# VERIFICAR SISTEMA
# =========================================================

def verificar_sistema():

    estados = {}

    # REACTORES
    for i, key in enumerate(GROQ_KEYS):

        nombre = f"REACTOR {i+1}"

        ok = verificar_reactor(key)

        estados[nombre] = ok

    # DB
    try:

        conn = conectar()
        conn.cursor().execute("SELECT 1")
        conn.close()

        estados["MEMORIA"] = True

    except:
        estados["MEMORIA"] = False

    return estados

# =========================================================
# IA
# =========================================================

def ia(prompt):

    for i, key in enumerate(GROQ_KEYS):

        try:

            client = Groq(api_key=key)

            respuesta = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=prompt
            )

            st.session_state.reactor_actual = f"REACTOR {i+1}"

            return respuesta

        except:
            continue

    return None

# =========================================================
# MEMORIA
# =========================================================

def guardar_memoria(usuario, texto):

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    INSERT INTO memoria_media
    (usuario, contenido)
    VALUES (?, ?)
    """, (usuario, texto))

    conn.commit()
    conn.close()

# =========================================================
# CONTEXTO
# =========================================================

def obtener_contexto(usuario):

    conn = conectar()
    c = conn.cursor()

    # MEMORIA MEDIA
    c.execute("""
    SELECT contenido
    FROM memoria_media
    WHERE usuario=?
    ORDER BY id DESC
    LIMIT 5
    """, (usuario,))

    media = "\n".join([
        x[0] for x in c.fetchall()
    ])

    # CHAT
    c.execute("""
    SELECT rol, mensaje
    FROM chat_log
    WHERE usuario=?
    ORDER BY id DESC
    LIMIT 6
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

# =========================================================
# RESPUESTA
# =========================================================

def responder(prompt, usuario, rol):

    media, historial = obtener_contexto(usuario)

    system = f"""
USUARIO ACTUAL: {usuario}
ROL: {rol}

CONTEXTO:
{media}

Eres JARVIS.

REGLAS:
- Recuerdas información importante.
- Ignoras ruido.
- No reveles datos internos a usuarios normales.
- Solo admins pueden ver información técnica.
- Sé preciso.
"""

    mensajes = [
        {
            "role": "system",
            "content": system
        }
    ]

    mensajes.extend(historial)

    mensajes.append({
        "role": "user",
        "content": prompt
    })

    res = ia(mensajes)

    if not res:
        return "⚠️ Todos los reactores están offline."

    return res.choices[0].message.content

# =========================================================
# CHAT
# =========================================================

def guardar_chat(usuario, rol, texto):

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    INSERT INTO chat_log
    (usuario, rol, mensaje)
    VALUES (?, ?, ?)
    """, (usuario, rol, texto))

    conn.commit()
    conn.close()

# =========================================================
# ARCHIVOS
# =========================================================

def procesar_archivo(file):

    try:

        contenido = file.read().decode("utf-8")

        return contenido

    except:

        return None

# =========================================================
# INIT
# =========================================================

init_db()

# =========================================================
# SESSION
# =========================================================

if "user" not in st.session_state:
    st.session_state.user = None

if "chat" not in st.session_state:
    st.session_state.chat = []

if "reactor_actual" not in st.session_state:
    st.session_state.reactor_actual = "NINGUNO"

# =========================================================
# LOGIN UI
# =========================================================

if not st.session_state.user:

    st.title("🔐 LOGIN JARVIS")

    username = st.text_input("Usuario")

    password = st.text_input(
        "Contraseña",
        type="password"
    )

    if st.button("Entrar"):

        user = login_local(username, password)

        if user:

            st.session_state.user = user

            st.success("Acceso concedido")

            st.rerun()

        else:

            st.error("Credenciales incorrectas")

    st.stop()

# =========================================================
# USUARIO
# =========================================================

user = st.session_state.user["username"]
rol = st.session_state.user["rol"]

# =========================================================
# VERIFICACIÓN SISTEMA
# SOLO ADMIN/COLAB
# =========================================================

if rol in ["admin", "colaborador"]:

    if "verificacion_hecha" not in st.session_state:

        st.title("⚙️ VERIFICANDO SISTEMA")

        estados = verificar_sistema()

        todo_ok = True

        for nombre, estado in estados.items():

            if estado:
                st.success(f"{nombre}: ONLINE")
            else:
                st.error(f"{nombre}: OFFLINE")
                todo_ok = False

        if todo_ok:
            st.success("✅ Sistema listo")
        else:
            st.warning("⚠️ Algunos módulos fallaron")

        if st.button("Continuar"):

            st.session_state.verificacion_hecha = True

            st.rerun()

        st.stop()

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header("⚡ REACTORES")

    st.write(
        f"🧠 Reactor activo: "
        f"{st.session_state.reactor_actual}"
    )

    st.divider()

    st.header("📂 ARCHIVOS")

    archivo = st.file_uploader(
        "Subir TXT",
        type=["txt"]
    )

    st.divider()

    st.write(f"👤 Usuario: {user}")
    st.write(f"🛡 Rol: {rol}")

# =========================================================
# CHAT UI
# =========================================================

st.title("🔘 JARVIS VORTEX")

for m in st.session_state.chat:

    with st.chat_message(m["role"]):

        st.markdown(m["content"])

# =========================================================
# INPUT
# =========================================================

if prompt := st.chat_input("Habla con JARVIS..."):

    # =====================================================
    # ARCHIVO
    # =====================================================

    if archivo:

        contenido = procesar_archivo(archivo)

        if contenido:

            prompt = f"""
ARCHIVO CARGADO:

{contenido}

INSTRUCCIÓN DEL USUARIO:
{prompt}
"""

    # =====================================================
    # USER MSG
    # =====================================================

    st.session_state.chat.append({
        "role": "user",
        "content": prompt
    })

    guardar_chat(user, "user", prompt)

    guardar_memoria(user, prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    # =====================================================
    # IA
    # =====================================================

    with st.chat_message("assistant"):

        with st.spinner("JARVIS pensando..."):

            respuesta = responder(
                prompt,
                user,
                rol
            )

            st.markdown(respuesta)

    # =====================================================
    # SAVE
    # =====================================================

    st.session_state.chat.append({
        "role": "assistant",
        "content": respuesta
    })

    guardar_chat(user, "assistant", respuesta)

    guardar_memoria(user, respuesta)
