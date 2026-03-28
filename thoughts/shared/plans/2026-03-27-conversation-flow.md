---
date: 2026-03-27T00:00:00Z
planner: claude
branch: main
repository: healthie-agent
topic: "Implement scheduling conversation flow using pipecat-flows"
tags: [plan, conversation-flow, pipecat-flows, scheduling]
status: completed
autonomy: critical
last_updated: 2026-03-27
last_updated_by: claude
research_refs:
  - thoughts/shared/research/20260327_how-the-bot-works.md
---

# Plan: Implement Scheduling Conversation Flow

**Date**: 2026-03-27
**Scope**: Conversation flow only (not Healthie tool call implementations)
**Approach**: pipecat-flows (node-based conversation graph), sequential flow

## Overview

Add a structured conversation flow so the bot:
1. Greets the patient and asks for their **name** and **date of birth**
2. Calls `find_patient` to look up the patient
3. If found, asks for the desired **appointment date and time**
4. Calls `create_appointment` to book the appointment
5. Confirms the booking or handles errors gracefully

The code is organized under `app/`: **`app/scheduling/`** holds the conversation flow (prompts, nodes, handlers), **`app/shared/tools/`** holds backend-agnostic tool functions reusable across flows, and **`healthie.py`** remains the low-level Healthie API client (unused until tools go real). See brainstorm: `thoughts/shared/brainstorms/2026-03-27-code-structure.md`.

## Architecture

```
bot.py                                    # Pipeline setup, FlowManager initialization
                                          #   imports from: app.scheduling

app/
  __init__.py
  scheduling/                             # Scheduling conversation flow
    __init__.py                           # Public API: exports create_greeting_node
    prompts.py                            # ROLE_MESSAGES, task message strings
    nodes.py                              # create_*_node() functions + FlowsFunctionSchema
    handlers.py                           # handle_find_patient, handle_create_appointment
                                          #   imports from: app.shared.tools
  shared/
    __init__.py
    tools/                                # Abstract tool capabilities (reusable across flows)
      __init__.py
      find_patient.py                     # Patient lookup (dummy impl for now)
      create_appointment.py               # Appointment creation (dummy impl for now)

healthie.py                               # Low-level Healthie Playwright automation (unused until tools go real)
```

### Dependency Chain (current, with dummies)
```
bot.py → app.scheduling → app.shared.tools
```
### Dependency Chain (future, with real Healthie)
```
bot.py → app.scheduling → app.shared.tools → healthie
```
Each layer only knows about the one below it. No circular dependencies.

### Conversation Graph

```
[greeting_node] ──find_patient──> [appointment_node] ──create_appointment──> [confirmation_node]
       │                                  │                                         │
       └── patient not found ─┐           └── booking failed ─┐                    └── end
                               │                                │
                               └── retry / end                  └── retry / end
```

---

## Phase 1: Add pipecat-ai-flows dependency

**Files**: `pyproject.toml`

### Steps

1.1. Add `pipecat-ai-flows` to the project dependencies in `pyproject.toml`:
   ```toml
   dependencies = [
       ...,
       "pipecat-ai-flows",
   ]
   ```

1.2. Run `uv sync` to install the new dependency.

### Verification
- `uv run python -c "from pipecat_flows import FlowManager; print('OK')"` succeeds

---

## Phase 2: Create `app/shared/tools/` (shared tool abstraction layer)

**Files**: `app/__init__.py`, `app/shared/__init__.py`, `app/shared/tools/__init__.py`, `app/shared/tools/find_patient.py`, `app/shared/tools/create_appointment.py`

The tools layer provides abstract capabilities that any flow's handlers can call. Tools live under `app/shared/` because they're not specific to scheduling -- other flows (e.g., intake) may reuse them. Each tool is in its own file with a dummy implementation. When we implement real Healthie integration later, these files will import from `healthie.py` -- but for now they're self-contained.

### Steps

