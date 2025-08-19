<p align="center">
  <img src="logo.png" alt="Agentic Scraper Logo" width="300"/>
</p>


<p align="center">
  <em>LLM-powered web scraping with modular agents, secure Auth0 authentication, and concurrent performance</em><br/>
  <em>FastAPI backend · Streamlit frontend · OpenAI-integrated structured extraction · Self-healing adaptive retries </em>
</p>

<p align="center">
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/berserkhmdvhb/agentic-scraper" alt="License"/>
  </a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python" alt="Python"/>
  <a href="https://hub.docker.com/r/hmdvhb/agentic-scraper-frontend">
    <img src="https://img.shields.io/badge/docker-frontend-blue?logo=docker" alt="Docker: Frontend"/>
  </a>
  <a href="https://hub.docker.com/r/hmdvhb/agentic-scraper-backend">
    <img src="https://img.shields.io/badge/docker-backend-blue?logo=docker" alt="Docker: Backend"/>
  </a>
  <img src="https://img.shields.io/badge/lint-ruff-blue?logo=python&logoColor=white" alt="Lint: Ruff"/>
  <a href="https://github.com/berserkhmdvhb/agentic-scraper/actions/workflows/tests.yml">
    <img src="https://github.com/berserkhmdvhb/agentic-scraper/actions/workflows/tests.yml/badge.svg" alt="CI: Tests"/>
  </a>
  <a href="https://coveralls.io/github/berserkhmdvhb/agentic-scraper?branch=main">
    <img src="https://img.shields.io/coveralls/github/berserkhmdvhb/agentic-scraper/main?cacheSeconds=300" alt="Coverage"/>
  </a>
  <a href="https://agenticscraper.onrender.com">
    <img src="https://img.shields.io/badge/frontend-render-blueviolet?logo=render" alt="Frontend"/>
  </a>
  <a href="https://api-agenticscraper.onrender.com">
    <img src="https://img.shields.io/badge/backend-render-blueviolet?logo=render" alt="Backend"/>
  </a>
</p>


## 📑 Table of Contents

