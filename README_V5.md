# Auditoria CEJUSC — versão 5.0, análise única

## Mudanças

- Removida a escolha manual da fase nos formulários novos.
- Um processamento percorre desde a sentença e verifica **liquidação + execução conjuntamente**.
- Gera pauta cronológica com eventos datados e páginas para conferência.
- Fase atual classificada pelos atos disponíveis, com ressalvas de confiança.
- Web `/` apresenta a pauta formatada e exporta DOCX com até seis prints de páginas relevantes quando houver PDF.
- Chat-JT `/chatjt` expõe **uma única função** Gradio `/analisar_processo`: número CNJ, texto dos autos ou PDF pesquisável.
- Endpoints REST novos: `POST /api/v2/analisar/texto`, `POST /api/v2/analisar/pdf`, `POST /api/v2/analisar/pdf/docx`. V1 preservado por compatibilidade (legado).

## Segurança e limites

- `CEJUSC_API_KEY` obrigatório para acesso remoto; novo Gradio aceita apenas `X-API-Key` e `X-IP-Token` **literal**, não consegue validar token codificado de usuário do Chat-JT sem documentação e autorização institucional.
- Uma chamada autenticada real Chat-JT ainda deve ser validada. Nunca desligar autenticação para contornar erro 401.
- A consulta pública DataJud exige `DATAJUD_API_KEY`, fornece **metadados, não PDFs do PJe**.
- A versão não inclui modelo externo de IA: relatórios são **prévia textual/documental**, não síntese jurídica certificada. O modelo do assistente Chat-JT deverá conferir o conteúdo do documento original.
- PDFs sem camada pesquisável exigem OCR institucional antes da análise. Não suba autos sigilosos a hospedagem não autorizada.
- O repositório GitHub é público, não incluir chaves ou documentos processuais nele.

## Deploy

Render: branch `cejusc-api`, Python 3, build `pip install -r requirements.txt`, start `uvicorn api:app --host 0.0.0.0 --port $PORT`.

## Cadastro Chat-JT

Depois de implantar o código, edite sua ferramenta para apontar a `https://cejusc-api-trabalhista.onrender.com/chatjt` e **atualizar a lista de funções**. A função nova é apenas `/analisar_processo`; retire seleções antigas `/consultar_cnj`, `/analisar_texto` e `/formatar_pauta` se exibidas. Repita o teste de autenticação institucional.