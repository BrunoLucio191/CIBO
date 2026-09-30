---
name: fernanda-produto
description: Edite os vídeos verticais de apresentação de produto da Fernanda (linha Zeo — ZeoBody, ZeoDent etc.) gravados em câmera Sony deitada e em S-Log3, com colorização, suavização de pele, corte de bastidores e gaguejadas, zoom suave, referências do Pexels em tela dividida, burn azul, legenda no estilo Zeo, SFX nas transições e música em faixa separada. Use somente em trabalhos da Fernanda.
---

# Fernanda — vídeo de produto

Padrão aprovado pelo usuário em duas entregas (ZeoBody `C0343`, ZeoDent `C0345`). Tudo é dirigido por um `job.json` (modelo em `assets/job.example.json`); os tempos do job são do **arquivo original** e `scripts/timeline.py` converte para o vídeo editado.

Leia `references/client-content-bible.md` antes de começar: lá estão as correções que o usuário já fez e que não podem voltar.

## Fluxo

1. **Probe e rotação.** `ffprobe` + `ffmpeg -hide_banner -i` para ver se há *Display Matrix*. O primeiro arquivo tinha rotação −90° nos metadados; o segundo não tinha. O render usa `-noautorotate` + `rotate: "clock"`: confira um quadro antes de seguir.
2. **Transcrição.** `mlx_whisper` com turbo (rápido) e **large-v3 completo** (`mlx-community/whisper-large-v3-mlx`), `--word-timestamps True --condition-on-previous-text False`.
3. **Início, fim, gaguejadas e fala limpa.** Rode a skill `fala-limpa` (outra voz, hesitação, pausa de pensamento, fim cortado) antes da legenda e de novo no QA. Só a voz da falante entra no vídeo.
   - `in` logo antes da primeira fala real e `out` logo depois da última. Corte "um, dois, três", "Gostou?", "deixa eu gravar outra" e os closes de produto para a equipe.
   - Gaguejadas: procure repetições e reinícios ("que essa microbioma, que esse microbioma"). **Antes de cortar, transcreva o trecho isolado com contexto**, porque o large-v3 inventa repetições em arquivo longo ("certeza certeza" não existia).
   - Ache as bordas com `scripts/find_pauses.py AUDIO env A B` (envelope em 10 ms) e corte **de silêncio a silêncio**. Corte só pelos tempos de palavra saiu "q-que" e foi reprovado.
   - Teste o corte só no áudio (atrim + acrossfade) e transcreva de novo com os dois modelos.
4. **Legenda.** `scripts/build_captions.py job.json large.json captions.json`, depois revise à mão as quebras finais e os termos.
   - **Em arquivo longo o tempo das palavras erra 0,1–0,3 s** e o script traz de volta palavra cortada ("o suor, manchou") ou perde palavra mantida ("sair de toxina" sem o "por"). Nesse caso monte o áudio editado (os mesmos `atrim` do job), transcreva **esse** áudio com `--word-timestamps` e escreva os blocos à mão sobre ele; use esse JSON como `caption_words`.
   - Quebra por sentido, nunca terminar bloco em palavra funcional (inclui "eu", "que eu"), ~17 cps.
   - `keywords`: poucas e escolhidas (6–8 por minuto), sem pontuação. Lista inflada (20+ palavras, "Toxina!", "40", "dela") faz o destaque cair em palavra à toa: reprovado no reel da Malu.
   - Fonte por job (opcional, padrão = Montserrat): `caption_font`/`caption_weight`, `key_font`/`key_weight`, `key_style: "plain"` (palavra-chave sem etiqueta), `key_scale`. Pesos aceitam nome ("Medium") ou eixos ([14, 400] no DM Sans). Ela fala "adsorve" (zeólita adsorve), não "absorve". "Estaminas" é legendado como "histaminas": avise o usuário.
5. **Referências (B-roll).** Siga `semantic-broll-validator`.
   - Pexels pelo Chrome: o `fetch` da página de busca/vídeo dentro da aba devolve os IDs e os links `sd`. O download em 4K é `https://www.pexels.com/download/video/<ID>/` via curl.
   - Mixkit gratuito só tem 720p, e muita coisa é *Restricted License*: evite.
   - Rejeite imagem só "do mesmo tema": o manequim anatômico para "tireoide e pineal" foi reprovado. A tireoide ficou com um médico examinando a garganta. Para a pineal, o cérebro em ilustração também foi tirado e ali entrou um zoom nela.
   - Quando nenhuma imagem é específica, não use referência. Deixe ela em tela cheia com zoom.
   - Mostre a lista de referências (tempo, fala, imagem) ao usuário.
