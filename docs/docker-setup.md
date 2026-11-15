# Docker Compose Setup

Run whole Clima-Zap stack with one command.

## Services

| Service | Image/Tag | Port | Purpose |
|---------|-----------|------|---------|
| backend | Custom (Python 3.10 + FastAPI) | 8000 | Clima-Zap API |
| frontend | Custom (React + Vite + nginx) | 5173 | Web SPA |
| evolution-api | evoapicloud/evolution-api:v2.2.2 (pinned) | 8080 | WhatsApp provider |
| postgres | postgres:15-alpine | internal | Evolution API DB |
| redis | redis:7-alpine | internal | Evolution API cache |

## Requirements

- Docker Engine + Docker Compose (v2).

## Quick Start

```bash
# 1. Copy env template (single file at repo root)
cp .env.example .env

# 2. Edit secrets in .env (change EVOLUTION_API_KEY + passwords)
#    Optional: FORECAST_GROUP_JID=120363...@g.us → 3x/day group bulletin
vim .env

# 3. Build & start (dev profile is required)
docker compose --profile dev up --build -d

# 4. Check status
docker compose --profile dev ps

# Logs
docker compose --profile dev logs -f backend
```

## Local safety defaults

The local stack starts with:

- `ENABLE_SCHEDULER=false` — no APScheduler jobs (alerts/bulletins);
- `ALLOW_OUTBOUND=false` — no real WhatsApp sends.

This prevents a local backend connected to the same Evolution instance from
duplicating the production Worker. To test sends, use a separate test instance
and opt in explicitly:

```bash
ALLOW_OUTBOUND=true ENABLE_SCHEDULER=true docker compose --profile dev up -d
```

## URLs (local)

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| WhatsApp integration docs | http://localhost:8000/docs/whatsapp |
| Frontend | http://localhost:5173 |
| Evolution Manager UI | http://localhost:8080/manager |

## Pair WhatsApp number (QR)

1. Open http://localhost:8080/manager
2. Autenticar with `EVOLUTION_API_KEY`
3. Tap "Criar Instância" → name: `clima-zap`
4. Scan QR code with WhatsApp
5. Connection state → `open`

## Wire Webhook to backend

Global webhook set in compose points to `http://backend:8000/api/v1/webhook`. To force per-instance:

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

## Common Commands

```bash
docker compose --profile dev up -d            # start
docker compose --profile dev down             # stop (keeps volumes)
docker compose --profile dev down -v          # stop + wipe volumes (data loss!)
docker compose --profile dev logs -f backend  # follow backend logs
docker compose --profile dev build backend    # rebuild after code change
docker compose --profile dev restart evolution-api
```

## Dev Mode (no Docker for backend)

Run backend/Frontend natively, keep Infra in Docker:

```bash
# Only infra
docker compose --profile dev up -d postgres redis evolution-api

# Backend local
cd backend
python -m uvicorn app.main:app --reload

# Frontend local
cd frontend
npm install
npm run dev
```

## Security

- Change `EVOLUTION_API_KEY`, `POSTGRES_PASSWORD` before production.
- Local Compose forces `ENABLE_SCHEDULER=false` and `ALLOW_OUTBOUND=false`; use a
  separate test instance/number before opting in with `ALLOW_OUTBOUND=true`.
- Production: set `WEBHOOK_GLOBAL_URL` to HTTPS public URL, add signature verification in backend.
- Volumes persist data: survive `docker compose down`, NOT `down -v`.
- Evolution API image pinned to `v2.2.2` for stability.