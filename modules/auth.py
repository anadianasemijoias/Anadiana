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
    st.title("💎 Anadiana Semijoias")
    st.subheader("Acesso ao Sistema")

    with st.form("login_form"):
        usuario_input = st.text_input("Usuário").strip().lower()
        senha_input = st.text_input("Senha", type="password")
        botao_login = st.form_submit_button("Entrar")

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
