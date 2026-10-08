from datetime import datetime, timedelta

from jose import jwt
from sqlmodel import Session, select

from auth import ALGORITHM, SECRET_KEY
from database import engine
from models import AuditLog, User

NEW_USER = {"username": "alice", "email": "alice@example.com", "password": "correct-password"}


def test_register_creates_user_with_hashed_password(client):
    response = client.post("/register", json=NEW_USER)

    assert response.status_code == 200
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == "alice")).one()
    assert user.password_hash != NEW_USER["password"]
    assert user.password_hash.startswith("$2")  # bcrypt


def test_register_rejects_duplicate_username(client):
    client.post("/register", json=NEW_USER)
    response = client.post("/register", json={**NEW_USER, "email": "other@example.com"})

    assert response.status_code == 400


def test_register_rejects_invalid_email(client):
    response = client.post("/register", json={**NEW_USER, "email": "not-an-email"})

    assert response.status_code == 422


def test_login_returns_token_that_works_on_me(client):
    client.post("/register", json=NEW_USER)
    response = client.post("/login", json={"username": "alice", "password": "correct-password"})

    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json() == {"username": "alice", "email": "alice@example.com"}


def test_login_rejects_wrong_password(client):
    client.post("/register", json=NEW_USER)
    response = client.post("/login", json={"username": "alice", "password": "wrong-password"})

    assert response.status_code == 401


def test_login_rejects_unknown_user(client):
    response = client.post("/login", json={"username": "nobody", "password": "correct-password"})

    assert response.status_code == 401


def test_me_requires_a_token(client):
    response = client.get("/me")

    assert response.status_code in (401, 403)


def test_me_rejects_tampered_token(client, alice):
    token = alice["Authorization"].removeprefix("Bearer ")
    response = client.get("/me", headers={"Authorization": f"Bearer {token}x"})

    assert response.status_code == 401


def test_me_rejects_expired_token(client, alice):
    expired = jwt.encode(
        {"sub": "alice", "exp": datetime.utcnow() - timedelta(minutes=1)}, SECRET_KEY, algorithm=ALGORITHM
    )
    response = client.get("/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


def test_me_rejects_token_signed_with_another_key(client, alice):
    forged = jwt.encode(
        {"sub": "alice", "exp": datetime.utcnow() + timedelta(minutes=5)}, "attacker-key", algorithm=ALGORITHM
    )
    response = client.get("/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


def test_login_and_logout_are_audit_logged(client, alice):
    client.post("/logout", headers=alice)

    with Session(engine) as session:
        actions = [entry.action for entry in session.exec(select(AuditLog).order_by(AuditLog.id)).all()]
    assert actions == ["login", "logout"]
