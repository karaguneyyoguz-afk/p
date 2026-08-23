# -*- coding: utf-8 -*-
"""
Kapsamli senaryo testi.
mail_processor.EmailCategorizer.categorize() icin tum siniflandirma dallarini,
oncelik/çakisma (precedence) durumlarini ve validators.py fonksiyonlarini
tek tek kontrol eder. Ag baglantisi (IMAP/SMTP/CSM API) gerektirmez.
"""

import sys

# Not: Windows'ta konsol varsayilan olarak cp1254 kullanabiliyor, bu da
# csm_api.TicketPayloadBuilder.build_payload() gibi emoji print eden
# fonksiyonlar test edilirken UnicodeEncodeError'a yol aciyordu.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from mail_processor import EmailCategorizer
from validators import (
    contains_profanity,
    extract_invoice_attributes,
    is_valid_turkish_id,
    is_valid_tax_id,
    is_valid_email,
    extract_reservation_number,
    detect_priority_level,
)
from csm_api import TicketPayloadBuilder

# validators.py ile uretilen, algoritmik olarak GECERLI test degerleri
VALID_TC = "90939729806"
VALID_VKN = "3513969371"

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


def cat(subject, body, sender="test@example.com"):
    return EmailCategorizer.categorize(subject, body, sender)


# ==========================================================
# 1) OTOBUS (BILGI_ISTEK > ULASIM > OTOBUS)
# ==========================================================
r = cat("", "Tur otobüsünün güzergahını öğrenmek istiyorum, hangi güzergahtan geçiyor?")
check("Otobus-1: tur otobusu + guzergah", r["classification"] == "BILGI_ISTEK > ULASIM > OTOBUS", r["classification"])

r = cat("", "Otobüs şoförünün iletişim bilgilerini alabilir miyim?")
check("Otobus-2: sofor iletisim", r["classification"] == "BILGI_ISTEK > ULASIM > OTOBUS", r["classification"])

r = cat("", "Tur rehberinin iletişim bilgisini otobüs için paylaşır mısınız?")
check("Otobus-3: tur rehberi + otobus", r["classification"] == "BILGI_ISTEK > ULASIM > OTOBUS", r["classification"])

# ==========================================================
# 2) ULASIM DEGISIKLIK HAKKI SORGULAMA
# ==========================================================
r = cat("", "Dönüş transferinin yapılması konusunda bilgi almak istiyorum.")
check("Transfer-1: donus transferi", r["classification"] == "BILGI_ISTEK > ULASIM > DEGISIKLIK_HAKKI_SORGULAMA", r["classification"])

r = cat("", "No show uygulanır mı bilmiyorum, kendi imkanlarıyla otele gideceğim.")
check("Transfer-2: no show + kendi imkanlariyla", r["classification"] == "BILGI_ISTEK > ULASIM > DEGISIKLIK_HAKKI_SORGULAMA", r["classification"])

# Not: "ucak bileti" + degisiklik niyeti birlikte gectiginde, somut/eylemsel
# Backoffice talebi (UCAK_BILETI_DEGISIKLIGI) genel Ulasim bilgi-istek dalindan
# ONCE degerlendiriliyor (COLLISION-1/2 duzeltmesinin bir sonucu).
r = cat("", "Uçak bileti için tarih değişikliği yapmak istiyorum, cezai işlem uygulanır mı?")
check("Transfer-3: ucak bileti + tarih degisikligi -> somut Backoffice talebi", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > UCAK_BILETI_DEGISIKLIGI", r["classification"])

# --- YENI KIRILIM (musteri onayli): SIKAYET > ULASIM > TRANSFER ---
# "transfer" + acik sikayet tonu (aksaklik/magduriyet/sikayet), genel
# Bilgi-Istek > Ulasim > Degisiklik Hakki Sorgulama'dan ONCE degerlendirilmeli.
r = cat("", "Merhaba, tatilimiz için satın aldığımız havalimanı transfer hizmetinde büyük bir aksaklık yaşadık. Transfer aracı, belirtilen saatte havalimanında bizi karşılamaya gelmedi ve uzun süre mağdur olduk. Bu olumsuzlukla ilgili şikayetimin incelenerek tarafıma dönüş yapılmasını rica ederim, iyi çalışmalar.")
check("Sikayet-Ulasim-Transfer (ONAYLI): transfer araci gelmedi, magduriyet", r["classification"] == "SIKAYET > ULASIM > TRANSFER", r["classification"])

# --- YENI KIRILIM (musteri onayli): SIKAYET > ULASIM > DIGER ---
# "ulasim" + sikayet tonu var ama transfer/otobus/ucak gibi spesifik bir alt
# konu YOK -- catch-all/yedek dal.
r = cat("", "İyi günler, rezervasyonumuz kapsamındaki genel ulaşım ve seyahat organizasyon süreçlerinde yaşanan aksaklıklar nedeniyle tatilimiz olumsuz etkilendi. Ulaşım kalitesiyle ilgili yaşadığımız bu genel memnuniyetsizliğin değerlendirilmesini talep ediyorum.")
check("Sikayet-Ulasim-Diger (ONAYLI): genel ulasim sikayeti, spesifik alt konu yok", r["classification"] == "SIKAYET > ULASIM > DIGER", r["classification"])

# Precedence testi (musteri onayli, guncellendi): "degisiklik hakki/ceza" gecmeyen
# bir "otobus" metni artik dogrudan OTOBUS dalina dusuyor (musteri onceligi:
# DEGISIKLIK_HAKKI_SORGULAMA > OTOBUS > BILET).
r = cat("", "Otobüs bileti fiyatını öğrenmek istiyorum.")
check(
    "Precedence-1 (ONAYLI): sadece 'otobus' -> OTOBUS dalina dusmeli",
    r["classification"] == "BILGI_ISTEK > ULASIM > OTOBUS",
    r["classification"],
)

# ==========================================================
# 3) SIKAYET > FATURA (fatura + magduriyet/sikayet kelimeleri)
# ==========================================================
r = cat("", "Faturamla ilgili mağduriyet yaşıyorum, konuyu merkeze bildireceğim.")
check("SikayetFatura-1", r["classification"] == "SIKAYET > FATURA > FATURA_TALEBI_SIKAYETLERI", r["classification"])

r = cat("", "E-faturamla ilgili talebim yanıtsız kaldı, yasal haklarımı kullanacağım.")
check("SikayetFatura-2", r["classification"] == "SIKAYET > FATURA > FATURA_TALEBI_SIKAYETLERI", r["classification"])

r = cat(
    "",
    f"Faturamla ilgili şikayetçiyim.\nŞahıs Adı: Ahmet Yılmaz\nTC: {VALID_TC}\nFatura Adresi: Örnek Mah. No:5 Kadıköy Istanbul\n",
)
check(
    "SikayetFatura-3: gecerli TC ile attribute cikarimi",
    r["classification"] == "SIKAYET > FATURA > FATURA_TALEBI_SIKAYETLERI" and not r["missing_fields"],
    (r["classification"], r["missing_fields"]),
)

# --- Kullanicinin onayladigi senaryo (kirilim.md gozden gecirme sureci) ---
# Gercek musteri mailine yakin format: uzun sikayet metni + "Guncel Fatura Bilgileri:"
# basligi altinda tum zorunlu alanlar + <mailto:...> HTML artefakti iceren e-posta.
r = cat(
    "",
    "Sayın İlgili, Ekte yer alan rezervasyon numaralı tatilimize ait faturanın tarafıma "
    "yanlış bilgilerle kesildiğini ve bu durumun düzeltilmesi için yaptığım başvuruların "
    "yanıtsız kaldığını/geciktirildiğini üzülerek müşahede etmekteyim. Yasal haklarım "
    "çerçevesinde, ekte yer alan fatura ünvanı yanlış olduğu için red veriyoruz. Onaylar "
    "mısınız? talebimi yineliyor; rezervasyon numaralı tatilin faturasını aşağıda "
    "belirttiğim şahıs bilgilerime göre acilen revize edip iletmenizi talep ediyorum. "
    "Aksi takdirde süreci yasal mercilere ve tüketici haklarına taşıyacağımı bilgilerinize "
    "sunarım. Güncel Fatura Bilgileri: Şahıs Adı: Bekir Oğuz Karagüney, TC Kimlik Numarası: "
    "63718240304, Fatura Adresi: Nişantaşı, İstanbul, E-Posta: "
    "karaguneyyoguz@gmail.com<mailto:karaguneyyoguz@gmail.com>. Gereğini rica ederim, iyi çalışmalar.",
    "gonderen@example.com",
)
sirket_sahis_attr = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "SIRKET_ADI_SAHIS_ADI"), None)
tc_secici_attr = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "VERGI_NUMARASI_TC_NUMARASI"), None)
check(
    "SikayetFatura-4 (ONAYLI): gercek musteri sikayet formati, ID'ler dogru",
    r["classification"] == "SIKAYET > FATURA > FATURA_TALEBI_SIKAYETLERI"
    and not r["missing_fields"]
    and sirket_sahis_attr is not None and sirket_sahis_attr["attribute"]["id"] == 100054902
    and tc_secici_attr is not None and tc_secici_attr["attribute"]["id"] == 100054901,
    (r["classification"], r["missing_fields"], r["attributes"]),
)

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# "Şirket Adı - Şahıs Adı (100054902): Şahıs Adı" gibi CIFT SATIRLI, CSM alan
# adlarini/ID'lerini dogrudan referans alan formatlarda, eski regex ilk
# satirdaki ETIKET YANKISINI ("Şahıs Adı" kelimesinin kendisini) gercek deger
# saniyordu. _find_real_match + "(?<!:)\s" ile duzeltildi.
r = cat(
    "",
    "Merhaba,\nTamamladığımız tatil konaklamamız üzerinden haftalar geçmesine "
    "rağmen faturamız hâlâ tarafımıza kesilmedi ve iletilmedi. Bu gecikme ve "
    "mağduriyet nedeniyle şikayetçiyim. Şahıs adına kesilmesi gereken "
    "faturamın bilgileri aşağıdadır:\n\n"
    "Şirket Adı - Şahıs Adı (100054902): Şahıs Adı\n"
    f"Şahıs Adı (100054903): Bekir Oğuz Karagüney\n"
    "Vergi Kimlik Numarası - TC Kimlik Numarası (100054901): TC Kimlik Numarası\n"
    "TC Kimlik Numarası (100054900): 63718240304\n"
    "Fatura Adresi (100000233): Nişantaşı, İstanbul\n"
    "E-Posta (100000234): karaguneyyoguz@gmail.com\n\n"
    "Faturamın acilen düzenlenip gönderilmesini talep ediyorum.",
    "gonderen@example.com",
)
sahis_deger = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "SAHIS_ADI"), None)
adres_deger = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "FATURA_ADRESI"), None)
check(
    "SikayetFatura-5 (CANLI HATA DUZELTMESI): cift satirli 'etiket yankisi' formati, sahis",
    r["classification"] == "SIKAYET > FATURA > FATURA_TALEBI_SIKAYETLERI"
    and not r["missing_fields"]
    and sahis_deger is not None and sahis_deger.get("textValue") == "Bekir Oğuz Karagüney"
    and adres_deger is not None and adres_deger.get("textValue") == "Nişantaşı, İstanbul",
    (r["classification"], r["missing_fields"], r["attributes"]),
)

# Ayni format, sirket versiyonu -- ayrica "Şirket adına düzenlenecek..." gibi
# metnin GIRISINDE gecen dogal "adina" ifadesinin yanlislikla etiket
# sanilmadigini da dogruluyor.
r = cat(
    "",
    "Merhaba,\nKurumsal rezervasyonumuz için faturanın yasal sürede "
    "kesilmemesi ve taleplerimize rağmen tarafımıza ulaştırılmaması "
    "sebebiyle mağduriyet yaşıyoruz. Şirket adına düzenlenecek fatura "
    "bilgilerimiz eksiksiz olarak aşağıdadır:\n\n"
    "Şirket Adı - Şahıs Adı (100054902): Şirket Adı\n"
    "Şirket Adı (100000070): Tatilbudur Seyahat Acenteliği ve Turizm A.Ş.\n"
    "Vergi Kimlik Numarası - TC Kimlik Numarası (100054901): Vergi Kimlik Numarası\n"
    "Vergi Kimlik Numarası (100000066): 8340123456\n"
    "Vergi Dairesi (100000232): Zincirlikuyu Vergi Dairesi\n"
    "Fatura Adresi (100000233): Esentepe Mah. Büyükdere Cad. Şişli/İstanbul\n"
    "E-Posta (100000234): oguz.karaguney@tatilbudur.com\n\n"
    "Geciken faturanın acilen kesilerek tarafımıza gönderilmesini talep ediyoruz.",
    "gonderen@example.com",
)
sirket_deger = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "SIRKET_ADI"), None)
check(
    "SikayetFatura-6 (CANLI HATA DUZELTMESI): cift satirli 'etiket yankisi' formati, sirket + 'adina' tuzagi",
    r["classification"] == "SIKAYET > FATURA > FATURA_TALEBI_SIKAYETLERI"
    and not r["missing_fields"]
    and sirket_deger is not None and sirket_deger.get("textValue") == "Tatilbudur Seyahat Acenteliği ve Turizm A.Ş.",
    (r["classification"], r["missing_fields"], r["attributes"]),
)

# "Bilgileri: Şahıs Adı: Değer" gibi, bir onceki alanin BASLIK kolonundan
# ("Güncel Fatura Bilgileri:") hemen sonra GERCEK bir yeni etiketin
# baslamasi -- etiket-yankisi tuzagina karsi eklenen "(?<!:)\s" korumasi bu
# mesru durumu da yanlislikla engelliyordu, duzeltildi.
r = cat(
    "",
    "Sayın İlgili, Ekte yer alan rezervasyon numaralı tatilimize ait faturanın tarafıma "
    "yanlış bilgilerle kesildiğini ve bu durumun düzeltilmesi için yaptığım başvuruların "
    "yanıtsız kaldığını/geciktirildiğini üzülerek müşahede etmekteyim. Yasal haklarım "
    "çerçevesinde, ekte yer alan fatura ünvanı yanlış olduğu için red veriyoruz. Onaylar "
    "mısınız? talebimi yineliyor; rezervasyon numaralı tatilin faturasını aşağıda "
    "belirttiğim şahıs bilgilerime göre acilen revize edip iletmenizi talep ediyorum. "
    "Aksi takdirde süreci yasal mercilere ve tüketici haklarına taşıyacağımı bilgilerinize "
    "sunarım. Güncel Fatura Bilgileri: Şahıs Adı: Bekir Oğuz Karagüney, TC Kimlik Numarası: "
    "63718240304, Fatura Adresi: Nişantaşı, İstanbul, E-Posta: "
    "karaguneyyoguz@gmail.com<mailto:karaguneyyoguz@gmail.com>. Gereğini rica ederim, iyi çalışmalar.",
    "gonderen@example.com",
)
sahis_deger = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "SAHIS_ADI"), None)
check(
    "SikayetFatura-7 (CANLI HATA DUZELTMESI): baslik satirindan hemen sonra gelen gercek 'Şahıs Adı:' etiketi, ':' oncesi metinden dolayi engellenmemeli",
    r["classification"] == "SIKAYET > FATURA > FATURA_TALEBI_SIKAYETLERI"
    and not r["missing_fields"]
    and sahis_deger is not None and sahis_deger.get("textValue") == "Bekir Oğuz Karagüney",
    (r["classification"], r["missing_fields"], r["attributes"]),
)

