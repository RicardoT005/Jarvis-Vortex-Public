import streamlit as st
from groq import Groq
import sqlite3

st.set_page_config(page_title="JARVIS OS", layout="wide")

# --- ESTILO JARVIS ---
st.markdown("""
<style>
body {
    background-color: #050609;
}
.stChatMessage.user {
    background-color: rgba(255,255,255,0.07);
    border-radius: 10px;
}
.stChatMessage.assistant {
    background-color: rgba(0,242,254,0.1);
    border-left: 3px solid #00f2fe;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# --- BASE DE DATOS ---
def buscar_memoria(texto):
    try:
        conn = sqlite3.connect('jarvis_memoria.db')
        cursor = conn.cursor()
        cursor.execute("SELECT respuesta FROM memoria WHERE pregunta LIKE ?", (f'%{texto}%',))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else None
    except:
        return None

# --- IA ---
def llamar_a_groq(prompt):
    memoria = buscar_memoria(prompt)
    if memoria:
        return f"{memoria} (Memoria Local)"

    try:
        client = Groq(api_key=st.secrets["GROQ_KEY_1"])

        chat_completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "Eres JARVIS, elegante y directo."},
                {"role": "user", "content": prompt}
            ]
        )

        return chat_completion.choices[0].message.content

    except Exception as e:
        return f"ERROR REAL: {str(e)}"

# --- HISTORIAL ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- MOSTRAR MENSAJES ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- INPUT ---
prompt = st.chat_input("Habla con JARVIS...")

if prompt:
    # Usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # IA
    respuesta = llamar_a_groq(prompt)

    st.session_state.messages.append({"role": "assistant", "content": respuesta})
    with st.chat_message("assistant"):
        st.markdown(respuesta)
