# Roteiro & Checklist da Demo — Secretário de Segurança (30/06/2026)
### Verificação ponta a ponta · preparado em 29/06/2026 · uso interno (NÃO mostrar ao secretário)

> **Veredito geral:** ✅ **Pronto para apresentar** as abas Denúncias, Recompensas e SOS Mulher. Sistema no ar, banco saudável, fluxo íntegro ponta a ponta. Os **3 maiores riscos de roteiro foram corrigidos** (ver abaixo). Os riscos restantes são menores e contornáveis.

---

## ⚙️ Ajustes aplicados em 29/06 (autorizados)

| # | Ajuste | Onde | Vale a partir de |
|---|---|---|---|
| 1 | Abas **Denúncias e Recompensas abrem em "Total"** (não mais "Mês") | `frontend/index.html` (L2648, L4447) | **Após redeploy no Coolify** |
| 2 | **Aba SOS visível no modo apresentação 🎬** + sirene dispara ao entrar nela | `frontend/index.html` (L5710, L5693) | **Após redeploy no Coolify** |
| 3 | **3 recompensas "validada" → "aguardando pagamento"** (R$ 750 destravados) | Banco (Supabase) | **Já valendo** |

> ⚠️ **IMPORTANTE — os ajustes 1 e 2 são de frontend.** Para valerem em produção (`maringa.nodedata.com.br`) é preciso **commit + push** e **redeploy no Coolify**, depois **Ctrl+Shift+R** no navegador. O ajuste 3 (banco) já está valendo, pois é o mesmo Supabase.

---

## 🔴 Regras de ouro (já com os ajustes)

1. **Login válido** antes de tudo — sem sessão, `/api` retorna vazio. Use `joao@nodedata.com.br` (admin, vê tudo) ou `financeiro@nodedata.com.br` (só Recompensas).
2. **Clique uma vez na página assim que abrir** — destrava o áudio do navegador (a 1ª sirene só sai após uma interação).
3. **Modo apresentação 🎬** agora mostra **Denúncias + Recompensas + SOS** e mantém a sirene quieta nas duas primeiras, disparando só ao entrar no SOS. Pode usá-lo o tempo todo.
4. Se preferir ficar **fora** do modo apresentação, lembre que a sirene toca a cada 15s enquanto houver alerta ativo — controle com **🔇**.

---

## ✅ Checklist 10 min antes

- [ ] **Redeploy do frontend feito no Coolify** e página recarregada com **Ctrl+Shift+R** (senão os ajustes 1 e 2 não aparecem).
- [ ] **Login válido** no painel.
- [ ] Clicar uma vez na tela (destrava áudio).
- [ ] **Denúncias** abre já cheia (≈165 cards). Se aparecer "Mês", confirme que o deploy passou.
- [ ] **Recompensas** abre já cheia (R$ 3.090 pagos, 9 aguardando pagamento somando R$ 2.030).
- [ ] **SOS Mulher** mostra o alerta ativo da **Marcia Aparecida** (tela vermelha) e a sirene dispara ao entrar.
- [ ] Decidir o estado do **🎬** (com ele, as 3 abas; sem ele, todas — e sirene a cada 15s).
- [ ] (Opcional) Protocolo **MGA-2026-00727** à mão para a consulta de status.

---

## 🎬 Roteiro sugerido

### 1) Aba DENÚNCIAS
- Abre direto no volume (≈165), cards com **foto**, categoria e status.
- Abrir 1 card com foto → painel de detalhe com a evidência e a localização.
- Mostrar a **ponte para recompensa** numa denúncia elegível **com CPF/PIX cadastrados** (botão "Validar recompensa").
- **Evite os filtros de status** (o "Encaminhado" mostra só 8 de 29; não há filtro para "Paga"). Navegue na lista completa. **Não** clique em "✓ Procedente" numa denúncia já marcada como *recompensa paga* (rebaixaria o status).

