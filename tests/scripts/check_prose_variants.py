#!/usr/bin/env python3
"""
Check a prose rendering against the SOL document it was rendered from.

The prose variants are produced by a model in one pass (`PROSE-VARIANT-PROMPT.md`
for `prose-generated`) or by a renderer (`build_prose_mechanical.py` for
`prose-mechanical`), and what can go wrong in them is narrow and known. Every
defect the generation prompt has recorded so far is one of these, and each cost a
block of MAIN runs before anyone noticed:

  trace lines      A line the source says to emit verbatim must survive character
                   for character, with nothing wrapped around it: a backtick or a
                   quotation mark against it is one the reader copies into what it
                   writes, and the parser will not match a line that starts with
                   one -- the prompt's fifth recorded defect. Standing alone on its
                   own line is checked for prose-generated only, that being a rule
                   its generation prompt gives rather than one the parser needs:
                   prose-mechanical renders each line inline after "Emit verbatim: "
                   and has the best trace yield of the seven renderings.
  no gag order     A document that requires trace lines and then says to output
                   the returned object and nothing else has forbidden them, and
                   the prohibition comes last, which is why models obey it. 61 of
                   MAIN's 69 prose-generated runs returned no trace at all -- the
                   sixth recorded defect.
  frontmatter      The contract is not the generator's to rewrite.
  the section      `## The procedure` stands where the process definition was, and
                   no SOL fence is left behind.

This checks those four things and nothing else. It cannot tell whether the prose
says what the process says -- that is what the campaign measures.

Usage:
    python tests/scripts/check_prose_variants.py            # every fixture, both variants
    python tests/scripts/check_prose_variants.py --variant prose-generated
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

# a line the oracle reads: the bracketed prefix and everything to end of line
TRACE_RE = re.compile(r"\[fixture-[^\]\n]+\]\[[^\]\n]+\][^\"\n]*")

# the shape that suppressed the trace: a return instruction that forbids output
# rather than fields. Deliberately narrow -- "return it alone" about the OBJECT is
# fine and every document says it; what is not fine is nothing else being allowed
# out at all.
GAG_RE = re.compile(
    r"(output|return|write)[^.\n]{0,80}\b(and nothing else|nothing but)\b"
    r"|no commentary before it, none after it",
    re.IGNORECASE)


def _frontmatter(text: str) -> str:
    parts = text.split("---\n", 2)
    return parts[1] if len(parts) >= 3 else ""


def _normalise_trace(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip().rstrip("\\")


def check_one(source: Path, prose: Path, standalone: bool) -> list[str]:
    problems: list[str] = []
    src = source.read_text(encoding="utf-8")
    doc = prose.read_text(encoding="utf-8")

    # 1. frontmatter untouched
    if _frontmatter(src) != _frontmatter(doc):
        problems.append("frontmatter differs from the source")

    # 2. the section stands where the process was
    if "## The procedure" not in doc:
        problems.append("no `## The procedure` section")
    if '"ROUTINE"' in doc:
        problems.append("a SOL script survived in the prose")

    # 3. every verbatim line present and unwrapped
    want = {_normalise_trace(m) for m in TRACE_RE.findall(src)}
    lines = [l.strip() for l in doc.splitlines()]
    bare = {_normalise_trace(l) for l in lines}
    flat = _normalise_trace(doc.replace("\n", " "))
    for line in sorted(want):
        if line not in flat:
            problems.append(f"trace line missing: {line[:70]}")
            continue
        # a backtick or quote against the prefix is a character the reader copies
        # into what it writes, and the parser matches from the prefix onward --
        # it would not recognise the line at all
        for l in lines:
            i = l.find(line[:40])
            if i > 0 and l[i - 1] in "`'\"":
                problems.append(f"trace line wrapped in {l[i - 1]!r}: {line[:60]}")
                break
        if standalone and line not in bare:
            problems.append(f"trace line not alone on its line: {line[:70]}")

    # 4. no absolute prohibition on output
    for m in GAG_RE.finditer(doc):
        if want:  # only a defect where trace lines are required
            problems.append(f"output gagged: ...{doc[max(0, m.start()-40):m.end()+20]!r}")

    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", default=None,
                    choices=["prose-generated", "prose-mechanical"],
                    help="check only this variant [default: both]")
    args = ap.parse_args()

    variants = [args.variant] if args.variant else ["prose-mechanical", "prose-generated"]
    failed = 0
    checked = 0

    for source in sorted(FIXTURES_DIR.glob("*/*/*.md")):
        if "-prose-" in source.name or source.name == "README.md":
            continue
        stem = source.stem
        for variant in variants:
            prose = source.with_name(f"{stem}-{variant}.md")
            if not prose.exists():
                continue
            checked += 1
            problems = check_one(source, prose,
                                 standalone=(variant == "prose-generated"))
            if problems:
                failed += 1
                print(f"FAIL {prose.relative_to(REPO_ROOT)}")
                for p in problems:
                    print(f"       {p}")
            else:
                print(f"ok   {prose.relative_to(REPO_ROOT)}")

    print(f"\n{checked} documents, {failed} with problems")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
