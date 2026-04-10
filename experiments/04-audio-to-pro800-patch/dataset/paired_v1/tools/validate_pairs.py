"""Sanity-check paired_v1: syx parses, wav readable, optional peak / silence warning."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]  # paired_v1/


def main() -> int:
    sys.path.insert(0, str(ROOT.parents[1]))  # 04-audio-to-pro800-patch/
    from devices.pro800.sysex_tools import parse_pro800_dump

    errors: list[str] = []
    warns: list[str] = []
    for i in range(1, 11):
        pid = f"pair_{i:02d}"
        d = ROOT / pid
        syx = d / "source.syx"
        wav = d / "render.wav"
        meta = d / "meta.json"
        pj = d / "patch.json"
        for f, label in [(syx, "source.syx"), (wav, "render.wav"), (meta, "meta.json")]:
            if not f.is_file():
                errors.append(f"{pid}: missing {label}")
        if pj.is_file():
            try:
                json.loads(pj.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"{pid}: patch.json invalid: {e}")
        if syx.is_file() and not parse_pro800_dump(syx):
            errors.append(f"{pid}: source.syx has no parseable PRO-800 packet")
        if wav.is_file():
            data, sr = sf.read(str(wav), always_2d=False)
            if np.ndim(data) > 1:
                data = data.mean(axis=1)
            peak = float(np.max(np.abs(data)))
            if peak < 1e-6:
                warns.append(f"{pid}: render.wav near-silence (placeholder?) peak={peak}")
            if peak > 1.0:
                warns.append(f"{pid}: render.wav peak>1.0 (check float clip): peak={peak}")
    for w in warns:
        print("WARN:", w)
    for e in errors:
        print("ERR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
