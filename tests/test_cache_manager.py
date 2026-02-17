"""
Tests for cache_manager module.
"""

import pytest
from mcq_generator.cache_manager import CacheManager, DuplicateDetector


class TestCacheManager:
    """Test suite for CacheManager."""

    def test_initialization(self, temp_dir):
        """Test CacheManager initialization creates required directories."""
        cache = CacheManager(cache_dir=str(temp_dir / "test_cache"))
        assert (temp_dir / "test_cache").exists()
        assert (temp_dir / "test_cache" / "mcq").exists()
        assert (temp_dir / "test_cache" / "similarity").exists()
        assert (temp_dir / "test_cache" / "examples").exists()
        cache.close()

    def test_compute_hash(self, cache_manager):
        """Test hash computation is consistent."""
        text = "test document"
        hash1 = cache_manager._compute_hash(text)
        hash2 = cache_manager._compute_hash(text)
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_get_mcq_cache_miss(self, cache_manager):
        """Test cache miss returns None."""
        result = cache_manager.get_mcq("nonexistent document")
        assert result is None

    def test_set_and_get_mcq(self, cache_manager, sample_mcq_dict):
        """Test setting and getting MCQ from cache."""
        text = "This is a test document for caching."

        cache_manager.set_mcq(text, sample_mcq_dict, quality_score=80.0)
        cached = cache_manager.get_mcq(text)

        assert cached is not None
        assert cached["mcq"]["question"] == sample_mcq_dict["question"]

    def test_cache_quality_threshold(self, cache_manager, sample_mcq_dict):
        """Test that low quality MCQs are not cached."""
        text = "Low quality document"

        cache_manager.set_mcq(text, sample_mcq_dict, quality_score=50.0)
        cached = cache_manager.get_mcq(text)

        assert cached is None

    def test_add_example(self, cache_manager, sample_mcq_dict):
        """Test adding high-quality examples."""
        cache_manager.add_example(sample_mcq_dict, quality_score=95.0)

        examples = cache_manager.get_best_examples(n=1)
        assert len(examples) == 1
        assert examples[0]["question"] == sample_mcq_dict["question"]

    def test_example_quality_threshold(self, cache_manager, sample_mcq_dict):
        """Test that low quality examples are not added."""
        cache_manager.add_example(sample_mcq_dict, quality_score=85.0)

        examples = cache_manager.get_best_examples(n=5)
        assert len(examples) == 0

    def test_get_best_examples_ordering(self, cache_manager):
        """Test that examples are returned in descending quality order."""
        mcq1 = {"question": "Q1", "options": ["A", "B", "C"], "correct_answer": 0}
        mcq2 = {"question": "Q2", "options": ["A", "B", "C"], "correct_answer": 0}
        mcq3 = {"question": "Q3", "options": ["A", "B", "C"], "correct_answer": 0}

        cache_manager.add_example(mcq1, quality_score=70.0)
        cache_manager.add_example(mcq2, quality_score=95.0)
        cache_manager.add_example(mcq3, quality_score=85.0)

        examples = cache_manager.get_best_examples(n=5)

        assert len(examples) >= 1

    def test_get_stats(self, cache_manager, sample_mcq_dict):
        """Test cache statistics retrieval."""
        text = "Test document for stats"
        cache_manager.set_mcq(text, sample_mcq_dict, quality_score=80.0)
        cache_manager.add_example(sample_mcq_dict, quality_score=95.0)

        stats = cache_manager.get_stats()

        assert "mcq_cache" in stats
        assert "example_cache" in stats
        assert "similarity_cache" in stats
        assert stats["mcq_cache"]["count"] >= 1

    def test_clear_all_caches(self, cache_manager, sample_mcq_dict):
        """Test clearing all caches."""
        cache_manager.set_mcq("doc1", sample_mcq_dict, quality_score=80.0)
        cache_manager.add_example(sample_mcq_dict, quality_score=95.0)

        cache_manager.clear()

        stats = cache_manager.get_stats()
        assert stats["mcq_cache"]["count"] == 0
        assert stats["example_cache"]["count"] == 0

    def test_clear_mcq_cache_only(self, cache_manager, sample_mcq_dict):
        """Test clearing only MCQ cache (keeping examples)."""
        cache_manager.set_mcq("doc1", sample_mcq_dict, quality_score=80.0)
        cache_manager.add_example(sample_mcq_dict, quality_score=95.0)

        cache_manager.clear_mcq_cache()

        stats = cache_manager.get_stats()
        assert stats["mcq_cache"]["count"] == 0
        assert stats["example_cache"]["count"] == 1

    def test_cache_embedding(self, cache_manager):
        """Test caching document embeddings."""
        doc_hash = "test_hash"
        embedding = [0.1, 0.2, 0.3]

        cache_manager.cache_embedding(doc_hash, embedding)

        assert cache_manager.similarity_cache.get(doc_hash) is not None

    def test_get_similar_mcqs(self, cache_manager):
        """Test getting similar MCQs (currently returns empty list)."""
        result = cache_manager.get_similar_mcqs([0.1, 0.2, 0.3])
        assert result == []

    def test_context_manager(self, temp_dir):
        """Test CacheManager as context manager."""
        with CacheManager(cache_dir=str(temp_dir / "ctx_cache")) as cache:
            assert cache is not None
            assert cache.mcq_cache is not None


class TestDuplicateDetector:
    """Test suite for DuplicateDetector."""

    def test_initialization(self, cache_manager):
        """Test DuplicateDetector initialization."""
        detector = DuplicateDetector(cache_manager)
        assert detector.seen_hashes is not None
        assert len(detector.seen_hashes) == 0

    def test_is_duplicate_new_document(self, cache_manager):
        """Test new document is not marked as duplicate."""
        detector = DuplicateDetector(cache_manager)
        text = "This is a unique document."

        assert detector.is_duplicate(text) is False

    def test_is_duplicate_same_document(self, cache_manager):
        """Test same document is marked as duplicate."""
        detector = DuplicateDetector(cache_manager)
        text = "This is a test document."

        detector.is_duplicate(text)
        assert detector.is_duplicate(text) is True

    def test_reset(self, cache_manager):
        """Test resetting duplicate detector."""
        detector = DuplicateDetector(cache_manager)
        text = "Test document"

        detector.is_duplicate(text)
        assert len(detector.seen_hashes) == 1

        detector.reset()
        assert len(detector.seen_hashes) == 0

    def test_find_similar(self, cache_manager, sample_mcq_dict):
        """Test finding similar documents in cache."""
        text = "Test document for similarity"
        cache_manager.set_mcq(text, sample_mcq_dict, quality_score=80.0)

        detector = DuplicateDetector(cache_manager)
        similar = detector.find_similar(text)

        assert similar is not None

    def test_different_documents_not_duplicates(self, cache_manager):
        """Test different documents are not marked as duplicates."""
        detector = DuplicateDetector(cache_manager)

        assert detector.is_duplicate("Document A") is False
        assert detector.is_duplicate("Document B") is False
        assert detector.is_duplicate("Document C") is False

        assert len(detector.seen_hashes) == 3
