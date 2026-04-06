from __future__ import annotations

import io
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from flask import Flask, jsonify, request, send_file

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_mapping.mapping import analyze_timbre_profile, map_timbre_to_abstract
from core_mapping.schema import TimbreFeatures
from devices.pro800.export import export_patch_cc_stream, export_patch_json, export_patch_syx
from devices.pro800.mapping import map_to_pro800
from devices.pro800.schema import Pro800Patch
from devices.pro800.transport import capture_sysex_dump, list_midi_inputs, list_midi_outputs, send_patch_cc, send_sysex_file

app = Flask(__name__)


def _syx_template_path(root: Path, basename: str | None) -> Path | None:
    if not basename:
        return None
    safe = Path(basename).name
    cand = (root / "presets" / safe).resolve()
    presets_dir = (root / "presets").resolve()
    if cand.parent != presets_dir:
        return None
    return cand if cand.is_file() else None


def _estimate_features_from_audio(payload: bytes) -> TimbreFeatures:
    data, sr = sf.read(io.BytesIO(payload), always_2d=False)
    if data.ndim > 1:
        data = np.mean(data, axis=1)
    y = data.astype(np.float32)

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr).mean()
    rms = librosa.feature.rms(y=y)[0]
    peak_idx = int(np.argmax(rms))
    attack_time_s = float((peak_idx * 512) / sr)

    harmonic = librosa.effects.harmonic(y)
    percussive = librosa.effects.percussive(y)
    h_energy = float(np.sum(harmonic**2) + 1e-8)
    p_energy = float(np.sum(percussive**2) + 1e-8)
    hnr = h_energy / p_energy

    return TimbreFeatures(
        spectral_centroid_mean=float(centroid),
        spectral_rolloff_mean=float(rolloff),
        attack_time_s=max(0.001, min(1.0, attack_time_s)),
        harmonic_to_noise_ratio=float(hnr),
        vibrato_rate_hz=0.0,
    )


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "experiment": "04-audio-to-pro800-patch", "version": "phase1"})


@app.post("/api/analyze")
def analyze():
    if "file" in request.files:
        payload = request.files["file"].read()
        features = _estimate_features_from_audio(payload)
        return jsonify({"source": "audio", "features": features.to_dict()})

    body = request.get_json(force=True, silent=True) or {}
    profile = body.get("profile")
    if profile is None:
        return jsonify({"error": "Provide multipart file or JSON body with 'profile'."}), 400
    features = analyze_timbre_profile(profile)
    return jsonify({"source": "profile", "features": features.to_dict()})


@app.post("/api/map")
def map_endpoint():
    body = request.get_json(force=True)
    features = TimbreFeatures(**body["features"])
    abstract = map_timbre_to_abstract(features)
    patch = map_to_pro800(abstract, patch_name=body.get("name", "Generated"))
    return jsonify({"abstract_params": abstract.to_dict(), "pro800_patch": patch.to_dict()})


@app.post("/api/export")
def export_endpoint():
    body = request.get_json(force=True)
    patch = body["patch"]
    fmt = body.get("format", "json")
    name = patch.get("name", "generated")
    params = patch["params_0_127"]
    pro_patch = Pro800Patch(name=name, params_0_127={k: int(v) for k, v in params.items()})

    out_dir = ROOT / "presets"
    out_dir.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        out_path = export_patch_json(pro_patch, out_dir / f"{name}.json")
        return jsonify({"path": str(out_path), "format": "json"})
    if fmt == "cc":
        out_path = export_patch_cc_stream(pro_patch, out_dir / f"{name}.cc.json")
        return jsonify({"path": str(out_path), "format": "cc"})
    if fmt == "syx":
        tpl = _syx_template_path(ROOT, body.get("syx_template"))
        idx = body.get("preset_index")
        idx_int = int(idx) if idx is not None else None
        out_path = export_patch_syx(
            pro_patch,
            out_dir / f"{name}.syx",
            template_path=tpl,
            preset_index=idx_int,
        )
        return send_file(out_path, as_attachment=True, download_name=out_path.name)
    return jsonify({"error": "format must be one of: json, cc, syx"}), 400


@app.get("/api/midi/outputs")
def midi_outputs_endpoint():
    return jsonify({"outputs": list_midi_outputs()})


@app.get("/api/midi/inputs")
def midi_inputs_endpoint():
    return jsonify({"inputs": list_midi_inputs()})


@app.post("/api/send")
def send_endpoint():
    body = request.get_json(force=True)
    patch = body["patch"]
    name = patch.get("name", "generated")
    params = patch["params_0_127"]
    channel = int(body.get("channel", 0))
    port_contains = body.get("port_contains", "PRO 800")
    pro_patch = Pro800Patch(name=name, params_0_127={k: int(v) for k, v in params.items()})
    port_used = send_patch_cc(
        pro_patch,
        midi_channel=channel,
        output_port_contains=port_contains,
    )
    return jsonify({"status": "sent", "port_used": port_used, "name": name, "channel": channel})


@app.post("/api/sysex/send")
def sysex_send_endpoint():
    body = request.get_json(force=True)
    syx_path = body.get("file")
    if not syx_path:
        return jsonify({"error": "Provide 'file' path to .syx."}), 400
    port_contains = body.get("port_contains", "PRO 800")
    delay = float(body.get("delay", 0.02))
    out_name = body.get("output_name")
    port_used = send_sysex_file(
        Path(syx_path),
        output_port_contains=port_contains,
        inter_message_delay_s=delay,
        output_port_name=out_name,
    )
    return jsonify({"status": "sent", "port_used": port_used, "file": syx_path})


@app.post("/api/sysex/capture")
def sysex_capture_endpoint():
    body = request.get_json(force=True, silent=True) or {}
    output = Path(body.get("output", str(ROOT / "presets" / "captured_dump.syx")))
    seconds = float(body.get("seconds", 10.0))
    port_contains = body.get("port_contains", "PRO 800")
    output.parent.mkdir(parents=True, exist_ok=True)
    port_used, count = capture_sysex_dump(
        output_path=output,
        input_port_contains=port_contains,
        listen_seconds=seconds,
    )
    return jsonify({"status": "captured", "port_used": port_used, "packets": count, "output": str(output)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055, debug=True)

