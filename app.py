import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
import sqlite3
import os

# --- 1. CONEXIÓN AL CEREBRO (.DB) ---
def consultar_memoria(usuario_input):
    # Conectamos al archivo de base de datos
    conn = sqlite3.connect('jarvis_memoria.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Aquí puedes añadir la lógica que ya teníamos para buscar 
    # recuerdos relevantes basados en el texto de Ricardo
    cursor.execute("SELECT respuesta FROM memoria WHERE pregunta LIKE ?", ('%' + usuario_input + '%',))
    resultado = cursor.fetchone()
    
    conn.close()
    return resultado[0] if resultado else None

def guardar_en_memoria(pregunta, respuesta):
    conn = sqlite3.connect('jarvis_memoria.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO memoria (pregunta, respuesta) VALUES (?, ?)", (pregunta, respuesta))
    conn.commit()
    conn.close()

# --- 2. CONFIGURACIÓN DE PANTALLA ---
st.set_page_config(page_title="JARVIS OS | VORTEX", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        .stApp {margin: 0; padding: 0; background-color: #050609; overflow: hidden;}
        .block-container {padding: 0 !important;}
        iframe {border: none; width: 100vw; height: 100vh;}
    </style>
""", unsafe_allow_html=True)

# --- 3. MEMORIA DE SESIÓN (FRONTEND) ---
if "historial_html" not in st.session_state:
    st.session_state.historial_html = ""

# --- 4. PROCESAMIENTO CON GROQ + BASE DE DATOS ---
def procesar_con_jarvis(texto):
    # Primero revisamos si Jarvis ya sabe la respuesta en su .db
    recuerdo = consultar_memoria(texto)
    if recuerdo:
        return f"{recuerdo} (Recuperado de mi base de datos central)"

    try:
        client = Groq(api_key=st.secrets["GROQ_KEY_1"])
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": "Eres JARVIS, la IA de Ricardo. Eres sofisticado. Usa tu base de datos para recordar detalles."},
                {"role": "user", "content": texto}
            ],
            temperature=0.7,
        )
        respuesta = completion.choices[0].message.content
        
        # Guardamos lo nuevo para que no se le olvide
        guardar_en_memoria(texto, respuesta)
        return respuesta
    except Exception as e:
        return f"Error en reactor: {str(e)}"

# --- 5. LÓGICA DE INTERACCIÓN ---
query_params = st.query_params
mensaje_usuario = query_params.get("chat", "")

if mensaje_usuario and mensaje_usuario != st.session_state.get("last_msg", ""):
    resp = procesar_con_jarvis(mensaje_usuario)
    st.session_state.historial_html += f'<div class="msg user"><strong>RICARDO:</strong> {mensaje_usuario}</div>'
    st.session_state.historial_html += f'<div class="msg jarvis"><strong>JARVIS:</strong> {resp}</div>'
    st.session_state.last_msg = mensaje_usuario

# --- 6. RENDERIZADO FINAL ---
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_final = f.read().replace("", st.session_state.historial_html)
    components.html(html_final, height=2000)
except Exception as e:
    st.error(f"Error: {e}")
