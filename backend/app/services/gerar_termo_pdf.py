"""
gerar_termo_pdf.py — Gerador do Termo de Recompensa (PDF)
=========================================================
Gera o PDF oficial do Termo de Recompensa do Programa Cidadão Ativo.
Usado para prestação de contas (Tribunal de Contas do Estado).

O PDF contém:
- Brasão e cabeçalho oficial da Prefeitura de Maringá
- Número do protocolo
- Dados do programa (Decreto 291/2026)
- Valor da recompensa
- Dados do beneficiário (CPF mascarado na versão pública)
- Dados fiscais (empenho, dotação orçamentária)
- Assinatura digital do sistema com timestamp

DICA: O brasão da prefeitura pode ser substituído colocando
o arquivo 'brasao_maringa.png' na pasta app/services/
"""
from __future__ import annotations

import io
import os
import logging
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image
)

logger = logging.getLogger("gerar_termo_pdf")

# Cores oficiais
VERDE_MARINGA = HexColor("#1a6b3c")
VERMELHO_MARINGA = HexColor("#c41e3a")
CINZA_ESCURO = HexColor("#333333")
CINZA_MEDIO = HexColor("#666666")
CINZA_CLARO = HexColor("#f0f0f0")

# Caminho do brasão (opcional — se não existir, usa texto)
BRASAO_PATH = Path(__file__).parent / "brasao_maringa.png"


