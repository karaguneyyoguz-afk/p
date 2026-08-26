# -*- coding: utf-8 -*-
"""
EmailProcessor.is_link_only_content() dogrulamasi -- gercek bir istek
tasimayan, sadece cikplak bir link iceren mailleri (canli ortamda gozlemlendi:
tum govdesi tek bir YouTube linki olan bir mail TESIS_ILETISIM catch-all'ina
dusup ticket'a donusmustu) yakalarken, linke ESLIK EDEN gercek bir soru/talep
oldugunda yanlislikla atlamadigini test eder. Ag baglantisi gerektirmez.
"""

import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from mail_processor import EmailProcessor

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
# 1) Canli ornek: govde SADECE bir link -> atlanmali
# ==========================================================
body = "https://www.youtube.com/watch?v=kVPoKfY0ZSo"
check("Link-1 (CANLI ORNEK): salt YouTube linki -> link-only", EmailProcessor.is_link_only_content(body) is True)

body = "https://www.youtube.com/watch?v=kVPoKfY0ZSo\n\n"
check("Link-2: link + bosluk/satir sonu -> link-only", EmailProcessor.is_link_only_content(body) is True)

body = "Selam\nhttps://www.youtube.com/watch?v=kVPoKfY0ZSo"
check("Link-3: link + tek kelimelik selam -> yine link-only (esik altinda)", EmailProcessor.is_link_only_content(body) is True)

# ==========================================================
# 2) Gercek talep + link birlikte -> ATLANMAMALI
# ==========================================================
body = (
    "Merhaba, şu turla ilgili detaylı bilgi almak istiyorum: "
    "https://tatilbudur.com/tur/12345 Katılmak istiyorum, fiyat ve tarihleri öğrenebilir miyim?"
)
check("Real-1: link + gercek soru/talep -> link-only DEGIL", EmailProcessor.is_link_only_content(body) is False)

body = "Rezervasyonumun iptalini istiyorum, ekte fatura var: https://ornek.com/fatura.pdf"
check("Real-2: link + iptal talebi -> link-only DEGIL", EmailProcessor.is_link_only_content(body) is False)

# ==========================================================
# 3) Link YOK -> hicbir zaman link-only sayilmamali (bu fonksiyonun isi degil)
# ==========================================================
body = "Merhaba, rezervasyonum hakkında bilgi almak istiyorum."
check("NoLink-1: link icermeyen normal mail -> link-only DEGIL", EmailProcessor.is_link_only_content(body) is False)

check("NoLink-2: bos govde -> link-only DEGIL", EmailProcessor.is_link_only_content("") is False)

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
