"""Toplu Kaydırma (Bulk Reservation Shift) module.

Creates CSM "ilişkili ticket" (LINKED_TICKET) entries in bulk, one per
reservation row, linked to an existing main ("Onay Kaydırma") ticket, from an
uploaded Excel export of reservations that need a date shift.

Payload shape verified against a real, successful production request
(captured from the CSM web UI's Network tab, 2026-08-25, ticket #101944819,
HTTP 200) -- see build_bulk_ticket_payload for the exact fields. Two things
about that captured example that are NOT obvious from CSM's UI:
  1. The link to the main ticket is two top-level fields on the payload
     (parentTicketUUID + relationType: "LINKED_TICKET") -- NOT an entry in
     ticketRelationList (which stays empty, unlike the parent-child relation
     this module used before).
  2. The reporter/"raporlayan kişi" for every linked ticket is a fixed,
     pre-existing anonymous CSM contact ("Onay Kaydırma", onay@tatilbudur.com)
     -- not the individual mail sender, and not something collected via a form.
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
    "parent_ticket_uuid": ("parentTicketUUID",),
}


class ExcelRow(TypedDict):
    reservation_no: str
    shift_type: str
    alternative: str
    parent_ticket_uuid: str


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
    last_parent_ticket_uuid = ""
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

        # parentTicketUUID is typically only filled on the first row of each
        # WorkGroup/Ticket ID group in the source export (observed live) --
        # carry the last non-empty value forward for rows that leave it blank.
        parent_ticket_uuid = cell("parent_ticket_uuid") or last_parent_ticket_uuid
        if parent_ticket_uuid:
            last_parent_ticket_uuid = parent_ticket_uuid

        rows.append(
            ExcelRow(
                reservation_no=reservation_no,
                shift_type=cell("shift_type") or "Operasyon Kaynaklı",
                alternative=cell("alternative") or "Toplu Kaydırma İşlemi",
                parent_ticket_uuid=parent_ticket_uuid,
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

# The fixed "Onay Kaydırma" anonymous contact every linked ticket is reported
# by (verified real party role id -- reusing it keeps CSM from accumulating
# more near-duplicate "onay kaydırma"-ish contacts, several of which already
# exist from past manual use).
ONAY_KAYDIRMA_PARTY_ROLE = {
    "id": 100239153,
    "party": {
        "firstName": "Onay",
        "lastName": "Kaydırma",
        "nationalityId": None,
        "partyType": "INDIVIDUAL",
        "fullName": "Onay Kaydırma",
    },
    "partyRoleType": {
        "id": 1000022,
        "uuid": "4b7fc8ce-289c-476f-92d0-9279e7199983",
        "shortCode": "ANONYMOUS",
        "ownerType": True,
    },
    "externalId": None,
    "attributeValueList": [],
    "contactMediumList": [
        {
            "contactMediumType": {"id": 10000005, "uuid": "c38936ac-7e2c-46e7-aacc-deca59e132bf", "shortCode": "EMAIL"},
            "val": "onay@tatilbudur.com",
            "isPrimary": True,
            "externalId": None,
        }
    ],
}

# Channel/ticketType/category/subCategory per "Kaydırma Tipi" classification
# (kullanıcı tarafından doğrulandı, 2026-08-25). The relation to the main
# ticket (top-level parentTicketUUID + relationType, see build_bulk_ticket_payload)
# and the fixed "Onay Kaydırma" reporter are shared across all three; only the
# kırılım (category path) differs by shift type. Add more entries here as new
# kırılımlar are confirmed.
SHIFT_TYPE_FIELDS: Dict[str, Dict[str, Any]] = {
    "OTEL_KAYNAKLI": {
        "channel": {"shortCode": "CAGRI_MERKEZI", "name": "Çağrı Merkezi", "id": 100000041, "uuid": "9a4dd8ef-045a-4f57-8c2c-8b0fc209d367"},
        "ticketType": {"shortCode": "REZERVASYON_ISLEMLERI", "name": "Backoffice İşlemleri", "id": 100000059, "uuid": "654c901c-40c2-46c1-8a00-925009dde46e"},
        "category": {"shortCode": "KAYDIRMA", "name": "Kaydırma", "id": 100000143, "uuid": "f3a9a508-0732-4410-82d7-847867fc616f"},
        "subCategory": {"shortCode": "OTEL_KAYNAKLI", "name": "Otel Kaynaklı", "id": 100000669, "uuid": "089de3d8-b26d-42da-88e6-f062cae187f3"},
    },
    "OPERASYON_KAYNAKLI": {
        "channel": {"shortCode": "CAGRI_MERKEZI", "name": "Çağrı Merkezi", "id": 100000041, "uuid": "9a4dd8ef-045a-4f57-8c2c-8b0fc209d367"},
        "ticketType": {"shortCode": "REZERVASYON_ISLEMLERI", "name": "Backoffice İşlemleri", "id": 100000059, "uuid": "654c901c-40c2-46c1-8a00-925009dde46e"},
        "category": {"shortCode": "KAYDIRMA", "name": "Kaydırma", "id": 100000143, "uuid": "f3a9a508-0732-4410-82d7-847867fc616f"},
        "subCategory": {"shortCode": "OPERASYON_KAYNAKLI", "name": "Operasyon Kaynaklı", "id": 100000671, "uuid": "089de3d8-b26d-42da-88e6-f062cae187f3"},
    },
    "ODEME_TAMAMLAMA": {
        "channel": {"shortCode": "CAGRI_MERKEZI", "name": "Çağrı Merkezi", "id": 100000041, "uuid": "9a4dd8ef-045a-4f57-8c2c-8b0fc209d367"},
        "ticketType": {"shortCode": "REZERVASYON_ISLEMLERI", "name": "Backoffice İşlemleri", "id": 100000059, "uuid": "654c901c-40c2-46c1-8a00-925009dde46e"},
        "category": {"shortCode": "DIGER_ISLEMLER", "name": "Diğer İşlemler", "id": 100000172, "uuid": "f3a9a508-0732-4410-82d7-847867fc616f"},
        "subCategory": {"shortCode": "ODEME_TAMAMLAMA", "name": "Ödeme Tamamlama", "id": 100000554, "uuid": "089de3d8-b26d-42da-88e6-f062cae187f3"},
    },
}

_cached_token: Optional[str] = None


def classify_shift_type(kaydirma_tipi: str) -> str:
    """Mirrors the original script's keyword-based classification -- selects
    which SHIFT_TYPE_FIELDS entry (channel/category/subCategory/ticketType)
    a row's ticket uses."""
    text = (kaydirma_tipi or "").strip()
    if "Otel" in text:
        return "OTEL_KAYNAKLI"
    if "Ödeme" in text or "Tamamlama" in text:
        return "ODEME_TAMAMLAMA"
    return "OPERASYON_KAYNAKLI"


