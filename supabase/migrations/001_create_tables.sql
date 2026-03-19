-- ============================================================
-- NODE DATA MARINGÁ — Migration 001: Criar Tabelas
-- Execute no Supabase: SQL Editor > New Query > Cole e Execute
-- ============================================================

-- Sequência para gerar protocolos MGA-2026-XXXXX
CREATE SEQUENCE IF NOT EXISTS protocolo_seq START 1;

-- ============================================================
-- TABELA: denuncias
-- Canal 1 (Clara) — Programa Cidadania Ativa
-- ============================================================
CREATE TABLE IF NOT EXISTS denuncias (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  protocolo TEXT NOT NULL UNIQUE,
  telefone TEXT NOT NULL,
  nome TEXT,
  cpf_encrypted TEXT,                      -- AES-256. NUNCA salvar CPF em plaintext!
  dados_bancarios_encrypted TEXT,          -- AES-256. NUNCA salvar em plaintext!
  categoria TEXT NOT NULL,                 -- pichacao | trafico | lixo | vandalismo | depredacao
  mensagem TEXT NOT NULL,
  midia_urls TEXT[] DEFAULT '{}',          -- Array de URLs de fotos/videos
  bairro TEXT,
  endereco TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  cidadania_ativa BOOLEAN DEFAULT false,
  status TEXT DEFAULT 'novo',              -- novo | em_analise | encaminhado | procedente | improcedente | recompensa_paga
  valor_recompensa DECIMAL(10,2),
  operador TEXT,
  notas TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- TABELA: sos_cadastros
-- Canal 2 (SOS Mulher) — Cadastro prévio de mulheres
-- ============================================================
CREATE TABLE IF NOT EXISTS sos_cadastros (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  telefone TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL,
  endereco TEXT,
  referencia TEXT,
  agressor TEXT,
  contato_confianca_nome TEXT,
  contato_confianca_telefone TEXT,
  foto_url TEXT,
  ativo BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- TABELA: sos_alertas
-- Canal 2 (SOS Mulher) — Alertas de emergência disparados
-- ============================================================
CREATE TABLE IF NOT EXISTS sos_alertas (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  cadastro_id UUID REFERENCES sos_cadastros(id),
  telefone TEXT NOT NULL,
  codigo_usado TEXT NOT NULL,
  status TEXT DEFAULT 'active',            -- active | attending | resolved
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  localizacao_realtime BOOLEAN DEFAULT false,
  atendido_por TEXT,
  notas TEXT,
  resolvido_em TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- TABELA: ocorrencias
-- Canal 3 (Clara Emergência) — Incidentes agrupados
-- ============================================================
CREATE TABLE IF NOT EXISTS ocorrencias (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  protocolo TEXT NOT NULL UNIQUE,
  categoria TEXT NOT NULL,                 -- queda_arvore | enchente | buraco | poste | incendio | vendaval | acidente | deslizamento
  severidade TEXT DEFAULT 'baixa',         -- baixa | media | alta | critica
  status TEXT DEFAULT 'aberto',            -- aberto | equipe_caminho | em_atendimento | resolvido
  titulo TEXT,
  endereco TEXT NOT NULL,
  endereco_normalizado TEXT NOT NULL,      -- lowercase sem acentos — usado para agrupamento
  bairro TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  total_relatos INTEGER DEFAULT 1,
  equipe TEXT,
  operador TEXT,
  notas TEXT,
  resolvido_em TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- TABELA: ocorrencias_relatos
-- Cada mensagem de cidadão vinculada a uma ocorrência
-- ============================================================
CREATE TABLE IF NOT EXISTS ocorrencias_relatos (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  ocorrencia_id UUID NOT NULL REFERENCES ocorrencias(id),
  telefone TEXT NOT NULL,
  nome TEXT,
  mensagem TEXT,
  midia_urls TEXT[] DEFAULT '{}',
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- TABELA: audit_log
-- Auditoria de TODAS as ações sensíveis (exigência LGPD)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  tabela TEXT NOT NULL,
  registro_id UUID NOT NULL,
  acao TEXT NOT NULL,                      -- create | update | delete | view_sensitive
  operador TEXT,
  dados_antes JSONB,
  dados_depois JSONB,
  ip TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- ÍNDICES — Aceleram as buscas no banco
-- ============================================================

-- Denúncias
CREATE INDEX IF NOT EXISTS idx_denuncias_status ON denuncias(status);
CREATE INDEX IF NOT EXISTS idx_denuncias_categoria ON denuncias(categoria);
CREATE INDEX IF NOT EXISTS idx_denuncias_bairro ON denuncias(bairro);
CREATE INDEX IF NOT EXISTS idx_denuncias_created ON denuncias(created_at DESC);

-- SOS Cadastros
CREATE INDEX IF NOT EXISTS idx_sos_cadastros_telefone ON sos_cadastros(telefone);

-- SOS Alertas
CREATE INDEX IF NOT EXISTS idx_sos_alertas_status ON sos_alertas(status);
CREATE INDEX IF NOT EXISTS idx_sos_alertas_telefone ON sos_alertas(telefone);
CREATE INDEX IF NOT EXISTS idx_sos_alertas_created ON sos_alertas(created_at DESC);

-- Ocorrências
CREATE INDEX IF NOT EXISTS idx_ocorrencias_status ON ocorrencias(status);
CREATE INDEX IF NOT EXISTS idx_ocorrencias_categoria ON ocorrencias(categoria);
CREATE INDEX IF NOT EXISTS idx_ocorrencias_endereco_norm ON ocorrencias(endereco_normalizado);
CREATE INDEX IF NOT EXISTS idx_ocorrencias_created ON ocorrencias(created_at DESC);

-- Relatos
CREATE INDEX IF NOT EXISTS idx_relatos_ocorrencia ON ocorrencias_relatos(ocorrencia_id);

-- Audit
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
