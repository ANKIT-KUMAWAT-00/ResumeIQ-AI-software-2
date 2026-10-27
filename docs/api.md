# API overview

Base prefix: `/api`. Authentication is an HTTP-only signed session cookie. FastAPI OpenAPI docs are available at `/docs` in the API service.

- `GET /health`, `GET /packages`, `GET /templates`
- `POST /auth/request-otp`, `POST /auth/verify-otp`, `POST /auth/logout`, `GET /auth/me`
- `POST /payments/orders`, `POST /payments/verify`, `POST /payments/webhook`, `GET /orders/me`
- `POST /resumes`, `GET /resumes`, `GET /resumes/{id}`, `GET /resumes/{id}/original/download`, `POST /resumes/{id}/retry`
- `GET /outputs/{id}/download`
- `GET /account/export`, `DELETE /account`
- `POST /resumes/{id}/revision` for the Full Makeover revision allowance
- `GET /testimonials`, `POST /testimonials` (public display requires explicit user consent)
- Admin: `GET /admin/orders`, `POST /admin/orders/{id}/refund`, `GET /admin/reviews/queue`, `PUT /admin/resumes/{id}/review`, `GET/PATCH /admin/revisions`, `GET /admin/templates`, `POST /admin/templates/analyze`, `PUT /admin/templates/{id}`, `POST /admin/templates/{id}/publish`, `GET/PUT /admin/rubrics`, `GET/POST /admin/testimonials`, `POST /admin/testimonials/{id}/approve`, `GET /admin/audit-log`, `GET /admin/analytics`

All user-specific resume and output lookups check resource ownership server-side. Admin routes require the user role to be set to `admin` (the email must be listed in `ADMIN_EMAILS` at sign-in). Prices and package entitlements are server-side.
