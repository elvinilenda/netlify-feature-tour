"""Ferramenta única Chat-JT. Analisa sempre conhecimento desde sentença, liquidação E execução.

A saída é uma pauta preliminar rastreável, nunca substitui conferência do inteiro teor.
X-IP-Token cifrado pelo Chat-JT NÃO pode ser decodificado por adivinhação.
"""
from __future__ import annotations

import asyncio
import hmac
import os
from pathlib import Path

import gradio as gr


def _autorizar(request: gr.Request | None) -> None:
    esperado = os.environ.get('CEJUSC_API_KEY', '').strip()
    if not esperado:
        raise gr.Error('Serviço protegido. Configure CEJUSC_API_KEY no Render.')
    cab = request.headers if request is not None else {}
    candidatos = (cab.get('x-api-key', ''), cab.get('x-ip-token',''))
    if not any(v and hmac.compare_digest(v, esperado) for v in candidatos):
        raise gr.Error('401: acesso não autorizado. É necessário adequar a autenticação do Chat-JT (X-IP-Token) à política institucional.')


def _erro_publico(exc: Exception) -> str:
    code=getattr(exc, 'status_code', None)
    if code==503:return 'Consulta pública DataJud indisponível: configure DATAJUD_API_KEY.'
    if code==422:return 'Confira o número CNJ informado.'
    return f'Não foi possível concluir ({type(exc).__name__}). Confira os logs sem compartilhar dados processuais.'


async def analisar_processo(numero_cnj: str, texto: str, arquivo: str | None, request: gr.Request) -> str:
    """Função ÚNICA: analisar critérios de liquidação e execução em paralelo desde a sentença.

    PDF > texto > CNJ (metadados apenas). Não seleciona fase.
    """
    _autorizar(request)
    from pauta_integrada import analisar_texto_integrado, analisar_pdf_integrado
    cnj=(numero_cnj or '').strip() or None
    try:
        if arquivo:
            path=Path(str(arquivo))
            if not path.exists() or path.suffix.lower()!='.pdf':
                return 'Anexe um PDF pesquisável válido.'
            if path.stat().st_size > 70*1024*1024:
                return 'PDF excede 70 MB.'
            result=await asyncio.to_thread(analisar_pdf_integrado,str(path),cnj,0)
            return result['pauta_markdown']
        if texto and texto.strip():
            if len(texto)>300_000:
                return 'Texto acima de 300 mil caracteres para o conector Gradio. Use o PDF no site ou divida em volumes.'
            result=await asyncio.to_thread(analisar_texto_integrado,texto,cnj,0)
            return result['pauta_markdown']
        if cnj:
            from api import _consultar_datajud,_pauta_publica
            dados=await _consultar_datajud(cnj)
            return _pauta_publica(dados)+'\n\n**NECESSÁRIO:** anexe o PDF para a pauta completa. Metadados públicos não informam valores, comprovantes ou reformas de acórdãos.'
        return 'Informe o número CNJ, anexe um PDF pesquisável ou cole o texto do processo.'
    except Exception as exc:
        return _erro_publico(exc)


def montar_chatjt(app):
    """Uma operação Gradio discoverable em /chatjt; resta da API permanece."""
    with gr.Blocks(title='CEJUSC — Pauta Processual Automática') as interface:
        gr.Markdown('# CEJUSC – pauta processual automática\n'
                    '**Uma única análise**, desde a sentença, aplicando simultaneamente critérios de liquidação e execução. '
                    'O sistema indica a fase provável, os atos datados e as páginas para conferência. '
                    'Não substitui leitura jurídica integral dos documentos.')
        numero=gr.Textbox(label='Número CNJ (opcional se já consta no PDF)', placeholder='0000000-00.2025.5.15.0000')
        arquivo=gr.File(label='PDF do processo (opcional)',file_types=['.pdf'],type='filepath')
        texto=gr.Textbox(label='Texto dos autos (opcional se usar PDF)',lines=5)
        executar=gr.Button('Analisar processo completo — liquidação + execução', variant='primary')
        saida=gr.Textbox(label='Pauta cronológica preliminar',lines=20)
        executar.click(analisar_processo,inputs=[numero,texto,arquivo],outputs=[saida],api_name='analisar_processo',queue=False)
    return gr.mount_gradio_app(app,interface,path='/chatjt',show_error=False)