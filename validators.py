"""
Validators Module

Contains all validation functions for user data, Turkish ID numbers,
and email content validation.
"""

import re
from typing import Tuple, List
from config import PROFANITY_WORDS
from utils import normalize_turkish_characters


# Bazi mailler etiketin hemen ardindan parantez icinde ek not/ID biraktir
# (ör. "Ad Soyad (Şahıs Adı - 100054903): Bekir Oğuz"). Bu segmenti tum alan
# etiketlerinden sonra, ":" beklenmeden once opsiyonel olarak kabul ediyoruz;
# aksi halde etiket ile deger arasindaki parantez eslesmeyi kirar.
OPTIONAL_LABEL_ANNOTATION = r'(?:\s*\([^)]*\))?'


def _normalize_date_to_ddmmyyyy(date_str: str) -> str:
    """
    "21.08.2026" / "1.8.2026" / "21-08-2026" gibi metinden cikarilan tarihleri
    CSM'in tarih (date-picker) alaninin bekledigi "DD/MM/YYYY" formatina
    (sifirla doldurulmus, "/" ayiracli) cevirir. CSM, "21.08.2026" gibi nokta
    ayiracli bir deger aldiginda parse edemeyip alani BUGUNUN tarihine
    varsayilan olarak sifirliyordu (canli ortamda gozlemlendi -- metinde
    "21.08.2026" yaziyken ticket'ta "23/08/2026" -- yani o gunun tarihi --
    goruntulenmisti).
    """
    parts = re.split(r'[./-]', date_str.strip())
    if len(parts) != 3:
        return date_str.strip()
    day, month, year = parts
    if len(year) == 2:
        year = "20" + year
    return f"{day.zfill(2)}/{month.zfill(2)}/{year}"


def _is_placeholder_value(value: str) -> bool:
    normalized_value = normalize_turkish_characters(value).strip()
    return "buraya" in normalized_value or normalized_value in {"yaz", "girilmedi", "belirtilmedi"}


# Bazi mailler CSM alan adlarini/ID'lerini dogrudan referans olarak yaziyor,
# ornegin: "Şirket Adı - Şahıs Adı (100054902): Şahıs Adı" (bu satir aslinda
# hangi SECICI'nin secildigini belirtiyor, gercek isim degil -- gercek isim
# BIR SONRAKI satirda "Şahıs Adı (100054903): Bekir Oğuz Karagüney" olarak
# geliyor). Bu "etiket yankisi" degerleri gercek deger SANILMAMALI.
_LABEL_ECHO_VALUES = {
    "sahis adi", "sirket adi", "tc kimlik numarasi", "vergi kimlik numarasi",
    "vergi kimlik numarasi - tc kimlik numarasi",
    "vergi kimlik numarasi tc kimlik numarasi",
}


def _is_label_echo_value(value: str) -> bool:
    normalized_value = normalize_turkish_characters(value).strip()
    normalized_value = re.sub(r'\s+', ' ', normalized_value)
    return normalized_value in _LABEL_ECHO_VALUES


# "X adına" (X'in adina, X'in namına) kalibiyla yakalanan isim/unvan
# adaylarinin GERCEK bir ozel isim degil, jenerik bir kelime olmasini
# engeller (ör. "Şirket adına düzenlenecek..." cumlesindeki cIplak "Şirket").
_GENERIC_NAME_CANDIDATE_VALUES = {
    "sirket", "sirketimiz", "firma", "firmamiz", "kurum", "kurumumuz", "sahis"
}


def _is_generic_name_candidate(value: str) -> bool:
    normalized_value = normalize_turkish_characters(value).strip()
    normalized_value = re.sub(r'\s+', ' ', normalized_value)
    return normalized_value in _GENERIC_NAME_CANDIDATE_VALUES


def _find_real_match(pattern: str, text: str, flags: int = 0):
    """
    re.search gibi davranir, ancak yakalanan deger bir "etiket yankisi"
    (_is_label_echo_value) veya placeholder ise bu eslesmeyi atlayip bir
    SONRAKI eslesmeyi dener.
    """
    for match in re.finditer(pattern, text, flags):
        value = match.group(1)
        if not _is_label_echo_value(value):
            return match
    return None


