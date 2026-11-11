# Progress

## Phase 0 — models proven (live, 2026-11-11)
- `scripts/smoke_deepseek.py`: plain chat, `content: null` reproduction + retry, tool call round trip through `SarvamChatModel` in a LangGraph `ToolNode` graph. PASS.
- `scripts/smoke_prism.py`: choice + noul + score in one request, English/Hindi/Hinglish. PASS.
- `scripts/smoke_tts.py`, `scripts/smoke_stt.py`: Bulbul v4 Flash → WAV → Saaras v4 loopback. PASS (exact transcript).
- `brain/models.py` (`SarvamChatModel`, `PrismDecider`, `chat_complete`, backoff), `brain/config.py`, 4 mocked unit tests.
- Python pinned to 3.12; `pytest` and `ruff` pass.

## Findings
- Prism `confidence` is rescaled; Hindi/Hinglish ≈ 0.56 vs English ≈ 0.79 on the same question. See docs/API_NOTES.md.
- Latency: DeepSeek 0.9–1.9 s per call (low effort); Prism 0.35–1.2 s; STT 2.2 s; TTS 3.2 s.

## Not done / open
- `samples/test.wav` is a TTS loopback, not a real mic clip.
- Sarvam dashboard training opt-out: manual step for you.
- `parallel_tool_calls` behaviour, DeepSeek/Prism retention: still open.
- `brain/privacy.py` redaction not built yet (plan: Phase 1).

## Next
Phase 1: read-only tools + plan/act/observe graph + SqliteSaver + cli.py.
