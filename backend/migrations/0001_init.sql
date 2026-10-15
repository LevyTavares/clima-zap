-- Schema do Clima-Zap para Cloudflare D1 (espelha as migrations do Alembic).
-- Aplicar com: npx wrangler d1 migrations apply clima-zap --remote

CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL UNIQUE,
    name TEXT,
    city TEXT,
    registered_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_subscribers_phone ON subscribers (phone);

CREATE TABLE IF NOT EXISTS alert_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    alert_type TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subscriber_id INTEGER REFERENCES subscribers (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_alert_logs_alert_type ON alert_logs (alert_type);

-- Dedupe dos eventos do webhook (o isolate não guarda estado confiável).
CREATE TABLE IF NOT EXISTS seen_messages (
    message_id TEXT PRIMARY KEY,
    seen_at REAL NOT NULL
);
