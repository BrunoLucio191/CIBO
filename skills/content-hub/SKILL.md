---
name: content-hub
description: Crie cortes verticais 9:16 para Reels, TikTok e Shorts da Content Hub, com identidade, seleção editorial, tratamento de áudio e transições próprios deste cliente. Use somente em trabalhos da Content Hub.
---

# Content Hub → Cortes verticais

Produza cortes finalizados a partir de vídeos master e seus SRTs, sem misturar identidade ou arquivos de outros clientes.

## Antes de editar

1. Confirme que o trabalho é da Content Hub. Não use esta skill para Autismo Cast ou Bombordo e Boreste.
2. Leia [references/brand-profile.md](references/brand-profile.md) antes de decidir capa, cores, logo, formato editorial ou organização no Drive.
3. Leia [references/media-policy.md](references/media-policy.md) antes de pesquisar ou aplicar B-roll, overlay, música ou SFX.
4. Leia e atualize [references/client-content-bible.md](references/client-content-bible.md) e [references/asset-source-catalog.md](references/asset-source-catalog.md). Estes documentos são memória canônica do cliente e devem acompanhar a skill no Drive.
5. Leia o SRT como transcrição agrupada em blocos de aproximadamente 15 s. Escolha os momentos pelo texto antes de revisar imagem e enquadramento.
6. Identifique entrevistador e convidados pelo fluxo da conversa. Os cortes priorizam a fala e a imagem dos convidados; mantenha perguntas apenas quando forem necessárias para contexto.
7. Verifique os assets entregues para o job. Nunca reutilize logo, patrocinador, vinheta, música, headline ou referência visual de outro cliente.
8. Antes de renderizar, sincronize `Content Hub/02 - Assets` do Drive com `assets/` local e confira `assets/ASSETS_MANIFEST.md`. O Drive é a fonte canônica dos assets reutilizáveis deste cliente; não use arquivos homônimos de outras skills.
9. Audite a estrutura com `video-project-structure`. Fontes, trabalho, QA, entregas e manifests precisam estar separados; não mova caminhos ativos sem atualizar jobs.

## Regra de entrega por gravação

Quando o usuário pedir cortes das gravações SEBRAE, produza **dois cortes por gravação válida**, ignorando testes ou arquivos corrompidos/curtíssimos. Cada corte deve ter gancho nos primeiros 3 s, uma ideia autônoma e conclusão semântica. Leia pelo menos os 10–20 s seguintes da transcrição antes de fechar o fim.

Organize as entregas em uma pasta por nome do convidado. Se uma gravação tiver mais de um convidado, arquive cada corte sob o participante que protagoniza o trecho. Não use nomes genéricos quando a identidade puder ser confirmada pela gravação, transcrição ou materiais do projeto.

Use 35–60 s como faixa normal e adapte ao pensamento completo. Um bom corte da Content Hub ensina, demonstra, provoca, mostra bastidor ou comprova resultado com clareza e autoridade.

## Áudio: escolha uma das três camadas

Masters OBS podem conter `both`, `main` e `holly`. Não misture as três. Analise as faixas, selecione **uma só** por gravação e registre a escolha. Favoreça voz do convidado inteligível, baixa reverberação/ruído, ausência de clipping e nível estável; `both` não é automaticamente a melhor.

Trate a faixa escolhida com `scripts/audio_select_enhance.py`, usando Pedalboard para filtro passa-altas, compressão, ganho e limiter. A redução de ruído deve ser moderada para não metalizar a voz. Compare o antes/depois por escuta e valide picos antes do render.

SNR, ruído e clipping apenas classificam qualidade; não provam que a faixa pertence ao convidado em imagem. Antes de aprovar, transcreva uma amostra de cada candidata no mesmo timecode e compare com o SRT/contexto e com o movimento labial. Rejeite qualquer faixa semanticamente divergente, mesmo que tenha a melhor pontuação técnica. Registre `semantic_match`, trecho comparado e decisão no relatório. Se a automação não puder confirmar correspondência, a escolha fica `REVIEW_REQUIRED`, nunca aprovada automaticamente.

