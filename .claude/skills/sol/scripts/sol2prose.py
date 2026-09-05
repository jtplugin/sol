#!/usr/bin/env python3
"""
sol2prose.py — Render a SOL 0.6 process as narrative prose.

MIT License
Copyright (c) 2026 Gianni Tommasi

The inverse direction of the skill: `guides/translation.md` turns a document into SOL;
this turns SOL back into a document. The output is the inverse of *Pass 0 — Narrative*
in `guides/authoring.md`: the process restated as plain prose in execution order — what
happens, in what sequence, with which decisions, loops, error paths and human gates.

Its purpose is **round-trip validation**. You wrote the process as JSON; read it back as
prose and check that it says what you meant. If the prose reads wrong, the SOL is wrong.
A diagram shows the *shape* of the flow; this shows its *content* — the leaf texts, the
contracts, the model tiers, the placeholders.

Two rules govern what this script may do:

  1. It RENDERS, it does not JUDGE. None of `sol-lint.py`'s rules are reproduced here:
     no severities, no findings, no verdicts on missing guards or decorative contracts.
     Rendering and linting are separate jobs; duplicating the linter here would make the
     two diverge at the first change to the spec.

  2. It NEVER TRANSLATES. Only the connective scaffolding ("For each…", "Otherwise:") is
     templated per language via --lang. Every leaf — TODO text, RUN command, conditions,
     contract descriptions — is quoted verbatim in whatever language the author wrote it.
     That is what makes the round-trip comparison against the source exact.

Note: `extract_sol_docs()` is duplicated from `sol-lint.py` on purpose. Each script in
this folder is self-contained and copyable anywhere, with no cross-imports — see
`doc/sol-convertibility.md` § Portability guarantees.

Usage:
    python3 sol2prose.py process.json              # writes process.prose.md
    python3 sol2prose.py process.json output.md    # writes to output.md
    python3 sol2prose.py process.json --stdout     # prints to stdout
    python3 sol2prose.py process.md                # extracts the ```json fences and renders each
    python3 sol2prose.py process.json --lang it    # scaffolding in Italian (default: en)
"""

import json
import re
import sys
from pathlib import Path

# ----------------------------------------------------------------------------
# Scaffolding templates. Leaf texts are never touched — only these strings are
# language-dependent. Adding a language = adding a key with the same slots.
# ----------------------------------------------------------------------------

