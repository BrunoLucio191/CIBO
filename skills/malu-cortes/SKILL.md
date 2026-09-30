---
name: malu-cortes
description: Edite os cortes verticais 9:16 da Malu (entrevista sobre a linha Zeo/Turi-Ita, câmera Sony em Rec.709, plano aberto com ela sentada e entrevistador fora de quadro) no padrão de Reel de marca premium de bem-estar editado por motion designer sênior — mapa de edição obrigatório, fala limpa, enquadramento por plano com rastreamento de rosto, kit de motion (título de gancho, lower third, números, callouts, cards), legenda Montserrat fina animada palavra por palavra, biblioteca de SFX curada, referências em tela dividida, tela cheia ou card, e pente-fino obrigatório antes do render. Use somente em trabalhos da Malu; o padrão da Fernanda continua na fernanda-produto e o do Bombordo na bombordo-boreste.
---

# Malu — cortes de entrevista

Motor: os scripts da `fernanda-produto` (`render.py`, `review_job.py`, `sync_captions.py`, `face_track.py`, `speech.py`, `find_pauses.py`). Esta skill define **o estilo e as regras da Malu**; nada daqui vale para a Fernanda nem para o Bombordo. O que vier de outra skill (a legenda animada e a altura da legenda do Bombordo) é adaptado aqui, sem alterar a skill de origem. Leia `references/client-content-bible.md` antes de começar. Modelo de job: `assets/job.malu.json`. Fontes: `assets/fonts/` (Montserrat Light, Regular e SemiBold, licença OFL).

## Direção criativa

O padrão é um **Reel de marca premium de bem-estar editado por um motion designer sênior**: elegante, fluido, com algo acontecendo o tempo todo, sem virar poluição visual. Estar correto não basta: o corte precisa de ritmo e acabamento. Nas palavras do usuário: "uma edição boa, parecendo que foi feita por um editor com anos de experiência e com um bom motion no geral".

Regras de ritmo (valem para o mapa e são conferidas no pente-fino):
- **Gancho nos primeiros 1,5 s**: título animado com a frase mais forte **dela** no corte, zoom de abertura e SFX de entrada. A pergunta da entrevistadora nunca aparece no reel, nem a voz nem o texto na tela, mesmo quando a janela de corte começa nela.
- **Mudança visual a cada 2 a 4 s** (plano, zoom, referência, gráfico ou destaque de legenda). Nunca mais de 5 s sem nada mudar.
- **No máximo 2 eventos de motion ao mesmo tempo** (por exemplo, zoom e destaque de legenda). Zoom, referência e gráfico juntos, nunca. A legenda normal palavra por palavra, a volta lenta do zoom e o push de respiro são fundo e não contam como evento; entrada de gráfico, destaque, zoom, referência e transição contam.
- **Todo evento precisa de motivo na fala**: ênfase, número, produto, mudança de ideia, punchline.

## Fluxo

