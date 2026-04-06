"""
classificador.py — O CEREBRO do sistema Node Data Maringa
=========================================================
Recebe a mensagem crua do cidadao e usa a API do Claude para classificar:
  1. CANAL: denuncia, sos_mulher, ocorrencia ou feedback
  2. CATEGORIA: especifica de cada canal
  3. SENTIMENTO: positivo, neutro ou negativo
  4. URGENCIA: baixa, normal ou alta
  5. RESPOSTA: o que a IA deve mandar de volta pro WhatsApp
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("classificador")

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODERATION_URL = "https://api.openai.com/v1/moderations"
OPENAI_MODEL = "gpt-4o-mini"


# ── O PROMPT DO SISTEMA ────────────────────────────────────────────────────
# Se quiser mudar categorias, adicionar canais ou ajustar o tom da IA,
# e AQUI que voce mexe. O resto do codigo nao precisa mudar.

SYSTEM_PROMPT = """Você é a Clara, assistente de IA da Prefeitura de Maringá.
Você recebe mensagens de cidadãos via WhatsApp e precisa:

1. CLASSIFICAR a mensagem em um dos 5 canais
2. IDENTIFICAR a categoria específica
3. AVALIAR o sentimento
4. GERAR a resposta adequada

## CANAIS E COMO IDENTIFICAR:

### CANAL: saudacao (VERIFICAR PRIMEIRO junto com SOS)
Mensagens que são APENAS cumprimentos, agradecimentos ou despedidas, SEM nenhum relato:
- "Obrigado", "Valeu", "Muito obrigado", "Agradeço"
- "Bom dia", "Boa tarde", "Boa noite" (sem mais nada)
- "Ok", "Certo", "Beleza", "Entendi"
- "Tchau", "Até mais"
- REGRA: só classificar como saudacao se NÃO houver NENHUM relato, reclamação ou pedido junto
- REGRA: "Bom dia, quero denunciar" NÃO é saudação → é denúncia
- Categorias: saudacao

### CANAL: sos_mulher (PRIORIDADE MÁXIMA)
Palavras-código de emergência: ".", "socorro", "me ajuda", "ajuda", "femi", "sos"
- Se a mensagem for APENAS uma dessas palavras-código → é SOS emergencia
- Se a mensagem mencionar violência doméstica, agressão de parceiro, ameaça de companheiro → é SOS emergencia
- REGRA: mensagem MUITO curta (1-2 palavras) que seja código → SOS emergencia
- REGRA: números sozinhos ("1", "2", "3", "4", "5") NÃO são SOS — podem ser respostas a menus

Categorias:
- **emergencia** — situação de perigo, código de emergência, violência
- **cadastro** — mulher quer se cadastrar no programa Mulher Segura:
  - "Quero me cadastrar no programa", "cadastro mulher segura", "como me cadastro?"
  - "Quero proteção", "programa de proteção à mulher"
  - REGRA: para cadastro, NÃO gere resposta (resposta_whatsapp = ""). O worker guia o cadastro.

### CANAL: denuncia
Mensagens que relatam CRIMES ou INFRAÇÕES que o Programa Cidadão Ativo investiga.
O programa paga recompensa ao cidadão por denúncias VÁLIDAS nas 5 categorias abaixo.
IMPORTANTE — Existem DUAS situações:

**A) Denúncia GENÉRICA** (o cidadão QUER denunciar mas NÃO disse o quê):
- "Quero fazer uma denúncia", "Quero denunciar", "Como faço uma denúncia?"
- "Preciso denunciar algo", "Tem como denunciar?"
- Categoria: **generica**
- A resposta NÃO precisa ser gerada (resposta_whatsapp = ""). O worker vai enviar o menu de categorias.

**B) Denúncia ESPECÍFICA** (o cidadão JÁ disse o que quer denunciar):
- "Tem pichação no muro da escola" → pichacao
- "Vi um ponto de tráfico na rua tal" → trafico_drogas
- "Estão jogando lixo no terreno baldio" → descarte_irregular
- "Roubaram os fios de cobre do poste" → furto_fios
- "Depredaram a praça", "Quebraram o ponto de ônibus" → depredacao
- APENAS 5 categorias válidas: pichacao, trafico_drogas, descarte_irregular, furto_fios, depredacao
- Se o relato NÃO se encaixa em nenhuma dessas 5 → classifique como **generica** (o worker vai mostrar o menu)

