-- ============================================================
-- NODE DATA MARINGÁ — Migration 010: Seed Completo Demo
-- Dados realistas de Maringá para reunião com a Prefeitura
-- 8 ocorrências (36 relatos), 6 denúncias (4 com recompensa),
-- 3 cadastros SOS, 1 alerta ativo
-- ============================================================
-- NOTA: Este arquivo SUBSTITUI os seeds das migrations 003 e 005b.
-- Pode ser re-executado quantas vezes quiser (limpa e recria).

-- Limpar dados antigos de ocorrências
DELETE FROM ocorrencias_relatos;
DELETE FROM ocorrencias;

-- Resetar sequência de protocolo (começa em 101)
SELECT setval('protocolo_seq', 100, true);

-- ============================================================
-- OCORRÊNCIA 1: Árvore caída — Av. Brasil, Centro
-- 8 relatos, severidade ALTA, em_atendimento
-- ============================================================
INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, equipe, created_at)
VALUES (
  '0c110001-0001-4000-a000-000000000001',
  'MGA-2026-00101', 'queda_arvore', 'alta', 'em_atendimento',
  'Queda de árvore grande na Avenida Brasil',
  'Árvore de grande porte caiu sobre a via, bloqueando duas faixas. Trânsito desviado pela Rua Santos Dumont.',
  'Avenida Brasil, 1200 - Centro, Maringá - PR',
  'avenida brasil 1200 centro maringa pr',
  'Centro',
  -23.4195, -51.9331, 8,
  'Equipe Defesa Civil #02',
  now() - interval '2 hours 30 min'
);

INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, nome, mensagem, latitude, longitude, created_at) VALUES
('0c110001-0001-4000-a000-000000000001', '44999110001', 'Marcos Oliveira', 'Uma arvore enorme caiu na av brasil ta bloqueando a rua toda socorro', -23.4195, -51.9331, now() - interval '2 hours 30 min'),
('0c110001-0001-4000-a000-000000000001', '44999110002', 'Patricia Almeida', 'Gente a arvore caiu na brasil perto do bradesco quase pegou um carro 😱', -23.4196, -51.9329, now() - interval '2 hours 15 min'),
('0c110001-0001-4000-a000-000000000001', '44999110003', NULL, 'arvore caida na avenida brasil centro impossivel passar', -23.4194, -51.9333, now() - interval '2 hours'),
('0c110001-0001-4000-a000-000000000001', '44999110004', 'Carlos Eduardo', 'A árvore caiu na fiação elétrica tbm, tá tudo escuro aqui no quarteirão', -23.4197, -51.9330, now() - interval '1 hour 50 min'),
('0c110001-0001-4000-a000-000000000001', '44999110005', 'Maria José', 'to presa no transito por causa da arvore q caiu na av brasil alguem sabe se ja chamaram a prefeitura?', -23.4193, -51.9335, now() - interval '1 hour 30 min'),
('0c110001-0001-4000-a000-000000000001', '44999110006', NULL, 'Arvore caida av brasil sentido catedral bloquenado tudo', -23.4198, -51.9328, now() - interval '1 hour 15 min'),
('0c110001-0001-4000-a000-000000000001', '44999110007', 'Roberta Santos', 'Meu carro ficou preso atras da arvore na brasil, nao consigo sair da vaga 😡', -23.4196, -51.9332, now() - interval '55 min'),
('0c110001-0001-4000-a000-000000000001', '44999110008', 'Fernando Dias', 'Ja tem 2h q essa arvore caiu na av brasil e ninguem apareceu. ta perigoso pq tem fio de alta tensao no chao', -23.4194, -51.9330, now() - interval '40 min');

-- ============================================================
-- OCORRÊNCIA 2: Alagamento — Rua das Margaridas, Zona 5
-- 12 relatos, severidade CRÍTICA, aberto
-- ============================================================
INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at)
VALUES (
  '0c110001-0002-4000-a000-000000000002',
  'MGA-2026-00102', 'enchente_alagamento', 'critica', 'aberto',
  'Alagamento severo na Rua das Margaridas',
  'Rua completamente alagada, água invadindo casas e comércios. Moradores ilhados.',
  'Rua das Margaridas, 450 - Zona 5, Maringá - PR',
  'rua das margaridas 450 zona 5 maringa pr',
  'Zona 5',
  -23.4312, -51.9450, 12,
  now() - interval '3 hours'
);

INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, nome, mensagem, latitude, longitude, created_at) VALUES
('0c110001-0002-4000-a000-000000000002', '44999120001', 'Dona Cida', 'a agua ta entrando na minha casa gente pelo amor de deus alguem ajuda', -23.4312, -51.9450, now() - interval '3 hours'),
('0c110001-0002-4000-a000-000000000002', '44999120002', 'José Carlos', 'Rua das margaridas completamente alagada, agua na altura do joelho', -23.4313, -51.9448, now() - interval '2 hours 50 min'),
('0c110001-0002-4000-a000-000000000002', '44999120003', NULL, 'alagamento forte zona 5 rua das margaridas carro nao passa', -23.4310, -51.9452, now() - interval '2 hours 40 min'),
('0c110001-0002-4000-a000-000000000002', '44999120004', 'Luciana Ferreira', 'to com agua dentro de casa precisamos de ajuda urgente zona 5 margaridas', -23.4314, -51.9449, now() - interval '2 hours 30 min'),
('0c110001-0002-4000-a000-000000000002', '44999120005', 'Pedro Henrique', 'O bueiro entupiu e a rua inteira alagou. Ta entrando agua nos comercios', -23.4311, -51.9451, now() - interval '2 hours 20 min'),
('0c110001-0002-4000-a000-000000000002', '44999120006', 'Ana Beatriz', 'Minha vizinha idosa ta ilhada na casa dela rua das margaridas 380 precisa de resgate', -23.4315, -51.9447, now() - interval '2 hours 10 min'),
('0c110001-0002-4000-a000-000000000002', '44999120007', NULL, 'alagamento zona 5 agua subindo rapido', -23.4309, -51.9453, now() - interval '2 hours'),
('0c110001-0002-4000-a000-000000000002', '44999120008', 'Marcos Paulo', 'Tem criança presa numa casa aqui na rua das margaridas a agua ta quase 1 metro', -23.4316, -51.9446, now() - interval '1 hour 50 min'),
('0c110001-0002-4000-a000-000000000002', '44999120009', 'Sandra Melo', 'Perdi tudo dentro de casa 😭 a agua entrou e levou os moveis. Rua margaridas zona 5', -23.4313, -51.9450, now() - interval '1 hour 40 min'),
('0c110001-0002-4000-a000-000000000002', '44999120010', NULL, 'moro na margaridas 500 a agua ta baixando mas tem muito lixo e lama agr', -23.4310, -51.9454, now() - interval '1 hour 20 min'),
('0c110001-0002-4000-a000-000000000002', '44999120011', 'Ricardo Souza', 'Ja ligamos pro bombeiro e defesa civil mas ninguem apareceu. Margaridas zona 5 alagada', -23.4317, -51.9445, now() - interval '1 hour'),
('0c110001-0002-4000-a000-000000000002', '44999120012', 'Camila Rodrigues', 'A rua das margaridas virou um rio!! Tem gente pedindo socorro das janelas', -23.4308, -51.9455, now() - interval '45 min');

-- ============================================================
-- OCORRÊNCIA 3: Buraco — Av. Colombo, Zona 7
-- 3 relatos, severidade MÉDIA, aberto
-- ============================================================
INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at)
VALUES (
  '0c110001-0003-4000-a000-000000000003',
  'MGA-2026-00103', 'buraco_via', 'media', 'aberto',
  'Buraco grande na Av. Colombo próximo à UEM',
  'Buraco na pista no sentido centro, carro já caiu. Está sem sinalização.',
  'Avenida Colombo, 3800 - Zona 7, Maringá - PR',
  'avenida colombo 3800 zona 7 maringa pr',
  'Zona 7',
  -23.4156, -51.9280, 3,
  now() - interval '5 hours'
);

INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, nome, mensagem, latitude, longitude, created_at) VALUES
('0c110001-0003-4000-a000-000000000003', '44999130001', 'Thiago Martins', 'Tem um buraco enorme na colombo perto da uem, meu pneu estourou nele agora', -23.4156, -51.9280, now() - interval '5 hours'),
('0c110001-0003-4000-a000-000000000003', '44999130002', NULL, 'buraco perigoso na av colombo sentido centro perto do posto ipiranga zona 7', -23.4157, -51.9279, now() - interval '4 hours'),
('0c110001-0003-4000-a000-000000000003', '44999130003', 'Juliana Costa', 'Gente cuidado com o buracão na colombo!! Ja vi 3 carros baterem a roda nele hj', -23.4155, -51.9281, now() - interval '2 hours');

