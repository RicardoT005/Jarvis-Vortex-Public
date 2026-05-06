import streamlit as st

st.write("URL:", st.secrets.get("SUPABASE_URL"))
st.write("KEY empieza:", str(st.secrets.get("SUPABASE_KEY"))[:20])
