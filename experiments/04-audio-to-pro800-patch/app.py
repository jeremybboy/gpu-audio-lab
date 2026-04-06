from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from flask import Flask, abort, jsonify, request, send_file, send_from_directory

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_mapping.mapping import analyze_timbre_profile, map_timbre_to_abstract
from core_mapping.schema import TimbreFeatures
from devices.pro800.export import export_patch_cc_stream, export_patch_json, export_patch_syx
from devices.pro800.mapping import map_to_pro800
from devices.pro800.schema import Pro800Patch
from devices.pro800.transport import capture_sysex_dump, list_midi_inputs, list_midi_outputs, send_patch_cc, send_sysex_file
from sound_intents.resolver import load_registry, resolve_in_registry

app = Flask(__name__)

# Repo-root `docs/` — static UI for local Flask and for GitHub Pages (same files).
REPO_ROOT = ROOT.parent.parent
DOCS_WEB = REPO_ROOT / "docs"


def _path_must_be_under(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _registry_path_from_body(body: dict, root: Path) -> Path | None:
    raw = body.get("registry")
    if not raw:
        return None
    p = Path(str(raw)).expanduser()
    if not p.is_absolute():
        p = (root / p).resolve()
    else:
        p = p.resolve()
    if not p.is_file():
        raise ValueError(f"registry file not found: {p}")
    if not _path_must_be_under(p, root):
        raise ValueError("registry path must be inside the experiment directory")
    return p


def _syx_template_path(root: Path, basename: str | None) -> Path | None:
    if not basename:
        return None
    safe = Path(basename).name
    cand = (root / "presets" / safe).resolve()
    presets_dir = (root / "presets").resolve()
    if cand.parent != presets_dir:
        return None
    return cand if cand.is_file() else None


def _corpus_not_ready_response():
    return (
        jsonify(
            {
                "error": (
                    "Corpus index missing. Install corpus extras "
                    "(experiments/04-audio-to-pro800-patch/requirements-corpus.txt), "
                    "then from that folder run: python corpus/build_index.py"
                ),
            }
        ),
        503,
    )


def _corpus_export_syx(meta: dict, body: dict) -> tuple[Path, str]:
    """Load recipe JSON from corpus row and write template-based .syx under presets/."""
    patch_rel = meta.get("patch_file")
    if not patch_rel or not isinstance(patch_rel, str):
        raise ValueError("preset has no patch_file")
    patch_path = (ROOT / patch_rel).resolve()
    if not _path_must_be_under(patch_path, ROOT) or not patch_path.is_file():
        raise ValueError(f"patch JSON not found or invalid path: {patch_rel}")

    tpl_raw = body.get("syx_template") or meta.get("recommended_template_basename")
    if not tpl_raw:
        raise ValueError("syx_template required (body or corpus row)")
    tpl = _syx_template_path(ROOT, str(tpl_raw).strip())
    if tpl is None or not tpl.is_file():
        raise ValueError(f"syx template not found under presets/: {Path(str(tpl_raw)).name!r}")

    overlay = body.get("syx_overlay", meta.get("syx_overlay", "patch_only"))
    if overlay not in ("blend_max", "patch_only"):
        raise ValueError("syx_overlay must be blend_max or patch_only")

    raw = json.loads(patch_path.read_text(encoding="utf-8"))
    pro_patch = Pro800Patch.from_export_dict(raw)

    name_raw = body.get("name") or meta.get("label") or meta.get("id", "corpus_export")
    safe_name = Path(str(name_raw)).name
    if not safe_name or safe_name in (".", ".."):
        safe_name = "corpus_export"

    out_dir = ROOT / "presets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_name}.syx"

    idx = body.get("preset_index")
    idx_int = int(idx) if idx is not None else None

    export_patch_syx(
        pro_patch,
        out_path,
        template_path=tpl,
        preset_index=idx_int,
        syx_overlay=str(overlay),
    )
    return out_path, f"{safe_name}.syx"


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


@app.get("/")
def serve_ui():
    if not DOCS_WEB.is_dir() or not (DOCS_WEB / "index.html").is_file():
        return (
            jsonify(
                {
                    "error": "Web UI missing: add repo-root docs/index.html (clone full repo).",
                }
            ),
            503,
        )
    return send_from_directory(DOCS_WEB, "index.html")


@app.get("/style.css")
def serve_style():
    if not (DOCS_WEB / "style.css").is_file():
        abort(404)
    return send_from_directory(DOCS_WEB, "style.css", mimetype="text/css")


@app.get("/app.js")
def serve_app_js():
    if not (DOCS_WEB / "app.js").is_file():
        abort(404)
    return send_from_directory(DOCS_WEB, "app.js", mimetype="application/javascript")


@app.get("/corpus.html")
def serve_corpus_ui():
    if not DOCS_WEB.is_dir() or not (DOCS_WEB / "corpus.html").is_file():
        return (
            jsonify(
                {
                    "error": "Web UI missing: add repo-root docs/corpus.html.",
                }
            ),
            503,
        )
    return send_from_directory(DOCS_WEB, "corpus.html")


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
        ov = body.get("syx_overlay", "blend_max")
        if ov not in ("blend_max", "patch_only"):
            return jsonify({"error": "syx_overlay must be blend_max or patch_only"}), 400
        out_path = export_patch_syx(
            pro_patch,
            out_dir / f"{name}.syx",
            template_path=tpl,
            preset_index=idx_int,
            syx_overlay=ov,
        )
        return send_file(out_path, as_attachment=True, download_name=out_path.name)
    return jsonify({"error": "format must be one of: json, cc, syx"}), 400


@app.post("/api/export_sound")
def export_sound_endpoint():
    """Text phrase → sound_intents registry → recipe JSON → template-based .syx."""
    body = request.get_json(force=True, silent=True) or {}
    describe = body.get("describe")
    if not describe or not isinstance(describe, str) or not describe.strip():
        return jsonify({"error": "describe (non-empty string) is required"}), 400
    tpl_name = body.get("syx_template")
    if not tpl_name or not isinstance(tpl_name, str):
        return jsonify({"error": "syx_template (basename under presets/) is required"}), 400

    try:
        reg_path = _registry_path_from_body(body, ROOT)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        reg = load_registry(reg_path)
        intent_id, meta = resolve_in_registry(describe.strip(), reg)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    overlay = str(meta.get("syx_overlay", "patch_only"))
    if overlay not in ("blend_max", "patch_only"):
        return jsonify({"error": f"invalid syx_overlay in recipe for {intent_id!r}"}), 400

    rel_patch = meta.get("patch_file")
    if not rel_patch or not isinstance(rel_patch, str):
        return jsonify({"error": f"intent {intent_id!r} has no patch_file in registry"}), 400

    patch_path = (ROOT / rel_patch).resolve()
    if not _path_must_be_under(patch_path, ROOT) or not patch_path.is_file():
        return jsonify({"error": f"recipe patch JSON not found or invalid path: {rel_patch}"}), 400

    tpl = _syx_template_path(ROOT, tpl_name.strip())
    if tpl is None or not tpl.is_file():
        return (
            jsonify(
                {
                    "error": f"syx template not found under presets/: {Path(tpl_name).name!r}",
                }
            ),
            400,
        )

    try:
        raw = json.loads(patch_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"invalid recipe JSON: {exc}"}), 400
    pro_patch = Pro800Patch.from_export_dict(raw)

    name_raw = body.get("name") or intent_id or "sound_export"
    safe_name = Path(str(name_raw)).name
    if not safe_name or safe_name in (".", ".."):
        safe_name = "sound_export"

    out_dir = ROOT / "presets"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_name}.syx"

    idx = body.get("preset_index")
    idx_int = int(idx) if idx is not None else None

    export_patch_syx(
        pro_patch,
        out_path,
        template_path=tpl,
        preset_index=idx_int,
        syx_overlay=overlay,
    )
    return send_file(out_path, as_attachment=True, download_name=out_path.name)


