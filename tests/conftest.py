import os
import sys
import tempfile

import pytest

# main.py, auth.py, and database.py read these when they are imported, so they have to be
# set before the imports below; every test run gets its own throwaway database and uploads folder
TEST_DIR = tempfile.mkdtemp(prefix="vault-tests-")
os.environ["SECRET_KEY"] = "test-secret-not-used-anywhere-else"
os.environ["VT_API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DIR}/test.db"
os.environ["UPLOAD_DIR"] = os.path.join(TEST_DIR, "uploads")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

import main  # noqa: E402
from database import engine  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    # start every test from empty tables so tests can't affect each other
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def no_virustotal(monkeypatch):
    # tests must never call the real VirusTotal API
    monkeypatch.setattr(main, "submit_to_virustotal", lambda file_path: "analysis-123")


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def register_and_login(client, username):
    client.post(
        "/register",
        json={"username": username, "email": f"{username}@example.com", "password": "correct-password"},
    )
    response = client.post("/login", json={"username": username, "password": "correct-password"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def alice(client):
    return register_and_login(client, "alice")


@pytest.fixture
def bob(client):
    return register_and_login(client, "bob")


@pytest.fixture
def alice_file_id(client, alice):
    response = client.post(
        "/files/upload", headers=alice, files={"file": ("notes.txt", b"alice's notes", "text/plain")}
    )
    return response.json()["file_id"]
