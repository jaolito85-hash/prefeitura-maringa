# Proposta Executiva SEINFRA PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gerar um PDF institucional de oito páginas, diretamente endereçado ao Secretário Vagner Mussio, para propor uma reunião técnica e uma POC de arborização urbana adaptável a outras demandas municipais.

**Architecture:** Um gerador isolado em ReportLab construirá páginas A4 com layout editorial explícito, marca vetorial da Node Data, tipografia Arial incorporada e componentes reutilizáveis para cartões, diagramas e rodapés. Um teste automatizado validará dimensões, número de páginas, conteúdo obrigatório e termos proibidos; a inspeção final será feita sobre PNGs renderizados do PDF.

**Tech Stack:** Python 3, ReportLab 4, pypdf 6, PyMuPDF apenas para renderização de revisão, unittest.

---

## Estrutura de arquivos

- Criar `scripts/gerar_proposta_seinfra_poc03.py`: fonte única da redação, identidade visual, componentes de página e comando CLI de geração.
- Criar `scripts/test_proposta_seinfra_poc03.py`: testes de contrato do PDF e da redação institucional.
- Gerar `output/pdf/Proposta-Executiva-SEINFRA-Arborizacao-Node-Data.pdf`: artefato final estável.
- Usar `tmp/pdfs/seinfra-poc03/`: PNGs e dependências temporárias de inspeção; remover ao concluir.

### Task 1: Fixar o contrato editorial em testes

**Files:**
- Create: `scripts/test_proposta_seinfra_poc03.py`
- Test: `scripts/test_proposta_seinfra_poc03.py`

- [ ] **Step 1: Criar o teste inicialmente falho**

```python
from pathlib import Path
import subprocess
import sys
import unittest

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "gerar_proposta_seinfra_poc03.py"
OUTPUT = ROOT / "output" / "pdf" / "Proposta-Executiva-SEINFRA-Arborizacao-Node-Data.pdf"


class PropostaSeinfraPdfTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            [sys.executable, str(GENERATOR), "--output", str(OUTPUT)],
            cwd=ROOT,
            check=True,
        )
        cls.reader = PdfReader(str(OUTPUT))
        cls.text = "\n".join(page.extract_text() or "" for page in cls.reader.pages)

    def test_pdf_has_eight_a4_pages(self):
        self.assertEqual(len(self.reader.pages), 8)
        for page in self.reader.pages:
            self.assertAlmostEqual(float(page.mediabox.width), 595.28, delta=1)
            self.assertAlmostEqual(float(page.mediabox.height), 841.89, delta=1)

    def test_recipient_and_company_are_exact(self):
        required = [
            "Vagner Mussio",
            "Secretário de Infraestrutura de Maringá",
            "Node Data Tecnologia Ltda.",
            "65.705.831/0001-04",
            "(11) 93622-0172",
            "www.nodedata.com.br",
            "prefeituras@nodedata.com.br",
        ]
        for phrase in required:
            self.assertIn(phrase, self.text)

    def test_core_proposal_is_present(self):
        required = [
            "Gestão Inteligente de Serviços Urbanos",
            "piloto em arborização urbana",
            "Clara",
            "WhatsApp",
            "visão computacional",
            "A tecnologia vai onde o cidadão já está.",
            "A definir com a SEINFRA",
            "reunião técnica",
            "demonstração",
        ]
        for phrase in required:
            self.assertIn(phrase, self.text)

    def test_unapproved_claims_are_absent(self):
        forbidden = [
            "Decreto Municipal 291/2026",
            "Programa Cidadão Ativo",
            "R$",
            "redução de 50%",
            "economia de",
            "garantia de resultado",
        ]
        for phrase in forbidden:
            self.assertNotIn(phrase, self.text)

    def test_each_page_contains_meaningful_text(self):
        for index, page in enumerate(self.reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            self.assertGreater(len(text), 120, f"Página {index} tem pouco texto")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Executar o teste e confirmar a falha esperada**

Run:

```powershell
& 'C:\Users\Joao Marcos\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest scripts.test_proposta_seinfra_poc03 -v
```

Expected: erro porque `scripts/gerar_proposta_seinfra_poc03.py` ainda não existe.

### Task 2: Implementar o gerador institucional

**Files:**
- Create: `scripts/gerar_proposta_seinfra_poc03.py`
- Test: `scripts/test_proposta_seinfra_poc03.py`

- [ ] **Step 1: Criar a interface CLI e o sistema visual**

Implementar esta interface pública:

```python
def build_pdf(output_path: Path) -> Path:
    """Gera a proposta executiva e devolve o caminho absoluto do PDF."""

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "pdf" / "Proposta-Executiva-SEINFRA-Arborizacao-Node-Data.pdf",
    )
    args = parser.parse_args()
    print(build_pdf(args.output))