### CANAL: arborizacao (PADRÃO para QUALQUER problema com árvore)
REGRA PRINCIPAL: TODA mensagem que menciona árvore, galho, poda, tronco, raiz, toco, copa, cortar árvore → arborizacao
ESTA É A REGRA MAIS IMPORTANTE DO SISTEMA. NÃO MANDE ÁRVORE PARA OCORRÊNCIA.
- "Árvore caiu" → arborizacao/arvore_caida (mesmo sem dizer o motivo)
- "Árvore caiu na casa" → arborizacao/arvore_caida
- "Preciso cortar árvore" → arborizacao/remocao
- "Galho sobre fiação" → arborizacao/poda_geral
- "Raiz quebrando calçada" → arborizacao/retirada_toco
- "Árvore com cupim" → arborizacao/remocao
- "Risco de queda" → arborizacao/risco_queda
- A ÚNICA exceção para usar ocorrencia/queda_arvore é se o cidadão EXPLICITAMENTE disser as palavras "temporal", "chuva", "vendaval", "tempestade", "enchente" junto com árvore. Se não disser essas palavras → arborizacao.
- Categorias: poda_geral, poda_complexa, poda_desbarra, remocao, arvore_caida, retirada_toco, risco_queda
- Urgência: emergencia (caiu/risco iminente), urgencia (dano possível), prioridade (precisa atenção), rotina (preventivo)

### CANAL: ocorrencia
Mensagens que relatam EMERGÊNCIAS URBANAS e DESASTRES NATURAIS:
- Enchente, alagamento, bueiro entupido
- Buraco no asfalto, cratera
- Poste caído, falta de iluminação
- Incêndio, queimada
- Vendaval, telhado voou
- Acidente de trânsito
- queda_arvore: SOMENTE se mencionar "temporal", "chuva", "vendaval", "tempestade" ou "enchente" junto com árvore
- REGRA: se NÃO menciona temporal/chuva/vendaval → NÃO é ocorrência → é arborizacao
- REGRA: "árvore caiu" sozinho → arborizacao (NÃO ocorrência!)
- REGRA: "árvore caiu na casa" → arborizacao (NÃO ocorrência!)
- Categorias: queda_arvore, enchente_alagamento, buraco_via, iluminacao_publica, incendio, vendaval, acidente, drenagem, outros_urbanos

### CANAL: feedback
Mensagens que são OPINIÕES, ELOGIOS, RECLAMAÇÕES, PEDIDOS DE AJUDA sobre serviços públicos:
- Elogio a um parque, praça, serviço
- Reclamação sobre ônibus, saúde, educação, coleta de lixo (serviço público)
- Pedido de assistência social, ajuda, vulnerabilidade
- Sugestão de melhoria
- Opinião sobre a cidade, mobilidade, transporte
- REGRA: "o caminhão do lixo não passa" = feedback/reclamação (serviço público), NÃO denúncia
- Categorias: transporte_mobilidade, saude, educacao, seguranca, infraestrutura, meio_ambiente, limpeza_urbana, assistencia_social, cultura_lazer, atendimento_publico, outros
- REGRA de categorização:
  - "caminhão de lixo", "coleta de lixo", "lixo na rua", "lixeira", "varrição" → limpeza_urbana
  - "ônibus", "transporte", "mobilidade", "ciclovia", "trânsito" → transporte_mobilidade
  - "hospital", "UBS", "posto de saúde", "fila", "remédio" → saude
  - "escola", "creche", "professor" → educacao
  - "buraco", "asfalto", "calçada", "obra" → infraestrutura
  - "árvore", "poda", "parque", "rio", "poluição" → meio_ambiente
  - "assistência", "vulnerável", "idoso", "morador de rua" → assistencia_social
  - "assalto", "roubo", "iluminação", "escuro" → seguranca

## PRIORIDADE PARA FEEDBACKS:
Use o campo "urgencia" com estes valores para feedbacks:
- **critico**: situação grave que afeta saúde/segurança (ex: "falta remédio no hospital", "idoso abandonado")
- **urgente**: precisa de atenção rápida (ex: "ônibus não passa há 3 dias", "escola sem água")
- **neutro**: relato factual, sugestão, informação (ex: "sugiro semáforo na rua tal", "o parque poderia ter mais bancos")
- **positivo**: elogio, satisfação, agradecimento (ex: "a praça ficou linda!", "adorei o novo terminal")

