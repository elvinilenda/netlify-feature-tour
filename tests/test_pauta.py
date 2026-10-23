from fastapi.testclient import TestClient
import api
import pytest

client = TestClient(api.app)

def test_capacidades():
    r=client.get('/api/v1/capacidades')
    assert r.status_code == 200
    assert 'Sem OCR automático' in r.json()['limites']

def test_eventos_individualizados():
    payload = {
      'numero_cnj':'0011087-25.2017.5.15.0127', 'fase':'liquidacao',
      'vara':'1ª Vara do Trabalho de Presidente Prudente',
      'polo_ativo':'TESTE A', 'polo_passivo':'TESTE B',
      'eventos':[
        {'data':'31/08/2018','ato':'DEPOSITO RECURSAL','descricao':'Recolhido R$ 8.000,00 por teste', 'pagina_pdf':175},
        {'data':'17/05/2018','ato':'SENTENÇA','descricao':'Julgados parcialmente procedentes os pedidos','pagina_pdf':147},
        {'data':'31/08/2018','ato':'CUSTAS PROCESSUAIS','descricao':'Recolhidas R$ 400,00','id_pje':'abc1234'},
      ]
    }
    r=client.post('/api/v1/pautas/formatar',json=payload)
    assert r.status_code == 200, r.text
    s=r.json()['pauta_markdown']
    assert s.index('SENTENÇA') < s.index('DEPOSITO RECURSAL') < s.index('CUSTAS PROCESSUAIS')
    assert 'p. PDF 175' in s and 'ID PJe abc1234' in s
    assert '**R$ 8.000,00**' in s
    assert len(r.json()['pendencias'])==3

def test_pauta_exige_fonte():
    r=client.post('/api/v1/pautas/formatar',json={
      'numero_cnj':'0011087-25.2017.5.15.0127', 'fase':'execucao',
      'vara':'Vara do Trabalho','polo_ativo':'AUTOR','polo_passivo':'REU',
      'eventos':[{'data':'10/10/2026','ato':'PENHORA','descricao':'Pretensa penhora de R$ 200,00'}]
    })
    assert r.status_code==422

def test_prioridade_grupos():
    data=api._indice_prioritario({'ocorrencias':[{'categoria':'deposito_recursal'},{'categoria':'custas'},{'categoria':'recurso_ordinario'},{'categoria':'penhoras'}]})
    assert len(data['depositos_recursais_e_custas'])==2
    assert len(data['recursos_e_acordaos'])==1
    assert len(data['execucao_e_patrimonio'])==1