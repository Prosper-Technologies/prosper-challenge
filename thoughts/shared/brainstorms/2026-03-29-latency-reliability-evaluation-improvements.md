---
date: 2026-03-29T00:00:00+00:00
author: spagnoloe
topic: "Latency, Reliability & Evaluation Improvements for Voice Agent"
tags: [brainstorm, latency, reliability, evaluation, voice-agent, pipecat]
status: parked
exploration_type: workflow  # confirmed by user
last_updated: 2026-03-29
last_updated_by: spagnoloe
---

# Latency, Reliability & Evaluation Improvements — Brainstorm

## Context

This brainstorm explores potential improvements to the Prosper Challenge voice agent — an AI-powered healthcare appointment scheduling bot built with Pipecat, pipecat-flows, OpenAI LLM, ElevenLabs STT/TTS, and Daily.co WebRTC transport.

The current implementation is functional with:
- **Latency**: Healthie GraphQL API (~200ms) chosen over Playwright browser automation (8-10s). Async pipeline: WebRTC → STT → LLM → TTS → WebRTC.
- **Reliability**: Basic error handling at API/tool/flow levels. 30s HTTP timeout. No retry logic. Failures surface to user with retry prompts.
- **Evaluation**: Unit tests with mocks for API tools. Pre-commit hooks (ruff, mypy). GitHub Actions CI. No conversation-level evaluation, no latency monitoring, no automated end-to-end voice testing.

Three areas of improvement are being explored:
1. **Latency** — balancing speed with user experience and accuracy
2. **Reliability** — ensuring the agent is always available regardless of external factors (e.g. AI provider unavailable)
3. **Evaluation** — making it easy to check the agent behaves as expected

## Exploration

### Q: What kind of exploration is this?
Workflow to improve — the current system works but we want to make it better across latency, reliability, and evaluation.

**Insights:** This is about production-readiness, not fixing broken things.

### Q: Which area feels most urgent?
All roughly equal — no single area dominates. This is about overall production readiness across all three dimensions.

**Insights:** Since no area is critically broken, we can approach this holistically. The improvements should compound — e.g., better evaluation helps us measure latency and reliability improvements.

### Q: Is this heading toward real production or demo/proof-of-concept?
Production with real users — will handle actual patient calls, needs to be robust, monitored, and auditable.

**Insights:** This is a high-stakes environment. Healthcare scheduling with real patients means: (1) latency affects trust and call completion rates, (2) reliability failures mean missed appointments, (3) evaluation must cover correctness (right patient, right time slot) not just "it works." Compliance and auditability may also matter.

### Q: Where in the pipeline do you feel the most noticeable delay?
Haven't measured yet — don't have good visibility into where the bottleneck is.

**Insights:** This is actually a key finding: before optimizing latency, we need observability. Instrumenting the pipeline to measure per-stage latency (STT time, LLM time-to-first-token, tool execution time, TTS time) should be a prerequisite. You can't improve what you can't measure. This ties directly into the evaluation theme too — latency metrics are a form of evaluation.

### Q: On reliability — multi-provider failover or graceful degradation?
Multi-provider failover — if OpenAI is down, automatically switch to another LLM (e.g., Anthropic, Google).

**Insights:** This is ambitious but achievable. Key considerations: (1) Pipecat already supports multiple LLM services — switching the service object is feasible. (2) The challenge is prompt/tool-calling compatibility across providers — OpenAI function calling syntax differs from Anthropic's tool_use. (3) pipecat-flows node definitions use OpenAI-style function schemas — would need abstraction or adapter. (4) STT/TTS failover is also worth considering (ElevenLabs → Deepgram, etc.). (5) Need health-check or circuit-breaker pattern to detect when to fail over.

### Q: Failover between calls only, or mid-conversation too?
Mid-conversation too — even during an active call, detect failure and hot-swap the LLM provider seamlessly.

**Insights:** This is the hardest version of this problem. Challenges: (1) Conversation context (message history) must be portable across providers. (2) pipecat-flows state machine is LLM-agnostic in theory (state is in FlowManager), but function schemas are OpenAI-format. (3) Hot-swapping means replacing the LLM service in the pipeline mid-stream — Pipecat pipelines are processor chains, so this needs a proxy/wrapper service that delegates to the active provider. (4) We'd need to detect failure fast (timeout? error code?) and retry the same turn with the backup. (5) The user shouldn't notice — maybe a brief pause but no lost context.

### Q: What does 'behaving as expected' mean for evaluation?
All of the above — need visibility into every layer: tool correctness, conversation quality, and end-to-end success rate.

