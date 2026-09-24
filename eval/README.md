# eval/

Release-gate eval harness (Phase 8, `docs/EVALUATION.md`). Cases live in `cases/`:

| File | Gate | Runner |
|---|---|---|
| `birth-normalization.json` | A — normalizer boundary corpus | `tests/test_eval_gates.py::TestGateA` |
| `chart-regression.json` | B — CI tier (frozen expected values from x-iztro 0.6.1 + canonical DTO) | `TestGateB` |
| `grounding.json` | C — zero-tolerance grounding violations | `TestGateC` |
| `topic-routing.json` | D — ContextComposer routing | `TestGateD` |
| `interpretation.json` | E — rubric/bait corpus (schema-checked here) | `TestGateE` + model benchmark harness |

Run: `cd apps/api && uv run pytest tests/test_eval_gates.py` (CI runs it in the api test step).

Gate B's second tier — JS `iztro` differential oracle (`scripts/differential/`) — runs nightly, not in CI; classified school/config differences are waived explicitly, never counted as bugs. Gate E scoring is the 20–30 charts × 5 topics benchmark over `AI_BASE_URL` candidates; this corpus carries the rubric + safety/injection baits.