2.1. Create package files:
- `app/__init__.py` (empty)
- `app/shared/__init__.py` (empty)
- `app/shared/tools/__init__.py`:
```python
from .find_patient import find_patient
from .create_appointment import create_appointment
```

2.2. Create `app/shared/tools/find_patient.py`:
```python
"""Patient lookup tool.

Dummy implementation for now. Will be backed by Healthie (or another EHR)
in a future PR. The flow layer calls this function without knowing
which backend fulfills the request.
"""


async def find_patient(name: str, date_of_birth: str) -> dict | None:
    """Look up a patient by name and date of birth.

    Args:
        name: The patient's full name.
        date_of_birth: The patient's date of birth (YYYY-MM-DD).

    Returns:
        dict with patient_id, name, date_of_birth if found, or None.
    """
    # TODO: Replace with real Healthie lookup via healthie.py
    return {"patient_id": "dummy-123", "name": name, "date_of_birth": date_of_birth}
```

2.3. Create `app/shared/tools/create_appointment.py`:
```python
"""Appointment creation tool.

Dummy implementation for now. Will be backed by Healthie (or another EHR)
in a future PR. The flow layer calls this function without knowing
which backend fulfills the request.
"""


async def create_appointment(patient_id: str, date: str, time: str) -> dict | None:
    """Create an appointment for a patient.

    Args:
        patient_id: The patient's ID from find_patient.
        date: The appointment date (YYYY-MM-DD).
        time: The appointment time (HH:MM, 24-hour).

    Returns:
        dict with appointment_id, patient_id, date, time if created, or None.
    """
    # TODO: Replace with real Healthie appointment creation via healthie.py
    return {"appointment_id": "appt-456", "patient_id": patient_id, "date": date, "time": time}
```

### Key design decisions
- Each tool is a standalone async function with a clear return contract
- Tools are backend-agnostic -- swapping from Healthie to another service means changing the tool internals, not the flow
- The `__init__.py` re-exports for clean imports: `from app.shared.tools import find_patient`
- Dummy implementations always succeed, enabling happy-path end-to-end testing

### Verification
- `uv run python -c "from app.shared.tools import find_patient, create_appointment; print('OK')"`
- `uv run python -c "import asyncio; from app.shared.tools import find_patient; print(asyncio.run(find_patient('Jane Doe', '1990-01-15')))"` returns `{'patient_id': 'dummy-123', ...}`

---

## Phase 3: Create `app/scheduling/` (conversation flow layer)

**Files**: `app/scheduling/__init__.py`, `app/scheduling/prompts.py`, `app/scheduling/nodes.py`, `app/scheduling/handlers.py`

The scheduling flow lives directly in `app/scheduling/` -- no extra `flows/` subfolder needed since the folder IS the flow. It's split into three files:
- **prompts.py** -- system messages (editable independently from logic)
- **nodes.py** -- node factory functions + tool schemas (the graph structure)
- **handlers.py** -- async business logic (calls shared tools, manages state transitions)

### Steps

3.1. Create `app/scheduling/__init__.py`:
```python
from .nodes import create_greeting_node
```

3.2. Create `app/scheduling/prompts.py`:
```python
"""System prompts for the scheduling conversation flow.

Edit these to change what the bot says without touching flow logic.
"""

ROLE_MESSAGES = [
    {
        "role": "system",
        "content": (
            "You are a friendly and professional digital assistant for the Prosper Health clinic. "
            "You help patients schedule appointments. Be warm, conversational, and concise. "
            "Always confirm information back to the patient before proceeding."
        ),
    }
]

GREETING_TASK = (
    "Greet the patient warmly and introduce yourself as a digital assistant "
    "from the Prosper Health clinic. Tell them you can help schedule an appointment. "
    "Ask for their full name and date of birth so you can look them up in the system. "
    "You must collect BOTH the name and date of birth before calling the function."
)

APPOINTMENT_TASK = (
    "The patient has been found in the system. Now ask them for their preferred "
    "appointment date and time. Once they provide both, create the appointment. "
    "Be flexible with how they express dates and times, but confirm the exact "
    "date and time before proceeding."
)

CONFIRMATION_TASK = (
    "The appointment has been booked. Summarize the appointment details "
    "(patient name, date, and time) back to the patient. Ask if there's "
    "anything else you can help with. If not, say goodbye warmly."
)

PATIENT_NOT_FOUND_TASK = (
    "The patient was not found in the system. Apologize and ask if they'd like "
    "to try again with different details. If they want to retry, ask for their "
    "name and date of birth again."
)
```

