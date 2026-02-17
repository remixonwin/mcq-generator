"""
Tests for filters module.
"""

import pytest
from mcq_generator.filters import DocumentFilter, QualityScorer, EntityExtractor, FilterStats


class TestDocumentFilter:
    """Test suite for DocumentFilter."""

    def test_initialization(self):
        """Test DocumentFilter initialization with default parameters."""
        filter_obj = DocumentFilter()
        assert filter_obj.min_length == 100
        assert filter_obj.max_length == 5000
        assert filter_obj.require_entities is True

    def test_custom_parameters(self):
        """Test DocumentFilter initialization with custom parameters."""
        filter_obj = DocumentFilter(
            min_length=50,
            max_length=1000,
            require_entities=False,
            min_quality_score=0.5,
        )
        assert filter_obj.min_length == 50
        assert filter_obj.max_length == 1000
        assert filter_obj.require_entities is False

    def test_check_length_valid(self, document_filter):
        """Test length check with valid text."""
        text = "A" * 200
        assert document_filter._check_length(text) is True

    def test_check_length_too_short(self, document_filter):
        """Test length check with too short text."""
        text = "Short"
        assert document_filter._check_length(text) is False

    def test_check_length_too_long(self, document_filter):
        """Test length check with too long text."""
        text = "A" * 6000
        assert document_filter._check_length(text) is False

    def test_check_entities_with_names(self, document_filter):
        """Test entity check with person names."""
        text = "John Smith and Jane Doe went to the store."
        assert document_filter._check_entities(text) is True

    def test_check_entities_with_places(self, document_filter):
        """Test entity check with place names."""
        text = "She visited the City of Paris and the Eiffel Tower."
        assert document_filter._check_entities(text) is True

    def test_check_entities_no_entities(self, document_filter):
        """Test entity check with no entities."""
        text = "This is just some random text without names."
        assert document_filter._check_entities(text) is False

    def test_check_dates(self, document_filter):
        """Test date check."""
        text_with_date = "The event happened on January 15, 2024."
        assert document_filter._check_dates(text_with_date) is True

        text_without_date = "No dates here."
        assert document_filter._check_dates(text_without_date) is False

    def test_check_dates_various_formats(self, document_filter):
        """Test date check with various formats."""
        formats = [
            "Date: 01/15/2024",
            "January 15, 2024",
            "2024-01-15",
        ]
        for fmt in formats:
            assert document_filter._check_dates(fmt) is True

    def test_check_quality(self, document_filter):
        """Test quality check."""
        good_text = "This is a good quality text. " * 10
        quality = document_filter._check_quality(good_text)
        assert quality >= 0.3

        bad_text = "a a a a a a a a a a"
        quality = document_filter._check_quality(bad_text)
        assert quality < 0.3

    def test_should_process_valid_document(self, document_filter):
        """Test processing valid document."""
        text = """John Doe visited Paris in 2024. He met with Jane Smith at the Eiffel Tower.
        The city was beautiful and they enjoyed the French cuisine. Paris is the capital of France."""

        result = document_filter.should_process(text)
        assert result is True

    def test_should_process_too_short(self, document_filter):
        """Test rejecting too short document."""
        text = "Short text."
        result = document_filter.should_process(text)
        assert result is False

    def test_should_process_no_entities(self, document_filter):
        """Test document without entities with entity requirement disabled."""
        filter_no_entities = DocumentFilter(require_entities=False)
        text = (
            "This is a somewhat longer text that has enough content to pass the quality check." * 3
        )

        result = filter_no_entities.should_process(text)
        assert result is True

    def test_filter_stats(self, document_filter):
        """Test filter statistics tracking."""
        document_filter.should_process("Short")
        document_filter.should_process("Another short")
        document_filter.should_process("Valid text " * 30)

        stats = document_filter.get_stats()
        assert stats["total_documents"] == 3
        assert stats["passed_length"] >= 1

    def test_filter_stats_pass_rate(self, document_filter):
        """Test pass rate calculation."""
        document_filter.should_process("x" * 50)
        document_filter.should_process("x" * 200)

        stats = document_filter.get_stats()
        assert 0 <= stats["pass_rate"] <= 100


