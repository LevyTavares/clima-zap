# pylint: disable=duplicate-code
import random

GREETINGS = [
    "E aí, como estamos hoje? ☀️",
    "Olá! Aqui está o panorama do tempo para você: 🌤️",
    "Pronto para o dia? Confira a previsão atualizada: ⚡",
    "Boas! Aqui estão as condições do clima agora: 🌡️",
]


def get_random_greeting() -> str:
    """Retorna uma saudação aleatória para variar as respostas."""
    return random.choice(GREETINGS)


def get_dynamic_tip(temp_max: float, uv_index: float, rain_chance: int) -> str:
    """Gera uma dica contextualizada de acordo com o clima."""
    tips = []

    if uv_index >= 8:
        tips.append("O sol está forte! Não esqueça o protetor solar e óculos escuros. 😎")
    elif uv_index >= 5:
        tips.append("Índice UV moderado a alto. Mantenha-se hidratado ao longo do dia! 💧")

    if rain_chance >= 60:
        tips.append("Alta probabilidade de chuva! Leve um guarda-chuva se for sair. ☔")
    elif rain_chance >= 30:
        tips.append("Possibilidade de chuva isolada. Vale a pena ficar atento ao céu! 🌧️")

    if temp_max >= 34.0:
        tips.append("Calor intenso previsto! Dê preferência a ambientes ventilados. 🪟")

    if not tips:
        tips.append("Dia com clima estável. Aproveite a jornada! 👍")

    return random.choice(tips)
