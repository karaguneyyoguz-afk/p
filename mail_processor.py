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
    SUB_CATEGORY_ONLINE_OPERATIONS_COMPLAINT, SUB_CATEGORY_MOBILE_APP_COMPLAINT,
    SUB_CATEGORY_WEBSITE_COMPLAINT,
    SUB_CATEGORY_CANCELLATION_HEALTH_ISSUE, SUB_CATEGORY_CANCELLATION_SPECIAL_REASON,
    SUB_CATEGORY_CANCELLATION_FORCE_MAJEURE, SUB_CATEGORY_CANCELLATION_HOTEL_REVIEWS,
    MAIL_CHARSET_DEFAULT,
    MAIL_CHARSET_FALLBACK
)
from utils import (
    decode_email_header, extract_sender_info,
    clean_subject_line, normalize_turkish_characters, html_to_text
)
from validators import (
    contains_profanity, extract_invoice_attributes, extract_payment_attributes,
    extract_option_deadline, build_invoice_attributes_from_fields,
    merge_invoice_attribute_results
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


BULK_UNSUBSCRIBE_KEYWORDS = [
    "unsubscribe", "uyelikten ayril", "abonelikten cik", "listeden cik",
]


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
        
        def _decode_part(part) -> str:
            charset = part.get_content_charset() or MAIL_CHARSET_DEFAULT
            try:
                return part.get_payload(decode=True).decode(charset, errors="ignore")
            except Exception:
                return part.get_payload(decode=True).decode(MAIL_CHARSET_FALLBACK, errors="ignore")

        body = ""
        if msg.is_multipart():
            # Extract first text/plain part (ignore attachments); if there is
            # no text/plain alternative at all (some marketing senders only
            # include text/html), fall back to the HTML part with tags
            # stripped rather than leaving the body empty.
            html_fallback = ""
            for part in msg.walk():
                content_type = part.get_content_type()
                if "attachment" in str(part.get("Content-Disposition", "")):
                    continue
                if content_type == "text/plain":
                    body = _decode_part(part)
                    break
                if content_type == "text/html" and not html_fallback:
                    html_fallback = html_to_text(_decode_part(part))
            if not body:
                body = html_fallback
        else:
            # Single part message -- strip tags if it's actually HTML (some
            # senders send a single text/html part with no plain-text
            # alternative at all).
            raw_body = _decode_part(msg)
            body = html_to_text(raw_body) if msg.get_content_type() == "text/html" else raw_body
        
        return subject, sender_email, sender_name, body

    @staticmethod
    def is_bulk_marketing_email(msg: email.message.Message, body: str) -> bool:
        """Detect bulk/marketing/newsletter mail -- these should never become
        a support ticket or get an automated reply (replying to a mass
        mailing list is pointless and the "sender" often can't even receive
        replies).

        The List-Unsubscribe header (RFC 2369) is the industry-standard
        signal virtually every legitimate marketing/newsletter platform sets;
        checked first since it's unambiguous. Falls back to unsubscribe-link
        boilerplate text for senders that skip the header.

        Not a generic spam filter -- a real customer email asking to cancel
        their own membership ("üyeliğimi iptal etmek istiyorum") doesn't
        contain these markers and is unaffected. Added after a Passo
        newsletter's "Üyelikten Ayrıl" footer collided with the
        ONLINE_ISLEMLER classification keyword list and got miscategorized
        as a membership-process ticket (observed live)."""
        if msg.get("List-Unsubscribe"):
            return True
        normalized = normalize_turkish_characters(body)
        return any(keyword in normalized for keyword in BULK_UNSUBSCRIBE_KEYWORDS)

    @staticmethod
    def is_bounce_notification(msg: email.message.Message, subject: str) -> bool:
        """Detect an automated bounce/delivery-failure notification (a "your
        message could not be delivered" report from a mail SERVER, not a
        person) -- these must never become a ticket or get an automated
        reply, since replying to mailer-daemon is a no-op at best and a
        bounce loop at worst: observed live, a rejection email the system
        itself sent to marketing@github.com got blocked by Google's policy,
        the resulting bounce notification landed back in the inbox, and THAT
        got processed as if it were a new customer email and turned into its
        own ticket.

        multipart/report with report-type=delivery-status (RFC 3462) is the
        structural, unambiguous signal mail servers use for this; falls back
        to the conventional mailer-daemon/postmaster sender address and
        "Delivery Status Notification"-style subject wording for servers
        that don't set the RFC 3462 content type."""
        content_type = msg.get_content_type()
        if content_type == "multipart/report" and "delivery-status" in (msg.get_param("report-type") or "").lower():
            return True

        # Covers both the address local-part ("mailer-daemon@...") and the
        # display name ("Mail Delivery Subsystem <mailer-daemon@...>") in one
        # check -- checking the raw From header text rather than the already
        # parsed-out sender_email/name separately.
        from_header = str(msg.get("From", "")).lower()
        if any(marker in from_header for marker in ("mailer-daemon", "postmaster", "mail delivery subsystem")):
            return True

        normalized_subject = normalize_turkish_characters(subject or "")
        bounce_subject_markers = (
            "delivery status notification", "delivery status notification (failure)",
            "undelivered mail returned to sender", "mail delivery failed",
            "returned mail", "teslim edilemedi",
        )
        return any(marker in normalized_subject for marker in bounce_subject_markers)

    @staticmethod
    def extract_ocr_attachments(msg: email.message.Message) -> List[Tuple[bytes, str]]:
        """Pull out raw bytes (+ content type) of any image/PDF attachments or
        inline images (customers sometimes send a Vergi Levhası scan/export or
        a company kaşe photo instead of typing the invoice info into the mail
        body -- see ocr_utils.py, which reads these before invoice-attribute
        extraction)."""
        from ocr_utils import ATTACHMENT_CONTENT_TYPES

        attachments: List[Tuple[bytes, str]] = []
        if not msg.is_multipart():
            return attachments

        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type not in ATTACHMENT_CONTENT_TYPES:
                continue
            try:
                payload = part.get_payload(decode=True)
            except Exception:
                continue
            if payload:
                attachments.append((payload, content_type))

        return attachments


class EmailCategorizer:
    """Categorizes emails and determines ticket routing."""
    
    THANK_YOU_KEYWORDS = [
        "tesekkur", "tesekkurler", "tesekkur ederim", "sagol",
        "tsk", "tks", "tessskur", "tesegkur", "teskut", "tesegkurr"
    ]
    
    INVOICE_KEYWORDS = ["fatura", "efatura", "e-fatura"]

    INVOICE_MODIFICATION_KEYWORDS = [
        "degisiklik", "degistir", "duzeltme", "revize", "onay",
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

    # Not: iki FARKLI durumda "iptal etmek/islemi" gibi CANCEL_INTENT_KEYWORDS
    # ifadeleri, yuzeysel olarak eslesse bile GERCEK/CANLI bir iptal talebi
    # DEGILDIR:
    #  1) KOSULLU/hipotetik soru: "iptal etmek istedigimiz TAKDIRDE/
    #     DURUMUNDA/HALINDE izlenmesi gereken surec ... hakkinda bilgi rica
    #     ederim" -- musteri henuz iptal ETMIYOR, sadece iptal EDERSE ne
    #     olacagini soruyor (ticket #101940152'de gozlemlendi).
    #  2) GECMISE DONUK + RAGMEN: "iptal islemi yapmamiza RAGMEN ... iade
    #     talebimizin acilmadigini ogrendik" -- iptal ZATEN TAMAMLANMIS,
    #     asil sikayet konusu FARKLI (burada: iade talebinin acilmamis
    #     olmasi); "iptal islemi" NOUN'u zamana gore CEKIMLENMEDIGI icin
    #     CANCEL_INTENT_KEYWORDS'teki gecmis-zaman filtresini (bkz. yukarida
    #     "iptal ettigimiz" notu) atlatiyordu (ticket #101940257'de
    #     gozlemlendi, kullanici tarafindan bildirildi).
    # Her iki durumda da "iptal etmek/ettirmek/edebilir/edelim/ediyoruz/
    # islemi" ifadesinden HEMEN SONRA (~25 karakter icinde) bir KOSUL/GECMIS
    # baglaci gecerse, bu somut/canli bir talep sayilmaz.
    CANCEL_NON_ACTIONABLE_PATTERN = re.compile(
        r'iptal\s+(?:etmek|ettirmek|edebilir|edelim|ediyoruz|islemi)\w*[^.!?]{0,25}'
        r'(?:takdirde|durumunda|halinde|ragmen)',
        re.IGNORECASE
    )

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

    # Not: bare "balayi" KASITLI OLARAK YOK -- "rezervasyonumuza balayı notu
    # düşürebilir misiniz?" gibi aslinda Not Ekleme Talebi'ne ait bir mail de
    # "balayi" iceriyor, bare haliyle bu Ek Hizmetler dalina yanlislikla
    # dusuyordu (Gercekci-26 testinde yakalandi). "balayi konsepti" gibi
    # gercekten SERVIS/PAKET degisikligi ifade eden compound kalip kullanildi.
    EXTRA_SERVICES_TOPIC_KEYWORDS = [
        "ek hizmet", "ekstra hizmet", "ekstra yatak", "transfer hizmeti",
        "balayi konsepti", "balayi paketi", "arac kirala", "transfer ekleme",
        "transfer cikarma", "transferi ekle", "transferi cikar"
    ]

    # Not: "adinda"/"adinin"/"isminde"/"isminin" gibi cekimli formlar da
    # eklendi (ör. "misafirin adında harf hatası", "adının güncellenmesi") --
    # bunlar "adres"/"adet" gibi kelimelerle CAKISMIYOR (ozel ek gerektiriyor).
    # Not: bare "isim" kasitli olarak buradan CIKARILDI -- "değişim"/"değişimi"
    # kelimesinin normalize hali ("degisim") tesadufen "isim" alt dizesini
    # icerdigi icin ("deg-ISIM-i"), CHANGE_INTENT_KEYWORDS'e "degisim" eklenince
    # "ulaşım firması değişimi" gibi alakasiz mailler yanlislikla ISIM_DEGISIKLIGI'ne
    # dusuyordu (canli ortamda gozlemlendi). Asagida NAME_CHANGE_BARE_ISIM_PATTERN
    # ile kelime siniri (\b) sarti eklenerek ayri kontrol ediliyor.
    NAME_CHANGE_TOPIC_KEYWORDS = [
        "ad soyad", "soyadim", "adim yanlis",
        "adinda", "adinin", "isminde", "isminin"
    ]
    NAME_CHANGE_BARE_ISIM_PATTERN = re.compile(r'\bisim\b', re.IGNORECASE)

    PERSON_ADD_REMOVE_TOPIC_KEYWORDS = [
        "kisi eklemek", "kisi cikarmak", "kisi ekleme", "kisi cikarma",
        "kisi sayisini", "bir kisi daha", "kisi daha eklemek",
        "misafir cikarma", "misafir ekleme", "yolcu ilavesi", "yolcu ekle",
        "yolcu cikar", "kisi sayisi guncelle", "kisi dahil edilmesi"
    ]

    NOTE_ADD_TOPIC_KEYWORDS = ["not"]
    # Not: bare "guncelle" KASITLI OLARAK burada YOK -- "not" (topic) cok
    # genel oldugu icin, alakasiz bir mailde "Ödeme bilgilerimi güncellememi
    # rica ederim, lütfen not edin." gibi ("not edin" = "lutfen dikkate
    # alin" deyimi, rezervasyon notu degil) cumleler yanlislikla yakalaniyordu
    # (denendi, canliya gitmeden yakalandi). "notu güncelleme"/"not
    # güncellemesi" GIBI, "not" kelimesiyle DOGRUDAN BAGLANTILI compound
    # ifadeler kullaniliyor.
    NOTE_ADD_EVENT_KEYWORDS = [
        "eklemek", "eklenmesini", "ekleyebilir", "dusurebilir", "dusmek",
        "ozel not", "ekleme", "dusul", "not guncelle", "notu guncelle",
        "notunun guncellenmesi"
    ]

    ROOM_TYPE_TOPIC_KEYWORDS = [
        "oda tipi", "suit odaya", "deluxe odaya", "deluxe oda"
    ]

    ROOM_TOPIC_KEYWORDS = ["oda", "odami", "odamizi", "odamiz"]
    # Genis oda konfigurasyonu sinyalleri -- "oda tipi" kelimesi bunlarla
    # BIRLIKTE geciyorsa (yani talep sadece tip degil, kisi dagilimi/yatak
    # tercihi/konfigurasyon gibi BASKA oda unsurlarini da kapsiyorsa), dar
    # "Oda Tipi Değişikliği" (546) yerine genis "Oda" (545) dalina
    # yonlendirilmesi gerekiyor (kullanici tarafindan revize edildi).
    ROOM_CONFIG_TOPIC_KEYWORDS = [
        "konfigurasyon", "kisi dagilim", "yatak tercihi", "yatak tipi",
        "misafir dagilim", "kisi sayisi"
    ]
    # Not: ROOM_CONFIG_TOPIC_KEYWORDS'un TAMAMI, "Oda" (545) dalinin TOPIC
    # KAPISI olarak (bare "oda" kelimesi HIC gecmese bile) kullanilamaz --
    # "kisi dagilim"/"kisi sayisi"/"misafir dagilim" tek basina genellikle
    # Kişi Ekleme/Çıkarma kırılımına ait ("Kişi sayısı güncellemesi" gibi,
    # kullanici tarafindan bildirildi). Sadece GERCEKTEN oda-spesifik olan
    # ("yatak tercihi"/"yatak tipi"/"oda konfigurasyon") bare "oda" olmadan
    # da yeterli sayilir; digerleri SADECE bare "oda" ile BIRLIKTE (is_broad_room_config
    # + ROOM_TOPIC_KEYWORDS ikisi birden) veya 546-geri-cekilme kontrolunde kullanilir.
    ROOM_CONFIG_STANDALONE_TOPIC_KEYWORDS = [
        "yatak tercihi", "yatak tipi", "konfigurasyon"
    ]

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
    # "ulasim"/"ucak bileti"/"otobus bileti" gibi genel bir nesne tek basina COK
    # GENEL (bilgi-istek Otobus/Bilet dallariyla cakisir), bu yuzden
    # CHANGE_INTENT_KEYWORDS ile ESLESTIRILEREK kullanilir, tek basina
    # tetiklenmez.
    TRANSPORT_MODE_TOPIC_KEYWORDS_PAIRED = [
        "ulasim", "ucak bileti", "otobus bileti", "sefer saati",
        "ulasim firmasi", "ucak saat"
    ]
    # Not: bare "degisikli" (CHANGE_INTENT_KEYWORDS icinde) kasitli olarak
    # BURADA kullanilmiyor -- "Otobüs seferi saatinde bir değişiklik var mı
    # acaba?" gibi SAF SORU cumleleri de "degisiklik" NOUN'unu icerdigi icin,
    # tam CHANGE_INTENT_KEYWORDS ile eslesince somut bir talep sanilip
    # Otobus-4 (ONAYLI) gibi mevcut bilgi-istek senaryolarini bozuyordu (canli
    # denemede yakalandi). Sadece daha guclu, eylem-fiili agirlikli sinyaller
    # kullanilir; hedeflenen 5 senaryonun hepsi zaten bunlardan birini iceriyor.
    TRANSPORT_MODE_STRONG_INTENT_KEYWORDS = [
        "degistir", "guncelle", "revizyon", "revize", "duzenle"
    ]

    # Not: "ucak bileti\w*" yerine sadece "ucak bilet" koku kullanildi -- eski
    # liste sadece tekil iyelik eklerini ("biletim","biletimiz") kapsiyordu,
    # "uçak biletlerimizin" gibi COGUL formlar ("bilet"+"ler"+"imiz"+"in")
    # kacyordu (kullanici tarafindan bildirildi). "ucus"/"pnr"/"havayolu"/
    # "ucak seferi" de eklendi.
    AIRPLANE_TICKET_TOPIC_KEYWORDS = [
        "ucak bilet", "ucus", "pnr", "havayolu", "ucak seferi"
    ]
    # "degisikli" (CHANGE_INTENT_KEYWORDS'teki NOUN stemi) tek basina cok
    # belirsiz -- "değişiklik hakkımız VAR MI" (soru) ile "değişikliği
    # İSTİYORUM"/"değişikliği için ... yapılmasını RİCA ederim" (somut talep)
    # ayni koku paylasiyor. Ayirt edici sinyal: "degisikli" kelimesinden
    # sonra, ayni cumle icinde (nokta/unlem/soru isaretine kadar, en fazla
    # ~45 karakter icinde) "isti" (istiyorum/istiyoruz) veya "rica"
    # (rica ederim/ederiz) gecmesi -- sorularda "isti" cok daha UZAKTA
    # ("hakkımız var mı ... öğrenmek istiyorum" gibi araya giren baska bir
    # cumlecikte) gecmeye egilimli (canli ortamda olcduk: 40 vs 69 karakter).
    CHANGE_REQUEST_NOUN_PATTERN = re.compile(r'degisikli\w*[^.!?]{0,45}(?:isti|rica)', re.IGNORECASE)
    # Aynı mantik "iptal"/"iade" NOUN'lari icin: "iptal EDİLMESİ hususunda ...
    # RİCA ederim" veya "bilet iadesi için ... RİCA ederiz" gibi CANCEL_INTENT_KEYWORDS'un
    # (iptal etmek/edebilir/ediyoruz/talebi vb.) kapsamadigi cekimler
    # (kullanici tarafindan bildirildi). "yapar mı(sınız)"/"eder mi(siniz)"
    # de -- Turkce'de cok yaygin bir KIBAR TALEP sorusu formu ("X yapar
    # mısınız?" = "lutfen X yapin") -- gercek bir soru degil, talep sayilir.
    # Her kullanildigi yerde SADECE ilgili konu listesiyle (AIRPLANE_TICKET_TOPIC_KEYWORDS,
    # ROOM_TOPIC_KEYWORDS, vb.) ESLESTIRILEREK kullanilir, boylece "İptal
    # ettiğim rezervasyonun iadesi ne zaman yapılır" gibi GECMISE DONUK
    # bilgi-istek metinleriyle cakismiyor (topic + 50 karakterlik dar pencere
    # zaten yeterince ayirt ediyor).
    CANCEL_REQUEST_NOUN_PATTERN = re.compile(
        r'(?:iptal|iade)\w*[^.!?]{0,50}(?:isti|rica|yapar\s*m[iı]s|eder\s*m[iı]s)',
        re.IGNORECASE
    )

    # Not: bare "sigorta" da eklendi -- "sigorta poliçesi iptal talebi" gibi
    # ifadeler "iptal sigortasi"/"seyahat sigortasi" kaliplarina uymuyor
    # (kullanici tarafindan bildirildi). Bare "sigorta" burada guvenli --
    # bu liste HER ZAMAN CANCEL_INTENT_KEYWORDS/CANCEL_REQUEST_NOUN_PATTERN
    # ile ESLESTIRILEREK kullaniliyor.
    CANCELLATION_INSURANCE_TOPIC_KEYWORDS = [
        "iptal sigortasi", "seyahat sigortasi", "sigorta"
    ]

    # Not: "kaydirildi" (PASIF, "rezervasyonumuz kaydırıldı") eksikti -- eski
    # liste sadece "kaydirildik" (biz+pasif) kapsiyordu, "kaydirdi" (aktif,
    # "farkli koku") "kaydirildi"yi (araya giren "il" pasif eki yuzunden)
    # KAPSAMIYOR (kullanici tarafindan bildirilen ornekte gozlemlendi).
    SHIFT_EVENT_KEYWORDS = [
        "kaydirdi", "kaydirildi", "kaydirma", "kaydirildik", "kaydirilmis",
        "kaydirmis", "overbooking"
    ]
    SHIFT_HOTEL_BASED_TOPIC_KEYWORDS = ["otel"]
    SHIFT_OPERATION_BASED_TOPIC_KEYWORDS = ["operasyon"]

    # Not: "kalan tutar"/"borc"/"odeme link" eklendi -- eski liste sadece
    # "bakiye" iceren ifadeleri kapsiyordu, "kalan tutarı tahsil etme"/
    # "rezervasyon borcunu ödeme"/"kalan ödeme linki" gibi ifadeler kacyordu
    # (kullanici tarafindan bildirildi).
    PAYMENT_COMPLETION_TOPIC_KEYWORDS = [
        "bakiye", "kalan bakiye", "eksik odeme", "kalan odeme", "kalan tutar",
        "borc", "odeme link"
    ]
    # "Ödemeyi tamamlamak istiyoruz" gibi, bare "odeme" ile "tamamla" fiilinin
    # BIRLIKTE (ama farkli ek/cekimlerle) gectigi durumlar icin -- bare
    # "odeme" tek basina TOPIC listesine eklenemez (cok genel, diger
    # onlarca dalla cakisir), bu yuzden "tamamla" fiiliyle YAKINLIK sarti
    # tasiyan bu regex kendi kendine yeterli (self-sufficient) sayilir.
    PAYMENT_COMPLETION_PATTERN = re.compile(r'odeme\w*\s+tamamla', re.IGNORECASE)

    # Not: eski liste tamamen SABIT/UZUN kaliplardan olustugu icin ("tamamlamak
    # istiyoruz" gibi) gercek musteri mailerindeki dogal varyasyonlarin
    # (ör. "tamamlamak ve ... rica ederim", "kapatmak istiyoruz", "tahsil
    # etmenizi rica ederiz") HICBIRINI yakalamiyordu. Stem'lere cevrildi --
    # PAYMENT_COMPLETION_TOPIC_KEYWORDS ile ESLESTIRILEREK kullanildigi icin
    # bare "isti"/"rica" burada guvenli (topic zaten yeterince spesifik).
    PAYMENT_COMPLETION_INTENT_KEYWORDS = [
        "tamamla", "kapat", "tahsil", "isti", "rica"
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
        "degisiklik hakkinda bilgi almak istiyorum", "nasil degisiklik yapabilirim",
        "degisiklik sartlari", "degisiklik ucreti"
    ]
    # Not: "degisiklik yapip yapamayacagimizi ... bilgi talep ediyorum" gibi,
    # Turkce'de COK YAYGIN olan "yapip yapamama" (yapabilir miyiz/miyim) soru
    # kalibi, yukaridaki SABIT/UZUN RESERVATION_CHANGE_INFO_KEYWORDS
    # kaliplarinin hicbirine uymuyordu -- musteri somut bir islem talep
    # etmeden sadece imkanini soruyor olsa bile, bare "degisikli"
    # (CHANGE_INTENT_KEYWORDS icinde) eslesip mail yanlislikla Backoffice >
    # Degisiklik > Diger'e dusuyordu (ticket #101940103'te gozlemlendi,
    # kullanici tarafindan bildirildi).
    RESERVATION_CHANGE_INFO_PATTERN = re.compile(
        r'degisikli\w*[^.!?]{0,45}yap\w*\s+yapamayacag\w*', re.IGNORECASE
    )

    RESERVATION_CANCELLATION_INFO_TOPIC_KEYWORDS = ["iptal"]
    # Not: bare "surec" kasitli olarak CIKARILDI -- "surec" cok genel bir kelime
    # oldugu icin, metnin baska bir yerinde alakasiz sekilde "iptal" gecen
    # mailler de (ör. "iade surecimin kontrolu" + ayrica bahsi gecen "daha once
    # iptal ettigim rezervasyon") yanlislikla bu dala takiliyordu.
    RESERVATION_CANCELLATION_INFO_EVENT_KEYWORDS = [
        "nasil", "kosul", "sart", "ne olur", "iptal sureci"
    ]

    RESERVATION_CONFIRMATION_INFO_EVENT_KEYWORDS = [
        "nedir", "ne zaman", "sure", "ulasir", "ogrenmek", "onayladi mi",
        "onaylanip", "onay bilgisi"
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
        "resepsiyon", "check-in", "checkin", "check-out", "checkout",
        "otelin operasyon", "otel operasyon", "personel ilgisiz",
        "otel yonetim", "kotu karsilama"
    ]

    HOTEL_SERVICES_TOPIC_KEYWORDS = [
        "oda temizligi", "temizlenmedi", "havuz", "yemek", "otel hizmet"
    ]

    AIRLINE_CHANGE_TOPIC_KEYWORDS = ["havayolu"]
    AIRLINE_CHANGE_EVENT_KEYWORDS = [
        "degisti", "degistirildi", "degisikligi yapildi", "farkli", "baska",
        "haber verilmeden", "habersiz"
    ]

    # Not: "ucus saat" (sonundaki "i" olmadan) eklendi -- eski liste sadece
    # tekil iyelik eklerini ("saati","saatimiz") kapsiyordu, "uçuş
    # saatlerinin" gibi COGUL formlar kaciyordu (kullanici tarafindan
    # bildirilen ticket #101939947'de gozlemlendi). "saatlerin birbirine
    # uymamasi" da eklendi.
    FLIGHT_TIME_TOPIC_KEYWORDS = [
        "ucus saat", "sefer saat", "kalkis saat", "saatlerin birbirine"
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

    # Not: "rota"/"vaat edilen yer"/"tur hizmet" eklendi -- eski liste sadece
    # bare "tur" kelimesiyle baslayan iki kalibi ("tur program"/"tur
    # organizasyon") kapsiyordu, "Vaat edilen yerler gezilmedi"/"Rota
    # değiştirildi"/"Tur hizmetinden şikayetçiyiz" gibi ifadeler "tur"
    # kelimesini hic icermeyebiliyor veya farkli bir kalip kullaniyordu
    # (kullanici tarafindan bildirildi).
    TOUR_TOPIC_KEYWORDS = [
        "tur program", "tur organizasyon", "tur hizmet", "rota",
        "vaat edilen yer", "planlanan yer"
    ]

    GUIDE_COMPLAINT_TOPIC_KEYWORDS = ["rehber"]

    REFUND_TOPIC_KEYWORDS = ["iade"]

    # Not: "acilmadi"/"alinmadi" (olumsuz isim-fiil kokleri, "acilmadigini
    # ogrendik"/"alinmadigini ogrendik" gibi cekimleri kapsar) eklendi -- eski
    # liste sadece "-mamis" (olumsuz sifat-fiil) formlarini kapsiyordu,
    # "acilmadigini"/"alinmadigini" gibi COK YAYGIN "-madigini" cekimleri
    # kacyordu (ticket #101940257'de gozlemlendi, kullanici tarafindan
    # bildirildi).
    REFUND_REQUEST_NOT_OPENED_EVENT_KEYWORDS = [
        "acilmamis", "olusturulmamis", "islenmemis", "isleme alinmamis",
        "kayit gorunmuyor", "hicbir kayit", "kayit yok", "acilmadi", "alinmadi"
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
        "fiyat garantisi", "daha ucuz gordum", "baska sitede ucuz",
        "daha ucuz bulduk", "es deger fiyat"
    ]

    # Not: "fiyat dusus" (noun, "düşüşü") eklendi -- eski liste sadece "fiyat
    # dustu"/"fiyati dustu" (fiil) kapsiyordu. "ucuzladi"/"geriledi" de
    # eklendi (kullanici tarafindan bildirildi).
    PRICE_DROP_TOPIC_KEYWORDS = [
        "fiyat dustu", "fiyati dustu", "fiyat dusus", "ucuzladi", "geriledi",
        "indirim farki"
    ]

    # Not: "fatura fiyati" eklendi -- "Fatura fiyatı uyumsuzluğu" gibi
    # ifadeler bare "fatura" kelimesi yuzunden yanlislikla FATURA sikayet
    # dalina dusuyordu (asagida is_price_payment_objection korumasi ile).
    PAYMENT_OBJECTION_TOPIC_KEYWORDS = ["odeme", "tutar", "kart", "fatura fiyati", "ucret"]
    # Not: bare "cekilmesi" KASITLI OLARAK YOK -- "ödeme çekilmesine rağmen
    # tutar sisteminize yansımadı" gibi TAMAMEN FARKLI bir kirilima
    # (ODEMENIN_YANSIMAMASI) ait mailler de "cekilmesi" iceriyor, bare
    # haliyle Odeme-2/Odeme-3 testlerini bozuyordu (denendi, geri alindi).
    # "yanlis ucret" gibi spesifik compound kalip kullanildi.
    PAYMENT_OBJECTION_EVENT_KEYWORDS = [
        "itiraz", "fazla cekildi", "yanlis tutar", "fazla odeme",
        "hatali tutar", "yansitilmasi", "uyumsuz", "yanlis ucret"
    ]

    PRICE_GENERAL_TOPIC_KEYWORDS = ["fiyat", "ucret"]
    # Not: eski EVENT listesi SADECE tutarsizlik/uyusmazlik tespitine
    # odakliydi ("tutmuyor"/"uyusmuyor" vb.); kullanici bu dali "joker fiyat
    # sikayeti" (genel memnuniyetsizlik/yuksek fiyat) olarak revize etti --
    # COMPLAINT_SENTIMENT_KEYWORDS de ayri bir alternatif olarak eklendi.
    PRICE_GENERAL_EVENT_KEYWORDS = [
        "tutmuyor", "uyusmuyor", "farkli gosteriliyor", "yanlis hesaplanmis",
        "hatali gosterilmis", "cok yuksek"
    ]

    # --- SIKAYET > ONLINE_ISLEMLER (3 kirilim) ---
    # Not: oncelik sirasi (musteri onayli) -- MOBIL_UYGULAMA > WEB_SITESI >
    # ONLINE_ISLEMLER (genel/platform belirtilmeyen). Bare "site" KASITLI
    # OLARAK YOK -- cok kisa/genel bir alt dize, "web sitesi"/"internet
    # sitesi" gibi compound kaliplar kullanildi.
    MOBILE_APP_TOPIC_KEYWORDS = ["mobil", "uygulama", " app "]
    # Not: "siteniz" (sitenize/sitenizin/sitenizde gibi 2. cogul iyelik
    # ekleriyle CEKIMLENMIS KOK) eklendi -- eski liste sadece 3. tekil sahiplik
    # eki tasiyan "web sitesi" kalibini kapsiyordu, "web sitenize girerek...
    # web sitenizin calismamasindan sikayetciyim" gibi COK YAYGIN, dogrudan
    # musteriye hitaben yazilmis ifadeler (ticket #101940185'te gozlemlendi,
    # kullanici tarafindan bildirildi) kaciyordu ve varsayilan Bilgi-Istek >
    # Tesis > Tesis Iletisim'e dusuyordu. Bare "site" hala KASITLI OLARAK YOK
    # (yukaridaki not gecerliligini koruyor); "siteniz" yeterince spesifik.
    #
    # ANCAK: "siteniz" bare COMPLAINT_SENTIMENT_KEYWORDS (genel sikayet tonu)
    # ile eslestirilince COK GENIS oluyordu -- "web sitenizde yapilan otel
    # yorumlari/puanlamalari gercegi yansitmiyor ... iptal etmek zorunda
    # kaldik, sikayetciyiz" gibi mailler, "siteniz" SADECE olayin GECTIGI YERI
    # belirttigi (asil sikayet konusu FARKLI -- otel yorumlari) halde bu dala
    # dusuyordu (ticket #101940278'de gozlemlendi, kullanici tarafindan
    # bildirildi). Bu yuzden WEBSITE_TOPIC_KEYWORDS artik generic
    # COMPLAINT_SENTIMENT_KEYWORDS ile degil, asagidaki SPESIFIK
    # WEBSITE_MALFUNCTION_EVENT_KEYWORDS (sitenin/sayfanin TEKNIK olarak
    # calismamasi) ile eslestiriliyor.
    WEBSITE_TOPIC_KEYWORDS = ["web sitesi", "internet sitesi", "siteniz"]
    WEBSITE_MALFUNCTION_EVENT_KEYWORDS = [
        "acilmiyor", "calismiyor", "calismama", "sayfa don", "site don",
        "hata al", "giremiyorum", "erisemiyorum", "yuklenmiyor"
    ]
    ONLINE_OPERATIONS_COMPLAINT_TOPIC_KEYWORDS = ["online islem"]
    ONLINE_OPERATIONS_COMPLAINT_EVENT_KEYWORDS = [
        "sistem hata", "islem yapamiyoruz", "islem yapamiyorum", "dijital hata"
    ]

    # --- SIKAYET > IPTAL (sebep bazli, 4 kirilim) ---
    CANCELLATION_HEALTH_TOPIC_KEYWORDS = [
        "saglik problem", "hastane", "hastalik", "saglik rapor", "rahatsizlik"
    ]
    CANCELLATION_FORCE_MAJEURE_TOPIC_KEYWORDS = ["mucbir sebep", "dogal afet"]
    # Not: "ozel sebeb" (unsuz yumusamasi -- "sebep" + iyelik eki "sebebimiz"
    # olur, "p" harfi unluyle baslayan ekten once "b"ye donusur) ve "kisisel
    # mazeret" (musteriler "ozel mazeret" yerine cok sik "kisisel mazeret"
    # de diyor) eklendi -- eski liste bu COK YAYGIN cekim/esanlamli
    # varyasyonlari kaciriyordu (ör. "ozel sebebimiz / kisisel mazeretimiz
    # nedeniyle iptal etmek zorunda kaldik", ticket #101940293'te
    # gozlemlendi, kullanici tarafindan bildirildi).
    CANCELLATION_SPECIAL_REASON_TOPIC_KEYWORDS = [
        "ozel sebep", "ozel mazeret", "ozel sebeb", "kisisel mazeret", "kisisel sebep"
    ]
    CANCELLATION_HOTEL_REVIEWS_TOPIC_KEYWORDS = ["otel yorum", "yanilti", "gercek disi puan"]
    # Not: "otel yorum" bitisik kalibi, "otel icin yapilan yorumlarin ve
    # puanlamalarin ... gercegi yansitmasindan oturu yanlis yonlendirildik"
    # gibi araya BASKA kelimeler giren (word order farkli) dogal ifadeleri
    # kaciriyordu (ticket #101940278'de gozlemlendi, kullanici tarafindan
    # bildirildi). "otel" ile "yorum"/"puanlama" arasinda ~40 karakterlik bir
    # pencerede (sira ne olursa olsun) BIRLIKTE gecmesi de yeterli sayilir.
    CANCELLATION_HOTEL_REVIEWS_PROXIMITY_PATTERN = re.compile(
        r'otel\w*[^.!?]{0,40}(?:yorum|puanlama)\w*', re.IGNORECASE
    )

    PAYMENT_OBJECTION_KEYWORDS = [
        "odemeye itiraz ediyorum", "yanlis tutar cekildi", "fazla odeme yapildi", "odeme itirazi"
    ]

    @staticmethod
    def categorize(subject: str, body: str, sender_email: str, attachment_fields: Optional[dict] = None) -> Dict:
        """
        Categorize email and determine ticket type/category.

        Args:
            subject: Email subject line
            body: Email body content
            sender_email: Sender's email address
            attachment_fields: Invoice fields (company_name/person_name/
                tax_office/tax_value/tc_value/address) already extracted from
                image/PDF attachments -- see
                ocr_utils.extract_invoice_fields_from_attachments(). Used to
                fill in whatever the mail body itself didn't provide.

        Returns:
            Dictionary containing ticket categorization info
        """
        combined_text = f"{subject} {body}"

        def resolve_invoice_attributes(text: str) -> Tuple[List[dict], List[str]]:
            """extract_invoice_attributes() on the mail body, with any fields
            it couldn't find filled in from an attachment (if present)."""
            result = extract_invoice_attributes(text, sender_email)
            if result[1] and attachment_fields:
                attachment_result = build_invoice_attributes_from_fields(attachment_fields, sender_email)
                result = merge_invoice_attribute_results(result, attachment_result)
            return result
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
            and (
                any(keyword in normalized_text for keyword in EmailCategorizer.CANCEL_INTENT_KEYWORDS)
                or EmailCategorizer.CANCEL_REQUEST_NOUN_PATTERN.search(normalized_text)
            )
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

        # Not: bare "degisikli" (CHANGE_INTENT_KEYWORDS) yerine TRANSPORT_MODE_STRONG_INTENT_KEYWORDS
        # kullanildi -- "Uçuşumuz iptal olursa değişiklik hakkımız var mı ...
        # öğrenmek istiyorum" gibi SAF SORU cumleleri "degisiklik" NOUN'unu
        # icerdigi icin somut talep saniliyor, DEGISIKLIK_HAKKI_SORGULAMA
        # bilgi-istek dalini (Gercekci-10) bozuyordu. Ayrica "degistirildi"
        # (PASIF, "-di" gecmis zaman) acikca haric tutuluyor -- "Uçuş saatimiz
        # habersizce değiştirildi" gibi bir SIKAYET ifadesi ("baskasi yapti,
        # ben istemedim") somut bir DEGISIKLIK TALEBIYLE ("değiştirmek
        # istiyoruz") ayni "degistir" kokunu paylasiyor ama anlam tam tersi
        # (Gercekci-44, SIKAYET > UCAK > SAAT_DEGISIKLIGI ile cakisiyordu).
        # Not: COMPLAINT_SENTIMENT_KEYWORDS ("sikayetciyiz" vb.) de haric
        # tutuluyor -- "Havayolu firması uçuş rotamızı değiştirdi,
        # şikayetçiyiz." gibi bir SIKAYET ifadesi ("havayolu DEGISTIRDI",
        # aktif ama musteri TALEP ETMEDI) "degistir" kokunu paylastigi icin
        # yanlislikla somut bir Backoffice talebi saniliyor, SIKAYET > UCAK >
        # HAVAYOLU_DEGISIKLIGI ile cakisiyordu (kullanici tarafindan bildirildi).
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.AIRPLANE_TICKET_TOPIC_KEYWORDS)
            and "degistirildi" not in normalized_text
            and not any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
            and (
                any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_MODE_STRONG_INTENT_KEYWORDS)
                or "degisim" in normalized_text
                or EmailCategorizer.CHANGE_REQUEST_NOUN_PATTERN.search(normalized_text)
            )
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
        # Not: bare "transfer" (TRANSPORT_CHANGE_RIGHTS_KEYWORDS) somut bir Ek
        # Hizmet (transfer/balayi/arac kiralama) talebiyle CAKISIRSA geri
        # cekilir -- aksi halde "daha önce eklenen transfer hizmetinin saat ve
        # detaylarında değişiklik yapılması" gibi bir talep, bare "transfer"
        # kelimesi yuzunden yanlislikla bu bilgi-istek dalina dusuyordu
        # (kullanici tarafindan bildirildi).
        is_extra_service_change = any(
            keyword in normalized_text for keyword in EmailCategorizer.EXTRA_SERVICES_TOPIC_KEYWORDS
        )
        # Not: "tarih degisikligi"/"ceza" gibi TRANSPORT_CHANGE_RIGHTS_KEYWORDS
        # ifadeleri, hicbir tasima-modu kelimesi (bilet/otobus/ucak/ucus/
        # transfer/pnr/havayolu) icermeyen GENEL bir rezervasyon-degisiklik
        # bilgi sorusuyla karsilasinca da geri cekiliyor -- aksi halde
        # "Rezervasyonumda tarih değişikliği yapmak istesem değişiklik
        # şartları ve ücreti hakkında bilgi almak istiyorum." gibi tasimayla
        # ilgisiz bir soru, bare "tarih degisikligi" yuzunden yanlislikla bu
        # Ulasim-ozel dalina dusuyordu (kullanici tarafindan bildirildi).
        is_general_reservation_change_info = (
            "degisiklik" in normalized_text
            and ("sart" in normalized_text or "nasil" in normalized_text)
            and not any(
                keyword in normalized_text
                for keyword in ["bilet", "otobus", "ucak", "ucus", "transfer", "pnr", "havayolu"]
            )
        )
        # Not: "kesinti uygulan"/"ceza" gibi TRANSPORT_CHANGE_RIGHTS_KEYWORDS
        # ifadeleri, tasima-modu BAGLAMI olmayan SAF REZERVASYON/OTEL iptal
        # SIKAYETLERINDE de geciyordu ("... rezervasyonumuzu iptal etmek
        # zorunda kaldigimiz halde kesinti uygulanmasindan ... sikayetciyiz"
        # gibi, ticket #101940293'te gozlemlendi) -- bu tamamen alakasiz bir
        # Ulasim bilgi-istek dalina degil, SIKAYET > IPTAL altindaki genel
        # iptal sikayeti dallarina ait. Tasima-modu kelimesi HICBIRI yoksa VE
        # metin acikca bir SIKAYET (COMPLAINT_SENTIMENT_KEYWORDS) tasiyorsa,
        # bu dal geri cekilir (kullanici tarafindan bildirildi).
        is_reservation_cancellation_complaint_without_transport = (
            any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
            and not any(
                keyword in normalized_text
                for keyword in ["bilet", "otobus", "ucak", "ucus", "transfer", "pnr", "havayolu"]
            )
        )
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_CHANGE_RIGHTS_KEYWORDS)
            and not is_extra_service_change
            and not is_general_reservation_change_info
            and not is_reservation_cancellation_complaint_without_transport
        ):
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

        # Not: somut bir Backoffice > Degisiklik > Ulasim talebiyle (asagida,
        # TRANSPORT_MODE_CHANGE_TOPIC_KEYWORDS / TRANSPORT_MODE_TOPIC_KEYWORDS_PAIRED
        # + CHANGE_INTENT_KEYWORDS) CAKISIRSA bu bilgi-istek dali GERI CEKILIR --
        # aksi halde "Uçak veya otobüs bileti saatlerimizin... güncellenerek
        # backoffice işlemlerinin tamamlanmasını rica ederim" gibi ACIKCA
        # aksiyoner bir talep, bare "otobus" kelimesi yuzunden yanlislikla
        # bilgi-istek sayiliyordu (canli ortamda ticket #101939280'de gozlemlendi).
        is_actionable_transport_change = (
            any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_MODE_CHANGE_TOPIC_KEYWORDS)
            or (
                any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_MODE_TOPIC_KEYWORDS_PAIRED)
                and (
                    any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_MODE_STRONG_INTENT_KEYWORDS)
                    or "degisim" in normalized_text
                )
            )
        )
        # Not: somut bir Backoffice > Kaydırma > Operasyon/Otel Kaynaklı
        # talebiyle (asagida, SHIFT_OPERATION_BASED_TOPIC_KEYWORDS/SHIFT_HOTEL_BASED_TOPIC_KEYWORDS
        # + SHIFT_EVENT_KEYWORDS) CAKISIRSA bu bilgi-istek dallari da GERI
        # CEKILIR -- aksi halde "iç hat uçuş planlamalarındaki değişiklikler
        # ... operasyon biriminiz tarafından iletilen bilgilendirmede ..."
        # gibi bir mail, bare "ucus"+"bilgilendirme" kombinasyonu yuzunden
        # yanlislikla BILGI_ISTEK > ULASIM > BILET'e dusuyordu (kullanici
        # tarafindan bildirildi).
        is_shift_related = (
            any(keyword in normalized_text for keyword in EmailCategorizer.SHIFT_OPERATION_BASED_TOPIC_KEYWORDS)
            or any(keyword in normalized_text for keyword in EmailCategorizer.SHIFT_HOTEL_BASED_TOPIC_KEYWORDS)
        ) and any(keyword in normalized_text for keyword in EmailCategorizer.SHIFT_EVENT_KEYWORDS)
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.OTOBUS_TOPIC_KEYWORDS)
            and not is_actionable_transport_change
            and not is_shift_related
        ):
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

        # Not: is_actionable_transport_change yukarida (OTOBUS kontrolunden once)
        # hesaplandi, ayni koruma burada da gecerli -- aksi halde "bilet" +
        # "guncelle" kombinasyonu (TRANSPORT_TICKET_EVENT_KEYWORDS icinde
        # "guncelle" var) somut bir Backoffice > Degisiklik > Ulasim talebini
        # de yanlislikla bilgi-istek sayardi.
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_TICKET_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.TRANSPORT_TICKET_EVENT_KEYWORDS)
            and not is_actionable_transport_change
            and not is_shift_related
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

        # Not: "fatura fiyati" ("Fatura fiyatı uyumsuzluğu" gibi) gecen
        # mailler, bare "fatura"+"sikayet" kombinasyonu yuzunden yanlislikla
        # buraya (fatura KESILMESI/duzeltilmesi sikayeti) degil, asagida
        # Fiyatlandirma > Odeme Itirazi'na gitmeli -- bu mailler gercek bir
        # fatura duzenleme/kesim sorunu degil, fiyat/tutar mutabakatsizligi
        # (kullanici tarafindan bildirildi).
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.INVOICE_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.INVOICE_COMPLAINT_KEYWORDS)
            and "fatura fiyati" not in normalized_text
        ):
            attributes, missing_fields = resolve_invoice_attributes(combined_text)
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

        # Not: FLIGHT_TIME_TOPIC_KEYWORDS de gecerse (asagida, SAAT_DEGISIKLIGI
        # dali) bu dal geri cekilir -- "havayolu firması ... uçuş saatlerinin
        # ... değiştirilmesi ve saatlerin birbirine uymaması" gibi bir
        # sikayette asil odak SAAT UYUMSUZLUGU, "havayolu" sadece degisikligi
        # yapan tarafi belirtiyor (ticket #101939947'de kullanici tarafindan
        # bildirildi). Iki dal ayni "degisti" kokunu paylastigi icin
        # havayolu+saat birlikte gecen mailler her zaman SAAT_DEGISIKLIGI'ne
        # ait sayilir.
        is_flight_time_change = any(
            keyword in normalized_text for keyword in EmailCategorizer.FLIGHT_TIME_TOPIC_KEYWORDS
        )
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.AIRLINE_CHANGE_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.AIRLINE_CHANGE_EVENT_KEYWORDS)
            and not is_flight_time_change
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
        # Ayrica: REFUND_TOPIC_KEYWORDS ("iade") de BURADA HARIC TUTULUYOR --
        # "iadesinin gerceklestirildigi soylendi ... tutar ... yansimadi" gibi
        # mailler "tutar"+"yansimadi" yuzunden bu GENEL odeme dalina
        # dusuyordu, oysa musteri somut olarak bir IADENIN yansimamasindan
        # bahsediyor -- daha SPESIFIK olan asagidaki SIKAYET > IADE >
        # IADENIN_MISAFIRE_YANSIMAMASI dalina birakilmasi gerekiyor (ticket
        # bildirildi, kullanici tarafindan raporlandi).
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_REFLECTION_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_REFLECTION_EVENT_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
            and not any(keyword in normalized_text for keyword in EmailCategorizer.REFUND_TOPIC_KEYWORDS)
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
            and (
                any(keyword in normalized_text for keyword in EmailCategorizer.PRICE_GENERAL_EVENT_KEYWORDS)
                # Not: "joker fiyat şikayeti" olarak revize edildi -- genel
                # memnuniyetsizlik/sikayet ifadeleri de (COMPLAINT_SENTIMENT_KEYWORDS)
                # kabul ediliyor, sadece tutarsizlik/uyusmazlik tespitiyle
                # sinirli degil (kullanici tarafindan bildirildi).
                or any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
            )
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

        # ============================================================
        # SIKAYET > ONLINE_ISLEMLER (3 kirilim)
        # Oncelik: MOBIL_UYGULAMA > WEB_SITESI > ONLINE_ISLEMLER (genel).
        # ============================================================
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.MOBILE_APP_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_ONLINE_OPERATIONS,
                "category_name": "Online İşlemler",
                "sub_category_id": SUB_CATEGORY_MOBILE_APP_COMPLAINT,
                "sub_category_name": "Mobil Uygulama",
                "sub_category_code": "MOBIL_UYGULAMA",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > ONLINE_ISLEMLER > MOBIL_UYGULAMA"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.WEBSITE_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.WEBSITE_MALFUNCTION_EVENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_ONLINE_OPERATIONS,
                "category_name": "Online İşlemler",
                "sub_category_id": SUB_CATEGORY_WEBSITE_COMPLAINT,
                "sub_category_name": "Web Sitesi",
                "sub_category_code": "WEB_SITESI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > ONLINE_ISLEMLER > WEB_SITESI"
            }

        # Not: COMPLAINT_SENTIMENT_KEYWORDS de zorunlu -- "sistem hata veriyor"
        # gibi ifadeler gercek bir sikayet olmadan (ör. "nasıl
        # güncelleyebilirim?" gibi bir yardim talebinde) de gecebiliyor,
        # bare OR mantigi mevcut onayli Online-3 testini bozuyordu (denendi,
        # geri alindi).
        if (
            (
                any(keyword in normalized_text for keyword in EmailCategorizer.ONLINE_OPERATIONS_COMPLAINT_TOPIC_KEYWORDS)
                or any(keyword in normalized_text for keyword in EmailCategorizer.ONLINE_OPERATIONS_COMPLAINT_EVENT_KEYWORDS)
            )
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_ONLINE_OPERATIONS,
                "category_name": "Online İşlemler",
                "sub_category_id": SUB_CATEGORY_ONLINE_OPERATIONS_COMPLAINT,
                "sub_category_name": "Online İşlemler",
                "sub_category_code": "ONLINE_ISLEMLER",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > ONLINE_ISLEMLER > ONLINE_ISLEMLER"
            }

        # ============================================================
        # SIKAYET > IPTAL (sebep bazli, 4 kirilim)
        # ============================================================
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.CANCELLATION_HEALTH_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_CANCELLATION,
                "category_name": "İptal",
                "sub_category_id": SUB_CATEGORY_CANCELLATION_HEALTH_ISSUE,
                "sub_category_name": "Sağlık Problemleri",
                "sub_category_code": "SAGLIK_PROBLEMLERI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > IPTAL > SAGLIK_PROBLEMLERI"
            }

        if any(keyword in normalized_text for keyword in EmailCategorizer.CANCELLATION_FORCE_MAJEURE_TOPIC_KEYWORDS):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_CANCELLATION,
                "category_name": "İptal",
                "sub_category_id": SUB_CATEGORY_CANCELLATION_FORCE_MAJEURE,
                "sub_category_name": "Mücbir Sebep",
                "sub_category_code": "MUCBIR_SEBEP",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > IPTAL > MUCBIR_SEBEP"
            }

        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.CANCELLATION_SPECIAL_REASON_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_CANCELLATION,
                "category_name": "İptal",
                "sub_category_id": SUB_CATEGORY_CANCELLATION_SPECIAL_REASON,
                "sub_category_name": "Özel Sebep",
                "sub_category_code": "OZEL_SEBEP",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > IPTAL > OZEL_SEBEP"
            }

        if (
            (
                any(keyword in normalized_text for keyword in EmailCategorizer.CANCELLATION_HOTEL_REVIEWS_TOPIC_KEYWORDS)
                or EmailCategorizer.CANCELLATION_HOTEL_REVIEWS_PROXIMITY_PATTERN.search(normalized_text)
            )
            and any(keyword in normalized_text for keyword in EmailCategorizer.COMPLAINT_SENTIMENT_KEYWORDS)
        ):
            return {
                "channel_id": CHANNEL_ID,
                "ticket_type_id": TICKET_TYPE_COMPLAINT,
                "ticket_type_name": "Şikayet",
                "category_id": CATEGORY_CANCELLATION,
                "category_name": "İptal",
                "sub_category_id": SUB_CATEGORY_CANCELLATION_HOTEL_REVIEWS,
                "sub_category_name": "Otel Yorumları",
                "sub_category_code": "OTEL_YORUMLARI",
                "attributes": [],
                "missing_fields": [],
                "classification": "SIKAYET > IPTAL > OTEL_YORUMLARI"
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
            attributes, missing_fields = resolve_invoice_attributes(combined_text)
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
            attributes, missing_fields = resolve_invoice_attributes(combined_text)
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
            attributes, missing_fields = resolve_invoice_attributes(combined_text)
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

        # Not: somut bir sigorta IPTALI talebiyle (asagida, CANCELLATION_INSURANCE_TOPIC_KEYWORDS
        # + CANCEL_INTENT_KEYWORDS/CANCEL_REQUEST_NOUN_PATTERN) CAKISIRSA bu
        # genel "Ek Hizmetler" dali GERI CEKILIR -- aksi halde "iptal sigortası
        # ek hizmetinin kaldırılması" gibi somut bir talep, bare "ek hizmet"
        # kelimesi yuzunden yanlislikla genel Degisiklik>Ek Hizmetler'e
        # dusuyordu (kullanici tarafindan bildirildi).
        is_insurance_cancellation = (
            any(keyword in normalized_text for keyword in EmailCategorizer.CANCELLATION_INSURANCE_TOPIC_KEYWORDS)
            and (
                any(keyword in normalized_text for keyword in EmailCategorizer.CANCEL_INTENT_KEYWORDS)
                or EmailCategorizer.CANCEL_REQUEST_NOUN_PATTERN.search(normalized_text)
                # Not: "sigorta ek hizmetini ÇIKARMAK istiyoruz" -- "cikar"
                # (cikarmak) ek hizmet BAGLAMINDA "kaldirma/iptal" ile esdeger
                # bir fiil, ama CANCEL_INTENT_KEYWORDS'te "iptal" koku
                # gerektigi icin kapsanmiyordu (kullanici tarafindan bildirildi).
                or "cikar" in normalized_text
            )
        )
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.EXTRA_SERVICES_TOPIC_KEYWORDS)
            and not is_insurance_cancellation
        ):
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
            (
                any(keyword in normalized_text for keyword in EmailCategorizer.NAME_CHANGE_TOPIC_KEYWORDS)
                or EmailCategorizer.NAME_CHANGE_BARE_ISIM_PATTERN.search(normalized_text)
            )
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
        # ANCAK: mail SADECE tip degil, ROOM_CONFIG_TOPIC_KEYWORDS ile ifade
        # edilen BASKA oda unsurlarini da (kisi dagilimi, yatak tercihi,
        # konfigurasyon vb.) kapsiyorsa, dar "Oda Tipi Değişikliği" yerine
        # genis "Oda" (545) dalina birakiliyor -- "sadece 'oda tipi'
        # kelimesine takılıp kalmayacak" (kullanici tarafindan revize edildi).
        is_broad_room_config = any(
            keyword in normalized_text for keyword in EmailCategorizer.ROOM_CONFIG_TOPIC_KEYWORDS
        )
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.ROOM_TYPE_TOPIC_KEYWORDS)
            and any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS)
            and not is_broad_room_config
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
            (
                any(keyword in normalized_text for keyword in EmailCategorizer.ROOM_TOPIC_KEYWORDS)
                or any(keyword in normalized_text for keyword in EmailCategorizer.ROOM_CONFIG_STANDALONE_TOPIC_KEYWORDS)
            )
            and (
                any(keyword in normalized_text for keyword in EmailCategorizer.CHANGE_INTENT_KEYWORDS)
                # Not: "oda yükseltme (upgrade)" -- "yukselt" CHANGE_INTENT_KEYWORDS'te
                # yok (baska hicbir Degisiklik dalinda kullanilmadigi icin
                # sadece burada, dar kapsamda eklendi), kullanici tarafindan
                # bildirildi.
                or "yukselt" in normalized_text
                or "degisim" in normalized_text
                or EmailCategorizer.CHANGE_REQUEST_NOUN_PATTERN.search(normalized_text)
            )
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

        # Not: is_actionable_transport_change, fonksiyonun basinda (OTOBUS/BILET
        # bilgi-istek dallarinin geri cekilme kosulu olarak) zaten hesaplandi;
        # burada AYNI degisken tekrar kullanilarak iki kontrolun birbirinden
        # SAPMASI (drift) engelleniyor.
        if is_actionable_transport_change:
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

        # Not: is_insurance_cancellation yukarida (Ek Hizmetler dalinin geri
        # cekilme kosulu olarak) zaten hesaplandi; ayni degisken tekrar
        # kullanilarak iki kontrolun birbirinden sapmasi (drift) engelleniyor.
        if is_insurance_cancellation:
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
        is_cancel_non_actionable = bool(
            EmailCategorizer.CANCEL_NON_ACTIONABLE_PATTERN.search(normalized_text)
        )
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.ROOM_TOPIC_KEYWORDS)
            and not is_cancel_non_actionable
            and (
                any(keyword in normalized_text for keyword in EmailCategorizer.CANCEL_INTENT_KEYWORDS)
                or EmailCategorizer.CANCEL_REQUEST_NOUN_PATTERN.search(normalized_text)
            )
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

        if (
            not is_cancel_non_actionable
            and any(keyword in normalized_text for keyword in EmailCategorizer.CANCEL_INTENT_KEYWORDS)
        ):
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
            (
                any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_COMPLETION_TOPIC_KEYWORDS)
                and any(keyword in normalized_text for keyword in EmailCategorizer.PAYMENT_COMPLETION_INTENT_KEYWORDS)
            )
            or EmailCategorizer.PAYMENT_COMPLETION_PATTERN.search(normalized_text)
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
        if (
            any(keyword in normalized_text for keyword in EmailCategorizer.RESERVATION_CHANGE_INFO_KEYWORDS)
            or EmailCategorizer.RESERVATION_CHANGE_INFO_PATTERN.search(normalized_text)
        ):
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


