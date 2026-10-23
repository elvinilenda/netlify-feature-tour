"""API + interface CEJUSC: triagem textual transparente e consulta DataJud de metadados.

Apenas acesso a documentos publicamente autorizados; não autentica no PJe.
Nunca apresenta indícios textuais como decisões confirmadas.
"""
from __future__ import annotations

import os
import io
import re
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Literal

import httpx
from starlette.concurrency import run_in_threadpool
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator

from motor import analisar_pdf, analisar_texto, relatorio
from pauta_integrada import analisar_texto_integrado, analisar_pdf_integrado
from exportar_pauta import gerar_docx

ROOT = Path(__file__).resolve().parent
MAX_PDF_BYTES = 70 * 1024 * 1024
CNJ_RE = re.compile(r'^\d{7}-?\d{2}\.?\d{4}\.?[1-9]\.?(?:\d{2})\.?\d{4}$')
SENTENCE_RE = re.compile(r'\bsenten[cç]a\b|\bjulgad[oa]s?\s+(?:procedent|improcedent)', re.I)
TRT_RE = re.compile(r'^\d{7}-\d{2}\.\d{4}\.5\.(\d{2})\.\d{4}$')

app = FastAPI(
    title='API CEJUSC – Auditoria Processual Trabalhista',
    version='4.0.0',
    description=('API de apoio documental: leitura de PDF desde a sentença, rastreamento de indícios '
                 'com páginas e pesquisa pública de metadados no DataJud/CNJ. Não consulta o inteiro teor do PJe.'),
    docs_url='/docs',
    redoc_url='/redoc',
)


async def acesso(request: Request, x_api_key: str | None = Header(default=None, alias='X-API-Key'),
                 x_ip_token: str | None = Header(default=None, alias='X-IP-Token')):
    """Chave obrigatória para acesso remoto; sem chave, somente loopback no protótipo."""
    expected = os.environ.get('CEJUSC_API_KEY', '').strip()
    if expected:
        import hmac
        if not any(token and hmac.compare_digest(token, expected)
                   for token in (x_api_key, x_ip_token)):
            raise HTTPException(status_code=401, detail='Informe X-API-Key válido; X-IP-Token só é aceito se idêntico à chave do serviço.')
        return
    host = request.client.host if request.client else ''
    http_host = request.headers.get('host', '').split(':')[0].lower()
    if host not in ('127.0.0.1', '::1', 'localhost', 'testclient') or http_host not in ('127.0.0.1','localhost','[::1]','testserver'):
        raise HTTPException(status_code=403, detail='Acesso remoto desativado. Configure CEJUSC_API_KEY e proteja com HTTPS.')


class TextoEntrada(BaseModel):
    texto: str = Field(min_length=10, max_length=5_000_000, description='Texto dos autos com [PÁGINA N] ou quebras de página.')
    fase: Literal['liquidacao', 'execucao'] = 'liquidacao'
    pagina_sentenca: int = Field(default=0, ge=0, le=5000)
    numero_cnj: str | None = None


class ProcessoEntradaAutomatica(BaseModel):
    texto: str = Field(min_length=10, max_length=5_000_000, description='Texto dos autos, desde a sentença (ou integral, com páginas).')
    numero_cnj: str | None = None
    pagina_sentenca: int = Field(default=0, ge=0, le=5000)


class EventoConferido(BaseModel):
    """Evento fornecido pelo analista/Chat-JT; a API não confirma a prova."""
    data: str = Field(pattern=r'^\d{2}/\d{2}/\d{4}$')
    ato: str = Field(min_length=3, max_length=130)
    descricao: str = Field(min_length=5, max_length=1600)
    pagina_pdf: int | None = Field(default=None, ge=1)
    id_pje: str | None = Field(default=None, max_length=100)
    conferido_por_analista: bool = False

    @model_validator(mode='after')
    def exigir_fonte(self):
        if not self.pagina_pdf and not self.id_pje:
            raise ValueError('Informe página PDF ou ID PJe para cada acontecimento.')
        try:
            datetime.strptime(self.data, '%d/%m/%Y')
        except ValueError as exc:
            raise ValueError('Data inexistente no calendário.') from exc
        return self


