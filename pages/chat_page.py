"""Page Object for HuggingChat (https://huggingface.co/chat/).

Selectors come from the open-source HuggingChat UI (github.com/huggingface/chat-ui):
  - prompt box:        <textarea placeholder="Ask anything">
  - send button:       <button name="submit" aria-label="Send message">  (disabled while the draft is empty)
  - stop button:       aria-label="Stop generating"                      (visible while the answer streams)
  - user message:      [data-message-type="user"]
  - assistant message: [data-message-role="assistant"]
  - reasoning / tool blocks inside an answer are marked [data-exclude-from-copy]
"""

import os
import time

from playwright.sync_api import Page, expect

BASE_URL = os.getenv("BASE_URL", "https://huggingface.co/chat/")
RESPONSE_TIMEOUT_S = int(os.getenv("RESPONSE_TIMEOUT", "120"))


class ChatPage:
    PROMPT_BOX = "textarea"
    SEND_BUTTON = 'button[name="submit"]'
    STOP_BUTTON = 'button[aria-label="Stop generating"]'
    USER_MSG = '[data-message-type="user"]'
    ASSISTANT_MSG = '[data-message-role="assistant"]'
    ERROR_TEXT = "Sorry, something went wrong"

    def __init__(self, page: Page):
        self.page = page

    # ---------- navigation ----------
    def open(self):
        """Open a fresh chat and make sure we are logged in."""
        self.page.goto(BASE_URL, wait_until="domcontentloaded")
        if "/login" in self.page.url:
            raise RuntimeError(
                "Not logged in to HuggingChat. Run `python auth_setup.py` once to save your session."
            )
        expect(self.prompt_box).to_be_visible(timeout=30_000)
        return self

    # ---------- locators ----------
    @property
    def prompt_box(self):
        return self.page.locator(self.PROMPT_BOX).first

    @property
    def send_button(self):
        return self.page.locator(self.SEND_BUTTON)

    @property
    def stop_button(self):
        return self.page.locator(self.STOP_BUTTON)

    @property
    def user_messages(self):
        return self.page.locator(self.USER_MSG)

    @property
    def assistant_messages(self):
        return self.page.locator(self.ASSISTANT_MSG)

    # ---------- actions ----------
    def type_prompt(self, text: str):
        # fill() sets the value directly (no clipboard paste), so very long text
        # is NOT converted into a file attachment by HuggingChat's paste handler.
        self.prompt_box.fill(text)

    def send(self):
        self.send_button.click()

    def ask(self, prompt: str, timeout_s: int = RESPONSE_TIMEOUT_S) -> str:
        """Send a prompt and return the final (fully streamed) assistant answer."""
        before = self.assistant_messages.count()
        self.type_prompt(prompt)
        expect(self.send_button).to_be_enabled(timeout=10_000)
        self.send()
        return self.wait_for_answer(before, timeout_s)

    def wait_for_answer(self, previous_count: int, timeout_s: int = RESPONSE_TIMEOUT_S) -> str:
        deadline = time.time() + timeout_s

        # 1) a new assistant bubble appears
        expect(self.assistant_messages).to_have_count(previous_count + 1, timeout=timeout_s * 1000)

        # 2) streaming finished -> "Stop generating" disappears
        remaining_ms = max(1_000, int((deadline - time.time()) * 1000))
        expect(self.stop_button).to_be_hidden(timeout=remaining_ms)

        # 3) text is stable for 2 seconds (guards against late re-renders)
        # If streaming has ended but no answer text shows up within EMPTY_GRACE_S,
        # fail fast with a clear message instead of polling until the full timeout.
        EMPTY_GRACE_S = 15
        finished_at = time.time()
        last_text, stable_since = None, time.time()
        while time.time() < deadline:
            text = self.last_answer_text()
            if text and text == last_text:
                if time.time() - stable_since >= 2:
                    return text
            else:
                last_text, stable_since = text, time.time()
            if not text and time.time() - finished_at > EMPTY_GRACE_S:
                raw = self.assistant_messages.last.inner_text()[:500]
                raise AssertionError(
                    "Chatbot finished generating but rendered NO answer text "
                    f"(empty response or reasoning-only). Raw bubble text: {raw!r}"
                )
            self.page.wait_for_timeout(500)
        raise TimeoutError(
            f"Assistant answer did not stabilise within {timeout_s}s. Last text: {(last_text or '')[:300]!r}"
        )

    def last_answer_text(self) -> str:
        """Visible answer text of the latest assistant message, without reasoning/tool blocks."""
        last = self.assistant_messages.last
        return last.evaluate(
            """el => {
                // Preferred: only the rendered answer blocks (.prose), skipping reasoning/tool blocks.
                // This drops UI chrome such as the "via <provider>" label and the "Copied" tooltip.
                const blocks = [...el.querySelectorAll('.prose')]
                    .filter(n => !n.closest('[data-exclude-from-copy]'));
                if (blocks.length) {
                    return blocks.map(n => n.innerText.trim()).filter(Boolean).join('\\n\\n');
                }
                // Fallback: whole bubble minus excluded blocks
                let text = el.innerText || '';
                el.querySelectorAll('[data-exclude-from-copy]').forEach(n => {
                    const t = n.innerText || '';
                    if (t) text = text.replace(t, '');
                });
                return text.trim();
            }"""
        )

    def has_error(self) -> bool:
        # HuggingChat shows the error text inside the (disabled) prompt box
        in_box = self.ERROR_TEXT in (self.prompt_box.input_value() or "")
        on_page = self.page.get_by_text(self.ERROR_TEXT).count() > 0
        return in_box or on_page
