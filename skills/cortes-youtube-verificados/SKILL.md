---
name: cortes-youtube-verificados
description: Baixe e recorte trechos de vídeos do YouTube com yt-dlp e FFmpeg, preservando falas completas e validando obrigatoriamente a minutagem, a correspondência com a fonte e a integridade técnica do arquivo final. Use para cortes horizontais do YouTube; não use para transformar podcasts em Reels verticais com legendas e identidade visual.
---

# Cortes do YouTube Verificados

Antes de editar, preencha `references/content-brief-template.md`, mantenha `references/asset-source-catalog.md` atualizado e audite a estrutura fixa com `video-project-structure`.

Entregue um corte fiel ao vídeo indicado, na maior qualidade útil disponível e sem iniciar ou terminar no meio de uma fala. A validação editorial e técnica abaixo é obrigatória; nunca declare o arquivo pronto apenas porque o FFmpeg terminou sem erro.

## Entrada e origem

- Exija URL, início, fim e nome de saída. Se faltar apenas a minutagem ou se houver ambiguidade material, peça essa informação antes do corte.
- Confirme com `yt-dlp` o ID, título, duração e formatos disponíveis. Registre a resolução, FPS, codecs e formato escolhidos.
- Baixe `bestvideo*+bestaudio/best`. Mantenha o arquivo-fonte separado do resultado e preserve a resolução e a taxa de quadros originais, salvo pedido contrário.
- Obtenha legendas automáticas no idioma relevante em uma chamada separada para que uma falha ou limite de legendas não interrompa o vídeo.

## Ajuste editorial obrigatório

Inspecione alguns segundos antes e depois dos dois limites usando, conforme disponível, legendas com timestamps por palavra, áudio, detecção de pausas e quadros de referência.

- Início: localize o ataque real da primeira palavra ou uma transição natural. Inclua uma margem curta quando o horário informado removeria um fonema.
- Fim: preserve a conclusão da frase. Pode manter uma cauda curta de música ou cartão de encerramento quando isso produzir um final natural.
- Não altere significativamente o intervalo sem explicar ao usuário. Informe sempre a minutagem solicitada e a minutagem efetivamente usada.
- Se legendas e áudio discordarem ou o limite continuar ambíguo, gere uma prévia curta e inspecione-a; não adivinhe.

## Exportação

Antes do primeiro render em uma máquina ou perfil novo, use a skill `video-render-optimizer`: detecte GPU e encoders FFmpeg, compare CPU × hardware em 8–15 s do próprio material e escolha por velocidade, SSIM, compatibilidade, bitrate real e tamanho projetado. Defina alvo/teto conforme resolução, FPS e limite do destino. Não use GPU automaticamente se ela exigir bitrate excessivo ou reduzir a qualidade; valide o bitrate do arquivo final com `ffprobe`.

- Para limites exatos, recodifique em um formato amplamente compatível. Em 1080p60, H.264 High, `yuv420p`, CRF 16–18, preset slow e AAC 192 kb/s são uma base de alta qualidade; adapte nível, codec ou bitrate para resoluções maiores e para requisitos explícitos.
- Use `-movflags +faststart` em MP4 e copie metadados úteis sem incorporar credenciais ou dados privados.
- Evite `-c copy` quando isso deslocaria o começo para um keyframe ou tornaria o corte impreciso.

## Verificação obrigatória antes da entrega

Execute todas as etapas aplicáveis:

1. **Fonte online:** baixe novamente do YouTube uma janela curta que contenha alguns segundos antes e depois do trecho final. Não use somente o arquivo-fonte local como prova.
2. **Correspondência temporal:** alinhe o resultado à janela online e compare vídeo e áudio ao longo de todo o corte. Use SSIM e PSNR de áudio ou uma métrica equivalente. Divergências relevantes exigem investigação.
3. **Limites editoriais:** confira quadro e áudio no início e no fim, além das legendas próximas. Confirme explicitamente que nenhuma palavra ou frase ficou cortada.
4. **Estrutura:** valide duração, resolução, FPS, codecs, canais, sample rate, presença de vídeo e áudio e tamanho não nulo.
5. **Decodificação integral:** decodifique o arquivo completo com FFmpeg em modo de erro. Qualquer erro torna a entrega inválida.
6. **Reprodução prática:** confira que o MP4 abre no começo correto, permanece sincronizado e termina no ponto esperado. Investigue tela preta, silêncio inesperado, congelamento, duração divergente ou áudio ausente.
7. **Relatório:** só então informe nome/caminho, duração, qualidade, intervalo efetivo e resultado das verificações.

Use `scripts/verify_cut.py` para as verificações determinísticas. Passe também `--reference` e `--reference-offset` quando houver uma janela online; um resultado `FAIL` bloqueia a entrega. Métricas automáticas não substituem a inspeção de fala nos limites.

## Upload

Depois de todo render final, rode `caption-quality-gate` quando houver legendas e sempre rode `video-delivery-safety-check`. No encerramento, atualize brief, catálogo e manifestos e sincronize no Drive apenas skills/assets reutilizáveis licenciados. Nunca envie gravação bruta, master, proxy ou vídeo stock ao Drive de skills/assets.

Faça upload somente quando solicitado e para o destino indicado pelo usuário. Verifique a conclusão no serviço de destino; iniciar o envio não é confirmação de sucesso. Não apague fonte ou resultado local sem autorização explícita.
