"""Compara dois measure.csv (antes/depois) e imprime a dispersão entre fotos e as checagens.
uso: python3 compare.py antes/measure.csv depois/measure.csv"""
import csv,sys,numpy as np
b={r['file']:r for r in csv.DictReader(open(sys.argv[1]))}
a={r['file']:r for r in csv.DictReader(open(sys.argv[2]))}
line,tol=123,6
def v(d,c,ks): return np.array([float(d[k][c]) for k in ks if d[k].get(c)])
spk=[k for k in b if b[k]['faces']=='1']
allk=list(b)
print(f"{'medida':34} {'antes':>22} {'depois':>22}")
for lab,c,ks in [('ângulo da pele (todas)','skin_angle',allk),('ângulo da pele (palestrante)','skin_angle',spk),
                 ('L* da pele (palestrante)','skin_L',spk),('parede R/G','neutral_rg',allk),('parede B/G','neutral_bg',allk)]:
    x,y=v(b,c,ks),v(a,c,ks)
    print(f"{lab:34} {x.min():6.2f}–{x.max():<6.2f} σ{x.std():5.2f}  {y.min():6.2f}–{y.max():<6.2f} σ{y.std():5.2f}")
for lab,d in [('antes',b),('depois',a)]:
    ang=v(d,'skin_angle',allk); print(lab,'fotos com pele fora da faixa 117–129°:',int(((ang<line-tol)|(ang>line+tol)).sum()),
      '| com estouro >1%:',int((v(d,'clip%',allk)>1).sum()),'| preto lavado (L*0.5% >5):',int((v(d,'black',allk)>5).sum()))
