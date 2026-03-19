-- ============================================================
-- NODE DATA MARINGÁ — Migration 002: Ativar Realtime
-- Isso faz o dashboard atualizar AUTOMATICAMENTE quando
-- um novo dado chega no banco. É a "magia" do tempo real!
-- ============================================================

ALTER PUBLICATION supabase_realtime ADD TABLE denuncias;
ALTER PUBLICATION supabase_realtime ADD TABLE sos_alertas;
ALTER PUBLICATION supabase_realtime ADD TABLE ocorrencias;
ALTER PUBLICATION supabase_realtime ADD TABLE ocorrencias_relatos;
