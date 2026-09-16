---
name: video-delivery-safety-check
description: Execute o checking final obrigatório de um vídeo antes da entrega, confrontando o MP4 com o job esperado e detectando falhas técnicas, visuais, sonoras e editoriais, incluindo baixa qualidade, blur, compressão, exposição, cor, frames pretos/congelados, bitrate, capa, legendas e elementos ausentes. Use após todo render final.
---

# Trava final de qualidade e segurança do vídeo

Nenhum vídeo é entregue porque “renderizou sem erro”. A saída precisa corresponder ao material solicitado e passar por verificação técnica, visual, sonora e editorial.

## Fluxo obrigatório

1. Leia [references/final-checklist.md](references/final-checklist.md).
2. Rode primeiro `caption-quality-gate` quando houver legendas.
3. Rode o verificador no MP4 final:

```bash
python3 scripts/verify_video.py --video entrega.mp4 \
  --plan work/plan.json --clip corte_01 --cover "CAPA - entrega.png" \
  --sheet qa/entrega_contact_sheet.jpg --output-json qa/entrega_report.json
```

4. O script faz probe, decodificação integral, checagem de streams, duração, bitrate, cor, loudness, pico, silêncio, frames pretos/congelados, **duração de cada plano de câmera**, **cadência de frames** e métricas sem referência para blur, exposição e compressão. Ele detecta aceleração disponível e usa hardware decode quando confiável, com fallback para CPU.
5. Inspecione a contact sheet em tamanho legível e os frames de eventos esperados. Confirme rosto centralizado, pele natural, sombras recuperadas, ausência de artefatos, capa correta, lettering, legenda, B-roll, split, borda/blur e transições.
6. Confronte o resultado com job, transcrição, manifesto e pedido do usuário. Uma saída bonita, mas diferente do solicitado, falha.
7. `AUTOMATED_PASS` não autoriza entrega. Só marque `PASS` depois da inspeção visual, escuta do áudio final e confirmação do material esperado.

## Plano curto: o defeito que passa por todos os outros testes

`freezedetect` só acusa congelamento de 2 s ou mais, e nenhuma outra checagem
olha movimento. Um reenquadramento automático que salta de uma pessoa para
outra por meio segundo e volta produz um vídeo tecnicamente perfeito que, na
tela, pisca. Um cliente vai chamar isso de "travado" e o relatório vai continuar
verde.

Por isso o script agora corta o vídeo em planos e avisa quando algum fica abaixo
de `--min-shot` (padrão 1,2 s). A detecção compara quadros reduzidos a 160x90 em
escala de cinza, e **não** usa o filtro `scene` do ffmpeg: um corte de crop
dentro de um plano contínuo não mexe no histograma o suficiente para o `scene`
acusar, e em material real ele não achou nenhum corte onde havia quatro.

O limiar 35 foi calibrado em material real: corte de câmera de verdade deu 68 e
89, enquanto gesto largo e reflexo de luminária ficaram em 26. O agrupamento de
picos vizinhos é de apenas 3 quadros de propósito — com uma janela larga o
detector fica cego justamente para o plano de meio segundo que ele existe para
achar.

## Cadência de frames: medida, não veredito

O relatório traz `cadence.ratio`, a fração de quadros que carregam imagem nova.
Uma gravação feita a ~24 fps dentro de um container de 30 fps repete um quadro a
cada cinco, e o movimento treme sem que codec, fps ou bitrate acusem nada.

Esse número **não** vira aviso automático, e a razão está medida: a mesma métrica
cai igual quando a câmera está travada e o entrevistado está parado, que é o
normal de um talking head bem enquadrado. Em teste, a fonte com judder deu 0,78
e um corte limpo de câmera fixa deu 0,83 — não há limiar que separe os dois.
Endurecer o `mpdecimate` também não resolve: com limiar estrito o judder some da
medição, porque os quadros repetidos não são idênticos, têm ruído de compressão.

Use o número comparando o corte com a fonte: se os dois batem, o judder é
herdado e a conversa é sobre a gravação, não sobre o render.

## Bloqueios

Bloqueie por arquivo truncado/corrompido, áudio ausente, resolução/FPS/codec incorretos, bitrate fora do teto, clipping, loudness inadequado, cor não sinalizada, imagem persistentemente escura/estourada/desfocada, compressão visível, freeze inesperado, frames pretos, rosto cortado, legenda errada ou elemento obrigatório ausente.

Se a métrica e a inspeção divergirem, investigue; não silencie o alerta apenas para entregar.
