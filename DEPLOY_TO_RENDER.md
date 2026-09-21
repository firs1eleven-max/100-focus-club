# 100% Focus Club — Render Deployment

This package is prepared for deployment on Render. A Render account and a domain are still required; credentials are intentionally not included.

## 1. Create the service
1. Create a new Web Service from this project/repository.
2. Select Docker as the runtime.
3. Use the included `render.yaml` as the blueprint, or configure the service manually.
4. The included persistent disk mounts at `/data` so the SQLite database survives normal redeploys on a paid persistent-disk service.

## 2. Important database setting
The current application database path is inside the application directory. Before the first production deployment, change `DB` in `server.py` to:

`Path(os.environ.get('FOCUS_DATA_DIR','/data')) / 'focusclub.db'`

and add:

`FOCUS_DATA_DIR=/data`

as an environment variable. This keeps the production database on the persistent disk.

## 3. Required secrets
Set these in the hosting dashboard, never in source control:
- FOCUS_ADMIN_USER
- FOCUS_ADMIN_PASSWORD
- FOCUS_ADMIN_EMAIL
- SMTP_HOST
- SMTP_PORT
- SMTP_USER
- SMTP_PASSWORD
- SMTP_FROM

Use a long unique admin password.

## 4. Before opening the site publicly
- Visit `/health` and confirm it returns `ok: true`.
- Test a school request.
- Test a youth registration.
- Test a sponsor inquiry.
- Test admin login.
- Confirm each submission appears in the dashboard.
- Confirm email notifications arrive.
- Confirm logout works.
- Confirm HTTPS is active.
- Connect the custom domain after the site is verified.

## 5. Domain
After the service is live, add the organization's domain in the hosting provider and follow its DNS instructions. Do not put DNS credentials into the application.

## 6. Production note
This launch package uses SQLite with a persistent disk for simplicity. If submission volume becomes substantial or multiple administrators need concurrent access, migrate the database to PostgreSQL/Supabase in a later hardening phase.
