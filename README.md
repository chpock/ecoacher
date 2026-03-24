# English Coacher

Desktop Python + QML application for English phrase correction and explanation.
When the window is closed, the app hides to the system tray and continues running.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Install with test tooling:

```bash
pip install -e ".[dev]"
```

Alternative install path:

```bash
pip install -r requirements.txt
```

## Run

Run as script:

```bash
python main.py
```

Run as installed command:

```bash
ecoacher
```

Run dev profile via wrapper:

```bash
./ecoacher-dev
```

## Profiles (`normal` / `dev`)

Profiles use separate app IDs and IPC server names, so both can run in parallel.

```bash
ecoacher --profile normal
ecoacher --profile dev
```

Environment variable form:

```bash
ECOACHER_PROFILE=dev ecoacher
```

Single-instance behavior is enforced per profile. Launching the same profile again
focuses/shows the existing window.

## CLI spell flow

Send text to a running app instance:

```bash
ecoacher spell "New text"
echo "New text" | ecoacher spell
```

Profile-specific spell commands:

```bash
ecoacher --profile dev spell "New text"
echo "New text" | ecoacher --profile dev spell
./ecoacher-dev spell "New text"
```

If no app instance is running for that profile, `spell` bootstraps the GUI with
the provided text and starts checking it.

## Checks and tests

```bash
python -m py_compile main.py
python -m compileall src
pyside6-qmllint qml/Main.qml
pytest -q
```

Run one test file:

```bash
pytest tests/test_word_diff.py -q
```

Run one test function:

```bash
pytest tests/test_word_diff.py::test_build_word_diff_html_highlights_inserted_or_replaced_words -q
```

## Build artifacts

```bash
python -m build
```