1. **Fonte e estrutura** (`video-project-structure`): master em `01_sources/masters`, transcrição do master inteiro em `02_transcripts` (large-v3 com `--word-timestamps True --condition-on-previous-text False`).
2. **Seleção e fala limpa** (skill `fala-limpa`, obrigatória): só a voz dela. Em trecho curto e duvidoso, decida quem fala comparando o timbre (ECAPA) com uma amostra limpa da Malu e outra da entrevistadora: a auditoria sozinha errou "Uma limpeza" e "ou qualquer argila". Cortes: `scripts/cuts.py AUDIO16K IN OUT --cut A B ...` encurta toda pausa > 0,45 s para ~0,25 s e leva cada corte de conteúdo para o silêncio real. Confira no envelope de 10 ms os pontos em que o teste de áudio perde sílaba: o /s/ final e o fechamento do /t/ passam por silêncio ("testes", "feito", "jamais"). Corte a pergunta do entrevistador, comentários e vozes ao fundo. Corte hesitações e encurte pausas de pensamento (> 0,45 s → ~0,25 s, inclusive nas **emendas**: silêncio de saída + de entrada). Corte de silêncio a silêncio; queda curta no meio da palavra é consoante, não pausa.
3. **Teste só no áudio** dos trechos (`atrim`) com os dois modelos antes de qualquer imagem. Toda frase precisa sair inteira.
4. **Mapa de edição (obrigatório, antes de montar imagem).** Escreva `05_qa/<reel>_mapa_edicao.md`: uma tabela com uma linha por evento — tempo, trecho da fala, plano, motion, referência, gráfico, SFX e a **intenção** de cada escolha. Confira as regras de ritmo acima: nenhum buraco > 5 s, nenhum instante com mais de 2 eventos, todo evento com motivo. **Mostre o mapa ao usuário e espere o ok antes de renderizar a prévia.** Textos que não saem da fala (lower third, cartão final) são perguntados ao usuário, nunca inventados.
5. **Planos e enquadramento.** Trecho com menos de 1,2 s não vira plano: mantenha a pausa natural quando ela é dramática ("fica sem… chão") ou esconda o salto sob card/tela cheia (`review_job.py` aceita plano curto sob `malu_refs` card/full). Três níveis: 0 aberto (1500 px), 1 médio (1300), 2 fechado (1050 — no Instagram, exibido em 1080, é praticamente nativo). Escolha com intenção: aberto quando começa uma ideia, fechado na ênfase/punchline. Nenhum nível repetido lado a lado; nada de A/B/A/B mecânico. Plano ≥ 1,2 s.
6. **Rastreamento de rosto** (`face_track.py job.json --debug qa/face_track.mp4`, depois `--apply`): matriz no rosto; olhos a ~1/3 da altura; espaço de olhar do lado para onde ela olha (ela olha para a **direita**, onde fica o entrevistador). Plano parado fica **travado**; plano em que o rosto sairia da zona segura é **seguido** com zona morta e amortecimento. Mostre o vídeo de diagnóstico quando o usuário quiser conferir. A posição do queixo por plano também sai daqui e define a altura da legenda.
7. **Referências** — ver seção própria. Entram e saem **no próprio corte** ou no centro de uma pausa real, nunca a menos de 1,2 s de um corte.
8. **Zooms** (estilo aprovado): entrada de 0,3 s, volta lenta de ~6 s, **motion blur de câmera com shutter angle 360°** (`camera.py`, até 16 subquadros por quadro em movimento), como o efeito Transform do Premiere. Nunca use mistura de quadros (`zoom_blur`/`tmix`: fantasma de mão e boca, "blur estranho"). **Zoom ancorado no rosto** (`zoom_center_face: true`, `zoom_amount: 0.14`, posição do rosto por plano vinda do `face_track.py --apply`): os olhos ficam na mesma altura e o rosto vai do espaço de olhar para o **centro exato** no auge ("a convidada não tá 100% centralizada no zoom"). Varie o tipo: **punch-in rápido** na ênfase/punchline (`camera_moves` `punch`) e **push-in lento** em ideias que crescem (`push`); plano longo sem zoom leva `breathe` de 2 a 3%. Um zoom de abertura em t=0; os outros em começo de frase, dentro de plano contínuo, a ≥ 0,5 s de corte e sem encostar em referência.
9. **Kit de motion** — ver seção própria.
10. **Legenda** — ver seção própria.
11. **SFX** — ver seção própria.
12. **Áudio.** Arquivo editável com três faixas (`sfx_separate: true`, `edit_suffix: "voz, musica e sfx separados"`): A1 voz, A2 música, A3 SFX. O "mix pronto para postar" tem tudo junto. Música *Motivating Mornings* a `-27.5` dB, `duck_threshold: 0.015`. **Backtiming**: o final natural da faixa coincide com o fim do reel (`offset: "auto"`); no início, entra com fade curto; leve crescendo no gancho e no encerramento. `tail_hold: 0.8` (a última palavra nunca é engolida pelo fade). Mix final a **-14 LUFS integrado, true peak -1 dBTP**. Use `lufs: -13` no job: o limitador do `render.py` come ~1 LU depois do ganho (no reel 01, `-14` entregou -15,0 e `-13` entregou -14,1).
13. **Pente-fino antes do render (obrigatório)**: `review_job.py` com a transcrição do áudio editado (large + turbo) e `audit_fala.py` na fonte com o job. Só renderize com **0 bloqueios**; cada aviso restante precisa de uma decisão de editor registrada (`cortes_revisados`, `caption_pins`).
14. **Prévia e pente-fino de motion.** Renderize a prévia (`render.py job.json preview INICIO DURACAO`, 1080×1920). Extraia frames **no meio de cada movimento** (zoom, entrada de gráfico, transição de referência, destaque) e monte folhas de contato (`kinetic/cli.py job.json sheet PREVIA SAIDA.jpg --start T0`). Confira: motion blur natural (sem fantasma), rosto e legenda na zona segura, gráfico sem cobrir o rosto, nenhum trecho parado demais nem poluído demais. **Só depois peça o ok do usuário para o render completo.**
15. **Render** (`render.py prep/check/render`, em background com vigia de CPU) e **QA** no arquivo final: `video-delivery-safety-check`, `caption-quality-gate`, `fala-limpa` no áudio final, `legenda-cruzada`. Um arquivo de 0 bytes ou incompleto em `06_deliverables` nunca fica lá: se o render travar, apague a saída parcial e registre.

