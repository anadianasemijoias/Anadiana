    opcoes = [
        "🏠 Início",
        "🎯 Painel",
        "⚙️ Parâmetros",
        "📦 Produtos",
        "🛒 Compras",
        "💰 Vendas",
        "💳 Recebimentos",
        "🧾 Despesas",
        "🤝 Sócios",
        "🔄 Ajustes",
        "💵 Caixa",
        "📊 DRE",
    ]
    if st.session_state.get("cargo") == "Administrador":
        opcoes.append("👥 Usuários")