@app.get("/api/corpus/viz")
def corpus_viz():
    from corpus import index_runtime as cr

    if not cr.index_ready():
        return _corpus_not_ready_response()
    try:
        return jsonify(cr.viz_payload())
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 503


@app.post("/api/corpus/match")
def corpus_match():
    from corpus import index_runtime as cr

    if not cr.index_ready():
        return _corpus_not_ready_response()
    body = request.get_json(force=True, silent=True) or {}
    q = body.get("query")
    if not q or not isinstance(q, str) or not q.strip():
        return jsonify({"error": "query (non-empty string) is required"}), 400
    k = int(body.get("k", 8))
    k = max(1, min(k, 50))
    try:
        return jsonify(cr.match_query(q.strip(), k=k))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/corpus/export")
def corpus_export():
    from corpus import index_runtime as cr

    if not cr.index_ready():
        return _corpus_not_ready_response()
    body = request.get_json(force=True, silent=True) or {}
    preset_id = body.get("preset_id")
    query = body.get("query")
    meta: dict
    try:
        if preset_id and isinstance(preset_id, str) and preset_id.strip():
            meta = cr.preset_meta_by_id(preset_id.strip())
        elif query and isinstance(query, str) and query.strip():
            m = cr.match_query(query.strip(), k=1)
            meta = dict(m["matches"][0])
            for drop in ("score", "x", "y"):
                meta.pop(drop, None)
        else:
            return jsonify({"error": "Provide preset_id or non-empty query"}), 400
        out_path, download_name = _corpus_export_syx(meta, body)
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return send_file(out_path, as_attachment=True, download_name=download_name)


@app.post("/api/export_from_profile")
def export_from_profile_endpoint():
    """Timbre profile JSON → map → template-based .syx in one request."""
    body = request.get_json(force=True, silent=True) or {}
    profile = body.get("profile")
    if profile is None or not isinstance(profile, dict):
        return jsonify({"error": "profile (object) is required"}), 400
    tpl_name = body.get("syx_template")
    if not tpl_name or not isinstance(tpl_name, str):
        return jsonify({"error": "syx_template (basename under presets/) is required"}), 400

    tpl = _syx_template_path(ROOT, tpl_name.strip())
    if tpl is None or not tpl.is_file():
        return (
            jsonify(
                {
                    "error": f"syx template not found under presets/: {Path(tpl_name).name!r}",
                }
            ),
            400,
        )

    features = analyze_timbre_profile(profile)
    abstract = map_timbre_to_abstract(features)
    name = body.get("name", "generated")
    if not isinstance(name, str):
        name = "generated"
    patch = map_to_pro800(abstract, patch_name=name)

    ov = body.get("syx_overlay", "blend_max")
    if ov not in ("blend_max", "patch_only"):
        return jsonify({"error": "syx_overlay must be blend_max or patch_only"}), 400

    out_dir = ROOT / "presets"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(str(patch.name)).name
    out_path = out_dir / f"{safe_name}.syx"

    idx = body.get("preset_index")
    idx_int = int(idx) if idx is not None else None

    export_patch_syx(
        patch,
        out_path,
        template_path=tpl,
        preset_index=idx_int,
        syx_overlay=ov,
    )
    return send_file(out_path, as_attachment=True, download_name=out_path.name)


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

