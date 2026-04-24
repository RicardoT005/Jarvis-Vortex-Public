import streamlit as st
import streamlit.components.v1 as components
from groq import Groq

# --- CONFIGURACIÓN DE PANTALLA ---
st.set_page_config(
    page_title="JARVIS OS",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Ocultar la interfaz de Streamlit por completo
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stApp {margin: 0; padding: 0; background-color: #050609; overflow: hidden;}
        .block-container {padding: 0 !important;}
        iframe {border: none; width: 100vw; height: 100vh;}
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN CON LOS REACTORES (GROQ) ---
def procesar_respuesta_jarvis(prompt):
    try:
        client = Groq(api_key=st.secrets["GROQ_KEY_1"])
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": "Eres JARVIS, la IA avanzada de Ricardo. Eres sofisticado y técnico. Responde de forma elegante."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"ALERTA: Reactor inestable. {str(e)}"

# --- LÓGICA DE COMUNICACIÓN ---
user_input = st.query_params.get("chat", "")
jarvis_response = ""

if user_input:
    jarvis_response = procesar_respuesta_jarvis(user_input)

# --- CARGA DEL HOGAR DE JARVIS (HTML) ---
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    
    # Inyectar el historial si existe
    if user_input and jarvis_response:
        chat_html = f"""
            <div class="msg user"><strong>RICARDO:</strong> {user_input}</div>
            <div class="msg jarvis"><strong>JARVIS:</strong> {jarvis_response}</div>
        """
        html_code = html_code.replace(
            "",
            chat_html
        )

    # El componente ahora ocupa el 100% real de la ventana
    components.html(html_code, height=2000) 
except Exception as e:
    st.error(f"Error: {e}")
