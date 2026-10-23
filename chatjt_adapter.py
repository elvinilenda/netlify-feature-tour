"""Adaptador Gradio para descoberta e funções do Chat-JT.

O cadastro de ferramenta do Chat-JT pode usar o protocolo Gradio, e NÃO OpenAPI.
O X-IP-Token informado pelo Chat-JT pode conter identidade codificada; este projeto
NÃO assume esquema de assinatura desconhecido. Somente compara um token que seja
literalmente igual à chave de serviço; não autentica valores arbitrários.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import os
from typing import Any

import gradio as gr
from pydantic import ValidationError


def _autorizar(request: gr.Request | None) -> None:
    """Proteção fail-closed; metadados Gradio permanecem públicos para descoberta.

    A tela pública Gradio não dá autorização para executar operações. Somente
    X-API-Key ou X-IP-Token *literalmente igual à chave* é aceito. Tokens
    de usuário criptografados pelo Chat-JT requerem acordo técnico/documentado.
    """
    esperado = os.environ.get('CEJUSC_API_KEY', '').strip()
    if not esperado:
        raise gr.Error('Serviço bloqueado: configurar CEJUSC_API_KEY no Render.')
    cab = request.headers if request is not None else {}
    candidatos = (cab.get('x-api-key', ''), cab.get('x-ip-token', ''))
    if not any(valor and hmac.compare_digest(valor, esperado) for valor in candidatos):
        raise gr.Error(
            '401: credencial inválida. A ferramenta requer X-API-Key ou X-IP-Token '
            'literal com a chave do serviço. Se o Chat-JT enviar X-IP-Token '
            'codificado, é necessária integração institucional para verificação.'
        )


def _erro_publico(exc: Exception) -> str:
    """Erros curtos, sem reprodução de payload, chave ou documentos nos logs."""
    status = getattr(exc, 'status_code', None)
    if status == 503:
        return 'Consulta DataJud indisponível: chave DATAJUD_API_KEY não configurada.'
    if status == 422:
        return 'Número CNJ inválido; confira a numeração trabalhista de 20 dígitos.'
    if status == 502:
        return 'Falha de comunicação com DataJud/CNJ; consulte os logs do servidor.'
    return f'Não foi possível concluir a operação ({type(exc).__name__}).'


async def consultar_cnj(numero_cnj: str, request: gr.Request) -> str:
    """Consultar APENAS metadados e movimentações públicos do DataJud por CNJ."""
    _autorizar(request)
    from api import _consultar_datajud, _pauta_publica
    try:
        dados = await _consultar_datajud(numero_cnj.strip())
    except Exception as exc:
        return _erro_publico(exc)
    return _pauta_publica(dados) + '\n\n**AVISO:** sem teor integral, valores ou decisões confirmadas.'


async def triagem_texto(texto: str, fase: str, pagina_sentenca: int, request: gr.Request) -> str:
    """Localizar INDÍCIOS documentais após sentença em TEXTO fornecido no Chat-JT.

    A saída NÃO constitui parecer jurídico. Não enviar autos sigilosos para
    servidor público sem autorização institucional e política de dados.
    """
    _autorizar(request)
    from motor import analisar_texto, relatorio
    if not texto or len(texto) < 10:
        return 'Texto insuficiente para triagem. Forneça trecho processual com sentença.'
    if len(texto) > 300_000:
        return 'Texto excede o limite deste conector (300.000 caracteres). Divida o conteúdo.'
    if fase not in ('liquidacao', 'execucao'):
        return 'Fase inválida: selecione liquidacao ou execucao.'
    try:
        resultado = await asyncio.to_thread(analisar_texto, texto, fase, int(pagina_sentenca))
    except Exception as exc:
        return _erro_publico(exc)
    return relatorio(resultado) + '\n\n**ATENÇÃO:** indícios não substituem o exame do documento original.'


async def formatar_pauta(eventos_json: str, request: gr.Request) -> str:
    """Formatar eventos com data e ID/página, fornecidos após conferência documental.

    Recebe JSON conforme PautaEntrada e não inventa nem confirma fatos.
    """
    _autorizar(request)
    from api import PautaEntrada, _gerar_pauta_confirmavel
    if len(eventos_json or '') > 250_000:
        return 'JSON excede o limite de 250.000 caracteres.'
    try:
        dados: Any = json.loads(eventos_json)
        entrada = PautaEntrada.model_validate(dados)
        saida = _gerar_pauta_confirmavel(entrada)
    except (ValueError, ValidationError, TypeError):
        return 'JSON inválido ou incompleto. Informe fase, CNJ, Vara, partes e eventos com data e página/ID.'
    return saida['pauta_markdown']


def montar_chatjt(app):
    """Montar o Gradio em /chatjt sem alterar /, /docs nem /api/v1."""
    with gr.Blocks(title='Ferramenta CEJUSC para Chat-JT') as interface:
        gr.Markdown(
            '# CEJUSC – integração Chat-JT\n'
            'Ferramenta de **triagem documental**. Não substitui leitura dos autos. '
            'Funções exigem autenticação; a estrutura Gradio é pública para descoberta.'
        )
        with gr.Tab('Consulta pública CNJ'):
            cnj = gr.Textbox(label='Número CNJ', placeholder='0011087-25.2017.5.15.0127')
            consulta = gr.Button('Consultar metadados públicos')
            previa = gr.Textbox(label='Prévia (não certificada)', lines=12)
            consulta.click(consultar_cnj, inputs=[cnj], outputs=[previa], api_name='consultar_cnj', queue=False)
        with gr.Tab('Triagem de texto'):
            conteudo = gr.Textbox(label='Texto extraído do processo', lines=8)
            fase = gr.Dropdown(['liquidacao', 'execucao'], value='liquidacao', label='Fase')
            pagina = gr.Number(label='Página da sentença (0 = localizar)', value=0, precision=0)
            analisar = gr.Button('Identificar ocorrências')
            rel = gr.Textbox(label='Indícios e páginas – conferência obrigatória', lines=12)
            analisar.click(triagem_texto, inputs=[conteudo, fase, pagina], outputs=[rel],
                          api_name='analisar_texto', queue=False)
        with gr.Tab('Pauta a partir de eventos conferidos'):
            dados = gr.Textbox(label='Eventos em JSON (PautaEntrada)', lines=8)
            fmt = gr.Button('Formatar pauta')
            pauta = gr.Textbox(label='Pauta – sujeita a conferência', lines=12)
            fmt.click(formatar_pauta, inputs=[dados], outputs=[pauta], api_name='formatar_pauta', queue=False)
    return gr.mount_gradio_app(app, interface, path='/chatjt',
                               show_error=False, footer_links=[],
                               max_file_size='1mb')