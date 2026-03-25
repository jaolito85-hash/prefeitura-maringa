-- ============================================================
-- NODE DATA MARINGÁ — Migration 013: Sincronizar protocolo_seq
-- Garante que a sequence esteja sempre à frente do maior
-- protocolo existente (evita conflito 23505 com dados de seed)
-- ============================================================

SELECT setval(
  'protocolo_seq',
  GREATEST(
    (SELECT COALESCE(MAX(CAST(SUBSTRING(protocolo FROM '[0-9]+$') AS INTEGER)), 0) FROM denuncias WHERE protocolo ~ '^MGA-\d{4}-\d+$'),
    (SELECT last_value FROM protocolo_seq)
  ) + 1,
  false
);
