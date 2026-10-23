"""Testes locais de interface Gradio e autenticação; não dependem da rede."""
from pathlib import Path
import sys
import asyncio
import json
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import gradio as gr
import api
from chatjt_adapter import _autorizar, consultar_cnj, triagem_texto, formatar_pauta


class Requisicao:
    def __init__(self, **cabecalhos):
        self.headers = cabecalhos


def test_gradio_descoberta_e_site_preservado():
    c = TestClient(api.app)
    assert c.get('/').status_code == 200
    assert c.get('/docs').status_code == 200
    assert c.get('/chatjt').status_code == 200
    config = c.get('/chatjt/config').json()
    assert config['mode'] == 'blocks'
    info = c.get('/chatjt/gradio_api/info').json()
    assert {'/consultar_cnj','/analisar_texto','/formatar_pauta'} <= set(info['named_endpoints'])
    # Interface de ferramenta não recebe arquivos por Gradio; API REST protegida mantém o PDF.
    assert all(component.get('type') != 'file' for component in config['components'])


def test_chave_exigida_sem_fallback_publico(monkeypatch):
    monkeypatch.delenv('CEJUSC_API_KEY', raising=False)
    with pytest.raises(gr.Error):
        _autorizar(Requisicao())
    monkeypatch.setenv('CEJUSC_API_KEY','VALOR_INVENTADO_TESTE')
    with pytest.raises(gr.Error):
        _autorizar(Requisicao())
    with pytest.raises(gr.Error):
        _autorizar(Requisicao(**{'x-ip-token':'qualquer-valor-nao-assinado'}))
    _autorizar(Requisicao(**{'x-api-key':'VALOR_INVENTADO_TESTE'}))
    _autorizar(Requisicao(**{'x-ip-token':'VALOR_INVENTADO_TESTE'}))


def test_rest_tambem_aceita_chave_literal_x_ip_token(monkeypatch):
    monkeypatch.setenv('CEJUSC_API_KEY','TESTE_SOMENTE_NAO_USAR_EM_PRODUCAO')
    c = TestClient(api.app)
    data={'texto':'SENTENÇA com relatório de prova pericial e honorários sucumbenciais em 15%.','fase':'liquidacao'}
    assert c.post('/api/v1/analisar/texto',json=data).status_code == 401
    assert c.post('/api/v1/analisar/texto',json=data,headers={'X-IP-Token':'valor-falso'}).status_code == 401
    assert c.post('/api/v1/analisar/texto',json=data,headers={'X-IP-Token':'TESTE_SOMENTE_NAO_USAR_EM_PRODUCAO'}).status_code == 200


def test_consulta_cnj_e_tratamento_de_erro(monkeypatch):
    monkeypatch.setenv('CEJUSC_API_KEY','SEGREDO_FICTICIO')
    monkeypatch.delenv('DATAJUD_API_KEY',raising=False)
    msg=asyncio.run(consultar_cnj('0011087-25.2017.5.15.0127', Requisicao(**{'x-api-key':'SEGREDO_FICTICIO'})))
    assert 'DATAJUD' in msg
    assert 'SEGREDO_FICTICIO' not in msg


def test_texto_desde_sentenca_e_formatacao(monkeypatch):
    monkeypatch.setenv('CEJUSC_API_KEY','SEGREDO_FICTICIO')
    r=Requisicao(**{'x-api-key':'SEGREDO_FICTICIO'})
    texto='[PÁGINA 1]\nPETIÇÃO INICIAL - pagamento R$ 1.000,00\n[PÁGINA 2]\nSENTENÇA\nAnte o exposto, JULGO PARCIALMENTE PROCEDENTES os pedidos.\n[PÁGINA 3]\nDEPÓSITO RECURSAL R$ 5.000,00'
    triagem=asyncio.run(triagem_texto(texto,'liquidacao',0,r))
    assert 'depósito' in triagem.lower() or 'DEPOSITO' in triagem
    json_pauta={'fase':'liquidacao','numero_cnj':'0011087-25.2017.5.15.0127',
                'vara':'Vara do Trabalho de teste','polo_ativo':'Autor fictício','polo_passivo':'Empresa fictícia',
                'eventos':[{'data':'01/03/2020','ato':'SENTENÇA','descricao':'Deferidas verbas fictícias em R$ 1.000,00','pagina_pdf':2}]}
    pauta=asyncio.run(formatar_pauta(json.dumps(json_pauta),r))
    assert '01/03/2020' in pauta
    assert 'p. PDF 2' in pauta
    assert 'NÃO CERTIFICA' in pauta.upper()