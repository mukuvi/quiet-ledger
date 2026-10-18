import json
import os
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

LLAMA_BIN = os.environ.get("LLAMA_BIN", "llama-cli")
GEMMA_MODEL = os.environ.get("GEMMA_MODEL", str(Path("models") / "gemma-3-1b-it-Q4_K_M.gguf"))
LLAMA_THREADS = os.environ.get("LLAMA_THREADS", str(max(2, (os.cpu_count() or 4) // 2)))
MODEL_TIMEOUT = int(os.environ.get("MODEL_TIMEOUT", "180"))

CATEGORY_LIST = (
    "groceries, meals, transport, fuel, software, hardware, office, travel, "
    "utilities, marketing, professional-services, other"
)

PROMPT_TEMPLATE = """You are a bookkeeper sorting receipts for a one-person business.
Read the receipt text and return one JSON object describing it.

Rules:
- Return JSON only. No markdown, no explanation, no commentary.
- Use null when a value is not printed on the receipt. Never invent values.
- "date" is the purchase date as YYYY-MM-DD. If the year is missing, use {year}.
- "total" is the final amount paid: digits and a decimal point only, no symbols or separators.
  If the receipt shows both a subtotal and a total or amount due, use the final amount due, never the subtotal.
- "tax" is the tax or VAT amount in money, not the tax rate, same format, or null.
- "currency" is an ISO 4217 code such as KES, USD, EUR or GBP.
- "category" is exactly one of: {categories}.
- "vendor" is the business name as printed.
- "invoice_number" is the receipt or invoice number if printed, else null.
- "payment_method" is one of cash, card, mpesa, bank transfer, or null.
- "notes" is one short sentence only if something matters for bookkeeping, else null.

Shape:
{{"vendor": null, "date": null, "total": null, "tax": null, "currency": null, "category": null, "payment_method": null, "invoice_number": null, "notes": null}}

Receipt text:
\"\"\"
{text}
\"\"\"

JSON:"""


class ModelUnavailable(Exception):
    pass


def available():
    return bool(shutil.which(LLAMA_BIN) and Path(GEMMA_MODEL).exists())


def status():
    return {
        "binary": LLAMA_BIN,
        "binary_found": bool(shutil.which(LLAMA_BIN)),
        "model_path": GEMMA_MODEL,
        "model_found": Path(GEMMA_MODEL).exists(),
        "ready": available(),
    }


def extract_fields(text, filename=""):
    cleaned = _clean_for_prompt(text)
    if not cleaned:
        raise ValueError("No text to read.")
    if available():
        fields = _ask_gemma(cleaned)
        if fields:
            return fields, "gemma-3-1b-it"
    from normalize import normalize_record

    return normalize_record({}, text, filename), "fallback-parser"


def _clean_for_prompt(text):
    text = re.sub(r"[ \t]+", " ", text or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:6000]


def _ask_gemma(text):
    prompt = PROMPT_TEMPLATE.format(
        year=date.today().year, categories=CATEGORY_LIST, text=text
    )
    base = [
        LLAMA_BIN,
        "-m",
        GEMMA_MODEL,
        "-p",
        prompt,
        "-n",
        "300",
        "--temp",
        "0",
        "--top-k",
        "1",
        "-t",
        LLAMA_THREADS,
        "--no-warmup",
    ]
    output = _run_with_fallback(base)
    return _pick_json(output)


def _run_with_fallback(base):
    attempts = [
        base + ["-st", "--no-display-prompt"],
        base + ["--no-display-prompt"],
        base,
    ]
    last_error = None
    for args in attempts:
        try:
            result = subprocess.run(
                args, capture_output=True, timeout=MODEL_TIMEOUT, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            last_error = error
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        last_error = stderr or f"llama-cli exited {result.returncode}"
    raise ModelUnavailable(str(last_error))


def _pick_json(output):
    text = re.sub(r"```(?:json)?", "", output)
    decoded = []
    for start in [index for index, char in enumerate(text) if char == "{"]:
        try:
            candidate, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and (
            "vendor" in candidate or "total" in candidate
        ):
            decoded.append(candidate)
    if not decoded:
        return None
    merged = {}
    for candidate in decoded:
        merged.update({key: value for key, value in candidate.items() if value is not None})
    return merged
