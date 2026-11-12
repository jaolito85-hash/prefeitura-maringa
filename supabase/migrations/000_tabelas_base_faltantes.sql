-- ============================================================
-- NODE DATA MARINGÁ — Migration 000: tabelas que existiam só no banco
-- feedbacks e sessoes_conversa foram criadas direto no Supabase antigo
-- (kuhtndyhuddjpqimuijn) e nunca entraram no histórico. Sem elas os seeds
-- 010/011 e o worker quebram. Roda ANTES da 001. IDEMPOTENTE.
-- Esquema baseado no prefeitura-parobe (024_create_feedbacks e
-- reconcile_sos_schema) + colunas usadas pelo worker de Maringá.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS feedbacks (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  protocolo TEXT NOT NULL UNIQUE,
  telefone TEXT NOT NULL,
  nome TEXT,
  categoria TEXT,
  sentimento TEXT,                     -- positivo | negativo | neutro
  urgencia TEXT DEFAULT 'normal',
  mensagem TEXT NOT NULL,
  resumo TEXT,
  endereco TEXT,
  bairro TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  status TEXT DEFAULT 'novo',
  departamento TEXT,
  operador TEXT,
  notas TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_feedbacks_status     ON feedbacks(status);
CREATE INDEX IF NOT EXISTS idx_feedbacks_sentimento ON feedbacks(sentimento);
CREATE INDEX IF NOT EXISTS idx_feedbacks_created    ON feedbacks(created_at DESC);

CREATE TABLE IF NOT EXISTS sessoes_conversa (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  telefone TEXT NOT NULL UNIQUE,
  canal TEXT,
  etapa TEXT,
  registro_id TEXT,
  protocolo TEXT,
  arb_id TEXT,
  empresa_nome TEXT,
  contexto JSONB DEFAULT '{}'::jsonb,
  expira_em TIMESTAMPTZ,
  handoff_ativo BOOLEAN DEFAULT false,
  handoff_operador TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sessoes_expira ON sessoes_conversa(expira_em);
