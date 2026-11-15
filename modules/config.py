import streamlit as st
from modules.utils import get_db, brl

FORMAS_PAGAMENTO_PADRAO = [
    "Pix",
    "Dinheiro",
    "Cartão de Débito",
    "Cartão de Crédito (à vista)",
    "Cartão de Crédito (parcelado)",
    "Crediário (parcelado próprio)",
    "Transferência",
]

def carregar_parametros():
    """Retorna o documento de parâmetros, criando um padrão se não existir."""
    db = get_db()
    col = db["parametros"]
    doc = col.find_one({"_tipo": "global"})

    if not doc:
        doc = {
            "_tipo": "global",
            "ano": 2026,
            "mes": 1,
            "saldo_inicial_caixa": 0.0,
            "custo_embalagem": 2.0,
            "margem_desejada": 0.30,
            "aliquota_imposto": 0.06,
            "limite_faturamento_anual": 81000.0,
            "taxas_pagamento": {f: 0.0 for f in FORMAS_PAGAMENTO_PADRAO},
        }
        col.insert_one(doc)
    return doc

def salvar_parametros(dados):
    db = get_db()
    db["parametros"].update_one(
        {"_tipo": "global"}, {"$set": dados}, upsert=True
    )

def tela_config():
    st.header("⚙️ Parâmetros do Sistema")
    st.caption("Revise os valores abaixo. Eles são ilustrativos e devem ser ajustados.")

    if st.session_state.get("cargo") != "Administrador":
        st.warning("Apenas administradores podem alterar os parâmetros.")
        return

    p = carregar_parametros()

    with st.form("form_parametros"):
        st.subheader("📅 Período de análise")
        col1, col2 = st.columns(2)
        with col1:
            ano = st.number_input("Ano", min_value=2020, max_value=2100,
                                  value=int(p.get("ano", 2026)), step=1)
        with col2:
            mes = st.number_input("Mês (1-12)", min_value=1, max_value=12,
                                  value=int(p.get("mes", 1)), step=1)

        st.subheader("💰 Custos e margens")
        col1, col2 = st.columns(2)
        with col1:
            saldo_inicial = st.number_input(
                "Saldo inicial de caixa (R$)",
                min_value=0.0, value=float(p.get("saldo_inicial_caixa", 0.0)),
                step=50.0, format="%.2f",
            )
            custo_embalagem = st.number_input(
                "Custo de embalagem por venda (R$)",
                min_value=0.0, value=float(p.get("custo_embalagem", 2.0)),
                step=0.5, format="%.2f",
            )
        with col2:
            margem_desejada = st.number_input(
                "Margem desejada (%)",
                min_value=0.0, max_value=99.0,
                value=float(p.get("margem_desejada", 0.30)) * 100,
                step=1.0, format="%.1f",
            ) / 100
            aliquota_imposto = st.number_input(
                "Alíquota de imposto (%)",
                min_value=0.0, max_value=99.0,
                value=float(p.get("aliquota_imposto", 0.06)) * 100,
                step=0.5, format="%.1f",
            ) / 100

        st.subheader("📊 Limite anual de faturamento")
        limite = st.number_input(
            "Limite anual de faturamento (R$)",
            min_value=0.0, value=float(p.get("limite_faturamento_anual", 81000.0)),
            step=1000.0, format="%.2f",
        )

        st.subheader("💳 Taxas por forma de pagamento (%)")
        st.caption("Informe a taxa em % (ex.: 1.5 para 1,5%).")
        taxas_atuais = p.get("taxas_pagamento", {})
        taxas_novas = {}
        for forma in FORMAS_PAGAMENTO_PADRAO:
            valor = st.number_input(
                f"{forma} (%)",
                min_value=0.0, max_value=100.0,
                value=float(taxas_atuais.get(forma, 0.0)) * 100,
                step=0.1, format="%.2f",
                key=f"taxa_{forma}",
            )
            taxas_novas[forma] = valor / 100

        salvar = st.form_submit_button("💾 Salvar Parâmetros")

    if salvar:
        salvar_parametros({
            "ano": int(ano),
            "mes": int(mes),
            "saldo_inicial_caixa": saldo_inicial,
            "custo_embalagem": custo_embalagem,
            "margem_desejada": margem_desejada,
            "aliquota_imposto": aliquota_imposto,
            "limite_faturamento_anual": limite,
            "taxas_pagamento": taxas_novas,
        })
        st.success("Parâmetros salvos com sucesso!")
        st.rerun()

    # Resumo visual
    st.divider()
    st.subheader("📌 Resumo atual")
    p2 = carregar_parametros()
    st.write(f"**Período:** {p2['mes']:02d}/{p2['ano']}")
    st.write(f"**Saldo inicial de caixa:** {brl(p2['saldo_inicial_caixa'])}")
    st.write(f"**Custo de embalagem por venda:** {brl(p2['custo_embalagem'])}")
    st.write(f"**Margem desejada:** {p2['margem_desejada']*100:.1f}%")
    st.write(f"**Alíquota de imposto:** {p2['aliquota_imposto']*100:.1f}%")
    st.write(f"**Limite anual de faturamento:** {brl(p2['limite_faturamento_anual'])}")
    st.write("**Taxas por forma de pagamento:**")
    for forma, taxa in p2.get("taxas_pagamento", {}).items():
        st.write(f"- {forma}: {taxa*100:.2f}%")
