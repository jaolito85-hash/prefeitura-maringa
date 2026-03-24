# Node Data — Central de Seguranca Publica · Maringa-PR

Plataforma de seguranca publica para a Prefeitura de Maringa. Recebe denuncias, ocorrencias e alertas SOS via WhatsApp, classifica com IA, e exibe em tempo real num dashboard operacional.

---

## FASE ATUAL: DEMO AO VIVO

> **STATUS:** Sistema funcional com backend, worker, filas Redis e dashboard operando. Faltam dados mockados volumosos para o painel ficar visualmente impactante.
>
> **DEMO:** Reuniao de vendas B2G com a Prefeitura de Maringa-PR em **25 ou 26 de marco de 2026**. Embasada no Decreto 291/2026 (Programa Cidadao Ativo).
>
> **PRIORIDADE ABSOLUTA:** Tudo que for feito agora deve servir a demo. Nada de refatoracao, testes, ou melhorias estruturais ate a apresentacao terminar.
>
> **POS-DEMO:** Apos a apresentacao, faremos limpeza completa — remover dados mockados, resetar sequences, limpar bucket de evidencias. Nenhuma limpeza antes da demo.

### O que funciona hoje
- WhatsApp → Evolution API → Webhook → Classificacao IA → Redis → Worker → Supabase → Dashboard Realtime
- 7 routers REST (denuncias, ocorrencias, sos, feedbacks, recompensas, dashboard, protocolo)
- Frontend dark theme com 5 abas, mapa Mapbox, feed ao vivo, sirene SOS via Web Audio
- Sistema de recompensas com ciclo completo (pendente → validada → paga)
- Sessao de conversa por telefone com expiração

### O que falta para a demo
- **Dados volumosos:** O painel precisa de dezenas de denuncias, ocorrencias espalhadas pelo mapa de Maringa, feedbacks variados, historico de recompensas pagas — tudo mockado mas realista
- **KPIs impactantes:** Os numeros do dashboard precisam mostrar volume (ex: 247 denuncias, 89 ocorrencias, tempo medio 4min)
- **Mapa populado:** Markers espalhados por bairros reais de Maringa (Zona 7, Centro, Jardim Alvorada, Vila Operaria, etc.) com coordenadas reais
- **Feed ao vivo:** Historico de eventos recentes para o feed lateral parecer ativo
- **SOS demo:** Pelo menos 1 alerta SOS ativo para demonstrar a tela vermelha com sirene

### Regras durante a fase demo
- NUNCA apagar dados existentes no banco — so adicionar
- NUNCA rodar migrations destrutivas (DROP, TRUNCATE) — confirmar com usuario antes de qualquer DDL
- Scripts de seed devem ser idempotentes (rodar varias vezes sem duplicar)
- Dados mockados devem usar telefones falsos (ex: 5544999990001) e CPFs ficticios
- Enderecos devem ser de bairros reais de Maringa com coordenadas geograficas corretas
- Datas dos registros mockados devem estar espalhadas nos ultimos 30 dias (nao tudo no mesmo dia)

---

## Arquitetura

```
WhatsApp (cidadao)
    |
Evolution API (webhooks)
    |
FastAPI (backend) --> Redis (filas por prioridade)
    |                        |
    v                        v
Supabase (PostgreSQL)    Worker (processa filas)
    |                        |
    v                        v
Dashboard (React)       Evolution API (responde ao cidadao)
```

**Stack:** Python 3.11 / FastAPI / Redis / Supabase / React 18 / Mapbox GL / Nginx

## Estrutura do projeto

