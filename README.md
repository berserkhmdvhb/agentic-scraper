# 🕵️ Agentic Scraper

**Agentic Scraper** is an intelligent, LLM-powered web scraping tool with a Streamlit interface. It processes multiple URLs in parallel, extracts structured data using adaptive agent logic, and presents results in an interactive UI.

Built with modern Python, this project blends async scraping, schema-aware extraction, and human-friendly presentation — all in one app.

---

## 🚀 Features

* 🔗 Accepts lists of URLs (via text input or file upload)
* ⚡ Async web scraping using `httpx` and `asyncio`
* 🧠 Agentic logic powered by OpenAI for dynamic field extraction
* 📄 HTML parsing via `BeautifulSoup4`
* ✅ Data validation with `pydantic`
* 📊 Interactive Streamlit UI with progress tracking
* 📅 Export results to CSV / JSON
* 🧱 Modular architecture with clean code organization

---

## 📸 Demo

<!-- Include a screenshot or short GIF here -->

![screenshot](assets/screenshot.png)

---

## 📦 Tech Stack

| Layer         | Tools                                     |
| ------------- | ----------------------------------------- |
| Async HTTP    | `httpx.AsyncClient`, `tenacity` for retry |
| HTML Parsing  | `BeautifulSoup4`                          |
| Agent Logic   | `openai` (ChatCompletion API)             |
| Data Modeling | `pydantic`                                |
| UI            | `Streamlit`                               |
| Dev Tools     | `pyproject.toml`, `black`, `ruff`         |

---

## 🪰 Getting Started

### 1. Clone the Repo

```bash
git clone https://github.com/yourusername/agentic-scraper.git
cd agentic-scraper
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Or use `poetry install` if using `pyproject.toml`.

### 3. Set OpenAI Key

Create a `.env` file in the root:

```
OPENAI_API_KEY=your-key-here
```

### 4. Run the App

```bash
streamlit run app.py
```

---

## 🔍 How It Works

1. **Input** a list of URLs
2. The system **fetches pages in parallel** using `httpx`
3. Each page is parsed with `BeautifulSoup` and passed to an **LLM agent**
4. The LLM returns a structured JSON object based on context
5. Results are validated with `pydantic` and displayed in the UI

---

## ✨ Example Output

```json
{
  "title": "The Future of AI Agents",
  "author": "Jane Doe",
  "price": 19.99,
  "description": "An in-depth look at LLM-powered web automation."
}
```

---

## 🧠 Agent Prompt Strategy

> "Given the following HTML/text content, extract the most relevant fields like title, price, description, author, etc. Return a JSON object. If fields are missing, set them to null."

You can find this logic in [`scraper/agent.py`](scraper/agent.py)

---

## 📂 Project Structure

```
agentic-scraper/
├── .env.sample              # Example environment config
├── Makefile                 # Dev automation
├── pyproject.toml           # Tooling and deps
├── README.md
├── docker-compose.yml       # (Optional) containerization support
├── docs/
│   └── prompt_strategy.md
├── src/
│   └── agentic_scraper/
│       ├── app.py
│       ├── core/
│       │   └── settings.py
│       ├── config/
│       │   ├── __init__.py
│       │   ├── constants.py     # Static values (timeouts, tags, etc.)
│       │   ├── messages.py      # Prompts and user/system messages
│       │   ├── types.py         # TypedDicts and structural typing
│       │   └── aliases.py       # Shared type aliases
│       ├── scraper/
│       │   ├── fetcher.py       # Async HTTP logic
│       │   ├── parser.py        # HTML parsing logic
│       │   ├── agent.py         # LLM extraction logic
│       │   └── models.py        # Pydantic schemas
│       ├── utils/
│       │   ├── io_helpers.py
│       │   ├── text_cleaning.py
│       │   └── formatting.py
│       └── validators.py        # Input validators and sanity checks
└── tests/
    ├── test_fetcher.py
    ├── test_parser.py
    ├── test_agent.py
    └── test_integration.py
```

---

## 🔬 TODO / Roadmap

* [ ] Add fuzzy schema inference fallback (non-LLM)
* [ ] Include domain-based prompt tuning
* [ ] Add `st_aggrid` support for better UI filtering
* [ ] Optional: Docker support
* [ ] Optional: Save scraping runs to SQLite

---
