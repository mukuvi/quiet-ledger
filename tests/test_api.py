import pytest
from fastapi.testclient import TestClient

import app as app_module
import model
from ledger import Ledger

RECEIPT = (
    "KASHA HARDWARE LTD\n"
    "Invoice No: INV-2026-1044\n"
    "Date: 12/10/2026\n"
    "TOTAL KES 4,850.00\n"
    "Paid by: M-PESA\n"
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "ledger", Ledger(tmp_path / "data"))
    monkeypatch.setattr(model, "LLAMA_BIN", "definitely-not-a-real-binary")
    monkeypatch.setattr(model, "GEMMA_MODEL", str(tmp_path / "missing.gguf"))
    return TestClient(app_module.app)


def test_health_reports_fallback_when_no_model(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["model"]["ready"] is False
    assert "software" in body["categories"]


def test_text_ingest_sorts_a_receipt(client):
    response = client.post("/api/text", json={"text": RECEIPT})
    assert response.status_code == 200
    receipt = response.json()["receipt"]
    assert receipt["vendor"] == "KASHA HARDWARE LTD"
    assert receipt["total"] == 4850.0
    assert receipt["currency"] == "KES"
    assert receipt["category"] == "hardware"
    assert receipt["date"] == "2026-10-12"
    assert receipt["extracted_by"] == "fallback-parser"


def test_same_receipt_is_not_counted_twice(client):
    client.post("/api/text", json={"text": RECEIPT})
    again = client.post("/api/text", json={"text": RECEIPT})
    assert again.json()["duplicate"] is True
    assert len(client.get("/api/receipts").json()["receipts"]) == 1


def test_short_paste_is_rejected(client):
    response = client.post("/api/text", json={"text": "total 10"})
    assert response.status_code == 422


def test_corrections_are_validated(client):
    receipt = client.post("/api/text", json={"text": RECEIPT}).json()["receipt"]
    ok = client.patch(f"/api/receipts/{receipt['id']}", json={"category": "office"})
    assert ok.status_code == 200
    assert ok.json()["receipt"]["category"] == "office"

    bad_date = client.patch(f"/api/receipts/{receipt['id']}", json={"date": "yesterday"})
    assert bad_date.status_code == 422

    locked = client.patch(f"/api/receipts/{receipt['id']}", json={"id": "nope"})
    assert locked.status_code == 422


def test_export_and_delete(client):
    receipt = client.post("/api/text", json={"text": RECEIPT}).json()["receipt"]
    csv_response = client.get("/api/export.csv")
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "KASHA HARDWARE LTD" in csv_response.text

    assert client.delete(f"/api/receipts/{receipt['id']}").status_code == 200
    assert client.get("/api/receipts").json()["receipts"] == []
    assert client.delete(f"/api/receipts/{receipt['id']}").status_code == 404


def test_unsupported_file_type_is_explained(client):
    response = client.post(
        "/api/ingest", files={"file": ("receipt.docx", b"not a receipt", "application/msword")}
    )
    assert response.status_code == 422
    assert ".docx" in response.json()["detail"]


def test_filters_and_summary(client):
    client.post("/api/text", json={"text": RECEIPT})
    client.post(
        "/api/text",
        json={"text": "MAMA NJERI'S KITCHEN\nDate: 15/10/2026\nTotal KES 1,400.00\nPayment: cash\n"},
    )
    meals = client.get("/api/receipts", params={"category": "meals"}).json()
    assert len(meals["receipts"]) == 1
    assert meals["summary"]["currencies"][0]["total"] == 1400.0

    october = client.get("/api/receipts", params={"month": "2026-10"}).json()
    assert len(october["receipts"]) == 2
