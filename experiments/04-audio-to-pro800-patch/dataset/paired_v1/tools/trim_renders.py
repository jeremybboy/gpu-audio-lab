"""Trim leading silence from pair_XX/render.wav using librosa onset detection."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]  # paired_v1/


def _mono_for_detect(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return data.astype(np.float64)
    return data.mean(axis=1).astype(np.float64)


def first_onset_sample(mono: np.ndarray, sr: int, hop_length: int = 512) -> int:
    y = mono.astype(np.float64)
    peak = np.max(np.abs(y)) + 1e-12
    y_n = y / peak
    onsets = librosa.onset.onset_detect(
        y=y_n,
        sr=sr,
        hop_length=hop_length,
        backtrack=True,
        units="samples",
        wait=1,
        delta=0.07,
    )
    if len(onsets) > 0:
        return int(max(0, onsets[0]))
    # RMS fallback: first frame above noise floor
    win = max(int(0.01 * sr), 1)
    hop = win
    rms: list[float] = []
    idx = []
    for i in range(0, len(y) - win, hop):
        rms.append(float(np.sqrt(np.mean(y[i : i + win] ** 2))))
        idx.append(i)
    if not rms:
        return 0
    noise = float(np.median(rms[: min(20, len(rms))]))
    thresh = max(noise * 10.0, 0.005 * peak)
    for i, v in zip(idx, rms):
        if v > thresh:
            return int(i)
    return 0


def trim_one(
    wav_path: Path,
    *,
    pre_roll_ms: float,
    backup: bool,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Returns (old_samples, trim_start_sample, new_samples)."""
    data, sr = sf.read(str(wav_path), always_2d=True)
    n_old = data.shape[0]
    mono = _mono_for_detect(data)
    onset = first_onset_sample(mono, sr)
    pre_roll = int(sr * pre_roll_ms / 1000.0)
    trim_start = max(0, onset - pre_roll)
    trimmed = data[trim_start:, :]
    n_new = trimmed.shape[0]

    if dry_run:
        print(f"  {wav_path.parent.name}: old={n_old} sr={sr} onset~{onset} trim_start={trim_start} new={n_new}")
        return n_old, trim_start, n_new

    if backup and wav_path.is_file():
        bak = wav_path.with_suffix(wav_path.suffix + ".bak")
        shutil.copy2(wav_path, bak)

    sf.write(str(wav_path), trimmed, sr)
    return n_old, trim_start, n_new


def update_meta(pair_dir: Path, pre_roll_ms: float, trim_start: int, n_old: int, n_new: int) -> None:
    meta_path = pair_dir / "meta.json"
    if not meta_path.is_file():
        return
    m = json.loads(meta_path.read_text(encoding="utf-8"))
    m["trim_applied"] = True
    m["trim_pre_roll_ms"] = pre_roll_ms
    m["trim_start_sample"] = trim_start
    m["trim_old_length_samples"] = n_old
    m["trim_new_length_samples"] = n_new
    m["render_placeholder"] = False
    meta_path.write_text(json.dumps(m, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Trim leading silence from paired_v1 render.wav files.")
    ap.add_argument("--pre-roll-ms", type=float, default=15.0, help="Audio kept before detected onset (default 15).")
    ap.add_argument("--backup", action="store_true", help="Save render.wav.bak before overwrite.")
    ap.add_argument("--dry-run", action="store_true", help="Print trim points only.")
    ap.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="paired_v1 directory (default: beside tools/).",
    )
    args = ap.parse_args()
    root: Path = args.root.resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 1

    dirs = sorted(
        d for d in root.iterdir() if d.is_dir() and d.name.startswith("pair_") and (d / "render.wav").is_file()
    )
    if not dirs:
        print("No pair_XX/render.wav found.", file=sys.stderr)
        return 1

    for d in dirs:
        wav = d / "render.wav"
        try:
            n_old, trim_start, n_new = trim_one(
                wav,
                pre_roll_ms=args.pre_roll_ms,
                backup=bool(args.backup),
                dry_run=bool(args.dry_run),
            )
        except Exception as exc:
            print(f"ERR {d.name}: {exc}", file=sys.stderr)
            return 1
        print(f"{d.name}: samples {n_old} -> {n_new} (trim_start={trim_start})")
        if not args.dry_run:
            update_meta(d, args.pre_roll_ms, trim_start, n_old, n_new)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
