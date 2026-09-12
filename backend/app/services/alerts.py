def generate_weather_alerts(uv_index: float, humidity: float, rain_prob: float) -> list[str]:
    """
    Gera mensagens de alerta com base nos limiares metereológicos preventivos.
    """
    alerts = []

    # Regra 1: Índice UV >= 8 (Fotoproteção e hidratação)
    if uv_index >= 8.0:
        alerts.append("⚠️ *Alerta UV Extremo:* Índice UV elevado (≥ 8). Recomenda-se uso de protetor solar e hidratação constante.")

    # Regra 2: Umidade <= 30% (Tempo seco)
    if humidity <= 30.0:
        alerts.append("⚠️ *Alerta de Umidade Baixa:* Umidade relativa do ar crítica (≤ 30%). Mantenha-se hidratado e evite exposição ao sol.")

    # Regra 3: Probabilidade de Chuva >= 70% (Atenção a alagamentos)
    if rain_prob >= 70.0:
        alerts.append("🌧️ *Alerta de Chuva Forte:* Probabilidade de chuva alta (≥ 70%). Atenção a pontos de alagamento nas vias.")

    return alerts