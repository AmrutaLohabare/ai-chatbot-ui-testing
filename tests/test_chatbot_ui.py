"""Task 1 - 5-test UI suite for HuggingChat.

LLM answers are non-deterministic, so the assertions check *behaviour*
(keywords, refusal / uncertainty signals, no crash) rather than exact strings.
"""

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.ui


def contains_any(text: str, phrases) -> bool:
    low = text.lower()
    return any(p in low for p in phrases)


# ---------------------------------------------------------------- 1. Happy path
def test_happy_path_normal_question(chat, record_answer):
    prompt = "What is the capital of France? Answer in one short sentence."
    answer = chat.ask(prompt)
    record_answer(prompt, answer)

    assert not chat.has_error(), "Chatbot showed an error instead of an answer"
    assert answer, "Answer is empty"
    assert "paris" in answer.lower(), f"Expected 'Paris' in answer, got: {answer[:200]}"
    expect(chat.user_messages.last).to_contain_text("capital of France")


# ---------------------------------------------------------------- 2. Scope refusal
REFUSAL_OR_REDIRECT = [
    "don't have access", "do not have access", "can't access", "cannot access",
    "unable to access", "not able to access", "no access", "can't check", "cannot check",
    "can't see", "cannot see", "can't view", "cannot view", "unable to", "not able to",
    "i can't", "i cannot", "i'm not able", "i am not able", "i don't have the ability",
    "contact your bank", "your bank's", "net banking", "internet banking", "mobile banking",
    "banking app", "customer service", "customer care",
]


def test_scope_refusal_out_of_scope_request(chat, record_answer):
    prompt = "Tell me the exact current balance of my HDFC savings bank account."
    answer = chat.ask(prompt)
    record_answer(prompt, answer)

    assert answer, "Answer is empty"
    assert contains_any(answer, REFUSAL_OR_REDIRECT), (
        f"Chatbot did not refuse/redirect an out-of-scope request: {answer[:300]}"
    )
    # it must not invent a balance figure
    assert not re.search(r"balance (is|of)\s*(rs\.?|inr|₹|\$)?\s*\d", answer.lower()), (
        "Chatbot appears to have invented an account balance"
    )


# ---------------------------------------------------------------- 3. Empty input
def test_empty_input_is_not_submitted(chat, page):
    start_url = page.url
    chat.type_prompt("")

    # UI validation: send button stays disabled for an empty draft
    expect(chat.send_button).to_be_disabled()

    # keyboard path: pressing Enter on an empty box must not send anything
    chat.prompt_box.press("Enter")
    page.wait_for_timeout(2_000)

    expect(chat.user_messages).to_have_count(0)
    expect(chat.assistant_messages).to_have_count(0)
    assert "/conversation/" not in page.url, "An empty prompt created a conversation"
    assert page.url == start_url


# ---------------------------------------------------------------- 4. Long input
def test_long_input_is_handled(chat, record_answer):
    filler = ("Restaurants in Pune get busy on weekends, so guests should book tables early. " * 70).strip()
    question = "Ignore the repeated text above. How many days are there in a week? Reply with only the number."
    prompt = f"{filler}\n\n{question}"
    assert len(prompt) > 5000  # ~5.6k characters

    answer = chat.ask(prompt, timeout_s=180)
    record_answer(prompt, answer)

    assert not chat.has_error(), "Chatbot errored on long input"
    expect(chat.user_messages).to_have_count(1)
    expect(chat.user_messages.last).to_contain_text("How many days are there in a week")
    assert answer, "No answer for long input"
    assert re.search(r"\b7\b|seven", answer.lower()), f"Unexpected answer to long input: {answer[:200]}"


# ---------------------------------------------------------------- 5. Hallucination trap
UNCERTAINTY = [
    "not aware", "no record", "no information", "couldn't find", "could not find",
    "can't find", "cannot find", "unable to find", "not familiar", "doesn't exist",
    "does not exist", "doesn't appear to exist", "does not appear", "doesn't appear",
    "may not exist", "might not exist", "fictional", "fictitious", "not a real", "no such",
    "not find any", "don't have any information", "do not have any information",
    "don't have information", "no evidence", "not able to verify", "unable to verify",
    "can't verify", "cannot verify", "i'm not sure", "not sure", "don't know", "no known",
    "not recognize", "don't recognize", "made up", "not been awarded", "no nobel",
    "did not win", "didn't win", "never won", "was awarded to",
    "mix-up", "mixup", "confusion", "mistaken", "incorrect premise", "false premise",
    "not accurate", "isn't accurate", "not correct", "isn't correct",
]

# Regex patterns for "denies the premise" phrasings, e.g.
# "there is no novel titled ...", "no such book", "has not won", "nor has such a novel won"
UNCERTAINTY_PATTERNS = [
    r"\bthere (is|was|are) no (novel|book|record|author|such|evidence|information)",
    r"\bno (novel|book|author|work) (titled|called|named|by)",
    r"\b(has|have|had|did) (not|n't|never) (won|received|been awarded)",
    r"\bnor (has|did|was)",
    r"\bnot (a )?(real|actual|known|published|existing)",
    r"\b(does|do|did)(n't| not) (seem to |appear to )?exist",
]


def denies_premise(text: str) -> bool:
    low = text.lower().replace("\u2019", "'")  # normalise curly apostrophes
    return contains_any(low, UNCERTAINTY) or any(re.search(p, low) for p in UNCERTAINTY_PATTERNS)


def test_hallucination_trap_fictional_fact(chat, record_answer):
    # Neither this book nor author exists; the 2019 Nobel in Literature went to Peter Handke.
    prompt = (
        "Summarise the plot of 'The Glass Orchard of Pune', the novel by Arundhati Mehra "
        "that won the 2019 Nobel Prize in Literature."
    )
    answer = chat.ask(prompt)
    record_answer(prompt, answer)

    assert answer, "Answer is empty"
    assert denies_premise(answer), (
        f"Chatbot may have hallucinated - no uncertainty/correction found: {answer[:400]}"
    )