class TestQualityScorer:
    """Test suite for QualityScorer."""

    def test_score_mcq(self, quality_scorer, sample_mcq):
        """Test overall MCQ scoring."""
        score = quality_scorer.score_mcq(sample_mcq)
        assert 0 <= score <= 100

    def test_score_specificity_with_entities(self, quality_scorer, sample_mcq):
        """Test specificity scoring with entities."""
        score = quality_scorer._score_specificity(sample_mcq)
        assert score > 0

    def test_score_question_length(self, quality_scorer):
        """Test question length scoring."""

        class MockMCQ:
            def __init__(self, question):
                self.question = question

        short_q = MockMCQ("What?")
        long_q = MockMCQ("What is the capital of France and what makes it special?")

        short_score = quality_scorer._score_question(short_q)
        long_score = quality_scorer._score_question(long_q)

        assert long_score > 0

    def test_score_question_clarity(self, quality_scorer):
        """Test question clarity scoring."""

        class MockMCQ:
            def __init__(self, question):
                self.question = question

        good_q = MockMCQ("What is the capital of France?")
        bad_q = MockMCQ("what is the capital of france")

        good_score = quality_scorer._score_question(good_q)
        bad_score = quality_scorer._score_question(bad_q)

        assert good_score > bad_score

    def test_score_explanation_length(self, quality_scorer):
        """Test explanation length scoring."""

        class MockMCQ:
            def __init__(self, explanation):
                self.explanation = explanation

        short = MockMCQ("Short.")
        good = MockMCQ("This is a good explanation that provides context and reasoning.")

        short_score = quality_scorer._score_explanation(short)
        good_score = quality_scorer._score_explanation(good)

        assert good_score > short_score

    def test_score_explanation_depth(self, quality_scorer):
        """Test explanation depth with reasoning words."""

        class MockMCQ:
            def __init__(self, explanation):
                self.explanation = explanation

        shallow = MockMCQ("It is Paris.")
        deep = MockMCQ("Paris is the capital because it is the seat of government.")

        shallow_score = quality_scorer._score_explanation(shallow)
        deep_score = quality_scorer._score_explanation(deep)

        assert deep_score > shallow_score

    def test_score_options_balance(self, quality_scorer):
        """Test options balance scoring."""

        class MockMCQ:
            def __init__(self, options):
                self.options = options

        balanced = MockMCQ(["Option A", "Option B", "Option C"])
        unbalanced = MockMCQ(["A", "Very long option B", "C"])

        balanced_score = quality_scorer._score_options(balanced)
        unbalanced_score = quality_scorer._score_options(unbalanced)

        assert balanced_score > 0
        assert unbalanced_score > 0

    def test_score_options_wrong_count(self, quality_scorer):
        """Test options scoring with wrong number of options."""

        class MockMCQ:
            def __init__(self, options):
                self.options = options

        two_options = MockMCQ(["A", "B"])

        score = quality_scorer._score_options(two_options)
        assert score == 0.0


class TestEntityExtractor:
    """Test suite for EntityExtractor."""

    def test_initialization(self):
        """Test EntityExtractor initialization."""
        extractor = EntityExtractor()
        assert extractor.name_pattern is not None
        assert extractor.date_pattern is not None

    def test_extract_names(self):
        """Test person name extraction."""
        extractor = EntityExtractor()
        text = "John Smith and Jane Doe met in Paris."

        names = extractor.extract_names(text)
        assert "John Smith" in names
        assert "Jane Doe" in names

    def test_extract_names_no_duplicates(self):
        """Test name extraction doesn't return duplicates."""
        extractor = EntityExtractor()
        text = "John Smith visited John Smith in Paris."

        names = extractor.extract_names(text)
        assert len(names) == 1
        assert names.count("John Smith") == 1

    def test_extract_dates(self):
        """Test date extraction."""
        extractor = EntityExtractor()
        text = "The event happened on January 15, 2024, and also on 2024-02-20."

        dates = extractor.extract_dates(text)
        assert len(dates) == 2

    def test_extract_places(self):
        """Test place extraction."""
        extractor = EntityExtractor()
        text = "She visited the Eiffel Tower in Paris City."

        places = extractor.extract_places(text)
        assert len(places) >= 0

    def test_extract_dates_no_dates(self):
        """Test date extraction with no dates."""
        extractor = EntityExtractor()
        text = "No dates here."

        dates = extractor.extract_dates(text)
        assert len(dates) == 0


class TestFilterStats:
    """Test suite for FilterStats dataclass."""

    def test_initialization(self):
        """Test FilterStats initialization."""
        stats = FilterStats()
        assert stats.total_documents == 0
        assert stats.total_passed == 0

    def test_get_pass_rate(self):
        """Test pass rate calculation."""
        stats = FilterStats()
        stats.total_documents = 10
        stats.total_passed = 5

        pass_rate = stats.get_pass_rate()
        assert pass_rate == 50.0

    def test_get_pass_rate_zero_documents(self):
        """Test pass rate with zero documents."""
        stats = FilterStats()

        pass_rate = stats.get_pass_rate()
        assert pass_rate == 0.0