class PautaEntrada(BaseModel):
    """Formata acontecimentos apresentados com documentos-fonte; não valida seu mérito."""
    fase: Literal['liquidacao', 'execucao']
    numero_cnj: str
    vara: str = Field(min_length=3, max_length=250)
    horario: str = Field(default='HORÁRIO NÃO INFORMADO', max_length=60)
    polo_ativo: str = Field(min_length=3, max_length=300)
    polo_passivo: str = Field(min_length=3, max_length=450)
    peritos: str | None = Field(default=None, max_length=350)
    eventos: list[EventoConferido] = Field(min_length=1, max_length=350)


def _emphasis(texto: str) -> str:
    """Destaque numérico e de status; entradas são apenas texto literal do usuário."""
    texto = re.sub(r'[\r\n]+', ' ', texto).replace('**', '').strip()
    texto = re.sub(r'(R\$\s*[\d.]+(?:,\d{2})?|\b\d+(?:,\d+)?%\b|\bPOSITIVO\b|\bNEGATIVO\b)',
                   lambda m: f'**{m.group(0)}**', texto, flags=re.I)
    return texto


def _gerar_pauta_confirmavel(entrada: PautaEntrada) -> dict:
    _, fmt, _ = normalizar_cnj(entrada.numero_cnj)
    fase = 'LIQUIDAÇÃO' if entrada.fase == 'liquidacao' else 'EXECUÇÃO'
    titulo = f'**{entrada.horario} - {fmt} - {entrada.vara} - FASE DE {fase}**'
    linhas = [titulo, '', f'Polo ativo: {entrada.polo_ativo}', '', '.', '',
              f'Polo passivo: {entrada.polo_passivo}', '', '.', '']
    if entrada.peritos:
        linhas += ['', f'Peritos: {entrada.peritos}', '', '.', '']
    pendencias = []
    eventos_ordenados = sorted(enumerate(entrada.eventos),
             key=lambda e: (datetime.strptime(e[1].data, '%d/%m/%Y'), e[0]))
    for index, ev in eventos_ordenados:
        fonte = []
        if ev.pagina_pdf: fonte.append(f'p. PDF {ev.pagina_pdf}')
        if ev.id_pje: fonte.append(f'ID PJe {ev.id_pje}')
        linhas += ['', f'**{ev.data} - {ev.ato.upper()}**: {_emphasis(ev.descricao)}. ({"; ".join(fonte)})', '', '.', '']
        if not ev.conferido_por_analista:
            pendencias.append({'evento_original': index+1, 'ato': ev.ato,
                               'motivo': 'Exige conferência do documento-fonte por analista.'})
    linhas += ['', '**AVISO:** pauta formatada a partir de informações fornecidas; não certifica a veracidade dos atos.']
    return {'natureza':'pauta_formatada_pendente_conferencia', 'numero_cnj':fmt,
            'fase':entrada.fase, 'eventos_recebidos':len(entrada.eventos),
            'pendencias':pendencias, 'pauta_markdown':'\n'.join(linhas)}


def _indice_prioritario(resultado: dict) -> dict:
    """Separação visível das principais movimentações no retorno da triagem."""
    grupos = {
        'recursos_e_acordaos': ('embargos_declaracao','recurso_ordinario','recurso_revista','agravo_instrumento','agravo_peticao','outros_recursos','acordao'),
        'depositos_recursais_e_custas': ('deposito_recursal','seguro_garantia','custas'),
        'liquidacao_e_valores': ('calculos','impugnacao','homologacao','pericia','honorarios_sucumbenciais'),
        'execucao_e_patrimonio': ('sisbajud','bloqueios','renajud','imoveis','penhoras','mandados','idpj'),
        'pagamentos_acordos_e_alvaras': ('deposito_judicial','pagamento','alvaras','acordo','parcelamento'),
        'audiencia_e_despachos': ('audiencia','ultimo_despacho'),
    }
    return {grupo: [ev for ev in resultado.get('ocorrencias',[]) if ev['categoria'] in cats][:150]
            for grupo,cats in grupos.items()}


