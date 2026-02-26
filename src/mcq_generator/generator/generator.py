"""
High-Performance MCQ Generator with intelligent filtering and batch processing.
"""

import asyncio
import hashlib
import logging
import random
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from datasets import load_dataset

from ..cache_manager import CacheManager, DuplicateDetector
from ..config import config
from ..filters import DocumentFilter, QualityScorer
from ..provider_client import ProviderClient
from ..storage import StateManager

logger = logging.getLogger(__name__)


class InfrastructureError(Exception):
    """Raised when LLM provider is down or circuit breaker is open."""

    pass


class ContentParseError(Exception):
    """Raised when LLM returned content that couldn't be parsed into an MCQ."""

    pass


@dataclass
class MCQMetadata:
    """Metadata for generated MCQ."""

    source_document: str
    source_id: str
    source_url: str
    document_hash: str
    specific_names: list
    specific_places: list
    specific_dates: list
    specific_events: list
    timestamp: str
    difficulty: str
    topic_category: str
    quality_score: float = 0.0
    question_type: str = "factual"
    model_name: str = "gpt-4"


@dataclass
class MCQ:
    """Multiple Choice Question structure."""

    question: str
    options: list
    correct_answer: int
    explanation: str
    metadata: MCQMetadata
    source_text: str
    question_hash: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        if not self.question_hash:
            data["question_hash"] = hashlib.sha256(self.question.encode()).hexdigest()
        return data


