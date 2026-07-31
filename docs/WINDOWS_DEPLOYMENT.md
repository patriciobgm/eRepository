# Windows production deployment guide

This guide deploys the JSHS eRepository as one public HTTPS site:

```text
Internet -> GoDaddy DNS -> router TCP 80/443 -> Caddy
                                               |-- React production files
                                               `-- /api and /admin -> Waitress -> Django -> PostgreSQL
                                                                            `-> private local media
```

Replace every occurrence of `repository.example.edu.ph` with the school's real
domain. The examples assume the application is installed at `C:\eRepository`.

## 1. Do not expose an unsupported Windows installation

Windows 10 Pro reached end of support on October 14, 2025 and no longer receives
normal security updates. A public school repository contains personal data and
must not be hosted on an unsupported operating system. Before deployment, do one
of the following:

1. Upgrade the PC to a fully patched Windows 11 Pro release.
2. Replace it with supported hardware running Windows 11 Pro or Windows Server.
3. As a temporary exception only, enroll the PC in Microsoft's applicable
   Extended Security Updates program and record a firm migration date.

Microsoft's notice is at
https://learn.microsoft.com/en-us/lifecycle/announcements/windows-10-end-of-support.

## 2. Required equipment, accounts, and software

### Equipment and connectivity

- Dedicated PC: 4 physical CPU cores, 16 GB RAM, and an SSD at minimum.
- Storage sized for at least three years of uploads. The application currently
  allows 50 MB per document; 500 faculty uploads per month at 10 MB average is
  about 60 GB/year before backups and revision history.
- A separate external USB backup disk, NAS/network share, or approved encrypted
  off-site target. The server may have only `C:`, but another folder on that same
  physical disk is not a backup.
- UPS with USB shutdown support, wired Ethernet, and router/admin access.
- A business Internet connection with adequate upload speed and preferably one
  static public IPv4 address.
- School-controlled GoDaddy, Google Cloud, SMTP/mail, and GitHub accounts with 2FA.

### Software

- Supported Windows 11 Pro or Windows Server, Windows Defender, and BitLocker.
- Git for Windows: https://git-scm.com/download/win
- 64-bit Python 3.12 or another version supported by Django 5.2.
- Node.js 22 LTS (build-time only): https://nodejs.org/
- PostgreSQL and its command-line tools: https://www.postgresql.org/download/windows/
- Caddy web server: https://caddyserver.com/download
- WinSW service wrapper: https://github.com/winsw/winsw/releases
- Optional pgAdmin (included by the standard PostgreSQL Windows installer).
- Optional encrypted off-site backup provider and a VPN such as Tailscale for
  remote administration. Never publish RDP port 3389 to the Internet.

Do not install XAMPP, IIS, Apache, MySQL, Docker Desktop, or Vite's preview server
for this deployment. They are not part of this architecture.

## 3. Prepare Windows

1. Back up the PC and upgrade/replace Windows 10 before continuing.
2. Install all Windows, firmware, and driver updates. Enable automatic security
   updates and Defender real-time/cloud protection.
3. In the BIOS, enable automatic power-on after AC loss if available.
4. Connect the UPS and configure graceful shutdown.
5. Set the PC name, for example `JSHS-EREPO`, and set the timezone to
   `(UTC+08:00) Kuala Lumpur, Singapore`.
6. Set the Windows network profile to **Private**, reserve the PC's LAN address
   in DHCP (for example `192.168.1.20`), and use wired Ethernet.
7. In **Power Options**, disable sleep and hibernation while plugged in. The
   monitor may turn off.
8. Enable BitLocker and store the recovery key in two school-controlled secure
   locations, not only on this PC.
9. Create a named administrator account for maintenance. Do not use a shared
   `Administrator` password for routine work.
10. Create these folders in an elevated PowerShell window:

```powershell
New-Item -ItemType Directory -Force C:\eRepository\data\media
New-Item -ItemType Directory -Force C:\eRepository\logs
New-Item -ItemType Directory -Force C:\eRepository\tools\caddy
New-Item -ItemType Directory -Force C:\eRepository\services\backend
New-Item -ItemType Directory -Force C:\eRepository\services\caddy
```

## 4. Install the prerequisites

Install Git, Python, Node.js, and PostgreSQL from their official installers.

During Python installation:

- Select **Install for all users** and **Add python.exe to PATH**.
- Confirm `py -3.12 --version` in a new PowerShell window.

During PostgreSQL installation:

- Use the default port `5432`.
- Give the built-in `postgres` administrator a unique password.
- Install Command Line Tools and optionally pgAdmin.
- Do not allow port 5432 through the Windows Firewall.

