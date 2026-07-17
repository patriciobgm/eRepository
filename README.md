# Faculty eRepository

A secure document repository for public Senior High School faculty, built with Django REST Framework and React/MUI.

## Included

- Teacher, Master Teacher, and Assistant Principal roles
- Self-registration with Assistant Principal approval
- Automatically provisioned private repository for every faculty account
- Shared repositories created and managed only by the Assistant Principal
- Office, PDF, text, image, OpenDocument, CSV, and ZIP uploads (50 MB default limit)
- Document ownership, immutable revision history, SHA-256 checksums, archive/restore, and protected downloads
- Search, tags, repository filters, dashboards, and responsive MUI interface
- Append-only audit trail for create, update, revision, download, archive, restore, and delete events
- Profile/avatar management, password validation with email confirmation, JWT sessions, and authenticator-app 2FA
- Staff management and registration approval queue

## Local setup

Backend (Python 3.11+):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

- `admin@school.edu` — Assistant Principal
- `teacher@school.edu` — Teacher
- `master@school.edu` — Master Teacher

The development email backend prints password-change and reset emails in the Django terminal.

## Verification

```bash
cd backend && .venv/bin/python manage.py test
cd frontend && npm run lint && npm run build
```

## Production notes

Set `DJANGO_DEBUG=False`, a long random `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `FRONTEND_URL`. Configure SMTP through Django email settings, use PostgreSQL and private object storage for documents, serve everything over HTTPS, run malware scanning on uploads, and back up both the database and stored files. Production security flags are enabled automatically when debug mode is off.

The current SQLite and local-media configuration is intended for development. Document downloads are routed through an authenticated API endpoint; do not expose the media directory directly in production.

