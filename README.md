# gpu-audio-lab

Personal research **mono-repo** for **GPU-accelerated audio / ML** work: small benchmarks, notebooks, and self-contained **experiments** (each in `experiments/NN-name/`). The focus is reproducible scripts, fair comparisons (warmup, `torch.cuda.synchronize()` where relevant), and clear write-ups—not a single application.

Topics covered here include **PyTorch + CUDA** audio workloads, **classical vs neural** recommendation baselines, and **inverse sound design** (timbre → synthesizer patch) for hardware like the **Behringer PRO-800**.

## Experiments

| # | Folder | Description |
|---|--------|-------------|
| 01 | `experiments/01-cpu-vs-gpu/` | CPU vs GPU benchmarks — matrix multiply, mel spectrogram, conv net forward pass |
| 01 | `experiments/01-audio-exploration/` | Audio fundamentals — waveform, spectrogram, mel, MFCCs (E minor scale demo) |
| 03 | `experiments/03-neural-vs-classical-recommendation/` | MovieLens-1M: SASRec-style neural recommender vs ItemKNN, BPR-MF, FMC |
| 03-fair | `experiments/03-fair-sasrec-vs-classical/` | Extended fair runs and metrics for neural vs classical recommendation |
| 04 | `experiments/04-audio-to-pro800-patch/` | **Timbre / audio → abstract patch → Behringer PRO-800** (JSON, MIDI CC, template-based `.syx`, text intents, local web UI). Repo **`docs/`** holds a static UI for **GitHub Pages** (preview); full export needs **`python app.py`**. See experiment README. |
| 05 | `experiments/05-raspberriPITests/` | Raspberry Pi — USB live BPM + OLED (`bpm_oled_autocorrel_fast.py`). Copy lives here for **Cursor Remote SSH**; canonical repo **[Raspberri_Pi_Audio](https://github.com/jeremybboy/Raspberri_Pi_Audio)**. Index: **[`experiments/README.md`](experiments/README.md)**. |

## Highlights from 01-cpu-vs-gpu

| Benchmark | CPU | GPU | Speedup |
|-----------|-----|-----|---------|
| Matrix multiply (4096x4096) | 207.5 ms | 21.9 ms | **9.5x** |
| Mel spectrogram (single clip) | 0.59 ms | 0.49 ms | **1.2x** |
| Conv net forward pass (batch=64) | 61.9 ms | 3.2 ms | **19.3x** |

GPU advantage scales with workload size — minimal on a single short clip, but **19x** on a realistic training batch through a conv net.

## Setup

```bash
# Create venv
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\activate

# Activate (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# PyTorch with CUDA (adjust cu124 to your CUDA version)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Register Jupyter kernel
python -m ipykernel install --user --name gpu-audio-lab --display-name "Python 3.11 (gpu-audio-lab)"
```

## Raspberry Pi (remote CPU lab)

Use a Raspberry Pi as a **small, always-on CPU target** for scripts, lighter benchmarks, and experiments that do not need CUDA. You edit and run code **on the Pi** while driving the session from your desktop with **SSH + Cursor**.

### Why this repo on a Pi

- **CPU-only PyTorch** and the same Python layout as your workstation (`venv`, `requirements.txt`).
- Good for **long-running or headless** jobs, GPIO-adjacent glue, or validating that something runs without a GPU.
- **CUDA-specific** experiment configs (for example `experiments/01-cpu-vs-gpu` GPU paths) will not apply; prefer CPU code paths or smaller problem sizes.

### One-time on the Raspberry Pi

1. Install **Raspberry Pi OS** (64-bit recommended on Pi 4 / Pi 5).
2. Enable **SSH** (e.g. `sudo raspi-config` → Interface Options → SSH, or imaging tool toggle).
3. Note the Pi’s **hostname** (default `raspberrypi`) or set a fixed name, and its **LAN IP** (router DHCP reservation helps).

### One-time on your desktop (SSH)

Add a host block in `~/.ssh/config` (adjust `Host`, `HostName`, and `User`):

```ssh-config
Host pi-gpu-audio-lab
    HostName 192.168.1.50
    User uzan
    # Optional: reuse one key
    # IdentityFile ~/.ssh/id_ed25519
```

Test: `ssh pi-gpu-audio-lab`.

### Cursor: open the repo on the Pi

1. Install the **Remote - SSH** extension in Cursor (same idea as VS Code).
2. **Remote-SSH: Connect to Host…** → pick `pi-gpu-audio-lab` (or your host alias).
3. **File → Open Folder** on the Pi, e.g. `/home/uzan/gpu-audio-lab` after you clone there.

The integrated terminal and agent run **on the Pi**; paths and binaries are the Pi’s, not your PC’s.

### Clone and Python env on the Pi

```bash
cd ~
git clone https://github.com/jeremybboy/gpu-audio-lab.git
cd gpu-audio-lab

python3 -m venv .venv
source .venv/bin/activate

pip install -U pip
pip install -r requirements.txt
```

Install **CPU** PyTorch from the default index (do **not** use the CUDA wheel index from the [Setup](#setup) section on the Pi):

```bash
pip install --upgrade torch torchaudio
```

Register a kernel (optional, for notebooks):

```bash
python -m ipykernel install --user --name gpu-audio-lab-pi --display-name "Python (gpu-audio-lab, Pi CPU)"
```

### Quick sanity check

```bash
source .venv/bin/activate
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

You should see a PyTorch version and `False` for CUDA on the Pi.

## Environment

- Python 3.11.8
- PyTorch 2.6.0 + CUDA 12.4
- NVIDIA GeForce RTX 2070 Super (8 GB VRAM)
