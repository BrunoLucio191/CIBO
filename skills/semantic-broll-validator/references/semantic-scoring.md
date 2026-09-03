# Semantic scoring and anti-keyword traps

## Semantic brief

Record these fields before searching:

```text
transcript_window:
speaker_and_actor:
subject:
claim_or_argument:
cause_and_effect:
literal_or_figurative:
purpose: explain | prove | warn | inspire | sell | transition
emotion:
time_and_place_constraints:
visual_function:
must_show:
must_not_imply:
```

## Weighted score

Score each criterion from 0–5:

```text
total =
  claim_and_causal_fit * 0.30 +
  narrative_function * 0.20 +
  actor_scope_and_setting * 0.15 +
  literal_figurative_accuracy * 0.15 +
  emotional_and_client_fit * 0.10 +
  layout_and_technical_fit * 0.05 +
  license_certainty * 0.05
```

Approve only at 4.0/5 or above. `claim_and_causal_fit` must be at least 4. For commercial work, `license_certainty` must be 5.

## Counterfactual tests

Ask all four:

1. Would this visual still appear relevant under ten unrelated corporate sentences? If yes, it is generic rather than explanatory.
2. Does the visual preserve the same actor, action, object, and consequence as the claim?
3. Could a viewer infer a meaning the speaker did not state? If yes, name that risk and reject when material.
4. If the matching keyword were removed from the transcript, would the conceptual relationship remain? If no, reject.

## Common traps

| Spoken expression | Superficial mismatch | Better visual direction |
|---|---|---|
| “correr contra o tempo” | random person jogging | deadline pressure, compressed workflow, time-sensitive decision |
| “tirar a pesquisa do papel” | close-up of loose paper | lab-to-market transfer, prototype, researcher meeting industry |
| “brilho nos olhos” | macro shot of an eye | founder conviction, engaged presentation, purposeful decision |
| “mercado” | supermarket aisle | the specific industry, customers, transaction, adoption, or commercialization |
| “impacto positivo” | collision or explosion | measured social/environmental outcome and affected community |
| “proteger a ideia” | generic shield animation | patent filing, IP documentation, confidential design review |
| “caminho difícil” | mountain hike | the actual entrepreneurial tradeoff or decision being discussed |
| “equilíbrio” | yoga pose | the competing priorities and dynamic adjustment named by the speaker |
| “Fator R” | isolated letter R | payroll-to-revenue calculation, accounting context, tax decision |

These directions are not automatic replacements. They still need to match the specific sentence, speaker, client, and consequences.

## Search construction

Build queries from the full concept:

```text
[actor] + [specific action/process] + [setting] + [visual function]
[cause] + [consequence] + [industry/context]
[document/process/evidence] + [specific claim]
```

Bad: `running`, `market`, `impact`, `research`.

Better: `small business owner reviewing difficult strategic options office`, `researcher presenting prototype to manufacturing company`, `medical clinic accountant reviewing payroll revenue ratio`.

## Final approval note

Store:

```text
approved_because:
meaning_preserved:
possible_misread:
why_this_candidate_beats_the_alternatives:
```

If these fields cannot be answered concretely, do not approve the insert.