```

Registrar Arial, Arial Bold e Arial Italic a partir de `C:/Windows/Fonts`, com fallback para Helvetica. Usar A4, margens de 20 mm e largura útil de 170 mm. Definir a paleta `NAVY=#123047`, `BLUE=#1F5E7A`, `GREEN=#159570`, `MINT=#E8F5F0`, `INK=#22313A`, `MUTED=#60717B`, `LINE=#D8E1E5` e `PAPER=#F7F9FA`.

Criar componentes focados com estas assinaturas e responsabilidades:

- `draw_logo(c, x, y, scale=1.0) -> None`: reproduzir a linha ascendente verde-azul e os quatro nós circulares do SVG existente em `frontend/index.html`, seguida do logotipo textual.
- `draw_paragraph(c, html, x, y_top, width, style) -> float`: instanciar `Paragraph`, executar `wrap`, desenhar em `y_top - height` e devolver essa coordenada inferior.
- `draw_card(c, x, y, width, height, title, body, accent) -> None`: desenhar fundo claro, linha lateral de 3 pt, título e corpo com `Paragraph`.
- `draw_footer(c, page_number) -> None`: inserir “Node Data Tecnologia Ltda.” à esquerda e o número à direita, a 10 mm da borda inferior.
- `draw_flow(c, steps, x, y, width) -> None`: distribuir os passos uniformemente, ligar os círculos por uma linha e usar `Paragraph` nos rótulos.

`draw_paragraph` deve retornar a coordenada inferior ocupada. Qualquer `Table` deve receber apenas células `Paragraph`, nunca strings diretas. Todas as funções devem salvar e restaurar o estado do canvas quando alterarem cores, espessuras ou transformações.

- [ ] **Step 2: Implementar exatamente oito páginas**

Usar uma função por página para manter limites claros:

```python
PAGES = [
    page_cover,
    page_executive_message,
    page_operational_challenge,
    page_clara_vision,
    page_arborization_flow,
    page_management_governance,
    page_future_expansion,
    page_poc_and_next_step,
]
```

Conteúdo e hierarquia obrigatórios:

1. **Capa:** título aprovado, subtítulo aprovado, bloco “Ao Senhor / Vagner Mussio / Secretário de Infraestrutura de Maringá”, “Junho de 2026” e marca Node Data. Não usar brasão municipal.
2. **Mensagem executiva:** abrir com “Secretário Vagner Mussio,”; explicar o piloto concreto e adaptável; destacar “A tecnologia vai onde o cidadão já está.”; fechar com a tese de começar por arborização e evoluir após validação conjunta.
3. **Desafio operacional:** quatro cartões sem números inventados: múltiplos canais e registros dispersos; prioridade difícil de padronizar; acompanhamento de prazos e equipes; fiscalização e histórico antes/depois.
4. **Clara e visão computacional:** diagrama “Cidadão -> Clara -> Classificação -> Encaminhamento -> Gestão”; explicar foto, texto, endereço/GPS, protocolo, nível de confiança e agrupamento de casos próximos.
5. **Fluxo de arborização:** recebimento; classificação; SLA configurável; ordem de serviço; atualização via WhatsApp; foto final; fiscalização assistida; retorno e avaliação. A tabela de severidade deve ser rotulada “Exemplo configurável” e conter Emergência/4 h, Urgência/24 h, Prioridade/72 h, Rotina/7 dias.
6. **Gestão e governança:** mapa, fila, linha do tempo, fotos, alertas, relatórios, perfis individuais e trilha de ações. Incluir caixa explícita: “A IA apoia a triagem e a fiscalização. A decisão técnica permanece sob governança humana conforme as regras definidas pelo Município.”
7. **Expansão futura:** colocar arborização como núcleo do piloto; três frentes futuras - pavimentação, obras e limpeza urbana - descritas como configurações possíveis após avaliação, sem afirmar que todas já pertencem à mesma estrutura administrativa.
8. **POC e próximo passo:** cinco etapas - definição conjunta, configuração, capacitação, operação assistida, avaliação final - com prazo e território “A definir com a SEINFRA”. Encerrar com convite para reunião técnica e demonstração e os quatro dados institucionais fornecidos.

