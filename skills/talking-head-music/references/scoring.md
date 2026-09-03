# Music decision framework

## Brief fields

For every cut, record:

```text
subject:
purpose: inform | convince | inspire | sell | entertain
speaker_energy: 1–5
start_emotion:
end_emotion:
narrative_turn:
tempo_range_bpm:
texture/instrumentation:
density: sparse | moderate | dense
avoid:
```

Do not reuse a brief merely because two cuts share a speaker.

## Direction map

| Spoken function | Useful direction | Typical rejection |
|---|---|---|
| Innovation/explanation | positive futuristic pulse, 95–118 BPM, sparse synth/bass | playful EDM, sci-fi effects, busy arpeggio |
| Motivation/decision | hopeful or propulsive build, 100–125 BPM | trailer bombast, sports brass under calm speech |
| Reflection/balance | warm ambient/acoustic bed, 70–95 BPM | melancholy that changes the meaning, sleepy pads |
| Risk/protection | restrained serious pulse, 75–105 BPM | horror tension, comic pizzicato |
| Finance/authority | minimal confident rhythm, 90–115 BPM | luxury swagger, trap bass, anxious ticking |
| Purpose/sustainability | organic hopeful texture, 75–105 BPM | generic ukulele, sentimental piano, nature cliché |

## Weighted scoring

Score each criterion from 0–5, then calculate:

```text
total =
  semantic_and_emotional_fit * 0.30 +
  energy_and_speech_cadence * 0.20 +
  voice_compatibility * 0.20 +
  narrative_arc_and_impact * 0.15 +
  client_identity * 0.10 +
  license_certainty * 0.05
```

Reject below 3.5/5 even if it ranks first. A license score below 5 rejects the item when the project is commercial.

## Audition protocol

Use three excerpts when possible:

1. first 3–6 s, to test whether the hook acquires the right expectation;
2. 12–18 s around the main thesis or reveal;
3. final 5–8 s, to test whether the music resolves with the speaker.

Normalize candidate audition levels before comparing. Test the music under the actual processed voice, not against a transcript alone. Prefer the track whose rhythm leaves space at phrase endings and whose spectral center does not mask consonants.

## Mix and manifest

- Record `source_offset_seconds`; choose the section with the best arc for the cut.
- Use 0.6–1.2 s entry fade unless a motivated hit begins the piece.
- Start music roughly 18–25 dB below dialogue, then adjust by ear and measured source loudness.
- Duck moderately; a 300–500 ms release usually avoids audible pumping in speech.
- Record title, author, source URL, file URL, item license, license URL, download date, attribution, commercial-use status, SHA-256, source loudness, estimated BPM, chosen offset, and final gain.