def is_valid_turkish_id(id_number: str) -> bool:
    """
    Validate Turkish ID (TC Kimlik Numarası).
    
    Args:
        id_number: 11-digit Turkish ID number
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not re.match(r'^[1-9]\d{10}$', id_number):
        return False
    
    digits = [int(d) for d in id_number]
    
    # All digits cannot be the same
    if len(set(digits)) == 1:
        return False
    
    # Check first 10 digits against 11th digit
    d_sum1 = sum(digits[0:9:2])  # Digits at positions 1, 3, 5, 7, 9
    d_sum2 = sum(digits[1:8:2])  # Digits at positions 2, 4, 6, 8
    
    if (d_sum1 * 7 - d_sum2) % 10 != digits[9]:
        return False
    
    # Check first 10 digits sum against 11th digit
    if sum(digits[:10]) % 10 != digits[10]:
        return False
    
    return True


def is_valid_tax_id(tax_id: str) -> bool:
    """
    Validate Turkish Tax ID (VKN - Vergi Kimlik Numarası).
    
    Args:
        tax_id: 10-digit tax ID number
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not re.match(r'^\d{10}$', tax_id):
        return False
    
    # All digits cannot be the same
    if len(set(tax_id)) == 1:
        return False
    
    # Basic length and digit validation
    return True


def is_valid_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        bool: True if valid email format, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def contains_profanity(text: str) -> bool:
    """
    Check if text contains profanity or hate speech.
    
    Args:
        text: Text to check
        
    Returns:
        bool: True if profanity detected, False otherwise
    """
    normalized_text = normalize_turkish_characters(text)
    
    for word in PROFANITY_WORDS:
        normalized_word = normalize_turkish_characters(word)
        pattern = r'\b' + re.escape(normalized_word) + r'(?:lar|ler)?\b'
        if re.search(pattern, normalized_text):
            return True
    
    return False


