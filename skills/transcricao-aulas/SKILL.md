---
name: transcricao-aulas
description: Transcreva, organize e resuma gravações longas de aulas, cursos, lives e mentorias (várias horas, muitos arquivos) com rapidez e pouca RAM, sempre com marcação de tempo, separando por aula/módulo/bloco, achando intervalos (café, almoço, manhã/tarde) e entregando numa estrutura pronta para subir no Drive, com sumário. Use quando o usuário pedir transcrição de curso/aula/pós/live, "onde tem intervalo/pausa", "em qual módulo essa aula se encaixa", ou organizar/renomear/juntar/dividir arquivos de aula (Andrea Francomano, Fernanda Ben/IFB e outros).
---

# Transcrição e organização de aulas longas

Pedidos recorrentes: 7 Chaves (Andrea), Pós 5 do IFB (Fernanda Ben, ~60 h), nutrição módulo 4,
aulas Live, meditações ao vivo. O usuário quase sempre tem **pressa** ("eu quero isso rápido",
"eu não tenho esse tempo todo") e o Mac tem **16 GB de RAM**, muitas vezes com o DaVinci
exportando ao mesmo tempo.

## Primeiro: o que ele quer de verdade?

| Pedido | O que fazer | Ferramenta |
|---|---|---|
| "onde tem intervalo/pausa", "separar manhã e tarde" | **não transcreva tudo**: varra o áudio e confirme só as bordas | `achar_intervalos.py` |
| "em qual módulo/tema essa aula se encaixa" | transcreva **só 3–4 trechos de 2 min** (começo, meio, fim) em modo rápido e compare com a lista de módulos | `transcrever_lote.py --modo rapido` num recorte |
| transcrição completa do curso (demanda com critério de conclusão) | lote completo, formatado, revisado, com sumário | fluxo completo abaixo |
| "transcrição de maior qualidade" | `--modo normal` com glossário, ou `qualidade` (large-v3) se houver tempo e RAM | idem |

Leia a demanda inteira e releia antes de entregar: "tem agora tudo que a demanda pede?" foi
perguntado mais de uma vez. Se ela pede sumário, o sumário faz parte da entrega.

## Fluxo completo

```bash
PY=~/.local/share/uv/tools/mlx-whisper/bin/python     # python com mlx_whisper
S=~/.claude/skills/transcricao-aulas/scripts
# 1. transcrever (em série, retomável; progresso e previsão em SAIDA/progresso.log)
$PY $S/transcrever_lote.py "PROJETO/Transcrições/_brutas" "PROJETO/aulas" --modo rapido \
    --glossario "zeólita, metilação, terreno biológico, Hulda Clark, ..."
# 2. formatar: TXT com [hh:mm:ss - hh:mm:ss] a cada ~20 s + SRT, pausas longas marcadas
python3 $S/formatar.py "PROJETO/Transcrições/_brutas/"*.json --saida "PROJETO/Transcrições" \
    --correcoes correcoes.json
```

1. **Inventário**: liste os arquivos com duração, detecte duplicatas (mesmo conteúdo com `_v1`,
   `(1)`) e aulas divididas em partes. Mapeie cada arquivo para a aula/módulo **pelo conteúdo**
   (data dita na fala, tema, professor, contagem de aulas por produto), não pelo nome: os
   arquivos do Vimeo têm outro nome e outra numeração que a plataforma (o "Módulo 11" do Vimeo
   era "Estratégias integrativas no Câncer" na Academy). Bônus de outra turma entra. Pergunte só
   o que for realmente ambíguo.
2. **Modo**: `rapido` (turbo com áudio a 1,3×) para cumprir prazo; `normal` para leitura
   pública; `qualidade` (large-v3) só quando pedirem e houver RAM. Com vídeo, pode usar a versão
   240p ou só o áudio: o que importa é o som.
3. **Glossário**: nomes de professores, autores e termos técnicos do curso em `--glossario`.
   Depois da primeira passada, junte os erros recorrentes em `correcoes.json`
   (`{"zelita": "zeólita"}`) e rode o `formatar.py` de novo. É barato e não retranscreve.
4. **Revisão**: leia uma amostra de cada arquivo. Onde o texto estiver estranho, retranscreva
   só aquele trecho com o `large-v3` e corrija. Não entregue sem ler.
5. **Sumário** (`00 - SUMÁRIO.md`): por aula/módulo, com a duração, os tópicos principais e o
   tempo `[hh:mm:ss]` onde cada tópico começa. Escreva lendo as transcrições, sem inventar.
6. **Entrega pronta para o Drive**, dentro da pasta do cliente/tarefa:
   ```
   <Curso>/Transcrições/
     00 - SUMÁRIO.md
     01 - Módulo 00 - Aula 1 - 25-01-2025 manhã.txt   (+ .srt)
     02 - ...
   ```
   Nomes padronizados, na ordem do curso, poucos níveis. `_brutas/` (JSON) fica fora da pasta
   de entrega ou é apagada. Nenhum temporário na árvore. Abra a pasta no fim.

## Regras de execução (aprendidas a duras penas)

- **Um whisper por vez.** Dois modelos grandes em paralelo esgotaram a RAM e foram mortos. O
  `transcrever_lote.py` já roda em série. Se o usuário avisar que o DaVinci está exportando,
  use `--modo rapido` e `nice -n 10`.
- **Temporários no SSD**, na pasta do projeto (`--tmp`), nunca em `/private/tmp`: o disco de
  sistema vive quase cheio e já travou uma transcrição.
- **Retomável**: cada bloco pronto fica em cache. "Pausa aí", SSD desconectado ou RAM: pare, e
  ao rodar de novo ele continua. Para voltar numa sessão futura, diga o comando exato.
- **Dê o progresso sem ser perguntado** (o log tem a previsão). Horas de áudio: avise antes
  quanto tempo e memória vai levar.
- **Sempre com tempo**: texto corrido sem `[hh:mm:ss]` o usuário considera inútil.

## Intervalos e cortes para o DaVinci

`achar_intervalos.py GRAVACAO --min 3 --inicio-timeline 01:00:00:00 [--janelas]` lista cada
silêncio longo com o tempo da gravação e o timecode para colar no DaVinci (a timeline começa em
01:00:00:00). `--janelas` transcreve 1 min de cada lado para confirmar "vamos para o café" /
"voltando". Quando ele pedir conta ("soma 2 h nisso", "voltou 5:20:10"), faça só a conta
pedida, no formato `HH:MM:SS:FF`.

Aulas com blocos de professores diferentes (ex.: 2 blocos da Fernanda e 2 do professor Luiz):
entregue a minutagem de início e fim de cada bloco, e os intervalos entre eles, para ele cortar.

## Organizar, renomear, juntar e dividir

- **Renomear** pelo padrão que ele der ("Meditação ao vivo dd/mm/aaaa"; troque "/" por "-" no
  nome do arquivo). Confira o tipo antes ("é meditação ao vivo, não reunião ao vivo").
- **Juntar partes** da mesma aula: a maior costuma ser a primeira; confirme pela fala.
  `ffmpeg -f concat -safe 0 -i lista.txt -c copy` quando os codecs batem; senão re-encode.
- **Dividir** num tempo: `-ss/-to` com `-c copy` corta no keyframe mais próximo; para corte
  exato, re-encode com `video-render-optimizer`. Nome: o original + " - parte 1" / " - parte 2".
- **Apagar** arquivos só com confirmação do usuário, mostrando a lista.
- Arquivo grande para Hotmart/Drive: reduza o bitrate com `video-render-optimizer`.
