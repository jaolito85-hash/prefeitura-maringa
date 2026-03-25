-- 016: Adicionar campos de encaminhamento em denúncias
ALTER TABLE denuncias ADD COLUMN IF NOT EXISTS encaminhada_para TEXT DEFAULT '';
ALTER TABLE denuncias ADD COLUMN IF NOT EXISTS encaminhada_em TIMESTAMPTZ;