def get_bulk_shift_token(force_refresh: bool = False) -> str:
    """Get a bearer token for the configured environment (BULK_SHIFT_ENV).

    Uses the dedicated RPA_OTOMASYON_USERNAME/PASSWORD system account (falls
    back to CSM_USERNAME/CSM_PASSWORD if that account isn't provisioned yet)
    so linked tickets show "Oluşturan: rpa_otomasyon" in CSM rather than a
    personal account.
    """
    global _cached_token
    if _cached_token and not force_refresh:
        return _cached_token

    from config import RPA_OTOMASYON_USERNAME, RPA_OTOMASYON_PASSWORD

    if not RPA_OTOMASYON_USERNAME or not RPA_OTOMASYON_PASSWORD:
        raise RuntimeError("RPA_OTOMASYON_USERNAME / RPA_OTOMASYON_PASSWORD (veya CSM_USERNAME / CSM_PASSWORD) ayarlanmamış.")

    auth_url = _ENV_URLS[BULK_SHIFT_ENV]["auth"]
    try:
        response = requests.post(
            auth_url,
            json={"userName": RPA_OTOMASYON_USERNAME, "password": RPA_OTOMASYON_PASSWORD},
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
) -> Dict[str, Any]:
    party_role = ONAY_KAYDIRMA_PARTY_ROLE
    fields = SHIFT_TYPE_FIELDS[classify_shift_type(shift_type_label)]

    return {
        "contactParties": [
            {
                "partyRole": party_role,
                "contactMediumList": [
                    {"contactMedium": party_role["contactMediumList"][0], "isPreferred": True},
                ],
                "isPreferred": True,
                "preferredContactChannelList": ["EMAIL"],
            }
        ],
        "attributeList": [],
        "attributeSetList": [],
        "ticketRelationList": [],
        "subTicketList": [],
        "availableOperations": [],
        "stage": {"shortCode": "START"},
        "partyRole": party_role,
        "description": f"<p>Toplu Kaydırma - Rezervasyon: {reservation_no} - {shift_type_label} - {alternative_text}</p>",
        "channel": fields["channel"],
        "subCategory": fields["subCategory"],
        "category": fields["category"],
        "ticketType": fields["ticketType"],
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
        "isParent": True,
        "reminders": [],
        "detectedLanguage": "",
        "parentTicketUUID": parent_ticket_uuid,
        "relationType": "LINKED_TICKET",
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


def process_rows(rows: List[ExcelRow], fallback_parent_ticket_uuid: str = "") -> Dict[str, Any]:
    """Resolves a bearer token once, then creates one linked ticket per row.
    Shared by the panel's /api/bulk-shift/upload endpoint and the
    mail-triggered flow (main.py's process_email, "toplu kaydırma" subject +
    Excel attachment) so both go through the exact same CSM call logic."""
    token = get_bulk_shift_token()

    results = []
    success_count = 0
    for row in rows:
        parent_ticket_uuid = row["parent_ticket_uuid"] or fallback_parent_ticket_uuid
        payload = build_bulk_ticket_payload(
            reservation_no=row["reservation_no"],
            shift_type_label=row["shift_type"],
            alternative_text=row["alternative"],
            parent_ticket_uuid=parent_ticket_uuid,
        )
        outcome = create_bulk_ticket(payload, token)
        if outcome["success"]:
            success_count += 1
        results.append({
            "reservation_no": row["reservation_no"],
            "shift_type": row["shift_type"],
            "shift_type_code": classify_shift_type(row["shift_type"]),
            "success": outcome["success"],
            "ticket_id": outcome.get("ticket_id"),
            "error": outcome.get("error"),
        })

    return {
        "environment": BULK_SHIFT_ENV,
        "total": len(results),
        "success_count": success_count,
        "failed_count": len(results) - success_count,
        "results": results,
    }
