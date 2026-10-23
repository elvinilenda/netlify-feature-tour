import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import fitz
import pytest
import api

client = TestClient(api.app)
SENTENCA = 'PODER JUDICIÁRIO\nSENTENÇA\nAnte o exposto, JULGO PARCIALMENTE PROCEDENTES os pedidos.\n'


def test_site_and_openapi():
    assert client.get('/').status_code == 200
    assert 'Auditoria CEJUSC' in client.get('/').text
    j = client.get('/openapi.json').json()
    assert '/api/v1/analisar/pdf' in j['paths']
    assert '/api/v1/processos/{numero_cnj}/consulta' in j['paths']


def test_text_and_marco_sentenca():
    texto = '[PÁGINA 1]\nDepósito judicial R$ 15.000,00\n[PÁGINA 2]\n'+ SENTENCA + '[PÁGINA 3]\nComprovante de depósito recursal R$ 8.000,00\n'
    r = client.post('/api/v1/analisar/texto', json={'texto': texto, 'fase': 'liquidacao'})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j['intervalo_paginas']['inicio'] == 2
    assert all(x['pagina'] >= 2 for x in j['ocorrencias'])
    assert any(x['categoria'] == 'deposito_recursal' for x in j['ocorrencias'])
    assert j['natureza'].startswith('triagem')


def test_pdf_endpoint(tmp_path):
    f = tmp_path / 'caso.pdf'
    d = fitz.open()
    d.new_page().insert_text((45,45), 'Peticao inicial. Depósito R$ 9000,00')
    d.new_page().insert_text((45,45), SENTENCA)
    d.new_page().insert_text((45,45), 'SISBAJUD bloqueio positivo R$ 3.400,00')
    d.save(f)
    d.close()
    with f.open('rb') as fh:
        r = client.post('/api/v1/analisar/pdf', data={'fase':'execucao'}, files={'arquivo':('caso.pdf',fh,'application/pdf')})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j['intervalo_paginas']['inicio'] == 2
    assert any(x['categoria'] == 'sisbajud' for x in j['ocorrencias'])


def test_invalid_pdf():
    r = client.post('/api/v1/analisar/pdf', files={'arquivo': ('arquivo.pdf', b'not a real pdf', 'application/pdf')})
    assert r.status_code == 422


def test_numero_validacao():
    assert api.normalizar_cnj('0011087-25.2017.5.15.0127')[2] == 'trt15'
    with pytest.raises(Exception):
        api.normalizar_cnj('abc')
    with pytest.raises(Exception):
        api.normalizar_cnj('0011087-25.2017.4.15.0127')


def test_datajud_precisa_chave(monkeypatch):
    monkeypatch.delenv('DATAJUD_API_KEY', raising=False)
    r = client.get('/api/v1/processos/0011087-25.2017.5.15.0127/consulta')
    assert r.status_code == 503
    assert 'Configure DATAJUD_API_KEY' in r.text


def test_chave_requerida(monkeypatch):
    monkeypatch.setenv('CEJUSC_API_KEY','SEGREDO_TESTE')
    assert client.post('/api/v1/analisar/texto', json={'texto':'sentenca para teste de acesso'}).status_code == 401
    assert client.post('/api/v1/analisar/texto', json={'texto':'sentenca para teste de acesso'}, headers={'X-API-Key':'SEGREDO_TESTE'}).status_code == 200


def test_marco_datajud_sem_sentenca():
    movimentos=[{'nome':'Distribuído', 'dataHora':'20170102093000'}, {'nome':'Conclusos para decisão','dataHora':'20180520150000'}]
    eventos=api._normalizar_movimentos(movimentos)
    assert len(eventos)==2
    assert api._data('20180520150000')=='20/05/2018'


@pytest.mark.asyncio
async def test_consulta_fake_datajud(monkeypatch):
    monkeypatch.setenv('DATAJUD_API_KEY','TEST_PUBLIC_KEY')
    class Resp:
        def raise_for_status(self): pass
        def json(self):
            return {'hits':{'hits':[{'_source':{'numeroProcesso':'00110872520175150127',
                'classe': {'nome':'Ação Trabalhista'}, 'orgaoJulgador': {'nome':'1ª Vara do Trabalho'},
                'movimentos':[
                    {'nome':'Distribuição', 'dataHora':'20171107120000', 'codigo':1},
                    {'nome':'Proferida sentença', 'dataHora':'20180517120000', 'codigo':2},
                    {'nome':'Recurso ordinário', 'dataHora':'20180604120000', 'codigo':3},
                ]}}]}}
    class Client:
        def __init__(self,*args,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,*args,**kwargs): return Resp()
    monkeypatch.setattr(api.httpx,'AsyncClient',Client)
    j=await api._consultar_datajud('0011087-25.2017.5.15.0127')
    assert j['encontrado']
    assert len(j['movimentacoes_desde_sentenca'])==2
    assert j['movimentacoes_desde_sentenca'][0]['movimento']=='Proferida sentença'
    assert 'Distribuição' not in api._pauta_publica(j)