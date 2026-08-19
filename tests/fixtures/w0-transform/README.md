# W0 — Self-contained transform fixtures

All input is inline in the prompt; the process produces a response with no tools. Exercises
`TODO`, `IF`/`WHEN`, `returns`. Runnable even on **E0** (model only), which makes this class the
best for isolating *model* quality with minimal environment noise.

**Oracle:** a checkable property of the output (valid JSON, every input row classified, schema
satisfied). **Path made knowable:** inline input built so only one outcome is correct.

_No fixture authored yet._
