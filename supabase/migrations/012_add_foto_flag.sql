-- ============================================================
-- NODE DATA MARINGÁ — Migration 012: Detecção de origem de foto
-- Adiciona campos para red flag de fotos suspeitas
-- ============================================================

ALTER TABLE denuncias ADD COLUMN IF NOT EXISTS foto_origem TEXT DEFAULT 'desconhecida';
ALTER TABLE denuncias ADD COLUMN IF NOT EXISTS foto_flag TEXT DEFAULT 'none';
ALTER TABLE denuncias ADD COLUMN IF NOT EXISTS foto_flag_motivo TEXT DEFAULT '';

-- Índice para filtrar denúncias suspeitas rapidamente
CREATE INDEX IF NOT EXISTS idx_denuncias_foto_flag ON denuncias(foto_flag);

COMMENT ON COLUMN denuncias.foto_origem IS 'camera_direta | galeria_recente | galeria_antiga | encaminhada | desconhecida';
COMMENT ON COLUMN denuncias.foto_flag IS 'none | low | medium | high';
COMMENT ON COLUMN denuncias.foto_flag_motivo IS 'Motivo legível do flag para o operador';
