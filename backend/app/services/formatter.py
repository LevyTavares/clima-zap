import random

def get_greeting() -> str:
    """Retorna uma saudação amigável e variada."""
    greetings = [
        "Bom dia, pessoal! 🌵",
        "E aí, como estamos hoje? ☀️",
        "Passando com as atualizações do clima! 🌤️",
        "Olá! Aqui é o seu boletim diário do Clima-Zap 📱"
    ]
    return random.choice(greetings)

def format_daily_summary(city: str, temp_min: float, temp_max: float, humidity: int, uv_index: float, rain_prob: int) -> str:
    """
    Gera a mensagem de resumo diário formatada para o WhatsApp.
    """
    # Lógica de Ícones e Alertas de UV
    uv_alert = "☀️" if uv_index < 6 else "🧴"
    uv_text = f"{uv_alert} *Índice UV:* {uv_index} "
    uv_text += "(_Muito Alto! Proteja-se_)" if uv_index >= 8 else "(_Tranquilo_)"

    # Lógica de Dicas de Saúde e Rotina (Foco no clima regional)
    health_tip = ""
    if humidity <= 30:
        health_tip = "_Dica: A umidade está de deserto hoje! Beba muita água e evite exposição ao sol entre 10h e 16h._ 🚰"
    elif rain_prob >= 70:
        health_tip = "_Dica: Tempo fechado! Leve o guarda-chuva se for sair para não ser pego de surpresa._ ☂️"
    elif uv_index >= 8:
        health_tip = "_Dica: O sol está rachando! Não saia de casa sem protetor solar e óculos escuros._ 😎"
    else:
        health_tip = "_Dica: Clima agradável hoje, aproveite o dia!_ 🍃"

    greeting = get_greeting()

    # Montagem final usando f-strings e formatação do WhatsApp (*negrito*, _itálico_)
    message = (
        f"{greeting}\n\n"
        f"📍 *Previsão para {city}*\n\n"
        f"🌡️ *Temperatura:* {temp_min}°C a {temp_max}°C\n"
        f"💧 *Umidade:* {humidity}%\n"
        f"🌧️ *Chance de Chuva:* {rain_prob}%\n"
        f"{uv_text}\n\n"
        f"{health_tip}"
    )
    
    return message

def format_urgent_alert(city: str, alert_type: str, severity: str, value: str, recommendation: str) -> str:
    """
    Gera mensagens de alertas urgentes para situações extremas.
    """
    # Define o ícone de cabeçalho baseado na gravidade/tipo
    icon = "⚠️"
    if "chuva" in alert_type.lower() or "tempestade" in alert_type.lower():
        icon = "⛈️"
    elif "seco" in alert_type.lower() or "umidade" in alert_type.lower():
        icon = "🏜️"
    elif "calor" in alert_type.lower() or "uv" in alert_type.lower():
        icon = "🔥"

    message = (
        f"🚨 *ALERTA CLIMA-ZAP: {city.upper()}* 🚨\n\n"
        f"{icon} *Aviso:* {alert_type}\n"
        f"🔴 *Nível:* {severity}\n"
        f"📊 *Condição Atual:* {value}\n\n"
        f"🛡️ *O que fazer:*\n"
        f"_{recommendation}_"
    )
    
    return message