3.3. Create `app/scheduling/handlers.py`:
```python
"""Handler functions for the scheduling conversation flow.

Each handler is called when the LLM invokes a tool. Handlers call
tools from the tools layer and return (message, next_node) tuples.
"""

from pipecat_flows import FlowArgs, FlowManager

from app.shared.tools import find_patient, create_appointment


async def handle_find_patient(args: FlowArgs, flow_manager: FlowManager):
    """Handle the find_patient tool call. Transitions to appointment or not-found node."""
    from .nodes import create_appointment_node, create_patient_not_found_node

    name = args["name"]
    date_of_birth = args["date_of_birth"]

    result = await find_patient(name, date_of_birth)

    if result:
        flow_manager.state["patient_id"] = result["patient_id"]
        flow_manager.state["patient_name"] = result["name"]
        return (
            f"Patient found: {result['name']}.",
            create_appointment_node(),
        )
    else:
        return (
            "No patient found with that name and date of birth.",
            create_patient_not_found_node(),
        )


async def handle_create_appointment(args: FlowArgs, flow_manager: FlowManager):
    """Handle the create_appointment tool call. Transitions to confirmation node."""
    from .nodes import create_confirmation_node

    patient_id = flow_manager.state["patient_id"]
    date = args["date"]
    time = args["time"]

    result = await create_appointment(patient_id, date, time)

    if result:
        flow_manager.state["appointment"] = result
        return (
            f"Appointment created for {date} at {time}.",
            create_confirmation_node(),
        )
    else:
        return (
            "Sorry, there was an issue creating the appointment. Please try a different date or time.",
            None,  # Stay on appointment node to retry
        )
```

3.4. Create `app/scheduling/nodes.py`:
```python
"""Node definitions for the scheduling conversation flow.

Each function returns a NodeConfig dict that pipecat-flows uses
to configure a conversation state.
"""

from pipecat_flows import FlowsFunctionSchema, NodeConfig

from .prompts import (
    APPOINTMENT_TASK,
    CONFIRMATION_TASK,
    GREETING_TASK,
    PATIENT_NOT_FOUND_TASK,
    ROLE_MESSAGES,
)
from .handlers import handle_create_appointment, handle_find_patient


FIND_PATIENT_SCHEMA = {
    "name": {
        "type": "string",
        "description": "The patient's full name",
    },
    "date_of_birth": {
        "type": "string",
        "description": "The patient's date of birth in YYYY-MM-DD format",
    },
}


def create_greeting_node() -> NodeConfig:
    """Initial node: greet patient, ask for name and date of birth."""
    return {
        "role_messages": ROLE_MESSAGES,
        "task_messages": [{"role": "system", "content": GREETING_TASK}],
        "functions": [
            FlowsFunctionSchema(
                name="find_patient",
                description="Look up a patient by name and date of birth",
                properties=FIND_PATIENT_SCHEMA,
                required=["name", "date_of_birth"],
                handler=handle_find_patient,
            )
        ],
    }


def create_appointment_node() -> NodeConfig:
    """Second node: ask for appointment date and time."""
    return {
        "task_messages": [{"role": "system", "content": APPOINTMENT_TASK}],
        "functions": [
            FlowsFunctionSchema(
                name="create_appointment",
                description="Create an appointment for the patient",
                properties={
                    "date": {
                        "type": "string",
                        "description": "The appointment date in YYYY-MM-DD format",
                    },
                    "time": {
                        "type": "string",
                        "description": "The appointment time in HH:MM format (24-hour)",
                    },
                },
                required=["date", "time"],
                handler=handle_create_appointment,
            )
        ],
    }


def create_confirmation_node() -> NodeConfig:
    """Final node: confirm booking and say goodbye."""
    return {
        "task_messages": [{"role": "system", "content": CONFIRMATION_TASK}],
        "functions": [],
        "post_actions": [{"type": "end_conversation"}],
    }


def create_patient_not_found_node() -> NodeConfig:
    """Error node: patient not found, offer to retry or end."""
    return {
        "task_messages": [{"role": "system", "content": PATIENT_NOT_FOUND_TASK}],
        "functions": [
            FlowsFunctionSchema(
                name="find_patient",
                description="Look up a patient by name and date of birth",
                properties=FIND_PATIENT_SCHEMA,
                required=["name", "date_of_birth"],
                handler=handle_find_patient,
            )
        ],
    }
```

