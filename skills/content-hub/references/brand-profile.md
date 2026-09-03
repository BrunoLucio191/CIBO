# Perfil da Content Hub

## Identidade confirmada

- Nome: **Content Hub**.
- Logo oficial para capas: `assets/logo_content_hub_transparent.png`, fornecido pelo usuário e preservado sem fundo. `assets/logo_content_hub.png` permanece apenas como fonte histórica.
- Cores dominantes medidas no logo original: laranja `#FF7400`, azul profundo `#000249`, azul de apoio `#002C7B` e branco para contraste.
- Fonte de capa: `assets/Montserrat-VariableFont_wght.ttf`, peso ExtraBold ou Black, sempre em caixa alta.
- Film burn oficial: `assets/film_burn_transitions.mp4`, fornecido pelo usuário. `assets/film_burn_clean.mp4` é o trecho 9:16 limpo para render, sem as telas promocionais do arquivo-fonte; usar em cada troca real de cena e preservar o SFX em volume controlado.

Use o laranja como acento, não como fundo dominante. Preserve proporção e cores do logo; não aplique a conversão monocromática usada por outros clientes.

A capa deve ter linguagem própria da Content Hub, sem copiar a composição de Bombordo e Boreste: frame expressivo, pessoa centralizada visualmente, leve glow laranja, painel editorial azul profundo assimétrico na parte inferior, barra laranja e headline curta em Montserrat caixa alta com uma linha de acento. Use a logo transparente no alto e mova-a para o lado oposto ao rosto. Não corte olhos, queixo ou testa de forma acidental. Entregue a mesma capa como PNG e como primeiro frame do MP4.

## Diferenças editoriais

Os cortes priorizam os convidados. A Content Hub não herda temas, patrocinadores, vocabulário ou grafismos do Autismo Cast e do Bombordo e Boreste. A fala precisa entregar conhecimento, experiência, provocação ou resultado de maneira compreensível fora do episódio completo.

## Estrutura no Google Drive

Raiz observada: `Meu Drive/skills_agents/01 - Cortes por Cliente`.

```text
Content Hub/
├── 01 - Skill/
├── 02 - Assets/
├── 03 - Thumbnails/
└── 04 - Capas dos Cortes/
```

- `01 - Skill`: pacote `content-hub.zip`.
- `02 - Assets`: logo, fontes, SFX, film burns, música e demais fontes de marca aprovadas.
- `03 - Thumbnails`: thumbnails finais ou aprovadas.
- `04 - Capas dos Cortes`: capas verticais PNG dos cortes entregues.

Nos arquivos locais de entrega, use `cortes_content_hub/<NOME DO CONVIDADO>/` e mantenha juntos os dois MP4s e suas duas capas.

Não mova nem apague arquivos de outros clientes ao organizar esta estrutura.

`02 - Assets` é a fonte canônica para a edição local. Ao iniciar um job, baixe os assets da Content Hub para a pasta `assets/` da skill e valide nomes, hashes e licenças contra `ASSETS_MANIFEST.md`. Ao criar uma transição ou SFX próprio que será reutilizado, envie o arquivo e atualize o manifesto. Não suba vídeos de estoque nessa pasta e não copie assets de outros clientes.

Dentro de `02 - Assets`, organize os reutilizáveis em `Overlays/`, `Sound Effects/`, `Music/`, `Licenses/` e `Manifests/`. A biblioteca deve permanecer privada. Para cada overlay aprovado, guardar original ou referência conforme a permissão de redistribuição, preview leve, `metadata.json`, `source.txt` e comprovante da licença. B-roll usado para ilustrar uma fala permanece na pasta do projeto, com manifesto próprio.
