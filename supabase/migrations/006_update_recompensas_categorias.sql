-- ============================================================
-- NODE DATA MARINGÁ — Migration 006: Atualizar categorias de recompensa
-- Decreto 291/2026 — Programa Cidadão Ativo
--
-- APENAS 5 categorias pagas:
--   1. Pichação (R$ 100)
--   2. Tráfico de Drogas (R$ 300)
--   3. Descarte Irregular de Lixo e Entulhos (R$ 80)
--   4. Furto de Fios e Cabos Elétricos (R$ 150) — NOVA
--   5. Depredação de Patrimônio Público (R$ 150)
--
-- Vandalismo foi REMOVIDO (desativado, não deletado)
-- ============================================================

-- Adicionar nova categoria: furto_fios
INSERT INTO recompensas_config (categoria, valor_padrao, ativo, descricao) VALUES
  ('furto_fios', 150.00, true, 'Furto de fios e cabos elétricos')
ON CONFLICT (categoria) DO UPDATE SET
  valor_padrao = 150.00,
  ativo = true,
  descricao = 'Furto de fios e cabos elétricos',
  updated_at = now();

-- Desativar vandalismo (não é mais categoria paga)
UPDATE recompensas_config SET
  ativo = false,
  updated_at = now()
WHERE categoria = 'vandalismo';
