---
name: foto-evento-cor
description: Corrija e nivele a cor de uma série de fotos (evento, palestra, corporativo) seguindo o padrão de correção de cor. O neutro de referência fica com os dois eixos certos, a pele fica na linha de tom de pele do vetorscópio (~123°), com brilho consistente entre fotos da mesma pessoa, e pretos e brancos ficam dentro do limite. Tudo é medido antes e depois, com tabela. Use quando o usuário pedir para ajustar, nivelar, igualar, deixar homogênea ou "acertar a cor" de várias fotos; não use para dar look/estilo (grading) sem antes corrigir.
---

# Correção e nivelamento de cor de fotos (padrão mensurável)

O usuário não aceita critério inventado na hora: toda mudança tem que vir de uma medida conhecida e ser provada com números de antes e depois. A ordem é sempre **correção → match → grading (look)**. Esta skill faz as duas primeiras. O grading só entra se o usuário pedir, e por cima de uma série já corrigida.

## Padrões usados (o "porquê" de cada número)

| Padrão | Medida | Alvo |
|---|---|---|
| Linha de tom de pele | ângulo de (U, V) da pele, vetorscópio BT.601 | 123°, faixa aceita ±6°. O alvo da série é a mediana da série, presa dentro da faixa |
| Neutro de referência | R/G e B/G, em luz linear, dos pixels quase sem cor (parede, piso, tripé) | Os **dois** eixos iguais aos da série. Com cartão cinza ou objeto sabidamente neutro, o alvo é 1,0/1,0 (`neutral_rg`/`neutral_bg` no config) |
| Exposição pela pele | L* mediano do rosto principal | Mesma pessoa com L* parecido (default 62; use 64 para pele morena bem iluminada). Com vários rostos, só corrige fora de 52–68 |
| Pretos | L* do 0,5% mais escuro | ≤ 5 (alvo ~3) |
| Brancos | % de pixels > 98,5% | ≤ 1% onde há detalhe; em JPEG, estouro já existente não volta |
| Entrega | sRGB, JPEG q95 4:4:4, EXIF e ICC preservados | — |

## Fluxo

Scripts em `scripts/` (Python 3 + numpy, Pillow, OpenCV ≥ 4.8 com `FaceDetectorYN`). O modelo de rosto fica em `assets/face_detection_yunet_2023mar.onnx`.

1. **Nunca sobrescreva.** Entrada = pasta do usuário; saída = pasta irmã `"<nome> - corrigidas"`. Temporários vão no scratchpad.
2. **Medir antes:** `python3 scripts/measure.py ENTRADA QA/antes`. Isso gera `measure.csv` e `faces.jpg`.
   - Abra `faces.jpg` e confira se cada recorte é mesmo um rosto. Falso positivo contamina a pele.
   - Leia a tabela: quais fotos fogem da faixa de pele, quais têm parede com cor diferente, quais têm preto lavado ou estouro. Agrupe por sequência ou ambiente (os desvios costumam vir em blocos, como uma sequência inteira com a luz diferente).
3. **Config** (modelo em `assets/config.example.json`):
   - Fotos em outro ambiente (madeira, piso quente, luz de janela) levam `neutral_weight: 0.3`, porque o "neutro" ali não é neutro.
   - Com um neutro de verdade conhecido, fixe `neutral_rg`/`neutral_bg`.
4. **Corrigir:** `python3 scripts/correct.py ENTRADA SAIDA config.json --report QA/report.json`. Leva cerca de 6 s por foto de 20 MP.
5. **Medir depois e comparar:** rode `measure.py SAIDA QA/depois` e depois `compare.py QA/antes/measure.csv QA/depois/measure.csv`.
6. **Olhar**, que não é opcional:
   - `contact_sheet.py SAIDA sheet.jpg` para ver a série inteira.
   - Antes/depois lado a lado das fotos que mais mexeram. Veja no `report.json` quem ficou com `gr`/`gb` perto de 0,75/1,25 ou `gam` no limite.
   - Parede rosada ou esverdeada, pele laranja e sombra lavada são reprovação, mesmo com os números bons.
7. **Entregar** com:
   - a tabela do `compare.py`;
   - o que ficou fora do padrão e por quê;
   - o que só se resolve no RAW.

## Lições (não repetir)

- **Nivelar pela média da cena (parede + saturação global) não é padrão.** Foi reprovado pelo usuário porque não havia como provar que estava certo. A saturação global engana: uma foto com muita parede cinza parece "pouco saturada" mesmo com a pele normal, e o boost deixou a pele laranja (DSC07490/7517 do CONFEA).
- **O ângulo da pele é pouco sensível ao balanço de branco:** 10% de verde gira só ~2,5°. Forçar 123° exato em pele medida a 113–116° exigiria ~25% de verde e esverdearia a foto. Por isso a pele trabalha com zona morta e faixa, e o neutro segura o resto.
- **O neutro precisa controlar R/G e B/G.** Com só B/G, a pele puxou a sequência do slide para o magenta e a parede ficou rosa.
- **O ponto de preto vem depois da curva de clareamento.** Clarear com gamma levanta o preto (L* 3 → 10). O script aplica `black2` depois do gamma.
- **Os limites existem para não "consertar" com um exagero:** balanço ±25%, exposição ~±0,5 EV, saturação 0,88–1,15. Foto que bate no limite deve ser citada ao usuário, não empurrada além dele.
- Quando pele e parede discordam (ex.: pele avermelhada e parede já no alvo), prevalece a parede. Informe a pele fora da faixa como observação, e não a corrija à força.
- JPEG já editado tem teto: branco estourado não volta. Se houver `.ARW`/RAW, recomende refazer a partir dele.