def extract_invoice_attributes(
    text: str, 
    sender_email: str
) -> Tuple[List[dict], List[str]]:
    """
    Extract invoice-related attributes and identify missing fields.
    
    Args:
        text: Email body text containing invoice information
        sender_email: Sender's email address
        
    Returns:
        Tuple of (attributes_list, missing_fields_list)
    """
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    attribute_list = []
    missing_fields = []

    person_name_match = _find_real_match(
        r'(?:^\s*(?:[-*]\s+)?|\s)(?:şahıs\s*adı|sahis\s*adi|ad\s*soyad(?:ı|i)?|isim(?:i)?|mükellef)' + OPTIONAL_LABEL_ANNOTATION + r'\s*:\s*'
        r'\[?([a-zA-ZğüşıöçĞÜŞİÖÇ\s]+?)\]?(?=\s*(?:,\s*)?(?:vergi\s*kimlik|vkn|tc\s*kimlik|fatura\s*adresi|e-?posta)|\r?\n|$)',
        text,
        re.IGNORECASE | re.MULTILINE
    )
    # Not: "\s*:\s*" yerine "(?:\s*:\s*|\s+)" kullaniliyor -- boylece ":" olmadan,
    # duz cumle ("Şirket unvanımız Tatilbudur ... A.Ş., vergi kimlik...") formatinda
    # yazilmis mailler de yakalanabiliyor. Etiket koklerine "\w{0,4}" ile iyelik
    # eki toleransi eklendi (unvanı, unvanımız, firması gibi). _find_real_match
    # kullanildi: "Şirket Adı - Şahıs Adı (100054902): Şirket Adı" gibi etiket-
    # yankisi satirlar atlanip gercek deger satiri bulunuyor.
    # Not: "şirket adı"/"sirket adi" icin SUFFIX TOLERANSI EKLENMEDI --
    # "\w{0,4}" eklenseydi "Şirket adına düzenlenecek..." gibi dogal
    # cumlelerdeki "adina" (haline/adina, farkli bir dilbilgisi eki)
    # yanlislikla etiket sanilip gercek sirket adini eziyordu.
    # Not: yakalanan degerin BUYUK harfle baslamasi zorunlu -- "firma\w{0,4}"/
    # "ünvan\w{0,4}" koku serbest ek tolerensi tasidigindan, "... ünvanı
    # yanlış olduğu için red veriyoruz..." gibi duz cumlelerde "ünvan" kelimesi
    # etiket degil cumlenin oznesi olarak geciyor; buyuk harf sarti olmadan
    # regex sonraki virgule kadar TUM cumleyi yanlislikla deger saniyordu
    # (canli ortamda gozlemlendi). Gercek sirket adlari/unvanlar her zaman
    # ozel isim oldugundan buyuk harfle baslar.
    # Not: pattern'in tamaminda re.IGNORECASE aktif oldugundan, buyuk harf
    # sartini gercekten zorlamak icin (?-i:...) ile SADECE bu karakter
    # icin case-insensitive kapatiliyor -- aksi halde [A-Z...] IGNORECASE
    # altinda kucuk harfleri de kabul eder ve sart etkisiz kalirdi.
    _COMPANY_LABEL_ROOT = r'(?:şirket\s*adı|sirket\s*adi|firma\w{0,4}|ünvan\w{0,4}|unvan\w{0,4})(?!\s*-)' + OPTIONAL_LABEL_ANNOTATION
    _COMPANY_VALUE_CAPTURE = r'\[?((?-i:[A-ZÇĞİÖŞÜ])[^\r\n\],]+?)\]?(?=\s*,|\s+ve\s+(?:mail|e-?posta)|\s*(?:vergi\s*kimlik|vkn|tc\s*kimlik|fatura\s*adresi|e-?posta)|\r?\n|$)'
    # Once "Label: Value" (kolon zorunlu) denenir -- prefix'in colon-oncelenmis
    # olmasina bakilmaksizin, cunku kolon zorunlulugu tek basina "...): Şirket
    # Adı\nŞirket Adı (ID): GercekDeger" gibi etiket-yankisi satirlarinda,
    # yankinin KENDISI kok sanildiginda bile sonraki metinde HEMEN bir kolon
    # bulunamadigi icin (araya baska metin girdiginden) otomatik elenir.
    company_name_match = _find_real_match(
        r'(?:^\s*(?:[-*]\s+)?|\s)' + _COMPANY_LABEL_ROOT + r'\s*:\s*' + _COMPANY_VALUE_CAPTURE,
        text,
        re.IGNORECASE | re.MULTILINE
    )
    if not company_name_match:
        # Duz cumle (kolonsuz) yedek -- SADECE prefix colon-ile-ONCELENMEMISSE
        # ("(?<!:)\s") izin verilir; aksi halde ayni etiket-yankisi tuzagina
        # bare-whitespace ayiricisi uzerinden yeniden dusulur (canli ortamda
        # gozlemlendi: yanki metni kok sanilip bir sonraki satirin TAMAMI
        # kendi etiketiyle birlikte yanlislikla deger olarak yutuluyordu).
        company_name_match = _find_real_match(
            r'(?:^\s*(?:[-*]\s+)?|(?<!:)\s)' + _COMPANY_LABEL_ROOT + r'\s+' + _COMPANY_VALUE_CAPTURE,
            text,
            re.IGNORECASE | re.MULTILINE
        )

    person_name_value = person_name_match.group(1) if person_name_match else None
    company_name_value = company_name_match.group(1) if company_name_match else None

    if person_name_value is None and company_name_value is None:
        # Duz cumle fallback: etiket hic yok, isim/unvan dogrudan "... adına"
        # kalibiyla geciyor olabilir (ör. "Bekir Oğuz Karagüney adınadır",
        # "Tatilbudur Seyahat Acenteliği ve Turizm A.Ş. adına"). Sirket
        # gorunumlu mu (A.Ş./Ltd/Şti/Turizm/Seyahat gibi izler) yoksa kisi
        # ismi gibi mi karar verilir. Jenerik kelimeler ("Şirket adına
        # düzenlenecek..." gibi) _is_generic_name_candidate ile eleniyor.
        # Not: "ad[ıi]na" -- Turkce klavyesi olmayan gonderenler noktasiz "ı"
        # yerine duz ASCII "i" yazabiliyor ("Oguz Karaguney adina" gibi),
        # bu yuzden her iki yazim da kabul ediliyor. Sadece bu kelime icin
        # scoped (?i:...) case-insensitive -- pattern'in tamamina genel
        # re.IGNORECASE uygulanirsa, isim adayindaki "[A-ZÇĞİÖŞÜ]" buyuk harf
        # sarti da etkisiz kalir ve cumledeki daha erken bir kucuk harfli
        # kelimeden baslayarak yanlislikla cok daha genis/yanlis bir metin
        # yakalanir (canli hatada gozlemlendi).
        adina_match = _find_real_match(
            r'([A-ZÇĞİÖŞÜ][^\r\n,]{2,80}?)\s+(?i:ad[ıi]na)\w*',
            text,
            0
        )
        if adina_match and not _is_generic_name_candidate(adina_match.group(1)):
            candidate = adina_match.group(1).strip()
            if re.search(r'\b(?:A\.?Ş\.?|Ltd\.?|Şti\.?|Turizm|Seyahat|Acenteliği)\b', candidate, re.IGNORECASE):
                company_name_value = candidate
            else:
                person_name_value = candidate

    selected_type = None  # "person" | "company" | None -- TC/VKN tutarliligi icin

    if person_name_value is not None and not _is_placeholder_value(person_name_value):
        selected_type = "person"
        person_name = person_name_value.strip()
        attribute_list.append({
            "attribute": {
                "id": 100054902,
                "shortCode": "SIRKET_ADI_SAHIS_ADI"
            },
            "lovItem": {
                "id": 100054903,
                "name": "Şahıs Adı",
                "shortCode": "SAHIS_ADI"
            }
        })
        attribute_list.append({
            "attribute": {
                "id": 100000237,
                "shortCode": "SAHIS_ADI"
            },
            "textValue": person_name
        })
    elif company_name_value is not None:
        selected_type = "company"
        company_name = company_name_value.strip()
        attribute_list.append({
            "attribute": {
                "id": 100054902,
                "shortCode": "SIRKET_ADI_SAHIS_ADI"
            },
            "lovItem": {
                "id": 100000070,
                "name": "Şirket Adı",
                "shortCode": "SIRKET_ADI"
            }
        })
        attribute_list.append({
            "attribute": {
                "id": 100000238,
                "shortCode": "SIRKET_ADI"
            },
            "textValue": company_name
        })
    else:
        missing_fields.append("Şirket Adı veya Şahıs Adı")
    
    # Extract Turkish ID or Tax ID
    # Not: "numara\w*" ile "numaram", "numaramız", "numarası" gibi tum iyelik
    # eki varyasyonlari tek seferde kapsanıyor. "(?:'\w+)?" ile "TCKN'm" gibi
    # kesme isaretli iyelik ekleri de destekleniyor (":" olmadan duz cumle
    # formatinda bile "[:\s]*" zaten bosluk-tolerensli).
    tc_match = re.search(
        r'(?:tc|tckn|tc\s*no|tc\s*kimlik(?:\s*numara\w*)?|kimlik\s*no)(?:\'\w+)?' + OPTIONAL_LABEL_ANNOTATION + r'[:\s]*\[?(\d+)\]?',
        text,
        re.IGNORECASE
    )
    tax_match = re.search(
        r'(?:vkn|vergi\s*no|vergi\s*kimlik(?:\s*numara\w*)?)(?:\'\w+)?' + OPTIONAL_LABEL_ANNOTATION + r'[:\s]*\[?(\d+)\]?',
        text,
        re.IGNORECASE
    )

    # Not: Musteri onayiyla, secilen tur (Sahis/Sirket) ile ID turu (TC/VKN)
    # TUTARLI olmali -- Sahis secilmisse SADECE TC kabul edilir (VKN'e
    # dusulmez), Sirket secilmisse SADECE VKN kabul edilir. Tur belirsizse
    # (isim/unvan hic bulunamadiysa) eski genel davranis korunuyor.
    if selected_type == "person":
        tax_match = None
    elif selected_type == "company":
        tc_match = None

    if tc_match:
        tc_value = tc_match.group(1)
        if is_valid_turkish_id(tc_value):
            attribute_list.append({
                "attribute": {
                    "id": 100054901,
                    "shortCode": "VERGI_NUMARASI_TC_NUMARASI"
                },
                "lovItem": {
                    "id": 100054900,
                    "name": "TC Kimlik Numarası",
                    "shortCode": "TC_KIMLIK_NUMARASI"
                }
            })
            attribute_list.append({
                "attribute": {
                    "id": 100000236,
                    "shortCode": "TC_KIMLIK_NUMARASI"
                },
                "textValue": int(tc_value)
            })
        else:
            missing_fields.append("Lütfen geçerli bir TC Kimlik Numarası giriniz")
    elif tax_match:
        tax_value = tax_match.group(1)
        if is_valid_tax_id(tax_value):
            attribute_list.append({
                "attribute": {
                    "id": 100054901,
                    "shortCode": "VERGI_NUMARASI_TC_NUMARASI"
                },
                "lovItem": {
                    "id": 100000066,
                    "name": "Vergi Kimlik Numarası",
                    "shortCode": "VERGI_KIMLIK_NUMARASI"
                }
            })
            attribute_list.append({
                "attribute": {
                    "id": 100000235,
                    "shortCode": "VERGI_KIMLIK_NUMARASI"
                },
                "textValue": int(tax_value)
            })
        else:
            missing_fields.append("Lütfen geçerli bir Vergi Kimlik Numarası (VKN) giriniz")
    elif selected_type == "person":
        missing_fields.append("TC Kimlik Numarası")
    elif selected_type == "company":
        missing_fields.append("Vergi Kimlik Numarası (VKN)")
    else:
        missing_fields.append("TC Kimlik Numarası veya VKN")

    if tax_match:
        tax_office_match = re.search(
            r'(?:vergi\s*dairesi|vergi\s*daire\w{0,4})' + OPTIONAL_LABEL_ANNOTATION + r'(?:\s*:\s*|\s+)\[?([^\r\n\],]+?)\]?(?=\s*,|\s*(?:fatura\s*adresi|e-?posta)|\r?\n|$)',
            text,
            re.IGNORECASE
        )
        if not tax_office_match:
            # Duz cumle fallback: deger etiketten ONCE de gelebilir, ör.
            # "Zincirlikuyu Vergi Dairesi" (VKN'den hemen sonra, virgulle ayrilmis).
            tax_office_match = re.search(
                r'(?:,\s*|^\s*)([^\r\n,]+?)\s*vergi\s*daire\w{0,4}',
                text,
                re.IGNORECASE | re.MULTILINE
            )
        if tax_office_match and not _is_placeholder_value(tax_office_match.group(1)):
            attribute_list.append({
                "attribute": {
                    "id": 100000232,
                    "shortCode": "VERGI_DAIRESI"
                },
                "textValue": tax_office_match.group(1).strip()
            })
        else:
            missing_fields.append("Vergi Dairesi")
    
    # Extract invoice address - multiple pattern attempts for robustness
    address_match = None

    # Try pattern 0: deger etiketten ONCE de gelebilir, ör. "...Şişli/İstanbul
    # adresine ve X mail adresine..." (adres + e-posta ayni "adresine" kalibiyla
    # arka arkaya, ters sirali gecebiliyor). Bu kalip cok spesifik oldugu icin
    # once denenir.
    address_match = re.search(
        r'([^\r\n,]+?)\s+adresine\s+ve\b',
        text,
        re.IGNORECASE
    )

    # Try pattern 1: "Fatura Adresi:" followed by content until next field or line break
    # Not: bare virgul ("\s*,") KASITLI OLARAK stop noktasi olarak eklenmedi --
    # "Nişantaşı, İstanbul" gibi adresler zaten virgul iceriyor. Sadece "ve
    # mail/e-posta ..." baglaci (duz cumle formatinda son alan genelde "ve"
    # ile baglaniyor) veya sonraki alan etiketi durdurma noktasi sayiliyor.
    if not address_match:
        address_match = re.search(
        r'(?:fatura\s*adresi\w{0,4}|adres\w{0,4})' + OPTIONAL_LABEL_ANNOTATION + r'[:\s]*'
        r'([a-zA-ZğüşıöçĞÜŞİÖÇ0-9\s/.,:-]+?)(?=\s+ve\s+(?:fatura\s*mail|fatura\s*e-posta|mail|e-posta)|\s*,?\s*(?:fatura\s*mail|fatura\s*e-posta|mail|e-posta)|\r?\n\s*(?:fatura\s*mail|fatura\s*e-posta|mail|e-posta|iyi|saygılarla|$)|$)',
        text,
        re.IGNORECASE | re.MULTILINE
    )

    # Try pattern 2: Simple "Fatura Adresi:" with end of line
    if not address_match:
        address_match = re.search(
            r'(?:fatura\s*adresi\w{0,4}|adres\w{0,4})' + OPTIONAL_LABEL_ANNOTATION + r'[:\s]*([^\n]+)',
            text,
            re.IGNORECASE
        )

    # Try pattern 3: Capture multi-line address (handle line breaks)
    if not address_match:
        address_match = re.search(
            r'(?:fatura\s*adresi\w{0,4}|adres\w{0,4})' + OPTIONAL_LABEL_ANNOTATION + r'[:\s]*\n\s*(.+?)(?:\n\s*\n|\n\s*(?:fatura|mail|e-posta|tc|vkn))',
            text,
            re.IGNORECASE | re.DOTALL
        )
    
    if address_match:
        invoice_address = address_match.group(1).strip()
        # Remove email patterns that might be attached
        invoice_address = re.split(
            r'\s*(?:ve\s+)?(?:fatura\s*mail|fatura\s*e-posta|mail|e-posta).*',
            invoice_address,
            flags=re.IGNORECASE
        )[0].strip()
        
        # Ensure address is not empty and has reasonable length
        if invoice_address and len(invoice_address) > 5 and not _is_placeholder_value(invoice_address):
            attribute_list.append({
                "attribute": {
                    "id": 100000233,
                    "shortCode": "FATURA_ADRESI"
                },
                "textValue": invoice_address
            })
        else:
            missing_fields.append("Fatura Adresi")
    else:
        missing_fields.append("Fatura Adresi")
    
    # Extract email address
    # Not: "mail adresim", "e-posta adresimiz" gibi etiket ile deger arasina
    # giren ek kelimeyi de tolere ediyor -- degeri zaten "@" iceren gecerli bir
    # e-posta deseni belirledigi icin araya giren kelime riskli degil.
    email_match = re.search(
        r'(?:fatura\s*e-?posta|fatura\s*mail|e-?posta|mail)(?:\s*adres\w*)?' + OPTIONAL_LABEL_ANNOTATION + r'[:\s]*\[?'
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\]?',
        text,
        re.IGNORECASE
    )
    if not email_match:
        # Genel fallback: metinde herhangi bir yerde gecerli bir e-posta adresi
        # varsa (etiket eslesmese bile) onu yakala.
        email_match = re.search(
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            text
        )
    
    invoice_email = email_match.group(1) if email_match else sender_email
    if invoice_email:
        attribute_list.append({
            "attribute": {
                "id": 100000234,
                "shortCode": "E-_POSTA"
            },
            "textValue": invoice_email
        })
    
    return attribute_list, missing_fields