TEMPLATES = {
    "en": {
        "meta_version":    "Version {version}",
        "meta_model":      "Default model tier: {model}",
        "meta_role":       "The agent adopts this persona throughout: {role}",
        "meta_env":        "Commands run in `{env}`",
        "meta_ref":        "Spec reference: {ref}",
        "meta_import":     "Loads definitions from {paths}",
        "hdr_accepts":     "**It expects from whoever invokes it:**",
        "hdr_returns":     "**It hands back to its invoker:**",
        "hdr_steps":       "## What it does",
        "hdr_subs":        "## Subroutines",
        "hdr_agents":      "## Agents",
        "hdr_onerror":     "## If anything fails anywhere in this process",
        "hdr_body":        "**What it does:**",
        "sub_heading":     "### The subroutine «{name}»",
        "agent_heading":   "### The agent «{name}»",
        "agent_desc":      "{desc}",
        "empty_routine":   "This process has no steps.",
        "empty_body":      "Nothing happens here.",
        "c_required":      "required",
        "c_anyof":         "one of: {values}",
        "c_number":        "numeric",
        "c_json":          "valid JSON",
        "todo":            "{text}",
        "run":             "Run exactly: `{cmd}`",
        "if":              "If {cond}, then:",
        "else":            "Otherwise:",
        "when_intro":      "Depending on the case:",
        "when_branch":     "When {cond}:",
        "when_no_else":    "If none of these hold, nothing happens here.",
        "foreach":         "For each {target}:",
        "foreach_bare":    "For {target}:",
        "while":           "While {cond}, repeat:",
        "until":           "Repeat until {cond}:",
        "for":             "Repeat {count} times:",
        "loop_bare":       "Repeat:",
        "sub_def":         "Define the subroutine «{name}» — see *Subroutines* below.",
        "call":            "Call the subroutine «{name}», which sees everything this process sees.",
        "agent_def":       "Define the agent «{name}» — see *Agents* below.",
        "spawn":           "Hand off to the agent «{name}», which runs in a clean context of its own.",
        "spawn_with":      "Passing it: {payload}",
        "spawn_returns":   "Expecting back: {payload}",
        "delegate":        "Delegate a one-off task to a sub-agent in a clean context: {task}",
        "import":          "Load the definitions from {paths}.",
        "return_bare":     "End this process and hand control back to whoever invoked it.",
        "return_value":    "End this process and hand control back to whoever invoked it, yielding: {value}",
        "halt_bare":       "Stop the entire run.",
        "halt_msg":        "Stop the entire run — {msg}",
        "wait":            "Pause and ask the human: {prompt} — wait for the answer before continuing.",
        "onerror":         "If that fails:",
        "model_tag":       "[{model} model]",
        "role_tag":        "[as: {role}]",
        "slots":           "[from context: {names}]",
        "unknown":         "Unrecognized instruction, left as written: `{raw}`",
        "footer":          "_Narrative rendering of `{source}` — generated by sol2prose.py. "
                           "Leaf texts are quoted verbatim from the source._",
    },
    "it": {
        "meta_version":    "Versione {version}",
        "meta_model":      "Tier di modello predefinito: {model}",
        "meta_role":       "L'agente assume questa persona per tutto il processo: {role}",
        "meta_env":        "I comandi girano in `{env}`",
        "meta_ref":        "Riferimento della spec: {ref}",
        "meta_import":     "Carica le definizioni da {paths}",
        "hdr_accepts":     "**Si aspetta da chi lo invoca:**",
        "hdr_returns":     "**Restituisce a chi lo ha invocato:**",
        "hdr_steps":       "## Che cosa fa",
        "hdr_subs":        "## Subroutine",
        "hdr_agents":      "## Agenti",
        "hdr_onerror":     "## Se qualcosa fallisce, in qualunque punto del processo",
        "hdr_body":        "**Che cosa fa:**",
        "sub_heading":     "### La subroutine «{name}»",
        "agent_heading":   "### L'agente «{name}»",
        "agent_desc":      "{desc}",
        "empty_routine":   "Questo processo non ha passi.",
        "empty_body":      "Qui non succede nulla.",
        "c_required":      "obbligatorio",
        "c_anyof":         "uno fra: {values}",
        "c_number":        "numerico",
        "c_json":          "JSON valido",
        "todo":            "{text}",
        "run":             "Esegui esattamente: `{cmd}`",
        "if":              "Se {cond}, allora:",
        "else":            "Altrimenti:",
        "when_intro":      "A seconda del caso:",
        "when_branch":     "Quando {cond}:",
        "when_no_else":    "Se nessuna di queste vale, qui non succede nulla.",
        "foreach":         "Per ogni {target}:",
        "foreach_bare":    "Per {target}:",
        "while":           "Finché {cond}, ripeti:",
        "until":           "Ripeti finché {cond}:",
        "for":             "Ripeti {count} volte:",
        "loop_bare":       "Ripeti:",
        "sub_def":         "Definisci la subroutine «{name}» — vedi *Subroutine* più sotto.",
        "call":            "Chiama la subroutine «{name}», che vede tutto ciò che vede questo processo.",
        "agent_def":       "Definisci l'agente «{name}» — vedi *Agenti* più sotto.",
        "spawn":           "Passa il lavoro all'agente «{name}», che gira in un contesto pulito tutto suo.",
        "spawn_with":      "Gli passi: {payload}",
        "spawn_returns":   "Ti aspetti indietro: {payload}",
        "delegate":        "Delega un compito una tantum a un sotto-agente in contesto pulito: {task}",
        "import":          "Carica le definizioni da {paths}.",
        "return_bare":     "Termina questo processo e restituisci il controllo a chi lo ha invocato.",
        "return_value":    "Termina questo processo e restituisci il controllo a chi lo ha invocato, "
                           "cedendo: {value}",
        "halt_bare":       "Ferma l'intera esecuzione.",
        "halt_msg":        "Ferma l'intera esecuzione — {msg}",
        "wait":            "Fermati e chiedi all'umano: {prompt} — aspetta la risposta prima di proseguire.",
        "onerror":         "Se fallisce:",
        "model_tag":       "[modello {model}]",
        "role_tag":        "[come: {role}]",
        "slots":           "[dal contesto: {names}]",
        "unknown":         "Istruzione non riconosciuta, riportata com'è: `{raw}`",
        "footer":          "_Resa narrativa di `{source}` — generata da sol2prose.py. "
                           "I testi foglia sono citati verbatim dal sorgente._",
    },
}

