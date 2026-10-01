## 2026-10-01T13:07:40Z
You are explorer_survey_persian_nlp, a teamwork_preview_explorer for the Sabad project.
Your working directory is: /Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_persian_nlp
Your parent orchestrator is: 5f3ddd0b-8fff-4532-82d8-412561e17041

MANDATORY: You MUST read the authoritative user requirements at:
/Users/sotoon/personal/Sabad/.agents/teamwork/ORIGINAL_REQUEST.md
before starting your work!

Also review prior work in:
/Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_3/handoff.md

Your objective:
1. Research and design the Natural Language Persian Grocery Basket Normalizer & SKU Matcher (Requirement R2):
   - Ingestion of natural language Persian grocery prompts (e.g. "دو تا شیر پرچرب کاله یک لیتری، یه پنیر ویلی ۳۵۰ گرمی، یه مایع ظرفشویی پریل ۴ لیتری").
   - Persian text normalization: handling Arabic vs Persian characters (ی/ي, ک/ك, ه/ة), zero-width non-joiner (ZWNJ / نیم‌فاصله `\u200c`), vowel marks (حرکات/تنوین), punctuation.
   - Persian numeral and quantity extraction: Persian digits (۰-۹), Arabic digits (٠-٩), English digits (0-9), Persian quantity words (یک, یه, دو, سه, نیم, یک و نیم, دو تا, سه بسته, etc.).
   - Unit parsing and standardization: گرم, کیلوگرم, میلی‌لیتر, لیتر, عدد, بسته, قوطی, بطری, etc.
   - Brand detection & entity extraction: recognize Iranian and international grocery brands (کاله, پگاه, میهن, دامداران, چوپان, پاک, صباح, ویلی, پریل, گلرنگ, تاژ, صحت, روژین, طبیعت, etc.).
   - Strict attribute extraction: fat percentage (پرچرب, کم‌چرب, نیم‌چرب, ۳٪, ۱.۵٪), flavor/scent, package type.
2. SKU Matching Algorithm:
   - Fuzzy string matching (Levenshtein / RapidFuzz ratio, token sort ratio) between parsed user item and candidate catalog items.
   - Strict attribute verification gates: brand must match if specified; volume/weight must match within tolerance (zero false SKU pairings like matching 1L milk to 200ml milk); fat percentage must match.
   - Match confidence score calculation and thresholding.
3. Design Pydantic schema contracts:
   - `ParsedGroceryItem`
   - `ParsedGroceryBasket`
   - `MatchedSKU`
   - `SKUMatchResult`
4. Document boundary conditions, edge cases, test inputs, and algorithm specifications.

Write your comprehensive findings, architecture, and schemas to:
/Users/sotoon/personal/Sabad/.agents/teamwork/explorer_survey_persian_nlp/handoff.md
Update progress.md as you work. When complete, send a completion message to your parent orchestrator.
