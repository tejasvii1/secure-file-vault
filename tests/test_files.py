import os

from sqlmodel import Session, select

import main
from database import engine
from models import AuditLog, File


def upload(client, headers, name="notes.txt", content=b"hello"):
    return client.post("/files/upload", headers=headers, files={"file": (name, content, "text/plain")})


def test_upload_requires_login(client):
    response = client.post("/files/upload", files={"file": ("notes.txt", b"hello", "text/plain")})

    assert response.status_code in (401, 403)


def test_upload_then_download_returns_same_bytes(client, alice):
    file_id = upload(client, alice, content=b"alice's notes").json()["file_id"]

    response = client.get(f"/files/{file_id}/download", headers=alice)

    assert response.status_code == 200
    assert response.content == b"alice's notes"


def test_upload_stores_file_under_generated_name(client, alice):
    upload(client, alice, name="notes.txt")

    with Session(engine) as session:
        record = session.exec(select(File)).one()
    assert record.filename == "notes.txt"
    assert os.path.basename(record.stored_path) != "notes.txt"
    assert os.path.exists(record.stored_path)
    assert record.virustotal_result == "pending:analysis-123"


def test_upload_rejects_dangerous_extension(client, alice):
    response = upload(client, alice, name="malware.EXE")

    assert response.status_code == 400
    assert client.get("/files", headers=alice).json() == []


def test_upload_rejects_file_over_size_limit(client, alice):
    response = upload(client, alice, content=b"x" * (main.ALLOWED_MAX_SIZE + 1))

    assert response.status_code == 413


def test_upload_still_succeeds_when_virustotal_is_down(client, alice, monkeypatch):
    def fail(filename, contents):
        raise RuntimeError("VirusTotal unreachable")

    monkeypatch.setattr(main, "submit_to_virustotal", fail)

    response = upload(client, alice)

    assert response.status_code == 200
    assert client.get("/files", headers=alice).json()[0]["virustotal_result"] == "scan_failed"


def test_sanitize_filename_strips_path_traversal():
    assert main.sanitize_filename("../../etc/passwd") == "passwd"
    assert "/" not in main.sanitize_filename("a/b/c.txt")
    assert main.sanitize_filename("my file (1).txt") == "my_file__1_.txt"


def test_list_only_shows_own_files(client, alice, bob):
    upload(client, alice, name="alice.txt")
    upload(client, bob, name="bob.txt")

    alice_files = client.get("/files", headers=alice).json()

    assert [f["filename"] for f in alice_files] == ["alice.txt"]


def test_other_user_cannot_download_file(client, bob, alice_file_id):
    response = client.get(f"/files/{alice_file_id}/download", headers=bob)

    assert response.status_code == 403


def test_other_user_cannot_delete_file(client, alice, bob, alice_file_id):
    response = client.delete(f"/files/{alice_file_id}", headers=bob)

    assert response.status_code == 403
    assert len(client.get("/files", headers=alice).json()) == 1


def test_other_user_cannot_check_scan(client, bob, alice_file_id):
    response = client.get(f"/files/{alice_file_id}/scan", headers=bob)

    assert response.status_code == 403


def test_missing_file_returns_404(client, alice):
    assert client.get("/files/999/download", headers=alice).status_code == 404
    assert client.delete("/files/999", headers=alice).status_code == 404


def test_delete_removes_record_and_file_from_disk(client, alice, alice_file_id):
    with Session(engine) as session:
        stored_path = session.get(File, alice_file_id).stored_path

    response = client.delete(f"/files/{alice_file_id}", headers=alice)

    assert response.status_code == 200
    assert client.get("/files", headers=alice).json() == []
    assert not os.path.exists(stored_path)


def test_scan_result_is_saved_once_virustotal_finishes(client, alice, alice_file_id, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"attributes": {"status": "completed", "stats": {"malicious": 2, "suspicious": 0}}}}

    monkeypatch.setattr(main.requests, "get", lambda url, headers: FakeResponse())

    response = client.get(f"/files/{alice_file_id}/scan", headers=alice)

    assert response.json()["scan_result"] == "malicious"
    assert client.get("/files", headers=alice).json()[0]["virustotal_result"] == "malicious"


def test_file_actions_are_audit_logged(client, alice, alice_file_id):
    client.get(f"/files/{alice_file_id}/download", headers=alice)
    client.delete(f"/files/{alice_file_id}", headers=alice)

    with Session(engine) as session:
        actions = [entry.action for entry in session.exec(select(AuditLog).order_by(AuditLog.id)).all()]
    assert actions == ["login", "upload:notes.txt", "download:notes.txt", "delete:notes.txt"]