```
backend/
  app/
    main.py              # FastAPI entry point, CORS, 7 routers
    config.py            # Pydantic BaseSettings (.env)
    api/
      dashboard.py       # GET /api/kpis, /api/feed, /api/relatorio
      denuncias.py       # GET lista, PATCH status
      ocorrencias.py     # GET lista, GET /mapa, GET relatos, PATCH status
      sos.py             # GET alertas, PATCH aceitar, PATCH resolver
      feedbacks.py       # GET lista, PATCH status, GET estatisticas
      recompensas.py     # GET lista, GET kpis, GET dados-pagamento, PATCH validar/pagar
      protocolo.py       # GET lookup, GET status-cidadao
    webhooks/
      unificado.py       # Webhook demo (numero unico, classifica com IA)
      denuncias.py       # Webhook producao — canal denuncia
      sos_mulher.py      # Webhook producao — canal SOS
      ocorrencias.py     # Webhook producao — canal ocorrencias
      common.py          # Validacao API key, rate limit, dedup
    services/
      classificador.py   # OpenAI GPT-4o-mini — classifica em: denuncia, sos_mulher, ocorrencia, feedback, saudacao
      supabase_client.py # Singleton Supabase client (service_key)
      webhook_queue.py   # Enfileirar no Redis por canal
      rate_limiter.py    # 30 msgs/dia, 3 consultas protocolo/hora
      gerar_termo_pdf.py # PDF de termo de recompensa (reportlab)
    utils/
      protocol.py        # Gerar protocolo MGA-2026-XXXXX
  worker.py              # Processa filas Redis por prioridade. ARQUIVO GRANDE (~900 linhas)
  requirements.txt
  Dockerfile             # python:3.11-slim

frontend/
  src/
    App.jsx              # Layout principal, 5 abas, banner SOS, busca protocolo
    pages/
      Central.jsx        # KPIs (4 cards), mapa Mapbox, feed ao vivo
      Denuncias.jsx      # Grid de cards, filtros categoria/status, painel detalhe
      SOSMulher.jsx      # TELA VERMELHA pulsante, sirene, dados vitima, botoes acao
      Ocorrencias.jsx    # Mapa fullscreen + sidebar incidentes
      Recompensas.jsx    # Dashboard financeiro, ciclo de pagamento
    components/
      AudioManager.jsx   # Web Audio API — sirene (800Hz), bipe duplo (1000Hz), bipe longo
      Map/CityMap.jsx    # Mapbox GL com markers coloridos por categoria
    services/
      api.js             # apiGet, apiPatch, apiPost — HTTP client
      supabase.js        # Realtime subscriptions (denuncias, ocorrencias, sos_alertas, feedbacks)
  index.html             # SPA monolitico (React 18 via CDN + Babel standalone)
  mulher-segura.html     # Pagina SOS separada
  monitor-sos.html       # Visao operador SOS
  nginx.conf             # Proxy /api/* e /webhook/* → backend:8000
  Dockerfile             # nginx:alpine

supabase/migrations/
  001_create_tables.sql           # Tabelas + audit_log + protocolo_seq
  002_enable_realtime.sql         # Realtime em 4 tabelas
  003_seed_demo_data.sql          # Seed inicial (pouco volume)
  004_create_storage_bucket.sql   # Bucket "evidencias"
  005_create_recompensas.sql      # Tabela recompensas + config + indices
  005b_seed_recompensas_demo.sql  # 4 recompensas demo
  006-010                         # Ajustes incrementais (categorias, tokens, limpeza, descricao)

docker-compose.yml       # Dev: redis + backend + worker(x2) + frontend
docker-compose.prod.yml  # Prod: Coolify/Traefik, sem portas expostas, health checks
```

## Banco de dados (Supabase PostgreSQL)

### Tabelas

