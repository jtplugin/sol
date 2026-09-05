#!/usr/bin/env python3
"""
sol-lint.py — Mechanical linter for SOL 0.6 scripts.

MIT License
Copyright (c) 2026 Gianni Tommasi

This is the deterministic half of Pass 7: it catches the *formal* defects that do
not require judgment, and surfaces the *heuristic* smells that do. It does NOT
replace the authoring discipline — it backs it up.

  ERROR  — deterministic defects. The script is malformed or provably wrong:
           single-brace placeholders, unknown/malformed constructs, CALL/SPAWN
           that resolve to nothing, missing ROUTINE, RETURN object keys that do
           not match a structured returns contract, etc. Fix before shipping.
  WARN   — heuristic smells that need a human/agent decision: control-flow words
           buried in a TODO, over-long TODOs, value-only duplicated SUBs, a
           contracted SPAWN with no ONERROR, an AGENT.accepts with no visible
           validation guard, RETURN as a string under structured returns (often
           intentional off-contract). Each is a prompt to re-read, not an automatic verdict.

Usage:
    python3 sol-lint.py script.json                 # human report, exit 1 on ERROR
    python3 sol-lint.py script.md                   # extracts ```json fences and lints each
    python3 sol-lint.py script.json --json          # machine-readable findings on stdout
    python3 sol-lint.py script.json --strict         # warnings also cause exit 1
"""

import json
import re
import sys
from pathlib import Path

# ----------------------------------------------------------------------------
# Recognized SOL construct keys and the modifier keys allowed alongside them.
# ----------------------------------------------------------------------------

CONSTRUCTS = {
    "TODO", "RUN", "IF", "WHEN", "REPEAT", "SUB", "AGENT", "CALL",
    "SPAWN", "DELEGATE", "IMPORT", "RETURN", "HALT", "WAITUSERINPUT",
}
MODIFIERS = {"model", "role", "ONERROR", "with", "returns"}

# Every string field whose value may carry a {{placeholder}}.
TEXT_FIELDS = {"TODO", "RUN", "when", "with", "returns", "RETURN", "HALT", "task",
               "foreach", "while", "until", "for", "accepts", "desc"}

# Control-flow words that must not live inside a TODO/RUN leaf (the smell test).
SMELL_PATTERNS = [
    ("decision", re.compile(r"\b(if|unless|in case|se|qualora)\b", re.I)),
    ("decision", re.compile(r"\bwhen\b", re.I)),
    ("case", re.compile(r"\b(depending on|a seconda d|based on the (kind|type|mode|state))\b", re.I)),
    ("foreach", re.compile(r"\b(for each|for every|per ogni|per ciascun|per ognun)\b", re.I)),
    ("loop", re.compile(r"\b(while|until|finch[eé]|\d+ times|ripeti)\b", re.I)),
    ("error", re.compile(r"\b(on failure|if it fails|se va in errore|in caso di errore|otherwise log)\b", re.I)),
    ("human", re.compile(r"\b(ask the user|wait for approval|once they confirm|chiedi all.?utente|attendi conferma)\b", re.I)),
    ("sequence", re.compile(r"\bthen\b.*\bthen\b", re.I | re.S)),
]

# What follows a buried "if" decides how bad it is. A consequent that transfers
# control (skip, stop, return...) hides a real branch: the steps after it do not
# run on that path, and a flowchart drawn from the script shows a straight line
# where the process actually forks. A consequent that merely assigns a value is
# a default -- the flow proceeds identically, and in most languages it is a single
# instruction. Decisione di Gianni (2026-08-20): il ramo va sempre esplicitato; il
# default si tollera, salvo quando e' l'unica istruzione del suo flusso, perche'
# allora il diagramma si riduce a una scatola che non rappresenta nulla.
CONTROL_CONSEQUENT_RE = re.compile(
    r"\b(skip|ignore|discard|drop|exclude|omit|stop|halt|abort|return|retry|"
    r"continue|salta|ignora|scarta|escludi|ometti|interrompi|esci|riprova)\b", re.I)
