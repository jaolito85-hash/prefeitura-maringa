-- ============================================================
-- NODE DATA MARINGÁ — Migration 014: Mídia nas ocorrências
-- Adiciona campos para armazenar fotos/vídeos das ocorrências
-- ============================================================

ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS midia_urls TEXT[] DEFAULT '{}';
ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS tem_foto BOOLEAN DEFAULT false;
ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS tem_video BOOLEAN DEFAULT false;

COMMENT ON COLUMN ocorrencias.midia_urls IS 'URLs das evidências no Supabase Storage';
COMMENT ON COLUMN ocorrencias.tem_foto IS 'true se tem pelo menos uma foto';
COMMENT ON COLUMN ocorrencias.tem_video IS 'true se tem pelo menos um vídeo';
