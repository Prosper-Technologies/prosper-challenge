# Solution: Decision Log

## Description

A voice agent for scheduling appointments with Healthie-based healthcare providers. The bot is built with [Pipecat](https://github.com/pipecat-ai/pipecat) and [pipecat-flows](https://github.com/pipecat-ai/pipecat-flows), which models the conversation as a directed graph of nodes. Each node scopes a specific step in the flow and exposes only the tools relevant to that step.

The scheduling flow is sequential: the bot first collects the patient's name and date of birth, looks them up via the Healthie GraphQL API, then — if found — collects appointment preferences and creates the appointment. Conversation state transitions are driven by function calls that the LLM makes when it has gathered the required information for each node.

Backend integrations live in `app/integrations/` (Healthie API client) and are exposed to the flow layer through tool wrappers in `app/shared/tools/`, keeping the conversation logic decoupled from the specific EHR backend.

---

Architecture decisions for the appointment scheduling voice agent, recorded as they were made.

---

## 1. Sequential flow vs upfront collection

**Decision**: Sequential -- ask for name + DOB first, validate patient, then ask for appointment details.

**Alternative**: Upfront collection -- gather all four fields at once, call both functions back-to-back.

**Tradeoff**: Upfront is faster in the happy path but wastes the user's time if the patient isn't found. In a voice interface where corrections are slow, failing fast with actionable feedback ("I couldn't find you, want to try different details?") beats collecting information that may be useless.

---

## 2. pipecat-flows vs plain function calling

**Decision**: Use pipecat-flows (node-based conversation graph).

**Alternative**: Plain Pipecat function calling with `register_function` and a single system prompt.

**Tradeoff**: Plain function calling exposes all tools at every step, relying on the system prompt to enforce ordering. The LLM can skip steps or call functions in the wrong order, and adding steps means rewriting the prompt. pipecat-flows gives structural guarantees: each node scopes which tools are visible, so ordering bugs are impossible. The cost is an extra dependency and a small learning curve -- worth it because prompt engineering can't guarantee correctness. One caveat we are assuming is that pipecat flows are less flexible for free-form conversation — harder to handle "I want to go back and change my name"

---

## 3. Healthie GraphQL API vs Playwright browser automation

**Decision**: Instead of using Playwright-based browser automation for finding patients and creating appointments, we use direct Healthie GraphQL API calls (`find_patient_api`, `create_appointment_api`). The bot uses the API functions for patient lookup and appointment creation.

**Alternative**: Continue using Playwright to drive Healthie's web UI.

**Why the API is better**:

- **Reliability**: Browser automation is inherently fragile. Selectors break when Healthie deploys UI changes, SPAs have unpredictable loading states, and multi-step form interactions can fail silently. A GraphQL API call either succeeds or returns an explicit error -- no flaky waits, no stale selectors, no "is the page loaded yet?" guessing.
- **Speed**: A Playwright flow for `find_patient` navigates pages, waits for search dropdowns (3+ seconds), then navigates to a detail page to verify DOB -- easily 8-10 seconds. The equivalent API call is a single HTTP POST returning in ~200ms. For a voice agent where response latency directly affects user experience, this is a critical improvement.
- **Data quality**: The Playwright `create_appointment` function couldn't extract the actual appointment ID from the UI -- it returned a hardcoded `"created"` string. The API returns the real appointment ID from the mutation response, enabling proper confirmation and follow-up.
- **No browser dependency**: Playwright requires a headless Chromium instance (~400MB), session cookie management, and login flow handling. The API client is a lightweight HTTP client with a single API key header -- no browser process, no session expiration, no multi-step login dance.
- **Simpler error handling**: Playwright errors are opaque (timeout, element not found, navigation failed). GraphQL errors are structured (`messages: [{field, message}]`), making it straightforward to surface meaningful feedback to the user.

**Staging environment note**: We use Healthie's staging environment because the API (`staging-api.gethealthie.com/graphql`) is freely available in the staging/sandbox environment. In production, API access requires a paid plan. This is sufficient for development and demonstration; a production deployment would switch to the production API endpoint with a paid API key.

Note that the Playwright functions remain in the codebase as documentation of the UI-based approach. They could be used as fallback mechanisms if necessary.

---

## 4. Tools decoupled from Healthie vs direct Healthie imports in handlers

**Decision**: Tool functions in `app/shared/tools/` and removed healthie.py file. Handlers import tools, not Healthie directly.

**Alternative**: Handlers call `healthie.find_patient()` / `healthie.create_appointment()` directly.

**Tradeoff**: Direct Healthie coupling means swapping to another EHR requires changing the flow layer. With tools as an abstraction boundary, the backend is an implementation detail -- swap Healthie for another service by changing the tool files, not the conversation flow. The dummy implementations also enable end-to-end testing of the full flow without a running Healthie instance.

---

## 5. Pre-commit hooks for ruff and mypy

**Decision**: Add pre-commit hooks that run ruff (lint + format) and mypy (type checking) on every commit.

**Alternative**: Rely on CI-only checks or manual linting before pushing.

**Tradeoff**: Pre-commit hooks catch lint and type errors before they enter the git history, giving instant feedback without waiting for a CI round-trip. The cost is a small delay on each commit (~1-2 seconds for incremental checks) and requiring developers to run `uv run pre-commit install` after cloning. This is worth it because fixing issues at commit time is cheaper than fixing them after review feedback or a failed CI run.

---

## 6. E2E integration test scripts instead of unit tests (for Playwright flows only)

**Decision**: Provide manual integration test scripts (`scripts/test_find_patient_playwright.py`, `scripts/test_create_appointment_playwright.py`, `scripts/test_e2e_flow.py`) that run against Healthie. No unit tests with mocked Playwright.

**Alternative**: Unit tests that mock Playwright's page/locator objects to verify the automation logic in isolation.

**Tradeoff**: The value of these tools is that they interact correctly with Healthie's real UI -- the exact selectors, the SPA loading behavior, the multi-step login. Mocking Playwright would test that our code calls `.fill()` and `.click()` in the right order, but wouldn't catch the failures that actually matter: a selector changing after a Healthie deploy, a new loading spinner, or a form field being renamed. Mocked tests pass when the mock matches our assumptions; they fail to catch when our assumptions no longer match reality. E2E scripts against staging catch exactly those regressions. The cost is that tests require network access and a valid staging account, making them unsuitable for CI -- but for browser automation tools, that tradeoff is correct.

---

## 7. GitHub Actions CI pipeline

**Decision**: Add a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs lint, type checking, and unit tests on every push to `main` and on every pull request.

**Alternative**: Rely solely on pre-commit hooks and manual local testing.

**Tradeoff**: Pre-commit hooks catch issues locally but are easily bypassed (`--no-verify`) and don't run in all environments (e.g., GitHub web editor, merge commits). CI provides a shared, authoritative gate that blocks merges when checks fail. The workflow runs two parallel jobs -- `lint` (ruff + mypy) and `test` (pytest) -- so feedback is fast. We intentionally exclude the E2E integration scripts (`scripts/test_*.py`) from CI since they require network access to Healthie staging and valid credentials; only the unit tests in `tests/` run in CI. The cost is GitHub Actions minutes, which are free for public repos and generous for private ones.
