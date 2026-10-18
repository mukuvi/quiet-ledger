import pytest

from ledger import Ledger, NotFound


def sample(**overrides):
    record = {
        "date": "2026-10-12",
        "vendor": "Kasha Hardware Ltd",
        "category": "hardware",
        "total": 4850.0,
        "currency": "KES",
        "tax": 620.0,
        "payment_method": "mpesa",
        "invoice_number": "INV-2026-1044",
        "source_file": "kasha.txt",
        "notes": "",
        "extracted_by": "fallback-parser",
        "source_sha256": "a" * 64,
    }
    record.update(overrides)
    return record


@pytest.fixture()
def ledger(tmp_path):
    return Ledger(tmp_path / "data")


def test_add_assigns_id_and_timestamp(ledger):
    stored, duplicate = ledger.add(sample())
    assert duplicate is False
    assert len(stored["id"]) == 12
    assert stored["created_at"]
    assert ledger.all() == [stored]


def test_same_file_is_not_sorted_twice(ledger):
    first, _ = ledger.add(sample())
    second, duplicate = ledger.add(sample(vendor="Different", total=1.0))
    assert duplicate is True
    assert second["id"] == first["id"]
    assert len(ledger.all()) == 1


def test_update_only_touches_editable_fields(ledger):
    stored, _ = ledger.add(sample())
    updated = ledger.update(stored["id"], {"category": "office", "id": "hacked"})
    assert updated["category"] == "office"
    assert updated["id"] == stored["id"]


def test_delete_removes_and_reports_missing(ledger):
    stored, _ = ledger.add(sample())
    ledger.delete(stored["id"])
    assert ledger.all() == []
    with pytest.raises(NotFound):
        ledger.delete(stored["id"])


def test_csv_is_what_an_accountant_gets(ledger):
    ledger.add(sample())
    csv_text = ledger.export_csv()
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("date,vendor,category,total,currency")
    assert lines[1].startswith("2026-10-12,Kasha Hardware Ltd,hardware,4850.00,KES")


def test_summary_keeps_currencies_apart(ledger):
    ledger.add(sample())
    ledger.add(
        sample(
            source_sha256="b" * 64,
            vendor="Northwind Studio",
            total=2083.2,
            currency="USD",
            category="professional-services",
            date="2026-10-09",
        )
    )
    summary = ledger.summary()
    assert summary["count"] == 2
    assert [bucket["currency"] for bucket in summary["currencies"]] == ["KES", "USD"]
    kes = next(b for b in summary["currencies"] if b["currency"] == "KES")
    assert kes["by_category"]["hardware"] == 4850.0


def test_summary_filters_by_month_and_counts_unpriced(ledger):
    ledger.add(sample())
    ledger.add(sample(source_sha256="c" * 64, date="2026-09-02", total=None))
    assert ledger.summary("2026-10")["count"] == 1
    september = ledger.summary("2026-09")
    assert september["count"] == 1
    assert september["unpriced"] == 1
