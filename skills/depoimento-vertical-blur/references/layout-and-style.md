# Layout e estilo

## Geometria padrão 1080×1920

Para um master 1920×1080:

| Camada | Recorte de origem | Saída | Posição |
|---|---:|---:|---:|
| Fundo | 608×1080 (9:16) | 1080×1920 | 0,0 |
| Primeiro plano nítido | 720×1080 (2:3) | 1080×1620 | 0,150 |

O primeiro plano ocupa 100% da largura. Sobram exatamente 150 px no topo e 150 px na base, preenchidos pelo fundo desfocado. Nunca reduza a largura do primeiro plano para criar bordas laterais.

Derive dimensões para outras fontes pela altura do master:

- `foreground_crop_width = source_height × 2/3`
- `background_crop_width = source_height × 9/16`
- limite ambos à largura disponível;
- preserve pixels pares para compatibilidade com yuv420p.

Filtro-base equivalente:

```text
[0:v]split=2[bgsrc][fgsrc];
[bgsrc]crop=BG_W:SRC_H:x=BG_X:y=0,
  scale=540:960,gblur=sigma=22:steps=2,
  scale=1080:1920,eq=brightness=-0.10:saturation=0.85[bg];
[fgsrc]crop=FG_W:SRC_H:x=FG_X:y=0,
  scale=1080:1620:flags=lanczos[fg];
[bg][fg]overlay=x=0:y=150[base]
```

Use expressões de crop suavizadas geradas por `scripts/face_track.py` ou valores fixos revisados por plano.

## Legenda padrão

- Cal Sans, 74 px como ponto de partida em 1080×1920.
- Branco puro, sem retângulo/fundo.
- Sombra preta com deslocamento aproximado de 6 px e blur de 10 px.
- Entrelinha aproximada de 82 px, mantendo tamanho constante.
- Centro horizontal; bloco visual normalmente entre y=1400 e y=1650.
- No máximo duas linhas, com quebras sem separar artigo/preposição da palavra seguinte quando houver opção melhor.

O posicionamento é aprovado pelo rosto, não por um número fixo. A boca e os olhos sempre têm prioridade sobre a preferência estética.

## Capa padrão

- 1080×1920.
- Montserrat em caixa alta.
- Alinhamento à esquerda e margens seguras.
- O título deve ser legível em thumbnail e o rosto não pode ser coberto.
- O PNG separado e o primeiro frame/primeiro segundo do MP4 devem corresponder.

## QA visual mínimo

Inspecione pelo menos: primeiro frame após a capa, primeira legenda, maior legenda, maior CPS, inclinações laterais da cabeça, aparição de lower thirds do master, última legenda e último frame. Confirme ausência de blur lateral em todos eles.
