import hashlib
import os
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import model
from extract import UnsupportedFile, extract_text
from ledger import EDITABLE, Ledger, NotFound
from normalize import CATEGORIES, normalize_category, normalize_record, parse_amount, parse_date

BASE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("QUIET_LEDGER_DATA", BASE / "data"))
MAX_BYTES = 15 * 1024 * 1024

ledger = Ledger(DATA_DIR)
app = FastAPI(title="Quiet Ledger", version="1.0.0")


class TextIn(BaseModel):
    text: str
    filename: str = "pasted-receipt.txt"


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "model": model.status(),
        "receipts": len(ledger.all()),
        "categories": CATEGORIES,
    }


@app.get("/api/receipts")
def list_receipts(
    month: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
):
    records = ledger.sorted()
    if month:
        records = [
            record
            for record in records
            if (record.get("date") or record.get("created_at") or "").startswith(month)
        ]
    if category:
        records = [record for record in records if record.get("category") == category]
    if q:
        needle = q.lower()
        records = [
            record
            for record in records
            if needle in (record.get("vendor") or "").lower()
            or needle in (record.get("notes") or "").lower()
        ]
    return {"receipts": records, "summary": ledger.summary(month, records)}


@app.post("/api/ingest")
async def ingest(file: UploadFile = File(...)):
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="That file is empty.")
    if len(payload) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Files over 15 MB are not supported.")

    digest = hashlib.sha256(payload).hexdigest()
    existing = ledger.find_by_hash(digest)
    if existing:
        return {"receipt": existing, "duplicate": True}

    try:
        text = extract_text(file.filename, payload)
    except UnsupportedFile as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return _store(text, file.filename or "receipt", digest)


@app.post("/api/text")
def ingest_text(body: TextIn):
    if len(body.text.strip()) < 12:
        raise HTTPException(status_code=422, detail="Paste a little more of the receipt.")
    digest = hashlib.sha256(body.text.encode("utf-8")).hexdigest()
    existing = ledger.find_by_hash(digest)
    if existing:
        return {"receipt": existing, "duplicate": True}
    return _store(body.text, body.filename, digest)


@app.patch("/api/receipts/{receipt_id}")
def correct_receipt(receipt_id: str, changes: dict = Body(...)):
    cleaned = {}
    for key, value in changes.items():
        if key not in EDITABLE:
            raise HTTPException(status_code=422, detail=f"{key} is not editable.")
        cleaned[key] = _clean_field(key, value)
    try:
        return {"receipt": ledger.update(receipt_id, cleaned)}
    except NotFound as error:
        raise HTTPException(status_code=404, detail="No receipt with that id.") from error


@app.delete("/api/receipts/{receipt_id}")
def delete_receipt(receipt_id: str):
    try:
        ledger.delete(receipt_id)
    except NotFound as error:
        raise HTTPException(status_code=404, detail="No receipt with that id.") from error
    return {"deleted": receipt_id}


@app.get("/api/export.csv")
def export_csv(month: Optional[str] = Query(default=None)):
    records = ledger.sorted()
    if month:
        records = [
            record
            for record in records
            if (record.get("date") or record.get("created_at") or "").startswith(month)
        ]
    buffer = ledger.export_csv(records)
    stamp = month or "all"
    return Response(
        content=buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="quiet-ledger-{stamp}.csv"'},
    )


@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(BASE / "static" / "manifest.webmanifest")


@app.get("/sw.js")
def service_worker():
    return FileResponse(BASE / "static" / "sw.js", media_type="application/javascript")


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


def _store(text, filename, digest):
    if len(text.strip()) < 12:
        raise HTTPException(
            status_code=422,
            detail="That file had almost no readable text. Try a clearer scan or paste the text.",
        )
    try:
        fields, extractor = model.extract_fields(text, filename)
    except model.ModelUnavailable:
        fields, extractor = normalize_record({}, text, filename), "fallback-parser"

    record = normalize_record(fields, text, filename)
    record["extracted_by"] = extractor
    record["source_sha256"] = digest
    stored, duplicate = ledger.add(record)
    return {"receipt": stored, "duplicate": duplicate}


def _clean_field(key, value):
    if value is None or value == "":
        return None if key in {"total", "tax", "date"} else ""
    if key == "date":
        parsed = parse_date(value)
        if not parsed:
            raise HTTPException(status_code=422, detail="Use a date like 2026-10-17.")
        return parsed
    if key in {"total", "tax"}:
        amount = parse_amount(value)
        if amount is None:
            raise HTTPException(status_code=422, detail=f"{key} must be a number.")
        return amount
    if key == "category":
        category = normalize_category(value)
        if category not in CATEGORIES:
            raise HTTPException(
                status_code=422, detail=f"Pick one of: {', '.join(CATEGORIES)}."
            )
        return category
    if key == "currency":
        code = str(value).strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise HTTPException(status_code=422, detail="Currency must be a 3-letter code.")
        return code
    return str(value).strip()[:280]

