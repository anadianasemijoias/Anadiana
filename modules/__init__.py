import streamlit as st
import pymongo
from datetime import datetime

@st.cache_resource
def get_db():
    """Retorna o banco de dados MongoDB (conexão cacheada)."""
    uri = st.secrets["mongo"]["uri"]
    client = pymongo.MongoClient(uri)
    return client[st.secrets["mongo"]["db_name"]]

def brl(valor):
    """Formata número como moeda brasileira."""
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"

def pct(valor):
    """Formata número como percentual."""
    try:
        return f"{float(valor)*100:.2f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "0,00%"

def agora():
    return datetime.now()
