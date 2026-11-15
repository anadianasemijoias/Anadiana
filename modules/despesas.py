import streamlit as st
from datetime import datetime, date
from bson import ObjectId
from modules.utils import get_db, brl


CATEGORIAS_DESPESA = [
    "Plataforma (wbuy)",
    "Hospedagem / Domínio",
    "Marketing / Anúncios",
    "Embalagens",
    "Impostos / Taxas (guia paga)",
    "Frete (envio de vendas)",
    "Software / Ferramentas",
    "Serviços (contador, designer, etc.)",
    "Material de escritório",
    "Manutenção / Equipamentos",
    "Outras despesas",
]

FORMAS_PAGAMENTO_DESPESA = [
    "Pix", "Dinheiro", "Boleto", "Cartão de Débito",
    "Cartão de Crédito", "Transferência", "Outro",
]


def _apenas_admin_ou_func():
    if st.session_state.get("cargo") not in ("Administrador", "Funcionário"):
        st.warning("Acesso restrito.")
        return False
    return True


def _situacao(vencimento, data_pagamento):
    if data_pagamento:
        return "Paga"
    if vencimento and vencimento < date.today():
        return "Vencida"
    return "Pendente"


def tela_despesas():
    st.header("🧾 Despesas")
    st.caption(
        "Compras de mercadoria **não** entram aqui — vão em **Compras**. "
        "Aqui entram plataforma, hospedagem, marketing, embalagens, impostos pagos, etc."
    )

    if not _apenas_admin_ou_func():
        return

    db = get_db()
    col = db["despesas"]

    # ---------- LISTAGEM ----------
    st.subheader("Despesas lançadas")
    despesas = list(col.find({}).sort("data_despesa", -1).limit(300))

    if despesas:
        linhas = []
        for d in despesas:
            linhas.append({
                "Data": d["data_despesa"].strftime("%d/%m/%Y") if d.get("data_despesa") else "",
                "Categoria": d.get("categoria", ""),
                "Descrição": d.get("descricao", ""),
                "Fornecedor": d.get("fornecedor", ""),
                "Valor": brl(d.get("valor", 0)),
                "Pagamento": d.get("forma_pagamento", ""),
                "Vencimento": d["vencimento"].strftime("%d/%m/%Y") if d.get("vencimento") else "",
                "Pago em": d["data_pagamento"].strftime("%d/%m/%Y") if d.get("data_pagamento") else "",
                "Situação": d.get("situacao", ""),
            })
        st.dataframe(linhas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma despesa lançada ainda.")

    st.divider()

    # ---------- CADASTRO ----------
    with st.expander("➕ Lançar nova despesa", expanded=not despesas):
        with st.form("nova_despesa", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                data_desp = st.date_input("Data da despesa *", value=date.today())
                categoria = st.selectbox("Categoria *", CATEGORIAS_DESPESA)
                descricao = st.text_input("Descrição *")
            with col2:
                fornecedor = st.text_input("Fornecedor")
                valor = st.number_input(
                    "Valor (R$) *", min_value=0.0, value=0.0,
                    step=0.5, format="%.2f",
                )
                forma_pag = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO_DESPESA)
            with col3:
                vencimento = st.date_input("Vencimento", value=None)
                data_pagamento = st.date_input("Data do pagamento (se já paga)", value=None)

            obs = st.text_area("Observações", height=60)

            submit = st.form_submit_button("💾 Lançar despesa")

            if submit:
                erros = []
                if not descricao:
                    erros.append("Informe a descrição.")
                if valor <= 0:
                    erros.append("O valor deve ser maior que zero.")

                if erros:
                    for e in erros:
                        st.error(e)
                else:
                    situacao = _situacao(vencimento, data_pagamento)
                    col.insert_one({
                        "data_despesa": datetime.combine(data_desp, datetime.min.time()),
                        "categoria": categoria,
                        "descricao": descricao,
                        "fornecedor": fornecedor,
                        "valor": float(valor),
                        "forma_pagamento": forma_pag,
                        "vencimento": datetime.combine(vencimento, datetime.min.time()) if vencimento else None,
                        "data_pagamento": datetime.combine(data_pagamento, datetime.min.time()) if data_pagamento else None,
                        "situacao": situacao,
                        "observacoes": obs,
                        "criado_em": datetime.now(),
                        "criado_por": st.session_state.get("usuario_logado"),
                    })
                    st.success(f"Despesa de {brl(valor)} lançada!")
                    st.rerun()

    st.divider()

    # ---------- EDIÇÃO ----------
    st.subheader("✏️ Editar despesa")
    if not despesas:
        st.info("Nenhuma despesa para editar.")
        return

    opcoes = {
        f"{d['data_despesa'].strftime('%d/%m/%Y') if d.get('data_despesa') else '—'} · "
        f"{d.get('categoria','')} · {d.get('descricao','')} · {brl(d.get('valor',0))}": d
        for d in despesas
    }
    escolha = st.selectbox("Selecione a despesa", list(opcoes.keys()))
    d = opcoes[escolha]
    desp_id = str(d["_id"])

    with st.form("editar_despesa"):
        col1, col2, col3 = st.columns(3)
        with col1:
            nova_data = st.date_input(
                "Data",
                value=d["data_despesa"].date() if d.get("data_despesa") else date.today(),
            )
            idx_cat = CATEGORIAS_DESPESA.index(d["categoria"]) if d.get("categoria") in CATEGORIAS_DESPESA else 0
            nova_cat = st.selectbox("Categoria", CATEGORIAS_DESPESA, index=idx_cat)
            nova_desc = st.text_input("Descrição", value=d.get("descricao", ""))
        with col2:
            novo_forn = st.text_input("Fornecedor", value=d.get("fornecedor", ""))
            novo_valor = st.number_input(
                "Valor (R$)", min_value=0.0,
                value=float(d.get("valor", 0.0)), step=0.5, format="%.2f",
            )
            idx_fp = FORMAS_PAGAMENTO_DESPESA.index(d["forma_pagamento"]) if d.get("forma_pagamento") in FORMAS_PAGAMENTO_DESPESA else 0
            nova_fp = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO_DESPESA, index=idx_fp)
        with col3:
            novo_venc = st.date_input(
                "Vencimento",
                value=d["vencimento"].date() if d.get("vencimento") else None,
            )
            nova_pag = st.date_input(
                "Data do pagamento",
                value=d["data_pagamento"].date() if d.get("data_pagamento") else None,
            )

        nova_obs = st.text_area("Observações", value=d.get("observacoes", ""), height=60)

        salvar = st.form_submit_button("💾 Salvar alterações")

        if salvar:
            nova_situacao = _situacao(novo_venc, nova_pag)
            col.update_one(
                {"_id": ObjectId(desp_id)},
                {"$set": {
                    "data_despesa": datetime.combine(nova_data, datetime.min.time()),
                    "categoria": nova_cat,
                    "descricao": nova_desc,
                    "fornecedor": novo_forn,
                    "valor": float(novo_valor),
                    "forma_pagamento": nova_fp,
                    "vencimento": datetime.combine(novo_venc, datetime.min.time()) if novo_venc else None,
                    "data_pagamento": datetime.combine(nova_pag, datetime.min.time()) if nova_pag else None,
                    "situacao": nova_situacao,
                    "observacoes": nova_obs,
                    "atualizado_em": datetime.now(),
                    "atualizado_por": st.session_state.get("usuario_logado"),
                }},
            )
            st.success("Despesa atualizada!")
            st.rerun()

    st.divider()

    # ---------- RESUMO ----------
    st.subheader("📊 Resumo das despesas")
    total = sum(d.get("valor", 0) for d in despesas)
    pagas = sum(d.get("valor", 0) for d in despesas if d.get("situacao") == "Paga")
    pendentes = sum(d.get("valor", 0) for d in despesas if d.get("situacao") == "Pendente")
    vencidas = sum(d.get("valor", 0) for d in despesas if d.get("situacao") == "Vencida")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total lançado", brl(total))
    c2.metric("Pago", brl(pagas))
    c3.metric("Pendente", brl(pendentes))
    c4.metric("Vencido", brl(vencidas))

    st.caption(
        "💡 A **situação** é recalculada automaticamente (Paga / Vencida / Pendente) ao salvar. "
        "A saída de caixa acontece na **data do pagamento**, não na data da despesa."
    )
