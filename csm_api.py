"""
CSM API Module

Handles all interactions with the CSM (Customer Service Management) API.
"""

import requests
import json
from typing import Dict, Optional
from config import (
    CSM_CREATE_TICKET_URL, DEFAULT_HEADERS,
    TICKET_TYPE_COMPLAINT, TICKET_TYPE_THANK_YOU
)
from auth import get_bearer_token
from utils import parse_name_parts


class CSMAPIClient:
    """Client for CSM API operations."""
    
    def __init__(self):
        """Initialize CSM API client."""
        self.base_headers = DEFAULT_HEADERS.copy()
    
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
    
    def create_ticket(self, payload: Dict) -> bool:
        """
        Create a new ticket in CSM system.
        
        Args:
            payload: Ticket payload dictionary
            
        Returns:
            bool: True if successful, False otherwise
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
                        "Created"
                    )
                    print(f"🚀 [SUCCESS] Ticket created in CSM! Ticket ID: #{ticket_id}")
                except Exception:
                    print("🚀 [SUCCESS] Ticket created in CSM!")
                
                return True
            else:
                print(f"⚠️ [ERROR] CSM request failed. Status: {response.status_code}")
                print(f"Response: {response.text}")
                return False
        
        except Exception as e:
            print(f"❌ Error creating ticket: {e}")
            return False


class TicketPayloadBuilder:
    """Builder for constructing CSM ticket payloads."""
    
    @staticmethod
    def build_payload(
        sender_email: str,
        sender_name: str,
        subject: str,
        body: str,
        categorization: Dict
    ) -> Dict:
        """
        Build a complete ticket payload for CSM API.
        
        Args:
            sender_email: Customer email
            sender_name: Customer name
            subject: Ticket subject
            body: Ticket description
            categorization: Categorization dictionary from EmailCategorizer
            
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
        
        # Determine ticket type code
        ticket_type_code = "COMPLAINT" if categorization["ticket_type_id"] == TICKET_TYPE_COMPLAINT else "THANK_YOU"
        
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
                "uuid": "a8e13665-8d0c-41bc-b3f7-c2ce489d2458"
            },
            "category": {
                "shortCode": "GENERAL",
                "name": "General",
                "id": categorization["category_id"],
                "uuid": "5e9ef86d-90d3-4efc-a8f4-dbd29eb132ea"
            },
            "ticketType": {
                "shortCode": ticket_type_code,
                "name": categorization.get("ticket_type_name", "General"),
                "id": categorization["ticket_type_id"],
                "uuid": "a01dabb1-c18d-4781-80ab-ed2bdf841d1f"
            },
            "priorityLevel": {
                "shortCode": "NORMAL",
                "name": "Normal",
                "ordinal": 3,
                "id": 100000037,
                "uuid": "074266b0-efdf-45a1-ab26-75a627a4b5ed"
            },
            "isResolved": False,
            "isProactive": False,
            "isParent": True,
            "reminders": [],
            "detectedLanguage": ""
        }
        
        return payload
