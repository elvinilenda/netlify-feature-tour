# CEJUSC API v4 — implantação Render (Chat-JT)

A versão 4 adiciona **Gradio montado em `/chatjt`**, mantendo o site `/`, o Swagger `/docs` e a API `/api/v1`.

## Hospedagem existente

Repositório: `elvinilenda/netlify-feature-tour`, branch: `cejusc-api`. O Render já utiliza a raiz do repositório e Python 3.

- Build: `pip install -r requirements.txt`
- Start: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- URL base: `https://cejusc-api-trabalhista.onrender.com`
- URL Gradio após o deploy: `https://cejusc-api-trabalhista.onrender.com/chatjt`
- Descoberta Gradio: `/chatjt/gradio_api/info`
- Teste de saúde: `/api/v1/saude`

## Variáveis

- `CEJUSC_API_KEY`: **obrigatória**, chave de serviço para proteger operações. Rotacione após qualquer exposição em captura de tela.
- `DATAJUD_API_KEY`: necessária apenas à consulta CNJ. Obtenha no CNJ, não gere aleatoriamente.
- `GRADIO_ANALYTICS_ENABLED=False`: recomendável para reduzir telemetria de aplicação.

**Autenticação Chat-JT:** sua tela descreve `X-IP-Token` como dados de usuário *codificados* com a chave preenchida. A API aceita o cabeçalho apenas se corresponder *literalmente* a `CEJUSC_API_KEY`, mas não sabe decodificar um protocolo não documentado. Não preencha o campo de chave do Chat-JT nem o declare funcional sem confirmar o contrato criptográfico com o suporte/TI. Sem chave válida, as operações falham de maneira segura; a descoberta Gradio é pública.

## Segurança

O serviço Render é público; não use processos sigilosos ou dados pessoais sem autorização institucional. O Gradio desta versão não recebe arquivos para evitar exposição de temporários. O site/API REST tem upload de PDF e exige `X-API-Key`, mas continua sendo um protótipo sem políticas de retenção institucionais. O plano Free pode exceder limites de memória ao instalar Gradio e PyMuPDF; verifique logs antes de aceitar a implantação.

## Testes locais

`pip install -r requirements.txt pytest pytest-asyncio && pytest -q`