PLACEHOLDER_RE = re.compile(r"\{\{(.*?)\}\}")

# A `foreach` target is often already written as "each revision in the table" (or its
# Italian equivalent). When it is, the scaffolding drops its own "each" instead of
# rewriting the leaf — the leaf is never touched, only the template around it changes.
FOREACH_SELF_QUANTIFIED = ("each ", "ogni ", "ciascun")


class Sol2Prose:
    """Renders a SOL document as narrative prose. Deterministic, no judgment."""

    def __init__(self, lang: str = "en"):
        self.t = TEMPLATES[lang]
        self._sub_defs: list[tuple[str, dict]] = []
        self._agent_defs: list[tuple[str, dict]] = []
        self._seen_subs: set[str] = set()
        self._seen_agents: set[str] = set()

    # ------------------------------------------------------------------
    # Text helpers — never truncate, never rewrite, never translate.
    # ------------------------------------------------------------------

    @staticmethod
    def _flat(value) -> str:
        """A leaf value as one line. Newlines become spaces so the nesting stays readable."""
        if value is None:
            return ""
        if not isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        return value.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()

    def _slots(self, *texts) -> str:
        """The `{{...}}` slots found in the given texts, as a trailing marker (or "")."""
        names: list[str] = []
        for text in texts:
            if not isinstance(text, str):
                continue
            for raw in PLACEHOLDER_RE.findall(text):
                name = raw.strip()
                if name and name not in names:
                    names.append(name)
        if not names:
            return ""
        return " " + self.t["slots"].format(names=", ".join(names))

    def _tags(self, block: dict) -> str:
        """Trailing `model` / `role` markers — intent that is invisible in a flowchart."""
        out = ""
        if isinstance(block, dict):
            if block.get("model"):
                out += " " + self.t["model_tag"].format(model=self._flat(block["model"]))
            if block.get("role"):
                out += " " + self.t["role_tag"].format(role=self._flat(block["role"]))
        return out

    @staticmethod
    def _bullet(level: int, text: str) -> str:
        return "  " * level + "- " + text

    # ------------------------------------------------------------------
    # Contracts
    # ------------------------------------------------------------------

    def _contract_lines(self, contract, level: int = 0) -> list[str]:
        """accepts/returns as bullets: one per field for the structured form, verbatim for a string."""
        if contract is None:
            return []
        if not isinstance(contract, dict):
            return [self._bullet(level, self._flat(contract) + self._slots(contract))]

        lines = []
        for field, spec in contract.items():
            lines.append(self._bullet(level, f"`{field}`" + self._field_suffix(spec)))
        return lines

    def _field_suffix(self, spec) -> str:
        if not isinstance(spec, dict):
            flat = self._flat(spec)
            return f" — {flat}" if flat else ""

        parts = []
        if spec.get("required"):
            parts.append(self.t["c_required"])
        if "anyof" in spec:
            values = spec["anyof"]
            rendered = ", ".join(self._flat(v) for v in values) if isinstance(values, list) \
                else self._flat(values)
            parts.append(self.t["c_anyof"].format(values=rendered))
        if spec.get("number"):
            parts.append(self.t["c_number"])
        if spec.get("json"):
            parts.append(self.t["c_json"])

        desc = self._flat(spec.get("desc", ""))
        suffix = ""
        if desc:
            suffix += f" — {desc}"
        if parts:
            suffix += f" ({'; '.join(parts)})"
        return suffix

    def _contract_inline(self, contract) -> str:
        """A contract squeezed onto one line, for SPAWN.with / DELEGATE.returns and friends."""
        if isinstance(contract, dict):
            return "; ".join(f"`{f}`{self._field_suffix(s)}" for f, s in contract.items())
        return self._flat(contract)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def convert(self, sol_doc: dict, source_label: str = "") -> str:
        # Agent root form: a file whose single key is AGENT is unwrapped to its agent.
        if isinstance(sol_doc, dict) and set(sol_doc.keys()) == {"AGENT"}:
            sol_doc = sol_doc["AGENT"]
        if not isinstance(sol_doc, dict):
            return self.t["unknown"].format(raw=self._flat(sol_doc))

        out: list[str] = []
        name = self._flat(sol_doc.get("name", "process"))
        out.append(f"# {name}")
        out.append("")

        desc = self._flat(sol_doc.get("description", ""))
        if desc:
            out.append(f"> {desc}{self._slots(sol_doc.get('description'))}")
            out.append("")

        meta = []
        for field, key in (("version", "meta_version"), ("model", "meta_model"),
                           ("role", "meta_role"), ("env", "meta_env"), ("ref", "meta_ref")):
            if sol_doc.get(field):
                meta.append(self.t[key].format(**{field: self._flat(sol_doc[field])}))
        if "IMPORT" in sol_doc:
            meta.append(self.t["meta_import"].format(paths=self._paths(sol_doc["IMPORT"])))
        if meta:
            out.append(" · ".join(meta))
            out.append("")

        for field, header in (("accepts", "hdr_accepts"), ("returns", "hdr_returns")):
            if field in sol_doc:
                out.append(self.t[header])
                out.append("")
                out.extend(self._contract_lines(sol_doc[field]))
                out.append("")

        out.append(self.t["hdr_steps"])
        out.append("")
        routine = sol_doc.get("ROUTINE", [])
        if routine:
            out.extend(self._routine(routine, 0))
        else:
            out.append(self._bullet(0, self.t["empty_routine"]))
        out.append("")

        # Deferred definitions. Rendering one may register others, so drain the queues.
        out.extend(self._drain_definitions())

        if "ONERROR" in sol_doc:
            out.append(self.t["hdr_onerror"])
            out.append("")
            out.extend(self._routine(sol_doc["ONERROR"], 0))
            out.append("")

        if source_label:
            out.append("---")
            out.append("")
            out.append(self.t["footer"].format(source=source_label))
            out.append("")

        return "\n".join(out).rstrip() + "\n"

    def _drain_definitions(self) -> list[str]:
        out: list[str] = []
        subs_done = 0
        agents_done = 0
        sub_lines: list[str] = []
        agent_lines: list[str] = []

        while subs_done < len(self._sub_defs) or agents_done < len(self._agent_defs):
            while subs_done < len(self._sub_defs):
                name, block = self._sub_defs[subs_done]
                subs_done += 1
                sub_lines.append(self.t["sub_heading"].format(name=name) + self._tags(block))
                sub_lines.append("")
                sub_lines.extend(self._definition_body(block))
                sub_lines.append("")
            while agents_done < len(self._agent_defs):
                name, block = self._agent_defs[agents_done]
                agents_done += 1
                agent_lines.append(self.t["agent_heading"].format(name=name) + self._tags(block))
                agent_lines.append("")
                desc = self._flat(block.get("description", ""))
                if desc:
                    agent_lines.append(f"> {desc}")
                    agent_lines.append("")
                for field, header in (("accepts", "hdr_accepts"), ("returns", "hdr_returns")):
                    if field in block:
                        agent_lines.append(self.t[header])
                        agent_lines.append("")
                        agent_lines.extend(self._contract_lines(block[field]))
                        agent_lines.append("")
                agent_lines.extend(self._definition_body(block))
                agent_lines.append("")

        if sub_lines:
            out.append(self.t["hdr_subs"])
            out.append("")
            out.extend(sub_lines)
        if agent_lines:
            out.append(self.t["hdr_agents"])
            out.append("")
            out.extend(agent_lines)
        return out

    def _definition_body(self, block: dict) -> list[str]:
        body = block.get("ROUTINE", []) if isinstance(block, dict) else []
        out = [self.t["hdr_body"], ""]
        if not body:
            out.append(self._bullet(0, self.t["empty_body"]))
        else:
            out.extend(self._routine(body, 0))
        return out

    # ------------------------------------------------------------------
    # Routine and instruction dispatch
    # ------------------------------------------------------------------

    def _routine(self, routine, level: int) -> list[str]:
        if not isinstance(routine, list):
            return [self._bullet(level, self.t["unknown"].format(raw=self._flat(routine)))]
        if not routine:
            return [self._bullet(level, self.t["empty_body"])]
        out: list[str] = []
        for instr in routine:
            out.extend(self._instruction(instr, level))
        return out

    def _instruction(self, instr, level: int) -> list[str]:
        if not isinstance(instr, dict):
            return [self._bullet(level, self.t["unknown"].format(raw=self._flat(instr)))]

        dispatch = {
            "TODO":          self._todo,
            "RUN":           self._run,
            "IF":            self._if,
            "WHEN":          self._when,
            "REPEAT":        self._repeat,
            "SUB":           self._sub_def,
            "CALL":          self._call,
            "AGENT":         self._agent_def,
            "SPAWN":         self._spawn,
            "DELEGATE":      self._delegate,
            "IMPORT":        self._import,
            "RETURN":        self._return,
            "HALT":          self._halt,
            "WAITUSERINPUT": self._wait,
        }
        for key, handler in dispatch.items():
            if key in instr:
                out = handler(instr, level)
                out.extend(self._inline_onerror(instr, level))
                return out
        return [self._bullet(level, self.t["unknown"].format(raw=self._flat(instr)))]

    def _inline_onerror(self, instr: dict, level: int) -> list[str]:
        handler = instr.get("ONERROR")
        if handler is None and isinstance(instr.get("DELEGATE"), dict):
            handler = instr["DELEGATE"].get("ONERROR")
        if handler is None:
            return []
        # Nested under the step it guards, so the handler visibly belongs to it.
        return [self._bullet(level + 1, self.t["onerror"])] + self._routine(handler, level + 2)

    # ------------------------------------------------------------------
    # Leaves
    # ------------------------------------------------------------------

    def _todo(self, instr: dict, level: int) -> list[str]:
        raw = instr["TODO"]
        text = self.t["todo"].format(text=self._flat(raw))
        return [self._bullet(level, text + self._slots(raw) + self._tags(instr))]

    def _run(self, instr: dict, level: int) -> list[str]:
        raw = instr["RUN"]
        text = self.t["run"].format(cmd=self._flat(raw))
        return [self._bullet(level, text + self._slots(raw) + self._tags(instr))]

    def _return(self, instr: dict, level: int) -> list[str]:
        value = instr.get("RETURN")
        if value is None or value == "":
            return [self._bullet(level, self.t["return_bare"])]
        rendered = self._flat(value)
        return [self._bullet(level, self.t["return_value"].format(value=rendered)
                             + self._slots(value))]

    def _halt(self, instr: dict, level: int) -> list[str]:
        msg = instr.get("HALT")
        if msg is None or msg == "":
            return [self._bullet(level, self.t["halt_bare"])]
        return [self._bullet(level, self.t["halt_msg"].format(msg=self._flat(msg))
                             + self._slots(msg))]

    def _wait(self, instr: dict, level: int) -> list[str]:
        prompt = instr.get("WAITUSERINPUT")
        return [self._bullet(level, self.t["wait"].format(prompt=self._flat(prompt))
                             + self._slots(prompt))]

    @staticmethod
    def _paths(value) -> str:
        if isinstance(value, list):
            return ", ".join(f"`{p}`" for p in value)
        return f"`{value}`"

    def _import(self, instr: dict, level: int) -> list[str]:
        return [self._bullet(level, self.t["import"].format(paths=self._paths(instr["IMPORT"])))]

    # ------------------------------------------------------------------
    # Control flow
    # ------------------------------------------------------------------

    def _if(self, instr: dict, level: int) -> list[str]:
        block = instr["IF"]
        if not isinstance(block, dict):
            return [self._bullet(level, self.t["unknown"].format(raw=self._flat(block)))]
        cond = block.get("when", "")
        out = [self._bullet(level, self.t["if"].format(cond=self._flat(cond)) + self._slots(cond))]
        out.extend(self._routine(block.get("then", []), level + 1))
        if block.get("else"):
            out.append(self._bullet(level, self.t["else"]))
            out.extend(self._routine(block["else"], level + 1))
        return out

    def _when(self, instr: dict, level: int) -> list[str]:
        branches = instr["WHEN"]
        if not isinstance(branches, list):
            return [self._bullet(level, self.t["unknown"].format(raw=self._flat(branches)))]

        out = [self._bullet(level, self.t["when_intro"])]
        has_else = False
        for branch in branches:
            if not isinstance(branch, dict):
                out.append(self._bullet(level + 1, self.t["unknown"].format(raw=self._flat(branch))))
                continue
            if "when" in branch:
                cond = branch["when"]
                out.append(self._bullet(level + 1,
                                        self.t["when_branch"].format(cond=self._flat(cond))
                                        + self._slots(cond)))
                out.extend(self._routine(branch.get("then", []), level + 2))
            elif "else" in branch:
                has_else = True
                out.append(self._bullet(level + 1, self.t["else"]))
                out.extend(self._routine(branch["else"], level + 2))
        if not has_else:
            out.append(self._bullet(level + 1, self.t["when_no_else"]))
        return out

    def _repeat(self, instr: dict, level: int) -> list[str]:
        block = instr["REPEAT"]
        if not isinstance(block, dict):
            return [self._bullet(level, self.t["unknown"].format(raw=self._flat(block)))]

        header = self.t["loop_bare"]
        slot_src = None
        if "foreach" in block:
            slot_src = block["foreach"]
            target = self._flat(slot_src)
            key = "foreach_bare" if target.lower().startswith(FOREACH_SELF_QUANTIFIED) \
                else "foreach"
            header = self.t[key].format(target=target)
        elif "while" in block:
            slot_src = block["while"]
            header = self.t["while"].format(cond=self._flat(slot_src))
        elif "until" in block:
            slot_src = block["until"]
            header = self.t["until"].format(cond=self._flat(slot_src))
        elif "for" in block:
            slot_src = block["for"]
            header = self.t["for"].format(count=self._flat(slot_src))

        out = [self._bullet(level, header + self._slots(slot_src))]
        out.extend(self._routine(block.get("ROUTINE", []), level + 1))
        return out

    # ------------------------------------------------------------------
    # Subroutines and agents — marker in the flow, body in the appendix
    # ------------------------------------------------------------------

    def _sub_def(self, instr: dict, level: int) -> list[str]:
        block = instr["SUB"]
        if not isinstance(block, dict):
            return [self._bullet(level, self.t["unknown"].format(raw=self._flat(block)))]
        name = self._flat(block.get("name", "subroutine"))
        if name not in self._seen_subs:
            self._seen_subs.add(name)
            self._sub_defs.append((name, block))
        return [self._bullet(level, self.t["sub_def"].format(name=name))]

    def _agent_def(self, instr: dict, level: int) -> list[str]:
        block = instr["AGENT"]
        if not isinstance(block, dict):
            return [self._bullet(level, self.t["unknown"].format(raw=self._flat(block)))]
        name = self._flat(block.get("name", "agent"))
        if name not in self._seen_agents:
            self._seen_agents.add(name)
            self._agent_defs.append((name, block))
        return [self._bullet(level, self.t["agent_def"].format(name=name))]

    def _call(self, instr: dict, level: int) -> list[str]:
        name = self._flat(instr["CALL"])
        return [self._bullet(level, self.t["call"].format(name=name))]

    def _spawn(self, instr: dict, level: int) -> list[str]:
        name = self._flat(instr["SPAWN"])
        out = [self._bullet(level, self.t["spawn"].format(name=name) + self._tags(instr))]
        if "with" in instr:
            out.append(self._bullet(level + 1,
                                    self.t["spawn_with"].format(payload=self._contract_inline(instr["with"]))
                                    + self._slots(instr["with"])))
        if "returns" in instr:
            out.append(self._bullet(level + 1,
                                    self.t["spawn_returns"].format(payload=self._contract_inline(instr["returns"]))
                                    + self._slots(instr["returns"])))
        return out

    def _delegate(self, instr: dict, level: int) -> list[str]:
        block = instr["DELEGATE"]
        if not isinstance(block, dict):
            return [self._bullet(level, self.t["unknown"].format(raw=self._flat(block)))]
        task = block.get("task", "")
        out = [self._bullet(level, self.t["delegate"].format(task=self._flat(task))
                            + self._slots(task) + self._tags(block))]
        if "with" in block:
            out.append(self._bullet(level + 1,
                                    self.t["spawn_with"].format(payload=self._contract_inline(block["with"]))
                                    + self._slots(block["with"])))
        if "returns" in block:
            out.append(self._bullet(level + 1,
                                    self.t["spawn_returns"].format(payload=self._contract_inline(block["returns"]))
                                    + self._slots(block["returns"])))
        return out