def extract_payment_attributes(text: str, required: bool = False) -> Tuple[List[dict], List[str]]:
    """
    Odeme ile ilgili attribute'lari (Islem Tarihi, Kartin Ilk 6/Son 4 Hanesi,
    Tutar, Siparis No) metinden cikarir.

    Args:
        text: E-posta govde metni
        required: True ise, bulunamayan her alan icin Turkce bir aciklama
            missing_fields listesine eklenir (ör. Odemenin Yansimamasi ve
            Iade Bilgisi kirilimlarinda bu 5 alan zorunlu tutuluyor). False
            ise (varsayilan) alanlar sessizce atlanir, missing_fields her
            zaman bos doner.

    Returns:
        Tuple[List[dict], List[str]]: (bulunan attribute'ler, eksik alanlar)
    """
    attribute_list = []
    missing_fields = []

    date_match = re.search(
        r'(?:işlem\s*tarihi|islem\s*tarihi)' + OPTIONAL_LABEL_ANNOTATION + r'[:\s]*\[?(\d{1,2}[./]\d{1,2}[./]\d{2,4})\]?',
        text,
        re.IGNORECASE
    )
    if not date_match:
        # Duz cumle fallback: "15.08.2026 tarihinde" gibi etiketsiz ifadeler
        date_match = re.search(r'(\d{1,2}[./]\d{1,2}[./]\d{4})\s*tarihinde', text, re.IGNORECASE)
    if date_match:
        attribute_list.append({
            "attribute": {
                "id": 100000037,
                "shortCode": "ISLEM_TARIHI"
            },
            "textValue": _normalize_date_to_ddmmyyyy(date_match.group(1))
        })
    elif required:
        missing_fields.append("İşlem Tarihi")

    # Musterilerin en sik kullandigi format: karti maskeleyerek "454360******1234"
    # seklinde yazmalari. Hem ilk-6 hem son-4 alanini TEK SEFERDE karsilar.
    masked_card_match = re.search(r'(\d{6})\*{2,}(\d{4})', text)

    card_first6_match = re.search(
        r'(?:kart(?:ı|i)n\s*ilk\s*6(?:\s*hane(?:si)?|\s*rakam(?:ı|i))?)' + OPTIONAL_LABEL_ANNOTATION + r'[:\s]*\[?(\d{6})\]?',
        text,
        re.IGNORECASE
    )
    if not card_first6_match:
        # Duz cumle fallback: "454360 ile başlayan ... kartımla" gibi ifadeler
        card_first6_match = re.search(r'(\d{6})\s+ile\s+ba[sş]la', text, re.IGNORECASE)
    card_first6_value = card_first6_match.group(1) if card_first6_match else None
    if card_first6_value is None and masked_card_match:
        card_first6_value = masked_card_match.group(1)
    if card_first6_value is not None:
        attribute_list.append({
            "attribute": {
                "id": 100000189,
                "shortCode": "KARTIN_ILK_6_RAKAMI"
            },
            "textValue": card_first6_value
        })
    elif required:
        missing_fields.append("Kartın İlk 6 Rakamı")

    card_last4_match = re.search(
        r'(?:kart(?:ı|i)n\s*son\s*4(?:\s*hane(?:si)?|\s*rakam(?:ı|i))?)' + OPTIONAL_LABEL_ANNOTATION + r'[:\s]*\[?(\d{4})\]?',
        text,
        re.IGNORECASE
    )
    if not card_last4_match:
        # Duz cumle fallback: "... 1234 ile biten kartımla" gibi ifadeler
        card_last4_match = re.search(r'(\d{4})\s+ile\s+bit', text, re.IGNORECASE)
    card_last4_value = card_last4_match.group(1) if card_last4_match else None
    if card_last4_value is None and masked_card_match:
        card_last4_value = masked_card_match.group(2)
    if card_last4_value is not None:
        attribute_list.append({
            "attribute": {
                "id": 100000190,
                "shortCode": "KARTIN_SON_4_RAKAMI"
            },
            "textValue": card_last4_value
        })
    elif required:
        missing_fields.append("Kartın Son 4 Rakamı")

    amount_match = re.search(
        r'(?:tutar)' + OPTIONAL_LABEL_ANNOTATION + r'[:\s]*\[?(\d+(?:[.,]\d+)?)\s*(?:tl|₺|try)?\]?',
        text,
        re.IGNORECASE
    )
    if not amount_match:
        # Duz cumle fallback: "12.500 TL tutarında bir ödeme" gibi ifadeler
        # (para birimi zorunlu -- aksi halde herhangi bir sayi yanlislikla
        # tutar sanilabilir).
        amount_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:tl|₺|try)\b', text, re.IGNORECASE)
    if amount_match:
        attribute_list.append({
            "attribute": {
                "id": 100000192,
                "shortCode": "TUTAR"
            },
            "textValue": amount_match.group(1).strip()
        })
    elif required:
        missing_fields.append("Tutar")

    # Not: yakalanan deger MUTLAKA bir rakamla BASLAMALI ("\d[A-Za-z0-9-]*") --
    # aksi halde etiketten sonra rakamsiz bir cumle gelirse (ör. "Sipariş
    # Numarası belirtilmemiştir"), sonraki kelimenin ASCII on eki yanlislikla
    # siparis numarasi saniliyordu (extract_reservation_number'da gorulen ayni
    # sinif hata, canli ortamda gozlemlendi).
    order_number_match = re.search(
        r'(?:sipariş\s*no|siparis\s*no|sipariş\s*numara\w*|siparis\s*numara\w*)' + OPTIONAL_LABEL_ANNOTATION + r'(?:\s*ise)?[:\s]*\[?(\d[A-Za-z0-9-]*)\]?',
        text,
        re.IGNORECASE
    )
    if not order_number_match:
        # Duz cumle fallback: sayi etiketten ONCE gelebilir, ör. "358109758
        # numaralı siparişim için..." veya "358109758 nolu rezervasyonum
        # için..." -- nesne kelimesi "siparis" ile SINIRLI DEGIL, gercek
        # musteri mailleri cogunlukla "rezervasyon" diyor (canli ortamda
        # gozlemlendi).
        order_number_match = re.search(
            r'(\d[A-Za-z0-9-]*)\s*(?:numaral[iı]|no[\'’]?lu)\s*(?:sipari[sş]\w*|rezervasyon\w*)',
            text,
            re.IGNORECASE
        )
    if order_number_match:
        attribute_list.append({
            "attribute": {
                "id": 100000194,
                "shortCode": "SIPARIS_NO"
            },
            "textValue": order_number_match.group(1).strip()
        })
    elif required:
        missing_fields.append("Sipariş No")

    return attribute_list, missing_fields


