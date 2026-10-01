"""
Persian text cleaning, Unicode normalization, and Persian/Arabic numeral conversion.
"""

import re

# Persian & Arabic to Western digit mapping
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
WESTERN_DIGITS = "0123456789"

DIGIT_TRANS = str.maketrans(
    PERSIAN_DIGITS + ARABIC_DIGITS,
    WESTERN_DIGITS + WESTERN_DIGITS
)

# Persian verbal numbers to integer
PERSIAN_WORD_NUMBERS = {
    "یک": 1, "یه": 1, "یکی": 1,
    "دو": 2, "دوتا": 2,
    "سه": 3, "سه‌تا": 3, "سه تا": 3,
    "چهار": 4, "چهارتا": 4, "چهار تا": 4,
    "پنج": 5, "پنج‌تا": 5, "پنج تا": 5,
    "شش": 6, "شیش": 6, "شش‌تا": 6, "شش تا": 6,
    "هفت": 7, "هفت‌تا": 7, "هفت تا": 7,
    "هشت": 8, "هشت‌تا": 8, "هشت تا": 8,
    "نه": 9, "نه‌تا": 9, "نه تا": 9,
    "ده": 10, "ده‌تا": 10, "ده تا": 10,
    "نیم": 0.5, "نصف": 0.5,
}


def to_ascii_digits(text: str) -> str:
    """Converts all Persian and Arabic digits in text to standard ASCII digits."""
    if not text:
        return ""
    return text.translate(DIGIT_TRANS)


def clean_persian_text(text: str) -> str:
    """Normalizes Persian characters, removes extra whitespace, and standardizes half-spaces."""
    if not text:
        return ""
    # Standardize Arabic Yeh and Kaf
    text = text.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه")
    # Digits to ASCII
    text = to_ascii_digits(text)
    # Standardize zero-width non-joiner (half-space)
    text = text.replace("\u200c", " ")
    # Replace newlines, commas, and dots used as separators with standard Persian comma
    text = re.sub(r'[\r\n\t]+', ' ', text)
    # Collapse duplicate spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text
