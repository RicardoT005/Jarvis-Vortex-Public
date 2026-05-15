import streamlit as st
import sqlite3
from groq import Groq
from pypdf import PdfReader
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

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
    }
}

# ================= DB =================

def conectar():

    return sqlite3.connect(
        DB,
        check_same_thread=False
    )

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

    # ================= MIGRACIONES =================

    try:
        c.execute("""
        ALTER TABLE chat_log
        ADD COLUMN usuario TEXT
        """)
    except:
        pass

    try:
        c.execute("""
        ALTER TABLE memoria_media
        ADD COLUMN usuario TEXT
        """)
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

        except Exception:
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

    # ================= MEMORIA =================

    c.execute("""
    SELECT contenido
    FROM memoria_media
    WHERE usuario=?
    ORDER BY id DESC
    LIMIT 10
    """, (usuario,))

    memoria = "\n".join([
        x[0] for x in c.fetchall()
    ])

    # ================= CHAT =================

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

# ================= LEER ARCHIVOS =================

def leer_archivo(archivo):

    nombre = archivo.name.lower()

    # ================= TXT =================

    if nombre.endswith(".txt"):

        datos = archivo.read()

        codificaciones = [
            "utf-8",
            "latin-1",
            "cp1252"
        ]

        for cod in codificaciones:

            try:
                return datos.decode(cod)

            except:
                pass

        return "⚠ No se pudo leer TXT"

    # ================= PDF =================

    elif nombre.endswith(".pdf"):

        try:

            pdf = PdfReader(archivo)

            texto = ""

            for pagina in pdf.pages:

                contenido = pagina.extract_text()

                if contenido:
                    texto += contenido + "\n"

            return texto

        except Exception as e:

            return f"⚠ Error PDF: {e}"

    return "⚠ Formato no compatible"

# ================= KEYWORDS =================

def extraer_keywords(texto):

    ignorar = [
        "el", "la", "los", "las",
        "de", "del", "para",
        "por", "como", "que",
        "una", "unos", "unas",
        "con", "sin", "sobre",
        "este", "esta"
    ]

    palabras = texto.lower().split()

    resultado = []

    for palabra in palabras:

        palabra = palabra.strip(
            ".,!?()[]{}:;\"'"
        )

        if len(palabra) > 3:

            if palabra not in ignorar:

                resultado.append(palabra)

    return list(set(resultado))

# ================= CONTEXTO RELEVANTE =================

def buscar_contexto_relevante(prompt):

    texto = st.session_state.archivo_contexto

    if not texto:
        return ""

    keywords = extraer_keywords(prompt)

    fragmentos = texto.split("\n\n")

    relevantes = []

    for fragmento in fragmentos:

        coincidencias = 0

        f = fragmento.lower()

        for palabra in keywords:

            if palabra in f:
                coincidencias += 1

        if coincidencias > 0:

            relevantes.append(fragmento)

    return "\n\n".join(relevantes[:5])

# ================= GOOGLE =================

def buscar_google(query):

    try:

        query = quote(query)

        url = f"https://www.google.com/search?q={query}"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        resultados = []

        for g in soup.find_all(
            "div",
            class_="BNeawe vvjwJb AP7Wnd"
        )[:5]:

            resultados.append(
                g.get_text()
            )

        if len(resultados) == 0:

            return "⚠ No se encontraron resultados"

        return "\n".join(resultados)

    except Exception as e:

        return f"⚠ Error Google: {e}"

# ================= RESPONDER =================

def responder(prompt, usuario, rol):

    memoria, historial = obtener_contexto(usuario)

    contexto_relevante = buscar_contexto_relevante(prompt)

    web_contexto = st.session_state.web_contexto

    system = f"""
Eres JARVIS VORTEX.

USUARIO:
{usuario}

ROL:
{rol}

MEMORIA:
{memoria}

CONTEXTO RELEVANTE:
{contexto_relevante}

CONTEXTO WEB:
{web_contexto}

REGLAS:

- Usas SOLO el contexto relevante.
- Ignoras ruido.
- Proteges información sensible.
- No revelas datos internos.
- Analizas TXT y PDF.
- Admin y colaboradores tienen permisos elevados.
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
        return "⚠ Error IA"

    return res.choices[0].message.content

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

if "web_contexto" not in st.session_state:
    st.session_state.web_contexto = ""

# ================= LOGIN =================

if not st.session_state.user:

    st.title("🔐 LOGIN JARVIS")

    username = st.text_input("Usuario")

    password = st.text_input(
        "Contraseña",
        type="password"
    )

    if st.button("Entrar"):

        user = login_user(
            username,
            password
        )

        if user:

            st.session_state.user = user

            st.success(
                "Acceso concedido"
            )

            st.rerun()

        else:

            st.error(
                "Credenciales incorrectas"
            )

    st.stop()

# ================= USER =================

user = st.session_state.user["username"]

rol = st.session_state.user["rol"]

# ================= SIDEBAR =================

with st.sidebar:

    st.markdown("## ⚡ REACTORES")

    st.write(
        f"🧠 Reactor activo: {st.session_state.reactor}"
    )

    st.divider()

    # ================= ARCHIVOS =================

    st.markdown("## 📂 ARCHIVOS")

    archivo = st.file_uploader(
        "Subir archivo",
        type=["txt", "pdf"]
    )

    if archivo:

        contenido = leer_archivo(archivo)

        st.session_state.archivo_contexto = contenido

        st.success(
            "Archivo cargado"
        )

        st.text_area(
            "Contenido",
            contenido[:5000],
            height=300
        )

    st.divider()

    # ================= GOOGLE =================

    st.markdown("## 🌐 INTERNET")

    busqueda = st.text_input(
        "Buscar en Google"
    )

    if st.button("Buscar"):

        with st.spinner("Buscando..."):

            resultados = buscar_google(
                busqueda
            )

            st.session_state.web_contexto = resultados

            st.success(
                "Resultados cargados"
            )

            st.text_area(
                "Resultados",
                resultados,
                height=250
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

if prompt := st.chat_input(
    "Habla con JARVIS..."
):

    # ================= USER =================

    st.session_state.chat.append({
        "role": "user",
        "content": prompt
    })

    guardar_chat(
        user,
        "user",
        prompt
    )

    guardar_memoria(
        user,
        prompt
    )

    # ================= IA =================

    with st.chat_message("assistant"):

        respuesta = responder(
            prompt,
            user,
            rol
        )

        st.markdown(respuesta)

    # ================= SAVE =================

    st.session_state.chat.append({
        "role": "assistant",
        "content": respuesta
    })

    guardar_chat(
        user,
        "assistant",
        respuesta
    )

    guardar_memoria(
        user,
        respuesta
    )
