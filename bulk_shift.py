"""Toplu Kaydırma (Bulk Reservation Shift) module.

Creates CSM sub-tickets in bulk, linked to a parent ticket, from an uploaded
Excel export of reservations that need a date shift. Ported from a standalone
desktop RPA script (task/rpa_otomasyon.py, task/rpa.txt) into the Enigma
panel so it runs through the web UI instead of a local Python script with a
hardcoded bearer token and hardcoded reporter identity.

Environment: defaults to PRE-PROD (see BULK_SHIFT_ENV). PROD_MAPPINGS now
carries the same category/channel/ticketType ids as PREPROD_MAPPINGS —
cross-checked against config.py's production category ids (identical) — but
this has not yet been confirmed end-to-end with a real production request.
Verify with one row before trusting it for a full batch, then set
BULK_SHIFT_ENV=prod to actually target production.
"""

import os
from typing import Any, BinaryIO, Dict, List, Optional, TypedDict

import requests
from openpyxl import load_workbook

from service_log import record_service_event

MAX_ROWS = 500

# Original script's column names (Turkish, exact match from the source Excel export).
COLUMN_ALIASES = {
    "reservation_no": ("Rezervasyon No",),
    "shift_type": ("Kaydırma Tipi",),
    "alternative": ("Alternatif 1",),
}


class ExcelRow(TypedDict):
    reservation_no: str
    shift_type: str
    alternative: str


def parse_excel_rows(file_stream: BinaryIO) -> List[ExcelRow]:
    """Read the uploaded Excel export into plain dicts.

    Raises ValueError if required columns are missing or the sheet has more
    than MAX_ROWS data rows (a hard cap — this endpoint processes rows
    synchronously, one HTTP request per row to CSM, so an unbounded upload
    would tie up a request/worker for an unbounded amount of time).
    """
    workbook = load_workbook(filename=file_stream, data_only=True, read_only=True)
    sheet = workbook.active

    header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if not header_row:
        raise ValueError("Excel dosyası boş görünüyor.")

    header_index = {
        str(cell).strip(): idx for idx, cell in enumerate(header_row) if cell is not None
    }

    column_positions: Dict[str, int] = {}
    for field, aliases in COLUMN_ALIASES.items():
        match = next((a for a in aliases if a in header_index), None)
        if match is None:
            raise ValueError(f"Beklenen sütun bulunamadı: '{aliases[0]}'")
        column_positions[field] = header_index[match]

    rows: List[ExcelRow] = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row is None or all(cell is None for cell in row):
            continue
        if len(rows) >= MAX_ROWS:
            raise ValueError(f"Excel dosyası {MAX_ROWS} satırdan fazla içeriyor — daha küçük parçalara bölün.")

        def cell(field: str) -> str:
            pos = column_positions[field]
            value = row[pos] if pos < len(row) else None
            return "" if value is None else str(value).strip()

        reservation_no = cell("reservation_no")
        if not reservation_no:
            continue

        rows.append(
            ExcelRow(
                reservation_no=reservation_no,
                shift_type=cell("shift_type") or "Operasyon Kaynaklı",
                alternative=cell("alternative") or "Toplu Kaydırma İşlemi",
            )
        )

    return rows

BULK_SHIFT_ENV = os.getenv("BULK_SHIFT_ENV", "preprod")

_ENV_URLS = {
    "preprod": {
        "auth": "https://tatilbudur-pp-api.cloudcsmetiya.com/api/v1/auth/authenticate",
        "create_ticket": "https://tatilbudur-pp-api.cloudcsmetiya.com/api/v1/business/ticket/add",
    },
    "prod": {
        "auth": "https://tatilbudur-api.cloudcsmetiya.com/api/v1/auth/authenticate",
        "create_ticket": "https://tatilbudur-api.cloudcsmetiya.com/api/v1/business/ticket/add",
    },
}

