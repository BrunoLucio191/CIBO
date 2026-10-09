# Regras transversais (valem para todo cliente)

Correções que o usuário repetiu em várias sessões e pastas diferentes. Estavam só em
memórias por pasta, que não carregam fora da pasta onde nasceram. Cada regra traz a origem.

## Antes de começar

- **Procure a skill antes de fazer.** "Procura skill ao invés de tentar fazer algo que já
  tá resolvido pela skill, faça isso sempre." Rodar um script solto de dentro da pasta de uma
  skill não conta: o valor está no SKILL.md, com as convenções e as falhas conhecidas. Se
  falta uma opção, estenda a skill e avise, em vez de escrever uma versão paralela. (Dr.
  Energia; Fernanda)
- **Procure o efeito em `assets/` antes de criar.** Quando o cliente pede outra cor, tinja o
  asset (`hue=h=...`, `colorchannelmixer` em `format=gbrp`) em vez de recriar o efeito: o
  burn-in feito do zero com `geq` custou dois renders no Dr. Energia.
- **Pergunte se o usuário já tem os tempos escolhidos** antes de fazer seleção editorial de
  um bruto longo ("na vdd eu tenho tempos escolhidos"). (Malu)
- **Execute você mesmo, em primeiro plano.** Não delegue o entregável principal a um fork em
  segundo plano respondendo "te aviso quando terminar". (Bombordo)
- **Entregue o resultado antes da análise.** Rode o pedido principal primeiro (mesmo numa
  amostra de 2–3 arquivos), mostre, e só depois faça triagem e diagnóstico. (fotos CONFEA)

## Durante o job

- **Temporários no SSD**, na pasta do projeto, nunca no disco de sistema (vive perto de
  100 %). Detalhes e o `taskpolicy` para encode em background: `video-render-optimizer`.
- **No máximo 2–3 ffmpeg em paralelo sobre 4K**, e um Whisper grande por vez: o Mac tem
  16 GB. Se o DaVinci estiver exportando, `nice` e modelo menor.
- **Dê progresso e tempo restante sem ser perguntado** em tarefa longa. "E aí", "falta
  quanto" e "tá editando mesmo?" são sinal de silêncio longo demais.
- **Pode instalar a biblioteca certa** em vez de improvisar ("não precisa fazer gambiarra").

## Regras editoriais de todo corte

- **Fala limpa** (skill `fala-limpa`): só a voz de quem fala, sem hesitação, sem palavra
  final cortada. Antes da legenda e de novo no QA.
- **Legenda fiel à fala.** Reproduza como foi dito, inclusive erro de português do
  convidado; corrija só o erro do transcritor (palavra trocada, termo técnico, nome próprio).
  (Thomas)
- **Legenda abaixo do queixo**, nunca sobre boca ou rosto. Meça o queixo ao longo do bloco
  inteiro, incluindo o auge de zoom. Se não couber, corrija o enquadramento, não a legenda.
  (Thomas, Katia, Bombordo, Malu)
- **Pente-fino de legenda com modelo grande** (`large-v3`, ou a versão 8-bit se faltar
  RAM), independente do que gerou a legenda: skill `legenda-cruzada`. Termos que o Whisper
  erra: zeólita ("ódio"), Bombordo ("Bom Bordo"), adsorve ("absorve").
- **O enquadramento só muda onde a câmera corta.** Um `cropx` por plano de câmera, nunca
  por trecho mantido. Um salto de 46 px numa emenda de áudio foi lido como "deslize".
  Prefira o quadro parado à câmera virtual que persegue o rosto. (Rodrigo, Dr. Energia)
- **Sem zoom digital além da escala nativa.** Gravação em 1080p não aguenta ampliação: o
  recorte de câmera usa a escala nativa (608×1080 para 9:16; o plano aberto entra inteiro no
  16:9) e o ken-burns do motor fica desligado (`ZOOM_AMT=0`) quando a fonte já é 1080p ou
  escura. Se o falante aparece pequeno no plano aberto, use o aberto, não um "close" ampliado.
  Rode `video-delivery-safety-check` (nitidez contra a fonte) antes de entregar. (João/Begrow:
  "a qualidade já não tá perfeita e você ainda dá esse close no João", 09/10/2026)
- **Burn no final: vídeo acaba seco e o burn passa do fim, sobre preto.** Como numa timeline
  com a trilha do vídeo e a do efeito por cima, terminando depois dela. O pico do burn cai no
  último quadro do vídeo; nada de fade nem de congelar a imagem. No `podcast-reels`:
  `scripts/burn_end.py`. Vale para qualquer cliente que use burn na saída. (podLilian, 09/10/2026)
