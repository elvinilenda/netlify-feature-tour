"""Fluxo CEJUSC único — dados fictícios, sem acesso externo."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fitz
from fastapi.testclient import TestClient
import pytest
import api
import gradio as gr
from chatjt_adapter import analisar_processo
from pauta_integrada import analisar_texto_integrado
import asyncio

CNJ='0011087-25.2017.5.15.0127'
TEXTO='''[PÁGINA 1]
23/04/2025 - DISTRIBUIÇÃO
Autuação, valor da causa R$ 99.000,00.
[PÁGINA 2]
27/08/2025 - SENTENÇA
O Juízo julgou parcialmente procedentes os pedidos. Deferiu horas extras e dano moral de R$ 5.000,00. Fixou honorários de 10% e custas de R$ 400,00.
[PÁGINA 3]
10/09/2025 - RECURSO ORDINÁRIO E PREPARO
Recurso da reclamada. Depósito recursal: R$ 13.813,83. Custas processuais: R$ 400,00.
[PÁGINA 4]
30/03/2026 - ACÓRDÃO TRT-15
O Tribunal deu provimento parcial ao recurso para excluir a multa do art. 467 da CLT e manteve danos morais em R$ 5.000,00.
[PÁGINA 5]
22/04/2026 - TRÂNSITO EM JULGADO
Certificado.
[PÁGINA 6]
25/05/2026 - CÁLCULOS DA RECLAMADA
Apurou crédito líquido de R$ 32.000,00.
[PÁGINA 7]
08/06/2026 - HOMOLOGAÇÃO DOS CÁLCULOS
Homologado o valor de R$ 34.000,00.
[PÁGINA 8]
17/07/2026 - DETERMINAÇÃO DE PAGAMENTO
Notificada a empresa para pagar ou garantir execução em 15 dias.
[PÁGINA 9]
22/08/2026 - SISBAJUD
Resultado POSITIVO; bloqueio de R$ 3.800,00 da reclamada fictícia.
[PÁGINA 10]
28/09/2026 - REMESSA AO CEJUSC
Processo encaminhado para tentativa de conciliação.
'''

def test_analise_conjunta_sem_escolha_de_fase():
    r=analisar_texto_integrado(TEXTO,CNJ)
    assert r['status']=='analise_preliminar'
    assert r['avaliadas_fases']==['LIQUIDAÇÃO','EXECUÇÃO']
    assert r['fase_identificada']=='EXECUÇÃO',r['fundamento_fase']
    assert r['pagina_inicial']==2
    assert all(e['pagina_pdf']>=2 for e in r['eventos'])
    assert any(e['categoria']=='recurso_ordinario' for e in r['eventos'])
    assert any(e['categoria']=='deposito_recursal' for e in r['eventos'])
    assert any(e['categoria']=='custas' for e in r['eventos'])
    assert any(e['categoria']=='calculos' for e in r['eventos'])
    assert any(e['categoria']=='sisbajud' for e in r['eventos'])
    assert '13.813,83' in r['pauta_markdown']
    assert '28/09/2026' in r['pauta_markdown']
    assert 'DISTRIBUIÇÃO' not in r['pauta_markdown']
    dates=[e['data'] for e in r['eventos']]
    assert dates==sorted(dates,key=lambda x: (x[6:],x[3:5],x[:2]))


def test_so_liquidacao_ainda_analisa_execucao():
    r=analisar_texto_integrado(TEXTO.split('[PÁGINA 8]')[0],CNJ)
    assert r['fase_identificada']=='LIQUIDAÇÃO'
    assert r['avaliadas_fases']==['LIQUIDAÇÃO','EXECUÇÃO']


def test_pdf_unico_sem_parametro_fase(tmp_path):
    p=tmp_path/'ficticio.pdf'
    doc=fitz.open()
    for page in TEXTO.split('[PÁGINA ')[1:]:
        content=page.split(']',1)[1].strip()
        pg=doc.new_page()
        # Insert lines short enough to fit PDF text block.
        pg.insert_textbox((40,40,560,780),content,fontsize=10)
    doc.save(p);doc.close()
    c=TestClient(api.app)
    with p.open('rb') as stream:
        resp=c.post('/api/v2/analisar/pdf',files={'arquivo':('ficticio.pdf',stream,'application/pdf')},data={'numero_cnj':CNJ})
    assert resp.status_code==200,resp.text
    result=resp.json()
    assert result['fase_identificada']=='EXECUÇÃO'
    assert 'p. PDF 9' in result['pauta_markdown']


def test_gradio_uma_funcao():
    c=TestClient(api.app)
    info=c.get('/chatjt/gradio_api/info')
    assert info.status_code==200
    assert set(info.json()['named_endpoints'])=={'/analisar_processo'}
    config=c.get('/chatjt/config').json()
    assert not any(x.get('label')=='Fase' for x in config['components'])
    assert any(x.get('type')=='file' for x in config['components'])


def test_autenticacao_persistente(monkeypatch):
    from chatjt_adapter import _autorizar
    class Request:
        def __init__(self,headers):self.headers=headers
    monkeypatch.setenv('CEJUSC_API_KEY','CHAVE_APENAS_TESTE')
    with pytest.raises(gr.Error):_autorizar(Request({}))
    _autorizar(Request({'x-api-key':'CHAVE_APENAS_TESTE'}))
    with pytest.raises(gr.Error):_autorizar(Request({'x-ip-token':'TOKEN_CODIFICADO_NAO_VALIDADO'}))