"""
Application Configuration Module

This module contains all constants, API endpoints, and configuration
settings for the email automation system.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==========================================
# EMAIL CONFIGURATION
# ==========================================
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", "")
IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

# ==========================================
# CSM AUTHENTICATION CONFIGURATION
# ==========================================
CSM_USERNAME = os.getenv("CSM_USERNAME", "")
CSM_PASSWORD = os.getenv("CSM_PASSWORD", "")

# ==========================================
# CSM API ENDPOINTS
# ==========================================
CSM_AUTH_URL = "https://tatilbudur-api.cloudcsmetiya.com/api/v1/auth/authenticate"
CSM_CREATE_TICKET_URL = "https://tatilbudur-api.cloudcsmetiya.com/api/v1/business/ticket/add"
CSM_CANCEL_TICKET_URL = "https://tatilbudur-api.cloudcsmetiya.com/api/v1/business/ticket/cancel"
CSM_SEARCH_PARTY_ROLES_URL = "https://tatilbudur-api.cloudcsmetiya.com/api/v1/business/partyRole/getPartyRoles"
CSM_BASE_URL = "https://tatilbudur-api.cloudcsmetiya.com"

# ==========================================
# CUSTOMER LOOKUP CONFIGURATION
# ==========================================
CUSTOMER_SEARCH_TYPE = "CUSTOMER"
CUSTOMER_CONTACT_MEDIUM_TYPE = "EMAIL"

# ==========================================
# CSM CHANNEL CONFIGURATION
# ==========================================
CHANNEL_ID = 100000043  # Email Channel ID

# ==========================================
# TICKET TYPE IDs
# ==========================================
TICKET_TYPE_THANK_YOU = 100000062
TICKET_TYPE_COMPLAINT = 100000061
TICKET_TYPE_INFO_REQUEST = 100000057
TICKET_TYPE_RESERVATION = 100000059  # Backoffice İşlemleri

# ==========================================
# CATEGORY IDs
# ==========================================
CATEGORY_THANK_YOU = 100000154
CATEGORY_COMPLAINT = 100000132
CATEGORY_FACILITY = 100000171
CATEGORY_AGENCY = 100000130
CATEGORY_ONLINE_OPERATIONS = 100000133
CATEGORY_TRANSPORT = 100000137

# RESERVATION CATEGORIES
CATEGORY_PAYMENT = 100000134               # Ödeme Sistemleri
CATEGORY_CONFIRMATION = 100000139         # Konfirme
CATEGORY_CHANGE = 100000140               # Değişiklik
CATEGORY_CANCELLATION = 100000141         # İptal
CATEGORY_ADDITIONAL_SERVICE = 100000142   # Ek Hizmet Ekleme/Çıkarma
CATEGORY_SHIFT = 100000143                # Kaydırma
CATEGORY_OTHER_OPERATIONS = 100000172     # Diğer İşlemler

# ==========================================
# SUB-CATEGORY IDs - THANK YOU
# ==========================================
SUB_CATEGORY_THANK_YOU_GENERAL = 100000618
SUB_CATEGORY_THANK_YOU_GUIDE = 100000617
SUB_CATEGORY_THANK_YOU_CONSULTANT = 100000616

# ==========================================
# SUB-CATEGORY IDs - COMPLAINT
# ==========================================
SUB_CATEGORY_COMPLAINT_DOCUMENT = 100000561
SUB_CATEGORY_COMPLAINT_INVOICE = 100000562

# ==========================================
# INVOICE RELATED IDs
# ==========================================
CATEGORY_INVOICE = 100000132
SUB_CATEGORY_GUEST_INVOICE = 100000523
SUB_CATEGORY_INVOICE_MODIFICATION = 100000525
SUB_CATEGORY_INVOICE_REQUEST = 100000562

# ==========================================
# SUB-CATEGORY IDs - FACILITY
# ==========================================
SUB_CATEGORY_FACILITY_CONTACT = 100000702

# ==========================================
# SUB-CATEGORY IDs - AGENCY
# ==========================================
SUB_CATEGORY_AGENCY_CONTACT_INFORMATION = 100000516
SUB_CATEGORY_MEMBERSHIP_PROCESSES = 100000526

# ==========================================
# SUB-CATEGORY IDs - TRANSPORT
# ==========================================
SUB_CATEGORY_TRANSPORT_TICKET = 100000534
SUB_CATEGORY_TRANSPORT_CHANGE_RIGHTS = 100000535
SUB_CATEGORY_TRANSPORT_BUS = 100000538

# ==========================================
# SUB-CATEGORY IDs - ŞİKAYET (ULAŞIM)
# ==========================================
SUB_CATEGORY_TRANSPORT_COMPLAINT_TRANSFER = 100000719               # Transfer
SUB_CATEGORY_TRANSPORT_COMPLAINT_OTHER = 100000539                  # Diğer

# ==========================================
# SUB-CATEGORY IDs - RESERVATION (PAYMENT)
# ==========================================
SUB_CATEGORY_PAYMENT_REFLECTION = 100000591  # Ödemenin Yansımaması

# ==========================================
# SUB-CATEGORY IDs - ŞİKAYET (ÖDEME SİSTEMLERİ)
# Not: "Ödemenin Yansımaması" (100000591) burada AYNI ID ile ama Backoffice
# yerine Şikayet ticket tipi altinda tekrar kullaniliyor -- CSM sisteminde
# ayni sub-category node'u farkli ticket tiplerinde tekrar etiketlenebiliyor.
# ==========================================
SUB_CATEGORY_PAYMENT_COMPLAINT_BANK_OBJECTION = 100000581     # Banka İtirazı
SUB_CATEGORY_PAYMENT_COMPLAINT_OVERCHARGE = 100000583         # Fazla Çekim
SUB_CATEGORY_PAYMENT_COMPLAINT_CAMPAIGN = 100000586           # Kampanya Uygulama
SUB_CATEGORY_PAYMENT_COMPLAINT_REFLECTION = 100000591         # Ödemenin Yansımaması (Şikayet)
SUB_CATEGORY_PAYMENT_COMPLAINT_PROVISION = 100000592          # Provizyon

# ==========================================
# SUB-CATEGORY IDs - RESERVATION (CONFIRMATION)
# ==========================================
SUB_CATEGORY_CONFIRMATION = 100000531       # Konfirme

# ==========================================
# SUB-CATEGORY IDs - RESERVATION (CHANGE/DEGISIKLIK)
# ==========================================
SUB_CATEGORY_CHANGE_PAYMENT_TYPE = 100000527         # Ödeme Tipi Değişikliği
SUB_CATEGORY_CHANGE_BIRTH_DATE = 100000540          # Doğum Tarihi Değişikliği
SUB_CATEGORY_CHANGE_EXTRA_SERVICES = 100000541      # Ek Hizmetler
SUB_CATEGORY_CHANGE_NAME = 100000542                # İsim Değişikliği
SUB_CATEGORY_CHANGE_PERSON_ADD_REMOVE = 100000543   # Kişi Ekleme/Çıkarma
SUB_CATEGORY_CHANGE_NOTE_ADD = 100000544            # Not Ekleme Talebi
SUB_CATEGORY_CHANGE_ROOM = 100000545                # Oda
SUB_CATEGORY_CHANGE_ROOM_TYPE = 100000546           # Oda Tipi Değişikliği
SUB_CATEGORY_CHANGE_HOTEL = 100000547               # Otel Değişikliği
SUB_CATEGORY_CHANGE_DATE = 100000548                # Tarih Değişikliği
SUB_CATEGORY_CHANGE_TOUR = 100000549                # Tur Değişikliği
SUB_CATEGORY_CHANGE_TRANSPORT = 100000550           # Ulaşım
SUB_CATEGORY_CHANGE_AIRPLANE_TICKET = 100000521    # Uçak Bileti
SUB_CATEGORY_CHANGE_OTHER = 100000539               # Diğer

# ==========================================
# SUB-CATEGORY IDs - RESERVATION (CANCELLATION)
# ==========================================
SUB_CATEGORY_CANCELLATION_ROOM = 100000545          # Oda
SUB_CATEGORY_CANCELLATION_REQUEST = 100000551       # İptal Talebi
SUB_CATEGORY_CANCELLATION_AIRPLANE = 100000521      # Uçak Bileti

# ==========================================
# SUB-CATEGORY IDs - RESERVATION (ADDITIONAL SERVICE)
# ==========================================
SUB_CATEGORY_ADDITIONAL_CANCELLATION_INSURANCE = 100000552  # İptal Sigortası

# ==========================================
# SUB-CATEGORY IDs - RESERVATION (SHIFT)
# ==========================================
SUB_CATEGORY_SHIFT_HOTEL_BASED = 100000669          # Otel Kaynaklı
SUB_CATEGORY_SHIFT_OPERATION_BASED = 100000671      # Operasyon Kaynaklı

# ==========================================
# SUB-CATEGORY IDs - RESERVATION (OTHER OPERATIONS)
# ==========================================
SUB_CATEGORY_OTHER_OPERATIONS_PAYMENT_COMPLETION = 100000554  # Ödeme Tamamlama

# ==========================================
# BILGI-İSTEK - EVRAK (kirilim.md kaynaklı)
# ==========================================
CATEGORY_DOCUMENT = 100000131                          # Evrak (Bilgi-İstek VE Şikayet ticket tiplerinde ortak kullanılıyor)
SUB_CATEGORY_DOCUMENT_CONTRACT = 100000519              # Sözleşme
SUB_CATEGORY_DOCUMENT_VISA_KIT = 100000522              # Vize Kiti
SUB_CATEGORY_DOCUMENT_BUS_DRIVER_INFO = 100000520       # Tur Otobüs Şoför Bilgileri
SUB_CATEGORY_DOCUMENT_COMPLAINT = 100000561             # Evrak (Şikayet)

# ==========================================
# BILGI-İSTEK - REZERVASYON (bilgi amaçlı, Backoffice'ten ayrı)
# ==========================================
CATEGORY_RESERVATION_INFO = 100000135                   # Rezervasyon
SUB_CATEGORY_RESERVATION_CHANGE_INFO = 100000529        # Değişiklik Bilgi Talebi
SUB_CATEGORY_RESERVATION_CANCELLATION_INFO = 100000530  # İptal Süreç Bilgisi
SUB_CATEGORY_RESERVATION_CONFIRMATION_INFO = 100000531  # Konfirme (Bilgi-İstek)

# ==========================================
# BILGI-İSTEK - ÖDEME SİSTEMLERİ KONULARI
# ==========================================
CATEGORY_PAYMENT_SYSTEMS_INFO = 100000189               # Ödeme Sistemleri Konuları
SUB_CATEGORY_REFUND_INFO = 100000733                    # İade Bilgisi

# ==========================================
# ŞİKAYET - OTEL
# ==========================================
CATEGORY_HOTEL = 100000147                              # Otel
SUB_CATEGORY_HOTEL_OPERATION = 100000720                # Operasyon
SUB_CATEGORY_HOTEL_SERVICES = 100000721                 # Otel Hizmetleri

# ==========================================
# ŞİKAYET - UÇAK
# ==========================================
CATEGORY_AIRPLANE = 100000151                           # Uçak
SUB_CATEGORY_AIRLINE_CHANGE = 100000596                 # Havayolu Değişikliği
SUB_CATEGORY_FLIGHT_TIME_CHANGE = 100000597             # Saat Değişikliği
SUB_CATEGORY_FLIGHT_CANCELLED = 100000598               # Sefer İptali

# ==========================================
# ŞİKAYET - BİLGİ TALEBİ
# ==========================================
CATEGORY_COMPLAINT_INFO_REQUEST = 100000170             # Bilgi Talebi
SUB_CATEGORY_RESERVATION_PROCESS = 100000667            # Rezervasyon İşlemi

# ==========================================
# ŞİKAYET - SATIŞ SÜRECİ
# ==========================================
CATEGORY_SALES_PROCESS = 100000174                      # Satış Süreci
SUB_CATEGORY_CALL_CENTER = 100000712                    # Çağrı Merkezi

# ==========================================
# ŞİKAYET - TUR ORGANİZASYONU VE REHBER
# ==========================================
CATEGORY_TOUR_AND_GUIDE = 100000176                     # Tur Organizasyonu ve Rehber
SUB_CATEGORY_TOUR_COMPLAINT = 100000722                 # Tur
SUB_CATEGORY_GUIDE_COMPLAINT = 100000723                # Rehber

# ==========================================
# ŞİKAYET - İADE
# ==========================================
CATEGORY_REFUND = 100000185                             # İade
SUB_CATEGORY_REFUND_NOT_MADE = 100000728                # İadenin Yapılmaması
SUB_CATEGORY_REFUND_REQUEST_NOT_OPENED = 100000729      # İade Talebinin Açılmamış Olması
SUB_CATEGORY_REFUND_NOT_REFLECTED = 100000730           # İadenin Misafire Yansımaması

# ==========================================
# ŞİKAYET - FİYATLANDIRMA
# ==========================================
CATEGORY_PRICING = 100000193                            # Fiyatlandırma
SUB_CATEGORY_BEST_PRICE_GUARANTEE = 100000582           # En İyi Fiyat Garantisi
SUB_CATEGORY_PRICE_GENERAL = 100000585                  # Fiyat Genel
SUB_CATEGORY_PRICE_DROP = 100000584                     # Ürün Fiyat Düşüşü
SUB_CATEGORY_PAYMENT_OBJECTION = 100000589              # Ödeme İtirazı

# ==========================================
# ATTRIBUTE IDs
# ==========================================
ATTRIBUTE_TRANSACTION_DATE = 100000037
ATTRIBUTE_CARD_FIRST_6 = 100000189
ATTRIBUTE_CARD_LAST_4 = 100000190
ATTRIBUTE_AMOUNT = 100000192
ATTRIBUTE_ORDER_NUMBER = 100000194
ATTRIBUTE_COMPANY_NAME = 100000230
ATTRIBUTE_PERSON_NAME = 100000237
ATTRIBUTE_INVOICE_ADDRESS = 100000233
ATTRIBUTE_EMAIL = 100000234
ATTRIBUTE_TAX_NUMBER = 100000235
ATTRIBUTE_TAX_ID_NUMBER = 100000236
ATTRIBUTE_WG_LIST = 100000057  # WG Listesi

# ==========================================
# TOKEN CACHE CONFIGURATION
# ==========================================
TOKEN_CACHE_DURATION_MINUTES = 55  # Refresh 5 minutes before expiry

# ==========================================
# HTTP HEADERS
# ==========================================
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr,en;q=0.9,en-US;q=0.8,tr-TR;q=0.7",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://tatilbudur-new-ui.cloudcsmetiya.com",
    "Referer": "https://tatilbudur-new-ui.cloudcsmetiya.com/",
    "userMode": "LEAD"
}

# ==========================================
# CONTENT VALIDATION
# ==========================================
PROFANITY_WORDS = [
    "orospu", "amk", "aq", "salak", "aptal", "mal", "yarrak",
    "fahişe", "piç", "göt", "sik", "sikim", "kahpe", "ibne",
    "puşt", "yavşak", "oğlan", "sürtük"
]

# ==========================================
# MAIL PROCESSING
# ==========================================
MAIL_BATCH_SIZE = 100  # Process emails in batches
MAIL_CHARSET_DEFAULT = 'utf-8'
MAIL_CHARSET_FALLBACK = 'iso-8859-9'
