---
name: video-render-optimizer
description: Detecte CPU, GPU e encoders FFmpeg, compare CPU versus aceleração por hardware em uma amostra real e escolha o encoder e o bitrate mais eficientes sem inflar o arquivo nem degradar perceptivelmente a imagem. Use antes de renderizações de edição de vídeo em uma máquina nova ou quando hardware, FFmpeg, resolução, FPS ou perfil de entrega mudarem.
---

# Otimização de render de vídeo

Escolha encoder e bitrate por evidência no dispositivo atual. Não presuma que GPU é sempre mais rápida ou que hardware encoding produz o melhor arquivo.

## Procedimento obrigatório

1. Leia [references/decision-policy.md](references/decision-policy.md).
2. Selecione uma amostra representativa de 8–15 s que contenha rosto, movimento, texto/legenda, transição e alguma região escura ou com gradiente.
3. Rode:

```bash
python3 scripts/benchmark_encoder.py --input /path/amostra.mp4 \
  --output-json work/encoder_benchmark.json
```

4. Registre GPU, encoders disponíveis, resolução/FPS, duração do teste, velocidade, bitrate real, tamanho e SSIM de cada candidato.
5. Defina a prioridade do job: `speed`, `balanced` ou `size`. A preferência operacional atual é `speed`: hardware vence quando acelera materialmente, respeita o teto absoluto de bitrate/tamanho e fica dentro da tolerância de qualidade.
6. Refaça o teste quando mudar máquina, versão do FFmpeg, codec, resolução, FPS, perfil de cor ou tipo de conteúdo. Não repita em todo corte se o ambiente e o perfil continuam iguais.

## Cache de benchmark

O script agora impõe a regra do item 6 sozinho, em vez de depender de lembrar entre sessões: ele monta uma *fingerprint* (SHA-256) de dispositivo + versão do FFmpeg + encoders disponíveis + perfil do vídeo (resolução/FPS/codec/pixel format) + prioridade/bitrate/preset do job, e guarda o relatório em `~/.cache/cibo/video-render-optimizer/<fingerprint>.json`.

- Rodar de novo com o mesmo ambiente e perfil devolve o relatório cacheado na hora (`"cache": {"hit": true, ...}`), sem recodificar nada.
- Qualquer mudança real (máquina, FFmpeg, encoder disponível, resolução/FPS/codec da amostra, prioridade ou bitrate) já muda a fingerprint e força um benchmark novo automaticamente — não precisa decidir manualmente se "mudou o suficiente".
- Cache expira sozinho em 30 dias (`--max-cache-age-days`), porque driver de GPU e build do FFmpeg podem mudar de comportamento silenciosamente.
- Use `--no-cache` para forçar um benchmark novo sem tocar no cache (ex.: suspeita de driver problemático).

## Integração

- Para Reels 1080×1920/30, o padrão inicial é `target 8 Mb/s`, `maxrate 10 Mb/s`, AAC 192 kb/s. Ajuste conforme duração, movimento e limite do destino.
- Para `libx264`, use CRF com `maxrate`/`bufsize`; CRF não é desculpa para ignorar o bitrate final.
- Para VideoToolbox/NVENC/QSV/VAAPI/AMF, fixe alvo e teto. Hardware normalmente precisa de mais bitrate para qualidade equivalente.
- Sempre valide o MP4 final com `ffprobe`: bitrate real, tamanho, codec, perfil, pixel format, resolução, FPS e faststart.
- Em `speed`, aceite bitrate maior que CPU desde que continue abaixo do teto definido e a qualidade passe. Em `balanced`/`size`, limite também a inflação relativa.
- Se a GPU for rejeitada, registre o motivo; não force hardware quando ultrapassar teto ou perder qualidade.

O script não altera arquivos do projeto. Ele grava apenas amostras temporárias e o relatório solicitado.
