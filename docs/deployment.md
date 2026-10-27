# Deployment guide

## Docker Compose
Copy `.env.example` to `.env`; configure `SECRET_KEY`, Gemini, SMTP, Razorpay, and optional S3 values. `docker compose up --build` starts PostgreSQL, Redis, API, worker, and frontend. Run `docker compose exec api alembic upgrade head`. Local Compose uses development database credentials and must not be exposed publicly.

## Vercel frontend
Deploy `frontend/` as the root directory. Set `NEXT_PUBLIC_API_URL` to the public API origin. Configure CORS on the API to include the exact Vercel origin. Cookie-based sessions require HTTPS and same-site/cross-origin settings to be tested in the chosen domain arrangement. For unrelated domains, configure the cookie policy and CSRF protection before launch.

## Render / Railway API and worker
Deploy `backend/` twice from the same Dockerfile: API command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`; worker command `rq worker resumeiq --url $REDIS_URL`. Provision PostgreSQL and Redis. Set the same environment variables in both services and mount persistent private storage or configure S3. Run `alembic upgrade head` as a release/pre-deploy command.

## Required secrets and services
- `SECRET_KEY` (generate a strong random value)
- `GEMINI_API_KEY`, `GEMINI_MODEL`
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
- SMTP credentials for production OTP delivery
- PostgreSQL, Redis, and optionally S3-compatible bucket credentials
- Admin email allowlist via `ADMIN_EMAILS`

Configure Razorpay webhook events for `payment.captured`, `payment.failed`, and `order.paid`. Do not enable live mode until test-mode end-to-end tests, privacy/legal review, backups, and security review are complete.