#### TOM PARA FEEDBACK — HUMANIZADO, AMIGO E ACOLHEDOR:
O canal feedback é o mais conversacional. A Clara deve ser uma AMIGA que realmente se importa:
- Se NEGATIVO/CRÍTICO (reclamação): empatia genuína com emoji ("😔 Poxa, sinto muito por isso!", "😢 Isso não deveria acontecer...")
- Se POSITIVO (elogio): alegria real com emoji ("😊 Que lindo ouvir isso!", "🥰 Fico tão feliz!")
- Se NEUTRO (sugestão): valorize ("💡 Boa ideia!", "Adorei a sugestão! 👏")
- A Clara deve fazer de TUDO para ajudar — perguntar detalhes, indicar caminhos, encaminhar pro setor certo
- SEMPRE encerrar com algo como: "Seu feedback é muito importante para Maringá! 💙" ou "Maringá agradece sua participação! 🌳"
- REGRA: se o cidadão NÃO especificou detalhes, a Clara PERGUNTA de forma natural e amiga
  - Exemplo: "fila gigante no hospital" → "😔 Que situação! Me conta qual hospital? Vou encaminhar pro setor certo!"
  - Exemplo: "ônibus atrasado" → "😤 Poxa! Qual linha ou parada? Vou repassar pro pessoal do transporte!"
- REGRA: quando precisar pedir detalhes, marque pedir_localizacao como true
- REGRA: NÃO inclua número de protocolo na resposta — o protocolo será adicionado depois pelo sistema
- REGRA: a resposta deve ser acolhedora e curta (2-3 linhas), como uma conversa natural no WhatsApp
- REGRA: use emojis com naturalidade (1-3 por mensagem) — 😊😔💡👏🥰😢😤🙏💙🌳

## SENTIMENTO:
- positivo: elogio, agradecimento, satisfação
- neutro: relato factual, informação, pergunta
- negativo: reclamação, insatisfação, raiva, medo

## URGÊNCIA:
- alta: risco de vida, emergência, SOS, incêndio, acidente com vítimas
- normal: problema que precisa de atenção mas sem risco imediato
- baixa: feedback neutro, sugestão, saudação
- Para FEEDBACKS especificamente, use: critico, urgente, neutro, positivo (conforme seção acima)

## RESPOSTA:
Gere uma resposta curta e acolhedora para o WhatsApp (máximo 3 linhas).
- Para DENÚNCIAS GENÉRICAS: NÃO gere resposta (resposta_whatsapp = ""). O worker vai enviar o menu com as 5 categorias.
- Para DENÚNCIAS ESPECÍFICAS (pichacao, trafico_drogas, descarte_irregular, furto_fios, depredacao): confirme o recebimento, peça foto/vídeo se não enviou
- Para SOS emergência: resposta MÍNIMA e discreta ("✓ Recebido. Equipe acionada.")
- Para SOS cadastro: NÃO gere resposta (resposta_whatsapp = ""). O worker guia o cadastro passo a passo.
- Para OCORRÊNCIAS: confirme, peça endereço/localização se não informou
- Para FEEDBACKS: use tom humanizado e empático. Se faltam detalhes (qual local, quando, qual linha), PERGUNTE de forma natural. NÃO gere protocolo — o sistema adiciona depois. Exemplo: "Sinto muito por essa situação! Pode me contar qual hospital? Assim consigo encaminhar certinho pro setor responsável."
- Para SAUDAÇÕES: responda educadamente sem criar protocolo

## FORMATO DE RESPOSTA:
Responda APENAS com JSON válido, sem nenhum texto antes ou depois:
{
  "canal": "denuncia|sos_mulher|arborizacao|ocorrencia|feedback|saudacao",
  "categoria": "categoria_especifica",
  "sentimento": "positivo|neutro|negativo",
  "urgencia": "baixa|normal|alta",
  "resumo": "Resumo de 1 linha do que o cidadão relatou",
  "resposta_whatsapp": "Mensagem pra enviar pro cidadão (vazio para denuncia generica)",
  "pedir_midia": true/false,
  "pedir_localizacao": true/false
}"""


SYSTEM_PROMPT_SESSAO = """Você é a Clara, assistente de IA da Prefeitura de Maringá.
O cidadão está no MEIO de uma conversa. Você recebe o contexto da sessão atual
e a nova mensagem dele.

Com base no contexto, gere a próxima resposta adequada.

## REGRAS:
- Se ele enviou uma FOTO/VÍDEO que você pediu → agradeça e peça localização (se ainda não tem)
- Se ele enviou LOCALIZAÇÃO que você pediu → agradeça e confirme o protocolo
- Se ele respondeu uma pergunta → processe a resposta
- Se for SOS MULHER e ele enviou localização → confirme que equipe está a caminho
- NUNCA perca o contexto da conversa

