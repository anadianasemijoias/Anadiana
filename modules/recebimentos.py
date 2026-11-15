import streamlit as st
from datetime import datetime, date
from bson import ObjectId
from modules.utils import get_db, brl
from modules.vendas import _recalcular_venda


def _apenas_admin_ou_func():
    if st.session_state.get("cargo") not in ("Administrador", "Funcionário"):
        st.warning("Acesso restrito.")
        return False
    return True


def _vendas_com_saldo(db):
    """Retorna vendas não canceladas com saldo > 0."""
    vendas = list(
        db["vendas"].find({
            "status": {"$ne": "Cancelada"},
            "saldo_a_receber": {"$gt": 0.005},
        }).sort("data_venda", -1)
    )
    return vendas


def _parcelas_da_venda(venda, recebidos):
    """Monta lista de parcelas com status (paga/em aberto/vencida)."""
    num_parcelas = int(venda.get("num_parcelas", 0))
    if num_parcelas <= 0:
        return []

    primeiro = venda.get("primeiro_vencimento")
    if not primeiro:
        return []

    valor_parcela = venda.get("valor_parcela", 0)
    total = venda.get("total_venda", 0)
    entrada = venda.get("entrada", 0)
    financiado = venda.get("valor_financiado", 0)

    # Última parcela absorve diferença de centavos
    valor_ultima = round(financiado - valor_parcela * (num_parcelas - 1), 2)

    hoje = date.today()
    venc_base = primeiro.date() if isinstance(primeiro, datetime) else primeiro

    # Marca quais parcelas já foram recebidas (por número)
    recebidas = {}
    for r in recebidos:
        recebidas[int(r.get("numero_parcela", 0))] = r

    lista = []
    for i in range(1, num_parcelas + 1):
        ano = venc_base.year + (venc_base.month - 1 + (i - 1)) // 12
        mes = (venc_base.month - 1 + (i - 1)) % 12 + 1
        dia = min(venc_base.day, 28)
        venc = date(ano, mes, dia)

        valor = valor_ultima if i == num_parcelas else valor_parcela
        r = recebidas.get(i)
        if r:
            status = "Paga"
            data_pgto = r.get("data_recebimento")
        else:
            if venc < hoje:
                status = "Vencida"
            else:
                status = "Em aberto"
            data_pgto = None

        lista.append({
            "numero": i,
            "vencimento": venc,
            "valor": valor,
            "status": status,
            "data_recebimento": data_pgto,
            "recebimento_id": r["_id"] if r else None,
        })
    return lista


