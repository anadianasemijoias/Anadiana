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
        {"numero": {"$regex": f"^{prefixo}"}},
        sort=[("numero", -1)],
    )
    if ultima:
        try:
            seq = int(ultima["numero"].split("-")[1]) + 1
        except (IndexError, ValueError):
            seq = 1
    else:
        seq = 1
    return f"{prefixo}{seq:04d}"


def _carregar_produtos(db):
    """Retorna dict {sku: produto} para lookup rápido."""
    return {p["sku"]: p for p in db["produtos"].find({})}


def _calcular_totais_venda(itens, params):
    """Calcula totais da venda a partir dos itens e dos parâmetros."""
    total_bruto = sum(i["preco_unitario"] * i["quantidade"] for i in itens)
    custo_total = sum(i["custo_unitario"] * i["quantidade"] for i in itens)
    aliquota = params.get("aliquota_imposto", 0.0)
    imposto = total_bruto * aliquota
    return total_bruto, custo_total, imposto


def _baixar_estoque(db, itens, numero_venda):
    """Baixa estoque dos produtos vendidos."""
    for item in itens:
        db["produtos"].update_one(
            {"sku": item["sku"]},
            {"$inc": {"estoque_atual": -item["quantidade"]}},
        )
        # Registra movimento de saída (opcional, para rastreio)
        db["movimentos_estoque"].insert_one({
            "data": datetime.now(),
            "sku": item["sku"],
            "tipo": "Venda",
            "quantidade": -item["quantidade"],
            "referencia": numero_venda,
        })


def _repor_estoque(db, itens, numero_venda):
    """Devolve estoque (usado em cancelamento de venda)."""
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
# TELA PRINCIPAL
# ---------------------------------------------------------
def tela_vendas():
    st.header("💰 Vendas")
    db = get_db()
    params = carregar_parametros()

    aba_nova, aba_lista = st.tabs(["➕ Nova Venda", "📋 Vendas Registradas"])

    # -----------------------------------------------------
    # ABA 1 — NOVA VENDA
    # -----------------------------------------------------
    with aba_nova:
        _form_nova_venda(db, params)

    # -----------------------------------------------------
    # ABA 2 — LISTAGEM / CANCELAMENTO
    # -----------------------------------------------------
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

    # Inicializa carrinho na sessão
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

    col1, col2, col3 = st.columns(3)
    with col1:
        forma_pgto = st.selectbox(
            "Forma de pagamento",
            list(params.get("taxas_pagamento", {}).keys()) or ["Pix"],
        )
    with col2:
        parcelas = st.number_input("Nº de parcelas", min_value=1, max_value=24, value=1)
    with col3:
        primeiro_venc = st.date_input("1º vencimento (crediário)", value=date.today())

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

    # Tabela do carrinho
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
        total_liquido = total_bruto - desconto - imposto - taxa_valor - embalagem
        lucro_contrib = total_liquido - custo_total
        margem = (lucro_contrib / total_bruto) if total_bruto else 0.0

        st.subheader("📊 Resumo da venda")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total bruto", brl(total_bruto))
        c2.metric("Desconto", brl(desconto))
        c3.metric("Imposto", brl(imposto))
        c4.metric("Taxa pgto", brl(taxa_valor))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Embalagem", brl(embalagem))
        c2.metric("Custo peças", brl(custo_total))
        c3.metric("Lucro contrib.", brl(lucro_contrib))
        c4.metric("Margem", pct(margem))

        # ---------------- Finalizar ----------------
        if st.button("✅ Finalizar venda", type="primary"):
            numero = _proximo_numero_venda(db)
            venda_doc = {
                "numero": numero,
                "data": datetime.combine(data_venda, datetime.min.time()),
                "cliente": cliente,
                "canal": canal,
                "forma_pagamento": forma_pgto,
                "parcelas": int(parcelas),
                "primeiro_vencimento": datetime.combine(primeiro_venc, datetime.min.time()),
                "status": "Concluída",
                "desconto": desconto,
                "total_bruto": total_bruto,
                "total_liquido": total_liquido,
                "custo_total": custo_total,
                "imposto": imposto,
                "taxa_pagamento": taxa_valor,
                "embalagem": embalagem,
                "lucro_contribuicao": lucro_contrib,
                "margem": margem,
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
    vendas = list(db["vendas"].find({}).sort("data", -1))
    if not vendas:
        st.info("Nenhuma venda registrada.")
        return

    st.dataframe(
        [
            {
                "Nº": v["numero"],
                "Data": v["data"].strftime("%d/%m/%Y"),
                "Cliente": v.get("cliente", ""),
                "Canal": v.get("canal", ""),
                "Forma": v.get("forma_pagamento", ""),
                "Total": brl(v.get("total_bruto", 0)),
                "Lucro": brl(v.get("lucro_contribuicao", 0)),
                "Margem": pct(v.get("margem", 0)),
                "Status": v.get("status", ""),
            }
            for v in vendas
        ],
        use_container_width=True,
        hide_index=True,
    )

    # Detalhe + cancelamento
    opcoes = {f"{v['numero']} — {v.get('cliente','')}": v for v in vendas}
    escolha = st.selectbox("Ver detalhes / cancelar", ["—"] + list(opcoes.keys()))

    if escolha != "—":
        v = opcoes[escolha]
        st.subheader(f"Venda {v['numero']}")
        st.write(f"**Cliente:** {v.get('cliente','')}")
        st.write(f"**Data:** {v['data'].strftime('%d/%m/%Y')}")
        st.write(f"**Forma:** {v.get('forma_pagamento','')} — {v.get('parcelas',1)}x")
        st.write(f"**Status:** {v.get('status','')}")

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
                    {"$set": {"status": "Cancelada", "cancelado_em": datetime.now()}},
                )
                _repor_estoque(db, v.get("itens", []), v["numero"])
                st.success("Venda cancelada e estoque devolvido.")
                st.rerun()
