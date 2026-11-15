import streamlit as st
from datetime import datetime, date, timedelta
from modules.utils import get_db, brl, pct
from modules.config import carregar_parametros
from modules.dre import _calcular_dre
from modules.caixa import _linhas_caixa


MESES = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]


def _soma_por_mes(colecao, campo_data, campo_valor, ano, filtro_extra=None):
    """Soma campo_valor por mês (Jan..Dez) no ano informado."""
    valores = [0.0] * 12
    pipeline = [
        {"$match": {
            campo_data: {
                "$gte": datetime(ano, 1, 1),
                "$lt": datetime(ano + 1, 1, 1),
            },
            **(filtro_extra or {}),
        }},
        {"$group": {
            "_id": {"$month": f"${campo_data}"},
            "total": {"$sum": f"${campo_valor}"},
        }},
    ]
    for r in colecao.aggregate(pipeline):
        valores[int(r["_id"]) - 1] = float(r["total"])
    return valores


def _posicao_atual(db):
    """Indicadores de posição atual (não dependem de mês)."""
    hoje = date.today()

    # Total a receber e em atraso (vendas não canceladas)
    total_receber = 0.0
    em_atraso = 0.0
    parcelas_7d = 0.0

    vendas = db["vendas"].find({"status": {"$ne": "Cancelada"}})
    for v in vendas:
        total_receber += float(v.get("saldo_a_receber", 0))
        em_atraso += float(v.get("em_atraso", 0))

        # Parcelas a vencer em 7 dias
        pv = v.get("primeiro_vencimento")
        num = int(v.get("num_parcelas", 0))
        if pv and num > 0:
            venc_base = pv.date() if isinstance(pv, datetime) else pv
            valor_parcela = float(v.get("valor_parcela", 0))
            financiado = float(v.get("valor_financiado", 0))
            valor_ultima = round(financiado - valor_parcela * (num - 1), 2)

            for i in range(1, num + 1):
                ano = venc_base.year + (venc_base.month - 1 + (i - 1)) // 12
                mes = (venc_base.month - 1 + (i - 1)) % 12 + 1
                dia = min(venc_base.day, 28)
                venc = date(ano, mes, dia)
                if hoje <= venc <= hoje + timedelta(days=7):
                    parcelas_7d += valor_ultima if i == num else valor_parcela

    inadimplencia = (em_atraso / total_receber) if total_receber > 0 else 0

    # Estoque
    compras = list(db["compras"].aggregate([
        {"$group": {"_id": "$sku",
                    "qtd": {"$sum": "$quantidade"},
                    "custo": {"$sum": "$valor_total"}}}
    ]))
    vendas_itens = list(db["itens_venda"].aggregate([
        {"$group": {"_id": "$sku", "qtd": {"$sum": "$quantidade"}}}
    ]))
    ajustes = list(db["ajustes"].aggregate([
        {"$group": {"_id": "$sku", "qtd": {"$sum": "$quantidade"}}}
    ]))

    qtd_comprada = {c["_id"]: c["qtd"] for c in compras}
    custo_total = {c["_id"]: c["custo"] for c in compras}
    qtd_vendida = {v["_id"]: v["qtd"] for v in vendas_itens}
    qtd_ajuste = {a["_id"]: a["qtd"] for a in ajustes}

    produtos = list(db["produtos"].find({"status": "Ativo"}))
    estoque_pecas = 0
    estoque_custo = 0.0
    alerta_repor = 0
    alerta_esgotado = 0
    alerta_revisar = 0

    for p in produtos:
        sku = p["sku"]
        qc = qtd_comprada.get(sku, 0)
        ct = custo_total.get(sku, 0)
        qv = qtd_vendida.get(sku, 0)
        qa = qtd_ajuste.get(sku, 0)
        custo_medio = (ct / qc) if qc > 0 else 0
        estoque = qc - qv + qa
        estoque_min = int(p.get("estoque_minimo", 0))

        estoque_pecas += estoque
        estoque_custo += estoque * custo_medio

        if estoque < 0:
            alerta_revisar += 1
        elif estoque == 0:
            alerta_esgotado += 1
        elif estoque <= estoque_min:
            alerta_repor += 1

    # Contas a pagar em aberto (compras + despesas)
    contas_pagar = 0.0
    for c in db["compras"].find({"situacao": {"$in": ["Pendente", "Vencida"]}}):
        contas_pagar += float(c.get("valor_total", 0))
    for d in db["despesas"].find({"situacao": {"$in": ["Pendente", "Vencida"]}}):
        contas_pagar += float(d.get("valor", 0))

    return {
        "total_receber": total_receber,
        "em_atraso": em_atraso,
        "inadimplencia": inadimplencia,
        "parcelas_7d": parcelas_7d,
        "estoque_pecas": estoque_pecas,
        "estoque_custo": estoque_custo,
        "alerta_repor": alerta_repor,
        "alerta_esgotado": alerta_esgotado,
        "alerta_revisar": alerta_revisar,
        "contas_pagar": contas_pagar,
    }


