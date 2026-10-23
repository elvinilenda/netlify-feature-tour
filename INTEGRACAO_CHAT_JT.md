# Integração Chat-JT — CEJUSC v5

**Endereço da ferramenta:** `https://cejusc-api-trabalhista.onrender.com/chatjt`

**Nova função única para selecionar:** `/analisar_processo`.

A ferramenta não pergunta a fase. Ao receber PDF, texto ou número CNJ, considera simultaneamente as exigências de liquidação e execução. Se houver apenas CNJ, a resposta é prévia pública DataJud; documentos integrais não são fornecidos pelo CNJ.

Para uma nova versão aparecer no Chat-JT, atualize os dados da ferramenta que já está cadastrada: URL acima, descubra a função `/analisar_processo`, selecione-a e salve. Em alguns casos a aprovação institucional é necessária para ficar disponível aos assistentes. A função anterior `/analisar_texto` tinha parâmetro `fase` e deve ser desmarcada/substituída no cadastro.

## Autenticação

`CEJUSC_API_KEY` configurada no Render é necessária; a função aceita `X-API-Key` ou `X-IP-Token` **literal igual** à chave. A tela do Chat-JT relata que codifica as informações do usuário em `X-IP-Token`, cujo formato/assinatura não foi fornecido. **Não é possível validar um token codificado apenas conhecendo a chave literal.** Portanto, é indispensável teste institucional, sem autos reais, e suporte oficial para implementar verificação segura. Não remova o controle de acesso para fazer a ferramenta responder.

## Endpoints REST (para integração institucional independente do Gradio)

- `POST /api/v2/analisar/pdf` com `arquivo`, `numero_cnj` opcional e `pagina_sentenca` opcional. Retorna JSON de atos, páginas e `pauta_markdown`.
- `POST /api/v2/analisar/texto` com `texto`, `numero_cnj` opcional e `pagina_sentenca` opcional. Retorna os mesmos campos.
- `POST /api/v2/analisar/pdf/docx` com PDF para baixar um Word com a cronologia e até seis capturas relevantes para conferência.
- `GET /api/v1/processos/{numero_cnj}/consulta` somente metadados públicos DataJud.

**Segurança:** mantenha segredos apenas no Render, rotacione a chave já exibida em captura de tela, não inclua dados sigilosos em testes ou repositórios públicos. Sempre confira o inteiro teor antes de utilizar a pauta.