def normalizar_cnj(numero: str) -> tuple[str, str, str]:
    bruto = re.sub(r'\D', '', numero)
    if len(bruto) != 20 or not bruto.isdigit():
        raise HTTPException(422, 'Número CNJ inválido. Ex.: 0011087-25.2017.5.15.0127')
    cod_justica, regiao = bruto[13], bruto[14:16]
    if cod_justica != '5' or not ('01' <= regiao <= '24'):
        raise HTTPException(422, 'Esta API está configurada para processos da Justiça do Trabalho (TRT 1 a 24).')
    formatado = f'{bruto[:7]}-{bruto[7:9]}.{bruto[9:13]}.{bruto[13]}.{regiao}.{bruto[16:]}'
    return bruto, formatado, f'trt{int(regiao)}'


def _data(d: str | None) -> str:
    if not d:
        return ''
    # DataJud costuma enviar YYYY-MM-DDTHH:MM:SS ou YYYYMMDDHHMMSS.
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%Y%m%d%H%M%S', '%Y%m%d'):
        try:
            return datetime.strptime(d[:len(datetime.now().strftime(fmt))], fmt).strftime('%d/%m/%Y')
        except (ValueError, TypeError):
            continue
    if len(d) >= 10 and re.match(r'\d{4}-\d{2}-\d{2}', d):
        return f'{d[8:10]}/{d[5:7]}/{d[:4]}'
    return str(d)


def _normalizar_movimentos(mov: list[dict]) -> list[dict]:
    resultado = []
    for item in mov:
        nome = str(item.get('nome') or '').strip()
        data_raw = str(item.get('dataHora') or '')
        compl = item.get('complementosTabelados') or []
        resultado.append({
            'data': _data(data_raw), 'data_original': data_raw, 'movimento': nome,
            'codigo': item.get('codigo'),
            'complementos': [{'nome': c.get('nome'), 'descricao': c.get('descricao'),
                              'valor': c.get('valor')} for c in compl[:10] if isinstance(c, dict)],
            'fonte': 'DataJud/CNJ – metadados, não inteiro teor',
        })
    resultado.sort(key=lambda x: x['data_original'])
    return resultado


