import streamlit as st
import pymongo
from passlib.hash import bcrypt
import datetime
import pandas as pd

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
    """Garante que o Admin principal sempre exista."""
    if not usuarios_col.find_one({"usuario": "diego"}):
        usuarios_col.insert_one({
            "nome": "Diego Roberto", "usuario": "diego", 
            "senha": hash_senha("Diana@164707"), "cargo": "Administrador", "ativo": True
        })
criar_usuarios_iniciais()

# --- MÓDULOS DO SISTEMA ---

def pagina_parametros():
    st.title("⚙️ Parâmetros do Sistema")
    st.write("Defina as regras de negócio, taxas e custos iniciais.")
    
    params = parametros_col.find_one({"_id": "config_geral"}) or {}

    with st.form("form_parametros"):
        col1, col2 = st.columns(2)
        with col1:
            taxa = st.number_input("Taxa de Pagamento Padrão (%)", value=float(params.get("taxa_padrao", 0.0)), step=0.1) / 100
            custo_emb = st.number_input("Custo de Embalagem por Venda (R$)", value=float(params.get("custo_embalagem", 0.0)), step=0.5)
            imposto = st.number_input("Imposto Estimado (%)", value=float(params.get("imposto", 0.0)), step=0.1) / 100
        with col2:
            margem = st.number_input("Margem de Lucro Desejada (%)", value=float(params.get("margem_desejada", 0.0)), step=1.0) / 100
            saldo_inicial = st.number_input("Saldo Inicial de Caixa (R$)", value=float(params.get("saldo_inicial_caixa", 0.0)), step=100.0)
            
        if st.form_submit_button("Salvar Parâmetros"):
            parametros_col.update_one(
                {"_id": "config_geral"},
                {"$set": {"taxa_padrao": taxa, "custo_embalagem": custo_emb, "imposto": imposto, "margem_desejada": margem, "saldo_inicial_caixa": saldo_inicial}},
                upsert=True
            )
            st.success("Parâmetros salvos com sucesso!")

def pagina_usuarios():
    st.title("👥 Gestão de Usuários")
    
    tab1, tab2 = st.tabs(["Listar e Editar", "Novo Usuário"])

    # ABA 1: Listar e Editar
    with tab1:
        usuarios = list(usuarios_col.find({}, {"senha": 0})) # Não traz a senha para a tela
        if not usuarios:
            st.info("Nenhum usuário cadastrado.")
        else:
            df = pd.DataFrame(usuarios)
            df = df[["nome", "usuario", "cargo", "ativo", "_id"]]
            
            st.dataframe(df[["nome", "usuario", "cargo", "ativo"]], use_container_width=True, hide_index=True)
            
            st.divider()
            st.subheader("Editar Usuário ou Resetar Senha")
            
            # Seletor de usuário para editar
            usuario_selecionado = st.selectbox("Selecione o usuário", [u["usuario"] for u in usuarios])
            
            if usuario_selecionado:
                user_data = usuarios_col.find_one({"usuario": usuario_selecionado})
                
                with st.form("form_editar_usuario"):
                    novo_nome = st.text_input("Nome Completo", value=user_data.get("nome", ""))
                    novo_cargo = st.selectbox("Cargo", ["Administrador", "Funcionário"], index=0 if user_data.get("cargo") == "Administrador" else 1)
                    novo_status = st.checkbox("Usuário Ativo", value=user_data.get("ativo", True))
                    
                    st.write("Deixe a senha em branco se não quiser alterá-la.")
                    nova_senha = st.text_input("Nova Senha (opcional)", type="password")
                    
                    if st.form_submit_button("Atualizar Dados"):
                        update_data = {"nome": novo_nome, "cargo": novo_cargo, "ativo": novo_status}
                        if nova_senha.strip() != "":
                            update_data["senha"] = hash_senha(nova_senha)
                            
                        usuarios_col.update_one({"usuario": usuario_selecionado}, {"$set": update_data})
                        st.success(f"Usuário {usuario_selecionado} atualizado com sucesso!")
                        st.rerun()

    # ABA 2: Novo Usuário
    with tab2:
        with st.form("form_novo_usuario"):
            st.subheader("Cadastrar Novo Funcionário")
            novo_user_nome = st.text_input("Nome Completo")
            novo_user_login = st.text_input("Usuário de Acesso (ex: joao)").strip().lower()
            novo_user_senha = st.text_input("Senha Inicial", type="password")
            novo_user_cargo = st.selectbox("Cargo", ["Funcionário", "Administrador"])
            
            if st.form_submit_button("Criar Usuário"):
                if not novo_user_nome or not novo_user_login or not novo_user_senha:
                    st.error("Preencha todos os campos obrigatórios.")
                elif usuarios_col.find_one({"usuario": novo_user_login}):
                    st.error("Este nome de usuário já existe.")
                else:
                    usuarios_col.insert_one({
                        "nome": novo_user_nome,
                        "usuario": novo_user_login,
                        "senha": hash_senha(novo_user_senha),
                        "cargo": novo_user_cargo,
                        "ativo": True
                    })
                    st.success(f"Usuário {novo_user_login} criado com sucesso!")

def app_principal():
    st.sidebar.title(f"Olá, {st.session_state['usuario_logado']}!")
    st.sidebar.write(f"Cargo: {st.session_state['cargo']}")
    st.sidebar.divider()
    
    # Monta o menu baseado no cargo
    opcoes_menu = ["Painel", "Parâmetros", "Produtos", "Compras", "Vendas"]
    
    # Apenas Administradores veem a aba de Usuários
    if st.session_state["cargo"] == "Administrador":
        opcoes_menu.append("Usuários")
        
    menu = st.sidebar.radio("Navegação", opcoes_menu)
    
    st.sidebar.divider()
    if st.sidebar.button("Sair"):
        st.session_state["logged_in"] = False
        st.rerun()
        
    # Roteamento de Páginas
    if menu == "Painel":
        st.title("Painel Principal")
        st.write("Bem-vindo ao sistema de gestão da Anadiana Semijoias.")
    elif menu == "Parâmetros":
        pagina_parametros()
    elif menu == "Usuários":
        pagina_usuarios()
    elif menu in ["Produtos", "Compras", "Vendas"]:
        st.title(f"Módulo de {menu}")
        st.info("Em breve...")

# --- INTERFACE DE LOGIN ---
def tela_login():
    st.title("💎 Anadiana Semijoias")
    st.subheader("Acesso ao Sistema")
    with st.form("login_form"):
        usuario_input = st.text_input("Usuário").strip().lower()
        senha_input = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
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
