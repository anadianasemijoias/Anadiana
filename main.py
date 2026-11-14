import streamlit as st
import pymongo
from passlib.hash import bcrypt
import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Anadiana Semijoias", page_icon="💎", layout="wide")

# --- CONEXÃO COM O BANCO (MongoDB via Secrets) ---
@st.cache_resource
def init_connection():
    uri = st.secrets["mongo"]["uri"]
    return pymongo.MongoClient(uri)

try:
    client = init_connection()
    db = client[st.secrets["mongo"]["db_name"]] 
    usuarios_col = db["usuarios"]
    parametros_col = db["parametros"]
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados. Detalhes: {e}")
    st.stop()

# --- FUNÇÕES AUXILIARES ---
def hash_senha(senha):
    return bcrypt.hash(senha)

def verificar_senha(senha_digitada, senha_hash):
    return bcrypt.verify(senha_digitada, senha_hash)

def criar_usuarios_iniciais():
    """Cria ou ATUALIZA os usuários padrão (Força a atualização da senha)."""
    usuarios_iniciais = [
        {"nome": "Diego Roberto", "usuario": "diego", "senha": hash_senha("Diana@164707"), "cargo": "Administrador", "ativo": True},
        {"nome": "Kellen Santos", "usuario": "kellen", "senha": hash_senha("Diana@164707"), "cargo": "Funcionário", "ativo": True}
    ]
    
    for u in usuarios_iniciais:
        # Se o usuário existe, atualiza a senha e o nome. Se não, cria.
        usuarios_col.update_one(
            {"usuario": u["usuario"]},
            {"$set": u},
            upsert=True
        )
criar_usuarios_iniciais()

# --- MÓDULOS DO SISTEMA ---

def pagina_parametros():
    st.title("⚙️ Parâmetros do Sistema")
    st.write("Defina as regras de negócio, taxas e custos iniciais da Anadiana Semijoias.")
    
    # Busca os parâmetros no banco, se não existirem, usa os padrões
    params = parametros_col.find_one({"_id": "config_geral"}) or {
        "taxa_padrao": 0.0,
        "custo_embalagem": 0.0,
        "imposto": 0.0,
        "margem_desejada": 0.0,
        "saldo_inicial_caixa": 0.0
    }

    with st.form("form_parametros"):
        col1, col2 = st.columns(2)
        
        with col1:
            taxa = st.number_input("Taxa de Pagamento Padrão (%)", value=float(params.get("taxa_padrao", 0.0)), step=0.1) / 100
            custo_emb = st.number_input("Custo de Embalagem por Venda (R$)", value=float(params.get("custo_embalagem", 0.0)), step=0.5)
            imposto = st.number_input("Imposto Estimado (%)", value=float(params.get("imposto", 0.0)), step=0.1) / 100
            
        with col2:
            margem = st.number_input("Margem de Lucro Desejada (%)", value=float(params.get("margem_desejada", 0.0)), step=1.0) / 100
            saldo_inicial = st.number_input("Saldo Inicial de Caixa (R$)", value=float(params.get("saldo_inicial_caixa", 0.0)), step=100.0)
            
        salvar = st.form_submit_button("Salvar Parâmetros")

        if salvar:
            parametros_col.update_one(
                {"_id": "config_geral"},
                {"$set": {
                    "taxa_padrao": taxa,
                    "custo_embalagem": custo_emb,
                    "imposto": imposto,
                    "margem_desejada": margem,
                    "saldo_inicial_caixa": saldo_inicial
                }},
                upsert=True
            )
            st.success("Parâmetros salvos com sucesso!")

def pagina_produtos():
    st.title("📦 Cadastro de Produtos")
    st.info("Em breve: Cadastro de SKUs, estoque e precificação.")

def pagina_compras():
    st.title("🛒 Compras de Mercadorias")
    st.info("Em breve: Entrada de estoque e cálculo de custo médio.")

def pagina_vendas():
    st.title("💰 Vendas")
    st.info("Em breve: Registro de vendas, emissão de parcelas e controle de estoque.")

def app_principal():
    # Menu Lateral
    st.sidebar.title(f"Olá, {st.session_state['usuario_logado']}!")
    st.sidebar.write(f"Cargo: {st.session_state['cargo']}")
    st.sidebar.divider()
    
    # Navegação
    menu = st.sidebar.radio("Navegação", ["Painel", "Parâmetros", "Produtos", "Compras", "Vendas"])
    
    st.sidebar.divider()
    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()
        
    # Roteamento de Páginas
    if menu == "Painel":
        st.title("Painel Principal")
        st.write("Bem-vindo ao sistema de gestão da Anadiana Semijoias.")
        st.info("Selecione um módulo no menu lateral para começar.")
    elif menu == "Parâmetros":
        pagina_parametros()
    elif menu == "Produtos":
        pagina_produtos()
    elif menu == "Compras":
        pagina_compras()
    elif menu == "Vendas":
        pagina_vendas()

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

# --- CONTROLE DE FLUXO ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if st.session_state["logged_in"]:
    app_principal()
else:
    tela_login()
