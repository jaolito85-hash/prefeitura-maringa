-- ============================================================
-- NODE DATA MARINGÁ — Migration 027: operadores + permissões
-- 1) Tabela `operadores` (papéis do login Supabase Auth). Existia só no
--    banco antigo; o backend (app/auth.py) lê nome, papel, ativo por id.
-- 2) Projetos Supabase novos não concedem mais privilégios automáticos
--    em public nem ao service_role. Sem os GRANTs abaixo o backend toma
--    "permission denied" e as páginas do SOS (anon) não gravam o GPS.
-- IDEMPOTENTE.
-- ============================================================

CREATE TABLE IF NOT EXISTS operadores (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  nome TEXT NOT NULL,
  email TEXT NOT NULL,
  papel TEXT NOT NULL DEFAULT 'operador'
        CHECK (papel IN ('operador', 'financeiro', 'admin')),
  ativo BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE operadores ENABLE ROW LEVEL SECURITY;

-- Backend/worker (service_role): acesso total ao schema public
GRANT USAGE ON SCHEMA public TO service_role, anon, authenticated;
GRANT ALL ON ALL TABLES    IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES    TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO service_role;

-- Páginas públicas do SOS (mulher-segura.html / monitor-sos.html) usam a
-- anon key direto no REST: lê a sessão pelo token e grava/lê pontos GPS.
GRANT SELECT, INSERT, UPDATE ON emergencia_sessoes TO anon;
GRANT SELECT, INSERT         ON emergencia_pontos  TO anon;
-- O painel (index.html) lê a trilha GPS e assina o Realtime com o operador logado
GRANT SELECT ON emergencia_sessoes, emergencia_pontos TO authenticated;

-- Colunas que o código usa e que também só existiam no banco antigo
-- (sem elas o cadastro Mulher Segura e o painel SOS dão erro 42703)
ALTER TABLE sos_cadastros ADD COLUMN IF NOT EXISTS agressor_foto_url TEXT;
ALTER TABLE sos_alertas   ADD COLUMN IF NOT EXISTS protocolo TEXT;
ALTER TABLE feedbacks     ADD COLUMN IF NOT EXISTS resposta_prefeitura TEXT;

-- Feedbacks também ao vivo (como no banco antigo)
DO $$ BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE feedbacks;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

NOTIFY pgrst, 'reload schema';
