#!/usr/bin/env python3
"""
build_repl_arms.py — materialize the two SS8.3 replication fixture dirs.

One command, run AFTER the manual verification has landed in
pool-manifest.json (apply_pool_corrections.py). It performs, in order:

  1. copy the process documents byte-identically from the source arms,
     renamed to the target dir names (support-routing-repl.md, ...): the
     frontmatter names stay `fixture-w2-support-routing[-notrace]`, so the
     prompts a model reads are the source arms' prompts, byte for byte;
  2. copy prose-generated the same way — a frozen artefact (SS8.1 item 6):
     same source document, same rendering; regenerating it would be a new
     model pass and a new treatment;
  3. copy catalog.json and reference.py (the oracle);
  4. build_requests.py --repl: the twenty frozen strata and worlds, items
     drawn from the verified REPLICATION survivors, seed REPL_SEED;
  5. hydrate both inputs/ dirs from data-local/pool-replication.json;
  6. build_prose_mechanical.py: regenerates prose-mechanical for every
     fixture; the two new ones appear, the nine existing ones must report
     `unchanged`.

Idempotent: rerunning overwrites the same files with the same bytes.

After it: bump the fixture count in test_prose_mechanical.py (9 -> 11) if not
already done, run the toolchain suite, then `campaign.py smoke --plan --block
routing-repl` / `routing-notrace-repl`.

Usage:
    python tests/scripts/build_repl_arms.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
W2 = REPO_ROOT / "tests" / "fixtures" / "w2-branching"
SCRIPTS = Path(__file__).parent

ARMS = [("support-routing", "support-routing-repl"),
        ("support-routing-notrace", "support-routing-notrace-repl")]

README = """\
# {dst} — the SS8.3 replication of the {kind} arm

`{src}` rerun on items the campaign has never seen. The process document, both
prose renderings, `catalog.json` and `reference.py` are byte-identical to the
source arm (the documents keep the frontmatter name `{fname}`: same prompts, so
nothing in what a model reads names the arm). What changes is the draw: the
same twenty frozen strata and world states (`build_requests.STRATA`), filled
from the sealed REPLICATION half of the pool — seed 20260827, split
`REPLICATION` — after manual verification of a seed-selected candidate set
(`select_repl_candidates.py`, `build_verification_html.py --repl`,
`apply_pool_corrections.py`).

Grid: the decisive cells only (`campaign.DECISIVE_CELLS`), 7 renderings,
2 reps — block `{block}`. Read one-to-one against `{src}`.

Regenerate everything in this directory: `python tests/scripts/build_repl_arms.py`
"""


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    r = subprocess.run([sys.executable] + cmd, cwd=REPO_ROOT)
    if r.returncode != 0:
        sys.exit(r.returncode)


def main() -> None:
    for src, dst in ARMS:
        (W2 / dst).mkdir(exist_ok=True)
        shutil.copyfile(W2 / src / f"{src}.md", W2 / dst / f"{dst}.md")
        shutil.copyfile(W2 / src / f"{src}-prose-generated.md",
                        W2 / dst / f"{dst}-prose-generated.md")
        for aux in ("catalog.json", "reference.py"):
            shutil.copyfile(W2 / src / aux, W2 / dst / aux)
        fname = ("fixture-w2-support-routing-notrace" if "notrace" in src
                 else "fixture-w2-support-routing")
        (W2 / dst / "README.md").write_text(
            README.format(src=src, dst=dst, fname=fname,
                          kind="untracked" if "notrace" in src else "tracked",
                          block="routing-notrace-repl" if "notrace" in src else "routing-repl"),
            encoding="utf-8")
        print(f"  {dst}: documents copied")

    run([str(SCRIPTS / "build_requests.py"), "--repl"])
    for _src, dst in ARMS:
        run([str(SCRIPTS / "hydrate.py"), "--mode", "requests",
             "--routing-dir", str(W2 / dst)])
    run([str(SCRIPTS / "build_prose_mechanical.py")])
    print("\nDone. Next: bump test_prose_mechanical count to 11 if needed, "
          "run the suite, then campaign.py smoke --plan --block routing-repl.")


if __name__ == "__main__":
    main()
