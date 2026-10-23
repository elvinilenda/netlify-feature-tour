# Auditoria CEJUSC — site + API HTTP para Chat-JT

**Versão 2.0.** Site local e API FastAPI que reutilizam o motor de triagem documental do projeto anterior.

## O que a API realmente faz

- Recebe **PDF pesquisável** (até 70 MB) ou **texto com páginas** e identifica, **da sentença em diante**, menções a sentenças, recursos, custas, depósitos recursais, honorários, cálculos, bloqueios, penhoras, acordos e movimentações financeiras. Retorna **relatório Markdown e índice JSON com trechos/páginas**.
- Ao receber um **número CNJ trabalhista**, consulta diretamente a **API Pública do DataJud/CNJ** (desde que você configure a chave pública vigente) e retorna capa processual e **movimentações públicas a partir de um possível marco de sentença**, se detectado. Nunca afirma o conteúdo de uma decisão não acessada.
- Interface web em `/`, documentação interativa em `/docs`, especificação OpenAPI em `/openapi.json`.

**Limitação fundamental:** DataJud disponibiliza **metadados**, não documentos integrais nem comprovantes; PDF é indispensável para conferir reformas, depósitos e crédito líquido. A triagem textual identifica **pistas**, não interpreta juridicamente sentenças. Cabe ao Chat-JT ou revisor humano conferir decisões e pagamentos. Não existe login no PJe nem consulta a autos sigilosos.

## Início rápido no Windows

1. Instale **Python 3.10 ou superior**.
2. Extraia o ZIP; dê dois cliques em `iniciar_windows.bat`.
3. Abra **http://127.0.0.1:8000** (site); **http://127.0.0.1:8000/docs** (API).
4. Envie um PDF, cole texto ou forneça CNJ. Para número CNJ, configure `DATAJUD_API_KEY` como variável de ambiente antes de iniciar (veja abaixo).

Linux/macOS: `bash iniciar_linux.sh`.

## Configuração

Obtenha a **chave pública vigente** no endereço oficial:

- https://datajud-wiki.cnj.jus.br/api-publica/acesso/

Na sessão PowerShell, por exemplo:

```powershell
$env:DATAJUD_API_KEY = "COLE_A_CHAVE_PUBLICA_DO_CNJ"
$env:CEJUSC_API_KEY = "UMA_CHAVE_FORTE_E_PRIVADA_PARA_SUA_API"
.\iniciar_windows.bat
```

Para uso local sem chave privada, o servidor aceita apenas conexões loopback. Para uso remoto, **configure CEJUSC_API_KEY, HTTPS e autorização institucional**. No site, digite a chave no campo correspondente. A aplicação não salva resultados nem documentos em banco; os PDFs recebidos são gravados temporariamente e apagados após o processamento, ressalvados logs/instrumentação externos da infraestrutura.

## Endpoints

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/api/v1/saude` | Status da aplicação |
| POST | `/api/v1/analisar/pdf` | Arquivo PDF + `fase` + `pagina_sentenca` + CNJ opcional |
| POST | `/api/v1/analisar/texto` | JSON com `texto`, `fase`, `pagina_sentenca`, `numero_cnj` |
| GET | `/api/v1/processos/{numero_cnj}/consulta` | Metadados e movimentações DataJud |
| GET | `/api/v1/processos/{numero_cnj}/previa` | Prévia Markdown de movimentos públicos desde a sentença |
| GET | `/openapi.json` | Contrato para integração com ferramentas de IA |
| GET | `/docs` | Testes no navegador |

**Exemplo — envio de texto:**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analisar/texto \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: SUA_CHAVE_SE_CONFIGURADA' \
  -d '{"fase":"execucao","pagina_sentenca":0,"texto":"[PÁGINA 1]\nPODER JUDICIÁRIO\nSENTENÇA\nAnte o exposto, JULGO PARCIALMENTE PROCEDENTES.\n[PÁGINA 2]\nComprovante de depósito recursal R$ 500,00."}'
```

**Exemplo — consultar CNJ:**

```bash
curl -H 'X-API-Key: SUA_CHAVE_SE_CONFIGURADA' \
  'http://127.0.0.1:8000/api/v1/processos/0011087-25.2017.5.15.0127/consulta'
```

## Integração com Chat-JT

1. Instale a aplicação em **servidor HTTPS institucional com domínio real**, autenticação e permissão da TI.
2. No Chat-JT, abra **Ferramentas / Criar ferramenta** e confira se o formulário aceita URL de documentação OpenAPI. Se aceitar, indique `https://SEU-DOMINIO/openapi.json` (somente após publicação real). Se exigir URL de aplicação Gradio, use o adaptador Gradio do projeto anterior, pois o campo pode exigir protocolo específico.
3. Descreva a finalidade da ferramenta: localizar trechos e páginas no PDF, destacar individualmente recursos, custas e depósitos; a consulta CNJ devolve apenas metadados.
4. Defina o prompt de sistema do assistente para **não classificar indícios como fatos confirmados**, e conferir cada comprovante antes de informar valores.
5. Teste exclusivamente com dados fictícios antes de utilizar qualquer processo real.

**Nenhum endereço externo é fornecido automaticamente:** este pacote é executável localmente; o domínio público/institucional depende de hospedagem e autorização.

## Segurança

- Não hospede abertamente com dados reais. O motor não implementa gestão de usuários nem integração com identidade institucional. Uma única chave de API não substitui SSO, autorização por usuário, trilha de auditoria, proteção LGPD e políticas do tribunal.
- A API só faz requisição externa ao host **fixo do CNJ**; não aceita URL arbitrária do usuário. Não envia PDFs à API do DataJud.
- Para implantação oficial: reverse proxy HTTPS, autenticação/SSO institucional, controle de rede, limites de tráfego, gestão de segredos, retenção e logs auditados. Verifique classificação/compartilhamento de ferramenta no Chat-JT.
- A ferramenta não faz OCR automático; PDFs escaneados exigem tratamento autorizado.

## Testes

```bash
pip install -r requirements.txt pytest
pytest -q
```

## Fontes oficiais

- Portal CNJ: https://www.cnj.jus.br/sistemas/datajud/api-publica/
- Documentação DataJud: https://datajud-wiki.cnj.jus.br/api-publica/
- Acesso e chave vigente: https://datajud-wiki.cnj.jus.br/api-publica/acesso/
- Busca por processo: https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo1/