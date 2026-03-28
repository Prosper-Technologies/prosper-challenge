---
date: 2026-03-28T22:00:00Z
topic: "Playwright Healthie Integration"
status: completed
autonomy: critical
commit_per_phase: true
---

# Playwright Healthie Integration Implementation Plan

## Overview
Replace the dummy implementations of `find_patient` and `create_appointment` with real Playwright-based browser automation that interacts with Healthie's staging UI. Create a reusable `HealthiePlaywrightClient` class in `app/integrations/healthie_playwright.py` that encapsulates login, session management (with `storage_state` persistence), patient search, and appointment creation.

## Current State Analysis

### Existing Code:
- **`app/shared/tools/utils.py`**: Contains `login_to_healthie()` with module-level globals `_browser` and `_page`. Uses `input[name="email"]` selector which is **outdated** — the actual login form uses `input[name="identifier"]` and has a multi-step flow (email → submit → password → submit → passkey prompt → "Continue to app").
- **`app/shared/tools/find_patient.py:9-25`**: Dummy implementation returning hardcoded `{"patient_id": "dummy-123", ...}`.
- **`app/shared/tools/create_appointment.py:9-28`**: Dummy implementation returning hardcoded `{"appointment_id": "appt-456", ...}`.
- **`app/scheduling/handlers.py`**: Imports and calls `find_patient(name, dob)` and `create_appointment(patient_id, date, time)` — these signatures must be preserved.
- **`app/shared/tools/__init__.py`**: Re-exports both functions.

### Key UI Discoveries (from Playwright exploration):

**Login Flow** (multi-step):
1. Navigate to `/users/sign_in` → redirects to `/account/login`
2. Fill `input[name="identifier"]` with email, click first `button[type="submit"]`
3. Wait for `input[name="password"]` to become visible, fill it
4. Click `button:has-text("Log In")`
5. Handle passkey prompt: click `a:has-text("Continue to app")`
6. Wait for dashboard to load

**Patient Search** (global search bar):
- Search input: `input[name="keywords"]` with `placeholder="Search Clients..."` and `aria-label="Search Clients"`
- Typing a name shows a dropdown with results like: `a._userName_709sz_1` linking to `/users/{id}`
- Example: "Jeff" → "Jeff Mills" → `/users/5769986`
- Shows "No results..." if not found

**Client Detail Page** (`/users/{id}`):
- Shows: name, phone, DOB ("Date of birth" field), group, location, timezone
- Unique client ID visible (e.g., `5769986`)
- DOB may be "Not Set" for some clients

**Appointment Creation** (modal from dashboard):
- Trigger: Click `button:has-text("Add New Appointment")` on home page
- Modal class: `_asideModalBackground_m7fvj_1`
- Form fields:
  - **Invitee** (`#user`): Type client name, select from dropdown
  - **Appointment type** (`#appointment_type_id`): Dropdown with options like "Initial Consultation - 60 Minutes", "Follow-up Session - 45 Minutes"
  - **Contact type** (`#contact_type`): Default "Video Call"
  - **Start date** (`#date`, `name="date"`): Pre-filled with current date, format "March 28, 2026"
  - **Start time** (`#time`, `name="time"`): Pre-filled "12:00 PM", placeholder "Select a time"
  - **Timezone** (`#timezone`): Auto-detected
  - **Notes** (`textarea[name="notes"]`): Optional
- Submit: `button:has-text("Add Individual Session")`

**SPA Behavior Notes**:
- Sub-pages like `/clients`, `/calendar` load slowly (SPA spinners)
- Sidebar navigation works: clicking "Clients" → `/clients/active` loads a table with client rows
- Client rows link to `/users/{id}`
- Dashboard/home page loads fastest and has both search bar and "Add New Appointment"

## Desired End State

1. A `HealthiePlaywrightClient` class in `app/integrations/healthie_playwright.py` that:
   - Manages browser lifecycle with async context manager
   - Handles the multi-step login flow
   - Persists session via `storage_state` to `auth/healthie_state.json`
   - Reuses sessions when cookies are still valid
   - Provides `search_patient(name)` and `create_appointment(patient_id, date, time)` methods

2. `find_patient(name, dob)` in `app/shared/tools/find_patient.py` uses the client to search by name, navigate to the client detail page, verify DOB matches, and return patient info.

3. `create_appointment(patient_id, date, time)` in `app/shared/tools/create_appointment.py` uses the client to open the appointment modal, fill the form, and submit.

4. `app/shared/tools/utils.py` is cleaned up (login logic moved to the client).

## Quick Verification Reference

Common commands:
- `uv run ruff check app/` — linting
- `uv run pyright app/` — type checking
- `uv run python scripts/test_find_patient.py` — manual integration test
- `uv run python scripts/test_create_appointment.py` — manual integration test

Key files:
- `app/integrations/healthie_playwright.py` — new Playwright client
- `app/shared/tools/find_patient.py` — updated implementation
- `app/shared/tools/create_appointment.py` — updated implementation
- `app/shared/tools/utils.py` — cleaned up (login removed)
- `auth/healthie_state.json` — session persistence (gitignored)

