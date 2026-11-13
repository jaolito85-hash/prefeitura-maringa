-- ============================================================
-- NODE DATA MARINGÁ · Migration 029: cadastro geográfico de câmeras
--
-- Objetivo: quando uma mulher dispara o SOS, o painel mostra as câmeras
-- AUTORIZADAS mais próximas do último ponto GPS dela, ao vivo.
--
-- Regra de ouro: só entra nesta tabela câmera própria do município, de
-- convênio (termo de cooperação) ou de parceiro que aderiu formalmente.
-- O campo `convenio_ref` registra o instrumento jurídico que autoriza.
--
-- `url_stream` é a FONTE interna (ex.: rtsp://...) que só o servidor de
-- mídia (MediaMTX) lê. NUNCA é devolvida ao navegador: a API devolve só
-- `stream_path`, o nome do caminho no MediaMTX. Em produção, guardar
-- `url_stream` cifrada (AES-256-GCM, app/services/crypto.py), porque ela
-- costuma carregar usuário e senha do equipamento.
--
-- As 6 câmeras do seed são de DEMONSTRAÇÃO: não existem na rua. O vídeo
-- delas é um sinal de teste sintético gerado pelo próprio MediaMTX
-- (ffmpeg lavfi), ver infra/mediamtx/mediamtx.yml.
--
-- IDEMPOTENTE. Não destrói nada.
-- ============================================================

CREATE TABLE IF NOT EXISTS cameras (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome               TEXT NOT NULL,
  descricao          TEXT,
  lat                DOUBLE PRECISION NOT NULL CHECK (lat BETWEEN -90 AND 90),
  lng                DOUBLE PRECISION NOT NULL CHECK (lng BETWEEN -180 AND 180),
  -- Para onde a câmera aponta (azimute, 0 = norte, 90 = leste). NULL = desconhecido/PTZ.
  direcao_graus      SMALLINT CHECK (direcao_graus BETWEEN 0 AND 359),
  -- Abertura horizontal da lente (ex.: 90). NULL = desconhecido.
  campo_visao_graus  SMALLINT CHECK (campo_visao_graus BETWEEN 1 AND 360),
  -- Distância útil para reconhecer uma pessoa (metros).
  alcance_m          SMALLINT DEFAULT 60,
  tipo               TEXT NOT NULL DEFAULT 'fixa'
                     CHECK (tipo IN ('fixa', 'ptz', 'lpr', 'transito', 'parceira', 'demo')),
  url_stream         TEXT,               -- fonte interna (RTSP/ONVIF). NUNCA expor.
  stream_path        TEXT UNIQUE,        -- caminho público no MediaMTX (ex.: cam-demo-01)
  orgao_responsavel  TEXT NOT NULL,      -- quem opera: GM, SEMOB, PM-PR, parceiro X...
  convenio_ref       TEXT,               -- nº do termo/convênio/adesão que autoriza o uso
  ativo              BOOLEAN NOT NULL DEFAULT true,
  demo               BOOLEAN NOT NULL DEFAULT false,
  created_at         TIMESTAMPTZ DEFAULT now(),
  updated_at         TIMESTAMPTZ DEFAULT now()
);

-- Busca por raio: a API faz um pré-filtro por "caixa" (lat/lng entre limites)
-- e calcula a distância exata (haversine) em Python. Com milhares de câmeras
-- isso é suficiente; acima disso, migrar para PostGIS (geography + GiST +
-- ST_DWithin), ver docs/PESQUISA-CAMERAS-SOS-MULHER.md.
CREATE INDEX IF NOT EXISTS idx_cameras_lat_lng ON cameras (lat, lng) WHERE ativo;
CREATE INDEX IF NOT EXISTS idx_cameras_orgao  ON cameras (orgao_responsavel);

-- Só o backend (service_role) lê. Navegador nunca consulta a tabela direto,
-- justamente para não vazar url_stream.
ALTER TABLE cameras ENABLE ROW LEVEL SECURITY;
GRANT ALL ON cameras TO service_role;
REVOKE ALL ON cameras FROM anon, authenticated;

-- Índice para a trilha de auditoria "quem assistiu qual câmera em qual SOS"
-- (registros gravados em audit_log com tabela = 'cameras').
CREATE INDEX IF NOT EXISTS idx_audit_tabela_registro ON audit_log (tabela, registro_id, created_at DESC);

-- ── Seed de DEMONSTRAÇÃO ────────────────────────────────────
-- Posicionadas ao longo das trilhas GPS demo da migration 028
-- (alertas SOS do seed 011). IDs fixos para o seed ser idempotente e
-- para coincidir com o catálogo de fallback do backend (app/api/cameras.py).
INSERT INTO cameras (id, nome, descricao, lat, lng, direcao_graus, campo_visao_graus, alcance_m,
                     tipo, url_stream, stream_path, orgao_responsavel, convenio_ref, ativo, demo)
VALUES
  ('ca000000-0000-4000-a000-000000000001', 'DEMO 01 · Jd. Alvorada (sul)',
   'Câmera fictícia de demonstração. Vídeo de rua de banco público (Wikimedia Commons), em loop.',
   -23.44345, -51.92110, 35, 90, 80, 'demo', 'arquivo://rua1.mp4', 'cam-demo-01',
   'Demonstração Node Data', 'DEMO (sem convênio, câmera inexistente)', true, true),
  ('ca000000-0000-4000-a000-000000000002', 'DEMO 02 · Jd. Alvorada (meio da quadra)',
   'Câmera fictícia de demonstração. Vídeo de rua de banco público (Wikimedia Commons), em loop.',
   -23.44255, -51.92025, 200, 90, 80, 'demo', 'arquivo://rua4.mp4', 'cam-demo-02',
   'Demonstração Node Data', 'DEMO (sem convênio, câmera inexistente)', true, true),
  ('ca000000-0000-4000-a000-000000000003', 'DEMO 03 · Jd. Alvorada (norte)',
   'Câmera fictícia de demonstração. Vídeo de rua de banco público (Wikimedia Commons), em loop.',
   -23.44150, -51.91960, 210, 100, 80, 'demo', 'arquivo://rua3.mp4', 'cam-demo-03',
   'Demonstração Node Data', 'DEMO (sem convênio, câmera inexistente)', true, true),
  ('ca000000-0000-4000-a000-000000000004', 'DEMO 04 · Vila Morangueira (sul)',
   'Câmera fictícia de demonstração. Vídeo de rua de banco público (Wikimedia Commons), em loop.',
   -23.40690, -51.93290, 30, 90, 80, 'demo', 'arquivo://rua4.mp4', 'cam-demo-04',
   'Demonstração Node Data', 'DEMO (sem convênio, câmera inexistente)', true, true),
  ('ca000000-0000-4000-a000-000000000005', 'DEMO 05 · Vila Morangueira (esquina)',
   'Câmera fictícia de demonstração. Vídeo de rua de banco público (Wikimedia Commons), em loop.',
   -23.40520, -51.93150, 220, 120, 80, 'demo', 'arquivo://rua1.mp4', 'cam-demo-05',
   'Demonstração Node Data', 'DEMO (sem convênio, câmera inexistente)', true, true),
  ('ca000000-0000-4000-a000-000000000006', 'DEMO 06 · Zona 7 (PTZ)',
   'Câmera fictícia de demonstração (PTZ). Vídeo de rua de banco público (Wikimedia Commons), em loop.',
   -23.43330, -51.92370, NULL, NULL, 120, 'demo', 'arquivo://rua3.mp4', 'cam-demo-06',
   'Demonstração Node Data', 'DEMO (sem convênio, câmera inexistente)', true, true)
ON CONFLICT (id) DO NOTHING;

NOTIFY pgrst, 'reload schema';
