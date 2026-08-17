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
CSM_BASE_URL = "https://tatilbudur-api.cloudcsmetiya.com"

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

# ==========================================
# CATEGORY IDs
# ==========================================
CATEGORY_THANK_YOU = 100000154
CATEGORY_COMPLAINT = 100000132
CATEGORY_FACILITY = 100000171

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
# FACILITY RELATED IDs
# ==========================================
SUB_CATEGORY_FACILITY_CONTACT = 100000702

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
