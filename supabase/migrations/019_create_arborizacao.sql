-- ============================================================
-- NODE DATA MARINGÁ — Migration 019: Arborização Urbana
-- Pipeline agentic: cidadão → IA → empresa → fiscal → feedback
-- ============================================================

-- Sequência para protocolos ARB-2026-XXXXX
CREATE SEQUENCE IF NOT EXISTS arborizacao_seq START 1;

-- ============================================================
-- TABELA: arborizacao
-- Solicitações de arborização urbana
-- ============================================================
CREATE TABLE IF NOT EXISTS arborizacao (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  protocolo TEXT NOT NULL UNIQUE,

  -- Cidadão (quem reportou)
  telefone TEXT NOT NULL,
  nome TEXT,
  mensagem TEXT,
  endereco TEXT,
  endereco_normalizado TEXT,
  bairro TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,

  -- Classificação IA
  categoria TEXT NOT NULL,            -- poda_geral|poda_complexa|poda_desbarra|remocao|arvore_caida|retirada_toco|risco_queda
  severidade TEXT DEFAULT 'rotina',   -- emergencia|urgencia|prioridade|rotina
  resumo TEXT,

  -- Fotos antes/depois (arrays separados)
  foto_antes_urls TEXT[] DEFAULT '{}',
  foto_depois_urls TEXT[] DEFAULT '{}',
  tem_foto_antes BOOLEAN DEFAULT false,
  tem_foto_depois BOOLEAN DEFAULT false,

  -- Status pipeline (6 etapas)
  status TEXT DEFAULT 'recebido',     -- recebido|triado|atribuido|em_execucao|concluido|fiscalizado

  -- Empresa contratada
  empresa_atribuida TEXT,
  empresa_telefone TEXT,
  atribuida_em TIMESTAMPTZ,

  -- SLA
  sla_horas INTEGER,
  sla_vencimento TIMESTAMPTZ,
  sla_estourado BOOLEAN DEFAULT false,

  -- Fiscalização (IA + humana)
  fiscal_aprovado BOOLEAN,
  fiscal_confianca INTEGER,           -- 0-100 confiança da IA
  fiscal_obs TEXT,
  fiscal_data TIMESTAMPTZ,
  fiscal_operador TEXT,               -- 'IA' ou nome do fiscal humano

  -- Avaliação do cidadão
  cidadao_avaliacao INTEGER,          -- 1-5 estrelas
  cidadao_avaliacao_obs TEXT,

  -- Operador / notas internas
  operador TEXT,
  notas TEXT,

  -- Timestamps
  triado_em TIMESTAMPTZ,
  concluido_em TIMESTAMPTZ,
  fiscalizado_em TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_arb_status ON arborizacao(status);
CREATE INDEX IF NOT EXISTS idx_arb_categoria ON arborizacao(categoria);
CREATE INDEX IF NOT EXISTS idx_arb_severidade ON arborizacao(severidade);
CREATE INDEX IF NOT EXISTS idx_arb_bairro ON arborizacao(bairro);
CREATE INDEX IF NOT EXISTS idx_arb_created ON arborizacao(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_arb_sla ON arborizacao(sla_vencimento) WHERE sla_estourado = false;
CREATE INDEX IF NOT EXISTS idx_arb_empresa ON arborizacao(empresa_telefone) WHERE empresa_telefone IS NOT NULL;

-- ============================================================
-- TABELA: arborizacao_config
-- Configuração de SLA e cadastro de empresas
-- ============================================================
CREATE TABLE IF NOT EXISTS arborizacao_config (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  tipo TEXT NOT NULL,                 -- 'sla' ou 'empresa'
  chave TEXT NOT NULL UNIQUE,
  valor JSONB NOT NULL,
  ativo BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- SLA padrão por severidade (em horas)
INSERT INTO arborizacao_config (tipo, chave, valor) VALUES
  ('sla', 'emergencia', '{"horas": 4, "descricao": "Risco iminente"}'::jsonb),
  ('sla', 'urgencia',   '{"horas": 24, "descricao": "Possibilidade de danos graves"}'::jsonb),
  ('sla', 'prioridade', '{"horas": 72, "descricao": "Necessita atenção"}'::jsonb),
  ('sla', 'rotina',     '{"horas": 168, "descricao": "Manutenção preventiva"}'::jsonb)
ON CONFLICT (chave) DO NOTHING;

-- Empresas contratadas (demo)
INSERT INTO arborizacao_config (tipo, chave, valor) VALUES
  ('empresa', 'corpus', '{"nome": "Corpus Soluções Ambientais", "telefone": "5544999990050", "contato": "Sr. Ricardo", "zona": "todas"}'::jsonb),
  ('empresa', 'podare', '{"nome": "Podare Serviços Ambientais", "telefone": "5544999990051", "contato": "Sra. Marina", "zona": "zona_norte"}'::jsonb),
  ('empresa', 'arborivida', '{"nome": "ArboriVida Maringá", "telefone": "5544999990052", "contato": "Sr. Eduardo", "zona": "zona_sul"}'::jsonb)
ON CONFLICT (chave) DO NOTHING;

-- Habilitar Realtime
ALTER PUBLICATION supabase_realtime ADD TABLE arborizacao;
