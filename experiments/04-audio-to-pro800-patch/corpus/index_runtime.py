from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INDEX_DIR = ROOT / "corpus" / "_index"
EMBEDDINGS_NPY = INDEX_DIR / "embeddings.npy"
COORDS_NPY = INDEX_DIR / "coords_2d.npy"
META_JSON = INDEX_DIR / "meta.json"
PCA_PATH = INDEX_DIR / "pca.joblib"
MODEL_NAME_TXT = INDEX_DIR / "model_name.txt"

_model = None
_bundle: dict[str, Any] | None = None


def index_ready() -> bool:
    return (
        EMBEDDINGS_NPY.is_file()
        and COORDS_NPY.is_file()
        and META_JSON.is_file()
        and PCA_PATH.is_file()
        and MODEL_NAME_TXT.is_file()
    )


def _load_bundle() -> dict[str, Any]:
    global _bundle
    if _bundle is not None:
        return _bundle
    if not index_ready():
        raise FileNotFoundError(
            f"Corpus index missing under {INDEX_DIR}. Run: python corpus/build_index.py"
        )
    meta = json.loads(META_JSON.read_text(encoding="utf-8"))
    _bundle = {
        "embeddings": np.load(EMBEDDINGS_NPY),
        "coords_2d": np.load(COORDS_NPY),
        "meta": meta,
        "pca": joblib.load(PCA_PATH),
        "model_name": MODEL_NAME_TXT.read_text(encoding="utf-8").strip(),
    }
    return _bundle


def _get_model():
    global _model
    if _model is not None:
        return _model
    from sentence_transformers import SentenceTransformer

    name = MODEL_NAME_TXT.read_text(encoding="utf-8").strip()
    override = os.environ.get("CORPUS_EMBED_MODEL")
    if override:
        name = override
    _model = SentenceTransformer(name)
    return _model


def _cosine_sim(q: np.ndarray, X: np.ndarray) -> np.ndarray:
    qn = q / (np.linalg.norm(q) + 1e-9)
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    return Xn @ qn


def match_query(query: str, k: int = 8) -> dict[str, Any]:
    q = query.strip()
    if not q:
        raise ValueError("empty query")
    b = _load_bundle()
    model = _get_model()
    q_emb = np.asarray(model.encode(q, convert_to_numpy=True), dtype=np.float64).ravel()
    sims = _cosine_sim(q_emb, b["embeddings"])
    top_idx = np.argsort(-sims)[: max(1, k)]

    pca = b["pca"]
    q_xy = pca.transform(q_emb.reshape(1, -1))[0].tolist()

    matches = []
    for i in top_idx:
        m = dict(b["meta"][int(i)])
        m["score"] = float(sims[int(i)])
        m["x"] = float(b["coords_2d"][int(i), 0])
        m["y"] = float(b["coords_2d"][int(i), 1])
        matches.append(m)

    return {
        "query": q,
        "query_xy": {"x": q_xy[0], "y": q_xy[1]},
        "matches": matches,
    }


def viz_payload() -> dict[str, Any]:
    b = _load_bundle()
    points = []
    for i, m in enumerate(b["meta"]):
        points.append(
            {
                "id": m["id"],
                "family": m["family"],
                "label": m.get("label", m["id"]),
                "x": float(b["coords_2d"][i, 0]),
                "y": float(b["coords_2d"][i, 1]),
            }
        )
    families = sorted({p["family"] for p in points})
    return {"points": points, "families": families}


def preset_meta_by_id(preset_id: str) -> dict[str, Any]:
    """Export metadata for one corpus row (same ordering as the built index)."""
    b = _load_bundle()
    for m in b["meta"]:
        if m["id"] == preset_id:
            return dict(m)
    raise KeyError(f"unknown preset_id: {preset_id!r}")
