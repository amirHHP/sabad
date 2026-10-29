"""Wrong-result feedback and the sentence shown for a missing item."""

import pytest

from sabad.feedback import FEEDBACK_REASONS, FeedbackStore
from sabad.search_explanations import explain_missing_item


def test_feedback_reasons_match_the_shopper_choices(tmp_path):
    store = FeedbackStore(path=str(tmp_path / "feedback.sqlite3"))
    saved = store.submit(
        requested_text="حوله",
        selected_title="حوله ورزشی",
        platform="snapp_market",
        reason="محصول ورزشی",
    )

    assert saved.reason == "محصول ورزشی"
    assert FEEDBACK_REASONS == ("حجم نامناسب", "نوع اشتباه", "محصول خودرو", "محصول ورزشی")
    assert store.recent("snapp_market")[-1]["selected_title"] == "حوله ورزشی"


def test_unknown_feedback_reason_is_rejected(tmp_path):
    store = FeedbackStore(path=str(tmp_path / "feedback.sqlite3"))
    with pytest.raises(ValueError):
        store.submit("شامپو", "شامپو بدن", "okala", "سایر")


def test_out_of_stock_variant_names_the_branch_and_removed_results():
    text = explain_missing_item(
        {
            "candidate_count": 4,
            "selected": "حوله دستی کوچک",
            "selected_in_stock": False,
            "rejected_count": 3,
            "rejected": [{}, {}, {}],
        },
        requested_title="حوله دستی کوچک",
        product_name="حوله",
    )

    assert text == "حوله پیدا شد، اما حوله دستی کوچک در این شعبه موجود نبود؛ ۳ نتیجهٔ نامرتبط حذف شد."


def test_store_timeout_is_not_reported_as_a_definite_miss():
    text = explain_missing_item({"error": "timeout", "candidate_count": 0})
    assert "زمان پاسخ" in text
    assert "قطعی نیست" in text