# ----------------------------------------------------------------------------
# Markdown fence extraction — duplicated from sol-lint.py by design (see docstring).
# ----------------------------------------------------------------------------

def extract_sol_docs(text: str):
    """Yield (doc, label) for each ```json fence that parses to a SOL-looking object."""
    fences = re.findall(r"```json\s*\n(.*?)```", text, re.S)
    out = []
    for i, body in enumerate(fences):
        try:
            doc = json.loads(body)
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict) and ("ROUTINE" in doc or "AGENT" in doc):
            out.append((doc, f"fence#{i + 1}"))
    return out


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

USAGE = "Usage: sol2prose.py <process.json|process.md> [output.md] [--stdout] [--lang en|it]"


def main():
    # Keep the output safe on consoles that default to a non-UTF-8 codepage (e.g. Windows).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    argv = [a for a in sys.argv[1:] if a]
    stdout_mode = "--stdout" in argv

    lang = "en"
    args: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--stdout":
            i += 1
        elif a.startswith("--lang="):
            lang = a.split("=", 1)[1]
            i += 1
        elif a == "--lang":
            if i + 1 >= len(argv):
                print(USAGE, file=sys.stderr)
                sys.exit(1)
            lang = argv[i + 1]
            i += 2
        elif a.startswith("--"):
            print(f"Error: unknown option: {a}\n{USAGE}", file=sys.stderr)
            sys.exit(1)
        else:
            args.append(a)
            i += 1

    if not args:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    if lang not in TEMPLATES:
        print(f"Error: unknown language '{lang}'. Available: {', '.join(sorted(TEMPLATES))}",
              file=sys.stderr)
        sys.exit(1)

    sol_path = Path(args[0])
    if not sol_path.exists():
        print(f"Error: file not found: {sol_path}", file=sys.stderr)
        sys.exit(1)

    text = sol_path.read_text(encoding="utf-8")

    targets = []  # (doc, label)
    try:
        targets.append((json.loads(text), sol_path.name))
    except json.JSONDecodeError:
        docs = extract_sol_docs(text)
        if not docs:
            print(f"Error: {sol_path} is neither valid SOL JSON nor a markdown file "
                  f"with a SOL json fence.", file=sys.stderr)
            sys.exit(1)
        for doc, lbl in docs:
            targets.append((doc, f"{sol_path.name}:{lbl}"))

    renderings = []
    for doc, label in targets:
        renderings.append(Sol2Prose(lang=lang).convert(doc, source_label=label))
    result = "\n\n---\n\n".join(renderings)

    if stdout_mode:
        print(result)
        return

    # `.prose.md`, never `.md`: a bare `.md` would overwrite the markdown document that
    # hosts the SOL fences — the json-in-md pattern used by every fixture in tests/.
    out_path = Path(args[1]) if len(args) >= 2 else sol_path.with_name(sol_path.stem + ".prose.md")
    out_path.write_text(result, encoding="utf-8")
    print(f"Prose rendering written to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
