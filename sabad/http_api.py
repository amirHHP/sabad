"""Public HTTP API for search and basket optimization.

The Streamlit app remains the prototyping UI. This service is the production
boundary: it checks a real API credential, limits how often a caller can
search, and never returns provider keys.
"""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from sabad.app_services import compare_and_optimize_basket
from sabad.compare_view import build_compare_view
from sabad import config
from sabad.config import DEFAULT_LATITUDE, DEFAULT_LONGITUDE
from sabad.feedback import FEEDBACK_REASONS, FeedbackStore
from sabad.normalizer.gemini_parser import transcribe_audio_gemini
from sabad.normalizer.parser import parse_grocery_input
from sabad.price_history import PriceHistoryStore
from sabad.security import (
    MAX_BASKET_ITEMS,
    SlidingWindowLimiter,
    configured_api_key,
    is_production,
    log_store_failure,
    validate_audio_size,
    validate_basket_text,
    verify_api_key,
)

_compare_limiter = SlidingWindowLimiter()
_feedback_limiter = SlidingWindowLimiter(limit=30, window_seconds=60)
_transcribe_limiter = SlidingWindowLimiter(limit=8, window_seconds=60)
_history: Optional[PriceHistoryStore] = None
_feedback: Optional[FeedbackStore] = None


def history_store() -> PriceHistoryStore:
    global _history
    if _history is None:
        _history = PriceHistoryStore()
    return _history


def feedback_store() -> FeedbackStore:
    global _feedback
    if _feedback is None:
        _feedback = FeedbackStore()
    return _feedback


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _auth_failure(request: Request):
    if is_production() and not configured_api_key():
        return JSONResponse({"error": "احراز هویت سرویس تنظیم نشده است."}, status_code=503)
    if not verify_api_key(_bearer(request)):
        return JSONResponse({"error": "برای این درخواست باید وارد حساب سرویس شوی."}, status_code=401)
    return None


def _caller(request: Request) -> str:
    """Stable caller id that is safe to store. The raw credential is never kept.

    The Next.js server sends ``X-Sabad-Client`` so each browser has its own
    search budget. The value is hashed together with the service credential.
    """
    client = request.headers.get("x-sabad-client", "").strip()
    if not client and request.client and request.client.host:
        client = request.client.host
    material = f"{_bearer(request)}:{client or 'anonymous'}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


async def health(_request: Request):
    return JSONResponse({"status": "ok", "service": "sabad"})


async def compare(request: Request):
    denied = _auth_failure(request)
    if denied is not None:
        return denied
    allowed, retry_after = _compare_limiter.allow(_caller(request))
    if not allowed:
        return JSONResponse(
            {"error": f"تعداد جست‌وجو در این دقیقه تمام شد. {retry_after} ثانیهٔ دیگر دوباره امتحان کن."},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "بدنهٔ درخواست قابل خواندن نیست."}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "بدنهٔ درخواست باید یک شیء JSON باشد."}, status_code=400)

    text = str(payload.get("text") or "")
    basket_check = validate_basket_text(text)
    if not basket_check.ok:
        return JSONResponse({"error": basket_check.message}, status_code=400)
    try:
        latitude = float(payload.get("latitude", DEFAULT_LATITUDE))
        longitude = float(payload.get("longitude", DEFAULT_LONGITUDE))
    except (TypeError, ValueError):
        return JSONResponse({"error": "مختصات تحویل نامعتبر است."}, status_code=400)

    basket = parse_grocery_input(text, use_llm=bool(payload.get("use_ai")))
    if not basket.items:
        return JSONResponse({"error": "لطفاً حداقل یک قلم کالا وارد کن."}, status_code=400)
    if len(basket.items) > MAX_BASKET_ITEMS:
        return JSONResponse(
            {"error": f"حداکثر {MAX_BASKET_ITEMS} قلم در هر جست‌وجو بررسی می‌شود."},
            status_code=400,
        )

    try:
        harvester, _store_infos, catalog_matches, _flash, result = await compare_and_optimize_basket(
            basket.items,
            latitude,
            longitude,
            split_penalty_tomans=int(payload.get("split_penalty_tomans") or 25000),
            allow_multi_store=bool(payload.get("allow_multi_store", True)),
        )
    except Exception as exc:
        log_store_failure("api", "compare", exc)
        return JSONResponse({"error": "مقایسهٔ فروشگاه‌ها در این لحظه انجام نشد."}, status_code=502)

    try:
        changes = history_store().record_matches(catalog_matches)
    except Exception as exc:
        log_store_failure("api", "price_history", exc)
        changes = {}

    titles = {
        name: adapter.platform_title_fa
        for name, adapter in harvester.adapters.items()
    }
    view = build_compare_view(
        basket.items,
        catalog_matches,
        getattr(harvester, "last_search_evidence", {}),
        result,
        changes,
        titles,
    )
    return JSONResponse(view)


