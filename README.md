# Pawgress App 🐾

Pawgress is a lightweight PyQt6 desktop application for tracking animal health data and simple project tasks. Keep it next to your Unreal Engine `.uproject` so everything stays under version control.

## Features

- Log health notes and schedules
- Manage project TODO items
- Cross‑platform Python app

## Quick Start

Clone this repository and launch the helper script. It creates a local Python environment, installs dependencies and starts the program.

### Windows
```cmd
start_app.bat
```

### macOS / Linux
```bash
./start_app.sh
```

The first run may take a little while as packages are installed. Subsequent launches will start the app immediately.

## Manual Setup

If you prefer to handle the environment yourself:

```bash
pip install -r requirements.txt
python run_app.py
```

`run_app.py` automatically pulls the latest changes before running `pawgress.py`.

## Building a Standalone Executable

Install [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
```

Then execute the build script:

```bash
python build.py
```

After completion, the standalone binary appears in the `dist` folder.

## Updating

The application performs a `git pull` on startup through `run_app.py`, keeping it up to date with the repository.

---

Enjoy using Pawgress! 🐾

