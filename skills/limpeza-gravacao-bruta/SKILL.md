---
name: limpeza-gravacao-bruta
description: Encontre e remova de uma gravação bruta longa (podcast, entrevista, live, videocast) os bastidores, pausas, retakes, falhas técnicas, bip de início e os assuntos que a equipe pediu para tirar, com emendas limpas definidas pelo sinal de áudio (início real da voz, sem suspiro, com folga na última palavra) e conferidas no arquivo final. Use quando o usuário perguntar se "pediram pra pausar/cortar algo" numa gravação, pedir para "tirar os bastidores", "limpar o bruto" ou "cortar esses trechos", ou apontar emendas ruins, em qualquer cliente; não use para criar cortes verticais/Reels (isso é a skill de corte do cliente).
---

# Limpeza de gravação bruta

Transforma o bruto de um episódio (ex.: `2026-09-23 14-15-51.mp4`, 1 h, OBS, 1080p30) no episódio sem bastidor, pronto para a edição fina. O usuário confere **cada emenda de ouvido**. Toda regra abaixo vem de uma emenda que foi reprovada ou de um pedido que foi perdido.

Os scripts ficam em `scripts/`. Use o Python do mlx-whisper para os que transcrevem: `PY=~/.local/share/uv/tools/mlx-whisper/bin/python`. Coloque os arquivos de trabalho no scratchpad (`DIR`).

## 1. Triagem: "foi pedido pra pausar/cortar algo?"

- **Pedido de resposta rápida**: rode `transcrever.py --rapido` (tiny a 1,5x, ~1 min/h) e depois `achar_bastidores.py`. Diga que a transcrição é grosseira.
- **Pedido de resposta precisa, ou quando você vai cortar**: rode `transcrever.py` (large-v3-turbo, ~5 min/h). Nos testes, o tiny não pegou nada que o turbo pegou: pausa pedida, "está em pausa" e 16 min de bastidor.

```bash
$PY scripts/transcrever.py BRUTO.mp4 --out DIR
python3 scripts/achar_bastidores.py DIR/segmentos.tsv
python3 scripts/achar_bastidores.py DIR/segmentos.tsv --janela 17:30-22:10 43:00-59:20
```

A palavra-chave **só aponta** onde olhar. Leia o contexto de cada ocorrência:
- Uma palavra-chave pode ser conteúdo: "esses cortes rendem muito", "pra fazer o corte isso é burrice".
- O bastidor mais longo quase não tem palavra-chave. Os sinais são: a conversa sai do formato de entrevista (contas de voto, agenda, futebol, "olha o que eu mandei no grupo"), o convidado para no meio da resposta, um apresentador dá direção ao outro ("aí tu fala assim…", "tu pode começar", "só contextualiza") ou há contagem ("um, dois, três").
- Um bloco repetido de texto ("tá tá tá…") marca falha técnica ou ruído. Confira o que foi dito em volta ("Tá saindo não? Será que foi o meu?").
- Não pare na primeira varredura. Se uma segunda leitura com termos mais amplos não achar nada, diga isso. Se achar, liste.

Entregue uma **tabela com trecho (início–fim), o que acontece e a citação**. Marque o que é certo, o que é provável e o que deve ser ouvido.

## 2. Decidir o que sai (a parte editorial)

- **Quando a equipe pede para tirar um assunto, sai também a parte que foi ao ar.** Quando o bastidor diz "tira essa parte", "deixa quieta a questão de X" ou "esse bloco não é pra ele", corte **a pergunta e a resposta sobre X que foram gravadas**, além da conversa de bastidor. Esse erro já aconteceu: a pergunta sobre a saída de um candidato da chapa ficou no vídeo.
- **Pedido ambíguo vai para o usuário.** Exemplo: "deixa quieta a escolha do partido", respondido com "mas a gente tem que falar sobre partido, né?… vocês é que sabem". Não decida sozinho. Mostre o trecho e as citações e pergunte. Neste caso o usuário mandou tirar.
- **Quando você corta a pergunta, a emenda precisa continuar fazendo sentido.** Termine a fala do apresentador numa frase que funcione como gancho e volte direto na resposta. Por exemplo: "…nesses últimos dias na Vila Passos" → "No início, nós percorremos o Estado…". Proponha o ponto e aceite o ajuste do usuário.
- **Retake**: fique com a versão refeita, que costuma ser a melhor ("então vamos falar de novo" → a pergunta refeita). Mas se a direção disser "pega aquela primeira parte", use a primeira parte e emende no retake.
- **Quando um apresentador combina a pergunta com o outro** ("além dessa pauta, qual a outra…?" dito ao colega), a volta começa na **pergunta real** do colega.
- **Erro de fala sem texto: procure pelo sinal.** Gagueira ("eu, eu, eu, eu"), hesitação ("ah, é… e aí") e frase largada ("e que…") muitas vezes não aparecem na transcrição, nem com o prompt de hesitação da `fala-limpa`. Na Katia, o usuário perguntou "pegou todos os erros?", e 6 tinham passado. Rode `scripts/achar_voz_sem_palavra.py audio16k.wav whisper.json` e transcreva cada candidato isolado com large-v3 **e** turbo. Fala contínua sem respiro (ex.: a convidada procurando a palavra) não corta limpo: diga isso ao usuário em vez de forçar a emenda.
- **Bate-bola e trechos com muitos retakes curtos**: revise palavra por palavra no trecho inteiro, não só nas bordas. Fique com a tomada mais limpa de cada pergunta. Tire "vamos lá" com pausa longa, "vai", gaguejadas e inícios incompletos ("ma… maior qualidade").
- **Início**: corte a pré-gravação e o **bip** de claquete. O bip encosta na primeira palavra, então use `achar_bip.py`.
- **Fim**: corte depois da despedida ("valeu, até a próxima").
- **Nome do convidado**: a transcrição erra a grafia (Arraes → **Arrais**). Confirme em fonte oficial antes de usar em qualquer texto.