def extract_option_deadline(text: str) -> str | None:
    """
    Metinde bir "opsiyon süresi" (saat) geciyorsa onu HH:MM formatinda dondurur,
    yoksa None. Backoffice > Kaydırma > Operasyon Kaynaklı / Otel Kaynaklı
    kirilimlarinda kullanilir: CSM ticket'inda hem OPSIYON_SURESI (100000130)
    attribute'una hem de ticket'in Oncelik (priorityLevel) alaninin
    "Opsiyonlu" secilmesine karar vermek icin.

    NOT: Etiketli ("Opsiyon Süresi: 11:40"), araya kelime giren duz cumle
    ("opsiyon süresi bugün saat 18:40 itibariyla dolacaktır" -- canli ortamda
    gozlemlendi) ve ters sirali ("11:40'a kadar opsiyon") kaliplari
    destekleniyor.
    """
    # Not: "opsiyon süresi" ile saat degeri arasina "bugün saat"/"saat" gibi
    # kelimeler girebiliyor; "[^\d]{0,25}" ile en fazla 25 rakam-disi karakter
    # toleransi taniniyor (rakam gecmedigi icin bir sonraki farkli sayiya
    # atlama riski yok).
    match = re.search(
        r'opsiyon\s*s[uü]res?i[^\d]{0,25}(\d{1,2}[:.]\d{2})',
        text,
        re.IGNORECASE
    )
    if not match:
        # Duz cumle fallback: "saat 11:40'a kadar opsiyonlu/opsiyon" gibi
        # ifadeler -- saat degeri "opsiyon" kelimesinden ONCE gecebiliyor.
        match = re.search(
            r'(\d{1,2}[:.]\d{2})(?:[\'’]\w+)?\s*(?:kadar\s+)?opsiyon',
            text,
            re.IGNORECASE
        )
    if not match:
        return None
    return match.group(1).replace(".", ":")


