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
- [🔌 API (FastAPI)](#-api-fastapi)
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
Note that when the app is launched, it shows you button for login (redirects to Auth0 page) on sidebar, and then prompts an OpenAI API key and Project key.
Whe these are provided, you could enter URLs to scrape.

> ⚙️ Ensure you have `.env` configured before running. The backend requires Auth0 and domain values at runtime. You can create a `.env` file.
>  See [`sample.env`](https://github.com/berserkhmdvhb/agentic-scraper/blob/main/sample.env) as example.

### Online
 Visit the hosted version domains here:  

- 🔗 **Frontend (Streamlit UI):** [![CD: Frontend Deploy](https://img.shields.io/badge/frontend-render-blueviolet?logo=render)](https://agenticscraper.onrender.com)
- 🔗 **Backend (FastAPI API):** [![CD: Backend Deploy](https://img.shields.io/badge/backend-render-blueviolet?logo=render)](https://api-agenticscraper.onrender.com)

### Local

To launch the frontend, start the Streamlit UI:

```bash
streamlit run src/agentic_scraper/frontend/app.py
```

Or, use the shortcut:

```bash
python run.py
```

To launch the backend, run the Uvicorn server:

```bash
 uvicorn src.agentic_scraper.backend.api.main:app --reload
```


> ⚙️ Ensure you have `.env` configured before running containers. The backend requires Auth0 and domain values at runtime. You can mount volumes or use env_file: in `docker-compose.yml` to inject secrets.
>  See [`sample.env`](https://github.com/berserkhmdvhb/agentic-scraper/blob/main/sample.env) as example.


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

> ⚙️ Ensure you have `.env` configured before running containers. The backend requires Auth0 and OpenAI credentials at runtime. You can mount volumes or use env_file: in `docker-compose.yml` to inject secrets.
>  See [`sample.env`](https://github.com/berserkhmdvhb/agentic-scraper/blob/main/sample.env) as example.


---


## 🔧 Environment Configuration (.env)

See [`sample.env`](https://github.com/berserkhmdvhb/agentic-scraper/blob/main/sample.env) as example.

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


## 📐 Architecture Diagram

https://lucid.app/lucidchart/3fb8cd99-6bee-44ba-8f47-87e8de28ea95/view

<img width="6563" height="6563" alt="diagram" src="https://github.com/user-attachments/assets/128f4fac-711e-4463-9b25-04c257ef50a9" />


---


## 🧪 How It Works

1. **User Input**

   * URLs are provided via Streamlit UI (paste or `.txt` file).
   * OpenAI credentials are securely stored using encrypted local store.
   * User must authenticate via Auth0 (JWT token required for API access).

2. **API Request (FastAPI)**

   * Frontend sends a scrape request to the FastAPI backend (`/api/v1/scrape/start`) with the list of URLs and user config.
   * Backend validates JWT token and user scopes.

3. **Fetch HTML**

   * Backend fetches page content using `httpx` with retry logic.
   * Optionally stores raw HTML if needed for debugging.

4. **Extract Structured Data**

   * [The Scraping Pipeline](#-scraping-pipeline) runs agents per URL:

     * `rule_based`: uses `BeautifulSoup` heuristics.
     * `llm_fixed`: strict schema LLM extraction.
     * `llm_dynamic`: free-form LLM extraction.
     * `llm_dynamic_adaptive`: retry-aware LLM with field scoring + self-healing.
   * Agents are configurable via sidebar in the frontend.

5. **Validate Output**

   * Extracted output is validated using a `ScrapedItem` Pydantic schema.
   * If invalid, adaptive agents retry with refined prompts.

6. **Retry (Adaptive Agent Only)**

   * If required fields are missing or placeholders are returned (e.g. "N/A"),

     * The agent retries up to `LLM_SCHEMA_RETRIES` times.
     * Prompts adapt based on previously missing fields.

7. **Screenshot (Optional)**

   * If enabled, Playwright captures a screenshot for each page.
   * Screenshots are saved and included in the final output.

8. **Display in Streamlit**

   * Results are shown in the frontend using Ag-Grid.
   * Users can filter, sort, and inspect structured data and screenshots.

9. **Export Results**

   * Scraped data can be exported as:

     * **JSON**
     * **CSV**
     * **SQLite**
   * Export options are available from the UI.

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
| `rule-based`           | Heuristic parser using BeautifulSoup — fast, LLM-free baseline               |
| `llm-fixed`            | Extracts a fixed predefined schema (e.g. title, price)                        |
| `llm-dynamic`          | LLM selects relevant fields based on page content and contextual hints       |
| `llm-dynamic-adaptive` | Adds retries, field scoring, and placeholder detection for better coverage   |

> 💡 Recommended: Use `llm-dynamic` for the best balance of quality and performance.

> The UI dynamically adapts to the selected mode — model selection and retry sliders appear only for LLM-based modes.

> All LLM modes use the OpenAI ChatCompletion API (`gpt-4`, `gpt-3.5-turbo`).

See [`agents.md`](https://github.com/berserkhmdvhb/agentic-scraper/blob/main/docs/agents.md) 


---


## 🔬 Scraping Pipeline

<img width="815" height="538" alt="pipeline" src="https://github.com/user-attachments/assets/11940f42-b1e4-4889-a1a7-49e694f1c793" />



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

See [`agents.md`](https://github.com/berserkhmdvhb/agentic-scraper/blob/main/docs/agents.md) 


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
