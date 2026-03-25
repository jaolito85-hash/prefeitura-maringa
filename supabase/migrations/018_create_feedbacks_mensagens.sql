-- 018: Tabela de mensagens do chat Feedbacks (cidadão + operador + bot)
CREATE TABLE IF NOT EXISTS feedbacks_mensagens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  feedback_id UUID NOT NULL REFERENCES feedbacks(id),
  telefone TEXT NOT NULL,
  nome TEXT,
  mensagem TEXT,
  remetente TEXT NOT NULL DEFAULT 'cidadao',
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fbk_msgs_feedback ON feedbacks_mensagens(feedback_id);
ALTER PUBLICATION supabase_realtime ADD TABLE feedbacks_mensagens;
