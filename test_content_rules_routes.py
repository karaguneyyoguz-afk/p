# -*- coding: utf-8 -*-
"""
/api/content-rules/* ve /api/flagged-mails/* uc noktalarinin CRUD, dogrulama
ve yetkilendirme davranisini kontrol eder. Gercek CSM/SMTP cagrisi
YAPILMAZ -- bu yuzden approve/reject akislarinin son adimi (ticket acma /
mail gonderme) burada degil, main.py'nin _continue_after_content_check'i
zaten process_email testleriyle dolayli kapsanan mevcut mantigina emanet;
burada sadece CRUD + yetki + FlaggedMail veri katmani test ediliyor.
"""

import os
import sys
import tempfile

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"

from app import app
from config import PROFANITY_WORDS
from dev_test_helpers import login_test_client
from models import ContentRule, FlaggedMail, TrustedDomain, db

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
# _resolve_relative_sqlite_url -- content_moderation.py'nin standalone
# SQLAlchemy engine'inin, Flask-SQLAlchemy'nin (panelin db.session'ı) AYNI
# dosyaya baktığından emin olması. CANLI ORTAMDA BULUNDU: .env'deki
# DATABASE_URL=sqlite:///enigma.db (göreli yol) ile panel instance/enigma.db
# yazarken, bu modül düzeltilmeden önce proje kökündeki boş/tablosuz bir
# enigma.db'ye bakıyordu -- panelden eklenen HİÇBİR ContentRule/TrustedDomain
# gerçek mail işlemede hiç görülmüyordu.
# ==========================================================
from content_moderation import _resolve_relative_sqlite_url

check(
    "_resolve_relative_sqlite_url (CANLI HATA DÜZELTMESİ): göreli yol instance/ klasörüne çözülüyor",
    _resolve_relative_sqlite_url("sqlite:///enigma.db").replace("\\", "/").endswith("instance/enigma.db"),
    _resolve_relative_sqlite_url("sqlite:///enigma.db"),
)
check(
    "_resolve_relative_sqlite_url: zaten mutlak olan (Windows sürücü harfli) bir yol DOKUNULMADAN kalıyor",
    _resolve_relative_sqlite_url("sqlite:///C:/Users/test/db.sqlite") == "sqlite:///C:/Users/test/db.sqlite",
)
check(
    "_resolve_relative_sqlite_url: zaten mutlak (POSIX) bir yol dokunulmadan kalıyor",
    _resolve_relative_sqlite_url("sqlite:////tmp/test.db") == "sqlite:////tmp/test.db",
)
check(
    "_resolve_relative_sqlite_url: sqlite dışı bir URL (ör. postgres) hiç dokunulmadan geçiyor",
    _resolve_relative_sqlite_url("postgresql://user:pass@host/db") == "postgresql://user:pass@host/db",
)

admin_client = app.test_client()
admin_csrf = login_test_client(app, admin_client, email="admin@local.test", role="admin")
admin_headers = {"X-CSRF-Token": admin_csrf}

operator_client = app.test_client()
operator_csrf = login_test_client(app, operator_client, email="operator@local.test", role="operator")
operator_headers = {"X-CSRF-Token": operator_csrf}

# ==========================================================
# Yetkilendirme -- operator (content_rules ekranı verilmemiş rol) 403 almalı
# ==========================================================
resp = operator_client.get("/api/content-rules")
check("Yetki: operator rolü /api/content-rules'a GET ile bile giremiyor (403)", resp.status_code == 403, resp.status_code)

resp = operator_client.post("/api/content-rules", json={"pattern": "x", "rule_type": "keyword", "category": "spam"}, headers=operator_headers)
check("Yetki: operator rolü kural OLUŞTURAMIYOR (403)", resp.status_code == 403, resp.status_code)

resp = operator_client.get("/api/flagged-mails")
check("Yetki: operator rolü /api/flagged-mails'a giremiyor (403)", resp.status_code == 403, resp.status_code)

resp = admin_client.get("/api/content-rules")
check("Yetki: admin rolü içerik kurallarını görebiliyor (200)", resp.status_code == 200, resp.status_code)

