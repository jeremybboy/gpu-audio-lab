"""Copy matched .wav + .syx from paired_v1/New folder into pair_01..pair_N, update manifest + meta."""
from __future__ import annotations

import csv
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "New folder"


def main() -> int:
    if not STAGING.is_dir():
        print(f"No staging folder: {STAGING}", file=sys.stderr)
        return 1
    pairs: list[tuple[str, Path, Path]] = []
    for wav in sorted(STAGING.glob("*.wav"), key=lambda p: p.stem.lower()):
        syx = STAGING / f"{wav.stem}.syx"
        if syx.is_file():
            pairs.append((wav.stem, wav, syx))
    if len(pairs) != 10:
        print(f"Expected 10 wav+syx pairs in New folder, found {len(pairs)}.", file=sys.stderr)
        return 1

    pairs.sort(key=lambda x: x[0].lower())
    now = datetime.now(timezone.utc).isoformat()
    manifest_rows: list[dict[str, str]] = []

    for i, (stem, wav, syx) in enumerate(pairs, start=1):
        pid = f"pair_{i:02d}"
        bank = f"{stem}.syx"
        d = ROOT / pid
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(syx, d / "source.syx")
        shutil.copy2(wav, d / "render.wav")
        meta = {
            "pair_id": pid,
            "bank_stem": bank,
            "created_utc": now,
            "protocol_version": "paired_v1",
            "midi_channel_1_based": 1,
            "midi_note": 60,
            "velocity": 100,
            "sample_rate_hz": 48000,
            "load_method": "synthtribe_or_send_syx",
            "gain_notes": "REPLACE after calibration",
            "firmware": "TBD",
            "render_placeholder": False,
            "notes": "Merged from New folder; run trim_renders.py then set gain_notes/firmware.",
            "staging_stem": stem,
        }
        (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        manifest_rows.append(
            {
                "pair_id": pid,
                "bank_stem": bank,
                "wav_path": f"{pid}/render.wav",
                "syx_path": f"{pid}/source.syx",
                "sample_rate": "48000",
                "note": "60",
                "velocity": "100",
                "gain_notes": "REPLACE after calibration",
                "firmware": "TBD",
            }
        )
        print(pid, "<-", stem)

    man_path = ROOT / "manifest.csv"
    with man_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "pair_id",
                "bank_stem",
                "wav_path",
                "syx_path",
                "sample_rate",
                "note",
                "velocity",
                "gain_notes",
                "firmware",
            ],
        )
        w.writeheader()
        w.writerows(manifest_rows)
    print(f"Wrote {man_path} ({len(manifest_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
