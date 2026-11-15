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
    # --- CSS ESPECÍFICO PARA O CARD DE LOGIN ---
    st.markdown("""
        <style>
        /* Cria o fundo do card central */
        div[data-testid="stVerticalBlock"] > div:has(div.stForm) {
            background-color: #FFFFFF;
            padding: 2.5rem 2rem;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
            border: 1px solid #F0EBE1;
            max-width: 450px;
            margin: 0 auto;
        }
        
        /* Ajusta a logo dentro do card */
        div[data-testid="stVerticalBlock"] > div:has(div.stForm) img {
            display: block;
            margin: 0 auto 1.5rem auto;
            max-width: 180px !important;
        }

        /* Título "Acesso ao Sistema" estilizado */
        h3 {
            text-align: center;
            font-family: 'Cormorant Garamond', serif;
            color: #2C2C2C;
            margin-bottom: 1.5rem !important;
        }

        /* Ajusta os inputs para ficarem mais elegantes */
        .stTextInput input {
            border-radius: 8px;
            border: 1px solid #E0D8C8;
            padding: 10px 15px;
        }
        .stTextInput input:focus {
            border-color: #8A8A8A;
            box-shadow: 0 0 0 1px #8A8A8A;
        }
        
        /* Botão de entrar */
        .stButton>button {
            background-color: #2C2C2C;
            color: #FFFFFF;
            border-radius: 8px;
            padding: 10px;
            font-weight: 600;
            letter-spacing: 1px;
            margin-top: 1rem;
        }
        .stButton>button:hover {
            background-color: #4A4A4A;
            color: #FFFFFF;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- CONTEÚDO DO CARD ---
    # Colunas para centralizar o formulário
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Logo (Tenta carregar a imagem, senão usa o texto)
        try:
            st.image("logo.png", use_column_width=False)
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

        with st.form("login_form"):
            usuario_input = st.text_input("Usuário").strip().lower()
            senha_input = st.text_input("Senha", type="password")
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
