-- ============================================================
-- NODE DATA MARINGÁ — Migration 028: trilha GPS dos alertas SOS demo
-- Os alertas SOS do seed não tinham sessão de rastreamento, então o
-- painel mostrava "Sessão GPS não encontrada". Cria token + sessão +
-- 8 pontos (últimos ~14 min, deslocamento a pé) para cada alerta
-- active/attending do seed (telefones 5544977050xxx). IDEMPOTENTE.
-- ============================================================

-- 1) token para alertas demo que não têm
UPDATE sos_alertas
   SET token_rastreamento = 'demo' || substr(md5(id::text), 1, 6)
 WHERE token_rastreamento IS NULL
   AND telefone LIKE '5544977050%'
   AND status IN ('active', 'attending');

-- 2) sessão GPS por alerta
INSERT INTO emergencia_sessoes (token, alerta_id, telefone, nome, status)
SELECT a.token_rastreamento, a.id, a.telefone, COALESCE(c.nome, 'Não identificada'), 'ativa'
  FROM sos_alertas a
  LEFT JOIN sos_cadastros c ON c.id = a.cadastro_id
 WHERE a.telefone LIKE '5544977050%'
   AND a.status IN ('active', 'attending')
   AND a.token_rastreamento IS NOT NULL
ON CONFLICT (token) DO NOTHING;

-- 3) 8 pontos por sessão que ainda não tem pontos
INSERT INTO emergencia_pontos (sessao_id, latitude, longitude, precisao_metros, created_at)
SELECT s.id,
       COALESCE(a.latitude,  -23.4205) + (g.n - 8) * 0.00018 + (CASE WHEN g.n % 2 = 0 THEN 0.00004 ELSE -0.00003 END),
       COALESCE(a.longitude, -51.9333) + (g.n - 8) * 0.00012,
       8 + (g.n % 3) * 4,
       now() - ((8 - g.n) * interval '2 minutes')
  FROM emergencia_sessoes s
  JOIN sos_alertas a ON a.id = s.alerta_id
 CROSS JOIN generate_series(1, 8) AS g(n)
 WHERE s.telefone LIKE '5544977050%'
   AND NOT EXISTS (SELECT 1 FROM emergencia_pontos p WHERE p.sessao_id = s.id);
