# -*- coding: utf-8 -*-
"""
/api/reports/* endpoint'lerinin arkasindaki saf yardimci fonksiyonlari
(_parse_range, _cutoff_from_range, _apply_report_filters) ve endpoint'lerin
sozlesmesini (response sekli, limit/offset/filtre davranisi) dogrular.
Ag baglantisi gerektirmez — sadece yerel mail_processing_log.jsonl okunur.
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Temp SQLite DB for the login below -- must be set before `from app import
# app` (app.py reads DATABASE_URL at import time). Never touches the real
# instance/enigma.db.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"

from app import app, _parse_range, _cutoff_from_range, _apply_report_filters
from dev_test_helpers import login_test_client

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
# _parse_range
# ==========================================================
check("parse_range: '7d' -> (7, 'd')", _parse_range("7d", 14, "d") == (7, "d"))
check("parse_range: '24h' -> (24, 'h')", _parse_range("24h", 14, "d") == (24, "h"))
check("parse_range: None -> varsayilan", _parse_range(None, 14, "d") == (14, "d"))
check("parse_range: gecersiz string -> varsayilan", _parse_range("abc", 14, "d") == (14, "d"))
check("parse_range: '0d' -> (0, 'd') (sinir deger)", _parse_range("0d", 14, "d") == (0, "d"))

# ==========================================================
# _cutoff_from_range
# ==========================================================
now = datetime.now().astimezone()
cutoff = _cutoff_from_range("1d")
cutoff_dt = datetime.fromisoformat(cutoff) if cutoff else None
delta = (now - cutoff_dt) if cutoff_dt else None
check(
    "cutoff_from_range: '1d' su andan ~1 gun once bir zaman damgasi uretir",
    delta is not None and timedelta(hours=23, minutes=55) < delta < timedelta(hours=24, minutes=5),
    delta,
)
check("cutoff_from_range: None -> None", _cutoff_from_range(None) is None)
check("cutoff_from_range: gecersiz string -> None", _cutoff_from_range("nonsense") is None)

# ==========================================================
# _apply_report_filters
# ==========================================================
sample = [
    {"timestamp": "2026-08-20T10:00:00+03:00", "sender_email": "a@x.com", "classification": "BILGI_ISTEK > FOO"},
    {"timestamp": "2026-08-22T10:00:00+03:00", "sender_email": "B@X.com", "classification": "SIKAYET > BAR"},
    {"timestamp": "2026-08-23T10:00:00+03:00", "sender_email": "c@x.com", "classification": ""},
]

check("apply_filters: filtre yoksa tumu doner", len(_apply_report_filters(sample)) == 3)

filtered_sender = _apply_report_filters(sample, sender="b@x.com")
check(
    "apply_filters: sender filtresi buyuk/kucuk harf duyarsiz tam eslesir",
    [e["sender_email"] for e in filtered_sender] == ["B@X.com"],
    filtered_sender,
)

filtered_class = _apply_report_filters(sample, classification="BILGI_ISTEK")
check(
    "apply_filters: classification filtresi sadece ust seviye segmenti kontrol eder",
    len(filtered_class) == 1 and filtered_class[0]["sender_email"] == "a@x.com",
    filtered_class,
)

filtered_since = _apply_report_filters(sample, since_iso="2026-08-21T00:00:00+03:00")
check(
    "apply_filters: since_iso kesim tarihinden eski kayitlari eler",
    len(filtered_since) == 2,
    filtered_since,
)

filtered_combined = _apply_report_filters(
    sample, sender="c@x.com", since_iso="2026-08-21T00:00:00+03:00"
)
check(
    "apply_filters: sender + since_iso birlikte daraltir",
    len(filtered_combined) == 1 and filtered_combined[0]["sender_email"] == "c@x.com",
    filtered_combined,
)

# ==========================================================
# Endpoint sozlesmesi (Flask test client — ag baglantisi yok)
# ==========================================================
client = app.test_client()
login_test_client(app, client)

resp = client.get("/api/reports/timeseries?range=7d")
check("GET /api/reports/timeseries?range=7d -> 200", resp.status_code == 200, resp.status_code)
body = resp.get_json() or {}
points = body.get("points", [])
check(
    "timeseries: her nokta count/success_count/error_count icerir",
    len(points) > 0 and all({"date", "count", "success_count", "error_count"} <= set(p) for p in points),
    points[:2],
)

resp = client.get("/api/reports/by-classification")
check("GET /api/reports/by-classification -> 200", resp.status_code == 200, resp.status_code)
check(
    "by-classification: 'categories' listesi doner",
    isinstance((resp.get_json() or {}).get("categories"), list),
    resp.get_json(),
)

resp = client.get("/api/reports/by-sender?limit=3")
check(
    "GET /api/reports/by-sender?limit=3 -> 200 ve limit'e uyar",
    resp.status_code == 200 and len((resp.get_json() or {}).get("senders", [])) <= 3,
    resp.get_json(),
)

resp = client.get("/api/reports/by-sender?limit=abc")
check(
    "by-sender: gecersiz limit patlamiyor, varsayilana duser (200)",
    resp.status_code == 200,
    resp.status_code,
)

resp = client.get("/api/tickets?limit=2&offset=0")
tickets_body = resp.get_json() or {}
check(
    "GET /api/tickets sayfalama: limit/offset/total alanlarini iceriyor",
    resp.status_code == 200 and {"tickets", "total", "limit", "offset"} <= set(tickets_body),
    tickets_body,
)
check(
    "GET /api/tickets sayfalama: donen kayit sayisi limit'i asmiyor",
    len(tickets_body.get("tickets", [])) <= 2,
    tickets_body,
)

resp = client.get("/api/tickets?q=zzz-hicbir-eslesme-olmamali-zzz")
check(
    "GET /api/tickets arama: eslesmeyen sorgu icin bos liste ve total=0",
    resp.status_code == 200 and resp.get_json().get("total") == 0,
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
