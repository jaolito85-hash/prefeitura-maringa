# CLAUDE.md — Node Data Maringá: Plataforma de Segurança Pública

> **ATENÇÃO: Este projeto NÃO é uma vertical padrão do Node Data.**
> É uma plataforma customizada de segurança pública para uma cidade de 500 mil habitantes.
> O dashboard, a arquitetura e a escala são completamente diferentes das outras verticais.
> NÃO use o template padrão. NÃO use `/new-vertical`. Construa do zero com as specs abaixo.

---

## 1. VISÃO GERAL DO PROJETO

### O que é

Uma plataforma de segurança pública para a Prefeitura de Maringá que opera em **3 canais independentes via WhatsApp**, cada um com seu próprio número, sua própria agente de IA e sua própria lógica:

| Canal | Número | Agente | Função |
|---|---|---|---|
| **Denúncias** | Número 1 | Clara | Denúncias com recompensa: drogas, pichação, lixo, vandalismo |
| **SOS Mulher** | Número 2 | (Sem nome visível — disfarçado de farmácia) | Botão de pânico silencioso para mulheres em violência |
| **Ocorrências** | Número 3 | Clara Emergência | Catástrofes, queda de árvores, enchentes, buracos |

Cada número é uma instância separada na Evolution API. Cada um tem webhook próprio. Cada um tem lógica independente.

### O que NÃO é

