-- 015: Adicionar campos de equipe designada e timestamps de encaminhamento/resolução
-- A coluna 'equipe' já existe (001), mas adicionamos equipe_designada e timestamps

ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS equipe_designada TEXT DEFAULT '';
ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS encaminhada_em TIMESTAMPTZ;
ALTER TABLE ocorrencias ADD COLUMN IF NOT EXISTS resolvida_em TIMESTAMPTZ;
