# MB World Project Tracker

This repository contains a simple PyQt6 application to manage a to-do list. Tasks can be added with a priority, automatically sorted and moved to a completed list when done.

## Running from source

```bash
pip install -r requirements.txt
python mb_world_tracker.py
```

## Creating standalone executables

The project can be bundled as a single file using [PyInstaller](https://www.pyinstaller.org/). Build on the same operating system you are targeting:

```bash
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed mb_world_tracker.py
```

The resulting executable will be placed in the `dist/` directory. On Windows the file will be `mb_world_tracker.exe`, while on macOS and Linux it will be simply `mb_world_tracker`.

