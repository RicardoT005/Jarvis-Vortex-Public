import streamlit as st
import sqlite3
from groq import Groq
from pypdf import PdfReader

# ================= CONFIG =================

st.set_page_config(
    page_title="JARVIS VORTEX",
    layout="wide"
)

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

    "colab1": {
        "password": "1234",
        "rol": "colaborador"
    },

    "user1": {
        "password": "1234",
        "rol": "usuario"
    },

    "iker": {
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

    # ================= CHAT =================

    c.execute("""
    CREATE TABLE IF NOT EXISTS chat_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        rol TEXT,
        mensaje TEXT
    )
    """)

    # ================= MEMORIA =================

    c.execute("""
    CREATE TABLE IF NOT EXISTS memoria_media (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        contenido TEXT
    )
    """)

    conn.commit()

    # ================= MIGRACIONES =================

    try:
        c.execute("ALTER TABLE chat_log ADD COLUMN usuario TEXT")
    except:
        pass

    try:
        c.execute("ALTER TABLE memoria_media ADD COLUMN usuario TEXT")
    except:
        pass

    conn.commit()
    conn.close()

# ================= LOGIN =================

def login_user(username, password):

    username = username.strip().lower()

    if username in USUARIOS:

        if USUARIOS[username]["password"] == password:

            return {
                "username": username,
                "rol": USUARIOS[username]["rol"]
            }

    return None

# ================= IA =================

def ia(prompt):

    for i, key in enumerate(GROQ_KEYS):

        try:

            st.session_state.reactor = f"REACTOR {i+1}"

            client = Groq(api_key=key)

            respuesta = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=prompt
            )

            return respuesta

        except:
            continue

    st.session_state.reactor = "NINGUNO"

    return None

# ================= MEMORIA =================

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

# ================= CHAT =================

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

# ================= CONTEXTO =================

def obtener_contexto(usuario):

    conn = conectar()
    c = conn.cursor()

    # ===== MEMORIA =====

    c.execute("""
    SELECT contenido
    FROM memoria_media
    WHERE usuario=?
    ORDER BY id DESC
    LIMIT 10
    """, (usuario,))

    memoria = "\n".join([x[0] for x in c.fetchall()])

    # ===== CHAT =====

    c.execute("""
    SELECT rol, mensaje
    FROM chat_log
    WHERE usuario=?
    ORDER BY id DESC
    LIMIT 10
    """, (usuario,))

    filas = c.fetchall()

    conn.close()

    historial = []

    for rol, msg in reversed(filas):

        historial.append({
            "role": rol,
            "content": msg
        })

    return memoria, historial

# ================= RESPONDER =================

def responder(prompt, usuario, rol):

    memoria, historial = obtener_contexto(usuario)

    archivo_contexto = st.session_state.archivo_contexto

    system = f"""
Eres JARVIS VORTEX.

USUARIO ACTUAL:
{usuario}

ROL:
{rol}

MEMORIA:
{memoria}

ARCHIVO CARGADO:
{archivo_contexto}

REGLAS:

- Recuerdas información importante.
- Ignoras ruido.
- Proteges información sensible.
- No revelas datos internos a usuarios normales.
- Admin y colaboradores tienen permisos elevados.
- Puedes analizar archivos TXT y PDF.
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
        return "⚠ Error con IA"

    return res.choices[0].message.content

# ================= LEER ARCHIVOS =================

def leer_archivo(archivo):

    nombre = archivo.name.lower()

    # ================= TXT =================

    if nombre.endswith(".txt"):

        codificaciones = [
            "utf-8",
            "latin-1",
            "cp1252"
        ]

        datos = archivo.read()

        for cod in codificaciones:

            try:

                contenido = datos.decode(cod)

                return contenido

            except:
                pass

        return "⚠ No se pudo leer el TXT"

    # ================= PDF =================

    elif nombre.endswith(".pdf"):

        try:

            pdf = PdfReader(archivo)

            texto = ""

            for pagina in pdf.pages:

                contenido = pagina.extract_text()

                if contenido:
                    texto += contenido + "\n"

            if texto.strip() == "":
                return "⚠ El PDF no contiene texto seleccionable"

            return texto

        except Exception as e:

            return f"⚠ Error leyendo PDF: {e}"

    return "⚠ Formato no compatible"

# ================= INICIO =================

init_db()

# ================= SESSION =================

if "user" not in st.session_state:
    st.session_state.user = None

if "chat" not in st.session_state:
    st.session_state.chat = []

if "reactor" not in st.session_state:
    st.session_state.reactor = "NINGUNO"

if "archivo_contexto" not in st.session_state:
    st.session_state.archivo_contexto = ""

# ================= LOGIN UI =================

if not st.session_state.user:

    st.title("🔐 LOGIN JARVIS")

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

# ================= DATOS USER =================

user = st.session_state.user["username"]
rol = st.session_state.user["rol"]

# ================= SIDEBAR =================

with st.sidebar:

    st.markdown("## ⚡ REACTORES")

    st.write(f"🧠 Reactor activo: {st.session_state.reactor}")

    st.divider()

    st.markdown("## 📂 ARCHIVOS")

    archivo = st.file_uploader(
        "Subir archivo",
        type=["txt", "pdf"]
    )

    if archivo:

        contenido = leer_archivo(archivo)

        st.session_state.archivo_contexto = contenido

        st.success("Archivo cargado al contexto de JARVIS")

        st.text_area(
            "Contenido",
            contenido,
            height=300
        )

    st.divider()

    st.write(f"👤 Usuario: {user}")
    st.write(f"🛡 Rol: {rol}")

# ================= PANEL =================

st.title("⚙ JARVIS VORTEX")

for m in st.session_state.chat:

    with st.chat_message(m["role"]):

        st.markdown(m["content"])

# ================= CHAT =================

if prompt := st.chat_input("Habla con JARVIS..."):

    # ===== USER =====

    st.session_state.chat.append({
        "role": "user",
        "content": prompt
    })

    guardar_chat(user, "user", prompt)

    guardar_memoria(user, prompt)

    # ===== IA =====

    with st.chat_message("assistant"):

        respuesta = responder(prompt, user, rol)

        st.markdown(respuesta)

    # ===== SAVE =====

    st.session_state.chat.append({
        "role": "assistant",
        "content": respuesta
    })

    guardar_chat(user, "assistant", respuesta)

    guardar_memoria(user, respuesta)
