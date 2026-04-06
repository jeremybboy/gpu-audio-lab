from __future__ import annotations

from core_mapping.schema import AbstractSubtractiveParams
from devices.pro800.schema import Pro800Patch, patch_baseline


def _to_midi7(value_01: float) -> int:
    clipped = max(0.0, min(1.0, value_01))
    return int(round(clipped * 127.0))


def map_to_pro800(params: AbstractSubtractiveParams, patch_name: str = "Generated") -> Pro800Patch:
    patch = patch_baseline(name=patch_name)
    for key, value in params.to_dict().items():
        if key in patch.params_0_127:
            patch.params_0_127[key] = _to_midi7(value)
    return patch

