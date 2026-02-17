"""
Document filters and quality scoring for intelligent pre-processing.
"""

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FilterStats:
    """Statistics for filtering."""

    total_documents: int = 0
    passed_length_check: int = 0
    passed_entity_check: int = 0
    passed_date_check: int = 0
    passed_quality_check: int = 0
    total_passed: int = 0

    def get_pass_rate(self) -> float:
        """Calculate overall pass rate."""
        return (self.total_passed / self.total_documents * 100) if self.total_documents > 0 else 0.0


class DocumentFilter:
    """
    Multi-stage document filter to reduce LLM calls by 70-80%.
    """

    def __init__(
        self,
        min_length: int = 100,
        max_length: int = 5000,
        require_entities: bool = True,
        require_dates: bool = False,
        min_quality_score: float = 0.3,
    ):
        self.min_length = min_length
        self.max_length = max_length
        self.require_entities = require_entities
        self.require_dates = require_dates
        self.min_quality_score = min_quality_score

        self.stats = FilterStats()

        self.name_pattern = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b")

        self.date_pattern = re.compile(
            r"\b(?:"
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}|"
            r"\d{4}-\d{2}-\d{2}"
            r")\b",
            re.IGNORECASE,
        )

        self.place_indicators = [
            "in",
            "at",
            "from",
            "to",
            "near",
            "located",
            "City",
            "Island",
            "Beach",
            "Street",
            "Avenue",
            "Airport",
            "Building",
            "Hotel",
            "Office",
        ]

    def should_process(self, text: str) -> bool:
        """Determine if a document should be processed."""
        self.stats.total_documents += 1

        if not self._check_length(text):
            return False
        self.stats.passed_length_check += 1

        if self.require_entities and not self._check_entities(text):
            return False
        self.stats.passed_entity_check += 1

        if self.require_dates and not self._check_dates(text):
            return False
        self.stats.passed_date_check += 1

        if not self._check_quality(text):
            return False
        self.stats.passed_quality_check += 1

        self.stats.total_passed += 1
        return True

    def _check_length(self, text: str) -> bool:
        """Check if text length is within bounds."""
        length = len(text.strip())
        return self.min_length <= length <= self.max_length

    def _check_entities(self, text: str) -> bool:
        """Check if text contains entities (names, places)."""
        has_names = len(self.name_pattern.findall(text)) >= 2

        has_places = any(indicator in text for indicator in self.place_indicators)

        return has_names or has_places

    def _check_dates(self, text: str) -> bool:
        """Check if text contains dates."""
        return bool(self.date_pattern.search(text))

    def _check_quality(self, text: str) -> bool:
        """Calculate document quality score."""
        words = text.split()

        if not words:
            return False

        unique_ratio = len(set(words)) / len(words)

        sentences = text.count(".") + text.count("!") + text.count("?")
        avg_words_per_sentence = len(words) / max(sentences, 1)

        quality = (
            unique_ratio * 0.5
            + min(avg_words_per_sentence / 20, 1.0) * 0.3
            + min(sentences / 10, 1.0) * 0.2
        )

        return float(quality) >= self.min_quality_score

    def get_stats(self) -> dict:
        """Get filtering statistics."""
        return {
            "total_documents": self.stats.total_documents,
            "passed_length": self.stats.passed_length_check,
            "passed_entities": self.stats.passed_entity_check,
            "passed_dates": self.stats.passed_date_check,
            "passed_quality": self.stats.passed_quality_check,
            "total_passed": self.stats.total_passed,
            "pass_rate": self.stats.get_pass_rate(),
        }


class QualityScorer:
    """
    Score the quality of generated MCQs.
    """

    def score_mcq(self, mcq) -> float:
        """Calculate quality score for an MCQ."""
        score = 0.0

        score += self._score_specificity(mcq) * 0.4
        score += self._score_question(mcq) * 0.3
        score += self._score_explanation(mcq) * 0.2
        score += self._score_options(mcq) * 0.1

        return min(100, score)

    def _score_specificity(self, mcq) -> float:
        """Score based on specific entities mentioned (0-100)."""
        score = 0.0

        score += min(25, len(mcq.metadata.specific_names) * 5)
        score += min(25, len(mcq.metadata.specific_places) * 5)
        score += min(25, len(mcq.metadata.specific_dates) * 5)
        score += min(25, len(mcq.metadata.specific_events) * 5)

        return score

    def _score_question(self, mcq) -> float:
        """Score question quality (0-100)."""
        question = mcq.question

        length_score = 0.0
        length = len(question)
        if 80 <= length <= 200:
            length_score = 100
        elif length < 80:
            length_score = length / 80 * 100
        else:
            length_score = max(0, 100 - (length - 200) / 3)

        clarity_score = 0.0
        if question:
            if question.endswith("?"):
                clarity_score += 50
            if question[0].isupper():
                clarity_score += 50

        return length_score * 0.7 + clarity_score * 0.3

    def _score_explanation(self, mcq) -> float:
        """Score explanation quality (0-100)."""
        explanation = mcq.explanation

        length = len(explanation)
        length_score = 0.0
        if 100 <= length <= 300:
            length_score = 100
        elif length < 100:
            length_score = length / 100 * 100
        else:
            length_score = max(0, 100 - (length - 300) / 5)

        reasoning_words = ["because", "since", "therefore", "thus", "as", "shows", "indicates"]
        depth_score = 0.0
        for word in reasoning_words:
            if word in explanation.lower():
                depth_score += 20
        depth_score = min(100, depth_score)

        return length_score * 0.6 + depth_score * 0.4

    def _score_options(self, mcq) -> float:
        """Score option quality (0-100)."""
        options = mcq.options

        if len(options) != 3:
            return 0.0

        lengths = [len(opt) for opt in options]
        avg_length = sum(lengths) / 3
        variance = sum((l - avg_length) ** 2 for l in lengths) / 3
        balance_score = max(0, 100 - variance * 2)

        nontrivial_score = sum(100 if len(opt) > 10 else 0 for opt in options) / 3

        return balance_score * 0.6 + nontrivial_score * 0.4


class EntityExtractor:
    """Extract entities from text for metadata enrichment."""

    def __init__(self):
        self.name_pattern = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b")
        self.date_pattern = re.compile(
            r"\b(?:"
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}|"
            r"\d{4}-\d{2}-\d{2}"
            r")\b",
            re.IGNORECASE,
        )

    def extract_names(self, text: str) -> list:
        """Extract person names."""
        return list(set(self.name_pattern.findall(text)))

    def extract_dates(self, text: str) -> list:
        """Extract dates."""
        return list(set(self.date_pattern.findall(text)))

    def extract_places(self, text: str) -> list:
        """Extract place names (simplified)."""
        place_indicators = ["City", "Island", "Beach", "Street", "Avenue", "Airport", "Building"]
        places = []

        for indicator in place_indicators:
            pattern = re.compile(rf"\b\w+\s+{indicator}\b")
            places.extend(pattern.findall(text))

        return list(set(places))