def tela_recebimentos():
    st.header("💳 Recebimentos (Crediário)")
    st.caption(
        "Lance aqui cada parcela paga pela cliente. "
        "A **entrada** ou o **pagamento à vista** fica na própria venda e **não** entra aqui."
    )

    if not _apenas_admin_ou_func():
        return

    db = get_db()
    col = db["recebimentos"]

    # ---------- LISTAGEM GERAL ----------
    st.subheader("Recebimentos lançados")
    recebimentos = list(col.find({}).sort("data_recebimento", -1).limit(300))

    if recebimentos:
        linhas = []
        for r in recebimentos:
            linhas.append({
                "Data": r["data_recebimento"].strftime("%d/%m/%Y") if r.get("data_recebimento") else "",
                "Venda": r.get("numero_venda", ""),
                "Parcela": r.get("numero_parcela", ""),
                "Valor": brl(r.get("valor", 0)),
                "Forma": r.get("forma_recebimento", ""),
                "Obs.": r.get("observacoes", ""),
                "Lançado por": r.get("criado_por", ""),
            })
        st.dataframe(linhas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum recebimento lançado ainda.")

    st.divider()

    # ---------- NOVO RECEBIMENTO ----------
    st.subheader("➕ Lançar recebimento")

    vendas = _vendas_com_saldo(db)
    if not vendas:
        st.success("✅ Nenhuma venda com saldo em aberto no momento.")
        return

    opcoes_venda = {
        f"{v['numero_venda']} · {v.get('cliente','')} · saldo {brl(v.get('saldo_a_receber',0))}": v
        for v in vendas
    }
    escolha = st.selectbox("Selecione a venda", list(opcoes_venda.keys()))
    venda = opcoes_venda[escolha]
    venda_id = str(venda["_id"])
    num_venda = venda["numero_venda"]

    # Busca recebimentos dessa venda
    recebidos = list(col.find({"numero_venda": num_venda}))
    parcelas = _parcelas_da_venda(venda, recebidos)

    if not parcelas:
        st.warning(
            "Esta venda não tem parcelas programadas. "
            "Se for pagamento à vista, use o campo **Entrada** na edição da venda."
        )
        return

    # Mostra o quadro de parcelas
    st.markdown(f"**Parcelas da venda {num_venda}**")
    st.dataframe(
        [
            {
                "Parcela": f"{p['numero']}/{len(parcelas)}",
                "Vencimento": p["vencimento"].strftime("%d/%m/%Y"),
                "Valor": brl(p["valor"]),
                "Status": p["status"],
                "Recebido em": p["data_recebimento"].strftime("%d/%m/%Y") if p["data_recebimento"] else "—",
            }
            for p in parcelas
        ],
        use_container_width=True,
        hide_index=True,
    )

    # Parcelas em aberto ou vencidas
    disponiveis = [p for p in parcelas if p["status"] in ("Em aberto", "Vencida")]
    if not disponiveis:
        st.success("✅ Todas as parcelas desta venda já foram recebidas.")
        return

    st.markdown("---")
    with st.form("novo_recebimento", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            parcela_escolhida = st.selectbox(
                "Parcela a receber *",
                disponiveis,
                format_func=lambda p: (
                    f"{p['numero']}/{len(parcelas)} · venc. {p['vencimento'].strftime('%d/%m/%Y')} · "
                    f"{brl(p['valor'])} · {p['status']}"
                ),
            )
        with col2:
            data_receb = st.date_input("Data do recebimento *", value=date.today())
            valor = st.number_input(
                "Valor recebido (R$) *",
                min_value=0.0,
                value=float(parcela_escolhida["valor"]),
                step=0.5,
                format="%.2f",
            )
        with col3:
            forma = st.selectbox(
                "Forma de recebimento",
                ["Pix", "Dinheiro", "Transferência", "Cartão", "Outro"],
            )
            obs = st.text_input("Observações")

        submit = st.form_submit_button("💾 Registrar recebimento")

        if submit:
            erros = []
            if valor <= 0:
                erros.append("O valor deve ser maior que zero.")
            if valor > venda.get("saldo_a_receber", 0) + 0.005:
                erros.append(
                    f"O valor ({brl(valor)}) é maior que o saldo devedor "
                    f"({brl(venda.get('saldo_a_receber', 0))})."
                )

            if erros:
                for e in erros:
                    st.error(e)
            else:
                col.insert_one({
                    "numero_venda": num_venda,
                    "numero_parcela": parcela_escolhida["numero"],
                    "data_recebimento": datetime.combine(data_receb, datetime.min.time()),
                    "valor": float(valor),
                    "forma_recebimento": forma,
                    "observacoes": obs,
                    "criado_em": datetime.now(),
                    "criado_por": st.session_state.get("usuario_logado"),
                })
                # Recalcula a venda (saldo, atraso, situação)
                _recalcular_venda(db, venda_id)
                st.success(f"Recebimento de {brl(valor)} registrado para {num_venda}.")
                st.rerun()

    st.divider()

    # ---------- EXCLUIR RECEBIMENTO ----------
    st.subheader("🗑️ Excluir recebimento")
    receb_da_venda = list(col.find({"numero_venda": num_venda}))
    if not receb_da_venda:
        st.info("Esta venda ainda não tem recebimentos lançados.")
        return

    opcoes_rec = {
        f"Parcela {r['numero_parcela']} · {r['data_recebimento'].strftime('%d/%m/%Y')} · {brl(r['valor'])}": r
        for r in receb_da_venda
    }
    escolha_r = st.selectbox("Selecione o recebimento", list(opcoes_rec.keys()))
    r = opcoes_rec[escolha_r]

    if st.button("Excluir recebimento selecionado"):
        col.delete_one({"_id": r["_id"]})
        _recalcular_venda(db, venda_id)
        st.success("Recebimento excluído e venda recalculada.")
        st.rerun()

    st.caption(
        "💡 Ao excluir um recebimento, o saldo a receber, o atraso e a situação da venda "
        "são recalculados automaticamente. A **entrada** da venda não aparece aqui — "
        "ela é registrada no próprio cabeçalho da venda."
    )
