# Email Automation System

Professional email automation and ticket management system for CSM (Customer Service Management).

## Project Structure

```
Otomasyon/
├── config.py              # Configuration constants and settings
├── auth.py               # Authentication and token management
├── validators.py         # Input validation functions
├── utils.py             # Utility and helper functions
├── mail_processor.py    # Email retrieval and categorization
├── csm_api.py          # CSM API client and payload builder
├── main.py             # Application entry point
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (not in git)
└── README.md          # This file
```

## Features

- **Automatic Email Processing**: Retrieves emails from Gmail inbox
- **Content Validation**: Detects profanity and inappropriate content
- **Smart Categorization**: Automatically routes emails to correct ticket types:
  - Invoice requests
  - Thank you messages
  - General inquiries
- **Turkish Language Support**: Proper handling of Turkish characters and validation
- **Data Extraction**: Automatically extracts invoice information, ID numbers, addresses
- **CSM Integration**: Creates tickets in CSM system with proper categorization
- **Notification System**: Sends automated responses when requests cannot be processed
- **Token Management**: Automatic authentication with CSM API with token caching

## Requirements

- Python 3.14+
- Gmail account with App Password configured
- CSM system credentials

## Dependencies

```
python-dotenv==1.2.3
requests==2.34.2
```

Install with:
```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```env
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password
CSM_USERNAME=your-csm-username
CSM_PASSWORD=your-csm-password
```

### Getting Gmail App Password

1. Enable 2-Factor Authentication on your Google Account
2. Go to [Google Account Security](https://myaccount.google.com/security)
3. Find "App passwords"
4. Create a password for "Mail" and "Windows Computer"
5. Use this 16-character password as `EMAIL_PASS`

## Usage

Run the application:

```bash
python main.py
```

The application will:
1. Connect to Gmail IMAP
2. Retrieve unread emails (or recent emails if none unread)
3. Process each email:
   - Check for profanity/inappropriate content
   - Extract invoice information if applicable
   - Categorize the request
   - Create a CSM ticket
   - Send notification emails if needed
4. Disconnect from Gmail

## Module Documentation

### config.py
Central configuration file containing:
- API endpoints and credentials
- CSM channel, ticket type, and category IDs
- Validation settings
- Character encoding defaults

### auth.py
Handles CSM API authentication:
- `get_bearer_token()`: Acquires and caches auth tokens
- `invalidate_token_cache()`: Forces token refresh
- Automatic 55-minute token cache with refresh logic

### validators.py
Data validation functions:
- `is_valid_turkish_id()`: Validates Turkish ID numbers (11 digits)
- `is_valid_tax_id()`: Validates Turkish Tax IDs (10 digits)
- `is_valid_email()`: Email format validation
- `contains_profanity()`: Detects inappropriate content
- `extract_invoice_attributes()`: Extracts and validates invoice data

### utils.py
Helper functions:
- `normalize_turkish_characters()`: Converts Turkish chars to ASCII
- `decode_email_header()`: Handles email header encoding
- `extract_sender_info()`: Parses From header
- `parse_name_parts()`: Splits names into first/last
- `clean_subject_line()`: Removes email prefixes (Re:, Fwd:)

### mail_processor.py
Email handling:
- `EmailProcessor`: IMAP connection and email retrieval
- `EmailCategorizer`: Categorizes emails and determines ticket type
- `send_notification_email()`: Sends automated responses

### csm_api.py
CSM system integration:
- `CSMAPIClient`: Creates tickets via CSM API
- `TicketPayloadBuilder`: Constructs properly formatted ticket payloads

### main.py
Application orchestration:
- `process_email()`: Main email processing logic
- `main()`: Application entry point

## Email Classification

### Invoice Requests
Detected by keywords: fatura, efatura, e-fatura

Extracts:
- Person/Company name
- Turkish ID or Tax ID
- Invoice address
- Email address

Requires complete information or sends notification with missing fields.

### Thank You Messages
Detected by keywords: teşekkür, sağol, etc.

Sub-categories:
- Guide thank you (rehber, tur lideri, etc.)
- Consultant thank you (danışman, temsilci, etc.)
- General thank you (default)

### General Information Requests
Default category for other emails

## Error Handling

The system handles:
- Invalid email credentials
- IMAP connection failures
- Profanity detection and automatic rejection
- Missing required invoice information
- CSM API errors with appropriate error messages
- Email encoding issues with fallback encodings

## Logging

The application provides console output indicating:
- ✅ Success operations
- ❌ Errors
- ⚠️ Warnings
- 📌 Information
- 🔄 Processing steps
- 📧 Email operations
- 🚀 CSM ticket creation

## Best Practices Implemented

- **Modular Design**: Separation of concerns across modules
- **Configuration Management**: All settings in config.py
- **Environment Variables**: Sensitive data in .env
- **Type Hints**: Full type annotations for better code clarity
- **Documentation**: Comprehensive docstrings
- **Error Handling**: Try-except blocks with meaningful messages
- **Token Caching**: Efficient authentication with expiry handling
- **Character Encoding**: Proper Turkish language support
- **Code Organization**: Functions grouped by responsibility
- **Security**: No hardcoded credentials

## License

Internal use only.

## Support

For issues or questions, contact the development team.
