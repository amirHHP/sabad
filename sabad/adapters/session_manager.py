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

    @classmethod
    def _get_streamlit_session_state(cls) -> Optional[Any]:
        """Returns st.session_state if executing within an active Streamlit context, else None."""
        try:
            import streamlit as st
            for module_name in (
                "streamlit.runtime.scriptrunner",
                "streamlit.runtime.scriptrunner_utils.script_run_context",
            ):
                try:
                    mod = __import__(module_name, fromlist=["get_script_run_ctx"])
                    get_ctx = getattr(mod, "get_script_run_ctx", None)
                    if get_ctx:
                        try:
                            ctx = get_ctx(suppress_warning=True)
                        except TypeError:
                            ctx = get_ctx()
                        if ctx is not None and hasattr(st, "session_state"):
                            return st.session_state
                except Exception:
                    continue
        except Exception:
            pass
        return None

    @staticmethod
    def _get_path(platform: str) -> Path:
        return SESSIONS_DIR / f"{platform}.json"

    @classmethod
    def load_session(cls, platform: str) -> Dict[str, Any]:
        """Loads stored session credentials for a platform."""
        st_state = cls._get_streamlit_session_state()
        if st_state is not None:
            data = st_state.get(f"_session_{platform}")
            if isinstance(data, dict):
                return dict(data)
            return {}

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
        """Persists session credentials to session_state or disk."""
        session_data["updated_at"] = datetime.now().isoformat()

        st_state = cls._get_streamlit_session_state()
        if st_state is not None:
            st_state[f"_session_{platform}"] = dict(session_data)
            return

        path = cls._get_path(platform)
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
        st_state = cls._get_streamlit_session_state()
        if st_state is not None:
            key = f"_session_{platform}"
            if key in st_state:
                del st_state[key]
            return

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
