"""
Load an audio file and display its spectrogram, or generate a synthetic
tone if no file is provided.

Usage:
    python show_spectrogram.py                     # synthetic demo
    python show_spectrogram.py path/to/audio.wav   # real file
"""

from __future__ import annotations

import argparse
import sys

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="Display spectrogram of an audio file.")
    parser.add_argument("audio_path", nargs="?", default=None,
                        help="Path to .wav/.mp3/.flac. Omit for a synthetic tone.")
    parser.add_argument("--sr", type=int, default=22_050, help="Target sample rate.")
    parser.add_argument("--n_fft", type=int, default=2048, help="FFT window size.")
    parser.add_argument("--hop", type=int, default=512, help="Hop length.")
    args = parser.parse_args()

    if args.audio_path:
        print(f"Loading {args.audio_path} ...")
        y, sr = librosa.load(args.audio_path, sr=args.sr, mono=True)
    else:
        print("No file provided — generating a 2-second synthetic tone (440 Hz + 880 Hz).")
        sr = args.sr
        t = np.linspace(0.0, 2.0, int(sr * 2.0), endpoint=False)
        y = 0.4 * np.sin(2 * np.pi * 440 * t) + 0.3 * np.sin(2 * np.pi * 880 * t)

    S = librosa.stft(y, n_fft=args.n_fft, hop_length=args.hop)
    S_db = librosa.amplitude_to_db(np.abs(S), ref=np.max)

    fig, ax = plt.subplots(figsize=(10, 4))
    img = librosa.display.specshow(S_db, sr=sr, hop_length=args.hop,
                                   x_axis="time", y_axis="hz", ax=ax)
    fig.colorbar(img, ax=ax, format="%+2.0f dB")
    ax.set_title("Magnitude Spectrogram")
    plt.tight_layout()

    out_path = "spectrogram.png"
    fig.savefig(out_path, dpi=150)
    print(f"Saved to {out_path}")
    plt.show()


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print(f"File not found: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
