from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Pro800Patch:
    name: str
    params_0_127: dict[str, int]

    def to_dict(self) -> dict:
        return {"name": self.name, "params_0_127": dict(self.params_0_127)}

    @classmethod
    def from_export_dict(cls, data: dict) -> Pro800Patch:
        """Load from `export_patch_json` / `generate` output (name + params_0_127).

        Merges onto patch_baseline so omitted keys keep safe defaults; values clamped 0..127.
        Unknown keys are kept so future encoder fields can round-trip.
        """
        name = str(data.get("name", "patch"))
        base = patch_baseline(name=name)
        incoming = data.get("params_0_127")
        if not isinstance(incoming, dict):
            return base
        merged = dict(base.params_0_127)
        for k, v in incoming.items():
            merged[str(k)] = max(0, min(127, int(v)))
        return cls(name=name, params_0_127=merged)


def patch_baseline(name: str = "Init") -> Pro800Patch:
    # Conservative baseline values; replace with validated defaults once
    # exact PRO-800 parameter table is finalized.
    baseline = {
        "osc1_level": 96,
        "osc2_level": 90,
        "noise_level": 8,
        "osc_detune": 12,
        "osc_mix_bias": 64,
        "filter_cutoff": 72,
        "filter_resonance": 28,
        "filter_env_amount": 54,
        "amp_attack": 8,
        "amp_decay": 56,
        "amp_sustain": 88,
        "amp_release": 48,
        "filter_attack": 6,
        "filter_decay": 52,
        "filter_sustain": 72,
        "filter_release": 44,
        "lfo_rate": 18,
        "lfo_depth": 6,
        "poly_mod_amount": 14,
    }
    return Pro800Patch(name=name, params_0_127=baseline)

