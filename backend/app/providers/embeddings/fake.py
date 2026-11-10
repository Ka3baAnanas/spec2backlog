"""Deterministic hashing bag-of-words. For tests / offline demo only."""

import hashlib
import math


class FakeEmbedder:
    name = "fake"
    dimensions = 256

    def embed(
        self, texts: list[str], task: str = "document", on_event=None
    ) -> list[list[float]]:
        out = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for word in text.lower().split():
                digest = int(hashlib.md5(word.encode()).hexdigest(), 16)
                vector[digest % self.dimensions] += 1
            norm = math.sqrt(sum(value * value for value in vector)) or 1
            out.append([value / norm for value in vector])
        return out
