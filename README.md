[![License](https://img.shields.io/github/license/berserkhmdvhb/agentic-scraper)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)
[![Docker: Frontend](https://img.shields.io/badge/docker-frontend-blue?logo=docker)](https://hub.docker.com/r/hmdvhb/agentic-scraper-frontend)
[![Docker: Backend](https://img.shields.io/badge/docker-backend-blue?logo=docker)](https://hub.docker.com/r/hmdvhb/agentic-scraper-backend)
![Lint: Ruff](https://img.shields.io/badge/lint-ruff-blue?logo=python&logoColor=white)
[![CI: Tests GA](https://github.com/berserkhmdvhb/agentic-scraper/actions/workflows/tests.yml/badge.svg)](https://github.com/berserkhmdvhb/agentic-scraper/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/coveralls/github/berserkhmdvhb/agentic-scraper/main?cacheSeconds=300)](https://coveralls.io/github/berserkhmdvhb/agentic-scraper?branch=main)
[![CD: Frontend Deploy](https://img.shields.io/badge/frontend-render-blueviolet?logo=render)](https://agenticscraper.onrender.com)
[![CD: Backend Deploy](https://img.shields.io/badge/backend-render-blueviolet?logo=render)](https://api-agenticscraper.onrender.com)


# 🕵️ Agentic Scraper <img src="logo.jpg" align="right" style="width: 15%;"/>

**Agentic Scraper** is an intelligent, LLM-powered web scraping platform with a modular backend and a Streamlit interface. It supports adaptive agents, schema-aware retries, multilingual readiness, and fast parallel scraping for structured data extraction at scale.


## 📑 Table of Contents

- [🚀 Features](#-features)
- [📸 Demo](#-demo)
- [⚙️ Tech Stack](#️-tech-stack)
- [🧠 Agent Modes](#-agent-modes)
- [🔬 Scraping Architecture](#-scraping-architecture)
  - [🔗 URL Fetching](#-url-fetching-in-fetcherpy)
  - [🧬 Agent Extraction](#-agent-extraction-in-agent)
- [🧠 Adaptive Retry Logic](#-adaptive-retry-logic-for-llm-agents)
- [📁 Project Structure](#-project-structure)
- [🧰 Installation](#-installation)
  - [👤 For Users](#-for-users)
  - [💼 For Developers](#-for-developers)
  - [🐳 Run via Docker](#-run-via-docker)
- [▶️ Running the App](#%EF%B8%8F-running-the-app)
  - [Online](#online)
  - [Local](#local)
- [🔧 Environment Configuration (.env)](#-environment-configuration-env)
- [🧪 How It Works](#-how-it-works)
- [✨ Example Output](#-example-output)
- [🚀 CI/CD & Deployment](#-cicd--deployment)
  - [🧪 Continuous Integration](#-continuous-integration)
  - [🚀 Continuous Delivery (Render)](#-continuous-delivery-render)
  - [📦 Docker Support](#-docker-support)
- [🗺 Roadmap](#-roadmap)
- [📜 License](#-license)


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

| Layer                         | Tools                                                    |
| ----------------------------- | -------------------------------------------------------- |
| **Async Fetching**            | `httpx`, `asyncio`, `tenacity`                           |
| **HTML Parsing**              | `BeautifulSoup4`                                         |
| **Screenshots**               | `playwright.async_api`                                   |
| **Agent Logic**               | `OpenAI API`, `ChatCompletion`, schema retry loop        |
| **Schema Validation**         | `Pydantic v2`                                            |
| **UI Layer**                  | `Streamlit`, `streamlit-aggrid`                          |
| **Settings & Logging**        | `.env`, `loguru`, centralized `messages.py`              |
| **Backend API**               | `FastAPI`, `Pydantic`, `uvicorn`                         |
| **Authentication / Security** | Auth0, OAuth2, OIDC *(in progress)*                      |
| **Testing**                   | `pytest`, `conftest.py` fixtures                         |
| **Linting & Typing**          | `ruff`, `mypy`                                           |
| **Tooling & Automation**      | `Makefile`, `Docker`, `Docker Compose`                   |
| **Deployment**                | `Render.com`, Docker Hub (`frontend` & `backend` images) |



---

## 🧠 Agent Modes

| Mode                   | Description                                              |
| ---------------------- | -------------------------------------------------------- |
| `rule-based`           | Heuristic parser using BeautifulSoup (no LLM)            |
| `llm-fixed`            | LLM extracts fixed schema fields (e.g. title, price)     |
| `llm-dynamic`          | LLM chooses relevant fields based on page content        |
| `llm-dynamic-adaptive` | Adds retries, field importance, and contextual reasoning |

> Recommended: use llm-dynamic-adaptive for best results.



> The UI dynamically adapts to the selected mode — retry sliders and model selectors appear only for LLM-based modes.

---

## 🔬 Scraping Architecture

The scraping pipeline consists of two major components:

* **🔗 URL Fetching** – Responsible for retrieving raw HTML and metadata.
* **🧠 Agent Extraction** – Parses and extracts structured data using either rules or LLMs.

These stages are modular and can be extended independently.

---

### 🔗 URL Fetching (in `fetcher.py`)

The fetching stage is implemented using `httpx.AsyncClient` for concurrent HTTP requests and `tenacity` for smart retries. Each URL is fetched asynchronously and returned as a `FetchedDocument` object containing:

* Original and final (redirected) URLs
* HTTP status code and headers
* Raw HTML content
* Metadata such as domain and fetch timestamp

**Features:**

* Concurrent execution with `asyncio.gather`
* Exponential backoff retry on failure
* Bot-mimicking headers and timeouts
* Optional screenshot triggering via middleware

This stage feeds clean, validated inputs into the next step: agent-based extraction.

---

### 🧬 Agent Extraction (in `agent/`)

The Agent layer transforms raw HTML into structured output by selecting relevant fields and filling a JSON schema. The agent used is determined by the `AGENT_MODE` setting.

Each strategy is implemented as a self-contained module and shares a common interface.

#### `rule_based` (baseline benchmark)

* Implements classic parsing with BeautifulSoup4.
* Uses heuristics (e.g., heading tags, price regex) to extract fields.
* No LLMs involved.
* **Fastest and most deterministic.**
* Good for simple product/job/blog pages.

#### `llm_fixed`

* Prompts OpenAI to extract a **predefined schema**: title, price, description, etc.
* Always expects these fields, even if they're not present in the page.
* Simple, schema-first design.
* Does not retry or adapt.

#### `llm_dynamic`

* Gives the LLM freedom to **choose relevant fields** based on the page content.
* Useful for heterogeneous or unknown page types.
* Adds minor prompt conditioning to bias field detection.

#### `llm_dynamic_adaptive`

* Builds on `llm_dynamic` by adding:

  * **Field coverage scoring** using `field_utils.py`
  * **Retry loop** up to `LLM_SCHEMA_RETRIES`
  * **Context hints**: page meta tags, URL segments, and expected field importance
* Selects the best result across multiple attempts.
* Enables **robust, schema-aware, self-healing extraction**.

Each agent returns a `ScrapedItem` that conforms to the schema and may include fallback values or nulls.

---

## 🧠 Adaptive Retry Logic (for LLM Agents)

Only the `llm-dynamic-adaptive` agent supports **field-aware retrying** when critical fields (e.g. `title`, `price`, `job_title`) are missing.

### How It Works:

1. Performs an initial LLM extraction attempt.
2. Evaluates field coverage using `field_utils.score_fields()`.
3. If important fields are missing, it re-prompts with hints and context.
4. Repeats up to `LLM_SCHEMA_RETRIES` times.
5. Returns the best-scoring result among attempts.

→ Enables **self-healing extraction** and **schema robustness** on diverse webpages.

---


## 📁 Project Structure
### Overview

```
agentic_scraper/
├── .env, sample.env, Makefile, README.md, docker-compose.yml
├── Dockerfile.backend, Dockerfile.frontend
├── pyproject.toml, requirements.txt, poetry.lock
├── run.py, run_api.py, run_batch.py, run_experiments.py
├── .github/workflows/             # GitHub Actions CI/CD workflows
├── docs/                          # Developer and testing docs
├── input/                         # URL input files
├── tests/                         # Unit and integration tests
├── src/
│   └── agentic_scraper/
│       ├── backend/
│       │   ├── api/               # FastAPI app and routes
│       │   ├── config/            # Constants, aliases, enums, messages
│       │   ├── core/              # Logger and settings
│       │   ├── scraper/
│       │   │   ├── agent/         # Modular agent strategies (LLMs, rules)
│       │   │   ├── fetcher, parser, pipeline, screenshotter, worker_pool
│       │   └── utils/             # Validators and shared helpers
│       └── frontend/              # Streamlit UI (core, display, runner)
```

### Detailed

```
agentic_scraper/
├── .env                         # Local config
├── Makefile                     # Dev commands
├── pyproject.toml               # Project dependencies and tool config
├── run.py                       # CLI launcher for Streamlit
├── README.md                    # Project documentation
├── sample.env                   # Example environment file
├── requirements.txt             # Exported requirements (pip)
├── poetry.lock                  # Poetry lock file
├── remove_bom.py                # Utility script
├── run_api.py                   # CLI launcher for FastAPI backend
├── run_batch.py                 # CLI for batch scraping
├── run_experiments.py           # Concurrency benchmarking script
├── mock_api.py                  # Local mock server for experiments testing
├── docker-compose.yml           # Orchestrates frontend and backend containers
├── Dockerfile.backend           # Builds the FastAPI backend image
├── Dockerfile.frontend          # Builds the Streamlit frontend image
├── logo.jpg                     # Project logo (used in README/demo)
├── LICENSE                      # License file
├── .github/workflows/           # GitHub Actions CI/CD workflows
│   ├── badge-refresh.yml
│   ├── check-requirements.yml
│   ├── docker-build-backend.yml
│   ├── docker-build-frontend.yml
│   └── tests.yml
├── docs/                        # Additional documentation
├── input/                       # Sample input files
│   ├── urls1.txt
│   └── urls2.txt
├── screenshots/                 # Captured screenshots per scrape
├── tests/                       # Unit and manual tests
│   ├── backend/core/test_settings.py
│   ├── manual/screenshotter_test.py
│   └── manual/validators_test.py
├── src/                         # Source code (main application)
│   └── agentic_scraper/
│       ├── backend/
│       │   ├── api/
│       │   │   ├── main.py                  # FastAPI app entrypoint
│       │   │   ├── models.py                # API models/schemas
│       │   │   └── routes/
│       │   │       └── scrape.py            # Scrape endpoint logic
│       │   ├── config/
│       │   │   ├── aliases.py               # Input aliases, enums
│       │   │   ├── constants.py             # Default values
│       │   │   ├── messages.py              # All log/UI messages
│       │   │   └── types.py                 # Strongly-typed enums
│       │   ├── core/
│       │   │   ├── logger_helpers.py        # Logging formatter utilities
│       │   │   ├── logger_setup.py          # Loguru setup
│       │   │   ├── settings.py              # Global settings model
│       │   │   └── settings_helpers.py      # Validation, resolution helpers
│       │   ├── scraper/
│       │   │   ├── fetcher.py               # HTML fetching with retries
│       │   │   ├── models.py                # Scraped item schema
│       │   │   ├── parser.py                # HTML parsing logic
│       │   │   ├── pipeline.py              # Orchestration pipeline
│       │   │   ├── screenshotter.py         # Playwright screenshot logic
│       │   │   ├── worker_pool.py           # Async task concurrency manager
│       │   │   └── agent/
│       │   │       ├── agent_helpers.py     # Agent utils
│       │   │       ├── field_utils.py       # Field scoring, synonyms
│       │   │       ├── llm_dynamic.py       # LLM agent: dynamic fields
│       │   │       ├── llm_dynamic_adaptive.py # LLM agent: retries, context
│       │   │       ├── llm_fixed.py         # LLM agent: fixed schema
│       │   │       ├── prompt_helpers.py    # Prompt generation
│       │   │       └── rule_based.py        # Rule-based parser
│       │   └── utils/
│       │       └── validators.py            # Input validators
│       └── frontend/
│           ├── app.py                      # Streamlit UI entrypoint
│           ├── models.py                   # Shared data schemas
│           ├── ui_core.py                  # Sidebar + config widgets
│           ├── ui_display.py               # Table, chart, image display
│           └── ui_runner.py                # Async scrape runner + hooks
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

>  Screenshots require installing Playwright separately. [Install docs →](https://playwright.dev/python/docs/intro)

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

#### 🐳 Run via Docker

To launch both frontend and backend locally using Docker Compose:

```bash
docker-compose up --build
```
Or use the Makefile shortcuts:

```bash
make docker-up
make docker-build
```

Then visit:

- Frontend: http://localhost:8501
- Backend: http://localhost:8000



---
## ▶️ Running the App

### Online
 Visit the hosted version domains here: 

 

- 🔗 **Frontend (Streamlit UI):** [![CD: Frontend Deploy](https://img.shields.io/badge/frontend-render-blueviolet?logo=render)](https://agenticscraper.onrender.com)
- 🔗 **Backend (FastAPI API):** [![CD: Backend Deploy](https://img.shields.io/badge/backend-render-blueviolet?logo=render)](https://api-agenticscraper.onrender.com)

### Local

Start the Streamlit UI:

```bash
streamlit run src/agentic_scraper/frontend/app.py
```

Or, use the shortcut:

```bash
python run.py
```

The app prompts you for an OpenAI API key and URLs to scrape.

---

## 🔧 Environment Configuration (.env)

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

## 🚀 CI/CD & Deployment

Agentic Scraper now supports **full CI/CD** with Docker-based builds and continuous deployment to Render.com.

### 🧪 Continuous Integration
Automated tests, linting, and type checks are run via [GitHub Actions](https://github.com/berserkhmdvhb/agentic-scraper/actions) on every push and PR.

### 🚀 Continuous Delivery (Render)
Production deployments are triggered automatically when changes are pushed to `main`.
To see the hosted domains, visit [Running the App](#%EF%B8%8F-running-the-app)

### 📦 Docker Support

We’ve added production-ready Docker configuration:
- `Dockerfile.backend` – builds the FastAPI backend
- `Dockerfile.frontend` – builds the Streamlit frontend
- `docker-compose.yml` – orchestrates both services for local dev or deployment

> Use `docker-compose up` to spin up the app locally with both services.

#### 🐳 Docker Hub Images

Pre-built Docker images for both frontend and backend are available:

* **Frontend:**
  [![Docker: Frontend](https://img.shields.io/badge/docker-frontend-blue?logo=docker)](https://hub.docker.com/r/hmdvhb/agentic-scraper-frontend)

  `docker pull hmdvhb/agentic-scraper-frontend`

* **Backend:**
  [![Docker: Backend](https://img.shields.io/badge/docker-backend-blue?logo=docker)](https://hub.docker.com/r/hmdvhb/agentic-scraper-backend)

  `docker pull hmdvhb/agentic-scraper-backend`



These images are automatically published on every versioned release and push to `main`. Use them to quickly deploy the app without building locally.

---

## 🗺 Roadmap

* [x] Self-healing retry loop for LLM
* [x] Field scoring to prioritize important fields
* [x] Conditional UI for agent settings
* [x] FastAPI backend (in progress)
* [x] Docker container deployment
* [ ] Multilingual support + auto-translation
* [ ] User authentication with Auth0
* [ ] Authentication protocol with OAuth2 + OIDC


---

## 📜 License

MIT License