**Insights:** This maps to a three-tier evaluation strategy: (1) **Unit level** — already partly covered with mock tests for tools, but could add contract tests against Healthie staging. (2) **Conversation level** — need test scenarios (transcripts) evaluated for quality: did the bot follow the flow, handle ambiguity, recover from errors? LLM-as-judge or rubric-based scoring. (3) **Outcome level** — did the call result in a correctly booked appointment? This is measurable by checking Healthie state after a test call. Each tier needs different tooling.

### Q: How would you generate test scenarios for conversation-level evaluation?
LLM-simulated callers — use an LLM to play the patient role with various personas and edge cases. More coverage, less predictable.

**Insights:** This is powerful but needs careful design: (1) The simulator LLM needs persona definitions (confused caller, impatient caller, caller who gives wrong DOB first, caller who changes their mind on appointment time). (2) Can run text-only (bypass STT/TTS) for fast iteration, or voice-to-voice for full E2E. (3) Need a scoring rubric — what makes a "good" conversation? Metrics: task completion, turn count, error recovery, information accuracy. (4) Pipecat has a testing framework possibility — could inject synthetic audio or text directly into the pipeline. (5) This approach pairs well with CI: run 50 simulated calls after each deploy, flag regressions.

### Q: What's your biggest worry about tackling all three together?
Not concerned — wants concrete ideas to improve in these areas and will judge them. Not looking for risk analysis, looking for an ideas menu.

### Q: Open to switching primary LLM? Healthie reliability a concern too?
Open to all — happy to switch primary LLM if better, and Healthie API reliability is also a concern (not just AI services).

**Insights:** The full reliability surface is: LLM (OpenAI/alternatives), STT (ElevenLabs), TTS (ElevenLabs), Healthie API, and Daily.co WebRTC transport. Each needs a failover or graceful-degradation strategy. For Healthie specifically, the Playwright browser automation already exists as a potential fallback (slower but functional).

### Q: Give me the full menu or prioritize?
Full menu — wants to see all ideas from quick wins to ambitious. Will pick what to do.

## Synthesis

### Ideas Menu

#### Latency

| # | Idea | Description | Effort |
|---|------|-------------|--------|
| L1 | **Pipeline instrumentation** | Add per-stage timing (STT, LLM TTFT, tool execution, TTS) with structured logging. Prerequisite for all other latency work — you can't optimize what you can't measure. | Low |
| L2 | **LLM provider benchmarking** | Test alternatives (Claude, Gemini, Groq, Together AI) on your actual prompts. Measure time-to-first-token and total latency. Groq and Together AI with open models can be significantly faster for simple function-calling tasks. | Medium |
| L3 | **Streaming TTS with LLM output** | Ensure LLM tokens stream directly into TTS as they arrive (sentence-level chunking), minimizing the gap between LLM finishing and speech starting. Pipecat supports this but verify it's optimally configured. | Low |
| L4 | **Prefetch/precompute appointment slots** | When the patient is found, proactively fetch available appointment slots before the user asks. Cache them so the appointment creation step is faster. | Medium |
| L5 | **Smaller/faster model for simple nodes** | Use a faster/cheaper model for straightforward nodes (greeting, confirmation) and a more capable model for complex ones (patient lookup, appointment scheduling). Pipecat supports swapping services per node. | Medium |
| L6 | **Edge-deployed STT/TTS** | If latency is dominated by STT/TTS round-trips, consider Deepgram (known for low latency STT) or local Whisper for STT. Trade-off: accuracy vs speed. | High |
| L7 | **Filler speech during tool execution** | While waiting for Healthie API or LLM tool calls, play natural filler ("Let me look that up for you...") to mask perceived latency. This is a UX improvement, not a technical speed improvement. | Low |

#### Reliability

| # | Idea | Description | Effort |
|---|------|-------------|--------|
| R1 | **LLM provider failover (between calls)** | At call start, health-check the primary LLM. If unhealthy, route to backup. Simpler than mid-call failover. Pipecat supports multiple LLM services — create both at startup, select based on health. | Medium |
| R2 | **LLM provider failover (mid-conversation)** | Wrap LLM service in a proxy that detects errors/timeouts and retries with a backup provider. Must translate message history and function schemas between formats. Circuit-breaker pattern with fast failure detection. | High |
| R3 | **STT/TTS failover** | Configure backup STT (Deepgram) and TTS (Google Cloud TTS, AWS Polly) services. Switch if ElevenLabs errors or latency exceeds threshold. | Medium |
| R4 | **Healthie API retry with exponential backoff** | Add retry logic (e.g., tenacity library) for transient Healthie API failures. 3 retries with exponential backoff before surfacing error. | Low |
| R5 | **Healthie API → Playwright fallback** | If Healthie GraphQL API is down, fall back to Playwright browser automation (already implemented). Slower but functional. Detect via consecutive API errors. | Medium |
| R6 | **Circuit breaker pattern** | Implement circuit breakers for each external service (LLM, STT, TTS, Healthie). Track error rates, open circuit after threshold, attempt half-open periodically. Libraries: `pybreaker` or custom. | Medium |
| R7 | **Graceful degradation with human handoff** | When all automated options are exhausted, transfer to a human operator or take a voicemail. "I'm having trouble with our system right now. Let me connect you with a team member." | Medium |
| R8 | **Health check endpoint** | Expose a `/health` endpoint that checks all dependencies (LLM reachability, Healthie API, STT/TTS). Use for monitoring, alerting, and load balancer health checks. | Low |

