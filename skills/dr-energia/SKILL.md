---
name: dr-energia
description: Crie cortes verticais 9:16 para Reels, TikTok e Shorts do Dr. Energia BR Cast, com a identidade, a proporção de falantes, o burn-in verde e as convenções de capa e áudio próprias deste cliente. Use somente em trabalhos do Dr. Energia.
---

# Dr. Energia BR Cast → cortes verticais

Apresentador: **Guilherme** (o canal é dele). Convidados são empresários e
especialistas do setor de energia solar. O público-alvo declarado no próprio
episódio são **médicos e profissionais liberais** que investem em usina.

Este cliente tem um motor próprio, em `scripts/`, e não usa a `podcast-reels`.
O reenquadramento delega para o `face_crop.py` da `bombordo-boreste`.

## Convenções do cliente

Todas foram definidas pelo Bruno e nenhuma é negociável sem ele dizer.

| Item | Regra |
|---|---|
| Capa | **Um frame só** (`CAPA_FRAMES = 1`). Ela é a miniatura do feed, não a abertura. |
| Degradê da capa | Só no rodapé: alpha zero até 60% da altura, denso atrás do título e sob a logo. Nunca cobrir o rosto. |
| Burn-in | Verde, **na entrada e na saída**. `assets/filmburn_green.mp4`. |
| Taxa de quadros | **24 fps**. A fonte está marcada como 30 mas tem ~23,7 fps de conteúdo real. |
| Proporção de falantes | **4 cortes do apresentador e 2 do convidado.** Se não der, 3 e 3; em último caso 2 e 4. |
| Encerramento | Nunca cortar fala, de nenhum dos dois. |
| Enquadramento | Quadro parado. Um crop por plano de câmera, nunca perseguindo rosto. |
| Áudio | Voz a −15 LUFS por ganho fixo medido; trilha ~20 dB abaixo; pico ≤ −1 dBTP. |

## O material de origem (verificado no episódio 4)

- Gravação do OBS, 1920x1080, container 30 fps, **conteúdo real ~23,7 fps**: um
  quadro a cada cinco é repetido. Entregar a 24 conforma a cadência de verdade.
- Áudio **mono duplicado nos dois canais** — não há microfone separado por
  pessoa, então diarização por canal é impossível.
- Feed multicâmera já chaveado: a direção corta para quem fala, o que serve de
  confirmação visual de quem é o dono da fala.

## Fluxo

1. **Prepare a transcrição.** A transcrição de produção sai com defeitos
   sistemáticos; `preparar_transcricao.py` os corrige de forma reproduzível,
   partindo sempre do arquivo cru preservado:
   ```bash
   python3 scripts/preparar_transcricao.py ep4_palavras_cru.json ep4_palavras.json
   ```
2. **Escolha os cortes lendo a transcrição inteira.** Atribua as falas pelo
   conteúdo (quem pergunta, quem é chamado pelo nome, quem conta a história) e
   **confirme visualmente** quem está em cena. Ver "Quem fala" abaixo.
3. **Encaixe as bordas nas lacunas entre palavras**, conferindo contra o JSON de
   palavras: a primeira e a última palavra precisam caber inteiras.
4. **Escreva `cortes.json`** (modelo em `references/cortes.exemplo.json`), com
   `quem` (`host`/`convidado`), `titulo` em duas linhas, trilha, offset e ganho.
   `capa_ini`/`capa_fim` opcionais forçam a capa para dentro de um plano.
5. **Gere capa e trilha de enquadramento, e renderize:**
   ```bash
   export PROJETO="$PWD"
   python3 scripts/pick_frame.py <fonte> <ini> <fim> capas/<nome>_frame.png
   python3 scripts/make_cover.py capas/<nome>_frame.png capas/<nome>.png "Linha 1" "Linha 2"
   ~/.claude/skills/bombordo-boreste/.venv/bin/python3 scripts/reframe.py <fonte> <ini> <fim> tmp/<nome>.sendcmd
   python3 scripts/render_corte.py cortes.json <palavras.json> ["<nome do corte>" ...]
   ```
   O `reframe.py` precisa do venv da `bombordo-boreste`: o OpenCV do sistema não
   traz `CascadeClassifier`.
