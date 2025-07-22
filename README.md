[![License](https://img.shields.io/github/license/berserkhmdvhb/agentic-scraper)](LICENSE)
[![Tests](https://github.com/berserkhmdvhb/charfinder/actions/workflows/tests.yml/badge.svg)](https://github.com/berserkhmdvhb/charfinder/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/coveralls/github/berserkhmdvhb/agentic-scraper/main?cacheSeconds=300)](https://coveralls.io/github/berserkhmdvhb/agentic-scraper?branch=main)
[![Lint: Ruff](https://img.shields.io/badge/lint-ruff-blue?logo=python\&logoColor=white)](https://docs.astral.sh/ruff)

# 🕵️ Agentic Scraper

**Agentic Scraper** is an intelligent, LLM-powered web scraping platform with a Streamlit interface. It supports parallel URL processing, adaptive data extraction via OpenAI, and structured output presentation — all in one streamlined tool.

Built with modern Python and a modular architecture, it combines async scraping, schema validation, automated screenshots, and user-friendly visualization.

---

## 🚀 Features

* 🔗 Accepts URL lists (text input or file upload)
* ⚡ Fast async scraping with `httpx` + `asyncio`
* 🔀 Smart retries using `tenacity`
* 🧠 OpenAI-powered agentic extraction
* 🔧 HTML parsing via `BeautifulSoup4`
* 📸 Full-page screenshots using Playwright
* ✅ Schema validation with `pydantic v2`
* 📊 Interactive UI with Streamlit + Ag-Grid + progress bars
* 🧲 Centralized logging, configurable via `.env`
* 📄 Export results to CSV / JSON / SQLite
* 🌍 Multilingual-ready and deduplication-aware
* 🧹 Modular, extensible design

---

## 📸 Demo

![screenshot](assets/screenshot.png)

---

## ⚙️ Tech Stack

| Layer            | Tools                                         |
| ---------------- | --------------------------------------------- |
| Async HTTP       | `httpx.AsyncClient`, `tenacity`               |
| HTML Parsing     | `BeautifulSoup4`                              |
| Screenshotting   | `playwright.async_api`                        |
| Agent Logic      | `openai.ChatCompletion` API                   |
| Data Modeling    | `pydantic v2`                                 |
| Validation       | Centralized helpers (`utils/validators.py`)   |
| Logging & Output | `.env` + centralized message constants        |
| UI               | `Streamlit`, `streamlit-aggrid`               |
| Dev Tools        | `black`, `ruff`, `mypy`, `pytest`, `Makefile` |

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

## 🔧 Environment Configuration

Create a `.env` file in the project root:

```ini
OPENAI_API_KEY=your-key-here
LOG_LEVEL=INFO
```

**Optional keys:**

* `MAX_CONCURRENCY`
* `LLM_MODEL`
* `LOG_MAX_BYTES`
* `LOG_BACKUP_COUNT`

---

## 🧪 How It Works

1. **Input** URLs via text or file
2. **Validate** using `validators.py`
3. **Fetch** HTML with `httpx`, with retries
4. **Parse** relevant content with `BeautifulSoup`
5. **Extract** structured data using OpenAI LLM
6. **Validate** output via `pydantic`
7. **Capture** screenshots with Playwright
8. **Display** results in Streamlit UI with Ag-Grid

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

> “Given the following HTML/text content, extract the most relevant fields like title, price, description, author, etc. Return a JSON object. If fields are missing, set them to null.”

See implementation in [`agent.py`](src/agentic_scraper/backend/scraper/agent.py)

---

## 📁 Project Structure

<details>
<summary>Click to expand</summary>

```
agentic_scraper/
├── .env                         # Local config
├── Makefile                     # Dev commands
├── pyproject.toml               # Dependencies & tools
├── run.py                       # CLI launcher
├── README.md                    # Project docs
├── sample.env                   # Example .env
├── docs/                        # Additional docs
│   └── development/, testing/
├── logs/                        # Per-env logs
│   ├── DEV/, UAT/, PROD/
├── screenshots/                 # Screenshot output
├── src/agentic_scraper/         # Main codebase
│   ├── backend/
│   │   ├── config/              # Constants, types, messages
│   │   ├── core/                # Logging, settings
│   │   ├── scraper/             # Agents, parser, fetcher
│   │   └── utils/               # Validators, helpers
│   └── frontend/                # Streamlit UI
│       └── app.py
├── tests/                       # Unit + integration tests
```

</details>

---

## 🗺 Roadmap

* [ ] 🌍 Multilingual support via language detection
* [ ] 🧠 Embedding-based deduplication
* [ ] 📂 SQLite export + scrape history
* [ ] 🧰 Domain-specific prompt customization
* [ ] 🚧 Docker container
* [ ] 🔐 Optional auth for multi-user access

---

## 📜 License

MIT License
