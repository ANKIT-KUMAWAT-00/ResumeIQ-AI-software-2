# Google Gemini setup

1. Obtain an API key from Google AI Studio / the current Google AI developer console.
2. Set `GEMINI_API_KEY` only in the backend/worker secret environment; never use a `NEXT_PUBLIC_` prefix.
3. Set `GEMINI_MODEL` to a model available to your project (default `gemini-2.5-flash`).
4. Restart API and worker. The health endpoint intentionally does not expose secret presence.
5. Upload a test resume using a verified test order and inspect backend logs for request failures without logging resume text.

The code uses the official `google-genai` SDK, structured JSON response configuration, strict Pydantic validation, bounded retries, versioned prompts, and untrusted-document delimiters. API quota, availability, model access, and billing depend on the provider account. No AI results are fabricated when credentials are absent.
