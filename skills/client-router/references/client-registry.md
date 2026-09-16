# Registro de clientes

Cada linha é um cliente com skill própria. "Engine" indica de qual motor de render a skill nasceu — útil para saber onde uma correção de bug deve ser propagada, não para decidir se assets são intercambiáveis (eles não são).

| Cliente | Skill | Fonte | Identidade visual | SFX / transições | Engine de origem | Fonte de verdade | Observações |
|---|---|---|---|---|---|---|---|
| Bombordo e Boreste | `bombordo-boreste` | Cal Sans (bundled) | logo_portos (preto/branco/cor) | filmburn azul + click | motor de referência (compartilhado com autismo-cast, podcast-reels) | `references/client-content-bible.md`, `references/asset-source-catalog.md` | Podcast; fluxo padrão de "corte de podcast" |
| Content Hub | `content-hub` | Montserrat (capa) + Cal Sans (legendas) | logo_content_hub(_transparent) | whoosh/pop, film_burn_clean + film_burn_transitions + overlays | motor próprio (mais complexo: split-screen, B-roll, grading dedicado) | `references/brand-profile.md`, `media-policy.md`, `client-content-bible.md`, `asset-source-catalog.md`; `assets/ASSETS_MANIFEST.md` — Drive é a fonte canônica dos assets | Entregas organizadas por pasta com nome do convidado; múltiplos convidados por gravação são possíveis |
| Katia | `katia` | Montserrat Bold apenas — **não** cair para Cal Sans | sem barra azul na capa; headline mais baixa que o padrão | herdado de podcast-reels, sem filmburn/SFX próprios documentados | fork de `podcast-reels` | — | Trilha vem do pool compartilhado `content_hub_assets/music/` — **exceção documentada**, não é sinal de que o job é da Content Hub |
| Autismo Cast | `autismo-cast` | Cal Sans (bundled) | logo/click/filmburn próprios | filmburn azul + click | motor de referência (compartilhado com bombordo-boreste, podcast-reels) | `references/client-content-bible.md`, `references/asset-source-catalog.md` | — |
| Dr. Energia BR Cast | `dr-energia` | Montserrat Bold (bundled) | logo_dr_energia, verde #9AE71C; capa de um frame com degradê só no rodapé | **filmburn verde, na entrada e na saída** (tingido do `filmburn_blue` do acervo) | motor próprio (reenquadramento delega para o `face_crop.py` da bombordo-boreste) | `SKILL.md`, `references/decisao_musical.md` | Apresentador Guilherme; público-alvo médicos. Proporção obrigatória de **4 cortes do apresentador e 2 do convidado**. Entrega a **24 fps**: a fonte é OBS a 30 fps com ~23,7 fps reais |
| Fernanda (produtos Zeo) | `fernanda-produto` | Montserrat Medium (legenda) | sem logo; vídeo de apresentação de produto | `filmburn_blue` da Bombordo (**exceção autorizada pelo usuário**), whoosh do `film_burn_transitions` original, clique de câmera | motor próprio (`scripts/render.py` + `job.json`) | `references/client-content-bible.md`, `references/asset-source-catalog.md` | Sony deitada em S-Log3; tela dividida com B-roll Pexels; música em faixa separada (A2) + cópia mixada |
| *(sem cliente / genérico)* | `podcast-reels` | Cal Sans (bundled) | logo genérico, filmburn azul | filmburn azul + click | motor de referência original | — | Fallback quando o job não pertence a nenhum cliente com skill própria. Nome de arquivo de entrega segue a manchete, nunca `corte01`/`corte02` genérico |

## Skills de formato (não são clientes)

Estas skills tratam de formato/transformação e se combinam com a identidade do cliente que estiver sendo atendido, em vez de terem identidade própria:

- `depoimento-vertical-blur` — reenquadramento vertical com blur
- `cortes-youtube-verificados` — cortes horizontais verificados do YouTube

## Quando um cliente novo aparecer

1. Pergunte ao usuário o nome oficial do cliente/marca se não estiver óbvio.
2. Crie `skills/<nome-do-cliente>/` com `SKILL.md`, `scripts/`, `assets/` (fonte, logo, SFX, filmburn próprios) e `references/client-content-bible.md` + `references/asset-source-catalog.md`.
3. Adicione uma linha nesta tabela.
4. Só reaproveite assets de outro cliente se o usuário confirmar explicitamente que é uma exceção intencional (como o caso da Katia acima) — documente a exceção aqui quando isso acontecer.
