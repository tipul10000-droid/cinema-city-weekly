# Cinema City weekly

Every Sunday at 08:00 (Israel time) a GitHub Action scans the movies now showing at [Cinema City](https://www.cinema-city.co.il/), adds IMDb and Rotten Tomatoes scores, directors and lead actors, publishes them to the page below and sends a push notification via [ntfy](https://ntfy.sh).

Page: https://tipul10000-droid.github.io/cinema-city-weekly/

- `scraper.py`: stdlib-only Python. `python scraper.py --no-push` runs locally without notifying.
- Notification topic is the `NTFY_TOPIC` repository secret; subscribe to it in the ntfy app.
- Run on demand: Actions tab, "Weekly Cinema City scan", Run workflow.
