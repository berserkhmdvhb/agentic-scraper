#!/usr/bin/env python3
"""
run_experiments.py - Run Agentic Scraper batch mode with different concurrency settings.
"""
import os
import csv
import itertools
from pathlib import Path
import asyncio
import sys
import json

# Ensure the project root is in the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.resolve()))

from agentic_scraper.backend.core.settings import Settings
from agentic_scraper.backend.scraper.pipeline import scrape_with_stats

# ------------------------
# CONFIGURATION
# ------------------------

INPUT_FILES = [
    "input/urls1.txt",
    "input/urls2.txt",
]

FETCH_CONCURRENCY_VALUES = [1, 5, 10, 20]
LLM_CONCURRENCY_VALUES = [1, 2, 4]

OUTPUT_DIR = Path("output/experiment")
CSV_LOG_PATH = OUTPUT_DIR / "summary.csv"

# --- WINDOWS ASYNCIO FIX ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ------------------------
# RUNNER LOGIC
# ------------------------

def load_urls(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def format_error(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"[:200]

async def run_experiment(input_file: str, fetch_c: int, llm_c: int) -> dict:
    urls = load_urls(input_file)
    settings = Settings(
        fetch_concurrency=fetch_c,
        llm_concurrency=llm_c,
        screenshot_enabled=False,
        log_tracebacks=False,
    )

    output_file = OUTPUT_DIR / f"{Path(input_file).stem}_f{fetch_c}_l{llm_c}.json"

    try:
        results, stats = await scrape_with_stats(urls, settings)

        if results:
            with output_file.open("w", encoding="utf-8") as f:
                json.dump([item.model_dump(mode="json") for item in results], f, indent=2, ensure_ascii=False)

        return {
            "input_file": input_file,
            "fetch_concurrency": fetch_c,
            "llm_concurrency": llm_c,
            "output_file": str(output_file),
            "duration_sec": stats["duration_sec"],
            "success_count": stats["num_success"],
            "fail_count": stats["num_failed"],
            "exit_code": 0,
            "stderr": "",
        }

    except Exception as e:
        return {
            "input_file": input_file,
            "fetch_concurrency": fetch_c,
            "llm_concurrency": llm_c,
            "output_file": str(output_file),
            "duration_sec": None,
            "success_count": None,
            "fail_count": None,
            "exit_code": 1,
            "stderr": format_error(e),
        }

async def run_all(writer: csv.DictWriter):
    for input_file, fetch_c, llm_c in itertools.product(
        INPUT_FILES, FETCH_CONCURRENCY_VALUES, LLM_CONCURRENCY_VALUES
    ):
        print(f"\n▶️ {input_file} | fetch={fetch_c} | llm={llm_c}")
        result = await run_experiment(input_file, fetch_c, llm_c)
        writer.writerow(result)

        if result["exit_code"] == 0:
            print(f"✅ Done: {result['duration_sec']}s | ✅ {result['success_count']} | ❌ {result['fail_count']}")
        else:
            print(f"❌ Failed: {result['stderr']}")

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with CSV_LOG_PATH.open("w", encoding="utf-8", newline="") as csvfile:
        fieldnames = [
            "input_file", "fetch_concurrency", "llm_concurrency",
            "duration_sec", "success_count", "fail_count",
            "output_file", "exit_code", "stderr"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        asyncio.run(run_all(writer))

if __name__ == "__main__":
    main()
