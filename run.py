#!/usr/bin/env python3
"""
run.py - Launches the AgenticScraper Streamlit UI
"""

import subprocess
import sys
import shutil
from pathlib import Path

APP_PATH = Path("src/agentic_scraper/frontend/app.py")

def main():
    if shutil.which("streamlit") is None:
        print("❌ Streamlit is not installed. Please run: pip install streamlit", file=sys.stderr)
        sys.exit(1)

    print(f"▶️ Launching Streamlit app: {APP_PATH}", file=sys.stderr)

    try:
        subprocess.run(["streamlit", "run", str(APP_PATH)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to run Streamlit: {e}", file=sys.stderr)
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
