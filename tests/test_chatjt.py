"""Testes para integração de ferramenta única no Chat-JT, sem rede."""
import asyncio,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gradio as gr
import pytest
from fastapi.testclient import TestClient
import api
from chatjt_adapter import _autorizar,analisar_processo

class Request:
    def __init__(self,headers=None):self.headers=headers or {}


def test_gradio_uma_funcao_automatica():
    client=TestClient(api.app)
    assert client.get('/chatjt').status_code==200
    assert client.get('/').status_code==200
    assert set(client.get('/chatjt/gradio_api/info').json()['named_endpoints'])=={'/analisar_processo'}


def test_credencial_nao_exposta(monkeypatch):
    monkeypatch.setenv('CEJUSC_API_KEY','EXEMPLO_NAO_REAL')
    with pytest.raises(gr.Error):_autorizar(Request())
    with pytest.raises(gr.Error):_autorizar(Request({'x-ip-token':'TOKEN_CODIFICADO'}))
    _autorizar(Request({'x-api-key':'EXEMPLO_NAO_REAL'}))


def test_gradio_analisa_as_duas_sem_seletor(monkeypatch):
    monkeypatch.setenv('CEJUSC_API_KEY','EXEMPLO_NAO_REAL')
    texto='''[PÁGINA 1]
20/06/2025 - SENTENÇA
Julgo parcialmente procedentes os pedidos.
[PÁGINA 2]
15/07/2025 - ACÓRDÃO TRT
O recurso foi parcialmente provido.
[PÁGINA 3]
20/08/2025 - CÁLCULOS
Apurado crédito líquido de R$ 1.500,00.
[PÁGINA 4]
03/09/2025 - SISBAJUD
Bloqueio positivo de R$ 100,00.''' 
    result=asyncio.run(analisar_processo('',texto,None,Request({'x-api-key':'EXEMPLO_NAO_REAL'})))
    assert 'SENTENÇA' in result
    assert 'CÁLCULOS' in result
    assert 'SISBAJUD' in result
    assert 'EXECUÇÃO' in result


def test_gradio_sem_credencial_bloqueia(monkeypatch):
    monkeypatch.setenv('CEJUSC_API_KEY','EXEMPLO_NAO_REAL')
    with pytest.raises(gr.Error):
        asyncio.run(analisar_processo('','teste processual fictício',None,Request()))