-- ============================================================
-- NODE DATA MARINGÁ — Migration 022: Tabelas de rastreamento SOS
-- emergencia_sessoes: vincula token ao alerta
-- emergencia_pontos: pontos GPS contínuos da vítima
-- ============================================================

CREATE TABLE IF NOT EXISTS emergencia_sessoes (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  token TEXT NOT NULL UNIQUE,
  alerta_id UUID REFERENCES sos_alertas(id),
  telefone TEXT NOT NULL,
  nome TEXT,
  status TEXT DEFAULT 'ativa',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_emerg_sessoes_token ON emergencia_sessoes(token);
CREATE INDEX IF NOT EXISTS idx_emerg_sessoes_status ON emergencia_sessoes(status);

CREATE TABLE IF NOT EXISTS emergencia_pontos (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  sessao_id UUID REFERENCES emergencia_sessoes(id),
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  precisao_metros DOUBLE PRECISION,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_emerg_pontos_sessao ON emergencia_pontos(sessao_id);
CREATE INDEX IF NOT EXISTS idx_emerg_pontos_created ON emergencia_pontos(created_at DESC);

-- Realtime + RLS
ALTER PUBLICATION supabase_realtime ADD TABLE emergencia_pontos;
ALTER PUBLICATION supabase_realtime ADD TABLE emergencia_sessoes;

ALTER TABLE emergencia_sessoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE emergencia_pontos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_emergencia_sessoes" ON emergencia_sessoes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_emergencia_pontos" ON emergencia_pontos FOR ALL USING (true) WITH CHECK (true);
