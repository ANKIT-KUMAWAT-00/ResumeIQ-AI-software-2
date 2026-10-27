# Verification report

Last local verification in the build environment:

- Backend automated tests: **30 passed, 1 skipped**. The skipped test requires configured Razorpay credentials and intentionally avoids creating a live order.
- Python syntax: `compileall` passed for backend app, tests, and scripts.
- Alembic migrations: clean SQLite migration chain applied successfully through the current head; PostgreSQL is the intended Compose database.
- Template rendering: DOCX and PDF generated for LPU Standard, ATS Clean, and Modern One-Page. LPU Standard rendered to one page in this environment; ATS Clean rendered to two pages; Modern One-Page rendered to one page. Page count can vary with content and fonts.
- Visual regression: all pages compared against checked-in golden PNGs; all three templates matched with zero pixel difference in the latest local run.
- Template analyzer: successfully produced a validated draft from the supplied reference PDF.
- Frontend TypeScript/TSX syntax transpilation: 12 files checked with no syntax diagnostics.

Not verified in this environment:

- A full Next.js `npm run lint` / `npm run build`: npm dependencies could not be installed because network access was unavailable. Run these commands after `npm install` in a network-enabled environment.
- Docker image builds or `docker compose up`: Docker was not available in the build environment.
- Live Gemini calls, SMTP delivery, Razorpay checkout/refund, or real webhook delivery: provider credentials and external services were not available. The relevant paths are credential-driven and have offline unit coverage for signature and state-transition logic, but production integration still needs test-mode end-to-end verification.
- Independent penetration testing, legal review, or production deployment.

Do not treat the successful unit tests as a production certification.
