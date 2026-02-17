"""
Configuration manager for environment variables.
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """
    Simple configuration manager that loads from .env if present.
    """

    def __init__(self, env_file: Optional[str] = None):
        if env_file is None:
            # Look for .env in project root (assuming we are in src/mcq_generator)
            env_file = Path(__file__).parent.parent.parent / ".env"

        self.env_file = Path(env_file)
        self.env = {}
        self._load_env()

    def _load_env(self):
        """Parse .env file manually to avoid dependencies."""
        if not self.env_file.exists():
            return

        with open(self.env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Support both KEY=VALUE and KEY="VALUE"
                    value = value.strip().strip("'").strip('"')
                    self.env[key.strip()] = value

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get value from .env or environment variables."""
        return self.env.get(key) or os.getenv(key) or default

    @property
    def HF_TOKEN(self) -> Optional[str]:
        return self.get("HF_TOKEN")

    @property
    def PROVIDER_URL(self) -> str:
        return self.get("ROUTER_URL") or self.get("PROVIDER_URL") or "http://localhost:7543"

    @property
    def LLM_MODEL(self) -> str:
        return self.get("LLM_MODEL") or "gpt-4"

    @property
    def CONSECUTIVE_FAILURE_LIMIT(self) -> int | None:
        """Maximum consecutive failures before an aggressive backoff/reset.

        If unset or set to an empty string, returns None which disables the hard
        limit and instead falls back to a periodic backoff strategy.
        """
        v = self.get("CONSECUTIVE_FAILURE_LIMIT")
        if v is None or v == "":
            return None
        try:
            return int(v)
        except Exception:
            return None

    @property
    def BACKOFF_INITIAL_SECONDS(self) -> int:
        try:
            return int(self.get("BACKOFF_INITIAL_SECONDS") or 30)
        except Exception:
            return 30

    @property
    def BACKOFF_MULTIPLIER(self) -> int:
        try:
            return int(self.get("BACKOFF_MULTIPLIER") or 2)
        except Exception:
            return 2

    @property
    def BACKOFF_MAX_SECONDS(self) -> int:
        try:
            return int(self.get("BACKOFF_MAX_SECONDS") or 1800)
        except Exception:
            return 1800

    @property
    def BACKOFF_TRIGGER(self) -> int:
        """When hard limit is disabled, perform backoff every N consecutive failures."""
        try:
            return int(self.get("BACKOFF_TRIGGER") or 50)
        except Exception:
            return 50

    @property
    def COUNT_CONTENT_FAILURES(self) -> bool:
        """Whether to count content/parse failures toward backoff (default False)."""
        v = self.get("COUNT_CONTENT_FAILURES")
        if v is None:
            return False
        return str(v).lower() in ("1", "true", "yes", "on")

    @property
    def CONTENT_FAILURE_LIMIT(self) -> int:
        try:
            return int(self.get("CONTENT_FAILURE_LIMIT") or 200)
        except Exception:
            return 200

    @property
    def DUMP_RETENTION(self) -> int:
        try:
            return int(self.get("DUMP_RETENTION") or 200)
        except Exception:
            return 200


# Global config instance
config = Config()
