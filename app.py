import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
import sqlite3

# --- CONFIGURACIÓN DE NÚCLEO ---
st.set_page_config(page_title="JARVIS OS", layout="wide", initial_sidebar_state="collapsed")

# Ocultar rastro de Streamlit
st.markdown("""
    <style>
        #MainMenu, footer, header {visibility: hidden;}
        .stApp {margin: 0; padding: 0; background-color: #050609; overflow: hidden;}
        .block-container {padding: 0 !important;}
        iframe {border: none; width: 100vw; height: 100vh;}
    </style>
""", unsafe_allow_html=True)

# --- MEMORIA DE SESIÓN ---
if "chat_log" not in st.session_state:
    st.session_state.chat_log = ""

# --- FUNCIÓN DE IA ---
def jarvis_brain(prompt):
    try:
        client = Groq(api_key=st.secrets["GROQ_KEY_1"])
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": "Eres JARVIS, la IA de Ricardo. Eres elegante y técnico."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"ERROR: Reactor inestable. {e}"

# --- DETECCIÓN DE MENSAJE ---
query_params = st.query_params
user_msg = query_params.get("chat", "")

if user_msg and user_msg != st.session_state.get("last_msg", ""):
    resp = jarvis_brain(user_msg)
    st.session_state.chat_log += f'<div class="msg user"><strong>RICARDO:</strong> {user_msg}</div>'
    st.session_state.chat_log += f'<div class="msg jarvis"><strong>JARVIS:</strong> {resp}</div>'
    st.session_state.last_msg = user_msg

# --- RENDER FINAL ---
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read().replace("", st.session_state.chat_log)
    components.html(html, height=1500)
except Exception as e:
    st.error(e)
