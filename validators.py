"""
Validators Module

Contains all validation functions for user data, Turkish ID numbers,
and email content validation.
"""

import re
from typing import Tuple, List
from config import PROFANITY_WORDS
from utils import normalize_turkish_characters


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
        pattern = r'\b' + re.escape(normalized_word) + r'\b'
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
    attribute_list = []
    missing_fields = []
    
    # Extract person name
    name_match = re.search(
        r'(?:şahıs\s*adı|sahis\s*adi|ad\s*soyad|isim|mükellef)[:\s]*'
        r'([a-zA-ZğüşıöçĞÜŞİÖÇ\s]+?)(?:\r?\n|tc|vkn|fatura|$)',
        text,
        re.IGNORECASE
    )
    
    if name_match:
        person_name = name_match.group(1).strip()
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
    else:
        missing_fields.append("Person Name-Surname")
    
    # Extract Turkish ID or Tax ID
    tc_match = re.search(
        r'(?:tc|tckn|tc\s*no|kimlik\s*no)[:\s]*(\d{11})\b',
        text,
        re.IGNORECASE
    )
    tax_match = re.search(
        r'(?:vkn|vergi\s*no|vergi\s*kimlik)[:\s]*(\d{10})\b',
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
            missing_fields.append("Valid Turkish ID Number")
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
            missing_fields.append("Valid Tax ID Number (VKN)")
    else:
        missing_fields.append("Turkish ID or Tax ID (VKN)")
    
    # Extract invoice address
    address_match = re.search(
        r'(?:fatura\s*adresi|adres)[:\s]*'
        r'([a-zA-ZğüşıöçĞÜŞİÖÇ0-9\s/.,:-]+?)(?=\r?\n\s*(?:fatura\s*mail|mail|iyi|saygılarla|$))',
        text,
        re.IGNORECASE
    )
    
    if not address_match:
        address_match = re.search(
            r'(?:fatura\s*adresi|adres)[:\s]*([^\n]+)',
            text,
            re.IGNORECASE
        )
    
    if address_match:
        invoice_address = address_match.group(1).strip()
        invoice_address = re.split(
            r'fatura\s*mail|mail:',
            invoice_address,
            flags=re.IGNORECASE
        )[0].strip()
        
        attribute_list.append({
            "attribute": {
                "id": 100000233,
                "shortCode": "FATURA_ADRESI"
            },
            "textValue": invoice_address
        })
    else:
        missing_fields.append("Invoice Address")
    
    # Extract email address
    email_match = re.search(
        r'(?:fatura\s*e-?posta|fatura\s*mail|mail)[:\s]*'
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        text,
        re.IGNORECASE
    )
    
    invoice_email = email_match.group(1) if email_match else sender_email
    attribute_list.append({
        "attribute": {
            "id": 100000234,
            "shortCode": "E-_POSTA"
        },
        "textValue": invoice_email
    })
    
    return attribute_list, missing_fields
