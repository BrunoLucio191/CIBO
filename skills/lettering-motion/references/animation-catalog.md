# Catálogo de animações e árvore de decisão

## Presets de entrada (Pillow + `easing.py`)

| Preset | `direction` | `ease` | Quando usar |
|---|---|---|---|
| `slide_up_fade` | `up` | `ease_out_cubic` | Padrão para legenda/lettering entrando por baixo, desacelerando até a posição final |
| `slide_down_fade` | `down` | `ease_out_cubic` | Headline/título entrando por cima |
| `slide_left_fade` / `slide_right_fade` | `left` / `right` | `ease_out_cubic` | Card lateral, popup de canto, comparação lado a lado |
| `pop_back` | — (sem slide, só `scale` de 0.74→1.0) | `ease_out_back` | Ênfase pontual sem deslocamento — já era o padrão antigo, continua válido quando não há necessidade de direção |
| `bounce_in` | qualquer | `ease_out_bounce` | Uso raro — CTA/gancho que precisa de energia extra; não usar em legenda corrida (cansa) |

Distância padrão: 30–50 px para legenda/lettering em 1080×1920 (proporcional ao tamanho do elemento; maior que isso lê como exagero na tela pequena de um celular). Duração padrão: 5–8 frames a 30 fps (~180–260 ms) — mais rápido que isso não dá tempo de perceber a direção, mais lento que isso atrasa a leitura.

## Combinando slide com o que já existe

`scale` (pop-in) e `entrance()` (slide+fade) não são mutuamente exclusivos: dá pra aplicar os dois na mesma tile (slide traz a posição, scale dá o peso de entrada). Mas não empilhe mais de dois efeitos no mesmo elemento — legenda que desliza, aparece, cresce e ainda balança compete com a leitura da fala, que é sempre prioridade (ver hierarquia editorial em `video-delivery-safety-check/references/final-checklist.md`).

## Árvore de decisão: Pillow × SVG × Remotion

```
O efeito é slide, fade, scale-pop ou bounce de um elemento já rasterizado (texto/PNG)?
├── Sim → Pillow + easing.py. Fim.
└── Não, precisa desenhar/morphar uma forma vetorial (traço, ícone, contorno)?
    ├── Sim → SVG por frame + cairosvg, mesmo pipe de PNG. Fim.
    └── Não, precisa de física de mola real ou múltiplos elementos
        reagindo uns aos outros em composição complexa?
        ├── Não → volte para Pillow + easing.py; provavelmente falta só
        │         uma curva nova em easing.py, não uma ferramenta nova.
        └── Sim, e isso é um padrão recorrente (não um efeito isolado)
            → avaliar Remotion como decisão de arquitetura à parte,
              não como resposta a um único job.
```

## Quando NÃO usar SVG ou Remotion

- Nunca troque de ferramenta só porque "parece mais profissional" — o teste é sempre "esse efeito específico é impossível ou visivelmente pior em Pillow?".
- SVG por frame tem custo de rasterização por frame (mais lento que o compositing direto em Pillow); só compensa quando o resultado visual realmente depende de desenho vetorial.
- Remotion exige Node.js + Chromium instalados na máquina de render — não introduzir esse pipeline paralelo para resolver uma única animação; primeiro confirmar que é um padrão que vai se repetir em vários clientes/jobs.
