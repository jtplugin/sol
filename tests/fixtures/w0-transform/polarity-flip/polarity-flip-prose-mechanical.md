---
name: fixture-w0-polarity-flip
version: "1.0"
schema: "../../../../sol-schema.json"
system_prompt: "You are a precise language analyst. You read one sentence and re-express it in a fixed structured form, then transform that form. You never add commentary."
description: "W0 self-contained transform. Two dependent passes over a single inline sentence: first express it in a closed predicate form (subject, verb, object, polarity), then flip the polarity and re-render the sentence in English. No branching, no iteration, no tools — the purest linear shape in the suite. The lexicon is closed and the rendering rule is stated, so exactly one output is correct."
accepts:
  sentence:
    required: true
    desc: "one inline English sentence, present simple, third person singular, of the form <subject> <verb> <object> or <subject> does not <verb> <object>"
returns:
  subject:
    required: true
    desc: "the subject noun phrase, verbatim from the sentence, lowercase"
  verb:
    required: true
    desc: "the verb in its base form (infinitive without 'to'), e.g. 'read' for 'reads'"
  object:
    required: true
    desc: "the object noun phrase, verbatim from the sentence, lowercase"
  polarity:
    required: true
    desc: "polarity of the INPUT sentence: 'affirmative' or 'negative'"
  flipped:
    required: true
    desc: "the sentence with the opposite polarity, rendered by the rule below; no trailing period"
---

# Transformation task

Follow strictly the procedure described below. All the input you need is in this document.

## Sentence

```text
{{sentence}}
```

## Rendering rule for `flipped`

The rule is mechanical and admits exactly one output. Apply it verbatim.

- If the input is **affirmative**, `flipped` is `<subject> does not <verb> <object>` — verb in base form.
- If the input is **negative**, `flipped` is `<subject> <verb-s> <object>`, where `<verb-s>` is the
  third-person singular of the base verb: add `es` when the base form ends in `s`, `sh`, `ch`, `x` or
  `z`; change a final `y` preceded by a consonant into `ies`; otherwise add `s`.

Use the subject and object exactly as they appear in the sentence, lowercased. No leading capital,
no trailing period, single spaces between words.

## The procedure

### What it does

- Emit verbatim: [fixture-w0-polarity-flip][main] BRANCH: parse
- Set subject to the noun phrase before the verb, lowercased, wording unchanged.
- Set object to the noun phrase after the verb, lowercased, wording unchanged.
- Set verb to the base form of the sentence's verb: no third-person 's', no 'does not' auxiliary.
- Set polarity to 'negative' when the sentence contains 'does not', and to 'affirmative' otherwise.
- Emit verbatim: [fixture-w0-polarity-flip][main] BRANCH: flip
- Set flipped by applying the rendering rule stated above to subject, verb, object and polarity.
- Build the result as JSON: {"subject": <subject>, "verb": <verb>, "object": <object>, "polarity": <polarity>, "flipped": <flipped>}. All five values are JSON strings. No other fields. Respect exact key casing.
- End this process and hand control back to whoever invoked it, yielding: {{result}} [from context: result]
