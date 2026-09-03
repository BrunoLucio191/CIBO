---
name: caption-quality-gate
description: Faça um pente-fino obrigatório nas legendas de vídeos, verificando fidelidade à fala e ao contexto, português, timing, velocidade de leitura, quebras, ênfases, sobreposições e legibilidade no render. Detecta o hardware e usa o caminho mais eficiente para transcrição assistida e extração visual. Use antes do QA final de qualquer vídeo com legendas.
---

# Pente-fino de legendas

Uma legenda só é aprovada quando texto, tempo e render visual estão corretos. Arquivo válido ou SRT bem-formado não bastam.

## Fluxo obrigatório

1. Leia [references/review-policy.md](references/review-policy.md).
2. Detecte o dispositivo e os motores disponíveis. Em Apple Silicon, prefira MLX/Metal para ASR; em NVIDIA, CUDA; em outros casos, faster-whisper/whisper.cpp otimizado ou CPU. Se nenhum ASR estiver disponível, não finja validação fonética: faça os testes estruturais e marque escuta contextual como pendente.
3. Compare a legenda à fala completa, com pelo menos uma frase antes/depois. Corrija nomes, números, siglas, termos técnicos, concordância, acentuação e pontuação pelo sentido; nunca pelo som isolado.
4. Rode o verificador estrutural:

```bash
python3 scripts/check_captions.py --captions work/captions_corte.json \
  --video entrega.mp4 --caption-offset 1.0 \
  --sheet work/caption_sheet.jpg --output-json work/caption_report.json
```

5. Inspecione a contact sheet gerada. Confira todas as legendas críticas e uma amostra distribuída do restante. Texto precisa estar dentro da safe area, sem corte, desalinhamento, rosto coberto, contraste ruim ou palavra enfatizada errada.
6. Faça escuta A/B nos pontos com nomes, números, jargão, fala baixa, sobreposição de vozes e qualquer alerta. Uma similaridade alta de ASR não autoriza correção automática de nome próprio.
7. Só marque `PASS` depois de resolver erros e registrar a revisão visual/contextual. `AUTOMATED_PASS` significa apenas que os testes determinísticos passaram.

## Otimização

- Parseie JSON/SRT diretamente; não use OCR para validar texto que já existe em dados estruturados.
- Extraia todos os quadros de revisão em uma única decodificação. Use hardware decode quando disponível e faça fallback automático para CPU.
- Rode ASR uma vez por áudio e cacheie resultado por SHA-256, motor, modelo e parâmetros.
- Revise 100% dos alertas e captions críticos; use amostragem estratificada para captions simples, sem pular começo/fim.

Bloqueie a entrega por texto incorreto, pensamento mutilado, timing que corta fonema, CPS excessivo, sobreposição, linhas truncadas, legenda sobre rosto ou inconsistência entre dados e render.
