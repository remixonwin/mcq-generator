"""
Dataset router.

Handles dataset search endpoints, providing access to HuggingFace Hub datasets.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, Query

from ...metrics import api_requests
from ..dependencies import get_api_key_optional
from ..schemas import DatasetSearchResponse, ErrorResponse
from ..services import DatasetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets")


class RecommendDatasetResponse(BaseModel):
    """Response for dataset recommendation."""

    dataset: str
    text_column: str
    confidence: float
    reason: str


# Topic clusters - keywords that map to the same domain
TOPIC_CLUSTERS = {
    "medical": {
        "keywords": [
            "medical",
            "medicine",
            "health",
            "disease",
            "doctor",
            "hospital",
            "patient",
            "clinical",
            "anatomy",
            "physiology",
            "pharma",
            "drug",
            "treatment",
            "diagnosis",
            "symptom",
        ],
        "dataset": "openlifescienceai/medmcqa",
        "text_column": "question",
        "has_mcq": True,
        "confidence": 0.95,
    },
    "biology": {
        "keywords": [
            "biology",
            "bio",
            "cell",
            "dna",
            "gene",
            "evolution",
            "organism",
            "species",
            "ecology",
            "photosynthesis",
            "mitochondria",
            "protein",
            "enzyme",
            "microscope",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.85,
    },
    "physics": {
        "keywords": [
            "physics",
            "quantum",
            "thermodynamics",
            "electromagnetism",
            "gravity",
            "newton",
            "einstein",
            "relativity",
            "particle",
            "atom",
            "nuclear",
            "energy",
            "force",
            "motion",
            "wave",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.85,
    },
    "chemistry": {
        "keywords": [
            "chemistry",
            "chemical",
            "molecule",
            "atom",
            "bond",
            "reaction",
            "acid",
            "base",
            "organic",
            "inorganic",
            "periodic",
            "element",
            "compound",
            "solution",
            "gas",
            "liquid",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.85,
    },
    "math": {
        "keywords": [
            "math",
            "mathematics",
            "algebra",
            "geometry",
            "calculus",
            "statistics",
            "probability",
            "equation",
            "theorem",
            "formula",
            "number",
            "matrix",
            "vector",
            "trigonometry",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.85,
    },
    "technology": {
        "keywords": [
            "technology",
            "tech",
            "computer",
            "software",
            "hardware",
            "internet",
            "ai",
            "artificial intelligence",
            "machine learning",
            "ml",
            "deep learning",
            "robotics",
            "automation",
            "digital",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.80,
    },
    "programming": {
        "keywords": [
            "programming",
            "code",
            "coding",
            "developer",
            "software",
            "python",
            "javascript",
            "java",
            "c++",
            "algorithm",
            "database",
            "web",
            "api",
            "backend",
            "frontend",
            "debug",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.80,
    },
    "history": {
        "keywords": [
            "history",
            "historical",
            "war",
            "ancient",
            "medieval",
            "century",
            "empire",
            "civilization",
            "revolution",
            "king",
            "queen",
            "president",
            "battle",
            "treaty",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.90,
    },
    "geography": {
        "keywords": [
            "geography",
            "country",
            "city",
            "capital",
            "continent",
            "ocean",
            "river",
            "mountain",
            "island",
            "climate",
            "population",
            "region",
            "border",
            "map",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.85,
    },
    "literature": {
        "keywords": [
            "literature",
            "book",
            "author",
            "poem",
            "poetry",
            "novel",
            "story",
            "writing",
            "shakespeare",
            "literary",
            "fiction",
            "non-fiction",
            "essay",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.80,
    },
    "music": {
        "keywords": [
            "music",
            "song",
            "album",
            "artist",
            "band",
            "musician",
            "classical",
            "jazz",
            "rock",
            "pop",
            "concert",
            "instrument",
            "piano",
            "guitar",
            "orchestra",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.80,
    },
    "movies": {
        "keywords": [
            "movie",
            "film",
            "cinema",
            "actor",
            "actress",
            "director",
            "hollywood",
            "oscar",
            "academy",
            "screen",
            "scene",
            "script",
            "trailer",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.80,
    },
    "sports": {
        "keywords": [
            "sport",
            "football",
            "basketball",
            "soccer",
            "baseball",
            "tennis",
            "golf",
            "olympic",
            "championship",
            "player",
            "team",
            "score",
            "match",
            "tournament",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.80,
    },
    "law": {
        "keywords": [
            "law",
            "legal",
            "court",
            "judge",
            "lawyer",
            "attorney",
            "crime",
            "criminal",
            "civil",
            "constitution",
            "statute",
            "contract",
            "rights",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.75,
    },
    "trivia": {
        "keywords": [
            "trivia",
            "quiz",
            "fact",
            "knowledge",
            "general knowledge",
            "question",
            "answer",
            "fun",
            "interesting",
        ],
        "dataset": "mandarjoshi/trivia_qa",
        "text_column": "question",
        "has_mcq": False,
        "confidence": 0.90,
    },
    "science": {
        "keywords": [
            "science",
            "scientific",
            "experiment",
            "research",
            "scientist",
            "discovery",
            "theory",
            "hypothesis",
            "laboratory",
            "scientific method",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.80,
    },
}

# Default fallback
DEFAULT_DATASET = {
    "dataset": "squad",
    "text_column": "context",
    "confidence": 0.60,
}


def calculate_keyword_score(query: str, keywords: list[str]) -> float:
    """Calculate how well a query matches a set of keywords."""
    query_lower = query.lower()
    query_words = set(re.findall(r"\w+", query_lower))

    score = 0.0
    for keyword in keywords:
        keyword_lower = keyword.lower()
        keyword_words = set(re.findall(r"\w+", keyword_lower))

        # Exact keyword match
        if keyword_lower in query_lower:
            score += 1.0
        # Partial match (keyword contains query or vice versa)
        elif any(
            w in keyword_lower or kw in query_lower for w in query_words for kw in keyword_words
        ):
            if keyword_words & query_words:  # intersection
                score += 0.5 * len(keyword_words & query_words)

    return score


def find_best_topic_cluster(query: str) -> tuple[dict, float]:
    """Find the best matching topic cluster for a query."""
    query_lower = query.lower()
    best_cluster = None
    best_score = 0.0

    for topic_name, cluster in TOPIC_CLUSTERS.items():
        score = calculate_keyword_score(query_lower, cluster["keywords"])
        if score > best_score:
            best_score = score
            best_cluster = {**cluster, "topic": topic_name}

    return best_cluster, best_score


@router.get(
    "/search",
    response_model=DatasetSearchResponse,
    summary="Search datasets",
    description="Search for datasets on HuggingFace Hub.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid search parameters"},
    },
)
def search_datasets_endpoint(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    sort: str = Query("downloads", pattern="^(downloads|likes|trending)$"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    api_key: str | None = Depends(get_api_key_optional),
) -> DatasetSearchResponse:
    """Search for datasets on HuggingFace Hub."""
    api_requests.labels(path="/api/v1/datasets/search").inc()

    service = DatasetService()
    result = service.search(query=q, limit=limit, sort=sort, offset=offset)

    return DatasetSearchResponse(**result)


@router.get(
    "/recommend",
    response_model=RecommendDatasetResponse,
    summary="Recommend best dataset",
    description="Intelligently recommend the best dataset based on keyword.",
)
def recommend_dataset(
    q: str = Query(..., min_length=1, description="Search keyword"),
    api_key: str | None = Depends(get_api_key_optional),
) -> RecommendDatasetResponse:
    """Recommend the best dataset for a given keyword."""
    logger.info(f"Recommending dataset for query: {q}")

    # Use keyword matching to find best topic cluster
    cluster, score = find_best_topic_cluster(q)

    if score > 0:
        confidence = min(cluster["confidence"], 0.5 + score * 0.1)
        logger.info(
            f"Matched topic: {cluster['topic']} with score {score}, confidence {confidence}"
        )
        return RecommendDatasetResponse(
            dataset=cluster["dataset"],
            text_column=cluster["text_column"],
            confidence=confidence,
            reason=f"Matched topic: {cluster['topic']}",
        )

    # No match found - use default but with lower confidence
    logger.info(f"No topic match found, using default dataset")
    return RecommendDatasetResponse(
        dataset=DEFAULT_DATASET["dataset"],
        text_column=DEFAULT_DATASET["text_column"],
        confidence=DEFAULT_DATASET["confidence"],
        reason="Using general purpose dataset (no specific topic match)",
    )
