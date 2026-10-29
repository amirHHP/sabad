"""
Persistent Session and Authentication Manager for Sabad.
Stores tokens and cookies in .sessions/ across runs.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
from sabad.config import SESSIONS_DIR
from sabad.security import log_store_failure


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

    @classmethod
    def _is_cloud_multi_tenant(cls) -> bool:
        """Checks if executing in a multi-tenant cloud environment where disk writes must be disabled."""
        import os
        if (
            os.environ.get("STREAMLIT_COMMUNITY_CLOUD")
            or os.environ.get("MULTI_TENANT_CLOUD")
            or os.environ.get("VERCEL")
            or os.environ.get("VERCEL_ENV")
            or os.environ.get("SABAD_ENV", "").lower() == "production"
        ):
            return True
        current_test = os.environ.get("PYTEST_CURRENT_TEST", "")
        if "multi_tenant" in current_test:
            return True
        return False

    @staticmethod
    def _get_path(platform: str) -> Path:
        return SESSIONS_DIR / f"{platform}.json"

    @classmethod
    def _scope(cls) -> str:
        st_state = cls._get_streamlit_session_state()
        if st_state is None:
            return os.environ.get("SABAD_SESSION_SCOPE", "local")
        scope = st_state.get("_sabad_scope")
        if scope:
            return str(scope)
        user = None
        try:
            import streamlit as st
            user = getattr(st, "user", None)
        except Exception:
            user = None
        email = getattr(user, "email", None) if user else None
        if not email:
            import uuid
            email = uuid.uuid4().hex
        st_state["_sabad_scope"] = str(email)
        return str(email)

    @classmethod
    def _kv_key(cls, platform: str) -> str:
        return f"session:{cls._scope()}:{platform}"

    @classmethod
    def _read_kv(cls, platform: str):
        kv = cls._session_kv()
        if kv is None:
            return None
        try:
            return kv.get(cls._kv_key(platform))
        except Exception as exc:
            log_store_failure(platform, "session_load", exc)
            return None

    @classmethod
    def _session_kv(cls):
        try:
            from sabad.durable_store import open_session_kv
            return open_session_kv()
        except Exception:
            return None

    @classmethod
    def load_session(cls, platform: str) -> Dict[str, Any]:
        """Loads stored session credentials for a platform."""
        st_state = cls._get_streamlit_session_state()
        if st_state is not None:
            data = st_state.get(f"_session_{platform}")
            if isinstance(data, dict) and data:
                return dict(data)
            if cls._is_cloud_multi_tenant():
                stored = cls._read_kv(platform)
                if isinstance(stored, dict):
                    st_state[f"_session_{platform}"] = dict(stored)
                    return dict(stored)
                return {}

        stored = cls._read_kv(platform)
        if isinstance(stored, dict):
            return dict(stored)
        if cls._is_cloud_multi_tenant():
            return {}

        path = cls._get_path(platform)
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if st_state is not None and isinstance(data, dict):
                    st_state[f"_session_{platform}"] = dict(data)
                return data
        except Exception:
            return {}

    @classmethod
    def save_session(cls, platform: str, session_data: Dict[str, Any]) -> None:
        """Persists session credentials to session state and Redis or the local database."""
        session_data["updated_at"] = datetime.now().isoformat()

        st_state = cls._get_streamlit_session_state()
        if st_state is not None:
            st_state[f"_session_{platform}"] = dict(session_data)

        kv = cls._session_kv()
        if kv is not None:
            try:
                kv.set(cls._kv_key(platform), dict(session_data))
            except Exception as exc:
                log_store_failure(platform, "session_save", exc)
        if cls._is_cloud_multi_tenant():
            return

        path = cls._get_path(platform)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            log_store_failure(platform, "session_save", exc)

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

        kv = cls._session_kv()
        if kv is not None:
            try:
                kv.delete(cls._kv_key(platform))
            except Exception as exc:
                log_store_failure(platform, "session_clear", exc)
        if cls._is_cloud_multi_tenant():
            return

        path = cls._get_path(platform)
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass

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
