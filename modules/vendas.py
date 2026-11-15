import streamlit as st
from datetime import datetime, date, timedelta
from bson import ObjectId
from modules.utils import get_db, brl, pct
from modules.config import carregar_parametros


CANAIS = [
    "Presencial (em casa)", "Instagram", "WhatsApp", "Facebook",
    "Loja física", "Indicação", "Outro",
]

FORMAS_PAGAMENTO = [
    "Pix", "Dinheiro", "Cartão de Débito", "Cartão de Crédito (à vista)",
    "Cartão de Crédito (parcelado)", "Crediário (parcelado próprio)",
    "Transferência",
]

STATUS_VENDA = ["Concluída", "Cancelada"]


# ---------- HELPERS ----------

def _proximo_numero_venda(db):
    ultima = db["vendas"].find_one(sort=[("numero_venda", -1)])
    if not ultima:
        return "V0001"
    try:
        n = int(ultima["numero_venda"][1:]) + 1
    except (ValueError, KeyError):
        n = 1
    return f"V{n:04d}"


def _custo_medio_produto(db, sku):
    """Calcula custo médio do SKU a partir das compras (igual à planilha)."""
    resultado = list(db["compras"].aggregate([
        {"$match": {"sku": sku}},
        {"$group": {
            "_id": "$sku",
            "qtd": {"$sum": "$quantidade"},
            "total": {"$sum": "$valor_total"},
        }},
    ]))
    if not resultado or resultado[0]["qtd"] == 0:
        return 0.0
    return resultado[0]["total"] / resultado[0]["qtd"]


def _soma_recebimentos(db, numero_venda):
    resultado = list(db["recebimentos"].aggregate([
        {"$match": {"numero_venda": numero_venda}},
        {"$group": {"_id": None, "total": {"$sum": "$valor"}}},
    ]))
    return resultado[0]["total"] if resultado else 0.0


def _parcelas_vencidas(primeiro_venc, num_parcelas):
    """Quantas parcelas já passaram do vencimento (não pago ainda)."""
    if not primeiro_venc or num_parcelas == 0:
        return 0
    hoje = date.today()
    venc = primeiro_venc.date() if isinstance(primeiro_venc, datetime) else primeiro_venc
    count = 0
    for i in range(num_parcelas):
        try:
            v = venc.replace(month=venc.month + i) if venc.month + i <= 12 else venc
        except ValueError:
            v = venc
        # cálculo simplificado: soma meses
        ano = venc.year + (venc.month - 1 + i) // 12
        mes = (venc.month - 1 + i) % 12 + 1
        v = date(ano, mes, min(venc.day, 28))
        if v < hoje:
            count += 1
    return count


def _recalcular_venda(db, venda_id):
    """Recalcula todos os campos derivados de uma venda e atualiza no banco."""
    venda = db["vendas"].find_one({"_id": ObjectId(venda_id)})
    if not venda:
        return

    params = carregar_parametros()
    num = venda["numero_venda"]

    # Itens
    itens = list(db["itens_venda"].find({"numero_venda": num}))
    valor_itens = sum(i.get("preco_total", 0) for i in itens)
    custo_pecas = sum(
        i.get("custo_unitario", 0) * i.get("quantidade", 0) for i in itens
    )

    total = valor_itens - venda.get("desconto", 0) + venda.get("frete_cobrado", 0)
    entrada = venda.get("entrada", 0)
    num_parcelas = int(venda.get("num_parcelas", 0))
    financiado = max(total - entrada, 0)
    parcela = round(financiado / num_parcelas, 2) if num_parcelas > 0 else 0

    recebido_extra = _soma_recebimentos(db, num)
    saldo = max(total - venda.get("estorno", 0) - entrada - recebido_extra, 0)

    # Embalagem
    embalagem = params.get("custo_embalagem", 0) if itens else 0

    # Taxa
    taxas = params.get("taxas_pagamento", {})
    taxa_pct = taxas.get(venda.get("forma_pagamento", ""), 0)
    taxa_valor = total * taxa_pct

    # Imposto
    imposto = total * params.get("aliquota_imposto", 0)

    # Lucro e margem
    frete_pago = venda.get("frete_pago", 0)
    lucro = total - custo_pecas - embalagem - taxa_valor - imposto - frete_pago
    base_margem = total - custo_pecas
    margem = (lucro / base_margem) if base_margem > 0 else 0

    # Situação
    if venda.get("status") == "Cancelada":
        situacao = "Cancelada"
    elif saldo <= 0.005:
        situacao = "Quitada"
    else:
        pv = _parcelas_vencidas(venda.get("primeiro_vencimento"), num_parcelas)
        situacao = "Atrasada" if pv > 0 else "Em dia"

    pv = _parcelas_vencidas(venda.get("primeiro_vencimento"), num_parcelas)
    em_atraso = min(saldo, parcela * pv) if parcela else 0

    db["vendas"].update_one(
        {"_id": ObjectId(venda_id)},
        {"$set": {
            "valor_itens": valor_itens,
            "total_venda": total,
            "valor_financiado": financiado,
            "valor_parcela": parcela,
            "total_recebido": entrada + recebido_extra,
            "saldo_a_receber": saldo,
            "parcelas_vencidas": pv,
            "em_atraso": em_atraso,
            "situacao": situacao,
            "custo_pecas": custo_pecas,
            "embalagem": embalagem,
            "taxa_pagamento": taxa_valor,
            "imposto_estimado": imposto,
            "lucro_contribuicao": lucro,
            "margem_contribuicao": margem,
            "atualizado_em": datetime.now(),
        }},
    )


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


