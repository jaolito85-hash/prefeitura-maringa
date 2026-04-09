# Node Data — Plataforma de Gestão Urbana e Segurança Pública

## O que é este projeto

Plataforma de gestão urbana com IA desenvolvida pela **Node Data Tecnologia Ltda** (CNPJ 65.705.831/0001-04), sediada em Sumaré, SP.

O projeto está em fase de **POC (Prova de Conceito) de 3 meses** com a **Prefeitura de Maringá, PR**, operando sob o **Decreto Municipal 291/2026 (Programa Cidadão Ativo)**, contratado via **Marco Legal das Startups (Lei Complementar 182/2021)**.

O núcleo da plataforma é a **Clara**, assistente de IA que recebe denúncias, emergências e solicitações dos cidadãos via WhatsApp, classifica automaticamente e encaminha para os órgãos municipais corretos.

---

## Módulos da plataforma

- **Cidadão Ativo** — cidadão envia foto/texto via WhatsApp → Clara classifica com GPT-4o Vision → encaminha para secretaria ou órgão competente
- **SOS Mulher** — mulher em situação de risco envia um "." pelo WhatsApp → sistema ativa rastreamento GPS silencioso e aciona Guarda Municipal
- **Arborização Urbana** — pipeline de 8 agentes de IA para gestão do inventário de árvores da cidade
- **Radar de Notícias** — monitoramento de mídia com clusterização de temas por relevância
- **Radar de Segurança** — inteligência de ocorrências com mapa de calor e clustering geoespacial

---

## Órgãos de destino das ocorrências

- Guarda Municipal (153)
- SAMU (192)
- Polícia Militar (190)
- Defesa Civil
- Secretarias municipais (obras, saúde, meio ambiente, etc.)

---

## Stack técnico

### Frontend
- React 18 via CDN (sem build step)
- Babel standalone
- Mapbox GL JS (mapas em tempo real)
- Tailwind CSS + CSS puro
- Arquitetura single `index.html`

### Backend
- Python + Flask
- Redis (filas de processamento)
- Supabase (PostgreSQL + Auth + Storage)

### IA
- GPT-4o Vision — classificação de fotos e processamento de denúncias
- Claude API (Anthropic) — agentes especializados e pipeline de arborização

### WhatsApp
- Evolution API (self-hosted no VPS)
- WhatsApp Business API (Meta oficial)

### Infraestrutura
- VPS Hostinger com Coolify
- Vercel (frontend)
- GitHub: `jaolito85-hash/site-prefeituras`
- Domínio: nodedata.com.br (Hostinger)
- DNS/CDN: Cloudflare

### Geração de documentos
- Python + ReportLab (PDFs A4, largura 170mm)

---

## Regras e padrões do projeto

### Código
- Todo frontend novo deve ser single-file (`index.html`) sem build step
- Nunca usar `localStorage` ou `sessionStorage`
- Mapas sempre com Mapbox GL JS
- Arquivos grandes nunca devem passar pelo deploy do Cloudflare — usar GitHub API diretamente
- CSS: estética **sober, institucional, governamental** — sem emojis, sem cores vibrantes, sem estética de gaming

### Dados e segurança
- Dados operacionais (ocorrências, mapa) ficam no painel principal
- Dados sensíveis (CPF, dados bancários) ficam em servidor isolado — dois layers de proteção LGPD
- Denúncias anônimas **nunca** aparecem na aba de Recompensas

### Pitch e apresentação
- Nunca incluir métricas inventadas em apresentações
- Nunca revelar custo interno ao cliente
- Argumento de fechamento: focar no **custo de NÃO ter o sistema**, não no custo de ter
- Frase-chave da plataforma: *"A tecnologia vai onde o cidadão já está."*

### Geração de PDFs
- Sempre usar `Paragraph` com `ParagraphStyle` para células de tabela — nunca texto direto
- Largura de conteúdo: 170mm, margens de 20mm

---

## Contatos do projeto

- **João** — fundador e desenvolvedor principal | (11) 93622-0172
- **Email comercial:** prefeituras@nodedata.com.br
- **Site:** nodedata.com.br

### Contatos em Maringá
- **Sandra Jacovós** — Prefeita em exercício
- **Luiz Alves** — Secretário de Segurança Pública
- **Decreto de referência:** 291/2026 (Programa Cidadão Ativo)

---

## Integrações em avaliação (próximos passos)

- **SINESP CAD** — sistema federal de despacho de emergências
- **SINESP PPe** — policiamento preditivo
- **CCONet (CPN Informática)** — sistema de controle operacional municipal
- **Linha 153** — central da Guarda Municipal de Maringá
- **B.O. automático** — geração de Boletim de Ocorrência a partir de denúncias classificadas pela Clara

---

## Workflow de desenvolvimento

1. Criar arquivo de referência HTML + arquivo `.md` com instruções na raiz do projeto
2. Rodar `claude` ou `hermes` na pasta
3. Colar instrução referenciando ambos os arquivos
4. Confirmar push com `sim`
5. Deletar arquivos de referência após o push

---

## Prioridades atuais

1. Finalizar integração com a linha 153 da Guarda Municipal
2. Definir fluxo de geração automática de B.O.
3. Usar Maringá como caso de estudo para escalar para outros municípios brasileiros
