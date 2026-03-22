# Repository Guidelines

## Project Structure & Module Organization
Application code lives in `src/faceprompt/`, automated tests in `tests/`, static assets in `assets/`, and supporting documentation in `docs/`. Prompt library seed data is stored under `src/faceprompt/data/`, while internal-only reference thumbnail guidelines live in `assets/reference-thumbnails/`. Keep runtime or toolchain config files at the repository root, and document any new top-level directory in this file when it is introduced.

## Build, Test, and Development Commands
Use the standard `make` entry points at the repository root:

- `make summary` prints prompt library counts and style-line coverage.
- `make lint` runs the built-in data and schema validator for the prompt catalog.
- `make test` runs the automated unit test suite.
- `make render-example` renders one end-to-end example prompt from the catalog.
- `make interactive` opens the interactive selector for gender, scene, and hairstyle choices.

## Coding Style & Naming Conventions
Follow language-native conventions, but keep naming predictable across the repository. Use `PascalCase` for classes and UI components, `camelCase` for functions and variables, and `UPPER_SNAKE_CASE` for constants. Use 4-space indentation for Python and 2-space indentation for JavaScript, TypeScript, JSON, and YAML. Ruff settings are defined in `pyproject.toml`; run `make lint` before opening a pull request.

## Testing Guidelines
Mirror the source layout under `tests/` where practical. Name tests after the unit under test, for example `tests/test_auth.py` or `src/button.test.ts`. Prefer fast, deterministic tests and add regression coverage for every bug fix. Until CI is configured, include the exact command you ran to verify changes in the pull request description. The current baseline verification command is `make test`.

## Commit & Pull Request Guidelines
This checkout does not include Git history, so there is no repository-specific commit pattern to follow yet. Use short, imperative commit subjects and prefer Conventional Commit prefixes such as `feat:`, `fix:`, `docs:`, and `test:`. Pull requests should describe scope, list verification steps, link related issues, and include screenshots or sample output when user-facing behavior changes.

## Security & Configuration Tips
Do not commit secrets, tokens, or machine-specific credentials. Store local configuration in an untracked file such as `.env.local`, and provide an `.env.example` file with placeholder values whenever new environment variables are required.