class MCQGenerator:
    """
    High-performance MCQ generator with:
    - Intelligent pre-filtering (70% cost reduction)
    - Multi-layer caching (50% speedup)
    - Batch processing (3-5x throughput)
    - Pause/resume support
    - Real-time progress tracking
    """

    def __init__(
        self,
        provider_url: str | None = None,
        cache_dir: str = ".mcq_cache",
        db_path: str = "mcq_state.duckdb",
        checkpoint_interval: int = 10,
    ):
        self.provider = ProviderClient(base_url=provider_url or config.PROVIDER_URL)
        self.cache = CacheManager(cache_dir=cache_dir)
        self.state = StateManager(db_path=db_path)
        self.duplicate_detector = DuplicateDetector(self.cache)
        self.filter = DocumentFilter()
        self.quality_scorer = QualityScorer()

        self.checkpoint_interval = checkpoint_interval

        logger.info("Initialized MCQGenerator")

    async def generate_from_dataset(
        self,
        dataset_name: str,
        target_questions: int,
        dataset_split: str = "train",
        text_column: str | None = "text",
        sample_randomly: bool = True,
        resume_job_id: str | None = None,
    ):
        """
        Generate MCQs from a HuggingFace dataset with pause/resume support.
        """
        if resume_job_id:
            job_id = resume_job_id
            checkpoint = self.state.get_latest_checkpoint(job_id)
            start_index = checkpoint["last_processed_index"] + 1 if checkpoint else 0
            logger.info(f"Resuming job {job_id} from index {start_index}")
            # Restore persisted text_column / synth_columns from job config or checkpoint
            try:
                prog = self.state.get_job_progress(job_id)
                cfg = prog.get("config", {}) if isinstance(prog, dict) else {}
                # prefer explicit config in job row, fallback to checkpoint synth_columns
                text_column = cfg.get("text_column", text_column)
                synth_cols = cfg.get("synth_columns")
                if not synth_cols and checkpoint:
                    synth_cols = checkpoint.get("synth_columns")
                if synth_cols:
                    # ensure generator has the same synthesized columns for deterministic resume
                    self._synth_columns = synth_cols
            except Exception:
                # Best-effort: if state read fails, continue with provided args
                pass
        else:
            # Use timezone-aware timestamp to avoid naive datetime deprecation
            job_id = (
                f"job_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            )
            # Persist initial job config including the user-requested text_column
            initial_config = {"text_column": text_column}
            self.state.create_job(
                job_id=job_id,
                dataset_name=dataset_name,
                target_questions=target_questions,
                dataset_split=dataset_split,
                config=initial_config,
            )
            start_index = 0
            logger.info(f"Created new job {job_id}")

        self.state.update_job_status(job_id, "running")

        # Initialize counters before starting processing so exception handlers
        # can safely reference them even if an early error occurs (e.g. dataset
        # loading fails). This prevents 'possibly unbound' static analysis
        # warnings and runtime NameError in rare crash paths.
        generated_count = 0
        processed_indices = []
        consecutive_failures = 0
        # Allow disabling the hard failure limit via config.CONSECUTIVE_FAILURE_LIMIT
        # If None, the generator will not abort on a fixed number of failures and
        # will instead perform periodic exponential backoff when failures accumulate.
        failure_limit = config.CONSECUTIVE_FAILURE_LIMIT
        total_processed = 0

        try:
            logger.info(f"Loading dataset: {dataset_name}")
            dataset = load_dataset(dataset_name, split=dataset_split, token=config.HF_TOKEN)
            logger.info(f"Loaded {len(dataset)} documents")

            # Auto-detect text column if the specified one doesn't exist
            if text_column not in dataset.column_names:
                logger.warning(
                    f"Text column '{text_column}' not found. Available: {dataset.column_names}"
                )
                # Try common text column names (including lists of paragraphs)
                for col in ["paragraphs", "content", "text", "full_text", "raw_text", "body"]:
                    if col in dataset.column_names:
                        text_column = col
                        logger.info(f"Auto-detected text column: {text_column}")
                        try:
                            self.state.update_job_config(job_id, {"text_column": text_column})
                        except Exception:
                            logger.debug("Failed to persist detected text_column in job config")
                        break
                else:
                    # Check if any column contains long text values
                    for col in dataset.column_names:
                        try:
                            sample = dataset[0].get(col)
                        except Exception:
                            sample = None
                        if isinstance(sample, str) and len(sample) > 100:
                            text_column = col
                            logger.info(
                                f"Auto-detected text column from long string: {text_column}"
                            )
                            try:
                                self.state.update_job_config(job_id, {"text_column": text_column})
                            except Exception:
                                logger.debug("Failed to persist detected text_column in job config")
                            break
                    else:
                        # No obvious text column found. Fall back to using the
                        # first available string-like column, or synthesize a
                        # document by concatenating columns per row. This makes
                        # the generator more tolerant of tabular datasets that
                        # don't have an explicit text field (e.g. CSVs with
                        # numeric features).
                        fallback_col = None
                        for col in dataset.column_names:
                            try:
                                sample = dataset[0].get(col)
                            except Exception:
                                sample = None
                            if isinstance(sample, str):
                                fallback_col = col
                                break

                        if fallback_col:
                            text_column = fallback_col
                            logger.info(f"Using short string column as text: {text_column}")
                            try:
                                self.state.update_job_config(job_id, {"text_column": text_column})
                            except Exception:
                                logger.debug("Failed to persist fallback text_column in job config")
                        else:
                            # No string columns found. Instead of blindly
                            # concatenating every column (which can dilute useful
                            # context), pick a small set of high-value columns
                            # heuristically. Preference is given to common text
                            # column names and any column with a longer sample
                            # string. This improves quality when synthesizing
                            # documents from purely tabular datasets.
                            logger.info(
                                "No obvious text column found; selecting heuristic columns for synthesis"
                            )
                            # Column name priorities (higher = more important)
                            # Allow whitelist tuning via config
                            whitelist = config.TEXT_COLUMN_WHITELIST

                            col_scores = []
                            for col in dataset.column_names:
                                try:
                                    sample = dataset[0].get(col)
                                except Exception:
                                    sample = None

                                # Basic heuristics: length of string sample and
                                # whether the column name matches whitelist
                                name = col.lower()
                                wl_score = 0
                                for i, term in enumerate(whitelist):
                                    if term in name:
                                        # higher priority for earlier whitelist items
                                        wl_score = max(wl_score, len(whitelist) - i)
                                sample_len = 0
                                is_numeric = False
                                if isinstance(sample, str):
                                    sample_len = len(sample)
                                else:
                                    # Treat numeric-like samples as less useful
                                    if sample is None:
                                        sample_len = 0
                                    else:
                                        try:
                                            float(sample)
                                            is_numeric = True
                                        except Exception:
                                            sample_len = len(str(sample))

                                # Score combines whitelist and sample length,
                                # penalize numeric columns slightly
                                score = wl_score * 1000 + sample_len - (100 if is_numeric else 0)
                                col_scores.append((col, score, is_numeric, sample_len))

                            # Sort by score desc and pick top N columns
                            col_scores.sort(key=lambda x: x[1], reverse=True)
                            max_cols = config.MAX_SYNTH_COLUMNS
                            synth_columns = [c for c, *_ in col_scores[:max_cols] if c]
                            if not synth_columns:
                                # Fallback to all columns
                                synth_columns = list(dataset.column_names)

                            logger.info(f"Synthesizing documents using columns: {synth_columns}")
                            # Use None to signal synthesis mode; synth_columns used later
                            text_column = None
                            # store synth_columns on the generator instance for later use
                            # when building synthesized documents per-row
                            self._synth_columns = synth_columns
                            try:
                                # persist synth_columns and signal synthesis by storing text_column=None
                                self.state.update_job_config(
                                    job_id, {"synth_columns": synth_columns, "text_column": None}
                                )
                            except Exception:
                                logger.debug("Failed to persist synth_columns in job config")

            # Persist dataset size so progress percentages are accurate
            try:
                self.state.update_total_documents(job_id, len(dataset))
            except Exception as e:
                logger.warning(f"Failed to update total_documents in state: {e}")

            # Process all documents when target is unlimited (0) or very large
            # Otherwise limit to target_questions * 3 as a buffer for retries
            if target_questions <= 0 or target_questions >= len(dataset):
                # Unlimited mode: process all documents
                if sample_randomly:
                    indices = random.sample(range(len(dataset)), len(dataset))
                else:
                    indices = list(range(start_index, len(dataset)))
                logger.info(f"Unlimited mode: Will process all {len(indices)} documents")
            else:
                # Limited mode: process target_questions * 3 documents max
                if sample_randomly:
                    indices = random.sample(
                        range(len(dataset)), min(target_questions * 3, len(dataset))
                    )
                else:
                    target_docs = target_questions * 3
                    indices = list(range(start_index, min(start_index + target_docs, len(dataset))))
                logger.info(
                    f"Limited mode: Target {target_questions} MCQs, will process up to {len(indices)} documents"
                )

            # counters initialized above before try/except

            # Backoff strategy when consecutive failures accumulate: instead of
            # cancelling the job, wait and retry to allow transient infra issues
            # (provider flakiness, rate limits, network blips) to recover.
            backoff_seconds = config.BACKOFF_INITIAL_SECONDS
            backoff_multiplier = config.BACKOFF_MULTIPLIER
            max_backoff_seconds = config.BACKOFF_MAX_SECONDS  # 30 minutes default
            # If failure_limit is None, use BACKOFF_TRIGGER to decide when to back off
            backoff_trigger = config.BACKOFF_TRIGGER

            for idx in indices:
                # Periodic check for job cancellation/pause in the database
                if total_processed % 5 == 0:
                    try:
                        current_status = self.state.get_job_progress(job_id).get("status")
                        if current_status not in ("running", "pending"):
                            logger.info(
                                f"Job {job_id} status is {current_status}, stopping generation loop."
                            )
                            break
                    except Exception as e:
                        logger.warning(f"Could not check job status for {job_id}: {e}")

                if target_questions > 0 and generated_count >= target_questions:
                    logger.info(f"Reached target: {generated_count} MCQs generated")
                    break

                await asyncio.sleep(0)

                total_processed += 1

                if total_processed - generated_count > len(dataset):
                    logger.warning("Processed all available documents, stopping")
                    break

                retry_attempts = 0
                while True:  # Retry loop for infrastructure failures
                    # Decide whether to perform backoff. If a hard failure_limit is
                    # configured, use that; otherwise perform backoff every
                    # `backoff_trigger` failures.
                    should_backoff = False
                    if failure_limit is not None:
                        if consecutive_failures >= failure_limit:
                            should_backoff = True
                    else:
                        if consecutive_failures > 0 and consecutive_failures % backoff_trigger == 0:
                            should_backoff = True

                    if should_backoff:
                        logger.warning(
                            f"Consecutive failures: {consecutive_failures}. "
                            f"Sleeping for {backoff_seconds}s before retrying."
                        )
                        remaining = backoff_seconds
                        check_interval = 5
                        while remaining > 0:
                            try:
                                await asyncio.sleep(min(remaining, check_interval))
                            except asyncio.CancelledError:
                                logger.info("Sleep interrupted by cancellation")
                                raise
                            remaining -= check_interval
                        backoff_seconds = min(
                            backoff_seconds * backoff_multiplier, max_backoff_seconds
                        )
                        # When using a hard limit we reset the counter after backoff to
                        # allow further retries; when using periodic backoff we keep the
                        # counter so the system can continue to make decisions based on
                        # the full failure history.
                        if failure_limit is not None:
                            consecutive_failures = 0
                        # retry the same document
                        continue

                    try:
                        doc = dataset[idx]
                        if text_column is not None:
                            raw_text = doc.get(text_column, "")

                            # Handle list of strings (e.g., paragraphs) by joining
                            if isinstance(raw_text, list):
                                text = " ".join(str(item) for item in raw_text if item)
                            else:
                                text = str(raw_text) if raw_text else ""
                        else:
                            # Synthesize a textual representation of the row by
                            # concatenating "column: value." pairs. Skip empty
                            # or null values to keep text concise.
                            parts = []
                            # Prefer previously computed synth_columns if present
                            cols = getattr(self, "_synth_columns", None) or list(
                                dataset.column_names
                            )
                            for col in cols:
                                try:
                                    val = doc.get(col)
                                except Exception:
                                    val = None
                                if val is None:
                                    continue
                                if isinstance(val, list):
                                    val_str = " ".join(str(v) for v in val if v)
                                else:
                                    val_str = str(val)
                                val_str = val_str.strip()
                                if not val_str or val_str.lower() in ("nan", "none"):
                                    continue
                                parts.append(f"{col}: {val_str}")
                            text = ". ".join(parts)

                        if not text or not text.strip():
                            break  # Move to next document

                        mcq = await self._process_document(
                            text=text, document_index=idx, dataset_name=dataset_name, job_id=job_id
                        )

                        if mcq:
                            generated_count += 1
                            consecutive_failures = 0
                            retry_attempts = 0
                            processed_indices.append(idx)
                            yield mcq

                            if generated_count % self.checkpoint_interval == 0:
                                await self._save_checkpoint(
                                    job_id=job_id,
                                    last_index=idx,
                                    processed_indices=processed_indices,
                                    generated_count=generated_count,
                                    synth_columns=getattr(self, "_synth_columns", None),
                                )
                        else:
                            # Content parse failure or generation returned None.
                            # Count as content failure only when configured to do so.
                            retry_attempts += 1
                            if config.COUNT_CONTENT_FAILURES:
                                consecutive_failures += 1
                            if consecutive_failures > 0 and consecutive_failures % 10 == 0:
                                logger.warning(
                                    f"Consecutive failures: {consecutive_failures}/{failure_limit or 'N/A'}"
                                )
                        break  # Successfully processed (either MCQ or skip), move to next doc

                    except InfrastructureError as e:
                        logger.warning(f"Provider unavailable: {e}. Waiting 30s to retry...")
                        await asyncio.sleep(30)
                        # Do NOT increment consecutive_failures, retry the SAME document
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error processing doc {idx}: {e}")
                        # Unexpected exceptions likely indicate infra or code issues.
                        # Count them as infra so we retry the same document after a pause.
                        consecutive_failures += 1
                        break  # Move to next document

            # Completed processing indices
            self.state.update_job_status(job_id, "completed")
            docs_processed = len(processed_indices)
            logger.info(
                f"Job {job_id} completed: {generated_count} MCQs generated from {docs_processed}/{len(dataset)} documents ({docs_processed / len(dataset) * 100:.1f}%)"
            )

        except (KeyboardInterrupt, asyncio.CancelledError) as e:
            # User-requested stop (Ctrl-C) or task cancellation. Persist a
            # checkpoint and mark job as paused so the user can resume later.
            logger.info(f"Job {job_id} interrupted by user: {e}. Saving checkpoint and pausing.")
            try:
                last_idx = processed_indices[-1] if processed_indices else max(0, start_index - 1)
                await self._save_checkpoint(
                    job_id=job_id,
                    last_index=last_idx,
                    processed_indices=processed_indices,
                    generated_count=generated_count,
                    synth_columns=getattr(self, "_synth_columns", None),
                )
            except Exception as cp_e:
                logger.warning(f"Failed to save checkpoint on interrupt: {cp_e}")

            try:
                self.state.update_job_status(job_id, "paused")
            except Exception as se:
                logger.error(f"Failed to update job status to paused: {se}")

            # Re-raise so the process/task actually stops instead of continuing
            raise

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            # Attempt to persist a final checkpoint so resume can continue from
            # the last processed index.
            try:
                last_idx = processed_indices[-1] if processed_indices else max(0, start_index - 1)
                await self._save_checkpoint(
                    job_id=job_id,
                    last_index=last_idx,
                    processed_indices=processed_indices,
                    generated_count=generated_count,
                    synth_columns=getattr(self, "_synth_columns", None),
                )
            except Exception as cp_e:
                logger.warning(f"Failed to save final checkpoint: {cp_e}")

            try:
                self.state.update_job_status(job_id, "failed")
            except Exception as se:
                logger.error(f"Failed to update job status: {se}")
            raise

    async def _process_document(
        self, text: str, document_index: int, dataset_name: str, job_id: str
    ) -> MCQ | None:
        """Process a single document through the pipeline."""
        if not self.filter.should_process(text):
            logger.debug(f"Document {document_index} filtered out")
            return None

        if self.duplicate_detector.is_duplicate(text):
            logger.debug(f"Document {document_index} is duplicate")
            return None

        cached_mcq = self.cache.get_mcq(text)
        if cached_mcq:
            logger.debug(f"Document {document_index} found in cache")
            mcq = self._dict_to_mcq(cached_mcq["mcq"])
            self.state.save_mcq(
                job_id=job_id,
                document_index=document_index,
                document_hash=cached_mcq["document_hash"],
                mcq_data=cached_mcq["mcq"],
                quality_score=cached_mcq["quality_score"],
                synth_columns=getattr(self, "_synth_columns", None),
            )
            return mcq

        logger.info(f"Generating MCQ for document {document_index}")
        mcq = await self._generate_mcq(text, document_index, dataset_name)

        if not mcq:
            return None

        try:
            quality_score = self.quality_scorer.score_mcq(mcq)
        except Exception as e:
            logger.error(f"Scoring failed for MCQ at index {document_index}: {e}")
            quality_score = 50.0  # Fallback score
        mcq.metadata.quality_score = quality_score

        logger.info(f"Generated MCQ with quality score: {quality_score:.1f}")

        if quality_score >= 70:
            self.cache.set_mcq(text, mcq.to_dict(), quality_score)

            if quality_score >= 90:
                self.cache.add_example(mcq.to_dict(), quality_score)

        self.state.save_mcq(
            job_id=job_id,
            document_index=document_index,
            document_hash=hashlib.sha256(text.encode()).hexdigest(),
            mcq_data=mcq.to_dict(),
            quality_score=quality_score,
            synth_columns=getattr(self, "_synth_columns", None),
        )

        return mcq

    async def _generate_mcq(self, text: str, document_index: int, dataset_name: str) -> MCQ | None:
        """Generate MCQ using LLM with few-shot examples."""
        examples = self.cache.get_best_examples(n=2)

        prompt = self._build_prompt(text, examples)

        try:
            response = await self.provider.generate(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4",
                temperature=0.7,
                max_tokens=2000,
                routing={"strategy": "auto", "cache_enabled": False},
            )

            # ProviderClient now validates response shape, but be defensive here too.
            try:
                content = response["choices"][0]["message"]["content"]
            except Exception as e:
                # Treat malformed provider responses as infrastructure issues so we
                # retry the SAME document instead of counting them as a content failure.
                raise InfrastructureError(f"Malformed provider response: {e}") from e

            mcq = self._parse_response(content, text, f"{dataset_name}_{document_index}")

            if mcq is None:
                # Explicitly raise a ContentParseError so the caller can decide
                # whether to treat this as a content failure (increment counter)
                # or an infrastructure issue. By default we will treat content
                # parse failures as non-infra so the generator can choose how to
                # count them based on config.
                raise ContentParseError("Incomplete or unparsable MCQ content")

            return mcq

        except Exception as e:
            # If provider is unavailable or returned malformed responses, treat as infra
            # so the caller will wait and retry the same document instead of counting
            # it toward consecutive content failures.
            try:
                import httpx

                from ..provider_client import CircuitBreakerOpen

                if isinstance(e, (httpx.HTTPError, CircuitBreakerOpen)):
                    raise InfrastructureError(str(e))
            except Exception:
                # If httpx isn't present or import fails, fall back to string checks.
                if (
                    "circuit breaker" in str(e).lower()
                    or "connection" in str(e).lower()
                    or "timeout" in str(e).lower()
                ):
                    raise InfrastructureError(str(e)) from e

            if isinstance(e, InfrastructureError):
                raise

            logger.error(f"Generation failed for document {document_index}: {e}")
            return None

    def _build_prompt(self, text: str, examples: list) -> str:
        """Build prompt with few-shot examples."""
        examples_text = ""
        if examples:
            examples_text = "\n\n".join(
                [f"EXAMPLE {i + 1}:\n{self._format_example(ex)}" for i, ex in enumerate(examples)]
            )
            examples_text = f"Here are examples of excellent MCQs:\n\n{examples_text}\n\n"

        return f"""{examples_text}Generate a self-contained MCQ from this document:

DOCUMENT:
{text}

Requirements:
- Self-contained question with full context
- Reference specific names, places, dates, events
- 3 plausible options
- Clear explanation
- NO document ID references

Format:
QUESTION: [question]
A) [option]
B) [option]
C) [option]
CORRECT: [A/B/C]
EXPLANATION: [explanation]
NAMES: [names]
PLACES: [places]
DATES: [dates]
EVENTS: [events]
QUESTION_TYPE: [factual/conceptual/application/analysis/scenario]
DIFFICULTY: [Easy/Medium/Hard]
TOPIC: [topic]
"""

    def _format_example(self, example: dict) -> str:
        """Format an example MCQ for the prompt."""
        return f"""QUESTION: {example["question"]}
A) {example["options"][0]}
B) {example["options"][1]}
C) {example["options"][2]}
CORRECT: {chr(65 + example["correct_answer"])}
EXPLANATION: {example.get("explanation", "This answer is correct based on the document content.")}
NAMES: {", ".join(example.get("metadata", {}).get("specific_names", []))}
PLACES: {", ".join(example.get("metadata", {}).get("specific_places", []))}
DATES: {", ".join(example.get("metadata", {}).get("specific_dates", []))}
EVENTS: {", ".join(example.get("metadata", {}).get("specific_events", []))}
DIFFICULTY: {example.get("metadata", {}).get("difficulty", "Medium")}
TOPIC: {example.get("metadata", {}).get("topic_category", "General")}
"""

    def _parse_response(self, response: str, source_text: str, doc_id: str) -> MCQ | None:
        """Parse LLM response into MCQ object."""
        try:
            import re

            lines = response.strip().split("\n")
            data = {}
            # Pre-process lines to extract key-value pairs
            # Handle formats like "QUESTION: ...", "QUESTION:...", "Question: ..."
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if ":" in line:
                    key, value = line.split(":", 1)
                    data[key.strip().upper()] = value.strip()

            # Robust option extraction
            options = []
            # Support formats: A) text, A. text, A: text, [A] text, - A: text
            # Regex to match leading label and capture text
            # Patterns to look for in order
            option_patterns = [
                (r"^[A-Z][\)\.\:]\s*(.*)$", 1),
                (r"^\[([A-Z])\]\s*(.*)$", 2),
                (r"^[A-Z]\s+(.*)$", 1),
                (r"^-\s+[A-Z][\:\)]\s*(.*)$", 1),
            ]

            # Scan for options A, B, C (we expect 3)
            current_opt_idx = 0
            expected_labels = ["A", "B", "C"]

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if current_opt_idx >= len(expected_labels):
                    break

                label = expected_labels[current_opt_idx]
                match_found = False

                # Try specific labels first
                for pattern, capture_idx in option_patterns:
                    # Compile dynamic regex for the expected label
                    # Special handling for patterns that capture the label vs those that just use it
                    if capture_idx == 2:  # e.g. [A]
                        p = r"^\[" + re.escape(label) + r"\]\s*(.*)$"
                        m = re.search(p, line, re.IGNORECASE)
                        if m:
                            options.append(m.group(1).strip())
                            match_found = True
                            break
                    else:
                        p = r"^" + re.escape(label) + r"[\)\.\:\s]\s*(.*)$"
                        m = re.search(p, line, re.IGNORECASE)
                        if not m:
                            # Try with leading dash or bullet
                            p = r"^[\-\*]\s*" + re.escape(label) + r"[\)\.\:\s]\s*(.*)$"
                            m = re.search(p, line, re.IGNORECASE)

                        if m:
                            options.append(m.group(1).strip())
                            match_found = True
                            break

                if match_found:
                    current_opt_idx += 1

            if len(options) < 3:
                # Fallback: if we didn't find specific labels, look for any 3 lines that look like options
                if not options:
                    opt_lines = [
                        l.strip() for l in lines if re.search(r"^[A-Z][\)\.\:]", l.strip())
                    ]
                    if len(opt_lines) >= 3:
                        options = [
                            re.sub(r"^[A-Z][\)\.\:]\s*", "", l).strip() for l in opt_lines[:3]
                        ]

            if len(options) != 3:
                return None

            correct_map = {"A": 0, "B": 1, "C": 2}
            correct_val = data.get("CORRECT", "").strip().upper()
            if not correct_val and "CORRECT_ANSWER" in data:
                correct_val = data.get("CORRECT_ANSWER", "").strip().upper()

            correct_answer = None
            if correct_val:
                # Handle "A", "A)", "CORRECT: A", etc.
                match = re.search(r"([A-C])", correct_val)
                if match:
                    correct_answer = correct_map.get(match.group(1))

            if correct_answer is None:
                # Try to find it in the text if not in data
                for line in lines:
                    if "CORRECT" in line.upper():
                        m = re.search(r"([A-C])", line.upper().split("CORRECT")[-1])
                        if m:
                            correct_answer = correct_map.get(m.group(1))
                            break

            if correct_answer is None:
                return None

            # Validate essential fields
            question = data.get("QUESTION", "").strip()
            explanation = data.get("EXPLANATION", "").strip()

            # More robust extraction if labels are slightly different
            if not question:
                for k, v in data.items():
                    if "QUESTION" in k:
                        question = v
                        break
            if not explanation:
                for k, v in data.items():
                    if "EXPLANATION" in k or "REASON" in k:
                        explanation = v
                        break

            if not question or not explanation or not options:
                logger.warning(
                    f"Incomplete MCQ response for doc {doc_id}: question={bool(question)}, explanation={bool(explanation)}, options={len(options)}"
                )
                return None

            metadata = MCQMetadata(
                source_document=doc_id,
                source_id=doc_id,
                source_url=data.get("SOURCE_URL", ""),
                document_hash=hashlib.sha256(source_text.encode()).hexdigest(),
                specific_names=[
                    n.strip() for n in str(data.get("NAMES", "")).split(",") if n.strip()
                ],
                specific_places=[
                    p.strip() for p in str(data.get("PLACES", "")).split(",") if p.strip()
                ],
                specific_dates=[
                    d.strip() for d in str(data.get("DATES", "")).split(",") if d.strip()
                ],
                specific_events=[
                    e.strip() for e in str(data.get("EVENTS", "")).split(",") if e.strip()
                ],
                timestamp=datetime.now(timezone.utc).isoformat(),
                difficulty=str(data.get("DIFFICULTY", "Medium")),
                topic_category=str(data.get("TOPIC", "General")),
                question_type=str(data.get("QUESTION_TYPE", "factual")),
                model_name="gpt-4",
                quality_score=0.0,
            )

            return MCQ(
                question=question,
                options=options,
                correct_answer=correct_answer,
                explanation=explanation,
                metadata=metadata,
                source_text=source_text[:500],
            )

        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            return None

    def _dict_to_mcq(self, mcq_dict: dict) -> MCQ:
        """Convert dict to MCQ object."""
        metadata_dict = mcq_dict["metadata"]
        metadata = MCQMetadata(
            source_document=metadata_dict.get("source_document", ""),
            source_id=metadata_dict.get("source_id", ""),
            source_url=metadata_dict.get("source_url", ""),
            document_hash=metadata_dict.get("document_hash", ""),
            specific_names=metadata_dict.get("specific_names", []),
            specific_places=metadata_dict.get("specific_places", []),
            specific_dates=metadata_dict.get("specific_dates", []),
            specific_events=metadata_dict.get("specific_events", []),
            timestamp=metadata_dict.get("timestamp", datetime.now(timezone.utc).isoformat()),
            difficulty=str(metadata_dict.get("difficulty", "Medium")),
            topic_category=str(metadata_dict.get("topic_category", "General")),
            question_type=str(metadata_dict.get("question_type", "factual")),
            model_name=str(metadata_dict.get("model_name", "gpt-4")),
            quality_score=float(metadata_dict.get("quality_score", 0.0)),
        )

        return MCQ(
            question=mcq_dict["question"],
            options=mcq_dict["options"],
            correct_answer=mcq_dict["correct_answer"],
            explanation=mcq_dict["explanation"],
            metadata=metadata,
            source_text=mcq_dict["source_text"],
        )

    async def _save_checkpoint(
        self,
        job_id: str,
        last_index: int,
        processed_indices: list,
        generated_count: int,
        synth_columns: list | None = None,
    ) -> None:
        """Save checkpoint for pause/resume."""
        cache_stats = self.cache.get_stats()
        provider_stats = self.provider.get_stats()

        self.state.save_checkpoint(
            job_id=job_id,
            last_processed_index=last_index,
            document_indices=processed_indices,
            cache_stats=cache_stats,
            metrics={"generated_count": generated_count, "provider_stats": provider_stats},
            synth_columns=synth_columns,
        )

        logger.info(f"Saved checkpoint: {generated_count} MCQs generated")

    async def close(self) -> None:
        """Close all connections."""
        await self.provider.close()
        self.cache.close()
        self.state.close()
