# Project Implementation Documentation

## Scope
This project implements a voice scheduling assistant that books appointments in Healthie through Playwright UI automation.

Core workflow:
1. Collect patient full name.
2. Collect date of birth.
3. Find patient in Healthie.
4. Collect appointment date.
5. Collect appointment time.
6. Create appointment.
7. Confirm result.

## What Is Implemented

### 1. Voice assistant orchestration (`bot.py`)
- Replaced generic assistant behavior with a scheduling-specific system prompt (`SCHEDULING_SYSTEM_PROMPT`).
- Added two LLM tools:
  - `lookup_patient_record(name, date_of_birth)`
  - `book_appointment(date, time)`
- Added `SchedulingSession` state to store:
  - `patient_name`, `date_of_birth`, `patient_id`, `appointment_date`, `appointment_time`
- Added per-connection session reset (`on_client_connected`) to avoid cross-caller state reuse.
- Registered tool handlers that call Healthie integration functions and return structured status payloads:
  - Lookup statuses: `missing_required_fields`, `lookup_error`, `not_found`, `found`
  - Booking statuses: `patient_not_selected`, `missing_required_fields`, `booking_error`, `booking_failed`, `booked`

### 2. Healthie authentication (`healthie.py`)
- Implemented `login_to_healthie()` with session reuse via module-level `_page` / `_browser`.
- Updated flow to Healthie’s current login path and behavior:
  - URL: `https://secure.gethealthie.com/account/login`
  - Two-step login (email, then password)
  - Handles post-auth "Continue to app" interstitial
- Uses robust selectors with `data-test-id` + fallback selectors.
- Success criteria is navigation away from `/account/login` (not fixed sleep).

### 3. Patient lookup (`healthie.py`)
- Implemented `find_patient(name, date_of_birth)`.
- Uses authenticated session and Healthie global client search.
- Matching policy is strict:
  - Name match + DOB match required (no name-only acceptance).
- DOB normalization and parsing supports multiple formats, including ordinal input (e.g., `31st May 2019`).
- Returns normalized payload:
  - `patient_id`, `name`, `date_of_birth`, `profile_url`
- Returns `None` for valid not-found outcomes.

### 4. Appointment creation (`healthie.py`)
- Implemented `create_appointment(patient_id, date, time)`.
- Navigates directly to `/users/{patient_id}` and opens Add Appointment sidebar.
- Fills form with defaults:
  - Appointment type: `Initial Consultation`
  - Contact type: `Video Call`
  - Video service: `Healthie Video Call`
  - Timezone target: `Europe/Madrid` (only changed if needed)
  - Notes: empty
  - Repeating: false
- Added `_select_react_option()` helper for Healthie React-select controls.
- Confirms booking by waiting for GraphQL `createAppointment` response and parsing appointment payload.
- Returns normalized result:
  - `appointment_id`, `patient_id`, `appointment_type`, `contact_type`, `date`, `time`, `end`, `timezone`

## Technical Decisions

### Prompt-led flow with tool calls (instead of explicit state machine)
- Decision: constrain LLM through system prompt + tool contracts.
- Why: fastest way to ship a working conversational prototype.
- Tradeoff: less deterministic than a hardcoded finite-state flow.

### Internal Python session state for operational IDs
- Decision: keep `patient_id` in `SchedulingSession`, not in user dialogue.
- Why: cleaner caller experience and safer separation between conversational and operational data.
- Tradeoff: in-memory only; not durable for distributed/production scenarios.

### UI automation over API integration
- Decision: use Playwright against Healthie UI.
- Why: fits challenge constraints and validates real user workflow.
- Tradeoff: brittle to UI/selector changes.

### Strict identity matching policy
- Decision: require name + DOB for patient selection.
- Why: reduces wrong-patient risk.
- Tradeoff: more parsing/normalization logic needed to avoid false negatives.


## Issues Encountered and Fixes

### Healthie login flow changed
- Symptom: old login logic failed.
- Root causes:
  - outdated route (`/users/sign_in` assumption)
  - one-step login assumption
  - brittle selectors
  - unhandled "Continue to app" interstitial
  - timing assumptions (`networkidle` / fixed sleeps)
