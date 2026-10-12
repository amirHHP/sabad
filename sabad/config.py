"""
Configuration settings for Sabad.
Handles environment variables, endpoints, coordinates, and default thresholds.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()


def get_config(key: str, default: str = "") -> str:
    """
    Unified secrets and configuration resolver.
    Checks Streamlit secrets (st.secrets) first, falling back to environment variables.
    """
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Session persistence storage
SESSIONS_DIR = BASE_DIR / ".sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

# Geolocation context (Default: Tehran - Keshavarz Boulevard / Yousef Abad)
DEFAULT_LATITUDE = float(get_config("LATITUDE", get_config("DEFAULT_LATITUDE", "35.715298")))
DEFAULT_LONGITUDE = float(get_config("LONGITUDE", get_config("DEFAULT_LONGITUDE", "51.404343")))

# Platform API Base URLs
SNAPP_MARKET_BASE_URL = get_config("SNAPP_MARKET_BASE_URL", "https://svc.snapp.market")
DIGIKALA_JET_BASE_URL = get_config("DIGIKALA_JET_BASE_URL", "https://api.digikalajet.ir")
OKALA_BASE_URL = get_config("OKALA_BASE_URL", "https://apigateway.okala.com")
TAPSI_MARKET_BASE_URL = get_config("TAPSI_MARKET_BASE_URL", "https://api.tapsi.food")

# Network timeouts (seconds)
HTTP_TIMEOUT = float(get_config("HTTP_TIMEOUT", "12.0"))

# Gemini LLM Configuration for Persian semantic parsing
GEMINI_API_KEY = get_config("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = get_config("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

# Optimizer defaults (in Tomans)
# Coordination penalty for receiving multiple deliveries (friction cost)
DEFAULT_SPLIT_PENALTY_TOMANS = int(get_config("SPLIT_PENALTY_TOMANS", "25000"))

# Default Minimum Order Value (MOV) fallback if store rules are missing
DEFAULT_MOV_TOMANS = {
    "snapp_market": 100000,
    "digikala_jet": 120000,
    "okala": 100000,
    "tapsi_market": 100000,
}

# Browser & Mobile Headers
COMMON_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
}

SNAPP_HEADERS = {
    **COMMON_BROWSER_HEADERS,
    "Origin": "https://snapp.market",
    "Referer": "https://snapp.market/",
}

JET_HEADERS = {
    **COMMON_BROWSER_HEADERS,
    "Origin": "https://www.digikalajet.com",
    "Referer": "https://www.digikalajet.com/",
    "Client": "Pwa",
    "ClientOs": "web",
    "platform-sso-disable-prod": "1",
}

OKALA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
    "Origin": "https://www.okala.com",
    "Referer": "https://www.okala.com/",
}

TAPSI_HEADERS = {
    **COMMON_BROWSER_HEADERS,
    "Origin": "https://tapsi.food",
    "Referer": "https://tapsi.food/",
}

__all__ = [
    "get_config",
    "BASE_DIR",
    "SESSIONS_DIR",
    "DEFAULT_LATITUDE",
    "DEFAULT_LONGITUDE",
    "SNAPP_MARKET_BASE_URL",
    "DIGIKALA_JET_BASE_URL",
    "OKALA_BASE_URL",
    "TAPSI_MARKET_BASE_URL",
    "HTTP_TIMEOUT",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "DEFAULT_SPLIT_PENALTY_TOMANS",
    "DEFAULT_MOV_TOMANS",
    "COMMON_BROWSER_HEADERS",
    "SNAPP_HEADERS",
    "JET_HEADERS",
    "OKALA_HEADERS",
    "TAPSI_HEADERS",
]
