"""
Email Automation System - Web UI Dashboard

Flask-based web interface for managing email automation and ticket creation.
"""

from flask import Flask, g, request, jsonify, send_from_directory
from flask_session import Session
from flask_migrate import Migrate
from datetime import datetime, timedelta
from collections import Counter, OrderedDict
import base64
import io
import json
import os
import re
from dotenv import load_dotenv

from mail_processor import EmailProcessor, EmailCategorizer, send_notification_email
from csm_api import CSMAPIClient, TicketPayloadBuilder
from auth import get_bearer_token, invalidate_token_cache
from validators import is_valid_turkish_id, is_valid_tax_id
from content_moderation import check_content, create_flagged_mail
from utils import normalize_turkish_characters
from logging_utils import (
    clear_mail_error_events,
    clear_mail_events,
    read_mail_events,
    record_mail_event,
)
from main import process_email
from service_log import (
    set_actor,
    record_service_event,
    read_service_events,
    clear_service_events,
)
from bulk_shift import (
    BULK_SHIFT_ENV,
    parse_excel_rows,
    process_rows,
    generate_result_workbook,
)
from models import db
from accounts import require_screen, get_csrf_token, current_user
from accounts_routes import accounts_bp
from content_rules_routes import content_rules_bp
from jobs_routes import jobs_bp

# Load environment variables
load_dotenv()
set_actor('panel')

# The Enigma frontend (React/Vite) is built to frontend/dist and served directly by
# Flask in production. In development, run `npm run dev` in frontend/ instead (Vite
# on :5173 proxies /api/* to this server) and this static folder stays unused.
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')

# static_folder=None disables Flask's built-in static route, which would otherwise
# shadow our own catch-all below at the same '/<path:...>' pattern and 404 before it
# ever gets a chance to fall back to index.html for client-side routes.
app = Flask(__name__, static_folder=None)

