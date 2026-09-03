# Content Hub — manifesto de assets

## Identidade e transições

| Arquivo | Uso | Origem/licença | Redistribuição |
|---|---|---|---|
| `logo_content_hub.png` | Logo oficial | Fornecido pelo cliente no Drive | Uso interno da Content Hub |
| `logo_content_hub_transparent.png` | Logo oficial sem fundo para capas e peças | Fornecido pelo usuário; SHA-256 `c0689edd0a9e79dfedf5ece52e55b860035e788925f9a7fcd20c1a8de911346a` | Uso interno da Content Hub |
| `film_burn_transitions.mp4` | Fonte da transição com SFX | Fornecido pelo usuário | Uso interno da Content Hub |
| `film_burn_clean.mp4` | Trecho 9:16 limpo derivado do asset acima | Produção interna | Uso interno da Content Hub |
| `Montserrat-VariableFont_wght.ttf` | Headline/capa | Montserrat, SIL Open Font License 1.1 — https://github.com/JulietaUla/Montserrat | Permitida pela OFL |
| `CalSans-Regular.ttf` | Legendas | Cal Sans, SIL Open Font License 1.1 — https://github.com/calcom/sans | Permitida pela OFL |

## SFX próprios

`click.wav`, `whoosh_soft.wav` e `pop_low.wav` são sintetizados localmente por `scripts/sfx_generate.py`; não contêm gravação ou sample de terceiros. Podem ser mantidos no Drive da Content Hub e regenerados de forma determinística.

## Música

As trilhas atuais vieram da biblioteca Mixkit e são usadas sob a `Mixkit Stock Music Free License`: https://mixkit.co/free-stock-music/ e https://mixkit.co/license/. A licença permite incorporação aos vídeos, mas não redistribuição isolada; portanto, os MP3s permanecem apenas na pasta local do job e o Drive guarda manifesto/referência.

| Faixa | Autor | Função atual | Arquivo local do job |
|---|---|---|---|
| Driving Ambition | Ahjay Stelino | empreendedorismo, inspiração e otimismo | `driving_ambition_ahjay_stelino.mp3` |
| Close Up | Michael Ramir C. | inovação, tecnologia e execução | `close_up_michael_ramirc.mp3` |
| Curiosity | Diego Nava | equilíbrio, mentoria e reflexão | `curiosity_diego_nava.mp3` |
| Stylz | Ahjay Stelino | pesquisa, tecnologia e propriedade intelectual | `stylz_ahjay_stelino.mp3` |
| The Boss | Diego Nava | gestão financeira e autoridade | `the_boss_diego_nava.mp3` |
| The King | Michael Ramir C. | propósito e sustentabilidade | `the_king_michael_ramirc.mp3` |

Fontes futuras seguem `references/media-policy.md`: Openverse, Coverr, Wikimedia Commons, Internet Archive, Pixabay Music, Mixkit, YouTube Audio Library e Incompetech, sempre com verificação individual de licença, atribuição e restrição de redistribuição.

## SFX externos futuros

- Freesound API: https://freesound.org/docs/api/
- Aceitar automaticamente somente `CC0`.
- `CC BY` exige arquivo de créditos com autor, título, URL e licença.
- Rejeitar `CC BY-NC` em trabalhos comerciais.