Faça QA rigoroso em quatro etapas: (1) compare métricas das três faixas; (2) escute amostras A/B em fala baixa, fala forte e pausas; (3) verifique voz natural, ruído, reverberação, clipping, sibilância e sincronismo; (4) repita a escuta no MP4 final depois de música, SFX e codificação. Se a redução de ruído criar voz metálica, bombeamento ou cortes de final de palavra, alivie o gate/processamento. Qualidade e naturalidade da voz têm prioridade sobre silêncio absoluto.

## Pipeline

O job é controlado por `job.json`; veja `assets/job.example.json`.

Na primeira utilização em uma máquina nova, crie `.venv` e instale `requirements.txt`. FFmpeg e FFprobe também precisam estar disponíveis no sistema.

1. Defina `src`, `master_in`, `headline`, `cover_t` e `keeps` para cada corte.
2. Remova repetições, falsos começos e silêncios, preservando orações inteiras. As bordas internas são ajustadas automaticamente ao silêncio.
3. Rode `face_crop.py` e revise a prévia. Use `cropx_timeline` por plano; não siga o rosto quadro a quadro.
4. Detecte as trocas reais de câmera. Use o asset oficial `assets/film_burn_clean.mp4` de forma seletiva, com seu SFX abaixo da voz. Todo split-screen deve entrar e sair escondido por um film burn curto; não use fade e não use film burn para esconder corte semântico ruim.
5. Defina `letterings` independentes para números, conceitos e frases-chave. Defina `broll` somente depois de validar a relação com a frase completa e seu contexto. O layout padrão usa o B-roll no topo e desloca o talking head para baixo, preservando escala natural e rosto/tronco.
6. Revise uma amostra curta ou contact sheet antes do render final.
7. Renderize:

```bash
JOB=job.json ~/.codex/skills/content-hub/.venv/bin/python3 \
  ~/.codex/skills/content-hub/scripts/make_reels.py
```

## Regras visuais e técnicas

Antes do primeiro render em uma máquina ou perfil novo, use a skill `video-render-optimizer`: detecte GPU e encoders FFmpeg, faça benchmark CPU × hardware em 8–15 s do material real e escolha por velocidade, SSIM, compatibilidade e bitrate. Para 1080×1920/30, comece em 6–8 Mb/s com teto de 10 Mb/s; confirme o bitrate real no MP4 final. Não use GPU automaticamente se ela inflar o arquivo ou perder qualidade.

