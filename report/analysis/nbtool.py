#!/usr/bin/env python3
"""Minimal notebook writer shared by the build_*.py scripts.

The notebooks in this directory are generated, not hand-edited: change the
build script and rerun it.
"""
from __future__ import annotations

import json
from pathlib import Path


class Notebook:
    def __init__(self, kernel: str = "sol-analysis",
                 display: str = "SOL analysis (3.14)") -> None:
        self.cells: list[tuple[str, str]] = []
        self.kernel = kernel
        self.display = display

    def md(self, text: str) -> None:
        self.cells.append(("markdown", text))

    def code(self, text: str) -> None:
        self.cells.append(("code", text))

    def write(self, path: Path) -> None:
        nb = {
            "cells": [
                {
                    "cell_type": t,
                    "id": f"cell-{i:02d}",
                    "metadata": {},
                    "source": s.splitlines(keepends=True),
                    **({"outputs": [], "execution_count": None} if t == "code" else {}),
                }
                for i, (t, s) in enumerate(self.cells)
            ],
            "metadata": {
                "kernelspec": {"display_name": self.display, "language": "python",
                               "name": self.kernel},
                "language_info": {"name": "python", "version": "3.14.6"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{len(self.cells)} celle -> {path}")
