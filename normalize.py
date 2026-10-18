import re
from datetime import date

CATEGORIES = [
    "groceries",
    "meals",
    "transport",
    "fuel",
    "software",
    "hardware",
    "office",
    "travel",
    "utilities",
    "marketing",
    "professional-services",
    "other",
]

CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "₦": "NGN",
    "R$": "BRL",
    "KSh": "KES",
    "KES": "KES",
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
    "NGN": "NGN",
    "INR": "INR",
    "TZS": "TZS",
    "UGX": "UGX",
    "ZAR": "ZAR",
}

CATEGORY_KEYWORDS = {
    "groceries": [
        "supermarket", "grocery", "groceries", "market", "naivas", "quickmart",
        "carrefour", "food store", "greengrocer", "butcher", "bakery",
    ],
    "meals": [
        "restaurant", "cafe", "coffee", "cafe", "bistro", "kitchen", "pizza",
        "grill", "bar", "lunch", "dinner", "eatery", "hotel restaurant",
    ],
    "transport": [
        "uber", "bolt", "taxi", "matatu", "bus", "train", "metro", "parking",
        "toll", "ride", "fare",
    ],
    "fuel": ["petrol", "diesel", "fuel", "shell", "total energies", "gas station", "petroleum"],
    "software": [
        "subscription", "saas", "software license", "software licence",
        "license key", "software", "cloud", "hosting", "domain", "api", "adobe",
        "figma", "github", "openai", "notion", "slack", "vercel", "render",
        "railway",
    ],
    "hardware": [
        "hardware", "tool", "tools", "laptop", "monitor", "keyboard", "mouse",
        "ssd", "hard drive", "router", "phone", "cable", "charger",
        "electronics", "computer", "drill", "screws",
    ],
    "office": [
        "stationery", "printer", "paper", "ink", "toner", "desk", "chair",
        "office supplies", "envelope",
    ],
    "travel": [
        "airline", "flight", "airport", "hotel", "booking", "airbnb", "visa fee",
        "lodging", "accommodation", "airways",
    ],
    "utilities": [
        "electricity", "water", "internet", "broadband", "airtime", "data bundle",
        "kplc", "safaricom", "utility", "gas bill", "wifi",
    ],
    "marketing": [
        "advertising", "ads", "campaign", "facebook ads", "google ads",
        "promotion", "billboard", "flyers", "printing",
    ],
    "professional-services": [
        "accounting", "accountant", "legal", "lawyer", "consulting",
        "consultant", "audit", "bookkeeping", "notary", "tax return", "tax filing",
        "retainer", "design services",
    ],
}

DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{2})\b"), "dmy2"),
    (re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b"), "ymd"),
]

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

MONTH_NAME_PATTERN = re.compile(
    r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b", re.IGNORECASE
)

MONTH_FIRST_PATTERN = re.compile(
    r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b", re.IGNORECASE
)

MONEY_PATTERN = re.compile(r"-?\d[\d,\s]*\.?\d{0,2}")


def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def parse_date(value, text=""):
    raw = clean_text(value)
    candidates = [raw] if raw else []
    candidates.extend(m.group(0) for m in DATE_PATTERNS[0][0].finditer(text))
    candidates.extend(m.group(0) for m in DATE_PATTERNS[1][0].finditer(text))
    candidates.extend(m.group(0) for m in MONTH_NAME_PATTERN.finditer(text))
    candidates.extend(m.group(0) for m in MONTH_FIRST_PATTERN.finditer(text))

    for candidate in candidates:
        parsed = _parse_one(candidate)
        if parsed:
            return parsed.isoformat()
    return None


def _parse_one(value):
    value = value.strip()
    match = DATE_PATTERNS[0][0].search(value)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return _safe_date(year, month, day)

    for pattern, kind in DATE_PATTERNS[1:3]:
        match = pattern.search(value)
        if match:
            first, second, year = (int(part) for part in match.groups())
            if kind == "dmy2":
                year += 2000
            else:
                year = int(match.group(3))
            return _safe_date(year, second, first) if second <= 12 and first <= 31 else None

    match = MONTH_NAME_PATTERN.search(value)
    if match:
        day = int(match.group(1))
        month = MONTHS.get(match.group(2).lower())
        if month:
            return _safe_date(int(match.group(3)), month, day)

    match = MONTH_FIRST_PATTERN.search(value)
    if match:
        day = int(match.group(2))
        month = MONTHS.get(match.group(1).lower())
        if month:
            return _safe_date(int(match.group(3)), month, day)
    return None


