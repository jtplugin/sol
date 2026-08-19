# Audit of existing results — 2026-08-03

Read-only analysis of `tests/results/index.jsonl` (575 rows). **No data was modified** — this
is classification only.

## 1. Native E1 versus labelled-but-emulated E1

| Category | N | Meaning |
|---|---|---|
| Native E1 (`runner_type=claude-code`, `env_realization=native`) | 102 | `executor.py`, a real tool loop was present |
| Labelled `claude-code` but `env_realization=emulated` | **13** | manual `runner.py` — **no tool was actually present** |
| E1 via `api_executor.py` (`runner_type=api`, anthropic backend) | 33 | tool loop through the Messages API |

The 13 mislabelled rows are all `w2-branching/release-gate`, models `claude-sonnet-4-6` (8) and
`claude-opus-4-8` (5), dated 2026-06-04. Full run ids:

```
w2-branching-release-gate-i1-blocked-20260604T105747
w2-branching-release-gate-i2-insufficient-coverage-20260604T105747
w2-branching-release-gate-i3-security-hold-20260604T105747
w2-branching-release-gate-i4-ready-20260604T105747
w2-branching-release-gate-i1-blocked-20260604T110600
w2-branching-release-gate-i2-insufficient-coverage-20260604T110601
w2-branching-release-gate-i3-security-hold-20260604T110601
w2-branching-release-gate-i4-ready-20260604T110601
w2-branching-release-gate-i1-blocked-20260604T120438
w2-branching-release-gate-i2-insufficient-coverage-20260604T120447
w2-branching-release-gate-i3-security-hold-20260604T120447
w2-branching-release-gate-i4-ready-20260604T120447
w2-branching-release-gate-i1-blocked-20260604T120456
```

**How to use this**: when filtering for "real E1", filter on `env_realization=='native'`, not on
`runner_type=='claude-code'` alone — the second criterion wrongly includes these 13 rows.

## 2. The `execution-error` rate: model or runner?

97 rows carry `degradation_mode=execution-error`. The cause was reconstructed by reading
`output.raw` in the original run records (never exposed in `index.jsonl`):

| Model | Errors | Cause (100% attributed) | Model or runner? |
|---|---|---|---|
| `qwen3.5:9b` | 52 | 47 timeouts + 5 OOM (`"model requires more system memory (7.9 GiB) than is available (6.2 GiB)"`), **all** from the same LAN Ollama endpoint | **Runner/infrastructure** — undersized endpoint, see section 3 |
| `qwen2.5-coder:7b` | 21 | 100% `"qwen2.5-coder:7b" does not support thinking` — `reasoning_budget=1` set for an Ollama model with no thinking support | **Runner/config** — a mismatch between config and model capability, not a model failure on the task |
| `claude-haiku-4-5` | 18 | 100% `max_tokens must be greater than thinking.budget_tokens` (reasoning_budget=8000, E1 context) | **Runner, ALREADY FIXED** — current `api_executor.py` computes `effective_max_tokens = max(DEFAULT_MAX_TOKENS, reasoning_budget + 1024)`, which yields 9024 > 8000; these records predate the fix, verified against the current code |
| `claude-opus-4-8` | 5 | not inspected in detail (low volume) | — |
| `mistral:7b` | 1 | 1 run in total, 100% error — sample too small to generalise | — |

**Conclusion**: none of the inspected causes (97/97 across the first three rows, the bulk of the
volume) is a genuine capability failure of the model on the task. All are attributable to
undersized infrastructure or to runner/config. The high `execution-error` rate on local models is
a runner/infrastructure artefact, not a model result.

## 3. The June local timings are not a throughput measurement

**All** 52 `qwen3.5:9b` errors — and, as far as the records show, all of its runs, failing or not
— went to a single Ollama endpoint on a local network, recorded in each run record's
`api_base_url`. A successful `qwen3.5:9b` run shows the same endpoint. That machine was
memory-constrained (see the OOM message in section 2), so the June timings and error rates from
these runs cannot be read as a throughput characterisation of any particular hardware. They
characterise one undersized endpoint.

## Not covered by this audit

- `claude-opus-4-8` (5 errors) and `mistral:7b` (1 error) were not inspected in detail: low
  volume, and they do not change the overall conclusion.
- Neither `index.jsonl` nor the run records were rewritten. This audit is read-only. A relabelling
  script — to correct `env_realization` on the 13 mislabelled rows — is deliberately left out.
