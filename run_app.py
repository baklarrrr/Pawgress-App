import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent


def update_repo():
    """Pull the latest changes for the application repo."""
    try:
        subprocess.run(["git", "pull"], cwd=APP_DIR, check=True)
    except Exception as exc:
        print(f"Repository update failed: {exc}")


def main():
    update_repo()
    subprocess.run([sys.executable, str(APP_DIR / "pawgress.py"), *sys.argv[1:]], cwd=APP_DIR)


if __name__ == "__main__":
    main()