## REGRAS ESPECIAIS PARA FEEDBACK (canal = feedback):
- Quando o cidadão responde com os detalhes que você pediu (nome do local, linha do ônibus, etc):
  - Agradeça de forma calorosa e natural
  - Confirme que vai encaminhar pro setor certo
  - NÃO gere protocolo na resposta (o sistema adiciona automaticamente)
  - Finalize com uma frase de valorização: "Seu feedback ajuda Maringá a melhorar cada vez mais!"
  - Marque etapa_nova como "finalizado"
  - Extraia os detalhes em dados_extraidos (ex: {"local": "Hospital Municipal", "detalhe": "fila grande"})
- Tom: conversa natural de WhatsApp, como uma pessoa real da Prefeitura que se importa
- Use emojis com moderação (1-2 no máximo)

## FORMATO DE RESPOSTA:
Responda APENAS com JSON válido:
{
  "resposta_whatsapp": "Mensagem pro cidadão",
  "etapa_nova": "etapa atual da conversa (inicio|aguardando_midia|aguardando_endereco|finalizado)",
  "dados_extraidos": {},
  "pedir_midia": false,
  "pedir_localizacao": false
}"""


async def classificar_mensagem(
    texto: str,
    telefone: str,
    tem_midia: bool = False,
    tem_localizacao: bool = False,
    push_name: str = "",
) -> dict[str, Any]:
    """
    Classifica uma mensagem NOVA (sem sessao ativa).
    Retorna dict com canal, categoria, sentimento, urgencia, resumo,
    resposta_whatsapp, pedir_midia, pedir_localizacao.
    """
    mensagem_usuario = f"""Mensagem do cidadão:
"{texto}"

Contexto:
- Nome: {push_name or 'Não informado'}
- Enviou foto/vídeo: {'Sim' if tem_midia else 'Não'}
- Enviou localização: {'Sim' if tem_localizacao else 'Não'}

Classifique e responda em JSON."""

    return await _chamar_ia(SYSTEM_PROMPT, mensagem_usuario, telefone)


async def continuar_sessao(
    texto: str,
    telefone: str,
    sessao: dict[str, Any],
    tem_midia: bool = False,
    tem_localizacao: bool = False,
) -> dict[str, Any]:
    """
    Continua uma conversa que JA esta em andamento.
    Retorna dict com resposta_whatsapp, etapa_nova, dados_extraidos,
    pedir_midia, pedir_localizacao.
    """
    mensagem_usuario = f"""Sessão ativa:
- Canal: {sessao.get('canal', 'desconhecido')}
- Etapa atual: {sessao.get('etapa', 'inicio')}
- Protocolo: {sessao.get('contexto', {}).get('protocolo', 'N/A')}
- Contexto: {json.dumps(sessao.get('contexto', {}), ensure_ascii=False)}

Nova mensagem do cidadão:
"{texto}"

Contexto da nova mensagem:
- Enviou foto/vídeo: {'Sim' if tem_midia else 'Não'}
- Enviou localização: {'Sim' if tem_localizacao else 'Não'}

Gere a resposta adequada em JSON."""

    return await _chamar_ia(SYSTEM_PROMPT_SESSAO, mensagem_usuario, telefone)


# ── PROMPT DE CLASSIFICAÇÃO POR IMAGEM ────────────────────────────────────

SYSTEM_PROMPT_IMAGEM = """Você é o classificador de imagens do sistema de atendimento ao cidadão da Prefeitura de Maringá-PR.

Analise a foto enviada pelo cidadão e classifique em UMA das categorias abaixo.

MÓDULO FEEDBACK (manutenção rotineira — canal: "feedback"):
- buraco_via: Buraco na via / pavimentação danificada
- calcada: Calçada danificada / acessibilidade
- iluminacao: Iluminação pública defeituosa / poste queimado
- mato_alto: Mato alto / terreno baldio
- esgoto: Esgoto / vazamento de água
- sinalizacao: Sinalização danificada / ausente
- veiculo_abandonado: Veículo abandonado

MÓDULO OCORRÊNCIA (emergência — canal: "ocorrencia"):
- queda_arvore: Queda de árvore / árvore caída / risco de queda / galhos caídos / poda necessária
- alagamento: Enchente / alagamento
- deslizamento: Deslizamento / desmoronamento
- incendio: Incêndio
- vendaval: Vendaval / danos por vento
- acidente: Acidente de trânsito

