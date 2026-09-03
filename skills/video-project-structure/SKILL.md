---
name: video-project-structure
description: Crie e audite uma estrutura fixa para projetos de edição de vídeo, separando fontes, transcrições, assets, trabalho, QA, entregas e manifestos; detecta arquivos soltos, duplicados, nomes inconsistentes e mídia proibida em pacotes de Drive. Use no início e antes do encerramento de todo projeto de vídeo.
---

# Estrutura fixa de projeto de vídeo

Organização é uma condição de qualidade, não uma limpeza opcional no fim.

## Estrutura canônica

Leia [references/layout.md](references/layout.md). Em projeto novo, crie as pastas com:

```bash
python3 scripts/audit_structure.py --root /path/projeto --init \
  --output-json /path/projeto/07_manifests/structure_audit.json
```

Em projeto existente, não mova arquivos automaticamente. Audite, produza um mapa de migração e preserve todos os caminhos usados por jobs ativos. Movimentação só acontece como etapa consciente depois de atualizar referências e validar os renders.

## Regras obrigatórias

- fontes brutas, masters, proxies e gravações ficam somente em `01_sources/`, local e privado;
- `02_transcripts/`: SRT, VTT, TXT e transcrições;
- `03_assets/`: identidade, fontes, áudio, VFX/overlays e stock local do projeto, separados por tipo e licença;
- `04_work/`: caches, intermediários, plans, captions e previews temporários;
- `05_qa/`: relatórios, contact sheets, probes e benchmarks;
- `06_deliverables/`: somente entregas finais e suas capas;
- `07_manifests/`: hashes, fontes, licenças, decisões e índice do projeto.

Antes de publicar pacote de skills/assets no Drive, rode a auditoria com `--drive-staging`. Bloqueie qualquer bruto/master/proxy, vídeo stock ou entrega final. MP4/MOV só podem aparecer ali como VFX/overlay/transição reutilizável, claramente classificado e licenciado.

Não apague duplicados automaticamente. Calcule hash, liste caminhos e peça decisão quando a remoção puder afetar jobs.