## What We're NOT Doing
- Changing the function signatures in `find_patient` or `create_appointment`
- Modifying `app/scheduling/handlers.py` or `app/scheduling/nodes.py`
- Adding unit tests with mocked Playwright (these are integration tools; manual testing is appropriate)
- Supporting multiple concurrent sessions or thread safety
- Handling appointment type selection (will use the first/default appointment type)

## Implementation Approach
Build bottom-up: client class first, then patient search, then appointment creation. Each phase is independently verifiable. The client class manages a singleton browser instance with session persistence, similar to the current `utils.py` pattern but properly encapsulated.

---

## Phase 1: HealthiePlaywrightClient — Login & Session Management

### Overview
Create the `HealthiePlaywrightClient` class with login, session persistence, and browser lifecycle management. Move login logic from `utils.py` to the new client. Add `auth/` to `.gitignore`.

### Changes Required:

#### 1. New Integration Client
**File**: `app/integrations/__init__.py` (new, empty)
**File**: `app/integrations/healthie_playwright.py` (new)
**Changes**:
- Create `HealthiePlaywrightClient` class with:
  - `__init__(self)`: Initialize state (no browser yet)
  - `async ensure_browser(self) -> Page`: Lazy-init browser, try restoring session from `storage_state`, fall back to fresh login
  - `async _login(self, context) -> Page`: Implement the full multi-step login:
    1. Navigate to `/users/sign_in`
    2. Fill `input[name="identifier"]`, click submit
    3. Wait for `input[name="password"]`, fill it, click "Log In"
    4. Handle passkey prompt ("Continue to app")
    5. Wait for dashboard (loading spinner to disappear)
    6. Save `storage_state` to `auth/healthie_state.json`
  - `async _try_restore_session(self) -> Page | None`: Try to create context with saved storage state, verify by checking if we land on dashboard (not login page)
  - `async close(self)`: Clean up browser and playwright instances
  - Module-level singleton: `_client: HealthiePlaywrightClient | None = None` with `async def get_client() -> HealthiePlaywrightClient`
  - `self.patient_cache: dict[str, str] = {}` for patient_id → name mapping (used by Phase 3)

#### 2. Update utils.py
**File**: `app/shared/tools/utils.py`
**Changes**: Remove the `login_to_healthie` function and all Playwright-related code. The file can either be deleted or left with a docstring. Since `login_to_healthie` is not imported by handlers.py (handlers import from `find_patient` and `create_appointment` directly), we can safely remove the contents.

#### 3. Gitignore
**File**: `.gitignore`
**Changes**: Add `auth/` directory to prevent committing session cookies.

### Success Criteria:

#### Automated Verification:
- [x] Linting passes: `uv run ruff check app/integrations/`
- [x] File exists: `ls app/integrations/healthie_playwright.py`
- [x] No broken imports: `uv run python -c "from app.integrations.healthie_playwright import get_client; print('OK')"`
- [x] Auth dir gitignored: `grep -q 'auth/' .gitignore`

#### Manual Verification:
- [x] Run `uv run python -c "import asyncio; from app.integrations.healthie_playwright import get_client; asyncio.run(get_client().ensure_browser())"` — should log in and create `auth/healthie_state.json`
- [x] Run the same command again — should reuse the saved session (faster, logs "Restoring session")
- [x] Delete `auth/healthie_state.json` and run again — should do a fresh login

**Implementation Note**: After completing this phase, pause for manual confirmation of login flow. Create commit after verification passes.

---

## Phase 2: find_patient Implementation

### Overview
Implement `find_patient(name, dob)` using the Playwright client to search for patients via the global search bar and verify their DOB on the client detail page.

### Changes Required:

#### 1. Patient Search Implementation
**File**: `app/shared/tools/find_patient.py`
**Changes**:
- Import `get_client` from `app.integrations.healthie_playwright`
- Implement `find_patient(name, date_of_birth)`:
  1. Get authenticated page via `client.ensure_browser()`
  2. Navigate to home page (if not already there)
  3. Fill `input[name="keywords"]` with patient name
  4. Wait for search results dropdown (up to 5s)
  5. Check for "No results..." text → return `None`
  6. Find the first result link (class contains `_userName_`) and extract:
     - Patient name from link text
     - Patient ID from href (`/users/{id}`)
  7. Navigate to `/users/{id}` to get DOB from the detail page
  8. Look for "Date of birth" field value on the client detail page
  9. Compare DOB with the provided `date_of_birth` parameter
  10. Return `{"patient_id": id, "name": name, "date_of_birth": dob}` if match, or `None` if DOB doesn't match
  11. Populate `client.patient_cache[patient_id] = name`
  12. Clear the search input after search
- Keep the same function signature: `async def find_patient(name: str, date_of_birth: str) -> dict | None`

#### 2. Test Script
**File**: `scripts/test_find_patient.py` (new)
**Changes**: Simple script that calls `find_patient("Jeff Mills", "some-dob")` and prints the result.

### Success Criteria:

