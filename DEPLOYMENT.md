# 100% Focus Club — Deployment

This package is prepared for deployment as a small Python web application.

## Before going public
1. Copy `.env.example` to `.env` or configure the same variables in your hosting provider.
2. Set a long, unique `FOCUS_ADMIN_PASSWORD`.
3. Configure SMTP variables if you want email notifications.
4. Keep the SQLite database on persistent storage. If your host uses ephemeral disks, move the database to a persistent volume or a production database before launch.
5. Put the app behind HTTPS at the hosting provider/reverse proxy.
6. Confirm `/health` returns `ok`.
7. Test all four public forms and the admin login.
8. Set up backups before accepting real submissions.

## Docker
Build:
`docker build -t focusclub .`

Run:
`docker run --env-file .env -p 8080:8080 -v focusclub-data:/app focusclub`

Then open:
`http://localhost:8080`

Admin:
`http://localhost:8080/admin-login`

Health check:
`http://localhost:8080/health`

## Important production note
SQLite is appropriate for an early-stage, low-volume deployment, but for a growing public service with multiple administrators or higher traffic, use a managed production database and persistent storage. Do not publish the default credentials or commit `.env` files.
