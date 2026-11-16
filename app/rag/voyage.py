from __future__ import annotations
import os
from typing import Generator

MODEL = "voyage-3-lite"
BATCH_SIZE = 64
DIMS = 512


def _client():
    import voyageai
    return voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])


def embed_batch(texts: list[str], input_type: str = "document") -> list[list[float]]:
    return _client().embed(texts, model=MODEL, input_type=input_type).embeddings


def embed_query(query: str) -> list[float]:
    return embed_batch([query], input_type="query")[0]


def batched(items: list, size: int = BATCH_SIZE) -> Generator:
    for i in range(0, len(items), size):
        yield items[i: i + size]
