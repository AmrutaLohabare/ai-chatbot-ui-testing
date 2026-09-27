"""Task 3 - run the UI suite N times and build a flakiness report.

    python scripts/run_flakiness.py            # 5 runs (default)
    python scripts/run_flakiness.py --runs 3

Outputs (in reports/):
    run_<n>.xml / run_<n>.html   - JUnit + HTML report per run
    flakiness_results.json        - raw per-test results
    flakiness_report.md           - run table, per-test matrix, flaky tests
"""

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

# Why each test *could* be flaky and how to stabilise it - used in the report
# only for tests that actually turned out flaky or failing.
KNOWN_CAUSES = {
    "test_happy_path_normal_question": (
        "Slow model / router picking a different model; answer occasionally rendered late.",
        "Wait for 'Stop generating' to hide + text stability (already done); raise RESPONSE_TIMEOUT; "
        "pin a specific model URL instead of the Omni router.",
    ),
    "test_scope_refusal_out_of_scope_request": (
        "Non-deterministic wording: the model sometimes redirects with phrasing not in the keyword list "
        "(e.g. 'check via your bank's app' or 'I'm just an AI').",
        "Replace keyword matching with an LLM-as-judge check (DeepEval GEval 'Did the assistant decline "
        "and redirect?'), or pin model + temperature 0 via a system prompt; keep the keyword list as a fast pre-check.",
    ),
    "test_empty_input_is_not_submitted": (
        "Rarely flaky - only if the page was not fully hydrated when Enter was pressed.",
        "Wait for the prompt box to be visible and enabled before interacting (already done).",
    ),
    "test_long_input_is_handled": (
        "Long prompts take longer to process; timeouts or rate limits (HTTP 429) on the free tier.",
        "Use a larger timeout for this test (180 s), add a retry for 429/5xx, run it last/serially.",
    ),
    "test_hallucination_trap_fictional_fact": (
        "False negative from the test oracle, not the chatbot: the model correctly rejected the premise but used "
        "wording the keyword list did not cover (seen in practice: 'There seems to be a mix-up... there is no novel "
        "titled ...'). The captured text also contained UI labels ('via ovhcloud', 'Copied').",
        "Assert with DeepEval HallucinationMetric / GEval against the context 'this book does not exist', "
        "run each prompt N times and use a pass-rate threshold, pin model and disable tools.",
    ),
}


TIMEOUT_CAUSE = (
    "Synchronisation / empty response, not wording: generation finished ('Stop generating' disappeared) but no "
    "final answer text was rendered in the bubble (empty reply, or only a reasoning/status element), so the "
    "wait-for-stable-text step polled until the timeout. The auto-router may pick a different (e.g. reasoning) "
    "model for a sensitive banking prompt, which explains why it happens only in some runs.",
    "Fail fast when streaming ends with an empty answer (added: 15 s grace period with a clear error), retry the "
    "prompt once on an empty/infrastructure response, pin a specific model via BASE_URL instead of the auto-router, "
    "and keep per-run traces (test-results/run_<n>) to confirm what was on screen.",
)


def run_once(i: int) -> dict:
    xml = REPORTS / f"run_{i}.xml"
    cmd = [sys.executable, "-m", "pytest", "tests/test_chatbot_ui.py",
           f"--junitxml={xml}", f"--html={REPORTS / f'run_{i}.html'}", "--self-contained-html", "-q",
           f"--output=test-results/run_{i}"]  # keep each run's screenshots/traces (not overwritten)
    print(f"\n===== Run {i} =====\n{' '.join(cmd)}")
    started = datetime.now()
    subprocess.run(cmd, cwd=ROOT)
    duration = (datetime.now() - started).total_seconds()

    results = {}
    if xml.exists():
        for case in ET.parse(xml).getroot().iter("testcase"):
            name = case.get("name")
            failure = case.find("failure") if case.find("failure") is not None else case.find("error")
            skipped = case.find("skipped")
            if failure is not None:
                msg = (failure.get("message") or "").splitlines()[0][:160]
                results[name] = {"status": "failed", "message": msg}
            elif skipped is not None:
                results[name] = {"status": "skipped", "message": skipped.get("message", "")}
            else:
                results[name] = {"status": "passed", "message": ""}
    return {"run": i, "duration_s": round(duration, 1), "tests": results}


