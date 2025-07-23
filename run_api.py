# src/run_api.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run("agentic_scraper.backend.api.main:app", host="0.0.0.0", port=8000, reload=True)
