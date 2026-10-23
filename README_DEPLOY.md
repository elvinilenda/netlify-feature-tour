# Deploy Render — CEJUSC v5

Repositório: `elvinilenda/netlify-feature-tour`; branch `cejusc-api`.

Serviço existente: `cejusc-api-trabalhista` (Python 3) com build `pip install -r requirements.txt` e start `uvicorn api:app --host 0.0.0.0 --port $PORT`.

**Após atualizar a branch:** confirme a revisão mais recente com status Live em Deploys. Se o deploy automático estiver desativado, use *Manual Deploy → Deploy latest commit*. Não selecione a branch `main` do projeto antigo.

Ambiente: `CEJUSC_API_KEY` (segredo obrigatório), `DATAJUD_API_KEY` (chave pública CNJ, opcional); nunca imprimir, enviar em conversa ou inserir em GitHub.

Verificações: `/api/v1/saude`, `/chatjt/gradio_api/info` (deve apresentar `/analisar_processo`), `/docs`, e chamadas autenticadas com **dados fictícios**. A descoberta das funções é pública, mas sua execução exige autenticação, que ainda depende de validação com o Chat-JT quanto ao token `X-IP-Token` codificado.

A versão não possui modelo autônomo de interpretação jurídica, nem OCR automático. Não utilizar em processos sigilosos sem aprovação de TI/encarregado de dados.