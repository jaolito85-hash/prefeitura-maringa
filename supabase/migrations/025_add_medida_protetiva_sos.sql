-- 025_add_medida_protetiva_sos.sql
-- Adiciona o campo de medida protetiva ao cadastro do SOS Mulher.
-- Coletado no fluxo "Cadastro mulher segura" do bot (pergunta SIM/NÃO)
-- e exibido no painel SOS Mulher ao lado da foto do agressor.
--
-- Nullable e sem DEFAULT de proposito: cadastros antigos (anteriores a esta
-- feature) ficam NULL = "Não informado", enquanto novos cadastros sempre
-- gravam true/false explicitamente.

ALTER TABLE sos_cadastros ADD COLUMN IF NOT EXISTS medida_protetiva BOOLEAN;

COMMENT ON COLUMN sos_cadastros.medida_protetiva IS
  'A vítima possui medida protetiva contra o agressor? true/false; NULL = não informado (cadastros antigos).';