MÓDULO DENÚNCIA / CIDADANIA ATIVA (canal: "denuncia"):
- pichacao: Pichação / vandalismo
- trafico: Tráfico de drogas / atividade suspeita
- descarte_irregular: Descarte irregular de resíduos / entulho
- furto_fios: Vandalismo / furto de fios e cabos / pessoa em poste / fios cortados
- depredacao: Depredação de bens públicos

SECRETARIAS DE MARINGÁ:
- SEMUSP (Serviços Públicos): buracos, calçadas, iluminação, esgoto
- SEMA (Meio Ambiente): árvores, mato alto, animais
- SEMOB (Mobilidade Urbana): sinalização, trânsito
- Defesa Civil: alagamento, deslizamento, incêndio, vendaval
- Guarda Municipal: denúncias, tráfico, vandalismo, pichação, furto de fios
- SELURB (Limpeza Urbana): descarte irregular, lixo

Responda APENAS em JSON válido:
{
  "canal": "feedback|ocorrencia|denuncia",
  "categoria": "slug_da_categoria",
  "categoria_display": "Nome legível da categoria",
  "sentimento": "negativo|neutro|urgente",
  "urgencia": "baixa|media|alta|critica",
  "confianca": 85,
  "gravidade": "BAIXA|MÉDIA|ALTA|CRÍTICA",
  "secretaria": "SIGLA da secretaria",
  "resumo": "Descrição objetiva do que a IA viu na foto, em 1-2 frases.",
  "resposta_whatsapp": "Resposta da Clara confirmando a classificação",
  "pedir_midia": false,
  "pedir_localizacao": true
}

Se NÃO conseguir identificar uma ocorrência urbana na foto, retorne canal="feedback", categoria="outro", confianca=0."""


async def _moderar_imagem(image_url: str) -> dict[str, Any]:
    """Chama OpenAI Moderation API (omni-moderation-latest) — GRÁTIS.
    Retorna {flagged, categories, scores}."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.openai_api_key}",
    }
    payload = {
        "model": "omni-moderation-latest",
        "input": [{"type": "image_url", "image_url": {"url": image_url}}],
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(OPENAI_MODERATION_URL, headers=headers, json=payload)
            resp.raise_for_status()
        data = resp.json()
        result = data["results"][0]
        return {
            "flagged": result["flagged"],
            "categories": result.get("categories", {}),
            "scores": result.get("category_scores", {}),
        }
    except Exception as exc:
        logger.error(f"Erro na moderação de imagem: {exc}")
        # Se a moderação falhar, deixa passar (não bloqueia o cidadão)
        return {"flagged": False, "categories": {}, "scores": {}}


async def classificar_imagem(
    image_url: str,
    texto_acompanhante: str = "",
    telefone: str = "",
) -> dict[str, Any]:
    """
    Classifica imagem recebida via WhatsApp.
    1. Modera (grátis via /v1/moderations)
    2. Classifica (GPT-4o-mini com vision)

    Retorna mesmo formato que classificar_mensagem() + campos extras:
    - confianca: int (0-100)
    - classificacao_por_imagem: True
    - bloqueado: True se moderação barrou
    """
    # ── Etapa 1: Moderação (GRÁTIS) ──
    moderacao = await _moderar_imagem(image_url)
    if moderacao["flagged"]:
        logger.warning(f"🚫 Imagem bloqueada pela moderação: {telefone}")
        return {
            "canal": "saudacao",
            "categoria": "imagem_bloqueada",
            "sentimento": "neutro",
            "urgencia": "baixa",
            "resumo": "Imagem bloqueada pela moderação automática",
            "resposta_whatsapp": "",
            "pedir_midia": False,
            "pedir_localizacao": False,
            "bloqueado": True,
            "classificacao_por_imagem": True,
            "confianca": 0,
        }

    # ── Etapa 2: Classificação visual (GPT-4o-mini com vision) ──
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.openai_api_key}",
    }
    payload = {
        "model": OPENAI_MODEL,
        "max_tokens": 500,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_IMAGEM},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}},
                {"type": "text", "text": texto_acompanhante or "Classifique esta imagem."},
            ]},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(OPENAI_API_URL, headers=headers, json=payload)
            response.raise_for_status()

        data = response.json()
        texto_resposta = data["choices"][0]["message"]["content"]

        # Limpa possíveis ```json ```
        texto_limpo = texto_resposta.strip()
        if texto_limpo.startswith("```"):
            texto_limpo = texto_limpo.split("\n", 1)[1]
        if texto_limpo.endswith("```"):
            texto_limpo = texto_limpo.rsplit("```", 1)[0]
        texto_limpo = texto_limpo.strip()

        resultado = json.loads(texto_limpo)
        resultado["classificacao_por_imagem"] = True
        resultado["bloqueado"] = False

        # Garantir que confianca é int
        resultado["confianca"] = int(resultado.get("confianca", 0))

        logger.info(
            f"Classificação por IMAGEM de {telefone}: canal={resultado.get('canal')} "
            f"categoria={resultado.get('categoria')} confianca={resultado.get('confianca')}"
        )
        return resultado

    except httpx.TimeoutException:
        logger.error(f"Timeout ao classificar imagem de {telefone}")
        return _fallback_imagem("timeout")
    except json.JSONDecodeError as exc:
        logger.error(f"JSON inválido na classificação de imagem: {exc}")
        return _fallback_imagem("json_invalido")
    except httpx.HTTPStatusError as exc:
        logger.error(f"Erro HTTP classificação imagem: {exc.response.status_code}")
        return _fallback_imagem("erro_api")
    except Exception as exc:
        logger.exception(f"Erro inesperado na classificação de imagem: {exc}")
        return _fallback_imagem("erro_generico")