ASSIGN_CONSEQUENT_RE = re.compile(
    r"\b(set|assign|use|default to|treat (it )?as|mark (it )?as|imposta|assegna|"
    r"usa|considera|vale)\b", re.I)

# A RETURN whose whole value is one named placeholder is an indirection to a value
# built earlier in the script -- not an off-contract literal. Building the object to
# the contract and then returning a reference to it is good practice: it keeps the
# shape in one named step instead of inlining it at the exit. Prose-y placeholders
# ({{the array built earlier}}) deliberately do NOT match -- they stay a finding,
# and 'vague-placeholder' reports them separately.
RETURN_REF_RE = re.compile(r"^\s*\{\{\s*([A-Za-z_][\w.\-\[\]']*)\s*\}\}\s*$")

# Identifier-like content inside single braces ⇒ almost certainly a placeholder defect.
IDENT_RE = r"[A-Za-z_][\w]*(?:[.\[\]'\w-]*)"
SINGLE_BRACE_RE = re.compile(r"(?<![\$\{])\{(" + IDENT_RE + r")\}(?!\})")

TODO_LONG_CHARS = 240


class Finding:
    __slots__ = ("severity", "path", "code", "message")

    def __init__(self, severity: str, path: str, code: str, message: str):
        self.severity = severity
        self.path = path
        self.code = code
        self.message = message

    def as_dict(self) -> dict:
        return {"severity": self.severity, "path": self.path,
                "code": self.code, "message": self.message}


