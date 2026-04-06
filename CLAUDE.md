# Healthie Voice Agent

## Tech Stack
- **Python 3.10+** with **Pipecat AI** (voice agent framework)
- **Playwright** for Healthie EHR browser automation, **httpx** for API calls
- Package manager: **uv** — always use `uv run` to execute commands

## Commands
```bash
uv run ruff check .          # Lint
uv run ruff format .         # Format
uv run mypy .                # Type check
uv run pytest tests/ -v      # Run all tests
uv run pytest tests/app/shared/tools/test_find_patient.py -v  # Single test file
```

## Code Structure
- `bot.py` — entry point, orchestrates the voice agent
- `app/scheduling/` — appointment flow: handlers, nodes (state machine), prompts
- `app/shared/tools/` — reusable tools (find_patient, create_appointment)
- `app/integrations/` — external adapters: `healthie_playwright.py`, `healthie_api.py`
- `tests/` — mirrors `app/` structure; all tools must have test coverage

## Principles
- **Fix root causes** — never patch symptoms or silence errors
- **Lint code** — run linting and type checks before considering work done
- **Separation of concerns** — integrations stay in `integrations/`, business logic in `scheduling/`, reusable pieces in `shared/tools/`
- **Include tests** — new tools and business logic always need tests
- **Keep it simple** — no speculative abstractions; solve the problem at hand
