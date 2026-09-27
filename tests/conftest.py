import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from pages.chat_page import ChatPage  # noqa: E402

STATE_FILE = ROOT / "auth" / "storage_state.json"
(ROOT / "reports").mkdir(exist_ok=True)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Re-use the saved HuggingChat login for every test."""
    args = {**browser_context_args, "viewport": {"width": 1366, "height": 900}}
    if STATE_FILE.exists():
        args["storage_state"] = str(STATE_FILE)
    elif "huggingface.co" in os.getenv("BASE_URL", "https://huggingface.co/chat/"):
        pytest.exit("auth/storage_state.json not found - run `python auth_setup.py` first.", returncode=2)
    return args


@pytest.fixture
def chat(page) -> ChatPage:
    """A fresh, empty conversation for each test (tests never share chat history)."""
    page.set_default_timeout(30_000)
    return ChatPage(page).open()


# ---- attach the chatbot's answer to the HTML report -------------------------
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    answer = getattr(item, "chatbot_answer", None)
    if report.when == "call" and answer is not None:
        report.sections.append(("Chatbot answer", answer[:3000]))


@pytest.fixture
def record_answer(request):
    def _record(prompt: str, answer: str):
        request.node.chatbot_answer = f"PROMPT:\n{prompt[:500]}\n\nANSWER:\n{answer}"
        print(f"\n--- PROMPT ---\n{prompt[:300]}\n--- ANSWER ---\n{answer}\n")
    return _record
