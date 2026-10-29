"""Vercel-compatible ASGI handler for the Sabad Streamlit application."""

from pathlib import Path

import streamlit as st

from sabad.deployment import runtime_secrets
from sabad.http_api import api_routes

ROOT = Path(__file__).resolve().parents[1]

# Keep API paths namespaced so they cannot collide with Streamlit's internal routes.
app = st.App(
    str(ROOT / "streamlit_app.py"),
    secrets=runtime_secrets(),
    routes=api_routes(),
)