## 3. Definir o ponto exato de cada emenda

**Não use o tempo da transcrição como ponto de corte.** O tempo por frase erra até 1 s, e o tempo por palavra errou 0,3–0,5 s em vários pontos. A primeira versão feita com esses tempos teve 6 emendas reprovadas: sobrou "pode ir", "isso" e "É, ficou bom", entraram suspiros e uma palavra ficou cortada.

```bash
# cortes.json = [[inicio, fim], ...] em segundos do ORIGINAL; o que está entre eles sai. null = até o final.
$PY scripts/sondar_emendas.py DIR/audio16k.wav cortes.json
python3 scripts/achar_bip.py BRUTO.mp4 45 5
```

Leia o perfil de cada borda (`V` = voz, `b` = som sem voz, `.` = silêncio) e decida. Validação feita contra os pontos corrigidos à mão neste projeto: a **volta** acertou 7 de 9 com diferença ≤ 0,05 s. Os 2 erros foram por causa do `t` informado: o script escolheu "pode ir" e "ma…". Por isso **o `t` da volta precisa ficar depois da última fala de direção ou gaguejada**, e escolher em que palavra voltar é decisão editorial. Na **saída**, o script mostra dois candidatos, CURTO (primeiro vale) e LONGO (logo antes da próxima fala), e escolhe pela distância entre eles: até 0,3 s é o fim da própria palavra e ele usa o LONGO; mais que isso é a respiração de quem vai falar e ele usa o CURTO. A transcrição dos candidatos não diferencia "sucesso" cortado de inteiro, então não use só ela.

| Borda | Regra | Por quê |
|---|---|---|
| **Volta** | Comece a ~20 ms do primeiro `V` da primeira palavra. Só recue sobre `b` se for consoante curta (≤ 80 ms: "F", "C", "S"). | Sobra de "preparação" antes da fala e demora antes do convidado falar foram reprovadas. |
| **Volta com suspiro** | Um `bbbbbbbbb` de 0,4–0,7 s em −23…−30 dB colado no `V` é suspiro ou respiração. Comece depois dele. | O apresentador (Mota, no Pod Acontecer) suspira alto antes de retomar. Isso foi reprovado 3 vezes. |
| **Saída** | Corte no primeiro vale (< −40 dB) depois da última voz. Isso costuma dar 0,1–0,3 s de folga. | "vai ter sucesso" cortado colado foi reprovado. O "-so" final continuava 0,25 s depois do tempo do Whisper. |
| **Saída colada em direção** | Quando a direção entra sem pausa ("acredito que não **é bom botar isso aí**"), teste pontos de corte transcrevendo trechos que terminam em t, t+0,2 e t+0,4. Fique com o último que não traz a direção. | Uma folga maior deixaria a direção entrar no vídeo. |
| **Saída dentro de fala contínua** | Sem vale < −40 dB, não confie na queda de envelope. Monte a emenda só no áudio (`atrim` + `concat`) com saída em t−0,06, t e t+0,06, transcreva com large-v3 e turbo e fique com a que mantém a última palavra inteira sem começo da próxima. | Katia 14:14: a saída em 870,93 deixou "sensibili…" de outra fala depois de "também". 870,56 resolveu. |
| **Bip** | Um tom fixo > 2 kHz com tonalidade > 60. Pode tocar duas vezes, e o segundo toque encosta no "F" de "Fala". Volte no início da fricativa. | O bip ficou no vídeo e foi reprovado. |
| **Silêncio digital** | −180 dB é o noise gate do OBS. Pode cortar dentro dele à vontade. | — |

## 4. Renderizar e verificar

