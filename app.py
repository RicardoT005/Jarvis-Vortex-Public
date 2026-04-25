import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
import sqlite3

# --- CONFIGURACIÓN DE NÚCLEO ---
st.set_page_config(page_title="JARVIS OS", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        #MainMenu, footer, header {visibility: hidden;}
        .stApp {margin: 0; padding: 0; background-color: #050609; overflow: hidden;}
        .block-container {padding: 0 !important;}
        iframe {border: none; width: 100vw; height: 100vh;}
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN A LA BASE DE DATOS (.DB) ---
def buscar_en_db(texto):
    try:
        conn = sqlite3.connect('jarvis_memoria.db')
        cursor = conn.cursor()
        # Buscamos coincidencias en tu tabla de memoria
        cursor.execute("SELECT respuesta FROM memoria WHERE pregunta LIKE ?", (f'%{texto}%',))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else None
    except:
        return None

# --- LÓGICA DE IA ---
def respuesta_jarvis(prompt):
    # 1. Intentar recordar del .db
    memoria = buscar_en_db(prompt)
    if memoria: return f"{memoria} (Dato recuperado de mi núcleo de memoria)"

    # 2. Si no lo sabe, preguntar a Groq
    try:
        client = Groq(api_key=st.secrets["GROQ_KEY_1"])
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": "Eres JARVIS, la IA de Ricardo. Eres elegante, leal y técnico."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error en reactor: {e}"

# --- PUENTE DE COMUNICACIÓN ---
# Usamos un componente que detecta cambios en tiempo real
if "historial" not in st.session_state:
    st.session_state.historial = ""

# Capturar mensaje de la URL (Método forzado)
query = st.query_params.get("chat", "")
if query and query != st.session_state.get("last_query", ""):
    with st.spinner(""): # Procesa en segundo plano
        res = respuesta_jarvis(query)
        st.session_state.historial += f'<div class="msg user"><strong>RICARDO:</strong> {query}</div>'
        st.session_state.historial += f'<div class="msg jarvis"><strong>JARVIS:</strong> {res}</div>'
        st.session_state.last_query = query

# --- INYECCIÓN AL HTML ---
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read().replace("", st.session_state.historial)
    
    # El secreto: Enviar el historial actualizado al HTML
    components.html(html_code, height=1500)
except Exception as e:
    st.error(f"Error crítico: {e}")