- Toda entrega tem capa. Use `assets/logo_content_hub_transparent.png`, headline coerente com o trecho e Montserrat em CAIXA ALTA. Centralize visualmente a pessoa, preserve olhos/queixo e mova a logo para o lado oposto ao rosto quando necessário.
- A assinatura da capa é exclusiva da Content Hub. Use thumbnails apenas como repertório de composição e compare a direção com o registro de capas dos demais clientes; não reutilize estrutura visual.
- A identidade é azul profundo com acento laranja. Palavras enfatizadas e a barra da capa usam o laranja da marca.
- Legendas têm no máximo 18 caracteres por bloco, até duas linhas, baseline compartilhada e correção manual do português.
- Lettering não é legenda ampliada. Use Montserrat ExtraBold/Black, card azul profundo, acento laranja e popup eased curto no canto inferior esquerdo ou em outra área negativa segura. Mostre de uma a duas peças por corte, sincronizadas a números, contrastes ou teses, sem cobrir rosto ou legenda. O card deve medir o texto, ampliar largura/altura e quebrar linhas automaticamente; nunca trate `width` como caixa de corte. Bloqueie o render se qualquer glyph sair da safe box ou se a posição renderizada divergir de `side`/`y` do job.
- O enquadramento é vertical 1080×1920, consciente das trocas de câmera e centrado no convidado.
- Clicks e movimentos marcam poucos pontos semânticos. Não aplique click na palavra de abertura.
- Música precisa ser licenciada/aprovada, ficar abaixo da fala e usar ducking. Faça um brief e uma escolha independentes para cada corte, incluindo assunto, subtexto, arco emocional, energia, velocidade da fala, duração e objetivo. Compare 3–5 candidatas no trecho real, selecione também um `music_offset` que comece em uma seção útil e registre a decisão; nunca escolha apenas pelo gênero ou por audição isolada.
- B-roll precisa passar por validação semântica: leia a oração completa e pelo menos uma frase antes/depois, classifique usos literais e figurativos, descreva em uma frase o que a imagem prova e rejeite correspondência baseada apenas em palavra-chave. Se a imagem estreitar, contradizer ou banalizar a tese, use talking head ou lettering.
- No split-screen, não use headline entre os painéis. O B-roll ocupa o topo; o talking head fica abaixo na escala original. A emenda tem blur real estreito e somente uma borda inferior azul semitransparente. Entrada e saída usam film burn, nunca fade.
- Preserve `setsar=1`, blend em RGB, limiter com `level=false` e o fluxo de cor + matte H.264 para transparência das legendas.
- Preserve e sinalize Rec.709 (`color_range=tv`, `colorspace`, `color_primaries` e `color_trc` em `bt709`). Use grade por plano: recupere detalhe nas sombras sem lavar pele nem transformar roupa preta em cinza; controle saturação de fundos laranja/azul e revise a luminância do rosto.
- No talking head, o rosto é a âncora. Introduza mudança visual útil a cada novo bloco de raciocínio, normalmente a cada 3–6 s: palavra enfatizada, zoom eased, card numérico, recorte, documento ou B-roll licenciado. Não cubra o rosto por longos períodos e não force B-roll quando a fala já é visualmente suficiente.
- Use no máximo 2–3 acentos sonoros principais por minuto. Clicks marcam palavras ou números; whooshes acompanham movimentos longos; pops graves ficam reservados a dados ou conclusões. Evite clusters e nunca aplique SFX na palavra de abertura.
- As referências editoriais (Cleo Abram, Codie Sanchez, Hayden Hillier-Smith, Jordan Orme, Johnny Harris, Rafael Gratta, Anderson Gaveta, Pedro Loos, Fill Rocha e Olga Lehnerg) orientam clareza, ritmo e hierarquia, não cópia de identidade ou reutilização de trechos.
- Não adicione patrocinador, linguagem clínica, elementos náuticos ou assinatura herdada dos outros clientes sem material explícito do job.

## Assets e licenças

Mantenha em `Content Hub/02 - Assets` apenas transições, overlays, SFX, fontes, logo, música aprovada e manifestos de origem/licença. B-roll de estoque fica separado por projeto e nunca é confundido com overlay reutilizável. Para SFX externos, aceite automaticamente somente CC0; CC BY exige créditos anexos; rejeite CC BY-NC. Itens cuja licença não permita redistribuição ficam apenas referenciados no manifesto e são baixados da fonte oficial para o job, sem re-hospedagem no Drive compartilhado.

## Revisão e entrega

Cada corte entrega o MP4 com a mesma capa como primeiro frame, `CAPA - <nome>.png` em 1080×1920 e os timecodes `HH:MM:SS:FF` de entrada e saída no master. A capa é obrigatória e deve ser visualmente revisada. Confira o MP4, a headline em caixa alta, Montserrat, logo, frame zero, trilha de áudio escolhida e todos os film burns de troca de cena.

Depois de todo render final, rode `caption-quality-gate` com cobertura de 100% dos blocos e `video-delivery-safety-check`. Valide também 100% dos popups no início/meio/fim e confronte o texto com o job. Um vídeo com erro, baixa qualidade ou divergência do job é bloqueado mesmo que o FFmpeg tenha terminado. Ao encerrar a demanda, rode novamente `video-project-structure`, atualize bíblias/catálogos/manifests e suba ao Drive as skills e assets reutilizáveis necessários. Nunca envie bruto/master/proxy ou vídeo stock ao Drive de skills/assets; música/SFX/VFX/overlays só sobem quando a licença permitir, caso contrário sobe apenas a referência legal.

Quando o usuário pedir organização no Google Drive, mantenha a estrutura descrita no perfil da marca. Uploads e alterações no Drive exigem autorização da tarefa atual; a skill não presume permissão permanente.