-- ============================================================
-- OCORRÊNCIA 4: Poste apagado — Rua Pioneiro, Jd. Alvorada
-- 1 relato, severidade BAIXA, aberto
-- ============================================================
INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at)
VALUES (
  '0c110001-0004-4000-a000-000000000004',
  'MGA-2026-00104', 'iluminacao_publica', 'baixa', 'aberto',
  'Poste apagado na Rua Pioneiro',
  'Três postes apagados deixando trecho escuro. Moradores relatam insegurança.',
  'Rua Pioneiro, 88 - Jardim Alvorada, Maringá - PR',
  'rua pioneiro 88 jardim alvorada maringa pr',
  'Jardim Alvorada',
  -23.4420, -51.9200, 1,
  now() - interval '8 hours'
);

INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, nome, mensagem, latitude, longitude, created_at) VALUES
('0c110001-0004-4000-a000-000000000004', '44999140001', 'Dona Maria', 'tem 3 postes apagados na rua pioneiro proximo ao numero 88 ta muito escuro e perigoso a noite', -23.4420, -51.9200, now() - interval '8 hours');

-- ============================================================
-- OCORRÊNCIA 5: Incêndio em terreno — Rua Goiás, Zona 3
-- 5 relatos, severidade ALTA, em_atendimento
-- ============================================================
INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, equipe, created_at)
VALUES (
  '0c110001-0005-4000-a000-000000000005',
  'MGA-2026-00105', 'incendio', 'alta', 'em_atendimento',
  'Incêndio em terreno baldio na Rua Goiás',
  'Fogo alto em terreno baldio com mato seco. Fumaça densa. Próximo a residências.',
  'Rua Goiás, 240 - Zona 3, Maringá - PR',
  'rua goias 240 zona 3 maringa pr',
  'Zona 3',
  -23.4280, -51.9380, 5,
  'Corpo de Bombeiros #07',
  now() - interval '1 hour 30 min'
);

INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, nome, mensagem, latitude, longitude, created_at) VALUES
('0c110001-0005-4000-a000-000000000005', '44999150001', 'Alberto Nunes', 'Ta pegando fogo num terreno na rua goias zona 3! Fogo alto demais chama o bombeiro', -23.4280, -51.9380, now() - interval '1 hour 30 min'),
('0c110001-0005-4000-a000-000000000005', '44999150002', NULL, 'incendio terreno baldio rua goias perto do numero 240 fumaca muito forte', -23.4281, -51.9378, now() - interval '1 hour 20 min'),
('0c110001-0005-4000-a000-000000000005', '44999150003', 'Renata Campos', 'o fogo do terreno ta chegando perto da minha casa rua goias 260 to com medo 😰', -23.4279, -51.9382, now() - interval '1 hour 10 min'),
('0c110001-0005-4000-a000-000000000005', '44999150004', 'Leandro Silva', 'Fumaça preta muito forte vindo do terreno da rua goiás. Meus filhos tão passando mal com a fumaça', -23.4282, -51.9377, now() - interval '1 hour'),
('0c110001-0005-4000-a000-000000000005', '44999150005', 'Dona Aparecida', 'ja chegou os bombeiros no incendio da goias mas ta dificil apagar o fogo ta muito seco', -23.4278, -51.9383, now() - interval '45 min');

-- ============================================================
-- OCORRÊNCIA 6: Vendaval — Av. Mauá, Nova Esperança
-- 4 relatos, severidade MÉDIA, aberto
-- ============================================================
INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at)
VALUES (
  '0c110001-0006-4000-a000-000000000006',
  'MGA-2026-00106', 'vendaval', 'media', 'aberto',
  'Danos de vendaval na Av. Mauá',
  'Vendaval arrancou telhas e derrubou placas de sinalização. Fios expostos na calçada.',
  'Avenida Mauá, 1500 - Nova Esperança, Maringá - PR',
  'avenida maua 1500 nova esperanca maringa pr',
  'Nova Esperança',
  -23.4100, -51.9150, 4,
  now() - interval '4 hours'
);

INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, nome, mensagem, latitude, longitude, created_at) VALUES
('0c110001-0006-4000-a000-000000000006', '44999160001', 'João Batista', 'O vento arrancou as telhas da minha casa na mauá 1500!! Telhado todo destruido', -23.4100, -51.9150, now() - interval '4 hours'),
('0c110001-0006-4000-a000-000000000006', '44999160002', 'Simone Oliveira', 'vendaval derrubou uma placa de transito na av maua nova esperança ta no meio da rua', -23.4101, -51.9148, now() - interval '3 hours 30 min'),
('0c110001-0006-4000-a000-000000000006', '44999160003', NULL, 'fio da copel caiu na calçada da maua depois do vendaval ta muito perigoso', -23.4099, -51.9152, now() - interval '3 hours'),
('0c110001-0006-4000-a000-000000000006', '44999160004', 'Rogério Lima', 'O vendaval destruiu a cobertura do ponto de ônibus da mauá e quebrou a vitrine da farmácia', -23.4102, -51.9147, now() - interval '2 hours 30 min');