### Key design decisions
- **prompts.py** is pure text -- clinicians or prompt engineers can edit without touching logic
- **nodes.py** imports handlers at module level; **handlers.py** uses late imports for nodes (breaks circular dependency)
- **FIND_PATIENT_SCHEMA** is defined once and reused in greeting + not-found nodes
- **ROLE_MESSAGES** is set in greeting node only; pipecat-flows persists it across transitions
- **`app/scheduling/__init__.py`** exports `create_greeting_node` -- the single entry point for bot.py

### Verification
- `uv run python -c "from app.scheduling import create_greeting_node; print('OK')"`
- With dummy tool implementations (Phase 2), full flow is testable end-to-end

---

## Phase 4: Modify `bot.py` to use FlowManager

**Files**: `bot.py`

### Important: context_aggregator must be the full pair

Research confirmed that FlowManager expects the **full `LLMContextAggregatorPair` object** (not just the assistant half). Internally, FlowManager inspects the type and creates a `UniversalLLMAdapter` from the pair. The current `bot.py` constructs the pair manually via `LLMContextAggregatorPair(context, ...)`. We need to switch to `llm.create_context_aggregator(context)` which returns a pair object compatible with FlowManager, and then use `.user()` / `.assistant()` in the pipeline.

### Steps

4.1. **Add imports** (after existing imports, around line 59):
```python
from pipecat_flows import FlowManager
from app.scheduling import create_greeting_node
```

4.2. **Remove the old hardcoded system prompt and manual aggregator setup** (lines 79-94):
```python
# DELETE these lines:
messages = [
    {
        "role": "system",
        "content": "You are a friendly AI assistant. Respond naturally and keep your answers conversational.",
    },
]

context = LLMContext(messages)
user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
    context,
    user_params=LLMUserAggregatorParams(
        user_turn_strategies=UserTurnStrategies(
            stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=LocalSmartTurnAnalyzerV3())]
        ),
    ),
)
```

4.3. **Replace with FlowManager-compatible setup**:
```python
context = LLMContext()
context_aggregator = llm.create_context_aggregator(
    context,
    user_params=LLMUserAggregatorParams(
        user_turn_strategies=UserTurnStrategies(
            stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=LocalSmartTurnAnalyzerV3())]
        ),
    ),
)
```

4.4. **Update the pipeline** to use `context_aggregator.user()` and `context_aggregator.assistant()`:
```python
pipeline = Pipeline(
    [
        transport.input(),
        rtvi,
        stt,
        context_aggregator.user(),     # was: user_aggregator
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant(),  # was: assistant_aggregator
    ]
)
```

4.5. **Create FlowManager after task creation** (after line 118):
```python
flow_manager = FlowManager(
    task=task,
    llm=llm,
    context_aggregator=context_aggregator,
    transport=transport,
)
```

