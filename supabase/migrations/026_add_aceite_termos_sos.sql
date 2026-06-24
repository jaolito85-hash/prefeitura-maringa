-- 026_add_aceite_termos_sos.sql
-- Consentimento LGPD do Cadastro Mulher Segura.
-- A primeira mensagem do cadastro apresenta um termo de aceite e exige "SIM"
-- explícito antes de coletar qualquer dado. Estas colunas registram esse
-- consentimento (quando e qual versão do texto foi aceita).
--
-- Nullable e idempotente (ADD COLUMN IF NOT EXISTS), não-destrutivo.
-- Cadastros antigos (anteriores ao termo) ficam NULL.

ALTER TABLE sos_cadastros ADD COLUMN IF NOT EXISTS aceite_termos BOOLEAN;
ALTER TABLE sos_cadastros ADD COLUMN IF NOT EXISTS aceite_termos_em TIMESTAMPTZ;
ALTER TABLE sos_cadastros ADD COLUMN IF NOT EXISTS aceite_termos_versao TEXT;

COMMENT ON COLUMN sos_cadastros.aceite_termos IS
  'Consentimento LGPD: a mulher digitou SIM no termo de aceite. NULL = cadastro anterior ao termo.';
COMMENT ON COLUMN sos_cadastros.aceite_termos_em IS
  'Data/hora (UTC) em que o aceite foi registrado.';
COMMENT ON COLUMN sos_cadastros.aceite_termos_versao IS
  'Versão do texto do termo aceito (ex: v1-2026-06).';
