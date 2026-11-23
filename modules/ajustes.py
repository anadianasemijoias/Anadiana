import streamlit as st
from datetime import datetime, date
from bson import ObjectId
from modules.utils import get_db, brl


# Tipo -> sinal aplicado ao estoque
TIPOS_AJUSTE = {
    "Perda": -1,
    "Brinde": -1,
    "Devolução de cliente": +1,
    "Troca (saída)": -1,
    "Troca (entrada)": +1,
    "Acerto de inventário (positivo)": +1, # Aqui ele será recalculado se for inventário
    "Acerto de inventário (negativo)": -1,
}


def _apenas_admin_ou_func():
    if st.session_state.get("cargo") not in ("Administrador", "Funcionário"):
        st.warning("Acesso restrito.")
        return False
    return True


def _estoque_disponivel(db, sku):
    """Estoque atual do SKU (compras − vendas + ajustes)."""
    compras = list(db["compras"].aggregate([
        {"$match": {"sku": sku}},
        {"$group": {"_id": None, "qtd": {"$sum": "$quantidade"}}},
    ]))
    vendas = list(db["itens_venda"].aggregate([
        {"$match": {"sku": sku}},
        {"$group": {"_id": None, "qtd": {"$sum": "$quantidade"}}},
    ]))
    ajustes = list(db["ajustes"].aggregate([
        {"$match": {"sku": sku}},
        {"$group": {"_id": None, "qtd": {"$sum": "$quantidade"}}},
    ]))
    qc = compras[0]["qtd"] if compras else 0
    qv = vendas[0]["qtd"] if vendas else 0
    qa = ajustes[0]["qtd"] if ajustes else 0
    return qc - qv + qa


