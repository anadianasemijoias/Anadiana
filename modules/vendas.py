import streamlit as st
from datetime import datetime, date
from bson import ObjectId
from modules.utils import get_db, brl, pct
from modules.config import carregar_parametros


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def _proximo_numero_venda(db):
    """Gera o próximo número de venda no formato V2026-0001."""
    ano = datetime.now().year
    prefixo = f"V{ano}-"
    ultima = db["vendas"].find_one(
        {"numero_venda": {"$regex": f"^{prefixo}"}},
        sort=[("numero_venda", -1)],
    )
    if ultima:
        try:
            seq = int(ultima["numero_venda"].split("-")[1]) + 1
        except (IndexError, ValueError):
            seq = 1
    else:
        seq = 1
    return f"{prefixo}{seq:04d}"


def _carregar_produtos(db):
    return {p["sku"]: p for p in db["produtos"].find({})}


def _calcular_totais_venda(itens, params):
    total_bruto = sum(i["preco_unitario"] * i["quantidade"] for i in itens)
    custo_total = sum(i["custo_unitario"] * i["quantidade"] for i in itens)
    aliquota = params.get("aliquota_imposto", 0.0)
    imposto = total_bruto * aliquota
    return total_bruto, custo_total, imposto


def _baixar_estoque(db, itens, numero_venda):
    for item in itens:
        db["produtos"].update_one(
            {"sku": item["sku"]},
            {"$inc": {"estoque_atual": -item["quantidade"]}},
        )
        db["movimentos_estoque"].insert_one({
            "data": datetime.now(),
            "sku": item["sku"],
            "tipo": "Venda",
            "quantidade": -item["quantidade"],
            "referencia": numero_venda,
        })


def _repor_estoque(db, itens, numero_venda):
    for item in itens:
        db["produtos"].update_one(
            {"sku": item["sku"]},
            {"$inc": {"estoque_atual": item["quantidade"]}},
        )
        db["movimentos_estoque"].insert_one({
            "data": datetime.now(),
            "sku": item["sku"],
            "tipo": "Cancelamento Venda",
            "quantidade": item["quantidade"],
            "referencia": numero_venda,
        })


# ---------------------------------------------------------
# RECÁLCULO DA VENDA (usado pelo módulo de Recebimentos)
# ---------------------------------------------------------
def _recalcular_venda(db, venda_id):
    """
    Recalcula saldo_a_receber, atraso e situação da venda
    com base nos recebimentos lançados.
    """
    venda = db["vendas"].find_one({"_id": ObjectId(venda_id)})
    if not venda:
        return

    total = float(venda.get("total_venda", 0))
    entrada = float(venda.get("entrada", 0))
    financiado = max(total - entrada, 0.0)

    recebidos = list(db["recebimentos"].find({"numero_venda": venda["numero_venda"]}))
    total_recebido = sum(float(r.get("valor", 0)) for r in recebidos)

    saldo = round(financiado - total_recebido, 2)
    if saldo < 0:
        saldo = 0.0

    # Situação
    if saldo <= 0.005:
        situacao = "Quitada"
    elif total_recebido > 0:
        situacao = "Parcialmente recebida"
    else:
        situacao = "Em aberto"

    # Atraso: alguma parcela vencida e não paga?
    hoje = date.today()
    primeiro = venda.get("primeiro_vencimento")
    num_parcelas = int(venda.get("num_parcelas", 0))
    valor_parcela = float(venda.get("valor_parcela", 0))
    atraso = False
    parcelas_vencidas = 0

    if primeiro and num_parcelas > 0 and saldo > 0.005:
        venc_base = primeiro.date() if isinstance(primeiro, datetime) else primeiro
        recebidas_nums = {int(r.get("numero_parcela", 0)) for r in recebidos}
        for i in range(1, num_parcelas + 1):
            if i in recebidas_nums:
                continue
            ano = venc_base.year + (venc_base.month - 1 + (i - 1)) // 12
            mes = (venc_base.month - 1 + (i - 1)) % 12 + 1
            dia = min(venc_base.day, 28)
            venc = date(ano, mes, dia)
            if venc < hoje:
                atraso = True
                parcelas_vencidas += 1

    db["vendas"].update_one(
        {"_id": ObjectId(venda_id)},
        {"$set": {
            "saldo_a_receber": saldo,
            "total_recebido": round(total_recebido, 2),
            "situacao": situacao,
            "em_atraso": atraso,
            "parcelas_vencidas": parcelas_vencidas,
            "atualizado_em": datetime.now(),
        }},
    )