```bash
python3 scripts/renderizar_cortes.py BRUTO.mp4 cortes.json "BRUTO (sem bastidores).mp4" --so-plano   # posições das emendas
python3 scripts/renderizar_cortes.py BRUTO.mp4 cortes.json "BRUTO (sem bastidores).mp4" [--punch punch.json]
$PY scripts/conferir_emendas.py "BRUTO (sem bastidores).mp4" BRUTO.mp4 cortes.json
```

- **Corte por frame** (trim/concat) com re-encode. Stream copy cortaria no keyframe e erraria a emenda.
- **Encoder**: h264_videotoolbox a ~8 Mb/s no Mac (≈ 6x tempo real, ~5 min para 30 min de vídeo). Mantenha o bitrate acima do original para não perder qualidade.
- **Renderize num arquivo temporário e decodifique o arquivo inteiro antes de substituir.** Um render interrompido gerou AAC corrompido (1.943 erros) que o ffprobe mostrava como normal. O script já faz isso.
- **Rode o render em background** quando o usuário puder mandar mensagens durante ele, e avise que está renderizando ("tá editando mesmo?" é sinal de que você ficou em silêncio tempo demais).
- **Duração das duas trilhas.** Num episódio de ~1 h (Autismo Cast), vários `atrim` da mesma entrada num grafo geraram 59:56 de vídeo e só 4:17 de áudio, com exit 0 e decodificação limpa. O script agora confere vídeo e áudio contra o total esperado e, se o áudio encurtar, refaz só o áudio a partir de um WAV e remuxa o vídeo com `-c:v copy` (1 min em vez de 35 min de re-encode).
- **Ponto de emenda por palavra, nunca por segmento.** Uma contagem "um, dois, três, vai" estava escondida dentro de um segmento do Whisper que começava em 15,7 s. Use `--word-timestamps` numa janela curta em volta de cada IN/OUT.
- **Emenda no mesmo plano vira jump cut.** Em master multicâmera já cortado (Katia, 14/09), compare o quadro antes e depois de cada emenda. Se o plano for o mesmo, use `--punch punch.json` (`[[ini, fim, zoom, cx, cy], ...]` em segundos do original): o trecho depois da emenda entra com zoom de 1,15–1,2× no rosto (1,3× num plano aberto) **até a próxima troca de câmera** do master, que você acha com `select='gt(scene,0.25)'`. Não deixe trecho menor que ~1,5 s entre duas emendas no mesmo plano, porque o punch pisca. Nesse caso, desista de uma das emendas.
- **Meça o true peak do original antes de entregar.** O bruto da Katia vinha a −12 LUFS, limitado no teto, e o AAC decodificava a +3,8 dBFS. O `verify_video.py` barrou. A correção foi ganho fixo de −3 dB mais `aresample=192000,alimiter=limit=-1.5dB:level=false,aresample=48000`, refazendo só o áudio com `-c:v copy` (~1 min). O resultado foi −15,2 LUFS e −1,2 dBTP. Nunca use `loudnorm`.
- **Confira no arquivo final**, não no plano. Em cada emenda, o texto precisa fechar e abrir limpo, e a voz precisa aparecer em ≤ 0,1 s depois dela.
- Detalhes do FFmpeg 7+/8: use `-/filter_complex ARQUIVO`, porque `-filter_complex_script` foi removido. No zsh, `set -- $var` não separa palavras. Use Python para montar listas.

## 5. Entrega

- Mantenha o original intocado. A saída vai para `NOME (sem bastidores).mp4`, na mesma pasta, e sempre fica só a última versão boa.
- Informe a duração antes e depois, uma tabela com **cada emenda no tempo do vídeo final** e o que ficou dos dois lados, e as decisões editoriais que o usuário deve checar (retake escolhido, assunto mantido ou tirado).
- Seja honesto sobre o que não foi verificado. Bastidor sem palavra-chave no meio do conteúdo pode ter passado, e o salto de enquadramento nas emendas secas precisa ser visto na imagem.
- **"Corte" para o usuário quer dizer Reel.** Quando ele pede "edição limpa" de um podcast longo, fale em "emendas" ou "trechos removidos", nunca em "cortes": "eu n quero corte, é um podcast limpo" (Katia).
- Toda correção nova do usuário sobre emenda ou editorial vira uma regra nesta skill.

## Configuração de render no DaVinci (pergunta recorrente)

Para renderizar mais rápido sem perder qualidade visível:
- Encoder **Apple VideoToolbox** (hardware).
- Para podcast 1080p30, **Restrict to 20 000–25 000 kb/s**. 80 000 é exagero.
- **Multi-pass desligado**, porque dobra o tempo.
- Key frames e profile em Auto, frame reordering ligado.
- "Use render cached images" quando houver cache de color ou efeitos.
- O que mais pesa depois do encoder é noise reduction e efeito na timeline, não as opções do encoder.