def _parcelas_programadas(db, ano, mes, n_meses=6):
    """Retorna lista de (mês_label, valor) para os próximos n_meses a partir do mês atual."""
    resultado = []
    for i in range(n_meses):
        ano_alvo = ano + (mes - 1 + i) // 12
        mes_alvo = (mes - 1 + i) % 12 + 1
        inicio = datetime(ano_alvo, mes_alvo, 1)
        if mes_alvo == 12:
            fim = datetime(ano_alvo + 1, 1, 1)
        else:
            fim = datetime(ano_alvo, mes_alvo + 1, 1)

        total = 0.0
        vendas = db["vendas"].find({"status": {"$ne": "Cancelada"}})
        for v in vendas:
            pv = v.get("primeiro_vencimento")
            num = int(v.get("num_parcelas", 0))
            if not pv or num == 0:
                continue
            venc_base = pv.date() if isinstance(pv, datetime) else pv
            valor_parcela = float(v.get("valor_parcela", 0))
            financiado = float(v.get("valor_financiado", 0))
            valor_ultima = round(financiado - valor_parcela * (num - 1), 2)
            for j in range(1, num + 1):
                a = venc_base.year + (venc_base.month - 1 + (j - 1)) // 12
                m = (venc_base.month - 1 + (j - 1)) % 12 + 1
                d = min(venc_base.day, 28)
                venc = datetime(a, m, d)
                if inicio <= venc < fim:
                    total += valor_ultima if j == num else valor_parcela

        resultado.append((f"{MESES[mes_alvo-1]}/{ano_alvo}", total))
    return resultado