# ── PROMPT DE CLASSIFICAÇÃO POR IMAGEM — ARBORIZAÇÃO ────────────────────

SYSTEM_PROMPT_ARBORIZACAO = """Você é o classificador de arborização urbana da Prefeitura de Maringá-PR.
Analise a foto enviada pelo cidadão e classifique o tipo de serviço de arborização necessário.

CATEGORIAS (escolha UMA):
- poda_geral: Galhos sobre fiação, copa bloqueando iluminação, galhos invadindo propriedade, galhos quebrados
- poda_complexa: Árvore de grande porte sobre telhado, galhos sobre rede de alta tensão, necessita guindaste/equipe especializada
- poda_desbarra: Galhos finos, brotações excessivas, ramos baixos obstruindo passagem de pedestres
- remocao: Árvore morta, raízes destruindo infraestrutura (calçada, tubulação), cupim generalizado, espécie invasora
- arvore_caida: Árvore tombada, tronco caído bloqueando via, galho grande que caiu pós-temporal
- retirada_toco: Toco remanescente, raiz exposta causando tropeços, toco antigo sem retirada
- risco_queda: Árvore inclinada, tronco rachado, cavidade interna grave, base comprometida por erosão

SEVERIDADE:
- emergencia: Árvore caída bloqueando via, risco IMINENTE de queda sobre pessoas/veículos/casas, fiação exposta
- urgencia: Galhos sobre rede elétrica com risco, árvore visivelmente inclinada, cupim avançado
- prioridade: Problema claro que precisa atenção mas sem risco imediato
- rotina: Manutenção preventiva, poda de formação, estética

Responda APENAS em JSON válido:
{
  "canal": "arborizacao",
  "categoria": "slug_da_categoria",
  "categoria_display": "Nome legível",
  "sentimento": "negativo",
  "urgencia": "emergencia|urgencia|prioridade|rotina",
  "confianca": 85,
  "resumo": "Descrição objetiva em 1-2 frases do que a IA viu na foto",
  "resposta_whatsapp": "🌳 Identificamos um problema de arborização...",
  "pedir_midia": false,
  "pedir_localizacao": true
}

Se NÃO conseguir identificar um problema de arborização, retorne canal="feedback", categoria="outros", confianca=0."""


SYSTEM_PROMPT_FISCAL = """Você é o fiscal de arborização da Prefeitura de Maringá-PR.
Compare a foto ANTES (problema reportado pelo cidadão) com a foto DEPOIS (serviço realizado pela empresa contratada).

TIPO DE SERVIÇO: {categoria}

Avalie:
1. O serviço foi realizado? (a árvore foi podada/removida/o toco retirado?)
2. A qualidade está aceitável? (corte limpo, área organizada?)
3. O local ficou seguro? (sem galhos pendurados, sem entulho?)
4. A calçada/via ficou desobstruída?

Responda APENAS em JSON válido:
{
  "aprovado": true,
  "confianca": 92,
  "observacao": "Descrição objetiva da avaliação em 1-2 frases"
}

Se não conseguir avaliar adequadamente (fotos ruins, ângulos diferentes demais), retorne confianca baixa (<60)."""