def build_report(runs: list) -> str:
    tests = sorted({t for r in runs for t in r["tests"]})
    lines = [
        "# Flakiness Report - AI Chatbot UI Suite",
        "",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M}  ",
        f"Suite: `tests/test_chatbot_ui.py` ({len(tests)} tests) x {len(runs)} runs  ",
        "Target: HuggingChat (https://huggingface.co/chat/)",
        "",
        "## Run summary",
        "",
        "| Run | Passed | Failed | Notes |",
        "|---|---|---|---|",
    ]
    for r in runs:
        passed = sum(1 for v in r["tests"].values() if v["status"] == "passed")
        failed = sum(1 for v in r["tests"].values() if v["status"] == "failed")
        fails = [f"{n.replace('test_', '')}: {v['message']}" for n, v in r["tests"].items() if v["status"] == "failed"]
        notes = "; ".join(fails) if fails else f"All green ({r['duration_s']} s)"
        lines.append(f"| {r['run']} | {passed} | {failed} | {notes.replace('|', '/')} |")

    lines += ["", "## Per-test results", "", "| Test | " + " | ".join(f"Run {r['run']}" for r in runs) + " | Pass rate |",
              "|---|" + "---|" * (len(runs) + 1)]
    flaky, broken = [], []
    for t in tests:
        statuses = [r["tests"].get(t, {}).get("status", "-") for r in runs]
        cells = ["PASS" if s == "passed" else "FAIL" if s == "failed" else s.upper() for s in statuses]
        rate = statuses.count("passed") / len(statuses)
        lines.append(f"| {t} | " + " | ".join(cells) + f" | {rate:.0%} |")
        if "passed" in statuses and "failed" in statuses:
            flaky.append(t)
        elif statuses and all(s == "failed" for s in statuses):
            broken.append(t)

    lines += ["", "## Flaky tests", ""]
    if not flaky:
        lines.append("No test failed intermittently - every test gave the same result in all runs.")
    for t in flaky + broken:
        kind = "FLAKY (intermittent)" if t in flaky else "CONSISTENTLY FAILING (not flaky - a real/assertion issue)"
        msgs = sorted({r["tests"][t]["message"] for r in runs if r["tests"].get(t, {}).get("status") == "failed"})
        if any("stabilise" in m or "NO answer text" in m or "Timeout" in m for m in msgs):
            cause, fix = TIMEOUT_CAUSE
        else:
            cause, fix = KNOWN_CAUSES.get(t.split("[")[0], ("See failure message / trace.", "Investigate trace in test-results/."))
        lines += [
            f"### {t} - {kind}",
            "",
            "**Failure message(s):**",
            *[f"- `{m}`" for m in msgs],
            "",
            f"**Why it failed (likely cause):** {cause}",
            "",
            f"**How to make it stable:** {fix}",
            "",
            "_Evidence: see `reports/run_<n>.html` (chatbot answer is attached to each test) and the "
            "trace/video in `test-results/` - open a trace with `playwright show-trace <trace.zip>`._",
            "",
        ]

    lines += [
        "",
        "## General stabilisation strategies for LLM UI tests",
        "",
        "1. **Wait on app state, not time** - wait for the stop button to disappear and the text to stop changing, never `sleep`.",
        "2. **Assert behaviour, not exact text** - keywords/regex for facts, and an LLM judge (DeepEval GEval / relevancy) for refusals and hallucinations.",
        "3. **Reduce randomness** - pin one model (not the auto router), use temperature 0 / a fixed system prompt where the app allows it.",
        "4. **Isolate tests** - fresh conversation per test, saved login state instead of logging in each time.",
        "5. **Statistical assertions** - for truly non-deterministic checks run k times and require e.g. >= 80% pass rate.",
        "6. **Retry only infrastructure errors** (429/5xx, network), never assertion failures, so real regressions stay visible.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    REPORTS.mkdir(exist_ok=True)

    runs = [run_once(i) for i in range(1, args.runs + 1)]
    (REPORTS / "flakiness_results.json").write_text(json.dumps(runs, indent=2), encoding="utf-8")
    report = build_report(runs)
    (REPORTS / "flakiness_report.md").write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"Report written to {REPORTS / 'flakiness_report.md'}")


if __name__ == "__main__":
    main()
