import streamlit as st
import pymongo
from datetime import datetime
import base64  # <-- Nova importação necessária

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

def carregar_css():
    """Aplica estilos personalizados (identidade visual Anadiana)."""
    st.markdown("""
        <style>
        /* Importar fontes do Google */
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Lato:wght@300;400;700&display=swap');

        /* Alterar a fonte de todos os textos para Lato (mais limpa) */
        html, body, [class*="css"] {
            font-family: 'Lato', sans-serif;
        }

        /* Títulos principais usando a fonte serifada elegante */
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Cormorant Garamond', serif;
            color: #2C2C2C;
        }

        /* Deixar os botões mais elegantes */
        .stButton>button {
            border-radius: 4px;
            font-family: 'Lato', sans-serif;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            font-size: 0.8rem;
            transition: all 0.3s ease;
        }
        
        .stButton>button:hover {
            transform: scale(1.02);
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        /* Barra lateral ajustada para a cor de fundo da marca */
        [data-testid="stSidebar"] {
            background-color: #F0EBE1;
            border-right: 1px solid #E0D8C8;
        }
        
        /* Esconder o menu hamburger e o footer do Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        </style>
    """, unsafe_allow_html=True)

# --- NOVA FUNÇÃO PARA IMAGEM DE FUNDO ---
def get_base64_image(image_path):
    """Converte uma imagem local em string Base64 para uso no CSS."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None