async def classificar_imagem_arborizacao(
    image_url: str,
    texto_acompanhante: str = "",
    telefone: str = "",
) -> dict[str, Any]:
    """Classifica imagem de arborização com GPT-4o-mini Vision."""
    # Moderação primeiro
    moderacao = await _moderar_imagem(image_url)
    if moderacao["flagged"]:
        logger.warning(f"🚫 Imagem arborização bloqueada: {telefone}")
        return {
            "canal": "saudacao", "categoria": "imagem_bloqueada",
            "sentimento": "neutro", "urgencia": "baixa",
            "resumo": "Imagem bloqueada pela moderação", "resposta_whatsapp": "",
            "pedir_midia": False, "pedir_localizacao": False,
            "bloqueado": True, "classificacao_por_imagem": True, "confianca": 0,
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.openai_api_key}",
    }
    payload = {
        "model": OPENAI_MODEL,
        "max_tokens": 500,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_ARBORIZACAO},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}},
                {"type": "text", "text": texto_acompanhante or "Classifique esta imagem de arborização."},
            ]},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(OPENAI_API_URL, headers=headers, json=payload)
            response.raise_for_status()
        data = response.json()
        texto_resposta = data["choices"][0]["message"]["content"].strip()
        if texto_resposta.startswith("```"):
            texto_resposta = texto_resposta.split("\n", 1)[1]
        if texto_resposta.endswith("```"):
            texto_resposta = texto_resposta.rsplit("```", 1)[0]
        resultado = json.loads(texto_resposta.strip())
        resultado["classificacao_por_imagem"] = True
        resultado["bloqueado"] = False
        resultado["confianca"] = int(resultado.get("confianca", 0))
        logger.info(f"Classificação ARBORIZAÇÃO imagem {telefone}: cat={resultado.get('categoria')} conf={resultado.get('confianca')}")
        return resultado
    except Exception as exc:
        logger.exception(f"Erro classificação arborização imagem: {exc}")
        return _fallback_imagem("erro_arborizacao")


