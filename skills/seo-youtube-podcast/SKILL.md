---
name: seo-youtube-podcast
description: Escreva o SEO de YouTube de um episódio de podcast (título, descrição com capítulos, hashtags e tags até 500 caracteres) no modelo já usado pelo cliente e casado com o gancho da thumb, e monte a thumb do episódio quando o cliente tiver template (Pod Acontecer). Use quando o usuário pedir "seo", "título/descrição/tags do YouTube", "tags de busca" ou "thumb do ep" de Pod Acontecer, Bombordo e Boreste, Autismo Cast ou outro podcast.
---

# SEO de YouTube para podcast

Pedido recorrente (Bombordo EP 01/02, Pod Acontecer EP 17/20/21/22/23, Autismo Cast). O
usuário sempre quer **o mesmo modelo dos episódios anteriores** e que **o título converse
com a thumb**. Nunca invente um formato novo.

## Fluxo

1. **Transcrição com tempo** do episódio **editado** (o que foi cortado não entra no SEO). Se
   não houver, gere uma rápida com a skill `transcricao-aulas` (modo rápido). Para achar
   capítulos, leia a transcrição em blocos `[hh:mm:ss] texto`.
2. **Carregue o modelo do cliente** em `references/<cliente>.md` e, se houver, o `SEO EP NN.txt`
   do episódio anterior na pasta do cliente. Siga a estrutura, o tom, o bloco fixo de rodapé
   (hosts, contato, CTA) e o padrão de título dele, trocando só o conteúdo.
3. **Gancho = título da thumb.** Se a thumb já existe, o título do vídeo começa pelo texto dela e
   depois amplia com os nomes pesquisáveis. Se não existe, proponha os dois juntos (e a
   demanda do designer sai pela skill `clickup-thumb-podcast` com o mesmo título).
4. **Confira nomes e grafias** (convidado, cargo, partido, empresa, cidade) na fala e na web.
   Quando o episódio traz duas grafias, use a oficial e ponha as variantes nas tags. Confira o
   número do episódio: no Bombordo a pasta `epN` é o "EP N-1" no YouTube; no Pod Acontecer,
   pergunte se houver dúvida ("o último foi o 19, esse é o 20").
5. **Escreva só o que está no corte final.** Não prometa no título algo que não aparece; se um
   trecho foi cortado a pedido (ex.: um assunto que a equipe pediu para tirar), ele não entra.
6. **Tags**: termos que o público busca, do mais específico ao mais geral: nome do convidado
   (com variantes de grafia), programa, temas do episódio, cargo, cidade/estado, ano. Conte
   com `scripts/contar_tags.py` (o YouTube soma 2 caracteres para cada tag com espaço). Quando
   o usuário pedir "500 caracteres de tags", preencha até 480–500 pela contagem do YouTube.
7. **Salve em TXT** na pasta do episódio (`SEO EP NN.txt`) com as seções `TÍTULO DA THUMB`,
   `TÍTULO DO VÍDEO`, `DESCRIÇÃO`, `TAGS DO YOUTUBE`, e mostre no chat para copiar.

## Thumb do episódio

- **Pod Acontecer**: regras completas em `references/pod-acontecer.md` (template, fonte exata
  Tusker Grotesk, fotos fixas dos hosts, par de hosts pronto do ep 18, convidado do bruto).
- **Frame do convidado**: de frente, sorrindo, olhos abertos, sem letreiro de rodapé (prefira a
  gravação bruta ao editado). Olhe a folha de contatos antes de escolher.
- **Nada gerado**: braço, ombro ou paletó faltando não se pinta nem se gera; pegue a peça
  pronta de outra thumb do mesmo template. O usuário reprovou todo remendo.
- Entrega em 1920×1080, PNG master + JPG para upload, e abra a pasta.

## Baixar as thumbs de um canal

`scripts/baixar_thumbs.py URL_DO_CANAL PASTA [--pular N]` baixa a maior versão pública de
cada vídeo (`maxresdefault`, 1280×720, com fallback). O YouTube não publica a resolução
original. O arquivo enviado (ex.: 1920×1080) só sai pelo YouTube Studio, logado como admin,
por isso não dá para baixar pelo navegador automatizado. As faixas pretas de algumas thumbs
baixadas são do letterbox do YouTube, não do design.
