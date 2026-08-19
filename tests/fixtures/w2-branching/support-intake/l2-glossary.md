# SOL tag glossary

Semantics of the SOL constructs used in this fixture's script, condensed from `spec/sol-0.6.md`.

## ROUTINE

An ordered list of instructions. Executed top to bottom unless a construct inside it (like `REPEAT` or `RETURN`) changes that.

## RUN

Executes a command verbatim. What you write is what gets executed — the agent does not interpret it. `{{placeholder}}` marks parts the agent must resolve from context; everything outside `{{...}}` is passed as written.

## IF

Binary decision. Has `when` (the condition), `then` (instructions run if the condition holds), and an optional `else` (instructions run otherwise).

## TODO

A natural language instruction. The agent interprets and executes it in the context of the process.

## RETURN

Ends the current process cleanly and hands control back to whoever invoked it. Execution resumes above this point; nothing further in the current routine runs. The normal way a process finishes early.

## SUB

Defines a subroutine, identified by `name`, with its own `ROUTINE`. Can appear anywhere in the enclosing `ROUTINE` — definition order does not matter. Shares the calling agent's context (no input/output boundary). Invoked via `CALL`.

## CALL

Invokes a `SUB` defined in the same file, by name. Executes in the shared context.

## REPEAT

Repeats a nested `ROUTINE`. `foreach` names the target iterated — one pass of the `ROUTINE` per element of the target, in the given order.

## WHEN

Evaluates a list of `{when, then}` conditions and executes the branch(es) whose condition holds, plus an optional trailing `else` (a `then`-less branch) executed only if no `when` matched. Behavior is fully predictable when the conditions are mutually exclusive.
