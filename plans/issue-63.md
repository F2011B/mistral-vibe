# Plan for Issue #63: Feature Request: Implement OpenTelemetry-based Observability

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/63

## Description
Inspired by the [obeservability implementation](https://geminicli.com/docs/cli/telemetry/) in Gemini CLI, mistral-vibe would provide standardized tracing, metrics, and logging capabilities.

## Proposed Implementation

### 1. Metrics System
- **Core metrics**:
  - Tool call count and latency
  - API request count and latency
  - Token usage metrics
- **GenAI Semantic Conventions**:
  - Implement `gen_ai.client.token.usage`
  - Implement `gen_ai.client.operation.duration`
  - Support standard GenAI attributes

### 2. Tracing System
- Implement `run_in_trace_span` utility function
- Add tracing to key operations:
  - Agent interactions
  - Tool executions
  - API calls
  - File operations

The detailed trace might look like below

<img width="1278" height="474" alt="Image" src="https://github.com/user-attachments/assets/34a8a000-e423-45f7-82c6-18e252a53978" />

### The corresponding iteration

<img width="1109" height="306" alt="Image" src="https://github.com/user-attachments/assets/600cc488-f29b-4444-8427-c7361bc9621c" />


### Trace waterfall overview of an iteration:

<img width="1726" height="413" alt="Image" src="https://github.com/user-attachments/assets/d8680f4f-c64d-4096-ae3d-fca847c8cfaf" />


### Agent 
<img width="1728" height="635" alt="Image" src="https://github.com/user-attachments/assets/de93935f-d2d2-4755-a9be-b73c0d26078a" />


### Tool use
<img width="1728" height="526" alt="Image" src="https://github.com/user-attachments/assets/c4ed862c-bfc4-4fad-a8f3-dfbf0df10fd3" />



I am willing to implement this feature :)

## Plan
1. Read the issue description and comments; extract requested outcome and acceptance criteria.
2. Reproduce the problem or desired workflow; document observed vs. expected behavior.
3. Isolate the root cause (logs, stack traces, configs, related modules). Capture hypotheses and confirm with a minimal repro.
4. Design the fix/change: scope, API/CLI/UX impact, backward compatibility, and risk mitigations.
5. Implement the change with small, reviewable commits; prefer simple, typed code and guardrails.
6. Add/update automated tests to cover the repro and edge cases; ensure existing suites still pass.
7. Update docs/examples/changelog if user-facing behavior changes; note migration steps if needed.
8. Validate locally (and in CI if available) against the repro steps; post results and open questions in the issue before closing.