- [ ] **Step 3: Executar os testes e ajustar somente falhas de contrato**

Run:

```powershell
& 'C:\Users\Joao Marcos\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest scripts.test_proposta_seinfra_poc03 -v
```

Expected: 5 testes `OK`; o PDF existe no caminho estável.

### Task 3: Renderizar e revisar visualmente

**Files:**
- Generate: `tmp/pdfs/seinfra-poc03/page-01.png` até `page-08.png`
- Verify: `output/pdf/Proposta-Executiva-SEINFRA-Arborizacao-Node-Data.pdf`

- [ ] **Step 1: Preparar o renderizador temporário se necessário**

Como Poppler e PyMuPDF não estão instalados no ambiente atual, instalar PyMuPDF apenas na pasta temporária:

```powershell
& 'C:\Users\Joao Marcos\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pip install --target 'tmp\pdfs\seinfra-poc03\vendor' pymupdf
```

Expected: `tmp/pdfs/seinfra-poc03/vendor/pymupdf` disponível; nada é instalado globalmente ou versionado.

- [ ] **Step 2: Renderizar cada página em 160 dpi**

Executar este script somente de leitura do PDF:

```python
from pathlib import Path
import sys

root = Path.cwd()
work = root / "tmp" / "pdfs" / "seinfra-poc03"
sys.path.insert(0, str(work / "vendor"))

import pymupdf

pdf = root / "output" / "pdf" / "Proposta-Executiva-SEINFRA-Arborizacao-Node-Data.pdf"
document = pymupdf.open(pdf)
matrix = pymupdf.Matrix(160 / 72, 160 / 72)
for index, page in enumerate(document, start=1):
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    pixmap.save(work / f"page-{index:02d}.png")
document.close()
```

Expected: oito arquivos `page-01.png` a `page-08.png`, todos com dimensões e tamanho de arquivo consistentes.

- [ ] **Step 3: Inspecionar as oito páginas**

Abrir os PNGs e conferir: ausência de corte ou sobreposição; contraste; acentos; alinhamento; equilíbrio de espaços; sequência narrativa; tamanho mínimo confortável do corpo; rodapés e números; consistência do logotipo; capa sem número visível.

- [ ] **Step 4: Corrigir e repetir o ciclo**

Após qualquer alteração no gerador, executar novamente os testes, gerar o PDF, renderizar todos os PNGs e reinspecionar. Não entregar com defeitos conhecidos.

### Task 4: Validação final e entrega

**Files:**
- Verify: `scripts/gerar_proposta_seinfra_poc03.py`
- Verify: `scripts/test_proposta_seinfra_poc03.py`
- Deliver: `output/pdf/Proposta-Executiva-SEINFRA-Arborizacao-Node-Data.pdf`

- [ ] **Step 1: Executar a suíte final**

Run:

```powershell
& 'C:\Users\Joao Marcos\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest scripts.test_proposta_seinfra_poc03 -v
```

Expected: 5 testes `OK`.

- [ ] **Step 2: Fazer auditoria textual final**

Extrair o texto com pypdf e verificar destinatário, título, CNPJ, telefone, domínio, e-mail, “A definir com a SEINFRA”, convite para reunião e ausência dos termos proibidos.

- [ ] **Step 3: Limpar temporários**

Remover `tmp/pdfs/seinfra-poc03/` somente depois de concluída a inspeção; preservar o PDF final.

- [ ] **Step 4: Entregar o artefato**

Fornecer link local clicável para o PDF e informar, em uma frase, que ele foi validado por testes de conteúdo e revisão visual das oito páginas.
