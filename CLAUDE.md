# Node Data — Central de Seguranca Publica · Maringa-PR

Plataforma de seguranca publica para a Prefeitura de Maringa. Recebe denuncias, ocorrencias e alertas SOS via WhatsApp, classifica com IA, e exibe em tempo real num dashboard operacional.

> **CONTEXTO:** Sistema em demo ao vivo para reuniao de vendas B2G com a Prefeitura de Maringa-PR, embasada no Decreto 291/2026 (Programa Cidadao Ativo). Backend FastAPI rodando com dados reais de teste. Antes de qualquer operacao destrutiva no banco (DELETE, UPDATE em massa, migrations), confirmar com o usuario.

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
    main.py              # FastAPI entry point
    config.py            # Pydantic settings (.env)
    api/                 # Endpoints REST: denuncias, ocorrencias, sos, feedbacks, dashboard
    webhooks/
      unificado.py       # Webhook demo (numero unico, classifica com IA)
      denuncias.py       # Webhook producao — canal denuncia
      sos_mulher.py      # Webhook producao — canal SOS
      ocorrencias.py     # Webhook producao — canal ocorrencias
      common.py          # Validacao de API key, rate limit, dedup
    services/
      classificador.py   # Classificador IA (OpenAI GPT-4o-mini)
      supabase_client.py # Singleton Supabase client
      webhook_queue.py   # Enfileirar eventos no Redis
  worker.py              # Processa filas Redis: SOS > Denuncias > Ocorrencias > Feedbacks
  Dockerfile             # python:3.11-slim
  requirements.txt

frontend/
  src/
    App.jsx              # Layout principal, navegacao por abas, banner SOS
    pages/
      Central.jsx        # Painel: KPIs, mapa Mapbox, feed ao vivo
      Denuncias.jsx      # Lista de denuncias com filtros, modal com midia
      SOSMulher.jsx      # Tela emergencia: fundo vermelho, sirene, dados vitima
      Ocorrencias.jsx    # Mapa fullscreen, sidebar incidentes, agrupamento
      Recompensas.jsx    # Painel financeiro: recompensas Cidadao Ativo, pagamentos PIX
    components/
      AudioManager.jsx   # Web Audio API — sirene e bipes (sem MP3)
      Map/CityMap.jsx    # Mapa Leaflet com tiles CartoDB Dark
    services/
      api.js             # HTTP client pro backend
      supabase.js        # Supabase Realtime subscriptions
  index.html             # SPA monolitico (React via CDN + Babel standalone)
  nginx.conf             # Proxy /api/* e /webhook/* pro backend
  Dockerfile             # nginx:alpine

supabase/migrations/
  001_create_tables.sql  # 5 tabelas + audit_log + sequencia protocolo
  002_enable_realtime.sql
  003_seed_demo_data.sql  # <-- dados de demonstracao para a reuniao
  004_create_storage_bucket.sql  # Bucket "evidencias" pra fotos/videos
  005_create_recompensas.sql     # Tabela recompensas + recompensas_config + indices
  005b_seed_recompensas_demo.sql # Dados demo: 4 recompensas em diferentes status

