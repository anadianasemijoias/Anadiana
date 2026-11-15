import streamlit as st
from passlib.hash import bcrypt
from modules.utils import get_db

def hash_senha(senha):
    return bcrypt.hash(senha)

def verificar_senha(senha_digitada, senha_hash):
    return bcrypt.verify(senha_digitada, senha_hash)

def criar_usuarios_iniciais():
    # ... (mantenha como estava) ...
    pass

def tela_login():
    # Layout centralizado
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        # OPÇÃO 1: Usar a imagem menor (deixe o try/except)
        try:
            # Largura de 250px para não ficar gigante
            st.image("logo.png", width=250)
            
        # OPÇÃO 2: Usar apenas o texto elegante (se apagar a imagem, ele cai aqui)
        except:
            st.markdown("""
                <h1 style='text-align: center; font-family: "Cormorant Garamond", serif; font-size: 3.5rem; margin-bottom: 0; padding-bottom: 0; color: #2C2C2C;'>
                    ANADIANA
                </h1>
                <p style='text-align: center; font-family: "Lato", sans-serif; font-size: 0.9rem; letter-spacing: 3px; color: #8A8A8A; text-transform: uppercase; margin-top: 5px;'>
                    Semijoias & Acessórios
                </p>
            """, unsafe_allow_html=True)
    
    st.write("---")
    st.subheader("Acesso ao Sistema")
    st.write("")

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
