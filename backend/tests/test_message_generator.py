from app.services.message_generator import get_dynamic_tip, get_random_greeting


def test_get_random_greeting():
    greeting = get_random_greeting()
    assert isinstance(greeting, str)
    assert len(greeting) > 0


def test_get_dynamic_tip():
    tip_uv = get_dynamic_tip(temp_max=30.0, uv_index=9.0, rain_chance=10)
    assert "protetor solar" in tip_uv or "óculos" in tip_uv

    tip_rain = get_dynamic_tip(temp_max=28.0, uv_index=2.0, rain_chance=80)
    assert "guarda-chuva" in tip_rain
