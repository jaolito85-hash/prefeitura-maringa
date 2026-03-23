# TAREFA: Integrar Rastreamento GPS ao Node Mulher Segura

## CONTEXTO

Já temos funcionando:
- **Página de rastreamento** (`mulher-segura.html`) — a vítima abre no celular, o GPS rastreia e faz POST no Supabase a cada poucos segundos
- **Painel de monitoramento** (`monitor-sos.html`) — mostra no mapa ao vivo a trilha da vítima com Mapbox
- **Tabelas no Supabase** — `emergencia_sessoes` e `emergencia_pontos` já existem e funcionam

O que falta é **conectar tudo ao fluxo do WhatsApp**: quando a mulher manda "." ou "socorro", o bot cria a sessão, manda o link, e o dashboard mostra o rastreamento.

---

## TABELAS JÁ EXISTENTES NO SUPABASE

```sql
-- Sessões de emergência (uma por pedido de socorro)
emergencia_sessoes (
  id UUID PRIMARY KEY,
  token VARCHAR(12) UNIQUE NOT NULL,
  telefone VARCHAR(20) NOT NULL,
  nome VARCHAR(100),
  status VARCHAR(20) DEFAULT 'ativa',
  created_at TIMESTAMPTZ DEFAULT now(),
  closed_at TIMESTAMPTZ
);

-- Pontos GPS (vários por sessão)
emergencia_pontos (
  id UUID PRIMARY KEY,
  sessao_id UUID REFERENCES emergencia_sessoes(id),
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  precisao_metros INTEGER,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

RLS está habilitado. Policies de INSERT e SELECT anônimo já existem.
Realtime está habilitado em `emergencia_pontos`.

---

## O QUE PRECISA SER FEITO

### 1. BACKEND — Worker: Criar sessão ao receber SOS

No arquivo `backend/worker.py`, na função `processar_sos()`, quando um novo alerta SOS é criado:

**DEPOIS** de criar o registro em `sos_alertas`, adicionar:

```python
import secrets

# Gerar token único para rastreamento GPS
token_rastreamento = secrets.token_urlsafe(8)[:10]  # 10 chars, URL-safe

# Criar sessão de rastreamento
sb.table("emergencia_sessoes").insert({
    "token": token_rastreamento,
    "telefone": telefone,
    "nome": nome_cadastro or "Não identificada",
    "status": "ativa",
}).execute()

# Montar link de rastreamento
# IMPORTANTE: usar o domínio real do projeto
DOMINIO = "maringa.nodedata.com.br"
link_rastreamento = f"https://{DOMINIO}/mulher-segura.html?t={token_rastreamento}"

# Enviar link discreto pelo WhatsApp (após a mensagem de confirmação)
enviar_whatsapp(telefone, f"📍 {link_rastreamento}")
```

**IMPORTANTE**: O link deve ser enviado LOGO APÓS a mensagem de confirmação do SOS ("✓ Recebido. Equipe acionada."). A mulher clica no link e o rastreamento começa automaticamente.

### 2. BACKEND — Worker: Atualizar sos_alertas com link

Adicionar campo `link_rastreamento` no INSERT do `sos_alertas` para o dashboard saber qual link mandar:

```python
# No INSERT de sos_alertas, adicionar:
"token_rastreamento": token_rastreamento,
```

**OU** salvar o token diretamente na tabela `sos_alertas`. Para isso, criar uma migration:

```sql
ALTER TABLE sos_alertas ADD COLUMN IF NOT EXISTS token_rastreamento VARCHAR(12);
```

### 3. FRONTEND — Dashboard: Botão "Ver Rastreamento" no SOS Mulher

No arquivo `frontend/index.html`, na seção do SOS Mulher (dentro da div que mostra os dados da vítima), adicionar um botão que abre o monitor:

```jsx
{/* Botão de rastreamento — aparece se tem token */}
{sel.token_rastreamento && (
  <a href={`/monitor-sos.html?t=${sel.token_rastreamento}`}
     target="_blank" rel="noopener"
     className="btn btn-primary"
     style={{width:'100%',justifyContent:'center',fontSize:14,padding:'12px 20px',textDecoration:'none',marginTop:8}}>
    📍 Ver Rastreamento ao Vivo no Mapa
  </a>
)}
```

Colocar isso na área de **ações rápidas** do painel lateral do SOS, junto com os botões de WhatsApp e ligar.

### 4. BACKEND — API: Retornar token_rastreamento nos alertas

No arquivo `backend/app/api/sos.py`, garantir que o SELECT dos alertas inclui o campo `token_rastreamento`:

```python
# Em listar_alertas_sos() e alertas_sos_ativos():
# O select("*") já pega tudo, mas se tiver select específico, adicionar token_rastreamento
```

### 5. ARQUIVOS ESTÁTICOS — Garantir que as páginas existem no container

Os arquivos `mulher-segura.html` e `monitor-sos.html` precisam estar em `/usr/share/nginx/html/` no container do frontend.

**Opção A (recomendada)**: Copiar os arquivos para a pasta `frontend/` do repositório e atualizar o Dockerfile:

```dockerfile
FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
COPY mulher-segura.html /usr/share/nginx/html/mulher-segura.html
COPY monitor-sos.html /usr/share/nginx/html/monitor-sos.html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

