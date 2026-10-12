"""
Sabad UI Assets & E-Commerce Visual Component System.
Inspired by Digikala Jet (دیجی‌کالا جت) and modern Iranian quick-commerce supermarkets.
Provides high-res product photos, SVG vector fallbacks, quick-shelf items, and rich HTML product cards.
"""

import re
import urllib.parse
from typing import Optional, Dict, Tuple, List

from sabad.normalizer.persian_digits import to_ascii_digits


# ---------------------------------------------------------------------------
# Text Normalization & Persian Boundary Matching Helpers
# ---------------------------------------------------------------------------
def _normalize_title(text: str) -> str:
    """Normalizes Persian characters, standardizes ZWNJ, digits, and spacing."""
    if not text:
        return ""
    t = text.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه")
    t = to_ascii_digits(t)
    # Separate attached digits from Persian letters (e.g. 'کره۱۰۰گرم' -> 'کره 100 گرم')
    t = re.sub(r'([\u0600-\u06FF])(\d+)', r'\1 \2', t)
    t = re.sub(r'(\d+)([\u0600-\u06FF])', r'\1 \2', t)
    t = t.replace("\u200c", " ")
    t = t.lower()
    # Normalize common compound phrases
    t = re.sub(r'تخم\s*مرغ', 'تخم مرغ', t)
    t = re.sub(r'آب\s*میوه', 'آبمیوه', t)
    t = re.sub(r'سیب\s*زمینی', 'سیب زمینی', t)
    t = re.sub(r'گوجه\s*فرنگی', 'گوجه فرنگی', t)
    t = re.sub(r'خمیر\s*دندان', 'خمیر دندان', t)
    t = re.sub(r'دست\s*شویی', 'دستشویی', t)
    t = re.sub(r'ظرف\s*شویی', 'ظرفشویی', t)
    t = re.sub(r'لباس\s*شویی', 'لباسشویی', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _has_word(t_norm: str, word: str) -> bool:
    """Matches word as a discrete token within Persian text without false substring collisions."""
    pattern = rf'(?:^|[^\w\u0600-\u06FF]){re.escape(word)}(?:$|[^\w\u0600-\u06FF])'
    return bool(re.search(pattern, t_norm))


def _has_phrase(t_norm: str, phrase: str) -> bool:
    """Matches a phrase or single word using proper word boundaries."""
    if " " in phrase:
        return phrase in t_norm
    return _has_word(t_norm, phrase)


# ---------------------------------------------------------------------------
# SVG Vector Fallback Generator (0ms latency, 100% offline resilient)
# ---------------------------------------------------------------------------
def create_svg_fallback(emoji: str, bg_color: str, title: str) -> str:
    """Creates a lightweight, responsive vector data URI as image fallback."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" width="100%" height="100%">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg_color}" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="{bg_color}" stop-opacity="0.1"/>
    </linearGradient>
  </defs>
  <rect width="160" height="160" rx="20" fill="url(#grad)" stroke="{bg_color}" stroke-width="1.5" stroke-opacity="0.5"/>
  <circle cx="80" cy="70" r="42" fill="#ffffff" fill-opacity="0.9" />
  <text x="80" y="85" font-size="44" text-anchor="middle" dominant-baseline="central">{emoji}</text>
  <text x="80" y="135" font-family="Vazirmatn, sans-serif" font-size="12" font-weight="bold" fill="#334155" text-anchor="middle">{title}</text>
</svg>"""
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


# Known legacy/bogus image IDs that pointed to non-grocery products (phones, cases, boots, gadgets)
BOGUS_LEGACY_IMAGE_PATTERNS = {
    "114945763",  # Phone cases
    "113110298",  # Mobile phone accessories
    "114389025",  # Black boots
    "115168018",  # Electronics / gadgets
    "115159074",  # Non-grocery
    "114972101",  # Non-grocery
    "114402636",  # Non-grocery
    "114389146",  # Non-grocery
    "115160868",  # Non-grocery
    "114777598",  # Non-grocery
    "115159235",  # Non-grocery
}

# Pre-computed curated category vector fallbacks with verified high-res grocery images
CATEGORY_FALLBACKS: Dict[str, Tuple[str, str, str, str]] = {
    # key: (emoji, accent_color, category_title, cdn_image_url)
    "milk": ("🥛", "#3b82f6", "شیر پاستوریزه", "https://dkstatics-public.digikala.com/digikala-products/113df70a77c84301dceee3db0bef3b9c55e9b41d_1701035054.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "cheese": ("🧀", "#f59e0b", "پنیر و صبحانه", "https://dkstatics-public.digikala.com/digikala-products/49b16a765cea3eb6a1ced4c843d30ca3fe07ce9f_1783750845.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "butter": ("🧈", "#eab308", "کره پاستوریزه", "https://dkstatics-public.digikala.com/digikala-products/d1055810db8be202b6d0bd250bdf69005b9bb597_1667285890.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "cream": ("🥛", "#fde047", "خامه صبحانه", "https://dkstatics-public.digikala.com/digikala-products/57499a37e42c50683e137e94efa423e6b996f6f5_1718102990.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "yogurt": ("🥣", "#06b6d4", "ماست و دوغ", "https://dkstatics-public.digikala.com/digikala-products/7b2c5c5859e98af373a8be6da7e9be5e6e39917c_1747651842.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "egg": ("🥚", "#f97316", "تخم مرغ تازه", "https://dkstatics-public.digikala.com/digikala-products/415850b9c7c05bc33cbaecee57942f522ff16ea2_1745144399.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "oil": ("🫒", "#84cc16", "روغن خوراکی", "https://dkstatics-public.digikala.com/digikala-products/5c9bbf9381f70dd62946c42c56594b04861121f7_1652622326.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "rice": ("🍚", "#e2e8f0", "برنج ایرانی", "https://dkstatics-public.digikala.com/digikala-products/25629c0b2a25f54a83813f6a8c79442b83490080_1782662294.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "pasta": ("🍝", "#f59e0b", "ماکارونی و پاستا", "https://dkstatics-public.digikala.com/digikala-products/5a916496b1a92bbee5bb6e43849b005cf09894b6_1657598500.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "legumes": ("🫘", "#a16207", "حبوبات و غلات", "https://dkstatics-public.digikala.com/digikala-products/2543547.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "tomato_paste": ("🥫", "#ef4444", "رب و چاشنی", "https://dkstatics-public.digikala.com/digikala-products/7c391ac4335c87cc49b458650470ac240a6bf7da_1619600774.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "tuna": ("🐟", "#0284c7", "کنسرو تن ماهی", "https://dkstatics-public.digikala.com/digikala-products/3fba53a3010dd4628f7d01bcae56eff637ad7e55_1744810553.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "dishwashing": ("🧴", "#10b981", "مایع ظرفشویی", "https://dkstatics-public.digikala.com/digikala-products/723d422b1d7a727f89b80ae0e43073e4a8194ca3_1770546437.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "handwash": ("🧼", "#06b6d4", "مایع دستشویی", "https://dkstatics-public.digikala.com/digikala-products/176c143a20de9077a0b8d8f36d2f05833504beab_1703057619.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "soap": ("🧼", "#14b8a6", "صابون و بهداشت", "https://dkstatics-public.digikala.com/digikala-products/114916007.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "toothpaste": ("🪥", "#0ea5e9", "بهداشت دهان و دندان", "https://dkstatics-public.digikala.com/digikala-products/7bbcfa3c9b2cf4f2ab79b93910a8f8d9f4640e39_1778076790.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "laundry": ("🧺", "#2563eb", "شوینده لباس", "https://dkstatics-public.digikala.com/digikala-products/7f6ad8d779e94ddc13b29cff87daa80052ef8d10_1723969627.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "cleaning": ("✨", "#3b82f6", "سفیدکننده و نظافت", "https://dkstatics-public.digikala.com/digikala-products/036f58d549c0fc07349b806dbcd36b87158e4f0f_1739358387.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "tissue": ("🧻", "#a855f7", "دستمال کاغذی", "https://dkstatics-public.digikala.com/digikala-products/80c0d139ab95f0ed35594c005e0e2fe8c680e182_1605362214.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "tea": ("🫖", "#92400e", "چای و دمنوش", "https://dkstatics-public.digikala.com/digikala-products/6350c64247e87fc05a1354908c0aa8e4b8008605_1618244476.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "coffee": ("☕", "#78350f", "قهوه و نسکافه", "https://dkstatics-public.digikala.com/digikala-products/46f8a08e5cb7effb6219e9951722803fa0b5b67e_1730799706.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "water": ("💧", "#0284c7", "آب معدنی و آشامیدنی", "https://dkstatics-public.digikala.com/digikala-products/99f8bf0ec0af5bf8518e3613b23e8d0315725868_1723272346.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "beverage": ("🧃", "#ef4444", "نوشیدنی و آبمیوه", "https://dkstatics-public.digikala.com/digikala-products/121228177.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "snack": ("🍪", "#ec4899", "تنقلات و بیسکویت", "https://dkstatics-public.digikala.com/digikala-products/5551340.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "jam": ("🍓", "#e11d48", "مربا و صبحانه", "https://dkstatics-public.digikala.com/digikala-products/a0d97603e705f6b5a2055bb327d78b5cda0660d1_1674888752.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "honey": ("🍯", "#f59e0b", "عسل طبیعی", "https://dkstatics-public.digikala.com/digikala-products/6c15b32ca9b089991d5d49ed6a7255ce881aa732_1758369846.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "sugar": ("🍚", "#94a3b8", "قند و شکر", "https://dkstatics-public.digikala.com/digikala-products/4fe66e970e35f21d8ce3faa5b78b8f4ac76b0c94_1748860813.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "spices": ("🧂", "#f97316", "ادویه و نمک", "https://dkstatics-public.digikala.com/digikala-products/2352215.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "sauce": ("🥫", "#e11d48", "سس و چاشنی", "https://dkstatics-public.digikala.com/digikala-products/aa617945dc69c97fa257b901c51c91e23b74cf22_1694342406.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "bread": ("🍞", "#d97706", "نان و غلات", "https://dkstatics-public.digikala.com/digikala-products/7fb240e2644fa195a372f4cbc18d7d624acfccab_1730896518.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "meat": ("🥩", "#be123c", "گوشت و پروتئین", "https://dkstatics-public.digikala.com/digikala-products/ec9d7252d6f4ab1a89b75d3a325ed092c8d1f73d_1675079001.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "chicken": ("🍗", "#ea580c", "مرغ و طیور", "https://dkstatics-public.digikala.com/digikala-products/cf0bef3ea860a48f24c3d535aba3f623c71b07b0_1762807498.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "produce": ("🥦", "#16a34a", "میوه و سبزیجات", "https://dkstatics-public.digikala.com/digikala-products/0c351a90ea18b5143fb08752c978c05684e41bcd_1641899699.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "shampoo": ("🧴", "#0284c7", "شامپو و بهداشت مو", "https://dkstatics-public.digikala.com/digikala-products/a459092caac996a96de7f2af88954282252cc369_1790693048.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "nuts": ("🥜", "#ca8a04", "آجیل و خشکبار", "https://dkstatics-public.digikala.com/digikala-products/8e31a3e0fb41e4c7d9bf1275dcb762f6bb8b2006_1701199223.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
    "general": ("🛒", "#e11d48", "سوپرمارکت جت", "https://dkstatics-public.digikala.com/digikala-products/664546583ef61a370e6bfc7acae7fa2e18de0bab_1630505330.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80"),
}

# Granular item-specific photo resolutions (matched against title keywords)
SPECIFIC_PRODUCT_MATCHES: List[Tuple[List[str], str, str, str]] = [
    # Milk brands
    (["شیر", "روزانه"], "https://dkstatics-public.digikala.com/digikala-products/3520506.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥛", "شیر روزانه"),
    (["شیر", "کاله"], "https://dkstatics-public.digikala.com/digikala-products/113df70a77c84301dceee3db0bef3b9c55e9b41d_1701035054.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥛", "شیر کاله"),
    (["شیر", "میهن"], "https://dkstatics-public.digikala.com/digikala-products/113df70a77c84301dceee3db0bef3b9c55e9b41d_1701035054.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥛", "شیر میهن"),
    (["شیر", "دامداران"], "https://dkstatics-public.digikala.com/digikala-products/113df70a77c84301dceee3db0bef3b9c55e9b41d_1701035054.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥛", "شیر دامداران"),
    (["شیر", "پگاه"], "https://dkstatics-public.digikala.com/digikala-products/113df70a77c84301dceee3db0bef3b9c55e9b41d_1701035054.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥛", "شیر پگاه"),

    # Breakfast Cream
    (["خامه", "کاله"], "https://dkstatics-public.digikala.com/digikala-products/57499a37e42c50683e137e94efa423e6b996f6f5_1718102990.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥛", "خامه صبحانه کاله"),
    (["خامه", "صبحانه"], "https://dkstatics-public.digikala.com/digikala-products/57499a37e42c50683e137e94efa423e6b996f6f5_1718102990.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥛", "خامه صبحانه"),

    # Butter brands
    (["کره", "کاله"], "https://dkstatics-public.digikala.com/digikala-products/d1055810db8be202b6d0bd250bdf69005b9bb597_1667285890.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧈", "کره کاله"),
    (["کره", "شکلی"], "https://dkstatics-public.digikala.com/digikala-products/111946794.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧈", "کره شکلی"),
    (["کره", "پاک"], "https://dkstatics-public.digikala.com/digikala-products/8ac8b68df71585907b1ed22d5f04cacf87e77b07_1623051026.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧈", "کره پاک"),

    # Cheese
    (["پنیر", "ویلی"], "https://dkstatics-public.digikala.com/digikala-products/49b16a765cea3eb6a1ced4c843d30ca3fe07ce9f_1783750845.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧀", "پنیر ویلی"),
    (["پنیر", "کاله"], "https://dkstatics-public.digikala.com/digikala-products/49b16a765cea3eb6a1ced4c843d30ca3fe07ce9f_1783750845.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧀", "پنیر کاله"),
    (["پنیر", "روزانه"], "https://dkstatics-public.digikala.com/digikala-products/49b16a765cea3eb6a1ced4c843d30ca3fe07ce9f_1783750845.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧀", "پنیر روزانه"),

    # Yogurt & Doogh
    (["ماست", "سون"], "https://dkstatics-public.digikala.com/digikala-products/7b2c5c5859e98af373a8be6da7e9be5e6e39917c_1747651842.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥣", "ماست سون کاله"),

    # Eggs
    (["تخم مرغ"], "https://dkstatics-public.digikala.com/digikala-products/415850b9c7c05bc33cbaecee57942f522ff16ea2_1745144399.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥚", "تخم مرغ ۲۰ عددی"),
    (["تخم‌مرغ"], "https://dkstatics-public.digikala.com/digikala-products/415850b9c7c05bc33cbaecee57942f522ff16ea2_1745144399.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥚", "تخم مرغ ۲۰ عددی"),
    (["تلاونگ"], "https://dkstatics-public.digikala.com/digikala-products/415850b9c7c05bc33cbaecee57942f522ff16ea2_1745144399.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥚", "تخم مرغ تلاونگ"),

    # Oil
    (["روغن", "زیتون"], "https://dkstatics-public.digikala.com/digikala-products/01adc31225568930f78ddb5c5851a75700817cd4_1763893227.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🫒", "روغن زیتون اکسیر"),
    (["روغن", "اکسیر"], "https://dkstatics-public.digikala.com/digikala-products/01adc31225568930f78ddb5c5851a75700817cd4_1763893227.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🫒", "روغن زیتون"),
    (["روغن", "بهار"], "https://dkstatics-public.digikala.com/digikala-products/5c9bbf9381f70dd62946c42c56594b04861121f7_1652622326.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🫒", "روغن بهار"),
    (["روغن", "لادن"], "https://dkstatics-public.digikala.com/digikala-products/5c9bbf9381f70dd62946c42c56594b04861121f7_1652622326.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🫒", "روغن خوراکی"),

    # Rice
    (["برنج", "طارم"], "https://dkstatics-public.digikala.com/digikala-products/25629c0b2a25f54a83813f6a8c79442b83490080_1782662294.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍚", "برنج طارم هاشمی"),
    (["برنج", "هاشمی"], "https://dkstatics-public.digikala.com/digikala-products/25629c0b2a25f54a83813f6a8c79442b83490080_1782662294.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍚", "برنج طارم هاشمی"),

    # Pasta
    (["ماکارونی", "زر"], "https://dkstatics-public.digikala.com/digikala-products/5a916496b1a92bbee5bb6e43849b005cf09894b6_1657598500.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍝", "ماکارونی زر"),
    (["اسپاگتی", "زر"], "https://dkstatics-public.digikala.com/digikala-products/5a916496b1a92bbee5bb6e43849b005cf09894b6_1657598500.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍝", "اسپاگتی زر"),

    # Legumes & Grains
    (["عدس", "گلستان"], "https://dkstatics-public.digikala.com/digikala-products/2543547.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🫘", "عدس گلستان"),
    (["عدس"], "https://dkstatics-public.digikala.com/digikala-products/2543547.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🫘", "عدس بسته‌بندی"),

    # Spices
    (["زردچوبه", "گلستان"], "https://dkstatics-public.digikala.com/digikala-products/2352215.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧂", "زردچوبه گلستان"),
    (["زردچوبه"], "https://dkstatics-public.digikala.com/digikala-products/2352215.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧂", "پودر زردچوبه"),

    # Tomato paste
    (["رب", "روژین"], "https://dkstatics-public.digikala.com/digikala-products/7c391ac4335c87cc49b458650470ac240a6bf7da_1619600774.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥫", "رب روژین"),
    (["رب", "تبرک"], "https://dkstatics-public.digikala.com/digikala-products/7c391ac4335c87cc49b458650470ac240a6bf7da_1619600774.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥫", "رب گوجه"),
    (["رب", "گوجه"], "https://dkstatics-public.digikala.com/digikala-products/7c391ac4335c87cc49b458650470ac240a6bf7da_1619600774.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥫", "رب گوجه فرنگی"),

    # Tuna
    (["تن", "شیلتون"], "https://dkstatics-public.digikala.com/digikala-products/3fba53a3010dd4628f7d01bcae56eff637ad7e55_1744810553.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🐟", "تن ماهی شیلتون"),

    # Water
    (["آب معدنی", "دماوند"], "https://dkstatics-public.digikala.com/digikala-products/99f8bf0ec0af5bf8518e3613b23e8d0315725868_1723272346.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "💧", "آب آشامیدنی دماوند"),
    (["آب", "دماوند"], "https://dkstatics-public.digikala.com/digikala-products/99f8bf0ec0af5bf8518e3613b23e8d0315725868_1723272346.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "💧", "آب دماوند"),

    # Personal Care / Oral / Hygiene
    (["خمیر دندان", "سیگنال"], "https://dkstatics-public.digikala.com/digikala-products/7bbcfa3c9b2cf4f2ab79b93910a8f8d9f4640e39_1778076790.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🪥", "خمیر دندان سیگنال"),
    (["صابون", "گلنار"], "https://dkstatics-public.digikala.com/digikala-products/114916007.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧼", "صابون گلنار"),

    # Cleaning & Household
    (["ظرفشویی", "پریل"], "https://dkstatics-public.digikala.com/digikala-products/723d422b1d7a727f89b80ae0e43073e4a8194ca3_1770546437.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧴", "مایع ظرفشویی پریل"),
    (["دستشویی", "اکتیو"], "https://dkstatics-public.digikala.com/digikala-products/176c143a20de9077a0b8d8f36d2f05833504beab_1703057619.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧼", "مایع دستشویی اکتیو"),
    (["لباسشویی", "پرسیل"], "https://dkstatics-public.digikala.com/digikala-products/7f6ad8d779e94ddc13b29cff87daa80052ef8d10_1723969627.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧺", "مایع لباسشویی پرسیل"),
    (["دستمال", "پاپیا"], "https://dkstatics-public.digikala.com/digikala-products/80c0d139ab95f0ed35594c005e0e2fe8c680e182_1605362214.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧻", "دستمال توالت پاپیا"),
    (["سفید کننده", "گلرنگ"], "https://dkstatics-public.digikala.com/digikala-products/036f58d549c0fc07349b806dbcd36b87158e4f0f_1739358387.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "✨", "سفید کننده گلرنگ"),
    (["وایتکس"], "https://dkstatics-public.digikala.com/digikala-products/036f58d549c0fc07349b806dbcd36b87158e4f0f_1739358387.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "✨", "مایع سفید کننده"),

    # Tea & Coffee
    (["چای", "دوغزال"], "https://dkstatics-public.digikala.com/digikala-products/6350c64247e87fc05a1354908c0aa8e4b8008605_1618244476.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🫖", "چای دوغزال"),
    (["قهوه", "بن مانو"], "https://dkstatics-public.digikala.com/digikala-products/46f8a08e5cb7effb6219e9951722803fa0b5b67e_1730799706.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "☕", "قهوه بن‌مانو"),

    # Jam & Honey & Sugar
    (["مربا", "موسوی"], "https://dkstatics-public.digikala.com/digikala-products/a0d97603e705f6b5a2055bb327d78b5cda0660d1_1674888752.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍓", "مربا آلبالو موسوی"),
    (["عسل", "خوانسار"], "https://dkstatics-public.digikala.com/digikala-products/6c15b32ca9b089991d5d49ed6a7255ce881aa732_1758369846.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍯", "عسل طبیعی خوانسار"),
    (["شکر", "گلها"], "https://dkstatics-public.digikala.com/digikala-products/4fe66e970e35f21d8ce3faa5b78b8f4ac76b0c94_1748860813.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍚", "شکر سفید گلها"),

    # Beverages & Snacks
    (["آبمیوه", "سن ایچ"], "https://dkstatics-public.digikala.com/digikala-products/121228177.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧃", "آبمیوه سن ایچ"),
    (["بیسکویت", "پتی بور"], "https://dkstatics-public.digikala.com/digikala-products/5551340.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍪", "بیسکویت پتی بور"),
    (["پتی بور"], "https://dkstatics-public.digikala.com/digikala-products/5551340.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍪", "بیسکویت پتی بور"),

    # Shampoo & Personal Care
    (["شامپو", "کلیر"], "https://dkstatics-public.digikala.com/digikala-products/a459092caac996a96de7f2af88954282252cc369_1790693048.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧴", "شامپو کلیر"),
    (["پسته"], "https://dkstatics-public.digikala.com/digikala-products/8e31a3e0fb41e4c7d9bf1275dcb762f6bb8b2006_1701199223.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥜", "پسته اکبری"),

    # Produce
    (["خیار"], "https://dkstatics-public.digikala.com/digikala-products/e89a2ae440dc992bb55ee5ccb7355dd44c6b631b_1625306647.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥒", "خیار تازه"),
    (["گوجه"], "https://dkstatics-public.digikala.com/digikala-products/0c351a90ea18b5143fb08752c978c05684e41bcd_1641899699.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍅", "گوجه فرنگی"),
    (["سیب زمینی"], "https://dkstatics-public.digikala.com/digikala-products/8d208dd52debc12c61216cf99fbd856b8031da71_1625308692.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥔", "سیب زمینی"),
    (["پیاز"], "https://dkstatics-public.digikala.com/digikala-products/d8c105a37c1c1b111a23471dc2c1276c093f1e3a_1639988013.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🧅", "پیاز زرد"),

    # Meat & Bakery
    (["مرغ"], "https://dkstatics-public.digikala.com/digikala-products/cf0bef3ea860a48f24c3d535aba3f623c71b07b0_1762807498.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍗", "مرغ تازه"),
    (["گوشت"], "https://dkstatics-public.digikala.com/digikala-products/ec9d7252d6f4ab1a89b75d3a325ed092c8d1f73d_1675079001.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🥩", "گوشت چرخ‌کرده"),
    (["نان"], "https://dkstatics-public.digikala.com/digikala-products/7fb240e2644fa195a372f4cbc18d7d624acfccab_1730896518.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80", "🍞", "نان تست"),
]


def _categorize_title(text: str) -> str:
    """
    Categorizes product title into primary grocery aisle key.
    Uses token boundary matching and prioritized hierarchy to prevent false substring collisions
    (e.g., 'نان بربری' or 'شامپو موهای چرب' matching 'رب', 'شیرینی' matching 'شیر', 'آبمیوه' matching 'میوه').
    """
    t = _normalize_title(text)
    if not t:
        return "general"

    # 1. Eggs (prioritized before chicken)
    if any(_has_phrase(t, p) for p in ["تخم مرغ", "تخم بلدرچین", "egg", "تلاونگ"]):
        return "egg"

    # 2. Bread & Bakery (prioritized early to protect 'بربری' from 'رب')
    if any(_has_phrase(t, p) for p in ["نان", "بربری", "سنگک", "لواش", "تافتون", "باگت", "تست", "نان سحر"]):
        return "bread"

    # 3. Breakfast Dairy: Cream & Clotted Cream (prioritized before butter and milk)
    if any(_has_phrase(t, p) for p in ["خامه", "سرشیر", "قیماق"]):
        return "cream"

    # 4. Milk (word-boundary matched to protect 'شیرینی' and 'شیره')
    if any(_has_phrase(t, p) for p in ["شیر", "milk"]):
        return "milk"

    # 5. Cheese
    if any(_has_phrase(t, p) for p in ["پنیر", "ویلی", "فتا", "چدار", "گودا", "موزارلا", "پیتزا", "لیقوان"]):
        return "cheese"

    # 6. Butter
    if any(_has_phrase(t, p) for p in ["کره"]):
        return "butter"

    # 7. Yogurt, Doogh, Kashk
    if any(_has_phrase(t, p) for p in ["ماست", "سون", "دوغ", "کشک"]):
        return "yogurt"

    # 8. Cooking Oil
    if any(_has_phrase(t, p) for p in ["روغن", "oil"]):
        return "oil"

    # 9. Rice
    if any(_has_phrase(t, p) for p in ["برنج", "طارم", "هاشمی", "دمسیاه", "rice"]):
        return "rice"

    # 10. Pasta & Noodles
    if any(_has_phrase(t, p) for p in ["ماکارونی", "اسپاگتی", "لازانیا", "پاستا", "ورمیشل", "رشته پلویی", "رشته آش", "نودل"]):
        return "pasta"

    # 11. Legumes & Grains
    if any(_has_phrase(t, p) for p in ["عدس", "لوبیا", "نخود", "لپه", "سویا"]):
        return "legumes"

    # 12. Tuna & Canned fish
    if any(_has_phrase(t, p) for p in ["تن ماهی", "شیلتون", "ماهی تن", "کنسرو ماهی"]):
        return "tuna"

    # 13. Confectionery / Sweets / Biscuits / Snacks (prioritized before honey to protect brands like 'شیرین عسل')
    if any(_has_phrase(t, p) for p in ["بیسکویت", "بیسکوئیت", "ویفر", "پتی بور", "شکلات", "چیپس", "پفک", "کیک", "کلوچه", "کوکی", "شیرینی", "تخم شربتی"]):
        return "snack"

    # 14. Jam & Breakfast spreads
    if any(_has_phrase(t, p) for p in ["مربا", "مربای", "مارمالاد", "حلوا شکری", "ارده", "کرم کنجد", "شیره خرما", "شیره انگور", "شیره"]):
        return "jam"

    # 15. Honey
    if any(_has_phrase(t, p) for p in ["عسل", "honey"]):
        return "honey"

    # 16. Sugar & Sugar cubes
    if any(_has_phrase(t, p) for p in ["شکر", "قند", "نبات"]):
        return "sugar"

    # 17. Tomato Paste & Pomegranate paste (clean word matching to protect 'بربری' and 'چرب')
    if any(_has_phrase(t, p) for p in ["رب گوجه", "رب انار", "رب نارنج", "رب"]):
        return "tomato_paste"

    # 18. Tea & Herbal Infusions
    if any(_has_phrase(t, p) for p in ["چای", "دمنوش", "تی بگ", "دوغزال", "گلستان", "ارل گری"]):
        return "tea"

    # 19. Coffee
    if any(_has_phrase(t, p) for p in ["قهوه", "اسپرسو", "نسکافه", "کاپوچینو", "هات چاکلت", "بن مانو", "بن‌مانو"]):
        return "coffee"

    # 20. Water
    if any(_has_phrase(t, p) for p in ["آب معدنی", "آب آشامیدنی", "اب معدنی", "دماوند"]):
        return "water"

    # 21. Beverage (prioritized before produce to protect 'آبمیوه')
    if any(_has_phrase(t, p) for p in ["آبمیوه", "نوشابه", "دلستر", "ماءالشعیر", "کوکاکولا", "پپسی", "سن ایچ", "سن‌ایچ", "رانی", "شربت"]):
        return "beverage"

    # 22. Personal Care & Hygiene
    if any(_has_phrase(t, p) for p in ["خمیر دندان", "خمیردندان", "مسواک", "دهانشویه"]):
        return "toothpaste"
    if any(_has_phrase(t, p) for p in ["شامپو", "نرم کننده مو", "ماسک مو", "سر شوی"]):
        return "shampoo"
    if any(_has_phrase(t, p) for p in ["صابون"]):
        return "soap"
    if any(_has_phrase(t, p) for p in ["دستشویی", "مایع دستشویی", "مایع دست"]):
        return "handwash"

    # 23. Cleaning & Household Chemicals
    if any(_has_phrase(t, p) for p in ["ظرفشویی", "مایع ظرفشویی", "پریل", "خاکستر"]):
        return "dishwashing"
    if any(_has_phrase(t, p) for p in ["لباسشویی", "مایع لباسشویی", "پودر لباسشویی", "پرسیل", "تاژ"]):
        return "laundry"
    if any(_has_phrase(t, p) for p in ["سفید کننده", "وایتکس", "جرم گیر", "شیشه پاک کن", "شیشه شور", "ضدعفونی", "دامستوس"]):
        return "cleaning"
    if any(_has_phrase(t, p) for p in ["دستمال", "دستمال کاغذی", "دستمال توالت", "پاپیا", "سافتلن", "دلسی", "نوار بهداشتی", "پوشک"]):
        return "tissue"

    # 24. Nuts & Dried Fruits
    if any(_has_phrase(t, p) for p in ["پسته", "بادام", "گردو", "فندق", "آجیل", "تخمه", "تخم کدو", "تخم آفتابگردان", "کشمش", "خرما"]):
        return "nuts"

    # 25. Meat & Poultry
    if any(_has_phrase(t, p) for p in ["مرغ", "جوجه", "بوقلمون", "فیله مرغ", "سینه مرغ", "ران مرغ", "شنیسل"]):
        if not _has_phrase(t, "تخم"):
            return "chicken"
    if any(_has_phrase(t, p) for p in ["گوشت", "چرخ کرده", "چرخ‌کرده", "گوسفندی", "گوساله", "استیک", "خورشتی", "ماهیچه"]):
        return "meat"

    # 26. Fresh Produce
    if any(_has_phrase(t, p) for p in ["خیار", "گوجه", "سیب زمینی", "پیاز", "سبزی", "میوه", "سیب", "موز", "پرتقال", "لیمو", "کاهو", "هویج", "سیر", "قارچ", "کلم", "بادمجان", "کدو"]):
        return "produce"

    # 27. Spices & Condiments
    if any(_has_phrase(t, p) for p in ["نمک", "زردچوبه", "فلفل", "دارچین", "زعفران", "آویشن", "ادویه", "کاری", "زنجبیل"]):
        return "spices"
    if any(_has_phrase(t, p) for p in ["سس", "مایونز", "کچاپ", "خردل", "هزارجزیره", "باربیکیو"]):
        return "sauce"

    return "general"


def resolve_product_image_and_fallback(title: str, explicit_url: Optional[str] = None) -> Tuple[str, str]:
    """
    Resolves the main image URL and an inline SVG data URI fallback for any grocery item title.
    If explicit_url is provided and valid (and not an obsolete placeholder), it is prioritized.
    Otherwise, matches against specific brand/product keywords or curated category fallbacks.
    """
    t_norm = _normalize_title(title or "")

    # Reject obsolete/bogus image IDs that pointed to non-grocery products
    if explicit_url and isinstance(explicit_url, str):
        cleaned_url = explicit_url.strip()
        if cleaned_url.startswith("http") and not any(bogus in cleaned_url for bogus in BOGUS_LEGACY_IMAGE_PATTERNS):
            cat_key = _categorize_title(t_norm)
            emoji, color, cat_title, _ = CATEGORY_FALLBACKS[cat_key]
            return cleaned_url, create_svg_fallback(emoji, color, cat_title)

    # 1. Check specific product/brand matches first
    for keywords, spec_url, emoji, spec_title in SPECIFIC_PRODUCT_MATCHES:
        if "مرغ" in keywords and _has_phrase(t_norm, "تخم"):
            continue
        if "گوجه" in keywords and ("رب" in t_norm or _has_phrase(t_norm, "رب")):
            continue
        if "شیر" in keywords and any(_has_phrase(t_norm, w) for w in ["شیرینی", "شیره"]):
            continue
        if "کره" in keywords and any(w in t_norm for w in ["بادام زمینی", "پسته", "فندق"]):
            continue
        if all(_has_phrase(t_norm, k) for k in keywords):
            cat_key = _categorize_title(t_norm)
            _, color, _, _ = CATEGORY_FALLBACKS[cat_key]
            fallback_uri = create_svg_fallback(emoji, color, spec_title)
            return spec_url, fallback_uri

    # 2. General category match
    cat_key = _categorize_title(t_norm)
    emoji, color, cat_title, default_cdn = CATEGORY_FALLBACKS[cat_key]
    fallback_uri = create_svg_fallback(emoji, color, cat_title)
    return default_cdn, fallback_uri


# ---------------------------------------------------------------------------
# Popular Grocery Essentials Shelf for Novice Users
# Organized by Everyday Supermarket Aisles
# ---------------------------------------------------------------------------
POPULAR_SHELF_ITEMS: List[Dict] = [
    # Category 1: لبنیات و صبحانه
    {
        "id": "milk_kaleh",
        "title": "شیر پرچرب کاله ۱ لیتری",
        "brand": "کاله",
        "category": "لبنیات و صبحانه",
        "raw_text": "یک شیر پرچرب کاله ۱ لیتری",
        "emoji": "🥛",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/113df70a77c84301dceee3db0bef3b9c55e9b41d_1701035054.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 37800,
        "old_price_approx": 42000,
        "discount_percent": 10,
    },
    {
        "id": "cheese_vili",
        "title": "پنیر خامه‌ای ویلی کاله ۳۵۰ گرمی",
        "brand": "ویلی",
        "category": "لبنیات و صبحانه",
        "raw_text": "یک پنیر ویلی ۳۵۰ گرمی",
        "emoji": "🧀",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/49b16a765cea3eb6a1ced4c843d30ca3fe07ce9f_1783750845.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 48000,
        "old_price_approx": 56000,
        "discount_percent": 14,
    },
    {
        "id": "butter_kaleh",
        "title": "کره پاستوریزه کاله ۱۰۰ گرمی",
        "brand": "کاله",
        "category": "لبنیات و صبحانه",
        "raw_text": "یک کره ۱۰۰ گرمی",
        "emoji": "🧈",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/d1055810db8be202b6d0bd250bdf69005b9bb597_1667285890.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 35000,
        "old_price_approx": 38000,
        "discount_percent": 8,
    },
    {
        "id": "eggs_pack",
        "title": "تخم مرغ ۲۰ عددی تلاونگ",
        "brand": "تلاونگ",
        "category": "لبنیات و صبحانه",
        "raw_text": "یک بسته تخم مرغ",
        "emoji": "🥚",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/415850b9c7c05bc33cbaecee57942f522ff16ea2_1745144399.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 125000,
        "old_price_approx": 145000,
        "discount_percent": 14,
    },
    # Category 2: خواربار و پخت‌وپز
    {
        "id": "oil_bahar",
        "title": "روغن آفتابگردان پخت‌وپز ۱.۵ لیتری",
        "brand": "بهار",
        "category": "خواربار و پخت‌وپز",
        "raw_text": "یک روغن مایع ۱.۵ لیتری",
        "emoji": "🫒",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/5c9bbf9381f70dd62946c42c56594b04861121f7_1652622326.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 115000,
        "old_price_approx": 130000,
        "discount_percent": 11,
    },
    {
        "id": "pasta_zar",
        "title": "ماکارونی رشته‌ای زر ماکارون ۷۰۰ گرمی",
        "brand": "زر ماکارون",
        "category": "خواربار و پخت‌وپز",
        "raw_text": "یک ماکارونی ۷۰۰ گرمی",
        "emoji": "🍝",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/5a916496b1a92bbee5bb6e43849b005cf09894b6_1657598500.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 28000,
        "old_price_approx": 32000,
        "discount_percent": 12,
    },
    {
        "id": "tuna_shilton",
        "title": "کنسرو تن ماهی در روغن شیلتون ۱۸۰ گرم",
        "brand": "شیلتون",
        "category": "خواربار و پخت‌وپز",
        "raw_text": "یک کنسرو تن ماهی",
        "emoji": "🐟",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/3fba53a3010dd4628f7d01bcae56eff637ad7e55_1744810553.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 79000,
        "old_price_approx": 92000,
        "discount_percent": 14,
    },
    {
        "id": "tomato_paste_tabarok",
        "title": "رب گوجه فرنگی تبرک ۸۰۰ گرمی",
        "brand": "تبرک",
        "category": "خواربار و پخت‌وپز",
        "raw_text": "یک رب گوجه فرنگی",
        "emoji": "🥫",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/7c391ac4335c87cc49b458650470ac240a6bf7da_1619600774.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 59000,
        "old_price_approx": 68000,
        "discount_percent": 13,
    },
    # Category 3: شوینده و بهداشتی
    {
        "id": "pril_4l",
        "title": "مایع ظرفشویی پریل لیمو ۴ لیتری",
        "brand": "پریل",
        "category": "شوینده و بهداشتی",
        "raw_text": "یک مایع ظرفشویی پریل ۴ لیتری",
        "emoji": "🧴",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/723d422b1d7a727f89b80ae0e43073e4a8194ca3_1770546437.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 162000,
        "old_price_approx": 180000,
        "discount_percent": 10,
    },
    {
        "id": "handwash_active",
        "title": "مایع دستشویی کرمی اکتیو ۴۵۰ گرمی",
        "brand": "اکتیو",
        "category": "شوینده و بهداشتی",
        "raw_text": "یک مایع دستشویی اکتیو",
        "emoji": "🧼",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/176c143a20de9077a0b8d8f36d2f05833504beab_1703057619.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 42000,
        "old_price_approx": 49000,
        "discount_percent": 14,
    },
    {
        "id": "tissue_papia",
        "title": "دستمال توالت ۴ قلوی پاپیا ۳ لایه",
        "brand": "پاپیا",
        "category": "شوینده و بهداشتی",
        "raw_text": "یک دستمال توالت پاپیا",
        "emoji": "🧻",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/80c0d139ab95f0ed35594c005e0e2fe8c680e182_1605362214.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 89000,
        "old_price_approx": 105000,
        "discount_percent": 15,
    },
    {
        "id": "persil_laundry",
        "title": "ژل مایع لباسشویی پرسیل ۲.۷ لیتری",
        "brand": "پرسیل",
        "category": "شوینده و بهداشتی",
        "raw_text": "یک مایع لباسشویی پرسیل",
        "emoji": "🧺",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/7f6ad8d779e94ddc13b29cff87daa80052ef8d10_1723969627.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 195000,
        "old_price_approx": 225000,
        "discount_percent": 13,
    },
    # Category 4: نوشیدنی و تنقلات
    {
        "id": "tea_doghazal",
        "title": "چای سیلان ارل گری دوغزال ۵۰۰ گرم",
        "brand": "دوغزال",
        "category": "نوشیدنی و تنقلات",
        "raw_text": "یک بسته چای دوغزال",
        "emoji": "🫖",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/6350c64247e87fc05a1354908c0aa8e4b8008605_1618244476.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 285000,
        "old_price_approx": 320000,
        "discount_percent": 11,
    },
    {
        "id": "juice_sunich",
        "title": "آبمیوه پرتقال ۱ لیتری سن‌ایچ",
        "brand": "سن ایچ",
        "category": "نوشیدنی و تنقلات",
        "raw_text": "یک آبمیوه سن ایچ",
        "emoji": "🧃",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/121228177.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 45000,
        "old_price_approx": 52000,
        "discount_percent": 13,
    },
    {
        "id": "biscuits_petibor",
        "title": "بیسکویت پتی بور وانیلی مینو ۱۲۵ گرم",
        "brand": "مینو",
        "category": "نوشیدنی و تنقلات",
        "raw_text": "یک بسته بیسکویت پتی بور",
        "emoji": "🍪",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/5551340.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 18000,
        "old_price_approx": 20000,
        "discount_percent": 10,
    },
    {
        "id": "honey_nature",
        "title": "عسل طبیعی خوانسار ۵۰۰ گرمی",
        "brand": "طبیعی",
        "category": "لبنیات و صبحانه",
        "raw_text": "یک عسل طبیعی",
        "emoji": "🍯",
        "image_url": "https://dkstatics-public.digikala.com/digikala-products/6c15b32ca9b089991d5d49ed6a7255ce881aa732_1758369846.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        "price_approx": 145000,
        "old_price_approx": 170000,
        "discount_percent": 15,
    },
]


# ---------------------------------------------------------------------------
# HTML Product Card Generator (Digikala Jet Aesthetics)
# ---------------------------------------------------------------------------
STORE_METADATA = {
    "digikala_jet": {
        "title_fa": "دیجی‌کالا جت",
        "color": "#E6123D",
        "bg_soft": "#FEF2F2",
        "border_color": "#FECACA",
        "icon": "🔴",
        "badge_class": "badge-jet",
        "delivery_badge": "⚡ ارسال جت (۳۰ دقیقه)",
    },
    "snapp_market": {
        "title_fa": "اسنپ‌مارکت",
        "color": "#D97706",
        "bg_soft": "#FFFBEB",
        "border_color": "#FDE68A",
        "icon": "🟡",
        "badge_class": "badge-snapp",
        "delivery_badge": "🛵 تحویل اکسپرس هایپراستار",
    },
    "okala": {
        "title_fa": "افق کوروش / اکالا",
        "color": "#059669",
        "bg_soft": "#ECFDF5",
        "border_color": "#A7F3D0",
        "icon": "🟢",
        "badge_class": "badge-okala",
        "delivery_badge": "🛒 تحویل از نزدیک‌ترین شعبه",
    },
    "tapsi_market": {
        "title_fa": "تپسی مارکت",
        "color": "#2563EB",
        "bg_soft": "#EFF6FF",
        "border_color": "#BFDBFE",
        "icon": "🔵",
        "badge_class": "badge-tapsi",
        "delivery_badge": "⚡ تحویل سریع تپسی",
    },
}


def render_jet_product_card_html(
    product_title: str,
    requested_title: str,
    platform: str,
    price: float,
    base_price: float,
    quantity: int,
    image_url: Optional[str] = None,
    is_in_stock: bool = True,
    discount_percent: float = 0.0,
    store_title_override: Optional[str] = None,
) -> str:
    """
    Renders an Iranian e-commerce product card inspired by Digikala Jet's UI.
    Includes product photo with SVG fallback, discount badge, strikethrough price, and quantity.
    """
    store_info = STORE_METADATA.get(platform, {
        "title_fa": store_title_override or platform,
        "color": "#475569",
        "bg_soft": "#F1F5F9",
        "border_color": "#CBD5E1",
        "icon": "🏬",
        "badge_class": "badge-default",
        "delivery_badge": "تحویل سوپرمارکت",
    })
    store_name = store_title_override or store_info["title_fa"]
    img_src, fallback_uri = resolve_product_image_and_fallback(product_title, image_url)
    
    line_total = price * quantity
    line_saving = max(0.0, (base_price - price) * quantity)
    
    # Calculate discount percent if not provided
    if discount_percent <= 0 and base_price > price > 0:
        discount_percent = round(((base_price - price) / base_price) * 100)

    discount_badge_html = ""
    if discount_percent > 0:
        discount_badge_html = f'<div class="jet-card-discount-badge">{int(discount_percent)}٪ تخفیف</div>'

    old_price_html = ""
    if base_price > price:
        old_price_html = f'<span class="jet-card-old-price">{base_price:,.0f}</span>'

    stock_badge_html = (
        '<span class="jet-card-stock-in">✅ موجود در شعبه</span>'
        if is_in_stock
        else '<span class="jet-card-stock-out">⚠️ ناموجود</span>'
    )

    saving_badge_html = ""
    if line_saving > 0:
        saving_badge_html = f'<div class="jet-card-saving-pill">🎁 سود شما: {line_saving:,.0f} تومان</div>'

    html = f"""
<div class="jet-product-card">
  <div class="jet-card-header-bar">
    <span class="jet-store-chip" style="background-color:{store_info['bg_soft']}; color:{store_info['color']}; border:1px solid {store_info['border_color']};">
      {store_info['icon']} {store_name}
    </span>
    {discount_badge_html}
  </div>

  <div class="jet-card-img-container">
    <img
      src="{img_src}"
      alt="{product_title}"
      class="jet-card-img"
      loading="lazy"
      onerror="this.onerror=null; this.src='{fallback_uri}';"
    />
  </div>

  <div class="jet-card-content">
    <div class="jet-card-req-title">درخواستی: {requested_title}</div>
    <div class="jet-card-product-title" title="{product_title}">{product_title}</div>
    
    <div class="jet-card-meta-row">
      {stock_badge_html}
      <span class="jet-card-qty-badge">{quantity} عدد</span>
    </div>

    <div class="jet-card-price-container">
      <div class="jet-card-price-primary">
        <span class="jet-price-digits">{price:,.0f}</span>
        <span class="jet-currency-unit">تومان</span>
      </div>
      {old_price_html}
    </div>

    <div class="jet-card-footer-summary">
      <div class="jet-card-line-total">جمع ردیف: <b>{line_total:,.0f} تومان</b></div>
      {saving_badge_html}
    </div>
  </div>
</div>
"""
    return html


def render_selected_cart_card_html(
    title: str,
    brand: Optional[str] = None,
    quantity: int = 1,
    volume_spec: Optional[str] = None,
    image_url: Optional[str] = None,
) -> str:
    """
    Renders a compact, beginner-friendly Digikala Jet product card for items
    selected in the user's active shopping cart, showing the product photo,
    brand badge, quantity tag, and title.
    """
    search_term = f"{title} {brand}" if brand and brand not in title else title
    img_src, fallback_uri = resolve_product_image_and_fallback(search_term, image_url)
    brand_display = brand or "برند آزاد"
    vol_html = f'<span class="jet-cart-vol-badge">{volume_spec}</span>' if volume_spec else ""

    html = f"""
<div class="jet-cart-item-card">
  <div class="jet-cart-card-top">
    <span class="jet-cart-brand-tag">🏷️ {brand_display}</span>
    <span class="jet-cart-qty-tag">{quantity} عدد</span>
  </div>
  <div class="jet-cart-img-box">
    <img
      src="{img_src}"
      alt="{title}"
      class="jet-cart-img"
      loading="lazy"
      onerror="this.onerror=null; this.src='{fallback_uri}';"
    />
  </div>
  <div class="jet-cart-info">
    <div class="jet-cart-title" title="{title}">{title}</div>
    <div class="jet-cart-subrow">
      {vol_html}
      <span class="jet-cart-ready-chip">⚡ آماده استعلام قیمت</span>
    </div>
  </div>
</div>
"""
    return html


# ---------------------------------------------------------------------------
# High-Discount Curated Daily Flash Deals (40% to 70% Discounts)
# ---------------------------------------------------------------------------
CURATED_FLASH_DEALS_BY_STORE: Dict[str, List[Dict]] = {
    "digikala_jet": [
        {
            "product_id": "jet_deal_tuna",
            "title": "کنسرو تن ماهی در روغن شیلتون ۱۸۰ گرمی",
            "brand": "شیلتون",
            "base_price": 95000.0,
            "discount_price": 38000.0,
            "discount_percent": 60.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/3fba53a3010dd4628f7d01bcae56eff637ad7e55_1744810553.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
        {
            "product_id": "jet_deal_tea",
            "title": "چای سیاه ارل گری سیلان دوغزال ۵۰۰ گرمی",
            "brand": "دوغزال",
            "base_price": 240000.0,
            "discount_price": 96000.0,
            "discount_percent": 60.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/6350c64247e87fc05a1354908c0aa8e4b8008605_1618244476.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
        {
            "product_id": "jet_deal_pril",
            "title": "مایع ظرفشویی پریل لیمو ۴ لیتری",
            "brand": "پریل",
            "base_price": 180000.0,
            "discount_price": 72000.0,
            "discount_percent": 60.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/723d422b1d7a727f89b80ae0e43073e4a8194ca3_1770546437.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
        {
            "product_id": "jet_deal_cheese",
            "title": "پنیر خامه‌ای ویلی کاله ۳۵۰ گرمی",
            "brand": "کاله",
            "base_price": 70000.0,
            "discount_price": 35000.0,
            "discount_percent": 50.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/49b16a765cea3eb6a1ced4c843d30ca3fe07ce9f_1783750845.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
    ],
    "snapp_market": [
        {
            "product_id": "snapp_deal_oil",
            "title": "روغن زیتون فرابکر اکسیر ۱ لیتری",
            "brand": "اکسیر",
            "base_price": 320000.0,
            "discount_price": 128000.0,
            "discount_percent": 60.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/01adc31225568930f78ddb5c5851a75700817cd4_1763893227.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
        {
            "product_id": "snapp_deal_rice",
            "title": "برنج طارم هاشمی معطر ۱۰ کیلویی",
            "brand": "گلستان",
            "base_price": 650000.0,
            "discount_price": 357500.0,
            "discount_percent": 45.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/25629c0b2a25f54a83813f6a8c79442b83490080_1782662294.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
        {
            "product_id": "snapp_deal_tissue",
            "title": "دستمال توالت ۸ قلوی پاپیا ۳ لایه",
            "brand": "پاپیا",
            "base_price": 280000.0,
            "discount_price": 112000.0,
            "discount_percent": 60.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/80c0d139ab95f0ed35594c005e0e2fe8c680e182_1605362214.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
        {
            "product_id": "snapp_deal_persil",
            "title": "ژل مایع لباسشویی پرسیل ۲.۷ لیتری",
            "brand": "پرسیل",
            "base_price": 210000.0,
            "discount_price": 84000.0,
            "discount_percent": 60.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/7f6ad8d779e94ddc13b29cff87daa80052ef8d10_1723969627.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
    ],
    "okala": [
        {
            "product_id": "okala_deal_coffee",
            "title": "دانه قهوه اسپرسو ۱۰۰٪ عربیکا بن‌مانو ۲۵۰ گرمی",
            "brand": "بن مانو",
            "base_price": 200000.0,
            "discount_price": 60000.0,
            "discount_percent": 70.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/46f8a08e5cb7effb6219e9951722803fa0b5b67e_1730799706.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
        {
            "product_id": "okala_deal_tuna",
            "title": "کنسرو ماهی تن در روغن زیتون شیلتون ۱۸۰ گرمی",
            "brand": "شیلتون",
            "base_price": 110000.0,
            "discount_price": 44000.0,
            "discount_percent": 60.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/3fba53a3010dd4628f7d01bcae56eff637ad7e55_1744810553.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
        {
            "product_id": "okala_deal_tomato",
            "title": "رب گوجه فرنگی قوطی روژین ۸۰۰ گرمی",
            "brand": "روژین",
            "base_price": 80000.0,
            "discount_price": 40000.0,
            "discount_percent": 50.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/7c391ac4335c87cc49b458650470ac240a6bf7da_1619600774.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
        {
            "product_id": "okala_deal_shampoo",
            "title": "شامپو ضدشوره آقایان کلیر ۴۰۰ میلی‌لیتری",
            "brand": "کلیر",
            "base_price": 160000.0,
            "discount_price": 64000.0,
            "discount_percent": 60.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/a459092caac996a96de7f2af88954282252cc369_1790693048.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
    ],
    "tapsi_market": [
        {
            "product_id": "tapsi_deal_honey",
            "title": "عسل خالص گون و آویشن خوانسار ۱۰۰۰ گرمی",
            "brand": "خوانسار",
            "base_price": 280000.0,
            "discount_price": 112000.0,
            "discount_percent": 60.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/6c15b32ca9b089991d5d49ed6a7255ce881aa732_1758369846.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
        {
            "product_id": "tapsi_deal_pistachio",
            "title": "پسته اکبری بوداده زعفرانی ۲۵۰ گرمی",
            "brand": "تواضع",
            "base_price": 380000.0,
            "discount_price": 190000.0,
            "discount_percent": 50.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/8e31a3e0fb41e4c7d9bf1275dcb762f6bb8b2006_1701199223.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
        {
            "product_id": "tapsi_deal_milk",
            "title": "شیر پرچرب بطری کاله ۱ لیتری",
            "brand": "کاله",
            "base_price": 46000.0,
            "discount_price": 23000.0,
            "discount_percent": 50.0,
            "is_flash_deal": True,
            "image_url": "https://dkstatics-public.digikala.com/digikala-products/113df70a77c84301dceee3db0bef3b9c55e9b41d_1701035054.jpg?x-oss-process=image/resize,m_lfit,h_300,w_300/quality,q_80",
        },
    ],
}


def get_default_flash_deals() -> Dict[str, List]:
    """Returns fallback StoreItem instances for daily flash deals across all supported platforms."""
    from sabad.models.catalog import StoreItem
    deals_by_store: Dict[str, List[StoreItem]] = {}
    for platform, items in CURATED_FLASH_DEALS_BY_STORE.items():
        deals_by_store[platform] = [
            StoreItem(
                platform=platform,
                store_id=f"{platform}_flash",
                product_id=it["product_id"],
                title=it["title"],
                brand=it.get("brand"),
                base_price=it["base_price"],
                discount_price=it["discount_price"],
                discount_percent=it["discount_percent"],
                is_flash_deal=True,
                is_in_stock=True,
                image_url=it.get("image_url"),
            )
            for it in items
        ]
    return deals_by_store


def render_flash_deal_opportunity_card_html(
    title: str,
    platform: str,
    base_price: float,
    discount_price: float,
    discount_percent: float,
    opportunity_type: str,
    benefit_highlight: str,
    image_url: Optional[str] = None,
    store_title_override: Optional[str] = None,
) -> str:
    """
    Renders a promotional card for a 40%-70% flash deal opportunity.
    Supports 'same_store_addon' (same-store bonus) and 'store_switch_deal' (golden store switch).
    """
    img_src, fallback_uri = resolve_product_image_and_fallback(title, image_url)
    store_info = STORE_METADATA.get(platform, {
        "title_fa": store_title_override or platform,
        "color": "#E11D48",
        "bg_soft": "#FFF1F2",
        "border_color": "#FECDD3",
        "icon": "⚡",
        "badge_class": "badge-jet",
    })
    store_title = store_title_override or store_info["title_fa"]
    saving_amount = max(0.0, base_price - discount_price)

    is_switch = opportunity_type == "store_switch_deal"
    badge_label = "🔥 فرصت تغییر فروشگاه" if is_switch else "🎁 تخفیف از همین فروشگاه"
    badge_color = "#B45309" if is_switch else "#047857"
    badge_bg = "#FEF3C7" if is_switch else "#D1FAE5"

    html = f"""
<div class="deal-opportunity-card" style="border: 2px solid {store_info['border_color']}; background: #ffffff; border-radius: 14px; padding: 14px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: right; direction: rtl;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
    <span style="background: {badge_bg}; color: {badge_color}; font-weight: 800; font-size: 0.8rem; padding: 3px 10px; border-radius: 9999px;">{badge_label}</span>
    <span style="background: {store_info['bg_soft']}; color: {store_info['color']}; font-weight: 700; font-size: 0.8rem; padding: 3px 10px; border-radius: 9999px; border: 1px solid {store_info['border_color']};">{store_info['icon']} {store_title}</span>
  </div>
  <div style="display: flex; gap: 14px; align-items: center;">
    <div style="width: 80px; height: 80px; flex-shrink: 0; background: #f8fafc; border-radius: 10px; overflow: hidden; display: flex; align-items: center; justify-content: center; position: relative;">
      <img src="{img_src}" alt="{title}" style="max-width: 100%; max-height: 100%; object-fit: contain;" onerror="this.onerror=null; this.src='{fallback_uri}';" />
      <span style="position: absolute; top: 4px; right: 4px; background: #dc2626; color: #fff; font-size: 0.7rem; font-weight: 800; padding: 2px 5px; border-radius: 4px;">%{discount_percent:.0f}</span>
    </div>
    <div style="flex-grow: 1;">
      <div style="font-weight: 700; font-size: 0.95rem; color: #1e293b; margin-bottom: 4px;">{title}</div>
      <div style="display: flex; gap: 8px; align-items: baseline; margin-bottom: 4px;">
        <span style="font-size: 1.1rem; font-weight: 900; color: #dc2626;">{discount_price:,.0f} تومان</span>
        <span style="font-size: 0.85rem; color: #94a3b8; text-decoration: line-through;">{base_price:,.0f} تومان</span>
        <span style="font-size: 0.75rem; color: #059669; font-weight: 700;">(سود: {saving_amount:,.0f} ت)</span>
      </div>
      <div style="font-size: 0.82rem; color: #475569; background: #f1f5f9; padding: 6px 10px; border-radius: 8px;">
        💡 {benefit_highlight}
      </div>
    </div>
  </div>
</div>
"""
    return html


