"""Shared in-memory stores used for graceful fallback when DB is unavailable.

This module centralizes tiny fallbacks (currently `_inmem_jobs`) so both
the new API module and the legacy compatibility endpoints can share state
without circular imports or relying on DuckDB.
"""


# job_id -> job dict
_inmem_jobs: dict[str, dict] = {}
