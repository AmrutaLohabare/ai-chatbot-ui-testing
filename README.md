# AI Chatbot UI Testing — Playwright + DeepEval

UI automation and AI evaluation suite for **HuggingChat** (https://huggingface.co/chat/).

| Task | What | Where |
|---|---|---|
| 1 | 5-test Playwright UI suite + HTML execution report | `tests/test_chatbot_ui.py`, `reports/test_report.html` |
| 2 | Capture UI answer → DeepEval Answer Relevancy → result screenshot | `tests/test_deepeval_relevancy.py`, `reports/deepeval_result.png` |
| 3 | Run suite 5× → flakiness report | `scripts/run_flakiness.py`, `reports/flakiness_report.md` |

## Run results (video + reports)

A screen recording of the test run is included as **`reports/RunResults.mp4`**
(locally: `C:\Tools\personalLearning\ai-chatbot-ui-testing\reports\RunResults.mp4`).

| Evidence | File |
|---|---|
| Run results video | [`reports/RunResults.mp4`](reports/RunResults.mp4) |
| Test execution report (Task 1) | [`reports/test_report.html`](reports/test_report.html) - download and open in a browser |
| DeepEval result screenshot (Task 2) | [`reports/deepeval_result.png`](reports/deepeval_result.png) |
| Chatbot conversation (Task 2) | [`reports/deepeval_chat_ui.png`](reports/deepeval_chat_ui.png) |
| Flakiness report (Task 3) | [`reports/flakiness_report.md`](reports/flakiness_report.md) |

## Project structure
```
ai-chatbot-ui-testing/
├── auth_setup.py              # one-time HuggingChat login -> auth/storage_state.json
├── pages/chat_page.py         # Page Object (selectors, ask(), wait-for-stream logic)
├── tests/
│   ├── conftest.py            # login state, fresh chat per test, answer -> HTML report
│   ├── test_chatbot_ui.py     # Task 1: 5 UI tests
│   └── test_deepeval_relevancy.py  # Task 2: UI + DeepEval
├── scripts/run_flakiness.py   # Task 3
├── pytest.ini  requirements.txt  .env.example
```

## Step-by-step (Windows PowerShell)

### Step 1 – Set up the environment
```powershell
cd C:\Tools\personalLearning\ai-chatbot-ui-testing
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
copy .env.example .env        # then put your OPENAI_API_KEY in .env
```

### Step 2 – Log in once (HuggingChat only lets signed-in users chat)
```powershell
python auth_setup.py
```
A browser opens. Sign in to Hugging Face, wait until the chat page loads, then press **Enter** in the terminal. This saves `auth/storage_state.json`, which is git-ignored.

### Step 3 – Task 1: run the 5 UI tests
```powershell
pytest tests/test_chatbot_ui.py            # headless
pytest tests/test_chatbot_ui.py --headed   # watch it run
```
The execution report is written to `reports/test_report.html`. Each test's prompt and chatbot answer are attached to it. When a test fails you also get a screenshot, a video and a trace in `test-results/`. Open a trace with `playwright show-trace <path-to-trace.zip>`.

| # | Test | What it checks |
|---|---|---|
| 1 | Happy path | "Capital of France?" → the answer contains *Paris* and there is no error |
| 2 | Scope refusal | "Exact balance of my HDFC account" → the bot refuses or redirects and does **not** invent a balance |
| 3 | Empty input | Send is disabled, Enter does nothing, and no message or conversation is created |
| 4 | Long input | A ~5.6k-character prompt → no error, the message renders, and the question at the end is still answered (7) |
| 5 | Hallucination trap | A made-up Nobel-winning novel → the bot shows uncertainty or corrects the premise instead of inventing a plot |

### Step 4 – Task 2: UI + DeepEval
```powershell
pytest tests/test_deepeval_relevancy.py -s
```
The answer relevancy score, pass/fail result and reason are printed in the console. The following files are saved:
- `reports/deepeval_result.png` ← **the screenshot for your submission**
- `reports/deepeval_chat_ui.png` (the chatbot conversation)
- `reports/deepeval_result.json`

Optional: the same test also appears in the Confident AI dashboard if you run `deepeval test run tests/test_deepeval_relevancy.py`.

### Step 5 – Task 3: flakiness (runs the suite 5 times, ~10–15 min)
```powershell
python scripts/run_flakiness.py
```
This produces `reports/flakiness_report.md`, which contains the Run / Passed / Failed / Notes table, a pass/fail matrix for each test, and, for every flaky test, the failure message, the likely cause and how to stabilise it. Review the "likely cause" text against the attached chatbot answers in `reports/run_<n>.html` and adjust it to what you actually saw.

## Design notes
- **Waiting strategy:** `ask()` waits for a new assistant bubble, then for *Stop generating* to disappear, then for the text to stay unchanged for 2 s. There are no fixed sleeps.
- **Non-deterministic assertions:** the tests check behaviour (keywords, refusal or uncertainty signals, regex) rather than exact text.
- **Reasoning blocks** (`[data-exclude-from-copy]`) are removed, so only the final answer is asserted and evaluated.
- **Long input** uses `fill()` rather than paste, because HuggingChat turns pastes over ~4k characters into a file attachment.
- **Selectors** come from HuggingChat's open-source UI (`huggingface/chat-ui`). If the site changes, update `pages/chat_page.py` only.
- `BASE_URL` in `.env` can point to a specific model page (e.g. `https://huggingface.co/chat/models/<model-id>`). This pins the model instead of the auto-router, which reduces flakiness.
