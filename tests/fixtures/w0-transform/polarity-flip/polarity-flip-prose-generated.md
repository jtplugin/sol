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

Execute strictly the procedure below. All the input you need is in this document.

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

You have one English sentence to work on: the sentence given in this document. The work comes in
two stages, and the second uses what the first produced, so take them in the order given here.

### First stage: taking the sentence apart

Start by writing out this line, exactly as it stands:

[fixture-w0-polarity-flip][main] BRANCH: parse

Then read the sentence and settle four things about it.

The **subject** is the noun phrase standing before the verb. Keep its wording exactly as the
sentence has it, and lowercase it.

The **object** is the noun phrase standing after the verb. Again, keep the wording exactly as the
sentence has it, and lowercase it.

The **verb** is the sentence's verb in its base form: no third-person `s` on the end, and no
`does not` auxiliary in front of it.

The **polarity** is what the sentence does with that verb. It is `negative` when the sentence
contains `does not`, and `affirmative` in every other case.

### Second stage: turning the sentence around

Write out this line, exactly as it stands:

[fixture-w0-polarity-flip][main] BRANCH: flip

Then produce the **flipped** sentence: take the rendering rule for `flipped` set out in this
document and apply it to the subject, the verb, the object and the polarity you settled in the
first stage.

### What you hand back

When both stages are done, return a single JSON object. It carries exactly these five keys, with
their casing precisely as written here, and no others:

`subject`, `verb`, `object`, `polarity`, `flipped`.

Each of the five values is a JSON string, holding the value you settled for it. None of them is
ever null or absent.

The two lines you wrote out along the way are not part of that object and are not returned inside
it; they stand on their own, and they still have to be written.

The object is built like this, with each placeholder standing where its value goes:

```json
{
  "subject": "<subject>",
  "verb": "<verb>",
  "object": "<object>",
  "polarity": "<polarity>",
  "flipped": "<flipped>"
}
```