#### Evaluation

| # | Idea | Description | Effort |
|---|------|-------------|--------|
| E1 | **Conversation logging & replay** | Log full conversation transcripts (user utterances, bot responses, tool calls, state transitions) in structured format. Foundation for all other evaluation. | Low |
| E2 | **LLM-simulated caller framework** | Build a test harness where an LLM plays the patient with configurable personas (confused, impatient, wrong DOB, accent variations). Run text-only against the flow logic for fast iteration. | High |
| E3 | **LLM-as-judge scoring** | After each test conversation, have a separate LLM evaluate the transcript against a rubric: task completion, naturalness, error recovery, information accuracy, turn efficiency. | Medium |
| E4 | **Contract tests against Healthie staging** | Integration tests that hit real Healthie staging API — verify patient lookup returns expected data, appointment creation works. Run in CI on a schedule (not every commit, to avoid flakiness). | Medium |
| E5 | **End-to-end outcome verification** | After a simulated call, check Healthie to confirm the appointment was actually created with correct details (right patient, right time, right provider). The ultimate correctness check. | Medium |
| E6 | **Latency regression alerts** | Track P50/P95/P99 per-stage latency over time. Alert if any stage degrades beyond baseline thresholds. Requires L1 (instrumentation) first. | Medium |
| E7 | **A/B testing framework** | Run two configurations side-by-side (different LLM, different prompts, different flow) and compare metrics. Useful for validating improvements. | High |
| E8 | **Conversation flow coverage tracking** | Track which conversation paths (nodes in pipecat-flows) are exercised by tests. Identify untested paths — e.g., error recovery from patient-not-found, appointment conflict handling. | Medium |
| E9 | **CI-integrated eval suite** | Run N simulated conversations on every deploy/PR. Report pass/fail rate, average task completion, latency metrics. Gate deployments on eval results. | High |

### Key Decisions
- This is a production system — all improvements should be production-grade
- Multi-provider failover is desired, including mid-conversation hot-swap
- LLM-simulated callers are the preferred approach for evaluation test generation
- Open to switching primary LLM provider if benchmarks justify it
- Full reliability surface includes LLM, STT, TTS, Healthie API, and transport

### Open Questions
- What's the actual latency breakdown today? (Requires L1 instrumentation first)
- How compatible are pipecat-flows function schemas across LLM providers? (Needs research)
- Can Pipecat's pipeline support hot-swapping a processor mid-stream? (Needs research)
- What Healthie API SLA/uptime can be expected in production vs staging?
- What's the acceptable latency budget per stage? (Need to define after measuring)
- Should conversation logs be stored for compliance/audit purposes?

### Constraints Identified
- pipecat-flows uses OpenAI-style function schemas — multi-provider support needs an abstraction layer
- Mid-conversation failover requires portable conversation context across providers
- Healthcare domain means correctness is non-negotiable — evaluation must cover data accuracy
- Healthie staging environment may not reflect production behavior/reliability
- LLM-simulated callers need careful persona design to be realistic

### Core Requirements
- **Observability first**: Instrument before optimizing (L1, E1, E6)
- **Failover at every external boundary**: LLM, STT, TTS, Healthie (R1-R6)
- **Three-tier evaluation**: Unit (E4), conversation (E2, E3), outcome (E5)
- **Automated regression detection**: CI-integrated eval that catches degradation (E9)
- **Production UX**: Mask latency with filler speech (L7), graceful degradation (R7)

## Next Steps

- **Parked** — ideas menu is ready for review. When ready to proceed:
  - `/research` to deep-dive on specific ideas (e.g., Pipecat multi-provider support, LLM latency benchmarks)
  - `/create-plan` to pick ideas and build an implementation plan
- **Suggested starting point**: L1 (pipeline instrumentation) + E1 (conversation logging) — they're low effort and unlock everything else
