import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
import sqlite3
import json

st.set_page_config(page_title="JARVIS OS", layout="wide")

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

    client = Groq(api_key=st.secrets["GROQ_KEY_1"])
    chat_completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": "Eres JARVIS, elegante, preciso y directo."},
            {"role": "user", "content": prompt}
        ]
    )
    return chat_completion.choices[0].message.content

# --- ESTADO ---
if "chat" not in st.session_state:
    st.session_state.chat = []

# --- HTML COMPONENT ---
component_value = components.html(f"""
<!DOCTYPE html>
<html>
<head>
<style>
body {{
    background:#050609;
    color:white;
    font-family:Segoe UI;
    margin:0;
}}
#chat {{
    height:85vh;
    overflow-y:auto;
    padding:15px;
}}
.msg {{
    padding:10px;
    margin:5px;
    border-radius:10px;
}}
.user {{ background:#222; text-align:right; }}
.jarvis {{ background:#0af2; }}
input {{
    width:80%;
    padding:10px;
}}
button {{
    padding:10px;
}}
</style>
</head>

<body>

<div id="chat"></div>

<div>
<input id="input" placeholder="Escribe..." />
<button onclick="send()">Enviar</button>
</div>

<script>
const chatDiv = document.getElementById("chat");

// Cargar historial desde Streamlit
const historial = {json.dumps(st.session_state.chat)};
historial.forEach(m => addMessage(m.role, m.content));

function addMessage(role, text) {{
    let div = document.createElement("div");
    div.className = "msg " + role;
    div.innerText = text;
    chatDiv.appendChild(div);
    chatDiv.scrollTop = chatDiv.scrollHeight;
}}

function send() {{
    let input = document.getElementById("input");
    let text = input.value.trim();
    if (!text) return;

    addMessage("user", text);

    // enviar a Streamlit
    window.parent.postMessage({{
        type: "chat",
        text: text
    }}, "*");

    input.value = "";
}}

// recibir respuesta de Streamlit
window.addEventListener("message", (event) => {{
    if (event.data.type === "response") {{
        addMessage("jarvis", event.data.text);
    }}
}});
</script>

</body>
</html>
""", height=800)

# --- RECEPCIÓN DE MENSAJES ---
if component_value:
    data = component_value
    if data["type"] == "chat":
        user_msg = data["text"]

        st.session_state.chat.append({"role": "user", "content": user_msg})

        respuesta = llamar_a_groq(user_msg)

        st.session_state.chat.append({"role": "jarvis", "content": respuesta})

        # reenviar respuesta al frontend
        components.html(f"""
        <script>
        window.parent.postMessage({{
            type: "response",
            text: {json.dumps(respuesta)}
        }}, "*");
        </script>
        """, height=0)
