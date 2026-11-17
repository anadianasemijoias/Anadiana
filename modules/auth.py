import streamlit as st
from passlib.hash import bcrypt
from modules.utils import get_db

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
    # --- CSS CUSTOMIZADO ---
    st.markdown("""
        <style>
            /* Esconde o menu e footer do Streamlit para ficar limpo */
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}

            /* Fundo da página levemente cinza para destacar o card branco */
            .stApp {
                background-color: #fcfcfc;
            }

            /* ESTILO DO CARD DE LOGIN */
            div[data-testid="stForm"] {
                background-color: #FFFFFF;
                padding: 2.5rem 2rem;
                border-radius: 15px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
                border: 1px solid #EAEAEA;
                max-width: 400px; /* Largura máxima do card */
                margin: 0 auto;
            }

            /* ESTILO DOS INPUTS */
            .stTextInput > div > div > input {
                border-radius: 8px;
                border: 1px solid #E0D8C8;
                padding: 12px 15px;
                font-size: 16px;
            }
            .stTextInput > div > div > input:focus {
                border-color: #2C2C2C;
                box-shadow: 0 0 0 1px #2C2C2C;
            }

            /* ESTILO DO BOTÃO */
            .stButton > button {
                width: 100%;
                background-color: #2C2C2C;
                color: #FFFFFF;
                border-radius: 8px;
                padding: 10px;
                font-weight: 600;
                letter-spacing: 1px;
                border: none;
                transition: 0.3s;
            }
            .stButton > button:hover {
                background-color: #4A4A4A;
                color: #FFFFFF;
            }
            
            /* Título */
            h3 {
                text-align: center;
                font-family: 'Cormorant Garamond', serif;
                color: #2C2C2C;
                margin-bottom: 1.5rem !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # --- LAYOUT ---
    # Cria 3 colunas para centralizar o formulário (a do meio é a do login)
    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        # Logo (Tenta carregar a imagem, senão usa o texto)
        try:
            # Ajuste o width conforme o tamanho da sua logo
            st.image("logo.png", width=180) 
        except:
            st.markdown("""
                <h1 style='text-align: center; font-family: "Cormorant Garamond", serif; font-size: 2.5rem; margin-bottom: 0; padding-bottom: 0; color: #2C2C2C;'>
                    ANADIANA
                </h1>
                <p style='text-align: center; font-family: "Lato", sans-serif; font-size: 0.8rem; letter-spacing: 3px; color: #8A8A8A; text-transform: uppercase; margin-top: 5px; margin-bottom: 2rem;'>
                    Semijoias & Acessórios
                </p>
            """, unsafe_allow_html=True)

        st.subheader("Acesso ao Sistema")

        # O formulário (O CSS acima aplica o estilo de "card" a este form)
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
