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

As regras são aplicadas em três pontos: endpoint `/api/v1/clima/cariri`, scheduler agendado (6×/dia) e comando `forecast` no WhatsApp. Endpoint e scheduler avaliam a **janela das próximas 3h** (`ALERT_WINDOW_MINUTES`) — média de umidade, pico de chuva e UV máximo —, não a leitura instantânea; o `/clima` usa a mesma agregação na janela escolhida com `/janela`.

---

## ✅ Funcionalidades

### 🌦️ Clima e alertas

- **Previsão Open-Meteo** (sem API key): condições atuais (temperatura, umidade, chuva, UV), máximas/mínimas do dia e série horária (precipitação, UV, `weather_code`) para 2 dias, fuso `America/Fortaleza`
- **Motor de regras preventivas** — UV ≥ 8.0, umidade ≤ 30%, chuva ≥ 70% — aplicado no endpoint, nos jobs agendados e no comando `/clima`, com texto em Markdown de WhatsApp
- **Local por assinante**: presets do Crajubar (Barbalha, Juazeiro do Norte, Crato por nome, número ou emoji), qualquer cidade pelo geocoder da Open-Meteo, coordenadas `lat,lon`, localização GPS (opt-in, ver abaixo), e `/configurar padrao` para voltar à região padrão
- **`/comparar`** — tabela compacta (uma linha por cidade) com as 3 cidades do Crajubar na mesma janela
- **Janela configurável** com `/janela` (`1h`, `2h`, `3h`, `4h` ou `padrao`): vale para `/clima` e `/comparar` do contato; sem escolha, usa `FORECAST_WINDOW_MINUTES` (60 min). Janelas de até 4h usam a série de 15 min da Open-Meteo (`minutely_15`), incluindo o bloco do horário corrente — quando não há variação real, a mensagem mostra um valor único em vez de uma faixa repetida
- **Uma agregação, dois horizontes**: alertas agendados e `/api/v1/clima/cariri` avaliam as próximas 3h; `/clima` avalia a janela do contato. Mesma função (`aggregate_window`), mesma semântica (umidade média, chuva de pico, UV máximo)
- **Cache em memória por local** (10 min) nas consultas à Open-Meteo

### 💬 Bot de WhatsApp

