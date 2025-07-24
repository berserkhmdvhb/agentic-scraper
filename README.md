[![License](https://img.shields.io/github/license/berserkhmdvhb/agentic-scraper)](LICENSE)
[![Tests](https://github.com/berserkhmdvhb/agentic-scraper/actions/workflows/tests.yml/badge.svg)](https://github.com/berserkhmdvhb/agentic-scraper/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/coveralls/github/berserkhmdvhb/agentic-scraper/main?cacheSeconds=300)](https://coveralls.io/github/berserkhmdvhb/agentic-scraper?branch=main)
[![Lint: Ruff](https://img.shields.io/badge/lint-ruff-blue?logo=python&logoColor=white)

# 🕵️ Agentic Scraper

**Agentic Scraper** is an intelligent, LLM-powered web scraping platform with a modular backend and a Streamlit interface. It supports adaptive agents, schema-aware retries, multilingual readiness, and fast parallel scraping for structured data extraction at scale.

---

## 🚀 Features

* 🔗 Accepts URLs via paste or `.txt` file upload
* 🌐 Multiple agent modes (`rule-based`, `llm-fixed`, `llm-dynamic`, `llm-dynamic-adaptive`)
* 🧠 Adaptive self-healing LLM retries for missing fields
* ⚡ Async scraping with `httpx`, `asyncio`, and retry via `tenacity`
* ✔️ Schema validation using `pydantic v2`
* 📸 Full-page screenshots via Playwright
* 🔧 Advanced UI controls for concurrency, retries, and agent config
* 📚 Export scraped data to CSV / JSON / SQLite
* 🧰 Configurable logging, progress bars, and Ag-Grid display
* 🧱 Modular architecture with FastAPI backend

---

## 📸 Demo

![screenshot](assets/screenshot.png)

---

## ⚙️ Tech Stack

| Layer             | Tools                                         |
| ----------------- | --------------------------------------------- |
| Async Fetching    | `httpx`, `asyncio`, `tenacity`                |
| HTML Parsing      | `BeautifulSoup4`                              |
| Screenshots       | `playwright.async_api`                        |
| Agent Logic       | `openai.ChatCompletion`, retry loop           |
| Schema Validation | `pydantic v2`                                 |
| UI Layer          | `Streamlit`, `streamlit-aggrid`               |
| Settings/Logging  | `.env`, `loguru`, centralized messages        |
| Backend API       | `FastAPI` (`backend/api/`)                    |
| Dev Tools         | `ruff`, `pytest`, `Makefile`, `mypy` |

---

## 🧠 Agent Modes

| Mode                   | Description                                              |
| ---------------------- | -------------------------------------------------------- |
| `rule-based`           | Heuristic parser using BeautifulSoup (no LLM)            |
| `llm-fixed`            | LLM extracts fixed schema fields (e.g. title, price)     |
| `llm-dynamic`          | LLM chooses relevant fields based on page content        |
| `llm-dynamic-adaptive` | Adds retries, field importance, and contextual reasoning |

> The UI dynamically adapts to the selected mode — retry sliders and model selectors appear only for LLM-based modes.

---

## 🧠 Adaptive Retry Logic

In `llm-dynamic-adaptive` mode:

* Detects missing high-importance fields (e.g. title, price)
* Re-prompts the LLM using a **self-healing loop**
* Scores output by **field coverage**
* Returns the best result among attempts

---

## 📁 Project Structure

```
agentic_scraper/
├── .env                         # Local config
├── Makefile                     # Dev commands
├── pyproject.toml               # Project dependencies and tool config
├── run.py                       # CLI launcher for Streamlit
├── README.md                    # Project documentation
├── sample.env                   # Example environment file
├── docs/                        # Additional documentation
│   └── development/, testing/   # Dev/test-specific notes
├── logs/                        # Log output grouped by environment
│   ├── DEV/
│   ├── UAT/
│   └── PROD/
├── screenshots/                 # Captured screenshots per scrape
├── tests/                       # Unit and integration tests
│   └── (mirrors src/ structure)
├── src/                         # Source code (main application)
│   └── agentic_scraper/
│       ├── backend/
│       │   ├── api/
│       │   │   ├── main.py                  # FastAPI app entrypoint
│       │   │   ├── models.py                # API models/schemas
│       │   │   └── routes/
│       │   │       ├── scrape.py            # Scrape endpoint logic
│       │   ├── config/
│       │   │   ├── aliases.py               # Input aliases, enums
│       │   │   ├── constants.py             # Default values
│       │   │   ├── messages.py              # All log/UI messages
│       │   │   ├── types.py                 # Strongly-typed enums
│       │   ├── core/
│       │   │   ├── logger_helpers.py        # Logging formatter utilities
│       │   │   ├── logger_setup.py          # Loguru setup
│       │   │   ├── settings.py              # Global settings model
│       │   │   ├── settings_helpers.py      # Validation, resolution helpers
│       │   ├── scraper/
│       │   │   ├── fetcher.py               # HTML fetching with retries
│       │   │   ├── models.py                # Scraped item schema
│       │   │   ├── parser.py                # HTML parsing logic
│       │   │   ├── pipeline.py              # Orchestration pipeline
│       │   │   ├── screenshotter.py         # Playwright screenshot logic
│       │   │   ├── worker_pool.py           # Async task concurrency manager
│       │   │   └── agent/
│       │   │       ├── agent_helpers.py             # Agent utils
│       │   │       ├── field_utils.py               # Field scoring, synonyms
│       │   │       ├── llm_dynamic.py               # LLM agent: dynamic fields
│       │   │       ├── llm_dynamic_adaptive.py      # LLM agent: retries, context
│       │   │       ├── llm_fixed.py                 # LLM agent: fixed schema
│       │   │       ├── prompt_helpers.py            # Prompt generation
│       │   │       ├── rule_based.py                # Rule-based parser
│       │   └── utils/
│       │       ├── validators.py            # Input validators
│       └── frontend/
│           ├── app.py                      # Streamlit UI entrypoint
│           ├── ui_core.py                  # Sidebar + config widgets
│           ├── ui_display.py               # Table, chart, image display
│           ├── ui_runner.py                # Async scrape runner + hooks
```
---

## 🧰 Installation

### 👤 For Users

**Install from GitHub (Recommended):**

```bash
pip install git+https://github.com/berserkhmdvhb/agentic-scraper.git
```

> 📦 This installs all dependencies defined in `pyproject.toml`.

**Playwright Setup (for screenshots):**

```bash
playwright install
```

> Screenshots require separate Playwright setup. [Install docs →](https://playwright.dev/python/docs/intro)

**Alternative (pip + requirements.txt):**

```bash
pip install -r requirements.txt
```

> ⚠️ `requirements.txt` is auto-generated via `poetry export`. Keep it synced.

---

### 💼 For Developers

**Clone and set up development environment:**

```bash
git clone https://github.com/berserkhmdvhb/agentic-scraper.git
cd agentic-scraper
make develop
```

Or manually:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
poetry install
```

---

## ▶️ Running the App

Start the Streamlit UI:

```bash
streamlit run src/agentic_scraper/frontend/app.py
```

Or, use the shortcut:

```bash
python run.py
```

You'll be prompted to enter your OpenAI API key and a list of URLs to scrape. Results will display in real time with screenshots and metadata.

---

## 🔧 .env Configuration

```ini
OPENAI_API_KEY=sk-...
LOG_LEVEL=INFO
AGENT_MODE=llm-dynamic-adaptive
LLM_MODEL=gpt-4
LLM_SCHEMA_RETRIES=2
MAX_CONCURRENCY=10
LOG_MAX_BYTES=500000
LOG_BACKUP_COUNT=2
```

The UI overrides `.env` if sidebar values are selected.

---

## 🧪 How It Works

1. **Input**: URLs from user (via paste or file)
2. **Fetch**: HTML pages with retries
3. **Parse**: HTML content with `BeautifulSoup`
4. **Extract**: Structured info via LLM or rule-based parser
5. **Validate**: Output with `pydantic` schema
6. **Retry** (LLM only): Re-prompt if fields are missing
7. **Screenshot**: Page saved via Playwright
8. **Display**: Results shown in Streamlit with Ag-Grid
9. **Export**: JSON, CSV, or SQLite output

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

## 🗺 Roadmap

* [x] Self-healing retry loop for LLM
* [x] Field scoring to prioritize important fields
* [x] Conditional UI for agent settings
* [x] FastAPI backend (in progress)
* [ ] SQLite export + scrape history view
* [ ] Multilingual support + auto-translation
* [ ] User authentication with Auth0
* [ ] Authentication protocol with OAuth2 + OIDC
* [ ] Docker container deployment

---

## 📜 License

MIT License
