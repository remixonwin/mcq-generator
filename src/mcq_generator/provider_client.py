"""
HTTP client for LLM Provider with retry logic, circuit breaker, and connection pooling.
"""

import httpx
import logging
from typing import Optional
from pathlib import Path
import traceback

from . import provider_adapters
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import asyncio
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""

    pass


class InvalidProviderResponse(Exception):
    """Provider returned a syntactically valid HTTP response but missing expected fields."""

    pass


class ProviderClient:
    """
    Async HTTP client for the LLM Provider microservice.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:7543",
        timeout: float = 30.0,
        max_connections: int = 10,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")

        # Optional HTTP/2 support
        try:
            import h2

            http2_support = True
        except ImportError:
            http2_support = False
            logger.warning("h2 package not found, HTTP/2 support disabled")

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            limits=httpx.Limits(
                max_connections=max_connections, max_keepalive_connections=max_connections
            ),
            http2=http2_support,
        )

        self.circuit_state = "closed"
        self.failure_count = 0
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self.circuit_opened_at: Optional[datetime] = None

        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

        logger.info(f"Initialized ProviderClient: {self.base_url}")

    async def health_check(self) -> bool:
        """Check if the provider service is healthy."""
        try:
            response = await self.client.get("/health", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    async def generate(
        self,
        messages: list[dict],
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        routing: Optional[dict] = None,
        quality: Optional[dict] = None,
        **kwargs,
    ) -> dict:
        """Generate completion from the provider."""
        self._check_circuit_breaker()

        request_data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
            "routing": routing,
            "quality": quality,
            **kwargs,
        }

        if max_tokens:
            request_data["max_tokens"] = max_tokens

        self.total_requests += 1

        try:
            response = await self.client.post("/v1/chat/completions", json=request_data)

            response.raise_for_status()

            resp_json = response.json()

            # Give provider adapters an early chance to normalize deep/nested shapes
            try:
                resp_json = provider_adapters.adapt(resp_json, request_data=request_data)
            except Exception as e:
                logger.debug(f"Provider adapter early-adapt failed: {e}")

            # Log raw body for easier debugging (debug-level)
            try:
                logger.debug(f"Provider raw body: {response.text}")
            except Exception:
                pass

            # Normalize a few common provider response shapes into the canonical
            # {'choices': [{ 'message': {'content': ...}, ... }, ...]} shape the
            # rest of the generator expects.
            #  - Some providers return a top-level list
            #  - Some wrap the result under a 'response' key
            #  - Some use 'outputs' or other keys
            if isinstance(resp_json, list) and resp_json and isinstance(resp_json[0], dict):
                resp_json = {"choices": resp_json}

            # If provider nested response (e.g. {"response": {...}}) extract choices
            if isinstance(resp_json, dict) and "choices" not in resp_json:
                # common nested keys that may contain choices
                for candidate_key in ("response", "result", "outputs", "output", "body", "payload"):
                    if candidate_key in resp_json:
                        candidate = resp_json[candidate_key]
                        if isinstance(candidate, dict) and "choices" in candidate:
                            resp_json = {"choices": candidate["choices"]}
                            break
                        if isinstance(candidate, list):
                            resp_json = {"choices": candidate}
                            break

            # At this point we should have a 'choices' list; attempt to normalize
            # each choice so callers can safely read message->content.
            if isinstance(resp_json, dict) and "choices" in resp_json:
                choices = resp_json["choices"]
                normalized = []
                for ch in choices:
                    # If it's already the expected dict with message.content, keep it
                    if isinstance(ch, dict):
                        if "message" in ch and isinstance(ch["message"], dict):
                            normalized.append(ch)
                            continue

                        # Common alt shapes -> {"text": "..."}
                        if "text" in ch and isinstance(ch["text"], str):
                            new = {**ch}
                            text = new.pop("text")
                            new.setdefault("message", {})["content"] = text
                            normalized.append(new)
                            continue

                        # Some providers put content at top-level 'content'
                        if "content" in ch and isinstance(ch["content"], str):
                            new = {**ch}
                            content = new.pop("content")
                            new.setdefault("message", {})["content"] = content
                            normalized.append(new)
                            continue

                        # Streaming chunk shape: {'delta': {'content': '...'}}
                        if (
                            "delta" in ch
                            and isinstance(ch["delta"], dict)
                            and "content" in ch["delta"]
                        ):
                            new = {**ch}
                            content = new.pop("delta")["content"]
                            new.setdefault("message", {})["content"] = content
                            normalized.append(new)
                            continue

                        # Fallback: keep dict but ensure message.content exists (may be empty)
                        new = {**ch}
                        if "message" not in new:
                            new["message"] = {"content": ""}
                        normalized.append(new)
                    elif isinstance(ch, str):
                        # Plain string choice -> wrap
                        normalized.append({"message": {"content": ch}})
                    else:
                        # Unknown type -> stringify
                        normalized.append({"message": {"content": str(ch)}})

                resp_json["choices"] = normalized

            # Allow provider-specific adapters a final chance to normalize/validate the response
            try:
                resp_json = provider_adapters.adapt(resp_json, request_data=request_data)
            except Exception as e:
                logger.debug(f"Provider adapter failed: {e} - continuing normalization")

            if not isinstance(resp_json, dict) or "choices" not in resp_json:
                # Log full response to help debugging provider issues
                try:
                    body_text = response.text
                except Exception:
                    body_text = repr(resp_json)

                logger.error(
                    "Invalid provider response: missing 'choices'. "
                    f"status={response.status_code} body={body_text}"
                )

                # Structured dump for offline analysis
                try:
                    dump_dir = Path(".mcq_provider_dumps")
                    dump_dir.mkdir(parents=True, exist_ok=True)
                    dump_file = (
                        dump_dir
                        / f"provider_response_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
                    )
                    dump_content = {
                        "status_code": response.status_code,
                        "request": request_data,
                        "body": None,
                    }
                    try:
                        dump_content["body"] = response.json()
                    except Exception:
                        dump_content["body"] = body_text

                    # Redact known sensitive fields in the request before writing.
                    # Use substring matching to catch nested/variant keys like
                    # "apiKey", "x-api-key", "user_token", "authorizationBearer".
                    sensitive_substrings = (
                        "api_key",
                        "apikey",
                        "authorization",
                        "auth",
                        "token",
                        "access_token",
                        "secret",
                        "passwd",
                        "password",
                        "bearer",
                    )

                    def _redact(obj):
                        if isinstance(obj, dict):
                            out = {}
                            for k, v in obj.items():
                                lk = k.lower()
                                if any(sub in lk for sub in sensitive_substrings):
                                    out[k] = "REDACTED"
                                else:
                                    out[k] = _redact(v)
                            return out
                        if isinstance(obj, list):
                            return [_redact(i) for i in obj]
                        return obj

                    try:
                        dump_content["request"] = _redact(dump_content.get("request"))
                    except Exception:
                        pass

                    dump_file.write_text(
                        json.dumps(dump_content, indent=2, ensure_ascii=False), encoding="utf-8"
                    )

                    # Rotate old dumps to limit disk usage (best-effort).
                    try:
                        retention = (
                            config.DUMP_RETENTION if hasattr(config, "DUMP_RETENTION") else 200
                        )
                        files = sorted(
                            dump_dir.glob("provider_response_*.json"),
                            key=lambda p: p.stat().st_mtime,
                        )
                        if len(files) > retention:
                            for old in files[: max(0, len(files) - retention)]:
                                try:
                                    old.unlink()
                                except Exception:
                                    pass
                    except Exception:
                        # Don't fail the whole operation for dump rotation issues
                        pass
                except Exception as dump_e:
                    logger.debug(
                        f"Failed to write structured provider dump: {dump_e}\n{traceback.format_exc()}"
                    )

                # Count as a provider error/failure so circuit breaker is updated and
                # retry logic in this method can apply. Use a dedicated exception
                # for semantic provider failures so retry policies don't treat them
                # as transient network errors.
                self._handle_failure(Exception("Invalid provider response: missing 'choices'"))
                raise InvalidProviderResponse("Invalid provider response: missing 'choices'")

            self.failure_count = 0
            self.successful_requests += 1

            if self.circuit_state == "half-open":
                self._close_circuit()

            return resp_json

        except httpx.HTTPError as e:
            self.failed_requests += 1
            self._handle_failure(e)
            raise

    async def generate_batch(
        self, batch_messages: list[list[dict]], model: str = "gpt-4", **kwargs
    ) -> list[dict]:
        """Generate multiple completions in parallel."""
        tasks = [self.generate(messages, model=model, **kwargs) for messages in batch_messages]

        semaphore = asyncio.Semaphore(5)

        async def bounded_task(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(
            *[bounded_task(task) for task in tasks], return_exceptions=True
        )

        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch request {i} failed: {result}")
            else:
                valid_results.append(result)

        return valid_results

    def _check_circuit_breaker(self) -> None:
        """Check and update circuit breaker state."""
        if self.circuit_state == "open":
            opened_at = self.circuit_opened_at
            if opened_at:
                elapsed = (datetime.now() - opened_at).seconds
                if elapsed >= self.circuit_breaker_timeout:
                    logger.info("Circuit breaker: open -> half-open")
                    self.circuit_state = "half-open"
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit breaker is open. Retry in {self.circuit_breaker_timeout - elapsed}s"
                    )

    def _handle_failure(self, error: Exception) -> None:
        """Handle request failure and update circuit breaker."""
        self.failure_count += 1
        logger.error(
            f"Request failed ({self.failure_count}/{self.circuit_breaker_threshold}): {error}"
        )

        if self.failure_count >= self.circuit_breaker_threshold:
            self._open_circuit()

    def _open_circuit(self) -> None:
        """Open the circuit breaker."""
        self.circuit_state = "open"
        self.circuit_opened_at = datetime.now()
        logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")

    def _close_circuit(self) -> None:
        """Close the circuit breaker."""
        self.circuit_state = "closed"
        self.failure_count = 0
        self.circuit_opened_at = None
        logger.info("Circuit breaker CLOSED")

    async def get_remote_stats(self) -> dict:
        """Get statistics from the remote provider."""
        try:
            response = await self.client.get("/stats")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch remote stats: {e}")
            return {}

    def get_stats(self) -> dict:
        """Get client statistics."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                (self.successful_requests / self.total_requests * 100)
                if self.total_requests > 0
                else 0.0
            ),
            "circuit_state": self.circuit_state,
            "failure_count": self.failure_count,
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class BatchProcessor:
    """Intelligent batch processor for efficient LLM calls."""

    def __init__(self, provider_client: ProviderClient, batch_size: int = 3):
        self.client = provider_client
        self.batch_size = batch_size

    async def process_documents(self, documents: list, prompt_template: str) -> list[dict]:
        """Process documents in batches."""
        results = []

        for i in range(0, len(documents), self.batch_size):
            batch = documents[i : i + self.batch_size]
            batch_prompt = self._create_batch_prompt(batch, prompt_template)

            try:
                response = await self.client.generate(
                    messages=[{"role": "user", "content": batch_prompt}], temperature=0.7
                )

                batch_mcqs = self._parse_batch_response(response, len(batch))
                results.extend(batch_mcqs)

            except Exception as e:
                logger.error(f"Batch processing failed: {e}")
                for doc in batch:
                    try:
                        response = await self.client.generate(
                            messages=[
                                {"role": "user", "content": prompt_template.format(document=doc)}
                            ]
                        )
                        results.append(self._parse_single_response(response))
                    except Exception as inner_e:
                        logger.error(f"Individual processing failed: {inner_e}")

        return results

    def _create_batch_prompt(self, documents: list, template: str) -> str:
        """Create a prompt for batch processing."""
        batch_text = "\n\n---DOCUMENT SEPARATOR---\n\n".join(
            f"DOCUMENT {i + 1}:\n{doc}" for i, doc in enumerate(documents)
        )

        return f"""Generate {len(documents)} MCQs, one for each document below.

{batch_text}

Generate ONE MCQ for EACH document. Format as:

MCQ 1:
[Question]
A) [Option]
B) [Option]
C) [Option]
CORRECT: [A/B/C]
...

MCQ 2:
...
"""

    def _parse_batch_response(self, response: dict, expected_count: int) -> list[dict]:
        """Parse batch response into individual MCQs."""
        import re

        content = response["choices"][0]["message"]["content"]
        mcq_sections = re.split(r"MCQ \d+:", content)[1:]

        results = []
        for section in mcq_sections[:expected_count]:
            results.append({"raw": section.strip()})

        return results

    def _parse_single_response(self, response: dict) -> dict:
        """Parse single MCQ response."""
        return {"raw": response["choices"][0]["message"]["content"]}
