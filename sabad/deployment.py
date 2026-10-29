"""Runtime secret mapping for ASGI hosts such as Vercel."""

import os
from typing import Any, Dict, Optional


def runtime_secrets() -> Optional[Dict[str, Any]]:
    """Map platform environment variables to Streamlit's secret shape.

    Streamlit local development reads ``.streamlit/secrets.toml``. Serverless
    platforms usually expose only environment variables, so the ASGI wrapper
    passes this mapping to ``st.App(secrets=...)`` without writing credentials to
    disk.
    """
    auth_keys = {
        "redirect_uri": os.getenv("OIDC_REDIRECT_URI", ""),
        "cookie_secret": os.getenv("OIDC_COOKIE_SECRET", ""),
        "client_id": os.getenv("OIDC_CLIENT_ID", ""),
        "client_secret": os.getenv("OIDC_CLIENT_SECRET", ""),
        "server_metadata_url": os.getenv("OIDC_SERVER_METADATA_URL", ""),
    }
    secrets: Dict[str, Any] = {}
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    gemini_model = os.getenv("GEMINI_MODEL", "")
    if gemini_key:
        secrets["GEMINI_API_KEY"] = gemini_key
    if gemini_model:
        secrets["GEMINI_MODEL"] = gemini_model
    if any(auth_keys.values()):
        secrets["auth"] = auth_keys
    return secrets or None