6. **Rode os três portões, nesta ordem**: `caption-quality-gate`,
   `legenda-cruzada` e `video-delivery-safety-check`. Nenhum deles sozinho
   autoriza entrega — ver `qa-automatico-nao-basta` na memória do projeto.
   No checking final use `--fps 24 --max-video-mbps 14`.

## Quem fala: como decidir

A proporção 4/2 obriga a garimpar falas do apresentador, que em entrevista tem
poucos blocos longos — normalmente histórias pessoais e opiniões entre uma
pergunta e outra. No episódio 4 eles estavam em 08:06 (carro elétrico e os
haters), 09:58 (a bateria no dia a dia), 47:31 (quanto vale o seu plantão) e
54:24 (a molecada vai dominar o setor).

**Não tente diarização por áudio.** Foi tentado: os canais são idênticos, não há
`pyannote` nem `speechbrain` na máquina, e MFCC com k-means alternou o rótulo
dentro de uma mesma fala contínua, com margens de 0,02 a 0,5. Inútil para
decisão editorial. O que funciona é ler a transcrição e conferir a câmera.

**Confirme a capa.** Num corte do apresentador a câmera pode estar no convidado
em plano de reação — no episódio 4 isso aconteceu em 53% de um corte, e o
`pick_frame` escolheu a capa com a pessoa errada. Use `capa_ini`/`capa_fim`.

## Falhas conhecidas — todas já custaram um render

1. **Tela inteira magenta.** `blend=all_mode=screen` em YUV soma também os planos
   de croma. Os dois lados precisam de `format=gbrp` antes, e o
   `colorchannelmixer` também só faz sentido em RGB.
2. **Trilha mais alta que a voz nas pausas.** `loudnorm` em passada única é
   dinâmico: onde não há voz ele levanta a trilha até o alvo. Meça uma vez com
   `ebur128` e aplique ganho fixo com `volume=XdB`. Vale igual para o stem de
   voz, onde o loudnorm dinâmico levanta o ruído de sala das pausas.
3. **Medição de loudness falhando em silêncio.** `-af` não pode ser combinado com
   uma saída de `-filter_complex`: o `ebur128` precisa entrar dentro do grafo. A
   função que mede deve levantar erro quando não achar leitura — devolver 0,0
   faz os seis cortes renderizarem "com sucesso" sem normalização.
4. **`alimiter` desfazendo a normalização.** O auto-level vem ligado e reempurra
   o mix até o teto. Use `level=disabled`.
5. **Legenda sumindo.** Onde os dois falam por cima o alinhador devolve palavras
   com duração zero. Descartar esses blocos apaga fala do episódio — o
   `arruma_ritmo` estica, empresta tempo do vizinho e funde, mas nunca joga fora.
6. **Repetição real confundida com fala sobreposta.** A regra que trata
   crosstalk só pode valer para blocos vindos de tempo reparado (marcados com
   `reparado` pela preparação da transcrição). Sem essa trava ela come repetições
   de verdade do apresentador ("um moleque de 22, um moleque de 22").
7. **Palavra composta partida.** O transcritor quebra "ar-condicionado" em dois
   tokens e a legenda começa com hífen. Nunca quebrar antes de token com hífen.

## Trilha

`references/decisao_musical.md` traz a escolha por corte, com métricas medidas
(LUFS, BPM, centroide, LRA, crest) e a justificativa. A escolha é **por corte**,
não por episódio. As faixas estão em `assets/music`.

**Pendência de licença:** as faixas vieram do acervo local sem evidência de
licença item a item. Os nomes seguem o padrão do Pixabay (`autor-titulo-ID.mp3`)
e do Mixkit. Confirme a licença pelo ID antes de veicular como conteúdo
comercial. Isso está sinalizado como pendência, não como verificado.