| Tabela | Descricao | Campos-chave |
|---|---|---|
| `denuncias` | Cidadania Ativa | protocolo, telefone, categoria, mensagem, midia_urls[], bairro, status, cpf_encrypted, dados_bancarios_encrypted |
| `ocorrencias` | Incidentes urbanos agrupados | protocolo, categoria, endereco_normalizado, severidade, total_relatos, latitude, longitude |
| `ocorrencias_relatos` | Relatos individuais | ocorrencia_id, telefone, mensagem, midia_urls[] |
| `sos_cadastros` | Cadastro previo mulheres | telefone (UNIQUE), nome, agressor, contato_confianca |
| `sos_alertas` | Alertas emergencia | cadastro_id, status (ativo/atendendo/resolvido), latitude, longitude |
| `feedbacks` | Elogios, reclamacoes, sugestoes | telefone, mensagem, sentimento, categoria, status |
| `sessoes_conversa` | Estado conversa por telefone | telefone (UNIQUE), canal, etapa, expira_em, contexto (JSONB) |
| `recompensas` | Ciclo pagamento | protocolo, denuncia_id, status, valor, cpf_encrypted, chave_pix_encrypted |
| `recompensas_config` | Valores por categoria | categoria, valor_padrao, ativo |
| `audit_log` | LGPD | tabela, acao, operador, ip, created_at |

### Seguranca de dados

- `cpf_encrypted` e `dados_bancarios_encrypted` — AES-256. NUNCA salvar plaintext. NUNCA retornar na API publica.
- `chave_pix_encrypted` — mesmo tratamento.
- Separacao de camadas: quem ve denuncia NAO ve CPF/PIX. Quem ve recompensa NAO ve conteudo da denuncia. Ponte: protocolo + audit_log.
- Telefones de cidadaos: nao expor em endpoints publicos do dashboard.

### Protocolo
Formato `MGA-2026-XXXXX` via `protocolo_seq` (PostgreSQL sequence).

## Fluxo de mensagens WhatsApp

1. Mensagem chega no webhook → valida API key + dedup
2. Detecta SOS (resposta < 2s) → fila prioritaria
3. Verifica sessao ativa pra esse telefone
4. Se tem sessao → CONTINUACAO (mesmo protocolo, nao classifica de novo)
5. Se nao tem → classifica com IA (GPT-4o-mini) → abre protocolo
6. Enfileira no Redis (fila por canal)
7. Worker processa: `queue:sos` > `queue:denuncias` > `queue:ocorrencias` > `queue:feedbacks` > `queue:consultas` > `queue:saudacoes`
8. Salva no Supabase + responde via Evolution API

### Classificador IA
- Modelo: OpenAI GPT-4o-mini (NAO usa Claude/Anthropic apesar da var no config)
- Canais: `denuncia`, `sos_mulher`, `ocorrencia`, `feedback`, `saudacao`
- Extrai: categoria, sentimento, urgencia (1-5), resumo, resposta_whatsapp
- Dois prompts: SYSTEM_PROMPT (msg nova) e SYSTEM_PROMPT_SESSAO (continuacao)

### Sessao de conversa
Uma por telefone, expira em ~1 min (demo) ou 30 min (prod). Etapas: `aguardando_midia` → `aguardando_endereco` → `finalizado`.

### Midia
- Download via Evolution API (`getBase64FromMediaMessage`)
- Upload para Supabase Storage (bucket `evidencias`)
- URLs em `midia_urls[]` (TEXT array)
- Limites: max 5 fotos (5MB cada), max 1 video (16MB)

## Frontend — Dashboard operacional

