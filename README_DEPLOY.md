# CEJUSC API — versão para implantação no Render

**Estado:** aplicação preparada e testável localmente; NÃO foi publicada. **Não use PDFs sigilosos ou dados pessoais sem aprovação institucional.**

## O que faz
- Indexa texto pesquisável em PDFs a partir da sentença (não faz OCR nem interpreta o teor juridicamente).
- Realça recursos, depósitos recursais e custas em grupos independentes no JSON (`indice_prioritario`).
- Consulta capa e movimentações públicas no DataJud, com chave do CNJ (`DATAJUD_API_KEY`).
- Formata em cronologia CEJUSC eventos fornecidos com datas e fontes por `/api/v1/pautas/formatar`.
- Expõe documentação OpenAPI em `/openapi.json` e interface em `/`.

## Publicar (exige acesso à conta de hospedagem)
1. Colocar estes arquivos em um repositório Git privado (ou outro repositório controlado).
2. Conectar o Render à conta e criar um **Blueprint** utilizando `render.yaml`.
3. Confirmar a geração de `CEJUSC_API_KEY` e preencher `DATAJUD_API_KEY` com a chave pública vigente no CNJ.
4. Aguardar aprovação do deploy, depois testar `GET https://SEU-ENDERECO.onrender.com/api/v1/saude` (200), `GET /openapi.json` (200) e uma requisição autorizada (401 sem chave; 200 com chave).
5. Copiar a URL HTTPS do Render e cadastrar como ferramenta **somente se** a edição do Chat-JT aceitar serviços HTTP OpenAPI (algumas instalações exigem ferramentas Gradio).

## Integração
- Endpoint: `https://SEU-ENDERECO.onrender.com/openapi.json` (exemplo, NÃO é URL real).
- Autenticação: `X-API-Key: <valor de CEJUSC_API_KEY>`; configurar como segredo no cadastro da ferramenta, nunca no prompt público.
- `POST /api/v1/analisar/pdf`: multipart/form-data com PDF pesquisável.
- `POST /api/v1/analisar/texto`: corpo JSON texto + fase.
- `GET /api/v1/processos/{numero_cnj}/consulta`: metadados do CNJ, não documentos.
- `POST /api/v1/pautas/formatar`: recebe eventos já analisados e referências para compor a pauta.
- `GET /api/v1/capacidades`: capacidades e limites.

## Segurança
O Render Free expõe um serviço na internet e pode suspender por inatividade. Uma chave API única protege a entrada, mas **não** equivale a SSO, logs institucionais, retenção formal, controle de usuários ou autorização para trânsito de dados processuais. Uso em produção na Justiça do Trabalho requer revisão pela TI/segurança e respeito à LGPD.

## Testes
`pip install -r requirements.txt pytest pytest-asyncio && pytest -q`

## Fontes
- Render Blueprint: https://render.com/docs/blueprint-spec
- CNJ DataJud: https://datajud-wiki.cnj.jus.br/api-publica/acesso/