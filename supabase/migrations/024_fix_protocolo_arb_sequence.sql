-- ============================================================
-- NODE DATA MARINGÁ — Migration 024: Corrigir geração do protocolo ARB
-- ============================================================
-- Mesma correção da migration 023, aplicada à arborização. O worker gerava
-- ARB-YYYY-XXXXX lendo MAX(protocolo)+1 via REST; em erro transitório do
-- Supabase caía num fallback UUID (ex: ARB-2026-EFB1F398) que poluía a coluna
-- e travava o gerador. Agora usa a sequence atômica arborizacao_seq via RPC.
-- ============================================================

CREATE OR REPLACE FUNCTION public.proximo_protocolo_arb()
RETURNS text
LANGUAGE sql
VOLATILE
AS $$
  SELECT 'ARB-' || EXTRACT(YEAR FROM now())::int || '-' ||
         LPAD(nextval('arborizacao_seq')::text, 5, '0');
$$;

GRANT EXECUTE ON FUNCTION public.proximo_protocolo_arb() TO service_role, anon, authenticated;
GRANT USAGE ON SEQUENCE arborizacao_seq TO service_role;

-- Re-sincroniza a sequence acima do maior número real de arborização.
SELECT setval('arborizacao_seq',
  COALESCE((SELECT max((substring(protocolo from 'ARB-[0-9]{4}-([0-9]{5})'))::int) FROM arborizacao WHERE protocolo ~ '^ARB-[0-9]{4}-[0-9]{5}$'), 0) + 1,
  false);
