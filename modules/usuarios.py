import streamlit as st
from modules.utils import get_db
from modules.auth import hash_senha
from bson import ObjectId


def _apenas_admin():
    if st.session_state.get("cargo") != "Administrador":
        st.warning("Apenas administradores podem acessar esta tela.")
        return False
    return True


def _contar_admins_ativos(col, ignorar_id=None):
    filtro = {"cargo": "Administrador", "ativo": True}
    if ignorar_id:
        filtro["_id"] = {"$ne": ObjectId(ignorar_id)}
    return col.count_documents(filtro)


def tela_usuarios():
    st.header("👥 Gestão de Usuários")

    if not _apenas_admin():
        return

    db = get_db()
    col = db["usuarios"]

    # ---------- LISTAGEM ----------
    st.subheader("Usuários cadastrados")
    usuarios = list(col.find({}, {"senha": 0}))
    if usuarios:
        st.dataframe(
            [
                {
                    "Nome": u["nome"],
                    "Login": u["usuario"],
                    "Cargo": u["cargo"],
                    "Ativo": "✅" if u.get("ativo") else "❌",
                }
                for u in usuarios
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum usuário cadastrado.")

    st.divider()

    # ---------- CADASTRO ----------
    with st.expander("➕ Cadastrar novo usuário", expanded=False):
        with st.form("novo_usuario"):
            nome = st.text_input("Nome completo")
            usuario = st.text_input("Login (usuário)").strip().lower()
            senha = st.text_input("Senha", type="password")
            cargo = st.selectbox("Cargo", ["Administrador", "Funcionário"])
            submit = st.form_submit_button("Cadastrar")

            if submit:
                if not (nome and usuario and senha):
                    st.error("Preencha todos os campos.")
                elif col.find_one({"usuario": usuario}):
                    st.error("Este login já existe.")
                elif len(senha) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres.")
                elif " " in usuario:
                    st.error("O login não pode conter espaços.")
                else:
                    col.insert_one({
                        "nome": nome,
                        "usuario": usuario,
                        "senha": hash_senha(senha),
                        "cargo": cargo,
                        "ativo": True,
                    })
                    st.success(f"Usuário **{usuario}** cadastrado com sucesso!")
                    st.rerun()

    st.divider()

    # ---------- EDIÇÃO ----------
    st.subheader("✏️ Editar usuário")
    if not usuarios:
        st.info("Nenhum usuário para editar.")
        return

    opcoes = {f"{u['nome']} ({u['usuario']})": u for u in usuarios}
    escolha = st.selectbox("Selecione o usuário", list(opcoes.keys()))
    user = opcoes[escolha]
    user_id = str(user["_id"])

    with st.form("editar_usuario"):
        novo_nome = st.text_input("Nome completo", value=user["nome"])
        novo_login = st.text_input("Login (usuário)", value=user["usuario"]).strip().lower()
        novo_cargo = st.selectbox(
            "Cargo",
            ["Administrador", "Funcionário"],
            index=0 if user["cargo"] == "Administrador" else 1,
        )
        novo_ativo = st.checkbox("Usuário ativo", value=bool(user.get("ativo", True)))

        st.markdown("**Redefinir senha** (deixe em branco para não alterar)")
        nova_senha = st.text_input("Nova senha", type="password")
        confirmar_senha = st.text_input("Confirmar nova senha", type="password")

        salvar = st.form_submit_button("💾 Salvar alterações")

        if salvar:
            erro = False
            dados = {"nome": novo_nome, "cargo": novo_cargo, "ativo": novo_ativo}

            # Validação do login
            if not novo_login:
                st.error("O login não pode ficar em branco.")
                erro = True
            elif " " in novo_login:
                st.error("O login não pode conter espaços.")
                erro = True
            elif novo_login != user["usuario"]:
                # Só verifica duplicidade se mudou
                if col.find_one({"usuario": novo_login, "_id": {"$ne": ObjectId(user_id)}}):
                    st.error("Este login já está em uso por outro usuário.")
                    erro = True
                else:
                    dados["usuario"] = novo_login

            # Proteção: não permitir desativar/rebaixar o último admin ativo
            if user["cargo"] == "Administrador" and (not novo_ativo or novo_cargo != "Administrador"):
                if _contar_admins_ativos(col, ignorar_id=user_id) == 0:
                    st.error("Não é possível desativar ou rebaixar o último administrador ativo.")
                    erro = True

            # Senha
            if nova_senha or confirmar_senha:
                if nova_senha != confirmar_senha:
                    st.error("As senhas não coincidem.")
                    erro = True
                elif len(nova_senha) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres.")
                    erro = True
                else:
                    dados["senha"] = hash_senha(nova_senha)

            if not erro:
                col.update_one({"_id": ObjectId(user_id)}, {"$set": dados})
                st.success("Usuário atualizado com sucesso!")
                st.rerun()

    st.divider()
    st.caption(
        "💡 O **login** deve ser único e sem espaços (use ponto, underline ou hífen). "
        "Para excluir um usuário, prefira **desativá-lo** — assim o histórico é preservado."
    )
