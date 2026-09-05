#!/usr/bin/env python3
"""
sol2mermaid.py — Convert a SOL 0.6 process file to a Mermaid flowchart diagram.

MIT License
Copyright (c) 2026 Gianni Tommasi

Usage:
    python3 sol2mermaid.py process.json              # writes process.mmd
    python3 sol2mermaid.py process.json output.mmd   # writes to output.mmd
    python3 sol2mermaid.py process.json --stdout     # prints to stdout
"""

import json
import sys
from pathlib import Path


CONSTRAINT_KEYS = ("required", "anyof", "number", "json", "desc")


def fmt_value(value) -> str:
    """A SOL field value as readable text.

    Structured `accepts`/`returns` contracts (SOL 0.6.0), `IMPORT` lists and structured
    `RETURN` values arrive as dicts/lists. Passing them through `str()` prints a Python
    repr — `True` instead of `true`, single quotes — so this renders them the way
    `sol2prose.py` does, keeping the three derived views consistent.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(fmt_value(v) for v in value)
    if isinstance(value, dict):
        return "; ".join(f"{k}{fmt_constraints(v)}" for k, v in value.items())
    return str(value)


def fmt_constraints(spec) -> str:
    """The constraint suffix of one contract field, or the raw value if it is not one."""
    if not isinstance(spec, dict):
        return f": {fmt_value(spec)}"
    if not spec:
        return ""
    if not any(k in spec for k in CONSTRAINT_KEYS):
        return ": " + json.dumps(spec, ensure_ascii=False)
    parts = []
    if spec.get("required"):
        parts.append("required")
    if "anyof" in spec:
        parts.append("one of: " + fmt_value(spec["anyof"]))
    if spec.get("number"):
        parts.append("numeric")
    if spec.get("json"):
        parts.append("json")
    out = ""
    if spec.get("desc"):
        out += f" — {spec['desc']}"
    if parts:
        out += f" ({'; '.join(parts)})"
    return out


def fmt_contract_lines(value) -> list:
    """A contract as one text line per field, so a wide contract is not truncated whole."""
    if isinstance(value, dict) and value:
        return [f"{k}{fmt_constraints(v)}" for k, v in value.items()]
    return [fmt_value(value)]


class Sol2Mermaid:
    def __init__(self):
        self._counter = 0
        self._main: list[str] = []
        self._deferred: list[str] = []   # subgraphs for SUB and AGENT definitions
        self._buf: list[str] = self._main  # active write target
        self._subs: dict[str, str] = {}   # sub name → entry node id
        self._agents: dict[str, str] = {} # agent name → entry node id

    # ------------------------------------------------------------------
    # Node ID and text helpers
    # ------------------------------------------------------------------

    def _id(self, prefix: str = "n") -> str:
        self._counter += 1
        return f"{prefix}{self._counter}"

    def _esc(self, text, max_len: int = 55) -> str:
        s = str(text).replace('"', "'").replace("\n", " ").replace("`", "'").strip()
        return s if len(s) <= max_len else s[: max_len - 1] + "…"

    def _contract_label(self, field: str, value) -> str:
        lines = [self._esc(line, 90) for line in fmt_contract_lines(value)]
        return f"{field}:\\n" + "\\n".join(lines)

    def _emit(self, line: str) -> None:
        self._buf.append(line)

    def _use_deferred(self):
        """Context manager: redirect emits to the deferred buffer."""
        return _BufContext(self, self._deferred)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def convert(self, sol_doc: dict) -> str:
        # Agent root form: a file whose single key is AGENT is unwrapped to its agent.
        if set(sol_doc.keys()) == {"AGENT"}:
            sol_doc = sol_doc["AGENT"]
        name = sol_doc.get("name", "process")
        desc = sol_doc.get("description", "")
        # Pin a light base theme so host dark-mode cannot flip label text to a
        # light color on the light node fills (which renders unreadable).
        self._main = [
            "%%{init: {'theme':'base','themeVariables':{"
            "'darkMode':false,'background':'#ffffff','primaryTextColor':'#1e293b',"
            "'primaryColor':'#f8fafc','primaryBorderColor':'#64748b',"
            "'lineColor':'#64748b','fontSize':'14px'}}}%%",
            "flowchart TD",
        ]
        self._deferred = []
        self._buf = self._main
        self._subs = {}
        self._agents = {}
        self._counter = 0

        if desc:
            self._emit(f"    %% {self._esc(desc, 100)}")
            self._emit("")

        start_id = self._id("START")
        self._emit(f'    {start_id}(["▶ {self._esc(name)}"])')
        self._emit(f"    class {start_id} terminal")

        # Root contracts (SOL 0.6.0): the outer boundary toward whoever invokes the
        # process. Rendered beside START, like an AGENT's own contract beside its entry.
        for field in ("accepts", "returns"):
            if field in sol_doc:
                info_id = self._id("RC")
                self._emit(f'    {info_id}["{self._contract_label(field, sol_doc[field])}"]')
                self._emit(f"    class {info_id} io")
                self._emit(f"    {start_id} --- {info_id}")

        routine = sol_doc.get("ROUTINE", [])
        if routine:
            r_first, r_last = self._routine(routine)
            self._emit(f"    {start_id} --> {r_first}")
            end_id = self._id("END")
            self._emit(f'    {end_id}(["⏹ end"])')
            self._emit(f"    class {end_id} terminal")
            self._emit(f"    {r_last} --> {end_id}")
        else:
            end_id = self._id("END")
            self._emit(f'    {end_id}(["⏹ end"])')
            self._emit(f"    class {end_id} terminal")
            self._emit(f"    {start_id} --> {end_id}")

        # Global ONERROR footnote
        if "ONERROR" in sol_doc:
            gerr_id = self._id("GERR")
            self._emit("")
            self._emit(f'    {gerr_id}["⚠ Global ONERROR"]')
            self._emit(f"    class {gerr_id} onerror")

        # Append deferred subgraphs
        if self._deferred:
            self._main.append("")
            self._main.extend(self._deferred)

        # Styles
        self._main.extend([
            "",
            "    classDef todo     fill:#dbeafe,stroke:#3b82f6,color:#1e3a8a",
            "    classDef run      fill:#dcfce7,stroke:#16a34a,color:#14532d",
            "    classDef ctrl     fill:#fef9c3,stroke:#ca8a04,color:#713f12",
            "    classDef agent    fill:#f3e8ff,stroke:#9333ea,color:#3b0764",
            "    classDef terminal fill:#1e293b,stroke:#475569,color:#f8fafc",
            "    classDef onerror  fill:#fee2e2,stroke:#dc2626,color:#7f1d1d",
            "    classDef io       fill:#ffedd5,stroke:#ea580c,color:#7c2d12",
            "    classDef sub      fill:#f0fdf4,stroke:#16a34a,color:#14532d",
            "    classDef halt     fill:#450a0a,stroke:#dc2626,color:#fecaca",
            "    classDef return   fill:#e2e8f0,stroke:#64748b,color:#1e293b",
            "    classDef import   fill:#f1f5f9,stroke:#94a3b8,color:#334155",
        ])

        return "\n".join(self._main)

    # ------------------------------------------------------------------
    # Routine and instruction dispatch
    # ------------------------------------------------------------------

    def _routine(self, routine: list) -> tuple[str, str]:
        """Process a list of instructions sequentially. Returns (first_id, last_id)."""
        if not routine:
            noop = self._id("noop")
            self._emit(f"    {noop}(\" \")")
            return noop, noop

        segments: list[tuple[str, str]] = []
        for instr in routine:
            segments.append(self._instruction(instr))

        # Wire segments in sequence
        for i in range(len(segments) - 1):
            _, prev_exit = segments[i]
            next_entry, _ = segments[i + 1]
            self._emit(f"    {prev_exit} --> {next_entry}")

        return segments[0][0], segments[-1][1]

    def _instruction(self, instr: dict) -> tuple[str, str]:
        if not isinstance(instr, dict):
            return self._unknown(instr)
        dispatch = {
            "TODO":         self._todo,
            "RUN":          self._run,
            "IF":           self._if,
            "WHEN":         self._when,
            "REPEAT":       self._repeat,
            "SUB":          self._sub_def,
            "CALL":         self._call,
            "AGENT":        self._agent_def,
            "SPAWN":        self._spawn,
            "DELEGATE":     self._delegate,
            "IMPORT":       self._import,
            "RETURN":       self._return,
            "HALT":         self._halt,
            "WAITUSERINPUT": self._wait,
        }
        for key, handler in dispatch.items():
            if key in instr:
                return handler(instr)
        return self._unknown(instr)

    # ------------------------------------------------------------------
    # Leaf instructions
    # ------------------------------------------------------------------

    def _todo(self, instr: dict) -> tuple[str, str]:
        nid = self._id("T")
        model_tag = f' [{instr["model"]}]' if "model" in instr else ""
        label = self._esc(instr["TODO"])
        self._emit(f'    {nid}["{label}{model_tag}"]')
        self._emit(f"    class {nid} todo")
        if "ONERROR" in instr:
            self._inline_onerror(nid)
        return nid, nid

    def _run(self, instr: dict) -> tuple[str, str]:
        nid = self._id("R")
        label = self._esc(instr["RUN"])
        self._emit(f'    {nid}["`RUN: {label}`"]')
        self._emit(f"    class {nid} run")
        if "ONERROR" in instr:
            self._inline_onerror(nid)
        return nid, nid

    def _inline_onerror(self, from_id: str) -> None:
        err_id = self._id("ERR")
        self._emit(f'    {err_id}["⚠ ONERROR"]')
        self._emit(f"    class {err_id} onerror")
        self._emit(f"    {from_id} -. error .-> {err_id}")

    def _return(self, instr: dict) -> tuple[str, str]:
        nid = self._id("RETURN")
        msg = instr.get("RETURN")
        label = f"RETURN: {self._esc(fmt_value(msg), 90)}" if msg else "RETURN"
        self._emit(f'    {nid}(["↩️ {label}"])')
        self._emit(f"    class {nid} return")
        return nid, nid

    def _halt(self, instr: dict) -> tuple[str, str]:
        nid = self._id("HALT")
        msg = instr.get("HALT")
        label = f"HALT: {self._esc(fmt_value(msg), 90)}" if msg else "HALT"
        self._emit(f'    {nid}(["🛑 {label}"])')
        self._emit(f"    class {nid} halt")
        return nid, nid

    def _wait(self, instr: dict) -> tuple[str, str]:
        nid = self._id("WUI")
        prompt = self._esc(instr.get("WAITUSERINPUT", "waiting for input…"))
        self._emit(f'    {nid}[/"⏸ {prompt}"/]')
        self._emit(f"    class {nid} io")
        return nid, nid

    def _import(self, instr: dict) -> tuple[str, str]:
        nid = self._id("IMP")
        path = self._esc(fmt_value(instr["IMPORT"]), 90)
        self._emit(f'    {nid}[("IMPORT: {path}")]')
        self._emit(f"    class {nid} import")
        return nid, nid

    def _unknown(self, instr) -> tuple[str, str]:
        nid = self._id("UNK")
        self._emit(f'    {nid}["{self._esc(fmt_value(instr), 90)}"]')
        return nid, nid

    # ------------------------------------------------------------------
    # Control flow
    # ------------------------------------------------------------------

    def _if(self, instr: dict) -> tuple[str, str]:
        block = instr["IF"]
        cond_id = self._id("C")
        cond_label = self._esc(block.get("when", "condition"))
        self._emit(f'    {cond_id}{{"{cond_label}"}}')
        self._emit(f"    class {cond_id} ctrl")

        merge_id = self._id("M")
        self._emit(f'    {merge_id}(" ")')

        # then
        then_steps = block.get("then", [])
        if then_steps:
            t_first, t_last = self._routine(then_steps)
            self._emit(f"    {cond_id} -->|yes| {t_first}")
            self._emit(f"    {t_last} --> {merge_id}")
        else:
            self._emit(f"    {cond_id} -->|yes| {merge_id}")

        # else
        else_steps = block.get("else", [])
        if else_steps:
            e_first, e_last = self._routine(else_steps)
            self._emit(f"    {cond_id} -->|no| {e_first}")
            self._emit(f"    {e_last} --> {merge_id}")
        else:
            self._emit(f"    {cond_id} -->|no| {merge_id}")

        return cond_id, merge_id

    def _when(self, instr: dict) -> tuple[str, str]:
        branches = instr["WHEN"]
        merge_id = self._id("WM")
        self._emit(f'    {merge_id}(" ")')

        first_id = None
        prev_cond_id = None

        for branch in branches:
            has_when = "when" in branch
            has_else = "else" in branch and not has_when

            if has_else:
                else_steps = branch.get("else", [])
                if else_steps:
                    e_first, e_last = self._routine(else_steps)
                    if prev_cond_id:
                        self._emit(f"    {prev_cond_id} -->|no| {e_first}")
                    self._emit(f"    {e_last} --> {merge_id}")
                elif prev_cond_id:
                    self._emit(f"    {prev_cond_id} -->|no| {merge_id}")
            else:
                cond_id = self._id("WC")
                label = self._esc(branch.get("when", "condition"))
                self._emit(f'    {cond_id}{{"{label}"}}')
                self._emit(f"    class {cond_id} ctrl")

                if first_id is None:
                    first_id = cond_id
                if prev_cond_id is not None:
                    self._emit(f"    {prev_cond_id} -->|no| {cond_id}")

                then_steps = branch.get("then", [])
                if then_steps:
                    t_first, t_last = self._routine(then_steps)
                    self._emit(f"    {cond_id} -->|yes| {t_first}")
                    self._emit(f"    {t_last} --> {merge_id}")
                else:
                    self._emit(f"    {cond_id} -->|yes| {merge_id}")

                prev_cond_id = cond_id

        # If no else branch: last condition's no → merge
        has_explicit_else = any("else" in b and "when" not in b for b in branches)
        if prev_cond_id and not has_explicit_else:
            self._emit(f"    {prev_cond_id} -->|no| {merge_id}")

        return (first_id or merge_id), merge_id

    def _repeat(self, instr: dict) -> tuple[str, str]:
        block = instr["REPEAT"]

        for key in ("while", "until", "for", "foreach"):
            if key in block:
                loop_label = f"{key}: {self._esc(fmt_value(block[key]))}"
                loop_type = key
                break
        else:
            loop_label = "loop"
            loop_type = "while"

        check_id = self._id("LC")
        self._emit(f'    {check_id}{{"{loop_label}"}}')
        self._emit(f"    class {check_id} ctrl")

        exit_id = self._id("LE")
        self._emit(f'    {exit_id}(" ")')

        body = block.get("ROUTINE", [])
        if body:
            b_first, b_last = self._routine(body)
            if loop_type == "until":
                self._emit(f"    {check_id} -->|not yet| {b_first}")
                self._emit(f"    {check_id} -->|done| {exit_id}")
            else:
                self._emit(f"    {check_id} -->|continue| {b_first}")
                self._emit(f"    {check_id} -->|exit| {exit_id}")
            self._emit(f"    {b_last} --> {check_id}")
        else:
            self._emit(f"    {check_id} --> {exit_id}")

        return check_id, exit_id

    # ------------------------------------------------------------------
    # Subroutines and agents
    # ------------------------------------------------------------------

    def _sub_def(self, instr: dict) -> tuple[str, str]:
        """SUB definition: rendered as a deferred subgraph, inline marker in main flow."""
        sub = instr["SUB"]
        name = sub.get("name", "subroutine")
        sg_id = self._id("SG")
        entry_id = self._id("SE")
        self._subs[name] = entry_id

        # Deferred subgraph
        with self._use_deferred():
            self._emit(f'    subgraph {sg_id} ["SUB: {self._esc(name)}"]')
            self._emit(f'        {entry_id}["{self._esc(name)}"]')
            self._emit(f"        class {entry_id} sub")
            sub_routine = sub.get("ROUTINE", [])
            if sub_routine:
                s_first, _ = self._routine(sub_routine)
                self._emit(f"        {entry_id} --> {s_first}")
            self._emit("    end")

        # Inline marker (SUB definitions don't execute inline, just declare)
        marker_id = self._id("SD")
        self._emit(f'    {marker_id}[["define SUB: {self._esc(name)}"]]')
        self._emit(f"    class {marker_id} sub")
        return marker_id, marker_id

    def _call(self, instr: dict) -> tuple[str, str]:
        nid = self._id("CALL")
        name = self._esc(instr["CALL"])
        self._emit(f'    {nid}[["{name}"]]')
        self._emit(f"    class {nid} sub")
        if instr["CALL"] in self._subs:
            self._emit(f"    {nid} -.-> {self._subs[instr['CALL']]}")
        return nid, nid

    def _agent_def(self, instr: dict) -> tuple[str, str]:
        """AGENT definition: rendered as a deferred subgraph."""
        agent = instr["AGENT"]
        name = agent.get("name", "agent")
        sg_id = self._id("AG")
        entry_id = self._id("AE")
        self._agents[name] = entry_id

        with self._use_deferred():
            self._emit(f'    subgraph {sg_id} ["AGENT: {self._esc(name)}"]')
            self._emit(f'        {entry_id}["{self._esc(name)}"]')
            self._emit(f"        class {entry_id} agent")
            for field in ("accepts", "returns"):
                if field in agent:
                    info_id = self._id("AI")
                    self._emit(f'        {info_id}["{self._contract_label(field, agent[field])}"]')
                    self._emit(f"        class {info_id} io")
                    self._emit(f"        {entry_id} --- {info_id}")
            ag_routine = agent.get("ROUTINE", [])
            if ag_routine:
                a_first, _ = self._routine(ag_routine)
                self._emit(f"        {entry_id} --> {a_first}")
            self._emit("    end")

        marker_id = self._id("AD")
        self._emit(f'    {marker_id}[/"define AGENT: {self._esc(name)}"/]')
        self._emit(f"    class {marker_id} agent")
        return marker_id, marker_id

    def _spawn(self, instr: dict) -> tuple[str, str]:
        nid = self._id("SP")
        name = instr["SPAWN"]
        parts = [f"SPAWN: {self._esc(name)}"]
        if "with" in instr:
            parts.append(f"with: {self._esc(fmt_value(instr['with']), 90)}")
        if "returns" in instr:
            parts.append(f"returns: {self._esc(fmt_value(instr['returns']), 90)}")
        label = "\\n".join(parts)
        self._emit(f'    {nid}[/"{label}"/]')
        self._emit(f"    class {nid} agent")
        if name in self._agents:
            self._emit(f"    {nid} -.-> {self._agents[name]}")
        return nid, nid

    def _delegate(self, instr: dict) -> tuple[str, str]:
        nid = self._id("DG")
        block = instr["DELEGATE"]
        task = self._esc(block.get("task", "delegate task"))
        model_tag = f' [{block["model"]}]' if "model" in block else ""
        self._emit(f'    {nid}[/"DELEGATE: {task}{model_tag}"/]')
        self._emit(f"    class {nid} agent")
        return nid, nid


class _BufContext:
    """Temporarily redirects Sol2Mermaid._buf to a target list."""

    def __init__(self, converter: Sol2Mermaid, target: list):
        self._conv = converter
        self._target = target
        self._saved = None

    def __enter__(self):
        self._saved = self._conv._buf
        self._conv._buf = self._target
        return self

    def __exit__(self, *_):
        self._conv._buf = self._saved


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    args = [a for a in sys.argv[1:] if a]
    stdout_mode = "--stdout" in args
    args = [a for a in args if a != "--stdout"]

    if not args:
        print(
            "Usage: sol2mermaid.py <process.json> [output.mmd] [--stdout]",
            file=sys.stderr,
        )
        sys.exit(1)

    sol_path = Path(args[0])
    if not sol_path.exists():
        print(f"Error: file not found: {sol_path}", file=sys.stderr)
        sys.exit(1)

    with open(sol_path, encoding="utf-8") as f:
        doc = json.load(f)

    result = Sol2Mermaid().convert(doc)

    if stdout_mode:
        print(result)
        return

    out_path = Path(args[1]) if len(args) >= 2 else sol_path.with_suffix(".mmd")
    out_path.write_text(result, encoding="utf-8")
    print(f"Mermaid diagram written to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
