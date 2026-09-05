# Prose variant of a SOL fixture — generation prompt

> **Frozen 2026-08-22, revised 2026-08-23.** This is the mechanical pass that produces the `prose-generated`
> variant of §5.4 of `doc/experiment-minimum-context.md`, and a frozen artefact under §8.1
> item 6. Any change to the prompt text below invalidates every prose document produced
> with it: those documents are regenerated, never patched. The same holds for the documents
> themselves — a prose variant that reads badly is a defect of this prompt, and is fixed
> here.
>
> **How the variants are produced.** One agent, one pass, no conversation, no hand-tuning of
> the result. The agent is given this file and one fixture file, and is told to read nothing
> else — no SOL specification, no skill, no other file of the repository. Model: Claude
> Opus 5, run as a Claude Code subagent at its default sampling settings, which are not
> settable from the harness. A prose document produced by a different model or a different
> version of this prompt is a different artefact and must be labelled as one.
>
> **What validated it.** Five generations against `w2-branching/support-intake`, then one
> generation of every fixture in the suite, each read
> for two things: that the result is prose rather than the source notation with its
> punctuation removed, and that a reader following it forward, once, reaches the results the
> source process produces. Three defects were found and each was fixed here, never in the
> output — an instruction to carry the source wording across, which made the generator copy
> the source sentence by sentence and keep its intermediate variables; a missing prohibition
> on referring to where the material sits on the page, which produced a sentence true under
> one runner and false under the other; and an output example that quoted its numbers,
> teaching a type the contract does not accept. The
> suite pass found a fourth: nothing said what to do with a sentence elsewhere in the file
> that points at the process definition, so one generator re-pointed it and five left a
> reference dangling at a section that no longer exists. A fifth followed: two generators set
> the lines to be emitted inside inline code spans, and the backtick that wraps such a line is
> a character the reader may copy into it — the trace parser anchors at the start of the line
> and would have dropped every one of them.
>
> **Sixth defect, 2026-08-23, found in MAIN's data.** The bullet on the returned object
> asked for "the instruction to return it alone with nothing around it", one line below
> the bullet requiring every verbatim line to survive. A document holding both has
> forbidden its own trace lines, and the prohibition sits at the end, where it wins. Every
> model obeyed it: on `support-intake` 61 of MAIN's 69 `prose-generated` runs returned the
> JSON object alone, `stop_reason` `stop`, not one trace line. Conditional fidelity was
> unscoreable on them and comprehension scored 0.0, against 0.59-0.81 for the same runs
> read off the payload they did return. The same contradiction had been found in the SOL
> documents on 2026-08-22 (SS12, correction (c)) and fixed there; nobody looked here, so this
> prompt went on producing it from its own instruction rather than inheriting it. Per the
> rule stated above, every document generated with the previous text is invalid and is
> regenerated -- all seven, not only the one MAIN runs.
>
> **The audit that followed, same day.** Six defects in, five of them collisions between two
> rules of this prompt rather than mistakes in either, it was read once through against
> itself. Two more of the same shape: "its way of labelling branches" and "no advice on how to
> recognise anything" are prohibitions on style, stated without exempting what the source
> states or what the scoring tool reads — the verbatim lines carry the notation's branch
> labels and its variable names, and `classify-request` states in the source how the product
> is to be judged. On support-intake the generator improvised its way past the first and kept
> the second; neither outcome was this prompt's doing. One governing sentence now says where
> the style prohibitions stop, in place of an exception per rule. Also corrected: this file
> called its own output `prose-derived`, a name retired on 2026-08-22.

---

You are given one fixture file: a markdown document with YAML frontmatter, one or more
sections of task material, and a section containing a process definition written in a
structured notation.

Rewrite that one section — and only that one — as a written explanation of the same work.
Leave everything else in the file exactly as it is.

## Who you are writing for

Someone who has never seen that notation and never will. They will read your text and do the
work by hand. They know nothing about the task beyond what the file tells them.

So write the way a competent colleague writes a working instruction: paragraphs, headings
where they help, plain sentences. Explain the work. **Do not imitate the shape of the source.**
It is a machine notation and you are not translating it — you are saying, in your own words,
what someone has to do.

