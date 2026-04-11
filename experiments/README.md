# Experiments

Each numbered folder is a self-contained project with its own scripts, data layout, and `README.md`. This file is the **index for `experiments/`**; GitHub shows it when you open [gpu-audio-lab/experiments](https://github.com/jeremybboy/gpu-audio-lab/tree/master/experiments) in the browser.

## In-repo experiments

| Folder | Summary |
|--------|---------|
| [`01-cpu-vs-gpu/`](01-cpu-vs-gpu/) | CPU vs GPU benchmarks (matrix multiply, mel spectrogram, conv forward). |
| [`01-audio-exploration/`](01-audio-exploration/) | Audio basics — waveform, spectrogram, mel, MFCCs. |
| [`02-placeholder/`](02-placeholder/) | Placeholder for repo access tests. |
| [`03-neural-vs-classical-recommendation/`](03-neural-vs-classical-recommendation/) | MovieLens-style neural vs classical recommenders. |
| [`03-fair-sasrec-vs-classical/`](03-fair-sasrec-vs-classical/) | Extended fair runs and metrics. |
| [`04-audio-to-pro800-patch/`](04-audio-to-pro800-patch/) | Timbre / audio → patch → Behringer PRO-800 (JSON, MIDI, `.syx`, web UI). |
| [`05-raspberriPITests/`](05-raspberriPITests/) | Raspberry Pi USB live BPM + OLED; vendored copy for editing via **Cursor Remote SSH** (see folder `README.md`). |

## Raspberry Pi real-time audio (companion repo)

Device-side code is checked in under **[`05-raspberriPITests/`](05-raspberriPITests/)** so it appears next to the rest of the lab on GitHub and on disk.

The **public / appliance** home for that project is still **[jeremybboy/Raspberri_Pi_Audio](https://github.com/jeremybboy/Raspberri_Pi_Audio)** — refresh the `05-raspberriPITests/` tree from there when you cut a release, or push changes upstream when you want the standalone repo to match.

For **CPU / PyTorch** use of the wider mono-repo on the Pi (venv, root `requirements.txt`, no CUDA wheel index), see **[Raspberry Pi (remote CPU lab)](../README.md#raspberry-pi-remote-cpu-lab)**.