async def _consultar_datajud(numero: str) -> dict:
    bruto, formatado, alias = normalizar_cnj(numero)
    key = os.environ.get('DATAJUD_API_KEY', '').strip()
    if not key:
        raise HTTPException(503, detail={
            'mensagem': 'Configure DATAJUD_API_KEY com a chave pública vigente do CNJ.',
            'documentacao': 'https://datajud-wiki.cnj.jus.br/api-publica/acesso/',
        })
    url = f'https://api-publica.datajud.cnj.jus.br/api_publica_{alias}/_search'
    query = {'size': 10, 'query': {'match': {'numeroProcesso': bruto}}}
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=False) as client:
            response = await client.post(url, json=query, headers={
                'Authorization': f'APIKey {key}', 'Content-Type': 'application/json', 'Accept': 'application/json'
            })
        response.raise_for_status()
        dados = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, detail=f'Falha ao consultar o DataJud: {type(exc).__name__}. Verifique conexão, chave e disponibilidade.') from exc
    hits = dados.get('hits', {}).get('hits', [])
    # Só mantém correspondência exata e não tenta identificar nomes/valores ausentes.
    exatos = [h.get('_source', {}) for h in hits if re.sub(r'\D', '', str(h.get('_source', {}).get('numeroProcesso', ''))) == bruto]
    if not exatos:
        return {
            'numero_cnj': formatado, 'tribunal': alias.upper(), 'encontrado': False,
            'fonte': url, 'avisos': ['Processo não localizado na API pública do DataJud; isso não confirma inexistência no PJe.'],
            'movimentacoes_desde_sentenca': [], 'processo': {},
        }
    fonte = max(exatos, key=lambda x: len(x.get('movimentos', [])))
    orgao = fonte.get('orgaoJulgador') or {}
    classe = fonte.get('classe') or {}
    movimentos = _normalizar_movimentos(fonte.get('movimentos') or [])
    i_sentenca = next((i for i, e in enumerate(movimentos) if SENTENCE_RE.search(e['movimento'])), None)
    avisos = [
        'DataJud oferece capa e movimentações públicas, não PDF da sentença, acórdãos, comprovantes ou peças integrais.',
        'Movimentações podem estar incompletas ou desatualizadas. Não inferir depósitos, valores, reformas ou fase apenas pelo título.',
    ]
    if i_sentenca is None:
        avisos.append('Marco da sentença não identificado com segurança; nenhuma movimentação anterior foi usada na prévia. Anexe PDF.')
        corte = []
    else:
        corte = movimentos[i_sentenca:]
    return {
        'numero_cnj': formatado, 'tribunal': alias.upper(), 'encontrado': True,
        'fonte': url,
        'processo': {
            'numeroProcesso': fonte.get('numeroProcesso'),
            'dataAjuizamento': _data(str(fonte.get('dataAjuizamento') or '')),
            'classe': classe.get('nome') if isinstance(classe, dict) else classe,
            'orgaoJulgador': orgao.get('nome') if isinstance(orgao, dict) else orgao,
            'grau': fonte.get('grau'),
        },
        'sentenca_detectada': i_sentenca is not None,
        'total_movimentacoes_publicas': len(movimentos),
        'movimentacoes_desde_sentenca': corte,
        'avisos': avisos,
    }


def _pauta_publica(obj: dict) -> str:
    processo = obj['numero_cnj']
    if not obj['encontrado']:
        return f'**{processo}**\n\nNão localizado nos metadados públicos do DataJud. Anexe o PDF para análise documental.'
    lines = [f'# PRÉVIA DOCUMENTAL – {processo}',
             '> DADOS CADASTRAIS DO DATAJUD. NÃO É RESUMO DEFINITIVO DE PAUTA.',
             f"**Unidade:** {obj.get('processo', {}).get('orgaoJulgador') or 'não informada'}", '']
    for mov in obj['movimentacoes_desde_sentenca']:
        lines += [f"**{mov['data'] or 'DATA NÃO INFORMADA'} – {mov['movimento'] or 'MOVIMENTAÇÃO'}:** registro público de movimentação; consultar documento original para especificações.", '', '.', '']
    if not obj['movimentacoes_desde_sentenca']:
        lines.append('Não foi possível estabelecer o marco da sentença. Envie PDF para extrair atos com páginas.')
    lines += ['','**Pendências:** conferir sentença, recursos, depósitos, valores, acórdãos, cálculos e último despacho no inteiro teor.',
              '**Fonte:** DataJud/CNJ, somente metadados públicos.']
    return '\n'.join(lines)


def _retorno_triagem(obj: dict, numero: str | None = None) -> dict:
    # Permite que Chat-JT receba texto e dados separados, sem inventar eventos.
    if numero:
        _, fmt, _ = normalizar_cnj(numero)
    else:
        fmt = None
    return {
        'numero_cnj': fmt,
        'fase_solicitada': obj.get('fase'),
        'situacao': obj.get('status'),
        'intervalo_paginas': {'inicio': obj.get('pagina_inicial'), 'fim': obj.get('pagina_final')},
        'relatorio_markdown': relatorio(obj),
        'ocorrencias': obj.get('ocorrencias', []),
        'checklist': obj.get('campos_obrigatorios', []),
        'avisos': obj.get('limites', []),
        'natureza': 'triagem textual, NÃO conclusão jurídica ou resultado confirmado',
        'indice_prioritario': _indice_prioritario(obj),
    }


@app.get('/', include_in_schema=False)
async def site():
    return FileResponse(ROOT / 'static' / 'index.html', media_type='text/html')


