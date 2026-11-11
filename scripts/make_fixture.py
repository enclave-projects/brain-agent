"""Reset sandbox/Downloads with a known set of files (stand-in for the real Downloads until Phase 4)."""

from __future__ import annotations

import shutil

from brain.config import ROOT

FILES = {
    "installer.exe": 3_000_000,
    "movie.mp4": 12_000_000,
    "report.pdf": 450_000,
    "photos/a.jpg": 800_000,
    "photos/b.jpg": 1_200_000,
    "notes.txt": 2_000,
    "archive.zip": 5_500_000,
}


def main() -> None:
    d = ROOT / "sandbox" / "Downloads"
    shutil.rmtree(d, ignore_errors=True)  # test fixture reset, not an agent tool
    for name, size in FILES.items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\0" * size) if name != "notes.txt" else p.write_text("Buy milk.\n" * 200)
    print(f"fixture ready at {d}")


if __name__ == "__main__":
    main()