# ==========================================================
# CRUD -- oluşturma, doğrulama, listeleme, güncelleme, silme
# ==========================================================
resp = admin_client.post(
    "/api/content-rules",
    json={"pattern": "dolandirici", "rule_type": "keyword", "category": "spam"},
    headers=admin_headers,
)
check("CRUD: keyword kural oluşturma -> 201", resp.status_code == 201, resp.get_json())
created_rule = resp.get_json()
check("CRUD: oluşturulan kuralda created_by_id dolu (audit için)", created_rule.get("created_by_id") is not None, created_rule)

resp = admin_client.post(
    "/api/content-rules",
    json={"pattern": "kazandiniz.*tikla", "rule_type": "regex", "category": "spam"},
    headers=admin_headers,
)
check("CRUD: geçerli regex kural oluşturma -> 201", resp.status_code == 201, resp.get_json())

resp = admin_client.post(
    "/api/content-rules",
    json={"pattern": "(a+)+$", "rule_type": "regex", "category": "spam"},
    headers=admin_headers,
)
check("CRUD (ReDoS KORUMA): tehlikeli regex kural oluşturma REDDEDİLİYOR (400)", resp.status_code == 400, resp.get_json())

resp = admin_client.post(
    "/api/content-rules",
    json={"pattern": "x", "rule_type": "gecersiz-tip", "category": "spam"},
    headers=admin_headers,
)
check("CRUD (doğrulama): geçersiz rule_type -> 400", resp.status_code == 400, resp.get_json())

resp = admin_client.post(
    "/api/content-rules",
    json={"pattern": "", "rule_type": "keyword", "category": "spam"},
    headers=admin_headers,
)
check("CRUD (doğrulama): boş pattern -> 400", resp.status_code == 400, resp.get_json())

resp = admin_client.get("/api/content-rules")
panel_rules = [r for r in resp.get_json()["rules"] if r["source"] == "panel"]
config_rules = [r for r in resp.get_json()["rules"] if r["source"] == "config"]
check(
    "CRUD: liste panel'den 2 aktif kural içeriyor (ReDoS/geçersiz olanlar hiç kaydedilmedi)",
    len(panel_rules) == 2, resp.get_json(),
)
check(
    "CRUD (YENİ ÖZELLİK, kullanıcı isteği): config.PROFANITY_WORDS'ün tamamı da 'source: config' olarak listede",
    len(config_rules) == len(PROFANITY_WORDS) and all(r["pattern"] in PROFANITY_WORDS for r in config_rules),
    len(config_rules),
)

rule_id = created_rule["id"]
resp = admin_client.patch(f"/api/content-rules/{rule_id}", json={"is_active": False}, headers=admin_headers)
check("CRUD: kuralı pasif yapma -> 200 ve is_active=False", resp.status_code == 200 and resp.get_json()["is_active"] is False, resp.get_json())

resp = admin_client.delete(f"/api/content-rules/{rule_id}", headers=admin_headers)
check("CRUD: kural silme -> 200", resp.status_code == 200, resp.get_json())

resp = admin_client.get("/api/content-rules")
panel_rules = [r for r in resp.get_json()["rules"] if r["source"] == "panel"]
check("CRUD: silinen kural artık panel listesinde yok", len(panel_rules) == 1, panel_rules)

# ==========================================================
# /api/content-rules/test -- kaydetmeden deneme
# ==========================================================
resp = admin_client.post("/api/content-rules/test", json={"text": "tebrikler kazandiniz hemen tikla"}, headers=admin_headers)
check("Test endpoint: aktif regex kurala uyan metin -> matched=True", resp.get_json()["matched"] is True, resp.get_json())

resp = admin_client.post("/api/content-rules/test", json={"text": "rezervasyonum hakkında bilgi istiyorum"}, headers=admin_headers)
check("Test endpoint: temiz metin -> matched=False", resp.get_json()["matched"] is False, resp.get_json())

# ==========================================================
# FlaggedMail -- listeleme, detay, maskeleme (approve/reject akışının SON
# adımı gerçek CSM/SMTP gerektirdiği için burada test edilmiyor)
# ==========================================================
with app.app_context():
    row = FlaggedMail(
        sender_email="kotu@ornek.com", sender_name="Kötü Niyetli", subject="deneme",
        mail_body="sen tam bir salaksın", matched_category="kufur",
        matched_rule_source="config", matched_pattern="salak", matched_snippet="tam bir salaksın",
        status="pending",
    )
    db.session.add(row)
    db.session.commit()
    flagged_id = row.id

