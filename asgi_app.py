"""ASGI entry point for self-hosting and platforms that support long-lived ASGI apps.

Vercel's serverless runtime is included through ``api/index.py``; this wrapper is
also useful for Fly.io, Railway, Render, or a small VPS where Streamlit's
WebSocket session can stay alive.
"""

from pathlib import Path

import streamlit as st

from sabad.deployment import runtime_secrets
from sabad.http_api import api_routes

app = st.App(
    str(Path(__file__).resolve().with_name("streamlit_app.py")),
    secrets=runtime_secrets(),
    routes=api_routes(),
)

