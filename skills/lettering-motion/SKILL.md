---
name: lettering-motion
description: Anime legendas, letterings e cards com curvas de easing nomeadas e entrada por slide-direcional + fade, em vez de só fade/scale-pop estático. Use ao criar ou revisar qualquer texto/card que entra na tela (legenda, headline, lettering, CTA) em qualquer skill de corte, e para decidir se o efeito pedido precisa de Pillow (padrão), SVG ou um motor tipo Remotion.
---

# Lettering Motion

Toda animação de texto/card do CIBO usa `scripts/easing.py` (curvas nomeadas + `entrance()` para slide-direcional com fade) em vez de reimplementar easing local em cada renderer. Isso existia de forma duplicada e incompleta antes: `render_caps.py` e `render_lettering.py` cada um tinha sua própria cópia de `ease_out_cubic`/`ease_out_back`, e nenhum tinha um componente de translação (slide) — só fade e scale-pop.

## Uso

```python
from easing import entrance, ease_out_back, ease_out_bounce

dx, dy, alpha = entrance(progress, direction='up', distance=40)  # slide de baixo pra cima + fade, desacelerando
paste(canvas, tile, final_x + dx, final_y + dy, alpha=alpha)
```

`direction` aceita `up`, `down`, `left` ou `right` — o elemento nasce deslocado `distance` px nessa direção a partir da posição final e converge enquanto ganha opacidade, com a curva de easing controlando a desaceleração (`ease_out_cubic` por padrão; troque por `ease_out_back` para um leve overshoot, ou `ease_out_bounce` para quicar). Ver `references/animation-catalog.md` para os presets nomeados e quando usar cada direção.

## Antes de pedir um efeito novo: qual ferramenta usar

Não use SVG ou Remotion por padrão — comece sempre pelo Pillow + `easing.py`. Suba de ferramenta só quando o efeito concreto exigir. Ver `references/animation-catalog.md` para a árvore de decisão completa; resumo:

1. **Pillow + `easing.py` (padrão, ~100% dos casos hoje).** Slide de qualquer direção, fade, scale-pop, bounce. Zero dependência nova, roda no pipe de frames que já existe.
2. **SVG (`cairosvg`) — só quando o efeito é vetorial por natureza.** Sublinhado sendo desenhado (`stroke-dashoffset`), forma fazendo morph, ícone traçando contorno. Rasteriza um SVG por frame e entra no mesmo pipe de PNG; não vale a pena para slide/fade simples porque Pillow já faz isso mais rápido.
3. **Remotion (React + Chromium headless) — só quando o efeito exige física de mola real ou composição multi-camada complexa** que easing manual não reproduz bem (overshoot/assentamento natural tipo iOS, múltiplos elementos reagindo uns aos outros). É um pipeline paralelo (Node.js + Chromium), decisão de arquitetura maior — não adotar por um efeito isolado; só justificado se isso virar um padrão recorrente em vários jobs.

## Onde já está integrado

`scripts/easing.py` está copiado (mesma convenção de `tools.py`, duplicado por skill) em: `bombordo-boreste`, `autismo-cast`, `katia`, `podcast-reels` (`render_caps.py`, entrada da legenda) e `content-hub` (`render_lettering.py`, entrada do card). Ao portar para uma skill nova, copie o arquivo — não reimplemente easing local de novo.
