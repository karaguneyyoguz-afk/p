"""
Mail Processor Module

Handles email retrieval, parsing, and categorization for ticket routing.
"""

import imaplib
import email
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Tuple, Optional
from config import (
    EMAIL_USER, EMAIL_PASS, IMAP_SERVER,
    SMTP_SERVER, SMTP_PORT, CHANNEL_ID,
    TICKET_TYPE_THANK_YOU, TICKET_TYPE_COMPLAINT,
    TICKET_TYPE_INFO_REQUEST, TICKET_TYPE_RESERVATION,
    CATEGORY_THANK_YOU,
    CATEGORY_COMPLAINT, CATEGORY_FACILITY, CATEGORY_AGENCY,
    CATEGORY_ONLINE_OPERATIONS, CATEGORY_TRANSPORT,
    SUB_CATEGORY_THANK_YOU_GENERAL, SUB_CATEGORY_THANK_YOU_GUIDE,
    SUB_CATEGORY_THANK_YOU_CONSULTANT, SUB_CATEGORY_COMPLAINT_INVOICE,
    SUB_CATEGORY_COMPLAINT_DOCUMENT,
    CATEGORY_INVOICE, SUB_CATEGORY_GUEST_INVOICE, SUB_CATEGORY_INVOICE_MODIFICATION,
    SUB_CATEGORY_FACILITY_CONTACT, SUB_CATEGORY_AGENCY_CONTACT_INFORMATION,
    SUB_CATEGORY_MEMBERSHIP_PROCESSES, SUB_CATEGORY_TRANSPORT_CHANGE_RIGHTS,
    SUB_CATEGORY_TRANSPORT_BUS, SUB_CATEGORY_TRANSPORT_TICKET,
    SUB_CATEGORY_TRANSPORT_COMPLAINT_TRANSFER, SUB_CATEGORY_TRANSPORT_COMPLAINT_OTHER,
    CATEGORY_PAYMENT, CATEGORY_CONFIRMATION, CATEGORY_CHANGE,
    CATEGORY_CANCELLATION, CATEGORY_ADDITIONAL_SERVICE,
    CATEGORY_SHIFT, CATEGORY_OTHER_OPERATIONS,
    SUB_CATEGORY_PAYMENT_REFLECTION, SUB_CATEGORY_CONFIRMATION,
    SUB_CATEGORY_CHANGE_PAYMENT_TYPE, SUB_CATEGORY_CHANGE_BIRTH_DATE,
    SUB_CATEGORY_CHANGE_EXTRA_SERVICES, SUB_CATEGORY_CHANGE_NAME,
    SUB_CATEGORY_CHANGE_PERSON_ADD_REMOVE, SUB_CATEGORY_CHANGE_NOTE_ADD,
    SUB_CATEGORY_CHANGE_ROOM, SUB_CATEGORY_CHANGE_ROOM_TYPE,
    SUB_CATEGORY_CHANGE_HOTEL, SUB_CATEGORY_CHANGE_DATE,
    SUB_CATEGORY_CHANGE_TOUR, SUB_CATEGORY_CHANGE_TRANSPORT,
    SUB_CATEGORY_CHANGE_OTHER,
    SUB_CATEGORY_CHANGE_AIRPLANE_TICKET,
    SUB_CATEGORY_CANCELLATION_ROOM, SUB_CATEGORY_CANCELLATION_REQUEST,
    SUB_CATEGORY_CANCELLATION_AIRPLANE,
    SUB_CATEGORY_ADDITIONAL_CANCELLATION_INSURANCE,
    SUB_CATEGORY_SHIFT_HOTEL_BASED, SUB_CATEGORY_SHIFT_OPERATION_BASED,
    SUB_CATEGORY_OTHER_OPERATIONS_PAYMENT_COMPLETION,
    CATEGORY_DOCUMENT, SUB_CATEGORY_DOCUMENT_CONTRACT, SUB_CATEGORY_DOCUMENT_VISA_KIT,
    SUB_CATEGORY_DOCUMENT_BUS_DRIVER_INFO, SUB_CATEGORY_DOCUMENT_COMPLAINT,
    CATEGORY_RESERVATION_INFO, SUB_CATEGORY_RESERVATION_CHANGE_INFO,
    SUB_CATEGORY_RESERVATION_CANCELLATION_INFO, SUB_CATEGORY_RESERVATION_CONFIRMATION_INFO,
    CATEGORY_PAYMENT_SYSTEMS_INFO, SUB_CATEGORY_REFUND_INFO,
    CATEGORY_HOTEL, SUB_CATEGORY_HOTEL_OPERATION, SUB_CATEGORY_HOTEL_SERVICES,
    CATEGORY_AIRPLANE, SUB_CATEGORY_AIRLINE_CHANGE, SUB_CATEGORY_FLIGHT_TIME_CHANGE,
    SUB_CATEGORY_FLIGHT_CANCELLED,
    CATEGORY_COMPLAINT_INFO_REQUEST, SUB_CATEGORY_RESERVATION_PROCESS,
    CATEGORY_SALES_PROCESS, SUB_CATEGORY_CALL_CENTER,
    CATEGORY_TOUR_AND_GUIDE, SUB_CATEGORY_TOUR_COMPLAINT, SUB_CATEGORY_GUIDE_COMPLAINT,
    CATEGORY_REFUND, SUB_CATEGORY_REFUND_NOT_MADE,
    SUB_CATEGORY_REFUND_REQUEST_NOT_OPENED, SUB_CATEGORY_REFUND_NOT_REFLECTED,
    CATEGORY_PRICING, SUB_CATEGORY_BEST_PRICE_GUARANTEE, SUB_CATEGORY_PRICE_GENERAL,
    SUB_CATEGORY_PRICE_DROP, SUB_CATEGORY_PAYMENT_OBJECTION,
    SUB_CATEGORY_PAYMENT_COMPLAINT_BANK_OBJECTION, SUB_CATEGORY_PAYMENT_COMPLAINT_OVERCHARGE,
    SUB_CATEGORY_PAYMENT_COMPLAINT_CAMPAIGN, SUB_CATEGORY_PAYMENT_COMPLAINT_REFLECTION,
    SUB_CATEGORY_PAYMENT_COMPLAINT_PROVISION,
    MAIL_CHARSET_DEFAULT,
    MAIL_CHARSET_FALLBACK
)
from utils import (
    decode_email_header, extract_sender_info, 
    clean_subject_line, normalize_turkish_characters
)
from validators import (
    contains_profanity, extract_invoice_attributes, extract_payment_attributes,
    extract_option_deadline
)
from service_log import record_service_event


def _levenshtein_distance(a: str, b: str) -> int:
    """Iki metin arasindaki duzenleme (Levenshtein) mesafesini hesaplar."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current_row = [i] + [0] * len(b)
        for j, char_b in enumerate(b, 1):
            current_row[j] = min(
                previous_row[j] + 1,
                current_row[j - 1] + 1,
                previous_row[j - 1] + (char_a != char_b),
            )
        previous_row = current_row
    return previous_row[-1]


def _compress_repeated_chars(word: str) -> str:
    """"teşekkürrrr" gibi uzatilmis kelimelerde art arda 3+ tekrar eden
    karakterleri 2'ye indirir (mesela "kk" gibi gercek cift harfleri bozmadan)."""
    compressed = []
    for char in word:
        if len(compressed) >= 2 and compressed[-1] == char and compressed[-2] == char:
            continue
        compressed.append(char)
    return "".join(compressed)


def contains_thank_you_word(normalized_text: str) -> bool:
    """
    "Teşekkür" kelimesinin yazim hatali/uzatilmis varyasyonlarini (ör.
    "teşeğğküüüü", "teşkut") da yakalar. Once THANK_YOU_KEYWORDS listesindeki
    kesin ifadelere bakar; hicbiri eslesmezse metindeki her kelimeyi "tesekkur"
    koküne olan duzenleme mesafesine gore kontrol eder.
    """
    if any(keyword in normalized_text for keyword in EmailCategorizer.THANK_YOU_KEYWORDS):
        return True

    for word in re.findall(r"[a-zğüşıöç]+", normalized_text):
        if len(word) < 6:
            continue
        compressed = _compress_repeated_chars(word)
        if _levenshtein_distance(compressed, "tesekkur") <= 3:
            return True

    return False