def tela_ajustes():
    st.header("🔄 Ajustes de Estoque")
    st.caption(
        "Perdas, brindes, devoluções, trocas e acertos de inventário. "
        "Ajuste **não mexe em caixa** e **não entra na DRE** — apenas corrige o estoque."
    )

    if not _apenas_admin_ou_func():
        return

    db = get_db()
    col = db["ajustes"]

    produtos = list(db["produtos"].find({"status": "Ativo"}).sort("sku", 1))
    if not produtos:
        st.warning("Cadastre produtos antes de lançar ajustes.")
        return

    mapa_prod = {p["sku"]: p for p in produtos}
    skus = list(mapa_prod.keys())

    # ---------- LISTAGEM ----------
    st.subheader("Ajustes lançados")
    ajustes = list(col.find({}).sort("data_ajuste", -1).limit(300))

    if ajustes:
        linhas = []
        for a in ajustes:
            qtd = a.get("quantidade", 0)
            sinal = "+" if qtd > 0 else ""
            linhas.append({
                "Data": a["data_ajuste"].strftime("%d/%m/%Y") if a.get("data_ajuste") else "",
                "SKU": a["sku"],
                "Produto": a.get("produto_nome", ""),
                "Tipo": a.get("tipo", ""),
                "Qtd (líq.)": f"{sinal}{qtd}",
                "Motivo": a.get("motivo", ""),
                "Lançado por": a.get("criado_por", ""),
            })
        st.dataframe(linhas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum ajuste lançado ainda.")

    st.divider()

    # ---------- CADASTRO ----------
    with st.expander("➕ Lançar novo ajuste", expanded=not ajustes):
        with st.form("novo_ajuste", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                data_ajuste = st.date_input("Data do ajuste *", value=date.today())
                sku = st.selectbox("SKU *", skus)
                estoque_atual = _estoque_disponivel(db, sku)
                st.info(f"Estoque atual do sistema: **{estoque_atual}** peça(s)")
            with col2:
                tipo = st.selectbox("Tipo de ajuste *", list(TIPOS_AJUSTE.keys()))
                
                # Se for inventário, pede a quantidade REAL contada
                if "inventário" in tipo.lower():
                    qtd_contada = st.number_input("Quantidade REAL contada", min_value=0, value=estoque_atual, step=1)
                    # Calcula a diferença silenciosamente
                    quantidade = qtd_contada - estoque_atual
                    st.caption(f"Diferença a ser ajustada: **{quantidade}**")
                else:
                    # Para os outros, pede a quantidade de peças do evento
                    quantidade = st.number_input(
                        "Quantidade * (sempre positiva)",
                        min_value=1, value=1, step=1,
                    )
                    qtd_contada = None
            with col3:
                motivo = st.text_input("Motivo / observações *")

            submit = st.form_submit_button("💾 Lançar ajuste")

            if submit:
                erros = []
                if not motivo:
                    erros.append("Informe o motivo do ajuste.")

                # Se for inventário, a quantidade será a diferença. Se for 0, não faz nada.
                if "inventário" in tipo.lower():
                    qtd_final = quantidade
                    if qtd_final == 0:
                        erros.append("O estoque real é igual ao do sistema. Nenhum ajuste necessário.")
                else:
                    sinal = TIPOS_AJUSTE[tipo]
                    qtd_final = sinal * int(quantidade)
                    if sinal < 0 and (estoque_atual - quantidade) < 0:
                        erros.append(
                            f"Estoque insuficiente: atual {estoque_atual}, "
                            f"tentativa de saída {quantidade}."
                        )

                if erros:
                    for e in erros:
                        st.error(e)
                else:
                    col.insert_one({
                        "data_ajuste": datetime.combine(data_ajuste, datetime.min.time()),
                        "sku": sku,
                        "produto_nome": mapa_prod[sku]["nome"],
                        "tipo": tipo,
                        "quantidade": qtd_final,
                        "motivo": motivo,
                        "criado_em": datetime.now(),
                        "criado_por": st.session_state.get("usuario_logado"),
                    })
                    st.success(f"Ajuste lançado com sucesso no SKU **{sku}**!")
                    st.rerun()

    st.divider()

    # ---------- EDIÇÃO (Mantida igual, mas com ajuste para inventário) ----------
    st.subheader("✏️ Editar ajuste")
    if not ajustes:
        st.info("Nenhum ajuste para editar.")
        return

    opcoes = {}
    for a in ajustes:
        label = (
            f"{a['data_ajuste'].strftime('%d/%m/%Y') if a.get('data_ajuste') else '—'} · "
            f"{a['sku']} · {a.get('tipo','')} · {a.get('quantidade',0)}"
        )
        opcoes[label] = a

    escolha = st.selectbox("Selecione o ajuste", list(opcoes.keys()))
    a = opcoes[escolha]
    ajuste_id = str(a["_id"])

    with st.form("editar_ajuste"):
        col1, col2, col3 = st.columns(3)
        with col1:
            nova_data = st.date_input(
                "Data",
                value=a["data_ajuste"].date() if a.get("data_ajuste") else date.today(),
            )
            novo_sku = st.selectbox(
                "SKU", skus,
                index=skus.index(a["sku"]) if a["sku"] in skus else 0,
            )
        with col2:
            idx_tipo = list(TIPOS_AJUSTE.keys()).index(a["tipo"]) if a.get("tipo") in TIPOS_AJUSTE else 0
            novo_tipo = st.selectbox("Tipo", list(TIPOS_AJUSTE.keys()), index=idx_tipo)
            nova_qtd = st.number_input(
                "Quantidade (se negativo, será subtraído)", 
                value=int(a.get("quantidade", 1)), step=1,
            )
        with col3:
            novo_motivo = st.text_input("Motivo", value=a.get("motivo", ""))

        salvar = st.form_submit_button("💾 Salvar alterações")

        if salvar:
            db["ajustes"].update_one(
                {"_id": ObjectId(ajuste_id)},
                {"$set": {
                    "data_ajuste": datetime.combine(nova_data, datetime.min.time()),
                    "sku": novo_sku,
                    "produto_nome": mapa_prod[novo_sku]["nome"],
                    "tipo": novo_tipo,
                    "quantidade": int(nova_qtd), # Na edição, aceita o valor exato
                    "motivo": novo_motivo,
                    "atualizado_em": datetime.now(),
                    "atualizado_por": st.session_state.get("usuario_logado"),
                }},
            )
            st.success("Ajuste atualizado!")
            st.rerun()

    st.divider()

    # ---------- EXCLUIR ----------
    st.subheader("🗑️ Excluir ajuste")
    if st.button("Excluir ajuste selecionado"):
        col.delete_one({"_id": a["_id"]})
        st.success("Ajuste excluído.")
        st.rerun()

    st.divider()

    # ---------- RESUMO ----------
    st.subheader("📊 Resumo por tipo")
    if ajustes:
        contagem = {}
        for a in ajustes:
            t = a.get("tipo", "—")
            contagem.setdefault(t, {"ocorrencias": 0, "qtd_liquida": 0})
            contagem[t]["ocorrencias"] += 1
            contagem[t]["qtd_liquida"] += a.get("quantidade", 0)

        linhas = []
        for t, v in contagem.items():
            linhas.append({
                "Tipo": t,
                "Ocorrências": v["ocorrencias"],
                "Qtd líquida": v["qtd_liquida"],
            })
        st.dataframe(linhas, use_container_width=True, hide_index=True)
