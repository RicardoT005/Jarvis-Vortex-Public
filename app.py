import streamlit as st
import sqlite3
import os
from groq import Groq

st.set_page_config(page_title="JARVIS OS", layout="wide")

DB_NAME = "jarvis_memoria.db"

# --- DB ---
def conectar():
    return sqlite3.connect(DB_NAME)

def guardar_mensaje(rol, mensaje):
    conn = conectar()
    c = conn.cursor()
    c.execute("INSERT INTO chat_log (rol, mensaje) VALUES (?, ?)", ("model" if rol=="assistant" else rol, mensaje))
    conn.commit()
    conn.close()

def obtener_contexto():
    conn = conectar()
    c = conn.cursor()

    # memoria larga
    try:
        c.execute("SELECT contenido FROM resumenes")
        memoria = "\n".join([x[0] for x in c.fetchall()])
    except:
        memoria = ""

    # memoria corta
    c.execute("SELECT rol, mensaje FROM chat_log ORDER BY id DESC LIMIT 8")
    filas = c.fetchall()
    conn.close()

    historial = []
    for rol, msg in reversed(filas):
        r = "assistant" if rol == "model" else rol
        historial.append({"role": r, "content": msg})

    return memoria, historial

# --- IA ---
def llamar_jarvis(prompt):
    memoria, historial = obtener_contexto()

    client = Groq(api_key=st.secrets["GROQ_KEY_1"])

    system = f"""
    MEMORIA:
    {memoria}

    Eres JARVIS.
    Recuerdas a Ricardo.
    Eres preciso, elegante y lógico.
    """

    messages = [{"role": "system", "content": system}]
    messages.extend(historial)
    messages.append({"role": "user", "content": prompt})

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages
    )

    return res.choices[0].message.content

# --- UI ---
st.title("🔘 JARVIS VORTEX (RESTORE)")

if "messages" not in st.session_state:
    st.session_state.messages = []

# mostrar chat
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# input
if prompt := st.chat_input("Habla con JARVIS"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    guardar_mensaje("user", prompt)

    with st.chat_message("assistant"):
        respuesta = llamar_jarvis(prompt)
        st.markdown(respuesta)

    st.session_state.messages.append({"role": "assistant", "content": respuesta})
    guardar_mensaje("assistant", respuesta)
