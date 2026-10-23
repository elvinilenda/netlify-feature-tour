# Configuração da ferramenta no Chat-JT

**Observação:** a hospedagem em HTTPS deve ser realizada em ambiente aprovado pela TI. O arquivo `openapi.json` foi gerado com as rotas da aplicação, mas **não é um site hospedado**. O exemplo `SEU-DOMINIO` abaixo é ilustrativo.

## Exposição HTTP recomendada

- Base: `https://SEU-DOMINIO/`
- Contrato OpenAPI online: `https://SEU-DOMINIO/openapi.json`
- Health: `https://SEU-DOMINIO/api/v1/saude`
- Swagger online: `https://SEU-DOMINIO/docs`

Confirme com a documentação de cadastro de ferramentas da **sua versão do Chat-JT** se exige contrato OpenAPI ou endpoints Gradio. São protocolos diferentes: **não há garantia de cadastro direto por `/openapi.json`**.

## Cadastro sugerido, se admitir OpenAPI

- **Nome:** Auditoria Processual Trabalhista CEJUSC
- **Descrição:** Consulta metadados públicos de processos trabalhistas por número CNJ e realiza triagem de PDFs/textos desde a sentença. Destaca separadamente recursos, depósitos recursais, custas, acórdãos, cálculos, bloqueios, penhoras, alvarás e acordos, com indicação de páginas e trechos. A saída é indicativa e depende de conferência jurídica.
- **Contrato:** seu endereço HTTPS real terminado em `/openapi.json`.
- **Autenticação:** chave `X-API-Key`, gerenciada pela equipe técnica (o campo no Chat-JT deve admitir esse cabeçalho). Nunca coloque a chave no prompt público.
- **Acesso:** serviço privado institucional, conforme política do órgão.

## Prompt breve para o assistente

> Use a ferramenta para consultar o número CNJ e localizar metadados e movimentações públicas. Se houver PDF, priorize o documento para conferir atos da sentença em diante. Identifique individualmente cada recurso, depósito, custas, acórdão, cálculos, bloqueio, penhora, depósito, alvará e acordo. Não trate indícios textuais como comprovação nem títulos de movimentação como teor da decisão. A ferramenta não acessa o PJe nem documentos restritos. Se faltar o inteiro teor, solicite o PDF ou indique dados não confirmados. Gere uma pauta cronológica CEJUSC apenas depois da conferência documental, com datas, valores, partes e páginas/IDs.

## Se o Chat-JT exigir Gradio

O pacote original da **Auditoria Processual Trabalhista** possui endpoints Gradio próprios. Uma API FastAPI com OpenAPI **não substitui automaticamente** aquele protocolo. Nesse caso, mantenha o adaptador Gradio do pacote anterior ou peça à TI um conector OpenAPI suportado.

## Inspeção rápida

Com o servidor iniciado em `http://127.0.0.1:8000`, abra `/docs`. Use dados de teste para experimentar os endpoints. A consulta CNJ requer `DATAJUD_API_KEY` obtida na wiki oficial do CNJ.