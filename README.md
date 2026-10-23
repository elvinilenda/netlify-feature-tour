# Auditoria CEJUSC — API Trabalhista v5

Acesse o guia completo em [`README_V5.md`](README_V5.md) e as instruções para o Chat-JT em [`INTEGRACAO_CHAT_JT.md`](INTEGRACAO_CHAT_JT.md).

## Objetivo

**Uma ferramenta, uma análise, dois conjuntos de critérios:** liquidação e execução verificados simultaneamente, iniciando na sentença, com a fase provável identificada automaticamente. **Não existe mais seleção manual de fase na interface nova.**

- Site: `/`
- Gradio para Chat-JT: `/chatjt` (função única `/analisar_processo`)
- Documentação da API: `/docs`
- Saúde: `/api/v1/saude`
- PDF e pauta: `POST /api/v2/analisar/pdf`
- Exportação em Word com prints: `POST /api/v2/analisar/pdf/docx`

O projeto produz uma **prévia rastreável** por página, não uma decisão jurídica certificada. A leitura por palavras-chave é insuficiente para confirmar o mérito dos acórdãos; sempre confira os PDFs e o último despacho antes de utilizar a pauta em audiência. Se o PDF não contiver texto pesquisável, o conteúdo não será analisado sem OCR autorizado.

Nunca armazene senhas ou autos sigilosos no repositório público ou em uma instância sem aprovação institucional.