def get_help_message() -> str:
    """Retorna o menu de ajuda e boas-vindas com a lista de comandos do Clima-Zap."""
    return (
        "🌤️ *Clima-Zap — Menu de Comandos*\n\n"
        "Comandos funcionam em duas formas: */comando* ou *@clima-zap comando*:\n\n"
        "🔹 */clima* — Previsão do tempo da sua localização.\n"
        "🔹 */configuracao [cidade | lat,lon | gps]* — Define seu local"
        " (ex: */configuracao Crato*, */configuracao -7.23, -39.31* ou */configuracao gps* para usar sua localização).\n"
        "🔹 Sem argumentos, */configuracao* e */cidade* mostram as cidades da região Crajubar "
        "(1️⃣ Barbalha, 2️⃣ Juazeiro do Norte, 3️⃣ Crato) — envie o número ou emoji para escolher.\n"
        "🔹 */cidade <nome>* — Atalho para definir a cidade (ex: Barbalha, Crato).\n"
        "🔹 */inscrever [alertas|boletins|todos]* — Inscreve em alertas climáticos e/ou boletins periódicos (padrão: todos).\n"
        "🔹 */sair [alertas|boletins|todos]* — Cancela a inscrição nos tipos informados.\n"
        "🔹 */ajuda* — Exibe este menu de ajuda.\n"
        "🔹 */agendar HH:MM* — (em grupos) agenda boletim personalizado (ex: */agendar 06:30*). Use */agendar off* para desativar.\n\n"
        "💡 _Em grupos, só respondo quando chamado com */comando* ou *@clima-zap*._\n"
        "💡 _Região de cobertura prioritária: Crajubar (Barbalha, Juazeiro e Crato)._"
    )
