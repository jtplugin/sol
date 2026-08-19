# W3 — Multi-agent orchestration fixtures

Isolated agents, contracts, model tiers. Adds `AGENT`/`SPAWN`/`DELEGATE`, `model`,
`accepts`/`returns`. Only meaningful on **E2 / E2+** — on E0/E1 a `SPAWN` collapses to in-context
role-play, which is itself an informative (expected-failure) matrix cell.

**Oracles:** isolation held (the sub-agent saw only the `with`), `accepts` satisfied, `returns`
shape correct, declared model tier used. **Path made knowable:** per-call trace plus the
contract payloads crossing each boundary.

_No fixture authored yet._
