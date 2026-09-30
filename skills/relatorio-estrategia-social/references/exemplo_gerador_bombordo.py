"""v2 — relatório do cliente (enxuto, com identidade) + planilha de produção separada.
Todo número vem de dados_*.csv, insta-*.csv, prints do painel Meta (02–29/09) ou do CSV do Spotify."""
import csv, io, json, datetime as dt, html, statistics as st, os, base64, re, glob
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(HERE, *a)
ROOT = '/Volumes/SSD/Movies/Edição/Mídia/content/bombordo'
E = html.escape
DIAS = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']
MES = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6, 'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12}
MES_EN = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}

def fmt(n, d=0): return f'{n:,.{d}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
def pctf(x, d=1): return fmt(float(x), d) + '%'
def yt_date(s):  # "Sep 24, 2026" -> date
    m, d_, y = re.match(r'(\w+) (\d+), (\d+)', s).groups(); return dt.date(int(y), MES_EN[m], int(d_))
def tt_date(s):  # "21 September" -> date (2026)
    d_, m = s.split(); return dt.date(2026, MES[m], int(d_))
def ig_time(s): return dt.datetime.strptime(s, '%m/%d/%Y %H:%M') + dt.timedelta(hours=4)  # export UTC-7 -> São Luís
def cut(s, n):  # nunca corta no meio da palavra
    s = re.sub(r'\s+', ' ', s).strip()
    if len(s) <= n: return s
    return s[:n].rsplit(' ', 1)[0].rstrip(',.;:—-') + '…'

ig = [r for r in csv.DictReader(open(P('dados_instagram.csv'), encoding='utf-8')) if r['conta'] == 'danieldematospereira']
yt = [r for r in csv.DictReader(open(P('dados_youtube.csv'), encoding='utf-8')) if '2026' in r['publicado']]
tt = list(csv.DictReader(open(P('dados_tiktok.csv'), encoding='utf-8')))
tt_links = {m.group(1): 'https://www.tiktok.com/@danieldoporto_/video/' + m.group(1)
            for m in re.finditer(r'video/(\d+)', open(P('raw/tiktok metitricas 2/Content.csv'), encoding='utf-8-sig').read())}

# ---------------------------------------------------------------- miniaturas e títulos curtos
CAPAS = {k: glob.glob(f'{ROOT}/CORTES/*/{p}*CAPA*.png') + glob.glob(f'{ROOT}/CORTES/*/CAPA - {p}*.png') for k, p in {
    'inpasa': '04 - A INPASA', 'carga': '02 - EXISTE CARGA', 'atracacao': '03 - A PRIMEIRA ATRA', 'sextou': '05 - PREFIRO', 'wpost': '01 - PARA TRABALHAR',
    '80': '02 - 80%', 'sabonete': '03 - SEU SABONETE', 'gasolina': '04 - A GASOLINA', 'galinha': '05 - GALINHA', 'podcast': '01 - UM PODCAST',
    'lidera': '01 - ELE LIDERA', 'bombordo': '02 - AFINAL', 'uber': '03 - TEM GENTE', 'arte': '04 - TODA ARTE', 'amarracao': '05 - A AMARRA', 'ingles': '06 - O INGL',
    'ferry': '01 - ELA COMEÇOU', 'presidente': '02 - AOS 30', 'tdah': '03 - COM TDAH', 'telas': '04 - ELA TINHA', 'porta': '05 - OU ESSA'}.items()}
# (palavra-chave no texto do post, capa, título curto escrito para o cliente)
POSTS = [('3ª maior produtora de etanol', 'inpasa', 'Inpasa — 3ª maior do mundo'), ('INPASA', 'inpasa', 'Inpasa — 3ª maior do mundo'),
         ('regra de ouro', 'carga', 'A carga dita o mercado'), ('EXISTE CARGA', 'carga', 'A carga dita o mercado'),
         ('escala perfeita', 'atracacao', 'A primeira atracação de contêiner'), ('PRIMEIRA ATRACAÇÃO', 'atracacao', 'A primeira atracação de contêiner'),
         ('currículo perfeito', 'sextou', 'Compromisso x currículo'), ('CURRÍCULO LINDO', 'sextou', 'Compromisso x currículo'),
         ('outro lado do mundo', 'wpost', 'Geopolítica muda o frete'), ('WASHINGTON', 'wpost', 'Geopolítica muda o frete'),
         ('Cerca de 80%', '80', '80% do comércio passa por porto'), ('80% DE TUDO', '80', '80% do comércio passa por porto'),
         ('sabonete', 'sabonete', 'Sabonete e Coca-Cola no navio'), ('SABONETE', 'sabonete', 'Sabonete e Coca-Cola no navio'),
         ('maior risco da sua operação', 'gasolina', 'O risco da rotina'), ('GASOLINA', 'gasolina', 'O risco da rotina'),
         ('GALINHA', 'galinha', 'Galinha não dá em gôndola'), ('histórias que quase nunca', 'podcast', 'Apresentação do podcast'), ('UM PODCAST', 'podcast', 'Apresentação do podcast'),
         ('Liderança e Desenvolvimento', 'lidera', 'Liderança no Itaqui'), ('LIDERA UMA', 'lidera', 'Liderança no Itaqui'),
         ('termos técnicos', 'bombordo', 'O que é bombordo e boreste'), ('BOMBORDO E BORESTE?', 'bombordo', 'O que é bombordo e boreste'),
         ('UBER', 'uber', 'Do Uber para o porto'), ('ARTE', 'arte', 'Toda arte precisa ser assinada'),
         ('mesma lógica há milênios', 'amarracao', 'Amarração: 5 mil anos'), ('AMARRAÇÃO DE NAVIOS NÃO', 'amarracao', 'Amarração: 5 mil anos'),
         ('fluência em inglês', 'ingles', 'Inglês e proatividade'), ('INGLÊS', 'ingles', 'Inglês e proatividade'),
         ('primeira função', 'ferry', 'Do ferryboat à liderança'), ('FERRYBOAT', 'ferry', 'Do ferryboat à liderança'),
         ('idade chama atenção', 'presidente', 'Presidente mais jovem'), ('PORTA VAI', 'porta', 'Vou arrombar essa porta'),
         ('inglês “perfeito”', None, 'Inglês não precisa ser perfeito'), ('Identificando Potencial', None, 'Identificar talentos'),
         ('Empreendedorismo', None, 'Empreender no porto'), ('Só vontade não basta', None, 'Só vontade não basta'),
         ('vaga no comércio exterior', None, 'Vagas com outro nome'), ('placa escrita', None, 'Oportunidades no etanol de milho'),
         ('inovação portuária', None, 'Política de inovação dos portos'), ('DAAS', None, 'Drones (DAAS) na PEGN'), ('futuro dos portos', None, 'Drones nos portos'), ('drones', None, 'Drones nos portos'), ('Drones', None, 'Drones nos portos'),
         ('Amarração de Navios: Inovação', None, 'EP 01 · Dayvid Guterres'), ('42 Anos', None, 'EP 00 · Silvio Lúcio'),
         ('30 Anos de Carreira', None, 'EP 02 · Dannyel'), ('Juliana Frazão', None, 'EP 03 · Juliana e Larissa'),
         ('Inspetor de Embarque', None, 'Inspetor de embarque'), ('A AMARRAÇÃO', 'amarracao', 'Amarração: 5 mil anos')]
_th = {}
def thumb(path, w=64):
    if not path: return ''
    if path not in _th:
        im = Image.open(path).convert('RGB'); im.thumbnail((w * 2, w * 4)); b = io.BytesIO(); im.save(b, 'JPEG', quality=72)
        _th[path] = 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()
    return _th[path]
def ident(text):
    for k, capa, curto in POSTS:
        if k in text: return (CAPAS[capa][0] if capa and CAPAS.get(capa) else None), curto
    return None, cut(text, 38)
TT_BY_KEY = {'inglês “perfeito”': '7686238114808941845', 'placa escrita': '7688210969373330709', 'inovação portuária': '7685465599706713362',
             'futuro dos portos': '7690531847234784564', 'Só vontade não basta': '7684411717513760008'}
def ig_thumb(r):
    src, curto = ident(r['texto'])
    if src: return src, curto
    sc = re.search(r'/(?:p|reel)/([^/]+)', r['link']).group(1)
    if os.path.exists(P('thumbs', f'ig_{sc}.jpg')): return P('thumbs', f'ig_{sc}.jpg'), curto
    for k, v in TT_BY_KEY.items():
        if k in r['texto']: return P('thumbs', f'tt_{v}.jpg'), curto
    return None, curto
def img(src, cls='th'): return f'<img class="{cls}" src="{src}">' if src else '<div class="th ph"></div>'

