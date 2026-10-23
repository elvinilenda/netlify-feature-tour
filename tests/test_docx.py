from pathlib import Path
import sys,io
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from docx import Document
import fitz,api

def test_exportar_docx_com_prints(tmp_path):
    d=fitz.open()
    d.new_page().insert_text((45,60),'SENTENÇA\nAnte o exposto julgo procedentes os pedidos.',fontsize=12)
    d.new_page().insert_text((45,60),'30/03/2026 - ACÓRDÃO TRT-15\nReformou parcialmente a condenação em R$ 5.000,00.',fontsize=12)
    p=tmp_path/'test_process.pdf';d.save(p);d.close()
    c=TestClient(api.app)
    with p.open('rb') as f:
        resp=c.post('/api/v2/analisar/pdf/docx',files={'arquivo':('test_process.pdf',f,'application/pdf')})
    assert resp.status_code==200,resp.text[:300] if resp.status_code!=200 else ''
    word=Document(io.BytesIO(resp.content))
    texto='\n'.join(p.text for p in word.paragraphs)
    assert 'SENTENÇA' in texto
    assert 'ACÓRDÃO' in texto
    assert 'ANÁLISE PRELIMINAR' in texto
    assert len(word.inline_shapes)>=1