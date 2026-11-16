"""Menu e ajuda do bot — fonte única do texto de `/ajuda` e `/ajuda <comando>`."""

from app.services.command_parser import canonical_command

# (comando canônico, uso, descrição). O menu completo e a ajuda por comando
# saem daqui: mudar o texto de um comando é uma edição só.
COMMANDS: list[tuple[str, str, str]] = [
    ("clima", "/clima", "Previsão da sua localização na janela do /janela."),
    ("comparar", "/comparar", "Barbalha, Juazeiro do Norte e Crato lado a lado."),
    (
        "configuracao",
        "/configuracao [cidade | lat,lon | gps | padrao]",
        "Define o local; sem argumento mostra as opções numeradas (/cidade é atalho).",
    ),
    (
        "janela",
        "/janela [1h|2h|3h|4h|padrao]",
        "Janela da previsão de /clima e /comparar (padrão: 1h).",
    ),
    (
        "inscrever",
        "/inscrever [alertas|boletins|todos]",
        "Ativa alertas e/ou boletins (padrão: todos).",
    ),
    (
        "sair",
        "/sair [alertas|boletins|todos]",
        "Cancela os tipos informados (padrão: todos).",
    ),
    (
        "agendar",
        "/agendar HH:MM | off",
        "Agenda o boletim personalizado deste grupo.",
    ),
    ("status", "/status", "Estado da API e da instância WhatsApp."),
    ("ajuda", "/ajuda [comando]", "Este menu, ou a ajuda de um comando."),
]


def get_help_message(topic: str | None = None) -> str:
    """Menu completo ou ajuda de um comando (``/ajuda janela``)."""
    wanted = canonical_command(topic.strip().lower()) if topic else ""
    if wanted:
        for command, usage, description in COMMANDS:
            if command == wanted:
                return f"*{usage}*\n{description}"
        known = ", ".join(f"/{command}" for command, _, _ in COMMANDS)
        return f"❓ Comando desconhecido: *{topic}*.\nComandos: {known}."

    lines = "\n".join(
        f"🔹 *{usage}* — {description}" for _, usage, description in COMMANDS
    )
    return (
        "🌤️ *Clima-Zap — Menu de Comandos*\n\n"
        "Use */comando* ou *@clima-zap comando*:\n\n"
        f"{lines}\n\n"
        "💡 _Em grupos, só respondo quando chamado com */comando* ou *@clima-zap*._\n"
        "💡 _Região de cobertura prioritária: Crajubar (Barbalha, Juazeiro e Crato)._"
    )
