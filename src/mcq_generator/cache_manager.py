"""
Cache Manager using diskcache for content-addressable storage.
"""

import hashlib
import logging
from typing import Optional
from pathlib import Path
from diskcache import Cache
import orjson

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Multi-layer caching system for MCQ generation:
    1. Content hash cache (exact matches)
    2. Similarity cache (near-duplicates)
    3. Example cache (few-shot learning)
    """

    def __init__(self, cache_dir: str = ".mcq_cache", size_limit: int = 10 * 1024**3):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.mcq_cache = Cache(
            str(self.cache_dir / "mcq"),
            size_limit=size_limit,
            eviction_policy="least-recently-used",
        )

        self.similarity_cache = Cache(
            str(self.cache_dir / "similarity"), size_limit=size_limit // 5
        )

        self.example_cache = Cache(str(self.cache_dir / "examples"), size_limit=size_limit // 10)

        logger.info(
            f"Initialized cache at {self.cache_dir} with {size_limit / 1024**3:.1f}GB limit"
        )

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get_mcq(self, document: str) -> Optional[dict]:
        """Get cached MCQ for a document (exact match)."""
        doc_hash = self._compute_hash(document)
        cached = self.mcq_cache.get(doc_hash)

        if cached:
            logger.debug(f"Cache HIT: {doc_hash[:8]}")
            return orjson.loads(cached)

        logger.debug(f"Cache MISS: {doc_hash[:8]}")
        return None

    def set_mcq(self, document: str, mcq: dict, quality_score: float = 0.0) -> None:
        """Cache an MCQ with its quality score."""
        if quality_score < 70:
            logger.debug(f"Skipping cache: quality {quality_score} < 70")
            return

        doc_hash = self._compute_hash(document)
        cached_data = {
            "mcq": mcq,
            "quality_score": quality_score,
            "document_hash": doc_hash,
            "document_length": len(document),
        }

        self.mcq_cache.set(doc_hash, orjson.dumps(cached_data))
        logger.debug(f"Cached MCQ: {doc_hash[:8]} (quality: {quality_score})")

    def get_similar_mcqs(
        self, document_embedding: list, threshold: float = 0.9, limit: int = 5
    ) -> list:
        """Find similar cached MCQs based on document embeddings."""
        return []

    def cache_embedding(self, document_hash: str, embedding: list) -> None:
        """Cache document embedding for similarity search."""
        self.similarity_cache.set(document_hash, orjson.dumps(embedding))

    def add_example(self, mcq: dict, quality_score: float) -> None:
        """Add a high-quality MCQ to the example cache for few-shot learning."""
        if quality_score < 90:
            return

        example_count = len(self.example_cache)
        example_id = f"example_{example_count:05d}"

        self.example_cache.set(example_id, orjson.dumps({"mcq": mcq, "score": quality_score}))

        logger.info(f"Added example {example_id} (score: {quality_score})")

    def get_best_examples(self, n: int = 3) -> list:
        """Get N best examples for few-shot prompting."""
        examples = []
        for key in self.example_cache.iterkeys():
            data = orjson.loads(self.example_cache.get(key))
            examples.append(data)

        examples.sort(key=lambda x: x["score"], reverse=True)
        return [ex["mcq"] for ex in examples[:n]]

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "mcq_cache": {
                "size_mb": self.mcq_cache.volume() / 1024**2,
                "count": len(self.mcq_cache),
                "hits": getattr(self.mcq_cache, "hits", 0),
                "misses": getattr(self.mcq_cache, "misses", 0),
                "hit_rate": self._calculate_hit_rate(self.mcq_cache),
            },
            "example_cache": {
                "count": len(self.example_cache),
                "size_mb": self.example_cache.volume() / 1024**2,
            },
            "similarity_cache": {
                "count": len(self.similarity_cache),
                "size_mb": self.similarity_cache.volume() / 1024**2,
            },
        }

    def _calculate_hit_rate(self, cache: Cache) -> float:
        """Calculate cache hit rate."""
        hits = getattr(cache, "hits", 0)
        misses = getattr(cache, "misses", 0)
        total = hits + misses

        return (hits / total * 100) if total > 0 else 0.0

    def clear(self) -> None:
        """Clear all caches."""
        self.mcq_cache.clear()
        self.similarity_cache.clear()
        self.example_cache.clear()
        logger.info("Cleared all caches")

    def clear_mcq_cache(self) -> None:
        """Clear only MCQ cache (keep examples)."""
        self.mcq_cache.clear()
        logger.info("Cleared MCQ cache")

    def close(self) -> None:
        """Close cache connections."""
        self.mcq_cache.close()
        self.similarity_cache.close()
        self.example_cache.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class DuplicateDetector:
    """Detect duplicate or near-duplicate documents."""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.seen_hashes: set = set()

    def is_duplicate(self, document: str) -> bool:
        """Check if document is a duplicate."""
        doc_hash = hashlib.sha256(document.encode()).hexdigest()

        if doc_hash in self.seen_hashes:
            logger.debug(f"Exact duplicate detected: {doc_hash[:8]}")
            return True

        self.seen_hashes.add(doc_hash)
        return False

    def find_similar(self, document: str, threshold: float = 0.85) -> Optional[dict]:
        """Find similar documents in cache."""
        cached_mcq = self.cache.get_mcq(document)
        return cached_mcq

    def reset(self) -> None:
        """Reset duplicate tracking (for new jobs)."""
        self.seen_hashes.clear()
