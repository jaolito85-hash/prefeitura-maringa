-- ============================================================
-- NODE DATA MARINGÁ — Migration 011: MEGA SEED DEMO
-- Dados volumosos e realistas para apresentação à Prefeitura
-- 25-26 de março de 2026
--
-- CONTEÚDO:
--   ~80 denúncias (tráfico, pichação, lixo, furto_fios, depredação)
--   ~40 ocorrências com ~120 relatos
--   ~25 feedbacks (elogios, reclamações, sugestões)
--   ~8 cadastros SOS Mulher + 2 alertas ativos + histórico
--   ~20 recompensas em diferentes status
--
-- BAIRROS baseados em dados reais de criminalidade:
--   Zona 7 (líder), Jardim Alvorada, Vila Morangueira,
--   Vila Operária, Centro, Zona 3, Zona 5, Zona 2, Zona 4,
--   Nova Esperança, Jd. Europa, Jd. Universitário, Mandacaru
--
-- IDEMPOTENTE: Limpa e recria. Safe to re-run.
-- ============================================================

-- ============================================================
-- LIMPEZA (ordem reversa por FK)
-- ============================================================
DELETE FROM recompensas;
DELETE FROM denuncias;
DELETE FROM ocorrencias_relatos;
DELETE FROM ocorrencias;
DELETE FROM sos_alertas;
DELETE FROM sos_cadastros;
DELETE FROM feedbacks;

-- Resetar sequência de protocolo
SELECT setval('protocolo_seq', 500, true);

-- ============================================================
-- ============================================================
--                    D E N Ú N C I A S
--           Programa Cidadania Ativa (Decreto 291/2026)
--           80 denúncias espalhadas por 30 dias
-- ============================================================
-- ============================================================

-- ---- TRÁFICO DE DROGAS (25 denúncias — alto volume na Zona 7, Jd Alvorada, Vila Morangueira, Vila Operária) ----

INSERT INTO denuncias (id, protocolo, telefone, nome, categoria, mensagem, bairro, endereco, latitude, longitude, cidadania_ativa, status, valor_recompensa, midia_urls, created_at) VALUES

-- Zona 7 — epicentro do tráfico
('d0010001-0001-4000-a000-000000000001', 'MGA-2026-00501', '5544999900001', NULL, 'trafico_drogas',
 'Todas as noites depois das 22h tem um grupo vendendo drogas na esquina. Chegam de moto e carro preto. Muitos usuários frequentam o local.',
 'Zona 7', 'Rua Neo Alves Martins, 800 - Zona 7', -23.4162, -51.9285, false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '28 days'),

('d0010001-0002-4000-a000-000000000002', 'MGA-2026-00502', '5544999900002', NULL, 'trafico_drogas',
 'Ponto de tráfico na Av. Colombo perto da UEM. Funcionam de dia e de noite. Motoristas param, compram e saem. Já vi menores envolvidos.',
 'Zona 7', 'Avenida Colombo, 4500 - Zona 7', -23.4089, -51.9386, false, 'em_analise', NULL, ARRAY[]::TEXT[], now() - interval '27 days'),

('d0010001-0003-4000-a000-000000000003', 'MGA-2026-00503', '5544999900003', 'Denúncia Anônima', 'trafico_drogas',
 'Tem uma casa na Rua Paranaguá que funciona como boca de fumo. Entra e sai gente a noite toda. Carro com placa de Londrina estaciona lá todo dia.',
 'Zona 7', 'Rua Paranaguá, 340 - Zona 7', -23.4175, -51.9272, false, 'encaminhado', NULL, ARRAY[]::TEXT[], now() - interval '25 days'),

('d0010001-0004-4000-a000-000000000004', 'MGA-2026-00504', '5544999900004', NULL, 'trafico_drogas',
 'Praça próxima à escola estadual virou ponto de tráfico. Crianças presenciam venda de drogas na saída da aula.',
 'Zona 7', 'Rua Joubert de Carvalho, 1200 - Zona 7', -23.4148, -51.9295, false, 'procedente', 300.00, ARRAY[]::TEXT[], now() - interval '22 days'),

('d0010001-0005-4000-a000-000000000005', 'MGA-2026-00505', '5544999900005', NULL, 'trafico_drogas',
 'Terreno abandonado sendo usado como ponto de distribuição de drogas. Vi pacotes grandes sendo descarregados de uma Hilux prata às 3h da madrugada.',
 'Zona 7', 'Rua Santos Dumont, 1500 - Zona 7', -23.4135, -51.9310, false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '20 days'),

('d0010001-0006-4000-a000-000000000006', 'MGA-2026-00506', '5544999900006', NULL, 'trafico_drogas',
 'Bar na esquina funciona como fachada pra tráfico. Fecha às 2h mas continua movimentação nos fundos até 5h da manhã.',
 'Zona 7', 'Rua Piauí, 620 - Zona 7', -23.4170, -51.9260, false, 'em_analise', NULL, ARRAY[]::TEXT[], now() - interval '18 days'),

-- Jardim Alvorada
('d0010001-0007-4000-a000-000000000007', 'MGA-2026-00507', '5544999900007', NULL, 'trafico_drogas',
 'Rapaz de moto vermelha entrega drogas em domicílio no Jardim Alvorada. Sempre entre 19h e 23h. Já relatei pra PM mas continua.',
 'Jardim Alvorada', 'Rua Araçá, 450 - Jardim Alvorada', -23.4430, -51.9192, false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '17 days'),

('d0010001-0008-4000-a000-000000000008', 'MGA-2026-00508', '5544999900008', NULL, 'trafico_drogas',
 'Condomínio abandonado virou ponto de drogas. Usuários acampam no local. Moradores não conseguem mais sair à noite.',
 'Jardim Alvorada', 'Rua Pioneiro, 350 - Jardim Alvorada', -23.4418, -51.9205, false, 'encaminhado', NULL, ARRAY[]::TEXT[], now() - interval '15 days'),

('d0010001-0009-4000-a000-000000000009', 'MGA-2026-00509', '5544999900009', NULL, 'trafico_drogas',
 'Quadra de esportes do bairro virou ponto de uso de drogas. Crianças não podem mais brincar lá.',
 'Jardim Alvorada', 'Rua das Palmeiras, 200 - Jardim Alvorada', -23.4425, -51.9188, false, 'procedente', 300.00, ARRAY[]::TEXT[], now() - interval '12 days'),

-- Vila Morangueira
('d0010001-0010-4000-a000-000000000010', 'MGA-2026-00510', '5544999900010', NULL, 'trafico_drogas',
 'Ponto de venda de crack atrás do supermercado. Funciona 24h. Traficantes armados. Vizinhança com medo.',
 'Vila Morangueira', 'Rua Guaporé, 900 - Vila Morangueira', -23.4050, -51.9320, false, 'em_analise', NULL, ARRAY[]::TEXT[], now() - interval '16 days'),

('d0010001-0011-4000-a000-000000000011', 'MGA-2026-00511', '5544999900011', NULL, 'trafico_drogas',
 'Traficantes usam lava-jato como fachada. Carros entram limpos e saem rápido. Movimentação suspeita o dia inteiro.',
 'Vila Morangueira', 'Avenida Morangueira, 2800 - Vila Morangueira', -23.4065, -51.9305, false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '14 days'),

('d0010001-0012-4000-a000-000000000012', 'MGA-2026-00512', '5544999900012', NULL, 'trafico_drogas',
 'Casa com muros altos e câmeras. Portão abre e fecha a noite toda. Carros param, buzinando 2x, alguém sai e entrega algo. Tráfico evidente.',
 'Vila Morangueira', 'Rua Mandaguari, 580 - Vila Morangueira', -23.4042, -51.9335, false, 'encaminhado', NULL, ARRAY[]::TEXT[], now() - interval '10 days'),

-- Vila Operária
('d0010001-0013-4000-a000-000000000013', 'MGA-2026-00513', '5544999900013', NULL, 'trafico_drogas',
 'Grupo vende drogas na saída da escola à tarde. Abordam adolescentes. Situação gravíssima.',
 'Vila Operária', 'Rua Vereador José Braga Ramos, 300 - Vila Operária', -23.4320, -51.9250, false, 'procedente', 300.00, ARRAY[]::TEXT[], now() - interval '8 days'),

('d0010001-0014-4000-a000-000000000014', 'MGA-2026-00514', '5544999900014', NULL, 'trafico_drogas',
 'Kitnet no Vila Operária funciona como entreposto de drogas. Motoboys fazem delivery de substâncias ilícitas.',
 'Vila Operária', 'Rua Itororó, 780 - Vila Operária', -23.4335, -51.9240, false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '6 days'),

-- Centro / Zona 1
('d0010001-0015-4000-a000-000000000015', 'MGA-2026-00515', '5544999900015', NULL, 'trafico_drogas',
 'Praça da Catedral é ponto de uso de drogas à noite. Moradores de rua e traficantes. Inseguro caminhar.',
 'Centro', 'Praça da Catedral - Centro', -23.4210, -51.9338, false, 'em_analise', NULL, ARRAY[]::TEXT[], now() - interval '5 days'),

('d0010001-0016-4000-a000-000000000016', 'MGA-2026-00516', '5544999900016', NULL, 'trafico_drogas',
 'Estacionamento atrás do terminal urbano é ponto de venda. Tráfico intenso entre 18h e 23h.',
 'Centro', 'Rua Getúlio Vargas, 200 - Centro', -23.4225, -51.9350, false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '4 days'),

('d0010001-0017-4000-a000-000000000017', 'MGA-2026-00517', '5544999900017', NULL, 'trafico_drogas',
 'Rapaz de boné vermelho vende droga na rua em plena luz do dia na região da rodoviária. Absurdo.',
 'Centro', 'Avenida Tamandaré, 1100 - Centro', -23.4240, -51.9365, false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '3 days'),

-- Zona 3
('d0010001-0018-4000-a000-000000000018', 'MGA-2026-00518', '5544999900018', NULL, 'trafico_drogas',
 'Beco atrás da padaria é ponto de tráfico. Moradores ouvem tiros com frequência.',
 'Zona 3', 'Rua Rio Branco, 440 - Zona 3', -23.4278, -51.9375, false, 'encaminhado', NULL, ARRAY[]::TEXT[], now() - interval '2 days'),

-- Mandacaru
('d0010001-0019-4000-a000-000000000019', 'MGA-2026-00519', '5544999900019', NULL, 'trafico_drogas',
 'Terreno baldio no Mandacaru virou ponto de distribuição. Carros com placa de fora estacionam de madrugada.',
 'Mandacaru', 'Rua Mandacarú, 1200 - Mandacaru', -23.4355, -51.9490, false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '1 day'),

-- Jd Universitário
('d0010001-0020-4000-a000-000000000020', 'MGA-2026-00520', '5544999900020', NULL, 'trafico_drogas',
 'República universitária vende drogas para alunos. Muito movimento de gente jovem entrando e saindo rápido.',
 'Jardim Universitário', 'Rua Bragança, 220 - Jardim Universitário', -23.4095, -51.9400, false, 'em_analise', NULL, ARRAY[]::TEXT[], now() - interval '9 days'),

-- Mais Zona 7 (concentração máxima)
('d0010001-0021-4000-a000-000000000021', 'MGA-2026-00521', '5544999900021', NULL, 'trafico_drogas',
 'Ponto de tráfico ao lado da creche municipal. Crianças passam ao lado de usuários de crack diariamente.',
 'Zona 7', 'Rua Alagoas, 310 - Zona 7', -23.4155, -51.9300, false, 'procedente', 300.00, ARRAY[]::TEXT[], now() - interval '19 days'),

('d0010001-0022-4000-a000-000000000022', 'MGA-2026-00522', '5544999900022', NULL, 'trafico_drogas',
 'Biqueira funciona dentro de prédio abandonado. Já vi arma de fogo. Medo de denunciar pessoalmente.',
 'Zona 7', 'Rua Bahia, 550 - Zona 7', -23.4140, -51.9268, false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '13 days'),

