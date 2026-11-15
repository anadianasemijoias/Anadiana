import streamlit as st
from datetime import datetime, date
from modules.utils import get_db, brl, pct
from modules.config import carregar_parametros


MESES = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]


def _soma_por_mes(colecao, campo_data, campo_valor, ano, filtro_extra=None):
    """Retorna lista de 12 valores (Jan..Dez) somando campo_valor no mês de campo_data."""
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


def _calcular_dre(db, ano):
    """Calcula todos os blocos do DRE para o ano informado."""
    params = carregar_parametros()
    aliquota = float(params.get("aliquota_imposto", 0.0))

    # Faturamento = vendas não canceladas (total_venda)
    faturamento = _soma_por_mes(
        db["vendas"], "data_venda", "total_venda", ano,
        filtro_extra={"status": {"$ne": "Cancelada"}},
    )

    # Impostos = faturamento × alíquota
    impostos = [f * aliquota for f in faturamento]
    receita_liquida = [faturamento[i] - impostos[i] for i in range(12)]

    # Custo das peças = soma de custo_pecas por mês (campo já calculado na venda)
    custo_pecas = _soma_por_mes(
        db["vendas"], "data_venda", "custo_pecas", ano,
        filtro_extra={"status": {"$ne": "Cancelada"}},
    )
    lucro_bruto = [receita_liquida[i] - custo_pecas[i] for i in range(12)]

    # Taxas de pagamento
    taxas = _soma_por_mes(
        db["vendas"], "data_venda", "taxa_pagamento", ano,
        filtro_extra={"status": {"$ne": "Cancelada"}},
    )

    # Embalagem
    embalagem = _soma_por_mes(
        db["vendas"], "data_venda", "embalagem", ano,
        filtro_extra={"status": {"$ne": "Cancelada"}},
    )

    # Frete pago
    frete_pago = _soma_por_mes(
        db["vendas"], "data_venda", "frete_pago", ano,
        filtro_extra={"status": {"$ne": "Cancelada"}},
    )

    # Imposto estimado
    imposto_estimado = _soma_por_mes(
        db["vendas"], "data_venda", "imposto_estimado", ano,
        filtro_extra={"status": {"$ne": "Cancelada"}},
    )

    # Margem de contribuição
    margem_contribuicao = [
        lucro_bruto[i] - taxas[i] - embalagem[i] - frete_pago[i] - imposto_estimado[i]
        for i in range(12)
    ]
    margem_contribuicao_pct = [
        (margem_contribuicao[i] / receita_liquida[i]) if receita_liquida[i] > 0 else 0
        for i in range(12)
    ]

    # Despesas operacionais (fixas + marketing + variáveis + impostos pagos)
    # Todas as despesas entram — a diferença é apenas se foram pagas ou não (DRE é regime de competência)
    despesas_operacionais = _soma_por_mes(
        db["despesas"], "data_despesa", "valor", ano,
    )

    # Resultado operacional
    resultado = [
        margem_contribuicao[i] - despesas_operacionais[i] for i in range(12)
    ]

    # Ponto de equilíbrio (receita líquida necessária)
    # = despesas fixas / margem de contribuição %
    ponto_equilibrio = []
    for i in range(12):
        if margem_contribuicao_pct[i] > 0:
            ponto_equilibrio.append(despesas_operacionais[i] / margem_contribuicao_pct[i])
        else:
            ponto_equilibrio.append(0.0)

    return {
        "faturamento": faturamento,
        "impostos": impostos,
        "receita_liquida": receita_liquida,
        "custo_pecas": custo_pecas,
        "lucro_bruto": lucro_bruto,
        "taxas": taxas,
        "embalagem": embalagem,
        "frete_pago": frete_pago,
        "imposto_estimado": imposto_estimado,
        "margem_contribuicao": margem_contribuicao,
        "margem_contribuicao_pct": margem_contribuicao_pct,
        "despesas_operacionais": despesas_operacionais,
        "resultado": resultado,
        "ponto_equilibrio": ponto_equilibrio,
    }


def _formatar_linha(label, valores, formato="brl", bold=False):
    """Formata uma linha (label + 12 valores) para o dataframe."""
    linha = {"Item": f"**{label}**" if bold else label}
    for i, m in enumerate(MESES):
        v = valores[i]
        if formato == "brl":
            linha[m] = brl(v)
        elif formato == "pct":
            linha[m] = pct(v)
        else:
            linha[m] = v
    return linha


