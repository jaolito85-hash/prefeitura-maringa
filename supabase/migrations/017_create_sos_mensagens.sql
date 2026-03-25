-- 017: Tabela de mensagens do chat SOS (vítima + operador)
CREATE TABLE IF NOT EXISTS sos_mensagens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  alerta_id UUID NOT NULL REFERENCES sos_alertas(id),
  telefone TEXT NOT NULL,
  nome TEXT,
  mensagem TEXT,
  remetente TEXT NOT NULL DEFAULT 'cidadao',
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sos_mensagens_alerta ON sos_mensagens(alerta_id);
ALTER PUBLICATION supabase_realtime ADD TABLE sos_mensagens;