# ---------------------------------------------------------------- números
IGP = dict(views=194716, reach='125,3 mil', inter='15 mil', visits='1,2 mil', follows=754, unf=36, clicks=11, conv=92, nonf=87.5)
inp = max(ig, key=lambda r: int(r['views'])); rest = [r for r in ig if r is not inp]
med = lambda k, rs: st.median(float(r[k]) for r in rs if r[k] != '')
reels = [r for r in rest if 'reel' in r['tipo']]; car = [r for r in rest if 'carousel' in r['tipo']]
for r in ig:
    r['seg_mil_alc'] = int(r['seg']) / int(r['alcance']) * 1000 if int(r['alcance']) else 0
eps = [r for r in yt if r['formato'] == 'Episódio']
shorts = [r for r in yt if r['formato'] == 'Short' and int(r['views']) > 0]
TT_PAINEL = 5428; tt_soma = sum(int(r['views']) for r in tt); tt_med = st.median(int(r['views']) for r in tt)
YT = dict(views=2449, horas=58.3, subs=30, gan=31, lost=1, imp=5783, ctr=2.59)
# ritmo de setembro (reels próprios + shorts por semana)
wk = {}
for r in ig:
    if 'reel' in r['tipo']: wk.setdefault(ig_time(r['data']).isocalendar()[1], [0, 0])[0] += 1
for r in shorts:
    d = yt_date(r['publicado'])
    if d.month == 9: wk.setdefault(d.isocalendar()[1], [0, 0])[1] += 1
print('ritmo por semana ISO [reels IG, shorts YT]:', dict(sorted(wk.items())))
# série diária de views (Instagram)
L = list(csv.reader(io.StringIO(open(os.path.join(HERE, '..', '..', 'insta-Views.csv'), 'rb').read().decode('utf-16'))))
daily = [(dt.date.fromisoformat(a[:10]), int(b)) for a, b in (r for r in L if len(r) == 2 and r[0][:4] == '2026')]

# ---------------------------------------------------------------- calendário (fonte única p/ PDF e planilha)
PILAR = {'Porto em números': ('Topo', '#4F95FF'), 'Bastidores da operação': ('Topo', '#1F5FBF'),
         'Carreira no porto': ('Meio', '#F2A541'), 'Episódio da semana': ('Fundo', '#0B1A33')}
ACERVO = {
    '13mi': dict(p='Porto em números', curto='13 milhões de toneladas', tema='Mais de 13 milhões de toneladas de grãos em um ano', ep='EP 01 · Dayvid Guterres', ts='00:04:01',
                 gancho='"SÃO MAIS DE 13 MILHÕES DE TONELADAS DE SOJA, MILHO E FARELO EM UM ANO"', est=['O número na 1ª frase', 'O que esse volume representa', 'Quem trabalha para ele passar']),
    'aero': dict(p='Bastidores da operação', curto='O navio com aeródromo', tema='O navio com aeródromo que eles atenderam', ep='EP 01 · Dayvid Guterres', ts='00:09:46',
                 gancho='"A GENTE ATENDEU UM NAVIO COM AERÓDROMO"', est=['A frase do navio multipropósito', 'Por que cada navio pede uma amarração diferente', 'Fecha na curiosidade']),
    '15': dict(p='Porto em números', curto='Amarração 15% mais rápida', tema='Tempo de amarração 15% menor', ep='EP 01 · Dayvid Guterres', ts='00:27:23',
               gancho='"A GENTE ENCURTOU O TEMPO DA AMARRAÇÃO EM 15%"', est=['O resultado na 1ª frase', 'Como fizeram', 'Por que navio parado custa caro']),
    'demurrage': dict(p='Bastidores da operação', curto='Demurrage', tema='A primeira palavra que você escuta no porto', ep='EP 02 · Dannyel', ts='00:23:58',
                      gancho='"A PRIMEIRA PALAVRA QUE VOCÊ ESCUTA NO PORTO É DEMURRAGE"', est=['A frase de abertura', 'O que é demurrage e dispatch', 'O peso no custo logístico do Brasil']),
    'controlador': dict(p='Bastidores da operação', curto='O "controlador de voo" do porto', tema='O controlador de voo do porto', ep='EP 02 · Dannyel', ts='00:17:48',
                        gancho='"SABE O CONTROLADOR DE VOO DO AEROPORTO? NO PORTO TAMBÉM TEM"', est=['A comparação', 'Quem faz esse papel e o que decide', 'Por que é invisível para quem está fora']),
    'trading': dict(p='Bastidores da operação', curto='Como a trading ganha', tema='A trading ganha no volume', ep='EP 02 · Dannyel', ts='00:24:40',
                    gancho='"A TRADING GANHA NO VOLUME. E O VOLUME É ASTRONÔMICO"', est=['A margem apertada x o volume', 'O produtor com 500 hectares de soja e milho safrinha', 'Onde o porto entra na conta']),
    'comandante': dict(p='Carreira no porto', curto='O comandante sem ninguém', tema='Intérprete de navio: o comandante não tem com quem conversar', ep='EP 02 · Dannyel', ts='00:09:16',
                       gancho='"O COMANDANTE É O PRESIDENTE DO NAVIO. E NÃO TEM COM QUEM CONVERSAR"', est=['A solidão do comandante', 'O intérprete como ponte', 'Como isso abriu a carreira do Dannyel']),
    'maceio': dict(p='Carreira no porto', curto='O navio dos 15 anos', tema='Aos 15 anos viu um navio; 18 anos depois trabalhou para o dono dele', ep='EP 02 · Dannyel', ts='00:07:12',
                   gancho='"AOS 15 ANOS EU VI ESSE NAVIO. 18 ANOS DEPOIS EU TRABALHAVA PARA O DONO DELE"', est=['1995: o Global Maceió no Itaqui', 'O encanto', 'A virada 18 anos depois']),
}
EP03 = {
    'telas': dict(p='Carreira no porto', curto='A resposta em 4 telas', tema='Ela tinha a resposta em 4 telas', ep='EP 03 · Juliana e Larissa', ts='corte 04 pronto',
                  gancho='"ELA TINHA A RESPOSTA EM 4 TELAS. DUVIDARAM PORQUE ERA MULHER"', est=['Corte pronto (pasta legendas animadas v2)']),
    'presidente': dict(p='Carreira no porto', curto='Presidente mais jovem', tema='Aos 30, o presidente mais jovem do setor', ep='EP 03 · Juliana e Larissa', ts='corte 02 pronto',
                       gancho='"AOS 30 ANOS, ELE JÁ É O PRESIDENTE MAIS JOVEM DO SETOR NO BRASIL"', est=['Corte pronto (pasta legendas animadas v2)']),
    'tdah': dict(p='Carreira no porto', curto='TDAH como trunfo', tema='Com TDAH, o hiperfoco virou trunfo', ep='EP 03 · Juliana e Larissa', ts='corte 03 pronto',
                 gancho='"COM TDAH, ELA TRANSFORMOU O HIPERFOCO NO SEU MAIOR TRUNFO NO PORTO"', est=['Corte pronto (pasta legendas animadas v2)']),
}
PLANO_B = [
    dict(p='Bastidores da operação', curto='Um mar de procedimentos', tema='Cada operação é um mar de procedimentos', ep='EP 00 · Silvio Lúcio', ts='00:25:31',
         gancho='"CADA OPERAÇÃO DESSA É UM MAR DE PROCEDIMENTOS"', est=['A frase do Silvio', 'Navio, caminhão, vagão: a cadeia diária', '"Todo dia tem uma história diferente"']),
    dict(p='Bastidores da operação', curto='O inspetor do navio atracado', tema='A função criada para cuidar do navio depois de atracado', ep='EP 01 · Dayvid Guterres', ts='00:13:51',
         gancho='"A GENTE CRIOU UMA FUNÇÃO SÓ PARA CUIDAR DO NAVIO DEPOIS DE ATRACADO"', est=['O problema: cabos sob estresse', 'O inspetor que eles criaram', 'Por que cada cabo tem um trabalho']),
    dict(p='Carreira no porto', curto='A pergunta de 1 milhão', tema='Como trabalhar no terminal? Manda o currículo', ep='EP 00 · Silvio Lúcio', ts='00:38:23',
         gancho='"A PERGUNTA DE 1 MILHÃO: COMO EU FAÇO PARA TRABALHAR AQUI? MANDA O CURRÍCULO"', est=['A pergunta', 'A resposta direta do Silvio', 'O que o RH olha'])]
def novo(n, tipo):
    if tipo == 'chamada':
        return dict(p='Episódio da semana', curto=f'Chamada do EP {n:02d}', tema=f'Chamada do EP {n:02d}: a melhor resposta do convidado', ep=f'EP {n:02d}', ts='escolher na edição',
                    gancho='A frase mais forte do convidado, sem introdução, nos 3 primeiros segundos', est=['Frase de impacto', 'Quem é o convidado (texto na tela)', 'Corta no auge: "o resto está no episódio"'])
    if tipo == 'fato':
        return dict(p='Porto em números', curto=f'EP {n:02d} · fato/número', tema=f'O número ou fato mais surpreendente do EP {n:02d}', ep=f'EP {n:02d}', ts='escolher na edição',
                    gancho='"[NÚMERO/FATO] + [O QUÊ]", como "A INPASA JÁ É A 3ª MAIOR INDÚSTRIA DE ETANOL DO MUNDO"', est=['Fato na 1ª frase', 'Contexto em até 2 frases', 'Por que importa para quem trabalha no porto'])
    return dict(p='Carreira no porto', curto=f'EP {n:02d} · virada de carreira', tema=f'A virada de carreira do convidado do EP {n:02d}', ep=f'EP {n:02d}', ts='escolher na edição',
                gancho='A decisão ou o obstáculo em 1 frase ("Eu comecei vendendo passagens...")', est=['Onde começou', 'O obstáculo/decisão', 'Onde chegou', 'A lição para quem quer entrar'])

