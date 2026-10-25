-- Sessões administrativas de 7 dias (/admin register). O fingerprint da senha
-- invalida sessões antigas quando ADMIN_PASSWORD muda; notified_at evita
-- repetir o aviso de expiração.
-- Aplicar com: npx wrangler d1 migrations apply clima-zap --remote

CREATE TABLE IF NOT EXISTS admin_sessions (
    phone TEXT PRIMARY KEY,
    password_fingerprint TEXT NOT NULL,
    registered_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    notified_at REAL
);

CREATE INDEX IF NOT EXISTS ix_admin_sessions_expires_at
    ON admin_sessions (expires_at);