### 2) Aba RECOMPENSAS
- Abre no painel financeiro completo: **total pago R$ 3.090** (28), aguardando pagamento **R$ 2.030** (9), pendentes **R$ 4.470** (29).
- Pegar uma **"Pendente de validação"** → **Validar** → vira "Aguardando pagamento".
- Numa **"Aguardando pagamento"** → preencher empenho/dotação → **Pagar** → vira "Paga". *(As 3 ex-"validada" — MGA-2026-00513, 00521, 00559 — agora pagam normalmente.)*
- Numa **"Paga"** → **gerar o Termo de Recompensa em PDF** (ótimo visual: brasão + Decreto 291/2026).
- Obs.: o nº de empenho digitado num pagamento **ao vivo** ainda não é persistido (bug de média prioridade) — para o Termo sair completo, gere-o a partir de uma recompensa **já paga** do ambiente.

### 3) Aba SOS MULHER
- **Tela vermelha** com o alerta ativo: vítima **Marcia Aparecida**, endereço Av. Colombo, **agressor Rafael da Silva (com foto)**, contato de confiança, **medida protetiva** sinalizada. A sirene dispara ao entrar.
- Demonstrar o **ciclo**: "Aceitar Atendimento" (vira *Em atendimento*) → "Resolver" (sai dos ativos). ⚠️ "Aceitar" **não** cala a sirene — para silenciar use **🔇** ou **Resolver**.
- **Rastreamento GPS:** o alerta ativo tem trilha curta. Para uma **trilha rica ao vivo**, dispare um SOS de teste de um celular (envie "." ao WhatsApp e abra o link de localização).
- Botões **190/153**: explique que acionam PM/Guarda; num notebook sem telefonia o clique só abre o discador — melhor **falar** do que clicar.

---

## 🧪 O que está sólido (confirmado na verificação)

- **Produção no ar** (`https://maringa.nodedata.com.br`) e **banco saudável** (Supabase ACTIVE_HEALTHY).
- **Fluxo ponta a ponta** WhatsApp → IA → fila → worker → banco → painel, íntegro.
- **Ponte denúncia → recompensa** cria a linha corretamente e é idempotente.
- **Ciclo financeiro** (pendente → aguardando → paga) + **Termo PDF** funcionando.
- **Segurança/LGPD:** CPF/PIX **nunca** aparecem nas listagens; "dados de pagamento" protegido por papel financeiro + auditoria; **AES-256-GCM** real; login por papéis.
- **SOS:** status consistentes ponta a ponta (`active`/`attending`/`resolved`); ficha da vítima à prova de campos nulos; GPS por tempo real; sirene + mute.
- **Volume realista:** 165 denúncias (134 com foto, 128 georreferenciadas), 68 recompensas, 13 cadastros SOS, 92 alertas, +8 mil pontos de GPS.

---

## 🧰 Pendências restantes (PÓS-demo — não mexer agora)

Já feitos: período padrão "Total", SOS no modo apresentação, "validada" destravada. Ficam para depois:

| Prioridade | Ajuste | Efeito |
|---|---|---|
| Média | Alinhar **`empenho` → `numero_empenho`** entre front e backend | Empenho passa a ser salvo no pagamento ao vivo |
| Média | Corrigir filtro **"Encaminhado"** (`encaminhada` vs `encaminhado`) e adicionar filtro de **"Paga"** | Filtros mostram todos os registros |
| Média | No modal, esconder "✓ Procedente" quando status = `recompensa_paga` | Evita rebaixar uma paga |
| Média | **Migração** versionando `sos_cadastros.agressor_foto_url` (existe no banco, não nas migrations) | Evita que a aba SOS quebre se o banco for reconstruído |
| Média | Recompensas somem da tabela quando a denúncia vinculada está fora das 100 últimas (`denuncias.py:36`) | Aba financeira mostra todas as 68 |
| Baixa | Mascarar/omitir **telefone** do cidadão na API de denúncias | Conformidade com a política interna |
| Baixa | Persistir o **termo de aceite LGPD** numa tela do painel SOS | Mostrar consentimento da vítima |

---

## 📇 Dados úteis do ambiente

- **Login admin:** joao@nodedata.com.br · **Login financeiro:** financeiro@nodedata.com.br
- **Protocolo pago (consulta de status):** MGA-2026-00727 (R$ 100)
- **Alerta SOS ativo:** vítima Marcia Aparecida (token `biuCNaI6OC`)
- **Recompensas agora:** 29 pendentes (R$ 4.470) · 9 aguardando (R$ 2.030) · 28 pagas (R$ 3.090) · 2 rejeitadas · **0 travadas**
- **Categorias com mais volume:** furto de fios (38), tráfico (39), descarte (35), pichação (34), depredação (19)
