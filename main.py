import sys
import os

# Garante que a raiz do projeto esteja no sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from modules.auth import tela_login, criar_usuarios_iniciais
from modules.config import tela_config
from modules.usuarios import tela_usuarios
from modules.produtos import tela_produtos
from modules.utils import carregar_css # <-- Importando o CSS

st.set_page_config(page_title="Anadiana Semijoias", page_icon="💎", layout="wide")

# Aplica o tema (cores e fontes)
carregar_css()

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
    # --- BARRA LATERAL ---
    with st.sidebar:
        # Logo no topo da Sidebar
        try:
            st.image("logo.png", use_column_width=True)
        except:
            st.markdown("<h2 style='text-align: center; font-size: 2rem;'>ANADIANA</h2>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Informações do usuário
        st.markdown(f"👤 **{st.session_state['usuario_logado']}**")
        st.caption(f"Cargo: {st.session_state['cargo']}")
        
        st.markdown("---")

        opcoes = [
            "🏠 Início",
            "🎯 Painel",
            "⚙️ Parâmetros",
            "📦 Produtos",
            "🛒 Compras",
            "💰 Vendas",
            "💳 Recebimentos",
            "🧾 Despesas",
            "🤝 Sócios",
            "🔄 Ajustes",
            "💵 Caixa",
            "📊 DRE",
        ]
        if st.session_state.get("cargo") == "Administrador":
            opcoes.append("👥 Usuários")

        menu = st.sidebar.radio("Navegação", opcoes)
        
        st.write("")
        
        # Botão Sair
        if st.button("Sair do Sistema", use_container_width=True):
            for k in ["logged_in", "usuario_logado", "usuario_id", "cargo"]:
                st.session_state[k] = None
            st.session_state["logged_in"] = False
            st.rerun()

    # --- ROTEAMENTO DAS PÁGINAS ---
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
        - 🔄 **Ajustes** ✅
        - 💵 **Caixa** ✅
        - 📊 **DRE** ✅
        - 🎯 **Painel** ✅
        """)
    elif menu == "🎯 Painel":
        from modules.painel import tela_painel
        tela_painel()
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
    elif menu == "🔄 Ajustes":
        from modules.ajustes import tela_ajustes
        tela_ajustes()
    elif menu == "💵 Caixa":
        from modules.caixa import tela_caixa
        tela_caixa()
    elif menu == "📊 DRE":
        from modules.dre import tela_dre
        tela_dre()
    elif menu == "👥 Usuários":
        tela_usuarios()
