
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

PERIOD_GREETINGS = {
    "morning": [
        "Bom dia, pessoal! 🌅",
        "Bom dia! Resumo do clima pra hoje de manhã 🌤️",
        "Acordou? Aqui vai a previsão da manhã ☕",
        "Bom dia! Comece o dia informado 🌵",
    ],
    "afternoon": [
        "Boa tarde, pessoal! ☀️",
        "Passando pra atualizar o clima da tarde 🌡️",
        "Boa tarde! Como está o tempo aí? 🌤️",
        "Meio do dia! Previsão pra tarde 🔆",
    ],
    "night": [
        "Boa noite, pessoal! 🌙",
        "Resumo da noite e madrugada 🌌",
        "Boa noite! Previsão pra agora e amanhã de manhã 🌠",
        "Antes de dormir, o clima da noite 🦉",
    ],
}

PERIOD_LABELS = {
    "morning": "Manhã",
    "afternoon": "Tarde",
    "night": "Noite / Madrugada",
}

PERIOD_WINDOWS = {
    "morning": "06h às 12h",
    "afternoon": "12h às 18h",
    "night": "18h às 06h",
}

# weather_code Open-Meteo → descrição curta (WMO)
WEATHER_CODE_TEXT = {
    0: "Céu limpo",
    1: "Predominantemente limpo",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Névoa",
    48: "Névoa com geada",
    51: "Garoa fraca",
    53: "Garoa",
    55: "Garoa forte",
    61: "Chuva fraca",
    63: "Chuva",
    65: "Chuva forte",
    71: "Neve fraca",
    73: "Neve",
    75: "Neve forte",
    80: "Pancadas isoladas",
    81: "Pancadas de chuva",
    82: "Pancadas fortes",
    95: "Tempestade",
    96: "Tempestade com granizo",
    99: "Tempestade forte com granizo",
}


def get_period_greeting(period: str) -> str:
    return random.choice(PERIOD_GREETINGS.get(period, PERIOD_GREETINGS["morning"]))


def weather_code_to_text(code: int) -> str:
    return WEATHER_CODE_TEXT.get(code, f"Código {code}")


def format_period_summary(
    city: str,
    period: str,
    temp_min: float,
    temp_max: float,
    humidity_avg: int,
    rain_prob_max: int,
    uv_max: float,
    weather_codes: list[int],
) -> str:
    """Mensagem de boletim por período (manhã/tarde/noite) para WhatsApp."""
    uv_alert = "☀️" if uv_max < 6 else "🧴"
    uv_text = f"{uv_alert} *Índice UV (pico):* {uv_max} "
    uv_text += "(_Muito Alto! Proteja-se_)" if uv_max >= 8 else "(_Tranquilo_)"

    # condição predominante = código mais frequente
    main_code = max(set(weather_codes), key=weather_codes.count) if weather_codes else 0
    condition = weather_code_to_text(main_code)

    if rain_prob_max >= 70:
        health_tip = "_Dica: Tempo fechado! Leve o guarda-chuva se for sair._ ☂️"
    elif uv_max >= 8:
        health_tip = "_Dica: Sol forte! Protetor solar e óculos não podem faltar._ 😎"
    elif humidity_avg <= 30:
        health_tip = "_Dica: Umidade baixa — beba bastante água._ 🚰"
    else:
        health_tip = "_Dica: Clima agradável, aproveite!_ 🍃"

    label = PERIOD_LABELS.get(period, period)
    window = PERIOD_WINDOWS.get(period, "")
    greeting = get_period_greeting(period)

    return (
        f"{greeting}\n\n"
        f"📍 *Previsão {label} — {city}*\n"
        f"🕐 Janela: {window}\n"
        f"🌤️ *Condição:* {condition}\n\n"
        f"🌡️ *Temperatura:* {temp_min:.0f}°C a {temp_max:.0f}°C\n"
        f"💧 *Umidade (média):* {humidity_avg}%\n"
        f"🌧️ *Chance de Chuva (pico):* {rain_prob_max:.0f}%\n"
        f"{uv_text}\n\n"
        f"{health_tip}"
    )

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