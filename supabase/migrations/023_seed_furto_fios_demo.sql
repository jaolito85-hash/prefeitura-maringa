-- ============================================================
-- NODE DATA MARINGÁ — Migration 023: Seed extra FURTO DE FIOS
-- Adiciona 14 denúncias de furto de fios e cabos elétricos
-- espalhadas em bairros reais de Maringá, com coordenadas reais
-- e datas variadas nos últimos 30 dias.
--
-- IDEMPOTENTE: usa ON CONFLICT (protocolo) DO NOTHING.
-- Pode rodar várias vezes sem duplicar.
-- ============================================================

INSERT INTO denuncias (
  id, protocolo, telefone, nome, categoria, mensagem,
  bairro, endereco, latitude, longitude,
  cidadania_ativa, status, valor_recompensa, midia_urls, created_at
) VALUES

-- Vila Operária
('d0023001-0001-4000-a000-000000000701', 'MGA-2026-00701', '5544999900701', 'Carlos Henrique', 'furto_fios',
 'Furtaram cabos da rede elétrica do quarteirão inteiro durante a madrugada. Bairro ficou sem energia por mais de 12 horas.',
 'Vila Operária', 'Rua Pioneiro Alcides Batista, 320 - Vila Operária', -23.4138, -51.9425,
 true, 'procedente', 150.00, ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=FURTO+CABOS']::TEXT[], now() - interval '29 days'),

-- Mandacaru
('d0023001-0002-4000-a000-000000000702', 'MGA-2026-00702', '5544999900702', 'Juliana Martins', 'furto_fios',
 'Vi uma Kombi branca parada perto do poste às 2h da manhã. Quando amanheceu, todo o cabo de cobre tinha sumido.',
 'Mandacaru', 'Rua Cesário Anhaia, 1100 - Mandacaru', -23.4521, -51.9082,
 true, 'em_analise', NULL, ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=KOMBI+SUSPEITA']::TEXT[], now() - interval '26 days'),

-- Jardim Universitário
('d0023001-0003-4000-a000-000000000703', 'MGA-2026-00703', '5544999900703', NULL, 'furto_fios',
 'Furtaram fios de iluminação pública em frente à creche municipal. Crianças saem no escuro.',
 'Jardim Universitário', 'Rua Reverendo João da Silva Martins, 540 - Jardim Universitário', -23.4258, -51.9447,
 false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '24 days'),

-- Zona 4
('d0023001-0004-4000-a000-000000000704', 'MGA-2026-00704', '5544999900704', 'Roberto Almeida', 'furto_fios',
 'Cabos de telefonia da rua inteira foram cortados e levados. Vizinhos sem internet há 3 dias.',
 'Zona 4', 'Rua Mato Grosso, 880 - Zona 4', -23.4348, -51.9272,
 true, 'encaminhado', NULL, ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=CABOS+TELEFONIA']::TEXT[], now() - interval '22 days'),

-- Zona 2
('d0023001-0005-4000-a000-000000000705', 'MGA-2026-00705', '5544999900705', 'Mariana Costa', 'furto_fios',
 'Levaram os cabos do transformador do poste. Ficamos sem luz das 23h até as 9h da manhã. Idoso na rua precisou de oxigênio.',
 'Zona 2', 'Avenida Tiradentes, 720 - Zona 2', -23.4055, -51.9408,
 true, 'recompensa_paga', 150.00, ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=POSTE+SEM+CABOS']::TEXT[], now() - interval '20 days'),

-- Jardim Imperial
('d0023001-0006-4000-a000-000000000706', 'MGA-2026-00706', '5544999900706', NULL, 'furto_fios',
 'Cortaram fios da iluminação da quadra de esporte do bairro. Jovens não jogam mais à noite.',
 'Jardim Imperial', 'Rua Genuíno Ferreira da Silva, 240 - Jardim Imperial', -23.4488, -51.9322,
 false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '18 days'),

-- Parque das Grevíleas
('d0023001-0007-4000-a000-000000000707', 'MGA-2026-00707', '5544999900707', 'Fernanda Lopes', 'furto_fios',
 'Carro Uno azul para no poste de madrugada e dois homens cortam os cabos com alicatão. Já vi 3 vezes esse mês.',
 'Parque das Grevíleas', 'Rua Pioneiro José de Lima, 80 - Parque das Grevíleas', -23.4180, -51.8952,
 true, 'em_analise', NULL, ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=UNO+SUSPEITO']::TEXT[], now() - interval '16 days'),

-- Conjunto Inocente Vila Nova Júnior
('d0023001-0008-4000-a000-000000000708', 'MGA-2026-00708', '5544999900708', 'Edson Pereira', 'furto_fios',
 'Furtaram cabos da subestação durante o feriado. Mais de 40 famílias ficaram sem luz no calor.',
 'Conjunto Inocente Vila Nova', 'Rua Pioneiro Tomás Penatti, 510 - Inocente Vila Nova', -23.4598, -51.9180,
 true, 'procedente', 150.00, ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=SUBESTACAO']::TEXT[], now() - interval '14 days'),

-- Vila Esperança
('d0023001-0009-4000-a000-000000000709', 'MGA-2026-00709', '5544999900709', NULL, 'furto_fios',
 'Reincidência de furto: já é a quarta vez que furtam os cabos da mesma rua nesse mês. Câmera do mercadinho gravou.',
 'Vila Esperança', 'Rua Marabá, 305 - Vila Esperança', -23.4212, -51.9531,
 false, 'encaminhado', NULL, ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=CAMERA+MERCADO']::TEXT[], now() - interval '12 days'),

-- Jardim Tropical
('d0023001-0010-4000-a000-000000000710', 'MGA-2026-00710', '5544999900710', 'Letícia Souza', 'furto_fios',
 'Furtaram fios da escola estadual durante o final de semana. Aulas suspensas na segunda-feira.',
 'Jardim Tropical', 'Rua Petrolina, 1450 - Jardim Tropical', -23.4395, -51.9522,
 true, 'novo', NULL, ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=ESCOLA+ESTADUAL']::TEXT[], now() - interval '10 days'),

-- Conjunto Cidade Alta
('d0023001-0011-4000-a000-000000000711', 'MGA-2026-00711', '5544999900711', 'Paulo Vinícius', 'furto_fios',
 'Vi um homem de capuz mexendo no poste com escada de madeira às 4h. Quando notou que eu olhei, fugiu correndo.',
 'Cidade Alta', 'Rua Joubert de Carvalho c/ Av. Cerro Azul - Cidade Alta', -23.3958, -51.9285,
 true, 'em_analise', NULL, ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=ESCADA+MADEIRA']::TEXT[], now() - interval '9 days'),

-- Jardim Liberdade
('d0023001-0012-4000-a000-000000000712', 'MGA-2026-00712', '5544999900712', NULL, 'furto_fios',
 'Iluminação do parquinho infantil furtada. Crianças não podem brincar no fim da tarde.',
 'Jardim Liberdade', 'Rua Pioneiro Antônio Pavin, 90 - Jardim Liberdade', -23.4675, -51.9362,
 false, 'novo', NULL, ARRAY[]::TEXT[], now() - interval '7 days'),

-- Vila Bosque
('d0023001-0013-4000-a000-000000000713', 'MGA-2026-00713', '5544999900713', 'Aline Rodrigues', 'furto_fios',
 'Cortaram fios do semáforo do cruzamento perigoso. Já houve 2 acidentes esta semana por causa disso.',
 'Vila Bosque', 'Avenida Brasil c/ Rua Santos Dumont - Vila Bosque', -23.3985, -51.9572,
 true, 'procedente', 150.00, ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=SEMAFORO+SEM+FIO']::TEXT[], now() - interval '5 days'),

-- Jardim Aclimação
('d0023001-0014-4000-a000-000000000714', 'MGA-2026-00714', '5544999900714', 'Wagner Fonseca', 'furto_fios',
 'Câmera de segurança gravou: três homens em moto preta cortaram cabo de fibra ótica. Posso enviar o vídeo.',
 'Jardim Aclimação', 'Rua Joaquim Nabuco, 1820 - Jardim Aclimação', -23.4262, -51.9182,
 true, 'encaminhado', NULL, ARRAY['https://placehold.co/400x300/1a1a2e/e94560?text=MOTO+PRETA+TRES']::TEXT[], now() - interval '2 days')

ON CONFLICT (protocolo) DO NOTHING;

-- ============================================================
-- Total adicionado: 14 denúncias de furto de fios
-- Bairros cobertos: Vila Operária, Mandacaru, Jd Universitário,
-- Zona 4, Zona 2, Jd Imperial, Parque das Grevíleas,
-- Inocente Vila Nova, Vila Esperança, Jd Tropical, Cidade Alta,
-- Jd Liberdade, Vila Bosque, Jd Aclimação
-- ============================================================
