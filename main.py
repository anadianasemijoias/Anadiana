import streamlit as st
import pymongo
from passlib.hash import bcrypt
import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Anadiana Semijoias", page_icon="💎", layout="centered")

# --- CONEXÃO COM O BANCO (MongoDB) ---
@st.cache_resource
def init_connection():
    uri = st.secrets["mongo"]["uri"]
    return pymongo.MongoClient(uri)

try:
    client = init_connection()
    db = client[st.secrets["mongo"]["db_name"]]
    usuarios_col = db["usuarios"]
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados. Verifique as credenciais. Detalhes: {e}")
    st.stop()

# --- FUNÇÕES AUXILIARES ---
def hash_senha(senha):
    return bcrypt.hash(senha)

def verificar_senha(senha_digitada, senha_hash):
    return bcrypt.verify(senha_digitada, senha_hash)

def criar_usuarios_iniciais():
    """Cria os usuários padrão se o banco estiver vazio."""
    if usuarios_col.count_documents({}) == 0:
        usuarios_iniciais = [
            {"nome": "Diego Roberto", "usuario": "diego", "senha": hash_senha("admin123"), "cargo": "Administrador", "ativo": True},
            {"nome": "Kellen", "usuario": "kellen", "senha": hash_senha("kellen123"), "cargo": "Funcionário", "ativo": True}
        ]
        usuarios_col.insert_many(usuarios_iniciais)
        st.toast("Usuários iniciais criados! (diego/admin123 e kellen/kellen123)", icon="✅")

criar_usuarios_iniciais()

# --- INTERFACE DE LOGIN ---
def tela_login():
    st.title("💎 Anadiana Semijoias")
    st.subheader("Acesso ao Sistema")
    
    with st.form("login_form"):
        usuario_input = st.text_input("Usuário").strip().lower()
        senha_input = st.text_input("Senha", type="password")
        botao_login = st.form_submit_button("Entrar")
        
        if botao_login:
            user = usuarios_col.find_one({"usuario": usuario_input})
            
            if user and user.get("ativo", False):
                if verificar_senha(senha_input, user["senha"]):
                    st.session_state["logged_in"] = True
                    st.session_state["usuario_logado"] = user["nome"]
                    st.session_state["cargo"] = user["cargo"]
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
            else:
                st.error("Usuário não encontrado ou inativo.")

# --- APLICAÇÃO PRINCIPAL (Após o Login) ---
def app_principal():
    st.sidebar.title(f"Olá, {st.session_state['usuario_logado']}!")
    st.sidebar.write(f"Cargo: {st.session_state['cargo']}")
    
    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.session_state["usuario_logado"] = None
        st.session_state["cargo"] = None
        st.rerun()
        
    st.title("Painel Principal")
    st.write("Bem-vindo ao sistema de gestão da Anadiana Semijoias.")
    st.info("Aqui começaremos a construir as abas do seu Excel (Produtos, Compras, Vendas, etc).")
    
    # Exemplo de como verificar se é admin
    if st.session_state["cargo"] == "Administrador":
        st.success("Você tem acesso total de Administrador.")
    else:
        st.warning("Você tem acesso limitado de Funcionário.")

# --- CONTROLE DE FLUXO ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if st.session_state["logged_in"]:
    app_principal()
else:
    tela_login()
