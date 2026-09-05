"""R1 tests for the `prose-mechanical` documents and their generator
(tests/scripts/build_prose_mechanical.py, 2026-08-22).

SS5.4 of doc/experiment-minimum-context.md puts two prose renderings of the SAME SOL
document side by side with the five collateral levels. For the comparison to mean
anything, a prose document must differ from its SOL source in the process section and
NOWHERE else: same frontmatter, same task material, same input placeholder. A prose
document that also dropped a section, or reordered the material, would be a different
prompt, and the cell would be measuring the difference between two documents rather than
between two renderings of one.

The second property under test is SS8.1's frozen-artefact discipline: the documents on
disk must be exactly what the generator produces today. A hand-patched document reads
identically and is unreproducible, which is the failure this suite exists to make loud.

No model and no GPU: the generator is deterministic, so `--check` is a real assertion.
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / "tests" / "scripts"))

import runner.api_executor as api_mod
import runner.runner as runner_mod
import build_prose_mechanical as gen

SUPPORT_INTAKE = "w2-branching/support-intake"


def _fixtures():
    return gen.fixture_paths()


def _procedure_body(prose: str) -> str:
    """The '## The procedure' section alone. Bounded at the next '## ' because a
    fixture may carry material AFTER the process -- cart-total does."""
    after = prose[prose.index("## The procedure") + len("## The procedure"):]
    lines = after.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("## "):
            return "\n".join(lines[:i])
    return after


def test_every_fixture_has_a_prose_mechanical_document():
    """Nine fixtures, nine documents -- eight since 2026-08-23, when
    support-routing joined the corpus, nine since 2026-08-25, when its untracked
    clone support-routing-notrace did. A missing one is not a soft failure: the
    runner refuses that cell (FileNotFoundError) rather than falling back on the
    SOL prompt, so the row would die at run time, on a live server, halfway
    through a campaign."""
    fixtures = _fixtures()
    assert len(fixtures) == 9
    for fixture in fixtures:
        doc = fixture.with_name(f"{fixture.stem}-prose-mechanical.md")
        assert doc.exists(), f"missing {doc.relative_to(REPO_ROOT)}"


def test_the_documents_on_disk_are_what_the_generator_produces():
    """SS8.1: the artefact is regenerated, never edited. --check writes nothing."""
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tests" / "scripts" / "build_prose_mechanical.py"),
         "--check"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_a_prose_document_differs_from_its_source_only_in_the_process_section():
    """Frontmatter and material sections survive byte for byte, in their original
    order, with one declared exception: the sentence that points at the process
    definition (covered by its own test below). cart-total is the case that makes
    this a real assertion rather than a tautology: its SOL script sits BEFORE
    '## File content', so a generator that cut the document at the process heading
    instead of swapping the section would silently drop the input from the prompt."""
    for fixture in _fixtures():
        source = fixture.read_text(encoding="utf-8")
        prose = fixture.with_name(f"{fixture.stem}-prose-mechanical.md").read_text(encoding="utf-8")

        def sections(text):
            """[(heading, body)] for every '## ' section, plus everything before."""
            out, current, body = [], None, []
            for line in text.split("\n"):
                if line.startswith("## "):
                    out.append((current, "\n".join(body)))
                    current, body = line, []
                else:
                    body.append(line)
            out.append((current, "\n".join(body)))
            return out

        src, dst = sections(source), sections(prose)
        assert [h for h, _ in src].count("## SOL script") == 1
        assert [h for h, _ in dst].count("## The procedure") == 1
        # same sections, same order, the process one renamed
        assert ([h.replace("## SOL script", "## The procedure") if h else h for h, _ in src]
                == [h for h, _ in dst])
        for (src_h, src_body), (_dst_h, dst_body) in zip(src, dst):
            if src_h == "## SOL script":
                continue
            assert (gen.repoint_pointer_sentence(src_body) == dst_body), \
                f"{fixture.name}: {src_h} changed beyond the pointer sentence"


def test_the_pointer_sentence_no_longer_points_at_a_script_that_is_not_there():
    """All but one of the fixtures open with '...by executing strictly the SOL script
    below'. In a prose document there is no script below, and the dangling reference
    sits on the sentence that tells the model what it is about to read -- defect 4
    of PROSE-VARIANT-PROMPT.md, which a generator that copies the material verbatim
    reintroduces."""
    repointed = 0
    for fixture in _fixtures():
        prose = fixture.with_name(f"{fixture.stem}-prose-mechanical.md").read_text(encoding="utf-8")
        _fm, body = prose.split("\n---\n", 1)[-1], prose
        assert "SOL script" not in body.split("---\n", 2)[-1], f"{fixture.name} still points at a SOL script"
        if "procedure described" in prose:
            repointed += 1
    assert repointed == 6, f"{repointed} document(s) re-pointed, expected 6"


def test_a_prose_document_carries_no_sol_notation():
    """The point of the cell is that the model never sees the script. A leftover
    fence would make the row a measurement of SOL filed under prose."""
    for fixture in _fixtures():
        prose = fixture.with_name(f"{fixture.stem}-prose-mechanical.md").read_text(encoding="utf-8")
        procedure = _procedure_body(prose)
        for keyword in ('"ROUTINE"', '"TODO"', '"RETURN"', '"REPEAT"'):
            assert keyword not in procedure, f"{fixture.name} still shows {keyword}"


def test_no_heading_in_the_procedure_outranks_the_procedure_itself():
    """The renderer emits its own '## What it does' / '## Subroutines'. Left at
    that level they become siblings of '## File content' and the document says
    the subroutines are a section of the task, not part of the process."""
    for fixture in _fixtures():
        prose = fixture.with_name(f"{fixture.stem}-prose-mechanical.md").read_text(encoding="utf-8")
        for line in _procedure_body(prose).split("\n"):
            if line.startswith("# ") or line.startswith("## "):
                pytest.fail(f"{fixture.name}: {line!r} sits at or above '## The procedure'")


def _has_hydrated_queues() -> bool:
    return any((runner_mod.FIXTURES_DIR / SUPPORT_INTAKE / "inputs").glob("queue-*.json"))


@pytest.mark.skipif(not _has_hydrated_queues(),
                    reason="queues not hydrated in this checkout")
def test_the_runner_builds_the_cell_from_the_document():
    """End to end at E0: the loader picks the document up as the rendering
    'prose-mechanical', and the built prompt has the input in it and the script
    out of it."""
    fixture_dir, sol_doc, _expectations, meta = runner_mod._load_fixture(SUPPORT_INTAKE)
    assert "prose-mechanical" in meta["prose"]

    bundle = runner_mod._load_input(fixture_dir, "queue-01")
    prompt = api_mod._build_prompt_e0(sol_doc, bundle, meta["body"],
                                      level="prose-mechanical",
                                      prose_bodies=meta["prose"])
    assert '"ROUTINE"' not in prompt
    assert "{{file_content}}" not in prompt
    assert "[fixture-w2-support-intake][main] EVAL:" in prompt
    assert runner_mod.L1_INSTRUCTION not in prompt
