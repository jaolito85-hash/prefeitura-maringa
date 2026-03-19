# 🛡️ Node Data Maringá — Plataforma de Segurança Pública

Central de Segurança Pública para a Prefeitura de Maringá-PR.
3 canais WhatsApp + Dashboard em tempo real para central de operações.

---

## ⚡ Como Rodar para o Demo (Guia Rápido)

### Passo 1 — Criar o projeto no Supabase

1. Acesse [supabase.com](https://supabase.com) e crie uma conta gratuita
2. Clique em **"New Project"** → dê um nome (ex: `maringa-seguranca`)
3. Aguarde o projeto ser criado (1-2 minutos)
4. Vá em **SQL Editor** → **New Query**
5. Cole o conteúdo do arquivo `supabase/migrations/001_create_tables.sql` → **Run**
6. Repita para `002_enable_realtime.sql`
7. Repita para `003_seed_demo_data.sql` (isso cria os dados do demo!)
8. Vá em **Project Settings > API** e copie:
   - `Project URL` → vai para `SUPABASE_URL`
   - `anon public` → vai para `VITE_SUPABASE_ANON_KEY` (frontend)
   - `service_role secret` → vai para `SUPABASE_SERVICE_KEY` (backend)

### Passo 2 — Configurar o Backend

```bash
cd backend

# Copie o arquivo de exemplo e preencha com seus dados
cp .env.example .env

# Instale as dependências
pip install -r requirements.txt

# Rode o servidor
uvicorn app.main:app --reload --port 8000
```

O backend estará em: **http://localhost:8000**
Documentação automática: **http://localhost:8000/docs**

### Passo 3 — Configurar o Frontend (Dashboard)

```bash
cd frontend

# Copie o arquivo de exemplo e preencha com seus dados do Supabase
cp .env.example .env

# Instale as dependências
npm install

# Rode o dashboard
npm run dev
```

O dashboard estará em: **http://localhost:3000** 🎉

---

## 📁 Estrutura do Projeto

```
maringa-seguranca/
├── backend/           ← Servidor Python FastAPI
├── frontend/          ← Dashboard React
├── supabase/
│   └── migrations/    ← Scripts SQL (execute nesta ordem no Supabase)
│       ├── 001_create_tables.sql      ← Cria todas as tabelas
│       ├── 002_enable_realtime.sql    ← Ativa atualização em tempo real
│       └── 003_seed_demo_data.sql     ← Dados realistas de Maringá
├── docker-compose.yml ← Rodar tudo com Docker
└── README.md
```

---

## 🖥️ O Dashboard

| Aba | Descrição |
|---|---|
| 📊 **CENTRAL** | Visão geral com mapa, KPIs e feed ao vivo |
| 📋 **DENÚNCIAS** | Denúncias do Programa Cidadania Ativa |
| 🛡️ **SOS MULHER** | Emergências — tela vermelha + sirene |
| 🌳 **OCORRÊNCIAS** | Incidentes agrupados por endereço |

---

## 💡 Dicas Importantes

### Onde trocar o estilo do mapa
Arquivo: `frontend/src/components/Map/CityMap.jsx`
Procure por `cartocdn.com/dark_all` — é o URL do tile do mapa.

### Onde trocar as fontes do dashboard
Arquivo: `frontend/src/styles/globals.css`
Adicione um `@import` do Google Fonts antes da linha `@tailwind base`.

### Onde adicionar novas categorias de ocorrência
Backend: `backend/app/services/ia_classifier.py` → dicionário `CATEGORIAS_OCORRENCIAS`
Frontend: `frontend/src/pages/Ocorrencias.jsx` → objeto `CATEGORIA_INFO`

### Como simular um alerta SOS para o demo
No Supabase SQL Editor:
```sql
INSERT INTO sos_alertas (telefone, codigo_usado, status)
VALUES ('44999990001', '.', 'active');
```
O dashboard ficará vermelho automaticamente em menos de 2 segundos!

---

## 🔒 Segurança (checklist antes do go-live)

- [ ] Ativar RLS em todas as tabelas (SQL em `supabase/migrations/004_rls_policies.sql` — a criar)
- [ ] Configurar autenticação de operadores no Supabase Auth
- [ ] Adicionar HTTPS no Coolify (certificado automático)
- [ ] Configurar variáveis de ambiente no Coolify (não no código!)
- [ ] Configurar UptimeRobot: https://uptimerobot.com

---

## 📞 Canais WhatsApp (Evolution API)

Após o demo, para conectar os 3 números reais:

1. Instale a Evolution API no servidor
2. Crie 3 instâncias: `maringa-denuncias`, `maringa-sos-mulher`, `maringa-ocorrencias`
3. Conecte cada número escaneando o QR Code
4. Configure os webhooks apontando para o backend:
   - `POST https://api.seudominio.com.br/webhook/denuncias`
   - `POST https://api.seudominio.com.br/webhook/sos-mulher`
   - `POST https://api.seudominio.com.br/webhook/ocorrencias`