@app.get('/api/v1/saude', tags=['Sistema'])
async def saude():
    return {'status': 'ok', 'produto': 'API CEJUSC', 'versao': app.version,
            'datajud_configurado': bool(os.environ.get('DATAJUD_API_KEY')),
            'autenticacao_configurada': bool(os.environ.get('CEJUSC_API_KEY'))}


@app.post('/api/v2/analisar/texto', tags=['Pauta automática única'], dependencies=[Depends(acesso)])
async def analisar_processo_texto_auto(entrada: ProcessoEntradaAutomatica):
    """Avalia, numa leitura, critérios de LIQUIDAÇÃO e EXECUÇÃO sem escolher fase."""
    try:
        return await run_in_threadpool(analisar_texto_integrado, entrada.texto, entrada.numero_cnj, entrada.pagina_sentenca)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@app.post('/api/v2/analisar/pdf', tags=['Pauta automática única'], dependencies=[Depends(acesso)])
async def analisar_processo_pdf_auto(
    arquivo: UploadFile = File(description='PDF pesquisável, até 70 MB'),
    numero_cnj: str | None = Form(None),
    pagina_sentenca: int = Form(0, ge=0),
):
    if not arquivo.filename or not arquivo.filename.lower().endswith('.pdf'):
        raise HTTPException(422, 'Envie um PDF válido.')
    path = None
    try:
        with tempfile.NamedTemporaryFile(prefix='cejusc_', suffix='.pdf',delete=False) as f:
            path=Path(f.name)
            total=0
            head=True
            while chunk := await arquivo.read(1024*1024):
                total += len(chunk)
                if total>MAX_PDF_BYTES:raise HTTPException(413, 'O PDF excede 70 MB.')
                if head:
                    head=False
                    if not chunk.startswith(b'%PDF-'): raise HTTPException(422,'Arquivo não é PDF.')
                f.write(chunk)
        try:
            return await run_in_threadpool(analisar_pdf_integrado, str(path), numero_cnj, pagina_sentenca)
        except ValueError as exc:
            raise HTTPException(422, detail=str(exc)) from exc
    finally:
        await arquivo.close()
        if path: path.unlink(missing_ok=True)


@app.post('/api/v2/analisar/pdf/docx', tags=['Pauta automática única'], dependencies=[Depends(acesso)])
async def exportar_pauta_pdf(
    arquivo: UploadFile = File(description='PDF pesquisável, até 70 MB'),
    numero_cnj: str | None = Form(None),
    pagina_sentenca: int = Form(0,ge=0),
):
    """Gera DOCX no padrão cronológico CEJUSC, com prints de páginas relevantes.

    Não incorpora prints quando o PDF não tem páginas acessíveis; nunca alega prova
    confirmada automaticamente.
    """
    if not arquivo.filename or not arquivo.filename.lower().endswith('.pdf'):
        raise HTTPException(422,'Envie PDF válido.')
    path=None
    try:
        with tempfile.NamedTemporaryFile(prefix='cejusc_',suffix='.pdf',delete=False) as f:
            path=Path(f.name);tamanho=0;primeiro=True
            while chunk:=await arquivo.read(1024*1024):
                tamanho+=len(chunk)
                if tamanho>MAX_PDF_BYTES:raise HTTPException(413,'PDF excede 70 MB.')
                if primeiro:
                    primeiro=False
                    if not chunk.startswith(b'%PDF-'):raise HTTPException(422,'Arquivo não é PDF.')
                f.write(chunk)
        try:
            resultado=await run_in_threadpool(analisar_pdf_integrado,str(path),numero_cnj,pagina_sentenca)
            dados=await run_in_threadpool(gerar_docx,resultado,str(path))
        except ValueError as exc:
            raise HTTPException(422,detail=str(exc)) from exc
        return StreamingResponse(io.BytesIO(dados),media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                 headers={'Content-Disposition':'attachment; filename="pauta_cejusc_preliminar.docx"'})
    finally:
        await arquivo.close()
        if path:path.unlink(missing_ok=True)


