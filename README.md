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
- [🧠 Agent Modes](#-agent-modes)
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
- [🔬 Scraping Architecture](#-scraping-architecture)
  - [🔗 URL Fetching](#-url-fetching-in-fetcherpy)
  - [🧬 Agent Extraction](#-agent-extraction-in-agent)
- [🔌 API (FastAPI)](#-api-fastapi)
- [🧠 Adaptive Retry Logic](#-adaptive-retry-logic-for-llm-agents)
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
* 🔒 Encrypted OpenAI credential storage per user
* 🌐 Multiple agent modes (`rule-based`, `llm-fixed`, `llm-dynamic`, `llm-dynamic-adaptive`)
* 🧠 Adaptive retry logic that self-heals missing fields via prompt regeneration
* ⚡ Concurrent scraping pipeline with `httpx`, `asyncio`, and retries via `tenacity`
* ✔️ Structured schema validation using `pydantic v2`
* 📸 Optional full-page screenshots via Playwright
* 🔧 UI controls for agent config, model selection, concurrency, retries, and verbosity
* 📤 Export scraped data to CSV, JSON, or SQLite
* 🧱 Modular backend with FastAPI and dependency-injected authentication & settings

---

## 🎥 Demo Video

https://github.com/user-attachments/assets/b342d0f3-6bed-477f-b657-8c10e0db3eaf

---


# ⚙️ Tech Stack

| Layer                    | Tools                                                |
| ------------------------ | ---------------------------------------------------- |
| **Frontend (UI)**        | `Streamlit`, `streamlit-aggrid`                      |
| **Backend API**          | `FastAPI`, `Pydantic`, `uvicorn`                     |
| **Authentication**       | Auth0, OAuth2 (JWT, scopes, tokens)                  |
| **LLM Integration**      | OpenAI ChatCompletion API (`gpt-4`, `gpt-3.5-turbo`) |
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

## 🧠 Agent Modes

| Mode                   | Description                                                                  |
|------------------------|------------------------------------------------------------------------------|
| `rule-based`           | Heuristic parser using BeautifulSoup — fast, LLM-free baseline               |
| `llm-fixed`            | Extracts a fixed predefined schema (e.g. title, price)                        |
| `llm-dynamic`          | LLM selects relevant fields based on page content and contextual hints       |
| `llm-dynamic-adaptive` | Adds retries, field scoring, and placeholder detection for better coverage   |

> 💡 Recommended: Use `llm-dynamic` for the best balance of quality and performance.

> The UI dynamically adapts to the selected mode — model selection and retry sliders appear only for LLM-based modes.

> All LLM modes use the OpenAI ChatCompletion API (`gpt-4`, `gpt-3.5-turbo`).

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
src/
└── agentic_scraper/
    ├── __init__.py                    # Project version + API version
    ├── backend/
    │   ├── api/
    │   │   ├── lifecycle.py           # Lifespan hooks and shutdown events
    │   │   ├── main.py                # FastAPI app factory and router registration
    │   │   ├── models.py              # Internal shared models
    │   │   ├── openapi.py             # Custom OpenAPI schema and JWT support
    │   │   ├── user_store.py          # Secure OpenAI credential storage
    │   │   ├── auth/
    │   │   │   ├── auth0_helpers.py   # JWKS fetching, token decoding, Auth0 utilities
    │   │   │   ├── dependencies.py    # FastAPI auth dependencies (e.g. get_current_user)
    │   │   │   ├── scope_helpers.py   # Scope validation logic for API access control
    │   │   ├── routes/
    │   │   │   └── v1/
    │   │   │       ├── auth.py        # Endpoint for token and session verification
    │   │   │       ├── scrape.py      # Main scraping initiation endpoint
    │   │   │       ├── user.py        # User profile, credential, and config routes
    │   │   ├── schemas/
    │   │   │   ├── scrape.py          # Pydantic models for scrape requests/responses
    │   │   │   ├── user.py            # Pydantic models for user authentication and config
    │   │   ├── utils/
    │   │   │   ├── log_helpers.py     # Logging utilities for API events
    │   ├── config/
    │   │   ├── aliases.py             # Field alias mappings
    │   │   ├── constants.py           # Global default values and limits
    │   │   ├── messages.py            # Centralized UI/logging message constants
    │   │   ├── types.py               # Enums and strong-typed field definitions
    │   ├── core/
    │   │   ├── logger_helpers.py      # Helpers for structured log output
    │   │   ├── logger_setup.py        # Loguru configuration and rotation
    │   │   ├── settings.py            # Pydantic settings model with env validation
    │   │   ├── settings_helpers.py    # Custom parsing, coercion, and default resolution
    │   ├── scraper/
    │   │   ├── fetcher.py             # HTML fetcher with `httpx`, headers, and retry logic
    │   │   ├── models.py              # Shared `ScrapedItem` schema
    │   │   ├── parser.py              # HTML cleanup and content distillation
    │   │   ├── pipeline.py            # Orchestration logic for full scrape flow
    │   │   ├── screenshotter.py       # Playwright screenshot capture (optional)
    │   │   ├── worker_pool.py         # Async scraping task manager using asyncio.Queue
    │   │   └── agent/
    │   │       ├── agent_helpers.py   # Agent-level utilities (scoring, error handling)
    │   │       ├── field_utils.py     # Field normalization, scoring, placeholder detection
    │   │       ├── llm_dynamic.py     # LLM agent for context-based dynamic field extraction
    │   │       ├── llm_dynamic_adaptive.py  # LLM agent with retries and field prioritization
    │   │       ├── llm_fixed.py       # Fixed-schema extractor using a static prompt
    │   │       ├── prompt_helpers.py  # Prompt construction for first and retry passes
    │   │       ├── rule_based.py      # Fast, deterministic parser without LLMs
    │   ├── utils/
    │       ├── crypto.py              # AES encryption/decryption of user credentials
    │       ├── validators.py          # URL and input validation logic
    └── frontend/
        ├── app.py                     # Streamlit entrypoint for launching the UI
        ├── models.py                  # Sidebar config model and pipeline config
        ├── ui_auth.py                 # Auth0 login + token management
        ├── ui_auth_credentials.py     # OpenAI credential input and validation
        ├── ui_display.py              # Grid/table visualization of extracted results
        ├── ui_effects.py              # UI effects: spinners, banners, toasts
        ├── ui_page_config.py          # Layout, environment badge, log path config
        ├── ui_runner.py               # Async scrape runner using backend API
        ├── ui_runner_helpers.py       # URL deduplication, fetch pre-processing, display
        ├── ui_sidebar.py              # Full sidebar rendering: model, agent, retries, etc.
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


#### 🐳 Installing with Docker (Alternative)
You can also install the app using prebuilt Docker images from Docker Hub.
https://hub.docker.com/r/hmdvhb/agentic-scraper-backend

- 🔗 **Frontend Image:** [![](https://img.shields.io/badge/docker-frontend-blue?logo=docker)](https://hub.docker.com/r/hmdvhb/agentic-scraper-frontend)
- 🔗 **Backend Image:** [![](https://img.shields.io/badge/docker-frontend-blue?logo=docker)](https://hub.docker.com/r/hmdvhb/agentic-scraper-backend)

Pull the images manually:

```bash
docker pull hmdvhb/agentic-scraper-backend
docker pull hmdvhb/agentic-scraper-frontend
```


---

## ▶️ Running the App
Note that when the app is launched, it shows you button for login (redirects to Auth0 page) on sidebar, and then prompts an OpenAI API key and Project key.
Whe these are provided, you could enter URLs to scrape.

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


### 🐳 Run via Docker

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

> ⚙️ Ensure you have `.env` configured before running containers.The backend requires Auth0 and OpenAI credentials at runtime.You can mount volumes or use env_file: in docker-compose.yml to inject secrets.


---


## 🔧 Environment Configuration (.env)

```ini
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


## 🔌 API (FastAPI)

The AgenticScraper backend is powered by **FastAPI** and exposes a versioned REST API under the `/api/v1/` prefix. All routes use **JWT Bearer authentication** via Auth0 and enforce **scope-based access control**.



### 🔐 Authentication

All endpoints (except `/auth/callback`) require a valid **Bearer token** issued by Auth0:

```http
Authorization: Bearer eyJhbGciOiJ...
```

Tokens are verified using Auth0's JWKS endpoint and validated for expiration, signature, and required scopes.



### 🧭 Available Routes

| Endpoint                          | Method | Description                                          | Auth Scope           |
| --------------------------------- | ------ | ---------------------------------------------------- | -------------------- |
| `/api/v1/auth/callback`           | GET    | OAuth2 callback: exchanges Auth0 code for JWT        | public (no auth)     |
| `/api/v1/user/me`                 | GET    | Returns authenticated user's profile                 | `read:user_profile`  |
| `/api/v1/user/openai-credentials` | GET    | Retrieves stored OpenAI API key & project ID         | `read:user_profile`  |
| `/api/v1/user/openai-credentials` | POST   | Stores OpenAI credentials for future scrape requests | `create:openai_credentials` |
| `/api/v1/scrape/start`            | POST   | Launches scraping pipeline with given URL list       | `read:user_profile`  |



### 🧪 Example: Scrape Request

```http
POST /api/v1/scrape/start
Authorization: Bearer <your_token>
Content-Type: application/json

{
  "urls": [
    "https://example.com/page1",
    "https://example.com/page2"
  ],
  "agent_mode": "llm-dynamic",
  "llm_model": "gpt-4"
}
```

#### Response

```json
{
  "results": [...],
  "stats": {
    "total": 2,
    "successful": 2,
    "duration_seconds": 6.2
  }
}
```



### 🧩 API Design Notes

* **Versioning**: All endpoints are served under `/api/v1/`
* **Schemas**: Defined with `pydantic` in the `schemas/` module
* **Security**: JWT validation via FastAPI dependencies (`get_current_user`)
* **Scope Enforcement**: Done via `check_required_scopes()` helper
* **OpenAPI UI**: Visit `/docs` (with token input) for interactive API explorer


## 🧠 Adaptive Retry Logic (for LLM Agents)

Only the `llm-dynamic-adaptive` agent supports **field-aware retrying** when critical fields (e.g. `title`, `price`, `job_title`) are missing.

### How It Works:

1. Performs an initial LLM extraction attempt.
2. Evaluates field coverage using `field_utils.score_fields()`.
3. If important fields are missing, it re-prompts with hints and context.
4. Repeats up to `LLM_SCHEMA_RETRIES` times.
5. Returns the best-scoring result among attempts.

→ Enables **self-healing extraction** and **schema robustness** on diverse webpages.

```
[LLM Response] ──> parse_llm_response() ──┐
                                         ↓
                              check missing fields (raw)
                                         ↓
                           retry missing fields if needed
                                         ↓
                          choose best or fallback candidate
                                         ↓
                            normalize_fields() final only
                                         ↓
                          validate with ScrapedItem schema


[LLM Response] ──> parse_llm_response() ──┐
                                         ↓
               extract raw_fields, evaluate new content
                                         ↓
       update all_fields with new non-empty / non-placeholder values
                                         ↓
  check: did we fill all required fields? → Yes → skip further retries
                                         ↓
  if score improved or new fields appeared → update best_fields
                                         ↓
             generate retry prompt for next missing or weak fields
                                         ↓
     ┌──────────┐        ...next pass...        ┌────────────┐
     │ Retry N+1│ ─────────────────────────────> │ Retry N+2 …│
     └──────────┘                               └────────────┘
                                         ↓
             fallback to best_fields or best_valid_item
                                         ↓
               normalize_fields() ← on final best only
                                         ↓
             validate with ScrapedItem schema (final)
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
* [ ] Increase test coverage
* [x] User authentication with Auth0
* [x] Authentication protocol with OAuth2 and JWT

---

## 📜 License

MIT License
