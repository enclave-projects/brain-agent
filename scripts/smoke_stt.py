"""Phase 0 smoke test 3: saaras:v4 transcribes samples/test.wav (30 s REST limit)."""

from __future__ import annotations

import time

from brain.config import ROOT, load_config
from brain.models import make_client, with_backoff


def main() -> None:
    wav = ROOT / "samples" / "test.wav"
    client = make_client()
    t0 = time.perf_counter()
    with wav.open("rb") as f:
        r = with_backoff(
            lambda: client.speech_to_text.transcribe(
                file=f, model=load_config()["models"]["stt"], mode="transcribe"
            )
        )
    print(f"latency {time.perf_counter() - t0:.2f}s")
    print("transcript:", r.transcript)
    print("language:", getattr(r, "language_code", None))
    assert r.transcript.strip()
    print("PASS")


if __name__ == "__main__":
    main()
