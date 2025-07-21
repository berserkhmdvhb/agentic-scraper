#!/usr/bin/env python3
"""
run_batch.py - Run Agentic Scraper in headless (non-UI) mode with concurrency options.
"""

import argparse
import json
import csv
import time
from pathlib import Path
import sys


from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.core.logger_setup import setup_logging
from agentic_scraper.backend.scraper.agent import scrape_urls
from agentic_scraper.backend.scraper.models import ScrapedItem



# Ensure the project root is in the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.resolve()))


def parse_args():
    parser = argparse.ArgumentParser(description="Agentic Scraper - Batch Mode")
    parser.add_argument("--input", required=True, help="Path to input file with URLs (one per line)")
    parser.add_argument("--output", help="Path to output file (.json or .csv)", default="output/experiment/results.json")
    parser.add_argument("--fetch-concurrency", type=int, default=10, help="Max concurrent fetch operations")
    parser.add_argument("--llm-concurrency", type=int, default=2, help="Max concurrent LLM calls")
    parser.add_argument("--timeout", type=int, default=30, help="Per-request timeout in seconds")
    return parser.parse_args()

def load_urls(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def save_results(output_path: str, items: list[ScrapedItem]):
    ext = Path(output_path).suffix.lower()
    if ext == ".json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([item.model_dump() for item in items], f, indent=2, ensure_ascii=False)
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

    settings = Settings(
        fetch_concurrency=args.fetch_concurrency,
        llm_concurrency=args.llm_concurrency,
        request_timeout=args.timeout,
        log_tracebacks=False,  # can make this configurable later
    )

    print(f"⚙️ Settings: fetch={args.fetch_concurrency}, llm={args.llm_concurrency}, timeout={args.timeout}s")
    start = time.perf_counter()

    try:
        results: list[ScrapedItem] = scrape_urls(urls, settings)
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        return

    duration = time.perf_counter() - start
    num_success = sum(1 for r in results if r.success)
    num_fail = len(results) - num_success

    print(f"✅ Finished in {duration:.2f} seconds")
    print(f"📦 Success: {num_success} / {len(results)}, Failures: {num_fail}")

    if results:
        save_results(args.output, results)
        print(f"💾 Results saved to {args.output}")

if __name__ == "__main__":
    main()