# "ünvanı yanlış olduğu için..." gibi duz cumlede "ünvan" kelimesi etiket
# degil cumlenin oznesi olarak geciyor; buyuk harfle baslama sarti olmadan
# regex bir sonraki virgule kadar TUM cumleyi yanlislikla sirket adi
# saniyordu (SikayetFatura-4 canli hatasi).
r = cat(
    "",
    "Fatura ünvanı yanlış girilmiş, düzeltilmesini rica ederim. Şirket Adı: "
    "Tatilbudur Seyahat Acenteliği ve Turizm A.Ş., Vergi Kimlik Numarası: "
    "8340123456, Vergi Dairesi: Zincirlikuyu Vergi Dairesi, Fatura Adresi: "
    "Esentepe Mah. İstanbul, E-Posta: oguz.karaguney@tatilbudur.com.",
    "gonderen@example.com",
)
sirket_deger2 = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "SIRKET_ADI"), None)
check(
    "SikayetFatura-8 (CANLI HATA DUZELTMESI): duz cumlede etiket-degil oznesi olan 'ünvanı' -> asiri genis yakalama olmamali",
    not r["missing_fields"]
    and sirket_deger2 is not None and sirket_deger2.get("textValue") == "Tatilbudur Seyahat Acenteliği ve Turizm A.Ş.",
    (r["missing_fields"], r["attributes"]),
)

# --- TC/VKN TUR TUTARLILIGI: Sahis -> SADECE TC, Sirket -> SADECE VKN ---
# Sahis Adi secilmisken metinde (yanlislikla/gereksiz) bir VKN de gecsse,
# VKN kullanilmamali; TC bulunamadigindan eksik alan olarak isaretlenmeli.
r = cat(
    "",
    f"Şahıs Adı: Bekir Oğuz Karagüney, Vergi Kimlik Numarası: {VALID_VKN}, "
    "Fatura Adresi: Nişantaşı, İstanbul, E-Posta: oguz.karaguney@tatilbudur.com.",
    "gonderen@example.com",
)
check(
    "TCVKN-Tutarlilik-1: Sahis secilince VKN yoksayilmali, TC eksik alan olarak gorunmeli",
    "TC Kimlik Numarası" in r["missing_fields"]
    and not any(a.get("attribute", {}).get("shortCode") == "VERGI_KIMLIK_NUMARASI" for a in r["attributes"]),
    (r["missing_fields"], r["attributes"]),
)

# Sirket Adi secilmisken metinde bir TC de gecsse, TC kullanilmamali; VKN
# bulunamadigindan eksik alan olarak isaretlenmeli.
r = cat(
    "",
    f"Şirket Adı: Tatilbudur Seyahat Acenteliği ve Turizm A.Ş., TC Kimlik Numarası: {VALID_TC}, "
    "Fatura Adresi: Nişantaşı, İstanbul, E-Posta: oguz.karaguney@tatilbudur.com.",
    "gonderen@example.com",
)
check(
    "TCVKN-Tutarlilik-2: Sirket secilince TC yoksayilmali, VKN eksik alan olarak gorunmeli",
    "Vergi Kimlik Numarası (VKN)" in r["missing_fields"]
    and not any(a.get("attribute", {}).get("shortCode") == "TC_KIMLIK_NUMARASI" for a in r["attributes"]),
    (r["missing_fields"], r["attributes"]),
)

# --- Etiketsiz, serbest cumlede gecen isim/unvan -- "X adına" kalibi ---
# Turkce klavyesi olmayan gonderenler noktasiz "ı" yerine duz ASCII "i"
# yazabiliyor ("Oguz Karaguney adina" gibi); her iki yazim da desteklenmeli.
r = cat(
    "",
    "Merhaba, Oguz Karaguney adina fatura kesilmesini rica ederim. TC Kimlik "
    f"Numaram {VALID_TC}. Adresim Bagdat Caddesi No:45 Kadikoy/Istanbul. Mail "
    "adresim oguz.karaguney@example.com.",
    "gonderen@example.com",
)
sahis_deger3 = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "SAHIS_ADI"), None)
check(
    "AdinaFallback-1: etiketsiz 'X adina' (ASCII i, noktasiz i degil) -> Sahis Adi olarak yakalanmali",
    not r["missing_fields"]
    and sahis_deger3 is not None and sahis_deger3.get("textValue") == "Oguz Karaguney",
    (r["missing_fields"], r["attributes"]),
)

# Sirket versiyonu, "adına" (dogru noktasiz ı) yazimiyla + adres alaninda
# ters sirali "X adresine ve Y mail adresine" kalibi bir arada.
r = cat(
    "",
    "İyi günler, kurumsal seyahatimiz için faturamızın hâlâ kesilmemiş olması "
    "iş süreçlerimizi aksatıyor ve bu durumdan şikayetçiyiz. Tatilbudur Seyahat "
    "Acenteliği ve Turizm A.Ş. adına, VKN 8340123456, Zincirlikuyu Vergi "
    "Dairesi, Esentepe Mah. Büyükdere Cad. Şişli/İstanbul adresine ve "
    "oguz.karaguney@tatilbudur.com mail adresine faturamızın acilen "
    "kesilmesini rica ederiz.",
    "gonderen@example.com",
)
sirket_deger3 = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "SIRKET_ADI"), None)
adres_deger3 = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "FATURA_ADRESI"), None)
check(
    "AdinaFallback-2 (CANLI HATA DUZELTMESI): etiketsiz sirket 'adına' + ters sirali 'X adresine ve Y mail adresine'",
    not r["missing_fields"]
    and sirket_deger3 is not None and sirket_deger3.get("textValue") == "Tatilbudur Seyahat Acenteliği ve Turizm A.Ş."
    and adres_deger3 is not None and adres_deger3.get("textValue") == "Esentepe Mah. Büyükdere Cad. Şişli/İstanbul",
    (r["missing_fields"], r["attributes"]),
)

# ==========================================================
# 4) FATURA_BILGI_DEGISIKLIGI (context + degisiklik/onay kelimesi birlikte)
# ==========================================================
r = cat("", "Vergi dairesi bilgim yanlış girilmiş, düzeltme rica ediyorum.")
check("FaturaDegisiklik-1: vergi dairesi + duzeltme", r["classification"] == "BILGI_ISTEK > FATURA > FATURA_BILGI_DEGISIKLIGI", r["classification"])

r = cat("", "Faturamda revize yapılmasını istiyorum, vergi kimlik no hatalı girilmiş.")
check("FaturaDegisiklik-2: fatura + revize + vergi kimlik no", r["classification"] == "BILGI_ISTEK > FATURA > FATURA_BILGI_DEGISIKLIGI", r["classification"])

# Ozel ifade dali: sadece "dogrusu bu sekildedir" / "bilgilere kesilmesi rica" -> context kelimesi
# (fatura/vergi vs.) OLMADAN da bu dala dusmeli.
r = cat("", "Doğrusu bu şekildedir, lütfen bu bilgilere göre işlem yapınız.")
check(
    "FaturaDegisiklik-3: ozel ifade (context kelimesi yok)",
    r["classification"] == "BILGI_ISTEK > FATURA > FATURA_BILGI_DEGISIKLIGI",
    r["classification"],
)

# --- Kullanicinin onayladigi senaryo (kirilim.md gozden gecirme sureci) ---
# "revize ettirmem gerekiyordu" -> zaten kesilmis ama yanlis olan bir faturanin
# duzeltilmesi talebi; Misafir Faturasi'ndan farkli olarak INVOICE_MODIFICATION dalina dusuyor.
r = cat(
    "",
    "Merhaba, ekte yer alan rezervasyon numaralı tatilimize ait faturanın şahıs bilgilerim "
    "yerine yanlış unvanla kesildiğini fark ettim. Bu faturayı kendi şahıs bilgilerime göre "
    "revize ettirmem gerekiyordu; fakat süreçle ilgili bilgi alabilir miyim? Eğer uygunsa "
    "faturayı aşağıdaki güncel bilgilerime göre revize edip iletmeniz mümkün müdür?\n\n"
    "Güncel Fatura Bilgileri:\nŞahıs Adı: Bekir Oğuz Karagüney,\nTC Kimlik Numarası: 63718240304,\n"
    "Fatura Adresi: Nişantaşı, İstanbul,\nE-Posta: karaguneyyoguz@gmail.com.\n\n"
    "Destekleriniz için şimdiden teşekkür eder, iyi çalışmalar dilerim.",
    "gonderen@example.com",
)
check(
    "FaturaDegisiklik-4 (ONAYLI): mevcut faturayi revize etme talebi",
    r["classification"] == "BILGI_ISTEK > FATURA > FATURA_BILGI_DEGISIKLIGI" and not r["missing_fields"],
    (r["classification"], r["missing_fields"]),
)

# ==========================================================
# 5) MISAFIR_FATURASI (sadece fatura kelimesi, sikayet/degisiklik yok)
# ==========================================================
r = cat(
    "",
    f"Fatura kesilmesini istiyorum.\nŞahıs Adı: Mehmet Demir\nTC: {VALID_TC}\nFatura Adresi: Bağdat Cad. No:12 Kadıköy Istanbul\n",
)
check(
    "MisafirFatura-1: tum bilgiler tam -> eksik alan yok",
    r["classification"] == "BILGI_ISTEK > FATURA > MISAFIR_FATURASI" and not r["missing_fields"],
    (r["classification"], r["missing_fields"]),
)

r = cat("", "Fatura kesilmesini istiyorum ama bilgilerimi yazmayı unuttum.")
check(
    "MisafirFatura-2: bilgiler eksik -> missing_fields dolu",
    r["classification"] == "BILGI_ISTEK > FATURA > MISAFIR_FATURASI" and len(r["missing_fields"]) > 0,
    (r["classification"], r["missing_fields"]),
)

r = cat(
    "",
    "Fatura talebim var.\nŞahıs Adı: [Buraya yazınız]\nTC: 12345678901\nFatura Adresi: [Buraya yazınız]\n",
)
check(
    "MisafirFatura-3: placeholder deger + gecersiz TC -> eksik alan",
    r["classification"] == "BILGI_ISTEK > FATURA > MISAFIR_FATURASI" and len(r["missing_fields"]) >= 2,
    (r["classification"], r["missing_fields"]),
)

r = cat(
    "",
    f"Şirket adına fatura istiyorum.\nŞirket Adı: ACME Turizm Ltd.\nVKN: {VALID_VKN}\nVergi Dairesi: Kadıköy\nFatura Adresi: Moda Cad. No:3 Istanbul\n",
)
check(
    "MisafirFatura-4: sirket adi + gecerli VKN -> eksik alan yok",
    r["classification"] == "BILGI_ISTEK > FATURA > MISAFIR_FATURASI" and not r["missing_fields"],
    (r["classification"], r["missing_fields"]),
)

# --- Kullanicinin onayladigi senaryo (kirilim.md gozden gecirme sureci) ---
# "revize" kelimesi GECMIYOR -> ilk kez fatura talebi, FATURA_BILGI_DEGISIKLIGI'nden
# ayrisan asil Misafir Faturasi senaryosu.
r = cat(
    "",
    "Merhaba, tamamlamış olduğumuz tatilimiz için henüz tarafımıza herhangi bir fatura "
    "kesilmediğini fark ettik. Konaklama bedelimiz için ilk kez resmi fatura kesilmesini "
    "rica ediyoruz. Faturanın aşağıdaki şahıs bilgilerime göre düzenlenerek tarafıma "
    "iletilmesini talep ediyorum.\n\nFatura Bilgileri:\nŞahıs Adı: Bekir Oğuz Karagüney,\n"
    "TC Kimlik Numarası: 63718240304,\nFatura Adresi: Nişantaşı, İstanbul,\n"
    "E-Posta: karaguneyyoguz@gmail.com.\n\nİyi çalışmalar dilerim.",
    "gonderen@example.com",
)
check(
    "MisafirFatura-5 (ONAYLI): ilk kez fatura talebi",
    r["classification"] == "BILGI_ISTEK > FATURA > MISAFIR_FATURASI" and not r["missing_fields"],
    (r["classification"], r["missing_fields"]),
)

# ==========================================================
# 6) ONLINE ISLEMLER > UYELIK SURECLERI
# ==========================================================
r = cat("", "Web sayfasından üyeliğimin olduğunu fakat giriş yapamadığımı belirtmek isterim.")
check("Online-1: web sayfa + giris yapamiyorum", r["classification"] == "BILGI_ISTEK > ONLINE_ISLEMLER > UYELIK_SURECLERI", r["classification"])

r = cat("", "Mobil uygulamada rezervasyonlarım kısmında görünmüyor, nedenini öğrenebilir miyim?")
check("Online-2: mobil uygulama + rezervasyon gorunmuyor", r["classification"] == "BILGI_ISTEK > ONLINE_ISLEMLER > UYELIK_SURECLERI", r["classification"])

# --- Kullanicinin onayladigi senaryolar (kirilim.md gozden gecirme sureci) ---
r = cat("", "Merhaba, Tatilbudur.com web siteniz üzerinden mevcut üyeliğime giriş yaptım. Profilimdeki kayıtlı telefon numaramı değiştirmek istiyorum fakat sistem hata veriyor ve kaydetmiyor. Web siteniz üzerinden profil bilgilerimi nasıl güncelleyebilirim veya sistemdeki numaramı 05321112233 olarak güncelleyebilir misiniz?\n\nÜyelik E-Posta: karaguneyyoguz@gmail.com\nDesteklerinizi rica ederim.")
check("Online-3 (ONAYLI): web sitesi profil guncelleme sorunu", r["classification"] == "BILGI_ISTEK > ONLINE_ISLEMLER > UYELIK_SURECLERI", r["classification"])

r = cat("", "İyi günler, TatilBudur mobil uygulamasını telefonuma indirdim ve yeni üyelik oluşturmaya çalışıyorum. Ancak üye ol butonuna bastıktan sonra telefonuma SMS doğrulama kodu bir türlü ulaşmıyor. Uygulama üzerinden üyeliğimi nasıl tamamlayabilirim, yardımcı olabilir misiniz?\n\nMobil GSM: 05321112233\nE-Posta: karaguneyyoguz@gmail.com")
check("Online-4 (ONAYLI): mobil uygulama SMS dogrulama sorunu", r["classification"] == "BILGI_ISTEK > ONLINE_ISLEMLER > UYELIK_SURECLERI", r["classification"])

# ==========================================================
# 6b) ULASIM > BILET
# ==========================================================
r = cat("", "Biletim gelmedi, e-bilet ulaşmadı bana.")
check("Bilet-1: biletim gelmedi + e-bilet ulasmadi", r["classification"] == "BILGI_ISTEK > ULASIM > BILET", r["classification"])

