# Flakiness Report - AI Chatbot UI Suite

Generated (from 2026-09-27 16:03 runs): 2026-09-27 12:07  
Suite: `tests/test_chatbot_ui.py` (5 tests) x 5 runs  
Target: HuggingChat (https://huggingface.co/chat/)

## Run summary

| Run | Passed | Failed | Notes |
|---|---|---|---|
| 1 | 5 | 0 | All green (61.5 s) |
| 2 | 4 | 1 | scope_refusal_out_of_scope_request[chromium]: TimeoutError: Assistant answer did not stabilise within 120s |
| 3 | 4 | 1 | scope_refusal_out_of_scope_request[chromium]: TimeoutError: Assistant answer did not stabilise within 120s |
| 4 | 4 | 1 | scope_refusal_out_of_scope_request[chromium]: TimeoutError: Assistant answer did not stabilise within 120s |
| 5 | 5 | 0 | All green (65.2 s) |

## Per-test results

| Test | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Pass rate |
|---|---|---|---|---|---|---|
| test_empty_input_is_not_submitted[chromium] | PASS | PASS | PASS | PASS | PASS | 100% |
| test_hallucination_trap_fictional_fact[chromium] | PASS | PASS | PASS | PASS | PASS | 100% |
| test_happy_path_normal_question[chromium] | PASS | PASS | PASS | PASS | PASS | 100% |
| test_long_input_is_handled[chromium] | PASS | PASS | PASS | PASS | PASS | 100% |
| test_scope_refusal_out_of_scope_request[chromium] | PASS | FAIL | FAIL | FAIL | PASS | 40% |

## Flaky tests

### test_scope_refusal_out_of_scope_request[chromium] - FLAKY (intermittent)

**Failure message(s):**
- `TimeoutError: Assistant answer did not stabilise within 120s`

**Why it failed (likely cause):** Synchronisation / empty response, not wording: generation finished ('Stop generating' disappeared) but no final answer text was rendered in the bubble (empty reply, or only a reasoning/status element), so the wait-for-stable-text step polled until the timeout. The auto-router may pick a different (e.g. reasoning) model for a sensitive banking prompt, which explains why it happens only in some runs.

**How to make it stable:** Fail fast when streaming ends with an empty answer (added: 15 s grace period with a clear error), retry the prompt once on an empty/infrastructure response, pin a specific model via BASE_URL instead of the auto-router, and keep per-run traces (test-results/run_<n>) to confirm what was on screen.

_Evidence: see `reports/run_<n>.html` (chatbot answer is attached to each test) and the trace/video in `test-results/` - open a trace with `playwright show-trace <trace.zip>`._


## General stabilisation strategies for LLM UI tests

1. **Wait on app state, not time** - wait for the stop button to disappear and the text to stop changing, never `sleep`.
2. **Assert behaviour, not exact text** - keywords/regex for facts, and an LLM judge (DeepEval GEval / relevancy) for refusals and hallucinations.
3. **Reduce randomness** - pin one model (not the auto router), use temperature 0 / a fixed system prompt where the app allows it.
4. **Isolate tests** - fresh conversation per test, saved login state instead of logging in each time.
5. **Statistical assertions** - for truly non-deterministic checks run k times and require e.g. >= 80% pass rate.
6. **Retry only infrastructure errors** (429/5xx, network), never assertion failures, so real regressions stay visible.
