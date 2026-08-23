# -*- coding: utf-8 -*-
"""
bulk_shift.py (siniflandirma, payload insasi, Excel ayristirma) ve
/api/bulk-shift/* uc noktalarinin dogrulama davranisini kontrol eder.
Gercek CSM auth/create_ticket cagrisi YAPILMAZ (harici uretim sistemine
gercek istek atmadan test edilebilecek her sey buradadir).
"""

import io
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openpyxl import Workbook

from bulk_shift import (
    classify_shift_type,
    build_bulk_ticket_payload,
    parse_excel_rows,
    MAX_ROWS,
)
from app import app

passed = 0
failed = 0
results = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        results.append(("PASS", name, detail))
    else:
        failed += 1
        results.append(("FAIL", name, detail))


# ==========================================================
# classify_shift_type
# ==========================================================
check("classify: 'Otel Kaynaklı' -> OTEL_KAYNAKLI", classify_shift_type("Otel Kaynaklı") == "OTEL_KAYNAKLI")
check(
    "classify: 'Ödeme Tamamlama' -> ODEME_TAMAMLAMA",
    classify_shift_type("Ödeme Tamamlama") == "ODEME_TAMAMLAMA",
)
check(
    "classify: bilinmeyen metin -> varsayilan OPERASYON_KAYNAKLI",
    classify_shift_type("Bilinmeyen Tip") == "OPERASYON_KAYNAKLI",
)
check("classify: bos string -> varsayilan OPERASYON_KAYNAKLI", classify_shift_type("") == "OPERASYON_KAYNAKLI")

# ==========================================================
# build_bulk_ticket_payload
# ==========================================================
reporter = {"first_name": "Test", "last_name": "Kullanici", "phone": "+905000000000", "email": "test@example.com"}
payload = build_bulk_ticket_payload(
    reservation_no="123456",
    shift_type_label="Otel Kaynaklı",
    alternative_text="Toplu Kaydırma İşlemi",
    parent_ticket_uuid="parent-uuid-123",
    reporter=reporter,
)
check(
    "payload: parent ticket UUID dogru yerlestirilmis",
    payload["ticketRelationList"][0]["parentTicketUUID"] == "parent-uuid-123",
    payload["ticketRelationList"],
)
check(
    "payload: reporter bilgisi partyRole'e yansimis (hardcoded degil)",
    payload["partyRole"]["party"]["firstName"] == "Test"
    and payload["partyRole"]["party"]["fullName"] == "Test Kullanici",
    payload["partyRole"]["party"],
)
check(
    "payload: OTEL_KAYNAKLI mapping'i kullanilmis",
    payload["subCategory"]["shortCode"] == "OTEL_KAYNAKLI",
    payload["subCategory"],
)
check(
    "payload: relatedProduct.serviceNumber rezervasyon no'yu tasiyor",
    payload["relatedProduct"]["serviceNumber"] == "123456",
)

# ==========================================================
# parse_excel_rows
# ==========================================================
def make_excel(rows, headers=("Rezervasyon No", "Kaydırma Tipi", "Alternatif 1")):
    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


good_excel = make_excel(
    [
        ("553044193", "Otel Kaynaklı", "Alt 1"),
        ("358109758", "Operasyon Kaynaklı", "Alt 2"),
        ("", "Boş satır atlanmalı", "x"),
    ]
)
parsed = parse_excel_rows(good_excel)
check("parse_excel_rows: 2 gecerli satir donuyor (bos satir atlaniyor)", len(parsed) == 2, parsed)
check("parse_excel_rows: ilk satirin alanlari dogru okunmus", parsed[0]["reservation_no"] == "553044193", parsed[0])

missing_alt_excel = make_excel([("111", "Otel Kaynaklı", "")])
parsed2 = parse_excel_rows(missing_alt_excel)
check(
    "parse_excel_rows: bos 'Alternatif 1' icin varsayilan metin kullanilir",
    parsed2[0]["alternative"] == "Toplu Kaydırma İşlemi",
    parsed2,
)

bad_columns_excel = make_excel([("x", "y", "z")], headers=("Yanlis", "Sutunlar", "Burada"))
try:
    parse_excel_rows(bad_columns_excel)
    check("parse_excel_rows: eksik sutun ValueError firlatir", False, "hata firlatmadi")
except ValueError as e:
    check("parse_excel_rows: eksik sutun ValueError firlatir", "Rezervasyon No" in str(e), str(e))

too_many_excel = make_excel([(str(i), "Otel Kaynaklı", "x") for i in range(MAX_ROWS + 5)])
try:
    parse_excel_rows(too_many_excel)
    check(f"parse_excel_rows: {MAX_ROWS} satir sinirini asinca ValueError firlatir", False, "hata firlatmadi")
except ValueError as e:
    check(f"parse_excel_rows: {MAX_ROWS} satir sinirini asinca ValueError firlatir", str(MAX_ROWS) in str(e), str(e))

# ==========================================================
# Endpoint dogrulama (Flask test client) -- gercek CSM cagrisi yapilmayan yollar
# ==========================================================
client = app.test_client()

resp = client.get("/api/bulk-shift/env")
check("GET /api/bulk-shift/env -> 200 + environment alani", resp.status_code == 200 and "environment" in resp.get_json())

resp = client.post("/api/bulk-shift/upload", data={})
check("POST upload: dosya yoksa 400", resp.status_code == 400 and "dosya" in resp.get_json().get("error", "").lower())

# openpyxl (read_only=True) closes the stream it's given once parsed, so each
# upload needs its own fresh buffer rather than seeking/reusing one.
resp = client.post(
    "/api/bulk-shift/upload",
    data={"file": (make_excel([("553044193", "Otel Kaynaklı", "Alt 1")]), "test.xlsx")},
    content_type="multipart/form-data",
)
check(
    "POST upload: parent_ticket_uuid yoksa 400",
    resp.status_code == 400 and "üst ticket" in resp.get_json().get("error", "").lower(),
    resp.get_json(),
)

resp = client.post(
    "/api/bulk-shift/upload",
    data={
        "file": (make_excel([("553044193", "Otel Kaynaklı", "Alt 1")]), "test.xlsx"),
        "parent_ticket_uuid": "abc",
    },
    content_type="multipart/form-data",
)
check(
    "POST upload: reporter alanlari eksikse 400",
    resp.status_code == 400 and "raporlayan" in resp.get_json().get("error", "").lower(),
    resp.get_json(),
)

resp = client.post(
    "/api/bulk-shift/upload",
    data={
        "file": (make_excel([("x", "y", "z")], headers=("Yanlis", "Sutunlar", "Burada")), "bad.xlsx"),
        "parent_ticket_uuid": "abc",
        "reporter_first_name": "T",
        "reporter_last_name": "K",
        "reporter_phone": "1",
        "reporter_email": "a@b.com",
    },
    content_type="multipart/form-data",
)
check(
    "POST upload: yanlis sutunlu Excel icin 400 (Rezervasyon No bulunamadi)",
    resp.status_code == 400 and "Rezervasyon No" in resp.get_json().get("error", ""),
    resp.get_json(),
)

# ==========================================================
# OZET
# ==========================================================
print("=" * 60)
for status, name, detail in results:
    mark = "[OK]" if status == "PASS" else "[FAIL]"
    line = f"{mark} {name}"
    if status == "FAIL":
        line += f"  -> {detail}"
    print(line)

print("=" * 60)
print(f"TOPLAM: {passed + failed} senaryo | BASARILI: {passed} | BASARISIZ: {failed}")
if failed:
    raise SystemExit(1)
