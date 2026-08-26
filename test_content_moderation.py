# -*- coding: utf-8 -*-
"""
content_moderation.py'nin normalizasyon (leetspeak/boslukla ayirma),
ReDoS-guvenli regex dogrulama ve check_content (config + DB kural motoru)
davranisini dogrular. Gercek instance/enigma.db'ye DOKUNMAZ -- kendi gecici
SQLite dosyasini kullanir.
"""

import os
import sys
import tempfile
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"

from app import app
from models import db, ContentRule

with app.app_context():
    db.create_all()

import content_moderation as cm

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
# normalize_for_moderation -- leetspeak + boslukla/noktayla ayirma
# ==========================================================
check(
    "normalize: k.ü.f.ü.r (nokta ile ayrik) -> kufur icerir",
    "kufur" in cm.normalize_for_moderation("bu bir k.ü.f.ü.r kelimesi"),
)
check(
    "normalize: k u f u r (bosluk ile ayrik) -> kufur icerir",
    "kufur" in cm.normalize_for_moderation("bu bir k u f u r kelimesi"),
)
check(
    "normalize: leetspeak (4->a, 0->o, 3->e) -> duz metne cevriliyor",
    cm.normalize_for_moderation("s4l4k") == "salak",
    cm.normalize_for_moderation("s4l4k"),
)
check(
    "normalize (KORUMA): siradan iki kelime arasindaki bosluk BOZULMUYOR",
    "bu kotu" in cm.normalize_for_moderation("Bu kötü bir davranış") or
    cm.normalize_for_moderation("Bu kötü bir davranış").startswith("bu kotu"),
    cm.normalize_for_moderation("Bu kötü bir davranış"),
)

# ==========================================================
# check_content -- config.PROFANITY_WORDS (kod listesi)
# ==========================================================
match = cm.check_content("sen tam bir salaksın")
check("check_content: config listesindeki 'salak' kelimesi yakalaniyor", match is not None and match.category == "kufur", match)

match = cm.check_content("s.a.l.a.k herif")
check("check_content: ayrik yazilmis 'salak' da yakalaniyor", match is not None, match)

match = cm.check_content("merhaba, rezervasyonum hakkında bilgi almak istiyorum")
check("check_content: temiz mail -> eslesme yok", match is None, match)

# ==========================================================
# check_content -- panelden eklenen DB kurallari (keyword + regex)
# ==========================================================
with app.app_context():
    kw_rule = ContentRule(pattern="dolandirici", rule_type="keyword", category="spam", is_active=True)
    regex_rule = ContentRule(pattern=r"kazandiniz.{0,20}tikla", rule_type="regex", category="spam", is_active=True)
    inactive_rule = ContentRule(pattern="pasifkelime", rule_type="keyword", category="diger", is_active=False)
    db.session.add_all([kw_rule, regex_rule, inactive_rule])
    db.session.commit()

match = cm.check_content("siz bir dolandiricisiniz")
check(
    "check_content: panelden eklenen keyword kurali yakalaniyor",
    match is not None and match.rule_source == "db" and match.category == "spam",
    match,
)

match = cm.check_content("tebrikler kazandiniz hemen tikla")
check(
    "check_content: panelden eklenen regex kurali yakalaniyor",
    match is not None and match.rule_source == "db",
    match,
)

match = cm.check_content("bu mailde pasifkelime geciyor")
check("check_content: PASIF kural eslesmiyor (is_active=False)", match is None, match)

# ==========================================================
# validate_regex_pattern -- ReDoS koruması ve genel geçerlilik
# ==========================================================
check("validate_regex_pattern: gecerli basit regex -> None (hata yok)", cm.validate_regex_pattern(r"kazandiniz.*tikla") is None)
check("validate_regex_pattern: bozuk regex sozdizimi -> hata mesaji doner", cm.validate_regex_pattern(r"(unclosed[") is not None)
check("validate_regex_pattern: bos pattern -> hata mesaji doner", cm.validate_regex_pattern("") is not None)
check(
    f"validate_regex_pattern: {cm.MAX_PATTERN_LENGTH} karakter siniri asilinca hata",
    cm.validate_regex_pattern("a" * (cm.MAX_PATTERN_LENGTH + 1)) is not None,
)

_start = time.time()
redos_result = cm.validate_regex_pattern(r"(a+)+$")
_elapsed = time.time() - _start
check(
    "validate_regex_pattern (ReDoS): klasik catastrophic-backtracking deseni REDDEDILIYOR",
    redos_result is not None,
    redos_result,
)
check(
    "validate_regex_pattern (ReDoS): reddetme makul sürede dönüyor (thread'i sonsuza kadar beklemiyor)",
    _elapsed < 2.0,
    f"{_elapsed:.2f}s",
)

# ==========================================================
# create_flagged_mail -- round-trip + maskeleme
# ==========================================================
match = cm.ModerationMatch(category="kufur", rule_source="config", rule_id=None, pattern="salak", snippet="sen tam bir salaksın")
flagged_id = cm.create_flagged_mail("kotu@ornek.com", "Kötü Niyetli", "deneme", "sen tam bir salaksın", match)

with app.app_context():
    from models import FlaggedMail
    row = db.session.get(FlaggedMail, flagged_id)
    check("create_flagged_mail: kayit DB'ye yazilmis", row is not None)
    check("create_flagged_mail: durum varsayilan olarak 'pending'", row.status == "pending", row.status)
    masked = row.to_dict(reveal=False)
    check(
        "FlaggedMail.to_dict (maskeli): ham kufur metni GORUNMUYOR",
        "salak" not in masked["matched_pattern"] and "*" in masked["matched_pattern"],
        masked["matched_pattern"],
    )
    revealed = row.to_dict(reveal=True)
    check("FlaggedMail.to_dict (reveal=True): ham metin gorunuyor", revealed["matched_pattern"] == "salak", revealed["matched_pattern"])

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
