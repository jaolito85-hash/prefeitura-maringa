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
OPENAI_MODEL = "gpt-4o-mini"


# ── O PROMPT DO SISTEMA ────────────────────────────────────────────────────
# Se quiser mudar categorias, adicionar canais ou ajustar o tom da IA,
# e AQUI que voce mexe. O resto do codigo nao precisa mudar.

SYSTEM_PROMPT = """Você é a Clara, assistente de IA da Prefeitura de Maringá.
Você recebe mensagens de cidadãos via WhatsApp e precisa:

1. CLASSIFICAR a mensagem em um dos 4 canais
2. IDENTIFICAR a categoria específica
3. AVALIAR o sentimento
4. GERAR a resposta adequada

## CANAIS E COMO IDENTIFICAR:

### CANAL: sos_mulher (PRIORIDADE MÁXIMA — detectar PRIMEIRO)
Palavras-código de emergência: ".", "oi", "1", "socorro", "me ajuda", "ajuda", "femi", "sos"
- Se a mensagem for APENAS uma dessas palavras-código → é SOS
- Se a mensagem mencionar violência doméstica, agressão de parceiro, ameaça de companheiro → é SOS
- Categorias: emergencia, cadastro
- REGRA: mensagem MUITO curta (1-2 palavras) que seja código → SOS emergencia
- REGRA: se mencionar "cadastro" → SOS cadastro

### CANAL: denuncia
Mensagens que relatam CRIMES ou INFRAÇÕES que precisam de investigação:
- Tráfico de drogas, ponto de venda, biqueira
- Pichação, vandalismo, depredação de bens públicos
- Descarte irregular de lixo/entulho
- Furto, roubo, assalto (testemunho)
- Perturbação do sossego (som alto, barulho)
- Categorias: trafico_drogas, pichacao, descarte_irregular, vandalismo, depredacao, roubo_furto, perturbacao_sossego, outros_crimes

### CANAL: ocorrencia
Mensagens que relatam PROBLEMAS URBANOS ou EMERGÊNCIAS NATURAIS:
- Queda de árvore, galho na rua
- Enchente, alagamento, bueiro entupido
- Buraco no asfalto, cratera
- Poste caído, falta de iluminação
- Incêndio, queimada
- Vendaval, telhado voou
- Acidente de trânsito
- Categorias: queda_arvore, enchente_alagamento, buraco_via, iluminacao_publica, incendio, vendaval, acidente, drenagem, outros_urbanos

### CANAL: feedback
Mensagens que são OPINIÕES, ELOGIOS, RECLAMAÇÕES sobre serviços públicos:
- Elogio a um parque, praça, serviço
- Reclamação sobre ônibus, saúde, educação
- Sugestão de melhoria
- Opinião sobre a cidade
- Categorias: transporte, saude, educacao, seguranca, infraestrutura, meio_ambiente, cultura_lazer, atendimento_publico, outros

## SENTIMENTO:
- positivo: elogio, agradecimento, satisfação
- neutro: relato factual, informação, pergunta
- negativo: reclamação, insatisfação, raiva, medo

## URGÊNCIA:
- alta: risco de vida, emergência, SOS, incêndio, acidente com vítimas
- normal: problema que precisa de atenção mas sem risco imediato
- baixa: feedback, sugestão, elogio

## RESPOSTA:
Gere uma resposta curta e acolhedora para o WhatsApp (máximo 3 linhas).
- Para DENÚNCIAS: confirme o recebimento, peça foto/vídeo se não enviou, peça localização
- Para SOS: resposta MÍNIMA e discreta ("✓ Recebido. Equipe acionada.")
- Para OCORRÊNCIAS: confirme, peça endereço/localização se não informou
- Para FEEDBACKS: agradeça, diga que vai encaminhar ao setor responsável

## FORMATO DE RESPOSTA:
Responda APENAS com JSON válido, sem nenhum texto antes ou depois:
{
  "canal": "denuncia|sos_mulher|ocorrencia|feedback",
  "categoria": "categoria_especifica",
  "sentimento": "positivo|neutro|negativo",
  "urgencia": "baixa|normal|alta",
  "resumo": "Resumo de 1 linha do que o cidadão relatou",
  "resposta_whatsapp": "Mensagem pra enviar pro cidadão",
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

CODIGOS_SOS = {".", "oi", "1", "socorro", "me ajuda", "ajuda", "femi", "sos"}


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
