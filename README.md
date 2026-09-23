# 🌤️ Clima-Zap — WhatsApp Weather Alert Bot

> **APIEXT III Project**
> Sistema de monitoramento e alertas climáticos em tempo real para a região do Cariri (CE), consumindo a [Open-Meteo API](https://open-meteo.com) e integrado ao WhatsApp via [Evolution API](https://doc.evolution-api.com) para disparos preventivos.

**Repositório:** [github.com/LevyTavares/clima-zap](https://github.com/LevyTavares/clima-zap)

---

## 📌 Sobre o Projeto

O **Clima-Zap** coleta dados meteorológicos precisos (temperatura, umidade, precipitação e índice UV) da região do Cariri (coordenadas `-7.31, -39.31` — Barbalha/Juazeiro do Norte), analisa regras de prevenção urbana em tempo real e dispara alertas via WhatsApp para manter os usuários informados e protegidos.

O sistema opera de forma **full-stack**: uma API REST FastAPI consome o Open-Meteo, um bot de WhatsApp recebe comandos por mensagem de texto e um frontend React (SPA) expõe a interface web. Toda a infraestrutura (banco, cache, WhatsApp, backend e frontend) sobe com **um único comando** via Docker Compose.

### 🚨 Regras de Alertas Preventivos

| Regra | Limiar | Recomendação |
|-------|--------|--------------|
| ☀️ **Índice UV Extremo** | UV ≥ 8.0 | Fotoproteção e hidratação constante |
| 🌵 **Umidade Crítica** | Umidade ≤ 30% | Hidratação, evitar exposição solar |
| 🌧️ **Chuva Forte** | Precipitação ≥ 70% | Atenção a pontos de alagamento |

As regras são aplicadas em três pontos: endpoint `/api/v1/clima/cariri`, scheduler agendado (6×/dia) e comando `forecast` no WhatsApp.

---

## ✅ Funcionalidades

- **API REST** com health checks (`/`, `/health`, `/api/v1/clima/ping`)
- **Previsão em tempo real** da região do Cariri com geração de alertas (`/api/v1/clima/cariri`)
- **Motor de regras** de alerta preventivo (UV, umidade, chuva) com mensagens formatadas em Markdown de WhatsApp
- **Alertas agendados** via APScheduler — 6 verificações diárias (06h, 08h, 12h, 14h, 16h, 18h — fuso `America/Fortaleza`)
- **Boletim periódico no grupo WhatsApp** — 3×/dia (manhã 06h, tarde 14h, noite 20h) com jitter 0–15min, alvo via `FORECAST_GROUP_JID`
- **Webhook do WhatsApp** (`POST /api/v1/webhook`) com processamento assíncrono (`BackgroundTasks`), normalização de eventos e deduplicação de mensagens (TTL 5 min)
- **Bot de WhatsApp** com comandos: `help`, `status`, `forecast` (DM e grupo)
- **Envio de mensagens** pelo WhatsApp via Evolution API (SDK `evolution-whatsapp`)
- **Verificação de sessão** do WhatsApp (`/instance/connectionState`)
- **Formatadores de mensagem** (resumo diário, alerta urgente, saudações aleatórias)
- **Documentação servida pela API** (`/docs/whatsapp`, `/docs/docker`) além do Swagger automático
- **Stack Docker Compose completa** — PostgreSQL + Redis + Evolution API + Backend + Frontend
- **CI com GitHub Actions** executando a suíte de testes (26 testes)

---

## 🛠️ Tecnologias Utilizadas

### Backend

| Camada | Tecnologia |
|--------|-----------|
| Linguagem | Python 3.11 (Docker/CI) |
| Framework Web | FastAPI 0.141.1 |
| Validação de Dados | Pydantic v2 2.13.4 + pydantic-settings 2.10.1 |
| Cliente HTTP Assíncrono | httpx 0.28.1 |
| Scheduler | APScheduler 3.11.0 |
| Integração WhatsApp | evolution-whatsapp 0.1.1 |
| Servidor ASGI | Uvicorn 0.52.4 |
| Testes | Pytest 8.4.2 |
| Variáveis de Ambiente | python-dotenv 1.2.3 |

### Frontend

| Camada | Tecnologia |
|--------|-----------|
| Biblioteca | React 18.3 |
| Bundler | Vite 6 |
| Estilização | Sass (SCSS modular) |
| Hospedagem planejada | Vercel |

### Infraestrutura

| Camada | Tecnologia |
|--------|-----------|
| Orquestração | Docker Compose |
| Banco de Dados (Evolution) | PostgreSQL 15 (Alpine) |
| Cache (Evolution) | Redis 7 (Alpine) |
| Provedor WhatsApp | Evolution API v2.3.7 (`evoapicloud/evolution-api`) |
| Reverse Proxy (frontend) | nginx 1.27 |
| CI/CD | GitHub Actions |
| Banco de Dados (planejado) | Neon / Supabase |
| Hospedagem backend (planejada) | Render |
| Provedor Metereológico | Open-Meteo API (sem API key) |

---

## 📂 Estrutura do Repositório

```text
clima-zap/
├── .env                          # Segredos do Docker Compose (gitignored)
├── .env.example                  # Template de segredos do Compose
├── .github/
│   └── workflows/
│       └── ci.yml                # Pipeline CI (Pytest, Python 3.11)
├── .dockerignore
├── .gitignore
├── AGENTS.md                     # Contexto do projeto para agentes de IA
├── README.md
├── docker-compose.yml            # Stack de 5 serviços
├── requirements.txt              # Dependências Python (raiz)
├── docs/
│   ├── docker-setup.md           # Guia do Docker Compose
│   └── whatsapp-integration.md   # Guia da integração WhatsApp
├── backend/
│   ├── .dockerignore
│   ├── .env.example              # Template de env do backend
│   ├── Dockerfile                # python:3.11-slim
│   ├── app/
│   │   ├── main.py               # App FastAPI, CORS, APScheduler, rotas
│   │   ├── formatter.py          # Formatares de mensagem WhatsApp
│   │   ├── api/
│   │   │   ├── api.py            # Cliente Open-Meteo (fetch_cariri_weather)
│   │   │   └── webhook.py        # Webhook WhatsApp + roteador de comandos
│   │   ├── core/
│   │   │   └── config.py         # Settings (pydantic-settings)
│   │   ├── schemas/
│   │   │   ├── schemas.py        # WeatherData / CurrentWeather / DailyWeather / HourlyWeather
│   │   │   └── webhook.py        # WebhookPayload
│   │   └── services/
│   │       ├── alerts.py         # generate_weather_alerts (3 regras)
│   │       ├── evolution_client.py    # Envio via Evolution API (EvoClient)
│   │       ├── forecast.py            # Builders on-demand e por período (manhã/tarde/noite)
│   │       └── whatsapp_session.py    # Verificação de connectionState
│   ├── test/                     # Testes legados (health)
│   └── tests/                    # Suíte principal (26 testes)
│       ├── conftest.py
│       ├── test_alerts.py
│       ├── test_forecast.py
│       ├── test_main.py
│       └── test_whatsapp_session.py
└── frontend/
    ├── .dockerignore
    ├── Dockerfile                # node:20-alpine build → nginx:1.27-alpine
    ├── index.html                # lang="pt-BR"
    ├── nginx.conf                # SPA fallback + proxy /api → backend:8000
    ├── package.json              # clima-zap-frontend
    ├── vite.config.js            # Dev proxy /api → localhost:8000
    └── src/
        ├── App.jsx               # Componente raiz
        └── main.jsx              # Entry point React 18
```

---

## 🚀 Início Rápido

### Pré-requisitos

- Docker Engine + Docker Compose v2
- (opcional, modo híbrido) Python 3.11+ e Node.js 20+

### Subindo a stack completa

```bash
# 1. Copiar templates de env
cp .env.example .env
cp backend/.env.example backend/.env

# 2. Editar segredos (.env) — trocar EVOLUTION_API_KEY e senhas
#    Opcional: FORECAST_GROUP_JID=120363...@g.us ativa boletim 3×/dia no grupo
vim .env

# 3. Build e start
docker compose up --build -d

# 4. Verificar status
docker compose ps

# Logs do backend
docker compose logs -f backend
```

### URLs locais

| Serviço | URL |
|---------|-----|
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Docs WhatsApp | http://localhost:8000/docs/whatsapp |
| Docs Docker | http://localhost:8000/docs/docker |
| Frontend | http://localhost:5173 |
| Evolution Manager | http://localhost:8080/manager |

### Parear número do WhatsApp (QR Code)

1. Abra http://localhost:8080/manager
2. Autentique com `EVOLUTION_API_KEY`
3. Crie a instância: nome `clima-zap`, integração `WHATSAPP-BAILEYS`
4. Escaneie o QR Code com o WhatsApp
5. Estado da conexão deve ficar `open`

### Associar o webhook à instância

```bash
curl -X POST "http://localhost:8080/webhook/set/clima-zap" \
  -H "apikey: $EVOLUTION_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "enabled": true,
      "url": "http://localhost:8000/api/v1/webhook",
      "events": ["MESSAGES_UPSERT"],
      "byEvents": false,
      "base64": false
    }
  }'
```

> Detalhes completos: [`docs/whatsapp-integration.md`](docs/whatsapp-integration.md) e [`docs/docker-setup.md`](docs/docker-setup.md).

---

## 🧑‍💻 Desenvolvimento Local (modo híbrido)

Rodar backend/frontend nativamente, mantendo infraestrutura no Docker:

```bash
# Apenas infraestrutura
docker compose up -d postgres redis evolution-api

# Backend local
pip install -r requirements.txt
cd backend
PYTHONPATH=. python -m uvicorn app.main:app --reload

# Frontend local (outra terminal)
cd frontend
npm install
npm run dev
```

> Fora do Docker, ajuste `EVOLUTION_API_URL=http://localhost:8080` no `backend/.env`.

### Scripts do Frontend

```bash
npm run dev       # Vite dev server (porta 5173)
npm run build     # Build de produção
npm run preview   # Preview do build
```

---

## 📡 Endpoints da API

| Método | Rota | Tag | Descrição |
|--------|------|-----|-----------|
| GET | `/` | Health Check | Status raiz da API |
| GET | `/health` | Health Check | Health check detalhado |
| GET | `/api/v1/clima/ping` | Health Check | Ping do módulo de clima |
| GET | `/api/v1/clima/cariri` | Dados Climáticos | Previsão atual + alertas gerados |
| GET | `/docs/whatsapp` | Documentação | Markdown da integração WhatsApp |
| GET | `/docs/docker` | Documentação | Markdown do setup Docker |
| POST | `/api/v1/webhook` | Webhook do WhatsApp | Recebe eventos da Evolution API |
| GET | `/docs` | — | Swagger UI (automático) |
| GET | `/redoc` | — | ReDoc (automático) |
| GET | `/openapi.json` | — | OpenAPI JSON (automático) |

### Exemplo de resposta — `/api/v1/clima/cariri`

```json
{
  "weather": {
    "latitude": -7.31,
    "longitude": -39.31,
    "current": {
      "temperature_2m": 31.4,
      "relative_humidity_2m": 45.0,
      "rain": 0.0,
      "uv_index": 9.1
    },
    "daily": {
      "temperature_2m_max": [34.0],
      "temperature_2m_min": [23.0]
    }
  },
  "alerts": [
    "⚠️ *Alerta UV Extremo:* Índice UV elevado (≥ 8). Recomenda-se uso de protetor solar e hidratação constante."
  ]
}
```

### Integração Open-Meteo

- **Endpoint:** `GET https://api.open-meteo.com/v1/forecast` (sem API key)
- **Parâmetros:** `latitude=-7.31`, `longitude=-39.31`, `current=temperature_2m,relative_humidity_2m,rain,uv_index`, `daily=temperature_2m_max,temperature_2m_min`, `hourly=temperature_2m,precipitation_probability,relative_humidity_2m,uv_index,weather_code`, `forecast_days=2`, `timezone=America/Fortaleza`
- **Cliente:** `httpx.AsyncClient` com timeout de 10s, resposta validada pelo modelo Pydantic `WeatherData`

### Fluxo do Scheduler

- `AsyncIOScheduler` com fuso `America/Fortaleza`
- Job `scheduled_weather_alerts` via cron: horas `6, 8, 12, 14, 16, 18` (minuto 0) — busca clima, gera alertas, **apenas loga** (`logger.warning`)
- Jobs `forecast_morning` / `forecast_afternoon` / `forecast_night`: horas `6, 14, 20`, `jitter=900` (0–15min) — montam boletim por período e **enviam** para `FORECAST_GROUP_JID` (só registram se o JID estiver setado)

---

## 💬 Integração WhatsApp

**Arquitetura:**

```
WhatsApp User → Evolution API → Webhook → Clima-Zap → Evolution API → WhatsApp User
```

### Comandos suportados

| Comando | Resposta |
|---------|----------|
| `help`, `?`, `comandos`, `ajuda` | Texto de ajuda com a lista de comandos |
| `status`, `status?` | Status da API + estado da instância WhatsApp |
| `forecast`, `previsao`, `previsão`, `clima` | Resumo diário do clima + alertas ativos |
| Outro | Mensagem de comando não reconhecido |

### Payload de exemplo (webhook)

```json
{
  "event": "MESSAGES_UPSERT",
  "instance": "clima-zap",
  "data": {
    "key": {
      "remoteJid": "558899887766@s.whatsapp.net",
      "fromMe": false,
      "id": "3EB0XXXXX"
    },
    "message": {
      "conversation": "help"
    }
  },
  "sender": "558899887766@s.whatsapp.net"
}
```

### Teste local do webhook

```bash
curl -X POST "http://localhost:8000/api/v1/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "MESSAGES_UPSERT",
    "instance": "clima-zap",
    "data": {
      "key": {
        "remoteJid": "558899887766@s.whatsapp.net",
        "fromMe": false,
        "id": "3EB0XXXXX"
      },
      "message": { "conversation": "help" }
    },
    "sender": "558899887766@s.whatsapp.net"
  }'
```

> Guia completo: [`docs/whatsapp-integration.md`](docs/whatsapp-integration.md)

---

## ⚙️ Variáveis de Ambiente

### Raiz (`.env` — Docker Compose)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `EVOLUTION_API_KEY` | `changeme` | Chave de autenticação da Evolution API |
| `EVOLUTION_INSTANCE_NAME` | `clima-zap` | Nome da instância WhatsApp |
| `FORECAST_GROUP_JID` | *(vazio)* | Grupo alvo do boletim 3×/dia (`120363...@g.us`). Passado ao container via `docker-compose.yml` |
| `POSTGRES_DATABASE` | `evolution` | Banco do PostgreSQL (Evolution) |
| `POSTGRES_USERNAME` | `evolution` | Usuário do PostgreSQL |
| `POSTGRES_PASSWORD` | `evolution_pass` | Senha do PostgreSQL |

### Backend (`backend/.env`)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `PORT` | `8000` | Porta da API |
| `ENVIRONMENT` | `development` | Ambiente de execução |
| `DEFAULT_CITY` | `Juazeiro do Norte` | Cidade padrão |
| `DEFAULT_LATITUDE` | `-7.2128` | Latitude padrão |
| `DEFAULT_LONGITUDE` | `-39.3151` | Longitude padrão |
| `OPEN_METEO_URL` | `https://api.open-meteo.com/v1/forecast` | URL do Open-Meteo |
| `EVOLUTION_API_URL` | `http://evolution-api:8080` (Docker) / `http://localhost:8080` (local) | URL da Evolution API |
| `EVOLUTION_API_KEY` | `changeme` | Chave da Evolution API |
| `EVOLUTION_INSTANCE_NAME` | `clima-zap` | Nome da instância |
| `TARGET_PHONE_NUMBER` | *(vazio)* | Número alvo (broadcast — não utilizado ainda) |
| `FORECAST_GROUP_JID` | *(vazio)* | JID do grupo WhatsApp (`...@g.us`) que recebe o boletim 3×/dia. Vazio = jobs de forecast periódico desativados |
| `DOCS_DIR` | `../docs` (dev) / `/docs` (Docker) | Diretório da documentação markdown |
| `PYTHONPATH` | `.` | Necessário para rodar pytest de `backend/` |

### Frontend

| Variável | Default | Descrição |
|----------|---------|-----------|
| `VITE_API_PROXY` | `http://localhost:8000` | Alvo do proxy `/api` no Vite dev server |

---

## 🗄️ Banco de Dados

- O backend **não possui banco próprio** — é stateless (apenas deduplicação de mensagens em memória).
- **PostgreSQL 15** e **Redis 7** existem exclusivamente como infraestrutura para a **Evolution API**:
  - Evolution persiste instâncias e mensagens no PostgreSQL
  - Evolution usa Redis (`redis://redis:6379/6`, prefixo `clima-zap`) como cache
- Volumes Docker: `postgres_data`, `redis_data`, `evolution_instances`
- Plano futuro: PostgreSQL gerenciado (Neon/Supabase) para dados da aplicação.

---

## 🐳 Serviços Docker Compose

| Serviço | Imagem | Porta | Propósito |
|---------|--------|-------|-----------|
| postgres | `postgres:15-alpine` | interna | Banco da Evolution API |
| redis | `redis:7-alpine` | interna | Cache da Evolution API |
| evolution-api | `evoapicloud/evolution-api:v2.3.7` | `8080:8080` | Provedor WhatsApp |
| backend | build `backend/Dockerfile` (python:3.11-slim) | `8000:8000` | API Clima-Zap |
| frontend | build `./frontend` (node:20 → nginx:1.27) | `5173:80` | SPA web |

- Rede: `clima-zap-net` (bridge)
- Backend monta `./docs:/docs:ro` (somente leitura)

### Comandos úteis

```bash
docker compose up -d              # iniciar
docker compose down               # parar (mantém volumes)
docker compose down -v            # parar + apagar volumes (perda de dados!)
docker compose logs -f backend    # logs do backend
docker compose build backend      # rebuild após mudança de código
docker compose restart evolution-api
```

---

## 🧪 Testes

```bash
cd backend
PYTHONPATH=. python -m pytest
```

**26 testes**, todos passando:

| Arquivo | Testes | Cobre |
|---------|--------|-------|
| `tests/test_main.py` | 10 | Endpoints, scheduler de alertas, registro/skip dos 3 jobs de forecast (jitter 900s), envio do boletim, endpoint `/api/v1/clima/cariri` |
| `tests/test_forecast.py` | 10 | Agregação por período (manhã/tarde/noite), formatação, builders on-demand e periódico |
| `tests/test_alerts.py` | 5 | Regras de UV, umidade, chuva, múltiplas e nenhuma |
| `tests/test_whatsapp_session.py` | 2 | `connectionState` (sucesso e erro de conexão) |
| `test/test_health.py` | 2 | `/` online e `/health` healthy (legado) |

Stack: `pytest` + `fastapi.testclient` + `unittest.mock` / `monkeypatch`.

---

## 🔄 CI/CD — GitHub Actions

Pipeline **Clima-Zap CI Pipeline** (`.github/workflows/ci.yml`):

- **Gatilhos:** push (todas as branches) e PR para `main`
- **Runner:** `ubuntu-latest`, Python **3.11**
- **Passos:**
  1. Checkout do código
  2. Setup Python 3.11
  3. `pip install -r requirements.txt`
  4. `cd backend && PYTHONPATH=. python -m pytest`

---

## 📖 Documentação Adicional

| Documento | Conteúdo | Endpoint |
|-----------|----------|----------|
| [`docs/whatsapp-integration.md`](docs/whatsapp-integration.md) | Setup Evolution API, webhook, comandos, segurança, troubleshooting | `GET /docs/whatsapp` |
| [`docs/docker-setup.md`](docs/docker-setup.md) | Serviços, quick start, QR pairing, comandos Compose | `GET /docs/docker` |
| [`AGENTS.md`](AGENTS.md) | Contexto do projeto e padrões de código para agentes de IA | — |

---

## 🗺️ Roadmap / Não implementado

- [x] Boletim periódico 3×/dia no grupo (`FORECAST_GROUP_JID` — manhã 06h, tarde 14h, noite 20h, jitter 0–15min)
- [ ] Envio real de alertas agendados ao WhatsApp (job de alertas ainda apenas loga)
- [ ] Verificação de assinatura do webhook (`X-Hub-Signature`) em produção
- [ ] UI do frontend com dados climáticos em tempo real (componente hoje é placeholder)
- [ ] Estilos SCSS modulares (`*.module.scss` + `_variables.scss`)
- [ ] Router no frontend (react-router)
- [ ] Banco de dados próprio da aplicação (Neon/Supabase)
- [ ] Configs de deploy: `vercel.json` (frontend) e `render.yaml` (backend)
- [ ] Broadcast via `TARGET_PHONE_NUMBER`
- [ ] Lint/format (ruff, ESLint, Prettier)
- [ ] LICENSE

---

## 🔐 Segurança

- Alterar `EVOLUTION_API_KEY` e `POSTGRES_PASSWORD` antes de produção
- Em produção: usar HTTPS no webhook e implementar verificação de assinatura
- Nunca commitar arquivos `.env`
- CORS está com `allow_origins=["*"]` — restringir em produção
- Volumes persistem dados: sobrevivem a `docker compose down`, **não** a `down -v`

---

## 📚 Referências

- [Open-Meteo API](https://open-meteo.com)
- [Evolution API Docs](https://doc.evolution-api.com)
- [evolution-whatsapp (PyPI)](https://pypi.org/project/evolution-whatsapp/)
- [FastAPI](https://fastapi.tiangolo.com)
- [Docker Compose](https://docs.docker.com/compose)
