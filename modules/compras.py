import streamlit as st
from datetime import datetime, date
from bson import ObjectId
from modules.utils import get_db, brl

FORMAS_PAGAMENTO_COMPRA = [
    "Pix", "Dinheiro", "Boleto", "Cartão de Débito",
    "Cartão de Crédito", "Transferência", "Outro",
]


def _apenas_admin_ou_func():
    if st.session_state.get("cargo") not in ("Administrador", "Funcionário"):
        st.warning("Acesso restrito.")
        return False
    return True


def _situacao(vencimento, data_pagamento):
    """Retorna Pago / Vencida / Pendente."""
    if data_pagamento:
        return "Pago"
    if vencimento and vencimento < date.today():
        return "Vencida"
    return "Pendente"


def _listar_skus(db):
    """Retorna lista de SKUs cadastrados (para o selectbox)."""
    return [p["sku"] for p in db["produtos"].find({}, {"sku": 1}).sort("sku", 1)]


def tela_compras():
    st.header("🛒 Compras de Mercadorias")
    st.caption(
        "Uma linha por produto comprado. Compras de embalagens e materiais "
        "NÃO entram aqui: lance em Despesas. Frete e desconto: informe na linha do produto."
    )

    if not _apenas_admin_ou_func():
        return

    db = get_db()
    col = db["compras"]
    skus = _listar_skus(db)

    if not skus:
        st.warning("Nenhum produto cadastrado. Cadastre produtos antes de lançar compras.")
        return

    # ---------- LISTAGEM ----------
    st.subheader("Compras lançadas")
    compras = list(col.find({}).sort("data_compra", -1).limit(200))

    if compras:
        linhas = []
        for c in compras:
            linhas.append({
                "Data": c["data_compra"].strftime("%d/%m/%Y") if c.get("data_compra") else "",
                "Fornecedor": c.get("fornecedor", ""),
                "NF": c.get("documento", ""),
                "SKU": c["sku"],
                "Produto": c.get("produto_nome", ""),
                "Qtd": c.get("quantidade", 0),
                "Valor unit.": brl(c.get("valor_unitario", 0)),
                "Frete": brl(c.get("frete", 0)),
                "Desconto": brl(c.get("desconto", 0)),
                "Total": brl(c.get("valor_total", 0)),
                "Pagamento": c.get("forma_pagamento", ""),
                "Vencimento": c["vencimento"].strftime("%d/%m/%Y") if c.get("vencimento") else "",
                "Pago em": c["data_pagamento"].strftime("%d/%m/%Y") if c.get("data_pagamento") else "",
                "Situação": c.get("situacao", ""),
                "Obs.": c.get("observacoes", ""),
            })
        st.dataframe(linhas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma compra lançada ainda. Use o formulário abaixo.")

    st.divider()

    # ---------- CADASTRO ----------
    with st.expander("➕ Lançar nova compra", expanded=not compras):
        with st.form("nova_compra", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                data_compra = st.date_input("Data da compra *", value=date.today())
                fornecedor = st.text_input("Fornecedor *")
                documento = st.text_input("Documento / NF")
            with col2:
                sku = st.selectbox("SKU *", skus)
                quantidade = st.number_input("Quantidade *", min_value=1, value=1, step=1)
                valor_unit = st.number_input(
                    "Valor unitário (R$) *", min_value=0.0, value=0.0,
                    step=0.5, format="%.2f",
                )
            with col3:
                frete = st.number_input(
                    "Frete da compra (R$)", min_value=0.0, value=0.0,
                    step=0.5, format="%.2f",
                )
                desconto = st.number_input(
                    "Desconto obtido (R$)", min_value=0.0, value=0.0,
                    step=0.5, format="%.2f",
                )
                forma_pag = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO_COMPRA)

            col4, col5 = st.columns(2)
            with col4:
                vencimento = st.date_input("Vencimento", value=None)
            with col5:
                data_pagamento = st.date_input("Data do pagamento (se já pago)", value=None)

            observacoes = st.text_area("Observações", height=60)

            submit = st.form_submit_button("💾 Lançar compra")

            if submit:
                erros = []
                if not fornecedor:
                    erros.append("Informe o fornecedor.")
                if not sku:
                    erros.append("Selecione o SKU.")
                if quantidade <= 0:
                    erros.append("Quantidade deve ser maior que zero.")
                if valor_unit <= 0:
                    erros.append("Valor unitário deve ser maior que zero.")

                if erros:
                    for e in erros:
                        st.error(e)
                else:
                    produto = db["produtos"].find_one({"sku": sku})
                    valor_total = (quantidade * valor_unit) + frete - desconto
                    situacao = _situacao(vencimento, data_pagamento)

                    col.insert_one({
                        "data_compra": datetime.combine(data_compra, datetime.min.time()),
                        "fornecedor": fornecedor,
                        "documento": documento,
                        "sku": sku,
                        "produto_nome": produto["nome"] if produto else "",
                        "quantidade": int(quantidade),
                        "valor_unitario": float(valor_unit),
                        "frete": float(frete),
                        "desconto": float(desconto),
                        "valor_total": float(valor_total),
                        "forma_pagamento": forma_pag,
                        "vencimento": datetime.combine(vencimento, datetime.min.time()) if vencimento else None,
                        "data_pagamento": datetime.combine(data_pagamento, datetime.min.time()) if data_pagamento else None,
                        "situacao": situacao,
                        "observacoes": observacoes,
                        "criado_em": datetime.now(),
                        "criado_por": st.session_state.get("usuario_logado"),
                    })
                    st.success(
                        f"Compra lançada: {quantidade} × {sku} — total {brl(valor_total)}."
                    )
                    st.rerun()

    st.divider()

    # ---------- EDIÇÃO ----------
    st.subheader("✏️ Editar compra")
    if not compras:
        st.info("Nenhuma compra para editar.")
        return

    opcoes = {}
    for c in compras:
        label = (
            f"{c['data_compra'].strftime('%d/%m/%Y') if c.get('data_compra') else '—'} · "
            f"{c['sku']} · {c.get('fornecedor','')} · {brl(c.get('valor_total',0))}"
        )
        opcoes[label] = c

    escolha = st.selectbox("Selecione a compra", list(opcoes.keys()))
    c = opcoes[escolha]
    compra_id = str(c["_id"])

    with st.form("editar_compra"):
        col1, col2, col3 = st.columns(3)
        with col1:
            nova_data = st.date_input(
                "Data da compra",
                value=c["data_compra"].date() if c.get("data_compra") else date.today(),
            )
            novo_forn = st.text_input("Fornecedor", value=c.get("fornecedor", ""))
            novo_doc = st.text_input("Documento / NF", value=c.get("documento", ""))
        with col2:
            novo_sku = st.selectbox(
                "SKU", skus,
                index=skus.index(c["sku"]) if c["sku"] in skus else 0,
            )
            nova_qtd = st.number_input(
                "Quantidade", min_value=1,
                value=int(c.get("quantidade", 1)), step=1,
            )
            novo_valor = st.number_input(
                "Valor unitário (R$)", min_value=0.0,
                value=float(c.get("valor_unitario", 0.0)),
                step=0.5, format="%.2f",
            )
        with col3:
            novo_frete = st.number_input(
                "Frete (R$)", min_value=0.0,
                value=float(c.get("frete", 0.0)), step=0.5, format="%.2f",
            )
            novo_desc = st.number_input(
                "Desconto (R$)", min_value=0.0,
                value=float(c.get("desconto", 0.0)), step=0.5, format="%.2f",
            )
            idx_forma = (
                FORMAS_PAGAMENTO_COMPRA.index(c["forma_pagamento"])
                if c.get("forma_pagamento") in FORMAS_PAGAMENTO_COMPRA else 0
            )
            nova_forma = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO_COMPRA, index=idx_forma)

        col4, col5 = st.columns(2)
        with col4:
            novo_venc = st.date_input(
                "Vencimento",
                value=c["vencimento"].date() if c.get("vencimento") else None,
            )
        with col5:
            nova_pag = st.date_input(
                "Data do pagamento",
                value=c["data_pagamento"].date() if c.get("data_pagamento") else None,
            )

        nova_obs = st.text_area("Observações", value=c.get("observacoes", ""), height=60)

        salvar = st.form_submit_button("💾 Salvar alterações")

        if salvar:
            novo_total = (nova_qtd * novo_valor) + novo_frete - novo_desc
            nova_situacao = _situacao(novo_venc, nova_pag)
            produto = db["produtos"].find_one({"sku": novo_sku})

            col.update_one(
                {"_id": ObjectId(compra_id)},
                {"$set": {
                    "data_compra": datetime.combine(nova_data, datetime.min.time()),
                    "fornecedor": novo_forn,
                    "documento": novo_doc,
                    "sku": novo_sku,
                    "produto_nome": produto["nome"] if produto else "",
                    "quantidade": int(nova_qtd),
                    "valor_unitario": float(novo_valor),
                    "frete": float(novo_frete),
                    "desconto": float(novo_desc),
                    "valor_total": float(novo_total),
                    "forma_pagamento": nova_forma,
                    "vencimento": datetime.combine(novo_venc, datetime.min.time()) if novo_venc else None,
                    "data_pagamento": datetime.combine(nova_pag, datetime.min.time()) if nova_pag else None,
                    "situacao": nova_situacao,
                    "observacoes": nova_obs,
                    "atualizado_em": datetime.now(),
                    "atualizado_por": st.session_state.get("usuario_logado"),
                }},
            )
            st.success("Compra atualizada!")
            st.rerun()

    st.divider()

    # ---------- RESUMO DO PERÍODO ----------
    st.subheader("📊 Resumo das compras")
    total = sum(c.get("valor_total", 0) for c in compras)
    pagas = sum(c.get("valor_total", 0) for c in compras if c.get("situacao") == "Pago")
    pendentes = sum(c.get("valor_total", 0) for c in compras if c.get("situacao") == "Pendente")
    vencidas = sum(c.get("valor_total", 0) for c in compras if c.get("situacao") == "Vencida")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total lançado", brl(total))
    col2.metric("Pago", brl(pagas))
    col3.metric("Pendente", brl(pendentes))
    col4.metric("Vencido", brl(vencidas))

    st.caption(
        "💡 O **frete** e o **desconto** entram no cálculo do valor total e do custo médio do produto. "
        "A **situação** é recalculada automaticamente (Pago / Vencida / Pendente) ao salvar."
    )
