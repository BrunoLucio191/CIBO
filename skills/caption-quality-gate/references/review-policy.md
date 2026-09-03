# Política de revisão de legendas

## Fidelidade e contexto

- Compare com a fala, não apenas com a transcrição automática.
- Leia a oração completa e a frase anterior/seguinte antes de corrigir homófonos.
- Confirme nomes próprios, empresas, localidades, números, unidades, siglas e jargão em fonte do projeto quando possível.
- Preserve oralidade útil, mas corrija erro ortográfico. Remova vício de linguagem somente quando o corte editorial também o removeu.
- Não invente palavra para preencher áudio incompreensível; marque para revisão humana.

## Timing e leitura

- Entrada no ataque da fala, sem antecipação incômoda; saída após o último fonema.
- Evite blocos inferiores a 180 ms ou superiores a 6 s.
- Meta até 18 caracteres por bloco para o estilo de cortes; trate acima de 24 como alerta forte.
- Em legenda social dinâmica, até 24 caracteres por segundo é normal; 24–32 exige revisão visual/contextual e acima de 32 bloqueia, salvo hook curto/transiente intencional explicitamente aprovado.
- Não permita sobreposição temporal não intencional.

## Visual

- no máximo duas linhas;
- baseline consistente;
- contraste suficiente em todos os planos;
- sem corte nas bordas ou safe areas das plataformas;
- sem cobrir olhos, boca, dado, logo ou informação central do B-roll;
- ênfase deve recair na palavra semanticamente importante, não em artigo/preposição;
- conferir primeira e última legenda, maior bloco, maior CPS e todas as correções manuais.

## Status

- `FAIL`: erro determinístico ou contextual confirmado.
- `REVIEW_REQUIRED`: automação não conseguiu decidir ou existe alerta visual/fonético.
- `AUTOMATED_PASS`: estrutura passou; ainda exige inspeção visual e contextual.
- `PASS`: estrutura, fala/contexto e render visual aprovados.
