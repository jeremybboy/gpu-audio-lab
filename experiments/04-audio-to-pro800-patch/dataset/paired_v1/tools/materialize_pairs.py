"""Copy bank .syx into pair folders, write meta.json, placeholder render.wav. Run from repo or experiment root."""
from __future__ import annotations

import csv
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]  # paired_v1/
EXP = Path(__file__).resolve().parents[3]  # 04-audio-to-pro800-patch/
BANK = EXP / "starsky_bank"
MANIFEST = ROOT / "manifest.csv"


def main() -> None:
    if not MANIFEST.is_file():
        raise SystemExit(f"Missing {MANIFEST}")
    rows = list(csv.DictReader(MANIFEST.read_text(encoding="utf-8").splitlines()))
    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        pid = row["pair_id"].strip()
        stem = row["bank_stem"].strip()
        pdir = ROOT / pid
        pdir.mkdir(parents=True, exist_ok=True)
        src = BANK / stem
        if not src.is_file():
            raise SystemExit(f"Missing bank file: {src}")
        shutil.copy2(src, pdir / "source.syx")
        meta = {
            "pair_id": pid,
            "bank_stem": stem,
            "created_utc": now,
            "protocol_version": "paired_v1",
            "midi_channel_1_based": 1,
            "midi_note": int(row["note"]),
            "velocity": int(row["velocity"]),
            "sample_rate_hz": int(row["sample_rate"]),
            "load_method": "synthtribe_or_send_syx",
            "gain_notes": row.get("gain_notes", ""),
            "firmware": row.get("firmware", "TBD"),
            "render_placeholder": True,
            "notes": "Overwrite render.wav with DAW capture; set load_method and gain_notes; set firmware.",
        }
        (pdir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        sr = int(row["sample_rate"])
        secs = 2.5
        n = int(sr * secs)
        silence = np.zeros(n, dtype=np.float32)
        wav_path = pdir / "render.wav"
        sf.write(str(wav_path), silence, sr, subtype="PCM_24")
        print(pid, "->", pdir)


if __name__ == "__main__":
    main()
