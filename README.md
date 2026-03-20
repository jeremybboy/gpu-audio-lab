# gpu-audio-lab

Research mono-repo for GPU-accelerated audio ML experiments, benchmarks, and CUDA quantum work.

## Experiments

| # | Folder | Description |
|---|--------|-------------|
| 01 | `experiments/01-cpu-vs-gpu/` | CPU vs GPU benchmarks — matrix multiply, mel spectrogram, conv net forward pass |
| 01 | `experiments/01-audio-exploration/` | Audio fundamentals — waveform, spectrogram, mel, MFCCs (E minor scale demo) |

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

## Environment

- Python 3.11.8
- PyTorch 2.6.0 + CUDA 12.4
- NVIDIA GeForce RTX 2070 Super (8 GB VRAM)
