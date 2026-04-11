# 05-raspberriPITests

Raspberry Pi **real-time BPM** from USB audio, with optional **SH1106 OLED** output. This folder holds a **working copy** of the standalone project so you can edit it from **Cursor Remote SSH** inside **gpu-audio-lab**.

**Canonical upstream:** [jeremybboy/Raspberri_Pi_Audio](https://github.com/jeremybboy/Raspberri_Pi_Audio) — push substantive releases there when you want the public appliance repo to stay in sync.

## Hardware (typical)

- Raspberry Pi 5 (Pi 4 possible with tuning)
- USB audio interface (ALSA)
- SH1106 I2C OLED at `0x3C` (enable I2C in `raspi-config`)

## Setup on the Pi

```bash
cd experiments/05-raspberriPITests
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-pi-device.txt
```

## Run

```bash
source .venv/bin/activate
python bpm_oled_autocorrel_fast.py
```

Long-form notes from the original repo are in [`Raspberri_Pi_Audio_Readme.md`](Raspberri_Pi_Audio_Readme.md). Assets: `BPM_Detector_pedal.svg`, `pi_bpm_detector.png`. Subfolder [`LatentSpaceReverb/`](LatentSpaceReverb/) is carried over from upstream.

## Lab context

For **CPU / PyTorch** use of the wider mono-repo on the Pi (not this OLED stack), see the root README [Raspberry Pi (remote CPU lab)](../../README.md#raspberry-pi-remote-cpu-lab).
