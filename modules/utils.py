import streamlit as st

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

        /* Deixar os botões mais elegantes (formato arredondado, sem sombra pesada) */
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

        /* Barra lateral um pouco mais escura para contraste */
        [data-testid="stSidebar"] {
            background-color: #F0EBE1;
            border-right: 1px solid #E0D8C8;
        }
        
        /* Esconder o menu hamburger e o footer do Streamlit para parecer um site/app */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        </style>
    """, unsafe_allow_html=True)
