import boto3
import pytest
from moto import mock_aws
from sqlmodel import Session

import main
from database import engine
from models import File
from storage import LocalStorage, S3Storage, get_storage

BUCKET = "vault-test-bucket"


@pytest.fixture
def s3_storage(monkeypatch):
    # moto replaces AWS with an in-memory fake, so these tests never touch a real account
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        boto3.client("s3").create_bucket(Bucket=BUCKET)
        yield S3Storage(BUCKET)


def test_local_storage_round_trip(tmp_path):
    storage = LocalStorage(str(tmp_path))

    location = storage.save("abc.txt", b"hello")

    assert storage.read(location) == b"hello"
    storage.delete(location)
    assert storage.read(location) is None


def test_s3_storage_round_trip(s3_storage):
    location = s3_storage.save("abc.txt", b"hello")

    assert location == "uploads/abc.txt"
    assert s3_storage.read(location) == b"hello"
    s3_storage.delete(location)
    assert s3_storage.read(location) is None


def test_s3_objects_are_encrypted_at_rest(s3_storage):
    location = s3_storage.save("abc.txt", b"hello")

    head = s3_storage.client.head_object(Bucket=BUCKET, Key=location)
    assert head["ServerSideEncryption"] == "AES256"


def test_get_storage_picks_backend_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.delenv("S3_BUCKET", raising=False)
    assert isinstance(get_storage(), LocalStorage)

    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET", BUCKET)
    assert isinstance(get_storage(), S3Storage)


def test_api_upload_download_delete_with_s3(client, alice, bob, s3_storage, monkeypatch):
    monkeypatch.setattr(main, "storage", s3_storage)

    upload = client.post("/files/upload", headers=alice, files={"file": ("notes.txt", b"in s3", "text/plain")})
    file_id = upload.json()["file_id"]

    # the object is stored under a generated key, not the user's filename
    keys = [obj["Key"] for obj in s3_storage.client.list_objects_v2(Bucket=BUCKET)["Contents"]]
    assert len(keys) == 1
    assert keys[0].startswith("uploads/") and "notes" not in keys[0]

    assert client.get(f"/files/{file_id}/download", headers=alice).content == b"in s3"
    assert client.get(f"/files/{file_id}/download", headers=bob).status_code == 403

    assert client.delete(f"/files/{file_id}", headers=alice).status_code == 200
    assert "Contents" not in s3_storage.client.list_objects_v2(Bucket=BUCKET)


def test_download_returns_404_when_stored_file_is_gone(client, alice, alice_file_id):
    with Session(engine) as session:
        stored_path = session.get(File, alice_file_id).stored_path
    main.storage.delete(stored_path)

    response = client.get(f"/files/{alice_file_id}/download", headers=alice)

    assert response.status_code == 404