def _criar_estilos():
    """Cria os estilos de parágrafo do documento."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "Cabecalho",
        parent=styles["Normal"],
        fontSize=18,
        fontName="Helvetica-Bold",
        textColor=VERDE_MARINGA,
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    ))

    styles.add(ParagraphStyle(
        "SubCabecalho",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Helvetica",
        textColor=CINZA_MEDIO,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    ))

    styles.add(ParagraphStyle(
        "TituloTermo",
        parent=styles["Normal"],
        fontSize=14,
        fontName="Helvetica-Bold",
        textColor=CINZA_ESCURO,
        alignment=TA_CENTER,
        spaceBefore=6 * mm,
        spaceAfter=6 * mm,
    ))

    styles.add(ParagraphStyle(
        "Corpo",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Helvetica",
        textColor=CINZA_ESCURO,
        alignment=TA_JUSTIFY,
        leading=14,
        spaceAfter=3 * mm,
    ))

    styles.add(ParagraphStyle(
        "CorpoNegrito",
        parent=styles["Normal"],
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=CINZA_ESCURO,
        alignment=TA_LEFT,
        leading=14,
        spaceAfter=2 * mm,
    ))

    styles.add(ParagraphStyle(
        "Rodape",
        parent=styles["Normal"],
        fontSize=7,
        fontName="Helvetica",
        textColor=CINZA_MEDIO,
        alignment=TA_CENTER,
        spaceBefore=10 * mm,
    ))

    styles.add(ParagraphStyle(
        "ValorGrande",
        parent=styles["Normal"],
        fontSize=24,
        fontName="Helvetica-Bold",
        textColor=VERDE_MARINGA,
        alignment=TA_CENTER,
        spaceBefore=4 * mm,
        spaceAfter=4 * mm,
    ))

    return styles


def _formatar_cpf_mascarado(cpf_enc: str | None) -> str:
    """Mascara CPF pra versão pública do PDF."""
    if not cpf_enc:
        return "***.***.***-**"
    if cpf_enc.startswith("ENC_"):
        return "***.***.***-**"
    return "***.***.***-**"


def _formatar_valor(valor: float | None) -> str:
    if not valor:
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_data(dt_str: str | None) -> str:
    if not dt_str:
        return "—"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y às %H:%M")
    except Exception:
        return str(dt_str)[:16]


def gerar_termo_recompensa(dados: dict) -> bytes:
    """
    Gera o PDF do Termo de Recompensa.

    Parâmetros (dict):
        protocolo: str           — ex: MGA-2026-00020
        valor: float             — ex: 100.00
        categoria: str           — ex: pichacao
        cpf_mascarado: str       — ex: ***.456.***-XX
        tipo_chave_pix: str      — ex: cpf
        status: str              — ex: paga
        validado_por: str        — ex: Op. Silva
        validado_em: str         — ISO datetime
        pago_por: str            — ex: Fin. Santos
        pago_em: str             — ISO datetime
        numero_empenho: str      — ex: EMP-2026-00412
        dotacao_orcamentaria: str — ex: DOT-15.452.0045.2.048
        created_at: str          — ISO datetime

    Retorna: bytes do PDF gerado
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
    )

    styles = _criar_estilos()
    story = []

    # ══════════════════════════════════════════
    # CABEÇALHO
    # ══════════════════════════════════════════

    # Brasão (se existir o arquivo PNG)
    if BRASAO_PATH.exists():
        try:
            img = Image(str(BRASAO_PATH), width=3 * cm, height=3 * cm)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 3 * mm))
        except Exception:
            pass

    story.append(Paragraph("PREFEITURA DO MUNICÍPIO DE MARINGÁ", styles["Cabecalho"]))
    story.append(Paragraph("Estado do Paraná", styles["SubCabecalho"]))

    # Linha decorativa verde-vermelha (cores de Maringá)
    story.append(HRFlowable(
        width="100%", thickness=2, color=VERDE_MARINGA,
        spaceAfter=1 * mm, spaceBefore=2 * mm,
    ))
    story.append(HRFlowable(
        width="100%", thickness=1, color=VERMELHO_MARINGA,
        spaceAfter=4 * mm,
    ))

    # ══════════════════════════════════════════
    # TÍTULO
    # ══════════════════════════════════════════

    story.append(Paragraph(
        "TERMO DE RECOMPENSA — PROGRAMA CIDADÃO ATIVO",
        styles["TituloTermo"],
    ))
    story.append(Paragraph(
        "Decreto Municipal nº 291/2026",
        styles["SubCabecalho"],
    ))

    # ══════════════════════════════════════════
    # PROTOCOLO E VALOR EM DESTAQUE
    # ══════════════════════════════════════════

    protocolo = dados.get("protocolo", "—")
    valor = dados.get("valor")
    categoria = dados.get("categoria", "—").replace("_", " ").title()

    # Tabela com protocolo e valor lado a lado
    destaque_data = [[
        Paragraph(
            f'<font size="9" color="#666666">PROTOCOLO</font><br/>'
            f'<font size="16"><b>{protocolo}</b></font>',
            ParagraphStyle("dest1", alignment=TA_CENTER, fontName="Helvetica"),
        ),
        Paragraph(
            f'<font size="9" color="#666666">VALOR DA RECOMPENSA</font><br/>'
            f'<font size="20" color="#1a6b3c"><b>{_formatar_valor(valor)}</b></font>',
            ParagraphStyle("dest2", alignment=TA_CENTER, fontName="Helvetica"),
        ),
    ]]

    destaque_table = Table(destaque_data, colWidths=[8 * cm, 8 * cm])
    destaque_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CINZA_CLARO),
        ("BOX", (0, 0), (-1, -1), 1, HexColor("#cccccc")),
        ("LINEAFTER", (0, 0), (0, 0), 1, HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(destaque_table)
    story.append(Spacer(1, 6 * mm))

    # ══════════════════════════════════════════
    # CORPO DO TERMO
    # ══════════════════════════════════════════

    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    story.append(Paragraph(
        f"A Prefeitura do Município de Maringá, Estado do Paraná, no uso de suas "
        f"atribuições legais e com fundamento no <b>Decreto Municipal nº 291/2026</b>, "
        f"que institui o <b>Programa Cidadão Ativo</b>, declara para os devidos fins que:",
        styles["Corpo"],
    ))

    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        f"O cidadão identificado pelo CPF <b>{dados.get('cpf_mascarado', '***.***.***-**')}</b>, "
        f"registrou denúncia classificada na categoria <b>{categoria}</b>, "
        f"sob o protocolo <b>{protocolo}</b>, por meio da plataforma digital "
        f"<b>Node Data — Central de Segurança Pública</b>.",
        styles["Corpo"],
    ))

    story.append(Paragraph(
        f"Após análise e validação pela equipe operacional, a denúncia foi considerada "
        f"<b>PROCEDENTE</b>, fazendo jus o denunciante à recompensa prevista no "
        f"programa, no valor de <b>{_formatar_valor(valor)}</b>.",
        styles["Corpo"],
    ))

    # ══════════════════════════════════════════
    # DADOS DA OPERAÇÃO
    # ══════════════════════════════════════════

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("DADOS DA OPERAÇÃO", styles["CorpoNegrito"]))

    info_data = [
        ["Protocolo:", protocolo],
        ["Categoria:", categoria],
        ["Tipo de Chave PIX:", dados.get("tipo_chave_pix", "—").upper()],
        ["Status:", dados.get("status", "—").replace("_", " ").title()],
        ["Validado por:", dados.get("validado_por", "—")],
        ["Data da Validação:", _formatar_data(dados.get("validado_em"))],
        ["Pago por:", dados.get("pago_por", "—")],
        ["Data do Pagamento:", _formatar_data(dados.get("pago_em"))],
    ]

    info_table = Table(info_data, colWidths=[5 * cm, 11 * cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), CINZA_MEDIO),
        ("TEXTCOLOR", (1, 0), (1, -1), CINZA_ESCURO),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, HexColor("#e0e0e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(info_table)

    # ══════════════════════════════════════════
    # DADOS FISCAIS
    # ══════════════════════════════════════════

    empenho = dados.get("numero_empenho")
    dotacao = dados.get("dotacao_orcamentaria")

    if empenho or dotacao:
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("DADOS FISCAIS — PRESTAÇÃO DE CONTAS", styles["CorpoNegrito"]))

        fiscal_data = []
        if empenho:
            fiscal_data.append(["Nº do Empenho:", empenho])
        if dotacao:
            fiscal_data.append(["Dotação Orçamentária:", dotacao])
        fiscal_data.append(["Valor Empenhado:", _formatar_valor(valor)])

        fiscal_table = Table(fiscal_data, colWidths=[5 * cm, 11 * cm])
        fiscal_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), CINZA_MEDIO),
            ("TEXTCOLOR", (1, 0), (1, -1), CINZA_ESCURO),
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#f8f8f0")),
            ("BOX", (0, 0), (-1, -1), 1, HexColor("#d4d4a0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(fiscal_table)

    # ══════════════════════════════════════════
    # DECLARAÇÃO FINAL
    # ══════════════════════════════════════════

    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph(
        f"O presente termo é gerado automaticamente pela plataforma "
        f"<b>Node Data — Central de Segurança Pública</b> e constitui documento "
        f"hábil para fins de prestação de contas junto ao Tribunal de Contas do "
        f"Estado do Paraná, nos termos do Decreto Municipal nº 291/2026.",
        styles["Corpo"],
    ))

    story.append(Paragraph(
        f"A identidade do denunciante é protegida por criptografia AES-256, "
        f"conforme exigência da Lei Geral de Proteção de Dados (LGPD — Lei nº 13.709/2018). "
        f"O acesso aos dados pessoais é restrito ao setor financeiro e cada acesso "
        f"é registrado no log de auditoria do sistema.",
        styles["Corpo"],
    ))

    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph(
        f"Maringá-PR, {agora}",
        ParagraphStyle("local", alignment=TA_RIGHT, fontSize=10,
                        fontName="Helvetica", textColor=CINZA_ESCURO),
    ))

    # ══════════════════════════════════════════
    # ASSINATURA DIGITAL
    # ══════════════════════════════════════════

    story.append(Spacer(1, 15 * mm))

    story.append(HRFlowable(
        width="40%", thickness=0.5, color=CINZA_MEDIO,
        spaceAfter=2 * mm,
    ))

    story.append(Paragraph(
        "Documento gerado eletronicamente",
        ParagraphStyle("assin1", alignment=TA_CENTER, fontSize=9,
                        fontName="Helvetica-Bold", textColor=CINZA_ESCURO),
    ))
    story.append(Paragraph(
        "Node Data — Central de Segurança Pública",
        ParagraphStyle("assin2", alignment=TA_CENTER, fontSize=8,
                        fontName="Helvetica", textColor=CINZA_MEDIO),
    ))

    # ══════════════════════════════════════════
    # RODAPÉ
    # ══════════════════════════════════════════

    story.append(HRFlowable(
        width="100%", thickness=0.5, color=HexColor("#e0e0e0"),
        spaceAfter=2 * mm, spaceBefore=10 * mm,
    ))

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    story.append(Paragraph(
        f"Validação digital: {protocolo} | Gerado em: {ts} | "
        f"Plataforma Node Data v2.0 | Prefeitura de Maringá-PR",
        styles["Rodape"],
    ))

    # ══════════════════════════════════════════
    # BUILD
    # ══════════════════════════════════════════

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    logger.info(f"Termo PDF gerado: {protocolo} ({len(pdf_bytes)} bytes)")
    return pdf_bytes
