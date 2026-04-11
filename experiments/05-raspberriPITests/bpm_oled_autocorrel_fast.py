#!/usr/bin/env python3
import time
import signal
import sys
from collections import deque

import numpy as np
import sounddevice as sd

from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from PIL import Image, ImageDraw

# ---------- CONFIG ----------
DEVICE_MATCH = ["USB Audio CODEC"]
I2C_ADDR = 0x3C

SR = 44100
BLOCK = 1024

# Long-term autocorr window (stability)
WINDOW_SEC = 8.0

# Fast-lock phase: for first FAST_LOCK_DURATION seconds use shorter window
FAST_LOCK_WINDOW_SEC = 4.0
FAST_LOCK_DURATION_SEC = 6.0

# How often to recompute BPM (responsiveness)
UPDATE_SEC = 0.5

NO_SIGNAL_RMS = 0.003

BPM_MIN = 90.0
BPM_MAX = 180.0

# Envelope smoothing (seconds): smaller = faster, larger = smoother
ENV_LP_SEC = 0.025  # 25ms

# Display smoothing / hysteresis
CLOSE_BPM = 2.0         # if estimate within this, follow faster
ALPHA_CLOSE = 0.25
ALPHA_FAR = 0.10
# ---------------------------

running = True
device_index = None
device_name = "?"

last_rms = 0.0
bpm_est = 0.0
bpm_lock = 0.0
last_update = 0.0
start_t = time.time()

ring = deque(maxlen=int(WINDOW_SEC * SR))


def pick_input_device():
    devs = sd.query_devices()
    for i, d in enumerate(devs):
        if d.get("max_input_channels", 0) <= 0:
            continue
        name = d.get("name", "")
        if any(m.lower() in name.lower() for m in DEVICE_MATCH):
            return i, name
    raise RuntimeError("USB Audio CODEC not found among input devices")


def handle_signal(signum, frame):
    global running
    running = False


def envelope(x: np.ndarray, sr: int) -> np.ndarray:
    # Rectify + 1st-order low-pass (cheap envelope follower)
    x = np.abs(x).astype(np.float32)

    alpha = np.exp(-1.0 / (sr * ENV_LP_SEC))
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = alpha * acc + (1.0 - alpha) * x[i]
        y[i] = acc

    # Remove DC / slow drift
    y -= float(np.mean(y))
    return y


def autocorr_bpm(env: np.ndarray, sr: int) -> float:
    n = len(env)
    if n < int(3 * sr):
        return 0.0

    w = np.hanning(n).astype(np.float32)
    x = (env * w).astype(np.float32)

    nfft = 1 << (n - 1).bit_length()
    X = np.fft.rfft(x, n=nfft)
    ac = np.fft.irfft(X * np.conj(X), n=nfft)[:n]
    ac[0] = 0.0

    lag_min = int(sr * 60.0 / BPM_MAX)
    lag_max = int(sr * 60.0 / BPM_MIN)
    lag_max = min(lag_max, n - 1)
    if lag_max <= lag_min + 10:
        return 0.0

    seg = ac[lag_min:lag_max]
    i = int(np.argmax(seg))
    lag = lag_min + i

    # Parabolic interpolation
    if 1 <= lag < len(ac) - 1:
        y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
        denom = (y0 - 2.0 * y1 + y2)
        if denom != 0:
            delta = 0.5 * (y0 - y2) / denom
            lag = lag + float(delta)

    bpm = 60.0 * sr / float(lag)

    # Fold half/double-time
    while bpm < BPM_MIN:
        bpm *= 2.0
    while bpm > BPM_MAX:
        bpm /= 2.0

    return float(bpm)


def main():
    global device_index, device_name, last_rms, bpm_est, bpm_lock, last_update, start_t

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    device_index, device_name = pick_input_device()
    sd.default.device = (device_index, None)

    serial = i2c(port=1, address=I2C_ADDR)
    oled = sh1106(serial)

    def cb(indata, frames, time_info, status):
        global last_rms
        mono = indata.mean(axis=1).astype(np.float32)
        rms = float(np.sqrt(np.mean(mono * mono)))
        last_rms = rms
        ring.extend(mono.tolist())

    try:
        with sd.InputStream(channels=2, samplerate=SR, blocksize=BLOCK, callback=cb):
            tick = 0
            while running:
                tick += 1
                now = time.time()

                if now - last_update >= UPDATE_SEC:
                    last_update = now

                    if last_rms >= NO_SIGNAL_RMS and len(ring) >= int(3 * SR):
                        x_all = np.array(ring, dtype=np.float32)

                        # fast-lock then stable-lock windowing
                        if (now - start_t) < FAST_LOCK_DURATION_SEC:
                            use_sec = FAST_LOCK_WINDOW_SEC
                        else:
                            use_sec = WINDOW_SEC

                        n = int(use_sec * SR)
                        x = x_all[-n:] if len(x_all) >= n else x_all

                        env = envelope(x, SR)
                        bpm_est = autocorr_bpm(env, SR)

                        if bpm_est > 0:
                            if bpm_lock == 0.0:
                                bpm_lock = bpm_est
                            else:
                                alpha = ALPHA_CLOSE if abs(bpm_est - bpm_lock) <= CLOSE_BPM else ALPHA_FAR
                                bpm_lock = (1.0 - alpha) * bpm_lock + alpha * bpm_est

                # OLED render (simple)
                img = Image.new("1", oled.size, 0)
                draw = ImageDraw.Draw(img)
                draw.text((0, 0), "BPM (ACF)", fill=1)

                if last_rms < NO_SIGNAL_RMS:
                    draw.text((0, 16), "NO SIGNAL", fill=1)
                else:
                    draw.text((0, 16), f"{bpm_lock:6.1f}", fill=1)

                draw.text((0, 32), f"rms {last_rms:.3f}", fill=1)
                draw.text((0, 48), f"in[{device_index}]", fill=1)
                oled.display(img)

                print(
                    f"tick={tick} bpm_est={bpm_est:.1f} bpm_lock={bpm_lock:.1f} rms={last_rms:.4f}",
                    flush=True,
                )
                time.sleep(0.05)

    finally:
        try:
            oled.clear()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FATAL:", e, file=sys.stderr)
        sys.exit(1)
