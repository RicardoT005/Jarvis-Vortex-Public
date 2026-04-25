import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
import sqlite3

# Configuración básica
st.set_page_config(page_title="JARVIS OS", layout="wide", initial_sidebar_state="collapsed")

# Estilos para limpiar la pantalla de Streamlit
st.markdown("""
    <style>
        #MainMenu, footer, header {visibility: hidden;}
        .stApp {margin: 0; padding: 0; background-color: #050609; overflow: hidden;}
        .block-container {padding: 0 !important;}
        iframe {border: none; width: 100vw; height: 100vh;}
    </style>
""", unsafe_allow_html=True)

# --- BASE DE DATOS (.DB) ---
def buscar_memoria(texto):
    try:
        conn = sqlite3.connect('jarvis_memoria.db')
        cursor = conn.cursor()
        cursor.execute("SELECT respuesta FROM memoria WHERE pregunta LIKE ?", (f'%{texto}%',))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else None
    except: return None

# --- MOTOR DE INTELIGENCIA ---
def llamar_a_groq(prompt):
    memoria = buscar_memoria(prompt)
    if memoria: return f"{memoria} (Memoria Local)"
    try:
        client = Groq(api_key=st.secrets["GROQ_KEY_1"])
        chat_completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "system", "content": "Eres JARVIS, la IA de Ricardo. Elegante y eficiente."},
                      {"role": "user", "content": prompt}]
        )
        return chat_completion.choices[0].message.content
    except Exception as e: return f"Error: {e}"

# --- GESTIÓN DE MENSAJES ---
if "historial" not in st.session_state:
    st.session_state.historial = ""

# Captura de datos desde la URL (el método más directo)
params = st.query_params
if "chat" in params:
    pregunta = params["chat"]
    if pregunta != st.session_state.get("last_chat", ""):
        respuesta = llamar_a_groq(pregunta)
        st.session_state.historial += f'<div class="msg user"><strong>RICARDO:</strong> {pregunta}</div>'
        st.session_state.historial += f'<div class="msg jarvis"><strong>JARVIS:</strong> {respuesta}</div>'
        st.session_state.last_chat = pregunta
        st.query_params.clear() # Limpia la URL para evitar bucles

# --- CARGA DE INTERFAZ ---
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read().replace("{{CHAT}}", st.session_state.historial)
    components.html(html_code, height=1500)
except Exception as e:
    st.error(f"Error cargando HTML: {e}")