# Verified against the pre-prod CSM environment (source: task/rpa_otomasyon.py).
PREPROD_MAPPINGS = {
    "OPERASYON_KAYNAKLI": {
        "channel": {"shortCode": "CAGRI_MERKEZI", "name": "Çağrı Merkezi", "id": 100000041, "uuid": "9a4dd8ef-045a-4f57-8c2c-8b0fc209d367"},
        "ticketType": {"shortCode": "REZERVASYON_ISLEMLERI", "name": "Backoffice İşlemleri", "id": 100000059, "uuid": "654c901c-40c2-46c1-8a00-925009dde46e"},
        "category": {"shortCode": "KAYDIRMA", "name": "Kaydırma", "id": 100000143, "uuid": "f3a9a508-0732-4410-82d7-847867fc616f"},
        "subCategory": {"shortCode": "OPERASYON_KAYNAKLI", "name": "Operasyon Kaynaklı", "id": 100000671, "uuid": "089de3d8-b26d-42da-88e6-f062cae187f3"},
    },
    "OTEL_KAYNAKLI": {
        "channel": {"shortCode": "CAGRI_MERKEZI", "name": "Çağrı Merkezi", "id": 100000041, "uuid": "9a4dd8ef-045a-4f57-8c2c-8b0fc209d367"},
        "ticketType": {"shortCode": "REZERVASYON_ISLEMLERI", "name": "Backoffice İşlemleri", "id": 100000059, "uuid": "654c901c-40c2-46c1-8a00-925009dde46e"},
        "category": {"shortCode": "KAYDIRMA", "name": "Kaydırma", "id": 100000143, "uuid": "f3a9a508-0732-4410-82d7-847867fc616f"},
        "subCategory": {"shortCode": "OTEL_KAYNAKLI", "name": "Otel Kaynaklı", "id": 100000669, "uuid": "089de3d8-b26d-42da-88e6-f062cae187f3"},
    },
    "ODEME_TAMAMLAMA": {
        "channel": {"shortCode": "CAGRI_MERKEZI", "name": "Çağrı Merkezi", "id": 100000041, "uuid": "9a4dd8ef-045a-4f57-8c2c-8b0fc209d367"},
        "ticketType": {"shortCode": "REZERVASYON_ISLEMLERI", "name": "Backoffice İşlemleri", "id": 100000059, "uuid": "654c901c-40c2-46c1-8a00-925009dde46e"},
        "category": {"shortCode": "DIGER_ISLEMLER", "name": "Diğer İşlemler", "id": 100000172, "uuid": "f3a9a508-0732-4410-82d7-847867fc616f"},
        "subCategory": {"shortCode": "ODEME_TAMAMLAMA", "name": "Ödeme Tamamlama", "id": 100000554, "uuid": "089de3d8-b26d-42da-88e6-f062cae187f3"},
    },
}

# Same category/channel/ticketType ids as PREPROD_MAPPINGS above — cross-checked
# against config.py's CATEGORY_SHIFT/SUB_CATEGORY_SHIFT_*/TICKET_TYPE_RESERVATION/
# CATEGORY_OTHER_OPERATIONS/SUB_CATEGORY_OTHER_OPERATIONS_PAYMENT_COMPLETION, which
# are the ids the main app already uses when creating real tickets against
# tatilbudur-api.cloudcsmetiya.com (production). They match exactly, and the
# priorityLevel uuid in build_bulk_ticket_payload also matches the one csm_api.py
# uses in production — so this tenant's category/channel/priority reference data
# is shared between preprod and production. Not yet confirmed end-to-end with a
# real production request — verify with one row before relying on this.
PROD_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "OPERASYON_KAYNAKLI": {
        "channel": {"shortCode": "CAGRI_MERKEZI", "name": "Çağrı Merkezi", "id": 100000041, "uuid": "9a4dd8ef-045a-4f57-8c2c-8b0fc209d367"},
        "ticketType": {"shortCode": "REZERVASYON_ISLEMLERI", "name": "Backoffice İşlemleri", "id": 100000059, "uuid": "654c901c-40c2-46c1-8a00-925009dde46e"},
        "category": {"shortCode": "KAYDIRMA", "name": "Kaydırma", "id": 100000143, "uuid": "f3a9a508-0732-4410-82d7-847867fc616f"},
        "subCategory": {"shortCode": "OPERASYON_KAYNAKLI", "name": "Operasyon Kaynaklı", "id": 100000671, "uuid": "089de3d8-b26d-42da-88e6-f062cae187f3"},
    },
    "OTEL_KAYNAKLI": {
        "channel": {"shortCode": "CAGRI_MERKEZI", "name": "Çağrı Merkezi", "id": 100000041, "uuid": "9a4dd8ef-045a-4f57-8c2c-8b0fc209d367"},
        "ticketType": {"shortCode": "REZERVASYON_ISLEMLERI", "name": "Backoffice İşlemleri", "id": 100000059, "uuid": "654c901c-40c2-46c1-8a00-925009dde46e"},
        "category": {"shortCode": "KAYDIRMA", "name": "Kaydırma", "id": 100000143, "uuid": "f3a9a508-0732-4410-82d7-847867fc616f"},
        "subCategory": {"shortCode": "OTEL_KAYNAKLI", "name": "Otel Kaynaklı", "id": 100000669, "uuid": "089de3d8-b26d-42da-88e6-f062cae187f3"},
    },
    "ODEME_TAMAMLAMA": {
        "channel": {"shortCode": "CAGRI_MERKEZI", "name": "Çağrı Merkezi", "id": 100000041, "uuid": "9a4dd8ef-045a-4f57-8c2c-8b0fc209d367"},
        "ticketType": {"shortCode": "REZERVASYON_ISLEMLERI", "name": "Backoffice İşlemleri", "id": 100000059, "uuid": "654c901c-40c2-46c1-8a00-925009dde46e"},
        "category": {"shortCode": "DIGER_ISLEMLER", "name": "Diğer İşlemler", "id": 100000172, "uuid": "f3a9a508-0732-4410-82d7-847867fc616f"},
        "subCategory": {"shortCode": "ODEME_TAMAMLAMA", "name": "Ödeme Tamamlama", "id": 100000554, "uuid": "089de3d8-b26d-42da-88e6-f062cae187f3"},
    },
}

