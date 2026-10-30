import hashlib
import os

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.utils.text import get_valid_filename
from rest_framework.exceptions import APIException, ValidationError

# Only these types are accepted. The value is the content type WE record.
ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}


class PayloadTooLarge(APIException):
    status_code = 413
    default_detail = "The upload is too large."
    default_code = "payload_too_large"


class DuplicateUpload(APIException):
    status_code = 409
    default_detail = "This file was already uploaded."
    default_code = "duplicate_upload"


def clean_filename(name):
    """Removes folders and unsafe characters from a client-supplied file name."""
    base = os.path.basename(name or "")
    try:
        cleaned = get_valid_filename(base)
    except SuspiciousFileOperation:
        return "document"
    stem, ext = os.path.splitext(cleaned)
    return (stem[:120] or "document") + ext


def validate_upload(uploaded_file):
    """Checks size, type and real content. Returns (clean_name, content_type)."""
    if uploaded_file.size == 0:
        raise ValidationError({"file": "The file is empty."})
    if uploaded_file.size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise PayloadTooLarge("The file is larger than the allowed limit.")

    name = clean_filename(uploaded_file.name)
    extension = os.path.splitext(name)[1].lower()
    if extension not in ALLOWED_TYPES:
        raise ValidationError({"file": "Only PDF and TXT files are allowed."})

    # Look at the real bytes. The name and the browser's content type can be faked.
    uploaded_file.seek(0)
    if extension == ".pdf":
        if uploaded_file.read(5) != b"%PDF-":
            raise ValidationError({"file": "This file is not a valid PDF."})
    else:
        data = uploaded_file.read()
        if b"\x00" in data:
            raise ValidationError({"file": "This file is not a plain text file."})
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError({"file": "Text files must be UTF-8 encoded."}) from exc
    uploaded_file.seek(0)

    return name, ALLOWED_TYPES[extension]


def sha256_of(uploaded_file):
    """Fingerprint of the file content."""
    digest = hashlib.sha256()
    uploaded_file.seek(0)
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()
