"""
One-command launcher for the Site Safety Monitor dashboard.

Starts:
  1. FastAPI read-only API on http://127.0.0.1:8000 (serves real project data)
  2. Vite dev server for the React dashboard on http://localhost:5173

Usage:
    .venv\\Scripts\\python run_dashboard.py

The Python backend serves only files the existing pipeline produced; the
detection/violation logic is untouched.
"""

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
NODE_MODULES = DASHBOARD_DIR / "node_modules"


def main() -> None:
    if not NODE_MODULES.exists():
        print("Dashboard dependencies not installed. Running: npm install ...")
        subprocess.run(["npm", "install"], cwd=DASHBOARD_DIR, check=True, shell=True)

    print("Starting API server on http://127.0.0.1:8000 ...")
    api_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.dashboard_api:app",
         "--host", "127.0.0.1", "--port", "8000"],
        cwd=PROJECT_ROOT,
    )

    print("Starting dashboard dev server on http://localhost:5173 ...")
    web_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=DASHBOARD_DIR,
        shell=True,
    )

    print("\n" + "=" * 60)
    print("  Dashboard:  http://localhost:5173")
    print("  API docs:   http://127.0.0.1:8000/docs")
    print("  Press Ctrl+C to stop both servers.")
    print("=" * 60 + "\n")

    try:
        try:
            web_proc.wait()
        except KeyboardInterrupt:
            pass
    finally:
        api_proc.terminate()
        web_proc.terminate()
        print("Servers stopped.")


if __name__ == "__main__":
    main()