- **Gramática estrita**: comandos só valem como `/comando` ou `@clima-zap comando` (nome de `BOT_NAME`, ou menção nativa com `TARGET_PHONE_NUMBER`); em grupo o bot fica calado fora de comandos, no privado envia uma dica única de `/ajuda`
- **Comandos**: `/ajuda`, `/status`, `/clima` (aliases `forecast`/`previsao`/…), `/configurar` (aliases `configuracao`/`cidade`), `/comparar`, `/inscrever`, `/sair`, `/agendar` — ver [tabela](#comandos-suportados)
- **Inscrição modular**: `alertas`, `boletins` ou `todos`, tanto nos comandos quanto na API
- **Boletim personalizado por grupo** (`/agendar HH:MM`, `/agendar off`)
- **Localização por GPS** (opt-in): `/configurar gps` (ou `/cidade gps`) abre um aguardo de 2 min; o pin/live location enviado nesse intervalo salva o local e é confirmado com `/clima`. Pin enviado fora do aguardo não sobrescreve a cidade escolhida
- **Deduplicação de mensagens** por id da Evolution (TTL 5 min)
- **Escrita única das mensagens**: faixa de temperatura, linha de UV e dica de saúde compartilhadas por janela, período e comparativo (tom e precisão não divergem)
- **Colunas de `subscribers` em fonte única** (`app/db/columns.py`) usada pelo domínio e pelo adaptador D1, com teste que barra divergência em relação ao ORM
- **Verificação da instância** WhatsApp (`/instance/connectionState`) usada por `/status` e `/admin status`
- **Administração com sessão** (`/admin`): liberação por número com senha, sessão de 7 dias, allowlist opcional, aviso de vencimento — ver [Administração](#administração-admin)

### ⏱️ Agendamento

- **6 alertas por dia** (06h, 08h, 12h, 14h, 16h, 18h BRT) com jitter 0–5 min anti-spam
- **Boletim periódico 3×/dia** no grupo (06h, 14h, 20h BRT) com jitter 0–15 min, alvo em `FORECAST_GROUP_JID`
- **Boletins personalizados** por grupo (cron de minuto em minuto processa só os horários cadastrados)
- **Aviso de sessão administrativa** vencendo, verificado a cada 5 min
- **Fonte única do cronograma** em `app/core/schedule.py` — APScheduler no Docker, Cron Triggers no Workers (mesmas horas UTC, jitter dentro do wall time de 15 min)
- **Prune diário** do histórico de envios (`alert_logs`, retenção de 90 dias)

### 🗄️ Persistência

- **Assinantes, local, tipos de inscrição, horário de boletim, histórico de envios e sessões admin** persistidos em ambos os caminhos
- **SQLAlchemy async + Alembic** (SQLite/PostgreSQL) no Docker; **Cloudflare D1** no Workers, com o mesmo modelo de domínio (`app/domain.py`) e migrations SQL em `migrations/`

### 📡 API REST

- Endpoints de clima, assinatura (`POST /api/v1/subscribe` com `subscribe`/`unsubscribe`), prévia de boletim, webhook, documentação e health checks — ver [Endpoints](#-endpoints-da-api)
- **Webhook assíncrono**: a Evolution recebe `200` antes do processamento (`BackgroundTasks` no Docker, `ctx.waitUntil` no Workers)
- **Health check detalhado** (`/health`) checando banco e Open-Meteo

### 🔐 Segurança e travas operacionais

- **Webhook fail closed** (503 sem `WEBHOOK_AUTH_TOKEN` em produção) com comparação em tempo constante
- **CORS por allowlist** lida a cada request, sem curinga e sem credenciais
- **Avisos de configuração insegura** no startup em produção (`production_warnings`)
- **Travas de ambiente local**: `ENABLE_SCHEDULER=false` e `ALLOW_OUTBOUND=false` por padrão no Compose, para um backend de desenvolvimento não duplicar alertas nem enviar WhatsApp da produção

### 🚀 Infraestrutura e entrega

- **Stack Docker Compose completa** (perfil `dev`): PostgreSQL + Redis + Evolution API + Backend + Frontend, com healthchecks
- **Cloudflare Workers** (Python Worker + D1 + Cron Triggers + assets estáticos das docs), mesmo código do Docker com imports tardios
- **CI (GitHub Actions)**: testes, pylint (`--fail-under=9.0`), migrations Alembic, `docker compose config`, build das imagens e `wrangler deploy --dry-run` do bundle Worker
- **CD (GitHub Actions)**: push em `main` → `pywrangler sync`, migrations D1 remotas, `pywrangler deploy` e checagem de `/health` (requer os segredos `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID`)
- **Frontend React + Vite** — scaffolding pronto (build no CI e no Compose); a UI com dados em tempo real ainda é placeholder (ver seção *Roadmap*)

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
│   │   │   ├── cors.py           # CORS por allowlist (lido por request)
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
│   ├── pyproject.toml            # Deps do bundle Workers (Pyodide, sem SQLAlchemy/APScheduler)
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

# 3. Build e start (perfil dev é obrigatório)
docker compose --profile dev up --build -d

# 4. Verificar status
docker compose --profile dev ps

# Logs do backend
docker compose --profile dev logs -f backend
```

> **Proteção local:** o Compose sobe com `ENABLE_SCHEDULER=false` e
> `ALLOW_OUTBOUND=false`. Assim o backend local não agenda alertas/boletins nem
> envia WhatsApp por padrão, evitando duplicar o Worker de produção. Para testar
> envios, use uma instância/número de teste e habilite explicitamente:
>
> ```bash
> ALLOW_OUTBOUND=true ENABLE_SCHEDULER=true docker compose --profile dev up -d
> ```

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
docker compose --profile dev up -d postgres redis evolution-api

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
| GET | `/api/v1/clima/cariri` | Dados Climáticos | Previsão atual + alertas gerados (`?cidade=Barbalha\|Juazeiro do Norte\|Crato` ou qualquer cidade) |
| GET | `/api/v1/forecast/preview` | Forecast | Prévia fixa do layout do relatório (teste rápido no Swagger) |
| POST | `/api/v1/subscribe` | Subscription | Inscreve/cancela (`action`: `subscribe`\|`unsubscribe`, `types`: `alertas`\|`boletins`\|`todos`) |
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

O bundle do Worker **não empacota** SQLAlchemy, APScheduler e `tzdata` (~8 MiB a
menos): esses pacotes vivem só no caminho Docker (`requirements.txt`) e são
alcançados por import tardio em `app/db/orm.py` — o modelo compartilhado entre os
dois caminhos é a dataclass de `app/domain.py`. `tests/test_worker_bundle.py`
falha se algum deles voltar ao grafo de imports do Worker.

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
npx wrangler secret put EVOLUTION_API_URL      # URL pública HTTPS da Evolution
npx wrangler secret put EVOLUTION_API_KEY
npx wrangler secret put EVOLUTION_INSTANCE_NAME
npx wrangler secret put FORECAST_GROUP_JID   # opcional: boletins 06/14/20h
npx wrangler secret put WEBHOOK_AUTH_TOKEN   # obrigatório em produção (503 sem ele)
npx wrangler secret put ADMIN_PASSWORD       # opcional: habilita /admin (senha longa)
npx wrangler secret put TARGET_PHONE_NUMBER  # opcional: menção nativa @número

# 5. Deploy
uvx --from workers-py pywrangler deploy
```

- **CORS:** liste as origens do frontend em `vars.CORS_ORIGINS` do
  `wrangler.jsonc` (ex.: `"CORS_ORIGINS": "https://clima-zap.vercel.app"`).
  Vazio = nenhuma origem cross-origin; `*` é ignorado de propósito
- **Webhook da Evolution:** `https://clima-zap-api.<subdominio>.workers.dev/api/v1/webhook`
- **Cron Triggers:** alertas `0 9,11,15,17,19,21 * * *` (06/08/12/14/16/18h BRT),
  boletins `0 9,17,23 * * *` (06/14/20h BRT) e verificação de sessão admin
  `*/5 * * * *` — America/Fortaleza = UTC-3 fixo.
  Cada expressão dispara só o job dela (as duas coincidem em 06h/14h BRT, sem
  isso os envios duplicariam) e o boletim aguarda o jitter anti-spam 0–15min
  antes do envio — expressões e jitter em `app/core/schedule.py`
- **Docs markdown** (`/docs/whatsapp`, `/docs/docker`) são servidos dos Assets
  do Worker (diretório `docs/` no `wrangler.jsonc`)
- **Dev local:** `uvx --from workers-py pywrangler dev` (workerd + D1 local;
  aplique antes `npx wrangler d1 migrations apply clima-zap --local`)

### Onde hospedar a Evolution API?

A Evolution API **não roda no Cloudflare Workers**: é Node.js/Baileys e mantém
um socket permanente com o WhatsApp, além de exigir PostgreSQL, Redis e disco
para as instâncias — nada disso existe no runtime do Worker (isolate efêmero,
sem socket persistente nem filesystem).

Ou seja: o Worker é só o *backend* do Clima-Zap. A Evolution fica **externa** ao
Worker e a comunicação é bidirecional por HTTPS:

| Sentido | Quem chama | Requisito |
|---------|------------|-----------|
| Worker → Evolution | envio de mensagens (API key no header) | URL **pública HTTPS** em `EVOLUTION_API_URL` |
| Evolution → Worker | webhook `/api/v1/webhook` (Bearer) | Evolution com saída para a internet + URL HTTPS do Worker |

Opções para produção:

- **VPS/servidor always-on** rodando o `docker compose` da Evolution, exposto por
  **Cloudflare Tunnel** (recomendado: HTTPS sem abrir portas, no mesmo
  ecossistema do Worker). Suba só os serviços da Evolution (`postgres`, `redis`,
  `evolution-api`).
- **PaaS com volume persistente** (Fly.io, Railway, Render…) + PostgreSQL/Redis
  gerenciados.
- **Cloudflare Containers** para concentrar no mesmo provedor — ainda exige
  storage persistente para a sessão Baileys e Postgres/Redis.

Em qualquer caso: `EVOLUTION_API_URL` nunca é `localhost` (o Worker não alcança a
sua máquina) e o `SERVER_URL` da própria Evolution deve ser a URL HTTPS pública
dela — o pareamento/QR depende disso.

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
| `/ajuda <comando>` | Ajuda de um comando só (ex: `/ajuda janela`); aceita aliases (`/ajuda previzão`) |
| `/status`, `/status?` | Status da API + estado da instância WhatsApp |
| `/forecast`, `/previsao`, `/previsão`, `/previzao`, `/previzão`, `/clima` | Resumo do clima + alertas ativos (usa o local do `/configurar`) |
| `/configurar` | Mostra o local atual (ou a região padrão) e as opções numeradas |
| `/configurar <cidade>` | Define o local — presets do Crajubar ou qualquer cidade (geocoder Open-Meteo) |
| `/configurar <lat,lon>` | Define por coordenadas (ex: `/configurar -7.23, -39.31`) |
| `/configurar padrao` | Remove o local e volta à região padrão |
| `/configuracao …`, `/cidade …` | Aliases de `/configurar` (mesmas validações: cidade, coordenadas, `gps`, `padrao`) |
| `/comparar`, `/crajubar` | Tabela compacta (uma linha por cidade) com Barbalha, Juazeiro do Norte e Crato na janela escolhida |
| `/janela [1h\|2h\|3h\|4h\|padrao]` | Janela da previsão on-demand do contato; sem argumento mostra as opções numeradas (envie `1`–`4` ou `0` para o padrão) |
| `/inscrever [alertas\|boletins\|todos]` | Ativa o envio de alertas climáticos e/ou boletins (padrão: todos) |
| `/sair [alertas\|boletins\|todos]` | Cancela a inscrição nos tipos informados |
| `/agendar HH:MM` · `/agendar off` | (Grupos) agenda/desativa o boletim personalizado do grupo |
| `/admin …` | Administração com sessão — ver [Administração](#administração-admin) |
| `/configurar gps` · `/cidade gps` | Aguarda (2 min) o envio de uma localização GPS pelo WhatsApp |
| Comando desconhecido (`/foo`) | Mensagem de comando não reconhecido + `/ajuda` |
| Texto sem invocação | Grupo: silêncio · Privado: dica única de `/ajuda` |

> Texto sem `/` e sem menção **não** é comando: `ajuda` puro é ignorado.

### Administração (`/admin`)

O acesso é liberado **por número** e dura **7 dias**: autentique uma vez com a
senha e use as demais ações sem repeti-la. O comando só funciona no **privado**;
em grupo o bot responde como comando desconhecido para não expor a
administração. Opcionalmente, `ADMIN_PHONE` limita o uso a um único número.

```text
/admin register <senha>                       # libera este número por 7 dias (aceita --<senha>)
/admin status                                 # API, WhatsApp, assinantes, grupos e últimos envios
/admin boletim [manha|tarde|noite]            # dispara o boletim agora (sem período = atual)
/admin alertas                                # executa o job de alertas agora
/admin grupos                                 # lista grupos inscritos e locais
/admin ping                                   # teste rápido
/admin logout                                 # encerra a sessão deste número
/admin ajuda                                  # ações disponíveis
```

- A senha só é necessária no `register`; depois a sessão fica vinculada ao
  telefone (D1 no Workers, Postgres no Docker) e expira sozinha em 7 dias.
- Quando a sessão vence, o bot envia um aviso no WhatsApp para o número (a
  verificação roda a cada 5 min). Se o envio falhar, tenta de novo no ciclo
  seguinte. O aviso não é repetido depois de entregue.
- Trocar `ADMIN_PASSWORD` invalida as sessões abertas: o hash da senha é
  comparado no banco a cada uso.
- O formato antigo `/admin <senha> <ação>` continua aceito para uso avulso (não
  cria sessão).
- A senha nunca é registrada nos logs (o webhook redige `/admin` antes do log)
  nem aparece nas respostas; ainda assim, use só no privado.
- Gere uma senha longa: `openssl rand -hex 16`. No Workers, configure como
  secret (`npx wrangler secret put ADMIN_PASSWORD`); no Docker, no `.env`.
- `ADMIN_PASSWORD` vazio = administração desabilitada.
- O `/admin` **não** aparece no menu público de `/ajuda`.

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
| `EVOLUTION_API_URL` | `http://localhost:8080` (local) / `http://evolution-api:8080` (Docker, override no compose) | URL da Evolution API. No Workers precisa ser um endpoint **público HTTPS** |
| `EVOLUTION_API_KEY` | `troque-esta-chave` | Chave de autenticação da Evolution API — **troque** antes de usar |
| `EVOLUTION_INSTANCE_NAME` | `clima-zap` | Nome da instância WhatsApp |
| `TARGET_PHONE_NUMBER` | *(vazio)* | Número do próprio bot (só dígitos) — ativa a menção nativa `@número` como invocação de comando |
| `BOT_NAME` | `clima-zap` | Nome do bot na invocação textual: `@clima-zap previsao` |
| `FORECAST_GROUP_JID` | *(vazio)* | Grupo alvo do boletim 3×/dia (`120363...@g.us`). Vazio = jobs desativados |
| `FORECAST_WINDOW_MINUTES` | `60` | Janela padrão (min) do `/clima` quando o contato não escolheu com `/janela` (`1h`–`4h`) |
| `WEBHOOK_AUTH_TOKEN` | *(vazio)* | Token do header `Authorization: Bearer <token>` (configure também no webhook da Evolution). **Obrigatório em produção**: sem ele o webhook responde 503 em vez de aceitar eventos forjados |
| `ADMIN_PASSWORD` | *(vazio)* | Senha do `/admin` (só no privado; usada no `register`, que libera o número por 7 dias). Vazio = administração desabilitada. No Workers: `wrangler secret put ADMIN_PASSWORD` |
| `ADMIN_PHONE` | *(vazio)* | Opcional: número (só dígitos, com DDI) autorizado a usar `/admin`; vazio = qualquer privado que saiba a senha |
| `CORS_ORIGINS` | *(vazio)* | Origens liberadas no CORS, separadas por vírgula (ex.: `https://clima-zap.vercel.app`). Vazio = nenhuma origem cross-origin; `*` é ignorado |
| `DOCS_DIR` | *(vazio → `docs/` da raiz)* / `/docs` (Docker) | Diretório da documentação markdown |
| `POSTGRES_DATABASE` | `evolution` | Banco do PostgreSQL (Evolution) |
| `POSTGRES_USERNAME` | `evolution` | Usuário do PostgreSQL |
| `POSTGRES_PASSWORD` | `troque-esta-senha` | Senha do PostgreSQL — **troque** antes de usar |
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
- O forecast periódico e os alertas climáticos gravam o status de envio em `alert_logs` (e o scheduler envia aos assinantes ativos por cidade).
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
- Todos os serviços usam o perfil `dev`: `docker compose up` sem `--profile dev`
  não sobe nada. O backend local inicia sem scheduler e sem envio real.

### Comandos úteis

```bash
docker compose --profile dev up -d              # iniciar
docker compose --profile dev down               # parar (mantém volumes)
docker compose --profile dev down -v            # parar + apagar volumes (perda de dados!)
docker compose --profile dev logs -f backend    # logs do backend
docker compose --profile dev build backend      # rebuild após mudança de código
docker compose --profile dev restart evolution-api
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
| `tests/test_webhook.py` | 35 | Roteamento de comandos (`/ajuda [comando]`, `/configurar`, `/comparar`, `/janela`, `/inscrever`, `/sair`, `/clima`), menu numerado de `/janela` (sem lista interativa: Baileys não suporta), janela escolhida chegando aos builders de `/clima` e `/comparar` (`/janela padrao` volta ao default), `extract_location`, aguardo de GPS (pin só vale após `/configurar gps`, expira em 2 min), silêncio em grupo, dica única no privado, menção nativa, fluxo completo webhook→resposta, autenticação `Bearer` e fail closed (503) em produção sem token |
| `tests/test_d1_store.py` | 26 | Caminho Cloudflare Workers: bridge do runtime (env→settings, `brt_hour`), persistência em D1 sobre SQLite real com as migrations aplicadas (assinantes, localização, janela da previsão, dedupe, dica), alert history, sessões administrativas e conversão FFI |
| `tests/test_admin_commands.py` | 22 | `/admin` (registro de 7 dias, sessão, senha avulsa, allowlist opcional, só privado): status, boletim sob demanda, alertas, grupos, ping, logout, ajuda e redação da senha nos logs |
| `tests/test_admin_sessions.py` | 4 | Sessões administrativas no banco local: criação/renovação/expiração, logout e aviso de vencimento (uma vez; retry em falha) |
| `tests/test_main.py` | 15 | Endpoints, scheduler de alertas, registro/skip dos 3 jobs de forecast (jitter 900s), trava `ENABLE_SCHEDULER`, verificação de sessão admin a cada 5min, envio do boletim, endpoint `/api/v1/clima/cariri` (com `?cidade=`) |
| `tests/test_config.py` | 10 | Travas de configuração: CORS por allowlist (curinga ignorado, sem credenciais, lido por request), `ENABLE_SCHEDULER`/`ALLOW_OUTBOUND` e avisos `production_warnings` de defaults inseguros (inclui `ADMIN_PASSWORD` curta) |
| `tests/test_evolution_client.py` | 3 | Trava de envio: bloqueado por padrão fora de produção, liberado em produção e com opt-in explícito |
| `tests/test_schedule.py` | 10 | Agendamento compartilhado: sorteio do jitter dentro do wall time do Cron Trigger, despacho por expressão de cron (sem duplicar em 06h/14h), cron de sessão admin, crons do `wrangler.jsonc` espelhando as constantes e horas UTC→BRT |
| `tests/test_forecast.py` | 15 | Agregação por período (manhã/tarde/noite), janela on-demand em série de 15 min (`minutely_15`) com fallback horário incluindo o bloco corrente, chuva desconhecida como `—` (nunca mm→%), alerta de 3h (chuva futura alerta mesmo com o instante seco), comparativo compacto, contrato do texto da mensagem e builders |
| `tests/test_persistence.py` | 12 | Persistência/reativação de assinante, histórico de envio, localização (`/configurar`), boletim personalizado no horário BRT, dica única e agrupamento de alertas |
| `tests/test_alerts.py` | 5 | Regras de UV, umidade, chuva, múltiplas e nenhuma |
| `tests/test_location.py` | 4 | Presets do Crajubar, fallback de cidade e parsing de `lat,lon` |
| `tests/test_command_parser.py` | 4 | Gramática de invocação (`/cmd`, `@clima-zap cmd`, menção nativa, texto solto) e canonicalização de aliases (`previzão`→`clima`, `cidade`→`configurar`) |
| `tests/test_geocode.py` | 3 | Geocoder Open-Meteo (sucesso, miss e falha de rede) |
| `tests/test_whatsapp_session.py` | 2 | `connectionState` (sucesso e erro de conexão) |
| `tests/test_resilience.py` | 2 | Retry assíncrono (backoff e limite de tentativas) |
| `tests/test_bot.py` | 1 | Menu de ajuda do bot e `/ajuda <comando>` (com alias) |
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

Além disso, a suíte cobre duas fronteiras que só quebrariam em produção:
`tests/test_worker_bundle.py` (nada de SQLAlchemy/APScheduler/`tzdata` no grafo do
Worker) e `tests/test_storage_schema.py` (as migrations do D1 espelham o ORM).

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
- [x] Deploy do backend no Cloudflare Workers (D1 + Cron Triggers) e workflow de CD para Workers (o CD só roda com os segredos `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` cadastrados)
- [ ] Broadcast via `TARGET_PHONE_NUMBER`
- [ ] Lint/format (ruff, ESLint, Prettier)
- [ ] LICENSE

---

## 🔐 Segurança

- **CORS por allowlist** (`CORS_ORIGINS`, lido a cada request): sem `*` e sem
  credenciais. Vazio = nenhuma origem cross-origin. O curinga é ignorado de
  propósito (`app/core/cors.py`)
- **Webhook fail closed:** em produção `WEBHOOK_AUTH_TOKEN` é obrigatório — sem
  ele `POST /api/v1/webhook` responde **503** em vez de aceitar eventos
  forjados. A comparação do Bearer é em tempo constante (`secrets.compare_digest`)
- **Ambiente local sem efeito colateral:** o Compose usa o perfil `dev` e força
  `ENABLE_SCHEDULER=false`/`ALLOW_OUTBOUND=false`; sem opt-in explícito o
  backend local não agenda jobs nem envia WhatsApp. Para testar, use uma
  instância/número separado da produção
- **Defaults inseguros:** trocar `EVOLUTION_API_KEY` (`openssl rand -hex 32`) e
  `POSTGRES_PASSWORD` antes de produção. Com `ENVIRONMENT=production` a app
  avisa no startup (`settings.production_warnings`) se ainda estiverem no
  placeholder ou se `EVOLUTION_API_URL` não for HTTPS
- **Evolution API exposta por HTTPS público:** a API key trafega até ela em cada
  envio, e ela precisa alcançar o webhook HTTPS do Worker (veja *Onde hospedar a
  Evolution API*)
- Nunca commitar arquivos `.env` (o `.gitignore` cobre `.env`, `.dev.vars` e
  artefatos do Workers)
- Volumes persistem dados: sobrevivem a `docker compose down`, **não** a `down -v`

---

## 📚 Referências

- [Open-Meteo API](https://open-meteo.com)
- [Evolution API Docs](https://doc.evolution-api.com)
- [evolution-whatsapp (PyPI)](https://pypi.org/project/evolution-whatsapp/)
- [FastAPI](https://fastapi.tiangolo.com)
- [Docker Compose](https://docs.docker.com/compose)