- NÃO é uma central de reclamações genéricas. O cidadão NÃO reclama de atendimento, calçada, ou qualquer coisa aleatória aqui.
- NÃO é o padrão de dashboard das outras verticais. O dashboard é customizado para telas grandes (50"+), com mapas, sons e alertas visuais.
- NÃO segue o `/new-vertical`. É construído do zero.

### Escala

- **Cidade:** Maringá-PR, ~500 mil habitantes
- **Pico estimado:** até 1.000 mensagens simultâneas (em eventos como tempestade)
- **Arquitetura precisa suportar esse volume sem perder mensagem alguma**

---

## 2. CONTEXTO DE MARINGÁ

### Por que essa cidade

- **3ª cidade mais inovadora do Brasil** (Anciti Awards 2025, 100-500k hab)
- **6ª cidade mais inteligente do Sul** (Connected Smart Cities)
- Orçamento 2026: **R$ 3,58 bilhões**
- Orçamento de segurança 2026: **R$ 66,9 milhões** (+96% vs 2025)
- Prefeito: Silvio Barros — posiciona Maringá como referência smart city

### Decreto 291/2026 — Programa Cidadania Ativa

Entrou em vigor 03/03/2026. Paga **R$ 250 a R$ 1.000** por denúncia comprovada com foto/vídeo.

Categorias do decreto:
- Pichação / grafite não autorizado
- Furto / vandalismo de fiação elétrica e cabos
- Descarte irregular de resíduos
- Depredação de bens públicos
- Pontos de tráfico de drogas

**Gargalo atual:** Denúncias só pelo telefone 153. Fotos/vídeos por "algum meio" separado. Sem canal digital.

**Exigência legal:** O cidadão deve declarar **espontaneamente** que quer participar. O atendente NÃO pode oferecer nem induzir.

### Problema de protocolos duplicados

O Secretário relatou: quando uma árvore cai, **10 pessoas ligam pro 153** e abrem **10 protocolos diferentes** pro mesmo incidente. A IA resolve isso com agrupamento inteligente por endereço.

---

## 3. ARQUITETURA TÉCNICA (SEGURANÇA E ESCALA)

### Stack

| Componente | Tecnologia | Por quê |
|---|---|---|
| **Backend** | Python + FastAPI (não Flask) | Async nativo, suporta alto volume, mais rápido que Flask |
| **Fila de mensagens** | Redis (Bull Queue ou rq) | Mensagens entram na fila ANTES de processar. Nenhuma mensagem se perde, mesmo com 1000 simultâneas |
| **Banco de dados** | Supabase (PostgreSQL + RLS + Realtime) | RLS garante que operadores só veem o que devem. Realtime atualiza o dashboard |
| **Cache** | Redis | Cache de sessões, rate limiting, deduplicação de mensagens |
| **WhatsApp** | Evolution API (3 instâncias separadas) | Uma instância por canal. Se uma cair, as outras continuam |
| **Frontend** | React + Vite + Tailwind | Dashboard customizado, NÃO é o padrão das outras verticais |
| **Mapas** | Leaflet + CartoDB Dark tiles | Gratuito, sem API key, tema escuro |
| **Hospedagem** | VPS Hostinger com Coolify (Docker) | Cada serviço em container separado |
| **Monitoramento** | Health checks + UptimeRobot | Alerta se qualquer serviço cair |

### Por que FastAPI ao invés de Flask

Flask é síncrono — com 1000 mensagens simultâneas, ele engasga. FastAPI é **assíncrono nativo** (usa `async/await`), suporta alta concorrência sem travar. Também tem validação automática com Pydantic e docs automáticas.

Se preferir manter Flask por familiaridade, usar **Gunicorn com workers gevent** para simular async. Mas FastAPI é a recomendação para esse volume.

### Fluxo de mensagem (com fila)

```
WhatsApp → Evolution API → Webhook
       ↓
[WEBHOOK] Recebe a mensagem
       ↓
Valida: rate limit por telefone (Redis) → se excedeu, rejeita
       ↓
Salva na FILA (Redis Queue) → responde 200 OK imediatamente
       ↓
[WORKER] Consome da fila (pode ter N workers)
       ↓
Processa: identifica módulo, classifica, salva no Supabase
       ↓
Responde via Evolution API
       ↓
Supabase Realtime → Dashboard atualiza
```

**Por que fila?** Se 1000 mensagens chegam ao mesmo tempo, o webhook aceita TODAS em milissegundos (coloca na fila) e retorna 200. Os workers processam uma por uma na sequência. Nenhuma mensagem se perde. Sem fila, o webhook trava e a Evolution API reenvia, criando duplicatas.

### Segurança — Regras invioláveis

#### Rate Limiting (Redis)

```
Por telefone: máximo 10 mensagens por minuto
Por IP do webhook: máximo 500 requests por minuto
Global: máximo 5000 mensagens por minuto (proteção DDoS)
```

Se exceder → bloqueia temporariamente (60 segundos) e loga o evento.

#### Deduplicação de mensagens

A Evolution API pode reenviar mensagens se o webhook demorar a responder. O sistema deve:
1. Gerar hash da mensagem (telefone + texto + timestamp truncado em 5 segundos)
2. Verificar no Redis se esse hash já existe
3. Se existe → ignora (é duplicata)
4. Se não existe → processa e salva o hash com TTL de 60 segundos

#### Criptografia e acesso

- **Supabase RLS (Row Level Security)** ativo em TODAS as tabelas
- Operadores autenticados por email/senha + role no Supabase
- Dados sensíveis (CPF, dados bancários, dados de vítimas) em colunas com acesso restrito
- **Nunca logar** dados sensíveis em console/arquivo de log
- **Nunca retornar** dados sensíveis em respostas de API
- **HTTPS obrigatório** em todos os endpoints
- **Webhook autenticado** — validar header `apikey` da Evolution API em cada request

#### Backup

- Supabase faz backup diário automático
- Configurar backup adicional semanal exportando as tabelas críticas

#### Variáveis de ambiente

NENHUMA chave, senha ou token hardcoded no código. Tudo em `.env` e carregado via variáveis de ambiente no Coolify.

---

## 4. OS 3 CANAIS (detalhamento)

---

### CANAL 1: DENÚNCIAS (Clara)

**Número:** Instância "maringa-denuncias" na Evolution API
**Agente:** Clara — tom sério, institucional, acolhedor mas objetivo

#### Fluxo completo

```
Cidadão manda mensagem para o número de denúncias
       ↓
Clara acolhe: "Olá! Sou a Clara, canal de denúncias da 
Prefeitura de Maringá. Pode me contar o que aconteceu?"
       ↓
Cidadão descreve (IA classifica: pichação, tráfico, lixo, etc.)
       ↓
Clara pede evidência: "Consegue enviar uma foto ou vídeo? 
Isso fortalece muito a denúncia."
       ↓
Cidadão envia foto/vídeo
       ↓
Clara pede localização: "Pode me dizer o endereço e bairro? 
Ou envie sua localização: 📎 > Localização"
       ↓
Clara pergunta sobre recompensa (UMA VEZ, sem induzir):
"A Prefeitura tem o Programa Cidadania Ativa que paga 
recompensa por denúncias comprovadas. Gostaria de participar? 
Suas informações ficam em sigilo total."
       ↓
Se SIM → coleta nome, CPF, dados bancários (tudo em sigilo)
Se NÃO → registra como denúncia anônima
       ↓
Clara confirma: "Protocolo MGA-2026-XXXXX registrado. 
A Guarda Municipal será notificada. Obrigada!"
```

#### Categorias e palavras-chave

| Categoria | Palavras-chave |
|---|---|
| Pichação | pichação, grafite, pixo, picharam, rabiscaram, muro |
| Tráfico | droga, tráfico, biqueira, ponto de venda, crack, maconha |
| Descarte irregular | lixo, entulho, jogaram, sujeira, terreno baldio |
| Vandalismo | quebraram, vandalismo, fios, cabos, poste, placa |
| Depredação | depredação, banco quebrado, ponto de ônibus, praça |

#### Mídia (OBRIGATÓRIA para recompensa)

O webhook captura `imageMessage` e `videoMessage` da Evolution API. Salvar no Supabase Storage. Vincular URL ao registro. Sem mídia, a denúncia é registrada mas NÃO é elegível para recompensa.

---

### CANAL 2: SOS MULHER (Disfarce de Farmácia)

**Número:** Instância "maringa-sos-mulher" na Evolution API
**Agente:** SEM NOME VISÍVEL — o número é salvo no celular da mulher como "Farmácia Municipal" ou "Drogaria"

#### Conceito

A mulher em situação de violência manda uma palavra-código curta. O sistema dispara alerta de emergência em menos de 2 segundos. O agressor não percebe porque as mensagens parecem ser com uma farmácia.

**Nenhuma cidade do Brasil tem isso.**

#### Códigos de emergência (configuráveis)

```
"."  "oi"  "1"  "socorro"  "me ajuda"  "ajuda"  "femi"  "sos"
```

Qualquer mensagem que NÃO seja código → resposta de farmácia:
```
"Olá! 😊 Farmácia Municipal. Funcionamos de seg a sex, 8h às 18h."
"Boa tarde! Para consultar medicamentos, envie o nome do remédio. 💊"
```

#### Fluxo de emergência

```
Mulher manda "." (ou qualquer código)
       ↓
[< 2 SEGUNDOS] Sistema detecta → dispara ALERTA VERMELHO
       ↓
Painel: tela vermelha pulsante + SOM DE SIRENE
       ↓
Resposta discreta: "✓ Recebido. Se puder, 📎 > Localização"
       ↓
WhatsApp da equipe: mensagem com todos os dados da vítima
       ↓
Se enviou localização → mapa atualiza em tempo real
       ↓
Operador aciona: PM (190), Guarda (153), contato de confiança
```

#### Cadastro prévio da mulher

Pelo WhatsApp (fluxo guiado), no CRAS ou Delegacia da Mulher. Manda "cadastro" e o bot guia:
- Nome completo (obrigatório)
- Endereço de residência (obrigatório)
- Ponto de referência
- Nome do agressor (opcional)
- Contato de confiança: nome + telefone

Mulher NÃO cadastrada também dispara alerta — só terá menos informações no painel.

#### Prioridade absoluta

Se a mulher estiver no meio do cadastro e mandar código de emergência → **abandona o cadastro e dispara a emergência**. Emergência > tudo.

#### LGPD e segurança

- Dados da vítima criptografados
- Acesso RESTRITO à equipe de emergência (RLS no Supabase)
- CPF e dados bancários NUNCA neste módulo
- DPA assinado com a prefeitura
- O nome do contato no celular da mulher é "Farmácia Municipal" (orientação na campanha)

---

### CANAL 3: OCORRÊNCIAS / CATÁSTROFES (Clara Emergência)

**Número:** Instância "maringa-ocorrencias" na Evolution API
**Agente:** Clara Emergência — tom direto, ágil, focado em resolver

#### O problema que resolve

Quando uma árvore cai em Maringá, 10 pessoas ligam pro 153 e abrem 10 protocolos pro mesmo incidente. A IA agrupa automaticamente por endereço.

#### Categorias

| Categoria | Emoji | Palavras-chave |
|---|---|---|
| Queda de árvore | 🌳 | árvore caiu, galho, tronco, árvore caída |
| Enchente/Alagamento | 🌊 | enchente, alagamento, água, inundação |
| Deslizamento | ⛰️ | deslizamento, barreira, morro, terra |
| Buraco na via | 🕳️ | buraco, cratera, asfalto |
| Poste/Iluminação | 💡 | poste caiu, sem luz, escuro |
| Incêndio | 🔥 | fogo, incêndio, queimada, fumaça |
| Vendaval | 🌪️ | vendaval, vento, telhado voou, tempestade |
| Acidente | 🚗 | acidente, batida, capotou |

#### Agrupamento inteligente (CRÍTICO)

Quando chega um relato, o sistema:

1. IA identifica a categoria pela mensagem
2. Pede o endereço: "Pode me dizer a rua e o bairro?"
3. **Busca no banco:** existe ocorrência ATIVA com a mesma categoria + mesmo endereço (ou endereço próximo) nas últimas 6 horas?

**Se NÃO existe** → cria nova ocorrência + protocolo:
```
Clara: "Protocolo MGA-2026-XXXXX aberto para queda de árvore 
na Rua das Palmeiras, Zona 5. Equipe sendo notificada. 
Se puder, envie foto e localização."
```

**Se JÁ existe** → agrupa o relato na ocorrência existente:
```
Clara: "Já recebemos outros relatos sobre essa ocorrência na 
Rua das Palmeiras, Zona 5. Equipe já está a caminho! 
Protocolo: MGA-2026-XXXXX. Obrigada por informar!"
```

#### Critérios de agrupamento

- **Mesmo endereço textual:** rua + bairro iguais (normalização: remover acentos, lowercase, tratar abreviações "Av." = "Avenida")
- **GPS próximo:** se ambos os relatos têm coordenadas, agrupar se distância < 500 metros (Haversine)
- **Mesma categoria:** só agrupa relatos da mesma categoria
- **Janela de tempo:** últimas 6 horas. Depois disso, nova ocorrência.

#### Severidade automática

| Relatos agrupados | Severidade | Cor no painel |
|---|---|---|
| 1 | Baixa | 🟡 Amarelo |
| 3+ | Média | 🟠 Laranja |
| 5+ | Alta | 🔴 Vermelho |
| 10+ | Crítica | 🔴 Vermelho pulsante + SOM |

Quando a severidade sobe para ALTA ou CRÍTICA → som de alerta no painel + notificação no grupo WhatsApp.

#### Indicador de economia

No painel, cada ocorrência mostra: "12 relatos agrupados nesta ocorrência — 11 protocolos duplicados evitados". Isso é dado de ouro pra justificar o investimento pro Secretário.

---

## 5. O DASHBOARD (Central de Comando)

### Filosofia de design

- **Projetado para tela de 50"** montada numa central de operações
- **Fundo escuro** (dark mode) — operadores de plantão, 24/7
- **Cards GRANDES** com letras GRANDES — visível a 3 metros de distância
- **Mapa CENTRAL** — ocupa pelo menos metade da tela
- **Sons e alertas visuais** — impossível ignorar uma emergência
- **NÃO é o dashboard padrão do Node Data** — é completamente customizado

### Navegação principal (abas no topo ou lateral)

```
📊 CENTRAL     → Visão geral com mapa + KPIs consolidados
📋 DENÚNCIAS   → Feed de denúncias do Cidadania Ativa
🛡️ SOS MULHER  → Painel de emergência (prioridade visual máxima)
🌳 OCORRÊNCIAS → Mapa de incidentes com agrupamento
📈 RELATÓRIOS  → Estatísticas e exportação
⚙️ CONFIG      → Códigos SOS, categorias, equipe
```

### Aba CENTRAL (tela principal)

Layout dividido:

```
┌──────────────────────────────────────────────────────┐
│  HEADER: Logo + relógio + status de conexão          │
├──────────┬───────────────────────────┬───────────────┤
│          │                           │               │
│  KPIs    │      MAPA DA CIDADE       │  Feed ao vivo │
│  grandes │    (Leaflet, tela cheia)  │  (últimos     │
│          │    marcadores coloridos   │   eventos)    │
│  4 cards │    por tipo e severidade  │               │
│          │                           │  Cards rolando│
│          │    Mapa de calor overlay  │  com preview  │
│          │                           │               │
├──────────┴───────────────────────────┴───────────────┤
│  BARRA INFERIOR: Alertas ativos + SOS Mulher (fixo)  │
└──────────────────────────────────────────────────────┘
```

#### KPIs (cards grandes, fonte 48pt+)

- 🚨 **Alertas SOS ativos** (vermelho pulsante se > 0)
- 📋 **Denúncias hoje** (com mini-gráfico de tendência)
- 🌳 **Ocorrências abertas** (com severidade máxima)
- ⏱️ **Tempo médio de resposta** (meta: < 15 minutos)

#### Mapa da cidade

- Tiles: **CartoDB Dark Matter** (tema escuro, gratuito)
- Marcadores coloridos por tipo (emoji + cor da categoria)
- Tamanho do marcador = severidade (maior = mais grave)
- Marcadores PULSAM se status = ativo
- Clique no marcador → popup com detalhes
- Mapa de calor overlay (toggle) mostrando concentração de ocorrências por bairro
- Círculo de raio (500m) ao redor de cada ocorrência agrupada

#### Feed ao vivo (lado direito)

Cards rolando de baixo pra cima, estilo "ticker":
- Cada card mostra: emoji da categoria, endereço resumido, há quanto tempo
- Se for SOS Mulher → card VERMELHO com destaque máximo
- Clique no card → abre o detalhe

#### Barra inferior fixa (ALERTA SEMPRE VISÍVEL)

Se existe alerta SOS Mulher ativo → barra vermelha pulsante com texto:
```
🛡️ ALERTA SOS MULHER ATIVO — Maria Silva — Jd. Alvorada — 2min atrás — [CLIQUE PARA DETALHES]
```
Se não tem alerta → barra discreta: "✅ Nenhum alerta SOS ativo"

### Aba SOS MULHER (prioridade visual máxima)

Quando entra nesta aba com alerta ativo:
- **FUNDO VERMELHO pulsante** (toda a tela)
- **SOM DE SIRENE** (3 bipes, repete a cada 30 segundos até ser aceito)
- **Dados da vítima em fonte GIGANTE** (nome, endereço, agressor)
- **Mapa com localização** (se disponível)
- **Botões enormes:** "ACIONAR PM" / "GUARDA MUNICIPAL" / "LIGAR VÍTIMA"
- **Histórico de reincidência** em destaque laranja
- **Botão:** "Aceitar Atendimento" → para o som, muda pra status EM ATENDIMENTO

### Aba DENÚNCIAS

- Lista de cards grandes com preview de foto/vídeo
- Cada card: categoria (badge colorido), texto resumido, bairro, hora, foto (miniatura)
- Clique → abre detalhe com foto grande, texto completo, mapa, dados do cidadão
- Filtros: por categoria, por bairro, por status, por período
- Status workflow: Novo → Em análise → Encaminhado → Procedente → Recompensa paga / Improcedente
- Flag visual se é elegível pro Cidadania Ativa ($ ao lado)

### Aba OCORRÊNCIAS

- **Mapa em tela cheia** com todas as ocorrências ativas
- Lista lateral com as ocorrências ordenadas por severidade (mais grave primeiro)
- Cada ocorrência mostra:
  - Emoji + categoria
  - Endereço
  - Total de relatos agrupados ("7 cidadãos reportaram")
  - Severidade (badge colorido)
  - Protocolo
  - Status
  - **"11 protocolos duplicados evitados"** ← isso é dado pra justificar o investimento
- Clique na ocorrência → timeline de relatos: quem mandou, quando, o que disse, fotos
- Som de alerta quando severidade sobe para ALTA ou CRÍTICA

### Sons e alertas (Web Audio API)

| Evento | Som | Volume |
|---|---|---|
| SOS Mulher — novo alerta | Sirene 3 bipes, repete a cada 30s | Alto |
| SOS Mulher — localização recebida | Bipe curto confirmação | Médio |
| Denúncia — nova denúncia urgente | Bipe duplo | Médio |
| Ocorrência — severidade subiu para CRÍTICA | Alerta longo | Alto |
| Ocorrência — nova ocorrência | Bipe suave | Baixo |

Implementar com Web Audio API (gera o som sem arquivo MP3). Operador pode mutar com toggle no header.

---

## 6. BANCO DE DADOS (Supabase)

### Tabela: `denuncias`

```sql
CREATE TABLE denuncias (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  protocolo TEXT NOT NULL UNIQUE,          -- MGA-2026-XXXXX
  telefone TEXT NOT NULL,
  nome TEXT,
  cpf_encrypted TEXT,                      -- AES-256 encriptado, NÃO plaintext
  dados_bancarios_encrypted TEXT,          -- AES-256 encriptado
  categoria TEXT NOT NULL,                 -- pichacao, trafico, lixo, vandalismo, depredacao
  mensagem TEXT NOT NULL,
  midia_urls TEXT[],                       -- Array de URLs (pode ter várias fotos)
  bairro TEXT,
  endereco TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  cidadania_ativa BOOLEAN DEFAULT false,
  status TEXT DEFAULT 'novo',              -- novo, em_analise, encaminhado, procedente, improcedente, recompensa_paga
  valor_recompensa DECIMAL(10,2),
  operador TEXT,
  notas TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_denuncias_status ON denuncias(status);
CREATE INDEX idx_denuncias_categoria ON denuncias(categoria);
CREATE INDEX idx_denuncias_bairro ON denuncias(bairro);
CREATE INDEX idx_denuncias_created ON denuncias(created_at DESC);

ALTER PUBLICATION supabase_realtime ADD TABLE denuncias;
```

### Tabela: `sos_cadastros`

```sql
CREATE TABLE sos_cadastros (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  telefone TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL,
  endereco TEXT,
  referencia TEXT,
  agressor TEXT,
  contato_confianca_nome TEXT,
  contato_confianca_telefone TEXT,
  foto_url TEXT,
  ativo BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_sos_cadastros_telefone ON sos_cadastros(telefone);
```

### Tabela: `sos_alertas`

```sql
CREATE TABLE sos_alertas (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  cadastro_id UUID REFERENCES sos_cadastros(id),
  telefone TEXT NOT NULL,
  codigo_usado TEXT NOT NULL,
  status TEXT DEFAULT 'active',            -- active, attending, resolved
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  localizacao_realtime BOOLEAN DEFAULT false,
  atendido_por TEXT,
  notas TEXT,
  resolvido_em TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_sos_alertas_status ON sos_alertas(status);
CREATE INDEX idx_sos_alertas_telefone ON sos_alertas(telefone);
CREATE INDEX idx_sos_alertas_created ON sos_alertas(created_at DESC);

ALTER PUBLICATION supabase_realtime ADD TABLE sos_alertas;
```

### Tabela: `ocorrencias`

```sql
CREATE TABLE ocorrencias (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  protocolo TEXT NOT NULL UNIQUE,
  categoria TEXT NOT NULL,                 -- queda_arvore, enchente, buraco, poste, incendio, vendaval, acidente
  severidade TEXT DEFAULT 'baixa',         -- baixa, media, alta, critica
  status TEXT DEFAULT 'aberto',            -- aberto, equipe_caminho, atendimento, resolvido
  titulo TEXT,                             -- "🌳 Queda de árvore - Rua das Palmeiras, Zona 5"
  endereco TEXT NOT NULL,
  endereco_normalizado TEXT NOT NULL,      -- lowercase, sem acentos, pra agrupamento
  bairro TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  total_relatos INTEGER DEFAULT 1,
  equipe TEXT,
  operador TEXT,
  notas TEXT,
  resolvido_em TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_ocorrencias_status ON ocorrencias(status);
CREATE INDEX idx_ocorrencias_categoria ON ocorrencias(categoria);
CREATE INDEX idx_ocorrencias_endereco_norm ON ocorrencias(endereco_normalizado);
CREATE INDEX idx_ocorrencias_created ON ocorrencias(created_at DESC);

ALTER PUBLICATION supabase_realtime ADD TABLE ocorrencias;
```

### Tabela: `ocorrencias_relatos`

```sql
CREATE TABLE ocorrencias_relatos (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  ocorrencia_id UUID NOT NULL REFERENCES ocorrencias(id),
  telefone TEXT NOT NULL,
  nome TEXT,
  mensagem TEXT,
  midia_urls TEXT[],
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_relatos_ocorrencia ON ocorrencias_relatos(ocorrencia_id);

ALTER PUBLICATION supabase_realtime ADD TABLE ocorrencias_relatos;
```

### Tabela: `audit_log` (auditoria de TUDO)

```sql
CREATE TABLE audit_log (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  tabela TEXT NOT NULL,
  registro_id UUID NOT NULL,
  acao TEXT NOT NULL,                      -- create, update, delete, view_sensitive
  operador TEXT,
  dados_antes JSONB,
  dados_depois JSONB,
  ip TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_audit_created ON audit_log(created_at DESC);
```

### RLS (Row Level Security)

Ativar RLS em TODAS as tabelas. Policies:
- Operadores autenticados: SELECT, UPDATE nas tabelas de sua área
- Campos sensíveis (cpf_encrypted, dados_bancarios_encrypted): política separada, só role "admin_financeiro"
- Tabela audit_log: INSERT pra todos, SELECT só pra admin
- Nenhum acesso público (anon) a nenhuma tabela

---

## 7. REDIS — Sessões, Cache e Filas

### O que o Redis faz neste projeto

| Uso | Chave | TTL | Descrição |
|---|---|---|---|
| Rate limiting | `rate:{telefone}` | 60s | Contador de mensagens por minuto |
| Deduplicação | `dedup:{hash}` | 60s | Evita processar a mesma mensagem 2x |
| Sessão de cadastro SOS | `sos_session:{telefone}` | 1800s | Etapa do cadastro da mulher |
| Sessão de denúncia | `den_session:{telefone}` | 1800s | Etapa da denúncia (aguardando foto, etc.) |
| Fila de processamento | `queue:denuncias`, `queue:sos`, `queue:ocorrencias` | — | Mensagens aguardando processamento |
| Cache de ocorrências ativas | `ocorrencias_ativas:{bairro}` | 300s | Pra agrupamento rápido (evita query no banco toda vez) |

---

## 8. EVOLUTION API — 3 Instâncias

```
Instância 1: maringa-denuncias
  → Webhook: https://api.nodedata.com.br/webhook/denuncias
  → Eventos: MESSAGES_UPSERT

Instância 2: maringa-sos-mulher
  → Webhook: https://api.nodedata.com.br/webhook/sos-mulher
  → Eventos: MESSAGES_UPSERT

Instância 3: maringa-ocorrencias
  → Webhook: https://api.nodedata.com.br/webhook/ocorrencias
  → Eventos: MESSAGES_UPSERT
```

Cada webhook valida o header `apikey` da Evolution API. Se inválido → rejeita com 401.

---

## 9. PROTOCOLO DE NUMERAÇÃO

Formato: `MGA-{ANO}-{SEQUENCIAL:5 dígitos}`

Exemplos:
- `MGA-2026-00001` (primeira denúncia)
- `MGA-2026-00342` (342ª ocorrência)

Sequencial global (não por módulo). Usar sequence no PostgreSQL:

```sql
CREATE SEQUENCE protocolo_seq START 1;
```

Gerar: `MGA-2026-` + `lpad(nextval('protocolo_seq')::text, 5, '0')`

---

## 10. REGRAS DE NEGÓCIO (INVIOLÁVEIS)

1. **SOS Mulher tem prioridade absoluta sobre TUDO.** Se processar SOS leva 1 segundo e denúncia leva 5, SOS vai na frente da fila.

2. **Agrupamento de ocorrências é obrigatório.** Mesma rua + mesma categoria + últimas 6h = mesma ocorrência. Sem isso, o projeto perde o argumento principal de venda.

3. **Mídia é obrigatória para recompensa.** Denúncia sem foto/vídeo é registrada mas NÃO elegível.

4. **Dados sensíveis NUNCA em plaintext.** CPF e dados bancários são AES-256 encriptados. Dados de vítimas SOS têm acesso restrito por RLS.

5. **Nenhuma mensagem pode se perder.** A fila Redis garante isso. Se o worker cair, as mensagens ficam na fila e são processadas quando voltar.

6. **O dashboard precisa funcionar em tela de 50".** Fontes grandes, cards grandes, clicável com mouse a 3 metros. Nada de fontes 12px.

7. **3 números, 3 webhooks, 3 lógicas.** Nunca misturar. Se uma instância cair, as outras continuam.

8. **Rate limit em tudo.** Por telefone, por IP, global. Logar tentativas de abuso.

9. **Audit log de tudo.** Quem viu os dados da vítima, quem mudou o status, quem acessou CPF. Tudo logado.

10. **Clara NUNCA manda primeira mensagem.** Cidadão sempre inicia.