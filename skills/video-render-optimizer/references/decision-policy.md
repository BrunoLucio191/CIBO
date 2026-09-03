# Política de decisão CPU × GPU e bitrate

## Critérios

Compare candidatos usando a mesma amostra e dimensões:

- velocidade de codificação e ganho sobre CPU;
- SSIM contra a amostra de referência;
- bitrate médio real e tamanho projetado;
- compatibilidade H.264 High/yuv420p/Rec.709/faststart;
- estabilidade visual em pele, texto, sombras, gradientes, grain e transições;
- custo térmico quando o teste for repetido em notebook.

## Perfis de prioridade

- `speed` (preferência atual): exige ganho ≥1,25×, qualidade aprovada e respeito ao teto absoluto. Não bloqueia apenas por ser maior que o arquivo CPU.
- `balanced`: exige ganho ≥1,5× e no máximo 175% do bitrate CPU, além do teto absoluto.
- `size`: exige ganho ≥2× e no máximo 125% do bitrate CPU; normalmente preserva x264.

## Aprovação automática de hardware

O encoder de hardware pode ser recomendado quando todos forem verdadeiros:

- ganho mínimo correspondente ao perfil escolhido;
- SSIM de pelo menos 0,96 e não mais que 0,01 abaixo do resultado CPU;
- bitrate real não excede 115% do teto configurado;
- inflação relativa respeita o perfil; em `speed`, vale o teto absoluto do job;
- tamanho projetado cabe no destino;
- arquivo decodifica integralmente e mantém pixel format/resolução/FPS esperados.

Caso contrário, use CPU para o master final. Hardware ainda pode ser usado para previews, desde que claramente separado da entrega final.

## Bitrate inicial por perfil

Valores são pontos de partida, não metas a preencher:

| Perfil | Alvo | Teto |
|---|---:|---:|
| 1080×1920, 30 fps, talking head | 6–8 Mb/s | 10 Mb/s |
| 1080×1920, 60 fps ou muito movimento | 9–12 Mb/s | 14 Mb/s |
| 1920×1080, 30 fps | 6–8 Mb/s | 10 Mb/s |
| 4K, 30 fps, H.264 | 24–35 Mb/s | 45 Mb/s |

Para um limite rígido de tamanho, calcule antes:

`bitrate_total_kbps = tamanho_MB × 8192 / duração_s`

Subtraia o bitrate de áudio e 3–5% de margem de container. Nunca aumente o bitrate somente porque o encoder permite.

## Inspeção visual obrigatória

Métricas não substituem revisão. Compare pelo menos três quadros e um trecho em movimento, procurando banding, blocos, ringing em letras, pele plastificada e perda de detalhe nas sombras.
