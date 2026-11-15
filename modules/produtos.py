import streamlit as st
from modules.utils import get_db, brl, pct
from modules.config import carregar_parametros
from bson import ObjectId


CATEGORIAS_PADRAO = [
    "Brinco", "Colar", "Conjunto", "Anel", "Pulseira",
    "Tornozeleira", "Piercing", "Kit", "Outro",
]


def _apenas_admin_ou_func():
    if st.session_state.get("cargo") not in ("Administrador", "Funcionário"):
        st.warning("Acesso restrito.")
        return False
    return True


def _calcular_agregados(db):
    """Monta um dicionário SKU -> dados agregados de compras/vendas/ajustes."""
    agregados = {}

    # Compras (qtd e custo total)
    for c in db["compras"].aggregate([
        {"$group": {
            "_id": "$sku",
            "qtd": {"$sum": "$quantidade"},
            "custo_total": {"$sum": "$valor_total"},
        }}
    ]):
        agregados.setdefault(c["_id"], {})["qtd_comprada"] = c["qtd"]
        agregados.setdefault(c["_id"], {})["custo_total"] = c["custo_total"]

    # Vendas (qtd vendida)
    for v in db["itens_venda"].aggregate([
        {"$group": {"_id": "$sku", "qtd": {"$sum": "$quantidade"}}}
    ]):
        agregados.setdefault(v["_id"], {})["qtd_vendida"] = v["qtd"]

    # Ajustes (líquido)
    for a in db["ajustes"].aggregate([
        {"$group": {"_id": "$sku", "qtd": {"$sum": "$quantidade"}}}
    ]):
        agregados.setdefault(a["_id"], {})["ajustes"] = a["qtd"]

    return agregados


def _taxa_media_pagamento(parametros):
    taxas = parametros.get("taxas_pagamento", {})
    if not taxas:
        return 0.0
    return sum(taxas.values()) / len(taxas)


def _precos_sugeridos(custo, parametros):
    """Retorna (preco_minimo, preco_sugerido) ou (None, None) se custo inválido."""
    if not custo or custo <= 0:
        return None, None

    emb = float(parametros.get("custo_embalagem", 0))
    imp = float(parametros.get("aliquota_imposto", 0))
    marg = float(parametros.get("margem_desejada", 0))
    taxa = _taxa_media_pagamento(parametros)

    denom_min = 1 - imp - marg
    denom_sug = 1 - imp - marg - taxa

    preco_min = (custo + emb) / denom_min if denom_min > 0 else None
    preco_sug = (custo + emb) / denom_sug if denom_sug > 0 else None
    return preco_min, preco_sug


def _alerta(estoque, estoque_min):
    if estoque < 0:
        return "Revisar estoque"
    if estoque == 0:
        return "Esgotado"
    if estoque <= estoque_min:
        return "Repor"
    return "OK"


