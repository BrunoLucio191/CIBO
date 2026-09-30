---
name: relatorio-estrategia-social
description: Produza o relatório mensal de performance de redes sociais (Instagram, TikTok, YouTube) de um cliente e a estratégia de conteúdo do mês seguinte, com diagnóstico por plataforma, leitura cruzada e funil, calendário de pautas pronto para produção, metas e testes — entregue em PDF e com o calendário em planilha. Use quando o usuário pedir relatório de performance, análise de métricas/exports das redes, estratégia ou planejamento de conteúdo do próximo mês, ou calendário editorial baseado em dados de um cliente.
---

# Relatório de performance + estratégia de conteúdo do próximo mês

O usuário é social media. A estratégia vira a base de **todo** o conteúdo do cliente no mês
seguinte: tem de ser específica o bastante para virar pauta sem reinterpretação (tema, gancho,
roteiro, CTA e métrica de sucesso por post).

## Regras que valem o tempo todo
- **Nenhum número inventado.** Todo número do relatório vem de um arquivo da pasta; guarde de
  onde veio (arquivo + coluna/print). O que for inferência é marcado como **Hipótese**.
- **Não compare métricas de nomes iguais entre plataformas** (view do Instagram ≠ TikTok ≠
  YouTube). Cada plataforma é comparada com ela mesma; entre plataformas, só **taxas**.
- **No Instagram, o alcance da conta não é a soma do alcance dos posts** (a mesma pessoa conta
  uma vez na conta). Use o número de conta dos prints de Resultados.
- **Amostra de um mês é pequena:** diferencie padrão consistente (vários posts, mais de uma
  semana) de caso isolado (1 post). Diga o tamanho da amostra junto de cada padrão.
- Linguagem que o cliente entenda, com profundidade suficiente para o social media executar.
- Definições e fórmulas das métricas: `references/metricas.md`.

## Etapa 0 — Briefing (antes de começar)
Confira se estas informações existem (no pedido, na pasta ou em relatórios anteriores).
Modelo para preencher: `references/briefing.md`.
- Nicho e o que o cliente faz; público que quer atingir.
- Objetivo principal do próximo mês (1 principal, no máximo 1 secundário).
- O que vende e onde a venda acontece (link na bio, DM, WhatsApp, site).
- Tom de voz e limites (o que não faz, não fala, não mostra).
- Capacidade de produção por semana (quantos vídeos, se aparece em câmera, se tem editor).
- Datas importantes do próximo mês (lançamentos, promoções, datas do nicho).
- Cores/logo do cliente para o PDF, se houver.

**Se faltar algo que muda a estratégia (objetivo, onde vende, capacidade de produção), pergunte
antes de começar**, tudo numa pergunta só. O que não muda a estratégia vira premissa declarada.

## Etapa 1 — Inventário e validação
- Liste cada arquivo: o que contém, plataforma, período e métricas disponíveis (tabela).
- Aponte lacunas (ex.: sem período anterior, sem dados de público, print cortado), inconsistências
  (totais que não batem, períodos diferentes entre arquivos, posts duplicados, fuso) e o que **não**
  dá para concluir com esses dados.
- Leia prints com cuidado (OCR/visão) e transcreva os números para uma tabela antes de usar.
- Normalize os exports numa tabela única por plataforma (um post por linha, datas no fuso do
  cliente) em `trabalho/dados_<plataforma>.csv`; é daqui que saem todas as contas.

## Etapa 2 — Diagnóstico por plataforma
Para cada plataforma:
- Números do mês e variação vs. período anterior, se houver.
- Taxas: engajamento por alcance/views, salvamentos e compartilhamentos por alcance, seguidores
  ganhos por view, retenção/tempo assistido quando houver.
- Top 5 e bottom 5 conteúdos com o **porquê**: formato, tema, gancho dos primeiros segundos,
  duração, dia/horário, CTA. Ordene por uma taxa coerente com o objetivo (não por volume bruto)
  e diga qual.
- Outliers (picos e viralizações): o que causou e se é replicável.
- Padrões de tema, formato, duração e horário acima da média da conta (com n de posts).
- Público: quem é, onde está, quando está ativo.

## Etapa 3 — Leitura cruzada
- Papel de cada plataforma para esse cliente (descoberta, relacionamento, conversão).
- Temas e formatos que funcionaram em mais de uma plataforma.
- Onde o funil vaza (ex.: muito alcance e pouca visita ao perfil; muita visita e poucos cliques
  no link), com as taxas de cada passagem.

### PARE AQUI
Mostre ao usuário o **diagnóstico resumido** (achados principais, lacunas, vazamentos do funil)
e **espere a aprovação**. Só siga para a estratégia depois do ok; incorpore as correções dele.

## Etapa 4 — Estratégia do próximo mês
1. **Manter / Parar / Testar** — cada item justificado com dado (número + fonte).
2. **Pilares de conteúdo** (3 a 5), com o objetivo de cada um.
3. **Funil** com mix % por etapa e por plataforma, coerente com o objetivo:
   topo (descoberta e alcance), meio (autoridade e relacionamento), fundo (conversão).
4. **Papel e frequência de cada plataforma** e o que reaproveitar entre elas.
5. **Calendário do mês** — uma linha por conteúdo: data, plataforma, formato, pilar, etapa do
   funil, tema, gancho (primeira frase / 3 primeiros segundos), estrutura do roteiro ou dos slides
   em tópicos, CTA e métrica que define o sucesso do post. Respeite a capacidade de produção
   semanal e as datas importantes; conteúdo reaproveitado aparece como linha própria em cada
   plataforma, indicando a origem.
6. **2 a 4 testes** com hipótese clara, como medir e quando avaliar.
7. **Metas por plataforma**: base atual → meta realista (justifique a meta pelo histórico).
8. **O que coletar no fim do mês** para o próximo relatório (exports, prints, períodos).

## Entrega
- **PDF** em português, visual limpo e profissional, com as cores/logo do cliente se houver.
  Estrutura fixa: capa → resumo executivo (1 página: 5 principais achados e 5 principais
  decisões) → diagnóstico por plataforma → leitura cruzada e funil → estratégia → calendário →
  metas e testes → anexo com as tabelas completas.
- Gráficos e tabelas onde facilitam a leitura (carregue a skill `dataviz` antes do primeiro
  gráfico). Números de uma plataforma nunca no mesmo eixo de outra.
- Gere o PDF a partir de HTML: `scripts/html_to_pdf.sh relatorio.html relatorio.pdf`
  (Chrome headless, A4). Confira o PDF página a página (quebras de tabela, calendário legível).
- **Planilha do calendário**, uma linha por conteúdo, para produção:
  `python3 scripts/calendario_xlsx.py calendario.json calendario.xlsx` (colunas na ordem do item 5,
  cabeçalho congelado, filtros, colunas de status/responsável/link em branco para a equipe).
- Organize a pasta de saída: `entrega/Relatorio_<Cliente>_<AAAA-MM>.pdf`,
  `entrega/Calendario_<Cliente>_<AAAA-MM>.xlsx`, e `trabalho/` com os CSVs normalizados.

## Checagem antes de entregar
- Todo número do PDF encontrado nos CSVs/prints (confira por amostragem os 10 mais citados).
- Nenhuma comparação de métrica bruta entre plataformas; hipóteses marcadas.
- Resumo executivo cabe em 1 página; calendário tem todas as colunas preenchidas.
- Quantidade de posts por semana ≤ capacidade de produção informada.
- A planilha e o calendário do PDF têm as mesmas linhas.
