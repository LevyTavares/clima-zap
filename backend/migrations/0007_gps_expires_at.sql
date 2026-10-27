-- Expiração (epoch) do aguardo de localização GPS (2 minutos).
ALTER TABLE subscribers ADD COLUMN gps_expires_at REAL;