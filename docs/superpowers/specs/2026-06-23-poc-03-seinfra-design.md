# Proposta Executiva SEINFRA - POC-03

## Objetivo

Criar um PDF institucional, profissional e diretamente endereçado ao Sr. Vagner Mussio, Secretário de Infraestrutura de Maringá, para apresentar a solução da Node Data e obter uma reunião técnica com demonstração. O documento deve propor um piloto de arborização urbana e mostrar, de forma secundária, como a mesma base pode ser adaptada a outras demandas municipais.

## Posicionamento aprovado

O documento combina uma abordagem executiva institucional com elementos seletivos de visão estratégica. A tecnologia aparece como meio para melhorar atendimento, priorização, despacho, acompanhamento e fiscalização, sem substituir a decisão técnica dos servidores.

Mensagem central:

> A Node Data propõe iniciar por um problema concreto e mensurável - a gestão das solicitações de arborização - e construir, junto à SEINFRA, uma base tecnológica adaptável para outras demandas urbanas.

O material será independente: não citará o Decreto Municipal 291/2026, o Programa Cidadão Ativo ou a POC atualmente em andamento. Não apresentará preços, custos internos, métricas inventadas ou promessas quantitativas sem dados comprovados. A duração, o território, o volume e os parâmetros do piloto serão definidos em conjunto com a SEINFRA.

## Estrutura editorial

O PDF terá de 7 a 9 páginas A4, com leitura executiva e uma ideia principal por página:

1. **Capa personalizada** - título "Gestão Inteligente de Serviços Urbanos"; subtítulo "Proposta de piloto em arborização urbana, com expansão para novas demandas municipais"; destinatário nominal; Node Data; junho de 2026.
2. **Mensagem executiva** - oportunidade de transformar fotos e relatos enviados pelo WhatsApp em demandas classificadas, priorizadas e rastreáveis; convite para iniciar por arborização.
3. **Desafio operacional** - dispersão de solicitações, dificuldade de priorização, deslocamentos, controle de prazos e fiscalização antes/depois, sem usar números não validados.
4. **Clara e AI Vision** - explicação simples do fluxo: foto, texto e localização; classificação; protocolo; prioridade; encaminhamento; acompanhamento.
5. **Fluxo do piloto de arborização** - diagrama do cidadão ao encerramento: recebimento, triagem inteligente, SLA configurável, ordem de serviço, execução, foto de conclusão, fiscalização assistida e retorno ao cidadão.
6. **Gestão e governança** - painel com mapa, indicadores, linha do tempo, perfis de acesso, registro de ações, alertas e exportação de relatórios. A decisão final permanece humana quando exigida pela regra operacional.
7. **Expansão futura** - mostrar a mesma arquitetura sendo configurada, após validação do piloto, para pavimentação, obras e limpeza urbana. Tratar essas frentes como possibilidades de expansão e integração municipal, sem afirmar competências administrativas não confirmadas.
8. **Plano de implantação da POC** - definição conjunta de escopo; configuração de categorias, equipes e prazos; capacitação; operação assistida; avaliação e relatório final. Prazo e abrangência ficam "a definir com a SEINFRA".
9. **Próximo passo** - convite direto para reunião técnica e demonstração, seguido dos dados institucionais da Node Data.

Se o texto couber com melhor ritmo em oito páginas, as páginas 2 e 3 poderão ser combinadas. Nenhuma página deve parecer densa ou jurídica.

## Conteúdo obrigatório

- A Clara atende pelo WhatsApp, canal que o cidadão já utiliza.
- O cidadão pode enviar foto, texto, endereço ou localização GPS e recebe protocolo.
- A visão computacional identifica o tipo da demanda, estima severidade e gera uma classificação com nível de confiança.
- Pedidos semelhantes e próximos podem ser agrupados para reduzir duplicidade operacional.
- Os prazos de atendimento são configuráveis conforme as regras definidas com a SEINFRA; a tabela atual de 4 h, 24 h, 72 h e 7 dias pode ser apresentada apenas como exemplo configurável, nunca como compromisso definitivo.
- A equipe recebe ordem de serviço com contexto, mapa e prazo, e atualiza o andamento pelo WhatsApp.
- A comparação de fotos antes e depois apoia a fiscalização; casos incertos ou definidos por regra seguem para avaliação humana.
- O painel consolida mapa, fila, prazos, histórico, fotos, indicadores e satisfação do cidadão.
- A arquitetura pode ser configurada futuramente para buracos e pavimentação, problemas em obras e demandas de limpeza urbana.
- A frase-chave "A tecnologia vai onde o cidadão já está." deve aparecer uma vez, em destaque discreto.
- A Node Data deve ser apresentada como fornecedora da tecnologia e parceira da administração, sem sugerir autoria oficial da Prefeitura.

## Direção visual

- Estilo institucional claro, editorial e sóbrio.
- Fundo branco ou cinza muito claro; azul-petróleo para hierarquia; verde como acento ligado ao piloto; cinzas neutros para textos e divisores.
- Reaproveitar em vetor a marca gráfica da Node Data existente no painel, com gradiente verde-azul, e o logotipo textual "Node Data".
- Não usar brasão ou logotipo da Prefeitura sem um ativo oficial fornecido e autorização explícita; o destinatário será identificado por texto.
- Tipografia sem serifa de alta legibilidade, com títulos fortes, corpo arejado e no máximo dois pesos principais.
- Diagramas simples, ícones lineares e blocos de informação; evitar emojis, cores vibrantes, efeitos de gaming e imagens decorativas genéricas.
- Rodapé interno com "Node Data Tecnologia Ltda." e numeração de página; capa sem número visível.

## Endereçamento e encerramento

Na capa:

> Ao Senhor  
> Vagner Mussio  
> Secretário de Infraestrutura de Maringá

No encerramento, sem assinatura pessoal:

> Node Data Tecnologia Ltda.  
> CNPJ 65.705.831/0001-04  
> (11) 93622-0172  
> www.nodedata.com.br  
> prefeituras@nodedata.com.br

## Produção e controle de qualidade

- Gerar o documento com Python e ReportLab em A4, com margens de 20 mm e largura útil de 170 mm.
- Usar `Paragraph` e `ParagraphStyle` em todas as células de tabelas.
- Salvar o PDF final em `output/pdf/Proposta-Executiva-SEINFRA-Arborizacao-Node-Data.pdf`.
- Manter arquivos temporários em `tmp/pdfs/` e removê-los ao concluir.
- Renderizar todas as páginas em PNG, revisar visualmente página a página e corrigir qualquer corte, sobreposição, desequilíbrio ou falha de acentuação.
- Extrair o texto final com `pypdf` ou `pdfplumber` para confirmar nome do destinatário, contatos, CNPJ, ordem das seções e ausência de placeholders.

## Critérios de aceite

- O destinatário percebe imediatamente que o documento foi preparado para ele e para a Secretaria de Infraestrutura.
- O piloto de arborização é o foco principal; a expansão aparece como próximo passo possível, não como dispersão de escopo.
- Benefícios operacionais estão claros sem métricas inventadas, precificação ou contexto jurídico da POC atual.
- A IA é apresentada como apoio à triagem e fiscalização, com supervisão humana conforme as regras do município.
- O PDF é legível em tela e impresso, tem acabamento executivo e termina com convite inequívoco para reunião técnica e demonstração.
