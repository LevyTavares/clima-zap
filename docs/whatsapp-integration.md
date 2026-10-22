# WhatsApp Integration (Evolution API)

## Overview

Clima-Zap uses Evolution API for WhatsApp messaging. This document explains setup, configuration, and usage.

## Architecture

```
WhatsApp User → Evolution API → Webhook → Clima-Zap → Evolution API → WhatsApp User
```

## Setup

### 1. Run Evolution API (Docker)

```bash
docker run -d \
  --name evolution-api \
  -p 8080:8080 \
  -v evolution_store:/evolution/store \
  -e SERVER_URL=http://localhost:8080 \
  -e APIKEY=your_secure_api_key \
  atendai/evolution-api
```

> O Compose da raiz já sobe essa stack (`docker compose up -d postgres redis
> evolution-api`). Em produção, a Evolution precisa de um host always-on com
> **HTTPS público** (o Worker não alcança `localhost`) — veja o README.

### 2. Create Instance

```bash
curl -X POST "http://localhost:8080/instance/create" \
  -H "apikey: your_secure_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "clima-zap",
    "number": "558899887766",
    "qrcode": true,
    "integration": "WHATSAPP-BAILEYS"
  }'
```

### 3. Set Webhook

```bash
curl -X POST "http://localhost:8080/webhook/set/clima-zap" \
  -H "apikey: your_secure_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "enabled": true,
      "url": "http://your-server:8000/api/v1/webhook",
      "events": ["MESSAGES_UPSERT"],
      "byEvents": false,
      "base64": false
    }
  }'
```

> No Cloudflare Workers a URL é `https://clima-zap-api.<subdominio>.workers.dev/api/v1/webhook`
> (o `WEBHOOK_AUTH_TOKEN` é obrigatório em produção; adicione também
> `"headers": {"Authorization": "Bearer <token>"}` ao payload do webhook).
> A Evolution continua hospedada fora do Worker (veja *Onde hospedar a
> Evolution API?* no README) e precisa alcançar essa URL por HTTPS.

### 4. Environment Variables

Set everything in the root `.env` (copied from `.env.example`) — used by Docker Compose and the backend:

```bash
EVOLUTION_API_URL="http://localhost:8080"  # Docker overrides to http://evolution-api:8080
EVOLUTION_API_KEY="your_secure_api_key"
EVOLUTION_INSTANCE_NAME="clima-zap"
FORECAST_GROUP_JID="120363xxxxxxxxxx@g.us"  # optional: group periodic bulletin
```

## Webhook Payload

Evolution API sends POST to `/api/v1/webhook`:

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

## Supported Commands

Commands are recognized in **two invocation forms** only:

1. `/command [args]` — e.g. `/clima`, `/cidade Crato`;
2. `@clima-zap command [args]` — the bot name comes from `BOT_NAME`; a native WhatsApp mention (`@number`) also counts and requires `TARGET_PHONE_NUMBER` (the bot's own number).

| Command | Response |
|---------|----------|
| `/help`, `/?`, `/comandos`, `/ajuda` | Help menu with the command list |
| `/status`, `/status?` | System status |
| `/forecast`, `/previsao`, `/previsão`, `/previzao`, `/previzão`, `/clima` | Weather forecast + active alerts (uses the location set via `/configuracao`) |
| `/configuracao` | Show the current location (default region when unset) |
| `/configuracao <city>` | Set the location — Crajubar presets or any city (Open-Meteo geocoder) |
| `/configuracao <lat,lon>` | Set by coordinates (e.g. `/configuracao -7.23, -39.31`) |
| `/configuracao padrao` | Clear the location and return to the default region |
| `/cidade <name>` | Shortcut of `/configuracao` for cities |
| `/inscrever` | Subscribe the contact to weather alerts |
| `/sair` | Unsubscribe the contact from weather alerts |
| Unknown command (`/foo`) | Command-not-understood message pointing to `/ajuda` |
| Non-command text | In groups: silence. In DMs: a one-time hint with `/ajuda`. |

Plain text without `/` or a mention is **not** a command (`ajuda` alone is ignored).

### Webhook authentication (required in production)

If `WEBHOOK_AUTH_TOKEN` is set, `POST /api/v1/webhook` requires the header `Authorization: Bearer <token>` (HTTP 401 otherwise). Configure the same value as a **custom header** on the Evolution API instance webhook (`webhook.headers`). When empty the endpoint stays open, but only in development: with `ENVIRONMENT=production` it responds **503** until the token is configured (fail closed).

## Periodic Group Forecast

The backend registers three APScheduler jobs that push a period bulletin to `FORECAST_GROUP_JID` (when set) **and to every active group subscriber** — groups that ran `/inscrever` (JID ending in `@g.us`). Each group receives the bulletin for its own saved location (`/configuracao`/`/cidade`); groups without a location get the default region, and targets are deduplicated.

| Job | Base hour (America/Fortaleza) | Period covered | Jitter |
|-----|------------------------------|----------------|--------|
| `forecast_morning` | 06:00 | 06h–12h | 0–15 min |
| `forecast_afternoon` | 14:00 | 12h–18h | 0–15 min |
| `forecast_night` | 20:00 | 18h–06h (next day) | 0–15 min |

Jobs are registered even when `FORECAST_GROUP_JID` is empty — the bulletins then go only to subscribed groups. Private chats (DMs) do **not** receive bulletins, only weather alerts. To find a group JID: subscribe it with `/inscrever` or read `remoteJid` in webhook/Evolution logs (ends with `@g.us`).

Replies to commands sent **inside a group** also go to the group (full JID preserved).

## Testing

### Local Test

```bash
cd backend
python -m uvicorn app.main:app --reload

# Send test webhook
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
      "message": {
        "conversation": "/help"
      }
    },
    "sender": "558899887766@s.whatsapp.net"
  }'
```

## Security

- Set `WEBHOOK_AUTH_TOKEN` in production (the endpoint fails closed with 503 without it) and send it as a custom `Authorization: Bearer <token>` header on the Evolution webhook
- Use HTTPS for the webhook URL and for `EVOLUTION_API_URL` — the API key travels to Evolution on every send
- Restrict CORS to the frontend origin via `CORS_ORIGINS` (wildcard is ignored)
- Store API keys in environment variables and rotate `EVOLUTION_API_KEY` / `POSTGRES_PASSWORD` off the template placeholders
- Never commit `.env` files
- Evolution API cannot run on Cloudflare Workers (persistent WhatsApp socket, PostgreSQL/Redis, instance storage). Host it on an always-on Docker host reachable over public HTTPS — see the README section *Onde hospedar a Evolution API?*

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Webhook not receiving | Check Evolution API logs, verify URL |
| Messages not sending | Verify API key, check instance connection |
| QR code not appearing | Restart Evolution API container |
| No periodic bulletin in group | Set `FORECAST_GROUP_JID` in root `.env` or subscribe the group with `/inscrever`; restart the backend and check startup log for `Forecast periódico ativo` |
| Bulletin job registered but no message | Check backend logs for `Forecast ... enviado` / errors; verify Evolution instance `connectionState` |

## References

- [Evolution API Documentation](https://doc.evolution-api.com)
- [evolution-whatsapp PyPI](https://pypi.org/project/evolution-whatsapp/)
