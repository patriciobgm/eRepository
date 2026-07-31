# Faculty eRepository

A secure document repository for public Senior High School faculty, built with Django REST Framework and React/MUI.

## Included

- Teacher, Master Teacher, Principal, and Django superadmin authority
- Self-registration with Principal approval
- Google Identity Services login and registration for Gmail and Google Workspace accounts
- Superadmin-managed Principal access, department CRUD, role-based position CRUD, and designation catalog
- Managed default departments: TVL, ABM & Mathematics, Science & Social Sciences, PE & Language, and Admin
- Automatically provisioned private repository for every faculty account
- Principal/Superadmin designation assignment for Teachers and Master Teachers, with assignment history
- Purpose-specific shared repositories initiated by the Principal or faculty with an authorized designation
- Private/shared repository folders with folder ownership and root-folder uploads
- Persistent per-user notifications with unread, read, remove, and clear-all controls
- Office, PDF, text, image, OpenDocument, CSV, and ZIP uploads (50 MB default limit)
- Document ownership, immutable revision history, SHA-256 checksums, archive/restore, and protected downloads
- Search, tags, repository filters, dashboards, and responsive MUI interface
- Append-only audit trail for create, update, revision, download, archive, restore, and delete events
- Profile/avatar management, password validation with email confirmation, JWT sessions, and authenticator-app 2FA
- Superadmin administration, Principal staff management, and registration approval queue
- Provider-aware forgot/reset-password screens and API rate limiting

## Local setup

Backend (Python 3.11+):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Frontend (Node 20+):

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`. Demo accounts use password `DemoPass!2026`:

- `superadmin@school.edu` — Superadmin
- `admin@school.edu` — Principal
- `teacher@school.edu` — Teacher
- `master@school.edu` — Master Teacher

The development email backend prints password-change and reset emails in the Django terminal.
Both backend and frontend load their own `.env` files; `.env.example` files are templates only.

## Google sign-in setup

1. In Google Cloud Console, configure the OAuth consent screen.
2. Create an OAuth client with application type **Web application**.
3. Add `http://localhost:5173` under **Authorized JavaScript origins**. Add the production HTTPS frontend origin when deploying.
4. Copy the client ID into both `backend/.env` as `GOOGLE_OAUTH_CLIENT_ID` and `frontend/.env` as `VITE_GOOGLE_CLIENT_ID`.
5. Restart Django and Vite after changing environment variables.

The frontend receives a Google ID token and submits it to Django. Django verifies Google's signature, expiry, issuer, audience, verified email, and stable Google `sub` identifier using Google's official authentication library. No Google client secret is required for this popup ID-token flow.

## API security

The application does not use a shared API key. Individual users authenticate with short-lived JWT bearer access tokens and rotating refresh tokens. Server-side role and object permissions protect repositories and downloads. Additional controls include Google ID-token verification, password validation, optional TOTP 2FA, CORS allowlisting, HTTPS production flags, upload type/size validation, audit logs, and request throttling.

Default throttles are 60 anonymous requests/hour, 1,000 authenticated requests/hour, 10 login or Google-auth attempts/minute, and 5 registrations or password-reset requests/hour. Override them with the `API_*_RATE` environment variables. For multi-process production deployments, configure Django's cache with Redis so throttle counters are shared across application instances. Rate limiting is defense-in-depth and should also be enforced at the reverse proxy or API gateway.

## Verification

```bash
cd backend && .venv/bin/python manage.py test
cd frontend && npm run lint && npm run build
```

## Production notes

Set `DJANGO_DEBUG=False`, a long random `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`, and the Google client ID. Configure SMTP, use PostgreSQL, serve everything over HTTPS, scan uploads for malware, and back up both the database and stored files. Use a shared cache such as Redis if the backend is expanded to multiple processes or servers. Production security flags are enabled automatically when debug mode is off.

The current SQLite and local-media configuration is intended for development. Document downloads are routed through an authenticated API endpoint; do not expose the media directory directly in production.

For the supported Windows, PostgreSQL, Caddy/HTTPS, GoDaddy DNS, Windows service,
backup, restore, and update procedure, see
[`docs/WINDOWS_DEPLOYMENT.md`](docs/WINDOWS_DEPLOYMENT.md).
