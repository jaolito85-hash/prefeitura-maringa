-- ============================================================
-- NODE DATA MARINGÁ — Migration 005b: Dados Demo Recompensas
-- 4 cenários que contam a história do fluxo completo
-- ============================================================

-- 1. PAGA — Carlos denunciou pichação, validada e paga com sucesso
INSERT INTO denuncias (id, protocolo, telefone, nome, categoria, mensagem, bairro, endereco, latitude, longitude, cidadania_ativa, status, valor_recompensa, midia_urls, created_at)
VALUES (
  'a1111111-1111-1111-1111-111111111111',
  'MGA-2026-00020', '44988010001', 'Carlos Mendes', 'pichacao',
  'Picharam a parede da escola municipal com tinta preta, foto em anexo',
  'Zona 7', 'Rua Duque de Caxias, 400, Zona 7',
  -23.4160, -51.9290, true, 'recompensa_paga', 100.00,
  ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+ESCOLA'],
  now() - interval '5 days'
);

INSERT INTO recompensas (denuncia_id, protocolo, status, valor, cpf_encrypted, chave_pix_encrypted, tipo_chave_pix, validado_por, validado_em, pago_por, pago_em, numero_empenho, dotacao_orcamentaria, created_at)
VALUES (
  'a1111111-1111-1111-1111-111111111111',
  'MGA-2026-00020', 'paga', 100.00,
  'ENC_AES256_demo_cpf_carlos', 'ENC_AES256_demo_pix_carlos', 'cpf',
  'Op. Silva', now() - interval '3 days',
  'Fin. Santos', now() - interval '1 day',
  'EMP-2026-00412', 'DOT-15.452.0045.2.048',
  now() - interval '5 days'
);

-- 2. AGUARDANDO PAGAMENTO — Ana Paula denunciou lixo, validada, falta pagar
INSERT INTO denuncias (id, protocolo, telefone, nome, categoria, mensagem, bairro, endereco, latitude, longitude, cidadania_ativa, status, valor_recompensa, midia_urls, created_at)
VALUES (
  'b2222222-2222-2222-2222-222222222222',
  'MGA-2026-00022', '44988010003', 'Ana Paula Costa', 'lixo',
  'Jogaram entulho e lixo no terreno baldio ao lado do condomínio, tem foto',
  'Nova Esperança', 'Rua das Palmeiras, 800, Nova Esperança',
  -23.4105, -51.9160, true, 'procedente', 80.00,
  ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=LIXO+TERRENO'],
  now() - interval '3 days'
);

INSERT INTO recompensas (denuncia_id, protocolo, status, valor, cpf_encrypted, chave_pix_encrypted, tipo_chave_pix, validado_por, validado_em, created_at)
VALUES (
  'b2222222-2222-2222-2222-222222222222',
  'MGA-2026-00022', 'aguardando_pagamento', 80.00,
  'ENC_AES256_demo_cpf_ana', 'ENC_AES256_demo_pix_ana', 'email',
  'Op. Silva', now() - interval '1 day',
  now() - interval '3 days'
);

-- 3. PENDENTE VALIDAÇÃO — Roberto denunciou vandalismo, em análise
INSERT INTO denuncias (id, protocolo, telefone, nome, categoria, mensagem, bairro, endereco, latitude, longitude, cidadania_ativa, status, valor_recompensa, midia_urls, created_at)
VALUES (
  'c3333333-3333-3333-3333-333333333333',
  'MGA-2026-00023', '44988010004', 'Roberto Silva', 'vandalismo',
  'Vandalizaram os bancos da praça e quebraram o bebedouro público',
  'Centro', 'Praça da República, Centro',
  -23.4200, -51.9340, true, 'em_analise', 150.00,
  ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=VANDALISMO+PRACA'],
  now() - interval '1 day'
);

INSERT INTO recompensas (denuncia_id, protocolo, status, valor, cpf_encrypted, chave_pix_encrypted, tipo_chave_pix, created_at)
VALUES (
  'c3333333-3333-3333-3333-333333333333',
  'MGA-2026-00023', 'pendente_validacao', 150.00,
  'ENC_AES256_demo_cpf_roberto', 'ENC_AES256_demo_pix_roberto', 'telefone',
  now() - interval '1 day'
);

-- 4. REJEITADA — Fernanda, evidência insuficiente
INSERT INTO denuncias (id, protocolo, telefone, nome, categoria, mensagem, bairro, endereco, latitude, longitude, cidadania_ativa, status, midia_urls, created_at)
VALUES (
  'd4444444-4444-4444-4444-444444444444',
  'MGA-2026-00025', '44988010006', 'Fernanda Lima', 'depredacao',
  'Quebraram o ponto de ônibus da Av Colombo, sem cobertura há 3 dias',
  'Zona 7', 'Av. Colombo, 4200, Zona 7',
  -23.4150, -51.9275, true, 'improcedente',
  ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PONTO+ONIBUS'],
  now() - interval '4 days'
);

INSERT INTO recompensas (denuncia_id, protocolo, status, valor, cpf_encrypted, chave_pix_encrypted, tipo_chave_pix, validado_por, validado_em, motivo_rejeicao, created_at)
VALUES (
  'd4444444-4444-4444-4444-444444444444',
  'MGA-2026-00025', 'rejeitada', 150.00,
  'ENC_AES256_demo_cpf_fernanda', 'ENC_AES256_demo_pix_fernanda', 'aleatoria',
  'Op. Silva', now() - interval '2 days',
  'Evidência fotográfica insuficiente — imagem não mostra o dano relatado. Solicitado novo envio, sem resposta.',
  now() - interval '4 days'
);
