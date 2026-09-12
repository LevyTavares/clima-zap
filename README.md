# 🌤️ ClimaZap — WhatsApp Weather Forecast Bot

> **APIEXT III Project**  
> Automação em Python desenvolvida para monitoramento climático em tempo real da região do Cariri, integrada ao Open-Meteo e projetada para disparos preventivos de alertas via WhatsApp.

---

## 📌 Sobre o Projeto

O **ClimaZap** coleta dados meteorológicos precisos (temperatura, umidade, probabilidade de chuva e índice UV) para prever e alertar sobre condições extremas na região do Cariri. O sistema analisa os parâmetros em tempo real e dispara regras de prevenção urbana para manter os usuários informados e protegidos.

### 🚨 Regras de Alertas Preventivos
- ☀️ **Índice UV Extremo ($\ge 8.0$):** Alerta de alta radiação com recomendação de fotoproteção e hidratação.
- 🌵 **Umidade Crítica ($\le 30\%$):** Alerta de tempo seco extremo e riscos à saúde.
- 🌧️ **Chuva Forte ($\ge 70\%$):** Alerta de alta probabilidade de precipitação e atenção a alagamentos em vias urbanas.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3.14+
- **Framework Web:** FastAPI
- **Validação de Dados:** Pydantic
- **Testes Automatizados:** Pytest (8 testes unitários)
- **CI/CD:** GitHub Actions
- **Provedor Metereológico:** Open-Meteo API

---

## 📂 Estrutura do Repositório

```text
clima-zap/
├── .github/
│   └── workflows/          # Workflows de CI/CD (GitHub Actions)
├── backend/
│   ├── app/
│   │   ├── api/            # Integrações com APIs externas
│   │   ├── schemas/        # Modelos de dados Pydantic
│   │   ├── services/       # Regras de negócio e alertas
│   │   └── main.py         # Pontos de entrada da API FastAPI
│   ├── tests/              # Suite de testes unitários do Pytest
│   └── requirements.txt    # Dependências do projeto
├── AGENTS.md
└── README.md