class EmailProcessor:
    """Handles email retrieval and processing."""
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize email processor.
        
        Args:
            username: Email account username (uses env var if None)
            password: Email account password (uses env var if None)
        """
        self.username = username or EMAIL_USER
        self.password = password or EMAIL_PASS
        self.mail_connection = None
    
    def connect(self) -> None:
        """Establish IMAP connection to email server."""
        try:
            self.mail_connection = imaplib.IMAP4_SSL(IMAP_SERVER)
            self.mail_connection.login(self.username, self.password)
            self.mail_connection.select("inbox")
            print("✅ E-posta sunucusuna bağlandı")
            record_service_event("gmail_imap", "connect", "success", detail=self.username)
        except Exception as e:
            print(f"❌ E-posta bağlantı hatası: {e}")
            record_service_event("gmail_imap", "connect", "failed", detail=str(e))
            raise
    
    def disconnect(self) -> None:
        """Close IMAP connection."""
        if self.mail_connection:
            try:
                self.mail_connection.logout()
                print("✅ E-posta sunucusundan bağlantı kesildi")
            except Exception as e:
                print(f"⚠️ Bağlantı kesilirken hata: {e}")
    
    def get_unread_emails(self) -> List[bytes]:
        """
        Retrieve unread emails.
        
        Returns:
            List of email message IDs
        """
        status, messages = self.mail_connection.search(None, 'UNSEEN')
        email_ids = messages[0].split()
        return email_ids
    
    def get_recent_emails(self, count: int = 1) -> List[bytes]:
        """
        Retrieve recent emails when no unread emails exist.
        
        Args:
            count: Number of recent emails to retrieve
            
        Returns:
            List of email message IDs
        """
        status, all_messages = self.mail_connection.search(None, 'ALL')
        all_ids = all_messages[0].split()
        
        if all_ids:
            return all_ids[-count:]
        return []
    
    def fetch_email(self, email_id: bytes) -> Optional[email.message.Message]:
        """
        Fetch and parse a single email.
        
        Args:
            email_id: Email message ID
            
        Returns:
            Parsed email message object or None
        """
        try:
            status, msg_data = self.mail_connection.fetch(email_id, "(RFC822)")
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    return email.message_from_bytes(response_part[1])
        except Exception as e:
            print(f"❌ E-posta getirilirken hata: {e}")
        
        return None
    
    @staticmethod
    def extract_email_content(msg: email.message.Message) -> Tuple[str, str, str, str]:
        """
        Extract subject, sender info, and body from email message.
        
        Args:
            msg: Email message object
            
        Returns:
            Tuple of (subject, sender_email, sender_name, body)
        """
        subject = decode_email_header(msg["Subject"]) if msg["Subject"] else ""
        raw_from = msg.get("From", "")
        sender_email, sender_name = extract_sender_info(raw_from)
        
        body = ""
        if msg.is_multipart():
            # Extract first text/plain part (ignore attachments)
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    if "attachment" not in str(part.get("Content-Disposition", "")):
                        charset = part.get_content_charset() or MAIL_CHARSET_DEFAULT
                        try:
                            body = part.get_payload(decode=True).decode(charset, errors="ignore")
                        except Exception:
                            body = part.get_payload(decode=True).decode(MAIL_CHARSET_FALLBACK, errors="ignore")
                        break
        else:
            # Single part message
            charset = msg.get_content_charset() or MAIL_CHARSET_DEFAULT
            try:
                body = msg.get_payload(decode=True).decode(charset, errors="ignore")
            except Exception:
                body = msg.get_payload(decode=True).decode(MAIL_CHARSET_FALLBACK, errors="ignore")
        
        return subject, sender_email, sender_name, body


class EmailCategorizer:
    """Categorizes emails and determines ticket routing."""
    
    THANK_YOU_KEYWORDS = [
        "tesekkur", "tesekkurler", "tesekkur ederim", "sagol",
        "tsk", "tks", "tessskur", "tesegkur", "teskut", "tesegkurr"
    ]
    
    INVOICE_KEYWORDS = ["fatura", "efatura", "e-fatura"]

    INVOICE_MODIFICATION_KEYWORDS = [
        "degisiklik", "duzeltme", "revize", "onay",
        "yeniden duzenle", "yeniden kes", "bu bilgilere kes",
        "dogrusu bu sekildedir", "bilgilere kesil"
    ]

    INVOICE_CONTEXT_KEYWORDS = [
        "fatura", "efatura", "e-fatura", "vergi dairesi",
        "vergi kimlik no", "vergi no", "fatura unvani"
    ]

    INVOICE_COMPLAINT_KEYWORDS = [
        "magduriyet", "aksaklik", "sikayet", "merkeze bildir",
        "olumsuz etk", "red veriyoruz", "reddediyoruz", "yanitsiz",
        "geciktiril", "yasal hak", "yasal merci", "tuketici hak"
    ]

    AGENCY_KEYWORDS = ["acente", "acenteye", "acentesi", "acenta", "acentaya"]

    AGENCY_CONTACT_KEYWORDS = [
        "iletisim", "telefon", "numara", "ula", "ulas",
        "yanit alam", "geri donus", "erisim", "basvuru", "yonlendir"
    ]

    ONLINE_PROCESS_KEYWORDS = [
        "uyelik", "giris yap", "giris yapam", "web sayfa",
        "uygulama", "mobil uygulama", "rezervasyonlarim",
        "rezervasyon gorunmuyor", "rezervasyon gorun", "kesin rezervasyon bekliyor"
    ]

    # Not: bare "bilet" ve "otobus" kelimeleri bu listeden kasitli olarak
    # CIKARILDI -- "otobus" artik dogrudan ULASIM > OTOBUS kirilimina, bilet
    # bilgilendirme/teyit/guncelleme talepleri de ULASIM > BILET kirilimina ait
    # (asagida OTOBUS_TOPIC_KEYWORDS / TRANSPORT_TICKET_* listeleri). Kirilim
    # onceligi (musteri onayli): DEGISIKLIK_HAKKI_SORGULAMA > OTOBUS > BILET.
    TRANSPORT_CHANGE_RIGHTS_KEYWORDS = [
        "transfer", "no show", "noshow", "kendi imkanlariyla",
        "donus transferi", "transferin yapilmasi", "transfer degisikligi",
        "otelimizi tercih etmistir", "fiyat ve sartlarindan",
        "tarih degisikligi", "saat degisikligi",
        "degisiklik hakki", "ceza", "kesinti uygulan",
        "bilet iptal sartlari", "bilet degisim sartlari", "degisim sartlari",
        "tarih degistirebilir miyim", "kupon iade"
    ]

    OTOBUS_TOPIC_KEYWORDS = [
        "otobus", "peron", "koltuk", "otobus firmasi", "otobus seferi",
        "hareket saati", "otobus bileti"
    ]

    TRANSPORT_BUS_KEYWORDS = [
        "tur otobusu", "otobusun guzergahi", "otobusune bin",
        "otobusten bin", "otobus sofor", "tur rehberi",
        "rehberin iletisim", "soforun iletisim"
    ]

    GUIDE_KEYWORDS = ["rehber", "tur lideri"]

    CONSULTANT_KEYWORDS = [
        "danisman", "temsilci", "cagri merkezi", "telefondaki"
    ]

    # "Tesekkur" ile birlikte gecerse mailin aslinda bir talep/soru oldugunu,
    # sadece kibarlik amacli "tesekkurler" ile bittigini gosteren ifadeler.
    REQUEST_INDICATOR_KEYWORDS = [
        "miyim", "misiniz", "musunuz", "misin", "mısınız", "münüz", "misiniz",
        "istiyorum", "rica ederim", "alabilir miyim", "ogrenebilir miyim",
        "yapabilir miyim", "paylasabilir misiniz", "atabilir misiniz"
    ]

    # kirilim.md kaynakli gercek mail ornekleri uzerinden genisletildi (bilet
    # ulasmama sikayeti + uctan uca bilet bilgilendirme/teyit/guncelleme).
    TRANSPORT_TICKET_TOPIC_KEYWORDS = ["bilet", "e-bilet", "ucus", "pnr"]
    TRANSPORT_TICKET_EVENT_KEYWORDS = [
        "gelmedi", "dusmedi", "ulasmadi", "gonderilmedi", "numaram",
        "teyi", "kod", "guncelle", "detay", "eklen",
        "bilgilendirme", "ricadir", "rica ederiz", "kontrolunuz",
        "aciga alin", "pdf"
    ]

    # Not: "evrag" ayrica eklendi -- "evrak" iyelik eki alinca unsuz yumusamasi
    # ile "evragi"/"evragimiz"/"evragini" olur (k->g), "evrak" koku artik
    # metinde gecmez (Turkce dilbilgisi tuzagi, "degisiklik->degisikligi" ile
    # ayni sinif).
    DOCUMENT_TOPIC_KEYWORDS = ["evrak", "evrag", "belge"]
    DOCUMENT_COMPLAINT_EVENT_KEYWORDS = [
        "eksik", "hatali", "yanlis", "sikinti", "sorun",
        "gelmedi", "ulasmadi", "ulasmiyor", "gonderilmedi", "iletilme",
        "gecik", "teslim edilmedi", "magduriyet", "sikayetci", "aksakl"
    ]

    # ==========================================
    # REZERVASYON / BACKOFFICE İŞLEMLERİ ANAHTAR KELİMELERİ
    # KONU + NIYET ikili listeler halinde: bir mailin bu dala girmesi icin
    # ilgili KONU listesinden bir kelime VE ilgili NIYET listesinden bir kelime
    # birlikte gecmeli. Bu, tek bir uzun cumleyle birebir eslesme aramaktan
    # cok daha esnek ve gercek musteri ifadelerine dayanikli.
    # ==========================================
    # Not: bu listeler kok/govde (stem-benzeri) kisa parcalar iceriyor, tam cumle
    # degil -- boylece "degistirmek", "degistirebilir", "degistirilmesi",
    # "degisiklik", "degisikligi" gibi tum ceki'mleri tek bir "degistir" /
    # "degisiklik" kaydiyla yakalar. Python'daki `in` kontrolu alt-dize (substring)
    # aramasi oldugu icin bu yaklasim calisir.
    CHANGE_INTENT_KEYWORDS = [
        "degistir", "degisikli", "gecmek", "gecis yapmak", "cevirmek",
        "duzelt", "guncelle", "yanlis gir", "yanlis yaz", "hatali yaz",
        "eklettirmek", "eklemek isti", "ileri almak", "geri almak",
        "revizyon", "revize", "duzenle"
    ]

    # Not: bilinçli olarak "iptal etmek/ettirmek/edebilir/edelim/ediyoruz" gibi
    # ILERIYE DONUK talep bicimleriyle sinirli tutuluyor; "iptal ettigimiz",
    # "iptal ettik" gibi GECMISE DONUK/betimleyici ifadeleri KAPSAMIYOR --
    # aksi halde "iptal ettigimiz rezervasyonun iadesi ne zaman yapilir" gibi
    # bilgi-istek mailleri de yanlislikla Backoffice Iptal Talebi'ne dusebilirdi.
    CANCEL_INTENT_KEYWORDS = [
        "iptal etmek", "iptal ettirmek", "iptal edebilir", "iptal edelim",
        "iptal ediyoruz", "iptal talebi", "iptal edilmesini", "iptalini rica",
        "iptalini talep", "iptal islemi"
    ]

    # Not: "sikayetci" -> "sikayet" ve "aksama" -> "aksa" olarak genisletildi;
    # eski dar formlar "sikayetimin"/"aksaklik" gibi cok yaygin cekim
    # varyasyonlarini yakalayamiyordu (canli ortamda gozlemlendi).
    COMPLAINT_SENTIMENT_KEYWORDS = [
        "memnun degil", "sikayet", "kotu", "ilgisiz", "magdur ol", "magduriyet",
        "sorun yasa", "berbat", "yetersiz", "hayal kirikligi", "kaba", "aksa",
        "duzensiz", "karisti", "olumsuzluk"
    ]

    # Şikayet > Ulaşım > Transfer: "transfer" bare kelimesi hem bu dalda hem de
    # Bilgi-İstek > Ulaşım > Değişiklik Hakkı Sorgulama'da kullanildigi icin,
    # bu dal DAHA ONCE kontrol edilmeli (musteri onayli).
    TRANSPORT_COMPLAINT_TRANSFER_TOPIC_KEYWORDS = [
        "transfer", "havalimani karsilama", "vip arac", "soforun gelmemesi"
    ]

    # Şikayet > Ulaşım > Diğer: "ulasim" gecen ama transfer/otobus/ucak gibi
    # spesifik bir alt konu icermeyen genel ulasim sikayetleri icin catch-all.
    TRANSPORT_COMPLAINT_OTHER_TOPIC_KEYWORDS = ["ulasim"]
    TRANSPORT_COMPLAINT_SPECIFIC_EXCLUDE_KEYWORDS = ["otobus", "ucak", "transfer"]

    # Not: eskiden tam cumle kaliplariydi ("odeme yansimadi" gibi), gercek
    # mailde "tutar sisteminize yansimadi" / "kartimdan odeme cekilmesine
    # ragmen..." gibi dogal varyasyonlari yakalayamiyordu -- konu+olay ikili
    # listeye cevrildi (canli ortamda gozlemlendi).
    PAYMENT_REFLECTION_TOPIC_KEYWORDS = ["odeme", "tutar", "para"]
    PAYMENT_REFLECTION_EVENT_KEYWORDS = [
        "yansimadi", "cekilmesine ragmen", "gozukmuyor", "kayboldu",
        "sisteme yansimadi", "hesaba yansimadi", "olusmadi", "sistemde yok"
    ]

    # --- SIKAYET > ODEME_SISTEMLERI (5 kirilim) ---
    # Not: "banka" mecburi konu kelimesi olarak tutuldu -- SADECE "itiraz"
    # kelimesi zaten SIKAYET > FIYATLANDIRMA > ODEME_ITIRAZI (genel/banka
    # disi) dalini tetikliyor; "banka" sarti bu iki dali birbirinden ayirir.
    BANK_OBJECTION_TOPIC_KEYWORDS = ["banka"]
    BANK_OBJECTION_EVENT_KEYWORDS = [
        "itiraz", "chargeback", "bilgim disinda", "iznim disinda",
        "onaylamadigim", "haberim olmadan"
    ]

    OVERCHARGE_TOPIC_KEYWORDS = ["tutar", "kart", "odeme"]
    OVERCHARGE_EVENT_KEYWORDS = [
        "fazla cekil", "fazla odendi", "mukerrer cekim", "cift cekim",
        "fazladan cekil"
    ]

    CAMPAIGN_TOPIC_KEYWORDS = ["kampanya", "promosyon", "indirim"]
    CAMPAIGN_EVENT_KEYWORDS = [
        "uygulanma", "yansitilma", "yansimadi", "dusulmedi"
    ]

    PROVISION_TOPIC_KEYWORDS = ["provizyon"]
    PROVISION_EVENT_KEYWORDS = [
        "bloke", "kaldirilmadi", "cozulmedi", "kalkmadi", "dusmedi"
    ]

    CONFIRMATION_TOPIC_KEYWORDS = [
        "konfirme", "konfirmasyon", "rezervasyon onayi", "otel onayi", "kesinles"
    ]
    # Not: bare "sure" (RESERVATION_CONFIRMATION_INFO_EVENT_KEYWORDS, bilgi-istek
    # dali) kelimesi "surecinin" gibi kelimelerde de gectigi icin ("surec" ile
    # ayni Turkce koku), somut talep ifadeleri buraya eklenerek bu dalin ONCE
    # eslesmesi sagliyor -- boylece "...sürecinin tamamlanmasını rica eder..."
    # gibi gercek talep icerikli mailler yanlislikla bilgi-istek/konfirme
    # dalina dusmuyor.
    CONFIRMATION_ACTIONABLE_EVENT_KEYWORDS = [
        "gelmedi", "ulasmadi", "hala", "acil laz",
        "etmenizi", "etmesini", "islemi", "tamamlanmasini", "yapilmasini",
        "iletilmesini", "kesinlesti mi", "bilgisinin"
    ]

    PAYMENT_TYPE_TOPIC_KEYWORDS = [
        "odeme tipi", "taksit", "tek cekim", "kredi karti", "havale"
    ]

    BIRTH_DATE_TOPIC_KEYWORDS = ["dogum tarihi"]

    EXTRA_SERVICES_TOPIC_KEYWORDS = [
        "ek hizmet", "ekstra hizmet", "ekstra yatak", "transfer hizmeti"
    ]

    # Not: "adinda"/"adinin"/"isminde"/"isminin" gibi cekimli formlar da
    # eklendi (ör. "misafirin adında harf hatası", "adının güncellenmesi") --
    # bunlar "adres"/"adet" gibi kelimelerle CAKISMIYOR (ozel ek gerektiriyor).
    NAME_CHANGE_TOPIC_KEYWORDS = [
        "isim", "ad soyad", "soyadim", "adim yanlis",
        "adinda", "adinin", "isminde", "isminin"
    ]

    PERSON_ADD_REMOVE_TOPIC_KEYWORDS = [
        "kisi eklemek", "kisi cikarmak", "kisi ekleme", "kisi cikarma",
        "kisi sayisini", "bir kisi daha", "kisi daha eklemek"
    ]

    NOTE_ADD_TOPIC_KEYWORDS = ["not"]
    NOTE_ADD_EVENT_KEYWORDS = [
        "eklemek", "eklenmesini", "ekleyebilir", "dusurebilir", "dusmek", "ozel not"
    ]

    ROOM_TYPE_TOPIC_KEYWORDS = [
        "oda tipi", "suit odaya", "deluxe odaya", "deluxe oda"
    ]

    ROOM_TOPIC_KEYWORDS = ["oda", "odami", "odamizi", "odamiz"]

    HOTEL_CHANGE_TOPIC_KEYWORDS = [
        "otel degisikligi", "baska otele", "baska bir otele", "otelimi degistirmek",
        "yakinindaki baska bir otel"
    ]
    # "tesis" tek basina cok genel (CATEGORY_FACILITY / TESIS_ILETISIM ile
    # cakisir), bu yuzden CHANGE_INTENT_KEYWORDS veya "aktar" (aktarma/
    # aktarmak) ile ESLESTIRILEREK kullanilir, tek basina tetiklenmez.
    FACILITY_CHANGE_TOPIC_KEYWORDS = ["tesis"]

    RESERVATION_DATE_TOPIC_KEYWORDS = [
        "rezervasyon tarihi", "tatil tarihi", "tatil tarihlerimiz", "giris tarihi",
        "cikis tarihi", "konaklama tarihi"
    ]

    TOUR_CHANGE_TOPIC_KEYWORDS = [
        "tur degisikligi", "baska tura", "baska bir tura", "turu yerine"
    ]
    # "tur paketi/rotasi/programi" gibi genel bir "tur" nesnesi -- tek basina
    # bilgi-istek de olabilecegi icin (ör. "tur paketi hakkinda bilgi"),
    # CHANGE_INTENT_KEYWORDS veya "sec" (secmek) ile ESLESTIRILEREK kullanilir,
    # TOUR_CHANGE_TOPIC_KEYWORDS'un aksine tek basina tetiklenmez.
    TOUR_PACKAGE_TOPIC_KEYWORDS = ["tur paket", "tur rota", "tur program"]

    TRANSPORT_MODE_CHANGE_TOPIC_KEYWORDS = [
        "ulasim degisikligi", "ulasim tipimi", "ucakla gitmek yerine", "otobusle gitmek yerine"
    ]

    AIRPLANE_TICKET_TOPIC_KEYWORDS = [
        "ucak bileti", "ucak biletim", "ucak biletimiz", "ucak biletimizdeki"
    ]

    CANCELLATION_INSURANCE_TOPIC_KEYWORDS = [
        "iptal sigortasi", "seyahat sigortasi"
    ]

    SHIFT_EVENT_KEYWORDS = [
        "kaydirdi", "kaydirma", "kaydirildik", "kaydirilmis", "kaydirmis",
        "overbooking"
    ]
    SHIFT_HOTEL_BASED_TOPIC_KEYWORDS = ["otel"]
    SHIFT_OPERATION_BASED_TOPIC_KEYWORDS = ["operasyon"]

    PAYMENT_COMPLETION_TOPIC_KEYWORDS = [
        "bakiye", "kalan bakiye", "eksik odeme", "kalan odeme"
    ]

    PAYMENT_COMPLETION_INTENT_KEYWORDS = [
        "tamamlamak istiyoruz", "tamamlamak istiyorum", "odemesi yapmak istiyorum",
        "simdi tamamlamak", "tamamlayabilir miyiz"
    ]

    # ==========================================
    # BİLGİ-İSTEK - EVRAK ANAHTAR KELİMELERİ (Taslak)
    # ==========================================
    DOCUMENT_CONTRACT_KEYWORDS = [
        "sozlesme", "sozlesmemi", "sozlesme metni", "sozlesme kopyasi",
        "mesafeli satis sozlesmesi", "tur sozlesmesi", "islak imzali sozlesme",
        "iptal sartlari sozlesmesi", "satis sartlari"
    ]

    DOCUMENT_VISA_KIT_TOPIC_KEYWORDS = ["vize", "konsolosluk"]
    DOCUMENT_VISA_KIT_EVENT_KEYWORDS = [
        "kit", "evrak", "belge", "basvuru formu", "pasaport teslim"
    ]

    # Musteri onayli oncelik: bu dal ULASIM > OTOBUS kontrolunden ONCE
    # degerlendirilmeli, ama "sofor" bare kelimesi tek basina yeterli DEGIL --
    # onaylanan iki ornek ("Soforumuzun telefon numarasini iletir misiniz,
    # otobuse nereden binecegiz?" -> OTOBUS, ama "...soforun adini, telefon
    # numarasini ve plaka bilgilerini ogrenebilir miyim?" -> EVRAK) birbirinden
    # su sekilde ayriliyor: "plaka"/"kaptan" tek basina güçlü bir sinyal; "sofor"
    # ise ancak ISIM/AD talebiyle birlikte gecerse (sadece telefon/iletisim
    # sorulmasi degil) bu dala giriyor.
    DOCUMENT_BUS_DRIVER_INFO_STRONG_KEYWORDS = ["plaka", "kaptan"]
    DOCUMENT_BUS_DRIVER_INFO_NAME_REQUEST_KEYWORDS = [
        "adini", "ismini", "adi ve", "ismi ve", "kim oldugunu", "kimdir"
    ]

    # ==========================================
    # BİLGİ-İSTEK - REZERVASYON (bilgi amaçlı) ANAHTAR KELİMELERİ (Taslak)
    # ==========================================
    RESERVATION_CHANGE_INFO_KEYWORDS = [
        "degisiklik yapabilir miyim", "degisiklik yapilabilir mi",
        "degisiklik hakkinda bilgi almak istiyorum", "nasil degisiklik yapabilirim"
    ]

    RESERVATION_CANCELLATION_INFO_TOPIC_KEYWORDS = ["iptal"]
    # Not: bare "surec" kasitli olarak CIKARILDI -- "surec" cok genel bir kelime
    # oldugu icin, metnin baska bir yerinde alakasiz sekilde "iptal" gecen
    # mailler de (ör. "iade surecimin kontrolu" + ayrica bahsi gecen "daha once
    # iptal ettigim rezervasyon") yanlislikla bu dala takiliyordu.
    RESERVATION_CANCELLATION_INFO_EVENT_KEYWORDS = [
        "nasil", "kosul", "sart", "ne olur", "iptal sureci"
    ]

    RESERVATION_CONFIRMATION_INFO_EVENT_KEYWORDS = [
        "nedir", "ne zaman", "sure", "ulasir"
    ]

    # ==========================================
    # BİLGİ-İSTEK - ÖDEME SİSTEMLERİ KONULARI ANAHTAR KELİMELERİ (Taslak)
    # ==========================================
    REFUND_INFO_TOPIC_KEYWORDS = ["iade"]
    REFUND_INFO_EVENT_KEYWORDS = [
        "ne zaman", "kac gun", "nasil alinir", "ne kadar", "hesabimiza gecer",
        "hesabima gecer", "hakkinda bilgi", "konusunda bilgi", "ne asamada",
        "bilgi almak istiyorum", "bilgi talep ediyorum"
    ]

    # ==========================================
    # ŞİKAYET AĞACI ANAHTAR KELİMELERİ
    # Ayni KONU + NIYET/DUYGU mantigi: konu kelimesi VE bir sikayet/olay sinyali
    # birlikte arandigi icin gercek musteri ifadelerine cok daha dayanikli.
    # ==========================================
    HOTEL_OPERATION_TOPIC_KEYWORDS = [
        "resepsiyon", "check-in", "checkin", "check-out", "checkout", "otelin operasyon"
    ]

    HOTEL_SERVICES_TOPIC_KEYWORDS = [
        "oda temizligi", "temizlenmedi", "havuz", "yemek", "otel hizmet"
    ]

    AIRLINE_CHANGE_TOPIC_KEYWORDS = ["havayolu"]
    AIRLINE_CHANGE_EVENT_KEYWORDS = [
        "degisti", "degistirildi", "degisikligi yapildi", "farkli", "baska",
        "haber verilmeden", "habersiz"
    ]

    FLIGHT_TIME_TOPIC_KEYWORDS = [
        "ucus saati", "sefer saati", "kalkis saati", "ucus saatimiz"
    ]
    FLIGHT_TIME_EVENT_KEYWORDS = [
        "degisti", "degistirildi", "habersiz", "erteledi", "one alindi"
    ]

    FLIGHT_CANCELLED_TOPIC_KEYWORDS = [
        "seferimiz", "ucusumuz", "ucagimiz", "seferi", "ucusu"
    ]

    RESERVATION_PROCESS_TOPIC_KEYWORDS = [
        "rezervasyon islem", "rezervasyon yapilirken", "rezervasyon sirasinda"
    ]
    RESERVATION_PROCESS_EVENT_KEYWORDS = [
        "hata", "yanlis rezervasyon", "yanlis tarih girildi", "hatali yapildi"
    ]

    CALL_CENTER_TOPIC_KEYWORDS = [
        "cagri merkezi", "musteri hizmetleri", "temsilci", "danisman hattindan",
        "telefon gorusmesi", "telefonda soylenen", "telefonda aktarilan",
        "hatta bekletil"
    ]

    TOUR_TOPIC_KEYWORDS = ["tur program", "tur organizasyon"]

    GUIDE_COMPLAINT_TOPIC_KEYWORDS = ["rehber"]

    REFUND_TOPIC_KEYWORDS = ["iade"]

    REFUND_REQUEST_NOT_OPENED_EVENT_KEYWORDS = [
        "acilmamis", "olusturulmamis", "islenmemis", "isleme alinmamis",
        "kayit gorunmuyor", "hicbir kayit", "kayit yok"
    ]

    # Not: bare "yansima" kasitli olarak CIKARILDI -- "yansima durumu hakkinda
    # bilgi talep ediyorum" gibi notr bir bilgi talebiyle "hala yansimadi" gibi
    # gercek bir sikayeti ayirt edemiyordu (canli ortamda gozlemlendi). Sadece
    # acikca olumsuz/sikayet tonlu ifadeler birakildi.
    REFUND_NOT_REFLECTED_EVENT_KEYWORDS = [
        "yansimadi", "yansimiyor", "yansima goremiyorum", "yansima yok", "gorunmuyor"
    ]

    REFUND_NOT_MADE_EVENT_KEYWORDS = [
        "yapilmadi", "edilmedi", "almadim"
    ]

    BEST_PRICE_GUARANTEE_TOPIC_KEYWORDS = [
        "fiyat garantisi", "daha ucuz gordum", "baska sitede ucuz"
    ]

    PRICE_DROP_TOPIC_KEYWORDS = [
        "fiyat dustu", "fiyati dustu"
    ]

    PAYMENT_OBJECTION_TOPIC_KEYWORDS = ["odeme", "tutar", "kart"]
    PAYMENT_OBJECTION_EVENT_KEYWORDS = [
        "itiraz", "fazla cekildi", "yanlis tutar", "fazla odeme"
    ]

    PRICE_GENERAL_TOPIC_KEYWORDS = ["fiyat"]
    PRICE_GENERAL_EVENT_KEYWORDS = [
        "tutmuyor", "uyusmuyor", "farkli gosteriliyor", "yanlis hesaplanmis", "hatali gosterilmis"
    ]

    PAYMENT_OBJECTION_KEYWORDS = [
        "odemeye itiraz ediyorum", "yanlis tutar cekildi", "fazla odeme yapildi", "odeme itirazi"
    ]

    @staticmethod
    def categorize(subject: str, body: str, sender_email: str) -> Dict:
        """
        Categorize email and determine ticket type/category.
        
        Args:
            subject: Email subject line
            body: Email body content
            sender_email: Sender's email address
            
        Returns:
            Dictionary containing ticket categorization info
        """
        combined_text = f"{subject} {body}"
        normalized_text = normalize_turkish_characters(combined_text)

        # Not: Uçak bileti değişikliği/iptali kontrolleri kasıtlı olarak fonksiyonun
        # en başında yapılıyor. TRANSPORT_CHANGE_RIGHTS_KEYWORDS listesinde tek başına
        # "bilet" kelimesi geçiyor; bu daha genel kontrol aşağıda çalışırsa "uçak
        # biletimi değiştirmek/iptal etmek istiyorum" gibi somut, eylemsel talepler
        # hep genel "Ulaşım > Değişiklik Hakkı Sorgulama" bilgi-istek dalına düşerdi.
        # Somut/eylemsel Backoffice talepleri, genel bilgi-istek kontrolünden önce
        # değerlendirilmeli.
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.AIRPLANE_TICKET_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CANCEL_INTENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CANCELLATION,
                "category_name": "İptal",
                "sub_category_id": SUB_CATEGORY_CANCELLATION_AIRPLANE,
                "sub_category_name": "Uçak Bileti",
                "sub_category_code": "UCAK_BILETI_IPTALI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > IPTAL > UCAK_BILETI_IPTALI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.AIRPLANE_TICKET_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_AIRPLANE_TICKET,
                "sub_category_name": "Uçak Bileti Değişikliği",
                "sub_category_code": "UCAK_BILETI_DEGISIKLIGI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > UCAK_BILETI_DEGISIKLIGI"
            }

        # Not: Teşekkür tespiti KASITLI OLARAK burada, fonksiyonun çok başında
        # yapılıyor. Aşağıdaki Ulaşım kontrolünde "transfer"/"otobus" gibi genel
        # kelimeler var; bu yüzden "...transfer süreçlerinden çok memnun kaldık,
        # teşekkür ederim" gibi saf bir teşekkür maili, Teşekkür kontrolü sona
        # birakilirsa hep yanlislikla Ulasim dalina dusuyordu (canli ortamda
        # gozlemlendi). Talep/soru iceren mailler (has_request_marker) yine de
        # Teşekkür sayılmıyor, kendi asil kirilimina gidiyor.
        has_request_marker = "?" in combined_text or any(
            keyword in normalized_text for keyword in EmailCategorizer.REQUEST_INDICATOR_KEYWORDS
        )
        if contains_thank_you_word(normalized_text) and not has_request_marker:
            if any(kw in normalized_text for kw in EmailCategorizer.CONSULTANT_KEYWORDS):
                sub_category_id = SUB_CATEGORY_THANK_YOU_CONSULTANT
                sub_category_name = "Danışman Teşekkür"
                sub_category_code = "DANISMAN_TESEKKUR"
            elif any(kw in normalized_text for kw in EmailCategorizer.GUIDE_KEYWORDS):
                sub_category_id = SUB_CATEGORY_THANK_YOU_GUIDE
                sub_category_name = "Rehber Teşekkür"
                sub_category_code = "REHBER_TESEKKUR"
            else:
                sub_category_id = SUB_CATEGORY_THANK_YOU_GENERAL
                sub_category_name = "Genel Teşekkür"
                sub_category_code = "GENEL_TESEKKUR"

            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_THANK_YOU,
                "ticket_type_name": "Teşekkür",
                "category_id": CATEGORY_THANK_YOU,
                "category_name": "Teşekkür",
                "sub_category_id": sub_category_id,
                "sub_category_name": sub_category_name,
                "sub_category_code": sub_category_code,
                "attributes": [],
                "missing_fields": [],
                "classification": f"TESEKKUR > TESEKKUR > {sub_category_code}"
            }

        # Not: Musteri onayli oncelik -- "sofor/plaka/kaptan" gecen mailler,
        # genel ULASIM > OTOBUS kontrolunden ONCE bu dala yonlenmeli.
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.DOCUMENT_BUS_DRIVER_INFO_STRONG_KEYWORDS)
            or (
                "sofor" in normalized_text
                and any(keyword in normalized_text for keyword in EmailCategorizer.DOCUMENT_BUS_DRIVER_INFO_NAME_REQUEST_KEYWORDS)
            )
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_DOCUMENT,
                "category_name": "Evrak",
                "sub_category_id": SUB_CATEGORY_DOCUMENT_BUS_DRIVER_INFO,
                "sub_category_name": "Tur Otobüs Şoför Bilgileri",
                "sub_category_code": "TUR_OTOBUS_SOFOR_BILGILERI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BILGI_ISTEK > EVRAK > TUR_OTOBUS_SOFOR_BILGILERI"
            }

        # Musteri onayli oncelik: "transfer" + acik sikayet tonu (aksaklik,
        # magduriyet, sikayet vb.) gecen mailler, genel Bilgi-İstek > Ulaşım >
        # Değişiklik Hakkı Sorgulama kontrolunden ONCE Şikayet > Ulaşım >
        # Transfer'e yonlenmeli.
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_COMPLAINT_TRANSFER_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_TRANSPORT,
                "category_name": "Ulaşım",
                "sub_category_id": SUB_CATEGORY_TRANSPORT_COMPLAINT_TRANSFER,
                "sub_category_name": "Transfer",
                "sub_category_code": "TRANSFER",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > ULASIM > TRANSFER"
            }

        # Şikayet > Ulaşım > Diğer: "ulasim" + sikayet tonu var ama transfer/
        # otobus/ucak gibi spesifik bir alt konu YOK -- catch-all/yedek dal.
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_COMPLAINT_OTHER_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
            and not any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_COMPLAINT_SPECIFIC_EXCLUDE_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_TRANSPORT,
                "category_name": "Ulaşım",
                "sub_category_id": SUB_CATEGORY_TRANSPORT_COMPLAINT_OTHER,
                "sub_category_name": "Diğer",
                "sub_category_code": "DIGER",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > ULASIM > DIGER"
            }

        # Not: Musteri onayli oncelik sirasi -- DEGISIKLIK_HAKKI_SORGULAMA (ceza/
        # degisiklik hakki gecen mailler) > OTOBUS (otobus/peron/koltuk gecen
        # mailler) > BILET (genel bilet/PNR/e-bilet bilgilendirme talepleri).
        if any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_CHANGE_RIGHTS_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_TRANSPORT,
                "category_name": "Ulaşım",
                "sub_category_id": SUB_CATEGORY_TRANSPORT_CHANGE_RIGHTS,
                "sub_category_name": "Değişiklik Hakkı Sorgulama",
                "sub_category_code": "DEGISIKLIK_HAKKI_SORGULAMA",
                "attributes": [],
                "missing_fields": [],
                "classification": "BILGI_ISTEK > ULASIM > DEGISIKLIK_HAKKI_SORGULAMA"
            }

        if any(keyword in normalized_text for keyword in EmailCategorizer.OTOBUS_TOPIC_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_TRANSPORT,
                "category_name": "Ulaşım",
                "sub_category_id": SUB_CATEGORY_TRANSPORT_BUS,
                "sub_category_name": "Otobüs",
                "sub_category_code": "OTOBUS",
                "attributes": [],
                "missing_fields": [],
                "classification": "BILGI_ISTEK > ULASIM > OTOBUS"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_TICKET_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_TICKET_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_TRANSPORT,
                "category_name": "Ulaşım",
                "sub_category_id": SUB_CATEGORY_TRANSPORT_TICKET,
                "sub_category_name": "Bilet",
                "sub_category_code": "BILET",
                "attributes": [],
                "missing_fields": [],
                "classification": "BILGI_ISTEK > ULASIM > BILET"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.DOCUMENT_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.DOCUMENT_COMPLAINT_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_DOCUMENT,
                "category_name": "Evrak",
                "sub_category_id": SUB_CATEGORY_DOCUMENT_COMPLAINT,
                "sub_category_name": "Evrak",
                "sub_category_code": "EVRAK",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > EVRAK > EVRAK"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.INVOICE_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.INVOICE_COMPLAINT_KEYWORDS)
        ):
            attributes, missing_fields = extract_invoice_attributes(combined_text, sender_email)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_INVOICE,
                "category_name": "Fatura",
                "sub_category_id": SUB_CATEGORY_COMPLAINT_INVOICE,
                "sub_category_name": "Fatura Talebi ve Şikayetleri",
                "sub_category_code": "FATURA_TALEBI_SIKAYETLERI",
                "attributes": attributes,
                "missing_fields": missing_fields,
                "classification": "SIKAYET > FATURA > FATURA_TALEBI_SIKAYETLERI"
            }

        # ============================================================
        # ŞİKAYET AĞACI (kirilim.md kaynaklı, taslak)
        # ============================================================
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.HOTEL_OPERATION_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_HOTEL,
                "category_name": "Otel",
                "sub_category_id": SUB_CATEGORY_HOTEL_OPERATION,
                "sub_category_name": "Operasyon",
                "sub_category_code": "OPERASYON",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > OTEL > OPERASYON"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.HOTEL_SERVICES_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_HOTEL,
                "category_name": "Otel",
                "sub_category_id": SUB_CATEGORY_HOTEL_SERVICES,
                "sub_category_name": "Otel Hizmetleri",
                "sub_category_code": "OTEL_HIZMETLERI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > OTEL > OTEL_HIZMETLERI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.AIRLINE_CHANGE_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.AIRLINE_CHANGE_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_AIRPLANE,
                "category_name": "Uçak",
                "sub_category_id": SUB_CATEGORY_AIRLINE_CHANGE,
                "sub_category_name": "Havayolu Değişikliği",
                "sub_category_code": "HAVAYOLU_DEGISIKLIGI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > UCAK > HAVAYOLU_DEGISIKLIGI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.FLIGHT_TIME_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.FLIGHT_TIME_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_AIRPLANE,
                "category_name": "Uçak",
                "sub_category_id": SUB_CATEGORY_FLIGHT_TIME_CHANGE,
                "sub_category_name": "Saat Değişikliği",
                "sub_category_code": "SAAT_DEGISIKLIGI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > UCAK > SAAT_DEGISIKLIGI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.FLIGHT_CANCELLED_TOPIC_KEYWORDS)
            and "iptal" in normalized_text
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_AIRPLANE,
                "category_name": "Uçak",
                "sub_category_id": SUB_CATEGORY_FLIGHT_CANCELLED,
                "sub_category_name": "Sefer İptali",
                "sub_category_code": "SEFER_IPTALI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > UCAK > SEFER_IPTALI"
            }

        # ============================================================
        # SIKAYET > ODEME_SISTEMLERI (5 kirilim: Banka Itirazi, Fazla Cekim,
        # Kampanya Uygulama, Odemenin Yansimamasi, Provizyon)
        # Not: RESERVATION_PROCESS ve FIYATLANDIRMA > ODEME_ITIRAZI dallarindan
        # ONCE kontrol ediliyor -- aksi halde "itiraz" gibi genel kelimeler
        # veya "rezervasyon islemim" gibi genel ifadeler bu daha spesifik 5
        # kirilimdan ONCE devreye girip yanlis (daha az spesifik) dallara
        # yonlendirebilirdi.
        # ============================================================
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.BANK_OBJECTION_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.BANK_OBJECTION_EVENT_KEYWORDS)
        ):
            payment_attributes, payment_missing_fields = extract_payment_attributes(combined_text, required=False)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_PAYMENT,
                "category_name": "Ödeme Sistemleri",
                "sub_category_id": SUB_CATEGORY_PAYMENT_COMPLAINT_BANK_OBJECTION,
                "sub_category_name": "Banka İtirazı",
                "sub_category_code": "BANKA_ITIRAZI",
                "attributes": payment_attributes,
                "missing_fields": payment_missing_fields,
                "classification": "SIKAYET > ODEME_SISTEMLERI > BANKA_ITIRAZI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.OVERCHARGE_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.OVERCHARGE_EVENT_KEYWORDS)
        ):
            payment_attributes, payment_missing_fields = extract_payment_attributes(combined_text, required=False)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_PAYMENT,
                "category_name": "Ödeme Sistemleri",
                "sub_category_id": SUB_CATEGORY_PAYMENT_COMPLAINT_OVERCHARGE,
                "sub_category_name": "Fazla Çekim",
                "sub_category_code": "FAZLA_CEKIM",
                "attributes": payment_attributes,
                "missing_fields": payment_missing_fields,
                "classification": "SIKAYET > ODEME_SISTEMLERI > FAZLA_CEKIM"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.CAMPAIGN_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CAMPAIGN_EVENT_KEYWORDS)
        ):
            payment_attributes, payment_missing_fields = extract_payment_attributes(combined_text, required=False)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_PAYMENT,
                "category_name": "Ödeme Sistemleri",
                "sub_category_id": SUB_CATEGORY_PAYMENT_COMPLAINT_CAMPAIGN,
                "sub_category_name": "Kampanya Uygulama",
                "sub_category_code": "KAMPANYA_UYGULAMA",
                "attributes": payment_attributes,
                "missing_fields": payment_missing_fields,
                "classification": "SIKAYET > ODEME_SISTEMLERI > KAMPANYA_UYGULAMA"
            }

        # Not: Backoffice > Odeme > Odemenin Yansimamasi (ayni topic/event
        # listeleriyle) ile AYNI metin kalibini paylasiyor; ayirt edici
        # sinyal COMPLAINT_SENTIMENT_KEYWORDS (magduriyet/sikayetci vb.) --
        # varsa Sikayet, yoksa Backoffice (islemsel talep) sayiliyor.
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_REFLECTION_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_REFLECTION_EVENT_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            payment_attributes, payment_missing_fields = extract_payment_attributes(combined_text, required=False)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_PAYMENT,
                "category_name": "Ödeme Sistemleri",
                "sub_category_id": SUB_CATEGORY_PAYMENT_COMPLAINT_REFLECTION,
                "sub_category_name": "Ödemenin Yansımaması",
                "sub_category_code": "ODEMENIN_YANSIMAMASI",
                "attributes": payment_attributes,
                "missing_fields": payment_missing_fields,
                "classification": "SIKAYET > ODEME_SISTEMLERI > ODEMENIN_YANSIMAMASI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.PROVISION_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.PROVISION_EVENT_KEYWORDS)
        ):
            payment_attributes, payment_missing_fields = extract_payment_attributes(combined_text, required=False)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_PAYMENT,
                "category_name": "Ödeme Sistemleri",
                "sub_category_id": SUB_CATEGORY_PAYMENT_COMPLAINT_PROVISION,
                "sub_category_name": "Provizyon",
                "sub_category_code": "PROVIZYON",
                "attributes": payment_attributes,
                "missing_fields": payment_missing_fields,
                "classification": "SIKAYET > ODEME_SISTEMLERI > PROVIZYON"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.RESERVATION_PROCESS_TOPIC_KEYWORDS)
            and (
                any(keyword in normalized_text for keyword in EmailCategorizer.RESERVATION_PROCESS_EVENT_KEYWORDS)
                or any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
            )
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_COMPLAINT_INFO_REQUEST,
                "category_name": "Bilgi Talebi",
                "sub_category_id": SUB_CATEGORY_RESERVATION_PROCESS,
                "sub_category_name": "Rezervasyon İşlemi",
                "sub_category_code": "REZERVASYON_ISLEMI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > BILGI_TALEBI > REZERVASYON_ISLEMI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.CALL_CENTER_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_SALES_PROCESS,
                "category_name": "Satış Süreci",
                "sub_category_id": SUB_CATEGORY_CALL_CENTER,
                "sub_category_name": "Çağrı Merkezi",
                "sub_category_code": "CAGRI_MERKEZI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > SATIS_SURECI > CAGRI_MERKEZI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.TOUR_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_TOUR_AND_GUIDE,
                "category_name": "Tur Organizasyonu ve Rehber",
                "sub_category_id": SUB_CATEGORY_TOUR_COMPLAINT,
                "sub_category_name": "Tur",
                "sub_category_code": "TUR",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > TUR_ORGANIZASYONU_VE_REHBER > TUR"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.GUIDE_COMPLAINT_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_TOUR_AND_GUIDE,
                "category_name": "Tur Organizasyonu ve Rehber",
                "sub_category_id": SUB_CATEGORY_GUIDE_COMPLAINT,
                "sub_category_name": "Rehber",
                "sub_category_code": "REHBER",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > TUR_ORGANIZASYONU_VE_REHBER > REHBER"
            }

        # Not: FIYATLANDIRMA dallari (spesifik konu kelimeleri: "fiyat garantisi",
        # "fiyat dustu" vb.) IADE dallarindan ONCE kontrol ediliyor; aksi halde
        # "fiyat dustu ama iade edilmedi" gibi bir metin, cok daha genel olan
        # "iade" + "edilmedi" catch-all'ina takilip yanlislikla IADE dalina duserdi.
        if any(keyword in normalized_text for keyword in EmailCategorizer.BEST_PRICE_GUARANTEE_TOPIC_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_PRICING,
                "category_name": "Fiyatlandırma",
                "sub_category_id": SUB_CATEGORY_BEST_PRICE_GUARANTEE,
                "sub_category_name": "En İyi Fiyat Garantisi",
                "sub_category_code": "EN_IYI_FIYAT_GARANTISI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > FIYATLANDIRMA > EN_IYI_FIYAT_GARANTISI"
            }

        if any(keyword in normalized_text for keyword in EmailCategorizer.PRICE_DROP_TOPIC_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_PRICING,
                "category_name": "Fiyatlandırma",
                "sub_category_id": SUB_CATEGORY_PRICE_DROP,
                "sub_category_name": "Ürün Fiyat Düşüşü",
                "sub_category_code": "FIYAT_DUSUSU",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > FIYATLANDIRMA > FIYAT_DUSUSU"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_OBJECTION_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_OBJECTION_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_PRICING,
                "category_name": "Fiyatlandırma",
                "sub_category_id": SUB_CATEGORY_PAYMENT_OBJECTION,
                "sub_category_name": "Ödeme İtirazı",
                "sub_category_code": "ODEME_ITIRAZI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > FIYATLANDIRMA > ODEME_ITIRAZI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.PRICE_GENERAL_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.PRICE_GENERAL_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_PRICING,
                "category_name": "Fiyatlandırma",
                "sub_category_id": SUB_CATEGORY_PRICE_GENERAL,
                "sub_category_name": "Fiyat Genel",
                "sub_category_code": "FIYAT_GENEL",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > FIYATLANDIRMA > FIYAT_GENEL"
            }

        # Not: en spesifik IADE dallari (talep acilmamis, misafire yansimamasi) genel
        # "iade yapilmadi" catch-all'inden ONCE kontrol ediliyor.
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.REFUND_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.REFUND_REQUEST_NOT_OPENED_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_REFUND,
                "category_name": "İade",
                "sub_category_id": SUB_CATEGORY_REFUND_REQUEST_NOT_OPENED,
                "sub_category_name": "İade Talebinin Açılmamış Olması",
                "sub_category_code": "IADE_TALEBININ_ACILMAMIS_OLMASI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > IADE > IADE_TALEBININ_ACILMAMIS_OLMASI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.REFUND_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.REFUND_NOT_REFLECTED_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_REFUND,
                "category_name": "İade",
                "sub_category_id": SUB_CATEGORY_REFUND_NOT_REFLECTED,
                "sub_category_name": "İadenin Misafire Yansımaması",
                "sub_category_code": "IADENIN_MISAFIRE_YANSIMAMASI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > IADE > IADENIN_MISAFIRE_YANSIMAMASI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.REFUND_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.REFUND_NOT_MADE_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_REFUND,
                "category_name": "İade",
                "sub_category_id": SUB_CATEGORY_REFUND_NOT_MADE,
                "sub_category_name": "İadenin Yapılmaması",
                "sub_category_code": "IADENIN_YAPILMAMASI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > IADE > IADENIN_YAPILMAMASI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.INVOICE_CONTEXT_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.INVOICE_MODIFICATION_KEYWORDS)
        ):
            attributes, missing_fields = extract_invoice_attributes(combined_text, sender_email)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi İstek",
                "category_id": CATEGORY_INVOICE,
                "category_name": "Fatura",
                "sub_category_id": SUB_CATEGORY_INVOICE_MODIFICATION,
                "sub_category_name": "Fatura Bilgi Değişikliği",
                "sub_category_code": "FATURA_BILGI_DEGISIKLIGI",
                "attributes": attributes,
                "missing_fields": missing_fields,
                "classification": "BILGI_ISTEK > FATURA > FATURA_BILGI_DEGISIKLIGI"
            }

        if any(
            keyword in normalized_text
            for keyword in ["dogrusu bu sekildedir", "bilgilere kesilmesi rica"]
        ):
            attributes, missing_fields = extract_invoice_attributes(combined_text, sender_email)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi İstek",
                "category_id": CATEGORY_INVOICE,
                "category_name": "Fatura",
                "sub_category_id": SUB_CATEGORY_INVOICE_MODIFICATION,
                "sub_category_name": "Fatura Bilgi Değişikliği",
                "sub_category_code": "FATURA_BILGI_DEGISIKLIGI",
                "attributes": attributes,
                "missing_fields": missing_fields,
                "classification": "BILGI_ISTEK > FATURA > FATURA_BILGI_DEGISIKLIGI"
            }

        # Check for invoice requests
        if any(keyword in normalized_text for keyword in EmailCategorizer.INVOICE_KEYWORDS):
            attributes, missing_fields = extract_invoice_attributes(combined_text, sender_email)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi İstek",
                "category_id": CATEGORY_INVOICE,
                "category_name": "Fatura",
                "sub_category_id": SUB_CATEGORY_GUEST_INVOICE,
                "sub_category_name": "Misafir Faturası",
                "sub_category_code": "MISAFIR_FATURASI",
                "attributes": attributes,
                "missing_fields": missing_fields,
                "classification": "BILGI_ISTEK > FATURA > MISAFIR_FATURASI"
            }

        # ============================================================
        # BİLGİ-İSTEK > EVRAK (kirilim.md kaynaklı, taslak)
        # ============================================================
        if any(keyword in normalized_text for keyword in EmailCategorizer.DOCUMENT_CONTRACT_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_DOCUMENT,
                "category_name": "Evrak",
                "sub_category_id": SUB_CATEGORY_DOCUMENT_CONTRACT,
                "sub_category_name": "Sözleşme",
                "sub_category_code": "SOZLESME",
                "attributes": [],
                "missing_fields": [],
                "classification": "BILGI_ISTEK > EVRAK > SOZLESME"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.DOCUMENT_VISA_KIT_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.DOCUMENT_VISA_KIT_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_DOCUMENT,
                "category_name": "Evrak",
                "sub_category_id": SUB_CATEGORY_DOCUMENT_VISA_KIT,
                "sub_category_name": "Vize Kiti",
                "sub_category_code": "VIZE_KITI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BILGI_ISTEK > EVRAK > VIZE_KITI"
            }

        if any(keyword in normalized_text for keyword in EmailCategorizer.ONLINE_PROCESS_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_ONLINE_OPERATIONS,
                "category_name": "Online İşlemler",
                "sub_category_id": SUB_CATEGORY_MEMBERSHIP_PROCESSES,
                "sub_category_name": "Üyelik Süreçleri",
                "sub_category_code": "UYELIK_SURECLERI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BILGI_ISTEK > ONLINE_ISLEMLER > UYELIK_SURECLERI"
            }

        # ============================================================
        # REZERVASYON / BACKOFFICE İŞLEMLERİ
        # (Ödeme, Konfirme, Değişiklik, İptal, Ek Hizmet, Kaydırma, Diğer İşlemler)
        # ============================================================
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_REFLECTION_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_REFLECTION_EVENT_KEYWORDS)
        ):
            # Not: musteri onayiyla, Islem Tarihi/Kartin Ilk 6-Son 4 Rakami/
            # Tutar/Siparis No bu kirilimda ZORUNLU tutuluyor (once opsiyoneldi).
            payment_attributes, payment_missing_fields = extract_payment_attributes(combined_text, required=True)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_PAYMENT,
                "category_name": "Ödeme Sistemleri",
                "sub_category_id": SUB_CATEGORY_PAYMENT_REFLECTION,
                "sub_category_name": "Ödemenin Yansımaması",
                "sub_category_code": "ODEMENIN_YANSIMAMASI",
                "attributes": payment_attributes,
                "missing_fields": payment_missing_fields,
                "classification": "BACKOFFICE_ISLEMLERI > ODEME > ODEMENIN_YANSIMAMASI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.CONFIRMATION_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CONFIRMATION_ACTIONABLE_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CONFIRMATION,
                "category_name": "Konfirme",
                "sub_category_id": SUB_CATEGORY_CONFIRMATION,
                "sub_category_name": "Konfirme",
                "sub_category_code": "KONFIRME",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > KONFIRME > KONFIRME"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_TYPE_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_PAYMENT_TYPE,
                "sub_category_name": "Ödeme Tipi Değişikliği",
                "sub_category_code": "ODEME_TIPI_DEGISIKLIGI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ODEME_TIPI_DEGISIKLIGI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.BIRTH_DATE_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_BIRTH_DATE,
                "sub_category_name": "Doğum Tarihi Değişikliği",
                "sub_category_code": "DOGUM_TARIHI_DEGISIKLIGI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DOGUM_TARIHI_DEGISIKLIGI"
            }

        if any(keyword in normalized_text for keyword in EmailCategorizer.EXTRA_SERVICES_TOPIC_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_EXTRA_SERVICES,
                "sub_category_name": "Ek Hizmetler",
                "sub_category_code": "EK_HIZMETLER",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > EK_HIZMETLER"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.NAME_CHANGE_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_NAME,
                "sub_category_name": "İsim Değişikliği",
                "sub_category_code": "ISIM_DEGISIKLIGI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ISIM_DEGISIKLIGI"
            }

        if any(keyword in normalized_text for keyword in EmailCategorizer.PERSON_ADD_REMOVE_TOPIC_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_PERSON_ADD_REMOVE,
                "sub_category_name": "Kişi Ekleme/Çıkarma",
                "sub_category_code": "KISI_EKLEME_CIKARMA",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > KISI_EKLEME_CIKARMA"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.NOTE_ADD_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.NOTE_ADD_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_NOTE_ADD,
                "sub_category_name": "Not Ekleme Talebi",
                "sub_category_code": "NOT_EKLEME_TALEBI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > NOT_EKLEME_TALEBI"
            }

        # Not: "oda tipi" kontrolü, salt "oda" kontrolünden ÖNCE yapılıyor;
        # aksi halde "oda tipi değişikliği" metni de ODA dalına düşebilirdi.
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.ROOM_TYPE_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_ROOM_TYPE,
                "sub_category_name": "Oda Tipi Değişikliği",
                "sub_category_code": "ODA_TIPI_DEGISIKLIGI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ODA_TIPI_DEGISIKLIGI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.ROOM_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_ROOM,
                "sub_category_name": "Oda",
                "sub_category_code": "ODA",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > ODA"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.HOTEL_CHANGE_TOPIC_KEYWORDS)
            or (
                any(keyword in normalized_text for keyword in EmailCategorizer.FACILITY_CHANGE_TOPIC_KEYWORDS)
                and (
                    any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS)
                    or "aktar" in normalized_text
                )
            )
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_HOTEL,
                "sub_category_name": "Otel Değişikliği",
                "sub_category_code": "OTEL_DEGISIKLIGI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > OTEL_DEGISIKLIGI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.RESERVATION_DATE_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_DATE,
                "sub_category_name": "Tarih Değişikliği",
                "sub_category_code": "TARIH_DEGISIKLIGI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TARIH_DEGISIKLIGI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.TOUR_CHANGE_TOPIC_KEYWORDS)
            or (
                any(keyword in normalized_text for keyword in EmailCategorizer.TOUR_PACKAGE_TOPIC_KEYWORDS)
                and (
                    any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS)
                    or "sec" in normalized_text
                )
            )
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_TOUR,
                "sub_category_name": "Tur Değişikliği",
                "sub_category_code": "TUR_DEGISIKLIGI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > TUR_DEGISIKLIGI"
            }

        if any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_MODE_CHANGE_TOPIC_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_TRANSPORT,
                "sub_category_name": "Ulaşım",
                "sub_category_code": "DEGISIKLIK_ULASIM",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DEGISIKLIK_ULASIM"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.CANCELLATION_INSURANCE_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CANCEL_INTENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_ADDITIONAL_SERVICE,
                "category_name": "Ek Hizmet Ekleme/Çıkarma",
                "sub_category_id": SUB_CATEGORY_ADDITIONAL_CANCELLATION_INSURANCE,
                "sub_category_name": "İptal Sigortası",
                "sub_category_code": "IPTAL_SIGORTASI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > EK_HIZMET > IPTAL_SIGORTASI"
            }

        # Not: oda iptali kontrolu, genel "İptal Talebi" kontrolünden ÖNCE yapılıyor;
        # aksi halde "iptal etmek istiyoruz" gibi genel bir ifade her oda iptalini de
        # yakalayip yanlis (daha az spesifik) alt kirilima yonlendirebilirdi.
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.ROOM_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CANCEL_INTENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CANCELLATION,
                "category_name": "İptal",
                "sub_category_id": SUB_CATEGORY_CANCELLATION_ROOM,
                "sub_category_name": "Oda",
                "sub_category_code": "ODA_IPTALI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > IPTAL > ODA_IPTALI"
            }

        if any(keyword in normalized_text for keyword in EmailCategorizer.CANCEL_INTENT_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CANCELLATION,
                "category_name": "İptal",
                "sub_category_id": SUB_CATEGORY_CANCELLATION_REQUEST,
                "sub_category_name": "İptal Talebi",
                "sub_category_code": "IPTAL_TALEBI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > IPTAL > IPTAL_TALEBI"
            }

        # Not: "operasyon" konu kelimesi "otel" konu kelimesinden ÖNCE kontrol
        # ediliyor; kaydirma her zaman bir otele yapildigi icin "otel" kelimesi
        # OPERASYON_KAYNAKLI mailerde de gecebiliyor ("...bizi otele kaydirdi"),
        # bu yuzden daha ayirt edici olan "operasyon" sinyali once degerlendirilmeli.
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.SHIFT_OPERATION_BASED_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.SHIFT_EVENT_KEYWORDS)
        ):
            # Not: mailde "opsiyon suresi" gecerse hem OPSIYON_SURESI (100000130)
            # attribute'u eklenir, hem de ticket'in Oncelik alaninin "Opsiyonlu"
            # secilmesi icin priority_level isaretlenir (csm_api.py bunu okuyup
            # priorityLevel objesini secer).
            option_deadline = extract_option_deadline(combined_text)
            shift_attributes = []
            shift_result = {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_SHIFT,
                "category_name": "Kaydırma",
                "sub_category_id": SUB_CATEGORY_SHIFT_OPERATION_BASED,
                "sub_category_name": "Operasyon Kaynaklı",
                "sub_category_code": "OPERASYON_KAYNAKLI",
                "attributes": shift_attributes,
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > KAYDIRMA > OPERASYON_KAYNAKLI"
            }
            if option_deadline:
                shift_attributes.append({
                    "attribute": {
                        "id": 100000130,
                        "shortCode": "OPSIYON_SURESI"
                    },
                    "textValue": option_deadline
                })
                shift_result["priority_level"] = "OPSIYONLU"
            return shift_result

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.SHIFT_HOTEL_BASED_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.SHIFT_EVENT_KEYWORDS)
        ):
            option_deadline = extract_option_deadline(combined_text)
            shift_attributes = []
            shift_result = {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_SHIFT,
                "category_name": "Kaydırma",
                "sub_category_id": SUB_CATEGORY_SHIFT_HOTEL_BASED,
                "sub_category_name": "Otel Kaynaklı",
                "sub_category_code": "OTEL_KAYNAKLI",
                "attributes": shift_attributes,
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > KAYDIRMA > OTEL_KAYNAKLI"
            }
            if option_deadline:
                shift_attributes.append({
                    "attribute": {
                        "id": 100000130,
                        "shortCode": "OPSIYON_SURESI"
                    },
                    "textValue": option_deadline
                })
                shift_result["priority_level"] = "OPSIYONLU"
            return shift_result

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_COMPLETION_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_COMPLETION_INTENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_OTHER_OPERATIONS,
                "category_name": "Diğer İşlemler",
                "sub_category_id": SUB_CATEGORY_OTHER_OPERATIONS_PAYMENT_COMPLETION,
                "sub_category_name": "Ödeme Tamamlama",
                "sub_category_code": "ODEME_TAMAMLAMA",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DIGER_ISLEMLER > ODEME_TAMAMLAMA"
            }

        # ============================================================
        # BİLGİ-İSTEK > REZERVASYON (islem yapmadan, sadece bilgi soran mailler)
        # Backoffice > Değişiklik/İptal/Konfirme dallarından FARKLI: burada müşteri
        # somut bir işlem talep etmiyor, süreç hakkında soru soruyor.
        # ============================================================
        if any(keyword in normalized_text for keyword in EmailCategorizer.RESERVATION_CHANGE_INFO_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_RESERVATION_INFO,
                "category_name": "Rezervasyon",
                "sub_category_id": SUB_CATEGORY_RESERVATION_CHANGE_INFO,
                "sub_category_name": "Değişiklik Bilgi Talebi",
                "sub_category_code": "DEGISIKLIK_BILGI_TALEBI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BILGI_ISTEK > REZERVASYON > DEGISIKLIK_BILGI_TALEBI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.RESERVATION_CANCELLATION_INFO_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.RESERVATION_CANCELLATION_INFO_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_RESERVATION_INFO,
                "category_name": "Rezervasyon",
                "sub_category_id": SUB_CATEGORY_RESERVATION_CANCELLATION_INFO,
                "sub_category_name": "İptal Süreç Bilgisi",
                "sub_category_code": "IPTAL_SUREC_BILGISI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BILGI_ISTEK > REZERVASYON > IPTAL_SUREC_BILGISI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.CONFIRMATION_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.RESERVATION_CONFIRMATION_INFO_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_RESERVATION_INFO,
                "category_name": "Rezervasyon",
                "sub_category_id": SUB_CATEGORY_RESERVATION_CONFIRMATION_INFO,
                "sub_category_name": "Konfirme",
                "sub_category_code": "KONFIRME",
                "attributes": [],
                "missing_fields": [],
                "classification": "BILGI_ISTEK > REZERVASYON > KONFIRME"
            }

        # ============================================================
        # BİLGİ-İSTEK > ÖDEME SİSTEMLERİ KONULARI
        # ============================================================
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.REFUND_INFO_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.REFUND_INFO_EVENT_KEYWORDS)
        ):
            # Not: musteri onayiyla, Islem Tarihi/Kartin Ilk 6-Son 4 Rakami/
            # Tutar/Siparis No bu kirilimda ZORUNLU tutuluyor (once opsiyoneldi).
            payment_attributes, payment_missing_fields = extract_payment_attributes(combined_text, required=True)
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_PAYMENT_SYSTEMS_INFO,
                "category_name": "Ödeme Sistemleri Konuları",
                "sub_category_id": SUB_CATEGORY_REFUND_INFO,
                "sub_category_name": "İade Bilgisi",
                "sub_category_code": "IADE_BILGISI",
                "attributes": payment_attributes,
                "missing_fields": payment_missing_fields,
                "classification": "BILGI_ISTEK > ODEME_SISTEMLERI_KONULARI > IADE_BILGISI"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.AGENCY_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.AGENCY_CONTACT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
                "ticket_type_name": "Bilgi-İstek",
                "category_id": CATEGORY_AGENCY,
                "category_name": "Acente",
                "sub_category_id": SUB_CATEGORY_AGENCY_CONTACT_INFORMATION,
                "sub_category_name": "İletişim Bilgileri",
                "sub_category_code": "ILETISIM_BILGILERI",
                "attributes": [],
                "missing_fields": [],
                "classification": "BILGI_ISTEK > ACENTE > ILETISIM_BILGILERI"
            }

        # "Diger" (coplukutusu): tarih/oda/isim/dogum tarihi/odeme tipi/otel/
        # tur/ulasim gibi SPESIFIK degisiklik dallarinin, ayrica IPTAL_TALEBI
        # ve TUM Bilgi-Istek dallarinin (ozellikle "degisiklik yapabilir
        # miyim?" gibi SORU formundaki DEGISIKLIK_BILGI_TALEBI) HICBIRINE
        # uymayan ama genel bir "degisiklik/revizyon" niyeti tasiyan mailler
        # icin SON CARE fallback. Bilerek fonksiyonun EN SONUNA, varsayilan
        # TESIS_ILETISIM donusunden hemen once yerlestirildi -- daha erken bir
        # konuma alinirsa (ör. Backoffice > Degisiklik blogunun hemen
        # sonunda), "degisiklik" kelimesinin SADECE baglamsal olarak gectigi
        # ama asil niyeti FARKLI olan mailleri (ör. "iptal edilmesini talep
        # ediyoruz" + baglamsal "ani degisiklik nedeniyle" ifadesi, veya soru
        # formundaki bilgi-istek talepleri) yanlislikla once yakaliyordu
        # (canli ortamda gozlemlendi, denendi).
        if any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_RESERVATION,
                "ticket_type_name": "Backoffice İşlemleri",
                "category_id": CATEGORY_CHANGE,
                "category_name": "Değişiklik",
                "sub_category_id": SUB_CATEGORY_CHANGE_OTHER,
                "sub_category_name": "Diğer",
                "sub_category_code": "DIGER",
                "attributes": [],
                "missing_fields": [],
                "classification": "BACKOFFICE_ISLEMLERI > DEGISIKLIK > DIGER"
            }

        # Default: General information request
        return {
            "channel_id": CHANNEL_ID,
            "ticket_type_id": TICKET_TYPE_INFO_REQUEST,
            "ticket_type_name": "Bilgi-İstek",
            "category_id": CATEGORY_FACILITY,
            "category_name": "Tesis",
            "sub_category_id": SUB_CATEGORY_FACILITY_CONTACT,
            "sub_category_name": "Tesis İletişim",
            "sub_category_code": "TESIS_ILETISIM",
            "attributes": [],
            "missing_fields": [],
            "classification": "BILGI_ISTEK > TESIS > TESIS_ILETISIM"
        }


def send_notification_email(recipient_email: str, subject: str, body: str) -> None:
    """
    Send automatic notification email to recipient.
    
    Args:
        recipient_email: Recipient email address
        subject: Email subject
        body: Email body (notification message)
    """
    try:
        message = MIMEMultipart()
        message['From'] = EMAIL_USER
        message['To'] = recipient_email
        message['Subject'] = f"Re: {subject} - BİLDİRİM: Talebiniz İşleme Alınamadı"
        
        formatted_body = f"Sayın Müşterimiz,\n\n{body}\n\nSaygılarımızla."
        message.attach(MIMEText(formatted_body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, recipient_email, message.as_string())
        server.quit()
        
        print(f"✉️ [BİLDİRİM MAİLİ GÖNDERİLDİ] -> {recipient_email}")
    
    except Exception as e:
        print(f"❌ Bildirim maili gönderilirken hata: {e}")


def send_ticket_confirmation_email(recipient_email: str, subject: str, ticket_id: str, customer_name: str) -> None:
    """
    Send ticket confirmation email to customer.
    
    Args:
        recipient_email: Recipient email address
        subject: Original email subject
        ticket_id: Ticket ID created in CSM
        customer_name: Customer name
    """
    try:
        message = MIMEMultipart()
        message['From'] = EMAIL_USER
        message['To'] = recipient_email
        message['Subject'] = f"Re: {subject} - Talebiniz Başarıyla Oluşturulmuştur (#{ticket_id})"
        
        formatted_body = (
            f"Sayın {customer_name},\n\n"
            f"Talebiniz sistemimizde başarıyla oluşturulmuştur.\n\n"
            f"🎫 Ticket No: #{ticket_id}\n"
            f"📝 Konu: {subject}\n"
            f"📅 Oluşturma Tarihi: Bugün\n\n"
            f"Bu ticket numarasını kullanarak talebinizin durumunu izleyebilirsiniz.\n\n"
            f"Talebiniz en kısa zamanda değerlendirilecektir.\n\n"
            f"Saygılarımızla,\n"
            f"Müşteri Hizmetleri Ekibi"
        )
        message.attach(MIMEText(formatted_body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, recipient_email, message.as_string())
        server.quit()
        
        print(f"✉️ [TICKET ONAY MAİLİ GÖNDERİLDİ] Ticket #{ticket_id} -> {recipient_email}")
    
    except Exception as e:
        print(f"❌ Ticket onay maili gönderilirken hata: {e}")


def send_rejection_email(recipient_email: str, subject: str, customer_name: str) -> None:
    """
    Send rejection email for inappropriate/hateful content.
    
    Args:
        recipient_email: Recipient email address
        subject: Original email subject
        customer_name: Customer name
    """
    try:
        message = MIMEMultipart()
        message['From'] = EMAIL_USER
        message['To'] = recipient_email
        message['Subject'] = f"Re: {subject} - Talebiniz İşleme Alınamadı"
        
        formatted_body = (
            f"Sayın {customer_name},\n\n"
            f"E-postanız incelenmiş olup, talebiniz işleme alınamıştır.\n\n"
            f"❌ Neden: Mesajınız uygunsuz ifadeler veya hakaret içermektedir.\n\n"
            f"Müşterilerimize karşı saygılı ve nazik iletişim bekliyoruz.\n\n"
            f"Lütfen uygun bir dil kullanarak talebinizi yeniden iletiniz.\n\n"
            f"Anlayışınız için teşekkür ederiz.\n\n"
            f"Saygılarımızla,\n"
            f"Müşteri Hizmetleri Ekibi"
        )
        message.attach(MIMEText(formatted_body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, recipient_email, message.as_string())
        server.quit()
        
        print(f"🚫 [RED ONAY MAİLİ GÖNDERİLDİ] (Uygunsuz içerik) -> {recipient_email}")
    
    except Exception as e:
        print(f"❌ Red maili gönderilirken hata: {e}")


def send_missing_fields_email(recipient_email: str, subject: str, missing_fields: List[str], customer_name: str) -> None:
    """
    Send email notifying customer about missing/invalid fields.
    
    Args:
        recipient_email: Recipient email address
        subject: Original email subject
        missing_fields: List of missing or invalid fields
        customer_name: Customer name
    """
    try:
        message = MIMEMultipart()
        message['From'] = EMAIL_USER
        message['To'] = recipient_email
        message['Subject'] = f"Re: {subject} - Eksik Bilgiler"
        
        missing_fields_str = "\n".join([f"  • {field}" for field in missing_fields])
        
        formatted_body = (
            f"Sayın {customer_name},\n\n"
            f"Talebiniz alınmış ancak eksik veya geçersiz bilgiler nedeniyle işleme alınamıştır.\n\n"
            f"⚠️ Lütfen aşağıdaki bilgileri sağlayınız:\n\n"
            f"{missing_fields_str}\n\n"
            f"Eksik bilgileri tamamlayarak bu e-postaya yanıt gönderiniz.\n\n"
            f"Böylelikle talebiniz hızlıca işleme alınabilecektir.\n\n"
            f"Anlayışınız için teşekkür ederiz.\n\n"
            f"Saygılarımızla,\n"
            f"Müşteri Hizmetleri Ekibi"
        )
        message.attach(MIMEText(formatted_body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, recipient_email, message.as_string())
        server.quit()
        
        print(f"📋 [EKSİK ALAN BİLDİRİM MAİLİ GÖNDERİLDİ] -> {recipient_email}")
    
    except Exception as e:
        print(f"❌ Eksik alan maili gönderilirken hata: {e}")
