"""Extração conjunta e cronologia preliminar CEJUSC, SEM inferir decisões jurídicas.

Uma só leitura desde a sentença. Mantém evidência documental e pendências visíveis;
ambos os conjuntos de critérios (liquidação e execução) são avaliados em paralelo.
Não há inferência sem fonte do resultado de recurso, valor pago ou penhora efetiva.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from collections import defaultdict
import re
from typing import Iterable

from motor import Pagina, paginas_de_pdf, paginas_de_texto, _inicio_sentenca, _buscar, PADROES, normalizar, MONEY, DOCID

DATA_INICIO = re.compile(r'^\s*(?P<data>[0-3]?\d[/.-][01]?\d[/.-](?:19|20)\d{2})\s*[-–—:]\s*(?P<titulo>[^\n]{3,180})\s*$', re.I)
# Não basta uma data encontrada em parágrafo para datar um ato.
DATA_DOCUMENTO = re.compile(r'^\s*(?:Juntado|Assinado|Publicado|Proferido)\s+em\s*:\s*(?P<data>[0-3]?\d[/.-][01]?\d[/.-](?:19|20)\d{2})(?:\s|$)',re.I)
CNJ = re.compile(r'\b\d{7}-\d{2}\.\d{4}\.5\.\d{2}\.\d{4}\b')
IMPORTANTES = {'sentenca','embargos_declaracao','recurso_ordinario','recurso_revista','agravo_instrumento','agravo_peticao','outros_recursos','acordao','deposito_recursal','seguro_garantia','custas','transito','calculos','impugnacao','homologacao','pericia','parcelamento','acordo','pagamento','sisbajud','bloqueios','renajud','imoveis','penhoras','mandados','idpj','alvaras','deposito_judicial','audiencia','ultimo_despacho'}
# A classificação usa primeiro o TÍTULO do ato, depois o corpo se for genérico.
LABELS = [
 ('sentenca',r'\bsenten[cç]a\b'),
 ('embargos_declaracao',r'embargos? de declara[cç][aã]o'),
 ('recurso_ordinario',r'recurso ordin[aá]rio'),
 ('recurso_revista',r'recurso de revista'),
 ('agravo_instrumento',r'agravo de instrumento|\bAIRR\b'),
 ('agravo_peticao',r'agravo de peti[cç][aã]o'),
 ('acordao',r'\bac[oó]rd[aã]o\b'),
 ('transito',r'tr[aâ]nsito em julgado'),
 ('deposito_recursal',r'dep[oó]sito recursal'),
 ('seguro_garantia',r'seguro[ -]garantia|ap[oó]lice'),
 ('custas',r'custas processuais|recolhimento de custas|\bGRU\b'),
 ('homologacao',r'homologa[cç][aã]o dos c[aá]lculos|decis[aã]o de liquida[cç][aã]o|liquida[cç][aã]o definitiva'),
 ('calculos',r'\bc[aá]lculos\b|laudo pericial cont[aá]bil|planilha de atualiza[cç][aã]o|atualiza[cç][aã]o do d[eé]bito'),
 ('impugnacao',r'impugna[cç][aã]o|esclarecimentos periciais'),
 ('parcelamento',r'parcelamento|art(?:igo|\.)?\s*916'),
 ('acordo',r'\bacordo\b|concilia[cç][aã]o'),
 ('sisbajud',r'SISBAJUD|BACENJUD|bloqueio de ativos'),
 ('renajud',r'RENAJUD'),
 ('imoveis',r'\bCNIB\b|indisponibilidade'),
 ('mandados',r'mandado execut[oó]rio|mandado de penhora|certid[aã]o do oficial'),
 ('idpj',r'\bIDPJ\b|desconsidera[cç][aã]o da personalidade'),
 ('alvaras',r'alvar[aá]|guia de retirada|levantamento'),
 ('deposito_judicial',r'dep[oó]sito judicial|guia de dep[oó]sito'),
 ('penhoras',r'penhora|hasta p[uú]blica|leil[aã]o'),
 ('pagamento',r'pagamento|quita[cç][aã]o'),
 ('audiencia',r'audi[eê]ncia|remessa ao CEJUSC'),
 ('ultimo_despacho',r'despacho|decis[aã]o'),
]
COMP = [(k,re.compile(p,re.I)) for k,p in LABELS]
RECURSOS={'embargos_declaracao','recurso_ordinario','recurso_revista','agravo_instrumento','agravo_peticao','acordao','transito'}
EXECUCAO_FORTE={'sisbajud','renajud','imoveis','penhoras','mandados','idpj','alvaras'}
LIQUIDACAO={'calculos','impugnacao','homologacao','pericia'}
# A mera palavra "pagamento" não determina execução; precisa contexto real.
EXECUCAO_INICIO=re.compile(r'\b(?:in[ií]cio da execu[cç][aã]o|determina[cç][aã]o de pagamento|intima[cç][aã]o para pagar|garantir a execu[cç][aã]o|execu[cç][aã]o iniciada)\b', re.I)
CONDENACAO=re.compile(r'\b(?:reintegra[cç][aã]o|condena(?:r|[cç][aã]o)|responsabilidade|honor[aá]rios|sucumb[eê]ncia|deferid[oa]s?|improcedentes?|danos morais|FGTS|custas|horas extras|\bR\$)\b',re.I)

@dataclass
class Evento:
    data: str
    ato: str
    categoria: str
    descricao: str
    pagina_pdf: int
    valores: list[str]
    ids: list[str]
    forca_documental: str = 'título de evento no texto; conferir peça original'
    ordem_no_arquivo: int = 0


def _ordem_evento(e: Evento):
    try:dt=datetime.strptime(e.data,'%d/%m/%Y')
    except ValueError:dt=datetime.min
    return (dt,e.ordem_no_arquivo)


def _data(dt: str) -> str | None:
    try:
        return datetime.strptime(dt.replace('.','/').replace('-','/'),'%d/%m/%Y').strftime('%d/%m/%Y')
    except ValueError:
        return None


def _categoria(titulo: str, corpo: str='') -> str | None:
    for tipo, pat in COMP:
        if tipo=='sentenca':
            if re.search(r'^\s*senten[cç]a\b', titulo, re.I):return tipo
            continue
        if pat.search(titulo):
            return tipo
    # Só para títulos vagos, se houver frase decisória inequívoca.
    if re.search(r'\b(?:decis[aã]o|juntada|manifesta[cç][aã]o)\b',titulo,re.I):
        for tipo, pat in COMP:
            if tipo not in ('sentenca','ultimo_despacho','audiencia') and pat.search(corpo[:250]):return tipo
    return None


def _sumario(titulo: str, corpo: str, categoria: str) -> str:
    """Trechos literais essenciais por tipo, sem fabricar interpretações."""
    conteudo = re.sub(r'\s+', ' ', corpo).strip().replace('**','')
    if not conteudo:
        return 'Ato datado localizado; conteúdo não identificado na camada textual.'
    limite={'sentenca':2400,'acordao':1650,'homologacao':1100,'calculos':1100}.get(categoria,850)
    if len(conteudo)<=limite:
        return conteudo
    # Primeiro trecho + sentenças com pontos obrigatórios de cada fase; preserva redação original.
    pedacos=re.split(r'(?<=[.!?;])\s+',conteudo)
    peso=re.compile(r'custas|honor[aá]rios|per[ií]cia|sucumb[eê]ncia|solid[aá]ri|subsidi[aá]ri|deposit|dep[oó]sito|garantia|alvar[aá]|multa|R\$|reform|provido|rejeitad|FGTS|bloque|liquido|l[ií]quido|parcela|saldo|condena|procedente|penhora|per[ií]od|retifica|SISBAJUD|RENAJUD|CNIB|acordo',re.I)
    selecionados=[];tamanho=0
    for j,t in enumerate(pedacos):
        t=t.strip()
        if not t:continue
        if j<2 or peso.search(t):
            if t in selecionados:continue
            if tamanho+len(t)>limite-30:break
            selecionados.append(t);tamanho+=len(t)+1
    resumo=' '.join(selecionados)
    if not resumo:resumo=conteudo[:limite-30]
    return resumo.rstrip()+' […]'


def _documentos(paginas: list[Pagina]):
    """Lê cabeçalhos datados e respectivo texto nas páginas seguintes.

    NÃO deduz a data de um ato com base em outra data próxima do PDF.
    """
    tokens=[]
    for p in paginas:
        tokens.extend((p.numero, linha.strip()) for linha in p.texto.splitlines() if linha.strip())
    marcas=[]
    for ix,(pag,linha) in enumerate(tokens):
        m=DATA_INICIO.match(linha)
        if m:
            cat=_categoria(m.group('titulo'))
            if cat:marcas.append((ix,pag,m.group('data'),m.group('titulo'),cat))
    eventos=[];pendencias=[];contador=0
    for idx,(inicio,pag,bruta,titulo,cat) in enumerate(marcas):
        fim=marcas[idx+1][0] if idx+1<len(marcas) else len(tokens)
        # Para evitar incorporar capítulos inteiros sem limites de documento.
        janela=[];lim=0
        for _,linha in tokens[inicio+1:fim]:
            janela.append(linha);lim+=len(linha)+1
            if lim>=15000:break
        texto=' '.join(janela)
        data=_data(bruta)
        if not data:
            pendencias.append(f'Data inválida na p. {pag}: {bruta}')
            continue
        contador+=1
        eventos.append(Evento(data,titulo.strip(' :-–'),cat,_sumario(titulo,texto,cat),pag,
                              list(dict.fromkeys(MONEY.findall(texto)))[:16],
                              list(dict.fromkeys(DOCID.findall(texto)))[:8],ordem_no_arquivo=contador))
        if cat in {'recurso_ordinario','recurso_revista','agravo_instrumento'}:
            # Destaca preparo referido pelo ato. Nunca afirma pagamento ou data efetiva sem guia.
            for tipo,rotulo,rx in [
                ('deposito_recursal','DEPÓSITO RECURSAL',r'dep[oó]sito recursal\s*(?:de|no valor de|:)?\s*(R\$\s*[\d.,]+)'),
                ('seguro_garantia','SEGURO-GARANTIA',r'seguro[ -]garantia\s*(?:judicial\s*)?(?:de|no valor de|:)?\s*(R\$\s*[\d.,]+)'),
                ('custas','CUSTAS PROCESSUAIS',r'custas (?:processuais|judiciais)?\s*(?:de|no valor de|:)?\s*(R\$\s*[\d.,]+)'),
            ]:
                match=re.search(rx,texto,re.I)
                if match:
                    contador+=1
                    eventos.append(Evento(data,rotulo,tipo,
                        f'Valor {match.group(1)} referido no preparo do recurso. Conferir documento bancário e data efetiva.',
                        pag,[match.group(1)],[], 'preparo informado; não confirma recolhimento',contador))
    return eventos,pendencias


def _relevantes_sem_data(paginas: list[Pagina], categorias_presentes: set[str]):
    rastros=[]
    for o in _buscar(paginas):
        if o.categoria not in IMPORTANTES or o.categoria in categorias_presentes:
            continue
        if not any(q['categoria']==o.categoria and q['pagina']==o.pagina for q in rastros):
            rastros.append({'categoria':o.categoria,'pagina':o.pagina,'trecho':o.trecho[:260],
                            'observacao':'MENÇÃO TEXTUAL SEM DATA/ATO VALIDADO — conferir documento'})
    return rastros[:50]


def _fase(eventos: list[Evento], paginas: list[Pagina]):
    """Apuração de fase com estados INDETERMINADO/CONHECIMENTO/LIQUIDAÇÃO/EXECUÇÃO.
    Fase por último ato material *com evidência*, não pelo nome do tribunal.
    """
    if not eventos:
        return ('NÃO DETERMINADA','Sem decisões datadas suficientes para identificar a fase com segurança.')
    ordn=sorted(eventos,key=_ordem_evento)
    sinal_exec=any(e.categoria in EXECUCAO_FORTE or EXECUCAO_INICIO.search(e.ato+' '+e.descricao[:150]) for e in ordn)
    homologacao=any(e.categoria=='homologacao' for e in ordn)
    parcelado=any(e.categoria=='parcelamento' and re.search(r'\b(?:art(?:igo|\.)?\s*916|entrada|parcelas mensais|deferid[oa])\b',e.descricao,re.I) for e in ordn)
    if sinal_exec or (homologacao and parcelado):
        return ('EXECUÇÃO','Constam atos executivos ou pedido de parcelamento após liquidação; conferir se há execução provisória, cumprimento voluntário ou suspensão.')
    if any(e.categoria in LIQUIDACAO for e in ordn):
        return ('LIQUIDAÇÃO','Constam cálculos ou atos de liquidação, mas não foi comprovada a instauração da execução.')
    if any(e.categoria=='transito' for e in ordn):
        return ('LIQUIDAÇÃO / AGUARDANDO CÁLCULOS','Trânsito localizado; conferir despacho de liquidação e se houve cálculo.')
    return ('CONHECIMENTO / NÃO CONFIRMADA','Não foram identificados atos posteriores suficientes para classificar liquidação/execução.')


def _polo(paginas: list[Pagina]):
    texto='\n'.join(p.texto for p in paginas[:min(len(paginas),15)])
    result={}
    for chave,exp in [('polo_ativo',r'(?im)^\s*(?:polo\s+ativo|reclamante)\s*:\s*(.{3,250})$'),('polo_passivo',r'(?im)^\s*(?:polo\s+passivo|reclamad[oa]s?)\s*:\s*(.{3,350})$'),('peritos',r'(?im)^\s*perit[oa]s?(?:\s+cont[aá]bil)?\s*:\s*(.{3,250})$')]:
        m=re.search(exp,texto)
        if m:result[chave]=m.group(1).strip()
    return result


def _resumo_final(eventos: list[Evento],fase: str) -> str:
    itens=sorted(eventos,key=_ordem_evento)
    recentes=[e for e in itens if e.categoria in {'acordo','parcelamento','pagamento','homologacao','sisbajud','penhoras','alvaras','deposito_judicial','audiencia','ultimo_despacho'}]
    if not recentes:return 'Não foi possível determinar o crédito pendente, as garantias e o motivo da audiência pelos atos datados disponíveis.'
    ult=recentes[-1]
    return ('Último ato relevante identificado: '+ult.data+' — '+ult.ato+'. '
            'Saldo efetivamente devido, valores disponíveis e motivo da audiência exigem conferência da última planilha e do despacho.')


def _formatar(resultado: dict) -> str:
    r=resultado
    numero=r['numero_cnj'] or 'PROCESSO NÃO IDENTIFICADO'
    vara=r['vara'] or 'VARA NÃO IDENTIFICADA'
    fase=r['fase_identificada']
    lines=[f'**HORÁRIO NÃO INFORMADO - {numero} - {vara} - {fase}**','',
           'Polo ativo: '+r.get('polo_ativo','Não localizado no texto fornecido'),'', '.', '',
           'Polo passivo: '+r.get('polo_passivo','Não localizado no texto fornecido'),'', '.', '',
           'Peritos: '+r.get('peritos','Não localizados no texto fornecido'),'', '.', '']
    if r['status']!='analise_preliminar':
        lines+=['','**ATENÇÃO:** sentença não localizada com segurança. A cronologia não foi produzida para evitar atos anteriores à sentença.','']
        return '\n'.join(lines)
    for e in r['eventos']:
        descricao=e['descricao'];dados=[]
        if e['pagina_pdf']:dados.append(f'p. PDF {e["pagina_pdf"]}')
        dados.extend(f'ID PJe {x}' for x in e['ids'][:2])
        p=' ('+'; '.join(dados)+')' if dados else ''
        # Negrito somente dos campos estáveis; números já estão no texto literal.
        descricao=re.sub(r'(R\$\s*[\d.,]+|\b\d{1,2}(?:,\d+)?%\b|\bPOSITIVO\b|\bNEGATIVO\b)',lambda m:'**'+m.group(0)+'**',descricao,flags=re.I)
        lines+=['',f'**{e["data"]} - {e["ato"].upper()}**: {descricao}{p}','','.','']
    if r['rastros_sem_data']:
        lines+=['','**DOCUMENTOS A CONFERIR (sem movimentação datada segura):**']
        for x in r['rastros_sem_data'][:12]:
            lines.append(f'- {PADROES[x["categoria"]][0]} — p. PDF {x["pagina"]}. Menção textual, não ato comprovado.')
    lines+=['','**SITUAÇÃO ATUAL:** '+r['situacao_atual'],
            '', '**CLASSIFICAÇÃO:** '+r['fundamento_fase'],
            '', '**CONFERÊNCIA OBRIGATÓRIA:** prévia automática a partir de texto pesquisável; conferir conteúdo integral dos documentos, datas efetivas, partes, valores e o último despacho antes de utilizar em audiência.']
    return '\n'.join(lines)


def analisar_integrado(paginas: list[Pagina], numero_cnj: str|None=None, pagina_sentenca: int=0) -> dict:
    if not paginas:raise ValueError('Nenhum documento recebido.')
    idx,criterio=_inicio_sentenca(paginas,pagina_sentenca)
    bruto='\n'.join(p.texto for p in paginas[:15])
    match=CNJ.search(bruto)
    num=numero_cnj or (match.group(0) if match else None)
    varam=re.search(r'(?im)^\s*(?:\d+ª\s+)?VARA DO TRABALHO[^\n]{0,140}',bruto)
    vara=varam.group(0).strip() if varam else None
    partes=_polo(paginas)
    base={'numero_cnj':num,'vara':vara,**partes,'pagina_inicial':paginas[idx].numero if idx is not None else None,
          'pagina_final':paginas[-1].numero,'criterio_corte':criterio,'paginas_totais':len(paginas)}
    if idx is None:
        final={**base,'status':'sentenca_nao_localizada','fase_identificada':'NÃO DETERMINADA','fundamento_fase':criterio,
               'eventos':[],'rastros_sem_data':[],'situacao_atual':'Conferir localização da sentença e enviar arquivo pesquisável.'}
        final['pauta_markdown']=_formatar(final)
        return final
    trechos=paginas[idx:]
    eventos,avisos=_documentos(trechos)
    # PDF do PJe pode ter sentença sem data no título. Nunca a omita;
    # indique explicitamente a ausência da data, sem usar datas de atos vizinhos.
    if not any(e.categoria=='sentenca' for e in eventos):
        pag0=trechos[0]
        texto0=' '.join(p.texto for p in trechos[:min(len(trechos),3)])[:8500]
        if re.search(r'\bsenten[cç]a\b',pag0.texto,re.I):
            eventos.append(Evento('DATA NÃO LOCALIZADA','SENTENÇA','sentenca',
                                  _sumario('SENTENÇA',texto0,'sentenca'),pag0.numero,
                                  list(dict.fromkeys(MONEY.findall(texto0)))[:10],
                                  list(dict.fromkeys(DOCID.findall(texto0)))[:8],
                                  'sentença localizada; data não confirmada',ordem_no_arquivo=-1))
            avisos.append('Sentença identificada, mas data não localizada em cabeçalho datado: conferir assinatura no documento.')
    eventos.sort(key=_ordem_evento)
    cats={e.categoria for e in eventos}
    rastros=_relevantes_sem_data(trechos,cats)
    fase,prova=_fase(eventos,trechos)
    resumo=_resumo_final(eventos,fase)
    final={**base,'status':'analise_preliminar','fase_identificada':fase,'fundamento_fase':prova,
           'avaliadas_fases':['LIQUIDAÇÃO','EXECUÇÃO'],
           'eventos':[asdict(e) for e in eventos], 'rastros_sem_data':rastros,
           'avisos':avisos+['Não foi realizada interpretação jurídica automatizada do teor integral das decisões.','Não usar como pauta definitiva sem conferência dos documentos e valores.'],
           'situacao_atual':resumo}
    final['pauta_markdown']=_formatar(final)
    return final


def analisar_texto_integrado(texto: str, numero_cnj: str|None=None, pagina_sentenca: int=0) -> dict:
    return analisar_integrado(paginas_de_texto(texto),numero_cnj,pagina_sentenca)


def analisar_pdf_integrado(path: str, numero_cnj: str|None=None, pagina_sentenca: int=0) -> dict:
    return analisar_integrado(paginas_de_pdf(path),numero_cnj,pagina_sentenca)