Verify:

```powershell
git --version
py -3.12 --version
node --version
npm --version
```

Download `caddy.exe` into `C:\eRepository\tools\caddy`. Download the WinSW
x64 executable later into each service folder as described in section 11.

## 5. Create the PostgreSQL database

Open pgAdmin's Query Tool while connected as `postgres`, or run the equivalent
commands with `psql`. Generate two different long random passwords: one for the
database role and one for Django's secret key.

Run this SQL after replacing the password:

```sql
CREATE ROLE erepository LOGIN PASSWORD 'REPLACE_WITH_A_LONG_UNIQUE_PASSWORD';
CREATE DATABASE erepository OWNER erepository ENCODING 'UTF8';
REVOKE ALL ON DATABASE erepository FROM PUBLIC;
```

Keep PostgreSQL restricted to localhost. In `postgresql.conf`, use:

```text
listen_addresses = 'localhost'
password_encryption = 'scram-sha-256'
```

Leave `pg_hba.conf` host entries on SCRAM authentication, then restart the
PostgreSQL Windows service. PostgreSQL must never be router-forwarded or exposed
to the Internet.

## 6. Transfer the solution from GitHub

Git transfers source code and migration history. It intentionally does not
transfer `.env`, the SQLite database, uploaded media, `node_modules`, or compiled
frontend files.

For a fresh production database, open elevated PowerShell:

```powershell
Set-Location C:\
git clone https://github.com/patriciobgm/eRepository.git
Set-Location C:\eRepository
git status
```

If the repository becomes private, use Git Credential Manager or a narrowly
scoped GitHub token/deploy key. Do not save a personal password in scripts.

### If real data already exists on the Mac

Do not copy a live SQLite file while Django is running. Stop the Mac backend,
then create a logical export and archive the media folder:

```bash
cd backend
.venv/bin/python manage.py dumpdata --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.permission --output production-data.json
tar -czf media-backup.tar.gz media
```

Transfer those two files over an encrypted external disk or secure LAN. Do not
commit them to GitHub. Complete migrations on Windows first, copy media into
`C:\eRepository\data\media`, then import:

```powershell
Set-Location C:\eRepository\backend
.\.venv\Scripts\python.exe manage.py loaddata production-data.json
```

Delete transfer copies securely after validation. If the current Mac contains
only demo data, start clean instead and never run `seed_demo` in production.

## 7. Configure and build Django

```powershell
Set-Location C:\eRepository\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item ..\deploy\windows\backend.env.example .env
```

If PowerShell blocks activation, use the virtual environment's full executable
path in every command; changing the machine-wide execution policy is unnecessary.

Generate a Django secret without printing any existing secret:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
```

Edit `backend\.env` and set all values. At minimum:

- `DJANGO_DEBUG=False`
- the new `DJANGO_SECRET_KEY`
- the real domain in allowed hosts, trusted origins, CORS, and frontend URL
- PostgreSQL database name/user/password
- `DJANGO_MEDIA_ROOT=C:\eRepository\data\media`
- production Google client ID
- working SMTP configuration

The application now loads `backend\.env` automatically. `.env.example` is only a
template and must never contain real credentials. Restrict the production file:

```powershell
icacls C:\eRepository\backend\.env /inheritance:r
icacls C:\eRepository\backend\.env /grant:r "SYSTEM:(R)" "Administrators:(F)"
```

Initialize and validate Django:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py check --deploy
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Review every warning from `check --deploy`. Do not run `seed_demo` on this server.

Test Waitress temporarily:

```powershell
.\.venv\Scripts\python.exe -m waitress --listen=127.0.0.1:8000 --threads=8 --max-request-body-size=57671680 config.wsgi:application
```

In a second PowerShell window, run:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health/
```

It must return `status: ok`. Stop the temporary server with Ctrl+C.

## 8. Configure and build React

The frontend's environment variables are embedded at build time. Changing its
`.env` after `npm run build` has no effect until it is rebuilt.

```powershell
Set-Location C:\eRepository\frontend
Copy-Item ..\deploy\windows\frontend.env.production.example .env
notepad .env
npm ci
npm run lint
npm run build
```

Set `VITE_API_URL=/api` so browser traffic uses the same HTTPS origin. Put the
same Google client ID used by Django in `VITE_GOOGLE_CLIENT_ID`. The build output
must exist at `C:\eRepository\frontend\dist`.

## 9. Configure Google login and email

In Google Cloud Console, open the existing **Web application** OAuth client and
add this exact Authorized JavaScript origin:

