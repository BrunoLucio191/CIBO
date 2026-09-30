# Malu — bíblia de conteúdo

## Material
- Entrevista em estúdio com estante de produtos Zeo/Turi-Ita ao fundo; ela sentada numa poltrona, copo de Turi-Ita na mão.
- Sony, 4K 29,97 fps, **Rec.709** (`color_transfer=iec61966-2-4`), rotação −90° nos metadados (`rotate: "clock"`). `grade: "rec709"`, `rec709_eq: "eq=contrast=1.0:saturation=0.98"` (contraste 1,03 esmagava o preto).
- Há entrevistador e outras pessoas na sala. Ela olha para a **direita** do quadro (entrevistador).
- A voz dela é ~5 dB mais baixa que a da Fernanda.

## Grafia e termos
- Produto: **Turi-Ita** (ela fala "turita"). Nunca "zeólita" no lugar, nem "Turiita". `brand_terms` no job.
- Ela fala "Thomas" (pessoa citada). Linhas de produto: premium, gold, silver, standard (ela troca os nomes às vezes: confirme o sentido antes de legendar).
- Sílaba ambígua antes de "Toxina" (~91 s do `C0097`): modelos ouvem "na"/"falei". Não inventar; perguntar ao usuário.

## Pedidos e correções do usuário
1. "A legenda está ruim e cheia de erros" / "foi feito de uma maneira bem porca": legenda revisada à mão, sincronizada no ataque da fala, destaque só em termos que importam.
2. "Legenda com fonte suave e elegante" → atualizado: "os vídeos aqui precisam de uma fonte do Montserrat mais fina". Montserrat Light ou Regular no texto e SemiBold no destaque, animada palavra por palavra (vinda do Bombordo, sem spring), logo abaixo do queixo. O par DM Sans + Playfair itálico foi aposentado.
3. "Tem uma voz de fundo antes de 'é a micronização'… em 25 s uma pessoa no fundo falando 'vai preparando o corpo'… o foco é apenas da pessoa que está falando": skill `fala-limpa`.
4. "Esses ehhh deixam anti profissional": cortar hesitações e pausas de pensamento.
5. "No final a palavra desconforto foi cortada": `tail_hold`.
6. "O zoom in deveria ser mais rápido e ter um pouco de blur e o zoom out mais lerdo".
7. "Passe um pente na edição para garantir qualidade antes de renderizar" / "edição de editor com anos de experiência, bom motion": pente-fino `review_job.py` obrigatório, 3 níveis de enquadramento com intenção, rastreamento de rosto.
8. "Desenhe uma matriz no rosto pra identificar quando está parada ou se movimentando e merece ser seguida": `face_track.py --debug`.
9. Esse padrão é **só dos cortes da Malu** — não mexer no padrão da Fernanda.
10. "O zoom in tá com um blur estranho" / "quero aquele blur natural como quem usa shutter angle em zoom in no Premiere" / "shutter angle em 360": motion blur de câmera, 360°.
11. "A convidada não tá 100% centralizada no zoom": zoom ancorado no rosto, centro exato no auge.
12. "A skill atual é quase toda sobre evitar erros e quase nada sobre direção criativa. O resultado sai correto, mas sem ritmo nem acabamento": padrão de Reel de marca premium de bem-estar editado por motion designer sênior — mapa de edição antes de qualquer render, kit de motion, SFX curados, referências com nota, -14 LUFS. Detalhes na `SKILL.md`.
13. "Me mostre o mapa antes de renderizar a prévia" e "só depois peça meu ok para o render completo": dois pontos de aprovação por reel.

## Identidade visual (paleta)
Tirada das cores reais do estúdio (amostras do reel 01). Nada fora dela: sem azul do Bombordo, sem cores de template. **Proposta; aguarda aprovação do usuário no mapa do reel 01.**
- Texto da legenda: branco quente `#FFFBF3`, com sombra suave.
- Palavra falada e destaque: areia dourada `#E9C98F` (luz quente da prateleira, clareada para leitura).
- Cards e gráficos: fundo creme `#F4EEE1` (parede, amostra `#E2DAC2`) com texto azul-marinho Zeo `#1F2740` (tubo ZeoBody, amostra `#41475A`).
- Acento: kraft Turi-Ita `#A98155` (pacote na estante).
- Fonte de tudo: Montserrat (Light/Regular no texto, SemiBold em destaque e números).

## Textos a confirmar com o usuário (nunca inventar)
- Lower third: nome e função da Malu.
- Cartão final: produto ou chamada.

## Inserts do master (C0097, estúdio)
- Estante de cima: tubos ZeoBody azul-marinho, frascos brancos e roll-ons. Estante de baixo, à direita: pacotes kraft de Turi-Ita com rótulo escuro.
- O copo de Turi-Ita na mão dela está no quadro quase o tempo todo.
- Recorte do próprio 4K com push lento (ver `SKILL.md`, Referências).

## Referências já aprovadas (reel 01)
- "intestino preso" → Pexels 9465540 (mão no abdômen).
- "o suor, toxina" → Pexels 5712806 (testa suada; 4804848 ficou escuro e ilegível no recorte).
- "primeiro você toma 40 dias" → Pexels 13107036 (pó caindo no copo d'água).
