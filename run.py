#!/usr/bin/env python3
"""
run.py - Launches the Agentic Scraper Streamlit UI
"""
import asyncio
import subprocess
import sys
import shutil
from pathlib import Path

APP_PATH = Path("src/agentic_scraper/frontend/app.py")

# --- WINDOWS ASYNCIO FIX ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def main():
    # Check if Streamlit is installed
    if shutil.which("streamlit") is None:
        print("❌ Streamlit is not installed. Please run: pip install streamlit", file=sys.stderr)
        sys.exit(1)

    # Ensure app file exists
    if not APP_PATH.is_file():
        print(f"❌ Could not find Streamlit app at: {APP_PATH}", file=sys.stderr)
        sys.exit(1)

    print(f"▶️ Launching Streamlit app: {APP_PATH}", file=sys.stderr)

    # Run Streamlit as a subprocess (separate Python process)
    try:
        subprocess.run(["streamlit", "run", str(APP_PATH)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Streamlit exited with error: {e}", file=sys.stderr)
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("🛑 Interrupted by user", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
