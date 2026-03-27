import json

import pytest

from thesis_prototype.demo_exports import (
    export_csv_bytes,
    export_json_bytes,
    export_pdf_bytes,
    export_xlsx_bytes,
    normalize_records,
)


def test_normalize_records_and_csv_json_exports() -> None:
    rows = [
        {"id": "1", "status": "PASS", "extra": {"a": 1}},
        {"id": "2", "status": "FAIL", "message": "Missing label"},
    ]

    normalized = normalize_records(rows)
    assert len(normalized) == 2

    csv_bytes = export_csv_bytes(rows)
    assert b"id,status" in csv_bytes

    json_bytes = export_json_bytes(rows)
    payload = json.loads(json_bytes.decode("utf-8"))
    assert payload[0]["id"] == "1"


def test_empty_export_behaviors() -> None:
    assert export_csv_bytes([]) == b""
    assert export_json_bytes([]) == b"[]"


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("openpyxl") is None,
    reason="openpyxl not installed",
)
def test_xlsx_export_bytes_generated() -> None:
    data = [{"id": "1", "status": "PASS"}]
    blob = export_xlsx_bytes(data)
    assert len(blob) > 100


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("reportlab") is None,
    reason="reportlab not installed",
)
def test_pdf_export_bytes_generated() -> None:
    data = [{"id": "1", "status": "PASS"}]
    blob = export_pdf_bytes(data, title="Demo")
    assert blob.startswith(b"%PDF")