Concretely, that means not carrying across the things that belong to the notation rather than
to the work: its keywords, its nesting, its habit of naming and assigning intermediate values,
its way of labelling branches, the commands it uses to fetch things. Say what is read, not
with which command. Say what makes a case different, not what flag would be set to mark it.

Those prohibitions govern your prose and stop there. They never reach a line the source says
to emit verbatim, and they never delete something the source itself states. Such a line may
well carry the notation's own branch labels and its variable names, and it keeps every one of
them exactly as it stands — a scoring tool reads those lines, and it is reading for the
notation, not for your prose. Where one contains a placeholder, that placeholder is the single
point at which a name from the source has to survive into your reader's hands: leave it as it
is, and let your own sentence introducing the line say, in your words, what belongs in its
place.

Nor should you refer to how the document carrying your text is laid out. Your reader may have
the material in front of them already, or may have to go and fetch it; either way they know
what they are looking for from your description of it, and a sentence telling them where on
the page it sits is true in one setting and false in the other.

## What must be exact

The work itself, and three things about its output:

- **Every line the source says to emit verbatim** stays verbatim — the bracketed prefix, the
  spacing, the casing, the placeholders. A scoring tool reads these lines; a changed
  character is a failed run. Set each one out on a line of its own with nothing wrapped
  around it. Quotation marks or backticks set around such a line are characters your reader
  may copy into what it writes, and the tool that reads those lines will not recognise a line
  that starts with one.
- **The returned object**: every key, its casing, its type, its null cases, and the
  instruction that it carries those keys and no others. Scope that instruction to the
  object and never to the output as a whole. The lines of the bullet above are emitted
  alongside it, so a sentence forbidding anything other than the object forbids them
  too -- and it is the last thing your reader meets, which makes it the one they obey.
  Say instead that those lines are not part of what is returned.
- **Every literal value**: numeric constants, enumerated values, ids, the names of tables and
  fields in the material above.

Someone following your text must reach the same results as someone following the source. That
is the whole of the fidelity you owe it.

## What prose has to say out loud

The source carries some things in its structure. Your text has no structure to carry them, so
each becomes a sentence or it is lost. Check for these before you finish:

- Work that repeats — that it repeats, over what, in what order, and that after finishing one
  round you go back and start the next.
- Where a stretch of work ends: which instructions belong to one case only, and which apply
  whatever happened.
- Order inside a case — in particular, a case that both records something and ends the run
  must be written with the recording first. Your reader does what it reads in the order it
  reads it.
- An early ending: what stops, what is left as it stands, and what has been accumulated at
  that moment.
- Which case wins, when two could be true of the same thing. If they cannot both be true, say
  nothing — do not invent a precedence.

## What not to add

Nothing that is not in the source. No worked example of the task, no case walked through, no
arithmetic shown. No cases beyond the ones the source distinguishes. No explanation of why a
rule exists or what it protects against — state the rule. No advice of your own on how to
recognise anything — though a constraint the source itself puts on how something is decided
is part of the work and stays, in your words. Say each thing once, where it applies.

One thing you may add: at the end, an example showing the **shape** of the returned object,
with placeholders where the values go. Each placeholder sits where its value would and is
written as that value would be written — a number bare, a string in quotes — because an example
that misstates a type teaches the wrong output. It shows how the object is built, never how the
task is judged.

## Before you output

Read your text from the top, once, forward only, never looking ahead — the way your reader
will. At every point, do you know what to do next from what you have read so far? Two failures
are common and both are silent: ending the run before you have read the instruction that
records the current round, and finishing a round with nothing telling you to start the next.

If you find either, fix the order or add the missing sentence. Removing an ambiguity the
source does not have is required, not an addition.

## What you output

The complete fixture file, unchanged except that the process-definition section is gone and a
section headed `## The procedure` stands in its place. Do not touch the frontmatter, the input
data, or any reference material. Do not rename anything, do not add sections.

One exception, and only one. If a sentence elsewhere in the file points at the process
definition — telling the reader to execute it, naming the notation it is written in, saying
where it sits — that sentence now points at nothing. Re-point it at your text and leave the
rest of it alone: the same instruction, about the thing that is actually there.

The file and nothing else — no preamble, no account of your choices.
