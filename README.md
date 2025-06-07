# Pawgress App

This repository provides a standalone PyQt6 desktop application used to track
animal health data and simple project tasks.  It can be placed alongside your
Unreal Engine `.uproject` file so the application is version controlled with
the rest of the project.

## Requirements

Install the Python dependencies with:

```bash
pip install -r requirements.txt
```

## Running

Use the `run_app.py` helper which automatically pulls the latest changes from
the repository and then launches the main application:

```bash
python run_app.py
```

The main application code lives in `pawgress.py`.

## Updating

`run_app.py` performs a `git pull` on startup so the application stays in sync
with the repository whenever it is launched.