## Kit de motion

Toda animação usa **ease in e ease out como no Premiere** (`cubic-bezier(0.33, 0, 0.67, 1)` ou mais suave), **sem spring e sem overshoot**, com **motion blur de câmera em shutter angle 360°** em tudo o que se move. Os gráficos são renderizados em camada transparente (skill `motion-graphics` com Remotion quando disponível, exportando ProRes 4444 ou WebM com alfa) e compostos pelo `render.py`.

- **Câmera que respira**: em plano longo sem zoom, push-in lento de 2 a 3% ao longo do plano. Nada fica 100% parado.
- **Zooms**: o estilo aprovado do fluxo (item 8), variando entre punch-in e push-in.
- **Título de gancho**: 1 a 2 linhas em Montserrat, revelado por máscara com blur, sai com fade e blur antes de 2,5 s.
- **Lower third** na primeira aparição da Malu: nome e função (pergunte o texto ao usuário), entrada suave, sai em 3 s.
- **Números e prazos** ("40 dias"): número grande animado por 1 a 1,5 s.
- **Linhas de produto** (premium, gold, silver, standard): callout ou lista animada quando ela compara. Mostre só o que ela afirma; ela troca os nomes às vezes (ver bíblia).
- **Transições de referência**: varie entre tela dividida com deslize, tela cheia com push lento e card flutuante com cantos arredondados e sombra suave.
- **Troca de layout nunca em corte seco** ("deixa o vídeo feio e amador"): film burn vermelho do arquivo do usuário (`scripts/burn.py`, `burn_events`, `burn: true`) com o pico de luz exatamente no corte, em toda saída de tela dividida/card/tela cheia e em toda entrada de tela cheia; alterne os burns B9, B13, B10, B12 e B4. A tela dividida entra com deslize e o card com a própria animação. O som do burn vai para a trilha de SFX (evento com `src`). Jump cut com troca de nível dentro da mesma fala continua seco.
- **Encerramento**: o último quadro dela desfoca em fade (`malu_refs` `endbg`), a música termina no fim natural e o vídeo sai em fade. **Sem cartão final de produto e sem card com o recorte dos pacotes Turi-Ita**: o usuário reprovou os dois em todos os cortes (o recorte fica mole ampliado).
- **Unidade visual**: grão de filme bem sutil e o mesmo tratamento de cor sobre tudo (câmera, referências e gráficos), para colar as fontes diferentes.
- **Proibido**: shake, glitch, transições de template, emojis, cores fora da paleta da bíblia. Exceção pedida pelo usuário: o film burn vermelho nas trocas de layout.

## Legenda

- **Montserrat fina**: Regular no texto e SemiBold no destaque, substituindo DM Sans + Playfair. No teste do reel 01, a Light branca sumiu sobre a estante clara ("da Turi-Ita", tela dividida); por isso o padrão é Regular com sombra suave e halo escuro largo (`halo_alpha`). Use Light só sobre fundo escuro, conferindo na prévia. O destaque é **contido**: 1,3x (faixa de 1,2 a 1,4x), nunca os 2x do Bombordo.
- **Pontuação na tela**: saem vírgula, ponto, aspas, dois-pontos e reticências; ficam "?" e "!". Nunca saem o hífen dentro da palavra ("Turi-Ita"), acentos, números, "%" e "R$". Depois de qualquer mudança no motor, confira no render que "Turi-Ita" saiu certo.
- **Animação palavra por palavra** adaptada do Bombordo (ver "Motor da Malu"): deslize com blur, queda vertical e revelação por máscara, todos em Easy Ease. A palavra aparece ~1,5 quadro antes do som, a palavra falada ganha a cor de destaque da paleta, e o micro-movimento é só respiração de escala (~1,2%). **Sem** `pop_spring` nem `ease_out_back`: o destaque entra como unidade, com zoom suave de 1,06→1 e blur. Cores da paleta da bíblia, nunca o azul do Bombordo.
- **Altura logo abaixo do queixo**, pelo queixo medido no vídeo já com zoom (o zoom de 14% desce o queixo). Nunca cobre o rosto e respeita a área segura do Reels (coluna de botões à direita, faixa de baixo). Em tela dividida e card, a legenda segue a regra do layout.
- **Camada sem perdas**: QuickTime Animation RGBA. Se um dia ela virar H.264 cor + máscara, a máscara tem que ser qp 0 e a cor yuv444p; a Light é fina e serrilha com compressão.
- Mantém: texto revisado à mão (quebra por sentido, linha ≤ 26 caracteres, nunca terminar linha em palavra funcional), `sync_captions.py` para colocar cada bloco no ataque real da fala, 6 a 8 palavras-chave (destaques) por minuto escolhidas pelo sentido. Casos que nenhuma regra resolve: `caption_pins` (tempo do original).

