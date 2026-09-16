---
name: clickup-thumb-podcast
description: Crie a demanda de thumb de um episódio de podcast (Pod Acontecer, Bombordo e Boreste, Dr. Energia etc.) direto no ClickUp, na lista ContentHub > Max > Edição, com o nome, a descrição, os responsáveis e o prazo no padrão da equipe. Use quando o usuário pedir para "subir", "criar" ou "mandar" a demanda da thumb para o ClickUp.
---

# Demanda de thumb no ClickUp

Cria a tarefa do designer via API do ClickUp. O token fica em `~/.config/clickup/token`
(chmod 600) — nunca imprimir nem colar o token em respostas.

## Destino fixo

- Workspace Begrow (`9011388881`) → ContentHub → Max → **Edição** (lista `901112367271`)
- Responsáveis: **Bruno Lucio BeGrow** (`81565536`) e **Jorge Luis** (`75568670`)
- Status inicial: `pendente`
- Prioridade: **normal**
- Prazo padrão: **amanhã às 12:00 (horário de Brasília)**, salvo se o usuário disser outro

## Padrão da demanda

- Nome: `[Podcast - <Podcast>] - Thumb EP <NN> - <CONVIDADO>: <TÍTULO DA THUMB>`
  O título é exatamente o texto da thumb; nada de resumo longo de pauta no nome.
- Descrição (markdown): Ep, Título da Thumb, Subtítulo (curto), Convidado, Orientações
  para a thumb, Instagram dos hosts e convidados, Gravação, Subir aqui.
- Instagram dos hosts é repetido em toda demanda (fixo no script, `HOST_INSTAGRAM`);
  o do convidado só entra se o usuário passar (`instagram_convidado`); sem ele, a linha é omitida.
- Sempre incluir a orientação para o designer pegar as imagens do convidado e dos
  hosts **direto da gravação**.
- Links que o usuário não passou ficam como placeholder (`[LINK DA GRAVAÇÃO]` etc.).
- Pod Acontecer: hosts atuais **Mota** (Felipe Mota, @portaldomota_) e **John Cutrim**
  (@john.cutrim), salvo orientação diferente do episódio.

## Fluxo

1. Monte o título/subtítulo da thumb junto com o SEO do episódio (mesmo gancho).
2. Escreva um `job.json` no scratchpad (campos documentados no topo do script).
3. Rode a prévia e mostre ao usuário:
   `python3 ~/.claude/skills/clickup-thumb-podcast/scripts/create_thumb_task.py job.json`
4. Só depois da aprovação, crie de verdade com `--send` e devolva o link da tarefa.
5. Antes de criar, confira se já não existe tarefa com o mesmo EP na lista para não duplicar
   (GET `/list/901112367271/task?include_closed=true`).
