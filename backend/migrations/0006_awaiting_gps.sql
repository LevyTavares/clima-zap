-- Flag de aguardo de localização GPS enviada pelo WhatsApp.
ALTER TABLE subscribers ADD COLUMN awaiting_gps INTEGER NOT NULL DEFAULT 0;