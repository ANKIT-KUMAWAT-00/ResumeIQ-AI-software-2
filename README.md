# ResumeIQ AI

A full-stack, credential-driven AI resume intelligence SaaS starter built around the supplied master prompt and the supplied resume PDF as the visual reference for the LPU Standard template.

## Stack
- Frontend: Next.js App Router, React, TypeScript strict mode, Tailwind CSS, Framer Motion, Lucide.
- API/worker: FastAPI, Pydantic v2, SQLAlchemy, Alembic, RQ/Redis.
- Data: PostgreSQL; local private filesystem storage for development with optional S3-compatible storage configuration.
- AI: Google Gen AI SDK (`google-genai`) only; Gemini calls are backend-only.
- Documents: pdfplumber, python-docx, LibreOffice PDF conversion, optional Tesseract OCR.
- Payments: Razorpay order API, checkout signature validation, webhook signature verification and idempotency.

## Quick start (Docker)
1. Copy `.env.example` to `.env` and set `SECRET_KEY` to a long random value.
2. For AI, set `GEMINI_API_KEY` and `GEMINI_MODEL`. For email OTP delivery configure SMTP; without SMTP, OTPs are printed and returned only in development mode.
3. Configure Razorpay test credentials to enable checkout. Payment features return a clear configuration error until configured.
4. Run `docker compose up --build`.
5. Open `http://localhost:3000` and API docs at `http://localhost:8000/docs`.
6. Run migrations in a second terminal: `docker compose exec api alembic upgrade head`.

## Local development
Backend: Python 3.11+, PostgreSQL, Redis, LibreOffice; Tesseract is optional. If you use the supplied `.env.example` locally, change `DATABASE_URL` to `postgresql+psycopg://resumeiq:resumeiq@localhost:5432/resumeiq` (or use SQLite for a quick local smoke test) and set `REDIS_URL=redis://localhost:6379/0`. The `.env.example` database hostname `db` is for Docker Compose.
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
In another terminal, run the worker: `cd backend && rq worker resumeiq --url redis://localhost:6379/0`.
Frontend: Node 20+
```bash
cd frontend
npm install
npm run dev
```
Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`.

## Features implemented in this repository
- Email OTP sign-in with hashed OTPs, expiry and attempt limits, server-stored hashed/revocable sessions, HTTP-only cookies, origin checks, and optional SMTP delivery.
- Server-side package catalog and entitlements.
- Private PDF/DOCX upload validation and ownership-scoped resources.
- Gemini extraction/review service with strict Pydantic validation, bounded retries, explicit untrusted-document handling, and clear unavailable-credential errors.
- Nine editable role rubrics seeded from JSON into PostgreSQL and edited through the admin workspace.
- RQ background processing with persisted job state and status polling; synchronous fallback can be enabled for local testing.
- Template specifications, deterministic DOCX generation, PDF conversion, and DOCX/PDF template analyzer CLI.
- Razorpay order creation, checkout signature verification, webhook signature validation, event idempotency, and state transition checks.
- Account data export/deletion endpoints, a recurring retention cleanup service, admin-protected order/refund/review/template/rubric/revision/testimonial endpoints, and audit events.
- Futuristic responsive landing page, package cards, login, live template preview controls, upload/analysis workspace, results, testimonial consent flow, and admin operations console.
- Docker Compose, Dockerfiles, Alembic migration, CI workflow, and backend tests.

## Important deployment prerequisites
- Replace development secrets; configure HTTPS, trusted origins, secure cookies, database backups, Redis persistence, private S3 storage, SMTP, Gemini, and Razorpay webhook settings before production.
- For local development, uploads use a private filesystem directory. Set `STORAGE_BACKEND=s3` and S3 variables for object storage.
- If `GEMINI_API_KEY` is missing, AI jobs fail with a truthful configuration error; the app does not invent scores or review results.
- If Razorpay credentials are missing, order creation fails clearly; the app never fabricates payment success.
- The supplied PDF is a personal resume sample, not an official LPU placement-cell style guide. `lpu-standard` is based on the observable layout (single-column, uppercase headings, right-aligned dates, compact spacing) and its spec records that limitation. It must not be marketed as officially certified LPU formatting.
- PDF conversion requires LibreOffice. OCR fallback requires Tesseract. These are optional host dependencies and are documented, not bundled into Python.
- Real provider integration and deployment require credentials and infrastructure not available in this workspace. Backend tests and visual regression checks ran locally; no live Gemini call, Razorpay transaction, Docker image build, or frontend dependency build was run here.

## Commands
```bash
# Backend checks
cd backend && pytest -q
# Analyzer
python -m app.services.templates.analyzer /path/to/sample.pdf --output draft.json
# Render representative files
python scripts/render_samples.py
# Frontend checks (requires network access to install npm packages)
cd frontend && npm install && npm run lint && npm run build
# Visual regression (requires LibreOffice and pdftoppm)
cd .. && python scripts/visual_regression.py
```

## Security and privacy
Resume content is sensitive. Avoid logging resume text or secrets. Configure data retention (`RETENTION_DAYS`, default 30), private storage, deletion workflows, and provider policies. Resume text is sent to Google Gemini only for requested analysis; disclose this in the privacy notice. Role-fit is an advisory heuristic, not an ATS score guarantee or hiring probability. No employment outcome is promised.

See `docs/` for architecture, API, security, setup, deployment, payment guides, and the verification report. Visual golden PNGs live in `visual_regression/golden/`; use `python scripts/visual_regression.py --update` only when intentionally accepting a new layout baseline.
