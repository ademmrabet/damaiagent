import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from webapp import storage


def _upload_file(filename="notes.pdf", content_type="application/pdf"):
    return UploadFile(filename=filename, file=io.BytesIO(b"hi"), headers={"content-type": content_type})


@pytest.fixture(autouse=True)
def _configured_storage(monkeypatch):
    # storage_configured() gates upload_attachment on these being set -
    # a dev machine or CI run with no bucket provisioned yet should get
    # a clear 503, not a KeyError from os.environ deep inside _client().
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "https://example-endpoint.test")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("AWS_REGION", "eu-central-1")


def test_upload_rejects_oversized_files():
    contents = b"x" * (storage.MAX_UPLOAD_BYTES + 1)
    with pytest.raises(HTTPException) as exc:
        storage.upload_attachment(_upload_file(), "user-1", contents)
    assert exc.value.status_code == 413


def test_upload_rejects_disallowed_content_type():
    with pytest.raises(HTTPException) as exc:
        storage.upload_attachment(_upload_file(content_type="application/x-msdownload"), "user-1", b"hi")
    assert exc.value.status_code == 415


def test_upload_without_configured_bucket_is_a_clear_503(monkeypatch):
    monkeypatch.delenv("AWS_ENDPOINT_URL_S3", raising=False)
    with pytest.raises(HTTPException) as exc:
        storage.upload_attachment(_upload_file(), "user-1", b"hi")
    assert exc.value.status_code == 503


def test_successful_upload_namespaces_the_key_by_uploader_and_returns_metadata():
    fake_client = MagicMock()
    with patch.object(storage, "_client", return_value=fake_client):
        result = storage.upload_attachment(_upload_file(filename="report.pdf"), "user-42", b"hello world")

    assert result["filename"] == "report.pdf"
    assert result["content_type"] == "application/pdf"
    assert result["size"] == len(b"hello world")
    assert result["key"].startswith("attachments/user-42/")
    assert result["key"].endswith("-report.pdf")

    fake_client.put_object.assert_called_once()
    call_kwargs = fake_client.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == storage.BUCKET_NAME
    assert call_kwargs["Key"] == result["key"]
    assert call_kwargs["Body"] == b"hello world"
    assert call_kwargs["ContentType"] == "application/pdf"


def test_two_uploads_with_the_same_filename_get_different_keys():
    fake_client = MagicMock()
    with patch.object(storage, "_client", return_value=fake_client):
        first = storage.upload_attachment(_upload_file(filename="same.png", content_type="image/png"), "user-1", b"a")
        second = storage.upload_attachment(_upload_file(filename="same.png", content_type="image/png"), "user-1", b"b")

    assert first["key"] != second["key"]


def test_presign_download_asks_for_the_configured_bucket_and_a_short_expiry():
    fake_client = MagicMock()
    fake_client.generate_presigned_url.return_value = "https://example-endpoint.test/signed"
    with patch.object(storage, "_client", return_value=fake_client):
        url = storage.presign_download("attachments/user-1/some-key-report.pdf")

    assert url == "https://example-endpoint.test/signed"
    fake_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": storage.BUCKET_NAME, "Key": "attachments/user-1/some-key-report.pdf"},
        ExpiresIn=storage.PRESIGNED_URL_EXPIRY_SECONDS,
    )
