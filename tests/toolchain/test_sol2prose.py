"""
R1 toolchain tests for sol2prose.py — the SOL → narrative prose renderer.

Ordinary, fast, fully deterministic unit tests: a tiny SOL document goes in, a known
phrase comes out. No model, no harness, no network. This is the cheapest ring (R1) —
see doc/testing-strategy.md.

Two properties matter more than any single phrase, and each has its own test below:

  * **verbatim** — a leaf (TODO text, RUN command, condition, contract desc) must come
    out exactly as it went in: never paraphrased, never truncated, never translated.
  * **total coverage** — no construct may be silently dropped. A document using every
    SOL 0.6 construct must produce a line for each one.

Run from the repo root:

    python3 -m pytest tests/toolchain -q
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# Load the renderer by path: it lives under .claude/, outside any package.
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parents[2]
PROSE_PATH = REPO_ROOT / ".claude" / "skills" / "sol" / "scripts" / "sol2prose.py"

_spec = importlib.util.spec_from_file_location("sol2prose", PROSE_PATH)
sol2prose = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sol2prose)


# --------------------------------------------------------------------------- #
# Helpers — keep each test a one-line assertion about what the prose says.
# --------------------------------------------------------------------------- #
def render(doc, lang="en"):
    return sol2prose.Sol2Prose(lang=lang).convert(doc)


def proc(routine, **root):
    """A minimal process document wrapping the given routine."""
    return {"name": "t", "version": "1.0", "ROUTINE": routine, **root}


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(PROSE_PATH), *[str(a) for a in args]],
        capture_output=True, text=True, encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# One rendering per construct
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("instr,expected", [
    ({"TODO": "Read the status files"},              "Read the status files"),
    ({"RUN": "git status"},                          "Run exactly: `git status`"),
    ({"IF": {"when": "it is ready", "then": []}},    "If it is ready, then:"),
    ({"WHEN": [{"when": "A", "then": []}]},          "Depending on the case:"),
    ({"REPEAT": {"while": "the queue is full", "ROUTINE": []}},
     "While the queue is full, repeat:"),
    ({"REPEAT": {"until": "green", "ROUTINE": []}},  "Repeat until green:"),
    ({"REPEAT": {"for": "3", "ROUTINE": []}},        "Repeat 3 times:"),
    ({"REPEAT": {"foreach": "item in the list", "ROUTINE": []}},
     "For each item in the list:"),
    ({"SUB": {"name": "check", "ROUTINE": []}},      "Define the subroutine «check»"),
    ({"CALL": "check"},                              "Call the subroutine «check»"),
    ({"AGENT": {"name": "auditor", "ROUTINE": []}},  "Define the agent «auditor»"),
    ({"SPAWN": "auditor"},                           "Hand off to the agent «auditor»"),
    ({"DELEGATE": {"task": "Summarize it"}},         "one-off task"),
    ({"IMPORT": "shared/common.json"},               "Load the definitions from `shared/common.json`."),
    ({"RETURN": None},                               "hand control back to whoever invoked it."),
    ({"RETURN": "done"},                             "yielding: done"),
    ({"HALT": None},                                 "Stop the entire run."),
    ({"HALT": "no way out"},                         "Stop the entire run — no way out"),
    ({"WAITUSERINPUT": "Approve?"},                  "Pause and ask the human: Approve?"),
])
def test_construct_renders(instr, expected):
    assert expected in render(proc([instr]))


def test_every_construct_appears_no_silent_drop():
    """A document using every construct must produce a line for each one."""
    routine = [
        {"TODO": "leaf-todo"},
        {"RUN": "leaf-run"},
        {"IF": {"when": "cond-if", "then": [{"TODO": "leaf-then"}],
                "else": [{"TODO": "leaf-else"}]}},
        {"WHEN": [{"when": "cond-when", "then": [{"TODO": "leaf-when"}]},
                  {"else": [{"TODO": "leaf-when-else"}]}]},
        {"REPEAT": {"foreach": "leaf-target", "ROUTINE": [{"TODO": "leaf-loop"}]}},
        {"SUB": {"name": "leaf-sub", "ROUTINE": [{"TODO": "leaf-sub-body"}]}},
        {"CALL": "leaf-sub"},
        {"AGENT": {"name": "leaf-agent", "accepts": "leaf-accepts",
                   "ROUTINE": [{"TODO": "leaf-agent-body"}]}},
        {"SPAWN": "leaf-agent", "with": "leaf-with", "returns": "leaf-returns"},
        {"DELEGATE": {"task": "leaf-delegate"}},
        {"IMPORT": "leaf-import"},
        {"WAITUSERINPUT": "leaf-wait"},
        {"RETURN": "leaf-return"},
        {"HALT": "leaf-halt"},
    ]
    out = render(proc(routine, ONERROR=[{"TODO": "leaf-global-onerror"}]))
    for leaf in ("leaf-todo", "leaf-run", "cond-if", "leaf-then", "leaf-else",
                 "cond-when", "leaf-when", "leaf-when-else", "leaf-target", "leaf-loop",
                 "leaf-sub", "leaf-sub-body", "leaf-agent", "leaf-accepts",
                 "leaf-agent-body", "leaf-with", "leaf-returns", "leaf-delegate",
                 "leaf-import", "leaf-wait", "leaf-return", "leaf-halt",
                 "leaf-global-onerror"):
        assert leaf in out, f"dropped: {leaf}"


def test_unknown_construct_is_reported_not_swallowed():
    out = render(proc([{"MYSTERY": "not a construct"}]))
    assert "Unrecognized instruction" in out and "MYSTERY" in out


# --------------------------------------------------------------------------- #
# Verbatim — the property the round-trip depends on
# --------------------------------------------------------------------------- #
def test_leaf_text_is_verbatim_not_rewritten_or_truncated():
    weird = ("Scrivi 00_spec.md seguendo il ## template — with «quotes», a very long "
             "tail that must not be cut at fifty-five characters, and symbols: {} [] $#@!")
    out = render(proc([{"TODO": weird}]))
    assert weird in out


def test_run_command_is_verbatim_including_placeholders():
    cmd = "deploy.py --env {{revision.env}} --dry-run"
    out = render(proc([{"RUN": cmd}]))
    assert f"`{cmd}`" in out


def test_leaves_identical_across_languages_only_scaffolding_changes():
    doc = proc([{"TODO": "Leggi i file di stato"},
                {"IF": {"when": "manca il diff", "then": [{"TODO": "Fermati"}]}}])
    en, it = render(doc, "en"), render(doc, "it")
    for leaf in ("Leggi i file di stato", "manca il diff", "Fermati"):
        assert leaf in en and leaf in it
    assert "If manca il diff, then:" in en
    assert "Se manca il diff, allora:" in it


def test_unknown_language_rejected():
    with pytest.raises(KeyError):
        sol2prose.Sol2Prose(lang="xx")


# --------------------------------------------------------------------------- #
# What the round-trip must make visible
# --------------------------------------------------------------------------- #
def test_placeholders_are_flagged_as_coming_from_context():
    out = render(proc([{"TODO": "Write to {{task_dir}}/00_spec.md"}]))
    assert "[from context: task_dir]" in out


def test_single_braces_are_not_flagged_as_placeholders():
    out = render(proc([{"TODO": "Write to {task_dir}/00_spec.md"}]))
    assert "from context" not in out


def test_model_and_role_are_surfaced():
    out = render(proc([{"TODO": "Synthesize", "model": "smart"},
                       {"DELEGATE": {"task": "Edit", "role": "An editor."}}]))
    assert "[smart model]" in out
    assert "[as: An editor.]" in out


def test_structured_contract_rendered_field_by_field():
    out = render(proc([], accepts={
        "env": {"anyof": ["coding", "staging"], "required": True},
        "git_diff": {"required": True, "desc": "diff vs the merge-base"},
        "item_max": {"number": True},
        "resume": {"json": True},
    }))
    assert "`env` (required; one of: coding, staging)" in out
    assert "`git_diff` — diff vs the merge-base (required)" in out
    assert "`item_max` (numeric)" in out
    assert "`resume` (valid JSON)" in out


def test_open_contract_quoted_verbatim():
    out = render(proc([], returns="A verdict and the review text."))
    assert "A verdict and the review text." in out


def test_when_without_else_says_so():
    out = render(proc([{"WHEN": [{"when": "A", "then": [{"TODO": "x"}]}]}]))
    assert "If none of these hold, nothing happens here." in out


def test_when_with_else_does_not_say_so():
    out = render(proc([{"WHEN": [{"when": "A", "then": [{"TODO": "x"}]},
                                 {"else": [{"TODO": "y"}]}]}]))
    assert "If none of these hold" not in out


def test_inline_onerror_nests_under_the_step_it_guards():
    out = render(proc([{"RUN": "deploy.sh", "ONERROR": [{"TODO": "Roll back"}]}]))
    lines = [ln for ln in out.splitlines() if ln.strip()]
    step = next(i for i, ln in enumerate(lines) if "deploy.sh" in ln)
    assert lines[step + 1].startswith("  - If that fails:")
    assert lines[step + 2].startswith("    - Roll back")


def test_global_onerror_gets_its_own_section():
    out = render(proc([{"TODO": "x"}], ONERROR=[{"TODO": "Log it"}]))
    assert "## If anything fails anywhere in this process" in out


def test_foreach_target_already_quantified_does_not_double_the_each():
    out = render(proc([{"REPEAT": {"foreach": "each revision in the table", "ROUTINE": []}}]))
    assert "For each revision in the table:" in out
    assert "For each each" not in out


# --------------------------------------------------------------------------- #
# Structure: definitions deferred, agent root form, nesting
# --------------------------------------------------------------------------- #
def test_definitions_are_deferred_to_appendix_sections():
    out = render(proc([{"SUB": {"name": "s", "ROUTINE": [{"TODO": "sub-body"}]}},
                       {"AGENT": {"name": "a", "ROUTINE": [{"TODO": "agent-body"}]}}]))
    assert out.index("Define the subroutine «s»") < out.index("## Subroutines")
    assert out.index("## Subroutines") < out.index("sub-body")
    assert out.index("## Agents") < out.index("agent-body")


def test_agent_root_form_is_unwrapped():
    out = render({"AGENT": {"name": "feanor", "version": "1.0",
                            "description": "A single reusable agent.",
                            "ROUTINE": [{"TODO": "Do the work"}]}})
    assert out.startswith("# feanor")
    assert "A single reusable agent." in out
    assert "Do the work" in out


def test_nesting_uses_indentation():
    out = render(proc([{"IF": {"when": "c", "then": [{"TODO": "inner"}]}}]))
    assert "\n  - inner" in out


def test_empty_routine_is_stated():
    assert "This process has no steps." in render(proc([]))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_stdout(tmp_path):
    src = tmp_path / "p.json"
    src.write_text(json.dumps(proc([{"TODO": "Do it"}])), encoding="utf-8")
    r = run_cli(src, "--stdout")
    assert r.returncode == 0 and "Do it" in r.stdout


def test_cli_default_output_is_prose_md_and_never_overwrites_the_host_document(tmp_path):
    """A `.md` input hosts the SOL in json fences — writing `<stem>.md` would destroy it."""
    src = tmp_path / "release-gate.md"
    body = json.dumps(proc([{"TODO": "Do it"}]))
    src.write_text(f"# Fixture\n\n```json\n{body}\n```\n", encoding="utf-8")
    original = src.read_text(encoding="utf-8")

    r = run_cli(src)
    assert r.returncode == 0
    out = tmp_path / "release-gate.prose.md"
    assert out.exists() and "Do it" in out.read_text(encoding="utf-8")
    assert src.read_text(encoding="utf-8") == original


def test_cli_markdown_input_renders_every_sol_fence(tmp_path):
    src = tmp_path / "multi.md"
    a = json.dumps(proc([{"TODO": "first fence"}], name="one"))
    b = json.dumps({"not": "sol"})
    c = json.dumps(proc([{"TODO": "second fence"}], name="two"))
    src.write_text(f"```json\n{a}\n```\n```json\n{b}\n```\n```json\n{c}\n```\n",
                   encoding="utf-8")
    r = run_cli(src, "--stdout")
    assert r.returncode == 0
    assert "first fence" in r.stdout and "second fence" in r.stdout
    assert "fence#1" in r.stdout and "fence#3" in r.stdout


def test_cli_lang_flag(tmp_path):
    src = tmp_path / "p.json"
    src.write_text(json.dumps(proc([{"TODO": "Fai la cosa"}])), encoding="utf-8")
    assert "## Che cosa fa" in run_cli(src, "--stdout", "--lang", "it").stdout
    assert "## Che cosa fa" in run_cli(src, "--stdout", "--lang=it").stdout


def test_cli_rejects_unknown_language(tmp_path):
    src = tmp_path / "p.json"
    src.write_text(json.dumps(proc([{"TODO": "x"}])), encoding="utf-8")
    r = run_cli(src, "--stdout", "--lang", "xx")
    assert r.returncode == 1 and "unknown language" in r.stderr


def test_cli_rejects_a_file_with_no_sol_in_it(tmp_path):
    src = tmp_path / "readme.md"
    src.write_text("# Just prose, no fences.\n", encoding="utf-8")
    r = run_cli(src, "--stdout")
    assert r.returncode == 1


def test_cli_missing_file():
    r = run_cli("does-not-exist.json", "--stdout")
    assert r.returncode == 1 and "file not found" in r.stderr


# --------------------------------------------------------------------------- #
# The corpus must render end to end
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("rel", [
    "examples/daily-briefing.json",
    "examples/review-runner.json",
    "examples/vault-ingest.json",
    "examples/weekly-closure.json",
    "tests/fixtures/w0-transform/polarity-flip/polarity-flip.md",
    "tests/fixtures/w1-linear/cart-summary/cart-summary.md",
    "tests/fixtures/w1-linear/cart-total/cart-total.md",
    "tests/fixtures/w2-branching/release-gate/release-gate.md",
    "tests/fixtures/w2-branching/sales-summary/sales-summary.md",
    "tests/fixtures/w2-branching/support-intake/support-intake.md",
    "tests/fixtures/w3-multi-call/task-router/task-router.md",
])
def test_repo_corpus_renders(rel):
    r = run_cli(REPO_ROOT / rel, "--stdout")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip()
