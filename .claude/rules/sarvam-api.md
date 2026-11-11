---
paths:
  - "brain/models.py"
  - "brain/nodes/**"
  - "voice/**"
  - "scripts/**"
---

# Sarvam API rules

- **Read `docs/API_NOTES.md` first.** If a fact isn't there, fetch https://docs.sarvam.ai/api/llms.txt or the model page. Never invent parameters.
- All Sarvam calls go through `brain/models.py` (`SarvamChatModel`, `PrismDecider`) or `voice/`. No direct HTTP calls elsewhere.
- Model IDs come from `config/agent.yaml`:
  - `models.planner`: `deepseekv4.1-flash-1017`
  - `models.planner_fast`: `deepseekv4.1-flash-1017-interactive`
  - `models.decider`: `sarvam-prism`
  - `models.stt`: `saaras:v4`
  - `models.tts`: `bulbul:v4-flash`

## DeepSeek calls

- Always pass `max_tokens` and `reasoning_effort` explicitly. Default `low`; `high` only for re-planning.
- If `content is None` and `finish_reason == "length"`, retry once with `max_tokens * 2` or lower effort, then raise `ReasoningBudgetExceeded`.
- Keep `reasoning_content` in traces only. Never put it in user-facing output or long-term memory.
- Expect one tool call per turn (`parallel_tool_calls` is false).

## Prism calls

- One request per decision point, with all questions batched (the state is billed once).
- Return a typed `Decision(option: str, confidence: float, probs: dict[str, float])`.
- Below `thresholds.route_confidence`, return `None` so the caller defers to the planner.
- Keep the state small: goal, last observation and tool descriptions. Don't send the full message history.

## Reliability

- Retry 429/503 with exponential backoff and jitter (max 3). Don't retry 400/402/403/404.
- Log every call: model, latency, input/output tokens, ₹ cost estimate, decision confidence.
- Send all outbound text through `brain/privacy.py.redact()` first.

## Testing

- Unit tests mock the SDK client. Live API tests live in `scripts/smoke_*.py` and are never run in CI.
