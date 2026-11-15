import streamlit as st
import pymongo
from datetime import datetime

@st.cache_resource
def get_db():
    uri = st.secrets["mongo"]["uri"]
    client = pymongo.MongoClient(uri)
    return client[st.secrets["mongo"]["db_name"]]

def brl(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"

def pct(valor):
    try:
        return f"{float(valor)*100:.2f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "0,00%"

def agora():
    return datetime.now()
