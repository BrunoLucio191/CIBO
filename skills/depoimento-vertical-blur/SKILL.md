---
name: depoimento-vertical-blur
description: Transforme depoimentos e talking heads horizontais de baixa resolução em vídeos 9:16 com a pessoa em um quadro vertical nítido ocupando toda a largura, blur somente acima e abaixo, legendas queimadas, capa e SRT. Use para Reels, Shorts e TikTok; não use quando o usuário quiser blur nas laterais ou reenquadramento horizontal.
---

# Depoimento vertical com blur

**Setup local:** as dependências (numpy, opencv-python-headless) vivem em um venv
em `~/.claude/skills/depoimento-vertical-blur/.venv`. Rode `scripts/face_track.py`
com `~/.claude/skills/depoimento-vertical-blur/.venv/bin/python3
scripts/face_track.py`, ou ative o venv primeiro, em vez do `python3` puro.
Requer `ffmpeg`/`ffprobe` no PATH.

Converta o master sem inventar detalhe. O resultado precisa parecer um vídeo vertical deliberado, preservar a cabeça inteira e usar o fundo desfocado apenas para completar as faixas superior e inferior.

## Antes de renderizar

1. Preserve o master e trabalhe em uma estrutura com fontes, transcrição, assets, trabalho, QA e entregas separados.
2. Faça probe de resolução, FPS, duração, áudio e cor.
3. Transcreva e revise a fala completa. O SRT revisado é a fonte textual; não valide nomes ou palavras ambíguas somente pelo som isolado.
4. Detecte o rosto com `scripts/face_track.py`. Se OpenCV não estiver disponível, use um centro manual revisado em vários momentos do vídeo.
5. Leia [references/layout-and-style.md](references/layout-and-style.md) antes de montar o filtro ou alterar enquadramento e legenda.

## Enquadramento obrigatório

- Entrega padrão: 1080×1920, 30 fps, H.264 High, yuv420p, AAC e Rec.709.
- A camada nítida usa toda a altura do master e um recorte 2:3. Em fonte 1920×1080, isso equivale a `crop=720:1080`.
- Escale a camada nítida para 1080×1620 e posicione em `x=0,y=150`.
- Portanto, o quadro nítido toca as bordas esquerda e direita. Blur lateral é erro.
- O background usa o mesmo vídeo, recortado em 9:16, preenchendo 1080×1920, escurecido levemente e com blur forte.
- O background só fica visível nos 150 px superiores e inferiores. Ajuste essa geometria proporcionalmente se a entrega não for 1080×1920.
- Centralize pelo rosto com movimento suave. Não siga micro movimentos quadro a quadro; use centros suavizados e verifique começo, meio, fim e mudanças bruscas.
- Cabeça, cabelo, queixo e ombros precisam permanecer inteiros. Se o master não permitir isso, reduza a escala do quadro nítido e explique o compromisso antes do render final.

## Legendas

- Use texto branco, fonte Cal Sans ou a fonte indicada pelo usuário, tamanho constante, no máximo duas linhas, sem caixa de fundo e com drop shadow preto suave.
- Mantenha o bloco no terço inferior, sobre peito/roupa ou área inferior, nunca sobre olhos, boca ou cabelo.
- Use entrelinhas compactas e largura segura. Não aumente uma legenda isolada para preencher espaço.
- Queime as legendas no MP4 e entregue também o SRT. Se houver capa de 1 segundo no início do MP4, desloque o SRT entregue em +1 segundo.

## Capa

Quando o trabalho pedir capa, entregue PNG 1080×1920 e use a mesma imagem no primeiro segundo do MP4. Por padrão: Montserrat, caixa alta, alinhamento à esquerda, sem misturar identidades de outros clientes. Confirme visualmente que o frame inicial corresponde ao PNG.

## Fluxo de revisão

1. Gere uma prévia ou contact sheet antes do render integral. Ela deve mostrar a camada nítida tocando as duas bordas laterais e blur somente em cima/baixo.
2. Revise todos os momentos em que a pessoa inclina ou desloca a cabeça.
3. Rode o pente-fino de legendas antes da checagem final do vídeo.
4. Decodifique o arquivo inteiro e confira capa, sincronismo, loudness, true peak, resolução, FPS, bitrate, cor, frames pretos/congelados e artefatos.
5. Só entregue depois da inspeção visual da contact sheet. `AUTOMATED_PASS` sozinho não basta.

## Bloqueios

Não entregue se houver blur nas laterais, cabeça cortada, rosto fora do centro, legenda sobre olhos/boca, fundo opaco atrás da legenda, tamanho de fonte variável, capa divergente, SRT sem o deslocamento da capa ou arquivo fora do perfil vertical esperado.