# ---------- TELA PRINCIPAL ----------

def tela_vendas():
    st.header("💰 Vendas")
    st.caption(
        "Uma linha por venda (cabeçalho). As peças vendidas ficam na aba **Itens da venda**. "
        "Pago à vista = informe o valor em 'Entrada ou pago à vista' e 0 parcelas."
    )

    if st.session_state.get("cargo") not in ("Administrador", "Funcionário"):
        st.warning("Acesso restrito.")
        return

    db = get_db()

    tab_vendas, tab_itens = st.tabs(["📋 Vendas", "🧾 Itens da venda"])

    with tab_vendas:
        _aba_vendas(db)
    with tab_itens:
        _aba_itens(db)


# ---------- ABA VENDAS ----------

def _aba_vendas(db):
    col = db["vendas"]
    produtos = list(db["produtos"].find({"status": "Ativo"}))
    skus = [p["sku"] for p in produtos]

    # ---------- LISTAGEM ----------
    st.subheader("Vendas lançadas")
    vendas = list(col.find({}).sort("data_venda", -1).limit(200))

    if vendas:
        linhas = []
        for v in vendas:
            linhas.append({
                "Nº": v["numero_venda"],
                "Data": v["data_venda"].strftime("%d/%m/%Y") if v.get("data_venda") else "",
                "Cliente": v.get("cliente", ""),
                "Canal": v.get("canal", ""),
                "Pagamento": v.get("forma_pagamento", ""),
                "Status": v.get("status", ""),
                "Total": brl(v.get("total_venda", 0)),
                "Entrada": brl(v.get("entrada", 0)),
                "Parcelas": v.get("num_parcelas", 0),
                "Saldo": brl(v.get("saldo_a_receber", 0)),
                "Atraso": brl(v.get("em_atraso", 0)),
                "Situação": v.get("situacao", ""),
                "Lucro": brl(v.get("lucro_contribuicao", 0)),
                "Margem": pct(v.get("margem_contribuicao", 0)),
            })
        st.dataframe(linhas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma venda lançada ainda.")

    st.divider()

    # ---------- NOVA VENDA ----------
    with st.expander("➕ Lançar nova venda (cabeçalho)", expanded=not vendas):
        with st.form("nova_venda", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                data_venda = st.date_input("Data da venda *", value=date.today())
                cliente = st.text_input("Cliente *")
                canal = st.selectbox("Canal", CANAIS)
            with col2:
                forma_pag = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO)
                status = st.selectbox("Status", STATUS_VENDA)
                num_parcelas = st.number_input(
                    "Nº de parcelas (0 a 6)", min_value=0, max_value=6, value=0, step=1,
                )
            with col3:
                desconto = st.number_input(
                    "Desconto geral (R$)", min_value=0.0, value=0.0, step=0.5, format="%.2f",
                )
                frete_cobrado = st.number_input(
                    "Frete cobrado da cliente (R$)", min_value=0.0, value=0.0,
                    step=0.5, format="%.2f",
                )
                frete_pago = st.number_input(
                    "Frete pago por você (R$)", min_value=0.0, value=0.0,
                    step=0.5, format="%.2f",
                )

            col4, col5 = st.columns(2)
            with col4:
                entrada = st.number_input(
                    "Entrada ou pago à vista (R$)", min_value=0.0, value=0.0,
                    step=0.5, format="%.2f",
                )
            with col5:
                primeiro_venc = st.date_input("1º vencimento (se parcelado)", value=None)

            submit = st.form_submit_button("💾 Lançar venda")

            if submit:
                if not cliente:
                    st.error("Informe o cliente.")
                else:
                    num = _proximo_numero_venda(db)
                    col.insert_one({
                        "numero_venda": num,
                        "data_venda": datetime.combine(data_venda, datetime.min.time()),
                        "cliente": cliente,
                        "canal": canal,
                        "forma_pagamento": forma_pag,
                        "status": status,
                        "desconto": float(desconto),
                        "frete_cobrado": float(frete_cobrado),
                        "frete_pago": float(frete_pago),
                        "entrada": float(entrada),
                        "num_parcelas": int(num_parcelas),
                        "primeiro_vencimento": datetime.combine(primeiro_venc, datetime.min.time()) if primeiro_venc else None,
                        "estorno": 0.0,
                        "criado_em": datetime.now(),
                        "criado_por": st.session_state.get("usuario_logado"),
                    })
                    st.success(f"Venda **{num}** criada! Agora lance os itens na aba **Itens da venda**.")
                    st.rerun()

    st.divider()

    # ---------- EDIÇÃO ----------
    st.subheader("✏️ Editar venda")
    if not vendas:
        st.info("Nenhuma venda para editar.")
        return

    opcoes = {f"{v['numero_venda']} · {v.get('cliente','')} · {brl(v.get('total_venda',0))}": v for v in vendas}
    escolha = st.selectbox("Selecione a venda", list(opcoes.keys()))
    v = opcoes[escolha]
    venda_id = str(v["_id"])

    with st.form("editar_venda"):
        col1, col2, col3 = st.columns(3)
        with col1:
            nova_data = st.date_input(
                "Data da venda",
                value=v["data_venda"].date() if v.get("data_venda") else date.today(),
            )
            novo_cliente = st.text_input("Cliente", value=v.get("cliente", ""))
            idx_canal = CANAIS.index(v["canal"]) if v.get("canal") in CANAIS else 0
            novo_canal = st.selectbox("Canal", CANAIS, index=idx_canal)
        with col2:
            idx_fp = FORMAS_PAGAMENTO.index(v["forma_pagamento"]) if v.get("forma_pagamento") in FORMAS_PAGAMENTO else 0
            nova_fp = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO, index=idx_fp)
            idx_st = STATUS_VENDA.index(v["status"]) if v.get("status") in STATUS_VENDA else 0
            novo_status = st.selectbox("Status", STATUS_VENDA, index=idx_st)
            novas_parcelas = st.number_input(
                "Nº de parcelas", min_value=0, max_value=6,
                value=int(v.get("num_parcelas", 0)), step=1,
            )
        with col3:
            novo_desc = st.number_input(
                "Desconto (R$)", min_value=0.0,
                value=float(v.get("desconto", 0.0)), step=0.5, format="%.2f",
            )
            novo_frete_c = st.number_input(
                "Frete cobrado (R$)", min_value=0.0,
                value=float(v.get("frete_cobrado", 0.0)), step=0.5, format="%.2f",
            )
            novo_frete_p = st.number_input(
                "Frete pago (R$)", min_value=0.0,
                value=float(v.get("frete_pago", 0.0)), step=0.5, format="%.2f",
            )

        col4, col5, col6 = st.columns(3)
        with col4:
            nova_entrada = st.number_input(
                "Entrada (R$)", min_value=0.0,
                value=float(v.get("entrada", 0.0)), step=0.5, format="%.2f",
            )
        with col5:
            novo_venc = st.date_input(
                "1º vencimento",
                value=v["primeiro_vencimento"].date() if v.get("primeiro_vencimento") else None,
            )
        with col6:
            novo_estorno = st.number_input(
                "Estorno / devolução (R$)", min_value=0.0,
                value=float(v.get("estorno", 0.0)), step=0.5, format="%.2f",
            )

        salvar = st.form_submit_button("💾 Salvar alterações")

        if salvar:
            col.update_one(
                {"_id": ObjectId(venda_id)},
                {"$set": {
                    "data_venda": datetime.combine(nova_data, datetime.min.time()),
                    "cliente": novo_cliente,
                    "canal": novo_canal,
                    "forma_pagamento": nova_fp,
                    "status": novo_status,
                    "desconto": float(novo_desc),
                    "frete_cobrado": float(novo_frete_c),
                    "frete_pago": float(novo_frete_p),
                    "entrada": float(nova_entrada),
                    "num_parcelas": int(novas_parcelas),
                    "primeiro_vencimento": datetime.combine(novo_venc, datetime.min.time()) if novo_venc else None,
                    "estorno": float(novo_estorno),
                }},
            )
            _recalcular_venda(db, venda_id)
            st.success("Venda atualizada!")
            st.rerun()

    st.caption(
        "💡 Ao mudar o **status** para *Cancelada*, os itens permanecem registrados, "
        "mas a venda não conta em faturamento, lucro nem saldo. O estoque é devolvido na aba **Itens**."
    )


