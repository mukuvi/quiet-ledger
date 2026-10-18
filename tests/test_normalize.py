from normalize import (
    CATEGORIES,
    detect_currency,
    normalize_category,
    normalize_record,
    parse_amount,
    parse_date,
)


def test_parse_amount_handles_symbols_and_separators():
    assert parse_amount("KES 4,850.00") == 4850.0
    assert parse_amount("$1,800.00") == 1800.0
    assert parse_amount("1 200.50") == 1200.5
    assert parse_amount("16%") is None
    assert parse_amount("") is None
    assert parse_amount("no numbers") is None


def test_parse_amount_handles_credits():
    assert parse_amount("(120.50)") == -120.5
    assert parse_amount("-300") == -300.0


def test_parse_dates_in_common_shapes():
    assert parse_date("12/10/2026") == "2026-10-12"
    assert parse_date("2026-10-15") == "2026-10-15"
    assert parse_date("October 9, 2026") == "2026-10-09"
    assert parse_date("9 October 2026") == "2026-10-09"
    assert parse_date("32/13/2026") is None


def test_kasha_receipt_is_read_cleanly():
    text = (
        "KASHA HARDWARE LTD\n"
        "TAX INVOICE\n"
        "Invoice No: INV-2026-1044\n"
        "Date: 12/10/2026\n"
        "VAT 16% 620.00\n"
        "TOTAL KES 4,850.00\n"
        "Paid by: M-PESA\n"
    )
    record = normalize_record({}, text, "kasha.txt")
    assert record["vendor"] == "KASHA HARDWARE LTD"
    assert record["date"] == "2026-10-12"
    assert record["total"] == 4850.0
    assert record["currency"] == "KES"
    assert record["category"] == "hardware"
    assert record["tax"] == 620.0
    assert record["invoice_number"] == "INV-2026-1044"
    assert record["payment_method"] == "mpesa"


def test_foreign_invoice_keeps_its_own_currency():
    text = (
        "Northwind Studio LLC\n"
        "INVOICE\n"
        "Issued: October 9, 2026\n"
        "Subtotal $1,920.00\n"
        "Sales tax (8.5%) $163.20\n"
        "Amount due $2,083.20\n"
        "Payment: bank transfer\n"
    )
    record = normalize_record({}, text, "northwind.txt")
    assert record["date"] == "2026-10-09"
    assert record["total"] == 2083.2
    assert record["currency"] == "USD"
    assert record["tax"] == 163.2
    assert record["payment_method"] == "bank transfer"


def test_meal_receipt_lands_in_meals():
    text = "MAMA NJERI'S KITCHEN\nLunch combo 1,200.00\nTotal KES 1,400.00\n"
    record = normalize_record({}, text, "lunch.txt")
    assert record["category"] == "meals"
    assert record["total"] == 1400.0


def test_model_fields_are_normalized_not_trusted():
    record = normalize_record(
        {
            "vendor": "  Acme   Hosting ",
            "date": "2026-10-12",
            "total": "$120.00",
            "tax": "n/a",
            "currency": "usd",
            "category": "Software Subscriptions",
            "invoice_number": "null",
        },
        "Acme Hosting invoice",
        "acme.txt",
    )
    assert record["vendor"] == "Acme Hosting"
    assert record["date"] == "2026-10-12"
    assert record["total"] == 120.0
    assert record["tax"] is None
    assert record["currency"] == "USD"
    assert record["category"] == "software"
    assert record["invoice_number"] == ""


def test_a_tax_rate_is_not_mistaken_for_tax_paid():
    record = normalize_record(
        {"vendor": "Kasha Hardware Ltd", "total": "4850.00", "tax": "16.00"},
        "VAT 16% 620.00\nTOTAL KES 4,850.00\n",
    )
    assert record["tax"] == 620.0


def test_printed_amount_due_beats_a_model_subtotal():
    record = normalize_record(
        {"vendor": "Northwind Studio LLC", "total": "1920.00", "tax": "163.20"},
        "Subtotal $1,920.00\nSales tax (8.5%) $163.20\nAmount due $2,083.20\n",
    )
    assert record["total"] == 2083.2
    assert record["tax"] == 163.2


def test_model_category_other_defers_to_the_text():
    record = normalize_record(
        {"vendor": "Kasha Hardware Ltd", "category": "other", "total": "4850.00"},
        "Cordless drill, wood screws, work gloves",
    )
    assert record["category"] == "hardware"


def test_unknown_category_falls_back_to_other():
    assert normalize_category("spaceships") == "other"
    assert normalize_category("", "nothing useful here") == "other"
    assert set(CATEGORIES).issuperset({"groceries", "software", "other"})


def test_currency_detection_prefers_explicit_code():
    assert detect_currency("Total KES 100") == "KES"
    assert detect_currency("Total 100", "eur") == "EUR"
    assert detect_currency("Total 100") == "USD"
