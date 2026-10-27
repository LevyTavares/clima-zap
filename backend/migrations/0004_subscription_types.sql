-- Inscrição modular: alertas climáticos e boletins periódicos independentes.
-- Aplicar com: npx wrangler d1 migrations apply clima-zap --remote

ALTER TABLE subscribers ADD COLUMN receive_alerts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE subscribers ADD COLUMN receive_bulletins INTEGER NOT NULL DEFAULT 0;

-- Preserva o comportamento anterior: quem estava inscrito passa a receber
-- alertas; grupos inscritos passam a receber boletins.
UPDATE subscribers SET receive_alerts = is_active;
UPDATE subscribers SET receive_bulletins = is_active WHERE phone LIKE '%@g.us';