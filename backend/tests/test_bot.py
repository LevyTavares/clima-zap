from app.services.bot_menu import get_help_message


def test_get_help_message_content():
    help_text = get_help_message()

    assert "Clima-Zap" in help_text
    assert "*/clima*" in help_text
    assert "*/cidade <nome>*" in help_text
    assert "*/inscrever*" in help_text
    assert "*/sair*" in help_text
    assert "*/ajuda*" in help_text