# CIBO

CIBO é um agente de edição de vídeo construído como uma coleção de skills do Claude Code. Cada skill encapsula um fluxo de edição específico — de um cliente, de um formato ou de uma etapa de qualidade — com suas próprias instruções, scripts e assets.

O nome vem de *BLAME!* (Tsutomu Nihei): Cibo é uma inteligência que sobrevive migrando de corpo em corpo, carregando conhecimento adiante. É a mesma lógica deste repositório — o agente não é uma skill fixa, é a soma de tudo que ele já aprendeu, e cresce a cada skill nova ou correção que entra aqui.

## Como está organizado

```
CIBO/
  skills/
    <nome-da-skill>/
      SKILL.md           # instruções, quando usar, fluxo obrigatório
      scripts/            # scripts Python/shell que a skill roda
      references/          # políticas, checklists, memória de cliente
      assets/             # fontes, SFX, overlays, logos, exemplos de job
      requirements.txt    # dependências Python (quando houver)
```

Cada skill é autocontida: lê seu próprio `SKILL.md` antes de qualquer coisa, e não mistura assets/identidade com outro cliente.

## Skills

### Roteamento de cliente
| Skill | O que faz |
|---|---|
| `client-router` | Identifica a que cliente pertence um job antes de qualquer corte, e garante que fonte, logo, trilha, SFX e capa nunca vazem entre clientes — mesmo quando compartilham o mesmo motor de render. |

### Cortes por cliente (vertical 9:16)
| Skill | O que faz |
|---|---|
| `bombordo-boreste` | Cortes verticais do podcast Bombordo e Boreste, com estilo e assets próprios do cliente. |
| `content-hub` | Cortes verticais da Content Hub — identidade, seleção editorial, tratamento de áudio e transições próprias. |
| `katia` | Cortes verticais da Katia, com fonte e trilha próprias da cliente. |
| `autismo-cast` | Cortes verticais do Autismo Cast, com estilo e assets próprios do cliente. |
| `dr-energia` | Cortes verticais do Dr. Energia BR Cast: burn-in verde na entrada e saída, proporção de 4 cortes do apresentador para 2 do convidado, entrega a 24 fps. |
| `fernanda-produto` | Vídeos de produto da Fernanda (linha Zeo): Sony S-Log3 deitada → vertical colorizado, corte de bastidores e gaguejadas de silêncio a silêncio, zoom suave, referências Pexels em tela dividida, burn azul, SFX só nas transições e música em faixa separada. |
| `podcast-reels` | Fluxo genérico de podcast → Reels: legendas Cal Sans, SFX de câmera, abertura com zoom-out e blur, capa com manchete. |

### Formato e transformação
| Skill | O que faz |
|---|---|
| `depoimento-vertical-blur` | Transforma depoimento/talking head horizontal em vertical nítido com blur só nas faixas superior/inferior. |
| `cortes-youtube-verificados` | Baixa e recorta trechos do YouTube (yt-dlp + FFmpeg) validando minutagem e integridade contra a fonte. |

### Qualidade e QA
| Skill | O que faz |
|---|---|
| `caption-quality-gate` | Pente-fino obrigatório de legendas: fidelidade à fala, timing, quebras, ênfases, legibilidade no render. |
| `legenda-cruzada` | Confere a legenda queimada retranscrevendo o áudio final com um modelo mais forte (large-v3) e comparando palavra a palavra. |
| `video-delivery-safety-check` | Checking final antes da entrega: confronta o MP4 com o job esperado, falhas técnicas/visuais/sonoras. |
| `semantic-broll-validator` | Valida se um B-roll casa com o sentido completo da fala, não só com uma palavra-chave isolada. |

### Produção e infraestrutura
| Skill | O que faz |
|---|---|
| `video-project-structure` | Cria e audita a estrutura fixa de pastas de um projeto de edição (fontes, transcrições, QA, entregas). |
| `video-render-optimizer` | Detecta CPU/GPU/encoders FFmpeg disponíveis e escolhe o mais eficiente sem perder qualidade perceptível. |
| `talking-head-music` | Escolhe, compara e mixa trilha de fundo para vídeos de talking head sem atropelar a inteligibilidade da fala. |
| `clickup-thumb-podcast` | Cria a demanda de thumb de episódio de podcast no ClickUp (ContentHub > Max > Edição) no padrão da equipe; o token fica fora do repositório. |

## Setup

Requer `ffmpeg`/`ffprobe` no PATH (via Homebrew, por exemplo) e Python 3.11+.

Cada skill com dependências Python tem seu próprio `requirements.txt`. Crie um venv por skill:

```bash
cd skills/<nome-da-skill>
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Os `.venv/` não são versionados (veja `.gitignore`) — são recriados localmente a partir do `requirements.txt` de cada skill.

## Como o CIBO cresce

Este repositório é o histórico de aprendizado do agente. Quando uma skill existente for corrigida (um bug de render, uma regra de estilo nova de um cliente) ou uma skill nova for ensinada, ela entra aqui do mesmo jeito: pasta própria em `skills/`, `SKILL.md` com o fluxo obrigatório, scripts e assets versionados, sem misturar com as outras.
