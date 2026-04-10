"""Set performance notes on every pair_XX/meta.json (capture contract)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NOTES = (
    "Held ~1 s on C4, natural release. "
    "(Merged from staging; trim applied.)"
)


def main() -> int:
    for d in sorted(ROOT.glob("pair_*")):
        p = d / "meta.json"
        if not p.is_file():
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        m["notes"] = NOTES
        p.write_text(json.dumps(m, indent=2), encoding="utf-8")
        print("updated", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
