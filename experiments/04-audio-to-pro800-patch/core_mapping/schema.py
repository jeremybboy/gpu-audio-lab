from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class TimbreFeatures:
    spectral_centroid_mean: float
    spectral_rolloff_mean: float
    attack_time_s: float
    harmonic_to_noise_ratio: float
    vibrato_rate_hz: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class AbstractSubtractiveParams:
    osc1_level: float
    osc2_level: float
    noise_level: float
    osc_detune: float
    osc_mix_bias: float
    filter_cutoff: float
    filter_resonance: float
    filter_env_amount: float
    amp_attack: float
    amp_decay: float
    amp_sustain: float
    amp_release: float
    filter_attack: float
    filter_decay: float
    filter_sustain: float
    filter_release: float
    lfo_rate: float
    lfo_depth: float
    poly_mod_amount: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

