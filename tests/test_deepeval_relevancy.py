"""Task 2 - Hybrid UI + AI evaluation.

Playwright drives the chatbot UI -> the answer is captured from the page ->
DeepEval's AnswerRelevancyMetric scores it with an LLM judge (OpenAI) ->
the result is printed, saved as JSON, and rendered as an HTML card that is
screenshotted to reports/deepeval_result.png.
"""

import html
import json
import os
from datetime import datetime
from pathlib import Path

import pytest
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

pytestmark = pytest.mark.ai_eval

REPORTS = Path(__file__).resolve().parents[1] / "reports"
QUESTION = "What are three tips for writing reliable automated UI tests?"
THRESHOLD = 0.7


def render_result_card(page, data: dict, path: Path):
    ok = data["passed"]
    color = "#15803d" if ok else "#b91c1c"
    page.set_content(f"""
    <html><body style="font-family:Segoe UI,Arial;background:#f6f7f9;padding:32px">
      <div style="max-width:900px;margin:auto;background:#fff;border-radius:12px;padding:28px;
                  box-shadow:0 2px 10px rgba(0,0,0,.08)">
        <h2 style="margin-top:0">DeepEval &middot; Answer Relevancy</h2>
        <p style="color:#666">Chatbot: {html.escape(data['chatbot'])} &middot; Judge: {html.escape(data['judge_model'])}
           &middot; {data['timestamp']}</p>
        <div style="display:flex;gap:16px;margin:20px 0">
          <div style="flex:1;border:1px solid #eee;border-radius:10px;padding:16px">
            <div style="color:#666">Score</div><div style="font-size:40px;font-weight:700">{data['score']:.2f}</div></div>
          <div style="flex:1;border:1px solid #eee;border-radius:10px;padding:16px">
            <div style="color:#666">Threshold</div><div style="font-size:40px;font-weight:700">{data['threshold']}</div></div>
          <div style="flex:1;border:1px solid #eee;border-radius:10px;padding:16px">
            <div style="color:#666">Result</div>
            <div style="font-size:40px;font-weight:700;color:{color}">{'PASS' if ok else 'FAIL'}</div></div>
        </div>
        <h3>Input (sent through the UI)</h3><p>{html.escape(data['input'])}</p>
        <h3>Actual output (captured from the UI)</h3>
        <pre style="white-space:pre-wrap;background:#f6f7f9;padding:12px;border-radius:8px">{html.escape(data['actual_output'][:2500])}</pre>
        <h3>Judge's reason</h3><p>{html.escape(data['reason'] or '')}</p>
      </div></body></html>""")
    page.screenshot(path=str(path), full_page=True)


def test_ui_answer_relevancy_with_deepeval(chat, page, record_answer):
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set (add it to .env)")

    # 1-2) run the chatbot through the UI and capture its answer
    answer = chat.ask(QUESTION)
    record_answer(QUESTION, answer)
    page.screenshot(path=str(REPORTS / "deepeval_chat_ui.png"), full_page=True)

    # 3-4) pass the captured answer to DeepEval and evaluate relevancy
    judge = os.getenv("DEEPEVAL_MODEL", "gpt-4o-mini")
    metric = AnswerRelevancyMetric(threshold=THRESHOLD, model=judge, include_reason=True)
    test_case = LLMTestCase(input=QUESTION, actual_output=answer)
    metric.measure(test_case)

    # 5) display the evaluation result
    result = {
        "chatbot": os.getenv("BASE_URL", "https://huggingface.co/chat/"),
        "judge_model": judge,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input": QUESTION,
        "actual_output": answer,
        "metric": "AnswerRelevancyMetric",
        "score": float(metric.score),
        "threshold": THRESHOLD,
        "passed": bool(metric.is_successful()),
        "reason": metric.reason,
    }
    print("\n========== DeepEval result ==========")
    print(f"Metric    : {result['metric']}")
    print(f"Score     : {result['score']:.2f} (threshold {THRESHOLD})")
    print(f"Result    : {'PASS' if result['passed'] else 'FAIL'}")
    print(f"Reason    : {result['reason']}")
    print("=====================================")

    (REPORTS / "deepeval_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    render_result_card(page, result, REPORTS / "deepeval_result.png")

    assert metric.is_successful(), f"Relevancy {metric.score:.2f} < {THRESHOLD}: {metric.reason}"
