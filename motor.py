"""Motor de triagem documental trabalhista: extração de evidências, não parecer jurídico.

Sem chamadas à internet, modelos externos, bases de dados ou persistência dos PDFs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import unicodedata
from typing import Iterable

MAX_PAGES = 1500
MAX_BYTES = 70 * 1024 * 1024
MAX_TEXT_CHARS = 8_000_000
MAX_EVENTS = 2000


def normalizar(s: str) -> str:
    """Remove apenas acentos para comparar; preserva texto original nos resultados."""
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).lower()


@dataclass
class Pagina:
    numero: int
    texto: str


@dataclass
class Ocorrencia:
    categoria: str
    detalhe: str
    pagina: int
    trecho: str
    data_no_trecho: str
    valores_mencionados: list[str]
    ids_mencionados: list[str]
    evidencia: str  # ocorrência textual; não confirmação automática do ato


# Uma categoria é um índice de busca de texto, não uma declaração de fato ocorrido.
PADROES = {
    "sentenca": ("Sentença / dispositivo", [r'\bsenten[cç]a\b', r'\bante o exposto\b', r'\bjulgo\b']),
    "pericia": ("Perícia e honorários periciais", [r'\bper[ií]ci[ao]\b', r'\bhonor[aá]rios periciais\b', r'\bsucumbente na per[ií]cia\b']),
    "honorarios_sucumbenciais": ("Honorários de sucumbência e reciprocidade", [r'\bhonor[aá]rios (?:advocat[ií]cios|sucumbenciais|de sucumb[eê]ncia)\b', r'\bsucumb[eê]ncia rec[ií]proca\b']),
    "custas": ("Custas processuais e recolhimentos", [r'\bcustas (?:processuais|judiciais|recursais)\b', r'\brecolhimento de custas\b', r'\bGRU\b']),
    "embargos_declaracao": ("Embargos de declaração (ED)", [r'\bembargos? de declara[cç][aã]o\b', r'\bED\b.{0,30}\b(?:interpost|acolhid|rejeitad|julgad)']),
    "recurso_ordinario": ("Recurso ordinário (RO)", [r'\brecurso ordin[aá]rio\b', r'\binterposi[cç][aã]o do RO\b']),
    "recurso_revista": ("Recurso de revista (RR)", [r'\brecurso de revista\b', r'\binterposi[cç][aã]o do RR\b']),
    "agravo_instrumento": ("Agravo de instrumento / AIRR", [r'\bagravo de instrumento\b', r'\bAIRR\b']),
    "agravo_peticao": ("Agravo de petição", [r'\bagravo de peti[cç][aã]o\b']),
    "outros_recursos": ("Outros recursos e embargos", [r'\brecurso adesivo\b', r'\bembargos [aà] execu[cç][aã]o\b', r'\bexce[cç][aã]o de pr[eé]-executividade\b']),
    "acordao": ("Acórdãos e resultados recursais", [r'\bac[oó]rd[aã]o\b', r'\bnegar provimento\b', r'\bdar provimento\b', r'\bprovido parcialmente\b', r'\breform(?:o|ada) a senten[cç]a\b']),
    "transito": ("Trânsito em julgado", [r'tr[aâ]nsito em julgado', r'\bcertid[aã]o de tr[aâ]nsito\b']),
    "deposito_recursal": ("DEPÓSITOS RECURSAIS — GARANTIAS", [r'\bdep[oó]sito recursal\b', r'\bcomprovante.*dep[oó]sito recursal\b']),
    "seguro_garantia": ("SEGURO-GARANTIA / FIANÇA — GARANTIAS", [r'seguro[ -]garantia', r'\bfian[cç]a banc[aá]ria\b', r'\bap[oó]lice\b']),
    "deposito_judicial": ("DEPÓSITOS JUDICIAIS — VERIFICAR FINALIDADE", [r'\bdep[oó]sito judicial\b', r'\bdep[oó]sito em conta judicial\b']),
    "calculos": ("Cálculos de liquidação / atualização", [r'\bc[aá]lculos? de liquida[cç][aã]o\b', r'\bplanilha de c[aá]lculos\b', r'\bapresent(?:e|em|ados) os c[aá]lculos\b', r'\bplanilha atualizada\b']),
    "impugnacao": ("Impugnações aos cálculos e esclarecimentos", [r'\bimpugna[cç][aã]o (?:aos|dos|de) c[aá]lculos\b', r'\bimpugna[cç][aã]o [aà] senten[cç]a de liquida[cç][aã]o\b', r'\bper[ií]cia cont[aá]bil\b']),
    "homologacao": ("Homologação dos cálculos / decisão líquida", [r'\bhomolog(?:o|ados|ada|a[cç][aã]o)\b.{0,60}\bc[aá]lculos?\b', r'\bsenten[cç]a de liquida[cç][aã]o\b', r'\bvalor l[ií]quido\b']),
    "acordo": ("Acordos e descumprimento", [r'\bacordo (?:homologado|celebrado|judicial)\b', r'\bdescumprimento (?:do|de) acordo\b', r'\bparcelas? do acordo\b']),
    "parcelamento": ("Parcelamento / art. 916 do CPC", [r'\bparcelamento\b', r'art(?:igo|\.)?\s*916\b']),
    "pagamento": ("PAGAMENTOS — CONFERIR EFETIVA QUITAÇÃO", [r'\bcomprovante de pagamento\b', r'\bpagamento realizado\b', r'\bquitação\b', r'\bvalor pago\b', r'\btransfer[eê]ncia ao exequente\b']),
    "sisbajud": ("SISBAJUD / BACENJUD / teimosinha", [r'\bSISBAJUD\b', r'\bBACENJUD\b', r'\bteimosinha\b', r'\bbloqueio de (?:ativos|valores|contas)\b']),
    "bloqueios": ("Bloqueios / desbloqueios / transferência de valores", [r'\bbloqueio (?:positivo|negativo|parcial)\b', r'\bdesbloqueio\b', r'\btransfer[eê]ncia de valores bloqueados\b', r'\bconvers[aã]o em penhora\b']),
    "renajud": ("RENAJUD / veículos", [r'\bRENAJUD\b', r'\brestri[cç][aã]o de ve[ií]culo\b']),
    "imoveis": ("ARISP / imóveis / indisponibilidade", [r'\bARISP\b', r'\bCNIB\b', r'\bindisponibilidade de bens\b', r'\bregistro de im[oó]veis\b']),
    "penhoras": ("Penhoras, avaliações e leilões", [r'\bpenhora\b', r'\bauto de penhora\b', r'\bavalia[cç][aã]o do bem\b', r'\bleil[aã]o\b', r'\bhasta p[uú]blica\b', r'\badjudica[cç][aã]o\b']),
    "mandados": ("Mandados e resultados de diligências", [r'\bmandado (?:de|expedido|cumprido)\b', r'\bcertid[aã]o do oficial de justi[cç]a\b', r'\bmandado devolvido\b']),
    "idpj": ("IDPJ / sócios / redirecionamento", [r'\bIDPJ\b', r'\bincidente de desconsidera[cç][aã]o\b', r'\bredirecionamento da execu[cç][aã]o\b', r'\binclus[aã]o (?:dos|de) s[oó]cios\b']),
    "alvaras": ("ALVARÁS E LEVANTAMENTOS — SAÍDA DE VALORES", [r'\balvar[aá]\b', r'\blevantamento de valores\b', r'\bexpedi[cç][aã]o de alvar[aá]\b', r'\bsaque judicial\b']),
    "audiencia": ("Audiência / conciliação / CEJUSC", [r'\bdesign(?:o|ada|ada a) audi[eê]ncia\b', r'\baudi[eê]ncia de concilia[cç][aã]o\b', r'\bCEJUSC\b', r'\bremessa.*concilia[cç][aã]o\b']),
    "ultimo_despacho": ("Despachos, decisões e intimações", [r'\bdespacho\b', r'\bintimem-se\b', r'\bdetermino\b', r'\bdefiro\b', r'\bindefiro\b']),
}
PAT = {key: [re.compile(p, re.IGNORECASE) for p in arr] for key, (_, arr) in PADROES.items()}
DATE = re.compile(r'(?<!\d)(?:[0-3]?\d[/.-][01]?\d[/.-](?:19|20)\d{2})(?!\d)')
MONEY = re.compile(r'R\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?|R\$\s*\d+(?:,\d{2})?', re.IGNORECASE)
DOCID = re.compile(r'\b(?:ID|Id|id)[:\s#-]*([a-f\d]{6,12})\b')


def _cleanup(texto: str, max_chars: int=500) -> str:
    return re.sub(r'\s+', ' ', texto).strip()[:max_chars]


def paginas_de_texto(texto: str) -> list[Pagina]:
    """Aceita quebras de página (\f) ou marcações [PÁGINA 1]."""
    if not texto or not texto.strip():
        raise ValueError('Não foi enviado texto processual.')
    if len(texto) > MAX_TEXT_CHARS:
        raise ValueError('Texto grande demais para a versão inicial. Divida por intervalos de páginas.')
    if '\f' in texto:
        return [Pagina(i, t) for i, t in enumerate(texto.split('\f'), 1)]
    m = list(re.finditer(r'^\s*\[\s*p[aá]gina\s+(\d+)\s*\]\s*$', texto, re.I | re.M))
    if m:
        out = []
        for i, hit in enumerate(m):
            end = m[i+1].start() if i+1 < len(m) else len(texto)
            out.append(Pagina(int(hit.group(1)), texto[hit.end():end]))
        return out
    return [Pagina(1, texto)]


def paginas_de_pdf(caminho: str) -> list[Pagina]:
    """Extrai camada textual existente; não executa OCR nem envia dados a terceiros."""
    import fitz
    p = Path(caminho)
    if not p.is_file():
        raise ValueError('PDF não encontrado.')
    if p.suffix.lower() != '.pdf' or p.stat().st_size > MAX_BYTES:
        raise ValueError('Use PDF com até 70 MB nesta versão.')
    try:
        with fitz.open(p) as doc:
            if doc.page_count > MAX_PAGES:
                raise ValueError(f'Este PDF tem mais de {MAX_PAGES} páginas; divida-o por volumes.')
            pages = [Pagina(i + 1, page.get_text(sort=True) or '') for i, page in enumerate(doc)]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('Não foi possível ler o PDF (pode estar protegido ou corrompido).') from exc
    if not any(p.texto.strip() for p in pages):
        raise ValueError('O PDF não possui camada de texto reconhecível. Precisa de OCR autorizado antes da análise.')
    return pages


def _inicio_sentenca(paginas: list[Pagina], indicacao: int) -> tuple[int | None, str]:
    if indicacao > 0:
        for i, pag in enumerate(paginas):
            if pag.numero == indicacao:
                return i, 'Página da sentença informada manualmente; conferir se corresponde à sentença correta.'
        return None, f'A página {indicacao} não está presente no documento fornecido.'
    for i, pag in enumerate(paginas):
        text = normalizar(pag.texto)
        near = normalizar(' '.join(x.texto for x in paginas[i:min(i+2, len(paginas))]))
        titulo = bool(re.search(r'(?m)^\s*(?:poder judiciario.*\n)?\s*sentenca(?:\s*\n|\s*[-–:]\s*)', text))
        dispositivo = bool(re.search(r'\b(?:julgo|condeno|dispositivo|ante o exposto)\b', near))
        # Um sumário que apenas lista 'SENTENÇA' não basta para localizar o marco.
        if titulo and dispositivo:
            return i, 'Início detectado por título SENTENÇA e termos decisórios; validar a página indicada.'
    for i,p in enumerate(paginas):
        txt = normalizar(p.texto)
        if re.search(r'\bante o exposto.{0,180}\bjulgo\b', txt, re.S) and 'juiz' in txt:
            return i, 'Início presumido pelo dispositivo; conferir se a sentença começa em página anterior.'
    return None, 'Não foi possível identificar com segurança a primeira página da sentença. Informe-a manualmente.'


def _qualidade_de_evidencia(snippet: str) -> str:
    x = normalizar(snippet)
    if re.search(r'\b(?:foi interposto|interp[oô]s|interpos|foi realizado|comprovante|homologo|homologados|foi expedido|certifico|julgou|deferiu|determino|bloqueado|transferido|quitado|foi pago|expedido)\b', x):
        return 'indício de ato no texto — validar documento e resultado'
    return 'menção encontrada — não confirma realização do ato'


def _buscar(paginas: Iterable[Pagina]) -> list[Ocorrencia]:
    out: list[Ocorrencia] = []
    for pag in paginas:
        linhas = [l.strip() for l in pag.texto.splitlines() if l.strip()]
        # Uma ocorrência por categoria/janela/linha. Detecta várias movimentações na mesma página.
        vistos: set[tuple[str,int]] = set()
        for j, linha in enumerate(linhas):
            for categoria, pats in PAT.items():
                if not any(p.search(linha) for p in pats):
                    continue
                # Evita diversas duplicações da mesma categoria em linhas vizinhas.
                item = (categoria, j//3)
                if item in vistos:
                    continue
                vistos.add(item)
                antes = max(0, j-1)
                depois = min(len(linhas), j+3)
                janela = ' '.join(linhas[antes:depois])
                out.append(Ocorrencia(
                    categoria=categoria, detalhe=PADROES[categoria][0], pagina=pag.numero,
                    trecho=_cleanup(janela), data_no_trecho=(DATE.search(janela).group(0) if DATE.search(janela) else 'não localizada'),
                    valores_mencionados=list(dict.fromkeys(MONEY.findall(janela)))[:6],
                    ids_mencionados=list(dict.fromkeys(DOCID.findall(janela)))[:6],
                    evidencia=_qualidade_de_evidencia(janela),
                ))
                if len(out) >= MAX_EVENTS:
                    return out
    return out


SECOES_COMUNS = [
    ("Sentença e condenações", ["sentenca","pericia","honorarios_sucumbenciais","custas"]),
    ("RECURSOS — interposição, julgamento e reforma", ["embargos_declaracao","recurso_ordinario","recurso_revista","agravo_instrumento","agravo_peticao","outros_recursos","acordao","transito"]),
    ("MOVIMENTAÇÕES FINANCEIRAS — distinguir garantia de pagamento", ["deposito_recursal","seguro_garantia","deposito_judicial","custas","pagamento","alvaras"]),
]
SECOES_LIQ = [
    ("Liquidação — cálculos, homologação e impugnações", ["calculos","impugnacao","homologacao","pericia","parcelamento","acordo"]),
    ("Fatos posteriores e motivo da audiência", ["audiencia","ultimo_despacho"]),
]
SECOES_EXEC = [
    ("Execução — título, cálculos e acordos", ["homologacao","acordo","calculos","impugnacao","parcelamento"]),
    ("ATOS EXECUTIVOS — buscas, bloqueios e constrições", ["sisbajud","bloqueios","renajud","imoveis","penhoras","mandados","idpj"]),
    ("Últimos atos e motivo da audiência", ["audiencia","ultimo_despacho"]),
]

OBRIGATORIOS = {
    'liquidacao': [
        ('Data e teor do dispositivo da sentença', 'sentenca'),
        ('Perícia, sucumbente e honorários periciais', 'pericia'),
        ('Honorários advocatícios e sucumbência recíproca', 'honorarios_sucumbenciais'),
        ('Custas fixadas / preparo de recursos', 'custas'),
        ('ED, RO, RR, AIRR e resultados', 'acordao'),
        ('Depósitos recursais, seguro-garantia e destinação', 'deposito_recursal'),
        ('Trânsito em julgado (data)', 'transito'),
        ('Despacho para apresentação dos cálculos', 'calculos'),
        ('Cálculos, impugnações e valor líquido atualizado', 'impugnacao'),
        ('Homologação dos cálculos ou acordo', 'homologacao'),
        ('Parcelamento, pagamentos e alvarás', 'pagamento'),
        ('Último despacho e razão da audiência', 'audiencia'),
    ],
    'execucao': [
        ('Título: homologação ou acordo e data', 'homologacao'),
        ('Valor líquido e planilha atualizada', 'calculos'),
        ('SISBAJUD/BACENJUD: resultado positivo/negativo e valores', 'sisbajud'),
        ('Mandado: ID/folha, destinatário, diligência e resultado', 'mandados'),
        ('RENAJUD e veículos', 'renajud'),
        ('ARISP, CNIB e indisponibilidade de imóveis', 'imoveis'),
        ('Penhora, avaliação e leilão / adjudicação', 'penhoras'),
        ('IDPJ, sócios e redirecionamento', 'idpj'),
        ('Depósitos: recursais, judiciais e bloqueios', 'deposito_judicial'),
        ('Levantamentos, pagamentos e beneficiários', 'alvaras'),
        ('Acordos, inadimplemento e parcelamento', 'acordo'),
        ('Último despacho e razão concreta da audiência', 'audiencia'),
    ],
}


def analisar_paginas(paginas: list[Pagina], fase: str='liquidacao', pagina_sentenca: int=0) -> dict:
    fase_cod = normalizar(fase)
    fase_cod = 'execucao' if fase_cod.startswith('execu') else 'liquidacao'
    if not paginas:
        raise ValueError('Nenhuma página enviada.')
    i, explicacao = _inicio_sentenca(paginas, pagina_sentenca)
    if i is None:
        return {
            'status': 'revisar_marco_da_sentenca', 'fase': fase_cod, 'paginas_totais': len(paginas),
            'pagina_inicial': None, 'pagina_final': paginas[-1].numero, 'criterio_corte': explicacao,
            'ocorrencias': [], 'contagens': {}, 'campos_obrigatorios': [],
            'limites': ['Nenhuma página anterior à sentença foi incluída. A análise não prosseguiu sem um marco verificável.']
        }
    trecho = paginas[i:]
    achados = _buscar(trecho)
    counts = {k: sum(o.categoria == k for o in achados) for k in PADROES}
    campos = [{
        'campo':nome, 'categoria_rastreada':categoria,
        'status':'Há menções para conferir' if counts.get(categoria,0) else 'Não localizado no trecho analisado',
    } for nome,categoria in OBRIGATORIOS[fase_cod]]
    avisos = [
        'A ordem é a sequência de páginas do PDF, que pode diferir da ordem cronológica dos atos.',
        'Data, valores e IDs próximos são pistas textuais, não vinculação jurídica confirmada ao ato.',
        'Depósito recursal, depósito judicial, seguro-garantia e bloqueio NÃO significam pagamento ao credor.',
        'Não houve cálculo de saldo, conferência de recolhimentos, leitura de documentos digitalizados sem OCR nem consulta ao PJe.',
        'Não localizado não equivale a inexistente; conferir peças completas e o último ato processual.',
    ]
    if any(not p.texto.strip() for p in trecho):
        avisos.append('Existem páginas sem texto pesquisável. A análise dessas páginas depende de OCR autorizado.')
    if len(achados) >= MAX_EVENTS:
        avisos.append('Limite de ocorrências alcançado: extração potencialmente incompleta.')
    return {
        'status':'triagem_concluida', 'fase':fase_cod, 'paginas_totais':len(paginas),
        'pagina_inicial':trecho[0].numero, 'pagina_final':trecho[-1].numero,
        'criterio_corte':explicacao, 'ocorrencias':[asdict(o) for o in achados],
        'contagens':counts, 'campos_obrigatorios':campos, 'limites':avisos,
    }


def analisar_texto(texto: str, fase: str='liquidacao', pagina_sentenca: int=0) -> dict:
    return analisar_paginas(paginas_de_texto(texto), fase, pagina_sentenca)


def analisar_pdf(caminho: str, fase: str='liquidacao', pagina_sentenca: int=0) -> dict:
    return analisar_paginas(paginas_de_pdf(caminho), fase, pagina_sentenca)


def _esc(s: str) -> str:
    return str(s).replace('|','\\|').replace('\n',' ')


def relatorio(resultado: dict) -> str:
    """Relatório Markdown auditável, com destaque para recursos e movimentações financeiras."""
    fase = resultado.get('fase', 'liquidacao')
    nome = 'LIQUIDAÇÃO — FAIXA VERDE' if fase == 'liquidacao' else 'EXECUÇÃO — FAIXA CINZA'
    linhas = [f'# AUDITORIA DOCUMENTAL — {nome}',
              '> TRIAGEM AUTOMÁTICA: as menções exigem confronto com a decisão, comprovantes e movimentações oficiais.',
              f"**Páginas examinadas:** {resultado.get('pagina_inicial') or 'não definida'} a {resultado.get('pagina_final')}; **páginas do arquivo:** {resultado.get('paginas_totais')}",
              f"**Marco de corte:** {resultado.get('criterio_corte', '')}", '']
    if resultado.get('status') != 'triagem_concluida':
        linhas += ['## AÇÃO NECESSÁRIA', '**Não foi possível identificar a sentença de modo seguro.** Informe o número da página da sentença. Não foram analisadas páginas anteriores.', '']
        return '\n'.join(linhas)
    linhas.append('## CHECKLIST DE ELEMENTOS OBRIGATÓRIOS')
    for item in resultado['campos_obrigatorios']:
        linhas.append(f"- **{item['campo']}:** {item['status']}")
    linhas.append('')
    seccoes = SECOES_COMUNS + (SECOES_LIQ if fase=='liquidacao' else SECOES_EXEC)
    for titulo, tipos in seccoes:
        linhas.append(f'## {titulo}')
        for kind in tipos:
            items = [o for o in resultado['ocorrencias'] if o['categoria'] == kind]
            if not items:
                linhas.append(f"**{PADROES[kind][0]}:** não localizado no trecho analisado.")
                continue
            linhas.append(f"**{PADROES[kind][0]} — {len(items)} ocorrência(s) textual(is)**")
            for item in items[:12]:
                valores = ', '.join(item['valores_mencionados']) or 'sem valor identificado'
                ids = ', '.join(item['ids_mencionados']) or 'sem ID localizado'
                linhas.append(f"- **p. {item['pagina']}** | data próxima: {item['data_no_trecho']} | valores mencionados: {_esc(valores)} | ID(s): {_esc(ids)} | {item['evidencia']}. **Trecho:** “{_esc(item['trecho'][:330])}”")
            if len(items)>12:
                linhas.append(f"- **Mais {len(items)-12} ocorrências** no JSON de auditoria; revisar todas.")
        linhas.append('')
    linhas += ['## ÚLTIMAS OCORRÊNCIAS DOCUMENTAIS (NÃO NECESSARIAMENTE ÚLTIMO DESPACHO)']
    for item in resultado['ocorrencias'][-8:]:
        linhas.append(f"- p. {item['pagina']} — {item['detalhe']}: {_esc(item['trecho'][:200])}")
    if not resultado['ocorrencias']:
        linhas.append('Nenhuma ocorrência de categorias rastreadas foi identificada após a sentença.')
    linhas += ['', '## LIMITAÇÕES E CONFERÊNCIAS OBRIGATÓRIAS']
    linhas.extend(f'- {x}' for x in resultado['limites'])
    linhas.append('**Motivo concreto da audiência / valor efetivamente disponível ao reclamante:** somente afirmar após exame da decisão e dos comprovantes correspondentes.')
    return '\n'.join(linhas)