HTML monolitico com React 18 via CDN (sem build step). Dark theme (#03040a bg, #10b981 accent). Abas:

| Aba | Componente | Descricao |
|---|---|---|
| CENTRAL | Central.jsx | 4 KPI cards + mapa Mapbox + feed ao vivo (sidebar direita) |
| DENUNCIAS | Denuncias.jsx | Grid 2 colunas, filtros, painel lateral com detalhe + midia |
| SOS MULHER | SOSMulher.jsx | Tela vermelha pulsante, sirene, dados vitima, botoes 190/153 |
| OCORRENCIAS | Ocorrencias.jsx | Mapa fullscreen + sidebar com lista de incidentes |
| RECOMPENSAS | Recompensas.jsx | Dashboard financeiro, ciclo pendente→validada→paga |

**Audio:** Web Audio API (sem MP3). Sirene 800Hz (SOS), bipe duplo 1000Hz (denuncia urgente), bipe longo (escalada).

**Realtime:** Supabase subscriptions em denuncias, ocorrencias, sos_alertas, feedbacks, recompensas. Dashboard atualiza automaticamente.

## Comandos

```bash
# Dev local (Docker)
docker compose up --build

# Producao (Coolify)
docker compose -f docker-compose.prod.yml up -d

# Logs ao vivo (util na demo)
docker compose logs -f

# Backend local (sem Docker)
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload

# Worker local
cd backend && python worker.py

# Frontend local
cd frontend && npm install && npm run dev
```

## Variaveis de ambiente

### Backend (.env)
| Variavel | Descricao |
|---|---|
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_SERVICE_KEY` | Service key (acesso total) |
| `REDIS_URL` | Conexao Redis (redis://redis:6379) |
| `EVOLUTION_API_URL` | URL da Evolution API |
| `EVOLUTION_API_KEY` | Chave da Evolution API |
| `WA_INSTANCE_NAME` | Instancia demo (numero unico) |
| `WA_INSTANCE_DENUNCIAS` | Instancia producao — denuncias |
| `WA_INSTANCE_SOS` | Instancia producao — SOS |
| `WA_INSTANCE_OCORRENCIAS` | Instancia producao — ocorrencias |
| `OPENAI_API_KEY` | Chave OpenAI (classificador) |
| `WEBHOOK_SECRET` | Validacao de webhook |
| `AES_KEY` | Chave AES-256 (criptografia CPF/banco) |

### Frontend (.env)
| Variavel | Descricao |
|---|---|
| `VITE_API_URL` | URL do backend |
| `VITE_SUPABASE_URL` | URL Supabase (Realtime) |
| `VITE_SUPABASE_ANON_KEY` | Anon key Supabase |

## Limitacoes conhecidas (aceitaveis para demo)

- **Sem autenticacao:** Dashboard aberto, sem login. OK para demo em ambiente controlado.
- **Sem testes:** Zero cobertura. Se for criar depois da demo, usar pytest.
- **Frontend monolitico:** React via CDN num unico HTML. Nao quebrar em arquivos separados.
- **Worker grande:** worker.py tem ~900 linhas. Refatorar depois da demo.
- **Classificador:** Usa OpenAI, nao Claude (apesar de ANTHROPIC_API_KEY no config — esta la mas nao e usada).
- **Mapa:** Mapbox funciona mas sem heatmap/cluster/rotas avancadas ainda.
- **Pagamento PIX:** Campo existe, ciclo funciona, mas sem integracao real com API Pix.

## Regras para o Claude

### Gerais
- Toda comunicacao em portugues brasileiro
- Manter padrao existente: funcoes snake_case, variaveis descritivas em portugues
- Commitar direto na main (sem branches ate organizar pos-demo)

### Seguranca
- NUNCA expor cpf_encrypted, dados_bancarios_encrypted ou chave_pix_encrypted na API
- NUNCA salvar CPF ou dados bancarios em plaintext
- Telefones de cidadaos nao devem aparecer em endpoints publicos do dashboard

### Arquitetura
- Webhook deve retornar 202 imediatamente — processamento via fila Redis
- Frontend e HTML monolitico com React via CDN — NAO quebrar em arquivos separados
- Worker roda como processo standalone (nao usa rq, nao usa celery)
- Deploy via Coolify com Traefik — sem portas expostas nos containers
- Mapa usa Mapbox GL JS (token no frontend)
- Audio gerado por Web Audio API — NAO adicionar arquivos MP3
- Supabase Realtime habilitado — usar para live updates no dashboard

### Dados demo
- Ao criar dados mockados, usar bairros reais de Maringa com coordenadas corretas
- Telefones ficticios: formato 55449999XXXXX
- CPFs ficticios (nao usar CPFs reais)
- Datas espalhadas nos ultimos 30 dias
- Categorias variadas para mostrar diversidade no dashboard
- Scripts de seed devem ser idempotentes (safe to re-run)
