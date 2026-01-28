# Repository Guidelines

## Project Structure & Module Organization
- `src/`: React frontend source. Entry points are `src/main.jsx` and `src/App.jsx`; shared UI pieces live in `src/components/`, state/context in `src/contexts/`, and helpers in `src/utils/`.
- `canonical/`: Python implementation for the Canonical spec engine and API (CLI, engine, models, store, adapters).
- `docs/`: Product and technical specifications plus MVP contract docs.
- `scripts/`: Helper scripts such as `start_api.sh`, `restart_frontend.sh`, and `restart_backend.sh`.
- `assets/` and `inputs/`: Static assets and sample inputs.
- Root config: `vite.config.js`, `index.html`, `package.json`, `requirements.txt`.

## Build, Test, and Development Commands
Frontend (Vite):
- `npm run dev` — start the frontend dev server.
- `npm run build` — create a production build.
- `npm run preview` — preview the production build locally.
- `npm run lint` — run ESLint across the repo.

Backend/API (Python):
- `pip install -r requirements.txt` — install backend dependencies.
- `scripts/start_api.sh` — start the FastAPI server (see `README_API.md`).

## Coding Style & Naming Conventions
- JavaScript/React uses 2-space indentation and semicolons (match existing `src/*.jsx`).
- Prefer named components and hooks; keep files in `src/components/` and `src/contexts/` aligned with their role.
- Lint with ESLint via `npm run lint` before shipping UI changes.
- Python tooling listed in `requirements.txt` includes `black`, `flake8`, and `mypy`; use them when touching backend code if the team enables them.

## Testing Guidelines
- No frontend test suite is present yet. If adding tests, place them alongside components (e.g., `src/components/Foo.test.jsx`) or under a new `tests/` directory.
- Python testing dependencies (pytest + pytest-cov) are available, but there are no test folders yet. Prefer `tests/test_*.py` naming when you add coverage.

## Commit & Pull Request Guidelines
- Recent commits use conventional prefixes like `feat:`, `fix:`, and `chore:`; follow that pattern.
- Some automated commits are prefixed with `[Cursor]` — avoid using that unless you are an automation tool.
- PRs should include: a short summary, the motivation or linked issue, and UI screenshots or recordings when the frontend changes.

## Configuration & Environment
- API endpoints expect a running FastAPI server; see `README_API.md` for `.env` keys such as `CANONICAL_LLM_API_KEY` and Feishu tokens.
- Keep secrets out of the repo; use local `.env` only.
