"""
Audio processing demo — generates a synthetic signal and saves
waveform, spectrogram, mel spectrogram, and MFCC plots to disk.
"""

from __future__ import annotations

from pathlib import Path

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

SR = 22_050
DURATION = 3.0
OUT_DIR = Path(__file__).parent / "output"


def make_signal() -> np.ndarray:
    t = np.linspace(0, DURATION, int(SR * DURATION), endpoint=False)
    return (
        0.40 * np.sin(2 * np.pi * 440 * t)
        + 0.30 * np.sin(2 * np.pi * 880 * t)
        + 0.15 * np.sin(2 * np.pi * 1320 * t)
    )


def plot_waveform(y: np.ndarray, path: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(10, 5))
    t = np.linspace(0, DURATION, len(y), endpoint=False)

    librosa.display.waveshow(y, sr=SR, ax=axes[0], color="steelblue")
    axes[0].set_title("Full waveform")

    n = int(0.02 * SR)
    axes[1].plot(t[:n] * 1000, y[:n], color="coral")
    axes[1].set_xlabel("Time (ms)")
    axes[1].set_ylabel("Amplitude")
    axes[1].set_title("First 20 ms (zoomed)")

    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_spectrogram(y: np.ndarray, path: Path) -> None:
    S = librosa.stft(y, n_fft=2048, hop_length=512)
    S_db = librosa.amplitude_to_db(np.abs(S), ref=np.max)

    fig, ax = plt.subplots(figsize=(10, 4))
    img = librosa.display.specshow(
        S_db, sr=SR, hop_length=512, x_axis="time", y_axis="hz", ax=ax, cmap="magma"
    )
    fig.colorbar(img, ax=ax, format="%+2.0f dB")
    ax.set_title("Magnitude Spectrogram")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_mel(y: np.ndarray, path: Path) -> None:
    S_mel = librosa.feature.melspectrogram(
        y=y, sr=SR, n_fft=2048, hop_length=512, n_mels=128
    )
    S_mel_db = librosa.power_to_db(S_mel, ref=np.max)

    fig, ax = plt.subplots(figsize=(10, 4))
    img = librosa.display.specshow(
        S_mel_db, sr=SR, hop_length=512, x_axis="time", y_axis="mel", ax=ax, cmap="viridis"
    )
    fig.colorbar(img, ax=ax, format="%+2.0f dB")
    ax.set_title("Mel Spectrogram (128 bands)")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_mfcc(y: np.ndarray, path: Path) -> None:
    mfccs = librosa.feature.mfcc(y=y, sr=SR, n_mfcc=13, n_fft=2048, hop_length=512)

    fig, ax = plt.subplots(figsize=(10, 3))
    img = librosa.display.specshow(mfccs, sr=SR, hop_length=512, x_axis="time", ax=ax)
    fig.colorbar(img, ax=ax)
    ax.set_title("MFCCs (13 coefficients)")
    ax.set_ylabel("MFCC index")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    y = make_signal()
    print(f"Signal: {DURATION}s, {SR} Hz, shape={y.shape}")

    steps = [
        ("1_waveform.png", plot_waveform),
        ("2_spectrogram.png", plot_spectrogram),
        ("3_mel_spectrogram.png", plot_mel),
        ("4_mfcc.png", plot_mfcc),
    ]
    for name, fn in steps:
        path = OUT_DIR / name
        fn(y, path)
        print(f"  Saved {path}")

    wav_path = OUT_DIR / "demo_tone.wav"
    sf.write(wav_path, y, SR)
    print(f"  Saved {wav_path}")

    print("Done — all plots + audio in ./output/")


if __name__ == "__main__":
    main()
