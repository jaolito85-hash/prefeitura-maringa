-- ============================================================
-- NODE DATA MARINGÁ — Migration 005: Tabela Recompensas
-- Sistema de recompensa do Programa Cidadão Ativo
-- Decreto 291/2026 — Prefeitura de Maringá-PR
--
-- CONCEITO: "Identidade Protegida com Camadas"
-- → Camada OPERACIONAL (denuncias): vê fotos, vídeos, local — NÃO vê quem denunciou
-- → Camada FINANCEIRA (recompensas): vê CPF, PIX, valor — NÃO vê conteúdo da denúncia
-- → Conexão entre as duas: apenas via protocolo + audit_log
-- ============================================================

-- ============================================================
-- TABELA: recompensas
-- Ciclo de vida do pagamento, SEPARADA da denúncia
-- ============================================================
CREATE TABLE IF NOT EXISTS recompensas (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

  -- Vínculo com a denúncia (protocolo é a "ponte" entre as camadas)
  denuncia_id UUID NOT NULL REFERENCES denuncias(id),
  protocolo TEXT NOT NULL,                       -- mesmo MGA-2026-XXXXX da denúncia

  -- Status do pagamento (fluxo completo)
  -- pendente_validacao → validada → aguardando_pagamento → paga
  --                    → rejeitada (pode acontecer em qualquer etapa)
  status TEXT DEFAULT 'pendente_validacao'
    CHECK (status IN (
      'pendente_validacao',      -- denúncia ainda sendo analisada pelo operacional
      'validada',                -- operacional marcou como procedente
      'aguardando_pagamento',    -- financeiro já tem os dados, precisa pagar
      'paga',                    -- PIX realizado, comprovante anexado
      'rejeitada'                -- denúncia improcedente ou fraude detectada
    )),

  -- Valor da recompensa (definido por categoria ou manualmente)
  valor DECIMAL(10,2),

  -- Dados do beneficiário — CRIPTOGRAFADOS (AES-256)
  -- Esses campos SÓ são acessados pela camada financeira
  -- Cada acesso é registrado no audit_log (LGPD)
  cpf_encrypted TEXT,                            -- CPF do cidadão (AES-256)
  chave_pix_encrypted TEXT,                      -- Chave PIX: CPF, email, telefone ou aleatória (AES-256)
  tipo_chave_pix TEXT                            -- 'cpf' | 'email' | 'telefone' | 'aleatoria'
    CHECK (tipo_chave_pix IN ('cpf', 'email', 'telefone', 'aleatoria')),

  -- Comprovantes e documentos
  comprovante_pix_url TEXT,                      -- URL do comprovante de pagamento (upload)
  termo_url TEXT,                                -- URL do PDF do Termo de Recompensa gerado

  -- Rastreabilidade (quem fez o quê e quando)
  validado_por TEXT,                             -- operador que validou a denúncia
  validado_em TIMESTAMPTZ,                       -- quando foi validada
  pago_por TEXT,                                 -- operador financeiro que efetuou o pagamento
  pago_em TIMESTAMPTZ,                           -- quando o PIX foi feito
  motivo_rejeicao TEXT,                          -- se rejeitada, por quê

  -- Referência fiscal (prestação de contas)
  numero_empenho TEXT,                           -- número do empenho orçamentário (preenchido pelo financeiro)
  dotacao_orcamentaria TEXT,                     -- dotação orçamentária do programa

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- TABELA: recompensas_config
-- Configuração dos valores por categoria (editável pela prefeitura)
-- Ex: pichação = R$100, tráfico = R$300, vandalismo = R$150
-- ============================================================
CREATE TABLE IF NOT EXISTS recompensas_config (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  categoria TEXT NOT NULL UNIQUE,                -- pichacao | trafico | vandalismo | depredacao | lixo
  valor_padrao DECIMAL(10,2) NOT NULL,           -- valor da recompensa pra essa categoria
  ativo BOOLEAN DEFAULT true,                    -- categoria elegível ou não
  descricao TEXT,                                -- descrição amigável
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- ÍNDICES — Aceleram as consultas do painel financeiro
-- ============================================================

-- Busca por status (a consulta mais comum do financeiro)
CREATE INDEX IF NOT EXISTS idx_recompensas_status ON recompensas(status);

-- Busca por protocolo (a "ponte" entre operacional e financeiro)
CREATE INDEX IF NOT EXISTS idx_recompensas_protocolo ON recompensas(protocolo);

-- Busca por denúncia (pra saber se já tem recompensa vinculada)
CREATE INDEX IF NOT EXISTS idx_recompensas_denuncia ON recompensas(denuncia_id);

-- Ordenação por data (relatórios mensais)
CREATE INDEX IF NOT EXISTS idx_recompensas_created ON recompensas(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recompensas_pago_em ON recompensas(pago_em DESC);

-- ============================================================
-- VALORES PADRÃO por categoria
-- (a prefeitura pode alterar depois pelo painel)
-- ============================================================
INSERT INTO recompensas_config (categoria, valor_padrao, ativo, descricao) VALUES
  ('pichacao',    100.00, true,  'Pichação em patrimônio público ou privado'),
  ('trafico',     300.00, true,  'Ponto de venda de drogas'),
  ('vandalismo',  150.00, true,  'Vandalismo em equipamentos públicos'),
  ('depredacao',  150.00, true,  'Depredação de patrimônio público'),
  ('lixo',         80.00, true,  'Descarte irregular de lixo ou entulho')
ON CONFLICT (categoria) DO NOTHING;

-- ============================================================
-- ATIVAR REALTIME na tabela recompensas
-- (pra atualizar o dashboard financeiro em tempo real)
-- ============================================================
ALTER PUBLICATION supabase_realtime ADD TABLE recompensas;
