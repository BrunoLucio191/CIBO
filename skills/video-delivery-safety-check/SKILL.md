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

4. O script faz probe, decodificação integral, checagem de streams, duração, bitrate, cor, loudness, pico, silêncio, frames pretos/congelados e métricas sem referência para blur, exposição e compressão. Ele detecta aceleração disponível e usa hardware decode quando confiável, com fallback para CPU.
5. Inspecione a contact sheet em tamanho legível e os frames de eventos esperados. Confirme rosto centralizado, pele natural, sombras recuperadas, ausência de artefatos, capa correta, lettering, legenda, B-roll, split, borda/blur e transições.
6. Confronte o resultado com job, transcrição, manifesto e pedido do usuário. Uma saída bonita, mas diferente do solicitado, falha.
7. `AUTOMATED_PASS` não autoriza entrega. Só marque `PASS` depois da inspeção visual, escuta do áudio final e confirmação do material esperado.

## Bloqueios

Bloqueie por arquivo truncado/corrompido, áudio ausente, resolução/FPS/codec incorretos, bitrate fora do teto, clipping, loudness inadequado, cor não sinalizada, imagem persistentemente escura/estourada/desfocada, compressão visível, freeze inesperado, frames pretos, rosto cortado, legenda errada ou elemento obrigatório ausente.

Se a métrica e a inspeção divergirem, investigue; não silencie o alerta apenas para entregar.
