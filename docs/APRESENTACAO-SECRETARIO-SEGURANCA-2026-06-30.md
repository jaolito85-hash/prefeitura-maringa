# Plataforma de Segurança Pública Cidadã
## Apresentação à Secretaria Municipal de Segurança Pública — Prefeitura de Maringá-PR

**Proponente:** Node Data — Governo Digital
**Base legal:** Programa Cidadão Ativo — Decreto Municipal nº 291/2026
**Módulos apresentados:** (1) Cidadão Ativo — Denúncias com Recompensa · (2) SOS Mulher — Botão de Pânico via WhatsApp
**Data:** 30 de junho de 2026

---

## 1. Apresentação

A **Node Data** é uma plataforma de governo digital que transforma o **WhatsApp** — o aplicativo que o cidadão já usa todos os dias — na porta de entrada para a segurança pública municipal. Com **inteligência artificial**, o sistema recebe, classifica e encaminha denúncias e pedidos de socorro, exibindo tudo em **tempo real** num painel operacional para a equipe da Secretaria.

Sem aplicativo para instalar, sem cadastro burocrático e sem custo para o cidadão. Para a gestão, um centro de comando único, com mapa georreferenciado, trilha de auditoria e indicadores de desempenho.

Esta apresentação cobre os dois módulos prontos para operação:

| Módulo | Para que serve | Respaldo |
|---|---|---|
| **Cidadão Ativo** | Denúncias de infrações urbanas com recompensa ao denunciante | Decreto 291/2026 |
| **SOS Mulher** | Acionamento de emergência discreto para mulheres em risco | Política de enfrentamento à violência doméstica / Patrulha Maria da Penha |

> A demonstração será feita sobre um ambiente já populado com dezenas de casos simulados — denúncias georreferenciadas pelos bairros de Maringá, recompensas percorrendo todo o ciclo financeiro e um alerta de emergência ativo — para ilustrar a operação em escala real.

---

## 2. Módulo 1 — Programa Cidadão Ativo (Denúncia + Recompensa)

### 2.1. O problema que resolve
Infrações de "baixa visibilidade" — pichação, descarte irregular de lixo, furto de fios e cabos, depredação de patrimônio público e tráfico — são **subnotificadas**. O cidadão não sabe onde denunciar, ou tem receio de se expor. O Cidadão Ativo converte o morador em parceiro da gestão, com **incentivo financeiro**, **identidade protegida** perante a operação e **prestação de contas** completa para os órgãos de controle.

### 2.2. Como funciona — para o cidadão (WhatsApp)
1. Relata a infração por mensagem, **foto**, vídeo ou áudio.
2. A IA **classifica** o tipo de denúncia e, havendo imagem, **confirma o enquadramento** ("Identifiquei como descarte irregular. Está correto?").
3. Informa a **localização** (texto ou GPS) e recebe o **número de protocolo** (gerado quando há evidência).
4. Opcionalmente adere à recompensa, informando **CPF** (validado) e **chave PIX**.

### 2.3. Inteligência e automação
- Classificação por IA de texto e imagem, com índice de confiança.
- Moderação automática de linguagem e de imagens impróprias.
- Validação de CPF (dígitos verificadores) e sinalização da origem da foto (indício de imagem encaminhada × registrada na hora).

### 2.4. Categorias e valores (Decreto 291/2026)

| Categoria | Recompensa |
|---|---|
| Pichação | R$ 100 |
| Tráfico de drogas | R$ 300 |
| Descarte irregular de lixo/entulho | R$ 80 |
| Furto de fios e cabos elétricos | R$ 150 |
| Depredação de patrimônio público | R$ 150 |

*Valores parametrizáveis pela gestão.*

### 2.5. Ciclo de recompensa e controle financeiro
**Pendente de validação → Aguardando pagamento → Paga** (com a opção **Rejeitada**, mediante justificativa).
- O **operador** analisa a procedência e valida ou rejeita a denúncia.
- O **setor financeiro** registra o pagamento, com campos para **número de empenho** e **dotação orçamentária**.
- O sistema gera o **Termo de Recompensa em PDF** — com brasão, fundamento no Decreto 291/2026 e dados de empenho — pronto para o processo administrativo.
- *O PIX é executado pelo setor financeiro com a chave informada; a plataforma registra o pagamento e a trilha de auditoria.*

### 2.6. Para a gestão (painel)
- **Aba Denúncias:** cards com foto, categoria, status e filtros; painel de detalhe com a evidência.
- **Aba Recompensas:** painel financeiro com indicadores — pendentes, aguardando pagamento, total pago e rejeitadas.
- **Identidade protegida em camadas:** quem analisa a denúncia **não vê** CPF/dados bancários; quem opera o financeiro **não vê** o conteúdo da denúncia. A ponte entre as camadas é o protocolo, com registro de auditoria.

---

## 3. Módulo 2 — SOS Mulher (Botão de Pânico via WhatsApp)

