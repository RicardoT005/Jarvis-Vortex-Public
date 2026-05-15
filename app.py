import streamlit as st
import sqlite3
from groq import Groq

st.set_page_config(page_title="JARVIS VORTEX", layout="wide")

# =========================================================
# CONFIG
# =========================================================

DB = "jarvis_memoria.db"

GROQ_KEYS = {
    "REACTOR_1": st.secrets["GROQ_KEY_1"],
    "REACTOR_2": st.secrets["GROQ_KEY_2"],
    "REACTOR_3": st.secrets["GROQ_KEY_3"]
}

LIMITE_TOKENS = 6000

# =========================================================
# LOGIN LOCAL
# =========================================================

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

# =========================================================
# DB
# =========================================================

def conectar():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():

    conn = conectar()
    c = conn.cursor()

    # =====================================================
    # CHAT LOG
    # =====================================================

    c.execute("""
    CREATE TABLE IF NOT EXISTS chat_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT DEFAULT 'ricardo',
        rol TEXT,
        mensaje TEXT
    )
    """)

    # detectar columnas existentes
    c.execute("PRAGMA table_info(chat_log)")
    columnas = [col[1] for col in c.fetchall()]

    # agregar columna usuario si no existe
    if "usuario" not in columnas:

        c.execute("""
        ALTER TABLE chat_log
        ADD COLUMN usuario TEXT DEFAULT 'ricardo'
        """)

    # =====================================================
    # MEMORIA MEDIA
    # =====================================================

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

    # =====================================================
    # TOKENS
    # =====================================================

    c.execute("""
    CREATE TABLE IF NOT EXISTS tokens_uso (
        reactor TEXT PRIMARY KEY,
        usados INTEGER
    )
    """)

    for reactor in GROQ_KEYS.keys():

        c.execute("""
        INSERT OR IGNORE INTO tokens_uso
        (reactor, usados)
        VALUES (?, ?)
        """, (reactor, 0))

    conn.commit()
    conn.close()

# =========================================================
# TOKENS
# =========================================================

def obtener_tokens():

    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT reactor, usados FROM tokens_uso")

    datos = c.fetchall()

    conn.close()

    return {x[0]: x[1] for x in datos}

def actualizar_tokens(reactor, cantidad):

    conn = conectar()
    c = conn.cursor()

    c.execute("""
    UPDATE tokens_uso
    SET usados = usados + ?
    WHERE reactor = ?
    """, (cantidad, reactor))

    conn.commit()
    conn.close()

# =========================================================
# IA
# =========================================================

def ia(prompt):

    for reactor, key in GROQ_KEYS.items():

        try:

            client = Groq(api_key=key)

            respuesta = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=prompt
            )

            usados = respuesta.usage.total_tokens

            actualizar_tokens(reactor, usados)

            return respuesta, reactor, usados

        except:
            continue

    return None, None, 0

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

def obtener_contexto(usuario):

    conn = conectar()
    c = conn.cursor()

    # memoria media
    c.execute("""
    SELECT contenido
    FROM memoria_media
    WHERE usuario=?
    ORDER BY id DESC
    LIMIT 5
    """, (usuario,))

    media = "\n".join([x[0] for x in c.fetchall()])

    # historial reciente
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

        r = "assistant" if rol == "assistant" else "user"

        historial.append({
            "role": r,
            "content": msg
        })

    return media, historial

# =========================================================
# LEER ARCHIVOS
# =========================================================

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

# =========================================================
# RESPONDER
# =========================================================

def responder(prompt, usuario, rol):

    media, historial = obtener_contexto(usuario)

    system = f"""
Eres JARVIS VORTEX.

USUARIO:
{usuario}

ROL:
{rol}

CONTEXTO:
{media}

REGLAS:
- Recuerda información importante.
- Ignora ruido innecesario.
- Mantén contexto.
- No reveles información sensible a usuarios no admin.
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

    res, reactor, usados = ia(mensajes)

    if not res:
        return "⚠️ Error con IA", reactor, usados

    return res.choices[0].message.content, reactor, usados

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

# =========================================================
# LOGIN
# =========================================================

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

# =========================================================
# USER
# =========================================================

user = st.session_state.user["username"]
rol = st.session_state.user["rol"]

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.title("⚡ REACTORES")

    tokens = obtener_tokens()

    for reactor, usados in tokens.items():

        restante = LIMITE_TOKENS - usados

        porcentaje = usados / LIMITE_TOKENS

        st.subheader(reactor)

        st.progress(min(porcentaje, 1.0))

        st.write(f"🔥 Usados: {usados}")
        st.write(f"⚡ Restantes: {restante}")

    st.divider()

    st.subheader("📂 ANALIZAR ARCHIVO")

    archivo = st.file_uploader(
        "Subir archivo",
        type=["txt", "md", "py", "json", "html", "css", "js"]
    )

# =========================================================
# MAIN
# =========================================================

st.title("🔘 JARVIS VORTEX")
st.write(f"👤 {user} | 🛡 {rol}")

# =========================================================
# ARCHIVO
# =========================================================

contenido_archivo = ""

if archivo:

    contenido_archivo = leer_archivo(archivo)

    if contenido_archivo:

        st.success("Archivo cargado")

        with st.expander("Contenido"):

            st.text(contenido_archivo[:5000])

# =========================================================
# MOSTRAR CHAT
# =========================================================

for m in st.session_state.chat:

    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# =========================================================
# INPUT
# =========================================================

if prompt := st.chat_input("Habla con JARVIS..."):

    prompt_final = prompt

    if contenido_archivo:

        prompt_final += f"""

ARCHIVO:
{contenido_archivo}
"""

    # guardar user
    st.session_state.chat.append({
        "role": "user",
        "content": prompt
    })

    guardar_chat(user, "user", prompt)
    guardar_memoria(user, prompt)

    # responder
    with st.chat_message("assistant"):

        with st.spinner("Procesando..."):

            respuesta, reactor, usados = responder(
                prompt_final,
                user,
                rol
            )

        st.markdown(respuesta)

        st.caption(f"⚡ {reactor} | Tokens usados: {usados}")

    # guardar respuesta
    st.session_state.chat.append({
        "role": "assistant",
        "content": respuesta
    })

    guardar_chat(user, "assistant", respuesta)
    guardar_memoria(user, respuesta)
