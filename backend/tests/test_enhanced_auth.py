import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.core.config import settings
from app.models import User, Verification
from app.db.session import SessionLocal
from app.core.security import hash_password, hash_otp

def test_registration_and_dev_verification(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "allow_dev_otp", True)
    monkeypatch.setattr(settings, "smtp_host", "")

    client = TestClient(app)
    uid = uuid.uuid4().hex[:8]
    email = f"test-user-{uid}@example.com"
    reg_payload = {
        "full_name": "Test Candidate",
        "email": email,
        "phone": "+919999999999",
        "password": "SecurePassword123!",
    }
    # 1. Register
    r = client.post("/api/auth/register", json=reg_payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email"] == email
    assert data["full_name"] == "Test Candidate"
    assert data["email_verified"] is False
    assert data["verification"]["simulated"] is True
    assert data["verification"]["development_code"] == "123456"

    # 2. Get profile (me) using session cookie
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    # 3. Verify email with wrong code -> should fail
    bad_verify = client.post("/api/auth/verify-email", json={"email": email, "code": "999999"})
    assert bad_verify.status_code == 400

    # 4. Verify email with development code 123456 -> should succeed
    good_verify = client.post("/api/auth/verify-email", json={"email": email, "code": "123456"})
    assert good_verify.status_code == 200
    assert good_verify.json()["email_verified"] is True

    # 5. Profile should now reflect email_verified = True
    me_after = client.get("/api/auth/me")
    assert me_after.json()["email_verified"] is True

    # 6. Logout
    logout_resp = client.post("/api/auth/logout")
    assert logout_resp.status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    # 7. Login with password
    login_resp = client.post("/api/auth/login", json={"email": email, "password": "SecurePassword123!"})
    assert login_resp.status_code == 200
    assert login_resp.json()["email"] == email

    # 8. Login with wrong password -> 401
    bad_login = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword"})
    assert bad_login.status_code == 401

def test_production_rejects_simulated_verification(monkeypatch):
    """
    Critical requirement:
    APP_ENV=production:
    - Simulated verification forbidden.
    - Real verification provider required.
    - Fail closed if required provider configuration is missing.
    """
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "allow_dev_otp", False)
    monkeypatch.setattr(settings, "smtp_host", "") # missing SMTP

    client = TestClient(app)
    uid = uuid.uuid4().hex[:8]
    email = f"prod-user-{uid}@example.com"

    # Attempting to register in production without SMTP fails closed (503 Service Unavailable)
    reg_resp = client.post(
        "/api/auth/register",
        json={
            "full_name": "Prod Candidate",
            "email": email,
            "password": "SecurePassword123!",
        },
    )
    assert reg_resp.status_code == 503
    assert "Production email provider requires SMTP_HOST" in reg_resp.json()["detail"]

def test_password_reset_flow(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "allow_dev_otp", True)
    monkeypatch.setattr(settings, "smtp_host", "")

    client = TestClient(app)
    uid = uuid.uuid4().hex[:8]
    email = f"reset-{uid}@example.com"

    # Register user
    client.post(
        "/api/auth/register",
        json={"full_name": "Reset Candidate", "email": email, "password": "OldPassword123!"},
    )
    client.post("/api/auth/logout")

    # Request password reset
    forgot_resp = client.post("/api/auth/forgot-password", json={"email": email})
    assert forgot_resp.status_code == 200
    assert forgot_resp.json()["development_code"] == "123456"

    # Reset password with valid code
    reset_resp = client.post(
        "/api/auth/reset-password",
        json={"email": email, "code": "123456", "new_password": "BrandNewPassword123!"},
    )
    assert reset_resp.status_code == 200

    # Old password no longer works
    old_login = client.post("/api/auth/login", json={"email": email, "password": "OldPassword123!"})
    assert old_login.status_code == 401

    # New password works
    new_login = client.post("/api/auth/login", json={"email": email, "password": "BrandNewPassword123!"})
    assert new_login.status_code == 200
    assert new_login.json()["email"] == email

def test_expired_verification_rejected(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "allow_dev_otp", True)

    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    email = f"expired-{uid}@example.com"
    # Create an already-expired verification row
    past = datetime.now(timezone.utc) - timedelta(minutes=15)
    row = Verification(
        identifier=email,
        verification_type="email",
        token_hash=hash_otp("123456"),
        expires_at=past,
        attempts=0,
    )
    db.add(row)
    db.commit()
    db.close()

    client = TestClient(app)
    resp = client.post("/api/auth/verify-email", json={"email": email, "code": "123456"})
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()