_flask_secret_key = os.getenv('FLASK_SECRET_KEY')
if not _flask_secret_key:
    if os.getenv('FLASK_ENV') == 'production':
        # Bilinen/public bir default ile üretimde oturum imzalamak session
        # forgery riski taşır -- .env'de gerçek bir FLASK_SECRET_KEY yoksa
        # üretimde uygulama hiç başlamasın.
        raise RuntimeError(
            "FLASK_SECRET_KEY .env dosyasında tanımlı olmalı (production). "
            "Üretmek için: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    _flask_secret_key = 'dev-secret-key-change-in-production'
app.config['SECRET_KEY'] = _flask_secret_key
app.config['SESSION_TYPE'] = 'filesystem'
# Same-origin architecture (Vite dev proxy / Flask serving the built SPA in
# prod, see FRONTEND_DIST below) means there's no cross-site cookie exposure
# to worry about -- SameSite=Lax + Secure-in-prod is enough CSRF-adjacent
# protection here without a heavier framework; a belt-and-suspenders CSRF
# token check for mutating requests is still applied below.
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
Session(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///enigma.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
Migrate(app, db)
app.register_blueprint(accounts_bp)
app.register_blueprint(content_rules_bp)
app.register_blueprint(jobs_bp)


@app.before_request
def _check_csrf():
    """Double-submit CSRF check for mutating /api/* requests. The token is
    handed to the client at login (see accounts.log_in_session /
    accounts_routes._me_payload) and must be echoed back via the
    X-CSRF-Token header -- an attacker's cross-site form/script can make the
    browser send the session cookie automatically, but can't read the token
    out of it to also send that header."""
    if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return None
    if not request.path.startswith('/api/'):
        return None
    if request.path == '/api/auth/login':
        return None

    expected = get_csrf_token()
    if expected is None:
        # Not logged in yet -- the route's own require_login/require_screen
        # decorator will correctly answer 401, not this hook's job.
        return None
    provided = request.headers.get('X-CSRF-Token')
    if provided != expected:
        return jsonify({'error': 'Geçersiz CSRF token.'}), 403
    return None

# Global variables for storing system state
system_state = {
    'is_running': False,
    'last_run': None,
    'total_emails_processed': 0,
    'total_tickets_created': 0,
    'errors': []
}

email_log = []
token_info = None

# Requests that are just polling for data (dashboard auto-refresh etc.) aren't
# "activity" worth an audit-trail entry — only log routes that change state.
_AUDITED_METHODS = {'POST'}


@app.after_request
def _audit_panel_requests(response):
    if request.method in _AUDITED_METHODS and request.path.startswith('/api/'):
        record_service_event(
            'panel_api',
            f'{request.method} {request.path}',
            'success' if response.status_code < 400 else 'failed',
            detail=f'HTTP {response.status_code}',
        )
    return response


def get_token_info():
    """Get current token information."""
    global token_info
    try:
        token = get_bearer_token()
        token_info = {
            'token': token[:20] + '...' if len(token) > 20 else token,
            'acquired_at': datetime.now().isoformat(),
            'expires_in': '55 minutes'
        }
        return token_info
    except Exception as e:
        print(f"⚠️ Token bilgisi alınamadı: {e}")
        return {'error': 'Token bilgisi alınamadı.'}


# Routes


@app.route('/api/status')
@require_screen("dashboard")
def get_status():
    """Get system status."""
    logs = read_mail_events(limit=1000)
    processed_logs = [
        log for log in logs
        if log.get('event') in {'ticket_created', 'ticket_not_created', 'email_processed'}
    ]
    successful_tickets = [log for log in logs if log.get('event') == 'ticket_created']
    failed_logs = [log for log in logs if log.get('status') in {'failed', 'blocked', 'rejected'}]
    last_log_time = logs[0].get('timestamp') if logs else system_state['last_run']

    return jsonify({
        'is_running': system_state['is_running'],
        'last_run': last_log_time,
        'total_emails_processed': len(processed_logs),
        'total_tickets_created': len(successful_tickets),
        'errors_count': len(failed_logs),
        'current_time': datetime.now().isoformat()
    })


@app.route('/api/run', methods=['POST'])
@require_screen("dashboard")
def run_email_processor():
    """Process unread emails from the dashboard and persist the results."""
    if system_state['is_running']:
        return jsonify({'success': False, 'message': 'Sistem zaten çalışıyor'}), 409

    processor = EmailProcessor()
    categorizer = EmailCategorizer()
    csm_client = CSMAPIClient()
    system_state['is_running'] = True
    system_state['last_run'] = datetime.now().astimezone().isoformat()

    try:
        processor.connect()
        email_ids = processor.get_unread_emails()
        if not email_ids:
            return jsonify({
                'success': True,
                'processed': 0,
                'message': 'Okunmamış e-posta bulunamadı'
            })

        processed = 0
        for email_id in email_ids:
            email_message = processor.fetch_email(email_id)
            if email_message:
                process_email(email_message, processor, categorizer, csm_client)
                processed += 1
            else:
                record_mail_event(
                    event='email_fetch',
                    status='failed',
                    reason='E-posta IMAP sunucusundan alınamadı',
                    details=f'IMAP ID: {email_id!r}',
                )

        return jsonify({
            'success': True,
            'processed': processed,
            'message': f'{processed} e-posta işlendi'
        })
    except Exception as e:
        record_mail_event(
            event='processor_error',
            status='failed',
            reason='Panelden mail işleme sırasında hata oluştu',
            details=str(e),
        )
        system_state['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        })
        return jsonify({'success': False, 'error': 'Mail işleme sırasında bir hata oluştu.'}), 500
    finally:
        processor.disconnect()
        system_state['is_running'] = False


@app.route('/api/emails')
@require_screen("emails")
def get_emails():
    """Get email list from server."""
    try:
        processor = EmailProcessor()
        processor.connect()
        
        email_ids = processor.get_unread_emails()
        
        if not email_ids:
            email_ids = processor.get_recent_emails(count=10)
        
        emails = []
        for email_id in email_ids[:20]:  # Limit to 20 emails
            msg = processor.fetch_email(email_id)
            if msg:
                subject, sender_email, sender_name, body = processor.extract_email_content(msg)
                emails.append({
                    'id': email_id.decode() if isinstance(email_id, bytes) else email_id,
                    'from': f"{sender_name} <{sender_email}>",
                    'subject': subject,
                    'preview': body[:100] + '...' if len(body) > 100 else body,
                    'received': datetime.now().isoformat(),
                    'is_unread': True
                })
        
        processor.disconnect()
        return jsonify({'emails': emails, 'count': len(emails)})

    except Exception as e:
        print(f"⚠️ E-posta listesi alınamadı: {e}")
        return jsonify({'error': 'E-posta listesi alınamadı.'}), 500


@app.route('/api/token/refresh', methods=['POST'])
@require_screen("settings")
def refresh_token():
    """Refresh authentication token."""
    try:
        invalidate_token_cache()
        token_info = get_token_info()
        return jsonify({
            'success': True,
            'message': 'Token refreshed successfully',
            'token_info': token_info
        })
    except Exception as e:
        print(f"⚠️ Token yenilenemedi: {e}")
        return jsonify({'success': False, 'error': 'Token yenilenemedi.'}), 500


@app.route('/api/token/info')
@require_screen("settings")
def token_info_endpoint():
    """Get current token information."""
    try:
        info = get_token_info()
        return jsonify({'token_info': info})
    except Exception as e:
        print(f"⚠️ Token bilgisi alınamadı: {e}")
        return jsonify({'error': 'Token bilgisi alınamadı.'}), 500


@app.route('/api/process-email', methods=['POST'])
@require_screen("emails")
def process_email_manual():
    """Manually process an email."""
    try:
        data = request.json
        email_id = data.get('email_id')
        
        processor = EmailProcessor()
        processor.connect()
        
        msg = processor.fetch_email(email_id.encode())
        subject, sender_email, sender_name, body = processor.extract_email_content(msg)

        # Gated on invoice-context keywords so OCR doesn't run on unrelated PDF
        # attachments (uçak/otobüs bileti vb.) -- those are routed to the right
        # kırılım by subject/body keywords alone, no attribute extraction needed.
        attachment_fields = None
        normalized_for_ocr_gate = normalize_turkish_characters(f"{subject} {body}")
        looks_invoice_related = any(
            keyword in normalized_for_ocr_gate for keyword in EmailCategorizer.INVOICE_CONTEXT_KEYWORDS
        )
        if looks_invoice_related:
            ocr_attachments = processor.extract_ocr_attachments(msg)
            if ocr_attachments:
                from ocr_utils import extract_invoice_fields_from_attachments
                attachment_fields = extract_invoice_fields_from_attachments(ocr_attachments)

        # Uygunsuz içerik denetimi -- bkz. content_moderation.py. main.py'nin
        # process_email'iyle AYNI mekanizma: ticket akışına doğrudan girmez,
        # FlaggedMail olarak operatör onayına düşer (otomatik reddedilmez).
        moderation_match = check_content(f"{subject} {body}")
        if moderation_match:
            flagged_id = create_flagged_mail(sender_email, sender_name, subject, body, moderation_match)
            record_mail_event(
                event="email_processed",
                status="pending_review",
                sender_email=sender_email,
                subject=subject,
                reason=f"Uygunsuz içerik şüphesi ({moderation_match.category}) -- operatör onayı bekleniyor",
                details=f"flagged_mail_id={flagged_id}",
                classification="flagged_content",
                mail_body=body,
            )
            processor.disconnect()
            return jsonify({
                'success': False,
                'message': 'Uygunsuz içerik şüphesiyle işaretlendi, operatör onayı bekleniyor',
                'flagged_mail_id': flagged_id,
            }), 202
        
        # Categorize
        categorizer = EmailCategorizer()
        categorization = categorizer.categorize(subject, body, sender_email, attachment_fields)
        
        # Check missing fields
        if categorization.get('missing_fields'):
            record_mail_event(
                event="ticket_not_created",
                status="blocked",
                sender_email=sender_email,
                subject=subject,
                reason="Zorunlu alanlar eksik veya geçersiz",
                details=", ".join(categorization['missing_fields']),
                classification=categorization.get('classification', ''),
                mail_body=body,
            )
            processor.disconnect()
            return jsonify({
                'success': False,
                'message': f"Missing fields: {', '.join(categorization['missing_fields'])}"
            }), 400
        
        # Create ticket
        csm_client = CSMAPIClient()
        payload = TicketPayloadBuilder.build_payload(
            sender_email, sender_name, subject, body, categorization
        )
        
        ticket_id = csm_client.create_ticket(payload)
        
        processor.disconnect()
        
        system_state['total_emails_processed'] += 1
        if ticket_id:
            system_state['total_tickets_created'] += 1
            record_mail_event(
                event="ticket_created",
                status="success",
                sender_email=sender_email,
                subject=subject,
                reason="Ticket başarıyla oluşturuldu",
                classification=categorization.get('classification', ''),
                ticket_id=ticket_id,
                ticket_details={
                    "ticket_type": categorization.get("ticket_type_id"),
                    "category": categorization.get("category_id"),
                    "sub_category": categorization.get("sub_category_id"),
                    "sub_category_code": categorization.get("sub_category_code", ""),
                    "body_preview": body[:300],
                },
                mail_body=body,
            )
        else:
            send_notification_email(
                sender_email,
                subject,
                "Talebiniz teknik bir nedenle şu anda işleme alınamadı. Lütfen daha sonra tekrar deneyiniz."
            )
            record_mail_event(
                event="ticket_not_created",
                status="failed",
                sender_email=sender_email,
                subject=subject,
                reason="CSM API ticket oluşturamadı",
                details=csm_client.last_error,
                classification=categorization.get('classification', ''),
                mail_body=body,
            )
        
        return jsonify({
            'success': ticket_id is not None,
            'ticket_id': ticket_id,
            'classification': categorization.get('classification'),
            'sender': sender_name,
            'email': sender_email
        })
    
    except Exception as e:
        record_mail_event(
            event="processor_error",
            status="failed",
            reason="Panelden mail işleme sırasında hata oluştu",
            details=str(e),
        )
        system_state['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        })
        return jsonify({'success': False, 'error': 'Mail işleme sırasında bir hata oluştu.'}), 500


@app.route('/api/mail-logs')
@require_screen("logs")
def get_mail_logs():
    """Return persistent email/ticket processing logs, paginated and filterable.

    Defaults (no params) preserve the old behavior — up to 200 most recent
    events, used by the Dashboard for client-side chart aggregation. The
    Loglar page passes explicit limit/offset/filters for real pagination.
    """
    query = (request.args.get('q') or '').strip().lower()
    status = request.args.get('status')
    event_type = request.args.get('event')

    try:
        limit = int(request.args.get('limit', 200))
    except (TypeError, ValueError):
        limit = 200
    limit = max(1, min(limit, 500))

    try:
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    logs = _apply_report_filters(
        read_mail_events(limit=100000),
        sender=request.args.get('sender'),
        classification=request.args.get('classification'),
        since_iso=_cutoff_from_range(request.args.get('range')),
    )

    if status:
        logs = [log for log in logs if log.get('status') == status]
    if event_type:
        logs = [log for log in logs if log.get('event') == event_type]
    if query:
        def matches(log):
            haystack = ' '.join(
                str(log.get(field, '') or '')
                for field in ('sender_email', 'subject', 'reason', 'classification', 'ticket_id')
            ).lower()
            return query in haystack

        logs = [log for log in logs if matches(log)]

    total = len(logs)
    page = logs[offset:offset + limit]
    return jsonify({'logs': page, 'total': total, 'limit': limit, 'offset': offset})


@app.route('/api/mail-logs/detail/<timestamp>')
@require_screen("logs")
def get_mail_log_detail(timestamp):
    """Return a single processing-log record by its exact timestamp (unique
    at microsecond precision — logs have no other stable identifier).

    Deliberately under /detail/ rather than /api/mail-logs/<timestamp>: that
    shape sits at the same path depth as the existing /api/mail-logs/clear
    (POST-only) route, and Werkzeug will happily route a stray GET to
    /api/mail-logs/clear into this dynamic rule (timestamp='clear') instead
    of correctly 405-ing — confirmed by testing before this was split out.
    """
    for log in read_mail_events(limit=100000):
        if log.get('timestamp') == timestamp:
            return jsonify({'log': log})
    return jsonify({'error': 'Log kaydı bulunamadı'}), 404


@app.route('/api/tickets')
@require_screen("tickets")
def get_created_tickets():
    """Return successful ticket records, paginated and filterable by date
    range, sender, top-level classification, and/or a free-text search."""
    query = (request.args.get('q') or '').strip().lower()

    try:
        limit = int(request.args.get('limit', 25))
    except (TypeError, ValueError):
        limit = 25
    limit = max(1, min(limit, 100))

    try:
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    tickets = [
        log for log in read_mail_events(limit=100000)
        if log.get('event') == 'ticket_created'
    ]

    tickets = _apply_report_filters(
        tickets,
        sender=request.args.get('sender'),
        classification=request.args.get('classification'),
        since_iso=_cutoff_from_range(request.args.get('range')),
    )

    if query:
        def matches(ticket):
            haystack = ' '.join(
                str(ticket.get(field, '') or '')
                for field in ('ticket_id', 'sender_email', 'subject', 'classification')
            ).lower()
            return query in haystack

        tickets = [t for t in tickets if matches(t)]

    total = len(tickets)
    page = tickets[offset:offset + limit]
    return jsonify({'tickets': page, 'total': total, 'limit': limit, 'offset': offset})


@app.route('/api/tickets/<ticket_id>')
@require_screen("tickets")
def get_ticket_detail(ticket_id):
    """Return a single ticket record by its CSM ticket id, with full detail
    (mail body, classification breadcrumb, raw CSM category ids)."""
    for log in read_mail_events(limit=100000):
        if log.get('event') == 'ticket_created' and str(log.get('ticket_id')) == str(ticket_id):
            return jsonify({'ticket': log})
    return jsonify({'error': f"#{ticket_id} numaralı ticket bulunamadı"}), 404


@app.route('/api/mail-logs/clear', methods=['POST'])
@require_screen("logs")
def clear_mail_logs():
    """Clear persistent processing logs."""
    clear_mail_events()
    return jsonify({'success': True})


@app.route('/api/validate/turkish-id', methods=['POST'])
@require_screen("settings")
def validate_turkish_id():
    """Validate Turkish ID number."""
    try:
        data = request.json
        id_number = data.get('id_number', '')
        is_valid = is_valid_turkish_id(id_number)
        return jsonify({'id_number': id_number, 'is_valid': is_valid})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/validate/tax-id', methods=['POST'])
@require_screen("settings")
def validate_tax_id():
    """Validate Tax ID number."""
    try:
        data = request.json
        tax_id = data.get('tax_id', '')
        is_valid = is_valid_tax_id(tax_id)
        return jsonify({'tax_id': tax_id, 'is_valid': is_valid})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/profanity-check', methods=['POST'])
@require_screen("settings")
def check_profanity():
    """Bir metni content_moderation motoruna (config listesi + panelden
    eklenen aktif kurallar) karşı test eder -- kural eklerken/düzenlerken
    hemen deneyebilmek için."""
    try:
        data = request.json
        text = data.get('text', '')
        match = check_content(text)
        return jsonify({
            'text_preview': text[:50],
            'has_profanity': match is not None,
            'match': {
                'category': match.category,
                'rule_source': match.rule_source,
                'rule_id': match.rule_id,
            } if match else None,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/errors')
@require_screen("dashboard")
def get_errors():
    """Get system errors."""
    persistent_errors = [
        {
            'timestamp': log.get('timestamp'),
            'error': log.get('reason') or 'İşlem başarısız',
            'details': log.get('details', ''),
            'sender_email': log.get('sender_email', ''),
            'subject': log.get('subject', ''),
            'status': log.get('status', ''),
        }
        for log in read_mail_events(limit=1000)
        if log.get('status') in {'failed', 'blocked', 'rejected'}
    ]
    runtime_errors = system_state['errors'][-20:]
    return jsonify({'errors': (persistent_errors + runtime_errors)[:50]})


@app.route('/api/statistics')
@require_screen("dashboard")
def get_statistics():
    """Get system statistics."""
    return jsonify({
        'total_emails_processed': system_state['total_emails_processed'],
        'total_tickets_created': system_state['total_tickets_created'],
        'success_rate': (
            (system_state['total_tickets_created'] / system_state['total_emails_processed'] * 100)
            if system_state['total_emails_processed'] > 0
            else 0
        ),
        'total_errors': len(system_state['errors']),
        'last_run': system_state['last_run']
    })


RANGE_PATTERN = re.compile(r'^(\d+)([dh])$')
PROCESSED_EVENTS = {'ticket_created', 'ticket_not_created', 'email_processed'}


def _parse_range(range_str, default_n, default_unit):
    """Parse a '7d' / '24h' style range string, falling back to the given default."""
    if range_str:
        match = RANGE_PATTERN.match(range_str.strip())
        if match:
            return int(match.group(1)), match.group(2)
    return default_n, default_unit


def _cutoff_from_range(range_str):
    """Return an ISO cutoff timestamp for a '7d'/'24h' range string, or None if absent/invalid."""
    n, unit = _parse_range(range_str, None, None)
    if n is None:
        return None
    delta = timedelta(days=n) if unit == 'd' else timedelta(hours=n)
    return (datetime.now().astimezone() - delta).isoformat()


def _apply_report_filters(events, sender=None, classification=None, since_iso=None):
    """Narrow persisted log events by sender, top-level classification, and/or a time cutoff."""
    filtered = events
    if since_iso:
        filtered = [e for e in filtered if (e.get('timestamp') or '') >= since_iso]
    if sender:
        filtered = [
            e for e in filtered
            if (e.get('sender_email') or '').lower() == sender.lower()
        ]
    if classification:
        filtered = [
            e for e in filtered
            if (e.get('classification') or '').split('>')[0].strip().upper()
            == classification.upper()
        ]
    return filtered


@app.route('/api/reports/timeseries')
@require_screen("reports")
def reports_timeseries():
    """Zaman bazlı işlenen e-posta hacmi (gün veya saat kırılımında), başarı/hata kırılımıyla."""
    n, unit = _parse_range(request.args.get('range'), 14, 'd')
    granularity_param = request.args.get('granularity')
    if granularity_param in ('day', 'hour'):
        unit = 'd' if granularity_param == 'day' else 'h'
    granularity = 'day' if unit == 'd' else 'hour'
    n = max(1, min(n, 90 if granularity == 'day' else 168))

    now = datetime.now().astimezone()
    buckets = OrderedDict()
    if granularity == 'day':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(n - 1, -1, -1):
            key = (start - timedelta(days=i)).strftime('%Y-%m-%d')
            buckets[key] = {'count': 0, 'success_count': 0, 'error_count': 0}
        key_len = 10
    else:
        start = now.replace(minute=0, second=0, microsecond=0)
        for i in range(n - 1, -1, -1):
            key = (start - timedelta(hours=i)).strftime('%Y-%m-%dT%H')
            buckets[key] = {'count': 0, 'success_count': 0, 'error_count': 0}
        key_len = 13

    events = _apply_report_filters(
        read_mail_events(limit=100000),
        sender=request.args.get('sender'),
        classification=request.args.get('classification'),
    )

    for log in events:
        if log.get('event') not in PROCESSED_EVENTS:
            continue
        bucket = buckets.get((log.get('timestamp') or '')[:key_len])
        if not bucket:
            continue
        bucket['count'] += 1
        status = log.get('status')
        if status == 'success':
            bucket['success_count'] += 1
        elif status in {'failed', 'blocked', 'rejected'}:
            bucket['error_count'] += 1

    points = [{'date': key, **values} for key, values in buckets.items()]
    return jsonify({'granularity': granularity, 'range': f'{n}{unit}', 'points': points})


@app.route('/api/reports/by-classification')
@require_screen("reports")
def reports_by_classification():
    """Oluşturulan ticket'ların üst seviye sınıflandırmaya göre dağılımı."""
    events = _apply_report_filters(
        read_mail_events(limit=100000),
        sender=request.args.get('sender'),
        since_iso=_cutoff_from_range(request.args.get('range')),
    )

    counts = Counter()
    for log in events:
        if log.get('event') != 'ticket_created':
            continue
        top_level = (log.get('classification') or '').split('>')[0].strip()
        counts[top_level or 'DIGER'] += 1

    categories = [
        {'name': name, 'count': count}
        for name, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return jsonify({'categories': categories})


@app.route('/api/reports/by-sender')
@require_screen("reports")
def reports_by_sender():
    """Gönderen bazlı e-posta hacmi (en çok yazan N adres)."""
    try:
        limit = int(request.args.get('limit', 10))
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 50))

    events = _apply_report_filters(
        read_mail_events(limit=100000),
        classification=request.args.get('classification'),
        since_iso=_cutoff_from_range(request.args.get('range')),
    )

    counts = Counter()
    for log in events:
        if log.get('event') not in PROCESSED_EVENTS:
            continue
        sender = log.get('sender_email') or ''
        if sender:
            counts[sender] += 1

    senders = [
        {'sender_email': sender, 'count': count}
        for sender, count in counts.most_common(limit)
    ]
    return jsonify({'senders': senders})


@app.route('/api/clear-errors', methods=['POST'])
@require_screen("dashboard")
def clear_errors():
    """Clear error log."""
    system_state['errors'] = []
    clear_mail_error_events()
    return jsonify({'success': True, 'message': 'Errors cleared'})


@app.route('/api/service-logs')
@require_screen("monitoring")
def get_service_logs():
    """Return outbound service-call records (CSM API, Gmail IMAP, panel API),
    paginated and filterable by service, actor, status, and date range."""
    service = request.args.get('service')
    actor = request.args.get('actor')
    status = request.args.get('status')

    try:
        limit = int(request.args.get('limit', 25))
    except (TypeError, ValueError):
        limit = 25
    limit = max(1, min(limit, 200))

    try:
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)

    since_iso = _cutoff_from_range(request.args.get('range'))

    logs = read_service_events(limit=100000)
    if since_iso:
        logs = [log for log in logs if (log.get('timestamp') or '') >= since_iso]
    if service:
        logs = [log for log in logs if log.get('service') == service]
    if actor:
        logs = [log for log in logs if log.get('actor') == actor]
    if status:
        logs = [log for log in logs if log.get('status') == status]

    total = len(logs)
    page = logs[offset:offset + limit]
    return jsonify({'logs': page, 'total': total, 'limit': limit, 'offset': offset})


@app.route('/api/service-logs/summary')
@require_screen("monitoring")
def get_service_logs_summary():
    """Per-service health snapshot: last success/failure timestamp and totals.
    Powers the Monitoring page's status cards without shipping the full log."""
    logs = read_service_events(limit=100000)
    services = ('csm_api', 'gmail_imap', 'panel_api')
    summary = {}
    for service in services:
        service_logs = [log for log in logs if log.get('service') == service]
        last_success = next((l for l in service_logs if l.get('status') == 'success'), None)
        last_failure = next((l for l in service_logs if l.get('status') == 'failed'), None)
        summary[service] = {
            'total': len(service_logs),
            'success_count': sum(1 for l in service_logs if l.get('status') == 'success'),
            'failed_count': sum(1 for l in service_logs if l.get('status') == 'failed'),
            'last_success_at': last_success.get('timestamp') if last_success else None,
            'last_failure_at': last_failure.get('timestamp') if last_failure else None,
        }

    actor_counts = Counter(log.get('actor') for log in logs)
    return jsonify({
        'services': summary,
        'actors': {actor: count for actor, count in actor_counts.items()},
    })


@app.route('/api/service-logs/clear', methods=['POST'])
@require_screen("monitoring")
def clear_service_logs():
    """Clear the outbound service-call log."""
    clear_service_events()
    return jsonify({'success': True})


@app.route('/api/bulk-shift/env')
@require_screen("bulk_shift")
def get_bulk_shift_env():
    """Which CSM environment bulk-shift tickets currently go to (preprod/prod)."""
    return jsonify({'environment': BULK_SHIFT_ENV})


@app.route('/api/bulk-shift/upload', methods=['POST'])
@require_screen("bulk_shift")
def upload_bulk_shift():
    """Parse an uploaded reservation-shift Excel export and create one CSM
    ticket per row -- an "ilişkili ticket" (LINKED_TICKET) if the row (or the
    optional form parent_ticket_uuid fallback) carries a parentTicketUUID
    (Eos/wtatil), or a standalone "ana ticket" if not (BO/YÇM -- their
    template has no parentTicketUUID column at all, and that's expected, not
    an error). Reporter is always the fixed "Onay Kaydırma" system contact --
    not collected from the form. Runs synchronously (one HTTP call per row)
    — see bulk_shift.MAX_ROWS for the row cap.

    If the uploaded template also has "Yeni Ticket ID"/"Servis Durumu"/
    "Servis Mesajı" columns (BO/YÇM), the response includes that same file
    with those columns filled in (result_file_base64/result_file_name) for
    the panel to offer as a download."""
    if 'file' not in request.files:
        return jsonify({'error': 'Excel dosyası bulunamadı (file alanı boş)'}), 400

    fallback_parent_ticket_uuid = (request.form.get('parent_ticket_uuid') or '').strip()
    uploaded_file = request.files['file']
    original_bytes = uploaded_file.read()

    try:
        rows = parse_excel_rows(io.BytesIO(original_bytes))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Excel okunamadı: {e}'}), 400

    if not rows:
        return jsonify({'error': 'Excel dosyasında işlenecek satır bulunamadı'}), 400

    try:
        summary = process_rows(rows, fallback_parent_ticket_uuid=fallback_parent_ticket_uuid)
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 502

    # Not: bu record_mail_event çağrısı önceden HİÇ YOKTU -- panelden yüklenen
    # toplu kaydırma sonuçları (başarılı veya başarısız) Loglar sayfasında
    # görünmüyordu, sadece o an ekrandaki geçici sonuç tablosunda kalıyordu.
    # Mail-tetikli akış (main.py) zaten aynı şekilde logluyor; ikisi tutarlı
    # olsun diye buraya da eklendi.
    record_mail_event(
        event="ticket_created" if summary["success_count"] > 0 else "ticket_not_created",
        status="success" if summary["failed_count"] == 0 else "failed",
        sender_email=g.current_user.email,
        subject=f"Toplu Kaydırma (panel): {uploaded_file.filename or ''}",
        reason=f"Toplu kaydırma: {summary['success_count']}/{summary['total']} ticket oluşturuldu",
        classification="bulk_kaydirma",
        ticket_details=summary,
    )

    result_file_bytes = generate_result_workbook(original_bytes, rows, summary["results"])
    if result_file_bytes is not None:
        summary['result_file_base64'] = base64.b64encode(result_file_bytes).decode('ascii')
        summary['result_file_name'] = f"sonuc_{uploaded_file.filename or 'toplu_kaydirma.xlsx'}"

    return jsonify(summary)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_enigma(path):
    """Serve the built Enigma SPA; unknown paths fall back to index.html for client-side routing."""
    if path and os.path.exists(os.path.join(FRONTEND_DIST, path)):
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, 'index.html')


if __name__ == '__main__':
    # debug=True açıkken Werkzeug'ün interaktif hata konsolu aktif olur --
    # bu, hatalı bir istekten sonra rastgele kod çalıştırmaya izin verir
    # (bkz. Werkzeug/Flask debugger RCE). FLASK_ENV=production olmadığı
    # sürece varsayılan hâlâ debug modu (yerel geliştirme için), ama artık
    # üretimde kasıtlı bir .env değişikliği olmadan kapanıyor.
    app.run(debug=os.getenv('FLASK_ENV') != 'production', host='127.0.0.1', port=5000)