# ---------- ABA ITENS ----------

def _aba_itens(db):
    st.subheader("🧾 Itens da venda")
    st.caption(
        "Cada linha é uma peça. O **Nº venda** precisa existir na aba Vendas. "
        "O estoque é baixado automaticamente e o custo vem do custo médio do produto."
    )

    vendas = list(db["vendas"].find({"status": {"$ne": "Cancelada"}}).sort("data_venda", -1))
    if not vendas:
        st.warning("Cadastre uma venda primeiro (aba Vendas).")
        return

    produtos = list(db["produtos"].find({"status": "Ativo"}))
    if not produtos:
        st.warning("Cadastre produtos antes de lançar itens.")
        return

    mapa_prod = {p["sku"]: p for p in produtos}
    skus = list(mapa_prod.keys())

    # ---------- LISTAGEM ----------
    itens = list(db["itens_venda"].find({}).sort("numero_venda", -1).limit(300))
    if itens:
        linhas = []
        for i in itens:
            linhas.append({
                "Nº venda": i["numero_venda"],
                "SKU": i["sku"],
                "Produto": i.get("produto_nome", ""),
                "Qtd": i.get("quantidade", 0),
                "Preço unit.": brl(i.get("preco_unitario", 0)),
                "Preço total": brl(i.get("preco_total", 0)),
                "Custo unit.": brl(i.get("custo_unitario", 0)),
            })
        st.dataframe(linhas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum item lançado ainda.")

    st.divider()

    # ---------- NOVO ITEM ----------
    with st.expander("➕ Lançar novo item", expanded=not itens):
        with st.form("novo_item", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                num_venda = st.selectbox(
                    "Nº venda *",
                    [v["numero_venda"] for v in vendas],
                )
            with col2:
                sku = st.selectbox("SKU *", skus)
                quantidade = st.number_input("Quantidade *", min_value=1, value=1, step=1)
            with col3:
                preco_unit = st.number_input(
                    "Preço unitário (R$) *", min_value=0.0, value=0.0,
                    step=0.5, format="%.2f",
                )

            submit = st.form_submit_button("💾 Lançar item")

            if submit:
                if quantidade <= 0 or preco_unit <= 0:
                    st.error("Quantidade e preço devem ser maiores que zero.")
                else:
                    disp = _estoque_disponivel(db, sku)
                    if quantidade > disp:
                        st.warning(
                            f"Estoque disponível do **{sku}** é {disp}. "
                            f"Lançando mesmo assim (estoque poderá ficar negativo)."
                        )
                    custo = _custo_medio_produto(db, sku)
                    db["itens_venda"].insert_one({
                        "numero_venda": num_venda,
                        "sku": sku,
                        "produto_nome": mapa_prod[sku]["nome"],
                        "quantidade": int(quantidade),
                        "preco_unitario": float(preco_unit),
                        "preco_total": float(quantidade * preco_unit),
                        "custo_unitario": float(custo),
                        "criado_em": datetime.now(),
                    })
                    # Recalcula a venda
                    venda = db["vendas"].find_one({"numero_venda": num_venda})
                    if venda:
                        _recalcular_venda(db, str(venda["_id"]))
                    st.success(f"Item lançado na venda {num_venda}.")
                    st.rerun()

    st.divider()

    # ---------- REMOVER ITEM ----------
    st.subheader("🗑️ Remover item")
    if not itens:
        st.info("Nenhum item para remover.")
        return

    opcoes = {
        f"{i['numero_venda']} · {i['sku']} · {i.get('quantidade',0)} pç · {brl(i.get('preco_total',0))}": i
        for i in itens
    }
    escolha = st.selectbox("Selecione o item", list(opcoes.keys()))
    item = opcoes[escolha]

    if st.button("Remover item selecionado"):
        num = item["numero_venda"]
        db["itens_venda"].delete_one({"_id": item["_id"]})
        venda = db["vendas"].find_one({"numero_venda": num})
        if venda:
            _recalcular_venda(db, str(venda["_id"]))
        st.success("Item removido e venda recalculada.")
        st.rerun()