-- ============================================================
-- OCORRÊNCIA 7: Acidente — Av. Cerro Azul, Zona 4
-- 2 relatos, severidade BAIXA, resolvido
-- ============================================================
INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, resolvido_em, created_at)
VALUES (
  '0c110001-0007-4000-a000-000000000007',
  'MGA-2026-00107', 'acidente', 'baixa', 'resolvido',
  'Acidente entre dois veículos na Av. Cerro Azul',
  'Colisão entre carro e moto. SAMU atendeu. Via liberada.',
  'Avenida Cerro Azul, 500 - Zona 4, Maringá - PR',
  'avenida cerro azul 500 zona 4 maringa pr',
  'Zona 4',
  -23.4230, -51.9420, 2,
  now() - interval '3 hours',
  now() - interval '6 hours'
);

INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, nome, mensagem, latitude, longitude, created_at) VALUES
('0c110001-0007-4000-a000-000000000007', '44999170001', 'Felipe Augusto', 'acabou de acontecer um acidente na cerro azul um carro bateu numa moto parece q o motoqueiro ta machucado', -23.4230, -51.9420, now() - interval '6 hours'),
('0c110001-0007-4000-a000-000000000007', '44999170002', NULL, 'acidente cerro azul zona 4 o samu ja ta aqui mas o transito ta parado', -23.4231, -51.9418, now() - interval '5 hours 45 min');

-- ============================================================
-- OCORRÊNCIA 8: Bueiro entupido — Rua Santos Dumont, Zona 2
-- 1 relato, severidade BAIXA, aberto
-- ============================================================
INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at)
VALUES (
  '0c110001-0008-4000-a000-000000000008',
  'MGA-2026-00108', 'drenagem', 'baixa', 'aberto',
  'Bueiro entupido na Rua Santos Dumont',
  'Bueiro transbordando com acúmulo de lixo. Mau cheiro forte.',
  'Rua Santos Dumont, 700 - Zona 2, Maringá - PR',
  'rua santos dumont 700 zona 2 maringa pr',
  'Zona 2',
  -23.4250, -51.9500, 1,
  now() - interval '6 hours'
);

INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, nome, mensagem, latitude, longitude, created_at) VALUES
('0c110001-0008-4000-a000-000000000008', '44999180001', 'Mariana Costa', 'o bueiro aqui na santos dumont 700 ta entupido e transbordando agua suja com um cheiro horrivel. tem muito lixo acumulado', -23.4250, -51.9500, now() - interval '6 hours');


-- ============================================================
-- DENÚNCIAS — Programa Cidadania Ativa (Decreto 291/2026)
-- Limpa e recria com IDs fixos para vincular recompensas
-- ============================================================
DELETE FROM recompensas;
DELETE FROM denuncias;

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
  'MGA-2026-00022', '44988010003', 'Ana Paula Costa', 'descarte_irregular',
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

-- 3. PENDENTE VALIDAÇÃO — Roberto denunciou depredação, em análise
INSERT INTO denuncias (id, protocolo, telefone, nome, categoria, mensagem, bairro, endereco, latitude, longitude, cidadania_ativa, status, valor_recompensa, midia_urls, created_at)
VALUES (
  'c3333333-3333-3333-3333-333333333333',
  'MGA-2026-00023', '44988010004', 'Roberto Silva', 'depredacao',
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
  'Evidência fotográfica insuficiente — imagem não mostra o dano relatado.',
  now() - interval '4 days'
);

-- 5. NOVA — denúncia anônima de tráfico (sem recompensa ainda)
INSERT INTO denuncias (protocolo, telefone, nome, categoria, mensagem, bairro, endereco, latitude, longitude, cidadania_ativa, status, midia_urls, created_at)
VALUES (
  'MGA-2026-00021', '44988010002', NULL, 'trafico_drogas',
  'Há um ponto de venda de drogas na esquina da rua desde as 22h todo dia. Vem carro preto e moto vermelha.',
  'Jardim Alvorada', 'Rua Pioneiro c/ Rua Araçá, Jd. Alvorada',
  -23.4425, -51.9195, false, 'novo',
  ARRAY[]::TEXT[],
  now() - interval '12 hours'
);

