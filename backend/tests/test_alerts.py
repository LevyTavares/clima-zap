from app.services.alerts import generate_weather_alerts

def test_uv_alert_trigger():
    alerts = generate_weather_alerts(uv_index=8.5, humidity=50, rain_prob=20)
    assert len(alerts) == 1
    assert "Alerta UV Extremo" in alerts[0]

def test_humidity_alert_trigger():
    alerts = generate_weather_alerts(uv_index=3.0, humidity=25, rain_prob=10)
    assert len(alerts) == 1
    assert "Alerta de Umidade Baixa" in alerts[0]

def test_rain_alert_trigger():
    alerts = generate_weather_alerts(uv_index=4.0, humidity=60, rain_prob=75)
    assert len(alerts) == 1
    assert "Alerta de Chuva Forte" in alerts[0]

def test_multiple_alerts_trigger():
    alerts = generate_weather_alerts(uv_index=9.0, humidity=20, rain_prob=80)
    assert len(alerts) == 3

def test_no_alerts_trigger():
    alerts = generate_weather_alerts(uv_index=5.0, humidity=55, rain_prob=30)
    assert len(alerts) == 0