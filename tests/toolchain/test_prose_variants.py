"""The prose renderings agree with the SOL documents they were rendered from.

Not a test of the prose -- whether it says what the process says is what the
campaign measures, and no assertion here can stand in for that. This is the narrow
band of defects that have actually happened, each of which cost a block of MAIN
runs before anyone read the document that caused them:

- a trace line wrapped in a backtick, which the parser then does not match
  (PROSE-VARIANT-PROMPT.md's fifth recorded defect);
- a document that requires trace lines and then forbids any output but the
  returned object, which is the sixth, and which suppressed the trace on 61 of
  MAIN's 69 prose-generated runs;
- a rewritten frontmatter, or a SOL fence left standing beside the prose.

The check lives in tests/scripts/check_prose_variants.py and is runnable on its
own; this binds it to the suite so a regenerated document cannot regress quietly.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tests" / "scripts" / "check_prose_variants.py"


def test_every_prose_document_agrees_with_its_source():
    proc = subprocess.run([sys.executable, str(SCRIPT)],
                          capture_output=True, text=True, cwd=REPO_ROOT)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_the_check_would_catch_a_gagged_document(tmp_path):
    """A guard on the guard. The check passing means nothing if it cannot fail:
    the defect it exists for is one that read as a clean document for a day."""
    sys.path.insert(0, str(REPO_ROOT / "tests" / "scripts"))
    import check_prose_variants as chk

    source = tmp_path / "f.md"
    source.write_text(
        '---\nname: f\n---\n\n## SOL script\n\n'
        '{"ROUTINE": [{"TODO": "Emit verbatim: [fixture-f][main] BRANCH: go"}]}\n',
        encoding="utf-8")
    prose = tmp_path / "f-prose-generated.md"
    prose.write_text(
        '---\nname: f\n---\n\n## The procedure\n\nEmit this line:\n\n'
        '[fixture-f][main] BRANCH: go\n\n'
        'Output that JSON object and nothing else.\n',
        encoding="utf-8")

    problems = chk.check_one(source, prose, standalone=True)
    assert any("gagged" in p for p in problems), problems
