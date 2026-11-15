import streamlit as st
from modules.auth import tela_login, criar_usuarios_iniciais
from modules.config import tela_config
from modules.usuarios import tela_usuarios

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
    # Menu lateral
    st.sidebar.title(f"Olá, {st.session_state['usuario_logado']}!")
    st.sidebar.write(f"Cargo: {st.session_state['cargo']}")

    opcoes = ["🏠 Início", "⚙️ Parâmetros"]
    if st.session_state.get("cargo") == "Administrador":
        opcoes.append("👥 Usuários")

    # Módulos futuros (descomente conforme for criando):
    # opcoes += ["📦 Produtos", "🛒 Compras", "💰 Vendas", "💳 Recebimentos",
    #            "🧾 Despesas", "🤝 Sócios", "🔄 Ajustes"]

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
        st.info("Use o menu lateral para navegar entre os módulos. "
                "Comece por **Parâmetros** para configurar taxas, margem e o mês de análise.")
        st.subheader("Módulos planejados")
        st.markdown("""
        - ⚙️ **Parâmetros** ✅ (disponível)
        - 👥 **Usuários** ✅ (disponível para Admin)
        - 📦 **Produtos** (próximo)
        - 🛒 **Compras**
        - 💰 **Vendas** + Itens
        - 💳 **Recebimentos**
        - 🧾 **Despesas** e 🤝 **Sócios**
        - 🔄 **Ajustes**
        - 📊 **Caixa, DRE e Painel** (calculados)
        """)
    elif menu == "⚙️ Parâmetros":
        tela_config()
    elif menu == "👥 Usuários":
        tela_usuarios()