6. **Transições nas pausas.** Rode `find_pauses.py AUDIO snap <tempos>` e coloque cada entrada, saída e troca de referência no centro de uma pausa. Um flash com whoosh em cima da palavra que ela retomava soou como "corte estranho cortando palavras".
7. **Zooms.** 3 a 5 zooms suaves a cada 10–18 s, só com ela em tela cheia, no começo de frase, e nunca a menos de 4,6 s de outra referência. Em cada corte de gaguejada entra automaticamente um zoom seco (10%, volta em 3 s).
   - O padrão da Fernanda é este (0,6 s de entrada). Os cortes da **Malu** têm estilo próprio (entrada rápida com blur, volta lenta): ver skill `malu-cortes`. Não aplicar o estilo da Malu em vídeo da Fernanda.
   - Referência entra e sai **no próprio corte** ou longe dele (> 1,2 s): referência saindo 0,2 s antes de um corte gera um plano que pisca (pego pelo `video-delivery-safety-check`).
   - Jump cut (inclusive aparo de pausa) sempre com troca de nível de enquadramento (`shots` alternando).
8. **Música.** Siga `talking-head-music`. A usada nos dois vídeos é *Motivating Mornings* (Ahjay Stelino, Mixkit, licença livre, 123 BPM, 4,8% da energia em 1–4 kHz), com `offset: auto`, que alinha o final natural da faixa (93,2 s) com o fim do vídeo. Fica ~20 dB abaixo da voz, com sidechain.
9. **Render.**
   ```bash
   python3 scripts/render.py job.json prep    # legenda, trilha de burn, trilha de SFX
   python3 scripts/render.py job.json check   # valida o grafo em 0,5 s
   python3 scripts/render.py job.json render  # ~10 min em 4K; rode em background
   ```
   Saídas em `out_dir`:
   - `<name> - final com referencias.mp4`: A1 voz+SFX e A2 música, para ajuste no editor.
   - `<name> - final (mix pronto para postar).mp4`: uma faixa só.
10. **QA** (`caption-quality-gate`, `legenda-cruzada`, `video-delivery-safety-check`):
    - Contact sheet de cada referência e de cada corte.
    - Transcrição final com large-v3.
    - `ebur128` (alvo: voz ~−16 LUFS, pico ≤ −1 dB).
    - Voz ≥ 18 dB acima da música na fala.
    - Nenhum trecho com SFX > −35 dB sobre fala > −26 dB.

## Cortes da Malu

Os cortes da Malu (entrevista, `C0097`, mesma linha Zeo) usam este motor, mas com **estilo, regras e bíblia próprios**: skill `malu-cortes`. O que é da Malu (fonte DM Sans + Playfair, zoom rápido com blur, 3 níveis de enquadramento, rastreamento de rosto, música −27,5) fica lá e não vale para a Fernanda.

## Opções do motor (todas opcionais; sem a chave, vale o padrão Fernanda)

| Chave do job | O que faz | Nasceu de |
|---|---|---|
| `shots` + `framings` | enquadramento por plano; `framings[i]` estático `[x,y,w,h]` ou seguido `{"w","h","kx","ky"}` (keyframes do `face_track.py`) | Malu: plano aberto, ela se mexe |
| `tail_hold` | congela o último quadro em silêncio (s) | "desconforto" engolido pelo fade |
| `zoom_in`, `zoom_out`, `zoom_blur`, `smooth_zooms` | duração da entrada/volta do zoom suave e blur de movimento na entrada | estilo Malu |
| `ref_push` | push lento dentro do painel da referência | estilo Malu |
| `whoosh_post`, `click_lead`, `sfx_db` | cauda do whoosh, antecipação do clique, nível dos SFX | SFX encostando na fala |
| `caption_font/weight`, `key_font/weight`, `key_style`, `key_scale`, `caption_glow` | tipografia da legenda | legenda "suave e elegante" |
| `voice_filter`, `duck_threshold` | leveling da voz e limiar do ducking | voz baixa (confirme o locutor antes!) |
| `caption_pins`, `brand_terms`, `cortes_revisados` | ajuste manual de legenda (tempo do original), grafia de marca, emendas já ouvidas | pente-fino |