def _safe_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_amount(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    raw = str(value).strip()
    if "%" in raw:
        return None
    negative = raw.startswith("-") or raw.startswith("(")
    raw = raw.replace("(", "").replace(")", "").replace("-", "")
    match = MONEY_PATTERN.search(raw)
    if not match:
        return None
    number = match.group(0).replace(",", "").replace(" ", "")
    try:
        amount = float(number)
    except ValueError:
        return None
    if negative:
        amount = -amount
    return round(amount, 2)


def detect_currency(text, value=None):
    hinted = clean_text(value).upper()
    if hinted in CURRENCY_SYMBOLS.values():
        return hinted
    haystack = f"{value or ''} {text or ''}"
    for token in ("KES", "KSh", "USD", "EUR", "GBP", "NGN", "INR", "TZS", "UGX", "ZAR", "BRL"):
        if re.search(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", haystack):
            return "KES" if token == "KSh" else token
    for symbol, code in CURRENCY_SYMBOLS.items():
        if len(symbol) == 1 and symbol in haystack:
            return code
    return "USD"


def guess_category(*parts):
    haystack = " ".join(clean_text(part).lower() for part in parts if part)
    if not haystack:
        return "other"
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", haystack):
                return category
    return "other"


def normalize_category(value, *context):
    candidate = clean_text(value).lower().replace("_", "-").replace(" ", "-")
    if candidate in CATEGORIES:
        return candidate
    for category in CATEGORIES:
        if category in candidate and candidate:
            return category
    return guess_category(*context)


def _category_or_guess(candidate, *context):
    if candidate in CATEGORIES and candidate != "other":
        return candidate
    guessed = guess_category(*context)
    return guessed if guessed != "other" else candidate


def normalize_record(fields, text="", source_file=""):
    vendor = clean_text(fields.get("vendor"))
    if not vendor or vendor.lower() in {"unknown", "n/a", "none", "null"}:
        vendor = _guess_vendor(text) or "Unknown vendor"

    invoice_number = clean_text(fields.get("invoice_number"))
    if invoice_number.lower() in {"unknown", "n/a", "none", "null"}:
        invoice_number = ""
    if not invoice_number:
        invoice_number = _guess_invoice(text)

    total = parse_amount(fields.get("total"))
    printed = _labelled_total(text)
    if printed is not None:
        total = printed
    elif total is None:
        total = _guess_total(text)

    tax = parse_amount(fields.get("tax"))
    if tax is not None and total and (tax <= 0 or tax > total or tax < total * 0.01):
        tax = None
    if tax is None:
        tax = _guess_tax(text)

    return {
        "vendor": vendor,
        "date": parse_date(fields.get("date"), text),
        "total": total,
        "tax": tax,
        "currency": detect_currency(text, fields.get("currency")),
        "category": _category_or_guess(
            normalize_category(fields.get("category"), vendor, text), vendor, text
        ),
        "payment_method": _payment_method(fields.get("payment_method"), text),
        "invoice_number": invoice_number,
        "notes": clean_text(fields.get("notes"))[:280],
        "source_file": source_file,
    }


def _payment_method(value, text):
    raw = clean_text(value).lower()
    haystack = f"{raw} {clean_text(text).lower()}"
    for method in ("cash", "card", "mpesa", "m-pesa", "bank transfer", "mobile money", "cheque", "check"):
        if method in haystack:
            return {"m-pesa": "mpesa", "check": "cheque"}.get(method, method)
    return ""


def _guess_invoice(text):
    labelled = re.search(
        r"\b(?:invoice|receipt|bill)\s*(?:no|num|number|#)\s*\.?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-/]{2,})",
        text or "",
        re.IGNORECASE,
    )
    if labelled:
        return labelled.group(1)
    invoice_only = re.search(
        r"\binvoice\s*[:#]\s*([A-Z0-9][A-Z0-9\-/]{2,})", text or "", re.IGNORECASE
    )
    return invoice_only.group(1) if invoice_only else ""


def _guess_tax(text):
    match = re.search(
        r"\b(?:vat|sales\s+tax|tax|gst)\b[^\n]{0,24}?(\d[\d,]*\.\d{2})",
        text or "",
        re.IGNORECASE,
    )
    return parse_amount(match.group(1)) if match else None


def _labelled_total(text):
    labelled = re.search(
        r"\b(grand\s+total|total\s+due|amount\s+due|balance\s+due|total|balance)\b\s*[:\-]?\s*([A-Z]{0,3}\s?[$€£₹₦]?\s?[\d,\s]+\.?\d{0,2})",
        clean_text(text),
        re.IGNORECASE,
    )
    if not labelled:
        return None
    return parse_amount(labelled.group(2))


def _guess_total(text):
    haystack = clean_text(text)
    amount = _labelled_total(haystack)
    if amount is not None:
        return amount
    amounts = [parse_amount(match.group(0)) for match in MONEY_PATTERN.finditer(haystack)]
    amounts = [amount for amount in amounts if amount is not None and amount > 0]
    return max(amounts) if amounts else None


def _guess_vendor(text):
    for line in (text or "").splitlines():
        line = clean_text(line)
        if len(line) < 3 or not re.search(r"[A-Za-z]", line):
            continue
        if re.search(r"\b(invoice|receipt|tax invoice|date|total)\b", line, re.IGNORECASE):
            continue
        if re.search(
            r"\b(ltd|limited|llc|inc|store|market|shop|supermarket|hotel|cafe|restaurant|services|company|co\.)\b",
            line,
            re.IGNORECASE,
        ):
            return line[:80]
    for line in (text or "").splitlines():
        line = clean_text(line)
        if len(line) >= 3 and re.search(r"[A-Za-z]", line):
            return line[:80]
    return ""