## SFX: biblioteca curada da Malu

Substitui o whoosh e o clique fixos da `fernanda-produto`. A biblioteca fica em `assets/sfx/` desta skill e é reaproveitada em todos os cortes da Malu.

- **Categorias**: whoosh suave (zoom e entrada de referência), swish curto (texto), riser (antes do gancho ou da punchline), impacto suave e grave (revelação de número), pop ou clique discreto (palavra-chave), brilho (produto) e foley ligado à imagem (água caindo no copo, pó, respiração).
- **Fontes**: Freesound (só CC0), Pixabay e Mixkit. Confira a licença de cada arquivo e registre fonte, URL e licença em `assets/sfx/licencas.csv`. Se precisar de chave de API, peça ao usuário.
- **Seleção**: baixe de 4 a 6 candidatos por categoria e filtre por análise: sem ruído de fundo, sem voz (rode o Whisper para conferir), ataque limpo, duração compatível.
- **Aprovação**: como você não consegue ouvir, monte uma audição (vídeo com cada candidato numerado na tela) para o usuário aprovar a biblioteca **uma única vez**. Só os aprovados entram em `assets/sfx/`.
- **Uso**: o pico do whoosh cai no ponto mais rápido do movimento; SFX nunca por cima de consoante da fala; nunca o mesmo arquivo duas vezes seguidas; foley só quando a imagem justifica; em média 1 SFX a cada 3 a 5 s. `sfx_db: -8` é o ponto de partida; `whoosh_post: 0.1` e `click_lead: 0.3` continuam valendo (a fala dela volta colada nos cortes).

## Referências

- Busque no **Pexels, Pixabay e Mixkit**, sempre em inglês e com descritores visuais: *close up, slow motion, macro, soft natural light, shallow depth of field*.
- Baixe de 5 a 8 candidatos por trecho, monte uma folha de contatos com 3 frames de cada e dê nota (`semantic-broll-validator`) para: relação com a fala, estética cinematográfica, cor compatível com o estúdio (quente e suave), recorte 9:16 e movimento dentro do plano.
- **Recuse**: cara de banco de imagem (gente sorrindo para a câmera, fundo branco), marca d'água, texto na imagem, imagem escura ou estourada, baixa resolução.
- Literal para coisas concretas, metáfora visual para ideias abstratas.
- **Inserts do próprio master em 4K**: só quando o recorte for grande (o copo na mão, as mãos). O card com os pacotes Turi-Ita da estante foi reprovado (região pequena, fica mole).
- Aplique o tratamento de cor e o grão do kit de motion e conforme para 29,97 fps.
- Tela dividida: `ref_push: 0.06` (push lento no painel), `shift: 1150`.
- **Entrega em Full HD** (1080×1920, ~12 Mb/s: `out_size: [1080, 1920]`, `vbitrate: "12M"`), não em 4K. O processamento interno continua em 4K; o usuário pediu "exporta em fullhd somente" quando o render 4K demorou.
- **Resolução decide o layout**: tela cheia só com fonte 4K (1080p ampliaria 3,6× no 4K); 1080p e 720p vão em tela dividida ou card. O Mixkit gratuito tem muito vídeo só em 720p.
- Na tela cheia a legenda ganha faixa escura em degradê atrás (automática na camada): o dourado some sobre stock claro.

## Nunca mais (erros reprovados)

- Reel entregue sem a explicação central (a antiga cortou "a silver e a standard são mais grossas").
- `keywords` inflada (23+ palavras com pontuação), destaque caindo em "marido".
- Voz do entrevistador antes de "É a micronização"; "vai preparando o corpo" (pessoa ao fundo). Atenção: "ou deixa sair, né?" é da Malu (conferido por timbre); cortar isso deixou a fala do Thomas pela metade e o usuário reclamou.
- "Eeee" de hesitação, pausas de 0,8 s nas emendas, palavra final engolida pelo fade.
- Zoom começando 0,07 s depois de um corte; referência saindo 0,2–0,6 s antes de um corte; pingue-pongue de enquadramento.
- Blur de zoom por mistura de quadros (fantasma) e zoom no centro do quadro com o rosto fora do centro.
- Legenda entrando 0,3–0,6 s fora da fala por confiar no tempo do Whisper.
- Edição correta mas sem ritmo nem acabamento: trechos de 5 s ou mais sem nada mudar, plano 100% parado, evento sem motivo na fala.
- Render travado deixando arquivo de 0 bytes em `06_deliverables` (v10 do reel 01).
- Flash de 1 quadro na emenda (plano seguinte com o enquadramento do anterior): o `camera.py` decide o plano pela contagem exata de quadros do trim, nunca pelo tempo arredondado.
- Palavra final comida pelo `out` ("desconforto" sem o "-to"): confira no envelope o fim real da última palavra.