Ferramentas: `review_job.py` (pente-fino pré-render: cortes, planos, referências, zooms, legenda, SFX), `sync_captions.py` (legenda no ataque real da fala), `face_track.py` (matriz no rosto, parada × movimento, travar ou seguir), `speech.py` (ataque/fim de fala no envelope).

## Fim do vídeo

`tail_hold` (s, ~0,8): congela o último quadro em silêncio depois do `out`. O fade de 0,35 s cai sobre o quadro parado, nunca sobre a última palavra ("desconforto" foi engolido). Continuar o vídeo com som mudo mostraria ela falando a frase seguinte sem áudio.

## O que o render faz (e por quê)

| Etapa | Valor | Origem da decisão |
|---|---|---|
| Rotação + colorização | LUT Sony S-Log3/S-Gamut3.Cine → LC-709 Type A, saturação 0,88, temperatura 6200 K a 35%, contraste 1,03 | material é S-Log3 8 bits; LUT puro deixava o vestido violeta |
| Pele | bilateral (σS 6, σR 0,06) em meia resolução, **30%** sobre o original | 45% já parece plástico |
| Zoom | crop dinâmico + scale fixo, 12% em 0,6 s, volta em 4 s, âncora y 0,38 | 0,25 s foi "rápido demais"; `scale(eval=frame)+crop(iw)` ancorava no canto |
| Tela dividida | referência 2160×1500 no topo, Fernanda deslocada **850 px**, blur em degradê de 220 px na emenda | 1250 px deixou ela "baixa demais"; emenda seca pediu blur suave |
| Legenda | Montserrat Medium 122 px, sombra suave, baseline 2322 (1650 na tela dividida) | medida nos cortes Zeo anteriores |
| Burn | `filmburn_blue` (Bombordo) em screen, pico em cada emenda + início e fim | usuário pediu "azul, tom mais escuro como Bombordo" |
| SFX | whoosh do arquivo original do burn só em entradas e saídas das referências, clique em cada entrada ou troca, trilha a −6 dB | "use o sfx com sabedoria"; "só um pouquinho mais baixo" |
| Áudio | A1 voz+SFX, A2 música com ducking + cópia mixada | usuário gostou de ter as faixas separadas |

## Armadilhas já encontradas

- `crop` com `iw/ih` depois de `scale(eval=frame)` usa o tamanho da configuração inicial: o zoom "vai para a esquerda". Use crop com `w/h/x/y` calculados pelo tempo e `scale` fixo depois.
- Somar termos de zoom que se sobrepõem dobra o zoom. Combine com `max()`.
- `blend=all_mode=normal:all_opacity` não mistura como esperado. Para misturar dois quadros use `mix=weights`.
- Clipe 4:3 (1920×1440) quebra `scale=-2:1500,crop=2160`. Use `force_original_aspect_ratio=increase`.
- Comparar quadros num `hstack` do ffmpeg com PNGs de formatos diferentes distorce a cor da comparação. Monte o comparativo com PIL.
- `sed` com `#` no texto de substituição falha em silêncio no macOS. Edite scripts com Python.
- Processos iniciados com `&` dentro do Bash podem morrer. Use `run_in_background`.
- `render.py check` às vezes trava no encerramento do ffmpeg (0% de CPU, nunca sai). Agora tem timeout de 120 s; o render completo não tem esse problema, mas rode-o com um vigia de CPU.
- **Música relativa à voz, não número fixo.** `db: -20.5` serve para a voz da Fernanda; na Malu (voz ~5 dB mais baixa) deixou 69% da fala com menos de 18 dB de margem e a música encobriu "vai preparando o corpo". Meça A1 × A2 por janelas de fala depois do render e ajuste (`-27.5` na Malu).
- Referência que entra logo depois de um corte cria um plano de ~0,5 s que pisca: comece a referência no próprio corte.
- A cópia mixada com `-c:v copy` perdia `color_transfer/primaries` bt709, e o limitador em 0,89 deixava o true peak em −0,9 dBTP: corrigido (tags explícitas e limite 0,84).
- `caption_glow` (~0,4): halo escuro suave na legenda, para ler sobre frasco branco na emenda da tela dividida.
