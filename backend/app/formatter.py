"""Formatadores de mensagem para WhatsApp.

Um único conjunto de peças (faixa de temperatura, linha de UV, dica de saúde)
usado pelos três formatos — janela on-demand, período e comparativo — para
tom e precisão não divergirem entre eles.
"""

import random

from app.core.clock import local_now

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


def time_greeting() -> str:
    """Saudação baseada na hora local (America/Fortaleza)."""
    hour = local_now().hour
    if 5 <= hour < 12:
        return "Bom dia! ☀️"
    if 12 <= hour < 18:
        return "Boa tarde! 🌤️"
    return "Boa noite! 🌙"


def get_period_greeting(period: str) -> str:
    return random.choice(PERIOD_GREETINGS.get(period, PERIOD_GREETINGS["morning"]))


def weather_code_to_text(code: int) -> str:
    return WEATHER_CODE_TEXT.get(code, f"Código {code}")


def _window_label(minutes: int) -> str:
    """60/120/180/240 → 1h/2h/3h/4h; valores quebrados ficam em minutos."""
    return f"{minutes // 60}h" if minutes % 60 == 0 else f"{minutes} min"


def _temp_range(temp_min: float, temp_max: float, decimals: int = 1) -> str:
    """Faixa de temperatura; um único valor quando não há variação."""
    if temp_min == temp_max:
        return f"{temp_min:.{decimals}f}°C"
    return f"{temp_min:.{decimals}f}°C a {temp_max:.{decimals}f}°C"


def _uv_line(uv_index: float) -> str:
    if uv_index <= 0:
        return "🌙 *Índice UV (máx.):* 0.0 (_Sem sol agora_)"
    icon = "☀️" if uv_index < 6 else "🧴"
    note = "(_Muito Alto! Proteja-se do sol_)" if uv_index >= 8 else "(_Tranquilo_)"
    return f"{icon} *Índice UV (máx.):* {uv_index:.1f} {note}"


def _health_tip(uv_index: float, humidity: float, rain_prob: float | None) -> str:
    """Dica única, na ordem chuva → umidade → UV → clima agradável."""
    if rain_prob is not None and rain_prob >= 70:
        return "_Dica: Tempo fechado! Leve o guarda-chuva se for sair._ ☂️"
    if humidity <= 30:
        return "_Dica: Umidade de deserto! Beba água e evite o sol entre 10h e 16h._ 🚰"
    if uv_index >= 8:
        return "_Dica: Sol muito forte! Protetor solar e óculos não podem faltar._ 😎"
    return "_Dica: Clima agradável por aí! Aproveite._ 🍃"


def format_period_summary(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    city: str,
    period: str,
    temp_min: float,
    temp_max: float,
    humidity_avg: int,
    rain_prob_max: int | None,
    uv_max: float,
    weather_codes: list[int],
) -> str:
    """Mensagem de boletim por período (manhã/tarde/noite) para WhatsApp."""
    condition = weather_code_to_text(
        max(set(weather_codes), key=weather_codes.count) if weather_codes else 0
    )
    rain_text = (
        "—" if rain_prob_max is None else f"{rain_prob_max:.0f}%"
    )

    return (
        f"{get_period_greeting(period)}\n\n"
        f"📍 *Previsão {PERIOD_LABELS.get(period, period)} — {city}*\n"
        f"🕐 Janela: {PERIOD_WINDOWS.get(period, '')}\n"
        f"🌤️ *Condição:* {condition}\n\n"
        f"🌡️ *Temperatura:* {_temp_range(temp_min, temp_max, decimals=0)}\n"
        f"💧 *Umidade (média):* {humidity_avg}%\n"
        f"🌧️ *Chance de Chuva (pico):* {rain_text}\n"
        f"{_uv_line(uv_max)}\n\n"
        f"{_health_tip(uv_max, humidity_avg, rain_prob_max)}"
    )


def format_window_summary(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    city: str,
    temp_min: float,
    temp_max: float,
    humidity: int,
    uv_index: float,
    rain_prob: int | None,
    window_minutes: int = 60,
) -> str:
    """Resumo da previsão para a janela (em minutos) a partir de agora."""
    rain_text = "—" if rain_prob is None else f"{rain_prob}%"

    return (
        f"{time_greeting()}\n\n"
        f"📍 *Previsão para {city} — próximos {_window_label(window_minutes)}*\n\n"
        f"🌡️ *Temperatura:* {_temp_range(temp_min, temp_max)}\n"
        f"💧 *Umidade (média):* {humidity}%\n"
        f"🌧️ *Chance de Chuva (pico):* {rain_text}\n"
        f"{_uv_line(uv_index)}\n\n"
        f"{_health_tip(uv_index, humidity, rain_prob)}"
    )


def format_comparison(rows: list[dict], window_minutes: int) -> str:
    """Comparativo compacto: uma linha por cidade (temp/umidade/chuva/UV)."""
    numbers = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣")
    lines = []
    for index, row in enumerate(rows):
        icon = numbers[index] if index < len(numbers) else "▫️"
        rain = "—" if row["rain_prob"] is None else f"{row['rain_prob']}%"
        lines.append(
            f"{icon} *{row['city']}*: "
            f"{_temp_range(row['temp_min'], row['temp_max'])} · "
            f"💧 {row['humidity']}% · 🌧️ {rain} · UV {row['uv_index']:.1f}"
        )
    return (
        f"📊 *Comparativo — próximos {_window_label(window_minutes)}*\n\n"
        + "\n".join(lines)
    )
