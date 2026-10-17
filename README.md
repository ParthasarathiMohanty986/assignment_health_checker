# Assignment Health

A standalone Django MVP for instructors: upload a text PDF, review extracted resource checks, execute real Python validations, and optionally request AI suggestions based on failure evidence.

## Local setup (PowerShell, Python 3.12)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py runserver 127.0.0.1:8002
```

Open http://127.0.0.1:8002 and choose **Open local workspace**. That button is restricted to loopback requests with DEBUG enabled. There is no shared default password. For ordinary authenticated deployment, create accounts with `manage.py createsuperuser`; sign-in and all assignment queries are owner-scoped.

## What works

- PDF text and embedded-URL extraction with source-page numbers (5 MB / 30 pages).
- Editable proposals based on URLs and extensions, not AI. Expected fields require instructor review.
- Up to 8 checks: HTTP status, UTF-8 comma-separated CSV parsing/column names, JSON parsing/top-level keys.
- Real public-network GET requests, bounded bodies and request times. Private IP ranges, URL credentials, query strings, unusual ports and private redirects are blocked. Resolved addresses are pinned to sockets.
- Passed, failed and unverified states, saved run history and check snapshots, JSON report export.
- Explicit demo using local fixtures: pass, missing CSV column, missing JSON key and protected endpoint. Demo results are never presented as real network tests.
- Optional Groq Chat Completions API suggestions; requires explicit consent after reviewing the exact evidence payload. Full PDF, user identity, resource URLs and bodies are excluded. There is no automatic fix execution.

## AI configuration

Set environment variables before starting the server:

```powershell
$env:GROQ_API_KEY = 'YOUR_KEY'
$env:GROQ_MODEL = 'openai/gpt-oss-20b'
```

Use a model enabled for your API project. Keys remain server-side; never commit them. You can also put these values in the project-root `.env` file, which is loaded at startup. Existing process environment variables take priority. Restart the server after editing `.env`. AI requests are sent to `https://api.groq.com/openai/v1/chat/completions`. Review evidence before sending: redaction is best-effort, not a guarantee of removing all confidential content. See https://console.groq.com/docs/text-chat.

## Limits

This MVP does not include OCR, LLM-generated checks, arbitrary student-code execution, authenticated endpoint adapters, POST submissions, semantic grading, schedulers, or automatic repairs. Scanned PDFs get an explicit OCR-needed message. Response checks are syntactic, not proof that an assignment is pedagogically correct. A successful GET alone does not prove a workflow works. HTTP 401/403/429 and network failures are reported as unverified.

Uploaded original PDFs are not retained. Extracted text, expectations, results, and suggestions are stored in local SQLite. Do not deploy this local configuration unchanged: provision production users, HTTPS, secrets, database backup/persistence, application/worker limits, upload scanning/resource isolation and network egress controls before accepting untrusted public uploads. Run checks in background workers before scaling beyond a small pilot.

## Verification

```powershell
.venv\Scripts\python manage.py test
.venv\Scripts\python manage.py check
```

Tests cover PDF extraction, missing columns, malformed rows, JSON keys, protected checks, private-target blocking, access control and the review/run/report workflow. AI tests use mock responses and never incur API charges.

## Architecture

`checker/extract.py`: PDF parsing and URL proposals. `forms.py`: instructor expectations. `network.py`: bounded public fetcher. `runner.py`: deterministic checks. `ai.py`: evidence minimization and optional suggestions. `models.py`: assignments/run snapshots. `views.py`: owner-scoped workflows. `templates/` and `static/`: server-rendered interface.

Inspired by Anand's public account of assignment dependencies changing: https://www.s-anand.net/blog/tds-jan-2026-ga1-released/. This is an independent prototype, not an official course integration.


## Render deployment

Create a separate GitHub repository for this directory, then create a Render Blueprint from that repository using render.yaml. The blueprint uses a free web service and a free PostgreSQL database. Free Render PostgreSQL expires after 30 days; upgrade or export your data before expiry. Local SQLite data is not uploaded.

During setup, enter GROQ_API_KEY, INSTRUCTOR_USERNAME, and INSTRUCTOR_PASSWORD (at least 12 characters) in Render, not GitHub. The build creates the initial instructor once and never resets an existing account password. Sign in using those credentials. Public registration is not implemented. The local workspace shortcut is disabled in production.

The build installs dependencies, collects static files, migrates PostgreSQL, and creates the initial account. Gunicorn serves the app. Render supplies the hostname and database URL; a Django secret is generated automatically. Use HTTPS. See https://render.com/docs/deploy-django and https://render.com/docs/free.
