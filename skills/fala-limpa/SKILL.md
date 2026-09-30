---
name: fala-limpa
description: Audite e limpe a fala de cortes de talking head e entrevista antes do render e no QA — detecta e manda cortar outra voz (entrevistador, alguém ao fundo), hesitações ("ééé", "ahn", pausas de pensamento) e palavra final engolida pelo fade. Use em todo corte de fala de qualquer cliente (Fernanda/Malu, podcasts, depoimentos), junto com a skill de corte do cliente.
---

# Fala limpa

O corte só tem a voz de quem está falando, sem hesitação e sem palavra cortada. Três erros que o usuário reprovou num reel entregue (Malu, `C0097`) e que **não podem voltar**:

1. **Outra voz no vídeo.** A cauda da pergunta do entrevistador ("e o que diferencia?") entrou antes de "É a micronização"; uma pessoa ao fundo disse "vai preparando o corpo"; uma terceira pessoa disse "ou deixa sair, né?". O Whisper escreve tudo como se fosse a falante, e o tempo de palavra dele errou 0,5 s justamente no "é" colado na pergunta.
2. **Hesitação** ("Eeee meu marido", pausas de 0,5–0,9 s de quem está pensando): "deixa anti profissional".
3. **Palavra final cortada**: o fade de 0,35 s do fim caiu sobre "desconforto".

## Ferramenta

Ambiente próprio (não usar o Python do sistema):

```bash
uv venv ~/.venvs/audiotools --python 3.12
VIRTUAL_ENV=~/.venvs/audiotools uv pip install torch torchaudio speechbrain silero-vad librosa soundfile numpy scikit-learn
```

```bash
~/.venvs/audiotools/bin/python scripts/audit_fala.py --audio master16k.wav --words whisper_large.json \
  --range IN OUT --job job.json --out qa/fala_limpa.json
```

- Silero VAD acha a voz; SpeechBrain ECAPA (`speechbrain/spkrec-ecapa-voxceleb`, público) gera embeddings em janelas de 0,8 s a cada 0,1 s; clusterização define a falante principal (cluster com mais fala).
- **Volume não decide quem fala**: o entrevistador da Malu falava *mais alto* que ela (−15 dB) e a pessoa do fundo mais baixo (−41 dB). Decide o timbre (similaridade < 0,25 com a principal).
- Região que só encosta numa emenda é remedida com janela inteiramente dentro do trecho mantido (a janela de 0,8 s atravessa o corte e "vê" a voz cortada).
- **Rode com GPU (MPS/CUDA).** No CPU este torch levou ~90 s por lote de 64 janelas; no MPS, 0,27 s.
- Janela < 0,5 s não serve para decidir locutor (dá ~0 para todo mundo). Nesses casos decida pelo envelope (`find_pauses.py env`) e pelo tempo de palavra das duas transcrições.

## Fluxo (antes de escrever a legenda)

1. Transcreva o trecho com large-v3 **e** com um prompt que faz o Whisper escrever hesitações:
   `--initial-prompt "Ééé... então, ahn, é... hum, a gente, é, tipo, né. Ééé, eu acho que, ahn..."`.
   O prompt também **inventa** "é," em pausa vazia: confirme cada hesitação no envelope antes de cortar.
2. Rode `audit_fala.py` na fonte com o job. Para cada `outra_voz`: corte de silêncio a silêncio. Quando não há silêncio (fala sobreposta), corte no ponto mais baixo do envelope entre a última sílaba da outra voz e o ataque da principal (Malu: "né?" terminava em 96,19 e "Só" começava em 96,20).
3. Hesitação: corte vogal sustentada isolada ("Eeee" de 0,6 s antes de "meu"). Pausas internas > 0,45 s viram ~0,2 s. Cada corte novo precisa de troca de enquadramento (jump cut no mesmo quadro é proibido).
4. **Teste só no áudio** (`atrim` dos trechos) e transcreva com os dois modelos. Os erros que isso pegou num único reel: "passa para…" (sem "a fina": a janela de locutor misturou a palavra com a voz do fundo), "a camisa, por sair" (sem "o suor": o silêncio achado era entre "o" e "suor"), "os pacientes…" (sem "assustam": as quedas eram consoantes, não pausas), "turir" (sem "-ta": o silêncio era o fechamento do "t"). **Queda de volume curta no meio de palavra é consoante oclusiva, não pausa.**
5. Fim: `tail_hold` (fernanda-produto) congela o último quadro em silêncio para o fade não engolir a última palavra.
6. **Nunca** use compressor/leveling para "salvar" uma frase baixa antes de confirmar que ela é da falante: a frase baixa da Malu era outra pessoa, e o compressor a deixou mais audível.
7. No QA, rode de novo sobre o áudio do MP4 final. `outra_voz` exatamente na entrada de uma referência costuma ser o whoosh/clique: confirme na fonte sem SFX.

## Bloqueia a entrega

Qualquer `outra_voz` confirmada, hesitação audível, `fim_cortado`, ou palavra perdida no teste de áudio.
