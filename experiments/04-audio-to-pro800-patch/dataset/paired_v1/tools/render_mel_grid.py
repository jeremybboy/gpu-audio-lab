"""Save 2×5 log-mel overview of all paired_v1 render.wav (matches notebook cell 5)."""
from __future__ import annotations

import csv
from pathlib import Path

import librosa
import librosa.display
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # paired_v1/


def main() -> int:
    rows: list[dict[str, str]] = []
    with (ROOT / "manifest.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["stem"] = Path(row["bank_stem"]).stem
            rows.append(row)

    out_dir = ROOT / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "paired_v1_mel_grid.png"

    fig, axes = plt.subplots(2, 5, figsize=(16, 5.5))
    for ax, row in zip(axes.flat, rows):
        pid = row["pair_id"]
        wav = ROOT / pid / "render.wav"
        y, sr = librosa.load(str(wav), sr=None, mono=True)
        S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
        S_db = librosa.power_to_db(S, ref=np.max)
        librosa.display.specshow(S_db, sr=sr, x_axis="time", y_axis="mel", ax=ax)
        ax.set_title(f"{pid}\n{row['stem']}", fontsize=8)
    plt.suptitle("All pairs — log-mel", y=1.02)
    plt.tight_layout()
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
