#!/usr/bin/env python3
"""
run_batch.py - Run Agentic Scraper in headless (non-UI) mode with concurrency options.
"""

import argparse
import json
import csv
from pathlib import Path
import sys
import asyncio

# Ensure the project root is in the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.resolve()))

from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.core.logger_setup import setup_logging
from agentic_scraper.backend.scraper.models import ScrapedItem
from agentic_scraper.backend.scraper.pipeline import scrape_with_stats

# --- WINDOWS ASYNCIO FIX ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def parse_args():
    parser = argparse.ArgumentParser(description="Agentic Scraper - Batch Mode")
    parser.add_argument("--input", required=True, help="Path to input file with URLs (one per line)")
    parser.add_argument("--output", help="Path to output file (.json or .csv)")
    parser.add_argument("--fetch-concurrency", type=int, help="Override FETCH_CONCURRENCY")
    parser.add_argument("--llm-concurrency", type=int, help="Override LLM_CONCURRENCY")
    parser.add_argument("--timeout", type=int, help="Override MAX_CONCURRENT_REQUESTS")
    parser.add_argument("--retries", type=int, help="Override RETRY_ATTEMPTS")
    return parser.parse_args()

def load_urls(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def save_results(output_path: str, items: list[ScrapedItem]):
    ext = Path(output_path).suffix.lower()
    if ext == ".json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([item.model_dump(mode="json") for item in items], f, indent=2, ensure_ascii=False)
    elif ext == ".csv":
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=items[0].model_dump().keys())
            writer.writeheader()
            for item in items:
                writer.writerow(item.model_dump())
    else:
        raise ValueError(f"Unsupported output format: {output_path}")

def main():
    args = parse_args()
    setup_logging()

    urls = load_urls(args.input)
    print(f"🔗 Loaded {len(urls)} URLs from {args.input}")

    # Selectively override settings from CLI args (only if passed)
    overrides = {
        "fetch_concurrency": args.fetch_concurrency,
        "llm_concurrency": args.llm_concurrency,
        "request_timeout": args.timeout,
        "retry_attempts": args.retries,
        "screenshot_enabled": False,
        "log_tracebacks": False,
    }

    # Remove unset values to allow fallback to .env
    settings_kwargs = {k: v for k, v in overrides.items() if v is not None}
    settings = Settings(**settings_kwargs)

    print(f"⚙️ Settings: fetch={settings.fetch_concurrency}, llm={settings.llm_concurrency}, timeout={settings.request_timeout}s, retries={settings.retry_attempts}")

    try:
        results, stats = asyncio.run(scrape_with_stats(urls, settings))
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        return

    print(f"✅ Finished in {stats['duration_sec']} seconds")
    print(f"📦 Success: {stats['num_success']} / {stats['num_urls']}, Failures: {stats['num_failed']}")

    output_path = args.output or "output/experiment/results.json"
    if results:
        save_results(output_path, results)
        print(f"💾 Results saved to {output_path}")

if __name__ == "__main__":
    main()
