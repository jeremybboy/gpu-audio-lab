from __future__ import annotations

from core_mapping.schema import AbstractSubtractiveParams, TimbreFeatures


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _norm(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return _clip01((x - lo) / (hi - lo))


def analyze_timbre_profile(profile: dict) -> TimbreFeatures:
    return TimbreFeatures(
        spectral_centroid_mean=float(profile.get("spectral_centroid_mean", 1500.0)),
        spectral_rolloff_mean=float(profile.get("spectral_rolloff_mean", 3000.0)),
        attack_time_s=float(profile.get("attack_time_s", 0.03)),
        harmonic_to_noise_ratio=float(profile.get("harmonic_to_noise_ratio", 15.0)),
        vibrato_rate_hz=float(profile.get("vibrato_rate_hz", 0.0)),
    )


def map_timbre_to_abstract(features: TimbreFeatures) -> AbstractSubtractiveParams:
    brightness = _norm(features.spectral_centroid_mean, 400.0, 5000.0)
    rolloff = _norm(features.spectral_rolloff_mean, 1200.0, 10000.0)
    noise_inv = 1.0 - _norm(features.harmonic_to_noise_ratio, 2.0, 30.0)
    attack = _norm(features.attack_time_s, 0.005, 0.25)
    vibrato = _norm(features.vibrato_rate_hz, 0.0, 8.0)

    return AbstractSubtractiveParams(
        osc1_level=_clip01(0.65 + 0.20 * brightness),
        osc2_level=_clip01(0.55 + 0.25 * (1.0 - brightness)),
        noise_level=_clip01(0.05 + 0.40 * noise_inv),
        osc_detune=_clip01(0.08 + 0.25 * (1.0 - attack)),
        osc_mix_bias=_clip01(0.50 + 0.30 * (brightness - 0.5)),
        filter_cutoff=_clip01(0.20 + 0.70 * brightness),
        filter_resonance=_clip01(0.15 + 0.40 * (1.0 - rolloff)),
        filter_env_amount=_clip01(0.20 + 0.50 * attack),
        amp_attack=_clip01(0.05 + 0.70 * attack),
        amp_decay=_clip01(0.35 + 0.40 * (1.0 - attack)),
        amp_sustain=_clip01(0.45 + 0.25 * (1.0 - noise_inv)),
        amp_release=_clip01(0.30 + 0.45 * attack),
        filter_attack=_clip01(0.03 + 0.60 * attack),
        filter_decay=_clip01(0.25 + 0.45 * (1.0 - attack)),
        filter_sustain=_clip01(0.35 + 0.30 * brightness),
        filter_release=_clip01(0.25 + 0.45 * attack),
        lfo_rate=_clip01(0.10 + 0.50 * vibrato),
        lfo_depth=_clip01(0.05 + 0.40 * vibrato),
        poly_mod_amount=_clip01(0.10 + 0.35 * (1.0 - noise_inv)),
    )