4.6. **Replace the on_client_connected handler** (lines 120-125):
```python
# REPLACE:
@transport.event_handler("on_client_connected")
async def on_client_connected(transport, client):
    logger.info(f"Client connected")
    messages.append({"role": "system", "content": "Say hello and briefly introduce yourself as a digital assistant from the Prosper Health clinic."})
    await task.queue_frames([LLMRunFrame()])

# WITH:
@transport.event_handler("on_client_connected")
async def on_client_connected(transport, client):
    logger.info(f"Client connected")
    await flow_manager.initialize(create_greeting_node())
```

4.7. **Clean up unused imports**:
- Remove `LLMRunFrame` from the frames import
- Remove `LLMContextAggregatorPair` import (no longer used directly)
- Remove `LLMContext` if it's fully replaced by `llm.create_context_aggregator`
- Keep `LLMUserAggregatorParams`, `UserTurnStrategies`, `TurnAnalyzerUserTurnStopStrategy` (still needed)

### Summary of bot.py changes
- **Added**: 2 import lines (FlowManager, create_greeting_node)
- **Removed**: old messages list, old LLMContext, old manual aggregator pair, old on_connect body
- **Modified**: context creation via `llm.create_context_aggregator()`, pipeline references, FlowManager init
- **Net change**: ~20 lines touched

### Verification
1. `uv run python -c "from pipecat_flows import FlowManager; print('OK')"` -- dependency works
2. `uv run python -c "from app.scheduling import create_greeting_node; print('OK')"` -- app module works
3. `uv run bot.py` -- bot starts without errors
4. Open `http://localhost:7860/client`, click Connect -- bot greets and asks for name + DOB
5. Provide name + DOB -- bot acknowledges patient found, asks for date + time
6. Provide date + time -- bot confirms appointment and says goodbye

---

**Note**: `healthie.py` is unchanged in this plan. The dummy implementations live in `app/shared/tools/` (Phase 2). When real Healthie integration is needed, the tool files will import from `healthie.py` -- but that's a future PR.

---

## Phase 5: Add tests

**Files**: `tests/app/scheduling/test_nodes.py`, `tests/app/scheduling/test_handlers.py`, `tests/app/shared/tools/test_find_patient.py`, `tests/app/shared/tools/test_create_appointment.py`

Tests mirror the source layout for predictable discovery.

### Steps

5.1. Add `pytest` and `pytest-asyncio` as dev dependencies in `pyproject.toml`:
```toml
[dependency-groups]
dev = [
    ...,
    "pytest",
    "pytest-asyncio",
]
```

5.2. Create package files (all empty `__init__.py`):
- `tests/__init__.py`
- `tests/app/__init__.py`
- `tests/app/scheduling/__init__.py`
- `tests/app/shared/__init__.py`
- `tests/app/shared/tools/__init__.py`

5.3. Create `tests/app/scheduling/test_nodes.py`:
```python
"""Tests for scheduling flow node definitions."""

from app.scheduling.nodes import (
    create_appointment_node,
    create_confirmation_node,
    create_greeting_node,
    create_patient_not_found_node,
)
from app.scheduling.prompts import ROLE_MESSAGES


class TestNodeDefinitions:
    def test_greeting_node_has_role_and_task_messages(self):
        node = create_greeting_node()
        assert node["role_messages"] == ROLE_MESSAGES
        assert len(node["task_messages"]) == 1
        assert node["task_messages"][0]["role"] == "system"

    def test_greeting_node_has_find_patient_function(self):
        node = create_greeting_node()
        assert len(node["functions"]) == 1
        assert node["functions"][0].name == "find_patient"

    def test_appointment_node_has_create_appointment_function(self):
        node = create_appointment_node()
        assert len(node["functions"]) == 1
        assert node["functions"][0].name == "create_appointment"

    def test_appointment_node_has_no_role_messages(self):
        node = create_appointment_node()
        assert "role_messages" not in node

    def test_confirmation_node_has_no_functions(self):
        node = create_confirmation_node()
        assert node["functions"] == []

    def test_confirmation_node_has_end_conversation_post_action(self):
        node = create_confirmation_node()
        assert node["post_actions"] == [{"type": "end_conversation"}]

    def test_patient_not_found_node_has_find_patient_function(self):
        node = create_patient_not_found_node()
        assert len(node["functions"]) == 1
        assert node["functions"][0].name == "find_patient"
```

