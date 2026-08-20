"""
Validators Module

Contains all validation functions for user data, Turkish ID numbers,
and email content validation.
"""

import re
from typing import Tuple, List
from config import PROFANITY_WORDS
from utils import normalize_turkish_characters


def _is_placeholder_value(value: str) -> bool:
    normalized_value = normalize_turkish_characters(value).strip()
    return "buraya" in normalized_value or normalized_value in {"yaz", "girilmedi", "belirtilmedi"}


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
    
    person_name_match = re.search(
        r'(?:^\s*(?:[-*]\s+)?|\s)(?:şahıs\s*adı|sahis\s*adi|ad\s*soyad|isim|mükellef)\s*:\s*'
        r'\[?([a-zA-ZğüşıöçĞÜŞİÖÇ\s]+?)\]?(?=\s*(?:,\s*)?(?:vergi\s*kimlik|vkn|tc\s*kimlik|fatura\s*adresi|e-?posta)|\r?\n|$)',
        text,
        re.IGNORECASE | re.MULTILINE
    )
    company_name_match = re.search(
        r'(?:^\s*(?:[-*]\s+)?|\s)(?:şirket\s*adı|sirket\s*adi|firma|ünvan|unvan)\s*:\s*'
        r'\[?([^\r\n\],]+)\]?(?=\s*(?:,\s*)?(?:vergi\s*kimlik|vkn|tc\s*kimlik|fatura\s*adresi|e-?posta)|\r?\n|$)',
        text,
        re.IGNORECASE | re.MULTILINE
    )

    if person_name_match and not _is_placeholder_value(person_name_match.group(1)):
        person_name = person_name_match.group(1).strip()
        attribute_list.append({
            "attribute": {
                "id": 100000230,
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
    elif company_name_match:
        company_name = company_name_match.group(1).strip()
        attribute_list.append({
            "attribute": {
                "id": 100000230,
                "shortCode": "SIRKET_ADI_SAHIS_ADI"
            },
            "lovItem": {
                "id": 100054902,
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
    tc_match = re.search(
        r'(?:tc|tckn|tc\s*no|tc\s*kimlik\s*numarası|tc\s*kimlik\s*numarasi|kimlik\s*no)[:\s]*\[?(\d+)\]?',
        text,
        re.IGNORECASE
    )
    tax_match = re.search(
        r'(?:vkn|vergi\s*no|vergi\s*kimlik(?:\s*numarası|\s*numarasi)?)[:\s]*\[?(\d+)\]?',
        text,
        re.IGNORECASE
    )
    
    if tc_match:
        tc_value = tc_match.group(1)
        if is_valid_turkish_id(tc_value):
            attribute_list.append({
                "attribute": {
                    "id": 100000231,
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
                    "id": 100000231,
                    "shortCode": "VERGI_NUMARASI_TC_NUMARASI"
                },
                "lovItem": {
                    "id": 100054901,
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
    else:
        missing_fields.append("TC Kimlik Numarası veya VKN")

    if tax_match:
        tax_office_match = re.search(
            r'(?:vergi\s*dairesi|vergi\s*daire)\s*:\s*\[?([^\r\n\],]+)\]?(?=\s*(?:,\s*)?(?:fatura\s*adresi|e-?posta)|\r?\n|$)',
            text,
            re.IGNORECASE
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
    
    # Try pattern 1: "Fatura Adresi:" followed by content until next field or line break
    address_match = re.search(
        r'(?:fatura\s*adresi|adres)[:\s]*'
        r'([a-zA-ZğüşıöçĞÜŞİÖÇ0-9\s/.,:-]+?)(?=\s*(?:,\s*)?(?:fatura\s*mail|fatura\s*e-posta|mail|e-posta)|\r?\n\s*(?:fatura\s*mail|fatura\s*e-posta|mail|e-posta|iyi|saygılarla|$)|$)',
        text,
        re.IGNORECASE | re.MULTILINE
    )
    
    # Try pattern 2: Simple "Fatura Adresi:" with end of line
    if not address_match:
        address_match = re.search(
            r'(?:fatura\s*adresi|adres)[:\s]*([^\n]+)',
            text,
            re.IGNORECASE
        )
    
    # Try pattern 3: Capture multi-line address (handle line breaks)
    if not address_match:
        address_match = re.search(
            r'(?:fatura\s*adresi|adres)[:\s]*\n\s*(.+?)(?:\n\s*\n|\n\s*(?:fatura|mail|e-posta|tc|vkn))',
            text,
            re.IGNORECASE | re.DOTALL
        )
    
    if address_match:
        invoice_address = address_match.group(1).strip()
        # Remove email patterns that might be attached
        invoice_address = re.split(
            r'\s*(?:fatura\s*mail|fatura\s*e-posta|mail|e-posta).*',
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
    email_match = re.search(
        r'(?:fatura\s*e-?posta|fatura\s*mail|e-?posta|mail)[:\s]*\[?'
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\]?',
        text,
        re.IGNORECASE
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
