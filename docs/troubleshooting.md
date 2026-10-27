# Troubleshooting

- **Gemini configuration error:** set `GEMINI_API_KEY` and a supported `GEMINI_MODEL` in both API and worker services.
- **Payment configuration error:** use Razorpay test credentials; verify webhook secret and provider event settings.
- **OTP not delivered:** configure SMTP. Development OTP is returned only in local development mode and must not be enabled in production.
- **Resume stays queued:** check Redis availability, worker logs, and that API and worker share database and storage configuration.
- **PDF missing:** ensure LibreOffice is installed and available on PATH; DOCX may still be available when PDF conversion fails.
- **Scanned PDF unreadable:** install Tesseract and the `pytesseract` / `pdf2image` packages plus system PDF utilities, or convert to a text-based PDF/DOCX first.
- **CORS or cookies fail:** set the exact frontend origin, HTTPS in production, and matching cookie configuration.
- **Migration errors:** ensure the database is reachable and run `alembic upgrade head` from `backend/`.
