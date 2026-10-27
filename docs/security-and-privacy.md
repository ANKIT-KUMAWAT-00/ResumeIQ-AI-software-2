# Security and privacy notes

- Set a strong random `SECRET_KEY`, use HTTPS, restrict `FRONTEND_ORIGINS`, and enable secure cookies in production.
- OTPs are hashed, expire, and have attempt limits. Session tokens are random opaque values; only their SHA-256 hashes are stored server-side, and logout revokes the stored session. Auth and upload endpoints have Redis-backed rate limiting with a process-local fallback for development. Configure SMTP before production; development codes are intentionally returned only when `APP_ENV=development`, `ALLOW_DEV_OTP=true`, and SMTP is not configured.
- Do not log resume contents, OTP values, provider secrets, or raw webhook payloads. Audit logs contain event types and non-sensitive identifiers.
- Uploads are capped, checked by file extension and basic signature, stored under opaque names, and only accessible through authenticated routes. Document parsers still process complex untrusted formats; use updated libraries and isolated infrastructure.
- Use private S3-compatible storage in production, encryption, a least-privilege bucket policy, signed URLs, and retention/deletion controls. Local storage is for development.
- Set `RETENTION_DAYS`; Docker Compose includes a retention-cleanup service that checks hourly. For manual runs, use `python -c 'from app.workers.cleanup import cleanup_expired; print(cleanup_expired())'` from the backend directory. External backups and provider-side copies require separate lifecycle policies.
- Resume content is sent to Google Gemini when the user requests AI analysis. Review Google's current terms, data handling, region, and retention settings before production.
- Razorpay webhooks require the raw request body and `RAZORPAY_WEBHOOK_SECRET`; configure the exact endpoint and secret in the provider dashboard.
- This repository has no independent third-party penetration test, external provider certification, or live deployment verification. Complete those before accepting real customers.