resp = operator_client.get("/api/flagged-mails")
check("Yetki: operator işaretli mailleri de göremiyor (403)", resp.status_code == 403, resp.status_code)

resp = admin_client.get("/api/flagged-mails")
check("FlaggedMail: liste dönüyor, en az 1 kayıt var", resp.status_code == 200 and resp.get_json()["total"] >= 1, resp.get_json())

resp = admin_client.get(f"/api/flagged-mails/{flagged_id}")
masked = resp.get_json()["flagged_mail"]
check("FlaggedMail detay (varsayılan, maskeli): ham küfür kelimesi metinde YOK", "salak" not in masked["mail_body"], masked["mail_body"])

resp = admin_client.get(f"/api/flagged-mails/{flagged_id}?reveal=true")
revealed = resp.get_json()["flagged_mail"]
check("FlaggedMail detay (?reveal=true): ham metin görünüyor", "salak" in revealed["mail_body"], revealed["mail_body"])

resp = admin_client.get("/api/flagged-mails?status=pending")
check("FlaggedMail: status filtresi çalışıyor", resp.get_json()["total"] >= 1, resp.get_json())

resp = admin_client.get("/api/flagged-mails?status=approved")
check("FlaggedMail: olmayan durum için boş liste (henüz onaylanan yok)", resp.get_json()["total"] == 0, resp.get_json())

# ==========================================================
# Kabul edilen linkler (TrustedDomain) -- kullanıcı isteği: bu ekranda olsun
# ==========================================================
resp = operator_client.get("/api/trusted-domains")
check("Yetki: operator güvenilir alan adlarını da göremiyor (403)", resp.status_code == 403, resp.status_code)

resp = admin_client.get("/api/trusted-domains")
check(
    "TrustedDomain: temel liste (tatilbudur.com vb.) base_domains'te görünüyor",
    "tatilbudur.com" in resp.get_json()["base_domains"],
    resp.get_json(),
)

resp = admin_client.post(
    "/api/trusted-domains",
    json={"domain": "https://Ornek-Tedarikci.com/kampanya?x=1"},
    headers=admin_headers,
)
check(
    "TrustedDomain: tam bir URL yapıştırılınca sadece alan adı çıkarılıp kaydediliyor",
    resp.status_code == 201 and resp.get_json()["domain"] == "ornek-tedarikci.com",
    resp.get_json(),
)
domain_id = resp.get_json()["id"]

resp = admin_client.post("/api/trusted-domains", json={"domain": "ornek-tedarikci.com"}, headers=admin_headers)
check("TrustedDomain: aynı alan adı ikinci kez eklenemiyor (409)", resp.status_code == 409, resp.get_json())

resp = admin_client.post("/api/trusted-domains", json={"domain": "tatilbudur.com"}, headers=admin_headers)
check("TrustedDomain: zaten temel listede olan bir alan adı reddediliyor (409)", resp.status_code == 409, resp.get_json())

resp = admin_client.post("/api/trusted-domains", json={"domain": "gecersiz alan adi!!"}, headers=admin_headers)
check("TrustedDomain: geçersiz alan adı formatı reddediliyor (400)", resp.status_code == 400, resp.get_json())

resp = admin_client.get("/api/trusted-domains")
check(
    "TrustedDomain: eklenen alan adı listede görünüyor",
    any(d["domain"] == "ornek-tedarikci.com" for d in resp.get_json()["domains"]),
    resp.get_json(),
)

resp = admin_client.delete(f"/api/trusted-domains/{domain_id}", headers=admin_headers)
check("TrustedDomain: silme -> 200", resp.status_code == 200, resp.get_json())

resp = admin_client.get("/api/trusted-domains")
check(
    "TrustedDomain: silinen alan adı artık listede yok",
    all(d["id"] != domain_id for d in resp.get_json()["domains"]),
    resp.get_json(),
)

# phishing_check.get_safe_domains() gerçekten bu tabloyu okuyor mu -- uçtan uca
admin_client.post("/api/trusted-domains", json={"domain": "guvenilir-ortak.com"}, headers=admin_headers)
from phishing_check import get_safe_domains
check(
    "TrustedDomain (uçtan uca): panelden eklenen alan adı phishing_check.get_safe_domains()'te görünüyor",
    "guvenilir-ortak.com" in get_safe_domains(),
    get_safe_domains(),
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