def tela_produtos():
    st.header("📦 Produtos e Estoque")

    if not _apenas_admin_ou_func():
        return

    db = get_db()
    col = db["produtos"]
    parametros = carregar_parametros()
    agregados = _calcular_agregados(db)

    # ---------- LISTAGEM ----------
    st.subheader("Produtos cadastrados")
    produtos = list(col.find({}).sort("sku", 1))

    if produtos:
        linhas = []
        for p in produtos:
            agg = agregados.get(p["sku"], {})
            qtd_comprada = agg.get("qtd_comprada", 0)
            custo_total = agg.get("custo_total", 0)
            qtd_vendida = agg.get("qtd_vendida", 0)
            ajustes = agg.get("ajustes", 0)

            custo_medio = (custo_total / qtd_comprada) if qtd_comprada > 0 else 0
            estoque = qtd_comprada - qtd_vendida + ajustes
            estoque_min = int(p.get("estoque_minimo", 0))
            preco = float(p.get("preco_venda", 0))

            markup = (preco - custo_medio) / custo_medio if custo_medio > 0 else 0
            margem = (preco - custo_medio) / preco if preco > 0 else 0
            estoque_custo = estoque * custo_medio
            preco_min, preco_sug = _precos_sugeridos(custo_medio, parametros)
            alerta = _alerta(estoque, estoque_min)

            linhas.append({
                "SKU": p["sku"],
                "Nome": p["nome"],
                "Categoria": p.get("categoria", ""),
                "Fornecedor": p.get("fornecedor", ""),
                "Qtd comprada": qtd_comprada,
                "Custo médio": brl(custo_medio),
                "Qtd vendida": qtd_vendida,
                "Ajustes": ajustes,
                "Estoque": estoque,
                "Mín.": estoque_min,
                "Alerta": alerta,
                "Estoque a custo": brl(estoque_custo),
                "Preço venda": brl(preco),
                "Markup": pct(markup),
                "Margem": pct(margem),
                "Preço mínimo": brl(preco_min) if preco_min else "—",
                "Preço sugerido": brl(preco_sug) if preco_sug else "—",
                "Status": p.get("status", "Ativo"),
            })
        st.dataframe(linhas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum produto cadastrado ainda. Use o formulário abaixo para começar.")

    st.divider()

    # ---------- CADASTRO ----------
    with st.expander("➕ Cadastrar novo produto", expanded=not produtos):
        with st.form("novo_produto"):
            col1, col2 = st.columns(2)
            with col1:
                sku = st.text_input("SKU / código *").strip().upper()
                nome = st.text_input("Nome do produto *")
                categoria = st.selectbox("Categoria", CATEGORIAS_PADRAO)
            with col2:
                fornecedor = st.text_input("Fornecedor")
                estoque_min = st.number_input("Estoque mínimo", min_value=0, value=0, step=1)
                preco_venda = st.number_input(
                    "Preço de venda (R$)", min_value=0.0, value=0.0,
                    step=0.5, format="%.2f",
                )

            submit = st.form_submit_button("Cadastrar produto")

            if submit:
                if not sku or not nome:
                    st.error("SKU e Nome são obrigatórios.")
                elif col.find_one({"sku": sku}):
                    st.error("Já existe um produto com este SKU.")
                else:
                    col.insert_one({
                        "sku": sku,
                        "nome": nome,
                        "categoria": categoria,
                        "fornecedor": fornecedor,
                        "estoque_minimo": int(estoque_min),
                        "preco_venda": float(preco_venda),
                        "status": "Ativo",
                    })
                    st.success(f"Produto **{sku}** cadastrado!")
                    st.rerun()

    st.divider()

    # ---------- EDIÇÃO ----------
    st.subheader("✏️ Editar produto")
    if not produtos:
        st.info("Nenhum produto para editar.")
        return

    opcoes = {f"{p['sku']} — {p['nome']}": p for p in produtos}
    escolha = st.selectbox("Selecione o produto", list(opcoes.keys()))
    p = opcoes[escolha]
    prod_id = str(p["_id"])

    with st.form("editar_produto"):
        col1, col2 = st.columns(2)
        with col1:
            novo_nome = st.text_input("Nome", value=p["nome"])
            nova_cat = st.selectbox(
                "Categoria", CATEGORIAS_PADRAO,
                index=CATEGORIAS_PADRAO.index(p.get("categoria", "Outro"))
                if p.get("categoria") in CATEGORIAS_PADRAO else 0,
            )
            novo_forn = st.text_input("Fornecedor", value=p.get("fornecedor", ""))
        with col2:
            novo_min = st.number_input(
                "Estoque mínimo", min_value=0,
                value=int(p.get("estoque_minimo", 0)), step=1,
            )
            novo_preco = st.number_input(
                "Preço de venda (R$)", min_value=0.0,
                value=float(p.get("preco_venda", 0.0)),
                step=0.5, format="%.2f",
            )
            novo_status = st.selectbox(
                "Status", ["Ativo", "Inativo"],
                index=0 if p.get("status", "Ativo") == "Ativo" else 1,
            )

        salvar = st.form_submit_button("💾 Salvar alterações")

        if salvar:
            col.update_one(
                {"_id": ObjectId(prod_id)},
                {"$set": {
                    "nome": novo_nome,
                    "categoria": nova_cat,
                    "fornecedor": novo_forn,
                    "estoque_minimo": int(novo_min),
                    "preco_venda": float(novo_preco),
                    "status": novo_status,
                }},
            )
            st.success("Produto atualizado!")
            st.rerun()

    st.caption(
        "💡 O **custo médio**, **estoque**, **markup**, **margem** e **preços mínimo/sugerido** "
        "são calculados automaticamente a partir de Compras, Itens de Venda e Ajustes. "
        "Para excluir um produto, prefira deixá-lo **Inativo**."
    )
