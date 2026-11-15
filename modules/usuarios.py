import streamlit as st
from modules.utils import get_db
from modules.auth import hash_senha

def tela_usuarios():
    st.header("👥 Gestão de Usuários")

    if st.session_state.get("cargo") != "Administrador":
        st.warning("Apenas administradores podem acessar esta tela.")
        return

    db = get_db()
    col = db["usuarios"]

    # Lista
    st.subheader("Usuários cadastrados")
    usuarios = list(col.find({}, {"senha": 0}))
    if usuarios:
        st.dataframe(
            [{"Nome": u["nome"], "Usuário": u["usuario"],
              "Cargo": u["cargo"], "Ativo": u["ativo"]} for u in usuarios],
            use_container_width=True,
        )
    else:
        st.info("Nenhum usuário cadastrado.")

    # Cadastro
    st.subheader("Cadastrar novo usuário")
    with st.form("novo_usuario"):
        nome = st.text_input("Nome completo")
        usuario = st.text_input("Usuário (login)").strip().lower()
        senha = st.text_input("Senha", type="password")
        cargo = st.selectbox("Cargo", ["Administrador", "Funcionário"])
        submit = st.form_submit_button("Cadastrar")

        if submit:
            if not (nome and usuario and senha):
                st.error("Preencha todos os campos.")
            elif col.find_one({"usuario": usuario}):
                st.error("Este usuário já existe.")
            else:
                col.insert_one({
                    "nome": nome,
                    "usuario": usuario,
                    "senha": hash_senha(senha),
                    "cargo": cargo,
                    "ativo": True,
                })
                st.success(f"Usuário {usuario} cadastrado com sucesso!")
                st.rerun()