# ---------------------------------------------------------
# TELA PRINCIPAL
# ---------------------------------------------------------
def tela_vendas():
    st.header("💰 Vendas")
    db = get_db()
    params = carregar_parametros()

    aba_nova, aba_lista = st.tabs(["➕ Nova Venda", "📋 Vendas Registradas"])
    with aba_nova:
        _form_nova_venda(db, params)
    with aba_lista:
        _lista_vendas(db)


# ---------------------------------------------------------
# FORMULÁRIO DE NOVA VENDA
# ---------------------------------------------------------
def _form_nova_venda(db, params):
    produtos = _carregar_produtos(db)
    if not produtos:
        st.warning("Cadastre produtos antes de registrar vendas.")
        return

    if "carrinho_venda" not in st.session_state:
        st.session_state["carrinho_venda"] = []

    st.subheader("Dados da venda")
    col1, col2, col3 = st.columns(3)
    with col1:
        data_venda = st.date_input("Data da venda", value=date.today())
    with col2:
        cliente = st.text_input("Cliente")
    with col3:
        canal = st.selectbox(
            "Canal de venda",
            ["Loja física", "Instagram", "WhatsApp", "Site", "Outro"],
        )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        forma_pgto = st.selectbox(
            "Forma de pagamento",
            list(params.get("taxas_pagamento", {}).keys()) or ["Pix"],
        )
    with col2:
        num_parcelas = st.number_input("Nº de parcelas", min_value=1, max_value=24, value=1)
    with col3:
        primeiro_venc = st.date_input("1º vencimento", value=date.today())
    with col4:
        entrada = st.number_input(
            "Entrada (R$)", min_value=0.0, value=0.0, step=10.0, format="%.2f"
        )

    st.divider()

    # ---------------- Itens ----------------
    st.subheader("🧾 Itens da venda")
    with st.form("add_item", clear_on_submit=True):
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            sku_sel = st.selectbox(
                "Produto (SKU)",
                list(produtos.keys()),
                format_func=lambda s: f"{s} — {produtos[s].get('nome','')}",
            )
        with col2:
            qtd = st.number_input("Qtd", min_value=1, value=1, step=1)
        with col3:
            preco = st.number_input(
                "Preço unit. (R$)",
                min_value=0.0,
                value=float(produtos[sku_sel].get("preco_venda", 0.0)),
                step=1.0,
                format="%.2f",
            )
        add = st.form_submit_button("➕ Adicionar item")

        if add:
            prod = produtos[sku_sel]
            estoque = prod.get("estoque_atual", 0)
            if qtd > estoque:
                st.error(f"Estoque insuficiente. Disponível: {estoque}.")
            else:
                st.session_state["carrinho_venda"].append({
                    "sku": sku_sel,
                    "nome": prod.get("nome", ""),
                    "quantidade": int(qtd),
                    "preco_unitario": float(preco),
                    "custo_unitario": float(prod.get("custo_medio", 0.0)),
                })
                st.success(f"{qtd}x {sku_sel} adicionado.")

    carrinho = st.session_state["carrinho_venda"]
    if carrinho:
        st.dataframe(
            [
                {
                    "SKU": i["sku"],
                    "Produto": i["nome"],
                    "Qtd": i["quantidade"],
                    "Preço unit.": brl(i["preco_unitario"]),
                    "Subtotal": brl(i["preco_unitario"] * i["quantidade"]),
                }
                for i in carrinho
            ],
            use_container_width=True,
            hide_index=True,
        )
        colA, colB = st.columns([1, 1])
        with colA:
            if st.button("🗑️ Limpar carrinho"):
                st.session_state["carrinho_venda"] = []
                st.rerun()
        with colB:
            desconto = st.number_input("Desconto (R$)", min_value=0.0, value=0.0, step=1.0, format="%.2f")
    else:
        desconto = 0.0
        st.info("Nenhum item adicionado ainda.")

    st.divider()

    # ---------------- Resumo ----------------
    if carrinho:
        total_bruto, custo_total, imposto = _calcular_totais_venda(carrinho, params)
        taxa_pgto = params.get("taxas_pagamento", {}).get(forma_pgto, 0.0)
        taxa_valor = total_bruto * taxa_pgto
        embalagem = params.get("custo_embalagem", 0.0)
        total_venda = total_bruto - desconto  # valor efetivo da venda
        total_liquido = total_venda - imposto - taxa_valor - embalagem
        lucro_contrib = total_liquido - custo_total
        margem = (lucro_contrib / total_bruto) if total_bruto else 0.0

        # Financiamento (crediário)
        entrada = min(entrada, total_venda)
        valor_financiado = max(total_venda - entrada, 0.0)
        valor_parcela = round(valor_financiado / num_parcelas, 2) if num_parcelas > 0 else 0.0

        st.subheader("📊 Resumo da venda")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total bruto", brl(total_bruto))
        c2.metric("Desconto", brl(desconto))
        c3.metric("Total da venda", brl(total_venda))
        c4.metric("Entrada", brl(entrada))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Financiado", brl(valor_financiado))
        c2.metric("Parcela", brl(valor_parcela))
        c3.metric("Lucro contrib.", brl(lucro_contrib))
        c4.metric("Margem", pct(margem))

        if st.button("✅ Finalizar venda", type="primary"):
            numero = _proximo_numero_venda(db)
            venda_doc = {
                "numero_venda": numero,
                "data_venda": datetime.combine(data_venda, datetime.min.time()),
                "cliente": cliente,
                "canal": canal,
                "forma_pagamento": forma_pgto,
                "num_parcelas": int(num_parcelas),
                "primeiro_vencimento": datetime.combine(primeiro_venc, datetime.min.time()),
                "status": "Concluída",
                "desconto": desconto,
                "total_venda": total_venda,
                "total_bruto": total_bruto,
                "total_liquido": total_liquido,
                "custo_total": custo_total,
                "imposto": imposto,
                "taxa_pagamento": taxa_valor,
                "embalagem": embalagem,
                "lucro_contribuicao": lucro_contrib,
                "margem": margem,
                "entrada": entrada,
                "valor_financiado": valor_financiado,
                "valor_parcela": valor_parcela,
                "saldo_a_receber": valor_financiado,
                "total_recebido": 0.0,
                "situacao": "Em aberto" if valor_financiado > 0 else "Quitada",
                "em_atraso": False,
                "parcelas_vencidas": 0,
                "itens": carrinho,
                "criado_em": datetime.now(),
                "criado_por": st.session_state.get("usuario_logado", ""),
            }
            db["vendas"].insert_one(venda_doc)
            _baixar_estoque(db, carrinho, numero)
            st.session_state["carrinho_venda"] = []
            st.success(f"Venda **{numero}** registrada com sucesso!")
            st.rerun()


