import json, sys, time
from datetime import datetime, timezone
sys.path.insert(0, ".")
import scraper as s
tokens = json.loads(s.http(f"{s.SITE}/_api/v1/access-tokens", tries=2, wait=20))
inst = tokens["apps"][s.WIX_CODE_APP]["instance"]
feats = {str(f.get("externalId")): f for f in s.wix_query(inst, "SyncFeatures")[0]}
up = s.coming_soon(feats, datetime.now(timezone.utc))
print(len(up), "upcoming")
for m in sorted(up, key=lambda m: m["date_started"]):
    hit = s.imdb_find(m["title"], 2026)
    d = s.imdb_details(hit["id"]) if hit else {}
    print(m["date_started"], m["title"], "|", m["title_he"], "| kids", m["kids"], "dub", m["dubbed_only"], "| rank", d.get("popularity"), "votes", d.get("imdb_votes"), d.get("year"), d.get("directors"), d.get("actors"))
    time.sleep(0.3)
# rerun
