# Error-path fixtures

Cross-cutting family: inject a failure — a failing `RUN`, a malformed sub-agent return, an
off-contract payload — and assert the defined error behavior fired.

**Oracle:** `ONERROR` ran on the injected failure / `HALT` stopped cleanly where expected; the
process did not silently proceed on the happy path. **Path made knowable:** the failure is
injected deterministically, so the error branch is the only correct continuation.

_No fixture authored yet._
