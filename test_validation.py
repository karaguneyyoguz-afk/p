# -*- coding: utf-8 -*-
"""
Kapsamli senaryo testi.
mail_processor.EmailCategorizer.categorize() icin tum siniflandirma dallarini,
oncelik/çakisma (precedence) durumlarini ve validators.py fonksiyonlarini
tek tek kontrol eder. Ag baglantisi (IMAP/SMTP/CSM API) gerektirmez.
"""

from mail_processor import EmailCategorizer
from validators import (
    contains_profanity,
    extract_invoice_attributes,
    is_valid_turkish_id,
    is_valid_tax_id,
    is_valid_email,
)

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

# Precedence testi: sadece "otobus" gecen ama bus-context kelimesi olmayan metin
# TRANSPORT_CHANGE_RIGHTS_KEYWORDS listesinde de "otobus" var; bus-context kosulu
# saglanmadigi icin bu OTOBUS dalina degil, DEGISIKLIK_HAKKI_SORGULAMA dalina dusmeli.
r = cat("", "Otobüs bileti fiyatını öğrenmek istiyorum.")
check(
    "Precedence-1: sadece 'otobus' -> DEGISIKLIK_HAKKI_SORGULAMA (OTOBUS dalina degil)",
    r["classification"] == "BILGI_ISTEK > ULASIM > DEGISIKLIK_HAKKI_SORGULAMA",
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

r = cat("", "Konfirme maili hala gelmedi, rezervasyon onayı gelmedi.")
check("Konfirme-1", r["classification"] == "BACKOFFICE_ISLEMLERI > KONFIRME > KONFIRME", r["classification"])

r = cat("", "Ödeme tipi değişikliği yapmak istiyorum.")
check("Degisiklik-OdemeTipi", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ODEME_TIPI_DEGISIKLIGI", r["classification"])

r = cat("", "Doğum tarihi değişikliği yapmam gerekiyor.")
check("Degisiklik-DogumTarihi", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DOGUM_TARIHI_DEGISIKLIGI", r["classification"])

r = cat("", "Ek hizmet eklemek istiyorum rezervasyonuma.")
check("Degisiklik-EkHizmetler", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > EK_HIZMETLER", r["classification"])

r = cat("", "İsim değişikliği yapmak istiyorum.")
check("Degisiklik-Isim", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ISIM_DEGISIKLIGI", r["classification"])

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

r = cat("", "Rezervasyon tarihini değiştirmek istiyorum.")
check("Degisiklik-Tarih", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TARIH_DEGISIKLIGI", r["classification"])

r = cat("", "Tur değişikliği istiyorum, başka tura geçmek istiyorum.")
check("Degisiklik-Tur", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TUR_DEGISIKLIGI", r["classification"])

r = cat("", "Ulaşım değişikliği istiyorum, ulaşım tipimi değiştirmek istiyorum.")
check("Degisiklik-Ulasim", r["classification"] == "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DEGISIKLIK_ULASIM", r["classification"])

r = cat("", "Odamı iptal etmek istiyorum.")
check("Iptal-Oda", r["classification"] == "BACKOFFICE_ISLEMLERI > IPTAL > ODA_IPTALI", r["classification"])

r = cat("", "İptal sigortası iptal etmek istiyorum.")
check("EkHizmet-IptalSigortasi", r["classification"] == "BACKOFFICE_ISLEMLERI > EK_HIZMET > IPTAL_SIGORTASI", r["classification"])

r = cat("", "Rezervasyonumu iptal etmek istiyorum, genel iptal talebi oluşturuyorum.")
check("Iptal-Talebi", r["classification"] == "BACKOFFICE_ISLEMLERI > IPTAL > IPTAL_TALEBI", r["classification"])

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

# ==========================================================
# 11) kirilim.md KAYNAKLI YENI DALLAR (Taslak)
# Bu blok, gercek CSM kirilim listesinin okunmasiyla eklendi.
# ==========================================================
r = cat("", "Evrak eksik olduğu için şikayetçiyim.")
check("Evrak-Sikayet-1", r["classification"] == "SIKAYET > EVRAK > EVRAK", r["classification"])

r = cat("", "Sözleşme metnini gönderir misiniz.")
check("Evrak-BI-Sozlesme", r["classification"] == "BILGI_ISTEK > EVRAK > SOZLESME", r["classification"])

r = cat("", "Vize kiti evraklarını ne zaman gönderiyorsunuz.")
check("Evrak-BI-VizeKiti", r["classification"] == "BILGI_ISTEK > EVRAK > VIZE_KITI", r["classification"])

r = cat("", "Rezervasyonumda değişiklik yapabilir miyim.")
check("Rezervasyon-BI-DegisiklikBilgi", r["classification"] == "BILGI_ISTEK > REZERVASYON > DEGISIKLIK_BILGI_TALEBI", r["classification"])

r = cat("", "İptal süreci hakkında bilgi almak istiyorum.")
check("Rezervasyon-BI-IptalSurecBilgi", r["classification"] == "BILGI_ISTEK > REZERVASYON > IPTAL_SUREC_BILGISI", r["classification"])

r = cat("", "İade ne zaman yapılır, iade süresi ne kadar.")
check("OdemeSistemleri-BI-IadeBilgisi", r["classification"] == "BILGI_ISTEK > ODEME_SISTEMLERI_KONULARI > IADE_BILGISI", r["classification"])

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

r = cat("", "Çağrı merkezinden kötü hizmet aldım, temsilci kaba davrandı.")
check("Sikayet-SatisSureci-CagriMerkezi", r["classification"] == "SIKAYET > SATIS_SURECI > CAGRI_MERKEZI", r["classification"])

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

# --- YENI BILINEN CAKISMALAR (kirilim.md sonrasi tespit edildi) ---
# "Tur Otobüs Şoför Bilgileri" (Bilgi-İstek > Evrak) ile mevcut ULASIM > OTOBUS
# kavramsal olarak neredeyse ayni konuyu (sofor iletisim bilgisi) kapsiyor.
# ULASIM > OTOBUS kontrolu kod akisinda cok daha erken oldugu icin bu yeni dala
# hicbir zaman ulasilamiyor.
r = cat("", "Otobüs şoförünün evraklarını paylaşır mısınız.")
check(
    "COLLISION-4: 'sofor evraklari' -> beklenen EVRAK>TUR_OTOBUS_SOFOR_BILGILERI ama ULASIM>OTOBUS dalina dusuyor",
    r["classification"] == "BILGI_ISTEK > EVRAK > TUR_OTOBUS_SOFOR_BILGILERI",
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
KNOWN_ISSUE_SCENARIOS = {14, 15, 23, 32}

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
    (14, "BILGI_ISTEK > EVRAK > TUR_OTOBUS_SOFOR_BILGILERI", "Turumuzda kullanılacak otobüsün şoförüne ait belgeleri paylaşabilir misiniz?"),
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

for num, expected, text in REALISTIC_SCENARIOS:
    r = cat("", text)
    label = f"Gercekci-{num}"
    if num in KNOWN_ISSUE_SCENARIOS:
        label += " (KNOWN ISSUE: otobus/transfer genel kelime cakismasi)"
    check(label, r["classification"] == expected, r["classification"])

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
