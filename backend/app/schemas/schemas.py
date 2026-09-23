from pydantic import BaseModel
from typing import Optional

# Modelo para os dados atuais (temperatura, umidade, chuva, UV)
class CurrentWeather(BaseModel):
    temperature_2m: float
    relative_humidity_2m: float
    rain: float
    uv_index: float

# Min/max diários (daily do Open-Meteo)
class DailyWeather(BaseModel):
    temperature_2m_max: list[float] = []
    temperature_2m_min: list[float] = []

# Dados horários (hourly do Open-Meteo) — alinhados por índice de hora
class HourlyWeather(BaseModel):
    time: list[str] = []
    temperature_2m: list[float] = []
    precipitation_probability: list[float] = []
    relative_humidity_2m: list[float] = []
    uv_index: list[float] = []
    weather_code: list[int] = []

# Modelo principal que engloba a resposta da API do Open-Meteo
class WeatherData(BaseModel):
    latitude: float
    longitude: float
    current: CurrentWeather
    daily: Optional[DailyWeather] = None
    hourly: Optional[HourlyWeather] = None