### 3.1. O problema que resolve
Na violência doméstica, a vítima muitas vezes **não pode falar ao telefone nem operar um aplicativo**. O canal de socorro precisa ser **discreto, instantâneo e rastreável**. O SOS Mulher entrega isso pelo mesmo WhatsApp do dia a dia — alinhado às ações da Patrulha Maria da Penha e à rede de proteção do município.

### 3.2. Acionamento à prova de falhas (o diferencial)
- A vítima dispara com uma **mensagem mínima**: um ponto (`.`), "socorro", "sos" ou "ajuda".
- A detecção usa **reconhecimento direto de palavra-chave** — **não depende de inteligência artificial nem de serviços externos**: funciona mesmo que a IA esteja indisponível.
- O alerta **fura todas as filas e bloqueios** (limites de mensagem, moderação): *vida em risco nunca é bloqueada*. É a **primeira prioridade** do sistema.
- O painel da central dispara **tela vermelha com sirene** imediatamente.

### 3.3. Cadastro prévio (Programa Mulher Segura)
A mulher pode se cadastrar antes, pelo WhatsApp, informando **nome, endereço, identificação do agressor (com foto, opcional), existência de medida protetiva e um contato de confiança** — com **registro de consentimento (LGPD)**. Esses dados aparecem prontos para a equipe no momento do acionamento.

### 3.4. Rastreamento de localização ao vivo
- Ao disparar, a vítima recebe um **link discreto** que ativa o **compartilhamento contínuo de localização**.
- A central acompanha a **trilha da vítima em tempo real no mapa**, com rota da base mais próxima até ela.
- Captura **resiliente**: mantém o envio de posições e recupera os pontos acumulados quando o sinal oscila.

### 3.5. Para a central / equipe
- **Tela de alerta** com sirene, **dados da vítima e do agressor** em destaque, incluindo a sinalização de **medida protetiva**.
- **Ciclo de atendimento:** Ativo → Em atendimento → Resolvido, com registro de quem atendeu, anotações e horário.
- **Canal de conversa com a vítima:** o operador pode assumir a conversa e falar diretamente pelo WhatsApp, com histórico registrado.
- **Acesso rápido** para acionar 190 (PM) e 153 (Guarda Municipal) e contatar a pessoa de confiança a partir do painel.

---

## 4. Segurança e conformidade (LGPD)

A plataforma trata dados sensíveis (denunciantes, dados bancários, paradeiro de vítimas) e foi construída com privacidade desde a concepção:

- **Acesso por login individual e perfis** (operador / financeiro / administrador): cada acesso é identificado, com permissões por papel.
- **Criptografia AES-256-GCM** de CPF e chave PIX (dados sensíveis cifrados em repouso).
- **Separação de identidade em camadas** (operação × financeiro).
- **Registro de auditoria** das ações críticas — validação, pagamento e acesso a dados sensíveis — com operador, horário e contexto, atendendo à LGPD e à prestação de contas ao Tribunal de Contas.
- **Mascaramento de CPF** nas listagens; dados completos apenas para o perfil financeiro, com acesso auditado.
- **Sigilo operacional** dos dados da vítima e do agressor no módulo SOS, restritos à equipe autorizada.

*O hardening adicional de produção — políticas de banco por perfil, expurgo conforme finalidade e criptografia específica dos dados de localização — compõe o escopo de implantação e antecede a operação com casos reais em escala.*

---

## 5. Tecnologia (alto nível)

WhatsApp como canal (sem app, sem cadastro prévio) · IA de classificação e visão computacional · detecção de emergência determinística (independente de IA) · processamento por prioridade · rastreamento de localização ao vivo · painel operacional em **tempo real** com mapa georreferenciado e sirene · nuvem com banco gerenciado e criptografia.

---

## 6. Proposta de Prova de Conceito (POC)

1. **Definição do escopo do piloto** com a Secretaria — território, equipe e duração.
2. **Hardening de dados** dos módulos ativado antes da operação com casos reais (especialmente no SOS Mulher).
3. **Capacitação** das equipes operacional, financeira e de atendimento (sessões dirigidas).
4. **Operação assistida** por período determinado, com protocolo de resposta acordado e indicadores acompanhados em conjunto:
   - Cidadão Ativo: volume de denúncias, taxa de procedência, tempo de tratamento, valores pagos.
   - SOS Mulher: tempo de acionamento → atendimento → resolução.
5. **Relatório de resultados** ao final, embasando a decisão de expansão.

---

**Node Data** · prefeituras@nodedata.com.br · nodedata.com.br

> *Nota de transparência: o pagamento via PIX é executado manualmente pelo setor financeiro (a automação bancária é item opcional de implantação). No SOS Mulher, o aviso ao contato de confiança e o acionamento de 190/153 são operados pela equipe da central a partir do painel; a integração automática com as centrais da PM/Guarda é prevista como evolução conforme a necessidade da Secretaria. As funcionalidades descritas refletem o sistema em operação.*