- **Todo corte vertical leva trilha**, mesmo sem pedido. Biblioteca própria no SSD:
  `/Volumes/SSD/Music/Sound/Músicas edicao` e `/Volumes/SSD/Music/Projeto premiere/`
  (AMBIENTAÇÃO, IMPACTO, RISERS, HITS, ATMOSFERA, WHOOSHS). Escolha e nível pela skill
  `talking-head-music`. A biblioteca mistura faixas comerciais protegidas: para cliente,
  só o que tem direito de uso claro. (Rodrigo)
- **Loudness por ganho fixo medido**, nunca `loudnorm` dinâmico no mix ou na voz: ele
  levanta a trilha nas pausas até ficar mais alta que a voz. (Dr. Energia)
- **SFX só onde há mudança visual real** (entrada, saída e troca de referência), nunca no
  burn de abertura ou fechamento. Música e SFX em faixas separadas no arquivo editável.
  (Fernanda)
- **Zoom no vídeo**: keyframes estilo Premiere Easy Ease (cubic-bezier 0.33,0,0.67,1), sem
  mola nem overshoot, escala em espaço log, motion blur de 360°, segurar no nível do zoom.
  (Bombordo, Malu)
- **Capa**: a pessoa de frente, olhos abertos, sorriso ou boca fechada, nunca no meio da
  palavra, e pode vir de qualquer momento do episódio. Olhe a folha de contatos rotulada com
  o tempo real antes de escolher. Título e degradê só na parte de baixo, nunca sobre o
  rosto. A capa tem um frame só. (Bombordo, Katia, Dr. Energia)
- **Cortar bastidores**: conversa com a equipe, contagem, "deixa eu gravar outra", no começo
  e no fim. (Fernanda, Katia)

## Entrega

- **Nomes**: `NN - HEADLINE.mp4`, com acentos, numerados pela ordem da fala no episódio, e
  `CAPA - NN - HEADLINE.png` (prefixo, para as capas ficarem agrupadas no Finder). Nunca
  `corte01.mp4`. Troque `"` por `'`.
- **Pastas que ele lê de relance**: poucos níveis, nomes em português (`CORTES/Cortes ep1`),
  sem taxonomia numerada nem manifesto que ele não pediu. Nenhum arquivo temporário na
  árvore final. Rode `video-project-structure` no início e no fim, mas o nome das pastas de
  entrega segue esta regra.
- **Uma versão por vídeo** na pasta de entrega: sobrescreva ao refazer. Nada de v1/v2/final
  acumulando, salvo quando o usuário pedir uma pasta nova (ex.: "v2, sem sobrescrever").
- **Transcrição sempre com tempo** (`[hh:mm:ss - hh:mm:ss] texto` + SRT). Sem tempo, ele
  considera inútil. Skill `transcricao-aulas` para aulas e gravações longas.
- **Não diga que está bom antes de olhar.** O portão automático é piso: rode
  `caption-quality-gate`, `legenda-cruzada` e `video-delivery-safety-check`, olhe as contact
  sheets e **meça de novo depois de cada correção**, porque a correção costuma criar um
  defeito novo. O que não dá para verificar (ouvido, ritmo), diga que não verificou.
- **Abra a pasta no Finder ao terminar** (`open "<pasta>"`). Ele pediu isso em quase toda
  sessão.

## Depois de uma correção do usuário

- **A lição vai para a skill no mesmo turno**, não só para a memória: SKILL.md, bíblia do
  cliente, script ou checagem automática. Se a falha passou pelo QA, acrescente a checagem
  que faltou ao portão. Diga qual skill mudou.
- **Se a causa está no motor da skill, conserte o motor** (e procure o mesmo defeito no lote
  todo), não só os arquivos do job.
- **Código compartilhado entre clientes** (motor da Fernanda usado pela Malu; `face_crop.py`
  do Bombordo usado pelo Dr. Energia): mudança entra como opção por chave no job, e o outro
  cliente precisa sair idêntico (`framemd5` num trecho de 5 s, ou checksum da pasta).
- **Suba para o CIBO** (`~/CIBO`, `git@github.com:BrunoLucio191/CIBO.git`): copie a skill,
  confira o diff, atualize o README se a skill for nova, commit e push. Nada vai para
  `~/.codex/skills`.
