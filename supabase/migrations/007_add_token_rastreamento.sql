-- 007: Adicionar token_rastreamento ao sos_alertas
-- Permite vincular o alerta SOS à sessão de rastreamento GPS

ALTER TABLE sos_alertas ADD COLUMN IF NOT EXISTS token_rastreamento VARCHAR(12);