**Opção B (provisória)**: docker cp após cada deploy (não recomendado pra produção).

### 6. LIMPEZA — Apagar dados de teste

```sql
DELETE FROM emergencia_pontos;
DELETE FROM emergencia_sessoes;
```

---

## ARQUIVOS HTML JÁ PRONTOS

Os dois arquivos HTML já estão no VPS em `/var/www/html/`:
- `mulher-segura.html` — página que a vítima abre (rastreamento GPS)
- `monitor-sos.html` — painel com mapa ao vivo (operador/polícia vê)

Copiar esses arquivos para a pasta `frontend/` do repositório do projeto.

As credenciais do Supabase e Mapbox já estão hardcoded nesses HTMLs:
- Supabase URL: `https://kuhtndyhuddjpqimuijn.supabase.co`
- Supabase Anon Key: já está no arquivo
- Mapbox Token: já está no arquivo (mesmo do dashboard principal)

---

## FLUXO COMPLETO ESPERADO

```
1. Mulher manda "." pelo WhatsApp
2. Worker detecta SOS → cria sos_alertas
3. Worker cria emergencia_sessoes com token único
4. Worker envia: "✓ Recebido. Equipe acionada."
5. Worker envia: "📍 https://maringa.nodedata.com.br/mulher-segura.html?t=abc123"
6. Mulher clica no link → página abre → GPS começa a rastrear
7. Cada ponto GPS faz POST em emergencia_pontos
8. Dashboard SOS Mulher mostra botão "Ver Rastreamento"
9. Operador clica → abre monitor-sos.html com mapa ao vivo
10. Trilha rosa aparece no mapa em tempo real
```

---

## REGRAS IMPORTANTES

- O link de rastreamento deve ser CURTO e DISCRETO (a mulher pode estar em perigo)
- Cada SOS gera um token ÚNICO — nunca reutilizar tokens
- O rastreamento funciona enquanto a página estiver aberta no celular
- Se a mulher fechar o navegador, o rastreamento para (mas os dados já salvos permanecem)
- O monitor-sos.html faz polling a cada 3 segundos (não usa WebSocket)
- Toda a comunicação é HTTPS (GPS só funciona em HTTPS)

---

## PRIORIDADE DE EXECUÇÃO

1. Migration SQL (adicionar token_rastreamento ao sos_alertas)
2. Copiar HTMLs pro repositório + atualizar Dockerfile
3. Alterar worker.py (criar sessão + enviar link)
4. Alterar sos.py (retornar token nos alertas)
5. Alterar frontend/index.html (botão "Ver Rastreamento")
6. Limpar dados de teste
7. Testar fluxo completo