# --- Kullanicinin onayladigi gercek CSM ornekleri (kirilim.md gozden gecirme sureci) ---
r = cat("", "Belirttiğim misafirlerimizin uçuş kodu ve saatlerinin teyidini rica ederiz.")
check("Bilet-2 (ONAYLI): ucus kodu/saat teyidi", r["classification"] == "BILGI_ISTEK > ULASIM > BILET", r["classification"])

r = cat("", "Ayrıca eğer Buse Sekmen olarak güncelleme yapılmışsa sorun yok demektir. Qatar hava yolları geliş biletimizi güncelledi. Ama dönüş hakkımda bilgi sahibi değiliz.")
check("Bilet-3 (ONAYLI): havayolu bilet guncellemesi", r["classification"] == "BILGI_ISTEK > ULASIM > BILET", r["classification"])

r = cat("", "Önümüzdeki hafta için tur fiyatlandırması ve uçak bileti detaylarını öğrenebilir miyim?")
check("Bilet-4 (ONAYLI): ucak bileti detay talebi", r["classification"] == "BILGI_ISTEK > ULASIM > BILET", r["classification"])

r = cat("", "Merhaba, Biletler rezervasyona manuel eklenmiştir, kontrolünüz ricadır.")
check("Bilet-5 (ONAYLI): bilet manuel eklendi bildirimi", r["classification"] == "BILGI_ISTEK > ULASIM > BILET", r["classification"])

# --- Kullanicinin verdigi "nokta atisi" oncelik senaryolari (ONAYLI) ---
r = cat("", "Merhaba, geçtiğimiz günlerde satın aldığım ulaşım biletine ait e-bilet PDF dosyasını ve PNR detaylarını sistemde bulamıyorum. Bilet bilgilerimin mail adresime tekrar gönderilmesini rica ediyorum, iyi çalışmalar.")
check("Bilet-6 (ONAYLI): e-bilet PDF + PNR detaylari", r["classification"] == "BILGI_ISTEK > ULASIM > BILET", r["classification"])

r = cat("", "İyi günler, elimdeki rezervasyon/bilet için ileri bir tarihe değişiklik yapma hakkımın olup olmadığını öğrenmek istiyorum. Eğer varsa yansıyacak ceza veya fiyat farkı tutarları hakkında bilgi talep ediyorum.")
check("DegisiklikHakki-4 (ONAYLI): degisiklik hakki + ceza", r["classification"] == "BILGI_ISTEK > ULASIM > DEGISIKLIK_HAKKI_SORGULAMA", r["classification"])

r = cat("", "Merhaba, satın almış olduğum otobüs ulaşım hizmeti için kalkış peronu numarasını ve koltuk detaylarımı öğrenmek istiyorum. Otobüs seferi saatinde bir değişiklik var mı acaba? Bilgi rica ederim.")
check("Otobus-4 (ONAYLI): peron + koltuk + otobus seferi", r["classification"] == "BILGI_ISTEK > ULASIM > OTOBUS", r["classification"])

# --- COZULMEMIS: "ucus dahil tur bilgilendirmesi" tarzi duyuru mailleri (bilet/ucus
# kelimesi gecmiyor, "Ucakli ... Turu" gibi dolayli ifade var) henuz yakalanmiyor.
r = cat("", "23.01.2026 Hareketli Sömestir Özel İzmir Çıkışlı Uçaklı Mardin Urfa Göbeklitepe Gaziantep Turu / 2 Gece Otel Konaklaması Tur Bilgilendirmesi bilginize sunulmuştur. Misafirlerin bilgilendirilmesini rica ederim.")
check(
    "COLLISION-6 (KNOWN ISSUE): 'Ucakli ... Tur Bilgilendirmesi' -> beklenen BILET ama TESIS_ILETISIM'e dusuyor",
    r["classification"] == "BILGI_ISTEK > ULASIM > BILET",
    r["classification"],
)

# ==========================================================
# 6c) SIKAYET > EVRAK > EVRAK
# kirilim.md ile dogrulandiktan sonra düzeltildi: bu kirilim FATURA kategorisi
# altinda degil, ayri bir EVRAK kategorisi altinda yer aliyor (bkz. bolum 11).
# ==========================================================
r = cat("", "Faturamın evrağında belge eksik var, şikayetçiyim.")
check("EvrakSikayet-1: belge eksik -> EVRAK kategorisi", r["classification"] == "SIKAYET > EVRAK > EVRAK", r["classification"])

# ==========================================================
# 6d) BACKOFFICE ISLEMLERI (Odeme / Konfirme / Degisiklik / Iptal / Ek Hizmet / Kaydirma / Diger)
# Bu blok config.py'de tanimli olup daha once koda hic baglanmamis 20+ alt kirilimi kapsar.
# ==========================================================
r = cat("", "Ödeme yansımadı, hesabımdan para çekildi.")
check("Odeme-1: odemenin yansimamasi", r["classification"] == "BACKOFFICE_ISLEMLERI > ODEME > ODEMENIN_YANSIMAMASI", r["classification"])

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# "tutar sisteminize yansimadi" / "odeme cekilmesine ragmen" gibi dogal
# ifadeler eski dar kelime listesiyle hic yakalanamiyordu. Ayrica musteri
# onayiyla bu kirilimda 5 odeme alani (Islem Tarihi, Kart Ilk 6/Son 4,
# Tutar, Siparis No) artik ZORUNLU.
r = cat(
    "",
    "Merhaba,\nGerçekleştirdiğim rezervasyon için kartımdan ödeme çekilmesine "
    "rağmen tutar sisteminize yansımadı ve rezervasyonum onay bekliyor "
    "durumunda kaldı. İşleme ait detaylar şu şekildedir:\n"
    "İşlem Tarihi : 22.08.2026\nKartın İlk 6 Rakamı : 454360\n"
    "Kartın Son 4 Rakamı :1234\nTutar : 12.500 TL\nSipariş No : 358109758\n"
    "Ödememin kontrol edilerek rezervasyonumun konfirme edilmesini rica "
    "ederim. İyi çalışmalar.",
)
check(
    "Odeme-2 (CANLI HATA DUZELTMESI): dogal ifade + tum zorunlu alanlar dolu",
    r["classification"] == "BACKOFFICE_ISLEMLERI > ODEME > ODEMENIN_YANSIMAMASI" and not r["missing_fields"] and len(r["attributes"]) == 5,
    (r["classification"], r["missing_fields"], r["attributes"]),
)

r = cat("", "Merhaba, kartımdan ödeme çekilmesine rağmen tutar sisteminize yansımadı. Kontrol eder misiniz?")
check(
    "Odeme-3 (ZORUNLU ALAN KONTROLU): detay verilmezse tum alanlar eksik sayilmali",
    r["classification"] == "BACKOFFICE_ISLEMLERI > ODEME > ODEMENIN_YANSIMAMASI" and len(r["missing_fields"]) == 5,
    (r["classification"], r["missing_fields"]),
)

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# Siparis numarasi etiketten ONCE de gelebiliyor: "358109758 numaralı
# siparişim için..." -- eski regex sadece "Siparis No: X" sirasini destekliyordu.
r = cat(
    "",
    "İyi günler, bugün (22.08.2026 tarihinde) 358109758 numaralı siparişim "
    "için 454360 ile başlayıp 1234 ile biten kartımla 12.500 TL tutarında "
    "çekim yapmama rağmen bu ödeme sisteminize yansımadı. Dekontum elimde "
    "mevcut, ödememin kontrol edilerek işlemimin tamamlanması hususunda "
    "yardımlarınızı rica ederim.",
)
check(
    "Odeme-4 (CANLI HATA DUZELTMESI): 'X numarali siparisim' ters sirali format",
    r["classification"] == "BACKOFFICE_ISLEMLERI > ODEME > ODEMENIN_YANSIMAMASI" and not r["missing_fields"] and len(r["attributes"]) == 5,
    (r["classification"], r["missing_fields"], r["attributes"]),
)

r = cat("", "Konfirme maili hala gelmedi, rezervasyon onayı gelmedi.")
check("Konfirme-1", r["classification"] == "BACKOFFICE_ISLEMLERI > KONFIRME > KONFIRME", r["classification"])

# CONFIRMATION_ACTIONABLE_EVENT_KEYWORDS eski hali sadece "gelmedi/ulasmadi/
# hala/acil laz" iceriyordu (yalnizca "konfirme gecikmesi" sikayetlerini
# kapsiyordu); "konfirme etmenizi rica ederiz" gibi TALEP ifadeleri eksikti
# (kullanici tarafindan bildirildi). Ayrica bare "sure" kelimesi (bilgi-istek
# dalinda) "sürecinin" gibi kelimelerde de gectigi icin somut talep icerikli
# mailleri yanlislikla BILGI_ISTEK > REZERVASYON > KONFIRME dalina cekiyordu.
r = cat(
    "",
    "İyi günler, 358109758 numaralı rezervasyonumuzun otel tarafındaki "
    "konfirme ve kesinleşme sürecinin tamamlanarak tarafımıza resmi onay "
    "bilgisinin iletilmesini rica eder, iyi çalışmalar dilerim.",
)
check(
    "Konfirme-2 (ONAYLI): 'konfirme ve kesinleşme süreci' + 'onay bilgisinin iletilmesi' -> 'sure' yanlis eslesmesine ragmen Backoffice onceliklenmeli",
    r["classification"] == "BACKOFFICE_ISLEMLERI > KONFIRME > KONFIRME",
    r["classification"],
)

r = cat("", "Rezervasyonumuzu konfirme etmenizi rica ederiz.")
check("Konfirme-3: 'konfirme etmenizi rica'", r["classification"] == "BACKOFFICE_ISLEMLERI > KONFIRME > KONFIRME", r["classification"])

r = cat("", "Otel onayının tamamlanmasını rica ederiz.")
check("Konfirme-4: 'otel onayının tamamlanması' (yeni topic kelimesi 'otel onayi')", r["classification"] == "BACKOFFICE_ISLEMLERI > KONFIRME > KONFIRME", r["classification"])

r = cat("", "Rezervasyonumuz kesinleşti mi, bilgi verir misiniz?")
check("Konfirme-5: 'kesinleşti mi' (yeni topic kelimesi 'kesinles')", r["classification"] == "BACKOFFICE_ISLEMLERI > KONFIRME > KONFIRME", r["classification"])

# Koruma: saf tanimsal soru ("konfirme nedir") hala BILGI_ISTEK > REZERVASYON >
# KONFIRME'de kalmali, genisletilen event listesi bunu yanlislikla yakalamamali
# (COLLISION-5 ile ayni mantik).
r = cat("", "Konfirme nedir, açıklar mısınız?")
check(
    "Konfirme-6 (KORUMA): saf tanimsal 'konfirme nedir' sorusu Backoffice'e degil Bilgi-Istek'e dusmeli",
    r["classification"] == "BILGI_ISTEK > REZERVASYON > KONFIRME",
    r["classification"],
)