- [🚀 Features](#-features)
- [🎥 Demo Video](#-demo-video)
- [⚙️ Tech Stack](#️-tech-stack)
- [📁 Project Structure](#-project-structure)
- [🧰 Installation](#-installation)
  - [👤 For Users](#-for-users)
  - [💼 For Developers](#-for-developers)
  - [🐳 Installing via Docker](#-installing-via-docker-alternative)
- [▶️ Running the App](#%EF%B8%8F-running-the-app)
  - [Prerequisites](#prerequisites)  
  - [Online](#online)
  - [Local](#local)
  - [🐳 Run via Docker](#-run-via-docker)
- [🔧 Environment Configuration (.env)](#-environment-configuration-env)
- [📐 Architecture Diagram](#-architecture-diagram)
- [🧪 How It Works](#-how-it-works)
- [✨ Example Output](#-example-output)
- [🧠 Agent Modes](#-agent-modes)
- [🔬 Scraping Pipeline](#-scraping-pipeline)
  - [🔗 URL Fetching](#-url-fetching-in-fetcherpy)
  - [🧬 Agent Extraction](#-agent-extraction-in-agent)
- [📊 Jobs & Exports](#-jobs--exports)
- [🔌 API (FastAPI)](#-api-fastapi)
- [🔐 Security & Authentication](#-security--authentication)
- [🚀 CI/CD & Deployment](#-cicd--deployment)
  - [🧪 Continuous Integration](#-continuous-integration)
  - [🚀 Continuous Delivery (Render)](#-continuous-delivery-render)
  - [📦 Docker Support](#-docker-support)
- [🗺 Roadmap](#-roadmap)
- [📜 License](#-license)


---

## 🚀 Features

* 🔗 Accepts URLs via paste or `.txt` file upload
* 🔐 Auth0-secured API access using JWT tokens and scope-based control
* 🔒 Encrypted per-user storage of OpenAI API key + project ID
* 🌐 Multiple agent modes (`rule-based`, `llm-fixed`, `llm-dynamic`, `llm-dynamic-adaptive`)
* 🧠 `llm-dynamic` agent automatically decides which fields to extract based on page context and hints.
* 🧠 `llm-dynamic-adaptive` employs retry logic with field scoring, placeholder detection, and self-healing prompt regeneration
* ⚡ Concurrent scraping pipeline with `asyncio` worker pool, granular job progress tracking, and cancellation support
* ✔️ Structured schema validation with `pydantic v2`
* 📸 Optional full-page screenshots via Playwright
* 🔧 Streamlit UI controls for agent mode, model, concurrency, retries, screenshots, and verbosity
* 📊 Jobs tab with real-time job status, cancel button, results overview, and table exports
* 📤 Export scraped data to JSON, CSV, SQLite, or a bundled job package (metadata + results)
* 🧱 Modular backend with FastAPI and dependency-injected authentication & settings

---

## 🎥 Demo Video

https://github.com/user-attachments/assets/b342d0f3-6bed-477f-b657-8c10e0db3eaf

---


## ⚙️ Tech Stack

| Layer                    | Tools                                                |
| ------------------------ | ---------------------------------------------------- |
| **Frontend (UI)**        | `Streamlit`, `streamlit-aggrid`                      |
| **Backend API**          | `FastAPI`, `Pydantic v2`, `uvicorn`                  |
| **Authentication**       | Auth0, OAuth2 (JWT, scopes, tokens)                  |
| **LLM Integration**      | OpenAI Chat API (`gpt-4`, `gpt-3.5-turbo`)           |
| **Async Fetching**       | `httpx`, `asyncio`, `tenacity`                       |
| **HTML Parsing**         | `BeautifulSoup4`                                     |
| **Screenshots**          | `playwright.async_api`                               |
| **Schema Validation**    | `pydantic v2`                                        |
| **Settings & Logging**   | `.env`, `loguru`, centralized messages file          |
| **Credential Storage**   | Encrypted per-user storage via `cryptography`        |
| **Testing**              | `pytest`, fixtures, `httpx.MockTransport`            |
| **Linting & Typing**     | `ruff`, `mypy`                                       |
| **Tooling & Automation** | `Makefile`, `Docker`, GitHub Actions                 |
| **Deployment**           | `Render.com`, Docker Hub (frontend & backend images) |


---


## 📁 Project Structure
### Overview

```
agentic_scraper/
├── .env, sample.env, Makefile, README.md, docker-compose.yml
├── Dockerfile.backend, Dockerfile.frontend
├── pyproject.toml, requirements.txt, poetry.lock
├── run_frontend.py, run_backend.py, run_batch.py
├── .github/workflows/             # GitHub Actions CI/CD workflows
├── docs/                          # Developer and testing docs
├── input/                         # URL input files
├── screenshots/                   # Captured screenshots per scrape
├── tests/                         # Unit and integration tests
└── src/
    └── agentic_scraper/
        ├── backend/               # FastAPI backend
        │   ├── api/               # Routes, auth, lifecycle, schemas, stores
        │   ├── config/            # Constants, messages, aliases, types
        │   ├── core/              # Logger + settings
        │   ├── scraper/           # Fetcher, parser, pipeline, worker pool
        │   └── utils/             # Crypto + validators
        └── frontend/              # Streamlit frontend
            ├── ui_auth*, ui_sidebar, ui_runner, ui_jobs
            └── helpers + display modules
```


### Detailed

```
agentic_scraper/
├── .env                          # Local env config (see sample.env)
├── sample.env                    # Example environment file
├── Makefile                      # Dev commands (lint, type-check, test, docker)
├── README.md                     # Project documentation
├── docker-compose.yml            # Orchestrates frontend and backend containers
├── Dockerfile.backend            # Builds the FastAPI backend image
├── Dockerfile.frontend           # Builds the Streamlit frontend image
├── pyproject.toml                # Project dependencies and tool config
├── requirements.txt              # Exported requirements (pip)
├── poetry.lock                   # Poetry lock file
├── LICENSE                       # License file
├── .github/workflows/            # GitHub Actions CI/CD workflows
│   ├── badge-refresh.yml
│   ├── check-requirements.yml
│   ├── docker-build-backend.yml
│   ├── docker-build-frontend.yml
│   └── tests.yml
├── docs/                         # Additional documentation
├── input/                        # Sample input files
│   ├── urls1.txt
│   └── urls2.txt
├── screenshots/                  # Captured screenshots per scrape
├── tests/                        # Unit and manual tests
│   ├── backend/core/test_settings.py
│   ├── manual/screenshotter_test.py
│   └── manual/validators_test.py
├── run_frontend.py               # CLI launcher for Streamlit UI
├── run_backend.py                # CLI launcher for FastAPI backend
├── run_batch.py                  # CLI for batch scraping via the backend
└── src/
    └── agentic_scraper/
        ├── __init__.py                 # Project version + API version
        ├── backend/
        │   ├── api/
        │   │   ├── lifecycle.py        # Lifespan hooks and shutdown events
        │   │   ├── main.py             # FastAPI app instance and router registration
        │   │   ├── models.py           # Internal/shared API models
        │   │   ├── openapi.py          # Custom OpenAPI schema + JWT bearer support
        │   │   ├── __init__.py
        │   │   ├── auth/
        │   │   │   ├── auth0_helpers.py    # JWKS fetching, token verification
        │   │   │   ├── dependencies.py     # get_current_user dependency (Auth0 JWT)
        │   │   │   ├── scope_helpers.py    # Scope validation for API access control
        │   │   │   └── __init__.py
        │   │   ├── routes/
        │   │   │   ├── auth.py              # Auth/session verification endpoints
        │   │   │   ├── scrape.py            # Start scraping job; list/get jobs
        │   │   │   ├── scrape_cancel_registry.py # In-memory cancel registry helpers
        │   │   │   ├── scrape_helpers.py    # Shared helpers for scrape routes
        │   │   │   ├── user.py              # User profile & OpenAI credential routes
        │   │   │   └── __init__.py
        │   │   ├── schemas/
        │   │   │   ├── items.py             # Shared item schemas for API responses
        │   │   │   ├── scrape.py            # Scrape request/response models
        │   │   │   ├── user.py              # User & credential models
        │   │   │   └── __init__.py
        │   │   ├── stores/
        │   │   │   ├── job_store.py         # In-memory job store (status, progress, pagination)
        │   │   │   ├── user_store.py        # Encrypted OpenAI credentials store
        │   │   │   └── __init__.py
        │   │   └── utils/
        │   │       ├── log_helpers.py       # Logging utilities for API events
        │   │       └── __init__.py
        │   ├── config/
        │   │   ├── aliases.py               # Field alias mappings
        │   │   ├── constants.py             # Global defaults/limits
        │   │   ├── messages.py              # Centralized logging/UI message constants
        │   │   ├── types.py                 # Enums and strong-typed field definitions
        │   │   └── __init__.py
        │   ├── core/
        │   │   ├── logger_helpers.py        # Helpers for structured logging output
        │   │   ├── logger_setup.py          # Loguru configuration and rotation
        │   │   ├── settings.py              # Pydantic settings model with env validation
        │   │   ├── settings_helpers.py      # Custom parsing/coercion/default resolution
        │   │   └── __init__.py
        │   ├── scraper/
        │   │   ├── fetcher.py               # Async HTML fetcher (httpx + retries)
        │   │   ├── models.py                # ScrapedItem and related models
        │   │   ├── parser.py                # HTML cleanup & content distillation
        │   │   ├── pipeline.py              # Orchestration of full scrape flow
        │   │   ├── schemas.py               # Internal scraping schemas
        │   │   ├── screenshotter.py         # Playwright screenshots (optional)
        │   │   ├── worker_pool.py           # Async workers, progress updates, cancellation
        │   │   ├── worker_pool_helpers.py   # Worker pool utilities
        │   │   ├── __init__.py
        │   │   └── agents/
        │   │       ├── agent_helpers.py     # Agent utilities (scoring, error handling)
        │   │       ├── field_utils.py       # Field normalization, scoring, placeholder detection
        │   │       ├── llm_dynamic.py       # Context-driven LLM extraction (recommended)
        │   │       ├── llm_dynamic_adaptive.py # Adaptive retries + discovery for completeness
        │   │       ├── llm_fixed.py         # Fixed-schema extraction with static prompt
        │   │       ├── prompt_helpers.py    # Prompt construction (initial + retry)
        │   │       ├── rule_based.py        # Heuristic baseline without LLM
        │   │       └── __init__.py
        │   └── utils/
        │       ├── crypto.py                # AES encrypt/decrypt user credentials
        │       ├── validators.py            # URL & input validation
        │       └── __init__.py
        └── frontend/
            ├── __init__.py
            ├── app.py                       # Streamlit entrypoint
            ├── app_helpers.py               # Frontend helpers (formatting, utilities)
            ├── models.py                    # Sidebar + pipeline config models
            ├── ui_auth.py                   # Auth0 login + token flow
            ├── ui_auth_credentials.py       # OpenAI credential input & validation
            ├── ui_auth_helpers.py           # Auth helpers (fetch status, error handling)
            ├── ui_display.py                # Grid/table visualization of results
            ├── ui_effects.py                # Spinners, banners, toasts
            ├── ui_jobs.py                   # Jobs tab: overview, results, exports, cancel
            ├── ui_page_config.py            # Layout, environment badges, log path
            ├── ui_runner.py                 # Async scrape runner (calls backend API)
            ├── ui_runner_helpers.py         # URL dedupe, pre-processing, progress UI
            └── ui_sidebar.py                # Full sidebar rendering: model/agent/retries
```



---

## 🧰 Installation

### 👤 For Users


**Recommended: Clone and install:**

```bash
git clone https://github.com/berserkhmdvhb/agentic-scraper.git
cd agentic-scraper
make install
```

Or manually:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```
> This installs the app in editable mode with runtime-only dependencies from `pyproject.toml`.


**Alternative: Install from GitHub without cloning**

```bash
pip install git+https://github.com/berserkhmdvhb/agentic-scraper.git
```

> Useful for trying the package without cloning. Not needed if using `make install`


**If required to use `requirements.txt`**:

```bash
pip install -r requirements.txt
```

> ⚠️ `requirements.txt` is auto-generated via `poetry export`.
> Commits check automatically if it's synched with `pyproject.toml`


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
pip install -e .[dev]
```

> This installs the app in developer mode with `[dev]` dependencies from `pyproject.toml`.

#### **Setup Playwright (for screenshots):**

```bash
playwright install
```

>  Screenshots require installing Playwright separately. [Install docs →](https://playwright.dev/python/docs/intro)

---

### 🐳 Installing via Docker (Alternative)
You can also install the app using prebuilt Docker images from Docker Hub.

- 🔗 **Frontend Image:** [![](https://img.shields.io/badge/docker-frontend-blue?logo=docker)](https://hub.docker.com/r/hmdvhb/agentic-scraper-frontend)
- 🔗 **Backend Image:** [![](https://img.shields.io/badge/docker-backend-blue?logo=docker)](https://hub.docker.com/r/hmdvhb/agentic-scraper-backend)

Pull the images manually:

```bash
docker pull hmdvhb/agentic-scraper-frontend
docker pull hmdvhb/agentic-scraper-backend
```

---

## ▶️ Running the App

### Prerequisites

* ✅ Python 3.10+
* ✅ `.env` configured (see [🔧 Environment Configuration (.env)](#-environment-configuration-env))
* ✅ Auth0 application + API configured (issuer/audience/client id & client secret/scopes).
Required for login, saving OpenAI creds, and starting scrapes (see [Setup Auth0](#setup-auth0)).
* *(Optional)* Playwright installed if you enable screenshots: `playwright install`

### Online
 Visit the hosted version domains here:  

- 🔗 **Frontend (Streamlit UI):** [![CD: Frontend Deploy](https://img.shields.io/badge/frontend-render-blueviolet?logo=render)](https://agenticscraper.onrender.com)
- 🔗 **Backend (FastAPI API):** [![CD: Backend Deploy](https://img.shields.io/badge/backend-render-blueviolet?logo=render)](https://api-agenticscraper.onrender.com)

### Local
#### Frontend UI (Streamlit):

```bash
python run_frontend.py
```

or directly:

```bash
streamlit run src/agentic_scraper/frontend/app.py
```

#### Backend API (FastAPI):

```bash
python run_backend.py
```

or directly:

```bash
 uvicorn src.agentic_scraper.backend.api.main:app --reload
```

#### Batch mode (CLI trigger via backend):

```bash
python run_batch.py --input input/urls1.txt --agent-mode llm-dynamic --model gpt-4o
```


### 🐳 Run via Docker

To launch both frontend and backend locally using Docker Compose:

```bash
docker-compose up --build
```
Makefile shortcuts:

```bash
make docker-up
make docker-build
```

Then open:

- Frontend: http://localhost:8501
- Backend: http://localhost:8000




---


## 🔧 Environment Configuration (.env)

Use [`sample.env`](https://github.com/berserkhmdvhb/agentic-scraper/blob/main/sample.env) as a reference and create a `.env` in the project root. The backend will refuse to start without valid values for the required keys below.

### Required (minimum to boot)

- `ENCRYPTION_SECRET`: 32‑byte Fernet key used to encrypt per‑user OpenAI credentials.

  - Generate one:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If you haven't installed the dependencies, you need at least the package `cryptography` for this:

```bash
pip install cryptography
```

2. `AUTH0_ISSUER`: Your Auth0 tenant issuer with trailing slash, e.g.

`https://dev-xxxxx.us.auth0.com/`

3. `AUTH0_API_AUDIENCE`: Your API identifier, which should be set as your backend domain:

`https://your-backend-domain.com/`


To setup auth0, see [Setup Auth0](#setup-auth0).



Example of `.env` values:

```ini
# Logging
LOG_LEVEL=INFO

# Public domains (used in UI and redirects)
FRONTEND_DOMAIN=https://agenticscraper.onrender.com
BACKEND_DOMAIN=https://api-agenticscraper.onrender.com

# Auth0 (REQUIRED)
AUTH0_ISSUER=https://dev-xxxxx.us.auth0.com/
AUTH0_API_AUDIENCE=https://6d35bd763370.ngrok-free.app/

# Crypto (REQUIRED)
ENCRYPTION_SECRET=<paste Fernet key here>

# Defaults
AGENT_MODE=llm-dynamic
SCREENSHOTS_ENABLED=false
FETCH_CONCURRENCY=6
LLM_CONCURRENCY=2
OPENAI_MODEL=gpt-4o
...

```

### Notes

* The Streamlit UI can override some settings at runtime via the sidebar.
* Auth flows and scraping require a working Auth0 setup (see [Setup Auth0](#setup-auth0)).
* OpenAI API key & project ID are provided by the user in the UI and stored encrypted by the backend using `ENCRYPTION_SECRET`.


---


## 📐 Architecture Diagram

https://lucid.app/lucidchart/3fb8cd99-6bee-44ba-8f47-87e8de28ea95/view

<img width="5550" height="6305" alt="AS_Architecture_online" src="https://github.com/user-attachments/assets/22a16c18-3db9-476d-8147-b380b0ca63fc" />


---

## 🧪 How It Works

1. **Authenticate & Provide Credentials**

   * User signs in via **Auth0** from the Streamlit UI.
   * User optionally saves **OpenAI API key** and **Project ID** to the backend; they’re AES‑encrypted with `ENCRYPTION_SECRET`.

2. **Submit URLs from the UI**

   * Paste URLs or upload a `.txt` file.
   * Pick the **agent mode** (recommended: `llm-dynamic`), **model**, and performance settings (concurrency, retries, screenshots).

3. **Backend Receives a Scrape Job**

   * The UI calls `POST /api/v1/scrape/start` with URLs + config.
   * A job is created in the **in‑memory job store** with status `QUEUED` → `RUNNING`.
   * The job id is returned to the UI for progress tracking.

4. **Fetch Stage (Async)**

   * `fetcher.py` uses `httpx.AsyncClient` + retries to download HTML concurrently.
   * Each fetched item includes original/final URL, status, headers, and HTML.

5. **Parse Stage**

   * `parser.py` cleans HTML and distills main content (title/body/meta) for the agents.

6. **Agent Extraction**

   * `agents/` run per‑URL. Modes:

     * `rule_based` — heuristic, fast, no LLM.
     * `llm_fixed` — strict fixed schema.
     * `llm_dynamic` — **context‑driven selection of fields** for better quality/perf (recommended default).
     * `llm_dynamic_adaptive` — adds retries with field scoring + placeholder detection to maximize completeness.

7. **Validation & Retries**

   * Outputs are validated against `ScrapedItem` schemas.
   * Adaptive mode may retry with refined prompts targeting missing/placeholder fields.

8. **Optional Screenshots**

   * If enabled, `screenshotter.py` captures page screenshots via Playwright and associates paths with results.

9. **Progress, Cancellation, Finalization**

   * `worker_pool.py` emits granular progress updates to the job store.
   * The job can be **canceled** mid‑run; the backend honors cancelability.
   * On completion, the job is finalized with `SUCCEEDED`/`FAILED` and includes **results + stats**.

10. **UI: Results & Exports**

* The Streamlit UI polls job status, shows progress and results.
* The **Jobs** tab provides Overview/Results views, **cancel** button, and exports: **JSON / CSV / SQLite** or a **full job package** (results + metadata).

---


### ✨ Example Output

Input URL: https://www.amazon.com/Beats-Solo-Wireless-Headphones-Matte/dp/B0CZPLV566

<img width="1505" height="537" alt="display" src="https://github.com/user-attachments/assets/31f5ff36-6885-48c8-bedf-5da595c5c000" />



```json
[
  {
    "title":"Beats Solo 4 - Wireless Bluetooth On-Ear Headphones, Apple & Android Compatible, Up to 50 Hours of Battery Life - Matte Black",
    "description":null,
    "price":null,
    "author":"Beats",
    "date_published":null,
    "page_type":"product",
    "summary":"Wireless Bluetooth On-Ear Headphones, Apple & Android Compatible, Up to 50 Hours of Battery Life - Matte Black",
    "company":"Amazon.com",
    "location":"Deliver to Germany",
    "date":null,
    "product_features":{
      "Compatibility":"Apple & Android Compatible",
      "Battery Life":"Up to 50 Hours",
      "Color":"Matte Black",
      "Wireless":"Bluetooth"
    },
    "product_specifications":{
      "Brand":"Beats",
      "Type":"On-Ear Headphones",
      "Connectivity":"Wireless Bluetooth"
    },
    "ratings":"4.6 out of 5 stars",
    "reviews_count":"15,382",
    "return_policy":"FREE returns, 30-day refund\/replacement",
    "shipping_info":"Ships from and sold by Amazon.com",
    "seller":"Amazon.com",
    "quantity_available":"30",
    "product_support_included":true,
    "secure_transaction":true,
    "gift_options_available":true,
    "other_sellers_on_amazon":true,
    "new_and_used_offers":"New & Used (9) from $122.46 & FREE Shipping",
    "url":"https:\/\/www.amazon.com\/Beats-Solo-Wireless-Headphones-Matte\/dp\/B0CZPLV566\/"
  }
]
```

---

## 🧠 Agent Modes

| Mode                   | Description                                                                  |
|------------------------|------------------------------------------------------------------------------|
| `rule-based`           | Heuristic parser using regex and basic rules — fast, LLM-free baseline               |
| `llm-fixed`            | Extracts a fixed predefined schema (e.g. title, price, author)                        |
| `llm-dynamic`          | Context-driven LLM extraction that automatically decides which fields to extract per page     |
| `llm-dynamic-adaptive` | Retry-aware variant: adds field scoring, placeholder detection, and self-healing retries for maximum completeness  |

### Notes

* 💡 Recommended: Use `llm-dynamic` for the best balance of quality and performance.

* The UI dynamically adapts to the selected mode — model selection and retry sliders appear only for LLM-based modes.

* All LLM modes use the OpenAI ChatCompletion API (`gpt-4`, `gpt-3.5-turbo`). See [`agents.md`](https://github.com/berserkhmdvhb/agentic-scraper/blob/main/docs/agents.md) 


---


## 🔬 Scraping Pipeline

<img width="2842" height="1572" alt="ScrapingPipeline" src="https://github.com/user-attachments/assets/ae49f6d4-831a-467c-a0f3-08c511fa7584" />

The scraping pipeline has three main stages:

* **🔗 URL Fetching** — Retrieves raw HTML + metadata.
* **🧹 Parse Stage** — Cleans HTML and distills main content for analysis.
* **🧬 Agent Extraction** — Parses content and extracts structured data using rule-based or LLM agents.

These stages are modular and can be extended independently.



### 🔗 URL Fetching (in `fetcher.py`)

* Implemented with `httpx.AsyncClient` for concurrent requests.
* Retries handled via `tenacity` with exponential backoff.
* Produces a `FetchedDocument` containing:

  * Original + final URL (after redirects)
  * Status code & headers
  * Raw HTML
  * Metadata (domain, fetch timestamp)

**Features:**

* Async concurrency with `asyncio.gather`
* Retry/backoff on failures
* Realistic headers & timeouts
* Optionally triggers screenshot capture



### 🧹 Parse Stage (in `parser.py`)

* Cleans raw HTML (removes boilerplate, scripts/styles, noisy elements).
* Distills **main content** (title, meta description, primary text/body) and normalizes whitespace.
* Extracts lightweight page metadata (canonical URL, domain, timestamps when available).
* Outputs a structured object (e.g., `ParsedContent`) used as the **input to agents**.

**Why it matters:**

* Reduces token and noise for LLMs, improving extraction quality and speed.
* Provides consistent fields (title/body/meta) regardless of source markup quirks.


### 🧬 Agent Extraction (in `agents/`)

* Runs after parsing/cleaning.
* Supports multiple strategies:

  * `rule_based` (fast heuristics)
  * `llm_fixed` (fixed schema)
  * `llm_dynamic` (context-driven, **recommended**)
  * `llm_dynamic_adaptive` (adds retries + scoring)
* Validates results against `ScrapedItem` schema.
* Adaptive retries regenerate prompts for missing/placeholder fields.



### Progress, Cancellation, Jobs

* The **worker pool** processes URLs concurrently and updates job progress.
* Jobs are stored in the in-memory `job_store` with status + progress.
* Cancel requests are honored mid-run: canceled jobs never flip back to succeeded.
* On completion, jobs finalize with `SUCCEEDED` or `FAILED`, plus results + stats.

---


## 📊 Jobs & Exports

All scraping runs are tracked as **jobs** in the backend. Jobs provide real‑time progress, cancellation, and export options.

### Job Lifecycle

* Jobs are created with status `QUEUED` → `RUNNING` → `SUCCEEDED`/`FAILED`.
* Progress (`0.0 – 1.0`) updates as items are processed.
* Cancel requests set status to `CANCELED` and prevent overwriting with success.
* Each job stores results, errors, and execution stats.

### Jobs Tab (Frontend)

* **Overview** tab: status, progress bar, timestamps, config.
* **Results** tab: interactive Ag‑Grid table with filtering/sorting.
* **Cancel button** for active jobs.
* Compact UI for quick inspection of URLs.

### Export Options

* **Table exports**: JSON, CSV, SQLite (filenames include `job_id`).
* **Job package download**: full payload with results + metadata + stats.
* Exports are available directly from the Jobs tab.

---

## 🔌 API (FastAPI)

The backend exposes a **versioned REST API** under `/api/v1/`, powered by FastAPI. Most routes use **Auth0 JWT Bearer authentication** with **scope-based access control** — **except** the OAuth2 callback, which is public by design.

### Authentication

* Endpoints require a valid Bearer token:

  ```http
  Authorization: Bearer eyJhbGciOiJ...
  ```
* Tokens are verified against Auth0 JWKS.
* Scope validation is done via `scope_helpers.check_required_scopes()`.

### Key Routes (as implemented)

#### `auth/`

| Endpoint                | Method | Description                                                               | Scope                |
| ----------------------- | ------ | ------------------------------------------------------------------------- | -------------------- |
| `/api/v1/auth/callback` | GET    | OAuth2 callback: exchanges Auth0 `code` → access token, then redirects UI | **public (no auth)** |

#### `user/`

| Endpoint                                 | Method | Description                                          | Scope                       |
| ---------------------------------------- | ------ | ---------------------------------------------------- | --------------------------- |
| `/api/v1/user/me`                        | GET    | Return authenticated user's profile                  | `read:user_profile`         |
| `/api/v1/user/openai-credentials`        | GET    | Retrieve stored OpenAI API key + project ID (if any) | `read:user_profile`         |
| `/api/v1/user/openai-credentials/status` | GET    | Return existence/health status of saved credentials  | `read:user_profile`         |
| `/api/v1/user/openai-credentials`        | PUT    | Create/update encrypted OpenAI credentials           | `create:openai_credentials` |
| `/api/v1/user/openai-credentials`        | DELETE | Delete stored OpenAI credentials                     | `delete:user_account`       |

#### `scrape/`

| Endpoint                  | Method | Description                              | Scope            |
| ------------------------- | ------ | ---------------------------------------- | ---------------- |
| `/api/v1/scrape/`         | POST   | Start a scraping job (returns `job_id`)  | `create:scrapes` |
| `/api/v1/scrape/`         | GET    | List jobs (pagination/filters supported) | `read:scrapes`   |
| `/api/v1/scrape/{job_id}` | GET    | Get job status and results               | `read:scrapes`   |
| `/api/v1/scrape/{job_id}` | DELETE | Cancel a running job                     | `cancel:scrapes` |

### Example: Start a Job

```http
POST /api/v1/scrape/
Authorization: Bearer <token>
Content-Type: application/json

{
  "urls": ["https://example.com/page1", "https://example.com/page2"],
  "agent_mode": "llm-dynamic",
  "llm_model": "gpt-4"
}
```

**Response:**

```json
{
  "job_id": "abc123",
  "status": "QUEUED"
}
```

### Notes

* Interactive API docs at `/docs` (Swagger UI) with JWT auth.
* Schemas defined in `backend/api/schemas/*`.
* Job lifecycle & cancellation logic enforced by `job_store.py`.
* OAuth2 callback uses `settings.auth0_redirect_uri` and redirects to `FRONTEND_DOMAIN` with `?token=...` or `?error=...`.
* Scopes above reflect your **Auth0 API permissions** and must be assigned to users in Auth0 for the corresponding actions.




## 🔐 Security & Authentication

AgenticScraper uses **Auth0** for authentication and **JWT Bearer tokens** for securing the API. Tokens are verified against Auth0 **JWKS** and checked for expiration and scopes.

### How it works

* **Frontend (Streamlit)** initiates login and receives a redirect to the backend.
* **Backend** handles the OAuth2 callback at `/api/v1/auth/callback`, exchanges the `code` for an access token, and redirects back to the frontend with `?token=...` (or `?error=...`).
* The **JWT** is stored in the Streamlit session and attached to API calls as `Authorization: Bearer ...`.
* FastAPI dependencies (`get_current_user`) validate the token using Auth0 JWKS. Scopes are enforced with `scope_helpers.py`.

### Required Auth0 Configuration

1. **Applications**

   * Create a **Regular Web Application** for the Streamlit UI.
   * Enable **Machine-to-Machine** access if you need server-to-server token flows (optional).
2. **API**

   * Create an **Auth0 API** with an identifier (the **audience**) — **must end with a trailing slash** (e.g., `https://your-ngrok-or-domain/`).
3. **Allowed Callback URLs** (on the Application)

   * Set to your backend callback URL, e.g., `https://<BACKEND_DOMAIN>/api/v1/auth/callback`.
4. **Allowed Logout / CORS URLs**

   * Include both `FRONTEND_DOMAIN` and `BACKEND_DOMAIN`.
5. **Scopes**

   * At minimum: `read:user_profile` (used for all protected routes in the current setup).
   * You can introduce granular scopes later (e.g., `create:openai_credentials`) and enforce them in `scope_helpers.py`.

### .env settings

* `AUTH0_ISSUER` — e.g., `https://dev-xxxxx.us.auth0.com/` (**trailing slash required**)
* `AUTH0_API_AUDIENCE` — e.g., `https://6d35bd763370.ngrok-free.app/` (**trailing slash required**)
* `FRONTEND_DOMAIN` / `BACKEND_DOMAIN` — used in redirects and CORS.

### Implementation Notes

* **JWT verification** & JWKS caching: `backend/api/auth/auth0_helpers.py`
* **Dependency** (`get_current_user`): `backend/api/auth/dependencies.py`
* **Scope checks**: `backend/api/auth/scope_helpers.py`
* **OAuth2 callback**: `backend/api/routes/auth.py`
* **Message constants** (no raw strings): `backend/config/messages.py`

> If JWKS fetch fails (wrong issuer or missing slash), token verification will fail. Double‑check the issuer and audience values in `.env`.



---

## 🚀 CI/CD & Deployment

### 🧪 Continuous Integration

* **GitHub Actions** run on every push/PR:

  * Linting (`ruff`) and type checks (`mypy`)
  * Unit tests (`pytest`)
  * Requirements drift check (Poetry → requirements.txt)

### 🚀 Delivery / Hosting

* Reference deployments are hosted on **Render.com** (Frontend & Backend). See the links in the header.
* Docker images can be built locally or pulled from Docker Hub.

### 📦 Docker Support

* `Dockerfile.backend` — builds the FastAPI backend
* `Dockerfile.frontend` — builds the Streamlit frontend
* `docker-compose.yml` — orchestrates both services for local dev or a single-box deployment

**Local with Docker Compose:**

```bash
docker-compose up --build
```

**Pull prebuilt images:**

```bash
docker pull hmdvhb/agentic-scraper-frontend
docker pull hmdvhb/agentic-scraper-backend
```

### Notes

* Production deployments should configure `FRONTEND_DOMAIN` and `BACKEND_DOMAIN` with HTTPS.
* For uptime checks, consider adding a public `/health` endpoint to the backend.
* Secrets (Auth0 keys, encryption key) must be provided via environment variables in your host.


---

## 🗺 Roadmap

* [x] Self-healing retry loop for LLM
* [x] Field scoring to prioritize important fields
* [x] Conditional UI for agent settings
* [x] FastAPI backend (in progress)
* [x] Docker container deployment
* [ ] Multilingual support + auto-translation
* [ ] Increase test coverage
* [ ] Add agentic workflow to classify and contextualize input URLs and feed that to other models
* [ ] Add DELETE, POST, and PATCH operatoins on FastAPI for the route `user/openai-credentails`
* [ ] In scraping pipeline, fetching and scraping are sequential operations, find a robust and clean way to parallelize them.
* [ ] Use Playwright do explore the page and add more content before feeding to scraping pipeline.
* [x] User authentication with Auth0
* [x] Authentication protocol with OAuth2 and JWT

---

## 📜 License

MIT License
