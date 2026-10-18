# 🌤️ Clima-Zap — WhatsApp Weather Alert Bot

> **APIEXT III Project**
> Sistema de monitoramento e alertas climáticos em tempo real para a região do Cariri (CE - alterável), consumindo a [Open-Meteo API](https://open-meteo.com) e integrado ao WhatsApp via [Evolution API](https://doc.evolution-api.com) para disparos preventivos.

**Repositório:** [github.com/LevyTavares/clima-zap](https://github.com/LevyTavares/clima-zap)

---

## 📌 Sobre o Projeto

O **Clima-Zap** coleta dados meteorológicos precisos (temperatura, umidade, precipitação e índice UV) do bairro Triângulo, em Juazeiro do Norte (coordenadas padrão `-7.229711, -39.3300014`), analisa regras de prevenção urbana em tempo real e dispara alertas via WhatsApp para manter os usuários informados e protegidos.

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
- **Bot de WhatsApp** com gramática estrita — comandos só valem como `/comando` ou `@clima-zap comando`: `ajuda`, `status`, `clima`, `configuracao`, `cidade`, `inscrever`, `sair` (em grupo só responde a comandos; no privado, dica única)
- **Envio de mensagens** pelo WhatsApp via Evolution API (SDK `evolution-whatsapp`)
- **Verificação de sessão** do WhatsApp (`/instance/connectionState`)
- **Formatadores de mensagem** (resumo diário, alerta urgente, saudações aleatórias)
- **Documentação servida pela API** (`/docs/whatsapp`, `/docs/docker`) além do Swagger automático
- **Stack Docker Compose completa** — PostgreSQL + Redis + Evolution API + Backend + Frontend
- **CI com GitHub Actions** executando a suíte de testes
- **Persistência de assinantes e alertas** com SQLAlchemy assíncrono, SQLite/PostgreSQL e migrations Alembic

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
| ORM / Migrações | SQLAlchemy 2 + Alembic |
| Driver de banco | aiosqlite / asyncpg |
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
| Banco de Dados (aplicação) | SQLite local / PostgreSQL via SQLAlchemy (Docker) · Cloudflare D1 (Workers) |
| Hospedagem backend | Cloudflare Workers (Python Workers + D1 + Cron Triggers) — Docker como alternativa |
| Provedor Metereológico | Open-Meteo API (sem API key) |

---

## 📂 Estrutura do Repositório

```text
clima-zap/
├── .env                          # Segredos Compose + backend (gitignored)
├── .env.example                  # Template único de env (Compose + backend)
├── .github/
│   └── workflows/
│       ├── ci.yml                # Pipeline CI (testes, lint, migrations, Docker, bundle Workers)
│       └── cd.yml                # Pipeline CD (deploy no Cloudflare Workers)
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
│   ├── Dockerfile                # python:3.11-slim
│   ├── app/
│   │   ├── main.py               # App FastAPI, CORS, APScheduler, rotas
│   │   ├── db/                   # Engine e sessões assíncronas
│   │   ├── models.py             # Subscribers e AlertLogs
│   │   ├── formatter.py          # Formatares de mensagem WhatsApp
│   │   ├── api/
│   │   │   ├── api.py            # Cliente Open-Meteo (fetch_cariri_weather)
│   │   │   └── webhook.py        # Webhook WhatsApp + roteador de comandos
│   │   ├── core/
│   │   │   ├── config.py         # Settings (pydantic-settings)
│   │   │   ├── schedule.py       # Horas, jitter e crons (Docker + Workers)
│   │   │   └── worker_runtime.py # Bridge do runtime Workers (D1, brt_hour)
│   │   ├── schemas/
│   │   │   ├── schemas.py        # WeatherData / CurrentWeather / DailyWeather / HourlyWeather
│   │   │   └── webhook.py        # WebhookPayload
│   │   └── services/
│   │       ├── alerts.py         # generate_weather_alerts (3 regras)
│   │       ├── alert_history.py  # Persistência do resultado de envios
│   │       ├── evolution_client.py    # Envio via Evolution API (EvoClient)
│   │       ├── forecast.py            # Builders on-demand e por período (manhã/tarde/noite)
│   │       └── whatsapp_session.py    # Verificação de connectionState
│   ├── test/                     # Testes legados (health)
│   ├── alembic/                  # Histórico versionado de schema
│   ├── worker.py                 # Entrypoint Workers (ASGI + Cron Triggers)
│   ├── wrangler.jsonc            # Config do Worker (crons, D1, assets)
│   ├── pyproject.toml            # Deps do bundle Workers (Pyodide)
│   ├── migrations/               # Migrations D1 (SQL)
│   └── tests/                    # Suíte principal
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
# 1. Copiar template de env (único, na raiz)
cp .env.example .env

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

> Fora do Docker, `EVOLUTION_API_URL` já aponta para `http://localhost:8080` no `.env` da raiz (o backend local carrega esse arquivo automaticamente).

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
| GET | `/api/v1/clima/cariri` | Dados Climáticos | Previsão atual + alertas gerados (`?cidade=Barbalha\|Juazeiro do Norte\|Crato`) |
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
    "latitude": -7.229711,
    "longitude": -39.3300014,
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
- **Parâmetros padrão:** `latitude=-7.229711`, `longitude=-39.3300014`, `current=temperature_2m,relative_humidity_2m,rain,uv_index`, `daily=temperature_2m_max,temperature_2m_min`, `hourly=temperature_2m,precipitation_probability,relative_humidity_2m,uv_index,weather_code`, `forecast_days=2`, `timezone=America/Fortaleza`
- **Cliente:** `httpx.AsyncClient` com timeout de 10s, resposta validada pelo modelo Pydantic `WeatherData`

### Fluxo do Scheduler

- `AsyncIOScheduler` com fuso `America/Fortaleza` (caminho Docker)
- Job `scheduled_weather_alerts` via cron: horas `6, 8, 12, 14, 16, 18` (minuto 0) — busca clima, gera alertas, envia aos assinantes ativos e registra o resultado em `alert_logs`
- Jobs `forecast_morning` / `forecast_afternoon` / `forecast_night`: horas `6, 14, 20`, `jitter=900` (0–15min) — montam boletim por período e **enviam** para `FORECAST_GROUP_JID` (só registram se o JID estiver setado)
- No Cloudflare Workers o mesmo fluxo roda via **Cron Triggers** (ver seção seguinte), com o mesmo jitter 0–15min: cada expressão dispara só o job dela e o boletim dorme o sorteio dentro do handler `scheduled()`

---

## ☁️ Backend no Cloudflare Workers

O backend roda como **Python Worker** (FastAPI nativo via ASGI, GA desde set/2026):

| Docker | Cloudflare Workers |
|---------------|--------------------|
| FastAPI + Uvicorn | FastAPI via ASGI server do Workers (`workers.asgi.entrypoint`) |
| APScheduler (cron local) | Cron Triggers (UTC) + handler `scheduled()` em `backend/worker.py` |
| SQLite / PostgreSQL (SQLAlchemy) | Cloudflare D1 (`app/db/d1.py`, schema em `backend/migrations/`) |
| `.env` / ambiente | `vars` + `wrangler secret put` (sincronizados em `settings` pelo middleware) |
| Jitter anti-spam 0–15min | Mesmo jitter, sorteado no handler `scheduled()` (`app/core/schedule.py`) dentro do limite de 15min de wall time do Cron Trigger |

A aplicação é **dual-mode**: no caminho Docker nada muda ( SQLAlchemy + APScheduler
continuam no ar); no Workers, `app/core/worker_runtime.py` detecta o isolate e
troca persistência para D1 e agendamento para Cron Triggers.

### Deploy

Pré-requisitos: conta Cloudflare, [Node.js](https://nodejs.org) e [`uv`](https://docs.astral.sh/uv/).

```bash
cd backend

# 1. Sincroniza dependências para Pyodide (gera python_modules/ e pylock.toml)
uvx --from workers-py pywrangler sync

# 2. Cria o banco D1 e cola o id retornado em database_id (wrangler.jsonc)
npx wrangler d1 create clima-zap

# 3. Aplica o schema no D1
npx wrangler d1 migrations apply clima-zap --remote

# 4. Segredos (nomes em CAIXA ALTA; o código aceita também os nomes do .env)
npx wrangler secret put EVOLUTION_API_URL
npx wrangler secret put EVOLUTION_API_KEY
npx wrangler secret put EVOLUTION_INSTANCE_NAME
npx wrangler secret put FORECAST_GROUP_JID   # opcional: boletins 06/14/20h
npx wrangler secret put WEBHOOK_AUTH_TOKEN   # opcional: bearer no webhook
npx wrangler secret put TARGET_PHONE_NUMBER  # opcional: menção nativa @número

# 5. Deploy
uvx --from workers-py pywrangler deploy
```

- **Webhook da Evolution:** `https://clima-zap-api.<subdominio>.workers.dev/api/v1/webhook`
- **Cron Triggers:** alertas `0 9,11,15,17,19,21 * * *` (06/08/12/14/16/18h BRT) e
  boletins `0 9,17,23 * * *` (06/14/20h BRT) — America/Fortaleza = UTC-3 fixo.
  Cada expressão dispara só o job dela (as duas coincidem em 06h/14h BRT, sem
  isso os envios duplicariam) e o boletim aguarda o jitter anti-spam 0–15min
  antes do envio — expressões e jitter em `app/core/schedule.py`
- **Docs markdown** (`/docs/whatsapp`, `/docs/docker`) são servidos dos Assets
  do Worker (diretório `docs/` no `wrangler.jsonc`)
- **Dev local:** `uvx --from workers-py pywrangler dev` (workerd + D1 local;
  aplique antes `npx wrangler d1 migrations apply clima-zap --local`)

---

## 💬 Integração WhatsApp

**Arquitetura:**

```
WhatsApp User → Evolution API → Webhook → Clima-Zap → Evolution API → WhatsApp User
```

### Comandos suportados

Os comandos valem em **duas formas de invocação**:

1. `/comando [argumentos]` — ex: `/clima`, `/cidade Crato`;
2. `@clima-zap comando [argumentos]` — ex: `@clima-zap previsao` (o nome vem de `BOT_NAME`; a menção nativa do WhatsApp `@número` também vale, requerendo `TARGET_PHONE_NUMBER`).

| Comando | Resposta |
|---------|----------|
| `/help`, `/?`, `/comandos`, `/ajuda` | Menu de ajuda com a lista de comandos |
| `/status`, `/status?` | Status da API + estado da instância WhatsApp |
| `/forecast`, `/previsao`, `/previsão`, `/previzao`, `/previzão`, `/clima` | Resumo do clima + alertas ativos (usa o local do `/configuracao`) |
| `/configuracao` | Mostra o local atual (ou a região padrão) |
| `/configuracao <cidade>` | Define o local — presets do Crajubar ou qualquer cidade (geocoder Open-Meteo) |
| `/configuracao <lat,lon>` | Define por coordenadas (ex: `/configuracao -7.23, -39.31`) |
| `/configuracao padrao` | Remove o local e volta à região padrão |
| `/cidade <nome>` | Atalho de `/configuracao` para cidades |
| `/inscrever` | Ativa o envio de alertas climáticos para o contato |
| `/sair` | Cancela a inscrição dos alertas climáticos |
| Comando desconhecido (`/foo`) | Mensagem de comando não reconhecido + `/ajuda` |
| Texto sem invocação | Grupo: silêncio · Privado: dica única de `/ajuda` |

> Texto sem `/` e sem menção **não** é comando: `ajuda` puro é ignorado.

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
      "conversation": "/help"
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
      "message": { "conversation": "/help" }
    },
    "sender": "558899887766@s.whatsapp.net"
  }'
```

> Guia completo: [`docs/whatsapp-integration.md`](docs/whatsapp-integration.md)

---

## ⚙️ Variáveis de Ambiente

### Raiz (`.env` — Docker Compose + backend)

Único template: `.env.example` → `.env`. Docker Compose e o backend (pydantic-settings) leem o mesmo arquivo.

| Variável | Default | Descrição |
|----------|---------|-----------|
| `PORT` | `8000` | Porta da API (host e container) |
| `ENVIRONMENT` | `development` | Ambiente de execução |
| `DEFAULT_CITY` | `Triângulo, Juazeiro do Norte` | Região padrão dos alertas |
| `DEFAULT_LATITUDE` | `-7.229711` | Latitude do bairro Triângulo |
| `DEFAULT_LONGITUDE` | `-39.3300014` | Longitude do bairro Triângulo |
| `OPEN_METEO_URL` | `https://api.open-meteo.com/v1/forecast` | URL do Open-Meteo |
| `EVOLUTION_API_URL` | `http://localhost:8080` (local) / `http://evolution-api:8080` (Docker, override no compose) | URL da Evolution API |
| `EVOLUTION_API_KEY` | `changeme` | Chave de autenticação da Evolution API |
| `EVOLUTION_INSTANCE_NAME` | `clima-zap` | Nome da instância WhatsApp |
| `TARGET_PHONE_NUMBER` | *(vazio)* | Número do próprio bot (só dígitos) — ativa a menção nativa `@número` como invocação de comando |
| `BOT_NAME` | `clima-zap` | Nome do bot na invocação textual: `@clima-zap previsao` |
| `FORECAST_GROUP_JID` | *(vazio)* | Grupo alvo do boletim 3×/dia (`120363...@g.us`). Vazio = jobs desativados |
| `WEBHOOK_AUTH_TOKEN` | *(vazio)* | Se definido, o webhook exige `Authorization: Bearer <token>` (configure como header custom no webhook da Evolution). Vazio = sem verificação |
| `DOCS_DIR` | *(vazio → `docs/` da raiz)* / `/docs` (Docker) | Diretório da documentação markdown |
| `POSTGRES_DATABASE` | `evolution` | Banco do PostgreSQL (Evolution) |
| `POSTGRES_USERNAME` | `evolution` | Usuário do PostgreSQL |
| `POSTGRES_PASSWORD` | `evolution_pass` | Senha do PostgreSQL |
| `PYTHONPATH` | `.` | Necessário para rodar pytest de `backend/` (não vai no `.env`) |

### Frontend

| Variável | Default | Descrição |
|----------|---------|-----------|
| `VITE_API_PROXY` | `http://localhost:8000` | Alvo do proxy `/api` no Vite dev server |

---

## 🗄️ Banco de Dados

- O backend usa SQLAlchemy assíncrono e migrations Alembic. `DATABASE_URL` configura a conexão e é tratada como segredo pela aplicação.
- Sem `DATABASE_URL`, o backend usa `sqlite+aiosqlite:///./clima_zap.db` no diretório de execução. Em Docker Compose, o backend aponta para o PostgreSQL do Compose; configure as credenciais pelo `.env`.
- As tabelas `subscribers` e `alert_logs` guardam contatos, estado ativo/inativo, data de cadastro e o resultado dos envios. Cancelar uma inscrição desativa o registro, preservando histórico; uma nova inscrição reativa o mesmo telefone.
- O forecast periódico grava seu status de envio. Os jobs de alertas climáticos ainda apenas geram/logam alertas, sem envio WhatsApp.
- A imagem Docker executa `alembic upgrade head` antes de iniciar a API. Para desenvolvimento local, a partir de `backend/`, rode `python -m alembic upgrade head` antes de iniciar o servidor.
- Para PostgreSQL gerenciado, configure uma URL `postgresql+asyncpg://...` em `DATABASE_URL` e os requisitos de TLS do provedor.
- **PostgreSQL 15** e **Redis 7** também são usados pela **Evolution API**:
  - Evolution persiste instâncias e mensagens no PostgreSQL
  - Evolution usa Redis (`redis://redis:6379/6`, prefixo `clima-zap`) como cache
- Volumes Docker: `postgres_data`, `redis_data`, `evolution_instances`

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

Testes da suíte principal:

| Arquivo | Testes | Cobre |
|---------|--------|-------|
| `tests/test_webhook.py` | 19 | Roteamento de comandos (`/ajuda`, `/cidade`, `/configuracao`, `/inscrever`, `/sair`, `/clima`), silêncio em grupo, dica única no privado, menção nativa, fluxo completo webhook→resposta e autenticação `Bearer` |
| `tests/test_d1_store.py` | 16 | Caminho Cloudflare Workers: bridge do runtime (env→settings, `brt_hour`), persistência em D1 (assinantes, localização, dedupe, dica), alert history e conversão FFI |
| `tests/test_main.py` | 11 | Endpoints, scheduler de alertas, registro/skip dos 3 jobs de forecast (jitter 900s), envio do boletim, endpoint `/api/v1/clima/cariri` (com `?cidade=`) |
| `tests/test_schedule.py` | 7 | Agendamento compartilhado: sorteio do jitter dentro do wall time do Cron Trigger, despacho por expressão de cron (sem duplicar em 06h/14h), crons do `wrangler.jsonc` espelhando as constantes e horas UTC→BRT |
| `tests/test_forecast.py` | 8 | Agregação por período (manhã/tarde/noite), formatação, builders on-demand e periódico |
| `tests/test_persistence.py` | 8 | Persistência/reativação de assinante, histórico de envio, localização (`/configuracao`), dica única e agrupamento de alertas |
| `tests/test_alerts.py` | 5 | Regras de UV, umidade, chuva, múltiplas e nenhuma |
| `tests/test_location.py` | 4 | Presets do Crajubar, fallback de cidade e parsing de `lat,lon` |
| `tests/test_command_parser.py` | 4 | Gramática de invocação: `/cmd`, `@clima-zap cmd`, menção nativa e texto solto |
| `tests/test_geocode.py` | 3 | Geocoder Open-Meteo (sucesso, miss e falha de rede) |
| `tests/test_whatsapp_session.py` | 2 | `connectionState` (sucesso e erro de conexão) |
| `tests/test_resilience.py` | 2 | Retry assíncrono (backoff e limite de tentativas) |
| `tests/test_bot.py` | 1 | Conteúdo do menu de ajuda do bot |
| `tests/test_preview.py` | 1 | Endpoint `/api/v1/forecast/preview` |
| `test/test_health.py` | 2 | `/` online e `/health` healthy (legado) |

Stack: `pytest` + `fastapi.testclient` + `unittest.mock` / `monkeypatch`.

---

## 🔄 CI/CD — GitHub Actions

Pipeline **Clima-Zap CI Pipeline** (`.github/workflows/ci.yml`):

- **Gatilhos:** push (todas as branches) e PR para `main`
- **Runner:** `ubuntu-latest`
- **Job `build-and-test`** (Python 3.11):
  1. Checkout, setup Python 3.11 e `pip install -r requirements.txt`
  2. Suíte de testes: `cd backend && PYTHONPATH=. python -m pytest`
  3. Qualidade: `python -m pylint backend`
  4. Migrations: `alembic upgrade head` + `alembic check` (SQLite)
  5. `docker compose config` + build das imagens `backend` e `frontend`
- **Job `workers-bundle`** (garante que o Worker continua empacotável para Python Workers):
  1. `uvx --from workers-py pywrangler sync` (deps Pyodide)
  2. `npx wrangler deploy --dry-run` (valida o bundle)

Pipeline de CD (`.github/workflows/cd.yml`):

- Executa em push para `main` ou manualmente via `workflow_dispatch`, com `concurrency` para não sobrepor deploys.
- Sincroniza as deps Pyodide (`pywrangler sync`), aplica as migrations do D1 (`wrangler d1 migrations apply --remote`) e faz deploy via `pywrangler deploy`.
- Opcionalmente faz polling em `WORKERS_SERVICE_URL/health` (até 5 min) após o deploy.

Para ativar o CD: crie um [API Token](https://dash.cloudflare.com/profile/api-tokens) com permissão **Account → Workers Scripts → Edit** e **D1 → Edit**, e cadastre `CLOUDFLARE_API_TOKEN` e `CLOUDFLARE_ACCOUNT_ID` no environment `production` do GitHub. Opcionalmente cadastre `WORKERS_SERVICE_URL=https://clima-zap-api.<subdominio>.workers.dev` para ativar o health check.

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
- [x] Jitter anti-spam nos boletins no Cloudflare Workers (sorteio 0–15min no handler `scheduled`, limitado pelo wall time de 15min do Cron Trigger)
- [x] Envio real de alertas agendados ao WhatsApp com histórico de sucesso/falha
- [x] Verificação opcional do webhook via token (`WEBHOOK_AUTH_TOKEN` → `Authorization: Bearer`)
- [ ] UI do frontend com dados climáticos em tempo real (componente hoje é placeholder)
- [ ] Estilos SCSS modulares (`*.module.scss` + `_variables.scss`)
- [ ] Router no frontend (react-router)
- [ ] Migrar a aplicação para PostgreSQL gerenciado (Neon/Supabase), se necessário
- [x] Deploy do backend no Cloudflare Workers (D1 + Cron Triggers) e workflow de CD para Workers
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
