# s3-compatible storage for chat attachments

import os
import uuid

import boto3
from botocore.config import Config
from fastapi import HTTPException, UploadFile, status

BUCKET_NAME = os.getenv("NEON_BUCKET_NAME", "uploads")
PRESIGNED_URL_EXPIRY_SECONDS = 5 * 60

MAX_UPLOAD_BYTES = 15 * 1024 * 1024

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


# s3 client, built on each call so env vars are read fresh
def _client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


# true only if all the storage env vars are set
def storage_configured() -> bool:
    return bool(
        os.getenv("AWS_ENDPOINT_URL_S3")
        and os.getenv("AWS_ACCESS_KEY_ID")
        and os.getenv("AWS_SECRET_ACCESS_KEY")
    )


# check the file and upload it to the bucket
def upload_attachment(file: UploadFile, uploader_id: str, contents: bytes) -> dict:
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


# short-lived download link (5 minutes) for a private file
def presign_download(key: str) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": key},
        ExpiresIn=PRESIGNED_URL_EXPIRY_SECONDS,
    )


# read an attachment back from the bucket
def download_attachment(key: str) -> bytes:
    if not storage_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File uploads aren't configured yet - the object storage bucket hasn't been set up.",
        )

    from botocore.exceptions import ClientError

    try:
        obj = _client().get_object(Bucket=BUCKET_NAME, Key=key)
        return obj["Body"].read()
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        ) from exc
