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
import subprocess
import tempfile

from PIL import Image

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
_TESSDATA_DIR = os.path.join(_PROJECT_DIR, "tessdata")
_TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

IMAGE_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/tiff", "image/bmp", "image/webp"}


def is_ocr_available() -> bool:
    """Whether both the Tesseract binary and local Turkish trained data are present."""
    tur_data = os.path.join(_TESSDATA_DIR, "tur.traineddata")
    return os.path.exists(_TESSERACT_CMD) and os.path.exists(tur_data)


def extract_text_from_image(image_bytes: bytes) -> str:
    """OCR a single image attachment's bytes to text. Returns "" on any failure
    (corrupt image, missing binary, unreadable format) -- OCR is a best-effort
    supplement to the email body text, never something that should crash mail
    processing.

    Shells out to tesseract.exe directly rather than using pytesseract's
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

        result = subprocess.run(
            [_TESSERACT_CMD, tmp_path, "stdout", "--tessdata-dir", _TESSDATA_DIR, "-l", "tur+eng"],
            capture_output=True,
            timeout=30,
        )
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


def extract_text_from_images(image_bytes_list) -> str:
    """OCR multiple attachments and join the results with blank lines between
    them (kept separate so downstream per-document label parsing doesn't run
    two unrelated documents' text together)."""
    texts = [extract_text_from_image(b) for b in image_bytes_list]
    return "\n\n".join(t for t in texts if t.strip())