def tela_dre():
    st.header("📊 DRE — Demonstrativo de Resultado")
    st.caption(
        "**Não precisa de digitação.** Faturamento = vendas não canceladas. "
        "Resultado = o que sobrou depois de custos e despesas. "
        "Diferente do Caixa: aqui vale a **data da venda/despesa** (regime de competência)."
    )

    if st.session_state.get("cargo") not in ("Administrador", "Funcionário"):
        st.warning("Acesso restrito.")
        return

    db = get_db()
    params = carregar_parametros()
    ano = int(params.get("ano", date.today().year))
    mes_atual = int(params.get("mes", 1))

    # ---------- SELETOR DE ANO ----------
    col_ano, col_info = st.columns([1, 3])
    with col_ano:
        anos_disponiveis = sorted(set([ano - 1, ano, ano + 1]))
        ano_sel = st.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(ano))
    with col_info:
        st.info(
            f"Alíquota de imposto (Parâmetros): **{pct(params.get('aliquota_imposto', 0))}**. "
            f"Mês analisado no Painel: **{MESES[mes_atual-1]}/{ano}**."
        )

    dre = _calcular_dre(db, ano_sel)

    st.divider()

    # ---------- BLOCO 1: RECEITA ----------
    st.subheader("1️⃣ Receita")
    st.dataframe(
        [
            _formatar_linha("Faturamento (receita bruta)", dre["faturamento"], bold=True),
            _formatar_linha("(−) Impostos", dre["impostos"]),
            _formatar_linha("= Receita líquida", dre["receita_liquida"], bold=True),
        ],
        use_container_width=True,
        hide_index=True,
    )

    # ---------- BLOCO 2: LUCRO BRUTO ----------
    st.subheader("2️⃣ Lucro bruto")
    st.dataframe(
        [
            _formatar_linha("(−) Custo das peças", dre["custo_pecas"]),
            _formatar_linha("= Lucro bruto", dre["lucro_bruto"], bold=True),
        ],
        use_container_width=True,
        hide_index=True,
    )

    # ---------- BLOCO 3: MARGEM DE CONTRIBUIÇÃO ----------
    st.subheader("3️⃣ Margem de contribuição")
    st.dataframe(
        [
            _formatar_linha("Lucro bruto", dre["lucro_bruto"]),
            _formatar_linha("(−) Taxas de pagamento", dre["taxas"]),
            _formatar_linha("(−) Embalagem", dre["embalagem"]),
            _formatar_linha("(−) Frete pago", dre["frete_pago"]),
            _formatar_linha("(−) Imposto estimado", dre["imposto_estimado"]),
            _formatar_linha("= Margem de contribuição (R$)", dre["margem_contribuicao"], bold=True),
            _formatar_linha("Margem de contribuição (%)", dre["margem_contribuicao_pct"], formato="pct"),
        ],
        use_container_width=True,
        hide_index=True,
    )

    # ---------- BLOCO 4: RESULTADO ----------
    st.subheader("4️⃣ Resultado operacional")
    st.dataframe(
        [
            _formatar_linha("Margem de contribuição", dre["margem_contribuicao"]),
            _formatar_linha("(−) Despesas operacionais", dre["despesas_operacionais"]),
            _formatar_linha("= Resultado operacional", dre["resultado"], bold=True),
            _formatar_linha("Ponto de equilíbrio (receita líquida)", dre["ponto_equilibrio"]),
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # ---------- MÊS EM DESTAQUE ----------
    st.subheader(f"📌 Mês de {MESES[mes_atual-1]}/{ano_sel}")
    idx = mes_atual - 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Faturamento", brl(dre["faturamento"][idx]))
    c2.metric("Margem de contribuição", brl(dre["margem_contribuicao"][idx]))
    c3.metric("Resultado operacional", brl(dre["resultado"][idx]))
    c4.metric("Ponto de equilíbrio", brl(dre["ponto_equilibrio"][idx]))

    st.divider()

    # ---------- GRÁFICO ----------
    st.subheader("📈 Faturamento, margem e resultado ao longo do ano")
    st.bar_chart(
        {
            "Faturamento": {MESES[i]: dre["faturamento"][i] for i in range(12)},
            "Margem contribuição": {MESES[i]: dre["margem_contribuicao"][i] for i in range(12)},
            "Resultado operacional": {MESES[i]: dre["resultado"][i] for i in range(12)},
        },
        use_container_width=True,
    )

    st.caption(
        "💡 O **DRE** é gerencial (regime de competência: venda entra no mês da venda, "
        "despesa no mês da despesa). O **Caixa** é regime de caixa (entra quando recebe, "
        "sai quando paga). Por isso os dois podem diferir no mesmo mês."
    )