async def submit_feedback(request: Request):
    denied = _auth_failure(request)
    if denied is not None:
        return denied
    allowed, retry_after = _feedback_limiter.allow(_caller(request))
    if not allowed:
        return JSONResponse(
            {"error": "بازخوردهای این دقیقه زیاد شده. کمی بعد دوباره بفرست."},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "بدنهٔ درخواست قابل خواندن نیست."}, status_code=400)
    reason = str((payload or {}).get("reason") or "")
    if reason not in FEEDBACK_REASONS:
        return JSONResponse(
            {"error": "دلیل را از بین حجم نامناسب، نوع اشتباه، محصول خودرو یا محصول ورزشی انتخاب کن."},
            status_code=400,
        )
    feedback_store().submit(
        requested_text=str(payload.get("requested") or ""),
        selected_title=str(payload.get("title") or ""),
        platform=str(payload.get("platform") or ""),
        reason=reason,
        session_key=_caller(request)[:32],
    )
    return JSONResponse({"ok": True})


def _gemini_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or getattr(config, "GEMINI_API_KEY", "") or "").strip()


async def transcribe(request: Request):
    """Turn a short voice note into the shopping list text."""
    denied = _auth_failure(request)
    if denied is not None:
        return denied
    allowed, retry_after = _transcribe_limiter.allow(_caller(request))
    if not allowed:
        return JSONResponse(
            {"error": f"ضبط‌های این دقیقه تمام شد. {retry_after} ثانیهٔ دیگر دوباره امتحان کن."},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "بدنهٔ درخواست قابل خواندن نیست."}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "بدنهٔ درخواست باید یک شیء JSON باشد."}, status_code=400)

    encoded = payload.get("audio_base64")
    if not isinstance(encoded, str) or not encoded.strip():
        return JSONResponse({"error": "صدایی نرسید. دوباره ضبط کن."}, status_code=400)
    try:
        audio = base64.b64decode(encoded, validate=True)
    except Exception:
        return JSONResponse({"error": "صدایی نرسید. دوباره ضبط کن."}, status_code=400)
    size_check = validate_audio_size(len(audio))
    if not size_check.ok:
        return JSONResponse({"error": size_check.message}, status_code=400)
    if not _gemini_key():
        return JSONResponse(
            {"error": "تبدیل صدا به متن هنوز فعال نشده؛ لیست را بنویس."},
            status_code=503,
        )

    mime_type = str(payload.get("mime_type") or "audio/webm")
    if not mime_type.startswith("audio/"):
        mime_type = "audio/webm"
    text = transcribe_audio_gemini(audio, mime_type.split(";", 1)[0])
    if not text:
        return JSONResponse(
            {"error": "صدا واضح نبود. دوباره ضبط کن یا لیست را بنویس."},
            status_code=422,
        )
    return JSONResponse({"text": text})


async def parse_list(request: Request):
    """Read the list before the expensive store search, so the shopper can correct it."""
    denied = _auth_failure(request)
    if denied is not None:
        return denied
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "بدنهٔ درخواست قابل خواندن نیست."}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "بدنهٔ درخواست باید یک شیء JSON باشد."}, status_code=400)
    text = str(payload.get("text") or "")
    basket_check = validate_basket_text(text)
    if not basket_check.ok:
        return JSONResponse({"error": basket_check.message}, status_code=400)
    basket = parse_grocery_input(text, use_llm=False)
    if not basket.items:
        return JSONResponse({"error": "لطفاً حداقل یک قلم کالا وارد کن."}, status_code=400)
    if len(basket.items) > MAX_BASKET_ITEMS:
        return JSONResponse(
            {"error": f"حداکثر {MAX_BASKET_ITEMS} قلم در هر جست‌وجو بررسی می‌شود."},
            status_code=400,
        )
    return JSONResponse({
        "items": [
            {
                "name": item.name,
                "raw_text": item.raw_text,
                "title": item.display_title,
                "quantity": item.quantity,
            }
            for item in basket.items
        ]
    })


def api_routes() -> list[Route]:
    return [
        Route("/api/health", health, methods=["GET"]),
        Route("/api/v1/compare", compare, methods=["POST"]),
        Route("/api/v1/parse", parse_list, methods=["POST"]),
        Route("/api/v1/feedback", submit_feedback, methods=["POST"]),
        Route("/api/v1/transcribe", transcribe, methods=["POST"]),
    ]


def create_app() -> Starlette:
    origins = [
        item.strip()
        for item in os.getenv("SABAD_CORS_ORIGINS", "http://localhost:3000").split(",")
        if item.strip()
    ]
    return Starlette(
        routes=api_routes(),
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_methods=["GET", "POST"],
                allow_headers=["authorization", "content-type"],
            )
        ],
    )


app = create_app()
