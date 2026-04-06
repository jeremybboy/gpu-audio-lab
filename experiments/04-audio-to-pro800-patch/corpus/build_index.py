from __future__ import annotations

"""Build embedding matrix + PCA 2D for corpus (run after seed_corpus, with deps installed)."""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.decomposition import PCA

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CORPUS_JSONL = ROOT / "corpus" / "presets_corpus.jsonl"
INDEX_DIR = ROOT / "corpus" / "_index"
EMBEDDINGS_NPY = INDEX_DIR / "embeddings.npy"
COORDS_NPY = INDEX_DIR / "coords_2d.npy"
META_JSON = INDEX_DIR / "meta.json"
PCA_PATH = INDEX_DIR / "pca.joblib"
MODEL_NAME_TXT = INDEX_DIR / "model_name.txt"


def _load_rows() -> list[dict]:
    if not CORPUS_JSONL.is_file():
        from corpus.seed_corpus import main as seed_main

        seed_main()
    rows = []
    with CORPUS_JSONL.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def main() -> None:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        print(
            "Install corpus deps: pip install sentence-transformers scikit-learn joblib",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    rows = _load_rows()
    if not rows:
        raise SystemExit("Corpus empty")

    model_name = "all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name)

    embs: list[np.ndarray] = []
    meta_out: list[dict] = []
    for row in rows:
        chunks = row.get("text_chunks") or []
        if not chunks:
            continue
        vecs = model.encode(list(chunks), convert_to_numpy=True, show_progress_bar=False)
        mean_vec = np.asarray(vecs, dtype=np.float64).mean(axis=0)
        embs.append(mean_vec)
        meta_out.append(
            {
                "id": row["id"],
                "family": row["family"],
                "label": row.get("label", row["id"]),
                "patch_file": row["patch_file"],
                "syx_overlay": row.get("syx_overlay", "patch_only"),
                "recommended_template_basename": row.get(
                    "recommended_template_basename", "28 solid bass.syx"
                ),
            }
        )

    X = np.stack(embs, axis=0)
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDDINGS_NPY, X)
    np.save(COORDS_NPY, coords)
    META_JSON.write_text(json.dumps(meta_out, indent=2), encoding="utf-8")
    joblib.dump(pca, PCA_PATH)
    MODEL_NAME_TXT.write_text(model_name, encoding="utf-8")
    print(f"Indexed {len(meta_out)} presets -> {INDEX_DIR}")


if __name__ == "__main__":
    main()