def tela_painel():
    st.header("🎯 Painel · Anadiana Semijoias")
    st.caption(
        "**Não precisa de digitação.** Junta indicadores do mês, posição atual, "
        "comparativo mensal e parcelas programadas."
    )

    if st.session_state.get("cargo") not in ("Administrador", "Funcionário"):
        st.warning("Acesso restrito.")
        return

    db = get_db()
    params = carregar_parametros()
    ano = int(params.get("ano", date.today().year))
    mes = int(params.get("mes", 1))
    idx = mes - 1

    # ---------- SELETOR DE ANO ----------
    col_ano, col_info = st.columns([1, 3])
    with col_ano:
        anos_disponiveis = sorted(set([ano - 1, ano, ano + 1]))
        ano_sel = st.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(ano))
    with col_info:
        st.info(
            f"Mês analisado: **{MESES[mes-1]}/{ano_sel}** "
            f"(definido em Parâmetros). Troque o mês/ano em **⚙️ Parâmetros**."
        )

    # ---------- CÁLCULOS ----------
    dre = _calcular_dre(db, ano_sel)
    caixa = _linhas_caixa(db, ano_sel)
    pos = _posicao_atual(db)

    # ---------- NO MÊS ----------
    st.subheader(f"📅 No mês analisado — {MESES[mes-1]}/{ano_sel}")

    # Nº de vendas e peças vendidas
    inicio = datetime(ano_sel, mes, 1)
    fim = datetime(ano_sel + 1, 1, 1) if mes == 12 else datetime(ano_sel, mes + 1, 1)
    n_vendas = db["vendas"].count_documents({
        "data_venda": {"$gte": inicio, "$lt": fim},
        "status": {"$ne": "Cancelada"},
    })
    pecas = list(db["itens_venda"].aggregate([
        {"$match": {"criado_em": {"$gte": inicio, "$lt": fim}}},
        {"$group": {"_id": None, "qtd": {"$sum": "$quantidade"}}},
    ]))
    pecas_vendidas = pecas[0]["qtd"] if pecas else 0

    faturamento = dre["faturamento"][idx]
    receita_liq = dre["receita_liquida"][idx]
    lucro_bruto = dre["lucro_bruto"][idx]
    margem = dre["margem_contribuicao"][idx]
    margem_pct = dre["margem_contribuicao_pct"][idx]
    despesas = dre["despesas_operacionais"][idx]
    resultado = dre["resultado"][idx]
    ponto_eq = dre["ponto_equilibrio"][idx]
    recebido = caixa["entradas_mes"][idx]
    saldo_caixa = caixa["saldo_acumulado"][idx]
    ticket_medio = (faturamento / n_vendas) if n_vendas > 0 else 0
    pecas_por_venda = (pecas_vendidas / n_vendas) if n_vendas > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Faturamento", brl(faturamento))
    c2.metric("Receita líquida", brl(receita_liq))
    c3.metric("Nº de vendas", n_vendas)
    c4.metric("Peças vendidas", pecas_vendidas)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ticket médio", brl(ticket_medio))
    c2.metric("Peças/venda", f"{pecas_por_venda:.2f}")
    c3.metric("Lucro bruto", brl(lucro_bruto))
    c4.metric("Margem de contribuição", brl(margem))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Margem de contribuição (%)", pct(margem_pct))
    c2.metric("Despesas operacionais", brl(despesas))
    c3.metric("Resultado operacional", brl(resultado))
    c4.metric("Ponto de equilíbrio", brl(ponto_eq))

    c1, c2 = st.columns(2)
    c1.metric("Recebido no mês (entradas)", brl(recebido))
    c2.metric("Saldo de caixa (fim do mês)", brl(saldo_caixa))

    st.divider()

    # ---------- POSIÇÃO ATUAL ----------
    st.subheader("📍 Posição atual")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total a receber", brl(pos["total_receber"]))
    c2.metric("Em atraso", brl(pos["em_atraso"]))
    c3.metric("Inadimplência", pct(pos["inadimplencia"]))
    c4.metric("A vencer em 7 dias", brl(pos["parcelas_7d"]))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Estoque (peças)", pos["estoque_pecas"])
    c2.metric("Estoque a custo", brl(pos["estoque_custo"]))
    c3.metric("Produtos para repor", pos["alerta_repor"])
    c4.metric("Produtos esgotados", pos["alerta_esgotado"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Produtos a revisar", pos["alerta_revisar"])
    c2.metric("Contas a pagar em aberto", brl(pos["contas_pagar"]))
    c3.metric("Faturamento acumulado no ano", brl(sum(dre["faturamento"])))

    limite = float(params.get("limite_faturamento_anual", 0))
    if limite > 0:
        pct_limite = sum(dre["faturamento"]) / limite
        st.metric("% do limite anual de faturamento", pct(pct_limite))
    else:
        st.caption("ℹ️ Informe o limite anual de faturamento em **Parâmetros** para ver o percentual.")

    st.divider()

    # ---------- COMPARATIVO MENSAL ----------
    st.subheader("📊 Comparativo mensal")
    comparativo = []
    for i in range(12):
        comparativo.append({
            "Mês": MESES[i],
            "Faturamento": brl(dre["faturamento"][i]),
            "Margem de contribuição": brl(dre["margem_contribuicao"][i]),
            "Resultado operacional": brl(dre["resultado"][i]),
            "Saldo de caixa": brl(caixa["saldo_acumulado"][i]),
        })
    st.dataframe(comparativo, use_container_width=True, hide_index=True)

    st.divider()

    # ---------- GRÁFICO COMPARATIVO ----------
    st.subheader("📈 Evolução ao longo do ano")
    st.bar_chart(
        {
            "Faturamento": {MESES[i]: dre["faturamento"][i] for i in range(12)},
            "Margem de contribuição": {MESES[i]: dre["margem_contribuicao"][i] for i in range(12)},
            "Resultado operacional": {MESES[i]: dre["resultado"][i] for i in range(12)},
            "Saldo de caixa": {MESES[i]: caixa["saldo_acumulado"][i] for i in range(12)},
        },
        use_container_width=True,
    )

    st.divider()

    # ---------- PARCELAS PROGRAMADAS ----------
    st.subheader("🗓️ Parcelas programadas (crediário) — próximos 6 meses")
    prog = _parcelas_programadas(db, ano_sel, mes, 6)
    st.dataframe(
        [{"Mês": m, "A receber previsto": brl(v)} for m, v in prog],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "💡 Soma das parcelas **programadas** por mês. Não desconta o que já foi pago — "
        "para isso, veja **Total a receber** na Posição Atual."
    )
