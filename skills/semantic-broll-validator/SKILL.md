---
name: semantic-broll-validator
description: Analyze, search, score, and approve B-roll for dialogue-led talking-head videos by matching the complete meaning and narrative function of a speech passage, not isolated keywords. Use when selecting, downloading, replacing, or auditing stock/reference footage, split-screen inserts, or visual examples for Reels, Shorts, ads, interviews, and business content.
---

# Semantic B-roll Validator

Approve a visual only when it clarifies the speaker's actual claim. A clip that illustrates one spoken word but changes, trivializes, or narrows the meaning is a mismatch.

Read [references/semantic-scoring.md](references/semantic-scoring.md) before evaluating candidates.

## Workflow

1. Read the complete sentence plus at least one sentence before and after it. Extend the window when a pronoun, example, contrast, or conclusion depends on earlier context.
2. Write a semantic brief containing the speaker, subject, claim, intended audience, purpose, literal or figurative status, emotional function, and what the passage explicitly does not mean.
3. Identify the visual function: evidence, example, process, consequence, environment, comparison, atmosphere, or pattern interruption. Do not add B-roll when the talking head is clearer.
4. Translate the claim into two to four concept-first searches. Search for the situation, relationship, or consequence; never build the query from a lone noun or verb.
5. Inspect the actual candidate segment, not only its title, tags, or thumbnail. Check actions, people, setting, visible text, brands, geography, implied socioeconomic context, and the moment before and after the proposed in-point.
6. For each candidate, write a one-sentence mapping: `This visual supports the claim because ...`. Then write the strongest possible mismatch risk. Reject any candidate whose mapping depends only on a shared keyword.
7. Score with the semantic matrix. Reject below 4.0/5, reject `claim_and_causal_fit` below 4, and reject uncertain commercial rights.
8. Test the candidate in the real layout with captions and speaker visible. Confirm it improves comprehension without creating a second competing story.
9. Download only the approved asset. Record the transcript window, semantic brief, queries, selected time range, score, rejection reasons, source, item-level license, and hash.

## Hard rejection rules

- Do not convert metaphors into literal stock footage unless the speaker is explicitly discussing the literal action.
- Do not use a generic industry clip merely because it shares the topic label. Match the specific claim, scale, actor, and consequence.
- Do not use a visual that silently changes who is acting, who benefits, the country, the type of business, or the direction of cause and effect.
- Do not use a candidate that could fit almost any corporate sentence. If removing the transcript does not make the intended connection recoverable, the fit is probably superficial.
- Do not let motion, production value, or an attractive thumbnail compensate for weak meaning.
- Do not keep a B-roll slot filled when every available candidate is weak. Use the talking head, lettering, a document, or a simple graphic instead.

## Deliverable

Return one row per proposed insert with:

```text
transcript_window | literal_or_figurative | claim | visual_function |
candidate | semantic_mapping | mismatch_risk | score | decision |
source_url | license | selected_range
```

List rejected candidates and the exact semantic reason. Do not report only “not relevant.”