class SolLinter:
    def __init__(self, doc_text: str = ""):
        self.findings: list[Finding] = []
        self.doc_text = doc_text or ""
        self.defined_subs: set[str] = set()
        self.defined_agents: set[str] = set()
        self.has_imports = False
        # Deferred resolution checks: (kind, name, path)
        self._calls: list[tuple[str, str, str]] = []
        self._spawns: list[tuple[str, str, str]] = []
        # SUB signatures for the duplication smell: name -> shape signature
        self._sub_sigs: dict[str, tuple] = {}
        # Structured returns contracts in scope for RETURN shape checks (inner overrides outer).
        self._returns_stack: list[dict] = []
        # Text used by the RETURN-reference checks (set in lint()).
        # _doc_json is the whole document: a name may legitimately be bound by
        # 'accepts' as well as by a step. _body_json is the ROUTINE alone --
        # contract keys must be searched there, because the 'returns' block
        # itself names every key and would make the check always pass.
        self._doc_json = ""
        self._body_json = ""
        # Size of the ROUTINE currently being walked, for the buried-flow refinement.
        self._routine_sizes: list[int] = []

    # -- finding helpers ----------------------------------------------------

    def err(self, path, code, msg):
        self.findings.append(Finding("ERROR", path, code, msg))

    def warn(self, path, code, msg):
        self.findings.append(Finding("WARN", path, code, msg))

    # -- public entry -------------------------------------------------------

    def lint(self, doc) -> list[Finding]:
        if not isinstance(doc, dict):
            self.err("$", "root-type", "Root must be a JSON object.")
            return self.findings
        self._doc_json = json.dumps(doc, ensure_ascii=False)
        corpo = doc.get("AGENT", doc).get("ROUTINE") if isinstance(doc.get("AGENT", doc), dict) else None
        self._body_json = json.dumps(corpo, ensure_ascii=False) if corpo is not None else ""

        # Unwrap the agent root form: { "AGENT": {...} }
        if set(doc.keys()) == {"AGENT"}:
            agent = doc["AGENT"]
            if not isinstance(agent, dict):
                self.err("$.AGENT", "agent-type", "AGENT root value must be an object.")
                return self.findings
            self.defined_agents.add(agent.get("name", ""))
            self._collect_defs(agent.get("ROUTINE", []), "$.AGENT.ROUTINE")
            self._check_agent_block(agent, "$.AGENT", is_root=True)
        else:
            # Process form.
            for field in ("name", "version", "description"):
                if not doc.get(field):
                    self.warn("$", "root-meta", f"Process root is missing '{field}' (required by the spec).")
            if "ROUTINE" not in doc or not isinstance(doc["ROUTINE"], list):
                self.err("$", "root-routine", "Process root must have a ROUTINE array.")
                return self.findings
            self._scan_text(doc.get("accepts"), "$.accepts", "accepts")
            self._collect_defs(doc["ROUTINE"], "$.ROUTINE")
            root_returns = doc.get("returns")
            if self._is_structured_returns(root_returns):
                self._returns_stack.append(root_returns)
            try:
                self._walk_routine(doc["ROUTINE"], "$.ROUTINE")
            finally:
                if self._is_structured_returns(root_returns):
                    self._returns_stack.pop()

        self._resolve_references()
        self._detect_duplicate_subs()
        return self.findings

    # -- definition collection (two-pass: defs first, then references) ------

    def _collect_defs(self, routine, path):
        if not isinstance(routine, list):
            return
        for i, instr in enumerate(routine):
            if not isinstance(instr, dict):
                continue
            p = f"{path}[{i}]"
            if "SUB" in instr and isinstance(instr["SUB"], dict):
                name = instr["SUB"].get("name")
                if name:
                    self.defined_subs.add(name)
                self._collect_defs(instr["SUB"].get("ROUTINE", []), f"{p}.SUB.ROUTINE")
            elif "AGENT" in instr and isinstance(instr["AGENT"], dict):
                name = instr["AGENT"].get("name")
                if name:
                    self.defined_agents.add(name)
                self._collect_defs(instr["AGENT"].get("ROUTINE", []), f"{p}.AGENT.ROUTINE")
            elif "IMPORT" in instr:
                self.has_imports = True
            # Recurse into nested control flow to find defs nested in branches.
            for key in ("then", "else"):
                if "IF" in instr and isinstance(instr["IF"], dict):
                    self._collect_defs(instr["IF"].get(key, []), f"{p}.IF.{key}")
            if "WHEN" in instr and isinstance(instr["WHEN"], list):
                for j, br in enumerate(instr["WHEN"]):
                    if isinstance(br, dict):
                        self._collect_defs(br.get("then", []), f"{p}.WHEN[{j}].then")
                        self._collect_defs(br.get("else", []), f"{p}.WHEN[{j}].else")
            if "REPEAT" in instr and isinstance(instr["REPEAT"], dict):
                self._collect_defs(instr["REPEAT"].get("ROUTINE", []), f"{p}.REPEAT.ROUTINE")

    # -- routine walk -------------------------------------------------------

    def _walk_routine(self, routine, path):
        if not isinstance(routine, list):
            self.err(path, "routine-type", "ROUTINE must be an array of instructions.")
            return
        self._routine_sizes.append(len(routine))
        try:
            for i, instr in enumerate(routine):
                self._walk_instruction(instr, f"{path}[{i}]")
        finally:
            self._routine_sizes.pop()

    def _walk_instruction(self, instr, path):
        if not isinstance(instr, dict):
            self.err(path, "instr-type", "Instruction must be an object.")
            return

        construct_keys = [k for k in instr if k in CONSTRUCTS]
        if len(construct_keys) == 0:
            unknown = [k for k in instr if k not in MODIFIERS]
            self.err(path, "no-construct",
                     f"Instruction has no recognized construct key (found: {sorted(instr.keys())}).")
            return
        if len(construct_keys) > 1:
            self.err(path, "multi-construct",
                     f"Instruction mixes several construct keys: {construct_keys}. Split into siblings.")
            return

        key = construct_keys[0]
        # Unknown sibling keys (typos like 'wth', 'returnss').
        for k in instr:
            if k not in CONSTRUCTS and k not in MODIFIERS:
                self.warn(path, "unknown-field", f"Unexpected field '{k}' on a {key} instruction.")

        # Placeholder + smell scan on every text field of this instruction.
        for field, val in instr.items():
            if field in TEXT_FIELDS and isinstance(val, str):
                self._scan_text(val, f"{path}.{field}", field)

        handler = getattr(self, f"_c_{key.lower()}", None)
        if handler:
            handler(instr[key], path, instr)

        # ONERROR is itself a routine.
        if "ONERROR" in instr:
            self._walk_routine(instr["ONERROR"], f"{path}.ONERROR")

    # -- per-construct structural checks -----------------------------------

    def _c_todo(self, val, path, instr):
        if not isinstance(val, str) or not val.strip():
            self.err(path, "todo-empty", "TODO must be a non-empty string.")
            return
        if len(val) > TODO_LONG_CHARS or ("\n" in val and re.search(r"(^|\n)\s*([-*]|\d+\.)\s", val)):
            self.warn(path, "todo-long",
                      f"TODO is long/multi-part ({len(val)} chars). Likely buries flow or data — "
                      f"re-check it is a single judgment leaf.")

    def _c_run(self, val, path, instr):
        if not isinstance(val, str) or not val.strip():
            self.err(path, "run-empty", "RUN must be a non-empty command string.")

    def _c_if(self, val, path, instr):
        if not isinstance(val, dict):
            self.err(path, "if-type", "IF value must be an object with 'when' and 'then'.")
            return
        if not val.get("when"):
            self.err(path, "if-when", "IF must have a non-empty 'when'.")
        if not isinstance(val.get("then"), list):
            self.err(path, "if-then", "IF must have a 'then' array.")
        else:
            self._walk_routine(val["then"], f"{path}.IF.then")
        if "else" in val:
            if not isinstance(val["else"], list):
                self.err(path, "if-else", "IF 'else' must be an array.")
            else:
                self._walk_routine(val["else"], f"{path}.IF.else")

    def _c_when(self, val, path, instr):
        if not isinstance(val, list) or not val:
            self.err(path, "when-type", "WHEN value must be a non-empty array of branches.")
            return
        seen_else = False
        for j, br in enumerate(val):
            bp = f"{path}.WHEN[{j}]"
            if not isinstance(br, dict):
                self.err(bp, "when-branch", "WHEN branch must be an object.")
                continue
            has_when, has_else = "when" in br, "else" in br
            if has_else and not has_when:
                seen_else = True
                if not isinstance(br.get("else"), list):
                    self.err(bp, "when-else", "WHEN 'else' must be an array.")
                else:
                    self._walk_routine(br["else"], f"{bp}.else")
            elif has_when:
                if not br.get("when"):
                    self.err(bp, "when-cond", "WHEN branch 'when' must be non-empty.")
                else:
                    self._scan_text(br["when"], f"{bp}.when", "when")
                if not isinstance(br.get("then"), list):
                    self.err(bp, "when-then", "WHEN branch must have a 'then' array.")
                else:
                    self._walk_routine(br["then"], f"{bp}.then")
            else:
                self.err(bp, "when-shape", "WHEN branch must have 'when'+'then' or 'else'.")
        if seen_else and not any("when" in b for b in val if isinstance(b, dict)):
            self.warn(path, "when-only-else", "WHEN has only an else branch — likely should be plain steps.")

    def _c_repeat(self, val, path, instr):
        if not isinstance(val, dict):
            self.err(path, "repeat-type", "REPEAT value must be an object.")
            return
        loop_keys = [k for k in ("while", "until", "for", "foreach") if k in val]
        if len(loop_keys) == 0:
            self.err(path, "repeat-key", "REPEAT must have one of: while, until, for, foreach.")
        elif len(loop_keys) > 1:
            self.err(path, "repeat-multi", f"REPEAT has multiple loop keys: {loop_keys}.")
        else:
            lk = loop_keys[0]
            self._scan_text(str(val[lk]), f"{path}.REPEAT.{lk}", lk)
            if lk == "foreach":
                self._check_foreach_collection(str(val[lk]), f"{path}.REPEAT.foreach")
        if not isinstance(val.get("ROUTINE"), list):
            self.err(path, "repeat-routine", "REPEAT must have a ROUTINE array.")
        else:
            self._walk_routine(val["ROUTINE"], f"{path}.REPEAT.ROUTINE")

    def _c_sub(self, val, path, instr):
        if not isinstance(val, dict):
            self.err(path, "sub-type", "SUB value must be an object.")
            return
        if not val.get("name"):
            self.err(path, "sub-name", "SUB must have a 'name'.")
        if not isinstance(val.get("ROUTINE"), list):
            self.err(path, "sub-routine", "SUB must have a ROUTINE array.")
        else:
            if val.get("name"):
                self._sub_sigs[val["name"]] = self._shape(val["ROUTINE"])
            self._walk_routine(val["ROUTINE"], f"{path}.SUB.ROUTINE")
        if "accepts" in val or "returns" in val:
            self.warn(path, "sub-contract",
                      "SUB has a contract (accepts/returns). SUBs share the caller's context "
                      "and must not declare contracts — use an AGENT if a boundary is needed.")

    def _c_agent(self, val, path, instr):
        self._check_agent_block(val, path)

    def _c_call(self, val, path, instr):
        if not isinstance(val, str) or not val.strip():
            self.err(path, "call-type", "CALL must be the string name of a SUB.")
            return
        self._calls.append(("CALL", val.strip(), path))

    def _c_spawn(self, val, path, instr):
        if not isinstance(val, str) or not val.strip():
            self.err(path, "spawn-type", "SPAWN must be the string name of an AGENT.")
            return
        self._spawns.append(("SPAWN", val.strip(), path))
        if "ONERROR" not in instr:
            self.warn(path, "spawn-noonerror",
                      "SPAWN has no ONERROR. A contracted call must handle a missing/malformed/"
                      "off-contract response on the caller side.")

    def _c_delegate(self, val, path, instr):
        if not isinstance(val, dict):
            self.err(path, "delegate-type", "DELEGATE value must be an object.")
            return
        if not val.get("task"):
            self.err(path, "delegate-task", "DELEGATE must have a 'task'.")
        for field in ("task", "with", "returns"):
            if isinstance(val.get(field), str):
                self._scan_text(val[field], f"{path}.DELEGATE.{field}", field)
        if "ONERROR" not in instr and "ONERROR" not in val:
            self.warn(path, "delegate-noonerror",
                      "DELEGATE has no ONERROR. Handle a failed/empty sub-agent response.")

    def _c_import(self, val, path, instr):
        if not (isinstance(val, str) or isinstance(val, list)):
            self.err(path, "import-type", "IMPORT must be a string path or array of paths.")

    def _c_return(self, val, path, instr):
        self._check_return_value(val, path)

    def _c_halt(self, val, path, instr):
        pass  # null or string, both valid

    def _c_waituserinput(self, val, path, instr):
        if not isinstance(val, str) or not val.strip():
            self.err(path, "wait-type", "WAITUSERINPUT must be a non-empty prompt string.")

    # -- agent block (shared by inline AGENT and agent root form) -----------

    def _check_agent_block(self, val, path, is_root=False):
        if not isinstance(val, dict):
            self.err(path, "agent-type", "AGENT value must be an object.")
            return
        if not val.get("name"):
            self.err(path, "agent-name", "AGENT must have a 'name'.")
        if not isinstance(val.get("ROUTINE"), list):
            self.err(path, "agent-routine", "AGENT must have a ROUTINE array.")
            routine = []
        else:
            routine = val["ROUTINE"]

        for field in ("accepts", "returns"):
            self._scan_text(val.get(field), f"{path}.{field}", field)

        # accepts ⇒ a validation guard should open the ROUTINE.
        if val.get("accepts") and routine:
            if not self._looks_like_guard(routine[0]):
                self.warn(f"{path}.ROUTINE[0]", "accepts-guard",
                          "AGENT declares 'accepts' but its ROUTINE does not open with a visible "
                          "validation guard (IF/WHEN/RETURN/HALT or a 'verify/validate/required' TODO).")
        agent_returns = val.get("returns")
        pushed = self._is_structured_returns(agent_returns)
        if pushed:
            self._returns_stack.append(agent_returns)
        try:
            self._walk_routine(routine, f"{path}.ROUTINE")
        finally:
            if pushed:
                self._returns_stack.pop()

    # -- RETURN vs structured returns ---------------------------------------

    def _is_structured_returns(self, r) -> bool:
        return isinstance(r, dict) and len(r) > 0

    def _active_structured_returns(self):
        return self._returns_stack[-1] if self._returns_stack else None

    def _check_return_value(self, val, path):
        contract = self._active_structured_returns()
        if contract is None:
            return
        expected = set(contract.keys())
        if val is None:
            return
        if isinstance(val, str):
            m = RETURN_REF_RE.match(val)
            if m:
                self._check_return_reference(m.group(1), expected, path)
                return
            if val.strip():
                self.warn(path, "return-shape-mismatch",
                          f"RETURN is a string but structured returns expects object keys "
                          f"{sorted(expected)}. Strings are valid for intentional off-contract "
                          f"reports (e.g. accepts violation) — verify this is intended.")
            return
        if isinstance(val, dict):
            got = set(val.keys())
            if got == expected:
                return
            self.err(path, "return-shape-mismatch",
                     f"RETURN object keys {sorted(got)} do not match structured returns keys "
                     f"{sorted(expected)}.")
            return
        self.err(path, "return-malformed",
                 f"RETURN must be null, a string, or an object with keys {sorted(expected)}; "
                 f"got {type(val).__name__}.")

    def _mentioned(self, word: str, testo: str) -> int:
        """How many times `word` occurs as a whole word in `testo`."""
        return len(re.findall(r"\b" + re.escape(word) + r"\b", testo))

    def _check_return_reference(self, name, expected, path):
        """RETURN {{name}} is an indirection -- so verify the thing it points at.

        Exempting the reference from 'return-shape-mismatch' would otherwise trade
        a false positive for a blind spot: nobody would check that the object the
        script builds actually satisfies the contract. Two textual checks, both on
        the whole document:

          - the name must be bound somewhere else (the RETURN itself accounts for
            one occurrence, so a lone hit means nothing ever builds it);
          - every contract key must appear somewhere in the script, otherwise the
            step that assembles the payload cannot be producing them.

        Both are heuristics over text, hence WARN: a script can name things in ways
        a word search misses. They catch the case that matters -- the contract grows
        a key and the assembling step is never updated.
        """
        if not self._doc_json or not self._body_json:
            return
        radice = name.split(".")[0].split("[")[0]
        if self._mentioned(radice, self._doc_json) < 2:
            self.warn(path, "return-ref-unbound",
                      f"RETURN points at {{{{{name}}}}} but nothing else in the script "
                      f"mentions '{radice}' -- no step appears to build it.")
        assenti = sorted(k for k in expected if not self._mentioned(k, self._body_json))
        if assenti:
            self.warn(path, "return-contract-keys-unmentioned",
                      f"RETURN points at {{{{{name}}}}}, but structured returns keys "
                      f"{assenti} never appear in the script: the step that assembles "
                      f"the payload cannot be producing them.")

    def _looks_like_guard(self, instr) -> bool:
        if not isinstance(instr, dict):
            return False
        if any(k in instr for k in ("IF", "WHEN", "RETURN", "HALT")):
            return True
        text = instr.get("TODO", "")
        return bool(isinstance(text, str) and re.search(
            r"\b(valid|validate|verif|check|required|conform|accepts|missing|guard)", text, re.I))

    # -- text-level checks: placeholders + smells ---------------------------

    def _scan_text(self, val, path, field):
        if not isinstance(val, str):
            return
        for m in SINGLE_BRACE_RE.finditer(val):
            self.err(path, "single-brace",
                     f"Single-brace placeholder {{{m.group(1)}}} - use double braces {{{{{m.group(1)}}}}}.")
        # Smell test only on the leaf text fields where prose flow is a defect.
        if field in ("TODO", "RUN"):
            hits = sorted({label for label, rx in SMELL_PATTERNS if rx.search(val)})
            if hits == ["decision"]:
                self._check_buried_decision(val, path, field)
            elif hits:
                self.warn(path, "buried-flow",
                          f"{field} text contains control-flow words ({', '.join(hits)}). "
                          f"If this is the program (not a declarative criterion), lift it into a construct.")
        # Unnamed placeholder reference (heuristic): {{the array built earlier}}.
        for m in re.finditer(r"\{\{(.*?)\}\}", val):
            inner = m.group(1).strip()
            if re.match(r"^(the|a|an|il|lo|la|gli|le|i)\b.*\s", inner, re.I):
                self.warn(path, "vague-placeholder",
                          f"Placeholder {{{{{inner}}}}} reads as prose, not a named reference. "
                          f"Point it at a named step, loop item, or contract field.")

    def _check_buried_decision(self, val, path, field):
        """A prose 'if' is graded by what its consequent does (see the constants).

        Control transfer -> 'buried-branch': the steps after it do not run on that
        path, so a flowchart drawn from the script shows a straight line where the
        process forks. This one always needs lifting into a construct.

        Assignment -> a defaulted value: the flow proceeds the same either way, and
        the decision is an internal detail of the step. Reported only when it is the
        sole instruction of its ROUTINE, because then the diagram is a single box
        that represents nothing.

        Neither pattern recognised -> the original 'buried-flow', unchanged: when the
        consequent cannot be read, the conservative call is to still say something.
        """
        if CONTROL_CONSEQUENT_RE.search(val):
            self.warn(path, "buried-branch",
                      f"{field} text hides a branch: a prose condition whose consequent "
                      f"transfers control, so the steps that follow do not run on that "
                      f"path. Lift it into an IF/WHEN -- a flowchart built from this "
                      f"script cannot show the fork.")
            return
        if ASSIGN_CONSEQUENT_RE.search(val):
            sola = bool(self._routine_sizes) and self._routine_sizes[-1] == 1
            if sola:
                self.warn(path, "buried-flow",
                          f"{field} text buries a condition, and it is the only "
                          f"instruction of its ROUTINE: the diagram would be a single "
                          f"box hiding the whole decision. Lift it into a construct.")
            return
        self.warn(path, "buried-flow",
                  f"{field} text contains control-flow words (decision). "
                  f"If this is the program (not a declarative criterion), lift it into a construct.")

    def _check_foreach_collection(self, val, path):
        # Heuristic: if the foreach cites a PascalCase/labelled collection and we have the
        # host document text, the label should appear somewhere in it.
        if not self.doc_text:
            return
        labels = re.findall(r"\b([A-Z][a-zA-Z]{2,}[A-Z][a-zA-Z]+)\b", val)  # PascalCase tokens
        for label in labels:
            if self.doc_text.count(label) < 2:  # only the foreach mention itself
                self.warn(path, "foreach-collection",
                          f"foreach cites '{label}' but no matching labelled section/table is "
                          f"visible in the host document. Verify the collection resolves in scope.")

    # -- deferred reference resolution --------------------------------------

    def _resolve_references(self):
        for kind, name, path in self._calls:
            if name in self.defined_subs:
                continue
            if self.has_imports:
                self.warn(path, "call-unresolved-import",
                          f"CALL '{name}' is not a SUB defined in this file; assuming it comes from an "
                          f"IMPORT — verify the imported file actually defines it.")
            else:
                self.err(path, "call-unresolved",
                         f"CALL '{name}' resolves to no SUB defined in this file, and there is no IMPORT.")
        for kind, name, path in self._spawns:
            if name in self.defined_agents:
                continue
            if self.has_imports:
                self.warn(path, "spawn-unresolved-import",
                          f"SPAWN '{name}' is not an AGENT defined in this file; assuming it comes from an "
                          f"IMPORT — verify the imported file actually defines it.")
            else:
                self.err(path, "spawn-unresolved",
                         f"SPAWN '{name}' resolves to no AGENT defined in this file, and there is no IMPORT.")

    # -- value-only duplication smell ---------------------------------------

    def _shape(self, node):
        """Structural signature ignoring all string values — captures shape, not data."""
        if isinstance(node, list):
            return tuple(self._shape(x) for x in node)
        if isinstance(node, dict):
            ck = [k for k in node if k in CONSTRUCTS]
            if not ck:
                return ("?",)
            key = ck[0]
            if key == "IF":
                b = node["IF"] if isinstance(node["IF"], dict) else {}
                return ("IF", self._shape(b.get("then", [])), self._shape(b.get("else", [])))
            if key == "WHEN":
                return ("WHEN", tuple(self._shape(br.get("then", br.get("else", [])))
                                     for br in node["WHEN"] if isinstance(br, dict)))
            if key == "REPEAT":
                b = node["REPEAT"] if isinstance(node["REPEAT"], dict) else {}
                return ("REPEAT", self._shape(b.get("ROUTINE", [])))
            return (key,)
        return ("lit",)

    def _detect_duplicate_subs(self):
        by_sig: dict[tuple, list[str]] = {}
        for name, sig in self._sub_sigs.items():
            # Only consider non-trivial shapes (more than a single leaf).
            if sig and len(sig) >= 1 and sig != (("TODO",),) and sig != (("RUN",),):
                by_sig.setdefault(sig, []).append(name)
        for sig, names in by_sig.items():
            if len(names) >= 2:
                self.warn("$", "duplicate-subs",
                          f"SUBs {', '.join(sorted(names))} share an identical structure. "
                          f"If they differ only by values, collapse them into a labelled "
                          f"collection + one REPEAT foreach.")


