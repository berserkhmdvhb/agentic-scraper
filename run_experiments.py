#!/usr/bin/env python3
"""
run_experiments.py - Run Agentic Scraper batch mode with different concurrency settings.
"""

import csv
import itertools
import subprocess
import time
from pathlib import Path

# ------------------------
# CONFIGURATION
# ------------------------

INPUT_FILES = [
    "input/urls1.txt",
    "input/urls2.txt",
]


FETCH_CONCURRENCY_VALUES = [5, 10, 20]
LLM_CONCURRENCY_VALUES = [1, 2, 4]

BATCH_SCRIPT = "run_batch.py"
OUTPUT_DIR = Path("output/experiment")
CSV_LOG_PATH = OUTPUT_DIR / "summary.csv"

# ------------------------
# RUNNER LOGIC
# ------------------------

def parse_output(output: str) -> dict:
    """
    Parses stdout from run_batch.py and extracts summary metrics.
    Assumes specific print patterns.
    """
    lines = output.strip().splitlines()
    result = {
        "duration_sec": None,
        "success_count": None,
        "fail_count": None,
    }

    for line in lines:
        if "Finished in" in line:
            try:
                result["duration_sec"] = float(line.split("in")[-1].split("seconds")[0].strip())
            except Exception:
                pass
        elif "Success:" in line:
            try:
                parts = line.split("Success:")[1].strip().split(",")
                result["success_count"] = int(parts[0].split("/")[0].strip())
                result["fail_count"] = int(parts[1].split(":")[-1].strip())
            except Exception:
                pass

    return result

import os  # Add this at the top

def run_experiment(input_file, fetch_c, llm_c) -> dict:
    output_file = OUTPUT_DIR / f"{Path(input_file).stem}_f{fetch_c}_l{llm_c}.json"

    cmd = [
        "python", BATCH_SCRIPT,
        "--input", input_file,
        "--fetch-concurrency", str(fetch_c),
        "--llm-concurrency", str(llm_c),
        "--output", str(output_file)
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    elapsed = time.perf_counter() - start


    parsed = parse_output(result.stdout)

    return {
        "input_file": input_file,
        "fetch_concurrency": fetch_c,
        "llm_concurrency": llm_c,
        "output_file": str(output_file),
        "duration_sec": round(parsed["duration_sec"] or elapsed, 2),
        "success_count": parsed["success_count"],
        "fail_count": parsed["fail_count"],
        "exit_code": result.returncode,
        "stderr": result.stderr.strip()[:200],  # truncate for readability
    }

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with CSV_LOG_PATH.open("w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "input_file", "fetch_concurrency", "llm_concurrency",
            "duration_sec", "success_count", "fail_count",
            "output_file", "exit_code", "stderr"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for input_file, fetch_c, llm_c in itertools.product(
            INPUT_FILES, FETCH_CONCURRENCY_VALUES, LLM_CONCURRENCY_VALUES
        ):
            print(f"\n▶️ Running: {input_file} | fetch={fetch_c} | llm={llm_c}")
            try:
                result = run_experiment(input_file, fetch_c, llm_c)
                writer.writerow(result)
                print(f"✅ Done: {result['duration_sec']}s | Success: {result['success_count']} | Fail: {result['fail_count']}")
            except Exception as e:
                print(f"❌ Error: {e}")
                writer.writerow({
                    "input_file": input_file,
                    "fetch_concurrency": fetch_c,
                    "llm_concurrency": llm_c,
                    "duration_sec": None,
                    "success_count": None,
                    "fail_count": None,
                    "output_file": None,
                    "exit_code": 1,
                    "stderr": str(e)
                })

if __name__ == "__main__":
    main()
