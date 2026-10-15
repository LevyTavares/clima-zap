-- Localização arbitrária (/configuracao: cidade geocodificada ou coordenadas)
-- + registro da dica única de /ajuda enviada no privado.
-- Aplicar com: npx wrangler d1 migrations apply clima-zap --remote

ALTER TABLE subscribers ADD COLUMN latitude REAL;
ALTER TABLE subscribers ADD COLUMN longitude REAL;

-- Dica de /ajuda mostrada uma única vez por contato no privado (o isolate
-- não guarda estado confiável entre requests — mesmo papel de seen_messages).
CREATE TABLE IF NOT EXISTS dm_hints (
    phone TEXT PRIMARY KEY,
    shown_at REAL NOT NULL
);