D = lambda d: dt.date(2026, 10, d)
HORA = {40: '12:00', 41: '12:00', 42: '12:00', 43: '19:00', 44: '19:00'}  # teste T2; feriado de 12/10 fora do bloco das 19h
cortes = []   # (data, hora, item)
def add(d, it, hora=None): cortes.append(dict(data=d, hora=hora or HORA[d.isocalendar()[1]], **it))
add(D(1), EP03['telas']); add(D(2), EP03['tdah'])  # 'presidente' já saiu em 30/09 no Instagram
episodios = []
plano = {5: (4, ['13mi', 'aero']), 12: (5, ['15', 'demurrage']), 19: (6, ['controlador', 'trading']), 26: (7, ['comandante', 'maceio'])}
for seg, (n, ac) in plano.items():
    episodios.append((D(seg), n))
    add(D(seg), novo(n, 'chamada'), '19:15')          # depois do episódio no ar (19h)
    add(D(seg + 1), novo(n, 'fato')); add(D(seg + 2), ACERVO[ac[0]])
    add(D(seg + 3), novo(n, 'virada')); add(D(seg + 4), ACERVO[ac[1]])
for c in cortes: c['funil'] = PILAR[c['p']][0]
cnt = lambda f: sum(1 for c in cortes if f(c))
N = len(cortes); TOPO = cnt(lambda c: c['funil'] == 'Topo'); MEIO = cnt(lambda c: c['funil'] == 'Meio'); FUNDO = cnt(lambda c: c['funil'] == 'Fundo')
NUM = cnt(lambda c: c['p'] == 'Porto em números'); BAST = cnt(lambda c: c['p'] == 'Bastidores da operação'); CARR = cnt(lambda c: c['p'] == 'Carreira no porto')
assert all(c['data'].weekday() < 5 for c in cortes), 'corte no fim de semana'
assert max(sum(1 for c in cortes if c['data'].isocalendar()[1] == w) for w in HORA) <= 5, 'acima da capacidade'
print(f'cortes {N}: topo {TOPO} meio {MEIO} fundo {FUNDO} | números {NUM} bastidores {BAST} carreira {CARR}')

REGRAS_CTA = {'Instagram': 'Reels', 'TikTok': 'Vídeo', 'YouTube Shorts': 'Shorts'}
CTA = {'Instagram': '"Episódio completo no link da bio" + pergunta para os comentários; link do Linktree nos stories do dia',
       'TikTok': 'Texto na tela: "Episódio completo: Bombordo e Boreste no YouTube"; legenda de no máximo 2 linhas',
       'YouTube Shorts': 'Vídeo relacionado apontando para o episódio completo'}
SUCESSO = {('Topo', 'Instagram'): 'Views ≥ 1.500 e compartilhamentos ≥ 1% do alcance', ('Meio', 'Instagram'): 'Salvamentos ≥ 0,3% do alcance ou ≥ 5 seguidores',
           ('Fundo', 'Instagram'): '≥ 2 cliques no link no dia', ('Topo', 'TikTok'): 'Views ≥ 400', ('Meio', 'TikTok'): 'Views ≥ 400 e ≥ 1 comentário',
           ('Fundo', 'TikTok'): '≥ 5 visitas ao perfil', ('Topo', 'YouTube Shorts'): 'Views ≥ 100 e ≥ 50% assistido',
           ('Meio', 'YouTube Shorts'): 'Views ≥ 100 e ≥ 50% assistido', ('Fundo', 'YouTube Shorts'): '≥ 5 cliques no vídeo relacionado'}
rows = []
for c in sorted(cortes, key=lambda c: (c['data'], c['hora'])):
    for pl, f in REGRAS_CTA.items():
        rows.append(dict(data=c['data'].strftime('%d/%m') + ' ' + DIAS[c['data'].weekday()], horario=c['hora'], plataforma=pl, formato=f, pilar=c['p'], funil=c['funil'],
                         tema=c['tema'], gancho=c['gancho'], estrutura=c['est'] + ['CTA'], trecho=f"{c['ep']} · {c['ts']}", cta=CTA[pl], metrica=SUCESSO[(c['funil'], pl)]))
for d, n in episodios:
    for pl in ('YouTube', 'Spotify'):
        rows.append(dict(data=d.strftime('%d/%m') + ' ' + DIAS[d.weekday()], horario='19:00', plataforma=pl, formato='Episódio completo', pilar='Episódio da semana', funil='Fundo',
                         tema=f'EP {n:02d} — convidado a confirmar', gancho='Título com o número/fato mais forte + nome do convidado no fim (teste T4)' if pl == 'YouTube' else 'Mesmo título do YouTube (conferir grafia dos nomes)',
                         estrutura=['Trecho mais forte nos primeiros 30 s', 'Capítulos na descrição', 'Tela final com o Short da semana'] if pl == 'YouTube' else ['Descrição com capítulos', 'Links do YouTube e do Linktree'],
                         trecho=f'EP {n:02d}', cta='Inscreva-se + Spotify na descrição' if pl == 'YouTube' else 'Seguir o podcast',
                         metrica='CTR ≥ 3,5% e ≥ 5 inscritos em 7 dias' if pl == 'YouTube' else '≥ 5 plays em 7 dias'))
rows.sort(key=lambda r: (r['data'][:5][::-1], r['horario']))
for d_, it in zip((5, 6, 8), PLANO_B):
    for pl, f in REGRAS_CTA.items():
        rows.append(dict(data=f'{d_:02d}/10 {DIAS[D(d_).weekday()]} · PLANO B', horario='12:00', plataforma=pl, formato=f, pilar=it['p'], funil=PILAR[it['p']][0], tema=it['tema'], gancho=it['gancho'],
                         estrutura=it['est'] + ['CTA'], trecho=f"{it['ep']} · {it['ts']}", cta=CTA[pl], metrica=SUCESSO[(PILAR[it['p']][0], pl)]))
REGRAS = [['Plano B do EP 04', 'Se o EP 04 não estiver gravado até 02/10: segunda 05/10 sai "Um mar de procedimentos" no lugar da chamada, terça 06/10 "O inspetor do navio atracado" e quinta 08/10 "A pergunta de 1 milhão" (linhas PLANO B). O EP 04 e os demais episódios passam uma semana para frente.']] + [['CTA padrão — ' + k, v] for k, v in CTA.items()] + [[f'Sucesso — {f} · {p}', v] for (f, p), v in SUCESSO.items()] + [
    ['Pilar → etapa', 'Porto em números e Bastidores = Topo; Carreira = Meio; Episódio = Fundo'],
    ['Horário (teste T2)', 'Cortes às 12h nas semanas de 01, 05 e 12/10; às 19h nas semanas de 19 e 26/10 (o feriado de 12/10 fica fora do bloco das 19h). Episódio 19h, chamada 19h15'],
    ['Stories', 'Todo dia: corte do dia + figurinha de link para o Linktree'],
    ['Coleta para o próximo relatório', 'Instagram: export de Conteúdo 01–31/10, séries diárias e prints (Visão geral, Resultados, Público, Stories, Benchmarking); Linktree: cliques por link; YouTube: Conteúdo 01–31/10; TikTok: Content/Overview/Viewers/Followers 01–31/10; Spotify: plays por episódio no mês. Tudo no mesmo dia e período.']]
