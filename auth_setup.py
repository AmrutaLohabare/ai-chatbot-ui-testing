"""One-time login helper.

HuggingChat only lets signed-in users type a prompt. Run this once:

    python auth_setup.py

A browser opens -> sign in with your Hugging Face account -> come back to the
terminal and press Enter. Your session is saved to auth/storage_state.json and
every test re-uses it (no login inside tests = faster and less flaky).
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

STATE_FILE = Path(__file__).parent / "auth" / "storage_state.json"
LOGIN_URL = "https://huggingface.co/chat/login"


def main():
    STATE_FILE.parent.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(LOGIN_URL)
        input("\nSign in to Hugging Face in the opened browser, wait until you see the chat page, then press Enter here... ")
        context.storage_state(path=str(STATE_FILE))
        browser.close()
    print(f"Saved login session to {STATE_FILE}")


if __name__ == "__main__":
    main()
