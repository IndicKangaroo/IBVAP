"""One-command IBVAP launcher.

Builds the frontend if it isn't built yet, then starts the backend —
which now serves BOTH the API and the built frontend from one process
(see backend/main.py's static mount at the bottom). That's the whole
point: this is the only command you run in a terminal for the whole
demo. Cameras are added and started from the UI's "Add Camera" button
afterward — no more per-camera terminal windows.

Usage:
    python run_demo.py
    python run_demo.py --rebuild-frontend
    python run_demo.py --host 0.0.0.0 --port 8000 --no-browser
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def run(cmd: list[str], cwd: str | None = None, use_shell: bool = False) -> None:
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, shell=use_shell)
    if result.returncode != 0:
        print(f"Command failed (exit {result.returncode}): {' '.join(cmd)}", file=sys.stderr)
        sys.exit(result.returncode)


def ensure_frontend_built(rebuild: bool) -> None:
    frontend_dir = PROJECT_ROOT / "frontend"
    dist_dir = frontend_dir / "dist"
    node_modules = frontend_dir / "node_modules"

    # if dist_dir.exists() and not rebuild:
    #     print(f"Using existing frontend build at {dist_dir} (pass --rebuild-frontend to force a rebuild)")
    #     return

    if not shutil.which("npm"):
        print(
            "npm not found on PATH — install Node.js, or build the frontend yourself\n"
            "  (cd frontend && npm install && npm run build)\nand rerun this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    # npm on Windows resolves through a .cmd shim — shell=True makes
    # that work the same way it would typing the command directly into
    # a terminal, on both Windows and everywhere else.
    on_windows = sys.platform == "win32"

    if not node_modules.exists():
        print("Installing frontend dependencies (first run only)...")
        run(["npm", "install"], cwd=str(frontend_dir), use_shell=on_windows)

    print("Building frontend...")
    run(["npm", "run", "build"], cwd=str(frontend_dir), use_shell=on_windows)


def open_browser_after_delay(url: str, delay: float = 1.5) -> None:
    def _open():
        time.sleep(delay)  # give uvicorn time to actually bind the port first
        try:
            webbrowser.open(url)
        except Exception:
            pass  # best-effort — don't let this fail the launch
    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command IBVAP launcher")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--rebuild-frontend", action="store_true")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open a browser tab")
    args = parser.parse_args()

    ensure_frontend_built(rebuild=args.rebuild_frontend)

    url = f"http://{args.host}:{args.port}"
    print(f"\nStarting IBVAP — {url}")
    print("Add and start cameras from the UI's 'Add Camera' button once it loads.\n")

    if not args.no_browser:
        open_browser_after_delay(url)

    run([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", args.host, "--port", str(args.port)], cwd=str(PROJECT_ROOT))


if __name__ == "__main__":
    main()
