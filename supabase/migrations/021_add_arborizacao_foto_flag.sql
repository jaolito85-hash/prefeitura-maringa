-- ============================================================
-- NODE DATA MARINGÁ — Migration 021: Foto flag em arborização
-- Detecção de fotos encaminhadas (red flag) igual denúncias
-- ============================================================

ALTER TABLE arborizacao ADD COLUMN IF NOT EXISTS foto_origem TEXT;
ALTER TABLE arborizacao ADD COLUMN IF NOT EXISTS foto_flag TEXT;
ALTER TABLE arborizacao ADD COLUMN IF NOT EXISTS foto_flag_motivo TEXT;
