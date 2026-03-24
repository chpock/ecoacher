# AGENTS.md

Guidance for coding agents working in this repository.

## Scope and Priority

- This file applies to the entire repository rooted at `/w/projects/ecoacher`.
- Follow direct user instructions first.
- Then follow this file.
- Keep changes minimal, focused, and easy to review.

## Repository Snapshot

- Language: Python 3.10+.
- UI: QML via PySide6.
- Source layout: `src/ecoacher/` package.
- Root launcher: `main.py` (thin shim to `ecoacher.main:main`).
- Main QML file: `qml/Main.qml`.
- QML components: `qml/components/`.
- Package metadata: `pyproject.toml` (source of truth).
- Runtime dependency mirror: `requirements.txt`.
- Tests exist under `tests/` and use `pytest`.
- Profiles: `normal` and `dev`.

## Environment Setup

- Create virtual environment:
- `python -m venv .venv`
- Activate:
- `source .venv/bin/activate`
- Install package (preferred):
- `pip install -e .`
- Install package with dev tools:
- `pip install -e ".[dev]"`
- Alternative install path:
- `pip install -r requirements.txt`
- Notes:
- Commands below assume the virtual environment is activated.
- If not activated, use explicit binaries (for example `.venv/bin/pytest`, `.venv/bin/pyside6-qmllint`).

## Quick Command Matrix

- Create venv: `python -m venv .venv`
- Activate venv: `source .venv/bin/activate`
- Install package editable: `pip install -e .`
- Install with test deps: `pip install -e ".[dev]"`
- Install from requirements: `pip install -r requirements.txt`
- Run app (script): `python main.py`
- Run app (console script): `ecoacher`
- Run dev profile wrapper: `./ecoacher-dev`
- Run explicit profile: `ecoacher --profile dev`
- Send spell text to running app: `ecoacher spell "Text"`
- Python syntax check: `python -m py_compile main.py`
- Compile check (project): `python -m compileall src`
- QML lint: `pyside6-qmllint qml/Main.qml`
- QML format preview: `pyside6-qmlformat -n qml/Main.qml`
- Run all tests: `pytest -q`
- Run single test file: `pytest tests/test_word_diff.py -q`
- Run single test function: `pytest tests/test_word_diff.py::test_build_word_diff_html_highlights_inserted_or_replaced_words -q`
- Run tests by keyword: `pytest -k "keyword" -q`
- Build package artifacts: `python -m build`

## Build / Run Commands

- Run as script:
- `python main.py`
- Run via installed console script:
- `ecoacher`
- Run dev wrapper:
- `./ecoacher-dev`
- Run explicit profile:
- `ecoacher --profile dev`
- Send text via CLI spell flow:
- `ecoacher spell "Text"`
- `echo "Text" | ecoacher spell`
- Build wheel/sdist (if `build` is installed):
- `python -m build`

## Lint / Format / Static Checks

- Python syntax check:
- `python -m py_compile main.py`
- Project-wide bytecode compile check:
- `python -m compileall src`
- QML lint (PySide tool):
- `pyside6-qmllint qml/Main.qml`
- Optional QML formatting preview:
- `pyside6-qmlformat -n qml/Main.qml`

## Tests

- Test directory exists: `tests/`.
- Preferred test runner: `pytest`.
- Run all tests:
- `pytest -q`
- Run a single file:
- `pytest tests/test_constants.py -q`
- Run a single test function:
- `pytest tests/test_constants.py::test_app_id_for_profile_values -q`
- Run tests by keyword:
- `pytest -k "keyword" -q`
- Stop early on first failure:
- `pytest -x -q`

## Expected Workflow for Agents

- Read relevant files before editing.
- Make the smallest change that satisfies the request.
- Preserve existing structure unless refactor is requested.
- Update docs when behavior or commands change.
- Run the narrowest useful validation command first.
- For UI edits, also run QML lint.

## Python Style Guidelines

- Follow PEP 8 and keep code straightforward.
- Use 4-space indentation; no tabs.
- Prefer line length <= 100 where practical.
- Keep functions small and single-purpose.
- Add blank lines between top-level definitions.
- Avoid unnecessary comments.
- Use comments only for non-obvious intent.

## Imports

- Group imports in this order:
- Standard library.
- Third-party packages.
- Local application imports.
- Separate groups with one blank line.
- Prefer explicit imports over wildcard imports.
- Remove unused imports.

## Types and Signatures

- Add type hints for public functions.
- Include return types on non-trivial functions.
- Prefer concrete types when useful, e.g. `list[str]`.
- Avoid misleading hints; keep them accurate.
- If a type is uncertain, choose a safe broad type.

## Naming Conventions

- Modules/files: `snake_case.py`.
- Functions/variables: `snake_case`.
- Constants: `UPPER_SNAKE_CASE`.
- Classes: `PascalCase`.
- QML object IDs: `camelCase`.
- QML user-visible text should be intentional and consistent.

## Error Handling

- Fail fast on startup errors.
- Return explicit non-zero exit codes for fatal startup failures.
- Prefer clear checks over broad `try/except` blocks.
- Catch narrow exception types when recovery is possible.
- Do not silently swallow exceptions.

## QML Style Guidelines

- Keep QML declarative and readable.
- One logical UI block per component when possible.
- Prefer layout containers (`ColumnLayout`, `RowLayout`) over manual geometry.
- Keep property names explicit and grouped logically.
- Use signal handlers (`onClicked`) for direct interactions.
- Use `Qt.quit()` for simple app-exit behavior.
- Avoid heavy JavaScript in QML; move logic to Python when it grows.

## Project Structure Conventions

- Keep Python application code in `src/ecoacher/` by domain (`app/`, `ipc/`, `opencode/`, `spellcheck/`, `text/`, `logging/`, `config/`).
- Keep `main.py` as a thin root shim only.
- QML files belong under `qml/`.
- Reusable QML components belong under `qml/components/`.
- Keep dependency declarations in `pyproject.toml` as source of truth.
- If `requirements.txt` remains, keep it synchronized with runtime deps.

## Dependency and Tooling Policy

- Do not add new dependencies without clear need.
- Prefer standard library solutions for simple tasks.
- If adding developer tools (pytest/ruff/mypy), update this file and docs.

## Git and Change Hygiene

- Do not revert unrelated local changes.
- Do not perform destructive git operations.
- Keep commits focused and atomic when committing is requested.
- Do not include `.venv/`, caches, or generated artifacts in commits.

## Files and Artifacts to Ignore

- Virtual environment directory: `.venv/`.
- Python cache directories: `__pycache__/`.
- Compiled files: `*.pyc`.
- Build artifacts if created: `dist/`, `build/`, `*.egg-info/`.

## Cursor / Copilot Rules Check

- `.cursorrules`: not present.
- `.cursor/rules/`: not present.
- `.github/copilot-instructions.md`: not present.
- If any of these files are added later, treat them as additional instructions and update this document.

## When Extending the App

- Keep startup path deterministic.
- Ensure missing QML files fail clearly.
- Keep UI text and behavior covered by tests where practical.
- Prefer incremental changes over broad rewrites.
- Preserve profile-aware behavior (`normal`/`dev`) for app ID and IPC server names.
- Preserve CLI `spell` flow: deliver to running instance or bootstrap app with initial text.

## Definition of Done (for typical changes)

- Requested behavior implemented.
- Relevant Python syntax check passes.
- Relevant QML lint passes for changed QML files.
- Relevant tests pass (`pytest -q`) for logic changes.
- Documentation updated when commands or behavior changed.
- No unrelated files modified.