-- 6. EM ANÁLISE — pichação com foto
INSERT INTO denuncias (protocolo, telefone, nome, categoria, mensagem, bairro, endereco, latitude, longitude, cidadania_ativa, status, midia_urls, created_at)
VALUES (
  'MGA-2026-00024', '44988010005', 'Lucas Fernandes', 'pichacao',
  'Pixaram o muro da UBS com símbolo de gangue, aconteceu na madrugada. Mandei foto.',
  'Zona 3', 'Rua Goiás, 100, Zona 3',
  -23.4285, -51.9375, true, 'em_analise',
  ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PIXACAO+UBS'],
  now() - interval '2 days'
);


-- ============================================================
-- SOS MULHER — Cadastros e Alerta Ativo
-- Limpa e recria para garantir dados completos
-- ============================================================
DELETE FROM sos_alertas;
DELETE FROM sos_cadastros;

INSERT INTO sos_cadastros (id, telefone, nome, endereco, referencia, agressor, contato_confianca_nome, contato_confianca_telefone) VALUES
('50500d01-0001-4000-a000-000000000001', '44977050001', 'Maria Silva', 'Rua das Acácias, 120, Jardim Alvorada', 'Em frente ao mercadinho do João', 'João Carlos Silva', 'Mãe - Dona Cida', '44966010001'),
('50500d01-0002-4000-a000-000000000002', '44977050002', 'Joana Ferreira', 'Av. Morangueira, 3400, ap 22, Zona 7', 'Prédio azul ao lado do banco', 'Pedro Ferreira', 'Irmã - Paula', '44966010002'),
('50500d01-0003-4000-a000-000000000003', '44977050003', 'Lucia Santos', 'Rua Pioneiro, 55, Nova Esperança', 'Casa amarela com portão de ferro', 'Marcos Antônio Santos', 'Vizinha - Marta', '44966010003');

-- Alerta ATIVO com token de rastreamento (faz o dashboard ficar vermelho)
INSERT INTO sos_alertas (cadastro_id, telefone, codigo_usado, status, latitude, longitude, token_rastreamento, created_at)
VALUES (
  '50500d01-0001-4000-a000-000000000001',
  '44977050001', '.', 'active',
  -23.4420, -51.9200,
  'demo_tk_01',
  now() - interval '3 minutes'
);

-- Alerta resolvido (histórico)
INSERT INTO sos_alertas (cadastro_id, telefone, codigo_usado, status, latitude, longitude, resolvido_em, atendido_por, notas, created_at)
VALUES (
  '50500d01-0002-4000-a000-000000000002',
  '44977050002', '.', 'resolved',
  -23.4156, -51.9280,
  now() - interval '2 days',
  'Patrulha Maria da Penha #03',
  'Vítima acolhida. Medida protetiva solicitada. Agressor não estava no local.',
  now() - interval '2 days 15 minutes'
);


-- ============================================================
-- FEEDBACKS — Alguns exemplos para a aba Feedbacks
-- ============================================================
DELETE FROM feedbacks;

INSERT INTO feedbacks (protocolo, telefone, nome, categoria, sentimento, urgencia, mensagem, resumo, created_at) VALUES
('MGA-2026-00030', '44988020001', 'Dona Terezinha', 'elogio', 'positivo', 'normal', 'Quero parabenizar a equipe que veio limpar a praça do bairro! Ficou lindo, obrigada prefeitura ❤️', 'Elogio à equipe de limpeza da praça', now() - interval '1 day'),
('MGA-2026-00031', '44988020002', NULL, 'reclamacao', 'negativo', 'alta', 'O ônibus da linha 22 tá sempre atrasado de manhã. Chego atrasada no trabalho todo dia por causa disso', 'Reclamação sobre atraso do ônibus linha 22', now() - interval '18 hours'),
('MGA-2026-00032', '44988020003', 'Pedro Augusto', 'sugestao', 'neutro', 'normal', 'Seria bom colocar mais lixeiras na av colombo perto da uem. Os alunos jogam lixo no chao pq nao tem lixeira', 'Sugestão de lixeiras na Av. Colombo', now() - interval '8 hours'),
('MGA-2026-00033', '44988020004', 'Carla Mendes', 'elogio', 'positivo', 'normal', 'Parabéns pelo app de denúncia!! Denunciei uma pichação e em 2 dias já tinham pintado o muro. Sistema muito bom 👏', 'Elogio ao sistema de denúncias', now() - interval '4 hours');
