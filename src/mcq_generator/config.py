"""
Configuration manager for environment variables.

Supports loading from:
1. HashiCorp Vault (when VAULT_ENABLED=true)
2. Environment variables
3. .env file (for development)
"""

import os
from pathlib import Path

# Try to import Vault integration (optional)
try:
    from unified.secrets import get_secret as _vault_get_secret
except ImportError:
    _vault_get_secret = None


class Config:
    """
    Simple configuration manager that loads from .env if present.
    """

    def __init__(self, env_file: str | None = None):
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

        with open(self.env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    # Support both KEY=VALUE and KEY="VALUE"
                    value = value.strip().strip("'").strip('"')
                    self.env[key.strip()] = value

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get value from Vault, .env, or environment variables."""
        # Try Vault first if available
        if _vault_get_secret is not None:
            try:
                vault_value = _vault_get_secret(key, "mcq-generator", None)
                if vault_value:
                    return vault_value
            except Exception:
                pass  # Fall back to environment variables

        # Fall back to environment variables
        return self.env.get(key) or os.getenv(key) or default

    @property
    def HF_TOKEN(self) -> str | None:  # noqa: N802
        return self.get("HF_TOKEN")

    @property
    def PROVIDER_URL(self) -> str:  # noqa: N802
        return self.get("ROUTER_URL") or self.get("PROVIDER_URL") or "http://localhost:7330"

    @property
    def LLM_MODEL(self) -> str:  # noqa: N802
        return self.get("LLM_MODEL") or "gpt-4"

    @property
    def CONSECUTIVE_FAILURE_LIMIT(self) -> int | None:  # noqa: N802
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
    def BACKOFF_INITIAL_SECONDS(self) -> int:  # noqa: N802
        try:
            return int(self.get("BACKOFF_INITIAL_SECONDS") or 30)
        except Exception:
            return 30

    @property
    def BACKOFF_MULTIPLIER(self) -> int:  # noqa: N802
        try:
            return int(self.get("BACKOFF_MULTIPLIER") or 2)
        except Exception:
            return 2

    @property
    def BACKOFF_MAX_SECONDS(self) -> int:  # noqa: N802
        try:
            return int(self.get("BACKOFF_MAX_SECONDS") or 1800)
        except Exception:
            return 1800

    @property
    def BACKOFF_TRIGGER(self) -> int:  # noqa: N802
        """When hard limit is disabled, perform backoff every N consecutive failures."""
        try:
            return int(self.get("BACKOFF_TRIGGER") or 50)
        except Exception:
            return 50

    @property
    def COUNT_CONTENT_FAILURES(self) -> bool:  # noqa: N802
        """Whether to count content/parse failures toward backoff (default False)."""
        v = self.get("COUNT_CONTENT_FAILURES")
        if v is None:
            return False
        return str(v).lower() in ("1", "true", "yes", "on")

    @property
    def TEXT_COLUMN_WHITELIST(self) -> list[str]:  # noqa: N802
        """Preferred text-like column name terms (comma-separated in env)."""
        v = self.get("TEXT_COLUMN_WHITELIST")
        if not v:
            return [
                "title",
                "headline",
                "summary",
                "abstract",
                "description",
                "prompt",
                "question",
                "text",
                "content",
                "body",
            ]
        return [t.strip() for t in v.split(",") if t.strip()]

    @property
    def MAX_SYNTH_COLUMNS(self) -> int:  # noqa: N802
        try:
            return int(self.get("MAX_SYNTH_COLUMNS") or 6)
        except Exception:
            return 6

    @property
    def CONTENT_FAILURE_LIMIT(self) -> int:  # noqa: N802
        try:
            return int(self.get("CONTENT_FAILURE_LIMIT") or 200)
        except Exception:
            return 200

    @property
    def DUMP_RETENTION(self) -> int:  # noqa: N802
        try:
            return int(self.get("DUMP_RETENTION") or 200)
        except Exception:
            return 200

    @property
    def MAX_INPUT_LENGTH(self) -> int:  # noqa: N802
        """Maximum input length in bytes (default 10KB)"""
        try:
            return int(self.get("MAX_INPUT_LENGTH") or 10 * 1024)
        except Exception:
            return 10 * 1024

    @property
    def MAX_JSON_DEPTH(self) -> int:  # noqa: N802
        """Maximum JSON nesting depth"""
        try:
            return int(self.get("MAX_JSON_DEPTH") or 10)
        except Exception:
            return 10

    @property
    def MAX_ARRAY_LENGTH(self) -> int:  # noqa: N802
        """Maximum array length in JSON"""
        try:
            return int(self.get("MAX_ARRAY_LENGTH") or 100)
        except Exception:
            return 100

    @property
    def ENABLE_XSS_PROTECTION(self) -> bool:  # noqa: N802
        """Enable XSS protection for user input"""
        v = self.get("ENABLE_XSS_PROTECTION")
        if v is None:
            return True
        return str(v).lower() in ("1", "true", "yes", "on")

    @property
    def ENABLE_PATH_TRAVERSAL_PROTECTION(self) -> bool:  # noqa: N802
        """Enable path traversal protection for file operations"""
        v = self.get("ENABLE_PATH_TRAVERSAL_PROTECTION")
        if v is None:
            return True
        return str(v).lower() in ("1", "true", "yes", "on")


# Global config instance
config = Config()
