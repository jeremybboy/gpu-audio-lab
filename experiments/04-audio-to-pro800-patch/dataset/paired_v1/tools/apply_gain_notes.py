"""Set gain_notes on every pair_XX/meta.json (Item A capture chain)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GAIN_NOTES = (
    "Signal chain: Behringer PRO-800 → Mackie 1402 VLZ → Steinberg UR22 (USB) → "
    "Windows → Audacity. Recorded mono 48 kHz. Gain staged nominally ~0 dB "
    "(no intentional boost); trim as set on mixer/interface for clean level without clipping."
)


def main() -> int:
    for d in sorted(ROOT.glob("pair_*")):
        p = d / "meta.json"
        if not p.is_file():
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        m["gain_notes"] = GAIN_NOTES
        p.write_text(json.dumps(m, indent=2), encoding="utf-8")
        print("updated", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
