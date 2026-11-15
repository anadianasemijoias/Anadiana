import streamlit as st
from datetime import datetime, date
from bson import ObjectId
from modules.utils import get_db, brl


TIPOS_MOVIMENTO = ["Aporte", "Retirada"]


def _apenas_admin_ou_func():
    if st.session_state.get("cargo") not in ("Administrador", "Funcionário"):
        st.warning("Acesso restrito.")
        return False
    return True


def tela_socios():
    st.header("🤝 Sócios — Aportes e Retiradas")
    st.caption(
        "Aportes entram como **entrada** de caixa; retiradas como **saída**. "
        "Diferente de Despesas: aqui é movimento de capital dos sócios."
    )

    if not _apenas_admin_ou_func():
        return

    db = get_db()
    col = db["socios"]

    # ---------- LISTAGEM ----------
    st.subheader("Movimentos lançados")
    movimentos = list(col.find({}).sort("data_movimento", -1).limit(300))

    if movimentos:
        linhas = []
        for m in movimentos:
            linhas.append({
                "Data": m["data_movimento"].strftime("%d/%m/%Y") if m.get("data_movimento") else "",
                "Sócio": m.get("socio", ""),
                "Tipo": m.get("tipo", ""),
                "Valor": brl(m.get("valor", 0)),
                "Observações": m.get("observacoes", ""),
                "Lançado por": m.get("criado_por", ""),
            })
        st.dataframe(linhas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum movimento lançado ainda.")

    st.divider()

    # ---------- CADASTRO ----------
    with st.expander("➕ Lançar novo movimento", expanded=not movimentos):
        with st.form("novo_movimento", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                data_mov = st.date_input("Data do movimento *", value=date.today())
            with col2:
                socio = st.text_input("Sócio *")
                tipo = st.selectbox("Tipo *", TIPOS_MOVIMENTO)
            with col3:
                valor = st.number_input(
                    "Valor (R$) *", min_value=0.0, value=0.0,
                    step=0.5, format="%.2f",
                )

            obs = st.text_area("Observações", height=60)

            submit = st.form_submit_button("💾 Lançar movimento")

            if submit:
                erros = []
                if not socio:
                    erros.append("Informe o sócio.")
                if valor <= 0:
                    erros.append("O valor deve ser maior que zero.")

                if erros:
                    for e in erros:
                        st.error(e)
                else:
                    col.insert_one({
                        "data_movimento": datetime.combine(data_mov, datetime.min.time()),
                        "socio": socio,
                        "tipo": tipo,
                        "valor": float(valor),
                        "observacoes": obs,
                        "criado_em": datetime.now(),
                        "criado_por": st.session_state.get("usuario_logado"),
                    })
                    st.success(f"{tipo} de {brl(valor)} lançado para {socio}.")
                    st.rerun()

    st.divider()

    # ---------- EDIÇÃO ----------
    st.subheader("✏️ Editar movimento")
    if not movimentos:
        st.info("Nenhum movimento para editar.")
        return

    opcoes = {
        f"{m['data_movimento'].strftime('%d/%m/%Y') if m.get('data_movimento') else '—'} · "
        f"{m.get('socio','')} · {m.get('tipo','')} · {brl(m.get('valor',0))}": m
        for m in movimentos
    }
    escolha = st.selectbox("Selecione o movimento", list(opcoes.keys()))
    m = opcoes[escolha]
    mov_id = str(m["_id"])

    with st.form("editar_movimento"):
        col1, col2, col3 = st.columns(3)
        with col1:
            nova_data = st.date_input(
                "Data",
                value=m["data_movimento"].date() if m.get("data_movimento") else date.today(),
            )
        with col2:
            novo_socio = st.text_input("Sócio", value=m.get("socio", ""))
            idx_tipo = TIPOS_MOVIMENTO.index(m["tipo"]) if m.get("tipo") in TIPOS_MOVIMENTO else 0
            novo_tipo = st.selectbox("Tipo", TIPOS_MOVIMENTO, index=idx_tipo)
        with col3:
            novo_valor = st.number_input(
                "Valor (R$)", min_value=0.0,
                value=float(m.get("valor", 0.0)), step=0.5, format="%.2f",
            )

        nova_obs = st.text_area("Observações", value=m.get("observacoes", ""), height=60)

        salvar = st.form_submit_button("💾 Salvar alterações")

        if salvar:
            col.update_one(
                {"_id": ObjectId(mov_id)},
                {"$set": {
                    "data_movimento": datetime.combine(nova_data, datetime.min.time()),
                    "socio": novo_socio,
                    "tipo": novo_tipo,
                    "valor": float(novo_valor),
                    "observacoes": nova_obs,
                    "atualizado_em": datetime.now(),
                    "atualizado_por": st.session_state.get("usuario_logado"),
                }},
            )
            st.success("Movimento atualizado!")
            st.rerun()

    st.divider()

    # ---------- EXCLUIR ----------
    st.subheader("🗑️ Excluir movimento")
    if st.button("Excluir movimento selecionado"):
        col.delete_one({"_id": m["_id"]})
        st.success("Movimento excluído.")
        st.rerun()

    st.divider()

    # ---------- RESUMO POR SÓCIO ----------
    st.subheader("📊 Resumo por sócio")
    if movimentos:
        agregados = {}
        for m in movimentos:
            s = m.get("socio", "—")
            if s not in agregados:
                agregados[s] = {"Aporte": 0.0, "Retirada": 0.0}
            agregados[s][m.get("tipo", "Aporte")] += m.get("valor", 0)

        linhas = []
        for s, v in agregados.items():
            saldo = v["Aporte"] - v["Retirada"]
            linhas.append({
                "Sócio": s,
                "Aportes": brl(v["Aporte"]),
                "Retiradas": brl(v["Retirada"]),
                "Saldo (Aporte − Retirada)": brl(saldo),
            })
        st.dataframe(linhas, use_container_width=True, hide_index=True)

    st.caption(
        "💡 **Aporte** = dinheiro que o sócio colocou na empresa (entrada de caixa). "
        "**Retirada** = dinheiro que o sócio tirou (saída de caixa). "
        "Esse módulo **não** é despesa operacional — é movimento de capital."
    )
