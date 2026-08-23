"""
CSM API Module

Handles all interactions with the CSM (Customer Service Management) API.
"""

import requests
import json
from typing import Dict, Optional, List
from config import (
    CSM_CREATE_TICKET_URL, DEFAULT_HEADERS,
    CSM_SEARCH_PARTY_ROLES_URL, CSM_SEARCH_PRODUCT_URL,
    TICKET_TYPE_COMPLAINT, TICKET_TYPE_THANK_YOU, TICKET_TYPE_INFO_REQUEST,
    CATEGORY_INVOICE, CATEGORY_THANK_YOU, CATEGORY_AGENCY,
    SUB_CATEGORY_GUEST_INVOICE, SUB_CATEGORY_INVOICE_MODIFICATION,
    CUSTOMER_SEARCH_TYPE, CUSTOMER_CONTACT_MEDIUM_TYPE
)
from auth import get_bearer_token
from utils import parse_name_parts


class CSMAPIClient:
    """Client for CSM API operations."""
    
    def __init__(self):
        """Initialize CSM API client."""
        self.base_headers = DEFAULT_HEADERS.copy()
        self.last_error = ""
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers with valid bearer token.
        
        Returns:
            Dictionary of HTTP headers
        """
        headers = self.base_headers.copy()
        token = get_bearer_token()
        headers["Authorization"] = f"Bearer {token}"
        headers["Multilanguage"] = "true"
        # Note: Do NOT set Content-Type here when using multipart/form-data
        # requests library will set it automatically
        
        return headers
    
    def search_customer_by_email(self, email: str) -> Optional[Dict]:
        """
        Search for customer in database by email address.
        
        Args:
            email: Customer email address
            
        Returns:
            Dict with customer info if found, None otherwise
            Contains: id, firstName, lastName, email
        """
        try:
            headers = self._get_headers()
            
            # Build query parameters
            params = {
                'searchType': CUSTOMER_SEARCH_TYPE,
                'contactMediumType': CUSTOMER_CONTACT_MEDIUM_TYPE,
                'contactMediumValue': email
            }
            
            response = requests.get(
                CSM_SEARCH_PARTY_ROLES_URL,
                headers=headers,
                params=params
            )
            
            # Status 204 = No Content (customer not found)
            if response.status_code == 204:
                print(f"ℹ️ [BİLGİ] Müşteri veritabanında bulunamadı: {email}")
                return None
            
            # Status 200 = Customer found
            if response.status_code == 200:
                # Check if response has content
                if not response.text or response.text.strip() == '':
                    print(f"ℹ️ [BİLGİ] Boş yanıt - müşteri bulunamadı: {email}")
                    return None
                
                try:
                    response_data = response.json()
                    # API returns array of results
                    if isinstance(response_data, list) and len(response_data) > 0:
                        customer = response_data[0]
                        print(f"✅ [BULUNDU] Veritabanında müşteri: {email}")
                        return {
                            'id': customer.get('id'),
                            'firstName': customer.get('party', {}).get('firstName', ''),
                            'lastName': customer.get('party', {}).get('lastName', ''),
                            'email': email,
                            'fullData': customer
                        }
                    else:
                        print(f"ℹ️ [BİLGİ] Boş sonuç listesi - müşteri bulunamadı: {email}")
                        return None
                except Exception as e:
                    print(f"⚠️ [UYARI] Müşteri verisi ayrıştırılamadı: {e}")
                    return None
            else:
                print(f"⚠️ [HATA] Müşteri arama başarısız. Status: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ Müşteri aranırken hata: {e}")
            return None

    def search_product_by_reservation_number(self, reservation_number: str) -> Optional[List[Dict]]:
        """
        Mailde gecen rezervasyon numarasina karsilik gelen urun (otel/tur/vs.)
        kaydini CSM/Etiya'dan arar. Bu kayit, ticket olusturulurken hem
        "ticketProductId" hem de "relatedProduct" alanlarini doldurmak icin
        kullanilir -- aksi halde backoffice ekibi ticket icinde ilgili urune
        erisemiyor (canli ortamda musteri temsilcisinin "rezervasyon numarasi
        paylasabilir misiniz" diye geri donmesiyle tespit edildi).

        Args:
            reservation_number: Mailde gecen rezervasyon/hesap numarasi

        Returns:
            Bulunan urun kayitlarinin listesi (bos olabilir), hata durumunda None
        """
        try:
            headers = self._get_headers()
            params = {'customerId': reservation_number}

            response = requests.get(
                CSM_SEARCH_PRODUCT_URL,
                headers=headers,
                params=params
            )

            if response.status_code == 204:
                print(f"ℹ️ [BİLGİ] Rezervasyon numarasına ait ürün bulunamadı: {reservation_number}")
                return []

            if response.status_code == 200:
                if not response.text or response.text.strip() == '':
                    return []
                products = response.json()
                if isinstance(products, list):
                    print(f"✅ [BULUNDU] {len(products)} ürün kaydı: {reservation_number}")
                    return products
                return []

            print(f"⚠️ [HATA] Ürün arama başarısız. Status: {response.status_code}")
            return None

        except Exception as e:
            print(f"❌ Ürün aranırken hata: {e}")
            return None

    def create_ticket(self, payload: Dict) -> Optional[str]:
        """
        Create a new ticket in CSM system.
        
        Args:
            payload: Ticket payload dictionary
            
        Returns:
            str: Ticket ID if successful, None otherwise
        """
        try:
            headers = self._get_headers()
            
            # CSM API expects JSON in multipart form
            payload_json = json.dumps(payload, ensure_ascii=False)
            files = {
                'ticket': ('blob', payload_json.encode('utf-8'), 'application/json; charset=utf-8')
            }
            
            response = requests.post(
                CSM_CREATE_TICKET_URL,
                files=files,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                try:
                    response_data = response.json()
                    ticket_id = (
                        response_data.get("id") or
                        response_data.get("ticketNo") or
                        response_data.get("idNum") or
                        "Oluşturuldu"
                    )
                    print(f"🚀 [BAŞARILI] CSM'de Ticket oluşturuldu! Ticket ID: #{ticket_id}")
                    return str(ticket_id)
                except Exception as e:
                    print(f"🚀 [BAŞARILI] CSM'de Ticket oluşturuldu!")
                    return "Oluşturuldu"
            else:
                self.last_error = f"HTTP {response.status_code}: {response.text}"
                print(f"⚠️ [HATA] CSM isteği başarısız. Status: {response.status_code}")
                print(f"Yanıt: {response.text}")
                return None
        
        except Exception as e:
            self.last_error = str(e)
            print(f"❌ Ticket oluşturulurken hata: {e}")
            return None


class TicketPayloadBuilder:
    """Builder for constructing CSM ticket payloads."""
    
    @staticmethod
    def build_payload(
        sender_email: str,
        sender_name: str,
        subject: str,
        body: str,
        categorization: Dict,
        customer_id: Optional[int] = None,
        related_product: Optional[Dict] = None
    ) -> Dict:
        """
        Build a complete ticket payload for CSM API.
        
        Args:
            sender_email: Customer email
            sender_name: Customer name
            subject: Ticket subject
            body: Ticket description
            categorization: Categorization dictionary from EmailCategorizer
            customer_id: Optional customer ID (if registered customer)
            
        Returns:
            Complete ticket payload dictionary
        """
        # Parse sender name
        first_name, last_name = parse_name_parts(sender_name if sender_name else "User Guest")
        
        # Build contact medium
        contact_medium = {
            "contactMediumType": {
                "id": 10000005,
                "uuid": "c38936ac-7e2c-46e7-aacc-deca59e132bf",
                "shortCode": "EMAIL"
            },
            "val": sender_email,
            "isPrimary": True,
            "externalId": None
        }
        
        # Build party role
        party_role = {
            "party": {
                "firstName": first_name,
                "lastName": last_name,
                "nationalityId": None,
                "partyType": "INDIVIDUAL",
                "fullName": f"{first_name} {last_name}",
                "preferredLanguage": {
                    "country": None,
                    "createDate": "2021-06-23T20:39:15.028Z",
                    "displayLanguage": "Turkish",
                    "id": 1000001,
                    "language": "tr",
                    "rtl": None,
                    "status": 1,
                    "updateDate": None
                }
            },
            "partyRoleType": {
                "id": 1000022,
                "uuid": "4b7fc8ce-289c-476f-92d0-9279e7199983",
                "shortCode": "CSM_USER",
                "ownerType": True
            },
            "externalId": None,
            "attributeValueList": [],
            "contactMediumList": [contact_medium]
        }
        
        # Add customer ID if this is a registered customer
        if customer_id is not None:
            party_role["id"] = customer_id
            print(f"✅ [KAYITLI] Kayıtlı müşteri ID ekleniyor: {customer_id}")
        else:
            print(f"🆕 [POTANSİYEL] Yeni potansiyel müşteri kaydı oluşturuluyor")
        
        ticket_type_codes = {
            TICKET_TYPE_COMPLAINT: "COMPLAINT",
            TICKET_TYPE_THANK_YOU: "TESEKKUR",
            TICKET_TYPE_INFO_REQUEST: "BILGI_ISTEK",
        }
        ticket_type_code = ticket_type_codes.get(categorization["ticket_type_id"], "BILGI_ISTEK")
        category_codes = {
            CATEGORY_INVOICE: "FATURA",
            CATEGORY_THANK_YOU: "TESEKKUR",
            CATEGORY_AGENCY: "ACENTE",
        }
        category_code = category_codes.get(categorization["category_id"], "TESIS")
        category_uuid = (
            "0ccfc115-fc6a-4e0b-ae08-857b8cbf994c"
            if categorization["category_id"] == CATEGORY_INVOICE
            else "5e9ef86d-90d3-4efc-a8f4-dbd29eb132ea"
        )
        subcategory_uuids = {
            SUB_CATEGORY_GUEST_INVOICE: "d3b400ea-9276-4dd6-aad4-b95b9ddce030",
            SUB_CATEGORY_INVOICE_MODIFICATION: "565227a6-c991-47f1-b138-c77aaccee869",
        }
        subcategory_uuid = subcategory_uuids.get(
            categorization["sub_category_id"],
            "a8e13665-8d0c-41bc-b3f7-c2ce489d2458"
        )
        ticket_type_uuid = (
            "6ed921e1-56f3-4743-b8af-c0c616cd0950"
            if categorization["ticket_type_id"] == TICKET_TYPE_INFO_REQUEST
            else "a01dabb1-c18d-4781-80ab-ed2bdf841d1f"
        )
        
        # Build complete payload
        payload = {
            "contactParties": [
                {
                    "partyRole": party_role,
                    "contactMediumList": [
                        {
                            "contactMedium": contact_medium,
                            "isPreferred": True
                        }
                    ],
                    "isPreferred": True,
                    "preferredContactChannelList": ["EMAIL"]
                }
            ],
            "attributeList": categorization.get("attributes", []),
            "attributeSetList": [
                {
                    "attributeSet": {"shortCode": "REKLAMASYON"},
                    "attributeList": []
                }
            ],
            "ticketRelationList": [],
            "subTicketList": [],
            "availableOperations": [],
            "stage": {"shortCode": "START"},
            "partyRole": party_role,
            "description": body,
            "channel": {
                "shortCode": "MAIL",
                "name": "Email",
                "id": categorization["channel_id"],
                "uuid": "e0ebda2b-28da-4ee7-a5c9-1d111e72e232"
            },
            "subCategory": {
                "shortCode": categorization["sub_category_code"],
                "name": categorization.get("sub_category_name", "General"),
                "id": categorization["sub_category_id"],
                "uuid": subcategory_uuid
            },
            "category": {
                "shortCode": category_code,
                "name": categorization.get("category_name", "Genel"),
                "id": categorization["category_id"],
                "uuid": category_uuid
            },
            "ticketType": {
                "shortCode": ticket_type_code,
                "name": categorization.get("ticket_type_name", "General"),
                "id": categorization["ticket_type_id"],
                "uuid": ticket_type_uuid
            },
            "priorityLevel": (
                {
                    "shortCode": "OPSIYONLU",
                    "name": "Opsiyonlu",
                    "ordinal": 5,
                    "id": 100000039,
                    "uuid": "e4486839-eb48-4647-85a7-c988f47c6920"
                }
                if categorization.get("priority_level") == "OPSIYONLU"
                else {
                    "shortCode": "NORMAL",
                    "name": "Normal",
                    "ordinal": 3,
                    "id": 100000037,
                    "uuid": "074266b0-efdf-45a1-ab26-75a627a4b5ed"
                }
            ),
            "isResolved": False,
            "isProactive": False,
            "isParent": True,
            "reminders": [],
            "detectedLanguage": ""
        }

        # Not: mailde rezervasyon numarasi bulunup CSM'den ilgili urun kaydi
        # cekilebildiyse, ticket'a "ticketProductId" ve "relatedProduct"
        # olarak gomuluyor -- aksi halde backoffice ekibi ticket icinde ilgili
        # rezervasyona/urune erisemiyor (canli ortamda gozlemlendi, gercek
        # CSM UI'sinin urettigi payload'dan birebir alindi).
        if related_product:
            payload["ticketProductId"] = related_product.get("productId")
            payload["relatedProduct"] = {
                **related_product,
                "relatedInvoices": related_product.get("relatedInvoices", []),
                "uniqueRowId": (
                    f"{related_product.get('productId')}_"
                    f"{related_product.get('parentProductId')}_"
                    f"{related_product.get('serviceNumber')}"
                )
            }

        return payload