docker-compose.yml       # Dev: redis + backend + worker + frontend
docker-compose.prod.yml  # Producao: Coolify/Traefik (sem portas expostas)
```


## Banco de dados (Supabase PostgreSQL)

### Tabelas principais

| Tabela | Descricao |
|---|---|
| `denuncias` | Canal Cidadania Ativa — protocolo, categoria, midia_urls[], status, cpf/banco encrypted |
| `sos_cadastros` | Cadastro previo de mulheres (telefone, agressor, contato confianca) |
| `sos_alertas` | Alertas ativos quando codigo SOS enviado — status, localizacao |
| `ocorrencias` | Incidentes agrupados por endereco — severidade auto-calculada por total_relatos |
| `ocorrencias_relatos` | Relatos individuais vinculados a uma ocorrencia |
| `feedbacks` | Canal generico (elogios, reclamacoes, sugestoes) |
| `sessoes_conversa` | Estado da conversa por telefone (evita duplicar protocolos) |
| `audit_log` | LGPD — log de acesso a dados sensiveis |

### Campos sensiveis (AES-256)

`denuncias.cpf_encrypted` e `denuncias.dados_bancarios_encrypted` — NUNCA salvar em plaintext. NUNCA retornar na API publica.

### Protocolo

Formato `MGA-2026-XXXXX` gerado via `protocolo_seq` (PostgreSQL sequence).

## Fluxo de mensagens WhatsApp

1. Mensagem chega no webhook → valida API key
2. Verifica se tem sessao ativa pra esse telefone
3. Se tem → CONTINUACAO (mesmo protocolo, nao classifica de novo)
4. Se nao tem → NOVA mensagem → classifica com IA → abre protocolo
5. Enfileira no Redis (fila por canal)
6. Worker processa na ordem: `queue:sos` > `queue:denuncias` > `queue:ocorrencias` > `queue:feedbacks`
7. Salva no Supabase + responde via Evolution API

### Sessao de conversa

Uma sessao por telefone, expira em 30 min. Etapas: `aguardando_midia` → `aguardando_endereco` → `finalizado`.

### Midia (fotos/videos)

- Download via Evolution API (`getBase64FromMediaMessage`)
- Upload para Supabase Storage (bucket `evidencias`)
- URLs salvas em `midia_urls[]` (TEXT array)
- **Limites:** max 5 fotos (5MB cada), max 1 video (16MB), por registro

## Frontend — Dashboard operacional

HTML monolitico com React 18 via CDN (sem build step). Abas:

- **Painel** — KPIs, mapa Mapbox com markers coloridos, feed ao vivo
- **Mapa** — Fullscreen com rotas, bases policiais, heatmap
- **Ocorrencias** — Lista + mapa, agrupamento por endereco
- **Denuncias** — Tabela com filtros, modal de detalhe com fotos/videos
- **Feedbacks** — Cards com sentimento e prioridade
- **SOS Mulher** — Fundo vermelho pulsante, sirene via Web Audio, dados da vitima

**Audio:** sirene (SOS), bipe duplo (denuncia urgente), bipe longo (ocorrencia escalada) — gerados por Web Audio API, sem arquivos.

## Comandos

```bash
# Dev
docker compose up --build

# Producao (Coolify)
docker compose -f docker-compose.prod.yml up -d

# Ver logs ao vivo (util durante a demo)
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
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` — acesso total ao banco
- `REDIS_URL` — fila de mensagens
- `EVOLUTION_API_URL`, `EVOLUTION_API_KEY` — WhatsApp
- `WA_INSTANCE_NAME` — instancia demo (numero unico)
- `WA_INSTANCE_DENUNCIAS`, `WA_INSTANCE_SOS`, `WA_INSTANCE_OCORRENCIAS` — producao
- `OPENAI_API_KEY` — classificador IA
- `WEBHOOK_SECRET` — validacao de webhook
- `AES_KEY` — criptografia CPF/banco

### Frontend (.env)
- `VITE_API_URL` — URL do backend
- `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` — Realtime

## Regras para o Claude

- Toda comunicacao em portugues brasileiro
- Manter padrao de codigo existente: funcoes snake_case, variaveis descritivas
- NUNCA expor cpf_encrypted ou dados_bancarios_encrypted na API
- Webhook deve retornar 202 imediatamente — processamento sempre via fila Redis
- Frontend e um HTML monolitico com React via CDN — nao quebrar em arquivos separados
- Worker roda como processo standalone (nao usa rq, nao usa celery)
- Testes: nao existem ainda. Se for criar, usar pytest
- Deploy via Coolify com Traefik — sem portas expostas nos containers
- Mapa usa Mapbox GL JS (token no frontend). Fallback: CartoDB Dark tiles via Leaflet
- Audio e gerado por Web Audio API — nao adicionar arquivos MP3
- Supabase Realtime esta habilitado nas tabelas principais — usar pra live updates
