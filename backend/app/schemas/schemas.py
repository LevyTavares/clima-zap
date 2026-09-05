from pydantic import BaseModel

# Modelo para os dados atuais (temperatura, umidade, chuva, UV)
class CurrentWeather(BaseModel):
    temperature_2m: float
    relative_humidity_2m: float
    rain: float
    uv_index: float

# Modelo principal que engloba a resposta da API do Open-Meteo
class WeatherData(BaseModel):
    latitude: float
    longitude: float
    current: CurrentWeather
# HELLO