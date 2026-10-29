"""User feedback for a result that does not match the request."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from sabad.durable_store import EventLog, open_event_log


FEEDBACK_REASONS = (
    "حجم نامناسب",
    "نوع اشتباه",
    "محصول خودرو",
    "محصول ورزشی",
)


@dataclass(frozen=True)
class ProductFeedback:
    requested_text: str
    selected_title: str
    platform: str
    reason: str
    details: str
    created_at: str
    session_key: str = "anonymous"


class FeedbackStore:
    """Append feedback to SQLite, Redis, or memory. Production does not use a local json file."""

    def __init__(self, path: Optional[str] = None, log: Optional[EventLog] = None):
        self._log = log or open_event_log("feedback.sqlite3", path)

    def submit(
        self,
        requested_text: str,
        selected_title: str,
        platform: str,
        reason: str,
        details: str = "",
        session_key: str = "anonymous",
    ) -> ProductFeedback:
        if reason not in FEEDBACK_REASONS:
            raise ValueError("unknown feedback reason")
        feedback = ProductFeedback(
            requested_text=str(requested_text)[:500],
            selected_title=str(selected_title)[:500],
            platform=str(platform)[:100],
            reason=reason,
            details=str(details)[:1000],
            created_at=datetime.now(timezone.utc).isoformat(),
            session_key=str(session_key)[:120],
        )
        self._log.append("feedback", feedback.platform or "unknown", asdict(feedback))
        return feedback

    def recent(self, platform: str = "") -> list[dict]:
        if platform:
            return self._log.read("feedback", platform)
        return []
