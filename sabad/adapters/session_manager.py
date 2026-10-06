"""
Persistent Session and Authentication Manager for Sabad.
Stores tokens and cookies in .sessions/ across runs.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
from sabad.config import SESSIONS_DIR


class SessionManager:
    """Handles secure loading, saving, and validation of user session tokens."""

    @staticmethod
    def _get_path(platform: str) -> Path:
        return SESSIONS_DIR / f"{platform}.json"

    @classmethod
    def load_session(cls, platform: str) -> Dict[str, Any]:
        """Loads stored session credentials for a platform."""
        path = cls._get_path(platform)
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def save_session(cls, platform: str, session_data: Dict[str, Any]) -> None:
        """Persists session credentials to disk."""
        path = cls._get_path(platform)
        session_data["updated_at"] = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

    @classmethod
    def save_tokens(
        cls,
        platform: str,
        token: str,
        refresh_token: Optional[str] = None,
        phone: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Helper to quickly persist tokens and phone number."""
        session_data = cls.load_session(platform)
        session_data.update({
            "token": token,
            "access_token": token,
            "refresh_token": refresh_token,
            "phone": phone,
            **(metadata or {})
        })
        cls.save_session(platform, session_data)

    @classmethod
    def clear_session(cls, platform: str) -> None:
        """Deletes session file on logout or token expiration."""
        path = cls._get_path(platform)
        if path.exists():
            path.unlink()

    @classmethod
    def get_token(cls, platform: str) -> Optional[str]:
        """Retrieves active Bearer token if present."""
        data = cls.load_session(platform)
        return data.get("token") or data.get("access_token")

    @classmethod
    def get_phone(cls, platform: str) -> Optional[str]:
        """Retrieves stored phone number if present."""
        data = cls.load_session(platform)
        return data.get("phone")

    @classmethod
    def is_authenticated(cls, platform: str) -> bool:
        """Returns True if platform has stored session token/cookie."""
        token = cls.get_token(platform)
        return bool(token and len(token) > 10)
