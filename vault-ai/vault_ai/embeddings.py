"""Turn text into vectors so notes can be found by meaning, not just exact words.

Runs a small embedding model locally (BAAI/bge-small-en-v1.5, about 70 MB,
downloaded once on first use), so your notes never leave your machine for
this step. Install with `pip install fastembed`; without it, vault-ai
falls back to keyword search only.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import numpy as np

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class Embedder(Protocol):
    name: str  # stored in the index so a model change triggers re-embedding

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...


def normalize(vectors: np.ndarray) -> np.ndarray:
    """Scale each row to length 1, so a dot product is the cosine similarity."""
    import numpy as np

    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


class FastEmbedder:
    def __init__(self, model: str = DEFAULT_MODEL):
        from fastembed import TextEmbedding
        from loguru import logger

        # fastembed logs every download retry; load_default_embedder reports
        # a failure in one line instead.
        logger.disable("fastembed")
        self.name = model
        self._model = TextEmbedding(model)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return normalize(list(self._model.passage_embed(texts)))

    def embed_query(self, text: str) -> np.ndarray:
        return normalize(list(self._model.query_embed(text)))[0]


def load_default_embedder(model: str = DEFAULT_MODEL) -> Embedder | None:
    """The local embedding model, or None (with a note on stderr) if it can't load."""
    try:
        import fastembed  # noqa: F401
    except ImportError:
        print("Semantic search is off: run `pip install fastembed` to turn it on.", file=sys.stderr)
        return None
    try:
        return FastEmbedder(model)
    except Exception as e:  # first run needs to download the model; this fails offline
        print(f"Semantic search is off: could not load {model} ({e}).", file=sys.stderr)
        return None
