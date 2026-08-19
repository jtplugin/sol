"""Run-record and score-record data structures. Stdlib only, no dependencies."""
from __future__ import annotations
import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Run-record  (written by the runner, one per execution)
# ---------------------------------------------------------------------------

@dataclass
class Config:
    fixture_id: str
    context: str            # E0 | E1 | E2 | E2+
    model_id: str
    spec_version: str = "0.6"
    sol_variant: str = "standard"
    interactive: bool = False
    env_realization: str = "emulated"   # native | emulated
    predictability_layers: list = field(default_factory=list)
    runner_type: str = "claude-code"    # "claude-code" | "api"
    api_base_url: Optional[str] = None  # set only for runner_type="api"
    backend: str = "anthropic"          # "anthropic" | "ollama" | "openai" (runner_type="api")
    reasoning_budget: int = 0           # 0 = off; >0 = thinking tokens (api) / budget (claude-code)
    temperature: Optional[float] = None  # sampling temperature actually used; None = provider default
    thinking: Optional[bool] = None     # openai backend chat_template_kwargs.enable_thinking; None = not set
    ctx_size: Optional[int] = None      # cell metadata: llama-server --ctx-size used for this run
    kv_cache_type: Optional[str] = None  # cell metadata: llama-server --cache-type-k/v used for this run
    n_parallel: Optional[int] = None    # cell metadata: llama-server -np used for this run


@dataclass
class Execution:
    status: str             # done | error | timeout | connection-error | na
    wall_clock_ms: Optional[int] = None
    na_reason: Optional[str] = None
    error_detail: Optional[str] = None


@dataclass
class Trace:
    """Captured execution trace. Fields absent from the context are left empty."""
    steps: list = field(default_factory=list)           # "[case][agent] action" spine
    tool_calls: list = field(default_factory=list)      # E1+
    boundaries: list = field(default_factory=list)      # E2+: SPAWN with/returns payloads
    per_call_model: list = field(default_factory=list)  # where env exposes it
    request_messages: list = field(default_factory=list)  # messages sent to API


@dataclass
class Output:
    raw: str = ""
    returned_payload: Optional[Any] = None


@dataclass
class Usage:
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost: Optional[float] = None
    sub_agent_count: Optional[int] = None


@dataclass
class RunRecord:
    run_id: str
    timestamp: str
    config: Config
    staged_input_id: str
    execution: Execution
    trace: Trace
    output: Output
    usage: Usage

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> RunRecord:
        return cls(
            run_id=d["run_id"],
            timestamp=d["timestamp"],
            config=Config(**d["config"]),
            staged_input_id=d["staged_input_id"],
            execution=Execution(**d["execution"]),
            trace=Trace(**d["trace"]),
            output=Output(**d["output"]),
            usage=Usage(**d["usage"]),
        )

    def save(self, path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path) -> RunRecord:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Score-record  (written by the checker, one per run-record)
# ---------------------------------------------------------------------------

@dataclass
class FidelityCheck:
    result: str                         # pass | fail | not_checkable
    expected_branch: Optional[str] = None
    observed_branch: Optional[str] = None
    # Sequence-oracle fields (W2 state-accumulation fixtures, e.g. support-intake).
    # Populated only when the expectations case carries `expected_sequence`;
    # single-branch fixtures (release-gate, task-router) leave these None and
    # are scored exactly as before via expected_branch/observed_branch above.
    sequence_rate: Optional[float] = None                    # rate vs ground-truth sequence
    # Two-metric sequence oracle: sequence_rate's denominator is
    # max(len(expected), len(observed)) -- a run that never halts (loops past
    # the expected end) no longer scores an inflated rate just because the
    # comparison window was capped at len(expected). redundancy_ratio =
    # len(observed)/len(expected) reads alongside it: rate low + ratio ~=1 ->
    # wrong actions taken at the right cadence; rate low + ratio high -> loop
    # (no-halt); rate low + ratio <1 -> stopped early. None if expected_sequence
    # is empty (division guard, mirrors the `rate` guard above).
    redundancy_ratio: Optional[float] = None
    expected_sequence: Optional[list] = None
    observed_sequence: Optional[list] = None
    # Conditional fidelity: rate vs the sequence reference.run_queue() would
    # produce using the MODEL's OWN classifications (not ground truth) --
    # isolates pure control-flow correctness from comprehension errors.
    conditional_rate: Optional[float] = None
    conditional_expected_sequence: Optional[list] = None
    conditional_observed_sequence: Optional[list] = None


@dataclass
class QualityCheck:
    result: str                         # pass | fail | not_checkable
    expected: Optional[Any] = None
    got: Optional[Any] = None
    rate: Optional[float] = None        # set for rate-based checks (e.g. comprehension)


@dataclass
class EfficiencyRecord:
    wall_clock_ms: Optional[int] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost: Optional[float] = None


@dataclass
class ScoreRecord:
    run_id: str
    fixture_id: str
    staged_input_id: str
    context: str
    model_id: str
    fidelity: FidelityCheck
    quality: QualityCheck
    efficiency: EfficiencyRecord
    # Categorical: none | wrong-value | no-output | refused |
    #              garbled-output | execution-error | timeout | connection-error | na |
    #              partial-sequence | no-halt | budget-drift
    degradation_mode: str
    # Domain comprehension (product+intent vs ground truth), independent of
    # SOL control-flow. None for fixtures without a comprehension oracle.
    comprehension: Optional[QualityCheck] = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def save(self, path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
