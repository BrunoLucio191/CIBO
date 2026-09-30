#!/usr/bin/env python3
"""Calendário de conteúdo -> planilha de produção (uma linha por conteúdo).

Uso: python3 calendario_xlsx.py calendario.json calendario.xlsx
calendario.json: lista de objetos com as chaves de COLS (as de produção podem faltar), ou
{"rows": [...], "regras": [["Regra", "Valor"], ...]} — as regras que se repetem (CTA padrão por
plataforma, critério de sucesso por tipo, coleta) vão numa aba própria, não em cada linha.
Requer openpyxl (pip install -r requirements.txt).
"""
import json, sys
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

COLS = [('data', 'Data', 12), ('horario', 'Horário', 9), ('plataforma', 'Plataforma', 14), ('formato', 'Formato', 14),
        ('pilar', 'Pilar', 18), ('funil', 'Etapa do funil', 12), ('tema', 'Tema', 32),
        ('gancho', 'Gancho (1ª frase / 3s)', 40), ('estrutura', 'Estrutura do roteiro / slides', 60),
        ('cta', 'CTA', 28), ('metrica', 'Métrica de sucesso', 26), ('trecho', 'Trecho / origem', 24), ('origem', 'Reaproveitado de', 16),
        ('status', 'Status', 12), ('responsavel', 'Responsável', 14), ('link', 'Link', 24)]

data = json.load(open(sys.argv[1], encoding='utf-8'))
rows = data['rows'] if isinstance(data, dict) else data
regras = data.get('regras', []) if isinstance(data, dict) else []
COLS = [c for c in COLS if any(c[0] in r for r in rows) or c[0] in ('status', 'responsavel', 'link')]
wb = Workbook(); ws = wb.active; ws.title = 'Calendário'
ws.append([c[1] for c in COLS])
for r in rows:
    ws.append(['\n'.join(r[k]) if isinstance(r.get(k), list) else r.get(k, '') for k, _, _ in COLS])
head = PatternFill('solid', fgColor='1F2A44')
for i, (_, _, w) in enumerate(COLS, 1):
    ws.column_dimensions[get_column_letter(i)].width = w
    c = ws.cell(1, i); c.font = Font(bold=True, color='FFFFFF'); c.fill = head
    c.alignment = Alignment(vertical='center', wrap_text=True)
for row in ws.iter_rows(min_row=2):
    for c in row: c.alignment = Alignment(vertical='top', wrap_text=True)
ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions
if regras:
    wr = wb.create_sheet('Regras'); wr.append(['Regra', 'Valor'])
    for r in regras: wr.append(r)
    wr.column_dimensions['A'].width = 34; wr.column_dimensions['B'].width = 110
    for c in wr[1]: c.font = Font(bold=True, color='FFFFFF'); c.fill = head
    for row in wr.iter_rows(min_row=2):
        for c in row: c.alignment = Alignment(vertical='top', wrap_text=True)
wb.save(sys.argv[2]); print(f'{len(rows)} conteúdos -> {sys.argv[2]}')
