---
name: legenda-cruzada
description: Verifique a legenda queimada de um vídeo já renderizado transcrevendo o áudio final de novo com um modelo mais forte e independente, e comparando palavra a palavra. Use depois do render e antes da entrega, sempre que houver legenda na tela; especialmente com convidado de sotaque não nativo, termo técnico ou nome próprio.
---

# Legenda cruzada — verificação por modelo independente

Revisar legenda lendo o próprio texto que a gerou não prova nada: o erro que passou na transcrição passa igual na revisão. Esta skill confere a legenda **contra o áudio que foi de fato entregue**, usando uma segunda transcrição feita por um modelo diferente e mais forte que o da produção.

## Regra que define a skill

**O modelo da conferência precisa ser mais forte que o modelo que gerou a legenda.** Conferir uma legenda feita com `whisper-large-v3-turbo` usando o próprio turbo valida quase nada — modelos distilados repetem os próprios erros, principalmente com falante de sotaque não nativo. A conferência usa `large-v3` completo; se a memória não permitir, usa a quantização de 8 bits do `large-v3`, **nunca** cai de volta para o turbo.

## Fidelidade: o que é erro e o que não é

Erro é o que o **modelo** ouviu errado: palavra trocada, termo técnico grafado errado, nome próprio, pontuação ausente, número quebrado ("50 %" em vez de "50%").

Não é erro o que o **falante** disse errado. Erros de português do entrevistado — concordância, regência, conjugação, palavra inventada, construção estranha — ficam na legenda exatamente como foram ditos. Legenda mais correta que o áudio quebra a sincronia entre o que se lê e o que se ouve, e descaracteriza quem falou. Na dúvida entre "ele falou assim" e "o modelo errou", mantenha o que está na legenda e registre a dúvida no relatório em vez de reescrever.

## Fluxo

1. **Extraia o áudio de cada MP4 entregue** (mono, 16 kHz). O áudio conferido é o do arquivo final, com música e mixagem — é ele que o espectador ouve, e é nele que um erro de sincronia ou uma legenda órfã aparece.
2. **Transcreva um arquivo por chamada.** O CLI do `mlx_whisper` sobrescreve a saída quando recebe vários arquivos de uma vez: 19 entradas resultaram em um único JSON com o conteúdo do último. Sempre `--output-name` explícito, um arquivo por vez.
3. **Use `--condition-on-previous-text False`.** Com o encadeamento de contexto ligado, uma transcrição longa entra em loop e degenera (um episódio de 50 minutos virou "É... É... É..." depois dos 21 minutos). Sem ele, o texto sai limpo.
4. **Compare palavra a palavra** com o texto queimado, normalizando caixa e pontuação, via `scripts/cross_check.py`.
5. **Classifique cada divergência** antes de corrigir:
   - os **dois** modelos concordam entre si e discordam da legenda → erro de transcrição, corrija;
   - só o modelo rápido diverge → ruído dele, ignore;
   - a divergência é uma palavra de apoio ("é", "a", "o", "que", "né") → ruído de segmentação, ignore;
   - a divergência é gramática do falante → mantenha.
6. **Corrija no JSON de legendas e re-renderize só os clipes afetados.** Depois confirme na imagem: extraia o frame no timecode do bloco corrigido e leia o texto na tela. Corrigir o JSON sem re-renderizar não muda o que foi entregue.
7. **Publique o relatório** com similaridade por clipe, contagem de blocos, divergências e a decisão tomada em cada uma.

## Critérios de bloqueio

- Similaridade abaixo de 0,85 em um clipe: investigue o clipe inteiro antes de liberar — normalmente é dessincronia ou trecho de outra fala, não palavra isolada.
- Bloco com mais de 18 caracteres, ou velocidade de leitura acima de ~22 caracteres por segundo: refaça a quebra.
- Legenda cobrindo boca ou queixo: reposicione a baseline; a legenda fica abaixo do queixo.
- Qualquer bloco não coberto pela comparação: a cobertura é de 100% dos blocos, não amostragem.

## Baixar o modelo em rede instável

O modelo de conferência tem alguns gigabytes e o download é a parte mais frágil do fluxo. Em link instável, a conexão morre sem fechar e o cliente fica pendurado esperando para sempre — o download parece "lento" quando na verdade está parado. Toda chamada de download precisa de detecção de travamento: com `curl`, `--speed-time 20 --speed-limit 20000` aborta quando a taxa cai abaixo de 20 KB/s por 20 segundos, e um laço externo reconecta a partir do byte já baixado. Numa medição real, o mesmo link saiu de 100 KB/s aparentes (com travamentos) para 273 KB/s só com essa correção.

Antes de culpar a banda, meça: `networkQuality -s` no macOS mostra a capacidade real e a responsividade. Se a capacidade for muito maior que a taxa observada, o problema é travamento, não banda — e paralelizar faixas de bytes não resolve travamento.

Baixe por faixas retomáveis e valide o tamanho final byte a byte antes de usar o arquivo; modelo truncado falha de formas confusas na inferência.

## Memória de máquina

Em Mac de 16 GB, o `large-v3` completo pode ser morto pelo sistema por falta de memória, sem deixar saída nenhuma. Rode um arquivo por vez, pule o que já tiver JSON pronto (para retomar de onde parou) e caia para a quantização de 8 bits quando o full não couber. Prever isso no script evita perder 40 minutos de fila.

## Uso

```bash
python3 scripts/cross_check.py \
  --videos "/caminho/06_entregas/Cliente" \
  --captions "/caminho/04_trabalho/_work" \
  --out "/caminho/05_qa" \
  --model mlx-community/whisper-large-v3-mlx \
  --fallback-model mlx-community/whisper-large-v3-mlx-8bit \
  --whisper /caminho/.venv/bin/mlx_whisper
```

`--captions` aceita a pasta com `captions_<clipe>.json` do motor de cortes ou arquivos `.srt` com o mesmo nome-base dos vídeos. O relatório sai em `<out>/legenda_cruzada.json` e `<out>/legenda_cruzada.md`.

## Repetição inventada pelo large-v3 em arquivo longo

Numa transcrição de 83 s, o `large-v3` completo escreveu "eu tenho certeza certeza que" onde a fala tinha um "certeza" só. O turbo e o próprio large-v3 no trecho isolado com contexto (±2 s) ouviram uma vez. Antes de legendar ou **cortar** uma repetição, transcreva o trecho isolado com os dois modelos. Só trate como gaguejada o que aparecer também ali, e confirme no envelope do áudio.