@app.post('/api/v1/analisar/texto', tags=['Análise documental'], dependencies=[Depends(acesso)])
async def analisar_texto_endpoint(entrada: TextoEntrada):
    try:
        return _retorno_triagem(await run_in_threadpool(analisar_texto, entrada.texto, entrada.fase, entrada.pagina_sentenca), entrada.numero_cnj)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@app.post('/api/v1/analisar/pdf', tags=['Análise documental'], dependencies=[Depends(acesso)])
async def analisar_pdf_endpoint(
    arquivo: UploadFile = File(description='Processo PDF pesquisável, até 70 MB'),
    fase: Literal['liquidacao','execucao'] = Form('liquidacao'),
    pagina_sentenca: int = Form(0, ge=0),
    numero_cnj: str | None = Form(None),
):
    if not arquivo.filename or not arquivo.filename.lower().endswith('.pdf'):
        raise HTTPException(422, 'Envie um arquivo com extensão .pdf.')
    path = None
    try:
        with tempfile.NamedTemporaryFile(prefix='cejusc_', suffix='.pdf', delete=False) as f:
            path = Path(f.name)
            size = 0
            first = True
            while chunk := await arquivo.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_PDF_BYTES:
                    raise HTTPException(413, 'O PDF excede o limite de 70 MB.')
                if first:
                    first = False
                    if not chunk.startswith(b'%PDF-'):
                        raise HTTPException(422, 'O arquivo enviado não parece ser um PDF válido.')
                f.write(chunk)
        try:
            resultado = await run_in_threadpool(analisar_pdf, str(path), fase, pagina_sentenca)
        except ValueError as exc:
            raise HTTPException(422, detail=str(exc)) from exc
        return _retorno_triagem(resultado, numero_cnj)
    finally:
        await arquivo.close()
        if path:
            path.unlink(missing_ok=True)


@app.get('/api/v1/processos/{numero_cnj}/consulta', tags=['Consulta pública'], dependencies=[Depends(acesso)])
async def consultar_processo(numero_cnj: str):
    """Consulta metadados públicos no CNJ/DataJud (não consulta PDFs do PJe)."""
    data = await _consultar_datajud(numero_cnj)
    data['previa_markdown'] = _pauta_publica(data)
    return data


@app.get('/api/v1/processos/{numero_cnj}/previa', tags=['Consulta pública'], dependencies=[Depends(acesso)])
async def gerar_previa(numero_cnj: str):
    """Prévia cronológica baseada apenas em movimentações públicas após sentença; sem conclusões de mérito."""
    data = await _consultar_datajud(numero_cnj)
    return {'numero_cnj': data['numero_cnj'], 'fonte': data['fonte'],
            'previa_markdown': _pauta_publica(data), 'avisos': data['avisos']}


@app.post('/api/v1/pautas/formatar', tags=['Preparação de pauta'], dependencies=[Depends(acesso)])
async def formatar_pauta(entrada: PautaEntrada):
    """Formata atos individualizados com data e documento-fonte. Não inventa ou verifica eventos."""
    return _gerar_pauta_confirmavel(entrada)


@app.get('/api/v1/capacidades', tags=['Sistema'])
async def capacidades():
    return {
        'aplicacao':'CEJUSC – análise documental',
        'recurso':'análise textual conjunta de liquidação e execução, metadados públicos CNJ e pauta cronológica rastreável',
        'limites':['Sem acesso autenticado ao PJe', 'Sem IA de interpretação jurídica embutida',
                  'Sem OCR automático', 'Requer revisão jurídica antes do uso em audiência'],
        'cadastro_chat_jt':'Adaptador Gradio em /chatjt. O X-IP-Token criptografado requer validação de formato com TI do Chat-JT.',
        'gradio_url_path':'/chatjt',
        'operacoes_gradio':['analisar_processo']
    }


# Gradio funciona em subcaminho e mantém a API/site existentes.
from chatjt_adapter import montar_chatjt
app = montar_chatjt(app)