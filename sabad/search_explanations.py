"""Short, user-facing explanations for missing or rejected catalog items."""

from collections import Counter
from typing import Any

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa_num(value: int) -> str:
    return str(value).translate(_PERSIAN_DIGITS)


def explain_missing_item(
    evidence: dict[str, Any] | None,
    *,
    requested_title: str = "",
    product_name: str = "",
) -> str:
    """Explain a gap in the form the shopper can act on.

    A typical sentence is: «حوله پیدا شد، اما حوله دستی کوچک در این شعبه موجود
    نبود؛ ۳ نتیجهٔ نامرتبط حذف شد.»
    """
    if not evidence:
        return "عدم موجودی یا عدم یافتن کالا در شعبه فعال این فروشگاه."
    product = (product_name or "").strip() or "کالا"
    requested = (requested_title or str(evidence.get("requested") or "")).strip() or product
    rejected_count = int(evidence.get("rejected_count") or len(evidence.get("rejected") or []))

    def finish(message: str) -> str:
        if rejected_count > 0:
            return f"{message}؛ {_fa_num(rejected_count)} نتیجهٔ نامرتبط حذف شد."
        return message

    error = str(evidence.get("error") or "")
    if error:
        if "timeout" in error.lower():
            return "زمان پاسخ این فروشگاه تمام شد؛ موجود نبودن کالا قطعی نیست."
        return "ارتباط با این فروشگاه در این بررسی برقرار نشد؛ نتیجهٔ ناموجود قطعی نیست."

    candidate_count = int(evidence.get("candidate_count") or 0)
    if candidate_count == 0:
        attempts = evidence.get("queries") or []
        successful = [attempt for attempt in attempts if not attempt.get("error")]
        if successful:
            return "این عبارت‌ها بررسی شدند، اما API فروشگاه نتیجه‌ای برنگرداند؛ ممکن است شعبه یا جست‌وجوی فروشگاه محدود باشد."
        return "پاسخ جست‌وجوی فروشگاه دریافت نشد؛ ناموجودی قطعی نیست."

    if evidence.get("selected_in_stock") is False and evidence.get("selected"):
        return finish(f"{product} پیدا شد، اما {evidence['selected']} در این شعبه موجود نبود")

    rejected = evidence.get("rejected") or []
    reasons = Counter(reason for row in rejected for reason in row.get("reasons", []))
    if reasons:
        top_reason, _count = reasons.most_common(1)[0]
        if "حجم" in top_reason:
            return finish(f"{product} پیدا شد، اما اندازهٔ آن با {requested} جور نبود")
        if "نوع" in top_reason:
            return finish(f"{product} پیدا شد، اما نوع آن با {requested} یکی نبود")
        if "نام پایه" in top_reason or "شباهت" in top_reason:
            return finish(f"نتیجه پیدا شد، اما نام کالا با {requested} به‌اندازهٔ کافی یکی نبود")
        return finish(f"نتیجه پیدا شد، اما با {requested} منطبق نبود")

    if evidence.get("selected_in_stock") is False:
        return finish(f"{product} پیدا شد، اما {requested} در این شعبه موجود نبود")
    return finish(str(evidence.get("final_reason") or "این قلم در این بررسی به سبد اضافه نشد"))