5.4. Create `tests/app/scheduling/test_handlers.py`:
```python
"""Tests for scheduling flow handler functions."""

import pytest

from app.scheduling.handlers import handle_create_appointment, handle_find_patient


class FakeFlowManager:
    def __init__(self):
        self.state = {}


class TestHandleFindPatient:
    @pytest.mark.asyncio
    async def test_patient_found_transitions_to_appointment_node(self):
        fm = FakeFlowManager()
        result_msg, next_node = await handle_find_patient(
            {"name": "Jane Doe", "date_of_birth": "1990-01-15"}, fm
        )
        assert "Jane Doe" in result_msg
        assert next_node is not None
        assert len(next_node["functions"]) == 1
        assert next_node["functions"][0].name == "create_appointment"

    @pytest.mark.asyncio
    async def test_patient_found_updates_state(self):
        fm = FakeFlowManager()
        await handle_find_patient(
            {"name": "Jane Doe", "date_of_birth": "1990-01-15"}, fm
        )
        assert fm.state["patient_id"] == "dummy-123"
        assert fm.state["patient_name"] == "Jane Doe"

    @pytest.mark.asyncio
    async def test_patient_not_found_transitions_to_not_found_node(self):
        # Must patch the name in handlers module, not the source module,
        # because handlers.py binds find_patient via `from ... import`.
        import app.scheduling.handlers as handlers_module
        original = handlers_module.find_patient

        async def fake_not_found(name, dob):
            return None

        handlers_module.find_patient = fake_not_found
        try:
            fm = FakeFlowManager()
            result_msg, next_node = await handle_find_patient(
                {"name": "Nobody", "date_of_birth": "2000-01-01"}, fm
            )
            assert "not found" in result_msg.lower()
            assert next_node is not None
            assert next_node["functions"][0].name == "find_patient"
        finally:
            handlers_module.find_patient = original


class TestHandleCreateAppointment:
    @pytest.mark.asyncio
    async def test_appointment_created_transitions_to_confirmation(self):
        fm = FakeFlowManager()
        fm.state["patient_id"] = "dummy-123"
        result_msg, next_node = await handle_create_appointment(
            {"date": "2026-04-01", "time": "10:00"}, fm
        )
        assert "2026-04-01" in result_msg
        assert "10:00" in result_msg
        assert next_node is not None
        assert next_node["functions"] == []
        assert next_node["post_actions"] == [{"type": "end_conversation"}]

    @pytest.mark.asyncio
    async def test_appointment_created_updates_state(self):
        fm = FakeFlowManager()
        fm.state["patient_id"] = "dummy-123"
        await handle_create_appointment(
            {"date": "2026-04-01", "time": "10:00"}, fm
        )
        assert fm.state["appointment"]["appointment_id"] == "appt-456"
        assert fm.state["appointment"]["date"] == "2026-04-01"

    @pytest.mark.asyncio
    async def test_appointment_failed_stays_on_same_node(self):
        # Must patch the name in handlers module, not the source module,
        # because handlers.py binds create_appointment via `from ... import`.
        import app.scheduling.handlers as handlers_module
        original = handlers_module.create_appointment

        async def fake_fail(patient_id, date, time):
            return None

        handlers_module.create_appointment = fake_fail
        try:
            fm = FakeFlowManager()
            fm.state["patient_id"] = "dummy-123"
            result_msg, next_node = await handle_create_appointment(
                {"date": "2026-04-01", "time": "10:00"}, fm
            )
            assert "sorry" in result_msg.lower()
            assert next_node is None
        finally:
            handlers_module.create_appointment = original
```

