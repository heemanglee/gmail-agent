# Repository Guidelines

## Project Structure & Module Organization

Application code lives under `app/`. Put agent construction and CLI behavior in `app/agent/`, environment handling in `app/core/`, Gmail MCP integration in `app/mcp/`, and future HTTP/SSE endpoints in `app/server/`. `main.py` is the minimal application entry point. Tests mirror these modules in `tests/test_*.py`. Keep product and integration documentation in `docs/`; OAuth verification utilities belong in `scripts/`.

## Build, Test, and Development Commands

- `uv sync`: create `.venv` and install versions pinned in `uv.lock`.
- `cp .env.example .env`: create local configuration; fill in required values without committing secrets.
- `uv run python main.py`: validate configuration and run the basic entry point.
- `uv run python -m app.agent.cli`: start the interactive Gmail agent; this requires working OpenAI, Gmail OAuth, and MCP settings.
- `uv run pytest`: run the complete offline test suite. Use `uv run pytest tests/test_mcp_filter.py -q` for a focused check.

There is currently no separate build, lint, formatter, or coverage command configured in `pyproject.toml`.

## Coding Style & Naming Conventions

Use Python 3.12 syntax, four-space indentation, PEP 8 naming, and type annotations on public functions. Name modules and functions with `snake_case`, classes with `PascalCase`, and environment-backed `Settings` fields with `UPPER_SNAKE_CASE`. Prefer short Korean docstrings and comments where that matches the surrounding module. Keep async boundaries explicit for MCP operations, and reuse the cached `app.core.config.settings` object rather than constructing settings repeatedly.

## Testing Guidelines

Tests use pytest, `monkeypatch`, and `capsys`. Name files `test_<module>.py` and tests `test_<behavior>`. Keep unit tests deterministic and offline by mocking model, OAuth, and MCP calls. Add regression tests for tool allowlists, especially to ensure permanent-delete tools never become available. No coverage threshold is enforced, but every behavior change should include a focused test.

## Commit & Pull Request Guidelines

Recent history follows Conventional Commit subjects such as `feat:`, `fix:`, and `docs:`; keep subjects imperative and scoped. Explain safety constraints and untested live integrations in the body when relevant. PRs should summarize behavior, link the issue, list verification commands, and call out credential, Gmail scope, or tool-permission changes. Include screenshots only for user-visible UI changes. Commits created by Codex must end with a blank line and `Co-Authored-By: Codex <noreply@openai.com>`.

## Security & Configuration

Never commit `.env`, OAuth client secrets, refresh tokens, or `token.json`. Update `.env.example` only with safe placeholders. Preserve the least-privilege Gmail tool allowlist and require human approval before exposing trash operations.
