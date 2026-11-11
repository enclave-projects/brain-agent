"""Phase 0 smoke test 4: bulbul:v4-flash -> out/test.wav (also makes samples/test.wav if missing)."""

from __future__ import annotations

import base64
import shutil
import time

from brain.config import ROOT, load_config
from brain.models import make_client, with_backoff

TEXT = "Hello, this is a test of the brain agent. Please clean up my downloads folder."


def main() -> None:
    cfg = load_config()["models"]
    client = make_client()
    t0 = time.perf_counter()
    r = with_backoff(
        lambda: client.text_to_speech.convert(text=TEXT, language_code="en-IN", model=cfg["tts"])
    )
    dt = time.perf_counter() - t0
    out = ROOT / "out" / "test.wav"
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(base64.b64decode(r.audios[0]))
    print(f"wrote {out} ({out.stat().st_size} bytes) in {dt:.2f}s, chars={len(TEXT)}")
    sample = ROOT / "samples" / "test.wav"
    if not sample.exists():
        shutil.copy(out, sample)
        print(
            "samples/test.wav was missing: seeded from TTS output (loopback test, weaker than a real mic clip)"
        )
    assert out.stat().st_size > 1000
    print("PASS")


if __name__ == "__main__":
    main()