# Bu kutunun ilgilenmedigi B2B/tedarikci muhasebe yazismalari (ekstre/
# mutabakat/cari hesap) icin yonlendirilecek gercek muhasebe adresleri
# (kullanici tarafindan bildirildi).
VENDOR_FINANCE_REDIRECT_ADDRESSES = [
    "muhasebe@tatilbudur.com",
    "maliyetfatura@tatilbudur.com",
    "extranet@tatilbudur.com",
    "mutabakatjira@tatilbudur.com",
    "tatilbudur@mutabakat.com",
]


def send_vendor_redirect_email(recipient_email: str, subject: str, customer_name: str) -> None:
    """
    Otel/tedarikci muhasebe biriminden gelen ekstre/mutabakat/cari hesap
    yazismalarina, bu kutunun bu konularla ilgilenmedigini ve dogru
    adreslere yonlendirmelerini bildiren otomatik yanit gonderir. Ticket
    OLUSTURULMAZ.

    Args:
        recipient_email: Yaniti alacak gonderici adresi
        subject: Orijinal e-posta konusu
        customer_name: Gonderici adi
    """
    try:
        message = MIMEMultipart()
        message['From'] = EMAIL_USER
        message['To'] = recipient_email
        message['Subject'] = f"Re: {subject} - Yanlış Adres Yönlendirmesi"

        redirect_list_str = "\n".join([f"  • {addr}" for addr in VENDOR_FINANCE_REDIRECT_ADDRESSES])

        formatted_body = (
            f"Sayın {customer_name},\n\n"
            f"Bu e-posta adresi, ekstre/mutabakat/cari hesap gibi muhasebe "
            f"konularıyla ilgilenmemektedir.\n\n"
            f"Bu tarz maillerinizi lütfen aşağıdaki adreslerden ilgili olana "
            f"gönderiniz:\n\n"
            f"{redirect_list_str}\n\n"
            f"Anlayışınız için teşekkür ederiz.\n\n"
            f"Saygılarımızla,\n"
            f"Müşteri Hizmetleri Ekibi"
        )
        message.attach(MIMEText(formatted_body, 'plain', 'utf-8'))

        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, recipient_email, message.as_string())
        server.quit()

        print(f"↪️ [YÖNLENDİRME MAİLİ GÖNDERİLDİ] (B2B muhasebe yazışması) -> {recipient_email}")

    except Exception as e:
        print(f"❌ Yönlendirme maili gönderilirken hata: {e}")


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