def extract_reservation_number(text: str) -> str | None:
    """
    Mailde gecen rezervasyon/siparis numarasini GENEL AMACLI olarak cikarir.
    extract_payment_attributes icindeki SIPARIS_NO alaniyla benzer bir
    kalibi hedefler, ama o fonksiyon SADECE odeme/fatura kirilimlarinda
    cagiriliyor; bu fonksiyon ise ticket olusturulurken -- kirilim ne olursa
    olsun -- CSM/Etiya'dan ilgili urun kaydini (relatedProduct) cekebilmek
    icin HER mailde calistirilmak uzere main.py'de kullanilir (kullanici
    tarafindan bildirilen kural: "gelen mailde rez no var ise ürün kısmına
    girmemiz gerekiyor").
    """
    # Not: yakalanan deger MUTLAKA bir rakamla BASLAMALI ("\d[A-Za-z0-9-]*") --
    # aksi halde "Rezervasyon Numarası içermiyor" gibi rakamsiz cumlelerde,
    # etiketten sonraki kelimenin ASCII on eki ("i", "içermiyor" kelimesinden)
    # yanlislikla rezervasyon numarasi saniliyordu (canli ortamda gozlemlendi).
    match = re.search(
        r'(?:rezervasyon\s*no|rez\s*no|sipariş\s*no|siparis\s*no|'
        r'rezervasyon\s*numara\w*|sipariş\s*numara\w*|siparis\s*numara\w*)'
        + OPTIONAL_LABEL_ANNOTATION + r'(?:\s*ise)?[:\s]*\[?(\d[A-Za-z0-9-]*)\]?',
        text,
        re.IGNORECASE
    )
    if not match:
        # Duz cumle fallback: sayi etiketten ONCE gelebilir, ör. "358109758
        # numaralı siparişim için..." veya "358109758 nolu rezervasyonum
        # için...".
        match = re.search(
            r'(\d[A-Za-z0-9-]*)\s*(?:numaral[iı]|no[\'’]?lu)\s*(?:sipari[sş]\w*|rezervasyon\w*)',
            text,
            re.IGNORECASE
        )
    if not match:
        return None
    return match.group(1).strip()
