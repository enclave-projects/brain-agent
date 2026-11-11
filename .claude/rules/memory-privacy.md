---
paths:
  - "brain/memory/**"
  - "brain/privacy.py"
---

# Memory and privacy rules

## Memory (fast and slow, like hippocampus and neocortex)

- **Episode log** (`episodes.sqlite`): append-only. One row per step: goal, action, args, result, check outcome, source and timestamp. Never update or delete rows from agent code.
- **Long-term store** (LangGraph Store): facts, preferences and skills. Only `consolidate.py` proposes writes, and they go to a review queue. You approve them via `cli.py memory review`.
- **Retrieval score** = recency decay + importance + relevance (Generative Agents). Top-k only, within a token budget for the `retrieved` slot.
- **Untrusted content** (web, files, screen) can't become a memory without your approval, and it keeps its source tag.
- The nightly job runs from Windows Task Scheduler. It summarises, scores importance, decays stale items and proposes skills.

## Privacy

- `privacy.redact(text)` (Presidio + custom recognisers for Indian phone numbers, Aadhaar-like and PAN-like patterns) runs on **all** outbound text: DeepSeek, Prism, Saaras transcripts sent onward, and traces.
- Local data (episodes, Store, checkpoints, screenshots) lives in `%LOCALAPPDATA%\brain-agent\` with a retention limit in config.
- Never log API keys or unredacted user files.
- Langfuse, if used, runs self-hosted in Docker. Traces are redacted before export.
