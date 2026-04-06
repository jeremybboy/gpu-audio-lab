from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_mapping.mapping import analyze_timbre_profile, map_timbre_to_abstract
from devices.pro800.mapping import map_to_pro800


def run_smoke_test() -> None:
    profile = {
        "spectral_centroid_mean": 1600.0,
        "spectral_rolloff_mean": 3500.0,
        "attack_time_s": 0.03,
        "harmonic_to_noise_ratio": 10.0,
        "vibrato_rate_hz": 4.0,
    }
    features = analyze_timbre_profile(profile)
    abstract = map_timbre_to_abstract(features)
    patch = map_to_pro800(abstract, patch_name="smoke")
    assert patch.name == "smoke"
    assert all(0 <= v <= 127 for v in patch.params_0_127.values())


if __name__ == "__main__":
    run_smoke_test()
    print("Smoke test passed.")

