import streamlit as st
import sqlite3
import os
import time
from groq import Groq

# --- SISTEMA DE ENERGÍA (REDUNDANCIA TRIPLE) ---
# Sustituye estas variables con tus llaves reales o asegúrate de que estén en tu terminal
KEYS = {
    "PRINCIPAL": os.getenv("GROQ_KEY_1"),
    "DATOS": os.getenv("GROQ_KEY_2"),
    "EMERGENCIA": os.getenv("GROQ_KEY_3")
}

DB_NAME = 'jarvis_memoria.db'
CUOTA_DIARIA = 100000  # Límite de tokens de Groq (Llama 3.3 70B)

# --- GESTIÓN DE BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_log 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, rol TEXT, mensaje TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS resumenes 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, contenido TEXT)''')
    # Tabla de consciencia de recursos por fecha
    cursor.execute('''CREATE TABLE IF NOT EXISTS tokens_stats 
                      (fecha DATE DEFAULT CURRENT_DATE, usado INTEGER, PRIMARY KEY(fecha))''')
    conn.commit()
    conn.close()

def actualizar_tokens(n_tokens):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO tokens_stats (fecha, usado) VALUES (CURRENT_DATE, 0)")
    cursor.execute("UPDATE tokens_stats SET usado = usado + ? WHERE fecha = CURRENT_DATE", (n_tokens,))
    conn.commit()
    conn.close()

def obtener_uso_tokens():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT usado FROM tokens_stats WHERE fecha = CURRENT_DATE")
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else 0

def guardar_mensaje(rol, mensaje):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_log (rol, mensaje) VALUES (?, ?)", ("model" if rol == "assistant" else rol, mensaje))
    conn.commit()
    conn.close()

def obtener_contexto():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT contenido FROM resumenes")
    resumenes = "\n".join([row[0] for row in cursor.fetchall()])
    cursor.execute("SELECT rol, mensaje FROM chat_log ORDER BY id DESC LIMIT 8")
    filas = cursor.fetchall()
    conn.close()
    
    historial = []
    for rol, mensaje in reversed(filas):
        r = "assistant" if rol == "model" else rol
        historial.append({"role": r, "content": mensaje})
    return resumenes, historial

# --- MOTOR VORTEX (LÓGICA DE CONMUTACIÓN) ---
def llamar_jarvis_vortex(prompt_usuario, memoria_larga, historial, modo="PRINCIPAL"):
    usado_hoy = obtener_uso_tokens()
    restante = CUOTA_DIARIA - usado_hoy
    
    # Selector de Cliente basado en el modo
    key_actual = KEYS.get(modo) or KEYS["PRINCIPAL"]
    client = Groq(api_key=key_actual)
    
    fuente_texto = "REACTOR PRINCIPAL" if modo == "PRINCIPAL" else f"MÓDULO DE {modo}"
    
    # Instrucción de Personalidad Equilibrada y Consciencia de Recursos
    system_prompt = (
        f"CONTEXTO MEMORIA: {memoria_larga}\n"
        f"ESTADO DE ENERGÍA: {fuente_texto} | {restante} tokens disponibles hoy.\n"
        "Eres JARVIS. Instrucciones de comportamiento:\n"
        "1. Personalidad: Equilibrio maestro entre la amabilidad de Gemini y la firmeza lógica.\n"
        "2. Consciencia: Sabes cuántos tokens te quedan. Si hay menos de 10,000, sé breve.\n"
        "3. Estilo: Elegante, técnico y aliado de Ricardo. No seas rudo sin necesidad lógica."
    )
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, *historial, {"role": "user", "content": prompt_usuario}],
            temperature=0.6,
        )
        
        total_tokens = completion.usage.total_tokens
        actualizar_tokens(total_tokens)
        
        respuesta = completion.choices[0].message.content
        meta_info = f"\n\n`[Fuente: {fuente_texto} | Gasto: {total_tokens} tokens | Restante: {CUOTA_DIARIA - (usado_hoy + total_tokens)}]`"
        return respuesta + meta_info
    except Exception as e:
        if "429" in str(e):
            return "⚠️ ADVERTENCIA: Reactor Principal agotado. Cambiando a Núcleo de Emergencia..."
        return f"❌ Error Crítico en Núcleo: {e}"

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="JARVIS VORTEX OS", page_icon="🔘", layout="wide")
st.markdown("<style>.stApp { background-color: #050505; color: #00ff41; font-family: monospace; }</style>", unsafe_allow_html=True)

st.title("🔘 JARVIS OS - NÚCLEO VORTEX v5.0")
init_db()

# BARRA LATERAL (ESTADO DE RECURSOS)
with st.sidebar:
    usado = obtener_uso_tokens()
    st.header("⚡ Monitor de Energía")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Uso Hoy", f"{usado}")
    with col2:
        st.metric("Restante", f"{CUOTA_DIARIA - usado}")
    
    st.progress(min(usado / CUOTA_DIARIA, 1.0))
    
    st.divider()
    st.header("📂 Gestión de Datos")
    file = st.file_uploader("Inyectar archivo al flujo", type=['txt', 'py', 'json'])
    
    st.divider()
    st.info("Modo de Procesamiento: Automático (Smart Switch)")

# CHAT INTERFAZ
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Órdenes para Jarvis..."):
    # Determinamos el modo (si hay archivo, usamos la Key de DATOS)
    modo_actual = "PRINCIPAL"
    if file:
        modo_actual = "DATOS"
        content_file = file.getvalue().decode("utf-8")
        prompt = f"ANALIZA ESTE DOCUMENTO:\n{content_file}\n\nINSTRUCCIÓN: {prompt}"

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    guardar_mensaje("user", prompt)
    
    with st.chat_message("assistant"):
        mem_larga, hist_reciente = obtener_contexto()
        # Llamada al motor con selector de modo
        with st.spinner(f"Accediendo a {modo_actual}..."):
            respuesta = llamar_jarvis_vortex(prompt, mem_larga, hist_reciente, modo=modo_actual)
            st.markdown(respuesta)
    
    st.session_state.messages.append({"role": "assistant", "content": respuesta})
    guardar_mensaje("assistant", respuesta)
