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

See [`sample.env`](https://github.com/berserkhmdvhb/agentic-scraper/blob/main/sample.env) as example.
Two values are mandatory for backend to run:

1. `ENCRYPTION_SECRET`: Ensure you generate the `ENCRYPTION_SECRET` value using the `cryptography.fernet` command provided in `sample.env` and replace it with the command. The command to generate is following:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If you haven't installed the dependencies (from ), you need at least the package `cryptography` to produce the command above. It can be installed as following;

```bash
pip install cryptography
```
2. `AUTH0_ISSUER`: In `sample.env` the value is `https://dev-xxxxxx.us.auth0.com/`. But it should be replaced with a correct one, otherwise FastAPI will raise following error:
   
```
httpx.HTTPStatusError: Client error '404 Not Found' for url 'https://dev-xxxxxx.us.auth0.com/.well-known/jwks.json'
```

The file [`src\backend\api\auth\auth0_helpers.py`](https://github.com/berserkhmdvhb/agentic-scraper/blob/main/src/agentic_scraper/backend/api/auth/auth0_helpers.py) is responsible for fetching JWKS.
Although providing `ENCRYPTION_SECRET` and `AUTH0_ISSUER` will be enough for both frontend and backend to launch, but the following operations require proper setup of auth0:
- Authenticate users on auth0
- Authenticated users log in on the frontend domain.
- Authenticated users submit their openai-credentials.
- Authenticated users with saved openai-credentials could now feed URLs and perform scraping.


To setup auth0, see [Setup Auth0](#setup-auth0).



Example of `.env` values:

```ini
LOG_LEVEL=INFO
AGENT_MODE=llm-dynamic-adaptive
BACKEND_DOMAIN=https://api-agenticscraper.onrender.com
FRONTEND_DOMAIN=https://agenticscraper.onrender.com
ENCRYPTION_SECRET=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
...
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



## 🔐 Security & Authentication 

### Setup Auth0
To 
...




---

## 🚀 CI/CD & Deployment

Agentic Scraper now supports **full CI/CD** with Docker-based builds and continuous deployment to Render.com.

### 🧪 Continuous Integration
Automated tests, linting, and type checks are run via [GitHub Actions](https://github.com/berserkhmdvhb/agentic-scraper/actions) on every push and PR.

### 🚀 Continuous Delivery (Render)
Production deployments are triggered automatically when changes are pushed to `main`.
To see the hosted domains, visit [Running the App](#%EF%B8%8F-running-the-app)

### 📦 Docker Support
Production-ready Docker configuration are provided as following files:
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
* [ ] Add agentic workflow to classify and contextualize input URLs and feed that to other models
* [ ] Add DELETE, POST, and PATCH operatoins on FastAPI for the route `user/openai-credentails`
* [ ] In scraping pipeline, fetching and scraping are sequential operations, find a robust and clean way to parallelize them.
* [ ] Use Playwright do explore the page and add more content before feeding to scraping pipeline.
* [x] User authentication with Auth0
* [x] Authentication protocol with OAuth2 and JWT

---

## 📜 License

MIT License
