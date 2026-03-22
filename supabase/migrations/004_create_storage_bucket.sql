-- ============================================================
-- NODE DATA MARINGÁ — Migration 004: Bucket de Evidências
-- Execute no Supabase: SQL Editor > New Query > Cole e Execute
-- ============================================================

-- Criar bucket público para fotos/vídeos de denúncias e ocorrências
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'evidencias',
  'evidencias',
  true,
  16777216,  -- 16MB max por arquivo
  ARRAY['image/jpeg', 'image/png', 'image/webp', 'video/mp4', 'video/3gpp', 'video/quicktime']
)
ON CONFLICT (id) DO NOTHING;

-- Política: backend (service_key) pode fazer upload
CREATE POLICY "Service key upload" ON storage.objects
  FOR INSERT TO service_role
  WITH CHECK (bucket_id = 'evidencias');

-- Política: qualquer um pode ler (público)
CREATE POLICY "Public read evidencias" ON storage.objects
  FOR SELECT TO anon, authenticated
  USING (bucket_id = 'evidencias');
