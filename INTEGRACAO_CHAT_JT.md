# Integração CEJUSC × Chat-JT — Versão 4

## Links no serviço Render existente

- **Site web:** `https://cejusc-api-trabalhista.onrender.com/`
- **Interface Gradio:** `https://cejusc-api-trabalhista.onrender.com/chatjt`
- **Descoberta de funções Gradio:** `https://cejusc-api-trabalhista.onrender.com/chatjt/gradio_api/info`
- **Documentação API FastAPI:** `https://cejusc-api-trabalhista.onrender.com/docs`
- **Saúde pública:** `https://cejusc-api-trabalhista.onrender.com/api/v1/saude`

Esses caminhos são a configuração da versão 4. Apenas a URL raiz foi observada na implantação anterior; `/chatjt` precisa ser confirmado após o novo deploy.

## Como preencher a ferramenta (modo teste)

- **Nome:** Auditoria CEJUSC — Integração Gradio
- **Descrição:** Localiza indícios documentais de atos processuais a partir da sentença e consulta movimentações públicas no CNJ, com indicação de limites e necessidade de conferência. Ferramenta não autenticada no PJe e não realiza parecer jurídico automático.
- **URL da API Gradio:** `https://cejusc-api-trabalhista.onrender.com/chatjt`
- **Vetorização:** desmarcada
- **Cache:** `0`
- **Chave da API no Chat-JT:** **não preencher antes de confirmar o formato exato do X-IP-Token** com o suporte da plataforma.

## Atenção à autenticação

- A API REST antiga usa `X-API-Key: <CEJUSC_API_KEY>`.
- A camada nova aceita também `X-IP-Token: <CEJUSC_API_KEY>`, **somente quando for exatamente igual à chave**. Não aceita strings arbitrárias como prova de autorização.
- A tela do Chat-JT afirma que a chave inserida no cadastro **codifica informações do usuário** antes do envio em `X-IP-Token`. Logo, **a cadeia enviada provavelmente NÃO será igual à chave**, e essa configuração deve ser conferida com a TI/documentação do Chat-JT.
- Não há especificação verificada de algoritmo, assinatura ou decodificação de tokens do Chat-JT. Não seria seguro assumir JWT ou simplesmente aceitar qualquer `X-IP-Token`.
- Por essa razão, o endpoint Gradio é descobrível (`/chatjt/config` e `/chatjt/gradio_api/info`), mas **as funções exigem token válido**. É esperado que a primeira tentativa de execução no Chat-JT exija ajuste do modo de autenticação; registre o código de erro SEM copiar nenhuma chave.
- Com chave recebida por `X-IP-Token` criptografado, peça à TI a especificação de formato/assinatura ou integração autorizada antes de tentar utilizar processos reais. É possível manter o Chat-JT público apenas para metadados públicos, mas a análise privada exige identidade/autorização real.

## Funções Gradio nomeadas

- `consultar_cnj(numero_cnj)` — usa DataJud, **requer `DATAJUD_API_KEY`** no Render. Retorna apenas metadados públicos/indicativos.
- `analisar_texto(texto, fase, pagina_sentenca)` — tria trechos **textuais**, a partir da sentença. Não extrai PDFs anexos do Chat-JT automaticamente.
- `formatar_pauta(eventos_json)` — gera cronologia a partir de eventos informados e referenciados, não certifica fatos.

O site atual continua permitindo upload de PDF pela API REST, protegido por `X-API-Key`; **não foi exposto um endpoint Gradio para upload** por risco de armazenamento temporário de autos em ferramenta pública.

## Checklist após Deploy

1. Gerar **nova** `CEJUSC_API_KEY` porque o valor anterior apareceu em uma captura de tela. Guarde a chave apenas no Render/gerenciador de segredos.
2. Confirmar a URL `/chatjt/config` (HTTP 200) e `/chatjt/gradio_api/info` (HTTP 200, três funções).
3. Confirmar `/api/v1/saude` (HTTP 200).
4. Consultar a documentação `/docs` e testar endpoint de texto com **dado fictício** usando `X-API-Key`.
5. Cadastrar URL da ferramenta `/chatjt` no Chat-JT.
6. Testar primeiro com informações **fictícias**. Se retornar não autorizado, conferir formato do `X-IP-Token` com TI do Chat-JT.

**Não envie processos sigilosos ou chaves por conversa, repositório público ou formulário público.** O protótipo não implementa SSO, controle de retenção, auditoria institucional nem revisão automática de mérito.