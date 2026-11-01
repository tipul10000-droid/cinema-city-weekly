# Cinema City weekly ("מה בסינמה סיטי השבוע")

A Hebrew PWA that shows the movies playing this week at Cinema City (Glilot, Rishon LeZion, Kfar Saba, Netanya)
with IMDb and Rotten Tomatoes scores, director and lead actors, special halls, "new" and "leaving soon" badges,
a "coming soon" tab with IMDb watchlist counts, per-user ★ favorites and ✓ watched marks, and Web Push notifications.

- Family page (login: Oren / Lior / Evyatar): https://tipul10000-droid.github.io/cinema-city-weekly/
- Public page (no login, separate data): https://tipul10000-droid.github.io/cinema-city-weekly/app/

No build step, no npm, no server of our own: static files on GitHub Pages + one Supabase Edge Function.

## How it fits together

```
GitHub Action (Sunday)          laptop fallback (Sunday, Windows Task Scheduler)
        \                         /
         scraper.py  ->  docs/data.json, docs/archive.json, docs/posters/*.jpg  ->  commit to main
                                    |
                     GitHub Pages serves docs/ (family app)  +  docs/app/ (public app, generated)
                                    |
       POST cinema-push?action=send -> Supabase Edge Function reads docs/data.json on main -> Web Push
```

| Path | What it is |
|---|---|
| `scraper.py` | Python 3, standard library only. Scans Cinema City, adds IMDb + RT, writes `docs/data.json` and `docs/archive.json`, saves poster copies. |
| `docs/index.html` | The whole family app (single file: HTML + CSS + JS). Edit only this one. |
| `docs/app/` | Public app. **Generated** from `docs/index.html` by `tools/make_public.py` (workflow `public-copy.yml`). Never edit by hand. |
| `docs/data.json` | This week's scan (`generated_at`, `movies[]`, `upcoming[]`). |
| `docs/archive.json` | Every movie that ever appeared, keyed by normalized title. Used by the "✓ ראיתי" tab. Never delete or reset. |
| `docs/posters/<norm>.jpg` | Poster copies (Cinema City poster links expire with 403). Never delete. |
| `docs/sw.js`, `docs/manifest.json`, icons | PWA service worker (push handling) and manifest. |
| `supabase/cinema-push/index.ts` | Edge Function source (deployed as `cinema-push`, `verify_jwt = false`). |
| `supabase/schema.sql` | The `cinema_*` tables it uses. |
| `laptop-fallback.ps1` | Re-runs the scan from Oren's laptop when the cloud run was blocked. |
| `tools/make_public.py` | Builds `docs/app/` from `docs/index.html`. |

## Data sources

- **Cinema City** (a Wix site): get an anonymous token from `https://www.cinema-city.co.il/_api/v1/access-tokens`,
  then query collections with `/_api/cloud-data/v2/items/query`.
  - `SyncPresentations` is the source of truth for screenings (~3,000 rows, 1,000 per page, cursor paging).
    `venueTypeName`: Lounge / ONYX (Glilot), Prime (Netanya, Kfar Saba), VIP (Rishon LeZion).
    "Infinity Vision" is a suffix in the feature name.
  - `SyncFeatures` (posters, release dates, upcoming movies) often answers 429; treated as optional.
  - Wix blocks after a few runs in an hour: space retries out, never loop. Cinema City is blocked from some
    cloud IPs, which is why the laptop fallback exists.
- **IMDb**: suggestion API (`v3.sg.media-imdb.com/suggestion/...`) to find the title, then
  `caching.graphql.imdb.com` (header `x-imdb-client-name`) for rating, directors, cast, watchlist count.
- **Rotten Tomatoes**: RT blocks GitHub runners, so scores come from RT's public Algolia search index (app id `79FRDP12PN`).

## Running

```bash
python3 scraper.py --no-push      # scan and write docs/*.json locally, no notification
python3 scraper.py --scheduled    # what the Action runs: skips before 08:00 Israel time and if today's scan exists
python3 tools/make_public.py      # rebuild docs/app/ (CI does this on push to main)
python3 -m http.server -d docs    # view the page at http://localhost:8000/
```

Python 3.9+ (uses `zoneinfo`; on Windows add `tzdata`, e.g. `uv run --with tzdata python scraper.py`).

## Deploying

- **Page**: GitHub Pages, branch `main`, folder `/docs`. Merging to `main` deploys.
- **Weekly scan**: `.github/workflows/weekly.yml`, Sundays, cron at 05/06/08/10 UTC (the first run at or after
  08:00 Israel time does the work; the rest are retries). Commits the data and calls `cinema-push?action=send`.
- **Release-day push**: `.github/workflows/released.yml`, daily 07:00 UTC, calls `cinema-push?action=released`.
- **Public app sync**: `.github/workflows/public-copy.yml`, on push to `main` that touches the app files.
- **Edge Function**: Supabase project `family-apps` (`emgtyfksnofzzlutngbf`). Deploy with
  `supabase functions deploy cinema-push --no-verify-jwt --project-ref emgtyfksnofzzlutngbf`
  (or the Supabase dashboard / MCP). The project is shared with other apps: only touch `cinema_*`.
- **Laptop fallback**: Windows Task Scheduler task `CinemaCityWeeklyFallback` on Oren's laptop, Sundays 08:40 and 13:40,
  runs `powershell -File laptop-fallback.ps1` in the repo folder. It publishes only if `docs/data.json` on `main`
  is not from today.

## Environment variables and secrets (names only)

| Name | Where | Used for |
|---|---|---|
| `NTFY_TOPIC` | GitHub repo secret | Legacy ntfy.sh notification topic (optional; Web Push is the main channel). |
| `PAGE_URL` | optional env for `scraper.py` | Link in notifications; defaults to the family page. |
| `CINEMA_NTFY_TOPIC` | Windows user env var on the laptop | Passed to the scraper as `NTFY_TOPIC` by `laptop-fallback.ps1`. |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | set automatically by Supabase for Edge Functions | DB access from `cinema-push`. |
| `cinema_secrets` rows: `vapid_public`, `vapid_private`, `user_password`, `upcoming_known`, `released_last` | Supabase table (server-only) | VAPID keys (generated on first use), the family login password, de-duplication state. |

No keys are needed by the page itself: it calls the Edge Function URL directly.

## Edge Function API (`/functions/v1/cinema-push`)

`pubkey`, `login`, `subscribe`, `unsubscribe`, `prefs` (family marks, `x-cinema-pass` header),
`pprefs` (public marks by uuid), `send` (weekly push, once per scan), `released` (daily "it's out" push).
See the header comment in `supabase/cinema-push/index.ts`.

## Rules for changes

- Edit `docs/index.html` only; both the family and public apps must keep working.
- Never delete `docs/archive.json` or `docs/posters/`.
- Don't hammer Cinema City (Wix rate limit). Don't scan in a loop.