```text
https://repository.example.edu.ph
```

If `www` is only redirected to the canonical non-www domain, it does not need to
be used by the application. This project uses Google's popup ID-token flow, so it
does not require a client secret or redirect URI. Google documents the production
origin requirement at
https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid.

For email, prefer the school's Google Workspace SMTP relay or an approved
transactional mail account. Put its host, port, username, and app-specific/SMTP
password in `backend\.env`. Do not use a teacher's ordinary Google password.
Confirm registration notices, password-reset links, Google-only password-reset
guidance, and password-change confirmation messages all arrive successfully.

## 10. Configure GoDaddy DNS and the school network

First ask the ISP these questions:

- Is the school connection behind CGNAT?
- Is inbound TCP 80 and 443 allowed?
- Is a static public IPv4 address available?

If the public IP shown by the router differs from an external IP-check service,
the school may be behind CGNAT. Direct port forwarding will not work until the ISP
provides a public address. Do not proceed by exposing arbitrary router services.

With a static public IP:

1. Give the server a DHCP reservation such as `192.168.1.20`.
2. Forward router TCP port 80 to `192.168.1.20:80`.
3. Forward router TCP port 443 to `192.168.1.20:443`.
4. Do not forward 5432, 8000, 3389, file sharing, or router management ports.
5. In GoDaddy, open **Domain Portfolio -> domain -> DNS -> Add New Record**.
6. Add an `A` record: Name `@`, Value = the static public IPv4 address.
7. Add a `CNAME`: Name `www`, Value `@` (or the root hostname accepted by the
   GoDaddy UI).
8. Do not use GoDaddy URL/domain forwarding.

GoDaddy notes that DNS propagation may take up to 48 hours:
https://www.godaddy.com/help/add-or-edit-an-a-record-42546.

Create Windows Firewall rules in elevated PowerShell. Bind the rules to the Caddy
program, not every process:

```powershell
New-NetFirewallRule -DisplayName "eRepository HTTPS" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 443 -Program "C:\eRepository\tools\caddy\caddy.exe"
New-NetFirewallRule -DisplayName "eRepository HTTP ACME" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80 -Program "C:\eRepository\tools\caddy\caddy.exe"
```

Do not add an inbound rule for Waitress port 8000; it listens only on loopback.

If there is no static public IP or port forwarding is prohibited, use a managed
outbound tunnel/CDN design instead. That requires a separate, documented DNS and
proxy configuration and should be agreed with the school's privacy officer; do
not mix that design with the direct Caddy certificate steps in this guide.

## 11. Configure Caddy and Windows services

Copy and edit the Caddy configuration:

```powershell
Copy-Item C:\eRepository\deploy\windows\Caddyfile.example C:\eRepository\tools\caddy\Caddyfile
notepad C:\eRepository\tools\caddy\Caddyfile
C:\eRepository\tools\caddy\caddy.exe validate --config C:\eRepository\tools\caddy\Caddyfile --adapter caddyfile
```

Replace both example hostnames. Caddy will obtain and renew public HTTPS
certificates automatically once DNS and ports 80/443 work. Its official Windows
service options are documented at https://caddyserver.com/docs/running.

### Backend service

1. Put a copy of the WinSW x64 executable at
   `C:\eRepository\services\backend\erepository-backend-service.exe`.
2. Copy the matching XML beside it:

```powershell
Copy-Item C:\eRepository\deploy\windows\erepository-backend-service.xml.example C:\eRepository\services\backend\erepository-backend-service.xml
Set-Location C:\eRepository\services\backend
.\erepository-backend-service.exe install
.\erepository-backend-service.exe start
```

### Caddy service

1. Put another WinSW x64 executable at
   `C:\eRepository\services\caddy\caddy-service.exe`.
2. Copy and install the matching configuration:

```powershell
Copy-Item C:\eRepository\deploy\windows\caddy-service.xml.example C:\eRepository\services\caddy\caddy-service.xml
Set-Location C:\eRepository\services\caddy
.\caddy-service.exe install
.\caddy-service.exe start
```

Confirm both services are `Running` and `Automatic` in `services.msc`. Check
`C:\eRepository\logs` for startup errors. Waitress is used because Django's
development server is not suitable for production and Waitress supports Windows.

## 12. First production verification

Test from a phone using cellular data, not school Wi-Fi:

