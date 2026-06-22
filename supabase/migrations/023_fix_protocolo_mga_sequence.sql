-- ============================================================
-- NODE DATA MARINGÁ — Migration 023: Corrigir geração do protocolo MGA
-- ============================================================
-- Problema: o worker gerava protocolo lendo MAX(protocolo)+1 via REST. Em
-- qualquer erro transitório do Supabase (ex: Cloudflare 1101), caía num
-- fallback que gravava um UUID (ex: MGA-2026-FBFBD8A3). Como 'F' > '0' na
-- ordenação de texto, esse UUID virava o MAX, o parse do número falhava e o
-- gerador resetava para MGA-2026-00001 — colidindo com o índice único.
--
-- Solução: gerar via sequence atômica do Postgres (protocolo_seq), exposta
-- por RPC. Race-free, nunca produz UUID, imune a 500 transitório.
--
-- NÃO toca em arborização (ARB / arborizacao_seq) — fora de escopo.
-- ============================================================

CREATE OR REPLACE FUNCTION public.proximo_protocolo()
RETURNS text
LANGUAGE sql
VOLATILE
AS $$
  SELECT 'MGA-' || EXTRACT(YEAR FROM now())::int || '-' ||
         LPAD(nextval('protocolo_seq')::text, 5, '0');
$$;

GRANT EXECUTE ON FUNCTION public.proximo_protocolo() TO service_role, anon, authenticated;
GRANT USAGE ON SEQUENCE protocolo_seq TO service_role;

-- Re-sincroniza a sequence ACIMA do maior número real entre TODAS as tabelas
-- que usam o formato MGA, para nunca colidir com registros já existentes.
SELECT setval('protocolo_seq', GREATEST(
  COALESCE((SELECT max((substring(protocolo from 'MGA-[0-9]{4}-([0-9]{5})'))::int) FROM denuncias   WHERE protocolo ~ '^MGA-[0-9]{4}-[0-9]{5}$'), 0),
  COALESCE((SELECT max((substring(protocolo from 'MGA-[0-9]{4}-([0-9]{5})'))::int) FROM feedbacks   WHERE protocolo ~ '^MGA-[0-9]{4}-[0-9]{5}$'), 0),
  COALESCE((SELECT max((substring(protocolo from 'MGA-[0-9]{4}-([0-9]{5})'))::int) FROM ocorrencias WHERE protocolo ~ '^MGA-[0-9]{4}-[0-9]{5}$'), 0),
  COALESCE((SELECT max((substring(protocolo from 'MGA-[0-9]{4}-([0-9]{5})'))::int) FROM recompensas WHERE protocolo ~ '^MGA-[0-9]{4}-[0-9]{5}$'), 0)
) + 1, false);
