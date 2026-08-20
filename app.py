"""
Email Automation System - Web UI Dashboard

Flask-based web interface for managing email automation and ticket creation.
"""

from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv

from mail_processor import EmailProcessor, EmailCategorizer, send_notification_email
from csm_api import CSMAPIClient, TicketPayloadBuilder
from auth import get_bearer_token, invalidate_token_cache
from validators import contains_profanity, is_valid_turkish_id, is_valid_tax_id
from utils import normalize_turkish_characters
from logging_utils import (
    clear_mail_error_events,
    clear_mail_events,
    read_mail_events,
    record_mail_event,
)
from main import process_email

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

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
        return {'error': str(e)}


# Routes
@app.route('/')
def dashboard():
    """Main dashboard page."""
    return render_template('dashboard.html')


@app.route('/api/status')
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
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        processor.disconnect()
        system_state['is_running'] = False


@app.route('/api/emails')
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
        return jsonify({'error': str(e)}), 500


@app.route('/api/token/refresh', methods=['POST'])
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
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/token/info')
def token_info_endpoint():
    """Get current token information."""
    try:
        info = get_token_info()
        return jsonify({'token_info': info})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/process-email', methods=['POST'])
def process_email_manual():
    """Manually process an email."""
    try:
        data = request.json
        email_id = data.get('email_id')
        
        processor = EmailProcessor()
        processor.connect()
        
        msg = processor.fetch_email(email_id.encode())
        subject, sender_email, sender_name, body = processor.extract_email_content(msg)
        
        # Check profanity
        if contains_profanity(f"{subject} {body}"):
            record_mail_event(
                event="email_processed",
                status="rejected",
                sender_email=sender_email,
                subject=subject,
                reason="Uygunsuz ifade veya hakaret tespit edildi",
                classification="rejected_content",
                mail_body=body,
            )
            processor.disconnect()
            return jsonify({
                'success': False,
                'message': 'Email contains profanity/hate speech'
            }), 400
        
        # Categorize
        categorizer = EmailCategorizer()
        categorization = categorizer.categorize(subject, body, sender_email)
        
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
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/mail-logs')
def get_mail_logs():
    """Return persistent email and ticket processing logs."""
    return jsonify({'logs': read_mail_events(limit=200)})


@app.route('/api/tickets')
def get_created_tickets():
    """Return successful ticket records for the dashboard."""
    tickets = [
        log for log in read_mail_events(limit=1000)
        if log.get('event') == 'ticket_created'
    ]
    return jsonify({'tickets': tickets})


@app.route('/api/mail-logs/clear', methods=['POST'])
def clear_mail_logs():
    """Clear persistent processing logs."""
    clear_mail_events()
    return jsonify({'success': True})


@app.route('/api/validate/turkish-id', methods=['POST'])
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
def check_profanity():
    """Check text for profanity."""
    try:
        data = request.json
        text = data.get('text', '')
        has_profanity = contains_profanity(text)
        return jsonify({'text_preview': text[:50], 'has_profanity': has_profanity})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/errors')
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


@app.route('/api/clear-errors', methods=['POST'])
def clear_errors():
    """Clear error log."""
    system_state['errors'] = []
    clear_mail_error_events()
    return jsonify({'success': True, 'message': 'Errors cleared'})


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
