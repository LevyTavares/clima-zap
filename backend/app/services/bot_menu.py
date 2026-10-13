# pylint: disable=duplicate-code


def get_help_message() -> str:
    """Retorna o menu de ajuda e boas-vindas com a lista de comandos do Clima-Zap."""
    return (
        "🌤️ *Clima-Zap — Menu de Comandos*\n\n"
        "Confira os comandos disponíveis para interagir com o bot:\n\n"
        "🔹 */clima* — Recebe a previsão do tempo atual para a sua localização.\n"
        "🔹 */cidade <nome>* — Define ou altera a sua cidade (ex: Barbalha, Crato, Juazeiro).\n"
        "🔹 */inscrever* — Ativa o envio diário de alertas de chuva e clima.\n"
        "🔹 */sair* — Cancela a assinatura dos alertas diários.\n"
        "🔹 */ajuda* — Exibe este menu de ajuda.\n\n"
        "💡 _Região de cobertura prioritária: Crajubar (Barbalha, Juazeiro e Crato)._"
    )
