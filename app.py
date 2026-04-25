import streamlit as st
import sqlite3
from groq import Groq
import os

st.set_page_config(page_title="JARVIS VORTEX", layout="wide")

DB = "jarvis_memoria.db"

# ================= DB =================

def conectar():
    return sqlite3.connect(DB)

def init_db():
    conn = conectar()
    c = conn.cursor()

    c.execute("CREATE TABLE IF NOT EXISTS chat_log (id INTEGER PRIMARY KEY, rol TEXT, mensaje TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS memoria_media (id INTEGER PRIMARY KEY, contenido TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS memoria_larga (clave TEXT PRIMARY KEY, valor TEXT)")

    conn.commit()
    conn.close()

# ================= IA =================

def ia(prompt):
    client = Groq(api_key=st.secrets["GROQ_KEY_1"])
    return client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=prompt
    )

# ================= MEMORIA =================

def clasificar(texto):
    res = ia([
        {"role": "system", "content": "Clasifica: IGNORAR / MEDIA / LARGA"},
        {"role": "user", "content": texto}
    ])
    return res.choices[0].message.content.strip()

def estructurar(texto):
    res = ia([
        {"role": "system", "content": "Extrae clave:valor (ej: nombre: Ricardo)"},
        {"role": "user", "content": texto}
    ])
    return res.choices[0].message.content

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

# ================= LIMPIEZA =================

def limpiar_memoria():
    conn = conectar()
    c = conn.cursor()

    # Limitar memoria media
    c.execute("DELETE FROM memoria_media WHERE id NOT IN (SELECT id FROM memoria_media ORDER BY id DESC LIMIT 20)")

    conn.commit()
    conn.close()

# ================= CONTEXTO =================

def obtener_contexto():
    conn = conectar()
    c = conn.cursor()

    # Largo
    c.execute("SELECT clave, valor FROM memoria_larga")
    larga = "\n".join([f"{k}: {v}" for k,v in c.fetchall()])

    # Medio
    c.execute("SELECT contenido FROM memoria_media ORDER BY id DESC LIMIT 5")
    media = "\n".join([x[0] for x in c.fetchall()])

    # Corto
    c.execute("SELECT rol, mensaje FROM chat_log ORDER BY id DESC LIMIT 6")
    filas = c.fetchall()

    conn.close()

    historial = []
    for rol, msg in reversed(filas):
        r = "assistant" if rol == "model" else rol
        historial.append({"role": r, "content": msg})

    return larga, media, historial

# ================= RESPUESTA =================

def responder(prompt):
    larga, media, historial = obtener_contexto()

    system = f"""
IDENTIDAD:
{larga}

CONTEXTO:
{media}

Eres JARVIS.
Recuerdas datos importantes.
Ignoras ruido.
No repites información innecesaria.
"""

    mensajes = [{"role": "system", "content": system}]
    mensajes.extend(historial)
    mensajes.append({"role": "user", "content": prompt})

    res = ia(mensajes)
    return res.choices[0].message.content

# ================= CHAT =================

def guardar_chat(rol, texto):
    conn = conectar()
    c = conn.cursor()
    c.execute("INSERT INTO chat_log (rol, mensaje) VALUES (?, ?)", (rol, texto))
    conn.commit()
    conn.close()

# ================= UI =================

st.title("🔘 JARVIS VORTEX")

init_db()

if "chat" not in st.session_state:
    st.session_state.chat = []

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Habla con JARVIS..."):

    # usuario
    st.session_state.chat.append({"role": "user", "content": prompt})
    guardar_chat("user", prompt)
    guardar_memoria(prompt)

    with st.chat_message("assistant"):

        respuesta = responder(prompt)
        st.markdown(respuesta)

    st.session_state.chat.append({"role": "assistant", "content": respuesta})
    guardar_chat("assistant", respuesta)
    guardar_memoria(respuesta)

    limpiar_memoria()
