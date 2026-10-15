def get_help_message() -> str:
    """Retorna o menu de ajuda e boas-vindas com a lista de comandos do Clima-Zap."""
    return (
        "🌤️ *Clima-Zap — Menu de Comandos*\n\n"
        "Comandos funcionam em duas formas: */comando* ou *@clima-zap comando*:\n\n"
        "🔹 */clima* — Previsão do tempo da sua localização.\n"
        "🔹 */configuracao [cidade | lat,lon]* — Define seu local"
        " (ex: */configuracao Crato* ou */configuracao -7.23, -39.31*).\n"
        "🔹 */cidade <nome>* — Atalho para definir a cidade (ex: Barbalha, Crato).\n"
        "🔹 */inscrever* — Ativa o envio diário de alertas de chuva e clima.\n"
        "🔹 */sair* — Cancela a assinatura dos alertas diários.\n"
        "🔹 */ajuda* — Exibe este menu de ajuda.\n\n"
        "💡 _Em grupos, só respondo quando chamado com */comando* ou *@clima-zap*._\n"
        "💡 _Região de cobertura prioritária: Crajubar (Barbalha, Juazeiro e Crato)._"
    )
