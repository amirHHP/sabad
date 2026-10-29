"""Regression coverage for the voice-first entry and hidden settings."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import streamlit as st
from streamlit.testing.v1 import AppTest

from sabad import config
from sabad.models.grocery import ParsedGroceryBasket, ParsedGroceryItem
from sabad.normalizer import gemini_parser, parser


def test_settings_persist_and_manual_list_returns_to_minimal_landing():
    at = AppTest.from_file(str(config.BASE_DIR / "app.py")).run(timeout=30)
    assert not at.selectbox and not at.text_area
    at.button(key="open_settings").click().run()
    at.selectbox(key="delivery_location").select("تهران - تجریش / شمیرانات").run()
    at.checkbox(key="allow_split").uncheck().run()
    at.checkbox(key="use_ai").uncheck().run()
    at.session_state["catalog_harvester"] = "location-bound adapter"
    at.selectbox(key="delivery_location").select("تهران - تهرانپارس").run()
    assert "catalog_harvester" not in at.session_state
    next(b for b in at.button if b.label == "بستن تنظیمات").click().run()
    assert not at.selectbox
    assert at.session_state["delivery_location"] == "تهران - تهرانپارس"
    assert at.session_state["allow_split"] is False

    at.button(key="open_settings").click().run()
    assert at.selectbox(key="delivery_location").value == "تهران - تهرانپارس"
    assert not at.checkbox(key="allow_split").value
    at.text_area[0].set_value("یک شیر کاله و یک تخم مرغ").run()
    next(b for b in at.button if b.label == "ادامه با این لیست").click().run()
    assert not at.exception
    assert not at.selectbox
    assert at.text_area(key="basket_editor").value == "یک شیر کاله و یک تخم مرغ"

    # Edits must invalidate the previous basket's prices and delivery calculation.
    at.session_state["opt_result"] = "stale result"
    at.text_area(key="basket_editor").set_value("یک شیر کاله").run()
    assert not at.exception
    assert "opt_result" not in at.session_state
    at.button(key="del_cart_item_0").click().run()
    at.button(key="clear_all_basket_btn").click().run()
    assert not at.exception
    assert not at.text_area and not at.selectbox
    assert [b.key for b in at.button] == ["open_settings"]


def test_recording_updates_editor_once_and_clear_does_not_restore_audio(monkeypatch):
    transcript = "دو تا شیر کاله"
    audio = SimpleNamespace(getvalue=lambda: b"test-wav-bytes", type="audio/wav")
    transcription = MagicMock(return_value=transcript)
    parsing = MagicMock(return_value=ParsedGroceryBasket(
        raw_input=transcript,
        items=[ParsedGroceryItem(raw_text=transcript, name="شیر", quantity=2)],
    ))
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gemini_parser, "transcribe_audio_gemini", transcription)
    monkeypatch.setattr(parser, "parse_grocery_input", parsing)
    monkeypatch.setattr(st, "audio_input", lambda *args, **kwargs: (
        audio if kwargs["key"] == "basket_voice_note_0" else None
    ))
    at = AppTest.from_file(str(config.BASE_DIR / "app.py")).run(timeout=30)
    assert not at.exception
    assert at.text_area(key="basket_editor").value == transcript
    at.run()
    assert not at.exception
    assert transcription.call_count == 1
    assert parsing.call_count == 1

    at.button(key="clear_all_basket_btn").click().run()
    assert not at.exception
    assert at.session_state["user_basket_text"] == ""
    assert not at.text_area
    assert transcription.call_count == 1
