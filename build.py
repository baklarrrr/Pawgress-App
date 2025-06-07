#!/usr/bin/env python3

import subprocess
from pathlib import Path
import sys

"""Simple build helper for creating a standalone executable using PyInstaller."""

APP_DIR = Path(__file__).resolve().parent


def main():
    script = APP_DIR / "run_app.py"
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--windowed",
        "--onefile",
        str(script)
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
