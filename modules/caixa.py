import streamlit as st
from datetime import datetime, date
from modules.utils import get_db, brl
from modules.config import carregar_parametros


MESES = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]


def _periodo(ano, mes):
    """Retorna (inicio, fim) do mês como datetime."""
    inicio = datetime(ano, mes, 1)
    if mes == 12:
        fim = datetime(ano + 1, 1, 1)
    else:
        fim = datetime(ano, mes + 1, 1)
    return inicio, fim


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


def _linhas_caixa(db, ano):
    """Calcula todas as linhas do caixa para o ano informado."""
    params = carregar_parametros()
    saldo_inicial = float(params.get("saldo_inicial_caixa", 0.0))

    # ENTRADAS
    vendas_avista = _soma_por_mes(
        db["vendas"], "data_venda", "entrada", ano,
        filtro_extra={"status": {"$ne": "Cancelada"}},
    )
    parcelas = _soma_por_mes(db["recebimentos"], "data_recebimento", "valor", ano)
    aportes = _soma_por_mes(
        db["socios"], "data_movimento", "valor", ano,
        filtro_extra={"tipo": "Aporte"},
    )

    # SAÍDAS
    compras_pagas = _soma_por_mes(
        db["compras"], "data_pagamento", "valor_total", ano,
    )
    despesas_pagas = _soma_por_mes(
        db["despesas"], "data_pagamento", "valor", ano,
    )
    retiradas = _soma_por_mes(
        db["socios"], "data_movimento", "valor", ano,
        filtro_extra={"tipo": "Retirada"},
    )

    entradas_mes = [vendas_avista[i] + parcelas[i] + aportes[i] for i in range(12)]
    saidas_mes = [compras_pagas[i] + despesas_pagas[i] + retiradas[i] for i in range(12)]
    saldo_mes = [entradas_mes[i] - saidas_mes[i] for i in range(12)]

    # Saldo acumulado mês a mês (partindo do saldo inicial)
    saldo_acumulado = []
    acumulado = saldo_inicial
    for i in range(12):
        acumulado += saldo_mes[i]
        saldo_acumulado.append(acumulado)

    return {
        "saldo_inicial": saldo_inicial,
        "vendas_avista": vendas_avista,
        "parcelas": parcelas,
        "aportes": aportes,
        "entradas_mes": entradas_mes,
        "compras_pagas": compras_pagas,
        "despesas_pagas": despesas_pagas,
        "retiradas": retiradas,
        "saidas_mes": saidas_mes,
        "saldo_mes": saldo_mes,
        "saldo_acumulado": saldo_acumulado,
    }


def _formatar_linha(label, valores, bold=False):
    """Formata uma linha (label + 12 valores) para o dataframe."""
    linha = {"Item": f"**{label}**" if bold else label}
    for i, m in enumerate(MESES):
        linha[m] = brl(valores[i])
    return linha


def tela_caixa():
    st.header("💰 Caixa")
    st.caption(
        "**Não precisa de digitação.** Entradas = vendas à vista + parcelas recebidas + aportes. "
        "Saídas = compras pagas + despesas pagas + retiradas. "
        "A data que vale é a do **pagamento/recebimento** — não a da venda ou compra."
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
        anos_disponiveis = [ano]
        # Permite consultar anos anteriores/posteriores
        anos_disponiveis = sorted(set(
            [ano - 1, ano, ano + 1]
        ))
        ano_sel = st.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(ano))
    with col_info:
        st.info(
            f"Saldo inicial de caixa (Parâmetros): **{brl(params.get('saldo_inicial_caixa', 0))}**. "
            f"Mês analisado no Painel: **{MESES[mes_atual-1]}/{ano}**."
        )

    caixa = _linhas_caixa(db, ano_sel)

    st.divider()

    # ---------- LINHAS DO CAIXA ----------
    st.subheader("📊 Movimento do ano (mês a mês)")

    # Entradas
    st.markdown("#### 🟢 Entradas")
    entradas_df = [
        _formatar_linha("Vendas à vista (entrada)", caixa["vendas_avista"]),
        _formatar_linha("Parcelas recebidas", caixa["parcelas"]),
        _formatar_linha("Aportes de sócios", caixa["aportes"]),
        _formatar_linha("TOTAL DE ENTRADAS", caixa["entradas_mes"], bold=True),
    ]
    st.dataframe(entradas_df, use_container_width=True, hide_index=True)

    # Saídas
    st.markdown("#### 🔴 Saídas")
    saidas_df = [
        _formatar_linha("Compras pagas", caixa["compras_pagas"]),
        _formatar_linha("Despesas pagas", caixa["despesas_pagas"]),
        _formatar_linha("Retiradas de sócios", caixa["retiradas"]),
        _formatar_linha("TOTAL DE SAÍDAS", caixa["saidas_mes"], bold=True),
    ]
    st.dataframe(saidas_df, use_container_width=True, hide_index=True)

    # Resultado
    st.markdown("#### 💰 Resultado do caixa")
    resultado_df = [
        _formatar_linha("SALDO DO MÊS", caixa["saldo_mes"], bold=True),
        _formatar_linha("SALDO ACUMULADO", caixa["saldo_acumulado"], bold=True),
    ]
    st.dataframe(resultado_df, use_container_width=True, hide_index=True)

    st.divider()

    # ---------- MÊS EM DESTAQUE ----------
    st.subheader(f"📌 Mês de {MESES[mes_atual-1]}/{ano_sel}")
    idx = mes_atual - 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entradas", brl(caixa["entradas_mes"][idx]))
    c2.metric("Saídas", brl(caixa["saidas_mes"][idx]))
    c3.metric("Saldo do mês", brl(caixa["saldo_mes"][idx]))
    c4.metric("Saldo acumulado", brl(caixa["saldo_acumulado"][idx]))

    st.divider()

    # ---------- GRÁFICO SIMPLES (barras por mês) ----------
    st.subheader("📈 Saldo acumulado ao longo do ano")
    st.bar_chart(
        {MESES[i]: caixa["saldo_acumulado"][i] for i in range(12)},
        use_container_width=True,
    )

    st.caption(
        "💡 **Vendas a prazo** não entram no caixa na data da venda — só quando a "
        "parcela é recebida (módulo Recebimentos). **Despesas pendentes** não entram "
        "no caixa até serem pagas. Por isso o caixa pode diferir do lucro (DRE)."
    )