_cached_token: Optional[str] = None


class Reporter(TypedDict):
    first_name: str
    last_name: str
    phone: str
    email: str


def _mappings_for_env() -> Dict[str, Dict[str, Any]]:
    if BULK_SHIFT_ENV == "prod":
        if not PROD_MAPPINGS:
            raise RuntimeError(
                "PROD_MAPPINGS henüz doldurulmadı — BULK_SHIFT_ENV='prod' için "
                "doğrulanmış production kategori/kanal/ticketType ID'leri gerekli."
            )
        return PROD_MAPPINGS
    return PREPROD_MAPPINGS


def classify_shift_type(kaydirma_tipi: str) -> str:
    """Mirrors the original script's keyword-based classification."""
    text = (kaydirma_tipi or "").strip()
    if "Otel" in text:
        return "OTEL_KAYNAKLI"
    if "Ödeme" in text or "Tamamlama" in text:
        return "ODEME_TAMAMLAMA"
    return "OPERASYON_KAYNAKLI"


def get_bulk_shift_token(force_refresh: bool = False) -> str:
    """Get a bearer token for the configured environment (BULK_SHIFT_ENV).

    Reuses the same CSM_USERNAME/CSM_PASSWORD as the main app (matching the
    original script's behavior) — just against the pre-prod auth URL.
    """
    global _cached_token
    if _cached_token and not force_refresh:
        return _cached_token

    from config import CSM_USERNAME, CSM_PASSWORD

    if not CSM_USERNAME or not CSM_PASSWORD:
        raise RuntimeError("CSM_USERNAME / CSM_PASSWORD ortam değişkenleri ayarlanmamış.")

    auth_url = _ENV_URLS[BULK_SHIFT_ENV]["auth"]
    try:
        response = requests.post(
            auth_url,
            json={"userName": CSM_USERNAME, "password": CSM_PASSWORD},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        if response.status_code != 200:
            record_service_event(
                "csm_api", "auth", "failed",
                detail=f"[{BULK_SHIFT_ENV.upper()}] HTTP {response.status_code}",
            )
            raise RuntimeError(f"Token alınamadı. Status Code: {response.status_code}")

        auth_header = response.headers.get("authorization") or response.headers.get("Authorization") or ""
        if auth_header:
            token = auth_header.replace("Bearer ", "").replace("bearer ", "").strip()
        else:
            res_data = response.json()
            token = res_data.get("token") or res_data.get("access_token")

        if not token:
            record_service_event(
                "csm_api", "auth", "failed",
                detail=f"[{BULK_SHIFT_ENV.upper()}] Token yanıtta bulunamadı",
            )
            raise RuntimeError("Token yanıtta bulunamadı.")

        _cached_token = token
        record_service_event("csm_api", "auth", "success", detail=f"[{BULK_SHIFT_ENV.upper()}] Token alındı")
        return token
    except requests.RequestException as e:
        record_service_event("csm_api", "auth", "failed", detail=f"[{BULK_SHIFT_ENV.upper()}] {e}")
        raise RuntimeError(str(e))


def build_bulk_ticket_payload(
    reservation_no: str,
    shift_type_label: str,
    alternative_text: str,
    parent_ticket_uuid: str,
    reporter: Reporter,
) -> Dict[str, Any]:
    mapping = _mappings_for_env()[classify_shift_type(shift_type_label)]
    full_name = f"{reporter['first_name']} {reporter['last_name']}".strip()

    contact_medium_list = [
        {
            "contactMediumType": {"id": 10000004, "uuid": "dd61771d-02d2-46e5-9b4d-7cbd568ed84c", "shortCode": "GSM"},
            "val": reporter["phone"],
            "isPrimary": True,
            "externalId": None,
        },
        {
            "contactMediumType": {"id": 10000005, "uuid": "c38936ac-7e2c-46e7-aacc-deca59e132bf", "shortCode": "EMAIL"},
            "val": reporter["email"],
            "isPrimary": True,
            "externalId": None,
        },
    ]

    party_role = {
        "party": {
            "firstName": reporter["first_name"],
            "lastName": reporter["last_name"],
            "nationalityId": None,
            "partyType": "INDIVIDUAL",
            "fullName": full_name,
            "preferredLanguage": {
                "country": None,
                "createDate": "2021-06-23T20:39:15.028Z",
                "displayLanguage": "Türkçe",
                "id": 1000001,
                "language": "tr",
                "rtl": None,
                "status": 1,
                "updateDate": None,
            },
        },
        "partyRoleType": {
            "id": 1000022,
            "uuid": "4b7fc8ce-289c-476f-92d0-9279e7199983",
            "shortCode": "ANONYMOUS",
            "ownerType": True,
        },
        "externalId": None,
        "attributeValueList": [],
        "contactMediumList": contact_medium_list,
    }

    return {
        "contactParties": [
            {
                "partyRole": party_role,
                "contactMediumList": [
                    {"contactMedium": contact_medium_list[0], "isPreferred": True},
                    {"contactMedium": contact_medium_list[1], "isPreferred": True},
                ],
                "isPreferred": True,
                "preferredContactChannelList": ["SMS", "EMAIL"],
            }
        ],
        "attributeList": [],
        "attributeSetList": [],
        "ticketRelationList": [{"parentTicketUUID": parent_ticket_uuid}],
        "subTicketList": [],
        "availableOperations": [],
        "stage": {"shortCode": "START"},
        "partyRole": party_role,
        "description": f"<p>Toplu Kaydırma - Rezervasyon: {reservation_no} - {alternative_text}</p>",
        "channel": mapping["channel"],
        "subCategory": mapping["subCategory"],
        "category": mapping["category"],
        "ticketType": mapping["ticketType"],
        "priorityLevel": {
            "shortCode": "NORMAL",
            "name": "Normal",
            "ordinal": 3,
            "createdInAI": None,
            "externalId": None,
            "expression": None,
            "extraFields": {"color": "#FFE733"},
            "id": 100000037,
            "uuid": "074266b0-efdf-45a1-ab26-75a627a4b5ed",
        },
        "isResolved": False,
        "isProactive": False,
        "isParent": False,
        "reminders": [],
        "detectedLanguage": "",
        "relatedProduct": {"serviceNumber": str(reservation_no)},
    }


def create_bulk_ticket(payload: Dict[str, Any], token: str) -> Dict[str, Any]:
    """POST one bulk-shift ticket. Returns {'success', 'ticket_id'?, 'error'?}."""
    import json

    url = _ENV_URLS[BULK_SHIFT_ENV]["create_ticket"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Multilanguage": "true",
        "userMode": "LEAD",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        payload_json = json.dumps(payload, ensure_ascii=False)
        files = {"ticket": ("blob", payload_json.encode("utf-8"), "application/json")}
        response = requests.post(url, files=files, headers=headers, timeout=30)

        if response.status_code in (200, 201):
            res_data = response.json()
            ticket_id = res_data.get("id") or res_data.get("ticketNo") or "Oluşturuldu"
            record_service_event(
                "csm_api", "create_bulk_ticket", "success",
                detail=f"[{BULK_SHIFT_ENV.upper()}] #{ticket_id}",
            )
            return {"success": True, "ticket_id": str(ticket_id)}

        record_service_event(
            "csm_api", "create_bulk_ticket", "failed",
            detail=f"[{BULK_SHIFT_ENV.upper()}] HTTP {response.status_code}",
        )
        return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:200]}"}
    except requests.RequestException as e:
        record_service_event("csm_api", "create_bulk_ticket", "failed", detail=f"[{BULK_SHIFT_ENV.upper()}] {e}")
        return {"success": False, "error": str(e)}
