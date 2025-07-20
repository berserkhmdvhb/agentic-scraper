[![License](https://img.shields.io/github/license/berserkhmdvhb/agentic-scraper)](LICENSE)
[![Tests](https://github.com/berserkhmdvhb/charfinder/actions/workflows/tests.yml/badge.svg)](https://github.com/berserkhmdvhb/charfinder/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/coveralls/github/berserkhmdvhb/agentic-scraper/main?cacheSeconds=300)](https://coveralls.io/github/berserkhmdvhb/agentic-scraper?branch=main)

# 🕵️ Agentic Scraper

**Agentic Scraper** is an intelligent, LLM-powered web scraping tool with a Streamlit interface. It processes multiple URLs in parallel, extracts structured data using adaptive agent logic, and presents results in an interactive UI.

Built with modern Python, this project blends async scraping, schema-aware extraction, automated screenshot capture, and human-friendly presentation — all in one app.

---

## 🚀 Features

* 🔗 Accepts lists of URLs (via text input or file upload)
* ⚡ Async web scraping using `httpx` and `asyncio`
* 🔁 Retry logic with `tenacity`
* 🧠 Agentic extraction powered by OpenAI LLMs
* 🧱 Structured HTML parsing with `BeautifulSoup4`
* 📸 Full-page screenshots using Playwright
* ✅ Schema-based validation with `pydantic`
* 📊 Interactive Streamlit UI with progress bars
* 🧢 Centralized logging with configurable levels
* 📅 Export to CSV / JSON / (future: SQLite)
* 🌍 Future-ready: multilingual support & deduplication
* 🧹 Modular architecture for easy extension

---

## 📸 Demo

<!-- Include a screenshot or short GIF here -->

![screenshot](assets/screenshot.png)

---

## 📦 Tech Stack

| Layer            | Tools                                         |
| ---------------- | --------------------------------------------- |
| Async HTTP       | `httpx.AsyncClient`, `tenacity`               |
| HTML Parsing     | `BeautifulSoup4`                              |
| Screenshotting   | `playwright.async_api`                        |
| Agent Logic      | `openai` (ChatCompletion API)                 |
| Data Modeling    | `pydantic v2`                                 |
| Validation       | Centralized helpers in `utils/validators.py`  |
| Logging & Output | Configurable via `.env` + message constants   |
| UI               | `Streamlit`                                   |
| Dev Tools        | `black`, `ruff`, `mypy`, `pytest`, `Makefile` |

---

## 🚀 Usage

This section shows how to install, run, and integrate **Agentic Scraper**, whether you're an end user exploring LLM-powered extraction or a developer integrating scraping into your workflow.

### Installation

#### 👤 For Users

##### GitHub (Recommended)

```bash
pip install git+https://github.com/berserkhmdvhb/agentic-scraper.git
```
> Note: 📦 This installs all dependencies declared in pyproject.toml.
> Note: You must also install and configure [Playwright](https://playwright.dev/python/docs/intro) separately if you need screenshot support.

##### Alternatively (pip + requirements.txt)

```bash
pip install -r requirements.txt
```

> ⚠️ This file is auto-generated from pyproject.toml using poetry export. Keep it in sync during development.

#### 💼 For Developers

##### Clone and Install in Editable Mode

```bash
git clone https://github.com/berserkhmdvhb/agentic-scraper.git
cd agentic-scraper
make develop
```

Alternatively:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
poetry install
```

---

### 💻 Run the App

Start the Streamlit UI locally:

```bash
streamlit run src/agentic_scraper/frontend/app.py
```
Or, if you prefer a shorter command:

```bash
python run.py
```

You'll be prompted to enter your OpenAI API key and URLs to scrape. Results will appear live, with metadata and screenshots exported.

---

### 🔢 Set Up Environment

Create a `.env` file in the project root:

```ini
OPENAI_API_KEY=your-key-here
LOG_LEVEL=INFO
```

Optional config keys:

* `MAX_CONCURRENCY`
* `LLM_MODEL`
* `LOG_MAX_BYTES`
* `LOG_BACKUP_COUNT`


---

## 🔍 How It Works

1. **Input** URLs via text or file
2. **Validate** URLs with `validators.py`
3. **Fetch** HTML with `httpx` and retry on failure
4. **Parse** key content using `BeautifulSoup`
5. **Run** OpenAI LLM prompt to extract fields
6. **Validate** structured output using `pydantic`
7. **Capture** full-page screenshots with Playwright
8. **Display** results in a clean Streamlit UI

---

## ✨ Example Output

```json
{
  "title": "The Future of AI Agents",
  "author": "Jane Doe",
  "price": 19.99,
  "description": "An in-depth look at LLM-powered web automation.",
  "url": "https://example.com/future-of-agents",
  "screenshot_path": "screenshots/example-f3d4c2a1.png"
}
```

---

## 🧠 Agent Prompt Strategy

> "Given the following HTML/text content, extract the most relevant fields like title, price, description, author, etc. Return a JSON object. If fields are missing, set them to null."

You can find this logic in [`scraper/agent.py`](src/agentic_scraper/backend/scraper/agent.py)

---

## 📂 Project Structure

```
agentic_scraper/
├── .env                              # Local environment configuration
├── .gitattributes
├── .gitignore
├── LICENSE
├── logo.jpg                          # Optional logo for UI
├── Makefile                          # Common development commands
├── pyproject.toml                    # Project dependencies and tooling
├── pytest.ini                        # Pytest configuration
├── README.md                         # Project documentation (this file)
├── run.py                            # Optional CLI/script entry point
├── sample.env                        # Example .env template
│
├── docs/                             # Project documentation
│   ├── development/
│   └── testing/
│
├── logs/                             # Log output by environment
│   ├── DEV/
│   ├── UAT/
│   └── PROD/
│
├── screenshots/                      # Output directory for saved page screenshots
│
├── src/agentic_scraper/              # Main application code
│   ├── backend/
│   │   ├── config/                   # Constants, messages, types
│   │   │   ├── aliases.py            # Shared type aliases
│   │   │   ├── constants.py          # Static values (timeouts, etc.)
│   │   │   ├── messages.py           # Centralized log + UI messages
│   │   │   ├── types.py              # Structured types (e.g., TypedDict)
│   │   │
│   │   ├── core/                     # Settings and logging
│   │   │   ├── logger_helpers.py     # Logging format and filter tools
│   │   │   ├── logger_setup.py       # Logger config and rotation
│   │   │   ├── settings.py           # Pydantic Settings model
│   │   │   ├── settings_helpers.py   # .env + environment logic
│   │   │
│   │   ├── scraper/                  # Scraping, parsing, and extraction
│   │   │   ├── agent.py              # OpenAI prompt and JSON extraction
│   │   │   ├── fetcher.py            # Async HTTP fetch logic
│   │   │   ├── models.py             # `ScrapedItem` and other schemas
│   │   │   ├── parser.py             # HTML metadata/text parsing
│   │   │   ├── screenshotter.py      # Playwright-based screenshot capture
│   │   │
│   │   ├── utils/                    # Reusable helpers
│   │       ├── validators.py         # Input and path validation functions
│
│   ├── frontend/                     # Streamlit UI
│   │   └── app.py                    # Streamlit app layout and logic
│
├── tests/                            # Unit and integration tests
```

---

## 🧪 Roadmap

* [ ] 💬 Add translation + language detection
* [ ] 🧰 Embedding-based deduplication
* [ ] 📅 SQLite export and scraping history
* [ ] 🔎 Domain-aware prompt tuning
* [ ] 📃 Ag-Grid or DataTable UI
* [ ] Docker containerization
* [ ] 🔐 Optional auth for multi-user workflows


---

## 📜 License

MIT License
