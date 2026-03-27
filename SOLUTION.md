# Solution: Decision Log

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

**Tradeoff**: Plain function calling exposes all tools at every step, relying on the system prompt to enforce ordering. The LLM can skip steps or call functions in the wrong order, and adding steps means rewriting the prompt. pipecat-flows gives structural guarantees: each node scopes which tools are visible, so ordering bugs are impossible. The cost is an extra dependency and a small learning curve -- worth it because prompt engineering can't guarantee correctness.

---

## 3. Code structure: `app/scheduling/` + `app/shared/tools/` vs single `prompts/scheduling.py`

**Decision**: Feature-first layout under `app/` with two concerns separated:
- `app/scheduling/` -- the conversation flow (prompts.py, nodes.py, handlers.py)
- `app/shared/tools/` -- backend-agnostic tool functions (find_patient.py, create_appointment.py)

**Alternatives considered**:
- **`prompts/scheduling.py`** (single file) -- everything in one place. Simple, but the name is misleading (it's not just prompts) and mixes graph structure, business logic, and system messages.
- **`flows/scheduling/` + `tools/scheduling/`** (top-level folders per concern) -- clean separation, but tools nested under `scheduling/` implies they're scheduling-specific.

**Tradeoff**: The `app/` layout groups by feature while keeping tools shared. `app/scheduling/` is the flow; `app/shared/tools/` is reusable by future flows (intake, etc.). Slightly deeper nesting, but each folder has a clear reason to exist and the dependency direction is one-way: `app.scheduling -> app.shared.tools`.

---

## 4. Three-file split inside `app/scheduling/` vs single file

**Decision**: Split into prompts.py, nodes.py, handlers.py.

**Alternative**: Keep everything in one file (~150 lines).

**Tradeoff**: Three files separate what the bot says (prompts), what the conversation looks like (nodes), and what happens when tools are called (handlers). Prompts can be edited by non-engineers without touching logic. The cost is managing a circular import between nodes and handlers (solved with late imports in handlers). At ~150 lines a single file would be fine, but the separation pays off as soon as prompts need tuning independently.

---

## 5. Tools decoupled from Healthie vs direct Healthie imports in handlers

**Decision**: Tool functions in `app/shared/tools/` with dummy implementations. Handlers import tools, not Healthie directly.

**Alternative**: Handlers call `healthie.find_patient()` / `healthie.create_appointment()` directly.

**Tradeoff**: Direct Healthie coupling means swapping to another EHR requires changing the flow layer. With tools as an abstraction boundary, the backend is an implementation detail -- swap Healthie for another service by changing the tool files, not the conversation flow. The dummy implementations also enable end-to-end testing of the full flow without a running Healthie instance.
