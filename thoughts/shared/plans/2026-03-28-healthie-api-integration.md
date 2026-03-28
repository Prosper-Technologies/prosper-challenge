---
date: 2026-03-28T12:00:00Z
topic: "Healthie API Integration"
status: completed
autonomy: critical
---

# Plan: Healthie API Integration

## Goal

Replace Playwright-based browser automation with direct Healthie GraphQL API calls for patient lookup and appointment creation. Create `find_patient_api` and `create_appointment_api` functions that mirror the signatures/return types of the existing Playwright versions.

## Context

- Healthie staging API: `https://staging-api.gethealthie.com/graphql`
- Auth headers: `Authorization: Basic <API_KEY>`, `AuthorizationSource: API`
- The API is GraphQL-based
- `HEALTHIE_API_KEY` already exists in `.env.example` (unused in code today)
- Current functions return `dict | None` — new functions must match this contract

## Research Summary

### Healthie API Details

| Item | Detail |
|---|---|
| Endpoint | `https://staging-api.gethealthie.com/graphql` |
| Auth header | `Authorization: Basic <HEALTHIE_API_KEY>` |
| Auth source header | `AuthorizationSource: API` |
| Patient search | `users(keywords: "...")` query — searches by name, DOB, email, etc. |
| Create appointment | `createAppointment` mutation with `appointment_type_id`, `datetime`, `attendee_ids` |
| List appointment types | `appointmentTypes` query — needed to pick the first type |

### Key GraphQL Operations

**Find patient:**
```graphql
query GetPatients($keywords: String) {
  users(keywords: $keywords, active_status: "Active") {
    id
    first_name
    last_name
    dob
  }
}
```

**List appointment types:**
```graphql
query GetAppointmentTypes {
  appointmentTypes {
    id
    name
  }
}
```

**Create appointment:**
```graphql
mutation CreateAppointment(
  $appointment_type_id: String
  $datetime: String
  $attendee_ids: [String]
) {
  createAppointment(input: {
    appointment_type_id: $appointment_type_id
    datetime: $datetime
    attendee_ids: $attendee_ids
  }) {
    appointment {
      id
      date
      start_time
      end_time
    }
    messages {
      field
      message
    }
  }
}
```

## Phases

### Phase 1: Create Healthie API client

**File**: `app/integrations/healthie_api.py` (new)

**What**:
- Create `HealthieApiClient` class that wraps `httpx.AsyncClient` for GraphQL calls
- Load `HEALTHIE_API_KEY` from environment via `os.environ`
- Provide a generic `async execute(query, variables)` method
- Provide a singleton `get_client()` function (matching the pattern in `healthie_playwright.py`)
- Include a `patient_cache: dict[str, str]` for name lookups (same pattern as Playwright client)

**Constants**:
- `STAGING_API_URL = "https://staging-api.gethealthie.com/graphql"`

**Dependencies to add**:
- `httpx` to `pyproject.toml` dependencies

**Acceptance criteria**:
- [x] `HealthieApiClient` can execute a simple introspection query against staging
- [x] API key is read from env; raises clear error if missing

### Phase 2: Implement `find_patient_api`

**File**: `app/shared/tools/find_patient.py` (add to existing file)

**What**:
- Add `async def find_patient_api(name: str, date_of_birth: str) -> dict | None`
- Uses `HealthieApiClient.execute()` with the `users` query, passing `keywords=name`
- Iterates results, normalizes DOB from each result's `dob` field
- Compares against input `date_of_birth` using existing `_normalize_date()` helper
- Returns first match as `{"patient_id": id, "name": "First Last", "date_of_birth": dob}` or `None`
- Caches found patient in `client.patient_cache`

**Signature**: Identical to `find_patient_playwright` — `(name: str, date_of_birth: str) -> dict | None`

**Acceptance criteria**:
- [x] Returns matching patient dict when patient exists and DOB matches
- [x] Returns `None` when no patient found or DOB mismatch
- [x] Populates `patient_cache` on success

### Phase 3: Implement `create_appointment_api`

**File**: `app/shared/tools/create_appointment.py` (add to existing file)

**What**:
- Add `async def create_appointment_api(patient_id: str, date: str, time: str) -> dict | None`
- First queries `appointmentTypes` to get the first available type's ID
- Combines `date` (YYYY-MM-DD) and `time` (HH:MM) into datetime string `"YYYY-MM-DD HH:MM:00"`
- Calls `createAppointment` mutation with `appointment_type_id`, `datetime`, `attendee_ids=[patient_id]`
- Returns `{"appointment_id": actual_id, "patient_id": patient_id, "date": date, "time": time}` or `None`

**Signature**: Identical to `create_appointment_playwright` — `(patient_id: str, date: str, time: str) -> dict | None`

**Key improvement**: Unlike Playwright version (which always returns `appointment_id: "created"`), the API version returns the **actual appointment ID** from the mutation response.

**Acceptance criteria**:
- [x] Creates appointment and returns dict with real appointment ID
- [x] Returns `None` on API error, logging the error details
- [x] Handles missing appointment types gracefully

### Phase 4: Wire up new functions

**Files to modify**:
- `app/shared/tools/__init__.py` — add exports for `find_patient_api`, `create_appointment_api`
- `app/scheduling/handlers.py` — switch imports to use `_api` versions instead of `_playwright` versions

**What**:
- Update `__init__.py` to export both `_playwright` and `_api` versions
- Update `handlers.py` to import and call `find_patient_api` and `create_appointment_api`
- No changes to `nodes.py`, `prompts.py`, or the flow structure — signatures are identical

**Acceptance criteria**:
- [x] Bot flow uses API functions instead of Playwright
- [x] Playwright functions remain importable (not deleted) for fallback

### Phase 5: Add test scripts

**Files**: `scripts/test_find_patient_api.py`, `scripts/test_create_appointment_api.py` (new)

**What**:
- Mirror the existing `scripts/test_find_patient.py` and `scripts/test_create_appointment.py` patterns
- Simple async scripts that call the new API functions with test data
- Print results to stdout for manual verification

**Acceptance criteria**:
- [x] `test_find_patient_api.py` runs and finds/doesn't find patients correctly
- [x] `test_create_appointment_api.py` runs and creates an appointment

## Files Changed Summary

| File | Action |
|---|---|
| `pyproject.toml` | Add `httpx` dependency |
| `app/integrations/healthie_api.py` | **New** — API client |
| `app/shared/tools/find_patient.py` | Add `find_patient_api` function |
| `app/shared/tools/create_appointment.py` | Add `create_appointment_api` function |
| `app/shared/tools/__init__.py` | Export new functions |
| `app/scheduling/handlers.py` | Switch to API functions |
| `scripts/test_find_patient_api.py` | **New** — test script |
| `scripts/test_create_appointment_api.py` | **New** — test script |

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| API key permissions may be limited | Test with introspection query in Phase 1 before building on it |
| GraphQL schema may differ from docs | Validate actual response shapes in test scripts |
| Appointment type query may return empty | Log error and return `None` gracefully |
| DOB format from API may differ from UI | Reuse existing `_normalize_date()` which handles multiple formats |
