-- Janela (minutos) da previsão on-demand por contato: NULL = padrão (60).
ALTER TABLE subscribers ADD COLUMN window_minutes INTEGER;
