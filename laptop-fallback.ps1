# Backup for the weekly scan, run by Windows Task Scheduler on Oren's laptop on Sunday mornings.
# If GitHub's run didn't publish today's scan (Cinema City / RT sometimes block cloud servers),
# run the same scraper from the laptop's home connection and publish it.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
git pull -q
$today = (Get-Date).ToString("yyyy-MM-dd")
$data = Get-Content docs/data.json -Raw -Encoding UTF8 | ConvertFrom-Json
if ($data.generated_at.StartsWith($today)) { "scan for $today already published"; exit 0 }
$env:PYTHONIOENCODING = "utf-8"
$env:NTFY_TOPIC = [Environment]::GetEnvironmentVariable("CINEMA_NTFY_TOPIC", "User")
uv run -q --with tzdata python scraper.py
if ($LASTEXITCODE) { throw "scraper failed" }
git add docs/data.json
git -c user.name="cinema-bot (laptop)" -c user.email="tipul10000-droid@users.noreply.github.com" commit -q -m "Weekly movie scan $today (laptop)"
if ($LASTEXITCODE) { throw "commit failed" }
git push -q
if ($LASTEXITCODE) { throw "push failed" }
Invoke-RestMethod -Method Post "https://emgtyfksnofzzlutngbf.supabase.co/functions/v1/cinema-push?action=send" | Out-Null
"published from laptop"
