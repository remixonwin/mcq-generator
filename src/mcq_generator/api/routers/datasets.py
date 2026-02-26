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
    "news": {
        "keywords": [
            "news",
            "current events",
            "epstein",
            "politics",
            "election",
            "government",
            "president",
            "minister",
            "scandal",
            "breaking",
            "headline",
            "article",
            "report",
            "journalism",
        ],
        "dataset": "fancyzhx/ag_news",
        "text_column": "text",
        "has_mcq": False,
        "confidence": 0.85,
    },
    "crime": {
        "keywords": [
            "crime",
            "criminal",
            "trial",
            "case",
            "investigation",
            "fraud",
            "murder",
            "justice",
            "court",
            "verdict",
            "prosecution",
            "defense",
        ],
        "dataset": "squad",
        "text_column": "context",
        "has_mcq": False,
        "confidence": 0.75,
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
    description="Search HuggingFace Hub for the most relevant dataset based on keyword.",
)
def recommend_dataset(
    q: str = Query(..., min_length=1, description="Search keyword"),
    api_key: str | None = Depends(get_api_key_optional),
) -> RecommendDatasetResponse:
    """Recommend the best dataset for a given keyword by searching HuggingFace."""
    logger.info(f"Recommending dataset for query: {q}")

    # ALWAYS search HuggingFace for relevant datasets based on keyword
    try:
        from ..services import DatasetService

        service = DatasetService()

        # Search with the keyword to find relevant datasets
        search_results = service.search(query=q, limit=10, sort="downloads")

        # Check both 'datasets' and 'results' keys
        raw_results = search_results.get("datasets") or search_results.get("results") or []

        # Convert to list of dicts if needed (handle both dict and object formats)
        results = []
        for item in raw_results:
            if hasattr(item, "model_dump"):  # Pydantic model
                results.append(item.model_dump())
            elif hasattr(item, "dict"):  # Old Pydantic
                results.append(item.dict())
            elif isinstance(item, dict):
                results.append(item)
            else:
                # Assume it's a dataset object with attributes - use getattr
                results.append(
                    {
                        "id": getattr(item, "id", str(item)),
                        "downloads": getattr(item, "downloads", 0),
                        "name": getattr(item, "name", str(item)),
                    }
                )

        if results:
            # First check for generic/known working datasets as fallback
            known_datasets = {
                "squad": {"dataset": "squad", "text_column": "context"},
                "ag_news": {"dataset": "fancyzhx/ag_news", "text_column": "text"},
                "trivia_qa": {"dataset": "mandarjoshi/trivia_qa", "text_column": "question"},
            }

            # For generic keywords, use known working datasets
            generic_keywords = [
                "science",
                "history",
                "geography",
                "biology",
                "physics",
                "math",
                "general",
                "trivia",
                "quiz",
            ]
            if q_lower in generic_keywords:
                if q_lower in known_datasets:
                    return RecommendDatasetResponse(
                        dataset=known_datasets[q_lower]["dataset"],
                        text_column=known_datasets[q_lower]["text_column"],
                        confidence=0.9,
                        reason=f"Using known working dataset for: {q}",
                    )
                # Default to ag_news for generic
                return RecommendDatasetResponse(
                    dataset="fancyzhx/ag_news",
                    text_column="text",
                    confidence=0.8,
                    reason=f"Using news dataset for general topic: {q}",
                )

            # Find the best suitable dataset - prefer text/email/document datasets for specific topics
            # First check if the keyword appears in the dataset name (for specific topics like "epstein")
            q_lower = q.lower()

            logger.info(f"Processing {len(results)} search results for query: {q}")

            # Look for datasets where the keyword is in the name (for specific topics)
            for i, dataset_info in enumerate(results):
                dataset_name = dataset_info.get("id") or dataset_info.get("name", "")
                downloads = dataset_info.get("downloads", 0)

                if not dataset_name:
                    continue

                # Skip non-text datasets
                skip_patterns = [
                    "image",
                    "img",
                    "photo",
                    "embed",
                    "embedding",
                    "eval",
                    "benchmark",
                    "test",
                    "-code",
                    "coco",
                    "voc",
                    "clip",
                    "vision",
                    "audio",
                    "speech",
                    "voice",
                    "video",
                ]
                dataset_lower = dataset_name.lower()
                should_skip = any(skip in dataset_lower for skip in skip_patterns)

                logger.info(
                    f"Dataset {i}: {dataset_name} (skip={should_skip}, patterns={[s for s in skip_patterns if s in dataset_lower]})"
                )

                if should_skip:
                    continue

                # Check if keyword is in dataset name (for specific topics like epstein)
                if q_lower in dataset_name.lower():
                    # Check if it's a QA dataset
                    if any(
                        kw in dataset_name.lower()
                        for kw in ["qa", "question", "quiz", "mcq", "trivia"]
                    ):
                        return RecommendDatasetResponse(
                            dataset=dataset_name,
                            text_column="question",
                            confidence=min(0.95, 0.7 + (downloads / 100000)),
                            reason=f"Found relevant dataset: {dataset_name}",
                        )
                    # For text/email/document datasets
                    return RecommendDatasetResponse(
                        dataset=dataset_name,
                        text_column="text",
                        confidence=min(0.9, 0.6 + (downloads / 100000)),
                        reason=f"Found relevant dataset: {dataset_name}",
                    )
                    # For text/email/document datasets
                    return RecommendDatasetResponse(
                        dataset=dataset_name,
                        text_column="text",
                        confidence=min(0.9, 0.6 + (downloads / 100000)),
                        reason=f"Found relevant dataset: {dataset_name}",
                    )

            # If no keyword match, find best general dataset
            for dataset_info in results:
                dataset_name = dataset_info.get("id") or dataset_info.get("name", "")
                downloads = dataset_info.get("downloads", 0)

                if not dataset_name:
                    continue

                # Skip non-text datasets
                skip_patterns = [
                    "image",
                    "img",
                    "embed",
                    "eval",
                    "benchmark",
                    "test",
                    "-code",
                    "coco",
                    "voc",
                    "clip",
                    "vision",
                    "audio",
                    "speech",
                    "video",
                    "photo",
                ]
                if any(skip in dataset_name.lower() for skip in skip_patterns):
                    continue

                # Check if it's a QA/MCQ dataset
                if any(
                    kw in dataset_name.lower() for kw in ["qa", "question", "quiz", "mcq", "trivia"]
                ):
                    return RecommendDatasetResponse(
                        dataset=dataset_name,
                        text_column="question",
                        confidence=min(0.9, 0.5 + (downloads / 100000)),
                        reason=f"Found QA dataset: {dataset_name}",
                    )

            # For the first suitable text dataset
            first_valid = results[0]
            dataset_name = first_valid.get("id") or first_valid.get("name", "squad")
            downloads = first_valid.get("downloads", 0)

            return RecommendDatasetResponse(
                dataset=dataset_name,
                text_column="text",
                confidence=min(0.8, 0.4 + (downloads / 200000)),
                reason=f"Found dataset: {dataset_name}",
            )

            # For the first suitable text dataset, use 'text' or 'content' column
            first_valid = results[0]
            dataset_name = first_valid.get("id") or first_valid.get("name", "squad")
            downloads = first_valid.get("downloads", 0)

            return RecommendDatasetResponse(
                dataset=dataset_name,
                text_column="text",  # Default text column for most datasets
                confidence=min(0.8, 0.4 + (downloads / 200000)),
                reason=f"Found dataset via HuggingFace search: {dataset_name} ({downloads} downloads)",
            )

    except Exception as e:
        logger.warning(f"HuggingFace search failed: {e}")

    # Ultimate fallback only if HF search fails completely
    logger.warning(f"HF search failed, using default dataset")
    return RecommendDatasetResponse(
        dataset=DEFAULT_DATASET["dataset"],
        text_column=DEFAULT_DATASET["text_column"],
        confidence=0.3,
        reason="Using default dataset (search unavailable)",
    )
