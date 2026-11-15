import sys
import os

# Garante que a raiz do projeto esteja no sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from modules.auth import tela_login, criar_usuarios_iniciais
from modules.config import tela_config
from modules.usuarios import tela_usuarios
from modules.produtos import tela_produtos

st.set_page_config(page_title="Anadiana Semijoias", page_icon="💎", layout="wide")

# Garante usuários iniciais
try:
    criar_usuarios_iniciais()
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados. Detalhes: {e}")
    st.stop()

# Inicializa sessão
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# --- FLUXO ---
if not st.session_state["logged_in"]:
    tela_login()
else:
    st.sidebar.title(f"Olá, {st.session_state['usuario_logado']}!")
    st.sidebar.write(f"Cargo: {st.session_state['cargo']}")

    opcoes = [
        "🏠 Início",
        "⚙️ Parâmetros",
        "📦 Produtos",
        "🛒 Compras",
        "💰 Vendas",
        "💳 Recebimentos",
        "🧾 Despesas",
        "🤝 Sócios",
    ]
    if st.session_state.get("cargo") == "Administrador":
        opcoes.append("👥 Usuários")

    menu = st.sidebar.radio("Navegação", opcoes)

    if st.sidebar.button("Sair"):
        for k in ["logged_in", "usuario_logado", "usuario_id", "cargo"]:
            st.session_state[k] = None
        st.session_state["logged_in"] = False
        st.rerun()

    # Roteamento
    if menu == "🏠 Início":
        st.title("💎 Anadiana Semijoias")
        st.write("Bem-vindo ao sistema de gestão.")
        st.info("Use o menu lateral para navegar. Comece por **Parâmetros**.")
        st.subheader("Módulos planejados")
        st.markdown("""
        - ⚙️ **Parâmetros** ✅
        - 👥 **Usuários** ✅
        - 📦 **Produtos** ✅
        - 🛒 **Compras** ✅
        - 💰 **Vendas + Itens** ✅
        - 💳 **Recebimentos** ✅
        - 🧾 **Despesas** e 🤝 **Sócios** ✅
        - 🔄 **Ajustes** (próximo)
        - 📊 **Caixa, DRE e Painel**
        """)
    elif menu == "⚙️ Parâmetros":
        tela_config()
    elif menu == "📦 Produtos":
        tela_produtos()
    elif menu == "🛒 Compras":
        from modules.compras import tela_compras
        tela_compras()
    elif menu == "💰 Vendas":
        from modules.vendas import tela_vendas
        tela_vendas()
    elif menu == "💳 Recebimentos":
        from modules.recebimentos import tela_recebimentos
        tela_recebimentos()
    elif menu == "🧾 Despesas":
        from modules.despesas import tela_despesas
        tela_despesas()
    elif menu == "🤝 Sócios":
        from modules.socios import tela_socios
        tela_socios()
    elif menu == "👥 Usuários":
        tela_usuarios()
