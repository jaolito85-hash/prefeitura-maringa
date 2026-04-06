# Node Data Maringá — Changelog

## Visão Geral do Projeto

Plataforma de segurança pública e gestão urbana para a Prefeitura de Maringá-PR. Recebe denúncias, ocorrências, alertas SOS e solicitações de arborização via WhatsApp, classifica com IA, e exibe em tempo real num dashboard operacional.

**Stack:** Python 3.11 / FastAPI / Redis / Supabase / React 18 / Mapbox GL / Evolution API (WhatsApp)

**Deploy:** Docker + Coolify + Traefik em `maringa.nodedata.com.br`

---

## Módulos do Sistema

### 1. SOS Mulher
- Código de emergência via WhatsApp (".", "socorro", "ajuda")
- Resposta em < 2 segundos
- Link de rastreamento GPS em tempo real (`mulher-segura.html`)
- Monitor operacional com mapa ao vivo (`monitor-sos.html`)
- Rota traçada pelas ruas (Mapbox Directions) em vez de linha reta
- Cadastro prévio de vítimas com dados do agressor

### 2. Denúncias (Programa Cidadão Ativo — Decreto 291/2026)
- 5 categorias pagas: pichação (R$100), tráfico (R$300), descarte irregular (R$80), furto de fios (R$150), depredação (R$100)
- Classificação por IA (texto + Vision para fotos)
- Detecção de fotos encaminhadas/falsas (red flag)
- Fluxo: cidadão denuncia → operador valida → encaminha para recompensa
- CPF/PIX criptografados, dados sensíveis auditados (LGPD)

### 3. Ocorrências
- Emergências urbanas: enchente, incêndio, buraco, iluminação, acidente
- Queda de árvore por temporal/vendaval (Defesa Civil)
- Dedup inteligente: agrupa relatos da mesma rua/região
- Pergunta ao cidadão "é o mesmo caso?" quando endereço é similar
- Rota para equipes (Google Maps, Waze, WhatsApp, Copiar Despacho)

### 4. Arborização Urbana (Pipeline Agentic)
- Fluxo 100% autônomo: cidadão → IA → empresa → fiscal → feedback
- 7 categorias: poda geral, poda complexa, desbarra, remoção, árvore caída, retirada de toco, risco de queda
- Classificação Vision: pede foto ANTES de classificar gravidade
- Auto-despacho: atribui empresa automaticamente e envia OS via WhatsApp
- Empresa responde: 1=aceitar, 2=a caminho, 3=concluído+foto, 0=recusar
- Fiscal IA: compara fotos antes/depois, auto-aprova se confiança ≥80%
- Feedback cidadão: recebe foto do serviço + avaliação 1-5 estrelas
- SLA por severidade: emergência 4h, urgência 24h, prioridade 72h, rotina 7d
- Monitoramento SLA automático a cada 5 minutos

### 5. Recompensas
- Ciclo: pendente → validada → aguardando pagamento → paga
- Operador vê CPF/PIX real apenas no momento do pagamento
- Cada acesso a dados sensíveis é auditado (LGPD)
- Geração de termo PDF
- Filtros: Dia / Semana / Mês / Total

### 6. Radar de Notícias
- Busca Google News RSS sobre Maringá
- Resumo por IA de notícias selecionadas
- Filtro por fonte e chips de busca rápida

---

## Alterações Recentes (Abril 2026)

### Arborização — Pipeline Agentic Completo
- **Banco:** Tabelas `arborizacao` (30+ campos) e `arborizacao_config` (SLA + empresas) criadas via migration
- **Classificador:** Novo canal `arborizacao` com 7 categorias no prompt de texto + prompt Vision específico para fotos de árvores
- **Worker:** `processar_arborizacao()` com sessão multi-etapa, `_despachar_para_empresa()` via WhatsApp, `_processar_resposta_empresa()` (1/2/3/0), SLA monitoring
- **Fiscal IA:** `comparar_antes_depois()` compara fotos com GPT-4o-mini Vision
- **API REST:** 8 endpoints (listar, mapa, KPIs, config, detalhe, status, atribuir, fiscalizar)
- **Frontend:** Layout 3 colunas (Stitch design), 6 KPIs com satisfação ⭐, filtros de status com contadores, dados reais do Supabase

### Separação Árvore Emergência vs Serviço
- Safety net no webhook: palavras de clima (temporal, chuva, vendaval) → ocorrência/Defesa Civil
- Palavras de serviço (poda, cortar, cupim, raiz) → arborização/empresa
- Ambíguo → arborização por padrão

### Dedup Inteligente de Ocorrências
- Busca por categorias relacionadas (não só exata)
- Janela ampliada de 6h para 12h
- Busca mesma rua: "Já temos X relatos nessa região. É o mesmo caso?" (1=sim, 2=não)
- Handler `aguardando_confirmacao_dedup` processa resposta do cidadão

### Denúncias — Melhorias
- Recompensa só criada APÓS validação do operador (não automática)
- Botão "💰 Validar e Encaminhar para Pagamento" no modal
- Seção Rota & Despacho: Google Maps, Waze, WhatsApp, Copiar
- Badge vermelho na sidebar com contagem de denúncias novas
- Filtro "✕ Improcedente" na barra de status
- Cards urgentes no feed com borda vermelha pulsante
- Filtro "Total" + setas de navegação ‹ › por período

### Recompensas
- Filtro "Total" adicionado (Dia/Semana/Mês/Total)
- `_encriptar_dado()` agora usa base64 reversível (demo)
- `_decriptar_dado()` permite ver CPF/PIX real no pagamento
- Aba Relatórios removida (dados consolidados em Recompensas)