# ---------------------------------------------------------
# LISTAGEM DE VENDAS
# ---------------------------------------------------------
def _lista_vendas(db):
    vendas = list(db["vendas"].find({}).sort("data_venda", -1))
    if not vendas:
        st.info("Nenhuma venda registrada.")
        return

    st.dataframe(
        [
            {
                "Nº": v.get("numero_venda", ""),
                "Data": v["data_venda"].strftime("%d/%m/%Y") if v.get("data_venda") else "",
                "Cliente": v.get("cliente", ""),
                "Canal": v.get("canal", ""),
                "Forma": v.get("forma_pagamento", ""),
                "Total": brl(v.get("total_venda", 0)),
                "Saldo": brl(v.get("saldo_a_receber", 0)),
                "Situação": v.get("situacao", ""),
                "Status": v.get("status", ""),
            }
            for v in vendas
        ],
        use_container_width=True,
        hide_index=True,
    )

    opcoes = {f"{v.get('numero_venda','')} — {v.get('cliente','')}": v for v in vendas}
    escolha = st.selectbox("Ver detalhes / cancelar", ["—"] + list(opcoes.keys()))

    if escolha != "—":
        v = opcoes[escolha]
        st.subheader(f"Venda {v.get('numero_venda','')}")
        st.write(f"**Cliente:** {v.get('cliente','')}")
        st.write(f"**Data:** {v['data_venda'].strftime('%d/%m/%Y') if v.get('data_venda') else ''}")
        st.write(f"**Forma:** {v.get('forma_pagamento','')} — {v.get('num_parcelas',1)}x")
        st.write(f"**Total:** {brl(v.get('total_venda',0))} · "
                 f"**Entrada:** {brl(v.get('entrada',0))} · "
                 f"**Saldo:** {brl(v.get('saldo_a_receber',0))}")
        st.write(f"**Situação:** {v.get('situacao','')} · **Status:** {v.get('status','')}")

        st.markdown("**Itens:**")
        st.dataframe(
            [
                {
                    "SKU": i["sku"],
                    "Produto": i["nome"],
                    "Qtd": i["quantidade"],
                    "Preço": brl(i["preco_unitario"]),
                    "Subtotal": brl(i["preco_unitario"] * i["quantidade"]),
                }
                for i in v.get("itens", [])
            ],
            use_container_width=True,
            hide_index=True,
        )

        if v.get("status") == "Concluída":
            if st.button("❌ Cancelar venda (devolve estoque)"):
                db["vendas"].update_one(
                    {"_id": v["_id"]},
                    {"$set": {
                        "status": "Cancelada",
                        "situacao": "Cancelada",
                        "saldo_a_receber": 0.0,
                        "cancelado_em": datetime.now(),
                    }},
                )
                _repor_estoque(db, v.get("itens", []), v.get("numero_venda", ""))
                st.success("Venda cancelada e estoque devolvido.")
                st.rerun()
