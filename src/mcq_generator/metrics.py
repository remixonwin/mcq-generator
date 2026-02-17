"""Prometheus metrics integration with graceful fallback.

This module exposes a small set of metrics used by the API and task runner.
If `prometheus_client` is not installed the functions are no-ops and the
metrics endpoint returns a helpful message.
"""

from __future__ import annotations

import os

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

    _available = True
except Exception:  # pragma: no cover - can't force import failure in tests
    _available = False


if _available:
    api_requests = Counter("mcq_api_requests_total", "Total API requests", ["path"])
    jobs_created = Counter("mcq_jobs_created_total", "Total jobs created")
    jobs_enqueued = Counter("mcq_jobs_enqueued_total", "Total jobs enqueued")
    jobs_failed = Counter("mcq_jobs_failed_total", "Total jobs failed")
    jobs_completed = Counter("mcq_jobs_completed_total", "Total jobs completed")
    # To keep label cardinality low we only label by `topic` (coarse dataset
    # name). Avoid using job_id as a label.
    job_duration = Histogram(
        "mcq_job_duration_seconds",
        "Job processing time seconds",
        ["topic"],
    )

    def _safe_topic_label(topic: str) -> str:
        if not topic:
            return "unknown"
        t = str(topic).lower()
        import re

        t = re.sub(r"[^a-z0-9]+", "_", t)
        return t[:32]

    def observe_job_duration(topic: str, seconds: float) -> None:
        job_duration.labels(_safe_topic_label(topic)).observe(seconds)

    def inc_job_failed(topic: str) -> None:
        jobs_failed.inc()

    def inc_job_completed(topic: str) -> None:
        jobs_completed.inc()

    def push_job_metrics(
        job_id: str, topic: str, duration: float, success: bool, ttl: int = 300
    ) -> None:
        """Push per-job short-lived metrics to Pushgateway and schedule deletion.

        Uses grouping_key to keep Prometheus series manageable on the main
        scrape (the job entry is short-lived). A background timer will delete
        the pushed job after `ttl` seconds to avoid long-lived cardinality.
        """
        try:
            from prometheus_client import (
                CollectorRegistry,
                Gauge,
                delete_from_gateway,
                push_to_gateway,
            )
        except Exception:
            return

        registry = CollectorRegistry()
        g = Gauge(
            "mcq_job_duration_seconds",
            "Per-job duration seconds",
            ["job_id", "topic"],
            registry=registry,
        )
        s = Gauge(
            "mcq_job_success",
            "Per-job success flag (1=success,0=failure)",
            ["job_id", "topic"],
            registry=registry,
        )

        jid = str(job_id)
        t = str(topic)
        g.labels(jid, t).set(duration)
        s.labels(jid, t).set(1 if success else 0)

        pushgateway = os.getenv("PUSHGATEWAY_URL")
        if not pushgateway:
            return

        try:
            push_to_gateway(
                pushgateway,
                job="mcq_job",
                registry=registry,
                grouping_key={"job_id": jid, "topic": t},
            )
        except Exception:
            return

        # Schedule deletion after ttl seconds to avoid long-lived series
        try:
            import threading

            def _delete():
                try:
                    delete_from_gateway(
                        pushgateway, job="mcq_job", grouping_key={"job_id": jid, "topic": t}
                    )
                except Exception:
                    pass

            timer = threading.Timer(ttl, _delete)
            timer.daemon = True
            timer.start()
        except Exception:
            # best-effort
            pass

    def metrics_available() -> bool:
        return True

    def generate_metrics() -> tuple[bytes, str]:
        return generate_latest(), CONTENT_TYPE_LATEST

else:
    # No-op fallbacks
    class _Noop:
        def inc(self, *a, **k):
            pass

        def labels(self, *a, **k):
            return self

        def observe(self, *a, **k):
            pass

    api_requests = _Noop()
    jobs_created = _Noop()
    jobs_enqueued = _Noop()
    jobs_failed = _Noop()
    jobs_completed = _Noop()
    job_duration = _Noop()

    def metrics_available() -> bool:
        return False

    def generate_metrics() -> tuple[bytes, str]:
        body = b"# prometheus_client not installed; no metrics available\n"
        return body, "text/plain; charset=utf-8"

    def observe_job_duration(topic: str, seconds: float) -> None:  # pragma: no cover - noop
        return None

    def inc_job_failed(topic: str) -> None:  # pragma: no cover - noop
        return None

    def inc_job_completed(topic: str) -> None:  # pragma: no cover - noop
        return None
