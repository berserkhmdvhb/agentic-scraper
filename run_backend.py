#!/usr/bin/env python3
"""
run_backend.py - Launches the Agentic Scraper FastAPI backend
"""
import subprocess
import sys
import shutil


def main():
    # Check if uvicorn is installed
    if shutil.which("uvicorn") is None:
        print("❌ uvicorn is not installed. Please run: pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    print("▶️ Launching FastAPI backend with uvicorn...", file=sys.stderr)

    try:
        subprocess.run([
            "uvicorn",
            "src.agentic_scraper.backend.api.main:app",
            "--reload"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Uvicorn exited with error: {e}", file=sys.stderr)
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("🛑 Interrupted by user", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
