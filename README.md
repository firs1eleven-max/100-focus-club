# 100% Focus Club — Phase 3

Phase 3 adds practical lead management and communication readiness on top of Phase 2.

## Added in Phase 3
- Admin sign-out.
- Submission filtering by type and status.
- Admin notes on every submission.
- Email notification architecture using SMTP environment variables.
- Notification log stored in SQLite, so failed/unconfigured email is visible in the database.
- Dashboard remains backed by SQLite.

## Run locally
Requires Python 3.9+.

```bash
python server.py
```

Site: http://localhost:8080  
Admin: http://localhost:8080/admin-login

Set a real admin password before use:

Windows PowerShell:
```powershell
$env:FOCUS_ADMIN_PASSWORD="your-strong-password"
python server.py
```

### Optional email configuration
Set these variables to enable admin email alerts:

- `FOCUS_ADMIN_EMAIL` — destination for new-submission alerts
- `SMTP_HOST`
- `SMTP_PORT` (default 587)
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

Example (PowerShell):
```powershell
$env:FOCUS_ADMIN_EMAIL="you@example.com"
$env:SMTP_HOST="smtp.example.com"
$env:SMTP_PORT="587"
$env:SMTP_USER="smtp-user"
$env:SMTP_PASSWORD="smtp-password"
$env:SMTP_FROM="website@example.com"
python server.py
```

If SMTP is not configured, submissions still save normally and the notification log records that email was not configured.

## Before public launch
Use production hosting with HTTPS, secure session storage, a production-grade authentication system, rate limiting/spam protection, secure secrets, database backups, privacy/consent review, and a transactional email provider. Do not publish with the default password.
