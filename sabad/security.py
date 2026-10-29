"""Input limits, lightweight rate limiting, and API-key guards."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:authorization\s*[:=]\s*bearer\s+\S+|bearer\s+\S+|\b(?:api[_-]?key|token|secret|password|cookie)\b\s*[:=]\s*\S+)"
)
_GEMINI_KEY = re.compile(r"AIza[0-9A-Za-z_\-]{10,}")
_QUERY_SECRET = re.compile(r"(?i)([?&](?:key|api_key|token|access_token)=)[^&\s]+")


MAX_BASKET_CHARS = int(os.getenv("SABAD_MAX_BASKET_CHARS", "800"))
MAX_BASKET_ITEMS = int(os.getenv("SABAD_MAX_BASKET_ITEMS", "20"))
MAX_AUDIO_BYTES = int(os.getenv("SABAD_MAX_AUDIO_BYTES", "6000000"))
COMPARE_RATE_LIMIT = int(os.getenv("SABAD_COMPARE_RATE_LIMIT", "12"))
COMPARE_RATE_WINDOW_SECONDS = int(os.getenv("SABAD_COMPARE_RATE_WINDOW_SECONDS", "60"))


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    message: str = ""


def validate_basket_text(text: str) -> ValidationResult:
    if not isinstance(text, str) or not text.strip():
        return ValidationResult(False, "لطفاً حداقل یک قلم کالا وارد کن.")
    if len(text) > MAX_BASKET_CHARS:
        return ValidationResult(False, f"لیست خرید خیلی طولانی است؛ حداکثر {MAX_BASKET_CHARS} نویسه مجاز است.")
    return ValidationResult(True)


def validate_audio_size(size: int) -> ValidationResult:
    if size > MAX_AUDIO_BYTES:
        return ValidationResult(False, "فایل صدا طولانی است؛ لطفاً یک فهرست کوتاه‌تر ضبط کن.")
    return ValidationResult(True)


class SlidingWindowLimiter:
    """Process-local limiter; use Redis/Upstash for multi-instance production."""

    def __init__(self, limit: int = COMPARE_RATE_LIMIT, window_seconds: int = COMPARE_RATE_WINDOW_SECONDS):
        self.limit = max(1, int(limit))
        self.window_seconds = max(1, int(window_seconds))
        self._events: dict[str, list[float]] = {}
        self._lock = threading.RLock()

    def allow(self, identity: str) -> tuple[bool, int]:
        shared = self._allow_redis(identity)
        if shared is not None:
            return shared
        now = time.monotonic()
        key = hashlib.sha256((identity or "anonymous").encode("utf-8")).hexdigest()[:32]
        with self._lock:
            recent = [event for event in self._events.get(key, []) if now - event < self.window_seconds]
            if len(recent) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - recent[0])))
                self._events[key] = recent
                return False, retry_after
            recent.append(now)
            self._events[key] = recent
            if len(self._events) > 2000:
                self._events = {k: v for k, v in self._events.items() if v and now - v[-1] < self.window_seconds}
            return True, 0

    def _allow_redis(self, identity: str) -> Optional[tuple[bool, int]]:
        try:
            from sabad.durable_store import redis_client

            client = redis_client()
        except Exception:
            return None
        if client is None:
            return None
        try:
            bucket = int(time.time()) // self.window_seconds
            digest = hashlib.sha256((identity or "anonymous").encode("utf-8")).hexdigest()[:32]
            key = f"sabad:rate:{digest}:{bucket}"
            count = int(client.incr(key))
            if count == 1:
                client.expire(key, self.window_seconds)
            if count > self.limit:
                return False, self.window_seconds
            return True, 0
        except Exception:
            logger.warning("shared rate limiter unavailable; using process memory")
            return None


def configured_api_key() -> str:
    return os.getenv("SABAD_API_KEY", "").strip()


def is_production() -> bool:
    if os.getenv("SABAD_ENV", "").lower() == "production":
        return True
    # Vercel sets these on every deployment. The compare API must not be open there.
    return bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))


def verify_api_key(provided: Optional[str]) -> bool:
    """Require a key only when ``SABAD_API_KEY`` is configured.

    Production refuses open access when the key was forgotten. Local runs stay
    usable until the key is set.
    """
    expected = configured_api_key()
    if not expected:
        return not is_production()
    return bool(provided) and hmac.compare_digest(provided.strip(), expected)


def redact_secrets(text: str) -> str:
    """Remove API keys and token assignments before a string is logged."""
    cleaned = _SECRET_ASSIGNMENT.sub("[redacted]", text or "")
    cleaned = _QUERY_SECRET.sub(r"\1[redacted]", cleaned)
    return _GEMINI_KEY.sub("[redacted]", cleaned)


def log_store_failure(platform: str, action: str, error: BaseException) -> None:
    """Log a store failure without request headers, tokens, or API keys."""
    detail = redact_secrets(f"{type(error).__name__}: {error}")
    logger.warning("store failure platform=%s action=%s error=%s", platform, action, detail[:300])