json.dump(dict(rows=rows, regras=REGRAS), open(P('calendario_v2.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('linhas da planilha:', len(rows))

# ---------------------------------------------------------------- gráficos SVG
def svg_daily():
    W, H, l, b, t = 700, 150, 44, 22, 12
    xs = lambda i: l + i * (W - l - 10) / (len(daily) - 1); mx = max(v for _, v in daily)
    ys = lambda v: H - b - v / mx * (H - b - t)
    pts = ' '.join(f'{xs(i):.1f},{ys(v):.1f}' for i, (_, v) in enumerate(daily))
    g = ''.join(f'<line x1="{l}" x2="{W-10}" y1="{ys(v):.1f}" y2="{ys(v):.1f}" class="gl"/><text x="{l-6}" y="{ys(v)+3:.1f}" class="ax" text-anchor="end">{fmt(v/1000)} mil</text>' for v in (0, 20000, 40000, 60000))
    xl = ''.join(f'<text x="{xs(i):.1f}" y="{H-6}" class="ax" text-anchor="middle">{d.strftime("%d/%m")}</text>' for i, (d, _) in enumerate(daily) if d.day in (1, 8, 15, 22, 27))
    ip = next(i for i, (d, _) in enumerate(daily) if d == dt.date(2026, 9, 24)); pk = max(range(len(daily)), key=lambda i: daily[i][1])
    return (f'<svg viewBox="0 0 {W} {H}" class="chart">{g}{xl}<polyline points="{pts}" fill="none" stroke="#4F95FF" stroke-width="2.2" stroke-linejoin="round"/>'
            f'<line x1="{xs(ip):.1f}" x2="{xs(ip):.1f}" y1="{t}" y2="{H-b}" stroke="#0B1A33" stroke-dasharray="3 3"/><text x="{xs(ip)-5:.1f}" y="{H-b-6}" class="an" text-anchor="end">24/09 · Inpasa publicada</text>'
            f'<circle cx="{xs(pk):.1f}" cy="{ys(daily[pk][1]):.1f}" r="4" fill="#4F95FF" stroke="#fff" stroke-width="2"/><text x="{xs(pk)-8:.1f}" y="{ys(daily[pk][1])+4:.1f}" class="an" text-anchor="end">{fmt(daily[pk][1])} views em {daily[pk][0].strftime("%d/%m")}</text></svg>')

def svg_funnel():
    st_ = [('Contas alcançadas', '125,3 mil', 125300), ('Visitas ao perfil', '1,2 mil', 1200), ('Novos seguidores', '754', 754), ('Cliques no Linktree', '11', 11)]
    rates = ['', '~1,0% do alcance', '~63% das visitas', '~0,9% das visitas']
    W, row = 700, 44; out = [f'<svg viewBox="0 0 {W} {row*4+6}" class="chart">']
    for i, (lab, txt, v) in enumerate(st_):
        w = max(40, (v / 125300) ** 0.25 * 420); x = 150 + (420 - w) / 2; y = i * row
        col = '#C0392B' if i == 3 else ('#0B1A33' if i == 0 else '#4F95FF')
        out.append(f'<rect x="{x:.0f}" y="{y+4}" width="{w:.0f}" height="{row-10}" rx="4" fill="{col}"/><text x="140" y="{y+row/2+3}" class="fl" text-anchor="end">{lab}</text>'
                   f'<text x="{150+210}" y="{y+row/2+4}" class="fv" text-anchor="middle">{txt}</text><text x="585" y="{y+row/2+3}" class="fr">{rates[i]}</text>')
    out.append('</svg>'); return ''.join(out)

def meta_bar(base, meta, lbl_b, lbl_m):
    w = min(100, base / meta * 100)
    return f'<div class="mb"><div class="mbf" style="width:{w:.0f}%"></div></div><div class="mbl"><span>{lbl_b}</span><span>meta {lbl_m}</span></div>'

# ---------------------------------------------------------------- HTML
font = os.path.expanduser('~/.claude/skills/bombordo-boreste/assets/CalSans-Regular.ttf')
_bg = base64.b64encode(open(os.path.join(ROOT, 'metricas', '_marca', 'logo_begrow.png'), 'rb').read()).decode()
# SVG embrulhando o PNG: define o tamanho impresso no rodapé sem perder resolução
BEGROW_SVG = 'data:image/svg+xml;base64,' + base64.b64encode(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="30" height="30" viewBox="0 0 150 150"><rect width="150" height="150" rx="18" fill="#101D51"/><image width="150" height="150" xlink:href="data:image/png;base64,{_bg}"/></svg>'.encode()).decode()
logo = 'data:image/png;base64,' + base64.b64encode(open(f'{ROOT}/ep4/codex_reels/assets/logo_podcast.png', 'rb').read()).decode()
logo_w = 'data:image/png;base64,' + base64.b64encode(open(os.path.expanduser('~/.claude/skills/bombordo-boreste/assets/logo_portos_white.png'), 'rb').read()).decode()
H = []; A = H.append
def table(head, body, cls=''):
    return (f'<table class="{cls}"><thead><tr>' + ''.join(f'<th>{x}</th>' for x in head) + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td>{x}</td>' for x in r) + '</tr>' for r in body) + '</tbody></table>')

# ---------------------------------------------------------------- série mensal: histórico que cresce a cada mês
HIST = os.path.join(HERE, '..', '..', '..', 'historico_bombordo.json')
LINHAS = [('Instagram', 'Views', 'ig_views'), ('Instagram', 'Contas alcançadas', 'ig_alcance'), ('Instagram', 'Novos seguidores', 'ig_seg'),
          ('Instagram', 'Visitas ao perfil', 'ig_visitas'), ('Instagram', 'Cliques no Linktree', 'ig_cliques'), ('Instagram', 'Reels publicados', 'ig_reels'),
          ('Instagram', 'Carrosséis publicados', 'ig_carrosseis'), ('Instagram', 'Stories publicados', 'ig_stories'),
          ('YouTube', 'Views', 'yt_views'), ('YouTube', 'Horas assistidas', 'yt_horas'), ('YouTube', 'Novos inscritos', 'yt_insc'), ('YouTube', 'Cliques na miniatura (CTR)', 'yt_ctr'),
          ('YouTube', 'Episódios publicados', 'yt_eps'), ('YouTube', 'Shorts publicados', 'yt_shorts'),
          ('TikTok', 'Views', 'tt_views'), ('TikTok', 'Vídeos publicados', 'tt_videos'), ('TikTok', 'Seguidores (total)', 'tt_seg'), ('Spotify', 'Plays nos 30 primeiros dias (soma)', 'sp_plays')]
FMT = {'yt_horas': lambda v: fmt(v, 1), 'yt_ctr': lambda v: fmt(v, 2) + '%',
       'ig_alcance': lambda v: fmt(v / 1000, 1) + ' mil', 'ig_visitas': lambda v: fmt(v / 1000, 1) + ' mil'}  # painel mostra arredondado (125,3K; 1,2K)
hist = json.load(open(HIST, encoding='utf-8')) if os.path.exists(HIST) else {'cliente': 'Bombordo e Boreste', 'meses': {}}
hist['meses']['2026-09'] = dict(
    rotulo='set/26', base=True,
    metricas=dict(ig_views=194716, ig_alcance=125300, ig_seg=754, ig_visitas=1200, ig_cliques=11, ig_reels=sum(1 for r in ig if 'reel' in r['tipo']),
                  ig_carrosseis=sum(1 for r in ig if 'carousel' in r['tipo']), ig_stories=36, yt_views=2449, yt_horas=58.3, yt_insc=30, yt_ctr=2.59,
                  yt_eps=3, yt_shorts=sum(1 for r in shorts if yt_date(r['publicado']).month == 9), tt_views=TT_PAINEL, tt_videos=len(tt), tt_seg=20, sp_plays=19),
    contexto=['Mês base da série: as publicações regulares começaram em 10/09.',
              'Ritmo: cerca de 5 cortes por semana (5, 6, 5 e 3 reels nas semanas de setembro) + 1 episódio.',
              '3 episódios novos: EP 01 (Dayvid), EP 02 (Dannyel) e EP 03 (Juliana e Larissa).',
              'Viral fora do padrão: Inpasa (24/09), com 78% das views e 82% dos seguidores do mês no Instagram.',
              'TikTok (@danieldoporto) começou a publicar em 10/09. Sem tráfego pago.'],
    plano=dict(metas={k: m for k, m in [('ig_seg', 300), ('ig_cliques', 40), ('yt_insc', 50), ('yt_ctr', 3.5), ('sp_plays', 40), ('tt_seg', 60)]},
               testes=['T1 · Fórmula Inpasa', 'T2 · Horário 12h x 19h', 'T3 · TikTok adaptado', 'T4 · Título do episódio'], cortes_planejados=None),
    aprendizados=['Gancho com número ou fato de escala na 1ª frase é o que mais compartilha (Inpasa, "a carga dita o mercado").',
                  'Quem visita o perfil segue (63%), mas não clica no link: o próximo passo precisa ser pedido.',
                  'No YouTube, inscrito vem do episódio completo; Shorts servem para descoberta.',
                  'A legenda do Instagram não serve no TikTok: mesmo vídeo, 0 comentários e 12 visitas ao perfil.',
                  'Um viral pode fazer o mês: as metas são calculadas sem contar com ele.'])
json.dump(hist, open(HIST, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
MESES = sorted(hist['meses']); COLS_EVO = MESES + ['2026-10', '2026-11', '2026-12'][:max(0, 4 - len(MESES))]
def evo_table():
    head = ['Rede', 'Indicador'] + [hist['meses'][m]['rotulo'] if m in hist['meses'] else dt.date(int(m[:4]), int(m[5:]), 1).strftime('%b/%y').replace('Oct', 'out').replace('Nov', 'nov').replace('Dec', 'dez') for m in COLS_EVO]
    body = []
    for rede, nome, k in LINHAS:
        cells = []
        for m in COLS_EVO:
            v = hist['meses'].get(m, {}).get('metricas', {}).get(k)
            cells.append(f'<span class="n">{FMT.get(k, fmt)(v)}</span>' if v is not None else '<span class="note">—</span>')
        body.append([rede, nome] + cells)
    return table(head, body, 'evo')
def link(url, txt): return f'<a href="{E(url)}">{txt}</a>'
HYP = '<span class="hyp">hipótese</span>'

A(f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Bombordo e Boreste · Relatório de setembro 2026</title><style>
@font-face {{ font-family:'Cal Sans'; src:url('file://{font}'); }}
@page {{ size:A4; margin:18mm 14mm 16mm;
  @top-left {{ content:'Bombordo e Boreste · Relatório de setembro 2026'; font:8pt -apple-system,Helvetica,sans-serif; color:#5B6678; }}
    @bottom-right {{ content:counter(page); font:8pt -apple-system,Helvetica,sans-serif; color:#0B1A33; }} }}
@page capa {{ margin:0; @top-left {{ content:none; }} @bottom-right {{ content:none; }} @bottom-left {{ content:none; }} }}
@page land {{ size:A4 landscape; margin:16mm 12mm 14mm; }}
:root {{ --navy:#0B1A33; --blue:#4F95FF; --ink:#1B2433; --mut:#5B6678; --line:#E3E8F0; --soft:#F2F6FC; }}
* {{ box-sizing:border-box; }}
body {{ font-family:-apple-system,'Helvetica Neue',Arial,sans-serif; color:var(--ink); font-size:9.4pt; line-height:1.45; margin:0; background:#fff; }}
h1,h2,h3,.kpi b,.big {{ font-family:'Cal Sans',-apple-system,sans-serif; font-weight:400; color:var(--navy); font-variant-ligatures:none; font-feature-settings:'liga' 0,'clig' 0,'calt' 0,'kern' 0; text-rendering:geometricPrecision; }}
h2 {{ font-size:19pt; margin:0 0 3px; }} .kick {{ color:var(--blue); font-size:8.5pt; letter-spacing:.08em; text-transform:uppercase; font-weight:700; margin-bottom:2px; }}
.rule {{ height:3px; background:linear-gradient(90deg,var(--navy) 0 18%,var(--blue) 18% 100%); margin:4px 0 12px; border-radius:2px; }}
h3 {{ font-size:12pt; margin:14px 0 6px; }}
section {{ page-break-before:always; }} .land {{ page:land; }}
a {{ color:var(--blue); text-decoration:none; }}
.capa {{ page:capa; background:var(--navy); color:#fff; width:210mm; height:297mm; padding:30mm 22mm; position:relative; overflow:hidden; }}
.capa .wm {{ font-family:'Cal Sans'; font-size:44pt; line-height:1; color:#fff; margin-top:34mm; }}
.capa .t {{ font-size:17pt; color:var(--blue); margin-top:10px; font-family:'Cal Sans'; }}
.capa .d {{ font-size:10.5pt; color:#C9D5EA; margin-top:10mm; line-height:1.7; }}
.capa .by {{ position:absolute; left:22mm; bottom:24mm; display:flex; gap:12px; align-items:center; color:#C9D5EA; font-size:9.5pt; }}
.capa .by img {{ height:18mm; }} .capa .bar {{ position:absolute; right:0; top:0; width:14mm; height:100%; background:var(--blue); }}
.kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin:6px 0 10px; }}
.kpi {{ background:var(--soft); border-radius:10px; padding:9px 11px; border-top:3px solid var(--blue); }}
.kpi b {{ display:block; font-size:17pt; }} .kpi span {{ color:var(--mut); font-size:8.2pt; }}
table {{ width:100%; border-collapse:collapse; margin:6px 0 10px; font-size:8.5pt; }}
th {{ background:var(--navy); color:#fff; text-align:left; padding:5px 6px; font-weight:600; }}
td {{ border-bottom:1px solid var(--line); padding:4px 6px; vertical-align:middle; }} tr {{ page-break-inside:avoid; }}
td.n, th.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
.two {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
.box {{ border:1px solid var(--line); border-radius:10px; padding:10px 12px; margin:6px 0; page-break-inside:avoid; background:#fff; }}
.box.blue {{ border-left:4px solid var(--blue); background:var(--soft); }}
.box.warn {{ border-left:4px solid #C0392B; }}
.hyp {{ display:inline-block; background:#FFF4D6; color:#7A5600; font-size:7.4pt; font-weight:700; padding:0 5px; border-radius:4px; text-transform:uppercase; }}
.note {{ color:var(--mut); font-size:8pt; margin:2px 0 8px; }}
.th {{ width:26px; height:38px; object-fit:cover; border-radius:4px; display:block; }} .th.wide {{ width:56px; height:32px; }}
.ph {{ background:var(--soft); border:1px dashed #C9D5EA; }}
.chart {{ width:100%; height:auto; }} .gl {{ stroke:#E3E8F0; }} .ax {{ font-size:9px; fill:#5B6678; }} .an {{ font-size:10px; fill:#0B1A33; font-weight:600; }}
.fl {{ font-size:11px; fill:#1B2433; }} .fv {{ font-size:12px; fill:#fff; font-weight:700; }} .fr {{ font-size:10.5px; fill:#5B6678; }}
.mb {{ height:9px; background:var(--soft); border-radius:5px; overflow:hidden; }} .mbf {{ height:9px; background:var(--blue); }}
.mbl {{ display:flex; justify-content:space-between; font-size:7.6pt; color:var(--mut); }}
ol,ul {{ margin:4px 0 8px 18px; padding:0; }} li {{ margin:3px 0; }}
.grid {{ display:grid; grid-template-columns:repeat(7,1fr); gap:4px; }}
.gd {{ min-height:22.5mm; border:1px solid var(--line); border-radius:6px; padding:4px; font-size:7.6pt; background:#fff; }}
.gd.off {{ background:#FAFBFD; color:#B5BDCB; }} .gd .dn {{ font-family:'Cal Sans'; font-size:10pt; color:var(--navy); }}
.gh {{ font-weight:700; color:var(--mut); font-size:8pt; text-align:center; }}
.chip {{ border-radius:4px; padding:2px 4px; margin:3px 0; color:#fff; line-height:1.25; }}
.chip.ep {{ background:#fff; color:var(--navy); border:1.5px solid var(--navy); }}
.leg {{ display:flex; gap:14px; flex-wrap:wrap; font-size:8.2pt; margin:6px 0; }} .leg i {{ display:inline-block; width:11px; height:11px; border-radius:3px; margin-right:5px; vertical-align:-1px; }}
.evo td {{ padding:3px 6px; }} .evo td:nth-child(n+3), .evo th:nth-child(n+3) {{ text-align:right; width:12%; }}
.gloss dt {{ font-weight:700; color:var(--navy); }} .gloss dd {{ margin:0 0 5px; }}
.toc a {{ display:flex; justify-content:space-between; border-bottom:1px dotted #C9D5EA; padding:3px 0; color:var(--ink); }}
</style></head><body>''')

# capa
A(f'''<div class="capa"><div class="bar"></div>
<div class="wm">Bombordo<br>e Boreste</div>
<div class="t">Resultados de setembro · Estratégia de outubro</div>
<div class="d">Instagram, YouTube, TikTok e Spotify<br>Período analisado: 02/09 a 30/09/2026<br>Entregue em 30/09/2026</div>
<div class="by"><img src="{logo_w}" alt="DL Portos"></div></div>''')

# resumo
achados = [
    f'<b>O podcast chegou a {IGP["reach"]} contas no Instagram</b> e ganhou <b>{IGP["follows"]} seguidores</b> no perfil do Daniel. {fmt(IGP["nonf"],1).replace(",0","")}% das views vieram de quem ainda não seguia: o conteúdo está saindo da bolha.',
    f'<b>O motor foi o vídeo da Inpasa</b> (24/09): {fmt(int(inp["views"]))} views e {inp["seg"]} seguidores. Isso também é o risco: sem ele, o post típico tem cerca de {fmt(med("views", rest))} views.',
    f'<b>Quem visita o perfil segue, mas não vai ao podcast:</b> {IGP["visits"]} visitas viraram {IGP["follows"]} seguidores e só {IGP["clicks"]} cliques no Linktree.',
    f'<b>No YouTube, o episódio completo é que traz inscrito:</b> {sum(int(r["inscritos"] or 0) for r in eps)} dos {YT["subs"]} novos inscritos vieram dos episódios.',
    f'<b>TikTok e Spotify ainda não encontraram o seu papel:</b> {fmt(TT_PAINEL)} views no TikTok com +1 seguidor; 19 plays no Spotify somando os 4 episódios.']
decisoes = [f'<b>Repetir a fórmula da Inpasa:</b> os {TOPO} cortes de alcance do mês abrem com um número ou fato surpreendente do setor.',
            '<b>Um só destino:</b> todo corte leva ao episódio pelo Linktree, com link nos stories todo dia.',
            '<b>Episódio toda segunda às 19h</b> (YouTube + Spotify), com a chamada entrando às 19h15, quando o link já funciona.',
            f'<b>Usar o acervo:</b> {len(ACERVO)} cortes de fatos e histórias dos EP 01 e EP 02 completam a semana.',
            '<b>Testar antes de fixar:</b> horário (12h x 19h), TikTok adaptado e título de episódio.']
A('<section><div class="kick">Resumo executivo</div><h2>Setembro em uma página</h2><div class="rule"></div>')
A(f'''<div class="kpis"><div class="kpi"><b>{fmt(IGP['views'])}</b><span>views no Instagram</span></div>
<div class="kpi"><b>+{IGP['follows']}</b><span>seguidores no Instagram</span></div>
<div class="kpi"><b>+{YT['subs']}</b><span>inscritos no YouTube</span></div>
<div class="kpi"><b>{fmt(TT_PAINEL)}</b><span>views no TikTok</span></div></div>''')
A('<div class="two"><div><h3>O que aconteceu</h3><ol>' + ''.join(f'<li>{x}</li>' for x in achados) + '</ol></div><div><h3>O que muda em outubro</h3><ol>' + ''.join(f'<li>{x}</li>' for x in decisoes) + '</ol></div></div>')
A('''<div class="box"><div class="toc"><b>Neste relatório</b>
<a href="#evo"><span>Evolução mês a mês e fechamento do plano</span><span>3</span></a><a href="#ig"><span>Instagram</span><span>4</span></a><a href="#yt"><span>YouTube</span><span>5</span></a><a href="#tt"><span>TikTok e Spotify</span><span>6</span></a>
<a href="#funil"><span>Funil e papel de cada rede</span><span>7</span></a><a href="#estr"><span>Estratégia de outubro</span><span>8</span></a><a href="#cal"><span>Calendário de outubro</span><span>9</span></a>
<a href="#metas"><span>Metas e testes</span><span>10</span></a><a href="#passos"><span>Aprendizados, próximos passos e glossário</span><span>11</span></a><a href="#anexo"><span>Anexo</span><span>12</span></a></div></div>''')
A('<div class="box blue"><b>Contexto do mês</b><ul>' + ''.join(f'<li>{x}</li>' for x in hist['meses']['2026-09']['contexto']) + '</ul></div>')
A('<p class="note">Números da conta do Instagram: painel do Meta Business Suite (02–29/09).</p></section>')
A(f'''<section id="evo"><div class="kick">Evolução</div><h2>A série mês a mês</h2><div class="rule"></div>
<p>Setembro é o <b>mês base</b>: o ponto de partida. A partir de outubro, cada relatório acrescenta uma coluna a este quadro, sempre com as mesmas linhas — inclusive o volume de publicações, para que qualquer mudança de ritmo fique registrada.</p>
{evo_table()}
<h3>Fechamento do plano anterior</h3>
<div class="box">Setembro não tinha plano anterior. A partir do relatório de outubro, esta parte mostra: <b>planejado x publicado</b> (22 cortes e 4 episódios previstos), <b>metas atingidas ou não</b> (quadro da página de metas) e <b>o resultado de cada teste com a decisão tomada</b> (T1 a T4).</div></section>''')

# Instagram
def rk(rs, key, n=5, rev=True): return sorted([r for r in rs if int(r['alcance']) >= 500], key=lambda r: (float(r[key] or 0) if key != 'seg_mil_alc' else r[key]), reverse=rev)[:n]
def igline(r, key):
    src, curto = ig_thumb(r); t = ig_time(r['data'])
    val = pctf(r['comp_alc'], 2) if key == 'comp_alc' else fmt(r['seg_mil_alc'], 1)
    return [img(thumb(src)), link(r['link'], E(curto)), t.strftime('%d/%m'), f'<span class="n">{fmt(int(r["views"]))}</span>', f'<span class="n">{fmt(int(r["alcance"]))}</span>', f'<b>{val}</b>']
A(f'''<section id="ig"><div class="kick">Instagram · @danieldematospereira</div><h2>O mês em que o perfil saiu da bolha</h2><div class="rule"></div>
<div class="kpis"><div class="kpi"><b>{IGP['reach']}</b><span>contas alcançadas</span></div><div class="kpi"><b>{fmt(IGP['nonf'],1)}%</b><span>das views de não seguidores</span></div>
<div class="kpi"><b>{IGP['inter']}</b><span>interações com o conteúdo</span></div><div class="kpi"><b>{IGP['follows']}</b><span>seguidores ({IGP['unf']} deixaram de seguir)</span></div></div>
<h3>Views por dia</h3>{svg_daily()}
<p class="note">Fonte: série diária exportada do Meta (31/08 a 27/09). O vídeo foi publicado em 24/09 e as views continuaram crescendo nos três dias seguintes.</p>
<div class="two"><div><h3>Os que mais foram compartilhados</h3>{table(['','Post','Data','Views','Alcance','Compart.'], [igline(r,'comp_alc') for r in rk(ig,'comp_alc')])}</div>
<div><h3>Os que mais trouxeram seguidores</h3>{table(['','Post','Data','Views','Alcance','Seg./mil'], [igline(r,'seg_mil_alc') for r in rk(ig,'seg_mil_alc')])}</div></div>
<p class="note">Compartilhamento = quantos a cada 100 alcançados enviaram o post; Seg./mil = novos seguidores a cada mil contas alcançadas. Posts com menos de 500 de alcance ficam fora do ranking (amostra pequena). Toque no título para abrir o post.</p>
<div class="two"><div class="box blue"><b>O que os melhores têm em comum</b><ul><li>Abrem com uma <b>afirmação forte ou um fato de escala</b> sobre o setor.</li><li>Reels de 40 a 55 segundos.</li><li>Interessam a quem não é do porto (agro, consumo, economia).</li></ul><p class="note" style="margin:4px 0 0">Público: 25–44 anos são 75% (56% homens); São Luís concentra 37,9%.</p></div>
<div class="box"><b>Por outro lado</b><ul><li>Sem a Inpasa, o post típico teve {fmt(med('views', rest))} views e os outros 22 posts somaram {sum(int(r['seg']) for r in rest)} seguidores.</li><li>Reels alcançaram mais que carrosséis (post típico: {fmt(med('views', reels))} x {fmt(med('views', car))} views); carrosséis foram mais salvos — são só {len(car)}, então é indício.</li></ul></div></div>
</section>''')

# YouTube
def ytline(r, wide=True):
    return [img(thumb(P('thumbs', f"yt_{r['id']}.jpg"), 60) if os.path.exists(P('thumbs', f"yt_{r['id']}.jpg")) else '', 'th wide'), link('https://youtu.be/' + r['id'], E(ident(r['titulo'])[1])),
            yt_date(r['publicado']).strftime('%d/%m'), f'<span class="n">{fmt(int(r["views"]))}</span>', (pctf(r['pct_assistido'], 0)) if r['pct_assistido'] else '—',
            fmt(float(r['horas'] or 0), 1), f'<b>{r["inscritos"] or "0"}</b>']
A(f'''<section id="yt"><div class="kick">YouTube · Bombordo e Boreste</div><h2>O episódio completo é quem fideliza</h2><div class="rule"></div>
<div class="kpis"><div class="kpi"><b>{fmt(YT['views'])}</b><span>views</span></div><div class="kpi"><b>{fmt(YT['horas'],1)} h</b><span>assistidas</span></div>
<div class="kpi"><b>+{YT['subs']}</b><span>inscritos ({YT['gan']} ganhos, {YT['lost']} perdido)</span></div><div class="kpi"><b>{fmt(YT['ctr'],2)}%</b><span>de cliques na miniatura</span></div></div>
<h3>Episódios</h3>{table(['','Episódio','Publicado','Views','Assistido','Horas','Inscritos'], [ytline(r) for r in sorted(eps, key=lambda r: -int(r['inscritos'] or 0))])}
<h3>Shorts com mais views</h3>{table(['','Short','Publicado','Views','Assistido','Horas','Inscritos'], [ytline(r) for r in sorted(shorts, key=lambda r: -int(r['views']))[:5]])}
<div class="two"><div class="box blue"><b>O que funcionou</b><ul><li>O EP 01 (Dayvid) trouxe 14 inscritos e 20,8 horas assistidas.</li><li>O Short da Inpasa foi assistido em 80% da duração, em média — a melhor retenção do canal.</li></ul></div>
<div class="box"><b>O que melhorar</b><ul><li>Nos episódios, o espectador assiste de 9% a 21% do total: os primeiros minutos precisam segurar mais.</li><li>O vídeo dos drones apareceu 2.347 vezes e teve 0,55% de cliques: título e miniatura não chamaram.</li><li>Shorts não trouxeram inscritos: o papel deles é levar ao episódio.</li></ul></div></div>
<p class="note">Fonte: YouTube Studio, 02–30/09/2026. Vídeos publicados antes de 2026 ficam fora da análise.</p></section>''')

# TikTok + Spotify
def ttline(r):
    curto = ident(r['titulo'])[1]; src = P('thumbs', f"tt_{r['video']}.jpg")
    if not os.path.exists(src): src = ident(r['titulo'])[0]
    return [img(thumb(src)), link(tt_links.get(r['video'], 'https://www.tiktok.com/@danieldoporto_'), E(curto)), tt_date(r['publicado']).strftime('%d/%m'), f'<span class="n">{fmt(int(r["views"]))}</span>', r['likes'], r['shares']]
tts = sorted(tt, key=lambda r: -int(r['views']))
A(f'''<section id="tt"><div class="kick">TikTok · @danieldoporto</div><h2>Alcance sem conversão</h2><div class="rule"></div>
<div class="kpis"><div class="kpi"><b>{fmt(TT_PAINEL)}</b><span>views em setembro (painel)</span></div><div class="kpi"><b>{fmt(tt_med)}</b><span>views no vídeo típico (15 vídeos)</span></div>
<div class="kpi"><b>12</b><span>visitas ao perfil</span></div><div class="kpi"><b>20</b><span>seguidores (+1 no mês)</span></div></div>
<div class="two"><div><h3>Mais vistos</h3>{table(['','Vídeo','Data','Views','Curt.','Comp.'], [ttline(r) for r in tts[:5]])}</div><div><h3>Menos vistos</h3>{table(['','Vídeo','Data','Views','Curt.','Comp.'], [ttline(r) for r in tts[-5:]])}</div></div>
<div class="box blue">Os vídeos chegam a quem não segue (3.674 espectadores novos contra 812 que voltaram), mas quase ninguém visita o perfil e não houve comentários. A Inpasa, que explodiu no Instagram, fez 410 views aqui: o tema funciona, o que falta é adaptar (texto na tela logo no início, legenda curta, sem mandar para outras contas). {HYP}</div>
<p class="note">As 5.428 views são o total do painel do TikTok em setembro; a soma dos 15 vídeos da lista exportada dá {fmt(tt_soma)}. Usamos o total do painel como número da conta. Sem dados de público nem de horário (arquivos vieram vazios).</p>
<h2 style="margin-top:16px">Spotify</h2><div class="rule"></div>
{table(['Episódio','Publicado','Plays e downloads (30 primeiros dias)'], [['EP 00 · Silvio Lúcio','24/08','<span class="n">7</span>'],['EP 01 · Dayvid Guterres','16/09','<span class="n">2</span>'],['EP 02 · Dannyel','21/09','<span class="n">1</span>'],['EP 03 · Juliana e Larissa','28/09','<span class="n">9</span>']])}
<p class="note">Os episódios de setembro ainda não completaram 30 dias (o EP 03 tinha 2 dias). Total de 19 plays: hoje o áudio não é divulgado.</p></section>''')

# funil e papel
A(f'''<section id="funil"><div class="kick">Leitura cruzada</div><h2>Onde o público entra e onde ele se perde</h2><div class="rule"></div>
<h3>Funil do Instagram (02–29/09)</h3>{svg_funnel()}
<div class="box warn"><b>O vazamento está no último passo.</b> A bio convence (63% de quem visita passa a seguir), mas só 11 pessoas foram ao Linktree. Os cortes não pedem esse passo de forma consistente, o link não aparece nos stories e metade das 92 conversas do direct ficou sem resposta. {HYP}</div>
<h3>O papel de cada rede</h3>{table(['Rede','Hoje','Em outubro','Por quê'], [
 ['Instagram','Descoberta (um viral)','Descoberta + ponte para o Linktree','87,5% das views de não seguidores; 754 seguidores'],
 ['YouTube','Aprofundamento','Onde o episódio acontece','23 dos 30 inscritos vieram dos episódios; Shorts, nenhum'],
 ['TikTok','Sem papel definido','Teste de descoberta por 4 semanas','5.428 views, 12 visitas, +1 seguidor'],
 ['Spotify','Arquivo','Arquivo, com link em todo episódio','19 plays nos 4 episódios']])}
<h3>O que funcionou em mais de uma rede</h3><ul>
<li><b>Inpasa:</b> 1º no Instagram, 1º em retenção no YouTube (80% assistido) e 4º no TikTok.</li>
<li><b>"A carga dita o mercado":</b> o post mais compartilhado do Instagram entre os de maior alcance e o mais visto do TikTok (502).</li>
<li><b>Histórias de carreira</b> engajam quem já segue, mas alcançam pouco fora.</li></ul>
<p class="note">Limites desta análise: sem mês anterior comparável (as contas começaram em agosto/setembro); métricas por post acumuladas até 30/09; sem métricas individuais de stories; sem cliques do Linktree por origem.</p></section>''')

# estratégia
mix = lambda f: f'{cnt(lambda c: c["funil"] == f)} de {N} ({cnt(lambda c: c["funil"] == f)/N*100:.0f}%)'
A(f'''<section id="estr"><div class="kick">Estratégia de outubro</div><h2>Crescer alcance e levar ao episódio</h2><div class="rule"></div>
{table(['','O quê','Por quê'], [
 ['<b>Manter</b>','Reels de 40–55 s como formato principal',f'Post típico de reel: {fmt(med("views", reels))} views, contra {fmt(med("views", car))} dos carrosséis'],
 ['<b>Manter</b>','Episódio completo toda semana no YouTube','23 dos 30 inscritos vieram dos episódios (EP 01: 14)'],
 ['<b>Manter</b>','Número ou fato forte na primeira frase','Mais compartilhados com alcance acima de mil: "carga dita o mercado" 3,18%, Inpasa 2,97%, primeira atracação 2,19%'],
 ['<b>Parar</b>','Mandar para outras contas no fim do vídeo','Dispersa o clique: 11 cliques no Linktree em 1,2 mil visitas'],
 ['<b>Parar</b>','Copiar a legenda do Instagram no TikTok','0 comentários e 12 visitas ao perfil em 5.428 views'],
 ['<b>Testar</b>','Horário, TikTok adaptado e título do episódio','Um mês não basta para fixar regra (página de metas e testes)']])}
<h3>Pilares e etapas</h3>{table(['Pilar','Para quê','Etapa','Cortes em outubro'], [
 [f'<i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:{PILAR["Porto em números"][1]}"></i> <b>Porto em números</b>','Alcance e compartilhamento fora da bolha','Topo',f'{NUM}'],
 [f'<i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:{PILAR["Bastidores da operação"][1]}"></i> <b>Bastidores da operação</b>','Curiosidade sobre como o porto funciona','Topo',f'{BAST}'],
 [f'<i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:{PILAR["Carreira no porto"][1]}"></i> <b>Carreira no porto</b>','Identificação: quem assiste quer seguir','Meio',f'{CARR}'],
 [f'<i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:{PILAR["Episódio da semana"][1]}"></i> <b>Episódio da semana</b>','Levar ao episódio completo','Fundo',f'{FUNDO} chamadas + 4 episódios']])}
<p><b>Mix do mês:</b> topo {mix('Topo')}, meio {mix('Meio')}, fundo {mix('Fundo')}. Todos os cortes de topo abrem com número ou fato surpreendente.</p>
<h3>Semana-tipo</h3>{table(['Segunda','Terça','Quarta','Quinta','Sexta','Todo dia'], [[
 '19h: episódio no YouTube e no Spotify<br>19h15: corte de chamada','Corte com o fato do episódio','Corte do acervo','Corte de carreira do episódio','Corte do acervo','Stories com o corte do dia e link do Linktree']])}
<div class="box"><b>Regras de todo corte</b> (valem para as 3 redes; não se repetem no calendário)<ul>
<li><b>Instagram:</b> {CTA['Instagram']}.</li><li><b>TikTok:</b> {CTA['TikTok']}.</li><li><b>YouTube Shorts:</b> {CTA['YouTube Shorts']}.</li>
<li><b>Sucesso no Instagram:</b> topo = views ≥ 1.500 e compartilhamentos ≥ 1% do alcance; meio = salvamentos ≥ 0,3% do alcance ou ≥ 5 seguidores; fundo = ≥ 2 cliques no link no dia.</li></ul></div>
<p class="note">Os cortes dos EP 04 a 07 seguem regras fixas por tipo porque os convidados ainda não estão confirmados. Trechos, ganchos e roteiros de cada corte estão na planilha de produção (Calendario_BombordoEBoreste_2026-10.xlsx).</p></section>''')

# calendário grade
bycal = {}
for c in cortes: bycal.setdefault(c['data'], []).append(c)
epd = {d: n for d, n in episodios}
cells = ''.join(f'<div class="gh">{x}</div>' for x in ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'])
start = dt.date(2026, 9, 28)
for i in range(35):
    d = start + dt.timedelta(days=i); off = d.month != 10
    inner = f'<div class="dn">{d.day}</div>'
    if d in epd: inner += f'<div class="chip ep">19h · <b>EP {epd[d]:02d}</b> no YouTube e Spotify</div>'
    for c in sorted(bycal.get(d, []), key=lambda c: c['hora']):
        inner += f'<div class="chip" style="background:{PILAR[c["p"]][1]}">{c["hora"].replace(":00", "h").replace(":", "h")} · {E(c["curto"])}</div>'
    if d == dt.date(2026, 10, 12): inner += '<div class="note" style="margin:2px 0">feriado</div>'
    cells += f'<div class="gd{" off" if off else ""}">{inner}</div>'
A(f'''<section id="cal" class="land"><div class="kick">Calendário</div><h2>Outubro de 2026</h2><div class="rule"></div>
<div class="leg">''' + ''.join(f'<span><i style="background:{v[1]}"></i>{k} ({v[0].lower()})</span>' for k, v in PILAR.items()) + f'''<span><i style="background:#fff;border:1.5px solid #0B1A33"></i>Episódio completo</span></div>
<p class="note" style="margin:0 0 5px;color:#C0392B"><b>Plano B do EP 04:</b> se o episódio não estiver gravado até 02/10, a semana de 05/10 usa 3 cortes do acervo (prontos na planilha) e os episódios passam uma semana para frente.</p>
<div class="grid">{cells}</div>
<p class="note">Cada corte sai no mesmo dia no Instagram (Reels), no TikTok e no YouTube Shorts. Stories todos os dias. Horário dos cortes em teste: 12h nas semanas de 01, 05 e 12/10; 19h nas semanas de 19 e 26/10 (o feriado de 12/10 não entra no bloco das 19h).</p></section>''')

# metas e testes
metas = [('Instagram', 'Views no post típico (reel)', med('views', reels), 1500, lambda v: fmt(v)),
         ('Instagram', 'Novos seguidores no mês', 55, 300, lambda v: fmt(v) + ' sem o viral'),
         ('Instagram', 'Cliques no Linktree', 11, 40, fmt),
         ('YouTube', 'Novos inscritos', 30, 50, fmt),
         ('YouTube', 'Cliques na miniatura (CTR)', 2.59, 3.5, lambda v: fmt(v, 2) + '%'),
         ('YouTube', 'Views no Short típico', st.median(int(r['views']) for r in shorts), 100, fmt),
         ('TikTok', 'Views no vídeo típico', tt_med, 400, fmt),
         ('TikTok', 'Seguidores', 20, 60, fmt),
         ('Spotify', 'Plays nos 30 primeiros dias (soma dos episódios)', 19, 40, fmt)]
A('<section id="metas"><div class="kick">Metas e testes</div><h2>Onde queremos chegar em outubro</h2><div class="rule"></div>')
A(table(['Rede', 'Indicador', 'Setembro', 'Meta de outubro', 'Realizado em outubro'],
        [[r, i, f'<span class="n">{f(b)}</span>', f'<b>{f(m) if "sem" not in f(m) else fmt(m)}</b>', '<span class="note">no próximo relatório</span>'] for r, i, b, m, f in metas]))
A('<p class="note">Este quadro se repete todo mês: a coluna "Realizado" é preenchida no relatório de outubro, com a indicação de meta atingida ou não. Metas calculadas sem contar com outro viral.</p>')
A('<h3>Testes do mês</h3>' + table(['Teste', 'O que queremos descobrir', 'Como medir', 'Quando decidir'], [
 ['<b>T1 · Fórmula Inpasa</b>', f'Cortes que abrem com número/fato ({TOPO}) alcançam mais que os de carreira ({MEIO})?', 'Views e compartilhamentos por alcance no Instagram, topo x meio', '31/10'],
 ['<b>T2 · Horário</b>', 'Cortes às 12h rendem mais que às 19h? (hoje, o 12h vem de um único post)', 'Views nas primeiras 24 h: semanas de 12h x semanas de 19h', '31/10'],
 ['<b>T3 · TikTok adaptado</b>', 'Texto na tela no 1º segundo e legenda curta fazem o vídeo típico passar de 400 views?', 'Views no vídeo típico (hoje 256) e visitas ao perfil (hoje 12)', '25/10 — se não passar, TikTok vira só repost'],
 ['<b>T4 · Título do episódio</b>', 'Título com número/fato tem mais cliques que "Carreira com X"?', 'Cliques na miniatura nas primeiras 72 h (hoje 2,59%)', 'Após o EP 05 (12/10) e no fim do mês']]) + '</section>')

# próximos passos + glossário
A(f'''<section id="passos"><div class="kick">Aprendizados e próximos passos</div><h2>O que já sabemos e o que precisa acontecer</h2><div class="rule"></div>
<div class="box blue"><b>Aprendizados acumulados</b> — lista que só cresce; com o tempo vira o manual do perfil<ol>{''.join(f'<li>{x} <span class="note">(set/26)</span></li>' for m in MESES for x in hist['meses'][m]['aprendizados'])}</ol></div>
{table(['O quê','Quem','Até'], [
 ['Confirmar convidados e datas dos EP 04 a 07 — se o EP 04 não estiver gravado, ativar o plano B da semana de 05/10','<b>Cliente</b>','02/10'],
 ['Responder as mensagens do direct em até 24 h (hoje metade fica sem resposta)','<b>Cliente / Daniel</b>','contínuo'],
 ['Colocar o link do Linktree nos stories todos os dias','Social media','a partir de 01/10'],
 ['Tirar dos cortes as chamadas para outras contas; CTA único para o episódio','Social media e edição','01/10'],
 ['Manter a conversa livre, sem roteiro, levando 2 ou 3 perguntas-âncora que puxem números, histórias e opiniões — o acervo de cortes acaba em outubro','<b>Cliente</b> e social media','antes da gravação do EP 08'],
 ['Ponto de controle dos testes T2 e T3','Social media','16/10'],
 ['Coletar o painel de Benchmarking do Business Suite para comparar com contas parecidas','Social media','31/10'],
 ['Relatório de outubro com o quadro "meta x realizado"','Social media','05/11']])}
<h3>Glossário</h3><dl class="gloss" style="columns:2;column-gap:18px">
<dt>Alcance</dt><dd>Quantas contas diferentes viram o conteúdo (uma pessoa conta uma vez).</dd>
<dt>Views</dt><dd>Quantas vezes o conteúdo foi exibido (a mesma pessoa pode contar várias vezes).</dd>
<dt>Compartilhamento por alcance</dt><dd>De cada 100 pessoas alcançadas, quantas enviaram o post para alguém. É o melhor sinal de que o conteúdo vai viajar.</dd>
<dt>Post típico (mediana)</dt><dd>O post do meio da lista quando ordenamos por views. Não é distorcido por um viral, ao contrário da média.</dd>
<dt>Cliques na miniatura (CTR)</dt><dd>De cada 100 vezes que o YouTube mostrou o vídeo, quantas pessoas clicaram.</dd>
<dt>Assistido (retenção)</dt><dd>Quanto do vídeo, em média, as pessoas assistiram.</dd>
<dt>Topo, meio e fundo</dt><dd>Topo atrai quem não conhece; meio faz a pessoa se identificar e seguir; fundo leva à ação (assistir ao episódio).</dd>
<dt>Viral / ponto fora da curva</dt><dd>Um post muito acima do normal da conta, como a Inpasa.</dd></dl></section>''')

# anexo
igrow = lambda r: [link(r['link'], E(ig_thumb(r)[1])), ig_time(r['data']).strftime('%d/%m %Hh'), 'Reel' if 'reel' in r['tipo'] else 'Carrossel',
                   f'<span class="n">{fmt(int(r["views"]))}</span>', f'<span class="n">{fmt(int(r["alcance"]))}</span>', pctf(r['eng_alc'], 1), pctf(r['comp_alc'], 2), r['seg']]
A('<section id="anexo"><div class="kick">Anexo</div><h2>Tabelas completas</h2><div class="rule"></div><h3>Instagram — posts do perfil (métricas até 30/09)</h3>')
A(table(['Post', 'Data', 'Formato', 'Views', 'Alcance', 'Engaj.', 'Compart.', 'Seg.'], [igrow(r) for r in sorted(ig, key=lambda r: ig_time(r['data']))]))
A('<p class="note">Engaj. = curtidas + comentários + salvamentos + compartilhamentos, dividido pelo alcance. Posts de outras contas (colaborações) ficam fora porque vieram sem alcance no export.</p>')
A('<h3>YouTube — vídeos de 2026 (02–30/09)</h3>' + table(['Vídeo', 'Formato', 'Publicado', 'Views', 'Assistido', 'Horas', 'Inscritos'], [ytline(r)[1:2] + [r['formato']] + ytline(r)[2:] for r in sorted(yt, key=lambda r: -int(r['views']))]))
A('<h3>TikTok — vídeos de setembro</h3>' + table(['Vídeo', 'Publicado', 'Views', 'Curt.', 'Comp.'], [ttline(r)[1:] for r in tts]) + '</section></body></html>')
open(P('relatorio_v2.html'), 'w', encoding='utf-8').write('\n'.join(H)); print('html v2 ok')
