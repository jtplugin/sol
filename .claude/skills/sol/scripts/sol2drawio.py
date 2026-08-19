#!/usr/bin/env python3
"""
sol2drawio.py — Convert a SOL 0.5.0 process file to a draw.io XML diagram.

MIT License
Copyright (c) 2026 Gianni Tommasi

Usage:
    python3 sol2drawio.py process.json              # writes process.drawio
    python3 sol2drawio.py process.json output.drawio # writes to output.drawio
    python3 sol2drawio.py process.json --stdout      # prints to stdout

The output is a .drawio (XML) file that can be opened directly in draw.io
(app.diagrams.net) or the draw.io desktop app. Use Ctrl+Shift+H (Arrange →
Layout → Vertical Tree) after opening to get a clean automatic layout.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


class Sol2DrawIO:
    # ------------------------------------------------------------------ layout
    _CX   = 400   # center X of main flow
    _NW   = 220   # node width
    _NH   = 60    # node height
    _DW   = 180   # diamond width
    _DH   = 80    # diamond height
    _VGAP = 40    # vertical gap between nodes
    _HOFF = 280   # horizontal offset for branch columns

    # ------------------------------------------------------------------ styles
    _S = {
        "todo":     "rounded=0;whiteSpace=wrap;html=1;"
                    "fillColor=#dbeafe;strokeColor=#3b82f6;fontColor=#1e3a8a;",
        "run":      "rounded=0;whiteSpace=wrap;html=1;"
                    "fillColor=#dcfce7;strokeColor=#16a34a;fontColor=#14532d;fontStyle=1;",
        "ctrl":     "rhombus;whiteSpace=wrap;html=1;"
                    "fillColor=#fef9c3;strokeColor=#ca8a04;fontColor=#713f12;",
        "agent":    "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;"
                    "fillColor=#f3e8ff;strokeColor=#9333ea;fontColor=#3b0764;",
        "terminal": "rounded=1;whiteSpace=wrap;html=1;"
                    "fillColor=#1e293b;strokeColor=#475569;fontColor=#f8fafc;",
        "onerror":  "rounded=0;whiteSpace=wrap;html=1;"
                    "fillColor=#fee2e2;strokeColor=#dc2626;fontColor=#7f1d1d;",
        "io":       "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;"
                    "fillColor=#ffedd5;strokeColor=#ea580c;fontColor=#7c2d12;",
        "sub":      "rounded=0;whiteSpace=wrap;html=1;"
                    "fillColor=#f0fdf4;strokeColor=#16a34a;fontColor=#14532d;",
        "subdef":   "shape=process;whiteSpace=wrap;html=1;"
                    "fillColor=#f0fdf4;strokeColor=#16a34a;fontColor=#14532d;",
        "halt":     "rounded=1;whiteSpace=wrap;html=1;"
                    "fillColor=#450a0a;strokeColor=#dc2626;fontColor=#fecaca;",
        "return":   "rounded=1;whiteSpace=wrap;html=1;"
                    "fillColor=#e2e8f0;strokeColor=#64748b;fontColor=#1e293b;",
        "import":   "shape=cylinder3;whiteSpace=wrap;html=1;"
                    "fillColor=#f1f5f9;strokeColor=#94a3b8;fontColor=#334155;",
        "agentdef": "rounded=1;whiteSpace=wrap;html=1;"
                    "fillColor=#f3e8ff;strokeColor=#9333ea;fontColor=#3b0764;",
        "merge":    "ellipse;whiteSpace=wrap;html=1;"
                    "fillColor=#e2e8f0;strokeColor=#94a3b8;opacity=50;",
    }

    def __init__(self):
        self._counter = 0
        self._cells: list = []
        self._y = 0
        self._subs: dict[str, str] = {}
        self._agents: dict[str, str] = {}

    # ------------------------------------------------------------------ helpers

    def _id(self, prefix: str = "n") -> str:
        self._counter += 1
        return f"{prefix}{self._counter}"

    def _esc(self, text, max_len: int = 55) -> str:
        s = (str(text)
             .replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("\n", " ")
             .strip())
        return s if len(s) <= max_len else s[:max_len - 1] + "…"

    def _vertex(self, nid: str, label: str, style: str,
                x: float, y: float, w: float, h: float) -> None:
        cell = ET.Element("mxCell", id=nid, value=label,
                          style=style, vertex="1", parent="1")
        geo = ET.SubElement(cell, "mxGeometry", **{"as": "geometry"})
        geo.set("x", str(int(x)))
        geo.set("y", str(int(y)))
        geo.set("width", str(int(w)))
        geo.set("height", str(int(h)))
        self._cells.append(cell)

    def _edge(self, src: str, tgt: str, label: str = "", dashed: bool = False) -> None:
        eid = self._id("e")
        style = "edgeStyle=none;html=1;rounded=0;"
        if dashed:
            style += "dashed=1;"
        cell = ET.Element("mxCell", id=eid, value=label, style=style,
                           edge="1", source=src, target=tgt, parent="1")
        ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        self._cells.append(cell)

    # ------------------------------------------------------------------ placers

    def _place(self, nid: str, label: str, style_key: str,
               cx: float, y: float) -> float:
        """Place a standard rect node. Returns bottom y."""
        self._vertex(nid, label, self._S[style_key],
                     cx - self._NW / 2, y, self._NW, self._NH)
        return y + self._NH

    def _place_diamond(self, nid: str, label: str, cx: float, y: float) -> float:
        """Place a diamond (control) node. Returns bottom y."""
        self._vertex(nid, label, self._S["ctrl"],
                     cx - self._DW / 2, y, self._DW, self._DH)
        return y + self._DH

    def _place_terminal(self, nid: str, label: str, cx: float, y: float) -> float:
        self._vertex(nid, label, self._S["terminal"],
                     cx - self._NW / 2, y, self._NW, self._NH)
        return y + self._NH

    def _place_merge(self, nid: str, cx: float, y: float) -> float:
        """Place an invisible merge dot. Returns bottom y."""
        self._vertex(nid, "", self._S["merge"], cx - 10, y, 20, 20)
        return y + 20

    # ------------------------------------------------------------------ convert

    def convert(self, sol_doc: dict) -> str:
        # Agent root form: a file whose single key is AGENT is unwrapped to its agent.
        if set(sol_doc.keys()) == {"AGENT"}:
            sol_doc = sol_doc["AGENT"]
        name = sol_doc.get("name", "process")
        self._cells = []
        self._y = 80
        self._counter = 0
        self._subs = {}
        self._agents = {}
        cx = float(self._CX)

        # START
        start_id = self._id("START")
        self._y = self._place_terminal(start_id, f"▶ {self._esc(name)}", cx, self._y)
        self._y += self._VGAP

        # Routine
        routine = sol_doc.get("ROUTINE", [])
        if routine:
            r_first, r_last = self._routine(routine, cx)
            self._edge(start_id, r_first)
            end_id = self._id("END")
            self._y = self._place_terminal(end_id, "⏹ end", cx, self._y)
            self._edge(r_last, end_id)
        else:
            end_id = self._id("END")
            self._y = self._place_terminal(end_id, "⏹ end", cx, self._y)
            self._edge(start_id, end_id)

        # Global ONERROR — placed off to the right
        if "ONERROR" in sol_doc:
            gerr_id = self._id("GERR")
            self._vertex(gerr_id, "⚠ Global ONERROR", self._S["onerror"],
                          cx + self._NW / 2 + 60, 80, self._NW, self._NH)

        return self._build_xml()

    def _build_xml(self) -> str:
        model = ET.Element("mxGraphModel",
                            dx="1422", dy="762",
                            grid="1", gridSize="10",
                            guides="1", tooltips="1",
                            connect="1", arrows="1", fold="1",
                            page="1", pageScale="1",
                            pageWidth="1654", pageHeight="1169",
                            math="0", shadow="0")
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")
        for cell in self._cells:
            root.append(cell)
        _indent(model)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(model, encoding="unicode")

    # ------------------------------------------------------------------ routine

    def _routine(self, routine: list, cx: float) -> tuple[str, str]:
        """Process a list of instructions sequentially. Returns (first_id, last_id)."""
        if not routine:
            nid = self._id("noop")
            self._place_merge(nid, cx, self._y)
            self._y += 20 + self._VGAP
            return nid, nid

        segments: list[tuple[str, str]] = []
        for instr in routine:
            segments.append(self._instruction(instr, cx))

        for i in range(len(segments) - 1):
            self._edge(segments[i][1], segments[i + 1][0])

        return segments[0][0], segments[-1][1]

    def _instruction(self, instr: dict, cx: float) -> tuple[str, str]:
        if not isinstance(instr, dict):
            return self._unknown(instr, cx)
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
                return handler(instr, cx)
        return self._unknown(instr, cx)

    # ------------------------------------------------------------------ leaves

    def _todo(self, instr: dict, cx: float) -> tuple[str, str]:
        nid = self._id("T")
        model_tag = f" [{instr['model']}]" if "model" in instr else ""
        label = self._esc(instr["TODO"]) + model_tag
        y = self._y
        self._y = self._place(nid, label, "todo", cx, y) + self._VGAP
        if "ONERROR" in instr:
            self._inline_onerror(nid, cx, y)
        return nid, nid

    def _run(self, instr: dict, cx: float) -> tuple[str, str]:
        nid = self._id("R")
        label = "RUN: " + self._esc(instr["RUN"])
        y = self._y
        self._y = self._place(nid, label, "run", cx, y) + self._VGAP
        if "ONERROR" in instr:
            self._inline_onerror(nid, cx, y)
        return nid, nid

    def _inline_onerror(self, from_id: str, cx: float, node_y: float) -> None:
        err_id = self._id("ERR")
        self._vertex(err_id, "⚠ ONERROR", self._S["onerror"],
                      cx + self._NW / 2 + 20, node_y, self._NW, self._NH)
        self._edge(from_id, err_id, "", dashed=True)

    def _return(self, instr: dict, cx: float) -> tuple[str, str]:
        nid = self._id("RETURN")
        msg = instr.get("RETURN")
        label = f"↩️ RETURN: {self._esc(str(msg))}" if msg else "↩️ RETURN"
        y = self._y
        self._y = self._place(nid, label, "return", cx, y) + self._VGAP
        return nid, nid

    def _halt(self, instr: dict, cx: float) -> tuple[str, str]:
        nid = self._id("HALT")
        msg = instr.get("HALT")
        label = f"🛑 HALT: {self._esc(str(msg))}" if msg else "🛑 HALT"
        y = self._y
        self._y = self._place(nid, label, "halt", cx, y) + self._VGAP
        return nid, nid

    def _wait(self, instr: dict, cx: float) -> tuple[str, str]:
        nid = self._id("WUI")
        prompt = self._esc(instr.get("WAITUSERINPUT", "waiting for input…"))
        y = self._y
        self._y = self._place(nid, f"⏸ {prompt}", "io", cx, y) + self._VGAP
        return nid, nid

    def _import(self, instr: dict, cx: float) -> tuple[str, str]:
        nid = self._id("IMP")
        label = f"IMPORT: {self._esc(instr['IMPORT'])}"
        y = self._y
        self._y = self._place(nid, label, "import", cx, y) + self._VGAP
        return nid, nid

    def _unknown(self, instr, cx: float) -> tuple[str, str]:
        nid = self._id("UNK")
        y = self._y
        self._y = self._place(nid, self._esc(str(instr)), "todo", cx, y) + self._VGAP
        return nid, nid

    # ------------------------------------------------------------------ control

    def _if(self, instr: dict, cx: float) -> tuple[str, str]:
        block = instr["IF"]
        cond_id = self._id("C")
        y_cond = self._y
        self._y = self._place_diamond(cond_id, self._esc(block.get("when", "condition")),
                                       cx, y_cond) + self._VGAP

        y_branch = self._y
        then_cx = cx - self._HOFF
        else_cx = cx + self._HOFF

        # Then branch
        then_steps = block.get("then", [])
        self._y = y_branch
        if then_steps:
            t_first, t_last = self._routine(then_steps, then_cx)
            self._edge(cond_id, t_first, "yes")
        else:
            t_first = t_last = None
        then_y = self._y

        # Else branch
        else_steps = block.get("else", [])
        self._y = y_branch
        if else_steps:
            e_first, e_last = self._routine(else_steps, else_cx)
            self._edge(cond_id, e_first, "no")
        else:
            e_first = e_last = None
        else_y = self._y

        # Merge
        self._y = max(then_y, else_y)
        merge_id = self._id("M")
        self._place_merge(merge_id, cx, self._y)
        self._y += 20 + self._VGAP

        if t_last:
            self._edge(t_last, merge_id)
        else:
            self._edge(cond_id, merge_id, "yes")
        if e_last:
            self._edge(e_last, merge_id)
        else:
            self._edge(cond_id, merge_id, "no")

        return cond_id, merge_id

    def _when(self, instr: dict, cx: float) -> tuple[str, str]:
        branches = instr["WHEN"]
        merge_id = self._id("WM")
        first_id = None
        prev_cond_id = None
        max_y = self._y

        for branch in branches:
            has_when = "when" in branch
            has_else = "else" in branch and not has_when

            if has_else:
                else_steps = branch.get("else", [])
                if else_steps and prev_cond_id:
                    saved_y = self._y
                    e_cx = cx + self._HOFF
                    e_first, e_last = self._routine(else_steps, e_cx)
                    self._edge(prev_cond_id, e_first, "no")
                    self._edge(e_last, merge_id)
                    max_y = max(max_y, self._y)
                    self._y = saved_y
                elif prev_cond_id:
                    self._edge(prev_cond_id, merge_id, "no")
            else:
                cond_id = self._id("WC")
                label = self._esc(branch.get("when", "condition"))
                y_c = self._y
                self._y = self._place_diamond(cond_id, label, cx, y_c) + self._VGAP

                if first_id is None:
                    first_id = cond_id
                if prev_cond_id is not None:
                    self._edge(prev_cond_id, cond_id, "no")

                then_steps = branch.get("then", [])
                if then_steps:
                    saved_y = self._y
                    t_cx = cx - self._HOFF
                    t_first, t_last = self._routine(then_steps, t_cx)
                    self._edge(cond_id, t_first, "yes")
                    self._edge(t_last, merge_id)
                    max_y = max(max_y, self._y)
                    self._y = saved_y
                else:
                    self._edge(cond_id, merge_id, "yes")

                prev_cond_id = cond_id

        has_explicit_else = any("else" in b and "when" not in b for b in branches)
        if prev_cond_id and not has_explicit_else:
            self._edge(prev_cond_id, merge_id, "no")

        self._y = max(max_y, self._y)
        self._place_merge(merge_id, cx, self._y)
        self._y += 20 + self._VGAP

        return (first_id or merge_id), merge_id

    def _repeat(self, instr: dict, cx: float) -> tuple[str, str]:
        block = instr["REPEAT"]
        for key in ("while", "until", "for", "foreach"):
            if key in block:
                loop_label = f"{key}: {self._esc(str(block[key]))}"
                loop_type = key
                break
        else:
            loop_label = "loop"
            loop_type = "while"

        check_id = self._id("LC")
        self._y = self._place_diamond(check_id, loop_label, cx, self._y) + self._VGAP

        body = block.get("ROUTINE", [])
        if body:
            b_first, b_last = self._routine(body, cx)
            lbl_cont = "not yet" if loop_type == "until" else "continue"
            self._edge(check_id, b_first, lbl_cont)
            self._edge(b_last, check_id)  # loop back

        exit_id = self._id("LE")
        self._place_merge(exit_id, cx, self._y)
        self._y += 20 + self._VGAP
        lbl_exit = "done" if loop_type == "until" else "exit"
        self._edge(check_id, exit_id, lbl_exit)

        return check_id, exit_id

    # ------------------------------------------------------------------ subs/agents

    def _sub_def(self, instr: dict, cx: float) -> tuple[str, str]:
        sub = instr["SUB"]
        name = sub.get("name", "subroutine")
        marker_id = self._id("SD")
        label = f"define SUB: {self._esc(name)}"
        y = self._y
        self._y = self._place(marker_id, label, "subdef", cx, y) + self._VGAP
        self._subs[name] = marker_id
        return marker_id, marker_id

    def _call(self, instr: dict, cx: float) -> tuple[str, str]:
        nid = self._id("CALL")
        name = instr["CALL"]
        y = self._y
        self._y = self._place(nid, f"CALL: {self._esc(name)}", "sub", cx, y) + self._VGAP
        if name in self._subs:
            self._edge(nid, self._subs[name], "", dashed=True)
        return nid, nid

    def _agent_def(self, instr: dict, cx: float) -> tuple[str, str]:
        agent = instr["AGENT"]
        name = agent.get("name", "agent")
        marker_id = self._id("AD")
        label = f"define AGENT: {self._esc(name)}"
        y = self._y
        self._y = self._place(marker_id, label, "agentdef", cx, y) + self._VGAP
        self._agents[name] = marker_id
        return marker_id, marker_id

    def _spawn(self, instr: dict, cx: float) -> tuple[str, str]:
        nid = self._id("SP")
        name = instr["SPAWN"]
        parts = [f"SPAWN: {self._esc(name)}"]
        if "with" in instr:
            parts.append(f"with: {self._esc(instr['with'], 35)}")
        if "returns" in instr:
            parts.append(f"returns: {self._esc(instr['returns'], 35)}")
        label = " | ".join(parts)
        y = self._y
        self._y = self._place(nid, label, "agent", cx, y) + self._VGAP
        if name in self._agents:
            self._edge(nid, self._agents[name], "", dashed=True)
        return nid, nid

    def _delegate(self, instr: dict, cx: float) -> tuple[str, str]:
        nid = self._id("DG")
        block = instr["DELEGATE"]
        task = self._esc(block.get("task", "delegate task"))
        model_tag = f" [{block['model']}]" if "model" in block else ""
        y = self._y
        self._y = self._place(nid, f"DELEGATE: {task}{model_tag}", "agent", cx, y) + self._VGAP
        return nid, nid


# ------------------------------------------------------------------
# XML pretty-print (compatible with Python 3.8+)
# ------------------------------------------------------------------

def _indent(elem, level: int = 0) -> None:
    pad = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = pad + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = pad
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = pad
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = pad


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    args = [a for a in sys.argv[1:] if a]
    stdout_mode = "--stdout" in args
    args = [a for a in args if a != "--stdout"]

    if not args:
        print(
            "Usage: sol2drawio.py <process.json> [output.drawio] [--stdout]",
            file=sys.stderr,
        )
        sys.exit(1)

    sol_path = Path(args[0])
    if not sol_path.exists():
        print(f"Error: file not found: {sol_path}", file=sys.stderr)
        sys.exit(1)

    with open(sol_path, encoding="utf-8") as f:
        doc = json.load(f)

    result = Sol2DrawIO().convert(doc)

    if stdout_mode:
        print(result)
        return

    out_path = Path(args[1]) if len(args) >= 2 else sol_path.with_suffix(".drawio")
    out_path.write_text(result, encoding="utf-8")
    print(f"draw.io diagram written to: {out_path}", file=sys.stderr)
    print("Tip: open in draw.io, then use Ctrl+Shift+H (Arrange → Layout → Vertical Tree) for a clean layout.", file=sys.stderr)


if __name__ == "__main__":
    main()
