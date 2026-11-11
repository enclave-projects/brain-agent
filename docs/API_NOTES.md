# API Notes — verified facts only

Checked against official Sarvam docs on **2026-11-11**. When you confirm or correct something, edit this file and give the source and date. Items marked **[verify]** weren't confirmed.

Docs index for agents: https://docs.sarvam.ai/api/llms.txt

---

## Auth (all models)

- One key: `SARVAM_API_KEY` in `.env`.
- Header: `api-subscription-key: <key>`. Prism also accepts a Bearer token.
- SDK: `sarvamai` (Python). **Prism needs `sarvamai >= 0.1.43`.**
- An invalid key returns **403** (not 401).

---

## DeepSeek V4.1 Flash 1017 — planner/reasoner

Source: https://docs.sarvam.ai/api/token-factory/models/deepseek-v4.1-flash-1017

| Item | Value |
|---|---|
| Model IDs | `deepseekv4.1-flash-1017` (~80 tok/s), `deepseekv4.1-flash-1017-interactive` (>200 tok/s) |
| Endpoints | `POST /v2/chat/completions`, `POST /v2/responses` |
| Context | 1,048,576 tokens total (prompt + reasoning + output) |
| Input | text, images as **base64 data URIs only** (URL → 400). No audio or video (400). |
| Tools | OpenAI-style `tools`, `tool_choice` (`"required"` OK). Named `tool_choice` without `tools` → 400. `parallel_tool_calls` listed as `false` **[verify]** |
| Reasoning | `reasoning_effort`: `"none"`, `"low"`, `"high"` (**default**), `"max"`. Must be a string. Reasoning text comes back in `reasoning_content`. |
| Price / 1M tokens | base: ₹14 in, ₹0.25 cached, ₹55 out. interactive: ₹25 / ₹0.5 / ₹105. Reasoning is billed as output. |
| Body limit | 32 MiB (413) |
| `n` > 1 | 400 |

```python
from sarvamai import SarvamAI
client = SarvamAI(api_subscription_key=KEY)
r = client.chat.completions_v2(
    model="deepseekv4.1-flash-1017",
    messages=[{"role": "user", "content": "..."}],
    max_tokens=4000,
    reasoning_effort="low",
)
text = r.choices[0].message.content
```

### Pitfalls

- **Reasoning uses up `max_tokens`.** When that happens you get HTTP **200** with `content: null` and `finish_reason: "length"`.
  - Always set `max_tokens`.
  - Treat `content is None` as retryable: retry once with a larger `max_tokens` or lower effort.
- Default effort is `high`, which is slow and costly. Use `low` for routine steps and `high` only for re-planning after a mismatch.
- Disable thinking with `reasoning_effort="none"`. The alternatives are `thinking={"type":"disabled"}` or `chat_template_kwargs={"enable_thinking": False}` via `extra_body`.
- **LangChain:** `ChatSarvam` (`langchain-sarvam`) officially lists only `sarvam-105b` and defaults to the `/v1` base URL. We use our own `SarvamChatModel` wrapper over `completions_v2`. See `docs/DECISIONS.md`.

### Errors

| Code | Meaning | Action |
|---|---|---|
| 400 | bad params | fix, don't retry |
| 402 | out of credits | stop, tell the user |
| 403 | bad key | stop |
| 404 | unknown model | check `agent.yaml` |
| 413 | body too big | shrink the context or images |
| 429 | rate limited | exponential backoff |
| 503 | overloaded | backoff, then retry |

---

## Sarvam Prism — decision model

Source: https://docs.sarvam.ai/api/token-factory/models/sarvam-prism

| Item | Value |
|---|---|
| Model ID | `sarvam-prism` |
| Endpoint | `POST /v2/systemone` (synchronous JSON, no streaming) |
| SDK | `client.decisions.create(model="sarvam-prism", state=..., questions={...})` |
| Question types | `noul` (yes/no → P(yes)), `choice` (top option, `confidence`, probs), `score` (expected level, `confidence`, `legend`, probs) |
| Limits | 32,768 tokens per question (state + question + options). State is never truncated. `choice` 2–255 options, `score` 2–10 levels, unlimited questions. |
| Input | text or JSON only. No `temperature` or `max_tokens`. |
| Output tokens | always 0 |
| Price | ₹4 per 1M input tokens, output free. State is counted once per request. |
| Languages | English, 10 Indian languages, Hinglish. **Confidence is lower in Indian languages.** |
| Timeout | must finish within 60 s, else `503 model_overloaded` |
| Privacy | not documented on the model page **[verify]** |

### Pitfalls

- Answers always have a valid shape but can still be wrong. Gate on `confidence` (start at 0.7 and tune in Phase 4).
- Ask several questions in **one request**, since the state is billed once.
- Prism never overrides `permissions.yaml`. It can only make a decision stricter.
- Exact request JSON shape for `questions` (keys, option format): copy it from the docs page before coding **[verify]**.

---

## Saaras v4 — speech to text (Phase 7)

Source: https://docs.sarvam.ai/api/getting-started/models/saaras/llms.txt

- Model: `saaras:v4` (the default; v3 is still available).
- Modes: `transcribe` (default), `translate` (to English), `verbatim`, `translit`, `codemix` (Hinglish → English words in Latin script, Indic words in native script).
- 23 languages with auto-detect.
- REST: **30 s max per request**. Batch: up to 2 h. WebSocket streaming exists.
- Raw PCM needs `input_audio_codec` and 16 kHz audio.
- Keyterm prompting: up to 50 terms, v4 only, REST/Batch only (not streaming).
- Pricing and rate limits: see the pricing page **[verify]**.

## Bulbul v4 Flash — text to speech (Phase 7)

Source: https://www.sarvam.ai/blogs/bulbul-v4-flash/

- Model: `bulbul:v4-flash`.
- REST, HTTP streaming and WebSocket options exist. Which apply to v4 Flash, plus voices, languages and parameters, aren't confirmed here **[verify]**. Read the "Best Practice Guide for Bulbul v4 Flash" in the Sarvam docs before Phase 7.

---

## LangGraph facts we rely on

- Checkpointer per `thread_id`. For local use: `SqliteSaver` (package `langgraph-checkpoint-sqlite` **[verify]**).
- `interrupt()` needs a checkpointer. Resume with `Command(resume=...)`.
- **On resume, the interrupted node restarts from the beginning**, so code before `interrupt()` must be idempotent.
- The Store holds long-term memory across threads.

## Privacy status

- Sarvam's privacy policy: API content is used for training **unless you opt out** (do it in the dashboard), kept 30 days after last access by default, logs kept 1 year, may be processed in the US/EU.
- DeepSeek and Prism model pages don't mention retention. Ask Sarvam support **[verify]**.
- Our rule: redact everything with `brain/privacy.py` before it leaves the PC.