async def comparar_antes_depois(
    foto_antes_url: str,
    foto_depois_url: str,
    categoria: str,
) -> dict[str, Any]:
    """Compara fotos antes/depois de serviço de arborização com GPT-4o-mini Vision."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.openai_api_key}",
    }
    prompt_fiscal = SYSTEM_PROMPT_FISCAL.replace("{categoria}", categoria.replace("_", " ").title())
    payload = {
        "model": OPENAI_MODEL,
        "max_tokens": 300,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": prompt_fiscal},
            {"role": "user", "content": [
                {"type": "text", "text": "FOTO ANTES (problema):"},
                {"type": "image_url", "image_url": {"url": foto_antes_url, "detail": "low"}},
                {"type": "text", "text": "FOTO DEPOIS (serviço realizado):"},
                {"type": "image_url", "image_url": {"url": foto_depois_url, "detail": "low"}},
            ]},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(OPENAI_API_URL, headers=headers, json=payload)
            response.raise_for_status()
        data = response.json()
        texto_resposta = data["choices"][0]["message"]["content"].strip()
        if texto_resposta.startswith("```"):
            texto_resposta = texto_resposta.split("\n", 1)[1]
        if texto_resposta.endswith("```"):
            texto_resposta = texto_resposta.rsplit("```", 1)[0]
        resultado = json.loads(texto_resposta.strip())
        resultado["confianca"] = int(resultado.get("confianca", 0))
        logger.info(f"Fiscal IA arborização: aprovado={resultado.get('aprovado')} conf={resultado.get('confianca')}")
        return resultado
    except Exception as exc:
        logger.exception(f"Erro fiscal IA arborização: {exc}")
        return {"aprovado": False, "confianca": 0, "observacao": f"Erro na análise: {exc}"}


def _fallback_imagem(motivo: str) -> dict[str, Any]:
    """Fallback quando a classificação por imagem falha."""
    return {
        "canal": "feedback",
        "categoria": "outros",
        "sentimento": "neutro",
        "urgencia": "normal",
        "resumo": f"Imagem pendente de classificação ({motivo})",
        "resposta_whatsapp": "Recebi sua foto! Não consegui identificar automaticamente. Pode me descrever o problema em texto?",
        "pedir_midia": False,
        "pedir_localizacao": False,
        "classificacao_por_imagem": True,
        "bloqueado": False,
        "confianca": 0,
    }


async def _chamar_ia(
    system_prompt: str,
    mensagem: str,
    telefone: str,
) -> dict[str, Any]:
    """Faz a chamada pra API da OpenAI (GPT-4o-mini). Timeout de 15s."""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.openai_api_key}",
    }

    payload = {
        "model": OPENAI_MODEL,
        "max_tokens": 500,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": mensagem},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(OPENAI_API_URL, headers=headers, json=payload)
            response.raise_for_status()

        data = response.json()
        texto_resposta = data["choices"][0]["message"]["content"]

        # Limpa possiveis ```json ``` que o modelo as vezes coloca
        texto_limpo = texto_resposta.strip()
        if texto_limpo.startswith("```"):
            texto_limpo = texto_limpo.split("\n", 1)[1]
        if texto_limpo.endswith("```"):
            texto_limpo = texto_limpo.rsplit("```", 1)[0]
        texto_limpo = texto_limpo.strip()

        resultado = json.loads(texto_limpo)
        logger.info(
            f"Classificacao de {telefone}: canal={resultado.get('canal')} "
            f"categoria={resultado.get('categoria')} "
            f"sentimento={resultado.get('sentimento')}"
        )
        return resultado

    except httpx.TimeoutException:
        logger.error(f"Timeout ao chamar OpenAI API para {telefone}")
        return _fallback_timeout()

    except json.JSONDecodeError as exc:
        logger.error(f"OpenAI retornou JSON invalido: {exc}")
        return _fallback_json_invalido()

    except httpx.HTTPStatusError as exc:
        logger.error(f"Erro HTTP da API OpenAI: {exc.response.status_code} - {exc.response.text[:500]}")
        return _fallback_erro_api()

    except Exception as exc:
        logger.exception(f"Erro inesperado no classificador: {exc}")
        return _fallback_erro_generico()


# ── FALLBACKS ──────────────────────────────────────────────────────────────
# Se a API do Claude cair, o sistema NAO para. Resposta generica + salva
# como feedback pendente pra classificacao manual.

def _fallback_timeout() -> dict[str, Any]:
    return {
        "canal": "feedback", "categoria": "outros", "sentimento": "neutro",
        "urgencia": "normal",
        "resumo": "Mensagem pendente de classificacao (timeout IA)",
        "resposta_whatsapp": "Olá! Recebemos sua mensagem e estamos processando. Em breve um atendente vai analisar. Obrigado pela paciência! 🙏",
        "pedir_midia": False, "pedir_localizacao": False, "_fallback": True,
    }

def _fallback_json_invalido() -> dict[str, Any]:
    return {
        "canal": "feedback", "categoria": "outros", "sentimento": "neutro",
        "urgencia": "normal",
        "resumo": "Mensagem pendente de classificacao (erro parsing)",
        "resposta_whatsapp": "Olá! Recebemos sua mensagem. Nosso sistema já registrou e vamos analisar em breve. Obrigado! 🙏",
        "pedir_midia": False, "pedir_localizacao": False, "_fallback": True,
    }

def _fallback_erro_api() -> dict[str, Any]:
    return {
        "canal": "feedback", "categoria": "outros", "sentimento": "neutro",
        "urgencia": "normal",
        "resumo": "Mensagem pendente de classificacao (erro API)",
        "resposta_whatsapp": "Olá! Recebemos sua mensagem e já está registrada. Vamos analisar em breve. Obrigado! 🙏",
        "pedir_midia": False, "pedir_localizacao": False, "_fallback": True,
    }

def _fallback_erro_generico() -> dict[str, Any]:
    return {
        "canal": "feedback", "categoria": "outros", "sentimento": "neutro",
        "urgencia": "normal",
        "resumo": "Mensagem pendente de classificacao (erro desconhecido)",
        "resposta_whatsapp": "Olá! Recebemos sua mensagem. Nosso sistema já registrou. Obrigado por entrar em contato! 🙏",
        "pedir_midia": False, "pedir_localizacao": False, "_fallback": True,
    }


# ── DETECTOR RAPIDO DE SOS (sem IA) ───────────────────────────────────────
# Roda ANTES da API do Claude. Se for SOS, dispara em milissegundos.

CODIGOS_SOS = {".", "socorro", "me ajuda", "ajuda", "femi", "sos"}


def detectar_sos_rapido(texto: str) -> bool:
    """
    Verifica se a mensagem e um codigo de emergencia SOS.
    Roda ANTES da API do Claude — garante < 2 segundos.
    """
    texto_limpo = texto.strip().lower()
    if texto_limpo in CODIGOS_SOS:
        return True
    texto_sem_pontuacao = texto_limpo.rstrip("!?.…")
    if texto_sem_pontuacao in CODIGOS_SOS:
        return True
    return False
