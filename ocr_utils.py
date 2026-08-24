"""OCR helper for reading text out of email image attachments (scanned Vergi
Levhası / kaşe photos customers send instead of typing invoice info).

Uses local Tesseract OCR (tur+eng) so tax/company documents never leave the
machine. Requires the Tesseract binary installed separately (not a pip
package) and Turkish trained data in ./tessdata (see .gitignore -- not
checked into git, download from
https://github.com/tesseract-ocr/tessdata/raw/main/tur.traineddata).
"""

import io
import os
import re
import subprocess
import tempfile

from PIL import Image

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_TESSDATA_DIR = os.path.join(_PROJECT_DIR, "tessdata")
_TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

IMAGE_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/tiff", "image/bmp", "image/webp"}
PDF_CONTENT_TYPES = {"application/pdf"}
ATTACHMENT_CONTENT_TYPES = IMAGE_CONTENT_TYPES | PDF_CONTENT_TYPES


def is_ocr_available() -> bool:
    """Whether both the Tesseract binary and local Turkish trained data are present."""
    tur_data = os.path.join(_TESSDATA_DIR, "tur.traineddata")
    return os.path.exists(_TESSERACT_CMD) and os.path.exists(tur_data)


def _run_tesseract(image_bytes: bytes, lang: str, psm: int = None, whitelist: str = None) -> str:
    """Shells out to tesseract.exe directly rather than using pytesseract's
    image_to_string(): pytesseract decodes tesseract's stderr as strict UTF-8,
    which raises UnicodeDecodeError on this machine because the project path
    contains non-ASCII characters ("Masaüstü") that tesseract echoes back in
    diagnostic output using the console's codepage, not UTF-8."""
    if not image_bytes:
        return ""
    if not os.path.exists(_TESSERACT_CMD):
        print("⚠️ OCR atlandı: Tesseract-OCR kurulu değil.")
        return ""

    tmp_path = None
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("RGB")
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
                img.save(tmp, format="PNG")

        args = [_TESSERACT_CMD, tmp_path, "stdout", "--tessdata-dir", _TESSDATA_DIR, "-l", lang]
        if psm is not None:
            args += ["--psm", str(psm)]
        if whitelist:
            args += ["-c", f"tessedit_char_whitelist={whitelist}"]

        result = subprocess.run(args, capture_output=True, timeout=30)
        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="replace")
            print(f"⚠️ OCR başarısız (tesseract çıkış kodu {result.returncode}): {stderr_text}")
            return ""
        return result.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"⚠️ OCR başarısız: {e}")
        return ""
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def extract_text_from_image(image_bytes: bytes) -> str:
    """OCR a single image attachment's bytes to text. Returns "" on any failure
    (corrupt image, missing binary, unreadable format) -- OCR is a best-effort
    supplement to the email body text, never something that should crash mail
    processing."""
    return _run_tesseract(image_bytes, lang="tur+eng")


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Get text out of a PDF attachment (Vergi Levhası is often sent as a PDF
    export, not just a photo). Tries each page's embedded text layer first
    (instant, exact -- covers PDFs generated digitally, e.g. from GİB's
    e-devlet portal); only rasterizes and OCRs a page when it has no usable
    text layer (a scanned/photographed page saved as PDF)."""
    if not pdf_bytes:
        return ""
    try:
        import pymupdf
    except ImportError:
        print("⚠️ OCR atlandı: pymupdf kurulu değil, PDF okunamıyor.")
        return ""

    texts = []
    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                page_text = page.get_text().strip()
                if len(page_text) < 20:  # no meaningful text layer -- likely a scan
                    pix = page.get_pixmap(dpi=300)
                    page_text = extract_text_from_image(pix.tobytes("png"))
                texts.append(page_text)
    except Exception as e:
        print(f"⚠️ PDF okunamadı: {e}")
        return ""

    return "\n\n".join(t for t in texts if t.strip())


def extract_text_from_attachment(payload: bytes, content_type: str) -> str:
    """Dispatch a single attachment's bytes to the right extractor by content type."""
    if content_type in PDF_CONTENT_TYPES:
        return extract_text_from_pdf(payload)
    return extract_text_from_image(payload)


def extract_text_from_attachments(attachments) -> str:
    """OCR/read multiple attachments -- attachments: iterable of
    (payload_bytes, content_type) tuples -- and join the results with blank
    lines between them (kept separate so downstream per-document label
    parsing doesn't run two unrelated documents' text together)."""
    texts = [extract_text_from_attachment(payload, ctype) for payload, ctype in attachments]
    return "\n\n".join(t for t in texts if t.strip())


# Vergi Levhası label -> raw-field key it maps to (see validators.py's
# build_invoice_attributes_from_fields for what these keys mean).
_VERGI_LEVHASI_LABELS = {
    "TİCARET ÜNVANI": "company_name",
    "ADI SOYADI": "person_name",
    "VERGİ DAİRESİ": "tax_office",
    "VERGİ KİMLİK NO": "tax_value",
    "TC KİMLİK NO": "tc_value",
    "İŞ YERİ ADRESİ": "address",
}