#### Automated Verification:
- [x] Linting passes: `uv run ruff check app/shared/tools/find_patient.py`
- [x] Import works: `uv run python -c "from app.shared.tools import find_patient; print('OK')"`

#### Manual Verification:
- [x] Run `uv run python scripts/test_find_patient.py` with a known patient name → returns patient dict with correct ID
- [x] Run with a non-existent patient name → returns `None`
- [x] The function signature is unchanged (handlers.py still works)

**Implementation Note**: After completing this phase, pause for manual confirmation of patient search. Create commit after verification passes.

---

## Phase 3: create_appointment Implementation

### Overview
Implement `create_appointment(patient_id, date, time)` using the Playwright client to open the appointment modal, fill the form, and submit.

### Changes Required:

#### 1. Appointment Creation Implementation
**File**: `app/shared/tools/create_appointment.py`
**Changes**:
- Import `get_client` from `app.integrations.healthie_playwright`
- Implement `create_appointment(patient_id, date, time)`:
  1. Get authenticated page via `client.ensure_browser()`
  2. Navigate to home page
  3. Click `text=Add New Appointment`
  4. Wait for modal to appear (`text=Add to Calendar`)
  5. Fill **Invitee** field (`#user`): Look up patient name from `client.patient_cache[patient_id]`, type it, wait for and select the dropdown result
  6. Select first **Appointment type** from `#appointment_type_id` dropdown (click to open, click first option)
  7. Fill **Start date** (`#date`): Clear and type the formatted date (convert YYYY-MM-DD to "Month DD, YYYY")
  8. Fill **Start time** (`#time`): Clear and type the formatted time (convert HH:MM 24h to "H:MM AM/PM")
  9. Click `button:has-text("Add Individual Session")`
  10. Wait for confirmation (modal closes or success message)
  11. Return `{"appointment_id": generated_id, "patient_id": patient_id, "date": date, "time": time}` on success
  12. Return `None` on failure
- Keep the same function signature: `async def create_appointment(patient_id: str, date: str, time: str) -> dict | None`

**Note on patient_id → name resolution**: The appointment modal needs a patient name for the invitee field. Uses `client.patient_cache` populated by `find_patient` in Phase 2. Falls back to navigating to `/users/{patient_id}` to get the name if cache miss.

#### 2. Test Script
**File**: `scripts/test_create_appointment.py` (new)
**Changes**: Script that calls `find_patient` then `create_appointment` and prints results.

### Success Criteria:

#### Automated Verification:
- [x] Linting passes: `uv run ruff check app/shared/tools/create_appointment.py`
- [x] Import works: `uv run python -c "from app.shared.tools import create_appointment; print('OK')"`

#### Manual Verification:
- [x] Run `uv run python scripts/test_create_appointment.py` → creates appointment in Healthie staging
- [ ] Verify the appointment appears in the Healthie calendar UI
- [x] The function signature is unchanged (handlers.py still works)

**Implementation Note**: After completing this phase, pause for manual confirmation of appointment creation. Create commit after verification passes.

---

## Phase 4: Cleanup & Integration Test

### Overview
Remove old `utils.py` login code, ensure end-to-end flow works with the bot, and clean up exploration scripts.

### Changes Required:

#### 1. Clean up utils.py
**File**: `app/shared/tools/utils.py`
**Changes**: Remove file entirely or leave empty with a docstring. The `login_to_healthie` function is no longer needed.

#### 2. End-to-end integration test
**File**: `scripts/test_e2e_flow.py` (new)
**Changes**: Script that simulates the full flow: find patient → create appointment, verifying the complete pipeline works.

#### 3. Clean up exploration scripts
**File**: `scripts/explore_healthie_ui.py`
**Changes**: Can be kept as documentation/reference or removed.

### Success Criteria:

#### Automated Verification:
- [x] Full lint passes: `uv run ruff check app/`
- [ ] Type check passes: `uv run pyright app/`
- [x] All imports work: `uv run python -c "from app.shared.tools import find_patient, create_appointment; from app.integrations.healthie_playwright import get_client; print('OK')"`
- [x] No references to old utils login: `grep -r "login_to_healthie" app/` returns nothing

#### Manual Verification:
- [ ] Run `uv run python scripts/test_e2e_flow.py` — complete flow works
- [ ] Run the bot (`uv run python bot.py`) and test the full conversation flow
- [ ] Verify no regressions in the bot's conversation flow

**Implementation Note**: After completing this phase, pause for final confirmation. Create commit after verification passes.

---

## Testing Strategy
- **No unit tests**: These are browser automation integration tools. Mocking Playwright would test the mock, not the integration.
- **Manual integration tests**: Test scripts in `scripts/` directory for each function.
- **E2E test**: Full flow script simulating the bot's conversation pipeline.
- **Regression**: Verify the bot still works end-to-end after all changes.

## References
- UI exploration screenshots: `scripts/screenshots/`
- Existing research: `thoughts/shared/research/20260327_how-the-bot-works.md`
- Playwright Python docs: https://playwright.dev/python/docs/auth (storage_state pattern)
