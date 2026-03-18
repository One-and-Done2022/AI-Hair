# Repository Guidelines

## Project Structure & Module Organization
The repository now contains two main surfaces:

- `backend/`: FastAPI service for WeChat login, image upload, template delivery, async job creation, and Seedream generation.
- `miniapp/`: native WeChat Mini Program pages for upload, template selection, polling results, and history.
- `tests/`: backend API tests.

Keep product code inside `backend/app/` and page-specific logic inside `miniapp/pages/`. Do not add generated media, local secrets, or sample user photos to tracked paths.

## Build, Test, and Development Commands
Use the local virtual environment and run from the repository root:

- `python3 -m venv .venv && source .venv/bin/activate`: create and activate the local environment.
- `pip install -r requirements.txt`: install backend and test dependencies.
- `uvicorn app.main:app --reload --app-dir backend --port 8000`: start the FastAPI service.
- `pytest -q`: run backend tests.

In WeChat DevTools, use the repository root as the project directory; `project.config.json` already points `miniprogramRoot` to `miniapp/`.

## Coding Style & Naming Conventions
Follow standard Python conventions:

- Use 4-space indentation and UTF-8 text files.
- Prefer `snake_case` for files, functions, and variables.
- Use `PascalCase` for classes.
- Keep service logic in `backend/app/services/` and HTTP handlers in `backend/app/routers/`.

For Mini Program code, use lower-case page directories such as `pages/result/` and keep request helpers in `miniapp/utils/`.

Format Python consistently before review; if formatting tools are added later, standardize on `black`.

## Testing Guidelines
Add backend coverage in `tests/test_<feature>.py` using `pytest` and FastAPI `TestClient`. New API behavior should include at least one happy-path test and one failure-path check where practical. Use the mock image generator for automated tests instead of calling live Seedream.

## Commit & Pull Request Guidelines
Use short, imperative commits such as `Add job polling endpoint` or `Wire miniapp upload flow`. Work from `feature/*` branches and merge into `main` through reviewed PRs.

Pull requests should include:

- a brief summary of the change,
- any setup or verification commands used,
- linked issue numbers when applicable,
- screenshots for Mini Program UI changes,
- confirmation that `.env`, `storage/`, and local sample images remain untracked.

Keep PRs focused and small enough to review quickly.
