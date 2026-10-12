# Spec 04: Persian NLP & Strict SKU Matcher

> **Status**: Approved & Verified  
> **Source Directory**: `sabad/normalizer/`  
> **Key Modules**: `persian_digits.py`, `parser.py`, `matcher.py`, `gemini_parser.py`

---

## 1. Persian Text & Numeral Normalization

### Digit Normalizer (`persian_digits.py`)
Converts both Eastern-Arabic (`٠-٩`) and Persian-Urdu (`۰-۹`) characters into standard ASCII digits (`0-9`).
Replaces Persian momayyez (`٫`) with standard decimal points (`.`).

### Clean Text Function
- Replaces Arabic Yeh (`ي`) and Kaf (`ك`) with Persian equivalents (`ی` and `ک`).
- Replaces non-breaking half-spaces (`\u200c`) with standard spaces to ensure uniform tokenization.
- Strips surrounding quotes, asterisks, and excessive whitespace.

---

## 2. Quantity & Volume Parsing Rules (`parser.py`)

### Verbal Volume Mapping (`VERBAL_VOL_PATTERNS`)
Handles colloquial Persian size phrases:
- `"یک و نیم لیتری"` / `"یه و نیم لیتری"` ➔ `1.5 لیتر`
- `"یک و نیم کیلویی"` / `"یک و نیم کیلوگرمی"` ➔ `1.5 کیلوگرم`
- `"نیم لیتری"` ➔ `0.5 لیتر`
- `"نیم کیلویی"` / `"نیم کیلو"` ➔ `0.5 کیلوگرم`
- `"یک لیتری"` / `"یه لیتری"` ➔ `1.0 لیتر`
- `"دو لیتری"` ➔ `2.0 لیتر`
- `"چهار لیتری"` ➔ `4.0 لیتر`

### Regex Non-ASCII Boundary Rule (CRITICAL)
> [!IMPORTANT]
> In Python `re`, standard ASCII `\b` fails on Unicode/Persian characters when followed by Persian suffixes.
> **Mandatory Rule**: All unit pattern regexes must use negative lookaheads:
> `(?![آ-ی\w\u0600-\u06FF])` instead of `\b`.

### Unit Extraction Precedence
To prevent substring misclassification:
1. `میلی‌لیتر` / `میلی‌لیتری` / `سی‌سی` MUST be tested **before** `لیتر` / `لیتری`.
   - *Example*: `"۹۵۵ میلی‌لیتر"` must parse as `955 میلی‌لیتر`, NEVER as `955 لیتر`.
2. Suffixes `"کیلوگرمی"` and `"کیلو\s*گرمی"` MUST be recognized alongside `"کیلوگرم"` and `"کیلویی"`.

---

## 3. Strict SKU Matching & Attribute Verification (`matcher.py`)

Matching combines fuzzy title similarity with **strict physical attribute vetoes**:

```
Candidate StoreItem
         │
         ├── 1. Fat Level Verification (is_fat_compatible)
         │       └── Fails? ──► REJECT CANDIDATE
         │
         ├── 2. Product Flavor Verification (is_flavor_compatible)
         │       └── Fails? ──► REJECT CANDIDATE
         │
         ├── 3. Strict Volume / Weight Verification (is_volume_compatible)
         │       └── Fails? ──► REJECT CANDIDATE
         │
         └── 4. RapidFuzz Token-Set Similarity & Brand Scoring
                 └── Best score >= 0.50 ──► WINNING MATCH
```

### 1. Strict Volume Compatibility (`is_volume_compatible`)
- Normalizes all volume/weight units to base metric units:
  - `لیتر` ➔ `* 1000.0` (ml)
  - `کیلوگرم` ➔ `* 1000.0` (g)
  - `گرم` / `میلی‌لیتر` ➔ base
- **Tolerance**: Absolute difference must be `<= 15%`.
- **None Guard (The 4L vs 1kg rule)**:
  If user requested a specific volume (e.g. 4L):
  - If candidate title does not contain an extractable volume, BUT contains an explicit incompatible unit keyword or a known standard smaller packaging (e.g. `1000 گرم`, `1 کیلوگرم`), it is **strictly rejected**.
  - A 4L dishwashing liquid request must **never** match a 1kg bottle.

### 2. Dairy Fat Compatibility (`is_fat_compatible`)
- If user requested `fat >= 2.5%` (پرچرب): Candidate title containing `"کم چرب"` / `"کم‌چرب"` / `"1.5%"` is rejected.
- If user requested `fat <= 1.5%` (کم‌چرب): Candidate title containing `"پر چرب"` / `"پرچرب"` / `"3%"` is rejected.

### 3. Product Flavor Exclusion (`is_flavor_compatible`)
- If user requested plain unflavored milk (`"شیر"`, `"شیر پرچرب"`, `"شیر کم چرب"`):
  - Candidate titles containing flavored dairy keywords:
    `"طالبی"`, `"کاکائو"`, `"موز"`, `"قهوه"`, `"توت فرنگی"`, `"وانیل"`, `"خرما"`, `"عسل"`, `"پسته"`, `"نارگیل"`
    are **strictly rejected**.
  - *Example*: `"شیر طالبی سولیکو کاله"` is rejected when user requests `"شیر پرچرب کاله"`.

### 4. Fuzzy Similarity & Scoring
- Computes `fuzz.token_set_ratio(target_str, candidate_str) / 100.0`.
- **Brand Bonus/Penalty**: If user specified a brand (e.g. `"کاله"`):
  - If brand is missing from candidate title and brand field: multiply score by `0.6`.
- **Noun Verification**: If core noun (e.g. `"شیر"`) is missing from candidate: multiply score by `0.5`.
- **Threshold**: Requires `score >= 0.50` for acceptance.
