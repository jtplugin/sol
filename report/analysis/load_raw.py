#!/usr/bin/env python3
"""
Build tidy.csv — the analysis table — from the raw per-run artifacts.

This script is the *producer*. Nothing else reads the raw artifacts: the
notebook, the fact sheet and every number in the articles read tidy.csv. One
path in, one path out.

Source of truth is the pair of files each run leaves on disk:
    <run_id>.json        the run record (config, execution, output, usage)
    <run_id>.score.json  the oracle verdict (fidelity, quality, comprehension)

The campaign index (index.csv) is NOT used: it binarizes quality to pass/fail
and drops quality.rate and redundancy_ratio entirely. Reading the raw files
keeps the continuous measures. (The notebook does read index.csv, once, for the
sole purpose of checking whether it agrees with the raw scores — see 1.8.)

The raw artifacts are 213 MB and carry the administered prompts, hence the text
of third-party issue reports; they are not redistributed. tidy.csv carries only
identifiers and measures, and is enough to recompute the whole analysis. Running
this script therefore needs the private campaign tree; reading tidy.csv does not.

Usage:
    py report/analysis/load_raw.py          # rebuild report/analysis/tidy.csv
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
RAW = REPO / "tests" / "results-main"
OUT = HERE / "tidy.csv"

REP_RE = re.compile(r"-rep(\d+)$")


def _rep_of(run_id: str) -> int:
    m = REP_RE.search(run_id)
    if not m:
        raise ValueError(f"run_id without a rep suffix: {run_id!r}")
    return int(m.group(1))


def _record(score_path: Path) -> dict:
    run_path = Path(str(score_path).replace(".score.json", ".json"))
    if not run_path.exists():
        raise FileNotFoundError(f"score without its run record: {score_path}")

    s = json.loads(score_path.read_text(encoding="utf-8"))
    r = json.loads(run_path.read_text(encoding="utf-8"))
    cfg = r["config"]

    payload = (r.get("output") or {}).get("returned_payload")
    payload_status = payload.get("status") if isinstance(payload, dict) else None

    fid = s.get("fidelity") or {}
    qua = s.get("quality") or {}
    com = s.get("comprehension") or {}
    eff = s.get("efficiency") or {}

    exp_seq = fid.get("expected_sequence")
    obs_seq = fid.get("observed_sequence")

    return {
        # identity / design factors
        "run_id": s["run_id"],
        "fixture": s["fixture_id"].split("/")[-1],
        "input_id": s["staged_input_id"],
        "rep": _rep_of(s["run_id"]),
        "model": cfg["mode"].replace("llama-", ""),
        "rendering": cfg["process_rendering"],
        "reasoning_budget": cfg["reasoning_budget"],
        "temperature": cfg["temperature"],
        "runner_type": cfg["runner_type"],
        # execution
        "status": r["execution"]["status"],
        "stop_reason": r["execution"].get("stop_reason"),
        # outcomes — categorical
        "quality": qua.get("result"),
        # Lo `status` dell'oggetto restituito. Non e' un punteggio: e' cio' che il
        # modello ha dichiarato di aver fatto. Serve a distinguere una risposta
        # sbagliata da un rifiuto motivato di eseguire (INVALID_INPUT), che
        # l'oracolo conta come sbagliata ma non e' la stessa cosa.
        "payload_status": payload_status,
        "fidelity": fid.get("result"),
        "comprehension": com.get("result"),
        "degradation_mode": s.get("degradation_mode"),
        # outcomes — continuous (absent from the index)
        "quality_rate": qua.get("rate"),
        "comprehension_rate": com.get("rate"),
        "sequence_rate": fid.get("sequence_rate"),
        "conditional_rate": fid.get("conditional_rate"),
        "redundancy_ratio": fid.get("redundancy_ratio"),
        # sequence shape
        "expected_branch": fid.get("expected_branch"),
        "observed_branch": fid.get("observed_branch"),
        "n_expected_steps": len(exp_seq) if exp_seq is not None else None,
        "n_observed_steps": len(obs_seq) if obs_seq is not None else None,
        # cost
        "wall_clock_ms": eff.get("wall_clock_ms"),
        "tokens_in": eff.get("tokens_in"),
        "tokens_out": eff.get("tokens_out"),
    }


def build() -> pd.DataFrame:
    scores = sorted(RAW.rglob("*.score.json"))
    if not scores:
        raise FileNotFoundError(f"no .score.json under {RAW}")
    df = pd.DataFrame([_record(p) for p in scores])
    df["cell"] = df["fixture"] + "|" + df["input_id"] + "|" + df["model"] + "|" + df["rendering"]
    return df


if __name__ == "__main__":
    df = build()
    df.to_csv(OUT, index=False)
    print(f"{len(df)} runs -> {OUT.relative_to(REPO)}")
    print(f"{df['cell'].nunique()} cells, reps per cell: "
          f"{df.groupby('cell').size().value_counts().to_dict()}")
