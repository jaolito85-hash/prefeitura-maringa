-- ============================================================
-- NODE DATA MARINGÁ — Migration 003: Dados de Demo
-- Dados realistas de Maringá para a apresentação na Prefeitura
-- ============================================================

-- ============================================================
-- OCORRÊNCIAS (com coordenadas reais de Maringá)
-- ============================================================
INSERT INTO ocorrencias (protocolo, categoria, severidade, status, titulo, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos) VALUES
('MGA-2026-00001', 'queda_arvore', 'alta', 'aberto',       '🌳 Queda de árvore — Av. Brasil, Centro',         'Avenida Brasil, 1200, Centro',         'avenida brasil 1200 centro',         'Centro',          -23.4195, -51.9331, 7),
('MGA-2026-00002', 'enchente',     'critica', 'aberto',     '🌊 Alagamento — Rua das Margaridas, Zona 5',       'Rua das Margaridas, 450, Zona 5',      'rua das margaridas 450 zona 5',      'Zona 5',          -23.4312, -51.9450, 12),
('MGA-2026-00003', 'buraco',       'media', 'aberto',       '🕳️ Buraco — Av. Colombo, Zona 7',                'Avenida Colombo, 3800, Zona 7',        'avenida colombo 3800 zona 7',        'Zona 7',          -23.4156, -51.9280, 3),
('MGA-2026-00004', 'poste',        'baixa', 'equipe_caminho','💡 Poste caído — Rua Pioneiro, Jd. Alvorada',     'Rua Pioneiro, 88, Jardim Alvorada',    'rua pioneiro 88 jardim alvorada',    'Jardim Alvorada', -23.4420, -51.9200, 1),
('MGA-2026-00005', 'incendio',     'alta', 'em_atendimento','🔥 Incêndio — Rua Goiás, Zona 3',                 'Rua Goiás, 240, Zona 3',               'rua goias 240 zona 3',               'Zona 3',          -23.4280, -51.9380, 5),
('MGA-2026-00006', 'vendaval',     'media', 'aberto',       '🌪️ Vendaval — Av. Mauá, Nova Esperança',          'Avenida Mauá, 1500, Nova Esperança',   'avenida maua 1500 nova esperanca',   'Nova Esperança',  -23.4100, -51.9150, 4),
('MGA-2026-00007', 'queda_arvore', 'baixa', 'resolvido',    '🌳 Queda de árvore — Rua Mandacarú, Jd. Europa', 'Rua Mandacarú, 320, Jardim Europa',    'rua mandacaru 320 jardim europa',    'Jardim Europa',   -23.4350, -51.9500, 2),
('MGA-2026-00008', 'acidente',     'media', 'aberto',       '🚗 Acidente — Av. Cerro Azul, Zona 4',            'Avenida Cerro Azul, 500, Zona 4',      'avenida cerro azul 500 zona 4',      'Zona 4',          -23.4230, -51.9420, 3);

-- Relatos das ocorrências (para mostrar o agrupamento)
INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, mensagem, created_at)
SELECT o.id, '44999110001', 'Uma árvore enorme caiu na Av Brasil bloqueou a rua', now() - interval '2 hours'
FROM ocorrencias o WHERE o.protocolo = 'MGA-2026-00001';

INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, mensagem, created_at)
SELECT o.id, '44999110002', 'Árvore caiu e bateu num carro estacionado', now() - interval '1 hour 45 min'
FROM ocorrencias o WHERE o.protocolo = 'MGA-2026-00001';

INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, mensagem, created_at)
SELECT o.id, '44999110003', 'Tem uma árvore caída na Av Brasil sentido centro precisa de urgência', now() - interval '1 hour 30 min'
FROM ocorrencias o WHERE o.protocolo = 'MGA-2026-00001';

-- ============================================================
-- DENÚNCIAS (Programa Cidadania Ativa)
-- ============================================================
INSERT INTO denuncias (protocolo, telefone, nome, categoria, mensagem, bairro, endereco, latitude, longitude, cidadania_ativa, status, midia_urls) VALUES
('MGA-2026-00020', '44988010001', 'Carlos Mendes',    'pichacao',   'Picharam a parede da escola municipal com tinta preta, foto em anexo',       'Zona 7',          'Rua Duque de Caxias, 400, Zona 7',     -23.4160, -51.9290, true,  'em_analise',  ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FOTO+1']),
('MGA-2026-00021', '44988010002', NULL,               'trafico',    'Há um ponto de venda de drogas na esquina da rua desde as 22h todo dia',     'Jardim Alvorada', 'Rua Pioneiro c/ Rua Araça, Jd. Alvorada', -23.4425, -51.9195, false, 'novo',        ARRAY[]::TEXT[]),
('MGA-2026-00022', '44988010003', 'Ana Paula Costa',  'lixo',       'Jogaram entulho e lixo no terreno baldio ao lado do condomínio, tem foto',   'Nova Esperança',  'Rua das Palmeiras, 800, Nova Esperança', -23.4105, -51.9160, true,  'encaminhado', ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FOTO+2']),
('MGA-2026-00023', '44988010004', 'Roberto Silva',    'vandalismo', 'Vandalizaram os bancos da praça e quebraram o bebedouro público',            'Centro',          'Praça da República, Centro',             -23.4200, -51.9340, true,  'procedente',  ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FOTO+3']),
('MGA-2026-00024', '44988010005', NULL,               'pichacao',   'Pixaram o muro da UBS com símbolo de gangue, aconteceu na madrugada',       'Zona 3',          'Rua Goiás, 100, Zona 3',                -23.4285, -51.9375, false, 'novo',        ARRAY[]::TEXT[]),
('MGA-2026-00025', '44988010006', 'Fernanda Lima',    'depredacao', 'Quebraram o ponto de ônibus da Av Colombo, sem cobertura há 3 dias',         'Zona 7',          'Av. Colombo, 4200, Zona 7',             -23.4150, -51.9275, true,  'novo',        ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FOTO+4']);

-- ============================================================
-- SOS — Cadastro de mulheres
-- ============================================================
INSERT INTO sos_cadastros (telefone, nome, endereco, referencia, agressor, contato_confianca_nome, contato_confianca_telefone) VALUES
('44977050001', 'Maria Silva',    'Rua das Acácias, 120, Jardim Alvorada',   'Em frente ao mercadinho do João',       'João Carlos Silva',  'Mãe - Dona Cida',  '44966010001'),
('44977050002', 'Joana Ferreira', 'Av. Morangueira, 3400, ap 22, Zona 7',    'Prédio azul ao lado do banco',          'Pedro Ferreira',     'Irmã - Paula',     '44966010002'),
('44977050003', 'Lucia Santos',   'Rua Pioneiro, 55, Nova Esperança',         'Casa amarela com portão de ferro',      NULL,                 'Vizinha - Marta',  '44966010003');

-- ============================================================
-- SOS — Alerta ATIVO (para mostrar no demo!)
-- Este é o alerta que faz a tela virar vermelha
-- ============================================================
INSERT INTO sos_alertas (cadastro_id, telefone, codigo_usado, status, latitude, longitude, created_at)
SELECT
  c.id,
  '44977050001',
  '.',
  'active',
  -23.4420,
  -51.9200,
  now() - interval '3 minutes'
FROM sos_cadastros c WHERE c.telefone = '44977050001';