('d0010001-0023-4000-a000-000000000023', 'MGA-2026-00523', '5544999900023', NULL, 'trafico_drogas',
 'Carro Gol prata e moto Honda preta fazem entregas de droga na região. Todos os dias entre 20h e 1h.',
 'Zona 7', 'Rua Minas Gerais, 720 - Zona 7', -23.4168, -51.9278, false, 'em_analise', NULL, ARRAY[]::TEXT[], now() - interval '11 days'),

('d0010001-0024-4000-a000-000000000024', 'MGA-2026-00524', '5544999900024', NULL, 'trafico_drogas',
 'Tráfico aberto na rua, sem nenhuma vergonha. Vários jovens vendendo e usando drogas na calçada.',
 'Zona 7', 'Rua Pará, 280 - Zona 7', -23.4145, -51.9252, false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '7 days'),

('d0010001-0025-4000-a000-000000000025', 'MGA-2026-00525', '5544999900025', NULL, 'trafico_drogas',
 'Denuncio pela terceira vez. Casa com luz vermelha na janela. Entra carro importado toda madrugada. Tráfico pesado.',
 'Zona 7', 'Rua Sergipe, 190 - Zona 7', -23.4158, -51.9245, false, 'encaminhado', NULL, ARRAY[]::TEXT[], now() - interval '23 days'),


-- ---- PICHAÇÃO (15 denúncias) ----