## Motor da Malu (scripts desta skill)

Ligado só no job da Malu; o `render.py` da `fernanda-produto` chama tudo no `prep`. Sem as chaves abaixo o grafo da Fernanda é idêntico ao de antes (conferido quadro a quadro e no PCM da voz e da música). Nada do Bombordo foi alterado: o código veio por cópia adaptada.

- **`camera_engine: "malu"` → `scripts/camera.py`**: cortes, enquadramento por plano (face track), zooms, push-in e respiro saem da fonte 4K num warp só, com Easy Ease `cubic-bezier(0.33,0,0.67,1)`, escala em log e shutter 360° (até 16 subquadros). O resultado é `<work>/camera.mov` (ProRes 422 HQ), reaproveitado enquanto nada muda (impressão digital em `camera.json`). Movimentos em `camera_moves`: `{"t", "kind": "punch"|"push"|"breathe", "amount", "in", "until"}`, em tempo editado; sem essa chave, os `smooth_zooms` viram `punch`. Leva ~9 min por reel de 50 s num M4 e usa ~0,6 GB. O grafo antigo do zoom (escala 4K repetida por janela) travou o v10 com 11 GB.
- **`caption_engine: "kinetic"` → `scripts/kinetic/cli.py job.json words|blocks|chin|layer|all|sheet`**:
  - `words`: tempo por palavra, com o texto do `captions.json` e o tempo do Whisper do áudio editado (`word_timing`), ajustado no ataque só depois de pausa real e com o master em 16 kHz (`audio16k`).
  - `blocks`: gera `<work>/kinetic/blocks.json`, editável. Divide os blocos pelo conjunto da frase: nunca separa "40 dias", nunca termina bloco em artigo, "não" ou demonstrativo, e as quebras feitas à mão são fronteiras. O destaque vem com a palavra pequena por cima.
  - `chin`: mede o queixo no `camera.mov` e gera `<work>/chin_track.json` e `kinetic/chin_sheet.jpg`.
  - `layer`: gera `<work>/kinetic_caps.mov` em QuickTime Animation, RGBA sem perdas.
  - `sheet`: gera a folha de contatos com o meio de cada entrada, destaque, saída e zoom.
  - Destaques pelo sentido: `kinetic.highlights`, em ordem de fala; `"Toxina#2"` indica a segunda ocorrência.
  - Configuração: `kinetic/config.json` + `job["kinetic"]` + `<work>/kinetic.json`.
- **Altura da legenda**: cada bloco fica abaixo do queixo mais baixo do tempo em que está na tela, incluindo o auge do zoom, com folga para a entrada e a saída. Dentro de um plano a altura é a do bloco mais exigente, então a legenda só muda de altura no corte. Na tela dividida vale `position.split_cy`, e outros layouts vão em `caption_layouts` (`start`, `end`, `cy`, `kind`). Nenhum bloco fica na tela durante uma troca de layout. Se a zona segura de baixo vencer, a camada lista o bloco. Relatório em `kinetic/positions.json`.
- **Queixo**: `chin_track.py` ignora os quadros de referência (não é o rosto dela) e descarta falso rosto isolado (mão/copo que foge 0,6 altura de rosto da mediana dos vizinhos).
- **Mapa**: `scripts/mapa.py job.json 05_qa/<reel>_mapa_edicao.md` monta a tabela de eventos e mede o maior trecho sem mudança visual.
- **Gráficos** (`job["graphics"]`): `title`, `callout` (pílulas empilham quando não cabem), `number` (unidade longa vai embaixo; `big_px`/`unit_px`/`cy` configuráveis — sobre o rosto dela, nunca: no plano dela o número vai pequeno e em linha única no alto, acima da cabeça, como "150 milhões de anos" no reel 04), `endcard` (recorte do master sem o ombro: `[1760, 1860, 400, 533]` em 47,5 s).
- **Ainda não construído** (fazer antes de usar): lower third (falta o texto: nome e função), audição da biblioteca de SFX com o usuário e a regra "SFX nunca sobre consoante" dentro do `review_job.py` (hoje o `audio.py` já desvia os picos das consoantes).
