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
      "conversation": "help"
    }
  },
  "sender": "558899887766@s.whatsapp.net"
}
```

## Supported Commands

| Command | Response |
|---------|----------|
| `help`, `?`, `comandos`, `ajuda` | Help text |
| `status`, `status?` | System status |
| `forecast`, `previsao`, `previsão`, `previzao`, `previzão`, `clima` | Weather forecast |
| Other | Command not understood |

## Periodic Group Forecast

If `FORECAST_GROUP_JID` is set (group JID ending in `@g.us`), the backend registers three APScheduler jobs that push a period bulletin to that group:

| Job | Base hour (America/Fortaleza) | Period covered | Jitter |
|-----|------------------------------|----------------|--------|
| `forecast_morning` | 06:00 | 06h–12h | 0–15 min |
| `forecast_afternoon` | 14:00 | 12h–18h | 0–15 min |
| `forecast_night` | 20:00 | 18h–06h (next day) | 0–15 min |

Jobs are **not registered** when `FORECAST_GROUP_JID` is empty. To find the JID: send any message in the group and read `remoteJid` in webhook/Evolution logs (ends with `@g.us`).

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
        "conversation": "help"
      }
    },
    "sender": "558899887766@s.whatsapp.net"
  }'
```

## Security

- Verify webhook signatures in production
- Use HTTPS for webhook URLs
- Store API keys in environment variables
- Never commit `.env` files

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Webhook not receiving | Check Evolution API logs, verify URL |
| Messages not sending | Verify API key, check instance connection |
| QR code not appearing | Restart Evolution API container |
| No periodic bulletin in group | Set `FORECAST_GROUP_JID` in root `.env`, `docker compose up -d backend`, check startup log for `Forecast periódico ativo` |
| Bulletin job registered but no message | Check backend logs for `Forecast ... enviado` / errors; verify Evolution instance `connectionState` |

## References

- [Evolution API Documentation](https://doc.evolution-api.com)
- [evolution-whatsapp PyPI](https://pypi.org/project/evolution-whatsapp/)
