import streamlit as st
from passlib.hash import bcrypt
from modules.utils import get_db, get_base64_image  # Importando a nova função

def hash_senha(senha):
    return bcrypt.hash(senha)

def verificar_senha(senha_digitada, senha_hash):
    return bcrypt.verify(senha_digitada, senha_hash)

def criar_usuarios_iniciais():
    """Cria Diego (Admin) e Kellen (Funcionária) se o banco estiver vazio."""
    db = get_db()
    usuarios_col = db["usuarios"]

    if usuarios_col.count_documents({}) == 0:
        usuarios_col.insert_many([
            {
                "nome": "Diego Roberto",
                "usuario": "diego",
                "senha": hash_senha("Diana@164707"),
                "cargo": "Administrador",
                "ativo": True,
            },
            {
                "nome": "Kellen Santos",
                "usuario": "kellen",
                "senha": hash_senha("Diana@164707"),
                "cargo": "Funcionário",
                "ativo": True,
            },
        ])
        st.toast("Usuários iniciais criados: diego e kellen (senha Diana@164707)", icon="✅")

def tela_login():
    # 1. Converte a logo.png para Base64 para usar no fundo
    img_base64 = get_base64_image("logo.png")
    
    # 2. Define o CSS do fundo (se a imagem existir, usa ela; senão, usa uma cor escura)
    if img_base64:
        bg_css = f"background-image: url('data:image/png;base64,{img_base64}'); background-size: cover; background-position: center; background-repeat: no-repeat; background-attachment: fixed;"
    else:
        bg_css = "background-color: #2C2C2C;"

    # --- CSS ESPECÍFICO PARA A TELA DE LOGIN ---
    st.markdown(f"""
        <style>
            /* Esconde o menu e footer */
            #MainMenu {{visibility: hidden;}}
            footer {{visibility: hidden;}}
            header {{visibility: hidden;}}

            /* --- FUNDO COM IMAGEM --- */
            .stApp {{
                {bg_css}
            }}

            /* --- OVERLAY ESCURO (Ajustado para 0.7 devido ao fundo preto da logo) --- */
            .stApp::before {{
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.7); 
                z-index: -1;
            }}

            /* --- ESTILO DO CARD DE LOGIN --- */
            /* Forçando o estilo com !important para evitar conflitos do Streamlit */
            div[data-testid="stForm"], .stForm {{
                background-color: #FFFFFF !important;
                padding: 2.5rem 2rem !important;
                border-radius: 15px !important;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4) !important;
                border: 1px solid #EAEAEA !important;
                max-width: 400px !important;
                margin: 0 auto !important;
            }}

            /* --- ESTILO DOS INPUTS --- */
            .stTextInput > div > div > input {{
                border-radius: 8px !important;
                border: 1px solid #E0D8C8 !important;
                padding: 12px 15px !important;
                font-size: 16px !important;
                background-color: #FFFFFF !important;
            }}
            .stTextInput > div > div > input:focus {{
                border-color: #2C2C2C !important;
                box-shadow: 0 0 0 1px #2C2C2C !important;
            }}

            /* --- ESTILO DO BOTÃO --- */
            .stButton > button {{
                width: 100% !important;
                background-color: #2C2C2C !important;
                color: #FFFFFF !important;
                border-radius: 8px !important;
                padding: 10px !important;
                font-weight: 600 !important;
                letter-spacing: 1px !important;
                border: none !important;
                transition: 0.3s !important;
            }}
            .stButton > button:hover {{
                background-color: #4A4A4A !important;
                color: #FFFFFF !important;
            }}
            
            /* --- TÍTULO --- */
            h3 {{
                text-align: center !important;
                font-family: 'Cormorant Garamond', serif !important;
                color: #2C2C2C !important;
                margin-bottom: 1.5rem !important;
            }}
        </style>
    """, unsafe_allow_html=True)

    # --- LAYOUT DA TELA ---
    # Cria 3 colunas para centralizar o formulário (a do meio é a do login)
    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        # Logo no topo do card (Tenta carregar a imagem, senão usa o texto)
        try:
            st.image("logo.png", width=150)
        except:
            st.markdown("<h1 style='text-align: center; color: #2C2C2C;'>ANADIANA</h1>", unsafe_allow_html=True)

        st.subheader("Acesso ao Sistema")

        # O formulário (o CSS acima aplica o estilo de "card" a este form)
        with st.form("login_form"):
            usuario_input = st.text_input("Usuário", placeholder="Digite seu usuário").strip().lower()
            senha_input = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            
            # Espaçamento
            st.write("")
            
            botao_login = st.form_submit_button("Entrar", use_container_width=True)

            if botao_login:
                db = get_db()
                user = db["usuarios"].find_one({"usuario": usuario_input})

                if user and user.get("ativo", False):
                    if verificar_senha(senha_input, user["senha"]):
                        st.session_state["logged_in"] = True
                        st.session_state["usuario_logado"] = user["nome"]
                        st.session_state["usuario_id"] = str(user["_id"])
                        st.session_state["cargo"] = user["cargo"]
                        st.rerun()
                    else:
                        st.error("Senha incorreta.")
                else:
                    st.error("Usuário não encontrado ou inativo.")