1. `https://repository.example.edu.ph` opens with a valid certificate.
2. `http://...` redirects to HTTPS and `www` redirects to the canonical hostname.
3. `https://repository.example.edu.ph/api/health/` returns `{"status":"ok"}`.
4. Log in as the newly created superadmin and change/secure its credentials.
5. Create/approve a test teacher, then test password and Google login.
6. Test 2FA after confirming Windows time synchronization is accurate.
7. Upload a harmless PDF to My Repository and a shared repository.
8. Download it, add a revision, verify ownership/history, and check activity logs.
9. Verify profile avatar display without making document storage publicly browsable.
10. Test forgot-password and confirmation email delivery.
11. Confirm users cannot reach another user's private documents by changing IDs.
12. Confirm `https://domain/media/documents/...` returns 404.
13. Restart Windows and verify PostgreSQL, backend, and Caddy return automatically.

Only after this checklist passes should staff receive the production URL.

## 13. Automated backups and restore testing

Use the included `deploy\windows\backup.ps1`. It intentionally defaults to a
placeholder NAS path because this server has only a `C:` drive. Replace
`\\BACKUP-NAS\eRepository-Backups` with either a real UNC network share such as
`\\JSHS-NAS\Backups\eRepository` or the drive letter of an external USB disk.
Do not change it to a folder on `C:` and call that the backup. The example uses
PostgreSQL 17; change `-PgDump` if another supported version is installed.
Configure PostgreSQL's `pgpass.conf` for the service account so a scheduled backup
does not contain a password in the command line. Restrict that file to
Administrators and SYSTEM.

Test manually against the real NAS share (the account running the command must
have write access):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\eRepository\deploy\windows\backup.ps1 -BackupRoot "\\JSHS-NAS\Backups\eRepository"
```

Then create a Task Scheduler task:

- Run as a controlled service/backup account whether the user is logged on or not.
- Trigger daily outside school hours.
- Program: `powershell.exe`
- Arguments:
  `-NoProfile -ExecutionPolicy Bypass -File C:\eRepository\deploy\windows\backup.ps1 -BackupRoot "\\JSHS-NAS\Backups\eRepository"`
- Start in: `C:\eRepository`
- Fail the task on a non-zero exit and notify the responsible administrator.

Maintain a 3-2-1 backup policy: production plus two copies, on two media types,
with one encrypted copy off-site. Back up both PostgreSQL and the complete media
directory; either one alone is insufficient. Keep daily, monthly, and annual
retention according to school policy. Test a full restore on another machine at
least quarterly and record the result.

Typical clean restore sequence:

```powershell
pg_restore --clean --if-exists --no-owner --host=127.0.0.1 --username=erepository --dbname=erepository "\\JSHS-NAS\Backups\eRepository\TIMESTAMP\database.dump"
robocopy "\\JSHS-NAS\Backups\eRepository\TIMESTAMP\media" C:\eRepository\data\media /E /COPY:DAT /DCOPY:DAT
```

Stop the backend during a disaster restore. Never test restoration over the only
production database.

## 14. Safe application updates

Schedule downtime, verify the previous night's backup, then use elevated
PowerShell:

```powershell
C:\eRepository\services\backend\erepository-backend-service.exe stop
Set-Location C:\eRepository
git fetch origin
git status
git pull --ff-only origin main
Set-Location C:\eRepository\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\.venv\Scripts\python.exe manage.py check --deploy
Set-Location C:\eRepository\frontend
npm ci
npm run lint
npm run build
C:\eRepository\services\backend\erepository-backend-service.exe start
C:\eRepository\tools\caddy\caddy.exe validate --config C:\eRepository\tools\caddy\Caddyfile --adapter caddyfile
C:\eRepository\services\caddy\caddy-service.exe restart
```

Run the production verification checks after every update. A Git rollback does
not reverse database migrations; restore the tested database/media backup when a
release requires a data rollback.

## 15. Ongoing operating controls

- Assign a primary and backup system custodian; document who holds each account.
- Review Windows, PostgreSQL, Caddy, Python, and Node security updates monthly.
- Review failed logins, registration approvals, superadmin activity, free disk
  space, backup results, and Caddy/backend logs weekly.
- Keep at least 25% disk space free and alert before storage is exhausted.
- Do not browse the web, read email, or use this PC as an ordinary workstation.
- Do not disable Defender or exclude the media directory from scanning.
- Establish document retention, account offboarding, incident response, breach
  reporting, and restore procedures with the school's Data Protection Officer.
- Remove staff access immediately when they leave or change responsibility.
- Renew and protect the GoDaddy domain; enable auto-renewal, registrar lock, 2FA,
  and school-owned recovery contacts.

The server being online is not proof that it is healthy. Backups, restore tests,
patching, monitoring, and named operational ownership are part of the deployment.