- Fixes:
  - route update to `/account/login`
  - two-step credential flow
  - resilient selectors
  - interstitial handling
  - navigation-based success check

### DOB false negatives for ordinal dates
- Symptom: valid users not matched when caller gave DOB like `31st May 2019`.
- Root cause: ordinal suffixes were not normalized before parsing.
- Fixes:
  - ordinal normalization in `_parse_date_value()`
  - expanded parse formats
  - parsed-date fallback comparison between input DOB and result DOB
  - regression unit test

### React-select interaction fragility
- Symptom: dropdown interactions were flaky in real runs.
- Root cause: custom React-select controls are not native `<select>` elements.
- Fixes:
  - `_select_react_option()` helper with opener/input fallbacks
  - forced click and evaluate-click fallback
  - option selection by visible text
  - integration-driven refinements for timezone behavior

## Testing Strategy and Current Status

### Unit tests (`tests/test_healthie.py`)
- Focus: deterministic logic and control flow.
- Covers:
  - login guardrails
  - patient lookup matching behavior
  - appointment creation flow and response parsing
  - helper/date parsing logic
- Status: designed for fast local feedback using mocked Playwright objects.

### Integration tests (`tests/test_healthie_integration.py`)
- Focus: real Healthie E2E behavior.
- Covers:
  - `login_to_healthie()`
  - `find_patient()`
  - `create_appointment()`
- Important characteristic: side-effecting test creates real appointments.

## Known Limitations
- Session state is in-memory only (not persistent across process restarts).
- Bot-level context isolation depends on runtime behavior; explicit context reset beyond session object is limited.
- Healthie UI selector changes can break automation.
- Integration tests depend on live credentials and external app stability.
- Appointment defaults are module constants; not yet environment/clinic configurable.

## Suggested Next Hardening Steps
1. Add explicit deterministic state transitions for conversation flow.
2. Move defaults to structured configuration with validation.
3. Add retry/backoff and richer failure categorization for UI actions.
4. Add non-side-effecting smoke checks plus dedicated cleanup strategy for booking tests.
5. Add metrics around tool latency, failure rates, and ambiguity handling.

## Operational Commentary

### Latency: balancing speed with user experience and accuracy
- Main latency sources are LLM round trips and Playwright UI actions in Healthie.
- Speed should not be improved by skipping safety checks (identity verification, date/time clarification, booking confirmation from GraphQL response).
- Practical approach for this project:
  - Keep conversational turns short and ask only one missing field at a time.
  - Reuse authenticated browser session aggressively (already implemented).
  - Use deterministic waits/selectors rather than long blanket sleeps.
  - Add fast-fail validation before browser actions when input is clearly invalid/ambiguous.
- Target behavior: perceived responsiveness for callers while preserving booking correctness.

### Reliability: keeping the agent available despite external failures
- Current architecture depends on multiple external systems (AI providers, Healthie UI, network).
- Reliability should be treated as graceful degradation, not just “no errors.”
- Practical reliability controls:
  - Add provider fallback strategy for LLM (secondary provider or queue/retry path).
  - Add circuit breakers and bounded retries around Healthie automation and LLM/tool calls.
  - Expose clear user-safe fallback messages when booking cannot proceed in real time.
  - Add health checks for dependencies and a readiness gate before serving live calls.
- Goal: the assistant remains reachable and predictable even when one dependency is unavailable.

### Evaluation: verifying expected behavior continuously
- Evaluation should cover both conversation behavior and backend execution correctness.
- Practical evaluation layers:
  - Deterministic scenario tests for conversation paths (happy path, not found, ambiguity, tool failure).
  - Tool-call contract tests (input/output schema and status transitions).
  - Integration smoke tests for Healthie selectors and booking mutation shape.
  - Production telemetry review: tool success rate, booking completion rate, average turn latency, fallback frequency.
- Add a lightweight regression dataset (DOB/date/time edge cases, multi-detail utterances) and run it on prompt/tool changes.
- Goal: fast detection of behavior drift and confidence that the bot follows intended policy.