# ----------------------------------------------------------------------------
# Input handling (json file or json fences in markdown) + CLI
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


def format_report(label: str, findings: list[Finding]) -> str:
    lines = [f"SOL lint: {label}", ""]
    if not findings:
        lines.append("  clean — no findings")
    else:
        order = {"ERROR": 0, "WARN": 1}
        for f in sorted(findings, key=lambda x: (order.get(x.severity, 9), x.path)):
            tag = "ERROR" if f.severity == "ERROR" else "WARN "
            lines.append(f"  {tag}  {f.path}")
            lines.append(f"         {f.message}  [{f.code}]")
    errs = sum(1 for f in findings if f.severity == "ERROR")
    warns = sum(1 for f in findings if f.severity == "WARN")
    lines += ["", f"  {errs} error(s), {warns} warning(s)"]
    return "\n".join(lines)


def main():
    # Make the report safe on consoles that default to a non-UTF-8 codepage (e.g. Windows).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    args = [a for a in sys.argv[1:] if a]
    json_out = "--json" in args
    strict = "--strict" in args
    args = [a for a in args if not a.startswith("--")]

    if not args:
        print("Usage: sol-lint.py <script.json|script.md> [--json] [--strict]", file=sys.stderr)
        sys.exit(2)

    path = Path(args[0])
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(2)

    text = path.read_text(encoding="utf-8")

    targets = []  # (doc, label, doc_text)
    try:
        doc = json.loads(text)
        targets.append((doc, path.name, ""))
    except json.JSONDecodeError:
        docs = extract_sol_docs(text)
        if not docs:
            print(f"Error: {path} is neither valid SOL JSON nor a markdown file with a SOL json fence.",
                  file=sys.stderr)
            sys.exit(2)
        for doc, lbl in docs:
            targets.append((doc, f"{path.name}:{lbl}", text))

    all_findings = []
    reports = []
    for doc, label, doc_text in targets:
        findings = SolLinter(doc_text=doc_text).lint(doc)
        all_findings.extend(findings)
        reports.append((label, findings))

    if json_out:
        payload = {"results": [{"label": lbl, "findings": [f.as_dict() for f in fs]}
                               for lbl, fs in reports]}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("\n\n".join(format_report(lbl, fs) for lbl, fs in reports))

    n_err = sum(1 for f in all_findings if f.severity == "ERROR")
    n_warn = sum(1 for f in all_findings if f.severity == "WARN")
    if n_err or (strict and n_warn):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
