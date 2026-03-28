from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, Iterable, List


def normalize_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = list(records)
    if not rows:
        return []
    ordered_keys = []
    for row in rows:
        for key in row.keys():
            if key not in ordered_keys:
                ordered_keys.append(key)

    normalized = []
    for row in rows:
        normalized.append({key: _to_cell_value(row.get(key)) for key in ordered_keys})
    return normalized


def export_csv_bytes(records: Iterable[Dict[str, Any]]) -> bytes:
    rows = normalize_records(records)
    if not rows:
        return b""

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def export_json_bytes(records: Iterable[Dict[str, Any]]) -> bytes:
    rows = normalize_records(records)
    return json.dumps(rows, indent=2, ensure_ascii=False).encode("utf-8")


def export_xlsx_bytes(records: Iterable[Dict[str, Any]], sheet_name: str = "results") -> bytes:
    rows = normalize_records(records)
    try:
        from openpyxl import Workbook
    except Exception as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError("openpyxl is required for Excel export") from exc

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31] or "results"

    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(header, "") for header in headers])
    else:
        ws.append(["no_data"])

    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()


def export_pdf_bytes(records: Iterable[Dict[str, Any]], title: str = "Export") -> bytes:
    rows = normalize_records(records)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError("reportlab is required for PDF export") from exc

    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=letter)
    width, height = letter

    y = height - 40
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, title)
    y -= 20

    if not rows:
        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, y, "No data available.")
    else:
        headers = list(rows[0].keys())
        pdf.setFont("Courier", 8)
        header_text = " | ".join(headers)
        pdf.drawString(40, y, header_text[:140])
        y -= 14
        pdf.line(40, y, width - 40, y)
        y -= 12
        for row in rows:
            line = " | ".join(str(row.get(h, "")) for h in headers)
            pdf.drawString(40, y, line[:140])
            y -= 12
            if y < 50:
                pdf.showPage()
                y = height - 40
                pdf.setFont("Courier", 8)

    pdf.save()
    return stream.getvalue()


def _to_cell_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value