def _normalize_pdf_label(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().upper()


def _ocr_barcode_digits(page, rect) -> str:
    """OCR the human-readable digit string printed under a 1D barcode graphic
    (GİB Vergi Levhası PDFs render VERGİ KİMLİK NO / TC KİMLİK NO this way).

    OCR'ing the barcode's full image rect directly is unreliable -- the bars
    confuse tesseract's character segmentation and it silently returns a
    wrong-but-plausible same-length digit string (verified against two real
    Vergi Levhası exports: e.g. barcode's real digits '3961584028' came back
    as '3961540286' when OCR'd with the bars included). Cropping to roughly
    the bottom 40% of the rect (bars excluded, digit row only) and reading it
    as a single text line with a digit-only whitelist reproduced the exact
    correct digits on both real documents -- the bar height is consistently
    proportioned across normal-DPI barcode renders, so this fraction isn't
    tuned to one specific image's pixel dimensions."""
    import pymupdf

    digit_row = pymupdf.Rect(rect.x0, rect.y0 + rect.height * 0.6, rect.x1, rect.y1)
    pix = page.get_pixmap(clip=digit_row, dpi=600)
    return _run_tesseract(pix.tobytes("png"), lang="eng", psm=6, whitelist="0123456789")


def extract_vergi_levhasi_fields_from_pdf(pdf_bytes: bytes) -> dict:
    """Pair each Vergi Levhası label with its value using the PDF's real text
    block bounding boxes (a value sits in the same horizontal band as its
    label, positioned to the right of it).

    This is deliberately geometric rather than "read the value right after
    the label in the extracted text": GİB-issued Vergi Levhası PDFs commonly
    emit ALL label text first, then ALL value text, as two separate groups in
    the content stream -- flat reading order pairs each label with the NEXT
    label instead of its actual value.

    VERGİ KİMLİK NO / TC KİMLİK NO are also commonly rendered as a barcode
    IMAGE rather than selectable text; when no text value is found in a
    number field's row, the same-row region is rendered to an image and OCR'd
    instead (the barcode always has the human-readable digits printed
    alongside/under it).

    Returns {} (not an exception) for anything that goes wrong or doesn't
    look like a Vergi Levhası -- this is a best-effort opportunistic parser,
    callers fall back to flat-text parsing when it comes back empty."""
    if not pdf_bytes:
        return {}
    try:
        import pymupdf
    except ImportError:
        return {}

    from validators import normalize_ocr_digit_confusions

    fields: dict = {}
    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                blocks = page.get_text("blocks")
                label_blocks = []
                value_candidates = []
                for x0, y0, x1, y1, text, *_rest in blocks:
                    norm = _normalize_pdf_label(text)
                    field_name = _VERGI_LEVHASI_LABELS.get(norm)
                    if field_name:
                        label_blocks.append((x0, y0, x1, y1, field_name))
                    elif text.strip():
                        value_candidates.append((x0, y0, x1, y1, text.strip()))

                # Each value looks for its NEAREST preceding label in the same
                # row (not the other way around): a two-column form has TWO
                # label/value pairs per visual row, so "does any value sit to
                # the right of this label" wrongly grabs the OTHER column's
                # value when this label's own value cell is blank (observed
                # live: an empty "ADI SOYADI" box let the far-right "VERGİ
                # DAİRESİ" value get matched to it instead). Picking, for each
                # value, the closest label whose right edge precedes it,
                # naturally keeps each column's pairs together.
                for vx0, vy0, vx1, vy1, text in value_candidates:
                    same_row_labels = [
                        lb for lb in label_blocks
                        if lb[2] <= vx0 + 2 and lb[1] < vy1 and lb[3] > vy0
                    ]
                    if not same_row_labels:
                        continue
                    lx0, ly0, lx1, ly1, field_name = max(same_row_labels, key=lambda lb: lb[2])
                    if field_name not in fields:
                        fields[field_name] = re.sub(r"\s+", " ", text).strip()

                image_rects = [
                    rect
                    for img in page.get_images(full=True)
                    for rect in page.get_image_rects(img[0])
                ]

                for lx0, ly0, lx1, ly1, field_name in label_blocks:
                    if field_name in fields or field_name not in ("tax_value", "tc_value"):
                        continue
                    # No text value in this row -- check for a barcode image instead
                    # (GİB-issued Vergi Levhası PDFs often render VKN/TC as a
                    # barcode graphic, not selectable text).
                    row_images = [
                        r for r in image_rects
                        if r.x0 >= lx1 - 10 and r.y0 < ly1 and r.y1 > ly0
                    ]
                    if not row_images:
                        continue
                    barcode_text = _ocr_barcode_digits(page, row_images[0])
                    digits = re.sub(r"\D", "", normalize_ocr_digit_confusions(barcode_text))
                    target_len = 10 if field_name == "tax_value" else 11
                    if len(digits) == target_len:
                        fields[field_name] = digits
    except Exception as e:
        print(f"⚠️ Vergi Levhası PDF ayrıştırma hatası: {e}")
        return {}

    return fields


def extract_invoice_fields_from_attachments(attachments) -> dict:
    """Best-effort merged invoice fields (company_name/person_name/tax_office/
    tax_value/tc_value/address) out of every image/PDF attachment. Tries the
    geometric PDF parser first (most reliable when it applies); falls back to
    flat-text OCR parsing for photos, and for PDFs that don't look like a
    Vergi Levhası. First attachment to provide a given field wins -- doesn't
    overwrite a field already found in an earlier attachment."""
    from validators import extract_vergi_levhasi_fields_from_text, extract_kase_fields_from_text

    fields: dict = {}

    def merge_in(new_fields: dict) -> None:
        for key, value in new_fields.items():
            fields.setdefault(key, value)

    for payload, content_type in attachments:
        if content_type in PDF_CONTENT_TYPES:
            pdf_fields = extract_vergi_levhasi_fields_from_pdf(payload)
            merge_in(pdf_fields)
            if not pdf_fields:
                text = extract_text_from_pdf(payload)
                merge_in(extract_vergi_levhasi_fields_from_text(text))
                merge_in(extract_kase_fields_from_text(text))
        else:
            text = extract_text_from_image(payload)
            merge_in(extract_vergi_levhasi_fields_from_text(text))
            merge_in(extract_kase_fields_from_text(text))

    return fields