('d0010001-0026-4000-a000-000000000026', 'MGA-2026-00526', '5544999900026', 'Marcos Souza', 'pichacao',
 'Picharam o muro da escola Gastão Vidigal com tinta spray preta. Tem símbolo de facção.',
 'Zona 7', 'Rua Duque de Caxias, 400 - Zona 7', -23.4160, -51.9290, true, 'procedente', 100.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+ESCOLA'], now() - interval '26 days'),

('d0010001-0027-4000-a000-000000000027', 'MGA-2026-00527', '5544999900027', 'Luciana Torres', 'pichacao',
 'Muro do posto de saúde todo pichado. Acabaram de pintar e já picharam de novo na mesma noite.',
 'Zona 3', 'Rua Goiás, 100 - Zona 3', -23.4285, -51.9375, true, 'em_analise', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PIXACAO+UBS'], now() - interval '24 days'),

('d0010001-0028-4000-a000-000000000028', 'MGA-2026-00528', '5544999900028', 'José Aparecido', 'pichacao',
 'Viaduto da Av. Colombo completamente pichado. Imagem horrível pra cidade.',
 'Zona 7', 'Avenida Colombo, 5800 - Zona 7', -23.4080, -51.9395, true, 'recompensa_paga', 100.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+VIADUTO'], now() - interval '21 days'),

('d0010001-0029-4000-a000-000000000029', 'MGA-2026-00529', '5544999900029', 'Ana Carolina', 'pichacao',
 'Pichação nos bancos e brinquedos da praça do bairro. Frases obscenas. Crianças brincam ali.',
 'Jardim Alvorada', 'Rua Pioneiro, 500 - Jardim Alvorada', -23.4415, -51.9210, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+PRACA'], now() - interval '19 days'),

('d0010001-0030-4000-a000-000000000030', 'MGA-2026-00530', '5544999900030', 'Paulo Roberto', 'pichacao',
 'Picharam toda a fachada da igreja matriz com tinta vermelha.',
 'Centro', 'Avenida Brasil, 2200 - Centro', -23.4188, -51.9345, true, 'procedente', 100.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+IGREJA'], now() - interval '17 days'),

('d0010001-0031-4000-a000-000000000031', 'MGA-2026-00531', '5544999900031', 'Maria Eduarda', 'pichacao',
 'Pichação com spray no muro do cemitério municipal. Palavras ofensivas.',
 'Zona 2', 'Rua Santos Dumont, 2100 - Zona 2', -23.4255, -51.9505, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+MURO'], now() - interval '15 days'),

('d0010001-0032-4000-a000-000000000032', 'MGA-2026-00532', '5544999900032', NULL, 'pichacao',
 'Vários prédios comerciais da Av. Brasil pichados na mesma noite. Parece ação coordenada.',
 'Centro', 'Avenida Brasil, 3500 - Centro', -23.4178, -51.9355, false, 'em_analise', NULL,
 ARRAY[]::TEXT[], now() - interval '13 days'),

('d0010001-0033-4000-a000-000000000033', 'MGA-2026-00533', '5544999900033', 'Fernanda Oliveira', 'pichacao',
 'Muro da creche municipal pichado com símbolo de gangue. Pais estão preocupados.',
 'Vila Morangueira', 'Rua Guaporé, 400 - Vila Morangueira', -23.4055, -51.9318, true, 'procedente', 100.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+CRECHE'], now() - interval '11 days'),

('d0010001-0034-4000-a000-000000000034', 'MGA-2026-00534', '5544999900034', 'Ricardo Almeida', 'pichacao',
 'Ponto de ônibus da Av. Mandacaru todo pichado e com vidros quebrados.',
 'Mandacaru', 'Avenida Mandacaru, 800 - Mandacaru', -23.4345, -51.9495, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+PONTO'], now() - interval '9 days'),

('d0010001-0035-4000-a000-000000000035', 'MGA-2026-00535', '5544999900035', 'Claudia Mendes', 'pichacao',
 'Muro recém-pintado da APAE foi pichado. Revoltante — é uma instituição que ajuda pessoas com deficiência.',
 'Zona 4', 'Avenida Cerro Azul, 800 - Zona 4', -23.4228, -51.9425, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+APAE'], now() - interval '7 days'),

('d0010001-0036-4000-a000-000000000036', 'MGA-2026-00536', '5544999900036', 'Thiago Martins', 'pichacao',
 'Pichação no monumento da Catedral. Patrimônio histórico da cidade sendo destruído.',
 'Centro', 'Praça da Catedral - Centro', -23.4205, -51.9340, true, 'em_analise', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+CATEDRAL'], now() - interval '5 days'),

('d0010001-0037-4000-a000-000000000037', 'MGA-2026-00537', '5544999900037', 'Beatriz Lima', 'pichacao',
 'Vários postes de iluminação pichados na Av. Morangueira. Pichação cobre inclusive os números dos postes.',
 'Vila Morangueira', 'Avenida Morangueira, 3200 - Vila Morangueira', -23.4060, -51.9310, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+POSTES'], now() - interval '3 days'),

('d0010001-0038-4000-a000-000000000038', 'MGA-2026-00538', '5544999900038', 'Gustavo Henrique', 'pichacao',
 'Passarela de pedestres na Colombo cheia de pichações. Turistas veem isso ao chegar na cidade.',
 'Zona 7', 'Avenida Colombo, 6200 - Zona 7', -23.4075, -51.9405, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+PASSARELA'], now() - interval '2 days'),

('d0010001-0039-4000-a000-000000000039', 'MGA-2026-00539', '5544999900039', 'Juliana Costa', 'pichacao',
 'Escola municipal pichada de novo. Terceira vez este mês. Precisamos de câmeras no local.',
 'Vila Operária', 'Rua Itororó, 500 - Vila Operária', -23.4330, -51.9245, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+ESCOLA2'], now() - interval '1 day'),

('d0010001-0040-4000-a000-000000000040', 'MGA-2026-00540', '5544999900040', 'Renato Campos', 'pichacao',
 'Picharam o muro do parque do Japão. Lugar turístico ficou horrível.',
 'Zona 4', 'Avenida Cerro Azul, 1200 - Zona 4', -23.4220, -51.9430, true, 'procedente', 100.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PICHACAO+PARQUE'], now() - interval '14 days'),


-- ---- DESCARTE IRREGULAR DE LIXO (15 denúncias) ----

('d0010001-0041-4000-a000-000000000041', 'MGA-2026-00541', '5544999900041', 'Sandra Melo', 'descarte_irregular',
 'Entulho de construção despejado no terreno baldio. Caminhão branco sem placa descarga à noite.',
 'Nova Esperança', 'Rua das Palmeiras, 800 - Nova Esperança', -23.4105, -51.9160, true, 'procedente', 80.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=LIXO+TERRENO'], now() - interval '26 days'),

('d0010001-0042-4000-a000-000000000042', 'MGA-2026-00542', '5544999900042', 'Pedro Henrique', 'descarte_irregular',
 'Lixo hospitalar jogado no córrego. Seringas e frascos de medicamento. Perigo de contaminação.',
 'Zona 5', 'Rua das Margaridas, 300 - Zona 5', -23.4315, -51.9445, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=LIXO+HOSPITALAR'], now() - interval '24 days'),

('d0010001-0043-4000-a000-000000000043', 'MGA-2026-00543', '5544999900043', 'Camila Rodrigues', 'descarte_irregular',
 'Sofás, colchões e geladeira velha jogados na calçada. Faz uma semana e ninguém recolheu.',
 'Zona 7', 'Rua Piauí, 380 - Zona 7', -23.4172, -51.9258, true, 'em_analise', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=LIXO+CALCADA'], now() - interval '22 days'),

('d0010001-0044-4000-a000-000000000044', 'MGA-2026-00544', '5544999900044', 'Rodrigo Santos', 'descarte_irregular',
 'Pneus velhos jogados no fundo do terreno. Foco de dengue certo. Período de chuvas.',
 'Jardim Alvorada', 'Rua Araçá, 600 - Jardim Alvorada', -23.4428, -51.9198, true, 'procedente', 80.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PNEUS+DENGUE'], now() - interval '20 days'),

('d0010001-0045-4000-a000-000000000045', 'MGA-2026-00545', '5544999900045', NULL, 'descarte_irregular',
 'Óleo de cozinha despejado no bueiro da rua. Cheiro forte. Vizinho do restaurante faz isso todo dia.',
 'Centro', 'Rua Getúlio Vargas, 500 - Centro', -23.4222, -51.9348, false, 'novo', NULL,
 ARRAY[]::TEXT[], now() - interval '18 days'),

('d0010001-0046-4000-a000-000000000046', 'MGA-2026-00546', '5544999900046', 'Adriana Lima', 'descarte_irregular',
 'Terreno baldio virou lixão. Ratos enormes. Mau cheiro insuportável. Moradores doentes.',
 'Vila Morangueira', 'Rua Mandaguari, 900 - Vila Morangueira', -23.4048, -51.9330, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=TERRENO+LIXAO'], now() - interval '16 days'),

('d0010001-0047-4000-a000-000000000047', 'MGA-2026-00547', '5544999900047', 'Carlos Eduardo', 'descarte_irregular',
 'Restos de poda jogados na calçada bloqueando passagem de cadeirantes.',
 'Zona 2', 'Rua Santos Dumont, 1800 - Zona 2', -23.4252, -51.9508, true, 'recompensa_paga', 80.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PODA+CALCADA'], now() - interval '14 days'),

('d0010001-0048-4000-a000-000000000048', 'MGA-2026-00548', '5544999900048', 'Marina Alves', 'descarte_irregular',
 'Caminhão despeja entulho todo final de semana no mesmo terreno. Já reclamei 3 vezes.',
 'Vila Operária', 'Rua Vereador José Braga Ramos, 600 - Vila Operária', -23.4325, -51.9248, true, 'em_analise', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=ENTULHO+TERRENO'], now() - interval '12 days'),

('d0010001-0049-4000-a000-000000000049', 'MGA-2026-00549', '5544999900049', 'Felipe Augusto', 'descarte_irregular',
 'Sacolas de lixo doméstico jogadas na margem do córrego Mandacaru. Contaminação da água.',
 'Mandacaru', 'Rua Mandacarú, 500 - Mandacaru', -23.4350, -51.9488, true, 'procedente', 80.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=LIXO+CORREGO'], now() - interval '10 days'),

('d0010001-0050-4000-a000-000000000050', 'MGA-2026-00550', '5544999900050', 'Patrícia Ferreira', 'descarte_irregular',
 'Loja de materiais de construção despeja restos na rua. Pedras, areia e cimento na calçada.',
 'Zona 4', 'Avenida Cerro Azul, 1500 - Zona 4', -23.4218, -51.9435, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=ENTULHO+LOJA'], now() - interval '8 days'),

('d0010001-0051-4000-a000-000000000051', 'MGA-2026-00551', '5544999900051', 'Roberto Dias', 'descarte_irregular',
 'Animais mortos jogados no terreno. Cheiro horrível. Possível crime ambiental.',
 'Zona 5', 'Rua das Violetas, 200 - Zona 5', -23.4318, -51.9442, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=DESCARTE+ANIMAIS'], now() - interval '6 days'),

('d0010001-0052-4000-a000-000000000052', 'MGA-2026-00552', '5544999900052', 'Cristiane Souza', 'descarte_irregular',
 'Vizinho joga lixo no quintal do terreno vazio. Acúmulo de 3 meses. Dengue na certa.',
 'Jardim Europa', 'Rua do Rosário, 350 - Jardim Europa', -23.4348, -51.9502, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=LIXO+VIZINHO'], now() - interval '4 days'),

('d0010001-0053-4000-a000-000000000053', 'MGA-2026-00553', '5544999900053', 'Leandro Silva', 'descarte_irregular',
 'Resíduos de oficina mecânica (óleo, estopa, peças) despejados no terreno ao lado.',
 'Zona 3', 'Rua Rio Branco, 800 - Zona 3', -23.4275, -51.9378, true, 'em_analise', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=RESIDUOS+OFICINA'], now() - interval '2 days'),

('d0010001-0054-4000-a000-000000000054', 'MGA-2026-00554', '5544999900054', 'Aline Martins', 'descarte_irregular',
 'Móveis velhos e eletrodomésticos abandonados na praça. Perigo para crianças.',
 'Nova Esperança', 'Avenida Mauá, 900 - Nova Esperança', -23.4102, -51.9155, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=MOVEIS+PRACA'], now() - interval '12 hours'),

('d0010001-0055-4000-a000-000000000055', 'MGA-2026-00555', '5544999900055', 'Rogério Lima', 'descarte_irregular',
 'Empresa despeja resíduos químicos no fundo do galpão. Cheiro forte de solvente. Perigo ambiental.',
 'Zona 7', 'Rua Paraná, 1500 - Zona 7', -23.4130, -51.9315, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=RESIDUOS+QUIMICOS'], now() - interval '9 days'),


-- ---- FURTO DE FIOS (10 denúncias) ----

('d0010001-0056-4000-a000-000000000056', 'MGA-2026-00556', '5544999900056', 'Antônio Carlos', 'furto_fios',
 'Furtaram os cabos de cobre do poste na madrugada. Bairro inteiro ficou sem luz.',
 'Zona 7', 'Rua Neo Alves Martins, 1200 - Zona 7', -23.4158, -51.9288, true, 'procedente', 150.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FURTO+FIOS'], now() - interval '25 days'),

('d0010001-0057-4000-a000-000000000057', 'MGA-2026-00557', '5544999900057', 'Simone Oliveira', 'furto_fios',
 'Cabos de iluminação da praça foram furtados. Praça está completamente escura e perigosa.',
 'Jardim Alvorada', 'Rua Pioneiro, 700 - Jardim Alvorada', -23.4412, -51.9215, true, 'recompensa_paga', 150.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FIOS+PRACA'], now() - interval '23 days'),

('d0010001-0058-4000-a000-000000000058', 'MGA-2026-00558', '5544999900058', 'Marcos Paulo', 'furto_fios',
 'Vi dois homens cortando fios do poste às 3h da manhã com alicate. Fugiam de Saveiro branca.',
 'Vila Morangueira', 'Rua Guaporé, 1200 - Vila Morangueira', -23.4045, -51.9325, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FURTO+MADRUGADA'], now() - interval '21 days'),

('d0010001-0059-4000-a000-000000000059', 'MGA-2026-00559', '5544999900059', 'Vanessa Costa', 'furto_fios',
 'Furtaram fios de cobre da construção do novo prédio da prefeitura. Obra parada por causa disso.',
 'Centro', 'Avenida Brasil, 4000 - Centro', -23.4175, -51.9358, true, 'procedente', 150.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FURTO+OBRA'], now() - interval '19 days'),

('d0010001-0060-4000-a000-000000000060', 'MGA-2026-00560', '5544999900060', NULL, 'furto_fios',
 'Semáforo parou de funcionar pq furtaram os fios. Cruzamento perigoso sem sinalização.',
 'Zona 3', 'Rua Goiás c/ Av. Brasil - Zona 3', -23.4282, -51.9370, false, 'em_analise', NULL,
 ARRAY[]::TEXT[], now() - interval '16 days'),

('d0010001-0061-4000-a000-000000000061', 'MGA-2026-00561', '5544999900061', 'Douglas Ferreira', 'furto_fios',
 'Furtaram todos os fios de iluminação da ciclovia. Perigoso pedalar à noite.',
 'Zona 5', 'Rua das Margaridas, 100 - Zona 5', -23.4310, -51.9448, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FIOS+CICLOVIA'], now() - interval '13 days'),

('d0010001-0062-4000-a000-000000000062', 'MGA-2026-00562', '5544999900062', 'Priscila Nunes', 'furto_fios',
 'Cabos da rede de internet comunitária furtados. Bairro sem internet há 4 dias.',
 'Vila Operária', 'Rua Itororó, 300 - Vila Operária', -23.4332, -51.9242, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FIOS+INTERNET'], now() - interval '10 days'),

('d0010001-0063-4000-a000-000000000063', 'MGA-2026-00563', '5544999900063', 'Anderson Ramos', 'furto_fios',
 'Fios da iluminação do campo de futebol comunitário furtados pela segunda vez este mês.',
 'Mandacaru', 'Rua Mandacarú, 700 - Mandacaru', -23.4352, -51.9492, true, 'procedente', 150.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FIOS+CAMPO'], now() - interval '7 days'),

('d0010001-0064-4000-a000-000000000064', 'MGA-2026-00564', '5544999900064', 'Gabriela Santos', 'furto_fios',
 'Cabos de cobre do transformador furtados. 200 casas sem energia no calor de 38 graus.',
 'Zona 7', 'Rua Bahia, 900 - Zona 7', -23.4142, -51.9265, true, 'em_analise', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FIOS+TRANSFORMADOR'], now() - interval '4 days'),

('d0010001-0065-4000-a000-000000000065', 'MGA-2026-00565', '5544999900065', 'Rafael Oliveira', 'furto_fios',
 'Homem em moto cortou fios telefônicos de 5 postes seguidos na madrugada. Filmei pela janela.',
 'Nova Esperança', 'Avenida Mauá, 2000 - Nova Esperança', -23.4098, -51.9158, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FURTO+FILMADO'], now() - interval '1 day'),


-- ---- DEPREDAÇÃO DE PATRIMÔNIO PÚBLICO (15 denúncias) ----

('d0010001-0066-4000-a000-000000000066', 'MGA-2026-00566', '5544999900066', 'Dona Terezinha', 'depredacao',
 'Quebraram o bebedouro e os bancos da praça. Idosos não têm onde sentar.',
 'Centro', 'Praça da República - Centro', -23.4200, -51.9340, true, 'procedente', 150.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PRACA+DESTRUIDA'], now() - interval '27 days'),

('d0010001-0067-4000-a000-000000000067', 'MGA-2026-00567', '5544999900067', 'João Batista', 'depredacao',
 'Arrancaram a placa de sinalização de trânsito. Cruzamento perigoso sem indicação.',
 'Zona 7', 'Rua Paranaguá c/ Rua Piauí - Zona 7', -23.4173, -51.9270, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PLACA+ARRANCADA'], now() - interval '23 days'),

('d0010001-0068-4000-a000-000000000068', 'MGA-2026-00568', '5544999900068', 'Eliane Souza', 'depredacao',
 'Ponto de ônibus destruído. Vidro estilhaçado no chão. Passageiros esperam sol e chuva.',
 'Zona 7', 'Avenida Colombo, 4200 - Zona 7', -23.4150, -51.9275, true, 'recompensa_paga', 150.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PONTO+DESTRUIDO'], now() - interval '20 days'),

('d0010001-0069-4000-a000-000000000069', 'MGA-2026-00569', '5544999900069', 'Márcio Almeida', 'depredacao',
 'Quebraram a grade de proteção do córrego. Crianças podem cair. Perigo iminente.',
 'Zona 5', 'Rua das Violetas, 400 - Zona 5', -23.4320, -51.9440, true, 'em_analise', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=GRADE+CORREGO'], now() - interval '18 days'),

('d0010001-0070-4000-a000-000000000070', 'MGA-2026-00570', '5544999900070', 'Silvana Martins', 'depredacao',
 'Destruíram os brinquedos do playground da praça. Balanço arrancado, escorregador quebrado.',
 'Jardim Alvorada', 'Rua das Palmeiras, 400 - Jardim Alvorada', -23.4422, -51.9195, true, 'procedente', 150.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PLAYGROUND+DESTRUIDO'], now() - interval '15 days'),

('d0010001-0071-4000-a000-000000000071', 'MGA-2026-00571', '5544999900071', 'Alexandre Lima', 'depredacao',
 'Câmeras de segurança do parque foram arrancadas e levadas. Coincide com aumento de assaltos no local.',
 'Zona 4', 'Avenida Cerro Azul, 600 - Zona 4', -23.4232, -51.9418, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=CAMERAS+FURTADAS'], now() - interval '12 days'),

('d0010001-0072-4000-a000-000000000072', 'MGA-2026-00572', '5544999900072', 'Débora Ferreira', 'depredacao',
 'Lixeiras públicas queimadas na avenida. Terceira vez este mês. Parecem atos de vandalismo coordenado.',
 'Vila Morangueira', 'Avenida Morangueira, 2500 - Vila Morangueira', -23.4068, -51.9308, true, 'em_analise', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=LIXEIRAS+QUEIMADAS'], now() - interval '9 days'),

('d0010001-0073-4000-a000-000000000073', 'MGA-2026-00573', '5544999900073', 'Fábio Augusto', 'depredacao',
 'Mesas e cadeiras da área de convivência do parque arrancadas e jogadas no lago.',
 'Centro', 'Avenida Brasil, 5000 - Centro', -23.4168, -51.9362, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=MESAS+LAGO'], now() - interval '6 days'),

('d0010001-0074-4000-a000-000000000074', 'MGA-2026-00574', '5544999900074', 'Luciano Ramos', 'depredacao',
 'Quebraram o orelhão e a tampa do bueiro da rua. Buraco aberto no meio da calçada.',
 'Zona 3', 'Rua Rio Branco, 600 - Zona 3', -23.4280, -51.9372, true, 'procedente', 150.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=ORELHAO+BUEIRO'], now() - interval '3 days'),

('d0010001-0075-4000-a000-000000000075', 'MGA-2026-00575', '5544999900075', 'Isabela Costa', 'depredacao',
 'Arrancaram a torneira do bebedouro público da academia ao ar livre. Água jorrando há 2 dias.',
 'Mandacaru', 'Rua Mandacarú, 900 - Mandacaru', -23.4348, -51.9495, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=BEBEDOURO+JORRANDO'], now() - interval '1 day'),

('d0010001-0076-4000-a000-000000000076', 'MGA-2026-00576', '5544999900076', 'Henrique Alves', 'depredacao',
 'Destruíram o letreiro de entrada do bairro. Era novo, instalado mês passado pela prefeitura.',
 'Nova Esperança', 'Avenida Mauá, 500 - Nova Esperança', -23.4104, -51.9152, true, 'em_analise', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=LETREIRO+DESTRUIDO'], now() - interval '11 days'),

('d0010001-0077-4000-a000-000000000077', 'MGA-2026-00577', '5544999900077', 'Tatiane Mendes', 'depredacao',
 'Banco de concreto da praça quebrado com marreta. Fragmentos espalhados. Perigo pra crianças.',
 'Vila Operária', 'Rua Vereador José Braga Ramos, 150 - Vila Operária', -23.4328, -51.9255, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=BANCO+QUEBRADO'], now() - interval '8 days'),

('d0010001-0078-4000-a000-000000000078', 'MGA-2026-00578', '5544999900078', 'Vinícius Santos', 'depredacao',
 'Portão de ferro da quadra poliesportiva arrancado. Quadra agora usada por usuários de drogas à noite.',
 'Zona 7', 'Rua Joubert de Carvalho, 900 - Zona 7', -23.4150, -51.9292, true, 'procedente', 150.00,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=PORTAO+QUADRA'], now() - interval '5 days'),

('d0010001-0079-4000-a000-000000000079', 'MGA-2026-00579', '5544999900079', 'Amanda Ribeiro', 'depredacao',
 'Refletor da quadra de esportes destruído a pedradas. R$3.000 de prejuízo pra prefeitura.',
 'Jardim Universitário', 'Rua Bragança, 400 - Jardim Universitário', -23.4092, -51.9405, true, 'novo', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=REFLETOR+QUEBRADO'], now() - interval '2 days'),

('d0010001-0080-4000-a000-000000000080', 'MGA-2026-00580', '5544999900080', 'Renan Oliveira', 'depredacao',
 'Grade do cemitério municipal arrancada. Pedaço de 10 metros sem proteção. Possível furto de metal.',
 'Zona 2', 'Rua Santos Dumont, 2300 - Zona 2', -23.4258, -51.9510, true, 'encaminhado', NULL,
 ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=GRADE+CEMITERIO'], now() - interval '15 days');


-- ============================================================
-- ============================================================
--                 O C O R R Ê N C I A S
--       40 ocorrências com ~120 relatos espalhados
-- ============================================================
-- ============================================================

-- ---- QUEDA DE ÁRVORE (6) ----

INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, equipe, created_at) VALUES
('0c200001-0001-4000-a000-000000000001', 'MGA-2026-00601', 'queda_arvore', 'alta', 'em_atendimento',
 'Queda de árvore grande na Avenida Brasil',
 'Árvore de grande porte caiu sobre a via, bloqueando duas faixas. Trânsito desviado pela Rua Santos Dumont. Fios de alta tensão no chão.',
 'Avenida Brasil, 1200 - Centro', 'avenida brasil 1200 centro', 'Centro',
 -23.4195, -51.9331, 8, 'Equipe Defesa Civil #02', now() - interval '2 hours 30 min'),

('0c200001-0002-4000-a000-000000000002', 'MGA-2026-00602', 'queda_arvore', 'media', 'aberto',
 'Árvore caída na Rua Paranaguá',
 'Árvore média caiu sobre calçada e um veículo estacionado. Sem vítimas.',
 'Rua Paranaguá, 500 - Zona 7', 'rua paranagua 500 zona 7', 'Zona 7',
 -23.4172, -51.9275, 4, NULL, now() - interval '5 hours'),

('0c200001-0003-4000-a000-000000000003', 'MGA-2026-00603', 'queda_arvore', 'baixa', 'resolvido',
 'Galho grande caiu na Rua Mandacarú',
 'Galho pesado caiu bloqueando meia pista. Já removido.',
 'Rua Mandacarú, 320 - Mandacaru', 'rua mandacaru 320 mandacaru', 'Mandacaru',
 -23.4350, -51.9500, 2, 'Equipe Poda #05', now() - interval '1 day'),

('0c200001-0004-4000-a000-000000000004', 'MGA-2026-00604', 'queda_arvore', 'critica', 'em_atendimento',
 'Árvore caiu sobre casa na Vila Morangueira',
 'Árvore de 15 metros caiu sobre telhado de residência. Família evacuada. Risco estrutural.',
 'Rua Guaporé, 600 - Vila Morangueira', 'rua guapore 600 vila morangueira', 'Vila Morangueira',
 -23.4052, -51.9322, 6, 'Defesa Civil + Bombeiros', now() - interval '45 min'),

('0c200001-0005-4000-a000-000000000005', 'MGA-2026-00605', 'queda_arvore', 'media', 'aberto',
 'Árvore tombou no Jardim Alvorada',
 'Raízes expostas, árvore inclinada sobre a rede elétrica. Pode cair a qualquer momento.',
 'Rua Araçá, 800 - Jardim Alvorada', 'rua araca 800 jardim alvorada', 'Jardim Alvorada',
 -23.4435, -51.9190, 3, NULL, now() - interval '3 hours'),

('0c200001-0006-4000-a000-000000000006', 'MGA-2026-00606', 'queda_arvore', 'alta', 'aberto',
 'Eucalipto caiu na Av. Colombo',
 'Eucalipto enorme caiu bloqueando 3 faixas. Congestionamento de 2km.',
 'Avenida Colombo, 5200 - Zona 7', 'avenida colombo 5200 zona 7', 'Zona 7',
 -23.4085, -51.9390, 9, NULL, now() - interval '1 hour');

-- ---- ENCHENTE/ALAGAMENTO (5) ----

INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at) VALUES
('0c200001-0007-4000-a000-000000000007', 'MGA-2026-00607', 'enchente_alagamento', 'critica', 'aberto',
 'Alagamento severo na Rua das Margaridas',
 'Rua completamente alagada, água invadindo casas e comércios. Moradores ilhados. Bombeiros acionados.',
 'Rua das Margaridas, 450 - Zona 5', 'rua das margaridas 450 zona 5', 'Zona 5',
 -23.4312, -51.9450, 12, now() - interval '3 hours'),

('0c200001-0008-4000-a000-000000000008', 'MGA-2026-00608', 'enchente_alagamento', 'alta', 'em_atendimento',
 'Alagamento no centro após chuva forte',
 'Bueiros não dão vazão. Água na altura dos pneus. Comércio alagado.',
 'Avenida Brasil, 2500 - Centro', 'avenida brasil 2500 centro', 'Centro',
 -23.4185, -51.9348, 7, now() - interval '2 hours'),

('0c200001-0009-4000-a000-000000000009', 'MGA-2026-00609', 'enchente_alagamento', 'media', 'aberto',
 'Rua alagada na Vila Operária',
 'Acúmulo de água após chuva. Carros não conseguem passar. Bueiro entupido com lixo.',
 'Rua Itororó, 600 - Vila Operária', 'rua itororo 600 vila operaria', 'Vila Operária',
 -23.4333, -51.9243, 4, now() - interval '4 hours'),

('0c200001-0010-4000-a000-000000000010', 'MGA-2026-00610', 'enchente_alagamento', 'alta', 'aberto',
 'Córrego transbordou no Mandacaru',
 'Córrego Mandacaru transbordou com a chuva. Casas ribeirinhas alagadas. Famílias precisam de abrigo.',
 'Rua Mandacarú, 400 - Mandacaru', 'rua mandacaru 400 mandacaru', 'Mandacaru',
 -23.4358, -51.9485, 8, now() - interval '1 hour 30 min'),

('0c200001-0011-4000-a000-000000000011', 'MGA-2026-00611', 'enchente_alagamento', 'baixa', 'resolvido',
 'Ponto de alagamento na Zona 2',
 'Alagamento recorrente na esquina. Água escoou após 2h.',
 'Rua Santos Dumont, 1500 - Zona 2', 'rua santos dumont 1500 zona 2', 'Zona 2',
 -23.4248, -51.9502, 2, now() - interval '8 hours');

-- ---- BURACO NA VIA (6) ----

INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at) VALUES
('0c200001-0012-4000-a000-000000000012', 'MGA-2026-00612', 'buraco_via', 'media', 'aberto',
 'Buraco grande na Av. Colombo',
 'Buraco na pista sentido centro. Carro já caiu. Sem sinalização.',
 'Avenida Colombo, 3800 - Zona 7', 'avenida colombo 3800 zona 7', 'Zona 7',
 -23.4156, -51.9280, 5, now() - interval '6 hours'),

('0c200001-0013-4000-a000-000000000013', 'MGA-2026-00613', 'buraco_via', 'alta', 'equipe_caminho',
 'Cratera na Rua Pioneiro',
 'Asfalto cedeu formando cratera de 2m. Risco de desabamento. Trânsito interditado.',
 'Rua Pioneiro, 200 - Jardim Alvorada', 'rua pioneiro 200 jardim alvorada', 'Jardim Alvorada',
 -23.4425, -51.9208, 6, now() - interval '4 hours'),

('0c200001-0014-4000-a000-000000000014', 'MGA-2026-00614', 'buraco_via', 'baixa', 'aberto',
 'Buracos múltiplos na Zona 3',
 'Trecho de 200m com vários buracos. Veículos desviam pela contramão.',
 'Rua Rio Branco, 500 - Zona 3', 'rua rio branco 500 zona 3', 'Zona 3',
 -23.4282, -51.9368, 3, now() - interval '2 days'),

('0c200001-0015-4000-a000-000000000015', 'MGA-2026-00615', 'buraco_via', 'media', 'aberto',
 'Buraco em frente à escola',
 'Buraco profundo na entrada da escola. Alunos desviam pela rua. Perigoso.',
 'Rua Joubert de Carvalho, 1000 - Zona 7', 'rua joubert de carvalho 1000 zona 7', 'Zona 7',
 -23.4152, -51.9298, 4, now() - interval '1 day'),

('0c200001-0016-4000-a000-000000000016', 'MGA-2026-00616', 'buraco_via', 'baixa', 'resolvido',
 'Buraco tapado na Av. Cerro Azul',
 'Buraco foi reparado pela equipe de manutenção.',
 'Avenida Cerro Azul, 300 - Zona 4', 'avenida cerro azul 300 zona 4', 'Zona 4',
 -23.4235, -51.9415, 2, now() - interval '5 days'),

('0c200001-0017-4000-a000-000000000017', 'MGA-2026-00617', 'buraco_via', 'media', 'aberto',
 'Buraco na Av. Morangueira',
 'Buraco no cruzamento. Motociclista caiu hoje de manhã.',
 'Avenida Morangueira, 3000 - Vila Morangueira', 'avenida morangueira 3000 vila morangueira', 'Vila Morangueira',
 -23.4058, -51.9312, 3, now() - interval '10 hours');

-- ---- ILUMINAÇÃO PÚBLICA (5) ----

INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at) VALUES
('0c200001-0018-4000-a000-000000000018', 'MGA-2026-00618', 'iluminacao_publica', 'baixa', 'aberto',
 'Postes apagados na Rua Pioneiro',
 'Três postes apagados. Trecho escuro e perigoso à noite. Moradores com medo de assalto.',
 'Rua Pioneiro, 88 - Jardim Alvorada', 'rua pioneiro 88 jardim alvorada', 'Jardim Alvorada',
 -23.4420, -51.9200, 2, now() - interval '12 hours'),

('0c200001-0019-4000-a000-000000000019', 'MGA-2026-00619', 'iluminacao_publica', 'media', 'equipe_caminho',
 'Quadra inteira sem luz na Zona 7',
 'Furto de cabos deixou quadra inteira no escuro. Assaltos aumentaram.',
 'Rua Neo Alves Martins, 1200 - Zona 7', 'rua neo alves martins 1200 zona 7', 'Zona 7',
 -23.4158, -51.9288, 5, now() - interval '18 hours'),

('0c200001-0020-4000-a000-000000000020', 'MGA-2026-00620', 'iluminacao_publica', 'baixa', 'aberto',
 'Poste piscando na Vila Operária',
 'Poste com lâmpada piscando há 2 semanas. Incomoda moradores.',
 'Rua Vereador José Braga Ramos, 400 - Vila Operária', 'rua vereador jose braga ramos 400 vila operaria', 'Vila Operária',
 -23.4322, -51.9252, 1, now() - interval '3 days'),

('0c200001-0021-4000-a000-000000000021', 'MGA-2026-00621', 'iluminacao_publica', 'baixa', 'resolvido',
 'Lâmpada queimada na Av. Mauá',
 'Lâmpada substituída pela equipe de manutenção.',
 'Avenida Mauá, 1200 - Nova Esperança', 'avenida maua 1200 nova esperanca', 'Nova Esperança',
 -23.4100, -51.9155, 1, now() - interval '4 days'),

('0c200001-0022-4000-a000-000000000022', 'MGA-2026-00622', 'iluminacao_publica', 'media', 'aberto',
 'Iluminação da ciclovia apagada',
 'Toda a iluminação da ciclovia está apagada após furto de fios. Ciclistas em risco.',
 'Rua das Margaridas, 100 - Zona 5', 'rua das margaridas 100 zona 5', 'Zona 5',
 -23.4308, -51.9452, 3, now() - interval '2 days');

-- ---- INCÊNDIO (4) ----

INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, equipe, created_at) VALUES
('0c200001-0023-4000-a000-000000000023', 'MGA-2026-00623', 'incendio', 'alta', 'em_atendimento',
 'Incêndio em terreno baldio na Zona 3',
 'Fogo alto em terreno com mato seco. Fumaça densa. Próximo a residências.',
 'Rua Goiás, 240 - Zona 3', 'rua goias 240 zona 3', 'Zona 3',
 -23.4280, -51.9380, 5, 'Corpo de Bombeiros #07', now() - interval '1 hour 30 min'),

('0c200001-0024-4000-a000-000000000024', 'MGA-2026-00624', 'incendio', 'critica', 'em_atendimento',
 'Incêndio em galpão abandonado',
 'Galpão abandonado pegou fogo. Risco de desabamento. Ruas adjacentes evacuadas.',
 'Rua Bahia, 1100 - Zona 7', 'rua bahia 1100 zona 7', 'Zona 7',
 -23.4138, -51.9270, 7, 'Bombeiros #03 + #07', now() - interval '30 min'),

('0c200001-0025-4000-a000-000000000025', 'MGA-2026-00625', 'incendio', 'media', 'resolvido',
 'Queimada em terreno na Nova Esperança',
 'Fogo controlado. Área queimada: ~500m². Sem vítimas.',
 'Avenida Mauá, 2500 - Nova Esperança', 'avenida maua 2500 nova esperanca', 'Nova Esperança',
 -23.4095, -51.9162, 3, 'Bombeiros #05', now() - interval '6 hours'),

('0c200001-0026-4000-a000-000000000026', 'MGA-2026-00626', 'incendio', 'alta', 'aberto',
 'Foco de incêndio perto de residências',
 'Queimada avançando em direção a casas. Moradores pedindo socorro.',
 'Rua Mandacarú, 1500 - Mandacaru', 'rua mandacaru 1500 mandacaru', 'Mandacaru',
 -23.4360, -51.9480, 4, NULL, now() - interval '40 min');

-- ---- VENDAVAL (3) ----

INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at) VALUES
('0c200001-0027-4000-a000-000000000027', 'MGA-2026-00627', 'vendaval', 'media', 'aberto',
 'Danos de vendaval na Av. Mauá',
 'Vendaval arrancou telhas e derrubou placas. Fios expostos na calçada.',
 'Avenida Mauá, 1500 - Nova Esperança', 'avenida maua 1500 nova esperanca', 'Nova Esperança',
 -23.4100, -51.9150, 4, now() - interval '4 hours'),

('0c200001-0028-4000-a000-000000000028', 'MGA-2026-00628', 'vendaval', 'alta', 'em_atendimento',
 'Telhados arrancados no Jd. Alvorada',
 '3 casas com telhados arrancados pelo vendaval. Famílias desabrigadas.',
 'Rua Pioneiro, 600 - Jardim Alvorada', 'rua pioneiro 600 jardim alvorada', 'Jardim Alvorada',
 -23.4418, -51.9212, 5, now() - interval '2 hours'),

('0c200001-0029-4000-a000-000000000029', 'MGA-2026-00629', 'vendaval', 'baixa', 'resolvido',
 'Placa de trânsito derrubada pelo vento',
 'Placa removida da via. Sem feridos.',
 'Avenida Cerro Azul, 900 - Zona 4', 'avenida cerro azul 900 zona 4', 'Zona 4',
 -23.4225, -51.9422, 1, now() - interval '1 day');

-- ---- ACIDENTE (4) ----

INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, equipe, created_at) VALUES
('0c200001-0030-4000-a000-000000000030', 'MGA-2026-00630', 'acidente', 'alta', 'em_atendimento',
 'Acidente grave na Av. Colombo',
 'Colisão frontal entre carro e caminhonete. 2 vítimas graves. SAMU no local.',
 'Avenida Colombo, 4800 - Zona 7', 'avenida colombo 4800 zona 7', 'Zona 7',
 -23.4092, -51.9382, 6, 'SAMU + PM', now() - interval '50 min'),

('0c200001-0031-4000-a000-000000000031', 'MGA-2026-00631', 'acidente', 'media', 'aberto',
 'Moto x pedestre na Av. Brasil',
 'Motociclista atropelou pedestre na faixa. Pedestre com ferimentos leves.',
 'Avenida Brasil, 3200 - Centro', 'avenida brasil 3200 centro', 'Centro',
 -23.4180, -51.9352, 3, NULL, now() - interval '3 hours'),

('0c200001-0032-4000-a000-000000000032', 'MGA-2026-00632', 'acidente', 'baixa', 'resolvido',
 'Acidente leve na Cerro Azul',
 'Colisão traseira. Sem feridos. Veículos removidos.',
 'Avenida Cerro Azul, 500 - Zona 4', 'avenida cerro azul 500 zona 4', 'Zona 4',
 -23.4230, -51.9420, 2, NULL, now() - interval '8 hours'),

('0c200001-0033-4000-a000-000000000033', 'MGA-2026-00633', 'acidente', 'critica', 'em_atendimento',
 'Capotamento na Av. Morangueira',
 'Veículo capotou após perder controle. Motorista preso nas ferragens. Bombeiros acionados.',
 'Avenida Morangueira, 2200 - Vila Morangueira', 'avenida morangueira 2200 vila morangueira', 'Vila Morangueira',
 -23.4072, -51.9302, 5, 'Bombeiros + SAMU', now() - interval '25 min');

-- ---- DRENAGEM (3) ----

INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at) VALUES
('0c200001-0034-4000-a000-000000000034', 'MGA-2026-00634', 'drenagem', 'baixa', 'aberto',
 'Bueiro entupido na Santos Dumont',
 'Bueiro transbordando com acúmulo de lixo. Mau cheiro forte.',
 'Rua Santos Dumont, 700 - Zona 2', 'rua santos dumont 700 zona 2', 'Zona 2',
 -23.4250, -51.9500, 2, now() - interval '10 hours'),

('0c200001-0035-4000-a000-000000000035', 'MGA-2026-00635', 'drenagem', 'media', 'equipe_caminho',
 'Bueiro quebrado na Rua Goiás',
 'Tampa do bueiro quebrou. Buraco aberto na calçada. Perigo para pedestres.',
 'Rua Goiás, 400 - Zona 3', 'rua goias 400 zona 3', 'Zona 3',
 -23.4278, -51.9382, 3, now() - interval '5 hours'),

('0c200001-0036-4000-a000-000000000036', 'MGA-2026-00636', 'drenagem', 'baixa', 'resolvido',
 'Bueiro limpo na Av. Brasil',
 'Equipe de manutenção realizou limpeza e desentupimento.',
 'Avenida Brasil, 4500 - Centro', 'avenida brasil 4500 centro', 'Centro',
 -23.4170, -51.9360, 1, now() - interval '2 days');

-- ---- DESLIZAMENTO (2) ----

INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at) VALUES
('0c200001-0037-4000-a000-000000000037', 'MGA-2026-00637', 'deslizamento', 'alta', 'aberto',
 'Deslizamento de terra no Mandacaru',
 'Barranco cedeu após chuvas. Terra cobriu parte da rua. Casas em risco.',
 'Rua Mandacarú, 1000 - Mandacaru', 'rua mandacaru 1000 mandacaru', 'Mandacaru',
 -23.4355, -51.9488, 5, now() - interval '2 hours'),

('0c200001-0038-4000-a000-000000000038', 'MGA-2026-00638', 'deslizamento', 'media', 'equipe_caminho',
 'Muro de contenção cedeu',
 'Muro de contenção rompeu. Terra invadiu quintal de residência.',
 'Rua das Violetas, 300 - Zona 5', 'rua das violetas 300 zona 5', 'Zona 5',
 -23.4322, -51.9438, 3, now() - interval '3 hours');

-- ---- DIVERSOS (2) ----

INSERT INTO ocorrencias (id, protocolo, categoria, severidade, status, titulo, descricao, endereco, endereco_normalizado, bairro, latitude, longitude, total_relatos, created_at) VALUES
('0c200001-0039-4000-a000-000000000039', 'MGA-2026-00639', 'animal_solto', 'baixa', 'aberto',
 'Cavalo solto na Av. Colombo',
 'Cavalo sem dono solto no canteiro central. Risco de acidente.',
 'Avenida Colombo, 6000 - Zona 7', 'avenida colombo 6000 zona 7', 'Zona 7',
 -23.4078, -51.9398, 2, now() - interval '1 hour'),

('0c200001-0040-4000-a000-000000000040', 'MGA-2026-00640', 'vazamento_gas', 'critica', 'em_atendimento',
 'Vazamento de gás na Zona 3',
 'Cheiro forte de gás na rua. Moradores evacuados. Bombeiros e Compagas acionados.',
 'Rua Rio Branco, 300 - Zona 3', 'rua rio branco 300 zona 3', 'Zona 3',
 -23.4285, -51.9365, 4, now() - interval '20 min');


-- ============================================================
-- RELATOS DAS OCORRÊNCIAS (3 relatos por ocorrência em média)
-- Gerando relatos para as 10 primeiras (as mais importantes)
-- ============================================================

INSERT INTO ocorrencias_relatos (ocorrencia_id, telefone, nome, mensagem, latitude, longitude, created_at) VALUES
-- Oc 1: Árvore Av Brasil (8 relatos)
('0c200001-0001-4000-a000-000000000001', '5544999110001', 'Marcos Oliveira', 'Uma arvore enorme caiu na av brasil ta bloqueando a rua toda socorro', -23.4195, -51.9331, now() - interval '2 hours 30 min'),
('0c200001-0001-4000-a000-000000000001', '5544999110002', 'Patricia Almeida', 'Gente a arvore caiu na brasil perto do bradesco quase pegou um carro', -23.4196, -51.9329, now() - interval '2 hours 15 min'),
('0c200001-0001-4000-a000-000000000001', '5544999110003', NULL, 'arvore caida na avenida brasil centro impossivel passar', -23.4194, -51.9333, now() - interval '2 hours'),
('0c200001-0001-4000-a000-000000000001', '5544999110004', 'Carlos Eduardo', 'A árvore caiu na fiação elétrica tbm, tá tudo escuro aqui no quarteirão', -23.4197, -51.9330, now() - interval '1 hour 50 min'),
('0c200001-0001-4000-a000-000000000001', '5544999110005', 'Maria José', 'to presa no transito por causa da arvore q caiu na av brasil alguem sabe se ja chamaram a prefeitura?', -23.4193, -51.9335, now() - interval '1 hour 30 min'),
('0c200001-0001-4000-a000-000000000001', '5544999110006', NULL, 'Arvore caida av brasil sentido catedral bloquenado tudo', -23.4198, -51.9328, now() - interval '1 hour 15 min'),
('0c200001-0001-4000-a000-000000000001', '5544999110007', 'Roberta Santos', 'Meu carro ficou preso atras da arvore na brasil, nao consigo sair da vaga', -23.4196, -51.9332, now() - interval '55 min'),
('0c200001-0001-4000-a000-000000000001', '5544999110008', 'Fernando Dias', 'Ja tem 2h q essa arvore caiu na av brasil e ninguem apareceu. ta perigoso pq tem fio de alta tensao no chao', -23.4194, -51.9330, now() - interval '40 min'),

-- Oc 4: Árvore sobre casa Vila Morangueira (6 relatos)
('0c200001-0004-4000-a000-000000000004', '5544999110020', 'Sandra Melo', 'arvore caiu em cima de uma casa na guapore vila morangueira socorro', -23.4052, -51.9322, now() - interval '45 min'),
('0c200001-0004-4000-a000-000000000004', '5544999110021', 'Rogério Lima', 'tem gente dentro da casa onde a arvore caiu!! mandem bombeiros urgente rua guapore 600', -23.4053, -51.9320, now() - interval '40 min'),
('0c200001-0004-4000-a000-000000000004', '5544999110022', NULL, 'arvore gigante caiu no telhado guapore morangueira familia ta la dentro', -23.4051, -51.9324, now() - interval '35 min'),
('0c200001-0004-4000-a000-000000000004', '5544999110023', 'Dona Cida', 'meu deus a arvore destruiu o telhado do vizinho ta tudo quebrado aqui', -23.4054, -51.9321, now() - interval '30 min'),
('0c200001-0004-4000-a000-000000000004', '5544999110024', 'Thiago Martins', 'bombeiros ja chegaram na guapore estao tirando a familia de dentro da casa', -23.4050, -51.9323, now() - interval '20 min'),
('0c200001-0004-4000-a000-000000000004', '5544999110025', 'Maria Eduarda', 'update: familia foi retirada com vida. casa ta destruida. precisa de abrigo pra eles', -23.4055, -51.9319, now() - interval '10 min'),

-- Oc 6: Eucalipto Av Colombo (9 relatos)
('0c200001-0006-4000-a000-000000000006', '5544999110030', 'João Batista', 'eucalipto caiu na colombo bloqueou TUDO. 3 faixas. ninguem passa', -23.4085, -51.9390, now() - interval '1 hour'),
('0c200001-0006-4000-a000-000000000006', '5544999110031', NULL, 'colombo parada total por arvore. desvio pelo contorno', -23.4086, -51.9388, now() - interval '55 min'),
('0c200001-0006-4000-a000-000000000006', '5544999110032', 'Simone Oliveira', 'congestionamento absurdo na colombo pq caiu eucalipto enorme', -23.4084, -51.9392, now() - interval '50 min'),
('0c200001-0006-4000-a000-000000000006', '5544999110033', 'Felipe Augusto', 'to parado ha 40min na colombo por causa da arvore, quando vem a prefeitura??', -23.4087, -51.9387, now() - interval '45 min'),
('0c200001-0006-4000-a000-000000000006', '5544999110034', 'Adriana Lima', 'eucalipto caiu e levou a fiacao eletrica junto. sem luz na regiao toda', -23.4083, -51.9393, now() - interval '40 min'),
('0c200001-0006-4000-a000-000000000006', '5544999110035', NULL, 'arvore enorme colombo 5200 ta um caos aqui', -23.4088, -51.9386, now() - interval '35 min'),
('0c200001-0006-4000-a000-000000000006', '5544999110036', 'Camila Rodrigues', 'a arvore q caiu na colombo pegou 2 carros estacionados. ninguem se machucou', -23.4082, -51.9394, now() - interval '30 min'),
('0c200001-0006-4000-a000-000000000006', '5544999110037', 'Anderson Ramos', 'PM ta aqui desviando o transito mas a arvore eh gigante vai demorar pra tirar', -23.4089, -51.9385, now() - interval '25 min'),
('0c200001-0006-4000-a000-000000000006', '5544999110038', 'Gabriela Santos', 'update colombo: congestionamento de 2km. usem rota alternativa pela herval', -23.4081, -51.9395, now() - interval '15 min'),

-- Oc 7: Alagamento Zona 5 (12 relatos)
('0c200001-0007-4000-a000-000000000007', '5544999120001', 'Dona Cida', 'a agua ta entrando na minha casa gente pelo amor de deus alguem ajuda', -23.4312, -51.9450, now() - interval '3 hours'),
('0c200001-0007-4000-a000-000000000007', '5544999120002', 'José Carlos', 'Rua das margaridas completamente alagada, agua na altura do joelho', -23.4313, -51.9448, now() - interval '2 hours 50 min'),
('0c200001-0007-4000-a000-000000000007', '5544999120003', NULL, 'alagamento forte zona 5 rua das margaridas carro nao passa', -23.4310, -51.9452, now() - interval '2 hours 40 min'),
('0c200001-0007-4000-a000-000000000007', '5544999120004', 'Luciana Ferreira', 'to com agua dentro de casa precisamos de ajuda urgente zona 5 margaridas', -23.4314, -51.9449, now() - interval '2 hours 30 min'),
('0c200001-0007-4000-a000-000000000007', '5544999120005', 'Pedro Henrique', 'O bueiro entupiu e a rua inteira alagou. Ta entrando agua nos comercios', -23.4311, -51.9451, now() - interval '2 hours 20 min'),
('0c200001-0007-4000-a000-000000000007', '5544999120006', 'Ana Beatriz', 'Minha vizinha idosa ta ilhada na casa dela rua das margaridas 380 precisa de resgate', -23.4315, -51.9447, now() - interval '2 hours 10 min'),
('0c200001-0007-4000-a000-000000000007', '5544999120007', NULL, 'alagamento zona 5 agua subindo rapido', -23.4309, -51.9453, now() - interval '2 hours'),
('0c200001-0007-4000-a000-000000000007', '5544999120008', 'Marcos Paulo', 'Tem criança presa numa casa aqui na rua das margaridas a agua ta quase 1 metro', -23.4316, -51.9446, now() - interval '1 hour 50 min'),
('0c200001-0007-4000-a000-000000000007', '5544999120009', 'Sandra Melo', 'Perdi tudo dentro de casa a agua entrou e levou os moveis. Rua margaridas zona 5', -23.4313, -51.9450, now() - interval '1 hour 40 min'),
('0c200001-0007-4000-a000-000000000007', '5544999120010', NULL, 'moro na margaridas 500 a agua ta baixando mas tem muito lixo e lama agr', -23.4310, -51.9454, now() - interval '1 hour 20 min'),
('0c200001-0007-4000-a000-000000000007', '5544999120011', 'Ricardo Souza', 'Ja ligamos pro bombeiro e defesa civil mas ninguem apareceu. Margaridas zona 5 alagada', -23.4317, -51.9445, now() - interval '1 hour'),
('0c200001-0007-4000-a000-000000000007', '5544999120012', 'Camila Rodrigues', 'A rua das margaridas virou um rio!! Tem gente pedindo socorro das janelas', -23.4308, -51.9455, now() - interval '45 min'),

-- Oc 10: Córrego transbordou Mandacaru (8 relatos)
('0c200001-0010-4000-a000-000000000010', '5544999120030', 'Leandro Silva', 'o corrego mandacaru transbordou agua ta invadindo as casas da beira', -23.4358, -51.9485, now() - interval '1 hour 30 min'),
('0c200001-0010-4000-a000-000000000010', '5544999120031', NULL, 'enchente mandacaru ta horrivel agua no meio da rua', -23.4360, -51.9483, now() - interval '1 hour 20 min'),
('0c200001-0010-4000-a000-000000000010', '5544999120032', 'Priscila Nunes', 'minha casa ta alagando pelo quintal vem do corrego mandacaru 400', -23.4356, -51.9487, now() - interval '1 hour 10 min'),
('0c200001-0010-4000-a000-000000000010', '5544999120033', 'Douglas Ferreira', 'familias precisam de abrigo aqui no mandacaru as casas estao alagadas', -23.4362, -51.9481, now() - interval '1 hour'),
('0c200001-0010-4000-a000-000000000010', '5544999120034', 'Vanessa Costa', 'tem bebe e idoso aqui precisamos de resgate no mandacaru urgente', -23.4354, -51.9489, now() - interval '50 min'),
('0c200001-0010-4000-a000-000000000010', '5544999120035', NULL, 'corrego mandacaru saiu do leito completamente. situacao critica', -23.4364, -51.9479, now() - interval '40 min'),
('0c200001-0010-4000-a000-000000000010', '5544999120036', 'Roberto Dias', 'defesa civil precisa vir pro mandacaru AGORA. tem gente ilhada', -23.4352, -51.9491, now() - interval '30 min'),
('0c200001-0010-4000-a000-000000000010', '5544999120037', 'Aline Martins', 'update: agua ta baixando mas muita casa destruida. vamos precisar de ajuda', -23.4366, -51.9477, now() - interval '15 min'),

-- Oc 24: Incêndio galpão Zona 7 (7 relatos)
('0c200001-0024-4000-a000-000000000024', '5544999150010', 'Henrique Alves', 'galpao pegando fogo na rua bahia zona 7!! fumaca preta enorme', -23.4138, -51.9270, now() - interval '30 min'),
('0c200001-0024-4000-a000-000000000024', '5544999150011', NULL, 'incendio no galpao abandonado bahia 1100 fogo muito alto', -23.4140, -51.9268, now() - interval '28 min'),
('0c200001-0024-4000-a000-000000000024', '5544999150012', 'Tatiane Mendes', 'o galpao ta desabando com o fogo!! evacua as casas em volta pelo amor de deus', -23.4136, -51.9272, now() - interval '25 min'),
('0c200001-0024-4000-a000-000000000024', '5544999150013', 'Vinícius Santos', 'nao da pra respirar aqui perto do galpao. fumaca toxica. crianças passando mal', -23.4142, -51.9266, now() - interval '22 min'),
('0c200001-0024-4000-a000-000000000024', '5544999150014', 'Amanda Ribeiro', 'bombeiros chegaram mas o fogo ta muito forte. pedem pra todo mundo sair da area', -23.4134, -51.9274, now() - interval '18 min'),
('0c200001-0024-4000-a000-000000000024', '5544999150015', NULL, 'incendio galpao bahia zona 7 segundo andar desabou', -23.4144, -51.9264, now() - interval '12 min'),
('0c200001-0024-4000-a000-000000000024', '5544999150016', 'Renan Oliveira', 'parece q tinha material inflamavel dentro do galpao. explosao pequena agora a pouco', -23.4132, -51.9276, now() - interval '5 min'),

-- Oc 30: Acidente grave Colombo (6 relatos)
('0c200001-0030-4000-a000-000000000030', '5544999170010', 'Beatriz Lima', 'acidente grave na colombo 4800!! carro bateu de frente com caminhonete', -23.4092, -51.9382, now() - interval '50 min'),
('0c200001-0030-4000-a000-000000000030', '5544999170011', NULL, 'batida forte colombo zona 7 tem gente machucada samu ja vem?', -23.4094, -51.9380, now() - interval '45 min'),
('0c200001-0030-4000-a000-000000000030', '5544999170012', 'Cristiane Souza', 'acidente colombo 4800 parece q o motorista do carro ta inconsciente', -23.4090, -51.9384, now() - interval '42 min'),
('0c200001-0030-4000-a000-000000000030', '5544999170013', 'Rafael Oliveira', 'samu chegou no acidente da colombo. 2 ambulancias. transito parado', -23.4096, -51.9378, now() - interval '35 min'),
('0c200001-0030-4000-a000-000000000030', '5544999170014', 'Eliane Souza', 'pm ta desviando o transito na colombo pq tem acidente grave com vitimas', -23.4088, -51.9386, now() - interval '30 min'),
('0c200001-0030-4000-a000-000000000030', '5544999170015', NULL, 'acidente colombo zona 7 carro destruido. orem pelas vitimas', -23.4098, -51.9376, now() - interval '25 min'),

-- Oc 33: Capotamento Morangueira (5 relatos)
('0c200001-0033-4000-a000-000000000033', '5544999170020', 'Fábio Augusto', 'carro capotou na morangueira!! motorista preso nas ferragens', -23.4072, -51.9302, now() - interval '25 min'),
('0c200001-0033-4000-a000-000000000033', '5544999170021', 'Isabela Costa', 'capotamento morangueira 2200 precisa de bombeiro pra tirar a pessoa do carro', -23.4074, -51.9300, now() - interval '22 min'),
('0c200001-0033-4000-a000-000000000033', '5544999170022', NULL, 'acidente morangueira carro virou de cabeca pra baixo', -23.4070, -51.9304, now() - interval '18 min'),
('0c200001-0033-4000-a000-000000000033', '5544999170023', 'Luciano Ramos', 'bombeiros cortando o carro pra tirar o motorista. samu esperando', -23.4076, -51.9298, now() - interval '12 min'),
('0c200001-0033-4000-a000-000000000033', '5544999170024', 'Débora Ferreira', 'motorista retirado com vida do capotamento da morangueira. sendo levado pro HUM', -23.4068, -51.9306, now() - interval '5 min'),

-- Oc 37: Deslizamento Mandacaru (5 relatos)
('0c200001-0037-4000-a000-000000000037', '5544999180010', 'Alexandre Lima', 'barranco cedeu na mandacaru 1000!! terra na rua toda', -23.4355, -51.9488, now() - interval '2 hours'),
('0c200001-0037-4000-a000-000000000037', '5544999180011', NULL, 'deslizamento de terra mandacaru bloqueou a rua', -23.4357, -51.9486, now() - interval '1 hour 50 min'),
('0c200001-0037-4000-a000-000000000037', '5544999180012', 'Silvana Martins', 'as casas perto do barranco estao em risco. rachaduras no muro. mandacaru 1000', -23.4353, -51.9490, now() - interval '1 hour 30 min'),
('0c200001-0037-4000-a000-000000000037', '5544999180013', 'Márcio Almeida', 'a terra continua descendo. se chover mais vai ser pior. evacuem as casas da mandacaru', -23.4359, -51.9484, now() - interval '1 hour'),
('0c200001-0037-4000-a000-000000000037', '5544999180014', 'Gabriela Santos', 'defesa civil veio avaliar o deslizamento da mandacaru. 3 casas interditadas', -23.4351, -51.9492, now() - interval '30 min'),

-- Oc 40: Vazamento de gás Zona 3 (4 relatos)
('0c200001-0040-4000-a000-000000000040', '5544999190001', 'Paulo Roberto', 'cheiro forte de gas na rua rio branco zona 3!! pode explodir', -23.4285, -51.9365, now() - interval '20 min'),
('0c200001-0040-4000-a000-000000000040', '5544999190002', NULL, 'vazamento de gas rio branco 300 evacuem a area!!', -23.4287, -51.9363, now() - interval '18 min'),
('0c200001-0040-4000-a000-000000000040', '5544999190003', 'Ana Carolina', 'bombeiros mandaram todo mundo sair das casas. cheiro de gas muito forte zona 3', -23.4283, -51.9367, now() - interval '14 min'),
('0c200001-0040-4000-a000-000000000040', '5544999190004', 'Antônio Carlos', 'compagas chegou no vazamento da rio branco. area isolada em 200 metros', -23.4289, -51.9361, now() - interval '8 min');


-- ============================================================
-- ============================================================
--              S O S   M U L H E R
--     8 cadastros + 2 alertas ativos + 4 histórico
-- ============================================================
-- ============================================================

INSERT INTO sos_cadastros (id, telefone, nome, endereco, referencia, agressor, contato_confianca_nome, contato_confianca_telefone) VALUES
('50500d01-0001-4000-a000-000000000001', '5544977050001', 'Maria Silva', 'Rua das Acácias, 120 - Jardim Alvorada', 'Em frente ao mercadinho do João', 'João Carlos Silva (ex-marido)', 'Mãe - Dona Cida', '5544966010001'),
('50500d01-0002-4000-a000-000000000002', '5544977050002', 'Joana Ferreira', 'Av. Morangueira, 3400, ap 22 - Zona 7', 'Prédio azul ao lado do banco', 'Pedro Ferreira (companheiro)', 'Irmã - Paula', '5544966010002'),
('50500d01-0003-4000-a000-000000000003', '5544977050003', 'Lucia Santos', 'Rua Pioneiro, 55 - Nova Esperança', 'Casa amarela com portão de ferro', 'Marcos Antônio Santos (ex-namorado)', 'Vizinha - Marta', '5544966010003'),
('50500d01-0004-4000-a000-000000000004', '5544977050004', 'Ana Beatriz Oliveira', 'Rua Guaporé, 200 - Vila Morangueira', 'Esquina com a padaria Pão Quente', 'Ricardo Oliveira (marido)', 'Amiga - Carla', '5544966010004'),
('50500d01-0005-4000-a000-000000000005', '5544977050005', 'Patrícia Almeida', 'Rua Rio Branco, 700 - Zona 3', 'Próximo ao posto Shell', 'Fernando Almeida (ex-marido)', 'Mãe - Dona Rosa', '5544966010005'),
('50500d01-0006-4000-a000-000000000006', '5544977050006', 'Camila Rodrigues', 'Rua Itororó, 400 - Vila Operária', 'Casa com muro branco', 'Diego Rodrigues (companheiro)', 'Irmã - Juliana', '5544966010006'),
('50500d01-0007-4000-a000-000000000007', '5544977050007', 'Fernanda Costa', 'Rua Santos Dumont, 900 - Zona 2', 'Ao lado do salão de beleza', 'Marcelo Costa (ex-namorado)', 'Amiga - Bruna', '5544966010007'),
('50500d01-0008-4000-a000-000000000008', '5544977050008', 'Roberta Mendes', 'Avenida Cerro Azul, 400 - Zona 4', 'Prédio com portaria 24h', 'Carlos Mendes (marido)', 'Mãe - Dona Teresa', '5544966010008');

-- Alertas ATIVOS (fazem o dashboard ficar vermelho!)
INSERT INTO sos_alertas (cadastro_id, telefone, codigo_usado, status, latitude, longitude, token_rastreamento, created_at) VALUES
('50500d01-0001-4000-a000-000000000001', '5544977050001', '.', 'active', -23.4420, -51.9200, 'demo_tk_01', now() - interval '3 minutes'),
('50500d01-0004-4000-a000-000000000004', '5544977050004', '.', 'active', -23.4055, -51.9318, 'demo_tk_04', now() - interval '8 minutes');

-- Alertas em atendimento
INSERT INTO sos_alertas (cadastro_id, telefone, codigo_usado, status, latitude, longitude, atendido_por, created_at) VALUES
('50500d01-0006-4000-a000-000000000006', '5544977050006', '.', 'attending', -23.4335, -51.9240, 'Patrulha Maria da Penha #02', now() - interval '25 minutes');

-- Alertas resolvidos (histórico)
INSERT INTO sos_alertas (cadastro_id, telefone, codigo_usado, status, latitude, longitude, resolvido_em, atendido_por, notas, created_at) VALUES
('50500d01-0002-4000-a000-000000000002', '5544977050002', '.', 'resolved', -23.4156, -51.9280, now() - interval '2 days', 'Patrulha Maria da Penha #03', 'Vítima acolhida. Medida protetiva solicitada. Agressor não estava no local.', now() - interval '2 days 15 minutes'),
('50500d01-0003-4000-a000-000000000003', '5544977050003', '.', 'resolved', -23.4100, -51.9155, now() - interval '5 days', 'Patrulha Maria da Penha #01', 'Agressor detido em flagrante. Vítima encaminhada à Casa da Mulher.', now() - interval '5 days 30 minutes'),
('50500d01-0005-4000-a000-000000000005', '5544977050005', '.', 'resolved', -23.4278, -51.9375, now() - interval '8 days', 'GM #12', 'Falso alarme. Vítima acionou por engano. Situação verificada e estável.', now() - interval '8 days 10 minutes'),
('50500d01-0007-4000-a000-000000000007', '5544977050007', '.', 'resolved', -23.4252, -51.9505, now() - interval '12 days', 'Patrulha Maria da Penha #03', 'Agressor tentou invadir residência. PM acionada. Boletim registrado.', now() - interval '12 days 20 minutes');


-- ============================================================
-- ============================================================
--                  F E E D B A C K S
--         25 feedbacks variados (elogios, reclamações, sugestões)
-- ============================================================
-- ============================================================

INSERT INTO feedbacks (protocolo, telefone, nome, categoria, sentimento, urgencia, mensagem, resumo, bairro, status, created_at) VALUES
-- Elogios (8)
('MGA-2026-00701', '5544988020001', 'Dona Terezinha', 'elogio', 'positivo', 'normal', 'Quero parabenizar a equipe que veio limpar a praça do bairro! Ficou lindo, obrigada prefeitura', 'Elogio à equipe de limpeza da praça', 'Jardim Alvorada', 'lido', now() - interval '25 days'),
('MGA-2026-00702', '5544988020002', 'Carla Mendes', 'elogio', 'positivo', 'normal', 'Parabéns pelo app de denúncia!! Denunciei uma pichação e em 2 dias já tinham pintado o muro. Sistema muito bom', 'Elogio ao sistema de denúncias', 'Zona 7', 'lido', now() - interval '20 days'),
('MGA-2026-00703', '5544988020003', 'Ricardo Souza', 'elogio', 'positivo', 'normal', 'A iluminação nova da Av. Colombo ficou excelente! Agora dá pra caminhar à noite com segurança', 'Elogio à nova iluminação pública', 'Zona 7', 'novo', now() - interval '15 days'),
('MGA-2026-00704', '5544988020004', 'Ana Beatriz', 'elogio', 'positivo', 'normal', 'Quero elogiar a patrulha Maria da Penha. Atendimento rápido e acolhedor. Salvaram minha vida', 'Elogio à Patrulha Maria da Penha', 'Vila Morangueira', 'lido', now() - interval '10 days'),
('MGA-2026-00705', '5544988020005', 'Fernando Dias', 'elogio', 'positivo', 'normal', 'A operação tapa-buracos passou aqui na zona 3 e ficou perfeito! Rua lisa de novo', 'Elogio à operação tapa-buracos', 'Zona 3', 'novo', now() - interval '7 days'),
('MGA-2026-00706', '5544988020006', 'Juliana Costa', 'elogio', 'positivo', 'normal', 'Esse sistema de denúncia por WhatsApp é genial. Muito mais prático que ir na delegacia', 'Elogio ao canal WhatsApp', 'Centro', 'novo', now() - interval '4 days'),
('MGA-2026-00707', '5544988020007', 'Marcos Oliveira', 'elogio', 'positivo', 'normal', 'Recebi a recompensa do programa Cidadão Ativo em 3 dias! Excelente iniciativa', 'Elogio ao programa de recompensas', 'Zona 7', 'lido', now() - interval '2 days'),
('MGA-2026-00708', '5544988020008', 'Patrícia Almeida', 'elogio', 'positivo', 'normal', 'O novo parque ficou incrível! Meus filhos amaram. Obrigada prefeitura de Maringá', 'Elogio ao novo parque', 'Nova Esperança', 'novo', now() - interval '1 day'),

-- Reclamações (10)
('MGA-2026-00709', '5544988020009', NULL, 'reclamacao', 'negativo', 'alta', 'O ônibus da linha 22 tá sempre atrasado de manhã. Chego atrasada no trabalho todo dia por causa disso', 'Reclamação sobre atraso do ônibus linha 22', 'Zona 7', 'novo', now() - interval '22 days'),
('MGA-2026-00710', '5544988020010', 'José Carlos', 'reclamacao', 'negativo', 'alta', 'Faz 3 semanas que abri protocolo sobre o buraco e ninguém veio resolver. Descaso total', 'Reclamação sobre buraco não resolvido', 'Zona 3', 'em_analise', now() - interval '18 days'),
('MGA-2026-00711', '5544988020011', 'Sandra Melo', 'reclamacao', 'negativo', 'normal', 'UBS do bairro só tem 1 médico pra atender 500 pessoas. Espera de 4 horas', 'Reclamação sobre falta de médicos na UBS', 'Jardim Alvorada', 'novo', now() - interval '16 days'),
('MGA-2026-00712', '5544988020012', NULL, 'reclamacao', 'negativo', 'alta', 'Rua sem coleta de lixo há 10 dias. Lixo acumulado atraindo ratos e baratas', 'Reclamação sobre falta de coleta de lixo', 'Vila Operária', 'encaminhado', now() - interval '13 days'),
('MGA-2026-00713', '5544988020013', 'Rogério Lima', 'reclamacao', 'negativo', 'normal', 'Calçada da Av. Brasil quebrada e irregular. Cadeirante não consegue passar', 'Reclamação sobre acessibilidade da calçada', 'Centro', 'novo', now() - interval '11 days'),
('MGA-2026-00714', '5544988020014', 'Simone Oliveira', 'reclamacao', 'negativo', 'alta', 'Poda de árvore foi pedida há 2 meses. Galhos ameaçam cair sobre fiação elétrica', 'Reclamação sobre poda não realizada', 'Vila Morangueira', 'em_analise', now() - interval '8 days'),
('MGA-2026-00715', '5544988020015', NULL, 'reclamacao', 'negativo', 'normal', 'Praça do bairro abandonada. Mato alto, lixo, sem iluminação. Virou ponto de drogas', 'Reclamação sobre praça abandonada', 'Mandacaru', 'novo', now() - interval '6 days'),
('MGA-2026-00716', '5544988020016', 'Adriana Lima', 'reclamacao', 'negativo', 'alta', 'Meu vizinho faz queimada todo fim de semana e a fiscalização nunca vem', 'Reclamação sobre queimadas não fiscalizadas', 'Zona 5', 'novo', now() - interval '3 days'),
('MGA-2026-00717', '5544988020017', 'Thiago Martins', 'reclamacao', 'negativo', 'normal', 'Semáforo da Colombo com Paranaguá tá com defeito há 1 mês. Acidentes toda semana', 'Reclamação sobre semáforo com defeito', 'Zona 7', 'encaminhado', now() - interval '1 day'),
('MGA-2026-00718', '5544988020018', 'Dona Cida', 'reclamacao', 'negativo', 'alta', 'Vazamento de água na rua há 15 dias. Desperdício absurdo. Sanepar não resolve', 'Reclamação sobre vazamento de água', 'Zona 2', 'novo', now() - interval '5 hours'),

-- Sugestões (7)
('MGA-2026-00719', '5544988020019', 'Pedro Augusto', 'sugestao', 'neutro', 'normal', 'Seria bom colocar mais lixeiras na av colombo perto da uem. Os alunos jogam lixo no chao pq nao tem lixeira', 'Sugestão de lixeiras na Av. Colombo', 'Zona 7', 'novo', now() - interval '19 days'),
('MGA-2026-00720', '5544988020020', 'Gabriela Santos', 'sugestao', 'neutro', 'normal', 'Poderiam instalar câmeras de segurança na praça. Toda semana tem vandalismo', 'Sugestão de câmeras na praça', 'Jardim Alvorada', 'lido', now() - interval '14 days'),
('MGA-2026-00721', '5544988020021', 'Felipe Augusto', 'sugestao', 'neutro', 'normal', 'Criar ciclovia na Av. Morangueira. Muitos ciclistas e nenhuma infraestrutura', 'Sugestão de ciclovia na Av. Morangueira', 'Vila Morangueira', 'novo', now() - interval '9 days'),
('MGA-2026-00722', '5544988020022', 'Maria Eduarda', 'sugestao', 'neutro', 'normal', 'Ampliar o horário de funcionamento da UBS para atendimento noturno', 'Sugestão de UBS noturna', 'Vila Operária', 'novo', now() - interval '5 days'),
('MGA-2026-00723', '5544988020023', 'Anderson Ramos', 'sugestao', 'positivo', 'normal', 'O programa Cidadão Ativo deveria incluir denúncia de som alto. Vizinho toca música até 4h da manhã', 'Sugestão de nova categoria no programa', 'Zona 7', 'lido', now() - interval '3 days'),
('MGA-2026-00724', '5544988020024', 'Camila Rodrigues', 'sugestao', 'neutro', 'normal', 'Colocar radar de velocidade na Av. Colombo. Carros passam a 100km/h. Já houve mortes', 'Sugestão de radar na Av. Colombo', 'Zona 7', 'novo', now() - interval '1 day'),
('MGA-2026-00725', '5544988020025', 'Leandro Silva', 'sugestao', 'positivo', 'normal', 'Ampliar o programa SOS Mulher pra todas as delegacias da mulher do estado. Maringá é exemplo!', 'Sugestão de expansão do SOS Mulher', 'Centro', 'lido', now() - interval '6 hours');


-- ============================================================
-- ============================================================
--              R E C O M P E N S A S
--     20 recompensas em diferentes status
-- ============================================================
-- ============================================================

-- PAGAS (6)
INSERT INTO recompensas (denuncia_id, protocolo, status, valor, cpf_encrypted, chave_pix_encrypted, tipo_chave_pix, validado_por, validado_em, pago_por, pago_em, numero_empenho, dotacao_orcamentaria, created_at) VALUES
('d0010001-0026-4000-a000-000000000026', 'MGA-2026-00526', 'paga', 100.00, 'ENC_AES256_demo_cpf_marcos', 'ENC_AES256_demo_pix_marcos', 'cpf', 'Op. Silva', now() - interval '22 days', 'Fin. Santos', now() - interval '20 days', 'EMP-2026-00412', 'DOT-15.452.0045.2.048', now() - interval '26 days'),
('d0010001-0028-4000-a000-000000000028', 'MGA-2026-00528', 'paga', 100.00, 'ENC_AES256_demo_cpf_jose', 'ENC_AES256_demo_pix_jose', 'cpf', 'Op. Costa', now() - interval '17 days', 'Fin. Santos', now() - interval '15 days', 'EMP-2026-00413', 'DOT-15.452.0045.2.048', now() - interval '21 days'),
('d0010001-0041-4000-a000-000000000041', 'MGA-2026-00541', 'paga', 80.00, 'ENC_AES256_demo_cpf_sandra', 'ENC_AES256_demo_pix_sandra', 'email', 'Op. Silva', now() - interval '22 days', 'Fin. Oliveira', now() - interval '20 days', 'EMP-2026-00414', 'DOT-15.452.0045.2.048', now() - interval '26 days'),
('d0010001-0047-4000-a000-000000000047', 'MGA-2026-00547', 'paga', 80.00, 'ENC_AES256_demo_cpf_carlos_e', 'ENC_AES256_demo_pix_carlos_e', 'telefone', 'Op. Costa', now() - interval '10 days', 'Fin. Santos', now() - interval '8 days', 'EMP-2026-00415', 'DOT-15.452.0045.2.048', now() - interval '14 days'),
('d0010001-0057-4000-a000-000000000057', 'MGA-2026-00557', 'paga', 150.00, 'ENC_AES256_demo_cpf_simone', 'ENC_AES256_demo_pix_simone', 'cpf', 'Op. Silva', now() - interval '19 days', 'Fin. Oliveira', now() - interval '17 days', 'EMP-2026-00416', 'DOT-15.452.0045.2.048', now() - interval '23 days'),
('d0010001-0068-4000-a000-000000000068', 'MGA-2026-00568', 'paga', 150.00, 'ENC_AES256_demo_cpf_eliane', 'ENC_AES256_demo_pix_eliane', 'aleatoria', 'Op. Costa', now() - interval '16 days', 'Fin. Santos', now() - interval '14 days', 'EMP-2026-00417', 'DOT-15.452.0045.2.048', now() - interval '20 days');

-- AGUARDANDO PAGAMENTO (4)
INSERT INTO recompensas (denuncia_id, protocolo, status, valor, cpf_encrypted, chave_pix_encrypted, tipo_chave_pix, validado_por, validado_em, created_at) VALUES
('d0010001-0004-4000-a000-000000000004', 'MGA-2026-00504', 'aguardando_pagamento', 300.00, 'ENC_AES256_demo_cpf_anon4', 'ENC_AES256_demo_pix_anon4', 'cpf', 'Op. Silva', now() - interval '18 days', now() - interval '22 days'),
('d0010001-0009-4000-a000-000000000009', 'MGA-2026-00509', 'aguardando_pagamento', 300.00, 'ENC_AES256_demo_cpf_anon9', 'ENC_AES256_demo_pix_anon9', 'telefone', 'Op. Costa', now() - interval '8 days', now() - interval '12 days'),
('d0010001-0044-4000-a000-000000000044', 'MGA-2026-00544', 'aguardando_pagamento', 80.00, 'ENC_AES256_demo_cpf_rodrigo', 'ENC_AES256_demo_pix_rodrigo', 'email', 'Op. Silva', now() - interval '16 days', now() - interval '20 days'),
('d0010001-0049-4000-a000-000000000049', 'MGA-2026-00549', 'aguardando_pagamento', 80.00, 'ENC_AES256_demo_cpf_felipe', 'ENC_AES256_demo_pix_felipe', 'cpf', 'Op. Costa', now() - interval '6 days', now() - interval '10 days');

-- VALIDADAS (3)
INSERT INTO recompensas (denuncia_id, protocolo, status, valor, cpf_encrypted, chave_pix_encrypted, tipo_chave_pix, validado_por, validado_em, created_at) VALUES
('d0010001-0013-4000-a000-000000000013', 'MGA-2026-00513', 'validada', 300.00, 'ENC_AES256_demo_cpf_anon13', 'ENC_AES256_demo_pix_anon13', 'cpf', 'Op. Silva', now() - interval '4 days', now() - interval '8 days'),
('d0010001-0021-4000-a000-000000000021', 'MGA-2026-00521', 'validada', 300.00, 'ENC_AES256_demo_cpf_anon21', 'ENC_AES256_demo_pix_anon21', 'telefone', 'Op. Costa', now() - interval '15 days', now() - interval '19 days'),
('d0010001-0059-4000-a000-000000000059', 'MGA-2026-00559', 'validada', 150.00, 'ENC_AES256_demo_cpf_vanessa', 'ENC_AES256_demo_pix_vanessa', 'cpf', 'Op. Silva', now() - interval '15 days', now() - interval '19 days');

-- PENDENTE VALIDAÇÃO (5)
INSERT INTO recompensas (denuncia_id, protocolo, status, valor, created_at) VALUES
('d0010001-0030-4000-a000-000000000030', 'MGA-2026-00530', 'pendente_validacao', 100.00, now() - interval '17 days'),
('d0010001-0033-4000-a000-000000000033', 'MGA-2026-00533', 'pendente_validacao', 100.00, now() - interval '11 days'),
('d0010001-0040-4000-a000-000000000040', 'MGA-2026-00540', 'pendente_validacao', 100.00, now() - interval '14 days'),
('d0010001-0063-4000-a000-000000000063', 'MGA-2026-00563', 'pendente_validacao', 150.00, now() - interval '7 days'),
('d0010001-0070-4000-a000-000000000070', 'MGA-2026-00570', 'pendente_validacao', 150.00, now() - interval '15 days');

-- REJEITADAS (2)
INSERT INTO recompensas (denuncia_id, protocolo, status, valor, cpf_encrypted, chave_pix_encrypted, tipo_chave_pix, validado_por, validado_em, motivo_rejeicao, created_at) VALUES
('d0010001-0031-4000-a000-000000000031', 'MGA-2026-00531', 'rejeitada', 100.00, 'ENC_AES256_demo_cpf_maria_e', 'ENC_AES256_demo_pix_maria_e', 'cpf', 'Op. Costa', now() - interval '11 days', 'Foto não corresponde ao local informado. Possível denúncia duplicada.', now() - interval '15 days'),
('d0010001-0045-4000-a000-000000000045', 'MGA-2026-00545', 'rejeitada', 80.00, NULL, NULL, NULL, 'Op. Silva', now() - interval '14 days', 'Denúncia anônima sem evidência fotográfica. Não foi possível verificar no local.', now() - interval '18 days');


-- ============================================================
-- FIM DO MEGA SEED
-- Totais:
--   80 denúncias (25 tráfico, 15 pichação, 15 lixo, 10 furto_fios, 15 depredação)
--   40 ocorrências com ~80 relatos
--   25 feedbacks (8 elogios, 10 reclamações, 7 sugestões)
--   8 cadastros SOS + 2 ativos + 1 atendendo + 4 resolvidos
--   20 recompensas (6 pagas, 4 aguardando, 3 validadas, 5 pendentes, 2 rejeitadas)
-- ============================================================