5.5. Create `tests/app/shared/tools/test_find_patient.py`:
```python
"""Tests for the find_patient tool."""

import pytest

from app.shared.tools import find_patient


class TestFindPatient:
    @pytest.mark.asyncio
    async def test_dummy_always_returns_patient(self):
        result = await find_patient("Jane Doe", "1990-01-15")
        assert result is not None
        assert result["patient_id"] == "dummy-123"
        assert result["name"] == "Jane Doe"
        assert result["date_of_birth"] == "1990-01-15"
```

5.6. Create `tests/app/shared/tools/test_create_appointment.py`:
```python
"""Tests for the create_appointment tool."""

import pytest

from app.shared.tools import create_appointment


class TestCreateAppointment:
    @pytest.mark.asyncio
    async def test_dummy_always_returns_appointment(self):
        result = await create_appointment("patient-123", "2026-04-01", "10:00")
        assert result is not None
        assert result["appointment_id"] == "appt-456"
        assert result["patient_id"] == "patient-123"
        assert result["date"] == "2026-04-01"
        assert result["time"] == "10:00"
```

### Verification
- `uv run pytest tests/ -v` -- all tests pass
- Tests cover: node structure (7), handler happy paths (4), handler error paths (2), tool contracts (2)
- Total: ~15 tests

---

## Files Changed Summary

| File | Change | Lines |
|------|--------|-------|
| `pyproject.toml` | Add `pipecat-ai-flows`, `pytest`, `pytest-asyncio` | ~3 |
| `app/__init__.py` | New empty file | 0 |
| `app/scheduling/__init__.py` | New: exports `create_greeting_node` | ~2 |
| `app/scheduling/prompts.py` | New: system messages and task prompts | ~40 |
| `app/scheduling/nodes.py` | New: node factories + tool schemas | ~80 |
| `app/scheduling/handlers.py` | New: handler functions (calls shared tools) | ~50 |
| `app/shared/__init__.py` | New empty file | 0 |
| `app/shared/tools/__init__.py` | New: re-exports tool functions | ~3 |
| `app/shared/tools/find_patient.py` | New: patient lookup (dummy impl) | ~20 |
| `app/shared/tools/create_appointment.py` | New: appointment creation (dummy impl) | ~20 |
| `bot.py` | Wire FlowManager, remove old prompt | ~20 |
| `tests/app/scheduling/test_nodes.py` | New: node structure tests | ~40 |
| `tests/app/scheduling/test_handlers.py` | New: handler transition tests | ~80 |
| `tests/app/shared/tools/test_find_patient.py` | New: tool contract tests | ~15 |
| `tests/app/shared/tools/test_create_appointment.py` | New: tool contract tests | ~15 |

**Total new code**: ~370 lines (app + tests)
**Total modified code**: ~23 lines across bot.py + pyproject.toml
**healthie.py**: unchanged

## Resolved Questions

1. **FlowManager `context_aggregator` parameter**: RESOLVED. Must pass the full `LLMContextAggregatorPair` object returned by `llm.create_context_aggregator(context)`. FlowManager internally inspects the type and creates a `UniversalLLMAdapter`. Updated Phase 4 accordingly.
2. **`post_actions: end_conversation`**: RESOLVED. This is a built-in action type in pipecat-flows. No registration needed. It fires after the LLM response and TTS finish, cleanly ending the session.
3. **Healthie function return format**: RESOLVED. Dummy implementations in `app/shared/tools/` define the contract explicitly. Handlers depend on `patient_id`, `name` from find_patient and `appointment_id`, `patient_id`, `date`, `time` from create_appointment.
4. **Code structure**: RESOLVED. `app/scheduling/` contains flow files directly (prompts, nodes, handlers). Shared tools live in `app/shared/tools/` for reuse across flows. Dependency chain: `app.scheduling` → `app.shared.tools` → `healthie.py` (future). Initial exploration in brainstorm `thoughts/shared/brainstorms/2026-03-27-code-structure.md` (note: brainstorm reflects an earlier iteration; this plan is authoritative).
5. **Circular imports between nodes and handlers**: RESOLVED. `nodes.py` imports handlers at module level; `handlers.py` uses late imports (inside function body) for node factories. This breaks the cycle cleanly.
