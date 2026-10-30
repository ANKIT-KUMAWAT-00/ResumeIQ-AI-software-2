from pathlib import Path
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.models import User
from app.db.session import SessionLocal
from app.core.security import issue_session

ROOT = Path(__file__).resolve().parents[2]

def get_auth_client():
    client = TestClient(app)
    db = SessionLocal()
    uid = uuid.uuid4().hex[:8]
    user = User(email=f"tpl-user-{uid}@example.com", role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = issue_session(user.id, db)
    db.commit()
    db.close()
    client.cookies.set(settings.session_cookie_name, token)
    return client, user

def test_list_templates_includes_lpu():
    client = TestClient(app)
    resp = client.get("/api/templates")
    assert resp.status_code == 200
    templates = resp.json()
    assert len(templates) >= 3
    ids = [t["template_id"] for t in templates]
    assert "lpu-standard" in ids
    lpu = next(t for t in templates if t["template_id"] == "lpu-standard")
    assert lpu["display_name"] == "LPU Standard"
    assert len(lpu["sections"]) >= 5

def test_template_specification_endpoint():
    client = TestClient(app)
    resp = client.get("/api/templates/lpu-standard/specification")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["template_id"] == "lpu-standard"
    assert "sections" in spec
    assert "margins" in spec
    assert "fonts" in spec

def test_upload_and_confirm_custom_template():
    client, user = get_auth_client()
    pdf_path = ROOT / "sample_data/reference_resume.pdf"
    if not pdf_path.exists():
        return

    # 1. Upload custom PDF template
    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/templates/upload",
            files={"file": ("my-custom-template.pdf", f, "application/pdf")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "template_id" in data
    assert data["template_type"] == "custom_pdf"
    assert data["is_confirmed"] is False
    assert data["analysis_status"] == "analyzed"
    tpl_id = data["template_id"]

    # 2. Confirm template
    conf_resp = client.post(f"/api/templates/{tpl_id}/confirm")
    assert conf_resp.status_code == 200
    assert conf_resp.json()["is_confirmed"] is True

    # 3. Confirmed template now appears in /templates
    list_resp = client.get("/api/templates")
    custom_ids = [t["template_id"] for t in list_resp.json()]
    assert tpl_id in custom_ids

