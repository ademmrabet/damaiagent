"""
Wraps Neon Object Storage (an S3-compatible bucket, provisioned via
neon.ts/`neon deploy` - see docs/decisions.md, 2026-09-20) for chat-
message attachments.

Kept as thin as webapp/auth.py's split from webapp/oauth.py: this
module only knows how to talk to the bucket (upload, presign a
download URL, validate what's allowed in). It has no idea a
Conversation or a message exists - webapp/backend.py's routes own the
question of who's allowed to upload or fetch a given attachment.

Env vars, matching exactly what `neon deploy` writes to .env.local:
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_ENDPOINT_URL_S3,
AWS_REGION - plus NEON_BUCKET_NAME, which isn't a Neon-provided value,
just the name we gave the bucket in neon.ts.
"""

import os
import uuid

import boto3
from botocore.config import Config
from fastapi import HTTPException, UploadFile, status

BUCKET_NAME = os.getenv("NEON_BUCKET_NAME", "uploads")
PRESIGNED_URL_EXPIRY_SECONDS = 5 * 60

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB - a chat attachment, not a file server

# Deliberately an allowlist, not a denylist - a new, unanticipated file
# type should fail closed (upload rejected) rather than fail open
# (silently accepted and later served back with whatever content-type
# a browser decides to trust).
ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "application/pdf",
    "text/plain",
    "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _client():
    # Constructed per-call rather than at import time - lets tests
    # monkeypatch the env vars first and still get a client that picks
    # them up, and avoids crashing every other route in backend.py at
    # import time on a dev machine that has no bucket configured yet.
    return boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def storage_configured() -> bool:
    return bool(os.getenv("AWS_ENDPOINT_URL_S3") and os.getenv("AWS_ACCESS_KEY_ID"))


def upload_attachment(file: UploadFile, uploader_id: str, contents: bytes) -> dict:
    """
    Validates and uploads one attachment. Takes `contents` already
    read (rather than reading file.file itself) so the caller enforces
    the size cap up front, before any bytes reach the network call -
    same reasoning as checking a cheque's amount before mailing it.

    Returns the metadata that gets stored in a message's
    `meta.attachment` (see webapp/backend.py's add_message route) -
    never the raw bytes, and never a permanent URL (see
    presign_download for why that's generated fresh on each read).
    """
    if not storage_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File uploads aren't configured yet - the object storage bucket hasn't been set up.",
        )

    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File is too large - the limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type {content_type!r} isn't supported.",
        )

    filename = file.filename or "upload"
    # uploader_id namespacing isn't an access control (that's the
    # conversation-scoped check in webapp/backend.py) - it just keeps
    # one person's uploads from colliding with or overwriting another's
    # if two people happen to attach a file with the same name.
    key = f"attachments/{uploader_id}/{uuid.uuid4()}-{filename}"

    _client().put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=contents,
        ContentType=content_type,
    )

    return {
        "key": key,
        "filename": filename,
        "content_type": content_type,
        "size": len(contents),
    }


def presign_download(key: str) -> str:
    """
    Short-lived (5 minute) signed URL rather than a permanent public
    link - the bucket is private, and a conversation (especially a
    shared one) can be reopened long after the attachment was posted,
    so there's no single point where it would be correct to mint a
    URL "for good." Callers regenerate one each time an attachment is
    actually viewed (see GET /api/conversations/{id}/attachments/{key}).
    """
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": key},
        ExpiresIn=PRESIGNED_URL_EXPIRY_SECONDS,
    )
