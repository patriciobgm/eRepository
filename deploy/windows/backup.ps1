param(
    [string]$BackupRoot = "\\BACKUP-NAS\eRepository-Backups",
    [string]$MediaRoot = "C:\eRepository\data\media",
    [string]$DatabaseName = "erepository",
    [string]$DatabaseUser = "erepository",
    [string]$DatabaseHost = "127.0.0.1",
    [string]$PgDump = "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"
)

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$destination = Join-Path $BackupRoot $timestamp
$mediaDestination = Join-Path $destination "media"
New-Item -ItemType Directory -Path $mediaDestination -Force | Out-Null

& $PgDump --host=$DatabaseHost --username=$DatabaseUser --format=custom --file=(Join-Path $destination "database.dump") $DatabaseName
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump failed with exit code $LASTEXITCODE"
}

& robocopy $MediaRoot $mediaDestination /E /COPY:DAT /DCOPY:DAT /R:2 /W:5 /NP
if ($LASTEXITCODE -ge 8) {
    throw "Media backup failed with robocopy exit code $LASTEXITCODE"
}

Get-FileHash (Join-Path $destination "database.dump") -Algorithm SHA256 |
    Format-List | Out-File (Join-Path $destination "database.sha256.txt")

Write-Output "Backup completed: $destination"