r = cat("", "Ödeme tipi değişikliği yapmak istiyorum.")
check("Degisiklik-OdemeTipi", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ODEME_TIPI_DEGISIKLIGI", r["classification"])

r = cat("", "Doğum tarihi değişikliği yapmam gerekiyor.")
check("Degisiklik-DogumTarihi", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DOGUM_TARIHI_DEGISIKLIGI", r["classification"])

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# "guncellenmesini rica eder" ifadesi CHANGE_INTENT_KEYWORDS listesinde yoktu
# (sadece "duzelt"/"degistir" vardi), bu yuzden bu mail varsayilan Tesis
# Iletisim'e dusuyordu (gercek CSM ticket'inda gozlemlendi).
r = cat(
    "",
    "İyi günler, 358109758 nolu rezervasyonumuzda yolcu olarak bulunan Bekir "
    "Oğuz Karagüney isimli misafirin doğum tarihi sistemde hatalı (19.06.1993) "
    "görünmektedir. Doğru doğum tarihinin 19.06.1994 olarak güncellenmesini "
    "rica eder, iyi çalışmalar dilerim.",
)
check(
    "Degisiklik-DogumTarihi-2 (CANLI HATA DUZELTMESI): 'guncellenmesini rica eder'",
    r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DOGUM_TARIHI_DEGISIKLIGI",
    r["classification"],
)

r = cat("", "Ek hizmet eklemek istiyorum rezervasyonuma.")
check("Degisiklik-EkHizmetler", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > EK_HIZMETLER", r["classification"])

r = cat("", "İsim değişikliği yapmak istiyorum.")
check("Degisiklik-Isim", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ISIM_DEGISIKLIGI", r["classification"])

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# "adında harf hatası" / "adının güncellenmesi" ifadeleri "isim" kelimesini
# hic kullanmiyor, eski konu listesi bunu yakalayamiyordu.
r = cat(
    "",
    "İyi günler, 358109758 numaralı rezervasyonumuzda yolcu olarak kayıtlı "
    "bulunan misafirin adında harf hatası yapıldığını fark ettik. İlgili "
    "kişinin adının doğru şekilde güncellenerek düzeltilmesini rica eder, "
    "iyi çalışmalar dilerim.",
)
check(
    "Degisiklik-Isim-2 (CANLI HATA DUZELTMESI): 'adinda harf hatasi'",
    r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ISIM_DEGISIKLIGI",
    r["classification"],
)

r = cat("", "Kişi eklemek istiyorum rezervasyona.")
check("Degisiklik-KisiEkleCikar", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > KISI_EKLEME_CIKARMA", r["classification"])

r = cat("", "Rezervasyonuma not eklemek istiyorum.")
check("Degisiklik-NotEkleme", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > NOT_EKLEME_TALEBI", r["classification"])

r = cat("", "Oda tipi değişikliği yapmak istiyorum.")
check("Degisiklik-OdaTipi", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ODA_TIPI_DEGISIKLIGI", r["classification"])

r = cat("", "Oda değişikliği istiyorum, farklı bir oda istiyorum.")
check("Degisiklik-Oda", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ODA", r["classification"])

r = cat("", "Otel değişikliği istiyorum, başka otele geçmek istiyorum.")
check("Degisiklik-Otel", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > OTEL_DEGISIKLIGI", r["classification"])

# HOTEL_CHANGE_TOPIC_KEYWORDS eski hali tumu "otel" koklu kalip ifadelerdi;
# "tesis degistirme talebi" / "farkli bir tesise aktarma" gibi "tesis" koklu
# ifadeler eksikti (kullanici tarafindan bildirildi). FACILITY_CHANGE_TOPIC_KEYWORDS
# ("tesis") bilgi-istek ile karismamasi icin CHANGE_INTENT_KEYWORDS/"aktar"
# ile ESLESTIRILEREK eklendi (tek basina tetiklenmiyor).
r = cat(
    "",
    "İyi günler, 358109758 numaralı rezervasyonumuzda yer alan otelimizi "
    "değiştirerek tatilimize başka bir tesiste devam etmek istiyoruz. Otel "
    "değişikliği için aradaki fiyat farkı ve müsaitlik durumunun incelenerek "
    "backoffice tarafında gerekli güncellemelerin yapılmasını rica eder, iyi "
    "çalışmalar dilerim.",
)
check(
    "Degisiklik-Otel-2 (ONAYLI): otelimizi degistirerek baska tesiste devam etme talebi",
    r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > OTEL_DEGISIKLIGI",
    r["classification"],
)

r = cat("", "Tesis değiştirme talebimiz var.")
check(
    "Degisiklik-Otel-3: 'tesis degistirme talebi' (FACILITY_CHANGE_TOPIC_KEYWORDS + CHANGE_INTENT)",
    r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > OTEL_DEGISIKLIGI",
    r["classification"],
)

r = cat("", "Otel rezervasyonumuzu farklı bir tesise aktarmak istiyoruz.")
check(
    "Degisiklik-Otel-4: 'tesise aktarma' (FACILITY_CHANGE_TOPIC_KEYWORDS + 'aktar')",
    r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > OTEL_DEGISIKLIGI",
    r["classification"],
)

# Koruma: sadece "tesis" gecen SAF bilgi-istek (degistirme niyeti yok)
# yanlislikla OTEL_DEGISIKLIGI'ne dusmemeli.
r = cat("", "Tesisin iletişim numarasını öğrenebilir miyim?")
check(
    "Degisiklik-Otel-5 (KORUMA): sadece 'tesis' bilgi-istegi, degistirme niyeti yok -> OTEL_DEGISIKLIGI'ne dusmemeli",
    r["classification"] != "BACKOFFICE_ISLEMLERI > DEGISIKLIK > OTEL_DEGISIKLIGI",
    r["classification"],
)

r = cat("", "Rezervasyon tarihini değiştirmek istiyorum.")
check("Degisiklik-Tarih", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TARIH_DEGISIKLIGI", r["classification"])

r = cat("", "Tur değişikliği istiyorum, başka tura geçmek istiyorum.")
check("Degisiklik-Tur", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TUR_DEGISIKLIGI", r["classification"])

# TOUR_CHANGE_TOPIC_KEYWORDS eski hali sadece "tur degisikligi/baska tura/
# baska bir tura/turu yerine" gibi zaten degisim-niyeti icine gomulu kalip
# ifadeleri kapsiyordu; "tur paketini degistirmek" / "tur rotasi secmek" gibi
# genel "tur paketi/rotasi/programi" + degistir/sec fiili kombinasyonlari
# eksikti (kullanici tarafindan bildirildi). TOUR_PACKAGE_TOPIC_KEYWORDS bu
# yuzden BILGI-ISTEK ile karismamasi icin CHANGE_INTENT_KEYWORDS/"sec" ile
# ESLESTIRILEREK eklendi (tek basina tetiklenmiyor).
r = cat(
    "",
    "İyi günler, 358109758 numaralı rezervasyonumuzla satın almış olduğumuz "
    "mevcut tur paketini iptal etmeden, tarihlerimize uygun farklı bir rota "
    "olan başka bir tur programıyla değiştirmek istiyoruz. Tur değişikliği "
    "için fiyat farkı ve müsaitlik durumunun kontrol edilerek backoffice "
    "işlemlerimizin başlatılmasını rica eder, iyi çalışmalar dilerim.",
)
check(
    "Degisiklik-Tur-2 (ONAYLI): tur paketini iptal etmeden baska bir tur programiyla degistirme talebi",
    r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TUR_DEGISIKLIGI",
    r["classification"],
)

r = cat("", "Tur paketini değiştirmek istiyorum, farklı bir rota var mı?")
check(
    "Degisiklik-Tur-3: 'tur paketini degistirmek' (TOUR_PACKAGE_TOPIC_KEYWORDS + CHANGE_INTENT)",
    r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TUR_DEGISIKLIGI",
    r["classification"],
)

r = cat("", "Farklı bir tur rotası seçmek istiyoruz, yardımcı olur musunuz?")
check(
    "Degisiklik-Tur-4: 'tur rotasi secmek' (TOUR_PACKAGE_TOPIC_KEYWORDS + 'sec')",
    r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TUR_DEGISIKLIGI",
    r["classification"],
)

# Koruma: sadece "tur paketi" gecen SAF bilgi-istek (degistirme niyeti yok)
# yanlislikla TUR_DEGISIKLIGI'ne dusmemeli -- TOUR_PACKAGE_TOPIC_KEYWORDS
# bilerek CHANGE_INTENT_KEYWORDS/"sec" ile eslestirilmeden tek basina
# tetiklenmiyor.
r = cat("", "Tur paketi hakkında bilgi almak istiyorum, içeriği nedir?")
check(
    "Degisiklik-Tur-5 (KORUMA): sadece 'tur paketi' bilgi-istegi, degistirme niyeti yok -> TUR_DEGISIKLIGI'ne dusmemeli",
    r["classification"] != "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TUR_DEGISIKLIGI",
    r["classification"],
)

r = cat("", "Ulaşım değişikliği istiyorum, ulaşım tipimi değiştirmek istiyorum.")
check("Degisiklik-Ulasim", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DEGISIKLIK_ULASIM", r["classification"])

r = cat("", "Odamı iptal etmek istiyorum.")
check("Iptal-Oda", r["classification"] == "BACKOFFICE_ISLEMLERI > IPTAL > ODA_IPTALI", r["classification"])

r = cat("", "İptal sigortası iptal etmek istiyorum.")
check("EkHizmet-IptalSigortasi", r["classification"] == "BACKOFFICE_ISLEMLERI > EK_HIZMET > IPTAL_SIGORTASI", r["classification"])

r = cat("", "Rezervasyonumu iptal etmek istiyorum, genel iptal talebi oluşturuyorum.")
check("Iptal-Talebi", r["classification"] == "BACKOFFICE_ISLEMLERI > IPTAL > IPTAL_TALEBI", r["classification"])

# CANCEL_INTENT_KEYWORDS eski hali "iptal etmek/ettirmek/edebilir/edelim/
# ediyoruz/talebi" ile siniirliydi; "iptal EDILMESINI talep ediyoruz" gibi
# EDILGEN (passive) yapida somut bir iptal talebi, hicbirini eslesmedigi icin
# BILGI_ISTEK > REZERVASYON > IPTAL_SUREC_BILGISI dalina (metindeki "iptal
# sartlari" ifadesindeki "sart" kelimesi uzerinden) yanlislikla dusuyordu
# (kullanici tarafindan bildirildi).
r = cat(
    "",
    "İyi günler, planlarımızda meydana gelen ani değişiklik nedeniyle 358109758 "
    "numaralı tatil rezervasyonumuzun tamamen iptal edilmesini talep ediyoruz. "
    "İptal şartları doğrultusunda varsa kesintiler düşülerek kalan tutarın iade "
    "sürecinin başlatılması hususunda yardımlarınızı rica eder, iyi çalışmalar dilerim.",
)
check(
    "Iptal-Talebi-2 (ONAYLI): edilgen 'iptal edilmesini talep ediyoruz' + metinde 'sart'/'surec' kelimeleri de gecse somut talep onceliklenmeli",
    r["classification"] == "BACKOFFICE_ISLEMLERI > IPTAL > IPTAL_TALEBI",
    r["classification"],
)

r = cat("", "Rezervasyonumun iptalini rica ediyorum.")
check(
    "Iptal-Talebi-3: 'iptalini rica ediyorum' (isim+rica kalibi)",
    r["classification"] == "BACKOFFICE_ISLEMLERI > IPTAL > IPTAL_TALEBI",
    r["classification"],
)

r = cat("", "İptal işlemi için yardımcı olur musunuz?")
check(
    "Iptal-Talebi-4: bare 'iptal islemi'",
    r["classification"] == "BACKOFFICE_ISLEMLERI > IPTAL > IPTAL_TALEBI",
    r["classification"],
)

# --- Backoffice > Degisiklik > Diger (coplukutusu/joker kirilim) ---
# Tarih/oda/isim/dogum tarihi/odeme tipi/otel/tur/ulasim gibi SPESIFIK
# degisiklik dallarinin hicbirine uymayan ama genel bir degisiklik/revizyon
# niyeti tasiyan mailler icin. Bilerek fonksiyonun EN SONUNA (varsayilan
# TESIS_ILETISIM'den hemen once) yerlestirildi -- daha erken konursa,
# "degisiklik" kelimesinin sadece baglamsal gectigi ama asil niyeti
# IPTAL_TALEBI olan ya da soru formundaki (DEGISIKLIK_BILGI_TALEBI) mailleri
# yanlislikla once yakaliyordu (bu oturumda denendi, geri alindi).
r = cat(
    "",
    "İyi günler, 358109758 numaralı rezervasyonumuzla ilgili sistemde standart "
    "kategoriye girmeyen ancak yapılmasını istediğimiz bazı özel değişiklikler "
    "ve revizyon taleplerimiz bulunmaktadır. Bu istisnai durumun incelenerek "
    "backoffice tarafında gerekli düzenlemelerin yapılmasını rica eder, iyi "
    "çalışmalar dilerim.",
)
check(
    "Degisiklik-Diger-1 (ONAYLI): standart alt kategorilere uymayan genel degisiklik/revizyon talebi",
    r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DIGER",
    r["classification"],
)

r = cat("", "Rezervasyonumda revizyon yapılmasını istiyoruz.")
check(
    "Degisiklik-Diger-2: 'revizyon' kelimesi (CHANGE_INTENT_KEYWORDS'e eklendi)",
    r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DIGER",
    r["classification"],
)

# Onceki iki regresyon: DIGER dalinin CANCEL_INTENT ve soru-formu Bilgi-Istek
# dallarindan ONCE gelmemesi gerektigini dogrulayan koruma testleri.
r = cat(
    "",
    "İyi günler, planlarımızda meydana gelen ani değişiklik nedeniyle "
    "358109758 numaralı tatil rezervasyonumuzun tamamen iptal edilmesini "
    "talep ediyoruz. İptal şartları doğrultusunda varsa kesintiler düşülerek "
    "kalan tutarın iade sürecinin başlatılması hususunda yardımlarınızı rica "
    "eder, iyi çalışmalar dilerim.",
)
check(
    "Degisiklik-Diger-3 (KORUMA): metinde baglamsal 'degisiklik' gecse bile IPTAL_TALEBI oncelikli olmali",
    r["classification"] == "BACKOFFICE_ISLEMLERI > IPTAL > IPTAL_TALEBI",
    r["classification"],
)

r = cat("", "Rezervasyonumda değişiklik yapabilir miyim.")
check(
    "Degisiklik-Diger-4 (KORUMA): soru formundaki 'degisiklik yapabilir miyim' DEGISIKLIK_BILGI_TALEBI'ne dusmeli, DIGER'e degil",
    r["classification"] == "BILGI_ISTEK > REZERVASYON > DEGISIKLIK_BILGI_TALEBI",
    r["classification"],
)

r = cat("", "Otel kaynaklı kaydırma yapıldığını öğrendim, bilgi istiyorum.")
check("Kaydirma-OtelKaynakli", r["classification"] == "BACKOFFICE_ISLEMLERI > KAYDIRMA > OTEL_KAYNAKLI", r["classification"])

r = cat("", "Operasyon kaynaklı kaydırma nedeniyle bilgi istiyorum.")
check("Kaydirma-OperasyonKaynakli", r["classification"] == "BACKOFFICE_ISLEMLERI > KAYDIRMA > OPERASYON_KAYNAKLI", r["classification"])

r = cat("", "Eksik ödemeyi tamamlamak istiyorum, bakiye ödemesi yapmak istiyorum.")
check("DigerIslemler-OdemeTamamlama", r["classification"] == "BACKOFFICE_ISLEMLERI > DIGER_ISLEMLER > ODEME_TAMAMLAMA", r["classification"])

# --- BILINEN CAKISMA (KOLLIZYON) DURUMLARI - once tespit, sonra birlikte cozulecek ---
# "bilet" kelimesi TRANSPORT_CHANGE_RIGHTS_KEYWORDS listesinde COK GENEL bir sinyal
# oldugu icin, "ucak bileti" ile ilgili degisiklik/iptal talepleri hicbir zaman kendi
# ozel dallarina ulasamiyor; her zaman ULASIM > DEGISIKLIK_HAKKI_SORGULAMA dalina
# takiliyor (cunku o kontrol kodda cok daha erken calisiyor).
r = cat("", "Uçak bileti değişikliği istiyorum.")
check(
    "COLLISION-1: 'ucak bileti degisikligi' -> beklenen UCAK_BILETI_DEGISIKLIGI ama 'bilet' kelimesi ULASIM dalina cekiyor",
    r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > UCAK_BILETI_DEGISIKLIGI",
    r["classification"],
)

r = cat("", "Uçak biletimi iptal etmek istiyorum.")
check(
    "COLLISION-2: 'ucak biletimi iptal' -> beklenen UCAK_BILETI_IPTALI ama 'bilet' kelimesi ULASIM dalina cekiyor",
    r["classification"] == "BACKOFFICE_ISLEMLERI > IPTAL > UCAK_BILETI_IPTALI",
    r["classification"],
)

# ONLINE_PROCESS_KEYWORDS listesindeki "rezervasyon gorun" ifadesi cok genis oldugu
# icin, odeme yansimama sikayetlerinde "rezervasyon gorunmuyor" ifadesi gecerse
# mail yanlislikla ONLINE_ISLEMLER > UYELIK_SURECLERI dalina dusuyor.
r = cat("", "Ödemem yansımadı, hesabımdan para çekildi ama rezervasyon görünmüyor.")
check(
    "COLLISION-3: odeme yansimama + 'rezervasyon gorunmuyor' -> beklenen ODEMENIN_YANSIMAMASI ama ONLINE dalina dusuyor",
    r["classification"] == "BACKOFFICE_ISLEMLERI > ODEME > ODEMENIN_YANSIMAMASI",
    r["classification"],
)

# ==========================================================
# 7) ACENTE > ILETISIM BILGILERI
# ==========================================================
r = cat("", "Acenta başvurusunda bulunmak istemiştim, yönlendirilmemi rica ederim.")
check("Acente-1: acenta basvuru + yonlendir", r["classification"] == "BILGI_ISTEK > ACENTE > ILETISIM_BILGILERI", r["classification"])

r = cat("", "Acenteye telefon numarasından ulaşamıyorum, iletişim bilgilerini paylaşır mısınız?")
check("Acente-2: acenteye + telefon + iletisim", r["classification"] == "BILGI_ISTEK > ACENTE > ILETISIM_BILGILERI", r["classification"])

# --- Kullanicinin onayladigi senaryolar (kirilim.md gozden gecirme sureci) ---
r = cat("", "Merhaba, operasyonel işlemlerimiz için X acentenin güncel iletişim bilgilerini, yetkili e-posta adresini ve telefon numarasını talep ediyorum. Yardımcı olabilir misiniz?")
check("Acente-3 (ONAYLI): acente iletisim bilgisi talebi", r["classification"] == "BILGI_ISTEK > ACENTE > ILETISIM_BILGILERI", r["classification"])

r = cat("", "İyi çalışmalar, sistemde kayıtlı olan X acentenin adres ve kurumsal iletişim detaylarına ulaşamıyorum. Acil olarak paylaşabilir misiniz?")
check("Acente-4 (ONAYLI): acenteye ulasamama", r["classification"] == "BILGI_ISTEK > ACENTE > ILETISIM_BILGILERI", r["classification"])

r = cat("", "Selam, X acente hakkında resmi yazışma yapmamız gerekiyor. İlgili acentenin açık adresini ve kurumsal iletişim kanalını iletebilir misiniz?")
check("Acente-5 (ONAYLI): acente resmi yazisma icin iletisim", r["classification"] == "BILGI_ISTEK > ACENTE > ILETISIM_BILGILERI", r["classification"])

# ==========================================================
# 8) TESEKKUR (3 alt dal)
# ==========================================================
r = cat("", "Çok teşekkür ederim, harika bir tatildi.")
check("Tesekkur-1: genel", r["classification"] == "TESEKKUR > TESEKKUR > GENEL_TESEKKUR", r["classification"])

r = cat("", "Rehberimize ve tur liderimize çok teşekkür ederiz, harikaydı.")
check("Tesekkur-2: rehber", r["classification"] == "TESEKKUR > TESEKKUR > REHBER_TESEKKUR", r["classification"])

r = cat("", "Çağrı merkezindeki danışmanımıza teşekkür ederiz, çok yardımcı oldu.")
check("Tesekkur-3: danisman", r["classification"] == "TESEKKUR > TESEKKUR > DANISMAN_TESEKKUR", r["classification"])

r = cat("", "Tsk ederiz, sagolun cok ilgilendiniz.")
check("Tesekkur-4: kisaltma (tsk/sagol)", r["classification"] == "TESEKKUR > TESEKKUR > GENEL_TESEKKUR", r["classification"])

# --- Kullanicinin onayladigi senaryolar (kirilim.md gozden gecirme sureci) ---
r = cat("", "Tatilbudur ailesine teşekkür ederim.")
check("Tesekkur-5 (ONAYLI): tatilbudur ailesine tesekkur", r["classification"] == "TESEKKUR > TESEKKUR > GENEL_TESEKKUR", r["classification"])

r = cat("", "Rehber Oğuz'a teşekkür ederim.")
check("Tesekkur-6 (ONAYLI): isimli rehbere tesekkur, isme takilmamali", r["classification"] == "TESEKKUR > TESEKKUR > REHBER_TESEKKUR", r["classification"])

r = cat("", "Danışmana teşekkür ederim.")
check("Tesekkur-7 (ONAYLI): danismana tesekkur", r["classification"] == "TESEKKUR > TESEKKUR > DANISMAN_TESEKKUR", r["classification"])

r = cat("", "Danışman Ayşe'ye teşekkür ederim.")
check("Tesekkur-8 (ONAYLI): isimli danismana tesekkur, isme takilmamali", r["classification"] == "TESEKKUR > TESEKKUR > DANISMAN_TESEKKUR", r["classification"])

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# "transfer surecinden memnun kaldik" ifadesindeki "transfer" kelimesi,
# TRANSPORT_CHANGE_RIGHTS_KEYWORDS listesinde oldugu icin bu SAF TESEKKUR maili
# yanlislikla ULASIM > DEGISIKLIK_HAKKI_SORGULAMA dalina dusuyordu (gercek CSM
# ticket'ında gozlemlendi). Tesekkur kontrolu fonksiyonun basina alinarak duzeltildi.
r = cat(
    "",
    "Merhaba TatilBudur ailesi, 15-20 Ağustos tarihleri arasında gerçekleştirdiğimiz "
    "tatilimiz başından sonuna kadar kusursuz geçti. Şirketinizin sunduğu organizasyondan, "
    "transfer süreçlerinden ve genel hizmet kalitenizden son derece memnun kaldık. Bize bu "
    "güzel tatili yaşattığınız için ekibinize çok teşekkür ederim. İyi çalışmalar dilerim.",
)
check(
    "Tesekkur-9 (CANLI HATA DUZELTMESI): 'transfer surecinden memnun kaldik' iceren tesekkur maili",
    r["classification"] == "TESEKKUR > TESEKKUR > GENEL_TESEKKUR",
    r["classification"],
)

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# Asiri uzatilmis/yazim hatali tesekkur ifadeleri (ornegin gercek bir CSM
# ticket'inda gorulen "teşeğğküüüü") sabit kelime listesiyle hic yakalanamiyordu.
# contains_thank_you_word() artik "tesekkur" kokune duzenleme mesafesi (fuzzy)
# ile de bakiyor.
r = cat("", "Tatilbudur ailesine teşeğğküüüü")
check("Tesekkur-10 (CANLI HATA DUZELTMESI): asiri uzatilmis/yazim hatali 'tesekkur'", r["classification"] == "TESEKKUR > TESEKKUR > GENEL_TESEKKUR", r["classification"])

r = cat("", "teşküt ederim")
check("Tesekkur-11 (ONAYLI): 'teskut' yazim hatasi", r["classification"] == "TESEKKUR > TESEKKUR > GENEL_TESEKKUR", r["classification"])

r = cat("", "teşeğkürr ediyoruz")
check("Tesekkur-12 (ONAYLI): 'tesegkurr' yazim hatasi", r["classification"] == "TESEKKUR > TESEKKUR > GENEL_TESEKKUR", r["classification"])

# Fuzzy kontrolun alakasiz kelimelere yanlislikla tepki vermedigini dogrula
r = cat("", "Bu otelin adresini öğrenmek istiyorum, oda değişikliği de yapmak istiyorum.")
check("Tesekkur-13 (guvenlik): alakasiz metin fuzzy'e takilmamali", r["classification"] != "TESEKKUR > TESEKKUR > GENEL_TESEKKUR", r["classification"])

# ==========================================================
# 9) VARSAYILAN (TESIS > TESIS ILETISIM)
# ==========================================================
r = cat("", "Otelde havlu değişimi ile ilgili bilgi almak istiyorum.")
check("Varsayilan-1: eslesme yok -> TESIS_ILETISIM", r["classification"] == "BILGI_ISTEK > TESIS > TESIS_ILETISIM", r["classification"])

r = cat("Merhaba", "Bu mail hicbir anahtar kelime icermiyor.")
check("Varsayilan-2: bos/alakasiz metin", r["classification"] == "BILGI_ISTEK > TESIS > TESIS_ILETISIM", r["classification"])

# --- Kullanicinin onayladigi senaryolar (kirilim.md gozden gecirme sureci) ---
r = cat(
    "",
    "Merhaba, 24-28 Ağustos tarih arasındaki rezervasyonumuz için konaklayacağımız "
    "otelin doğrudan iletişim numarasını ve açık adresini öğrenebilir miyim? Teşekkürler.",
)
check(
    "Tesis-1 (ONAYLI): otel iletisim talebi, 'tesekkurler' ile bitiyor ama Tesekkur'e dusmemeli",
    r["classification"] == "BILGI_ISTEK > TESIS > TESIS_ILETISIM",
    r["classification"],
)

r = cat("", "Selam, kalacağımız otelin numarasını atabilir misiniz acele.")
check("Tesis-2 (ONAYLI): otel numarasi talebi", r["classification"] == "BILGI_ISTEK > TESIS > TESIS_ILETISIM", r["classification"])

# ==========================================================
# 10) BUYUK/KUCUK HARF VE TURKCE KARAKTER NORMALIZASYONU
# ==========================================================
r = cat("", "ÇOK TEŞEKKÜR EDERİM, SAĞ OLUN!")
check("Normalize-1: buyuk harf + turkce karakter", r["classification"] == "TESEKKUR > TESEKKUR > GENEL_TESEKKUR", r["classification"])

r = cat("", "FATURA kesilmesini istiyorum.")
check("Normalize-2: buyuk harf FATURA", r["classification"] == "BILGI_ISTEK > FATURA > MISAFIR_FATURASI", r["classification"])

# ==========================================================
# validators.py - dogrudan birim testleri
# ==========================================================
check(f"TC-1: gecerli TC ({VALID_TC})", is_valid_turkish_id(VALID_TC) is True)
check("TC-2: tum haneler ayni -> gecersiz", is_valid_turkish_id("11111111111") is False)
check("TC-3: 0 ile baslayan -> gecersiz", is_valid_turkish_id("01234567890") is False)
check("TC-4: yanlis checksum -> gecersiz", is_valid_turkish_id("12345678901") is False)
check("TC-5: 10 haneli (eksik) -> gecersiz", is_valid_turkish_id("1234567890") is False)

check(f"VKN-1: gecerli VKN ({VALID_VKN})", is_valid_tax_id(VALID_VKN) is True)
check("VKN-2: tum haneler ayni -> gecersiz", is_valid_tax_id("1111111111") is False)
check("VKN-3: 9 haneli (eksik) -> gecersiz", is_valid_tax_id("123456789") is False)

check("Email-1: gecerli email", is_valid_email("ahmet.yilmaz@example.com") is True)
check("Email-2: @ yok -> gecersiz", is_valid_email("ahmet.yilmaz-example.com") is False)
check("Email-3: uzanti yok -> gecersiz", is_valid_email("ahmet@example") is False)

check("Kufur-1: dogrudan kufur tespiti", contains_profanity("bu ne salak bir uygulama") is True)
check("Kufur-2: cogul ek ile tespit", contains_profanity("hepiniz mal siniz") is True)
check("Kufur-3: kufur icermeyen normal metin", contains_profanity("harika bir tatildi tesekkurler") is False)
check(
    "Kufur-4: kelime govdesi eslesmesi olmamali (yanlis pozitif)",
    contains_profanity("malzeme listesini gonderir misiniz") is False,
)

# ==========================================================
# extract_invoice_attributes - dogrudan birim testleri
# ==========================================================
attrs, missing = extract_invoice_attributes(
    f"Şahıs Adı: Ayşe Kaya\nTC: {VALID_TC}\nFatura Adresi: Bağdat Cad. No:1 Istanbul\nFatura E-posta: ayse@example.com\n",
    "sender@example.com",
)
check("InvoiceAttr-1: tum alanlar tam -> eksik yok", missing == [], missing)

attrs, missing = extract_invoice_attributes("Sadece fatura istiyorum, başka bilgi yok.", "sender@example.com")
check("InvoiceAttr-2: hicbir alan yok -> tum alanlar eksik listesinde", len(missing) >= 3, missing)

attrs, missing = extract_invoice_attributes(
    f"Şahıs Adı: Can Öz\nTC: {VALID_TC}\nFatura Adresi: [Buraya yazınız]\n",
    "sender@example.com",
)
check("InvoiceAttr-3: placeholder adres -> eksik alan olarak isaretlenmeli", "Fatura Adresi" in missing, missing)

attrs, missing = extract_invoice_attributes(
    "Şahıs Adı: Deniz Ak\nTC: 12345678901\nFatura Adresi: Örnek Mah. No:9 Ankara\n",
    "sender@example.com",
)
check("InvoiceAttr-4: checksum gecersiz TC -> eksik/gecersiz TC uyarisi", len(missing) >= 1, missing)

attrs, missing = extract_invoice_attributes(
    "Şirket Adı: XYZ Ltd.\nVKN: 1111111111\nFatura Adresi: Örnek Cad. No:2 Izmir\n",
    "sender@example.com",
)
check("InvoiceAttr-5: checksum gecersiz VKN -> eksik/gecersiz VKN uyarisi", len(missing) >= 1, missing)

attrs, missing = extract_invoice_attributes(
    f"Şahıs Adı: Elif Su\nTC: {VALID_TC}\nFatura Adresi: Örnek Sk. No:7 Bursa\n",
    "gonderen@example.com",
)
email_attr = next((a for a in attrs if a.get("attribute", {}).get("shortCode") == "E-_POSTA"), None)
check(
    "InvoiceAttr-6: fatura maili belirtilmemis -> gonderen email fallback",
    email_attr is not None and email_attr.get("textValue") == "gonderen@example.com",
    email_attr,
)

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# Etiketin hemen ardindan parantez icinde ek not/ID gecerse (ör. "Ad Soyad
# (Şahıs Adı - 100054903): ..."), eski regex'ler etiket ile ":" arasinda baska
# bir sey beklemedigi icin hicbir alani yakalayamiyordu (gercek CSM ticket'inda
# "eksik bilgi" red maili gonderildigi gozlemlendi).
attrs, missing = extract_invoice_attributes(
    "Fatura Unvanı / Ad Soyad (Şahıs Adı - 100054903): Bekir Oğuz Karagüney\n"
    f"TC Kimlik Numarası (100054900): {VALID_TC}\n"
    "Fatura Adresi (100000233): Nişantaşı, İstanbul\n"
    "E-Posta (100000234): karaguneyyoguz@gmail.com\n",
    "gonderen@example.com",
)
check(
    "InvoiceAttr-7 (CANLI HATA DUZELTMESI): etiket sonrasi parantezli ID notu",
    not missing,
    missing,
)

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# "Fatura Unvanı" etiketindeki iyelik eki ("unvan" + "ı") regex'te yoktu, bu
# yuzden sirket adi hep eksik sayiliyordu (gercek CSM ticket'inda gozlemlendi).
attrs, missing = extract_invoice_attributes(
    "Fatura Unvanı (Şirket Adı - 100000070): Tatilbudur Seyahat Acenteliği ve Turizm A.Ş.\n"
    f"Vergi Kimlik Numarası (100000066 / 100054901): {VALID_VKN}\n"
    "Vergi Dairesi (100000232): Zincirlikuyu Vergi Dairesi\n"
    "Fatura Adresi (100000233): Esentepe Mah. Büyükdere Cad. Şişli/İstanbul\n"
    "E-Posta (100000234): oguz.karaguney@tatilbudur.com\n",
    "gonderen@example.com",
)
check(
    "InvoiceAttr-8 (CANLI HATA DUZELTMESI): 'Fatura Unvani' iyelik eki + sirket adi",
    not missing,
    missing,
)

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# Duz cumle formati (":" hic yok, "Fatura unvanı X, vergi kimlik numaram Y, ...
# ve mail adresim Z şeklindedir" tarzi) eskiden hic yakalanamiyordu.
attrs, missing = extract_invoice_attributes(
    "Yeni bilgilerim şu şekildedir: Fatura unvanı Tatilbudur Seyahat Acenteliği ve "
    "Turizm A.Ş., vergi kimlik numaram 8340123456, vergi dairem Zincirlikuyu, "
    "adresim Esentepe Mah. Büyükdere Cad. Şişli/İstanbul ve mail adresim "
    "oguz.karaguney@tatilbudur.com şeklindedir.",
    "gonderen@example.com",
)
check(
    "InvoiceAttr-9 (CANLI HATA DUZELTMESI): duz cumle formati, ':' hic yok",
    not missing,
    missing,
)

attrs, missing = extract_invoice_attributes(
    "Fatura bilgilerimiz şu şekildedir: Şirket unvanımız Tatilbudur Seyahat "
    "Acenteliği ve Turizm A.Ş., vergi kimlik numaramız 8340123456, vergi "
    "dairemiz Zincirlikuyu, fatura adresimiz Esentepe Mah. Büyükdere Cad. "
    "Şişli/İstanbul ve e-posta adresimiz oguz.karaguney@tatilbudur.com olarak "
    "belirlenmiştir.",
    "gonderen@example.com",
)
check(
    "InvoiceAttr-10 (CANLI HATA DUZELTMESI): duz cumle formati, coğul iyelik ekleri",
    not missing,
    missing,
)

# ==========================================================
# 11) kirilim.md KAYNAKLI YENI DALLAR (Taslak)
# Bu blok, gercek CSM kirilim listesinin okunmasiyla eklendi.
# ==========================================================
r = cat("", "Evrak eksik olduğu için şikayetçiyim.")
check("Evrak-Sikayet-1", r["classification"] == "SIKAYET > EVRAK > EVRAK", r["classification"])

# Backoffice > Kaydirma > Otel Kaynakli -- otelin overbooking/doluluk nedeniyle
# musteriyi baska tarih/odaya kaydirmasi (musterinin kendi istegiyle yaptigi
# degisiklikten AYRISMALI, bu yuzden bare "degisiklik" kelimesi kasten
# eklenmedi -- o zaten SUB_CATEGORY_CHANGE_HOTEL ile cakisirdi).
r = cat(
    "",
    "İyi günler, 358109758 numaralı rezervasyonumuz için iletişime geçen otel "
    "yönetimi, tesisin otel kaynaklı doluluk ve overbooking problemleri "
    "nedeniyle tarihlerimizi başka bir haftaya kaydırmamızı talep etti. Otelin "
    "bu zorunlu yönlendirmesi doğrultusunda rezervasyonumuzun kaydırma "
    "işlemlerinin backoffice tarafında gerçekleştirilerek güncel bilgilerin "
    "tarafımıza iletilmesini rica ederiz, iyi çalışmalar.",
)
check(
    "Kaydirma-OtelKaynakli-1 (ONAYLI): otel kaynaklı doluluk/overbooking + kaydırma",
    r["classification"] == "BACKOFFICE_ISLEMLERI > KAYDIRMA > OTEL_KAYNAKLI",
    r["classification"],
)

# "kaydir" koku hic gecmeden, sadece "overbooking" ile tetiklenen versiyon --
# SHIFT_EVENT_KEYWORDS'e "overbooking" eklendi (once TESIS_ILETISIM'e
# dusuyordu, canli/gercekci senaryo olarak bildirildi).
r = cat("", "Otelin overbooking durumu nedeniyle rezervasyonumuz başka bir tarihe alındı, bilgi rica ederiz.")
check(
    "Kaydirma-OtelKaynakli-2 (ONAYLI): sadece 'overbooking' ile, 'kaydir' koku olmadan tetiklenmeli",
    r["classification"] == "BACKOFFICE_ISLEMLERI > KAYDIRMA > OTEL_KAYNAKLI",
    r["classification"],
)

# --- Opsiyon Suresi (100000130) + Oncelik="Opsiyonlu" (kullanici tarafindan
# bildirildi: mailde opsiyon suresi gecerse hem attribute eklenmeli hem de
# ticket'in Oncelik alaninda "Opsiyonlu" secilmeli). Sadece Kaydırma > Operasyon
# Kaynaklı / Otel Kaynaklı alt kirilimlarinda gecerli.
r = cat("", "Otel yönetimi doluluk nedeniyle rezervasyonumuzu kaydırdı. Opsiyon Süresi: 11:40. Bilgilerinizi rica ederiz.")
opsiyon_deger = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "OPSIYON_SURESI"), None)
check(
    "Kaydirma-OtelKaynakli-OpsiyonSuresi (ONAYLI): etiketli 'Opsiyon Süresi: 11:40' -> attribute + Oncelik=Opsiyonlu",
    r["classification"] == "BACKOFFICE_ISLEMLERI > KAYDIRMA > OTEL_KAYNAKLI"
    and opsiyon_deger is not None and opsiyon_deger.get("textValue") == "11:40"
    and r.get("priority_level") == "OPSIYONLU",
    (r["classification"], r.get("attributes"), r.get("priority_level")),
)

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# "opsiyon süresi" etiketi ile saat degeri arasina "bugün saat" gibi
# kelimeler girince (ticket #101939124'te gozlemlendi), eski regex ("[:\s]*"
# ile SADECE bosluk/kolon toleransi) eslesemiyor, Oncelik "Normal" kaliyordu.
r = cat(
    "",
    "İyi günler, 553044193 numaralı rezervasyonumuz için otel yönetimi "
    "tarafından iletilen bilgilendirmede, tesisin otel kaynaklı doluluk "
    "problemleri sebebiyle tarihlerimizin başka bir haftaya kaydırılması "
    "istenmiştir. Otelin bu işlem için tanıdığı opsiyon süresi bugün saat "
    "18:40 itibariyla dolacaktır. Bu süre aşılmadan backoffice tarafında "
    "gerekli kaydırma işlemlerinin ivedilikle yapılarak güncel detayların "
    "tarafımıza iletilmesini rica eder, iyi çalışmalar dilerim.",
)
opsiyon_deger3 = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "OPSIYON_SURESI"), None)
check(
    "Kaydirma-OtelKaynakli-OpsiyonSuresi-2 (CANLI HATA DUZELTMESI): 'opsiyon süresi bugün saat 18:40 itibariyla' -> araya giren kelimeler tolere edilmeli",
    r["classification"] == "BACKOFFICE_ISLEMLERI > KAYDIRMA > OTEL_KAYNAKLI"
    and opsiyon_deger3 is not None and opsiyon_deger3.get("textValue") == "18:40"
    and r.get("priority_level") == "OPSIYONLU",
    (r["classification"], r.get("attributes"), r.get("priority_level")),
)

r = cat("", "Operasyon kaynaklı bir aksaklık nedeniyle rezervasyonumuzu kaydırdık, 11:40'a kadar opsiyonumuz var, ilgilenir misiniz.")
opsiyon_deger2 = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "OPSIYON_SURESI"), None)
check(
    "Kaydirma-OperasyonKaynakli-OpsiyonSuresi: duz cumle \"11:40'a kadar opsiyon\" -> attribute + Oncelik=Opsiyonlu",
    r["classification"] == "BACKOFFICE_ISLEMLERI > KAYDIRMA > OPERASYON_KAYNAKLI"
    and opsiyon_deger2 is not None and opsiyon_deger2.get("textValue") == "11:40"
    and r.get("priority_level") == "OPSIYONLU",
    (r["classification"], r.get("attributes"), r.get("priority_level")),
)

# Koruma: opsiyon suresi gecmiyorsa priority_level set edilmemeli (varsayilan
# Normal oncelikte kalmali).
r = cat("", "Otel bizi başka tarihe kaydırdı, bilgi rica ederiz.")
check(
    "Kaydirma-OtelKaynakli-OpsiyonYok (KORUMA): opsiyon suresi yoksa priority_level None kalmali",
    r["classification"] == "BACKOFFICE_ISLEMLERI > KAYDIRMA > OTEL_KAYNAKLI"
    and not r["attributes"]
    and r.get("priority_level") is None,
    (r["classification"], r.get("attributes"), r.get("priority_level")),
)

# DOCUMENT_COMPLAINT_EVENT_KEYWORDS eski hali sadece "eksik/hatali/yanlis/
# sikinti/sorun" iceriyordu; gercek musteri sikayetlerinde en sik gecen
# "ulasmadi/iletilmedi/magduriyet" gibi ifadeler eksikti (kullanici tarafindan
# bildirildi).
r = cat(
    "",
    "İyi günler, rezervasyonumuzla ilgili tarafımıza gönderilmesi gereken resmi "
    "evraklar ve belgeler üzerinden haftalar geçmesine rağmen hâlâ elimize "
    "ulaşmadı. Evrakların zamanında iletilmemesi nedeniyle büyük bir aksaklık "
    "yaşıyoruz ve bu durumdan şikayetçiyiz. İlgili belgelerin acilen tarafımıza "
    "elektronik veya kargo yoluyla ulaştırılmasını rica eder, iyi çalışmalar dilerim.",
)
check(
    "Evrak-Sikayet-2 (ONAYLI): 'ulasmadi/iletilmemesi/aksaklik/sikayetciyiz' -> DOCUMENT_COMPLAINT_EVENT_KEYWORDS genisletildi",
    r["classification"] == "SIKAYET > EVRAK > EVRAK",
    r["classification"],
)

# "evrak" koku iyelik eki alinca unsuz yumusamasiyla "evragi/evragimiz" olur
# (k->g, "degisiklik->degisikligi" ile ayni dilbilgisi sinifi); DOCUMENT_TOPIC_KEYWORDS'e
# "evrag" stemi eklendi.
r = cat("", "Merhaba, ıslak imzalı evrağımız hâlâ gönderilmedi, mağduriyet yaşıyoruz.")
check(
    "Evrak-Sikayet-3 (ONAYLI): 'evragimiz' unsuz yumusamasi + islak imza",
    r["classification"] == "SIKAYET > EVRAK > EVRAK",
    r["classification"],
)

r = cat("", "Sözleşme metnini gönderir misiniz.")
check("Evrak-BI-Sozlesme", r["classification"] == "BILGI_ISTEK > EVRAK > SOZLESME", r["classification"])

r = cat("", "Vize kiti evraklarını ne zaman gönderiyorsunuz.")
check("Evrak-BI-VizeKiti", r["classification"] == "BILGI_ISTEK > EVRAK > VIZE_KITI", r["classification"])

# --- Kullanicinin verdigi "nokta atisi" senaryolari (ONAYLI) ---
r = cat("", "Merhaba, gerçekleştirdiğimiz rezervasyona ait mesafeli satış sözleşmesinin ve tur sözleşmesi kopyasının tarafıma e-posta yoluyla iletilmesini rica ediyorum. İyi çalışmalar.")
check("Evrak-Sozlesme-2 (ONAYLI): mesafeli satis sozlesmesi", r["classification"] == "BILGI_ISTEK > EVRAK > SOZLESME", r["classification"])

r = cat("", "İyi günler, satın aldığımız yurtdışı turu için gerekli olan vize kiti evrak listesini ve konsolosluk başvuru formlarını öğrenmek istiyorum. Vize evrakları hakkında bilgilendirme rica ederim.")
check("Evrak-VizeKiti-2 (ONAYLI): vize kiti + konsolosluk basvuru formu", r["classification"] == "BILGI_ISTEK > EVRAK > VIZE_KITI", r["classification"])

r = cat("", "Merhaba, önümüzdeki günlerde hareket edecek olan turumuz için görevli otobüs şoförünün adını, telefon numarasını ve araç plaka bilgilerini öğrenebilir miyim? Teşekkürler.")
check("Evrak-SoforBilgileri-2 (ONAYLI): sofor adi + plaka", r["classification"] == "BILGI_ISTEK > EVRAK > TUR_OTOBUS_SOFOR_BILGILERI", r["classification"])

r = cat("", "Rezervasyonumda değişiklik yapabilir miyim.")
check("Rezervasyon-BI-DegisiklikBilgi", r["classification"] == "BILGI_ISTEK > REZERVASYON > DEGISIKLIK_BILGI_TALEBI", r["classification"])

r = cat("", "İptal süreci hakkında bilgi almak istiyorum.")
check("Rezervasyon-BI-IptalSurecBilgi", r["classification"] == "BILGI_ISTEK > REZERVASYON > IPTAL_SUREC_BILGISI", r["classification"])

r = cat("", "İade ne zaman yapılır, iade süresi ne kadar.")
check("OdemeSistemleri-BI-IadeBilgisi", r["classification"] == "BILGI_ISTEK > ODEME_SISTEMLERI_KONULARI > IADE_BILGISI", r["classification"])

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# "yansima" bare kelimesi ve "iptal"+"surec" gevsek eslesmesi, notr bir iade-
# bilgisi talebini yanlislikla SIKAYET > IADE ve REZERVASYON > IPTAL_SUREC_BILGISI
# dallarina cekiyordu (gercek CSM ticket'inda gozlemlendi).
r = cat(
    "",
    "Merhaba, Daha önce iptal ettiğim rezervasyonuma ait iade tutarının kartıma "
    "yansıma durumu hakkında bilgi talep ediyorum. İşleme ait detaylar aşağıda "
    "yer almaktadır:\nİşlem Tarihi: 15.08.2026\nKartın İlk 6 Rakamı: 454360\n"
    "Kartın Son 4 Rakamı: 1234\nTutar: 12.500 TL\nSipariş No: 358109758\n"
    "İade sürecimin kontrol edilerek tarafıma bilgi verilmesini rica ederim. "
    "İyi çalışmalar.",
)
check(
    "OdemeSistemleri-BI-IadeBilgisi-2 (CANLI HATA DUZELTMESI): notr iade sorgusu, sikayet degil",
    r["classification"] == "BILGI_ISTEK > ODEME_SISTEMLERI_KONULARI > IADE_BILGISI" and len(r["attributes"]) == 5,
    (r["classification"], r["attributes"]),
)

# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# Ayni senaryo, hic etiket kullanilmayan duz cumle formatinda ("454360 ile
# baslayan ve 1234 ile biten kartimla", "sipariş numaram ise X'dir" gibi).
r = cat(
    "",
    "İyi günler, geçtiğimiz günlerde iptalini gerçekleştirdiğim tatil "
    "rezervasyonum için ödediğim tutarın hesabıma iadesi konusunda bilgi almak "
    "istiyorum. İşlemle ilgili olarak 15.08.2026 tarihinde, 454360 ile "
    "başlayan ve 1234 ile biten kartımla 12.500 TL tutarında bir ödeme "
    "yapmıştım, sipariş numaram ise 358109758'dir. İade sürecimin ne "
    "aşamada olduğunu öğrenebilir miyim? Teşekkürler, iyi çalışmalar.",
)
check(
    "OdemeSistemleri-BI-IadeBilgisi-3 (CANLI HATA DUZELTMESI): duz cumle, etiketsiz odeme bilgileri",
    r["classification"] == "BILGI_ISTEK > ODEME_SISTEMLERI_KONULARI > IADE_BILGISI" and len(r["attributes"]) == 5,
    (r["classification"], r["attributes"]),
)

r = cat("", "Otelin operasyonundan şikayetçiyim, resepsiyon ilgisizdi.")
check("Sikayet-Otel-Operasyon", r["classification"] == "SIKAYET > OTEL > OPERASYON", r["classification"])

r = cat("", "Otel hizmetinden memnun değilim, havuz kirliydi.")
check("Sikayet-Otel-Hizmetleri", r["classification"] == "SIKAYET > OTEL > OTEL_HIZMETLERI", r["classification"])

r = cat("", "Havayolu değişti, farklı havayolu ile uçuruldu.")
check("Sikayet-Ucak-HavayoluDegisikligi", r["classification"] == "SIKAYET > UCAK > HAVAYOLU_DEGISIKLIGI", r["classification"])

r = cat("", "Uçak saati değişti, kalkış saati değişti.")
check("Sikayet-Ucak-SaatDegisikligi", r["classification"] == "SIKAYET > UCAK > SAAT_DEGISIKLIGI", r["classification"])

r = cat("", "Seferimiz iptal edildi.")
check("Sikayet-Ucak-SeferIptali", r["classification"] == "SIKAYET > UCAK > SEFER_IPTALI", r["classification"])

r = cat("", "Rezervasyon işlemimde sorun yaşadım, yanlış rezervasyon yapıldı.")
check("Sikayet-BilgiTalebi-RezervasyonIslemi", r["classification"] == "SIKAYET > BILGI_TALEBI > REZERVASYON_ISLEMI", r["classification"])

# --- Kullanicinin verdigi "nokta atisi" senaryosu (ONAYLI) ---
r = cat("", "İyi günler, rezervasyon işlemimiz sırasında yapılması gereken bilgilendirmelerin zamanında yapılmaması ve süreçin şeffaf yürütülmemesi nedeniyle ciddi mağduriyet yaşadık. Rezervasyon işlem adımlarında karşılaştığımız bu aksaklıkların ve ilgisizliğin incelenerek tarafıma açıklama yapılmasını talep ediyorum.")
check("Sikayet-BilgiTalebi-RezervasyonIslemi-2 (ONAYLI): magduriyet/aksaklik/ilgisizlik", r["classification"] == "SIKAYET > BILGI_TALEBI > REZERVASYON_ISLEMI", r["classification"])

r = cat("", "Çağrı merkezinden kötü hizmet aldım, temsilci kaba davrandı.")
check("Sikayet-SatisSureci-CagriMerkezi", r["classification"] == "SIKAYET > SATIS_SURECI > CAGRI_MERKEZI", r["classification"])

# --- Kullanicinin verdigi "nokta atisi" senaryosu (ONAYLI) ---
r = cat("", "Merhaba, rezervasyon aşamasında bilgi almak için çağrı merkezinizi aradığımda görüştüğüm müşteri temsilcisinin ilgisiz ve kaba tutumuyla karşılaştım. Ayrıca telefonda bana aktarılan bilgilerin yanlış olması nedeniyle planlamamız aksadı. Çağrı merkezi görüşmelerinin incelenerek ilgili personel hakkında gerekli uyarıların yapılmasını ve tarafıma dönüş sağlanmasını rica ederim.")
check("Sikayet-SatisSureci-CagriMerkezi-2 (ONAYLI): temsilci ilgisiz/kaba + yanlis bilgilendirme", r["classification"] == "SIKAYET > SATIS_SURECI > CAGRI_MERKEZI", r["classification"])

r = cat("", "Tur organizasyonu kötüydü, tur programında aksama oldu.")
check("Sikayet-TurRehber-Tur", r["classification"] == "SIKAYET > TUR_ORGANIZASYONU_VE_REHBER > TUR", r["classification"])

r = cat("", "Rehberden memnun değilim, rehber ilgisizdi.")
check("Sikayet-TurRehber-Rehber", r["classification"] == "SIKAYET > TUR_ORGANIZASYONU_VE_REHBER > REHBER", r["classification"])

r = cat("", "İade yapılmadı, param iade edilmedi.")
check("Sikayet-Iade-Yapilmamasi", r["classification"] == "SIKAYET > IADE > IADENIN_YAPILMAMASI", r["classification"])

r = cat("", "İade talebim açılmamış, iade başvurum işlenmemiş.")
check("Sikayet-Iade-TalebiAcilmamis", r["classification"] == "SIKAYET > IADE > IADE_TALEBININ_ACILMAMIS_OLMASI", r["classification"])

r = cat("", "İade hesabıma yansımadı.")
check("Sikayet-Iade-MisafireYansimamasi", r["classification"] == "SIKAYET > IADE > IADENIN_MISAFIRE_YANSIMAMASI", r["classification"])

r = cat("", "En iyi fiyat garantisi talep ediyorum, başka sitede daha ucuz gördüm.")
check("Sikayet-Fiyat-EnIyiFiyatGarantisi", r["classification"] == "SIKAYET > FIYATLANDIRMA > EN_IYI_FIYAT_GARANTISI", r["classification"])

r = cat("", "Ürün fiyatı düştü ama iade edilmedi.")
check("Sikayet-Fiyat-Dususu", r["classification"] == "SIKAYET > FIYATLANDIRMA > FIYAT_DUSUSU", r["classification"])

r = cat("", "Ödemeye itiraz ediyorum, yanlış tutar çekildi.")
check("Sikayet-Fiyat-OdemeItirazi", r["classification"] == "SIKAYET > FIYATLANDIRMA > ODEME_ITIRAZI", r["classification"])

r = cat("", "Fiyat ile ilgili şikayetim var, fiyat hatalı gösterilmiş.")
check("Sikayet-Fiyat-Genel", r["classification"] == "SIKAYET > FIYATLANDIRMA > FIYAT_GENEL", r["classification"])

# --- COZULDU (musteri onayli ayrim kurali): "sofor" bare kelimesi tek basina
# EVRAK'a gitmez; "plaka"/"kaptan" veya "sofor" + isim talebi (adini/ismini)
# gerekir. Sadece "sofor" + "evrak/belge" gecen bu metin dogru sekilde
# ULASIM > OTOBUS'ta kaliyor (plaka/kaptan/isim talebi yok).
r = cat("", "Otobüs şoförünün evraklarını paylaşır mısınız.")
check(
    "Otobus-5 (COZULDU): 'sofor evraklari' (plaka/isim yok) -> OTOBUS'ta kalmali",
    r["classification"] == "BILGI_ISTEK > ULASIM > OTOBUS",
    r["classification"],
)

# Backoffice'teki CONFIRMATION_KEYWORDS listesinde bare "konfirme" kelimesi var;
# bu yuzden sadece bilgi soran ("Konfirme nedir?") mailler de Backoffice > Konfirme
# dalina dusuyor, yeni eklenen Bilgi-Istek > Rezervasyon > Konfirme dalina hic ulasamiyor.
r = cat("", "Konfirme nedir, ne zaman gelir?")
check(
    "COLLISION-5: 'konfirme nedir' -> beklenen REZERVASYON>KONFIRME(bilgi) ama BACKOFFICE>KONFIRME dalina dusuyor",
    r["classification"] == "BILGI_ISTEK > REZERVASYON > KONFIRME",
    r["classification"],
)

# ==========================================================
# 12) DOGAL/GERCEKCI IFADE DENETIMI
# Bu blok, kirilim tanimlarinda kullanilan kelimelerle BIREBIR AYNI OLMAYAN,
# gercek musteri mailine yakin dogal ifadelerle kurulmustur. Amac: "sadece
# kendi anahtar kelimemi tekrar ediyorum" seklindeki dongusel testten kacinip
# kodun gercekten esnek olup olmadigini olcmek.
# Bilinen 4 senaryo (KNOWN ISSUE), TRANSPORT_CHANGE_RIGHTS_KEYWORDS listesindeki
# genel "otobus"/"transfer" kelimelerinin erken ve genis eslesmesinden dolayi
# hala basarisiz -- bu, otobus/transfer icerigi ayrica konusulup karara
# baglanana kadar boyle kalacak.
# ==========================================================
KNOWN_ISSUE_SCENARIOS = {15, 23, 32}

REALISTIC_SCENARIOS = [
    (9, "BILGI_ISTEK > ULASIM > BILET", "Merhaba, yarınki uçuşumuza ait e-biletimiz hala mail kutumuza düşmedi, tekrar gönderebilir misiniz?"),
    (9, "BILGI_ISTEK > ULASIM > BILET", "Bilet numaramı unuttum, bana tekrar iletebilir misiniz acaba."),
    (10, "BILGI_ISTEK > ULASIM > DEGISIKLIK_HAKKI_SORGULAMA", "Uçuşumuz iptal olursa değişiklik hakkımız var mı, transfer saatimiz kesinleşti mi öğrenmek istiyorum."),
    (10, "BILGI_ISTEK > ULASIM > DEGISIKLIK_HAKKI_SORGULAMA", "Otelimizi kendi imkanlarımızla terk etmek istiyoruz, bu durumda transferden düşer miyiz."),
    (11, "BILGI_ISTEK > ULASIM > OTOBUS", "Tur otobüsümüzün kalkış saatini ve güzergahını öğrenebilir miyiz?"),
    (11, "BILGI_ISTEK > ULASIM > OTOBUS", "Şoförümüzün telefon numarasını iletir misiniz, otobüse nereden bineceğiz?"),
    (12, "BILGI_ISTEK > EVRAK > SOZLESME", "Satın aldığımız tur paketine ait sözleşme belgesinin bir kopyasını iletebilir misiniz?"),
    (12, "BILGI_ISTEK > EVRAK > SOZLESME", "İmzaladığımız sözleşmenin PDF halini rica ediyorum."),
    (13, "BILGI_ISTEK > EVRAK > VIZE_KITI", "Vizemiz için gereken evrak kitini ne zaman elimize ulaştıracaksınız?"),
    (13, "BILGI_ISTEK > EVRAK > VIZE_KITI", "Vize başvurusu için kit hala gelmedi, kargoya verildi mi?"),
    (14, "BILGI_ISTEK > ULASIM > OTOBUS", "Turumuzda kullanılacak otobüsün şoförüne ait belgeleri paylaşabilir misiniz?"),
    (15, "BILGI_ISTEK > REZERVASYON > DEGISIKLIK_BILGI_TALEBI", "Rezervasyonumda oda tipini değiştirebilir miyim, önce bir bilgi almak istiyorum."),
    (16, "BILGI_ISTEK > REZERVASYON > IPTAL_SUREC_BILGISI", "Rezervasyonumu iptal edersem nasıl bir süreç işliyor, ücret iadesi oluyor mu?"),
    (17, "BILGI_ISTEK > REZERVASYON > KONFIRME", "Konfirme belgemiz ne zaman elimize ulaşır acaba, süreç ne kadar sürüyor?"),
    (18, "BILGI_ISTEK > ODEME_SISTEMLERI_KONULARI > IADE_BILGISI", "İptal ettiğimiz rezervasyonun iadesi genelde kaç gün içinde hesabımıza geçiyor?"),
    (19, "BACKOFFICE_ISLEMLERI > ODEME > ODEMENIN_YANSIMAMASI", "Kartımdan tutar çekildi ancak rezervasyon sistemde hiç oluşmadı, ödeme kayboldu sanırım."),
    (20, "BACKOFFICE_ISLEMLERI > KONFIRME > KONFIRME", "Rezervasyon yaptırdık ama hala konfirme evrağı elimize geçmedi, acil lazım."),
    (21, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ODEME_TIPI_DEGISIKLIGI", "Ödemeyi tek çekim yaptım, taksitli ödemeye çevirmek mümkün mü?"),
    (22, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DOGUM_TARIHI_DEGISIKLIGI", "Çocuğumun doğum tarihini rezervasyona yanlış girmişiz, düzeltilmesi gerekiyor."),
    (23, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > EK_HIZMETLER", "Rezervasyonumuza ekstra yatak ve transfer hizmeti eklettirmek istiyoruz."),
    (24, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ISIM_DEGISIKLIGI", "Rezervasyonda soyadım hatalı yazılmış, düzeltilmesini rica ederim."),
    (25, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > KISI_EKLEME_CIKARMA", "Rezervasyonumuza son anda 1 kişi daha eklemek istiyoruz, mümkün müdür?"),
    (26, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > NOT_EKLEME_TALEBI", "Otel tarafına iletilmek üzere rezervasyonumuza balayı notu düşürebilir misiniz?"),
    (27, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ODA", "Şu anki odamızı beğenmedik, başka bir odaya geçmek istiyoruz."),
    (28, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ODA_TIPI_DEGISIKLIGI", "Standart oda yerine deluxe odaya geçiş yapmak istiyoruz."),
    (29, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > OTEL_DEGISIKLIGI", "Rezervasyon yaptığımız otel yerine yakınındaki başka bir otele geçmek istiyoruz."),
    (30, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TARIH_DEGISIKLIGI", "Tatil tarihlerimizi bir hafta ileri almak istiyoruz, uygun mu?"),
    (31, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TUR_DEGISIKLIGI", "Kapadokya turu yerine Efes turuna geçmek istiyoruz."),
    (32, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DEGISIKLIK_ULASIM", "Uçakla gitmek yerine otobüsle gitmeyi tercih ediyoruz, değiştirebilir misiniz?"),
    (33, "BACKOFFICE_ISLEMLERI > DEGISIKLIK > UCAK_BILETI_DEGISIKLIGI", "Uçak biletimizdeki saati değiştirmek istiyoruz, mümkün mü?"),
    (34, "BACKOFFICE_ISLEMLERI > IPTAL > ODA_IPTALI", "Rezervasyonumuzdaki fazladan odayı iptal ettirmek istiyoruz."),
    (35, "BACKOFFICE_ISLEMLERI > IPTAL > IPTAL_TALEBI", "Tatil planımız değişti, rezervasyonun tamamını iptal etmek istiyoruz."),
    (36, "BACKOFFICE_ISLEMLERI > IPTAL > UCAK_BILETI_IPTALI", "Uçak biletimizi iptal ettirmek istiyoruz, iade alabilir miyiz?"),
    (37, "BACKOFFICE_ISLEMLERI > EK_HIZMET > IPTAL_SIGORTASI", "Aldığımız iptal sigortasını kullanmak istemiyoruz, iptal edebilir misiniz?"),
    (38, "BACKOFFICE_ISLEMLERI > KAYDIRMA > OTEL_KAYNAKLI", "Otel bize haber vermeden başka bir tesise kaydırmış, bilgi almak istiyoruz."),
    (39, "BACKOFFICE_ISLEMLERI > KAYDIRMA > OPERASYON_KAYNAKLI", "Operasyon ekibiniz bizi farklı bir otele kaydırdı, nedenini öğrenebilir miyiz?"),
    (40, "BACKOFFICE_ISLEMLERI > DIGER_ISLEMLER > ODEME_TAMAMLAMA", "Rezervasyonumuzda kalan bakiyeyi şimdi tamamlamak istiyoruz."),
    (41, "SIKAYET > OTEL > OPERASYON", "Otele giriş yaparken resepsiyon bizimle çok ilgisiz davrandı, check-in 2 saat sürdü."),
    (42, "SIKAYET > OTEL > OTEL_HIZMETLERI", "Odamız hiç temizlenmedi, havuz suyu pislik içindeydi, çok kötü bir deneyimdi."),
    (43, "SIKAYET > UCAK > HAVAYOLU_DEGISIKLIGI", "Bize önceden haber verilmeden farklı bir havayolu şirketiyle uçurulduk."),
    (44, "SIKAYET > UCAK > SAAT_DEGISIKLIGI", "Uçuş saatimiz habersizce değiştirildi, planlarımız altüst oldu."),
    (45, "SIKAYET > UCAK > SEFER_IPTALI", "Uçuşumuz son anda iptal edildi, mağdur olduk."),
    (46, "SIKAYET > EVRAK > EVRAK", "Gönderdiğiniz evrakta bilgiler hatalı, düzeltilmiş halini talep ediyorum."),
    (47, "SIKAYET > BILGI_TALEBI > REZERVASYON_ISLEMI", "Rezervasyon işlemimiz sırasında yanlış tarih girilmiş, bu ciddi bir hata."),
    (48, "SIKAYET > SATIS_SURECI > CAGRI_MERKEZI", "Çağrı merkezini aradığımda temsilci bana çok kaba davrandı, şikayetçiyim."),
    (49, "SIKAYET > TUR_ORGANIZASYONU_VE_REHBER > TUR", "Tur programı ilan edildiği gibi işlemedi, saatler tamamen karıştı."),
    (50, "SIKAYET > TUR_ORGANIZASYONU_VE_REHBER > REHBER", "Rehberimiz gruba karşı çok ilgisizdi, sorularımızı yanıtsız bıraktı."),
    (51, "SIKAYET > IADE > IADENIN_YAPILMAMASI", "İptal ettiğim rezervasyonun parası hala bana iade edilmedi."),
    (52, "SIKAYET > IADE > IADE_TALEBININ_ACILMAMIS_OLMASI", "İade talebi oluşturdum ama sistemde hiçbir kayıt görünmüyor, hiç işleme alınmamış."),
    (53, "SIKAYET > IADE > IADENIN_MISAFIRE_YANSIMAMASI", "İade yapıldığı söylendi ama kart ekstremde hiçbir yansıma göremiyorum."),
    (54, "SIKAYET > FIYATLANDIRMA > EN_IYI_FIYAT_GARANTISI", "Aynı oteli başka bir sitede çok daha ucuz gördüm, fiyat garantisi kapsamında fark ödemesi istiyorum."),
    (55, "SIKAYET > FIYATLANDIRMA > FIYAT_GENEL", "Rezervasyon sırasında gösterilen fiyat ile faturadaki tutar birbirini tutmuyor."),
    (56, "SIKAYET > FIYATLANDIRMA > FIYAT_DUSUSU", "Rezervasyon yaptıktan bir gün sonra aynı paketin fiyatı düştü, aradaki farkı talep ediyorum."),
    (57, "SIKAYET > FIYATLANDIRMA > ODEME_ITIRAZI", "Kartımdan çekilen tutar anlaştığımız tutardan fazla, buna itiraz ediyorum."),
]

# ==========================================================
# SIKAYET > ODEME_SISTEMLERI (5 kirilim): Banka Itirazi, Fazla Cekim,
# Kampanya Uygulama, Odemenin Yansimamasi, Provizyon. Finansal attribute'lar
# (Islem Tarihi/Kart Ilk 6/Kart Son 4/Tutar/Siparis No) OPSIYONEL tutuluyor
# (musteri onayiyla, Backoffice > Odeme > Odemenin Yansimamasi'nin aksine).
# ==========================================================
r = cat(
    "",
    "İyi günler, 21.08.2026 tarihinde 358109758 numaralı siparişim için 454360 "
    "ile başlayan ve 1234 ile biten kartımdan çekilen 12.500 TL tutarındaki "
    "işlem bilgim dışındadır veya hizmet alınamadığı için bankaya harcama "
    "itirazında bulundum, bu mağduriyetin giderilmesini ve şikayetimin işleme "
    "alınmasını talep ediyorum.",
)
tarih_deger = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "ISLEM_TARIHI"), None)
check(
    "OdemeSistemleri-Sikayet-BankaItirazi (ONAYLI)",
    r["classification"] == "SIKAYET > ODEME_SISTEMLERI > BANKA_ITIRAZI"
    and not r["missing_fields"]
    and tarih_deger is not None and tarih_deger.get("textValue") == "21/08/2026",
    (r["classification"], r["missing_fields"], r["attributes"]),
)

r = cat(
    "",
    "Merhaba, 21.08.2026 tarihinde 358109758 nolu rezervasyonum için "
    "454360******1234 kartımdan yapılması gereken tutardan fazla olacak "
    "şekilde 12.500 TL çekilmiştir. Fazla çekilen tutarın tarafıma iadesi "
    "hususunda acil yardımlarınızı rica eder, bu hatadan ötürü şikayetçiyim.",
)
check(
    "OdemeSistemleri-Sikayet-FazlaCekim (ONAYLI)",
    r["classification"] == "SIKAYET > ODEME_SISTEMLERI > FAZLA_CEKIM",
    r["classification"],
)
# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# Yukaridaki AYNI metin, CSM ekranina basildiginda: Islem Tarihi alani BUGUNUN
# tarihini gosteriyordu (CSM'in tarih widget'i "21.08.2026" nokta formatini
# parse edemiyordu -- "DD/MM/YYYY" egik cizgi formati bekliyor), Kartin Ilk
# 6/Son 4 Rakami alanlari BOS kaliyordu (maskeli "454360******1234" formati
# desteklenmiyordu) ve Siparis No alani BOS kaliyordu ("358109758 nolu
# rezervasyonum" -- "numarali siparis" degil -- eslesmiyordu).
tarih_deger2 = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "ISLEM_TARIHI"), None)
ilk6_deger2 = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "KARTIN_ILK_6_RAKAMI"), None)
son4_deger2 = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "KARTIN_SON_4_RAKAMI"), None)
siparis_deger2 = next((a for a in r["attributes"] if a.get("attribute", {}).get("shortCode") == "SIPARIS_NO"), None)
check(
    "OdemeSistemleri-Sikayet-FazlaCekim-Attributes (CANLI HATA DUZELTMESI): maskeli kart + 'nolu rezervasyon' + tarih formati",
    tarih_deger2 is not None and tarih_deger2.get("textValue") == "21/08/2026"
    and ilk6_deger2 is not None and ilk6_deger2.get("textValue") == "454360"
    and son4_deger2 is not None and son4_deger2.get("textValue") == "1234"
    and siparis_deger2 is not None and siparis_deger2.get("textValue") == "358109758",
    r["attributes"],
)

r = cat(
    "",
    "İyi günler, 21.08.2026 tarihinde gerçekleştirdiğim 358109758 numaralı "
    "siparişimde 454360******1234 kartımla yaptığım 12.500 TL ödemede hak "
    "kazandığım kampanya indirimi tutara uygulanmamıştır. İndirimin "
    "yansıtılmaması nedeniyle yaşadığım mağduriyetin giderilmesini rica ederim.",
)
check(
    "OdemeSistemleri-Sikayet-KampanyaUygulama (ONAYLI)",
    r["classification"] == "SIKAYET > ODEME_SISTEMLERI > KAMPANYA_UYGULAMA",
    r["classification"],
)

# Not: Backoffice > Odeme > Odemenin Yansimamasi ile AYNI topic/event
# kaliplarini paylasir; ayirt edici sinyal COMPLAINT_SENTIMENT_KEYWORDS
# ("magduriyet" burada) -- bu yuzden koruma testi de asagida ekli.
r = cat(
    "",
    "Merhaba, 21.08.2026 tarihinde 358109758 nolu siparişim için "
    "454360******1234 kartımdan 12.500 TL çekilmesine rağmen ödeme "
    "sisteminize yansımadı ve rezervasyonum askıda kaldı. Mağduriyetimin "
    "giderilmesi için ödememin eşleştirilmesini talep ediyorum.",
)
check(
    "OdemeSistemleri-Sikayet-OdemeninYansimamasi (ONAYLI)",
    r["classification"] == "SIKAYET > ODEME_SISTEMLERI > ODEMENIN_YANSIMAMASI",
    r["classification"],
)

r = cat("", "Kartımdan tutar çekildi ancak rezervasyon sistemde hiç oluşmadı, ödeme kayboldu sanırım.")
check(
    "OdemeSistemleri-Sikayet-OdemeninYansimamasi-Koruma: magduriyet/sikayet kelimesi YOK -> Backoffice (islemsel) kalmali",
    r["classification"] == "BACKOFFICE_ISLEMLERI > ODEME > ODEMENIN_YANSIMAMASI",
    r["classification"],
)

r = cat(
    "",
    "İyi günler, 21.08.2026 tarihli 358109758 numaralı rezervasyon işlemim "
    "sonrasında 454360******1234 kartımda 12.500 TL tutarındaki provizyon "
    "blokesi günlerdir kaldırılmadı. Bu durum kart limitimi olumsuz "
    "etkilediği için şikayetçiyim, blokenin kaldırılmasını rica ederim.",
)
check(
    "OdemeSistemleri-Sikayet-Provizyon (ONAYLI)",
    r["classification"] == "SIKAYET > ODEME_SISTEMLERI > PROVIZYON",
    r["classification"],
)

for num, expected, text in REALISTIC_SCENARIOS:
    r = cat("", text)
    label = f"Gercekci-{num}"
    if num in KNOWN_ISSUE_SCENARIOS:
        label += " (KNOWN ISSUE: otobus/transfer genel kelime cakismasi)"
    check(label, r["classification"] == expected, r["classification"])

# ==========================================================
# extract_reservation_number + ticketProductId/relatedProduct (Urun Eslestirme)
# Kullanici tarafindan bildirilen kural: kirilim ne olursa olsun, mailde
# rezervasyon numarasi geciyorsa CSM/Etiya'dan ilgili urun kaydi cekilip
# ticket'a ("ticketProductId" + "relatedProduct") gomulmeli -- aksi halde
# backoffice ekibi ticket icinde ilgili rezervasyona erisemiyor (canli
# ortamda musteri temsilcisinin "rezervasyon numarasi paylasabilir misiniz"
# diye geri donmesiyle tespit edildi).
# ==========================================================
check(
    "ReservationNo-1: etiketli 'Rezervasyon No: 553044193'",
    extract_reservation_number("Rezervasyon No: 553044193 için bilgi rica ederim.") == "553044193",
    extract_reservation_number("Rezervasyon No: 553044193 için bilgi rica ederim."),
)
check(
    "ReservationNo-2: kisa etiket 'Rez No: 553044193'",
    extract_reservation_number("Rez No: 553044193, bilgi rica ederim.") == "553044193",
    extract_reservation_number("Rez No: 553044193, bilgi rica ederim."),
)
check(
    "ReservationNo-3: duz cumle '358109758 nolu rezervasyonum'",
    extract_reservation_number("358109758 nolu rezervasyonum için bilgi rica ederim.") == "358109758",
    extract_reservation_number("358109758 nolu rezervasyonum için bilgi rica ederim."),
)
check(
    "ReservationNo-4: duz cumle '358109758 numaralı siparişim'",
    extract_reservation_number("358109758 numaralı siparişim için bilgi rica ederim.") == "358109758",
    extract_reservation_number("358109758 numaralı siparişim için bilgi rica ederim."),
)
# --- CANLI ORTAMDA BULUNAN GERCEK HATA (duzeltildi) ---
# Etiket sonrasi rakam OLMAYAN bir cumle gelirse (ör. "rezervasyon numarası
# içermiyor"), eski regex bir sonraki kelimenin ASCII on ekini ("i")
# yanlislikla rezervasyon numarasi saniyordu -- yakalanan degerin rakamla
# BASLAMASI zorunlu kilinarak duzeltildi.
check(
    "ReservationNo-5 (CANLI HATA DUZELTMESI): rakamsiz 'rezervasyon numarası içermiyor' -> None donmeli",
    extract_reservation_number("Genel bir bilgi talebim var, rezervasyon numarası içermiyor.") is None,
    extract_reservation_number("Genel bir bilgi talebim var, rezervasyon numarası içermiyor."),
)

_urun_ornek_kategorizasyon = cat("", "553044193 numaralı rezervasyonum ile ilgili bilgi almak istiyorum.")
_urun_related_product = {
    "accountId": None, "accountNumber": None,
    "accountStatus": "Kesin rezervasyondan iptal",
    "attributeValueList": [],
    "createDate": None, "endDate": "2026-10-01T21:00:00.000Z",
    "id": None, "isServiceNumberProduct": True,
    "name": "Limak Eurasia Luxury Hotel", "parentProductId": None,
    "productCategory": {"shortCode": "SEHIR_OTELLERI_HOTEL", "name": "Şehir Otelleri"},
    "productId": "6391234", "productNumber": "6391234",
    "productStatus": "CLO", "serviceNumber": "553044193",
    "startDate": "2026-09-30T21:00:00.000Z", "status": 1, "updateDate": None,
}
_urun_payload = TicketPayloadBuilder.build_payload(
    "test@example.com", "Test User", "konu",
    "553044193 numaralı rezervasyonum ile ilgili bilgi almak istiyorum.",
    _urun_ornek_kategorizasyon,
    related_product=_urun_related_product,
)
check(
    "UrunEslestirme-1 (ONAYLI): related_product verilince ticketProductId + relatedProduct dolmali",
    _urun_payload.get("ticketProductId") == "6391234"
    and _urun_payload.get("relatedProduct", {}).get("name") == "Limak Eurasia Luxury Hotel"
    and _urun_payload.get("relatedProduct", {}).get("uniqueRowId") == "6391234_None_553044193"
    and _urun_payload.get("relatedProduct", {}).get("relatedInvoices") == [],
    (_urun_payload.get("ticketProductId"), _urun_payload.get("relatedProduct")),
)

_urun_payload_bos = TicketPayloadBuilder.build_payload(
    "test@example.com", "Test User", "konu",
    "Genel bir bilgi talebim var.",
    _urun_ornek_kategorizasyon,
)
check(
    "UrunEslestirme-2 (KORUMA): related_product verilmeyince ticketProductId/relatedProduct payload'da hic olmamali",
    "ticketProductId" not in _urun_payload_bos and "relatedProduct" not in _urun_payload_bos,
    _urun_payload_bos.keys(),
)

# ==========================================================
# detect_priority_level: KIRILIM NE OLURSA OLSUN, mailde "acil"/"opsiyon"
# gecerse ticket'in Oncelik alani buna gore ayarlanmali (kullanici tarafindan
# bildirilen genel kural, main.py'de her mailde calistiriliyor).
# NOT: "ENGELLEYICI" oncelik seviyesinin CSM'deki tam uuid'i henuz bilinmiyor
# -- su an sadece TESPIT (detect_priority_level) hazir, csm_api.py'nin
# payload'a gercekten "Engelleyici" priorityLevel objesini gomebilmesi icin
# o uuid'in kullanicidan alinmasi bekleniyor.
# ==========================================================
check(
    "PriorityLevel-1: bare 'opsiyon' kelimesi -> OPSIYONLU (kirilimdan bagimsiz)",
    detect_priority_level("Faturamın kesilmesini rica ederim, opsiyon süremiz bugün doluyor.") == "OPSIYONLU",
    detect_priority_level("Faturamın kesilmesini rica ederim, opsiyon süremiz bugün doluyor."),
)
check(
    "PriorityLevel-2: bare 'acil' kelimesi -> ENGELLEYICI (kirilimdan bagimsiz)",
    detect_priority_level("Rezervasyonumu acil olarak iptal etmek istiyorum.") == "ENGELLEYICI",
    detect_priority_level("Rezervasyonumu acil olarak iptal etmek istiyorum."),
)
check(
    "PriorityLevel-3: hicbiri gecmiyorsa None",
    detect_priority_level("Rezervasyon tarihini değiştirmek istiyorum.") is None,
    detect_priority_level("Rezervasyon tarihini değiştirmek istiyorum."),
)
check(
    "PriorityLevel-4: hem 'acil' hem 'opsiyon' geciyorsa Engelleyici (daha yuksek aciliyet) kazanmali",
    detect_priority_level("Opsiyon süremiz doluyor, acil ilgilenir misiniz?") == "ENGELLEYICI",
    detect_priority_level("Opsiyon süremiz doluyor, acil ilgilenir misiniz?"),
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