### SOS Mulher
- Tabelas `emergencia_sessoes` e `emergencia_pontos` criadas no Supabase
- Worker inclui `alerta_id` na sessão GPS
- Monitor SOS: rota pelas ruas (Mapbox Directions) quando há salto >200m entre pontos

### Correções Gerais
- Rota Waze com origem e destino (antes só mostrava pin)
- Despacho reflete severidade real (não sempre "URGENTE")
- Scroll na aba Notícias (último card não ficava cortado)
- Modal de busca protocolo centralizado na tela (ReactDOM.createPortal)
- Classificação de fotos restaurada (SYSTEM_PROMPT_IMAGEM original)
- Telefone empresa normalizado com + (sessão não perdia)
- Sessão empresa com TTL 7 dias (não 5 minutos)
- Reconhecimento de empresa sem sessão ativa (webhook verifica config)

---

## Banco de Dados (Supabase PostgreSQL)

### Tabelas (14 total)
| Tabela | Descrição |
|---|---|
| `denuncias` | Denúncias do Cidadão Ativo |
| `ocorrencias` | Emergências urbanas agrupadas |
| `ocorrencias_relatos` | Relatos individuais por ocorrência |
| `sos_cadastros` | Cadastro prévio mulheres |
| `sos_alertas` | Alertas de emergência |
| `sos_mensagens` | Chat SOS operador ↔ vítima |
| `feedbacks` | Elogios, reclamações, sugestões |
| `feedbacks_mensagens` | Chat feedback |
| `recompensas` | Ciclo de pagamento |
| `recompensas_config` | Valores por categoria |
| `arborizacao` | Solicitações de arborização |
| `arborizacao_config` | SLA + empresas contratadas |
| `emergencia_sessoes` | Sessões de rastreamento GPS |
| `emergencia_pontos` | Pontos GPS contínuos |
| `audit_log` | Auditoria LGPD |
| `sessoes_conversa` | Estado de conversa por telefone |

### Migrations
```
001 — Tabelas base (denuncias, sos, ocorrencias, feedbacks)
002 — Habilitar Realtime
003 — Seed dados demo
004 — Storage bucket evidências
005 — Recompensas + config
006-018 — Ajustes incrementais
019 — Arborização (tabela + config + realtime)
020 — Seed arborização demo (50 registros)
021 — Foto flag em arborização
022 — Emergência tracking (sessões + pontos GPS)
```

---

## API REST (50+ endpoints)

| Prefixo | Endpoints | Descrição |
|---|---|---|
| `/api/kpis` | 1 | KPIs do painel central |
| `/api/feed` | 1 | Feed ao vivo |
| `/api/denuncias` | 4 | CRUD + validar recompensa |
| `/api/ocorrencias` | 6 | CRUD + handoff + mensagens |
| `/api/sos` | 9 | Alertas + chat + handoff |
| `/api/feedbacks` | 4 | CRUD + mensagens |
| `/api/recompensas` | 6 | CRUD + dados pagamento + termo PDF |
| `/api/arborizacao` | 8 | CRUD + atribuir + fiscalizar + KPIs |
| `/api/protocolo` | 1 | Busca unificada por protocolo |
| `/api/noticias` | 2 | Busca + resumo IA |
| `/webhook/unificado` | 1 | Webhook demo (número único) |
| `/webhook/denuncias` | 1 | Webhook produção denúncias |
| `/webhook/sos-mulher` | 1 | Webhook produção SOS |
| `/webhook/ocorrencias` | 1 | Webhook produção ocorrências |

---

## Worker — Filas Redis (7 filas)

```
Prioridade: queue:sos > queue:denuncias > queue:ocorrencias > queue:arborizacao > queue:feedbacks > queue:consultas > queue:saudacoes
```

| Fila | Handler | Função |
|---|---|---|
| `queue:sos` | `processar_sos()` | Emergência mulher |
| `queue:denuncias` | `processar_denuncia()` | Cidadão Ativo |
| `queue:ocorrencias` | `processar_ocorrencia()` | Emergências urbanas |
| `queue:arborizacao` | `processar_arborizacao()` | Arborização agentic |
| `queue:feedbacks` | `processar_feedback()` | Opiniões/reclamações |
| `queue:consultas` | `processar_consulta_protocolo()` | Consulta protocolo |
| `queue:saudacoes` | `processar_saudacao()` | Cumprimentos |

---

## Frontend — Dashboard (8 abas)

| Aba | Componente | Descrição |
|---|---|---|
| Painel | `Central` | KPIs, mapa, feed ao vivo |
| Mapa | `Mapa` | Mapa fullscreen com todos os pontos |
| Ocorrências | `Ocorrencias` | Mapa + sidebar + detalhe + rota |
| Denúncias | `Denuncias` | Cards + filtros + despacho + recompensa |
| Feedbacks | `Feedbacks` | Grid + chat + departamentos |
| Recompensas | `Recompensas` | Dashboard financeiro + pagamento PIX |
| SOS Mulher | `SOSMulher` | Tela vermelha + sirene + dados vítima |
| Notícias | `RadarNoticias` | Google News + resumo IA |
| Arborização | `Arborizacao` | 3 colunas + mapa + KPIs + satisfação |

---

## Segurança

- **LGPD:** CPF/PIX criptografados, audit_log em toda ação sensível
- **Foto fraud:** Detecção de fotos encaminhadas (red flag) via Evolution API metadata
- **Rate limiting:** 500 msgs/dia por telefone, 3 consultas protocolo/hora
- **Separação de camadas:** operador não vê CPF, financeiro não vê conteúdo da denúncia
- **Supabase:** Datacenter `sa-east-1` (São Paulo), dados em território nacional
