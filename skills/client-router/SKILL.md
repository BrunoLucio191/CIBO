---
name: client-router
description: Identifique a que cliente pertence um trabalho de edição antes de aplicar qualquer skill de corte, e trate cada cliente como um fluxo, estilo e conjunto de assets isolado — nunca misture fonte, logo, trilha, SFX ou convenção de capa entre clientes. Use no início de todo job que envolva um cliente com skill própria (Bombordo e Boreste, Content Hub, Katia, Autismo Cast), ou sempre que não estiver claro de qual cliente é o material, antes de escolher a skill de corte.
---

# Client Router

O CIBO edita para vários clientes, e cada um tem um fluxo de edição diferente — mesmo quando o motor por baixo é compartilhado. Duas skills de clientes distintos podem ter nascido do mesmo código (`bombordo-boreste`, `autismo-cast` e `podcast-reels` são o mesmo motor com defaults e assets próprios; `katia` é um fork de `podcast-reels`), mas isso não significa que os arquivos são intercambiáveis. Identidade de cliente é definida pelos assets, pela fonte, pela trilha e pelas regras editoriais daquele cliente específico, não pelo motor de render.

## Workflow

1. **Identifique o cliente antes de tocar em qualquer material.** Use o que o usuário disse, o nome do podcast/marca citado no SRT, ou o nome da pasta do projeto. Se não houver sinal claro, **pergunte ao usuário** — nunca infira o cliente pela localização física de um arquivo compartilhado (ex.: a trilha da Katia vem do mesmo pool de música da Content Hub/SEBRAE, mas isso não faz o job ser da Content Hub — ver `references/client-registry.md`).
2. **Consulte `references/client-registry.md`** para mapear o cliente à skill certa e às suas marcas de identidade (fonte, logo, SFX, engine de origem, fonte de verdade). Rode `scripts/detect_client.py "<texto>"` como apoio quando quiser testar um nome de pasta, marca ou trecho de SRT contra os clientes conhecidos.
3. **Delegue todo o trabalho à skill do cliente identificado.** Não copie fonte, logo, filmburn, SFX, `client-content-bible.md` ou convenção de capa de um cliente para o job de outro, mesmo que os arquivos estejam acessíveis no mesmo volume ou pasta compartilhada.
4. **Se o material não pertencer a nenhum cliente com skill própria:** use `podcast-reels` como fallback genérico, ou pare e pergunte ao usuário se deve nascer uma skill nova para esse cliente. Nunca force os assets/identidade de um cliente existente num material que não é dele.
5. **Ao nascer um cliente novo**, crie a skill seguindo a estrutura das demais (`SKILL.md`, `scripts/`, `references/client-content-bible.md`, `references/asset-source-catalog.md`, `assets/` com fonte/logo/SFX próprios) e adicione uma linha em `references/client-registry.md`. Use `video-project-structure` para auditar a organização de pastas do projeto desse cliente.
6. **Antes de entregar**, confirme que nome de pasta, capa, fonte, música e legendas não vazaram identidade de outro cliente — isso vale mesmo dentro de um único job com múltiplos convidados ou formatos.
