import csv
import io
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

FIELDS = [
    "id",
    "date",
    "vendor",
    "category",
    "total",
    "currency",
    "tax",
    "payment_method",
    "invoice_number",
    "source_file",
    "notes",
    "extracted_by",
    "created_at",
    "source_sha256",
]

CSV_COLUMNS = [
    "date",
    "vendor",
    "category",
    "total",
    "currency",
    "tax",
    "payment_method",
    "invoice_number",
    "source_file",
    "notes",
    "extracted_by",
    "id",
]

EDITABLE = [
    "date",
    "vendor",
    "category",
    "total",
    "currency",
    "tax",
    "payment_method",
    "invoice_number",
    "notes",
]


class NotFound(Exception):
    pass


class Ledger:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "receipts.jsonl"
        self._lock = threading.Lock()

    def all(self):
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records

    def sorted(self):
        return sorted(
            self.all(),
            key=lambda record: (record.get("date") or "", record.get("created_at") or ""),
            reverse=True,
        )

    def find_by_hash(self, digest):
        for record in self.all():
            if record.get("source_sha256") == digest:
                return record
        return None

    def get(self, receipt_id):
        for record in self.all():
            if record.get("id") == receipt_id:
                return record
        raise NotFound(receipt_id)

    def add(self, record):
        with self._lock:
            existing = self.find_by_hash(record.get("source_sha256"))
            if existing:
                return existing, True
            stored = {field: record.get(field) for field in FIELDS}
            stored["id"] = uuid.uuid4().hex[:12]
            stored["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self._append(stored)
            return stored, False

    def update(self, receipt_id, changes):
        with self._lock:
            records = self.all()
            updated = None
            for record in records:
                if record.get("id") == receipt_id:
                    for key, value in changes.items():
                        if key in EDITABLE:
                            record[key] = value
                    updated = record
                    break
            if updated is None:
                raise NotFound(receipt_id)
            self._write(records)
            return updated

    def delete(self, receipt_id):
        with self._lock:
            records = self.all()
            kept = [record for record in records if record.get("id") != receipt_id]
            if len(kept) == len(records):
                raise NotFound(receipt_id)
            self._write(kept)

    def export_csv(self, records=None):
        records = self.sorted() if records is None else records
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(CSV_COLUMNS)
        for record in records:
            writer.writerow([_csv_value(record.get(field)) for field in CSV_COLUMNS])
        return buffer.getvalue()

    def summary(self, month=None, records=None):
        records = self.sorted() if records is None else records
        if month:
            records = [
                record
                for record in records
                if (record.get("date") or record.get("created_at") or "").startswith(month)
            ]
        currencies = {}
        unpriced = 0
        for record in records:
            total = record.get("total")
            if total is None:
                unpriced += 1
                continue
            code = record.get("currency") or "UNKNOWN"
            bucket = currencies.setdefault(
                code, {"currency": code, "total": 0.0, "count": 0, "by_category": {}}
            )
            bucket["total"] = round(bucket["total"] + float(total), 2)
            bucket["count"] += 1
            category = record.get("category") or "other"
            bucket["by_category"][category] = round(
                bucket["by_category"].get(category, 0.0) + float(total), 2
            )
        return {
            "count": len(records),
            "unpriced": unpriced,
            "currencies": sorted(currencies.values(), key=lambda item: item["currency"]),
        }

    def _append(self, record):
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _write(self, records):
        payload = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
        self.path.write_text(payload, encoding="utf-8")


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return value
