# OTP Verification Platform

A browser-based email verification flow backed by a versioned FastAPI API. The project includes cryptographically secure OTP generation, HMAC-protected challenge storage, single-use verification, resend cooldowns, SMTP delivery over STARTTLS, and a responsive accessible web interface.

## Run locally

Use Python 3.9 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Set `OTP_HMAC_SECRET` in `.env` to a unique random value of at least 32 bytes. For example, generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

### Gmail delivery

1. Enable 2-Step Verification on the Google account that will send messages.
2. In that account's Google security settings, create an **App Password** for this application. Use the generated app password here, not your normal Google password. If Google does not offer App Passwords for the account, use another SMTP provider.
3. In `.env`, set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USERNAME` to the full Gmail address, `SMTP_PASSWORD` to the app password, and `SMTP_FROM_EMAIL` to that same Gmail address. Remove spaces if the app password is displayed grouped.
4. Restart Uvicorn after saving `.env`, then request a new code.

Never paste the app password into chat or commit it. SMTP uses STARTTLS on port 587.

Start the application from the repository root:

```bash
uvicorn otp_api.main:app --app-dir packages --reload
```

Open <http://127.0.0.1:8000>. API documentation is available at <http://127.0.0.1:8000/docs>; the health endpoint is <http://127.0.0.1:8000/health>.

The UI and API are same-origin. `POST /api/v1/challenges` accepts an email address and sends a code; `POST /api/v1/challenges/{challenge_id}/verify` accepts the email and code. The issue response never contains the OTP. Verification responses are marked `Cache-Control: no-store`.

## Configuration

Settings are loaded from environment variables or `.env` in the working directory. See [.env.example](./.env.example) for the supported values. `APP_ENV=production` requires a non-default HMAC secret and an SMTP host. Do not commit `.env` or provider credentials.

## Security and deployment status

This is a complete, runnable single-process application foundation, **not a production-ready multi-instance authentication service**. Challenges, resend state, and request throttles are held in process memory: a restart loses them, and multiple workers do not share them. Before public or multi-worker deployment, replace these with a persistent store and atomic challenge transitions, shared/distributed rate limits, and an asynchronous mail queue; configure TLS at a trusted reverse proxy, trusted-proxy handling, monitoring, alerting, and operational secret management. The in-memory throttles are defense-in-depth for local use, not a substitute for edge rate limiting.

The app intentionally has no user database or account/session system: it verifies possession of an email address for the supplied challenge only. Add account ownership and session issuance in the application that consumes this verification API.

## Tests and checks

```bash
python -m pytest
ruff check packages tests
```

The integration tests use a fake mail sender and never contact an external SMTP service.
