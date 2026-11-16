from app.services.bot_menu import get_help_message


def test_get_help_message_content():
    help_text = get_help_message()

    assert "Clima-Zap" in help_text
    assert "*/clima*" in help_text
    assert "*/configuracao" in help_text
    assert "*/inscrever" in help_text
    assert "*/sair" in help_text
    assert "*/ajuda [comando]*" in help_text

    janela = get_help_message("janelas")
    assert "Janela da previsão" in janela
    assert "/clima" in get_help_message("/previzão")
    assert "Comando desconhecido" in get_help_message("inexistente")